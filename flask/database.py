# -*- coding: utf-8 -*-
# database.py - Database initialization and operations (FIXED)
import sqlite3
import json
import hashlib
import os
import threading
import atexit
import traceback
from datetime import datetime
from contextlib import contextmanager
from logger_util import get_logger

logger = get_logger(__name__)

# Debug flag - set to True to enable connection tracking
_DEBUG_DB = False

def _log_debug(msg):
    """Log debug messages if _DEBUG_DB is enabled."""
    if _DEBUG_DB:
        logger.debug(msg)

# Database path - configurable via environment variable
_DB_DIR = os.environ.get('GATEWAY_DB_DIR', '/mnt/data')
DB_FILE = os.environ.get('GATEWAY_DB_FILE', os.path.join(_DB_DIR, 'gateway_config.db'))

# Create the directory if it does not exist
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)

# ============================================================================
# FIXED: Thread-local connection pool with proper handling
# ============================================================================
_thread_local = threading.local()
_db_initialized = False
_init_lock = threading.Lock()

# Track all connections to prevent accidental closure
_global_connections = set()
_global_lock = threading.Lock()


class _SafeConnection:
    """Wrapper around sqlite3.Connection that prevents accidental closure.
    Only allows closure through _real_close() method.
    """
    def __init__(self, conn):
        self._conn = conn
        
    def close(self):
        """Prevent accidental closure - use _real_close() instead."""
        _log_debug("WARNING: Prevented close of connection from thread: {}".format(
            threading.current_thread().name))
        if _DEBUG_DB:
            traceback.print_stack()
        # Don't actually close
    
    def _real_close(self):
        """Actually close the underlying connection."""
        _log_debug("Actually closing connection for thread: {}".format(
            threading.current_thread().name))
        return self._conn.close()
    
    def __getattr__(self, name):
        """Delegate all other attributes to the real connection."""
        return getattr(self._conn, name)


def get_db_connection():
    """Get a database connection with WAL mode and thread-local pooling.
    NEVER close this connection - it's managed by the thread.
    """
    if not hasattr(_thread_local, 'connection') or _thread_local.connection is None:
        _log_debug("Creating new connection for thread: {}".format(threading.current_thread().name))
        conn = sqlite3.connect(DB_FILE, timeout=30.0, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA cache_size = -2000')  # 2MB cache
        conn.execute('PRAGMA busy_timeout = 30000')  # 30 second timeout
        conn.row_factory = sqlite3.Row
        
        # Disable automatic commit - we'll manage manually
        conn.isolation_level = None
        
        # Wrap connection to prevent accidental closure
        safe_conn = _SafeConnection(conn)
        _thread_local.connection = safe_conn
        
        # Track this connection globally
        with _global_lock:
            _global_connections.add(safe_conn)
    
    return _thread_local.connection


def ensure_connection_alive():
    """Check if the current thread's connection is alive, recreate if dead."""
    if hasattr(_thread_local, 'connection') and _thread_local.connection is not None:
        try:
            # Test the connection with a simple query
            cursor = _thread_local.connection.cursor()
            cursor.execute('SELECT 1')
            cursor.fetchone()
            cursor.close()
            return True
        except Exception as e:
            _log_debug("Connection dead for thread {}, recreating: {}".format(
                threading.current_thread().name, e))
            try:
                # Use _real_close if it's a wrapped connection
                if hasattr(_thread_local.connection, '_real_close'):
                    _thread_local.connection._real_close()
                elif hasattr(_thread_local.connection, '_conn'):
                    _thread_local.connection._conn.close()
            except:
                pass
            _thread_local.connection = None
            get_db_connection()
            return True
    else:
        get_db_connection()
        return True


@contextmanager
def get_cursor():
    """Context manager for database cursors with auto commit/rollback.
    CRITICAL: Does NOT close the connection - uses thread-local connection.
    """
    # Ensure connection is alive before use
    ensure_connection_alive()
    conn = get_db_connection()
    
    try:
        # Start transaction
        conn.execute('BEGIN')
        cursor = conn.cursor()
        
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
    except Exception as e:
        _log_debug("Database error in get_cursor: {}".format(e))
        raise
    # NEVER close the connection here


def close_all_connections():
    """Close all database connections (for shutdown only)."""
    _log_debug("Closing all database connections")
    with _global_lock:
        for conn in _global_connections:
            try:
                if hasattr(conn, '_real_close'):
                    conn._real_close()
                elif hasattr(conn, '_conn'):
                    conn._conn.close()
                else:
                    conn.close()
            except Exception as e:
                _log_debug("Error closing connection: {}".format(e))
        _global_connections.clear()
    
    # Also clear thread-local
    if hasattr(_thread_local, 'connection'):
        try:
            if _thread_local.connection:
                if hasattr(_thread_local.connection, '_real_close'):
                    _thread_local.connection._real_close()
                elif hasattr(_thread_local.connection, '_conn'):
                    _thread_local.connection._conn.close()
        except Exception as e:
            _log_debug("Error closing thread-local connection: {}".format(e))
        _thread_local.connection = None


def execute_with_retry(func, *args, **kwargs):
    """Execute database function with retry on locked database."""
    max_retries = 3
    last_error = None
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except sqlite3.OperationalError as e:
            last_error = e
            if 'database is locked' in str(e) and attempt < max_retries - 1:
                import time
                time.sleep(0.1 * (attempt + 1))
                continue
            raise
        except Exception as e:
            raise e
    if last_error:
        raise last_error


def ensure_db_initialized():
    """Initialize database only once, called explicitly from main.py."""
    global _db_initialized
    if _db_initialized:
        return
    
    with _init_lock:
        if _db_initialized:
            return
        init_database()
        _db_initialized = True


def init_database():
    """Initialize SQLite database with full schema"""
    _log_debug("Initializing database schema")
    # Use a temporary connection for initialization
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys = ON')
    cursor = conn.cursor()
    
    create_tables(cursor)
    insert_default_data(cursor)
    _migrate_existing_db(cursor)
    _create_indexes(cursor)
    
    conn.commit()
    # This is a temporary connection, so actually close it
    cursor.close()
    conn.close()
    logger.info("[DB] Database initialized: {}".format(DB_FILE))
    logger.info("[DB] All tables created/verified OK")


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
            -- Ethernet: which interface is selected (eth0 or eth1)
            eth_selected        TEXT    DEFAULT 'eth0',

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
    # Loadcell device
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS loadcell_device (
            id               TEXT    PRIMARY KEY,
            name             TEXT    NOT NULL,
            service_id       INTEGER,

            device_path      TEXT    NOT NULL DEFAULT '/sys/bus/iio/devices/iio:device0/in_voltage0_raw',
            device_path_ch2  TEXT    DEFAULT NULL,
            lc_mode          TEXT    DEFAULT 'init' CHECK(lc_mode IN ('init', 'single_ended', 'differential', 'indifferential')),

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

            deadband         REAL    DEFAULT 0.0,
            overload         REAL    DEFAULT 0.0,

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
    # Loadcell datapoints
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS loadcell_datapoints (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id  TEXT    NOT NULL,
            name       TEXT    NOT NULL,
            unit       TEXT    DEFAULT '',
            group_id   INTEGER DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(device_id, name),
            FOREIGN KEY (device_id) REFERENCES loadcell_device(id) ON DELETE CASCADE,
            FOREIGN KEY (group_id) REFERENCES tag_groups(id) ON DELETE SET NULL
        )
    ''')

    # -----------------------------------------------------------------------
    # loadcell_device schema migrations (v2 additions)
    # -----------------------------------------------------------------------
    for _col, _defn in [
        ('publish_step_grams', 'REAL    DEFAULT 1.0'),
        ('action_tare',        'TEXT    DEFAULT NULL'),
        ('action_calibrate',   'TEXT    DEFAULT NULL'),
        ('deadband',           'REAL    DEFAULT 0.0'),
        ('overload',           'REAL    DEFAULT 0.0'),
    ]:
        try:
            cursor.execute('ALTER TABLE loadcell_device ADD COLUMN {} {}'.format(_col, _defn))
        except Exception:
            pass

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
    # Admin users
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
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

    # -----------------------------------------------------------------------
    # WebUI users
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS webui_users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT    NOT NULL UNIQUE,
            password   TEXT    NOT NULL,
            display_name TEXT  DEFAULT '',
            role       TEXT    NOT NULL DEFAULT 'user' CHECK(role IN ('admin', 'user')),
            enabled    BOOLEAN DEFAULT 1,
            max_sessions INTEGER DEFAULT 2,
            last_login TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # -----------------------------------------------------------------------
    # Pipeline service targets
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
    # Pipeline send log
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
    # Modal configuration table
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS modal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intname TEXT UNIQUE,
            modal_text TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_modal_intname ON modal (intname)')
    
    # -----------------------------------------------------------------------
    # Metadata table (Gateway-specific tags)
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            datatype    TEXT    NOT NULL DEFAULT 'float',
            source      TEXT    NOT NULL DEFAULT 'Univa-gateway',
            component   TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # -----------------------------------------------------------------------
    # External Devices
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS external_device (
            id                  TEXT    PRIMARY KEY,
            name                TEXT    NOT NULL,
            protocol            TEXT    DEFAULT 'ext-rtu'
                                    CHECK(protocol IN ('ext-rtu', 'ext-tcp', 'external')),
            device_type         TEXT    DEFAULT '',
            model_name          TEXT    DEFAULT '',
            slave_id            INTEGER DEFAULT 1,
            response_timeout_ms INTEGER DEFAULT 100,
            byte_timeout_ms     INTEGER DEFAULT 100,
            max_retries         INTEGER DEFAULT 2,
            polling_interval_ms INTEGER DEFAULT 300,
            serial_port         TEXT    DEFAULT '/dev/ttymxc5',
            baud_rate           INTEGER DEFAULT 9600,
            data_bits           INTEGER DEFAULT 8,
            parity              TEXT    DEFAULT 'N',
            stop_bits           INTEGER DEFAULT 1,
            ip_address          TEXT    DEFAULT '',
            port                INTEGER DEFAULT 502,
            enabled             BOOLEAN DEFAULT 1,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            retry_count      INTEGER DEFAULT 3,
            timeout_ms       INTEGER DEFAULT 100,
            register_count   INTEGER DEFAULT 1,
            group_id         INTEGER DEFAULT NULL,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(device_id, name),
            FOREIGN KEY (device_id) REFERENCES external_device(id) ON DELETE CASCADE,
            FOREIGN KEY (group_id) REFERENCES tag_groups(id) ON DELETE SET NULL
        )
    ''')

    # -----------------------------------------------------------------------
    # WebUI Page Restrictions
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
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS port_config (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            device_type TEXT    NOT NULL CHECK(device_type IN ('loadcell')),
            port_number INTEGER NOT NULL,
            label       TEXT    NOT NULL,
            port_value  TEXT    NOT NULL,
            UNIQUE(device_type, port_number)
        )
    ''')

    # -----------------------------------------------------------------------
    # Rules table
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rules (
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


def _migrate_existing_db(cursor):
    """Safe additive migrations for DBs created before schema updates."""
    # pipeline_service_targets CHECK constraint
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='pipeline_service_targets'")
    _pst_row = cursor.fetchone()
    if _pst_row and "'modbus'" not in _pst_row[0] and 'modbus' not in _pst_row[0]:
        logger.info("[DB] Migration: rebuilding pipeline_service_targets")
        cursor.execute("ALTER TABLE pipeline_service_targets RENAME TO _pipeline_service_targets_old")
        cursor.execute('''
            CREATE TABLE pipeline_service_targets (
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
        cursor.execute('''
            INSERT INTO pipeline_service_targets
                (config_type, service_name, config_name, enabled, description, updated_at)
            SELECT config_type, service_name, config_name, enabled, description, updated_at
            FROM _pipeline_service_targets_old
        ''')
        cursor.execute("DROP TABLE _pipeline_service_targets_old")

    cursor.execute("SELECT 1 FROM pipeline_service_targets WHERE config_type='modbus'")
    if not cursor.fetchone():
        cursor.execute("INSERT OR IGNORE INTO pipeline_service_targets "
                      "(config_type, service_name, config_name, description, enabled) VALUES (?, ?, ?, ?, 1)",
                      ('modbus', 'modbus_service', 'modbus_config', 'Modbus pipeline service name'))

    # pipeline_send_log CHECK constraint
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='pipeline_send_log'")
    _psl_row = cursor.fetchone()
    if _psl_row and "'modbus'" not in _psl_row[0] and 'modbus' not in _psl_row[0]:
        logger.info("[DB] Migration: rebuilding pipeline_send_log")
        cursor.execute("ALTER TABLE pipeline_send_log RENAME TO _pipeline_send_log_old")
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
        cursor.execute('''
            INSERT INTO pipeline_send_log
                (config_type, last_version, last_sent_at, last_service, last_status, last_message)
            SELECT config_type, last_version, last_sent_at, last_service, last_status, last_message
            FROM _pipeline_send_log_old
        ''')
        cursor.execute("DROP TABLE _pipeline_send_log_old")

    cursor.execute("SELECT 1 FROM pipeline_send_log WHERE config_type='modbus'")
    if not cursor.fetchone():
        cursor.execute("INSERT OR IGNORE INTO pipeline_send_log (config_type, last_version, last_status) VALUES (?, 0, 'never')", ('modbus',))

    # Add missing columns
    cursor.execute("PRAGMA table_info(pipeline_service_targets)")
    cols = {r[1] for r in cursor.fetchall()}
    if 'enabled' not in cols:
        cursor.execute("ALTER TABLE pipeline_service_targets ADD COLUMN enabled BOOLEAN DEFAULT 1")
    if 'config_name' not in cols:
        cursor.execute("ALTER TABLE pipeline_service_targets ADD COLUMN config_name TEXT NOT NULL DEFAULT ''")

    # Add missing columns to external_datapoints
    cursor.execute("PRAGMA table_info(external_datapoints)")
    ext_cols = {r[1] for r in cursor.fetchall()}
    for col_name, col_def in [('retry_count', 'INTEGER DEFAULT 3'), ('timeout_ms', 'INTEGER DEFAULT 100'),
                               ('register_count', 'INTEGER DEFAULT 1'), ('group_id', 'INTEGER DEFAULT NULL')]:
        if col_name not in ext_cols:
            try:
                cursor.execute('ALTER TABLE external_datapoints ADD COLUMN {} {}'.format(col_name, col_def))
            except Exception:
                pass

    # Add group_id to loadcell_datapoints
    cursor.execute("PRAGMA table_info(loadcell_datapoints)")
    lc_cols = {r[1] for r in cursor.fetchall()}
    if 'group_id' not in lc_cols:
        try:
            cursor.execute('ALTER TABLE loadcell_datapoints ADD COLUMN group_id INTEGER DEFAULT NULL')
        except Exception:
            pass

    # Add max_sessions to webui_users
    cursor.execute("PRAGMA table_info(webui_users)")
    webui_cols = [r[1] for r in cursor.fetchall()]
    if 'max_sessions' not in webui_cols:
        cursor.execute('ALTER TABLE webui_users ADD COLUMN max_sessions INTEGER DEFAULT 2')

    # Add lc_mode to loadcell_device
    cursor.execute("PRAGMA table_info(loadcell_device)")
    lc_dev_cols = {r[1] for r in cursor.fetchall()}
    if 'lc_mode' not in lc_dev_cols:
        cursor.execute("ALTER TABLE loadcell_device ADD COLUMN lc_mode TEXT DEFAULT 'init'")
    if 'device_path_ch2' not in lc_dev_cols:
        cursor.execute("ALTER TABLE loadcell_device ADD COLUMN device_path_ch2 TEXT DEFAULT NULL")

    # Add eth_selected to general_configuration (persists which ethernet interface is active)
    cursor.execute("PRAGMA table_info(general_configuration)")
    gc_cols = {r[1] for r in cursor.fetchall()}
    if 'eth_selected' not in gc_cols:
        cursor.execute("ALTER TABLE general_configuration ADD COLUMN eth_selected TEXT DEFAULT 'eth0'")
    # Add auto_connect to general_configuration (persists Auto-connect toggle state)
    if 'auto_connect' not in gc_cols:
        cursor.execute("ALTER TABLE general_configuration ADD COLUMN auto_connect INTEGER DEFAULT 0")
    # Add load_raw_enabled to general_configuration (persists the Raw toggle state)
    if 'load_raw_enabled' not in gc_cols:
        cursor.execute("ALTER TABLE general_configuration ADD COLUMN load_raw_enabled INTEGER DEFAULT 0")

    # Migration for modal table: remove modal_time column
    cursor.execute("PRAGMA table_info(modal)")
    modal_cols = {r[1] for r in cursor.fetchall()}
    if 'modal_time' in modal_cols:
        logger.info("[DB] Migration: removing modal_time from modal table")
        # Since it's a small config table, just drop and let it recreate/reseed
        cursor.execute("DROP TABLE modal")
        cursor.execute('''
            CREATE TABLE modal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                intname TEXT UNIQUE,
                modal_text TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')


def _create_indexes(cursor):
    """Create indexes on frequently queried columns."""
    indexes = [
        ('idx_external_device_enabled', 'external_device', 'enabled'),
        ('idx_external_datapoints_device_id', 'external_datapoints', 'device_id'),
        ('idx_external_datapoints_enabled', 'external_datapoints', 'enabled'),
        ('idx_loadcell_device_enabled', 'loadcell_device', 'enabled'),
        ('idx_loadcell_datapoints_device_id', 'loadcell_datapoints', 'device_id'),
        ('idx_admin_users_username', 'admin_users', 'username'),
        ('idx_webui_users_username', 'webui_users', 'username'),
    ]
    
    for index_name, table_name, column_name in indexes:
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info({})".format(table_name))
                columns = {col[1] for col in cursor.fetchall()}
                if column_name in columns:
                    cursor.execute('CREATE INDEX IF NOT EXISTS {} ON {} ({})'.format(
                        index_name, table_name, column_name))
        except Exception as e:
            logger.warning('[DB] Warning: Could not create index {}: {}'.format(index_name, e))
    
    logger.info('[DB] Performance indexes created')


def _hash_password(plain):
    return hashlib.sha256(plain.encode()).hexdigest()


def insert_default_data(cursor):
    """Insert default seed data."""
    cursor.execute('SELECT COUNT(*) FROM general_configuration')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO general_configuration (id) VALUES (1)')

    for name, desc in [('loadcell', 'Loadcell Service')]:
        cursor.execute('INSERT OR IGNORE INTO services (name, description) VALUES (?, ?)', (name, desc))

    cursor.execute('INSERT OR IGNORE INTO admin_users (username, password, role) VALUES (?, ?, ?)',
                   ('admin', _hash_password('admin123'), 'admin'))
    cursor.execute('INSERT OR IGNORE INTO webui_users (username, password, display_name, role) VALUES (?, ?, ?, ?)',
                   ('admin', _hash_password('admin'), 'Admin User', 'admin'))
    
    # Metadata seed
    for m in [('Gateway Name', 'string', 'System'), ('Uptime', 'int', 'Performance'), ('CPU Load', 'float', 'Hardware')]:
        cursor.execute('INSERT OR IGNORE INTO metadata (name, datatype, component) VALUES (?, ?, ?)', m)
    cursor.execute('INSERT OR IGNORE INTO webui_users (username, password, display_name, role) VALUES (?, ?, ?, ?)',
                   ('user', _hash_password('user123'), 'Regular User', 'user'))

    for cfg_type, svc_name, cfg_name, desc in [
        ('modbus', 'modbus_service', 'modbus_config', 'Modbus pipeline service name'),
        ('loadcell', 'load_cell_service', 'loadcell_config', 'Load-cell pipeline service name'),
        ('iot_gateway', 'iot-gateway', 'gateway_config', 'IoT gateway pipeline service name'),
        ('core', 'ilx_craneiq_core', 'core_config', 'Core config pipeline service name'),
    ]:
        cursor.execute('INSERT OR IGNORE INTO pipeline_service_targets (config_type, service_name, config_name, description, enabled) VALUES (?, ?, ?, ?, 1)',
                       (cfg_type, svc_name, cfg_name, desc))

    for cfg_type in ('modbus', 'loadcell', 'iot_gateway', 'core'):
        cursor.execute('INSERT OR IGNORE INTO pipeline_send_log (config_type, last_version, last_status) VALUES (?, 0, "never")', (cfg_type,))

    for device_type, port_number, label, port_value in [
        ('loadcell', 1, 'Channel 1', '/sys/bus/iio/devices/iio:device0/in_voltage0_raw'),
        ('loadcell', 2, 'Channel 2', '/sys/bus/iio/devices/iio:device1/in_voltage0_raw'),
    ]:
        cursor.execute('INSERT OR IGNORE INTO port_config (device_type, port_number, label, port_value) VALUES (?, ?, ?, ?)',
                       (device_type, port_number, label, port_value))

    # Default modals
    cursor.execute("INSERT OR IGNORE INTO modal (intname, modal_text) VALUES (?, ?)",
                  ('network-load', 'Switching network mode, please wait...'))


# ============================================================================
# ALL HELPER FUNCTIONS - Using get_cursor() with retry logic
# ============================================================================

def verify_admin_user(username, password):
    """Return user dict if credentials are valid, else None."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT id, username, role FROM admin_users WHERE username=? AND password=? AND enabled=1',
                          (username, _hash_password(password)))
            row = cursor.fetchone()
            if row:
                cursor.execute('UPDATE admin_users SET last_login=CURRENT_TIMESTAMP WHERE id=?', (row[0],))
            return {'id': row[0], 'username': row[1], 'role': row[2]} if row else None
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("[DB] verify_admin_user error: {}".format(e))
        return None


def verify_webui_user(username, password):
    """Return user dict if credentials are valid, else None."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT id, username, display_name, role FROM webui_users WHERE username=? AND password=? AND enabled=1',
                          (username, _hash_password(password)))
            row = cursor.fetchone()
            if row:
                cursor.execute('UPDATE webui_users SET last_login=CURRENT_TIMESTAMP WHERE id=?', (row[0],))
            return {'id': row[0], 'username': row[1], 'display_name': row[2], 'role': row[3]} if row else None
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("[DB] verify_webui_user error: {}".format(e))
        return None


def get_pipeline_service_name(config_type):
    """Return the configured pipeline service name for a config type."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT service_name FROM pipeline_service_targets WHERE config_type=?', (config_type,))
            row = cursor.fetchone()
            return row[0] if row else ''
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("[DB] get_pipeline_service_name error: {}".format(e))
        return ''


def set_pipeline_service_name(config_type, service_name, config_name=None):
    """Update the pipeline service name."""
    def _update():
        with get_cursor() as cursor:
            if config_name is not None:
                cursor.execute('UPDATE pipeline_service_targets SET service_name=?, config_name=?, updated_at=CURRENT_TIMESTAMP WHERE config_type=?',
                              (service_name, config_name, config_type))
            else:
                cursor.execute('UPDATE pipeline_service_targets SET service_name=?, updated_at=CURRENT_TIMESTAMP WHERE config_type=?',
                              (service_name, config_type))
        return True
    
    try:
        return execute_with_retry(_update)
    except Exception as e:
        logger.error("[DB] set_pipeline_service_name error: {}".format(e))
        return False


def get_pipeline_config_name(config_type):
    """Return the configured pipeline config name."""
    _defaults = {'loadcell': 'loadcell_config', 'iot_gateway': 'gateway_config', 'core': 'iq_core'}
    
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT config_name FROM pipeline_service_targets WHERE config_type=?', (config_type,))
            row = cursor.fetchone()
            val = row[0] if row else ''
            return val if val else _defaults.get(config_type, config_type + '_config')
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("[DB] get_pipeline_config_name error: {}".format(e))
        return _defaults.get(config_type, config_type + '_config')


def get_all_pipeline_service_targets():
    """Return all pipeline service target rows."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT config_type, service_name, config_name, enabled, description, updated_at FROM pipeline_service_targets ORDER BY config_type')
            rows = cursor.fetchall()
            return [{'config_type': r[0], 'service_name': r[1], 'config_name': r[2] if r[2] else (r[0] + '_config'),
                    'enabled': bool(r[3]), 'description': r[4], 'updated_at': r[5]} for r in rows]
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("[DB] get_all_pipeline_service_targets error: {}".format(e))
        return []


def get_pipeline_send_log(config_type):
    """Return the send-log row for a config_type."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT last_version, last_sent_at, last_service, last_status, last_message FROM pipeline_send_log WHERE config_type=?', (config_type,))
            row = cursor.fetchone()
            if row:
                return {'config_type': config_type, 'last_version': row[0], 'last_sent_at': row[1],
                       'last_service': row[2], 'last_status': row[3], 'last_message': row[4]}
            return {'config_type': config_type, 'last_version': 0, 'last_sent_at': None,
                   'last_service': '', 'last_status': 'never', 'last_message': ''}
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("[DB] get_pipeline_send_log error: {}".format(e))
        return {'config_type': config_type, 'last_version': 0}


def get_next_pipeline_version(config_type):
    """Read last_version from DB and return last_version + 1."""
    row = get_pipeline_send_log(config_type)
    return (row.get('last_version') or 0) + 1


def record_pipeline_send_success(config_type, version, service_name, message=''):
    """Called ONLY when pipeline send succeeds."""
    def _update():
        with get_cursor() as cursor:
            cursor.execute("""UPDATE pipeline_send_log SET last_version=?, last_sent_at=CURRENT_TIMESTAMP,
                           last_service=?, last_status='success', last_message=? WHERE config_type=?""",
                          (version, service_name, message, config_type))
        return True
    
    try:
        return execute_with_retry(_update)
    except Exception as e:
        logger.error("[DB] record_pipeline_send_success error: {}".format(e))
        return False


def record_pipeline_send_failure(config_type, message=''):
    """Record a failed send attempt."""
    def _update():
        with get_cursor() as cursor:
            cursor.execute("""UPDATE pipeline_send_log SET last_sent_at=CURRENT_TIMESTAMP,
                           last_status='failed', last_message=? WHERE config_type=?""", (message, config_type))
        return True
    
    try:
        return execute_with_retry(_update)
    except Exception as e:
        logger.error("[DB] record_pipeline_send_failure error: {}".format(e))
        return False


def get_all_pipeline_send_logs():
    """Return all send log rows."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT config_type, last_version, last_sent_at, last_service, last_status, last_message FROM pipeline_send_log ORDER BY config_type')
            rows = cursor.fetchall()
            return [{'config_type': r[0], 'last_version': r[1], 'last_sent_at': r[2],
                    'last_service': r[3], 'last_status': r[4], 'last_message': r[5]} for r in rows]
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("[DB] get_all_pipeline_send_logs error: {}".format(e))
        return []


def get_enabled_pipeline_targets():
    """Return only enabled service targets."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT config_type, service_name FROM pipeline_service_targets WHERE enabled=1 ORDER BY config_type')
            rows = cursor.fetchall()
            return [{'config_type': r[0], 'service_name': r[1]} for r in rows]
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("[DB] get_enabled_pipeline_targets error: {}".format(e))
        return []


def get_general_configuration():
    """Get general configuration settings."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('''
                SELECT gateway_name, serial_number, deployment_site, location_mode,
                       latitude, longitude, asset_id, mac_address,
                       timezone, ntp_server, date_format, time_format, language,
                       heartbeat_interval, offline_threshold,
                       COALESCE(network_mode, 'wifi') AS network_mode,
                       COALESCE(eth_selected, 'eth0') AS eth_selected,
                       COALESCE(wifi_ssid, '') AS wifi_ssid,
                       COALESCE(wifi_password, '') AS wifi_password,
                       COALESCE(eth_ip_assignment, 'dhcp') AS eth_ip_assignment,
                       COALESCE(eth_static_ip, '') AS eth_static_ip,
                       COALESCE(eth_subnet_mask, '') AS eth_subnet_mask,
                       COALESCE(eth_gateway, '') AS eth_gateway,
                       COALESCE(eth_dns1, '') AS eth_dns1,
                       COALESCE(eth_dns2, '') AS eth_dns2,
                       COALESCE(cell_apn, 'internet') AS cell_apn,
                       COALESCE(cell_username, '') AS cell_username,
                       COALESCE(cell_password, '') AS cell_password,
                       COALESCE(auto_connect, 0) AS auto_connect
                FROM general_configuration WHERE id = 1
            ''')
            row = cursor.fetchone()
            if not row:
                return {}
            return {
                'gateway_identity': {
                    'name': row[0], 'serial_number': row[1],
                    'deployment_site': row[2], 'location_mode': row[3],
                    'latitude': row[4], 'longitude': row[5],
                    'asset_id': row[6],
                },
                'date_time': {
                    'timezone': row[8], 'ntp_server': row[9],
                    'date_format': row[10], 'time_format': row[11], 'language': row[12],
                },
                'heartbeat': {'interval': row[13], 'offline_threshold': row[14]},
                'mac_address': row[7],
                'network': {
                    'mode':             row[15],
                    'eth_selected':     row[16],  # 'eth0' or 'eth1' -- persisted selection
                    'auto_connect':     bool(row[28]),  # Auto-connect toggle persisted state
                    'wifi': {'ssid': row[17], 'password': row[18]},
                    'ethernet': {
                        'ip_assignment': row[19], 'static_ip': row[20],
                        'subnet_mask': row[21], 'gateway': row[22],
                        'dns1': row[23], 'dns2': row[24],
                    },
                    'cellular': {'apn': row[25], 'username': row[26], 'password': row[27]},
                },
            }
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("Error getting general config: {}".format(e))
        return {}


def update_general_configuration(config_data):
    """Update general configuration settings."""
    def _update():
        with get_cursor() as cursor:
            sets, values = [], []
            def _add(col, val): sets.append('{} = ?'.format(col)); values.append(val)
            
            gi = config_data.get('gateway_identity', {})
            if 'name' in gi: _add('gateway_name', gi['name'])
            if 'serial_number' in gi: _add('serial_number', gi['serial_number'])
            if 'deployment_site' in gi: _add('deployment_site', gi['deployment_site'])
            if 'location_mode' in gi: _add('location_mode', gi['location_mode'])
            if 'latitude' in gi: _add('latitude', gi['latitude'])
            if 'longitude' in gi: _add('longitude', gi['longitude'])
            if 'asset_id' in gi: _add('asset_id', gi['asset_id'])
            
            dt = config_data.get('date_time', {})
            if 'timezone' in dt: _add('timezone', dt['timezone'])
            if 'ntp_server' in dt: _add('ntp_server', dt['ntp_server'])
            if 'date_format' in dt: _add('date_format', dt['date_format'])
            if 'time_format' in dt: _add('time_format', dt['time_format'])
            if 'language' in dt: _add('language', dt['language'])
            
            hb = config_data.get('heartbeat', {})
            if 'interval' in hb: _add('heartbeat_interval', hb['interval'])
            if 'offline_threshold' in hb: _add('offline_threshold', hb['offline_threshold'])
            
            if 'mac_address' in config_data: _add('mac_address', config_data['mac_address'])
            
            net = config_data.get('network', {})
            if 'mode' in net: _add('network_mode', net['mode'])
            if 'eth_selected' in net: _add('eth_selected', net['eth_selected'])
            if 'auto_connect' in net: _add('auto_connect', 1 if net['auto_connect'] else 0)
            
            wifi = net.get('wifi', {})
            if 'ssid' in wifi: _add('wifi_ssid', wifi['ssid'])
            if 'password' in wifi: _add('wifi_password', wifi['password'])
            
            eth = net.get('ethernet', {})
            if 'ip_assignment' in eth: _add('eth_ip_assignment', eth['ip_assignment'])
            if 'static_ip' in eth: _add('eth_static_ip', eth['static_ip'])
            if 'subnet_mask' in eth: _add('eth_subnet_mask', eth['subnet_mask'])
            if 'gateway' in eth: _add('eth_gateway', eth['gateway'])
            if 'dns1' in eth: _add('eth_dns1', eth['dns1'])
            if 'dns2' in eth: _add('eth_dns2', eth['dns2'])
            
            cell = net.get('cellular', {})
            if 'apn' in cell: _add('cell_apn', cell['apn'])
            if 'username' in cell: _add('cell_username', cell['username'])
            if 'password' in cell: _add('cell_password', cell['password'])
            
            if sets:
                cursor.execute('UPDATE general_configuration SET {}, updated_at = CURRENT_TIMESTAMP WHERE id = 1'.format(', '.join(sets)), values)
        return True
    
    try:
        return execute_with_retry(_update)
    except Exception as e:
        logger.error("Error updating general config: {}".format(e))
        return False


def get_all_tag_groups():
    """Get all tag groups."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT id, name, color, description, created_at FROM tag_groups ORDER BY name')
            rows = cursor.fetchall()
            return [{'id': r[0], 'name': r[1], 'color': r[2], 'description': r[3], 'created_at': r[4]} for r in rows]
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("Error getting device groups: {}".format(e))
        return []


def add_tag_group(name, color='blue', description=''):
    """Add a new tag group."""
    def _insert():
        with get_cursor() as cursor:
            cursor.execute('INSERT INTO tag_groups (name, color, description) VALUES (?, ?, ?)', (name, color, description))
            return cursor.lastrowid
    
    try:
        return execute_with_retry(_insert)
    except Exception as e:
        logger.error("Error adding device group: {}".format(e))
        return None


def delete_tag_group(group_id):
    """Delete a tag group."""
    def _delete():
        with get_cursor() as cursor:
            cursor.execute('UPDATE loadcell_datapoints SET group_id = NULL WHERE group_id = ?', (group_id,))
            cursor.execute('DELETE FROM tag_groups WHERE id = ?', (group_id,))
        return True
    
    try:
        return execute_with_retry(_delete)
    except Exception as e:
        logger.error("Error deleting device group: {}".format(e))
        return False


def get_all_services():
    """Get all services."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT id, name, description, enabled FROM services ORDER BY name')
            rows = cursor.fetchall()
            return [{'id': r[0], 'name': r[1], 'description': r[2], 'enabled': r[3]} for r in rows]
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("Error getting services: {}".format(e))
        return []


def get_service_by_name(name):
    """Get service ID by name."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT id FROM services WHERE name = ?', (name,))
            row = cursor.fetchone()
            return row[0] if row else None
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("Error getting service by name: {}".format(e))
        return None


def get_database_stats():
    """Get database statistics."""
    def _query():
        with get_cursor() as cursor:
            stats = {}
            for label, table in [('loadcell_devices', 'loadcell_device'), ('external_devices', 'external_device'),
                                ('loadcell_datapoints', 'loadcell_datapoints'), ('external_datapoints', 'external_datapoints'),
                                ('groups', 'tag_groups'), ('admin_users', 'admin_users'), ('webui_users', 'webui_users')]:
                cursor.execute('SELECT COUNT(*) FROM {}'.format(table))
                stats[label] = cursor.fetchone()[0]
            stats['total_devices'] = stats['loadcell_devices'] + stats.get('external_devices', 0)
            stats['total_datapoints'] = stats['loadcell_datapoints'] + stats.get('external_datapoints', 0)
            return stats
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("Error getting stats: {}".format(e))
        return {}


def get_all_admin_users():
    """Get all admin users."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT id, username, role, enabled, last_login, created_at FROM admin_users ORDER BY username')
            rows = cursor.fetchall()
            return [{'id': r[0], 'username': r[1], 'role': r[2], 'enabled': r[3],
                    'last_login': r[4], 'created_at': r[5]} for r in rows]
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("Error getting admin users: {}".format(e))
        return []


def create_admin_user(username, password, role='operator'):
    """Create a new admin user."""
    def _insert():
        with get_cursor() as cursor:
            cursor.execute('INSERT INTO admin_users (username, password, role) VALUES (?, ?, ?)',
                          (username, _hash_password(password), role))
            return cursor.lastrowid
    
    try:
        return execute_with_retry(_insert)
    except Exception as e:
        logger.error("Error creating admin user: {}".format(e))
        return None


def update_admin_user(user_id, data):
    """Update an admin user."""
    def _update():
        with get_cursor() as cursor:
            sets, values = [], []
            if 'username' in data: sets.append('username=?'); values.append(data['username'])
            if 'password' in data: sets.append('password=?'); values.append(_hash_password(data['password']))
            if 'role' in data: sets.append('role=?'); values.append(data['role'])
            if 'enabled' in data: sets.append('enabled=?'); values.append(1 if data['enabled'] else 0)
            if sets:
                values.append(user_id)
                cursor.execute('UPDATE admin_users SET {}, updated_at=CURRENT_TIMESTAMP WHERE id=?'.format(', '.join(sets)), values)
        return True
    
    try:
        return execute_with_retry(_update)
    except Exception as e:
        logger.error("Error updating admin user: {}".format(e))
        return False


def delete_admin_user(user_id):
    """Delete an admin user."""
    def _delete():
        with get_cursor() as cursor:
            cursor.execute('DELETE FROM admin_users WHERE id=?', (user_id,))
        return True
    
    try:
        return execute_with_retry(_delete)
    except Exception as e:
        logger.error("Error deleting admin user: {}".format(e))
        return False


def get_webui_user_max_sessions(user_id):
    """Return the max_sessions limit for a webui user."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT max_sessions FROM webui_users WHERE id=?', (user_id,))
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else 1
    
    try:
        return execute_with_retry(_query)
    except Exception:
        return 1


def set_webui_user_max_sessions(user_id, max_sessions):
    """Set the max concurrent session limit for a webui user."""
    def _update():
        with get_cursor() as cursor:
            cursor.execute('UPDATE webui_users SET max_sessions=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                          (int(max_sessions), user_id))
        return True
    
    try:
        return execute_with_retry(_update)
    except Exception:
        return False


def get_all_webui_users():
    """Get all webui users."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT id, username, display_name, role, enabled, last_login, created_at FROM webui_users ORDER BY username')
            rows = cursor.fetchall()
            return [{'id': r[0], 'username': r[1], 'display_name': r[2], 'role': r[3], 'enabled': r[4],
                    'last_login': r[5], 'created_at': r[6]} for r in rows]
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("Error getting webui users: {}".format(e))
        return []


def create_webui_user(username, password, display_name='', role='user'):
    """Create a new webui user."""
    def _insert():
        with get_cursor() as cursor:
            cursor.execute('INSERT INTO webui_users (username, password, display_name, role) VALUES (?, ?, ?, ?)',
                          (username, _hash_password(password), display_name, role))
            return cursor.lastrowid
    
    try:
        return execute_with_retry(_insert)
    except Exception as e:
        logger.error("Error creating webui user: {}".format(e))
        return None


def update_webui_user(user_id, data):
    """Update a webui user."""
    def _update():
        with get_cursor() as cursor:
            sets, values = [], []
            if 'username' in data: sets.append('username=?'); values.append(data['username'])
            if 'password' in data: sets.append('password=?'); values.append(_hash_password(data['password']))
            if 'display_name' in data: sets.append('display_name=?'); values.append(data['display_name'])
            if 'role' in data: sets.append('role=?'); values.append(data['role'])
            if 'enabled' in data: sets.append('enabled=?'); values.append(1 if data['enabled'] else 0)
            if sets:
                values.append(user_id)
                cursor.execute('UPDATE webui_users SET {}, updated_at=CURRENT_TIMESTAMP WHERE id=?'.format(', '.join(sets)), values)
        return True
    
    try:
        return execute_with_retry(_update)
    except Exception as e:
        logger.error("Error updating webui user: {}".format(e))
        return False


def delete_webui_user(user_id):
    """Delete a webui user."""
    def _delete():
        with get_cursor() as cursor:
            cursor.execute('DELETE FROM webui_users WHERE id=?', (user_id,))
        return True
    
    try:
        return execute_with_retry(_delete)
    except Exception as e:
        logger.error("Error deleting webui user: {}".format(e))
        return False


def get_all_rules():
    """Get all rules."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT * FROM rules ORDER BY created_at DESC')
            rows = [dict(r) for r in cursor.fetchall()]
            for r in rows:
                try:
                    r['groups'] = json.loads(r.get('groups_json') or '{}')
                except Exception:
                    r['groups'] = {}
            return rows
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("get_all_rules error: {}".format(e))
        return []


def save_rule(rule):
    """Save a rule."""
    def _save():
        with get_cursor() as cursor:
            rule_id = rule['id']
            name = rule.get('name', '')
            rule_type = rule.get('ruleType', rule.get('rule_type', 'group'))
            priority = rule.get('priority', 'medium')
            description = rule.get('description', '')
            enabled = 1 if rule.get('enabled', True) else 0
            groups_json = json.dumps(rule.get('groups', {}))
            relay_dp = rule.get('relayDatapoint', rule.get('relay_datapoint', ''))
            
            cursor.execute('SELECT id FROM rules WHERE id=?', (rule_id,))
            if cursor.fetchone():
                cursor.execute('''UPDATE rules SET name=?, rule_type=?, priority=?, description=?,
                               enabled=?, groups_json=?, relay_datapoint=?, updated_at=CURRENT_TIMESTAMP
                               WHERE id=?''', (name, rule_type, priority, description, enabled, groups_json, relay_dp, rule_id))
            else:
                cursor.execute('''INSERT INTO rules (id, name, rule_type, priority, description, enabled,
                               groups_json, relay_datapoint, updated_at)
                               VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''',
                              (rule_id, name, rule_type, priority, description, enabled, groups_json, relay_dp))
        return True
    
    try:
        return execute_with_retry(_save)
    except Exception as e:
        logger.error("save_rule error: {}".format(e))
        return False




def get_modal_config(intname):
    """Get modal configuration by internal name."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT modal_text FROM modal WHERE intname = ?', (intname,))
            row = cursor.fetchone()
            if row:
                return {'modal_text': row[0]}
            return None
    try:
        return execute_with_retry(_query)
    except Exception:
        return None


def save_modal_config(intname, modal_text):
    """Save/Update modal configuration."""
    def _update():
        with get_cursor() as cursor:
            cursor.execute('''INSERT INTO modal (intname, modal_text, updated_at)
                           VALUES (?, ?, CURRENT_TIMESTAMP)
                           ON CONFLICT(intname) DO UPDATE SET 
                           modal_text=excluded.modal_text, 
                           updated_at=excluded.updated_at''', (intname, modal_text))
        return True
    try:
        return execute_with_retry(_update)
    except Exception:
        return False


def get_all_modal_configs():
    """Get all modal configurations."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT intname, modal_text FROM modal ORDER BY intname')
            rows = cursor.fetchall()
            return [{'intname': r[0], 'modal_text': r[1]} for r in rows]
    try:
        return execute_with_retry(_query)
    except Exception:
        return []


def delete_rule(rule_id):
    """Delete a rule."""
    def _delete():
        with get_cursor() as cursor:
            cursor.execute('DELETE FROM rules WHERE id=?', (rule_id,))
        return True
    
    try:
        return execute_with_retry(_delete)
    except Exception as e:
        logger.error("delete_rule error: {}".format(e))
        return False


def get_all_loadcell_tags():
    """Return all enabled loadcell tag names as a flat list."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT name FROM loadcell_datapoints WHERE enabled=1 ORDER BY name')
            return [row[0] for row in cursor.fetchall()]
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("get_all_loadcell_tags error: {}".format(e))
        return []


def get_all_available_tags():
    """Return all available tags from every source."""
    def _map_dtype(data_type):
        dt = (data_type or '').lower()
        if 'bool' in dt: return 'bool'
        if 'float' in dt: return 'float'
        if 'int' in dt: return 'int'
        return 'float'

    def _query():
        tags = []
        with get_cursor() as cursor:
            # External (Modbus) datapoints - include protocol from device
            try:
                cursor.execute("SELECT ed.name, COALESCE(ed.unit,''), ed.device_id, COALESCE(dev.name,''), COALESCE(dev.protocol,'modbus'), COALESCE(ed.data_type,'float32') FROM external_datapoints ed LEFT JOIN external_device dev ON dev.id = ed.device_id WHERE ed.enabled = 1 ORDER BY ed.name")
                # Map protocol to display name: ext-rtu -> modbus-rtu, ext-tcp -> modbus-tcp, external/modbus -> modbus
                tags += [{'name': r[0], 'unit': r[1], 'deviceId': r[2], 'device': r[3], 'source': r[4].replace('ext-', 'modbus-') if r[4] and r[4].startswith('ext-') else 'modbus', 'dtype': _map_dtype(r[5])} for r in cursor.fetchall()]
            except Exception as e:
                logger.error("get_all_available_tags [modbus] error: {}".format(e))
            
            # Loadcell datapoints
            try:
                cursor.execute("SELECT ld.name, COALESCE(ld.unit,''), ld.device_id, COALESCE(lc.name,''), 'loadcell' FROM loadcell_datapoints ld LEFT JOIN loadcell_device lc ON lc.id = ld.device_id ORDER BY ld.name")
                tags += [{'name': r[0], 'unit': r[1], 'deviceId': r[2], 'device': r[3], 'source': r[4], 'dtype': 'float'} for r in cursor.fetchall()]
            except Exception as e:
                logger.error("get_all_available_tags [loadcell] error: {}".format(e))
            
            # Virtual datapoints (optional)
            try:
                cursor.execute("SELECT vd.name, COALESCE(vd.unit,''), vd.device_id, COALESCE(vdev.name,''), 'virtual' FROM virtual_datapoints vd LEFT JOIN virtual_device vdev ON vdev.id = vd.device_id ORDER BY vd.name")
                tags += [{'name': r[0], 'unit': r[1], 'deviceId': r[2], 'device': r[3], 'source': r[4], 'dtype': 'float'} for r in cursor.fetchall()]
            except Exception:
                pass
        
        return tags
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("get_all_available_tags error: {}".format(e))
        return []


# ---------------------------------------------------------------------------
# WebUI Page Restrictions
# ---------------------------------------------------------------------------

WEBUI_PAGES = [
    ('general-configuration', 'General Configuration', 1),
    ('device-management', 'Device Management', 2),
    ('field-integration', 'Field Integration', 3),
    ('mqtt-cloud', 'MQTT / Cloud', 4),
    ('ota-gateway', 'OTA Gateway', 5),
    ('craneiq', 'CraneIQ', 6),
    ('data-retention', 'Data Retention', 7),
    ('logging', 'Logging', 8),
    ('diagnostics', 'Diagnostics', 9),
    ('security', 'Security', 10),
    ('license', 'License', 11),
    ('automation', 'Automation', 12),
    ('alerts', 'Alerts', 13),
    ('rules', 'Rules', 14),
    ('backup', 'Backup', 15),
    ('notification', 'Notification', 16),
]

ALL_PAGE_KEYS = [p[0] for p in WEBUI_PAGES]


def get_all_pages():
    """Return the master list of pages as dicts."""
    return [{'page_key': k, 'label': l, 'sort_order': o} for k, l, o in WEBUI_PAGES]


def get_user_page_restrictions(user_id):
    """Return list of page_key strings that are HIDDEN for this user."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT page_key FROM webui_user_page_restrictions WHERE user_id=?', (user_id,))
            return [r[0] for r in cursor.fetchall()]
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error('get_user_page_restrictions error: {}'.format(e))
        return []


def set_user_page_restriction(user_id, page_key, hidden):
    """Add or remove a page restriction for a user."""
    def _update():
        with get_cursor() as cursor:
            if hidden:
                cursor.execute('INSERT OR IGNORE INTO webui_user_page_restrictions (user_id, page_key) VALUES (?, ?)', (user_id, page_key))
            else:
                cursor.execute('DELETE FROM webui_user_page_restrictions WHERE user_id=? AND page_key=?', (user_id, page_key))
        return True
    
    try:
        return execute_with_retry(_update)
    except Exception as e:
        logger.error('set_user_page_restriction error: {}'.format(e))
        return False


def get_pages_for_user(user_id):
    """Return list of {page_key, label, visible} for all pages for this user."""
    hidden = set(get_user_page_restrictions(user_id))
    return [{'page_key': k, 'label': l, 'sort_order': o, 'visible': k not in hidden} for k, l, o in WEBUI_PAGES]


def get_port_config(device_type=None):
    """Return port_config rows."""
    def _query():
        with get_cursor() as cursor:
            if device_type:
                cursor.execute('SELECT id, device_type, port_number, label, port_value FROM port_config WHERE device_type=? ORDER BY port_number', (device_type,))
            else:
                cursor.execute('SELECT id, device_type, port_number, label, port_value FROM port_config ORDER BY device_type, port_number')
            rows = cursor.fetchall()
            return [{'id': r[0], 'device_type': r[1], 'port_number': r[2], 'label': r[3], 'port_value': r[4]} for r in rows]
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error('[DB] get_port_config error: {}'.format(e))
        return []


def get_port_label(device_type, port_value):
    """Return the UI label for a given actual port value."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('SELECT label FROM port_config WHERE device_type=? AND port_value=?', (device_type, port_value))
            row = cursor.fetchone()
            return row[0] if row else port_value
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error('[DB] get_port_label error: {}'.format(e))
        return port_value


# Register cleanup on exit
atexit.register(close_all_connections)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    logger.info("Initializing database...")
    init_database()
    logger.info("\n=== Database Statistics ===")
    for k, v in get_database_stats().items():
        logger.info("{}: {}".format(k, v))
