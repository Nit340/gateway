# websocket_handler.py - aiohttp 2.0.7 / Python 3.5 compatible

import asyncio
import json
import datetime
from aiohttp import web

from auth import ws_auth
from models import (
    realtime_state, connected_websockets,
    device_status_tracker
)

# aiohttp 2.0.7 exposes MsgType on the WebSocketResponse class itself
# Fall back to integer constants if the import path differs
try:
    from aiohttp import MsgType as _MT
except ImportError:
    try:
        from aiohttp.web import MsgType as _MT
    except ImportError:
        # Last resort: use the integer values directly
        # text=1, binary=2, ping=9, pong=10, close=8, error=258
        class _MT:
            text  = 1
            binary = 2
            ping  = 9
            pong  = 10
            close = 8
            error = 258


async def websocket_handler(request):
    """Handle WebSocket connections for real-time updates."""

    user = ws_auth(request)
    if user is None:
        return web.Response(status=401, text='Unauthorized')

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    connected_websockets.add(ws)
    print("WebSocket connected (user={}). Total clients: {}".format(
        user, len(connected_websockets)))

    try:
        await ws.send_str(json.dumps({
            'type':                 'initial',
            'current_date':         realtime_state['current_date'],
            'current_time':         realtime_state['current_time'],
            'wifi_signal_strength': realtime_state.get('wifi_signal_strength', 3)
        }))

        while True:
            msg = await ws.receive()

            # aiohttp 2.x uses msg.tp; 3.x uses msg.type — support both
            tp = getattr(msg, 'tp', None) or getattr(msg, 'type', None)

            if tp == _MT.close:
                break

            elif tp == _MT.error:
                print('WebSocket error (user={}): {}'.format(user, ws.exception()))
                break

            elif tp == _MT.ping:
                await ws.pong()

            elif tp == _MT.text:
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


async def broadcast_to_clients(data):
    """Broadcast a dict to all connected WebSocket clients."""
    if not connected_websockets:
        return
    payload = json.dumps(data)
    await asyncio.gather(
        *[_safe_send(ws, payload, connected_websockets)
          for ws in list(connected_websockets) if not ws.closed],
        return_exceptions=True
    )


async def _safe_send(ws, payload, ws_set):
    """Send payload; discard socket from its set on failure."""
    try:
        if not ws.closed:
            await ws.send_str(payload)
    except Exception as e:
        print("Error sending to WebSocket: {}".format(e))
        ws_set.discard(ws)


async def safe_send(ws, payload):
    """Deprecated alias."""
    await _safe_send(ws, payload, connected_websockets)