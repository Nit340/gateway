# -*- coding: utf-8 -*-
# database.py - Database initialization and operations (FIXED)
# Verification command: python -c "import sys; sys.path.append('flask'); import database; database.ensure_db_initialized(); import sqlite3; conn=sqlite3.connect(database.DB_FILE); c=conn.cursor(); c.execute('SELECT name FROM sqlite_master WHERE type=\x22table\x22'); print(c.fetchall())"
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
# CHANGED: Defaulting to /mnt/data/.db as requested
_DB_DIR = os.environ.get('GATEWAY_DB_DIR', '/mnt/data/.db')
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
def sync_device_slave_id_to_tags(device_id, new_slave_id):
    """Update all tags for a device to use the device's slave_id"""
    def _update():
        with get_cursor() as cursor:
            # Update all external datapoints for this device to use the device's slave_id
            cursor.execute('''
                UPDATE external_datapoints 
                SET slave_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE device_id = ?
            ''', (new_slave_id, device_id))
            affected = cursor.rowcount
            logger.info("[DB] Synced slave_id {} to {} tags for device {}".format(new_slave_id, affected, device_id))
            return affected
    
    try:
        return execute_with_retry(_update)
    except Exception as e:
        logger.error("[DB] Error syncing device slave_id to tags: {}".format(e))
        return 0

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


def _insert_factory_data_on_new_db(conn):
    """If database is newly created and factory_default.db exists, 
    insert factory data into the new database.
    
    Called AFTER the initial schema + defaults have been committed, so we
    start with a clean connection state (no open transaction).
    """
    try:
        factory_db_path = os.path.join(os.path.dirname(DB_FILE), 'factory_default.db')
        
        if not os.path.exists(factory_db_path):
            logger.debug("[DB] No factory_default.db found - using minimal defaults")
            return
        
        logger.info("[DB] New database detected. Importing data from factory_default.db...")
        
        # Attach the factory database
        conn.execute('ATTACH DATABASE ? AS factory', (factory_db_path,))
        
        cursor = conn.cursor()
        
        # Get all tables from the factory DB (source of truth for what to import)
        cursor.execute(
            "SELECT name FROM factory.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        factory_tables = [row[0] for row in cursor.fetchall()]

        # Also get all tables from the newly created main database
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        main_tables = set(row[0] for row in cursor.fetchall())

        # Always ensure general_configuration is included if present in factory DB
        tables_to_import = factory_tables
        if 'general_configuration' not in [t for t in factory_tables]:
            logger.warning("[DB] 'general_configuration' not found in factory_default.db - will use schema defaults")

        # Temporarily disable foreign key constraints during import
        conn.execute('PRAGMA foreign_keys = OFF')

        # Open a single explicit transaction for the entire import
        conn.execute('BEGIN')

        # For each table in factory DB, copy data into the main database
        successful_imports = 0
        for table in tables_to_import:
            try:
                # Skip if table doesn't exist in the main (new) DB schema
                if table not in main_tables:
                    logger.debug("[DB] Table '{}' exists in factory DB but not in main schema, skipping".format(table))
                    continue

                # Get columns present in the factory DB table
                cursor.execute('PRAGMA factory.table_info({})'.format(table))
                factory_cols = {r[1] for r in cursor.fetchall()}

                # Get columns present in the main DB table
                cursor.execute('PRAGMA main.table_info({})'.format(table))
                main_cols = {r[1] for r in cursor.fetchall()}

                # Only copy columns that exist in BOTH schemas.
                # This handles the case where the factory DB was created from an older
                # schema (missing newer columns like eth_selected, auto_connect, etc.).
                # Missing columns will simply use their DEFAULT values from the main schema.
                shared_cols = [c for c in main_cols if c in factory_cols]
                if not shared_cols:
                    logger.warning("[DB] Table '{}' has no common columns, skipping".format(table))
                    continue

                cols_sql = ', '.join(shared_cols)

                # Clear any default data and insert factory data using only shared columns
                conn.execute('DELETE FROM main.{}'.format(table))
                conn.execute(
                    'INSERT INTO main.{0} ({1}) SELECT {1} FROM factory.{0}'.format(table, cols_sql)
                )
                logger.debug("[DB] Imported {} from factory DB ({} columns)".format(table, len(shared_cols)))
                successful_imports += 1
            except Exception as table_err:
                logger.warning("[DB] Could not import table '{}': {}".format(table, table_err))
        
        conn.commit()
        conn.execute('DETACH DATABASE factory')
        conn.execute('PRAGMA foreign_keys = ON')
        
        logger.info("[DB] Factory data import complete - {} tables imported".format(successful_imports))
        
    except Exception as e:
        logger.warning("[DB] Error importing factory data: {}".format(e))
        # Roll back any partial changes so the DB stays in a usable state
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.execute('DETACH DATABASE factory')
        except Exception:
            pass
        try:
            conn.execute('PRAGMA foreign_keys = ON')
        except Exception:
            pass


def init_database():
    """Initialize SQLite database with full schema"""
    _log_debug("Initializing database schema")
    
    # Check if this is a newly created database (file didn't exist before)
    is_new_db = not os.path.exists(DB_FILE)
    
    # Use a temporary connection for initialization
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys = ON')
    cursor = conn.cursor()
    
    create_tables(cursor)
    insert_default_data(cursor)

    # Commit schema + default data BEFORE factory import.
    # This closes the implicit transaction so _insert_factory_data_on_new_db
    # can open its own clean transaction with ATTACH DATABASE.
    conn.commit()

    # If database is newly created AND factory_default.db exists,
    # overwrite the just-committed default data with factory data.
    if is_new_db:
        _insert_factory_data_on_new_db(conn)
    
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
            auto_connect        INTEGER DEFAULT 1,
            load_raw_enabled    INTEGER DEFAULT 0,

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
    # Cloud integration (Structured)
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mqtt_connections (
            id              TEXT    PRIMARY KEY,
            name            TEXT    NOT NULL,
            enabled         INTEGER DEFAULT 1,
            protocol        TEXT    DEFAULT 'mqtts',
            host            TEXT    DEFAULT '',
            port            INTEGER DEFAULT 8883,
            client_id       TEXT    DEFAULT '',
            device_token    TEXT    DEFAULT '',
            username        TEXT    DEFAULT '',
            password        TEXT    DEFAULT '',
            keepalive_sec   INTEGER DEFAULT 60,
            qos             INTEGER DEFAULT 1,
            base_topic      TEXT    DEFAULT 'gateway/data',
            tls             INTEGER DEFAULT 1,
            json_template   TEXT    DEFAULT '{"timestamp":"%TIMESTAMP%","device":"%DEVICE_ID%","data":%DATA%}',
            channels_json   TEXT    DEFAULT '[]',
            mappings_json   TEXT    DEFAULT '[]',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS http_connections (
            id              TEXT    PRIMARY KEY,
            name            TEXT    NOT NULL,
            enabled         INTEGER DEFAULT 1,
            url             TEXT    DEFAULT '',
            method          TEXT    DEFAULT 'POST',
            auth_token      TEXT    DEFAULT '',
            headers_json    TEXT    DEFAULT '{}',
            timeout_sec     INTEGER DEFAULT 30,
            channels_json   TEXT    DEFAULT '[]',
            mappings_json   TEXT    DEFAULT '[]',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cloud_connection_stats (
            connection_id   TEXT    PRIMARY KEY,
            messages_total  INTEGER DEFAULT 0,
            messages_ok     INTEGER DEFAULT 0,
            messages_failed INTEGER DEFAULT 0,
            latency_avg_ms  REAL    DEFAULT 0.0,
            last_active     TEXT    DEFAULT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mqtt_datapoints (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_id    TEXT    NOT NULL,
            tag              TEXT    NOT NULL,
            topic            TEXT    NOT NULL,
            publish_mode     TEXT    DEFAULT 'on_change',
            change_threshold REAL    DEFAULT 0.0,
            enabled          INTEGER DEFAULT 1,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (connection_id) REFERENCES mqtt_connections(id) ON DELETE CASCADE,
            UNIQUE(connection_id, tag)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS http_datapoints (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_id    TEXT    NOT NULL,
            tag              TEXT    NOT NULL,
            endpoint         TEXT    NOT NULL,
            publish_mode     TEXT    DEFAULT 'on_change',
            change_threshold REAL    DEFAULT 0.0,
            enabled          INTEGER DEFAULT 1,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (connection_id) REFERENCES http_connections(id) ON DELETE CASCADE,
            UNIQUE(connection_id, tag)
        )
    ''')

    # Alter table migrations for existing installations
    for tbl in ('mqtt_connections', 'http_connections'):
        for col in ('channels_json', 'mappings_json'):
            try:
                cursor.execute('ALTER TABLE {} ADD COLUMN {} TEXT DEFAULT "[]"'.format(tbl, col))
            except Exception:
                pass


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
            id                       INTEGER PRIMARY KEY AUTOINCREMENT,
            username                 TEXT    NOT NULL UNIQUE,
            password                 TEXT    NOT NULL,
            display_name             TEXT    DEFAULT '',
            role                     TEXT    NOT NULL DEFAULT 'user' CHECK(role IN ('admin', 'user')),
            enabled                  BOOLEAN DEFAULT 1,
            max_sessions             INTEGER DEFAULT 2,
            session_timeout_minutes  INTEGER DEFAULT 0,
            session_debounce_seconds INTEGER DEFAULT 0,
            last_login               TIMESTAMP,
            created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            send_order   INTEGER DEFAULT 0,
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
    # Core Configs
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS core_configs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            version      INTEGER NOT NULL DEFAULT 1,
            device_names TEXT,
            service_name TEXT,
            config_json  TEXT NOT NULL,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
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
        CREATE TABLE IF NOT EXISTS session_global_settings (
            id                      INTEGER PRIMARY KEY DEFAULT 1 CHECK(id = 1),
            idle_timeout_minutes    INTEGER NOT NULL DEFAULT 0,
            updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Migration: add max_session_hours to existing databases
    cursor.execute("PRAGMA table_info(session_global_settings)")
    if 'max_session_hours' not in {r[1] for r in cursor.fetchall()}:
        cursor.execute('ALTER TABLE session_global_settings ADD COLUMN max_session_hours INTEGER NOT NULL DEFAULT 0')
    # Seed a single row if not present
    cursor.execute('''
        INSERT OR IGNORE INTO session_global_settings (id, idle_timeout_minutes, max_session_hours)
        VALUES (1, 0, 0)
    ''')

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
            device_type TEXT    NOT NULL CHECK(device_type IN ('loadcell', 'external')),
            port_number INTEGER NOT NULL,
            label       TEXT    NOT NULL,
            port_value  TEXT    NOT NULL,
            
            -- External Modbus RTU settings (only used if device_type='external')
            baud_rate           INTEGER DEFAULT 9600,
            data_bits           INTEGER DEFAULT 8,
            parity              TEXT    DEFAULT 'N',
            stop_bits           INTEGER DEFAULT 1,
            response_timeout_ms INTEGER DEFAULT 100,
            byte_timeout_ms     INTEGER DEFAULT 100,
            max_retries         INTEGER DEFAULT 2,
            polling_interval_ms INTEGER DEFAULT 300,
            
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

    # -----------------------------------------------------------------------
    # Network Monitor
    # -----------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS network_monitor_settings (
            id               INTEGER PRIMARY KEY DEFAULT 1 CHECK(id = 1),
            enabled          INTEGER DEFAULT 0,
            interval_ms      INTEGER DEFAULT 1800000,
            log_level        TEXT    DEFAULT 'INFO',
            max_rows         INTEGER DEFAULT 10000,
            retention_days   INTEGER DEFAULT 14,
            max_file_size_mb INTEGER DEFAULT 10,
            buffer_size_kb   INTEGER DEFAULT 64,
            log_format       TEXT    DEFAULT 'TEXT',
            flush_interval_ms INTEGER DEFAULT 250,
            updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute("DROP TABLE IF EXISTS logging_settings")
    cursor.execute("DROP TABLE IF EXISTS log_category_settings")



    # Ensure initial rows exist so UPDATE statements work
    cursor.execute("INSERT OR IGNORE INTO network_monitor_settings (id) VALUES (1)")


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
    if 'send_order' not in cols:
        # Add send_order column and set default ordering: modbus=1, loadcell=2, iot_gateway=3, core=4
        cursor.execute("ALTER TABLE pipeline_service_targets ADD COLUMN send_order INTEGER DEFAULT 0")
        cursor.execute("UPDATE pipeline_service_targets SET send_order=1 WHERE config_type='modbus'")
        cursor.execute("UPDATE pipeline_service_targets SET send_order=2 WHERE config_type='loadcell'")
        cursor.execute("UPDATE pipeline_service_targets SET send_order=3 WHERE config_type='iot_gateway'")
        cursor.execute("UPDATE pipeline_service_targets SET send_order=4 WHERE config_type='core'")
        logger.info("[DB] Migration: added send_order column to pipeline_service_targets")

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
        cursor.execute("ALTER TABLE general_configuration ADD COLUMN auto_connect INTEGER DEFAULT 1")
        # Only set default=1 when the column is brand new (no prior value exists)
        cursor.execute("UPDATE general_configuration SET auto_connect = 1 WHERE auto_connect IS NULL")
    
    # Add load_raw_enabled to general_configuration (persists the Raw toggle state)
    if 'load_raw_enabled' not in gc_cols:
        cursor.execute("ALTER TABLE general_configuration ADD COLUMN load_raw_enabled INTEGER DEFAULT 0")

    # Add last_route_select to general_configuration (persists manual route selection)
    if 'last_route_select' not in gc_cols:
        cursor.execute("ALTER TABLE general_configuration ADD COLUMN last_route_select INTEGER DEFAULT 0")

    # Add columns to network_monitor_settings
    cursor.execute("PRAGMA table_info(network_monitor_settings)")
    nms_cols = {r[1] for r in cursor.fetchall()}
    _nms_schema = [
        ('interval_ms', 'INTEGER DEFAULT 1800000'),
        ('max_rows', 'INTEGER DEFAULT 10000'),
        ('retention_days', 'INTEGER DEFAULT 14'),
        ('max_file_size_mb', 'INTEGER DEFAULT 10'),
        ('buffer_size_kb', 'INTEGER DEFAULT 64'),
        ('log_format', "TEXT DEFAULT 'TEXT'"),
        ('flush_interval_ms', 'INTEGER DEFAULT 250')
    ]
    for col_name, col_def in _nms_schema:
        if col_name not in nms_cols:
            cursor.execute('ALTER TABLE network_monitor_settings ADD COLUMN {} {}'.format(col_name, col_def))


    # Migration: create session_global_settings if it doesn't exist yet
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_global_settings (
            id                      INTEGER PRIMARY KEY DEFAULT 1 CHECK(id = 1),
            idle_timeout_minutes    INTEGER NOT NULL DEFAULT 0,
            updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Migration: add max_session_hours to existing databases (must run before INSERT)
    cursor.execute("PRAGMA table_info(session_global_settings)")
    if 'max_session_hours' not in {r[1] for r in cursor.fetchall()}:
        cursor.execute('ALTER TABLE session_global_settings ADD COLUMN max_session_hours INTEGER NOT NULL DEFAULT 0')
    cursor.execute('INSERT OR IGNORE INTO session_global_settings (id, idle_timeout_minutes, max_session_hours) VALUES (1, 0, 0)')

    # Migration: add session_timeout_minutes and session_debounce_seconds to webui_users
    cursor.execute("PRAGMA table_info(webui_users)")
    webui_cols = {r[1] for r in cursor.fetchall()}
    for _col, _defn in [
        ('session_timeout_minutes',  'INTEGER DEFAULT 0'),
        ('session_debounce_seconds', 'INTEGER DEFAULT 0'),
    ]:
        if _col not in webui_cols:
            try:
                cursor.execute('ALTER TABLE webui_users ADD COLUMN {} {}'.format(_col, _defn))
                logger.info('[DB] Migration: added {} to webui_users'.format(_col))
            except Exception as _e:
                logger.warning('[DB] Could not add {}: {}'.format(_col, _e))

    # Update port_config table for 'external' devices and new columns
    cursor.execute("PRAGMA table_info(port_config)")
    pc_cols = {r[1] for r in cursor.fetchall()}
    
    # 1. Add missing columns to port_config
    for col_name, col_def in [
        ('baud_rate',           'INTEGER DEFAULT 9600'),
        ('data_bits',           'INTEGER DEFAULT 8'),
        ('parity',              'TEXT    DEFAULT "N"'),
        ('stop_bits',           'INTEGER DEFAULT 1'),
        ('response_timeout_ms', 'INTEGER DEFAULT 100'),
        ('byte_timeout_ms',     'INTEGER DEFAULT 100'),
        ('max_retries',         'INTEGER DEFAULT 2'),
        ('polling_interval_ms', 'INTEGER DEFAULT 300')
    ]:
        if col_name not in pc_cols:
            try:
                cursor.execute('ALTER TABLE port_config ADD COLUMN {} {}'.format(col_name, col_def))
            except Exception:
                pass

    # 2. Rebuild port_config to update CHECK constraint if necessary
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='port_config'")
    _pc_row = cursor.fetchone()
    if _pc_row and "'external'" not in _pc_row[0] and 'external' not in _pc_row[0]:
        logger.info("[DB] Migration: rebuilding port_config to update CHECK constraint")
        cursor.execute("ALTER TABLE port_config RENAME TO _port_config_old")
        cursor.execute('''
            CREATE TABLE port_config (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                device_type TEXT    NOT NULL CHECK(device_type IN ('loadcell', 'external')),
                port_number INTEGER NOT NULL,
                label       TEXT    NOT NULL,
                port_value  TEXT    NOT NULL,
                baud_rate           INTEGER DEFAULT 9600,
                data_bits           INTEGER DEFAULT 8,
                parity              TEXT    DEFAULT 'N',
                stop_bits           INTEGER DEFAULT 1,
                response_timeout_ms INTEGER DEFAULT 100,
                byte_timeout_ms     INTEGER DEFAULT 100,
                max_retries         INTEGER DEFAULT 2,
                polling_interval_ms INTEGER DEFAULT 300,
                UNIQUE(device_type, port_number)
            )
        ''')
        cursor.execute('''
            INSERT INTO port_config (id, device_type, port_number, label, port_value, baud_rate, data_bits, parity, stop_bits, response_timeout_ms, byte_timeout_ms, max_retries, polling_interval_ms)
            SELECT id, device_type, port_number, label, port_value, baud_rate, data_bits, parity, stop_bits, response_timeout_ms, byte_timeout_ms, max_retries, polling_interval_ms
            FROM _port_config_old
        ''')
        cursor.execute("DROP TABLE _port_config_old")
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

    # Add device_token to mqtt_connections
    cursor.execute("PRAGMA table_info(mqtt_connections)")
    mqtt_cols = {r[1] for r in cursor.fetchall()}
    if 'device_token' not in mqtt_cols:
        cursor.execute("ALTER TABLE mqtt_connections ADD COLUMN device_token TEXT DEFAULT ''")
        logger.info("[DB] Migration: added device_token column to mqtt_connections")


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
    
    # Network Monitor defaults
    cursor.execute('SELECT COUNT(*) FROM network_monitor_settings')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO network_monitor_settings (id) VALUES (1)')
    
    # Metadata seed - All 36 parameters from Device Metadata Report (source: Univa-gateway)
    cursor.execute('DELETE FROM metadata')
    _metadata_params = [
        # Section 1: System Information
        ('device_hostname',         'string'),
        ('operating_system_version','string'),
        ('kernel_version',          'string'),
        ('system_architecture',     'string'),
        ('system_uptime',           'string'),
        ('current_date_timezone',   'string'),
        ('firmware_version',        'string'),
        # Section 2: CPU Information
        ('processor_model',         'string'),
        ('number_of_cpu_cores',     'int'),
        ('cpu_clock_frequency',     'float'),
        ('system_load_average',     'float'),
        # Section 3: Memory Information
        ('total_ram',               'float'),
        ('used_ram',                'float'),
        ('free_ram',                'float'),
        ('available_ram',           'float'),
        ('buffers_and_cache',       'float'),
        ('swap_memory',             'float'),
        # Section 4: Storage Information
        ('total_storage_capacity',  'float'),
        ('used_storage_space',      'float'),
        ('available_storage_space', 'float'),
        ('storage_usage_percentage','float'),
        ('mount_points',            'string'),
        ('flash_partition_layout',  'string'),
        # Section 5: CPU Usage
        ('total_cpu_usage',         'float'),
        # Section 6: Network Status - LAN
        ('ETH0_MAC_Address',        'string'),
        ('ETH1_MAC_Address',        'string'),
        ('ETH0_IP_Address',         'string'),
        ('ETH0_Connection_State',   'string'),
        ('ETH1_IP_Address',         'string'),
        ('ETH1_Connection_State',   'string'),
        # Section 7: Network Status - WLAN
        ('WiFi_MAC_Address',        'string'),
        ('Connected_Network_Name_SSID', 'string'),
        ('Access_Point_MAC_Address_BSSID', 'string'),
        ('WiFi_IP_Address',         'string'),
        ('WiFi_Frequency_MHz',      'float'),
        ('WiFi_Connection_State',   'string'),
        ('WiFi_Signal_Strength',   'string'),
        # Section 8: Network Status - LTE
        ('Device_IMEI',             'string'),
        ('SIM_Card_IMSI',           'string'),
        ('SIM_Card_ICCID',          'string'),
        ('Cellular_IP_Address',     'string'),
        ('Operator_Name',           'string'),
        ('Operator_ID',             'string'),
        ('Network_Technology_2G_3G_4G_5G','string'),
        ('Signal_Strength_Percentage', 'float'),
        ('Transmit_Power_Level',    'float'),
        ('Cellular_Connection_State','string'),
    ]
    for name, datatype in _metadata_params:
        cursor.execute(
            'INSERT OR IGNORE INTO metadata (name, datatype, source, component) VALUES (?, ?, ?, ?)',
            (name, datatype, 'Univa-gateway', None)
        )
    cursor.execute('INSERT OR IGNORE INTO webui_users (username, password, display_name, role) VALUES (?, ?, ?, ?)',
                   ('user', _hash_password('user123'), 'Regular User', 'user'))

    for cfg_type, svc_name, cfg_name, desc, order in [
        ('modbus',      'modbus_service',    'modbus_config',   'Modbus pipeline service name',       1),
        ('loadcell',    'load_cell_service', 'loadcell_config', 'Load-cell pipeline service name',     2),
        ('iot_gateway', 'iot-gateway',       'gateway_config',  'IoT gateway pipeline service name',  3),
        ('core',        'ilx_craneiq_core',  'core_config',     'Core config pipeline service name',  4),
    ]:
        cursor.execute(
            'INSERT OR IGNORE INTO pipeline_service_targets '
            '(config_type, service_name, config_name, description, enabled, send_order) VALUES (?, ?, ?, ?, 1, ?)',
            (cfg_type, svc_name, cfg_name, desc, order))

    for cfg_type in ('modbus', 'loadcell', 'iot_gateway', 'core'):
        cursor.execute('INSERT OR IGNORE INTO pipeline_send_log (config_type, last_version, last_status) VALUES (?, 0, "never")', (cfg_type,))

    # Network Monitor defaults
    cursor.execute('SELECT COUNT(*) FROM network_monitor_settings')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO network_monitor_settings (id) VALUES (1)')

    for device_type, port_number, label, port_value in [
        ('loadcell', 1, 'Channel 1', '/sys/bus/iio/devices/iio:device0/in_voltage0_raw'),
        ('loadcell', 2, 'Channel 2', '/sys/bus/iio/devices/iio:device1/in_voltage0_raw'),
        ('external', 1, 'Port 1',    '/dev/ttymxc5'),
        ('external', 2, 'Port 2',    '/dev/ttymxc2'),
    ]:
        # Check if exists
        cursor.execute('SELECT id FROM port_config WHERE device_type=? AND port_number=?', (device_type, port_number))
        row = cursor.fetchone()
        if not row:
            cursor.execute('''
                INSERT INTO port_config (device_type, port_number, label, port_value)
                VALUES (?, ?, ?, ?)
            ''', (device_type, port_number, label, port_value))
        else:
            # For loadcell, ensure serial fields are blank as requested
            if device_type == 'loadcell':
                cursor.execute('''
                    UPDATE port_config SET 
                        label=?, port_value=?, 
                        baud_rate=NULL, data_bits=NULL, parity=NULL, stop_bits=NULL,
                        response_timeout_ms=NULL, byte_timeout_ms=NULL, max_retries=NULL, polling_interval_ms=NULL
                    WHERE id=?
                ''', (label, port_value, row[0]))
            else:
                # For external, just ensure label and path are correct
                cursor.execute('UPDATE port_config SET label=?, port_value=? WHERE id=?', (label, port_value, row[0]))

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
            cursor.execute('SELECT config_type, service_name, config_name, enabled, description, updated_at, COALESCE(send_order, 0) FROM pipeline_service_targets ORDER BY COALESCE(send_order, 0) ASC, config_type ASC')
            rows = cursor.fetchall()
            return [{'config_type': r[0], 'service_name': r[1], 'config_name': r[2] if r[2] else (r[0] + '_config'),
                    'enabled': bool(r[3]), 'description': r[4], 'updated_at': r[5], 'send_order': r[6]} for r in rows]
    
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
                       COALESCE(auto_connect, 0) AS auto_connect,
                       COALESCE(last_route_select, 0) AS last_route_select
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
                    'last_route_select': row[29],
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
            if 'last_route_select' in net: _add('last_route_select', int(net['last_route_select']))
            
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


def get_session_global_settings():
    """Return the single global session settings row."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT idle_timeout_minutes, max_session_hours FROM session_global_settings WHERE id=1')
        row = cursor.fetchone()
        conn.close()
        return {
            'idle_timeout_minutes': row[0] if row else 0,
            'max_session_hours':    row[1] if row else 0,
        }
    except Exception:
        return {'idle_timeout_minutes': 0, 'max_session_hours': 0}


def set_session_global_settings(idle_timeout_minutes, max_session_hours=0):
    """Update the global session settings. 0 = disabled for both."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        idle = max(0, int(idle_timeout_minutes))
        maxh = max(0, int(max_session_hours))
        cursor.execute(
            'INSERT OR IGNORE INTO session_global_settings (id, idle_timeout_minutes, max_session_hours) VALUES (1, ?, ?)',
            (idle, maxh)
        )
        cursor.execute(
            'UPDATE session_global_settings SET idle_timeout_minutes=?, max_session_hours=?, updated_at=CURRENT_TIMESTAMP WHERE id=1',
            (idle, maxh)
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
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
            cursor.execute('''SELECT id, username, display_name, role, enabled, last_login, created_at,
                                     COALESCE(max_sessions, 2) as max_sessions,
                                     COALESCE(session_timeout_minutes, 0) as session_timeout_minutes,
                                     COALESCE(session_debounce_seconds, 0) as session_debounce_seconds
                              FROM webui_users ORDER BY username''')
            rows = cursor.fetchall()
            return [{'id': r[0], 'username': r[1], 'display_name': r[2], 'role': r[3], 'enabled': r[4],
                    'last_login': r[5], 'created_at': r[6], 'max_sessions': r[7],
                    'session_timeout_minutes': r[8], 'session_debounce_seconds': r[9]} for r in rows]
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("Error getting webui users: {}".format(e))
        return []


def create_webui_user(username, password, display_name='', role='user',
                       max_sessions=2, session_timeout_minutes=0, session_debounce_seconds=0):
    """Create a new webui user."""
    def _insert():
        with get_cursor() as cursor:
            cursor.execute(
                '''INSERT INTO webui_users
                   (username, password, display_name, role, max_sessions,
                    session_timeout_minutes, session_debounce_seconds)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (username, _hash_password(password), display_name, role,
                 int(max_sessions), int(session_timeout_minutes), int(session_debounce_seconds)))
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
            if 'max_sessions' in data: sets.append('max_sessions=?'); values.append(int(data['max_sessions']))
            if 'session_timeout_minutes' in data: sets.append('session_timeout_minutes=?'); values.append(int(data['session_timeout_minutes']))
            if 'session_debounce_seconds' in data: sets.append('session_debounce_seconds=?'); values.append(int(data['session_debounce_seconds']))
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
            cols = [
                'id', 'device_type', 'port_number', 'label', 'port_value',
                'baud_rate', 'data_bits', 'parity', 'stop_bits',
                'response_timeout_ms', 'byte_timeout_ms', 'max_retries', 'polling_interval_ms'
            ]
            col_str = ", ".join(cols)
            
            if device_type:
                # If modbus is requested, use external type
                q_type = 'external' if device_type == 'modbus' else device_type
                cursor.execute('SELECT {} FROM port_config WHERE device_type=? ORDER BY port_number'.format(col_str), (q_type,))
            else:
                cursor.execute('SELECT {} FROM port_config ORDER BY device_type, port_number'.format(col_str))
                
            rows = cursor.fetchall()
            return [dict(zip(cols, r)) for r in rows]
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error('[DB] get_port_config error: {}'.format(e))
        return []


def update_port_config(port_id, config_data):
    """Update a specific port configuration entry."""
    def _update():
        with get_cursor() as cursor:
            # We filter config_data to only include valid columns for update
            valid_cols = [
                'label', 'port_value', 'baud_rate', 'data_bits', 'parity', 'stop_bits',
                'response_timeout_ms', 'byte_timeout_ms', 'max_retries', 'polling_interval_ms'
            ]
            
            sets = []
            values = []
            for col in valid_cols:
                if col in config_data:
                    sets.append("{} = ?".format(col))
                    values.append(config_data[col])
            
            if not sets:
                return False
                
            values.append(port_id)
            query = "UPDATE port_config SET {} WHERE id = ?".format(", ".join(sets))
            cursor.execute(query, tuple(values))
            return cursor.rowcount > 0
            
    try:
        return execute_with_retry(_update)
    except Exception as e:
        logger.error('[DB] update_port_config error: {}'.format(e))
        return False




def get_network_settings():
    """Get network monitor settings."""
    def _query():
        with get_cursor() as cursor:
            cursor.execute('''
                SELECT enabled, interval_ms, log_level, max_rows, retention_days, 
                       max_file_size_mb, buffer_size_kb, log_format, flush_interval_ms 
                FROM network_monitor_settings WHERE id=1
            ''')
            row = cursor.fetchone()
            if row:
                return {
                    'enabled': bool(row[0]),
                    'interval_ms': row[1],
                    'log_level': row[2],
                    'max_rows': row[3],
                    'retention_days': row[4],
                    'max_file_size_mb': row[5],
                    'buffer_size_kb': row[6],
                    'log_format': row[7],
                    'flush_interval_ms': row[8]
                }
            return {
                'enabled': False,
                'interval_ms': 1800000,
                'log_level': 'INFO',
                'max_rows': 10000,
                'retention_days': 14,
                'max_file_size_mb': 10,
                'buffer_size_kb': 64,
                'log_format': 'TEXT'
            }
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error("[DB] get_network_settings error: {}".format(e))
        return {'enabled': False, 'interval_ms': 1800000}


def update_network_settings(data):
    """Update network monitor settings."""
    def _update():
        with get_cursor() as cursor:
            sets, vals = [], []
            if 'enabled' in data:
                sets.append("enabled = ?")
                vals.append(1 if data['enabled'] else 0)
            if 'interval_ms' in data:
                sets.append("interval_ms = ?")
                vals.append(int(data['interval_ms']))
            if 'log_level' in data:
                sets.append("log_level = ?")
                vals.append(data['log_level'])
            if 'max_rows' in data:
                sets.append("max_rows = ?")
                vals.append(int(data['max_rows']))
            if 'retention_days' in data:
                sets.append("retention_days = ?")
                vals.append(int(data['retention_days']))
            if 'max_file_size_mb' in data:
                sets.append("max_file_size_mb = ?")
                vals.append(int(data['max_file_size_mb']))
            if 'buffer_size_kb' in data:
                sets.append("buffer_size_kb = ?")
                vals.append(int(data['buffer_size_kb']))
            if 'log_format' in data:
                sets.append("log_format = ?")
                vals.append(data['log_format'])
            if 'flush_interval_ms' in data:
                sets.append("flush_interval_ms = ?")
                vals.append(int(data['flush_interval_ms']))
            
            if sets:
                vals.append(1) # id=1
                sql = "UPDATE network_monitor_settings SET {}, updated_at=CURRENT_TIMESTAMP WHERE id=?".format(", ".join(sets))
                cursor.execute(sql, vals)
        return True
    
    try:
        return execute_with_retry(_update)
    except Exception as e:
        logger.error("[DB] update_network_settings error: {}".format(e))
        return False




def get_port_value(device_type, label):
    """Return the actual port value (path) for a given UI label."""
    def _query():
        with get_cursor() as cursor:
            # Map 'modbus' request to 'external' type
            q_type = 'external' if device_type == 'modbus' else device_type
            cursor.execute('SELECT port_value FROM port_config WHERE device_type=? AND label=?', (q_type, label))
            row = cursor.fetchone()
            return row[0] if row else None
    
    try:
        return execute_with_retry(_query)
    except Exception as e:
        logger.error('[DB] get_port_value error: {}'.format(e))
        return None


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