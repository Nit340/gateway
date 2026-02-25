# -*- coding: utf-8 -*-
# pipeline.py - Pipeline (Load Cell) module
# Handles ilx_pipeline connection, WebSocket streaming, and calibration API.
# Register routes by calling register_pipeline_routes(app) in main.py.

import asyncio
import json
import logging
import sqlite3
import threading

from aiohttp import web

try:
    from ilx_pipeline import PipelineClient, EventType, DataType
    PIPELINE_AVAILABLE = True
except ImportError:
    PIPELINE_AVAILABLE = False
    logging.warning("ilx_pipeline not available - pipeline features disabled")

from database import DB_FILE

# ---------------------------------------------------------------------------
# Shared pipeline state
# ---------------------------------------------------------------------------
pipeline_state = {
    "client":    None,
    "connected": False,
    "load_raw":  None,
    "ws_clients": set(),
    "lock":      threading.Lock(),
}


# ---------------------------------------------------------------------------
# HTTP handlers
# ---------------------------------------------------------------------------

async def pipeline_connect_handler(request):
    """POST /api/pipeline/connect
    Connect to the ilx_pipeline server and start streaming datapoints.
    Body (optional JSON): { "host": "127.0.0.1", "port": 7000 }
    """
    try:
        if not PIPELINE_AVAILABLE:
            return web.json_response(
                {"success": False, "error": "ilx_pipeline library not found - check server logs"}
            )

        with pipeline_state["lock"]:
            if pipeline_state["connected"] and pipeline_state["client"]:
                return web.json_response({"success": True, "message": "Already connected"})

        try:
            body = await request.json()
        except Exception:
            body = {}

        host = body.get("host", "127.0.0.1")
        port = body.get("port", 7000)

        def _run_pipeline():
            try:
                client = PipelineClient("craneiq_loadcell_listener", host, port, 1000, 10)
                client.set_connection_timeout(5)

                def on_event(event):
                    try:
                        if event.event_type == EventType.PIPELINE_CONNECTED:
                            with pipeline_state["lock"]:
                                pipeline_state["connected"] = True

                        elif event.event_type == EventType.PIPELINE_OFFLINE:
                            with pipeline_state["lock"]:
                                pipeline_state["connected"] = False

                        elif event.event_type == EventType.RECEIVE_DONE:
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

                                msg = json.dumps({"datapoint": dp, "value": val})
                                for ws in list(pipeline_state["ws_clients"]):
                                    try:
                                        asyncio.run_coroutine_threadsafe(
                                            ws.send_str(msg), ws._loop
                                        )
                                    except Exception:
                                        pass
                            except Exception as e:
                                logging.error("Error reading datapoint %s: %s", dp, e)

                    except Exception as e:
                        logging.error("Pipeline event error: %s", e)

                client.set_event_callback(on_event)
                client.start()
                ok = client.wait_until_connected(5000)
                with pipeline_state["lock"]:
                    pipeline_state["client"] = client
                    pipeline_state["connected"] = ok

            except Exception as e:
                logging.error("Pipeline thread error: %s", e)
                with pipeline_state["lock"]:
                    pipeline_state["connected"] = False

        thread = threading.Thread(target=_run_pipeline, daemon=True)
        thread.start()
        thread.join(timeout=7)

        with pipeline_state["lock"]:
            ok = pipeline_state["connected"]

        if ok:
            return web.json_response({"success": True, "message": "Connected to pipeline"})
        else:
            return web.json_response({
                "success": False,
                "error": "Could not connect to pipeline server at {}:{}".format(host, port)
            })

    except Exception as e:
        logging.error("pipeline_connect_handler fatal: %s", e)
        return web.json_response({"success": False, "error": str(e)})


async def pipeline_disconnect_handler(request):
    """POST /api/pipeline/disconnect - Disconnect from the pipeline server"""
    with pipeline_state["lock"]:
        client = pipeline_state.get("client")
        if client:
            try:
                client.stop()
            except Exception:
                pass
        pipeline_state["client"] = None
        pipeline_state["connected"] = False
        pipeline_state["load_raw"] = None
    return web.json_response({"success": True, "message": "Disconnected"})


async def pipeline_status_handler(request):
    """GET /api/pipeline/status - Return current connection status and latest load_raw"""
    with pipeline_state["lock"]:
        return web.json_response({
            "connected": pipeline_state["connected"],
            "load_raw":  pipeline_state["load_raw"],
        })


async def pipeline_loadraw_ws_handler(request):
    """WebSocket /ws/pipeline/load_raw - Stream live load_raw values to browser"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ws._loop = asyncio.get_event_loop()

    pipeline_state["ws_clients"].add(ws)
    try:
        async for msg in ws:
            pass  # send-only stream; ignore any incoming messages
    finally:
        pipeline_state["ws_clients"].discard(ws)
    return ws


async def pipeline_loadcell_devices_handler(request):
    """GET /api/pipeline/loadcell-devices - Return all enabled loadcell devices from DB"""
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
            # Cast booleans
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
    """GET /api/pipeline/calibration?device_id=<id> - Return calibration data for a device"""
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
    """POST /api/pipeline/calibration - Save tare_offset / known_weight / known_weight_raw"""
    try:
        body = await request.json()
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
    """POST /api/pipeline/filters - Save all filter/overload settings for a loadcell device.
    No pipeline connection required — these are user-configured values only.
    """
    try:
        body = await request.json()
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
            filters.get("filter_cutoff_frequency",       8.0),
            filters.get("filter_activation_delta_min",   20000.0),
            1 if filters.get("moving_avg_enabled")        else 0,
            filters.get("moving_avg_window",             4),
            1 if filters.get("median_filter_enabled")     else 0,
            filters.get("median_filter_window",          3),
            1 if filters.get("autotare_enabled")          else 0,
            filters.get("autotare_trigger_delta_grams",  -5.0),
            1 if filters.get("adaptive_deadband_enabled") else 0,
            filters.get("adaptive_deadband_min",         1.0),
            filters.get("adaptive_deadband_max",         20.0),
            filters.get("adaptive_deadband_grow_rate",   0.5),
            filters.get("adaptive_deadband_shrink_rate", 1.5),
            filters.get("publish_step_grams",            5.0),
            filters.get("overload_threshold",            5000.0),
            filters.get("overload_relay",                "relay2"),
            filters.get("overload_action",               0),
            filters.get("overload_cooldown_ms",          2000),
            filters.get("confirm_count",                 3),
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
    """Register all pipeline routes onto an aiohttp Application."""
    app.router.add_post('/api/pipeline/connect',          pipeline_connect_handler)
    app.router.add_post('/api/pipeline/disconnect',       pipeline_disconnect_handler)
    app.router.add_get ('/api/pipeline/status',           pipeline_status_handler)
    app.router.add_get ('/ws/pipeline/load_raw',          pipeline_loadraw_ws_handler)
    app.router.add_get ('/api/pipeline/loadcell-devices', pipeline_loadcell_devices_handler)
    app.router.add_get ('/api/pipeline/calibration',      pipeline_calibration_get_handler)
    app.router.add_post('/api/pipeline/calibration',      pipeline_calibration_post_handler)
    app.router.add_post('/api/pipeline/filters',          pipeline_filters_post_handler)