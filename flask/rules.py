# rules.py - Rules Engine API

import json
import os
import sqlite3
from datetime import datetime
from aiohttp import web
from database import DB_FILE


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# GET /api/rules/tags  — all enabled modbus tag names
# ---------------------------------------------------------------------------
async def rules_tags_handler(request):
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute('SELECT name FROM modbus_datapoints WHERE enabled=1 ORDER BY name')
        tags = [row['name'] for row in cur.fetchall()]
        conn.close()
        return web.json_response({'success': True, 'tags': tags})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# GET /api/rules  — all saved rules
# ---------------------------------------------------------------------------
async def rules_list_handler(request):
    try:
        conn = get_db()
        cur  = conn.cursor()
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
# POST /api/rules/save  — insert or update a rule, then send core_config
# ---------------------------------------------------------------------------
async def rules_save_handler(request):
    try:
        body = await request.json()
        rule = body.get('rule')
        if not rule:
            return web.json_response({'success': False, 'error': 'Missing rule'})

        # Save to DB
        conn = get_db()
        cur  = conn.cursor()
        cur.execute('''
            INSERT INTO rules
                (id, name, rule_type, priority, description, enabled, groups_json, relay_datapoint, updated_at)
            VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                rule_type=excluded.rule_type,
                priority=excluded.priority,
                description=excluded.description,
                enabled=excluded.enabled,
                groups_json=excluded.groups_json,
                relay_datapoint=excluded.relay_datapoint,
                updated_at=CURRENT_TIMESTAMP
        ''', (
            rule['id'],
            rule.get('name', ''),
            rule.get('ruleType', 'group'),
            rule.get('priority', 'medium'),
            rule.get('description', ''),
            1 if rule.get('enabled', True) else 0,
            json.dumps(rule.get('groups', {})),
            rule.get('relayDatapoint', ''),
        ))
        conn.commit()
        conn.close()

        # Build and send core_config
        result = _send_core_config(rule)
        return web.json_response({'success': True, 'pipeline': result})

    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# DELETE /api/rules/{rule_id}
# ---------------------------------------------------------------------------
async def rules_delete_handler(request):
    rule_id = request.match_info.get('rule_id')
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute('DELETE FROM rules WHERE id=?', (rule_id,))
        conn.commit()
        conn.close()
        return web.json_response({'success': True})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# Build core_config JSON from rule and send via pipeline
# Follows the same pattern as modbus/loadcell/iot_gateway config sending
# ---------------------------------------------------------------------------
def _build_core_config(rule):
    """Build the ilx_craneiq_core config dict from a rule."""
    from pipeline import pipeline_state

    rtype  = rule.get('ruleType', 'group')
    groups = rule.get('groups', {})

    # Modbus groups: each group key → { enabled, datapoints: [tag, tag, ...] }
    modbus_groups = []
    for group_name, gdata in groups.items():
        if not gdata.get('enabled', True):
            continue
        modbus_groups.append({
            'datapoint':  group_name,
            'name':       group_name,
            'datapoints': gdata.get('datapoints', [])
        })

    # Read loadcell datapoint names from DB
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute('SELECT name FROM loadcell_datapoints ORDER BY id LIMIT 2')
        lc = [r['name'] for r in cur.fetchall()]
        conn.close()
    except Exception:
        lc = []

    core_config = {
        'service_name': 'ilx_craneiq_core',
        'pipeline': {
            'server':                '127.0.0.1',
            'port':                  7000,
            'connection_timeout_s':  5,
            'max_queue_size':        10,
            'reconnect_interval_ms': 100
        },
        'services': {
            'modbus': {
                'service_name': 'modbus_service',
                'groups':       modbus_groups
            },
            'loadcell': {
                'service_name':        'load_cell_service',
                'datapoint_name':      lc[0] if lc       else 'load_weight',
                'unit_datapoint_name': lc[1] if len(lc) > 1 else 'load_unit'
            }
        },
        'logging': {'level': 'info'}
    }

    if rtype == 'emergency':
        relay_tag = rule.get('relayDatapoint', '')
        core_config['services']['emergency_output'] = {
            'service_name':  'gpio_service',
            'datapoint_name': relay_tag
        }

    return core_config


def _send_core_config(rule):
    """Build core_config, save to disk, send via pipeline. Returns result dict."""
    from pipeline import pipeline_state

    core_config = _build_core_config(rule)
    config_json = json.dumps(core_config, indent=2)
    service     = 'ilx_craneiq_core'

    print('\n' + '='*60)
    print('[CORE-CFG] Build -> Save -> Send')
    print('='*60)

    # Save to disk (same pattern as other configs)
    config_dir = 'core_configs'
    os.makedirs(config_dir, exist_ok=True)
    ts           = datetime.now().strftime('%Y%m%d_%H%M%S')
    ts_file      = os.path.join(config_dir, 'core_config_{}.json'.format(ts))
    latest_file  = os.path.join(config_dir, 'core_config_latest.json')
    for path in (ts_file, latest_file):
        with open(path, 'w') as fh:
            fh.write(config_json)
    print('[CORE-CFG] Saved: {}'.format(ts_file))

    # Send via pipeline
    with pipeline_state['lock']:
        client    = pipeline_state.get('client')
        connected = pipeline_state.get('connected', False)
        services  = pipeline_state.get('connected_services', set())

    if connected and client and service in services:
        try:
            rid = client.datapoint_update(service, 'core_config', config_json)
            if rid > 0:
                print('[CORE-CFG] Sent to {} (rid={})'.format(service, rid))
                with pipeline_state['lock']:
                    pipeline_state['core_config_pending'] = None
                return {'sent': True, 'rid': rid}
            else:
                print('[CORE-CFG] Send returned rid=0, storing as pending')
        except Exception as e:
            print('[CORE-CFG] Send error: {}'.format(e))

    # Store as pending — dispatched automatically on SERVICE_ADDED
    with pipeline_state['lock']:
        pipeline_state['core_config_pending'] = config_json
    print('[CORE-CFG] Stored as pending (service not connected)')
    return {'sent': False, 'pending': True}


# ---------------------------------------------------------------------------
# Register routes
# ---------------------------------------------------------------------------
def register_rules_routes(app):
    app.router.add_get   ('/api/rules/tags',       rules_tags_handler)
    app.router.add_get   ('/api/rules',             rules_list_handler)
    app.router.add_post  ('/api/rules/save',        rules_save_handler)
    app.router.add_delete('/api/rules/{rule_id}',   rules_delete_handler)
    print('[Rules] Routes registered OK')