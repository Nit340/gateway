# general_config.py - Consolidated general configuration API with WebSocket support
import asyncio
import json
import datetime
import random
from aiohttp import web
from aiohttp import WSMsgType as MsgType
from database import get_general_configuration, update_general_configuration
from auth import ws_auth

# ============================================================================
# MODELS (from models.py)
# ============================================================================

# In-memory real-time state with previous values for comparison
realtime_state = {
    'current_date':        datetime.datetime.now().strftime('%Y-%m-%d'),
    'current_time':        datetime.datetime.now().strftime('%H:%M'),
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
        # signal quality in dBm (signed) arrives as net.wlan.signal_quality
        "wlan": {
            "state":           _v("net.wlan.state",           0),
            "signal_quality":  _v("net.wlan.signal_quality",  None),  # dBm signed
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

async def wifi_scan_handler(request):
    """POST /api/wifi-scan - Scan for WiFi networks and return signal strength"""
    # Auth check
    user = ws_auth(request)
    if user is None:
        return web.json_response({'success': False, 'error': 'Unauthorized'}, status=401)
    
    try:
        # Simulate signal strength (0-4)
        strength = random.randint(0, 4)
        
        # Update realtime state
        realtime_state['wifi_signal_strength'] = strength
        
        # Simulate available networks
        networks = [
            {"ssid": "Network-1", "strength": random.randint(0, 4), "security": "WPA2", "channel": 6},
            {"ssid": "Network-2", "strength": random.randint(0, 4), "security": "WPA3", "channel": 11},
            {"ssid": "Network-3", "strength": random.randint(0, 4), "security": "Open", "channel": 1},
            {"ssid": "Guest-WiFi", "strength": random.randint(0, 4), "security": "WPA2", "channel": 6},
        ]
        
        # Sort by strength (descending)
        networks.sort(key=lambda x: x['strength'], reverse=True)
        
        # Broadcast update to all WebSocket clients
        if connected_websockets:
            await broadcast_to_clients({
                'type': 'wifi_signal_update',
                'strength': strength
            })
        
        return web.json_response({
            'success': True,
            'strength': strength,
            'networks': networks,
            'message': 'WiFi scan completed successfully'
        })
        
    except Exception as e:
        print("WiFi scan error: {}".format(e))
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)


# Optional: Real WiFi scanning for Linux systems
def scan_wifi_linux():
    """Actual WiFi scanning on Linux using iwlist (optional)"""
    import subprocess
    import re
    
    try:
        # Run iwlist scan
        result = subprocess.run(['sudo', 'iwlist', 'wlan0', 'scan'], 
                               capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            return []
        
        # Parse the output
        networks = []
        cells = result.stdout.split('Cell ')
        
        for cell in cells[1:]:  # Skip first empty
            ssid_match = re.search(r'ESSID:"([^"]+)"', cell)
            quality_match = re.search(r'Quality=(\d+)/(\d+)', cell)
            channel_match = re.search(r'Channel:(\d+)', cell)
            encryption_match = re.search(r'Encryption key:(on|off)', cell)
            
            if ssid_match and quality_match:
                ssid = ssid_match.group(1)
                quality = int(quality_match.group(1))
                max_quality = int(quality_match.group(2))
                channel = int(channel_match.group(1)) if channel_match else 0
                
                # Determine security
                if encryption_match:
                    security = "WPA2" if encryption_match.group(1) == "on" else "Open"
                else:
                    security = "Unknown"
                
                # Convert to 0-4 scale
                strength = int((quality / max_quality) * 4)
                
                networks.append({
                    'ssid': ssid,
                    'strength': strength,
                    'security': security,
                    'channel': channel
                })
        
        return networks
    except Exception as e:
        print("Error scanning WiFi: {}".format(e))
        return []


# ============================================================================
# UTILS (from utils.py, simplified)
# ============================================================================

async def periodic_updates():
    """Update real-time state only when changes occur."""
    while True:
        try:
            # Update time
            new_date = datetime.datetime.now().strftime('%Y-%m-%d')
            new_time = datetime.datetime.now().strftime('%H:%M')
            
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
    
    # WiFi scan endpoint
    app.router.add_post('/api/wifi-scan', wifi_scan_handler)
    
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