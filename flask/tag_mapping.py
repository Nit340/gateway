# tag_mapping.py - Tag Mapping API endpoints with device integration
import sqlite3
import json
import csv
import io
import uuid
import re
from aiohttp import web
from datetime import datetime
import asyncio
DB_FILE = 'gateway_config.db'

# Protocol-specific form configurations
PROTOCOL_FORMS = {
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
        'supportedDataTypes': ['INT16', 'UINT16', 'INT32', 'UINT32', 'FLOAT32', 'BOOL', 'STRING']
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
                    {'value': 'input', 'label': 'Input Register (3x)'},
                    {'value': 'coil', 'label': 'Coil (0x)'},
                    {'value': 'discrete', 'label': 'Discrete Input (1x)'}
                ],
                'default': 'holding'
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
                'name': 'unitId',
                'label': 'Unit ID',
                'type': 'number',
                'min': 1,
                'max': 247,
                'default': 1
            }
        ],
        'supportedDataTypes': ['INT16', 'UINT16', 'INT32', 'UINT32', 'FLOAT32', 'BOOL', 'STRING']
    },
    'can': {
        'protocol': 'CANBus',
        'formFields': [
            {
                'name': 'canId',
                'label': 'CAN ID',
                'type': 'text',
                'placeholder': '0x100',
                'pattern': '^0x[0-9A-Fa-f]{1,8}$'
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
                    {'value': 'little', 'label': 'Little Endian'},
                    {'value': 'big', 'label': 'Big Endian'}
                ],
                'default': 'little'
            },
            {
                'name': 'startByte',
                'label': 'Start Byte',
                'type': 'number',
                'min': 0,
                'max': 7,
                'default': 0
            }
        ],
        'supportedDataTypes': ['INT16', 'UINT16', 'INT32', 'UINT32', 'FLOAT32', 'BOOL']
    },
    'ethernet-ip': {
        'protocol': 'EtherNet/IP',
        'formFields': [
            {
                'name': 'tagType',
                'label': 'Tag Type',
                'type': 'select',
                'options': [
                    {'value': 'tag', 'label': 'Tag Name'},
                    {'value': 'symbolic', 'label': 'Symbolic Address'},
                    {'value': 'direct', 'label': 'Direct Address'}
                ],
                'default': 'tag'
            },
            {
                'name': 'dataSize',
                'label': 'Data Size',
                'type': 'select',
                'options': [
                    {'value': 'BOOL', 'label': 'BOOL (1 bit)'},
                    {'value': 'SINT', 'label': 'SINT (8-bit)'},
                    {'value': 'INT', 'label': 'INT (16-bit)'},
                    {'value': 'DINT', 'label': 'DINT (32-bit)'},
                    {'value': 'REAL', 'label': 'REAL (32-bit float)'}
                ],
                'default': 'DINT'
            },
            {
                'name': 'arraySize',
                'label': 'Array Size',
                'type': 'number',
                'min': 1,
                'default': 1
            }
        ],
        'supportedDataTypes': ['BOOL', 'INT16', 'UINT16', 'INT32', 'UINT32', 'FLOAT32']
    }
}

# Default protocol for unknown devices
DEFAULT_PROTOCOL = {
    'protocol': 'Generic',
    'formFields': [
        {
            'name': 'addressType',
            'label': 'Address Type',
            'type': 'select',
            'options': [
                {'value': 'decimal', 'label': 'Decimal'},
                {'value': 'hex', 'label': 'Hexadecimal'},
                {'value': 'binary', 'label': 'Binary'}
            ],
            'default': 'decimal'
        }
    ],
    'supportedDataTypes': ['INT16', 'UINT16', 'INT32', 'UINT32', 'FLOAT32', 'BOOL', 'STRING']
}

async def get_tag_mapping_page(request):
    """GET handler - tag mapping page with embedded data"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get all devices
    cursor.execute('''
        SELECT id, name, type, protocol, address, firmware_version, 
               config_json, created_at, updated_at
        FROM device_management
        ORDER BY name
    ''')
    devices = []
    for row in cursor.fetchall():
        try:
            config = json.loads(row[6]) if row[6] else {}
        except:
            config = {}
        
        devices.append({
            'id': row[0],
            'name': row[1],
            'type': row[2],
            'protocol': row[3],
            'address': row[4],
            'firmware_version': row[5],
            'config': config,
            'created_at': row[7],
            'updated_at': row[8]
        })
    
    # Get all tag mappings
    cursor.execute('''
        SELECT tm.id, tm.device_id, tm.tag_name, tm.description, tm.address,
               tm.data_type, tm.endianness, tm.scale, tm.offset, tm.unit,
               tm.poll_interval, tm.category, tm.min_valid, tm.max_valid,
               tm.protocol_config, tm.created_at, tm.updated_at,
               dm.name as device_name, dm.protocol as device_protocol
        FROM tag_mappings tm
        LEFT JOIN device_management dm ON tm.device_id = dm.id
        ORDER BY tm.tag_name
    ''')
    
    mappings = []
    for row in cursor.fetchall():
        try:
            protocol_config = json.loads(row[14]) if row[14] else {}
        except:
            protocol_config = {}
        
        mappings.append({
            'id': row[0],
            'deviceId': row[1],
            'deviceName': row[17] or 'Unknown',
            'deviceProtocol': row[18] or 'Unknown',
            'tagName': row[2],
            'description': row[3],
            'address': row[4],
            'dataType': row[5],
            'endianness': row[6],
            'scale': row[7],
            'offset': row[8],
            'unit': row[9],
            'pollInterval': row[10],
            'category': row[11],
            'minValid': row[12],
            'maxValid': row[13],
            'protocolConfig': protocol_config,
            'createdAt': row[15],
            'updatedAt': row[16]
        })
    
    # Get all categories
    cursor.execute('SELECT id, name, description, color FROM tag_categories ORDER BY name')
    categories = [
        {'id': row[0], 'name': row[1], 'description': row[2], 'color': row[3]}
        for row in cursor.fetchall()
    ]
    
    conn.close()
    
    # Render HTML with embedded data
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Tag Mapping - Univa Gateway</title>
        <script>
            window.initialData = {{
                devices: {json.dumps(devices)},
                mappings: {json.dumps(mappings)},
                categories: {json.dumps(categories)}
            }};
        </script>
    </head>
    <body>
        <div id="app"></div>
        <!-- JavaScript will load and render the tag mapping interface -->
    </body>
    </html>
    '''
    
    return web.Response(text=html, content_type='text/html')

async def create_tag_mapping(request):
    """POST /api/tag-mapping - Create new tag mapping"""
    try:
        data = await request.json()
        
        # Validate required fields
        required_fields = ['deviceId', 'tagName', 'address', 'dataType']
        for field in required_fields:
            if field not in data:
                return web.json_response(
                    {'error': f'Missing required field: {field}'},
                    status=400
                )
        
        # Check if tag name already exists for this device
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) FROM tag_mappings 
            WHERE device_id = ? AND tag_name = ?
        ''', (data['deviceId'], data['tagName']))
        
        if cursor.fetchone()[0] > 0:
            conn.close()
            return web.json_response(
                {'error': 'Tag name already exists for this device', 'code': 'TAG_001'},
                status=400
            )
        
        # Validate device exists
        cursor.execute('SELECT id, protocol FROM device_management WHERE id = ?', (data['deviceId'],))
        device = cursor.fetchone()
        
        if not device:
            conn.close()
            return web.json_response(
                {'error': 'Device not found', 'code': 'TAG_002'},
                status=404
            )
        
        device_id, device_protocol = device
        
        # Validate data type for protocol
        protocol_form = PROTOCOL_FORMS.get(device_protocol, DEFAULT_PROTOCOL)
        supported_types = protocol_form.get('supportedDataTypes', [])
        
        if data['dataType'] not in supported_types:
            conn.close()
            return web.json_response(
                {'error': f'Unsupported data type {data["dataType"]} for protocol {device_protocol}', 'code': 'TAG_003'},
                status=400
            )
        
        # Prepare protocol config
        protocol_config = {
            'registerType': data.get('protocolConfig', {}).get('registerType', 'holding'),
            'address': data.get('address'),
            'registerCount': data.get('protocolConfig', {}).get('registerCount', 1),
            'byteOrder': data.get('protocolConfig', {}).get('byteOrder', '0')
        }
        
        # Insert tag mapping
        cursor.execute('''
            INSERT INTO tag_mappings (
                device_id, tag_name, description, address, data_type,
                endianness, scale, offset, unit, poll_interval,
                category, min_valid, max_valid, protocol_config
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['deviceId'],
            data['tagName'],
            data.get('description', ''),
            data['address'],
            data['dataType'],
            data.get('endianness', 'big-endian'),
            data.get('scale', 1.0),
            data.get('offset', 0.0),
            data.get('unit', ''),
            data.get('pollInterval', 200),
            data.get('category', 'Sensors'),
            data.get('minValid'),
            data.get('maxValid'),
            json.dumps(protocol_config)
        ))
        
        tag_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        # Get device name for response
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM device_management WHERE id = ?', (data['deviceId'],))
        device_name = cursor.fetchone()[0]
        conn.close()
        
        return web.json_response({
            'success': True,
            'tag': {
                'id': tag_id,
                'deviceId': data['deviceId'],
                'deviceName': device_name,
                'tagName': data['tagName'],
                'protocol': device_protocol,
                'address': data['address'],
                'dataType': data['dataType'],
                'unit': data.get('unit', '')
            }
        }, status=201)
        
    except json.JSONDecodeError:
        return web.json_response(
            {'error': 'Invalid JSON format'},
            status=400
        )
    except Exception as e:
        print(f"Error creating tag mapping: {e}")
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )

async def update_tag_mapping(request):
    """PUT /api/tag-mapping/{id} - Update existing tag mapping"""
    try:
        tag_id = request.match_info['id']
        data = await request.json()
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Check if tag exists
        cursor.execute('SELECT device_id, tag_name FROM tag_mappings WHERE id = ?', (tag_id,))
        tag = cursor.fetchone()
        
        if not tag:
            conn.close()
            return web.json_response(
                {'error': 'Tag mapping not found', 'code': 'TAG_005'},
                status=404
            )
        
        device_id, old_tag_name = tag
        
        # Check if new tag name conflicts (if changed)
        new_tag_name = data.get('tagName')
        if new_tag_name and new_tag_name != old_tag_name:
            cursor.execute('''
                SELECT COUNT(*) FROM tag_mappings 
                WHERE device_id = ? AND tag_name = ? AND id != ?
            ''', (device_id, new_tag_name, tag_id))
            
            if cursor.fetchone()[0] > 0:
                conn.close()
                return web.json_response(
                    {'error': 'Tag name already exists for this device', 'code': 'TAG_001'},
                    status=400
                )
        
        # Get device protocol for validation
        cursor.execute('SELECT protocol FROM device_management WHERE id = ?', (device_id,))
        device_protocol = cursor.fetchone()[0]
        
        # Validate data type if changed
        if 'dataType' in data:
            protocol_form = PROTOCOL_FORMS.get(device_protocol, DEFAULT_PROTOCOL)
            supported_types = protocol_form.get('supportedDataTypes', [])
            
            if data['dataType'] not in supported_types:
                conn.close()
                return web.json_response(
                    {'error': f'Unsupported data type {data["dataType"]} for protocol {device_protocol}', 'code': 'TAG_003'},
                    status=400
                )
        
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
                update_fields.append(f"{db_field} = ?")
                update_values.append(data[json_field])
        
        # Update protocol config if provided
        if 'protocolConfig' in data:
            update_fields.append("protocol_config = ?")
            update_values.append(json.dumps(data['protocolConfig']))
        
        # Add updated timestamp
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        
        # Execute update
        if update_fields:
            update_values.append(tag_id)
            query = f'''
                UPDATE tag_mappings 
                SET {', '.join(update_fields)}
                WHERE id = ?
            '''
            cursor.execute(query, update_values)
        
        conn.commit()
        conn.close()
        
        return web.json_response({
            'success': True,
            'message': 'Tag mapping updated successfully',
            'tag': {
                'id': tag_id,
                'tagName': data.get('tagName', old_tag_name)
            }
        })
        
    except json.JSONDecodeError:
        return web.json_response(
            {'error': 'Invalid JSON format'},
            status=400
        )
    except Exception as e:
        print(f"Error updating tag mapping: {e}")
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )

async def delete_tag_mapping(request):
    """DELETE /api/tag-mapping/{id} - Delete tag mapping"""
    try:
        tag_id = request.match_info['id']
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Check if tag exists
        cursor.execute('SELECT tag_name FROM tag_mappings WHERE id = ?', (tag_id,))
        tag = cursor.fetchone()
        
        if not tag:
            conn.close()
            return web.json_response(
                {'error': 'Tag mapping not found', 'code': 'TAG_005'},
                status=404
            )
        
        # Delete the tag
        cursor.execute('DELETE FROM tag_mappings WHERE id = ?', (tag_id,))
        conn.commit()
        conn.close()
        
        return web.json_response({
            'success': True,
            'message': 'Tag mapping deleted successfully',
            'deleted_id': tag_id
        })
        
    except Exception as e:
        print(f"Error deleting tag mapping: {e}")
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )

async def get_tag_mapping_details(request):
    """GET /api/tag-mapping/{id} - Get detailed tag mapping information"""
    try:
        tag_id = request.match_info['id']
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT tm.id, tm.device_id, tm.tag_name, tm.description, tm.address,
                   tm.data_type, tm.endianness, tm.scale, tm.offset, tm.unit,
                   tm.poll_interval, tm.category, tm.min_valid, tm.max_valid,
                   tm.protocol_config, tm.created_at, tm.updated_at,
                   dm.name as device_name, dm.protocol as device_protocol,
                   dm.type as device_type
            FROM tag_mappings tm
            LEFT JOIN device_management dm ON tm.device_id = dm.id
            WHERE tm.id = ?
        ''', (tag_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return web.json_response(
                {'error': 'Tag mapping not found', 'code': 'TAG_005'},
                status=404
            )
        
        try:
            protocol_config = json.loads(row[14]) if row[14] else {}
        except:
            protocol_config = {}
        
        tag_details = {
            'id': row[0],
            'deviceId': row[1],
            'deviceName': row[17] or 'Unknown',
            'deviceProtocol': row[18] or 'Unknown',
            'deviceType': row[19] or 'Unknown',
            'tagName': row[2],
            'description': row[3],
            'address': row[4],
            'dataType': row[5],
            'endianness': row[6],
            'scale': row[7],
            'offset': row[8],
            'unit': row[9],
            'pollInterval': row[10],
            'category': row[11],
            'minValid': row[12],
            'maxValid': row[13],
            'protocolConfig': protocol_config,
            'createdAt': row[15],
            'updatedAt': row[16],
            'lastValue': 0.0,  # In production, get from real-time data
            'quality': 'Good'  # In production, get from real-time data
        }
        
        return web.json_response(tag_details)
        
    except Exception as e:
        print(f"Error getting tag details: {e}")
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )

async def get_available_devices(request):
    """GET /api/tag-mapping/devices - Get list of available devices"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, protocol, type, 
                   (SELECT COUNT(*) FROM tag_mappings WHERE device_id = device_management.id) as tag_count
            FROM device_management
            ORDER BY name
        ''')
        
        devices = []
        for row in cursor.fetchall():
            devices.append({
                'id': row[0],
                'name': row[1],
                'protocol': row[2],
                'type': row[3],
                'tagCount': row[4],
                'status': 'online'  # In production, get from real-time status
            })
        
        conn.close()
        
        return web.json_response({
            'devices': devices,
            'total': len(devices)
        })
        
    except Exception as e:
        print(f"Error getting devices: {e}")
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )

async def get_protocol_form(request):
    """GET /api/tag-mapping/protocol-forms/{protocol} - Get protocol form configuration"""
    try:
        protocol = request.match_info['protocol']
        
        # Get form configuration for the protocol
        protocol_form = PROTOCOL_FORMS.get(protocol, DEFAULT_PROTOCOL)
        
        return web.json_response(protocol_form)
        
    except Exception as e:
        print(f"Error getting protocol form: {e}")
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )

async def import_csv(request):
    """POST /api/tag-mapping/import-csv - Import tag mappings from CSV"""
    try:
        reader = await request.multipart()
        
        file_field = await reader.next()
        if file_field.name != 'file':
            return web.json_response(
                {'error': 'No file uploaded'},
                status=400
            )
        
        # Read CSV content
        csv_content = await file_field.read()
        csv_text = csv_content.decode('utf-8')
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        imported = 0
        failed = 0
        errors = []
        
        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        
        for i, row in enumerate(csv_reader, 1):
            try:
                # Validate required fields
                if not row.get('deviceId') or not row.get('tagName') or not row.get('address'):
                    errors.append(f"Row {i}: Missing required fields")
                    failed += 1
                    continue
                
                # Check device exists
                cursor.execute('SELECT id FROM device_management WHERE id = ?', (row['deviceId'],))
                if not cursor.fetchone():
                    errors.append(f"Row {i}: Device not found: {row['deviceId']}")
                    failed += 1
                    continue
                
                # Check if tag already exists
                cursor.execute('''
                    SELECT COUNT(*) FROM tag_mappings 
                    WHERE device_id = ? AND tag_name = ?
                ''', (row['deviceId'], row['tagName']))
                
                if cursor.fetchone()[0] > 0:
                    errors.append(f"Row {i}: Tag already exists: {row['tagName']}")
                    failed += 1
                    continue
                
                # Insert tag mapping
                cursor.execute('''
                    INSERT INTO tag_mappings (
                        device_id, tag_name, description, address, data_type,
                        endianness, scale, offset, unit, poll_interval,
                        category, min_valid, max_valid
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row['deviceId'],
                    row['tagName'],
                    row.get('description', ''),
                    row['address'],
                    row.get('dataType', 'INT16'),
                    row.get('endianness', 'big-endian'),
                    float(row.get('scale', 1.0)),
                    float(row.get('offset', 0.0)),
                    row.get('unit', ''),
                    int(row.get('pollInterval', 200)),
                    row.get('category', 'Sensors'),
                    float(row['minValid']) if row.get('minValid') else None,
                    float(row['maxValid']) if row.get('maxValid') else None
                ))
                
                imported += 1
                
            except Exception as e:
                errors.append(f"Row {i}: {str(e)}")
                failed += 1
        
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
        print(f"Error importing CSV: {e}")
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )

async def export_csv(request):
    """GET /api/tag-mapping/export-csv - Export tag mappings to CSV"""
    try:
        # Get query parameters for filtering
        query = request.rel_url.query
        category_filter = query.get('category')
        device_filter = query.get('device_id')
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Build query with filters
        sql = '''
            SELECT tm.id, dm.name as device_name, tm.tag_name, dm.protocol, 
                   tm.address, tm.data_type, tm.unit, tm.scale, tm.offset,
                   tm.poll_interval, tm.category, tm.description, 
                   tm.min_valid, tm.max_valid, tm.endianness
            FROM tag_mappings tm
            LEFT JOIN device_management dm ON tm.device_id = dm.id
        '''
        
        params = []
        conditions = []
        
        if category_filter:
            conditions.append("tm.category = ?")
            params.append(category_filter)
        
        if device_filter:
            conditions.append("tm.device_id = ?")
            params.append(device_filter)
        
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        
        sql += " ORDER BY dm.name, tm.tag_name"
        
        cursor.execute(sql, params)
        
        # Create CSV
        output = io.StringIO()
        fieldnames = [
            'id', 'deviceName', 'tagName', 'protocol', 'address', 'dataType',
            'unit', 'scale', 'offset', 'pollInterval', 'category', 'description',
            'minValid', 'maxValid', 'endianness'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in cursor.fetchall():
            writer.writerow({
                'id': row[0],
                'deviceName': row[1],
                'tagName': row[2],
                'protocol': row[3],
                'address': row[4],
                'dataType': row[5],
                'unit': row[6],
                'scale': row[7],
                'offset': row[8],
                'pollInterval': row[9],
                'category': row[10],
                'description': row[11],
                'minValid': row[12],
                'maxValid': row[13],
                'endianness': row[14]
            })
        
        conn.close()
        
        # Return CSV file
        csv_content = output.getvalue()
        
        response = web.Response(
            text=csv_content,
            content_type='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename="tag_mappings_export.csv"'
            }
        )
        
        return response
        
    except Exception as e:
        print(f"Error exporting CSV: {e}")
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )

async def filter_tag_mappings(request):
    """GET /api/tag-mapping/filter - Filter tag mappings"""
    try:
        query = request.rel_url.query
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Build query with filters
        sql = '''
            SELECT tm.id, tm.tag_name, dm.name as device_name, dm.protocol,
                   tm.address, tm.data_type, tm.unit, tm.category, tm.description
            FROM tag_mappings tm
            LEFT JOIN device_management dm ON tm.device_id = dm.id
        '''
        
        params = []
        conditions = []
        
        category = query.get('category')
        device_id = query.get('device_id')
        protocol = query.get('protocol')
        search = query.get('search')
        
        if category:
            conditions.append("tm.category = ?")
            params.append(category)
        
        if device_id:
            conditions.append("tm.device_id = ?")
            params.append(device_id)
        
        if protocol:
            conditions.append("dm.protocol = ?")
            params.append(protocol)
        
        if search:
            conditions.append("(tm.tag_name LIKE ? OR tm.description LIKE ? OR dm.name LIKE ?)")
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term])
        
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        
        sql += " ORDER BY tm.tag_name"
        
        cursor.execute(sql, params)
        
        mappings = []
        for row in cursor.fetchall():
            mappings.append({
                'id': row[0],
                'tagName': row[1],
                'deviceName': row[2],
                'protocol': row[3],
                'address': row[4],
                'dataType': row[5],
                'unit': row[6],
                'category': row[7],
                'description': row[8]
            })
        
        conn.close()
        
        return web.json_response({
            'mappings': mappings,
            'count': len(mappings)
        })
        
    except Exception as e:
        print(f"Error filtering mappings: {e}")
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )

async def test_device_connection(request):
    """POST /api/tag-mapping/devices/{device_id}/test - Test device connection"""
    try:
        device_id = request.match_info['device_id']
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT name FROM device_management WHERE id = ?', (device_id,))
        device = cursor.fetchone()
        conn.close()
        
        if not device:
            return web.json_response(
                {'error': 'Device not found'},
                status=404
            )
        
        # Simulate device test
        await asyncio.sleep(0.5)  # Simulate network delay
        
        # Random response time between 1-100ms
        ping_time = 1 + (hash(device_id) % 100)
        
        return web.json_response({
            'success': True,
            'ping_time_ms': ping_time,
            'status': 'Online' if ping_time < 50 else 'Slow'
        })
        
    except Exception as e:
        print(f"Error testing device: {e}")
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )

async def validate_all_mappings(request):
    """POST /api/tag-mapping/validate-all - Validate all tag mappings"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Get all mappings with device info
        cursor.execute('''
            SELECT tm.id, tm.tag_name, tm.address, tm.data_type,
                   dm.name as device_name, dm.protocol as device_protocol
            FROM tag_mappings tm
            LEFT JOIN device_management dm ON tm.device_id = dm.id
        ''')
        
        mappings = cursor.fetchall()
        conn.close()
        
        errors = []
        validated_count = len(mappings)
        
        # Validate each mapping
        for mapping in mappings:
            mapping_id, tag_name, address, data_type, device_name, protocol = mapping
            
            # Basic validation rules
            if not tag_name or not tag_name.strip():
                errors.append(f"Mapping {mapping_id}: Empty tag name")
            
            if not address or not address.strip():
                errors.append(f"Mapping {mapping_id}: Empty address")
            
            if protocol in ['modbus-rtu', 'modbus-tcp']:
                # Validate Modbus address
                if not re.match(r'^[0-9]+$', str(address)):
                    errors.append(f"Mapping {mapping_id}: Invalid Modbus address: {address}")
            
            elif protocol == 'can':
                # Validate CAN address
                if not re.match(r'^0x[0-9A-Fa-f]+$', str(address)):
                    errors.append(f"Mapping {mapping_id}: Invalid CAN address: {address}")
        
        return web.json_response({
            'success': True,
            'validated_count': validated_count,
            'errors': errors,
            'message': f'Validated {validated_count} mappings. Found {len(errors)} errors.'
        })
        
    except Exception as e:
        print(f"Error validating mappings: {e}")
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )

async def save_configuration(request):
    """PUT /api/tag-mapping/save-config - Save tag mapping configuration"""
    try:
        # This would typically save to a configuration file or database
        # For now, we'll just acknowledge the request
        
        return web.json_response({
            'success': True,
            'message': 'Configuration saved successfully',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"Error saving configuration: {e}")
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )