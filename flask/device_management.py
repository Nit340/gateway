# device_management.py - Device management API for Modbus and Loadcell
import asyncio
import json
import random
import uuid
import sqlite3
from aiohttp import web

from models import device_status_tracker, device_websockets
from websocket_handler import broadcast_device_status
from database import DB_FILE, get_service_by_name

# ============================================================================
# GET ALL DEVICES (Both Modbus and Loadcell)
# ============================================================================

async def get_all_devices(request):
    """GET all devices (modbus + loadcell)"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        devices = []
        
        # Get Modbus devices
        cursor.execute('''
            SELECT m.id, m.name, m.device_type, m.ip_address, m.port, m.serial_port,
                   g.name as group_name, g.color, m.enabled, s.name as service_name
            FROM modbus_device m
            LEFT JOIN device_groups g ON m.group_id = g.id
            LEFT JOIN services s ON m.service_id = s.id
            ORDER BY CAST(m.id AS INTEGER)
        ''')
        
        for row in cursor.fetchall():
            device_id, name, device_type, ip, port, serial_port, group_name, color, enabled, service_name = row
            
            # Determine address display
            if device_type == 'tcp':
                address = f"{ip}:{port}" if ip else "Not configured"
                protocol = "modbus-tcp"
            else:  # rtu
                address = serial_port or "Not configured"
                protocol = "modbus-rtu"
            
            # Get real-time status
            status = device_status_tracker.get(device_id, {'status': 'Offline', 'last_poll': 'Never'})
            
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
            ORDER BY CAST(l.id AS INTEGER)
        ''')
        
        for row in cursor.fetchall():
            device_id, name, device_path, group_name, color, enabled, service_name = row
            
            # Get real-time status
            status = device_status_tracker.get(device_id, {'status': 'Offline', 'last_poll': 'Never'})
            
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
        print(f"Error getting devices: {e}")
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# GET DEVICE DETAILS
# ============================================================================

async def get_device_details(request):
    """GET device details by ID"""
    try:
        device_id = request.match_info['device_id']
        
        conn = sqlite3.connect(DB_FILE)
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
            
            status = device_status_tracker.get(device_id, {'status': 'Offline', 'last_poll': 'Never'})
            
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
                   l.unit, l.capacity, l.capacity_name,
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
            # It's a Loadcell device
            status = device_status_tracker.get(device_id, {'status': 'Offline', 'last_poll': 'Never'})
            
            details = {
                'id': row[0],
                'name': row[1],
                'type': 'Loadcell',
                'protocol': 'loadcell',
                'group': row[36] or 'None',
                'group_id': row[2],
                'service': row[37],
                'enabled': bool(row[35]),
                'status': status['status'],
                'lastPoll': status['last_poll'],
                'config': {
                    'device_path': row[3],
                    'channel': row[4],
                    'calibration': {
                        'tare_offset': row[5],
                        'known_weight': row[6],
                        'known_weight_raw': row[7],
                        'shift_bits': row[8],
                        'unit': row[9],
                        'capacity': row[10],
                        'capacity_name': row[11]
                    },
                    'service': {
                        'pipeline_server': row[12],
                        'pipeline_port': row[13],
                        'log_level': row[14],
                        'polling_interval_ms': row[15]
                    },
                    'filters': {
                        'lowpass_filter_enabled': bool(row[16]),
                        'filter_cutoff_frequency': row[17],
                        'filter_activation_delta_min': row[18],
                        'moving_avg_enabled': bool(row[19]),
                        'moving_avg_window': row[20],
                        'median_filter_enabled': bool(row[21]),
                        'median_filter_window': row[22],
                        'autotare_enabled': bool(row[23]),
                        'autotare_trigger_delta_grams': row[24],
                        'adaptive_deadband_enabled': bool(row[25]),
                        'adaptive_deadband_min': row[26],
                        'adaptive_deadband_max': row[27],
                        'adaptive_deadband_grow_rate': row[28],
                        'adaptive_deadband_shrink_rate': row[29],
                        'publish_step_grams': row[30],
                        'overload_threshold': row[31],
                        'overload_relay': row[32],
                        'overload_action': row[33],
                        'overload_cooldown_ms': row[34],
                        'confirm_count': row[35]
                    }
                }
            }
            
            conn.close()
            return web.json_response(details)
        
        conn.close()
        return web.json_response({'error': 'Device not found'}, status=404)
        
    except Exception as e:
        print(f"Error getting device details: {e}")
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
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Generate device ID
        if device_type == 'loadcell':
            cursor.execute('SELECT COUNT(*) FROM loadcell_device')
        else:  # modbus
            cursor.execute('SELECT COUNT(*) FROM modbus_device')
        
        count = cursor.fetchone()[0]
        device_id = str(count + 1)
        
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
                    capacity, capacity_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                device_id,
                data.get('name', 'Loadcell Device'),
                group_id,
                service_id,
                config.get('device_path', '/dev/spidev0.0'),
                config.get('channel', 0),
                config.get('capacity', 40000.0),
                config.get('capacity_name', 'capacity')
            ))
            
            # Automatically create 'load' and 'capacity' datapoints
            cursor.execute('''
                INSERT INTO loadcell_datapoints (device_id, name)
                VALUES (?, 'load'), (?, ?)
            ''', (device_id, device_id, config.get('capacity_name', 'capacity')))
            
        else:  # Modbus (TCP or RTU)
            config = data.get('config', {})
            
            # Determine device_type from protocol
            modbus_type = 'tcp' if 'tcp' in protocol else 'rtu'
            
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
        device_status_tracker[device_id] = {'status': 'Online', 'last_poll': 'Just now'}
        
        return web.json_response({
            'success': True,
            'message': 'Device added successfully',
            'device_id': device_id
        })
        
    except Exception as e:
        print(f"Error adding device: {e}")
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# UPDATE DEVICE
# ============================================================================

async def update_device(request):
    """PUT - Update device"""
    try:
        device_id = request.match_info['device_id']
        data = await request.json()
        
        conn = sqlite3.connect(DB_FILE)
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
            
            query = f'''
                UPDATE modbus_device 
                SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            '''
            
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
            
            query = f'''
                UPDATE loadcell_device 
                SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            '''
            
            cursor.execute(query, values)
        
        conn.commit()
        conn.close()
        
        return web.json_response({
            'success': True,
            'message': 'Device updated successfully'
        })
        
    except Exception as e:
        print(f"Error updating device: {e}")
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# DELETE DEVICE
# ============================================================================

async def delete_device(request):
    """DELETE - Delete device"""
    try:
        device_id = request.match_info['device_id']
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Try deleting from both tables (cascade will handle datapoints)
        cursor.execute('DELETE FROM modbus_device WHERE id = ?', (device_id,))
        cursor.execute('DELETE FROM loadcell_device WHERE id = ?', (device_id,))
        
        conn.commit()
        conn.close()
        
        # Remove from status tracker
        if device_id in device_status_tracker:
            del device_status_tracker[device_id]
        
        return web.json_response({
            'success': True,
            'message': 'Device deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting device: {e}")
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
            device_status_tracker[device_id] = {'status': 'Online', 'last_poll': 'Just now'}
            return web.json_response({
                'success': True,
                'message': 'Device connection successful'
            })
        else:
            device_status_tracker[device_id] = {'status': 'Offline', 'last_poll': 'Failed'}
            return web.json_response({
                'success': False,
                'message': 'Device connection failed'
            }, status=400)
            
    except Exception as e:
        print(f"Error testing device: {e}")
        return web.json_response({'error': str(e)}, status=500)

async def disable_device(request):
    """POST - Enable/Disable device"""
    try:
        device_id = request.match_info['device_id']
        data = await request.json()
        enabled = data.get('enabled', True)
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Update both tables
        cursor.execute('UPDATE modbus_device SET enabled = ? WHERE id = ?', (enabled, device_id))
        cursor.execute('UPDATE loadcell_device SET enabled = ? WHERE id = ?', (enabled, device_id))
        
        conn.commit()
        conn.close()
        
        return web.json_response({
            'success': True,
            'message': f"Device {'enabled' if enabled else 'disabled'} successfully"
        })
        
    except Exception as e:
        print(f"Error disabling device: {e}")
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
        print(f"Error getting groups: {e}")
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
        print(f"Error adding group: {e}")
        return web.json_response({'error': str(e)}, status=500)

async def assign_devices_to_group(request):
    """POST - Assign devices to group"""
    try:
        group_id = request.match_info['group_id']
        data = await request.json()
        device_ids = data.get('device_ids', [])
        
        conn = sqlite3.connect(DB_FILE)
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
        print(f"Error assigning devices to group: {e}")
        return web.json_response({'error': str(e)}, status=500)