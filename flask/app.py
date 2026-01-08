from flask import Flask, request, jsonify
import json
from datetime import datetime
import random

app = Flask(__name__)

# In-memory config storage
config_data = {
    "gateway_identity": {
        "name": "Univa-GW-01",
        "serial_number": "GW2025-1190021",
        "deployment_site": "Chennai Port - Zone A",
        "location_mode": "manual",
        "latitude": 12.99123,
        "longitude": 80.12312,
        "asset_id": "CRN-CT-12"
    },
    "date_time": {
        "timezone": "Asia/Kolkata",
        "ntp_server": "pool.ntp.org",
        "date_format": "DD/MM/YYYY",
        "time_format": "24-Hour",
        "language": "English"
    },
    "network": {
        "mode": "ethernet",
        "ethernet": {
            "ip_assignment": "dhcp",
            "static_ip": "192.168.1.50",
            "subnet_mask": "255.255.255.0",
            "gateway": "192.168.1.1",
            "dns1": "8.8.8.8",
            "dns2": "8.8.4.4"
        }
    },
    "heartbeat": {
        "interval": 30,
        "offline_threshold": 120
    }
}

@app.route('/api/general-configuration', methods=['PUT'])
def save_config():
    """Save configuration"""
    try:
        if not request.data:
            return jsonify({
                "success": False,
                "message": "No data provided"
            }), 400
        
        data = json.loads(request.data.decode('utf-8'))
        
        # Update config
        update_nested_dict(config_data, data)
        
        return jsonify({
            "success": True,
            "message": "Configuration saved successfully"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Error: " + str(e)
        }), 500

def update_nested_dict(target, source):
    """Update nested dictionary"""
    for key, value in source.items():
        if isinstance(value, dict) and key in target and isinstance(target[key], dict):
            update_nested_dict(target[key], value)
        else:
            target[key] = value

@app.route('/api/general-configuration/wifi-scan', methods=['POST'])
def wifi_scan():
    """Scan WiFi networks"""
    try:
        # Simulated WiFi networks
        networks = [
            {"ssid": "Port_WiFi_5G", "signal": random.randint(3, 4), "encryption": "WPA2"},
            {"ssid": "Guest_WiFi", "signal": random.randint(2, 3), "encryption": "WPA2"},
            {"ssid": "CraneIQ_Network", "signal": random.randint(3, 4), "encryption": "WPA3"}
        ]
        
        return jsonify({
            "success": True,
            "networks": networks
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Error: " + str(e)
        }), 500

@app.route('/api/general-configuration/time-sync', methods=['POST'])
def time_sync():
    """Sync time"""
    try:
        now = datetime.now()
        
        return jsonify({
            "success": True,
            "message": "Time synchronized successfully",
            "current_time": now.strftime('%H:%M'),
            "current_date": now.strftime('%Y-%m-%d')
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Error: " + str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        "status": "ok",
        "service": "config-api",
        "timestamp": datetime.now().isoformat()
    })

# Simple CORS handler
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

@app.route('/', methods=['OPTIONS'])
@app.route('/api/<path:path>', methods=['OPTIONS'])
def handle_options(path=None):
    """Handle CORS preflight requests"""
    return '', 200

if __name__ == '__main__':
    # Run on port 5000
    app.run(host='0.0.0.0', port=5000, debug=False)