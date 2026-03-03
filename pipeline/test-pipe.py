#!/usr/bin/env python
# -*- coding: utf-8 -*-
# test_modbus_config.py - Debug script to test sending config to all services

import json
import time
import sys
from ilx_pipeline import PipelineClient, EventType, Config

# Configuration to send (simplified test config)
TEST_CONFIG = {
    "connections": [
        {
            "id": "PLC Controller - Main",
            "type": "tcp",
            "host": "127.0.0.1",
            "port": 502,
            "responseTimeoutMs": 100,
            "byteTimeoutMs": 100,
            "maxRetries": 2,
            "pollingIntervalMs": 300
        }
    ],
    "assets": [
        {
            "connection_id": "PLC Controller - Main",
            "name": "Hoist_voltage",
            "slaveId": 1,
            "registerType": "holding",
            "address": 4565,
            "registerCount": 1,
            "dataType": "uint16",
            "scale": 1.0,
            "offset": 0.0,
            "byteOrder": "big",
            "wordOrder": "big",
            "retryCount": 1,
            "timeoutMs": 100,
            "writable": False,
            "group": "hoist_group"
        }
    ]
}

# List of all services from your logs
SERVICES_TO_TEST = [
    "modbus_service",                    # Most likely target
    "modbus",                             # Alternative
    "modbus-service",                     # With hyphen
    "gateway_config_service",              # Self
    "data_listener_service_42d46582",
    "data_lister_service_9ce10718",
    "load_cell_service",
    "gui_b38f5150",
    "gpio_service",
    "ilx_craneiq_core",
    "virtual_tag_hdl",
    "display_keys_service",
    "status_led",
    "",                                    # Broadcast to all
]

class ConfigDebugger:
    def __init__(self, host="127.0.0.1", port=7000):
        self.host = host
        self.port = port
        self.client = None
        self.received_configs = []
        self.service_events = set()
        
    def on_event(self, event):
        """Event callback to monitor what comes back"""
        print("\n[DEBUG] 📨 EVENT RECEIVED:")
        print("  Type: {}".format(event.event_type))
        print("  Service: '{}'".format(event.service_name))
        print("  Datapoint: '{}'".format(event.datapoint_name))
        
        if event.event_type == EventType.SERVICE_ADDED:
            self.service_events.add(event.service_name)
            print("  ➕ Service added to tracking")
            
        elif event.event_type == EventType.CONFIG_RECEIVED:
            print("  📦 CONFIG RECEIVED!")
            if event.config:
                print("    Config name: {}".format(event.config.name))
                print("    Config service target: '{}'".format(event.config.service))
                print("    Config version: {}".format(event.config.version))
                self.received_configs.append({
                    'service': event.service_name,
                    'config': event.config
                })
        
        elif event.event_type == EventType.NOTIFICATION_RECEIVED:
            print("  🔔 Notification from: {}".format(event.service_name))
            
        elif event.event_type == EventType.PIPELINE_CONNECTED:
            print("  🔌 Pipeline connected")
            
        elif event.event_type == EventType.PIPELINE_OFFLINE:
            print("  🔌 Pipeline offline")
    
    def connect(self):
        """Connect to pipeline"""
        print("\n[DEBUG] 🔌 Connecting to pipeline at {}:{}...".format(self.host, self.port))
        self.client = PipelineClient("config_debugger", self.host, self.port, 1000, 10)
        self.client.set_event_callback(self.on_event)
        self.client.start()
        
        if self.client.wait_until_connected(5000):
            print("[DEBUG] ✅ Connected successfully")
            # Wait a moment for service discovery
            time.sleep(2)
            return True
        else:
            print("[DEBUG] ❌ Failed to connect")
            return False
    
    def test_send_to_service(self, service_name):
        """Send test config to a specific service"""
        print("\n" + "="*60)
        print("[TEST] Sending to service: '{}'".format(service_name))
        print("="*60)
        
        if not self.client:
            print("[TEST] ❌ Not connected")
            return False
        
        try:
            # Create config
            cfg = Config()
            cfg.name = "test_config_{}".format(int(time.time()))
            cfg.value = json.dumps(TEST_CONFIG)
            cfg.version = int(time.time())
            cfg.service = service_name
            
            print("[TEST] Config name: {}".format(cfg.name))
            print("[TEST] Config size: {} bytes".format(len(cfg.value)))
            print("[TEST] Target service: '{}'".format(cfg.service))
            
            # Send
            print("[TEST] Sending...")
            ok = self.client.publish_config(cfg)
            print("[TEST] publish_config returned: {}".format(ok))
            
            return ok
            
        except Exception as e:
            print("[TEST] ❌ Error: {}".format(e))
            return False
    
    def test_broadcast(self):
        """Send to all services (empty service name)"""
        return self.test_send_to_service("")
    
    def run_all_tests(self):
        """Run tests for all services"""
        print("\n" + "="*80)
        print("STARTING DEBUG TESTS - SENDING TO ALL SERVICES")
        print("="*80)
        
        # First, show all discovered services
        print("\n[INFO] Services discovered so far:")
        for svc in sorted(self.service_events):
            print("  - {}".format(svc))
        
        # Test each service
        results = {}
        for service in SERVICES_TO_TEST:
            if service:  # Skip empty for now, we'll do broadcast separately
                success = self.test_send_to_service(service)
                results[service] = success
                time.sleep(1)  # Wait between tests
        
        # Test broadcast
        print("\n" + "="*60)
        print("[TEST] Testing BROADCAST (empty service name)")
        print("="*60)
        broadcast_success = self.test_broadcast()
        results["[BROADCAST]"] = broadcast_success
        
        # Wait a bit for any responses
        print("\n[INFO] Waiting 3 seconds for any responses...")
        time.sleep(3)
        
        # Print summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print("\nSent to services:")
        for service, success in results.items():
            status = "✅" if success else "❌"
            print("  {} {} - Send {}".format(status, service, "SUCCESS" if success else "FAILED"))
        
        print("\nReceived configs from:")
        if self.received_configs:
            for rcvd in self.received_configs:
                print("  ✅ {} sent config back".format(rcvd['service']))
        else:
            print("  ❌ No configs received by any service")
        
        print("\nAll discovered services during test:")
        for svc in sorted(self.service_events):
            received = "✅" if any(r['service'] == svc for r in self.received_configs) else "❌"
            print("  {} {} - {}".format(received, svc, "SENT CONFIG BACK" if any(r['service'] == svc for r in self.received_configs) else "no response"))
    
    def disconnect(self):
        """Disconnect from pipeline"""
        if self.client:
            self.client.stop()
            print("[DEBUG] Disconnected")

def main():
    debugger = ConfigDebugger()
    
    try:
        if debugger.connect():
            debugger.run_all_tests()
        else:
            print("Failed to connect to pipeline")
    except KeyboardInterrupt:
        print("\n[DEBUG] Interrupted by user")
    finally:
        debugger.disconnect()

if __name__ == "__main__":
    main()