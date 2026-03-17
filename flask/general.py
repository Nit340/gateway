# general_config.py - Consolidated general configuration API with WebSocket support
import asyncio
import json
import datetime
from aiohttp import web
from aiohttp import WSMsgType as MsgType
from database import get_general_configuration, update_general_configuration
from auth import ws_auth

# ============================================================================
# MODELS (from models.py)
# ============================================================================

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


# ============================================================================
# WEBSOCKET HANDLER (from websocket_handler.py, simplified)
# ============================================================================

async def websocket_handler(request):
    """Handle WebSocket connections for real-time updates."""
    # Auth check
    user = ws_auth(request)
    if user is None:
        return web.Response(status=401, text='Unauthorized')

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    connected_websockets.add(ws)
    print("WebSocket connected (user={}). Total clients: {}".format(user, len(connected_websockets)))

    try:
        # Send initial state to the newly connected client
        await ws.send_str(json.dumps({
            'type': 'initial',
            'current_date': realtime_state['current_date'],
            'current_time': realtime_state['current_time'],
            'wifi_signal_strength': realtime_state.get('wifi_signal_strength', 3)
        }))

        while True:
            msg = await ws.receive()

            if msg.type == MsgType.close:
                break
            elif msg.type == MsgType.error:
                print('WebSocket error (user={}): {}'.format(user, ws.exception()))
                break
            elif msg.type == MsgType.ping:
                await ws.pong()
            elif msg.type == MsgType.text:
                try:
                    data = json.loads(msg.data)

                    if data.get('type') == 'sync_time':
                        new_date = datetime.datetime.now().strftime('%Y-%m-%d')
                        new_time = datetime.datetime.now().strftime('%H:%M')

                        if (new_date != realtime_state['current_date'] or
                                new_time != realtime_state['current_time']):
                            realtime_state['current_date'] = new_date
                            realtime_state['current_time'] = new_time
                            await broadcast_to_clients({
                                'type': 'time_update',
                                'current_date': new_date,
                                'current_time': new_time
                            })

                        await ws.send_str(json.dumps({
                            'type': 'time_synced',
                            'current_date': realtime_state['current_date'],
                            'current_time': realtime_state['current_time']
                        }))

                    elif data.get('type') == 'get_wifi_signal':
                        # Return current wifi signal strength
                        strength = realtime_state.get('wifi_signal_strength', 3)
                        await ws.send_str(json.dumps({
                            'type': 'wifi_signal_update',
                            'strength': strength
                        }))

                    elif data.get('type') == 'ping':
                        await ws.send_str(json.dumps({'type': 'pong'}))

                except (ValueError, KeyError):
                    await ws.send_str(json.dumps({
                        'type': 'error',
                        'message': 'Invalid JSON format'
                    }))

    except Exception as e:
        print("WebSocket error (user={}): {}".format(user, e))
    finally:
        connected_websockets.discard(ws)
        print("WebSocket disconnected (user={}). Total clients: {}".format(user, len(connected_websockets)))

    return ws


async def broadcast_to_clients(data):
    """Broadcast a dict to all connected WebSocket clients."""
    if not connected_websockets:
        return
    payload = json.dumps(data)
    await asyncio.gather(
        *[_safe_send(ws, payload) for ws in list(connected_websockets) if not ws.closed],
        return_exceptions=True
    )


async def _safe_send(ws, payload):
    """Send payload to one WebSocket; discard on failure."""
    try:
        if not ws.closed:
            await ws.send_str(payload)
    except Exception as e:
        print("Error sending to WebSocket: {}".format(e))
        connected_websockets.discard(ws)


# ============================================================================
# NETWORK STATUS    helpers called by pipeline.py on RECEIVE_DONE
# ============================================================================

def update_network_status_field(datapoint_name: str, value) -> None:
    """
    Called from the pipeline RECEIVE_DONE handler (pipeline.py) whenever a
    network_status/* datapoint arrives.  Stores the value and broadcasts the
    delta to all live WebSocket subscribers.
    """
    network_status_state[datapoint_name] = value

    # Build a structured snapshot from the flat store and push it out.
    snapshot = _build_network_status_snapshot()
    main_loop = None
    try:
        import asyncio
        # Grab the running loop from the aiohttp application context.
        # We store a reference to it in start_background_tasks below.
        main_loop = _main_loop_ref.get("loop")
    except Exception:
        pass

    if main_loop and main_loop.is_running():
        try:
            asyncio.run_coroutine_threadsafe(
                _broadcast_network_status({
                    "type": "network_status_update",
                    "data": snapshot,
                }),
                main_loop,
            )
        except Exception as e:
            print("[NET-STATUS] broadcast error: {}".format(e))


def _build_network_status_snapshot():
    """Return a structured dict from the flat network_status_state.

    Key names match exactly what the pipeline publishes under
    network_status/lan, network_status/wlan, network_status/lte.
    """
    s = network_status_state

    def _v(key, default=None):
        return s.get(key, default)

    return {
        # --- LAN (ethernet) ---
        # pipeline: network_status/lan -> {"lan":{"dynamic":{"net.lan.eth1.ip":...,"net.lan.eth1.state":...}}}
        # eth0 may also appear with net.lan.eth0.ip / net.lan.eth0.state / net.lan.eth0.mac
        "lan": {
            "eth0": {
                "ip":    _v("net.lan.eth0.ip",    ""),
                "mac":   _v("net.lan.eth0.mac",   ""),
                "state": _v("net.lan.eth0.state",  0),
            },
            "eth1": {
                "ip":    _v("net.lan.eth1.ip",    ""),
                "mac":   _v("net.lan.eth1.mac",   ""),
                "state": _v("net.lan.eth1.state",  0),
            },
        },
        # --- WLAN (wifi) ---
        # pipeline: network_status/wlan -> {"wlan":{"dynamic":{"net.wlan.bssid":...,"net.wlan.frequency":...,"net.wlan.ip":...,"net.wlan.ssid":...,"net.wlan.state":...}}}
        # signal quality in dBm (signed) arrives as net.wlan.signal
        "wlan": {
            "state":           _v("net.wlan.state",           0),
            "signal_quality":  _v("net.wlan.signal",          None),  # dBm signed
            "ssid":            _v("net.wlan.ssid",            ""),
            "bssid":           _v("net.wlan.bssid",           ""),
            "mac":             _v("net.wlan.mac",             ""),
            "ip":              _v("net.wlan.ip",              ""),
            "frequency":       _v("net.wlan.frequency",       0),
        },
        # --- LTE ---
        # pipeline: network_status/lte -> {"lte":{"dynamic":{"net.lte.ip":...,"net.lte.operator_id":...,"net.lte.operator_name":...,"net.lte.power":1,"net.lte.signal_pct":97,"net.lte.state":1,"net.lte.tech":"4G/LTE"}}}
        "lte": {
            "state":         _v("net.lte.state",         0),
            "power":         _v("net.lte.power",         0),   # 0 = no hardware
            "signal_pct":    _v("net.lte.signal_pct",    0),   # 0-100
            "imei":          _v("net.lte.imei",          ""),
            "operator_id":   _v("net.lte.operator_id",   ""),
            "operator_name": _v("net.lte.operator_name", ""),
            "ip":            _v("net.lte.ip",            ""),
            "iccid":         _v("net.lte.iccid",         ""),
            "imsi":          _v("net.lte.imsi",          ""),
            "tech":          _v("net.lte.tech",          ""),
        },
        "network_status": _v("network_status", 0),
    }


async def _broadcast_network_status(data: dict) -> None:
    """Broadcast a dict to all network-status WebSocket clients."""
    if not network_status_websockets:
        return
    payload = json.dumps(data)
    await asyncio.gather(
        *[_safe_send_ns(ws, payload)
          for ws in list(network_status_websockets) if not ws.closed],
        return_exceptions=True,
    )


async def _safe_send_ns(ws, payload: str) -> None:
    try:
        if not ws.closed:
            await ws.send_str(payload)
    except Exception as e:
        print("[NET-STATUS] WS send error: {}".format(e))
        network_status_websockets.discard(ws)


# Tiny holder so the pipeline thread can reach the aiohttp event loop.
_main_loop_ref = {}  # type: dict


async def network_status_websocket_handler(request):
    """
    GET /ws/network-status

    WebSocket endpoint that streams live network-status data from the pipeline.
    The client connects and immediately receives the current snapshot, then gets
    pushed updates whenever the pipeline publishes new network_status/* data.
    """
    user = ws_auth(request)
    if user is None:
        return web.Response(status=401, text="Unauthorized")

    ws = web.WebSocketResponse()
    await ws.prepare(request)
    network_status_websockets.add(ws)
    print("[NET-STATUS] WS connected (user={}). Total: {}".format(
        user, len(network_status_websockets)))

    try:
        # Send current snapshot immediately on connect
        await ws.send_str(json.dumps({
            "type": "network_status_initial",
            "data": _build_network_status_snapshot(),
        }))

        async for msg in ws:
            if msg.type == MsgType.close:
                break
            elif msg.type == MsgType.error:
                print("[NET-STATUS] WS error (user={}): {}".format(user, ws.exception()))
                break
            elif msg.type == MsgType.ping:
                await ws.pong()
            elif msg.type == MsgType.text:
                try:
                    data = json.loads(msg.data)
                    if data.get("type") == "ping":
                        await ws.send_str(json.dumps({"type": "pong"}))
                    elif data.get("type") == "get_snapshot":
                        await ws.send_str(json.dumps({
                            "type": "network_status_initial",
                            "data": _build_network_status_snapshot(),
                        }))
                except (ValueError, KeyError):
                    pass

    except Exception as e:
        print("[NET-STATUS] WS error (user={}): {}".format(user, e))
    finally:
        network_status_websockets.discard(ws)
        print("[NET-STATUS] WS disconnected (user={}). Total: {}".format(
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
        print('[WIFI-SCAN] wlanapi scan trigger failed (non-fatal): {}'.format(e))
        time.sleep(1)  # still wait a bit in case a previous scan is cached

    # ------------------------------------------------------------------ #
    #  Step 2: read results via netsh                                      #
    # ------------------------------------------------------------------ #
    try:
        result = subprocess.run(
            ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
            capture_output=True, text=True, timeout=15,
            encoding='utf-8', errors='replace'
        )
        print('[WIFI-SCAN] netsh rc={} lines={}'.format(
            result.returncode, len(result.stdout.splitlines())))

        if result.returncode != 0 or not result.stdout.strip():
            return []

        networks = []
        seen     = set()

        # Each network block starts with "SSID N :" on its own line
        blocks = re.split(r'\nSSID\s+\d+\s*:', result.stdout)
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

            # Windows signal% → dBm approximation
            signal_dbm = int(signal_pct / 2) - 100

            networks.append({
                'ssid':           ssid,
                'signal_quality': signal_dbm,
                'security':       security,
                'channel':        channel,
            })

        print('[WIFI-SCAN] parsed {} networks'.format(len(networks)))
        return networks

    except Exception as e:
        print('[WIFI-SCAN] netsh parse error: {}'.format(e))
        return []
def _do_wifi_scan():
    """Use netsh on Windows, fall back to nmcli/iw/iwlist on Linux."""
    import platform
    print('[WIFI-SCAN] Starting scan on {}...'.format(platform.system()))

    if platform.system() == 'Windows':
        networks = _scan_wifi_windows()
    else:
        networks = _scan_wifi_nmcli_linux()
        if not networks:
            networks = _scan_wifi_iw()
        if not networks:
            networks = _scan_wifi_iwlist()

    if not networks:
        print('[WIFI-SCAN] All methods returned empty.')
    networks.sort(key=lambda n: n.get('signal_quality', -100), reverse=True)
    return networks


def _scan_wifi_nmcli_linux():
    import subprocess
    for cmd in (
        ['nmcli', '--escape', 'no', '-t', '-f', 'SSID,SIGNAL,SECURITY,CHAN', 'dev', 'wifi', 'list'],
        ['sudo', 'nmcli', '--escape', 'no', '-t', '-f', 'SSID,SIGNAL,SECURITY,CHAN', 'dev', 'wifi', 'list'],
    ):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0 or not result.stdout.strip():
                continue
            networks = []
            seen = set()
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.rsplit(':', 3)
                if len(parts) < 4:
                    continue
                ssid = parts[0].strip()
                if not ssid or ssid in seen:
                    continue
                seen.add(ssid)
                try:
                    signal_dbm = int(int(parts[1].strip()) / 2) - 100
                except Exception:
                    signal_dbm = -100
                networks.append({
                    'ssid':           ssid,
                    'signal_quality': signal_dbm,
                    'security':       parts[2].strip() or 'Open',
                    'channel':        int(parts[3].strip()) if parts[3].strip().isdigit() else 0,
                })
            if networks:
                return networks
        except Exception:
            pass
    return []


def _scan_wifi_iw():
    import subprocess, re
    iface = 'wlan0'
    try:
        r = subprocess.run(['iw', 'dev'], capture_output=True, text=True, timeout=5)
        m = re.search(r'Interface\s+(\S+)', r.stdout)
        if m: iface = m.group(1)
    except Exception:
        pass
    for cmd in (['iw', 'dev', iface, 'scan'], ['sudo', 'iw', 'dev', iface, 'scan']):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            if not result.stdout.strip():
                continue
            networks, seen, cur = [], set(), {}
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith('BSS '):
                    if cur.get('ssid') and cur['ssid'] not in seen:
                        seen.add(cur['ssid']); networks.append(cur)
                    cur = {}
                m = re.match(r'SSID:\s+(.+)', line)
                if m: cur['ssid'] = m.group(1).strip()
                m = re.match(r'signal:\s+(-?[\d.]+)\s+dBm', line)
                if m: cur['signal_quality'] = int(float(m.group(1)))
                m = re.match(r'\* primary channel:\s+(\d+)', line)
                if m: cur['channel'] = int(m.group(1))
                if re.match(r'RSN:', line): cur['security'] = 'WPA2'
                if re.match(r'WPA:', line): cur.setdefault('security', 'WPA')
            if cur.get('ssid') and cur['ssid'] not in seen:
                networks.append(cur)
            for n in networks:
                n.setdefault('signal_quality', -100)
                n.setdefault('security', 'Open')
                n.setdefault('channel', 0)
            if networks:
                return networks
        except Exception:
            pass
    return []


def _scan_wifi_iwlist():
    import subprocess, re
    iface = 'wlan0'
    for cmd in (['iwlist', iface, 'scan'], ['sudo', 'iwlist', iface, 'scan']):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            if not result.stdout.strip():
                continue
            networks, seen = [], set()
            for cell in result.stdout.split('Cell ')[1:]:
                ssid_m = re.search(r'ESSID:"([^"]+)"', cell)
                if not ssid_m: continue
                ssid = ssid_m.group(1)
                if ssid in seen: continue
                seen.add(ssid)
                level_m = re.search(r'Signal level=(-?\d+)', cell)
                qual_m  = re.search(r'Quality=(\d+)/(\d+)', cell)
                chan_m  = re.search(r'Channel[:\s]+(\d+)', cell)
                enc_m   = re.search(r'Encryption key:(on|off)', cell)
                signal_dbm = int(level_m.group(1)) if level_m else (
                    int(int(qual_m.group(1)) / int(qual_m.group(2)) * 70) - 100 if qual_m else -100)
                security = 'Open'
                if enc_m and enc_m.group(1) == 'on':
                    security = 'WPA2' if 'WPA' in cell else 'WEP'
                networks.append({
                    'ssid': ssid, 'signal_quality': signal_dbm,
                    'security': security, 'channel': int(chan_m.group(1)) if chan_m else 0,
                })
            if networks:
                return networks
        except Exception:
            pass
    return []

async def wifi_scan_debug_handler(request):
    """GET /api/wifi/scan/debug — raw output for troubleshooting."""
    user = ws_auth(request)
    if user is None:
        return web.json_response({'error': 'Unauthorized'}, status=401)
    import subprocess, platform
    out = {'platform': platform.system()}
    for label, cmd in [
        ('netsh_networks', ['netsh', 'wlan', 'show', 'networks', 'mode=bssid']),
        ('netsh_interfaces', ['netsh', 'wlan', 'show', 'interfaces']),
        ('nmcli',  ['nmcli', '--escape', 'no', '-t', '-f', 'SSID,SIGNAL,SECURITY,CHAN', 'dev', 'wifi', 'list']),
        ('iw_dev', ['iw', 'dev']),
    ]:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                               encoding='utf-8', errors='replace')
            out[label] = {'rc': r.returncode, 'stdout': r.stdout[:3000], 'stderr': r.stderr[:500]}
        except FileNotFoundError:
            out[label] = {'rc': -1, 'stdout': '', 'stderr': 'command not found'}
        except Exception as e:
            out[label] = {'rc': -1, 'stdout': '', 'stderr': str(e)}
    out['note'] = 'parsed_networks triggers a real wlanapi scan (~3s wait)'
    out['parsed_networks'] = _do_wifi_scan()
    return web.json_response(out)


async def wifi_scan_handler(request):
    """GET /api/wifi/scan — scan for nearby WiFi networks via nmcli / iwlist."""
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
        print('[WIFI-SCAN] Unexpected error: {}'.format(e))
        return web.json_response({'success': False, 'error': str(e)}, status=500)


def _do_wifi_connect(ssid, password):
    """
    Connect to a WiFi network using nmcli.
    Returns (ok: bool, message: str).
    """
    import subprocess
    try:
        cmd = ['nmcli', 'dev', 'wifi', 'connect', ssid]
        if password:
            cmd += ['password', password]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, 'Connected to {}'.format(ssid)
        # nmcli puts the error on stdout for this command
        err = (result.stdout or result.stderr or '').strip()
        return False, err or 'Connection failed'
    except subprocess.TimeoutExpired:
        return False, 'Connection timed out'
    except FileNotFoundError:
        return False, 'nmcli not available on this system'
    except Exception as e:
        return False, str(e)


async def wifi_connect_handler(request):
    """POST /api/wifi/connect — connect to a WiFi network."""
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
        print('[WIFI-CONNECT] Unexpected error: {}'.format(e))
        return web.json_response({'success': False, 'error': str(e)}, status=500)


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
            new_time = now.strftime('%H:%M')
            
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
                        'type': 'time_update',
                        'current_date': new_date,
                        'current_time': new_time
                    })
            
            # Smart sleep interval
            if connected_websockets:
                await asyncio.sleep(30)  # Clients connected - check every 30 seconds
            else:
                await asyncio.sleep(60)  # No clients - check every minute
            
        except Exception as e:
            print("Error in periodic updates: {}".format(e))
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
    Accepts optional JSON body with timezone, ntp_server, date_format, time_format.
    Applies the timezone, optionally triggers NTP sync, and returns the current
    date/time formatted according to the selected options.
    """
    user = ws_auth(request)
    if user is None:
        return web.json_response({'success': False, 'error': 'Unauthorized'}, status=401)

    # Parse request body (may be empty)
    try:
        body = await request.json()
    except Exception:
        body = {}

    timezone    = body.get('timezone',    'UTC')
    ntp_server  = body.get('ntp_server',  'pool.ntp.org')
    date_format = body.get('date_format', 'DD/MM/YYYY')
    time_format = body.get('time_format', '24-hour')

    # Store as active timezone so periodic_updates uses it from now on
    global active_timezone
    active_timezone = timezone

    # --- Attempt real NTP sync if ntpdate / chronyc is available ---
    sync_method = 'system_clock'
    try:
        import subprocess
        result = subprocess.run(
            ['ntpdate', '-u', ntp_server],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            sync_method = 'ntp'
        else:
            # Fall back to chronyc
            result2 = subprocess.run(
                ['chronyc', 'makestep'],
                capture_output=True, text=True, timeout=10
            )
            if result2.returncode == 0:
                sync_method = 'chrony'
    except Exception:
        pass  # NTP tool not available - use system clock

    # Get current time in the requested timezone via get_now()
    now = get_now()

    # Format date according to date_format preference
    if date_format == 'MM/DD/YYYY':
        formatted_date = now.strftime('%m/%d/%Y')
        iso_date       = now.strftime('%Y-%m-%d')   # for the input[type=date] value
    elif date_format == 'YYYY-MM-DD':
        formatted_date = now.strftime('%Y-%m-%d')
        iso_date       = formatted_date
    else:  # DD/MM/YYYY (default)
        formatted_date = now.strftime('%d/%m/%Y')
        iso_date       = now.strftime('%Y-%m-%d')

    # Format time according to time_format preference
    if time_format == '12-hour':
        formatted_time = now.strftime('%I:%M %p')
        input_time     = now.strftime('%I:%M')
    else:  # 24-hour (default)
        formatted_time = now.strftime('%H:%M')
        input_time     = formatted_time

    # Update realtime_state so WS broadcast is consistent
    realtime_state['current_date'] = iso_date
    realtime_state['current_time'] = input_time
    previous_state['current_date'] = iso_date
    previous_state['current_time'] = input_time

    # Broadcast updated time to all connected general WS clients
    if connected_websockets:
        await broadcast_to_clients({
            'type':         'time_update',
            'current_date': iso_date,
            'current_time': input_time,
        })

    return web.json_response({
        'success':        True,
        'current_date':   iso_date,       # YYYY-MM-DD  (for <input type="date">)
        'current_time':   input_time,     # HH:MM or HH:MM  (for <input type="time">)
        'formatted_date': formatted_date, # human-readable per date_format
        'formatted_time': formatted_time, # human-readable per time_format
        'timezone':       timezone,
        'ntp_server':     ntp_server,
        'sync_method':    sync_method,
        'message':        'Time synchronized successfully',
    })
    """GET /api/general-configuration"""
    config = get_general_configuration()
    
    # Add real-time data to response
    if isinstance(config, dict):
        config['_realtime'] = {
            'current_date': realtime_state['current_date'],
            'current_time': realtime_state['current_time'],
            'wifi_signal_strength': realtime_state.get('wifi_signal_strength', 3)
        }
    
    return web.json_response(config)


async def get_config_handler(request):
    """GET /api/general-configuration"""
    config = get_general_configuration()

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

    try:
        success = update_general_configuration(data)
    except Exception as e:
        print("Error in PUT handler: {}".format(e))
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

    # Broadcast config update to WebSocket clients
    if connected_websockets:
        await broadcast_to_clients({
            'type': 'config_updated',
            'message': 'Configuration saved successfully'
        })

    # Rebuild + push iot_gateway_config (wifi/heartbeat may have changed)
    try:
        from mqtt_cloud import send_iot_gateway_config_now
        await send_iot_gateway_config_now()
    except Exception as e:
        print('[IOT-CFG] sync error after general_config save: {}'.format(e))

    return web.json_response({'success': True, 'message': 'Configuration saved successfully'})


# ============================================================================
# BACKGROUND TASK MANAGEMENT
# ============================================================================

async def start_background_tasks(app):
    """Start background tasks for the general config module."""
    print("[GENERAL-CONFIG] Starting background tasks...")
    # Load saved timezone from DB so periodic_updates starts with correct tz
    global active_timezone
    try:
        cfg = get_general_configuration()
        saved_tz = (cfg.get('date_time') or {}).get('timezone')
        if saved_tz:
            active_timezone = saved_tz
            print("[GENERAL-CONFIG] Loaded timezone: {}".format(active_timezone))
    except Exception as e:
        print("[GENERAL-CONFIG] Could not load timezone from DB: {}".format(e))
    # Stash the running event loop so pipeline thread callbacks can reach it.
    _main_loop_ref["loop"] = asyncio.get_event_loop()
    app['general_config_periodic'] = asyncio.ensure_future(periodic_updates())


async def cleanup_background_tasks(app):
    """Clean up background tasks."""
    print("[GENERAL-CONFIG] Cleaning up background tasks...")
    if 'general_config_periodic' in app:
        app['general_config_periodic'].cancel()
        try:
            await app['general_config_periodic']
        except (asyncio.CancelledError, Exception):
            pass
    print("[GENERAL-CONFIG] Cleanup complete")


# ============================================================================
# ROUTE REGISTRATION
# ============================================================================

def register_general_config_routes(app):
    """Register all general configuration routes."""
    # Configuration API
    app.router.add_get('/api/general-configuration', get_config_handler)
    app.router.add_put('/api/general-configuration', put_config_handler)
    
    # Time sync endpoint
    app.router.add_post('/api/sync-time', sync_time_handler)

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
    
    print("[GENERAL-CONFIG] Routes registered")

# ============================================================================
# DEVICE STATUS TRACKING (from models.py + utils.py)
# ============================================================================

import datetime as _dt

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