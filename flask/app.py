# app.py - Updated with Device Management API - Python 3.5 compatible
import aiohttp
from aiohttp import web
import asyncio
import json
import datetime
import sqlite3
import random
import csv
import io
import uuid
from typing import Dict, Any, List

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

# Default configuration (single JSON in database) - EMPTY NOW
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

# Device status tracking (not in database)
device_status_tracker = {}

def init_database():
    """Initialize SQLite database with empty tables - NO DEFAULT DATA"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # General configuration table (existing)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS general_configuration (
            id INTEGER PRIMARY KEY,
            config_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Device management tables (new)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT DEFAULT 'blue',
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_management (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            address TEXT,
            firmware_version TEXT DEFAULT '1.0.0',
            group_id INTEGER,
            config_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES device_groups(id)
        )
    ''')
    
    # Check for general configuration - INSERT ONLY IF EMPTY
    cursor.execute('SELECT COUNT(*) FROM general_configuration')
    count = cursor.fetchone()[0]
    
    if count == 0:
        cursor.execute('''
            INSERT INTO general_configuration (config_json)
            VALUES (?)
        ''', (json.dumps(DEFAULT_CONFIG),))
    
    conn.commit()
    conn.close()
    print("Database initialized with empty device management tables")
    print("No default devices or groups inserted")


# WebSocket connections for device status updates
device_websockets = set()

# Active scans
active_scans = {}

# Wireless pairing sessions
pairing_sessions = {}

# ------------------------------------------------------------
# Device Management API Functions
# ------------------------------------------------------------

async def get_all_devices(request):
    """GET all devices"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT d.id, d.name, d.type, d.address, d.firmware_version, 
                   g.name as group_name, g.color, d.config_json
            FROM device_management d
            LEFT JOIN device_groups g ON d.group_id = g.id
        ''')
        
        devices = []
        for row in cursor.fetchall():
            device_id, name, type_, address, firmware, group_name, color, config_json = row
            
            # Get real-time status (not from database)
            status = device_status_tracker.get(device_id, {'status': 'Online', 'last_poll': 'Just now'})
            
            devices.append({
                'id': device_id,
                'name': name,
                'type': type_,
                'address': address,
                'status': status['status'],
                'lastPoll': status['last_poll'],
                'firmware': firmware,
                'group': group_name or 'None',
                'details': {
                    'status': status['status'],
                    'lastResponse': status['last_poll'],
                    'retries': 0,
                    'signalStrength': 'N/A',
                    'firmwareVersion': firmware
                }
            })
        
        conn.close()
        return web.json_response({'devices': devices})
        
    except Exception as e:
        print("Error getting devices: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)


async def get_device_details(request):
    """GET device details"""
    try:
        device_id = request.match_info['device_id']
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT d.id, d.name, d.type, d.address, d.firmware_version, 
                   g.name as group_name, g.color, d.config_json
            FROM device_management d
            LEFT JOIN device_groups g ON d.group_id = g.id
            WHERE d.id = ?
        ''', (device_id,))
        
        row = cursor.fetchone()
        if not row:
            return web.json_response({'error': 'Device not found'}, status=404)
        
        device_id, name, type_, address, firmware, group_name, color, config_json = row
        config = json.loads(config_json) if config_json else {}
        
        # Get real-time status
        status = device_status_tracker.get(device_id, {'status': 'Online', 'last_poll': 'Just now'})
        
        # Ensure config has all necessary fields for Modbus TCP
        if type_ == 'Modbus TCP':
            if 'polling_interval' not in config:
                config['polling_interval'] = 1000
            if 'timeout' not in config:
                config['timeout'] = 5000
            if 'retry_count' not in config:
                config['retry_count'] = 3
        
        details = {
            'device_id': device_id,
            'name': name,
            'type': type_,
            'address': address,
            'firmware_version': firmware,
            'group': group_name,
            'group_color': color,
            'config': config,
            'status': status['status'],
            'last_response': status['last_poll']
        }
        
        conn.close()
        return web.json_response(details)
        
    except Exception as e:
        print("Error getting device details: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)


async def add_device(request):
    """POST add new device"""
    try:
        data = await request.json()
        
        if not data.get('name') or not data.get('type'):
            return web.json_response({'error': 'Name and type are required'}, status=400)
        
        device_id = "device-{}".format(str(uuid.uuid4())[:8])
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Find group ID
        group_id = None
        if data.get('group'):
            cursor.execute('SELECT id FROM device_groups WHERE name = ?', (data['group'],))
            group = cursor.fetchone()
            if group:
                group_id = group[0]
        
        config = data.get('config', {})
        
        # Ensure Modbus TCP has all required fields
        if data.get('type') == 'Modbus TCP':
            if 'polling_interval' not in config:
                config['polling_interval'] = 1000
            if 'timeout' not in config:
                config['timeout'] = 5000
            if 'retry_count' not in config:
                config['retry_count'] = 3
        
        cursor.execute('''
            INSERT INTO device_management (id, name, type, address, firmware_version, group_id, config_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            device_id,
            data['name'],
            data['type'],
            data.get('address', 'N/A'),
            data.get('firmware_version', '1.0.0'),
            group_id,
            json.dumps(config)
        ))
        
        conn.commit()
        conn.close()
        
        # Initialize status
        device_status_tracker[device_id] = {'status': 'Online', 'last_poll': 'Just now'}
        
        return web.json_response({
            'success': True,
            'device': {
                'id': device_id,
                'name': data['name'],
                'type': data['type'],
                'address': data.get('address', 'N/A'),
                'status': 'Online'
            }
        }, status=201)
        
    except Exception as e:
        print("Error adding device: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)


async def update_device(request):
    """PUT update device"""
    try:
        device_id = request.match_info['device_id']
        data = await request.json()
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Check if device exists
        cursor.execute('SELECT id FROM device_management WHERE id = ?', (device_id,))
        if not cursor.fetchone():
            return web.json_response({'error': 'Device not found'}, status=404)
        
        # Build update query
        updates = []
        params = []
        
        if 'name' in data:
            updates.append('name = ?')
            params.append(data['name'])
        
        if 'type' in data:
            updates.append('type = ?')
            params.append(data['type'])
        
        if 'address' in data:
            updates.append('address = ?')
            params.append(data['address'])
        
        if 'firmware_version' in data:
            updates.append('firmware_version = ?')
            params.append(data['firmware_version'])
        
        if 'group' in data:
            group_id = None
            if data['group'] and data['group'] != 'None':
                cursor.execute('SELECT id FROM device_groups WHERE name = ?', (data['group'],))
                group = cursor.fetchone()
                if group:
                    group_id = group[0]
            updates.append('group_id = ?')
            params.append(group_id)
        
        if 'config' in data:
            config = data['config']
            # Ensure Modbus TCP has all required fields
            if data.get('type', '') == 'Modbus TCP':
                if 'polling_interval' not in config:
                    config['polling_interval'] = 1000
                if 'timeout' not in config:
                    config['timeout'] = 5000
                if 'retry_count' not in config:
                    config['retry_count'] = 3
            updates.append('config_json = ?')
            params.append(json.dumps(config))
        
        if updates:
            updates.append('updated_at = CURRENT_TIMESTAMP')
            query = 'UPDATE device_management SET {} WHERE id = ?'.format(', '.join(updates))
            params.append(device_id)
            
            cursor.execute(query, params)
            conn.commit()
        
        conn.close()
        
        return web.json_response({
            'success': True,
            'device': {
                'id': device_id,
                'name': data.get('name', ''),
                'type': data.get('type', '')
            }
        })
        
    except Exception as e:
        print("Error updating device: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)


async def delete_device(request):
    """DELETE device"""
    try:
        device_id = request.match_info['device_id']
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM device_management WHERE id = ?', (device_id,))
        conn.commit()
        conn.close()
        
        # Remove from status tracker
        if device_id in device_status_tracker:
            del device_status_tracker[device_id]
        
        return web.json_response({
            'success': True,
            'device_id': device_id
        })
        
    except Exception as e:
        print("Error deleting device: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)


async def test_device(request):
    """POST ping device test"""
    try:
        device_id = request.match_info['device_id']
        
        # Simulate ping response
        await asyncio.sleep(0.1)  # Simulate network delay
        
        return web.json_response({
            'success': True,
            'ping_time_ms': random.randint(1, 10),
            'status': device_status_tracker.get(device_id, {}).get('status', 'Online')
        })
        
    except Exception as e:
        print("Error testing device: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)


async def disable_device(request):
    """POST disable/enable device"""
    try:
        device_id = request.match_info['device_id']
        data = await request.json()
        
        disabled = data.get('disabled', True)
        
        if device_id in device_status_tracker:
            device_status_tracker[device_id]['status'] = 'Disabled' if disabled else 'Online'
        else:
            device_status_tracker[device_id] = {
                'status': 'Disabled' if disabled else 'Online',
                'last_poll': 'Just now'
            }
        
        return web.json_response({
            'success': True,
            'status': 'Disabled' if disabled else 'Online'
        })
        
    except Exception as e:
        print("Error disabling device: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)


async def duplicate_device(request):
    """POST duplicate device"""
    try:
        device_id = request.match_info['device_id']
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Get original device
        cursor.execute('''
            SELECT name, type, address, firmware_version, group_id, config_json
            FROM device_management WHERE id = ?
        ''', (device_id,))
        
        row = cursor.fetchone()
        if not row:
            return web.json_response({'error': 'Device not found'}, status=404)
        
        name, type_, address, firmware, group_id, config_json = row
        
        # Create new device
        new_device_id = "device-{}".format(str(uuid.uuid4())[:8])
        new_name = "{} (Copy)".format(name)
        
        cursor.execute('''
            INSERT INTO device_management (id, name, type, address, firmware_version, group_id, config_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (new_device_id, new_name, type_, address, firmware, group_id, config_json))
        
        conn.commit()
        conn.close()
        
        # Initialize status for new device
        device_status_tracker[new_device_id] = {'status': 'Online', 'last_poll': 'Just now'}
        
        return web.json_response({
            'success': True,
            'new_device_id': new_device_id,
            'new_device': {
                'id': new_device_id,
                'name': new_name,
                'type': type_
            }
        })
        
    except Exception as e:
        print("Error duplicating device: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)


async def get_device_packets(request):
    """GET last 10 packets for device"""
    try:
        device_id = request.match_info['device_id']
        
        # Simulate packet data
        packets = []
        for i in range(10):
            timestamp = (datetime.datetime.now() - datetime.timedelta(seconds=i)).isoformat()
            direction = 'tx' if i % 2 == 0 else 'rx'
            data_hex = ' '.join(["{:02X}".format(random.randint(0, 255)) for _ in range(8)])
            
            packets.append({
                'timestamp': timestamp,
                'direction': direction,
                'data_hex': data_hex
            })
        
        return web.json_response({'packets': packets})
        
    except Exception as e:
        print("Error getting packets: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)


async def get_all_groups(request):
    """GET all groups"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT g.id, g.name, g.color, g.description,
                   COUNT(d.id) as device_count
            FROM device_groups g
            LEFT JOIN device_management d ON g.id = d.group_id
            GROUP BY g.id
            ORDER BY g.name
        ''')
        
        groups = []
        for row in cursor.fetchall():
            id_, name, color, description, device_count = row
            groups.append({
                'id': id_,
                'name': name,
                'device_count': device_count,
                'color': color,
                'description': description or ''
            })
        
        conn.close()
        return web.json_response({'groups': groups})
        
    except Exception as e:
        print("Error getting groups: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)


async def add_group(request):
    """POST add new group"""
    try:
        data = await request.json()
        
        if not data.get('name'):
            return web.json_response({'error': 'Group name is required'}, status=400)
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Check if group already exists
        cursor.execute('SELECT id FROM device_groups WHERE name = ?', (data['name'],))
        if cursor.fetchone():
            return web.json_response({'error': 'Group already exists'}, status=400)
        
        cursor.execute('''
            INSERT INTO device_groups (name, color, description)
            VALUES (?, ?, ?)
        ''', (
            data['name'],
            data.get('color', 'blue'),
            data.get('description', '')
        ))
        
        group_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        return web.json_response({
            'success': True,
            'group_id': group_id,
            'group': {
                'id': group_id,
                'name': data['name'],
                'device_count': 0,
                'color': data.get('color', 'blue')
            }
        }, status=201)
        
    except Exception as e:
        print("Error adding group: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)


async def assign_devices_to_group(request):
    """POST assign devices to group"""
    try:
        group_id = int(request.match_info['group_id'])
        data = await request.json()
        
        if 'device_ids' not in data:
            return web.json_response({'error': 'device_ids is required'}, status=400)
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Check if group exists
        cursor.execute('SELECT id FROM device_groups WHERE id = ?', (group_id,))
        if not cursor.fetchone():
            return web.json_response({'error': 'Group not found'}, status=404)
        
        # Update devices
        assigned_count = 0
        for device_id in data['device_ids']:
            cursor.execute('UPDATE device_management SET group_id = ? WHERE id = ?', (group_id, device_id))
            if cursor.rowcount > 0:
                assigned_count += 1
        
        conn.commit()
        conn.close()
        
        return web.json_response({
            'success': True,
            'assigned_count': assigned_count
        })
        
    except Exception as e:
        print("Error assigning devices: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)


async def scan_devices(request):
    """POST scan for devices"""
    try:
        data = await request.json()
        scan_type = data.get('scan_type', 'all')
        
        scan_id = "scan-{}".format(str(uuid.uuid4())[:8])
        
        # Store scan in memory
        active_scans[scan_id] = {
            'status': 'running',
            'progress': 0,
            'devices_found': [],
            'scan_type': scan_type
        }
        
        # Simulate scan in background
        asyncio.ensure_future(simulate_scan(scan_id))
        
        return web.json_response({
            'scan_id': scan_id,
            'message': 'Scan started'
        })
        
    except Exception as e:
        print("Error starting scan: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)


async def get_scan_status(request):
    """GET scan status"""
    try:
        scan_id = request.match_info['scan_id']
        
        if scan_id not in active_scans:
            return web.json_response({'error': 'Scan not found'}, status=404)
        
        scan_data = active_scans[scan_id]
        
        return web.json_response({
            'scan_id': scan_id,
            'status': scan_data['status'],
            'progress': scan_data['progress'],
            'devices_found': len(scan_data['devices_found'])
        })
        
    except Exception as e:
        print("Error getting scan status: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)


async def scan_wireless(request):
    """POST scan for wireless devices"""
    try:
        # Simulate wireless scan
        devices_found = [
            {
                'rf_address': 'RF:0x09',
                'signal_strength': random.randint(-80, -60),
                'device_type': 'ACS Sensor'
            },
            {
                'rf_address': 'RF:0x11',
                'signal_strength': random.randint(-80, -60),
                'device_type': 'Wireless IO'
            }
        ]
        
        return web.json_response({
            'devices_found': devices_found
        })
        
    except Exception as e:
        print("Error scanning wireless: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)


async def pair_wireless(request):
    """POST pair wireless device"""
    try:
        data = await request.json()
        rf_address = data.get('rf_address')
        
        if not rf_address:
            return web.json_response({'error': 'RF address is required'}, status=400)
        
        pairing_code = "{}".format(random.randint(100000, 999999))
        pairing_sessions[rf_address] = {
            'code': pairing_code,
            'expires': datetime.datetime.now() + datetime.timedelta(seconds=30)
        }
        
        return web.json_response({
            'success': True,
            'pairing_code': pairing_code,
            'timeout_seconds': 30
        })
        
    except Exception as e:
        print("Error pairing wireless: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)


# ------------------------------------------------------------
# Import/Export Functions - UPDATED
# ------------------------------------------------------------

async def import_devices_csv(request):
    """POST import devices from CSV with full configuration"""
    try:
        reader = await request.multipart()
        
        while True:
            part = await reader.next()
            if part is None:
                break
            
            if part.name == 'file':
                content = await part.read()
                content_str = content.decode('utf-8')
                
                # Parse CSV
                csv_reader = csv.DictReader(io.StringIO(content_str))
                devices_added = 0
                devices_updated = 0
                devices_skipped = 0
                row_num = 0
                
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                
                for row_num, row in enumerate(csv_reader, 1):
                    try:
                        # Check for required fields
                        if not row.get('Device Name') or not row.get('Device Name').strip():
                            print("Skipping row {}: Missing device name".format(row_num))
                            devices_skipped += 1
                            continue
                        
                        # Check if device already exists (by ID or name)
                        device_id = row.get('Device ID', None)
                        existing_device_id = None
                        device_name = row['Device Name'].strip()
                        
                        if device_id and device_id.strip():
                            # Check by ID
                            cursor.execute('SELECT id FROM device_management WHERE id = ?', (device_id.strip(),))
                            existing = cursor.fetchone()
                            if existing:
                                existing_device_id = existing[0]
                        else:
                            # Check by name
                            cursor.execute('SELECT id FROM device_management WHERE name = ?', (device_name,))
                            existing = cursor.fetchone()
                            if existing:
                                existing_device_id = existing[0]
                        
                        # Find group
                        group_id = None
                        group_name = row.get('Group', '')
                        if group_name and group_name != 'None':
                            cursor.execute('SELECT id FROM device_groups WHERE name = ?', (group_name,))
                            group = cursor.fetchone()
                            if group:
                                group_id = group[0]
                            else:
                                # Create group if it doesn't exist
                                cursor.execute(
                                    'INSERT INTO device_groups (name, color) VALUES (?, ?)',
                                    (group_name, 'blue')
                                )
                                group_id = cursor.lastrowid
                                print("Created new group: {}".format(group_name))
                        
                        # Parse configuration JSON
                        config_json = row.get('Configuration JSON', '{}')
                        config = {}
                        try:
                            if config_json and config_json.strip():
                                config = json.loads(config_json)
                        except Exception as e:
                            print("Error parsing config JSON for row {}: {}".format(row_num, e))
                            # Create default config based on device type
                            device_type = row.get('Type', 'Unknown').strip()
                            if device_type == 'Modbus RTU':
                                config = {
                                    'slave_address': 1,
                                    'baud_rate': 9600,
                                    'parity': 'None',
                                    'stop_bits': 1,
                                    'polling_interval': 500
                                }
                            elif device_type == 'Modbus TCP':
                                config = {
                                    'ip_address': '192.168.1.100',
                                    'port': 502,
                                    'slave_address': 1,
                                    'polling_interval': 1000,
                                    'timeout': 5000,
                                    'retry_count': 3
                                }
                            elif device_type == 'CAN':
                                config = {
                                    'can_id': row.get('Address/ID', '0x000'),
                                    'protocol': 'CANOpen',
                                    'bitrate': '500K'
                                }
                            elif device_type == 'Wireless':
                                config = {
                                    'rf_address': row.get('Address/ID', 'RF:0x00'),
                                    'signal_strength': -70
                                }
                            elif device_type == 'ACS Sensor':
                                config = {
                                    'sensor_id': row.get('Address/ID', 'ACS-001'),
                                    'sampling_rate': '10 Hz',
                                    'sensitivity': 'Medium'
                                }
                        
                        if existing_device_id:
                            # Update existing device
                            cursor.execute('''
                                UPDATE device_management 
                                SET name = ?, type = ?, address = ?, firmware_version = ?, 
                                    group_id = ?, config_json = ?, updated_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            ''', (
                                device_name,
                                row.get('Type', 'Unknown').strip(),
                                row.get('Address/ID', 'N/A'),
                                row.get('Firmware Version', '1.0.0'),
                                group_id,
                                json.dumps(config),
                                existing_device_id
                            ))
                            devices_updated += 1
                            print("Updated device: {}".format(device_name))
                        else:
                            # Create new device
                            if not device_id or not device_id.strip():
                                device_id = "imported-{}-{}".format(row_num, str(uuid.uuid4())[:8])
                            else:
                                device_id = device_id.strip()
                            
                            cursor.execute('''
                                INSERT INTO device_management 
                                (id, name, type, address, firmware_version, group_id, config_json)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                device_id,
                                device_name,
                                row.get('Type', 'Unknown').strip(),
                                row.get('Address/ID', 'N/A'),
                                row.get('Firmware Version', '1.0.0'),
                                group_id,
                                json.dumps(config)
                            ))
                            
                            devices_added += 1
                            device_status_tracker[device_id] = {
                                'status': 'Online', 
                                'last_poll': 'Just now'
                            }
                            print("Added device: {} (ID: {})".format(device_name, device_id))
                        
                    except Exception as e:
                        print("Error importing row {}: {}".format(row_num, e))
                        devices_skipped += 1
                        continue
                
                conn.commit()
                conn.close()
                
                return web.json_response({
                    'success': True,
                    'devices_added': devices_added,
                    'devices_updated': devices_updated,
                    'devices_skipped': devices_skipped,
                    'total_processed': row_num
                })
        
        return web.json_response({'error': 'No file provided'}, status=400)
        
    except Exception as e:
        print("Error importing CSV: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)


async def export_devices_csv(request):
    """POST export devices to CSV with full configuration"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Get all devices with their full configuration
        cursor.execute('''
            SELECT d.id, d.name, d.type, d.address, d.firmware_version,
                   g.name as group_name, d.config_json
            FROM device_management d
            LEFT JOIN device_groups g ON d.group_id = g.id
            ORDER BY d.name
        ''')
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write comprehensive header
        writer.writerow([
            'Device ID', 'Device Name', 'Type', 'Address/ID', 
            'Firmware Version', 'Group', 'Configuration JSON'
        ])
        
        # Write data
        for row in cursor.fetchall():
            device_id, name, type_, address, firmware, group_name, config_json = row
            
            # Get real-time status
            status = device_status_tracker.get(device_id, {'status': 'Online', 'last_poll': 'Just now'})
            
            # Ensure config_json is not None
            if config_json is None:
                config_json = '{}'
            
            writer.writerow([
                device_id,
                name,
                type_,
                address,
                firmware,
                group_name or 'None',
                config_json  # Include the full configuration JSON
            ])
        
        conn.close()
        
        # Create filename with timestamp
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = 'devices_export_{}.csv'.format(timestamp)
        
        # Return CSV file
        response = web.Response(body=output.getvalue().encode('utf-8'))
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
        
        return response
        
    except Exception as e:
        print("Error exporting CSV: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)


async def simulate_scan(scan_id):
    """Simulate device scanning"""
    try:
        scan_data = active_scans[scan_id]
        
        # Simulate progress
        for i in range(1, 101, 10):
            await asyncio.sleep(0.5)
            scan_data['progress'] = i
            
            # Simulate finding devices
            if i % 30 == 0:
                device_types = ['Modbus RTU', 'Modbus TCP', 'CAN', 'Wireless', 'ACS Sensor']
                device_type = random.choice(device_types)
                
                scan_data['devices_found'].append({
                    'address': "Slave {}".format(random.randint(1, 247)) if device_type == 'Modbus RTU' else "0x{:03X}".format(random.randint(0x100, 0x3FF)),
                    'type': device_type
                })
        
        scan_data['status'] = 'completed'
        scan_data['progress'] = 100
        
        # Clean up after 5 minutes
        await asyncio.sleep(300)
        if scan_id in active_scans:
            del active_scans[scan_id]
            
    except Exception as e:
        print("Error in scan simulation: {}".format(e))
        if scan_id in active_scans:
            active_scans[scan_id]['status'] = 'failed'


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


# ------------------------------------------------------------
# Device WebSocket Handler for Real-time Status Updates
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# Existing code (keep all existing functions from original app.py)
# ------------------------------------------------------------

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


# WebSocket connections (existing)
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


# HTTP Route Handlers (existing)
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


# Device Management HTTP Route Handlers
async def device_management_handler(request):
    """GET handler - device management page"""
    # In a real implementation, you would serve the actual HTML file
    # For now, return a simple response
    return web.Response(text='Device Management API is running. Use API endpoints.', content_type='text/html')


async def start_background_tasks(app):
    """Start background tasks"""
    app['periodic_updates'] = asyncio.ensure_future(periodic_updates())
    app['device_status_updater'] = asyncio.ensure_future(device_status_updater())


async def cleanup_background_tasks(app):
    """Cleanup background tasks"""
    app['periodic_updates'].cancel()
    await app['periodic_updates']
    app['device_status_updater'].cancel()
    await app['device_status_updater']


def create_app():
    """Create and configure the aiohttp application"""
    app = web.Application()
    
    # HTTP endpoints for configuration (existing)
    app.router.add_get('/api/general-configuration', get_config_handler)
    app.router.add_put('/api/general-configuration', put_config_handler)
    
    # Device Management endpoints
    app.router.add_get('/device-management', device_management_handler)
    
    # Device operations
    app.router.add_get('/api/device-management/devices', get_all_devices)
    app.router.add_post('/api/device-management/devices', add_device)
    app.router.add_get('/api/device-management/devices/{device_id}/details', get_device_details)
    app.router.add_put('/api/device-management/devices/{device_id}', update_device)
    app.router.add_delete('/api/device-management/devices/{device_id}', delete_device)
    app.router.add_post('/api/device-management/devices/{device_id}/test', test_device)
    app.router.add_post('/api/device-management/devices/{device_id}/disable', disable_device)
    app.router.add_post('/api/device-management/devices/{device_id}/duplicate', duplicate_device)
    app.router.add_get('/api/device-management/devices/{device_id}/packets', get_device_packets)
    
    # Group operations
    app.router.add_get('/api/device-management/groups', get_all_groups)
    app.router.add_post('/api/device-management/groups', add_group)
    app.router.add_post('/api/device-management/groups/{group_id}/assign-devices', assign_devices_to_group)
    
    # Scanning operations
    app.router.add_post('/api/device-management/scan', scan_devices)
    app.router.add_get('/api/device-management/scan/{scan_id}/status', get_scan_status)
    app.router.add_post('/api/device-management/wireless/scan', scan_wireless)
    app.router.add_post('/api/device-management/wireless/pair', pair_wireless)
    
    # Import/Export operations - UPDATED
    app.router.add_post('/api/device-management/import', import_devices_csv)
    app.router.add_post('/api/device-management/export', export_devices_csv)
    
    # WebSocket for real-time data (existing)
    app.router.add_get('/ws', websocket_handler)
    
    # WebSocket for device status updates
    app.router.add_get('/ws/devices', device_websocket_handler)
    
    # Background tasks
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    
    return app


if __name__ == '__main__':
    # Initialize database
    print("Initializing database...")
    init_database()
    
    print("Starting server on http://0.0.0.0:8080")
    print("Database: Device management tables created (empty)")
    print("Memory: Real-time device status tracking")
    print("HTTP: Full device management API")
    print("WebSocket: Device status updates")
    print("Import/Export: CSV with full device configuration")
    print("Press Ctrl+C to stop")
    
    web.run_app(create_app(), host='0.0.0.0', port=8080)