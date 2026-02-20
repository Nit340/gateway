# -*- coding: utf-8 -*-
# database.py - Database initialization and operations
import sqlite3
import json
from datetime import datetime

DB_FILE = 'gateway_config.db'

def get_db_connection():
    """Get a database connection with proper timeout and WAL mode for concurrency"""
    conn = sqlite3.connect(DB_FILE, timeout=10.0)
    conn.execute('PRAGMA journal_mode=WAL')  # Write-Ahead Logging for better concurrency
    conn.execute('PRAGMA foreign_keys = ON')  # Enable foreign key constraints (including CASCADE)
    return conn

def init_database():
    """Initialize SQLite database with new schema
    
    DEVICE ID SYSTEM:
    - LoadCell devices use ID prefix: LC1, LC2, LC3, etc.
    - Modbus devices use ID prefix: MB1, MB2, MB3, etc.
    - This prevents ID collisions between different device types
    - IDs are generated in device_management.py during device creation
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Drop legacy SQL view if it exists (uses json_object which requires JSON1 extension
    # compiled into SQLite -- not guaranteed on all builds). Replaced by Python function.
    cursor.execute('DROP VIEW IF EXISTS modbus_device_config_view')

    # Create all tables
    create_tables(cursor)
    
    # Insert default data
    insert_default_data(cursor)
    
    conn.commit()
    conn.close()
    print("Database initialized with new schema")
    print("[OK] General configuration table (no JSON)")
    print("[OK] Services table (modbus, loadcell)")
    print("[OK] Modbus_device table (tcp/rtu with connection details) - NO status column")
    print("[OK] Loadcell_device table (with calibration) - NO status column")
    print("[OK] Modbus_datapoints table")
    print("[OK] Loadcell_datapoints table (auto-created: load, capacity)")
    print("[OK] Dynamic device groups")
    print("[OK] Status and last_poll handled via WebSocket real-time only")
    print("[OK] Device IDs: LoadCell=LC1,LC2... Modbus=MB1,MB2... (NO COLLISIONS)")
    print("[OK] Cloud Integration: cloud_connections | mqtt_datapoints | http_datapoints | ftp_datapoints | cloud_connection_stats")

def create_tables(cursor):
    """Create all tables with proper schema"""
    
    # General configuration table - NO JSON, all columns
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS general_configuration (
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
    
    # Services table - ONLY names (modbus and loadcell)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Device groups table - DYNAMIC, users create any groups
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT DEFAULT 'blue',
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Modbus device table - NO STATUS COLUMN (status is real-time via WebSocket)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS modbus_device (
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
            
            -- Only enabled flag, no status
            enabled BOOLEAN DEFAULT 1,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES device_groups(id),
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    ''')
    
    # Loadcell device table - NO STATUS COLUMN (status is real-time via WebSocket)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS loadcell_device (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            group_id INTEGER,
            service_id INTEGER,
            
            -- Device connection
            device_path TEXT NOT NULL,
            channel INTEGER DEFAULT 0,
            
            -- Calibration
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
            
            -- Filters
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
            
            -- Only enabled flag, no status
            enabled BOOLEAN DEFAULT 1,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES device_groups(id),
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    ''')
    
    # Modbus datapoints table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS modbus_datapoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            name TEXT NOT NULL,
            register_address INTEGER NOT NULL,
            register_type TEXT NOT NULL CHECK(register_type IN ('holding', 'input', 'coil', 'discrete')),
            data_type TEXT NOT NULL CHECK(data_type IN ('int16', 'uint16', 'int32', 'uint32', 'float32', 'bool')),
            byte_order TEXT DEFAULT 'big',
            word_order TEXT DEFAULT 'big',
            scale_factor REAL DEFAULT 1.0,
            offset REAL DEFAULT 0.0,
            unit TEXT,
            description TEXT,
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(device_id, name),
            FOREIGN KEY (device_id) REFERENCES modbus_device(id) ON DELETE CASCADE
        )
    ''')
    
    # Loadcell datapoints table - ONLY name (auto-created)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS loadcell_datapoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(device_id, name),
            FOREIGN KEY (device_id) REFERENCES loadcell_device(id) ON DELETE CASCADE
        )
    ''')

    # -- Cloud Integration -----------------------------------------------------
    # cloud_connections: one row per broker/endpoint (mqtt, http, or ftp)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cloud_connections (
            id         TEXT PRIMARY KEY,
            type       TEXT NOT NULL CHECK(type IN ('mqtt','http','ftp')),
            name       TEXT NOT NULL,
            enabled    INTEGER DEFAULT 1,
            config     TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # mqtt_datapoints: tags published via a specific MQTT connection
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mqtt_datapoints (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_id    TEXT NOT NULL,
            tag_name         TEXT NOT NULL,
            topic            TEXT NOT NULL DEFAULT '',
            publish_mode     TEXT NOT NULL DEFAULT 'onChange',
            change_threshold REAL DEFAULT 0.0,
            enabled          INTEGER DEFAULT 1,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(connection_id, tag_name),
            FOREIGN KEY (connection_id) REFERENCES cloud_connections(id) ON DELETE CASCADE
        )
    ''')

    # http_datapoints: tags published via a specific HTTP connection
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS http_datapoints (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_id      TEXT NOT NULL,
            tag_name           TEXT NOT NULL,
            field_name         TEXT NOT NULL DEFAULT '',
            publish_mode       TEXT NOT NULL DEFAULT 'onChange',
            include_unit       INTEGER DEFAULT 1,
            include_timestamp  INTEGER DEFAULT 1,
            enabled            INTEGER DEFAULT 1,
            created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(connection_id, tag_name),
            FOREIGN KEY (connection_id) REFERENCES cloud_connections(id) ON DELETE CASCADE
        )
    ''')

    # ftp_datapoints: tags exported via a specific FTP connection
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ftp_datapoints (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_id    TEXT NOT NULL,
            tag_name         TEXT NOT NULL,
            column_name      TEXT NOT NULL DEFAULT '',
            include_unit     INTEGER DEFAULT 1,
            include_timestamp INTEGER DEFAULT 1,
            enabled          INTEGER DEFAULT 1,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(connection_id, tag_name),
            FOREIGN KEY (connection_id) REFERENCES cloud_connections(id) ON DELETE CASCADE
        )
    ''')

    # cloud_connection_stats: runtime counters per connection
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cloud_connection_stats (
            connection_id   TEXT PRIMARY KEY,
            messages_total  INTEGER DEFAULT 0,
            messages_ok     INTEGER DEFAULT 0,
            messages_failed INTEGER DEFAULT 0,
            latency_avg_ms  REAL    DEFAULT 0.0,
            last_active     TEXT    DEFAULT NULL,
            FOREIGN KEY (connection_id) REFERENCES cloud_connections(id) ON DELETE CASCADE
        )
    ''')
    
    # -- Modbus Device Config VIEW -------------------------------------------------
    # NOTE: SQLite JSON functions (json_object, json_group_array) require SQLite 3.9.0+
    # which is not available on this system. The view has been replaced by the Python
    # function get_modbus_device_config_view() below, which produces identical output.

def insert_default_data(cursor):
    """Insert default data"""
    
    # Insert general configuration
    cursor.execute('SELECT COUNT(*) FROM general_configuration')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO general_configuration (id) VALUES (1)')
    
    # Insert default services
    for service in [
        ('modbus', 'Modbus Protocol Service'),
        ('loadcell', 'Loadcell Service')
    ]:
        cursor.execute('''
            INSERT OR IGNORE INTO services (name, description)
            VALUES (?, ?)
        ''', service)
    
    # Insert default device groups
    for group in [
        ('Crane-01', 'blue', 'Main Crane Devices'),
        ('Safety Sensors', 'red', 'Safety-critical sensors'),
        ('RTU Devices', 'green', 'RTU Communication Devices')
    ]:
        cursor.execute('''
            INSERT OR IGNORE INTO device_groups (name, color, description)
            VALUES (?, ?, ?)
        ''', group)

# -- Python replacement for modbus_device_config_view -------------------------
# Builds the same JSON config that the SQL view would have produced,
# but entirely in Python so it works with old SQLite (pre-3.9.0).

def get_modbus_device_config_view(device_id=None):
    """Return a list of dicts: {device_id, device_name, device_type, config}.
    config is a dict (not a string) matching the old SQL view's JSON shape.
    Pass device_id to filter to a single device."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if device_id:
            cursor.execute("""
                SELECT id, name, device_type, baud_rate, timeout_ms, data_bits,
                       serial_port, ip_address, retry_count, parity,
                       polling_interval_ms, stop_bits, slave_id, group_id
                FROM modbus_device WHERE enabled=1 AND id=?
            """, (device_id,))
        else:
            cursor.execute("""
                SELECT id, name, device_type, baud_rate, timeout_ms, data_bits,
                       serial_port, ip_address, retry_count, parity,
                       polling_interval_ms, stop_bits, slave_id, group_id
                FROM modbus_device WHERE enabled=1
            """)

        devices = cursor.fetchall()
        results = []

        parity_map = {'N': 'None', 'E': 'Even', 'O': 'Odd'}

        for d in devices:
            (d_id, d_name, d_type, baud_rate, timeout_ms, data_bits,
             serial_port, ip_address, retry_count, parity,
             polling_interval_ms, stop_bits, slave_id, group_id) = d

            # Resolve group name
            group_name = 'default_group'
            if group_id is not None:
                cursor.execute("SELECT name FROM device_groups WHERE id=?", (group_id,))
                row = cursor.fetchone()
                if row:
                    group_name = row[0]

            # Resolve datapoints
            cursor.execute("""
                SELECT register_address, data_type, name, register_type
                FROM modbus_datapoints
                WHERE device_id=? AND enabled=1
                ORDER BY register_address
            """, (d_id,))
            assets = []
            for dp in cursor.fetchall():
                assets.append({
                    'address':       dp[0],
                    'dataType':      dp[1],
                    'group':         group_name,
                    'name':          dp[2],
                    'registerCount': 1,
                    'registerType':  dp[3],
                    'slaveId':       slave_id
                })

            device_path = serial_port if d_type == 'rtu' else (ip_address or '127.0.0.1')

            config = {
                'system': {
                    'baud':                baud_rate or 9600,
                    'byteTimeoutMs':       (timeout_ms or 1000) * 2,
                    'dataBits':            data_bits or 8,
                    'device':              device_path or '/dev/ttymxc2',
                    'enablePacking':       True,
                    'interRequestDelayMs': 10,
                    'logLevel':            'info',
                    'maxBlockGap':         5,
                    'maxBlockSize':        125,
                    'maxRetries':          retry_count or 2,
                    'mode':                d_type,
                    'parity':              parity_map.get(parity or 'N', 'None'),
                    'pipelinePort':        7000,
                    'pipelineServer':      '127.0.0.1',
                    'pollingIntervalMs':   polling_interval_ms or 500,
                    'readStrategy':        'auto',
                    'responseTimeoutMs':   timeout_ms or 1000,
                    'serviceName':         'modbus',
                    'stopBits':            stop_bits or 1
                },
                'assets': assets
            }

            results.append({
                'device_id':   d_id,
                'device_name': d_name,
                'device_type': d_type,
                'config':      config
            })

        conn.close()
        return results
    except Exception as e:
        print("Error in get_modbus_device_config_view: {}".format(e))
        return []

def get_general_configuration():
    """Get general configuration"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT gateway_name, serial_number, deployment_site, location_mode,
                   latitude, longitude, asset_id, mac_address,
                   timezone, ntp_server, date_format, time_format, language,
                   heartbeat_interval, offline_threshold
            FROM general_configuration WHERE id = 1
        ''')
        
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return {}
        
        config = {
            'gateway_identity': {
                'name': row[0],
                'serial_number': row[1],
                'deployment_site': row[2],
                'location_mode': row[3],
                'latitude': row[4],
                'longitude': row[5],
                'asset_id': row[6]
            },
            'date_time': {
                'timezone': row[8],
                'ntp_server': row[9],
                'date_format': row[10],
                'time_format': row[11],
                'language': row[12]
            },
            'heartbeat': {
                'interval': row[13],
                'offline_threshold': row[14]
            },
            'mac_address': row[7]
        }
        
        conn.close()
        return config
    except Exception as e:
        print("Error getting general config: {}".format(e))
        return {}

def update_general_configuration(config_data):
    """Update general configuration"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Extract fields from nested structure
        updates = []
        values = []
        
        if 'gateway_identity' in config_data:
            gi = config_data['gateway_identity']
            if 'name' in gi:
                updates.append('gateway_name = ?')
                values.append(gi['name'])
            if 'serial_number' in gi:
                updates.append('serial_number = ?')
                values.append(gi['serial_number'])
            if 'deployment_site' in gi:
                updates.append('deployment_site = ?')
                values.append(gi['deployment_site'])
            if 'location_mode' in gi:
                updates.append('location_mode = ?')
                values.append(gi['location_mode'])
            if 'latitude' in gi:
                updates.append('latitude = ?')
                values.append(gi['latitude'])
            if 'longitude' in gi:
                updates.append('longitude = ?')
                values.append(gi['longitude'])
            if 'asset_id' in gi:
                updates.append('asset_id = ?')
                values.append(gi['asset_id'])
        
        if 'date_time' in config_data:
            dt = config_data['date_time']
            if 'timezone' in dt:
                updates.append('timezone = ?')
                values.append(dt['timezone'])
            if 'ntp_server' in dt:
                updates.append('ntp_server = ?')
                values.append(dt['ntp_server'])
            if 'date_format' in dt:
                updates.append('date_format = ?')
                values.append(dt['date_format'])
            if 'time_format' in dt:
                updates.append('time_format = ?')
                values.append(dt['time_format'])
            if 'language' in dt:
                updates.append('language = ?')
                values.append(dt['language'])
        
        if 'heartbeat' in config_data:
            hb = config_data['heartbeat']
            if 'interval' in hb:
                updates.append('heartbeat_interval = ?')
                values.append(hb['interval'])
            if 'offline_threshold' in hb:
                updates.append('offline_threshold = ?')
                values.append(hb['offline_threshold'])
        
        if 'mac_address' in config_data:
            updates.append('mac_address = ?')
            values.append(config_data['mac_address'])
        
        if updates:
            query = '''
                UPDATE general_configuration 
                SET {fields}, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            '''.format(fields=', '.join(updates))
            cursor.execute(query, values)
            conn.commit()
        
        conn.close()
        return True
    except Exception as e:
        print("Error updating general config: {}".format(e))
        return False

# Device Groups operations
def get_all_device_groups():
    """Get all device groups"""
    try:
        conn = get_db_connection()
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
        print("Error getting device groups: {}".format(e))
        return []

def add_device_group(name, color='blue', description=''):
    """Add a new device group"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO device_groups (name, color, description)
            VALUES (?, ?, ?)
        ''', (name, color, description))
        
        group_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return group_id
    except Exception as e:
        print("Error adding device group: {}".format(e))
        return None

def delete_device_group(group_id):
    """Delete a device group and unassign devices"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First, unassign all devices from this group (set group_id to NULL)
        cursor.execute('UPDATE modbus_device SET group_id = NULL WHERE group_id = ?', (group_id,))
        cursor.execute('UPDATE loadcell_device SET group_id = NULL WHERE group_id = ?', (group_id,))
        
        # Then delete the group
        cursor.execute('DELETE FROM device_groups WHERE id = ?', (group_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("Error deleting device group: {}".format(e))
        return False

# Services operations
def get_all_services():
    """Get all services"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, description, enabled
            FROM services
            ORDER BY name
        ''')
        
        services = []
        for row in cursor.fetchall():
            services.append({
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'enabled': row[3]
            })
        
        conn.close()
        return services
    except Exception as e:
        print("Error getting services: {}".format(e))
        return []

def get_service_by_name(name):
    """Get service ID by name"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM services WHERE name = ?', (name,))
        row = cursor.fetchone()
        
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print("Error getting service by name: {}".format(e))
        return None

# Database statistics
def get_database_stats():
    """Get database statistics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM modbus_device')
        modbus_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM loadcell_device')
        loadcell_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM modbus_datapoints')
        modbus_datapoint_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM loadcell_datapoints')
        loadcell_datapoint_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM device_groups')
        group_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM modbus_device WHERE enabled=1")
        view_device_count = cursor.fetchone()[0]

        conn.close()

        return {
            'modbus_devices': modbus_count,
            'loadcell_devices': loadcell_count,
            'total_devices': modbus_count + loadcell_count,
            'modbus_datapoints': modbus_datapoint_count,
            'loadcell_datapoints': loadcell_datapoint_count,
            'total_datapoints': modbus_datapoint_count + loadcell_datapoint_count,
            'groups': group_count,
            'views': {
                'modbus_device_config_view': {
                    'exists': True,
                    'enabled_devices': view_device_count,
                    'description': 'Python function replaces SQL view (SQLite JSON funcs unavailable)',
                    'query_all': 'get_modbus_device_config_view()',
                    'query_one': "get_modbus_device_config_view(device_id='MB1')",
                }
            }
        }
    except Exception as e:
        print("Error getting stats: {}".format(e))
        return {}

# Initialize database when module is imported
if __name__ == '__main__':
    print("Initializing database...")
    init_database()
    
    print("\n=== Database Statistics ===")
    stats = get_database_stats()
    for key, value in stats.items():
        print("{}: {}".format(key, value))
else:
    init_database()