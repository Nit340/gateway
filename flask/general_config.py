# general_config.py - General configuration API
from aiohttp import web
from database import get_configuration, update_configuration
from models import current_network_mode, connected_websockets
from websocket_handler import broadcast_to_clients
import asyncio

async def get_config_handler(request):
    """GET handler - configuration as single JSON"""
    config = get_configuration()
    return web.json_response(config)

async def put_config_handler(request):
    """PUT handler - update configuration as single JSON"""
    try:
        data = await request.json()
        success = update_configuration(data)
        
        if success:
            # Check if network mode changed
            if 'network' in data and 'mode' in data['network']:
                from models import current_network_mode
                new_mode = data['network']['mode']
                
                if new_mode != current_network_mode:
                    current_network_mode = new_mode
                    
                    # If switching to/from WiFi, broadcast initial state
                    if new_mode == 'wifi' or (current_network_mode == 'wifi' and new_mode != 'wifi'):
                        config = get_configuration()
                        wifi_configured = new_mode == 'wifi' and config.get('network', {}).get('wifi', {}).get('ssid')
                        
                        if wifi_configured:
                            # WiFi just got configured, send initial signal
                            if connected_websockets:
                                from models import realtime_state
                                await broadcast_to_clients({
                                    'type': 'wifi_signal_update',
                                    'strength': realtime_state['wifi_signal_strength']
                                })
            
            return web.json_response({
                'success': True,
                'message': 'Configuration saved successfully'
            })
        return web.json_response({
            'success': False,
            'message': 'Failed to save configuration'
        }, status=500)
        
    except Exception as e:
        print("Error in PUT handler: {}".format(e))
        return web.json_response({
            'success': False,
            'message': str(e)
        }, status=400)