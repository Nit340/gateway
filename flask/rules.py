# -*- coding: utf-8 -*-
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
# GET /api/rules/tags  -- all enabled modbus tag names
# ---------------------------------------------------------------------------
async def rules_tags_handler(request):
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute('SELECT name FROM vfd_datapoints WHERE enabled=1 ORDER BY name')
        tags = [row['name'] for row in cur.fetchall()]
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
# POST /api/rules/save  -- DB only, NO pipeline send
# ---------------------------------------------------------------------------
async def rules_save_handler(request):
    try:
        body = await request.json()
        rule = body.get('rule')
        if not rule:
            return web.json_response({'success': False, 'error': 'Missing rule'})

        conn = get_db()
        cur  = conn.cursor()

        # Use SELECT + UPDATE/INSERT instead of ON CONFLICT(...) DO UPDATE,
        # which requires SQLite >= 3.24 (not available in Python 3.5 environments).
        rule_id     = rule['id']
        name        = rule.get('name', '')
        rule_type   = rule.get('ruleType', 'group')
        priority    = rule.get('priority', 'medium')
        description = rule.get('description', '')
        enabled     = 1 if rule.get('enabled', True) else 0
        groups_json = json.dumps(rule.get('groups', {}))
        relay_dp    = rule.get('relayDatapoint', '')

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

        # Save only -- pipeline is triggered separately via Trigger JSON Pipeline button
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
        cur  = conn.cursor()
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
# matching ilx_craneiq_core-config.json exactly, then sends a SEPARATE
# datapoint_update call per service section:
#
#   datapoint_update(core_svc, "modbus",           json(modbus_section))
#   datapoint_update(core_svc, "loadcell",         json(loadcell_section))
#   datapoint_update(core_svc, "emergency_output", json(emergency_section))  <- if any
# ---------------------------------------------------------------------------
async def rules_pipeline_trigger_handler(request):
    try:
        result = await _build_and_send_core_config()
        return web.json_response({'success': True, 'pipeline': result})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _collect_all_enabled_rules():
    """Return all enabled rules from DB as list of dicts."""
    conn = get_db()
    cur  = conn.cursor()
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


def _build_combined_core_config(rules):
    """
    Build the full core_config dict from all enabled rules.
    Matches ilx_craneiq_core-config.json exactly:

    {
      "service_name": "ilx_craneiq_core",
      "pipeline": { "server", "port", ... },
      "services": {
        "modbus": {
          "service_name": "modbus_service",
          "groups": [
            { "datapoint": "hoist_group", "name": "hoist_group", "members": ["hoist_up","hoist_down"] },
            { "datapoint": "ct_group",    "name": "ct_group",    "members": ["ct_left","ct_right"] },
            { "datapoint": "lt_group",    "name": "lt_group",    "members": ["lt_forward","lt_backward"] }
          ]
        },
        "loadcell": {
          "service_name": "load_cell_service",
          "datapoint_name": "load_weight",
          "unit_datapoint_name": "load_unit"
        },
        "emergency_output": {          <- only if an emergency rule exists
          "service_name": "gpio_service",
          "datapoint_name": "relay2"
        }
      },
      "logging": { "level": "info" }
    }
    """

    # -- Modbus groups: merge hoist/ct/lt across all group rules ----------
    # Each alias maps to one group entry; members merged if multiple rules use same alias.
    merged = {}  # dp_name -> { datapoint, name, members: [] }

    for rule in rules:
        if rule.get('rule_type') != 'group':
            continue
        for alias, gdata in rule.get('groups', {}).items():
            if not gdata.get('enabled', True):
                continue
            members = gdata.get('datapoints', [])
            if not members:
                continue
            # Build datapoint name matching sample: "hoist_group", "ct_group", "lt_group"
            dp_name = alias if alias.endswith('_group') else alias + '_group'
            if dp_name not in merged:
                merged[dp_name] = {
                    'datapoint': dp_name,
                    'name':      dp_name,
                    'members':   [],
                }
            for m in members:
                if m not in merged[dp_name]['members']:
                    merged[dp_name]['members'].append(m)

    modbus_groups = list(merged.values())

    # -- Loadcell datapoint names: always use the fixed protocol defaults --
    # loadcell_device.name is the device display label, NOT the datapoint name.
    # The load_cell_service always publishes under 'load_weight' / 'load_unit'.
    lc_datapoint_name      = 'load_weight'
    lc_unit_datapoint_name = 'load_unit'

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
                'service_name':        'load_cell_service',
                'datapoint_name':      lc_datapoint_name,
                'unit_datapoint_name': lc_unit_datapoint_name,
            },
        },
        'logging': {'level': 'info'},
    }

    if emergency_output:
        core_config['services']['emergency_output'] = emergency_output

    return core_config


async def _build_and_send_core_config():
    """
    Build combined core_config, save to disk + DB, then send a separate
    datapoint_update per service section (modbus, loadcell, emergency_output).
    """
    from pipeline import pipeline_state, get_pipeline_service_name

    rules       = _collect_all_enabled_rules()
    core_config = _build_combined_core_config(rules)
    config_json = json.dumps(core_config, indent=2)

    print('\n' + '='*60)
    print('[CORE-CFG] Trigger -- {} enabled rule(s)'.format(len(rules)))
    print('='*60)
    print(config_json)

    # -- Save to disk ------------------------------------------------------
    config_dir  = 'core_configs'
    os.makedirs(config_dir, exist_ok=True)
    ts          = datetime.now().strftime('%Y%m%d_%H%M%S')
    ts_file     = os.path.join(config_dir, 'core_config_{}.json'.format(ts))
    latest_file = os.path.join(config_dir, 'core_config_latest.json')
    for path in (ts_file, latest_file):
        with open(path, 'w') as fh:
            fh.write(config_json)
    print('[CORE-CFG] Saved: {}'.format(ts_file))

    # -- Persist to core_configs DB table ----------------------------------
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS core_configs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                version      INTEGER NOT NULL DEFAULT 1,
                device_names TEXT,
                service_name TEXT,
                config_json  TEXT NOT NULL,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute(
            'INSERT INTO core_configs (version, service_name, config_json) VALUES (?,?,?)',
            (1, 'ilx_craneiq_core', config_json)
        )
        conn.commit()
        conn.close()
    except Exception as db_e:
        print('[CORE-CFG] DB persist warning: {}'.format(db_e))

    # -- Pipeline send -- one datapoint_update per service section ----------
    core_svc = get_pipeline_service_name('core') or 'ilx_craneiq_core'

    with pipeline_state['lock']:
        client    = pipeline_state.get('client')
        connected = pipeline_state.get('connected', False)
        services  = set(pipeline_state.get('connected_services', set()))

    if not (connected and client and core_svc in services):
        # Queue as pending -- pipeline.py SERVICE_ADDED will dispatch on reconnect
        with pipeline_state['lock']:
            pipeline_state['core_config_pending'] = config_json
        print('[CORE-CFG] Not connected -- queued as pending for "{}"'.format(core_svc))
        return {
            'sent':        False,
            'pending':     True,
            'service':     core_svc,
            'rules_count': len(rules),
            'file_saved':  ts_file,
        }

    # Send the full config as a single publish_config call
    from pipeline import get_pipeline_config_name, record_pipeline_send_success, record_pipeline_send_failure, get_next_pipeline_version
    from pipeline import Config

    new_version = get_next_pipeline_version('core')
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
            print('[CORE-CFG] publish_config -> {} (v{}) OK'.format(core_svc, new_version))
        else:
            record_pipeline_send_failure('core', 'publish_config returned False')
            with pipeline_state['lock']:
                pipeline_state['core_config_pending'] = config_json
            print('[CORE-CFG] publish_config -> {} FAILED -- queued as pending'.format(core_svc))
    except Exception as e:
        print('[CORE-CFG] publish_config error: {}'.format(e))
        with pipeline_state['lock']:
            pipeline_state['core_config_pending'] = config_json
        ok = False

    return {
        'sent':        ok,
        'service':     core_svc,
        'rules_count': len(rules),
        'file_saved':  ts_file,
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
    print('[Rules] Routes registered OK')