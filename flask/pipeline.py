# -*- coding: utf-8 -*-
# pipeline.py - Pipeline (Load Cell) module
#
# BUGS FIXED:
#   1. _WS_ERROR=258 was wrong for aiohttp 2.0.7 — replaced with aiohttp.MsgType enum
#   2. No auth on /ws/pipeline/load_raw — added ws_auth() check before ws.prepare()
#   3. Ping frames not handled in WS receive loop — added MsgType.ping -> ws.pong()
#   4. Race: main_loop cleared on disconnect while thread may still broadcast
#      — thread now reads main_loop inside the lock for atomic check

import asyncio
import json
import logging
import sqlite3
import threading

from aiohttp import web
from aiohttp import WSMsgType as MsgType   # aiohttp 3.x uses WSMsgType; alias as MsgType for clarity

try:
    from ilx_pipeline import PipelineClient, EventType, DataType
    PIPELINE_AVAILABLE = True
    print("[PIPELINE] ilx_pipeline imported OK")
except ImportError:
    PIPELINE_AVAILABLE = False
    print("[PIPELINE] WARNING: ilx_pipeline not available!")

from database import DB_FILE
from auth import ws_auth

# ---------------------------------------------------------------------------
# Shared pipeline state
# ---------------------------------------------------------------------------
pipeline_state = {
    "client":     None,
    "connected":  False,
    "load_raw":   None,
    "ws_clients": set(),
    "lock":       threading.Lock(),
    "main_loop":  None,
}


# ---------------------------------------------------------------------------
# Broadcast helper
# ---------------------------------------------------------------------------
async def _broadcast_pipeline_msg(msg):
    dead = set()
    clients = list(pipeline_state["ws_clients"])
    print("[PIPELINE] broadcasting to {} WS clients: {}".format(len(clients), msg[:80]))
    for ws in clients:
        if ws.closed:
            dead.add(ws)
            continue
        try:
            await ws.send_str(msg)
        except Exception as e:
            print("[PIPELINE] WS send failed: {}".format(e))
            dead.add(ws)
    for ws in dead:
        pipeline_state["ws_clients"].discard(ws)


# ---------------------------------------------------------------------------
# HTTP handlers
# ---------------------------------------------------------------------------

async def pipeline_connect_handler(request):
    """POST /api/pipeline/connect"""
    if not PIPELINE_AVAILABLE:
        return web.json_response({"success": False, "error": "ilx_pipeline not available"})

    with pipeline_state["lock"]:
        if pipeline_state["connected"] and pipeline_state["client"]:
            return web.json_response({"success": True, "message": "Already connected"})

    try:
        body = await request.json()
    except Exception:
        body = {}

    host = body.get("host", "127.0.0.1")
    port = body.get("port", 7000)

    print("[PIPELINE] Connecting to {}:{}".format(host, port))

    main_loop = asyncio.get_event_loop()
    pipeline_state["main_loop"] = main_loop

    connected_event = threading.Event()

    def _run_pipeline():
        try:
            print("[PIPELINE] Thread started, creating PipelineClient...")
            client = PipelineClient("craneiq_loadcell_listener", host, port, 1000, 10)
            client.set_connection_timeout(5)

            def on_event(event):
                try:
                    etype = event.event_type

                    if etype == EventType.PIPELINE_CONNECTED:
                        print("[PIPELINE] EVENT: CONNECTED")
                        with pipeline_state["lock"]:
                            pipeline_state["connected"] = True
                        connected_event.set()

                    elif etype == EventType.PIPELINE_OFFLINE:
                        print("[PIPELINE] EVENT: OFFLINE")
                        with pipeline_state["lock"]:
                            pipeline_state["connected"] = False

                    elif etype == EventType.RECEIVE_DONE:
                        dp = event.datapoint_name
                        try:
                            dtype = client.get_datapoint_type(dp)

                            if dtype == DataType.FLOAT:
                                val = client.get_datapoint_float(dp)
                            elif dtype == DataType.DOUBLE:
                                val = client.get_datapoint_double(dp)
                            elif dtype == DataType.INT:
                                val = client.get_datapoint_integer(dp)
                            elif dtype == DataType.LONG:
                                val = client.get_datapoint_long(dp)
                            elif dtype == DataType.BOOL:
                                val = client.get_datapoint_boolean(dp)
                            else:
                                val = client.get_datapoint_string(dp)

                            print("[PIPELINE] RECEIVE_DONE dp={} val={}".format(dp, val))

                            # FIX 4: Read main_loop INSIDE the lock so we get an atomic
                            # view — disconnect() also holds the lock when it clears it,
                            # eliminating the race between save and schedule.
                            with pipeline_state["lock"]:
                                pipeline_state[dp] = val
                                if dp == "load_raw":
                                    pipeline_state["load_raw"] = val
                                loop = pipeline_state["main_loop"]

                            if loop is not None:
                                msg = json.dumps({"datapoint": dp, "value": val})
                                asyncio.run_coroutine_threadsafe(
                                    _broadcast_pipeline_msg(msg), loop
                                )
                            else:
                                print("[PIPELINE] main_loop cleared (disconnect in progress), skipping broadcast")

                        except Exception as e:
                            print("[PIPELINE] ERROR reading dp {}: {}".format(dp, e))

                    else:
                        print("[PIPELINE] EVENT: unknown type={}".format(etype))

                except Exception as e:
                    print("[PIPELINE] EVENT handler error: {}".format(e))

            client.set_event_callback(on_event)
            print("[PIPELINE] Starting client...")
            client.start()

            print("[PIPELINE] Waiting for connection (5s)...")
            ok = client.wait_until_connected(5000)
            print("[PIPELINE] wait_until_connected returned: {}".format(ok))

            with pipeline_state["lock"]:
                pipeline_state["client"]    = client
                pipeline_state["connected"] = ok

            if ok:
                connected_event.set()
            else:
                print("[PIPELINE] Connection FAILED")

        except Exception as e:
            print("[PIPELINE] Thread exception: {}".format(e))
            with pipeline_state["lock"]:
                pipeline_state["connected"] = False
            connected_event.set()

    thread = threading.Thread(target=_run_pipeline, daemon=True)
    thread.start()

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: connected_event.wait(6))

    with pipeline_state["lock"]:
        ok = pipeline_state["connected"]

    print("[PIPELINE] Connect handler returning connected={}".format(ok))

    if ok:
        return web.json_response({"success": True, "message": "Connected to pipeline"})
    else:
        return web.json_response({
            "success": False,
            "error": "Could not connect to pipeline server at {}:{}".format(host, port)
        })


async def pipeline_disconnect_handler(request):
    """POST /api/pipeline/disconnect"""
    with pipeline_state["lock"]:
        client = pipeline_state.get("client")
        if client:
            try:
                client.stop()
            except Exception:
                pass
        pipeline_state["client"]    = None
        pipeline_state["connected"] = False
        pipeline_state["load_raw"]  = None
        # FIX 4: Clear inside lock so the broadcast thread sees None atomically
        pipeline_state["main_loop"] = None
    print("[PIPELINE] Disconnected.")
    return web.json_response({"success": True, "message": "Disconnected"})


async def pipeline_status_handler(request):
    """GET /api/pipeline/status"""
    with pipeline_state["lock"]:
        return web.json_response({
            "connected": pipeline_state["connected"],
            "load_raw":  pipeline_state["load_raw"],
        })


async def pipeline_loadraw_ws_handler(request):
    """WebSocket /ws/pipeline/load_raw"""

    # FIX 2: Auth check — endpoint had zero authentication before
    user = ws_auth(request)
    if user is None:
        return web.Response(status=401, text='Unauthorized')

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    pipeline_state["ws_clients"].add(ws)
    print("[PIPELINE] WS client connected (user={}), total={}".format(
        user, len(pipeline_state["ws_clients"])))

    # Send buffered value immediately
    with pipeline_state["lock"]:
        current_raw = pipeline_state["load_raw"]

    if current_raw is not None:
        try:
            await ws.send_str(json.dumps({"datapoint": "load_raw", "value": current_raw}))
            print("[PIPELINE] Sent buffered load_raw={} to new client".format(current_raw))
        except Exception as e:
            print("[PIPELINE] Could not send buffered value: {}".format(e))

    try:
        while True:
            msg = await ws.receive()

            # FIX 1: Use MsgType enum — _WS_ERROR=258 was wrong for aiohttp 2.0.7
            if msg.type == MsgType.close:
                break

            elif msg.type == MsgType.error:
                print("[PIPELINE] WS error (user={}): {}".format(user, ws.exception()))
                break

            # FIX 3: Respond to ping frames — prevents proxy from killing idle connections
            elif msg.type == MsgType.ping:
                await ws.pong()

            # Pipeline WS is server-push only; client text messages are ignored

    except Exception as e:
        print("[PIPELINE] WS receive error (user={}): {}".format(user, e))
    finally:
        pipeline_state["ws_clients"].discard(ws)
        print("[PIPELINE] WS client disconnected (user={}), total={}".format(
            user, len(pipeline_state["ws_clients"])))

    return ws


async def pipeline_loadcell_devices_handler(request):
    """GET /api/pipeline/loadcell-devices"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, device_path, channel, unit, capacity,
                   tare_offset, known_weight, known_weight_raw,
                   pipeline_server, pipeline_port,
                   lowpass_filter_enabled, filter_cutoff_frequency, filter_activation_delta_min,
                   moving_avg_enabled, moving_avg_window,
                   median_filter_enabled, median_filter_window,
                   autotare_enabled, autotare_trigger_delta_grams,
                   adaptive_deadband_enabled, adaptive_deadband_min, adaptive_deadband_max,
                   adaptive_deadband_grow_rate, adaptive_deadband_shrink_rate,
                   publish_step_grams, overload_threshold, overload_relay,
                   overload_action, overload_cooldown_ms, confirm_count, enabled
            FROM loadcell_device WHERE enabled = 1
        ''')
        rows = cursor.fetchall()
        conn.close()
        devices = []
        for r in rows:
            d = dict(r)
            d['lowpass_filter_enabled']    = bool(d['lowpass_filter_enabled'])
            d['moving_avg_enabled']        = bool(d['moving_avg_enabled'])
            d['median_filter_enabled']     = bool(d['median_filter_enabled'])
            d['autotare_enabled']          = bool(d['autotare_enabled'])
            d['adaptive_deadband_enabled'] = bool(d['adaptive_deadband_enabled'])
            devices.append(d)
        return web.json_response({"devices": devices})
    except Exception as e:
        logging.error("loadcell_devices error: %s", e)
        return web.json_response({"devices": [], "error": str(e)})


async def pipeline_calibration_get_handler(request):
    """GET /api/pipeline/calibration?device_id=<id>"""
    try:
        device_id = request.rel_url.query.get('device_id')
        if not device_id:
            return web.json_response({"error": "device_id required"}, status=400)
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            'SELECT tare_offset, known_weight, known_weight_raw FROM loadcell_device WHERE id = ?',
            (device_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return web.json_response({"error": "device not found"}, status=404)
        return web.json_response(dict(row))
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def pipeline_calibration_post_handler(request):
    """POST /api/pipeline/calibration"""
    try:
        body             = await request.json()
        device_id        = body.get("device_id")
        tare_offset      = body.get("tare_offset")
        known_weight     = body.get("known_weight")
        known_weight_raw = body.get("known_weight_raw")

        if not device_id:
            return web.json_response({"success": False, "error": "device_id required"})

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE loadcell_device
            SET tare_offset = ?, known_weight = ?, known_weight_raw = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (tare_offset, known_weight, known_weight_raw, device_id))
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        if affected == 0:
            return web.json_response({"success": False, "error": "Device not found"})
        return web.json_response({"success": True})
    except Exception as e:
        logging.error("calibration save error: %s", e)
        return web.json_response({"success": False, "error": str(e)})


async def pipeline_filters_post_handler(request):
    """POST /api/pipeline/filters"""
    try:
        body      = await request.json()
        device_id = body.get("device_id")
        filters   = body.get("filters", {})

        if not device_id:
            return web.json_response({"success": False, "error": "device_id required"})

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE loadcell_device SET
                lowpass_filter_enabled        = ?,
                filter_cutoff_frequency       = ?,
                filter_activation_delta_min   = ?,
                moving_avg_enabled            = ?,
                moving_avg_window             = ?,
                median_filter_enabled         = ?,
                median_filter_window          = ?,
                autotare_enabled              = ?,
                autotare_trigger_delta_grams  = ?,
                adaptive_deadband_enabled     = ?,
                adaptive_deadband_min         = ?,
                adaptive_deadband_max         = ?,
                adaptive_deadband_grow_rate   = ?,
                adaptive_deadband_shrink_rate = ?,
                publish_step_grams            = ?,
                overload_threshold            = ?,
                overload_relay                = ?,
                overload_action               = ?,
                overload_cooldown_ms          = ?,
                confirm_count                 = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            1 if filters.get("lowpass_filter_enabled")    else 0,
            filters.get("filter_cutoff_frequency",        8.0),
            filters.get("filter_activation_delta_min",    20000.0),
            1 if filters.get("moving_avg_enabled")        else 0,
            filters.get("moving_avg_window",              4),
            1 if filters.get("median_filter_enabled")     else 0,
            filters.get("median_filter_window",           3),
            1 if filters.get("autotare_enabled")          else 0,
            filters.get("autotare_trigger_delta_grams",   -5.0),
            1 if filters.get("adaptive_deadband_enabled") else 0,
            filters.get("adaptive_deadband_min",          1.0),
            filters.get("adaptive_deadband_max",          20.0),
            filters.get("adaptive_deadband_grow_rate",    0.5),
            filters.get("adaptive_deadband_shrink_rate",  1.5),
            filters.get("publish_step_grams",             5.0),
            filters.get("overload_threshold",             5000.0),
            filters.get("overload_relay",                 "relay2"),
            filters.get("overload_action",                0),
            filters.get("overload_cooldown_ms",           2000),
            filters.get("confirm_count",                  3),
            device_id
        ))
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        if affected == 0:
            return web.json_response({"success": False, "error": "Device not found"})
        return web.json_response({"success": True})
    except Exception as e:
        logging.error("filters save error: %s", e)
        return web.json_response({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Modbus Service Config handler
# ---------------------------------------------------------------------------

async def pipeline_modbus_config_handler(request):
    """POST /api/pipeline/modbus-config"""
    if not PIPELINE_AVAILABLE:
        return web.json_response({"success": False, "error": "ilx_pipeline not available"})

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "Invalid JSON body"})

    host       = body.get("host", "127.0.0.1")
    port       = int(body.get("port", 7000))
    modbus_cfg = body.get("config")

    if not modbus_cfg:
        return web.json_response({"success": False, "error": "Missing 'config' field"})

    # Reuse the existing pipeline client - same one used for load cell
    with pipeline_state["lock"]:
        client    = pipeline_state.get("client")
        connected = pipeline_state.get("connected", False)

    if not (connected and client):
        print("[MODBUS-CFG] Pipeline not connected - connecting to {}:{}".format(host, port))

        connected_event = threading.Event()

        def _run():
            try:
                c = PipelineClient("craneiq_loadcell_listener", host, port, 1000, 10)
                c.set_connection_timeout(5)

                def on_event(ev):
                    if ev.event_type == EventType.PIPELINE_CONNECTED:
                        print("[MODBUS-CFG] EVENT: CONNECTED")
                        with pipeline_state["lock"]:
                            pipeline_state["connected"] = True
                    elif ev.event_type == EventType.PIPELINE_OFFLINE:
                        print("[MODBUS-CFG] EVENT: OFFLINE")
                        with pipeline_state["lock"]:
                            pipeline_state["connected"] = False

                c.set_event_callback(on_event)
                print("[MODBUS-CFG] Starting client...")
                c.start()

                print("[MODBUS-CFG] Waiting for connection (5s)...")
                ok = c.wait_until_connected(5000)
                print("[MODBUS-CFG] wait_until_connected returned: {}".format(ok))

                with pipeline_state["lock"]:
                    pipeline_state["client"]    = c
                    pipeline_state["connected"] = ok

                connected_event.set()
            except Exception as ex:
                print("[MODBUS-CFG] Thread exception: {}".format(ex))
                connected_event.set()

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: connected_event.wait(7))

        with pipeline_state["lock"]:
            client    = pipeline_state.get("client")
            connected = pipeline_state.get("connected", False)

        if not (connected and client):
            return web.json_response({
                "success": False,
                "error": "Could not connect to pipeline at {}:{}".format(host, port)
            })

        print("[MODBUS-CFG] Connected successfully")

    # Publish config targeted to the modbus service
    try:
        from ilx_pipeline import Config
        cfg         = Config()
        cfg.name    = "modbus_config"
        cfg.value   = json.dumps(modbus_cfg)
        cfg.version = 1
        cfg.service = "modbus"

        ok = client.publish_config(cfg)
        if ok:
            asset_count = len(modbus_cfg.get("assets", []))
            print("[MODBUS-CFG] Config published - {} assets".format(asset_count))
            return web.json_response({
                "success": True,
                "message": "Configuration sent to modbus service ({} assets)".format(asset_count)
            })
        else:
            return web.json_response({
                "success": False,
                "error": "publish_config returned False - check pipeline connection"
            })
    except Exception as ex:
        print("[MODBUS-CFG] publish_config error: {}".format(ex))
        return web.json_response({"success": False, "error": str(ex)})


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------
def register_pipeline_routes(app):
    app.router.add_post('/api/pipeline/connect',          pipeline_connect_handler)
    app.router.add_post('/api/pipeline/disconnect',       pipeline_disconnect_handler)
    app.router.add_get ('/api/pipeline/status',           pipeline_status_handler)
    app.router.add_get ('/ws/pipeline/load_raw',          pipeline_loadraw_ws_handler)
    app.router.add_get ('/api/pipeline/loadcell-devices', pipeline_loadcell_devices_handler)
    app.router.add_get ('/api/pipeline/calibration',      pipeline_calibration_get_handler)
    app.router.add_post('/api/pipeline/calibration',      pipeline_calibration_post_handler)
    app.router.add_post('/api/pipeline/filters',          pipeline_filters_post_handler)

    app.router.add_post('/api/pipeline/modbus-config',    pipeline_modbus_config_handler)
    print("[PIPELINE] Routes registered OK")