"""
Pipeline Socket class for managing socket operations in both server and client modes - Python Implementation

This module provides socket management functionality for the Innospace Pipeline service,
supporting both client and server modes with event-driven communication.
"""

import socket
import threading
import time
import select
import struct
import errno
import logging
from enum import IntEnum
from collections import deque
import queue

# For Python 3.5 compatibility, define Any as object
try:
    from typing import Any, Callable, Dict, List
    # If typing is available, use it
except ImportError:
    # If typing is not available, define fallbacks
    Any = object
    Callable = object
    Dict = dict
    List = list

# Set up logger for the module
logger = logging.getLogger(__name__)


class SocketMode(IntEnum):
    """Socket operation mode (client or server)."""
    CLIENT = 0  # Client mode
    SERVER = 1  # Server mode


class SocketEvent(IntEnum):
    """Socket event types for callbacks."""
    CONNECTED = 0      # Connection established
    DISCONNECTED = 1   # Connection closed
    DATA_RECEIVED = 2  # Data received
    SEND_COMPLETE = 3  # Data send completed
    ERROR = 4          # Error occurred


class SocketEventData:
    """Data structure for socket event callback information."""
    
    def __init__(self, event_type: SocketEvent = SocketEvent.ERROR, 
                 service_name: str = "", data: bytes = b"", 
                 socket_fd: int = -1, client_fd: int = -1):
        """
        Initialize SocketEventData.
        
        Args:
            event_type: Type of socket event
            service_name: Name of the service associated with the event
            data: Data associated with the event (if any)
            socket_fd: Socket file descriptor
            client_fd: Client file descriptor (for server mode)
        """
        self.event_type = event_type
        self.service_name = service_name
        self.data = data
        self.socket_fd = socket_fd
        self.client_fd = client_fd


# Define SocketEventCallback as a type alias for function that takes SocketEventData and returns None
SocketEventCallback = Callable[[Any], None]  # Using Any to avoid issues with Callable in Python 3.5


class PipelineSocket:
    """Pipeline Socket class for managing socket operations."""
    
    def __init__(self, mode: SocketMode, address: str, port: int, 
                 max_queue_size: int = 100000, send_wait_timeout_ms: int = 100):
        """
        Initialize a PipelineSocket instance.
        
        Args:
            mode: The socket mode (client or server)
            address: The address to connect to (client) or bind to (server)
            port: The port to connect to (client) or bind to (server)
            max_queue_size: Maximum size of the send queue (default: 100000)
            send_wait_timeout_ms: Default timeout for send_wait (milliseconds)
        """
        self.mode = mode
        self.address = address
        self.port = port
        self.max_queue_size = max_queue_size
        self.send_wait_timeout_ms = send_wait_timeout_ms
        
        # Handle abstraction: Maps integer handles <-> socket file descriptors
        # Handles provide a lightweight identifier for sockets that matches C++ implementation
        # where handles are integer file descriptors. This two-way mapping enables:
        # 1. Converting socket fd to unique handle for external APIs
        # 2. Looking up socket fd from handle for internal operations
        self.next_client_handle = 1  # Monotonic counter for generating unique client handles
        self.handle_to_socket = {}  # Map from handle -> socket fd
        self.socket_to_handle = {}  # Map from socket fd -> handle
        
        # Main socket file descriptor (server listening socket or client connection socket)
        self.socket_fd = None
        
        # Thread lifecycle flags and thread objects
        self.running = False
        self.main_thread = None   # Main loop thread for select() and connection management
        self.send_thread = None   # Dedicated thread for transmitting queued data
        self.event_thread = None  # Dedicated thread for delivering events to callbacks
        
        # Stop synchronization - used for clean shutdown
        self.stop_mutex = threading.Lock()
        self.stop_cv = threading.Condition(self.stop_mutex)
        
        # Send queue: Batched transmission queue to reduce syscall overhead
        # Contains tuples of (client_handle, data_bytes) waiting to be sent
        # Producer: send_wait(), Consumer: send_thread_func()
        self.send_queue = deque()  # Queue of items to send
        self.send_queue_mutex = threading.Lock()
        self.send_queue_cv = threading.Condition(self.send_queue_mutex)
        
        # Receive buffers: Per-client accumulation of partial frame data
        # TCP is stream-oriented - frames may arrive fragmented across recv() calls
        # Map: socket object -> bytearray buffer
        self.client_buffers = {}  # Map from client socket object to receive buffer
        
        # Socket object cache: Efficient lookup to avoid repeated fromfd() calls
        # Map: client file descriptor (int) -> socket.socket object
        self.client_sockets = {}  # Map from client_fd to socket object
        self.clients_mutex = threading.RLock()  # Reentrant lock for nested access patterns
        
        # Event queue: Socket-level events (CONNECTED, DISCONNECTED, DATA_RECEIVED, etc.)
        # Producer: main_thread_func(), Consumer: event_thread_func()
        self.event_queue = queue.Queue()  # Queue of socket events
        self.event_queue_mutex = threading.Lock()
        self.event_queue_cv = threading.Condition(self.event_queue_mutex)
        
        # User-registered callback for socket events
        self.event_callback = None  # Callback function for socket events
        self.callback_mutex = threading.Lock()
        
        # Connection state tracking
        self.connected = False  # True when client mode is connected to server
        self.connected_clients = {}  # Map from client fd -> connection status (server mode)
        
        # Event for stopping threads - thread-safe signal mechanism
        self.stop_event = threading.Event()
    
    def flush_send_buffer(self):
        """Flush the send buffer (clear queued data)."""
        with self.send_queue_mutex:
            self.send_queue.clear()
    
    def send_wait(self, data: bytes, client_handle: int = -1) -> bool:
        """
        Send data and wait for completion or timeout.
        
        Queues data for transmission and blocks until sent or timeout expires.
        In server mode, client_handle specifies target client. In client mode,
        client_handle is ignored (sends to connected server).
        
        :param data: Binary data to transmit
        :type data: bytes
        :param client_handle: Target client handle (server mode only, -1 for client mode)
        :type client_handle: int
        :return: True if send completed successfully, False if timeout or error
        :rtype: bool
        """
        if not self.running:
            return False
        
        client_socket = -1
        if self.mode == SocketMode.SERVER:
            if client_handle != -1:
                client_socket = self.get_socket_for_handle(client_handle)
            else:
                logger.warning("No client handle provided for send_wait in server mode")
                return False
        else:
            client_socket = self.socket_fd.fileno() if self.socket_fd else -1
        
        timeout_ms = self.send_wait_timeout_ms
        
        send_complete = threading.Event()
        send_success = [False]  # Use list to allow modification in callback
        
        def temp_callback(event_data):
            if (event_data.event_type == SocketEvent.SEND_COMPLETE and 
                (client_socket == -1 or event_data.client_fd == client_socket)):
                send_success[0] = True
                send_complete.set()
            elif (event_data.event_type == SocketEvent.ERROR and 
                  (client_socket == -1 or event_data.client_fd == client_socket)):
                send_success[0] = False
                send_complete.set()
        
        # Save old callback
        old_callback = None
        with self.callback_mutex:
            old_callback = self.event_callback
            self.event_callback = temp_callback
        
        # Queue the data for sending
        queued = self.send_data(data, client_socket)
        if not queued:
            # Restore old callback
            with self.callback_mutex:
                self.event_callback = old_callback
            return False
        
        # Wait for send completion or timeout
        send_complete.wait(timeout=timeout_ms/1000.0)
        
        # Restore old callback
        with self.callback_mutex:
            self.event_callback = old_callback
        
        return send_success[0]
    
    def send_data(self, data: bytes, client_handle: int = -1) -> bool:
        """
        Send data asynchronously using handle.
        
        Queues data for transmission without blocking. The actual transmission
        occurs in send_thread. Returns immediately after queuing.
        
        :param data: Binary data to transmit
        :type data: bytes
        :param client_handle: Target client handle (server mode only, -1 for client mode)
        :type client_handle: int
        :return: True if data was queued for sending, False if queue is full
        :rtype: bool
        """
        if not self.running:
            return False
        
        with self.send_queue_mutex:
            # Check if queue is at maximum size
            if len(self.send_queue) >= self.max_queue_size:
                logger.warning("Send queue is full, dropping data")
                return False
            
            self.send_queue.append((data, client_handle))
            self.send_queue_cv.notify()
            return True
    
    def get_handle_for_socket(self, client_socket: int) -> int:
        """
        Get handle for a client socket fd.
        
        :param client_socket: Socket file descriptor
        :type client_socket: int
        :return: Unique handle for the socket, or -1 if not found
        :rtype: int
        
        .. note::
           Server mode only - returns -1 in client mode.
        """
        with self.clients_mutex:
            return self.socket_to_handle.get(client_socket, -1)
    
    def get_socket_for_handle(self, client_handle: int) -> int:
        """
        Get socket fd for a client handle.
        
        :param client_handle: Unique client handle
        :type client_handle: int
        :return: Socket file descriptor, or -1 if not found
        :rtype: int
        
        .. note::
           Server mode only - returns -1 in client mode.
        """
        with self.clients_mutex:
            return self.handle_to_socket.get(client_handle, -1)
    
    def get_connected_client_handles(self) -> List[int]:
        """
        Get all active client handles.
        
        :return: List of handles for currently connected clients
        :rtype: List[int]
        
        .. note::
           Server mode only - returns empty list in client mode.
        """
        with self.clients_mutex:
            return list(self.handle_to_socket.keys())
    
    def start(self):
        """Start the socket operations."""
        if self.running:
            logger.warning("Already running")
            return
        
        logger.info("Starting in {} mode on {}:{}".format(
            "CLIENT" if self.mode == SocketMode.CLIENT else "SERVER",
            self.address, self.port))
        
        self.running = True
        self.stop_event.clear()
        
        # Start the main thread for handling socket operations
        self.main_thread = threading.Thread(target=self.main_thread_func)
        self.main_thread.daemon = True
        self.main_thread.start()
        
        # Start the send thread for handling asynchronous sending
        self.send_thread = threading.Thread(target=self.send_thread_func)
        self.send_thread.daemon = True
        self.send_thread.start()
        
        # Start the event thread for handling event notifications
        self.event_thread = threading.Thread(target=self.event_thread_func)
        self.event_thread.daemon = True
        self.event_thread.start()
    
    def stop(self):
        """Stop the socket operations."""
        if not self.running:
            return
        
        logger.info("Stopping socket operations")
        
        self.running = False
        self.stop_event.set()
        
        # Notify threads to stop
        with self.send_queue_mutex:
            self.send_queue_cv.notify_all()
        
        with self.event_queue_mutex:
            self.event_queue_cv.notify_all()
        
        # Notify any threads waiting on stop_cv
        with self.stop_cv:
            self.stop_cv.notify_all()
        
        # Join threads
        if self.main_thread and self.main_thread.is_alive():
            self.main_thread.join()
        
        if self.send_thread and self.send_thread.is_alive():
            self.send_thread.join()
        
        if self.event_thread and self.event_thread.is_alive():
            self.event_thread.join()
        
        self.cleanup()
    
    def set_event_callback(self, callback: SocketEventCallback):
        """
        Set the event callback function.
        
        Args:
            callback: The callback function to set
        """
        with self.callback_mutex:
            self.event_callback = callback
    
    def is_connected(self) -> bool:
        """
        Check if socket is connected (client mode) or running (server mode).
        
        Returns:
            True if connected/running, false otherwise
        """
        return self.connected
    
    def get_connected_clients(self) -> List[int]:
        """
        Get the list of connected client sockets (server mode only).
        
        Returns:
            List of connected client socket file descriptors
        """
        if self.mode != SocketMode.SERVER:
            return []
        
        with self.clients_mutex:
            return [fd for fd, connected in self.connected_clients.items() if connected]
    
    def disconnect_client(self, client_socket: int):
        """
        Disconnect a specific client (server mode only).
        
        Args:
            client_socket: The client socket to disconnect
        """
        if self.mode != SocketMode.SERVER or self.socket_fd is None:
            return
        
        # Remove client socket from tracking
        with self.clients_mutex:
            if client_socket in self.connected_clients:
                # Remove from connected clients
                del self.connected_clients[client_socket]
                if client_socket in self.client_buffers:
                    del self.client_buffers[client_socket]
                
                # Get and close socket object
                sock_obj = self.client_sockets.get(client_socket)
                if sock_obj:
                    try:
                        sock_obj.close()
                    except:
                        pass
                    del self.client_sockets[client_socket]
                
                # Remove handle mappings
                if client_socket in self.socket_to_handle:
                    handle = self.socket_to_handle[client_socket]
                    del self.handle_to_socket[handle]
                    del self.socket_to_handle[client_socket]
        
        # Queue disconnection event
        self.queue_event(SocketEventData(SocketEvent.DISCONNECTED, "", b"", 
                                       self.socket_fd.fileno() if self.socket_fd else -1, 
                                       client_socket))
    
    def send_to_all(self, data: bytes) -> bool:
        """
        Send data to all connected clients (server mode only).
        
        Args:
            data: The data to send to all clients
            
        Returns:
            True if data was queued for sending to all clients, false otherwise
        """
        if not self.running or self.mode != SocketMode.SERVER:
            return False
        
        # Send to all connected clients by using send_data with client_socket = -1
        # This will broadcast to all clients in server mode
        return self.send_data(data, -1)
    
    def main_thread_func(self):
        """Main thread function for handling socket operations."""
        if self.mode == SocketMode.CLIENT:
            self.handle_client_mode()
        else:
            self.handle_server_mode()
    
    def send_thread_func(self):
        """
        Thread function for handling sending operations.
        
        Implements batched transmission to reduce syscall overhead:
        
        1. Wait for items in send_queue (with timeout for clean shutdown)
        2. Collect up to batch_size items at once
        3. Send all batched items before checking queue again
        4. Handle both CLIENT mode (single destination) and SERVER mode (per-client/broadcast)
        
        .. note::
           Batch size of 500 balances throughput vs latency. Larger batches improve
           throughput but increase latency for queued messages.
        """
        batch_size = 500  # Increased batch size for higher throughput
        
        while self.running:
            items = []
            
            # Wait for data to send and collect batch atomically
            # Condition variable allows efficient blocking until data available
            with self.send_queue_cv:
                while not self.send_queue and self.running:
                    self.send_queue_cv.wait(0.5)  # 500ms timeout for clean shutdown
                
                if not self.running and not self.send_queue:
                    break
                
                # Collect up to batch_size items for batch processing
                # Minimizes time holding lock by extracting all pending items at once
                while self.send_queue and len(items) < batch_size:
                    items.append(self.send_queue.popleft())
            
            if not items:
                continue
            
            # Process all items in the batch
            for item in items:
                if isinstance(item, tuple) and len(item) == 2:
                    data, client_handle = item
                else:
                    # Handle case where item is not a tuple (fallback)
                    continue
                if not data:
                    continue
                
                # Send the data - mode determines routing strategy
                if self.mode == SocketMode.CLIENT:
                    # CLIENT mode: send to connected server socket
                    # client_handle is ignored (always -1 in client mode)
                    self.send_to_socket(self.socket_fd, data)
                    # Skip SEND_COMPLETE event for performance (omit callback overhead)
                else:
                    # SERVER mode: route based on client_handle
                    if client_handle >= 0:
                        # Unicast: send to specific client identified by handle
                        client_socket = self.get_socket_for_handle(client_handle)
                        if client_socket != -1:
                            self.send_to_socket(client_socket, data)
                        # Skip SEND_COMPLETE event for performance
                    else:
                        # Broadcast: send to all connected clients
                        # client_handle < 0 indicates broadcast mode
                        failed_clients = []
                        with self.clients_mutex:
                            for client_fd, connected in self.connected_clients.items():
                                if connected:  # Only send to connected clients
                                    if not self.send_to_socket(client_fd, data):
                                        failed_clients.append(client_fd)
                                    # Skip SEND_COMPLETE event for performance
                        
                        # Clean up failed connections
                        for failed_client in failed_clients:
                            self.handle_client_disconnection(failed_client)
    
    def event_thread_func(self):
        """Thread function for handling event notifications."""
        while self.running:
            try:
                # Wait for events to process
                event_data = self.event_queue.get(timeout=0.5)  # 500ms timeout
                with self.callback_mutex:
                    if self.event_callback:
                        self.event_callback(event_data)
            except queue.Empty:
                continue
    
    def handle_client_mode(self):
        """Handle client mode operations."""
        while self.running:
            if not self.connect_to_server():
                logger.warning("Failed to connect to server, retrying in 1 second")
                # Use condition variable wait instead of sleep so we can be interrupted
                with self.stop_cv:
                    self.stop_cv.wait(1.0)  # 1 second
                continue
            
            # Add the connected socket to epoll BEFORE setting connected_ flag and queuing event
            # This ensures the socket is properly registered before any events are processed
            self.connected = True
            self.queue_event(SocketEventData(SocketEvent.CONNECTED, "", b"", 
                                           self.socket_fd.fileno() if self.socket_fd else -1, -1))
            
            # Main event loop for client
            while self.running and self.connected:
                try:
                    # Use select to wait for data with timeout
                    ready, _, error = select.select([self.socket_fd], [], [self.socket_fd], 1.0)  # 1 second timeout
                    
                    if error:
                        # Socket error
                        logger.error("Socket error")
                        break
                    
                    if ready:
                        # Data available on client socket
                        chunk_size = 4096
                        try:
                            data = self.socket_fd.recv(chunk_size)
                            if data:
                                # Process received data
                                logger.debug("CLIENT mode: Received {} bytes from server".format(len(data)))
                                self.queue_event(SocketEventData(SocketEvent.DATA_RECEIVED, "", data, 
                                                               self.socket_fd.fileno() if self.socket_fd else -1, -1))
                            else:
                                # Connection closed by server
                                logger.info("Server disconnected")
                                break
                        except socket.error as e:
                            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                                # No more data to read
                                continue
                            else:
                                # Error occurred
                                logger.error("Read error: {}".format(e))
                                break
                except Exception as e:
                    logger.error("Select error: {}".format(e))
                    break
            
            # Clean up connection
            self.connected = False
            self.queue_event(SocketEventData(SocketEvent.DISCONNECTED, "", b"", 
                                           self.socket_fd.fileno() if self.socket_fd else -1, -1))
            
            if self.socket_fd:
                self.socket_fd.close()
                self.socket_fd = None
    
    def handle_server_mode(self):
        """Handle server mode operations."""
        if not self.start_server():
            logger.error("Failed to start server")
            return
        
        self.connected = True
        self.queue_event(SocketEventData(SocketEvent.CONNECTED, "", b"", 
                                       self.socket_fd.fileno() if self.socket_fd else -1, -1))
        
        # Main event loop for server
        while self.running and self.connected:
            try:
                # Use select() to wait for connections/data with timeout
                # Multiplexes I/O across server socket + all client sockets
                # Server socket: new connection requests
                # Client sockets: incoming data from existing clients
                read_list = [self.socket_fd]  # Start with server listening socket
                with self.clients_mutex:
                    # Add client socket objects (not FDs) to read list
                    # select() requires socket objects, not integer file descriptors
                    for client_fd, is_connected in self.connected_clients.items():
                        if is_connected and client_fd in self.client_sockets:
                            read_list.append(self.client_sockets[client_fd])
                
                ready, _, error_list = select.select(read_list, [], read_list, 1.0)  # 1 second timeout
                
                for sock in ready:
                    if sock == self.socket_fd:
                        # New client connection
                        self.handle_server_socket_event()
                    else:
                        # Data from existing client - get FD from socket object
                        self.handle_client_socket_event(sock.fileno())
                
                for sock in error_list:
                    if sock != self.socket_fd:
                        # Client disconnected or error
                        self.handle_client_disconnection(sock.fileno())
            except Exception as e:
                logger.error("Server loop error: {}".format(e))
                break
        
        self.connected = False
        self.queue_event(SocketEventData(SocketEvent.DISCONNECTED, "", b"", 
                                       self.socket_fd.fileno() if self.socket_fd else -1, -1))
    
    def handle_server_socket_event(self):
        """Handle server socket events (new connections)."""
        try:
            client_socket, client_addr = self.socket_fd.accept()
            
            # Set client socket to non-blocking
            client_socket.setblocking(False)
            
            # Add client socket to tracking
            with self.clients_mutex:
                client_handle = self.next_client_handle
                self.next_client_handle += 1
                client_fd = client_socket.fileno()
                self.connected_clients[client_fd] = True
                self.client_buffers[client_fd] = bytearray()
                self.client_sockets[client_fd] = client_socket  # Store socket object
                self.handle_to_socket[client_handle] = client_fd
                self.socket_to_handle[client_fd] = client_handle
            
            logger.info("New client connected: fd={}, handle={}, address={}:{}".format(
                client_socket.fileno(), client_handle, client_addr[0], client_addr[1]))
            
            self.queue_event(SocketEventData(SocketEvent.CONNECTED, "", b"", 
                                           self.socket_fd.fileno() if self.socket_fd else -1, 
                                           client_socket.fileno()))
        except Exception as e:
            logger.error("Accept failed: {}".format(e))
    
    def handle_client_socket_event(self, client_fd: int):
        """Handle client socket events (data reception).
        
        Args:
            client_fd: The client socket file descriptor
        """
        # Get socket object from FD
        client_socket = None
        with self.clients_mutex:
            if client_fd in self.client_sockets:
                client_socket = self.client_sockets[client_fd]
        
        if not client_socket:
            logger.warning("Client socket not found for FD: {}".format(client_fd))
            return
        
        try:
            # Increase chunk size for higher throughput
            chunk_size = 65536  # 64KB
            batch_events = []
            
            while True:
                try:
                    data = client_socket.recv(chunk_size)
                    if data:
                        # Batch received data
                        batch_events.append(data)
                        if len(batch_events) >= 128:
                            # Queue all events in one go
                            for event_data in batch_events:
                                self.queue_event(SocketEventData(SocketEvent.DATA_RECEIVED, "", event_data, 
                                                               self.socket_fd.fileno() if self.socket_fd else -1, 
                                                               client_fd))
                            batch_events = []
                    else:
                        # Client disconnected
                        for event_data in batch_events:
                            self.queue_event(SocketEventData(SocketEvent.DATA_RECEIVED, "", event_data, 
                                                           self.socket_fd.fileno() if self.socket_fd else -1, 
                                                           client_fd))
                        batch_events = []
                        self.handle_client_disconnection(client_fd)
                        break
                except socket.error as e:
                    if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                        # No more data available right now
                        for event_data in batch_events:
                            self.queue_event(SocketEventData(SocketEvent.DATA_RECEIVED, "", event_data, 
                                                           self.socket_fd.fileno() if self.socket_fd else -1, 
                                                           client_fd))
                        batch_events = []
                        break
                    else:
                        # Actual error occurred
                        for event_data in batch_events:
                            self.queue_event(SocketEventData(SocketEvent.DATA_RECEIVED, "", event_data, 
                                                           self.socket_fd.fileno() if self.socket_fd else -1, 
                                                           client_fd))
                        batch_events = []
                        logger.error("Error reading from client (fd: {}): {}".format(client_fd, e))
                        self.handle_client_disconnection(client_fd)
                        break
        except Exception as e:
            logger.error("Error in handle_client_socket_event: {}".format(e))
    
    def handle_client_disconnection(self, client_fd: int):
        """Handle client disconnection.
        
        Args:
            client_fd: The client socket file descriptor
        """
        client_handle = -1
        
        # Get client handle before cleanup for logging
        with self.clients_mutex:
            if client_fd in self.socket_to_handle:
                client_handle = self.socket_to_handle[client_fd]
        
        logger.info("Client disconnecting: fd={}, handle={}".format(client_fd, client_handle))
        
        # Clean up all client data and mappings
        with self.clients_mutex:
            # Remove from connected_clients map
            if client_fd in self.connected_clients:
                del self.connected_clients[client_fd]
            
            # Remove client buffer
            if client_fd in self.client_buffers:
                del self.client_buffers[client_fd]
            
            # Remove socket object
            client_socket = None
            if client_fd in self.client_sockets:
                client_socket = self.client_sockets[client_fd]
                del self.client_sockets[client_fd]
            
            # Remove handle mappings
            if client_fd in self.socket_to_handle:
                handle = self.socket_to_handle[client_fd]
                if handle in self.handle_to_socket:
                    del self.handle_to_socket[handle]
                del self.socket_to_handle[client_fd]
        
        # Close the socket
        if client_socket:
            try:
                client_socket.close()
            except:
                pass
        
        logger.info("Client disconnected: fd={}, handle={}".format(client_fd, client_handle))
        
        # Queue disconnection event
        self.queue_event(SocketEventData(SocketEvent.DISCONNECTED, "", b"", 
                                       self.socket_fd.fileno() if self.socket_fd else -1, 
                                       client_fd))
    
    def send_to_socket(self, sock, data: bytes) -> bool:
        """
        Send data to a specific socket.
        
        Args:
            sock: The socket file descriptor (int) or socket object
            data: The data to send
            
        Returns:
            True if send successful, false otherwise
        """
        try:
            # If sock is an integer (file descriptor), get socket object
            if isinstance(sock, int):
                with self.clients_mutex:
                    if sock in self.client_sockets:
                        sock_obj = self.client_sockets[sock]
                    else:
                        # FD not found, might be main client socket
                        sock_obj = self.socket_fd if self.socket_fd and self.socket_fd.fileno() == sock else None
                        if not sock_obj:
                            return False
            else:
                sock_obj = sock
            
            # Send all data
            total_sent = 0
            while total_sent < len(data):
                sent = sock_obj.send(data[total_sent:])
                if sent <= 0:
                    return False
                total_sent += sent
            return True
        except socket.error as e:
            if e.errno in (errno.EPIPE, errno.ECONNRESET, errno.ECONNREFUSED):
                # Connection lost
                logger.debug("Connection lost for socket: {}".format(e))
                return False
            else:
                logger.error("Send failed: {}".format(e))
                return False
        except Exception as e:
            logger.error("Send failed: {}".format(e))
            return False
    
    def queue_event(self, event_data: SocketEventData):
        """
        Add event to the event queue.
        
        Args:
            event_data: The event data to add
        """
        try:
            self.event_queue.put(event_data, block=False)
        except queue.Full:
            logger.warning("Event queue is full, dropping event")
    
    def connect_to_server(self) -> bool:
        """
        Connect to server (client mode).
        
        Returns:
            True if connection successful, false otherwise
        """
        try:
            # Create socket
            self.socket_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket_fd.settimeout(5)  # 5 second connection timeout
            
            # Connect to server
            self.socket_fd.connect((self.address, self.port))
            
            # Set socket to non-blocking for data transmission
            self.socket_fd.setblocking(False)
            
            logger.info("Connected to server {}:{}".format(self.address, self.port))
            return True
        except Exception as e:
            logger.error("Failed to connect to server: {}".format(e))
            if self.socket_fd:
                self.socket_fd.close()
                self.socket_fd = None
            return False
    
    def start_server(self) -> bool:
        """
        Start server (server mode).
        
        Returns:
            True if server started successfully, false otherwise
        """
        try:
            # Create server socket
            self.socket_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind the socket
            self.socket_fd.bind((self.address, self.port))
            
            # Listen for connections
            self.socket_fd.listen(10)  # Allow up to 10 connections in the queue
            
            # Set server socket to non-blocking
            self.socket_fd.setblocking(False)
            
            logger.info("Server listening on {}:{}...".format(self.address, self.port))
            return True
        except Exception as e:
            logger.error("Failed to start server: {}".format(e))
            if self.socket_fd:
                self.socket_fd.close()
                self.socket_fd = None
            return False
    
    def cleanup(self):
        """Clean up all resources."""
        # Close all client sockets in server mode
        if self.mode == SocketMode.SERVER:
            with self.clients_mutex:
                for client_fd, client_socket in list(self.client_sockets.items()):
                    try:
                        client_socket.close()
                    except:
                        pass
                self.connected_clients.clear()
                self.client_buffers.clear()
                self.client_sockets.clear()
        
        # Close main socket
        if self.socket_fd:
            self.socket_fd.close()
            self.socket_fd = None
        
        # Clear queues
        with self.send_queue_mutex:
            self.send_queue.clear()
        
        # Clear event queue
        try:
            while True:
                self.event_queue.get_nowait()
        except queue.Empty:
            pass