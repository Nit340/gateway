#!/usr/bin/env python3
"""
ILX Pipeline Full Simulation Test
===================================
Starts the PipelineServer IN-PROCESS on port 7000, then connects three
simulated service clients (IoT-Gateway, Loadcell-Service, Simulator) and
exercises EVERY protocol feature:

  ✓ Service registration & detection (SERVICE_ADDED / SERVICE_REMOVED)
  ✓ Datapoint publish / receive (SEND_TO_INPUT → DATA_UPDATE)
  ✓ Config publish and reception (PUBLISH_CONFIG → CONFIG_UPDATE)
  ✓ Action publish, trigger, receive (PUBLISH_ACTION / TRIGGER_ACTION)
  ✓ Notification broadcast (PUBLISH_NOTIFICATION)
  ✓ Datapoint update (UPDATE_DATAPOINT → RESPONSE)
  ✓ Refresh request (REFRESH_DATA)
  ✓ Duplicate service name detection (DUPLICATE_SERVICE_NAME)
  ✓ Clean disconnect and SERVICE_REMOVED notification

Usage:
    python ilx_pipeline_test_simulation.py
"""

import logging
import sys
import os
import time
import threading

# Allow running from flask/ directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import server
from ilx_pipeline_server import PipelineServer

# Import client library
from ilx_pipeline import (
    PipelineClient, DataType, EventType, EventStatus, Config,
    NotificationType, NotificationPriority, NotificationCategory
)

# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(name)-20s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("simulation")
# Silence noisy socket-level debug from the library
logging.getLogger("ilx_pipeline.pipeline_socket").setLevel(logging.WARNING)
logging.getLogger("ilx_pipeline.pipeline_client").setLevel(logging.WARNING)
logging.getLogger("ilx_pipeline.binary_frame").setLevel(logging.WARNING)

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 7000
CONNECT_TIMEOUT_MS = 3000


# ============================================================================
# Event recorder – collects events from a PipelineClient for assertions
# ============================================================================
class EventRecorder:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self._lock = threading.Lock()
        self.events = []          # list of EventData objects

    def callback(self, event):
        with self._lock:
            self.events.append(event)

        type_str = PipelineClient.event_get_type_str(event.event_type)
        if event.event_type == EventType.RECEIVE_DONE:
            logger.info("  [%-20s] ← RECEIVE_DONE  dp='%s' from='%s'",
                        self.service_name, event.datapoint_name, event.service_name)
        elif event.event_type == EventType.CONFIG_RECEIVED:
            cfg = event.config
            logger.info("  [%-20s] ← CONFIG_RECEIVED  name='%s' value='%s' ver=%d",
                        self.service_name, cfg.name if cfg else "?",
                        cfg.value if cfg else "?", cfg.version if cfg else -1)
        elif event.event_type == EventType.ACTION_TRIGGERED:
            logger.info("  [%-20s] ← ACTION_TRIGGERED  action='%s'",
                        self.service_name, event.datapoint_name)
        elif event.event_type == EventType.ACTION_RECEIVED:
            logger.info("  [%-20s] ← ACTION_RECEIVED   action='%s' by='%s'",
                        self.service_name, event.datapoint_name, event.service_name)
        elif event.event_type == EventType.NOTIFICATION_RECEIVED:
            nd = event.notification
            logger.info("  [%-20s] ← NOTIFICATION  type=%d msg='%s'",
                        self.service_name, int(nd.type) if nd else -1,
                        nd.message if nd else "?")
        elif event.event_type == EventType.SERVICE_ADDED:
            logger.info("  [%-20s] ← SERVICE_ADDED   '%s'",
                        self.service_name, event.service_name)
        elif event.event_type == EventType.SERVICE_REMOVED:
            logger.info("  [%-20s] ← SERVICE_REMOVED '%s'",
                        self.service_name, event.service_name)
        elif event.event_type in (EventType.PIPELINE_CONNECTED, EventType.PIPELINE_OFFLINE):
            logger.info("  [%-20s] ← %s", self.service_name, type_str)
        elif event.event_type == EventType.SERVICE_NAME_CONFLICT:
            logger.warning("  [%-20s] ← SERVICE_NAME_CONFLICT (fatal)!", self.service_name)
        else:
            logger.debug("  [%-20s] ← %s  dp='%s'",
                         self.service_name, type_str, event.datapoint_name)

    def wait_for(self, event_type: EventType, timeout: float = 3.0,
                 dp_name: str = None, service_name: str = None) -> bool:
        """Block until the specified event arrives or timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                for ev in self.events:
                    if ev.event_type != event_type:
                        continue
                    if dp_name and ev.datapoint_name != dp_name:
                        continue
                    if service_name and ev.service_name != service_name:
                        continue
                    return True
            time.sleep(0.05)
        return False

    def clear(self):
        with self._lock:
            self.events.clear()


# ============================================================================
# Helper to make a client + recorder
# ============================================================================
def make_client(name: str, host=SERVER_HOST, port=SERVER_PORT):
    rec = EventRecorder(name)
    cli = PipelineClient(name, server_address=host, server_port=port)
    cli.set_event_callback(rec.callback)
    return cli, rec


# ============================================================================
# SIMULATION STEPS
# ============================================================================

def sep(title: str):
    bar = "─" * 55
    logger.info("")
    logger.info(bar)
    logger.info("  %s", title)
    logger.info(bar)


def check(condition: bool, description: str):
    status = "✓ PASS" if condition else "✗ FAIL"
    logger.info("  %s  │  %s", status, description)
    return condition


def simulate():
    results = []

    # ------------------------------------------------------------------
    # Step 1 – Start Server
    # ------------------------------------------------------------------
    sep("STEP 1 – Start Pipeline Server on port 7000")
    server = PipelineServer(host="0.0.0.0", port=SERVER_PORT)
    server.start()
    time.sleep(0.3)   # let socket bind settle
    logger.info("  [SERVER]  listening on 0.0.0.0:%d", SERVER_PORT)

    # ------------------------------------------------------------------
    # Step 2 – Connect IoT-Gateway service
    # ------------------------------------------------------------------
    sep("STEP 2 – Connect IoT-Gateway service")
    gw_cli, gw_rec = make_client("IoT-Gateway")
    gw_cli.start()
    ok = gw_cli.wait_until_connected(CONNECT_TIMEOUT_MS)
    results.append(check(ok, "IoT-Gateway connected to server"))
    time.sleep(0.2)

    # ------------------------------------------------------------------
    # Step 3 – Connect Loadcell-Service
    # ------------------------------------------------------------------
    sep("STEP 3 – Connect Loadcell-Service")
    lc_cli, lc_rec = make_client("Loadcell-Service")
    lc_cli.start()
    ok = lc_cli.wait_until_connected(CONNECT_TIMEOUT_MS)
    results.append(check(ok, "Loadcell-Service connected"))

    # IoT-Gateway should see SERVICE_ADDED for Loadcell-Service
    ok2 = gw_rec.wait_for(EventType.SERVICE_ADDED, service_name="Loadcell-Service")
    results.append(check(ok2, "IoT-Gateway sees Loadcell-Service as SERVICE_ADDED"))
    time.sleep(0.2)

    # ------------------------------------------------------------------
    # Step 4 – Connect Simulator service
    # ------------------------------------------------------------------
    sep("STEP 4 – Connect Simulator service")
    sim_cli, sim_rec = make_client("Simulator")
    sim_cli.start()
    ok = sim_cli.wait_until_connected(CONNECT_TIMEOUT_MS)
    results.append(check(ok, "Simulator connected"))
    time.sleep(0.2)

    # ------------------------------------------------------------------
    # Step 5 – Datapoint publish / receive
    # ------------------------------------------------------------------
    sep("STEP 5 – IoT-Gateway publishes datapoints, Loadcell receives them")
    gw_rec.clear(); lc_rec.clear()

    gw_cli.datapoint_set("tank_level",      72.5)
    gw_cli.datapoint_set("pump_running",    True)
    gw_cli.datapoint_set("sensor_status",   "online")
    gw_cli.datapoint_set("flow_rate",       18)

    time.sleep(0.5)

    ok1 = lc_rec.wait_for(EventType.RECEIVE_DONE, dp_name="tank_level",    service_name="IoT-Gateway", timeout=3)
    ok2 = lc_rec.wait_for(EventType.RECEIVE_DONE, dp_name="pump_running",  service_name="IoT-Gateway", timeout=3)
    ok3 = lc_rec.wait_for(EventType.RECEIVE_DONE, dp_name="sensor_status", service_name="IoT-Gateway", timeout=3)
    ok4 = lc_rec.wait_for(EventType.RECEIVE_DONE, dp_name="flow_rate",     service_name="IoT-Gateway", timeout=3)

    results.append(check(ok1, "Loadcell received tank_level"))
    results.append(check(ok2, "Loadcell received pump_running"))
    results.append(check(ok3, "Loadcell received sensor_status"))
    results.append(check(ok4, "Loadcell received flow_rate"))

    # Verify values readable from Loadcell-Service's perspective (they should
    # arrive as RECEIVE_DONE events and be stored by the client)
    tank_val = lc_cli.get_datapoint_double("tank_level")
    results.append(check(abs(tank_val - 72.5) < 0.01, f"Loadcell: tank_level value = {tank_val}"))

    # ------------------------------------------------------------------
    # Step 6 – Publish and receive Config
    # ------------------------------------------------------------------
    sep("STEP 6 – IoT-Gateway publishes config, all services receive it")
    gw_rec.clear(); lc_rec.clear(); sim_rec.clear()

    cfg = Config(name="mqtt_broker_url", value="mqtt://192.168.1.100:1883", version=1)
    gw_cli.publish_config(cfg)
    time.sleep(0.5)

    results.append(check(
        lc_rec.wait_for(EventType.CONFIG_RECEIVED, dp_name="mqtt_broker_url", timeout=3),
        "Loadcell-Service received config 'mqtt_broker_url'"
    ))
    results.append(check(
        sim_rec.wait_for(EventType.CONFIG_RECEIVED, dp_name="mqtt_broker_url", timeout=3),
        "Simulator received config 'mqtt_broker_url'"
    ))

    # Verify config can be retrieved via wait_for_config()
    retrieved = lc_cli.wait_for_config("mqtt_broker_url", timeout_ms=1000)
    results.append(check(
        retrieved.value == "mqtt://192.168.1.100:1883",
        f"Loadcell wait_for_config value: '{retrieved.value}'"
    ))

    # ------------------------------------------------------------------
    # Step 7 – Targeted config (only to Simulator)
    # ------------------------------------------------------------------
    sep("STEP 7 – Targeted config: IoT-Gateway → Simulator only")
    sim_rec.clear()
    cfg2 = Config(name="sim_mode", value="FAST", version=1, service="Simulator")
    gw_cli.publish_config(cfg2)
    time.sleep(0.5)

    results.append(check(
        sim_rec.wait_for(EventType.CONFIG_RECEIVED, dp_name="sim_mode", timeout=3),
        "Simulator received targeted config 'sim_mode'"
    ))

    # ------------------------------------------------------------------
    # Step 8 – Publish and trigger an Action
    # ------------------------------------------------------------------
    sep("STEP 8 – Simulator publishes action 'RESET_ALL', IoT-Gateway triggers it")
    gw_rec.clear(); lc_rec.clear(); sim_rec.clear()

    # Simulator registers the action
    sim_cli.publish_action("RESET_ALL")
    time.sleep(0.3)

    results.append(check(
        gw_rec.wait_for(EventType.ACTION_RECEIVED, dp_name="RESET_ALL", timeout=3),
        "IoT-Gateway received ACTION_RECEIVED for 'RESET_ALL'"
    ))
    results.append(check(
        lc_rec.wait_for(EventType.ACTION_RECEIVED, dp_name="RESET_ALL", timeout=3),
        "Loadcell-Service received ACTION_RECEIVED for 'RESET_ALL'"
    ))

    # IoT-Gateway triggers the action
    gw_cli.trigger_action("RESET_ALL")
    time.sleep(0.3)

    results.append(check(
        sim_rec.wait_for(EventType.ACTION_TRIGGERED, dp_name="RESET_ALL", timeout=3),
        "Simulator received ACTION_TRIGGERED for 'RESET_ALL'"
    ))
    results.append(check(
        lc_rec.wait_for(EventType.ACTION_TRIGGERED, dp_name="RESET_ALL", timeout=3),
        "Loadcell-Service received ACTION_TRIGGERED for 'RESET_ALL'"
    ))

    # ------------------------------------------------------------------
    # Step 9 – Publish notification
    # ------------------------------------------------------------------
    sep("STEP 9 – Loadcell publishes an Alarm notification, all services receive it")
    gw_rec.clear(); sim_rec.clear()

    lc_cli.publish_notification(
        NotificationType.Alarm,
        NotificationPriority.High,
        NotificationCategory.Process,
        subsystem="Loadcell-Service",
        entity="LC_01",
        message="Overload detected on channel 1",
    )
    time.sleep(0.4)

    results.append(check(
        gw_rec.wait_for(EventType.NOTIFICATION_RECEIVED, timeout=3),
        "IoT-Gateway received Alarm notification"
    ))
    results.append(check(
        sim_rec.wait_for(EventType.NOTIFICATION_RECEIVED, timeout=3),
        "Simulator received Alarm notification"
    ))

    # ------------------------------------------------------------------
    # Step 10 – UPDATE_DATAPOINT (cross-service write)
    # ------------------------------------------------------------------
    sep("STEP 10 – IoT-Gateway updates Loadcell-Service's threshold datapoint")
    lc_rec.clear()

    req_id = gw_cli.datapoint_update("Loadcell-Service", "overload_threshold", 95.0)
    results.append(check(req_id > 0, f"datapoint_update returned req_id={req_id}"))
    time.sleep(0.5)

    results.append(check(
        lc_rec.wait_for(EventType.RECEIVE_DONE, dp_name="overload_threshold", timeout=3),
        "Loadcell-Service received updated 'overload_threshold'"
    ))

    # ------------------------------------------------------------------
    # Step 11 – REFRESH_DATA (re-delivery of all cached datapoints)
    # ------------------------------------------------------------------
    sep("STEP 11 – Simulator requests REFRESH_DATA, gets all cached datapoints")
    sim_rec.clear()
    sim_cli.refresh()
    time.sleep(0.8)

    ok = sim_rec.wait_for(EventType.RECEIVE_DONE, dp_name="tank_level", timeout=3)
    results.append(check(ok, "Simulator got tank_level after REFRESH_DATA"))

    # ------------------------------------------------------------------
    # Step 12 – Duplicate service name detection
    # ------------------------------------------------------------------
    sep("STEP 12 – Duplicate service name: second 'IoT-Gateway' is rejected")
    # Run the duplicate client in a subprocess so that os._exit(1) doesn't
    # kill this test process.  We just check:
    #   a) the server logs the duplicate, and
    #   b) a short-lived subprocess exits with code 1 (os._exit triggered).
    import subprocess
    dup_script = (
        "import sys, os, time\n"
        "sys.path.insert(0, r'" + os.path.dirname(os.path.abspath(__file__)) + r"')\n"
        "from ilx_pipeline import PipelineClient, EventType\n"
        "events = []\n"
        "def cb(e): events.append(e)\n"
        "c = PipelineClient('IoT-Gateway', server_address='" + SERVER_HOST + "', server_port=" + str(SERVER_PORT) + ")\n"
        "c.set_event_callback(cb)\n"
        "c.start()\n"
        "time.sleep(2)\n"
        "# os._exit will have fired before reaching here if duplicate was detected\n"
        "sys.exit(0)\n"
    )
    dup_proc = subprocess.Popen(
        [sys.executable, "-c", dup_script],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    try:
        dup_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        dup_proc.kill()
        dup_proc.wait()

    # os._exit(1) → exit code 1 means conflict was detected and the client terminated
    conflict_detected = (dup_proc.returncode == 1)
    results.append(check(conflict_detected,
                         f"Duplicate 'IoT-Gateway' subprocess exited with code 1 (os._exit fired) rc={dup_proc.returncode}"))

    # ------------------------------------------------------------------
    # Step 13 – Disconnect Simulator and verify SERVICE_REMOVED
    # ------------------------------------------------------------------
    sep("STEP 13 – Simulator disconnects, others get SERVICE_REMOVED")
    gw_rec.clear(); lc_rec.clear()
    sim_cli.stop()
    time.sleep(0.5)

    ok1 = gw_rec.wait_for(EventType.SERVICE_REMOVED, service_name="Simulator", timeout=3)
    ok2 = lc_rec.wait_for(EventType.SERVICE_REMOVED, service_name="Simulator", timeout=3)
    results.append(check(ok1, "IoT-Gateway received SERVICE_REMOVED for Simulator"))
    results.append(check(ok2, "Loadcell-Service received SERVICE_REMOVED for Simulator"))

    # Action published by Simulator should also be deleted → ACTION_REMOVED
    ok3 = gw_rec.wait_for(EventType.ACTION_REMOVED, dp_name="RESET_ALL", timeout=3)
    results.append(check(ok3, "IoT-Gateway received ACTION_REMOVED for 'RESET_ALL'"))

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    sep("Cleanup")
    gw_cli.stop()
    lc_cli.stop()
    server.stop()
    time.sleep(0.3)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    sep("SIMULATION RESULTS")
    total  = len(results)
    passed = sum(results)
    failed = total - passed
    logger.info("")
    logger.info("  Total checks : %d", total)
    logger.info("  Passed       : %d", passed)
    logger.info("  Failed       : %d", failed)
    logger.info("")
    if failed == 0:
        logger.info("  🎉  ALL CHECKS PASSED – Pipeline server simulation SUCCESSFUL!")
    else:
        logger.warning("  ⚠   %d CHECK(S) FAILED – review the log above.", failed)
    logger.info("")
    return failed == 0


# ============================================================================
if __name__ == "__main__":
    success = simulate()
    sys.exit(0 if success else 1)
