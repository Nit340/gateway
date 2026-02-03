# database.py - Database initialization and operations
import sqlite3
from datetime import datetime

DB_FILE = 'config.db'

def init_database():
    """Initialize SQLite database with corrected schema"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Drop all existing tables to start fresh
    drop_tables(cursor)
    
    # Create new tables with proper schema
    create_tables(cursor)
    
    # Insert default data
    insert_default_data(cursor)
    
    conn.commit()
    conn.close()
    print("Database initialized with corrected schema")
    print("✓ General config table (no JSON)")
    print("✓ Services table (only names)")
    print("✓ Modbus_device table (with connection details)")
    print("✓ Loadcell_device table (with calibration)")
    print("✓ Network config matching JSON structure")
    print("✓ Modbus_datapoints table")
    print("✓ Loadcell_datapoints table (name only)")
    print("✓ Dynamic device groups (no fixed groups)")

def drop_tables(cursor):
    """Drop all existing tables"""
    tables = [
        'loadcell_datapoints',
        'modbus_datapoints',
        'network_configuration',
        'loadcell_device',
        'modbus_device',
        'device_groups',
        'services',
        'general_configuration'
    ]
    
    for table in tables:
        cursor.execute(f'DROP TABLE IF EXISTS {table}')

def create_tables(cursor):
    """Create all tables with proper schema"""
    
    # General configuration table - NO JSON, all columns
    cursor.execute('''
        CREATE TABLE general_configuration (
            id INTEGER PRIMARY KEY,
            
            -- Gateway Identity
            gateway_name TEXT DEFAULT 'Univa-GW-01',
            serial_number TEXT DEFAULT 'GW2025-1190021',
            deployment_site TEXT DEFAULT 'Chennai Port - Zone A',
            location_mode TEXT DEFAULT 'manual',
            latitude REAL DEFAULT 12.99123,
            longitude REAL DEFAULT 80.12312,
            asset_id TEXT DEFAULT 'CRN-CT-12',
            mac_address TEXT DEFAULT '00:1A:2B:3C:4D:5E',
            
            -- Date & Time
            timezone TEXT DEFAULT 'Asia/Kolkata',
            ntp_server TEXT DEFAULT 'pool.ntp.org',
            date_format TEXT DEFAULT 'DD/MM/YYYY',
            time_format TEXT DEFAULT '24-hour',
            language TEXT DEFAULT 'en',
            
            -- Heartbeat
            heartbeat_interval INTEGER DEFAULT 30,
            offline_threshold INTEGER DEFAULT 120,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Services table - ONLY names (no connection details)
    cursor.execute('''
        CREATE TABLE services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Device groups table - DYNAMIC, users create any groups
    cursor.execute('''
        CREATE TABLE device_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT DEFAULT 'blue',
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Modbus device table - with ALL connection details
    cursor.execute('''
        CREATE TABLE modbus_device (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            device_type TEXT NOT NULL CHECK(device_type IN ('tcp', 'rtu')),
            group_id INTEGER,
            service_id INTEGER,
            
            -- Common modbus config
            slave_id INTEGER DEFAULT 1,
            timeout_ms INTEGER DEFAULT 1000,
            retry_count INTEGER DEFAULT 3,
            polling_interval_ms INTEGER DEFAULT 100,
            
            -- TCP specific
            ip_address TEXT,
            port INTEGER DEFAULT 502,
            
            -- RTU specific
            serial_port TEXT DEFAULT '/dev/ttymxc2',
            baud_rate INTEGER DEFAULT 9600,
            parity TEXT DEFAULT 'N',
            data_bits INTEGER DEFAULT 8,
            stop_bits INTEGER DEFAULT 1,
            
            -- Status
            enabled BOOLEAN DEFAULT 1,
            status TEXT DEFAULT 'offline',
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES device_groups(id),
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    ''')
    
    # Loadcell device table - with ALL calibration details
    cursor.execute('''
        CREATE TABLE loadcell_device (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            group_id INTEGER,
            service_id INTEGER,
            
            -- Device connection
            device_path TEXT NOT NULL,
            channel INTEGER DEFAULT 0,
            
            -- Calibration (all calibration here)
            tare_offset REAL DEFAULT 0.0,
            known_weight REAL DEFAULT 1000.0,
            known_weight_raw REAL DEFAULT 0.0,
            shift_bits INTEGER DEFAULT 10,
            unit TEXT DEFAULT 'g',
            capacity REAL DEFAULT 40000.0,
            
            -- Service settings
            pipeline_server TEXT DEFAULT '127.0.0.1',
            pipeline_port INTEGER DEFAULT 7000,
            log_level TEXT DEFAULT 'info',
            polling_interval_ms INTEGER DEFAULT 15,
            
            -- Filters (as per JSON reference)
            lowpass_filter_enabled BOOLEAN DEFAULT 0,
            filter_cutoff_frequency REAL DEFAULT 8.0,
            filter_activation_delta_min REAL DEFAULT 20000.0,
            moving_avg_enabled BOOLEAN DEFAULT 1,
            moving_avg_window INTEGER DEFAULT 4,
            median_filter_enabled BOOLEAN DEFAULT 1,
            median_filter_window INTEGER DEFAULT 3,
            autotare_enabled BOOLEAN DEFAULT 1,
            autotare_trigger_delta_grams REAL DEFAULT -5.0,
            adaptive_deadband_enabled BOOLEAN DEFAULT 1,
            adaptive_deadband_min REAL DEFAULT 1.0,
            adaptive_deadband_max REAL DEFAULT 20.0,
            adaptive_deadband_grow_rate REAL DEFAULT 0.5,
            adaptive_deadband_shrink_rate REAL DEFAULT 1.5,
            publish_step_grams REAL DEFAULT 5.0,
            overload_threshold REAL DEFAULT 5000.0,
            overload_relay TEXT DEFAULT 'relay2',
            overload_action INTEGER DEFAULT 0,
            overload_cooldown_ms INTEGER DEFAULT 2000,
            confirm_count INTEGER DEFAULT 3,
            capacity_name TEXT DEFAULT 'capacity',
            
            -- Status
            enabled BOOLEAN DEFAULT 1,
            status TEXT DEFAULT 'offline',
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES device_groups(id),
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    ''')
    
    # Network configuration table - MATCHING JSON STRUCTURE from network.json
    cursor.execute('''
        CREATE TABLE network_configuration (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            -- Service settings (as per JSON)
            service_name TEXT DEFAULT 'network_status',
            polling_interval_ms INTEGER DEFAULT 1000,
            push_on_change BOOLEAN DEFAULT 1,
            log_level TEXT DEFAULT 'info',
            
            -- DBus settings
            use_dbus BOOLEAN DEFAULT 1,
            network_manager_service TEXT DEFAULT 'org.freedesktop.NetworkManager',
            modem_manager_service TEXT DEFAULT 'org.freedesktop.ModemManager1',
            dbus_timeout_ms INTEGER DEFAULT 1000,
            
            -- LAN monitoring
            lan_enabled BOOLEAN DEFAULT 1,
            lan_datapoint TEXT DEFAULT 'network_lan',
            lan_interfaces TEXT DEFAULT 'eth0,eth1',  -- Comma-separated
            lan_require_ip BOOLEAN DEFAULT 1,
            
            -- WiFi monitoring (NO SUBNET/GATEWAY/DNS)
            wifi_enabled BOOLEAN DEFAULT 1,
            wifi_interface TEXT DEFAULT 'wlan0',
            wifi_datapoint TEXT DEFAULT 'network_wifi',
            wifi_min_rssi INTEGER DEFAULT -90,
            
            -- LTE monitoring (NO SUBNET/GATEWAY/DNS)
            lte_enabled BOOLEAN DEFAULT 1,
            lte_datapoint TEXT DEFAULT 'network_tower',
            lte_min_rsrp INTEGER DEFAULT -110,
            
            -- Performance settings
            max_consecutive_failures INTEGER DEFAULT 3,
            stats_log_interval_sec INTEGER DEFAULT 300,
            detailed_logging BOOLEAN DEFAULT 1,
            log_connection_details_once BOOLEAN DEFAULT 1,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Modbus datapoints table
    cursor.execute('''
        CREATE TABLE modbus_datapoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            name TEXT NOT NULL,
            address INTEGER NOT NULL,
            register_type TEXT NOT NULL CHECK(register_type IN ('coil', 'discrete', 'holding', 'input')),
            data_type TEXT NOT NULL CHECK(data_type IN ('bool', 'int16', 'int32', 'float32', 'string')),
            scale REAL DEFAULT 1.0,
            offset REAL DEFAULT 0.0,
            byte_order TEXT DEFAULT 'big',
            word_order TEXT DEFAULT 'big',
            writable BOOLEAN DEFAULT 0,
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(device_id, name),
            FOREIGN KEY (device_id) REFERENCES modbus_device(id) ON DELETE CASCADE
        )
    ''')
    
    # Loadcell datapoints table - ONLY name (no other config)
    cursor.execute('''
        CREATE TABLE loadcell_datapoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            name TEXT NOT NULL CHECK(name IN ('load', 'capacity')),
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(device_id, name),
            FOREIGN KEY (device_id) REFERENCES loadcell_device(id) ON DELETE CASCADE
        )
    ''')

def insert_default_data(cursor):
    """Insert default data into all tables"""
    
    # Insert default general configuration
    cursor.execute('''
        INSERT INTO general_configuration 
        (gateway_name, serial_number, deployment_site, location_mode, 
         latitude, longitude, asset_id, mac_address, timezone, ntp_server,
         date_format, time_format, language, heartbeat_interval, offline_threshold)
        VALUES 
        ('Univa-GW-01', 'GW2025-1190021', 'Chennai Port - Zone A', 'manual',
         12.99123, 80.12312, 'CRN-CT-12', '00:1A:2B:3C:4D:5E', 'Asia/Kolkata', 'pool.ntp.org',
         'DD/MM/YYYY', '24-hour', 'en', 30, 120)
    ''')
    
    # Insert services (names only)
    default_services = [
        ('modbus_service', 'Modbus communication service'),
        ('loadcell_service', 'Load cell measurement service'),
        ('network_service', 'Network management service'),
        ('core_service', 'Core system service')
    ]
    
    for service_name, description in default_services:
        cursor.execute('''
            INSERT INTO services (name, description)
            VALUES (?, ?)
        ''', (service_name, description))
    
    # Insert ONE default device group (optional, users can create more)
    cursor.execute('''
        INSERT OR IGNORE INTO device_groups (name, color, description)
        VALUES (?, ?, ?)
    ''', ('Default', 'blue', 'Default device group'))
    
    # Insert network configuration MATCHING JSON structure
    cursor.execute('''
        INSERT INTO network_configuration 
        (service_name, polling_interval_ms, push_on_change, log_level,
         use_dbus, network_manager_service, modem_manager_service, dbus_timeout_ms,
         lan_enabled, lan_datapoint, lan_interfaces, lan_require_ip,
         wifi_enabled, wifi_interface, wifi_datapoint, wifi_min_rssi,
         lte_enabled, lte_datapoint, lte_min_rsrp,
         max_consecutive_failures, stats_log_interval_sec, detailed_logging, 
         log_connection_details_once)
        VALUES 
        ('network_status', 1000, 1, 'info',
         1, 'org.freedesktop.NetworkManager', 'org.freedesktop.ModemManager1', 1000,
         1, 'network_lan', 'eth0,eth1', 1,
         1, 'wlan0', 'network_wifi', -90,
         1, 'network_tower', -110,
         3, 300, 1, 1)
    ''')
    
    print("Default data inserted successfully")

# ==============================================
# DATABASE OPERATION FUNCTIONS
# ==============================================

def create_device_group(group_data):
    """Create a new device group (dynamic)"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO device_groups (name, color, description)
            VALUES (?, ?, ?)
        ''', (
            group_data.get('name'),
            group_data.get('color', 'blue'),
            group_data.get('description', '')
        ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error creating device group: {e}")
        return False

def get_all_device_groups():
    """Get all device groups"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, color, description, created_at
            FROM device_groups
            ORDER BY name
        ''')
        
        groups = []
        for row in cursor.fetchall():
            groups.append({
                'id': row[0],
                'name': row[1],
                'color': row[2],
                'description': row[3],
                'created_at': row[4]
            })
        
        conn.close()
        return groups
    except Exception as e:
        print(f"Error getting device groups: {e}")
        return []

def add_modbus_device(device_data):
    """Add a new modbus device (TCP or RTU)"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Get service ID for modbus_service
        cursor.execute("SELECT id FROM services WHERE name = 'modbus_service'")
        service_row = cursor.fetchone()
        service_id = service_row[0] if service_row else None
        
        cursor.execute('''
            INSERT INTO modbus_device 
            (id, name, device_type, group_id, service_id, 
             slave_id, timeout_ms, retry_count, polling_interval_ms,
             ip_address, port, serial_port, baud_rate, parity, data_bits, stop_bits,
             enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            device_data.get('id'),
            device_data.get('name'),
            device_data.get('device_type'),  # 'tcp' or 'rtu'
            device_data.get('group_id'),
            service_id,
            device_data.get('slave_id', 1),
            device_data.get('timeout_ms', 1000),
            device_data.get('retry_count', 3),
            device_data.get('polling_interval_ms', 100),
            device_data.get('ip_address'),
            device_data.get('port', 502),
            device_data.get('serial_port', '/dev/ttymxc2'),
            device_data.get('baud_rate', 9600),
            device_data.get('parity', 'N'),
            device_data.get('data_bits', 8),
            device_data.get('stop_bits', 1),
            device_data.get('enabled', 1)
        ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding modbus device: {e}")
        return False

def add_loadcell_device(device_data):
    """Add a new loadcell device with calibration"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Get service ID for loadcell_service
        cursor.execute("SELECT id FROM services WHERE name = 'loadcell_service'")
        service_row = cursor.fetchone()
        service_id = service_row[0] if service_row else None
        
        cursor.execute('''
            INSERT INTO loadcell_device 
            (id, name, group_id, service_id, device_path, channel,
             tare_offset, known_weight, known_weight_raw, shift_bits, unit, capacity,
             pipeline_server, pipeline_port, log_level, polling_interval_ms,
             lowpass_filter_enabled, filter_cutoff_frequency, filter_activation_delta_min,
             moving_avg_enabled, moving_avg_window, median_filter_enabled, median_filter_window,
             autotare_enabled, autotare_trigger_delta_grams, adaptive_deadband_enabled,
             adaptive_deadband_min, adaptive_deadband_max, adaptive_deadband_grow_rate,
             adaptive_deadband_shrink_rate, publish_step_grams, overload_threshold,
             overload_relay, overload_action, overload_cooldown_ms, confirm_count, capacity_name,
             enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            device_data.get('id'),
            device_data.get('name'),
            device_data.get('group_id'),
            service_id,
            device_data.get('device_path'),
            device_data.get('channel', 0),
            device_data.get('tare_offset', 0.0),
            device_data.get('known_weight', 1000.0),
            device_data.get('known_weight_raw', 0.0),
            device_data.get('shift_bits', 10),
            device_data.get('unit', 'g'),
            device_data.get('capacity', 40000.0),
            device_data.get('pipeline_server', '127.0.0.1'),
            device_data.get('pipeline_port', 7000),
            device_data.get('log_level', 'info'),
            device_data.get('polling_interval_ms', 15),
            device_data.get('lowpass_filter_enabled', 0),
            device_data.get('filter_cutoff_frequency', 8.0),
            device_data.get('filter_activation_delta_min', 20000.0),
            device_data.get('moving_avg_enabled', 1),
            device_data.get('moving_avg_window', 4),
            device_data.get('median_filter_enabled', 1),
            device_data.get('median_filter_window', 3),
            device_data.get('autotare_enabled', 1),
            device_data.get('autotare_trigger_delta_grams', -5.0),
            device_data.get('adaptive_deadband_enabled', 1),
            device_data.get('adaptive_deadband_min', 1.0),
            device_data.get('adaptive_deadband_max', 20.0),
            device_data.get('adaptive_deadband_grow_rate', 0.5),
            device_data.get('adaptive_deadband_shrink_rate', 1.5),
            device_data.get('publish_step_grams', 5.0),
            device_data.get('overload_threshold', 5000.0),
            device_data.get('overload_relay', 'relay2'),
            device_data.get('overload_action', 0),
            device_data.get('overload_cooldown_ms', 2000),
            device_data.get('confirm_count', 3),
            device_data.get('capacity_name', 'capacity'),
            device_data.get('enabled', 1)
        ))
        
        # Automatically create the 2 datapoints
        device_id = device_data.get('id')
        cursor.execute('''
            INSERT INTO loadcell_datapoints (device_id, name)
            VALUES 
            (?, 'load'),
            (?, 'capacity')
        ''', (device_id, device_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding loadcell device: {e}")
        return False

def get_network_configuration():
    """Get network configuration matching JSON structure"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                service_name, polling_interval_ms, push_on_change, log_level,
                use_dbus, network_manager_service, modem_manager_service, dbus_timeout_ms,
                lan_enabled, lan_datapoint, lan_interfaces, lan_require_ip,
                wifi_enabled, wifi_interface, wifi_datapoint, wifi_min_rssi,
                lte_enabled, lte_datapoint, lte_min_rsrp,
                max_consecutive_failures, stats_log_interval_sec, detailed_logging, 
                log_connection_details_once
            FROM network_configuration 
            WHERE id = 1
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            columns = [
                'service_name', 'polling_interval_ms', 'push_on_change', 'log_level',
                'use_dbus', 'network_manager_service', 'modem_manager_service', 'dbus_timeout_ms',
                'lan_enabled', 'lan_datapoint', 'lan_interfaces', 'lan_require_ip',
                'wifi_enabled', 'wifi_interface', 'wifi_datapoint', 'wifi_min_rssi',
                'lte_enabled', 'lte_datapoint', 'lte_min_rsrp',
                'max_consecutive_failures', 'stats_log_interval_sec', 'detailed_logging',
                'log_connection_details_once'
            ]
            config = dict(zip(columns, row))
            
            # Convert comma-separated interfaces to list
            if config['lan_interfaces']:
                config['lan_interfaces'] = [iface.strip() for iface in config['lan_interfaces'].split(',')]
            
            return config
        
        return {}
    except Exception as e:
        print(f"Error getting network config: {e}")
        return {}

def update_network_configuration(config_data):
    """Update network configuration"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Convert interfaces list to comma-separated string
        if 'lan_interfaces' in config_data and isinstance(config_data['lan_interfaces'], list):
            config_data['lan_interfaces'] = ','.join(config_data['lan_interfaces'])
        
        # Build SET clause dynamically
        set_clause = []
        values = []
        
        for key, value in config_data.items():
            set_clause.append(f"{key} = ?")
            values.append(value)
        
        values.append(1)  # For WHERE id = 1
        
        query = f'''
            UPDATE network_configuration 
            SET {', '.join(set_clause)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        '''
        
        cursor.execute(query, values)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating network config: {e}")
        return False

def get_database_stats():
    """Get database statistics"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Count modbus devices
        cursor.execute('SELECT COUNT(*) FROM modbus_device')
        modbus_count = cursor.fetchone()[0]
        
        # Count loadcell devices
        cursor.execute('SELECT COUNT(*) FROM loadcell_device')
        loadcell_count = cursor.fetchone()[0]
        
        # Count modbus datapoints
        cursor.execute('SELECT COUNT(*) FROM modbus_datapoints')
        modbus_datapoint_count = cursor.fetchone()[0]
        
        # Count loadcell datapoints
        cursor.execute('SELECT COUNT(*) FROM loadcell_datapoints')
        loadcell_datapoint_count = cursor.fetchone()[0]
        
        # Count groups
        cursor.execute('SELECT COUNT(*) FROM device_groups')
        group_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'modbus_devices': modbus_count,
            'loadcell_devices': loadcell_count,
            'total_devices': modbus_count + loadcell_count,
            'modbus_datapoints': modbus_datapoint_count,
            'loadcell_datapoints': loadcell_datapoint_count,
            'total_datapoints': modbus_datapoint_count + loadcell_datapoint_count,
            'groups': group_count
        }
    except Exception as e:
        print(f"Error getting stats: {e}")
        return {}

def test_database_structure():
    """Test database structure"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        print("\n=== Database Structure ===")
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            print(f"\nTable: {table_name}")
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  Rows: {count}")
        
        conn.close()
        return True
    except Exception as e:
        print(f"Error testing database structure: {e}")
        return False

# Initialize database when module is imported
if __name__ == '__main__':
    print("Initializing database with corrected schema...")
    init_database()
    
    # Test the database
    print("\n=== Database Statistics ===")
    stats = get_database_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    print("\n=== Device Groups ===")
    groups = get_all_device_groups()
    for group in groups:
        print(f"{group['name']} ({group['color']}): {group['description']}")
    
    print("\n=== Network Configuration ===")
    network_config = get_network_configuration()
    print(f"Service: {network_config.get('service_name')}")
    print(f"LAN Interfaces: {network_config.get('lan_interfaces')}")
    print(f"WiFi Interface: {network_config.get('wifi_interface')}")
    
else:
    # Auto-initialize when module is imported
    init_database()