# -*- coding: utf-8 -*-
# auth.py - Authentication disabled, all routes open
# Routes are registered in main.py

from aiohttp import web


# ---------------------------------------------------------------------------
# WebSocket auth helper - always returns a default user (no auth)
# ---------------------------------------------------------------------------
def ws_auth(request):
    """Auth disabled - always returns default user."""
    return 'guest'


# ---------------------------------------------------------------------------
# Handler functions - always succeed
# ---------------------------------------------------------------------------
async def login_handler(request):
    return web.json_response({'success': True, 'username': 'guest'})


async def logout_handler(request):
    return web.json_response({'success': True, 'message': 'Logged out.'})


async def auth_status_handler(request):
    return web.json_response({'authenticated': True, 'username': 'guest'})


# ---------------------------------------------------------------------------
# Route registration - called from main.py
# ---------------------------------------------------------------------------
def register_auth_routes(app):
    """Register all auth routes onto an aiohttp Application."""
    app.router.add_post('/api/auth/login',  login_handler)
    app.router.add_post('/api/auth/logout', logout_handler)
    app.router.add_get ('/api/auth/status', auth_status_handler)