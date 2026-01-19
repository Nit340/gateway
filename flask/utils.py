# utils.py - Utility functions and background tasks
import asyncio
import random
import datetime
from models import (
    realtime_state, previous_state, current_network_mode,
    device_status_tracker, connected_websockets
)
from websocket_handler import broadcast_to_clients, broadcast_device_status
from database import get_configuration

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
            
            # Get current config to check WiFi mode (less frequent check)
            if random.random() < 0.1:  # Check WiFi config only 10% of the time
                config = get_configuration()
                network_mode = config.get('network', {}).get('mode', 'ethernet')
                wifi_configured = network_mode == 'wifi' and config.get('network', {}).get('wifi', {}).get('ssid')
                
                # Check if WiFi configuration status changed
                wifi_config_changed = wifi_configured != previous_state['wifi_configured']
                
                if wifi_config_changed:
                    previous_state['wifi_configured'] = wifi_configured
                    print("WiFi config changed: {}".format('Enabled' if wifi_configured else 'Disabled'))
                
                # Update WiFi signal only if WiFi is configured
                if wifi_configured:
                    # Occasionally update signal strength (10% chance per check)
                    if random.random() < 0.1:
                        change = random.choice([-1, 0, 1])
                        new_strength = max(0, min(4, realtime_state['wifi_signal_strength'] + change))
                        
                        # Only send update if signal actually changed
                        if new_strength != previous_state['wifi_signal_strength']:
                            realtime_state['wifi_signal_strength'] = new_strength
                            previous_state['wifi_signal_strength'] = new_strength
                            
                            # Broadcast signal update
                            if connected_websockets:
                                await broadcast_to_clients({
                                    'type': 'wifi_signal_update',
                                    'strength': new_strength
                                })
                else:
                    # WiFi is not configured, clear previous signal strength
                    if previous_state['wifi_signal_strength'] is not None:
                        previous_state['wifi_signal_strength'] = None
            
            # Sleep with different intervals based on activity
            if connected_websockets:
                # If clients are connected, check more frequently (but still only send on changes)
                await asyncio.sleep(0.5)
            else:
                # No clients connected, check less frequently
                await asyncio.sleep(5)
            
        except Exception as e:
            print("Error in periodic updates: {}".format(e))
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
                        device_status_tracker[device_id]['last_poll'] = '{} sec ago'.format(random.randint(1, 60))
                    elif device_status_tracker[device_id]['status'] == 'Offline' and random.random() < 0.2:
                        device_status_tracker[device_id]['status'] = 'Online'
                        device_status_tracker[device_id]['last_poll'] = 'Just now'
                    else:
                        # Update last poll time
                        if device_status_tracker[device_id]['status'] == 'Online':
                            seconds_ago = random.choice([1, 2, 5, 10])
                            device_status_tracker[device_id]['last_poll'] = '{} sec ago'.format(seconds_ago)
            
            await asyncio.sleep(5)  # Update every 5 seconds
            
        except Exception as e:
            print("Error in device status updater: {}".format(e))
            await asyncio.sleep(5)