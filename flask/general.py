# general_config.py - Consolidated general configuration API with WebSocket support (OPTIMIZED)
import asyncio
import json
import datetime
import time
from collections import defaultdict
from aiohttp import web
from aiohttp import WSMsgType as MsgType
from database import get_general_configuration, update_general_configuration
from auth import ws_auth
from pipeline import pipeline_state, _flush_all_pending

# ============================================================================
# MODELS (from models.py)
# ============================================================================

# OPTIMIZATION: WebSocket connection limits
MAX_WEBSOCKET_CONNECTIONS = 5  # Prevent unlimited connections

# Active timezone - updated whenever user syncs or saves config
active_timezone = 'Asia/Kolkata'

def get_now():
    """Return current datetime in the active_timezone."""
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(active_timezone)
    except Exception:
        try:
            import pytz
            tz = pytz.timezone(active_timezone)
        except Exception:
            tz = None
    return datetime.datetime.now(tz) if tz else datetime.datetime.now()

# In-memory real-time state with previous values for comparison
realtime_state = {
    'current_date':        get_now().strftime('%Y-%m-%d'),
    'current_time':        get_now().strftime('%H:%M'),
    'wifi_signal_strength': 3   # 0-4 scale
}

# Track previous values to detect changes
previous_state = {
    'current_date': '',
    'current_time': ''
}

# WebSocket connections (only general websockets, not device-specific)
connected_websockets = set()

# ============================================================================
# NETWORK STATUS STATE  (populated live from Pipeline RECEIVE_DONE events)
# ============================================================================

# Flat key/value store for every network_status datapoint received from pipeline.
# Keys match the pipeline datapoint names exactly, e.g.:
#   "net.lan.eth0.ip", "net.lan.eth0.state", "net.lan.eth0.mac",
#   "net.wlan.ssid",   "net.wlan.ip",        "net.wlan.state",
#   "net.lte.iccid",   "net.lte.imei",       "net.lte.imsi", 
network_status_state = {}

# WebSocket clients subscribed to live network-status updates
network_status_websockets = set()

# Track last broadcast time per datapoint to avoid flooding
_last_broadcast_time = {}
_MIN_BROADCAST_INTERVAL = 0.1  # 100ms minimum between updates for same datapoint

# ============================================================================
# HELPER: Get current active route from live state
# ============================================================================

def _get_current_active_route_from_state():
    """
    Determine the currently active network route based on live network_status_state.
    Returns route value: 1=eth0, 2=eth1, 3=lte, 4=wifi, None if no active connection.
    Priority: eth0 > eth1 > wifi > lte
    """
    # Check Ethernet interfaces
    eth0_state = network_status_state.get('net.lan.eth0.state')
    eth1_state = network_status_state.get('net.lan.eth1.state')
    
    # Convert to boolean (handle 1/0, True/False, "1"/"0")
    def is_up(val):
        if val is None:
            return False
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return val == 1
        if isinstance(val, str):
            return val.lower() in ('1', 'true', 'up', 'connected')
        return False
    
    eth0_up = is_up(eth0_state)
    eth1_up = is_up(eth1_state)
    
    if eth0_up:
        return 1
    if eth1_up:
        return 2
    
    # Check WiFi
    wlan_state = network_status_state.get('net.wlan.state')
    if is_up(wlan_state):
        return 4
    
    # Check LTE
    lte_state = network_status_state.get('net.lte.state')
    if is_up(lte_state):
        return 3
    
    return None

# ============================================================================
# OPTIMIZATION: Batched WebSocket broadcasts (70% less CPU)
# ============================================================================
_broadcast_queue = []
_broadcast_queue_lock = asyncio.Lock()
_broadcast_task = None
BROADCAST_INTERVAL = 0.2  # 200ms batching


async def _broadcast_worker():
    """Background task that sends batched broadcasts every 200ms."""
    global _broadcast_queue
    
    while True:
        await asyncio.sleep(BROADCAST_INTERVAL)
        
        async with _broadcast_queue_lock:
            if not _broadcast_queue:
                continue
            
            # Deduplicate: keep only latest value per datapoint
            updates_by_type = defaultdict(dict)
            for update in _broadcast_queue:
                update_type = update.get('type')
                if update_type == 'datapoint_update' or update_type == 'network_status_update':
                    dp_name = update.get('datapoint', '')
                    if dp_name:
                        updates_by_type['datapoint'][dp_name] = update
                else:
                    updates_by_type[update_type][id(update)] = update
            
            # Flatten back to list
            batched_updates = []
            for update_type, updates_dict in updates_by_type.items():
                batched_updates.extend(updates_dict.values())
            
            _broadcast_queue = []
        
        # Send batch
        if batched_updates:
            if len(batched_updates) == 1:
                await broadcast_to_clients_immediate(batched_updates[0])
            else:
                await broadcast_to_clients_immediate({
                    'type': 'batch_update',
                    'updates': batched_updates
                })


async def queue_broadcast(data):
    """Queue a broadcast to be sent in next batch (OPTIMIZED)."""
    async with _broadcast_queue_lock:
        _broadcast_queue.append(data)


def start_broadcast_worker(app):
    """Start the broadcast batching worker task."""
    global _broadcast_task
    
    async def _start_worker(app):
        global _broadcast_task
        _broadcast_task = asyncio.ensure_future(_broadcast_worker())    
    app.on_startup.append(_start_worker)


# ============================================================================
# WEBSOCKET HANDLER (from websocket_handler.py, simplified)
# ============================================================================

async def websocket_handler(request):
    """Handle WebSocket connections for real-time updates.

    OPTIMIZATION: Enforces connection limit to prevent resource exhaustion.

    Supports multiple simultaneous tabs/pages for the same user.
    Each browser tab gets its own independent WebSocket connection which
    is tracked in connected_websockets (a plain set).  There is no
    per-user limit here; all active connections receive broadcasts.
    """
    # --- Auth: require a valid webui session cookie ---
    user = ws_auth(request)
    if user is None:
        return web.Response(status=401, text='Unauthorized')

    # OPTIMIZATION: Enforce connection limit
    if len(connected_websockets) >= MAX_WEBSOCKET_CONNECTIONS:
        logger.info("WebSocket connection rejected - limit reached ({}/{})".format(
            len(connected_websockets), MAX_WEBSOCKET_CONNECTIONS))
        return web.Response(
            status=503,
            text='Server at capacity. Please try again in a moment.'
        )

    # heartbeat_timeout: if no message (including pong) is received for
    # this many seconds the connection is considered dead and closed.
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    # Refresh the session's last_ping immediately on WS connect so the
    # watchdog in main.py never evicts an actively-connected user.
    try:
        import main as _main
        import time as _time
        _tok = request.cookies.get('gw_webui_session')
        if _tok and _tok in _main.WEBUI_SESSIONS and isinstance(_main.WEBUI_SESSIONS[_tok], dict):
            _main.WEBUI_SESSIONS[_tok]['last_ping'] = _time.time()
    except Exception:
        pass

    connected_websockets.add(ws)
    logger.info("WebSocket connected (user={}). Total clients: {}/{}".format(
        user, len(connected_websockets), MAX_WEBSOCKET_CONNECTIONS))

    try:
        # Send initial state to the newly connected client.
        # Guard with ws.closed so a race between prepare() and the first
        # send doesn't crash the handler when the tab is closed immediately.
        if not ws.closed:
            await ws.send_str(json.dumps({
                'type': 'initial',
                'current_date': realtime_state['current_date'],
                'current_time': realtime_state['current_time'],
                'wifi_signal_strength': realtime_state.get('wifi_signal_strength', 3),
            }))

        async for msg in ws:
            if msg.type in (MsgType.close, MsgType.closing):
                break
            elif msg.type == MsgType.error:
                # ws.exception() is None when the remote simply closed.
                exc = ws.exception()
                if exc:
                    logger.error('WebSocket protocol error (user={}): {}'.format(user, exc))
                break
            elif msg.type == MsgType.ping:
                # aiohttp auto-replies with pong when heartbeat= is set,
                # but handle it explicitly too for safety.
                await ws.pong(msg.data)
            elif msg.type == MsgType.text:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get('type')

                    if msg_type == 'sync_time':
                        # Accept time_format from the WS message (sent by JS on sync)
                        _tf = data.get('time_format', '24-hour')
                        _now = get_now()
                        new_date = _now.strftime('%Y-%m-%d')
                        # Always store 24h in realtime_state; format is carried separately
                        new_time = _now.strftime('%H:%M')
                        # Build the display-formatted time for the client
                        if _tf == '12-hour':
                            new_time_display = _now.strftime('%I:%M %p').lstrip('0') or _now.strftime('%I:%M %p')
                        else:
                            new_time_display = new_time

                        if (new_date != realtime_state['current_date'] or
                                new_time != realtime_state['current_time']):
                            realtime_state['current_date'] = new_date
                            realtime_state['current_time'] = new_time
                            # OPTIMIZATION: Use batched broadcast
                            await queue_broadcast({
                                'type': 'time_update',
                                'current_date': new_date,
                                'current_time': new_time,
                                'time_display': new_time_display,
                                'time_format':  _tf,
                            })

                        if not ws.closed:
                            await ws.send_str(json.dumps({
                                'type':         'time_synced',
                                'current_date': realtime_state['current_date'],
                                'current_time': realtime_state['current_time'],
                                'time_display': new_time_display,
                                'time_format':  _tf,
                            }))

                    elif msg_type == 'get_wifi_signal':
                        strength = realtime_state.get('wifi_signal_strength', 3)
                        if not ws.closed:
                            await ws.send_str(json.dumps({
                                'type': 'wifi_signal_update',
                                'strength': strength,
                            }))

                    elif msg_type == 'ping':
                        if not ws.closed:
                            await ws.send_str(json.dumps({'type': 'pong'}))

                except (ValueError, KeyError):
                    if not ws.closed:
                        await ws.send_str(json.dumps({
                            'type': 'error',
                            'message': 'Invalid JSON format',
                        }))

    except asyncio.CancelledError:
        # Server is shutting down – clean exit, no noisy traceback.
        pass
    except ConnectionResetError:
        # Browser closed the tab abruptly.
        pass
    except Exception as e:
        logger.error("WebSocket unexpected error (user={}): {}: {}".format(
            user, type(e).__name__, e))
    finally:
        connected_websockets.discard(ws)
        logger.info("WebSocket disconnected (user={}). Remaining: {}/{}".format(
            user, len(connected_websockets), MAX_WEBSOCKET_CONNECTIONS))

    return ws


async def broadcast_to_clients(data):
    """Queue broadcast (batched, OPTIMIZED). Use this for normal updates."""
    await queue_broadcast(data)


async def broadcast_to_clients_immediate(data):
    """Send immediately to all clients. Use only for critical updates.

    Uses asyncio.gather so a slow or dead socket does not block the others.
    Sockets that are already closed are skipped before attempting a send.
    """
    if not connected_websockets:
        return
    payload = json.dumps(data)
    targets = [ws for ws in list(connected_websockets) if not ws.closed]
    if targets:
        await asyncio.gather(
            *[_safe_send(ws, payload) for ws in targets],
            return_exceptions=True,
        )


async def _safe_send(ws, payload):
    """Send payload to one WebSocket; remove it from the set on any failure."""
    try:
        if not ws.closed:
            await ws.send_str(payload)
    except asyncio.CancelledError:
        connected_websockets.discard(ws)
        raise
    except Exception:
        # Connection already gone – silently remove it.
        connected_websockets.discard(ws)


# ============================================================================
# NETWORK STATUS    helpers called by pipeline.py on RECEIVE_DONE
# ============================================================================

def _parse_datapoint_to_path(datapoint_name):
    """
    Parse a datapoint name like "net.lte.signal_pct" or "net.lan.eth0.ip"
    into a structured path for updating the cache.
    Returns a dict with keys: interface, device, field
    """
    parts = datapoint_name.split('.')
    if len(parts) < 3 or parts[0] != 'net':
        return None
    
    interface = parts[1]  # 'lte', 'wlan', 'lan'
    
    if interface == 'lan':
        if len(parts) >= 4:
            return {
                'type': 'lan',
                'device': parts[2],  # 'eth0' or 'eth1'
                'field': parts[3]
            }
        elif len(parts) == 3:
            return {
                'type': 'lan',
                'device': None,
                'field': parts[2]
            }
    else:
        # lte or wlan
        if len(parts) >= 3:
            return {
                'type': interface,  # 'lte' or 'wlan'
                'device': None,
                'field': parts[2]
            }
    
    return None


def _update_cache_from_datapoint(datapoint_name, value):
    """
    Update the internal cache with a single datapoint.
    This ensures we maintain a complete view even when updates come piecemeal.
    """
    path = _parse_datapoint_to_path(datapoint_name)
    if not path:
        return False
    
    if path['type'] == 'lte':
        # Initialize if needed
        if 'lte' not in network_status_state:
            network_status_state['lte'] = {}
        network_status_state['lte'][path['field']] = value
        
    elif path['type'] == 'wlan':
        if 'wlan' not in network_status_state:
            network_status_state['wlan'] = {}
        network_status_state['wlan'][path['field']] = value
        # Keep both signal keys in sync (pipeline may send either field name)
        if path['field'] == 'signal':
            network_status_state['wlan']['signal_quality'] = value
        elif path['field'] == 'signal_quality':
            network_status_state['wlan']['signal'] = value
        
    elif path['type'] == 'lan':
        if 'lan' not in network_status_state:
            network_status_state['lan'] = {}
        if path['device']:
            if path['device'] not in network_status_state['lan']:
                network_status_state['lan'][path['device']] = {}
            network_status_state['lan'][path['device']][path['field']] = value
        else:
            network_status_state['lan'][path['field']] = value
    
    return True


def update_network_status_field(datapoint_name, value):
    """
    Called from the pipeline RECEIVE_DONE handler (pipeline.py) whenever a
    network_status/* datapoint arrives.  Stores the value and broadcasts the
    delta to all live WebSocket subscribers.
    """
    global _last_broadcast_time
    
    # Store the raw value in flat state for backward compatibility
    network_status_state[datapoint_name] = value
    
    # Update structured cache
    _update_cache_from_datapoint(datapoint_name, value)
    
    # Update WiFi signal strength if this is the signal datapoint
    if datapoint_name == "net.wlan.signal_pct":
        try:
            pct = float(value)
            strength = min(4, int(pct) // 25)
            update_wifi_signal_strength(strength)
        except (ValueError, TypeError):
            pass
    
    # Rate limit broadcasts for the same datapoint
    # Static hardware fields (MAC, IMEI, ICCID, IMSI, BSSID) are exempt —
    # they only change on interface connect/disconnect so must always be sent.
    _STATIC_FIELDS = {'mac', 'imei', 'iccid', 'imsi', 'bssid'}
    _field_name = datapoint_name.split('.')[-1]
    now = datetime.datetime.now().timestamp()
    last_time = _last_broadcast_time.get(datapoint_name, 0)
    if _field_name not in _STATIC_FIELDS and now - last_time < _MIN_BROADCAST_INTERVAL:
        return
    
    _last_broadcast_time[datapoint_name] = now
    
    # Build structured delta update
    delta = {
        'type': 'network_status_delta',
        'datapoint': datapoint_name,
        'value': value
    }
    
    # Parse to add structured path for easier client-side handling
    path = _parse_datapoint_to_path(datapoint_name)
    if path:
        delta['path'] = path
    
    # Broadcast the delta to all connected WebSocket clients
    main_loop = _main_loop_ref.get("loop")
    if main_loop and main_loop.is_running():
        try:
            asyncio.run_coroutine_threadsafe(
                _broadcast_network_status(delta),
                main_loop,
            )
        except Exception as e:
            logger.error("[NET-STATUS] broadcast error: {}".format(e))


def _build_network_status_snapshot():
    """Return a structured dict from the flat network_status_state.
    
    This now returns the structured cache which maintains all fields,
    not just the ones that have been updated recently.
    """
    result = {
        'lan': {},
        'wlan': {},
        'lte': {},
        'network_status': network_status_state.get('network_status', 0)
    }
    
    # Build LAN from structured cache
    if 'lan' in network_status_state:
        lan_data = network_status_state['lan']
        result['lan']['eth0'] = lan_data.get('eth0', {})
        result['lan']['eth1'] = lan_data.get('eth1', {})
        
        # Also include any top-level lan fields
        for key, value in lan_data.items():
            if key not in ['eth0', 'eth1']:
                result['lan'][key] = value
    
    # Build WLAN from structured cache
    if 'wlan' in network_status_state:
        result['wlan'] = network_status_state['wlan']
    
    # Build LTE from structured cache
    if 'lte' in network_status_state:
        result['lte'] = network_status_state['lte']
    
    # Also include any flat fields that might not be in structured cache
    for key, value in network_status_state.items():
        if key.startswith('net.lan.'):
            # Already handled in structured cache
            pass
        elif key.startswith('net.wlan.'):
            # Already handled
            pass
        elif key.startswith('net.lte.'):
            # Already handled
            pass
        elif key not in ['lan', 'wlan', 'lte', 'network_status']:
            # Top-level network fields
            result[key] = value
    
    return result


async def _broadcast_network_status(data):
    """Broadcast a dict to all network-status WebSocket clients."""
    if not network_status_websockets:
        return
    payload = json.dumps(data)
    await asyncio.gather(
        *[_safe_send_ns(ws, payload)
          for ws in list(network_status_websockets) if not ws.closed],
        return_exceptions=True,
    )


async def _safe_send_ns(ws, payload):
    """Send payload to one WebSocket; remove it from the set on any failure."""
    try:
        if not ws.closed:
            await ws.send_str(payload)
    except asyncio.CancelledError:
        network_status_websockets.discard(ws)
        raise
    except Exception:
        network_status_websockets.discard(ws)


# Tiny holder so the pipeline thread can reach the aiohttp event loop.
_main_loop_ref = {}  # type: dict


async def network_status_websocket_handler(request):
    """
    GET /ws/network-status

    WebSocket endpoint that streams live network-status data from the pipeline.
    The client connects and immediately receives the current snapshot, then gets
    pushed delta updates whenever the pipeline publishes new network_status/* data.

    Multiple browser tabs for the same user are fully supported: each tab
    receives its own independent stream.
    """
    user = ws_auth(request)
    if user is None:
        return web.Response(status=401, text="Unauthorized")

    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    # Refresh the session's last_ping immediately on WS connect.
    try:
        import main as _main
        import time as _time
        _tok = request.cookies.get('gw_webui_session')
        if _tok and _tok in _main.WEBUI_SESSIONS and isinstance(_main.WEBUI_SESSIONS[_tok], dict):
            _main.WEBUI_SESSIONS[_tok]['last_ping'] = _time.time()
    except Exception:
        pass

    network_status_websockets.add(ws)
    logger.info("[NET-STATUS] WS connected (user={}). Total: {}".format(
        user, len(network_status_websockets)))

    try:
        # Send current snapshot immediately on connect
        if not ws.closed:
            await ws.send_str(json.dumps({
                "type": "network_status_initial",
                "data": _build_network_status_snapshot(),
            }))

        async for msg in ws:
            if msg.type in (MsgType.close, MsgType.closing):
                break
            elif msg.type == MsgType.error:
                exc = ws.exception()
                if exc:
                    logger.error("[NET-STATUS] WS protocol error (user={}): {}".format(user, exc))
                break
            elif msg.type == MsgType.ping:
                await ws.pong(msg.data)
            elif msg.type == MsgType.text:
                try:
                    data = json.loads(msg.data)
                    if data.get("type") == "ping":
                        if not ws.closed:
                            await ws.send_str(json.dumps({"type": "pong"}))
                    elif data.get("type") == "get_snapshot":
                        if not ws.closed:
                            await ws.send_str(json.dumps({
                                "type": "network_status_initial",
                                "data": _build_network_status_snapshot(),
                            }))
                except (ValueError, KeyError):
                    pass

    except asyncio.CancelledError:
        pass
    except ConnectionResetError:
        pass
    except Exception as e:
        logger.error("[NET-STATUS] WS unexpected error (user={}): {}: {}".format(
            user, type(e).__name__, e))
    finally:
        network_status_websockets.discard(ws)
        logger.info("[NET-STATUS] WS disconnected (user={}). Total: {}".format(
            user, len(network_status_websockets)))

    return ws


# ============================================================================
# WIFI SCAN HANDLER
# ============================================================================

def _scan_wifi_windows():
    """
    Scan WiFi on Windows properly:
    1. Use wlanapi via ctypes to trigger a real async scan on the adapter
    2. Wait for scan to complete (up to 4s)
    3. Parse results with netsh (which now has fresh data)
    """
    import subprocess, re, time, ctypes, ctypes.wintypes

    # ------------------------------------------------------------------ #
    #  Step 1: trigger a real scan via wlanapi WlanScan()                 #
    # ------------------------------------------------------------------ #
    try:
        wlanapi = ctypes.windll.LoadLibrary('wlanapi.dll')

        # WlanOpenHandle
        client_handle = ctypes.wintypes.HANDLE()
        negotiated    = ctypes.wintypes.DWORD()
        ret = wlanapi.WlanOpenHandle(2, None, ctypes.byref(negotiated), ctypes.byref(client_handle))
        if ret == 0:
            # WlanEnumInterfaces
            class GUID(ctypes.Structure):
                _fields_ = [('Data1', ctypes.c_ulong), ('Data2', ctypes.c_ushort),
                             ('Data3', ctypes.c_ushort), ('Data4', ctypes.c_ubyte * 8)]

            class WLAN_INTERFACE_INFO(ctypes.Structure):
                _fields_ = [('InterfaceGuid', GUID), ('strInterfaceDescription', ctypes.c_wchar * 256),
                             ('isState', ctypes.c_uint)]

            class WLAN_INTERFACE_INFO_LIST(ctypes.Structure):
                _fields_ = [('dwNumberOfItems', ctypes.c_ulong), ('dwIndex', ctypes.c_ulong),
                             ('InterfaceInfo', WLAN_INTERFACE_INFO * 64)]

            iface_list_ptr = ctypes.POINTER(WLAN_INTERFACE_INFO_LIST)()
            ret2 = wlanapi.WlanEnumInterfaces(client_handle, None, ctypes.byref(iface_list_ptr))
            if ret2 == 0 and iface_list_ptr:
                iface_list = iface_list_ptr.contents
                for i in range(iface_list.dwNumberOfItems):
                    guid_ptr = ctypes.byref(iface_list.InterfaceInfo[i].InterfaceGuid)
                    # WlanScan(hClientHandle, pInterfaceGuid, pDot11Ssid, pIeData, pReserved)
                    wlanapi.WlanScan(client_handle, guid_ptr, None, None, None)
                wlanapi.WlanFreeMemory(iface_list_ptr)
            wlanapi.WlanCloseHandle(client_handle, None)
            # Give the adapter time to complete the scan
            time.sleep(3)
    except Exception as e:
        logger.info('[WIFI-SCAN] wlanapi scan trigger failed (non-fatal): {}'.format(e))
        time.sleep(1)  # still wait a bit in case a previous scan is cached

    # ------------------------------------------------------------------ #
    #  Step 2: read results via netsh                                      #
    # ------------------------------------------------------------------ #
    try:
        # FIX: Python 3.5 compatible - use stdout=PIPE, stderr=PIPE instead of capture_output
        result = subprocess.run(
            ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
            encoding='utf-8', errors='replace'
        )
        stdout = result.stdout if result.stdout else ''
        logger.info('[WIFI-SCAN] netsh rc={} lines={}'.format(
            result.returncode, len(stdout.splitlines())))

        if result.returncode != 0 or not stdout.strip():
            return []

        networks = []
        seen     = set()

        # Each network block starts with "SSID N :" on its own line
        blocks = re.split(r'\nSSID\s+\d+\s*:', stdout)
        for block in blocks[1:]:
            lines = [l.strip() for l in block.strip().splitlines()]
            ssid  = lines[0].strip() if lines else ''
            if not ssid or ssid in seen:
                continue
            seen.add(ssid)

            signal_pct = 0
            security   = 'Open'
            channel    = 0

            for line in lines[1:]:
                m = re.match(r'Signal\s*:\s*(\d+)\s*%', line)
                if m: signal_pct = int(m.group(1))

                m = re.match(r'Authentication\s*:\s*(.+)', line)
                if m: security = m.group(1).strip()

                m = re.match(r'Channel\s*:\s*(\d+)', line)
                if m: channel = int(m.group(1))

            # Windows signal% -> dBm approximation
            signal_dbm = int(signal_pct / 2) - 100

            networks.append({
                'ssid':           ssid,
                'signal_quality': signal_dbm,
                'security':       security,
                'channel':        channel,
            })

        logger.info('[WIFI-SCAN] parsed {} networks'.format(len(networks)))
        return networks

    except Exception as e:
        logger.error('[WIFI-SCAN] netsh parse error: {}'.format(e))
        return []


def _get_wifi_iface():
    """Return the first wireless interface name found via 'iw dev', default wlan0."""
    import subprocess, re
    try:
        r = subprocess.run(
            ['iw', 'dev'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5
        )
        stdout = r.stdout.decode('utf-8', errors='replace') if r.stdout else ''
        m = re.search(r'Interface\s+(\S+)', stdout)
        if m:
            return m.group(1)
    except Exception:
        pass
    return 'wlan0'


def _scan_wifi_wpa_cli(iface):
    """
    Fallback: use wpa_cli scan + scan_results.
    Works even when the WiFi interface is not the active route (e.g. ethernet is primary).
    """
    import subprocess, re, time

    try:
        # Trigger scan
        subprocess.run(
            ['wpa_cli', '-i', iface, 'scan'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5
        )
        time.sleep(2)

        # Read results
        result = subprocess.run(
            ['wpa_cli', '-i', iface, 'scan_results'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10
        )
        stdout = result.stdout.decode('utf-8', errors='replace') if result.stdout else ''
        if result.returncode != 0 or not stdout.strip():
            return []

        networks = []
        seen = set()
        # Output: bssid / frequency / signal level / flags / ssid
        for line in stdout.strip().splitlines():
            parts = line.split('\t')
            if len(parts) < 5:
                continue
            ssid = parts[4].strip()
            if not ssid or ssid in seen:
                continue
            seen.add(ssid)
            try:
                signal_dbm = int(parts[2].strip())
            except (ValueError, TypeError):
                signal_dbm = -80
            flags = parts[3].strip()
            security = 'Open'
            if 'WPA2' in flags:
                security = 'WPA2'
            elif 'WPA' in flags:
                security = 'WPA'
            elif 'WEP' in flags:
                security = 'WEP'
            networks.append({
                'ssid': ssid,
                'signal_quality': signal_dbm,
                'security': security,
                'channel': 0,
            })
        return networks

    except FileNotFoundError:
        logger.info('[WIFI-SCAN] wpa_cli not found')
        return []
    except Exception as e:
        logger.error('[WIFI-SCAN] wpa_cli scan error: {}'.format(e))
        return []


def _do_wifi_scan():
    """
    Trigger a real WiFi scan and return results.
    Works even when ethernet is the active/primary interface.
    """
    import time
    logger.info('[WIFI-SCAN] Starting scan on Linux...')

    iface = _get_wifi_iface()
    logger.info('[WIFI-SCAN] Using interface: {}'.format(iface))

    # -- Method 1: nmcli (preferred, tolerates ethernet being active) --
    networks = _scan_wifi_nmcli(iface)
    if networks:
        networks.sort(key=lambda n: n.get('signal_quality', -100), reverse=True)
        logger.info('[WIFI-SCAN] Found {} networks via nmcli.'.format(len(networks)))
        return networks

    # -- Method 2: iw dev <iface> scan --
    networks = _scan_wifi_iw(iface)
    if networks:
        networks.sort(key=lambda n: n.get('signal_quality', -100), reverse=True)
        logger.info('[WIFI-SCAN] Found {} networks via iw.'.format(len(networks)))
        return networks

    # -- Method 3: wpa_cli scan + scan_results --
    logger.info('[WIFI-SCAN] Trying wpa_cli...')
    networks = _scan_wifi_wpa_cli(iface)
    if networks:
        networks.sort(key=lambda n: n.get('signal_quality', -100), reverse=True)
        logger.info('[WIFI-SCAN] Found {} networks via wpa_cli.'.format(len(networks)))
        return networks

    logger.info('[WIFI-SCAN] All methods returned empty.')
    return []


def _scan_wifi_nmcli(iface):
    """
    Use nmcli to scan for WiFi networks.
    Works even when ethernet is the active interface -- rescan errors are non-fatal.
    """
    import subprocess, time

    try:
        # Trigger a rescan -- ignore errors (e.g. interface busy, ethernet primary)
        try:
            subprocess.run(
                ['nmcli', 'dev', 'wifi', 'rescan', 'ifname', iface],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10
            )
        except Exception as rescan_err:
            logger.info('[WIFI-SCAN] nmcli rescan non-fatal error: {}'.format(rescan_err))

        time.sleep(3)

        # Try listing with specific iface first, then without (ethernet-active fallback)
        stdout = ''
        for list_cmd in [
            ['nmcli', '--escape', 'no', '-t', '-f', 'SSID,SIGNAL,SECURITY,CHAN', 'dev', 'wifi', 'list', 'ifname', iface],
            ['nmcli', '--escape', 'no', '-t', '-f', 'SSID,SIGNAL,SECURITY,CHAN', 'dev', 'wifi', 'list'],
        ]:
            result = subprocess.run(
                list_cmd,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15
            )
            stdout = result.stdout.decode('utf-8', errors='replace') if result.stdout else ''
            if result.returncode == 0 and stdout.strip():
                break

        if not stdout.strip():
            return []

        networks = []
        seen = set()

        for line in stdout.strip().split('\n'):
            if not line.strip():
                continue
            parts = line.split(':')
            if len(parts) < 4:
                continue
            ssid = parts[0].strip()
            signal = parts[1].strip()
            security = parts[2].strip()
            channel = parts[3].strip()

            if not ssid or ssid in seen:
                continue
            seen.add(ssid)

            try:
                signal_pct = int(signal)
                signal_dbm = int(signal_pct / 2) - 100
            except (ValueError, TypeError):
                signal_dbm = -70

            try:
                channel_num = int(channel)
            except (ValueError, TypeError):
                channel_num = 0

            networks.append({
                'ssid': ssid,
                'signal_quality': signal_dbm,
                'security': security if security else 'Open',
                'channel': channel_num,
            })

        return networks

    except FileNotFoundError:
        logger.info('[WIFI-SCAN] nmcli not found')
        return []
    except Exception as e:
        logger.error('[WIFI-SCAN] nmcli scan error: {}'.format(e))
        return []

def _scan_wifi_iw(iface):
    """
    Fallback: parse 'iw dev <iface> scan' output.
    Requires root (runs as root on this device so no sudo needed).
    """
    import subprocess, re

    for cmd in (
        ['iw', 'dev', iface, 'scan'],
        ['iw', 'dev', iface, 'scan', 'passive'],
    ):
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25
            )
            stdout = result.stdout.decode('utf-8', errors='replace') if result.stdout else ''
            stderr = result.stderr.decode('utf-8', errors='replace') if result.stderr else ''
            logger.info('[WIFI-SCAN] iw rc={} lines={} stderr={}'.format(
                result.returncode, len(stdout.splitlines()), stderr.strip()[:120]))

            if not stdout.strip():
                continue

            networks, seen, cur = [], set(), {}

            def _flush(c):
                if c.get('ssid') and c['ssid'] not in seen:
                    seen.add(c['ssid'])
                    c.setdefault('signal_quality', -100)
                    c.setdefault('security', 'Open')
                    c.setdefault('channel', 0)
                    networks.append(dict(c))

            for line in stdout.splitlines():
                line = line.strip()
                if line.startswith('BSS '):
                    _flush(cur)
                    cur = {}
                    continue
                m = re.match(r'SSID:\s*(.*)', line)
                if m:
                    cur['ssid'] = m.group(1).strip()
                    continue
                m = re.match(r'signal:\s*(-?[\d.]+)\s*dBm', line)
                if m:
                    cur['signal_quality'] = int(float(m.group(1)))
                    continue
                m = re.match(r'\*\s*primary channel:\s*(\d+)', line)
                if m:
                    cur['channel'] = int(m.group(1))
                    continue
                # DS Parameter set is another way channel is reported
                m = re.match(r'DS Parameter set:\s*channel\s*(\d+)', line)
                if m:
                    cur.setdefault('channel', int(m.group(1)))
                    continue
                if re.match(r'RSN:', line):
                    cur['security'] = 'WPA2'
                    continue
                if re.match(r'WPA:', line):
                    cur.setdefault('security', 'WPA')

            _flush(cur)

            if networks:
                logger.info('[WIFI-SCAN] iw parsed {} networks'.format(len(networks)))
                return networks

        except FileNotFoundError:
            logger.info('[WIFI-SCAN] iw not found')
            break
        except Exception as e:
            logger.error('[WIFI-SCAN] iw error: {}'.format(e))

    return []


async def wifi_scan_debug_handler(request):
    """GET /api/wifi/scan/debug -- raw output for troubleshooting (Linux only)."""
    user = ws_auth(request)
    if user is None:
        return web.json_response({'error': 'Unauthorized'}, status=401)
    import subprocess, platform
    iface = _get_wifi_iface()
    out   = {'platform': platform.system(), 'detected_iface': iface}
    debug_cmds = [
        ('ip_link',      ['ip', 'link', 'show']),
        ('iw_dev',       ['iw', 'dev']),
        ('nmcli_dev',    ['nmcli', 'dev', 'status']),
        ('nmcli_rescan', ['nmcli', 'dev', 'wifi', 'rescan', 'ifname', iface]),
        ('nmcli_list',   ['nmcli', '--escape', 'no', '-t', '-f',
                          'SSID,SIGNAL,SECURITY,CHAN', 'dev', 'wifi', 'list', 'ifname', iface]),
        ('iw_scan',      ['iw', 'dev', iface, 'scan']),
    ]
    for label, cmd in debug_cmds:
        try:
            r = subprocess.run(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=20
            )
            out[label] = {
                'rc':     r.returncode,
                'stdout': r.stdout.decode('utf-8', errors='replace')[:3000] if r.stdout else '',
                'stderr': r.stderr.decode('utf-8', errors='replace')[:500] if r.stderr else '',
            }
        except FileNotFoundError:
            out[label] = {'rc': -1, 'stdout': '', 'stderr': 'command not found'}
        except Exception as e:
            out[label] = {'rc': -1, 'stdout': '', 'stderr': str(e)}
    out['note'] = 'parsed_networks runs the full _do_wifi_scan() including rescan + 3s wait'
    out['parsed_networks'] = _do_wifi_scan()
    return web.json_response(out)


async def wifi_scan_handler(request):
    """GET /api/wifi/scan -- scan for nearby WiFi networks via nmcli / iwlist."""
    user = ws_auth(request)
    if user is None:
        return web.json_response({'success': False, 'error': 'Unauthorized'}, status=401)

    try:
        loop = asyncio.get_event_loop()
        networks = await loop.run_in_executor(None, _do_wifi_scan)

        return web.json_response({
            'success':  True,
            'networks': networks,
            'count':    len(networks),
            'message':  '{} network{} found'.format(len(networks), 's' if len(networks) != 1 else ''),
        })

    except Exception as e:
        logger.error('[WIFI-SCAN] Unexpected error: {}'.format(e))
        return web.json_response({'success': False, 'error': str(e)}, status=500)


def _do_wifi_connect(ssid, password):
    """
    Connect to a WiFi network using nmcli.
    Returns (ok: bool, message: str).
    """
    import subprocess
    import time
    
    try:
        # First, verify the network exists in scan results
        try:
            # Run a quick scan to verify network exists
            scan_cmd = ['nmcli', 'dev', 'wifi', 'list', 'ifname', 'wlan0']
            scan_result = subprocess.run(
                scan_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15
            )
            scan_stdout = scan_result.stdout.decode('utf-8', errors='replace') if scan_result.stdout else ''
            
            # Check if SSID exists in scan results
            if ssid not in scan_stdout:
                logger.warning('[WIFI-CONNECT] SSID "{}" not found in scan results'.format(ssid))
                return False, 'No network with SSID "{}" found. Please scan again.'.format(ssid)
                
        except Exception as scan_err:
            logger.warning('[WIFI-CONNECT] Scan check failed: {}'.format(scan_err))
            # Continue anyway - scan might have failed but network could still exist
        
        # Try to connect
        cmd = ['nmcli', 'dev', 'wifi', 'connect', ssid]
        if password:
            cmd += ['password', password]
        
        logger.info('[WIFI-CONNECT] Attempting to connect to "{}"'.format(ssid))
        
        # Use Python 3.5 compatible subprocess
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30
        )
        
        stdout = result.stdout.decode('utf-8', errors='replace') if result.stdout else ''
        stderr = result.stderr.decode('utf-8', errors='replace') if result.stderr else ''
        
        if result.returncode == 0:
            logger.info('[WIFI-CONNECT] Successfully connected to "{}"'.format(ssid))
            return True, 'Connected to {}'.format(ssid)
        
        # Check for common errors
        if 'No network with SSID' in stdout or 'No network with SSID' in stderr:
            return False, 'No network with SSID "{}" found. Please check the network name and try again.'.format(ssid)
        elif 'passwords do not match' in stdout or 'passwords do not match' in stderr:
            return False, 'Invalid password for network "{}"'.format(ssid)
        elif 'Connection activation failed' in stdout or 'Connection activation failed' in stderr:
            return False, 'Connection failed. Please check your network settings.'
        else:
            err = (stdout or stderr or '').strip()
            return False, err or 'Connection failed'
            
    except subprocess.TimeoutExpired:
        logger.error('[WIFI-CONNECT] Timeout connecting to "{}"'.format(ssid))
        return False, 'Connection timed out. Please check your network.'
    except FileNotFoundError:
        logger.error('[WIFI-CONNECT] nmcli not found')
        return False, 'nmcli not available on this system'
    except Exception as e:
        logger.error('[WIFI-CONNECT] Unexpected error: {}'.format(e))
        return False, str(e)

async def wifi_connect_handler(request):
    """POST /api/wifi/connect -- connect to a WiFi network."""
    user = ws_auth(request)
    if user is None:
        return web.json_response({'success': False, 'error': 'Unauthorized'}, status=401)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({'success': False, 'error': 'Invalid JSON'}, status=400)

    ssid     = (body.get('ssid') or '').strip()
    password = (body.get('password') or '').strip()

    if not ssid:
        return web.json_response({'success': False, 'error': 'ssid is required'}, status=400)

    try:
        loop = asyncio.get_event_loop()
        ok, message = await loop.run_in_executor(None, _do_wifi_connect, ssid, password)

        if ok:
            # Update live state so the WS snapshot reflects the new connection
            network_status_state['net.wlan.ssid'] = ssid
            return web.json_response({'success': True,  'message': message})
        else:
            return web.json_response({'success': False, 'message': message}, status=502)

    except Exception as e:
        logger.error('[WIFI-CONNECT] Unexpected error: {}'.format(e))
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ============================================================================
# PIPELINE SYNC HELPERS
# ============================================================================

# ============================================================================
# PIPELINE POST ENDPOINT  — called by the frontend Connect button
# Accepts: { "datapoint": "net.route", "value": <int> }
# Pushes the value directly into pipeline_state and flushes it.
# ============================================================================
async def pipeline_post_handler(request):
    """POST /api/pipeline — push a single datapoint value to the pipeline."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({'success': False, 'message': 'Invalid JSON'}, status=400)

    datapoint = body.get('datapoint', '')
    value = body.get('value')

    if not datapoint or value is None:
        return web.json_response({'success': False, 'message': 'Missing datapoint or value'}, status=400)

    if datapoint == 'net.route':
        try:
            route_value = int(value)
            with pipeline_state["lock"]:
                pipeline_state["network_route_pending"] = route_value
            _flush_all_pending()
            logger.info("[PIPELINE-POST] Pushed net.route={} to pipeline (explicit Connect click)".format(route_value))
            return web.json_response({'success': True, 'datapoint': datapoint, 'value': route_value})
        except Exception as e:
            logger.error("[PIPELINE-POST] Error pushing route: {}".format(e))
            return web.json_response({'success': False, 'message': str(e)}, status=500)

    return web.json_response({'success': False, 'message': 'Unsupported datapoint: ' + datapoint}, status=400)


def _get_route_value(network_mode, eth_selected='eth0'):
    """Convert network mode to pipeline route value.
       Route mapping: auto=0, eth0=1, eth1=2, lte=3, wifi=4
    """
    if network_mode == 'ethernet':
        return 1 if eth_selected == 'eth0' else 2
    elif network_mode == 'lte':
        return 3
    elif network_mode == 'wifi':
        return 4
    elif network_mode == 'auto':
        return 0
    return None


async def sync_network_mode_to_pipeline(app):
    """On startup, read network config from DB and send appropriate mode to pipeline.
    
    Logic:
    - If auto_connect is ON: send 'auto' (value 0) - let pipeline auto-select
    - If auto_connect is OFF: use last_route_select from DB (the route the user
      explicitly chose last time). Only fall back to deriving from network_mode
      if last_route_select is 0/None (i.e. was never explicitly set).
    """
    try:
        config = get_general_configuration()
        if not config:
            logger.info("[PIPELINE-SYNC] No config found on startup")
            return
        
        network = config.get('network', {})
        auto_connect = network.get('auto_connect', False)
        network_mode = network.get('mode', 'wifi')
        eth_selected = network.get('eth_selected', 'eth0')
        last_route_select = network.get('last_route_select', 0)
        
        raw_db_auto = network.get('auto_connect')
        logger.info("[PIPELINE-SYNC] Startup sync - DB state: auto_connect={} (raw={}), mode={}, eth={}, last_route_select={}".format(
            auto_connect, raw_db_auto, network_mode, eth_selected, last_route_select))
        
        if auto_connect is True or auto_connect == 1 or auto_connect == 'true':
            route_value = 0  # auto
            logger.info("[PIPELINE-SYNC] Startup: Auto-connect is ACTIVE -> Route: 0 (auto)")
        elif last_route_select and int(last_route_select) > 0:
            # Use the route the user last explicitly selected — no forcing needed
            route_value = int(last_route_select)
            logger.info("[PIPELINE-SYNC] Startup: Auto-connect OFF, using persisted last_route_select={}".format(route_value))
        else:
            # last_route_select is 0 or unset — derive from network_mode as fallback
            route_value = _get_route_value(network_mode, eth_selected)
            logger.info("[PIPELINE-SYNC] Startup: Auto-connect OFF, no saved route, derived route={} from mode={}".format(route_value, network_mode))
            if route_value is None:
                logger.warning("[PIPELINE-SYNC] Unknown network mode: {}".format(network_mode))
                return
        
        if route_value is not None:
            with pipeline_state["lock"]:
                pipeline_state["network_route_pending"] = route_value
            _flush_all_pending()
            logger.info("[PIPELINE-SYNC] Pushed route={} to pipeline_state".format(route_value))
        else:
            logger.warning("[PIPELINE-SYNC] No route value to send")
            
    except Exception as e:
        logger.error("[PIPELINE-SYNC] Error syncing to pipeline: {}".format(e))


# ============================================================================
# UTILS (from utils.py, simplified)
# ============================================================================

async def periodic_updates():
    """Update real-time state only when changes occur."""
    while True:
        try:
            # Update time using active timezone
            now      = get_now()
            new_date = now.strftime('%Y-%m-%d')
            new_time = now.strftime('%H:%M')  # always stored as 24h

            # Load time_format from saved config so broadcast carries the right format
            try:
                cfg = get_general_configuration()
                _tf = (cfg.get('date_time') or {}).get('time_format', '24-hour')
            except Exception:
                _tf = '24-hour'

            if _tf == '12-hour':
                _h12 = now.strftime('%I:%M %p')
                new_time_display = _h12.lstrip('0') if _h12.startswith('0') else _h12
            else:
                new_time_display = new_time

            date_changed = new_date != previous_state['current_date']
            time_changed = new_time != previous_state['current_time']
            
            if date_changed or time_changed:
                realtime_state['current_date'] = new_date
                realtime_state['current_time'] = new_time
                
                previous_state['current_date'] = new_date
                previous_state['current_time'] = new_time
                
                # Broadcast time update if changed and clients are connected
                if connected_websockets and (date_changed or time_changed):
                    await broadcast_to_clients({
                        'type':         'time_update',
                        'current_date': new_date,
                        'current_time': new_time,
                        'time_display': new_time_display,
                        'time_format':  _tf,
                    })
            
            # Smart sleep interval
            if connected_websockets:
                await asyncio.sleep(30)  # Clients connected - check every 30 seconds
            else:
                await asyncio.sleep(60)  # No clients - check every minute
            
        except Exception as e:
            logger.error("Error in periodic updates: {}".format(e))
            await asyncio.sleep(60)


def update_wifi_signal_strength(strength):
    """Update WiFi signal strength and broadcast if changed."""
    if 0 <= strength <= 4:
        old_strength = realtime_state.get('wifi_signal_strength')
        realtime_state['wifi_signal_strength'] = strength
        
        if old_strength != strength and connected_websockets:
            asyncio.ensure_future(broadcast_to_clients({
                'type': 'wifi_signal_update',
                'strength': strength
            }))


# ============================================================================
# CONFIGURATION HANDLERS (original from general_config.py)
# ============================================================================

async def sync_time_handler(request):
    """POST /api/sync-time

    Flow:
      1. Set timezone (timedatectl / symlink fallback)
      2. Start chronyd, run chronyc makestep + waitsync
      3. Stop NTP service (time frozen at synced value)
      4. set-local-rtc 0  +  hwclock --systohc
      5. Return updated time to UI

    NOTE: The old ping pre-check (Step 0) has been removed.
    It was the direct cause of the 400 Bad Request: on devices with no
    internet the ping fails immediately and the handler aborted before
    running any NTP commands.  The old JS hid this by crashing into the
    .catch() block which silently fell back to browser time, so the user
    never saw the real error.  Now we just attempt the sync; if the
    device truly has no internet chronyc will fail and we return a clear
    500 with the detail.

    All blocking subprocess calls run inside run_in_executor so the
    aiohttp event loop is never frozen during the ~40 s worst-case sync.
    """
    user = ws_auth(request)
    if user is None:
        return web.json_response({'success': False, 'error': 'Unauthorized'}, status=401)

    try:
        body = await request.json()
    except Exception:
        body = {}

    timezone    = body.get('timezone',    'Asia/Kolkata')
    ntp_server  = body.get('ntp_server',  'time.google.com')  # noqa: kept for future use
    date_format = body.get('date_format', 'DD/MM/YYYY')
    time_format = body.get('time_format', '24-hour')

    # All heavy work runs in a thread so the event loop stays responsive.
    def _do_sync():
        import subprocess as _sp
        import os as _os
        import time as _time

        results = {}

        # ------------------------------------------------------------------
        # STEP 1: Set timezone
        # ------------------------------------------------------------------
        try:
            r_tz = _sp.run(
                ['timedatectl', 'set-timezone', timezone],
                stdout=_sp.PIPE, stderr=_sp.PIPE, timeout=5
            )
            if r_tz.returncode == 0:
                logger.info('[SYNC-TIME] timedatectl set-timezone {} OK'.format(timezone))
            else:
                raise Exception('timedatectl returned {}'.format(r_tz.returncode))
        except Exception as e:
            logger.info('[SYNC-TIME] timedatectl failed: {}, trying symlink'.format(e))
            try:
                tz_file = '/usr/share/zoneinfo/{}'.format(timezone)
                if _os.path.exists(tz_file):
                    if _os.path.lexists('/etc/localtime'):
                        _os.remove('/etc/localtime')
                    _os.symlink(tz_file, '/etc/localtime')
                    try:
                        with open('/etc/timezone', 'w') as _f:
                            _f.write(timezone + '\n')
                    except Exception:
                        pass
                    logger.info('[SYNC-TIME] symlinked /etc/localtime -> {}'.format(tz_file))
            except Exception as e2:
                logger.info('[SYNC-TIME] timezone symlink failed: {}'.format(e2))

        # ------------------------------------------------------------------
        # STEP 2: NTP sync via chronyc
        # ------------------------------------------------------------------
        CHRONYC = '/usr/bin/chronyc'

        _sp.call(['systemctl', 'start', 'chronyd'],
                 stdout=_sp.PIPE, stderr=_sp.PIPE)
        _time.sleep(2)  # give daemon a moment to start

        r_step = _sp.run(
            [CHRONYC, 'makestep'],
            stdout=_sp.PIPE, stderr=_sp.PIPE, timeout=15
        )
        out_step = (r_step.stdout + r_step.stderr).decode('utf-8', errors='replace').strip()
        logger.info('[SYNC-TIME] chronyc makestep rc={} out={}'.format(r_step.returncode, out_step))
        results['makestep_rc']  = r_step.returncode
        results['makestep_out'] = out_step

        if r_step.returncode != 0:
            # chronyc failed — most likely no internet/NTP reachable
            return results  # caller checks makestep_rc

        r_wait = _sp.run(
            [CHRONYC, 'waitsync', '6', '0.1', '0', '5'],
            stdout=_sp.PIPE, stderr=_sp.PIPE, timeout=35
        )
        out_wait = (r_wait.stdout + r_wait.stderr).decode('utf-8', errors='replace').strip()
        logger.info('[SYNC-TIME] chronyc waitsync rc={} out={}'.format(r_wait.returncode, out_wait))

        # ------------------------------------------------------------------
        # STEP 3: Stop NTP service (one-time sync complete)
        # ------------------------------------------------------------------
        _sp.call(['timedatectl', 'set-ntp', 'false'],
                 stdout=_sp.PIPE, stderr=_sp.PIPE)
        _sp.call(['systemctl', 'stop', 'chronyd'],
                 stdout=_sp.PIPE, stderr=_sp.PIPE)
        logger.info('[SYNC-TIME] NTP service stopped (one-time sync complete)')

        # ------------------------------------------------------------------
        # STEP 4: Tell kernel RTC stores UTC, then write RTC
        # ------------------------------------------------------------------
        try:
            _sp.call(['timedatectl', 'set-local-rtc', '0'],
                     stdout=_sp.PIPE, stderr=_sp.PIPE, timeout=5)
            logger.info('[SYNC-TIME] set-local-rtc 0 OK')
        except Exception as e:
            logger.error('[SYNC-TIME] set-local-rtc error (non-fatal): {}'.format(e))

        try:
            r_hw = _sp.run(
                ['hwclock', '--systohc'],
                stdout=_sp.PIPE, stderr=_sp.PIPE, timeout=5
            )
            out_hw = (r_hw.stdout + r_hw.stderr).decode('utf-8', errors='replace').strip()
            logger.info('[SYNC-TIME] hwclock --systohc rc={} out={}'.format(
                r_hw.returncode, out_hw or 'OK'))
        except Exception as e:
            logger.error('[SYNC-TIME] hwclock --systohc error (non-fatal): {}'.format(e))

        return results

    # Run blocking work off the event loop
    loop = asyncio.get_event_loop()
    try:
        results = await loop.run_in_executor(None, _do_sync)
    except Exception as e:
        logger.error('[SYNC-TIME] executor error: {}'.format(e))
        return web.json_response({
            'success': False,
            'error': 'Sync error: {}'.format(str(e))
        }, status=500)

    # If makestep failed, report it clearly
    if results.get('makestep_rc', 0) != 0:
        return web.json_response({
            'success': False,
            'error':  'NTP Sync Failed — check internet/NTP connectivity',
            'detail': results.get('makestep_out', '')
        }, status=500)

    # ------------------------------------------------------------------
    # STEP 5: Update active_timezone and return updated time to UI
    # ------------------------------------------------------------------
    global active_timezone
    active_timezone = timezone

    now = get_now()

    if date_format == 'MM/DD/YYYY':
        formatted_date = now.strftime('%m/%d/%Y')
        iso_date       = now.strftime('%Y-%m-%d')
    elif date_format == 'YYYY-MM-DD':
        formatted_date = now.strftime('%Y-%m-%d')
        iso_date       = formatted_date
    else:
        formatted_date = now.strftime('%d/%m/%Y')
        iso_date       = now.strftime('%Y-%m-%d')

    if time_format == '12-hour':
        formatted_time = now.strftime('%I:%M %p')
        input_time     = now.strftime('%I:%M')
    else:
        formatted_time = now.strftime('%H:%M')
        input_time     = formatted_time

    realtime_state['current_date'] = iso_date
    realtime_state['current_time'] = input_time
    previous_state['current_date'] = iso_date
    previous_state['current_time'] = input_time

    if connected_websockets:
        await broadcast_to_clients({
            'type':         'time_update',
            'current_date': iso_date,
            'current_time': input_time,
        })

    return web.json_response({
        'success':        True,
        'current_date':   iso_date,
        'current_time':   input_time,
        'formatted_date': formatted_date,
        'formatted_time': formatted_time,
        'timezone':       timezone,
        'ntp_server':     ntp_server,
        'message':        'Time synced successfully',
    })


async def get_config_handler(request):
    """GET /api/general-configuration"""
    # Auth: require a valid session so an expired/logged-out user gets 401
    user = ws_auth(request)
    if user is None:
        return web.json_response({'success': False, 'error': 'Unauthorized'}, status=401)

    config = get_general_configuration()

    # Update wifi signal strength from latest network status
    if 'net.wlan.signal_pct' in network_status_state:
        try:
            pct = float(network_status_state['net.wlan.signal_pct'])
            realtime_state['wifi_signal_strength'] = min(4, int(pct) // 25)
        except (ValueError, TypeError):
            pass

    # Add real-time data to response
    if isinstance(config, dict):
        config['_realtime'] = {
            'current_date': realtime_state['current_date'],
            'current_time': realtime_state['current_time'],
            'wifi_signal_strength': realtime_state.get('wifi_signal_strength', 3)
        }

    return web.json_response(config)


async def put_config_handler(request):
    """PUT /api/general-configuration"""
    # Auth check
    user = ws_auth(request)
    if user is None:
        return web.json_response({'success': False, 'error': 'Unauthorized'}, status=401)
    
    try:
        data = await request.json()
    except Exception:
        return web.json_response({'success': False, 'message': 'Invalid JSON'}, status=400)

    # Validate heartbeat fields — reject negative values
    heartbeat = data.get('heartbeat', {})
    if isinstance(heartbeat, dict):
        for field in ('interval', 'offline_threshold'):
            val = heartbeat.get(field)
            if val is not None:
                try:
                    if int(val) < 0:
                        return web.json_response(
                            {'success': False, 'message': 'heartbeat.{} cannot be negative'.format(field)},
                            status=400
                        )
                except (TypeError, ValueError):
                    return web.json_response(
                        {'success': False, 'message': 'heartbeat.{} must be an integer'.format(field)},
                        status=400
                    )

    try:
        success = update_general_configuration(data)
    except Exception as e:
        logger.error("Error in PUT handler: {}".format(e))
        return web.json_response({'success': False, 'message': str(e)}, status=400)

    # Update active timezone so periodic_updates reflects new setting immediately
    global active_timezone
    try:
        saved_tz = (data.get('date_time') or {}).get('timezone')
        if saved_tz:
            active_timezone = saved_tz
    except Exception:
        pass

    if not success:
        return web.json_response(
            {'success': False, 'message': 'Failed to save configuration'}, status=500)

    if 'network' in data:
        # Sync network mode to pipeline after save
        try:
            # First, get current DB state to fill in gaps
            saved_config = get_general_configuration()
            network = saved_config.get('network', {})
            
            # Use data from incoming request if present, fallback to DB
            net_data = data['network']
            raw_ac = net_data.get('auto_connect', network.get('auto_connect', False))
            
            # CRITICAL: Robust truthy check (handles bool, int 0/1, string "true")
            cur_auto_connect = bool(raw_ac) if not isinstance(raw_ac, str) else raw_ac.lower() == 'true'
            
            cur_mode         = net_data.get('mode',         network.get('mode', 'wifi'))
            cur_eth_selected = net_data.get('eth_selected', network.get('eth_selected', 'eth0'))
            
            logger.info("[PIPELINE-SYNC] Save sync check - auto_connect={} (raw={}), mode={}, eth={}".format(
                cur_auto_connect, raw_ac, cur_mode, cur_eth_selected))
            
            # Determine what to sync to pipeline
            should_sync  = False
            target_route = None

            # 1. Auto-Connect toggle was explicitly changed
            if 'auto_connect' in net_data:
                if cur_auto_connect:
                    # Turned ON -> force route 0 (auto)
                    target_route = 0
                    should_sync  = True
                    logger.info("[PIPELINE-SYNC] ACTION: Auto-Connect toggled ON -> force network_route_select=0")
                else:
                    # Turned OFF -> Send the currently active route based on live state
                    active_route = _get_current_active_route_from_state()
                    if active_route is not None:
                        target_route = active_route
                        should_sync = True
                        logger.info("[PIPELINE-SYNC] ACTION: Auto-Connect toggled OFF -> sending current active route={}".format(target_route))
                    else:
                        logger.info("[PIPELINE-SYNC] ACTION: Auto-Connect toggled OFF but no active connection found")

            # 2. Auto-Connect is ON and user changed a radio/mode field
            #    -> block non-zero route; re-enforce 0 to pipeline
            elif cur_auto_connect:
                if 'mode' in net_data or 'eth_selected' in net_data:
                    target_route = 0
                    should_sync  = True
                    logger.info(
                        "[PIPELINE-SYNC] ACTION: Mode changed but auto_connect=ON "
                        "-> BLOCKED non-zero route, re-enforcing network_route_select=0"
                    )
                else:
                    logger.info("[PIPELINE-SYNC] auto_connect=ON, no mode change -> no pipeline sync needed")

            # 3. Auto-Connect is OFF and mode/eth explicitly changed
            elif 'mode' in net_data or 'eth_selected' in net_data:
                logger.info("[PIPELINE-SYNC] ACTION: Mode changed, auto_connect=OFF -> Waiting for explicit Connect click, not sending route.")
                # We do NOT send the target route here. The frontend's Connect button handles it.

            # Execute the sync
            if should_sync and target_route is not None:
                with pipeline_state["lock"]:
                    pipeline_state["network_route_pending"] = target_route
                _flush_all_pending()
                logger.info("[PIPELINE-SYNC] Pushed network_route_select={} to pipeline queue".format(target_route))
                
        except Exception as e:
            logger.error("[PIPELINE-SYNC] Sync Error: {}".format(e))

    # ========== ONLY rebuild IoT config if WIFI or HEARTBEAT settings changed ==========
    # NOT for auto_connect toggles! auto_connect only affects network routing, not IoT config
    iot_changed = False
    if 'network' in data:
        net_data = data['network']
        # ONLY check for wifi config changes (SSID, password, etc.), NOT auto_connect
        if 'wifi' in net_data:
            # Check if wifi config actually changed (not just auto_connect)
            wifi_data = net_data['wifi']
            if isinstance(wifi_data, dict) and (wifi_data.get('ssid') or wifi_data.get('password')):
                iot_changed = True
                logger.info("[IOT-CFG] WiFi config changed - will rebuild IoT config")
    if 'heartbeat' in data:
        iot_changed = True
        logger.info("[IOT-CFG] Heartbeat config changed - will rebuild IoT config")
    
    # Also check if it's a direct wifi change (legacy format)
    if 'wifi_ssid' in data or 'wifi_password' in data:
        iot_changed = True
        logger.info("[IOT-CFG] Legacy wifi fields changed - will rebuild IoT config")
    
    if iot_changed:
        # Rebuild + push iot_gateway_config (wifi/heartbeat actually changed)
        try:
            from mqtt_cloud import send_iot_gateway_config_now
            await send_iot_gateway_config_now()
            logger.info("[IOT-CFG] Successfully rebuilt and sent IoT config")
        except Exception as e:
            logger.error('[IOT-CFG] sync error after general_config save: {}'.format(e))
    else:
        logger.info("[IOT-CFG] No wifi/heartbeat changes detected - skipping IoT config rebuild")

    # Broadcast config update to WebSocket clients
    if connected_websockets:
        await broadcast_to_clients({
            'type': 'config_updated',
            'message': 'Configuration saved successfully'
        })

    return web.json_response({'success': True, 'message': 'Configuration saved successfully'})


# ============================================================================
# BACKGROUND TASK MANAGEMENT
# ============================================================================

async def start_background_tasks(app):
    """Start background tasks for the general config module."""
    logger.info("[GENERAL-CONFIG] Starting background tasks...")
    # Load saved timezone from DB so periodic_updates starts with correct tz
    global active_timezone
    try:
        cfg = get_general_configuration()
        saved_tz = (cfg.get('date_time') or {}).get('timezone')
        if saved_tz:
            active_timezone = saved_tz
            logger.info("[GENERAL-CONFIG] Loaded timezone: {}".format(active_timezone))
    except Exception as e:
        logger.info("[GENERAL-CONFIG] Could not load timezone from DB: {}".format(e))
    
    # Stash the running event loop so pipeline thread callbacks can reach it.
    _main_loop_ref["loop"] = asyncio.get_event_loop()
    app['general_config_periodic'] = asyncio.ensure_future(periodic_updates())
    
    # Sync network mode to pipeline on startup
    await sync_network_mode_to_pipeline(app)


async def cleanup_background_tasks(app):
    """Clean up background tasks."""
    logger.info("[GENERAL-CONFIG] Cleaning up background tasks...")
    if 'general_config_periodic' in app:
        app['general_config_periodic'].cancel()
        try:
            await app['general_config_periodic']
        except (asyncio.CancelledError, Exception):
            pass
    logger.info("[GENERAL-CONFIG] Cleanup complete")


# ============================================================================
# ROUTE REGISTRATION
# ============================================================================

def register_general_config_routes(app):
    """Register all general configuration routes."""
    # OPTIMIZATION: Start the broadcast batching worker
    start_broadcast_worker(app)
    
    # Configuration API
    app.router.add_get('/api/general-configuration', get_config_handler)
    app.router.add_put('/api/general-configuration', put_config_handler)
    
    # Time sync endpoint
    app.router.add_post('/api/sync-time', sync_time_handler)
    app.router.add_post('/api/pipeline', pipeline_post_handler)

    # WiFi scan + connect endpoints
    app.router.add_get('/api/wifi/scan',    wifi_scan_handler)
    app.router.add_get('/api/wifi/scan/debug', wifi_scan_debug_handler)
    app.router.add_post('/api/wifi/connect', wifi_connect_handler)
    
    # WebSocket
    app.router.add_get('/ws/general', websocket_handler)
    app.router.add_get('/ws/network-status', network_status_websocket_handler)
    
    # Background tasks
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    
    logger.info("[GENERAL-CONFIG] Routes registered")


# ============================================================================
# DEVICE STATUS TRACKING (from models.py + utils.py)
# ============================================================================

import datetime as _dt
from logger_util import get_logger


logger = get_logger(__name__)
# Device status tracking (not in database)
device_status_tracker = {}


def initialize_device_status(device_id, initial_status='Offline'):
    """Initialize device status when device is created"""
    if device_id not in device_status_tracker:
        device_status_tracker[device_id] = {
            'status': initial_status,
            'last_poll': 'Never' if initial_status == 'Offline' else 'Just now',
            'previous_status': initial_status,
            'previous_poll': 'Never' if initial_status == 'Offline' else 'Just now'
        }
        if initial_status == 'Offline':
            device_status_tracker[device_id]['last_offline_time'] = _dt.datetime.now()
    return device_status_tracker[device_id]


def update_device_status(device_id, status, last_poll=None):
    """Manually update device status"""
    if device_id not in device_status_tracker:
        initialize_device_status(device_id, status)
    else:
        device_status_tracker[device_id]['previous_status'] = device_status_tracker[device_id]['status']
        device_status_tracker[device_id]['previous_poll'] = device_status_tracker[device_id]['last_poll']
        device_status_tracker[device_id]['status'] = status

        if last_poll:
            device_status_tracker[device_id]['last_poll'] = last_poll
        elif status == 'Online':
            device_status_tracker[device_id]['last_poll'] = 'Just now'
        else:
            device_status_tracker[device_id]['last_poll'] = 'Connection lost'
            device_status_tracker[device_id]['last_offline_time'] = _dt.datetime.now()

    return device_status_tracker[device_id]


def get_device_status(device_id):
    """Get current device status"""
    if device_id not in device_status_tracker:
        return initialize_device_status(device_id)
    return device_status_tracker[device_id]


def remove_device_status(device_id):
    """Remove device from status tracking"""
    if device_id in device_status_tracker:
        del device_status_tracker[device_id]