# -*- coding: utf-8 -*-
# rules.py - Rules Engine API
#
# MODIFIED: Core config now uses a single row in database with version tracking
# via updated_at timestamp. No local JSON files are generated.

import json
import os
import sqlite3
from datetime import datetime
from aiohttp import web
import database
from database import get_db_connection
from logger_util import get_logger


logger = get_logger(__name__)

def get_db():
    conn = sqlite3.connect(database.DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# GET /api/rules/tags  -- all enabled modbus tag names
# ---------------------------------------------------------------------------
async def rules_tags_handler(request):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''
            SELECT dp.name,
                   COALESCE(d.name, dp.device_id) AS device_name
            FROM external_datapoints dp
            LEFT JOIN external_device d ON d.id = dp.device_id
            WHERE dp.enabled=1 ORDER BY dp.name
        ''')
        tags = [{'name': r['name'], 'device_name': r['device_name']} for r in cur.fetchall()]
        conn.close()
        return web.json_response({'success': True, 'tags': tags})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# GET /api/rules  -- all saved rules
# ---------------------------------------------------------------------------
async def rules_list_handler(request):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('SELECT * FROM rules ORDER BY created_at DESC')
        rows = []
        for row in cur.fetchall():
            r = dict(row)
            try:
                r['groups'] = json.loads(r.get('groups_json') or '{}')
            except Exception:
                r['groups'] = {}
            rows.append(r)
        conn.close()
        return web.json_response({'success': True, 'rules': rows})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# POST /api/rules/save  -- DB only, NO pipeline send
# ---------------------------------------------------------------------------
async def rules_save_handler(request):
    try:
        body = await request.json()
        rule = body.get('rule')
        if not rule:
            return web.json_response({'success': False, 'error': 'Missing rule'})

        conn = get_db()
        cur = conn.cursor()

        rule_id = rule['id']
        name = rule.get('name', '')
        rule_type = rule.get('ruleType', 'group')
        priority = rule.get('priority', 'medium')
        description = rule.get('description', '')
        enabled = 1 if rule.get('enabled', True) else 0
        groups_json = json.dumps(rule.get('groups', {}))
        relay_dp = rule.get('relayDatapoint', '')

        cur.execute('SELECT id FROM rules WHERE id=?', (rule_id,))
        if cur.fetchone():
            cur.execute('''
                UPDATE rules
                SET name=?, rule_type=?, priority=?, description=?,
                    enabled=?, groups_json=?, relay_datapoint=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            ''', (name, rule_type, priority, description,
                  enabled, groups_json, relay_dp, rule_id))
        else:
            cur.execute('''
                INSERT INTO rules
                    (id, name, rule_type, priority, description, enabled,
                     groups_json, relay_datapoint, updated_at)
                VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
            ''', (rule_id, name, rule_type, priority, description,
                  enabled, groups_json, relay_dp))

        conn.commit()
        conn.close()

        return web.json_response({'success': True})

    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# DELETE /api/rules/{rule_id}
# ---------------------------------------------------------------------------
async def rules_delete_handler(request):
    rule_id = request.match_info.get('rule_id')
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('DELETE FROM rules WHERE id=?', (rule_id,))
        conn.commit()
        conn.close()
        return web.json_response({'success': True})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# POST /api/rules/pipeline/trigger
#
# Reads ALL enabled rules from DB, builds a single combined core_config JSON
# and sends it to the core pipeline service.
# ---------------------------------------------------------------------------
async def rules_pipeline_trigger_handler(request):
    try:
        result = await _build_and_send_core_config()
        return web.json_response({'success': True, 'pipeline': result})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# POST /api/rules/core-config/upload
#
# Upload and save core config JSON (replaces existing config), optionally send to pipeline.
# ---------------------------------------------------------------------------
async def core_config_upload_handler(request):
    """POST /api/rules/core-config/upload
    Upload and save core config JSON, optionally send to pipeline.
    REPLACES existing config - only one row is kept.
    """
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
        
        # Save to core_configs table - SINGLE ROW ONLY
        conn = get_db()
        cursor = conn.cursor()
        
        # Ensure table exists with version column
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS core_configs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                version      INTEGER NOT NULL DEFAULT 1,
                device_names TEXT,
                service_name TEXT,
                config_json  TEXT NOT NULL,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
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
        
        service_name = config.get('service_name', 'ilx_craneiq_core')
        
        # Check if we already have a config - UPDATE instead of INSERT
        cursor.execute('SELECT id, version FROM core_configs LIMIT 1')
        existing = cursor.fetchone()
        
        if existing:
            # Core config schema version is always fixed at 2 -- no auto-increment
            new_version = 2
            cursor.execute('''
                UPDATE core_configs 
                SET version = ?, 
                    device_names = ?, 
                    service_name = ?, 
                    config_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_version, json.dumps(device_names), service_name, config_json, existing['id']))
            logger.info("[CORE-CFG] Updated config (version fixed at 2) from JSON")
        else:
            new_version = 2
            cursor.execute('''
                INSERT INTO core_configs (version, device_names, service_name, config_json, updated_at) 
                VALUES (2, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (json.dumps(device_names), service_name, config_json))
            logger.info("[CORE-CFG] Inserted initial config (version fixed at 2) from JSON")
        
        conn.commit()
        conn.close()
        
        # Optionally send to pipeline
        sent = False
        queued = False
        if send_to_pipeline:
            try:
                from pipeline import pipeline_state, get_pipeline_service_name, get_pipeline_config_name
                from pipeline import record_pipeline_send_success, record_pipeline_send_failure
                from pipeline import Config
                
                core_svc = get_pipeline_service_name('core') or 'ilx_craneiq_core'
                cfg_name = get_pipeline_config_name('core')
                
                with pipeline_state.get('lock', None):
                    # If we can't get lock, try without it
                    client = pipeline_state.get('client')
                    connected = pipeline_state.get('connected', False)
                    services = set(pipeline_state.get('connected_services', set()))
                
                if connected and client and core_svc in services:
                    new_version = 2  # Core config schema version is always fixed at 2 -- no auto-increment
                    ok = client.publish_config(Config(
                        name=cfg_name,
                        value=config_json,
                        version=new_version,
                        service=core_svc,
                    ))
                    if ok:
                        record_pipeline_send_success('core', new_version, core_svc, 
                                                     'Uploaded JSON')
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
            'message': 'Config saved to DB' + 
                       (' and sent to pipeline' if sent else 
                        (' and queued for pipeline' if queued else ''))
        })
        
    except Exception as e:
        logger.error('[CORE-CFG] Upload error: {}'.format(e))
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# GET /api/rules/core-configs
#
# List all saved core configs (now only returns the single row)
# ---------------------------------------------------------------------------
async def core_configs_list_handler(request):
    """GET /api/rules/core-configs - List saved core configs (only one row exists)"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, version, device_names, service_name, config_json, created_at, updated_at
            FROM core_configs
            ORDER BY updated_at DESC
            LIMIT 1
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return web.json_response({
                'success': True, 
                'configs': [{
                    'id': row[0],
                    'version': row[1],
                    'device_names': json.loads(row[2]) if row[2] else [],
                    'service_name': row[3],
                    'config': json.loads(row[4]) if row[4] else {},
                    'created_at': row[5],
                    'updated_at': row[6]
                }]
            })
        else:
            return web.json_response({'success': True, 'configs': []})
        
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# GET /api/rules/core-config/latest
#
# Get the latest core config (always the single row)
# ---------------------------------------------------------------------------
async def core_config_latest_handler(request):
    """GET /api/rules/core-config/latest - Get the latest core config"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, version, device_names, service_name, config_json, created_at, updated_at
            FROM core_configs
            ORDER BY updated_at DESC
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
                    'created_at': row[5],
                    'updated_at': row[6]
                }
            })
        else:
            return web.json_response({'success': True, 'config': None})
        
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# GET /api/rules/core-config/preview
#
# Preview the generated core config JSON (built from current rules/devices)
# ---------------------------------------------------------------------------
async def core_config_preview_handler(request):
    """GET /api/rules/core-config/preview - Preview the generated core config"""
    try:
        # Get latest loadcell params from DB regardless of stored config
        lc_params = _get_loadcell_service_params()
        
        # First try to get the latest from DB
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT config_json FROM core_configs ORDER BY updated_at DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            config = json.loads(row[0])
            # Inject/Override with latest DB truth for loadcell
            if 'services' in config and 'loadcell' in config['services']:
                lc = config['services']['loadcell']
                lc['overload_threshold_grams'] = lc_params['overload_threshold_grams']
                lc['overload_deadband_grams']  = lc_params['overload_deadband_grams']
                lc['datapoint_name']            = lc_params['datapoint_name']
                lc['unit_datapoint_name']       = lc_params['unit_datapoint_name']
            return web.json_response({'success': True, 'config': config})
            
        # Fallback to building from rules
        rules = _collect_all_enabled_rules()
        core_config = _build_combined_core_config(rules)
        return web.json_response({'success': True, 'config': core_config})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _collect_all_enabled_rules():
    """Return all enabled rules from DB as list of dicts."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM rules WHERE enabled=1 ORDER BY created_at ASC")
    rows = []
    for row in cur.fetchall():
        r = dict(row)
        try:
            r['groups'] = json.loads(r.get('groups_json') or '{}')
        except Exception:
            r['groups'] = {}
        rows.append(r)
    conn.close()
    return rows


def _get_loadcell_service_params():
    """
    Auto-discover loadcell params from the first enabled row.
    """
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''
            SELECT
                name,
                load_name,
                capacity_name,
                deadband, 
                overload
            FROM loadcell_device
            WHERE enabled = 1
            ORDER BY created_at ASC
            LIMIT 1
        ''')
        row = cur.fetchone()
        conn.close()
        if row:
            dev_name = row['name'] or "load"
            # Build the full datapoint names with the proper prefix
            dp_name = "loadcells.{}.weight".format(dev_name)
            unit_name = "loadcells.{}.unit".format(dev_name)
            return {
                'datapoint_name': dp_name,
                'unit_datapoint_name': unit_name,
                'overload_deadband_grams': row['deadband'] or 0.0,
                'overload_threshold_grams': row['overload'] or 0.0,
                'device_name': dev_name  # Also return the device name for reference
            }
    except Exception as e:
        logger.error('[RULES] loadcell auto-discovery error: {} -- using defaults'.format(e))
    return {
        'datapoint_name': 'weight',  # Fallback to default
        'unit_datapoint_name': 'unit',
        'overload_deadband_grams': 0.0,
        'overload_threshold_grams': 0.0,
        'device_name': None
    }
def _build_combined_core_config(rules):
    """
    Build the full core_config dict from all enabled rules.

    The loadcell section is built AUTOMATICALLY from the loadcell_device DB --
    no UI input is needed for datapoint_name or unit_datapoint_name.

    Resulting shape matches ilx_craneiq_core-config.json exactly:

    {
      "service_name": "ilx_craneiq_core",
      "pipeline": { "server", "port", ... },
      "services": {
        "modbus": {
          "service_name": "modbus_service",
          "groups": [...]
        },
        "loadcell": {
          "service_name":        "load_cell_service",
          "datapoint_name":      <auto from DB>,
          "unit_datapoint_name": <auto from DB>
        },
        "emergency_output": {     <- only if an emergency rule exists
          "service_name":   "gpio_service",
          "datapoint_name": "relay2"
        }
      },
      "logging": { "level": "info" }
    }
    """

    # -- Modbus groups: static from ilx_craneiq_core-config.json ----------
    # These are fixed hardware groups and do not change based on rules.
    modbus_groups = [
        {"datapoint": "hoist_group", "name": "hoist_group", "members": ["hoist_up", "hoist_down"]},
        {"datapoint": "ct_group",    "name": "ct_group",   "members": ["ct_left", "ct_right"]},
        {"datapoint": "lt_group",    "name": "lt_group",   "members": ["lt_forward", "lt_reverse"]},
    ]

    # -- Loadcell: fully automatic from DB, no UI config required ---------
    lc_params = _get_loadcell_service_params()

    # -- Emergency output from first enabled emergency rule ----------------
    emergency_output = None
    for rule in rules:
        if rule.get('rule_type') == 'emergency':
            relay_dp = (rule.get('relay_datapoint') or '').strip()
            if relay_dp:
                emergency_output = {
                    'service_name':   'gpio_service',
                    'datapoint_name': relay_dp,
                }
                break

    # -- Assemble full config ----------------------------------------------
    core_config = {
        'version':      2,
        'service_name': 'ilx_craneiq_core',
        'pipeline': {
            'server':                '127.0.0.1',
            'port':                  7000,
            'connection_timeout_s':  5,
            'max_queue_size':        10,
            'reconnect_interval_ms': 100,
        },
        'services': {
            'modbus': {
                'service_name': 'modbus_service',
                'groups':       modbus_groups,
            },
            'loadcell': {
                'service_name':             'load_cell_service',
                'datapoint_name':           lc_params['datapoint_name'],
                'unit_datapoint_name':      lc_params['unit_datapoint_name'],
                'overload_threshold_grams': lc_params['overload_threshold_grams'],
                'overload_deadband_grams':  lc_params['overload_deadband_grams']
            },
        },
        'logging': {'level': 'info'},
    }

    if emergency_output:
        core_config['services']['emergency_output'] = emergency_output

    return core_config


def _save_core_config_to_db(config_json, device_names=None, service_name='ilx_craneiq_core'):
    """
    Save core config to database with version tracking.
    SINGLE ROW ONLY - updates existing row if present.
    Returns the version number.
    """
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Ensure table exists with updated_at column
        cur.execute('''
            CREATE TABLE IF NOT EXISTS core_configs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                version      INTEGER NOT NULL DEFAULT 1,
                device_names TEXT,
                service_name TEXT,
                config_json  TEXT NOT NULL,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        device_names_json = json.dumps(device_names) if device_names else '[]'
        
        # Check if we already have a config - UPDATE instead of INSERT
        cur.execute('SELECT id, version FROM core_configs LIMIT 1')
        existing = cur.fetchone()
        
        if existing:
            # Core config schema version is always fixed at 2 -- no auto-increment
            new_version = 2
            cur.execute('''
                UPDATE core_configs 
                SET version = ?, 
                    device_names = ?, 
                    service_name = ?, 
                    config_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_version, device_names_json, service_name, config_json, existing['id']))
            logger.info('[CORE-CFG] Updated DB (version fixed at 2)')
            return new_version
        else:
            # First-time insert
            cur.execute('''
                INSERT INTO core_configs (version, device_names, service_name, config_json, updated_at) 
                VALUES (2, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (device_names_json, service_name, config_json))
            conn.commit()
            logger.info('[CORE-CFG] Inserted initial config to DB (version fixed at 2)')
            return 2
        
    except Exception as db_e:
        logger.warning('[CORE-CFG] DB persist warning: {}'.format(db_e))
        return None
    finally:
        if conn:
            conn.close()


async def _build_and_send_core_config(force_rebuild=False):
    """
    Build combined core_config from DB, persist it (single row), then send via pipeline.
    If force_rebuild is False, it will try to use the existing config from the core_configs table.
    """
    from pipeline import pipeline_state, get_pipeline_service_name
    from pipeline import Config, get_pipeline_config_name
    from pipeline import record_pipeline_send_success, record_pipeline_send_failure

    config_json = None
    db_version = None
    device_names = []
    
    if not force_rebuild:
        # Try to load from DB first
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT config_json, version, device_names FROM core_configs LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            if row:
                config_json = row[0]
                db_version = row[1]
                device_names = json.loads(row[2]) if row[2] else []
                
                # Injection: Always override with latest DB truth for loadcell
                try:
                    lc_params = _get_loadcell_service_params()
                    config = json.loads(config_json)
                    if 'services' in config and 'loadcell' in config['services']:
                        lc = config['services']['loadcell']
                        lc['overload_threshold_grams'] = lc_params['overload_threshold_grams']
                        lc['overload_deadband_grams']  = lc_params['overload_deadband_grams']
                        lc['datapoint_name']            = lc_params['datapoint_name']
                        lc['unit_datapoint_name']       = lc_params['unit_datapoint_name']
                        config_json = json.dumps(config, indent=2)
                        logger.info("[CORE-CFG] Using existing config from DB (v{}) - loadcell params enforced".format(db_version))
                    else:
                        logger.info("[CORE-CFG] Using existing config from DB (v{})".format(db_version))
                except Exception as lc_e:
                    logger.warning("[CORE-CFG] Loadcell param injection failed: {}".format(lc_e))
                    logger.info("[CORE-CFG] Using existing config from DB (v{})".format(db_version))
        except Exception as e:
            logger.warning("[CORE-CFG] DB load warning: {}".format(e))

    if config_json is None:
        rules = _collect_all_enabled_rules()
        core_config = _build_combined_core_config(rules)
        config_json = json.dumps(core_config, indent=2)

        logger.info('\n' + '='*60)
        logger.info('[CORE-CFG] Trigger -- {} enabled rule(s)'.format(len(rules)))
        logger.info('[CORE-CFG] loadcell: datapoint_name="{}"  unit_datapoint_name="{}"'.format(
            core_config['services']['loadcell']['datapoint_name'],
            core_config['services']['loadcell']['unit_datapoint_name'],
        ))
        logger.info('='*60)

        # -- Extract device names for DB storage --
        if 'services' in core_config:
            for svc_name, svc_config in core_config['services'].items():
                if svc_name == 'modbus' and 'groups' in svc_config:
                    for group in svc_config['groups']:
                        if 'members' in group:
                            device_names.extend(group['members'])

        # -- Persist to core_configs DB table (SINGLE ROW) --
        db_version = _save_core_config_to_db(config_json, device_names, core_config.get('service_name', 'ilx_craneiq_core'))

    # -- Pipeline send --
    core_svc = get_pipeline_service_name('core') or 'ilx_craneiq_core'

    with pipeline_state['lock']:
        client = pipeline_state.get('client')
        connected = pipeline_state.get('connected', False)
        services = set(pipeline_state.get('connected_services', set()))

    if not (connected and client and core_svc in services):
        # Queue as pending -- pipeline.py SERVICE_ADDED will dispatch when ready
        with pipeline_state['lock']:
            pipeline_state['core_config_pending'] = config_json
        logger.info('[CORE-CFG] Not connected -- queued as pending for "{}"'.format(core_svc))
        return {
            'sent':        False,
            'queued':      True,
            'pending':     True,
            'service':     core_svc,
            'rules_count': len(rules),
            'db_version':  db_version,
        }

    new_version = 2  # Core config schema version is always fixed at 2 -- no auto-increment
    ok = False
    try:
        ok = client.publish_config(Config(
            name    = get_pipeline_config_name('core'),
            value   = config_json,
            version = new_version,
            service = core_svc,
        ))
        if ok:
            record_pipeline_send_success('core', new_version, core_svc,
                                         'Sent to {} (v{})'.format(core_svc, new_version))
            with pipeline_state['lock']:
                pipeline_state['core_config']         = config_json
                pipeline_state['core_config_pending'] = None
                pipeline_state['core_config_version'] = new_version
            logger.info('[CORE-CFG] publish_config -> {} (v{}) OK'.format(core_svc, new_version))
        else:
            record_pipeline_send_failure('core', 'publish_config returned False')
            with pipeline_state['lock']:
                pipeline_state['core_config_pending'] = config_json
            logger.info('[CORE-CFG] publish_config FAILED -- queued as pending')
    except Exception as e:
        logger.error('[CORE-CFG] publish_config error: {}'.format(e))
        record_pipeline_send_failure('core', str(e))
        with pipeline_state['lock']:
            pipeline_state['core_config_pending'] = config_json

    return {
        'sent':        ok,
        'queued':      not ok,
        'service':     core_svc,
        'rules_count': len(_collect_all_enabled_rules()) if config_json is None else "N/A",
        'db_version':  db_version,
    }


# ---------------------------------------------------------------------------
# Register routes
# ---------------------------------------------------------------------------
def register_rules_routes(app):
    app.router.add_get   ('/api/rules/tags',             rules_tags_handler)
    app.router.add_get   ('/api/rules',                  rules_list_handler)
    app.router.add_post  ('/api/rules/save',             rules_save_handler)
    app.router.add_delete('/api/rules/{rule_id}',        rules_delete_handler)
    app.router.add_post  ('/api/rules/pipeline/trigger', rules_pipeline_trigger_handler)
    
    # Core config JSON upload and management endpoints
    app.router.add_post  ('/api/rules/core-config/upload', core_config_upload_handler)
    app.router.add_get   ('/api/rules/core-configs',      core_configs_list_handler)
    app.router.add_get   ('/api/rules/core-config/latest', core_config_latest_handler)
    app.router.add_get   ('/api/rules/core-config/preview', core_config_preview_handler)
    
    logger.info('[Rules] Routes registered OK')