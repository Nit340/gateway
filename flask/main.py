# -*- coding: utf-8 -*-
# main.py - Main entry point
from aiohttp import web
import asyncio
import sqlite3
import json
import logging

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

# All pipeline state + handlers live ONLY in pipeline.py.
# main.py just calls register_pipeline_routes() - no duplicate pipeline_state here.
from pipeline import register_pipeline_routes


async def database_viewer_handler(request):
    """GET handler - simple database viewer showing all tables and data"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()
        
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
                    display: inline-block; background: #2196F3; color: white;
                    padding: 2px 8px; border-radius: 3px; font-size: 12px;
                    margin-left: 10px; font-weight: normal;
                }
                .json-cell { max-width: 500px; overflow-x: auto; }
                .json-cell pre { margin: 0; background: #f8f8f8; }
            </style>
        </head>
        <body>
            <h1> Database Viewer: gateway_config.db</h1>
        """
        
        stats = get_database_stats()
        html_content += '<div class="stats"><h3>Database Statistics</h3>'
        
        for key, value in stats.items():
            if key != 'views':
                label = key.replace('_', ' ').title()
                html_content += """
                    <div class="stat-item">
                        <div class="stat-value">{value}</div>
                        <div class="stat-label">{label}</div>
                    </div>
                """.format(value=value, label=label)
        
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
            
            cursor.execute("SELECT type FROM sqlite_master WHERE name = ?", (table_name,))
            object_type = cursor.fetchone()[0]
            is_view = (object_type == 'view')
            
            cursor.execute("PRAGMA table_info({table_name})".format(table_name=table_name))
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
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
            
            header_class = "view-header" if is_view else ""
            count_class  = "view-count"  if is_view else ""
            view_badge   = '<span class="view-badge">VIEW</span>' if is_view else ''
            
            html_content += """
            <h2 class="{header_class}">{table_name} {view_badge}
                <span class="count {count_class}">{row_count} rows</span>
            </h2>
            """.format(header_class=header_class, table_name=table_name,
                       view_badge=view_badge, count_class=count_class, row_count=len(rows))
            
            if rows:
                th_class = "view-th" if is_view else ""
                html_content += "<table><tr>{}</tr>".format(
                    ''.join(['<th class="{}">{}</th>'.format(th_class, col) for col in column_names])
                )
                for row in rows:
                    html_content += "<tr>"
                    for i, cell in enumerate(row):
                        if is_view and column_names[i] == 'config' and isinstance(cell, str):
                            try:
                                formatted_json = json.dumps(json.loads(cell), indent=2)
                                html_content += '<td class="json-cell"><pre>{}</pre></td>'.format(formatted_json)
                            except:
                                cell_str = str(cell)[:100]
                                html_content += "<td>{}</td>".format(cell_str)
                        else:
                            cell_str = str(cell)
                            if len(cell_str) > 100:
                                cell_str = cell_str[:100] + "..."
                            html_content += "<td>{}</td>".format(cell_str)
                    html_content += "</tr>"
                html_content += "</table>"
            else:
                html_content += "<p class='empty'>Table/View is empty</p>"
        
        html_content += "</body></html>"
        conn.close()
        return web.Response(text=html_content, content_type='text/html')
        
    except Exception as e:
        return web.Response(
            text="<h1>Database Error</h1><p>{}</p>".format(str(e)),
            content_type='text/html'
        )


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
        </style>
    </head>
    <body>
        <h1> Gateway Configuration API</h1>

        <h2> General Configuration</h2>
        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/api/general-configuration</span>
            <p>Get general gateway configuration</p>
        </div>
        <div class="endpoint">
            <span class="method put">PUT</span>
            <span class="path">/api/general-configuration</span>
            <p>Update general gateway configuration</p>
        </div>

        <h2> Device Management</h2>
        <div class="endpoint">
            <span class="method get">GET</span><span class="path">/api/devices</span>
            <p>Get all devices</p>
        </div>
        <div class="endpoint">
            <span class="method post">POST</span><span class="path">/api/devices</span>
            <p>Add a new device</p>
        </div>
        <div class="endpoint">
            <span class="method get">GET</span><span class="path">/api/devices/{device_id}/details</span>
            <p>Get device details</p>
        </div>
        <div class="endpoint">
            <span class="method put">PUT</span><span class="path">/api/devices/{device_id}</span>
            <p>Update device</p>
        </div>
        <div class="endpoint">
            <span class="method delete">DELETE</span><span class="path">/api/devices/{device_id}</span>
            <p>Delete device</p>
        </div>

        <h2> Pipeline / Load Cell</h2>
        <div class="endpoint">
            <span class="method post">POST</span><span class="path">/api/pipeline/connect</span>
            <p>Connect to pipeline server. Body: {"host": "127.0.0.1", "port": 7000}</p>
        </div>
        <div class="endpoint">
            <span class="method post">POST</span><span class="path">/api/pipeline/disconnect</span>
            <p>Disconnect from pipeline server</p>
        </div>
        <div class="endpoint">
            <span class="method get">GET</span><span class="path">/api/pipeline/status</span>
            <p>Get connection status and latest load_raw value</p>
        </div>
        <div class="endpoint">
            <span class="method get">GET</span><span class="path">/ws/pipeline/load_raw</span>
            <p>WebSocket - live load_raw stream</p>
        </div>

        <h2> WebSocket</h2>
        <div class="endpoint">
            <span class="method get">GET</span><span class="path">/ws</span>
            <p>Real-time time/date updates</p>
        </div>
        <div class="endpoint">
            <span class="method get">GET</span><span class="path">/ws/devices</span>
            <p>Device status updates</p>
        </div>

        <h2> Database Viewer</h2>
        <div class="endpoint">
            <span class="method get">GET</span><span class="path">/db</span>
            <p>View all database tables and data</p>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')


async def start_background_tasks(app):
    app['periodic_updates']      = asyncio.ensure_future(periodic_updates())
    app['device_status_updater'] = asyncio.ensure_future(device_status_updater())


async def cleanup_background_tasks(app):
    app['periodic_updates'].cancel()
    await app['periodic_updates']
    app['device_status_updater'].cancel()
    await app['device_status_updater']


def create_app():
    """Create and configure the aiohttp application"""
    app = web.Application()
    
    app.router.add_get('/',     api_docs_handler)
    app.router.add_get('/docs', api_docs_handler)
    
    app.router.add_get('/api/general-configuration', get_config_handler)
    app.router.add_put('/api/general-configuration', put_config_handler)
    
    register_auth_routes(app)
    register_cloud_routes(app)

    app.router.add_get   ('/api/devices',                    get_all_devices)
    app.router.add_post  ('/api/devices',                    add_device)
    app.router.add_get   ('/api/devices/{device_id}/details',get_device_details)
    app.router.add_put   ('/api/devices/{device_id}',        update_device)
    app.router.add_delete('/api/devices/{device_id}',        delete_device)
    app.router.add_post  ('/api/devices/{device_id}/test',   test_device)
    app.router.add_post  ('/api/devices/{device_id}/disable',disable_device)
    app.router.add_post  ('/api/devices/{device_id}/duplicate', duplicate_device)
    
    app.router.add_get ('/api/devices/export/csv',   export_devices_csv)
    app.router.add_post('/api/devices/import/csv',   import_devices_csv)
    app.router.add_get ('/api/devices/template/csv', download_csv_template)
    
    app.router.add_get   ('/api/groups',                          get_all_groups)
    app.router.add_post  ('/api/groups',                          add_group)
    app.router.add_delete('/api/groups/{group_id}',               delete_group)
    app.router.add_post  ('/api/groups/{group_id}/assign-devices',assign_devices_to_group)
    
    app.router.add_get   ('/api/datapoints',                      get_all_datapoints)
    app.router.add_post  ('/api/datapoints/modbus',               add_modbus_datapoint)
    app.router.add_put   ('/api/datapoints/modbus/{id}',          update_modbus_datapoint)
    app.router.add_put   ('/api/datapoints/loadcell/{id}',        update_loadcell_datapoint)
    app.router.add_delete('/api/datapoints/{id}',                 delete_datapoint)
    app.router.add_get   ('/api/datapoints/devices',              get_available_devices)
    app.router.add_get   ('/api/datapoints/protocol-form/{protocol}', get_protocol_form)
    app.router.add_get   ('/api/devices/{device_id}/datapoints',  get_device_datapoints)

    app.router.add_get('/db', database_viewer_handler)
    app.router.add_get('/ws/general', websocket_handler)
    app.router.add_get('/ws/devices', device_websocket_handler)

    # Pipeline routes - pipeline.py owns the one and only pipeline_state.
    # Do NOT add any pipeline routes here in main.py.
    register_pipeline_routes(app)
    
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    
    return app


if __name__ == '__main__':
    print("Initializing database...")
    init_database()
    
    print("\n" + "="*60)
    print(" Gateway Configuration Server Starting")
    print("="*60)
    print("\n Server: http://0.0.0.0:8082")
    print("  GET  /api/pipeline/status       - Status + load_raw value")
    print("  GET  /ws/pipeline/load_raw      - Live WebSocket stream")
    print("  GET  /ws                        - Real-time updates")
    print("  GET  /ws/devices                - Device status")
    print("="*60 + "\n")
    
    web.run_app(create_app(), host='0.0.0.0', port=8082)