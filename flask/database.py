# database.py - Database initialization and operations
import sqlite3
import json

DB_FILE = 'gateway_config.db'

def init_database():
    """Initialize SQLite database with empty tables - NO DEFAULT DATA"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # General configuration table (existing)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS general_configuration (
            id INTEGER PRIMARY KEY,
            config_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Device management tables (new)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT DEFAULT 'blue',
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_management (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            address TEXT,
            firmware_version TEXT DEFAULT '1.0.0',
            group_id INTEGER,
            config_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES device_groups(id)
        )
    ''')
    
    # Check for general configuration - INSERT ONLY IF EMPTY
    cursor.execute('SELECT COUNT(*) FROM general_configuration')
    count = cursor.fetchone()[0]
    
    if count == 0:
        default_config = {
            'gateway_identity': {
                'name': 'Univa-GW-01',
                'serial_number': 'GW2025-1190021',
                'deployment_site': 'Chennai Port - Zone A',
                'location_mode': 'manual',
                'latitude': 12.99123,
                'longitude': 80.12312,
                'asset_id': 'CRN-CT-12'
            },
            'date_time': {
                'timezone': 'Asia/Kolkata',
                'ntp_server': 'pool.ntp.org',
                'date_format': 'DD/MM/YYYY',
                'time_format': '24-hour',
                'language': 'en'
            },
            'network': {
                'mode': 'ethernet',
                'ethernet': {
                    'ip_assignment': 'dhcp',
                    'static_ip': '192.168.1.50',
                    'subnet_mask': '255.255.255.0',
                    'gateway': '192.168.1.1',
                    'dns1': '8.8.8.8',
                    'dns2': '8.8.4.4'
                }
            },
            'heartbeat': {
                'interval': 30,
                'offline_threshold': 120
            },
            'mac_address': '00:1A:2B:3C:4D:5E'
        }
        cursor.execute('''
            INSERT INTO general_configuration (config_json)
            VALUES (?)
        ''', (json.dumps(default_config),))
    
    conn.commit()
    conn.close()
    print("Database initialized with empty device management tables")
    print("No default devices or groups inserted")

def get_configuration():
    """Retrieve configuration from database as single JSON"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT config_json FROM general_configuration WHERE id = 1')
    row = cursor.fetchone()
    
    conn.close()
    
    if row and row[0]:
        try:
            return json.loads(row[0])
        except:
            return {}
    
    return {}

def update_configuration(config_data):
    """Update configuration in database as single JSON"""
    try:
        current = get_configuration()
        
        for key in config_data:
            if key in current and isinstance(current[key], dict) and isinstance(config_data[key], dict):
                current[key].update(config_data[key])
            else:
                current[key] = config_data[key]
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE general_configuration 
            SET config_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        ''', (json.dumps(current),))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("Error updating configuration: {}".format(e))
        return False