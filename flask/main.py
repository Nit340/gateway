# main.py - Main entry point
from aiohttp import web
import asyncio
import sqlite3
import json

# Import modules
from database import init_database, DB_FILE
from general_config import get_config_handler, put_config_handler
from device_management import (
    get_all_devices, get_device_details, add_device, update_device,
    delete_device, test_device, disable_device, duplicate_device,
    get_device_packets, get_all_groups, add_group, assign_devices_to_group,
    scan_devices, get_scan_status, scan_wireless, pair_wireless,
    import_devices_csv, export_devices_csv
)
from tag_mapping import (
    get_tag_mapping_page,
    create_tag_mapping, update_tag_mapping, delete_tag_mapping, get_tag_mapping_details,
    get_available_devices, get_protocol_form,
    import_csv, export_csv, filter_tag_mappings,
    test_device_connection, validate_all_mappings, save_configuration
)
from websocket_handler import websocket_handler, device_websocket_handler
from utils import periodic_updates, device_status_updater

async def device_management_handler(request):
    """GET handler - device management page"""
    return web.Response(text='Device Management API is running. Use API endpoints.', content_type='text/html')

async def tag_mapping_handler(request):
    """GET handler - tag mapping page with embedded data"""
    return await get_tag_mapping_page(request)

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
                body { font-family: monospace; margin: 20px; }
                h1 { color: #333; }
                h2 { color: #555; margin-top: 30px; }
                table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f4f4f4; }
                tr:nth-child(even) { background-color: #f9f9f9; }
                .count { background-color: #4CAF50; color: white; padding: 2px 6px; border-radius: 3px; }
                .empty { color: #999; font-style: italic; }
            </style>
        </head>
        <body>
            <h1>Database Viewer: gateway_config.db</h1>
        """
        
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
                        if isinstance(cell, str) and (cell.startswith('{') or cell.startswith('[')):
                            # Try to prettify JSON
                            try:
                                parsed = json.loads(cell)
                                cell = json.dumps(parsed, indent=2)
                                cell = f"<pre>{cell}</pre>"
                            except:
                                pass
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
    
    # HTTP endpoints for configuration
    app.router.add_get('/api/general-configuration', get_config_handler)
    app.router.add_put('/api/general-configuration', put_config_handler)
    
    # Device Management endpoints
    app.router.add_get('/device-management', device_management_handler)
    
    # Device operations
    app.router.add_get('/api/device-management/devices', get_all_devices)
    app.router.add_post('/api/device-management/devices', add_device)
    app.router.add_get('/api/device-management/devices/{device_id}/details', get_device_details)
    app.router.add_put('/api/device-management/devices/{device_id}', update_device)
    app.router.add_delete('/api/device-management/devices/{device_id}', delete_device)
    app.router.add_post('/api/device-management/devices/{device_id}/test', test_device)
    app.router.add_post('/api/device-management/devices/{device_id}/disable', disable_device)
    app.router.add_post('/api/device-management/devices/{device_id}/duplicate', duplicate_device)
    app.router.add_get('/api/device-management/devices/{device_id}/packets', get_device_packets)
    
    # Group operations
    app.router.add_get('/api/device-management/groups', get_all_groups)
    app.router.add_post('/api/device-management/groups', add_group)
    app.router.add_post('/api/device-management/groups/{group_id}/assign-devices', assign_devices_to_group)
    
    # Scanning operations
    app.router.add_post('/api/device-management/scan', scan_devices)
    app.router.add_get('/api/device-management/scan/{scan_id}/status', get_scan_status)
    app.router.add_post('/api/device-management/wireless/scan', scan_wireless)
    app.router.add_post('/api/device-management/wireless/pair', pair_wireless)
    
    # Import/Export operations
    app.router.add_post('/api/device-management/import', import_devices_csv)
    app.router.add_post('/api/device-management/export', export_devices_csv)
    
    # Tag Mapping endpoints (NEW)
    app.router.add_get('/tag-mapping', tag_mapping_handler)
    
    # Tag Mapping API operations
    app.router.add_post('/api/tag-mapping', create_tag_mapping)
    app.router.add_put('/api/tag-mapping/{id}', update_tag_mapping)
    app.router.add_delete('/api/tag-mapping/{id}', delete_tag_mapping)
    app.router.add_get('/api/tag-mapping/{id}', get_tag_mapping_details)
    
    # Device and protocol information
    app.router.add_get('/api/tag-mapping/devices', get_available_devices)
    app.router.add_get('/api/tag-mapping/protocol-forms/{protocol}', get_protocol_form)
    
    # Import/Export operations
    app.router.add_post('/api/tag-mapping/import-csv', import_csv)
    app.router.add_get('/api/tag-mapping/export-csv', export_csv)
    
    # Filtering and search
    app.router.add_get('/api/tag-mapping/filter', filter_tag_mappings)
    
    # Device testing and validation
    app.router.add_post('/api/tag-mapping/devices/{device_id}/test', test_device_connection)
    app.router.add_post('/api/tag-mapping/validate-all', validate_all_mappings)
    
    # Configuration management
    app.router.add_put('/api/tag-mapping/save-config', save_configuration)
    
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
    
    print("Starting server on http://0.0.0.0:8080")
    print("Routes:")
    print("  GET  /db                         - Database viewer")
    print("  GET  /device-management          - Device management page")
    print("  GET  /tag-mapping                - Tag mapping page")
    print("  GET  /ws                         - WebSocket for real-time data")
    print("  GET  /ws/devices                 - WebSocket for device status")
    print("Press Ctrl+C to stop")
    
    web.run_app(create_app(), host='0.0.0.0', port=8080)