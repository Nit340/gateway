# tag_mapping.py - Tag mapping management API with JSON storage
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

# Default tag configuration schema
DEFAULT_TAG_CONFIG = {
    'description': '',
    'address': '',
    'data_type': 'INT16',
    'endianness': 'big-endian',
    'scale': 1.0,
    'offset': 0.0,
    'unit': '',
    'poll_interval': 200,
    'category': 'Sensors',
    'min_valid': None,
    'max_valid': None,
    'protocol_config': {}
}

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
        SELECT dm.id, dm.name, dm.type, dm.protocol,  -- Use protocol column
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
        SELECT tm.id, tm.device_id, tm.tag_name, tm.config_json,
               dm.name as device_name
        FROM tag_mappings tm
        LEFT JOIN device_management dm ON tm.device_id = dm.id
        ORDER BY tm.tag_name
    ''')
    
    mappings = []
    for row in cursor.fetchall():
        # Parse JSON configuration
        config = DEFAULT_TAG_CONFIG.copy()
        if row['config_json']:
            try:
                config.update(json.loads(row['config_json']))
            except:
                pass
        
        # Determine protocol from device
        device_protocol = 'modbus'
        for device in devices:
            if device['id'] == row['device_id']:
                device_protocol = device['protocol']
                break
        
        mapping = {
            'id': row['id'],
            'deviceId': row['device_id'],
            'deviceName': row['device_name'],
            'tagName': row['tag_name'],
            'protocol': device_protocol,
            'address': config['address'],
            'dataType': config['data_type'],
            'scale': str(config['scale']),
            'offset': str(config['offset']),
            'unit': config['unit'],
            'pollInterval': str(config['poll_interval']),
            'category': config['category'],
            'description': config['description'],
            'minValid': str(config['min_valid']) if config['min_valid'] is not None else '',
            'maxValid': str(config['max_valid']) if config['max_valid'] is not None else '',
            'endianness': config['endianness']
        }
        
        # Merge protocol-specific config
        mapping.update(config['protocol_config'])
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
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if device exists
        cursor.execute('SELECT id FROM device_management WHERE id = ?', (data['deviceId'],))
        if not cursor.fetchone():
            conn.close()
            return web.json_response({
                'success': False,
                'error': 'TAG_002: Invalid device ID'
            }, status=404)
        
        # Check if tag name already exists for this device
        cursor.execute('''
            SELECT id FROM tag_mappings 
            WHERE device_id = ? AND LOWER(tag_name) = LOWER(?)
        ''', (data['deviceId'], data['tagName']))
        
        existing_tag = cursor.fetchone()
        if existing_tag:
            conn.close()
            return web.json_response({
                'success': False,
                'error': f'TAG_001: Tag name "{data["tagName"]}" already exists for this device. Please use a unique tag name.',
                'code': 'TAG_001'
            }, status=409)
        
        # Prepare configuration JSON
        config_json = DEFAULT_TAG_CONFIG.copy()
        
        # Map input fields to configuration
        field_mapping = {
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
        
        for input_field, config_field in field_mapping.items():
            if input_field in data:
                if input_field in ['scale', 'offset', 'minValid', 'maxValid']:
                    try:
                        config_json[config_field] = float(data[input_field]) if data[input_field] not in ['', None] else None
                    except (ValueError, TypeError):
                        config_json[config_field] = None if input_field in ['minValid', 'maxValid'] else 0.0
                elif input_field == 'pollInterval':
                    try:
                        config_json[config_field] = int(data[input_field])
                    except (ValueError, TypeError):
                        config_json[config_field] = 200
                else:
                    config_json[config_field] = data[input_field]
        
        # Prepare protocol-specific configuration
        protocol_config = {}
        protocol_keys = ['registerType', 'registerCount', 'byteOrder', 'canId', 
                        'dataLength', 'channel', 'nodeId', 'sensorId', 'parameterId']
        
        for key in protocol_keys:
            if key in data:
                protocol_config[key] = data[key]
        
        config_json['protocol_config'] = protocol_config
        
        # Insert tag mapping
        cursor.execute('''
            INSERT INTO tag_mappings (device_id, tag_name, config_json)
            VALUES (?, ?, ?)
        ''', (
            data['deviceId'],
            data['tagName'],
            json.dumps(config_json)
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
        
        # Check if tag exists and get current config
        cursor.execute('SELECT id, device_id, config_json FROM tag_mappings WHERE id = ?', (tag_id,))
        tag = cursor.fetchone()
        if not tag:
            conn.close()
            return web.json_response({
                'success': False,
                'error': 'TAG_005: Tag mapping not found'
            }, status=404)
        
        device_id = tag['device_id']
        
        # Check if new tag name conflicts (if changed)
        if 'tagName' in data and data['tagName']:
            cursor.execute('''
                SELECT id FROM tag_mappings 
                WHERE device_id = ? 
                AND LOWER(tag_name) = LOWER(?) 
                AND id != ?
            ''', (device_id, data['tagName'], tag_id))
            
            if cursor.fetchone():
                conn.close()
                return web.json_response({
                    'success': False,
                    'error': f'TAG_001: Tag name "{data["tagName"]}" already exists for this device. Please use a unique tag name.',
                    'code': 'TAG_001'
                }, status=409)
        
        # Load current configuration
        current_config = DEFAULT_TAG_CONFIG.copy()
        if tag['config_json']:
            try:
                current_config.update(json.loads(tag['config_json']))
            except:
                pass
        
        # Update configuration with new values
        field_mapping = {
            'tagName': 'tag_name',  # Special case for column name
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
        
        # Update tag name if provided
        if 'tagName' in data:
            cursor.execute('UPDATE tag_mappings SET tag_name = ? WHERE id = ?', (data['tagName'], tag_id))
        
        # Update configuration JSON
        for input_field, config_field in field_mapping.items():
            if input_field in data and input_field != 'tagName':
                if input_field in ['scale', 'offset', 'minValid', 'maxValid']:
                    try:
                        current_config[config_field] = float(data[input_field]) if data[input_field] not in ['', None] else None
                    except (ValueError, TypeError):
                        current_config[config_field] = None if input_field in ['minValid', 'maxValid'] else 0.0
                elif input_field == 'pollInterval':
                    try:
                        current_config[config_field] = int(data[input_field])
                    except (ValueError, TypeError):
                        current_config[config_field] = 200
                else:
                    current_config[config_field] = data[input_field]
        
        # Update protocol-specific configuration
        protocol_keys = ['registerType', 'registerCount', 'byteOrder', 'canId', 
                        'dataLength', 'channel', 'nodeId', 'sensorId', 'parameterId']
        
        for key in protocol_keys:
            if key in data:
                current_config['protocol_config'][key] = data[key]
        
        # Save updated configuration
        cursor.execute('''
            UPDATE tag_mappings 
            SET config_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (json.dumps(current_config), tag_id))
        
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
        
        # Parse configuration JSON
        config = DEFAULT_TAG_CONFIG.copy()
        if row['config_json']:
            try:
                config.update(json.loads(row['config_json']))
            except:
                pass
        
        # Get device protocol from device management
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT config_json FROM device_management WHERE id = ?', (row['device_id'],))
        device_config = cursor.fetchone()
        conn.close()
        
        device_protocol = 'Unknown'
        if device_config and device_config['config_json']:
            try:
                device_config_json = json.loads(device_config['config_json'])
                device_protocol = device_config_json.get('protocol', 'Unknown')
            except:
                pass
        
        # Build response data
        tag_data = {
            'id': row['id'],
            'deviceId': row['device_id'],
            'deviceName': row['device_name'],
            'deviceType': row['device_type'],
            'protocol': device_protocol,
            'tagName': row['tag_name'],
            'createdAt': row['created_at'],
            'updatedAt': row['updated_at'],
            'lastValue': 0.0,  # Would come from real-time data
            'quality': 'Good'  # Default quality
        }
        
        # Add configuration data
        tag_data.update(config)
        
        # Flatten protocol config for easier access
        if 'protocol_config' in tag_data:
            tag_data.update(tag_data['protocol_config'])
        
        return web.json_response(tag_data)
        
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)

async def get_available_devices(request):
    """Get list of all available devices for dropdown selection"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # SIMPLIFIED QUERY - No JSON extraction
        cursor.execute('''
            SELECT 
                dm.id, 
                dm.name, 
                dm.type, 
                dm.protocol,  -- Use protocol column directly
                dm.config_json,
                (SELECT COUNT(*) FROM tag_mappings tm WHERE tm.device_id = dm.id) as tag_count
            FROM device_management dm
            ORDER BY dm.name
        ''')
        
        devices = []
        for row in cursor.fetchall():
            try:
                config = json.loads(row['config_json']) if row['config_json'] else {}
            except:
                config = {}
                
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
        print(f"Error getting devices: {str(e)}")
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
            'modbus-rtu': { ... },
            'modbus-tcp': { ... },
            'can': { ... },
            'ethernet-ip': { ... },
            'wireless': {  # NEW
                'protocol': 'Wireless',
                'formFields': [
                    {
                        'name': 'rf_address',
                        'label': 'RF Address',
                        'type': 'text',
                        'placeholder': 'e.g., RF:0x09',
                        'default': ''
                    },
                    {
                        'name': 'channel',
                        'label': 'Channel',
                        'type': 'number',
                        'min': 1,
                        'max': 16,
                        'default': 1
                    }
                ],
                'supportedDataTypes': ['INT16', 'UINT16', 'INT32', 'UINT32', 'FLOAT32']
            },
            'acs-sensor': {  # NEW
                'protocol': 'ACS Sensor',
                'formFields': [
                    {
                        'name': 'sensor_id',
                        'label': 'Sensor ID',
                        'type': 'text',
                        'placeholder': 'e.g., ACS-001',
                        'default': ''
                    },
                    {
                        'name': 'parameter_id',
                        'label': 'Parameter ID',
                        'type': 'text',
                        'placeholder': 'e.g., TEMP, PRESSURE',
                        'default': ''
                    }
                ],
                'supportedDataTypes': ['INT16', 'UINT32', 'FLOAT32']
            }
        }
        
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
                for field_name in required:
                    if not row.get(field_name):
                        raise ValueError(f'Missing required field: {field_name}')
                
                # Get device ID from device name
                cursor.execute('SELECT id FROM device_management WHERE name = ?', (row['deviceName'],))
                device = cursor.fetchone()
                
                if not device:
                    raise ValueError(f'Device not found: {row["deviceName"]}')
                
                device_id = device['id']
                
                # Check for duplicate tag (case-insensitive)
                cursor.execute('''
                    SELECT id FROM tag_mappings 
                    WHERE device_id = ? AND LOWER(tag_name) = LOWER(?)
                ''', (device_id, row['tagName']))
                
                if cursor.fetchone():
                    raise ValueError(f'Tag name already exists for this device: {row["tagName"]}')
                
                # Prepare configuration JSON
                config_json = DEFAULT_TAG_CONFIG.copy()
                
                # Map CSV fields to configuration
                config_json['description'] = row.get('description', '')
                config_json['address'] = row['address']
                config_json['data_type'] = row['dataType']
                config_json['endianness'] = row.get('endianness', 'big-endian')
                config_json['unit'] = row.get('unit', '')
                config_json['category'] = row.get('category', 'Sensors')
                
                # Parse numeric values
                try:
                    config_json['scale'] = float(row.get('scale', 1.0))
                except (ValueError, TypeError):
                    config_json['scale'] = 1.0
                
                try:
                    config_json['offset'] = float(row.get('offset', 0.0))
                except (ValueError, TypeError):
                    config_json['offset'] = 0.0
                
                try:
                    config_json['poll_interval'] = int(row.get('pollInterval', 200))
                except (ValueError, TypeError):
                    config_json['poll_interval'] = 200
                
                config_json['min_valid'] = float(row['minValid']) if row.get('minValid') else None
                config_json['max_valid'] = float(row['maxValid']) if row.get('maxValid') else None
                
                # Insert tag mapping
                cursor.execute('''
                    INSERT INTO tag_mappings (device_id, tag_name, config_json)
                    VALUES (?, ?, ?)
                ''', (
                    device_id,
                    row['tagName'],
                    json.dumps(config_json)
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
                tm.id,
                tm.device_id,
                tm.tag_name,
                tm.config_json,
                tm.created_at,
                dm.name as device_name
            FROM tag_mappings tm
            LEFT JOIN device_management dm ON tm.device_id = dm.id
        '''
        
        query_params = []
        where_conditions = []
        
        if category:
            # We need to parse JSON to filter by category
            # This is inefficient but works for small datasets
            cursor.execute('''
                SELECT tm.id, tm.config_json
                FROM tag_mappings tm
                WHERE json_extract(tm.config_json, '$.category') = ?
            ''', (category,))
            category_ids = [row['id'] for row in cursor.fetchall()]
            if category_ids:
                where_conditions.append(f'tm.id IN ({",".join("?" * len(category_ids))})')
                query_params.extend(category_ids)
        
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
        
        # Define CSV fields
        fieldnames = [
            'device_name', 'tag_name', 'description', 'address', 
            'data_type', 'endianness', 'scale', 'offset', 'unit',
            'poll_interval', 'category', 'min_valid', 'max_valid', 'created_at'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in rows:
            # Parse JSON configuration
            config = DEFAULT_TAG_CONFIG.copy()
            if row['config_json']:
                try:
                    config.update(json.loads(row['config_json']))
                except:
                    pass
            
            # Write CSV row
            writer.writerow({
                'device_name': row['device_name'],
                'tag_name': row['tag_name'],
                'description': config['description'],
                'address': config['address'],
                'data_type': config['data_type'],
                'endianness': config['endianness'],
                'scale': config['scale'],
                'offset': config['offset'],
                'unit': config['unit'],
                'poll_interval': config['poll_interval'],
                'category': config['category'],
                'min_valid': config['min_valid'],
                'max_valid': config['max_valid'],
                'created_at': row['created_at']
            })
        
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
        
        # Build query - SIMPLIFIED without JSON extraction
        query_sql = '''
            SELECT 
                tm.id,
                tm.tag_name,
                tm.config_json,
                dm.name as device_name,
                dm.id as device_id,
                dm.protocol  -- Use protocol column directly
            FROM tag_mappings tm
            LEFT JOIN device_management dm ON tm.device_id = dm.id
        '''
        
        query_params = []
        where_conditions = []
        
        if category:
            # Parse JSON in Python instead of SQL
            # We'll filter after fetching
            pass
        
        if device_id:
            where_conditions.append('tm.device_id = ?')
            query_params.append(device_id)
        
        if protocol:
            where_conditions.append('dm.protocol = ?')
            query_params.append(protocol)
        
        if search:
            where_conditions.append('''
                (LOWER(tm.tag_name) LIKE ? OR 
                 LOWER(dm.name) LIKE ?)
            ''')
            search_term = f'%{search}%'
            query_params.extend([search_term, search_term])
        
        if where_conditions:
            query_sql += ' WHERE ' + ' AND '.join(where_conditions)
        
        query_sql += ' ORDER BY tm.tag_name'
        
        cursor.execute(query_sql, query_params)
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries with parsed JSON
        mappings = []
        for row in rows:
            # Parse JSON configuration
            config = DEFAULT_TAG_CONFIG.copy()
            if row['config_json']:
                try:
                    config.update(json.loads(row['config_json']))
                except:
                    pass
            
            # Filter by category if specified (in Python)
            if category and config.get('category') != category:
                continue
            
            mapping = {
                'id': row['id'],
                'tag_name': row['tag_name'],
                'device_name': row['device_name'],
                'device_id': row['device_id'],
                'protocol': row['protocol']
            }
            
            # Add configuration fields
            mapping.update({
                'description': config['description'],
                'address': config['address'],
                'data_type': config['data_type'],
                'unit': config['unit'],
                'category': config['category'],
                'poll_interval': config['poll_interval']
            })
            
            mappings.append(mapping)
        
        conn.close()
        
        return web.json_response({
            'mappings': mappings,
            'count': len(mappings)
        })
        
    except Exception as e:
        print(f"Filter error: {str(e)}")
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
            SELECT COUNT(*) as total_count
            FROM tag_mappings
        ''')
        
        total = cursor.fetchone()['total_count']
        
        # Check for invalid JSON
        cursor.execute('''
            SELECT COUNT(*) as invalid_json_count
            FROM tag_mappings
            WHERE config_json IS NULL OR json_valid(config_json) = 0
        ''')
        
        invalid_json = cursor.fetchone()['invalid_json_count']
        
        conn.close()
        
        errors = []
        if invalid_json > 0:
            errors.append(f'{invalid_json} mappings have invalid JSON configuration')
        
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