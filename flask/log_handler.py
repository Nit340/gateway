# -*- coding: utf-8 -*-
# log_handler.py
#
# Single file that:
#   1. Fixes logging so every logger.xxx() prints (basicConfig was missing)
#   2. Captures every print() via stdout wrap
#   3. Holds per-module ON/OFF + level settings in memory
#   4. When a module is OFF -> its logs are SUPPRESSED everywhere (terminal + buffer)
#   5. Serves REST API for the Logs page
#
# Usage in main.py (add these 2 lines):
#   import log_handler          <- top of file, before other imports
#   log_handler.install()       <- right after the import
#   log_handler.register_routes(app)   <- inside create_app()

import collections
import logging
import sys
import threading
import time
from datetime import datetime

# ---------------------------------------------------------------------------
# Module list + prefix detection
# ---------------------------------------------------------------------------
ALL_MODULES = ['main', 'database', 'pipeline', 'general',
               'device_management', 'tag_mapping', 'mqtt_cloud', 'rules', 'auth']

_PREFIX_MAP = [
    ('[MAIN]',       'main'),    ('[CORE-CFG]', 'main'),
    ('[PIPELINE]',   'pipeline'),('[WHITELIST]','pipeline'),('[LC',       'pipeline'),
    ('[DB',          'database'),
    ('[AUTH]',       'auth'),
    ('[GENERAL]',    'general'), ('[NET-STATUS]','general'),('[WIFI-SCAN]','general'),
    ('[EXT]',        'device_management'),
    ('[IOT-CFG]',    'mqtt_cloud'),('[MQTT]','mqtt_cloud'),
    ('[RULES]',      'rules'),
]

VALID_LEVELS = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
_LEVEL_NO    = {l: getattr(logging, l) for l in VALID_LEVELS}

# ---------------------------------------------------------------------------
# Per-module settings  { module: {'enabled': bool, 'level': 'DEBUG'} }
# ---------------------------------------------------------------------------
_settings_lock = threading.Lock()
_settings = {m: {'enabled': True, 'level': 'DEBUG'} for m in ALL_MODULES}

def _is_allowed(module: str, level: str) -> bool:
    """Return True if this log entry should be shown/stored."""
    with _settings_lock:
        s = _settings.get(module, {'enabled': True, 'level': 'DEBUG'})
    if not s['enabled']:
        return False
    return _LEVEL_NO.get(level, 20) >= _LEVEL_NO.get(s['level'], 10)

# ---------------------------------------------------------------------------
# Ring buffer
# ---------------------------------------------------------------------------
_RING_SIZE = 2000
_ring      = collections.deque(maxlen=_RING_SIZE)
_ring_lock = threading.Lock()
_id_counter = 0

def _push(module: str, level: str, message: str):
    global _id_counter
    if not _is_allowed(module, level):
        return
    with _ring_lock:
        _id_counter += 1
        _ring.append({
            'id':        _id_counter,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ts':        time.time(),
            'level':     level,
            'module':    module,
            'message':   message,
        })

# ---------------------------------------------------------------------------
# Detect module from print() prefix tags
# ---------------------------------------------------------------------------
def _detect_module(line: str) -> str:
    for prefix, mod in _PREFIX_MAP:
        if line.startswith(prefix):
            return mod
    return 'main'

def _detect_level(line: str) -> str:
    u = line.upper()
    if 'CRITICAL' in u: return 'CRITICAL'
    if 'ERROR'    in u: return 'ERROR'
    if 'WARNING'  in u or 'WARN' in u: return 'WARNING'
    if 'DEBUG'    in u: return 'DEBUG'
    return 'INFO'

# ---------------------------------------------------------------------------
# stdout wrapper — captures every print()
# ---------------------------------------------------------------------------
class _StdoutCapture:
    def __init__(self, real):
        self._real = real
        self._buf  = ''

    def write(self, text):
        self._buf += text
        while '\n' in self._buf:
            line, self._buf = self._buf.split('\n', 1)
            line = line.rstrip('\r')
            if not line:
                continue
            module = _detect_module(line)
            level  = _detect_level(line)
            # Only write to terminal AND ring buffer if module settings allow
            if _is_allowed(module, level):
                self._real.write(line + '\n')
                self._real.flush()
                _push(module, level, line)
        return len(text)

    def flush(self):   self._real.flush()
    def __getattr__(self, n): return getattr(self._real, n)

# ---------------------------------------------------------------------------
# logging handler — captures every logger.xxx()
# ---------------------------------------------------------------------------
class _RingHandler(logging.Handler):
    def emit(self, record):
        try:
            name   = record.name or 'main'
            module = name if name in ALL_MODULES else _detect_module(record.getMessage())
            level  = record.levelname
            msg    = self.format(record)
            # Push to ring buffer only if allowed
            _push(module, level, msg)
        except Exception:
            pass


class _FilteringStreamHandler(logging.StreamHandler):
    """
    Replaces the default basicConfig StreamHandler.
    Suppresses terminal output for disabled modules — the standard
    StreamHandler has no awareness of our per-module settings.
    """
    def emit(self, record):
        try:
            name   = record.name or 'main'
            module = name if name in ALL_MODULES else _detect_module(record.getMessage())
            level  = record.levelname
            if not _is_allowed(module, level):
                return   # suppress — module is OFF or below its level threshold
            super().emit(record)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# install() — call once at very top of main.py
# ---------------------------------------------------------------------------
_installed = False

def install():
    global _installed
    if _installed:
        return
    _installed = True

    fmt = logging.Formatter(
        '[%(asctime)s] %(levelname)-8s %(name)s: %(message)s',
        datefmt='%H:%M:%S',
    )

    # Set root logger level — handlers do the real filtering
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Remove any existing StreamHandlers so basicConfig output doesn't bypass our filter
    root_logger.handlers = [
        h for h in root_logger.handlers
        if not isinstance(h, logging.StreamHandler) or isinstance(h, (_RingHandler, _FilteringStreamHandler))
    ]

    # Our filtering terminal handler — respects per-module enabled/level settings
    fsh = _FilteringStreamHandler(sys.stdout)
    fsh.setLevel(logging.DEBUG)
    fsh.setFormatter(fmt)
    root_logger.addHandler(fsh)
    
    # Reduce noise from aiohttp internals
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    # Ring buffer handler — stores entries for the Logs UI page
    rh = _RingHandler()
    rh.setLevel(logging.DEBUG)
    rh.setFormatter(fmt)
    root_logger.addHandler(rh)

    # Wrap stdout so print() calls are also captured
    if not isinstance(sys.stdout, _StdoutCapture):
        sys.stdout = _StdoutCapture(sys.stdout)

# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------
def get_logs(limit=500, module='ALL', level='ALL', search=''):
    with _ring_lock:
        rows = list(_ring)
    if module and module != 'ALL':
        rows = [r for r in rows if r['module'] == module]
    if level and level != 'ALL':
        min_no = _LEVEL_NO.get(level, 0)
        rows   = [r for r in rows if _LEVEL_NO.get(r['level'], 0) >= min_no]
    if search:
        sl   = search.lower()
        rows = [r for r in rows if sl in r['message'].lower()]
    return rows[-limit:]

def get_settings():
    with _settings_lock:
        return {m: dict(v) for m, v in _settings.items()}

def update_setting(module: str, enabled: bool = None, level: str = None) -> bool:
    if module not in ALL_MODULES:
        return False
    with _settings_lock:
        if enabled is not None:
            _settings[module]['enabled'] = bool(enabled)
        if level is not None and level in _LEVEL_NO:
            _settings[module]['level'] = level
    return True

def clear_ring():
    with _ring_lock:
        _ring.clear()

# ---------------------------------------------------------------------------
# REST routes — call register_routes(app) inside create_app()
# ---------------------------------------------------------------------------
def register_routes(app):
    from aiohttp import web

    def _auth(request):
        import sys
        main_module = sys.modules['__main__']
        main_module._require_admin(request)

    async def api_logs_get(request):
        _auth(request)
        q      = request.rel_url.query
        limit  = min(int(q.get('limit', 500)), _RING_SIZE)
        module = q.get('module', 'ALL')
        level  = q.get('level',  'ALL')
        search = q.get('search', '')
        return web.json_response({'logs': get_logs(limit, module, level, search)})

    async def api_logs_delete(request):
        _auth(request)
        clear_ring()
        return web.json_response({'success': True})

    async def api_settings_get(request):
        _auth(request)
        s = get_settings()
        rows = [{'module': m, 'enabled': v['enabled'], 'level': v['level']} for m, v in s.items()]
        return web.json_response({'settings': rows, 'modules': ALL_MODULES, 'levels': list(VALID_LEVELS)})

    async def api_settings_put(request):
        _auth(request)
        try:
            body    = await request.json()
            module  = body.get('module', '').strip()
            enabled = body.get('enabled')   # None means not changing
            level   = (body.get('level') or '').upper().strip() or None
            if not update_setting(module, enabled=enabled, level=level):
                return web.json_response({'success': False, 'error': 'Unknown module or invalid level'}, status=400)
            return web.json_response({'success': True})
        except Exception as e:
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    app.router.add_get   ('/api/admin/logs',          api_logs_get)
    app.router.add_delete('/api/admin/logs',          api_logs_delete)
    app.router.add_get   ('/api/admin/log-settings',  api_settings_get)
    app.router.add_put   ('/api/admin/log-settings',  api_settings_put)