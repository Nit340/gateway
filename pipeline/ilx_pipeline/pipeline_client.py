"""
Innospace Pipeline Service interface library for connecting data sources and receivers - Python Implementation

This module provides the main PipelineClient class for connecting to the pipeline service,
managing data points, and handling events.
"""

import threading
import time
import struct
import socket
import logging
from datetime import datetime
from enum import IntEnum
from collections import deque
import queue

# For Python 3.5 compatibility, define Any as object
try:
    from typing import Any, Callable, Dict, List
    # If typing is available, use it
except ImportError:
    # If typing is not available, define fallbacks
    class _Any:
        def __getitem__(self, item):
            return object
    Any = object
    Callable = object
    Dict = dict
    List = list

from .pipeline_socket import PipelineSocket, SocketMode, SocketEvent, SocketEventData, SocketEventCallback
from .binary_frame import BinaryFrame, BinaryFrameHandler, DataTypeCode, CommandCode, TypedPayload, get_iso8601_timestamp

# Set up logger for the module
logger = logging.getLogger(__name__)


class DataType(IntEnum):
    """Enum for data types supported by DataPoint."""
    STRING = 0  # UTF-8 encoded string type
    INT = 1     # 32-bit signed integer type
    LONG = 2    # 64-bit signed integer type
    FLOAT = 3   # 32-bit floating point type
    DOUBLE = 4 # 64-bit floating point type
    BOOL = 5    # Boolean type
    ACTION = 6  # Action type (global action identifier)


class EventType(IntEnum):
    """Enum for different event types that can be triggered by the pipeline."""
    UNKNOWN = 0            # Unknown event type
    PIPELINE_CONNECTED = 1 # Pipeline connected event
    PIPELINE_OFFLINE = 2   # Pipeline offline event
    RECEIVE_DONE = 3       # Data receive completed event
    TRANSMIT_DONE = 4      # Data transmit completed event
    UPDATE_DONE = 5        # Datapoint update operation completed (success/failure)
    DELETE_DONE = 6        # Datapoint delete operation completed (success/failure)
    SERVICE_ADDED = 7      # New service connected to pipeline (notified during refresh)
    SERVICE_REMOVED = 8    # Service disconnected from pipeline (notified during refresh)
    ACTION_TRIGGERED = 9   # A global action was triggered by any connected service
    CONFIG_RECEIVED = 10   # A configuration entry was published or updated
    NOTIFICATION_RECEIVED = 11  # A notification was broadcast by any connected service


class EventStatus(IntEnum):
    """Enum for different event status values that can indicate the result of an event."""
    SUCCESS = 0              # Operation completed successfully
    FAILURE = 1              # Operation failed
    TIMEOUT = 2              # Operation timed out
    CONNECTION_LOST = 3      # Connection was lost
    CONNECTION_ESTABLISHED = 4 # Connection was established
    RECONNECTED = 5          # Connection was re-established


class EventData:
    """Structure to hold event data from the pipeline."""
    
    def __init__(self, event_type: EventType = EventType.UNKNOWN, 
                 service_name: str = "", datapoint_name: str = "", 
                 event_status: EventStatus = EventStatus.FAILURE, 
                 data_timestamp_us: int = 0):
        """
        Initialize EventData.
        
        Args:
            event_type: Type of the event
            service_name: Name of the service associated with the event
            datapoint_name: Name of the datapoint associated with the event
            event_status: Status of the event
            data_timestamp_us: Timestamp from datapoint (microseconds since epoch), 0 if not available
        """
        self.event_type = event_type
        self.service_name = service_name
        self.datapoint_name = datapoint_name
        self.event_status = event_status
        self.timestamp = get_iso8601_timestamp()
        self.data_timestamp_us = data_timestamp_us
        self.config = None          # type: Optional[Config]  # Populated for CONFIG_RECEIVED events
        self.notification = None    # type: Optional[NotificationData]  # Populated for NOTIFICATION_RECEIVED events


class Config:
    """
    Configuration entry with name, value, version, and optional target service.
    
    Mirrors Pipeline::Config from the C++ API.
    """
    def __init__(self, name: str = "", value: str = "", version: int = -1, service: str = ""):
        """
        Initialize a Config entry.
        
        Args:
            name: Configuration key name
            value: Configuration value (string-encoded)
            version: Configuration version (-1 = unset)
            service: Target service name (empty = broadcast to all services)
        """
        self.name = name
        self.value = value
        self.version = version
        self.service = service  # Target service name (empty = broadcast to all)


class NotificationType(IntEnum):
    """Notification type describing the urgency class (mirrors Pipeline::Notification::Type)."""
    Alarm      = 0  # Abnormal condition requiring immediate operator action
    Alert      = 1  # Abnormal condition requiring awareness (lower urgency)
    Prompt     = 2  # Operational request (e.g., "Insert Batch ID")
    Event      = 3  # Normal state change (e.g., "Motor Started"). Log-only.
    Diagnostic = 4  # System-level debug info (e.g., "IPC Buffer 80% full")


class NotificationPriority(IntEnum):
    """Notification priority (mirrors Pipeline::Notification::Priority)."""
    Critical = 0  # Immediate threat to life, environment, or expensive equipment
    High     = 1  # Significant process deviation; requires fast response
    Medium   = 2  # Moderate deviation; needs response to avoid high-priority alarm
    Low      = 3  # Minor issue or "Information" that still requires a task
    NoPriority = 4  # Used for "Events" or "Diagnostics" that have no urgency


class NotificationCategory(IntEnum):
    """Notification category describing the origin domain (mirrors Pipeline::Notification::Category)."""
    Process     = 0  # Normal process deviations
    Safety      = 1  # High-criticality safety triggers
    System      = 2  # IPC/Host machine health
    Network     = 3  # Communication/Connectivity
    Maintenance = 4  # Service reminders
    Security    = 5  # Unauthorized access


class NotificationData:
    """
    Data carried within a NOTIFICATION_RECEIVED event.
    
    Mirrors Pipeline::Notification::Data from the C++ API.
    """
    def __init__(self,
                 notif_type: NotificationType = NotificationType.Event,
                 priority: NotificationPriority = NotificationPriority.NoPriority,
                 category: NotificationCategory = NotificationCategory.System,
                 subsystem: str = "",
                 entity: str = "",
                 message: str = ""):
        """
        Initialize NotificationData.
        
        Args:
            notif_type: Notification type (Alarm, Alert, Prompt, Event, Diagnostic)
            priority: Notification priority (Critical, High, Medium, Low, NoPriority)
            category: Notification category (Process, Safety, System, Network, …)
            subsystem: Originating module (e.g., "IO_Driver")
            entity: Specific tag/device (e.g., "Pump_01")
            message: Human-readable summary
        """
        self.type = notif_type
        self.priority = priority
        self.category = category
        self.subsystem = subsystem
        self.entity = entity
        self.message = message


# Define EventCallback as a type alias for function that takes EventData and returns None
EventCallback = Callable[[Any], None]  # Using Any to avoid issues with Callable in Python 3.5


class DataPoint:
    """DataPoint structure to hold datapoint information."""
    
    def __init__(self, value: Any = "", data_type: DataType = DataType.STRING):
        """
        Initialize a DataPoint.
        
        Args:
            value: Initial value for the datapoint
            data_type: Type of the data point
        """
        self.type = data_type
        self.dirty = False
        self.last_update = time.time()
        self.timestamp = datetime.utcnow()
        
        # Initialize value based on type
        if data_type == DataType.STRING:
            self.string_value = str(value)
            self.int_value = 0
            self.long_value = 0
            self.float_value = 0.0
            self.double_value = 0.0
            self.bool_value = False
        elif data_type == DataType.INT:
            self.int_value = int(value)
            self.string_value = ""
            self.long_value = 0
            self.float_value = 0.0
            self.double_value = 0.0
            self.bool_value = False
        elif data_type == DataType.LONG:
            self.long_value = int(value)
            self.string_value = ""
            self.int_value = 0
            self.float_value = 0.0
            self.double_value = 0.0
            self.bool_value = False
        elif data_type == DataType.FLOAT:
            self.float_value = float(value)
            self.string_value = ""
            self.int_value = 0
            self.long_value = 0
            self.double_value = 0.0
            self.bool_value = False
        elif data_type == DataType.DOUBLE:
            self.double_value = float(value)
            self.string_value = ""
            self.int_value = 0
            self.long_value = 0
            self.float_value = 0.0
            self.bool_value = False
        elif data_type == DataType.BOOL:
            self.bool_value = bool(value)
            self.string_value = ""
            self.int_value = 0
            self.long_value = 0
            self.float_value = 0.0
            self.double_value = 0.0
        else:
            # Default to STRING
            self.string_value = str(value)
            self.int_value = 0
            self.long_value = 0
            self.float_value = 0.0
            self.double_value = 0.0
            self.bool_value = False


class PipelineClient:
    """Pipeline client class for connecting to the pipeline service."""
    
    def __init__(self, service_name: str, server_address: str = "127.0.0.1", 
                 server_port: int = 7000, reconnect_interval_ms: int = 1000, 
                 max_queue_size: int = 10):
        """
        Initialize a PipelineClient instance.
        
        Args:
            service_name: The name of the service to connect to
            server_address: The address of the pipeline server
            server_port: The port of the pipeline server
            reconnect_interval_ms: The interval in milliseconds to attempt reconnection (default 1000ms)
            max_queue_size: The maximum number of items in the data queue (default 10)
        """
        self.service_name = service_name
        self.server_address = server_address
        self.server_port = server_port
        self.reconnect_interval_ms = reconnect_interval_ms
        self.max_queue_size = max_queue_size
        
        self.connection_timeout_s = 5  # Connection timeout in seconds (default 5 seconds if not set)
        
        # Whitelist filtering: Map of service names to lists of datapoint names that this client accepts
        # If whitelist is empty (default), all events are processed. If populated, only matching
        # service/datapoint pairs trigger RECEIVE_DONE events. Empty string "" as service key acts as wildcard.
        self.whitelist = {}  # type: Dict[str, List[str]]
        self.whitelist_mutex = threading.Lock()
        
        # Thread lifecycle flags
        self.running = False  # Master flag indicating client is active
        self.sender_thread = None  # Thread for sending dirty datapoints
        self.callback_thread = None  # Thread for processing event callbacks
        
        # Socket manager for network operations - handles low-level I/O and connection management
        self.socket_manager = PipelineSocket(SocketMode.CLIENT, server_address, server_port, max_queue_size)
        self.socket_manager.set_event_callback(self.handle_socket_event)
        
        # Event queue for asynchronous event delivery to user callbacks
        # Events are queued here by trigger_event() and consumed by callback_thread_func()
        self.event_queue = []  # type: List[EventData]
        self.event_queue_mutex = threading.Lock()
        
        # Condition variable for callback thread - shares lock with event_queue_mutex
        # This allows atomic "add event + notify" operations in trigger_event()
        self.callback_cv = threading.Condition(self.event_queue_mutex)
        self.callback_thread_running = False
        
        # User-registered callback function that receives all events
        self.global_callback = None  # type: Optional[EventCallback]
        self.global_callback_mutex = threading.Lock()
        
        # Connection state tracking - set to True when socket connects
        self.connected = False
        self.sender_thread_running = False
        
        # Connection synchronization - used by wait_until_connected()
        self.connection_mutex = threading.Lock()
        self.connection_cv = threading.Condition(self.connection_mutex)
        
        # Response tracking for request/response protocol operations
        # Maps request_id -> response string for synchronous operations (legacy)
        self.response_map = {}  # type: Dict[int, str]
        self.response_mutex = threading.Lock()
        self.response_cv = threading.Condition()
        
        # Monotonically increasing counter for generating unique request IDs
        # Used in UPDATE_DATAPOINT and DELETE_DATAPOINT operations
        self.request_id_counter = 1
        
        # Tracks pending async operations (UPDATE_DATAPOINT, DELETE_DATAPOINT)
        # Maps request_id -> {target_service, datapoint_name, operation_code}
        # Used to correlate RESPONSE frames with original requests for event generation
        self.pending_requests = {}  # type: Dict[int, Dict[str, Any]]
        self.pending_requests_mutex = threading.Lock()
        
        # Datapoints storage - maps datapoint name to DataPoint object
        # Stores all received datapoint values (from DATA_UPDATE frames)
        # Uses RLock (reentrant) to allow nested locking in conversion methods
        self.datapoints = {}  # type: Dict[str, DataPoint]
        self.datapoints_mutex = threading.RLock()
        self.datapoints_cv_mutex = threading.Lock()
        self.datapoints_cv = threading.Condition()
        
        # Queue of datapoint names that have been modified and need transmission
        # Producer: datapoint_set(), Consumer: sender_thread_func()
        self.dirty_datapoint_queue = deque()  # type: deque
        self.dirty_queue_mutex = threading.Lock()
        
        # Config store: maps config name -> Config object
        # Populated when CONFIG_UPDATE frames are received from the server
        self.config_store = {}  # type: Dict[str, Config]
        self.config_store_mutex = threading.Lock()
        self.config_cv = threading.Condition(self.config_store_mutex)

        # Persistent receive buffer for TCP stream reassembly across DATA_RECEIVED events
        # TCP is stream-oriented; frames may span multiple recv() calls.
        self.recv_buffer = bytearray()
        self.recv_buffer_mutex = threading.Lock()
    
    def start(self):
        """Start the client and establish connection to the server."""
        if self.running:
            logger.warning("PipelineClient is already running")
            return
        
        logger.info("Starting PipelineClient for service: {}".format(self.service_name))
        
        # CRITICAL: Set running flag BEFORE starting threads
        # Thread functions check 'while self.running' immediately upon entry.
        # If set after thread.start(), race condition causes threads to exit prematurely.
        self.running = True
        
        # Start the callback thread
        self.callback_thread_running = True
        self.callback_thread = threading.Thread(target=self.callback_thread_func)
        self.callback_thread.daemon = True
        self.callback_thread.start()
        
        # Start the sender thread (handles sending of dirty datapoints)
        self.sender_thread_running = True
        self.sender_thread = threading.Thread(target=self.sender_thread_func)
        self.sender_thread.daemon = True
        self.sender_thread.start()
        
        # Start the socket manager which handles connection asynchronously
        if self.socket_manager:
            self.socket_manager.start()
    
    def stop(self):
        """Stop the client and close connections."""
        if not self.running:
            return
        
        logger.info("Stopping PipelineClient for service: {}".format(self.service_name))
        
        self.running = False
        self.sender_thread_running = False
        
        # Notify the sender thread to wake up and exit
        with self.datapoints_cv:
            self.datapoints_cv.notify()
        
        # Stop the socket manager FIRST so the DISCONNECTED event (→ PIPELINE_OFFLINE)
        # is queued and processed by the pipeline client's callback queue before we shut
        # down the callback thread.  socket_manager.stop() joins the socket threads, so
        # by the time it returns the PIPELINE_OFFLINE event is already in event_queue.
        if self.socket_manager:
            self.socket_manager.stop()
        
        # NOW stop the callback thread (after socket is fully done)
        self.callback_thread_running = False
        
        # Notify the callback thread to wake up and drain remaining events
        with self.callback_cv:
            self.callback_cv.notify()
        
        # Notify any threads waiting for connection
        with self.connection_cv:
            self.connection_cv.notify()
        
        # Join the threads
        if self.callback_thread and self.callback_thread.is_alive():
            self.callback_thread.join()
        
        # Clear the callback after the callback thread has been joined to prevent
        # any further execution of the callback after resources have been cleaned up
        with self.global_callback_mutex:
            self.global_callback = None
        
        if self.sender_thread and self.sender_thread.is_alive():
            self.sender_thread.join()
    
    def callback_thread_func(self):
        """Thread function to handle callback execution - OPTIMIZED."""
        logger.debug("Callback thread started")
        # Only use callback_thread_running to control the outer loop.
        # self.running is set False early in stop() (before the socket is stopped),
        # so we must NOT use it as the outer loop guard — doing so would cause the
        # thread to exit before PIPELINE_OFFLINE (fired by socket shutdown) can be
        # delivered to the user callback.
        while self.callback_thread_running:
            events_batch = []
            
            logger.debug("Callback thread: Waiting for events...")
            # Wait for notification that events are available (callback_cv shares lock with event_queue_mutex)
            with self.callback_cv:
                while not self.event_queue and self.callback_thread_running and self.running:
                    logger.debug("Callback thread: About to wait on condition variable")
                    self.callback_cv.wait()  # Block indefinitely until notified
                    logger.debug("Callback thread: Woke up from wait, queue size: {}".format(len(self.event_queue)))
                
                # Drain remaining events even when stopping (e.g. PIPELINE_OFFLINE fired just before stop)
                if self.event_queue:
                    events_batch = self.event_queue[:]
                    self.event_queue = []
                    logger.debug("Callback thread: Copied {} events from queue".format(len(events_batch)))
                elif not self.callback_thread_running:
                    break
            
            # Process events outside the lock
            if events_batch:
                logger.debug("Callback thread processing {} events".format(len(events_batch)))
                for event_data in events_batch:
                    should_process = True
                    
                    # Whitelist filtering: Only RECEIVE_DONE events are filtered
                    # Other events (CONNECTED, SERVICE_ADDED, etc.) always pass through
                    if event_data.event_type == EventType.RECEIVE_DONE:
                        with self.whitelist_mutex:
                            if self.whitelist:
                                logger.debug("Whitelist filtering: whitelist={}, service={}, datapoint={}".format(
                                    self.whitelist, event_data.service_name, event_data.datapoint_name))
                                should_process = False
                                # Check for service-specific datapoint match
                                if event_data.service_name in self.whitelist:
                                    datapoints = self.whitelist[event_data.service_name]
                                    if event_data.datapoint_name in datapoints:
                                        should_process = True
                                
                                # Check for wildcard service match ("" key accepts from all services)
                                if not should_process and "" in self.whitelist:
                                    datapoints = self.whitelist[""]
                                    if event_data.datapoint_name in datapoints:
                                        should_process = True
                            else:
                                logger.debug("No whitelist configured, processing all events")
                    
                    logger.debug("Event should_process={}, has_callback={}".format(should_process, self.global_callback is not None))
                    if should_process:
                        try:
                            if self.global_callback:
                                logger.debug("Calling global_callback for event type {}".format(event_data.event_type))
                                self.global_callback(event_data)
                        except Exception as e:
                            logger.error("Exception in global event callback: {}".format(e))
            
            # After draining, check if we should exit the outer loop
            if not self.callback_thread_running and not self.event_queue:
                break
                logger.debug("Callback thread processing {} events".format(len(events_batch)))
                for event_data in events_batch:
                    should_process = True
                    
                    # Whitelist filtering: Only RECEIVE_DONE events are filtered
                    # Other events (CONNECTED, SERVICE_ADDED, etc.) always pass through
                    if event_data.event_type == EventType.RECEIVE_DONE:
                        with self.whitelist_mutex:
                            if self.whitelist:
                                logger.debug("Whitelist filtering: whitelist={}, service={}, datapoint={}".format(
                                    self.whitelist, event_data.service_name, event_data.datapoint_name))
                                should_process = False
                                # Check for service-specific datapoint match
                                if event_data.service_name in self.whitelist:
                                    datapoints = self.whitelist[event_data.service_name]
                                    if event_data.datapoint_name in datapoints:
                                        should_process = True
                                
                                # Check for wildcard service match ("" key accepts from all services)
                                if not should_process and "" in self.whitelist:
                                    datapoints = self.whitelist[""]
                                    if event_data.datapoint_name in datapoints:
                                        should_process = True
                            else:
                                logger.debug("No whitelist configured, processing all events")
                    
                    logger.debug("Event should_process={}, has_callback={}".format(should_process, self.global_callback is not None))
                    if should_process:
                        try:
                            if self.global_callback:
                                logger.debug("Calling global_callback for event type {}".format(event_data.event_type))
                                self.global_callback(event_data)
                        except Exception as e:
                            logger.error("Exception in global event callback: {}".format(e))
            
            # After draining, check if we should exit the outer loop
            if not self.callback_thread_running and not self.event_queue:
                break
        
    def process_received_data(self, byte_data: bytearray):
        """
        Process incoming data from the server.
        
        Args:
            byte_data: The persistent receive buffer (modified in-place; consumed bytes removed)
        """
        logger.debug("Processing {} bytes of received data".format(len(byte_data)))
        # Parse frames from the receive buffer; parse_frame_from_stream removes consumed bytes
        # in-place and leaves any incomplete trailing frame for the next call.
        _success, parsed_frames = BinaryFrameHandler.parse_frame_from_stream(byte_data)
        logger.debug("Frame parsing: frame_count={}".format(len(parsed_frames)))
        
        # Process each parsed frame
        for frame in parsed_frames:
            # DATA_UPDATE is the most common frame type
            if frame.command_code == CommandCode.DATA_UPDATE:
                if len(frame.payloads) >= 3:
                    # Get service name, input name, and data from payloads
                    service_name_data = frame.payloads[0].data
                    input_name_data = frame.payloads[1].data
                    data_payload = frame.payloads[2]
                    
                    # Convert to strings
                    input_name = input_name_data.decode('utf-8')
                    service_name = service_name_data.decode('utf-8')
                    
                    # Store the received data in datapoints map so it can be retrieved
                    with self.datapoints_mutex:
                        # Parse and store data based on type
                        # IMPORTANT: Uses native byte order ('=') to match C++ implementation
                        # C++ uses std::memcpy which preserves platform's native endianness
                        # Frame headers use big-endian, but payload data uses native order
                        if data_payload.type == DataTypeCode.STRING:
                            str_value = data_payload.data.decode('utf-8')
                            self.datapoints[input_name] = DataPoint(str_value, DataType.STRING)
                        elif data_payload.type == DataTypeCode.INT:
                            if len(data_payload.data) >= 4:
                                # 32-bit signed integer, native byte order
                                int_value = struct.unpack('=i', data_payload.data[:4])[0]
                                self.datapoints[input_name] = DataPoint(int_value, DataType.INT)
                        elif data_payload.type == DataTypeCode.LONG:
                            if len(data_payload.data) >= 8:
                                # 64-bit signed integer, native byte order
                                long_value = struct.unpack('=q', data_payload.data[:8])[0]
                                self.datapoints[input_name] = DataPoint(long_value, DataType.LONG)
                        elif data_payload.type == DataTypeCode.FLOAT:
                            if len(data_payload.data) >= 4:
                                # 32-bit floating point, native byte order
                                float_value = struct.unpack('=f', data_payload.data[:4])[0]
                                self.datapoints[input_name] = DataPoint(float_value, DataType.FLOAT)
                        elif data_payload.type == DataTypeCode.DOUBLE:
                            if len(data_payload.data) >= 8:
                                # 64-bit floating point, native byte order
                                double_value = struct.unpack('=d', data_payload.data[:8])[0]
                                self.datapoints[input_name] = DataPoint(double_value, DataType.DOUBLE)
                        elif data_payload.type == DataTypeCode.BOOL:
                            if len(data_payload.data) >= 1:
                                # Boolean value, native byte order
                                bool_value = struct.unpack('=?', data_payload.data[:1])[0]
                                self.datapoints[input_name] = DataPoint(bool_value, DataType.BOOL)
                        else:
                            # Default to STRING for unknown types
                            str_value = data_payload.data.decode('utf-8', errors='ignore')
                            self.datapoints[input_name] = DataPoint(str_value, DataType.STRING)
                    
                    # Extract timestamp if available (4th payload in protocol v0x02)
                    data_timestamp_us = 0
                    if len(frame.payloads) >= 4 and len(frame.payloads[3].data) >= 8:
                        data_timestamp_us = struct.unpack('=q', frame.payloads[3].data[:8])[0]
                    
                    logger.debug("Stored datapoint: {} = [data hidden, type: {}] for service: {}".format(
                        input_name, int(data_payload.type), service_name))
                    
                    # Trigger event after updating datapoints map with timestamp
                    logger.debug("About to trigger RECEIVE_DONE event for: service='{}', input='{}', type={}".format(
                        service_name, input_name, int(data_payload.type)))
                    self.trigger_event(EventType.RECEIVE_DONE, service_name, input_name,
                                     EventStatus.SUCCESS, data_timestamp_us)
                    logger.debug("Received DATA_UPDATE: service='{}', input='{}', type={}".format(
                        service_name, input_name, int(data_payload.type)))
                continue
            
            if frame.command_code == CommandCode.RESPONSE:
                # Handle response frames
                if len(frame.payloads) >= 2:
                    # Extract request ID and result from payloads
                    request_id = 0
                    if len(frame.payloads[0].data) >= 2:
                        request_id = struct.unpack('=H', frame.payloads[0].data[:2])[0]
                    result = frame.payloads[1].data.decode('utf-8')
                    
                    logger.debug("Received response for request ID {}: {}".format(request_id, result))
                    
                    # Check if this is a response to UPDATE_DATAPOINT or DELETE_DATAPOINT
                    with self.pending_requests_mutex:
                        if request_id in self.pending_requests:
                            pending_req = self.pending_requests[request_id]
                            
                            # Determine event type based on operation
                            if pending_req['operation_code'] == CommandCode.UPDATE_DATAPOINT.value:
                                event_type = EventType.UPDATE_DONE
                            elif pending_req['operation_code'] == CommandCode.DELETE_DATAPOINT.value:
                                event_type = EventType.DELETE_DONE
                            else:
                                event_type = EventType.UNKNOWN
                            
                            event_status = EventStatus.SUCCESS if result in ["SUCCESS", "OK"] else EventStatus.FAILURE
                            
                            self.trigger_event(event_type, pending_req['target_service'],
                                             pending_req['datapoint_name'], event_status, 0)
                            
                            # Remove from pending requests
                            del self.pending_requests[request_id]
                            continue  # Skip generic response handling
                    
                    # Generic response handling (for backward compatibility)
                    with self.response_mutex:
                        self.response_map[request_id] = result
                        self.response_cv.notify()
            
            elif frame.command_code == CommandCode.SERVICE_STATUS:
                # Handle service status notifications (SERVICE_ADDED / SERVICE_REMOVED)
                if len(frame.payloads) >= 2:
                    status_str = frame.payloads[0].data.decode('utf-8')
                    service_name = frame.payloads[1].data.decode('utf-8')
                    
                    if status_str == "ADDED":
                        self.trigger_event(EventType.SERVICE_ADDED, service_name, "", EventStatus.SUCCESS, 0)
                        logger.info("Service added: {}".format(service_name))
                    elif status_str == "REMOVED":
                        self.trigger_event(EventType.SERVICE_REMOVED, service_name, "", EventStatus.SUCCESS, 0)
                        logger.info("Service removed: {}".format(service_name))
            elif frame.command_code == CommandCode.TRIGGER_ACTION:
                # Handle action trigger broadcast from the server
                if len(frame.payloads) >= 1:
                    action_name = frame.payloads[0].data.decode('utf-8')
                    logger.debug("Action triggered: '{}'".format(action_name))
                    self.trigger_event(EventType.ACTION_TRIGGERED, "", action_name, EventStatus.SUCCESS, 0)
            elif frame.command_code == CommandCode.PUBLISH_ACTION:
                # Informational: the server broadcasts published actions to all clients
                if len(frame.payloads) >= 1:
                    action_name = frame.payloads[0].data.decode('utf-8')
                    logger.debug("Action published: '{}'".format(action_name))
            elif frame.command_code == CommandCode.CONFIG_UPDATE:
                # Handle config update broadcast from the server
                if len(frame.payloads) >= 3:
                    cfg = Config()
                    cfg.name = frame.payloads[0].data.decode('utf-8')
                    cfg.value = frame.payloads[1].data.decode('utf-8')
                    if len(frame.payloads[2].data) >= 4:
                        d = frame.payloads[2].data
                        ver = (d[0] << 24) | (d[1] << 16) | (d[2] << 8) | d[3]
                        # Convert unsigned to signed 32-bit
                        if ver >= 0x80000000:
                            ver -= 0x100000000
                        cfg.version = ver
                    # payload[3] = target service name (empty = was broadcast to all)
                    if len(frame.payloads) >= 4 and frame.payloads[3].data:
                        cfg.service = frame.payloads[3].data.decode('utf-8')
                    logger.debug("Config update received: name='{}', version={}, target='{}'".format(cfg.name, cfg.version, cfg.service))

                    # Store in local cache and notify waiters
                    with self.config_cv:
                        self.config_store[cfg.name] = cfg
                        self.config_cv.notify_all()

                    # Trigger CONFIG_RECEIVED event
                    evt = EventData(EventType.CONFIG_RECEIVED, "", cfg.name, EventStatus.SUCCESS, 0)
                    evt.config = cfg
                    with self.callback_cv:
                        self.event_queue.append(evt)
                        self.callback_cv.notify()
            elif frame.command_code == CommandCode.PUBLISH_NOTIFICATION:
                # Handle notification broadcast from the server
                if len(frame.payloads) >= 6:
                    notif = NotificationData()
                    if frame.payloads[0].data:
                        notif.type = NotificationType(frame.payloads[0].data[0])
                    if frame.payloads[1].data:
                        notif.priority = NotificationPriority(frame.payloads[1].data[0])
                    if frame.payloads[2].data:
                        notif.category = NotificationCategory(frame.payloads[2].data[0])
                    notif.subsystem = frame.payloads[3].data.decode('utf-8')
                    notif.entity = frame.payloads[4].data.decode('utf-8')
                    notif.message = frame.payloads[5].data.decode('utf-8')

                    logger.debug("Notification received: type={}, subsystem='{}', entity='{}'".format(
                        int(notif.type), notif.subsystem, notif.entity))

                    evt = EventData(EventType.NOTIFICATION_RECEIVED, notif.subsystem, notif.entity, EventStatus.SUCCESS, 0)
                    evt.notification = notif
                    with self.callback_cv:
                        self.event_queue.append(evt)
                        self.callback_cv.notify()
            else:
                # Log unknown command codes for debugging
                logger.warning("Received unknown command code: {}".format(frame.command_code))
    
    def sender_thread_func(self):
        """
        Thread function to handle sending of dirty datapoints.
        
        Implements efficient event-driven transmission pattern:
        
        1. Block on datapoints_cv until dirty_datapoint_queue has items
        2. Wake up when datapoint_set() calls notify()
        3. Send all queued dirty datapoints in batch
        4. Return to blocking state
        
        This approach eliminates polling overhead - thread consumes zero CPU
        when no datapoints need transmission.
        
        .. note::
           Uses condition variable for zero-polling blocking. Thread wakes only
           when datapoint_set() signals new dirty data via datapoints_cv.notify().
        """
        while self.sender_thread_running and self.running:
            # Wait for notification that there are dirty datapoints
            # Blocks efficiently using condition variable (no CPU waste)
            with self.datapoints_cv:
                while not self.dirty_datapoint_queue and self.sender_thread_running and self.running:
                    self.datapoints_cv.wait()  # Block indefinitely until notified
            
            # If thread should stop, break out of the loop
            if not self.sender_thread_running or not self.running:
                break
            
            # Send all dirty datapoints in batch
            self.send_dirty_datapoints()
    
    def set_reconnect_interval(self, interval_ms: int):
        """
        Set the reconnection interval.
        
        Args:
            interval_ms: The interval in milliseconds
        """
        self.reconnect_interval_ms = interval_ms
    
    def set_max_queue_size(self, max_size: int):
        """
        Set the maximum queue size.
        
        Args:
            max_size: The maximum queue size
        """
        self.max_queue_size = max_size
    
    def set_event_callback(self, callback: EventCallback):
        """
        Register a callback function to receive all events.
        
        The callback will be invoked asynchronously by callback_thread for each event
        (CONNECTED, RECEIVE_DONE, SERVICE_ADDED, etc.). Callback must be thread-safe
        and should not block for extended periods.
        
        :param callback: Function accepting EventData parameter
        :type callback: Callable[[EventData], None]
        :return: None
        :rtype: None
        
        .. warning::
           Callback is invoked from callback_thread context, not from the caller's thread.
           Long-running callbacks will delay processing of subsequent events.
        
        Example::
        
            def my_callback(event):
                if event.event_type == EventType.RECEIVE_DONE:
                    value = client.get_datapoint_string(event.datapoint_name)
                    print(f"Received: {event.datapoint_name} = {value}")
            
            client.set_event_callback(my_callback)
        """
        with self.global_callback_mutex:
            self.global_callback = callback
    
    def set_connection_timeout(self, timeout_s: int):
        """
        Set the HTTP client connection timeout.
        
        Args:
            timeout_s: The connection timeout in seconds (default 5 seconds if not set)
        """
        self.connection_timeout_s = timeout_s
    
    def wait_until_connected(self, timeout_ms=1000):
        """
        Wait until connection is established with server.
        
        Blocks calling thread until connection completes or timeout expires.
        Uses condition variable for efficient blocking - no polling overhead.
        
        :param timeout_ms: Maximum time to wait in milliseconds (default: 1000ms)
        :type timeout_ms: int
        :return: True if connection established within timeout, False otherwise
        :rtype: bool
        
        .. note::
           This method should be called after start() to ensure background threads
           have initiated connection. Uses connection_cv internally for blocking.
        
        Example::
        
            client.start()
            if client.wait_until_connected(5000):
                print("Connected successfully")
            else:
                print("Connection timeout")
        """
        with self.connection_cv:
            timeout_s = timeout_ms / 1000.0
            end_time = time.time() + timeout_s
            
            while not self.connected:
                remaining = end_time - time.time()
                if remaining <= 0:
                    return False
                # Wait with remaining timeout, will be notified when connected
                self.connection_cv.wait(timeout=remaining)
            
            return True
    
    def datapoint_set(self, datapoint_name: str, value: Any, delta: float = 0.0) -> bool:
        """
        Set a datapoint value for transmission to server.
        
        Stores value internally, marks datapoint as dirty, and notifies sender_thread
        for transmission. Type is inferred automatically from Python value type.
        Supports delta filtering for numeric types to reduce unnecessary updates.
        
        :param datapoint_name: Unique identifier for the datapoint
        :type datapoint_name: str
        :param value: Value to set (bool, int, float, or str)
        :type value: Any
        :param delta: Minimum change threshold for numeric types (default: 0.0)
        :type delta: float
        :return: True if value was stored successfully
        :rtype: bool
        
        .. note::
           Type inference rules:
           
           - bool → DataType.BOOL (checked first as bool is subclass of int)
           - int → DataType.LONG (64-bit)
           - float → DataType.DOUBLE (64-bit)
           - other → DataType.STRING (converted via str())
           
           Delta filtering applies only to FLOAT and DOUBLE types. If absolute
           difference between new and old value is less than delta, update is skipped.
        
        Example::
        
            # Set various datatypes
            client.datapoint_set("temperature", 25.3)  # DOUBLE
            client.datapoint_set("count", 42)  # LONG
            client.datapoint_set("enabled", True)  # BOOL
            client.datapoint_set("status", "running")  # STRING
            
            # With delta filtering (updates only if change >= 0.5)
            client.datapoint_set("sensor", 10.2, delta=0.5)
        """
        # Automatic type inference from Python value type
        # Note: bool check must come before int check (bool is subclass of int in Python)
        if isinstance(value, bool):
            data_type = DataType.BOOL
        elif isinstance(value, int):
            # Use LONG (64-bit) by default to handle larger integers without overflow
            data_type = DataType.LONG
        elif isinstance(value, float):
            # Use DOUBLE (64-bit) for better precision
            data_type = DataType.DOUBLE
        else:
            # Fallback: convert any other type to string representation
            data_type = DataType.STRING
            value = str(value)
        
        with self.datapoints_mutex:
            # Check if the value has actually changed to avoid unnecessary updates
            if datapoint_name in self.datapoints:
                existing_dp = self.datapoints[datapoint_name]
                
                if data_type == DataType.STRING:
                    value_changed = existing_dp.string_value != value
                elif data_type == DataType.INT:
                    value_changed = existing_dp.int_value != int(value)
                elif data_type == DataType.LONG:
                    value_changed = existing_dp.long_value != int(value)
                elif data_type == DataType.FLOAT:
                    value_changed = abs(existing_dp.float_value - float(value)) >= delta
                elif data_type == DataType.DOUBLE:
                    value_changed = abs(existing_dp.double_value - float(value)) >= delta
                elif data_type == DataType.BOOL:
                    value_changed = existing_dp.bool_value != bool(value)
                else:
                    value_changed = True
            else:
                # New datapoint
                value_changed = True
            
            # Store or update the datapoint value
            self.datapoints[datapoint_name] = DataPoint(value, data_type)
            
            # Mark this datapoint as needing to be sent if the value changed
            if value_changed:
                was_clean = not self.datapoints[datapoint_name].dirty  # Check if it was clean before
                self.datapoints[datapoint_name].dirty = True
                self.datapoints[datapoint_name].last_update = time.time()
                self.datapoints[datapoint_name].timestamp = datetime.utcnow()
                
                # Only add to dirty queue if it wasn't already dirty (avoid duplicates)
                if was_clean:
                    with self.dirty_queue_mutex:
                        self.dirty_datapoint_queue.append(datapoint_name)
                
                # Notify the sender thread that there are dirty datapoints to send
                with self.datapoints_cv:
                    self.datapoints_cv.notify()
        
        return True  # Always return true as the operation is successful at storing the value
    
    def refresh(self):
        """Request server to refresh/resend all last data to all connected clients."""
        if self.connected and self.socket_manager:
            # Create and send REFRESH_DATA frame
            frame = BinaryFrameHandler.create_frame(CommandCode.REFRESH_DATA)
            BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, self.service_name)
            
            data = BinaryFrameHandler.serialize_frame(frame)
            self.socket_manager.send_data(data)
            
            logger.info("Sent REFRESH_DATA request for service: {}".format(self.service_name))
        else:
            logger.warning("Cannot send refresh request - not connected")
    
    def delete_datapoint(self, datapoint_name: str, service_name: str = "") -> bool:
        """
        Delete a datapoint from the server.
        
        Args:
            datapoint_name: Name of the datapoint to delete
            service_name: Service name (defaults to current service)
            
        Returns:
            True if request was sent successfully (actual result comes via UPDATE_DONE event)
        """
        if not self.connected or not self.socket_manager:
            logger.warning("Cannot delete datapoint - not connected")
            return False
        
        # Use current service name if not specified
        target_service = service_name if service_name else self.service_name
        
        # Create and send DELETE_DATAPOINT frame
        frame = BinaryFrameHandler.create_frame(CommandCode.DELETE_DATAPOINT)
        BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, target_service)
        BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, datapoint_name)
        
        data = BinaryFrameHandler.serialize_frame(frame)
        result = self.socket_manager.send_data(data)
        
        if result:
            logger.info("Sent DELETE_DATAPOINT request: service='{}', datapoint='{}'".format(target_service, datapoint_name))
            
            # Remove from local datapoints map if it's our service
            if target_service == self.service_name:
                with self.datapoints_mutex:
                    if datapoint_name in self.datapoints:
                        del self.datapoints[datapoint_name]
        
        return result
    
    def publish_action(self, action_name: str) -> bool:
        """
        Publish a supported action to the central service.

        Registers a named action with the pipeline server so that any connected
        service can discover and trigger it. The server stores actions globally
        (not per-service).

        Args:
            action_name: The name of the action to publish

        Returns:
            True if the publish request was sent successfully, False otherwise
        """
        if not self.connected or not self.socket_manager:
            logger.warning("Cannot publish action - not connected")
            return False

        frame = BinaryFrameHandler.create_frame(CommandCode.PUBLISH_ACTION)
        BinaryFrameHandler.add_string_payload(frame, DataTypeCode.ACTION, action_name)
        BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, self.service_name)

        data = BinaryFrameHandler.serialize_frame(frame)
        result = self.socket_manager.send_data(data)

        if result:
            logger.info("Sent PUBLISH_ACTION request: action='{}', service='{}'".format(action_name, self.service_name))

        return result

    def trigger_action(self, action_name: str) -> bool:
        """
        Trigger a global action on the central service.

        Sends a trigger request to the pipeline server for the named action.
        The server broadcasts the trigger to all connected services, which receive
        an ACTION_TRIGGERED event. Actions are global – no service name is required.

        Args:
            action_name: The name of the action to trigger

        Returns:
            True if the trigger request was sent successfully, False otherwise
        """
        if not self.connected or not self.socket_manager:
            logger.warning("Cannot trigger action - not connected")
            return False

        frame = BinaryFrameHandler.create_frame(CommandCode.TRIGGER_ACTION)
        BinaryFrameHandler.add_string_payload(frame, DataTypeCode.ACTION, action_name)
        BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, self.service_name)

        data = BinaryFrameHandler.serialize_frame(frame)
        result = self.socket_manager.send_data(data)

        if result:
            logger.info("Sent TRIGGER_ACTION request: action='{}', service='{}'".format(action_name, self.service_name))

        return result

    def publish_config(self, config) -> bool:
        """
        Publish a configuration entry to the central service.

        Stores a named configuration entry (name, value, version) on the pipeline
        server. If config.service is non-empty the config is delivered only to that
        service; if empty it is broadcast to all connected clients.
        Recipients receive a CONFIG_RECEIVED event with the updated Config data.

        Args:
            config: A Config object with name, value, version, and optional service fields

        Returns:
            True if the publish request was sent successfully, False otherwise
        """
        if not self.connected or not self.socket_manager:
            logger.warning("Cannot publish config - not connected")
            return False

        if not config.name:
            logger.warning("Cannot publish config with empty name")
            return False

        # Encode version as 4-byte big-endian payload (matches C++ implementation)
        ver = int(config.version)
        version_data = bytes([
            (ver >> 24) & 0xFF,
            (ver >> 16) & 0xFF,
            (ver >> 8) & 0xFF,
            ver & 0xFF
        ])

        target_service = getattr(config, 'service', '')

        frame = BinaryFrameHandler.create_frame(CommandCode.PUBLISH_CONFIG)
        BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, config.name)
        BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, config.value)
        BinaryFrameHandler.add_payload(frame, DataTypeCode.INT, version_data)
        BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, self.service_name)
        BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, target_service)

        data = BinaryFrameHandler.serialize_frame(frame)
        result = self.socket_manager.send_data(data)

        if result:
            logger.info("Sent PUBLISH_CONFIG: name='{}', version={}, sender='{}', target='{}'".format(
                config.name, config.version, self.service_name,
                target_service if target_service else "(all)"))

        return result

    def wait_for_config(self, name: str, timeout_ms: int = 5000):
        """
        Wait for a named configuration entry to be available.

        Blocks until a config entry with the given name is received from the server,
        or until the timeout expires. If the config is already cached locally it is
        returned immediately.

        Args:
            name: The configuration key to wait for
            timeout_ms: Maximum time to wait in milliseconds (default 5000 ms)

        Returns:
            The matching Config object, or a Config with version==-1 if not found within timeout
        """
        with self.config_cv:
            # Check if already cached
            if name in self.config_store:
                return self.config_store[name]

            timeout_s = timeout_ms / 1000.0
            end_time = time.time() + timeout_s

            while name not in self.config_store:
                remaining = end_time - time.time()
                if remaining <= 0:
                    break
                self.config_cv.wait(timeout=remaining)

            if name in self.config_store:
                return self.config_store[name]

        logger.warning("wait_for_config: timeout waiting for config '{}'".format(name))
        empty = Config(name=name)
        return empty

    def publish_notification(self,
                             notif_type: NotificationType,
                             priority: NotificationPriority,
                             category: NotificationCategory,
                             subsystem: str,
                             entity: str,
                             message: str):
        """
        Publish a notification to all connected services.

        Broadcasts a structured notification (ISA-18.2 inspired) to all services
        connected to the pipeline. Recipients receive a NOTIFICATION_RECEIVED event
        with the full NotificationData filled in.

        Args:
            notif_type: Notification type (Alarm, Alert, Prompt, Event, Diagnostic)
            priority: Notification priority (Critical, High, Medium, Low, NoPriority)
            category: Notification category (Process, Safety, System, Network, …)
            subsystem: Originating module (e.g., "IO_Driver")
            entity: Specific tag/device (e.g., "Pump_01")
            message: Human-readable summary
        """
        if not self.connected or not self.socket_manager:
            logger.warning("Cannot publish notification - not connected")
            return

        # Encode type, priority, category as single-byte payloads (matches C++ implementation)
        type_data     = bytes([int(notif_type)])
        priority_data = bytes([int(priority)])
        category_data = bytes([int(category)])

        frame = BinaryFrameHandler.create_frame(CommandCode.PUBLISH_NOTIFICATION)
        BinaryFrameHandler.add_payload(frame, DataTypeCode.STRING, type_data)
        BinaryFrameHandler.add_payload(frame, DataTypeCode.STRING, priority_data)
        BinaryFrameHandler.add_payload(frame, DataTypeCode.STRING, category_data)
        BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, subsystem)
        BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, entity)
        BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, message)
        BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, self.service_name)

        data = BinaryFrameHandler.serialize_frame(frame)
        result = self.socket_manager.send_data(data)

        if result:
            logger.info("Sent PUBLISH_NOTIFICATION: type={}, priority={}, category={}, subsystem='{}', entity='{}'".format(
                int(notif_type), int(priority), int(category), subsystem, entity))

    def datapoint_update(self, target_service: str, datapoint_name: str, value: Any) -> int:
        """
        Update a datapoint in another service (with acknowledgment via UPDATE_DONE event).
        
        Args:
            target_service: The service whose datapoint you want to update
            datapoint_name: The name of the datapoint to update
            value: The value to set
            
        Returns:
            Request ID for tracking (0 if failed to send)
        """
        if not self.connected or not self.socket_manager:
            logger.warning("Cannot update datapoint - not connected")
            return 0
        
        # Generate unique request ID (1-65535, wraps around, never 0)
        request_id = self.request_id_counter
        self.request_id_counter = (self.request_id_counter % 65535) + 1
        
        # Track pending request
        with self.pending_requests_mutex:
            self.pending_requests[request_id] = {
                'target_service': target_service,
                'datapoint_name': datapoint_name,
                'operation_code': CommandCode.UPDATE_DATAPOINT.value
            }
        
        # Create and send UPDATE_DATAPOINT frame
        frame = BinaryFrameHandler.create_frame(CommandCode.UPDATE_DATAPOINT)
        # Add request_id as first payload (uint16)
        request_id_data = struct.pack('>H', request_id)
        BinaryFrameHandler.add_payload(frame, DataTypeCode.INT, request_id_data)
        
        BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, target_service)
        BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, datapoint_name)
        
        # Add value based on its type
        if isinstance(value, bool):
            BinaryFrameHandler.add_bool_payload(frame, value)
        elif isinstance(value, int):
            if -(2**31) <= value < 2**31:  # fits in 32-bit int
                BinaryFrameHandler.add_int_payload(frame, value)
            else:  # use long for larger integers
                BinaryFrameHandler.add_long_payload(frame, value)
        elif isinstance(value, float):
            # Check if it's a float or double based on precision needs
            BinaryFrameHandler.add_double_payload(frame, value)
        else:
            BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, str(value))
        
        BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, self.service_name)  # Requesting service
        
        data = BinaryFrameHandler.serialize_frame(frame)
        result = self.socket_manager.send_data(data)
        
        if result:
            logger.info("Sent UPDATE_DATAPOINT request (id={}): target_service='{}', datapoint='{}'".format(request_id, target_service, datapoint_name))
            return request_id
        else:
            # Remove from pending if send failed
            with self.pending_requests_mutex:
                if request_id in self.pending_requests:
                    del self.pending_requests[request_id]
            return 0
    
    def get_datapoint_type(self, datapoint_name: str) -> DataType:
        """
        Get the type of a received datapoint.
        
        Args:
            datapoint_name: The name of the datapoint to get type for
            
        Returns:
            The type of the datapoint, or DataType.STRING if not found
        """
        with self.datapoints_mutex:
            if datapoint_name in self.datapoints:
                return self.datapoints[datapoint_name].type
            return DataType.STRING  # Default return value if not found
    
    def convert_to_integer(self, datapoint: DataPoint) -> int:
        """
        Helper method to convert any data type to integer.
        
        Args:
            datapoint: The DataPoint to convert
            
        Returns:
            The integer value of the datapoint
        """
        if datapoint.type == DataType.INT:
            return datapoint.int_value
        elif datapoint.type == DataType.LONG:
            return int(datapoint.long_value)
        elif datapoint.type == DataType.FLOAT:
            return int(datapoint.float_value)
        elif datapoint.type == DataType.DOUBLE:
            return int(datapoint.double_value)
        elif datapoint.type == DataType.BOOL:
            return 1 if datapoint.bool_value else 0
        elif datapoint.type == DataType.STRING:
            if not datapoint.string_value:
                return 0
            try:
                return int(datapoint.string_value)
            except ValueError:
                # If string can't be converted to int, return the length of the string
                return len(datapoint.string_value)
        return 0
    
    def convert_to_long(self, datapoint: DataPoint) -> int:
        """
        Helper method to convert any data type to long.
        
        Args:
            datapoint: The DataPoint to convert
            
        Returns:
            The long value of the datapoint
        """
        if datapoint.type == DataType.INT:
            return int(datapoint.int_value)
        elif datapoint.type == DataType.LONG:
            return datapoint.long_value
        elif datapoint.type == DataType.FLOAT:
            return int(datapoint.float_value)
        elif datapoint.type == DataType.DOUBLE:
            return int(datapoint.double_value)
        elif datapoint.type == DataType.BOOL:
            return 1 if datapoint.bool_value else 0
        elif datapoint.type == DataType.STRING:
            if not datapoint.string_value:
                return 0
            try:
                return int(datapoint.string_value)
            except ValueError:
                # If string can't be converted to long, return the length of the string
                return len(datapoint.string_value)
        return 0
    
    def convert_to_float(self, datapoint: DataPoint) -> float:
        """
        Helper method to convert any data type to float.
        
        Args:
            datapoint: The DataPoint to convert
            
        Returns:
            The float value of the datapoint
        """
        if datapoint.type == DataType.INT:
            return float(datapoint.int_value)
        elif datapoint.type == DataType.LONG:
            return float(datapoint.long_value)
        elif datapoint.type == DataType.FLOAT:
            return datapoint.float_value
        elif datapoint.type == DataType.DOUBLE:
            return float(datapoint.double_value)
        elif datapoint.type == DataType.BOOL:
            return 1.0 if datapoint.bool_value else 0.0
        elif datapoint.type == DataType.STRING:
            if not datapoint.string_value:
                return 0.0
            try:
                return float(datapoint.string_value)
            except ValueError:
                # If string can't be converted to float, return the length of the string
                return float(len(datapoint.string_value))
        return 0.0
    
    def convert_to_double(self, datapoint: DataPoint) -> float:
        """
        Helper method to convert any data type to double.
        
        Args:
            datapoint: The DataPoint to convert
            
        Returns:
            The double value of the datapoint
        """
        if datapoint.type == DataType.INT:
            return float(datapoint.int_value)
        elif datapoint.type == DataType.LONG:
            return float(datapoint.long_value)
        elif datapoint.type == DataType.FLOAT:
            return float(datapoint.float_value)
        elif datapoint.type == DataType.DOUBLE:
            return datapoint.double_value
        elif datapoint.type == DataType.BOOL:
            return 1.0 if datapoint.bool_value else 0.0
        elif datapoint.type == DataType.STRING:
            if not datapoint.string_value:
                return 0.0
            try:
                return float(datapoint.string_value)
            except ValueError:
                # If string can't be converted to double, return the length of the string
                return float(len(datapoint.string_value))
        return 0.0
    
    def convert_to_boolean(self, datapoint: DataPoint) -> bool:
        """
        Helper method to convert any data type to bool.
        
        Args:
            datapoint: The DataPoint to convert
            
        Returns:
            The boolean value of the datapoint
        """
        if datapoint.type == DataType.INT:
            return datapoint.int_value != 0
        elif datapoint.type == DataType.LONG:
            return datapoint.long_value != 0
        elif datapoint.type == DataType.FLOAT:
            return datapoint.float_value != 0.0
        elif datapoint.type == DataType.DOUBLE:
            return datapoint.double_value != 0.0
        elif datapoint.type == DataType.BOOL:
            return datapoint.bool_value
        elif datapoint.type == DataType.STRING:
            return bool(datapoint.string_value)
        return False
    
    def convert_to_string(self, datapoint: DataPoint) -> str:
        """
        Helper method to convert any data type to string.
        
        Args:
            datapoint: The DataPoint to convert
            
        Returns:
            The string value of the datapoint
        """
        if datapoint.type == DataType.INT:
            return str(datapoint.int_value)
        elif datapoint.type == DataType.LONG:
            return str(datapoint.long_value)
        elif datapoint.type == DataType.FLOAT:
            return str(datapoint.float_value)
        elif datapoint.type == DataType.DOUBLE:
            return str(datapoint.double_value)
        elif datapoint.type == DataType.BOOL:
            return "true" if datapoint.bool_value else "false"
        elif datapoint.type == DataType.STRING:
            return datapoint.string_value
        return ""
    
    def get_datapoint_integer(self, datapoint_name: str) -> int:
        """
        Get the integer value of a received datapoint with automatic type conversion.
        
        Args:
            datapoint_name: The name of the datapoint to get value for
            
        Returns:
            The integer value of the datapoint after conversion, or 0 if invalid type or not found
        """
        with self.datapoints_mutex:
            if datapoint_name in self.datapoints:
                return self.convert_to_integer(self.datapoints[datapoint_name])
            return 0  # Return 0 for not found
    
    def get_datapoint_long(self, datapoint_name: str) -> int:
        """
        Get the long value of a received datapoint with automatic type conversion.
        
        Args:
            datapoint_name: The name of the datapoint to get value for
            
        Returns:
            The long value of the datapoint after conversion, or 0 if invalid type or not found
        """
        with self.datapoints_mutex:
            if datapoint_name in self.datapoints:
                return self.convert_to_long(self.datapoints[datapoint_name])
            return 0  # Return 0 for not found
    
    def get_datapoint_float(self, datapoint_name: str) -> float:
        """
        Get the float value of a received datapoint with automatic type conversion.
        
        Args:
            datapoint_name: The name of the datapoint to get value for
            
        Returns:
            The float value of the datapoint after conversion, or 0.0f if invalid type or not found
        """
        with self.datapoints_mutex:
            if datapoint_name in self.datapoints:
                return self.convert_to_float(self.datapoints[datapoint_name])
            return 0.0  # Return 0.0 for not found
    
    def get_datapoint_double(self, datapoint_name: str) -> float:
        """
        Get the double value of a received datapoint with automatic type conversion.
        
        Args:
            datapoint_name: The name of the datapoint to get value for
            
        Returns:
            The double value of the datapoint after conversion, or 0.0 if invalid type or not found
        """
        with self.datapoints_mutex:
            if datapoint_name in self.datapoints:
                return self.convert_to_double(self.datapoints[datapoint_name])
            return 0.0  # Return 0.0 for not found
    
    def get_datapoint_boolean(self, datapoint_name: str) -> bool:
        """
        Get the boolean value of a received datapoint with automatic type conversion.
        
        Args:
            datapoint_name: The name of the datapoint to get value for
            
        Returns:
            The boolean value of the datapoint after conversion, or false if invalid type or not found
        """
        with self.datapoints_mutex:
            if datapoint_name in self.datapoints:
                return self.convert_to_boolean(self.datapoints[datapoint_name])
            return False  # Return false for not found
    
    def get_datapoint_string(self, datapoint_name: str) -> str:
        """
        Get the string value of a received datapoint with automatic type conversion.
        
        Args:
            datapoint_name: The name of the datapoint to get value for
            
        Returns:
            The string value of the datapoint after conversion, or empty string if not found
        """
        with self.datapoints_mutex:
            if datapoint_name in self.datapoints:
                return self.convert_to_string(self.datapoints[datapoint_name])
            return ""  # Return empty string if not found
    
    @staticmethod
    def event_get_type_str(event_type: EventType) -> str:
        """
        Convert EventType enum to string for logging and debugging.
        
        Args:
            event_type: The event type to convert
            
        Returns:
            String representation of the event type
        """
        type_map = {
            EventType.PIPELINE_CONNECTED: "PIPELINE_CONNECTED",
            EventType.PIPELINE_OFFLINE: "PIPELINE_OFFLINE",
            EventType.RECEIVE_DONE: "RECEIVE_DONE",
            EventType.TRANSMIT_DONE: "TRANSMIT_DONE",
            EventType.UPDATE_DONE: "UPDATE_DONE",
            EventType.DELETE_DONE: "DELETE_DONE",
            EventType.SERVICE_ADDED: "SERVICE_ADDED",
            EventType.SERVICE_REMOVED: "SERVICE_REMOVED",
            EventType.ACTION_TRIGGERED: "ACTION_TRIGGERED",
            EventType.CONFIG_RECEIVED: "CONFIG_RECEIVED",
            EventType.NOTIFICATION_RECEIVED: "NOTIFICATION_RECEIVED",
            EventType.UNKNOWN: "UNKNOWN"
        }
        return type_map.get(event_type, "UNKNOWN")
    
    @staticmethod
    def event_get_status_str(event_status: EventStatus) -> str:
        """
        Convert EventStatus enum to string for logging and debugging.
        
        Args:
            event_status: The event status to convert
            
        Returns:
            String representation of the event status
        """
        status_map = {
            EventStatus.SUCCESS: "SUCCESS",
            EventStatus.FAILURE: "FAILURE",
            EventStatus.TIMEOUT: "TIMEOUT",
            EventStatus.CONNECTION_LOST: "CONNECTION_LOST",
            EventStatus.CONNECTION_ESTABLISHED: "CONNECTION_ESTABLISHED",
            EventStatus.RECONNECTED: "RECONNECTED"
        }
        return status_map.get(event_status, "UNKNOWN_EVENT_STATUS")
    
    def set_whitelist(self, whitelist: Dict[str, List[str]]):
        """
        Set the whitelist of service/datapoint pairs that this client will accept.
        
        Args:
            whitelist: Map of service names to lists of datapoint names
                      If service name is empty, it matches all services
                      If whitelist is empty, all datapoints are accepted
        """
        with self.whitelist_mutex:
            # Copy the whitelist, filtering out blank datapoint names
            self.whitelist = {}
            for service, datapoints in whitelist.items():
                # Filter out blank datapoint names in each service's list
                filtered_datapoints = [dp for dp in datapoints if dp]
                self.whitelist[service] = filtered_datapoints
    
    def get_whitelist(self) -> Dict[str, List[str]]:
        """
        Get the current whitelist of service/datapoint pairs.
        
        Returns:
            Map of service names to lists of datapoint names
        """
        with self.whitelist_mutex:
            return self.whitelist.copy()
    
    def send_dirty_datapoints(self):
        """Send all datapoints that have been marked as dirty (changed)."""
        # Only send if we're connected
        if self.connected and self.socket_manager:
            # Process ALL dirty datapoints from queue
            dirty_datapoints = []
            
            # Collect all datapoint names from dirty queue
            dirty_names = []
            with self.dirty_queue_mutex:
                while self.dirty_datapoint_queue:
                    dirty_names.append(self.dirty_datapoint_queue.popleft())
            
            # Fetch actual datapoint data
            if dirty_names:
                with self.datapoints_mutex:
                    for name in dirty_names:
                        if name in self.datapoints and self.datapoints[name].dirty:
                            dirty_datapoints.append((name, self.datapoints[name]))
            
            # Send each dirty datapoint without holding the lock
            for datapoint_name, datapoint in dirty_datapoints:
                # Create frame directly instead of using the queue
                frame = BinaryFrameHandler.create_frame(CommandCode.SEND_TO_INPUT)
                BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, self.service_name)
                BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, datapoint_name)
                
                # Send raw binary data based on type
                if datapoint.type == DataType.INT:
                    BinaryFrameHandler.add_int_payload(frame, datapoint.int_value)
                elif datapoint.type == DataType.LONG:
                    BinaryFrameHandler.add_long_payload(frame, datapoint.long_value)
                elif datapoint.type == DataType.FLOAT:
                    BinaryFrameHandler.add_float_payload(frame, datapoint.float_value)
                elif datapoint.type == DataType.DOUBLE:
                    BinaryFrameHandler.add_double_payload(frame, datapoint.double_value)
                elif datapoint.type == DataType.BOOL:
                    BinaryFrameHandler.add_bool_payload(frame, datapoint.bool_value)
                elif datapoint.type == DataType.STRING:
                    BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, datapoint.string_value)
                else:
                    # Default to string
                    BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, str(datapoint.string_value))
                
                # Add timestamp as 4th payload (microseconds since epoch)
                timestamp_duration = (datapoint.timestamp - datetime(1970, 1, 1))
                timestamp_us = int(timestamp_duration.total_seconds() * 1000000)
                BinaryFrameHandler.add_timestamp_payload(frame, timestamp_us)
                
                # Add sender service name as 5th payload (NEW - breaks old protocol)
                BinaryFrameHandler.add_string_payload(frame, DataTypeCode.STRING, self.service_name)
                
                # Send using the socket manager (asynchronous for better throughput)
                data = BinaryFrameHandler.serialize_frame(frame)
                result = self.socket_manager.send_data(data)
                if result:
                    # Mark as clean after successful send - need to lock again for this
                    with self.datapoints_mutex:
                        if datapoint_name in self.datapoints:
                            self.datapoints[datapoint_name].dirty = False  # Mark as clean
                    
                    # Trigger TRANSMIT_DONE event for successful transmission
                    self.trigger_event(EventType.TRANSMIT_DONE, self.service_name, datapoint_name, EventStatus.SUCCESS)
                else:
                    # Send failed (queue full), but keep datapoint dirty so it will be retried
                    # Re-add to dirty queue for retry
                    with self.dirty_queue_mutex:
                        self.dirty_datapoint_queue.append(datapoint_name)
    
    def mark_all_datapoints_dirty(self):
        """Mark all datapoints as dirty so they will be sent on next connection."""
        with self.datapoints_mutex:
            with self.dirty_queue_mutex:
                for datapoint_name in self.datapoints:
                    datapoint = self.datapoints[datapoint_name]
                    # Only mark as dirty, DO NOT modify timestamp or data
                    # This preserves original data for retransmission on reconnect
                    if not datapoint.dirty:
                        datapoint.dirty = True
                        self.dirty_datapoint_queue.append(datapoint_name)
                        logger.debug("Marked datapoint for retransmission on reconnect: {} (type: {})".format(
                            datapoint_name, int(datapoint.type)))
        
        # Notify the sender thread that there are dirty datapoints to send
        with self.datapoints_cv:
            self.datapoints_cv.notify()
    
    def trigger_event(self, event_type, service_name,
                     datapoint_name="", event_status=EventStatus.SUCCESS,
                     data_timestamp_us=0):
        """
        Queue an event for asynchronous delivery to user callback.
        
        Creates EventData and adds to event_queue. Notifies callback_thread via
        callback_cv to wake and process event. This decouples event generation
        from callback execution, allowing protocol handlers to continue without
        blocking on user code.
        
        :param event_type: Type of event (CONNECTED, RECEIVE_DONE, etc.)
        :type event_type: EventType
        :param service_name: Service associated with event
        :type service_name: str
        :param datapoint_name: Datapoint associated with event (optional)
        :type datapoint_name: str
        :param event_status: Status code (SUCCESS, FAILED, etc.)
        :type event_status: EventStatus
        :param data_timestamp_us: Timestamp from datapoint data in microseconds (default 0)
        :type data_timestamp_us: int
        :return: None
        :rtype: None
        
        .. note::
           Uses callback_cv which shares lock with event_queue_mutex, enabling
           atomic \"append + notify\" operation. Callback thread wakes and processes
           event asynchronously in separate thread context.
        """
        # callback_cv shares the same lock as event_queue_mutex, so we can do both operations atomically
        with self.callback_cv:
            self.event_queue.append(EventData(event_type, service_name, datapoint_name, event_status, data_timestamp_us))
            logger.debug("trigger_event: Added event type {} to queue (size now: {}), calling notify()".format(event_type, len(self.event_queue)))
            self.callback_cv.notify()
            logger.debug("trigger_event: notify() called")
    
    def handle_socket_event(self, event_data: SocketEventData):
        """
        Private method to handle socket events from PipelineSocket.
        
        Args:
            event_data: The socket event data
        """
        if event_data.event_type == SocketEvent.CONNECTED:
            self.connected = True
            with self.connection_cv:
                self.connection_cv.notify_all() # Notify any threads waiting for connection
            
            # Send registration frame to server after connecting
            if self.socket_manager:
                reg_frame = BinaryFrameHandler.create_frame(CommandCode.CONNECT_SERVICE)
                BinaryFrameHandler.add_string_payload(reg_frame, DataTypeCode.STRING, self.service_name)
                reg_data = BinaryFrameHandler.serialize_frame(reg_frame)
                self.socket_manager.send_data(reg_data)
                logger.debug("Sent CONNECT_SERVICE registration frame for service: {}".format(self.service_name))
                
                # Automatically request data refresh to get all existing services and datapoints
                refresh_frame = BinaryFrameHandler.create_frame(CommandCode.REFRESH_DATA)
                BinaryFrameHandler.add_string_payload(refresh_frame, DataTypeCode.STRING, self.service_name)
                refresh_data = BinaryFrameHandler.serialize_frame(refresh_frame)
                self.socket_manager.send_data(refresh_data)
                logger.debug("Sent automatic REFRESH_DATA request after connection")
            
            self.trigger_event(EventType.PIPELINE_CONNECTED, self.service_name, "", EventStatus.CONNECTION_ESTABLISHED)
        
        elif event_data.event_type == SocketEvent.DISCONNECTED:
            self.connected = False
            # Clear receive buffer on disconnect so partial frames don't bleed into next connection
            with self.recv_buffer_mutex:
                self.recv_buffer = bytearray()
            self.mark_all_datapoints_dirty()  # Mark all datapoints dirty for next reconnection
            self.trigger_event(EventType.PIPELINE_OFFLINE, self.service_name, "", EventStatus.CONNECTION_LOST)
        
        elif event_data.event_type == SocketEvent.DATA_RECEIVED:
            # Accumulate into persistent buffer for TCP stream reassembly across recv() calls
            logger.debug("Received {} bytes of data from socket".format(len(event_data.data)))
            with self.recv_buffer_mutex:
                self.recv_buffer.extend(event_data.data)
                self.process_received_data(self.recv_buffer)
        
        elif event_data.event_type == SocketEvent.SEND_COMPLETE:
            # Data was successfully sent
            # This could be used to trigger transmission events if needed
            logger.debug("Send complete event received")
        
        elif event_data.event_type == SocketEvent.ERROR:
            # Handle error events
            logger.debug("Socket error event received")
            self.connected = False
            self.mark_all_datapoints_dirty() # Mark all datapoints dirty for next reconnection
            self.trigger_event(EventType.PIPELINE_OFFLINE, self.service_name, "", EventStatus.CONNECTION_LOST)