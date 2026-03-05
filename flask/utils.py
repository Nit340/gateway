# utils.py - Optimized utility functions and background tasks
import asyncio
import datetime
from models import (
    realtime_state, previous_state,
    device_status_tracker, connected_websockets
)
from websocket_handler import broadcast_to_clients

async def periodic_updates():
    """Update real-time state only when changes occur - OPTIMIZED"""
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
                
                # Broadcast time update ONLY if changed AND clients are connected
                if connected_websockets and (date_changed or time_changed):
                    await broadcast_to_clients({
                        'type': 'time_update',
                        'current_date': new_date,
                        'current_time': new_time
                    })
            
            # Smart sleep interval - check every minute when no clients
            if connected_websockets:
                # Clients connected - check every 30 seconds
                await asyncio.sleep(30)
            else:
                # No clients - check every minute
                await asyncio.sleep(60)
            
        except Exception as e:
            print("Error in periodic updates: {}".format(e))
            await asyncio.sleep(60)


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
            device_status_tracker[device_id]['last_offline_time'] = datetime.datetime.now()
    return device_status_tracker[device_id]

def update_device_status(device_id, status, last_poll=None):
    """Manually update device status (for testing or external triggers)"""
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
            device_status_tracker[device_id]['last_offline_time'] = datetime.datetime.now()
    
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