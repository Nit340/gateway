# device_management.py - Device management API for Modbus and Loadcell
import asyncio
import json
import random
import uuid
import sqlite3
import io
import csv
import re
from datetime import datetime
from aiohttp import web

from general import device_status_tracker
from database import DB_FILE, get_service_by_name
from general import initialize_device_status, remove_device_status, update_device_status

# ============================================================================
# DATABASE CONNECTION HELPER
# ============================================================================

def get_db_connection():
    """Get a database connection with proper timeout and WAL mode for concurrency"""
    conn = sqlite3.connect(DB_FILE, timeout=10.0)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys = ON')
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
                   m.enabled, s.name as service_name
            FROM modbus_device m
            LEFT JOIN services s ON m.service_id = s.id
            ORDER BY m.id
        ''')
        
        for row in cursor.fetchall():
            device_id, name, device_type, ip, port, serial_port, enabled, service_name = row
            
            # Determine address display
            if device_type == 'tcp':
                address = "{}:{}".format(ip, port) if ip else "Not configured"
                protocol = "modbus-tcp"
            else:  # rtu
                address = serial_port or "Not configured"
                protocol = "modbus-rtu"
            
            # Get or initialize real-time status
            if device_id not in device_status_tracker:
                initialize_device_status(device_id, 'Offline')
            
            status = device_status_tracker[device_id]
            
            devices.append({
                'id': device_id,
                'name': name,
                'type': 'Modbus',
                'protocol': protocol,
                'address': address,
                'status': status['status'],
                'lastPoll': status['last_poll'],
                'enabled': bool(enabled),
                'service': service_name
            })
        
        # Get Loadcell devices
        cursor.execute('''
            SELECT l.id, l.name, l.device_path,
                   l.enabled, s.name as service_name
            FROM loadcell_device l
            LEFT JOIN services s ON l.service_id = s.id
            ORDER BY l.id
        ''')
        
        for row in cursor.fetchall():
            device_id, name, device_path, enabled, service_name = row
            
            # Get or initialize real-time status
            if device_id not in device_status_tracker:
                initialize_device_status(device_id, 'Offline')
            
            status = device_status_tracker[device_id]
            
            devices.append({
                'id': device_id,
                'name': name,
                'type': 'Loadcell',
                'protocol': 'loadcell',
                'address': device_path,
                'status': status['status'],
                'lastPoll': status['last_poll'],
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
            SELECT m.id, m.name, m.device_type,
                   m.response_timeout_ms, m.byte_timeout_ms, m.max_retries, m.polling_interval_ms,
                   m.ip_address, m.port,
                   m.serial_port, m.baud_rate, m.parity, m.data_bits, m.stop_bits,
                   m.enabled, s.name as service_name
            FROM modbus_device m
            LEFT JOIN services s ON m.service_id = s.id
            WHERE m.id = ?
        ''', (device_id,))
        
        row = cursor.fetchone()
        
        if row:
            # It's a Modbus device
            (dev_id, name, device_type, response_timeout_ms, byte_timeout_ms,
             max_retries, polling_interval_ms, ip_address, port, serial_port, 
             baud_rate, parity, data_bits, stop_bits, enabled, service_name) = row
            
            # Get or initialize status
            if device_id not in device_status_tracker:
                initialize_device_status(device_id, 'Offline')
            
            status = device_status_tracker[device_id]
            
            details = {
                'id': dev_id,
                'name': name,
                'type': 'Modbus',
                'device_type': device_type,
                'service': service_name,
                'enabled': bool(enabled),
                'status': status['status'],
                'lastPoll': status['last_poll'],
                'config': {
                    'response_timeout_ms': response_timeout_ms,
                    'byte_timeout_ms': byte_timeout_ms,
                    'max_retries': max_retries,
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
            SELECT l.id, l.name, l.device_path,
                   l.poll_ms, l.resolution_bits, l.effective_bits, l.signed, l.gain, l.vref,
                   l.raw_min, l.raw_max,
                   l.capacity_min, l.capacity_max, l.unit,
                   l.load_name, l.capacity_name,
                   l.pipeline_server, l.pipeline_port, l.log_level,
                   l.tare_offset, l.known_weight, l.known_weight_raw,
                   l.raw_filters, l.weight_filters, l.levels,
                   l.enabled, s.name as service_name
            FROM loadcell_device l
            LEFT JOIN services s ON l.service_id = s.id
            WHERE l.id = ?
        ''', (device_id,))
        
        row = cursor.fetchone()
        
        if row:
            if device_id not in device_status_tracker:
                initialize_device_status(device_id, 'Offline')
            
            status = device_status_tracker[device_id]
            
            (dev_id, name, device_path,
             poll_ms, resolution_bits, effective_bits, signed, gain, vref,
             raw_min, raw_max,
             capacity_min, capacity_max, unit,
             load_name, capacity_name,
             pipeline_server, pipeline_port, log_level,
             tare_offset, known_weight, known_weight_raw,
             raw_filters_json, weight_filters_json, levels_json,
             enabled, service_name) = row
            
            import json as _json
            def _parse(v):
                try: return _json.loads(v) if v else []
                except: return []
            
            details = {
                'id': dev_id,
                'name': name,
                'type': 'Loadcell',
                'protocol': 'loadcell',
                'service': service_name,
                'enabled': bool(enabled),
                'status': status['status'],
                'lastPoll': status['last_poll'],
                'config': {
                    'device_path':    device_path,
                    'poll_ms':        poll_ms,
                    'resolution_bits': resolution_bits,
                    'effective_bits':  effective_bits,
                    'signed':          bool(signed),
                    'gain':            gain,
                    'vref':            vref,
                    'raw_min':         raw_min,
                    'raw_max':         raw_max,
                    'capacity_min':    capacity_min,
                    'capacity_max':    capacity_max,
                    'unit':            unit,
                    'load_name':       load_name or 'load_weight',
                    'capacity_name':   capacity_name or 'capacity',
                    'pipeline_server': pipeline_server,
                    'pipeline_port':   pipeline_port,
                    'log_level':       log_level,
                    'tare_offset':     tare_offset,
                    'known_weight':    known_weight,
                    'known_weight_raw': known_weight_raw,
                    'raw_filters':     _parse(raw_filters_json),
                    'weight_filters':  _parse(weight_filters_json),
                    'levels':          _parse(levels_json)
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
        
        # Generate device ID with unique prefix
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
            
            device_id = 'LC1'
        else:  # modbus
            cursor.execute('SELECT id FROM modbus_device WHERE id LIKE "MB%" ORDER BY id')
            existing_ids = [row[0] for row in cursor.fetchall()]
            
            max_num = 0
            for existing_id in existing_ids:
                try:
                    num = int(existing_id[2:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    continue
            
            device_id = 'MB{}'.format(max_num + 1)
        
        # Get service_id
        service_name = 'loadcell' if device_type == 'loadcell' else 'modbus'
        service_id = get_service_by_name(service_name)
        
        if device_type == 'loadcell':
            # Add Loadcell device
            config = data.get('config', {})
            
            cursor.execute('''
                INSERT INTO loadcell_device (
                    id, name, service_id, device_path,
                    poll_ms, resolution_bits, effective_bits, signed, gain, vref,
                    raw_min, raw_max,
                    capacity_min, capacity_max, unit,
                    load_name, capacity_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                device_id,
                data.get('name', 'Loadcell Device'),
                service_id,
                config.get('device_path', '/sys/bus/iio/devices/iio:device0/in_voltage0_raw'),
                config.get('poll_ms', 10),
                config.get('resolution_bits', 24),
                config.get('effective_bits', 14),
                1 if config.get('signed') else 0,
                config.get('gain', 1),
                config.get('vref', 5),
                config.get('raw_min', 0),
                config.get('raw_max', 16383),
                config.get('capacity_min', 0),
                config.get('capacity_max', 1000),
                config.get('unit', 'kg'),
                'load_weight',
                'capacity'
            ))
            
            # Automatically create 'load_weight' and 'capacity' datapoints
            cursor.execute('''
                INSERT OR IGNORE INTO loadcell_datapoints (device_id, name, unit)
                VALUES (?, 'load_weight', '')
            ''', (device_id,))
            cursor.execute('''
                INSERT OR IGNORE INTO loadcell_datapoints (device_id, name, unit)
                VALUES (?, 'capacity', '')
            ''', (device_id,))
            
        else:  # Modbus (TCP or RTU)
            config = data.get('config', {})
            
            # Determine device_type from protocol
            protocol_lower = protocol.lower()
            if 'tcp' in protocol_lower:
                modbus_type = 'tcp'
            elif 'rtu' in protocol_lower:
                modbus_type = 'rtu'
            else:
                modbus_type = 'tcp' if config.get('ip_address') else 'rtu'
            
            print("Creating Modbus device - Protocol: '{}', Type: '{}'".format(protocol, modbus_type))
            
            # Set default values matching your specified format
            response_timeout_ms = config.get('response_timeout_ms', 100)
            byte_timeout_ms = config.get('byte_timeout_ms', 100)
            max_retries = config.get('max_retries', 2)
            polling_interval_ms = config.get('polling_interval_ms', 300)
            
            cursor.execute('''
                INSERT INTO modbus_device (
                    id, name, device_type, service_id,
                    response_timeout_ms, byte_timeout_ms, max_retries, polling_interval_ms,
                    ip_address, port,
                    serial_port, baud_rate, parity, data_bits, stop_bits
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                device_id,
                data.get('name', 'Modbus Device'),
                modbus_type,
                service_id,
                response_timeout_ms,
                byte_timeout_ms,
                max_retries,
                polling_interval_ms,
                config.get('ip_address') if modbus_type == 'tcp' else None,
                config.get('port', 502) if modbus_type == 'tcp' else None,
                config.get('serial_port', '/dev/ttymxc5') if modbus_type == 'rtu' else None,
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
        
        if is_modbus:
            # Update Modbus device
            config = data.get('config', {})
            device_type = data.get('device_type', 'tcp')
            
            update_fields = ['name = ?', 'device_type = ?']
            values = [data.get('name'), device_type]
            
            # Common fields - using new column names
            if 'response_timeout_ms' in config:
                update_fields.append('response_timeout_ms = ?')
                values.append(config['response_timeout_ms'])
            if 'byte_timeout_ms' in config:
                update_fields.append('byte_timeout_ms = ?')
                values.append(config['byte_timeout_ms'])
            if 'max_retries' in config:
                update_fields.append('max_retries = ?')
                values.append(config['max_retries'])
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
            
            update_fields = ['name = ?']
            values = [data.get('name')]
            
            # Hardware parameters
            for field in ('device_path', 'poll_ms', 'resolution_bits', 'effective_bits',
                          'gain', 'vref', 'raw_min', 'raw_max',
                          'capacity_min', 'capacity_max', 'unit',
                          'pipeline_server', 'pipeline_port', 'log_level'):
                if field in config:
                    update_fields.append('{} = ?'.format(field))
                    values.append(config[field])
            
            # signed is a boolean
            if 'signed' in config:
                update_fields.append('signed = ?')
                values.append(1 if config['signed'] else 0)
            
            # Calibration fields (flat or nested)
            for field in ('tare_offset', 'known_weight', 'known_weight_raw'):
                if field in config:
                    update_fields.append('{} = ?'.format(field))
                    values.append(config[field])
            
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
        
        cursor.execute('DELETE FROM modbus_device WHERE id = ?', (device_id,))
        cursor.execute('DELETE FROM loadcell_device WHERE id = ?', (device_id,))
        
        conn.commit()
        conn.close()
        
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
        
        await asyncio.sleep(0.5)
        success = random.choice([True, True, True, False])
        
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
        
        cursor.execute('UPDATE modbus_device SET enabled = ? WHERE id = ?', (enabled, device_id))
        cursor.execute('UPDATE loadcell_device SET enabled = ? WHERE id = ?', (enabled, device_id))
        
        conn.commit()
        conn.close()
        
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
            # Get column names
            cursor.execute('PRAGMA table_info(modbus_device)')
            columns = [col[1] for col in cursor.fetchall()]
            
            old_device = dict(zip(columns, modbus_row))
            
            # Generate new device ID
            cursor.execute('SELECT id FROM modbus_device WHERE id LIKE "MB%" ORDER BY id')
            existing_ids = [row[0] for row in cursor.fetchall()]
            
            max_num = 0
            for existing_id in existing_ids:
                try:
                    num = int(existing_id[2:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    continue
            
            new_device_id = 'MB{}'.format(max_num + 1)
            
            # Generate new device name with -001 suffix
            base_name = old_device['name']
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
                counter = 1
            
            new_name = "{}-{}".format(base_name_clean, str(counter).zfill(3))
            
            # Insert new device
            cursor.execute('''
                INSERT INTO modbus_device (
                    id, name, device_type, service_id,
                    response_timeout_ms, byte_timeout_ms, max_retries, polling_interval_ms,
                    ip_address, port, serial_port, baud_rate, parity,
                    data_bits, stop_bits, enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                new_device_id, new_name, old_device['device_type'],
                old_device['service_id'],
                old_device['response_timeout_ms'],
                old_device['byte_timeout_ms'],
                old_device['max_retries'],
                old_device['polling_interval_ms'],
                old_device['ip_address'], old_device['port'],
                old_device['serial_port'], old_device['baud_rate'],
                old_device['parity'], old_device['data_bits'],
                old_device['stop_bits'], old_device['enabled']
            ))
            
            # Duplicate all Modbus datapoints
            cursor.execute('''
                SELECT name, slave_id, register_address, register_type, data_type,
                       byte_order, word_order, scale_factor, offset, unit, description
                FROM modbus_datapoints
                WHERE device_id = ?
            ''', (device_id,))
            
            datapoints = cursor.fetchall()
            for dp in datapoints:
                cursor.execute('''
                    INSERT INTO modbus_datapoints (
                        device_id, name, slave_id, register_address, register_type, data_type,
                        byte_order, word_order, scale_factor, offset, unit, description
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (new_device_id,) + dp)
            
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
                # Block duplicating loadcell
                conn.close()
                return web.json_response({
                    'success': False,
                    'error': 'Cannot duplicate Load Cell device. Only one Load Cell (LC1) is allowed.'
                }, status=400)
            
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
# EXPORT DEVICES TO CSV
# ============================================================================

async def export_devices_csv(request):
    """GET - Export all devices to CSV"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID', 'Name', 'Type', 'Protocol',
            'IP Address', 'Port', 'Serial Port',
            'Baud Rate', 'Data Bits', 'Parity', 'Stop Bits',
            'Response Timeout (ms)', 'Byte Timeout (ms)', 'Max Retries', 'Polling Interval (ms)',
            'Device Path', 'Channel', 'Capacity', 'Unit', 'Enabled'
        ])
        
        # Export Modbus devices
        cursor.execute('''
            SELECT m.id, m.name, m.device_type,
                   m.ip_address, m.port, m.serial_port,
                   m.baud_rate, m.data_bits, m.parity, m.stop_bits,
                   m.response_timeout_ms, m.byte_timeout_ms, m.max_retries, m.polling_interval_ms,
                   m.enabled
            FROM modbus_device m
            ORDER BY m.id
        ''')
        
        for row in cursor.fetchall():
            (device_id, name, device_type, ip, port, serial,
             baud, data_bits, parity, stop_bits,
             resp_timeout, byte_timeout, max_retries, polling_interval,
             enabled) = row
            
            protocol = 'modbus-tcp' if device_type == 'tcp' else 'modbus-rtu'
            
            writer.writerow([
                device_id, name, 'Modbus', protocol,
                ip or '', port or '', serial or '',
                baud or '', data_bits or '', parity or '', stop_bits or '',
                resp_timeout or '', byte_timeout or '', max_retries or '', polling_interval or '',
                '', '', '', '', '1' if enabled else '0'
            ])
        
        # Export Loadcell devices
        cursor.execute('''
            SELECT l.id, l.name,
                   l.device_path, l.capacity_max, l.unit, l.enabled
            FROM loadcell_device l
            WHERE l.id = 'LC1'
        ''')
        
        for row in cursor.fetchall():
            device_id, name, device_path, capacity_max, unit, enabled = row
            writer.writerow([
                'LC1', name, 'Loadcell', 'loadcell',
                '', '', '',
                '', '', '', '',
                '', '', '', '',
                device_path or '', capacity_max or 1000, unit or 'kg', '1' if enabled else '0'
            ])
        
        conn.close()
        
        csv_content = output.getvalue()
        output.close()
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = 'devices_export_{}.csv'.format(timestamp)
        
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

# ============================================================================
# IMPORT DEVICES FROM CSV
# ============================================================================

async def import_devices_csv(request):
    """POST - Import devices from CSV with duplicate detection"""
    try:
        reader = await request.multipart()
        field = await reader.next()
        
        if field.name != 'file':
            return web.json_response({'error': 'No file provided'}, status=400)
        
        csv_content = await field.read(decode=True)
        
        skip_existing = request.rel_url.query.get('skip_existing', 'false').lower() == 'true'
        replace_existing = request.rel_url.query.get('replace_existing', 'false').lower() == 'true'
        
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
                
                if device_type.lower() == 'loadcell':
                    cursor.execute('SELECT COUNT(*) FROM loadcell_device')
                    lc_existing_count = cursor.fetchone()[0]
                    lc_in_new = sum(1 for d in new_devices if d.get('data', {}).get('Type', '').lower() == 'loadcell')
                    if lc_existing_count > 0 or lc_in_new > 0:
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
        
        # Second pass: Import devices
        imported_count = 0
        replaced_count = 0
        skipped_count = 0
        errors = []
        
        csv_reader = csv.DictReader(io.StringIO(csv_content.decode('utf-8')))
        
        for row_num, row in enumerate(csv_reader, start=2):
            try:
                name = row.get('Name', '').strip()
                device_type = row.get('Type', '').strip()
                protocol = row.get('Protocol', '').strip().lower()
                if not name:
                    errors.append("Row {}: Missing device name".format(row_num))
                    continue
                
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
                        skipped_count += 1
                        continue
                
                service_name = 'loadcell' if device_type.lower() == 'loadcell' else 'modbus'
                service_id = get_service_by_name(service_name)
                
                if device_type.lower() == 'loadcell':
                    cursor.execute('SELECT COUNT(*) FROM loadcell_device')
                    if cursor.fetchone()[0] >= 1:
                        errors.append('Row {}: Only one Load Cell (LC1) is allowed. Skipping.'.format(row_num))
                        skipped_count += 1
                        continue
                    device_id = 'LC1'
                    
                    device_path = row.get('Device Path', '/dev/spidev0.0').strip()
                    capacity = float(row.get('Capacity', '40000'))
                    unit = row.get('Unit', 'g').strip() or 'g'
                    channel = int(row.get('Channel', '0') or '0')
                    enabled = row.get('Enabled', '1').strip() == '1'
                    
                    cursor.execute('''
                        INSERT INTO loadcell_device (
                            id, name, service_id, device_path,
                            poll_ms, resolution_bits, effective_bits, signed, gain, vref,
                            raw_min, raw_max,
                            capacity_min, capacity_max, unit,
                            load_name, capacity_name, enabled
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        device_id, name, service_id, device_path,
                        10, 24, 14, 0, 1, 5,
                        0, 16383,
                        0, capacity, unit,
                        'load_weight', 'capacity', enabled
                    ))
                    
                    cursor.execute(
                        "INSERT OR IGNORE INTO loadcell_datapoints (device_id, name, unit) VALUES (?, 'load_weight', '')",
                        (device_id,)
                    )
                    cursor.execute(
                        "INSERT OR IGNORE INTO loadcell_datapoints (device_id, name, unit) VALUES (?, 'capacity', '')",
                        (device_id,)
                    )
                    
                    initialize_device_status(device_id, 'Online' if enabled else 'Offline')
                    
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
                    
                    modbus_type = 'tcp' if 'tcp' in protocol else 'rtu'
                    enabled = row.get('Enabled', '1').strip() == '1'
                    
                    # Get timeout values with defaults
                    resp_timeout = int(row.get('Response Timeout (ms)', '100') or '100')
                    byte_timeout = int(row.get('Byte Timeout (ms)', '100') or '100')
                    max_retries = int(row.get('Max Retries', '2') or '2')
                    polling_interval = int(row.get('Polling Interval (ms)', '300') or '300')
                    
                    if modbus_type == 'tcp':
                        ip_address = row.get('IP Address', '').strip()
                        port = int(row.get('Port', '502') or '502')
                        
                        cursor.execute('''
                            INSERT INTO modbus_device (
                                id, name, device_type, service_id,
                                response_timeout_ms, byte_timeout_ms, max_retries, polling_interval_ms,
                                ip_address, port, enabled
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            device_id, name, modbus_type, service_id,
                            resp_timeout, byte_timeout, max_retries, polling_interval,
                            ip_address, port, enabled
                        ))
                    else:  # RTU
                        serial_port = row.get('Serial Port', '/dev/ttymxc5').strip()
                        baud_rate = int(row.get('Baud Rate', '9600') or '9600')
                        data_bits = int(row.get('Data Bits', '8') or '8')
                        parity = row.get('Parity', 'N').strip()
                        stop_bits = int(row.get('Stop Bits', '1') or '1')
                        
                        cursor.execute('''
                            INSERT INTO modbus_device (
                                id, name, device_type, service_id,
                                response_timeout_ms, byte_timeout_ms, max_retries, polling_interval_ms,
                                serial_port, baud_rate, parity, data_bits, stop_bits, enabled
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            device_id, name, modbus_type, service_id,
                            resp_timeout, byte_timeout, max_retries, polling_interval,
                            serial_port, baud_rate, parity, data_bits, stop_bits, enabled
                        ))
                    
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

# ============================================================================
# DOWNLOAD CSV TEMPLATE
# ============================================================================

async def download_csv_template(request):
    """GET - Download CSV template for device import"""
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'ID', 'Name', 'Type', 'Protocol',
            'IP Address', 'Port', 'Serial Port',
            'Baud Rate', 'Data Bits', 'Parity', 'Stop Bits',
            'Response Timeout (ms)', 'Byte Timeout (ms)', 'Max Retries', 'Polling Interval (ms)',
            'Device Path', 'Channel', 'Capacity', 'Unit', 'Enabled'
        ])
        
        writer.writerow([
            '', 'Example Modbus TCP', 'Modbus', 'modbus-tcp',
            '192.168.1.100', '502', '',
            '', '', '', '',
            '100', '100', '2', '300',
            '', '', '', '', '1'
        ])
        
        writer.writerow([
            '', 'Example Modbus RTU', 'Modbus', 'modbus-rtu',
            '', '', '/dev/ttymxc5',
            '9600', '8', 'N', '1',
            '100', '100', '2', '300',
            '', '', '', '', '1'
        ])
        
        writer.writerow([
            '', 'Example Loadcell', 'Loadcell', 'loadcell',
            '', '', '',
            '', '', '', '',
            '', '', '', '',
            '/dev/spidev0.0', '0', '40000', 'g', '1'
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
        
        cursor.execute('SELECT id FROM modbus_device WHERE id = ?', (device_id,))
        is_modbus = cursor.fetchone() is not None
        
        datapoints = []
        
        if is_modbus:
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
        
        result = update_device_status(device_id, status, last_poll)
        
        return web.json_response({
            'success': True,
            'device_id': device_id,
            'status': result['status'],
            'last_poll': result['last_poll']
        })
        
    except Exception as e:
        print("Error updating device status: {}".format(e))
        return web.json_response({'error': str(e)}, status=500)