# -*- coding: utf-8 -*-
# auth.py - Authentication API
# Default credentials: admin / admin
# Register routes by calling register_auth_routes(app) in main.py.

import json
import logging
from aiohttp import web

# ---------------------------------------------------------------------------
# Credentials store (replace with DB lookup when needed)
# ---------------------------------------------------------------------------
USERS = {
    'admin': 'admin',   # username: password
}


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def login_handler(request):
    """POST /api/auth/login
    Body: { "username": "admin", "password": "admin" }
    Returns: { "success": true, "username": "admin" }
          or { "success": false, "error": "..." }
    """
    try:
        body = await request.json()
        username = (body.get('username') or '').strip()
        password = (body.get('password') or '')

        if not username or not password:
            return web.json_response(
                {'success': False, 'error': 'Username and password are required.'},
                status=400
            )

        expected = USERS.get(username)
        if expected is None or expected != password:
            return web.json_response(
                {'success': False, 'error': 'Invalid username or password.'},
                status=401
            )

        # Set a simple server-side session cookie
        response = web.json_response({'success': True, 'username': username})
        response.set_cookie(
            'gw_session',
            username,
            httponly=True,
            samesite='Strict',
            max_age=8 * 3600  # 8 hours
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
    """POST /api/auth/logout
    Clears the session cookie and returns success.
    """
    response = web.json_response({'success': True, 'message': 'Logged out.'})
    response.del_cookie('gw_session')
    logging.info("User logged out.")
    return response


async def auth_status_handler(request):
    """GET /api/auth/status
    Returns whether the current session is authenticated.
    """
    session_user = request.cookies.get('gw_session')
    if session_user and session_user in USERS:
        return web.json_response({'authenticated': True, 'username': session_user})
    return web.json_response({'authenticated': False}, status=401)


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_auth_routes(app):
    """Register authentication routes onto an aiohttp Application."""
    app.router.add_post('/api/auth/login',  login_handler)
    app.router.add_post('/api/auth/logout', logout_handler)
    app.router.add_get ('/api/auth/status', auth_status_handler)