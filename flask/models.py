# models.py - Data models and shared state
import datetime

# In-memory real-time state with previous values for comparison
realtime_state = {
    'current_date':        datetime.datetime.now().strftime('%Y-%m-%d'),
    'current_time':        datetime.datetime.now().strftime('%H:%M'),
    'wifi_signal_strength': 3   # 0–4 scale; updated by OS probe or WebSocket request
}

# Track previous values to detect changes
previous_state = {
    'current_date': '',
    'current_time': ''
}

# Device status tracking (not in database)
device_status_tracker = {}

# WebSocket connections
connected_websockets = set()
device_websockets = set()