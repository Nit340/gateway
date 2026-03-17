# -*- coding: utf-8 -*-
# database.py - Database initialization and operations
import sqlite3
import json
import hashlib
import os
from datetime import datetime

# Database path - configurable via environment variable
_DB_DIR = os.environ.get('GATEWAY_DB_DIR', '/mnt/data')
DB_FILE = os.environ.get('GATEWAY_DB_FILE', os.path.join(_DB_DIR, 'gateway_config.db'))

# Create the directory if it does not exist
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)


def get_db_connection():
    """Get a database connection with WAL mode for concurrency"""
    conn = sqlite3.connect(DB_FILE, timeout=10.0)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_database():
    """Initialize SQLite database with full schema"""
    conn = get_db_connection()
    cursor = conn.cursor()
    create_tables(cursor)
    insert_default_data(cursor)
    _migrate_existing_db(cursor)
    conn.commit()
    conn.close()
    print("[DB] Database initialized: {}".format(DB_FILE))
    print("[DB] All tables created/verified OK")


def create_tables(cursor):
    """Create all tables -- schema is complete at creation, no ALTER TABLE migrations needed"""

    # -----------------------------------------------------------------------
    # General configuration (single-row store, id always = 1)
    # -----------------------------------------------------------------------
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

            -- WiFi
            wifi_ssid           TEXT    DEFAULT '',
            wifi_password       TEXT    DEFAULT '',

            -- Ethernet
            eth_ip_assignment   TEXT    DEFAULT 'dhcp',
            eth_static_ip       TEXT    DEFAULT '',
            eth_subnet_mask     TEXT    DEFAULT '',
            eth_gateway         TEXT    DEFAULT '',
            eth_dns1            TEXT    DEFAULT '',
            eth_dns2            TEXT    DEFAULT '',

            -- Cellular / LTE
            cell_apn            TEXT    DEFAULT 'internet',
            cell_username       TEXT    DEFAULT '',
            cell_password       TEXT    DEFAULT '',

            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # -----------------------------------------------------------------------
    # Services
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            description TEXT,
            enabled     BOOLEAN DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # -----------------------------------------------------------------------
    # Device groups
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tag_groups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            color       TEXT    DEFAULT 'blue',
            description TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # -----------------------------------------------------------------------
    # Modbus device
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vfd_device (
            id                  TEXT    PRIMARY KEY,
            name                TEXT    NOT NULL,
            protocol_type       TEXT    NOT NULL DEFAULT 'rtu' CHECK(protocol_type IN ('tcp', 'rtu')),
            device_type         TEXT    NOT NULL DEFAULT 'vfd' CHECK(device_type IN ('vfd')),
            group_id            INTEGER,
            service_id          INTEGER,

            response_timeout_ms INTEGER DEFAULT 100,
            byte_timeout_ms     INTEGER DEFAULT 100,
            max_retries         INTEGER DEFAULT 2,
            polling_interval_ms INTEGER DEFAULT 300,

            -- TCP
            ip_address          TEXT,
            port                INTEGER DEFAULT 502,

            -- RTU
            serial_port         TEXT    DEFAULT '/dev/ttymxc5',
            baud_rate           INTEGER DEFAULT 9600,
            parity              TEXT    DEFAULT 'N',
            data_bits           INTEGER DEFAULT 8,
            stop_bits           INTEGER DEFAULT 1,

            -- Modbus Slave ID (applies to both RTU and TCP)
            slave_id            INTEGER DEFAULT 1,

            enabled             BOOLEAN DEFAULT 1,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    ''')

    # -----------------------------------------------------------------------
    # Loadcell device
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS loadcell_device (
            id               TEXT    PRIMARY KEY,
            name             TEXT    NOT NULL,
            service_id       INTEGER,

            device_path      TEXT    NOT NULL DEFAULT '/sys/bus/iio/devices/iio:device0/in_voltage0_raw',
            device_path_ch2  TEXT    DEFAULT NULL,
            lc_mode          TEXT    DEFAULT 'init' CHECK(lc_mode IN ('init', 'single_ended', 'differential')),

            load_name        TEXT    DEFAULT 'load',
            capacity_name    TEXT    DEFAULT 'capacity',

            pipeline_server  TEXT    DEFAULT '127.0.0.1',
            pipeline_port    INTEGER DEFAULT 7000,
            log_level        TEXT    DEFAULT 'info',

            poll_ms          INTEGER DEFAULT 10,
            resolution_bits  INTEGER DEFAULT 24,
            effective_bits   INTEGER DEFAULT 14,
            signed           BOOLEAN DEFAULT 0,
            gain             REAL    DEFAULT 1,
            vref             REAL    DEFAULT 5,
            raw_min          REAL    DEFAULT 0,
            raw_max          REAL    DEFAULT 16383,

            capacity_min     REAL    DEFAULT 0,
            capacity_max     REAL    DEFAULT 1000,
            unit             TEXT    DEFAULT 'kg',

            tare_offset      REAL    DEFAULT 0.0,
            known_weight     REAL    DEFAULT 0.0,
            known_weight_raw REAL    DEFAULT 0.0,

            raw_filters      TEXT    DEFAULT '[]',
            weight_filters   TEXT    DEFAULT '[]',
            levels           TEXT    DEFAULT '[]',

            enabled          BOOLEAN DEFAULT 1,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    ''')

    # -----------------------------------------------------------------------
    # Modbus datapoints
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vfd_datapoints (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id        TEXT    NOT NULL,
            name             TEXT    NOT NULL,
            slave_id         INTEGER DEFAULT 1,
            group_id         INTEGER,
            "group"          TEXT,
            register_address INTEGER NOT NULL,
            register_type    TEXT    NOT NULL CHECK(register_type IN ('holding', 'input', 'coil', 'discrete')),
            data_type        TEXT    NOT NULL CHECK(data_type IN ('int16', 'uint16', 'int32', 'uint32', 'float32', 'bool')),
            byte_order       TEXT    DEFAULT 'big',
            word_order       TEXT    DEFAULT 'big',
            scale_factor     REAL    DEFAULT 1.0,
            offset           REAL    DEFAULT 0.0,
            unit             TEXT,
            description      TEXT,
            enabled          BOOLEAN DEFAULT 1,
            writable         BOOLEAN DEFAULT 0,
            retry_count      INTEGER DEFAULT 1,
            timeout_ms       INTEGER DEFAULT 100,
            register_count   INTEGER DEFAULT 1,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(device_id, slave_id, name),
            FOREIGN KEY (device_id) REFERENCES vfd_device(id) ON DELETE CASCADE,
            FOREIGN KEY (group_id) REFERENCES tag_groups(id) ON DELETE SET NULL
        )
    ''')

    # -----------------------------------------------------------------------
    # Loadcell datapoints
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS loadcell_datapoints (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id  TEXT    NOT NULL,
            name       TEXT    NOT NULL,
            unit       TEXT    DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(device_id, name),
            FOREIGN KEY (device_id) REFERENCES loadcell_device(id) ON DELETE CASCADE
        )
    ''')

    # -----------------------------------------------------------------------
    # loadcell_device schema migrations (v2 additions)
    #   publish_step_grams  -- min weight change before publishing (grams)
    #   action_tare         -- override pipeline action name for tare
    #   action_calibrate    -- override pipeline action name for calibrate
    # -----------------------------------------------------------------------
    for _col, _defn in [
        ('publish_step_grams', 'REAL    DEFAULT 1.0'),
        ('action_tare',        'TEXT    DEFAULT NULL'),
        ('action_calibrate',   'TEXT    DEFAULT NULL'),
    ]:
        try:
            cursor.execute('ALTER TABLE loadcell_device ADD COLUMN {} {}'.format(_col, _defn))
        except Exception:
            pass  # column already exists   safe to ignore

    # -----------------------------------------------------------------------
    # Cloud integration
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cloud_connections (
            id         TEXT    PRIMARY KEY,
            type       TEXT    NOT NULL CHECK(type IN ('mqtt','ftp')),
            name       TEXT    NOT NULL,
            enabled    INTEGER DEFAULT 1,
            config     TEXT    NOT NULL DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')



    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cloud_connection_stats (
            connection_id   TEXT    PRIMARY KEY,
            messages_total  INTEGER DEFAULT 0,
            messages_ok     INTEGER DEFAULT 0,
            messages_failed INTEGER DEFAULT 0,
            latency_avg_ms  REAL    DEFAULT 0.0,
            last_active     TEXT    DEFAULT NULL,
            FOREIGN KEY (connection_id) REFERENCES cloud_connections(id) ON DELETE CASCADE
        )
    ''')

    # MQTT tag datapoints mapping per connection
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mqtt_datapoints (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_id   TEXT    NOT NULL,
            tag_name        TEXT    NOT NULL,
            topic           TEXT    NOT NULL,
            publish_mode    TEXT    DEFAULT 'on_change',
            change_threshold REAL   DEFAULT 0.0,
            enabled         INTEGER DEFAULT 1,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (connection_id) REFERENCES cloud_connections(id) ON DELETE CASCADE,
            UNIQUE(connection_id, tag_name)
        )
    ''')

    # -----------------------------------------------------------------------
    # Admin users  (for the /admin panel)
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT    NOT NULL UNIQUE,
            password   TEXT    NOT NULL,          -- SHA-256 hex digest
            role       TEXT    NOT NULL DEFAULT 'admin' CHECK(role IN ('admin', 'operator')),
            enabled    BOOLEAN DEFAULT 1,
            last_login TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # -----------------------------------------------------------------------
    # WebUI users  (for the operator-facing Web UI login)
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS webui_users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT    NOT NULL UNIQUE,
            password   TEXT    NOT NULL,          -- SHA-256 hex digest
            display_name TEXT  DEFAULT '',
            enabled    BOOLEAN DEFAULT 1,
            max_sessions INTEGER DEFAULT 1,
            last_login TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # -----------------------------------------------------------------------
    # Pipeline service targets (replaces hard-coded service names)
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pipeline_service_targets (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            config_type  TEXT    NOT NULL UNIQUE
                             CHECK(config_type IN ('modbus', 'loadcell', 'iot_gateway', 'core')),
            service_name TEXT    NOT NULL DEFAULT '',
            config_name  TEXT    NOT NULL DEFAULT '',
            enabled      BOOLEAN DEFAULT 1,
            description  TEXT    DEFAULT '',
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # -----------------------------------------------------------------------
    # Pipeline send log -- one row per config_type, tracks last sent version
    # Version is read from here, incremented, written back ONLY on success
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pipeline_send_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            config_type     TEXT    NOT NULL UNIQUE
                                CHECK(config_type IN ('modbus', 'loadcell', 'iot_gateway', 'core')),
            last_version    INTEGER NOT NULL DEFAULT 0,
            last_sent_at    TIMESTAMP,
            last_service    TEXT    DEFAULT '',
            last_status     TEXT    DEFAULT 'never',
            last_message    TEXT    DEFAULT ''
        )
    ''')

    # -----------------------------------------------------------------------
    # External Devices
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS external_device (
            id         TEXT    PRIMARY KEY,
            name       TEXT    NOT NULL,
            protocol   TEXT    DEFAULT 'external',
            config     TEXT    DEFAULT '{}',
            enabled    BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS external_datapoints (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id        TEXT    NOT NULL,
            name             TEXT    NOT NULL,
            slave_id         INTEGER DEFAULT 1,
            register_address INTEGER NOT NULL DEFAULT 0,
            register_type    TEXT    NOT NULL DEFAULT 'holding'
                                 CHECK(register_type IN ('holding', 'input', 'coil', 'discrete')),
            data_type        TEXT    NOT NULL DEFAULT 'uint16'
                                 CHECK(data_type IN ('int16', 'uint16', 'int32', 'uint32', 'float32', 'bool')),
            byte_order       TEXT    DEFAULT 'big',
            word_order       TEXT    DEFAULT 'big',
            scale_factor     REAL    DEFAULT 1.0,
            offset           REAL    DEFAULT 0.0,
            unit             TEXT    DEFAULT '',
            description      TEXT    DEFAULT '',
            enabled          BOOLEAN DEFAULT 1,
            writable         BOOLEAN DEFAULT 0,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(device_id, name),
            FOREIGN KEY (device_id) REFERENCES external_device(id) ON DELETE CASCADE
        )
    ''')



    # -----------------------------------------------------------------------
    # WebUI Page Restrictions (per-user access control)
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS webui_user_page_restrictions (
            user_id    INTEGER NOT NULL REFERENCES webui_users(id) ON DELETE CASCADE,
            page_key   TEXT    NOT NULL,
            PRIMARY KEY (user_id, page_key)
        )
    ''')

    # -----------------------------------------------------------------------
    # Port / Path configuration
    #   device_type : 'modbus' | 'loadcell'
    #   port_number : 1-based index shown in the UI (Port 1, Port 2, �)
    #   port_value  : actual system path stored in vfd_device.serial_port
    #                 or loadcell_device.device_path
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS port_config (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            device_type TEXT    NOT NULL CHECK(device_type IN ('modbus', 'loadcell')),
            port_number INTEGER NOT NULL,
            label       TEXT    NOT NULL,
            port_value  TEXT    NOT NULL,
            UNIQUE(device_type, port_number)
        )
    ''')


def _migrate_existing_db(cursor):
    """Safe additive migrations for DBs created before schema updates.
    Only adds missing columns -- never drops or modifies existing data.
    """
    # pipeline_service_targets: add enabled column if missing
    cursor.execute("PRAGMA table_info(pipeline_service_targets)")
    cols = {r[1] for r in cursor.fetchall()}
    if 'enabled' not in cols:
        cursor.execute("ALTER TABLE pipeline_service_targets ADD COLUMN enabled BOOLEAN DEFAULT 1")
        print("[DB] Migration: added pipeline_service_targets.enabled")
    if 'config_name' not in cols:
        cursor.execute("ALTER TABLE pipeline_service_targets ADD COLUMN config_name TEXT NOT NULL DEFAULT ''")
        # Seed default config names for existing rows
        defaults = {
            'modbus':      'modbus_config',
            'loadcell':    'loadcell_config',
            'iot_gateway': 'gateway_config',
            'core':        'iq_core',
        }
        for cfg_type, cfg_name in defaults.items():
            cursor.execute(
                "UPDATE pipeline_service_targets SET config_name=? WHERE config_type=? AND (config_name IS NULL OR config_name='')",
                (cfg_name, cfg_type)
            )
        print("[DB] Migration: added pipeline_service_targets.config_name")

    # pipeline_send_log: ensure table exists (added in later version)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_send_log'")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE pipeline_send_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                config_type     TEXT    NOT NULL UNIQUE
                                    CHECK(config_type IN ('modbus', 'loadcell', 'iot_gateway', 'core')),
                last_version    INTEGER NOT NULL DEFAULT 0,
                last_sent_at    TIMESTAMP,
                last_service    TEXT    DEFAULT '',
                last_status     TEXT    DEFAULT 'never',
                last_message    TEXT    DEFAULT ''
            )
        ''')
        for cfg_type in ('modbus', 'loadcell', 'iot_gateway', 'core'):
            cursor.execute(
                'INSERT OR IGNORE INTO pipeline_send_log (config_type) VALUES (?)', (cfg_type,)
            )
        print("[DB] Migration: created pipeline_send_log table")

    # webui_users: add max_sessions column if missing (migration for existing DBs)
    cursor.execute("PRAGMA table_info(webui_users)")
    _webui_cols = [r[1] for r in cursor.fetchall()]
    if 'max_sessions' not in _webui_cols:
        cursor.execute('ALTER TABLE webui_users ADD COLUMN max_sessions INTEGER DEFAULT 1')
        print('[DB] Migration: added max_sessions to webui_users')

    # webui_users: ensure table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='webui_users'")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE webui_users (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                username     TEXT    NOT NULL UNIQUE,
                password     TEXT    NOT NULL,
                display_name TEXT    DEFAULT '',
                enabled      BOOLEAN DEFAULT 1,
                last_login   TIMESTAMP,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("[DB] Migration: created webui_users table")

    # admin_users: ensure table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_users'")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE admin_users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    NOT NULL UNIQUE,
                password   TEXT    NOT NULL,
                role       TEXT    NOT NULL DEFAULT 'admin' CHECK(role IN ('admin', 'operator')),
                enabled    BOOLEAN DEFAULT 1,
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("[DB] Migration: created admin_users table")

    # rules table -- stores each rule as a flat row with groups/datapoints as JSON
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rules'")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE rules (
                id              TEXT    PRIMARY KEY,
                name            TEXT    NOT NULL DEFAULT '',
                rule_type       TEXT    NOT NULL DEFAULT 'group',
                priority        TEXT    NOT NULL DEFAULT 'medium',
                description     TEXT    DEFAULT '',
                enabled         INTEGER DEFAULT 1,
                groups_json     TEXT    DEFAULT '{}',
                relay_datapoint TEXT    DEFAULT '',
                trigger_count   INTEGER DEFAULT 0,
                last_triggered  TIMESTAMP,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("[DB] Migration: created rules table")


    # vfd_device: add protocol_type, device_type, slave_id columns if missing
    cursor.execute("PRAGMA table_info(vfd_device)")
    vfd_cols = {r[1] for r in cursor.fetchall()}
    if 'protocol_type' not in vfd_cols:
        cursor.execute("ALTER TABLE vfd_device ADD COLUMN protocol_type TEXT NOT NULL DEFAULT 'rtu'")
        print("[DB] Migration: added vfd_device.protocol_type")
    if 'device_type' not in vfd_cols:
        cursor.execute("ALTER TABLE vfd_device ADD COLUMN device_type TEXT NOT NULL DEFAULT 'vfd'")
        print("[DB] Migration: added vfd_device.device_type")
    if 'slave_id' not in vfd_cols:
        cursor.execute("ALTER TABLE vfd_device ADD COLUMN slave_id INTEGER DEFAULT 1")
        print("[DB] Migration: added vfd_device.slave_id")

    # loadcell_device: add lc_mode and device_path_ch2 if missing
    cursor.execute("PRAGMA table_info(loadcell_device)")
    lc_cols = {r[1] for r in cursor.fetchall()}
    if 'lc_mode' not in lc_cols:
        cursor.execute("ALTER TABLE loadcell_device ADD COLUMN lc_mode TEXT DEFAULT 'init'")
        print("[DB] Migration: added loadcell_device.lc_mode")
    if 'device_path_ch2' not in lc_cols:
        cursor.execute("ALTER TABLE loadcell_device ADD COLUMN device_path_ch2 TEXT DEFAULT NULL")
        print("[DB] Migration: added loadcell_device.device_path_ch2")

    # external_datapoints: ensure table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='external_datapoints'")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS external_datapoints (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id        TEXT    NOT NULL,
                name             TEXT    NOT NULL,
                slave_id         INTEGER DEFAULT 1,
                register_address INTEGER NOT NULL DEFAULT 0,
                register_type    TEXT    NOT NULL DEFAULT 'holding'
                                     CHECK(register_type IN ('holding', 'input', 'coil', 'discrete')),
                data_type        TEXT    NOT NULL DEFAULT 'uint16'
                                     CHECK(data_type IN ('int16', 'uint16', 'int32', 'uint32', 'float32', 'bool')),
                byte_order       TEXT    DEFAULT 'big',
                word_order       TEXT    DEFAULT 'big',
                scale_factor     REAL    DEFAULT 1.0,
                offset           REAL    DEFAULT 0.0,
                unit             TEXT    DEFAULT '',
                description      TEXT    DEFAULT '',
                enabled          BOOLEAN DEFAULT 1,
                writable         BOOLEAN DEFAULT 0,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(device_id, name),
                FOREIGN KEY (device_id) REFERENCES external_device(id) ON DELETE CASCADE
            )
        ''')
        print("[DB] Migration: created external_datapoints table")

    # external_device: ensure table exists + migrate columns
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='external_device'")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS external_device (
                id         TEXT    PRIMARY KEY,
                name       TEXT    NOT NULL,
                protocol   TEXT    DEFAULT 'external',
                config     TEXT    DEFAULT '{}',
                enabled    BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("[DB] Migration: created external_device table")
    else:
        cursor.execute("PRAGMA table_info(external_device)")
        ext_cols = {r[1] for r in cursor.fetchall()}
        if 'protocol' not in ext_cols:
            cursor.execute("ALTER TABLE external_device ADD COLUMN protocol TEXT DEFAULT 'external'")
            print("[DB] Migration: added external_device.protocol")
        if 'config' not in ext_cols:
            cursor.execute("ALTER TABLE external_device ADD COLUMN config TEXT DEFAULT '{}'")
            print("[DB] Migration: added external_device.config")

    # Update port_config: rename Path 1/2 to Channel 1/2 for loadcell
    cursor.execute("UPDATE port_config SET label='Channel 1' WHERE device_type='loadcell' AND label='Path 1'")
    cursor.execute("UPDATE port_config SET label='Channel 2' WHERE device_type='loadcell' AND label='Path 2'")


    # webui_user_page_restrictions: ensure table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='webui_user_page_restrictions'")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE webui_user_page_restrictions (
                user_id  INTEGER NOT NULL,
                page_key TEXT    NOT NULL,
                PRIMARY KEY (user_id, page_key)
            )
        """)
        print("[DB] Migration: created webui_user_page_restrictions table")

    # port_config: ensure table exists on older DBs
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='port_config'")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE port_config (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                device_type TEXT    NOT NULL CHECK(device_type IN ('modbus', 'loadcell')),
                port_number INTEGER NOT NULL,
                label       TEXT    NOT NULL,
                port_value  TEXT    NOT NULL,
                UNIQUE(device_type, port_number)
            )
        ''')
        for device_type, port_number, label, port_value in [
            ('modbus',   1, 'Port 1', '/dev/ttymxc5'),
            ('modbus',   2, 'Port 2', '/dev/ttymxc2'),
            ('loadcell', 1, 'Channel 1', '/sys/bus/iio/devices/iio:device0/in_voltage0_raw'),
            ('loadcell', 2, 'Channel 2', '/sys/bus/iio/devices/iio:device1/in_voltage0_raw'),
        ]:
            cursor.execute(
                'INSERT OR IGNORE INTO port_config (device_type, port_number, label, port_value) VALUES (?, ?, ?, ?)',
                (device_type, port_number, label, port_value)
            )
        print("[DB] Migration: created port_config table with default entries")


def _hash_password(plain):
    return hashlib.sha256(plain.encode()).hexdigest()


def insert_default_data(cursor):
    """Insert default seed data (idempotent -- uses INSERT OR IGNORE)"""

    # General configuration row
    cursor.execute('SELECT COUNT(*) FROM general_configuration')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO general_configuration (id) VALUES (1)')

    # Default services
    for name, desc in [('modbus', 'Modbus Protocol Service'),
                        ('loadcell', 'Loadcell Service')]:
        cursor.execute('INSERT OR IGNORE INTO services (name, description) VALUES (?, ?)', (name, desc))

    # Default admin user  (admin / admin123)
    cursor.execute(
        'INSERT OR IGNORE INTO admin_users (username, password, role) VALUES (?, ?, ?)',
        ('admin', _hash_password('admin123'), 'admin')
    )

    # Default WebUI user
    cursor.execute(
        'INSERT OR IGNORE INTO webui_users (username, password, display_name) VALUES (?, ?, ?)',
        ('admin', _hash_password('admin'), 'Crane Operator')
    )

    # Default pipeline service targets
    for cfg_type, svc_name, cfg_name, desc in [
        ('modbus',      'modbus_service',   'modbus_config',    'Modbus pipeline service name'),
        ('loadcell',    'load_cell_service','loadcell_config',  'Load-cell pipeline service name'),
        ('iot_gateway', 'iot-gateway',      'gateway_config',   'IoT gateway pipeline service name'),
        ('core',        'ilx_craneiq_core',  'core_config',          'Core config pipeline service name'),
    ]:
        cursor.execute(
            'INSERT OR IGNORE INTO pipeline_service_targets (config_type, service_name, config_name, description, enabled) VALUES (?, ?, ?, ?, 1)',
            (cfg_type, svc_name, cfg_name, desc)
        )

    # Default pipeline send log rows
    for cfg_type in ('modbus', 'loadcell', 'iot_gateway', 'core'):
        cursor.execute(
            'INSERT OR IGNORE INTO pipeline_send_log (config_type, last_version, last_status) VALUES (?, 0, "never")',
            (cfg_type,)
        )

    # Default port/path configuration
    for device_type, port_number, label, port_value in [
        ('modbus',   1, 'Port 1', '/dev/ttymxc5'),
        ('modbus',   2, 'Port 2', '/dev/ttymxc2'),
        ('loadcell', 1, 'Channel 1', '/sys/bus/iio/devices/iio:device0/in_voltage0_raw'),
        ('loadcell', 2, 'Channel 2', '/sys/bus/iio/devices/iio:device1/in_voltage0_raw'),
    ]:
        cursor.execute(
            'INSERT OR IGNORE INTO port_config (device_type, port_number, label, port_value) VALUES (?, ?, ?, ?)',
            (device_type, port_number, label, port_value)
        )


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def verify_admin_user(username, password):
    """Return user dict if credentials are valid, else None."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, username, role FROM admin_users WHERE username=? AND password=? AND enabled=1',
            (username, _hash_password(password))
        )
        row = cursor.fetchone()
        if row:
            cursor.execute('UPDATE admin_users SET last_login=CURRENT_TIMESTAMP WHERE id=?', (row[0],))
            conn.commit()
        conn.close()
        return {'id': row[0], 'username': row[1], 'role': row[2]} if row else None
    except Exception as e:
        print("[DB] verify_admin_user error: {}".format(e))
        return None


def verify_webui_user(username, password):
    """Return user dict if credentials are valid, else None."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, username, display_name FROM webui_users WHERE username=? AND password=? AND enabled=1',
            (username, _hash_password(password))
        )
        row = cursor.fetchone()
        if row:
            cursor.execute('UPDATE webui_users SET last_login=CURRENT_TIMESTAMP WHERE id=?', (row[0],))
            conn.commit()
        conn.close()
        return {'id': row[0], 'username': row[1], 'display_name': row[2]} if row else None
    except Exception as e:
        print("[DB] verify_webui_user error: {}".format(e))
        return None


# ---------------------------------------------------------------------------
# Pipeline service target helpers
# ---------------------------------------------------------------------------

def get_pipeline_service_name(config_type):
    """Return the configured pipeline service name for a config type."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT service_name FROM pipeline_service_targets WHERE config_type=?', (config_type,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else ''
    except Exception as e:
        print("[DB] get_pipeline_service_name error: {}".format(e))
        return ''


def set_pipeline_service_name(config_type, service_name, config_name=None):
    """Update the pipeline service name (and optionally config_name) for a config type."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if config_name is not None:
            cursor.execute(
                'UPDATE pipeline_service_targets SET service_name=?, config_name=?, updated_at=CURRENT_TIMESTAMP WHERE config_type=?',
                (service_name, config_name, config_type)
            )
        else:
            cursor.execute(
                'UPDATE pipeline_service_targets SET service_name=?, updated_at=CURRENT_TIMESTAMP WHERE config_type=?',
                (service_name, config_type)
            )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("[DB] set_pipeline_service_name error: {}".format(e))
        return False


def get_pipeline_config_name(config_type):
    """Return the configured pipeline config name for a config type (e.g. 'modbus_config')."""
    _defaults = {
        'modbus':      'modbus_config',
        'loadcell':    'loadcell_config',
        'iot_gateway': 'gateway_config',
        'core':        'iq_core',
    }
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT config_name FROM pipeline_service_targets WHERE config_type=?', (config_type,))
        row = cursor.fetchone()
        conn.close()
        val = row[0] if row else ''
        return val if val else _defaults.get(config_type, config_type + '_config')
    except Exception as e:
        print("[DB] get_pipeline_config_name error: {}".format(e))
        return _defaults.get(config_type, config_type + '_config')


def get_all_pipeline_service_targets():
    """Return all pipeline service target rows."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT config_type, service_name, config_name, enabled, description, updated_at '
            'FROM pipeline_service_targets ORDER BY config_type'
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'config_type':  r[0],
                'service_name': r[1],
                'config_name':  r[2] if r[2] else (r[0] + '_config'),
                'enabled':      bool(r[3]),
                'description':  r[4],
                'updated_at':   r[5],
            }
            for r in rows
        ]
    except Exception as e:
        print("[DB] get_all_pipeline_service_targets error: {}".format(e))
        return []


# ---------------------------------------------------------------------------
# Pipeline send log helpers
# ---------------------------------------------------------------------------

def get_pipeline_send_log(config_type):
    """Return the send-log row for a config_type, or default dict."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT last_version, last_sent_at, last_service, last_status, last_message '
            'FROM pipeline_send_log WHERE config_type=?', (config_type,)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                'config_type':  config_type,
                'last_version': row[0],
                'last_sent_at': row[1],
                'last_service': row[2],
                'last_status':  row[3],
                'last_message': row[4],
            }
        return {'config_type': config_type, 'last_version': 0, 'last_sent_at': None,
                'last_service': '', 'last_status': 'never', 'last_message': ''}
    except Exception as e:
        print("[DB] get_pipeline_send_log error: {}".format(e))
        return {'config_type': config_type, 'last_version': 0}


def get_next_pipeline_version(config_type):
    """Read last_version from DB and return last_version + 1 (does NOT write)."""
    row = get_pipeline_send_log(config_type)
    return (row.get('last_version') or 0) + 1


def record_pipeline_send_success(config_type, version, service_name, message=''):
    """Called ONLY when pipeline send succeeds -- persists the new version."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE pipeline_send_log
               SET last_version=?, last_sent_at=CURRENT_TIMESTAMP,
                   last_service=?, last_status='success', last_message=?
               WHERE config_type=?""",
            (version, service_name, message, config_type)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("[DB] record_pipeline_send_success error: {}".format(e))
        return False


def record_pipeline_send_failure(config_type, message=''):
    """Record a failed send attempt (version NOT incremented)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE pipeline_send_log
               SET last_sent_at=CURRENT_TIMESTAMP, last_status='failed', last_message=?
               WHERE config_type=?""",
            (message, config_type)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("[DB] record_pipeline_send_failure error: {}".format(e))
        return False


def get_all_pipeline_send_logs():
    """Return all send log rows."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT config_type, last_version, last_sent_at, last_service, last_status, last_message '
            'FROM pipeline_send_log ORDER BY config_type'
        )
        rows = cursor.fetchall()
        conn.close()
        return [{'config_type': r[0], 'last_version': r[1], 'last_sent_at': r[2],
                 'last_service': r[3], 'last_status': r[4], 'last_message': r[5]} for r in rows]
    except Exception as e:
        print("[DB] get_all_pipeline_send_logs error: {}".format(e))
        return []


def get_enabled_pipeline_targets():
    """Return only enabled service targets (for Auto-Send)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT config_type, service_name FROM pipeline_service_targets WHERE enabled=1 ORDER BY config_type'
        )
        rows = cursor.fetchall()
        conn.close()
        return [{'config_type': r[0], 'service_name': r[1]} for r in rows]
    except Exception as e:
        print("[DB] get_enabled_pipeline_targets error: {}".format(e))
        return []



# ---------------------------------------------------------------------------
# General configuration helpers
# ---------------------------------------------------------------------------

def get_general_configuration():
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
                'name':            row[0], 'serial_number': row[1],
                'deployment_site': row[2], 'location_mode': row[3],
                'latitude':        row[4], 'longitude':     row[5],
                'asset_id':        row[6],
            },
            'date_time': {
                'timezone': row[8], 'ntp_server': row[9],
                'date_format': row[10], 'time_format': row[11], 'language': row[12],
            },
            'heartbeat': {'interval': row[13], 'offline_threshold': row[14]},
            'mac_address': row[7],
            'network': {
                'mode': row[15],
                'wifi':     {'ssid': row[16], 'password': row[17]},
                'ethernet': {
                    'ip_assignment': row[18], 'static_ip':  row[19],
                    'subnet_mask':   row[20], 'gateway':    row[21],
                    'dns1':          row[22], 'dns2':       row[23],
                },
                'cellular': {'apn': row[24], 'username': row[25], 'password': row[26]},
            },
        }
    except Exception as e:
        print("Error getting general config: {}".format(e))
        return {}


def update_general_configuration(config_data):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sets, values = [], []

        def _add(col, val):
            sets.append('{} = ?'.format(col))
            values.append(val)

        gi = config_data.get('gateway_identity', {})
        if 'name'            in gi: _add('gateway_name',    gi['name'])
        if 'serial_number'   in gi: _add('serial_number',   gi['serial_number'])
        if 'deployment_site' in gi: _add('deployment_site', gi['deployment_site'])
        if 'location_mode'   in gi: _add('location_mode',   gi['location_mode'])
        if 'latitude'        in gi: _add('latitude',        gi['latitude'])
        if 'longitude'       in gi: _add('longitude',       gi['longitude'])
        if 'asset_id'        in gi: _add('asset_id',        gi['asset_id'])

        dt = config_data.get('date_time', {})
        if 'timezone'    in dt: _add('timezone',    dt['timezone'])
        if 'ntp_server'  in dt: _add('ntp_server',  dt['ntp_server'])
        if 'date_format' in dt: _add('date_format', dt['date_format'])
        if 'time_format' in dt: _add('time_format', dt['time_format'])
        if 'language'    in dt: _add('language',    dt['language'])

        hb = config_data.get('heartbeat', {})
        if 'interval'          in hb: _add('heartbeat_interval', hb['interval'])
        if 'offline_threshold' in hb: _add('offline_threshold',  hb['offline_threshold'])

        if 'mac_address' in config_data:
            _add('mac_address', config_data['mac_address'])

        net = config_data.get('network', {})
        if 'mode' in net: _add('network_mode', net['mode'])

        wifi = net.get('wifi', {})
        if 'ssid'     in wifi: _add('wifi_ssid',     wifi['ssid'])
        if 'password' in wifi: _add('wifi_password', wifi['password'])

        eth = net.get('ethernet', {})
        if 'ip_assignment' in eth: _add('eth_ip_assignment', eth['ip_assignment'])
        if 'static_ip'     in eth: _add('eth_static_ip',     eth['static_ip'])
        if 'subnet_mask'   in eth: _add('eth_subnet_mask',   eth['subnet_mask'])
        if 'gateway'       in eth: _add('eth_gateway',       eth['gateway'])
        if 'dns1'          in eth: _add('eth_dns1',          eth['dns1'])
        if 'dns2'          in eth: _add('eth_dns2',          eth['dns2'])

        cell = net.get('cellular', {})
        if 'apn'      in cell: _add('cell_apn',      cell['apn'])
        if 'username' in cell: _add('cell_username',  cell['username'])
        if 'password' in cell: _add('cell_password',  cell['password'])

        if sets:
            cursor.execute(
                'UPDATE general_configuration SET {}, updated_at = CURRENT_TIMESTAMP WHERE id = 1'
                .format(', '.join(sets)),
                values
            )
            conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("Error updating general config: {}".format(e))
        return False


# ---------------------------------------------------------------------------
# Device groups
# ---------------------------------------------------------------------------

def get_all_tag_groups():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, color, description, created_at FROM tag_groups ORDER BY name')
        rows = cursor.fetchall()
        conn.close()
        return [{'id': r[0], 'name': r[1], 'color': r[2], 'description': r[3], 'created_at': r[4]} for r in rows]
    except Exception as e:
        print("Error getting device groups: {}".format(e))
        return []


def add_tag_group(name, color='blue', description=''):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO tag_groups (name, color, description) VALUES (?, ?, ?)', (name, color, description))
        gid = cursor.lastrowid
        conn.commit()
        conn.close()
        return gid
    except Exception as e:
        print("Error adding device group: {}".format(e))
        return None


def delete_tag_group(group_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE vfd_datapoints SET group_id = NULL WHERE group_id = ?', (group_id,))
        cursor.execute('DELETE FROM tag_groups WHERE id = ?', (group_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("Error deleting device group: {}".format(e))
        return False


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

def get_all_services():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, description, enabled FROM services ORDER BY name')
        rows = cursor.fetchall()
        conn.close()
        return [{'id': r[0], 'name': r[1], 'description': r[2], 'enabled': r[3]} for r in rows]
    except Exception as e:
        print("Error getting services: {}".format(e))
        return []


def get_service_by_name(name):
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


# ---------------------------------------------------------------------------
# Database stats
# ---------------------------------------------------------------------------

def get_database_stats():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        stats = {}
        for label, table in [
            ('vfd_devices',            'vfd_device'),
            ('loadcell_devices',       'loadcell_device'),
            ('external_devices',       'external_device'),
            ('vfd_datapoints',         'vfd_datapoints'),
            ('loadcell_datapoints',    'loadcell_datapoints'),
            ('external_datapoints',    'external_datapoints'),
            ('groups',                 'tag_groups'),
            ('admin_users',            'admin_users'),
            ('webui_users',            'webui_users'),
        ]:
            cursor.execute('SELECT COUNT(*) FROM {}'.format(table))
            stats[label] = cursor.fetchone()[0]
        conn.close()
        stats['total_devices']    = stats['vfd_devices'] + stats['loadcell_devices'] + stats.get('external_devices', 0)
        stats['total_datapoints'] = stats['vfd_datapoints'] + stats['loadcell_datapoints'] + stats.get('external_datapoints', 0)
        stats['total_datapoints'] = stats['vfd_datapoints'] + stats['loadcell_datapoints']
        return stats
    except Exception as e:
        print("Error getting stats: {}".format(e))
        return {}


# ---------------------------------------------------------------------------
# Admin users CRUD
# ---------------------------------------------------------------------------

def get_all_admin_users():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, role, enabled, last_login, created_at FROM admin_users ORDER BY username')
        rows = cursor.fetchall()
        conn.close()
        return [{'id': r[0], 'username': r[1], 'role': r[2], 'enabled': r[3],
                 'last_login': r[4], 'created_at': r[5]} for r in rows]
    except Exception as e:
        print("Error getting admin users: {}".format(e))
        return []


def create_admin_user(username, password, role='operator'):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO admin_users (username, password, role) VALUES (?, ?, ?)',
            (username, _hash_password(password), role)
        )
        uid = cursor.lastrowid
        conn.commit()
        conn.close()
        return uid
    except Exception as e:
        print("Error creating admin user: {}".format(e))
        return None


def update_admin_user(user_id, data):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sets, values = [], []
        if 'username' in data:
            sets.append('username=?'); values.append(data['username'])
        if 'password' in data:
            sets.append('password=?'); values.append(_hash_password(data['password']))
        if 'role' in data:
            sets.append('role=?'); values.append(data['role'])
        if 'enabled' in data:
            sets.append('enabled=?'); values.append(1 if data['enabled'] else 0)
        if sets:
            values.append(user_id)
            cursor.execute(
                'UPDATE admin_users SET {}, updated_at=CURRENT_TIMESTAMP WHERE id=?'.format(', '.join(sets)),
                values
            )
            conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("Error updating admin user: {}".format(e))
        return False


def delete_admin_user(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM admin_users WHERE id=?', (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("Error deleting admin user: {}".format(e))
        return False


# ---------------------------------------------------------------------------
# WebUI users CRUD
# ---------------------------------------------------------------------------

def get_webui_user_max_sessions(user_id):
    """Return the max_sessions limit for a webui user (default 1)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT max_sessions FROM webui_users WHERE id=?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        return int(row[0]) if row and row[0] is not None else 1
    except Exception:
        return 1


def set_webui_user_max_sessions(user_id, max_sessions):
    """Set the max concurrent session limit for a webui user."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE webui_users SET max_sessions=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (int(max_sessions), user_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def get_all_webui_users():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, display_name, enabled, last_login, created_at FROM webui_users ORDER BY username')
        rows = cursor.fetchall()
        conn.close()
        return [{'id': r[0], 'username': r[1], 'display_name': r[2], 'enabled': r[3],
                 'last_login': r[4], 'created_at': r[5]} for r in rows]
    except Exception as e:
        print("Error getting webui users: {}".format(e))
        return []


def create_webui_user(username, password, display_name=''):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO webui_users (username, password, display_name) VALUES (?, ?, ?)',
            (username, _hash_password(password), display_name)
        )
        uid = cursor.lastrowid
        conn.commit()
        conn.close()
        return uid
    except Exception as e:
        print("Error creating webui user: {}".format(e))
        return None


def update_webui_user(user_id, data):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sets, values = [], []
        if 'username'     in data: sets.append('username=?');     values.append(data['username'])
        if 'password'     in data: sets.append('password=?');     values.append(_hash_password(data['password']))
        if 'display_name' in data: sets.append('display_name=?'); values.append(data['display_name'])
        if 'enabled'      in data: sets.append('enabled=?');      values.append(1 if data['enabled'] else 0)
        if sets:
            values.append(user_id)
            cursor.execute(
                'UPDATE webui_users SET {}, updated_at=CURRENT_TIMESTAMP WHERE id=?'.format(', '.join(sets)),
                values
            )
            conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("Error updating webui user: {}".format(e))
        return False


def delete_webui_user(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM webui_users WHERE id=?', (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("Error deleting webui user: {}".format(e))
        return False


# ---------------------------------------------------------------------------
# Rules helpers
# ---------------------------------------------------------------------------

def get_all_rules():
    import json as _json
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT * FROM rules ORDER BY created_at DESC')
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        for r in rows:
            try:
                r['groups'] = _json.loads(r.get('groups_json') or '{}')
            except Exception:
                r['groups'] = {}
        return rows
    except Exception as e:
        print("get_all_rules error: {}".format(e))
        return []


def save_rule(rule):
    import json as _json
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Avoid ON CONFLICT(...) DO UPDATE -- requires SQLite >= 3.24 (not in Python 3.5).
        rule_id     = rule['id']
        name        = rule.get('name', '')
        rule_type   = rule.get('ruleType', rule.get('rule_type', 'group'))
        priority    = rule.get('priority', 'medium')
        description = rule.get('description', '')
        enabled     = 1 if rule.get('enabled', True) else 0
        groups_json = _json.dumps(rule.get('groups', {}))
        relay_dp    = rule.get('relayDatapoint', rule.get('relay_datapoint', ''))

        cur.execute('SELECT id FROM rules WHERE id=?', (rule_id,))
        if cur.fetchone():
            cur.execute('''
                UPDATE rules
                SET name=?, rule_type=?, priority=?, description=?,
                    enabled=?, groups_json=?, relay_datapoint=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            ''', (name, rule_type, priority, description,
                  enabled, groups_json, relay_dp, rule_id))
        else:
            cur.execute('''
                INSERT INTO rules (id, name, rule_type, priority, description, enabled,
                                   groups_json, relay_datapoint, updated_at)
                VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
            ''', (rule_id, name, rule_type, priority, description,
                  enabled, groups_json, relay_dp))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("save_rule error: {}".format(e))
        return False


def delete_rule(rule_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM rules WHERE id=?', (rule_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("delete_rule error: {}".format(e))
        return False


def get_all_modbus_tags():
    """Return all enabled modbus tag names as a flat list."""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT name FROM vfd_datapoints WHERE enabled=1 ORDER BY name')
        tags = [row['name'] for row in cur.fetchall()]
        conn.close()
        return tags
    except Exception as e:
        print("get_all_modbus_tags error: {}".format(e))
        return []


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print("Initializing database...")
    init_database()
    print("\n=== Database Statistics ===")
    for k, v in get_database_stats().items():
        print("{}: {}".format(k, v))
else:
    init_database()


# ---------------------------------------------------------------------------
# WebUI Page Restrictions � per-user access control
# ---------------------------------------------------------------------------

# Master list of all pages in layout.html  (page_key, human label, sort_order)
WEBUI_PAGES = [
    ('general-configuration', 'General Configuration',    1),
    ('device-management',     'Device Management',         2),
    ('field-integration',     'Field Integration',         3),
    ('mqtt-cloud',            'MQTT / Cloud',              4),
    ('ota-gateway',           'OTA Gateway',               5),
    ('craneiq',               'CraneIQ',                   6),
    ('data-retention',        'Data Retention',            7),
    ('logging',               'Logging',                   8),
    ('diagnostics',           'Diagnostics',               9),
    ('security',              'Security',                 10),
    ('license',               'License',                  11),
    ('automation',            'Automation',               12),
    ('alerts',                'Alerts',                   13),
    ('rules',                 'Rules',                    14),
    ('backup',                'Backup',                   15),
    ('notification',          'Notification',             16),
]

ALL_PAGE_KEYS = [p[0] for p in WEBUI_PAGES]


def get_all_pages():
    """Return the master list of pages as dicts."""
    return [{'page_key': k, 'label': l, 'sort_order': o} for k, l, o in WEBUI_PAGES]


def get_user_page_restrictions(user_id):
    """Return list of page_key strings that are HIDDEN for this user."""
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute(
            'SELECT page_key FROM webui_user_page_restrictions WHERE user_id=?',
            (user_id,)
        )
        keys = [r[0] for r in cur.fetchall()]
        conn.close()
        return keys
    except Exception as e:
        print('get_user_page_restrictions error: {}'.format(e))
        return []


def set_user_page_restriction(user_id, page_key, hidden):
    """Add or remove a page restriction for a user. hidden=True means blocked."""
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        if hidden:
            cur.execute(
                'INSERT OR IGNORE INTO webui_user_page_restrictions (user_id, page_key) VALUES (?, ?)',
                (user_id, page_key)
            )
        else:
            cur.execute(
                'DELETE FROM webui_user_page_restrictions WHERE user_id=? AND page_key=?',
                (user_id, page_key)
            )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print('set_user_page_restriction error: {}'.format(e))
        return False


def get_pages_for_user(user_id):
    """Return list of {page_key, label, visible} for all pages for this user."""
    hidden = set(get_user_page_restrictions(user_id))
    return [
        {'page_key': k, 'label': l, 'sort_order': o, 'visible': k not in hidden}
        for k, l, o in WEBUI_PAGES
    ]

# ---------------------------------------------------------------------------
# Port / Path configuration helpers
# ---------------------------------------------------------------------------

def get_port_config(device_type=None):
    """Return port_config rows, optionally filtered by device_type ('modbus' or 'loadcell')."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if device_type:
            cursor.execute(
                'SELECT id, device_type, port_number, label, port_value '
                'FROM port_config WHERE device_type=? ORDER BY port_number',
                (device_type,)
            )
        else:
            cursor.execute(
                'SELECT id, device_type, port_number, label, port_value '
                'FROM port_config ORDER BY device_type, port_number'
            )
        rows = cursor.fetchall()
        conn.close()
        return [
            {'id': r[0], 'device_type': r[1], 'port_number': r[2],
             'label': r[3], 'port_value': r[4]}
            for r in rows
        ]
    except Exception as e:
        print('[DB] get_port_config error: {}'.format(e))
        return []


def get_port_label(device_type, port_value):
    """Return the UI label (e.g. 'Port 1') for a given actual port value."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT label FROM port_config WHERE device_type=? AND port_value=?',
            (device_type, port_value)
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else port_value
    except Exception as e:
        print('[DB] get_port_label error: {}'.format(e))
        return port_value