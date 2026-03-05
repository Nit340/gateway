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
    """Create all tables — schema is complete at creation, no ALTER TABLE migrations needed"""

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
        CREATE TABLE IF NOT EXISTS modbus_device (
            id                  TEXT    PRIMARY KEY,
            name                TEXT    NOT NULL,
            device_type         TEXT    NOT NULL CHECK(device_type IN ('tcp', 'rtu')),
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
        CREATE TABLE IF NOT EXISTS modbus_datapoints (
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
            FOREIGN KEY (device_id) REFERENCES modbus_device(id) ON DELETE CASCADE,
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
        CREATE TABLE IF NOT EXISTS mqtt_datapoints (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_id    TEXT    NOT NULL,
            tag_name         TEXT    NOT NULL,
            topic            TEXT    NOT NULL DEFAULT '',
            publish_mode     TEXT    NOT NULL DEFAULT 'onChange',
            change_threshold REAL    DEFAULT 0.0,
            enabled          INTEGER DEFAULT 1,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(connection_id, tag_name),
            FOREIGN KEY (connection_id) REFERENCES cloud_connections(id) ON DELETE CASCADE
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
                             CHECK(config_type IN ('modbus', 'loadcell', 'iot_gateway')),
            service_name TEXT    NOT NULL DEFAULT '',
            enabled      BOOLEAN DEFAULT 1,
            description  TEXT    DEFAULT '',
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # -----------------------------------------------------------------------
    # Pipeline send log — one row per config_type, tracks last sent version
    # Version is read from here, incremented, written back ONLY on success
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pipeline_send_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            config_type     TEXT    NOT NULL UNIQUE
                                CHECK(config_type IN ('modbus', 'loadcell', 'iot_gateway')),
            last_version    INTEGER NOT NULL DEFAULT 0,
            last_sent_at    TIMESTAMP,
            last_service    TEXT    DEFAULT '',
            last_status     TEXT    DEFAULT 'never',
            last_message    TEXT    DEFAULT ''
        )
    ''')


def _migrate_existing_db(cursor):
    """Safe additive migrations for DBs created before schema updates.
    Only adds missing columns — never drops or modifies existing data.
    """
    # pipeline_service_targets: add enabled column if missing
    cursor.execute("PRAGMA table_info(pipeline_service_targets)")
    cols = {r[1] for r in cursor.fetchall()}
    if 'enabled' not in cols:
        cursor.execute("ALTER TABLE pipeline_service_targets ADD COLUMN enabled BOOLEAN DEFAULT 1")
        print("[DB] Migration: added pipeline_service_targets.enabled")

    # pipeline_send_log: ensure table exists (added in later version)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_send_log'")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE pipeline_send_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                config_type     TEXT    NOT NULL UNIQUE
                                    CHECK(config_type IN ('modbus', 'loadcell', 'iot_gateway')),
                last_version    INTEGER NOT NULL DEFAULT 0,
                last_sent_at    TIMESTAMP,
                last_service    TEXT    DEFAULT '',
                last_status     TEXT    DEFAULT 'never',
                last_message    TEXT    DEFAULT ''
            )
        ''')
        for cfg_type in ('modbus', 'loadcell', 'iot_gateway'):
            cursor.execute(
                'INSERT OR IGNORE INTO pipeline_send_log (config_type) VALUES (?)', (cfg_type,)
            )
        print("[DB] Migration: created pipeline_send_log table")

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

    # rules table — stores each rule as a flat row with groups/datapoints as JSON
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


def _hash_password(plain):
    return hashlib.sha256(plain.encode()).hexdigest()


def insert_default_data(cursor):
    """Insert default seed data (idempotent — uses INSERT OR IGNORE)"""

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

    # Default WebUI user  (operator / operator123)
    cursor.execute(
        'INSERT OR IGNORE INTO webui_users (username, password, display_name) VALUES (?, ?, ?)',
        ('operator', _hash_password('operator123'), 'Crane Operator')
    )

    # Default pipeline service targets
    for cfg_type, svc_name, desc in [
        ('modbus',      'modbus_service',      'Modbus pipeline service name'),
        ('loadcell',    'load_cell_service',   'Load-cell pipeline service name'),
        ('iot_gateway', 'iot_gateway_service', 'IoT gateway pipeline service name'),
    ]:
        cursor.execute(
            'INSERT OR IGNORE INTO pipeline_service_targets (config_type, service_name, description, enabled) VALUES (?, ?, ?, 1)',
            (cfg_type, svc_name, desc)
        )

    # Default pipeline send log rows
    for cfg_type in ('modbus', 'loadcell', 'iot_gateway'):
        cursor.execute(
            'INSERT OR IGNORE INTO pipeline_send_log (config_type, last_version, last_status) VALUES (?, 0, "never")',
            (cfg_type,)
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


def set_pipeline_service_name(config_type, service_name):
    """Update the pipeline service name for a config type."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
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


def get_all_pipeline_service_targets():
    """Return all pipeline service target rows."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT config_type, service_name, enabled, description, updated_at '
            'FROM pipeline_service_targets ORDER BY config_type'
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                'config_type':  r[0],
                'service_name': r[1],
                'enabled':      bool(r[2]),
                'description':  r[3],
                'updated_at':   r[4],
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
    """Called ONLY when pipeline send succeeds — persists the new version."""
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
        cursor.execute('UPDATE modbus_datapoints SET group_id = NULL WHERE group_id = ?', (group_id,))
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
            ('modbus_devices',      'modbus_device'),
            ('loadcell_devices',    'loadcell_device'),
            ('modbus_datapoints',   'modbus_datapoints'),
            ('loadcell_datapoints', 'loadcell_datapoints'),
            ('groups',              'tag_groups'),
            ('admin_users',         'admin_users'),
            ('webui_users',         'webui_users'),
        ]:
            cursor.execute('SELECT COUNT(*) FROM {}'.format(table))
            stats[label] = cursor.fetchone()[0]
        conn.close()
        stats['total_devices']    = stats['modbus_devices'] + stats['loadcell_devices']
        stats['total_datapoints'] = stats['modbus_datapoints'] + stats['loadcell_datapoints']
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
        cur.execute('''
            INSERT INTO rules (id, name, rule_type, priority, description, enabled,
                               groups_json, relay_datapoint, updated_at)
            VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, priority=excluded.priority,
                description=excluded.description, enabled=excluded.enabled,
                groups_json=excluded.groups_json,
                relay_datapoint=excluded.relay_datapoint,
                updated_at=CURRENT_TIMESTAMP
        ''', (
            rule['id'],
            rule.get('name', ''),
            rule.get('ruleType', rule.get('rule_type', 'group')),
            rule.get('priority', 'medium'),
            rule.get('description', ''),
            1 if rule.get('enabled', True) else 0,
            _json.dumps(rule.get('groups', {})),
            rule.get('relayDatapoint', rule.get('relay_datapoint', '')),
        ))
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
        cur.execute('SELECT name FROM modbus_datapoints WHERE enabled=1 ORDER BY name')
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