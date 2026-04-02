# -*- coding: utf-8 -*-
"""
ILX Pipeline Simulator Server
==============================
Implements the full ILX binary protocol pipeline server with:
  - All standard services running:
      modbus_service, load_cell_service, iot-gateway,
      ilx_craneiq_core, network_status
  - Receives and displays datapoints sent by the backend
  - Receives and displays configs (as pretty JSON) sent by the backend
  - Real-time web dashboard (SSE) at http://localhost:8765
  - Sends SERVICE_ADDED events to backend when it connects
  - Responds to CONNECT_SERVICE, SEND_TO_INPUT/SERVICE, UPDATE_DATAPOINT,
    PUBLISH_CONFIG, REFRESH_DATA

Usage:
    python server.py [--host 127.0.0.1] [--port 7000] [--web-port 8765]
"""

import sys
import io
import argparse
import json
import socket
import struct
import threading
import time
import logging
import traceback
from collections import OrderedDict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# Force UTF-8 encoding for stdout on Windows
if sys.stdout.encoding != 'UTF-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except Exception:
        pass

# ─────────────── Logging ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ILX-SIM")

# ─────────────── Protocol constants (mirrors binary_frame.py) ────────────────
START_OF_FRAME = 0xAA
API_VERSION    = 0x02
END_OF_FRAME   = 0x55

class Cmd:
    CONNECT_SERVICE        = 0x0001
    SEND_TO_SERVICE        = 0x0002
    SEND_TO_INPUT          = 0x0003
    GET_INPUT_DATA         = 0x0004
    DATA_UPDATE            = 0x0007
    RESPONSE               = 0x0008
    REFRESH_DATA           = 0x0009
    DELETE_DATAPOINT       = 0x000A
    UPDATE_DATAPOINT       = 0x000B
    SERVICE_STATUS         = 0x000C
    PUBLISH_ACTION         = 0x000D
    TRIGGER_ACTION         = 0x000E
    PUBLISH_CONFIG         = 0x000F
    CONFIG_UPDATE          = 0x0010
    PUBLISH_NOTIFICATION   = 0x0011
    DUPLICATE_SERVICE_NAME = 0x0012
    DELETE_ACTION          = 0x0013

class DType:
    STRING = 0x01
    INT    = 0x02
    LONG   = 0x03
    FLOAT  = 0x04
    DOUBLE = 0x05
    BOOL   = 0x06
    ACTION = 0x07

DTYPE_NAMES = {
    DType.STRING: "string",
    DType.INT:    "int32",
    DType.LONG:   "int64",
    DType.FLOAT:  "float32",
    DType.DOUBLE: "float64",
    DType.BOOL:   "bool",
    DType.ACTION: "action",
}

CMD_NAMES = {
    Cmd.CONNECT_SERVICE:      "CONNECT_SERVICE",
    Cmd.SEND_TO_SERVICE:      "SEND_TO_SERVICE",
    Cmd.SEND_TO_INPUT:        "SEND_TO_INPUT",
    Cmd.GET_INPUT_DATA:       "GET_INPUT_DATA",
    Cmd.DATA_UPDATE:          "DATA_UPDATE",
    Cmd.RESPONSE:             "RESPONSE",
    Cmd.REFRESH_DATA:         "REFRESH_DATA",
    Cmd.DELETE_DATAPOINT:     "DELETE_DATAPOINT",
    Cmd.UPDATE_DATAPOINT:     "UPDATE_DATAPOINT",
    Cmd.SERVICE_STATUS:       "SERVICE_STATUS",
    Cmd.PUBLISH_ACTION:       "PUBLISH_ACTION",
    Cmd.TRIGGER_ACTION:       "TRIGGER_ACTION",
    Cmd.PUBLISH_CONFIG:       "PUBLISH_CONFIG",
    Cmd.CONFIG_UPDATE:        "CONFIG_UPDATE",
    Cmd.PUBLISH_NOTIFICATION: "PUBLISH_NOTIFICATION",
}

# ─────────────── CRC-16-CCITT ────────────────────────────────────────────────
_CRC16_TABLE = []

def _init_crc():
    for i in range(256):
        crc = i << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
        _CRC16_TABLE.append(crc & 0xFFFF)

_init_crc()

def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc = ((crc << 8) ^ _CRC16_TABLE[(crc >> 8) ^ b]) & 0xFFFF
    return crc

# ─────────────── Frame helpers ───────────────────────────────────────────────

def _pack_payload(dtype: int, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + bytes([dtype]) + data

def build_frame(cmd: int, payloads: list, cmd_id: int = 0) -> bytes:
    """Build a complete binary frame from (dtype, data-bytes) payload tuples."""
    payload_bytes = b"".join(_pack_payload(dt, d) for dt, d in payloads)
    # frame_len = cmd(2) + id(2) + count(2) + payloads + crc(2)
    frame_len = 6 + len(payload_bytes) + 2
    body = (
        struct.pack(">H", cmd)
        + struct.pack(">H", cmd_id)
        + struct.pack(">H", len(payloads))
        + payload_bytes
    )
    checksum = crc16(body)
    raw = (
        bytes([START_OF_FRAME, API_VERSION])
        + struct.pack(">I", frame_len)
        + body
        + struct.pack(">H", checksum)
        + bytes([END_OF_FRAME])
    )
    return raw

def s(text: str) -> bytes:
    return text.encode("utf-8")

def parse_frames_from_buffer(buf: bytearray):
    """Parse all complete frames from buffer; removes consumed bytes in-place."""
    frames = []
    while len(buf) >= 12:
        # find start byte
        start = -1
        for i in range(len(buf)):
            if buf[i] == START_OF_FRAME:
                start = i
                break
        if start < 0:
            del buf[:]
            break
        if start > 0:
            del buf[:start]
        if len(buf) < 12:
            break

        if buf[1] != API_VERSION:
            del buf[:1]
            continue

        frame_len = struct.unpack(">I", bytes(buf[2:6]))[0]
        total = 2 + 4 + frame_len + 1  # SOF+VER + frame_len_field + payload + EOF
        if len(buf) < total:
            break

        frame_data = bytes(buf[:total])
        # verify crc
        body_start = 6
        body_end   = total - 3  # exclude CRC (2) and EOF (1)
        crc_in     = struct.unpack(">H", frame_data[total - 3: total - 1])[0]
        calc_crc   = crc16(frame_data[body_start:body_end])
        if calc_crc != crc_in:
            del buf[:1]
            continue
        if frame_data[-1] != END_OF_FRAME:
            del buf[:1]
            continue

        # parse
        pos = 6
        cmd  = struct.unpack(">H", frame_data[pos:pos + 2])[0]; pos += 2
        cid  = struct.unpack(">H", frame_data[pos:pos + 2])[0]; pos += 2
        cnt  = struct.unpack(">H", frame_data[pos:pos + 2])[0]; pos += 2

        payloads = []
        ok = True
        for _ in range(cnt):
            if pos + 5 > total - 3:
                ok = False; break
            plen = struct.unpack(">I", frame_data[pos:pos + 4])[0]; pos += 4
            dtype = frame_data[pos]; pos += 1
            if pos + plen > total - 3:
                ok = False; break
            payloads.append((dtype, frame_data[pos:pos + plen]))
            pos += plen

        if ok:
            frames.append({"cmd": cmd, "id": cid, "payloads": payloads})

        del buf[:total]

    return frames

def decode_payload(dtype: int, data: bytes):
    """Decode a payload value based on type."""
    try:
        if dtype == DType.STRING or dtype == DType.ACTION:
            return data.decode("utf-8")
        elif dtype == DType.INT:
            return struct.unpack("=i", data[:4])[0] if len(data) >= 4 else 0
        elif dtype == DType.LONG:
            return struct.unpack("=q", data[:8])[0] if len(data) >= 8 else 0
        elif dtype == DType.FLOAT:
            return struct.unpack("=f", data[:4])[0] if len(data) >= 4 else 0.0
        elif dtype == DType.DOUBLE:
            return struct.unpack("=d", data[:8])[0] if len(data) >= 8 else 0.0
        elif dtype == DType.BOOL:
            return bool(struct.unpack("=?", data[:1])[0]) if len(data) >= 1 else False
    except:
        pass
    return data.hex()

# ─────────────── Simulator State ─────────────────────────────────────────────

# Services this simulator claims to be running (backend looks for these)
SIMULATED_SERVICES = [
    "modbus_service",
    "load_cell_service",
    "iot-gateway",
    "ilx_craneiq_core",
    "network_status",
]

class SimState:
    def __init__(self):
        self.lock = threading.Lock()
        # datapoints: {name: {"value": ..., "type": str, "from": str, "ts": str, "count": int}}
        self.datapoints = OrderedDict()
        # configs: {name: {"value_raw": str, "value_parsed": ..., "version": int, "sender": str, "target": str, "ts": str}}
        self.configs = OrderedDict()
        # events log (most recent first, max 200)
        self.events = []
        # connected clients: {fd: {"addr": ..., "service": "", "connected_at": ...}}
        self.clients = {}
        # SSE subscribers
        self.sse_clients = []
        self.sse_lock = threading.Lock()
        self.started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def add_event(self, kind: str, msg: str, detail: str = ""):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        entry = {"ts": ts, "kind": kind, "msg": msg, "detail": detail}
        with self.lock:
            self.events.insert(0, entry)
            if len(self.events) > 300:
                self.events = self.events[:300]
        self._push_sse("event", json.dumps(entry))

    def update_datapoint(self, name: str, value, dtype: str, from_svc: str):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with self.lock:
            existing = self.datapoints.get(name, {})
            count = existing.get("count", 0) + 1
            self.datapoints[name] = {
                "value": value,
                "type": dtype,
                "from": from_svc,
                "ts": ts,
                "count": count,
            }
            dp_copy = dict(self.datapoints[name])
            dp_copy["name"] = name
        self._push_sse("datapoint", json.dumps({**dp_copy, "name": name}))

    def update_config(self, name: str, value_raw: str, version: int,
                      sender: str, target: str):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        try:
            value_parsed = json.loads(value_raw)
        except Exception:
            value_parsed = value_raw
        with self.lock:
            self.configs[name] = {
                "value_raw": value_raw,
                "value_parsed": value_parsed,
                "version": version,
                "sender": sender,
                "target": target if target else "(broadcast)",
                "ts": ts,
            }
            cfg_copy = dict(self.configs[name])
            cfg_copy["name"] = name
        self._push_sse("config", json.dumps({**cfg_copy, "name": name,
                                             "value_parsed": value_parsed}))

    def register_client(self, fd: int, addr: str):
        with self.lock:
            self.clients[fd] = {"addr": addr, "service": "(connecting)",
                                "connected_at": datetime.now().strftime("%H:%M:%S")}
        self._push_sse("clients", self._clients_json())

    def set_client_service(self, fd: int, svc: str):
        with self.lock:
            if fd in self.clients:
                self.clients[fd]["service"] = svc
        self._push_sse("clients", self._clients_json())

    def remove_client(self, fd: int):
        with self.lock:
            self.clients.pop(fd, None)
        self._push_sse("clients", self._clients_json())

    def _clients_json(self):
        with self.lock:
            return json.dumps(list(self.clients.values()))

    def subscribe_sse(self, q):
        with self.sse_lock:
            self.sse_clients.append(q)

    def unsubscribe_sse(self, q):
        with self.sse_lock:
            try:
                self.sse_clients.remove(q)
            except ValueError:
                pass

    def _push_sse(self, event_type: str, data: str):
        msg = "event: {}\ndata: {}\n\n".format(event_type, data).encode()
        dead = []
        with self.sse_lock:
            for q in self.sse_clients:
                try:
                    q.put_nowait(msg)
                except Exception:
                    dead.append(q)
            for q in dead:
                try:
                    self.sse_clients.remove(q)
                except ValueError:
                    pass

    def snapshot(self):
        """Full state snapshot for initial SSE payload."""
        with self.lock:
            return {
                "datapoints": dict(self.datapoints),
                "configs": {
                    k: {**v, "value_parsed": v["value_parsed"]}
                    for k, v in self.configs.items()
                },
                "events": list(self.events[:50]),
                "clients": list(self.clients.values()),
                "started_at": self.started_at,
            }

STATE = SimState()

# ─────────────── Client handler (one per TCP connection) ─────────────────────

class ClientHandler(threading.Thread):
    def __init__(self, conn: socket.socket, addr, server_ref):
        super().__init__(daemon=True)
        self.conn     = conn
        self.addr     = addr
        self.server   = server_ref
        self.fd       = conn.fileno()
        self.service  = ""
        self.buf      = bytearray()

    def run(self):
        STATE.register_client(self.fd, "{}:{}".format(*self.addr))
        STATE.add_event("CONNECT", "Client connected", "{}:{}".format(*self.addr))
        logger.info("[CLIENT] Connected: {}:{}".format(*self.addr))

        # As soon as a client connects, announce all simulated services to it
        threading.Thread(target=self._announce_services_delayed, daemon=True).start()

        try:
            while True:
                try:
                    chunk = self.conn.recv(65536)
                except Exception:
                    break
                if not chunk:
                    break
                self.buf.extend(chunk)
                frames = parse_frames_from_buffer(self.buf)
                for frame in frames:
                    self._handle_frame(frame)
        except Exception as e:
            logger.error("[CLIENT] Exception: {}".format(e))
        finally:
            self._cleanup()

    def _announce_services_delayed(self):
        """Small delay so the client finishes its CONNECT_SERVICE handshake first."""
        time.sleep(0.3)
        for svc in SIMULATED_SERVICES:
            self._send_service_status("ADDED", svc)
            STATE.add_event("SVC_ADDED", "Announced service",
                            svc + " → " + (self.service or "client"))
            logger.info("[SIM] Announced SERVICE_ADDED: {}".format(svc))
            time.sleep(0.05)

    def _handle_frame(self, frame: dict):
        cmd      = frame["cmd"]
        cmd_id   = frame["id"]
        payloads = frame["payloads"]
        cmd_name = CMD_NAMES.get(cmd, "CMD_0x{:04X}".format(cmd))

        logger.debug("[FRAME] cmd={} ({}) id={} payloads={}".format(
            cmd_name, hex(cmd), cmd_id, len(payloads)))

        # ── CONNECT_SERVICE: client announces its service name ──────────────
        if cmd == Cmd.CONNECT_SERVICE:
            if payloads:
                svc = payloads[0][1].decode("utf-8", errors="replace")
                self.service = svc
                STATE.set_client_service(self.fd, svc)
                STATE.add_event("HANDSHAKE", "Service connected", svc)
                logger.info("[CLIENT] Service: {}".format(svc))
            # Send OK response
            self._send_response(cmd_id, "OK")
            return

        # ── SEND_TO_INPUT / SEND_TO_SERVICE: backend pushes a datapoint ────
        if cmd in (Cmd.SEND_TO_INPUT, Cmd.SEND_TO_SERVICE):
            if len(payloads) >= 2:
                target_svc = payloads[0][1].decode("utf-8", errors="replace")
                dp_name    = payloads[1][1].decode("utf-8", errors="replace")
                val_raw    = ""
                d_type_str = "unknown"

                if len(payloads) >= 3:
                    dtype3, data3 = payloads[2]
                    value   = decode_payload(dtype3, data3)
                    val_raw = str(value)
                    d_type_str = DTYPE_NAMES.get(dtype3, str(dtype3))
                    STATE.update_datapoint(dp_name, value, d_type_str, target_svc)
                    STATE.add_event(
                        cmd_name, dp_name,
                        "{} = {} ({})  from={}".format(dp_name, val_raw, d_type_str, target_svc)
                    )
                    logger.info("[DATAPOINT] {} = {} [{}] (from={})".format(
                        dp_name, val_raw, d_type_str, target_svc))

            # Ack
            self._send_response(cmd_id, "OK")
            return

        # ── UPDATE_DATAPOINT: explicit versioned datapoint update ───────────
        if cmd == Cmd.UPDATE_DATAPOINT:
            if len(payloads) >= 2:
                target_svc = payloads[0][1].decode("utf-8", errors="replace")
                dp_name    = payloads[1][1].decode("utf-8", errors="replace")
                if len(payloads) >= 3:
                    dtype3, data3 = payloads[2]
                    value   = decode_payload(dtype3, data3)
                    val_raw = str(value)
                    d_type_str = DTYPE_NAMES.get(dtype3, str(dtype3))
                    # For configs sent as strings (e.g. JSON) show nicely
                    STATE.update_datapoint(dp_name, value, d_type_str, target_svc)
                    STATE.add_event(
                        "UPDATE_DP", dp_name,
                        "{} = {} ({})  target={}".format(dp_name, val_raw, d_type_str, target_svc)
                    )
                    logger.info("[UPDATE_DP] {} = {} [{}] target={}".format(
                        dp_name, val_raw, d_type_str, target_svc))
            self._send_response(cmd_id, "SUCCESS")
            return

        # ── PUBLISH_CONFIG: backend sends a named config entry ──────────────
        if cmd == Cmd.PUBLISH_CONFIG:
            if len(payloads) >= 3:
                cfg_name   = payloads[0][1].decode("utf-8", errors="replace")
                cfg_value  = payloads[1][1].decode("utf-8", errors="replace")
                version_data = payloads[2][1]
                if len(version_data) >= 4:
                    ver = struct.unpack(">I", version_data[:4])[0]
                    if ver >= 0x80000000:
                        ver -= 0x100000000
                else:
                    ver = -1
                sender = payloads[3][1].decode("utf-8", errors="replace") if len(payloads) >= 4 else ""
                target = payloads[4][1].decode("utf-8", errors="replace") if len(payloads) >= 5 else ""

                STATE.update_config(cfg_name, cfg_value, ver, sender, target)
                STATE.add_event(
                    "CONFIG_RX", cfg_name,
                    "v{} | sender={} | target={}".format(ver, sender, target or "(all)")
                )
                logger.info("[CONFIG] Received config='{}' v{} from={} target={}".format(
                    cfg_name, ver, sender, target or "(all)"))

                # Broadcast CONFIG_UPDATE to all connected clients (echo back)
                self._broadcast_config_update(cfg_name, cfg_value, ver, target)
            return

        # ── REFRESH_DATA: backend asks for current state ────────────────────
        if cmd == Cmd.REFRESH_DATA:
            STATE.add_event("REFRESH", "Refresh requested", self.service)
            logger.info("[REFRESH] Requested by {}".format(self.service))
            # Re-announce all services
            threading.Thread(target=self._announce_services_delayed, daemon=True).start()
            return

        # ── DELETE_DATAPOINT ────────────────────────────────────────────────
        if cmd == Cmd.DELETE_DATAPOINT:
            if len(payloads) >= 2:
                target_svc = payloads[0][1].decode("utf-8", errors="replace")
                dp_name    = payloads[1][1].decode("utf-8", errors="replace")
                STATE.add_event("DELETE_DP", dp_name, "target={}".format(target_svc))
                logger.info("[DELETE_DP] {} target={}".format(dp_name, target_svc))
            self._send_response(cmd_id, "SUCCESS")
            return

        # ── PUBLISH_NOTIFICATION ────────────────────────────────────────────
        if cmd == Cmd.PUBLISH_NOTIFICATION:
            if len(payloads) >= 6:
                msg_text = payloads[5][1].decode("utf-8", errors="replace")
                STATE.add_event("NOTIFICATION", msg_text)
                logger.info("[NOTIF] {}".format(msg_text))
            return

        # ── PUBLISH_ACTION / TRIGGER_ACTION ────────────────────────────────
        if cmd in (Cmd.PUBLISH_ACTION, Cmd.TRIGGER_ACTION):
            if payloads:
                action_name = payloads[0][1].decode("utf-8", errors="replace")
                label = "PUBLISH_ACTION" if cmd == Cmd.PUBLISH_ACTION else "TRIGGER_ACTION"
                STATE.add_event(label, action_name)
                logger.info("[{}] {}".format(label, action_name))
            return

        # ── Unknown ─────────────────────────────────────────────────────────
        STATE.add_event("UNKNOWN_CMD", cmd_name, "cmd=0x{:04X}".format(cmd))
        logger.warning("[FRAME] Unknown command: 0x{:04X}".format(cmd))

    def _send_response(self, cmd_id: int, result: str):
        frame = build_frame(
            Cmd.RESPONSE,
            [
                (DType.INT, struct.pack(">H", cmd_id)),
                (DType.STRING, s(result)),
            ],
            cmd_id=cmd_id,
        )
        self._send_raw(frame)

    def _send_service_status(self, status: str, svc_name: str):
        frame = build_frame(
            Cmd.SERVICE_STATUS,
            [
                (DType.STRING, s(status)),
                (DType.STRING, s(svc_name)),
            ],
        )
        self._send_raw(frame)

    def _broadcast_config_update(self, name: str, value: str, version: int, target: str):
        """Re-broadcast CONFIG_UPDATE to all connected clients (mirrors pipeline server)."""
        ver = int(version)
        version_bytes = bytes([
            (ver >> 24) & 0xFF,
            (ver >> 16) & 0xFF,
            (ver >>  8) & 0xFF,
             ver        & 0xFF,
        ])
        frame = build_frame(
            Cmd.CONFIG_UPDATE,
            [
                (DType.STRING, s(name)),
                (DType.STRING, s(value)),
                (DType.INT,   version_bytes),
                (DType.STRING, s(target)),
            ],
        )
        for handler in list(self.server.client_handlers.values()):
            handler._send_raw(frame)

    def _send_raw(self, data: bytes):
        try:
            self.conn.sendall(data)
        except Exception as e:
            logger.warning("[SEND] Error: {}".format(e))

    def _cleanup(self):
        try:
            self.conn.close()
        except Exception:
            pass
        STATE.remove_client(self.fd)
        STATE.add_event("DISCONNECT", "Client disconnected",
                        "{}:{} (service={})".format(self.addr[0], self.addr[1], self.service or "?"))
        logger.info("[CLIENT] Disconnected: {}:{} service={}".format(
            self.addr[0], self.addr[1], self.service))
        with self.server.handlers_lock:
            self.server.client_handlers.pop(self.fd, None)


# ─────────────── TCP Pipeline Server ─────────────────────────────────────────

class PipelineServer(threading.Thread):
    def __init__(self, host: str, port: int):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.client_handlers = {}          # fd → ClientHandler
        self.handlers_lock = threading.Lock()

    def run(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(32)
        logger.info("[SERVER] Listening on {}:{}".format(self.host, self.port))
        STATE.add_event("SERVER", "Pipeline server started",
                        "{}:{}".format(self.host, self.port))
        while True:
            try:
                conn, addr = srv.accept()
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                handler = ClientHandler(conn, addr, self)
                with self.handlers_lock:
                    self.client_handlers[conn.fileno()] = handler
                handler.start()
            except Exception as e:
                logger.error("[SERVER] Accept error: {}".format(e))


# ─────────────── HTTP + SSE Dashboard ────────────────────────────────────────

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ILX Pipeline Simulator</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0d1117;--surface:#161b22;--surface2:#1c2129;--border:#30363d;
  --text:#e6edf3;--muted:#8b949e;--accent:#58a6ff;--green:#3fb950;
  --yellow:#d29922;--red:#f85149;--purple:#bc8cff;--cyan:#39d0d8;
  --orange:#f0883e;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);height:100vh;overflow:hidden;display:flex;flex-direction:column}
header{background:var(--surface);border-bottom:1px solid var(--border);padding:10px 20px;display:flex;align-items:center;gap:16px;flex-shrink:0}
header h1{font-size:16px;font-weight:600;color:var(--accent)}
.pill{display:inline-flex;align-items:center;gap:6px;background:var(--surface2);border:1px solid var(--border);border-radius:20px;padding:3px 10px;font-size:12px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--green);flex-shrink:0;animation:pulse 2s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.badge{margin-left:auto;display:flex;gap:8px;align-items:center;font-size:11px;color:var(--muted)}
.main{display:grid;grid-template-columns:1fr 1fr 1fr;grid-template-rows:auto 1fr;gap:1px;background:var(--border);flex:1;overflow:hidden}
.panel{background:var(--surface);display:flex;flex-direction:column;overflow:hidden}
.panel-header{padding:8px 14px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border);background:var(--surface2);flex-shrink:0}
.panel-title{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:var(--muted)}
.panel-count{font-size:11px;font-weight:600;background:var(--accent);color:#000;border-radius:10px;padding:1px 7px;min-width:22px;text-align:center}
.panel-body{flex:1;overflow-y:auto;padding:4px 0}
.panel-body::-webkit-scrollbar{width:4px}
.panel-body::-webkit-scrollbar-track{background:transparent}
.panel-body::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}

/* Datapoints */
.dp-row{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:start;padding:6px 14px;border-bottom:1px solid rgba(48,54,61,.5);transition:background .15s}
.dp-row:hover{background:var(--surface2)}
.dp-name{font-size:11px;font-family:'JetBrains Mono',monospace;color:var(--accent);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dp-meta{font-size:10px;color:var(--muted);margin-top:2px}
.dp-value{font-size:12px;font-family:'JetBrains Mono',monospace;text-align:right;word-break:break-all;max-width:180px}
.dp-value.string{color:var(--green)}
.dp-value.number{color:var(--yellow)}
.dp-value.bool-true{color:var(--cyan)}
.dp-value.bool-false{color:var(--red)}
.dp-row.flash{animation:rowflash .4s ease-out}
@keyframes rowflash{0%{background:#1c3a5e}100%{background:transparent}}

/* Config panel */
.cfg-card{margin:6px 10px;border:1px solid var(--border);border-radius:6px;overflow:hidden}
.cfg-header{padding:7px 10px;background:var(--surface2);display:flex;align-items:center;justify-content:space-between;cursor:pointer;user-select:none}
.cfg-name{font-size:11px;font-family:'JetBrains Mono',monospace;color:var(--purple);font-weight:600}
.cfg-meta{font-size:10px;color:var(--muted)}
.cfg-body{display:none;max-height:300px;overflow-y:auto;background:#0d1117}
.cfg-body.open{display:block}
pre.cfg-json{font-family:'JetBrains Mono',monospace;font-size:10px;padding:10px;color:#e6edf3;white-space:pre-wrap;word-break:break-word;line-height:1.6}
.cfg-flash{animation:cfgflash .5s ease-out}
@keyframes cfgflash{0%{border-color:var(--purple)}100%{border-color:var(--border)}}

/* Events */
.ev-row{padding:4px 14px;border-bottom:1px solid rgba(48,54,61,.3);display:grid;grid-template-columns:58px auto 1fr;gap:6px;align-items:baseline}
.ev-ts{font-size:10px;font-family:'JetBrains Mono',monospace;color:var(--muted)}
.ev-kind{font-size:10px;font-weight:600;border-radius:3px;padding:1px 5px;text-align:center}
.ev-msg{font-size:11px;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ev-detail{font-size:10px;color:var(--muted);grid-column:2/4;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-left:0}
.kind-CONNECT,.kind-HANDSHAKE{background:#1a3045;color:var(--accent)}
.kind-DISCONNECT{background:#3d1a1a;color:var(--red)}
.kind-SEND_TO_INPUT,.kind-SEND_TO_SERVICE,.kind-UPDATE_DP{background:#1a3d1a;color:var(--green)}
.kind-CONFIG_RX{background:#2d1a3d;color:var(--purple)}
.kind-REFRESH{background:#3d2d1a;color:var(--orange)}
.kind-SVC_ADDED{background:#1a2d3d;color:var(--cyan)}
.kind-SERVER{background:#1a2d1a;color:var(--green)}
.kind-NOTIFICATION{background:#3d3d1a;color:var(--yellow)}
.kind-UNKNOWN_CMD{background:#3d1a1a;color:var(--red)}
.kind-default{background:var(--surface2);color:var(--muted)}

/* Clients panel (bottom row, spans all 3 cols) */
.clients-bar{background:var(--surface2);border-top:1px solid var(--border);padding:6px 20px;display:flex;gap:16px;align-items:center;flex-shrink:0;flex-wrap:wrap}
.client-chip{display:inline-flex;align-items:center;gap:6px;background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:3px 10px;font-size:11px}
.client-chip .svc{color:var(--accent)}
.client-chip .addr{color:var(--muted)}
.no-clients{color:var(--muted);font-size:11px}

.services-bar{background:var(--surface2);border-bottom:1px solid var(--border);padding:5px 20px;display:flex;gap:8px;flex-shrink:0;overflow-x:auto}
.svc-pill{display:inline-flex;align-items:center;gap:5px;font-size:10px;font-weight:600;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:2px 8px;color:var(--cyan)}
.svc-pill .svc-dot{width:6px;height:6px;border-radius:50%;background:var(--green)}

#dp-count,#cfg-count,#ev-count{transition:transform .2s}
.bump{animation:bump .3s ease-out}
@keyframes bump{0%{transform:scale(1.4)}100%{transform:scale(1)}}
</style>
</head>
<body>
<header>
  <div style="display:flex;align-items:center;gap:10px">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
    <h1>ILX Pipeline Simulator</h1>
  </div>
  <div class="pill"><span class="dot"></span><span id="status-text">Connecting...</span></div>
  <div class="badge">
    <span>Started: <strong id="started-at">-</strong></span>
    <span style="color:var(--border)">|</span>
    <span>Port: <strong id="srv-port">7000</strong></span>
  </div>
</header>

<div class="services-bar" id="services-bar">
  <span style="font-size:10px;color:var(--muted);margin-right:4px">SERVICES:</span>
</div>

<div class="main">
  <!-- Datapoints -->
  <div class="panel" style="grid-row:1">
    <div class="panel-header">
      <span class="panel-title">⚡ Datapoints</span>
      <span class="panel-count" id="dp-count">0</span>
    </div>
    <div class="panel-body" id="dp-list"></div>
  </div>

  <!-- Configs -->
  <div class="panel" style="grid-row:1">
    <div class="panel-header">
      <span class="panel-title">📦 Configs (JSON)</span>
      <span class="panel-count" id="cfg-count">0</span>
    </div>
    <div class="panel-body" id="cfg-list"></div>
  </div>

  <!-- Events -->
  <div class="panel" style="grid-row:1">
    <div class="panel-header">
      <span class="panel-title">📋 Event Log</span>
      <span class="panel-count" id="ev-count">0</span>
    </div>
    <div class="panel-body" id="ev-list"></div>
  </div>
</div>

<div class="clients-bar" id="clients-bar">
  <span style="font-size:10px;color:var(--muted);margin-right:4px">CLIENTS:</span>
  <span class="no-clients" id="no-clients">No clients connected</span>
</div>

<script>
const SERVICES = [
  "modbus_service","load_cell_service","iot-gateway","ilx_craneiq_core","network_status"
];

// Render static service pills
const bar = document.getElementById('services-bar');
SERVICES.forEach(s => {
  const el = document.createElement('div');
  el.className = 'svc-pill';
  el.id = 'svc-' + s;
  el.innerHTML = `<span class="svc-dot"></span>${s}`;
  bar.appendChild(el);
});

const state = { datapoints:{}, configs:{}, events:[] };
let evCount = 0;

function valClass(value, dtype) {
  if (dtype === 'bool') return value ? 'bool-true' : 'bool-false';
  if (['int32','int64','float32','float64'].includes(dtype)) return 'number';
  return 'string';
}

function renderDP(name, dp) {
  const cls = valClass(dp.value, dp.type);
  let valStr = String(dp.value);
  if (typeof dp.value === 'object') valStr = JSON.stringify(dp.value);
  const existing = document.getElementById('dp-'+name);
  const html = `
    <div class="dp-name" title="${name}">${name}</div>
    <div class="dp-meta">${dp.type} • ${dp.from} • ×${dp.count}</div>
    <div class="dp-value ${cls}" style="grid-row:1/3">${valStr}</div>`;
  if (existing) {
    existing.innerHTML = html;
    existing.classList.remove('flash');
    void existing.offsetWidth;
    existing.classList.add('flash');
  } else {
    const row = document.createElement('div');
    row.className = 'dp-row';
    row.id = 'dp-'+name;
    row.style.gridTemplateColumns = 'minmax(0,1fr) 180px';
    row.style.gridTemplateRows = 'auto auto';
    row.innerHTML = html;
    document.getElementById('dp-list').prepend(row);
  }
  const cnt = document.getElementById('dp-count');
  const n = Object.keys(state.datapoints).length;
  cnt.textContent = n;
  cnt.classList.remove('bump'); void cnt.offsetWidth; cnt.classList.add('bump');
}

function renderConfig(name, cfg) {
  let pretty = '';
  try {
    pretty = JSON.stringify(cfg.value_parsed, null, 2);
  } catch(e) {
    pretty = String(cfg.value_raw);
  }
  const existing = document.getElementById('cfg-'+name);
  if (existing) {
    existing.querySelector('.cfg-meta').textContent =
      `v${cfg.version} • ${cfg.sender} → ${cfg.target} • ${cfg.ts}`;
    existing.querySelector('pre').textContent = pretty;
    existing.classList.remove('cfg-flash');
    void existing.offsetWidth;
    existing.classList.add('cfg-flash');
  } else {
    const card = document.createElement('div');
    card.className = 'cfg-card';
    card.id = 'cfg-'+name;
    card.innerHTML = `
      <div class="cfg-header" onclick="this.nextElementSibling.classList.toggle('open')">
        <span class="cfg-name">${name}</span>
        <span class="cfg-meta">v${cfg.version} • ${cfg.sender} → ${cfg.target} • ${cfg.ts}</span>
      </div>
      <div class="cfg-body open"><pre class="cfg-json">${pretty}</pre></div>`;
    document.getElementById('cfg-list').prepend(card);
  }
  const cnt = document.getElementById('cfg-count');
  const n = Object.keys(state.configs).length;
  cnt.textContent = n;
  cnt.classList.remove('bump'); void cnt.offsetWidth; cnt.classList.add('bump');
}

function kindClass(kind) {
  const map = {
    CONNECT:'CONNECT', HANDSHAKE:'HANDSHAKE', DISCONNECT:'DISCONNECT',
    SEND_TO_INPUT:'SEND_TO_INPUT', SEND_TO_SERVICE:'SEND_TO_SERVICE',
    UPDATE_DP:'UPDATE_DP', CONFIG_RX:'CONFIG_RX', REFRESH:'REFRESH',
    SVC_ADDED:'SVC_ADDED', SERVER:'SERVER', NOTIFICATION:'NOTIFICATION',
    UNKNOWN_CMD:'UNKNOWN_CMD'
  };
  return 'ev-kind kind-'+(map[kind]||'default');
}

function renderEvent(ev) {
  const row = document.createElement('div');
  row.className = 'ev-row';
  row.innerHTML = `
    <span class="ev-ts">${ev.ts}</span>
    <span class="${kindClass(ev.kind)}">${ev.kind}</span>
    <span class="ev-msg">${ev.msg}</span>
    ${ev.detail ? `<span class="ev-detail">${ev.detail}</span>` : ''}`;
  const list = document.getElementById('ev-list');
  list.prepend(row);
  while (list.children.length > 200) list.removeChild(list.lastChild);
  evCount++;
  const cnt = document.getElementById('ev-count');
  cnt.textContent = evCount;
  cnt.classList.remove('bump'); void cnt.offsetWidth; cnt.classList.add('bump');
}

function renderClients(clients) {
  const bar = document.getElementById('clients-bar');
  const noC = document.getElementById('no-clients');
  // remove old chips
  bar.querySelectorAll('.client-chip').forEach(e=>e.remove());
  if (!clients || clients.length === 0) {
    noC.style.display = '';
    return;
  }
  noC.style.display = 'none';
  clients.forEach(c => {
    const chip = document.createElement('div');
    chip.className = 'client-chip';
    chip.innerHTML = `<span class="dot"></span><span class="svc">${c.service}</span><span class="addr">${c.addr}</span><span style="font-size:9px;color:var(--muted)">${c.connected_at}</span>`;
    bar.appendChild(chip);
  });
}

// SSE
const es = new EventSource('/events');
es.onopen = () => document.getElementById('status-text').textContent = 'Connected';
es.onerror = () => document.getElementById('status-text').textContent = 'Reconnecting…';

es.addEventListener('snapshot', e => {
  const d = JSON.parse(e.data);
  document.getElementById('started-at').textContent = d.started_at;
  // Populate datapoints
  Object.entries(d.datapoints||{}).forEach(([n,dp]) => {
    state.datapoints[n] = dp;
    renderDP(n, dp);
  });
  // Populate configs
  Object.entries(d.configs||{}).forEach(([n,cfg]) => {
    state.configs[n] = cfg;
    renderConfig(n, cfg);
  });
  // Populate events
  (d.events||[]).slice().reverse().forEach(ev => renderEvent(ev));
  renderClients(d.clients||[]);
});

es.addEventListener('datapoint', e => {
  const dp = JSON.parse(e.data);
  state.datapoints[dp.name] = dp;
  renderDP(dp.name, dp);
});

es.addEventListener('config', e => {
  const cfg = JSON.parse(e.data);
  state.configs[cfg.name] = cfg;
  renderConfig(cfg.name, cfg);
});

es.addEventListener('event', e => {
  const ev = JSON.parse(e.data);
  renderEvent(ev);
});

es.addEventListener('clients', e => {
  renderClients(JSON.parse(e.data));
});
</script>
</body>
</html>"""


import queue as _queue

class WebHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence access logs

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            body = DASHBOARD_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/events":
            q = _queue.Queue(maxsize=500)
            STATE.subscribe_sse(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            # Send full snapshot first
            snap = STATE.snapshot()
            try:
                self.wfile.write(
                    "event: snapshot\ndata: {}\n\n".format(json.dumps(snap)).encode()
                )
                self.wfile.flush()
            except Exception:
                STATE.unsubscribe_sse(q)
                return

            while True:
                try:
                    msg = q.get(timeout=30)
                    self.wfile.write(msg)
                    self.wfile.flush()
                except _queue.Empty:
                    # heartbeat
                    try:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                    except Exception:
                        break
                except Exception:
                    break

            STATE.unsubscribe_sse(q)

        elif self.path == "/api/state":
            body = json.dumps(STATE.snapshot()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_response(404)
            self.end_headers()


def run_web(host: str, port: int):
    server = HTTPServer((host, port), WebHandler)
    logger.info("[WEB] Dashboard at http://{}:{}/".format(host, port))
    server.serve_forever()


# ─────────────── Entry point ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ILX Pipeline Simulator Server")
    parser.add_argument("--host",     default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    parser.add_argument("--port",     type=int, default=7000, help="Pipeline TCP port (default 7000)")
    parser.add_argument("--web-port", type=int, default=8765, help="Dashboard HTTP port (default 8765)")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  ILX Pipeline Simulator")
    print("=" * 60)
    print("  TCP Server : {}:{}".format(args.host, args.port))
    print("  Dashboard  : http://{}:{}/".format(args.host, args.web_port))
    print("  Services   :")
    for svc in SIMULATED_SERVICES:
        print("    * {}".format(svc))
    print("=" * 60 + "\n")

    # Start pipeline TCP server
    pipeline_server = PipelineServer(args.host, args.port)
    pipeline_server.start()

    # Start web dashboard in background thread
    web_thread = threading.Thread(
        target=run_web, args=(args.host, args.web_port), daemon=True
    )
    web_thread.start()

    # Block main thread
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[STOP] Simulator stopped.")


if __name__ == "__main__":
    main()
