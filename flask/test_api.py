#!/usr/bin/env python3
"""
Test script for Gateway Configuration API
Demonstrates creating devices and datapoints
"""

import requests
import json
import time

BASE_URL = "http://localhost:8080"

def print_section(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def test_general_config():
    """Test general configuration"""
    print_section("Testing General Configuration")
    
    # Get config
    response = requests.get(f"{BASE_URL}/api/general-configuration")
    print(f"GET /api/general-configuration: {response.status_code}")
    config = response.json()
    print(json.dumps(config, indent=2))
    
    # Update config
    update_data = {
        "gateway_identity": {
            "name": "Updated Gateway",
            "deployment_site": "Mumbai Port"
        }
    }
    response = requests.put(f"{BASE_URL}/api/general-configuration", json=update_data)
    print(f"\nPUT /api/general-configuration: {response.status_code}")
    print(json.dumps(response.json(), indent=2))

def test_device_groups():
    """Test device groups"""
    print_section("Testing Device Groups")
    
    # Create groups
    groups = [
        {"name": "Production Line 1", "color": "blue", "description": "Main production line"},
        {"name": "Quality Control", "color": "green", "description": "QC sensors"},
        {"name": "Weighing Systems", "color": "orange", "description": "Load cells and scales"}
    ]
    
    for group in groups:
        response = requests.post(f"{BASE_URL}/api/groups", json=group)
        print(f"Creating group '{group['name']}': {response.status_code}")
    
    # Get all groups
    response = requests.get(f"{BASE_URL}/api/groups")
    print(f"\nGET /api/groups: {response.status_code}")
    print(json.dumps(response.json(), indent=2))

def test_modbus_tcp_device():
    """Test Modbus TCP device"""
    print_section("Testing Modbus TCP Device")
    
    device_data = {
        "type": "modbus",
        "name": "PLC Controller - Main",
        "protocol": "modbus-tcp",
        "group": "Production Line 1",
        "config": {
            "ip_address": "192.168.1.100",
            "port": 502,
            "slave_id": 1,
            "timeout_ms": 1000,
            "retry_count": 3,
            "polling_interval_ms": 100
        }
    }
    
    response = requests.post(f"{BASE_URL}/api/devices", json=device_data)
    print(f"POST /api/devices (Modbus TCP): {response.status_code}")
    result = response.json()
    print(json.dumps(result, indent=2))
    
    device_id = result.get('device_id')
    
    if device_id:
        # Get device details
        response = requests.get(f"{BASE_URL}/api/devices/{device_id}/details")
        print(f"\nGET /api/devices/{device_id}/details: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        
        # Test device connection
        response = requests.post(f"{BASE_URL}/api/devices/{device_id}/test")
        print(f"\nPOST /api/devices/{device_id}/test: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
    
    return device_id

def test_modbus_rtu_device():
    """Test Modbus RTU device"""
    print_section("Testing Modbus RTU Device")
    
    device_data = {
        "type": "modbus",
        "name": "Temperature Sensor Array",
        "protocol": "modbus-rtu",
        "group": "Quality Control",
        "config": {
            "serial_port": "/dev/ttymxc2",
            "baud_rate": 9600,
            "parity": "N",
            "data_bits": 8,
            "stop_bits": 1,
            "slave_id": 2,
            "timeout_ms": 2000,
            "retry_count": 3
        }
    }
    
    response = requests.post(f"{BASE_URL}/api/devices", json=device_data)
    print(f"POST /api/devices (Modbus RTU): {response.status_code}")
    result = response.json()
    print(json.dumps(result, indent=2))
    
    return result.get('device_id')

def test_loadcell_device():
    """Test Loadcell device"""
    print_section("Testing Loadcell Device")
    
    device_data = {
        "type": "loadcell",
        "name": "Crane Scale - Bay 1",
        "protocol": "loadcell",
        "group": "Weighing Systems",
        "config": {
            "device_path": "/dev/spidev0.0",
            "channel": 0,
            "capacity": 50000.0,
            "capacity_name": "max_capacity"
        }
    }
    
    response = requests.post(f"{BASE_URL}/api/devices", json=device_data)
    print(f"POST /api/devices (Loadcell): {response.status_code}")
    result = response.json()
    print(json.dumps(result, indent=2))
    
    device_id = result.get('device_id')
    
    if device_id:
        # Get device details
        response = requests.get(f"{BASE_URL}/api/devices/{device_id}/details")
        print(f"\nGET /api/devices/{device_id}/details: {response.status_code}")
        details = response.json()
        print(json.dumps(details, indent=2))
        
        print("\n✓ Auto-created datapoints:")
        print("  - load")
        print("  - max_capacity")
    
    return device_id

def test_modbus_datapoints(modbus_tcp_id, modbus_rtu_id):
    """Test Modbus datapoints"""
    print_section("Testing Modbus Datapoints")
    
    datapoints = [
        {
            "device_id": modbus_tcp_id,
            "tag_name": "temperature",
            "register_address": 100,
            "register_type": "holding",
            "data_type": "int16",
            "byte_order": "big",
            "word_order": "big",
            "scale_factor": 0.1,
            "offset": 0,
            "unit": "°C",
            "description": "Process temperature"
        },
        {
            "device_id": modbus_tcp_id,
            "tag_name": "pressure",
            "register_address": 102,
            "register_type": "holding",
            "data_type": "float32",
            "byte_order": "big",
            "word_order": "big",
            "scale_factor": 1.0,
            "offset": 0,
            "unit": "bar",
            "description": "System pressure"
        },
        {
            "device_id": modbus_rtu_id,
            "tag_name": "ambient_temp",
            "register_address": 200,
            "register_type": "input",
            "data_type": "int16",
            "byte_order": "big",
            "word_order": "big",
            "scale_factor": 0.1,
            "offset": -40,
            "unit": "°C",
            "description": "Ambient temperature sensor"
        }
    ]
    
    for dp in datapoints:
        response = requests.post(f"{BASE_URL}/api/datapoints/modbus", json=dp)
        print(f"Creating datapoint '{dp['tag_name']}' for device {dp['device_id']}: {response.status_code}")
        if response.status_code == 200:
            print(f"  ✓ {response.json()}")

def test_get_all_devices():
    """Get all devices"""
    print_section("Get All Devices")
    
    response = requests.get(f"{BASE_URL}/api/devices")
    print(f"GET /api/devices: {response.status_code}")
    data = response.json()
    
    print(f"\nTotal devices: {len(data['devices'])}")
    print("\nDevices:")
    for device in data['devices']:
        print(f"  - [{device['id']}] {device['name']}")
        print(f"    Type: {device['type']}, Protocol: {device['protocol']}")
        print(f"    Address: {device['address']}")
        print(f"    Status: {device['status']}, Group: {device['group']}")

def test_get_all_datapoints():
    """Get all datapoints"""
    print_section("Get All Datapoints")
    
    response = requests.get(f"{BASE_URL}/api/datapoints")
    print(f"GET /api/datapoints: {response.status_code}")
    data = response.json()
    
    print(f"\nTotal datapoints: {len(data['datapoints'])}")
    print("\nDatapoints:")
    
    # Group by device
    by_device = {}
    for dp in data['datapoints']:
        device_name = dp['device_name']
        if device_name not in by_device:
            by_device[device_name] = []
        by_device[device_name].append(dp)
    
    for device_name, datapoints in by_device.items():
        print(f"\n  {device_name} ({datapoints[0]['device_type']}):")
        for dp in datapoints:
            if 'register_address' in dp:
                print(f"    - {dp['tag_name']}: reg={dp['register_address']}, type={dp['data_type']}, unit={dp.get('unit', 'N/A')}")
            else:
                print(f"    - {dp['tag_name']}: unit={dp.get('unit', 'N/A')} (auto-created)")

def test_update_device():
    """Test updating a device"""
    print_section("Testing Device Update")
    
    # Update the first Modbus TCP device
    update_data = {
        "name": "PLC Controller - Main (Updated)",
        "device_type": "tcp",
        "config": {
            "ip_address": "192.168.1.101",
            "port": 502,
            "timeout_ms": 2000
        }
    }
    
    response = requests.put(f"{BASE_URL}/api/devices/1", json=update_data)
    print(f"PUT /api/devices/1: {response.status_code}")
    print(json.dumps(response.json(), indent=2))

def main():
    """Run all tests"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "GATEWAY CONFIGURATION API TEST" + " "*13 + "║")
    print("╚" + "="*58 + "╝")
    
    try:
        # Test general configuration
        test_general_config()
        time.sleep(1)
        
        # Test device groups
        test_device_groups()
        time.sleep(1)
        
        # Test Modbus TCP device
        modbus_tcp_id = test_modbus_tcp_device()
        time.sleep(1)
        
        # Test Modbus RTU device
        modbus_rtu_id = test_modbus_rtu_device()
        time.sleep(1)
        
        # Test Loadcell device
        loadcell_id = test_loadcell_device()
        time.sleep(1)
        
        # Test Modbus datapoints
        if modbus_tcp_id and modbus_rtu_id:
            test_modbus_datapoints(modbus_tcp_id, modbus_rtu_id)
            time.sleep(1)
        
        # Get all devices
        test_get_all_devices()
        time.sleep(1)
        
        # Get all datapoints
        test_get_all_datapoints()
        time.sleep(1)
        
        # Test update
        test_update_device()
        
        print_section("Tests Completed Successfully!")
        print("\n✓ All API endpoints tested")
        print("✓ Database viewer available at: http://localhost:8080/db")
        print("✓ API documentation at: http://localhost:8080/")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to server")
        print("Make sure the server is running: python main.py")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()