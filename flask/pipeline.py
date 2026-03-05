# -*- coding: utf-8 -*-
# pipeline.py
#
# ============================================================================
# DATA FLOW -- LOADCELL CONFIG
# ============================================================================
#
#  UI (craneiq.html)
#    |  User edits filters (Median, MovingAverage, Kalman, AdaptiveDeadband,
#    |  levels) and clicks "Save Filters & Levels"
#    |
#    v
#  craneiq.js  ->  POST /api/pipeline/filters
#    Body: {
#      device_id,
#      raw_filters:    [{type, parameters, enabled}, ...],   <- 5 raw filters
#      weight_filters: [{type, parameters, enabled}, ...],   <- 1 weight filter
#      levels:         [{name, ratio, enabled}, ...]         <- low/normal/high
#    }
#    |
#    v
#  pipeline_filters_post_handler()  [this file]
#    |
#    |  STEP 1 -- Persist to DB
#    |     loadcell_device.raw_filters    = JSON(raw_filters)
#    |     loadcell_device.weight_filters = JSON(weight_filters)
#    |     loadcell_device.levels         = JSON(levels)
#    |
#    |  STEP 2 -- Read full device row from DB
#    |     Hardware   : device_path, poll_ms, resolution_bits, effective_bits,
#    |                  signed, gain, vref, raw_min, raw_max
#    |     Capacity   : capacity_min, capacity_max, unit
#    |     Calibration: tare_offset, known_weight, known_weight_raw
#    |     Pipeline   : pipeline_server, pipeline_port, log_level
#    |
#    |  STEP 3 -- Build inno_load config JSON
#    |     {
#    |       version, timestamp, source,
#    |       logging : [{type:"console", parameters:{level}}],
#    |       ipc     : [{type:"pipeline", parameters:{
#    |                     server, port,
#    |                     service_name: "load_cell_service",
#    |                     datapoints: [{name, map:{weight,raw,unit,...}}]
#    |                  }}],
#    |       load_cells: [{
#    |         name,
#    |         device: {
#    |           type: "sysfs_hx711",
#    |           parameters: {
#    |             poll_ms, channels:[{path}],
#    |             resolution_bits, effective_bits, signed, gain, vref,
#    |             raw_min, raw_max
#    |           }
#    |         },
#    |         specifications: {capacity: {min:{value,unit}, max:{value,unit}}},
#    |         levels      : {type:"ratio", parameters:{ratios:[{name,ratio}]}},
#    |         tare        : {type:"manual", parameters:{offset_raw}},
#    |         calibration : {type:"single_point",
#    |                        parameters:{ref_weight:{value,unit}, ref_raw}},
#    |         filter      : {raw:[...enabled only...], weight:[...enabled only...]}
#    |       }]
#    |     }
#    |
#    |  STEP 4 -- Save to disk
#    |     loadcell_configs/loadcell_config_YYYYMMDD_HHMMSS.json
#    |     loadcell_configs/loadcell_config_latest.json
#    |
#    |  STEP 5 -- Send via pipeline
#    |     client.datapoint_update("load_cell_service",
#    |                             "loadcell_config", config_json)
#    |     If service not yet connected:
#    |       pipeline_state["loadcell_config_pending"] = config_json
#    |       -> sent automatically when SERVICE_ADDED fires
#    |
#    v
#  PipelineClient (ilx_pipeline)  ->  inno_load  (load_cell_service)
#    Receives loadcell_config -> reconfigures sysfs_hx711 device,
#    filter chain, levels, calibration at runtime
#
# ============================================================================
# FIELD MAP -- where each value in the sent JSON comes from
# ============================================================================
#
#  JSON path                            Source
#  -------------------------------------------------------------------------
#  version                              pipeline_state["loadcell_config_version"] + 1
#  timestamp / timestamp_str            generated at save time
#  logging[0].parameters.level          DB  loadcell_device.log_level
#  ipc[0].parameters.server             DB  loadcell_device.pipeline_server
#  ipc[0].parameters.port               DB  loadcell_device.pipeline_port
#  ipc[0].parameters.service_name       "load_cell_service"  (hardcoded)
#  ipc[0].parameters.datapoints[0].name DB  loadcell_device.name
#  load_cells[0].name                   DB  loadcell_device.name
#  .device.type                         "sysfs_hx711"  (hardcoded)
#  .device.parameters.poll_ms           DB  loadcell_device.poll_ms
#  .device.parameters.channels[0].path  DB  loadcell_device.device_path
#  .device.parameters.resolution_bits   DB  loadcell_device.resolution_bits
#  .device.parameters.effective_bits    DB  loadcell_device.effective_bits
#  .device.parameters.signed            DB  loadcell_device.signed
#  .device.parameters.gain              DB  loadcell_device.gain
#  .device.parameters.vref              DB  loadcell_device.vref
#  .device.parameters.raw_min           DB  loadcell_device.raw_min
#  .device.parameters.raw_max           DB  loadcell_device.raw_max
#  .specifications.capacity.min.value   DB  loadcell_device.capacity_min
#  .specifications.capacity.max.value   DB  loadcell_device.capacity_max
#  .specifications.capacity.*.unit      DB  loadcell_device.unit
#  .levels.parameters.ratios            POST body  levels[]  (enabled only)
#  .tare.parameters.offset_raw          DB  loadcell_device.tare_offset
#  .calibration.parameters.ref_weight   DB  loadcell_device.known_weight + unit
#  .calibration.parameters.ref_raw      DB  loadcell_device.known_weight_raw
#  .filter.raw[]                        POST body  raw_filters[]    (enabled only)
#  .filter.weight[]                      POST body  weight_filters[] (enabled only)
#
# ============================================================================
# DATA FLOW -- MODBUS CONFIG
# ============================================================================
#
#  UI  ->  POST /api/pipeline/modbus-config/save
#    |
#    v
#  pipeline_save_modbus_config()
#    |  1. Reads modbus_datapoints JOIN modbus_device (enabled only)
#    |  2. Builds {connections:[...], assets:[...], version, timestamp}
#    |  3. Saves to modbus_configs/
#    |  4. client.datapoint_update(<modbus_service>, "modbus_config", json)
#    |     Pending if not connected -> sent on SERVICE_ADDED
#    v
#  PipelineClient  ->  modbus service
#
# ============================================================================

import asyncio
import json
import logging
import sqlite3
import threading
import time
import os
from datetime import datetime

from aiohttp import web
try:
    from aiohttp import WSMsgType as MsgType
except ImportError:
    # aiohttp 2.x
    from aiohttp.web import MsgType

try:
    from ilx_pipeline import PipelineClient, EventType, DataType, Config
    PIPELINE_AVAILABLE = True
    print("[PIPELINE] ilx_pipeline imported OK")
except ImportError:
    PIPELINE_AVAILABLE = False
    print("[PIPELINE] WARNING: ilx_pipeline not available!")

from database import (
    DB_FILE,
    get_pipeline_service_name,
    get_next_pipeline_version,
    record_pipeline_send_success,
    record_pipeline_send_failure,
    get_enabled_pipeline_targets,
)
from auth import ws_auth

# ============================================================================
# SHARED STATE
# ============================================================================

pipeline_state = {
    "client":                      None,
    "connected":                    False,
    "load_raw":                     None,
    "modbus_config":                None,
    "loadcell_config":              None,
    "iot_gateway_config":           None,
    "core_config":                  None,
    "ws_clients":                   set(),
    "lock":                         threading.RLock(),
    "main_loop":                    None,
    "connected_services":           set(),
    "background_thread":            None,
    "should_run":                   True,
    # version counters
    "config_version":               1,
    "loadcell_config_version":      1,
    "iot_gateway_config_version":   1,
    "last_config_time":             0,
    # connection tracking
    "connection_attempts":          0,
    "last_connection_attempt":      0,
    "subscribed_datapoints":        set(),
    # pending configs -- sent automatically when the service appears
    "modbus_config_pending":        None,
    "loadcell_config_pending":      None,
    "iot_gateway_config_pending":   None,
    "core_config_pending":          None,
}

# ============================================================================
# INTERNAL HELPERS
# ============================================================================

async def _broadcast_pipeline_msg(msg):
    """Send a message string to all connected WebSocket clients."""
    dead = set()
    clients = list(pipeline_state["ws_clients"])
    if clients:
        print("[PIPELINE] Broadcasting to {} WS clients".format(len(clients)))
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


def _find_modbus_service():
    """Return the configured modbus service name if it is currently connected, else None."""
    configured = get_pipeline_service_name("modbus")
    if not configured:
        return None
    with pipeline_state["lock"]:
        services = pipeline_state["connected_services"]
    return configured if configured in services else None


def _find_loadcell_service():
    """Return the configured loadcell service name if it is currently connected, else None."""
    configured = get_pipeline_service_name("loadcell")
    if not configured:
        return None
    with pipeline_state["lock"]:
        services = pipeline_state["connected_services"]
    return configured if configured in services else None


def _find_iot_gateway_service():
    """Return the configured iot_gateway service name if it is currently connected, else None."""
    configured = get_pipeline_service_name("iot_gateway")
    if not configured:
        return None
    with pipeline_state["lock"]:
        services = pipeline_state["connected_services"]
    return configured if configured in services else None


def _find_core_service():
    """Return the configured core service name if it is currently connected, else None."""
    configured = get_pipeline_service_name("core")
    if not configured:
        return None
    with pipeline_state["lock"]:
        services = pipeline_state["connected_services"]
    return configured if configured in services else None

# ============================================================================
# BACKGROUND PIPELINE THREAD
# ============================================================================

def _run_pipeline_thread(host="127.0.0.1", port=7000):
    """Long-running thread that owns the PipelineClient."""
    print("[PIPELINE] Starting thread ({}:{})".format(host, port))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        client = PipelineClient("web_ui", host, port, 1000, 10)
        client.set_connection_timeout(5)

        with pipeline_state["lock"]:
            pipeline_state["client"] = client
            pipeline_state["connection_attempts"] += 1
            pipeline_state["last_connection_attempt"] = time.time()

        def on_event(event):
            try:
                etype = event.event_type

                # -- Connected --------------------------------------------
                if etype == EventType.PIPELINE_CONNECTED:
                    print("[PIPELINE] Connected")
                    with pipeline_state["lock"]:
                        pipeline_state["connected"] = True
                        pipeline_state["connection_attempts"] = 0
                    try:
                        if hasattr(client, 'subscribe'):
                            # Only subscribe to loadcell mapped datapoints --
                            # modbus/iot_gateway/core are send-only, no subscriptions needed.
                            # Re-subscribe from the last known loadcell config if available.
                            with pipeline_state["lock"]:
                                last_lc_config = pipeline_state.get("loadcell_config")
                            subscribed = set()
                            if last_lc_config:
                                try:
                                    cfg = json.loads(last_lc_config)
                                    for ipc_entry in cfg.get("ipc", []):
                                        for dp_entry in (ipc_entry.get("parameters") or {}).get("datapoints", []):
                                            for mapped_dp in (dp_entry.get("map") or {}).values():
                                                client.subscribe(mapped_dp)
                                                subscribed.add(mapped_dp)
                                                print("[PIPELINE] Subscribed to '{}'".format(mapped_dp))
                                except Exception as parse_e:
                                    print("[PIPELINE] Re-subscribe parse error: {}".format(parse_e))
                            with pipeline_state["lock"]:
                                pipeline_state["subscribed_datapoints"] = subscribed
                        else:
                            client.refresh()
                    except Exception as e:
                        print("[PIPELINE] Subscribe error: {}".format(e))
                        try:
                            client.refresh()
                        except Exception:
                            pass

                # -- Offline ----------------------------------------------
                elif etype == EventType.PIPELINE_OFFLINE:
                    print("[PIPELINE] Offline")
                    with pipeline_state["lock"]:
                        pipeline_state["connected"] = False

                # -- Service appeared -- dispatch any pending configs -------
                elif etype == EventType.SERVICE_ADDED:
                    svc = event.service_name
                    print("[PIPELINE] SERVICE_ADDED: '{}'".format(svc))
                    with pipeline_state["lock"]:
                        pipeline_state["connected_services"].add(svc)

                    # Use DB-configured service names (no pattern matching)
                    modbus_svc   = get_pipeline_service_name("modbus")
                    loadcell_svc = get_pipeline_service_name("loadcell")
                    iot_svc      = get_pipeline_service_name("iot_gateway")

                    if svc == modbus_svc:
                        print("[PIPELINE] Modbus service connected: '{}'".format(svc))
                        with pipeline_state["lock"]:
                            pending = pipeline_state.get("modbus_config_pending")
                        if pending:
                            try:
                                rid = client.datapoint_update(svc, "modbus_config", pending)
                                if rid > 0:
                                    print("[PIPELINE] Sent pending modbus config (rid={})".format(rid))
                                    with pipeline_state["lock"]:
                                        pipeline_state["modbus_config_pending"] = None
                                else:
                                    print("[PIPELINE] Pending modbus send failed (rid=0)")
                            except Exception as e:
                                print("[PIPELINE] Pending modbus send error: {}".format(e))

                    if svc == loadcell_svc:
                        print("[PIPELINE] Loadcell service connected: '{}'".format(svc))
                        with pipeline_state["lock"]:
                            pending = pipeline_state.get("loadcell_config_pending")
                            last_config = pipeline_state.get("loadcell_config")
                        if pending:
                            try:
                                rid = client.datapoint_update(svc, "loadcell_config", pending)
                                if rid > 0:
                                    print("[PIPELINE] Sent pending loadcell config (rid={})".format(rid))
                                    with pipeline_state["lock"]:
                                        pipeline_state["loadcell_config_pending"] = None
                                        pipeline_state["loadcell_config"] = pending
                                    last_config = pending
                                    # Request live data back for each device
                                    try:
                                        cfg_parsed = json.loads(pending)
                                        for lc_entry in cfg_parsed.get("load_cells", []):
                                            dev_dp = lc_entry.get("name")
                                            if dev_dp:
                                                client.datapoint_update(svc, dev_dp, '{}')
                                                print("[PIPELINE] Requested live data for: '{}'".format(dev_dp))
                                    except Exception as pull_e:
                                        print("[PIPELINE] Live data request error: {}".format(pull_e))
                                else:
                                    print("[PIPELINE] Pending loadcell send failed (rid=0)")
                            except Exception as e:
                                print("[PIPELINE] Pending loadcell send error: {}".format(e))

                        # Re-subscribe to all mapped receive datapoints from last known config
                        config_to_use = last_config
                        if config_to_use and hasattr(client, 'subscribe'):
                            try:
                                cfg = json.loads(config_to_use)
                                for ipc_entry in cfg.get("ipc", []):
                                    for dp_entry in (ipc_entry.get("parameters") or {}).get("datapoints", []):
                                        for mapped_dp in (dp_entry.get("map") or {}).values():
                                            try:
                                                client.subscribe(mapped_dp)
                                                print("[PIPELINE] Re-subscribed to receive: '{}'".format(mapped_dp))
                                            except Exception as sub_e:
                                                print("[PIPELINE] Re-subscribe error '{}': {}".format(mapped_dp, sub_e))
                            except Exception as parse_e:
                                print("[PIPELINE] Could not parse loadcell config for re-subscribe: {}".format(parse_e))

                    if svc == iot_svc:
                        print("[PIPELINE] IoT gateway service connected: '{}'".format(svc))
                        with pipeline_state["lock"]:
                            pending = pipeline_state.get("iot_gateway_config_pending")
                        if pending:
                            try:
                                rid = client.datapoint_update(svc, "iot_gateway_config", pending)
                                if rid > 0:
                                    print("[PIPELINE] Sent pending iot_gateway config (rid={})".format(rid))
                                    with pipeline_state["lock"]:
                                        pipeline_state["iot_gateway_config_pending"] = None
                                        pipeline_state["iot_gateway_config"] = pending
                                else:
                                    print("[PIPELINE] Pending iot_gateway send failed (rid=0)")
                            except Exception as e:
                                print("[PIPELINE] Pending iot_gateway send error: {}".format(e))

                    core_svc = get_pipeline_service_name("core")
                    if svc == core_svc:
                        print("[PIPELINE] Core service connected: '{}'".format(svc))
                        with pipeline_state["lock"]:
                            pending = pipeline_state.get("core_config_pending")
                        if pending:
                            try:
                                rid = client.datapoint_update(svc, "core_config", pending)
                                if rid > 0:
                                    print("[PIPELINE] Sent pending core config (rid={})".format(rid))
                                    with pipeline_state["lock"]:
                                        pipeline_state["core_config_pending"] = None
                                        pipeline_state["core_config"] = pending
                                else:
                                    print("[PIPELINE] Pending core config send failed (rid=0)")
                            except Exception as e:
                                print("[PIPELINE] Pending core config send error: {}".format(e))

                # -- Service removed --------------------------------------
                elif etype == EventType.SERVICE_REMOVED:
                    svc = event.service_name
                    print("[PIPELINE] SERVICE_REMOVED: '{}'".format(svc))
                    with pipeline_state["lock"]:
                        pipeline_state["connected_services"].discard(svc)

                # -- Datapoint received -----------------------------------
                elif etype == EventType.RECEIVE_DONE:
                    dp = event.datapoint_name
                    print("[PIPELINE] RECEIVE_DONE: '{}' from '{}'".format(dp, event.service_name))
                    try:
                        dtype = client.get_datapoint_type(dp)
                        if dtype == DataType.STRING:
                            val = client.get_datapoint_string(dp)
                        elif dtype == DataType.INT:
                            val = client.get_datapoint_integer(dp)
                        elif dtype == DataType.LONG:
                            val = client.get_datapoint_long(dp)
                        elif dtype == DataType.FLOAT:
                            val = client.get_datapoint_float(dp)
                        elif dtype == DataType.DOUBLE:
                            val = client.get_datapoint_double(dp)
                        elif dtype == DataType.BOOL:
                            val = client.get_datapoint_boolean(dp)
                        else:
                            val = client.get_datapoint_string(dp)

                        with pipeline_state["lock"]:
                            pipeline_state[dp] = val

                        # -- Network-status datapoints ----------------------
                        # The pipeline publishes JSON strings under the
                        # "network_status" service with datapoint names like
                        # "lan", "wlan", "lte", and "network_status" (int).
                        # We unpack them into flat net.* keys so the UI can
                        # display live values without a page refresh.
                        # -- Network-status datapoints ----------------------
                        # The pipeline publishes JSON strings under the
                        # "network_status" service with datapoint names like
                        # "lan", "wlan", "lte", and "network_status" (int).
                        # We unpack them into flat net.* keys so the UI can
                        # display live values without a page refresh.
                        _NET_SERVICES = {"network_status"}
                        if event.service_name in _NET_SERVICES or dp in (
                            "lan", "wlan", "lte", "network_status"
                        ):
                            try:
                                from general_config import update_network_status_field
                                
                                # Handle integer network_status specially
                                if dp == "network_status":
                                    update_network_status_field("network_status", val)
                                    # Skip further processing for this case
                                    main_loop = pipeline_state.get("main_loop")
                                    if main_loop and main_loop.is_running():
                                        try:
                                            asyncio.run_coroutine_threadsafe(
                                                _broadcast_pipeline_msg(
                                                    json.dumps({"datapoint": dp, "value": val})),
                                                main_loop)
                                        except Exception as e:
                                            print("[PIPELINE] Broadcast error: {}".format(e))
                                    # Don't use continue here - we need to let the main broadcast happen
                                else:
                                    # For other datapoints (lan, wlan, lte), parse JSON
                                    if isinstance(val, str):
                                        try:
                                            parsed = json.loads(val)
                                            print("[PIPELINE] Parsed {}: {}".format(dp, parsed))  # Debug log
                                        except json.JSONDecodeError as e:
                                            print("[PIPELINE] JSON parse error for {}: {}".format(dp, e))
                                            update_network_status_field(dp, val)
                                            main_loop = pipeline_state.get("main_loop")
                                            if main_loop and main_loop.is_running():
                                                try:
                                                    asyncio.run_coroutine_threadsafe(
                                                        _broadcast_pipeline_msg(
                                                            json.dumps({"datapoint": dp, "value": val})),
                                                        main_loop)
                                                except Exception as e:
                                                    print("[PIPELINE] Broadcast error: {}".format(e))
                                            # Skip further processing for this case
                                            # Don't use continue here
                                    else:
                                        parsed = val
                                    
                                    # Skip if parsed is not a dict
                                    if not isinstance(parsed, dict):
                                        update_network_status_field(dp, parsed)
                                        main_loop = pipeline_state.get("main_loop")
                                        if main_loop and main_loop.is_running():
                                            try:
                                                asyncio.run_coroutine_threadsafe(
                                                    _broadcast_pipeline_msg(
                                                        json.dumps({"datapoint": dp, "value": parsed})),
                                                    main_loop)
                                            except Exception as e:
                                                print("[PIPELINE] Broadcast error: {}".format(e))
                                        # Skip further processing for this case
                                        # Don't use continue here
                                    else:
                                        # For "lan" datapoint with structure like:
                                        # {"lan":{"dynamic":{"net.lan.eth1.ip":"","net.lan.eth1.state":0}}}
                                        # We need to extract the nested fields
                                        for section, section_data in parsed.items():
                                            if isinstance(section_data, dict):
                                                for subsection, subsection_data in section_data.items():
                                                    if isinstance(subsection_data, dict):
                                                        # This is where the actual fields are (like net.lan.eth1.ip)
                                                        for field_name, field_value in subsection_data.items():
                                                            update_network_status_field(field_name, field_value)
                                                            print("[PIPELINE] Updated {} = {}".format(field_name, field_value))  # Debug log
                                                    else:
                                                        # Direct value under subsection
                                                        update_network_status_field(subsection, subsection_data)
                                            else:
                                                # Direct value under section
                                                update_network_status_field(section, section_data)
                                                    
                            except Exception as _ne:
                                print("[PIPELINE] network_status parse error: {} for dp={}, val={} (type: {})".format(
                                    _ne, dp, val, type(val)))
                                import traceback
                                traceback.print_exc()
                        # --------------------------------------------------
                        # --------------------------------------------------

                        main_loop = pipeline_state.get("main_loop")
                        if main_loop and main_loop.is_running():
                            try:
                                asyncio.run_coroutine_threadsafe(
                                    _broadcast_pipeline_msg(
                                        json.dumps({"datapoint": dp, "value": val})),
                                    main_loop)
                            except Exception as e:
                                print("[PIPELINE] Broadcast error: {}".format(e))

                    except Exception as e:
                        print("[PIPELINE] Error reading dp '{}': {}".format(dp, e))
                        import traceback
                        traceback.print_exc()

            except Exception as e:
                print("[PIPELINE] Event handler error: {}".format(e))
                import traceback
                traceback.print_exc()

        client.set_event_callback(on_event)
        client.start()

        connected = client.wait_until_connected(5000)
        with pipeline_state["lock"]:
            pipeline_state["connected"] = connected
        print("[PIPELINE] Initial connection: {}".format("OK" if connected else "waiting"))

        # Keep alive; retry every 10 s if disconnected
        while pipeline_state.get("should_run", True):
            time.sleep(1)
            with pipeline_state["lock"]:
                still_connected = pipeline_state["connected"]
                client_ref      = pipeline_state["client"]

            if not still_connected and client_ref:
                now = time.time()
                with pipeline_state["lock"]:
                    last_attempt = pipeline_state["last_connection_attempt"]
                    attempts     = pipeline_state["connection_attempts"]
                if now - last_attempt > 10:
                    print("[PIPELINE] Reconnecting...")
                    with pipeline_state["lock"]:
                        pipeline_state["connection_attempts"]     = attempts + 1
                        pipeline_state["last_connection_attempt"] = now
                    try:
                        client_ref.refresh()
                    except Exception as e:
                        print("[PIPELINE] Refresh failed: {}".format(e))

    except Exception as e:
        print("[PIPELINE] Thread crashed: {}".format(e))
        import traceback
        traceback.print_exc()
    finally:
        print("[PIPELINE] Thread exiting")
        try:
            with pipeline_state["lock"]:
                if pipeline_state.get("client"):
                    pipeline_state["client"].stop()
        except Exception:
            pass


def start_pipeline_background(app=None):
    """Start (or restart) the pipeline background thread."""
    if not PIPELINE_AVAILABLE:
        print("[PIPELINE] Cannot start -- ilx_pipeline not available")
        return

    with pipeline_state["lock"]:
        if pipeline_state["background_thread"] and pipeline_state["background_thread"].is_alive():
            print("[PIPELINE] Background thread already running")
            return
        pipeline_state["should_run"]                 = True
        pipeline_state["modbus_config_pending"]      = None
        pipeline_state["loadcell_config_pending"]    = None
        pipeline_state["iot_gateway_config_pending"] = None

    try:
        main_loop = asyncio.get_event_loop()
        with pipeline_state["lock"]:
            pipeline_state["main_loop"] = main_loop
    except Exception as e:
        print("[PIPELINE] Could not capture main loop: {}".format(e))

    thread = threading.Thread(
        target=_run_pipeline_thread,
        args=("127.0.0.1", 7000),
        daemon=True,
        name="PipelineThread"
    )
    thread.start()

    with pipeline_state["lock"]:
        pipeline_state["background_thread"] = thread

    print("[PIPELINE] Background thread started")
    return thread

# ============================================================================
# CONNECTION HANDLERS
# ============================================================================

async def pipeline_connect_handler(request):
    """POST /api/pipeline/connect"""
    if not PIPELINE_AVAILABLE:
        return web.json_response({"success": False, "error": "ilx_pipeline not available"})

    try:
        body = await request.json()
    except Exception:
        body = {}

    host = body.get("host", "127.0.0.1")
    port = body.get("port", 7000)

    with pipeline_state["lock"]:
        pipeline_state["should_run"] = False
    await asyncio.sleep(1)
    with pipeline_state["lock"]:
        pipeline_state["should_run"] = True

    try:
        main_loop = asyncio.get_event_loop()
        with pipeline_state["lock"]:
            pipeline_state["main_loop"] = main_loop
    except Exception:
        pass

    thread = threading.Thread(target=_run_pipeline_thread, args=(host, port), daemon=True)
    thread.start()
    with pipeline_state["lock"]:
        pipeline_state["background_thread"] = thread

    await asyncio.sleep(2)

    with pipeline_state["lock"]:
        connected        = pipeline_state["connected"]
        services         = list(pipeline_state["connected_services"])
        modbus_service   = _find_modbus_service()
        loadcell_service = _find_loadcell_service()

    return web.json_response({
        "success":          connected,
        "message":          "Connected" if connected else "Connecting in background",
        "services":         services,
        "modbus_service":   modbus_service,
        "loadcell_service": loadcell_service,
    })


async def pipeline_disconnect_handler(request):
    """POST /api/pipeline/disconnect"""
    with pipeline_state["lock"]:
        pipeline_state["should_run"] = False
        client = pipeline_state.get("client")
        if client:
            try:
                client.stop()
            except Exception:
                pass
        pipeline_state["client"]                     = None
        pipeline_state["connected"]                  = False
        pipeline_state["load_raw"]                   = None
        pipeline_state["modbus_config"]              = None
        pipeline_state["loadcell_config"]            = None
        pipeline_state["iot_gateway_config"]         = None
        pipeline_state["connected_services"].clear()
        pipeline_state["subscribed_datapoints"].clear()
        pipeline_state["modbus_config_pending"]      = None
        pipeline_state["loadcell_config_pending"]    = None
        pipeline_state["iot_gateway_config_pending"] = None

    print("[PIPELINE] Disconnected")
    return web.json_response({"success": True, "message": "Disconnected"})

# ============================================================================
# STATUS / INFO HANDLERS
# ============================================================================

async def pipeline_status_handler(request):
    """GET /api/pipeline/status"""
    with pipeline_state["lock"]:
        def _preview_modbus(cfg):
            if not cfg:
                return None
            try:
                p = json.loads(cfg)
                return {"version": p.get("version"),
                        "connections": len(p.get("connections", [])),
                        "assets": len(p.get("assets", [])),
                        "timestamp": p.get("timestamp_str")}
            except Exception:
                return {"note": "not valid JSON"}

        def _preview_loadcell(cfg):
            if not cfg:
                return None
            try:
                p = json.loads(cfg)
                return {"version": p.get("version"),
                        "load_cells": len(p.get("load_cells", [])),
                        "timestamp": p.get("timestamp_str")}
            except Exception:
                return {"note": "not valid JSON"}

        return web.json_response({
            "connected":               pipeline_state["connected"],
            "load_raw":                pipeline_state["load_raw"],
            "services":                list(pipeline_state["connected_services"]),
            "modbus_service":          _find_modbus_service(),
            "loadcell_service":        _find_loadcell_service(),
            "modbus_config_preview":   _preview_modbus(pipeline_state["modbus_config"]),
            "loadcell_config_preview": _preview_loadcell(pipeline_state["loadcell_config"]),
            "modbus_config_length":    len(pipeline_state["modbus_config"])   if pipeline_state["modbus_config"]   else 0,
            "loadcell_config_length":  len(pipeline_state["loadcell_config"]) if pipeline_state["loadcell_config"] else 0,
            "config_version":          pipeline_state["config_version"],
            "loadcell_config_version": pipeline_state["loadcell_config_version"],
            "last_config_time":        pipeline_state["last_config_time"],
            "connection_attempts":     pipeline_state["connection_attempts"],
            "subscribed":              list(pipeline_state["subscribed_datapoints"]),
            "has_pending_modbus":      pipeline_state["modbus_config_pending"]   is not None,
            "has_pending_loadcell":    pipeline_state["loadcell_config_pending"] is not None,
        })


async def pipeline_services_handler(request):
    """GET /api/pipeline/services"""
    with pipeline_state["lock"]:
        return web.json_response({
            "services":         list(pipeline_state["connected_services"]),
            "count":            len(pipeline_state["connected_services"]),
            "modbus_service":   _find_modbus_service(),
            "loadcell_service": _find_loadcell_service(),
        })


async def pipeline_modbus_config_view_handler(request):
    """GET /api/pipeline/config -- view stored modbus_config"""
    with pipeline_state["lock"]:
        config = pipeline_state.get("modbus_config")
    if not config:
        return web.json_response({"success": False, "message": "No modbus config stored"})
    try:
        return web.json_response({"success": True, "config": json.loads(config), "raw_length": len(config)})
    except Exception as e:
        return web.json_response({"success": True, "config": config,
                                   "raw_length": len(config), "note": "not valid JSON", "error": str(e)})


async def pipeline_loadcell_config_view_handler(request):
    """GET /api/pipeline/loadcell-config -- view stored loadcell_config"""
    with pipeline_state["lock"]:
        config = pipeline_state.get("loadcell_config")
    if not config:
        return web.json_response({"success": False, "message": "No loadcell config stored"})
    try:
        return web.json_response({"success": True, "config": json.loads(config), "raw_length": len(config)})
    except Exception as e:
        return web.json_response({"success": True, "config": config,
                                   "raw_length": len(config), "note": "not valid JSON", "error": str(e)})


async def pipeline_debug_handler(request):
    """GET /api/pipeline/debug -- dump pipeline_state"""
    with pipeline_state["lock"]:
        out = {}
        for k, v in pipeline_state.items():
            if k in ("client", "ws_clients", "lock", "main_loop", "background_thread"):
                continue
            if k in ("connected_services", "subscribed_datapoints"):
                out[k] = list(v)
            elif k in ("modbus_config", "loadcell_config") and v:
                out[k + "_length"] = len(v)
                try:
                    p = json.loads(v)
                    out[k + "_preview"] = {"keys": list(p.keys()), "version": p.get("version")}
                except Exception:
                    out[k + "_preview"] = "not JSON"
            else:
                out[k] = v
        return web.json_response(out)

# ============================================================================
# WEBSOCKET -- live datapoint stream
# ============================================================================

async def pipeline_loadraw_ws_handler(request):
    """WS /ws/pipeline/load_raw -- streams load_raw, modbus_config, loadcell_config"""
    user = ws_auth(request)
    if user is None:
        return web.Response(status=401, text="Unauthorized")

    ws = web.WebSocketResponse()
    await ws.prepare(request)
    pipeline_state["ws_clients"].add(ws)
    print("[PIPELINE] WS client connected (total={})".format(len(pipeline_state["ws_clients"])))

    with pipeline_state["lock"]:
        raw   = pipeline_state["load_raw"]
        mcfg  = pipeline_state["modbus_config"]
        lccfg = pipeline_state["loadcell_config"]

    async def _send(payload):
        try:
            await ws.send_str(json.dumps(payload))
        except Exception:
            pass

    if raw is not None:
        await _send({"datapoint": "load_raw", "value": raw})

    if mcfg is not None:
        try:
            p = json.loads(mcfg)
            await _send({"datapoint": "modbus_config",
                          "value": {"version": p.get("version"),
                                    "timestamp": p.get("timestamp_str"),
                                    "connections": len(p.get("connections", [])),
                                    "assets": len(p.get("assets", []))},
                          "full": p})
        except Exception:
            await _send({"datapoint": "modbus_config", "value": mcfg})

    if lccfg is not None:
        try:
            p = json.loads(lccfg)
            await _send({"datapoint": "loadcell_config",
                          "value": {"version": p.get("version"),
                                    "timestamp": p.get("timestamp_str"),
                                    "load_cells": len(p.get("load_cells", []))},
                          "full": p})
        except Exception:
            await _send({"datapoint": "loadcell_config", "value": lccfg})

    try:
        while True:
            msg = await ws.receive()
            if msg.type == MsgType.close:
                break
    except Exception as e:
        print("[PIPELINE] WS error: {}".format(e))
    finally:
        pipeline_state["ws_clients"].discard(ws)
        print("[PIPELINE] WS client disconnected")

    return ws

# ============================================================================
# LOADCELL -- DEVICE LIST
# ============================================================================

async def pipeline_loadcell_devices_handler(request):
    """GET /api/pipeline/loadcell-devices"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, service_id, device_path,
                   poll_ms, resolution_bits, effective_bits, signed, gain, vref,
                   raw_min, raw_max, capacity_min, capacity_max, unit,
                   load_name, capacity_name,
                   pipeline_server, pipeline_port, log_level,
                   tare_offset, known_weight, known_weight_raw,
                   raw_filters, weight_filters, levels, enabled
            FROM loadcell_device WHERE enabled = 1
        ''')
        rows = cursor.fetchall()
        conn.close()

        devices = []
        for r in rows:
            d = dict(r)
            for col in ('raw_filters', 'weight_filters', 'levels'):
                try:
                    d[col] = json.loads(d[col]) if d.get(col) else []
                except Exception:
                    d[col] = []
            devices.append(d)

        return web.json_response({"devices": devices})
    except Exception as e:
        logging.error("loadcell_devices error: %s", e)
        return web.json_response({"devices": [], "error": str(e)})

# ============================================================================
# LOADCELL -- CALIBRATION
# ============================================================================

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
            (device_id,))
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
            SET tare_offset      = ?,
                known_weight     = ?,
                known_weight_raw = ?,
                updated_at       = CURRENT_TIMESTAMP
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

# ============================================================================
# LOADCELL -- FILTERS & LEVELS  ->  BUILD + SEND CONFIG
# ============================================================================

async def pipeline_filters_post_handler(request):
    """POST /api/pipeline/filters

    Saves filter/level arrays to DB, builds the complete inno_load config JSON,
    saves it to disk, then sends it to load_cell_service via the pipeline client.
    See the data-flow diagram at the top of this file for full field mapping.
    """
    print("\n" + "="*70)
    print("[LC-CFG] Save Filters & Levels  ->  Build  ->  Send")
    print("="*70)

    try:
        body = await request.json()
        device_id = body.get("device_id")
        if not device_id:
            return web.json_response({"success": False, "error": "device_id required"})

        raw_filters    = body.get("raw_filters", [])
        weight_filters = body.get("weight_filters", [])
        levels         = body.get("levels", [])

        # -- STEP 1: Persist to DB -----------------------------------------
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE loadcell_device
            SET raw_filters    = ?,
                weight_filters = ?,
                levels         = ?,
                updated_at     = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (json.dumps(raw_filters), json.dumps(weight_filters), json.dumps(levels), device_id))
        conn.commit()

        if cursor.rowcount == 0:
            conn.close()
            return web.json_response({"success": False, "error": "Device not found"})

        # -- STEP 2: Read full device row ----------------------------------
        cursor.execute('''
            SELECT id, name, device_path,
                   poll_ms, resolution_bits, effective_bits, signed, gain, vref,
                   raw_min, raw_max, capacity_min, capacity_max, unit,
                   pipeline_server, pipeline_port, log_level,
                   tare_offset, known_weight, known_weight_raw
            FROM loadcell_device WHERE id = ?
        ''', (device_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return web.json_response({"success": False, "error": "Device not found after update"})

        r = dict(row)
        print("[LC-CFG] Device: {} ({})".format(r['name'], r['id']))

        # -- STEP 3: Build inno_load config JSON ---------------------------
        def _active(arr):
            """Return only enabled filter/level entries, stripped of the 'enabled' key."""
            return [{"type": f["type"], "parameters": f["parameters"]}
                    for f in arr if f.get("enabled", True)]

        active_raw    = _active(raw_filters)
        active_weight = _active(weight_filters)
        active_levels = [{"name": lv["name"], "ratio": lv["ratio"]}
                         for lv in levels if lv.get("enabled", True)]

        # Get next version from DB (only written back on success)
        new_version = get_next_pipeline_version("loadcell")

        config = {
            "version":       new_version,
            "timestamp":     time.time(),
            "timestamp_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source":        "web_ui",
            # -- logging --------------------------------------------------
            "logging": [{
                "type":       "console",
                "parameters": {"level": r.get("log_level") or "info"}
            }],
            # -- ipc (pipeline connection info) ----------------------------
            "ipc": [{
                "type":    "pipeline",
                "enabled": True,
                "parameters": {
                    "server":       r.get("pipeline_server") or "127.0.0.1",
                    "port":         r.get("pipeline_port") or 7000,
                    "service_name": get_pipeline_service_name("loadcell") or "load_cell_service",
                    "datapoints": [{
                        "name": r["name"],
                        "map": {
                            "weight":        "{}.weight_kg".format(r["name"]),
                            "raw":           "{}.raw".format(r["name"]),
                            "unit":          "{}.unit".format(r["name"]),
                            "known_weight":  "{}.known_weight_kg".format(r["name"]),
                            "known_raw":     "{}.known_raw".format(r["name"]),
                            "is_tared":      "{}.tared".format(r["name"]),
                            "is_calibrated": "{}.calibrated".format(r["name"]),
                            "capacity":      "{}.capacity".format(r["name"]),
                        }
                    }]
                }
            }],
            # -- load_cells ------------------------------------------------
            "load_cells": [{
                "name": r["name"],
                # Hardware device (from DB hardware columns)
                "device": {
                    "type": "sysfs_hx711",
                    "parameters": {
                        "poll_ms":         r.get("poll_ms") or 10,
                        "channels":        [{"path": r.get("device_path") or ""}],
                        "resolution_bits": r.get("resolution_bits") or 24,
                        "effective_bits":  r.get("effective_bits") or 14,
                        "signed":          bool(r.get("signed")),
                        "gain":            r["gain"]    if r["gain"]    is not None else 1,
                        "vref":            r["vref"]    if r["vref"]    is not None else 5,
                        "raw_min":         r["raw_min"] if r["raw_min"] is not None else 0,
                        "raw_max":         r["raw_max"] if r["raw_max"] is not None else 16383,
                    }
                },
                # Capacity (from DB capacity columns)
                "specifications": {
                    "capacity": {
                        "min": {"value": r.get("capacity_min") or 0,    "unit": r.get("unit") or "kg"},
                        "max": {"value": r.get("capacity_max") or 1000, "unit": r.get("unit") or "kg"},
                    }
                },
                # Levels (from POST body -- enabled only)
                "levels": {
                    "type": "ratio",
                    "parameters": {"ratios": active_levels}
                },
                # Tare (from DB calibration columns)
                "tare": {
                    "type": "manual",
                    "parameters": {"offset_raw": r.get("tare_offset") or 0.0}
                },
                # Calibration (from DB calibration columns)
                "calibration": {
                    "type": "single_point",
                    "parameters": {
                        "ref_weight": {
                            "value": r.get("known_weight") or 0,
                            "unit":  r.get("unit") or "kg",
                        },
                        "ref_raw": r.get("known_weight_raw") or 0.0,
                    }
                },
                # Filters (from POST body -- enabled only, 'enabled' key stripped)
                "filter": {
                    "raw":    active_raw,
                    "weight": active_weight,
                }
            }]
        }

        config_json = json.dumps(config, indent=2)
        print("[LC-CFG] Built v{}: raw={} weight={} levels={}".format(
            new_version, len(active_raw), len(active_weight), len(active_levels)))

        # -- STEP 4: Save to disk ------------------------------------------
        config_dir  = "loadcell_configs"
        os.makedirs(config_dir, exist_ok=True)
        ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename    = "{}/loadcell_config_{}.json".format(config_dir, ts)
        latest_file = "{}/loadcell_config_latest.json".format(config_dir)
        for path in (filename, latest_file):
            with open(path, 'w') as fh:
                fh.write(config_json)
        print("[LC-CFG] Saved: {}".format(filename))

        # -- STEP 5: Send via pipeline -------------------------------------
        pipeline_sent    = False
        pipeline_message = "Not sent -- pipeline not connected"
        target_service   = None

        with pipeline_state["lock"]:
            client    = pipeline_state.get("client")
            connected = pipeline_state.get("connected", False)

        if connected and client:
            target_service = _find_loadcell_service()
            print("[LC-CFG] Target service: {}".format(target_service))

            if target_service:
                try:
                    rid = client.datapoint_update(target_service, "loadcell_config", config_json)
                    print("[LC-CFG] datapoint_update -> rid={}".format(rid))
                    if rid > 0:
                        pipeline_sent    = True
                        pipeline_message = "Sent to {} (v{})".format(target_service, new_version)
                        record_pipeline_send_success("loadcell", new_version, target_service, pipeline_message)
                        with pipeline_state["lock"]:
                            pipeline_state["loadcell_config"]         = config_json
                            pipeline_state["loadcell_config_pending"] = None
                        print("[LC-CFG] " + pipeline_message)

                        # Request live data back from the service for each device.
                        # Sending datapoint_update(service, device_name, '{}') tells
                        # the service to start publishing that device's datapoints back
                        # to web_ui (weight, raw, tared, calibrated, etc.)
                        for lc_entry in config.get("load_cells", []):
                            dev_dp = lc_entry.get("name")
                            if dev_dp:
                                try:
                                    client.datapoint_update(target_service, dev_dp, '{}')
                                    print("[LC-CFG] Requested live data for: '{}'".format(dev_dp))
                                except Exception as pull_e:
                                    print("[LC-CFG] Live data request error for '{}': {}".format(dev_dp, pull_e))

                        # Subscribe to all mapped receive datapoints for this device
                        # so RECEIVE_DONE fires when the service publishes live data back.
                        # The map values are the datapoint names the service will publish:
                        #   e.g. "loadcell_1.weight_kg", "loadcell_1.raw", "loadcell_1.tared" ...
                        device_name = r["name"]
                        mapped_datapoints = [
                            "{}.weight_kg".format(device_name),
                            "{}.raw".format(device_name),
                            "{}.unit".format(device_name),
                            "{}.known_weight_kg".format(device_name),
                            "{}.known_raw".format(device_name),
                            "{}.tared".format(device_name),
                            "{}.calibrated".format(device_name),
                            "{}.capacity".format(device_name),
                        ]
                        if hasattr(client, 'subscribe'):
                            for dp in mapped_datapoints:
                                try:
                                    client.subscribe(dp)
                                    print("[LC-CFG] Subscribed to receive: '{}'".format(dp))
                                except Exception as sub_e:
                                    print("[LC-CFG] Subscribe error for '{}': {}".format(dp, sub_e))
                            with pipeline_state["lock"]:
                                pipeline_state["subscribed_datapoints"].update(mapped_datapoints)
                    else:
                        pipeline_message = "Send failed (rid=0) -- queued as pending"
                        record_pipeline_send_failure("loadcell", pipeline_message)
                        with pipeline_state["lock"]:
                            pipeline_state["loadcell_config_pending"] = config_json
                except Exception as exc:
                    pipeline_message = "Error: {} -- queued as pending".format(exc)
                    record_pipeline_send_failure("loadcell", pipeline_message)
                    with pipeline_state["lock"]:
                        pipeline_state["loadcell_config_pending"] = config_json
            else:
                pipeline_message = "Service '{}' not connected -- queued as pending".format(
                    get_pipeline_service_name("loadcell") or "load_cell_service")
                record_pipeline_send_failure("loadcell", pipeline_message)
                with pipeline_state["lock"]:
                    pipeline_state["loadcell_config_pending"] = config_json
                print("[LC-CFG] " + pipeline_message)
        else:
            pipeline_message = "Queued as pending (not connected)"
            record_pipeline_send_failure("loadcell", pipeline_message)
            with pipeline_state["lock"]:
                pipeline_state["loadcell_config_pending"] = config_json
            print("[LC-CFG] " + pipeline_message)

        return web.json_response({
            "success":               True,
            "pipeline_sent":         pipeline_sent,
            "pipeline_message":      pipeline_message,
            "target_service":        target_service,
            "version":               new_version,
            "file_saved":            filename,
            "file_latest":           latest_file,
            "active_raw_filters":    len(active_raw),
            "active_weight_filters": len(active_weight),
            "active_levels":         len(active_levels),
        })

    except Exception as e:
        logging.error("pipeline_filters_post_handler error: %s", e)
        import traceback
        traceback.print_exc()
        return web.json_response({"success": False, "error": str(e)})

# ============================================================================
# MODBUS -- BUILD + SEND CONFIG
# ============================================================================

async def pipeline_save_modbus_config(request):
    """POST /api/pipeline/modbus-config/save

    Reads all enabled modbus tags from DB, builds {connections, assets, version},
    saves to disk, sends to the modbus pipeline service.
    """
    print("\n" + "="*70)
    print("[MODBUS-CFG] Save Modbus Configuration  ->  Build  ->  Send")
    print("="*70)

    if not PIPELINE_AVAILABLE:
        return web.json_response({"success": False, "error": "ilx_pipeline not available"})

    try:
        # -- STEP 1: Read tags from DB -------------------------------------
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                md.id, md.device_id, md.name as tag_name, md.slave_id,
                md.register_address, md.register_type, md.data_type,
                md.byte_order, md.word_order, md.scale_factor, md.offset,
                md.unit, md.writable, md.retry_count, md.timeout_ms,
                md.register_count, md."group" as tag_group,
                m.name as device_name, m.device_type,
                m.ip_address, m.port,
                m.serial_port, m.baud_rate, m.parity, m.data_bits, m.stop_bits,
                m.response_timeout_ms, m.byte_timeout_ms, m.max_retries,
                m.polling_interval_ms
            FROM modbus_datapoints md
            JOIN modbus_device m ON md.device_id = m.id
            WHERE md.enabled = 1
            ORDER BY md.device_id, md.slave_id
        ''')
        rows = cursor.fetchall()
        conn.close()

        print("[MODBUS-CFG] {} tags from DB".format(len(rows)))
        if not rows:
            return web.json_response({"success": False, "error": "No Modbus tags found in database"})

        # -- STEP 2: Build connections + assets ----------------------------
        connection_map = {}
        assets = []

        for row in rows:
            r      = dict(row)
            dev_id = r['device_id']
            name   = r['device_name'] or str(dev_id)
            dtype  = r['device_type'] or 'tcp'

            if dev_id not in connection_map:
                if dtype in ('tcp', 'modbus-tcp'):
                    connection_map[dev_id] = {
                        "id": name, "type": "tcp",
                        "host":              r.get('ip_address') or '127.0.0.1',
                        "port":              r.get('port') or 502,
                        "responseTimeoutMs": r.get('response_timeout_ms') or 100,
                        "byteTimeoutMs":     r.get('byte_timeout_ms') or 100,
                        "maxRetries":        r.get('max_retries') or 2,
                        "pollingIntervalMs": r.get('polling_interval_ms') or 300,
                    }
                else:
                    connection_map[dev_id] = {
                        "id": name, "type": "rtu",
                        "device":            r.get('serial_port') or '/dev/ttyUSB0',
                        "baud":              r.get('baud_rate') or 9600,
                        "parity":            r.get('parity') or 'N',
                        "dataBits":          r.get('data_bits') or 8,
                        "stopBits":          r.get('stop_bits') or 1,
                        "responseTimeoutMs": r.get('response_timeout_ms') or 100,
                        "byteTimeoutMs":     r.get('byte_timeout_ms') or 100,
                        "maxRetries":        r.get('max_retries') or 2,
                        "pollingIntervalMs": r.get('polling_interval_ms') or 300,
                    }

            asset = {
                "name":          r['tag_name'],
                "connection_id": name,
                "slaveId":       r['slave_id'] or 1,
                "registerType":  r['register_type'] or 'holding',
                "address":       r['register_address'] or 0,
                "registerCount": r['register_count'] or 1,
                "dataType":      r['data_type'] or 'uint16',
                "scale":         r['scale_factor'] or 1.0,
                "offset":        r['offset'] or 0.0,
                "byteOrder":     r['byte_order'] or 'big',
                "wordOrder":     r['word_order'] or 'big',
                "retryCount":    r['retry_count'] or 1,
                "timeoutMs":     r['timeout_ms'] or 100,
                "writable":      bool(r['writable']),
            }
            if r.get('tag_group'):
                asset['group'] = r['tag_group']
            assets.append(asset)

        # -- STEP 3: Get next version from DB (only written back on success) --
        new_version = get_next_pipeline_version("modbus")
        with pipeline_state["lock"]:
            pipeline_state["last_config_time"] = time.time()

        config = {
            "connections":   list(connection_map.values()),
            "assets":        assets,
            "version":       new_version,
            "timestamp":     time.time(),
            "timestamp_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source":        "web_ui",
            "tag_count":     len(rows),
        }
        config_json = json.dumps(config, indent=2)
        print("[MODBUS-CFG] Built v{}: {} connections, {} assets".format(
            new_version, len(connection_map), len(assets)))

        # -- STEP 4: Save to disk ------------------------------------------
        config_dir = "modbus_configs"
        os.makedirs(config_dir, exist_ok=True)
        ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename    = "{}/modbus_config_{}.json".format(config_dir, ts)
        latest_file = "{}/modbus_config_latest.json".format(config_dir)
        for path in (filename, latest_file):
            with open(path, 'w') as fh:
                fh.write(config_json)
        print("[MODBUS-CFG] Saved: {}".format(filename))

        # -- STEP 5: Send via pipeline -------------------------------------
        pipeline_sent    = False
        pipeline_message = "Not sent -- pipeline not connected"
        target_service   = None

        with pipeline_state["lock"]:
            client    = pipeline_state.get("client")
            connected = pipeline_state.get("connected", False)

        if connected and client:
            target_service = _find_modbus_service()

            if target_service:
                try:
                    rid = client.datapoint_update(target_service, "modbus_config", config_json)
                    if rid > 0:
                        pipeline_sent    = True
                        pipeline_message = "Sent to {} (v{})".format(target_service, new_version)
                        print("[MODBUS-CFG] " + pipeline_message)
                        record_pipeline_send_success("modbus", new_version, target_service, pipeline_message)
                        with pipeline_state["lock"]:
                            pipeline_state["modbus_config_pending"] = None
                    else:
                        pipeline_message = "Send failed (rid=0) -- queued as pending"
                        record_pipeline_send_failure("modbus", pipeline_message)
                        with pipeline_state["lock"]:
                            pipeline_state["modbus_config_pending"] = config_json
                except Exception as exc:
                    pipeline_message = "Error: {} -- queued as pending".format(exc)
                    record_pipeline_send_failure("modbus", pipeline_message)
                    with pipeline_state["lock"]:
                        pipeline_state["modbus_config_pending"] = config_json
            else:
                pipeline_message = "Service '{}' not connected -- queued as pending".format(
                    get_pipeline_service_name("modbus") or "modbus_service")
                record_pipeline_send_failure("modbus", pipeline_message)
                with pipeline_state["lock"]:
                    pipeline_state["modbus_config_pending"] = config_json
        else:
            with pipeline_state["lock"]:
                pipeline_state["modbus_config_pending"] = config_json
            pipeline_message = "Queued as pending (not connected)"
            record_pipeline_send_failure("modbus", pipeline_message)
            print("[MODBUS-CFG] " + pipeline_message)

        return web.json_response({
            "success":          True,
            "pipeline_sent":    pipeline_sent,
            "pipeline_message": pipeline_message,
            "target_service":   target_service,
            "version":          new_version,
            "file_saved":       filename,
            "file_latest":      latest_file,
            "connections":      len(connection_map),
            "assets":           len(assets),
        })

    except Exception as e:
        print("[MODBUS-CFG] Error: {}".format(e))
        import traceback
        traceback.print_exc()
        return web.json_response({"success": False, "error": str(e)})


# Standalone coroutine -- callable without an HTTP request (e.g. on startup)
async def send_modbus_config_now():
    """Build and send the modbus config directly (no HTTP request needed).

    Returns a dict with success, pipeline_sent, version, pipeline_message.
    Safe to call at startup or from any async context.
    """
    class _FakeRequest:
        pass
    resp = await pipeline_save_modbus_config(_FakeRequest())
    import json as _json
    try:
        return _json.loads(resp.body)
    except Exception:
        return {"success": False, "error": "could not parse response"}


# Legacy alias
async def pipeline_modbus_config_handler(request):
    """POST /api/pipeline/modbus-config -- legacy alias"""
    return await pipeline_save_modbus_config(request)

# ============================================================================
# IOT GATEWAY CONFIG -- BUILD + SAVE + SEND
# ============================================================================

async def send_iot_gateway_config_now():
    """Build iot_gateway config, save timestamped copy to disk, send via pipeline.

    Called from:
      - general_config.put_config_handler  (wifi/heartbeat changed)
      - mqtt_cloud._save_all               (MQTT channels/mappings changed)
      - POST /api/pipeline/iot-gateway-config/send  (manual trigger)

    Returns dict: {success, pipeline_sent, pipeline_message, version, file_saved}
    """
    print("\n" + "="*60)
    print("[IOT-CFG] Build  ->  Save  ->  Send")
    print("="*60)

    try:
        from mqtt_cloud import build_iot_gateway_config
        config = build_iot_gateway_config()
    except Exception as e:
        print("[IOT-CFG] build error: {}".format(e))
        return {"success": False, "error": "build failed: {}".format(e)}

    # Bump version
    # Get next version from DB (only written back on success)
    new_version = get_next_pipeline_version("iot_gateway")

    config["version"] = new_version
    config_json = json.dumps(config, indent=2)
    print("[IOT-CFG] Built v{}: {} server(s), {} mapping(s)".format(
        new_version, len(config.get("servers", {})), len(config.get("mappings", []))))

    # Save to disk
    config_dir  = "iot_gateway_configs"
    os.makedirs(config_dir, exist_ok=True)
    ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename    = "{}/iot_gateway_config_{}.json".format(config_dir, ts)
    latest_file = "{}/iot_gateway_config_latest.json".format(config_dir)
    for path in (filename, latest_file):
        with open(path, 'w') as fh:
            fh.write(config_json)
    print("[IOT-CFG] Saved: {}".format(filename))

    # Send via pipeline
    pipeline_sent    = False
    pipeline_message = "Not sent -- pipeline not connected"
    target_service   = None

    with pipeline_state["lock"]:
        client    = pipeline_state.get("client")
        connected = pipeline_state.get("connected", False)

    if connected and client:
        target_service = _find_iot_gateway_service()
        if target_service:
            try:
                rid = client.datapoint_update(target_service, "iot_gateway_config", config_json)
                if rid > 0:
                    pipeline_sent    = True
                    pipeline_message = "Sent to {} (v{})".format(target_service, new_version)
                    record_pipeline_send_success("iot_gateway", new_version, target_service, pipeline_message)
                    with pipeline_state["lock"]:
                        pipeline_state["iot_gateway_config"]         = config_json
                        pipeline_state["iot_gateway_config_pending"] = None
                    print("[IOT-CFG] " + pipeline_message)
                else:
                    pipeline_message = "Send failed (rid=0) -- queued as pending"
                    record_pipeline_send_failure("iot_gateway", pipeline_message)
                    with pipeline_state["lock"]:
                        pipeline_state["iot_gateway_config_pending"] = config_json
            except Exception as exc:
                pipeline_message = "Error: {} -- queued as pending".format(exc)
                record_pipeline_send_failure("iot_gateway", pipeline_message)
                with pipeline_state["lock"]:
                    pipeline_state["iot_gateway_config_pending"] = config_json
        else:
            pipeline_message = "Service '{}' not connected -- queued as pending".format(
                get_pipeline_service_name("iot_gateway") or "iot_gateway_service")
            record_pipeline_send_failure("iot_gateway", pipeline_message)
            with pipeline_state["lock"]:
                pipeline_state["iot_gateway_config_pending"] = config_json
            print("[IOT-CFG] " + pipeline_message)
    else:
        pipeline_message = "Queued as pending (not connected)"
        record_pipeline_send_failure("iot_gateway", pipeline_message)
        with pipeline_state["lock"]:
            pipeline_state["iot_gateway_config_pending"] = config_json
        print("[IOT-CFG] " + pipeline_message)

    return {
        "success":          True,
        "pipeline_sent":    pipeline_sent,
        "pipeline_message": pipeline_message,
        "target_service":   target_service,
        "version":          new_version,
        "file_saved":       filename,
        "file_latest":      latest_file,
    }


async def pipeline_send_iot_gateway_config_handler(request):
    """POST /api/pipeline/iot-gateway-config/send"""
    result = await send_iot_gateway_config_now()
    return web.json_response(result, status=200 if result.get("success") else 500)


async def pipeline_iot_gateway_config_view_handler(request):
    """GET /api/pipeline/iot-gateway-config"""
    with pipeline_state["lock"]:
        config = pipeline_state.get("iot_gateway_config")
    if not config:
        return web.json_response({"success": False, "message": "No iot_gateway config stored"})
    try:
        return web.json_response({"success": True, "config": json.loads(config)})
    except Exception as e:
        return web.json_response({"success": True, "config": config, "error": str(e)})

# ============================================================================
# ROUTE REGISTRATION
# ============================================================================

# ============================================================================
# AUTO-SEND  -- fire immediately for all enabled targets
# ============================================================================

async def pipeline_auto_send_handler(request):
    """POST /api/pipeline/auto-send
    
    Reads all enabled pipeline service targets from DB and immediately
    sends each config to its service.  Does NOT wait for connection --
    if a service is not yet connected the config is queued as pending
    exactly the same as a manual push.
    """
    from database import get_enabled_pipeline_targets

    targets  = get_enabled_pipeline_targets()
    results  = []

    for tgt in targets:
        cfg_type = tgt["config_type"]
        svc_name = tgt["service_name"]
        print("[AUTO-SEND] Sending {} -> {}".format(cfg_type, svc_name or "(no service configured)"))

        try:
            if cfg_type == "modbus":
                class _FakeReq: pass
                resp = await pipeline_save_modbus_config(_FakeReq())
                import json as _j
                d = _j.loads(resp.body)
            elif cfg_type == "loadcell":
                class _FakeReq: pass
                resp = await pipeline_filters_post_handler(_FakeReq())
                import json as _j
                try:
                    d = _j.loads(resp.body)
                except Exception:
                    d = {"success": False, "error": "no loadcell device configured"}
            elif cfg_type == "iot_gateway":
                d = await send_iot_gateway_config_now()
            else:
                d = {"success": False, "error": "unknown config_type"}

            results.append({
                "config_type":    cfg_type,
                "service_name":   svc_name,
                "success":        d.get("success", False),
                "pipeline_sent":  d.get("pipeline_sent", False),
                "version":        d.get("version"),
                "message":        d.get("pipeline_message") or d.get("error") or "",
            })
        except Exception as e:
            results.append({
                "config_type":  cfg_type,
                "service_name": svc_name,
                "success":      False,
                "pipeline_sent": False,
                "message":      str(e),
            })

    any_sent = any(r.get("pipeline_sent") for r in results)
    return web.json_response({
        "success": True,
        "auto_sent": any_sent,
        "results": results,
        "targets_attempted": len(results),
    })


async def pipeline_send_log_handler(request):
    """GET /api/pipeline/send-log -- return per-type send history from DB"""
    from database import get_all_pipeline_send_logs
    logs = get_all_pipeline_send_logs()
    return web.json_response({"logs": logs})


def register_pipeline_routes(app):
    """Register all pipeline API routes."""

    # -- Connection --------------------------------------------------------
    app.router.add_post('/api/pipeline/connect',    pipeline_connect_handler)
    app.router.add_post('/api/pipeline/disconnect', pipeline_disconnect_handler)

    # -- Status / info -----------------------------------------------------
    app.router.add_get('/api/pipeline/status',          pipeline_status_handler)
    app.router.add_get('/api/pipeline/services',        pipeline_services_handler)
    app.router.add_get('/api/pipeline/debug',           pipeline_debug_handler)
    app.router.add_get('/api/pipeline/config',          pipeline_modbus_config_view_handler)
    app.router.add_get('/api/pipeline/loadcell-config', pipeline_loadcell_config_view_handler)

    # -- WebSocket stream --------------------------------------------------
    app.router.add_get('/ws/pipeline/load_raw', pipeline_loadraw_ws_handler)

    # -- Loadcell (send config + receive live data) ------------------------
    app.router.add_get('/api/pipeline/loadcell-devices', pipeline_loadcell_devices_handler)
    app.router.add_get('/api/pipeline/calibration',      pipeline_calibration_get_handler)
    app.router.add_post('/api/pipeline/calibration',     pipeline_calibration_post_handler)
    app.router.add_post('/api/pipeline/filters',         pipeline_filters_post_handler)

    # -- Modbus (send only) ------------------------------------------------
    app.router.add_post('/api/pipeline/modbus-config',      pipeline_modbus_config_handler)
    app.router.add_post('/api/pipeline/modbus-config/save', pipeline_save_modbus_config)

    # -- IoT Gateway (send only) -------------------------------------------
    app.router.add_get ('/api/pipeline/iot-gateway-config',      pipeline_iot_gateway_config_view_handler)
    app.router.add_post('/api/pipeline/iot-gateway-config/send', pipeline_send_iot_gateway_config_handler)

    # -- Core Config (send only) -------------------------------------------
    app.router.add_get ('/api/pipeline/core-config',        pipeline_core_config_view_handler)
    app.router.add_get ('/api/pipeline/core-configs',       pipeline_core_configs_list_handler)
    app.router.add_post('/api/pipeline/core-config/upload', pipeline_core_config_upload_handler)
    app.router.add_post('/api/pipeline/core-config/resend', pipeline_core_config_resend_handler)

    # -- Auto-send + send log ----------------------------------------------
    app.router.add_post('/api/pipeline/auto-send',  pipeline_auto_send_handler)
    app.router.add_get ('/api/pipeline/send-log',   pipeline_send_log_handler)

    # Seed any missing pipeline_service_targets rows
    _seed_pipeline_targets()

    print("[PIPELINE] Routes registered OK")


def _seed_pipeline_targets():
    """Ensure all known config types exist in pipeline_service_targets.
    Inserts missing rows with empty service_name and enabled=False.
    Never overwrites existing rows.
    """
    KNOWN_TYPES = [
        ("modbus",      "Modbus TCP/RTU service -- send only"),
        ("loadcell",    "Load cell service -- send config + receive live data"),
        ("iot_gateway", "IoT Gateway service -- send only"),
        ("core",        "Core config service -- send only"),
    ]
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        for cfg_type, description in KNOWN_TYPES:
            cursor.execute(
                "SELECT 1 FROM pipeline_service_targets WHERE config_type = ?",
                (cfg_type,)
            )
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO pipeline_service_targets "
                    "(config_type, service_name, enabled, description) "
                    "VALUES (?, '', 0, ?)",
                    (cfg_type, description)
                )
                print("[PIPELINE] Seeded pipeline target: {}".format(cfg_type))
        conn.commit()
        conn.close()
    except Exception as e:
        print("[PIPELINE] Warning: could not seed pipeline targets: {}".format(e))


# ============================================================================
# CORE CONFIG -- receive JSON upload, persist to DB, forward via pipeline (send only)
# ============================================================================

async def pipeline_core_config_upload_handler(request):
    """POST /api/pipeline/core-config/upload
    Accepts an inno_load-style JSON body, extracts device names from load_cells[],
    persists to DB table core_configs, then forwards to the core pipeline service.
    """
    print("\n" + "="*70)
    print("[CORE-CFG] Upload  ->  Persist  ->  Send")
    print("="*70)

    try:
        body = await request.json()
    except Exception as e:
        return web.json_response({"success": False, "error": "Invalid JSON: {}".format(e)}, status=400)

    load_cells = body.get("load_cells", [])
    device_names = [lc.get("name", "") for lc in load_cells if lc.get("name")]
    service_name_in_cfg = None
    for entry in body.get("ipc", []):
        sn = (entry.get("parameters") or {}).get("service_name")
        if sn:
            service_name_in_cfg = sn
            break

    config_json = json.dumps(body, indent=2)
    new_version  = get_next_pipeline_version("core")

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS core_configs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                version      INTEGER NOT NULL,
                device_names TEXT,
                service_name TEXT,
                config_json  TEXT NOT NULL,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute(
            "INSERT INTO core_configs (version, device_names, service_name, config_json) VALUES (?, ?, ?, ?)",
            (new_version, json.dumps(device_names), service_name_in_cfg or "", config_json)
        )
        conn.commit()
        conn.close()
        print("[CORE-CFG] Persisted v{} to DB. Devices: {}".format(new_version, device_names))
    except Exception as db_err:
        logging.error("[CORE-CFG] DB persist error: %s", db_err)
        return web.json_response({"success": False, "error": "DB error: {}".format(db_err)}, status=500)

    config_dir  = "core_configs"
    os.makedirs(config_dir, exist_ok=True)
    ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename    = "{}/core_config_{}.json".format(config_dir, ts)
    latest_file = "{}/core_config_latest.json".format(config_dir)
    for path in (filename, latest_file):
        with open(path, 'w') as fh:
            fh.write(config_json)

    pipeline_sent    = False
    pipeline_message = "Not sent -- pipeline not connected"
    target_service   = None

    with pipeline_state["lock"]:
        client    = pipeline_state.get("client")
        connected = pipeline_state.get("connected", False)

    if connected and client:
        target_service = _find_core_service()
        if target_service:
            try:
                rid = client.datapoint_update(target_service, "core_config", config_json)
                if rid > 0:
                    pipeline_sent    = True
                    pipeline_message = "Sent to {} (v{})".format(target_service, new_version)
                    record_pipeline_send_success("core", new_version, target_service, pipeline_message)
                    with pipeline_state["lock"]:
                        pipeline_state["core_config"]         = config_json
                        pipeline_state["core_config_pending"] = None
                else:
                    pipeline_message = "Send failed (rid=0) -- queued as pending"
                    record_pipeline_send_failure("core", pipeline_message)
                    with pipeline_state["lock"]:
                        pipeline_state["core_config_pending"] = config_json
            except Exception as exc:
                pipeline_message = "Error: {} -- queued as pending".format(exc)
                record_pipeline_send_failure("core", pipeline_message)
                with pipeline_state["lock"]:
                    pipeline_state["core_config_pending"] = config_json
        else:
            pipeline_message = "Service '{}' not connected -- queued as pending".format(
                get_pipeline_service_name("core") or "core_service")
            record_pipeline_send_failure("core", pipeline_message)
            with pipeline_state["lock"]:
                pipeline_state["core_config_pending"] = config_json
    else:
        pipeline_message = "Queued as pending (not connected)"
        record_pipeline_send_failure("core", pipeline_message)
        with pipeline_state["lock"]:
            pipeline_state["core_config_pending"] = config_json

    return web.json_response({
        "success":                True,
        "pipeline_sent":          pipeline_sent,
        "pipeline_message":       pipeline_message,
        "target_service":         target_service,
        "version":                new_version,
        "device_names":           device_names,
        "service_name_in_config": service_name_in_cfg,
        "file_saved":             filename,
        "file_latest":            latest_file,
    })


async def pipeline_core_config_view_handler(request):
    """GET /api/pipeline/core-config"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, version, device_names, service_name, config_json, created_at "
            "FROM core_configs ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return web.json_response({"success": False, "message": "No core config stored"})
        d = dict(row)
        try: d["config_json"] = json.loads(d["config_json"])
        except Exception: pass
        try: d["device_names"] = json.loads(d["device_names"])
        except Exception: pass
        return web.json_response({"success": True, "config": d})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def pipeline_core_configs_list_handler(request):
    """GET /api/pipeline/core-configs"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS core_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, version INTEGER NOT NULL,
                device_names TEXT, service_name TEXT, config_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute(
            "SELECT id, version, device_names, service_name, created_at "
            "FROM core_configs ORDER BY id DESC LIMIT 50"
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        for r in rows:
            try: r["device_names"] = json.loads(r["device_names"])
            except Exception: pass
        return web.json_response({"success": True, "configs": rows})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def pipeline_core_config_resend_handler(request):
    """POST /api/pipeline/core-config/resend"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT config_json, version FROM core_configs ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return web.json_response({"success": False, "error": "No core config in DB to resend"})

        config_json = row["config_json"]
        new_version  = get_next_pipeline_version("core")
        pipeline_sent    = False
        pipeline_message = "Not sent -- pipeline not connected"
        target_service   = None

        with pipeline_state["lock"]:
            client    = pipeline_state.get("client")
            connected = pipeline_state.get("connected", False)

        if connected and client:
            target_service = _find_core_service()
            if target_service:
                try:
                    rid = client.datapoint_update(target_service, "core_config", config_json)
                    if rid > 0:
                        pipeline_sent    = True
                        pipeline_message = "Resent to {} (v{})".format(target_service, new_version)
                        record_pipeline_send_success("core", new_version, target_service, pipeline_message)
                        with pipeline_state["lock"]:
                            pipeline_state["core_config"]         = config_json
                            pipeline_state["core_config_pending"] = None
                    else:
                        pipeline_message = "Resend failed (rid=0) -- queued"
                        record_pipeline_send_failure("core", pipeline_message)
                        with pipeline_state["lock"]:
                            pipeline_state["core_config_pending"] = config_json
                except Exception as exc:
                    pipeline_message = "Error: {} -- queued".format(exc)
                    record_pipeline_send_failure("core", pipeline_message)
                    with pipeline_state["lock"]:
                        pipeline_state["core_config_pending"] = config_json
            else:
                pipeline_message = "Service not connected -- queued"
                record_pipeline_send_failure("core", pipeline_message)
                with pipeline_state["lock"]:
                    pipeline_state["core_config_pending"] = config_json
        else:
            pipeline_message = "Not connected -- queued"
            record_pipeline_send_failure("core", pipeline_message)
            with pipeline_state["lock"]:
                pipeline_state["core_config_pending"] = config_json

        return web.json_response({
            "success":          True,
            "pipeline_sent":    pipeline_sent,
            "pipeline_message": pipeline_message,
            "target_service":   target_service,
            "version":          new_version,
        })
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)