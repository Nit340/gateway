# -*- coding: utf-8 -*-
# main.py
import asyncio
import json
import logging
import os
import binascii
import sqlite3

from aiohttp import web

from database import (
    init_database, DB_FILE, get_database_stats, get_db_connection,
    verify_admin_user, verify_webui_user,
    get_all_admin_users, create_admin_user, update_admin_user, delete_admin_user,
    get_all_webui_users, create_webui_user, update_webui_user, delete_webui_user,
    get_all_pipeline_service_targets, set_pipeline_service_name,
    get_all_pipeline_send_logs, get_enabled_pipeline_targets,
)
from general import register_general_config_routes
from device_management import (
    get_all_devices, get_device_details, add_device, update_device,
    delete_device, test_device, disable_device, duplicate_device,
    export_devices_csv, import_devices_csv, download_csv_template,
    get_device_datapoints, update_device_status_api,
)
from tag_mapping import (
    get_all_datapoints, add_modbus_datapoint, update_modbus_datapoint,
    delete_datapoint, get_available_devices, get_protocol_form,
    update_loadcell_datapoint,
    get_all_tag_groups, add_tag_group, update_tag_group,
    delete_tag_group, assign_tags_to_group,
)
from mqtt_cloud import register_cloud_routes
from auth import register_auth_routes
from rules import register_rules_routes
from pipeline import (
    register_pipeline_routes, start_pipeline_background,
    PIPELINE_AVAILABLE, send_modbus_config_now,
)

ADMIN_SESSIONS = {}
_SESSION_COOKIE = 'gw_admin_session'

def _get_admin_session(request):
    token = request.cookies.get(_SESSION_COOKIE)
    return ADMIN_SESSIONS.get(token) if token else None

def _require_admin(request):
    user = _get_admin_session(request)
    if not user:
        path = request.path
        if path.startswith('/api/'):
            raise web.HTTPUnauthorized()
        raise web.HTTPFound('/admin/login')
    return user

ADMIN_UI_DIR = os.path.join(os.path.dirname(__file__), 'admin_ui')

def _html(filename):
    path = os.path.join(ADMIN_UI_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return web.Response(text=f.read(), content_type='text/html')

async def admin_login_page(request):
    return _html('login.html')

async def admin_login_post(request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    user = verify_admin_user(username, password)
    if not user:
        return web.json_response({'success': False, 'error': 'Invalid credentials'}, status=401)

    token = binascii.hexlify(os.urandom(32)).decode()
    ADMIN_SESSIONS[token] = user['username']
    resp = web.json_response({'success': True, 'username': user['username'], 'role': user['role']})
    resp.set_cookie(_SESSION_COOKIE, token, httponly=True, path='/')
    return resp

async def admin_logout(request):
    token = request.cookies.get(_SESSION_COOKIE)
    if token:
        ADMIN_SESSIONS.pop(token, None)
    resp = web.HTTPFound('/admin/login')
    resp.del_cookie(_SESSION_COOKIE, path='/')
    return resp

async def admin_root(request):
    _require_admin(request)
    return _html('dashboard.html')

async def admin_pipeline_page(request):
    _require_admin(request)
    return _html('pipeline.html')

async def admin_database_page(request):
    _require_admin(request)
    return _html('database.html')

async def admin_users_page(request):
    _require_admin(request)
    return _html('users.html')

async def api_pipeline_send_log(request):
    _require_admin(request)
    return web.json_response({'logs': get_all_pipeline_send_logs()})

async def api_pipeline_targets_get(request):
    _require_admin(request)
    return web.json_response({'targets': get_all_pipeline_service_targets()})

async def api_pipeline_targets_put(request):
    _require_admin(request)
    try:
        body = await request.json()
        config_type = body.get('config_type')
        service_name = body.get('service_name', '').strip()
        config_name  = body.get('config_name', '').strip() if 'config_name' in body else None
        enabled = body.get('enabled')
        if not config_type:
            return web.json_response({'success': False, 'error': 'config_type required'}, status=400)
        ok = set_pipeline_service_name(config_type, service_name, config_name)
        if enabled is not None and ok:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE pipeline_service_targets SET enabled=? WHERE config_type=?',
                    (1 if enabled else 0, config_type)
                )
                conn.commit()
                conn.close()
            except Exception:
                pass
        return web.json_response({'success': ok})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)

async def api_db_tables(request):
    _require_admin(request)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cursor.fetchall()]
        conn.close()
        return web.json_response({'tables': tables})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def api_db_table_data(request):
    _require_admin(request)
    table = request.match_info['table']
    if not table.replace('_', '').isalnum():
        return web.json_response({'error': 'Invalid table name'}, status=400)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info({})".format(table))
        columns = [r[1] for r in cursor.fetchall()]
        cursor.execute("SELECT * FROM {}".format(table))
        rows = [dict(zip(columns, r)) for r in cursor.fetchall()]
        conn.close()
        return web.json_response({'table': table, 'columns': columns, 'rows': rows})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def api_db_insert(request):
    _require_admin(request)
    table = request.match_info['table']
    if not table.replace('_', '').isalnum():
        return web.json_response({'error': 'Invalid table name'}, status=400)
    try:
        body = await request.json()
        body.pop('id', None)
        keys = list(body.keys())
        values = [body[k] for k in keys]
        sql = "INSERT INTO {} ({}) VALUES ({})".format(
            table,
            ', '.join('"{}"'.format(k) for k in keys),
            ', '.join('?' for _ in keys)
        )
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql, values)
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return web.json_response({'success': True, 'id': new_id})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)

async def api_db_update(request):
    _require_admin(request)
    table = request.match_info['table']
    row_id = request.match_info['id']
    if not table.replace('_', '').isalnum():
        return web.json_response({'error': 'Invalid table name'}, status=400)
    try:
        body = await request.json()
        body.pop('id', None)
        keys = list(body.keys())
        values = [body[k] for k in keys]
        sets = ', '.join('{} = ?'.format(k) for k in keys)
        values.append(row_id)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE {} SET {} WHERE id = ?".format(table, sets), values)
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return web.json_response({'success': True, 'affected': affected})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)

async def api_db_delete(request):
    _require_admin(request)
    table = request.match_info['table']
    row_id = request.match_info['id']
    if not table.replace('_', '').isalnum():
        return web.json_response({'error': 'Invalid table name'}, status=400)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM {} WHERE id = ?".format(table), (row_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return web.json_response({'success': True, 'affected': affected})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)

async def api_admin_users_get(request):
    _require_admin(request)
    return web.json_response({'users': get_all_admin_users()})

async def api_admin_users_post(request):
    _require_admin(request)
    try:
        body = await request.json()
        uid = create_admin_user(body['username'], body['password'], body.get('role', 'operator'))
        if uid:
            return web.json_response({'success': True, 'id': uid})
        return web.json_response({'success': False, 'error': 'Could not create user (duplicate?)'}, status=400)
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)

async def api_admin_user_put(request):
    _require_admin(request)
    user_id = request.match_info['id']
    try:
        body = await request.json()
        ok = update_admin_user(user_id, body)
        return web.json_response({'success': ok})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)

async def api_admin_user_delete(request):
    _require_admin(request)
    user_id = request.match_info['id']
    ok = delete_admin_user(user_id)
    return web.json_response({'success': ok})

async def api_webui_users_get(request):
    _require_admin(request)
    return web.json_response({'users': get_all_webui_users()})

async def api_webui_users_post(request):
    _require_admin(request)
    try:
        body = await request.json()
        uid = create_webui_user(body['username'], body['password'], body.get('display_name', ''))
        if uid:
            return web.json_response({'success': True, 'id': uid})
        return web.json_response({'success': False, 'error': 'Could not create user (duplicate?)'}, status=400)
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)

async def api_webui_user_put(request):
    _require_admin(request)
    user_id = request.match_info['id']
    try:
        body = await request.json()
        ok = update_webui_user(user_id, body)
        return web.json_response({'success': ok})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)

async def api_webui_user_delete(request):
    _require_admin(request)
    user_id = request.match_info['id']
    ok = delete_webui_user(user_id)
    return web.json_response({'success': ok})

async def webui_login_api(request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    user = verify_webui_user(username, password)
    if not user:
        return web.json_response({'success': False, 'error': 'Invalid username or password.'}, status=401)
    return web.json_response({'success': True, 'username': user['username'], 'display_name': user['display_name']})

async def database_viewer_handler(request):
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        html = '<html><head><title>DB Viewer</title></head><body>'
        html += '<h1>Database: {}</h1>'.format(DB_FILE)
        for (tname,) in tables:
            cursor.execute("PRAGMA table_info({})".format(tname))
            cols = [r[1] for r in cursor.fetchall()]
            cursor.execute("SELECT * FROM {}".format(tname))
            rows = cursor.fetchall()
            html += '<h2>{} ({} rows)</h2>'.format(tname, len(rows))
            if rows:
                html += '<table border=1><tr>' + ''.join('<th>{}</th>'.format(c) for c in cols) + '</tr>'
                for row in rows:
                    html += '<tr>' + ''.join('<td>{}</td>'.format(str(v)[:200]) for v in row) + '</tr>'
                html += '</table>'
        html += '</body></html>'
        conn.close()
        return web.Response(text=html, content_type='text/html')
    except Exception as e:
        return web.Response(text='<h1>Error</h1><p>{}</p>'.format(e), content_type='text/html')

_DB_PATH_FILE = os.path.join(os.path.dirname(__file__), '.db_path_override')

def _read_db_path_override():
    try:
        return open(_DB_PATH_FILE).read().strip()
    except FileNotFoundError:
        return ''

async def api_db_path_get(request):
    _require_admin(request)
    import database as _db
    override = _read_db_path_override()
    return web.json_response({
        'current': _db.DB_FILE,
        'default': '/mnt/data/gateway_config.db',
        'override': override,
        'env_var': os.environ.get('GATEWAY_DB_FILE', ''),
    })

async def api_db_path_put(request):
    _require_admin(request)
    try:
        body = await request.json()
        new_path = (body.get('path') or '').strip()
        if not new_path:
            return web.json_response({'success': False, 'error': 'path is required'}, status=400)
        if not new_path.endswith('.db'):
            return web.json_response({'success': False, 'error': 'Path must end in .db'}, status=400)
        os.makedirs(os.path.dirname(new_path) if os.path.dirname(new_path) else '.', exist_ok=True)
        open(_DB_PATH_FILE, 'w').write(new_path)
        os.environ['GATEWAY_DB_FILE'] = new_path
        return web.json_response({
            'success': True,
            'path': new_path,
            'note': 'Path saved. Restart the server for the new DB file to take effect.'
        })
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)

async def start_background_tasks(app):
    print("[MAIN] Starting background tasks...")

    if PIPELINE_AVAILABLE:
        print("[MAIN] Starting pipeline background thread...")
        start_pipeline_background(app)

        async def _startup_auto_send():
            from pipeline import pipeline_state, _do_auto_send
            print("[MAIN] Startup auto-send: waiting for pipeline connection (max 30 s)...")
            for _ in range(30):
                await asyncio.sleep(1)
                with pipeline_state["lock"]:
                    if pipeline_state["connected"]:
                        break
            with pipeline_state["lock"]:
                connected = pipeline_state["connected"]
            print("[MAIN] Startup auto-send: pipeline {} -- running ordered send".format(
                "connected" if connected else "not connected (will queue)"))
            try:
                result = await _do_auto_send()
                import json as _j
                body   = _j.loads(result.body) if hasattr(result, "body") else result
                sent   = body.get("auto_sent", False)
                count  = body.get("targets_attempted", 0)
                print("[MAIN] Startup auto-send complete: {} target(s), sent={}".format(count, sent))
                for r in body.get("results", []):
                    print("[MAIN]   {} order={} sent={} -> {}".format(
                        r.get("config_type"), r.get("send_order"), r.get("pipeline_sent"), r.get("message", "")))
            except Exception as e:
                print("[MAIN] Startup auto-send error: {}".format(e))

        app["startup_auto_send"] = asyncio.ensure_future(_startup_auto_send())
    else:
        print("[MAIN] Pipeline not available - skipping")

async def cleanup_background_tasks(app):
    print("[MAIN] Cleaning up background tasks...")
    if 'startup_auto_send' in app:
        app['startup_auto_send'].cancel()
        try:
            await app['startup_auto_send']
        except (asyncio.CancelledError, Exception):
            pass

    if PIPELINE_AVAILABLE:
        try:
            from pipeline import pipeline_state
            with pipeline_state["lock"]:
                pipeline_state["should_run"] = False
        except Exception as e:
            print("[MAIN] Error stopping pipeline: {}".format(e))
    print("[MAIN] Cleanup complete")

def create_app():
    # -------------------------------------------------------------------
    # FIX: pass auth_middleware to web.Application so it runs on every
    # request.  aiohttp 2.x uses the factory style (app, handler) which
    # is exactly what auth_middleware in auth.py implements.
    # Without this the middleware never executes, request['user'] is
    # never set, and ws_auth() cannot validate the session cookie on
    # WebSocket upgrade requests.
    # -------------------------------------------------------------------
    app = web.Application()

    app.router.add_get('/admin/login', admin_login_page)
    app.router.add_post('/admin/login', admin_login_post)
    app.router.add_get('/admin/logout', admin_logout)
    app.router.add_get('/admin', admin_root)
    app.router.add_get('/admin/', admin_root)
    app.router.add_get('/admin/pipeline', admin_pipeline_page)
    app.router.add_get('/admin/database', admin_database_page)
    app.router.add_get('/admin/users', admin_users_page)

    WEBUI_LOGIN_FILE = os.path.join(os.path.dirname(__file__), 'login.html')
    async def webui_login_page(request):
        try:
            with open(WEBUI_LOGIN_FILE, 'r', encoding='utf-8') as f:
                return web.Response(text=f.read(), content_type='text/html')
        except FileNotFoundError:
            raise web.HTTPNotFound(text='login.html not found beside main.py')
    app.router.add_get('/', webui_login_page)

    app.router.add_get('/api/admin/pipeline-targets', api_pipeline_targets_get)
    app.router.add_put('/api/admin/pipeline-targets', api_pipeline_targets_put)
    app.router.add_get('/api/admin/pipeline-send-log', api_pipeline_send_log)

    app.router.add_get('/api/admin/db/tables', api_db_tables)
    app.router.add_get('/api/admin/db/table/{table}', api_db_table_data)
    app.router.add_post('/api/admin/db/table/{table}', api_db_insert)
    app.router.add_put('/api/admin/db/table/{table}/{id}', api_db_update)
    app.router.add_delete('/api/admin/db/table/{table}/{id}', api_db_delete)

    app.router.add_get('/api/admin/users/admin', api_admin_users_get)
    app.router.add_post('/api/admin/users/admin', api_admin_users_post)
    app.router.add_put('/api/admin/users/admin/{id}', api_admin_user_put)
    app.router.add_delete('/api/admin/users/admin/{id}', api_admin_user_delete)

    app.router.add_get('/api/admin/users/webui', api_webui_users_get)
    app.router.add_post('/api/admin/users/webui', api_webui_users_post)
    app.router.add_put('/api/admin/users/webui/{id}', api_webui_user_put)
    app.router.add_delete('/api/admin/users/webui/{id}', api_webui_user_delete)

    # NOTE: /api/auth/login is registered here for the webui AND again
    # inside register_auth_routes below.  The second registration wins in
    # aiohttp so webui_login_api is effectively replaced by login_handler
    # from auth.py.  Both do the same job so this is harmless, but if you
    # want webui_login_api (database-backed) to be the active handler,
    # move this line AFTER register_auth_routes or remove the duplicate
    # inside register_auth_routes.
    app.router.add_post('/api/auth/login', webui_login_api)

    app.router.add_get('/api/admin/db-path', api_db_path_get)
    app.router.add_put('/api/admin/db-path', api_db_path_put)

    register_general_config_routes(app)

    register_auth_routes(app)
    register_cloud_routes(app)
    register_rules_routes(app)

    app.router.add_get('/api/devices', get_all_devices)
    app.router.add_post('/api/devices', add_device)
    app.router.add_get('/api/devices/{device_id}/details', get_device_details)
    app.router.add_put('/api/devices/{device_id}', update_device)
    app.router.add_delete('/api/devices/{device_id}', delete_device)
    app.router.add_post('/api/devices/{device_id}/test', test_device)
    app.router.add_post('/api/devices/{device_id}/disable', disable_device)
    app.router.add_post('/api/devices/{device_id}/duplicate', duplicate_device)
    app.router.add_get('/api/devices/export/csv', export_devices_csv)
    app.router.add_post('/api/devices/import/csv', import_devices_csv)
    app.router.add_get('/api/devices/template/csv', download_csv_template)
    app.router.add_post('/api/devices/{device_id}/status', update_device_status_api)

    app.router.add_get('/api/tag-groups', get_all_tag_groups)
    app.router.add_post('/api/tag-groups', add_tag_group)
    app.router.add_put('/api/tag-groups/{group_id}', update_tag_group)
    app.router.add_delete('/api/tag-groups/{group_id}', delete_tag_group)
    app.router.add_post('/api/tag-groups/{group_id}/assign-tags', assign_tags_to_group)

    app.router.add_get('/api/datapoints', get_all_datapoints)
    app.router.add_post('/api/datapoints/modbus', add_modbus_datapoint)
    app.router.add_put('/api/datapoints/modbus/{id}', update_modbus_datapoint)
    app.router.add_put('/api/datapoints/loadcell/{id}', update_loadcell_datapoint)
    app.router.add_delete('/api/datapoints/{id}', delete_datapoint)
    app.router.add_get('/api/datapoints/devices', get_available_devices)
    app.router.add_get('/api/datapoints/protocol-form/{protocol}', get_protocol_form)
    app.router.add_get('/api/devices/{device_id}/datapoints', get_device_datapoints)

    register_pipeline_routes(app)

    async def db_redirect(request):
        raise web.HTTPFound('/admin/database')
    app.router.add_get('/db', db_redirect)

    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    return app

if __name__ == '__main__':
    print("=" * 60)
    print("  Gateway Admin Server Starting")
    print("=" * 60)
    print("\nInitializing database...")
    init_database()
    print("\nAdmin Panel : http://0.0.0.0:8082/admin")
    print("Default login: admin / admin123")
    print("=" * 60 + "\n")
    web.run_app(create_app(), host='0.0.0.0', port=8082)