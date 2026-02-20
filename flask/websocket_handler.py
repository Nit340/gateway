# websocket_handler.py - WebSocket handlers compatible with aiohttp 2.0.7 / Python 3.5
#
# FIXES vs original:
#   1. Removed heartbeat= kwarg from WebSocketResponse (added in aiohttp 2.3+)
#   2. MsgType/WSMsgType unreliable across versions -- use raw integer constants instead
#   3. msg.type -> msg.tp                    (msg.type added in aiohttp 2.3+)
#   4. async for msg in ws -> while loop with ws.receive()  (async iteration added later)
#   5. ws.send_json() -> ws.send_str(json.dumps())          (send_json added in aiohttp 2.3+)

import asyncio
import json
import datetime
from aiohttp import web
import aiohttp

# Raw WebSocket opcode integers -- valid for all aiohttp versions including 2.0.7.
# Avoids importing MsgType/WSMsgType which moved between aiohttp versions.
_WS_TEXT  = 1    # text frame
_WS_CLOSE = 8    # connection close
_WS_PING  = 9    # ping
_WS_PONG  = 10   # pong
_WS_ERROR = 258  # aiohttp internal error sentinel

from models import (
    realtime_state, previous_state, connected_websockets,
    device_status_tracker, device_websockets
)

async def websocket_handler(request):
    """Handle WebSocket connections for real-time updates"""
    ws = web.WebSocketResponse()          # FIX 1: no heartbeat= kwarg
    await ws.prepare(request)

    connected_websockets.add(ws)
    print("WebSocket connected. Total clients: {}".format(len(connected_websockets)))

    try:
        # Send initial data
        initial_data = {
            'type': 'initial',
            'current_date': realtime_state['current_date'],
            'current_time': realtime_state['current_time']
        }
        await ws.send_str(json.dumps(initial_data))  # FIX 5

        previous_state['current_date'] = realtime_state['current_date']
        previous_state['current_time'] = realtime_state['current_time']

        # FIX 3+4: while loop + msg.tp + raw int constants
        while True:
            msg = await ws.receive()

            if msg.tp == _WS_CLOSE:
                break

            elif msg.tp == _WS_ERROR:
                print('WebSocket connection closed with exception {}'.format(ws.exception()))
                break

            elif msg.tp == _WS_TEXT:
                try:
                    data = json.loads(msg.data)

                    if data.get('type') == 'sync_time':
                        new_date = datetime.datetime.now().strftime('%Y-%m-%d')
                        new_time = datetime.datetime.now().strftime('%H:%M')

                        if (new_date != realtime_state['current_date'] or
                                new_time != realtime_state['current_time']):
                            realtime_state['current_date'] = new_date
                            realtime_state['current_time'] = new_time

                            broadcast_data = {
                                'type': 'time_update',
                                'current_date': new_date,
                                'current_time': new_time
                            }
                            await broadcast_to_clients(broadcast_data)

                        await ws.send_str(json.dumps({   # FIX 5
                            'type': 'time_synced',
                            'current_date': realtime_state['current_date'],
                            'current_time': realtime_state['current_time']
                        }))

                    elif data.get('type') == 'ping':
                        await ws.send_str(json.dumps({'type': 'pong'}))  # FIX 5

                except (ValueError, KeyError) as e:
                    await ws.send_str(json.dumps({       # FIX 5
                        'type': 'error',
                        'message': 'Invalid JSON format'
                    }))

    except Exception as e:
        print("WebSocket error: {}".format(e))
    finally:
        connected_websockets.discard(ws)
        print("WebSocket disconnected. Total clients: {}".format(len(connected_websockets)))

    return ws


async def device_websocket_handler(request):
    """WebSocket for real-time device status updates"""
    ws = web.WebSocketResponse()          # FIX 1: no heartbeat=
    await ws.prepare(request)

    device_websockets.add(ws)
    print("Device WebSocket connected. Total clients: {}".format(len(device_websockets)))

    try:
        # Send initial device status for ALL devices
        initial_devices = []
        for device_id, status in device_status_tracker.items():
            initial_devices.append({
                'device_id': device_id,
                'status': status['status'],
                'last_poll': status['last_poll']
            })

        if initial_devices:
            await ws.send_str(json.dumps({              # FIX 5
                'type': 'initial_devices',
                'devices': initial_devices
            }))

        # FIX 3+4: while loop + msg.tp + raw int constants
        while True:
            msg = await ws.receive()

            if msg.tp == _WS_CLOSE:
                break

            elif msg.tp == _WS_ERROR:
                print('Device WebSocket closed with exception {}'.format(ws.exception()))
                break

            elif msg.tp == _WS_TEXT:
                try:
                    data = json.loads(msg.data)

                    if data.get('type') == 'ping':
                        await ws.send_str(json.dumps({'type': 'pong'}))  # FIX 5

                except (ValueError, KeyError):
                    await ws.send_str(json.dumps({       # FIX 5
                        'type': 'error',
                        'message': 'Invalid JSON format'
                    }))

    except Exception as e:
        print("Device WebSocket error: {}".format(e))
    finally:
        device_websockets.discard(ws)
        print("Device WebSocket disconnected. Total clients: {}".format(len(device_websockets)))

    return ws


async def broadcast_to_clients(data):
    """Broadcast data to all connected WebSocket clients"""
    if not connected_websockets:
        return

    payload = json.dumps(data)
    tasks = []
    for ws in list(connected_websockets):
        if not ws.closed:
            tasks.append(safe_send(ws, payload))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def broadcast_device_status(device_id, status, last_poll):
    """Broadcast device status updates to all WebSocket clients"""
    if not device_websockets:
        return

    payload = json.dumps({                              # FIX 5
        'type': 'device_status',
        'device_id': device_id,
        'status': status,
        'last_poll': last_poll
    })

    tasks = []
    for ws in list(device_websockets):
        if not ws.closed:
            tasks.append(safe_send(ws, payload))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def safe_send(ws, payload):
    """Safely send a pre-serialized JSON string to a WebSocket"""
    try:
        if not ws.closed:
            await ws.send_str(payload)                  # FIX 5
    except Exception as e:
        print("Error sending to WebSocket: {}".format(e))
        device_websockets.discard(ws)
        connected_websockets.discard(ws)