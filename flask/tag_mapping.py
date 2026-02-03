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
        cursor = conn.cursor()
        
        datapoints = []
        
        # Get Modbus datapoints
        cursor.execute('''
            SELECT md.id, md.device_id, md.name, md.register_address, md.register_type,
                   md.data_type, md.byte_order, md.word_order, md.scale_factor, md.offset,
                   md.unit, md.description, md.enabled,
                   m.name as device_name, m.device_type
            FROM modbus_datapoints md
            JOIN modbus_device m ON md.device_id = m.id
            ORDER BY md.device_id, md.name
        ''')
        
        for row in cursor.fetchall():
            datapoints.append({
                'id': row[0],
                'device_id': row[1],
                'device_name': row[13],
                'device_type': f"Modbus {row[14].upper()}",
                'tag_name': row[2],
                'register_address': row[3],
                'register_type': row[4],
                'data_type': row[5],
                'byte_order': row[6],
                'word_order': row[7],
                'scale_factor': row[8],
                'offset': row[9],
                'unit': row[10],
                'description': row[11],
                'enabled': bool(row[12])
            })
        
        # Get Loadcell datapoints
        cursor.execute('''
            SELECT ld.id, ld.device_id, ld.name,
                   l.name as device_name
            FROM loadcell_datapoints ld
            JOIN loadcell_device l ON ld.device_id = l.id
            ORDER BY ld.device_id, ld.name
        ''')
        
        for row in cursor.fetchall():
            datapoints.append({
                'id': row[0],
                'device_id': row[1],
                'device_name': row[3],
                'device_type': 'Loadcell',
                'tag_name': row[2],
                'unit': 'g' if row[2] == 'load' else 'g',
                'description': f"Loadcell {row[2]}",
                'enabled': True
            })
        
        conn.close()
        return web.json_response({'datapoints': datapoints})
        
    except Exception as e:
        print(f"Error getting datapoints: {e}")
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# ADD MODBUS DATAPOINT
# ============================================================================

async def add_modbus_datapoint(request):
    """POST - Add Modbus datapoint"""
    try:
        data = await request.json()
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO modbus_datapoints (
                device_id, name, register_address, register_type, data_type,
                byte_order, word_order, scale_factor, offset, unit, description, enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('device_id'),
            data.get('tag_name'),
            data.get('register_address'),
            data.get('register_type', 'holding'),
            data.get('data_type', 'int16'),
            data.get('byte_order', 'big'),
            data.get('word_order', 'big'),
            data.get('scale_factor', 1.0),
            data.get('offset', 0.0),
            data.get('unit', ''),
            data.get('description', ''),
            data.get('enabled', True)
        ))
        
        datapoint_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return web.json_response({
            'success': True,
            'message': 'Modbus datapoint added successfully',
            'id': datapoint_id
        })
        
    except Exception as e:
        print(f"Error adding modbus datapoint: {e}")
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# UPDATE MODBUS DATAPOINT
# ============================================================================

async def update_modbus_datapoint(request):
    """PUT - Update Modbus datapoint"""
    try:
        datapoint_id = request.match_info['id']
        data = await request.json()
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        update_fields = []
        values = []
        
        if 'tag_name' in data:
            update_fields.append('name = ?')
            values.append(data['tag_name'])
        if 'register_address' in data:
            update_fields.append('register_address = ?')
            values.append(data['register_address'])
        if 'register_type' in data:
            update_fields.append('register_type = ?')
            values.append(data['register_type'])
        if 'data_type' in data:
            update_fields.append('data_type = ?')
            values.append(data['data_type'])
        if 'byte_order' in data:
            update_fields.append('byte_order = ?')
            values.append(data['byte_order'])
        if 'word_order' in data:
            update_fields.append('word_order = ?')
            values.append(data['word_order'])
        if 'scale_factor' in data:
            update_fields.append('scale_factor = ?')
            values.append(data['scale_factor'])
        if 'offset' in data:
            update_fields.append('offset = ?')
            values.append(data['offset'])
        if 'unit' in data:
            update_fields.append('unit = ?')
            values.append(data['unit'])
        if 'description' in data:
            update_fields.append('description = ?')
            values.append(data['description'])
        if 'enabled' in data:
            update_fields.append('enabled = ?')
            values.append(data['enabled'])
        
        values.append(datapoint_id)
        
        query = f'''
            UPDATE modbus_datapoints 
            SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        '''
        
        cursor.execute(query, values)
        conn.commit()
        conn.close()
        
        return web.json_response({
            'success': True,
            'message': 'Modbus datapoint updated successfully'
        })
        
    except Exception as e:
        print(f"Error updating modbus datapoint: {e}")
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# DELETE DATAPOINT
# ============================================================================

async def delete_datapoint(request):
    """DELETE - Delete datapoint"""
    try:
        datapoint_id = request.match_info['id']
        datapoint_type = request.query.get('type', 'modbus')
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        if datapoint_type == 'loadcell':
            # Don't allow deleting auto-created loadcell datapoints
            cursor.execute('SELECT name FROM loadcell_datapoints WHERE id = ?', (datapoint_id,))
            row = cursor.fetchone()
            if row and row[0] in ['load', 'capacity']:
                conn.close()
                return web.json_response({
                    'success': False,
                    'message': 'Cannot delete auto-created loadcell datapoints'
                }, status=400)
            
            cursor.execute('DELETE FROM loadcell_datapoints WHERE id = ?', (datapoint_id,))
        else:
            cursor.execute('DELETE FROM modbus_datapoints WHERE id = ?', (datapoint_id,))
        
        conn.commit()
        conn.close()
        
        return web.json_response({
            'success': True,
            'message': 'Datapoint deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting datapoint: {e}")
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# GET AVAILABLE DEVICES FOR DATAPOINT CREATION
# ============================================================================

async def get_available_devices(request):
    """GET devices available for creating datapoints"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        devices = []
        
        # Get Modbus devices
        cursor.execute('''
            SELECT id, name, device_type FROM modbus_device ORDER BY name
        ''')
        
        for row in cursor.fetchall():
            devices.append({
                'id': row[0],
                'name': row[1],
                'type': f"Modbus {row[2].upper()}",
                'protocol': f"modbus-{row[2]}"
            })
        
        # Get Loadcell devices
        cursor.execute('''
            SELECT id, name FROM loadcell_device ORDER BY name
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
        print(f"Error getting available devices: {e}")
        return web.json_response({'error': str(e)}, status=500)

# ============================================================================
# GET PROTOCOL FORM SCHEMA
# ============================================================================

async def get_protocol_form(request):
    """GET form schema for creating datapoint by protocol"""
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
                        'required': True
                    },
                    {
                        'name': 'register_address',
                        'label': 'Register Address',
                        'type': 'number',
                        'required': True
                    },
                    {
                        'name': 'register_type',
                        'label': 'Register Type',
                        'type': 'select',
                        'options': ['holding', 'input', 'coil', 'discrete'],
                        'default': 'holding'
                    },
                    {
                        'name': 'data_type',
                        'label': 'Data Type',
                        'type': 'select',
                        'options': ['int16', 'uint16', 'int32', 'uint32', 'float32', 'bool'],
                        'default': 'int16'
                    },
                    {
                        'name': 'byte_order',
                        'label': 'Byte Order',
                        'type': 'select',
                        'options': ['big', 'little'],
                        'default': 'big'
                    },
                    {
                        'name': 'word_order',
                        'label': 'Word Order',
                        'type': 'select',
                        'options': ['big', 'little'],
                        'default': 'big'
                    },
                    {
                        'name': 'scale_factor',
                        'label': 'Scale Factor',
                        'type': 'number',
                        'default': 1.0
                    },
                    {
                        'name': 'offset',
                        'label': 'Offset',
                        'type': 'number',
                        'default': 0.0
                    },
                    {
                        'name': 'unit',
                        'label': 'Unit',
                        'type': 'text'
                    },
                    {
                        'name': 'description',
                        'label': 'Description',
                        'type': 'textarea'
                    }
                ]
            }
        elif protocol == 'loadcell':
            form_schema = {
                'protocol': protocol,
                'message': 'Loadcell datapoints (load, capacity) are auto-created when device is added.',
                'fields': []
            }
        else:
            return web.json_response({
                'error': 'Unknown protocol'
            }, status=400)
        
        return web.json_response(form_schema)
        
    except Exception as e:
        print(f"Error getting protocol form: {e}")
        return web.json_response({'error': str(e)}, status=500)