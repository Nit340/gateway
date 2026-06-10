# -*- coding: utf-8 -*-
# auth.py - Session-based authentication helpers
# Routes are registered in main.py

import logging
from aiohttp import web

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# WebSocket auth helper
# Reads the gw_webui_session cookie and returns the real username from
# WEBUI_SESSIONS (maintained in main.py).  Returns None if the session
# is missing or expired so callers can reject the WebSocket upgrade.
# ---------------------------------------------------------------------------
def ws_auth(request):
    """
    Validate the WebSocket request against the active webui session store.

    Returns the username string on success, or None if unauthenticated.
    The WebSocket handlers in general.py check for None and return HTTP 401.

    IMPORTANT: we access main.WEBUI_SESSIONS through the module object, never
    via 'from main import WEBUI_SESSIONS'.  A direct import copies the reference
    at import time -- if main.py ever reassigns the dict the copy goes stale and
    every lookup returns None.  Accessing it as an attribute on the module always
    reads the live object.
    """
    try:
        import main as _main
        sessions = _main.WEBUI_SESSIONS
    except (ImportError, AttributeError):
        logger.warning("[AUTH] ws_auth: could not access main.WEBUI_SESSIONS")
        return None

    token = request.cookies.get('gw_webui_session')
    if not token:
        return None

    session = sessions.get(token)
    if not session:
        return None

    if isinstance(session, dict):
        return session.get('username')

    return session if isinstance(session, str) else None


# ---------------------------------------------------------------------------
# HTTP handler functions
# ---------------------------------------------------------------------------
async def login_handler(request):
    # The real login is handled by webui_login_api in main.py.
    # This stub is kept so register_auth_routes() doesn't break if called
    # before main.py patches the router.
    return web.json_response({'success': False, 'error': 'Use /api/auth/login'}, status=400)


async def logout_handler(request):
    return web.json_response({'success': True, 'message': 'Logged out.'})


async def auth_status_handler(request):
    """
    GET /api/auth/status
    Returns authenticated=True only when a valid webui session cookie exists.
    """
    try:
        import main as _main
        sessions = _main.WEBUI_SESSIONS
        token = request.cookies.get('gw_webui_session')
        if token and token in sessions:
            sess = sessions[token]
            username = sess.get('username') if isinstance(sess, dict) else sess
            return web.json_response({'authenticated': True, 'username': username})
    except (ImportError, AttributeError):
        pass
    return web.json_response({'authenticated': False}, status=401)


# ---------------------------------------------------------------------------
# Route registration - called from main.py
# ---------------------------------------------------------------------------
def register_auth_routes(app):
    """Register auth routes onto an aiohttp Application.

    NOTE: main.py registers /api/auth/login, /api/auth/logout, and
    /api/auth/status with its own richer handlers *before* calling this
    function, and patches app.router to skip duplicates.  The add_get call
    below is therefore a no-op for /api/auth/status when main.py is in charge,
    which is the desired behaviour.
    """
    app.router.add_get('/api/auth/status', auth_status_handler)