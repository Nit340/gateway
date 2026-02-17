# utils.py - Optimized utility functions and background tasks
import asyncio
import random
import datetime
from models import (
    realtime_state, previous_state,
    device_status_tracker, connected_websockets, device_websockets
)
from websocket_handler import broadcast_to_clients, broadcast_device_status

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

async def device_status_updater():
    """Update device status periodically - OPTIMIZED to only broadcast changes"""
    while True:
        try:
            # Only update if there are devices AND clients listening
            if not device_status_tracker or not device_websockets:
                await asyncio.sleep(10)
                continue
            
            # Track which devices had status changes
            changed_devices = []
            
            # Update device status with realistic patterns
            for device_id in list(device_status_tracker.keys()):
                device_info = device_status_tracker[device_id]
                current_status = device_info['status']
                previous_status = device_info.get('previous_status', current_status)
                previous_poll = device_info.get('previous_poll', device_info['last_poll'])
                
                if current_status == 'Online':
                    # Online devices poll regularly
                    seconds_ago = random.choice([2, 3, 5, 8, 10])
                    device_info['last_poll'] = "{} sec ago".format(seconds_ago)
                    
                    # Very small chance to go offline (0.5% per update)
                    if random.random() < 0.005:
                        device_info['previous_status'] = device_info['status']
                        device_info['previous_poll'] = device_info['last_poll']
                        device_info['status'] = 'Offline'
                        device_info['last_poll'] = 'Connection lost'
                        changed_devices.append(device_id)
                    else:
                        # Only broadcast poll updates occasionally (every 30 seconds on average)
                        if random.random() < 0.1:  # 10% chance = ~10 seconds average
                            if device_info['last_poll'] != previous_poll:
                                device_info['previous_poll'] = device_info['last_poll']
                                changed_devices.append(device_id)
                
                elif current_status == 'Offline':
                    # Offline devices have static last poll
                    if 'last_offline_time' not in device_info:
                        device_info['last_offline_time'] = datetime.datetime.now()
                    
                    # Calculate how long it's been offline
                    offline_duration = (datetime.datetime.now() - device_info['last_offline_time']).seconds
                    
                    if offline_duration < 60:
                        new_poll = "{} sec ago".format(offline_duration)
                    elif offline_duration < 3600:
                        minutes = offline_duration // 60
                        new_poll = "{} min ago".format(minutes)
                    else:
                        hours = offline_duration // 3600
                        new_poll = "{} hr ago".format(hours)
                    
                    # Only update if the time description changed
                    if new_poll != device_info['last_poll']:
                        device_info['previous_poll'] = device_info['last_poll']
                        device_info['last_poll'] = new_poll
                        # Don't broadcast every second change for offline devices
                        if offline_duration % 60 == 0:  # Only every minute
                            changed_devices.append(device_id)
                    
                    # Small chance to come back online (2% per update)
                    if random.random() < 0.02:
                        device_info['previous_status'] = device_info['status']
                        device_info['previous_poll'] = device_info['last_poll']
                        device_info['status'] = 'Online'
                        device_info['last_poll'] = 'Just now'
                        if 'last_offline_time' in device_info:
                            del device_info['last_offline_time']
                        changed_devices.append(device_id)
            
            # Broadcast ONLY devices that changed
            if changed_devices and device_websockets:
                for device_id in changed_devices:
                    device_info = device_status_tracker[device_id]
                    await broadcast_device_status(
                        device_id,
                        device_info['status'],
                        device_info['last_poll']
                    )
            
            # Update every 10 seconds (less aggressive)
            await asyncio.sleep(10)
            
        except Exception as e:
            print("Error in device status updater: {}".format(e))
            await asyncio.sleep(10)

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