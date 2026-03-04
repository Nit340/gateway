# -*- coding: utf-8 -*-
# database.py - Database initialization and operations
import sqlite3
import json
from datetime import datetime

import os

# Database stored at /mnt/data/ so it survives across working-directory changes
# and is kept outside the application source tree.
_DB_DIR  = '/mnt/data'
DB_FILE  = os.path.join(_DB_DIR, 'gateway_config.db')

# Create the directory if it does not exist (runs once at import time)
os.makedirs(_DB_DIR, exist_ok=True)

def get_db_connection():
    """Get a database connection with proper timeout and WAL mode for concurrency"""
    conn = sqlite3.connect(DB_FILE, timeout=10.0)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_database():
    """Initialize SQLite database with new schema"""
    conn = get_db_connection()
    cursor = conn.cursor()

    create_tables(cursor)
    insert_default_data(cursor)
    _migrate_general_config_columns(cursor)   # safe additive migration for existing DBs

    conn.commit()
    conn.close()
    print("Database initialized with new schema")
    print("[OK] General configuration table")
    print("[OK] Services table (modbus, loadcell)")
    print("[OK] Modbus_device table (tcp/rtu with connection details)")
    print("[OK] Loadcell_device table (with calibration)")
    print("[OK] Modbus_datapoints table")
    print("[OK] Loadcell_datapoints table")
    print("[OK] Device groups table")
    print("[OK] Cloud Integration tables")


def _migrate_general_config_columns(cursor):
    """Add any new columns to general_configuration on an existing live DB.
    Uses ALTER TABLE ADD COLUMN which is safe and additive — never drops data."""
    cursor.execute("PRAGMA table_info(general_configuration)")
    existing = {row[1] for row in cursor.fetchall()}
    new_cols = [
        ("network_mode",      "TEXT    DEFAULT 'wifi'"),
        ("wifi_ssid",         "TEXT    DEFAULT ''"),
        ("wifi_password",     "TEXT    DEFAULT ''"),
        ("eth_ip_assignment", "TEXT    DEFAULT 'dhcp'"),
        ("eth_static_ip",     "TEXT    DEFAULT ''"),
        ("eth_subnet_mask",   "TEXT    DEFAULT ''"),
        ("eth_gateway",       "TEXT    DEFAULT ''"),
        ("eth_dns1",          "TEXT    DEFAULT ''"),
        ("eth_dns2",          "TEXT    DEFAULT ''"),
        ("cell_apn",          "TEXT    DEFAULT 'internet'"),
        ("cell_username",     "TEXT    DEFAULT ''"),
        ("cell_password",     "TEXT    DEFAULT ''"),
    ]
    for col, defn in new_cols:
        if col not in existing:
            cursor.execute(
                "ALTER TABLE general_configuration ADD COLUMN {} {}".format(col, defn))
            print("[DB] Migration: added general_configuration.{}".format(col))

def create_tables(cursor):
    """Create all tables with proper schema"""
    
    # General configuration table — single-row store (id always = 1)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS general_configuration (
            id INTEGER PRIMARY KEY,

            -- Gateway Identity
            gateway_name        TEXT    DEFAULT 'Univa-GW-01',
            serial_number       TEXT    DEFAULT 'GW2025-1190021',
            deployment_site     TEXT    DEFAULT 'Chennai Port - Zone A',
            location_mode       TEXT    DEFAULT 'manual',
            latitude            REAL    DEFAULT 12.99123,
            longitude           REAL    DEFAULT 80.12312,
            asset_id            TEXT    DEFAULT 'CRN-CT-12',
            mac_address         TEXT    DEFAULT '00:1A:2B:3C:4D:5E',

            -- Date & Time
            timezone            TEXT    DEFAULT 'Asia/Kolkata',
            ntp_server          TEXT    DEFAULT 'pool.ntp.org',
            date_format         TEXT    DEFAULT 'DD/MM/YYYY',
            time_format         TEXT    DEFAULT '24-hour',
            language            TEXT    DEFAULT 'en',

            -- Heartbeat
            heartbeat_interval  INTEGER DEFAULT 30,
            offline_threshold   INTEGER DEFAULT 120,

            -- Network: active mode selector
            network_mode        TEXT    DEFAULT 'wifi',

            -- WiFi (network_mode = 'wifi')
            wifi_ssid           TEXT    DEFAULT '',
            wifi_password       TEXT    DEFAULT '',

            -- Ethernet (network_mode = 'ethernet')
            eth_ip_assignment   TEXT    DEFAULT 'dhcp',
            eth_static_ip       TEXT    DEFAULT '',
            eth_subnet_mask     TEXT    DEFAULT '',
            eth_gateway         TEXT    DEFAULT '',
            eth_dns1            TEXT    DEFAULT '',
            eth_dns2            TEXT    DEFAULT '',

            -- Cellular / LTE (network_mode = 'lte')
            cell_apn            TEXT    DEFAULT 'internet',
            cell_username       TEXT    DEFAULT '',
            cell_password       TEXT    DEFAULT '',

            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Services table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Device groups table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT DEFAULT 'blue',
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Modbus device table - MATCHING YOUR SPECIFIED FORMAT
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS modbus_device (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            device_type TEXT NOT NULL CHECK(device_type IN ('tcp', 'rtu')),
            group_id INTEGER,
            service_id INTEGER,
            
            -- Common parameters matching your format
            response_timeout_ms INTEGER DEFAULT 100,
            byte_timeout_ms INTEGER DEFAULT 100,
            max_retries INTEGER DEFAULT 2,
            polling_interval_ms INTEGER DEFAULT 300,
            
            -- TCP specific
            ip_address TEXT,
            port INTEGER DEFAULT 502,
            
            -- RTU specific
            serial_port TEXT DEFAULT '/dev/ttymxc5',
            baud_rate INTEGER DEFAULT 9600,
            parity TEXT DEFAULT 'N',
            data_bits INTEGER DEFAULT 8,
            stop_bits INTEGER DEFAULT 1,
            
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    ''')
    
    # Loadcell device table -- sysfs_hx711 hardware-aligned schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS loadcell_device (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            service_id INTEGER,

            -- SysFS / IIO device path  (sysfs_hx711 driver)
            device_path TEXT NOT NULL DEFAULT '/sys/bus/iio/devices/iio:device0/in_voltage0_raw',

            -- Auto-generated names (not entered by user)
            load_name TEXT DEFAULT 'load',
            capacity_name TEXT DEFAULT 'capacity',

            -- Pipeline connection
            pipeline_server TEXT DEFAULT '127.0.0.1',
            pipeline_port INTEGER DEFAULT 7000,
            log_level TEXT DEFAULT 'info',

            -- ADC hardware parameters (sysfs_hx711 device block)
            poll_ms INTEGER DEFAULT 10,
            resolution_bits INTEGER DEFAULT 24,
            effective_bits INTEGER DEFAULT 14,
            signed BOOLEAN DEFAULT 0,
            gain REAL DEFAULT 1,
            vref REAL DEFAULT 5,
            raw_min REAL DEFAULT 0,
            raw_max REAL DEFAULT 16383,

            -- Capacity specification
            capacity_min REAL DEFAULT 0,
            capacity_max REAL DEFAULT 1000,
            unit TEXT DEFAULT 'kg',

            -- Calibration (single_point method)
            tare_offset REAL DEFAULT 0.0,
            known_weight REAL DEFAULT 0.0,
            known_weight_raw REAL DEFAULT 0.0,

            -- Filter and level arrays stored as JSON strings
            -- raw_filters:    [{type, parameters, enabled}, ...]
            -- weight_filters: [{type, parameters, enabled}, ...]
            -- levels:         [{name, ratio, enabled}, ...]
            raw_filters TEXT DEFAULT '[]',
            weight_filters TEXT DEFAULT '[]',
            levels TEXT DEFAULT '[]',

            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    ''')
    
    # Modbus datapoints table - UPDATED with group field (quoted) and writable flag
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS modbus_datapoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            name TEXT NOT NULL,
            slave_id INTEGER DEFAULT 1,
            group_id INTEGER,
            "group" TEXT,
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
            writable BOOLEAN DEFAULT 0,
            retry_count INTEGER DEFAULT 1,
            timeout_ms INTEGER DEFAULT 100,
            register_count INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(device_id, slave_id, name),
            FOREIGN KEY (device_id) REFERENCES modbus_device(id) ON DELETE CASCADE,
            FOREIGN KEY (group_id) REFERENCES device_groups(id) ON DELETE SET NULL
        )
    ''')
    
    # Loadcell datapoints table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS loadcell_datapoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            name TEXT NOT NULL,
            unit TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(device_id, name),
            FOREIGN KEY (device_id) REFERENCES loadcell_device(id) ON DELETE CASCADE
        )
    ''')

    # Cloud Integration tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cloud_connections (
            id         TEXT PRIMARY KEY,
            type       TEXT NOT NULL CHECK(type IN ('mqtt','ftp')),
            name       TEXT NOT NULL,
            enabled    INTEGER DEFAULT 1,
            config     TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

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
    
    # Migration for new columns (with proper quoting)
    try:
        cursor.execute('ALTER TABLE modbus_datapoints ADD COLUMN "group" TEXT')
    except Exception:
        pass
    try:
        cursor.execute('ALTER TABLE modbus_datapoints ADD COLUMN writable BOOLEAN DEFAULT 0')
    except Exception:
        pass
    try:
        cursor.execute('ALTER TABLE modbus_datapoints ADD COLUMN retry_count INTEGER DEFAULT 1')
    except Exception:
        pass
    try:
        cursor.execute('ALTER TABLE modbus_datapoints ADD COLUMN timeout_ms INTEGER DEFAULT 100')
    except Exception:
        pass
    try:
        cursor.execute('ALTER TABLE modbus_datapoints ADD COLUMN register_count INTEGER DEFAULT 1')
    except Exception:
        pass

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

def get_general_configuration():
    """Get general configuration.

    The returned dict shape matches exactly what both the JS (populateFormWithConfig)
    and build_iot_gateway_config expect:

        network.mode
        network.wifi     = { ssid, password }
        network.ethernet = { ip_assignment, static_ip, subnet_mask, gateway, dns1, dns2 }
        network.cellular = { apn, username, password }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                gateway_name, serial_number, deployment_site, location_mode,
                latitude, longitude, asset_id, mac_address,
                timezone, ntp_server, date_format, time_format, language,
                heartbeat_interval, offline_threshold,
                COALESCE(network_mode,      'wifi')     AS network_mode,
                COALESCE(wifi_ssid,         '')         AS wifi_ssid,
                COALESCE(wifi_password,     '')         AS wifi_password,
                COALESCE(eth_ip_assignment, 'dhcp')     AS eth_ip_assignment,
                COALESCE(eth_static_ip,     '')         AS eth_static_ip,
                COALESCE(eth_subnet_mask,   '')         AS eth_subnet_mask,
                COALESCE(eth_gateway,       '')         AS eth_gateway,
                COALESCE(eth_dns1,          '')         AS eth_dns1,
                COALESCE(eth_dns2,          '')         AS eth_dns2,
                COALESCE(cell_apn,          'internet') AS cell_apn,
                COALESCE(cell_username,     '')         AS cell_username,
                COALESCE(cell_password,     '')         AS cell_password
            FROM general_configuration WHERE id = 1
        ''')

        row = cursor.fetchone()
        conn.close()

        if not row:
            return {}

        return {
            'gateway_identity': {
                'name':            row[0],
                'serial_number':   row[1],
                'deployment_site': row[2],
                'location_mode':   row[3],
                'latitude':        row[4],
                'longitude':       row[5],
                'asset_id':        row[6],
            },
            'date_time': {
                'timezone':    row[8],
                'ntp_server':  row[9],
                'date_format': row[10],
                'time_format': row[11],
                'language':    row[12],
            },
            'heartbeat': {
                'interval':          row[13],
                'offline_threshold': row[14],
            },
            'mac_address': row[7],
            # network shape matches JS populateFormWithConfig exactly
            'network': {
                'mode': row[15],
                'wifi': {
                    'ssid':     row[16],
                    'password': row[17],
                },
                'ethernet': {
                    'ip_assignment': row[18],
                    'static_ip':     row[19],
                    'subnet_mask':   row[20],
                    'gateway':       row[21],
                    'dns1':          row[22],
                    'dns2':          row[23],
                },
                'cellular': {
                    'apn':      row[24],
                    'username': row[25],
                    'password': row[26],
                },
            },
        }
    except Exception as e:
        print("Error getting general config: {}".format(e))
        return {}

def update_general_configuration(config_data):
    """Update general configuration.

    Accepts the nested shape the JS sends:
        gateway_identity, date_time, heartbeat, mac_address
        network.mode
        network.wifi.ssid / .password
        network.ethernet.ip_assignment / .static_ip / .subnet_mask / .gateway / .dns1 / .dns2
        network.cellular.apn / .username / .password
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        sets   = []
        values = []

        def _add(col, val):
            sets.append('{} = ?'.format(col))
            values.append(val)

        # Gateway Identity
        gi = config_data.get('gateway_identity', {})
        if 'name'            in gi: _add('gateway_name',    gi['name'])
        if 'serial_number'   in gi: _add('serial_number',   gi['serial_number'])
        if 'deployment_site' in gi: _add('deployment_site', gi['deployment_site'])
        if 'location_mode'   in gi: _add('location_mode',   gi['location_mode'])
        if 'latitude'        in gi: _add('latitude',        gi['latitude'])
        if 'longitude'       in gi: _add('longitude',       gi['longitude'])
        if 'asset_id'        in gi: _add('asset_id',        gi['asset_id'])

        # Date & Time
        dt = config_data.get('date_time', {})
        if 'timezone'    in dt: _add('timezone',    dt['timezone'])
        if 'ntp_server'  in dt: _add('ntp_server',  dt['ntp_server'])
        if 'date_format' in dt: _add('date_format', dt['date_format'])
        if 'time_format' in dt: _add('time_format', dt['time_format'])
        if 'language'    in dt: _add('language',    dt['language'])

        # Heartbeat
        hb = config_data.get('heartbeat', {})
        if 'interval'          in hb: _add('heartbeat_interval', hb['interval'])
        if 'offline_threshold' in hb: _add('offline_threshold',  hb['offline_threshold'])

        # MAC Address
        if 'mac_address' in config_data:
            _add('mac_address', config_data['mac_address'])

        # Network
        net = config_data.get('network', {})
        if 'mode' in net: _add('network_mode', net['mode'])

        # WiFi — JS sends network.wifi.ssid / .password
        wifi = net.get('wifi', {})
        if 'ssid'     in wifi: _add('wifi_ssid',      wifi['ssid'])
        if 'password' in wifi: _add('wifi_password',  wifi['password'])

        # Ethernet — JS sends network.ethernet.*
        eth = net.get('ethernet', {})
        if 'ip_assignment' in eth: _add('eth_ip_assignment', eth['ip_assignment'])
        if 'static_ip'     in eth: _add('eth_static_ip',     eth['static_ip'])
        if 'subnet_mask'   in eth: _add('eth_subnet_mask',   eth['subnet_mask'])
        if 'gateway'       in eth: _add('eth_gateway',       eth['gateway'])
        if 'dns1'          in eth: _add('eth_dns1',          eth['dns1'])
        if 'dns2'          in eth: _add('eth_dns2',          eth['dns2'])

        # Cellular — JS sends network.cellular.*
        cell = net.get('cellular', {})
        if 'apn'      in cell: _add('cell_apn',      cell['apn'])
        if 'username' in cell: _add('cell_username',  cell['username'])
        if 'password' in cell: _add('cell_password',  cell['password'])

        if sets:
            cursor.execute(
                'UPDATE general_configuration SET {}, updated_at = CURRENT_TIMESTAMP WHERE id = 1'
                .format(', '.join(sets)),
                values)
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
        
        cursor.execute('UPDATE modbus_datapoints SET group_id = NULL WHERE group_id = ?', (group_id,))
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