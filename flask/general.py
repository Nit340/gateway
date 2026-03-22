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
    """Handle WebSocket connections for real-time updates.

    Supports multiple simultaneous tabs/pages for the same user.
    Each browser tab gets its own independent WebSocket connection which
    is tracked in connected_websockets (a plain set).  There is no
    per-user limit here; all active connections receive broadcasts.
    """
    # --- Auth: require a valid webui session cookie ---
    user = ws_auth(request)
    if user is None:
        return web.Response(status=401, text='Unauthorized')

    # heartbeat_timeout: if no message (including pong) is received for
    # this many seconds the connection is considered dead and closed.
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    connected_websockets.add(ws)
    print("WebSocket connected (user={}). Total clients: {}".format(
        user, len(connected_websockets)))

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
                    print('WebSocket protocol error (user={}): {}'.format(user, exc))
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
                        new_date = datetime.datetime.now().strftime('%Y-%m-%d')
                        new_time = datetime.datetime.now().strftime('%H:%M')

                        if (new_date != realtime_state['current_date'] or
                                new_time != realtime_state['current_time']):
                            realtime_state['current_date'] = new_date
                            realtime_state['current_time'] = new_time
                            await broadcast_to_clients({
                                'type': 'time_update',
                                'current_date': new_date,
                                'current_time': new_time,
                            })

                        if not ws.closed:
                            await ws.send_str(json.dumps({
                                'type': 'time_synced',
                                'current_date': realtime_state['current_date'],
                                'current_time': realtime_state['current_time'],
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
        print("WebSocket unexpected error (user={}): {}: {}".format(
            user, type(e).__name__, e))
    finally:
        connected_websockets.discard(ws)
        print("WebSocket disconnected (user={}). Total clients: {}".format(
            user, len(connected_websockets)))

    return ws


async def broadcast_to_clients(data):
    """Broadcast a dict to all connected WebSocket clients.

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
    pushed updates whenever the pipeline publishes new network_status/* data.

    Multiple browser tabs for the same user are fully supported: each tab
    receives its own independent stream.
    """
    user = ws_auth(request)
    if user is None:
        return web.Response(status=401, text="Unauthorized")

    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    network_status_websockets.add(ws)
    print("[NET-STATUS] WS connected (user={}). Total: {}".format(
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
                    print("[NET-STATUS] WS protocol error (user={}): {}".format(user, exc))
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
        print("[NET-STATUS] WS unexpected error (user={}): {}: {}".format(
            user, type(e).__name__, e))
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

            # Windows signal% -> dBm approximation
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
def _get_wifi_iface():
    """Return the first wireless interface name found via 'iw dev', default wlan0."""
    import subprocess, re
    try:
        r = subprocess.run(
            ['iw', 'dev'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5
        )
        m = re.search(r'Interface\s+(\S+)', r.stdout.decode('utf-8', errors='replace'))
        if m:
            return m.group(1)
    except Exception:
        pass
    return 'wlan0'


def _do_wifi_scan():
    """
    Trigger a real WiFi scan and return results.

    This device uses wpa_supplicant to manage wlan0 directly.
    NetworkManager reports the interface as 'unmanaged' so nmcli
    cannot scan. iw dev wlan0 scan works because the process runs
    as root and wpa_supplicant keeps the interface up.

    Strategy:
      1. iw scan  -- primary: works perfectly on this device
      2. wpa_cli  -- fallback if iw is missing
    """
    import time
    print('[WIFI-SCAN] Starting scan on Linux...')

    iface = _get_wifi_iface()
    print('[WIFI-SCAN] Using interface: {}'.format(iface))

    # -- Method 1: iw dev <iface> scan --
    networks = _scan_wifi_iw(iface)
    if networks:
        networks.sort(key=lambda n: n.get('signal_quality', -100), reverse=True)
        print('[WIFI-SCAN] Found {} networks via iw.'.format(len(networks)))
        return networks

    # -- Method 2: wpa_cli scan + scan_results --
    print('[WIFI-SCAN] iw empty, trying wpa_cli...')
    networks = _scan_wifi_wpa_cli(iface)
    if networks:
        networks.sort(key=lambda n: n.get('signal_quality', -100), reverse=True)
        print('[WIFI-SCAN] Found {} networks via wpa_cli.'.format(len(networks)))
        return networks

    print('[WIFI-SCAN] All methods returned empty.')
    return []


def _scan_wifi_wpa_cli(iface):
    """
    Use wpa_cli to trigger a scan and read results.
    wpa_supplicant is the WiFi manager on many embedded Linux systems
    where NetworkManager is absent or does not own the interface.
    """
    import subprocess, re, time, os

    # Locate the wpa_supplicant control socket for this interface
    socket_dirs = [
        '/var/run/wpa_supplicant',
        '/run/wpa_supplicant',
        '/tmp/wpa_supplicant',
    ]
    socket_dir = None
    for d in socket_dirs:
        candidate = '{}/{}'.format(d, iface)
        if os.path.exists(candidate):
            socket_dir = d
            break

    # Build base wpa_cli command
    base = ['wpa_cli']
    if socket_dir:
        base += ['-p', socket_dir, '-i', iface]
    else:
        base += ['-i', iface]

    print('[WIFI-SCAN] wpa_cli base cmd: {}'.format(' '.join(base)))

    # Trigger scan
    try:
        r = subprocess.run(
            base + ['scan'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10
        )
        out = r.stdout.decode('utf-8', errors='replace').strip()
        print('[WIFI-SCAN] wpa_cli scan rc={} out={}'.format(r.returncode, out[:80]))
        if r.returncode != 0 and 'OK' not in out:
            return []
    except FileNotFoundError:
        print('[WIFI-SCAN] wpa_cli not found')
        return []
    except Exception as e:
        print('[WIFI-SCAN] wpa_cli scan error: {}'.format(e))
        return []

    # Wait for scan to complete
    time.sleep(4)

    # Read scan results
    try:
        r = subprocess.run(
            base + ['scan_results'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10
        )
        output = r.stdout.decode('utf-8', errors='replace')
        print('[WIFI-SCAN] wpa_cli scan_results rc={} lines={}'.format(
            r.returncode, len(output.splitlines())))
    except Exception as e:
        print('[WIFI-SCAN] wpa_cli scan_results error: {}'.format(e))
        return []

    # Parse tab-separated output: bssid / frequency / signal / flags / ssid
    networks = []
    seen     = set()
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith('bssid'):
            continue
        parts = line.split('	')
        if len(parts) < 5:
            parts = re.split(r'  +', line)
        if len(parts) < 5:
            continue
        try:
            freq   = int(parts[1].strip())
            signal = int(parts[2].strip())
            flags  = parts[3].strip()
            ssid   = parts[4].strip()
        except (IndexError, ValueError):
            continue

        if not ssid or ssid in seen:
            continue
        seen.add(ssid)

        channel = 0
        if 2412 <= freq <= 2484:
            channel = (freq - 2407) // 5
        elif 5000 <= freq <= 5885:
            channel = (freq - 5000) // 5

        if 'WPA2' in flags:
            security = 'WPA2'
        elif 'WPA' in flags:
            security = 'WPA'
        elif 'WEP' in flags:
            security = 'WEP'
        else:
            security = 'Open'

        networks.append({
            'ssid':           ssid,
            'signal_quality': signal,
            'security':       security,
            'channel':        channel,
        })

    return networks


def _scan_wifi_nmcli(iface):
    """
    Read wifi list from nmcli.
    Tries with and without explicit ifname, with and without sudo.
    """
    import subprocess
    base_fields = ['SSID', 'SIGNAL', 'SECURITY', 'CHAN']
    field_arg   = ','.join(base_fields)

    cmds = [
        ['nmcli', '--escape', 'no', '-t', '-f', field_arg,
         'dev', 'wifi', 'list', 'ifname', iface],
        ['nmcli', '--escape', 'no', '-t', '-f', field_arg,
         'dev', 'wifi', 'list'],
    ]

    for cmd in cmds:
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15
            )
            stdout = result.stdout.decode('utf-8', errors='replace')
            print('[WIFI-SCAN] nmcli rc={} lines={} cmd={}'.format(
                result.returncode, len(stdout.splitlines()), ' '.join(cmd)))

            if result.returncode != 0 or not stdout.strip():
                continue

            networks = []
            seen     = set()
            for line in stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                # nmcli -t uses ':' as separator; SSID may contain ':'
                # rsplit from right gives: [ssid_part, signal, security, chan]
                parts = line.rsplit(':', 3)
                if len(parts) < 4:
                    continue
                ssid = parts[0].strip()
                if not ssid or ssid in seen:
                    continue
                seen.add(ssid)
                try:
                    # nmcli SIGNAL is 0-100; convert to dBm approximation
                    signal_dbm = int(int(parts[1].strip()) / 2) - 100
                except Exception:
                    signal_dbm = -100
                security = parts[2].strip()
                if not security or security == '--':
                    security = 'Open'
                try:
                    channel = int(parts[3].strip())
                except Exception:
                    channel = 0
                networks.append({
                    'ssid':           ssid,
                    'signal_quality': signal_dbm,
                    'security':       security,
                    'channel':        channel,
                })

            if networks:
                print('[WIFI-SCAN] nmcli parsed {} networks'.format(len(networks)))
                return networks

        except FileNotFoundError:
            print('[WIFI-SCAN] nmcli not found')
            break
        except Exception as e:
            print('[WIFI-SCAN] nmcli error: {}'.format(e))

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
            stdout = result.stdout.decode('utf-8', errors='replace')
            stderr = result.stderr.decode('utf-8', errors='replace')
            print('[WIFI-SCAN] iw rc={} lines={} stderr={}'.format(
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
                print('[WIFI-SCAN] iw parsed {} networks'.format(len(networks)))
                return networks

        except FileNotFoundError:
            print('[WIFI-SCAN] iw not found')
            break
        except Exception as e:
            print('[WIFI-SCAN] iw error: {}'.format(e))

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
                'stdout': r.stdout.decode('utf-8', errors='replace')[:3000],
                'stderr': r.stderr.decode('utf-8', errors='replace')[:500],
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

    Flow:
      1. Check internet (ping ntp_server) -- abort if offline
      2. One-time NTP sync via ntpdate
      3. Stop NTP service (time frozen after sync)
      4. Set timezone
      5. set-local-rtc 0 (tell kernel RTC = UTC)
      6. hwclock --systohc (write synced system clock to RTC)
      7. Return updated time
    """
    user = ws_auth(request)
    if user is None:
        return web.json_response({'success': False, 'error': 'Unauthorized'}, status=401)

    try:
        body = await request.json()
    except Exception:
        body = {}

    timezone    = body.get('timezone',    'Asia/Kolkata')
    ntp_server  = body.get('ntp_server',  'time.google.com')
    date_format = body.get('date_format', 'DD/MM/YYYY')
    time_format = body.get('time_format', '24-hour')

    import subprocess as _sp, os as _os

    # ------------------------------------------------------------------
    # STEP 1: Check internet connectivity
    # ------------------------------------------------------------------
    try:
        ping = _sp.run(
            ['ping', '-c', '1', '-W', '2', ntp_server],
            stdout=_sp.PIPE, stderr=_sp.PIPE
        )
        if ping.returncode != 0:
            return web.json_response({
                'success': False,
                'error': 'No Internet Connection'
            }, status=400)
    except Exception:
        return web.json_response({
            'success': False,
            'error': 'No Internet Connection'
        }, status=400)

    # ------------------------------------------------------------------
    # STEP 2: One-time NTP sync via chronyc (ntpdate not installed)
    # Start chronyd first in case it was stopped from a previous sync
    # ------------------------------------------------------------------
    CHRONYC = '/usr/bin/chronyc'

    _sp.call(['systemctl', 'start', 'chronyd'])
    import time as _time
    _time.sleep(2)  # give daemon a moment to start

    r_step = _sp.run(
        [CHRONYC, 'makestep'],
        stdout=_sp.PIPE, stderr=_sp.PIPE, timeout=15
    )
    out_step = (r_step.stdout + r_step.stderr).decode('utf-8', errors='replace').strip()
    print('[SYNC-TIME] chronyc makestep rc={} out={}'.format(r_step.returncode, out_step))
    if r_step.returncode != 0:
        return web.json_response({
            'success': False,
            'error': 'NTP Sync Failed',
            'detail': out_step
        }, status=500)

    r_wait = _sp.run(
        [CHRONYC, 'waitsync', '6', '0.1', '0', '5'],
        stdout=_sp.PIPE, stderr=_sp.PIPE, timeout=35
    )
    out_wait = (r_wait.stdout + r_wait.stderr).decode('utf-8', errors='replace').strip()
    print('[SYNC-TIME] chronyc waitsync rc={} out={}'.format(r_wait.returncode, out_wait))

    # ------------------------------------------------------------------
    # STEP 3: Stop NTP service (time is now frozen at synced value)
    # ------------------------------------------------------------------
    _sp.call(['timedatectl', 'set-ntp', 'false'])
    _sp.call(['systemctl', 'stop', 'chronyd'])
    print('[SYNC-TIME] NTP service stopped (one-time sync complete)')

    # ------------------------------------------------------------------
    # STEP 4: Set timezone
    # ------------------------------------------------------------------
    try:
        r_tz = _sp.run(
            ['timedatectl', 'set-timezone', timezone],
            stdout=_sp.PIPE, stderr=_sp.PIPE, timeout=5
        )
        if r_tz.returncode == 0:
            print('[SYNC-TIME] timedatectl set-timezone {} OK'.format(timezone))
        else:
            raise Exception('timedatectl returned {}'.format(r_tz.returncode))
    except Exception as e:
        print('[SYNC-TIME] timedatectl failed: {}, trying symlink'.format(e))
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
                print('[SYNC-TIME] symlinked /etc/localtime -> {}'.format(tz_file))
            else:
                print('[SYNC-TIME] zoneinfo file not found: {}'.format(tz_file))
        except Exception as e2:
            print('[SYNC-TIME] timezone symlink failed: {}'.format(e2))

    # ------------------------------------------------------------------
    # STEP 5: Tell kernel RTC stores UTC
    # ------------------------------------------------------------------
    try:
        _sp.call(['timedatectl', 'set-local-rtc', '0'], timeout=5)
        print('[SYNC-TIME] timedatectl set-local-rtc 0 OK (RTC stores UTC)')
    except Exception as e:
        print('[SYNC-TIME] set-local-rtc error (non-fatal): {}'.format(e))

    # ------------------------------------------------------------------
    # STEP 6: Write synced system clock to RTC hardware
    #         Called last -- after timezone set and set-local-rtc 0
    #         so RTC gets the correct UTC value
    # ------------------------------------------------------------------
    try:
        r_hwclock = _sp.run(
            ['hwclock', '--systohc'],
            stdout=_sp.PIPE, stderr=_sp.PIPE, timeout=5
        )
        out_hwclock = (r_hwclock.stdout + r_hwclock.stderr).decode('utf-8', errors='replace').strip()
        out_hwclock = out_hwclock if out_hwclock else ('OK' if r_hwclock.returncode == 0 else 'failed')
        print('[SYNC-TIME] hwclock --systohc rc={} out={}'.format(r_hwclock.returncode, out_hwclock))
    except Exception as e:
        print('[SYNC-TIME] hwclock --systohc error (non-fatal): {}'.format(e))

    # ------------------------------------------------------------------
    # STEP 7: Update active_timezone and return updated time to UI
    # ------------------------------------------------------------------
    global active_timezone
    active_timezone = timezone

    now = get_now()

    # Format date
    if date_format == 'MM/DD/YYYY':
        formatted_date = now.strftime('%m/%d/%Y')
        iso_date       = now.strftime('%Y-%m-%d')
    elif date_format == 'YYYY-MM-DD':
        formatted_date = now.strftime('%Y-%m-%d')
        iso_date       = formatted_date
    else:
        formatted_date = now.strftime('%d/%m/%Y')
        iso_date       = now.strftime('%Y-%m-%d')

    # Format time
    if time_format == '12-hour':
        formatted_time = now.strftime('%I:%M %p')
        input_time     = now.strftime('%I:%M')
    else:
        formatted_time = now.strftime('%H:%M')
        input_time     = formatted_time

    # Update in-memory realtime state and broadcast to WebSocket clients
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
        'message':        'Time synced successfully (one-time sync)',
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