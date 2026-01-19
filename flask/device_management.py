# device_management.py - Device management API
import asyncio
import json
import datetime
import random
import csv
import io
import uuid
import sqlite3
from aiohttp import web

from models import (
    device_status_tracker, active_scans, pairing_sessions,
    device_websockets
)
from websocket_handler import broadcast_device_status
from database import DB_FILE

async def get_all_devices(request):
    """GET all devices"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT d.id, d.name, d.type, d.address, 
                   g.name as group_name, g.color, d.config_json
            FROM device_management d
            LEFT JOIN device_groups g ON d.group_id = g.id
            ORDER BY CAST(d.id AS INTEGER)
        ''')
        
        devices = []
        for row in cursor.fetchall():
            device_id, name, type_, address, group_name, color, config_json = row
            
            # Get real-time status (not from database)
            status = device_status_tracker.get(device_id, {'status': 'Online', 'last_poll': 'Just now'})
            
            devices.append({
                'id': device_id,
                'name': name,
                'type': type_,
                'address': address,
                'status': status['status'],
                'lastPoll': status['last_poll'],
                'group': group_name or 'None',
                'details': {
                    'status': status['status'],
                    'lastResponse': status['last_poll'],
                    'retries': 0,
                    'signalStrength': 'N/A'
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
            SELECT d.id, d.name, d.type, d.address, 
                   g.name as group_name, g.color, d.config_json
            FROM device_management d
            LEFT JOIN device_groups g ON d.group_id = g.id
            WHERE d.id = ?
        ''', (device_id,))
        
        row = cursor.fetchone()
        if not row:
            return web.json_response({'error': 'Device not found'}, status=404)
        
        device_id, name, type_, address, group_name, color, config_json = row
        config = json.loads(config_json) if config_json else {}
        
        # Get real-time status
        status = device_status_tracker.get(device_id, {'status': 'Online', 'last_poll': 'Just now'})
        
        # Ensure config has all necessary fields for Modbus TCP
        if type_ == 'Modbus TCP':
            config.setdefault('ip_address', '192.168.1.100')
            config.setdefault('port', 502)
            config.setdefault('slave_address', 1)
            config.setdefault('polling_interval', 1000)
            config.setdefault('timeout', 5000)
            config.setdefault('retry_count', 3)
        
        details = {
            'name': name,
            'type': type_,
            'address': address,
            'group': group_name,
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
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Get the next device number
        cursor.execute('SELECT COUNT(*) FROM device_management')
        device_count = cursor.fetchone()[0]
        device_id = str(device_count + 1)  # Simple sequential number
        
        # Find group ID
        group_id = None
        if data.get('group'):
            cursor.execute('SELECT id FROM device_groups WHERE name = ?', (data['group'],))
            group = cursor.fetchone()
            if group:
                group_id = group[0]
        
        config = data.get('config', {})
        
        # FIX: Ensure Modbus TCP has all required fields
        if data.get('type') == 'Modbus TCP':
            # Validate and set defaults for all TCP fields
            config.setdefault('ip_address', '192.168.1.100')
            config.setdefault('port', 502)
            config.setdefault('slave_address', 1)
            config.setdefault('polling_interval', 1000)
            config.setdefault('timeout', 5000)
            config.setdefault('retry_count', 3)
            
            print("Saving Modbus TCP device with config:", config)
        
        cursor.execute('''
            INSERT INTO device_management (id, name, type, address, group_id, config_json)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            device_id,
            data['name'],
            data['type'],
            data.get('address', 'N/A'),
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
            # FIX: Ensure Modbus TCP has all required fields
            if data.get('type', '') == 'Modbus TCP':
                config.setdefault('ip_address', '192.168.1.100')
                config.setdefault('port', 502)
                config.setdefault('slave_address', 1)
                config.setdefault('polling_interval', 1000)
                config.setdefault('timeout', 5000)
                config.setdefault('retry_count', 3)
                print("Updating Modbus TCP device with config:", config)
            
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
            SELECT name, type, address, group_id, config_json
            FROM device_management WHERE id = ?
        ''', (device_id,))
        
        row = cursor.fetchone()
        if not row:
            return web.json_response({'error': 'Device not found'}, status=404)
        
        name, type_, address, group_id, config_json = row
        
        # Get the next device number
        cursor.execute('SELECT COUNT(*) FROM device_management')
        device_count = cursor.fetchone()[0]
        new_device_id = str(device_count + 1)  # Simple sequential number
        
        new_name = "{} (Copy)".format(name)
        
        cursor.execute('''
            INSERT INTO device_management (id, name, type, address, group_id, config_json)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (new_device_id, new_name, type_, address, group_id, config_json))
        
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
                                # Ensure all TCP fields are included
                                config = {
                                    'ip_address': row.get('Address/ID', '192.168.1.100').split(':')[0] if ':' in row.get('Address/ID', '') else '192.168.1.100',
                                    'port': int(row.get('Address/ID', '502').split(':')[1]) if ':' in row.get('Address/ID', '') else 502,
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
                                SET name = ?, type = ?, address = ?, 
                                    group_id = ?, config_json = ?, updated_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            ''', (
                                device_name,
                                row.get('Type', 'Unknown').strip(),
                                row.get('Address/ID', 'N/A'),
                                group_id,
                                json.dumps(config),
                                existing_device_id
                            ))
                            devices_updated += 1
                            print("Updated device: {}".format(device_name))
                        else:
                            # Create new device
                            if not device_id or not device_id.strip():
                                # Get the next device number for imported devices
                                cursor.execute('SELECT COUNT(*) FROM device_management')
                                device_count = cursor.fetchone()[0]
                                device_id = str(device_count + 1)  # Simple sequential number
                            else:
                                device_id = device_id.strip()
                            
                            cursor.execute('''
                                INSERT INTO device_management 
                                (id, name, type, address, group_id, config_json)
                                VALUES (?, ?, ?, ?, ?, ?)
                            ''', (
                                device_id,
                                device_name,
                                row.get('Type', 'Unknown').strip(),
                                row.get('Address/ID', 'N/A'),
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
            SELECT d.id, d.name, d.type, d.address,
                   g.name as group_name, d.config_json
            FROM device_management d
            LEFT JOIN device_groups g ON d.group_id = g.id
            ORDER BY CAST(d.id AS INTEGER)
        ''')
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write comprehensive header (REMOVED Firmware Version)
        writer.writerow([
            'Device ID', 'Device Name', 'Type', 'Address/ID', 
            'Group', 'Configuration JSON'
        ])
        
        # Write data
        for row in cursor.fetchall():
            device_id, name, type_, address, group_name, config_json = row
            
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
        from models import active_scans
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