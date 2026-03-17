# mqtt_cloud.py
# Tables: cloud_connections, mqtt_datapoints, cloud_connection_stats
import json, time, asyncio
from aiohttp import web
from database import get_db_connection

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
    app.router.add_post  ('/api/cloud-integration/send-iot-config',                _send_iot_config)

# --- TYPE DEFAULTS ------------------------------------------------------------
_DEFAULTS = {
    'mqtt': {
        'protocol':'mqtts','host':'','port':8883,'clientId':'','keepAlive':60,
        'username':'','password':'','tls':True,'cleanSession':True,'retainMessages':False,'qos':1,
        'baseTopic':'gateway/data',
        'jsonTemplate':'{"timestamp":"%TIMESTAMP%","device":"%DEVICE_ID%","data":%DATA%}',
        'autoReconnect':True,'reconnectInterval':5,'connectTimeout':30,'maxRetries':5,
        'storeForward':False,'validateCerts':True,'logLevel':'info',
        'maxInflight':10,'queueSize':100,'bufferSize':1024,'pingTimeout':10,
        'compression':False,'compressionLevel':6,'minCompressSize':256,
        'tlsVersion':'auto','cipherSuite':'default',
        'lwt':False,'lwtTopic':'','lwtMessage':'','lwtQos':1,'lwtRetain':False,
        'connLogging':True,'msgLogging':False,'maxLogSize':10,'logRetention':7,
    },
    'ftp': {
        'host':'','port':21,'protocol':'ftp','mode':'passive',
        'username':'','password':'','anonymous':False,
        'remotePath':'/uploads/','filenamePattern':'data_${DATE}.csv',
        'fileFormat':'csv','maxFileSize':10485760,
        'uploadInterval':300,'appendMode':True,'compressFiles':True,'retryAttempts':3,
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
        cur.execute('SELECT tag_name,topic,publish_mode,change_threshold,enabled FROM mqtt_datapoints WHERE connection_id=? ORDER BY tag_name',(cid,))
        return [{'name':r[0],'topic':r[1],'publishMode':r[2],'changeThreshold':r[3],'enabled':bool(r[4])} for r in cur.fetchall()]
    return []

def _fetch_stats(cur, cid):
    cur.execute('SELECT messages_total,messages_ok,messages_failed,latency_avg_ms,last_active FROM cloud_connection_stats WHERE connection_id=?',(cid,))
    r=cur.fetchone()
    if not r: return {'messages':0,'ok':0,'failed':0,'latency':0,'lastActive':'Never','successRate':0}
    tot,ok,fail,lat,last=r
    return {'messages':tot or 0,'ok':ok or 0,'failed':fail or 0,'latency':round(lat or 0,1),
            'lastActive':last or 'Never','successRate':round((ok/tot*100) if tot else 0,1)}

def _row_dict(r, cur):
    cid,ctype,name,enabled,cfg_raw,ca,ua = r
    return {'id':cid,'type':ctype,'name':name,'enabled':bool(enabled),
            'config':_cfg(cfg_raw),'tags':_fetch_tags(cur,cid,ctype),
            'statistics':_fetch_stats(cur,cid),'created_at':ca,'updated_at':ua}

# --- HANDLERS -----------------------------------------------------------------
async def _connection_types(req):
    return _ok({'types':[
        {'id':'mqtt','name':'MQTT Broker',   'description':'Standard IoT messaging protocol','icon':'fa-solid fa-cloud','color':'#3B82F6'},
        {'id':'ftp', 'name':'FTP Server',    'description':'File transfer via FTP/SFTP/FTPS','icon':'fa-solid fa-folder-open','color':'#10B981'},
    ]})

async def _list(req):
    try:
        db=get_db_connection(); cur=db.cursor()
        cur.execute('SELECT id,type,name,enabled,config,created_at,updated_at FROM cloud_connections ORDER BY created_at DESC')
        result=[_row_dict(r,cur) for r in cur.fetchall()]
        db.close()
        return _ok({'connections':result,'total':len(result)})
    except Exception as e: return _err(str(e),500)

async def _create(req):
    try: body=await req.json()
    except: return _err('Invalid JSON')
    ctype=(body.get('type') or '').lower()
    if ctype not in ('mqtt','ftp'): return _err('Invalid type: {}'.format(ctype))
    name=(body.get('name') or '').strip()
    if not name: return _err('name is required')
    config={**_DEFAULTS[ctype],**(body.get('connection') or body.get('config') or {})}
    cid=_gid(ctype)
    try:
        db=get_db_connection(); cur=db.cursor()
        cur.execute('INSERT INTO cloud_connections(id,type,name,enabled,config) VALUES(?,?,?,?,?)',
                    (cid,ctype,name,1 if body.get('enabled',True) else 0,json.dumps(config)))
        _ensure_stats(cur,cid)
        db.commit(); db.close()
        return _ok({'id':cid,'message':'"{}" created'.format(name)},201)
    except Exception as e: return _err(str(e),500)

async def _get(req):
    cid=req.match_info['id']
    try:
        db=get_db_connection(); cur=db.cursor()
        cur.execute('SELECT id,type,name,enabled,config,created_at,updated_at FROM cloud_connections WHERE id=?',(cid,))
        r=cur.fetchone()
        if not r: db.close(); return _err('Not found',404)
        result=_row_dict(r,cur); db.close()
        return _ok(result)
    except Exception as e: return _err(str(e),500)

async def _update(req):
    cid=req.match_info['id']
    try: body=await req.json()
    except: return _err('Invalid JSON')
    try:
        db=get_db_connection(); cur=db.cursor()
        cur.execute('SELECT config FROM cloud_connections WHERE id=?',(cid,))
        r=cur.fetchone()
        if not r: db.close(); return _err('Not found',404)
        merged={**_cfg(r[0]),**(body.get('config') or {})}
        sets=['config=?','updated_at=CURRENT_TIMESTAMP']; vals=[json.dumps(merged)]
        if body.get('name'): sets.append('name=?'); vals.append(body['name'].strip())
        if 'enabled' in body: sets.append('enabled=?'); vals.append(1 if body['enabled'] else 0)
        vals.append(cid)
        cur.execute('UPDATE cloud_connections SET {} WHERE id=?'.format(','.join(sets)),vals)
        db.commit(); db.close()
        return _ok({'message':'Updated'})
    except Exception as e: return _err(str(e),500)

async def _delete(req):
    cid=req.match_info['id']
    try:
        db=get_db_connection(); cur=db.cursor()
        cur.execute('SELECT id FROM cloud_connections WHERE id=?',(cid,))
        if not cur.fetchone(): db.close(); return _err('Not found',404)
        cur.execute('DELETE FROM cloud_connections WHERE id=?',(cid,))
        db.commit(); db.close()
        return _ok({'message':'Deleted'})
    except Exception as e: return _err(str(e),500)

async def _toggle(req):
    """Toggle enabled. Returns the NEW state read back from DB -- never trust body."""
    cid=req.match_info['id']
    try:
        db=get_db_connection(); cur=db.cursor()
        cur.execute('SELECT enabled FROM cloud_connections WHERE id=?',(cid,))
        r=cur.fetchone()
        if not r: db.close(); return _err('Not found',404)
        new_val = 0 if bool(r[0]) else 1          # flip current
        cur.execute('UPDATE cloud_connections SET enabled=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(new_val,cid))
        db.commit()
        # Read back to confirm
        cur.execute('SELECT enabled FROM cloud_connections WHERE id=?',(cid,))
        confirmed = bool(cur.fetchone()[0])
        db.close()
        return _ok({'enabled': confirmed, 'message': 'enabled' if confirmed else 'disabled'})
    except Exception as e: return _err(str(e),500)

async def _get_tags(req):
    cid=req.match_info['id']
    try:
        db=get_db_connection(); cur=db.cursor()
        cur.execute('SELECT type FROM cloud_connections WHERE id=?',(cid,))
        r=cur.fetchone()
        if not r: db.close(); return _err('Not found',404)
        t=_fetch_tags(cur,cid,r[0]); db.close()
        return _ok({'connection_id':cid,'tags':t,'total':len(t)})
    except Exception as e: return _err(str(e),500)

async def _assign_tags(req):
    cid=req.match_info['id']
    try: body=await req.json()
    except: return _err('Invalid JSON')
    tag_list=body.get('tags') or []; mode=body.get('publishMode','onChange')
    thresh=float(body.get('changeThreshold',0.0)); replace=bool(body.get('replace',False))
    try:
        db=get_db_connection(); cur=db.cursor()
        cur.execute('SELECT type FROM cloud_connections WHERE id=?',(cid,))
        r=cur.fetchone()
        if not r: db.close(); return _err('Not found',404)
        ctype=r[0]
        if ctype != 'mqtt': db.close(); return _err('Tags not supported for this connection type',400)
        if replace: cur.execute('DELETE FROM mqtt_datapoints WHERE connection_id=?',(cid,))
        for tag in tag_list:
            cur.execute('INSERT OR REPLACE INTO mqtt_datapoints(connection_id,tag_name,topic,publish_mode,change_threshold,enabled) VALUES(?,?,?,?,?,1)',(cid,tag,'',mode,thresh))
        db.commit(); db.close()
        return _ok({'message':'{} tag(s) assigned'.format(len(tag_list))})
    except Exception as e: return _err(str(e),500)

async def _remove_tag(req):
    cid=req.match_info['id']; tag=req.match_info['tag']
    try:
        db=get_db_connection(); cur=db.cursor()
        cur.execute('SELECT type FROM cloud_connections WHERE id=?',(cid,))
        r=cur.fetchone()
        if not r: db.close(); return _err('Not found',404)
        tbl={'mqtt':'mqtt_datapoints'}[r[0]]
        cur.execute('DELETE FROM {} WHERE connection_id=? AND tag_name=?'.format(tbl),(cid,tag))
        db.commit(); db.close()
        return _ok({'message':'Tag removed'})
    except Exception as e: return _err(str(e),500)

async def _available_tags(req):
    # Maps vfd_datapoints.data_type -> simplified dtype for the frontend
    def _map_dtype(data_type):
        dt = (data_type or '').lower()
        if 'bool' in dt:   return 'bool'
        if 'float' in dt:  return 'float'
        if 'int' in dt:    return 'int'
        return 'float'
    try:
        db=get_db_connection(); cur=db.cursor()
        cur.execute('''SELECT md.name,COALESCE(md.unit,''),md.device_id,COALESCE(dev.name,''),'modbus',COALESCE(md.data_type,'float32')
                       FROM vfd_datapoints md LEFT JOIN vfd_device dev ON dev.id=md.device_id WHERE md.enabled=1''')
        tags=[{'name':r[0],'unit':r[1],'deviceId':r[2],'device':r[3],'source':r[4],'dtype':_map_dtype(r[5])} for r in cur.fetchall()]
        cur.execute('''SELECT ld.name,'',ld.device_id,COALESCE(lc.name,''),'loadcell'
                       FROM loadcell_datapoints ld LEFT JOIN loadcell_device lc ON lc.id=ld.device_id''')
        tags+=[{'name':r[0],'unit':r[1],'deviceId':r[2],'device':r[3],'source':r[4],'dtype':'float'} for r in cur.fetchall()]
        # Include virtual datapoints
        try:
            cur.execute('''SELECT vd.name,COALESCE(vd.unit,''),vd.device_id,COALESCE(vdev.name,''),'virtual'
                           FROM virtual_datapoints vd LEFT JOIN virtual_device vdev ON vdev.id=vd.device_id''')
            tags+=[{'name':r[0],'unit':r[1],'deviceId':r[2],'device':r[3],'source':r[4],'dtype':'float'} for r in cur.fetchall()]
        except Exception as e:
            print('[MQTT] virtual_datapoints query error: {}'.format(e))
        db.close()
        return _ok({'tags':tags,'total':len(tags)})
    except Exception as e: return _err(str(e),500)

async def _save_all(req):
    try:
        db=get_db_connection(); cur=db.cursor()
        cur.execute('SELECT COUNT(*) FROM cloud_connections')
        n=cur.fetchone()[0]; db.close()
        # Sync iot_gateway_config whenever connections are saved
        try:
            await send_iot_gateway_config_now()
        except Exception as _e:
            print('[IOT-CFG] sync error in _save_all: {}'.format(_e))
        return _ok({'message':'Saved ({} connections)'.format(n),'total':n})
    except Exception as e: return _err(str(e),500)

# =============================================================================
# IOT GATEWAY CONFIG BUILDER
# =============================================================================
#
#  JSON structure matches ilx_iot_gateway-config.json schema:
#
#  {
#    version, system:{wifi_ssid, wifi_password},
#    heartbeat:{interval_sec, channel},
#    servers:{
#      mqtt:{enabled, host, port, client_id, device_token, username, password,
#            keepalive_sec, channels:{publish:[...], subscribe:[...]}},
#      mqtt_cloud:{...same...}
#    },
#    mappings:[
#      {alias, channel, datapoints:{int:[...], float:[...], bool:[...]}},
#      {channel, datapoints:{...}}          // individual (no alias)
#    ]
#  }
#
#  Channel auto-assign rules:
#    - Group (has alias): use mapping.channel if set,
#                         else use connection's first default publish channel,
#                         else 'default_publish'
#    - Individual (no alias): same fallback
#
# =============================================================================

def _get_default_channel_for_connection(conn_config):
    """Return the name of the default (or first) publish channel for a connection."""
    channels = conn_config.get('channels', {})
    publish  = channels.get('publish', [])
    if not publish:
        return 'default_publish'
    # Prefer channel explicitly marked default=True
    for ch in publish:
        if ch.get('default'):
            return ch.get('name', 'default_publish')
    # Fall back to first channel
    return publish[0].get('name', 'default_publish')


def build_iot_gateway_config():
    """Build the complete iot_gateway JSON config from the database.

    Returns a dict ready to be json.dumps()-ed.

    - wifi credentials come from general_configuration (network.wifi.ssid / .password)
    - heartbeat.channel is taken from the first publish channel of the local MQTT
      broker connection so it always matches whatever is configured in the MQTT form
    """
    from database import get_general_configuration, get_db_connection
    import time as _time

    # -- 1. General config: wifi + heartbeat ----------------------------------
    gen  = get_general_configuration()
    wifi = gen.get('network', {}).get('wifi', {})
    hb   = gen.get('heartbeat', {})

    wifi_ssid     = wifi.get('ssid',     '')
    wifi_password = wifi.get('password', '')
    heartbeat_sec = int(hb.get('interval', 30))

    # -- 2. Load all enabled MQTT connections ---------------------------------
    db  = get_db_connection()
    cur = db.cursor()
    cur.execute(
        "SELECT id, name, enabled, config FROM cloud_connections WHERE type='mqtt' ORDER BY created_at")
    rows = cur.fetchall()
    db.close()

    servers          = {}
    all_mappings     = []
    heartbeat_channel = 'default_publish'   # updated from local broker's first publish channel

    for row in rows:
        cid, name, enabled, cfg_raw = row
        cfg = _cfg(cfg_raw)

        # Canonical server key: local broker ? 'mqtt', cloud/CMS ? 'mqtt_cloud'
        server_key = name.lower().replace(' ', '_').replace('-', '_')
        if 'cloud' in server_key or 'cms' in server_key:
            server_key = 'mqtt_cloud'
        else:
            server_key = 'mqtt'

        raw_pub = cfg.get('channels', {}).get('publish',   [])
        raw_sub = cfg.get('channels', {}).get('subscribe', [])

        server_entry = {
            'enabled':       bool(enabled),
            'host':          cfg.get('host', '127.0.0.1'),
            'port':          int(cfg.get('port', 1883)),
            'client_id':     cfg.get('client_id', ''),
            'device_token':  cfg.get('device_token', ''),
            'username':      cfg.get('username', ''),
            'password':      cfg.get('password', ''),
            'keepalive_sec': int(cfg.get('keepalive_sec', 60)),
            'channels': {
                'publish':   [raw_pub[0]] if raw_pub else [],
                'subscribe': [raw_sub[0]] if raw_sub else [],
            },
        }
        if cfg.get('secure_token'):
            server_entry['secure_token'] = cfg['secure_token']

        servers[server_key] = server_entry

        # heartbeat.channel = the 'name' field of publish channel[0]
        # e.g. {"topic":"default_pubtopic_cms","name":"receive",...} -> "receive"
        # applies to whichever connection is configured (mqtt or mqtt_cloud)
        if raw_pub:
            heartbeat_channel = raw_pub[0].get('name', 'default_publish')

        # Collect mappings   groups pass through as-is;
        # individual tags each become their own mapping entry.
        default_ch   = _get_default_channel_for_connection(cfg)
        raw_mappings = cfg.get('mappings', [])

        for m in raw_mappings:
            channel = m.get('channel') or default_ch
            if m.get('alias'):
                # Group: preserve alias, type, channel, and datapoints as-is
                # datapoints entries may be plain strings or {name, alias} objects
                entry = {
                    'alias':      m['alias'],
                    'channel':    channel,
                    'datapoints': m.get('datapoints', {}),
                }
                all_mappings.append(entry)
            else:
                # Individual: one mapping entry per tag, preserving {name, alias} or plain string
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
            'wifi_ssid':     wifi_ssid,
            'wifi_password': wifi_password,
        },
        'heartbeat': {
            'interval_sec': heartbeat_sec,
            'channel':      heartbeat_channel,
        },
        'servers':  servers,
        'mappings': all_mappings,
    }


async def send_iot_gateway_config_now():
    """Convenience coroutine: build config and dispatch via pipeline.
    Safe to call from any async context (general_config save, cloud save, startup).
    """
    try:
        from pipeline import send_iot_gateway_config_now as _pipeline_send
        return await _pipeline_send()
    except Exception as e:
        print('[IOT-CFG] send_iot_gateway_config_now error: {}'.format(e))
        return {'success': False, 'error': str(e)}


async def _send_iot_config(req):
    """POST /api/cloud-integration/send-iot-config
    Build and push the iot_gateway_config to the pipeline service.
    """
    result = await send_iot_gateway_config_now()
    if result.get('success'):
        return _ok({'message': result.get('pipeline_message', 'Sent'),
                    'version': result.get('version'),
                    'pipeline_sent': result.get('pipeline_sent')})
    return _err(result.get('error', 'Failed to send'), 500)