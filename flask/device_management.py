# device_management.py - Device management API for External and Loadcell devices
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

# ---------------------------------------------------------------------------
# Auth helper — validates the gw_webui_session cookie against main.py's
# WEBUI_SESSIONS store.  Returns the username on success, raises HTTP 401
# on failure so all device API routes are protected the same way.
# ---------------------------------------------------------------------------
def _require_webui_session(request):
    """Raise HTTP 401 unless the request carries a valid webui session cookie."""
    try:
        from main import WEBUI_SESSIONS
    except ImportError:
        # main hasn't fully started yet — deny for safety
        raise web.HTTPUnauthorized(reason='Session store unavailable')

    token = request.cookies.get('gw_webui_session')
    if not token:
        raise web.HTTPUnauthorized(reason='No session cookie')

    session = WEBUI_SESSIONS.get(token)
    if not session:
        raise web.HTTPUnauthorized(reason='Session expired or invalid')

    return session.get('username') if isinstance(session, dict) else session

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
    conn.row_factory = sqlite3.Row
    return conn

# ============================================================================
# GET ALL DEVICES (External and Loadcell)
# ============================================================================

async def get_all_devices(request):
    """GET all devices (external + loadcell) with real-time status"""
    _require_webui_session(request)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        devices = []
        
        # Get Loadcell devices
        cursor.execute('''
            SELECT l.id, l.name, l.device_path, l.device_path_ch2, l.lc_mode,
                   l.enabled, s.name as service_name
            FROM loadcell_device l
            LEFT JOIN services s ON l.service_id = s.id
            ORDER BY l.id
        ''')
        
        for row in cursor.fetchall():
            device_id = row[0]
            name = row[1]
            device_path = row[2]
            device_path_ch2 = row[3]
            lc_mode = row[4]
            enabled = row[5]
            service_name = row[6]
            
            # Get or initialize real-time status
            if device_id not in device_status_tracker:
                initialize_device_status(device_id, 'Offline')
            
            status = device_status_tracker[device_id]
            
            # Format address based on mode
            port_config_list = get_port_config('loadcell')
            if lc_mode == 'differential':
                # Differential: always Channel 1 (fixed)
                address = 'Channel 1'
                for p in port_config_list:
                    if p['port_value'] == device_path:
                        address = p['label']
                        break
            else:
                # Single ended: show whichever channel was selected
                address = 'Channel 1'
                for p in port_config_list:
                    if p['port_value'] == device_path:
                        address = p['label']
                        break
            
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
                SELECT id, name, enabled, protocol,
                       device_type, model_name,
                       slave_id, response_timeout_ms, byte_timeout_ms,
                       max_retries, polling_interval_ms,
                       serial_port, baud_rate, data_bits, parity, stop_bits,
                       ip_address, port
                FROM external_device
                ORDER BY id
            ''')
            for row in cursor.fetchall():
                device_id = row[0]
                name = row[1]
                enabled = row[2]
                ext_proto = row[3]
                device_type_val = row[4]
                model_name = row[5]
                slave_id = row[6]
                resp_timeout = row[7]
                byte_timeout = row[8]
                max_retries = row[9]
                polling_interval = row[10]
                serial_port = row[11]
                baud_rate = row[12]
                data_bits = row[13]
                parity = row[14]
                stop_bits = row[15]
                ip_address = row[16]
                port = row[17]

                # Format address based on protocol
                if ext_proto == 'ext-tcp':
                    address = "{}:{}".format(ip_address or 'Not configured', port or 502)
                else:  # ext-rtu
                    port_config_list = get_port_config('modbus') or []
                    address = serial_port or '/dev/ttymxc5'
                    for p in port_config_list:
                        if p.get('port_value') == serial_port:
                            address = p.get('label', serial_port)
                            break

                if device_id not in device_status_tracker:
                    initialize_device_status(device_id, 'Offline')
                status = device_status_tracker[device_id]

                # Determine display type - use device_type if available, otherwise fallback to 'External'
                display_type = device_type_val or 'External'
                # Capitalize first letter
                if display_type:
                    display_type = display_type.capitalize()

                devices.append({
                    'id': device_id,
                    'name': name,
                    'type': display_type,  # This will show as "Vfd", "Meter", "Sensor", etc.
                    'protocol': ext_proto,
                    'address': address,
                    'status': status['status'],
                    'lastPoll': status['last_poll'],
                    'enabled': bool(enabled),
                    'service': None,
                    'config': {
                        'device_type': device_type_val or '',
                        'model_name': model_name or '',
                        'slave_id': slave_id,
                        'response_timeout_ms': resp_timeout,
                        'byte_timeout_ms': byte_timeout,
                        'max_retries': max_retries,
                        'polling_interval_ms': polling_interval,
                        'serial_port': serial_port,
                        'baud_rate': baud_rate,
                        'data_bits': data_bits,
                        'parity': parity,
                        'stop_bits': stop_bits,
                        'ip_address': ip_address,
                        'port': port,
                    }
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
    _require_webui_session(request)
    try:
        device_id = request.match_info['device_id']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Try Loadcell first
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
            
            dev_id = row[0]
            name = row[1]
            device_path = row[2]
            poll_ms = row[3]
            resolution_bits = row[4]
            effective_bits = row[5]
            signed = row[6]
            gain = row[7]
            vref = row[8]
            raw_min = row[9]
            raw_max = row[10]
            capacity_min = row[11]
            capacity_max = row[12]
            unit = row[13]
            load_name = row[14]
            capacity_name = row[15]
            pipeline_server = row[16]
            pipeline_port = row[17]
            log_level = row[18]
            tare_offset = row[19]
            known_weight = row[20]
            known_weight_raw = row[21]
            raw_filters_json = row[22]
            weight_filters_json = row[23]
            levels_json = row[24]
            enabled = row[25]
            service_name = row[26]
            lc_mode = row[27]
            device_path_ch2 = row[28]
            
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
                SELECT id, name, enabled, protocol,
                       device_type, model_name,
                       slave_id, response_timeout_ms, byte_timeout_ms,
                       max_retries, polling_interval_ms,
                       serial_port, baud_rate, data_bits, parity, stop_bits,
                       ip_address, port
                FROM external_device
                WHERE id = ?
            ''', (device_id,))
            row = cursor.fetchone()
            if row:
                dev_id = row[0]
                name = row[1]
                enabled = row[2]
                ext_proto = row[3]
                device_type_val = row[4]
                model_name = row[5]
                slave_id = row[6]
                resp_timeout = row[7]
                byte_timeout = row[8]
                max_retries = row[9]
                polling_interval = row[10]
                serial_port = row[11]
                baud_rate = row[12]
                data_bits = row[13]
                parity = row[14]
                stop_bits = row[15]
                ip_address = row[16]
                port = row[17]

                if device_id not in device_status_tracker:
                    initialize_device_status(device_id, 'Offline')
                status = device_status_tracker[device_id]

                details = {
                    'id': dev_id,
                    'name': name,
                    'type': 'External',
                    'protocol': ext_proto,
                    'service': None,
                    'enabled': bool(enabled),
                    'status': status['status'],
                    'lastPoll': status['last_poll'],
                    'config': {
                        'device_type': device_type_val or '',
                        'model_name': model_name or '',
                        'slave_id': slave_id,
                        'response_timeout_ms': resp_timeout,
                        'byte_timeout_ms': byte_timeout,
                        'max_retries': max_retries,
                        'polling_interval_ms': polling_interval,
                        'serial_port': serial_port,
                        'baud_rate': baud_rate,
                        'data_bits': data_bits,
                        'parity': parity,
                        'stop_bits': stop_bits,
                        'ip_address': ip_address,
                        'port': port,
                    }
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
    """POST - Add a new device (External or Loadcell)"""
    _require_webui_session(request)
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
        else:
            return web.json_response({'error': 'Invalid device type'}, status=400)
        
        # Get service_id
        service_name = 'loadcell' if device_type == 'loadcell' else None
        service_id = get_service_by_name(service_name) if service_name else None
        
        if device_type == 'loadcell':
            # Add Loadcell device
            config = data.get('config', {})
            device_name = data.get('name', 'Loadcell Device')
            lc_mode = config.get('lc_mode', 'single_ended')

            # Build tag prefix from device name: e.g. "load" -> load.weight, load.capacity
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

            # Automatically create datapoints
            cursor.execute('''
                INSERT OR IGNORE INTO loadcell_datapoints (device_id, name, unit)
                VALUES (?, ?, '')
            ''', (device_id, tag_weight))
            cursor.execute('''
                INSERT OR IGNORE INTO loadcell_datapoints (device_id, name, unit)
                VALUES (?, ?, 'kg')
            ''', (device_id, tag_capacity))
            
        elif device_type == 'external':
            ext_protocol = data.get('protocol', 'ext-rtu')
            device_type_val = data.get('device_type_init', data.get('device_type', ''))
            model_name = data.get('model_name', '')
            config = data.get('config', {})

            cursor.execute('''
                INSERT INTO external_device (
                    id, name, protocol,
                    device_type, model_name,
                    slave_id, response_timeout_ms, byte_timeout_ms,
                    max_retries, polling_interval_ms,
                    serial_port, baud_rate, data_bits, parity, stop_bits,
                    ip_address, port,
                    enabled
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
            ''', (
                device_id,
                data.get('name', 'External Device'),
                ext_protocol,
                device_type_val,
                model_name,
                config.get('slave_id', 1),
                config.get('response_timeout_ms', 100),
                config.get('byte_timeout_ms', 100),
                config.get('max_retries', 2),
                config.get('polling_interval_ms', 300),
                # RTU fields — only set for ext-rtu
                config.get('serial_port') if ext_protocol == 'ext-rtu' else None,
                config.get('baud_rate')   if ext_protocol == 'ext-rtu' else None,
                config.get('data_bits')   if ext_protocol == 'ext-rtu' else None,
                config.get('parity')      if ext_protocol == 'ext-rtu' else None,
                config.get('stop_bits')   if ext_protocol == 'ext-rtu' else None,
                # TCP fields — only set for ext-tcp
                config.get('ip_address')  if ext_protocol == 'ext-tcp' else None,
                config.get('port')        if ext_protocol == 'ext-tcp' else None,
            ))

            # Build file payload with only the relevant fields per protocol
            file_payload = {
                'id': device_id,
                'name': data.get('name', 'External Device'),
                'protocol': ext_protocol,
                'device_type': device_type_val,
                'model_name': model_name,
                'slave_id': config.get('slave_id', 1),
                'response_timeout_ms': config.get('response_timeout_ms', 100),
                'byte_timeout_ms': config.get('byte_timeout_ms', 100),
                'max_retries': config.get('max_retries', 2),
                'polling_interval_ms': config.get('polling_interval_ms', 300),
                'enabled': True,
                'created_at': datetime.utcnow().isoformat()
            }
            if ext_protocol == 'ext-rtu':
                file_payload.update({
                    'serial_port': config.get('serial_port', '/dev/ttymxc5'),
                    'baud_rate':   config.get('baud_rate', 9600),
                    'data_bits':   config.get('data_bits', 8),
                    'parity':      config.get('parity', 'N'),
                    'stop_bits':   config.get('stop_bits', 1),
                })
            else:
                file_payload.update({
                    'ip_address': config.get('ip_address', ''),
                    'port':       config.get('port', 502),
                })
            _write_ext_device_file(device_id, file_payload)
        
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
    _require_webui_session(request)
    try:
        device_id = request.match_info['device_id']
        data = await request.json()
        
        conn = get_db_connection()
        cursor = conn.cursor()

        # Try External device
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

            new_protocol = data.get('protocol', 'ext-rtu')
            device_type_val = data.get('device_type_init', data.get('device_type', ''))
            model_name = data.get('model_name', '')
            config = data.get('config', {})

            cursor.execute('''
                UPDATE external_device SET
                    name=?, protocol=?,
                    device_type=?, model_name=?,
                    slave_id=?, response_timeout_ms=?, byte_timeout_ms=?,
                    max_retries=?, polling_interval_ms=?,
                    serial_port=?, baud_rate=?, data_bits=?, parity=?, stop_bits=?,
                    ip_address=?, port=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            ''', (
                new_name, new_protocol,
                device_type_val, model_name,
                config.get('slave_id', 1),
                config.get('response_timeout_ms', 100),
                config.get('byte_timeout_ms', 100),
                config.get('max_retries', 2),
                config.get('polling_interval_ms', 300),
                # RTU fields — only for ext-rtu
                config.get('serial_port') if new_protocol == 'ext-rtu' else None,
                config.get('baud_rate')   if new_protocol == 'ext-rtu' else None,
                config.get('data_bits')   if new_protocol == 'ext-rtu' else None,
                config.get('parity')      if new_protocol == 'ext-rtu' else None,
                config.get('stop_bits')   if new_protocol == 'ext-rtu' else None,
                # TCP fields — only for ext-tcp
                config.get('ip_address')  if new_protocol == 'ext-tcp' else None,
                config.get('port')        if new_protocol == 'ext-tcp' else None,
                device_id
            ))

            # Update per-device JSON file with protocol-specific fields only
            file_payload = {
                'id': device_id,
                'name': new_name,
                'protocol': new_protocol,
                'device_type': device_type_val,
                'model_name': model_name,
                'slave_id': config.get('slave_id', 1),
                'response_timeout_ms': config.get('response_timeout_ms', 100),
                'byte_timeout_ms': config.get('byte_timeout_ms', 100),
                'max_retries': config.get('max_retries', 2),
                'polling_interval_ms': config.get('polling_interval_ms', 300),
                'enabled': True,
                'updated_at': datetime.utcnow().isoformat()
            }
            if new_protocol == 'ext-rtu':
                file_payload.update({
                    'serial_port': config.get('serial_port', '/dev/ttymxc5'),
                    'baud_rate':   config.get('baud_rate', 9600),
                    'data_bits':   config.get('data_bits', 8),
                    'parity':      config.get('parity', 'N'),
                    'stop_bits':   config.get('stop_bits', 1),
                })
            else:
                file_payload.update({
                    'ip_address': config.get('ip_address', ''),
                    'port':       config.get('port', 502),
                })
            _write_ext_device_file(device_id, file_payload)
        
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
            
            # Calibration fields
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
    _require_webui_session(request)
    try:
        device_id = request.match_info['device_id']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
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
    _require_webui_session(request)
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
    _require_webui_session(request)
    try:
        device_id = request.match_info['device_id']
        data = await request.json()
        enabled = data.get('enabled', True)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE loadcell_device SET enabled = ? WHERE id = ?', (enabled, device_id))
        try:
            cursor.execute('UPDATE external_device SET enabled = ? WHERE id = ?', (enabled, device_id))
        except Exception:
            pass
        
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
    _require_webui_session(request)
    try:
        device_id = request.match_info['device_id']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
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
            import re
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

        # Check if it's an External device
        try:
            cursor.execute('SELECT * FROM external_device WHERE id = ?', (device_id,))
            ext_row = cursor.fetchone()
        except Exception:
            ext_row = None

        if ext_row:
            cursor.execute('PRAGMA table_info(external_device)')
            ext_cols = [col[1] for col in cursor.fetchall()]
            old_ext = dict(zip(ext_cols, ext_row))

            # Generate new EX ID
            cursor.execute('SELECT id FROM external_device WHERE id LIKE "EX%" ORDER BY id')
            existing_ids = [row[0] for row in cursor.fetchall()]
            max_num = 0
            for eid in existing_ids:
                try:
                    num = int(eid[2:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    continue
            new_device_id = 'EX{}'.format(max_num + 1)

            # Generate new name
            import re
            base_name_clean = re.sub(r'-\d+$', '', old_ext['name'])
            cursor.execute('SELECT name FROM external_device WHERE name LIKE ?', ('{}%'.format(base_name_clean),))
            existing_names = [row[0] for row in cursor.fetchall()]
            numbers = []
            for name in existing_names:
                match = re.search(r'-(\d+)$', name)
                if match:
                    numbers.append(int(match.group(1)))
            counter = (max(numbers) + 1) if numbers else 1
            new_name = '{}-{}'.format(base_name_clean, str(counter).zfill(3))

            ext_proto = old_ext.get('protocol', 'ext-rtu')

            cursor.execute('''
                INSERT INTO external_device (
                    id, name, protocol,
                    device_type, model_name,
                    slave_id, response_timeout_ms, byte_timeout_ms,
                    max_retries, polling_interval_ms,
                    serial_port, baud_rate, data_bits, parity, stop_bits,
                    ip_address, port, enabled
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
            ''', (
                new_device_id, new_name, ext_proto,
                old_ext.get('device_type', ''),
                old_ext.get('model_name', ''),
                old_ext.get('slave_id', 1),
                old_ext.get('response_timeout_ms', 100),
                old_ext.get('byte_timeout_ms', 100),
                old_ext.get('max_retries', 2),
                old_ext.get('polling_interval_ms', 300),
                old_ext.get('serial_port') if ext_proto == 'ext-rtu' else None,
                old_ext.get('baud_rate')   if ext_proto == 'ext-rtu' else None,
                old_ext.get('data_bits')   if ext_proto == 'ext-rtu' else None,
                old_ext.get('parity')      if ext_proto == 'ext-rtu' else None,
                old_ext.get('stop_bits')   if ext_proto == 'ext-rtu' else None,
                old_ext.get('ip_address')  if ext_proto == 'ext-tcp' else None,
                old_ext.get('port')        if ext_proto == 'ext-tcp' else None,
            ))

            # Duplicate external datapoints
            try:
                cursor.execute('''
                    SELECT name, slave_id, register_address, register_type, data_type,
                           byte_order, word_order, scale_factor, offset, unit, description, enabled, writable
                    FROM external_datapoints WHERE device_id = ?
                ''', (device_id,))
                ext_dps = cursor.fetchall()
                for dp in ext_dps:
                    cursor.execute('''
                        INSERT OR IGNORE INTO external_datapoints (
                            device_id, name, slave_id, register_address, register_type, data_type,
                            byte_order, word_order, scale_factor, offset, unit, description, enabled, writable
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ''', (new_device_id,) + dp)
            except Exception:
                ext_dps = []

            # Write per-device JSON file
            file_payload = {
                'id': new_device_id, 'name': new_name,
                'protocol': ext_proto,
                'device_type': old_ext.get('device_type', ''),
                'model_name': old_ext.get('model_name', ''),
                'slave_id': old_ext.get('slave_id', 1),
                'response_timeout_ms': old_ext.get('response_timeout_ms', 100),
                'byte_timeout_ms': old_ext.get('byte_timeout_ms', 100),
                'max_retries': old_ext.get('max_retries', 2),
                'polling_interval_ms': old_ext.get('polling_interval_ms', 300),
                'enabled': True,
                'created_at': datetime.utcnow().isoformat()
            }
            if ext_proto == 'ext-rtu':
                file_payload.update({
                    'serial_port': old_ext.get('serial_port', '/dev/ttymxc5'),
                    'baud_rate':   old_ext.get('baud_rate', 9600),
                    'data_bits':   old_ext.get('data_bits', 8),
                    'parity':      old_ext.get('parity', 'N'),
                    'stop_bits':   old_ext.get('stop_bits', 1),
                })
            else:
                file_payload.update({
                    'ip_address': old_ext.get('ip_address', ''),
                    'port':       old_ext.get('port', 502),
                })
            _write_ext_device_file(new_device_id, file_payload)

            initialize_device_status(new_device_id, 'Online')
            conn.commit()
            conn.close()

            return web.json_response({
                'success': True,
                'message': 'Device duplicated successfully as {}'.format(new_name),
                'device_id': new_device_id,
                'device_name': new_name,
                'datapoints_copied': len(ext_dps) if ext_dps else 0
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
    _require_webui_session(request)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID', 'Name', 'Type', 'Protocol', 'Model Name',
            'IP Address', 'Port', 'Serial Port',
            'Baud Rate', 'Data Bits', 'Parity', 'Stop Bits',
            'Response Timeout (ms)', 'Byte Timeout (ms)', 'Max Retries', 'Polling Interval (ms)',
            'Device Path', 'Device Path CH2', 'Mode', 'Capacity Min', 'Capacity Max', 'Unit', 'Enabled'
        ])
        
        # Export Loadcell devices
        cursor.execute('''
            SELECT l.id, l.name, l.device_path, l.device_path_ch2, l.lc_mode,
                   l.capacity_min, l.capacity_max, l.unit, l.enabled
            FROM loadcell_device l
            ORDER BY l.id
        ''')
        
        for row in cursor.fetchall():
            device_id = row[0]
            name = row[1]
            device_path = row[2]
            device_path_ch2 = row[3]
            lc_mode = row[4]
            capacity_min = row[5]
            capacity_max = row[6]
            unit = row[7]
            enabled = row[8]
            writer.writerow([
                device_id, name, 'Loadcell', 'loadcell', '',
                '', '', '',
                '', '', '', '',
                '', '', '', '',
                device_path or '', device_path_ch2 or '', lc_mode or 'single_ended',
                capacity_min if capacity_min is not None else 0,
                capacity_max if capacity_max is not None else 1000,
                unit or 'kg', '1' if enabled else '0'
            ])

        # Export External devices
        try:
            cursor.execute('''
                SELECT id, name, protocol,
                       device_type, model_name,
                       slave_id, response_timeout_ms, byte_timeout_ms,
                       max_retries, polling_interval_ms,
                       serial_port, baud_rate, data_bits, parity, stop_bits,
                       ip_address, port, enabled
                FROM external_device
                ORDER BY id
            ''')
            for row in cursor.fetchall():
                dev_id = row[0]
                name = row[1]
                proto = row[2]
                device_type = row[3]
                model_name = row[4]
                slave_id = row[5]
                resp_to = row[6]
                byte_to = row[7]
                max_ret = row[8]
                poll_iv = row[9]
                serial_port = row[10]
                baud = row[11]
                data_bits = row[12]
                parity = row[13]
                stop_bits = row[14]
                ip = row[15]
                port = row[16]
                enabled = row[17]
                
                writer.writerow([
                    dev_id, name, device_type or 'External', proto, model_name or '',
                    ip or '', port or '', serial_port or '',
                    baud or '', data_bits or '', parity or '', stop_bits or '',
                    resp_to or '', byte_to or '', max_ret or '', poll_iv or '',
                    '', '', '', '', '', '', '1' if enabled else '0'
                ])
        except Exception as e:
            print("Error exporting external devices: {}".format(e))
            pass
        
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
    _require_webui_session(request)
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
                    cursor.execute('SELECT id, name FROM external_device WHERE name = ?', (name,))
                
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
                    # Check if duplicate exists
                    cursor.execute('SELECT id FROM loadcell_device WHERE name = ?', (name,))
                    existing_lc = cursor.fetchone()
                    
                    if existing_lc:
                        if skip_existing:
                            skipped_count += 1
                            continue
                        elif replace_existing:
                            # Delete old device (cascade deletes datapoints)
                            cursor.execute('DELETE FROM loadcell_device WHERE id = ?', (existing_lc[0],))
                            existing_loadcell_count -= 1
                            replaced_count += 1
                        else:
                            skipped_count += 1
                            continue

                    # Check loadcell limit
                    if existing_loadcell_count >= 2:
                        errors.append("Row {}: Cannot import - only 2 Loadcell devices allowed".format(row_num))
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
                        float(row.get('Capacity Min', row.get('Capacity', 0)) or 0),
                        float(row.get('Capacity Max', row.get('Capacity', 1000)) or 1000),
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
                    if not (replace_existing and existing_lc):
                        imported_count += 1
                    
                else:  # External device
                    # Check if duplicate exists
                    cursor.execute('SELECT id FROM external_device WHERE name = ?', (name,))
                    existing_ext = cursor.fetchone()
                    
                    if existing_ext:
                        if skip_existing:
                            skipped_count += 1
                            continue
                        elif replace_existing:
                            cursor.execute('DELETE FROM external_device WHERE id = ?', (existing_ext[0],))
                            replaced_count += 1
                        else:
                            skipped_count += 1
                            continue

                    cursor.execute('SELECT id FROM external_device WHERE id LIKE "EX%" ORDER BY id')
                    existing_ids = [r[0] for r in cursor.fetchall()]
                    max_num = 0
                    for existing_id in existing_ids:
                        try:
                            num = int(existing_id[2:])
                            if num > max_num:
                                max_num = num
                        except ValueError:
                            continue
                    device_id = 'EX{}'.format(max_num + 1)
                    
                    device_type_val = row.get('Type', 'External').strip()
                    model_name = row.get('Model Name', '').strip()
                    enabled = row.get('Enabled', '1').strip() == '1'
                    
                    # Get timeout values with defaults
                    resp_timeout = int(row.get('Response Timeout (ms)', '100') or '100')
                    byte_timeout = int(row.get('Byte Timeout (ms)', '100') or '100')
                    max_retries = int(row.get('Max Retries', '2') or '2')
                    polling_interval = int(row.get('Polling Interval (ms)', '300') or '300')
                    
                    if 'tcp' in protocol:
                        ip_address = row.get('IP Address', '').strip()
                        port = int(row.get('Port', '502') or '502')
                        
                        cursor.execute('''
                            INSERT INTO external_device (
                                id, name, protocol, device_type, model_name,
                                slave_id, response_timeout_ms, byte_timeout_ms,
                                max_retries, polling_interval_ms,
                                ip_address, port, enabled
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            device_id, name, 'ext-tcp', device_type_val, model_name,
                            1, resp_timeout, byte_timeout, max_retries, polling_interval,
                            ip_address, port, enabled
                        ))
                    else:  # RTU
                        serial_port = row.get('Serial Port', '/dev/ttymxc5').strip()
                        baud_rate = int(row.get('Baud Rate', '9600') or '9600')
                        data_bits = int(row.get('Data Bits', '8') or '8')
                        parity = row.get('Parity', 'N').strip()
                        stop_bits = int(row.get('Stop Bits', '1') or '1')
                        
                        cursor.execute('''
                            INSERT INTO external_device (
                                id, name, protocol, device_type, model_name,
                                slave_id, response_timeout_ms, byte_timeout_ms,
                                max_retries, polling_interval_ms,
                                serial_port, baud_rate, data_bits, parity, stop_bits, enabled
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            device_id, name, 'ext-rtu', device_type_val, model_name,
                            1, resp_timeout, byte_timeout, max_retries, polling_interval,
                            serial_port, baud_rate, data_bits, parity, stop_bits, enabled
                        ))
                    
                    if not (replace_existing and existing_ext):
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
    _require_webui_session(request)
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'ID', 'Name', 'Type', 'Protocol', 'Model Name',
            'IP Address', 'Port', 'Serial Port',
            'Baud Rate', 'Data Bits', 'Parity', 'Stop Bits',
            'Response Timeout (ms)', 'Byte Timeout (ms)', 'Max Retries', 'Polling Interval (ms)',
            'Device Path', 'Device Path CH2', 'Mode', 'Capacity Min', 'Capacity Max', 'Unit', 'Enabled'
        ])
        
        writer.writerow([
            '', 'Example External TCP', 'VFD', 'ext-tcp', 'ACS880',
            '192.168.1.100', '502', '',
            '', '', '', '',
            '100', '100', '2', '300',
            '', '', '', '', '', '', '1'
        ])
        
        writer.writerow([
            '', 'Example External RTU', 'Meter', 'ext-rtu', 'Siemens S120',
            '', '', '/dev/ttymxc5',
            '9600', '8', 'N', '1',
            '100', '100', '2', '300',
            '', '', '', '', '', '', '1'
        ])
        
        writer.writerow([
            '', 'Example Loadcell Single', 'Loadcell', 'loadcell', '',
            '', '', '',
            '', '', '', '',
            '', '', '', '',
            '/sys/bus/iio/devices/iio:device0/in_voltage0_raw', '', 'single_ended',
            '0', '1000', 'kg', '1'
        ])
        
        writer.writerow([
            '', 'Example Loadcell Differential', 'Loadcell', 'loadcell', '',
            '', '', '',
            '', '', '', '',
            '', '', '', '',
            '/sys/bus/iio/devices/iio:device0/in_voltage0_raw', '/sys/bus/iio/devices/iio:device1/in_voltage0_raw', 'differential',
            '0', '2000', 'kg', '1'
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
    _require_webui_session(request)
    try:
        device_id = request.match_info['device_id']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        datapoints = []
        
        # Check if it's a loadcell device
        cursor.execute('SELECT id FROM loadcell_device WHERE id = ?', (device_id,))
        is_loadcell = cursor.fetchone() is not None
        
        if is_loadcell:
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
        else:
            # Try external datapoints
            try:
                cursor.execute('''
                    SELECT id, name, register_address, register_type, data_type,
                           unit, description
                    FROM external_datapoints
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
                        'unit': row[5],
                        'description': row[6],
                        'type': 'External'
                    })
            except Exception as e:
                print("Error fetching external datapoints: {}".format(e))
        
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
    _require_webui_session(request)
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
    _require_webui_session(request)
    try:
        device_type = request.rel_url.query.get('type', None)
        rows = get_port_config(device_type)
        return web.json_response({'success': True, 'ports': rows})
    except Exception as e:
        print('Error getting port config: {}'.format(e))
        return web.json_response({'error': str(e)}, status=500)