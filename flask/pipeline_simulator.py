#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_simulator.py
=====================
A self-contained pipeline SERVER + CLIENT that speaks the EXACT same binary
protocol as ilx_pipeline / Innospace Pipeline.

Verified against pipeline_client.py source:

  UPDATE_DATAPOINT frame payloads (what a real client sends):
    [0] request_id   (2 bytes big-endian, stored as DT_INT payload)
    [1] target_svc   (string)
    [2] dp_name      (string)
    [3] value        (any typed payload)
    [4] sender_name  (string)

  DATA_UPDATE frame payloads (what the server forwards to receiver):
    [0] sender_name  (string)   <- becomes event.service_name  in RECEIVE_DONE
    [1] dp_name      (string)   <- becomes event.datapoint_name
    [2] value        (typed)
    [3] timestamp_us (LONG, optional)

  SERVICE_STATUS payloads:
    [0] "ADDED" | "REMOVED"
    [1] service_name

  CONNECT_SERVICE payloads:
    [0] service_name

  RESPONSE payloads:
    [0] request_id bytes (2-byte big-endian)
    [1] result string ("SUCCESS" | "FAILURE")

Usage
-----
  python pipeline_simulator.py                        # server + sim client
  python pipeline_simulator.py --server-only          # hub only
  python pipeline_simulator.py --client-only          # sim client only
  python pipeline_simulator.py --service load_cell_service --target web_ui
"""

import argparse
import json
import logging
import queue
import select
import socket
import struct
import threading
import time

# logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-7s]  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipe_sim")

# ══════════════════════════════════════════════════════════════════════════════
# PROTOCOL CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

SOF      = 0xAA
API_VER  = 0x02
EOF_BYTE = 0x55

CMD_CONNECT_SERVICE      = 0x0001
CMD_SEND_TO_SERVICE      = 0x0002
CMD_SEND_TO_INPUT        = 0x0003
CMD_DATA_UPDATE          = 0x0007
CMD_RESPONSE             = 0x0008
CMD_REFRESH_DATA         = 0x0009
CMD_DELETE_DATAPOINT     = 0x000A
CMD_UPDATE_DATAPOINT     = 0x000B
CMD_SERVICE_STATUS       = 0x000C
CMD_PUBLISH_ACTION       = 0x000D
CMD_TRIGGER_ACTION       = 0x000E
CMD_PUBLISH_CONFIG       = 0x000F
CMD_CONFIG_UPDATE        = 0x0010
CMD_PUBLISH_NOTIFICATION = 0x0011

DT_STRING = 0x01
DT_INT    = 0x02
DT_LONG   = 0x03
DT_FLOAT  = 0x04
DT_DOUBLE = 0x05
DT_BOOL   = 0x06

# ══════════════════════════════════════════════════════════════════════════════
# CRC-16-CCITT
# ══════════════════════════════════════════════════════════════════════════════

_CRC = []
for _i in range(256):
    _c = _i << 8
    for _ in range(8):
        _c = ((_c << 1) ^ 0x1021) if _c & 0x8000 else _c << 1
    _CRC.append(_c & 0xFFFF)

def crc16(data):
    c = 0xFFFF
    for b in data:
        c = ((c << 8) ^ _CRC[(c >> 8) ^ b]) & 0xFFFF
    return c

# ══════════════════════════════════════════════════════════════════════════════
# FRAME SERIALISER
# ══════════════════════════════════════════════════════════════════════════════

def _build(cmd, payloads, cmd_id=0):
    """
    Build one complete binary frame.
    payloads = list of (dt_code:int, raw_bytes:bytes)
    """
    body = bytearray()
    body += struct.pack('>H', cmd)
    body += struct.pack('>H', cmd_id)
    body += struct.pack('>H', len(payloads))
    for dt, raw in payloads:
        body += struct.pack('>I', len(raw))
        body += bytes([dt])
        body += raw
    frame_len = len(body) + 2       # body + CRC(2)
    header    = bytes([SOF, API_VER]) + struct.pack('>I', frame_len)
    checksum  = crc16(bytes(body))  # CRC over body only (after 6-byte header)
    return header + bytes(body) + struct.pack('>H', checksum) + bytes([EOF_BYTE])

# payload type helpers
def _s(v):           return (DT_STRING, str(v).encode('utf-8'))
def _i(v):           return (DT_INT,    struct.pack('=i', int(v)))
def _l(v):           return (DT_LONG,   struct.pack('=q', int(v)))
def _f(v):           return (DT_FLOAT,  struct.pack('=f', float(v)))
def _d(v):           return (DT_DOUBLE, struct.pack('=d', float(v)))
def _bool(v):        return (DT_BOOL,   struct.pack('=?', bool(v)))
def _ts():
    return (DT_LONG, struct.pack('=q', int(time.time() * 1_000_000)))

def _rid(v):
    """request_id: DT_INT payload, but bytes are big-endian uint16 (matches pipeline_client.py)."""
    return (DT_INT, struct.pack('>H', v & 0xFFFF))

def _encode_value(value):
    """Auto-encode a Python value to the right (dt, bytes) payload."""
    if isinstance(value, bool):   return _bool(value)
    if isinstance(value, int):
        if -(2**31) <= value < 2**31: return _i(value)
        return _l(value)
    if isinstance(value, float):  return _d(value)
    return _s(str(value))

# ready-made frame builders

def frm_connect(service):
    return _build(CMD_CONNECT_SERVICE, [_s(service)])

def frm_service_status(status, svc):
    return _build(CMD_SERVICE_STATUS, [_s(status), _s(svc)])

def frm_data_update(sender, dp, dt, raw):
    """DATA_UPDATE = what the server sends to the receiver (e.g. web_ui)."""
    return _build(CMD_DATA_UPDATE, [_s(sender), _s(dp), (dt, raw), _ts()])

def frm_update_datapoint(sender, target, dp, value, req_id):
    """
    UPDATE_DATAPOINT = what a real client sends to the server.
    Payload order verified from pipeline_client.py datapoint_update():
      [0] request_id  (DT_INT, 2-byte big-endian)
      [1] target_svc  (string)
      [2] dp_name     (string)
      [3] value       (typed)
      [4] sender_name (string)
    """
    return _build(CMD_UPDATE_DATAPOINT, [
        _rid(req_id),
        _s(target),
        _s(dp),
        _encode_value(value),
        _s(sender),
    ], cmd_id=req_id)

def frm_response(req_id, result="SUCCESS"):
    return _build(CMD_RESPONSE, [
        (DT_INT, struct.pack('>H', req_id & 0xFFFF)),
        _s(result),
    ])

def frm_refresh(service):
    return _build(CMD_REFRESH_DATA, [_s(service)])

def frm_config_update(name, value, version, target=""):
    ver_bytes = struct.pack('>I', version & 0xFFFFFFFF)
    return _build(CMD_CONFIG_UPDATE, [_s(name), _s(value), (DT_INT, ver_bytes), _s(target)])

def frm_notification(n_type, priority, category, subsystem, entity, message):
    return _build(CMD_PUBLISH_NOTIFICATION, [
        (DT_INT, bytes([n_type])),
        (DT_INT, bytes([priority])),
        (DT_INT, bytes([category])),
        _s(subsystem), _s(entity), _s(message),
    ])

# ══════════════════════════════════════════════════════════════════════════════
# FRAME PARSER
# ══════════════════════════════════════════════════════════════════════════════

class Payload(object):
    __slots__ = ('dt', 'data')
    def __init__(self, dt, data):
        self.dt, self.data = dt, bytes(data)

    def str(self):
        return self.data.decode('utf-8', errors='replace')

    def int_(self):
        return struct.unpack('=i', self.data[:4])[0] if len(self.data) >= 4 else 0

    def long_(self):
        return struct.unpack('=q', self.data[:8])[0] if len(self.data) >= 8 else 0

    def float_(self):
        return struct.unpack('=f', self.data[:4])[0] if len(self.data) >= 4 else 0.0

    def double_(self):
        return struct.unpack('=d', self.data[:8])[0] if len(self.data) >= 8 else 0.0

    def bool_(self):
        return bool(self.data[0]) if self.data else False

    def rid(self):
        """Decode request_id: 2-byte big-endian stored in DT_INT payload."""
        return struct.unpack('>H', self.data[:2])[0] if len(self.data) >= 2 else 0

    def value(self):
        if self.dt == DT_STRING: return self.str()
        if self.dt == DT_INT:    return self.int_()
        if self.dt == DT_LONG:   return self.long_()
        if self.dt == DT_FLOAT:  return self.float_()
        if self.dt == DT_DOUBLE: return self.double_()
        if self.dt == DT_BOOL:   return self.bool_()
        return self.data


class Frame(object):
    __slots__ = ('cmd', 'cmd_id', 'payloads')
    def __init__(self, cmd, cmd_id, payloads):
        self.cmd, self.cmd_id, self.payloads = cmd, cmd_id, payloads

    def p(self, i):
        return self.payloads[i] if i < len(self.payloads) else Payload(DT_STRING, b'')


def parse_frames(buf):
    """Consume all complete frames from buf (mutates in-place). Returns list[Frame]."""
    frames = []
    while len(buf) >= 12:
        s = 0
        while s < len(buf) and buf[s] != SOF:
            s += 1
        if s:
            del buf[:s]
        if len(buf) < 12:
            break
        if buf[1] != API_VER:
            del buf[:1]; continue

        frame_len = struct.unpack('>I', buf[2:6])[0]
        total = 2 + 4 + frame_len + 1   # SOF+VER + len_field + (body+CRC) + EOF
        if len(buf) < total:
            break

        raw = bytes(buf[:total])
        if raw[-1] != EOF_BYTE:
            del buf[:1]; continue

        body_end = total - 3           # exclude CRC(2) + EOF(1)
        body     = raw[6:body_end]
        stored   = struct.unpack('>H', raw[body_end:body_end+2])[0]
        if crc16(body) != stored:
            del buf[:1]; continue

        pos = 0
        try:
            cmd    = struct.unpack('>H', body[pos:pos+2])[0]; pos += 2
            cmd_id = struct.unpack('>H', body[pos:pos+2])[0]; pos += 2
            n_p    = struct.unpack('>H', body[pos:pos+2])[0]; pos += 2
            pays, ok = [], True
            for _ in range(n_p):
                if pos + 5 > len(body): ok = False; break
                plen = struct.unpack('>I', body[pos:pos+4])[0]; pos += 4
                dt   = body[pos]; pos += 1
                if pos + plen > len(body): ok = False; break
                pays.append(Payload(dt, body[pos:pos+plen])); pos += plen
            if ok:
                frames.append(Frame(cmd, cmd_id, pays))
        except Exception:
            del buf[:1]; continue

        del buf[:total]
    return frames

# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE HUB SERVER
# ══════════════════════════════════════════════════════════════════════════════

class PipelineServer(object):
    """
    TCP hub that routes frames between all registered clients.

    UPDATE_DATAPOINT routing (verified against real protocol)
    ---------------------------------------------------------
    Client sends:  [rid, target_svc, dp_name, value, sender]
    Server does:   forward as DATA_UPDATE [sender, dp_name, value, ts] to target
                   reply with RESPONSE [rid, "SUCCESS"] to sender
    Result:        web_ui RECEIVE_DONE fires with
                     event.service_name   = sender  (e.g. "load_cell_service")
                     event.datapoint_name = dp_name (e.g. "loadcell_config")
    """

    def __init__(self, host="127.0.0.1", port=7000):
        self.host, self.port = host, port
        self._lock     = threading.RLock()
        self._clients  = {}      # fd -> {sock, buf, name, addr}
        self._services = {}      # service_name -> fd
        self._running  = False

    def start(self):
        self._running = True
        threading.Thread(target=self._run, daemon=True, name="PipeServer").start()

    def stop(self):
        self._running = False

    # ── main loop ────────────────────────────────────────────────────────────

    def _run(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(20)
        srv.setblocking(False)
        log.info("[SERVER] Listening on %s:%d", self.host, self.port)

        while self._running:
            with self._lock:
                client_socks = [i['sock'] for i in self._clients.values()]
            try:
                rd, _, _ = select.select([srv] + client_socks, [], [], 1.0)
            except Exception:
                break

            for s in rd:
                if s is srv:
                    try:
                        conn, addr = srv.accept()
                        conn.setblocking(False)
                        fd = conn.fileno()
                        with self._lock:
                            self._clients[fd] = {
                                'sock': conn, 'buf': bytearray(),
                                'name': None, 'addr': "{}:{}".format(*addr)
                            }
                        log.info("[SERVER] New connection fd=%d from %s:%d", fd, *addr)
                    except Exception as e:
                        log.debug("[SERVER] accept error: %s", e)
                else:
                    self._read(s)

        try: srv.close()
        except Exception: pass
        log.info("[SERVER] Stopped")

    def _read(self, sock):
        fd = sock.fileno()
        with self._lock:
            info = self._clients.get(fd)
        if not info: return
        try:
            chunk = sock.recv(65536)
        except Exception:
            chunk = b''
        if not chunk:
            self._drop(fd); return
        info['buf'].extend(chunk)
        for fr in parse_frames(info['buf']):
            self._dispatch(fd, info, fr)

    # ── dispatcher ───────────────────────────────────────────────────────────

    def _dispatch(self, fd, info, fr):
        cmd = fr.cmd
        p   = fr.payloads

        # ── CONNECT_SERVICE ──────────────────────────────────────────────────
        if cmd == CMD_CONNECT_SERVICE:
            svc = fr.p(0).str()
            with self._lock:
                info['name']        = svc
                self._services[svc] = fd
                others = [n for n in self._services if n != svc]
            log.info("[SERVER] CONNECT    fd=%-3d  service='%s'", fd, svc)
            self._broadcast(frm_service_status("ADDED", svc), exclude=fd)
            for other in others:
                self._send_fd(fd, frm_service_status("ADDED", other))

        # ── UPDATE_DATAPOINT ─────────────────────────────────────────────────
        # Payload order from pipeline_client.py datapoint_update():
        #   [0] request_id  (DT_INT, 2-byte big-endian)
        #   [1] target_svc  (string)
        #   [2] dp_name     (string)
        #   [3] value       (typed)
        #   [4] sender_name (string)
        elif cmd == CMD_UPDATE_DATAPOINT:
            if len(p) >= 4:
                req_id = fr.p(0).rid()
                target = fr.p(1).str()
                dp     = fr.p(2).str()
                val_p  = fr.p(3)
                sender = fr.p(4).str() if len(p) > 4 else (info.get('name') or "unknown")

                log.info("[SERVER] UPDATE_DP  %s -> %s . %s  (rid=%d)",
                         sender, target, dp, req_id)

                # Forward as DATA_UPDATE to the target service
                # [sender, dp_name, value, ts] — this is what triggers RECEIVE_DONE in web_ui
                out = frm_data_update(sender, dp, val_p.dt, val_p.data)
                self._send_service(target, out)

                # ACK back to sender
                self._send_fd(fd, frm_response(req_id, "SUCCESS"))

        # ── SEND_TO_INPUT / SEND_TO_SERVICE ──────────────────────────────────
        # Payload order from pipeline_client.py send_dirty_datapoints():
        #   [0] sender_service  (string)
        #   [1] dp_name         (string)
        #   [2] value           (typed)
        #   [3] timestamp_us    (LONG, optional)
        #   [4] sender_service  (string, optional duplicate)
        elif cmd in (CMD_SEND_TO_INPUT, CMD_SEND_TO_SERVICE):
            if len(p) >= 3:
                sender = fr.p(0).str()
                dp     = fr.p(1).str()
                val_p  = fr.p(2)
                log.info("[SERVER] SEND_TO_INPUT  %s . %s", sender, dp)
                out = frm_data_update(sender, dp, val_p.dt, val_p.data)
                self._broadcast(out, exclude=fd)

        # ── REFRESH_DATA ─────────────────────────────────────────────────────
        elif cmd == CMD_REFRESH_DATA:
            log.info("[SERVER] REFRESH_DATA from fd=%d", fd)
            with self._lock:
                svcs = list(self._services.keys())
            for svc in svcs:
                self._send_fd(fd, frm_service_status("ADDED", svc))

        # ── PUBLISH_CONFIG ────────────────────────────────────────────────────
        elif cmd == CMD_PUBLISH_CONFIG:
            name   = fr.p(0).str()
            value  = fr.p(1).str()
            ver_r  = fr.p(2).data if len(p) > 2 else b'\x00\x00\x00\x00'
            target = fr.p(3).str() if len(p) > 3 else ""
            ver    = struct.unpack('>I', ver_r[:4])[0] if len(ver_r) >= 4 else 0
            log.info("[SERVER] PUBLISH_CONFIG  name='%s' target='%s'", name, target)
            out = frm_config_update(name, value, ver, target)
            if target:
                self._send_service(target, out)
            else:
                self._broadcast(out, exclude=fd)

        # ── PUBLISH_NOTIFICATION ──────────────────────────────────────────────
        elif cmd == CMD_PUBLISH_NOTIFICATION:
            msg = fr.p(5).str() if len(p) > 5 else "?"
            log.info("[SERVER] NOTIFICATION  msg='%s'", msg)
            out = _build(CMD_PUBLISH_NOTIFICATION, [(pp.dt, pp.data) for pp in p])
            self._broadcast(out, exclude=fd)

        # ── ACTIONS ───────────────────────────────────────────────────────────
        elif cmd in (CMD_TRIGGER_ACTION, CMD_PUBLISH_ACTION):
            action = fr.p(0).str() if p else "?"
            label  = "TRIGGER_ACTION" if cmd == CMD_TRIGGER_ACTION else "PUBLISH_ACTION"
            log.info("[SERVER] %s  action='%s'", label, action)
            out = _build(cmd, [(pp.dt, pp.data) for pp in p])
            self._broadcast(out, exclude=fd)

        else:
            log.debug("[SERVER] Unknown cmd=0x%04X fd=%d", cmd, fd)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _send_fd(self, fd, data):
        with self._lock:
            info = self._clients.get(fd)
        if info:
            self._send_sock(info['sock'], data)

    def _send_service(self, svc_name, data):
        with self._lock:
            fd = self._services.get(svc_name, -1)
        if fd == -1:
            log.debug("[SERVER] Target '%s' not found; broadcasting instead", svc_name)
            self._broadcast(data)
            return
        self._send_fd(fd, data)

    def _broadcast(self, data, exclude=-1):
        with self._lock:
            fds = list(self._clients.keys())
        for fd in fds:
            if fd != exclude:
                self._send_fd(fd, data)

    @staticmethod
    def _send_sock(sock, data):
        try:
            total = 0
            while total < len(data):
                n = sock.send(data[total:])
                if n <= 0: return False
                total += n
            return True
        except Exception:
            return False

    def _drop(self, fd):
        with self._lock:
            info = self._clients.pop(fd, None)
            if info is None: return
            svc = info.get('name')
            if svc and self._services.get(svc) == fd:
                del self._services[svc]
        try: info['sock'].close()
        except Exception: pass
        log.info("[SERVER] fd=%d ('%s') disconnected", fd, info.get('name') or '?')
        if info.get('name'):
            self._broadcast(frm_service_status("REMOVED", info['name']))

# ══════════════════════════════════════════════════════════════════════════════
# SIM CLIENT
# ══════════════════════════════════════════════════════════════════════════════

class SimClient(object):
    """
    Registers as a named service, sends UPDATE_DATAPOINT frames and receives
    DATA_UPDATE / SERVICE_STATUS / RESPONSE frames.

    send(target, dp, value)   ←→  PipelineClient.datapoint_update(target, dp, value)
    """

    def __init__(self, service_name, host="127.0.0.1", port=7000):
        self.service_name = service_name
        self.host, self.port = host, port
        self._sock      = None
        self._buf       = bytearray()
        self._connected = False
        self._running   = False
        self._req_id    = 1
        self._lock      = threading.Lock()
        self._send_q    = queue.Queue()
        # Optional callback: receive_callback(service_name, dp_name, value)
        self.receive_callback = None

    # ── lifecycle ────────────────────────────────────────────────────────────

    def start(self):
        self._running = True
        threading.Thread(target=self._recv_thread, daemon=True,
                         name="SimC-recv-{}".format(self.service_name)).start()
        threading.Thread(target=self._send_thread, daemon=True,
                         name="SimC-send-{}".format(self.service_name)).start()

    def stop(self):
        self._running = False
        self._send_q.put(None)
        if self._sock:
            try: self._sock.close()
            except Exception: pass

    def wait_until_connected(self, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._connected: return True
            time.sleep(0.05)
        return False

    @property
    def connected(self):
        return self._connected

    # ── public send API ──────────────────────────────────────────────────────

    def send(self, target, dp, value):
        """
        Send value to target.dp via UPDATE_DATAPOINT.
        Equivalent to PipelineClient.datapoint_update(target, dp, value).
        Returns request_id > 0, or 0 if not connected.
        """
        if not self._connected:
            return 0
        with self._lock:
            rid = self._req_id
            self._req_id = (self._req_id % 65535) + 1
        data = frm_update_datapoint(self.service_name, target, dp, value, rid)
        self._send_q.put(data)
        return rid

    def refresh(self):
        if self._connected:
            self._send_q.put(frm_refresh(self.service_name))

    def send_raw_frame(self, data):
        """Enqueue a pre-built raw frame for sending."""
        self._send_q.put(data)

    # ── internals ────────────────────────────────────────────────────────────

    def _recv_thread(self):
        while self._running:
            if not self._connect():
                time.sleep(2); continue
            self._read_loop()
            self._connected = False
            if self._sock:
                try: self._sock.close()
                except Exception: pass
                self._sock = None
            if self._running:
                log.info("[CLIENT:%s] Disconnected, retrying…", self.service_name)
                time.sleep(2)

    def _connect(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((self.host, self.port))
            s.setblocking(True)
            s.sendall(frm_connect(self.service_name))
            s.setblocking(False)
            self._sock = s
            self._buf  = bytearray()
            self._connected = True
            log.info("[CLIENT:%s] Connected and registered", self.service_name)
            return True
        except Exception as e:
            log.warning("[CLIENT:%s] Connect failed: %s", self.service_name, e)
            return False

    def _read_loop(self):
        while self._running and self._connected and self._sock:
            try:
                rd, _, ex = select.select([self._sock], [], [self._sock], 1.0)
            except Exception: break
            if ex: break
            if not rd: continue
            try:
                chunk = self._sock.recv(65536)
            except Exception: break
            if not chunk: break
            self._buf.extend(chunk)
            for fr in parse_frames(self._buf):
                self._handle(fr)

    def _send_thread(self):
        while self._running:
            try:
                data = self._send_q.get(timeout=1.0)
            except queue.Empty:
                continue
            if data is None: break
            sock = self._sock
            if sock and self._connected:
                try:
                    sock.setblocking(True)
                    sock.sendall(data)
                    sock.setblocking(False)
                except Exception as e:
                    log.warning("[CLIENT:%s] Send error: %s", self.service_name, e)

    def _handle(self, fr):
        cmd = fr.cmd
        p   = fr.payloads

        if cmd == CMD_DATA_UPDATE:
            # [0] sender  [1] dp_name  [2] value  [3] ts?
            if len(p) >= 3:
                svc = fr.p(0).str()
                dp  = fr.p(1).str()
                val = fr.p(2).value()
                val_str = str(val)
                if len(val_str) > 200:
                    val_str = val_str[:200] + "…"
                log.info("[CLIENT:%s] ← DATA_UPDATE   %s . %s = %s",
                         self.service_name, svc, dp, val_str)
                if self.receive_callback:
                    try: self.receive_callback(svc, dp, val)
                    except Exception: pass

        elif cmd == CMD_SERVICE_STATUS:
            status = fr.p(0).str()
            svc    = fr.p(1).str()
            log.info("[CLIENT:%s] ← SERVICE_%-8s '%s'", self.service_name, status, svc)

        elif cmd == CMD_RESPONSE:
            req_id = fr.p(0).rid()
            result = fr.p(1).str() if len(p) > 1 else "?"
            log.info("[CLIENT:%s] ← RESPONSE      rid=%-5d  %s",
                     self.service_name, req_id, result)

        elif cmd == CMD_CONFIG_UPDATE:
            name   = fr.p(0).str()
            value  = fr.p(1).str()
            target = fr.p(3).str() if len(p) > 3 else ""
            preview = value[:150] + ("…" if len(value) > 150 else "")
            log.info("[CLIENT:%s] ← CONFIG_UPDATE  name='%s' target='%s'\n         %s",
                     self.service_name, name, target, preview)

        elif cmd == CMD_PUBLISH_NOTIFICATION:
            msg = fr.p(5).str() if len(p) > 5 else "?"
            log.info("[CLIENT:%s] ← NOTIFICATION   '%s'", self.service_name, msg)

        else:
            log.debug("[CLIENT:%s] ← cmd=0x%04X (unhandled)", self.service_name, cmd)

# ══════════════════════════════════════════════════════════════════════════════
# DEMO LOOP  —  sends loadcell_config + live data to web_ui
# ══════════════════════════════════════════════════════════════════════════════

def _make_loadcell_config(device_name="crane_loadcell"):
    return {
        "version": 1,
        "timestamp_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "sim",
        "logging": [{"type": "console", "parameters": {"level": "info"}}],
        "ipc": [{
            "type": "pipeline",
            "enabled": True,
            "parameters": {
                "server": "127.0.0.1",
                "port": 7000,
                "service_name": "load_cell_service",
                "datapoints": [{
                    "name": device_name,
                    "map": {
                        "weight":        "{}.weight_kg".format(device_name),
                        "raw":           "{}.raw".format(device_name),
                        "unit":          "{}.unit".format(device_name),
                        "known_weight":  "{}.known_weight_kg".format(device_name),
                        "known_raw":     "{}.known_raw".format(device_name),
                        "is_tared":      "{}.tared".format(device_name),
                        "is_calibrated": "{}.calibrated".format(device_name),
                        "capacity":      "{}.capacity".format(device_name),
                    }
                }]
            }
        }],
        "load_cells": [{
            "name": device_name,
            "device": {
                "type": "sysfs_hx711",
                "parameters": {
                    "poll_ms": 10,
                    "channels": [{"path": "/sys/bus/iio/devices/iio:device0/in_voltage0_raw"}],
                    "resolution_bits": 24, "effective_bits": 14,
                    "signed": False, "gain": 1, "vref": 5,
                    "raw_min": 0, "raw_max": 16383,
                }
            },
            "specifications": {
                "capacity": {
                    "min": {"value": 0,    "unit": "kg"},
                    "max": {"value": 5000, "unit": "kg"},
                }
            },
            "levels": {"type": "ratio", "parameters": {"ratios": [
                {"name": "low",    "ratio": 0.25},
                {"name": "normal", "ratio": 0.75},
                {"name": "high",   "ratio": 0.95},
            ]}},
            "tare":        {"type": "manual",       "parameters": {"offset_raw": 0.0}},
            "calibration": {"type": "single_point", "parameters": {
                "ref_weight": {"value": 100, "unit": "kg"},
                "ref_raw":    4096.0,
            }},
            "filter": {
                "raw":    [{"type": "moving_average", "parameters": {"window": 5}}],
                "weight": [{"type": "deadband",        "parameters": {"band": 0.5}}],
            }
        }]
    }


def demo_loop(client, target, device_name="crane_loadcell"):
    """
    Sends data to `target` (your web_ui service name).

    Flow
    ----
    1. Sends loadcell_config JSON → web_ui RECEIVE_DONE fires with
         event.datapoint_name = "loadcell_config"
         event.service_name   = client.service_name
       Your updated pipeline.py then parses the JSON and saves it to the DB.

    2. Every 3 s sends live weight/raw/unit/tared/calibrated/capacity datapoints.
    3. Every 5 ticks sends a notification.
    4. Every 10 ticks re-sends the config.
    """
    log.info("[DEMO] Waiting for client to connect…")
    if not client.wait_until_connected(10):
        log.error("[DEMO] Client never connected; aborting demo loop")
        return

    log.info("[DEMO] Connected — sending to target='%s'", target)
    time.sleep(0.5)

    cfg      = _make_loadcell_config(device_name)
    cfg_json = json.dumps(cfg, indent=2)

    # Step 1: send loadcell_config
    rid = client.send(target, "loadcell_config", cfg_json)
    log.info("[DEMO] Sent loadcell_config  rid=%d  (%d bytes)", rid, len(cfg_json))

    tick = 0
    while client._running:
        time.sleep(3)
        tick += 1
        if not client.connected:
            continue

        weight = round(1234.5 + (tick % 20) * 17.3, 2)
        raw    = 4096 + (tick % 50) * 80

        # Step 2: live datapoints
        dp = device_name
        client.send(target, "{}.weight_kg".format(dp),  float(weight))
        client.send(target, "{}.raw".format(dp),        int(raw))
        client.send(target, "{}.unit".format(dp),       "kg")
        client.send(target, "{}.tared".format(dp),      tick > 1)
        client.send(target, "{}.calibrated".format(dp), True)
        client.send(target, "{}.capacity".format(dp),   5000.0)

        log.info("[DEMO] tick=%-3d  weight=%.2f kg  raw=%d", tick, weight, raw)

        # Step 3: notification every 5 ticks
        if tick % 5 == 0:
            notif = frm_notification(1, 2, 0,
                                     client.service_name, dp,
                                     "Weight {:.2f} kg".format(weight))
            client.send_raw_frame(notif)

        # Step 4: re-send config every 10 ticks
        if tick % 10 == 0:
            rid = client.send(target, "loadcell_config", cfg_json)
            log.info("[DEMO] Re-sent loadcell_config  rid=%d", rid)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="ilx_pipeline simulator (server + client)")
    ap.add_argument("--host",        default="127.0.0.1",
                    help="Host to bind/connect (default 127.0.0.1)")
    ap.add_argument("--port",        default=7000, type=int,
                    help="Port (default 7000)")
    ap.add_argument("--service",     default="load_cell_service",
                    help="Service name this sim client registers as")
    ap.add_argument("--target",      default="web_ui",
                    help="Target service to send data to (your web_ui)")
    ap.add_argument("--device",      default="crane_loadcell",
                    help="Loadcell device name inside the config JSON")
    ap.add_argument("--server-only", action="store_true",
                    help="Run the TCP hub only, no built-in client")
    ap.add_argument("--client-only", action="store_true",
                    help="Run the sim client only (connect to existing server)")
    ap.add_argument("--no-demo",     action="store_true",
                    help="Start client but skip the demo data loop")
    ap.add_argument("--debug",       action="store_true",
                    help="Enable DEBUG log level")
    args = ap.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    server = client = None

    try:
        if not args.client_only:
            server = PipelineServer(host=args.host, port=args.port)
            server.start()
            time.sleep(0.3)   # let the socket bind

        if not args.server_only:
            client = SimClient(
                service_name=args.service,
                host=args.host,
                port=args.port,
            )
            client.start()

            if not args.no_demo:
                threading.Thread(
                    target=demo_loop,
                    args=(client, args.target, args.device),
                    daemon=True,
                    name="DemoLoop",
                ).start()

        log.info("[MAIN] Running — press Ctrl+C to stop")
        log.info("[MAIN] Port=%-5d  Service='%s'  Target='%s'  Device='%s'",
                 args.port, args.service, args.target, args.device)

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        log.info("[MAIN] Interrupted")
    finally:
        if client: client.stop()
        if server: server.stop()
        log.info("[MAIN] Done")


if __name__ == "__main__":
    main()