# -*- coding: utf-8 -*-
# pipeline.py - Pipeline (Load Cell) module

import asyncio
import json
import logging
import sqlite3
import threading

from aiohttp import web

try:
    from ilx_pipeline import PipelineClient, EventType, DataType
    PIPELINE_AVAILABLE = True
    print("[PIPELINE] ilx_pipeline imported OK")
except ImportError:
    PIPELINE_AVAILABLE = False
    print("[PIPELINE] WARNING: ilx_pipeline not available!")

from database import DB_FILE

# ---------------------------------------------------------------------------
# Shared pipeline state  (single dict   only one copy in the process)
# ---------------------------------------------------------------------------
pipeline_state = {
    "client":     None,
    "connected":  False,
    "load_raw":   None,
    "ws_clients": set(),
    "lock":       threading.Lock(),
    "main_loop":  None,   # set when connect is called
}

_WS_CLOSE = 8
_WS_ERROR = 258


# ---------------------------------------------------------------------------
# Broadcast helper (runs on the main asyncio loop)
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

    # Capture the running event loop BEFORE starting the thread.
    # This is the only safe place to call get_event_loop()   inside an async function.
    main_loop = asyncio.get_event_loop()
    pipeline_state["main_loop"] = main_loop

    # connected_event lets us wait briefly for connection without blocking the loop
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

                            # Save into state so /api/pipeline/status works
                            with pipeline_state["lock"]:
                                pipeline_state[dp] = val
                                if dp == "load_raw":
                                    pipeline_state["load_raw"] = val

                            # Push to all WebSocket clients
                            msg = json.dumps({"datapoint": dp, "value": val})
                            loop = pipeline_state.get("main_loop")
                            if loop is not None:
                                asyncio.run_coroutine_threadsafe(
                                    _broadcast_pipeline_msg(msg), loop
                                )
                            else:
                                print("[PIPELINE] WARNING: main_loop is None, cannot broadcast!")

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
            connected_event.set()  # unblock wait below even on failure

    # Start thread   do NOT join() on the main loop thread, it blocks asyncio.
    # Instead wait on a threading.Event with a short timeout.
    thread = threading.Thread(target=_run_pipeline, daemon=True)
    thread.start()

    # Wait up to 6s for connection without blocking the event loop
    # (we use run_in_executor so asyncio stays responsive)
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
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    # Add to set FIRST so no live broadcasts are missed while we send the buffered value
    pipeline_state["ws_clients"].add(ws)
    print("[PIPELINE] WS client connected, total={}".format(len(pipeline_state["ws_clients"])))

    # Send buffered value immediately so client doesn't wait for next event
    with pipeline_state["lock"]:
        current_raw = pipeline_state["load_raw"]

    if current_raw is not None:
        try:
            await ws.send_str(json.dumps({"datapoint": "load_raw", "value": current_raw}))
            print("[PIPELINE] Sent buffered load_raw={} to new client".format(current_raw))
        except Exception as e:
            print("[PIPELINE] Could not send buffered value: {}".format(e))

    try:
        # aiohttp 2.0.7 compatible receive loop
        while True:
            msg = await ws.receive()
            if msg.tp in (_WS_CLOSE, _WS_ERROR):
                break
    except Exception as e:
        print("[PIPELINE] WS receive error: {}".format(e))
    finally:
        pipeline_state["ws_clients"].discard(ws)
        print("[PIPELINE] WS client disconnected, total={}".format(len(pipeline_state["ws_clients"])))

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
    print("[PIPELINE] Routes registered OK")