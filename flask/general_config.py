# general_config.py - General configuration API
from aiohttp import web
from database import get_general_configuration, update_general_configuration

async def get_config_handler(request):
    """GET handler - general configuration"""
    config = get_general_configuration()
    return web.json_response(config)

async def put_config_handler(request):
    """PUT handler - update general configuration"""
    try:
        data = await request.json()
        success = update_general_configuration(data)
        
        if success:
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