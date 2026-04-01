#!/usr/bin/env python3
"""
ILX Pipeline Server - Full Simulation
======================================
A fully simulated Innospace Pipeline Server built using the ilx_pipeline library's
PipelineSocket in SERVER mode.

Listens on port 7000 and handles ALL pipeline protocol command codes:
  - CONNECT_SERVICE      : service registration (detects duplicates)
  - SEND_TO_INPUT        : data broadcast to all services
  - DATA_UPDATE          : internal broadcast frame type
  - REFRESH_DATA         : re-send all last-known datapoints to requester
  - DELETE_DATAPOINT     : remove a datapoint from cache
  - UPDATE_DATAPOINT     : write to another service's datapoint
  - PUBLISH_ACTION       : register a global action
  - TRIGGER_ACTION       : fire a global action → broadcast
  - PUBLISH_CONFIG       : store + broadcast a config entry
  - PUBLISH_NOTIFICATION : broadcast a structured notification
  - DELETE_ACTION        : clean up on disconnect

Usage:
    python ilx_pipeline_server.py [--host HOST] [--port PORT]

Defaults:
    host = 0.0.0.0
    port = 7000
"""

import argparse
import logging
import struct
import sys
import threading
import time
from collections import defaultdict

# ---------------------------------------------------------------------------
# Add parent directory so ilx_pipeline package is importable when running
# this file directly from flask/ directory.
# ---------------------------------------------------------------------------
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ilx_pipeline.pipeline_socket import (
    PipelineSocket, SocketMode, SocketEvent, SocketEventData
)
from ilx_pipeline.binary_frame import (
    BinaryFrame, BinaryFrameHandler, BinaryFrameHandler as BFH,
    DataTypeCode, CommandCode,
    START_OF_FRAME, API_VERSION, END_OF_FRAME
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ilx_pipeline_server")


# ============================================================================
# PipelineServer
# ============================================================================
class PipelineServer:
    """
    Full-featured ILX/Innospace Pipeline TCP server.

    Responsibilities
    ----------------
    1.  Accept TCP connections from PipelineClient instances.
    2.  Parse binary frames coming from each client.
    3.  Route / broadcast frames to the appropriate recipients.
    4.  Maintain global state:
          - connected_services   : handle → service_name
          - service_handles      : service_name → handle  (reverse)
          - datapoint_cache      : service_name → {dp_name → last_frame_bytes}
          - config_store         : config_name → last CONFIG frame bytes
          - action_store         : action_name → publisher_service_name
    5.  Detect duplicate service names and notify the offending client.
    6.  Notify all clients when a service connects or disconnects.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 7000):
        self.host = host
        self.port = port

        # PipelineSocket in SERVER mode
        self._sock = PipelineSocket(
            SocketMode.SERVER, host, port,
            max_queue_size=500_000,
            send_wait_timeout_ms=200,
        )
        self._sock.set_event_callback(self._on_socket_event)

        # Per-client receive buffers for TCP stream reassembly
        # Keyed by internal PipelineSocket CLIENT HANDLE (not raw OS fd)
        self._recv_buffers: dict = {}          # client_handle → bytearray
        self._recv_lock = threading.Lock()

        # Connected services state
        self._state_lock = threading.RLock()
        self._connected_services: dict = {}    # client_handle → service_name
        self._service_handles: dict  = {}      # service_name → client_handle

        # Datapoint cache  service_name → {dp_name → serialized DATA_UPDATE bytes}
        self._datapoint_cache: dict = defaultdict(dict)

        # Config store     config_name → serialized CONFIG_UPDATE bytes
        self._config_store: dict = {}

        # Action store     action_name → publisher_service_name
        self._action_store: dict = {}

        # fd → handle tracking so we can recover handle on DISCONNECT
        # (PipelineSocket removes handle mapping BEFORE firing DISCONNECTED event)
        self._fd_to_handle_map: dict = {}   # raw OS fd → PipelineSocket handle

        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Start the pipeline server (non-blocking)."""
        logger.info("="*60)
        logger.info(" ILX Pipeline Server starting on %s:%d", self.host, self.port)
        logger.info("="*60)
        self._running = True
        self._sock.start()
        logger.info("[SERVER] Socket layer started – waiting for clients…")

    def stop(self):
        """Gracefully stop the server."""
        logger.info("[SERVER] Stopping…")
        self._running = False
        self._sock.stop()
        logger.info("[SERVER] Stopped.")

    def run_forever(self):
        """Block until KeyboardInterrupt."""
        self.start()
        try:
            while self._running:
                time.sleep(0.5)
                self._print_status()
        except KeyboardInterrupt:
            logger.info("[SERVER] Keyboard interrupt – shutting down.")
        finally:
            self.stop()

    # ------------------------------------------------------------------
    # Status printer (called every 0.5s from run_forever)
    # ------------------------------------------------------------------

    _last_status_time = 0.0

    def _print_status(self):
        now = time.time()
        if now - self._last_status_time < 5.0:   # print every 5 s
            return
        self._last_status_time = now

        with self._state_lock:
            services = list(self._service_handles.keys())
            configs   = list(self._config_store.keys())
            actions   = list(self._action_store.keys())
            dp_counts = {svc: len(dps) for svc, dps in self._datapoint_cache.items()}

        logger.info("─" * 60)
        logger.info("[STATUS] Connected services (%d): %s", len(services), services or "(none)")
        logger.info("[STATUS] Configs cached  (%d): %s", len(configs), configs or "(none)")
        logger.info("[STATUS] Actions known   (%d): %s", len(actions), actions or "(none)")
        if dp_counts:
            for svc, cnt in dp_counts.items():
                logger.info("[STATUS]   Datapoints %-30s : %d", svc, cnt)
        logger.info("─" * 60)

    # ------------------------------------------------------------------
    # Socket event callback (called from PipelineSocket's event_thread)
    # ------------------------------------------------------------------

    def _fd_to_handle(self, client_fd: int) -> int:
        """Convert a raw OS socket fd to PipelineSocket's internal client handle."""
        return self._sock.get_handle_for_socket(client_fd)

    def _on_socket_event(self, event: SocketEventData):
        # event.client_fd is the raw OS file descriptor.
        # PipelineSocket.send_data() uses its own monotonic *handles* (not fds).
        # Convert fd → handle once here so the rest of the server uses handles.
        raw_fd = event.client_fd
        handle = self._fd_to_handle(raw_fd) if raw_fd >= 0 else -1

        if event.event_type == SocketEvent.CONNECTED:
            # On CONNECTED the handle mapping is already registered inside PipelineSocket
            # (handle_server_socket_event runs before queuing the event).
            # Use the handle we just looked up; -1 means the server socket itself connected
            # (the very first CONNECTED event has client_fd == -1 for the listening socket).
            if handle < 0:
                logger.info("[CONNECT ] Server socket started (no client yet)")
                return
            logger.info("[CONNECT ] New client connection – fd=%d handle=%d", raw_fd, handle)
            with self._recv_lock:
                self._recv_buffers[handle] = bytearray()
            # Track fd→handle so we can look it up on disconnect
            with self._state_lock:
                self._fd_to_handle_map[raw_fd] = handle

        elif event.event_type == SocketEvent.DISCONNECTED:
            if handle < 0:
                # PipelineSocket has already removed handle mapping on disconnect;
                # recover the handle from our own fd→handle tracking map.
                with self._state_lock:
                    handle = self._fd_to_handle_map.pop(raw_fd, -1)
            else:
                with self._state_lock:
                    self._fd_to_handle_map.pop(raw_fd, None)
            logger.info("[DISCONN ] TCP disconnection – fd=%d handle=%d", raw_fd, handle)
            self._handle_disconnect(handle)
            with self._recv_lock:
                self._recv_buffers.pop(handle, None)

        elif event.event_type == SocketEvent.DATA_RECEIVED:
            if handle >= 0:
                self._accumulate_and_parse(handle, event.data)

        elif event.event_type == SocketEvent.ERROR:
            logger.error("[ERROR   ] Socket error – fd=%d handle=%d", raw_fd, handle)

    # ------------------------------------------------------------------
    # TCP stream reassembly
    # ------------------------------------------------------------------

    def _accumulate_and_parse(self, handle: int, chunk: bytes):
        with self._recv_lock:
            if handle not in self._recv_buffers:
                self._recv_buffers[handle] = bytearray()
            self._recv_buffers[handle].extend(chunk)
            buf = self._recv_buffers[handle]

        # parse_frame_from_stream mutates buf in-place (removes consumed bytes)
        found, frames = BinaryFrameHandler.parse_frame_from_stream(buf)
        for frame in frames:
            try:
                self._dispatch_frame(handle, frame)
            except Exception as exc:
                logger.error("[FRAME   ] Error dispatching frame cmd=0x%04X from handle=%d: %s",
                             frame.command_code, handle, exc, exc_info=True)

    # ------------------------------------------------------------------
    # Frame dispatcher
    # ------------------------------------------------------------------

    def _dispatch_frame(self, sender_handle: int, frame: BinaryFrame):
        cmd = frame.command_code

        if cmd == CommandCode.CONNECT_SERVICE:
            self._handle_connect_service(sender_handle, frame)

        elif cmd == CommandCode.SEND_TO_INPUT:
            self._handle_send_to_input(sender_handle, frame)

        elif cmd == CommandCode.REFRESH_DATA:
            self._handle_refresh_data(sender_handle, frame)

        elif cmd == CommandCode.DELETE_DATAPOINT:
            self._handle_delete_datapoint(sender_handle, frame)

        elif cmd == CommandCode.UPDATE_DATAPOINT:
            self._handle_update_datapoint(sender_handle, frame)

        elif cmd == CommandCode.PUBLISH_ACTION:
            self._handle_publish_action(sender_handle, frame)

        elif cmd == CommandCode.TRIGGER_ACTION:
            self._handle_trigger_action(sender_handle, frame)

        elif cmd == CommandCode.PUBLISH_CONFIG:
            self._handle_publish_config(sender_handle, frame)

        elif cmd == CommandCode.PUBLISH_NOTIFICATION:
            self._handle_publish_notification(sender_handle, frame)

        else:
            svc = self._service_name(sender_handle)
            logger.warning("[FRAME   ] Unknown command 0x%04X from service='%s' handle=%d",
                           cmd, svc, sender_handle)

    # ------------------------------------------------------------------
    # Handler: CONNECT_SERVICE  (0x0001)
    # ------------------------------------------------------------------

    def _handle_connect_service(self, handle: int, frame: BinaryFrame):
        if not frame.payloads:
            logger.warning("[CONNECT ] CONNECT_SERVICE frame with no payload from handle=%d", handle)
            return

        service_name = frame.payloads[0].data.decode("utf-8", errors="replace")

        with self._state_lock:
            # Duplicate name detection
            if service_name in self._service_handles:
                existing_handle = self._service_handles[service_name]
                logger.warning("[CONNECT ] Duplicate service name '%s' (existing handle=%d, new handle=%d)",
                               service_name, existing_handle, handle)
                self._send_duplicate_name(handle, service_name)
                return

            # Register
            self._connected_services[handle] = service_name
            self._service_handles[service_name] = handle

        logger.info("[CONNECT ] Service registered: '%s'  handle=%d", service_name, handle)

        # Re-send all existing configs to the new service
        with self._state_lock:
            config_frames = list(self._config_store.values())

        for cfg_bytes in config_frames:
            self._sock.send_data(cfg_bytes, handle)

        # Re-broadcast all published actions to the new service
        with self._state_lock:
            action_snapshots = list(self._action_store.items())  # (name, publisher)

        for action_name, publisher_svc in action_snapshots:
            notify = BFH.create_frame(CommandCode.PUBLISH_ACTION)
            BFH.add_string_payload(notify, DataTypeCode.ACTION, action_name)
            BFH.add_string_payload(notify, DataTypeCode.STRING, publisher_svc)
            self._sock.send_data(BFH.serialize_frame(notify), handle)

        # Notify all OTHER clients that a new service joined
        self._broadcast_service_status("ADDED", service_name, exclude_handle=handle)

        # Also notify the new client of all currently connected services
        with self._state_lock:
            current_services = dict(self._connected_services)

        for other_handle, other_name in current_services.items():
            if other_handle != handle:
                notify = BFH.create_frame(CommandCode.SERVICE_STATUS)
                BFH.add_string_payload(notify, DataTypeCode.STRING, "ADDED")
                BFH.add_string_payload(notify, DataTypeCode.STRING, other_name)
                self._sock.send_data(BFH.serialize_frame(notify), handle)

    # ------------------------------------------------------------------
    # Handler: SEND_TO_INPUT  (0x0003)
    # ------------------------------------------------------------------

    def _handle_send_to_input(self, sender_handle: int, frame: BinaryFrame):
        """Client published a datapoint value → cache it, rewrite as DATA_UPDATE, broadcast."""
        if len(frame.payloads) < 3:
            logger.warning("[SEND_IN ] SEND_TO_INPUT with %d payloads from handle=%d (need ≥3)",
                           len(frame.payloads), sender_handle)
            return

        service_name = frame.payloads[0].data.decode("utf-8", errors="replace")
        dp_name      = frame.payloads[1].data.decode("utf-8", errors="replace")

        logger.debug("[SEND_IN ] service='%s' dp='%s'", service_name, dp_name)

        # Build DATA_UPDATE frame for broadcast
        upd = BFH.create_frame(CommandCode.DATA_UPDATE)
        # payloads: [service_name, dp_name, value, timestamp?, sender?]
        # We forward payloads[0..] exactly as received (re-pack)
        for pl in frame.payloads:
            BFH.add_payload(upd, pl.type, pl.data)

        upd_bytes = BFH.serialize_frame(upd)

        # Cache the datapoint (value payload is payloads[2])
        with self._state_lock:
            self._datapoint_cache[service_name][dp_name] = upd_bytes

        # Broadcast to ALL other connected clients
        self._broadcast(upd_bytes, exclude_handle=sender_handle)

    # ------------------------------------------------------------------
    # Handler: REFRESH_DATA  (0x0009)
    # ------------------------------------------------------------------

    def _handle_refresh_data(self, sender_handle: int, frame: BinaryFrame):
        """Client requested re-send of all cached datapoints."""
        svc = self._service_name(sender_handle)
        logger.info("[REFRESH ] REFRESH_DATA request from service='%s' handle=%d", svc, sender_handle)

        with self._state_lock:
            # Flatten all cached datapoint frames
            all_frames = [
                frame_bytes
                for dp_map in self._datapoint_cache.values()
                for frame_bytes in dp_map.values()
            ]
            all_configs = list(self._config_store.values())

        for fb in all_frames:
            self._sock.send_data(fb, sender_handle)

        for cfg in all_configs:
            self._sock.send_data(cfg, sender_handle)

        logger.info("[REFRESH ] Sent %d datapoint frames + %d config frames to handle=%d",
                    len(all_frames), len(all_configs), sender_handle)

    # ------------------------------------------------------------------
    # Handler: DELETE_DATAPOINT  (0x000A)
    # ------------------------------------------------------------------

    def _handle_delete_datapoint(self, sender_handle: int, frame: BinaryFrame):
        if len(frame.payloads) < 2:
            return

        target_svc = frame.payloads[0].data.decode("utf-8", errors="replace")
        dp_name    = frame.payloads[1].data.decode("utf-8", errors="replace")
        svc        = self._service_name(sender_handle)

        logger.info("[DELETE  ] service='%s' requesting delete dp='%s' from service='%s'",
                    svc, dp_name, target_svc)

        removed = False
        with self._state_lock:
            if target_svc in self._datapoint_cache and dp_name in self._datapoint_cache[target_svc]:
                del self._datapoint_cache[target_svc][dp_name]
                removed = True

        result = "SUCCESS" if removed else "FAILURE"
        self._send_response(sender_handle, frame.command_payload_id, result)

    # ------------------------------------------------------------------
    # Handler: UPDATE_DATAPOINT  (0x000B)
    # ------------------------------------------------------------------

    def _handle_update_datapoint(self, sender_handle: int, frame: BinaryFrame):
        """One service wants to write a value into another service's datapoint."""
        # payloads: request_id(2-byte int), target_service, dp_name, value, requester_service
        if len(frame.payloads) < 4:
            logger.warning("[UPDATE  ] UPDATE_DATAPOINT with insufficient payloads from handle=%d", sender_handle)
            return

        request_id_bytes = frame.payloads[0].data
        request_id = struct.unpack(">H", request_id_bytes[:2])[0] if len(request_id_bytes) >= 2 else 0
        target_svc = frame.payloads[1].data.decode("utf-8", errors="replace")
        dp_name    = frame.payloads[2].data.decode("utf-8", errors="replace")
        value_pl   = frame.payloads[3]
        requester  = frame.payloads[4].data.decode("utf-8", errors="replace") if len(frame.payloads) > 4 else self._service_name(sender_handle)

        logger.info("[UPDATE  ] '%s' → update dp='%s' in service='%s' (req_id=%d)",
                    requester, dp_name, target_svc, request_id)

        # Build DATA_UPDATE for the target service
        upd = BFH.create_frame(CommandCode.DATA_UPDATE)
        BFH.add_string_payload(upd, DataTypeCode.STRING, target_svc)
        BFH.add_string_payload(upd, DataTypeCode.STRING, dp_name)
        BFH.add_payload(upd, value_pl.type, value_pl.data)
        BFH.add_string_payload(upd, DataTypeCode.STRING, requester)
        upd_bytes = BFH.serialize_frame(upd)

        # Cache and forward to target
        with self._state_lock:
            self._datapoint_cache[target_svc][dp_name] = upd_bytes
            target_handle = self._service_handles.get(target_svc, -1)

        if target_handle >= 0:
            self._sock.send_data(upd_bytes, target_handle)
            result = "SUCCESS"
        else:
            logger.warning("[UPDATE  ] Target service '%s' not connected.", target_svc)
            result = "FAILURE"

        # Send RESPONSE back to requester
        self._send_response(sender_handle, request_id, result)

    # ------------------------------------------------------------------
    # Handler: PUBLISH_ACTION  (0x000D)
    # ------------------------------------------------------------------

    def _handle_publish_action(self, sender_handle: int, frame: BinaryFrame):
        if not frame.payloads:
            return

        action_name   = frame.payloads[0].data.decode("utf-8", errors="replace")
        publisher_svc = (frame.payloads[1].data.decode("utf-8", errors="replace")
                         if len(frame.payloads) > 1 else self._service_name(sender_handle))

        logger.info("[ACTION  ] PUBLISH_ACTION '%s' by service='%s'", action_name, publisher_svc)

        with self._state_lock:
            self._action_store[action_name] = publisher_svc

        # Broadcast to all clients (including sender)
        notify = BFH.create_frame(CommandCode.PUBLISH_ACTION)
        BFH.add_string_payload(notify, DataTypeCode.ACTION, action_name)
        BFH.add_string_payload(notify, DataTypeCode.STRING, publisher_svc)
        self._broadcast(BFH.serialize_frame(notify))

    # ------------------------------------------------------------------
    # Handler: TRIGGER_ACTION  (0x000E)
    # ------------------------------------------------------------------

    def _handle_trigger_action(self, sender_handle: int, frame: BinaryFrame):
        if not frame.payloads:
            return

        action_name  = frame.payloads[0].data.decode("utf-8", errors="replace")
        sender_svc   = (frame.payloads[1].data.decode("utf-8", errors="replace")
                        if len(frame.payloads) > 1 else self._service_name(sender_handle))

        logger.info("[ACTION  ] TRIGGER_ACTION '%s' by service='%s'", action_name, sender_svc)

        # Forward trigger to all clients
        bcast = BFH.create_frame(CommandCode.TRIGGER_ACTION)
        BFH.add_string_payload(bcast, DataTypeCode.ACTION, action_name)
        BFH.add_string_payload(bcast, DataTypeCode.STRING, sender_svc)
        self._broadcast(BFH.serialize_frame(bcast))

    # ------------------------------------------------------------------
    # Handler: PUBLISH_CONFIG  (0x000F)
    # ------------------------------------------------------------------

    def _handle_publish_config(self, sender_handle: int, frame: BinaryFrame):
        """Store config entry and broadcast CONFIG_UPDATE to all clients."""
        # payloads: name, value, version_bytes(4), sender_service, target_service
        if len(frame.payloads) < 3:
            return

        cfg_name       = frame.payloads[0].data.decode("utf-8", errors="replace")
        cfg_value      = frame.payloads[1].data.decode("utf-8", errors="replace")
        version_bytes  = frame.payloads[2].data
        sender_svc     = (frame.payloads[3].data.decode("utf-8", errors="replace")
                          if len(frame.payloads) > 3 else self._service_name(sender_handle))
        target_svc     = (frame.payloads[4].data.decode("utf-8", errors="replace")
                          if len(frame.payloads) > 4 else "")

        logger.info("[CONFIG  ] PUBLISH_CONFIG name='%s' version=%s sender='%s' target='%s'",
                    cfg_name, version_bytes.hex() if version_bytes else "?",
                    sender_svc, target_svc or "(all)")

        # Build CONFIG_UPDATE frame
        upd = BFH.create_frame(CommandCode.CONFIG_UPDATE)
        BFH.add_string_payload(upd, DataTypeCode.STRING, cfg_name)
        BFH.add_string_payload(upd, DataTypeCode.STRING, cfg_value)
        BFH.add_payload(upd, DataTypeCode.INT, version_bytes)
        BFH.add_string_payload(upd, DataTypeCode.STRING, target_svc)
        upd_bytes = BFH.serialize_frame(upd)

        # Cache config (overwrite if same name)
        with self._state_lock:
            self._config_store[cfg_name] = upd_bytes

        if target_svc:
            # Unicast to specific service
            with self._state_lock:
                target_handle = self._service_handles.get(target_svc, -1)
            if target_handle >= 0:
                self._sock.send_data(upd_bytes, target_handle)
            else:
                logger.warning("[CONFIG  ] Target service '%s' not connected – config cached only.", target_svc)
        else:
            # Broadcast to all (including sender so it gets its own config ack)
            self._broadcast(upd_bytes)

    # ------------------------------------------------------------------
    # Handler: PUBLISH_NOTIFICATION  (0x0011)
    # ------------------------------------------------------------------

    def _handle_publish_notification(self, sender_handle: int, frame: BinaryFrame):
        """Broadcast notification to all connected clients."""
        if len(frame.payloads) < 6:
            logger.warning("[NOTIF   ] PUBLISH_NOTIFICATION with only %d payloads", len(frame.payloads))
            return

        sender_svc = self._service_name(sender_handle)
        notif_type = frame.payloads[0].data[0] if frame.payloads[0].data else 0
        priority   = frame.payloads[1].data[0] if frame.payloads[1].data else 0
        category   = frame.payloads[2].data[0] if frame.payloads[2].data else 0
        subsystem  = frame.payloads[3].data.decode("utf-8", errors="replace")
        entity     = frame.payloads[4].data.decode("utf-8", errors="replace")
        message    = frame.payloads[5].data.decode("utf-8", errors="replace")

        logger.info("[NOTIF   ] type=%d priority=%d category=%d subsystem='%s' entity='%s' msg='%s' from='%s'",
                    notif_type, priority, category, subsystem, entity, message, sender_svc)

        # Re-build for broadcast (identical frame)
        bcast = BFH.create_frame(CommandCode.PUBLISH_NOTIFICATION)
        for pl in frame.payloads:
            BFH.add_payload(bcast, pl.type, pl.data)
        self._broadcast(BFH.serialize_frame(bcast))

    # ------------------------------------------------------------------
    # Disconnect cleanup
    # ------------------------------------------------------------------

    def _handle_disconnect(self, handle: int):
        with self._state_lock:
            service_name = self._connected_services.pop(handle, None)
            if service_name:
                self._service_handles.pop(service_name, None)

                # Remove actions published by this service
                removed_actions = [name for name, pub in self._action_store.items()
                                   if pub == service_name]
                for name in removed_actions:
                    del self._action_store[name]
            else:
                removed_actions = []

        if service_name:
            logger.info("[DISCONN ] Service '%s' unregistered (handle=%d)", service_name, handle)
            # Broadcast DELETE_ACTION for each action it owned
            for action_name in removed_actions:
                da = BFH.create_frame(CommandCode.DELETE_ACTION)
                BFH.add_string_payload(da, DataTypeCode.ACTION, action_name)
                BFH.add_string_payload(da, DataTypeCode.STRING, service_name)
                self._broadcast(BFH.serialize_frame(da))

            # Broadcast SERVICE_REMOVED
            self._broadcast_service_status("REMOVED", service_name)
        else:
            logger.info("[DISCONN ] Unregistered client disconnected (handle=%d)", handle)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _service_name(self, handle: int) -> str:
        with self._state_lock:
            return self._connected_services.get(handle, f"<unknown handle={handle}>")

    def _broadcast(self, data: bytes, exclude_handle: int = -1):
        """Send data to every connected client (by their PipelineSocket handle) except exclude_handle."""
        with self._state_lock:
            handles = list(self._connected_services.keys())

        for h in handles:
            if h != exclude_handle:
                self._sock.send_data(data, h)

    def _broadcast_service_status(self, status: str, service_name: str, exclude_handle: int = -1):
        """Send SERVICE_STATUS frame (ADDED/REMOVED) to all clients."""
        frame = BFH.create_frame(CommandCode.SERVICE_STATUS)
        BFH.add_string_payload(frame, DataTypeCode.STRING, status)
        BFH.add_string_payload(frame, DataTypeCode.STRING, service_name)
        self._broadcast(BFH.serialize_frame(frame), exclude_handle=exclude_handle)

    def _send_response(self, handle: int, request_id: int, result: str):
        """Send a RESPONSE frame back to a specific client."""
        resp = BFH.create_frame(CommandCode.RESPONSE)
        # request_id as 2-byte big-endian
        BFH.add_payload(resp, DataTypeCode.INT, struct.pack(">H", request_id & 0xFFFF))
        BFH.add_string_payload(resp, DataTypeCode.STRING, result)
        self._sock.send_data(BFH.serialize_frame(resp), handle)

    def _send_duplicate_name(self, handle: int, service_name: str):
        """Notify a client that its service name is already taken."""
        frame = BFH.create_frame(CommandCode.DUPLICATE_SERVICE_NAME)
        BFH.add_string_payload(frame, DataTypeCode.STRING, service_name)
        self._sock.send_data(BFH.serialize_frame(frame), handle)
        logger.warning("[CONNECT ] Sent DUPLICATE_SERVICE_NAME to handle=%d for name='%s'", handle, service_name)


# ============================================================================
# CLI entry point
# ============================================================================

def _build_args():
    p = argparse.ArgumentParser(
        description="ILX/Innospace Pipeline Server – full simulation on port 7000",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--host", default="0.0.0.0",
                   help="Bind address (0.0.0.0 = all interfaces)")
    p.add_argument("--port", type=int, default=7000,
                   help="TCP port to listen on")
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                   help="Logging verbosity")
    return p.parse_args()


def main():
    args = _build_args()
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    server = PipelineServer(host=args.host, port=args.port)
    server.run_forever()


if __name__ == "__main__":
    main()
