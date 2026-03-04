# websocket_handler.py - WebSocket handlers compatible with aiohttp 2.0.7 / Python 3.5
#
# BUGS FIXED:
#   1. _WS_ERROR=258 was wrong for aiohttp 2.0.7 — replaced with aiohttp.MsgType enum
#   2. No auth on either WS handler — added ws_auth() check before ws.prepare()
#   3. Ping frames not handled — added MsgType.ping -> ws.pong() in both loops
#   4. safe_send discarded from both sets — now takes owning set as parameter
#   5. previous_state written per-client — removed from WS handler, owned by periodic_updates only

import asyncio
import json
import datetime
from aiohttp import web
from aiohttp import WSMsgType as MsgType   # aiohttp 3.x uses WSMsgType; alias as MsgType for clarity

from auth import ws_auth
from models import (
    realtime_state, connected_websockets,
    device_status_tracker, device_websockets
)


async def websocket_handler(request):
    """Handle WebSocket connections for real-time updates."""

    # FIX 2: Auth check — middleware skips WS upgrades so we must check here
    user = ws_auth(request)
    if user is None:
        return web.Response(status=401, text='Unauthorized')

    ws = web.WebSocketResponse()  # No heartbeat= kwarg (added in aiohttp 2.3+)
    await ws.prepare(request)

    connected_websockets.add(ws)
    print("WebSocket connected (user={}). Total clients: {}".format(
        user, len(connected_websockets)))

    try:
        # Send initial state to the newly connected client
        await ws.send_str(json.dumps({
            'type':                 'initial',
            'current_date':         realtime_state['current_date'],
            'current_time':         realtime_state['current_time'],
            'wifi_signal_strength': realtime_state.get('wifi_signal_strength', 3)
        }))

        # FIX 5: Do NOT write previous_state here — that is owned by periodic_updates()
        #         Writing it here caused a multi-client race where client B connecting
        #         would reset the change-detection baseline for client A's next broadcast.

        while True:
            msg = await ws.receive()

            # FIX 1: Use aiohttp.MsgType enum — _WS_ERROR=258 was wrong for aiohttp 2.0.7
            if msg.type == MsgType.close:
                break

            elif msg.type == MsgType.error:
                print('WebSocket error (user={}): {}'.format(user, ws.exception()))
                break

            # FIX 3: Echo pong for every ping — prevents proxy from killing idle connections
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
                        # Return current wifi signal strength (0–4 scale)
                        # In production, read from OS (e.g. iwconfig / nmcli)
                        # For now, return the last known value from realtime_state
                        strength = realtime_state.get('wifi_signal_strength', 3)
                        await ws.send_str(json.dumps({
                            'type':     'wifi_signal_update',
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
        print("WebSocket disconnected (user={}). Total clients: {}".format(
            user, len(connected_websockets)))

    return ws


async def device_websocket_handler(request):
    """WebSocket for real-time device status updates."""

    # FIX 2: Auth check
    user = ws_auth(request)
    if user is None:
        return web.Response(status=401, text='Unauthorized')

    ws = web.WebSocketResponse()  # No heartbeat= kwarg
    await ws.prepare(request)

    device_websockets.add(ws)
    print("Device WebSocket connected (user={}). Total clients: {}".format(
        user, len(device_websockets)))

    try:
        # Send current status of ALL known devices immediately on connect
        initial_devices = [
            {
                'device_id': device_id,
                'status': info['status'],
                'last_poll': info['last_poll']
            }
            for device_id, info in device_status_tracker.items()
        ]

        if initial_devices:
            await ws.send_str(json.dumps({
                'type': 'initial_devices',
                'devices': initial_devices
            }))

        while True:
            msg = await ws.receive()

            # FIX 1: Use MsgType enum
            if msg.type == MsgType.close:
                break

            elif msg.type == MsgType.error:
                print('Device WebSocket error (user={}): {}'.format(user, ws.exception()))
                break

            # FIX 3: Respond to pings
            elif msg.type == MsgType.ping:
                await ws.pong()

            elif msg.type == MsgType.text:
                try:
                    data = json.loads(msg.data)

                    if data.get('type') == 'ping':
                        await ws.send_str(json.dumps({'type': 'pong'}))

                except (ValueError, KeyError):
                    await ws.send_str(json.dumps({
                        'type': 'error',
                        'message': 'Invalid JSON format'
                    }))

    except Exception as e:
        print("Device WebSocket error (user={}): {}".format(user, e))
    finally:
        device_websockets.discard(ws)
        print("Device WebSocket disconnected (user={}). Total clients: {}".format(
            user, len(device_websockets)))

    return ws


# ─── Broadcast helpers ────────────────────────────────────────────────────────

async def broadcast_to_clients(data):
    """Broadcast a dict to all connected general WebSocket clients."""
    if not connected_websockets:
        return
    payload = json.dumps(data)
    await asyncio.gather(
        *[_safe_send(ws, payload, connected_websockets)
          for ws in list(connected_websockets) if not ws.closed],
        return_exceptions=True
    )


async def broadcast_device_status(device_id, status, last_poll):
    """Broadcast a device-status update to all device WebSocket clients."""
    if not device_websockets:
        return
    payload = json.dumps({
        'type': 'device_status',
        'device_id': device_id,
        'status': status,
        'last_poll': last_poll
    })
    await asyncio.gather(
        *[_safe_send(ws, payload, device_websockets)
          for ws in list(device_websockets) if not ws.closed],
        return_exceptions=True
    )


async def _safe_send(ws, payload, ws_set):
    """Send payload to one WebSocket; discard ONLY from the owning set on failure.

    FIX 4: The old safe_send() always discarded from BOTH sets, which was wrong.
    Each socket belongs to exactly one set. Passing ws_set explicitly keeps cleanup precise.
    """
    try:
        if not ws.closed:
            await ws.send_str(payload)
    except Exception as e:
        print("Error sending to WebSocket: {}".format(e))
        ws_set.discard(ws)


# Backwards-compatible alias so any existing callers don't break
async def safe_send(ws, payload):
    """Deprecated — use _safe_send(ws, payload, ws_set) instead."""
    if ws in connected_websockets:
        await _safe_send(ws, payload, connected_websockets)
    else:
        await _safe_send(ws, payload, device_websockets)