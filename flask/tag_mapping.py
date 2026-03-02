# tag_mapping.py - Tag/Datapoint mapping API
import json
import sqlite3
from aiohttp import web

from database import DB_FILE

# ============================================================================
# GET ALL DATAPOINTS
# ============================================================================

async def get_all_datapoints(request):
    """GET all datapoints (modbus + loadcell)"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute('PRAGMA foreign_keys = ON')
        conn.row_factory = sqlite3.Row  # This allows accessing columns by name
        cursor = conn.cursor()
        
        tags = []
        
        # Get Modbus datapoints - with proper column quoting for 'group'
        cursor.execute('''
            SELECT 
                md.id, 
                md.device_id, 
                md.name, 
                md.register_address, 
                md.register_type,
                md.data_type, 
                md.byte_order, 
                md.word_order, 
                md.scale_factor, 
                md.offset,
                md.unit, 
                md.description, 
                md.enabled, 
                md.slave_id,
                md.group_id, 
                dg.name as group_name, 
                md."group" as tag_group,
                m.name as device_name, 
                m.device_type,
                md.writable, 
                md.retry_count, 
                md.timeout_ms, 
                md.register_count
            FROM modbus_datapoints md
            JOIN modbus_device m ON md.device_id = m.id
            LEFT JOIN device_groups dg ON md.group_id = dg.id
            ORDER BY md.device_id, md.slave_id, md.name
        ''')
        
        rows = cursor.fetchall()
        
        for row in rows:
            # Convert row to dict for easier handling
            r = dict(row)
            tags.append({
                'id': r['id'],
                'device_id': r['device_id'],
                'device_name': r['device_name'],
                'device_type': "Modbus {}".format(r['device_type'].upper() if r['device_type'] else ''),
                'tag_name': r['name'],
                'name': r['name'],
                'register_address': r['register_address'],
                'address': r['register_address'],
                'register_type': r['register_type'],
                'registerType': r['register_type'],
                'data_type': r['data_type'],
                'dataType': r['data_type'],
                'byte_order': r['byte_order'],
                'byteOrder': r['byte_order'],
                'word_order': r['word_order'],
                'wordOrder': r['word_order'],
                'scale_factor': r['scale_factor'],
                'scale': r['scale_factor'],
                'offset': r['offset'],
                'unit': r['unit'] or '',
                'description': r['description'] or '',
                'enabled': bool(r['enabled']),
                'slave_id': r['slave_id'] if r['slave_id'] is not None else 1,
                'slaveId': r['slave_id'] if r['slave_id'] is not None else 1,
                'group_id': r['group_id'],
                'group_name': r['group_name'] or '',
                'group': r['tag_group'] or '',  # Empty string if no group
                'writable': bool(r['writable']) if r['writable'] is not None else False,
                'retry_count': r['retry_count'] if r['retry_count'] is not None else 1,
                'retryCount': r['retry_count'] if r['retry_count'] is not None else 1,
                'timeout_ms': r['timeout_ms'] if r['timeout_ms'] is not None else 100,
                'timeoutMs': r['timeout_ms'] if r['timeout_ms'] is not None else 100,
                'register_count': r['register_count'] if r['register_count'] is not None else 1,
                'registerCount': r['register_count'] if r['register_count'] is not None else 1,
                'type': 'modbus'
            })
        
        # Get Loadcell datapoints
        cursor.execute('''
            SELECT 
                ld.id, 
                ld.device_id, 
                ld.name, 
                ld.unit,
                l.name as device_name, 
                l.capacity, 
                l.load_name, 
                l.capacity_name
            FROM loadcell_datapoints ld
            JOIN loadcell_device l ON ld.device_id = l.id
            ORDER BY ld.device_id, ld.name
        ''')
        
        rows = cursor.fetchall()
        
        for row in rows:
            r = dict(row)
            tags.append({
                'id': r['id'],
                'device_id': r['device_id'],
                'device_name': r['device_name'],
                'device_type': 'Loadcell',
                'tag_name': r['name'],
                'name': r['name'],
                'unit': r['unit'] or '',
                'capacity': r['capacity'],
                'load_name': r['load_name'] or 'load',
                'capacity_name': r['capacity_name'] or 'capacity',
                'data_type': 'float32',
                'dataType': 'float32',
                'description': "Loadcell {}".format(r['name']),
                'enabled': True,
                'type': 'loadcell'
            })
        
        conn.close()
        return web.json_response({'tags': tags})
        
    except Exception as e:
        print("Error getting tags: {}".format(str(e)))
        import traceback
        traceback.print_exc()
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# ADD MODBUS DATAPOINT (TAG)
# ============================================================================

async def add_modbus_datapoint(request):
    """POST - Add Modbus datapoint (tag)"""
    try:
        data = await request.json()
        print("Received data for modbus tag creation:", data)  # Debug log
        
        conn = sqlite3.connect(DB_FILE)
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()
        
        # Validate device exists
        cursor.execute('SELECT id FROM modbus_device WHERE id = ?', (data.get('device_id'),))
        if not cursor.fetchone():
            conn.close()
            return web.json_response({'error': 'Device not found'}, status=404)
        
        # Check if tag name already exists for this device+slave
        cursor.execute('''
            SELECT id FROM modbus_datapoints 
            WHERE device_id = ? AND slave_id = ? AND name = ?
        ''', (data.get('device_id'), data.get('slave_id', 1), data.get('tag_name')))
        
        if cursor.fetchone():
            conn.close()
            return web.json_response({'error': 'Tag name already exists for this device'}, status=400)
        
        # Get group value - can be empty string or None
        group_value = data.get('group', '')
        if group_value is None:
            group_value = ''
            
        # Try to find matching device group by name for group_id
        group_id = None
        if group_value:
            cursor.execute('SELECT id FROM device_groups WHERE name = ?', (group_value,))
            grp = cursor.fetchone()
            if grp:
                group_id = grp[0]

        cursor.execute('''
            INSERT INTO modbus_datapoints (
                device_id, name, slave_id, group_id, "group", register_address, register_type, data_type,
                byte_order, word_order, scale_factor, offset, unit, description, enabled,
                writable, retry_count, timeout_ms, register_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('device_id'),
            data.get('tag_name'),
            data.get('slave_id', 1),
            group_id,
            group_value,  # This can be empty string
            data.get('register_address'),
            data.get('register_type', 'holding'),
            data.get('data_type', 'uint16'),
            data.get('byte_order', 'big'),
            data.get('word_order', 'big'),
            data.get('scale_factor', 1.0),
            data.get('offset', 0.0),
            data.get('unit', ''),
            data.get('description', ''),
            data.get('enabled', True),
            data.get('writable', False),
            data.get('retry_count', 1),
            data.get('timeout_ms', 100),
            data.get('register_count', 1)
        ))
        
        datapoint_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return web.json_response({
            'success': True,
            'message': 'Tag added successfully',
            'id': datapoint_id
        })
        
    except Exception as e:
        print("Error adding tag: {}".format(str(e)))
        import traceback
        traceback.print_exc()
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# UPDATE MODBUS TAG
# ============================================================================

async def update_modbus_datapoint(request):
    """PUT - Update Modbus tag"""
    try:
        tag_id = request.match_info['id']
        data = await request.json()
        print("Received data for modbus tag update:", data)  # Debug log
        
        conn = sqlite3.connect(DB_FILE)
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()
        
        # Check if tag exists
        cursor.execute('SELECT id FROM modbus_datapoints WHERE id = ?', (tag_id,))
        if not cursor.fetchone():
            conn.close()
            return web.json_response({'error': 'Tag not found'}, status=404)
        
        update_fields = []
        values = []
        
        field_mappings = {
            'slave_id': 'slave_id',
            'tag_name': 'name',
            'register_address': 'register_address',
            'register_type': 'register_type',
            'data_type': 'data_type',
            'byte_order': 'byte_order',
            'word_order': 'word_order',
            'scale_factor': 'scale_factor',
            'offset': 'offset',
            'unit': 'unit',
            'description': 'description',
            'enabled': 'enabled',
            'writable': 'writable',
            'retry_count': 'retry_count',
            'timeout_ms': 'timeout_ms',
            'register_count': 'register_count'
        }
        
        # Handle regular fields
        for key, db_field in field_mappings.items():
            if key in data:
                update_fields.append('{} = ?'.format(db_field))
                values.append(data[key])
        
        # Handle group field separately (quoted)
        if 'group' in data:
            update_fields.append('"group" = ?')
            values.append(data['group'] or '')
            
            # Also try to update group_id if group name matches a device group
            if data['group']:
                cursor.execute('SELECT id FROM device_groups WHERE name = ?', (data['group'],))
                grp = cursor.fetchone()
                if grp:
                    update_fields.append('group_id = ?')
                    values.append(grp[0])
            else:
                update_fields.append('group_id = NULL')
        
        if not update_fields:
            conn.close()
            return web.json_response({'error': 'No fields to update'}, status=400)
        
        values.append(tag_id)
        
        query = '''
            UPDATE modbus_datapoints 
            SET {fields}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        '''.format(fields=', '.join(update_fields))
        
        cursor.execute(query, values)
        conn.commit()
        conn.close()
        
        return web.json_response({
            'success': True,
            'message': 'Tag updated successfully'
        })
        
    except Exception as e:
        print("Error updating tag: {}".format(str(e)))
        import traceback
        traceback.print_exc()
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# DELETE TAG
# ============================================================================

async def delete_datapoint(request):
    """DELETE - Delete tag"""
    try:
        tag_id = request.match_info['id']
        tag_type = request.query.get('type', 'modbus')
        
        conn = sqlite3.connect(DB_FILE)
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()
        
        if tag_type == 'loadcell':
            # Don't allow deleting auto-created loadcell tags
            cursor.execute('SELECT name FROM loadcell_datapoints WHERE id = ?', (tag_id,))
            row = cursor.fetchone()
            if row and row[0] in ['load', 'capacity']:
                conn.close()
                return web.json_response({
                    'success': False,
                    'message': 'Cannot delete auto-created loadcell tags'
                }, status=400)
            
            cursor.execute('DELETE FROM loadcell_datapoints WHERE id = ?', (tag_id,))
        else:
            cursor.execute('DELETE FROM modbus_datapoints WHERE id = ?', (tag_id,))
        
        conn.commit()
        conn.close()
        
        return web.json_response({
            'success': True,
            'message': 'Tag deleted successfully'
        })
        
    except Exception as e:
        print("Error deleting tag: {}".format(str(e)))
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# GET AVAILABLE DEVICES FOR TAG CREATION
# ============================================================================

async def get_available_devices(request):
    """GET devices available for creating tags"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()
        
        devices = []
        
        # Get Modbus devices
        cursor.execute('''
            SELECT id, name, device_type FROM modbus_device 
            WHERE enabled = 1 
            ORDER BY name
        ''')
        
        for row in cursor.fetchall():
            devices.append({
                'id': row[0],
                'name': row[1],
                'type': "Modbus {}".format(row[2].upper()),
                'protocol': "modbus-{}".format(row[2])
            })
        
        # Get Loadcell devices
        cursor.execute('''
            SELECT id, name FROM loadcell_device 
            WHERE enabled = 1 
            ORDER BY name
        ''')
        
        for row in cursor.fetchall():
            devices.append({
                'id': row[0],
                'name': row[1],
                'type': 'Loadcell',
                'protocol': 'loadcell'
            })
        
        conn.close()
        return web.json_response({'devices': devices})
        
    except Exception as e:
        print("Error getting available devices: {}".format(str(e)))
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# GET PROTOCOL FORM SCHEMA
# ============================================================================

async def get_protocol_form(request):
    """GET form schema for creating tag by protocol"""
    try:
        protocol = request.match_info['protocol']
        
        if protocol in ['modbus-tcp', 'modbus-rtu']:
            form_schema = {
                'protocol': protocol,
                'fields': [
                    {
                        'name': 'tag_name',
                        'label': 'Tag Name',
                        'type': 'text',
                        'required': True,
                        'placeholder': 'e.g., hoist_voltage'
                    },
                    {
                        'name': 'slave_id',
                        'label': 'Slave ID',
                        'type': 'number',
                        'required': False,
                        'default': 1,
                        'min': 1,
                        'max': 247
                    },
                    {
                        'name': 'register_type',
                        'label': 'Register Type',
                        'type': 'select',
                        'required': True,
                        'options': [
                            {'value': 'holding', 'label': 'Holding Register (R/W)'},
                            {'value': 'input', 'label': 'Input Register (R)'},
                            {'value': 'coil', 'label': 'Coil (R/W)'},
                            {'value': 'discrete', 'label': 'Discrete Input (R)'}
                        ],
                        'default': 'holding'
                    },
                    {
                        'name': 'register_address',
                        'label': 'Register Address',
                        'type': 'number',
                        'required': True,
                        'min': 0,
                        'max': 65535
                    },
                    {
                        'name': 'register_count',
                        'label': 'Register Count',
                        'type': 'number',
                        'required': False,
                        'default': 1,
                        'min': 1,
                        'max': 10
                    },
                    {
                        'name': 'data_type',
                        'label': 'Data Type',
                        'type': 'select',
                        'required': True,
                        'options': [
                            {'value': 'int16', 'label': 'INT16 (16-bit signed)'},
                            {'value': 'uint16', 'label': 'UINT16 (16-bit unsigned)'},
                            {'value': 'int32', 'label': 'INT32 (32-bit signed)'},
                            {'value': 'uint32', 'label': 'UINT32 (32-bit unsigned)'},
                            {'value': 'float32', 'label': 'FLOAT32 (32-bit float)'},
                            {'value': 'bool', 'label': 'BOOL (boolean)'}
                        ],
                        'default': 'uint16'
                    },
                    {
                        'name': 'byte_order',
                        'label': 'Byte Order',
                        'type': 'select',
                        'required': False,
                        'options': [
                            {'value': 'big', 'label': 'Big Endian'},
                            {'value': 'little', 'label': 'Little Endian'}
                        ],
                        'default': 'big'
                    },
                    {
                        'name': 'word_order',
                        'label': 'Word Order',
                        'type': 'select',
                        'required': False,
                        'options': [
                            {'value': 'big', 'label': 'Big Endian'},
                            {'value': 'little', 'label': 'Little Endian'}
                        ],
                        'default': 'big'
                    },
                    {
                        'name': 'scale_factor',
                        'label': 'Scale Factor',
                        'type': 'number',
                        'required': False,
                        'step': '0.001',
                        'default': 1.0
                    },
                    {
                        'name': 'offset',
                        'label': 'Offset',
                        'type': 'number',
                        'required': False,
                        'step': '0.01',
                        'default': 0.0
                    },
                    {
                        'name': 'unit',
                        'label': 'Unit',
                        'type': 'text',
                        'required': False,
                        'placeholder': 'e.g., V, A, Hz'
                    },
                    {
                        'name': 'group',
                        'label': 'Group',
                        'type': 'text',
                        'required': False,
                        'placeholder': 'e.g., hoist_group (optional)'
                    },
                    {
                        'name': 'writable',
                        'label': 'Writable',
                        'type': 'checkbox',
                        'required': False,
                        'default': False
                    },
                    {
                        'name': 'retry_count',
                        'label': 'Retry Count',
                        'type': 'number',
                        'required': False,
                        'default': 1,
                        'min': 0,
                        'max': 10
                    },
                    {
                        'name': 'timeout_ms',
                        'label': 'Timeout (ms)',
                        'type': 'number',
                        'required': False,
                        'default': 100,
                        'min': 10,
                        'max': 10000
                    },
                    {
                        'name': 'description',
                        'label': 'Description',
                        'type': 'textarea',
                        'required': False,
                        'placeholder': 'Description of this tag...'
                    }
                ]
            }
        elif protocol == 'loadcell':
            form_schema = {
                'protocol': protocol,
                'message': 'Loadcell tags (load, capacity) are auto-created when device is added.',
                'fields': []
            }
        else:
            return web.json_response({
                'error': 'Unknown protocol'
            }, status=400)
        
        return web.json_response(form_schema)
        
    except Exception as e:
        print("Error getting protocol form: {}".format(str(e)))
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# UPDATE LOADCELL DATAPOINT (unit only)
# ============================================================================

async def update_loadcell_datapoint(request):
    """PUT - Update Loadcell datapoint unit only"""
    try:
        tag_id = request.match_info['id']
        data = await request.json()
        
        conn = sqlite3.connect(DB_FILE)
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()
        
        # Check tag exists
        cursor.execute('SELECT id, name FROM loadcell_datapoints WHERE id = ?', (tag_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return web.json_response({'error': 'Loadcell tag not found'}, status=404)
        
        # Only allow updating unit
        unit = data.get('unit', '')
        cursor.execute(
            'UPDATE loadcell_datapoints SET unit = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (unit, tag_id)
        )
        
        conn.commit()
        conn.close()
        
        return web.json_response({
            'success': True,
            'message': 'Loadcell tag unit updated successfully'
        })
        
    except Exception as e:
        print("Error updating loadcell tag: {}".format(str(e)))
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# TAG GROUPS (device_groups table - managed from tag mapping page)
# ============================================================================

async def get_all_tag_groups(request):
    """GET all tag groups"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, color, description,
                   (SELECT COUNT(*) FROM modbus_datapoints WHERE group_id = dg.id) as tag_count
            FROM device_groups dg
            ORDER BY name
        ''')
        groups = []
        for row in cursor.fetchall():
            groups.append({
                'id': row[0],
                'name': row[1],
                'color': row[2] or 'blue',
                'description': row[3] or '',
                'tag_count': row[4]
            })
        conn.close()
        return web.json_response({'groups': groups})
    except Exception as e:
        print("Error getting tag groups: {}".format(str(e)))
        return web.json_response({'error': str(e)}, status=500)


async def add_tag_group(request):
    """POST - Create a new tag group"""
    try:
        data = await request.json()
        name = data.get('name', '').strip()
        if not name:
            return web.json_response({'error': 'Group name is required'}, status=400)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO device_groups (name, color, description) VALUES (?, ?, ?)',
            (name, data.get('color', 'blue'), data.get('description', ''))
        )
        group_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return web.json_response({'success': True, 'group_id': group_id, 'message': 'Group created'})
    except sqlite3.IntegrityError:
        return web.json_response({'error': 'Group name already exists'}, status=400)
    except Exception as e:
        print("Error adding tag group: {}".format(str(e)))
        return web.json_response({'error': str(e)}, status=500)


async def update_tag_group(request):
    """PUT - Update a tag group"""
    try:
        group_id = request.match_info['group_id']
        data = await request.json()
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        fields, values = [], []
        if 'name' in data:
            fields.append('name = ?')
            values.append(data['name'])
        if 'color' in data:
            fields.append('color = ?')
            values.append(data['color'])
        if 'description' in data:
            fields.append('description = ?')
            values.append(data['description'])
        if not fields:
            conn.close()
            return web.json_response({'error': 'Nothing to update'}, status=400)
        values.append(group_id)
        cursor.execute('UPDATE device_groups SET {} WHERE id = ?'.format(', '.join(fields)), values)
        conn.commit()
        conn.close()
        return web.json_response({'success': True, 'message': 'Group updated'})
    except Exception as e:
        print("Error updating tag group: {}".format(str(e)))
        return web.json_response({'error': str(e)}, status=500)


async def delete_tag_group(request):
    """DELETE - Delete a tag group (tags become ungrouped)"""
    try:
        group_id = request.match_info['group_id']
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('UPDATE modbus_datapoints SET group_id = NULL WHERE group_id = ?', (group_id,))
        cursor.execute('DELETE FROM device_groups WHERE id = ?', (group_id,))
        conn.commit()
        conn.close()
        return web.json_response({'success': True, 'message': 'Group deleted'})
    except Exception as e:
        print("Error deleting tag group: {}".format(str(e)))
        return web.json_response({'error': str(e)}, status=500)


async def assign_tags_to_group(request):
    """POST - Assign tag IDs to a group"""
    try:
        group_id = request.match_info['group_id']
        data = await request.json()
        tag_ids = data.get('tag_ids', [])
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        for tag_id in tag_ids:
            cursor.execute('UPDATE modbus_datapoints SET group_id = ? WHERE id = ?', (group_id, tag_id))
        conn.commit()
        conn.close()
        return web.json_response({'success': True, 'message': '{} tag(s) assigned'.format(len(tag_ids))})
    except Exception as e:
        print("Error assigning tags to group: {}".format(str(e)))
        return web.json_response({'error': str(e)}, status=500)