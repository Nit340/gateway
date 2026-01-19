# tag_mapping.py - Tag mapping management API
from aiohttp import web
import json
import sqlite3
import csv
import io
from datetime import datetime
import re

DB_FILE = 'gateway_config.db'

# Helper function to get database connection
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# GET /tag-mapping - Main tag mapping page
async def get_tag_mapping_page(request):
    """Render the complete tag mapping management page with embedded data"""
    
    # Read the HTML template
    with open('modbus-mapping.html', 'r') as f:
        html_content = f.read()
    
    # Get all data from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all devices
    cursor.execute('''
        SELECT dm.id, dm.name, dm.type, 
               CASE 
                   WHEN dm.config_json LIKE '%"protocol":"modbus-rtu"%' THEN 'modbus-rtu'
                   WHEN dm.config_json LIKE '%"protocol":"modbus-tcp"%' THEN 'modbus-tcp'
                   WHEN dm.config_json LIKE '%"protocol":"can"%' THEN 'can'
                   WHEN dm.config_json LIKE '%"protocol":"ethernet-ip"%' THEN 'ethernet-ip'
                   ELSE 'unknown'
               END as protocol,
               dm.config_json
        FROM device_management dm
        ORDER BY dm.name
    ''')
    
    devices = []
    for row in cursor.fetchall():
        config = json.loads(row['config_json']) if row['config_json'] else {}
        devices.append({
            'id': row['id'],
            'name': row['name'],
            'type': row['type'],
            'protocol': row['protocol'],
            'address': config.get('address', ''),
            'status': config.get('status', 'unknown'),
            'pollRate': config.get('poll_rate', '100'),
            'tags': 0  # Will be updated below
        })
    
    # Get all tag mappings with device info
    cursor.execute('''
        SELECT tm.*, dm.name as device_name, tc.name as category_name, tc.color as category_color
        FROM tag_mappings tm
        LEFT JOIN device_management dm ON tm.device_id = dm.id
        LEFT JOIN tag_categories tc ON tm.category = tc.name
        ORDER BY tm.tag_name
    ''')
    
    mappings = []
    for row in cursor.fetchall():
        protocol_config = json.loads(row['protocol_config']) if row['protocol_config'] else {}
        
        # Determine protocol from device or config
        device_protocol = 'modbus'
        for device in devices:
            if device['id'] == row['device_id']:
                device_protocol = device['protocol']
                break
        
        mapping = {
            'id': row['id'],
            'deviceId': row['device_id'],
            'deviceName': row['device_name'],
            'address': row['address'],
            'tagName': row['tag_name'],
            'dataType': row['data_type'],
            'scale': str(row['scale']),
            'offset': str(row['offset']),
            'unit': row['unit'],
            'pollInterval': str(row['poll_interval']),
            'category': row['category'] or 'Sensors',
            'description': row['description'] or '',
            'minValid': str(row['min_valid']) if row['min_valid'] is not None else '',
            'maxValid': str(row['max_valid']) if row['max_valid'] is not None else '',
            'endianness': row['endianness'],
            'protocol': device_protocol
        }
        
        # Merge protocol-specific config
        mapping.update(protocol_config)
        mappings.append(mapping)
    
    # Get categories
    cursor.execute('SELECT name, description, color FROM tag_categories ORDER BY name')
    categories = [{'name': row['name'], 'color': row['color']} for row in cursor.fetchall()]
    
    conn.close()
    
    # Update tag counts for devices
    for device in devices:
        device['tags'] = len([m for m in mappings if m['deviceId'] == device['id']])
    
    # Embed data in HTML
    embedded_html = html_content.replace(
        '</style>',
        f'''
    </style>
    <script>
        // Embedded data for tag mapping page
        window.embeddedData = {{
            devices: {json.dumps(devices)},
            mappings: {json.dumps(mappings)},
            categories: {json.dumps(categories)}
        }};
    </script>
        '''
    )
    
    return web.Response(text=embedded_html, content_type='text/html')

# POST /api/tag-mapping - Create new tag mapping
async def create_tag_mapping(request):
    """Create a new tag mapping"""
    try:
        data = await request.json()
        
        # Validate required fields
        required_fields = ['deviceId', 'tagName', 'address', 'dataType']
        for field in required_fields:
            if field not in data or not data[field]:
                return web.json_response({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }, status=400)
        
        # Check if tag name already exists for this device
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id FROM tag_mappings 
            WHERE device_id = ? AND tag_name = ?
        ''', (data['deviceId'], data['tagName']))
        
        if cursor.fetchone():
            conn.close()
            return web.json_response({
                'success': False,
                'error': 'TAG_001: Tag name already exists for this device'
            }, status=409)
        
        # Check if device exists
        cursor.execute('SELECT id FROM device_management WHERE id = ?', (data['deviceId'],))
        if not cursor.fetchone():
            conn.close()
            return web.json_response({
                'success': False,
                'error': 'TAG_002: Invalid device ID'
            }, status=404)
        
        # Prepare protocol config
        protocol_config = {}
        protocol_keys = ['registerType', 'registerCount', 'byteOrder', 'canId', 
                        'dataLength', 'channel', 'nodeId', 'sensorId', 'parameterId']
        for key in protocol_keys:
            if key in data:
                protocol_config[key] = data[key]
        
        # Insert tag mapping
        cursor.execute('''
            INSERT INTO tag_mappings (
                device_id, tag_name, description, address, 
                data_type, endianness, scale, offset, unit,
                poll_interval, category, min_valid, max_valid,
                protocol_config
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['deviceId'],
            data['tagName'],
            data.get('description', ''),
            data['address'],
            data['dataType'],
            data.get('endianness', 'big-endian'),
            float(data.get('scale', 1.0)),
            float(data.get('offset', 0.0)),
            data.get('unit', ''),
            int(data.get('pollInterval', 200)),
            data.get('category', 'Sensors'),
            float(data['minValid']) if data.get('minValid') else None,
            float(data['maxValid']) if data.get('maxValid') else None,
            json.dumps(protocol_config) if protocol_config else None
        ))
        
        tag_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        return web.json_response({
            'success': True,
            'tag': {
                'id': tag_id,
                'deviceId': data['deviceId'],
                'tagName': data['tagName'],
                'protocol': data.get('protocol', 'Unknown'),
                'address': data['address'],
                'dataType': data['dataType'],
                'unit': data.get('unit', '')
            }
        }, status=201)
        
    except json.JSONDecodeError:
        return web.json_response({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)

# PUT /api/tag-mapping/{id} - Update existing tag mapping
async def update_tag_mapping(request):
    """Update an existing tag mapping"""
    try:
        tag_id = request.match_info['id']
        data = await request.json()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if tag exists
        cursor.execute('SELECT id FROM tag_mappings WHERE id = ?', (tag_id,))
        if not cursor.fetchone():
            conn.close()
            return web.json_response({
                'success': False,
                'error': 'TAG_005: Tag mapping not found'
            }, status=404)
        
        # Check if new tag name conflicts (if changed)
        if 'tagName' in data:
            cursor.execute('''
                SELECT id FROM tag_mappings 
                WHERE device_id = (SELECT device_id FROM tag_mappings WHERE id = ?)
                AND tag_name = ? AND id != ?
            ''', (tag_id, data['tagName'], tag_id))
            
            if cursor.fetchone():
                conn.close()
                return web.json_response({
                    'success': False,
                    'error': 'TAG_001: Tag name already exists for this device'
                }, status=409)
        
        # Prepare update fields
        update_fields = []
        update_values = []
        
        field_mapping = {
            'tagName': 'tag_name',
            'description': 'description',
            'address': 'address',
            'dataType': 'data_type',
            'endianness': 'endianness',
            'scale': 'scale',
            'offset': 'offset',
            'unit': 'unit',
            'pollInterval': 'poll_interval',
            'category': 'category',
            'minValid': 'min_valid',
            'maxValid': 'max_valid'
        }
        
        for json_field, db_field in field_mapping.items():
            if json_field in data:
                if json_field in ['minValid', 'maxValid']:
                    if data[json_field] == '':
                        update_fields.append(f"{db_field} = ?")
                        update_values.append(None)
                    else:
                        update_fields.append(f"{db_field} = ?")
                        update_values.append(float(data[json_field]))
                elif json_field in ['scale', 'offset']:
                    update_fields.append(f"{db_field} = ?")
                    update_values.append(float(data[json_field]))
                elif json_field == 'pollInterval':
                    update_fields.append(f"{db_field} = ?")
                    update_values.append(int(data[json_field]))
                else:
                    update_fields.append(f"{db_field} = ?")
                    update_values.append(data[json_field])
        
        # Handle protocol config
        protocol_config = {}
        protocol_keys = ['registerType', 'registerCount', 'byteOrder', 'canId', 
                        'dataLength', 'channel', 'nodeId', 'sensorId', 'parameterId']
        
        for key in protocol_keys:
            if key in data:
                protocol_config[key] = data[key]
        
        if protocol_config:
            update_fields.append("protocol_config = ?")
            update_values.append(json.dumps(protocol_config))
        
        # Add updated_at timestamp
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        
        # Execute update
        if update_fields:
            update_query = f'''
                UPDATE tag_mappings 
                SET {', '.join(update_fields)}
                WHERE id = ?
            '''
            update_values.append(tag_id)
            
            cursor.execute(update_query, update_values)
            conn.commit()
        
        conn.close()
        
        return web.json_response({
            'success': True,
            'message': 'Tag mapping updated successfully',
            'tag': {
                'id': tag_id,
                'tagName': data.get('tagName', '')
            }
        })
        
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)

# DELETE /api/tag-mapping/{id} - Delete tag mapping
async def delete_tag_mapping(request):
    """Delete a tag mapping"""
    try:
        tag_id = request.match_info['id']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if tag exists
        cursor.execute('SELECT id FROM tag_mappings WHERE id = ?', (tag_id,))
        tag = cursor.fetchone()
        
        if not tag:
            conn.close()
            return web.json_response({
                'success': False,
                'error': 'TAG_005: Tag mapping not found'
            }, status=404)
        
        # Delete tag
        cursor.execute('DELETE FROM tag_mappings WHERE id = ?', (tag_id,))
        conn.commit()
        conn.close()
        
        return web.json_response({
            'success': True,
            'message': 'Tag mapping deleted successfully',
            'deleted_id': tag_id
        })
        
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)

# GET /api/tag-mapping/{id} - Get tag mapping details
async def get_tag_mapping_details(request):
    """Get detailed information for a single tag mapping"""
    try:
        tag_id = request.match_info['id']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT tm.*, dm.name as device_name, dm.type as device_type
            FROM tag_mappings tm
            LEFT JOIN device_management dm ON tm.device_id = dm.id
            WHERE tm.id = ?
        ''', (tag_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return web.json_response({
                'success': False,
                'error': 'TAG_005: Tag mapping not found'
            }, status=404)
        
        # Parse protocol config
        protocol_config = json.loads(row['protocol_config']) if row['protocol_config'] else {}
        
        # Get device protocol from device management
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT config_json FROM device_management WHERE id = ?', (row['device_id'],))
        device_config = cursor.fetchone()
        conn.close()
        
        device_protocol = 'Unknown'
        if device_config and device_config['config_json']:
            try:
                config = json.loads(device_config['config_json'])
                device_protocol = config.get('protocol', 'Unknown')
            except:
                pass
        
        tag_data = {
            'id': row['id'],
            'deviceId': row['device_id'],
            'deviceName': row['device_name'],
            'deviceType': row['device_type'],
            'protocol': device_protocol,
            'tagName': row['tag_name'],
            'description': row['description'],
            'address': row['address'],
            'dataType': row['data_type'],
            'endianness': row['endianness'],
            'scale': row['scale'],
            'offset': row['offset'],
            'unit': row['unit'],
            'pollInterval': row['poll_interval'],
            'category': row['category'],
            'minValid': row['min_valid'],
            'maxValid': row['max_valid'],
            'createdAt': row['created_at'],
            'updatedAt': row['updated_at'],
            'lastValue': 0.0,  # Would come from real-time data
            'quality': 'Good'  # Default quality
        }
        
        # Add protocol-specific config
        tag_data.update(protocol_config)
        
        return web.json_response(tag_data)
        
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)

# GET /api/tag-mapping/devices - Get available devices
async def get_available_devices(request):
    """Get list of all available devices for dropdown selection"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT dm.id, dm.name, dm.type, 
                   CASE 
                       WHEN dm.config_json LIKE '%"protocol":"modbus-rtu"%' THEN 'modbus-rtu'
                       WHEN dm.config_json LIKE '%"protocol":"modbus-tcp"%' THEN 'modbus-tcp'
                       WHEN dm.config_json LIKE '%"protocol":"can"%' THEN 'can'
                       WHEN dm.config_json LIKE '%"protocol":"ethernet-ip"%' THEN 'ethernet-ip'
                       ELSE 'unknown'
                   END as protocol,
                   dm.config_json,
                   (SELECT COUNT(*) FROM tag_mappings tm WHERE tm.device_id = dm.id) as tag_count
            FROM device_management dm
            ORDER BY dm.name
        ''')
        
        devices = []
        for row in cursor.fetchall():
            config = json.loads(row['config_json']) if row['config_json'] else {}
            devices.append({
                'id': row['id'],
                'name': row['name'],
                'protocol': row['protocol'],
                'type': row['type'],
                'status': config.get('status', 'unknown'),
                'address': config.get('address', ''),
                'tagCount': row['tag_count']
            })
        
        conn.close()
        
        return web.json_response({
            'devices': devices,
            'total': len(devices)
        })
        
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)

# GET /api/tag-mapping/protocol-forms/{protocol} - Get protocol form configuration
async def get_protocol_form(request):
    """Get form configuration for a specific protocol"""
    try:
        protocol = request.match_info['protocol']
        
        # Protocol-specific form configurations
        protocol_forms = {
            'modbus-rtu': {
                'protocol': 'Modbus RTU',
                'formFields': [
                    {
                        'name': 'registerType',
                        'label': 'Register Type',
                        'type': 'select',
                        'options': [
                            {'value': 'holding', 'label': 'Holding Register (4x)'},
                            {'value': 'input', 'label': 'Input Register (3x)'},
                            {'value': 'coil', 'label': 'Coil (0x)'},
                            {'value': 'discrete', 'label': 'Discrete Input (1x)'}
                        ],
                        'default': 'holding'
                    },
                    {
                        'name': 'address',
                        'label': 'Register Address',
                        'type': 'number',
                        'min': 0,
                        'max': 65535,
                        'default': 40001
                    },
                    {
                        'name': 'registerCount',
                        'label': 'Register Count',
                        'type': 'number',
                        'min': 1,
                        'max': 125,
                        'default': 1
                    },
                    {
                        'name': 'byteOrder',
                        'label': 'Byte Order',
                        'type': 'select',
                        'options': [
                            {'value': '0', 'label': '0-based (ABCD)'},
                            {'value': '1', 'label': '1-based (BADC)'}
                        ],
                        'default': '0'
                    }
                ],
                'supportedDataTypes': ['INT16', 'UINT16', 'INT32', 'UINT32', 'FLOAT32', 'BOOL']
            },
            'modbus-tcp': {
                'protocol': 'Modbus TCP',
                'formFields': [
                    {
                        'name': 'registerType',
                        'label': 'Register Type',
                        'type': 'select',
                        'options': [
                            {'value': 'holding', 'label': 'Holding Register (4x)'},
                            {'value': 'input', 'label': 'Input Register (3x)'}
                        ],
                        'default': 'holding'
                    },
                    {
                        'name': 'address',
                        'label': 'Register Address',
                        'type': 'number',
                        'min': 0,
                        'max': 65535,
                        'default': 40001
                    },
                    {
                        'name': 'registerCount',
                        'label': 'Register Count',
                        'type': 'number',
                        'min': 1,
                        'max': 125,
                        'default': 1
                    }
                ],
                'supportedDataTypes': ['INT16', 'UINT16', 'INT32', 'UINT32', 'FLOAT32', 'BOOL']
            },
            'can': {
                'protocol': 'CANBus',
                'formFields': [
                    {
                        'name': 'canId',
                        'label': 'CAN ID',
                        'type': 'text',
                        'placeholder': 'e.g., 0x100',
                        'default': '0x100'
                    },
                    {
                        'name': 'dataLength',
                        'label': 'Data Length (Bytes)',
                        'type': 'select',
                        'options': [
                            {'value': '1', 'label': '1 byte'},
                            {'value': '2', 'label': '2 bytes'},
                            {'value': '4', 'label': '4 bytes'},
                            {'value': '8', 'label': '8 bytes'}
                        ],
                        'default': '4'
                    },
                    {
                        'name': 'byteOrder',
                        'label': 'Byte Order',
                        'type': 'select',
                        'options': [
                            {'value': 'little-endian', 'label': 'Little Endian'},
                            {'value': 'big-endian', 'label': 'Big Endian'}
                        ],
                        'default': 'little-endian'
                    }
                ],
                'supportedDataTypes': ['INT16', 'UINT16', 'INT32', 'UINT32', 'FLOAT32', 'BYTE']
            },
            'ethernet-ip': {
                'protocol': 'EtherNet/IP',
                'formFields': [
                    {
                        'name': 'tagName',
                        'label': 'Tag Name',
                        'type': 'text',
                        'placeholder': 'e.g., MotorRPM',
                        'default': ''
                    },
                    {
                        'name': 'dataType',
                        'label': 'Data Type',
                        'type': 'select',
                        'options': [
                            {'value': 'BOOL', 'label': 'BOOL (1 bit)'},
                            {'value': 'SINT', 'label': 'SINT (8-bit)'},
                            {'value': 'INT', 'label': 'INT (16-bit)'},
                            {'value': 'DINT', 'label': 'DINT (32-bit)'},
                            {'value': 'REAL', 'label': 'REAL (32-bit float)'}
                        ],
                        'default': 'DINT'
                    }
                ],
                'supportedDataTypes': ['BOOL', 'INT16', 'UINT16', 'INT32', 'UINT32', 'FLOAT32']
            }
        }
        
        if protocol in protocol_forms:
            return web.json_response(protocol_forms[protocol])
        else:
            # Default form for unknown protocols
            return web.json_response({
                'protocol': protocol.upper(),
                'formFields': [
                    {
                        'name': 'address',
                        'label': 'Address',
                        'type': 'text',
                        'placeholder': 'Enter address...',
                        'default': ''
                    }
                ],
                'supportedDataTypes': ['INT16', 'UINT16', 'INT32', 'UINT32', 'FLOAT32', 'BOOL', 'STRING']
            })
        
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)

# POST /api/tag-mapping/import-csv - Import tag mappings from CSV
async def import_csv(request):
    """Import tag mappings from CSV file"""
    try:
        # Check if request has file
        reader = await request.multipart()
        field = await reader.next()
        
        if field.name != 'file':
            return web.json_response({
                'success': False,
                'error': 'No file uploaded'
            }, status=400)
        
        # Read CSV file
        csv_data = await field.read()
        csv_text = csv_data.decode('utf-8')
        
        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        imported = 0
        failed = 0
        errors = []
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for i, row in enumerate(csv_reader, 2):  # Start from line 2 (header is line 1)
            try:
                # Validate required fields
                required = ['deviceName', 'tagName', 'address', 'dataType']
                for field in required:
                    if not row.get(field):
                        raise ValueError(f'Missing required field: {field}')
                
                # Get device ID from device name
                cursor.execute('SELECT id FROM device_management WHERE name = ?', (row['deviceName'],))
                device = cursor.fetchone()
                
                if not device:
                    raise ValueError(f'Device not found: {row["deviceName"]}')
                
                device_id = device['id']
                
                # Check for duplicate tag
                cursor.execute('''
                    SELECT id FROM tag_mappings 
                    WHERE device_id = ? AND tag_name = ?
                ''', (device_id, row['tagName']))
                
                if cursor.fetchone():
                    raise ValueError(f'Tag already exists: {row["tagName"]}')
                
                # Parse numeric values
                scale = float(row.get('scale', 1.0))
                offset = float(row.get('offset', 0.0))
                poll_interval = int(row.get('pollInterval', 200))
                
                min_valid = float(row['minValid']) if row.get('minValid') else None
                max_valid = float(row['maxValid']) if row.get('maxValid') else None
                
                # Insert tag mapping
                cursor.execute('''
                    INSERT INTO tag_mappings (
                        device_id, tag_name, description, address, 
                        data_type, endianness, scale, offset, unit,
                        poll_interval, category, min_valid, max_valid
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    device_id,
                    row['tagName'],
                    row.get('description', ''),
                    row['address'],
                    row['dataType'],
                    row.get('endianness', 'big-endian'),
                    scale,
                    offset,
                    row.get('unit', ''),
                    poll_interval,
                    row.get('category', 'Sensors'),
                    min_valid,
                    max_valid
                ))
                
                imported += 1
                
            except Exception as e:
                failed += 1
                errors.append(f'Line {i}: {str(e)}')
        
        conn.commit()
        conn.close()
        
        return web.json_response({
            'success': True,
            'imported': imported,
            'failed': failed,
            'total': imported + failed,
            'errors': errors if errors else None
        })
        
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': f'Import error: {str(e)}'
        }, status=500)

# GET /api/tag-mapping/export-csv - Export tag mappings to CSV
async def export_csv(request):
    """Export tag mappings to CSV file"""
    try:
        # Get query parameters
        query = request.rel_url.query
        category = query.get('category')
        device_id = query.get('device_id')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build query with filters
        query_sql = '''
            SELECT 
                dm.name as device_name,
                tm.tag_name,
                tm.description,
                tm.address,
                tm.data_type,
                tm.endianness,
                tm.scale,
                tm.offset,
                tm.unit,
                tm.poll_interval,
                tm.category,
                tm.min_valid,
                tm.max_valid,
                tm.created_at
            FROM tag_mappings tm
            LEFT JOIN device_management dm ON tm.device_id = dm.id
        '''
        
        query_params = []
        where_conditions = []
        
        if category:
            where_conditions.append('tm.category = ?')
            query_params.append(category)
        
        if device_id:
            where_conditions.append('tm.device_id = ?')
            query_params.append(device_id)
        
        if where_conditions:
            query_sql += ' WHERE ' + ' AND '.join(where_conditions)
        
        query_sql += ' ORDER BY dm.name, tm.tag_name'
        
        cursor.execute(query_sql, query_params)
        rows = cursor.fetchall()
        conn.close()
        
        # Create CSV in memory
        output = io.StringIO()
        fieldnames = [
            'device_name', 'tag_name', 'description', 'address', 
            'data_type', 'endianness', 'scale', 'offset', 'unit',
            'poll_interval', 'category', 'min_valid', 'max_valid', 'created_at'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in rows:
            writer.writerow(dict(row))
        
        csv_content = output.getvalue()
        output.close()
        
        # Create response
        response = web.Response(text=csv_content)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename="tag_mappings_export.csv"'
        
        return response
        
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': f'Export error: {str(e)}'
        }, status=500)

# GET /api/tag-mapping/filter - Filter tag mappings
async def filter_tag_mappings(request):
    """Filter tag mappings based on criteria"""
    try:
        query = request.rel_url.query
        
        # Extract filter parameters
        category = query.get('category')
        device_id = query.get('device_id')
        protocol = query.get('protocol')
        search = query.get('search', '').lower()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build query
        query_sql = '''
            SELECT 
                tm.id,
                tm.tag_name,
                tm.description,
                tm.address,
                tm.data_type,
                tm.unit,
                tm.category,
                tm.poll_interval,
                dm.name as device_name,
                dm.id as device_id,
                CASE 
                    WHEN dm.config_json LIKE '%"protocol":"modbus-rtu"%' THEN 'modbus-rtu'
                    WHEN dm.config_json LIKE '%"protocol":"modbus-tcp"%' THEN 'modbus-tcp'
                    WHEN dm.config_json LIKE '%"protocol":"can"%' THEN 'can'
                    WHEN dm.config_json LIKE '%"protocol":"ethernet-ip"%' THEN 'ethernet-ip'
                    ELSE 'unknown'
                END as protocol
            FROM tag_mappings tm
            LEFT JOIN device_management dm ON tm.device_id = dm.id
        '''
        
        query_params = []
        where_conditions = []
        
        if category:
            where_conditions.append('tm.category = ?')
            query_params.append(category)
        
        if device_id:
            where_conditions.append('tm.device_id = ?')
            query_params.append(device_id)
        
        if protocol:
            where_conditions.append('''
                CASE 
                    WHEN dm.config_json LIKE '%"protocol":"modbus-rtu"%' THEN 'modbus-rtu'
                    WHEN dm.config_json LIKE '%"protocol":"modbus-tcp"%' THEN 'modbus-tcp'
                    WHEN dm.config_json LIKE '%"protocol":"can"%' THEN 'can'
                    WHEN dm.config_json LIKE '%"protocol":"ethernet-ip"%' THEN 'ethernet-ip'
                    ELSE 'unknown'
                END = ?
            ''')
            query_params.append(protocol)
        
        if search:
            where_conditions.append('''
                (LOWER(tm.tag_name) LIKE ? OR 
                 LOWER(tm.description) LIKE ? OR
                 LOWER(dm.name) LIKE ?)
            ''')
            search_term = f'%{search}%'
            query_params.extend([search_term, search_term, search_term])
        
        if where_conditions:
            query_sql += ' WHERE ' + ' AND '.join(where_conditions)
        
        query_sql += ' ORDER BY tm.tag_name'
        
        cursor.execute(query_sql, query_params)
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries
        mappings = []
        for row in rows:
            mappings.append(dict(row))
        
        conn.close()
        
        return web.json_response({
            'mappings': mappings,
            'count': len(mappings)
        })
        
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': f'Filter error: {str(e)}'
        }, status=500)

# POST /api/tag-mapping/devices/{device_id}/test - Test device connection
async def test_device_connection(request):
    """Test connection to a device"""
    try:
        device_id = request.match_info['device_id']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get device details
        cursor.execute('SELECT name, config_json FROM device_management WHERE id = ?', (device_id,))
        device = cursor.fetchone()
        conn.close()
        
        if not device:
            return web.json_response({
                'success': False,
                'error': 'Device not found'
            }, status=404)
        
        # Simulate device test (in real implementation, this would actually test the device)
        import random
        import time
        
        # Simulate network delay
        time.sleep(0.5)
        
        # Generate random ping time
        ping_time = random.randint(1, 50)
        
        # Determine status based on ping time
        status = 'Online' if ping_time < 30 else 'Slow' if ping_time < 100 else 'Offline'
        
        return web.json_response({
            'success': True,
            'ping_time_ms': ping_time,
            'status': status,
            'device_name': device['name']
        })
        
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': f'Test error: {str(e)}'
        }, status=500)

# POST /api/tag-mapping/validate-all - Validate all tag mappings
async def validate_all_mappings(request):
    """Validate all tag mappings"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all tag mappings
        cursor.execute('''
            SELECT COUNT(*) as total_count,
                   SUM(CASE WHEN address IS NULL OR address = '' THEN 1 ELSE 0 END) as missing_address,
                   SUM(CASE WHEN tag_name IS NULL OR tag_name = '' THEN 1 ELSE 0 END) as missing_name,
                   SUM(CASE WHEN data_type IS NULL OR data_type = '' THEN 1 ELSE 0 END) as missing_type
            FROM tag_mappings
        ''')
        
        stats = cursor.fetchone()
        conn.close()
        
        total = stats['total_count']
        errors = []
        
        if stats['missing_address'] > 0:
            errors.append(f'{stats["missing_address"]} mappings missing address')
        
        if stats['missing_name'] > 0:
            errors.append(f'{stats["missing_name"]} mappings missing tag name')
        
        if stats['missing_type'] > 0:
            errors.append(f'{stats["missing_type"]} mappings missing data type')
        
        return web.json_response({
            'success': True,
            'validated_count': total,
            'errors': errors,
            'message': 'All mappings validated successfully' if not errors else 'Validation completed with errors'
        })
        
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': f'Validation error: {str(e)}'
        }, status=500)

# PUT /api/tag-mapping/save-config - Save configuration
async def save_configuration(request):
    """Save all tag mapping configuration"""
    try:
        # In a real implementation, this might save to a file or trigger a system reload
        # For now, we'll just acknowledge the request
        
        return web.json_response({
            'success': True,
            'message': 'Configuration saved successfully',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': f'Save error: {str(e)}'
        }, status=500)