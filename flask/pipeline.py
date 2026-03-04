# -*- coding: utf-8 -*-
# pipeline.py - COMPLETE FIXED VERSION with enhanced config format and loadcell_config support

import asyncio
import json
import logging
import sqlite3
import threading
import time
import os
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
    "client": None,
    "connected": False,
    "load_raw": None,
    "modbus_config": None,
    "loadcell_config": None,  # Added for load cell service config
    "ws_clients": set(),
    "lock": threading.RLock(),
    "main_loop": None,
    "connected_services": set(),
    "background_thread": None,
    "should_run": True,
    "config_version": 1,
    "last_config_time": 0,
    "connection_attempts": 0,
    "last_connection_attempt": 0,
    "subscribed_datapoints": set(),
    "modbus_config_pending": None,
    "loadcell_config_pending": None  # Added for pending load cell config
}

# ---------------------------------------------------------------------------
# Broadcast helper
# ---------------------------------------------------------------------------
async def _broadcast_pipeline_msg(msg):
    dead = set()
    clients = list(pipeline_state["ws_clients"])
    if clients and len(clients) > 0:
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

# ---------------------------------------------------------------------------
# Helper function to find services
# ---------------------------------------------------------------------------
def _find_modbus_service():
    """Find any connected service that contains 'modbus' in its name"""
    with pipeline_state["lock"]:
        services = list(pipeline_state["connected_services"])
    
    for service in services:
        if 'modbus' in service.lower():
            return service
    return None

def _find_loadcell_service():
    """Find any connected service that contains 'load_cell' in its name"""
    with pipeline_state["lock"]:
        services = list(pipeline_state["connected_services"])
    
    for service in services:
        if 'load_cell' in service.lower() or 'loadcell' in service.lower():
            return service
    return None

# ---------------------------------------------------------------------------
# Background pipeline thread (runs continuously)
# ---------------------------------------------------------------------------
def _run_pipeline_thread(host="127.0.0.1", port=7000):
    """Background thread that runs the pipeline client"""
    thread_name = "PipelineThread-{}".format(int(time.time()))
    print("[PIPELINE] Starting background thread: {}".format(thread_name))
    
    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Create client
        client = PipelineClient("web_ui", host, port, 1000, 10)
        client.set_connection_timeout(5)
        
        # Store client in state
        with pipeline_state["lock"]:
            pipeline_state["client"] = client
            pipeline_state["connection_attempts"] += 1
            pipeline_state["last_connection_attempt"] = time.time()
        
        # Define event handler
        def on_event(event):
            try:
                etype = event.event_type
                
                if etype == EventType.PIPELINE_CONNECTED:
                    print("\n[PIPELINE] PIPELINE CONNECTED\n")
                    with pipeline_state["lock"]:
                        pipeline_state["connected"] = True
                        pipeline_state["connection_attempts"] = 0
                    
                    # Subscribe to datapoints
                    try:
                        if hasattr(client, 'subscribe'):
                            client.subscribe("modbus_config")
                            print("[PIPELINE] Subscribed to 'modbus_config' via subscribe()")
                            client.subscribe("loadcell_config")  # Added subscription
                            print("[PIPELINE] Subscribed to 'loadcell_config' via subscribe()")
                            client.subscribe("load_raw")
                            print("[PIPELINE] Subscribed to 'load_raw' via subscribe()")
                            
                            with pipeline_state["lock"]:
                                pipeline_state["subscribed_datapoints"].add("modbus_config")
                                pipeline_state["subscribed_datapoints"].add("loadcell_config")  # Added
                                pipeline_state["subscribed_datapoints"].add("load_raw")
                        else:
                            print("[PIPELINE] No subscribe method found, using refresh")
                            client.refresh()
                    except Exception as e:
                        print("[PIPELINE] Subscribe failed: {}".format(e))
                        try:
                            client.refresh()
                            print("[PIPELINE] Requested service refresh as fallback")
                        except Exception as e2:
                            print("[PIPELINE] Refresh failed: {}".format(e2))
                
                elif etype == EventType.PIPELINE_OFFLINE:
                    print("[PIPELINE] PIPELINE OFFLINE")
                    with pipeline_state["lock"]:
                        pipeline_state["connected"] = False
                
                elif etype == EventType.SERVICE_ADDED:
                    service_name = event.service_name
                    print("[PIPELINE] SERVICE ADDED: '{}'".format(service_name))
                    with pipeline_state["lock"]:
                        pipeline_state["connected_services"].add(service_name)
                    
                    if 'modbus' in service_name.lower():
                        print("[PIPELINE] FOUND MODBUS SERVICE: '{}'".format(service_name))
                        
                        # When modbus service appears, try to send any pending config
                        with pipeline_state["lock"]:
                            if pipeline_state.get("modbus_config_pending"):
                                pending_config = pipeline_state["modbus_config_pending"]
                                print("[PIPELINE] Found pending modbus config for service")
                                try:
                                    request_id = client.datapoint_update(service_name, "modbus_config", pending_config)
                                    if request_id > 0:
                                        print("[PIPELINE] Sent pending modbus config to {} (request_id={})".format(service_name, request_id))
                                        pipeline_state["modbus_config_pending"] = None
                                    else:
                                        print("[PIPELINE] Failed to send pending modbus config")
                                except Exception as e:
                                    print("[PIPELINE] Failed to send pending modbus config: {}".format(e))
                    
                    elif 'load_cell' in service_name.lower() or 'loadcell' in service_name.lower():
                        print("[PIPELINE] FOUND LOAD CELL SERVICE: '{}'".format(service_name))
                        
                        # When load cell service appears, try to send any pending config
                        with pipeline_state["lock"]:
                            if pipeline_state.get("loadcell_config_pending"):
                                pending_config = pipeline_state["loadcell_config_pending"]
                                print("[PIPELINE] Found pending load cell config for service")
                                try:
                                    request_id = client.datapoint_update(service_name, "loadcell_config", pending_config)
                                    if request_id > 0:
                                        print("[PIPELINE] Sent pending load cell config to {} (request_id={})".format(service_name, request_id))
                                        pipeline_state["loadcell_config_pending"] = None
                                    else:
                                        print("[PIPELINE] Failed to send pending load cell config")
                                except Exception as e:
                                    print("[PIPELINE] Failed to send pending load cell config: {}".format(e))
                
                elif etype == EventType.SERVICE_REMOVED:
                    service_name = event.service_name
                    print("[PIPELINE] SERVICE REMOVED: '{}'".format(service_name))
                    with pipeline_state["lock"]:
                        pipeline_state["connected_services"].discard(service_name)
                
                elif etype == EventType.RECEIVE_DONE:
                    dp = event.datapoint_name
                    print("[PIPELINE] RECEIVE_DONE: {} from {}".format(dp, event.service_name))
                    
                    try:
                        # Get the value based on its type
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
                        
                        # For modbus_config, try to parse JSON to show structure
                        if dp == "modbus_config" and isinstance(val, str):
                            try:
                                parsed = json.loads(val)
                                print("[PIPELINE]   Modbus Config structure: {}".format(list(parsed.keys())))
                                if "version" in parsed:
                                    print("[PIPELINE]   Config version: {}".format(parsed["version"]))
                                if "connections" in parsed:
                                    print("[PIPELINE]   Connections: {}".format(len(parsed["connections"])))
                                if "assets" in parsed:
                                    print("[PIPELINE]   Assets: {}".format(len(parsed["assets"])))
                                if "timestamp_str" in parsed:
                                    print("[PIPELINE]   Timestamp: {}".format(parsed["timestamp_str"]))
                            except Exception as e:
                                print("[PIPELINE]   Config is not valid JSON: {}".format(e))
                        
                        # For loadcell_config, try to parse JSON to show structure
                        if dp == "loadcell_config" and isinstance(val, str):
                            try:
                                parsed = json.loads(val)
                                print("[PIPELINE]   Load Cell Config structure: {}".format(list(parsed.keys())))
                                if "version" in parsed:
                                    print("[PIPELINE]   Config version: {}".format(parsed["version"]))
                                if "devices" in parsed:
                                    print("[PIPELINE]   Devices: {}".format(len(parsed["devices"])))
                                if "timestamp_str" in parsed:
                                    print("[PIPELINE]   Timestamp: {}".format(parsed["timestamp_str"]))
                            except Exception as e:
                                print("[PIPELINE]   Config is not valid JSON: {}".format(e))
                        
                        print("[PIPELINE]   Value length: {}".format(len(str(val))))
                        
                        # IMPORTANT: Store the value in pipeline_state
                        with pipeline_state["lock"]:
                            pipeline_state[dp] = val
                            if dp == "load_raw":
                                pipeline_state["load_raw"] = val
                                print("[PIPELINE] Stored load_raw value")
                            elif dp == "modbus_config":
                                pipeline_state["modbus_config"] = val
                                print("[PIPELINE] Stored modbus_config value")
                            elif dp == "loadcell_config":  # Added
                                pipeline_state["loadcell_config"] = val
                                print("[PIPELINE] Stored loadcell_config value")
                        
                        # Broadcast to websocket clients
                        main_loop = pipeline_state.get("main_loop")
                        if main_loop and main_loop.is_running():
                            try:
                                msg = json.dumps({"datapoint": dp, "value": val})
                                asyncio.run_coroutine_threadsafe(
                                    _broadcast_pipeline_msg(msg),
                                    main_loop
                                )
                            except Exception as e:
                                print("[PIPELINE] Broadcast error: {}".format(e))
                    
                    except Exception as e:
                        print("[PIPELINE] Error reading dp {}: {}".format(dp, e))
            
            except Exception as e:
                print("[PIPELINE] EVENT handler error: {}".format(e))
                import traceback
                traceback.print_exc()
        
        # Set callback and start
        client.set_event_callback(on_event)
        print("[PIPELINE] Starting client...")
        client.start()
        
        # Wait for connection
        connected = client.wait_until_connected(5000)
        print("[PIPELINE] Initial connection result: {}".format(connected))
        
        with pipeline_state["lock"]:
            pipeline_state["connected"] = connected
        
        if connected:
            print("[PIPELINE] Connected on startup")
        else:
            print("[PIPELINE] Not connected on startup, will retry automatically")
        
        # Keep thread alive
        while pipeline_state.get("should_run", True):
            time.sleep(1)
            
            # Check connection status periodically
            with pipeline_state["lock"]:
                was_connected = pipeline_state["connected"]
                client_ref = pipeline_state["client"]
            
            # If disconnected for a while, try to reconnect
            if not was_connected and client_ref:
                now = time.time()
                with pipeline_state["lock"]:
                    last_attempt = pipeline_state["last_connection_attempt"]
                    attempts = pipeline_state["connection_attempts"]
                
                # Try to reconnect every 10 seconds
                if now - last_attempt > 10:
                    print("[PIPELINE] Attempting to reconnect...")
                    with pipeline_state["lock"]:
                        pipeline_state["connection_attempts"] = attempts + 1
                        pipeline_state["last_connection_attempt"] = now
                    
                    try:
                        client_ref.refresh()
                        print("[PIPELINE] Refresh sent")
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
        except:
            pass

# ---------------------------------------------------------------------------
# Start background thread
# ---------------------------------------------------------------------------
def start_pipeline_background(app=None):
    """Start the pipeline background thread"""
    if not PIPELINE_AVAILABLE:
        print("[PIPELINE] Cannot start - ilx_pipeline not available")
        return
    
    with pipeline_state["lock"]:
        if pipeline_state["background_thread"] and pipeline_state["background_thread"].is_alive():
            print("[PIPELINE] Background thread already running")
            return
        
        pipeline_state["should_run"] = True
        pipeline_state["modbus_config_pending"] = None
        pipeline_state["loadcell_config_pending"] = None  # Added
    
    # Store the main loop for broadcasts
    try:
        main_loop = asyncio.get_event_loop()
        with pipeline_state["lock"]:
            pipeline_state["main_loop"] = main_loop
        print("[PIPELINE] Main event loop captured")
    except Exception as e:
        print("[PIPELINE] Warning: Could not get main event loop: {}".format(e))
    
    # Start thread
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

# ---------------------------------------------------------------------------
# HTTP Handlers
# ---------------------------------------------------------------------------

async def pipeline_connect_handler(request):
    """POST /api/pipeline/connect"""
    if not PIPELINE_AVAILABLE:
        return web.json_response({"success": False, "error": "ilx_pipeline not available"})
    
    try:
        body = await request.json()
    except:
        body = {}
    
    host = body.get("host", "127.0.0.1")
    port = body.get("port", 7000)
    
    # Restart background thread with new settings
    with pipeline_state["lock"]:
        pipeline_state["should_run"] = False
        old_thread = pipeline_state["background_thread"]
        pipeline_state["background_thread"] = None
    
    if old_thread:
        time.sleep(1)
    
    with pipeline_state["lock"]:
        pipeline_state["should_run"] = True
    
    # Store the main loop for broadcasts
    try:
        main_loop = asyncio.get_event_loop()
        with pipeline_state["lock"]:
            pipeline_state["main_loop"] = main_loop
    except Exception as e:
        print("[PIPELINE] Could not get main loop: {}".format(e))
    
    # Start thread
    thread = threading.Thread(
        target=_run_pipeline_thread,
        args=(host, port),
        daemon=True
    )
    thread.start()
    
    with pipeline_state["lock"]:
        pipeline_state["background_thread"] = thread
    
    # Wait a bit for connection
    await asyncio.sleep(2)
    
    with pipeline_state["lock"]:
        connected = pipeline_state["connected"]
        services = list(pipeline_state["connected_services"])
        modbus_service = _find_modbus_service()
        loadcell_service = _find_loadcell_service()  # Added
    
    return web.json_response({
        "success": connected,
        "message": "Connected to pipeline" if connected else "Connecting in background",
        "services": services,
        "modbus_service": modbus_service,
        "loadcell_service": loadcell_service  # Added
    })

async def pipeline_disconnect_handler(request):
    """POST /api/pipeline/disconnect"""
    with pipeline_state["lock"]:
        pipeline_state["should_run"] = False
        client = pipeline_state.get("client")
        if client:
            try:
                client.stop()
            except:
                pass
        pipeline_state["client"] = None
        pipeline_state["connected"] = False
        pipeline_state["load_raw"] = None
        pipeline_state["modbus_config"] = None
        pipeline_state["loadcell_config"] = None  # Added
        pipeline_state["connected_services"].clear()
        pipeline_state["subscribed_datapoints"].clear()
        pipeline_state["modbus_config_pending"] = None
        pipeline_state["loadcell_config_pending"] = None  # Added
    
    print("[PIPELINE] Disconnected")
    return web.json_response({"success": True, "message": "Disconnected"})

async def pipeline_status_handler(request):
    """GET /api/pipeline/status"""
    with pipeline_state["lock"]:
        modbus_service = _find_modbus_service()
        loadcell_service = _find_loadcell_service()  # Added
        
        modbus_config_preview = None
        if pipeline_state["modbus_config"]:
            try:
                # Show preview of config structure
                parsed = json.loads(pipeline_state["modbus_config"])
                modbus_config_preview = {
                    "version": parsed.get("version"),
                    "connections": len(parsed.get("connections", [])),
                    "assets": len(parsed.get("assets", [])),
                    "timestamp": parsed.get("timestamp_str")
                }
            except:
                modbus_config_preview = {"note": "config is not JSON"}
        
        loadcell_config_preview = None  # Added
        if pipeline_state["loadcell_config"]:
            try:
                # Show preview of config structure
                parsed = json.loads(pipeline_state["loadcell_config"])
                loadcell_config_preview = {
                    "version": parsed.get("version"),
                    "devices": len(parsed.get("devices", [])),
                    "timestamp": parsed.get("timestamp_str")
                }
            except:
                loadcell_config_preview = {"note": "config is not JSON"}
        
        return web.json_response({
            "connected": pipeline_state["connected"],
            "load_raw": pipeline_state["load_raw"],
            "modbus_config_preview": modbus_config_preview,
            "loadcell_config_preview": loadcell_config_preview,  # Added
            "modbus_config_length": len(pipeline_state["modbus_config"]) if pipeline_state["modbus_config"] else 0,
            "loadcell_config_length": len(pipeline_state["loadcell_config"]) if pipeline_state["loadcell_config"] else 0,  # Added
            "services": list(pipeline_state["connected_services"]),
            "modbus_service": modbus_service,
            "loadcell_service": loadcell_service,  # Added
            "config_version": pipeline_state["config_version"],
            "last_config_time": pipeline_state["last_config_time"],
            "connection_attempts": pipeline_state["connection_attempts"],
            "subscribed": list(pipeline_state["subscribed_datapoints"])
        })

async def pipeline_config_view_handler(request):
    """GET /api/pipeline/config - View the full current modbus_config"""
    with pipeline_state["lock"]:
        config = pipeline_state.get("modbus_config")
        if config:
            try:
                # Try to parse as JSON for display
                parsed = json.loads(config)
                return web.json_response({
                    "success": True,
                    "config": parsed,
                    "raw_length": len(config)
                })
            except Exception as e:
                return web.json_response({
                    "success": True,
                    "config": config,
                    "raw_length": len(config),
                    "note": "Raw string (not valid JSON)",
                    "error": str(e)
                })
        else:
            return web.json_response({
                "success": False,
                "message": "No modbus config stored"
            })

async def pipeline_loadcell_config_view_handler(request):  # Added
    """GET /api/pipeline/loadcell-config - View the full current loadcell_config"""
    with pipeline_state["lock"]:
        config = pipeline_state.get("loadcell_config")
        if config:
            try:
                # Try to parse as JSON for display
                parsed = json.loads(config)
                return web.json_response({
                    "success": True,
                    "config": parsed,
                    "raw_length": len(config)
                })
            except Exception as e:
                return web.json_response({
                    "success": True,
                    "config": config,
                    "raw_length": len(config),
                    "note": "Raw string (not valid JSON)",
                    "error": str(e)
                })
        else:
            return web.json_response({
                "success": False,
                "message": "No loadcell config stored"
            })

async def pipeline_services_handler(request):
    """GET /api/pipeline/services"""
    with pipeline_state["lock"]:
        modbus_service = _find_modbus_service()
        loadcell_service = _find_loadcell_service()  # Added
        return web.json_response({
            "services": list(pipeline_state["connected_services"]),
            "count": len(pipeline_state["connected_services"]),
            "modbus_service": modbus_service,
            "loadcell_service": loadcell_service  # Added
        })

async def pipeline_debug_handler(request):
    """GET /api/pipeline/debug - Show pipeline state"""
    with pipeline_state["lock"]:
        # Get all keys except non-serializable ones
        state_copy = {}
        for k, v in pipeline_state.items():
            if k not in ["client", "ws_clients", "lock", "main_loop", "background_thread"]:
                if k == "connected_services":
                    state_copy[k] = list(v)
                elif k == "subscribed_datapoints":
                    state_copy[k] = list(v)
                elif k == "modbus_config" and v:
                    state_copy[k + "_length"] = len(v)
                    try:
                        parsed = json.loads(v)
                        state_copy[k + "_preview"] = {
                            "keys": list(parsed.keys()),
                            "version": parsed.get("version"),
                            "connections": len(parsed.get("connections", [])),
                            "assets": len(parsed.get("assets", []))
                        }
                    except:
                        state_copy[k + "_preview"] = "not JSON"
                elif k == "loadcell_config" and v:  # Added
                    state_copy[k + "_length"] = len(v)
                    try:
                        parsed = json.loads(v)
                        state_copy[k + "_preview"] = {
                            "keys": list(parsed.keys()),
                            "version": parsed.get("version"),
                            "devices": len(parsed.get("devices", []))
                        }
                    except:
                        state_copy[k + "_preview"] = "not JSON"
                else:
                    state_copy[k] = v
        
        return web.json_response(state_copy)

async def pipeline_loadraw_ws_handler(request):
    """WebSocket /ws/pipeline/load_raw"""
    user = ws_auth(request)
    if user is None:
        return web.Response(status=401, text='Unauthorized')
    
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    pipeline_state["ws_clients"].add(ws)
    print("[PIPELINE] WS client connected, total={}".format(len(pipeline_state["ws_clients"])))
    
    with pipeline_state["lock"]:
        current_raw = pipeline_state["load_raw"]
        current_config = pipeline_state["modbus_config"]
        current_loadcell_config = pipeline_state["loadcell_config"]  # Added
    
    if current_raw is not None:
        try:
            await ws.send_str(json.dumps({"datapoint": "load_raw", "value": current_raw}))
        except Exception as e:
            print("[PIPELINE] Could not send buffered value: {}".format(e))
    
    if current_config is not None:
        try:
            # Try to parse config for better display
            try:
                parsed = json.loads(current_config)
                display_config = {
                    "version": parsed.get("version"),
                    "timestamp": parsed.get("timestamp_str"),
                    "connections": len(parsed.get("connections", [])),
                    "assets": len(parsed.get("assets", []))
                }
                await ws.send_str(json.dumps({"datapoint": "modbus_config", "value": display_config, "full": parsed}))
            except:
                await ws.send_str(json.dumps({"datapoint": "modbus_config", "value": current_config}))
        except Exception as e:
            print("[PIPELINE] Could not send buffered config: {}".format(e))
    
    if current_loadcell_config is not None:  # Added
        try:
            # Try to parse config for better display
            try:
                parsed = json.loads(current_loadcell_config)
                display_config = {
                    "version": parsed.get("version"),
                    "timestamp": parsed.get("timestamp_str"),
                    "devices": len(parsed.get("devices", []))
                }
                await ws.send_str(json.dumps({"datapoint": "loadcell_config", "value": display_config, "full": parsed}))
            except:
                await ws.send_str(json.dumps({"datapoint": "loadcell_config", "value": current_loadcell_config}))
        except Exception as e:
            print("[PIPELINE] Could not send buffered loadcell config: {}".format(e))
    
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
            d['lowpass_filter_enabled'] = bool(d['lowpass_filter_enabled'])
            d['moving_avg_enabled'] = bool(d['moving_avg_enabled'])
            d['median_filter_enabled'] = bool(d['median_filter_enabled'])
            d['autotare_enabled'] = bool(d['autotare_enabled'])
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
        body = await request.json()
        device_id = body.get("device_id")
        tare_offset = body.get("tare_offset")
        known_weight = body.get("known_weight")
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
        body = await request.json()
        device_id = body.get("device_id")
        filters = body.get("filters", {})
        
        if not device_id:
            return web.json_response({"success": False, "error": "device_id required"})
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE loadcell_device SET
                lowpass_filter_enabled = ?,
                filter_cutoff_frequency = ?,
                filter_activation_delta_min = ?,
                moving_avg_enabled = ?,
                moving_avg_window = ?,
                median_filter_enabled = ?,
                median_filter_window = ?,
                autotare_enabled = ?,
                autotare_trigger_delta_grams = ?,
                adaptive_deadband_enabled = ?,
                adaptive_deadband_min = ?,
                adaptive_deadband_max = ?,
                adaptive_deadband_grow_rate = ?,
                adaptive_deadband_shrink_rate = ?,
                publish_step_grams = ?,
                overload_threshold = ?,
                overload_relay = ?,
                overload_action = ?,
                overload_cooldown_ms = ?,
                confirm_count = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            1 if filters.get("lowpass_filter_enabled") else 0,
            filters.get("filter_cutoff_frequency", 8.0),
            filters.get("filter_activation_delta_min", 20000.0),
            1 if filters.get("moving_avg_enabled") else 0,
            filters.get("moving_avg_window", 4),
            1 if filters.get("median_filter_enabled") else 0,
            filters.get("median_filter_window", 3),
            1 if filters.get("autotare_enabled") else 0,
            filters.get("autotare_trigger_delta_grams", -5.0),
            1 if filters.get("adaptive_deadband_enabled") else 0,
            filters.get("adaptive_deadband_min", 1.0),
            filters.get("adaptive_deadband_max", 20.0),
            filters.get("adaptive_deadband_grow_rate", 0.5),
            filters.get("adaptive_deadband_shrink_rate", 1.5),
            filters.get("publish_step_grams", 5.0),
            filters.get("overload_threshold", 5000.0),
            filters.get("overload_relay", "relay2"),
            filters.get("overload_action", 0),
            filters.get("overload_cooldown_ms", 2000),
            filters.get("confirm_count", 3),
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
# LOAD CELL CONFIG SAVE HANDLER - NEW (Fixed without f-strings)
# ---------------------------------------------------------------------------

async def pipeline_save_loadcell_config(request):
    """POST /api/pipeline/loadcell-config/save
       Backend handles: 
       1. Fetch load cell devices from database
       2. Build load cell configuration
       3. Save to JSON file
       4. Send to load_cell_service via loadcell_config datapoint
    """
    print("\n" + "="*80)
    print("[LOADCELL-CFG] BACKEND: Saving Load Cell Configuration")
    print("="*80)
    
    if not PIPELINE_AVAILABLE:
        return web.json_response({
            "success": False, 
            "error": "ilx_pipeline not available"
        })
    
    try:
        # 1. Connect to database
        print("[LOADCELL-CFG] Connecting to database: {}".format(DB_FILE))
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all enabled load cell devices
        cursor.execute('''
            SELECT 
                id, name, device_path, channel, unit, capacity,
                tare_offset, known_weight, known_weight_raw,
                pipeline_server, pipeline_port,
                lowpass_filter_enabled, filter_cutoff_frequency, filter_activation_delta_min,
                moving_avg_enabled, moving_avg_window,
                median_filter_enabled, median_filter_window,
                autotare_enabled, autotare_trigger_delta_grams,
                adaptive_deadband_enabled, adaptive_deadband_min, adaptive_deadband_max,
                adaptive_deadband_grow_rate, adaptive_deadband_shrink_rate,
                publish_step_grams, overload_threshold, overload_relay,
                overload_action, overload_cooldown_ms, confirm_count
            FROM loadcell_device 
            WHERE enabled = 1
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        print("[LOADCELL-CFG] Fetched {} load cell devices from database".format(len(rows)))
        
        if not rows:
            return web.json_response({
                "success": False,
                "error": "No enabled load cell devices found in database"
            })
        
        # 2. Build devices configuration
        devices = []
        for row in rows:
            r = dict(row)
            
            # Build device config with all parameters (FIXED: no f-strings)
            device_config = {
                "id": r['id'],
                "name": r['name'] or ("LoadCell_" + str(r['id'])),  # Fixed: string concatenation instead of f-string
                "device_path": r.get('device_path', '/dev/ttyUSB0'),
                "channel": r.get('channel', 1),
                "unit": r.get('unit', 'g'),
                "capacity": r.get('capacity', 1000.0),
                
                # Calibration data
                "calibration": {
                    "tare_offset": r.get('tare_offset', 0.0),
                    "known_weight": r.get('known_weight', 1000.0),
                    "known_weight_raw": r.get('known_weight_raw', 1000.0)
                },
                
                # Pipeline connection info (if device connects directly)
                "pipeline": {
                    "server": r.get('pipeline_server', '127.0.0.1'),
                    "port": r.get('pipeline_port', 7000)
                } if r.get('pipeline_server') else None,
                
                # Filter configurations
                "filters": {
                    "lowpass": {
                        "enabled": bool(r.get('lowpass_filter_enabled', 0)),
                        "cutoff_frequency": r.get('filter_cutoff_frequency', 8.0),
                        "activation_delta_min": r.get('filter_activation_delta_min', 20000.0)
                    },
                    "moving_average": {
                        "enabled": bool(r.get('moving_avg_enabled', 0)),
                        "window": r.get('moving_avg_window', 4)
                    },
                    "median": {
                        "enabled": bool(r.get('median_filter_enabled', 0)),
                        "window": r.get('median_filter_window', 3)
                    }
                },
                
                # Auto-tare settings
                "autotare": {
                    "enabled": bool(r.get('autotare_enabled', 0)),
                    "trigger_delta_grams": r.get('autotare_trigger_delta_grams', -5.0)
                },
                
                # Adaptive deadband
                "adaptive_deadband": {
                    "enabled": bool(r.get('adaptive_deadband_enabled', 0)),
                    "min": r.get('adaptive_deadband_min', 1.0),
                    "max": r.get('adaptive_deadband_max', 20.0),
                    "grow_rate": r.get('adaptive_deadband_grow_rate', 0.5),
                    "shrink_rate": r.get('adaptive_deadband_shrink_rate', 1.5)
                },
                
                # Publishing settings
                "publish_step_grams": r.get('publish_step_grams', 5.0),
                
                # Overload protection
                "overload": {
                    "threshold": r.get('overload_threshold', 5000.0),
                    "relay": r.get('overload_relay', 'relay2'),
                    "action": r.get('overload_action', 0),
                    "cooldown_ms": r.get('overload_cooldown_ms', 2000)
                },
                
                # Stability confirmation
                "confirm_count": r.get('confirm_count', 3)
            }
            
            devices.append(device_config)
        
        config_payload = {
            "devices": devices
        }
        
        print("[LOADCELL-CFG] Built configuration for {} devices".format(len(devices)))
        
        # 3. SAVE TO JSON FILE FIRST
        config_dir = "loadcell_configs"
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
            print("[LOADCELL-CFG] Created directory: {}".format(config_dir))
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = "{}/loadcell_config_{}.json".format(config_dir, timestamp)
        
        # Add metadata before saving
        save_payload = config_payload.copy()
        save_payload['_saved_at'] = time.time()
        save_payload['_saved_at_str'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_payload['_device_count'] = len(devices)
        
        # Save to file
        with open(filename, 'w') as f:
            json.dump(save_payload, f, indent=2)
        
        print("[LOADCELL-CFG] Saved configuration to: {}".format(filename))
        
        # Also save a latest copy (overwrite)
        latest_file = "{}/loadcell_config_latest.json".format(config_dir)
        with open(latest_file, 'w') as f:
            json.dump(save_payload, f, indent=2)
        
        print("[LOADCELL-CFG] Updated latest file: {}".format(latest_file))
        
        # 4. Check pipeline connection
        with pipeline_state["lock"]:
            client = pipeline_state.get("client")
            connected = pipeline_state.get("connected", False)
            services = list(pipeline_state.get("connected_services", set()))
        
        print("[LOADCELL-CFG] Pipeline connected: {}, Services: {}".format(connected, services))
        
        # 5. If pipeline is connected, send the config with ENHANCED FORMAT
        pipeline_sent = False
        pipeline_message = "Not sent - pipeline not connected"
        target_service = None
        new_version = None
        
        if connected and client:
            # Find load cell service
            target_service = _find_loadcell_service()
            
            # Create ENHANCED payload with version and metadata
            with pipeline_state["lock"]:
                current_version = pipeline_state.get("config_version", 1)
                new_version = current_version + 1
                pipeline_state["config_version"] = new_version
                pipeline_state["last_config_time"] = time.time()
            
            enhanced_payload = {
                "devices": config_payload["devices"],
                "version": new_version,
                "timestamp": time.time(),
                "timestamp_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "web_ui",
                "device_count": len(devices)
            }
            
            enhanced_json = json.dumps(enhanced_payload)
            print("[LOADCELL-CFG] Enhanced payload structure: {}".format(list(enhanced_payload.keys())))
            
            if target_service:
                # Send to specific service using datapoint_update
                try:
                    request_id = client.datapoint_update(target_service, "loadcell_config", enhanced_json)
                    if request_id > 0:
                        print("[LOADCELL-CFG] Sent ENHANCED config to pipeline (v{}) targeting '{}', request_id={}".format(
                            new_version, target_service, request_id))
                        pipeline_sent = True
                        pipeline_message = "Sent to {} (v{})".format(target_service, new_version)
                    else:
                        print("[LOADCELL-CFG] Failed to send - request_id=0")
                        pipeline_message = "Send failed (request_id=0)"
                        # Store as pending
                        with pipeline_state["lock"]:
                            pipeline_state["loadcell_config_pending"] = enhanced_json
                except Exception as e:
                    print("[LOADCELL-CFG] Error sending to {}: {}".format(target_service, e))
                    pipeline_message = "Error: {}".format(e)
                    # Store as pending
                    with pipeline_state["lock"]:
                        pipeline_state["loadcell_config_pending"] = enhanced_json
            else:
                # No load cell service found, try broadcast or store pending
                print("[LOADCELL-CFG] No load cell service found, trying broadcast")
                try:
                    # Try broadcast via datapoint_set
                    client.datapoint_set("loadcell_config", enhanced_json)
                    print("[LOADCELL-CFG] Broadcast sent via datapoint_set")
                    pipeline_sent = True
                    pipeline_message = "Broadcast sent (v{})".format(new_version)
                    
                    # Also store as pending
                    with pipeline_state["lock"]:
                        pipeline_state["loadcell_config_pending"] = enhanced_json
                except Exception as e:
                    print("[LOADCELL-CFG] Broadcast failed: {}".format(e))
                    pipeline_message = "Broadcast failed"
                    # Store as pending
                    with pipeline_state["lock"]:
                        pipeline_state["loadcell_config_pending"] = enhanced_json
        else:
            # Not connected, store as pending
            enhanced_payload = {
                "devices": config_payload["devices"],
                "version": pipeline_state.get("config_version", 1) + 1,
                "timestamp": time.time(),
                "timestamp_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "web_ui",
                "device_count": len(devices)
            }
            enhanced_json = json.dumps(enhanced_payload)
            with pipeline_state["lock"]:
                pipeline_state["loadcell_config_pending"] = enhanced_json
                print("[LOADCELL-CFG] Stored as pending config (not connected)")
        
        # 6. Return response
        return web.json_response({
            "success": True,
            "message": "Load cell configuration saved to file{}".format(
                " and " + pipeline_message if pipeline_sent else ""),
            "file_saved": filename,
            "file_latest": latest_file,
            "pipeline_sent": pipeline_sent,
            "pipeline_message": pipeline_message,
            "devices": len(devices),
            "target_service": target_service,
            "version": new_version if new_version else pipeline_state.get("config_version", 1),
            "enhanced_format": {
                "keys": ["devices", "version", "timestamp", "timestamp_str", "source", "device_count"]
            }
        })
        
    except Exception as e:
        print("[LOADCELL-CFG] Error: {}".format(e))
        import traceback
        traceback.print_exc()
        return web.json_response({
            "success": False,
            "error": str(e)
        })

# ---------------------------------------------------------------------------
# MODBUS CONFIG SAVE HANDLER - ENHANCED VERSION
# ---------------------------------------------------------------------------

async def pipeline_save_modbus_config(request):
    """POST /api/pipeline/modbus-config/save
       Backend handles: 
       1. Fetch tags from database
       2. Build connections and assets
       3. Save to JSON file
       4. Send to pipeline service with enhanced format
    """
    print("\n" + "="*80)
    print("[MODBUS-CFG] BACKEND: Saving Modbus Configuration")
    print("="*80)
    
    if not PIPELINE_AVAILABLE:
        return web.json_response({
            "success": False, 
            "error": "ilx_pipeline not available"
        })
    
    try:
        # 1. Connect to database
        print("[MODBUS-CFG] Connecting to database: {}".format(DB_FILE))
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all modbus tags with device info
        cursor.execute('''
            SELECT 
                md.id, 
                md.device_id, 
                md.name as tag_name, 
                md.slave_id,
                md.register_address, 
                md.register_type, 
                md.data_type,
                md.byte_order, 
                md.word_order, 
                md.scale_factor, 
                md.offset,
                md.unit, 
                md.writable, 
                md.retry_count, 
                md.timeout_ms, 
                md.register_count,
                md."group" as tag_group,
                m.name as device_name, 
                m.device_type, 
                m.ip_address, 
                m.port, 
                m.serial_port, 
                m.baud_rate,
                m.parity, 
                m.data_bits, 
                m.stop_bits,
                m.response_timeout_ms, 
                m.byte_timeout_ms, 
                m.max_retries, 
                m.polling_interval_ms
            FROM modbus_datapoints md
            JOIN modbus_device m ON md.device_id = m.id
            WHERE md.enabled = 1
            ORDER BY md.device_id, md.slave_id
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        print("[MODBUS-CFG] Fetched {} tags from database".format(len(rows)))
        
        if not rows:
            return web.json_response({
                "success": False,
                "error": "No Modbus tags found in database"
            })
        
        # 2. Build connections and assets
        connection_map = {}
        assets = []
        
        for row in rows:
            r = dict(row)
            dev_id = r['device_id']
            dev_name = r['device_name'] or str(dev_id)
            dev_type = r['device_type'] or 'tcp'
            
            # Build connection if not exists
            if dev_id not in connection_map:
                if dev_type == 'tcp' or dev_type == 'modbus-tcp':
                    connection_map[dev_id] = {
                        "id": dev_name,
                        "type": "tcp",
                        "host": r.get('ip_address') or '127.0.0.1',
                        "port": r.get('port') or 502,
                        "responseTimeoutMs": r.get('response_timeout_ms') or 100,
                        "byteTimeoutMs": r.get('byte_timeout_ms') or 100,
                        "maxRetries": r.get('max_retries') or 2,
                        "pollingIntervalMs": r.get('polling_interval_ms') or 300
                    }
                else:  # RTU
                    connection_map[dev_id] = {
                        "id": dev_name,
                        "type": "rtu",
                        "device": r.get('serial_port') or '/dev/ttyUSB0',
                        "baud": r.get('baud_rate') or 9600,
                        "parity": r.get('parity') or 'N',
                        "dataBits": r.get('data_bits') or 8,
                        "stopBits": r.get('stop_bits') or 1,
                        "responseTimeoutMs": r.get('response_timeout_ms') or 100,
                        "byteTimeoutMs": r.get('byte_timeout_ms') or 100,
                        "maxRetries": r.get('max_retries') or 2,
                        "pollingIntervalMs": r.get('polling_interval_ms') or 300
                    }
            
            # Build asset
            asset = {
                "name": r['tag_name'],
                "connection_id": dev_name,
                "slaveId": r['slave_id'] or 1,
                "registerType": r['register_type'] or 'holding',
                "address": r['register_address'] or 0,
                "registerCount": r['register_count'] or 1,
                "dataType": r['data_type'] or 'uint16',
                "scale": r['scale_factor'] or 1.0,
                "offset": r['offset'] or 0.0,
                "byteOrder": r['byte_order'] or 'big',
                "wordOrder": r['word_order'] or 'big',
                "retryCount": r['retry_count'] or 1,
                "timeoutMs": r['timeout_ms'] or 100,
                "writable": bool(r['writable'])
            }
            
            if r.get('tag_group'):
                asset['group'] = r['tag_group']
            
            assets.append(asset)
        
        config_payload = {
            "connections": list(connection_map.values()),
            "assets": assets
        }
        
        print("[MODBUS-CFG] Built {} connections and {} assets".format(
            len(connection_map), len(assets)))
        
        # 3. SAVE TO JSON FILE FIRST
        config_dir = "modbus_configs"
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
            print("[MODBUS-CFG] Created directory: {}".format(config_dir))
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = "{}/modbus_config_{}.json".format(config_dir, timestamp)
        
        # Add metadata before saving
        save_payload = config_payload.copy()
        save_payload['_saved_at'] = time.time()
        save_payload['_saved_at_str'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_payload['_tag_count'] = len(rows)
        
        # Save to file
        with open(filename, 'w') as f:
            json.dump(save_payload, f, indent=2)
        
        print("[MODBUS-CFG] Saved configuration to: {}".format(filename))
        
        # Also save a latest copy (overwrite)
        latest_file = "{}/modbus_config_latest.json".format(config_dir)
        with open(latest_file, 'w') as f:
            json.dump(save_payload, f, indent=2)
        
        print("[MODBUS-CFG] Updated latest file: {}".format(latest_file))
        
        # 4. Check pipeline connection
        with pipeline_state["lock"]:
            client = pipeline_state.get("client")
            connected = pipeline_state.get("connected", False)
            services = list(pipeline_state.get("connected_services", set()))
        
        print("[MODBUS-CFG] Pipeline connected: {}, Services: {}".format(connected, services))
        
        # 5. If pipeline is connected, send the config with ENHANCED FORMAT
        pipeline_sent = False
        pipeline_message = "Not sent - pipeline not connected"
        target_service = None
        new_version = None
        
        if connected and client:
            # Find modbus service
            target_service = _find_modbus_service()
            
            # Create ENHANCED payload with version and metadata
            with pipeline_state["lock"]:
                current_version = pipeline_state.get("config_version", 1)
                new_version = current_version + 1
                pipeline_state["config_version"] = new_version
                pipeline_state["last_config_time"] = time.time()
            
            enhanced_payload = {
                "connections": config_payload["connections"],
                "assets": config_payload["assets"],
                "version": new_version,
                "timestamp": time.time(),
                "timestamp_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "web_ui",
                "tag_count": len(rows)
            }
            
            enhanced_json = json.dumps(enhanced_payload)
            print("[MODBUS-CFG] Enhanced payload structure: {}".format(list(enhanced_payload.keys())))
            
            if target_service:
                # Send to specific service using datapoint_update
                try:
                    request_id = client.datapoint_update(target_service, "modbus_config", enhanced_json)
                    if request_id > 0:
                        print("[MODBUS-CFG] Sent ENHANCED config to pipeline (v{}) targeting '{}', request_id={}".format(
                            new_version, target_service, request_id))
                        pipeline_sent = True
                        pipeline_message = "Sent to {} (v{})".format(target_service, new_version)
                    else:
                        print("[MODBUS-CFG] Failed to send - request_id=0")
                        pipeline_message = "Send failed (request_id=0)"
                        # Store as pending
                        with pipeline_state["lock"]:
                            pipeline_state["modbus_config_pending"] = enhanced_json
                except Exception as e:
                    print("[MODBUS-CFG] Error sending to {}: {}".format(target_service, e))
                    pipeline_message = "Error: {}".format(e)
                    # Store as pending
                    with pipeline_state["lock"]:
                        pipeline_state["modbus_config_pending"] = enhanced_json
            else:
                # No modbus service found, try broadcast or store pending
                print("[MODBUS-CFG] No modbus service found, trying broadcast")
                try:
                    # Try broadcast via datapoint_set
                    client.datapoint_set("modbus_config", enhanced_json)
                    print("[MODBUS-CFG] Broadcast sent via datapoint_set")
                    pipeline_sent = True
                    pipeline_message = "Broadcast sent (v{})".format(new_version)
                    
                    # Also store as pending
                    with pipeline_state["lock"]:
                        pipeline_state["modbus_config_pending"] = enhanced_json
                except Exception as e:
                    print("[MODBUS-CFG] Broadcast failed: {}".format(e))
                    pipeline_message = "Broadcast failed"
                    # Store as pending
                    with pipeline_state["lock"]:
                        pipeline_state["modbus_config_pending"] = enhanced_json
        else:
            # Not connected, store as pending
            enhanced_payload = {
                "connections": config_payload["connections"],
                "assets": config_payload["assets"],
                "version": pipeline_state.get("config_version", 1) + 1,
                "timestamp": time.time(),
                "timestamp_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "web_ui",
                "tag_count": len(rows)
            }
            enhanced_json = json.dumps(enhanced_payload)
            with pipeline_state["lock"]:
                pipeline_state["modbus_config_pending"] = enhanced_json
                print("[MODBUS-CFG] Stored as pending config (not connected)")
        
        # 6. Return response
        return web.json_response({
            "success": True,
            "message": "Configuration saved to file{}".format(
                " and " + pipeline_message if pipeline_sent else ""),
            "file_saved": filename,
            "file_latest": latest_file,
            "pipeline_sent": pipeline_sent,
            "pipeline_message": pipeline_message,
            "connections": len(connection_map),
            "assets": len(assets),
            "target_service": target_service,
            "version": new_version if new_version else pipeline_state.get("config_version", 1),
            "enhanced_format": {
                "keys": ["connections", "assets", "version", "timestamp", "timestamp_str", "source", "tag_count"]
            }
        })
        
    except Exception as e:
        print("[MODBUS-CFG] Error: {}".format(e))
        import traceback
        traceback.print_exc()
        return web.json_response({
            "success": False,
            "error": str(e)
        })

# Keep original handler for backward compatibility
async def pipeline_modbus_config_handler(request):
    """POST /api/pipeline/modbus-config - Legacy handler"""
    return await pipeline_save_modbus_config(request)

# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------
def register_pipeline_routes(app):
    """Register all pipeline routes with the aiohttp app"""
    app.router.add_post('/api/pipeline/connect', pipeline_connect_handler)
    app.router.add_post('/api/pipeline/disconnect', pipeline_disconnect_handler)
    app.router.add_get('/api/pipeline/status', pipeline_status_handler)
    app.router.add_get('/api/pipeline/config', pipeline_config_view_handler)
    app.router.add_get('/api/pipeline/loadcell-config', pipeline_loadcell_config_view_handler)  # Added
    app.router.add_get('/api/pipeline/services', pipeline_services_handler)
    app.router.add_get('/api/pipeline/debug', pipeline_debug_handler)
    app.router.add_get('/ws/pipeline/load_raw', pipeline_loadraw_ws_handler)
    app.router.add_get('/api/pipeline/loadcell-devices', pipeline_loadcell_devices_handler)
    app.router.add_get('/api/pipeline/calibration', pipeline_calibration_get_handler)
    app.router.add_post('/api/pipeline/calibration', pipeline_calibration_post_handler)
    app.router.add_post('/api/pipeline/filters', pipeline_filters_post_handler)
    app.router.add_post('/api/pipeline/modbus-config', pipeline_modbus_config_handler)
    app.router.add_post('/api/pipeline/modbus-config/save', pipeline_save_modbus_config)
    app.router.add_post('/api/pipeline/loadcell-config/save', pipeline_save_loadcell_config)  # Added
    print("[PIPELINE] Routes registered OK")