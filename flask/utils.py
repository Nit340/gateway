# utils.py - Utility functions and background tasks
import asyncio
import random
import datetime
from models import (
    realtime_state, previous_state,
    device_status_tracker, connected_websockets
)
from websocket_handler import broadcast_to_clients, broadcast_device_status

async def periodic_updates():
    """Update real-time state only when changes occur"""
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
                
                # Broadcast time update only if changed
                if connected_websockets and (date_changed or time_changed):
                    await broadcast_to_clients({
                        'type': 'time_update',
                        'current_date': new_date,
                        'current_time': new_time
                    })
            
            # Sleep with different intervals based on activity
            if connected_websockets:
                # If clients are connected, check more frequently
                await asyncio.sleep(0.5)
            else:
                # No clients connected, check less frequently
                await asyncio.sleep(5)
            
        except Exception as e:
            print(f"Error in periodic updates: {e}")
            await asyncio.sleep(5)

async def device_status_updater():
    """Update device status periodically with realistic behavior"""
    while True:
        try:
            # Only update if there are devices being tracked
            if not device_status_tracker:
                await asyncio.sleep(5)
                continue
            
            # Update device status with more realistic patterns
            for device_id in list(device_status_tracker.keys()):
                device_info = device_status_tracker[device_id]
                current_status = device_info['status']
                
                # Simulate realistic device behavior
                if current_status == 'Online':
                    # Online devices poll regularly
                    seconds_ago = random.choice([1, 2, 3, 5, 10])
                    device_info['last_poll'] = f"{seconds_ago} sec ago"
                    
                    # Small chance to go offline (1% per update)
                    if random.random() < 0.01:
                        device_info['status'] = 'Offline'
                        device_info['last_poll'] = 'Connection lost'
                        
                        # Broadcast status change
                        await broadcast_device_status(
                            device_id,
                            device_info['status'],
                            device_info['last_poll']
                        )
                    else:
                        # Just update poll time (no need to broadcast every time)
                        # Only broadcast every 10 seconds or on status change
                        if random.random() < 0.2:  # 20% chance to broadcast poll update
                            await broadcast_device_status(
                                device_id,
                                device_info['status'],
                                device_info['last_poll']
                            )
                
                elif current_status == 'Offline':
                    # Offline devices have static last poll
                    if 'last_offline_time' not in device_info:
                        device_info['last_offline_time'] = datetime.datetime.now()
                    
                    # Calculate how long it's been offline
                    offline_duration = (datetime.datetime.now() - device_info['last_offline_time']).seconds
                    
                    if offline_duration < 60:
                        device_info['last_poll'] = f"{offline_duration} sec ago"
                    elif offline_duration < 3600:
                        minutes = offline_duration // 60
                        device_info['last_poll'] = f"{minutes} min ago"
                    else:
                        hours = offline_duration // 3600
                        device_info['last_poll'] = f"{hours} hr ago"
                    
                    # Small chance to come back online (5% per update)
                    if random.random() < 0.05:
                        device_info['status'] = 'Online'
                        device_info['last_poll'] = 'Just now'
                        if 'last_offline_time' in device_info:
                            del device_info['last_offline_time']
                        
                        # Broadcast status change
                        await broadcast_device_status(
                            device_id,
                            device_info['status'],
                            device_info['last_poll']
                        )
            
            # Update every 5 seconds
            await asyncio.sleep(5)
            
        except Exception as e:
            print(f"Error in device status updater: {e}")
            await asyncio.sleep(5)

def initialize_device_status(device_id, initial_status='Offline'):
    """Initialize device status when device is created"""
    if device_id not in device_status_tracker:
        device_status_tracker[device_id] = {
            'status': initial_status,
            'last_poll': 'Never' if initial_status == 'Offline' else 'Just now'
        }
        if initial_status == 'Offline':
            device_status_tracker[device_id]['last_offline_time'] = datetime.datetime.now()
    return device_status_tracker[device_id]

def update_device_status(device_id, status, last_poll=None):
    """Manually update device status (for testing or external triggers)"""
    if device_id not in device_status_tracker:
        initialize_device_status(device_id, status)
    else:
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