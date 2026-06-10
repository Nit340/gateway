# mqtt_cloud.py
# Tables: mqtt_connections, http_connections, mqtt_datapoints, http_datapoints, cloud_connection_stats
# Verification command: python -m py_compile flask/mqtt_cloud.py
# Verification command: python -c "import sys; sys.path.append('flask'); import database, mqtt_cloud; database.ensure_db_initialized(); print(mqtt_cloud.build_iot_gateway_config())"
import json, time, asyncio
from aiohttp import web
from database import get_db_connection
from logger_util import get_logger

logger = get_logger(__name__)

def register_cloud_routes(app):
    app.router.add_get   ('/api/cloud-integration/connection-types',              _connection_types)
    app.router.add_get   ('/api/cloud-integration/connections',                   _list)
    app.router.add_post  ('/api/cloud-integration/connections',                   _create)
    app.router.add_get   ('/api/cloud-integration/connections/{id}',              _get)
    app.router.add_put   ('/api/cloud-integration/connections/{id}',              _update)
    app.router.add_delete('/api/cloud-integration/connections/{id}',              _delete)
    app.router.add_post  ('/api/cloud-integration/connections/{id}/toggle',       _toggle)
    app.router.add_get   ('/api/cloud-integration/connections/{id}/tags',         _get_tags)
    app.router.add_post  ('/api/cloud-integration/connections/{id}/tags',         _assign_tags)
    app.router.add_delete('/api/cloud-integration/connections/{id}/tags/{tag}',   _remove_tag)
    app.router.add_get   ('/api/cloud-integration/available-tags',                _available_tags)
    app.router.add_put   ('/api/cloud-integration/save-config',                   _save_all)
    app.router.add_get   ('/api/cloud-integration/metadata-tags',                 _metadata_tags)
    app.router.add_post  ('/api/cloud-integration/send-iot-config',               _send_iot_config)
    app.router.add_get   ('/api/cloud-integration/export',                        _export_connections)
    app.router.add_post  ('/api/cloud-integration/import',                        _import_connections)

# --- TYPE DEFAULTS ------------------------------------------------------------
_DEFAULTS = {
    'mqtt': {
        'protocol':'mqtts','host':'','port':8883,'client_id':'','keepAlive':60,
        'username':'','password':'','tls':True,'cleanSession':True,'retainMessages':False,'qos':1,
        'baseTopic':'gateway/data',
        'jsonTemplate':'{"timestamp":"%TIMESTAMP%","device":"%DEVICE_ID%","data":%DATA%}',
        'device_token': ''
    },
    'http': {
        'url':'','method':'POST','authToken':'','headers':{},'timeout':30
    },
}

# --- HELPERS ------------------------------------------------------------------
def _ok(d, s=200): return web.Response(text=json.dumps(d), content_type='application/json', status=s)
def _err(m, s=400): return web.Response(text=json.dumps({'error':m}), content_type='application/json', status=s)
def _cfg(raw):
    try: return json.loads(raw or '{}')
    except: return {}
def _gid(t):
    return "{}-{}".format(t, int(time.time()*1000) % 100000000)
def _ensure_stats(cur, cid):
    cur.execute('INSERT OR IGNORE INTO cloud_connection_stats(connection_id) VALUES(?)',(cid,))

def _fetch_tags(cur, cid, ctype):
    if ctype == 'mqtt':
        cur.execute('SELECT tag,topic,publish_mode,change_threshold,enabled FROM mqtt_datapoints WHERE connection_id=? ORDER BY tag',(cid,))
        return [{'name':r[0],'topic':r[1],'publishMode':r[2],'changeThreshold':r[3],'enabled':bool(r[4])} for r in cur.fetchall()]
    elif ctype == 'http':
        cur.execute('SELECT tag,endpoint,publish_mode,change_threshold,enabled FROM http_datapoints WHERE connection_id=? ORDER BY tag',(cid,))
        return [{'name':r[0],'topic':r[1],'publishMode':r[2],'changeThreshold':r[3],'enabled':bool(r[4])} for r in cur.fetchall()]
    return []

def _fetch_stats(cur, cid):
    cur.execute('SELECT messages_total,messages_ok,messages_failed,latency_avg_ms,last_active FROM cloud_connection_stats WHERE connection_id=?',(cid,))
    r=cur.fetchone()
    if not r: return {'messages':0,'ok':0,'failed':0,'latency':0,'lastActive':'Never','successRate':0}
    tot,ok,fail,lat,last=r
    return {'messages':tot or 0,'ok':ok or 0,'failed':fail or 0,'latency':round(lat or 0,1),
            'lastActive':last or 'Never','successRate':round((ok/tot*100) if tot else 0,1)}

# --- HANDLERS -----------------------------------------------------------------
async def _connection_types(req):
    return _ok({'types':[
        {'id':'mqtt','name':'MQTT Broker',   'description':'Standard IoT messaging protocol','icon':'fa-solid fa-cloud','color':'#3B82F6'},
        {'id':'http', 'name':'HTTP Server',  'description':'REST API Webhooks','icon':'fa-solid fa-globe','color':'#10B981'},
    ]})

async def _list(req):
    try:
        db=get_db_connection(); cur=db.cursor()
        result = []
        
        # MQTT
        cur.execute('SELECT id,name,enabled,protocol,host,port,client_id,username,password,keepalive_sec,qos,base_topic,tls,json_template,channels_json,mappings_json,created_at,updated_at,device_token FROM mqtt_connections')
        for r in cur.fetchall():
            cfg = {
                'protocol': r[3], 'host': r[4], 'port': r[5], 'client_id': r[6], 'username': r[7], 'password': r[8],
                'keepAlive': r[9], 'qos': r[10], 'baseTopic': r[11], 'tls': bool(r[12]), 'jsonTemplate': r[13],
                'channels': _cfg(r[14]), 'mappings': _cfg(r[15]), 'device_token': r[18] or ''
            }
            result.append({
                'id': r[0], 'type': 'mqtt', 'name': r[1], 'enabled': bool(r[2]),
                'config': cfg, 'tags': _fetch_tags(cur, r[0], 'mqtt'),
                'statistics': _fetch_stats(cur, r[0]), 'created_at': r[16], 'updated_at': r[17]
            })
            
        # HTTP
        cur.execute('SELECT id,name,enabled,url,method,auth_token,headers_json,timeout_sec,channels_json,mappings_json,created_at,updated_at FROM http_connections')
        for r in cur.fetchall():
            cfg = {
                'url': r[3], 'method': r[4], 'authToken': r[5], 'headers': _cfg(r[6]), 'timeout': r[7],
                'channels': _cfg(r[8]), 'mappings': _cfg(r[9])
            }
            result.append({
                'id': r[0], 'type': 'http', 'name': r[1], 'enabled': bool(r[2]),
                'config': cfg, 'tags': _fetch_tags(cur, r[0], 'http'),
                'statistics': _fetch_stats(cur, r[0]), 'created_at': r[10], 'updated_at': r[11]
            })
            
        result.sort(key=lambda x: x['created_at'], reverse=True)
        db.close()
        return _ok({'connections':result,'total':len(result)})
    except Exception as e: return _err(str(e),500)

async def _create(req):
    try: body=await req.json()
    except: return _err('Invalid JSON')
    ctype=(body.get('type') or '').lower()
    if ctype not in ('mqtt','http'): return _err('Invalid type: {}'.format(ctype))
    name=(body.get('name') or '').strip()
    if not name: return _err('name is required')
    
    cid=_gid(ctype)
    enabled = 1 if body.get('enabled',True) else 0
    config = {**_DEFAULTS[ctype], **(body.get('connection') or body.get('config') or {})}
    
    try:
        db=get_db_connection(); cur=db.cursor()
        if ctype == 'mqtt':
            cur.execute('''INSERT INTO mqtt_connections(
                id,name,enabled,protocol,host,port,client_id,username,password,
                keepalive_sec,qos,base_topic,tls,json_template,device_token
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                cid, name, enabled, 
                config.get('protocol','mqtts'), config.get('host',''), int(config.get('port',8883)),
                config.get('client_id',''), config.get('username',''), config.get('password',''),
                int(config.get('keepAlive',60)), int(config.get('qos',1)), config.get('baseTopic','gateway/data'),
                1 if config.get('tls',True) else 0, config.get('jsonTemplate','{"timestamp":"%TIMESTAMP%","device":"%DEVICE_ID%","data":%DATA%}'),
                config.get('device_token') or config.get('deviceToken') or ''
            ))
        elif ctype == 'http':
            cur.execute('''INSERT INTO http_connections(
                id,name,enabled,url,method,auth_token,headers_json,timeout_sec
            ) VALUES(?,?,?,?,?,?,?,?)''', (
                cid, name, enabled,
                config.get('url',''), config.get('method','POST'), config.get('authToken',''),
                json.dumps(config.get('headers',{})), int(config.get('timeout',30))
            ))
            
        _ensure_stats(cur,cid)
        db.commit(); db.close()
        return _ok({'id':cid,'message':'"{}" created'.format(name)},201)
    except Exception as e: return _err(str(e),500)

async def _get(req):
    cid=req.match_info['id']
    ctype = cid.split('-')[0]
    try:
        db=get_db_connection(); cur=db.cursor()
        if ctype == 'mqtt':
            cur.execute('SELECT id,name,enabled,protocol,host,port,client_id,username,password,keepalive_sec,qos,base_topic,tls,json_template,channels_json,mappings_json,created_at,updated_at,device_token FROM mqtt_connections WHERE id=?', (cid,))
            r = cur.fetchone()
            if not r: db.close(); return _err('Not found',404)
            cfg = {
                'protocol': r[3], 'host': r[4], 'port': r[5], 'client_id': r[6], 'username': r[7], 'password': r[8],
                'keepAlive': r[9], 'qos': r[10], 'baseTopic': r[11], 'tls': bool(r[12]), 'jsonTemplate': r[13],
                'channels': _cfg(r[14]), 'mappings': _cfg(r[15]), 'device_token': r[18] or ''
            }
            result = {
                'id': r[0], 'type': 'mqtt', 'name': r[1], 'enabled': bool(r[2]),
                'config': cfg, 'tags': _fetch_tags(cur, r[0], 'mqtt'),
                'statistics': _fetch_stats(cur, r[0]), 'created_at': r[16], 'updated_at': r[17]
            }
        elif ctype == 'http':
            cur.execute('SELECT id,name,enabled,url,method,auth_token,headers_json,timeout_sec,channels_json,mappings_json,created_at,updated_at FROM http_connections WHERE id=?', (cid,))
            r = cur.fetchone()
            if not r: db.close(); return _err('Not found',404)
            cfg = {
                'url': r[3], 'method': r[4], 'authToken': r[5], 'headers': _cfg(r[6]), 'timeout': r[7],
                'channels': _cfg(r[8]), 'mappings': _cfg(r[9])
            }
            result = {
                'id': r[0], 'type': 'http', 'name': r[1], 'enabled': bool(r[2]),
                'config': cfg, 'tags': _fetch_tags(cur, r[0], 'http'),
                'statistics': _fetch_stats(cur, r[0]), 'created_at': r[10], 'updated_at': r[11]
            }
        else:
            db.close(); return _err('Not found',404)
            
        db.close()
        return _ok(result)
    except Exception as e: return _err(str(e),500)

def _sync_datapoints_for_connection(cur, cid, ctype, channels, mappings, base_topic):
    """Synchronizes UI-assigned tag mappings into structured SQLite datapoints tables.
    Verification command: python -c "import sys; sys.path.append('flask'); import database, mqtt_cloud; db=database.get_db_connection(); cur=db.cursor(); mqtt_cloud._sync_datapoints_for_connection(cur, 'mqtt-test', 'mqtt', {}, [], 'test/topic')"
    """
    ch_topics = {}
    
    # Parse channels if it is a string
    actual_channels = channels
    if isinstance(channels, str):
        try: actual_channels = json.loads(channels)
        except: actual_channels = {}
        
    if isinstance(actual_channels, dict):
        for ch in actual_channels.get('publish', []):
            ch_name = ch.get('name')
            ch_topic = ch.get('topic')
            if ch_name:
                ch_topics[ch_name] = ch_topic

    # Parse mappings if it is a string
    actual_mappings = mappings
    if isinstance(mappings, str):
        try: actual_mappings = json.loads(mappings)
        except: actual_mappings = []
        
    if not isinstance(actual_mappings, list):
        actual_mappings = []

    if ctype == 'mqtt':
        cur.execute('DELETE FROM mqtt_datapoints WHERE connection_id=?', (cid,))
        for mapping in actual_mappings:
            channel = mapping.get('channel') or 'default_publish'
            topic = ch_topics.get(channel) or base_topic or 'gateway/data'
            dp = mapping.get('datapoints') or {}
            for dtype in ('float', 'int', 'bool', 'string'):
                for entry in dp.get(dtype) or []:
                    tname = entry if isinstance(entry, str) else entry.get('name')
                    if tname:
                        cur.execute('''INSERT OR IGNORE INTO mqtt_datapoints(
                            connection_id, tag, topic, publish_mode, change_threshold, enabled
                        ) VALUES(?,?,?,?,?,1)''', (cid, tname, topic, 'on_change', 0.0))
    elif ctype == 'http':
        cur.execute('DELETE FROM http_datapoints WHERE connection_id=?', (cid,))
        for mapping in actual_mappings:
            endpoint = mapping.get('endpoint') or ''
            dp = mapping.get('datapoints') or {}
            for dtype in ('float', 'int', 'bool', 'string'):
                for entry in dp.get(dtype) or []:
                    tname = entry if isinstance(entry, str) else entry.get('name')
                    if tname:
                        cur.execute('''INSERT OR IGNORE INTO http_datapoints(
                            connection_id, tag, endpoint, publish_mode, change_threshold, enabled
                        ) VALUES(?,?,?,?,?,1)''', (cid, tname, endpoint, 'on_change', 0.0))

async def _update(req):
    cid=req.match_info['id']
    ctype = cid.split('-')[0]
    try: body=await req.json()
    except: return _err('Invalid JSON')
    
    try:
        db=get_db_connection(); cur=db.cursor()
        
        # Read old to merge config
        if ctype == 'mqtt':
            cur.execute('SELECT host,port,client_id,username,password,keepalive_sec,qos,base_topic,tls,json_template,protocol,channels_json,mappings_json,device_token FROM mqtt_connections WHERE id=?', (cid,))
            r = cur.fetchone()
            if not r: db.close(); return _err('Not found',404)
            old_cfg = {
                'host': r[0], 'port': r[1], 'client_id': r[2], 'username': r[3], 'password': r[4],
                'keepAlive': r[5], 'qos': r[6], 'baseTopic': r[7], 'tls': bool(r[8]), 'jsonTemplate': r[9], 'protocol': r[10],
                'channels': _cfg(r[11]), 'mappings': _cfg(r[12]), 'device_token': r[13] or ''
            }
        elif ctype == 'http':
            cur.execute('SELECT url,method,auth_token,headers_json,timeout_sec,channels_json,mappings_json FROM http_connections WHERE id=?', (cid,))
            r = cur.fetchone()
            if not r: db.close(); return _err('Not found',404)
            old_cfg = {
                'url': r[0], 'method': r[1], 'authToken': r[2], 'headers': _cfg(r[3]), 'timeout': r[4],
                'channels': _cfg(r[5]), 'mappings': _cfg(r[6])
            }
        else:
            db.close(); return _err('Not found',404)

        cfg_payload = body.get('config') or {}
        merged = {**old_cfg, **cfg_payload}
        
        sets = ['updated_at=CURRENT_TIMESTAMP']
        vals = []
        if body.get('name'):
            sets.append('name=?')
            vals.append(body['name'].strip())
        if 'enabled' in body:
            sets.append('enabled=?')
            vals.append(1 if body['enabled'] else 0)
            
        if ctype == 'mqtt':
            for k, col in [('protocol','protocol'), ('host','host'), ('port','port'), ('client_id','client_id'),
                           ('username','username'), ('password','password'), ('keepAlive','keepalive_sec'),
                           ('qos','qos'), ('baseTopic','base_topic'), ('jsonTemplate','json_template'),
                           ('device_token','device_token')]:
                sets.append('{}=?'.format(col))
                vals.append(merged.get(k, ''))
            sets.append('tls=?')
            vals.append(1 if merged.get('tls', True) else 0)
            sets.append('channels_json=?')
            vals.append(json.dumps(merged.get('channels', [])))
            sets.append('mappings_json=?')
            vals.append(json.dumps(merged.get('mappings', [])))
            
            vals.append(cid)
            cur.execute('UPDATE mqtt_connections SET {} WHERE id=?'.format(','.join(sets)), vals)
            
        elif ctype == 'http':
            for k, col in [('url','url'), ('method','method'), ('authToken','auth_token'), ('timeout','timeout_sec')]:
                sets.append('{}=?'.format(col))
                vals.append(merged.get(k, ''))
            sets.append('headers_json=?')
            vals.append(json.dumps(merged.get('headers', {})))
            sets.append('channels_json=?')
            vals.append(json.dumps(merged.get('channels', [])))
            sets.append('mappings_json=?')
            vals.append(json.dumps(merged.get('mappings', [])))
            
            vals.append(cid)
            cur.execute('UPDATE http_connections SET {} WHERE id=?'.format(','.join(sets)), vals)

        # Synchronize tag mappings to structured tables if mappings key is provided
        if 'mappings' in cfg_payload:
            _sync_datapoints_for_connection(cur, cid, ctype, merged.get('channels'), cfg_payload.get('mappings'), merged.get('baseTopic'))
            
        db.commit(); db.close()
        return _ok({'message':'Updated'})
    except Exception as e: return _err(str(e),500)

async def _delete(req):
    cid=req.match_info['id']
    ctype = cid.split('-')[0]
    try:
        db=get_db_connection(); cur=db.cursor()
        tbl = 'mqtt_connections' if ctype == 'mqtt' else 'http_connections'
        cur.execute('SELECT id FROM {} WHERE id=?'.format(tbl),(cid,))
        if not cur.fetchone(): db.close(); return _err('Not found',404)
        cur.execute('DELETE FROM {} WHERE id=?'.format(tbl),(cid,))
        db.commit(); db.close()
        return _ok({'message':'Deleted'})
    except Exception as e: return _err(str(e),500)

async def _toggle(req):
    cid=req.match_info['id']
    ctype = cid.split('-')[0]
    try:
        db=get_db_connection(); cur=db.cursor()
        tbl = 'mqtt_connections' if ctype == 'mqtt' else 'http_connections'
        cur.execute('SELECT enabled FROM {} WHERE id=?'.format(tbl),(cid,))
        r=cur.fetchone()
        if not r: db.close(); return _err('Not found',404)
        new_val = 0 if bool(r[0]) else 1
        cur.execute('UPDATE {} SET enabled=?,updated_at=CURRENT_TIMESTAMP WHERE id=?'.format(tbl),(new_val,cid))
        db.commit()
        # Read back
        cur.execute('SELECT enabled FROM {} WHERE id=?'.format(tbl),(cid,))
        confirmed = bool(cur.fetchone()[0])
        db.close()
        return _ok({'enabled': confirmed, 'message': 'enabled' if confirmed else 'disabled'})
    except Exception as e: return _err(str(e),500)

async def _get_tags(req):
    cid=req.match_info['id']
    ctype = cid.split('-')[0]
    try:
        db=get_db_connection(); cur=db.cursor()
        tbl = 'mqtt_connections' if ctype == 'mqtt' else 'http_connections'
        cur.execute('SELECT id FROM {} WHERE id=?'.format(tbl),(cid,))
        if not cur.fetchone(): db.close(); return _err('Not found',404)
        t=_fetch_tags(cur,cid,ctype); db.close()
        return _ok({'connection_id':cid,'tags':t,'total':len(t)})
    except Exception as e: return _err(str(e),500)

async def _assign_tags(req):
    cid=req.match_info['id']
    ctype = cid.split('-')[0]
    try: body=await req.json()
    except: return _err('Invalid JSON')
    tag_list=body.get('tags') or []; mode=body.get('publishMode','onChange')
    thresh=float(body.get('changeThreshold',0.0)); replace=bool(body.get('replace',False))
    try:
        db=get_db_connection(); cur=db.cursor()
        
        if ctype == 'mqtt':
            cur.execute('SELECT id FROM mqtt_connections WHERE id=?',(cid,))
            if not cur.fetchone(): db.close(); return _err('Not found',404)
            if replace: cur.execute('DELETE FROM mqtt_datapoints WHERE connection_id=?',(cid,))
            for tag in tag_list:
                cur.execute('INSERT OR REPLACE INTO mqtt_datapoints(connection_id,tag,topic,publish_mode,change_threshold,enabled) VALUES(?,?,?,?,?,1)',(cid,tag,'',mode,thresh))
                
        elif ctype == 'http':
            cur.execute('SELECT id FROM http_connections WHERE id=?',(cid,))
            if not cur.fetchone(): db.close(); return _err('Not found',404)
            if replace: cur.execute('DELETE FROM http_datapoints WHERE connection_id=?',(cid,))
            for tag in tag_list:
                cur.execute('INSERT OR REPLACE INTO http_datapoints(connection_id,tag,endpoint,publish_mode,change_threshold,enabled) VALUES(?,?,?,?,?,1)',(cid,tag,'',mode,thresh))
                
        else:
            db.close(); return _err('Invalid connection type',400)
            
        db.commit(); db.close()
        return _ok({'message':'{} tag(s) assigned'.format(len(tag_list))})
    except Exception as e: return _err(str(e),500)

async def _remove_tag(req):
    cid=req.match_info['id']; tag=req.match_info['tag']
    ctype = cid.split('-')[0]
    try:
        db=get_db_connection(); cur=db.cursor()
        if ctype == 'mqtt':
            cur.execute('SELECT id FROM mqtt_connections WHERE id=?',(cid,))
            if not cur.fetchone(): db.close(); return _err('Not found',404)
            cur.execute('DELETE FROM mqtt_datapoints WHERE connection_id=? AND tag=?',(cid,tag))
        elif ctype == 'http':
            cur.execute('SELECT id FROM http_connections WHERE id=?',(cid,))
            if not cur.fetchone(): db.close(); return _err('Not found',404)
            cur.execute('DELETE FROM http_datapoints WHERE connection_id=? AND tag=?',(cid,tag))
        else:
            db.close(); return _err('Not found',404)
            
        db.commit(); db.close()
        return _ok({'message':'Tag removed'})
    except Exception as e: return _err(str(e),500)

async def _available_tags(req):
    try:
        from database import get_all_available_tags
        tags = get_all_available_tags()
        return _ok({'tags': tags, 'total': len(tags)})
    except Exception as e:
        return _err(str(e), 500)
    
async def _metadata_tags(req):
    try:
        db = get_db_connection(); cur = db.cursor()
        cur.execute('SELECT name, datatype, source, component FROM metadata ORDER BY name')
        tags = [{'name':r[0], 'dtype':r[1], 'source':r[2], 'component':r[3]} for r in cur.fetchall()]
        db.close()
        return _ok({'tags': tags, 'total': len(tags)})
    except Exception as e: return _err(str(e), 500)

async def _save_all(req):
    try:
        db=get_db_connection(); cur=db.cursor()
        cur.execute('SELECT COUNT(*) FROM mqtt_connections')
        n=cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM http_connections')
        n += cur.fetchone()[0]
        db.close()
        try:
            await send_iot_gateway_config_now()
        except Exception as _e:
            logger.error('[IOT-CFG] sync error in _save_all: {}'.format(_e))
        return _ok({'message':'Saved ({} connections)'.format(n),'total':n})
    except Exception as e: return _err(str(e),500)

# =============================================================================
# IOT GATEWAY CONFIG BUILDER
# =============================================================================

def _get_default_channel_for_connection(conn_config):
    """Return the name of the default (or first) publish channel for a connection."""
    channels = conn_config.get('channels', {})
    publish  = channels.get('publish', [])
    if not publish:
        return 'default_publish'
    for ch in publish:
        if ch.get('default'):
            return ch.get('name', 'default_publish')
    return publish[0].get('name', 'default_publish')


def _get_default_publish_channel_for_connection(conn_config):
    """Return the name of the default (or first) publish channel for a connection.

    Used to resolve the heartbeat/offline channel from the UE (upstream/publish)
    direction instead of the subscribe direction.

    Lookup order:
      1. publish channel explicitly marked  default=True
      2. first publish channel in the list
      3. hard-coded fallback 'default_publish'
    """
    channels = conn_config.get('channels', {})
    publish  = channels.get('publish', [])
    if not publish:
        return 'default_publish'
    for ch in publish:
        if ch.get('default'):
            return ch.get('name', 'default_publish')
    return publish[0].get('name', 'default_publish')


def _get_default_subscribe_channel_for_connection(conn_config):
    """Return the name of the default (or first) subscribe channel for a connection."""
    channels  = conn_config.get('channels', {})
    subscribe = channels.get('subscribe', [])
    if not subscribe:
        return 'default_subscribe'
    for ch in subscribe:
        if ch.get('default'):
            return ch.get('name', 'default_subscribe')
    return subscribe[0].get('name', 'default_subscribe')


def build_iot_gateway_config():
    """Build the complete iot_gateway JSON config from the database.

    Returns a dict ready to be json.dumps()-ed.

    - wifi credentials come from general_configuration (network.wifi.ssid / .password)
    - heartbeat.channel is taken from the default PUBLISH channel of the local MQTT
      broker connection so it always matches the UE publish direction.
    """
    from database import get_general_configuration, get_db_connection
    import time as _time

    # -- 1. General config: wifi + heartbeat ----------------------------------
    gen  = get_general_configuration()
    wifi = gen.get('network', {}).get('wifi', {})
    hb   = gen.get('heartbeat', {})

    cell = gen.get('network', {}).get('cellular', {})
    
    wifi_ssid     = wifi.get('ssid',     '')
    wifi_password = wifi.get('password', '')
    
    cell_apn  = cell.get('apn', '')
    cell_user = cell.get('username', '')
    cell_pass = cell.get('password', '')
    
    # Read heartbeat interval and offline threshold as separate values
    heartbeat_interval_sec = int(hb.get('interval', 30))
    offline_threshold_sec  = int(hb.get('offline_threshold', 120))

    # -- 2. Load all enabled connections from the database ---------------------
    db  = get_db_connection()
    cur = db.cursor()
    
    # MQTT Connections
    cur.execute(
        "SELECT id, name, enabled, host, port, client_id, username, password, keepalive_sec, channels_json, mappings_json, device_token FROM mqtt_connections ORDER BY created_at"
    )
    mqtt_rows = cur.fetchall()
    
    # HTTP Connections
    cur.execute(
        "SELECT id, name, enabled, url, method, auth_token, headers_json, timeout_sec, channels_json, mappings_json FROM http_connections ORDER BY created_at"
    )
    http_rows = cur.fetchall()
    
    db.close()

    servers           = {}
    all_mappings      = []
    heartbeat_channel = None   # Initialize as None

    # Process MQTT
    for row in mqtt_rows:
        cid, name, enabled, host, port, client_id, username, password, keepalive_sec, channels_json, mappings_json, device_token = row
        
        channels = _cfg(channels_json)
        mappings = _cfg(mappings_json)
        
        cfg = {
            'host':          host,
            'port':          port,
            'client_id':     client_id,
            'username':      username,
            'password':      password,
            'keepalive_sec': keepalive_sec,
            'channels':      channels,
            'mappings':      mappings,
        }

        # Canonical server key: local broker → 'mqtt', cloud/CMS → 'mqtt_cloud'
        server_key = name.lower().replace(' ', '_').replace('-', '_')
        if 'cloud' in server_key or 'cms' in server_key:
            server_key = 'mqtt_cloud'
        else:
            server_key = 'mqtt'

        raw_pub = channels.get('publish',   [])
        raw_sub = channels.get('subscribe', [])

        server_entry = {
            'enabled':       bool(enabled),
            'host':          host or '127.0.0.1',
            'port':          int(port or 1883),
            'client_id':     client_id or '',
            'device_token':  device_token or '',
            'username':      username or '',
            'password':      password or '',
            'keepalive_sec': int(keepalive_sec or 60),
            'channels': {
                'publish':   raw_pub,
                'subscribe': raw_sub,
            },
        }

        servers[server_key] = server_entry

        # heartbeat.channel = the 'name' of the default PUBLISH channel (UE direction).
        # Use _get_default_publish_channel_for_connection so it follows the publish
        # side, not the subscribe side.  Prioritise the 'mqtt' (local broker) server.
        if raw_pub:
            def_ch = _get_default_publish_channel_for_connection(cfg)
            if server_key == 'mqtt' or heartbeat_channel is None:
                heartbeat_channel = def_ch

        # Collect mappings – groups pass through as-is;
        # individual tags each become their own mapping entry.
        default_ch   = _get_default_channel_for_connection(cfg)
        raw_mappings = mappings

        for m in raw_mappings:
            channel = m.get('channel') or default_ch
            if m.get('alias'):
                # Group: preserve alias, type, channel, and datapoints as-is
                entry = {
                    'alias':      m['alias'],
                    'channel':    channel,
                    'datapoints': m.get('datapoints', {}),
                }
                all_mappings.append(entry)
            else:
                # Individual: one mapping entry per tag
                for dtype, tag_entries in (m.get('datapoints') or {}).items():
                    for tag_entry in tag_entries:
                        all_mappings.append({
                            'channel':    channel,
                            'datapoints': {dtype: [tag_entry]},
                        })

    # Process HTTP
    for row in http_rows:
        cid, name, enabled, url, method, auth_token, headers_json, timeout_sec, channels_json, mappings_json = row
        
        channels = _cfg(channels_json)
        mappings = _cfg(mappings_json)
        
        cfg = {
            'url':           url,
            'method':        method,
            'auth_token':    auth_token,
            'headers':       _cfg(headers_json),
            'timeout_sec':   timeout_sec,
            'channels':      channels,
            'mappings':      mappings,
        }

        # Canonical server key
        server_key = name.lower().replace(' ', '_').replace('-', '_')
        if 'cloud' in server_key or 'cms' in server_key:
            server_key = 'http_cloud'
        else:
            server_key = 'http'

        raw_pub = channels.get('publish',   [])

        server_entry = {
            'enabled':       bool(enabled),
            'url':           url or '',
            'method':        method or 'POST',
            'headers':       _cfg(headers_json),
            'auth_token':    auth_token or '',
            'timeout_sec':   int(timeout_sec or 30),
            'channels': {
                'publish':   raw_pub,
            },
        }

        servers[server_key] = server_entry

        # Collect mappings for HTTP
        default_ch   = _get_default_channel_for_connection(cfg)
        raw_mappings = mappings

        for m in raw_mappings:
            channel = m.get('channel') or default_ch
            if m.get('alias'):
                entry = {
                    'alias':      m['alias'],
                    'channel':    channel,
                    'datapoints': m.get('datapoints', {}),
                }
                all_mappings.append(entry)
            else:
                for dtype, tag_entries in (m.get('datapoints') or {}).items():
                    for tag_entry in tag_entries:
                        all_mappings.append({
                            'channel':    channel,
                            'datapoints': {dtype: [tag_entry]},
                        })

    # -- 3. Assemble ---------------------------------------------------------
    return {
        'version': 2,
        'system': {
            'wifi_ssid':           wifi_ssid,
            'wifi_password':       wifi_password,
            'cellular_apn':        cell_apn,
            'cellular_username':   cell_user,
            'cellular_password':   cell_pass,
        },
        'heartbeat': {
            'interval_sec': heartbeat_interval_sec,
            'channel':      heartbeat_channel or 'default_publish',
        },
        'offline_threshold': {
            'interval_sec': offline_threshold_sec,
            'channel':      heartbeat_channel or 'default_publish',
        },
        'servers':  servers,
        'mappings': all_mappings,
    }

async def send_iot_gateway_config_now():
    """Convenience coroutine: build config and dispatch via pipeline.
    Safe to call from any async context.
    """
    try:
        from pipeline import send_iot_gateway_config_now as _pipeline_send
        return await _pipeline_send()
    except Exception as e:
        logger.error('[IOT-CFG] send_iot_gateway_config_now error: {}'.format(e))
        return {'success': False, 'error': str(e)}

async def _send_iot_config(req):
    result = await send_iot_gateway_config_now()
    if result.get('success'):
        return _ok({'message': result.get('pipeline_message', 'Sent'),
                    'version': result.get('version'),
                    'pipeline_sent': result.get('pipeline_sent')})
    return _err(result.get('error', 'Failed to send'), 500)

async def _export_connections(req):
    """Exports all cloud connections to JSON or CSV.
    Verification commands:
      curl http://127.0.0.1:8082/api/cloud-integration/export?format=json
      curl http://127.0.0.1:8082/api/cloud-integration/export?format=csv
    """
    fmt = req.query.get('format', 'json').lower()
    try:
        db = get_db_connection()
        cur = db.cursor()
        
        # Fetch MQTT
        cur.execute('SELECT id,name,enabled,protocol,host,port,client_id,username,password,keepalive_sec,qos,base_topic,tls,json_template,channels_json,mappings_json,created_at,updated_at,device_token FROM mqtt_connections')
        mqtt_list = []
        for r in cur.fetchall():
            mqtt_list.append({
                'id': r[0], 'name': r[1], 'enabled': bool(r[2]),
                'protocol': r[3], 'host': r[4], 'port': r[5], 'client_id': r[6], 'username': r[7], 'password': r[8],
                'keepalive_sec': r[9], 'qos': r[10], 'base_topic': r[11], 'tls': bool(r[12]), 'json_template': r[13],
                'channels': _cfg(r[14]), 'mappings': _cfg(r[15]), 'created_at': r[16], 'updated_at': r[17],
                'device_token': r[18] or ''
            })
            
        # Fetch HTTP
        cur.execute('SELECT id,name,enabled,url,method,auth_token,headers_json,timeout_sec,channels_json,mappings_json,created_at,updated_at FROM http_connections')
        http_list = []
        for r in cur.fetchall():
            http_list.append({
                'id': r[0], 'name': r[1], 'enabled': bool(r[2]),
                'url': r[3], 'method': r[4], 'auth_token': r[5], 'headers': _cfg(r[6]), 'timeout_sec': r[7],
                'channels': _cfg(r[8]), 'mappings': _cfg(r[9]), 'created_at': r[10], 'updated_at': r[11]
            })
            
        db.close()
        
        if fmt == 'csv':
            import csv, io
            
            headers = [
                'type', 'id', 'name', 'enabled', 'protocol', 'host', 'port', 'client_id', 
                'username', 'password', 'keepalive_sec', 'qos', 'base_topic', 'tls', 
                'json_template', 'url', 'method', 'auth_token', 'headers_json', 
                'timeout_sec', 'channels_json', 'mappings_json', 'created_at', 'updated_at',
                'device_token'
            ]
            
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            
            for conn in mqtt_list:
                row = {
                    'type': 'mqtt',
                    'id': conn['id'], 'name': conn['name'], 'enabled': 1 if conn['enabled'] else 0,
                    'protocol': conn['protocol'], 'host': conn['host'], 'port': conn['port'],
                    'client_id': conn['client_id'], 'username': conn['username'], 'password': conn['password'],
                    'keepalive_sec': conn['keepalive_sec'], 'qos': conn['qos'], 'base_topic': conn['base_topic'],
                    'tls': 1 if conn['tls'] else 0, 'json_template': conn['json_template'],
                    'channels_json': json.dumps(conn['channels']), 'mappings_json': json.dumps(conn['mappings']),
                    'created_at': conn['created_at'], 'updated_at': conn['updated_at'],
                    'url': '', 'method': '', 'auth_token': '', 'headers_json': '', 'timeout_sec': '',
                    'device_token': conn['device_token']
                }
                writer.writerow(row)
                
            for conn in http_list:
                row = {
                    'type': 'http',
                    'id': conn['id'], 'name': conn['name'], 'enabled': 1 if conn['enabled'] else 0,
                    'url': conn['url'], 'method': conn['method'], 'auth_token': conn['auth_token'],
                    'headers_json': json.dumps(conn['headers']), 'timeout_sec': conn['timeout_sec'],
                    'channels_json': json.dumps(conn['channels']), 'mappings_json': json.dumps(conn['mappings']),
                    'created_at': conn['created_at'], 'updated_at': conn['updated_at'],
                    'protocol': '', 'host': '', 'port': '', 'client_id': '', 'username': '', 'password': '',
                    'keepalive_sec': '', 'qos': '', 'base_topic': '', 'tls': '', 'json_template': '',
                    'device_token': ''
                }
                writer.writerow(row)
                
            resp = web.Response(text=output.getvalue(), content_type='text/csv')
            resp.headers['Content-Disposition'] = 'attachment; filename="cloud_connections.csv"'
            return resp
            
        else: # default json
            data = {
                'version': 1,
                'mqtt_connections': mqtt_list,
                'http_connections': http_list
            }
            resp = web.Response(text=json.dumps(data, indent=2), content_type='application/json')
            resp.headers['Content-Disposition'] = 'attachment; filename="cloud_connections.json"'
            return resp
            
    except Exception as e:
        return _err(str(e), 500)

async def _import_connections(req):
    """Imports connections from uploaded JSON/CSV data.
    Verification command:
      curl -X POST -H "Content-Type: application/json" -d "@exported_connections.json" http://127.0.0.1:8082/api/cloud-integration/import
    """
    try:
        content_type = req.content_type
        content = ""
        filename = ""
        
        if content_type.startswith('multipart/form-data'):
            reader = await req.multipart()
            field = await reader.next()
            while field:
                if field.name == 'file':
                    filename = field.filename
                    content_bytes = await field.read()
                    content = content_bytes.decode('utf-8')
                    break
                field = await reader.next()
            if not content:
                return _err("No file uploaded under key 'file'")
        else:
            content = await req.text()
            filename = "import.json" if "json" in content_type else "import.csv"

        # Determine if CSV
        is_csv = False
        if filename.endswith('.csv') or 'csv' in content_type or (content.strip().startswith('type,id,name') or 'channels_json' in content):
            is_csv = True
            
        def _int_val(val, default):
            try:
                if val is None or str(val).strip() == '':
                    return default
                return int(float(str(val).strip()))
            except:
                return default

        db = get_db_connection()
        cur = db.cursor()
        imported_count = 0
        
        if is_csv:
            import csv, io
            f = io.StringIO(content)
            reader = csv.DictReader(f)
            
            for row in reader:
                ctype = row.get('type', '').lower().strip()
                if ctype not in ('mqtt', 'http'):
                    continue
                cid = row.get('id', '').strip()
                if not cid:
                    cid = _gid(ctype)
                name = row.get('name', 'Imported Connection').strip()
                enabled = _int_val(row.get('enabled'), 1)
                
                # Delete existing connection to trigger ON DELETE CASCADE
                cur.execute("DELETE FROM {}_connections WHERE id=?".format(ctype), (cid,))
                
                channels_str = row.get('channels_json') or '[]'
                mappings_str = row.get('mappings_json') or '[]'
                
                if ctype == 'mqtt':
                    cur.execute('''INSERT OR REPLACE INTO mqtt_connections(
                        id, name, enabled, protocol, host, port, client_id, username, password,
                        keepalive_sec, qos, base_topic, tls, json_template, channels_json, mappings_json, device_token
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                        cid, name, enabled,
                        row.get('protocol') or 'mqtts',
                        row.get('host') or '',
                        _int_val(row.get('port'), 8883),
                        row.get('client_id') or '',
                        row.get('username') or '',
                        row.get('password') or '',
                        _int_val(row.get('keepalive_sec'), 60),
                        _int_val(row.get('qos'), 1),
                        row.get('base_topic') or 'gateway/data',
                        _int_val(row.get('tls'), 1),
                        row.get('json_template') or '{"timestamp":"%TIMESTAMP%","device":"%DEVICE_ID%","data":%DATA%}',
                        channels_str,
                        mappings_str,
                        row.get('device_token') or ''
                    ))
                    _sync_datapoints_for_connection(cur, cid, 'mqtt', channels_str, mappings_str, row.get('base_topic') or 'gateway/data')
                    
                elif ctype == 'http':
                    headers_str = row.get('headers_json') or '{}'
                    cur.execute('''INSERT OR REPLACE INTO http_connections(
                        id, name, enabled, url, method, auth_token, headers_json, timeout_sec, channels_json, mappings_json
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)''', (
                        cid, name, enabled,
                        row.get('url') or '',
                        row.get('method') or 'POST',
                        row.get('auth_token') or '',
                        headers_str,
                        _int_val(row.get('timeout_sec'), 30),
                        channels_str,
                        mappings_str
                    ))
                    _sync_datapoints_for_connection(cur, cid, 'http', channels_str, mappings_str, '')
                
                _ensure_stats(cur, cid)
                imported_count += 1
                
        else: # JSON
            data = json.loads(content)
            mqtt_connections = []
            http_connections = []
            
            if isinstance(data, dict):
                mqtt_connections = data.get('mqtt_connections') or data.get('mqtt') or []
                http_connections = data.get('http_connections') or data.get('http') or []
            elif isinstance(data, list):
                for item in data:
                    ctype = item.get('type', '').lower().strip()
                    if ctype == 'mqtt':
                        mqtt_connections.append(item)
                    elif ctype == 'http':
                        http_connections.append(item)
            
            for conn in mqtt_connections:
                cid = conn.get('id')
                if not cid:
                    cid = _gid('mqtt')
                name = conn.get('name', 'Imported MQTT Connection').strip()
                enabled = 1 if conn.get('enabled', True) else 0
                
                cur.execute("DELETE FROM mqtt_connections WHERE id=?", (cid,))
                
                channels = conn.get('channels') or _cfg(conn.get('channels_json'))
                mappings = conn.get('mappings') or _cfg(conn.get('mappings_json'))
                
                cur.execute('''INSERT OR REPLACE INTO mqtt_connections(
                    id, name, enabled, protocol, host, port, client_id, username, password,
                    keepalive_sec, qos, base_topic, tls, json_template, channels_json, mappings_json, device_token
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                    cid, name, enabled,
                    conn.get('protocol') or 'mqtts',
                    conn.get('host') or '',
                    _int_val(conn.get('port'), 8883),
                    conn.get('client_id') or '',
                    conn.get('username') or '',
                    conn.get('password') or '',
                    _int_val(conn.get('keepalive_sec') or conn.get('keepAlive'), 60),
                    _int_val(conn.get('qos'), 1),
                    conn.get('base_topic') or conn.get('baseTopic') or 'gateway/data',
                    1 if conn.get('tls', True) else 0,
                    conn.get('json_template') or conn.get('jsonTemplate') or '{"timestamp":"%TIMESTAMP%","device":"%DEVICE_ID%","data":%DATA%}',
                    json.dumps(channels),
                    json.dumps(mappings),
                    conn.get('device_token') or conn.get('deviceToken') or ''
                ))
                _sync_datapoints_for_connection(cur, cid, 'mqtt', channels, mappings, conn.get('base_topic') or conn.get('baseTopic') or 'gateway/data')
                _ensure_stats(cur, cid)
                imported_count += 1
                
            for conn in http_connections:
                cid = conn.get('id')
                if not cid:
                    cid = _gid('http')
                name = conn.get('name', 'Imported HTTP Connection').strip()
                enabled = 1 if conn.get('enabled', True) else 0
                
                cur.execute("DELETE FROM http_connections WHERE id=?", (cid,))
                
                channels = conn.get('channels') or _cfg(conn.get('channels_json'))
                mappings = conn.get('mappings') or _cfg(conn.get('mappings_json'))
                headers = conn.get('headers') or _cfg(conn.get('headers_json'))
                
                cur.execute('''INSERT OR REPLACE INTO http_connections(
                    id, name, enabled, url, method, auth_token, headers_json, timeout_sec, channels_json, mappings_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?)''', (
                    cid, name, enabled,
                    conn.get('url') or '',
                    conn.get('method') or 'POST',
                    conn.get('auth_token') or conn.get('authToken') or '',
                    json.dumps(headers),
                    _int_val(conn.get('timeout_sec') or conn.get('timeout'), 30),
                    json.dumps(channels),
                    json.dumps(mappings)
                ))
                _sync_datapoints_for_connection(cur, cid, 'http', channels, mappings, '')
                _ensure_stats(cur, cid)
                imported_count += 1
                
        db.commit()
        db.close()
        return _ok({'message': 'Successfully imported {} connections'.format(imported_count), 'count': imported_count})
        
    except Exception as e:
        return _err(str(e), 500)