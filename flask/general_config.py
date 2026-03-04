# general_config.py - General configuration API
from aiohttp import web
from database import get_general_configuration, update_general_configuration


async def get_config_handler(request):
    """GET /api/general-configuration"""
    config = get_general_configuration()
    return web.json_response(config)


async def put_config_handler(request):
    """PUT /api/general-configuration

    Saves all general config fields (gateway identity, date/time, heartbeat,
    network/wifi/ethernet/cellular).  After a successful save it rebuilds and
    pushes the iot_gateway_config to the pipeline service so wifi credentials
    and heartbeat interval are always in sync.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({'success': False, 'message': 'Invalid JSON'}, status=400)

    try:
        success = update_general_configuration(data)
    except Exception as e:
        print("Error in PUT handler: {}".format(e))
        return web.json_response({'success': False, 'message': str(e)}, status=400)

    if not success:
        return web.json_response(
            {'success': False, 'message': 'Failed to save configuration'}, status=500)

    # Rebuild + push iot_gateway_config (wifi/heartbeat may have changed)
    try:
        from mqtt_cloud import send_iot_gateway_config_now
        await send_iot_gateway_config_now()
    except Exception as _e:
        print('[IOT-CFG] sync error after general_config save: {}'.format(_e))

    return web.json_response({'success': True, 'message': 'Configuration saved successfully'})