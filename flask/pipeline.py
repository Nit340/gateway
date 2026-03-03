# -*- coding: utf-8 -*-
# pipeline.py - Pipeline (Load Cell & Modbus) module
#
# CLEAN VERSION - Only sends modbus_config with proper versioning (1.0, 1.1, 1.2)
# REJECTS ALL TEST CONFIGURATIONS

import asyncio
import json
import logging
import sqlite3
import threading
import time
from datetime import datetime

from aiohttp import web
from aiohttp import WSMsgType as MsgType

try:
    from ilx_pipeline import PipelineClient, EventType, DataType, Config
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
    "lock":       threading.RLock(),  # Changed to RLock for reentrant locking
    "main_loop":  None,
    "connected_services": set(),
    "last_send_time": 0,  # Track last send time
    "send_count": 0,      # Track number of sends
    "current_config_version": "1.0",  # Track current config version as string (e.g., "1.0")
    "config_ack_received": False,     # Track if config was acknowledged
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
# Helper function to find modbus service
# ---------------------------------------------------------------------------
def _find_modbus_service():
    """Find any connected service that contains 'modbus' in its name"""
    with pipeline_state["lock"]:
        services = list(pipeline_state["connected_services"])
    
    # Look for any service with 'modbus' in the name (case insensitive)
    modbus_services = [s for s in services if 'modbus' in s.lower()]
    
    if modbus_services:
        # Return the first one found
        return modbus_services[0]
    return None


# ---------------------------------------------------------------------------
# Function to ensure pipeline is connected
# ---------------------------------------------------------------------------
async def _ensure_pipeline_connected(host="127.0.0.1", port=7000):
    """Ensure pipeline is connected, return (client, connected, services)"""
    
    with pipeline_state["lock"]:
        client = pipeline_state.get("client")
        connected = pipeline_state.get("connected", False)
        
        # If already connected and client exists, return it
        if connected and client:
            print("[PIPELINE] Already connected, reusing existing connection")
            return client, True, list(pipeline_state["connected_services"])
    
    # Not connected or no client, need to connect
    print("[PIPELINE] Connecting to {}:{}".format(host, port))
    
    main_loop = asyncio.get_event_loop()
    with pipeline_state["lock"]:
        pipeline_state["main_loop"] = main_loop

    connected_event = threading.Event()

    def _run_pipeline():
        try:
            print("[PIPELINE] Thread started, creating PipelineClient...")
            client = PipelineClient("gateway_config_service", host, port, 1000, 10)
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

                    elif etype == EventType.SERVICE_ADDED:
                        service_name = event.service_name
                        print("[PIPELINE] SERVICE ADDED: '{}'".format(service_name))
                        with pipeline_state["lock"]:
                            pipeline_state["connected_services"].add(service_name)
                            
                        # If this is a modbus service, log it
                        if 'modbus' in service_name.lower():
                            print("[PIPELINE] FOUND MODBUS SERVICE: '{}'".format(service_name))

                    elif etype == EventType.SERVICE_REMOVED:
                        service_name = event.service_name
                        print("[PIPELINE] SERVICE REMOVED: '{}'".format(service_name))
                        with pipeline_state["lock"]:
                            pipeline_state["connected_services"].discard(service_name)

                    elif etype == EventType.CONFIG_RECEIVED:
                        # IGNORE ANY TEST CONFIGS COMPLETELY
                        if event.datapoint_name and event.datapoint_name.startswith('test_'):
                            print("[PIPELINE] IGNORING TEST CONFIG: {}".format(event.datapoint_name))
                            return  # Don't process test configs at all
                        
                        print("[PIPELINE] CONFIG RECEIVED: {}".format(event.datapoint_name))
                        if event.config:
                            print("  Config name: {}".format(event.config.name))
                            print("  Target service: '{}'".format(event.config.service))
                            print("  Version: {}".format(getattr(event.config, 'version', 'unknown')))
                            
                            # Check if this is an acknowledgment for our config
                            if event.config.name == 'modbus_config':
                                with pipeline_state["lock"]:
                                    pipeline_state["config_ack_received"] = True
                                print("[PIPELINE] ✓ CONFIG ACKNOWLEDGED by receiver")

                    elif etype == EventType.RECEIVE_DONE:
                        dp = event.datapoint_name
                        # Only process real datapoints, ignore test ones
                        if dp.startswith("test_"):
                            return
                            
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

                        except Exception as e:
                            print("[PIPELINE] ERROR reading dp {}: {}".format(dp, e))

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
                # After connection, request a refresh to get list of services
                print("[PIPELINE] Requesting service list via refresh...")
                client.refresh()
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
        client = pipeline_state.get("client")
        connected = pipeline_state.get("connected", False)
        services = list(pipeline_state["connected_services"])

    if connected and client:
        print("[PIPELINE] Connected successfully")
        print("[PIPELINE] Connected services: {}".format(services))
        return client, connected, services
    else:
        print("[PIPELINE] Failed to connect")
        return None, False, []


# ---------------------------------------------------------------------------
# HTTP handlers
# ---------------------------------------------------------------------------

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

    client, connected, services = await _ensure_pipeline_connected(host, port)

    # Find and log any modbus service
    modbus_service = _find_modbus_service()

    if connected:
        return web.json_response({
            "success": True, 
            "message": "Connected to pipeline",
            "services": services,
            "modbus_service": modbus_service
        })
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
        pipeline_state["connected_services"].clear()
        pipeline_state["send_count"] = 0
        pipeline_state["current_config_version"] = "1.0"
        pipeline_state["config_ack_received"] = False
    print("[PIPELINE] Disconnected.")
    return web.json_response({"success": True, "message": "Disconnected"})


async def pipeline_status_handler(request):
    """GET /api/pipeline/status"""
    with pipeline_state["lock"]:
        modbus_service = _find_modbus_service()
        return web.json_response({
            "connected": pipeline_state["connected"],
            "load_raw":  pipeline_state["load_raw"],
            "services": list(pipeline_state["connected_services"]),
            "modbus_service": modbus_service,
            "send_count": pipeline_state["send_count"],
            "last_send_time": pipeline_state["last_send_time"],
            "current_config_version": pipeline_state["current_config_version"],
            "config_ack_received": pipeline_state["config_ack_received"]
        })


async def pipeline_services_handler(request):
    """GET /api/pipeline/services - List all connected services"""
    with pipeline_state["lock"]:
        modbus_service = _find_modbus_service()
        return web.json_response({
            "services": list(pipeline_state["connected_services"]),
            "count": len(pipeline_state["connected_services"]),
            "modbus_service": modbus_service
        })


async def pipeline_loadraw_ws_handler(request):
    """WebSocket /ws/pipeline/load_raw"""
    user = ws_auth(request)
    if user is None:
        return web.Response(status=401, text='Unauthorized')

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    pipeline_state["ws_clients"].add(ws)
    print("[PIPELINE] WS client connected (user={}), total={}".format(user, len(pipeline_state["ws_clients"])))

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
            if msg.type == MsgType.close:
                break
            elif msg.type == MsgType.error:
                print("[PIPELINE] WS error (user={}): {}".format(user, ws.exception()))
                break
            elif msg.type == MsgType.ping:
                await ws.pong()
    except Exception as e:
        print("[PIPELINE] WS receive error (user={}): {}".format(user, e))
    finally:
        pipeline_state["ws_clients"].discard(ws)
        print("[PIPELINE] WS client disconnected (user={}), total={}".format(user, len(pipeline_state["ws_clients"])))

    return ws


# ---------------------------------------------------------------------------
# MODBUS CONFIG HANDLER - CLEAN VERSION WITH PROPER VERSION INCREMENTING
# ---------------------------------------------------------------------------

def increment_version(current_version):
    """Increment version from 1.0 -> 1.1 -> 1.2 etc. (keeps as string)"""
    try:
        major, minor = map(int, current_version.split('.'))
        new_version = "{}.{}".format(major, minor + 1)
        return new_version
    except:
        return "1.0"

def version_to_int(version_str):
    """Convert version string like '1.0' to integer 100, '1.1' to 101, etc."""
    try:
        major, minor = map(int, version_str.split('.'))
        return major * 100 + minor
    except:
        return 100  # Default to 1.0 = 100

async def pipeline_modbus_config_handler(request):
    """POST /api/pipeline/modbus-config - Rejects any test configurations"""
    
    print("\n" + "="*80)
    print("[MODBUS-CFG] MODBUS CONFIGURATION RECEIVED FROM FRONTEND")
    print("="*80)
    
    if not PIPELINE_AVAILABLE:
        print("[MODBUS-CFG] ERROR: ilx_pipeline not available")
        return web.json_response({"success": False, "error": "ilx_pipeline not available"})

    try:
        body = await request.json()
        print("[MODBUS-CFG] Request body received")
    except Exception as e:
        print("[MODBUS-CFG] Invalid JSON: {}".format(e))
        return web.json_response({"success": False, "error": "Invalid JSON body"})

    host       = body.get("host", "127.0.0.1")
    port       = int(body.get("port", 7000))
    modbus_cfg = body.get("config")
    
    # Get version from frontend or auto-increment
    requested_version = body.get("version")
    
    with pipeline_state["lock"]:
        if requested_version:
            # Use requested version
            version = requested_version
            pipeline_state["current_config_version"] = version
            print("[MODBUS-CFG] Using requested version: {}".format(version))
        else:
            # Auto-increment from current version
            current = pipeline_state["current_config_version"]
            version = increment_version(current)
            pipeline_state["current_config_version"] = version
            print("[MODBUS-CFG] Auto-incremented version: {} -> {}".format(current, version))
        
        # Reset acknowledgment flag
        pipeline_state["config_ack_received"] = False

    if not modbus_cfg:
        print("[MODBUS-CFG] Missing 'config' field")
        return web.json_response({"success": False, "error": "Missing 'config' field"})

    # =====================================================================
    # AGGRESSIVE TEST CONFIG REJECTION
    # =====================================================================
    
    # Check 1: Look at the raw request body for any test indicators
    raw_body_str = str(body).lower()
    test_indicators = ['test_config', 'test_', 'testconfig', 'testconfig_', 
                       'test-', 'test_', '_test', 'testconfig']
    
    for indicator in test_indicators:
        if indicator in raw_body_str:
            print("[MODBUS-CFG] REJECTING TEST CONFIGURATION - Found '{}' in request".format(indicator))
            print("[MODBUS-CFG] Raw body preview: {}".format(raw_body_str[:200]))
            return web.json_response({
                "success": False, 
                "error": "Test configurations are not allowed",
                "message": "Please use the production config endpoint only",
                "rejected": True,
                "reason": "Test indicator found in request"
            })
    
    # Check 2: Check the config field specifically
    config_str = json.dumps(modbus_cfg).lower()
    for indicator in test_indicators:
        if indicator in config_str:
            print("[MODBUS-CFG] REJECTING TEST CONFIGURATION - Found '{}' in config".format(indicator))
            return web.json_response({
                "success": False, 
                "error": "Test configurations are not allowed",
                "message": "Config contains test references",
                "rejected": True,
                "reason": "Test indicator found in config"
            })
    
    # Check 3: Check for any test-related fields in the config structure
    if isinstance(modbus_cfg, dict):
        # Check connections for test names
        connections = modbus_cfg.get('connections', [])
        for conn in connections:
            conn_id = conn.get('id', '').lower()
            if 'test' in conn_id:
                print("[MODBUS-CFG] REJECTING - Connection ID contains 'test': {}".format(conn.get('id')))
                return web.json_response({
                    "success": False,
                    "error": "Test configurations not allowed",
                    "rejected": True,
                    "reason": "Connection ID contains 'test'"
                })
        
        # Check assets for test names
        assets = modbus_cfg.get('assets', [])
        for asset in assets:
            asset_name = asset.get('name', '').lower()
            if 'test' in asset_name:
                print("[MODBUS-CFG] REJECTING - Asset name contains 'test': {}".format(asset.get('name')))
                return web.json_response({
                    "success": False,
                    "error": "Test configurations not allowed",
                    "rejected": True,
                    "reason": "Asset name contains 'test'"
                })
            
            # Also check group field
            asset_group = asset.get('group', '').lower()
            if 'test' in asset_group:
                print("[MODBUS-CFG] REJECTING - Asset group contains 'test': {}".format(asset.get('group')))
                return web.json_response({
                    "success": False,
                    "error": "Test configurations not allowed",
                    "rejected": True,
                    "reason": "Asset group contains 'test'"
                })
    
    # =====================================================================
    # END TEST CONFIG REJECTION
    # =====================================================================

    # Log what we're about to send
    asset_count = len(modbus_cfg.get("assets", []))
    connection_count = len(modbus_cfg.get("connections", []))
    
    # Add version to config for reference (doesn't affect functionality)
    if isinstance(modbus_cfg, dict):
        modbus_cfg['_config_version'] = version
        modbus_cfg['_config_sent_at'] = time.time()
    
    print("[MODBUS-CFG] Config summary:")
    print("  - Version: {}".format(version))
    print("  - Version integer: {}".format(version_to_int(version)))
    print("  - Connections: {}".format(connection_count))
    print("  - Assets: {}".format(asset_count))
    print("  - Connection IDs: {}".format([c.get('id') for c in modbus_cfg.get('connections', [])]))
    print("  - Asset names: {}".format([a.get('name') for a in modbus_cfg.get('assets', [])]))

    # Ensure pipeline is connected (reuses existing connection if available)
    client, connected, services = await _ensure_pipeline_connected(host, port)

    if not connected or not client:
        print("[MODBUS-CFG] Failed to connect to pipeline")
        return web.json_response({
            "success": False,
            "error": "Could not connect to pipeline at {}:{}".format(host, port)
        })

    # Find modbus service (any service with 'modbus' in name)
    target_service = _find_modbus_service()
    
    if target_service:
        print("[MODBUS-CFG] Found modbus service: '{}'".format(target_service))
    else:
        print("[MODBUS-CFG] No modbus service found in connected services")
        print("[MODBUS-CFG] Will attempt broadcast to all services")

    # Publish the Modbus config
    try:
        # Create config object with fixed name "modbus_config"
        cfg         = Config()
        cfg.name    = "modbus_config"  # FIXED NAME - always the same!
        
        cfg.value   = json.dumps(modbus_cfg)
        
        # Convert version string to integer version for pipeline
        # e.g., "1.0" -> 100, "1.1" -> 101, "1.2" -> 102
        cfg.version = version_to_int(version)
        
        # Set target service if found, otherwise broadcast (empty string)
        if target_service:
            cfg.service = target_service
            service_msg = "to specific service '{}'".format(target_service)
        else:
            cfg.service = ""  # Empty string = broadcast to all services
            service_msg = "as broadcast to all services"

        print("\n[MODBUS-CFG] PUBLISHING MODBUS CONFIG {}:".format(service_msg))
        print("  - Config name: '{}'".format(cfg.name))
        print("  - Version string: {}".format(version))
        print("  - Version integer: {}".format(cfg.version))
        print("  - Target service: '{}'".format(cfg.service if cfg.service else "BROADCAST"))
        print("  - Config size: {} bytes".format(len(cfg.value)))

        # Send the config
        print("[MODBUS-CFG] Calling client.publish_config()...")
        ok = client.publish_config(cfg)
        print("[MODBUS-CFG] publish_config() returned: {}".format(ok))
        
        if ok:
            # Update stats
            with pipeline_state["lock"]:
                pipeline_state["send_count"] += 1
                pipeline_state["last_send_time"] = time.time()
            
            print("[MODBUS-CFG] Modbus config successfully sent to pipeline server")
            print("[MODBUS-CFG] Total sends so far: {}".format(pipeline_state["send_count"]))
            
            # Brief pause for any events
            await asyncio.sleep(0.5)
            
            # Check if we received acknowledgment
            with pipeline_state["lock"]:
                ack_received = pipeline_state["config_ack_received"]
            
            # Return success with info about target
            if target_service:
                return web.json_response({
                    "success": True,
                    "message": "Modbus configuration v{} sent to {} ({} assets, {} connections) - Send #{}{}".format(
                        version, 
                        target_service, 
                        asset_count, 
                        connection_count, 
                        pipeline_state["send_count"],
                        " [ACKNOWLEDGED]" if ack_received else ""
                    ),
                    "assets": asset_count,
                    "connections": connection_count,
                    "target_service": target_service,
                    "discovered": True,
                    "config_name": "modbus_config",
                    "version": version,
                    "version_int": cfg.version,
                    "send_count": pipeline_state["send_count"],
                    "ack_received": ack_received
                })
            else:
                return web.json_response({
                    "success": True,
                    "message": "Modbus configuration v{} broadcast to all services ({} assets, {} connections) - Send #{}{}".format(
                        version, 
                        asset_count, 
                        connection_count, 
                        pipeline_state["send_count"],
                        " [ACKNOWLEDGED]" if ack_received else ""
                    ),
                    "assets": asset_count,
                    "connections": connection_count,
                    "target_service": "broadcast",
                    "discovered": False,
                    "available_services": services,
                    "config_name": "modbus_config",
                    "version": version,
                    "version_int": cfg.version,
                    "send_count": pipeline_state["send_count"],
                    "ack_received": ack_received
                })
        else:
            print("[MODBUS-CFG] publish_config returned False")
            return web.json_response({
                "success": False,
                "error": "publish_config returned False - check pipeline connection"
            })
            
    except Exception as ex:
        print("[MODBUS-CFG] Exception in publish_config: {}".format(ex))
        import traceback
        traceback.print_exc()
        return web.json_response({"success": False, "error": str(ex)})


# ---------------------------------------------------------------------------
# Load Cell device handlers
# ---------------------------------------------------------------------------

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
    app.router.add_get ('/api/pipeline/services',         pipeline_services_handler)
    app.router.add_get ('/ws/pipeline/load_raw',          pipeline_loadraw_ws_handler)
    app.router.add_get ('/api/pipeline/loadcell-devices', pipeline_loadcell_devices_handler)
    app.router.add_get ('/api/pipeline/calibration',      pipeline_calibration_get_handler)
    app.router.add_post('/api/pipeline/calibration',      pipeline_calibration_post_handler)
    app.router.add_post('/api/pipeline/filters',          pipeline_filters_post_handler)

    app.router.add_post('/api/pipeline/modbus-config',    pipeline_modbus_config_handler)
    print("[PIPELINE] Routes registered OK")