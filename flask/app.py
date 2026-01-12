# app.py - Optimized WebSocket updates (only on changes) - Python 3.5 compatible
import aiohttp
from aiohttp import web
import asyncio
import json
import datetime
import sqlite3
import random
from typing import Dict, Any

# Database setup
DB_FILE = 'gateway_config.db'

# In-memory real-time state with previous values for comparison
realtime_state = {
    'current_date': datetime.datetime.now().strftime('%Y-%m-%d'),
    'current_time': datetime.datetime.now().strftime('%H:%M'),
    'wifi_signal_strength': 3  # Default signal strength
}

# Track previous values to detect changes
previous_state = {
    'current_date': '',
    'current_time': '',
    'wifi_signal_strength': None,
    'wifi_configured': False
}

# Track network mode to detect changes
current_network_mode = 'ethernet'

# Default configuration (single JSON in database)
DEFAULT_CONFIG = {
    'gateway_identity': {
        'name': 'Univa-GW-01',
        'serial_number': 'GW2025-1190021',
        'deployment_site': 'Chennai Port - Zone A',
        'location_mode': 'manual',
        'latitude': 12.99123,
        'longitude': 80.12312,
        'asset_id': 'CRN-CT-12'
    },
    'date_time': {
        'timezone': 'Asia/Kolkata',
        'ntp_server': 'pool.ntp.org',
        'date_format': 'DD/MM/YYYY',
        'time_format': '24-hour',
        'language': 'en'
    },
    'network': {
        'mode': 'ethernet',
        'ethernet': {
            'ip_assignment': 'dhcp',
            'static_ip': '192.168.1.50',
            'subnet_mask': '255.255.255.0',
            'gateway': '192.168.1.1',
            'dns1': '8.8.8.8',
            'dns2': '8.8.4.4'
        }
    },
    'heartbeat': {
        'interval': 30,
        'offline_threshold': 120
    },
    'mac_address': '00:1A:2B:3C:4D:5E'
}


def init_database():
    """Initialize SQLite database with single JSON field"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS general_configuration (
            id INTEGER PRIMARY KEY,
            config_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('SELECT COUNT(*) FROM general_configuration')
    count = cursor.fetchone()[0]
    
    if count == 0:
        cursor.execute('''
            INSERT INTO general_configuration (config_json)
            VALUES (?)
        ''', (json.dumps(DEFAULT_CONFIG),))
    
    conn.commit()
    conn.close()
    print("Database initialized (single JSON field)")


def get_configuration() -> Dict[str, Any]:
    """Retrieve configuration from database as single JSON"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT config_json FROM general_configuration WHERE id = 1')
    row = cursor.fetchone()
    
    conn.close()
    
    if row and row[0]:
        try:
            return json.loads(row[0])
        except:
            return DEFAULT_CONFIG.copy()
    
    return DEFAULT_CONFIG.copy()


def update_configuration(config_data: Dict[str, Any]) -> bool:
    """Update configuration in database as single JSON"""
    try:
        current = get_configuration()
        
        # Update network mode tracking if network config changed
        if 'network' in config_data and 'mode' in config_data['network']:
            global current_network_mode
            current_network_mode = config_data['network']['mode']
        
        for key in config_data:
            if key in current and isinstance(current[key], dict) and isinstance(config_data[key], dict):
                current[key].update(config_data[key])
            else:
                current[key] = config_data[key]
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE general_configuration 
            SET config_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        ''', (json.dumps(current),))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("Error updating configuration: {}".format(e))
        return False


# WebSocket connections
connected_websockets = set()


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


# HTTP Route Handlers
async def get_config_handler(request):
    """GET handler - configuration as single JSON"""
    config = get_configuration()
    return web.json_response(config)


async def put_config_handler(request):
    """PUT handler - update configuration as single JSON"""
    try:
        data = await request.json()
        success = update_configuration(data)
        
        if success:
            # Check if network mode changed
            if 'network' in data and 'mode' in data['network']:
                global current_network_mode
                new_mode = data['network']['mode']
                
                if new_mode != current_network_mode:
                    current_network_mode = new_mode
                    
                    # If switching to/from WiFi, broadcast initial state
                    if new_mode == 'wifi' or (current_network_mode == 'wifi' and new_mode != 'wifi'):
                        config = get_configuration()
                        wifi_configured = new_mode == 'wifi' and config.get('network', {}).get('wifi', {}).get('ssid')
                        
                        if wifi_configured:
                            # WiFi just got configured, send initial signal
                            if connected_websockets:
                                await broadcast_to_clients({
                                    'type': 'wifi_signal_update',
                                    'strength': realtime_state['wifi_signal_strength']
                                })
            
            return web.json_response({
                'success': True,
                'message': 'Configuration saved successfully'
            })
        return web.json_response({
            'success': False,
            'message': 'Failed to save configuration'
        }, status=500)
        
    except Exception as e:
        print("Error in PUT handler: {}".format(e))
        return web.json_response({
            'success': False,
            'message': str(e)
        }, status=400)


async def start_background_tasks(app):
    """Start background tasks"""
    app['periodic_updates'] = asyncio.ensure_future(periodic_updates())


async def cleanup_background_tasks(app):
    """Cleanup background tasks"""
    app['periodic_updates'].cancel()
    await app['periodic_updates']


def create_app():
    """Create and configure the aiohttp application"""
    app = web.Application()
    
    # HTTP endpoints for configuration
    app.router.add_get('/api/general-configuration', get_config_handler)
    app.router.add_put('/api/general-configuration', put_config_handler)
    
    # WebSocket for real-time data
    app.router.add_get('/ws', websocket_handler)
    
    # Background tasks
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    
    return app


if __name__ == '__main__':
    # Initialize database
    print("Initializing database...")
    init_database()
    
    print("Starting server on http://0.0.0.0:8080")
    print("Database: Single JSON field for all configuration")
    print("Memory: Real-time state with change detection")
    print("HTTP: Full configuration management")
    print("WebSocket: Optimized updates (only on changes)")
    print("Press Ctrl+C to stop")
    
    web.run_app(create_app(), host='0.0.0.0', port=8080)