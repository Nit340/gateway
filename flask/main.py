# -*- coding: utf-8 -*-
# main.py - Main entry point
from aiohttp import web
import asyncio
import sqlite3
import json
import threading
import logging

# Pipeline client integration
try:
    from ilx_pipeline import PipelineClient, EventType, DataType
    PIPELINE_AVAILABLE = True
except ImportError:
    PIPELINE_AVAILABLE = False
    logging.warning("ilx_pipeline not available - pipeline features disabled")

# Global pipeline state
pipeline_state = {
    "client": None,
    "connected": False,
    "load_raw": None,
    "ws_clients": set(),
    "lock": threading.Lock(),
}

# Calibration storage (in-memory, persists while server runs)
calibration_data = {}  # legacy - calibration now stored in DB

# Import modules
from database import init_database, DB_FILE, get_database_stats
from general_config import get_config_handler, put_config_handler

from device_management import (
    get_all_devices, get_device_details, add_device, update_device,
    delete_device, test_device, disable_device, duplicate_device,
    get_all_groups, add_group, delete_group, assign_devices_to_group,
    export_devices_csv, import_devices_csv, download_csv_template, get_device_datapoints
)



from tag_mapping import (
    get_all_datapoints, add_modbus_datapoint, update_modbus_datapoint,
    delete_datapoint, get_available_devices, get_protocol_form,
    update_loadcell_datapoint
)
from websocket_handler import websocket_handler, device_websocket_handler
from utils import periodic_updates, device_status_updater
from mqtt_cloud import register_cloud_routes
from auth import register_auth_routes

async def database_viewer_handler(request):
    """GET handler - simple database viewer showing all tables and data"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute('PRAGMA foreign_keys = ON')  # Enable foreign key constraints
        cursor = conn.cursor()
        
        # Get all tables (including views)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' OR type='view' ORDER BY name")
        tables = cursor.fetchall()
        
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Database Viewer</title>
            <style>
                body { font-family: monospace; margin: 20px; background: #f5f5f5; }
                h1 { color: #333; }
                h2 { color: #555; margin-top: 30px; background: #fff; padding: 10px; border-left: 4px solid #4CAF50; }
                .view-header { border-left-color: #2196F3; }
                table { border-collapse: collapse; width: 100%; margin-bottom: 20px; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #4CAF50; color: white; font-weight: bold; }
                .view-th { background-color: #2196F3; }
                tr:nth-child(even) { background-color: #f9f9f9; }
                tr:hover { background-color: #f0f0f0; }
                .count { background-color: #4CAF50; color: white; padding: 4px 8px; border-radius: 3px; font-size: 0.9em; }
                .view-count { background-color: #2196F3; }
                .empty { color: #999; font-style: italic; padding: 20px; }
                pre { background: #f4f4f4; padding: 10px; border-radius: 4px; overflow-x: auto; }
                .stats { background: white; padding: 20px; margin-bottom: 20px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .stats h3 { margin-top: 0; color: #4CAF50; }
                .stat-item { display: inline-block; margin-right: 30px; }
                .stat-value { font-size: 24px; font-weight: bold; color: #4CAF50; }
                .stat-label { color: #666; font-size: 14px; }
                .view-badge { 
                    display: inline-block;
                    background: #2196F3; 
                    color: white; 
                    padding: 2px 8px; 
                    border-radius: 3px; 
                    font-size: 12px;
                    margin-left: 10px;
                    font-weight: normal;
                }
                .json-cell { max-width: 500px; overflow-x: auto; }
                .json-cell pre { margin: 0; background: #f8f8f8; }
            </style>
        </head>
        <body>
            <h1> Database Viewer: gateway_config.db</h1>
        """
        
        # Add statistics
        stats = get_database_stats()
        html_content += """
            <div class="stats">
                <h3>Database Statistics</h3>
        """
        
        for key, value in stats.items():
            if key != 'views':
                label = key.replace('_', ' ').title()
                html_content += """
                    <div class="stat-item">
                        <div class="stat-value">{value}</div>
                        <div class="stat-label">{label}</div>
                    </div>
                """.format(value=value, label=label)
        
        # Add view stats if available
        if 'views' in stats:
            for vname, vinfo in stats['views'].items():
                if vinfo['exists']:
                    html_content += """
                    <div class="stat-item">
                        <div class="stat-value" style="color: #2196F3;">{enabled_devices}</div>
                        <div class="stat-label">Devices in View</div>
                    </div>
                    """.format(enabled_devices=vinfo['enabled_devices'])
        
        html_content += "</div>"
        
        for table in tables:
            table_name = table[0]
            
            # Check if it's a view
            cursor.execute("SELECT type FROM sqlite_master WHERE name = ?", (table_name,))
            object_type = cursor.fetchone()[0]
            is_view = (object_type == 'view')
            
            # Get table/view schema
            cursor.execute("PRAGMA table_info({table_name})".format(table_name=table_name))
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # For the modbus view render one combined JSON row per device via Python helper
            if is_view and table_name == 'modbus_device_config_view':
                from database import get_modbus_device_config_view
                view_data = get_modbus_device_config_view()
                column_names = ['device_id', 'device_name', 'device_type', 'config']
                rows = [
                    (r['device_id'], r['device_name'], r['device_type'], json.dumps(r['config'], indent=2))
                    for r in view_data
                ]
            else:
                try:
                    cursor.execute("SELECT * FROM {table_name}".format(table_name=table_name))
                    rows = cursor.fetchall()
                except Exception as tbl_err:
                    rows = []
                    print("DB viewer: could not query {}: {}".format(table_name, tbl_err))
            
            # Header with view badge if it's a view
            header_class = "view-header" if is_view else ""
            count_class = "view-count" if is_view else ""
            view_badge = '<span class="view-badge">VIEW</span>' if is_view else ''
            
            html_content += """
            <h2 class="{header_class}">{table_name} {view_badge} <span class="count {count_class}">{row_count} rows</span></h2>
            """.format(header_class=header_class, table_name=table_name, view_badge=view_badge, count_class=count_class, row_count=len(rows))
            
            if rows:
                # Table header with different color for views
                th_class = "view-th" if is_view else ""
                html_content += """
                <table>
                    <tr>
                        {th_cells}
                    </tr>
                """.format(th_cells=''.join(['<th class="{th_class}">{col}</th>'.format(th_class=th_class, col=col) for col in column_names]))
                
                for row in rows:
                    html_content += "<tr>"
                    for i, cell in enumerate(row):
                        # Check if this is the config column (JSON) in the view
                        if is_view and column_names[i] == 'config' and isinstance(cell, str):
                            try:
                                # Pretty print JSON
                                json_obj = json.loads(cell)
                                formatted_json = json.dumps(json_obj, indent=2)
                                html_content += '<td class="json-cell"><pre>{formatted_json}</pre></td>'.format(formatted_json=formatted_json)
                            except:
                                # If not valid JSON, display as is
                                cell_str = str(cell)
                                if len(cell_str) > 100:
                                    cell_str = cell_str[:100] + "..."
                                html_content += "<td>{cell_str}</td>".format(cell_str=cell_str)
                        else:
                            cell_str = str(cell)
                            if len(cell_str) > 100:
                                cell_str = cell_str[:100] + "..."
                            html_content += "<td>{cell_str}</td>".format(cell_str=cell_str)
                    html_content += "</tr>"
                
                html_content += "</table>"
                

            else:
                html_content += "<p class='empty'>Table/View is empty</p>"
        
        html_content += """
        </body>
        </html>
        """
        
        conn.close()
        return web.Response(text=html_content, content_type='text/html')
        
    except Exception as e:
        error_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Database Error</title></head>
        <body>
            <h1>Database Error</h1>
            <p>Error: {error}</p>
        </body>
        </html>
        """.format(error=str(e))
        return web.Response(text=error_html, content_type='text/html')

async def api_docs_handler(request):
    """API Documentation"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Gateway Configuration API Documentation</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            h1 { color: #333; }
            h2 { color: #4CAF50; margin-top: 30px; }
            h3 { color: #666; }
            .endpoint { background: white; padding: 20px; margin: 10px 0; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .method { display: inline-block; padding: 4px 8px; border-radius: 3px; font-weight: bold; color: white; margin-right: 10px; }
            .get { background: #2196F3; }
            .post { background: #4CAF50; }
            .put { background: #FF9800; }
            .delete { background: #f44336; }
            .path { font-family: monospace; background: #f4f4f4; padding: 4px 8px; border-radius: 3px; }
            pre { background: #f4f4f4; padding: 15px; border-radius: 4px; overflow-x: auto; }
            code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <h1> Gateway Configuration API</h1>
        <p>RESTful API for managing gateway configuration, devices, and datapoints.</p>
        
        <h2> General Configuration</h2>
        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/api/general-configuration</span>
            <p>Get general gateway configuration (gateway identity, date/time, heartbeat)</p>
        </div>
        
        <div class="endpoint">
            <span class="method put">PUT</span>
            <span class="path">/api/general-configuration</span>
            <p>Update general gateway configuration</p>
        </div>
        
        <h2> Device Management</h2>
        
        <h3>Device Operations</h3>
        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/api/devices</span>
            <p>Get all devices (Modbus TCP, Modbus RTU, Loadcell)</p>
        </div>
        
        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/api/devices</span>
            <p>Add a new device</p>
            <pre>{
  "type": "modbus|loadcell",
  "name": "Device Name",
  "protocol": "modbus-tcp|modbus-rtu|loadcell",
  "group": "Group Name",
  "config": {
    // For Modbus TCP:
    "ip_address": "192.168.1.100",
    "port": 502,
    "slave_id": 1,
    // For Modbus RTU:
    "serial_port": "/dev/ttymxc2",
    "baud_rate": 9600,
    "parity": "N",
    // For Loadcell:
    "device_path": "/dev/spidev0.0",
    "capacity": 40000.0
  }
}</pre>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/api/devices/{device_id}/details</span>
            <p>Get device details</p>
        </div>
        
        <div class="endpoint">
            <span class="method put">PUT</span>
            <span class="path">/api/devices/{device_id}</span>
            <p>Update device configuration</p>
        </div>
        
        <div class="endpoint">
            <span class="method delete">DELETE</span>
            <span class="path">/api/devices/{device_id}</span>
            <p>Delete a device</p>
        </div>
        
        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/api/devices/{device_id}/test</span>
            <p>Test device connection</p>
        </div>
        
        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/api/devices/{device_id}/disable</span>
            <p>Enable/Disable device</p>
        </div>
        
        <h3>Group Operations</h3>
        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/api/groups</span>
            <p>Get all device groups</p>
        </div>
        
        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/api/groups</span>
            <p>Add a new group</p>
        </div>
        
        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/api/groups/{group_id}/assign-devices</span>
            <p>Assign devices to a group</p>
        </div>
        
        <h2> Datapoint Management</h2>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/api/datapoints</span>
            <p>Get all datapoints (Modbus + Loadcell)</p>
        </div>
        
        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/api/datapoints/modbus</span>
            <p>Add a Modbus datapoint</p>
            <pre>{
  "device_id": "1",
  "tag_name": "temperature",
  "register_address": 100,
  "register_type": "holding",
  "data_type": "int16",
  "scale_factor": 0.1,
  "offset": 0,
  "unit": "degC"
}</pre>
        </div>
        
        <div class="endpoint">
            <span class="method put">PUT</span>
            <span class="path">/api/datapoints/modbus/{id}</span>
            <p>Update Modbus datapoint</p>
        </div>
        
        <div class="endpoint">
            <span class="method delete">DELETE</span>
            <span class="path">/api/datapoints/{id}</span>
            <p>Delete datapoint (query param: ?type=modbus|loadcell)</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/api/datapoints/devices</span>
            <p>Get available devices for creating datapoints</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/api/datapoints/protocol-form/{protocol}</span>
            <p>Get form schema for creating datapoint by protocol</p>
        </div>
        
        <h2> WebSocket Endpoints</h2>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/ws</span>
            <p>WebSocket for real-time updates (time, date)</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/ws/devices</span>
            <p>WebSocket for device status updates</p>
        </div>
        
        <h2> Database Viewer</h2>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/db</span>
            <p>View all database tables and data</p>
        </div>
        
        <h2> Notes</h2>
        <ul>
            <li><strong>Modbus Devices:</strong> Support both TCP and RTU. Device type determined by protocol.</li>
            <li><strong>Loadcell Devices:</strong> Automatically create 'load' and 'capacity' datapoints upon creation.</li>
            <li><strong>Services:</strong> Devices are linked to services (modbus or loadcell) automatically.</li>
            <li><strong>Groups:</strong> Dynamic groups can be created by users. Devices can be assigned to groups.</li>
        </ul>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

async def start_background_tasks(app):
    """Start background tasks"""
    app['periodic_updates'] = asyncio.ensure_future(periodic_updates())
    app['device_status_updater'] = asyncio.ensure_future(device_status_updater())

async def cleanup_background_tasks(app):
    """Cleanup background tasks"""
    app['periodic_updates'].cancel()
    await app['periodic_updates']
    app['device_status_updater'].cancel()
    await app['device_status_updater']

# ==================== PIPELINE HANDLERS ====================

async def pipeline_connect_handler(request):
    """POST /api/pipeline/connect - Connect to pipeline and start listening for all datapoints"""
    global pipeline_state
    try:
        if not PIPELINE_AVAILABLE:
            return web.json_response({"success": False, "error": "ilx_pipeline library not found - check server logs"})

        with pipeline_state["lock"]:
            if pipeline_state["connected"] and pipeline_state["client"]:
                return web.json_response({"success": True, "message": "Already connected"})

        try:
            body = await request.json()
        except Exception:
            body = {}

        host = body.get("host", "127.0.0.1")
        port = body.get("port", 7000)

        def _run_pipeline():
            try:
                client = PipelineClient("craneiq_loadcell_listener", host, port, 1000, 10)
                client.set_connection_timeout(5)

                def on_event(event):
                    try:
                        if event.event_type == EventType.PIPELINE_CONNECTED:
                            with pipeline_state["lock"]:
                                pipeline_state["connected"] = True
                        elif event.event_type == EventType.PIPELINE_OFFLINE:
                            with pipeline_state["lock"]:
                                pipeline_state["connected"] = False
                        elif event.event_type == EventType.RECEIVE_DONE:
                            dp = event.datapoint_name
                            try:
                                dtype = client.get_datapoint_type(dp)
                                if dtype == DataType.FLOAT:
                                    val = client.get_datapoint_float(dp)
                                elif dtype == DataType.DOUBLE:
                                    val = client.get_datapoint_double(dp)
                                elif dtype == DataType.INT:
                                    val = client.get_datapoint_integer(dp)
                                elif dtype == DataType.LONG:
                                    val = client.get_datapoint_long(dp)
                                elif dtype == DataType.BOOL:
                                    val = client.get_datapoint_boolean(dp)
                                else:
                                    val = client.get_datapoint_string(dp)
                                msg = json.dumps({"datapoint": dp, "value": val})
                                for ws in list(pipeline_state["ws_clients"]):
                                    try:
                                        asyncio.run_coroutine_threadsafe(ws.send_str(msg), ws._loop)
                                    except Exception:
                                        pass
                            except Exception as e:
                                logging.error("Error reading datapoint %s: %s", dp, e)
                    except Exception as e:
                        logging.error("Pipeline event error: %s", e)

                client.set_event_callback(on_event)
                client.start()
                ok = client.wait_until_connected(5000)
                with pipeline_state["lock"]:
                    pipeline_state["client"] = client
                    pipeline_state["connected"] = ok
            except Exception as e:
                logging.error("Pipeline thread error: %s", e)
                with pipeline_state["lock"]:
                    pipeline_state["connected"] = False

        thread = threading.Thread(target=_run_pipeline, daemon=True)
        thread.start()
        thread.join(timeout=7)

        with pipeline_state["lock"]:
            ok = pipeline_state["connected"]

        if ok:
            return web.json_response({"success": True, "message": "Connected to pipeline"})
        else:
            return web.json_response({"success": False, "error": "Could not connect to pipeline server at " + host + ":" + str(port)})

    except Exception as e:
        logging.error("pipeline_connect_handler fatal: %s", e)
        return web.json_response({"success": False, "error": str(e)})


async def pipeline_disconnect_handler(request):
    """POST /api/pipeline/disconnect - Disconnect from pipeline"""
    global pipeline_state
    with pipeline_state["lock"]:
        client = pipeline_state.get("client")
        if client:
            try:
                client.stop()
            except Exception:
                pass
        pipeline_state["client"] = None
        pipeline_state["connected"] = False
        pipeline_state["load_raw"] = None
    return web.json_response({"success": True, "message": "Disconnected"})


async def pipeline_status_handler(request):
    """GET /api/pipeline/status - Return current pipeline connection status and latest load_raw"""
    with pipeline_state["lock"]:
        return web.json_response({
            "connected": pipeline_state["connected"],
            "load_raw": pipeline_state["load_raw"],
        })


async def pipeline_loadraw_ws_handler(request):
    """WebSocket /ws/pipeline/load_raw - Stream live load_raw values to browser"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ws._loop = asyncio.get_event_loop()

    pipeline_state["ws_clients"].add(ws)
    try:
        async for msg in ws:
            pass  # We only send, not receive
    finally:
        pipeline_state["ws_clients"].discard(ws)
    return ws


async def pipeline_loadcell_devices_handler(request):
    """GET /api/pipeline/loadcell-devices - Return all enabled loadcell devices from DB"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, device_path, channel, tare_offset, known_weight, known_weight_raw,
                   pipeline_server, pipeline_port, unit, capacity, enabled
            FROM loadcell_device WHERE enabled = 1
        ''')
        rows = cursor.fetchall()
        conn.close()
        devices = [dict(r) for r in rows]
        return web.json_response({"devices": devices})
    except Exception as e:
        logging.error("loadcell_devices error: %s", e)
        return web.json_response({"devices": [], "error": str(e)})


async def pipeline_calibration_get_handler(request):
    """GET /api/pipeline/calibration - Return calibration for a device"""
    try:
        device_id = request.rel_url.query.get('device_id')
        if not device_id:
            return web.json_response({"error": "device_id required"}, status=400)
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT tare_offset, known_weight, known_weight_raw FROM loadcell_device WHERE id = ?', (device_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return web.json_response({"error": "device not found"}, status=404)
        return web.json_response(dict(row))
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def pipeline_calibration_post_handler(request):
    """POST /api/pipeline/calibration - Save tare_offset, known_weight, known_weight_raw to DB"""
    try:
        body = await request.json()
        device_id = body.get("device_id")
        tare_offset = body.get("tare_offset")
        known_weight = body.get("known_weight")
        known_weight_raw = body.get("known_weight_raw")

        if not device_id:
            return web.json_response({"success": False, "error": "device_id required"})

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE loadcell_device
            SET tare_offset = ?, known_weight = ?, known_weight_raw = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (tare_offset, known_weight, known_weight_raw, device_id))
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        if affected == 0:
            return web.json_response({"success": False, "error": "Device not found"})
        return web.json_response({"success": True})
    except Exception as e:
        logging.error("calibration save error: %s", e)
        return web.json_response({"success": False, "error": str(e)})


def create_app():
    """Create and configure the aiohttp application"""
    app = web.Application()
    
    # Documentation
    app.router.add_get('/', api_docs_handler)
    app.router.add_get('/docs', api_docs_handler)
    
    # General Configuration endpoints
    app.router.add_get('/api/general-configuration', get_config_handler)
    app.router.add_put('/api/general-configuration', put_config_handler)
    
    # Authentication endpoints
    register_auth_routes(app)

    # Cloud Integration endpoints
    register_cloud_routes(app)

    # Device Management endpoints
    app.router.add_get('/api/devices', get_all_devices)
    app.router.add_post('/api/devices', add_device)
    app.router.add_get('/api/devices/{device_id}/details', get_device_details)
    app.router.add_put('/api/devices/{device_id}', update_device)
    app.router.add_delete('/api/devices/{device_id}', delete_device)
    app.router.add_post('/api/devices/{device_id}/test', test_device)
    app.router.add_post('/api/devices/{device_id}/disable', disable_device)
    app.router.add_post('/api/devices/{device_id}/duplicate', duplicate_device)
    
    # Import/Export endpoints - ADD THESE NEW ROUTES
    app.router.add_get('/api/devices/export/csv', export_devices_csv)
    app.router.add_post('/api/devices/import/csv', import_devices_csv)
    app.router.add_get('/api/devices/template/csv', download_csv_template)
    
    # Group operations
    app.router.add_get('/api/groups', get_all_groups)
    app.router.add_post('/api/groups', add_group)
    app.router.add_delete('/api/groups/{group_id}', delete_group)
    app.router.add_post('/api/groups/{group_id}/assign-devices', assign_devices_to_group)
    
    # Datapoint Management endpoints
    app.router.add_get('/api/datapoints', get_all_datapoints)
    app.router.add_post('/api/datapoints/modbus', add_modbus_datapoint)
    app.router.add_put('/api/datapoints/modbus/{id}', update_modbus_datapoint)
    app.router.add_put('/api/datapoints/loadcell/{id}', update_loadcell_datapoint)
    app.router.add_delete('/api/datapoints/{id}', delete_datapoint)
    app.router.add_get('/api/datapoints/devices', get_available_devices)
    app.router.add_get('/api/datapoints/protocol-form/{protocol}', get_protocol_form)
    app.router.add_get('/api/devices/{device_id}/datapoints', get_device_datapoints)
    # Database Viewer route
    app.router.add_get('/db', database_viewer_handler)

    # WebSocket for real-time data
    app.router.add_get('/ws', websocket_handler)
    
    # WebSocket for device status updates
    app.router.add_get('/ws/devices', device_websocket_handler)

    # Pipeline endpoints for Load Cell live data
    app.router.add_post('/api/pipeline/connect', pipeline_connect_handler)
    app.router.add_post('/api/pipeline/disconnect', pipeline_disconnect_handler)
    app.router.add_get('/api/pipeline/status', pipeline_status_handler)
    app.router.add_get('/ws/pipeline/load_raw', pipeline_loadraw_ws_handler)
    app.router.add_get('/api/pipeline/loadcell-devices', pipeline_loadcell_devices_handler)
    app.router.add_get('/api/pipeline/calibration', pipeline_calibration_get_handler)
    app.router.add_post('/api/pipeline/calibration', pipeline_calibration_post_handler)
    
    # Background tasks
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    
    return app

if __name__ == '__main__':
    # Initialize database
    print("Initializing database...")
    init_database()
    
    print("\n" + "="*60)
    print(" Gateway Configuration Server Starting")
    print("="*60)
    print("\n Server: http://0.0.0.0:8080")
    print("\n Main Routes:")
    print("  GET  /                          - API Documentation")
    print("  GET  /docs                      - API Documentation")
    print("  GET  /db                        - Database viewer")
    print("\n Device Management:")
    print("  GET  /api/devices               - Get all devices")
    print("  POST /api/devices               - Add device")
    print("  GET  /api/devices/{id}/details  - Get device details")
    print("  PUT  /api/devices/{id}          - Update device")
    print("  DEL  /api/devices/{id}          - Delete device")
    print("\n  Datapoint Management:")
    print("  GET  /api/datapoints            - Get all datapoints")
    print("  POST /api/datapoints/modbus     - Add Modbus datapoint")
    print("\n WebSocket:")
    print("  GET  /ws                        - Real-time updates")
    print("  GET  /ws/devices                - Device status")
    print("\n" + "="*60)
    print("Press Ctrl+C to stop")
    print("="*60 + "\n")
    
    web.run_app(create_app(), host='0.0.0.0', port=8082)