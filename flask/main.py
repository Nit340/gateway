# -*- coding: utf-8 -*-
import sys
import io

# Force UTF-8 encoding for stdout
if sys.stdout.encoding != 'UTF-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from logger_util import get_logger

# ---------------------------------------------------------------------------
# Logger and auth globals - defined early for log_handler import
# ---------------------------------------------------------------------------
logger = get_logger(__name__)

ADMIN_SESSIONS = {}           # token -> username
ADMIN_USER_TOKENS = {}        # username -> token  (enforces one session per user)
_SESSION_COOKIE = 'gw_admin_session'

WEBUI_SESSIONS = {}           # token -> {username, logged_in_at, token}
WEBUI_USER_TOKENS = {}        # username -> [token, ...]  (enforces max_sessions per user)
_WEBUI_SESSION_COOKIE = 'gw_webui_session'

def _get_admin_session(request):
    token = request.cookies.get(_SESSION_COOKIE)
    return ADMIN_SESSIONS.get(token) if token else None

def _require_admin(request):
    token = request.cookies.get(_SESSION_COOKIE)
    user = ADMIN_SESSIONS.get(token) if token else None
    if not user:
        logger.warning("[ADMIN AUTH] Access denied for {}".format(request.path))
        path = request.path
        if path.startswith('/api/'):
            raise web.HTTPUnauthorized()
        raise web.HTTPFound('/admin/login')
    return user

# ---------------------------------------------------------------------------
import log_handler; log_handler.install()
# ---------------------------------------------------------------------------

# main.py (OPTIMIZED)
import asyncio
import json
import logging
import os
import binascii
import sqlite3

from aiohttp import web

# OPTIMIZATION: Import ensure_db_initialized instead of init_database
from database import (
    ensure_db_initialized, DB_FILE, get_database_stats, get_db_connection,
    verify_admin_user, verify_webui_user,
    get_all_admin_users, create_admin_user, update_admin_user, delete_admin_user,
    get_all_webui_users, create_webui_user, update_webui_user, delete_webui_user,
    get_all_pipeline_service_targets, set_pipeline_service_name,
    get_all_pipeline_send_logs, get_enabled_pipeline_targets,
    get_all_pages, get_user_page_restrictions, set_user_page_restriction, get_pages_for_user,
    get_webui_user_max_sessions, set_webui_user_max_sessions,
)
from general import register_general_config_routes
from device_management import (
    get_all_devices, get_device_details, add_device, update_device,
    delete_device, test_device, disable_device, duplicate_device,
    export_devices_csv, import_devices_csv, download_csv_template,
    get_device_datapoints, update_device_status_api, get_port_config_api,
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

# ---------------------------------------------------------------------------
# ws_auth - defined here in main.py so it always has direct access to
# WEBUI_SESSIONS without any cross-module import issues.
# general.py imports ws_auth from auth.py, but we monkey-patch it below
# in create_app() to point to this version instead.
# ---------------------------------------------------------------------------
def _ws_auth_main(request):
    """
    Read gw_webui_session cookie and return username from WEBUI_SESSIONS.
    Defined in main.py so it accesses WEBUI_SESSIONS directly - no import needed.
    Returns username string on success, None if unauthenticated.
    """
    token = request.cookies.get('gw_webui_session')
    if not token:
        return None
    session = WEBUI_SESSIONS.get(token)
    if not session:
        return None
    if isinstance(session, dict):
        return session.get('username')
    return session if isinstance(session, str) else None
from rules import register_rules_routes
from pipeline import (
    register_pipeline_routes, start_pipeline_background,
    PIPELINE_AVAILABLE, send_modbus_config_now,
)

ADMIN_UI_DIR = os.path.join(os.path.dirname(__file__), 'admin_ui')

def _html(filename):
    path = os.path.join(ADMIN_UI_DIR, filename)
    with open(path, 'rb') as f:
        raw = f.read()
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        text = raw.decode('windows-1252')
    return web.Response(text=text, content_type='text/html', charset='utf-8')

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

    # If this user already has an active session, log out the existing one to allow re-login.
    existing_token = ADMIN_USER_TOKENS.get(user['username'])
    if existing_token and existing_token in ADMIN_SESSIONS:
        ADMIN_SESSIONS.pop(existing_token, None)
        ADMIN_USER_TOKENS.pop(user['username'], None)

    ADMIN_SESSIONS[token] = user['username']
    ADMIN_USER_TOKENS[user['username']] = token
    logger.info("[ADMIN LOGIN] Created session for {}, token: {}...".format(user['username'], token[:8]))
    resp = web.json_response({'success': True, 'username': user['username'], 'role': user['role']})
    resp.set_cookie(_SESSION_COOKIE, token, httponly=False, path='/')
    return resp

async def admin_logout(request):
    token = request.cookies.get(_SESSION_COOKIE)
    if token:
        username = ADMIN_SESSIONS.pop(token, None)
        if username and ADMIN_USER_TOKENS.get(username) == token:
            ADMIN_USER_TOKENS.pop(username, None)
        logger.info("[ADMIN LOGOUT] Logged out user: {}".format(username or 'unknown'))
    resp = web.HTTPFound('/admin/login')
    resp.del_cookie(_SESSION_COOKIE, path='/')
    return resp

async def admin_session_check(request):
    """GET /api/admin/session-check -- returns 200 if session is valid, 401 if kicked out."""
    token = request.cookies.get(_SESSION_COOKIE)
    if not token or token not in ADMIN_SESSIONS:
        return web.json_response({'valid': False, 'reason': 'session_expired'}, status=401)
    return web.json_response({'valid': True})

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

async def admin_access_control_page(request):
    _require_admin(request)
    return _html('access-control.html')

async def api_webui_pages_get(request):
    """GET /api/admin/webui-pages?user_id=N -- get all pages + restriction status for a user"""
    _require_admin(request)
    user_id = request.rel_url.query.get('user_id')
    if not user_id:
        # No user selected: return master page list with no restrictions
        return web.json_response({'pages': get_all_pages(), 'users': []})
    try:
        pages = get_pages_for_user(int(user_id))
        return web.json_response({'pages': pages})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def api_webui_page_restriction_put(request):
    """PUT /api/admin/webui-pages -- set hidden flag for one page for one user"""
    _require_admin(request)
    try:
        body     = await request.json()
        user_id  = body.get('user_id')
        page_key = body.get('page_key', '').strip()
        hidden   = bool(body.get('hidden', False))
        if not user_id or not page_key:
            return web.json_response({'success': False, 'error': 'user_id and page_key required'}, status=400)
        ok = set_user_page_restriction(int(user_id), page_key, hidden)
        return web.json_response({'success': ok})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def api_pipeline_send_log(request):
    _require_admin(request)
    return web.json_response({'logs': get_all_pipeline_send_logs()})

async def api_pipeline_targets_get(request):
    _require_admin(request)
    DEFAULT_ORDER = ['modbus', 'loadcell', 'iot_gateway', 'core']
    targets = get_all_pipeline_service_targets()
    for t in targets:
        if not t.get('send_order'):
            try:
                t['send_order'] = DEFAULT_ORDER.index(t['config_type']) + 1
            except ValueError:
                t['send_order'] = 99
    return web.json_response({'targets': targets})

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
        role = body.get('role', 'user')
        if role not in ('admin', 'user'):
            return web.json_response({'success': False, 'error': "role must be 'admin' or 'user'"}, status=400)
        uid = create_webui_user(body['username'], body['password'], body.get('display_name', ''), role)
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

    # Enforce per-user session limit stored in database
    import datetime as _dt
    import time
    max_sessions = get_webui_user_max_sessions(user['id'])
    active_tokens = [t for t in WEBUI_USER_TOKENS.get(user['username'], []) if t in WEBUI_SESSIONS]
    if len(active_tokens) >= max_sessions:
        if max_sessions == 1:
            return web.json_response({'success': False, 'error': 'Session limit is 1. Another user is already logged in.'}, status=403)
        else:
            return web.json_response({'success': False, 'error': 'Session limit reached. Cannot allow more concurrent view-only sessions.'}, status=403)

    token = binascii.hexlify(os.urandom(32)).decode()
    WEBUI_SESSIONS[token] = {'username': user['username'], 'logged_in_at': _dt.datetime.now(_dt.timezone.utc).isoformat(), 'token': token, 'last_ping': time.time()}
    if user['username'] not in WEBUI_USER_TOKENS:
        WEBUI_USER_TOKENS[user['username']] = []
    WEBUI_USER_TOKENS[user['username']].append(token)

    resp = web.json_response({'success': True, 'username': user['username'], 'display_name': user['display_name'], 'role': user['role']})
    resp.set_cookie('gw_webui_session', token, httponly=False, path='/')
    return resp

async def webui_logout_api(request):
    """POST /api/auth/logout -- clears webui session so the user can log in again."""
    token = request.cookies.get('gw_webui_session')
    if token:
        info = WEBUI_SESSIONS.pop(token, None)
        username = info['username'] if isinstance(info, dict) else info
        if username and username in WEBUI_USER_TOKENS:
            try:
                WEBUI_USER_TOKENS[username].remove(token)
            except ValueError:
                pass
            if not WEBUI_USER_TOKENS[username]:
                del WEBUI_USER_TOKENS[username]
    resp = web.json_response({'success': True})
    resp.del_cookie('gw_webui_session', path='/')
    resp.del_cookie('gw_auth', path='/')
    resp.del_cookie('gw_user', path='/')
    return resp

async def webui_session_status(request):
    """GET /api/auth/status -- returns 200 if session valid, 401 if not.
    Also returns hidden_pages list so layout.html can restrict the sidebar per user."""
    import time
    token = request.cookies.get('gw_webui_session')
    if not token or token not in WEBUI_SESSIONS:
        return web.json_response({'authenticated': False}, status=401)
    _sess = WEBUI_SESSIONS[token]
    if isinstance(_sess, dict):
        _sess['last_ping'] = time.time()
        username = _sess['username']
    else:
        username = _sess
        WEBUI_SESSIONS[token] = {'username': username, 'last_ping': time.time()}
    # Look up user_id to fetch per-user page restrictions
    try:
        from database import get_db_connection as _gdc
        conn = _gdc()
        cur  = conn.cursor()
        cur.execute('SELECT id, role FROM webui_users WHERE username=?', (username,))
        row = cur.fetchone()
        conn.close()
        user_id   = row[0] if row else None
        user_role = row[1] if row else 'user'
        hidden_pages = get_user_page_restrictions(user_id) if user_id else []
    except Exception:
        hidden_pages = []
        user_role = 'user'
    return web.json_response({
        'authenticated': True,
        'username': username,
        'role': user_role,
        'hidden_pages': hidden_pages,
    })

async def webui_session_role(request):
    """GET /api/auth/session-role
    Returns the user's DB role ('admin' or 'user') and whether the current
    session is the 'editor' (first login) or a 'viewer' (read-only).
    """
    token = request.cookies.get('gw_webui_session')
    if not token or token not in WEBUI_SESSIONS:
        return web.json_response({'authenticated': False, 'role': 'viewer', 'user_role': 'user'}, status=401)

    info = WEBUI_SESSIONS[token]
    username = info['username'] if isinstance(info, dict) else info

    # The first token in the list for this user is the editor
    user_tokens = WEBUI_USER_TOKENS.get(username, [])
    # Filter to only tokens still active in WEBUI_SESSIONS
    active_tokens = [t for t in user_tokens if t in WEBUI_SESSIONS]
    role = 'editor' if (active_tokens and active_tokens[0] == token) else 'viewer'

    # Fetch DB-level role ('admin' or 'user')
    try:
        from database import get_db_connection as _gdc
        _conn = _gdc()
        _cur  = _conn.cursor()
        _cur.execute('SELECT role FROM webui_users WHERE username=?', (username,))
        _row  = _cur.fetchone()
        _conn.close()
        user_role = _row[0] if _row else 'user'
    except Exception:
        user_role = 'user'

    return web.json_response({'authenticated': True, 'username': username, 'role': role, 'user_role': user_role})


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
    logger.info("[MAIN] Starting background tasks...")
    import time

    async def _webui_session_watchdog():
        while True:
            await asyncio.sleep(5)
            now = time.time()
            to_remove = []
            for token, info in list(WEBUI_SESSIONS.items()):
                if isinstance(info, dict) and 'last_ping' in info:
                    if now - info['last_ping'] > 15:
                        to_remove.append(token)
            for token in to_remove:
                info = WEBUI_SESSIONS.pop(token, None)
                if info:
                    uname = info.get('username') if isinstance(info, dict) else info
                    if uname and uname in WEBUI_USER_TOKENS:
                        try:
                            WEBUI_USER_TOKENS[uname].remove(token)
                        except ValueError:
                            pass
                        if not WEBUI_USER_TOKENS[uname]:
                            del WEBUI_USER_TOKENS[uname]
                logger.info("[MAIN] Session watchdog removed inactive token for user {}".format(uname))

    app["webui_session_watchdog"] = asyncio.ensure_future(_webui_session_watchdog())

    if PIPELINE_AVAILABLE:
        logger.info("[MAIN] Starting pipeline background thread...")
        start_pipeline_background(app)

        async def _pipeline_watchdog():
            """Keep the pipeline thread alive forever.

            The pipeline thread is permanent -- it starts on boot and must
            never stop while the server is running.  connect/disconnect
            endpoints are no-ops, so should_run is always True.
            The watchdog simply checks every 5 s and restarts the thread
            if it has died for any reason (crash, exception, etc.).
            """
            import asyncio as _asyncio
            from pipeline import pipeline_state as _ps, start_pipeline_background as _spb
            while True:
                await _asyncio.sleep(5)
                with _ps["lock"]:
                    thread = _ps.get("background_thread")
                    # Ensure should_run is always True -- nothing should ever
                    # set it to False now that connect/disconnect are no-ops.
                    _ps["should_run"] = True
                if thread is None or not thread.is_alive():
                    logger.info("[MAIN] Watchdog: pipeline thread is dead -- restarting...")
                    _spb(app)

        app["pipeline_watchdog"] = asyncio.ensure_future(_pipeline_watchdog())

        async def _startup_auto_send():
            from pipeline import pipeline_state, _do_auto_send
            logger.info("[MAIN] Startup auto-send: waiting for pipeline connection (max 30 s)...")
            for _ in range(30):
                await asyncio.sleep(1)
                with pipeline_state["lock"]:
                    if pipeline_state["connected"]:
                        break
            with pipeline_state["lock"]:
                connected = pipeline_state["connected"]
            logger.info("[MAIN] Startup auto-send: pipeline {} -- running ordered send".format(
                "connected" if connected else "not connected (will queue)"))

            # On every startup, push the unit ("kg") for every enabled load cell
            # to load_cell_service so the service always has the correct unit set.
            if connected:
                try:
                    from pipeline import pipeline_state as _ps
                    from database import get_db_connection as _gdc
                    from database import get_pipeline_service_name

                    _conn = _gdc()
                    _cur  = _conn.cursor()
                    _cur.execute("SELECT name, unit FROM loadcell_device WHERE enabled = 1")
                    _lc_rows = _cur.fetchall()
                    _conn.close()

                    _lc_svc = get_pipeline_service_name("loadcell")
                    _client  = _ps.get("client")

                    if _client and _lc_svc:
                        for _row in _lc_rows:
                            _dev_name = _row[0]
                            _unit     = _row[1] if _row[1] else "kg"
                            _dp_name  = "loadcells.{}.unit".format(_dev_name)
                            try:
                                _rid = _client.datapoint_update(_lc_svc, _dp_name, _unit)
                                if _rid:
                                    logger.info("[MAIN] Startup unit update sent: '{}' = '{}' (req_id={})".format(
                                        _dp_name, _unit, _rid))
                                else:
                                    logger.info("[MAIN] Startup unit update FAILED (not connected?): '{}'".format(_dp_name))
                            except Exception as _ue:
                                logger.error("[MAIN] Startup unit update error for '{}': {}".format(_dp_name, _ue))
                    else:
                        logger.info("[MAIN] Startup unit update skipped -- client={} lc_svc={}".format(
                            bool(_client), _lc_svc))
                except Exception as _e:
                    logger.error("[MAIN] Startup unit update error: {}".format(_e))
            try:
                result = await _do_auto_send()
                import json as _j
                if hasattr(result, "body"):
                    raw = result.body
                    body = _j.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
                else:
                    body = result
                sent   = body.get("auto_sent", False)
                count  = body.get("targets_attempted", 0)
                logger.info("[MAIN] Startup auto-send complete: {} target(s), sent={}".format(count, sent))
                for r in body.get("results", []):
                    logger.info("[MAIN]   {} order={} sent={} -> {}".format(
                        r.get("config_type"), r.get("send_order"), r.get("pipeline_sent"), r.get("message", "")))
            except Exception as e:
                logger.error("[MAIN] Startup auto-send error: {}".format(e))

        app["startup_auto_send"] = asyncio.ensure_future(_startup_auto_send())
    else:
        logger.info("[MAIN] Pipeline not available - skipping")

async def cleanup_background_tasks(app):
    logger.info("[MAIN] Cleaning up background tasks...")
    for key in ('startup_auto_send', 'pipeline_watchdog', 'webui_session_watchdog'):
        task = app.get(key)
        if task:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    if PIPELINE_AVAILABLE:
        try:
            from pipeline import pipeline_state
            with pipeline_state["lock"]:
                pipeline_state["should_run"] = False
        except Exception as e:
            logger.error("[MAIN] Error stopping pipeline: {}".format(e))
    logger.info("[MAIN] Cleanup complete")


async def api_webui_sessions_get(request):
    """GET /api/admin/webui-sessions -- list all active webui sessions."""
    _require_admin(request)
    import datetime as _dt
    sessions = []
    for token, info in list(WEBUI_SESSIONS.items()):
        username = info['username'] if isinstance(info, dict) else info
        logged_in_at = info.get('logged_in_at', '') if isinstance(info, dict) else ''
        sessions.append({'token_prefix': token[:8], 'token': token, 'username': username, 'logged_in_at': logged_in_at})
    try:
        from database import get_db_connection as _gdc2
        conn = _gdc2()
        cur = conn.cursor()
        cur.execute('SELECT id, username, display_name, role, max_sessions FROM webui_users')
        user_rows = {r[1]: {'id': r[0], 'display_name': r[2], 'role': r[3] or 'user', 'max_sessions': r[4] or 1} for r in cur.fetchall()}
        conn.close()
    except Exception:
        user_rows = {}
    result = []
    for s in sessions:
        u = user_rows.get(s['username'], {})
        result.append(dict(s, **{'user_id': u.get('id'), 'display_name': u.get('display_name', s['username']), 'role': u.get('role', 'user'), 'max_sessions': u.get('max_sessions', 1)}))
    return web.json_response({'sessions': result})


async def api_webui_session_kill(request):
    """DELETE /api/admin/webui-sessions/{token} -- force-logout a specific session."""
    _require_admin(request)
    token = request.match_info['token']
    info = WEBUI_SESSIONS.pop(token, None)
    if info is None:
        return web.json_response({'success': False, 'error': 'Session not found'}, status=404)
    username = info['username'] if isinstance(info, dict) else info
    if username and username in WEBUI_USER_TOKENS:
        try:
            WEBUI_USER_TOKENS[username].remove(token)
        except ValueError:
            pass
        if not WEBUI_USER_TOKENS[username]:
            del WEBUI_USER_TOKENS[username]
    return web.json_response({'success': True})


async def api_webui_user_max_sessions_put(request):
    """PUT /api/admin/users/webui/{id}/max-sessions -- update session limit for a webui user."""
    _require_admin(request)
    user_id = request.match_info['id']
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        max_s = max(1, int(body.get('max_sessions', 1)))
    except (TypeError, ValueError):
        max_s = 1
    ok = set_webui_user_max_sessions(int(user_id), max_s)
    if ok:
        return web.json_response({'success': True, 'max_sessions': max_s})
    return web.json_response({'success': False, 'error': 'Failed to update'}, status=500)


# ---------------------------------------------------------------------------
# Core Config JSON Upload API
# ---------------------------------------------------------------------------
async def api_core_config_upload(request):
    """POST /api/pipeline/core-config/upload
    Upload and save core config JSON, optionally send to pipeline.
    """
    _require_admin(request)
    try:
        body = await request.json()
        config_json = body.get('config_json', '')
        send_to_pipeline = body.get('send_to_pipeline', True)
        
        if not config_json:
            return web.json_response({'success': False, 'error': 'Missing config_json'}, status=400)
        
        # Validate JSON
        try:
            config = json.loads(config_json)
        except json.JSONDecodeError as e:
            return web.json_response({'success': False, 'error': 'Invalid JSON: {}'.format(e)}, status=400)
        
        # Basic validation
        if 'service_name' not in config and 'services' not in config:
            return web.json_response({
                'success': False, 
                'error': 'Config must have service_name or services section'
            }, status=400)
        
        # Save to core_configs table
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS core_configs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                version      INTEGER NOT NULL DEFAULT 1,
                device_names TEXT,
                service_name TEXT,
                config_json  TEXT NOT NULL,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Extract device names from config if possible
        device_names = []
        if 'services' in config:
            for svc_name, svc_config in config['services'].items():
                if svc_name == 'modbus' and 'groups' in svc_config:
                    for group in svc_config['groups']:
                        if 'members' in group:
                            device_names.extend(group['members'])
        
        # Get next version
        cursor.execute('SELECT COALESCE(MAX(version), 0) FROM core_configs')
        next_version = cursor.fetchone()[0] + 1
        
        service_name = config.get('service_name', 'ilx_craneiq_core')
        
        cursor.execute(
            'INSERT INTO core_configs (version, device_names, service_name, config_json) VALUES (?, ?, ?, ?)',
            (next_version, json.dumps(device_names), service_name, config_json)
        )
        conn.commit()
        conn.close()
        
        logger.info("[CORE-CFG] Uploaded config v{} from JSON".format(next_version))
        
        # Optionally send to pipeline
        sent = False
        queued = False
        if send_to_pipeline:
            try:
                from pipeline import pipeline_state, get_pipeline_service_name, get_pipeline_config_name
                from pipeline import record_pipeline_send_success, record_pipeline_send_failure
                from pipeline import get_next_pipeline_version as get_ver
                from pipeline import Config
                
                core_svc = get_pipeline_service_name('core') or 'ilx_craneiq_core'
                cfg_name = get_pipeline_config_name('core')
                
                with pipeline_state.get('lock', None):
                    # If we can't get lock, try without it
                    client = pipeline_state.get('client')
                    connected = pipeline_state.get('connected', False)
                    services = set(pipeline_state.get('connected_services', set()))
                
                if connected and client and core_svc in services:
                    new_version = get_ver('core')
                    ok = client.publish_config(Config(
                        name=cfg_name,
                        value=config_json,
                        version=new_version,
                        service=core_svc,
                    ))
                    if ok:
                        record_pipeline_send_success('core', new_version, core_svc, 
                                                     'Uploaded JSON v{}'.format(next_version))
                        sent = True
                    else:
                        record_pipeline_send_failure('core', 'publish_config returned False')
                        queued = True
                else:
                    # Queue for later
                    with pipeline_state['lock']:
                        pipeline_state['core_config_pending'] = config_json
                    queued = True
                    logger.info('[CORE-CFG] Not connected -- queued for "{}"'.format(core_svc))
            except Exception as e:
                logger.error('[CORE-CFG] Upload send error: {}'.format(e))
                record_pipeline_send_failure('core', str(e))
                queued = True
        
        return web.json_response({
            'success': True,
            'sent': sent,
            'queued': queued,
            'version': next_version,
            'message': 'Config saved to DB' + 
                       (' and sent to pipeline' if sent else 
                        (' and queued for pipeline' if queued else ''))
        })
        
    except Exception as e:
        logger.error('[CORE-CFG] Upload error: {}'.format(e))
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def api_core_configs_list(request):
    """GET /api/pipeline/core-configs -- list all saved core configs"""
    _require_admin(request)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, version, device_names, service_name, config_json, created_at
            FROM core_configs
            ORDER BY version DESC
        ''')
        
        configs = []
        for row in cursor.fetchall():
            configs.append({
                'id': row[0],
                'version': row[1],
                'device_names': json.loads(row[2]) if row[2] else [],
                'service_name': row[3],
                'config': json.loads(row[4]) if row[4] else {},
                'created_at': row[5]
            })
        
        conn.close()
        return web.json_response({'success': True, 'configs': configs})
        
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def api_core_config_latest(request):
    """GET /api/pipeline/core-config/latest -- get the latest core config"""
    _require_admin(request)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, version, device_names, service_name, config_json, created_at
            FROM core_configs
            ORDER BY version DESC
            LIMIT 1
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return web.json_response({
                'success': True,
                'config': {
                    'id': row[0],
                    'version': row[1],
                    'device_names': json.loads(row[2]) if row[2] else [],
                    'service_name': row[3],
                    'config': json.loads(row[4]) if row[4] else {},
                    'created_at': row[5]
                }
            })
        else:
            return web.json_response({'success': True, 'config': None})
        
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


def create_app():
    # Monkey-patch ws_auth in every module that uses it so they all call
    # _ws_auth_main which has direct access to WEBUI_SESSIONS in this module.
    # This fixes the stale-import problem: auth.py's ws_auth does
    # "from main import WEBUI_SESSIONS" which copies the dict reference at
    # import time. If the dict is replaced or module reloaded the copy goes
    # stale. _ws_auth_main reads WEBUI_SESSIONS directly from this scope.
    import auth as _auth_mod
    import general as _general_mod
    import pipeline as _pipeline_mod
    import device_management as _dm_mod
    _auth_mod.ws_auth     = _ws_auth_main
    _general_mod.ws_auth  = _ws_auth_main
    _pipeline_mod.ws_auth = _ws_auth_main

    # Also patch device_management._require_webui_session for the same reason.
    def _require_webui_session_main(request):
        token = request.cookies.get('gw_webui_session')
        if not token:
            raise web.HTTPUnauthorized(reason='No session cookie')
        session = WEBUI_SESSIONS.get(token)
        if not session:
            raise web.HTTPUnauthorized(reason='Session expired or invalid')
        return session.get('username') if isinstance(session, dict) else session
    _dm_mod._require_webui_session = _require_webui_session_main

    async def security_headers_middleware_factory(app, handler):
        async def security_headers_middleware(request):
            try:
                response = await handler(request)
                if isinstance(response, web.StreamResponse):
                    response.headers['X-Content-Type-Options'] = 'nosniff'
                    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
                    response.headers['X-XSS-Protection'] = '1; mode=block'
                    response.headers['Content-Security-Policy'] = "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: ws: wss:;"
                return response
            except web.HTTPException as ex:
                ex.headers['X-Content-Type-Options'] = 'nosniff'
                ex.headers['X-Frame-Options'] = 'SAMEORIGIN'
                ex.headers['X-XSS-Protection'] = '1; mode=block'
                ex.headers['Content-Security-Policy'] = "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: ws: wss:;"
                raise
        return security_headers_middleware

    app = web.Application(middlewares=[security_headers_middleware_factory])

    app.router.add_get('/admin/login', admin_login_page)
    app.router.add_post('/admin/login', admin_login_post)
    app.router.add_get('/admin/logout', admin_logout)
    app.router.add_get('/api/admin/session-check', admin_session_check)
    app.router.add_get('/admin', admin_root)
    app.router.add_get('/admin/', admin_root)
    app.router.add_get('/admin/pipeline', admin_pipeline_page)
    app.router.add_get('/admin/database', admin_database_page)
    app.router.add_get('/admin/users', admin_users_page)
    app.router.add_get('/admin/access-control', admin_access_control_page)
    app.router.add_get('/api/admin/webui-pages', api_webui_pages_get)
    app.router.add_put('/api/admin/webui-pages', api_webui_page_restriction_put)

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
    app.router.add_put('/api/admin/users/webui/{id}/max-sessions', api_webui_user_max_sessions_put)
    app.router.add_get('/api/admin/webui-sessions', api_webui_sessions_get)
    app.router.add_delete('/api/admin/webui-sessions/{token}', api_webui_session_kill)

    # /api/auth/login is registered AFTER register_auth_routes so our
    # single-session webui_login_api handler wins over auth.py's version.

    app.router.add_get('/api/admin/db-path', api_db_path_get)
    app.router.add_put('/api/admin/db-path', api_db_path_put)

    register_general_config_routes(app)

    # Register our session handlers FIRST so they win over auth.py's versions
    app.router.add_post('/api/auth/login', webui_login_api)
    app.router.add_post('/api/auth/logout', webui_logout_api)
    app.router.add_get('/api/auth/status', webui_session_status)
    app.router.add_get('/api/auth/session-role', webui_session_role)
    
    # Patch register_auth_routes: temporarily wrap add_route/add_get/add_post
    # so duplicate registrations from auth.py are silently skipped
    _owned = {'/api/auth/login', '/api/auth/logout', '/api/auth/status', '/api/auth/session-role'}
    _orig_add_route = app.router.add_route
    _orig_add_get   = app.router.add_get
    _orig_add_post  = app.router.add_post
    def _safe_add_route(method, path, handler, **kw):
        if path in _owned: return
        return _orig_add_route(method, path, handler, **kw)
    def _safe_add_get(path, handler, **kw):
        if path in _owned: return
        return _orig_add_get(path, handler, **kw)
    def _safe_add_post(path, handler, **kw):
        if path in _owned: return
        return _orig_add_post(path, handler, **kw)
    app.router.add_route = _safe_add_route
    app.router.add_get   = _safe_add_get
    app.router.add_post  = _safe_add_post
    register_auth_routes(app)
    app.router.add_route = _orig_add_route  # restore
    app.router.add_get   = _orig_add_get
    app.router.add_post  = _orig_add_post
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
    app.router.add_get('/api/port-config', get_port_config_api)

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

    # Core Config JSON Upload endpoints
    app.router.add_post('/api/pipeline/core-config/upload', api_core_config_upload)
    app.router.add_get('/api/pipeline/core-configs', api_core_configs_list)
    app.router.add_get('/api/pipeline/core-config/latest', api_core_config_latest)

    async def db_redirect(request):
        raise web.HTTPFound('/admin/database')
    app.router.add_get('/db', db_redirect)

    async def debug_sessions(request):
        """GET /api/debug/sessions - show active WEBUI_SESSIONS (dev only)"""
        sessions_info = {}
        for token, info in WEBUI_SESSIONS.items():
            username = info.get('username') if isinstance(info, dict) else info
            sessions_info[token[:12] + '...'] = username
        cookie_token = request.cookies.get('gw_webui_session', '')
        found = cookie_token in WEBUI_SESSIONS
        return web.json_response({
            'total_sessions': len(WEBUI_SESSIONS),
            'sessions': sessions_info,
            'cookie_token_prefix': cookie_token[:12] + '...' if cookie_token else 'NO COOKIE',
            'cookie_found_in_sessions': found,
            'ws_auth_result': _ws_auth_main(request),
        })
    app.router.add_get('/api/debug/sessions', debug_sessions)

    # Logs page + API
    import log_handler as _lh
    _lh.register_routes(app)
    async def _logs_page(request):
        _require_admin(request)
        return _html('logs.html')
    app.router.add_get('/admin/logs', _logs_page)

    # ---------------------------------------------------------------------------
    # Static assets served from admin_ui/public/
    # Structure: public/css/*.css  public/fonts/**/*.woff2
    # ---------------------------------------------------------------------------
    _PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin_ui", "public")
    if os.path.isdir(_PUBLIC_DIR):
        app.router.add_static("/css",   os.path.join(_PUBLIC_DIR, "css"),   show_index=False, follow_symlinks=True)
        app.router.add_static("/fonts", os.path.join(_PUBLIC_DIR, "fonts"), show_index=False, follow_symlinks=True)

    # Silence favicon 404
    async def _favicon(request):
        _fav = os.path.join(os.path.dirname(os.path.abspath(__file__)), "favicon.ico")
        if os.path.isfile(_fav):
            with open(_fav, "rb") as f:
                return web.Response(body=f.read(), content_type="image/x-icon")
        return web.Response(status=204)
    app.router.add_get("/favicon.ico", _favicon)

    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    return app

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("  Gateway Admin Server Starting (OPTIMIZED)")
    logger.info("=" * 60)
    logger.info("\nInitializing database...")
    # OPTIMIZATION: Call ensure_db_initialized instead of init_database
    # This runs only once and supports lazy initialization
    ensure_db_initialized()
    logger.info("\nAdmin Panel : http://0.0.0.0:8082/admin")
    logger.info("Default login: admin / admin123")
    logger.info("=" * 60 + "\n")
    web.run_app(create_app(), host='0.0.0.0', port=8082)