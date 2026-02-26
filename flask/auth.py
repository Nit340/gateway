# -*- coding: utf-8 -*-
# auth.py - Authentication functions only
# Routes are registered in main.py

import json
import logging
import os
import hmac
import hashlib
from datetime import datetime, timedelta
from aiohttp import web

# ---------------------------------------------------------------------------
# Credentials - passwords stored as SHA-256 hashes
# To generate: hashlib.sha256("yourpassword".encode()).hexdigest()
# ---------------------------------------------------------------------------
def _hash(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

USERS = {
    'admin': _hash('admin'),  # change 'admin' password before production!
}

# ---------------------------------------------------------------------------
# Session token store { token: {"username": str, "expires": datetime} }
# ---------------------------------------------------------------------------
_sessions = {}
SESSION_MAX_AGE = 8 * 3600   # 8 hours
COOKIE_NAME = 'gw_session'


def _create_session(username):
    token = os.urandom(32).hex()  # 256-bit random token
    _sessions[token] = {
        'username': username,
        'expires': datetime.utcnow() + timedelta(seconds=SESSION_MAX_AGE),
    }
    return token


def _validate_token(token):
    """Return username if token valid and not expired, else None."""
    if not token:
        return None
    session = _sessions.get(token)
    if not session:
        return None
    if datetime.utcnow() > session['expires']:
        del _sessions[token]
        return None
    return session['username']


def _delete_token(token):
    if token and token in _sessions:
        del _sessions[token]


# ---------------------------------------------------------------------------
# WebSocket auth helper - call at top of every WS handler
# ---------------------------------------------------------------------------
def ws_auth(request):
    """
    Returns authenticated username or None.

    Usage in any WebSocket handler:
        user = ws_auth(request)
        if user is None:
            return web.Response(status=401, text='Unauthorized')
    """
    token = request.cookies.get(COOKIE_NAME)
    return _validate_token(token)


# ---------------------------------------------------------------------------
# Middleware - protects all non-public HTTP routes automatically
# ---------------------------------------------------------------------------
PUBLIC_PATHS = {
    '/api/auth/login',
    '/api/auth/logout',
    '/api/auth/status',
    '/',
    '/docs',
}

async def auth_middleware(app, handler):
    """aiohttp 2.x middleware factory style."""
    async def middleware(request):
        # Always allow public paths
        if request.path in PUBLIC_PATHS or request.method == 'OPTIONS':
            return await handler(request)

        # WS upgrades are checked inside the handler via ws_auth()
        if request.headers.get('Upgrade', '').lower() == 'websocket':
            return await handler(request)

        token = request.cookies.get(COOKIE_NAME)
        user = _validate_token(token)
        if user is None:
            return web.json_response(
                {'authenticated': False, 'error': 'Login required.'},
                status=401
            )

        request['user'] = user
        return await handler(request)
    return middleware


# ---------------------------------------------------------------------------
# Handler functions
# ---------------------------------------------------------------------------
async def login_handler(request):
    try:
        body = await request.json()
        username = (body.get('username') or '').strip()
        password = (body.get('password') or '')

        if not username or not password:
            return web.json_response(
                {'success': False, 'error': 'Username and password are required.'},
                status=400
            )

        expected_hash = USERS.get(username)
        if expected_hash is None or not hmac.compare_digest(
            expected_hash, _hash(password)
        ):
            logging.warning("Failed login for user: %s from %s", username, request.remote)
            return web.json_response(
                {'success': False, 'error': 'Invalid username or password.'},
                status=401
            )

        token = _create_session(username)
        response = web.json_response({'success': True, 'username': username})
        response.set_cookie(
            COOKIE_NAME,
            token,
            httponly=True,
            max_age=SESSION_MAX_AGE,
            # secure=True,  # uncomment when serving over HTTPS
        )
        logging.info("Login successful for user: %s", username)
        return response

    except json.JSONDecodeError:
        return web.json_response(
            {'success': False, 'error': 'Invalid JSON body.'},
            status=400
        )
    except Exception as e:
        logging.error("Login error: %s", e)
        return web.json_response(
            {'success': False, 'error': 'Server error. Please try again.'},
            status=500
        )


async def logout_handler(request):
    token = request.cookies.get(COOKIE_NAME)
    _delete_token(token)
    response = web.json_response({'success': True, 'message': 'Logged out.'})
    response.del_cookie(COOKIE_NAME)
    logging.info("User logged out.")
    return response


async def auth_status_handler(request):
    token = request.cookies.get(COOKIE_NAME)
    user = _validate_token(token)
    if user:
        return web.json_response({'authenticated': True, 'username': user})
    return web.json_response({'authenticated': False}, status=401)


# ---------------------------------------------------------------------------
# Route registration - called from main.py
# ---------------------------------------------------------------------------
def register_auth_routes(app):
    """Register all auth routes onto an aiohttp Application."""
    app.router.add_post('/api/auth/login',  login_handler)
    app.router.add_post('/api/auth/logout', logout_handler)
    app.router.add_get ('/api/auth/status', auth_status_handler)