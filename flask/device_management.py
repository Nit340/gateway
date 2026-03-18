# device_management.py - Device management API for Modbus and Loadcell
import asyncio
import json
import random
import uuid
import sqlite3
import io
import csv
import re
import os
from datetime import datetime
from aiohttp import web

from general import device_status_tracker
from database import DB_FILE, get_service_by_name, get_port_config
from general import initialize_device_status, remove_device_status, update_device_status

# ============================================================================
# EXTERNAL DEVICE FILE STORAGE
# Each external device is stored as an individual JSON file:
#   /mnt/data/external_devices/<device_id>.json
# ============================================================================

_EXT_DEVICE_DIR = os.environ.get('EXT_DEVICE_DIR', '/mnt/data/external_devices')

def _ensure_ext_dir():
    os.makedirs(_EXT_DEVICE_DIR, exist_ok=True)

def _ext_device_path(device_id):
    return os.path.join(_EXT_DEVICE_DIR, '{}.json'.format(device_id))

def _write_ext_device_file(device_id, payload):
    """Write a single external device JSON file."""
    _ensure_ext_dir()
    path = _ext_device_path(device_id)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

def _read_ext_device_file(device_id):
    """Read a single external device JSON file. Returns dict or None."""
    path = _ext_device_path(device_id)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print('[EXT] Failed to read {}: {}'.format(path, e))
        return None

def _delete_ext_device_file(device_id):
    """Delete the external device JSON file if it exists."""
    path = _ext_device_path(device_id)
    try:
        if os.path.isfile(path):
            os.remove(path)
    except Exception as e:
        print('[EXT] Failed to delete {}: {}'.format(path, e))

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
        
        # Get VFD devices
        cursor.execute('''
            SELECT m.id, m.name, m.protocol_type, m.device_type, m.ip_address, m.port, m.serial_port,
                   m.enabled, s.name as service_name
            FROM vfd_device m
            LEFT JOIN services s ON m.service_id = s.id
            ORDER BY m.id
        ''')
        
        for row in cursor.fetchall():
            device_id, name, protocol_type, device_type, ip, port, serial_port, enabled, service_name = row
            
            # Determine address display
            if protocol_type == 'tcp':
                address = "{}:{}".format(ip, port) if ip else "Not configured"
                protocol = "vfd-tcp"
            else:  # rtu
                address = serial_port or "Not configured"
                protocol = "vfd-rtu"
            
            # Get or initialize real-time status
            if device_id not in device_status_tracker:
                initialize_device_status(device_id, 'Offline')
            
            status = device_status_tracker[device_id]
            
            devices.append({
                'id': device_id,
                'name': name,
                'type': 'VFD',
                'device_type': device_type,     # always 'vfd'
                'protocol_type': protocol_type, # 'rtu' or 'tcp'
                'protocol': protocol,
                'address': address,
                'status': status['status'],
                'lastPoll': status['last_poll'],
                'enabled': bool(enabled),
                'service': service_name,
                'config': {
                    'serial_port': serial_port if protocol_type == 'rtu' else None,
                    'ip_address':  ip          if protocol_type == 'tcp' else None,
                    'port':        port        if protocol_type == 'tcp' else None,
                }
            })
        
        # Get Loadcell devices
        cursor.execute('''
            SELECT l.id, l.name, l.device_path, l.device_path_ch2, l.lc_mode,
                   l.enabled, s.name as service_name
            FROM loadcell_device l
            LEFT JOIN services s ON l.service_id = s.id
            ORDER BY l.id
        ''')
        
        for row in cursor.fetchall():
            device_id, name, device_path, device_path_ch2, lc_mode, enabled, service_name = row
            
            # Get or initialize real-time status
            if device_id not in device_status_tracker:
                initialize_device_status(device_id, 'Offline')
            
            status = device_status_tracker[device_id]
            
            # Format address based on mode
            if lc_mode == 'differential' and device_path_ch2:
                # Get channel labels from port config
                port_config_list = get_port_config('loadcell')
                ch1_label = 'Channel 1'
                ch2_label = 'Channel 2'
                
                for p in port_config_list:
                    if p['port_value'] == device_path:
                        ch1_label = p['label']
                    if p['port_value'] == device_path_ch2:
                        ch2_label = p['label']
                
                address = "{} & {}".format(ch1_label, ch2_label)
            else:
                # Single ended mode - get channel label
                port_config_list = get_port_config('loadcell')
                ch_label = 'Channel 1'
                for p in port_config_list:
                    if p['port_value'] == device_path:
                        ch_label = p['label']
                        break
                address = ch_label
            
            devices.append({
                'id': device_id,
                'name': name,
                'type': 'Loadcell',
                'protocol': 'loadcell',
                'address': address,
                'status': status['status'],
                'lastPoll': status['last_poll'],
                'enabled': bool(enabled),
                'service': service_name,
                'config': {
                    'device_path': device_path,
                    'device_path_ch2': device_path_ch2,
                    'lc_mode': lc_mode
                }
            })
        
        
        # Get External devices
        try:
            cursor.execute('''
                SELECT e.id, e.name, e.enabled, COALESCE(e.protocol,'external') as protocol,
                       e.config
                FROM external_device e
                ORDER BY e.id
            ''')
            for row in cursor.fetchall():
                device_id, name, enabled, ext_proto, config_json = row
                
                # Parse config
                import json as ext_json
                try:
                    config = ext_json.loads(config_json) if config_json else {}
                except:
                    config = {}
                
                # Format address based on protocol
                if ext_proto == 'ext-tcp':
                    ip = config.get('ip_address', 'Not configured')
                    port = config.get('port', '502')
                    address = "{}:{}".format(ip, port)
                elif ext_proto == 'ext-rtu':
                    serial_port = config.get('serial_port', '/dev/ttymxc5')
                    # Get port label from modbus port config
                    port_config_list = get_port_config('modbus')
                    address = serial_port
                    for p in port_config_list:
                        if p['port_value'] == serial_port:
                            address = p['label']
                            break
                else:
                    address = 'N/A'
                
                if device_id not in device_status_tracker:
                    initialize_device_status(device_id, 'Offline')
                status = device_status_tracker[device_id]
                
                devices.append({
                    'id': device_id,
                    'name': name,
                    'type': 'External',
                    'protocol': ext_proto,
                    'address': address,
                    'status': status['status'],
                    'lastPoll': status['last_poll'],
                    'enabled': bool(enabled),
                    'service': None,
                    'config': config
                })
        except Exception as e:
            print("Error fetching external devices: {}".format(e))
            pass
        
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
        
        # Try VFD first
        cursor.execute('''
            SELECT m.id, m.name, m.protocol_type, m.device_type,
                   m.response_timeout_ms, m.byte_timeout_ms, m.max_retries, m.polling_interval_ms,
                   m.ip_address, m.port,
                   m.serial_port, m.baud_rate, m.parity, m.data_bits, m.stop_bits,
                   m.enabled, s.name as service_name,
                   COALESCE(m.slave_id, 1) as slave_id
            FROM vfd_device m
            LEFT JOIN services s ON m.service_id = s.id
            WHERE m.id = ?
        ''', (device_id,))
        
        row = cursor.fetchone()
        
        if row:
            # It's a VFD device
            (dev_id, name, protocol_type, device_type, response_timeout_ms, byte_timeout_ms,
             max_retries, polling_interval_ms, ip_address, port, serial_port, 
             baud_rate, parity, data_bits, stop_bits, enabled, service_name, slave_id) = row
            
            # Get or initialize status
            if device_id not in device_status_tracker:
                initialize_device_status(device_id, 'Offline')
            
            status = device_status_tracker[device_id]
            
            details = {
                'id': dev_id,
                'name': name,
                'type': 'VFD',
                'device_type': device_type,       # always 'vfd'
                'protocol_type': protocol_type,   # 'rtu' or 'tcp'
                'service': service_name,
                'enabled': bool(enabled),
                'status': status['status'],
                'lastPoll': status['last_poll'],
                'config': {
                    'slave_id': slave_id,
                    'response_timeout_ms': response_timeout_ms,
                    'byte_timeout_ms': byte_timeout_ms,
                    'max_retries': max_retries,
                    'polling_interval_ms': polling_interval_ms
                }
            }
            
            if protocol_type == 'tcp':
                details['config']['ip_address'] = ip_address
                details['config']['port'] = port
                details['protocol'] = 'vfd-tcp'
                details['protocol_type'] = 'tcp'
            else:  # rtu
                details['config']['serial_port'] = serial_port
                details['config']['baud_rate'] = baud_rate
                details['config']['parity'] = parity
                details['config']['data_bits'] = data_bits
                details['config']['stop_bits'] = stop_bits
                details['protocol'] = 'vfd-rtu'
                details['protocol_type'] = 'rtu'
            
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
                   l.enabled, s.name as service_name,
                   COALESCE(l.lc_mode, 'single_ended') as lc_mode,
                   l.device_path_ch2
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
             enabled, service_name, lc_mode, device_path_ch2) = row
            
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
                    'lc_mode':        lc_mode,
                    'device_path':    device_path,
                    'device_path_ch2': device_path_ch2,
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
        
        
        # Try External device
        try:
            cursor.execute('''
                SELECT id, name, enabled, COALESCE(protocol,"external") as protocol, 
                       COALESCE(config,"{}") as config 
                FROM external_device 
                WHERE id = ?
            ''', (device_id,))
            row = cursor.fetchone()
            if row:
                dev_id, name, enabled, ext_proto, ext_config_json = row
                if device_id not in device_status_tracker:
                    initialize_device_status(device_id, 'Offline')
                status = device_status_tracker[device_id]
                import json as _extjson
                try:
                    ext_config = _extjson.loads(ext_config_json) if ext_config_json else {}
                except Exception:
                    ext_config = {}
                details = {
                    'id': dev_id, 
                    'name': name, 
                    'type': 'External', 
                    'protocol': ext_proto,
                    'service': None, 
                    'enabled': bool(enabled),
                    'status': status['status'], 
                    'lastPoll': status['last_poll'], 
                    'config': ext_config
                }
                conn.close()
                return web.json_response(details)
        except Exception as e:
            print("Error fetching external device: {}".format(e))
            pass

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

        # Enforce max-2 for loadcell
        if device_type == 'loadcell':
            cursor.execute('SELECT COUNT(*) FROM loadcell_device')
            if cursor.fetchone()[0] >= 2:
                conn.close()
                return web.json_response({
                    'success': False,
                    'error': 'Maximum 2 Loadcell devices allowed. Delete an existing one first.'
                }, status=400)

        # Generate device ID with unique prefix
        if device_type == 'loadcell':
            cursor.execute('SELECT id FROM loadcell_device WHERE id LIKE "LC%" ORDER BY id')
            existing_ids = [row[0] for row in cursor.fetchall()]
            max_num = 0
            for existing_id in existing_ids:
                try:
                    num = int(existing_id[2:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    continue
            device_id = 'LC{}'.format(max_num + 1)
        elif device_type == 'external':
            try:
                cursor.execute('SELECT id FROM external_device WHERE id LIKE "EX%" ORDER BY id')
                existing_ids = [row[0] for row in cursor.fetchall()]
            except Exception:
                existing_ids = []
            max_num = 0
            for existing_id in existing_ids:
                try:
                    num = int(existing_id[2:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    continue
            device_id = 'EX{}'.format(max_num + 1)
        else:  # modbus
            cursor.execute('SELECT id FROM vfd_device WHERE id LIKE "VF%" ORDER BY id')
            existing_ids = [row[0] for row in cursor.fetchall()]
            
            max_num = 0
            for existing_id in existing_ids:
                try:
                    num = int(existing_id[2:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    continue
            
            device_id = 'VF{}'.format(max_num + 1)
        
        # Get service_id
        service_name = 'loadcell' if device_type == 'loadcell' else 'modbus'
        service_id = get_service_by_name(service_name)
        
        if device_type == 'loadcell':
            # Add Loadcell device
            config = data.get('config', {})
            device_name = data.get('name', 'Loadcell Device')
            lc_mode = config.get('lc_mode', 'single_ended')

            # Build tag prefix from device name: e.g. "load" -> load.weight, load.capacity, load.unit
            tag_prefix   = device_name.strip().lower().replace(' ', '_')
            tag_weight   = 'loadcells.{}.weight'.format(tag_prefix)
            tag_capacity = 'loadcells.{}.capacity'.format(tag_prefix)

            # Set device_path_ch2 based on mode
            device_path_ch2 = config.get('device_path_ch2')
            if lc_mode == 'single_ended':
                device_path_ch2 = None

            cursor.execute('''
                INSERT INTO loadcell_device (
                    id, name, service_id, device_path, device_path_ch2, lc_mode,
                    poll_ms, resolution_bits, effective_bits, signed, gain, vref,
                    raw_min, raw_max,
                    capacity_min, capacity_max, unit,
                    load_name, capacity_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                device_id,
                device_name,
                service_id,
                config.get('device_path', '/sys/bus/iio/devices/iio:device0/in_voltage0_raw'),
                device_path_ch2,
                lc_mode,
                config.get('poll_ms', 10),
                24,  # resolution_bits fixed
                14,  # effective_bits fixed
                0,   # signed fixed
                1,   # gain fixed
                5,   # vref fixed
                0,   # raw_min fixed
                16383,  # raw_max fixed
                config.get('capacity_min', 0),
                config.get('capacity_max', 1000),
                config.get('unit', 'kg'),
                tag_weight,
                tag_capacity
            ))

            # Automatically create datapoints prefixed with device name:
            #   <name>.weight  (no unit - live reading)
            #   <name>.capacity (unit: kg - max capacity)
            #   <name>.unit    (no unit - unit label string)
            cursor.execute('''
                INSERT OR IGNORE INTO loadcell_datapoints (device_id, name, unit)
                VALUES (?, ?, '')
            ''', (device_id, tag_weight))
            cursor.execute('''
                INSERT OR IGNORE INTO loadcell_datapoints (device_id, name, unit)
                VALUES (?, ?, 'kg')
            ''', (device_id, tag_capacity))
            
        elif device_type == 'external':
            # Add External device — stores Modbus RTU or TCP config
            config = data.get('config', {})
            ext_protocol = data.get('protocol', 'ext-rtu')
            device_type_init = data.get('device_type_init', '')
            model_name = data.get('model_name', '')
            import json as _extjson
            # Store device_type_init and model_name inside config for persistence
            config['device_type_init'] = device_type_init
            config['model_name'] = model_name
            cursor.execute('''
                INSERT INTO external_device (id, name, enabled, protocol, config)
                VALUES (?, ?, 1, ?, ?)
            ''', (device_id, data.get('name', 'External Device'), ext_protocol, _extjson.dumps(config)))

            # Write per-device JSON file
            _write_ext_device_file(device_id, {
                'id': device_id,
                'name': data.get('name', 'External Device'),
                'protocol': ext_protocol,
                'enabled': True,
                'config': config,
                'created_at': datetime.utcnow().isoformat()
            })
            # external_datapoints are managed via tag mapping page (like vfd_datapoints)

        else:  # VFD (TCP or RTU)
            config = data.get('config', {})
            
            # Determine protocol_type: check explicit field first, then protocol string, then config
            explicit_pt = data.get('protocol_type', '').lower()
            protocol_lower = protocol.lower()
            if explicit_pt in ('tcp', 'rtu'):
                protocol_type = explicit_pt
            elif 'tcp' in protocol_lower:
                protocol_type = 'tcp'
            elif 'rtu' in protocol_lower:
                protocol_type = 'rtu'
            else:
                protocol_type = 'tcp' if config.get('ip_address') else 'rtu'
            
            print("Creating VFD device - Protocol: '{}', Type: '{}'".format(protocol, protocol_type))
            
            # Set default values matching your specified format
            response_timeout_ms = config.get('response_timeout_ms', 100)
            byte_timeout_ms = config.get('byte_timeout_ms', 100)
            max_retries = config.get('max_retries', 2)
            polling_interval_ms = config.get('polling_interval_ms', 300)
            
            cursor.execute('''
                INSERT INTO vfd_device (
                    id, name, protocol_type, device_type, service_id,
                    response_timeout_ms, byte_timeout_ms, max_retries, polling_interval_ms,
                    ip_address, port,
                    serial_port, baud_rate, parity, data_bits, stop_bits,
                    slave_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                device_id,
                data.get('name', 'VFD Device'),
                protocol_type,
                'vfd',
                service_id,
                response_timeout_ms,
                byte_timeout_ms,
                max_retries,
                polling_interval_ms,
                config.get('ip_address') if protocol_type == 'tcp' else None,
                config.get('port', 502) if protocol_type == 'tcp' else None,
                config.get('serial_port', '/dev/ttymxc5') if protocol_type == 'rtu' else None,
                config.get('baud_rate', 9600) if protocol_type == 'rtu' else None,
                config.get('parity', 'N') if protocol_type == 'rtu' else None,
                config.get('data_bits', 8) if protocol_type == 'rtu' else None,
                config.get('stop_bits', 1) if protocol_type == 'rtu' else None,
                config.get('slave_id', 1)
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
        
        # Check device type
        cursor.execute('SELECT id FROM vfd_device WHERE id = ?', (device_id,))
        is_modbus = cursor.fetchone() is not None

        try:
            cursor.execute('SELECT id FROM external_device WHERE id = ?', (device_id,))
            is_external = cursor.fetchone() is not None
        except Exception:
            is_external = False
        
        if is_external:
            new_name = data.get('name', '').strip()
            if not new_name:
                conn.close()
                return web.json_response({'success': False, 'error': 'Device name cannot be empty'}, status=400)
            import json as _extjson
            new_protocol = data.get('protocol', 'ext-rtu')
            new_config = data.get('config', {})
            # Preserve device_type_init and model_name if provided at top level
            if 'device_type_init' in data:
                new_config['device_type_init'] = data['device_type_init']
            if 'model_name' in data:
                new_config['model_name'] = data['model_name']
            cursor.execute(
                'UPDATE external_device SET name=?, protocol=?, config=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                (new_name, new_protocol, _extjson.dumps(new_config), device_id)
            )

            # Update per-device JSON file
            _write_ext_device_file(device_id, {
                'id': device_id,
                'name': new_name,
                'protocol': new_protocol,
                'enabled': True,
                'config': new_config,
                'updated_at': datetime.utcnow().isoformat()
            })

        elif is_modbus:
            # Update Modbus device
            config = data.get('config', {})
            protocol_type = data.get('protocol_type', data.get('device_type', 'rtu'))
            
            update_fields = ['name = ?', 'protocol_type = ?']
            values = [data.get('name'), protocol_type]
            
            # Common fields - using new column names
            if 'slave_id' in config:
                update_fields.append('slave_id = ?')
                values.append(config['slave_id'])
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
            if protocol_type == 'tcp':
                if 'ip_address' in config:
                    update_fields.append('ip_address = ?')
                    values.append(config['ip_address'])
                if 'port' in config:
                    update_fields.append('port = ?')
                    values.append(config['port'])
            
            # RTU specific
            if protocol_type == 'rtu':
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
                UPDATE vfd_device 
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
            for field in ('device_path', 'device_path_ch2', 'lc_mode',
                          'poll_ms',
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
        
        cursor.execute('DELETE FROM vfd_device WHERE id = ?', (device_id,))
        cursor.execute('DELETE FROM loadcell_device WHERE id = ?', (device_id,))
        try:
            cursor.execute('DELETE FROM external_datapoints WHERE device_id = ?', (device_id,))
        except Exception:
            pass
        try:
            cursor.execute('DELETE FROM external_device WHERE id = ?', (device_id,))
        except Exception:
            pass
        
        conn.commit()
        conn.close()
        
        # Remove per-device JSON file if it exists
        _delete_ext_device_file(device_id)
        
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
        
        cursor.execute('UPDATE vfd_device SET enabled = ? WHERE id = ?', (enabled, device_id))
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
        cursor.execute('SELECT * FROM vfd_device WHERE id = ?', (device_id,))
        modbus_row = cursor.fetchone()
        
        if modbus_row:
            # Get column names
            cursor.execute('PRAGMA table_info(vfd_device)')
            columns = [col[1] for col in cursor.fetchall()]
            
            old_device = dict(zip(columns, modbus_row))
            
            # Generate new device ID
            cursor.execute('SELECT id FROM vfd_device WHERE id LIKE "VF%" ORDER BY id')
            existing_ids = [row[0] for row in cursor.fetchall()]
            
            max_num = 0
            for existing_id in existing_ids:
                try:
                    num = int(existing_id[2:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    continue
            
            new_device_id = 'VF{}'.format(max_num + 1)
            
            # Generate new device name with -001 suffix
            base_name = old_device['name']
            base_name_clean = re.sub(r'-\d+$', '', base_name)
            
            cursor.execute('SELECT name FROM vfd_device WHERE name LIKE ?', ('{}%'.format(base_name_clean),))
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
                INSERT INTO vfd_device (
                    id, name, protocol_type, device_type, service_id,
                    response_timeout_ms, byte_timeout_ms, max_retries, polling_interval_ms,
                    ip_address, port, serial_port, baud_rate, parity,
                    data_bits, stop_bits, enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                new_device_id, new_name,
                old_device.get('protocol_type', 'rtu'),
                'vfd',
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
                FROM vfd_datapoints
                WHERE device_id = ?
            ''', (device_id,))
            
            datapoints = cursor.fetchall()
            for dp in datapoints:
                cursor.execute('''
                    INSERT INTO vfd_datapoints (
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
                # Enforce max-2 for loadcell duplicates
                cursor.execute('SELECT COUNT(*) FROM loadcell_device')
                if cursor.fetchone()[0] >= 2:
                    conn.close()
                    return web.json_response({
                        'success': False,
                        'message': 'Maximum 2 Loadcell devices allowed. Delete an existing one first.'
                    }, status=400)
                # Get column names
                cursor.execute('PRAGMA table_info(loadcell_device)')
                columns = [col[1] for col in cursor.fetchall()]
                old_device = dict(zip(columns, loadcell_row))
                
                # Generate new LC ID
                cursor.execute('SELECT id FROM loadcell_device WHERE id LIKE "LC%" ORDER BY id')
                existing_ids = [row[0] for row in cursor.fetchall()]
                max_num = 0
                for existing_id in existing_ids:
                    try:
                        num = int(existing_id[2:])
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        continue
                new_device_id = 'LC{}'.format(max_num + 1)
                
                # Generate new name
                base_name_clean = re.sub(r'-\d+$', '', old_device['name'])
                cursor.execute('SELECT name FROM loadcell_device WHERE name LIKE ?', ('{}%'.format(base_name_clean),))
                existing_names = [row[0] for row in cursor.fetchall()]
                numbers = []
                for name in existing_names:
                    match = re.search(r'-(\d+)$', name)
                    if match:
                        numbers.append(int(match.group(1)))
                counter = (max(numbers) + 1) if numbers else 1
                new_name = '{}-{}'.format(base_name_clean, str(counter).zfill(3))

                # Build tag prefix for the duplicated device
                new_tag_prefix   = new_name.strip().lower().replace(' ', '_')
                new_tag_weight   = 'loadcells.{}.weight'.format(new_tag_prefix)
                new_tag_capacity = 'loadcells.{}.capacity'.format(new_tag_prefix)

                cursor.execute('''
                    INSERT INTO loadcell_device (
                        id, name, service_id, device_path, device_path_ch2, lc_mode,
                        poll_ms, resolution_bits, effective_bits, signed, gain, vref,
                        raw_min, raw_max, capacity_min, capacity_max, unit,
                        load_name, capacity_name, enabled
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    new_device_id, new_name, old_device.get('service_id'),
                    old_device.get('device_path'),
                    old_device.get('device_path_ch2'),
                    old_device.get('lc_mode', 'single_ended'),
                    old_device.get('poll_ms'),
                    old_device.get('resolution_bits'), old_device.get('effective_bits'),
                    old_device.get('signed'), old_device.get('gain'), old_device.get('vref'),
                    old_device.get('raw_min'), old_device.get('raw_max'),
                    old_device.get('capacity_min'), old_device.get('capacity_max'),
                    old_device.get('unit'), new_tag_weight,
                    new_tag_capacity, old_device.get('enabled', 1)
                ))
                
                # Duplicate loadcell datapoints
                cursor.execute('SELECT name, unit FROM loadcell_datapoints WHERE device_id = ?', (device_id,))
                datapoints = cursor.fetchall()
                for dp in datapoints:
                    cursor.execute(
                        'INSERT OR IGNORE INTO loadcell_datapoints (device_id, name, unit) VALUES (?, ?, ?)',
                        (new_device_id, dp[0], dp[1])
                    )
                
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
            'Device Path', 'Device Path CH2', 'Mode', 'Capacity', 'Unit', 'Enabled'
        ])
        
        # Export VFD devices
        cursor.execute('''
            SELECT m.id, m.name, m.protocol_type,
                   m.ip_address, m.port, m.serial_port,
                   m.baud_rate, m.data_bits, m.parity, m.stop_bits,
                   m.response_timeout_ms, m.byte_timeout_ms, m.max_retries, m.polling_interval_ms,
                   m.enabled
            FROM vfd_device m
            ORDER BY m.id
        ''')
        
        for row in cursor.fetchall():
            (device_id, name, protocol_type, ip, port, serial,
             baud, data_bits, parity, stop_bits,
             resp_timeout, byte_timeout, max_retries, polling_interval,
             enabled) = row
            
            protocol = 'vfd-tcp' if protocol_type == 'tcp' else 'vfd-rtu'
            
            writer.writerow([
                device_id, name, 'VFD', protocol,
                ip or '', port or '', serial or '',
                baud or '', data_bits or '', parity or '', stop_bits or '',
                resp_timeout or '', byte_timeout or '', max_retries or '', polling_interval or '',
                '', '', '', '', '', '1' if enabled else '0'
            ])
        
        # Export Loadcell devices
        cursor.execute('''
            SELECT l.id, l.name, l.device_path, l.device_path_ch2, l.lc_mode,
                   l.capacity_max, l.unit, l.enabled
            FROM loadcell_device l
            ORDER BY l.id
        ''')
        
        for row in cursor.fetchall():
            device_id, name, device_path, device_path_ch2, lc_mode, capacity_max, unit, enabled = row
            writer.writerow([
                device_id, name, 'Loadcell', 'loadcell',
                '', '', '',
                '', '', '', '',
                '', '', '', '',
                device_path or '', device_path_ch2 or '', lc_mode or 'single_ended',
                capacity_max or 1000, unit or 'kg', '1' if enabled else '0'
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
                    cursor.execute('SELECT id, name FROM loadcell_device WHERE name = ?', (name,))
                else:
                    cursor.execute('SELECT id, name FROM vfd_device WHERE name = ?', (name,))
                
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

        # Pre-count existing loadcell devices for limit enforcement
        cursor.execute('SELECT COUNT(*) FROM loadcell_device')
        existing_loadcell_count = cursor.fetchone()[0]

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
                    # Check loadcell limit
                    if existing_loadcell_count >= 1:
                        errors.append("Row {}: Cannot import - only 1 Loadcell device allowed".format(row_num))
                        continue
                    
                    # Generate new LC ID
                    cursor.execute('SELECT id FROM loadcell_device WHERE id LIKE "LC%" ORDER BY id')
                    existing_ids = [r[0] for r in cursor.fetchall()]
                    max_num = 0
                    for existing_id in existing_ids:
                        try:
                            num = int(existing_id[2:])
                            if num > max_num:
                                max_num = num
                        except ValueError:
                            continue
                    device_id = 'LC{}'.format(max_num + 1)
                    
                    service_id = get_service_by_name('loadcell')
                    
                    # Build tag prefix
                    tag_prefix = name.strip().lower().replace(' ', '_')
                    tag_weight = 'loadcells.{}.weight'.format(tag_prefix)
                    tag_capacity = 'loadcells.{}.capacity'.format(tag_prefix)
                    
                    # Get mode and device paths
                    lc_mode = row.get('Mode', 'single_ended').strip()
                    device_path = row.get('Device Path', '/sys/bus/iio/devices/iio:device0/in_voltage0_raw')
                    device_path_ch2 = row.get('Device Path CH2') if lc_mode == 'differential' else None
                    
                    cursor.execute('''
                        INSERT INTO loadcell_device (
                            id, name, service_id, device_path, device_path_ch2, lc_mode,
                            poll_ms, resolution_bits, effective_bits, signed, gain, vref,
                            raw_min, raw_max, capacity_min, capacity_max, unit,
                            load_name, capacity_name, enabled
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        device_id, name, service_id,
                        device_path, device_path_ch2, lc_mode,
                        10, 24, 14, 0, 1, 5,
                        0, 16383,
                        float(row.get('Capacity', 1000) or 1000),
                        row.get('Unit', 'kg') or 'kg',
                        tag_weight, tag_capacity,
                        1 if row.get('Enabled', '1') == '1' else 0
                    ))
                    
                    # Create datapoints
                    cursor.execute('''
                        INSERT OR IGNORE INTO loadcell_datapoints (device_id, name, unit)
                        VALUES (?, ?, '')
                    ''', (device_id, tag_weight))
                    cursor.execute('''
                        INSERT OR IGNORE INTO loadcell_datapoints (device_id, name, unit)
                        VALUES (?, ?, 'kg')
                    ''', (device_id, tag_capacity))
                    
                    existing_loadcell_count += 1
                    imported_count += 1
                    
                else:  # VFD device
                    cursor.execute('SELECT id FROM vfd_device WHERE id LIKE "VF%" ORDER BY id')
                    existing_ids = [r[0] for r in cursor.fetchall()]
                    max_num = 0
                    for existing_id in existing_ids:
                        try:
                            num = int(existing_id[2:])
                            if num > max_num:
                                max_num = num
                        except ValueError:
                            continue
                    device_id = 'VF{}'.format(max_num + 1)
                    
                    service_id = get_service_by_name('modbus')
                    protocol_type = 'tcp' if 'tcp' in protocol else 'rtu'
                    enabled = row.get('Enabled', '1').strip() == '1'
                    
                    # Get timeout values with defaults
                    resp_timeout = int(row.get('Response Timeout (ms)', '100') or '100')
                    byte_timeout = int(row.get('Byte Timeout (ms)', '100') or '100')
                    max_retries = int(row.get('Max Retries', '2') or '2')
                    polling_interval = int(row.get('Polling Interval (ms)', '300') or '300')
                    
                    if protocol_type == 'tcp':
                        ip_address = row.get('IP Address', '').strip()
                        port = int(row.get('Port', '502') or '502')
                        
                        cursor.execute('''
                            INSERT INTO vfd_device (
                                id, name, protocol_type, device_type, service_id,
                                response_timeout_ms, byte_timeout_ms, max_retries, polling_interval_ms,
                                ip_address, port, enabled
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            device_id, name, protocol_type, 'vfd', service_id,
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
                            INSERT INTO vfd_device (
                                id, name, protocol_type, device_type, service_id,
                                response_timeout_ms, byte_timeout_ms, max_retries, polling_interval_ms,
                                serial_port, baud_rate, parity, data_bits, stop_bits, enabled
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            device_id, name, protocol_type, 'vfd', service_id,
                            resp_timeout, byte_timeout, max_retries, polling_interval,
                            serial_port, baud_rate, parity, data_bits, stop_bits, enabled
                        ))
                    
                    imported_count += 1
                
                initialize_device_status(device_id, 'Online' if enabled else 'Offline')
                
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
            'Device Path', 'Device Path CH2', 'Mode', 'Capacity', 'Unit', 'Enabled'
        ])
        
        writer.writerow([
            '', 'Example Modbus TCP', 'VFD', 'vfd-tcp',
            '192.168.1.100', '502', '',
            '', '', '', '',
            '100', '100', '2', '300',
            '', '', '', '', '', '1'
        ])
        
        writer.writerow([
            '', 'Example Modbus RTU', 'VFD', 'vfd-rtu',
            '', '', '/dev/ttymxc5',
            '9600', '8', 'N', '1',
            '100', '100', '2', '300',
            '', '', '', '', '', '1'
        ])
        
        writer.writerow([
            '', 'Example Loadcell Single', 'Loadcell', 'loadcell',
            '', '', '',
            '', '', '', '',
            '', '', '', '',
            '/sys/bus/iio/devices/iio:device0/in_voltage0_raw', '', 'single_ended',
            '1000', 'kg', '1'
        ])
        
        writer.writerow([
            '', 'Example Loadcell Differential', 'Loadcell', 'loadcell',
            '', '', '',
            '', '', '', '',
            '', '', '', '',
            '/sys/bus/iio/devices/iio:device0/in_voltage0_raw', '/sys/bus/iio/devices/iio:device1/in_voltage0_raw', 'differential',
            '2000', 'kg', '1'
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
        
        cursor.execute('SELECT id FROM vfd_device WHERE id = ?', (device_id,))
        is_modbus = cursor.fetchone() is not None
        
        datapoints = []
        
        if is_modbus:
            cursor.execute('''
                SELECT id, name, register_address, register_type, data_type,
                       byte_order, word_order, scale_factor, offset, unit, description
                FROM vfd_datapoints
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
                    'type': 'VFD'
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
# ============================================================================
# PORT / PATH CONFIGURATION
# ============================================================================

async def get_port_config_api(request):
    """GET /api/port-config  - return all port/path entries from port_config table.
    Optionally filter by ?type=modbus or ?type=loadcell
    """
    try:
        device_type = request.rel_url.query.get('type', None)
        rows = get_port_config(device_type)
        return web.json_response({'success': True, 'ports': rows})
    except Exception as e:
        print('Error getting port config: {}'.format(e))
        return web.json_response({'error': str(e)}, status=500)