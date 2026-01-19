# main.py - Main entry point
from aiohttp import web
import asyncio

# Import modules
from database import init_database
from general_config import get_config_handler, put_config_handler
from device_management import (
    get_all_devices, get_device_details, add_device, update_device,
    delete_device, test_device, disable_device, duplicate_device,
    get_device_packets, get_all_groups, add_group, assign_devices_to_group,
    scan_devices, get_scan_status, scan_wireless, pair_wireless,
    import_devices_csv, export_devices_csv
)
from websocket_handler import websocket_handler, device_websocket_handler
from utils import periodic_updates, device_status_updater

async def device_management_handler(request):
    """GET handler - device management page"""
    return web.Response(text='Device Management API is running. Use API endpoints.', content_type='text/html')

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
    print("Database: Device management tables created (empty)")
    print("Memory: Real-time device status tracking")
    print("HTTP: Full device management API")
    print("WebSocket: Device status updates")
    print("Import/Export: CSV with full device configuration")
    print("Press Ctrl+C to stop")
    
    web.run_app(create_app(), host='0.0.0.0', port=8080)