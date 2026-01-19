# websocket_handler.py - All WebSocket handlers
import asyncio
import json
import random
import datetime
from aiohttp import web
import aiohttp

from models import (
    realtime_state, previous_state, connected_websockets,
    device_status_tracker, device_websockets
)
from database import get_configuration

async def websocket_handler(request):
    """Handle WebSocket connections for real-time updates"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    connected_websockets.add(ws)
    print("WebSocket connected. Total clients: {}".format(len(connected_websockets)))
    
    try:
        # Get current config
        config = get_configuration()
        network_mode = config.get('network', {}).get('mode', 'ethernet')
        wifi_configured = network_mode == 'wifi' and config.get('network', {}).get('wifi', {}).get('ssid')
        
        # Prepare initial data
        initial_data = {
            'type': 'initial',
            'current_date': realtime_state['current_date'],
            'current_time': realtime_state['current_time']
        }
        
        # Only include signal strength if WiFi is configured
        if wifi_configured:
            initial_data['wifi_signal_strength'] = realtime_state['wifi_signal_strength']
        
        await ws.send_json(initial_data)
        
        # Update previous state
        previous_state['current_date'] = realtime_state['current_date']
        previous_state['current_time'] = realtime_state['current_time']
        previous_state['wifi_signal_strength'] = realtime_state['wifi_signal_strength'] if wifi_configured else None
        previous_state['wifi_configured'] = wifi_configured
        
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
                            
                            for client in connected_websockets:
                                try:
                                    await client.send_json(broadcast_data)
                                except:
                                    pass
                        
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
                    
    except Exception as e:
        print("WebSocket error: {}".format(e))
    finally:
        connected_websockets.remove(ws)
        print("WebSocket disconnected. Total clients: {}".format(len(connected_websockets)))
    
    return ws

async def device_websocket_handler(request):
    """WebSocket for real-time device status updates"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    device_websockets.add(ws)
    print("Device WebSocket connected. Total clients: {}".format(len(device_websockets)))
    
    try:
        # Send initial device status
        for device_id, status in device_status_tracker.items():
            await ws.send_json({
                'type': 'device_status',
                'device_id': device_id,
                'status': status['status'],
                'last_poll': status['last_poll']
            })
        
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
                    
    except Exception as e:
        print("Device WebSocket error: {}".format(e))
    finally:
        device_websockets.remove(ws)
        print("Device WebSocket disconnected. Total clients: {}".format(len(device_websockets)))
    
    return ws

async def broadcast_to_clients(data):
    """Helper to broadcast data to all connected WebSocket clients"""
    if not connected_websockets:
        return
    
    disconnected_clients = set()
    
    for ws in connected_websockets:
        try:
            await ws.send_json(data)
        except Exception as e:
            print("Error sending to WebSocket client: {}".format(e))
            disconnected_clients.add(ws)
    
    # Remove disconnected clients
    for ws in disconnected_clients:
        connected_websockets.remove(ws)

async def broadcast_device_status(device_id, status, last_poll):
    """Broadcast device status updates to all WebSocket clients"""
    if not device_websockets:
        return
    
    data = {
        'type': 'device_status',
        'device_id': device_id,
        'status': status,
        'last_poll': last_poll
    }
    
    disconnected_clients = set()
    
    for ws in device_websockets:
        try:
            await ws.send_json(data)
        except Exception as e:
            print("Error sending device status to WebSocket: {}".format(e))
            disconnected_clients.add(ws)
    
    for ws in disconnected_clients:
        device_websockets.remove(ws)