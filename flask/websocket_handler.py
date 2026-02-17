# websocket_handler.py - Optimized WebSocket handlers
import asyncio
import json
import datetime
from aiohttp import web
import aiohttp

from models import (
    realtime_state, previous_state, connected_websockets,
    device_status_tracker, device_websockets
)

async def websocket_handler(request):
    """Handle WebSocket connections for real-time updates"""
    ws = web.WebSocketResponse()
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
        
        await ws.send_json(initial_data)
        
        # Update previous state
        previous_state['current_date'] = realtime_state['current_date']
        previous_state['current_time'] = realtime_state['current_time']
        
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    
                    if data.get('type') == 'sync_time':
                        # Update time in memory
                        new_date = datetime.datetime.now().strftime('%Y-%m-%d')
                        new_time = datetime.datetime.now().strftime('%H:%M')
                        
                        # Only update if changed
                        if new_date != realtime_state['current_date'] or new_time != realtime_state['current_time']:
                            realtime_state['current_date'] = new_date
                            realtime_state['current_time'] = new_time
                            
                            # Broadcast to all clients
                            broadcast_data = {
                                'type': 'time_update',
                                'current_date': new_date,
                                'current_time': new_time
                            }
                            
                            await broadcast_to_clients(broadcast_data)
                        
                        # Send confirmation
                        await ws.send_json({
                            'type': 'time_synced',
                            'current_date': realtime_state['current_date'],
                            'current_time': realtime_state['current_time']
                        })
                    
                    elif data.get('type') == 'ping':
                        await ws.send_json({'type': 'pong'})
                        
                except json.JSONDecodeError:
                    await ws.send_json({
                        'type': 'error',
                        'message': 'Invalid JSON format'
                    })
            elif msg.type == aiohttp.WSMsgType.ERROR:
                print('WebSocket connection closed with exception {}'.format(ws.exception()))
                break
                    
    except Exception as e:
        print("WebSocket error: {}".format(e))
    finally:
        connected_websockets.discard(ws)
        print("WebSocket disconnected. Total clients: {}".format(len(connected_websockets)))
    
    return ws

async def device_websocket_handler(request):
    """WebSocket for real-time device status updates - ONE CONNECTION PER PAGE"""
    ws = web.WebSocketResponse(heartbeat=30)  # Add heartbeat to detect dead connections
    await ws.prepare(request)
    
    # Check if there's already a connection from this session
    # Only allow one device WebSocket connection at a time
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
            await ws.send_json({
                'type': 'initial_devices',
                'devices': initial_devices
            })
        
        # Listen for messages (mainly ping/pong)
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    
                    if data.get('type') == 'ping':
                        await ws.send_json({'type': 'pong'})
                        
                except json.JSONDecodeError:
                    await ws.send_json({
                        'type': 'error',
                        'message': 'Invalid JSON format'
                    })
            elif msg.type == aiohttp.WSMsgType.ERROR:
                print('Device WebSocket connection closed with exception {}'.format(ws.exception()))
                break
                    
    except Exception as e:
        print("Device WebSocket error: {}".format(e))
    finally:
        device_websockets.discard(ws)
        print("Device WebSocket disconnected. Total clients: {}".format(len(device_websockets)))
    
    return ws

async def broadcast_to_clients(data):
    """Helper to broadcast data to all connected WebSocket clients - NON-BLOCKING"""
    if not connected_websockets:
        return
    
    # Use asyncio.gather for parallel sending without blocking
    tasks = []
    for ws in list(connected_websockets):
        if not ws.closed:
            tasks.append(safe_send(ws, data))
    
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

async def broadcast_device_status(device_id, status, last_poll):
    """Broadcast device status updates to all WebSocket clients - NON-BLOCKING"""
    if not device_websockets:
        return
    
    data = {
        'type': 'device_status',
        'device_id': device_id,
        'status': status,
        'last_poll': last_poll
    }
    
    # Use asyncio.gather for parallel sending without blocking
    tasks = []
    for ws in list(device_websockets):
        if not ws.closed:
            tasks.append(safe_send(ws, data))
    
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

async def safe_send(ws, data):
    """Safely send data to a WebSocket, removing it if closed"""
    try:
        if not ws.closed:
            await ws.send_json(data)
    except Exception as e:
        print("Error sending to WebSocket: {}".format(e))
        # Remove from sets if it's there
        device_websockets.discard(ws)
        connected_websockets.discard(ws)