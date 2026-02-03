# main.py - Main entry point
from aiohttp import web
import asyncio
import sqlite3
import json

# Import modules
from database import init_database, DB_FILE, get_database_stats
from general_config import get_config_handler, put_config_handler
from device_management import (
    get_all_devices, get_device_details, add_device, update_device,
    delete_device, test_device, disable_device,
    get_all_groups, add_group, assign_devices_to_group
)
from tag_mapping import (
    get_all_datapoints, add_modbus_datapoint, update_modbus_datapoint,
    delete_datapoint, get_available_devices, get_protocol_form
)
from websocket_handler import websocket_handler, device_websocket_handler
from utils import periodic_updates, device_status_updater

async def database_viewer_handler(request):
    """GET handler - simple database viewer showing all tables and data"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
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
                table { border-collapse: collapse; width: 100%; margin-bottom: 20px; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #4CAF50; color: white; font-weight: bold; }
                tr:nth-child(even) { background-color: #f9f9f9; }
                tr:hover { background-color: #f0f0f0; }
                .count { background-color: #4CAF50; color: white; padding: 4px 8px; border-radius: 3px; font-size: 0.9em; }
                .empty { color: #999; font-style: italic; padding: 20px; }
                pre { background: #f4f4f4; padding: 10px; border-radius: 4px; overflow-x: auto; }
                .stats { background: white; padding: 20px; margin-bottom: 20px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .stats h3 { margin-top: 0; color: #4CAF50; }
                .stat-item { display: inline-block; margin-right: 30px; }
                .stat-value { font-size: 24px; font-weight: bold; color: #4CAF50; }
                .stat-label { color: #666; font-size: 14px; }
            </style>
        </head>
        <body>
            <h1>📊 Database Viewer: gateway_config.db</h1>
        """
        
        # Add statistics
        stats = get_database_stats()
        html_content += """
            <div class="stats">
                <h3>Database Statistics</h3>
        """
        
        for key, value in stats.items():
            label = key.replace('_', ' ').title()
            html_content += f"""
                <div class="stat-item">
                    <div class="stat-value">{value}</div>
                    <div class="stat-label">{label}</div>
                </div>
            """
        
        html_content += "</div>"
        
        for table in tables:
            table_name = table[0]
            
            # Get table schema
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # Get table data
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            
            html_content += f"""
            <h2>{table_name} <span class="count">{len(rows)} rows</span></h2>
            """
            
            if rows:
                html_content += f"""
                <table>
                    <tr>
                        {''.join([f'<th>{col}</th>' for col in column_names])}
                    </tr>
                """
                
                for row in rows:
                    html_content += "<tr>"
                    for cell in row:
                        if isinstance(cell, str) and len(cell) > 100:
                            # Truncate long strings
                            cell = cell[:100] + "..."
                        html_content += f"<td>{cell}</td>"
                    html_content += "</tr>"
                
                html_content += "</table>"
            else:
                html_content += "<p class='empty'>Table is empty</p>"
        
        html_content += """
        </body>
        </html>
        """
        
        conn.close()
        return web.Response(text=html_content, content_type='text/html')
        
    except Exception as e:
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Database Error</title></head>
        <body>
            <h1>Database Error</h1>
            <p>Error: {str(e)}</p>
        </body>
        </html>
        """
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
        <h1>🚀 Gateway Configuration API</h1>
        <p>RESTful API for managing gateway configuration, devices, and datapoints.</p>
        
        <h2>📋 General Configuration</h2>
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
        
        <h2>🔌 Device Management</h2>
        
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
        
        <h2>🏷️ Datapoint Management</h2>
        
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
  "unit": "°C"
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
        
        <h2>🔄 WebSocket Endpoints</h2>
        
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
        
        <h2>🗄️ Database Viewer</h2>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/db</span>
            <p>View all database tables and data</p>
        </div>
        
        <h2>📝 Notes</h2>
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

def create_app():
    """Create and configure the aiohttp application"""
    app = web.Application()
    
    # Documentation
    app.router.add_get('/', api_docs_handler)
    app.router.add_get('/docs', api_docs_handler)
    
    # General Configuration endpoints
    app.router.add_get('/api/general-configuration', get_config_handler)
    app.router.add_put('/api/general-configuration', put_config_handler)
    
    # Device Management endpoints
    app.router.add_get('/api/devices', get_all_devices)
    app.router.add_post('/api/devices', add_device)
    app.router.add_get('/api/devices/{device_id}/details', get_device_details)
    app.router.add_put('/api/devices/{device_id}', update_device)
    app.router.add_delete('/api/devices/{device_id}', delete_device)
    app.router.add_post('/api/devices/{device_id}/test', test_device)
    app.router.add_post('/api/devices/{device_id}/disable', disable_device)
    
    # Group operations
    app.router.add_get('/api/groups', get_all_groups)
    app.router.add_post('/api/groups', add_group)
    app.router.add_post('/api/groups/{group_id}/assign-devices', assign_devices_to_group)
    
    # Datapoint Management endpoints
    app.router.add_get('/api/datapoints', get_all_datapoints)
    app.router.add_post('/api/datapoints/modbus', add_modbus_datapoint)
    app.router.add_put('/api/datapoints/modbus/{id}', update_modbus_datapoint)
    app.router.add_delete('/api/datapoints/{id}', delete_datapoint)
    app.router.add_get('/api/datapoints/devices', get_available_devices)
    app.router.add_get('/api/datapoints/protocol-form/{protocol}', get_protocol_form)
    
    # Database Viewer route
    app.router.add_get('/db', database_viewer_handler)
    
    # WebSocket for real-time data
    app.router.add_get('/ws', websocket_handler)
    
    # WebSocket for device status updates
    app.router.add_get('/ws/devices', device_websocket_handler)
    
    # Background tasks
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    
    return app

if __name__ == '__main__':
    # Initialize database
    print("Initializing database...")
    init_database()
    
    print("\n" + "="*60)
    print("🚀 Gateway Configuration Server Starting")
    print("="*60)
    print("\n📍 Server: http://0.0.0.0:8080")
    print("\n📚 Main Routes:")
    print("  GET  /                          - API Documentation")
    print("  GET  /docs                      - API Documentation")
    print("  GET  /db                        - Database viewer")
    print("\n🔌 Device Management:")
    print("  GET  /api/devices               - Get all devices")
    print("  POST /api/devices               - Add device")
    print("  GET  /api/devices/{id}/details  - Get device details")
    print("  PUT  /api/devices/{id}          - Update device")
    print("  DEL  /api/devices/{id}          - Delete device")
    print("\n🏷️  Datapoint Management:")
    print("  GET  /api/datapoints            - Get all datapoints")
    print("  POST /api/datapoints/modbus     - Add Modbus datapoint")
    print("\n🔄 WebSocket:")
    print("  GET  /ws                        - Real-time updates")
    print("  GET  /ws/devices                - Device status")
    print("\n" + "="*60)
    print("Press Ctrl+C to stop")
    print("="*60 + "\n")
    
    web.run_app(create_app(), host='0.0.0.0', port=8080)