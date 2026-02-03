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
    """Update device status periodically"""
    while True:
        try:
            # Update device status randomly
            for device_id in list(device_status_tracker.keys()):
                if random.random() < 0.1:  # 10% chance to change status
                    if device_status_tracker[device_id]['status'] == 'Online' and random.random() < 0.05:
                        device_status_tracker[device_id]['status'] = 'Offline'
                        device_status_tracker[device_id]['last_poll'] = f"{random.randint(1, 60)} sec ago"
                    elif device_status_tracker[device_id]['status'] == 'Offline' and random.random() < 0.2:
                        device_status_tracker[device_id]['status'] = 'Online'
                        device_status_tracker[device_id]['last_poll'] = 'Just now'
                    else:
                        # Update last poll time
                        if device_status_tracker[device_id]['status'] == 'Online':
                            seconds_ago = random.choice([1, 2, 5, 10])
                            device_status_tracker[device_id]['last_poll'] = f"{seconds_ago} sec ago"
            
            await asyncio.sleep(5)  # Update every 5 seconds
            
        except Exception as e:
            print(f"Error in device status updater: {e}")
            await asyncio.sleep(5)