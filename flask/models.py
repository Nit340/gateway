# models.py - Data models and shared state
import datetime

# In-memory real-time state with previous values for comparison
realtime_state = {
    'current_date': datetime.datetime.now().strftime('%Y-%m-%d'),
    'current_time': datetime.datetime.now().strftime('%H:%M'),
    'wifi_signal_strength': 3  # Default signal strength
}

# Track previous values to detect changes
previous_state = {
    'current_date': '',
    'current_time': '',
    'wifi_signal_strength': None,
    'wifi_configured': False
}

# Track network mode to detect changes
current_network_mode = 'ethernet'

# Device status tracking (not in database)
device_status_tracker = {}

# Active scans
active_scans = {}

# Wireless pairing sessions
pairing_sessions = {}

# WebSocket connections
connected_websockets = set()
device_websockets = set()