# device_management.py - Device management API for Modbus and Loadcell
import asyncio
import json
import random
import uuid
import sqlite3
import io
import csv
from datetime import datetime
from aiohttp import web

from models import device_status_tracker, device_websockets
from websocket_handler import broadcast_device_status
from database import DB_FILE, get_service_by_name
from utils import initialize_device_status, remove_device_status, update_device_status

# ============================================================================
# DATABASE CONNECTION HELPER
# ============================================================================

def get_db_connection():
    """Get a database connection with proper timeout and WAL mode for concurrency"""
    conn = sqlite3.connect(DB_FILE, timeout=10.0)
    conn.execute('PRAGMA journal_mode=WAL')  # Write-Ahead Logging for better concurrency
    conn.execute('PRAGMA foreign_keys = ON')  # Enable foreign key constraints (including CASCADE)
    return conn

# ============================================================================
# GET ALL DEVICES (Both Modbus and Loadcell)
# ============================================================================

async def get_all_devices(request):
    """GET all devices (modbus + loadcell) with real-time status"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        devices = []
        
        # Get Modbus devices
        cursor.execute('''
            SELECT m.id, m.name, m.device_type, m.ip_address, m.port, m.serial_port,
                   g.name as group_name, g.color, m.enabled, s.name as service_name
            FROM modbus_device m
            LEFT JOIN device_groups g ON m.group_id = g.id
            LEFT JOIN services s ON m.service_id = s.id
            ORDER BY m.id
        ''')
        
        for row in cursor.fetchall():
            device_id, name, device_type, ip, port, serial_port, group_name, color, enabled, service_name = row
            
            # Determine address display
            if device_type == 'tcp':
                address = "{}:{}".format(ip, port) if ip else "Not configured"
                protocol = "modbus-tcp"
            else:  # rtu
                address = serial_port or "Not configured"
                protocol = "modbus-rtu"
            
            # Get or initialize real-time status
            if device_id not in device_status_tracker:
                # Initialize with random status for demo
                initial_status = 'Online' if random.random() > 0.3 else 'Offline'
                initialize_device_status(device_id, initial_status)
            
            status = device_status_tracker[device_id]
            
            devices.append({
                'id': device_id,
                'name': name,
                'type': 'Modbus',
                'protocol': protocol,
                'address': address,
                'status': status['status'],
                'lastPoll': status['last_poll'],
                'group': group_name or 'None',
                'enabled': bool(enabled),
                'service': service_name
            })
        
        # Get Loadcell devices
        cursor.execute('''
            SELECT l.id, l.name, l.device_path, 
                   g.name as group_name, g.color, l.enabled, s.name as service_name
            FROM loadcell_device l
            LEFT JOIN device_groups g ON l.group_id = g.id
            LEFT JOIN services s ON l.service_id = s.id
            ORDER BY l.id
        ''')
        
        for row in cursor.fetchall():
            device_id, name, device_path, group_name, color, enabled, service_name = row
            
            # Get or initialize real-time status
            if device_id not in device_status_tracker:
                # Initialize with random status for demo
                initial_status = 'Online' if random.random() > 0.3 else 'Offline'
                initialize_device_status(device_id, initial_status)
            
            status = device_status_tracker[device_id]
            
            devices.append({
                'id': device_id,
                'name': name,
                'type': 'Loadcell',
                'protocol': 'loadcell',
                'address': device_path,
                'status': status['status'],
                'lastPoll': status['last_poll'],
                'group': group_name or 'None',
                'enabled': bool(enabled),
                'service': service_name
            })
        
        conn.close()
        return web.json_response({'devices': devices})
        
    except Exception as e:
        print("Error getting devices: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# GET DEVICE DETAILS
# ============================================================================

async def get_device_details(request):
    """GET device details by ID with real-time status"""
    try:
        device_id = request.match_info['device_id']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Try Modbus first
        cursor.execute('''
            SELECT m.id, m.name, m.device_type, m.group_id,
                   m.slave_id, m.timeout_ms, m.retry_count, m.polling_interval_ms,
                   m.ip_address, m.port,
                   m.serial_port, m.baud_rate, m.parity, m.data_bits, m.stop_bits,
                   m.enabled, g.name as group_name, s.name as service_name
            FROM modbus_device m
            LEFT JOIN device_groups g ON m.group_id = g.id
            LEFT JOIN services s ON m.service_id = s.id
            WHERE m.id = ?
        ''', (device_id,))
        
        row = cursor.fetchone()
        
        if row:
            # It's a Modbus device
            (dev_id, name, device_type, group_id, slave_id, timeout_ms, retry_count, 
             polling_interval_ms, ip_address, port, serial_port, baud_rate, parity, 
             data_bits, stop_bits, enabled, group_name, service_name) = row
            
            # Get or initialize status
            if device_id not in device_status_tracker:
                initialize_device_status(device_id, 'Offline')
            
            status = device_status_tracker[device_id]
            
            details = {
                'id': dev_id,
                'name': name,
                'type': 'Modbus',
                'device_type': device_type,
                'group': group_name or 'None',
                'group_id': group_id,
                'service': service_name,
                'enabled': bool(enabled),
                'status': status['status'],
                'lastPoll': status['last_poll'],
                'config': {
                    'slave_id': slave_id,
                    'timeout_ms': timeout_ms,
                    'retry_count': retry_count,
                    'polling_interval_ms': polling_interval_ms
                }
            }
            
            if device_type == 'tcp':
                details['config']['ip_address'] = ip_address
                details['config']['port'] = port
                details['protocol'] = 'modbus-tcp'
            else:  # rtu
                details['config']['serial_port'] = serial_port
                details['config']['baud_rate'] = baud_rate
                details['config']['parity'] = parity
                details['config']['data_bits'] = data_bits
                details['config']['stop_bits'] = stop_bits
                details['protocol'] = 'modbus-rtu'
            
            conn.close()
            return web.json_response(details)
        
        # Try Loadcell
        cursor.execute('''
            SELECT l.id, l.name, l.group_id, l.device_path, l.channel,
                   l.tare_offset, l.known_weight, l.known_weight_raw, l.shift_bits,
                   l.unit, l.capacity, l.load_name, l.capacity_name,
                   l.pipeline_server, l.pipeline_port, l.log_level, l.polling_interval_ms,
                   l.lowpass_filter_enabled, l.filter_cutoff_frequency, l.filter_activation_delta_min,
                   l.moving_avg_enabled, l.moving_avg_window,
                   l.median_filter_enabled, l.median_filter_window,
                   l.autotare_enabled, l.autotare_trigger_delta_grams,
                   l.adaptive_deadband_enabled, l.adaptive_deadband_min, l.adaptive_deadband_max,
                   l.adaptive_deadband_grow_rate, l.adaptive_deadband_shrink_rate,
                   l.publish_step_grams, l.overload_threshold, l.overload_relay,
                   l.overload_action, l.overload_cooldown_ms, l.confirm_count,
                   l.enabled, g.name as group_name, s.name as service_name
            FROM loadcell_device l
            LEFT JOIN device_groups g ON l.group_id = g.id
            LEFT JOIN services s ON l.service_id = s.id
            WHERE l.id = ?
        ''', (device_id,))
        
        row = cursor.fetchone()
        
        if row:
            # Get or initialize status
            if device_id not in device_status_tracker:
                initialize_device_status(device_id, 'Offline')
            
            status = device_status_tracker[device_id]
            
            # Build loadcell details
            (dev_id, name, group_id, device_path, channel,
             tare_offset, known_weight, known_weight_raw, shift_bits,
             unit, capacity, load_name, capacity_name,
             pipeline_server, pipeline_port, log_level, polling_interval_ms,
             lowpass_filter_enabled, filter_cutoff_frequency, filter_activation_delta_min,
             moving_avg_enabled, moving_avg_window,
             median_filter_enabled, median_filter_window,
             autotare_enabled, autotare_trigger_delta_grams,
             adaptive_deadband_enabled, adaptive_deadband_min, adaptive_deadband_max,
             adaptive_deadband_grow_rate, adaptive_deadband_shrink_rate,
             publish_step_grams, overload_threshold, overload_relay,
             overload_action, overload_cooldown_ms, confirm_count,
             enabled, group_name, service_name) = row
            
            details = {
                'id': dev_id,
                'name': name,
                'type': 'Loadcell',
                'protocol': 'loadcell',
                'group': group_name or 'None',
                'group_id': group_id,
                'service': service_name,
                'enabled': bool(enabled),
                'status': status['status'],
                'lastPoll': status['last_poll'],
                'config': {
                    'device_path': device_path,
                    'channel': channel,
                    'capacity': capacity,
                    'load_name': load_name or 'load',
                    'capacity_name': capacity_name,
                    'unit': unit,
                    'shift_bits': shift_bits,
                    'polling_interval_ms': polling_interval_ms,
                    'calibration': {
                        'tare_offset': tare_offset,
                        'known_weight': known_weight,
                        'known_weight_raw': known_weight_raw,
                        'shift_bits': shift_bits
                    },
                    'filters': {
                        'lowpass_filter_enabled': bool(lowpass_filter_enabled),
                        'filter_cutoff_frequency': filter_cutoff_frequency,
                        'filter_activation_delta_min': filter_activation_delta_min,
                        'moving_avg_enabled': bool(moving_avg_enabled),
                        'moving_avg_window': moving_avg_window,
                        'median_filter_enabled': bool(median_filter_enabled),
                        'median_filter_window': median_filter_window
                    },
                    'autotare': {
                        'enabled': bool(autotare_enabled),
                        'trigger_delta_grams': autotare_trigger_delta_grams
                    },
                    'adaptive_deadband': {
                        'enabled': bool(adaptive_deadband_enabled),
                        'min': adaptive_deadband_min,
                        'max': adaptive_deadband_max,
                        'grow_rate': adaptive_deadband_grow_rate,
                        'shrink_rate': adaptive_deadband_shrink_rate
                    },
                    'overload': {
                        'threshold': overload_threshold,
                        'relay': overload_relay,
                        'action': overload_action,
                        'cooldown_ms': overload_cooldown_ms
                    },
                    'pipeline': {
                        'server': pipeline_server,
                        'port': pipeline_port,
                        'log_level': log_level
                    },
                    'publish_step_grams': publish_step_grams,
                    'confirm_count': confirm_count
                }
            }
            
            conn.close()
            return web.json_response(details)
        
        conn.close()
        return web.json_response({'error': 'Device not found'}, status=404)
        
    except Exception as e:
        print("Error getting device details: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# ADD DEVICE
# ============================================================================

async def add_device(request):
    """POST - Add a new device (Modbus or Loadcell)"""
    try:
        data = await request.json()
        
        device_type = data.get('type', '').lower()
        protocol = data.get('protocol', '').lower()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Generate device ID with unique prefix to prevent collisions
        if device_type == 'loadcell':
            # ENFORCE: Only one loadcell device allowed (LC1 only)
            cursor.execute('SELECT COUNT(*) FROM loadcell_device')
            lc_count = cursor.fetchone()[0]
            if lc_count >= 1:
                conn.close()
                return web.json_response({
                    'success': False,
                    'error': 'Only one Load Cell device (LC1) is allowed. A load cell device already exists.'
                }, status=400)
            
            device_id = 'LC1'  # Always LC1 - only one allowed
        else:  # modbus
            # Modbus devices get MB prefix - find max existing ID number
            cursor.execute('SELECT id FROM modbus_device WHERE id LIKE "MB%" ORDER BY id')
            existing_ids = [row[0] for row in cursor.fetchall()]
            
            # Extract numbers from IDs and find max
            max_num = 0
            for existing_id in existing_ids:
                try:
                    num = int(existing_id[2:])  # Skip 'MB' prefix
                    if num > max_num:
                        max_num = num
                except ValueError:
                    continue
            
            device_id = 'MB{}'.format(max_num + 1)
        
        # Get group_id if group name is provided
        group_id = None
        if data.get('group') and data['group'] != 'None':
            cursor.execute('SELECT id FROM device_groups WHERE name = ?', (data['group'],))
            group_row = cursor.fetchone()
            if group_row:
                group_id = group_row[0]
        
        # Get service_id
        service_name = 'loadcell' if device_type == 'loadcell' else 'modbus'
        service_id = get_service_by_name(service_name)
        
        if device_type == 'loadcell':
            # Add Loadcell device
            config = data.get('config', {})
            
            cursor.execute('''
                INSERT INTO loadcell_device (
                    id, name, group_id, service_id, device_path, channel,
                    capacity, unit, shift_bits, load_name, capacity_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                device_id,
                data.get('name', 'Loadcell Device'),
                group_id,
                service_id,
                config.get('device_path', '/dev/spidev0.0'),
                config.get('channel', 0),
                config.get('capacity', 40000.0),
                config.get('unit', 'g'),
                config.get('shift_bits', 10),
                'load',
                config.get('capacity_name', 'capacity')
            ))
            
            # Automatically create 'load' and 'capacity' datapoints
            cursor.execute('''
                INSERT OR IGNORE INTO loadcell_datapoints (device_id, name, unit)
                VALUES (?, 'load', '')
            ''', (device_id,))
            cursor.execute('''
                INSERT OR IGNORE INTO loadcell_datapoints (device_id, name, unit)
                VALUES (?, 'capacity', '')
            ''', (device_id,))
            
        else:  # Modbus (TCP or RTU)
            config = data.get('config', {})
            
            # Determine device_type from protocol - handle various formats
            protocol_lower = protocol.lower()
            if 'tcp' in protocol_lower:
                modbus_type = 'tcp'
            elif 'rtu' in protocol_lower:
                modbus_type = 'rtu'
            else:
                # Fallback: check if IP address is provided (indicates TCP)
                modbus_type = 'tcp' if config.get('ip_address') else 'rtu'
            
            print("Creating Modbus device - Protocol received: '{}', Type determined: '{}'".format(protocol, modbus_type))
            
            cursor.execute('''
                INSERT INTO modbus_device (
                    id, name, device_type, group_id, service_id,
                    slave_id, timeout_ms, retry_count, polling_interval_ms,
                    ip_address, port,
                    serial_port, baud_rate, parity, data_bits, stop_bits
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                device_id,
                data.get('name', 'Modbus Device'),
                modbus_type,
                group_id,
                service_id,
                config.get('slave_id', 1),
                config.get('timeout_ms', 1000),
                config.get('retry_count', 3),
                config.get('polling_interval_ms', 100),
                config.get('ip_address') if modbus_type == 'tcp' else None,
                config.get('port', 502) if modbus_type == 'tcp' else None,
                config.get('serial_port', '/dev/ttymxc2') if modbus_type == 'rtu' else None,
                config.get('baud_rate', 9600) if modbus_type == 'rtu' else None,
                config.get('parity', 'N') if modbus_type == 'rtu' else None,
                config.get('data_bits', 8) if modbus_type == 'rtu' else None,
                config.get('stop_bits', 1) if modbus_type == 'rtu' else None
            ))
        
        conn.commit()
        conn.close()
        
        # Initialize status tracker
        initialize_device_status(device_id, 'Online')
        
        return web.json_response({
            'success': True,
            'message': 'Device added successfully',
            'device_id': device_id
        })
        
    except sqlite3.IntegrityError as e:
        print("Database integrity error: {}".format(e))
        return web.json_response({'error': 'Database constraint violation: {}'.format(str(e))}, status=400)
    except Exception as e:
        print("Error adding device: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# UPDATE DEVICE
# ============================================================================

async def update_device(request):
    """PUT - Update device"""
    try:
        device_id = request.match_info['device_id']
        data = await request.json()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if it's Modbus or Loadcell
        cursor.execute('SELECT id FROM modbus_device WHERE id = ?', (device_id,))
        is_modbus = cursor.fetchone() is not None
        
        # Get group_id if group name is provided
        group_id = None
        if data.get('group') and data['group'] != 'None':
            cursor.execute('SELECT id FROM device_groups WHERE name = ?', (data['group'],))
            group_row = cursor.fetchone()
            if group_row:
                group_id = group_row[0]
        
        if is_modbus:
            # Update Modbus device
            config = data.get('config', {})
            device_type = data.get('device_type', 'tcp')
            
            update_fields = ['name = ?', 'device_type = ?', 'group_id = ?']
            values = [data.get('name'), device_type, group_id]
            
            # Common fields
            if 'slave_id' in config:
                update_fields.append('slave_id = ?')
                values.append(config['slave_id'])
            if 'timeout_ms' in config:
                update_fields.append('timeout_ms = ?')
                values.append(config['timeout_ms'])
            if 'retry_count' in config:
                update_fields.append('retry_count = ?')
                values.append(config['retry_count'])
            if 'polling_interval_ms' in config:
                update_fields.append('polling_interval_ms = ?')
                values.append(config['polling_interval_ms'])
            
            # TCP specific
            if device_type == 'tcp':
                if 'ip_address' in config:
                    update_fields.append('ip_address = ?')
                    values.append(config['ip_address'])
                if 'port' in config:
                    update_fields.append('port = ?')
                    values.append(config['port'])
            
            # RTU specific
            if device_type == 'rtu':
                if 'serial_port' in config:
                    update_fields.append('serial_port = ?')
                    values.append(config['serial_port'])
                if 'baud_rate' in config:
                    update_fields.append('baud_rate = ?')
                    values.append(config['baud_rate'])
                if 'parity' in config:
                    update_fields.append('parity = ?')
                    values.append(config['parity'])
                if 'data_bits' in config:
                    update_fields.append('data_bits = ?')
                    values.append(config['data_bits'])
                if 'stop_bits' in config:
                    update_fields.append('stop_bits = ?')
                    values.append(config['stop_bits'])
            
            values.append(device_id)
            
            query = '''
                UPDATE modbus_device 
                SET {fields}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            '''.format(fields=', '.join(update_fields))
            
            cursor.execute(query, values)
        
        else:
            # Update Loadcell device
            config = data.get('config', {})
            
            update_fields = ['name = ?', 'group_id = ?']
            values = [data.get('name'), group_id]
            
            # Device connection
            if 'device_path' in config:
                update_fields.append('device_path = ?')
                values.append(config['device_path'])
            if 'channel' in config:
                update_fields.append('channel = ?')
                values.append(config['channel'])
            if 'unit' in config:
                update_fields.append('unit = ?')
                values.append(config['unit'])
            if 'capacity' in config:
                update_fields.append('capacity = ?')
                values.append(float(config['capacity']))
            if 'shift_bits' in config:
                update_fields.append('shift_bits = ?')
                values.append(int(config['shift_bits']))
            
            # Calibration
            if 'calibration' in config:
                cal = config['calibration']
                if 'capacity' in cal:
                    update_fields.append('capacity = ?')
                    values.append(cal['capacity'])
                if 'capacity_name' in cal:
                    update_fields.append('capacity_name = ?')
                    values.append(cal['capacity_name'])
                if 'tare_offset' in cal:
                    update_fields.append('tare_offset = ?')
                    values.append(cal['tare_offset'])
                if 'known_weight' in cal:
                    update_fields.append('known_weight = ?')
                    values.append(cal['known_weight'])
                if 'known_weight_raw' in cal:
                    update_fields.append('known_weight_raw = ?')
                    values.append(cal['known_weight_raw'])
                if 'shift_bits' in cal:
                    update_fields.append('shift_bits = ?')
                    values.append(cal['shift_bits'])
                if 'unit' in cal:
                    update_fields.append('unit = ?')
                    values.append(cal['unit'])
            
            values.append(device_id)
            
            query = '''
                UPDATE loadcell_device 
                SET {fields}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            '''.format(fields=', '.join(update_fields))
            
            cursor.execute(query, values)
            

        
        conn.commit()
        conn.close()
        
        return web.json_response({
            'success': True,
            'message': 'Device updated successfully'
        })
        
    except Exception as e:
        print("Error updating device: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# DELETE DEVICE
# ============================================================================

async def delete_device(request):
    """DELETE - Delete device"""
    try:
        device_id = request.match_info['device_id']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Try deleting from both tables (cascade will handle datapoints)
        cursor.execute('DELETE FROM modbus_device WHERE id = ?', (device_id,))
        cursor.execute('DELETE FROM loadcell_device WHERE id = ?', (device_id,))
        
        conn.commit()
        conn.close()
        
        # Remove from status tracker
        remove_device_status(device_id)
        
        return web.json_response({
            'success': True,
            'message': 'Device deleted successfully'
        })
        
    except Exception as e:
        print("Error deleting device: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# DEVICE OPERATIONS (Test, Disable, etc.)
# ============================================================================

async def test_device(request):
    """POST - Test device connection"""
    try:
        device_id = request.match_info['device_id']
        
        # Simulate connection test
        await asyncio.sleep(0.5)
        success = random.choice([True, True, True, False])  # 75% success rate
        
        if success:
            update_device_status(device_id, 'Online', 'Just now')
            return web.json_response({
                'success': True,
                'message': 'Device connection successful'
            })
        else:
            update_device_status(device_id, 'Offline', 'Failed')
            return web.json_response({
                'success': False,
                'message': 'Device connection failed'
            }, status=400)
            
    except Exception as e:
        print("Error testing device: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)

async def disable_device(request):
    """POST - Enable/Disable device"""
    try:
        device_id = request.match_info['device_id']
        data = await request.json()
        enabled = data.get('enabled', True)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update both tables
        cursor.execute('UPDATE modbus_device SET enabled = ? WHERE id = ?', (enabled, device_id))
        cursor.execute('UPDATE loadcell_device SET enabled = ? WHERE id = ?', (enabled, device_id))
        
        conn.commit()
        conn.close()
        
        # Update status based on enabled state
        if enabled:
            update_device_status(device_id, 'Online', 'Just now')
        else:
            update_device_status(device_id, 'Disabled', 'Now')
        
        return web.json_response({
            'success': True,
            'message': "Device {} successfully".format('enabled' if enabled else 'disabled')
        })
        
    except Exception as e:
        print("Error disabling device: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# DUPLICATE DEVICE
# ============================================================================

async def duplicate_device(request):
    """POST - Duplicate device with all its datapoints"""
    try:
        device_id = request.match_info['device_id']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if it's a Modbus device
        cursor.execute('SELECT * FROM modbus_device WHERE id = ?', (device_id,))
        modbus_row = cursor.fetchone()
        
        if modbus_row:
            # It's a Modbus device - duplicate it
            # Get column names
            cursor.execute('PRAGMA table_info(modbus_device)')
            columns = [col[1] for col in cursor.fetchall()]
            
            # Create dictionary of old device data
            old_device = dict(zip(columns, modbus_row))
            
            # Generate new device ID with MB prefix - find max existing ID number
            cursor.execute('SELECT id FROM modbus_device WHERE id LIKE "MB%" ORDER BY id')
            existing_ids = [row[0] for row in cursor.fetchall()]
            
            # Extract numbers from IDs and find max
            max_num = 0
            for existing_id in existing_ids:
                try:
                    num = int(existing_id[2:])  # Skip 'MB' prefix
                    if num > max_num:
                        max_num = num
                except ValueError:
                    continue
            
            new_device_id = 'MB{}'.format(max_num + 1)
            
            # Generate new device name with -001, -002 suffix
            base_name = old_device['name']
            # Remove any existing -XXX suffix from base name
            import re
            base_name_clean = re.sub(r'-\d+$', '', base_name)
            
            cursor.execute('SELECT name FROM modbus_device WHERE name LIKE ?', ('{}%'.format(base_name_clean),))
            existing_names = [row[0] for row in cursor.fetchall()]
            
            counter = 1
            numbers = []
            for name in existing_names:
                match = re.search(r'-(\d+)$', name)
                if match:
                    numbers.append(int(match.group(1)))
            
            if numbers:
                counter = max(numbers) + 1
            else:
                # First duplicate should be -001
                counter = 1
            
            new_name = "{}-{}".format(base_name_clean, str(counter).zfill(3))
            
            # Insert new device
            cursor.execute('''
                INSERT INTO modbus_device (
                    id, name, device_type, group_id, service_id,
                    slave_id, timeout_ms, retry_count, polling_interval_ms,
                    ip_address, port, serial_port, baud_rate, parity,
                    data_bits, stop_bits, enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                new_device_id, new_name, old_device['device_type'],
                old_device['group_id'], old_device['service_id'],
                old_device['slave_id'], old_device['timeout_ms'],
                old_device['retry_count'], old_device['polling_interval_ms'],
                old_device['ip_address'], old_device['port'],
                old_device['serial_port'], old_device['baud_rate'],
                old_device['parity'], old_device['data_bits'],
                old_device['stop_bits'], old_device['enabled']
            ))
            
            # Duplicate all Modbus datapoints
            cursor.execute('''
                SELECT name, register_address, register_type, data_type,
                       byte_order, word_order, scale_factor, offset, unit, description
                FROM modbus_datapoints
                WHERE device_id = ?
            ''', (device_id,))
            
            datapoints = cursor.fetchall()
            for dp in datapoints:
                cursor.execute('''
                    INSERT INTO modbus_datapoints (
                        device_id, name, register_address, register_type, data_type,
                        byte_order, word_order, scale_factor, offset, unit, description
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (new_device_id,) + dp)
            
            # Initialize status for new device
            initialize_device_status(new_device_id, 'Online')
            
            conn.commit()
            conn.close()
            
            return web.json_response({
                'success': True,
                'message': 'Device duplicated successfully as {}'.format(new_name),
                'device_id': new_device_id,
                'device_name': new_name,
                'datapoints_copied': len(datapoints)
            })
        
        else:
            # Check if it's a Loadcell device
            cursor.execute('SELECT * FROM loadcell_device WHERE id = ?', (device_id,))
            loadcell_row = cursor.fetchone()
            
            if loadcell_row:
                # Block duplicating loadcell - only one loadcell (LC1) allowed
                conn.close()
                return web.json_response({
                    'success': False,
                    'error': 'Cannot duplicate Load Cell device. Only one Load Cell (LC1) is allowed.'
                }, status=400)
            
            if False and loadcell_row:  # unreachable - kept for reference
                # It's a Loadcell device - duplicate it
                cursor.execute('PRAGMA table_info(loadcell_device)')
                columns = [col[1] for col in cursor.fetchall()]
                
                old_device = dict(zip(columns, loadcell_row))
                
                # Generate new device ID with LC prefix - find max existing ID number
                cursor.execute('SELECT id FROM loadcell_device WHERE id LIKE "LC%" ORDER BY id')
                existing_ids = [row[0] for row in cursor.fetchall()]
                
                # Extract numbers from IDs and find max
                max_num = 0
                for existing_id in existing_ids:
                    try:
                        num = int(existing_id[2:])  # Skip 'LC' prefix
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        continue
                
                new_device_id = 'LC{}'.format(max_num + 1)
                
                # Generate new device name with -001, -002 suffix
                base_name = old_device['name']
                # Remove any existing -XXX suffix from base name
                import re
                base_name_clean = re.sub(r'-\d+$', '', base_name)
                
                cursor.execute('SELECT name FROM loadcell_device WHERE name LIKE ?', ('{}%'.format(base_name_clean),))
                existing_names = [row[0] for row in cursor.fetchall()]
                
                counter = 1
                numbers = []
                for name in existing_names:
                    match = re.search(r'-(\d+)$', name)
                    if match:
                        numbers.append(int(match.group(1)))
                
                if numbers:
                    counter = max(numbers) + 1
                else:
                    # First duplicate should be -001
                    counter = 1
                
                new_name = "{}-{}".format(base_name_clean, str(counter).zfill(3))
                
                # Insert new loadcell device
                cursor.execute('''
                    INSERT INTO loadcell_device (
                        id, name, group_id, service_id, device_path, channel,
                        tare_offset, known_weight, known_weight_raw, shift_bits,
                        unit, capacity, capacity_name, enabled
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    new_device_id, new_name, old_device['group_id'],
                    old_device['service_id'], old_device['device_path'],
                    old_device['channel'], old_device['tare_offset'],
                    old_device['known_weight'], old_device['known_weight_raw'],
                    old_device['shift_bits'], old_device['unit'],
                    old_device['capacity'], old_device['capacity_name'],
                    old_device['enabled']
                ))
                
                # Duplicate all Loadcell datapoints
                cursor.execute('''
                    SELECT name
                    FROM loadcell_datapoints
                    WHERE device_id = ?
                ''', (device_id,))
                
                datapoints = cursor.fetchall()
                for dp in datapoints:
                    cursor.execute('''
                        INSERT INTO loadcell_datapoints (device_id, name)
                        VALUES (?, ?)
                    ''', (new_device_id, dp[0]))
                
                # Initialize status for new device
                initialize_device_status(new_device_id, 'Online')
                
                conn.commit()
                conn.close()
                
                return web.json_response({
                    'success': True,
                    'message': 'Device duplicated successfully as {}'.format(new_name),
                    'device_id': new_device_id,
                    'device_name': new_name,
                    'datapoints_copied': len(datapoints)
                })
            else:
                conn.close()
                return web.json_response({
                    'success': False,
                    'message': 'Device not found'
                }, status=404)
        
    except Exception as e:
        print("Error duplicating device: {}".format(e))
        import traceback
        traceback.print_exc()
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# DEVICE GROUPS
# ============================================================================

async def get_all_groups(request):
    """GET all device groups"""
    try:
        from database import get_all_device_groups
        groups = get_all_device_groups()
        return web.json_response({'groups': groups})
    except Exception as e:
        print("Error getting groups: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)

async def add_group(request):
    """POST - Add new group"""
    try:
        data = await request.json()
        
        from database import add_device_group
        group_id = add_device_group(
            data.get('name'),
            data.get('color', 'blue'),
            data.get('description', '')
        )
        
        if group_id:
            return web.json_response({
                'success': True,
                'message': 'Group created successfully',
                'group_id': group_id
            })
        else:
            return web.json_response({
                'success': False,
                'message': 'Failed to create group'
            }, status=500)
            
    except Exception as e:
        print("Error adding group: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)

async def delete_group(request):
    """DELETE - Delete group"""
    try:
        group_id = request.match_info['group_id']
        
        from database import delete_device_group
        success = delete_device_group(group_id)
        
        if success:
            return web.json_response({
                'success': True,
                'message': 'Group deleted successfully'
            })
        else:
            return web.json_response({
                'success': False,
                'message': 'Failed to delete group'
            }, status=500)
            
    except Exception as e:
        print("Error deleting group: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)

async def assign_devices_to_group(request):
    """POST - Assign devices to group"""
    try:
        group_id = request.match_info['group_id']
        data = await request.json()
        device_ids = data.get('device_ids', [])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for device_id in device_ids:
            cursor.execute('UPDATE modbus_device SET group_id = ? WHERE id = ?', (group_id, device_id))
            cursor.execute('UPDATE loadcell_device SET group_id = ? WHERE id = ?', (group_id, device_id))
        
        conn.commit()
        conn.close()
        
        return web.json_response({
            'success': True,
            'message': 'Devices assigned to group successfully'
        })
        
    except Exception as e:
        print("Error assigning devices to group: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# IMPORT / EXPORT DEVICES
# ============================================================================

async def export_devices_csv(request):
    """GET - Export all devices to CSV"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID', 'Name', 'Type', 'Protocol', 'Group',
            'IP Address', 'Port', 'Serial Port', 'Slave ID',
            'Baud Rate', 'Data Bits', 'Parity', 'Stop Bits',
            'Device Path', 'Channel', 'Capacity', 'Unit', 'Enabled'
        ])
        
        # Export Modbus devices
        cursor.execute('''
            SELECT m.id, m.name, m.device_type, g.name as group_name,
                   m.ip_address, m.port, m.serial_port, m.slave_id,
                   m.baud_rate, m.data_bits, m.parity, m.stop_bits, m.enabled
            FROM modbus_device m
            LEFT JOIN device_groups g ON m.group_id = g.id
            ORDER BY CAST(m.id AS INTEGER)
        ''')
        
        for row in cursor.fetchall():
            device_id, name, device_type, group_name, ip, port, serial, slave_id, \
                baud, data_bits, parity, stop_bits, enabled = row
            
            protocol = 'modbus-tcp' if device_type == 'tcp' else 'modbus-rtu'
            
            writer.writerow([
                device_id, name, 'Modbus', protocol, group_name or '',
                ip or '', port or '', serial or '', slave_id or '',
                baud or '', data_bits or '', parity or '', stop_bits or '',
                '', '', '', '', '1' if enabled else '0'
            ])
        
        # Export Loadcell devices (only LC1 is valid - enforce single loadcell)
        cursor.execute('''
            SELECT l.id, l.name, g.name as group_name,
                   l.device_path, l.channel, l.capacity, l.unit, l.enabled
            FROM loadcell_device l
            LEFT JOIN device_groups g ON l.group_id = g.id
            WHERE l.id = 'LC1'
            LIMIT 1
        ''')
        
        for row in cursor.fetchall():
            device_id, name, group_name, device_path, channel, capacity, unit, enabled = row
            # Only export LC1 - system enforces single loadcell
            writer.writerow([
                'LC1', name, 'Loadcell', 'loadcell', group_name or '',
                '', '', '', '',
                '', '', '', '',
                device_path or '', channel or 0, capacity or '', unit or 'g', '1' if enabled else '0'
            ])
        
        conn.close()
        
        # Get CSV content
        csv_content = output.getvalue()
        output.close()
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = 'devices_export_{}.csv'.format(timestamp)
        
        # Return CSV file
        return web.Response(
            text=csv_content,
            headers={
                'Content-Type': 'text/csv',
                'Content-Disposition': 'attachment; filename="{}"'.format(filename)
            }
        )
        
    except Exception as e:
        print("Error exporting devices: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)

async def import_devices_csv(request):
    """POST - Import devices from CSV with duplicate detection"""
    try:
        # Get multipart data
        reader = await request.multipart()
        field = await reader.next()
        
        if field.name != 'file':
            return web.json_response({'error': 'No file provided'}, status=400)
        
        # Read CSV content
        csv_content = await field.read(decode=True)
        
        # Check if this is a confirmation request (skip_existing parameter)
        skip_existing = request.rel_url.query.get('skip_existing', 'false').lower() == 'true'
        replace_existing = request.rel_url.query.get('replace_existing', 'false').lower() == 'true'
        
        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(csv_content.decode('utf-8')))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First pass: Check for duplicates
        duplicates = []
        new_devices = []
        
        for row_num, row in enumerate(csv_reader, start=2):
            try:
                name = row.get('Name', '').strip()
                device_type = row.get('Type', '').strip()
                
                if not name:
                    continue
                
                # Check if device with same name already exists
                if device_type.lower() == 'loadcell':
                    # ENFORCE: Only one loadcell allowed - check if LC1 already exists
                    cursor.execute('SELECT COUNT(*) FROM loadcell_device')
                    lc_existing_count = cursor.fetchone()[0]
                    # Also count how many loadcell rows are already in new_devices
                    lc_in_new = sum(1 for d in new_devices if d.get('data', {}).get('Type', '').lower() == 'loadcell')
                    if lc_existing_count > 0 or lc_in_new > 0:
                        errors_pre = errors_pre if 'errors_pre' in dir() else []
                        duplicates.append({
                            'row': row_num,
                            'name': name,
                            'type': device_type,
                            'existing_id': 'LC1',
                            'reason': 'Only one Load Cell (LC1) is allowed'
                        })
                        continue
                    cursor.execute('SELECT id, name FROM loadcell_device WHERE name = ?', (name,))
                else:
                    cursor.execute('SELECT id, name FROM modbus_device WHERE name = ?', (name,))
                
                existing = cursor.fetchone()
                
                if existing:
                    duplicates.append({
                        'row': row_num,
                        'name': name,
                        'type': device_type,
                        'existing_id': existing[0]
                    })
                else:
                    new_devices.append({
                        'row': row_num,
                        'name': name,
                        'data': row
                    })
                    
            except Exception as e:
                continue
        
        # If duplicates found and user hasn't confirmed action
        if duplicates and not skip_existing and not replace_existing:
            conn.close()
            return web.json_response({
                'success': False,
                'requires_confirmation': True,
                'duplicates': duplicates,
                'new_devices_count': len(new_devices),
                'message': 'Found {} duplicate device(s). Please choose how to proceed.'.format(len(duplicates))
            })
        
        # Second pass: Import devices based on user choice
        imported_count = 0
        replaced_count = 0
        skipped_count = 0
        errors = []
        
        # Reset CSV reader
        csv_reader = csv.DictReader(io.StringIO(csv_content.decode('utf-8')))
        
        for row_num, row in enumerate(csv_reader, start=2):
            try:
                name = row.get('Name', '').strip()
                device_type = row.get('Type', '').strip()
                protocol = row.get('Protocol', '').strip().lower()
                group_name = row.get('Group', '').strip()
                
                if not name:
                    errors.append("Row {}: Missing device name".format(row_num))
                    continue
                
                # Check if device exists
                if device_type.lower() == 'loadcell':
                    cursor.execute('SELECT id FROM loadcell_device WHERE name = ?', (name,))
                else:
                    cursor.execute('SELECT id FROM modbus_device WHERE name = ?', (name,))
                
                existing_device = cursor.fetchone()
                
                if existing_device:
                    if skip_existing:
                        skipped_count += 1
                        continue
                    elif replace_existing:
                        # Delete existing device
                        device_id = existing_device[0]
                        if device_type.lower() == 'loadcell':
                            cursor.execute('DELETE FROM loadcell_datapoints WHERE device_id = ?', (device_id,))
                            cursor.execute('DELETE FROM loadcell_device WHERE id = ?', (device_id,))
                        else:
                            cursor.execute('DELETE FROM modbus_datapoints WHERE device_id = ?', (device_id,))
                            cursor.execute('DELETE FROM modbus_device WHERE id = ?', (device_id,))
                        
                        remove_device_status(device_id)
                        replaced_count += 1
                    else:
                        # Should not reach here if confirmation flow works
                        skipped_count += 1
                        continue
                
                # Get or create group
                group_id = None
                if group_name:
                    cursor.execute('SELECT id FROM device_groups WHERE name = ?', (group_name,))
                    group_row = cursor.fetchone()
                    if group_row:
                        group_id = group_row[0]
                    else:
                        # Create group if it doesn't exist
                        cursor.execute('INSERT INTO device_groups (name, color) VALUES (?, ?)', 
                                     (group_name, 'blue'))
                        group_id = cursor.lastrowid
                
                # Get service_id
                service_name = 'loadcell' if device_type.lower() == 'loadcell' else 'modbus'
                service_id = get_service_by_name(service_name)
                
                # Generate device ID using max ID logic
                if device_type.lower() == 'loadcell':
                    # ENFORCE: Only LC1 allowed
                    cursor.execute('SELECT COUNT(*) FROM loadcell_device')
                    if cursor.fetchone()[0] >= 1:
                        errors.append('Row {}: Only one Load Cell (LC1) is allowed. Skipping.'.format(row_num))
                        skipped_count += 1
                        continue
                    device_id = 'LC1'
                else:
                    cursor.execute('SELECT id FROM modbus_device WHERE id LIKE "MB%" ORDER BY id')
                    existing_ids = [r[0] for r in cursor.fetchall()]
                    max_num = 0
                    for existing_id in existing_ids:
                        try:
                            num = int(existing_id[2:])
                            if num > max_num:
                                max_num = num
                        except ValueError:
                            continue
                    device_id = 'MB{}'.format(max_num + 1)
                
                if device_type.lower() == 'loadcell':
                    # Import Loadcell device
                    device_path = row.get('Device Path', '/dev/spidev0.0').strip()
                    capacity = float(row.get('Capacity', '40000'))
                    unit = row.get('Unit', 'g').strip() or 'g'
                    channel = int(row.get('Channel', '0') or '0')
                    enabled = row.get('Enabled', '1').strip() == '1'
                    
                    cursor.execute('''
                        INSERT INTO loadcell_device (
                            id, name, group_id, service_id, device_path, 
                            channel, capacity, unit, load_name, capacity_name, enabled
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        device_id, name, group_id, service_id, device_path,
                        channel, capacity, unit, 'load', 'capacity', enabled
                    ))
                    
                    # Create default datapoints
                    cursor.execute(
                        "INSERT OR IGNORE INTO loadcell_datapoints (device_id, name, unit) VALUES (?, 'load', '')",
                        (device_id,)
                    )
                    cursor.execute(
                        "INSERT OR IGNORE INTO loadcell_datapoints (device_id, name, unit) VALUES (?, 'capacity', '')",
                        (device_id,)
                    )
                    
                    # Initialize status
                    initialize_device_status(device_id, 'Online' if enabled else 'Offline')
                    
                else:
                    # Import Modbus device
                    modbus_type = 'tcp' if 'tcp' in protocol else 'rtu'
                    
                    slave_id = int(row.get('Slave ID', '1') or '1')
                    enabled = row.get('Enabled', '1').strip() == '1'
                    
                    if modbus_type == 'tcp':
                        ip_address = row.get('IP Address', '').strip()
                        port = int(row.get('Port', '502') or '502')
                        
                        cursor.execute('''
                            INSERT INTO modbus_device (
                                id, name, device_type, group_id, service_id,
                                slave_id, timeout_ms, retry_count, polling_interval_ms,
                                ip_address, port, enabled
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            device_id, name, modbus_type, group_id, service_id,
                            slave_id, 1000, 3, 100,
                            ip_address, port, enabled
                        ))
                    else:  # RTU
                        serial_port = row.get('Serial Port', '/dev/ttymxc2').strip()
                        baud_rate = int(row.get('Baud Rate', '9600') or '9600')
                        data_bits = int(row.get('Data Bits', '8') or '8')
                        parity = row.get('Parity', 'N').strip()
                        stop_bits = int(row.get('Stop Bits', '1') or '1')
                        
                        cursor.execute('''
                            INSERT INTO modbus_device (
                                id, name, device_type, group_id, service_id,
                                slave_id, timeout_ms, retry_count, polling_interval_ms,
                                serial_port, baud_rate, parity, data_bits, stop_bits, enabled
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            device_id, name, modbus_type, group_id, service_id,
                            slave_id, 1000, 3, 100,
                            serial_port, baud_rate, parity, data_bits, stop_bits, enabled
                        ))
                    
                    # Initialize status
                    initialize_device_status(device_id, 'Online' if enabled else 'Offline')
                
                imported_count += 1
                
            except Exception as e:
                errors.append("Row {}: {}".format(row_num, str(e)))
                continue
        
        conn.commit()
        conn.close()
        
        message_parts = []
        if imported_count > 0:
            message_parts.append('Successfully imported {} device(s)'.format(imported_count))
        if replaced_count > 0:
            message_parts.append('Replaced {} existing device(s)'.format(replaced_count))
        if skipped_count > 0:
            message_parts.append('Skipped {} duplicate(s)'.format(skipped_count))
        
        response_data = {
            'success': True,
            'message': ', '.join(message_parts) if message_parts else 'No devices imported',
            'imported_count': imported_count,
            'replaced_count': replaced_count,
            'skipped_count': skipped_count,
            'errors': errors
        }
        
        return web.json_response(response_data)
        
    except Exception as e:
        print("Error importing devices: {}".format(e))
        import traceback
        traceback.print_exc()
        return web.json_response({'error': str(e)}, status=500)

async def download_csv_template(request):
    """GET - Download CSV template for device import"""
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID', 'Name', 'Type', 'Protocol', 'Group',
            'IP Address', 'Port', 'Serial Port', 'Slave ID',
            'Baud Rate', 'Data Bits', 'Parity', 'Stop Bits',
            'Device Path', 'Capacity', 'Enabled'
        ])
        
        # Write example rows
        writer.writerow([
            '', 'Example Modbus TCP', 'Modbus', 'modbus-tcp', 'Crane-01',
            '192.168.1.100', '502', '', '1',
            '', '', '', '',
            '', '', '1'
        ])
        
        writer.writerow([
            '', 'Example Modbus RTU', 'Modbus', 'modbus-rtu', 'Crane-01',
            '', '', '/dev/ttyUSB0', '1',
            '9600', '8', 'None', '1',
            '', '', '1'
        ])
        
        writer.writerow([
            '', 'Example Loadcell', 'Loadcell', 'loadcell', 'Safety Sensors',
            '', '', '', '',
            '', '', '', '',
            '/dev/spidev0.0', '40000', '1'
        ])
        
        csv_content = output.getvalue()
        output.close()
        
        return web.Response(
            text=csv_content,
            headers={
                'Content-Type': 'text/csv',
                'Content-Disposition': 'attachment; filename="device_import_template.csv"'
            }
        )
        
    except Exception as e:
        print("Error generating template: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# GET DEVICE DATAPOINTS
# ============================================================================

async def get_device_datapoints(request):
    """GET datapoints for a specific device"""
    try:
        device_id = request.match_info['device_id']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check device type
        cursor.execute('SELECT id FROM modbus_device WHERE id = ?', (device_id,))
        is_modbus = cursor.fetchone() is not None
        
        datapoints = []
        
        if is_modbus:
            # Get Modbus datapoints
            cursor.execute('''
                SELECT id, name, register_address, register_type, data_type,
                       byte_order, word_order, scale_factor, offset, unit, description
                FROM modbus_datapoints
                WHERE device_id = ?
                ORDER BY name
            ''', (device_id,))
            
            for row in cursor.fetchall():
                datapoints.append({
                    'id': row[0],
                    'name': row[1],
                    'register_address': row[2],
                    'register_type': row[3],
                    'data_type': row[4],
                    'byte_order': row[5],
                    'word_order': row[6],
                    'scale_factor': row[7],
                    'offset': row[8],
                    'unit': row[9],
                    'description': row[10],
                    'type': 'Modbus'
                })
        else:
            # Get Loadcell datapoints
            cursor.execute('''
                SELECT id, name
                FROM loadcell_datapoints
                WHERE device_id = ?
                ORDER BY name
            ''', (device_id,))
            
            for row in cursor.fetchall():
                datapoints.append({
                    'id': row[0],
                    'name': row[1],
                    'type': 'Loadcell'
                })
        
        conn.close()
        return web.json_response({'datapoints': datapoints})
        
    except Exception as e:
        print("Error getting device datapoints: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# MANUAL STATUS UPDATE (for testing/debugging)
# ============================================================================

async def update_device_status_api(request):
    """POST - Manually update device status (for testing)"""
    try:
        device_id = request.match_info['device_id']
        data = await request.json()
        
        status = data.get('status', 'Offline')
        last_poll = data.get('last_poll')
        
        # Update status
        result = update_device_status(device_id, status, last_poll)
        
        # Broadcast to all connected clients
        await broadcast_device_status(device_id, result['status'], result['last_poll'])
        
        return web.json_response({
            'success': True,
            'device_id': device_id,
            'status': result['status'],
            'last_poll': result['last_poll']
        })
        
    except Exception as e:
        print("Error updating device status: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)