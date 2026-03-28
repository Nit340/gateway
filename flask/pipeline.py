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
#    |  STEP 4 -- Send via pipeline CONFIG channel
#    |     client.publish_config(Config(name="loadcell_config",
#    |                                  value=config_json,
#    |                                  version=new_version,
#    |                                  service=load_cell_service))
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
#    |  1. Reads vfd_datapoints JOIN vfd_device (enabled only)
#    |  2. Builds {connections:[...], assets:[...], version, timestamp}
#    |  3. client.datapoint_update(<modbus_service>, "modbus_config", json)
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
from logger_util import get_logger

logger = get_logger(__name__)
try:
    from aiohttp import WSMsgType as MsgType
except ImportError:
    # aiohttp 2.x
    from aiohttp.web import MsgType

try:
    from ilx_pipeline import PipelineClient, EventType, DataType, Config
    PIPELINE_AVAILABLE = True
    logger.info("ilx_pipeline imported OK")
except ImportError:
    PIPELINE_AVAILABLE = False
    logger.warning("ilx_pipeline not available!")

from database import (
    DB_FILE,
    get_pipeline_service_name,
    get_pipeline_config_name,
    get_next_pipeline_version,
    record_pipeline_send_success,
    record_pipeline_send_failure,
    get_enabled_pipeline_targets,
)
from auth import ws_auth

# ============================================================================
# RATE LIMITING / FLOOD PROTECTION
# ============================================================================

# Minimum seconds between load_raw WebSocket broadcasts (prevents event-loop flood)
_LOAD_RAW_MIN_INTERVAL = 0.05   # 50 ms  ? max 20 broadcasts/sec
_last_load_raw_broadcast = 0.0

# Maximum number of pending coroutines we'll schedule on the main loop at once.
# If the queue is already this deep, new broadcasts are silently dropped.
_MAX_PENDING_BROADCASTS = 10
_pending_broadcast_count = 0
_pending_broadcast_lock  = threading.Lock()

# -- Flood kill guard --
# If load_raw arrives faster than this, exit immediately instead of freezing.
_LOAD_RAW_MAX_RATE   = 50        # events per second
_LOAD_RAW_WINDOW     = 1.0       # sliding window (seconds)
_load_raw_timestamps = []
_load_raw_flood_lock = threading.Lock()

def _check_load_raw_flood():
    """Kill the process cleanly if load_raw is arriving too fast.
    A clean exit lets systemd/supervisor restart the service rather than
    leaving it frozen and unresponsive indefinitely.
    """
    import sys
    now = time.time()
    with _load_raw_flood_lock:
        _load_raw_timestamps.append(now)
        cutoff = now - _LOAD_RAW_WINDOW
        while _load_raw_timestamps and _load_raw_timestamps[0] < cutoff:
            _load_raw_timestamps.pop(0)
        rate = len(_load_raw_timestamps)

    if rate > _LOAD_RAW_MAX_RATE:
        msg = (
            "FATAL: load_raw flood detected -- "
            "{} events/{:.1f}s exceeds limit of {}. "
            "Exiting to prevent freeze.".format(rate, _LOAD_RAW_WINDOW, _LOAD_RAW_MAX_RATE)
        )
        logger.critical(msg)
        sys.exit(1)

# ============================================================================
# DATAPOINT WHITELIST
# ============================================================================
# _dp_whitelist holds the exact datapoint names that may be broadcast.
#
# Rules:
#   - _PERMANENT_WHITELIST entries (network/status) are always present.
#   - Load-cell datapoints are only broadcast for explicitly whitelisted
#     device names.  Add a name via add_whitelisted_device_name(name) --
#     no auto-discovery from DB, no custom or unnamed devices.
#   - The <name>_raw datapoint is the sole exception: it is only added when
#     the UI Raw toggle is ON and removed when OFF.
#   - Any datapoint NOT in the whitelist is silently dropped.

_dp_whitelist = set()          # exact datapoint names allowed to broadcast
_dp_whitelist_lock = threading.Lock()

# Explicitly whitelisted device names (must be added by name; no auto-discover)
_whitelisted_device_names = set()
_whitelisted_names_lock = threading.Lock()

# Track (config_type, version) pairs already successfully sent so that
# SERVICE_ADDED replays on reconnect do not re-send the same config.
_sent_versions = set()
_sent_versions_lock = threading.Lock()


def _mark_sent(config_type, version):
    """Record that this config version was successfully sent."""
    with _sent_versions_lock:
        _sent_versions.add((config_type, version))


def _clear_sent(config_type):
    """Remove all sent records for config_type so a new pending version
    will be flushed even if an old version of the same type was sent before.
    """
    with _sent_versions_lock:
        stale = {k for k in _sent_versions if k[0] == config_type}
        _sent_versions.difference_update(stale)


# Network/status datapoints that are always allowed regardless of device
_PERMANENT_WHITELIST = {"lan", "wlan", "lte", "network_status", "modbus_config"}

# Suffixes appended to each whitelisted device name (excludes .raw, toggled separately)
_DEVICE_DP_SUFFIXES = [
    ".weight_kg",
    ".unit",
    ".known_weight_kg",
    ".known_raw",
    ".tared",
    ".calibrated",
    ".capacity",
]


def add_whitelisted_device_name(name):
    """Explicitly whitelist a device name so its datapoints are broadcast.

    Must be called with the exact device name string (e.g. "load").
    No auto-discovery -- only names registered here are ever allowed.
    Call rebuild_whitelist() afterwards to apply the change immediately.
    """
    name = name.strip()
    if not name:
        logger.warning("Refused to add empty device name")
        return
    with _whitelisted_names_lock:
        _whitelisted_device_names.add(name)
    logger.info("Registered device name: '{}'".format(name))


def rebuild_whitelist(include_raw=False):
    """Rebuild _dp_whitelist from enabled devices in the DB.

    Called once on startup and on every Raw toggle change, so the device
    name is always fresh -- no restart needed after a device import/rename.
    include_raw=True  -> also add <n>_raw for each enabled device
    include_raw=False -> omit the raw datapoints
    """
    new_set = set(_PERMANENT_WHITELIST)

    # Re-read enabled device names from DB on every call
    db_names = set()
    try:
        import sqlite3 as _sq
        _conn = _sq.connect(DB_FILE)
        _conn.row_factory = _sq.Row
        _cur = _conn.cursor()
        _cur.execute("SELECT name FROM loadcell_device WHERE enabled = 1")
        for _row in _cur.fetchall():
            if _row["name"]:
                db_names.add(_row["name"].strip())
        _conn.close()
    except Exception as _e:
        logger.error("DB read error: {}".format(_e))

    # Merge DB names with any explicitly registered names
    with _whitelisted_names_lock:
        names = db_names | set(_whitelisted_device_names)

    for device_name in names:
        for suffix in _DEVICE_DP_SUFFIXES:
            new_set.add("loadcells.{}{}".format(device_name, suffix))
        raw_dp = "loadcells.{}.raw".format(device_name)
        if include_raw:
            new_set.add(raw_dp)
            logger.info("Raw ON  -> added '{}' to whitelist".format(raw_dp))
        else:
            logger.debug("Raw OFF -> '{}' not in whitelist".format(raw_dp))

    if not names:
        logger.debug("No device names found -- only permanent entries active")

    with _dp_whitelist_lock:
        _dp_whitelist.clear()
        _dp_whitelist.update(new_set)

    logger.debug("Active whitelist: {}".format(sorted(_dp_whitelist)))

# ============================================================================
# SHARED STATE
# ============================================================================

pipeline_state = {
    "client":                      None,
    "connected":                    False,
    "loadcell_raw":                 None,   # current value of loadcells.<device>.raw
    "loadcell_raw_dp":              None,   # full datapoint name e.g. "loadcells.MyScale.raw"
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
    "core_config_version":          1,
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
    # load_raw whitelist toggle (controlled via UI button)
    "load_raw_enabled":             False,
    # crash / restart tracking
    "thread_crash_count":           0,
    "thread_last_crash_reason":     None,
    "thread_last_crash_time":       0,
}

# ============================================================================
# INTERNAL HELPERS
# ============================================================================

async def _broadcast_pipeline_msg(msg):
    """Send a message string to all connected WebSocket clients.

    Each send is wrapped in asyncio.wait_for so a frozen client cannot
    stall the entire event loop.  Dead sockets are pruned automatically.
    After the coroutine finishes it decrements the pending-broadcast counter
    so the thread-side guard knows a slot is free.
    """
    global _pending_broadcast_count
    dead = set()
    clients = list(pipeline_state["ws_clients"])
    for ws in clients:
        if ws.closed:
            dead.add(ws)
            continue
        try:
            await asyncio.wait_for(ws.send_str(msg), timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning("WS send timed out -- dropping client")
            dead.add(ws)
        except Exception as e:
            logger.error("WS send failed: {}".format(e))
            dead.add(ws)
    for ws in dead:
        pipeline_state["ws_clients"].discard(ws)

    # Release the slot so the thread-side guard allows new schedules
    with _pending_broadcast_lock:
        _pending_broadcast_count = max(0, _pending_broadcast_count - 1)


def _schedule_broadcast(main_loop, msg):
    """Thread-safe helper: schedule a broadcast only if the pipeline is not
    already backed up.  Drops the message silently when the queue is full,
    which is far safer than flooding the event loop and freezing the process.

    For ``load_raw`` datapoints an additional time-based rate limit is applied
    so high-frequency sensors cannot overwhelm WebSocket clients.
    """
    global _pending_broadcast_count, _last_load_raw_broadcast

    if not main_loop or not main_loop.is_running():
        return

    # Apply datapoint whitelist -- drop anything not in the exact set
    try:
        parsed_msg = json.loads(msg)
        dp_name = parsed_msg.get("datapoint", "")
        if dp_name:
            with _dp_whitelist_lock:
                allowed = dp_name in _dp_whitelist
            if not allowed:
                return  # not whitelisted -- silently drop
    except Exception:
        pass

    # Rate-limit loadcells raw datapoints specifically (most frequent datapoint)
    try:
        parsed = json.loads(msg)
        dp_check = parsed.get("datapoint", "")
        if dp_check.startswith("loadcells.") and dp_check.endswith(".raw"):
            now = time.time()
            if now - _last_load_raw_broadcast < _LOAD_RAW_MIN_INTERVAL:
                return  # drop -- too soon
            _last_load_raw_broadcast = now
    except Exception:
        pass

    with _pending_broadcast_lock:
        if _pending_broadcast_count >= _MAX_PENDING_BROADCASTS:
            return  # drop -- event loop is backed up
        _pending_broadcast_count += 1

    try:
        asyncio.run_coroutine_threadsafe(_broadcast_pipeline_msg(msg), main_loop)
    except Exception as e:
        logger.error("Could not schedule broadcast: {}".format(e))
        with _pending_broadcast_lock:
            _pending_broadcast_count = max(0, _pending_broadcast_count - 1)


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

def _flush_pending_for_service(client, svc):
    """Try to send any pending config for the given service name right now.

    Called from SERVICE_ADDED (service just appeared).
    Guards against duplicate sends using _sent_versions so that
    reconnect-replayed SERVICE_ADDED events don't re-send the same config.
    """
    modbus_svc   = get_pipeline_service_name("modbus")
    loadcell_svc = get_pipeline_service_name("loadcell")
    iot_svc      = get_pipeline_service_name("iot_gateway")
    core_svc     = get_pipeline_service_name("core")

    # ---- Modbus ----
    if svc == modbus_svc:
        with pipeline_state["lock"]:
            pending = pipeline_state.get("modbus_config_pending")
            version = pipeline_state.get("config_version", 0)
        if pending:
            with _sent_versions_lock:
                key = ("modbus", version)
                already = key in _sent_versions
            if already:
                # Do NOT return here -- fall through so loadcell/iot/core blocks still run
                logger.debug("Modbus v{} already sent -- skip duplicate flush".format(version))
            else:
                try:
                    rid = client.datapoint_update(svc, get_pipeline_config_name("modbus"), pending)
                    if rid > 0:
                        logger.info("Flushed pending modbus config to '{}' (rid={})".format(svc, rid))
                        record_pipeline_send_success("modbus", version, svc, "flushed pending")
                        with pipeline_state["lock"]:
                            pipeline_state["modbus_config"]         = pending
                            pipeline_state["modbus_config_pending"] = None
                        _mark_sent(key[0], key[1])
                    else:
                        logger.warning("Flush modbus failed (rid=0) -- stays pending")
                except Exception as e:
                    logger.error("Flush modbus error: {}".format(e))

    # ---- Loadcell ----
    if svc == loadcell_svc:
        with pipeline_state["lock"]:
            pending         = pipeline_state.get("loadcell_config_pending")
            pending_version = pipeline_state.get("loadcell_config_version", 1)
        if pending:
            with _sent_versions_lock:
                key = ("loadcell", pending_version)
                already = key in _sent_versions
            if already:
                logger.debug("Loadcell v{} already sent -- skip duplicate flush".format(pending_version))
                return
            try:
                ok = client.publish_config(Config(
                    name    = get_pipeline_config_name("loadcell"),
                    value   = pending,
                    version = pending_version,
                    service = svc,
                ))
                if ok:
                    logger.info("Flushed pending loadcell config to '{}' (v{})".format(svc, pending_version))
                    record_pipeline_send_success("loadcell", pending_version, svc, "flushed pending")
                    with pipeline_state["lock"]:
                        pipeline_state["loadcell_config_pending"] = None
                        pipeline_state["loadcell_config"]         = pending
                    _mark_sent(key[0], key[1])
                    # Request live data back
                    try:
                        cfg_parsed = json.loads(pending)
                        for lc_entry in cfg_parsed.get("load_cells", []):
                            dev_dp = lc_entry.get("name")
                            if dev_dp:
                                client.datapoint_update(svc, dev_dp, '{}')
                                logger.info("Requested live data for: '{}'".format(dev_dp))
                    except Exception as pull_e:
                        logger.error("Live data request error: {}".format(pull_e))
                    # Re-subscribe
                    if hasattr(client, 'subscribe'):
                        try:
                            cfg = json.loads(pending)
                            for ipc_entry in cfg.get("ipc", []):
                                for dp_entry in (ipc_entry.get("parameters") or {}).get("datapoints", []):
                                    for mapped_dp in (dp_entry.get("map") or {}).values():
                                        try:
                                            client.subscribe(mapped_dp)
                                            logger.info("Subscribed to '{}'".format(mapped_dp))
                                        except Exception as sub_e:
                                            logger.error("Subscribe error '{}': {}".format(mapped_dp, sub_e))
                        except Exception as parse_e:
                            logger.error("Re-subscribe parse error: {}".format(parse_e))
                else:
                    logger.warning("Flush loadcell failed -- stays pending")
            except Exception as e:
                logger.error("Flush loadcell error: {}".format(e))

    # ---- IoT Gateway ----
    if svc == iot_svc:
        with pipeline_state["lock"]:
            pending         = pipeline_state.get("iot_gateway_config_pending")
            pending_version = pipeline_state.get("iot_gateway_config_version", 1)
        if pending:
            with _sent_versions_lock:
                key = ("iot_gateway", pending_version)
                already = key in _sent_versions
            if already:
                logger.debug("IoT gateway v{} already sent -- skip duplicate flush".format(pending_version))
                return
            try:
                ok = client.publish_config(Config(
                    name    = get_pipeline_config_name("iot_gateway"),
                    value   = pending,
                    version = pending_version,
                    service = svc,
                ))
                if ok:
                    logger.info("Flushed pending iot_gateway config to '{}' (v{})".format(svc, pending_version))
                    record_pipeline_send_success("iot_gateway", pending_version, svc, "flushed pending")
                    with pipeline_state["lock"]:
                        pipeline_state["iot_gateway_config_pending"] = None
                        pipeline_state["iot_gateway_config"]         = pending
                    _mark_sent(key[0], key[1])
                else:
                    logger.warning("Flush iot_gateway failed -- stays pending")
            except Exception as e:
                logger.error("Flush iot_gateway error: {}".format(e))

    # ---- Core ----
    if svc == core_svc:
        with pipeline_state["lock"]:
            pending         = pipeline_state.get("core_config_pending")
            pending_version = pipeline_state.get("core_config_version", 1)
        if pending:
            with _sent_versions_lock:
                key = ("core", pending_version)
                already = key in _sent_versions
            if already:
                logger.debug("Core v{} already sent -- skip duplicate flush".format(pending_version))
                return
            try:
                ok = client.publish_config(Config(
                    name    = get_pipeline_config_name("core"),
                    value   = pending,
                    version = pending_version,
                    service = svc,
                ))
                if ok:
                    logger.info("Flushed pending core config to '{}' (v{})".format(svc, pending_version))
                    record_pipeline_send_success("core", pending_version, svc, "flushed pending")
                    with pipeline_state["lock"]:
                        pipeline_state["core_config_pending"] = None
                        pipeline_state["core_config"]         = pending
                        pipeline_state["core_config_version"] = pending_version
                    _mark_sent(key[0], key[1])
                else:
                    logger.warning("Flush core failed -- stays pending")
            except Exception as e:
                logger.error("Flush core error: {}".format(e))


def _flush_all_pending():
    """After storing any pending config, check all currently connected services
    and flush immediately if the target service is already up.
    Called from the async send helpers via asyncio.run_coroutine_threadsafe
    or directly when we already have the client reference.
    """
    with pipeline_state["lock"]:
        client    = pipeline_state.get("client")
        connected = pipeline_state.get("connected", False)
        services  = set(pipeline_state.get("connected_services", set()))
    if not connected or not client:
        return
    for svc in services:
        _flush_pending_for_service(client, svc)


# ============================================================================
# BACKGROUND PIPELINE THREAD
# ============================================================================

def _run_pipeline_thread(host="127.0.0.1", port=7000):
    """Long-running thread that owns the PipelineClient."""
    logger.info("Starting thread ({}:{})".format(host, port))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    crash_reason = None  # track why we exited for the watchdog

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
                    logger.info("Connected")
                    with pipeline_state["lock"]:
                        pipeline_state["connected"] = True
                        pipeline_state["connection_attempts"] = 0
                    try:
                        if hasattr(client, 'subscribe'):
                            # Only subscribe to loadcell mapped datapoints --
                            # modbus/iot_gateway/core are send-only, no subscriptions needed.
                            # Re-subscribe from the last known loadcell config if available.
                            # IMPORTANT: skip .raw datapoints unless the Raw toggle is ON --
                            # subscribing to raw when the toggle is OFF causes the library to
                            # fire DATA_UPDATE/RECEIVE_DONE events continuously even though
                            # the whitelist blocks them from reaching WebSocket clients.
                            with pipeline_state["lock"]:
                                last_lc_config  = pipeline_state.get("loadcell_config")
                                raw_toggle_on   = pipeline_state.get("load_raw_enabled", False)
                            subscribed = set()
                            if last_lc_config:
                                try:
                                    cfg = json.loads(last_lc_config)
                                    for ipc_entry in cfg.get("ipc", []):
                                        for dp_entry in (ipc_entry.get("parameters") or {}).get("datapoints", []):
                                            for mapped_dp in (dp_entry.get("map") or {}).values():
                                                if (mapped_dp.startswith("loadcells.") and
                                                        mapped_dp.endswith(".raw") and
                                                        not raw_toggle_on):
                                                    logger.info("[PIPELINE] Skipping raw subscribe (toggle OFF): '{}'".format(mapped_dp))
                                                    continue
                                                client.subscribe(mapped_dp)
                                                subscribed.add(mapped_dp)
                                                logger.info("[PIPELINE] Subscribed to '{}'".format(mapped_dp))
                                except Exception as parse_e:
                                    logger.error("[PIPELINE] Re-subscribe parse error: {}".format(parse_e))
                            with pipeline_state["lock"]:
                                pipeline_state["subscribed_datapoints"] = subscribed
                        else:
                            client.refresh()
                    except Exception as e:
                        logger.error("[PIPELINE] Subscribe error: {}".format(e))
                        try:
                            client.refresh()
                        except Exception:
                            pass

                # -- Offline ----------------------------------------------
                elif etype == EventType.PIPELINE_OFFLINE:
                    logger.info("Offline")
                    with pipeline_state["lock"]:
                        pipeline_state["connected"] = False

                # -- Service appeared -- flush any pending configs ----------
                elif etype == EventType.SERVICE_ADDED:
                    svc = event.service_name
                    logger.info("[PIPELINE] SERVICE_ADDED: '{}'".format(svc))
                    with pipeline_state["lock"]:
                        pipeline_state["connected_services"].add(svc)
                    # Flush any config that was queued waiting for this service
                    _flush_pending_for_service(client, svc)

                # -- Service removed --------------------------------------
                elif etype == EventType.SERVICE_REMOVED:
                    svc = event.service_name
                    logger.info("[PIPELINE] SERVICE_REMOVED: '{}'".format(svc))
                    with pipeline_state["lock"]:
                        pipeline_state["connected_services"].discard(svc)

                # -- Datapoint received -----------------------------------
                elif etype == EventType.RECEIVE_DONE:
                    dp = event.datapoint_name
                    with _dp_whitelist_lock:
                        _dp_allowed = dp in _dp_whitelist
                    if _dp_allowed:
                        logger.debug("[RECEIVE_DONE: '{}' from '{}'".format(dp, event.service_name))
                    if not _dp_allowed:
                        return  # not whitelisted -- skip read, store and broadcast
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
                            # Track the canonical raw value under a stable key
                            if dp.startswith("loadcells.") and dp.endswith(".raw"):
                                pipeline_state["loadcell_raw"]    = val
                                pipeline_state["loadcell_raw_dp"] = dp

                        # Kill the process if a raw datapoint is arriving too fast
                        # (prevents event-loop freeze from data floods)
                        if dp.startswith("loadcells.") and dp.endswith(".raw"):
                            _check_load_raw_flood()

                        # -- Network-status datapoints ----------------------
                        _NET_SERVICES = {"network_status"}
                        if event.service_name in _NET_SERVICES or dp in (
                            "lan", "wlan", "lte", "network_status"
                        ):
                            try:
                                from general import update_network_status_field

                                if dp == "network_status":
                                    update_network_status_field("network_status", val)
                                    main_loop = pipeline_state.get("main_loop")
                                    _schedule_broadcast(main_loop, json.dumps({"datapoint": dp, "value": val}))
                                else:
                                    if isinstance(val, str):
                                        try:
                                            parsed = json.loads(val)
                                            logger.debug("[Parsed {}: {}".format(dp, parsed))
                                        except json.JSONDecodeError as e:
                                            # Value is not valid JSON (e.g. lte sends unquoted keys).
                                            # Store raw string and broadcast as-is; skip dict traversal.
                                            logger.warning("[JSON parse error for {}: {}".format(dp, e))
                                            update_network_status_field(dp, val)
                                            main_loop = pipeline_state.get("main_loop")
                                            _schedule_broadcast(main_loop, json.dumps({"datapoint": dp, "value": val}))
                                            parsed = None  # sentinel -- skip dict-walk below
                                    else:
                                        parsed = val

                                    if parsed is None:
                                        pass  # already handled in except block above
                                    elif not isinstance(parsed, dict):
                                        update_network_status_field(dp, parsed)
                                        main_loop = pipeline_state.get("main_loop")
                                        _schedule_broadcast(main_loop, json.dumps({"datapoint": dp, "value": parsed}))
                                    else:
                                        for section, section_data in parsed.items():
                                            if isinstance(section_data, dict):
                                                for subsection, subsection_data in section_data.items():
                                                    if isinstance(subsection_data, dict):
                                                        for field_name, field_value in subsection_data.items():
                                                            update_network_status_field(field_name, field_value)
                                                            logger.debug("Updated {} = {}".format(field_name, field_value))
                                                    else:
                                                        update_network_status_field(subsection, subsection_data)
                                            else:
                                                update_network_status_field(section, section_data)

                            except Exception as _ne:
                                logger.error("[network_status parse error: {} for dp={}, val={} (type: {})".format(
                                    _ne, dp, val, type(val)))
                                import traceback
                                traceback.print_exc()

                        main_loop = pipeline_state.get("main_loop")
                        _schedule_broadcast(main_loop, json.dumps({"datapoint": dp, "value": val}))

                    except Exception as e:
                        logger.error("[Error reading dp '{}': {}".format(dp, e))
                        import traceback
                        traceback.print_exc()

                # -- Config received (publish_config channel) -------------
                elif etype == EventType.CONFIG_RECEIVED:
                    cfg = event.config
                    if cfg is not None:
                        logger.info("[CONFIG_RECEIVED: name='{}' version={}".format(
                            cfg.name, cfg.version))
                        if cfg.name == "loadcell_config":
                            # Always process every incoming loadcell_config --
                            # the loadcell service may send it at any time and
                            # we must never ignore or skip it.
                            _handle_received_loadcell_config(cfg)

            except Exception as e:
                logger.error("[Event handler error: {}".format(e))
                import traceback
                traceback.print_exc()

        client.set_event_callback(on_event)
        client.start()

        connected = client.wait_until_connected(5000)
        with pipeline_state["lock"]:
            pipeline_state["connected"] = connected
        logger.info("Initial connection: {}".format("OK" if connected else "waiting"))

        # ----------------------------------------------------------------
        # Keep-alive loop: sleep 1 s, attempt reconnect every 10 s if down
        # ----------------------------------------------------------------
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
                    logger.info("Reconnecting...")
                    with pipeline_state["lock"]:
                        pipeline_state["connection_attempts"]     = attempts + 1
                        pipeline_state["last_connection_attempt"] = now
                    try:
                        client_ref.refresh()
                    except Exception as e:
                        logger.error("Refresh failed: {}".format(e))

        # Normal exit (should_run was set to False)
        logger.info("Thread: should_run=False, exiting cleanly")

    except Exception as e:
        crash_reason = "{}: {}".format(type(e).__name__, e)
        logger.critical("Thread CRASHED: {}".format(crash_reason))
        import traceback
        traceback.print_exc()

        # Record crash info in shared state so the watchdog / UI can see it
        with pipeline_state["lock"]:
            pipeline_state["thread_crash_count"]      += 1
            pipeline_state["thread_last_crash_reason"] = crash_reason
            pipeline_state["thread_last_crash_time"]   = time.time()

    finally:
        # Always mark as disconnected when this thread stops
        with pipeline_state["lock"]:
            pipeline_state["connected"] = False
            pipeline_state["connected_services"].clear()

        # Best-effort client stop
        try:
            with pipeline_state["lock"]:
                cli = pipeline_state.get("client")
            if cli:
                cli.stop()
        except Exception:
            pass

        if crash_reason:
            logger.info("Thread exiting after crash: {}".format(crash_reason))
        else:
            logger.info("Thread exiting")


# ============================================================================
# LOADCELL CONFIG -- RECEIVE FROM ANOTHER CLIENT
# ============================================================================

def _handle_received_loadcell_config(cfg):
    """Validate, persist to DB, and save a loadcell_config received from
    another pipeline client.

    Steps:
      1. Parse cfg.value as JSON
      2. Validate load_cells[0].name matches a device in our DB -- reject if not
      3. Extract raw_filters, weight_filters, levels + optional hardware fields
      4. UPDATE loadcell_device row in DB
      5. Update in-memory pipeline_state
    """
    logger.info("[LC-RX] Processing received loadcell_config v{}".format(cfg.version))

    # 1. Parse
    try:
        received = json.loads(cfg.value)
    except Exception as parse_err:
        logger.info("[LC-RX] REJECTED -- could not parse JSON: {}".format(parse_err))
        return

    load_cells = received.get("load_cells", [])
    if not load_cells:
        logger.info("[LC-RX] REJECTED -- no load_cells array in received config")
        return

    received_name = load_cells[0].get("name", "").strip()
    if not received_name:
        logger.info("[LC-RX] REJECTED -- load_cells[0].name is empty")
        return

    # 2. Validate device name against DB
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name FROM loadcell_device WHERE name = ? LIMIT 1",
            (received_name,)
        )
        row = cursor.fetchone()
    except Exception as db_err:
        logger.info("[LC-RX] REJECTED -- DB error during validation: {}".format(db_err))
        try:
            conn.close()
        except Exception:
            pass
        return

    if not row:
        try:
            cursor.execute("SELECT name FROM loadcell_device")
            known = [r["name"] for r in cursor.fetchall()]
        except Exception:
            known = ["<db error>"]
        conn.close()
        logger.info("[LC-RX] REJECTED -- received device '{}' not in DB. Known: {}".format(
            received_name, known))
        return

    device_id   = row["id"]
    device_name = row["name"]
    logger.info("[LC-RX] Device matched: '{}' (id={})".format(device_name, device_id))

    # 3. Extract fields
    lc             = load_cells[0]
    filter_block   = lc.get("filter", {})
    raw_filters    = [dict(f, enabled=True) for f in filter_block.get("raw", [])]
    weight_filters = [dict(f, enabled=True) for f in filter_block.get("weight", [])]
    levels_list    = lc.get("levels", {}).get("parameters", {}).get("ratios", [])
    levels_out     = [dict(lv, enabled=True) for lv in levels_list]

    dev_params       = lc.get("device", {}).get("parameters", {})
    tare_offset      = lc.get("tare", {}).get("parameters", {}).get("offset_raw")
    calib_params     = lc.get("calibration", {}).get("parameters", {})
    _rw_d            = calib_params.get("ref_weight", {})
    _rw_unit         = _rw_d.get("unit", "kg") if isinstance(_rw_d, dict) else "kg"
    _rw_value        = _rw_d.get("value", 0.0) if isinstance(_rw_d, dict) else float(_rw_d or 0)
    known_weight, _  = _normalise_to_kg(_rw_value, _rw_unit)
    if known_weight != _rw_value:
        logger.info("[LC-RX] Normalised known_weight {} {} -> {} kg".format(_rw_value, _rw_unit, known_weight))
    known_weight_raw = calib_params.get("ref_raw")
    poll_ms          = dev_params.get("poll_ms")

    ipc_params = {}
    for ipc in received.get("ipc", []):
        if ipc.get("type") == "pipeline":
            ipc_params = ipc.get("parameters", {})
            break
    pipeline_server = ipc_params.get("server")
    pipeline_port   = ipc_params.get("port")

    log_level = None
    for log in received.get("logging", []):
        log_level = log.get("parameters", {}).get("level")
        break

    # 4. Persist to DB -- only write columns we actually received
    fields = [
        "raw_filters = ?",
        "weight_filters = ?",
        "levels = ?",
    ]
    values = [
        json.dumps(raw_filters),
        json.dumps(weight_filters),
        json.dumps(levels_out),
    ]
    for col, val in [
        ("tare_offset",      tare_offset),
        ("known_weight",     known_weight),
        ("known_weight_raw", known_weight_raw),
        ("pipeline_server",  pipeline_server),
        ("pipeline_port",    pipeline_port),
        ("log_level",        log_level),
        ("poll_ms",          poll_ms),
        ("unit",             "kg"),   # always normalise unit to kg in DB
    ]:
        if val is not None:
            fields.append("{} = ?".format(col))
            values.append(val)

    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(device_id)

    try:
        cursor.execute(
            "UPDATE loadcell_device SET {} WHERE id = ?".format(", ".join(fields)),
            values
        )
        conn.commit()
        logger.info("[LC-RX] DB updated for '{}' -- {} field(s) written".format(
            device_name, len(fields) - 1))
    except Exception as update_err:
        logger.info("[LC-RX] DB update error: {}".format(update_err))
    finally:
        conn.close()

    # 5. Update in-memory state
    with pipeline_state["lock"]:
        pipeline_state["loadcell_config"]         = cfg.value
        pipeline_state["loadcell_config_version"] = cfg.version

    logger.info("[LC-RX] Done -- loadcell_config v{} accepted".format(cfg.version))


def start_pipeline_background(app=None):
    """Start (or restart) the pipeline background thread."""
    if not PIPELINE_AVAILABLE:
        logger.warning("Cannot start -- ilx_pipeline not available")
        return

    with pipeline_state["lock"]:
        existing = pipeline_state.get("background_thread")
        if existing and existing.is_alive():
            logger.info("Background thread already running")
            return
        # Thread is dead or never started -- reset run flag and start fresh
        pipeline_state["should_run"]                 = True
        pipeline_state["connected"]                  = False
        pipeline_state["connected_services"]         = set()

    # Capture the main event loop so the thread can schedule coroutines
    try:
        main_loop = asyncio.get_event_loop()
        with pipeline_state["lock"]:
            pipeline_state["main_loop"] = main_loop
    except Exception as e:
        logger.error("Could not capture main loop: {}".format(e))

    thread = threading.Thread(
        target=_run_pipeline_thread,
        args=("127.0.0.1", 7000),
        daemon=True,
        name="PipelineThread",
    )
    thread.start()

    with pipeline_state["lock"]:
        pipeline_state["background_thread"] = thread

    logger.info("Background thread started")
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

    # Signal existing thread to stop, then wait briefly for it to exit
    with pipeline_state["lock"]:
        pipeline_state["should_run"] = False
    await asyncio.sleep(1)

    # Clear stale connection state
    with pipeline_state["lock"]:
        pipeline_state["should_run"] = True
        pipeline_state["connected"] = False
        pipeline_state["connected_services"].clear()

    try:
        main_loop = asyncio.get_event_loop()
        with pipeline_state["lock"]:
            pipeline_state["main_loop"] = main_loop
    except Exception:
        pass

    thread = threading.Thread(
        target=_run_pipeline_thread,
        args=(host, port),
        daemon=True,
        name="PipelineThread",
    )
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
        pipeline_state["loadcell_raw"]                = None
        pipeline_state["loadcell_raw_dp"]             = None
        pipeline_state["modbus_config"]              = None
        pipeline_state["loadcell_config"]            = None
        pipeline_state["iot_gateway_config"]         = None
        pipeline_state["connected_services"].clear()
        pipeline_state["subscribed_datapoints"].clear()
        pipeline_state["modbus_config_pending"]      = None
        pipeline_state["loadcell_config_pending"]    = None
        pipeline_state["iot_gateway_config_pending"] = None

    logger.info("Disconnected")
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

        thread = pipeline_state.get("background_thread")
        return web.json_response({
            "connected":               pipeline_state["connected"],
            "load_raw":                pipeline_state["loadcell_raw"],
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
            # Thread health info
            "thread_alive":            thread.is_alive() if thread else False,
            "thread_crash_count":      pipeline_state["thread_crash_count"],
            "thread_last_crash":       pipeline_state["thread_last_crash_reason"],
            "thread_last_crash_time":  pipeline_state["thread_last_crash_time"],
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
        thread = pipeline_state.get("background_thread")
        out["thread_alive"] = thread.is_alive() if thread else False
        return web.json_response(out)

# ============================================================================
# WEBSOCKET -- live datapoint stream
# ============================================================================

async def pipeline_loadraw_ws_handler(request):
    """WS /ws/pipeline/load_raw -- streams live load-cell datapoints (load_raw, weight, etc.)

    loadcell_config is NOT sent here; it is served separately via
    GET /api/pipeline/loadcell-config (REST) because it is configuration,
    not a live data stream.
    """
    user = ws_auth(request)
    if user is None:
        return web.Response(status=401, text="Unauthorized")

    ws = web.WebSocketResponse()
    await ws.prepare(request)
    pipeline_state["ws_clients"].add(ws)
    logger.debug("WS client connected (total={})".format(len(pipeline_state["ws_clients"])))

    with pipeline_state["lock"]:
        raw    = pipeline_state["loadcell_raw"]
        raw_dp = pipeline_state["loadcell_raw_dp"]
        mcfg   = pipeline_state["modbus_config"]

    async def _send(payload):
        try:
            await ws.send_str(json.dumps(payload))
        except Exception:
            pass

    # Push current raw value immediately on connect so the UI doesn't
    # have to wait for the next update tick.
    if raw is not None and raw_dp is not None:
        await _send({"datapoint": raw_dp, "value": raw})

    # Modbus config summary is still useful for the live dashboard.
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

    # loadcell_config is intentionally NOT pushed here.
    # Fetch it via GET /api/pipeline/loadcell-config when needed.

    try:
        while True:
            msg = await ws.receive()
            if msg.type == MsgType.close:
                break
    except Exception as e:
        logger.error("WS error: {}".format(e))
    finally:
        pipeline_state["ws_clients"].discard(ws)
        logger.debug("WS client disconnected")

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
# LOADCELL -- JSON IMPORT  (POST /api/pipeline/loadcell-config/import)
# ============================================================================

# ============================================================================
# UNIT NORMALISATION HELPER
# ============================================================================

def _normalise_to_kg(value, unit):
    """Convert a weight value to kg and return (value_kg, 'kg').

    Handles common variants:
      g / gram / grams   -> divide by 1000
      t / tonne / tonnes -> multiply by 1000
      lb / lbs / pound   -> multiply by 0.453592
      kg / kilogram etc  -> no change
    If the unit is unrecognised, the value is returned unchanged with unit 'kg'
    (safe default -- caller should log a warning if needed).
    """
    if not unit:
        return float(value), "kg"
    u = unit.strip().lower()
    v = float(value)
    if u in ("g", "gram", "grams"):
        return v / 1000.0, "kg"
    if u in ("t", "tonne", "tonnes", "metric ton", "metric tons"):
        return v * 1000.0, "kg"
    if u in ("lb", "lbs", "pound", "pounds"):
        return v * 0.453592, "kg"
    # kg / kilogram / kilograms / kgs / anything else -> treat as kg
    return v, "kg"


async def pipeline_loadcell_import_handler(request):
    """POST /api/pipeline/loadcell-config/import

    Accepts an inno_load-style JSON body, upserts each entry in
    load_cells[] into the loadcell_device table, then returns a
    summary of created / updated rows.
    """
    logger.info("\n" + "="*70)
    logger.info("[LC-IMPORT] Loadcell JSON import handler called")
    logger.info("=" * 70)

    try:
        body = await request.json()
    except Exception as e:
        return web.json_response({"success": False, "error": "Invalid JSON: {}".format(e)}, status=400)

    load_cells = body.get("load_cells", [])
    if not load_cells:
        return web.json_response({"success": False, "error": "No load_cells[] array found in JSON"}, status=400)

    created      = 0
    updated      = 0
    device_names = []
    errors       = []

    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        for lc in load_cells:
            name = lc.get("name", "").strip()
            if not name:
                errors.append("Skipped entry with no name")
                continue

            device_names.append(name)

            dev_params   = (lc.get("device") or {}).get("parameters") or {}
            channels     = dev_params.get("channels") or []
            device_path  = channels[0].get("path", "") if channels else dev_params.get("path", "")

            poll_ms         = dev_params.get("poll_ms",         10)
            resolution_bits = dev_params.get("resolution_bits", 24)
            effective_bits  = dev_params.get("effective_bits",  14)
            signed          = int(bool(dev_params.get("signed", False)))
            gain            = dev_params.get("gain",  1)
            vref            = dev_params.get("vref",  5)
            raw_min         = dev_params.get("raw_min", 0)
            raw_max         = dev_params.get("raw_max", 16383)

            specs     = lc.get("specifications") or {}
            cap       = specs.get("capacity") or {}
            cap_min_d = cap.get("min") or {}
            cap_max_d = cap.get("max") or {}

            # Normalise capacity to kg regardless of what unit the imported JSON uses
            raw_unit     = cap_max_d.get("unit") or cap_min_d.get("unit") or "kg"
            capacity_min, unit = _normalise_to_kg(cap_min_d.get("value", 0),    raw_unit)
            capacity_max, _    = _normalise_to_kg(cap_max_d.get("value", 1000), raw_unit)
            unit = "kg"  # always store as kg -- values already converted above

            tare_params  = (lc.get("tare") or {}).get("parameters") or {}
            tare_offset  = tare_params.get("offset_raw", tare_params.get("offset", 0.0))

            cal_params   = (lc.get("calibration") or {}).get("parameters") or {}
            ref_weight_d = cal_params.get("ref_weight") or {}
            # Normalise known_weight to kg using the unit declared inside ref_weight
            _rw_unit     = ref_weight_d.get("unit", raw_unit) if isinstance(ref_weight_d, dict) else raw_unit
            _rw_value    = ref_weight_d.get("value", 0.0)     if isinstance(ref_weight_d, dict) else float(ref_weight_d or 0)
            known_weight, _ = _normalise_to_kg(_rw_value, _rw_unit)
            known_weight_raw = cal_params.get("ref_raw", 0.0)
            if known_weight != _rw_value:
                logger.info("[LC-IMPORT] Normalised known_weight {} {} -> {} kg".format(
                    _rw_value, _rw_unit, known_weight))
            if raw_unit.lower().strip() not in ("kg", "kilogram", "kilograms", "kgs"):
                logger.info("[LC-IMPORT] Normalised capacity {}/{} {} -> {}/{} kg".format(
                    cap_min_d.get("value", 0), cap_max_d.get("value", 1000), raw_unit,
                    capacity_min, capacity_max))

            filters_d      = lc.get("filter") or {}
            raw_filters    = json.dumps(filters_d.get("raw",    []))
            weight_filters = json.dumps(filters_d.get("weight", []))

            levels_cfg = lc.get("levels") or {}
            if isinstance(levels_cfg, dict):
                lvl_params = levels_cfg.get("parameters") or {}
                levels_list = lvl_params.get("ratios", lvl_params.get("levels", []))
            elif isinstance(levels_cfg, list):
                levels_list = levels_cfg
            else:
                levels_list = []
            levels = json.dumps(levels_list)

            pipeline_server = "127.0.0.1"
            pipeline_port   = 7000
            for ipc in body.get("ipc", []):
                p = (ipc.get("parameters") or {})
                if p.get("server"):   pipeline_server = p["server"]
                if p.get("port"):     pipeline_port   = int(p["port"])

            cursor.execute("SELECT id FROM loadcell_device WHERE name = ?", (name,))
            existing = cursor.fetchone()

            if existing:
                cursor.execute('''
                    UPDATE loadcell_device SET
                        device_path      = ?,
                        poll_ms          = ?,
                        resolution_bits  = ?,
                        effective_bits   = ?,
                        signed           = ?,
                        gain             = ?,
                        vref             = ?,
                        raw_min          = ?,
                        raw_max          = ?,
                        capacity_min     = ?,
                        capacity_max     = ?,
                        unit             = ?,
                        tare_offset      = ?,
                        known_weight     = ?,
                        known_weight_raw = ?,
                        raw_filters      = ?,
                        weight_filters   = ?,
                        levels           = ?,
                        pipeline_server  = ?,
                        pipeline_port    = ?,
                        updated_at       = CURRENT_TIMESTAMP
                    WHERE name = ?
                ''', (
                    device_path, poll_ms, resolution_bits, effective_bits,
                    signed, gain, vref, raw_min, raw_max,
                    capacity_min, capacity_max, unit,
                    tare_offset, known_weight, known_weight_raw,
                    raw_filters, weight_filters, levels,
                    pipeline_server, pipeline_port,
                    name
                ))
                updated += 1
                logger.info("[LC-IMPORT] Updated device '{}'".format(name))
            else:
                import uuid
                new_id = str(uuid.uuid4())
                cursor.execute('''
                    INSERT INTO loadcell_device (
                        id, name,
                        device_path, poll_ms, resolution_bits, effective_bits,
                        signed, gain, vref, raw_min, raw_max,
                        capacity_min, capacity_max, unit,
                        tare_offset, known_weight, known_weight_raw,
                        raw_filters, weight_filters, levels,
                        pipeline_server, pipeline_port,
                        enabled
                    ) VALUES (
                        ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?,
                        1
                    )
                ''', (
                    new_id, name,
                    device_path, poll_ms, resolution_bits, effective_bits,
                    signed, gain, vref, raw_min, raw_max,
                    capacity_min, capacity_max, unit,
                    tare_offset, known_weight, known_weight_raw,
                    raw_filters, weight_filters, levels,
                    pipeline_server, pipeline_port
                ))
                created += 1
                logger.info("[LC-IMPORT] Created device '{}' id={}".format(name, new_id))

        conn.commit()
        conn.close()

    except Exception as db_err:
        logging.error("[LC-IMPORT] DB error: %s", db_err)
        return web.json_response({"success": False, "error": "DB error: {}".format(db_err)}, status=500)

    logger.info("[LC-IMPORT] Done -- created={} updated={} devices={}".format(created, updated, device_names))
    return web.json_response({
        "success":      True,
        "device_names": device_names,
        "created":      created,
        "updated":      updated,
        "errors":       errors,
    })


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

def _build_multi_loadcell_config(device_rows, source="auto_send"):
    """Internal helper to build a v2 config for ALL enabled devices in device_rows."""
    new_version = get_next_pipeline_version("loadcell")

    def _parse_json_col(val):
        if not val: return []
        if isinstance(val, list): return val
        try: return json.loads(val)
        except: return []

    def _active(arr):
        return [{"type": f["type"], "parameters": f["parameters"]}
                for f in arr if f.get("enabled", True)]

    load_cells_list = []
    for r in device_rows:
        r = dict(r)
        raw_filters    = _parse_json_col(r.get("raw_filters"))
        weight_filters = _parse_json_col(r.get("weight_filters"))
        levels         = _parse_json_col(r.get("levels"))

        active_raw    = _active(raw_filters)
        active_weight = _active(weight_filters)
        active_levels = [{"name": lv["name"], "ratio": lv["ratio"]}
                         for lv in levels if lv.get("enabled", True)]

        _db_unit = r.get("unit") or "kg"
        _cap_min_kg, _ = _normalise_to_kg(r.get("capacity_min") or 0,    _db_unit)
        _cap_max_kg, _ = _normalise_to_kg(r.get("capacity_max") or 1000, _db_unit)
        _kw_kg,      _ = _normalise_to_kg(r.get("known_weight") or 0,    _db_unit)

        lc_entry = {
            "name": r["name"],
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
            "specifications": {
                "capacity": {
                    "min": {"value": _cap_min_kg, "unit": "kg"},
                    "max": {"value": _cap_max_kg, "unit": "kg"},
                }
            },
            "levels":      {"type": "ratio", "parameters": {"ratios": active_levels}},
            "tare":        {"type": "manual", "parameters": {"offset_raw": r.get("tare_offset") or 0.0}},
            "calibration": {"type": "single_point" if r.get("lc_mode") == "single_ended" else "differential", "parameters": {
                "ref_weight": {"value": _kw_kg, "unit": "kg"},
                "ref_raw":    r.get("known_weight_raw") or 0.0,
            }},
            "filter": {"raw": active_raw, "weight": active_weight}
        }
        load_cells_list.append(lc_entry)

    # Use network/ipc settings from the first device in the list
    first = dict(device_rows[0])
    return {
        "version":       2,
        "send_version":  new_version,
        "timestamp":     time.time(),
        "timestamp_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source":        source,
        "logging": [{"type": "console", "parameters": {"level": first.get("log_level") or "info"}}],
        "ipc": [{
            "type": "pipeline", "enabled": True,
            "parameters": {
                "server":       first.get("pipeline_server") or "127.0.0.1",
                "port":         first.get("pipeline_port") or 7000,
                "service_name": get_pipeline_service_name("loadcell") or "load_cell_service",
            }
        }],
        "load_cells": load_cells_list
    }, new_version

async def send_loadcell_config_now():
    """Build and send loadcell config for ALL enabled devices."""
    logger.info("\n" + "="*70)
    logger.info("[LC-CFG] Auto-Send: Building config for all enabled devices")
    logger.info("=" * 70)
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM loadcell_device WHERE enabled = 1
        ''')
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            msg = "No enabled loadcell devices found"
            logger.info("[LC-CFG] " + msg)
            return {"success": False, "error": msg}

        config, new_version = _build_multi_loadcell_config(rows, source="auto_send")

        config_json = json.dumps(config, indent=2)
        _lc_list  = config.get("load_cells", [])
        _first_lc = _lc_list[0] if _lc_list else {}
        _filt     = _first_lc.get("filter", {})
        _n_raw    = len(_filt.get("raw", []))
        _n_weight = len(_filt.get("weight", []))
        _n_levels = len((_first_lc.get("levels") or {}).get("parameters", {}).get("ratios", []))
        logger.info("[LC-CFG] Built v{}: raw={} weight={} levels={}".format(
            new_version, _n_raw, _n_weight, _n_levels))

        pipeline_sent    = False
        pipeline_message = "Queued as pending (not connected)"
        target_service   = None

        with pipeline_state["lock"]:
            client    = pipeline_state.get("client")
            connected = pipeline_state.get("connected", False)

        if connected and client:
            target_service = _find_loadcell_service()
            if target_service:
                try:
                    ok = client.publish_config(Config(
                        name    = get_pipeline_config_name("loadcell"),
                        value   = config_json,
                        version = new_version,
                        service = target_service,
                    ))
                    if ok:
                        pipeline_sent    = True
                        pipeline_message = "Sent to {} (v{})".format(target_service, new_version)
                        record_pipeline_send_success("loadcell", new_version, target_service, pipeline_message)
                        _mark_sent("loadcell", new_version)
                        with pipeline_state["lock"]:
                            pipeline_state["loadcell_config"]         = config_json
                            pipeline_state["loadcell_config_pending"] = None
                    else:
                        pipeline_message = "publish_config failed -- queued as pending"
                        record_pipeline_send_failure("loadcell", pipeline_message)
                        _clear_sent("loadcell")
                        with pipeline_state["lock"]:
                            pipeline_state["loadcell_config_pending"] = config_json
                            pipeline_state["loadcell_config_version"] = new_version
                except Exception as exc:
                    pipeline_message = "Error: {} -- queued as pending".format(exc)
                    record_pipeline_send_failure("loadcell", pipeline_message)
                    _clear_sent("loadcell")
                    with pipeline_state["lock"]:
                        pipeline_state["loadcell_config_pending"] = config_json
                        pipeline_state["loadcell_config_version"] = new_version
            else:
                pipeline_message = "Service '{}' not connected -- queued as pending".format(
                    get_pipeline_service_name("loadcell") or "load_cell_service")
                record_pipeline_send_failure("loadcell", pipeline_message)
                _clear_sent("loadcell")
                with pipeline_state["lock"]:
                    pipeline_state["loadcell_config_pending"] = config_json
                    pipeline_state["loadcell_config_version"] = new_version
        else:
            record_pipeline_send_failure("loadcell", pipeline_message)
            _clear_sent("loadcell")
            with pipeline_state["lock"]:
                pipeline_state["loadcell_config_pending"] = config_json
                pipeline_state["loadcell_config_version"] = new_version
        logger.info("[LC-CFG] " + pipeline_message)

        return {
            "success":               True,
            "pipeline_sent":         pipeline_sent,
            "pipeline_message":      pipeline_message,
            "target_service":        target_service,
            "version":               new_version,
            "active_raw_filters":    _n_raw,
            "active_weight_filters": _n_weight,
            "active_levels":         _n_levels,
        }
    except Exception as e:
        logging.error("send_loadcell_config_now error: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}


async def pipeline_filters_post_handler(request):
    """POST /api/pipeline/filters"""
    logger.info("\n" + "="*70)
    logger.info("[LC-CFG] Save Filters & Levels  ->  Build  ->  Send")
    logger.info("=" * 70)

    try:
        body = await request.json()
        device_id = body.get("device_id")
        if not device_id:
            return web.json_response({"success": False, "error": "device_id required"})

        raw_filters    = body.get("raw_filters", [])
        weight_filters = body.get("weight_filters", [])
        levels         = body.get("levels", [])

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

        # If save_only is requested, we stop here.
        if body.get("save_only"):
            return web.json_response({
                "success":          True,
                "pipeline_sent":    False,
                "pipeline_message": "Saved to database only."
            })

        # Build and send config for ALL enabled devices
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM loadcell_device WHERE enabled = 1")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return web.json_response({"success": False, "error": "No enabled devices found for config build."})

        config, new_version = _build_multi_loadcell_config(rows, source="web_ui")

        config_json = json.dumps(config, indent=2)
        _lc_list  = config.get("load_cells", [])
        _first_lc = _lc_list[0] if _lc_list else {}
        _filt     = _first_lc.get("filter", {})
        _n_raw    = len(_filt.get("raw", []))
        _n_weight = len(_filt.get("weight", []))
        _n_levels = len((_first_lc.get("levels") or {}).get("parameters", {}).get("ratios", []))
        logger.info("[LC-CFG] Built v{}: raw={} weight={} levels={}".format(
            new_version, _n_raw, _n_weight, _n_levels))

        # Warn if known_weight_raw is 0 while known_weight is set -- calibration likely
        # not performed yet or the raw was not captured before saving.
        _first_row = dict(rows[0])
        _kw  = _first_row.get("known_weight") or 0
        _kwr = _first_row.get("known_weight_raw") or 0.0
        if float(_kw) != 0.0 and float(_kwr) == 0.0:
            logger.warning("[LC-CFG] WARNING: known_weight={} but known_weight_raw=0 -- "                  "calibration raw value missing! ref_raw will be 0 in sent config.".format(_kw))

        pipeline_sent    = False
        pipeline_message = "Not sent -- pipeline not connected"
        target_service   = None

        with pipeline_state["lock"]:
            client    = pipeline_state.get("client")
            connected = pipeline_state.get("connected", False)

        if connected and client:
            target_service = _find_loadcell_service()
            logger.info("[LC-CFG] Target service: {}".format(target_service))

            if target_service:
                try:
                    cfg_obj = Config(
                        name=get_pipeline_config_name("loadcell"),
                        value=config_json,
                        version=new_version,
                        service=target_service,
                    )
                    ok = client.publish_config(cfg_obj)
                    logger.info("[LC-CFG] publish_config -> ok={}".format(ok))
                    if ok:
                        pipeline_sent    = True
                        pipeline_message = "Sent to {} (v{})".format(target_service, new_version)
                        record_pipeline_send_success("loadcell", new_version, target_service, pipeline_message)
                        with pipeline_state["lock"]:
                            pipeline_state["loadcell_config"]         = config_json
                            pipeline_state["loadcell_config_pending"] = None
                        logger.info("[LC-CFG] " + pipeline_message)

                        # Request and subscribe to all datapoints for all devices
                        with pipeline_state["lock"]:
                            raw_toggle_on = pipeline_state.get("load_raw_enabled", False)
                        for lc_entry in config.get("load_cells", []):
                            device_name = lc_entry.get("name")
                            if device_name:
                                try:
                                    client.datapoint_update(target_service, device_name, '{}')
                                except: pass

                                mapped_datapoints = [
                                    "loadcells.{}.weight_kg".format(device_name),
                                    "loadcells.{}.unit".format(device_name),
                                    "loadcells.{}.known_weight_kg".format(device_name),
                                    "loadcells.{}.known_raw".format(device_name),
                                    "loadcells.{}.tared".format(device_name),
                                    "loadcells.{}.calibrated".format(device_name),
                                    "loadcells.{}.capacity".format(device_name),
                                ]
                                # Only subscribe to raw if the Raw toggle is currently ON
                                raw_dp = "loadcells.{}.raw".format(device_name)
                                if raw_toggle_on:
                                    mapped_datapoints.append(raw_dp)
                                else:
                                    logger.info("[LC-CFG] Skipping raw subscribe (toggle OFF): '{}'".format(raw_dp))
                                if hasattr(client, 'subscribe'):
                                    for dp in mapped_datapoints:
                                        try:
                                            client.subscribe(dp)
                                        except: pass
                                    with pipeline_state["lock"]:
                                        pipeline_state["subscribed_datapoints"].update(mapped_datapoints)
                    else:
                        pipeline_message = "publish_config failed -- queued as pending"
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
                logger.info("[LC-CFG] " + pipeline_message)
        else:
            pipeline_message = "Queued as pending (not connected)"
            record_pipeline_send_failure("loadcell", pipeline_message)
            with pipeline_state["lock"]:
                pipeline_state["loadcell_config_pending"] = config_json
            logger.info("[LC-CFG] " + pipeline_message)

        return web.json_response({
            "success":               True,
            "pipeline_sent":         pipeline_sent,
            "pipeline_message":      pipeline_message,
            "target_service":        target_service,
            "version":               new_version,
            "active_raw_filters":    _n_raw,
            "active_weight_filters": _n_weight,
            "active_levels":         _n_levels,
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
    Builds modbus_config.json from external_device (ext-rtu / ext-tcp)
    and their external_datapoints, then sends via pipeline.
    """
    logger.info("\n" + "="*70)
    logger.info("[MODBUS-CFG] Save Modbus Configuration  ->  Build  ->  Send")
    logger.info("=" * 70)

    if not PIPELINE_AVAILABLE:
        return web.json_response({"success": False, "error": "ilx_pipeline not available"})

    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Read enabled external devices that use Modbus (ext-rtu or ext-tcp)
        cursor.execute('''
            SELECT
                ed.id          AS tag_id,
                ed.device_id,
                ed.name        AS tag_name,
                ed.slave_id,
                ed.register_address,
                ed.register_type,
                ed.data_type,
                ed.byte_order,
                ed.word_order,
                ed.scale_factor,
                ed.offset,
                ed.unit,
                ed.writable,
                1   AS retry_count,
                100 AS timeout_ms,
                1   AS register_count,
                e.name          AS device_name,
                e.protocol      AS ext_protocol,
                e.serial_port,
                e.baud_rate,
                e.parity,
                e.data_bits,
                e.stop_bits,
                e.ip_address,
                e.port,
                e.slave_id          AS device_slave_id,
                e.response_timeout_ms,
                e.byte_timeout_ms,
                e.max_retries,
                e.polling_interval_ms
            FROM external_datapoints ed
            JOIN external_device e ON ed.device_id = e.id
            WHERE ed.enabled = 1
              AND e.enabled  = 1
              AND e.protocol IN ('ext-rtu', 'ext-tcp')
            ORDER BY ed.device_id, ed.slave_id
        ''')
        rows = cursor.fetchall()
        conn.close()

        logger.info("[MODBUS-CFG] {} tags from external_datapoints".format(len(rows)))
        if not rows:
            return web.json_response({
                "success": False,
                "error": "No Modbus tags found — add tags to External devices with Modbus RTU or TCP protocol"
            })

        connection_map = {}
        assets = []

        for row in rows:
            r      = dict(row)
            dev_id = r['device_id']
            name   = r['device_name'] or str(dev_id)
            proto  = r['ext_protocol'] or 'ext-rtu'
            is_tcp = 'tcp' in proto

            if dev_id not in connection_map:
                if is_tcp:
                    connection_map[dev_id] = {
                        "id":                name,
                        "type":              "tcp",
                        "host":              r.get('ip_address') or '127.0.0.1',
                        "port":              r.get('port') or 502,
                        "responseTimeoutMs": r.get('response_timeout_ms') or 100,
                        "byteTimeoutMs":     r.get('byte_timeout_ms') or 100,
                        "maxRetries":        r.get('max_retries') or 2,
                        "pollingIntervalMs": r.get('polling_interval_ms') or 300,
                    }
                else:
                    connection_map[dev_id] = {
                        "id":                name,
                        "type":              "rtu",
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

            assets.append({
                "name":          r['tag_name'],
                "connection_id": name,
                "slaveId":       r['slave_id'] or r.get('device_slave_id') or 1,
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
            })

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
        logger.info("[MODBUS-CFG] Built v{}: {} connections, {} assets".format(
            new_version, len(connection_map), len(assets)))

        pipeline_sent    = False
        pipeline_message = "Not sent -- pipeline not connected"
        target_service   = None

        with pipeline_state["lock"]:
            client    = pipeline_state.get("client")
            connected = pipeline_state.get("connected", False)

        logger.info("[MODBUS-CFG] Pipeline connected={}, client={}".format(connected, client is not None))

        if connected and client:
            target_service = _find_modbus_service()
            configured_name = get_pipeline_service_name("modbus")
            with pipeline_state["lock"]:
                active_services = list(pipeline_state.get("connected_services", set()))
            logger.info("[MODBUS-CFG] configured service_name='{}', target_service={}, connected_services={}".format(
                configured_name, target_service, active_services))

            if not target_service:
                # No service name configured or service not yet seen -- queue and log clearly
                pipeline_message = (
                    "Modbus service '{}' not found in connected services {} -- queued as pending. "
                    "Set the correct service name in Admin -> Pipeline Targets.".format(
                        configured_name or "<not configured>", active_services)
                )
                logger.info("[MODBUS-CFG] " + pipeline_message)
                record_pipeline_send_failure("modbus", pipeline_message)
                with pipeline_state["lock"]:
                    pipeline_state["modbus_config_pending"] = config_json
            else:
                try:
                    rid = client.datapoint_update(target_service, get_pipeline_config_name("modbus"), config_json)
                    logger.info("[MODBUS-CFG] datapoint_update rid={}".format(rid))
                    if rid > 0:
                        pipeline_sent    = True
                        pipeline_message = "Sent to '{}' (v{})".format(target_service, new_version)
                        logger.info("[MODBUS-CFG] " + pipeline_message)
                        record_pipeline_send_success("modbus", new_version, target_service, pipeline_message)
                        with pipeline_state["lock"]:
                            pipeline_state["modbus_config"]         = config_json
                            pipeline_state["modbus_config_pending"] = None
                        _mark_sent("modbus", new_version)
                    else:
                        pipeline_message = "Send failed (rid=0) -- queued as pending"
                        logger.info("[MODBUS-CFG] " + pipeline_message)
                        record_pipeline_send_failure("modbus", pipeline_message)
                        with pipeline_state["lock"]:
                            pipeline_state["modbus_config_pending"] = config_json
                except Exception as exc:
                    pipeline_message = "Error: {} -- queued as pending".format(exc)
                    logger.info("[MODBUS-CFG] " + pipeline_message)
                    import traceback; traceback.print_exc()
                    record_pipeline_send_failure("modbus", pipeline_message)
                    with pipeline_state["lock"]:
                        pipeline_state["modbus_config_pending"] = config_json
        else:
            with pipeline_state["lock"]:
                pipeline_state["modbus_config_pending"] = config_json
            pipeline_message = "Queued as pending (pipeline not connected)"
            record_pipeline_send_failure("modbus", pipeline_message)
            logger.info("[MODBUS-CFG] " + pipeline_message)

        return web.json_response({
            "success":          True,
            "pipeline_sent":    pipeline_sent,
            "pipeline_message": pipeline_message,
            "target_service":   target_service,
            "version":          new_version,
            "connections":      len(connection_map),
            "assets":           len(assets),
        })

    except Exception as e:
        logger.error("[MODBUS-CFG] Error: {}".format(e))
        import traceback
        traceback.print_exc()
        return web.json_response({"success": False, "error": str(e)})
async def send_modbus_config_now():
    """Build and send the modbus config directly (no HTTP request needed)."""
    class _FakeRequest:
        pass
    resp = await pipeline_save_modbus_config(_FakeRequest())
    import json as _json
    try:
        raw = resp.body
        return _json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except Exception:
        return {"success": False, "error": "could not parse response"}
# Add to pipeline.py - new save endpoint that updates the latest config
async def pipeline_core_config_save_handler(request):
    """POST /api/pipeline/core-config/save
    Save core config JSON to the latest version in DB (overwrites, no version increment)
    Optionally send to pipeline.
    """
    logger.info("\n" + "="*70)
    logger.info("[CORE-CFG] Save JSON (update latest)")
    logger.info("=" * 70)

    try:
        body = await request.json()
    except Exception as e:
        return web.json_response({"success": False, "error": "Invalid JSON: {}".format(e)}, status=400)

    config_json = body.get('config_json', '')
    send_to_pipeline = body.get('send_to_pipeline', True)
    
    if not config_json:
        return web.json_response({"success": False, "error": "Missing config_json"}, status=400)
    
    # Validate JSON
    try:
        config = json.loads(config_json)
    except json.JSONDecodeError as e:
        return web.json_response({"success": False, "error": "Invalid JSON: {}".format(e)}, status=400)
    
    # Extract device names
    device_names = []
    if 'services' in config:
        for svc_name, svc_config in config['services'].items():
            if svc_name == 'modbus' and 'groups' in svc_config:
                for group in svc_config['groups']:
                    if 'members' in group:
                        device_names.extend(group['members'])
    
    service_name = config.get('service_name', 'ilx_craneiq_core')
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS core_configs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                version      INTEGER NOT NULL DEFAULT 1,
                device_names TEXT,
                service_name TEXT,
                config_json  TEXT NOT NULL,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Get the latest version
        cursor.execute('SELECT COALESCE(MAX(version), 0) FROM core_configs')
        latest_version = cursor.fetchone()[0]
        
        if latest_version == 0:
            # No existing config - insert new
            cursor.execute(
                'INSERT INTO core_configs (version, device_names, service_name, config_json) VALUES (?, ?, ?, ?)',
                (1, json.dumps(device_names), service_name, config_json)
            )
            new_version = 1
            logger.info("[CORE-CFG] Created first config version 1")
        else:
            # Update the latest config - keep same version
            cursor.execute(
                'UPDATE core_configs SET device_names = ?, service_name = ?, config_json = ?, created_at = CURRENT_TIMESTAMP WHERE version = ?',
                (json.dumps(device_names), service_name, config_json, latest_version)
            )
            new_version = latest_version
            logger.info("[CORE-CFG] Updated config v{}".format(new_version))
        
        conn.commit()
        conn.close()
        logger.info("[CORE-CFG] Saved to DB (v{})".format(new_version))
        
    except Exception as db_err:
        logging.error("[CORE-CFG] DB persist error: %s", db_err)
        return web.json_response({"success": False, "error": "DB error: {}".format(db_err)}, status=500)
    
    # Send to pipeline if requested
    pipeline_sent = False
    pipeline_message = "Not sent"
    target_service = None
    
    if send_to_pipeline:
        with pipeline_state["lock"]:
            client = pipeline_state.get("client")
            connected = pipeline_state.get("connected", False)
        
        if connected and client:
            target_service = _find_core_service()
            if target_service:
                try:
                    # Use the same version (no increment)
                    ok = client.publish_config(Config(
                        name=get_pipeline_config_name("core"),
                        value=config_json,
                        version=new_version,
                        service=target_service,
                    ))
                    if ok:
                        pipeline_sent = True
                        pipeline_message = "Sent to {} (v{})".format(target_service, new_version)
                        record_pipeline_send_success("core", new_version, target_service, pipeline_message)
                        with pipeline_state["lock"]:
                            pipeline_state["core_config"] = config_json
                            pipeline_state["core_config_pending"] = None
                    else:
                        pipeline_message = "publish_config failed -- queued as pending"
                        record_pipeline_send_failure("core", pipeline_message)
                        with pipeline_state["lock"]:
                            pipeline_state["core_config_pending"] = config_json
                except Exception as exc:
                    pipeline_message = "Error: {} -- queued as pending".format(exc)
                    record_pipeline_send_failure("core", pipeline_message)
                    with pipeline_state["lock"]:
                        pipeline_state["core_config_pending"] = config_json
            else:
                pipeline_message = "Service not connected -- queued as pending"
                record_pipeline_send_failure("core", pipeline_message)
                with pipeline_state["lock"]:
                    pipeline_state["core_config_pending"] = config_json
        else:
            pipeline_message = "Pipeline not connected -- queued as pending"
            record_pipeline_send_failure("core", pipeline_message)
            with pipeline_state["lock"]:
                pipeline_state["core_config_pending"] = config_json
    
    return web.json_response({
        "success": True,
        "pipeline_sent": pipeline_sent,
        "pipeline_message": pipeline_message,
        "target_service": target_service,
        "version": new_version,
        "device_names": device_names,
    })

async def pipeline_modbus_config_handler(request):
    """POST /api/pipeline/modbus-config -- legacy alias"""
    return await pipeline_save_modbus_config(request)

# ============================================================================
# IOT GATEWAY CONFIG -- BUILD + SAVE + SEND
# ============================================================================

async def send_iot_gateway_config_now():
    """Build iot_gateway config, save timestamped copy to disk, send via pipeline."""
    logger.info("\n" + "="*60)
    logger.info("[IOT-CFG] Build  ->  Save  ->  Send")
    logger.info("="*60)

    try:
        from mqtt_cloud import build_iot_gateway_config
        config = build_iot_gateway_config()
    except Exception as e:
        logger.error("[IOT-CFG] build error: {}".format(e))
        return {"success": False, "error": "build failed: {}".format(e)}

    new_version = get_next_pipeline_version("iot_gateway")
    # config["version"] is the schema/format version (2) set by build_iot_gateway_config()
    # new_version is the pipeline send counter -- stored separately so schema version is preserved
    config["send_version"] = new_version
    config_json = json.dumps(config, indent=2)
    logger.info("[IOT-CFG] Built v{}: {} server(s), {} mapping(s)".format(
        new_version, len(config.get("servers", {})), len(config.get("mappings", []))))

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
                ok = client.publish_config(Config(
                    name    = get_pipeline_config_name("iot_gateway"),
                    value   = config_json,
                    version = new_version,
                    service = target_service,
                ))
                if ok:
                    pipeline_sent    = True
                    pipeline_message = "Sent to {} (v{})".format(target_service, new_version)
                    record_pipeline_send_success("iot_gateway", new_version, target_service, pipeline_message)
                    with pipeline_state["lock"]:
                        pipeline_state["iot_gateway_config"]         = config_json
                        pipeline_state["iot_gateway_config_pending"] = None
                        pipeline_state["iot_gateway_config_version"] = new_version
                    logger.info("[IOT-CFG] " + pipeline_message)
                else:
                    pipeline_message = "publish_config failed -- queued as pending"
                    record_pipeline_send_failure("iot_gateway", pipeline_message)
                    with pipeline_state["lock"]:
                        pipeline_state["iot_gateway_config_pending"] = config_json
                        pipeline_state["iot_gateway_config_version"] = new_version
            except Exception as exc:
                pipeline_message = "Error: {} -- queued as pending".format(exc)
                record_pipeline_send_failure("iot_gateway", pipeline_message)
                with pipeline_state["lock"]:
                    pipeline_state["iot_gateway_config_pending"] = config_json
                    pipeline_state["iot_gateway_config_version"] = new_version
        else:
            pipeline_message = "Service '{}' not connected -- queued as pending".format(
                get_pipeline_service_name("iot_gateway") or "iot_gateway_service")
            record_pipeline_send_failure("iot_gateway", pipeline_message)
            with pipeline_state["lock"]:
                pipeline_state["iot_gateway_config_pending"] = config_json
                pipeline_state["iot_gateway_config_version"] = new_version
            logger.info("[IOT-CFG] " + pipeline_message)
    else:
        pipeline_message = "Queued as pending (not connected)"
        record_pipeline_send_failure("iot_gateway", pipeline_message)
        with pipeline_state["lock"]:
            pipeline_state["iot_gateway_config_pending"] = config_json
            pipeline_state["iot_gateway_config_version"] = new_version
        logger.info("[IOT-CFG] " + pipeline_message)

    return {
        "success":          True,
        "pipeline_sent":    pipeline_sent,
        "pipeline_message": pipeline_message,
        "target_service":   target_service,
        "version":          new_version,
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
# AUTO-SEND  -- fire immediately for all enabled targets
# ============================================================================

async def pipeline_auto_send_handler(request):
    """POST /api/pipeline/auto-send"""
    from database import get_enabled_pipeline_targets
    return await _do_auto_send()


async def _do_auto_send():
    """Core auto-send logic - reads enabled targets ordered by send_order from DB."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT config_type, service_name, send_order FROM pipeline_service_targets "
            "WHERE enabled = 1 ORDER BY send_order ASC, config_type ASC"
        )
        targets = [dict(r) for r in cursor.fetchall()]
        conn.close()
    except Exception as e:
        return web.json_response({"success": False, "error": "DB error: {}".format(e)})

    results = []
    for tgt in targets:
        cfg_type = tgt["config_type"]
        svc_name = tgt["service_name"]
        logger.info("[AUTO-SEND] order={} {} -> {}".format(
            tgt.get("send_order", "?"), cfg_type, svc_name or "(no service configured)"))
        try:
            if cfg_type == "modbus":
                class _FakeReq: pass
                resp = await pipeline_save_modbus_config(_FakeReq())
                import json as _j
                raw = resp.body
                d = _j.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            elif cfg_type == "loadcell":
                d = await send_loadcell_config_now()
            elif cfg_type == "iot_gateway":
                d = await send_iot_gateway_config_now()
            elif cfg_type == "core":
                # Always build fresh from rules DB -- never rely on a stored blob.
                # This ensures the loadcell datapoint names are always current
                # (auto-discovered from loadcell_device) and all enabled rules
                # are included, even on first boot when core_configs is empty.
                from rules import _build_and_send_core_config as _core_send
                _core_result = await _core_send()
                d = {
                    "success":          True,
                    "pipeline_sent":    _core_result.get("sent", False),
                    "pipeline_message": (
                        "Sent to {} (rules-built)".format(_core_result.get("service"))
                        if _core_result.get("sent")
                        else "Queued as pending (rules-built)"
                        if _core_result.get("pending")
                        else _core_result.get("error", "unknown")
                    ),
                    "version":          _core_result.get("version"),
                }
            else:
                d = {"success": False, "error": "unknown config_type"}

            results.append({
                "config_type":   cfg_type,
                "service_name":  svc_name,
                "send_order":    tgt.get("send_order", 0),
                "success":       d.get("success", False),
                "pipeline_sent": d.get("pipeline_sent", False),
                "version":       d.get("version"),
                "message":       d.get("pipeline_message") or d.get("error") or "",
            })
        except Exception as e:
            results.append({
                "config_type":   cfg_type,
                "service_name":  svc_name,
                "send_order":    tgt.get("send_order", 0),
                "success":       False,
                "pipeline_sent": False,
                "message":       str(e),
            })

    any_sent = any(r.get("pipeline_sent") for r in results)
    return web.json_response({
        "success":           True,
        "auto_sent":         any_sent,
        "results":           results,
        "targets_attempted": len(results),
    })


async def pipeline_save_send_order_handler(request):
    """POST /api/pipeline/auto-send/order
    Body: { "order": ["modbus", "loadcell", "iot_gateway", "core"] }
    Saves the send_order for each config_type in the DB.
    """
    try:
        body  = await request.json()
        order = body.get("order", [])
        if not isinstance(order, list):
            return web.json_response({"success": False, "error": "order must be a list"}, status=400)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        for idx, cfg_type in enumerate(order, start=1):
            cursor.execute(
                "UPDATE pipeline_service_targets SET send_order = ? WHERE config_type = ?",
                (idx, cfg_type)
            )
        conn.commit()
        conn.close()
        logger.info("[PIPELINE] Saved send order: {}".format(order))
        return web.json_response({"success": True, "order": order})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def pipeline_send_log_handler(request):
    """GET /api/pipeline/send-log"""
    from database import get_all_pipeline_send_logs
    logs = get_all_pipeline_send_logs()
    return web.json_response({"logs": logs})

# ============================================================================
# CORE CONFIG -- receive JSON upload, persist to DB, forward via pipeline
# ============================================================================

async def pipeline_core_config_upload_handler(request):
    """POST /api/pipeline/core-config/upload"""
    logger.info("\n" + "="*70)
    logger.info("[CORE-CFG] Upload  ->  Persist  ->  Send")
    logger.info("=" * 70)

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
        logger.info("[CORE-CFG] Persisted v{} to DB. Devices: {}".format(new_version, device_names))
    except Exception as db_err:
        logging.error("[CORE-CFG] DB persist error: %s", db_err)
        return web.json_response({"success": False, "error": "DB error: {}".format(db_err)}, status=500)

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
                ok = client.publish_config(Config(
                    name    = get_pipeline_config_name("core"),
                    value   = config_json,
                    version = new_version,
                    service = target_service,
                ))
                if ok:
                    pipeline_sent    = True
                    pipeline_message = "Sent to {} (v{})".format(target_service, new_version)
                    record_pipeline_send_success("core", new_version, target_service, pipeline_message)
                    with pipeline_state["lock"]:
                        pipeline_state["core_config"]         = config_json
                        pipeline_state["core_config_pending"] = None
                        pipeline_state["core_config_version"] = new_version
                else:
                    pipeline_message = "publish_config failed -- queued as pending"
                    record_pipeline_send_failure("core", pipeline_message)
                    with pipeline_state["lock"]:
                        pipeline_state["core_config_pending"] = config_json
                        pipeline_state["core_config_version"] = new_version
            except Exception as exc:
                pipeline_message = "Error: {} -- queued as pending".format(exc)
                record_pipeline_send_failure("core", pipeline_message)
                with pipeline_state["lock"]:
                    pipeline_state["core_config_pending"] = config_json
                    pipeline_state["core_config_version"] = new_version
        else:
            pipeline_message = "Service '{}' not connected -- queued as pending".format(
                get_pipeline_service_name("core") or "core_service")
            record_pipeline_send_failure("core", pipeline_message)
            with pipeline_state["lock"]:
                pipeline_state["core_config_pending"] = config_json
                pipeline_state["core_config_version"] = new_version
    else:
        pipeline_message = "Queued as pending (not connected)"
        record_pipeline_send_failure("core", pipeline_message)
        with pipeline_state["lock"]:
            pipeline_state["core_config_pending"] = config_json
            pipeline_state["core_config_version"] = new_version

    return web.json_response({
        "success":                True,
        "pipeline_sent":          pipeline_sent,
        "pipeline_message":       pipeline_message,
        "target_service":         target_service,
        "version":                new_version,
        "device_names":           device_names,
        "service_name_in_config": service_name_in_cfg,
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
                    ok = client.publish_config(Config(
                        name    = get_pipeline_config_name("core"),
                        value   = config_json,
                        version = new_version,
                        service = target_service,
                    ))
                    if ok:
                        pipeline_sent    = True
                        pipeline_message = "Resent to {} (v{})".format(target_service, new_version)
                        record_pipeline_send_success("core", new_version, target_service, pipeline_message)
                        with pipeline_state["lock"]:
                            pipeline_state["core_config"]         = config_json
                            pipeline_state["core_config_pending"] = None
                            pipeline_state["core_config_version"] = new_version
                    else:
                        pipeline_message = "publish_config failed -- queued"
                        record_pipeline_send_failure("core", pipeline_message)
                        with pipeline_state["lock"]:
                            pipeline_state["core_config_pending"] = config_json
                            pipeline_state["core_config_version"] = new_version
                except Exception as exc:
                    pipeline_message = "Error: {} -- queued".format(exc)
                    record_pipeline_send_failure("core", pipeline_message)
                    with pipeline_state["lock"]:
                        pipeline_state["core_config_pending"] = config_json
                        pipeline_state["core_config_version"] = new_version
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

# ============================================================================
# WHITELIST API  -- GET /api/pipeline/whitelist
#                   POST /api/pipeline/whitelist/device
# ============================================================================

async def pipeline_whitelist_get_handler(request):
    """GET /api/pipeline/whitelist
    Returns the whitelist split into three categories:
      permanent   -- network/status entries, always active, never editable
      device_names-- explicitly registered device names (e.g. ["load"])
      named       -- expanded datapoints derived from those names
      active      -- full current whitelist (all of the above merged)
    """
    with _dp_whitelist_lock:
        active = sorted(_dp_whitelist)

    with _whitelisted_names_lock:
        device_names = sorted(_whitelisted_device_names)

    # Build the named datapoints list from registered names + suffixes
    named = []
    with pipeline_state["lock"]:
        include_raw = pipeline_state.get("load_raw_enabled", False)
    for name in device_names:
        for suffix in _DEVICE_DP_SUFFIXES:
            named.append("{}{}".format(name, suffix))
        if include_raw:
            named.append("{}_raw".format(name))

    return web.json_response({
        "success":      True,
        "permanent":    sorted(_PERMANENT_WHITELIST),
        "device_names": device_names,
        "named":        sorted(named),
        "active":       active,
    })


async def pipeline_whitelist_device_handler(request):
    """POST /api/pipeline/whitelist/device
    Body: { "action": "add" | "remove", "name": "<device_name>" }
    Adds or removes a device name from the whitelist and rebuilds immediately.
    """
    try:
        body   = await request.json()
        action = body.get("action", "").strip()
        name   = (body.get("name") or "").strip()
    except Exception:
        return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)

    if not name:
        return web.json_response({"success": False, "error": "name required"}, status=400)
    if action not in ("add", "remove"):
        return web.json_response({"success": False, "error": "action must be add or remove"}, status=400)

    with _whitelisted_names_lock:
        if action == "add":
            _whitelisted_device_names.add(name)
            logger.info("[WHITELIST] Device added via API: '{}'".format(name))
        else:
            _whitelisted_device_names.discard(name)
            logger.info("[WHITELIST] Device removed via API: '{}'".format(name))

    with pipeline_state["lock"]:
        include_raw = pipeline_state.get("load_raw_enabled", False)
    rebuild_whitelist(include_raw=include_raw)

    return web.json_response({"success": True, "action": action, "name": name})


# ============================================================================
# LOAD_RAW TOGGLE  -- POST /api/pipeline/load-raw-toggle
# ============================================================================

async def pipeline_load_raw_toggle_handler(request):
    """POST /api/pipeline/load-raw-toggle
    Body: { "enabled": true | false }
    Adds or removes the exact raw datapoint for the current device
    from the broadcast whitelist.

    When turning ON:  also call client.subscribe() for any .raw datapoints
                      that were skipped at connect time (because toggle was OFF).
    When turning OFF: whitelist removal is sufficient -- there is no
                      client.unsubscribe(), but the RECEIVE_DONE handler drops
                      non-whitelisted datapoints before reading or broadcasting.
    """
    try:
        body    = await request.json()
        enabled = bool(body.get("enabled", False))
    except Exception:
        return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)

    with pipeline_state["lock"]:
        pipeline_state["load_raw_enabled"] = enabled

    # Rebuild whitelist first -- adds/removes the exact raw datapoint strings
    rebuild_whitelist(include_raw=enabled)

    # When turning ON: subscribe to raw datapoints now (they were skipped at
    # connect time because the toggle was OFF then).
    if enabled:
        with pipeline_state["lock"]:
            client    = pipeline_state.get("client")
            connected = pipeline_state.get("connected", False)
            lc_config = pipeline_state.get("loadcell_config")

        if connected and client and hasattr(client, "subscribe") and lc_config:
            try:
                cfg = json.loads(lc_config)
                for lc_entry in cfg.get("load_cells", []):
                    device_name = lc_entry.get("name")
                    if device_name:
                        raw_dp = "loadcells.{}.raw".format(device_name)
                        with pipeline_state["lock"]:
                            already = raw_dp in pipeline_state.get("subscribed_datapoints", set())
                        if not already:
                            try:
                                client.subscribe(raw_dp)
                                with pipeline_state["lock"]:
                                    pipeline_state["subscribed_datapoints"].add(raw_dp)
                                logger.info("[PIPELINE] Raw ON -- subscribed to '{}'".format(raw_dp))
                            except Exception as sub_e:
                                logger.error("[PIPELINE] Raw subscribe error '{}': {}".format(raw_dp, sub_e))
                        else:
                            logger.info("[PIPELINE] Raw ON -- already subscribed to '{}'".format(raw_dp))
            except Exception as e:
                logger.error("[PIPELINE] Raw ON subscribe parse error: {}".format(e))
    else:
        # Turning OFF: remove raw datapoints from the subscribed_datapoints
        # tracking set so they get re-skipped on the next reconnect.
        with pipeline_state["lock"]:
            subs = pipeline_state.get("subscribed_datapoints", set())
            raw_dps = {dp for dp in subs if dp.startswith("loadcells.") and dp.endswith(".raw")}
            subs.difference_update(raw_dps)
            if raw_dps:
                logger.info("[PIPELINE] Raw OFF -- removed from tracked subscriptions: {}".format(raw_dps))

    state = "ON" if enabled else "OFF"
    logger.info("[PIPELINE] load_raw broadcast toggled: {}".format(state))
    return web.json_response({"success": True, "load_raw_enabled": enabled})


async def pipeline_load_raw_state_handler(request):
    """GET /api/pipeline/load-raw-toggle -- return current toggle state."""
    with pipeline_state["lock"]:
        enabled = pipeline_state.get("load_raw_enabled", False)
    return web.json_response({"load_raw_enabled": enabled})


# ============================================================================
# NETWORK ROUTE SELECT  -- POST /api/pipeline/network-route-select
# Publishes the network_route_select datapoint via client.datapoint_set().
#   "0": "auto", "1": "eth0", "2": "eth1", "3": "lte", "4": "wifi"
# Uses datapoint_set() -- no service name required; this client owns the
# datapoint and the pipeline broadcasts it via SEND_TO_INPUT frame.
# ============================================================================

_ROUTE_SELECT_MAP = {0: 'auto', 1: 'eth0', 2: 'eth1', 3: 'lte', 4: 'wifi'}

async def pipeline_network_route_select_handler(request):
    """POST /api/pipeline/network-route-select
    Body: { "network_route_select": <int 0-4> }
    Calls client.datapoint_set('network_route_select', value) -- no service
    name needed; the client publishes it as its own datapoint (SEND_TO_INPUT).
    """
    try:
        body  = await request.json()
        value = int(body.get('network_route_select', -1))
    except Exception:
        return web.json_response({'success': False, 'message': 'Invalid JSON or value'}, status=400)

    if value not in _ROUTE_SELECT_MAP:
        return web.json_response(
            {'success': False, 'message': 'Value must be 0-4 (0=auto,1=eth0,2=eth1,3=lte,4=wifi)'},
            status=400)

    route_name = _ROUTE_SELECT_MAP[value]
    logger.info('[NET-ROUTE] network_route_select={} ({})'.format(value, route_name))

    pipeline_sent    = False
    pipeline_message = 'Pipeline not connected'

    with pipeline_state['lock']:
        client    = pipeline_state.get('client')
        connected = pipeline_state.get('connected', False)

    if connected and client:
        try:
            # datapoint_set publishes this client's own datapoint -- no service name needed.
            # Type inference: int -> LONG (64-bit), sent via SEND_TO_INPUT binary frame.
            ok = client.datapoint_set('network_route_select', value)
            if ok:
                pipeline_sent    = True
                pipeline_message = 'Sent network_route_select={} ({})'.format(value, route_name)
            else:
                pipeline_message = 'datapoint_set returned False'
        except Exception as exc:
            pipeline_message = 'datapoint_set error: {}'.format(exc)
            logger.info('[NET-ROUTE] ' + pipeline_message)
    else:
        pipeline_message = 'Pipeline not connected -- datapoint not sent'

    logger.info('[NET-ROUTE] ' + pipeline_message)
    return web.json_response({
        'success':              True,
        'network_route_select': value,
        'route':                route_name,
        'pipeline_sent':        pipeline_sent,
        'pipeline_message':     pipeline_message,
    })


# ============================================================================
# ROUTE REGISTRATION
# ============================================================================

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

    # -- Loadcell ----------------------------------------------------------
    app.router.add_get ('/api/pipeline/loadcell-devices',        pipeline_loadcell_devices_handler)
    app.router.add_post('/api/pipeline/loadcell-config/import',  pipeline_loadcell_import_handler)
    app.router.add_get ('/api/pipeline/calibration',             pipeline_calibration_get_handler)
    app.router.add_post('/api/pipeline/calibration',             pipeline_calibration_post_handler)
    app.router.add_post('/api/pipeline/filters',                 pipeline_filters_post_handler)

    # -- Modbus ------------------------------------------------------------
    app.router.add_post('/api/pipeline/modbus-config',      pipeline_modbus_config_handler)
    app.router.add_post('/api/pipeline/modbus-config/save', pipeline_save_modbus_config)

    # -- IoT Gateway -------------------------------------------------------
    app.router.add_get ('/api/pipeline/iot-gateway-config',      pipeline_iot_gateway_config_view_handler)
    app.router.add_post('/api/pipeline/iot-gateway-config/send', pipeline_send_iot_gateway_config_handler)

    # -- Core Config -------------------------------------------------------
    app.router.add_get ('/api/pipeline/core-config',        pipeline_core_config_view_handler)
    app.router.add_get ('/api/pipeline/core-configs',       pipeline_core_configs_list_handler)
    app.router.add_post('/api/pipeline/core-config/upload', pipeline_core_config_upload_handler)
    app.router.add_post('/api/pipeline/core-config/resend', pipeline_core_config_resend_handler)

    # -- Auto-send + send log ----------------------------------------------
    app.router.add_post('/api/pipeline/auto-send',       pipeline_auto_send_handler)
    app.router.add_post('/api/pipeline/auto-send/order', pipeline_save_send_order_handler)
    app.router.add_get ('/api/pipeline/send-log',        pipeline_send_log_handler)

    # -- Whitelist ---------------------------------------------------------
    app.router.add_get ('/api/pipeline/whitelist',        pipeline_whitelist_get_handler)
    app.router.add_post('/api/pipeline/whitelist/device', pipeline_whitelist_device_handler)

    # -- Load-raw toggle ---------------------------------------------------
    app.router.add_get ('/api/pipeline/load-raw-toggle', pipeline_load_raw_state_handler)
    app.router.add_post('/api/pipeline/load-raw-toggle', pipeline_load_raw_toggle_handler)
    app.router.add_post('/api/pipeline/core-config/save', pipeline_core_config_save_handler)

    # -- Network route select ----------------------------------------------
    app.router.add_post('/api/pipeline/network-route-select', pipeline_network_route_select_handler)
    # Register whitelisted device names from DB (permanent devices only),
    # then build the initial whitelist with raw OFF.
    try:
        import sqlite3 as _sq
        _conn = _sq.connect(DB_FILE)
        _conn.row_factory = _sq.Row
        _cur = _conn.cursor()
        _cur.execute("SELECT name FROM loadcell_device WHERE enabled = 1")
        for _row in _cur.fetchall():
            add_whitelisted_device_name(_row["name"])
        _conn.close()
    except Exception as _wl_err:
        logger.info("[WHITELIST] Could not seed device names from DB: {}".format(_wl_err))
    rebuild_whitelist(include_raw=False)

    # Seed any missing pipeline_service_targets rows
    _seed_pipeline_targets()

    logger.info("[PIPELINE] Routes registered OK")


def _seed_pipeline_targets():
    """Ensure all known config types exist in pipeline_service_targets,
    and that the send_order column exists (added in v2)."""
    KNOWN_TYPES = [
        ("modbus",      "Modbus TCP/RTU service -- send only",                    1),
        ("loadcell",    "Load cell service -- send config + receive live data",   2),
        ("iot_gateway", "IoT Gateway service -- send only",                       3),
        ("core",        "Core config service -- send only",                       4),
    ]
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Migrate: add send_order column if it doesn't exist yet
        cursor.execute("PRAGMA table_info(pipeline_service_targets)")
        cols = [r[1] for r in cursor.fetchall()]
        if "send_order" not in cols:
            cursor.execute(
                "ALTER TABLE pipeline_service_targets ADD COLUMN send_order INTEGER DEFAULT 0"
            )
            logger.info("[PIPELINE] Migrated pipeline_service_targets: added send_order column")

        for cfg_type, description, default_order in KNOWN_TYPES:
            cursor.execute(
                "SELECT 1 FROM pipeline_service_targets WHERE config_type = ?",
                (cfg_type,)
            )
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO pipeline_service_targets "
                    "(config_type, service_name, enabled, description, send_order) "
                    "VALUES (?, '', 0, ?, ?)",
                    (cfg_type, description, default_order)
                )
                logger.info("[PIPELINE] Seeded pipeline target: {}".format(cfg_type))
            else:
                # Set default order if still 0
                cursor.execute(
                    "UPDATE pipeline_service_targets SET send_order = ? "
                    "WHERE config_type = ? AND (send_order IS NULL OR send_order = 0)",
                    (default_order, cfg_type)
                )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("[PIPELINE] Warning: could not seed pipeline targets: {}".format(e))