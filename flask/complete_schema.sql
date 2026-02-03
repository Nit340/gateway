-- ============================================================================
-- CraneIQ Complete Database Schema
-- Version: 2.0
-- Description: Multi-Service Architecture for Industrial IoT Gateway
-- ============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ============================================================================
-- REFERENCE TABLES (ENUMERATIONS)
-- ============================================================================

-- Device Types
CREATE TABLE IF NOT EXISTS device_types (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    icon TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO device_types (name, description, icon) VALUES
    ('sensor', 'Sensor device for data acquisition', 'sensor'),
    ('actuator', 'Actuator device for control operations', 'toggle'),
    ('controller', 'Controller/PLC device', 'cpu'),
    ('gateway', 'Gateway or bridge device', 'router'),
    ('hmi', 'Human-Machine Interface', 'monitor'),
    ('io_module', 'Input/Output expansion module', 'grid'),
    ('drive', 'Motor drive or VFD', 'zap'),
    ('relay', 'Relay board or switching device', 'power'),
    ('load_cell', 'Load cell or weight sensor', 'weight'),
    ('other', 'Other device type', 'help-circle');

-- Datapoint Types
CREATE TABLE IF NOT EXISTS datapoint_types (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    size_bytes INTEGER,
    min_value TEXT,
    max_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO datapoint_types (name, description, size_bytes, min_value, max_value) VALUES
    ('boolean', 'Boolean true/false value', 1, '0', '1'),
    ('int8', '8-bit signed integer', 1, '-128', '127'),
    ('uint8', '8-bit unsigned integer', 1, '0', '255'),
    ('int16', '16-bit signed integer', 2, '-32768', '32767'),
    ('uint16', '16-bit unsigned integer', 2, '0', '65535'),
    ('int32', '32-bit signed integer', 4, '-2147483648', '2147483647'),
    ('uint32', '32-bit unsigned integer', 4, '0', '4294967295'),
    ('int64', '64-bit signed integer', 8, NULL, NULL),
    ('uint64', '64-bit unsigned integer', 8, NULL, NULL),
    ('float32', '32-bit floating point', 4, NULL, NULL),
    ('float64', '64-bit floating point', 8, NULL, NULL),
    ('string', 'Variable length string', NULL, NULL, NULL),
    ('blob', 'Binary data blob', NULL, NULL, NULL),
    ('timestamp', 'Unix timestamp', 4, NULL, NULL),
    ('json', 'JSON formatted data', NULL, NULL, NULL);

-- Datapoint Modes
CREATE TABLE IF NOT EXISTS datapoint_modes (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO datapoint_modes (name, description) VALUES
    ('dynamic', 'Value changes frequently and is polled/published'),
    ('fixed', 'Value is constant or rarely changes'),
    ('calculated', 'Value is derived from other datapoints'),
    ('event', 'Value is event-driven, not polled');

-- Datapoint Priority
CREATE TABLE IF NOT EXISTS datapoint_priority (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    update_rate_hint TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO datapoint_priority (name, description, update_rate_hint) VALUES
    ('critical', 'Critical safety or control datapoint', '< 50ms'),
    ('high', 'High priority data requiring fast updates', '< 200ms'),
    ('medium', 'Medium priority normal operation data', '< 1s'),
    ('default', 'Default priority for general data', '< 5s'),
    ('low', 'Low priority background data', '> 5s');

-- Datapoint Health Status
CREATE TABLE IF NOT EXISTS datapoint_health (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    severity INTEGER NOT NULL, -- 0=good, 1=uncertain, 2=bad
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO datapoint_health (name, description, severity) VALUES
    ('good', 'Value is valid and current', 0),
    ('uncertain', 'Value quality is questionable', 1),
    ('bad', 'Value is stale or invalid', 2),
    ('error', 'Error reading or writing value', 2),
    ('not_connected', 'Device not connected', 2),
    ('calibrating', 'Device is calibrating', 1),
    ('overrange', 'Value exceeds sensor range', 2),
    ('underrange', 'Value below sensor range', 2);

-- Interface Directions
CREATE TABLE IF NOT EXISTS interface_directions (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO interface_directions (name, description) VALUES
    ('input', 'Service consumes data from this interface'),
    ('output', 'Service produces data to this interface'),
    ('bidir', 'Bidirectional data flow');

-- Log Levels
CREATE TABLE IF NOT EXISTS log_levels (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    severity INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO log_levels (name, description, severity) VALUES
    ('trace', 'Detailed trace messages', 0),
    ('debug', 'Debug messages for development', 1),
    ('info', 'Informational messages', 2),
    ('warning', 'Warning messages', 3),
    ('error', 'Error messages', 4),
    ('critical', 'Critical system errors', 5),
    ('fatal', 'Fatal errors causing shutdown', 6);

-- Protocol Types
CREATE TABLE IF NOT EXISTS protocol_types (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    transport_layer TEXT,
    default_port INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO protocol_types (name, description, transport_layer, default_port) VALUES
    ('modbus-tcp', 'Modbus TCP/IP', 'TCP', 502),
    ('modbus-rtu', 'Modbus RTU Serial', 'Serial', NULL),
    ('modbus-ascii', 'Modbus ASCII Serial', 'Serial', NULL),
    ('opcua', 'OPC Unified Architecture', 'TCP', 4840),
    ('mqtt', 'Message Queue Telemetry Transport', 'TCP', 1883),
    ('http', 'HTTP REST API', 'TCP', 80),
    ('https', 'HTTPS Secure REST API', 'TCP', 443),
    ('websocket', 'WebSocket Protocol', 'TCP', NULL),
    ('bacnet', 'BACnet Protocol', 'UDP', 47808),
    ('profinet', 'PROFINET Industrial Ethernet', 'Ethernet', NULL),
    ('ethercat', 'EtherCAT Industrial Ethernet', 'Ethernet', NULL),
    ('canopen', 'CANopen Protocol', 'CAN', NULL),
    ('snmp', 'Simple Network Management Protocol', 'UDP', 161),
    ('iio', 'Industrial I/O (Linux kernel)', 'Kernel', NULL),
    ('gpio', 'General Purpose I/O', 'Kernel', NULL),
    ('spi', 'Serial Peripheral Interface', 'Hardware', NULL),
    ('i2c', 'Inter-Integrated Circuit', 'Hardware', NULL),
    ('uart', 'Universal Asynchronous Receiver-Transmitter', 'Serial', NULL),
    ('dbus', 'D-Bus IPC', 'IPC', NULL),
    ('custom', 'Custom protocol implementation', NULL, NULL);

-- Register Types (for Modbus and similar protocols)
CREATE TABLE IF NOT EXISTS register_types (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    modbus_function TEXT,
    read_only BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO register_types (name, description, modbus_function, read_only) VALUES
    ('coil', 'Modbus Coil (read/write bit)', '01/05/15', 0),
    ('discrete', 'Modbus Discrete Input (read-only bit)', '02', 1),
    ('holding', 'Modbus Holding Register (read/write word)', '03/06/16', 0),
    ('input', 'Modbus Input Register (read-only word)', '04', 1);

-- Byte/Word Order
CREATE TABLE IF NOT EXISTS byte_orders (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    example TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO byte_orders (name, description, example) VALUES
    ('big', 'Big Endian (Most Significant Byte first)', '0x1234 -> [0x12, 0x34]'),
    ('little', 'Little Endian (Least Significant Byte first)', '0x1234 -> [0x34, 0x12]'),
    ('big_swap', 'Big Endian with word swap', '0x12345678 -> [0x34, 0x12, 0x78, 0x56]'),
    ('little_swap', 'Little Endian with word swap', '0x12345678 -> [0x56, 0x78, 0x12, 0x34]');

-- Service Status
CREATE TABLE IF NOT EXISTS service_status (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    is_operational BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO service_status (name, description, is_operational) VALUES
    ('stopped', 'Service is stopped', 0),
    ('starting', 'Service is starting up', 0),
    ('running', 'Service is running normally', 1),
    ('stopping', 'Service is shutting down', 0),
    ('error', 'Service encountered an error', 0),
    ('degraded', 'Service running with reduced functionality', 1),
    ('maintenance', 'Service in maintenance mode', 0);

-- Device Status
CREATE TABLE IF NOT EXISTS device_status (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    is_online BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO device_status (name, description, is_online) VALUES
    ('unknown', 'Device status unknown', 0),
    ('online', 'Device is connected and responding', 1),
    ('offline', 'Device is not responding', 0),
    ('error', 'Device communication error', 0),
    ('timeout', 'Device response timeout', 0),
    ('disabled', 'Device is disabled', 0),
    ('initializing', 'Device is initializing', 0),
    ('fault', 'Device reported a fault', 0);

-- Network Interface Types
CREATE TABLE IF NOT EXISTS network_interface_types (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    layer INTEGER, -- OSI layer
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO network_interface_types (name, description, layer) VALUES
    ('ethernet', 'Ethernet wired connection', 2),
    ('wifi', 'WiFi wireless connection', 2),
    ('cellular', 'Cellular/LTE connection', 2),
    ('bluetooth', 'Bluetooth connection', 2),
    ('loopback', 'Loopback interface', 2),
    ('vpn', 'VPN tunnel interface', 3),
    ('bridge', 'Bridge interface', 2),
    ('vlan', 'VLAN interface', 2);

-- ============================================================================
-- CORE SYSTEM TABLES
-- ============================================================================

-- Services
CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT,
    description TEXT NOT NULL DEFAULT '',
    version TEXT,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    auto_start BOOLEAN NOT NULL DEFAULT 1,
    status TEXT DEFAULT 'stopped',
    pid INTEGER,
    restart_count INTEGER DEFAULT 0,
    last_restart TIMESTAMP,
    memory_usage_kb INTEGER,
    cpu_usage_percent REAL,
    uptime_seconds INTEGER,
    config_file_path TEXT,
    log_file_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(status) REFERENCES service_status(name)
);

CREATE INDEX IF NOT EXISTS idx_services_name ON services(name);
CREATE INDEX IF NOT EXISTS idx_services_enabled ON services(enabled);
CREATE INDEX IF NOT EXISTS idx_services_status ON services(status);

-- Devices
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT,
    type TEXT NOT NULL,
    service TEXT,
    protocol TEXT,
    address TEXT,
    port INTEGER,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    status TEXT DEFAULT 'unknown',
    last_seen TIMESTAMP,
    connection_quality INTEGER, -- 0-100
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    metadata_json TEXT, -- Additional device metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(type) REFERENCES device_types(name),
    FOREIGN KEY(service) REFERENCES services(name) ON DELETE SET NULL,
    FOREIGN KEY(protocol) REFERENCES protocol_types(name),
    FOREIGN KEY(status) REFERENCES device_status(name)
);

CREATE INDEX IF NOT EXISTS idx_devices_service ON devices(service);
CREATE INDEX IF NOT EXISTS idx_devices_type ON devices(type);
CREATE INDEX IF NOT EXISTS idx_devices_protocol ON devices(protocol);
CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
CREATE INDEX IF NOT EXISTS idx_devices_enabled ON devices(enabled);

-- Datapoints
CREATE TABLE IF NOT EXISTS datapoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT,
    type TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'dynamic',
    priority TEXT NOT NULL DEFAULT 'default',
    unit TEXT,
    description TEXT,
    min_value REAL,
    max_value REAL,
    default_value TEXT,
    precision INTEGER, -- Decimal places for display
    scaling_factor REAL DEFAULT 1.0,
    scaling_offset REAL DEFAULT 0.0,
    alarm_enabled BOOLEAN DEFAULT 0,
    alarm_high REAL,
    alarm_low REAL,
    deadband REAL, -- Minimum change to trigger update
    retention_days INTEGER DEFAULT 30, -- How long to keep history
    enabled BOOLEAN NOT NULL DEFAULT 1,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(type) REFERENCES datapoint_types(name),
    FOREIGN KEY(mode) REFERENCES datapoint_modes(name),
    FOREIGN KEY(priority) REFERENCES datapoint_priority(name)
);

CREATE INDEX IF NOT EXISTS idx_datapoints_name ON datapoints(name);
CREATE INDEX IF NOT EXISTS idx_datapoints_type ON datapoints(type);
CREATE INDEX IF NOT EXISTS idx_datapoints_mode ON datapoints(mode);
CREATE INDEX IF NOT EXISTS idx_datapoints_priority ON datapoints(priority);
CREATE INDEX IF NOT EXISTS idx_datapoints_enabled ON datapoints(enabled);

-- Service Interfaces (Pub/Sub connections between services and datapoints)
CREATE TABLE IF NOT EXISTS service_interfaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    name TEXT NOT NULL,
    direction TEXT NOT NULL,
    datapoint TEXT,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    publish_interval_ms INTEGER,
    last_publish TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(service) REFERENCES services(name) ON DELETE CASCADE,
    FOREIGN KEY(direction) REFERENCES interface_directions(name),
    FOREIGN KEY(datapoint) REFERENCES datapoints(name) ON DELETE SET NULL,
    UNIQUE(service, name)
);

CREATE INDEX IF NOT EXISTS idx_interfaces_service ON service_interfaces(service);
CREATE INDEX IF NOT EXISTS idx_interfaces_datapoint ON service_interfaces(datapoint);
CREATE INDEX IF NOT EXISTS idx_interfaces_direction ON service_interfaces(direction);

-- Datapoint Current Values (Latest value cache)
CREATE TABLE IF NOT EXISTS datapoint_values (
    datapoint TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    health TEXT NOT NULL DEFAULT 'good',
    service TEXT,
    timestamp_unix INTEGER NOT NULL,
    quality INTEGER DEFAULT 100, -- 0-100
    FOREIGN KEY(datapoint) REFERENCES datapoints(name) ON DELETE CASCADE,
    FOREIGN KEY(health) REFERENCES datapoint_health(name),
    FOREIGN KEY(service) REFERENCES services(name)
);

CREATE INDEX IF NOT EXISTS idx_dp_values_health ON datapoint_values(health);
CREATE INDEX IF NOT EXISTS idx_dp_values_timestamp ON datapoint_values(timestamp_unix);

-- Datapoint History (Time-series data)
CREATE TABLE IF NOT EXISTS datapoint_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datapoint TEXT NOT NULL,
    service TEXT NOT NULL,
    value TEXT NOT NULL,
    health TEXT NOT NULL DEFAULT 'good',
    quality INTEGER DEFAULT 100,
    timestamp_unix INTEGER NOT NULL,
    FOREIGN KEY(datapoint) REFERENCES datapoints(name) ON DELETE CASCADE,
    FOREIGN KEY(service) REFERENCES services(name) ON DELETE CASCADE,
    FOREIGN KEY(health) REFERENCES datapoint_health(name)
);

CREATE INDEX IF NOT EXISTS idx_history_datapoint ON datapoint_history(datapoint);
CREATE INDEX IF NOT EXISTS idx_history_timestamp ON datapoint_history(timestamp_unix);
CREATE INDEX IF NOT EXISTS idx_history_service ON datapoint_history(service);
CREATE INDEX IF NOT EXISTS idx_history_dp_time ON datapoint_history(datapoint, timestamp_unix);

-- Datapoint Alarms
CREATE TABLE IF NOT EXISTS datapoint_alarms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datapoint TEXT NOT NULL,
    alarm_type TEXT NOT NULL, -- 'high', 'low', 'deviation', 'rate_of_change'
    severity TEXT NOT NULL, -- 'warning', 'alarm', 'critical'
    triggered_value TEXT,
    threshold_value TEXT,
    message TEXT,
    acknowledged BOOLEAN DEFAULT 0,
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMP,
    cleared BOOLEAN DEFAULT 0,
    cleared_at TIMESTAMP,
    timestamp_unix INTEGER NOT NULL,
    FOREIGN KEY(datapoint) REFERENCES datapoints(name) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_alarms_datapoint ON datapoint_alarms(datapoint);
CREATE INDEX IF NOT EXISTS idx_alarms_timestamp ON datapoint_alarms(timestamp_unix);
CREATE INDEX IF NOT EXISTS idx_alarms_active ON datapoint_alarms(cleared) WHERE cleared = 0;

-- Event Log
CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL,
    service TEXT,
    subsystem TEXT,
    entity TEXT,
    event_type TEXT,
    message TEXT NOT NULL,
    details_json TEXT,
    timestamp_unix INTEGER NOT NULL,
    FOREIGN KEY(level) REFERENCES log_levels(name),
    FOREIGN KEY(service) REFERENCES services(name) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_event_log_level ON event_log(level);
CREATE INDEX IF NOT EXISTS idx_event_log_service ON event_log(service);
CREATE INDEX IF NOT EXISTS idx_event_log_timestamp ON event_log(timestamp_unix);
CREATE INDEX IF NOT EXISTS idx_event_log_type ON event_log(event_type);

-- Device Groups
CREATE TABLE IF NOT EXISTS device_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT,
    color TEXT DEFAULT '#3B82F6',
    icon TEXT,
    description TEXT,
    parent_group_id INTEGER,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(parent_group_id) REFERENCES device_groups(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_device_groups_parent ON device_groups(parent_group_id);

-- Device Group Members
CREATE TABLE IF NOT EXISTS device_group_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    device_id TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(group_id) REFERENCES device_groups(id) ON DELETE CASCADE,
    FOREIGN KEY(device_id) REFERENCES devices(id) ON DELETE CASCADE,
    UNIQUE(group_id, device_id)
);

CREATE INDEX IF NOT EXISTS idx_group_members_group ON device_group_members(group_id);
CREATE INDEX IF NOT EXISTS idx_group_members_device ON device_group_members(device_id);

-- Tag Categories
CREATE TABLE IF NOT EXISTS tag_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT,
    description TEXT,
    color TEXT DEFAULT '#3B82F6',
    icon TEXT,
    parent_category_id INTEGER,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(parent_category_id) REFERENCES tag_categories(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_tag_categories_parent ON tag_categories(parent_category_id);

-- Datapoint Categories (Many-to-Many)
CREATE TABLE IF NOT EXISTS datapoint_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datapoint_ref TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(datapoint_ref) REFERENCES datapoints(name) ON DELETE CASCADE,
    FOREIGN KEY(category_id) REFERENCES tag_categories(id) ON DELETE CASCADE,
    UNIQUE(datapoint_ref, category_id)
);

CREATE INDEX IF NOT EXISTS idx_dp_cat_datapoint ON datapoint_categories(datapoint_ref);
CREATE INDEX IF NOT EXISTS idx_dp_cat_category ON datapoint_categories(category_id);

-- ============================================================================
-- GATEWAY CONFIGURATION TABLES
-- ============================================================================

-- Gateway Identity
CREATE TABLE IF NOT EXISTS gateway_identity (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    serial_number TEXT NOT NULL UNIQUE,
    model TEXT,
    firmware_version TEXT,
    hardware_version TEXT,
    deployment_site TEXT,
    asset_id TEXT,
    location_mode TEXT DEFAULT 'manual',
    latitude REAL,
    longitude REAL,
    altitude REAL,
    timezone TEXT DEFAULT 'UTC',
    mac_address TEXT,
    ip_address TEXT,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Gateway DateTime Configuration
CREATE TABLE IF NOT EXISTS gateway_datetime (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    timezone TEXT DEFAULT 'Asia/Kolkata',
    ntp_enabled BOOLEAN DEFAULT 1,
    ntp_server TEXT DEFAULT 'pool.ntp.org',
    ntp_backup_server TEXT,
    ntp_sync_interval_sec INTEGER DEFAULT 3600,
    date_format TEXT DEFAULT 'YYYY-MM-DD',
    time_format TEXT DEFAULT '24-hour',
    language TEXT DEFAULT 'en',
    locale TEXT DEFAULT 'en_US',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Gateway Network Configuration
CREATE TABLE IF NOT EXISTS gateway_network (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    mode TEXT DEFAULT 'ethernet',
    hostname TEXT,
    domain TEXT,
    ip_assignment TEXT DEFAULT 'dhcp',
    static_ip TEXT,
    subnet_mask TEXT,
    gateway TEXT,
    dns1 TEXT DEFAULT '8.8.8.8',
    dns2 TEXT DEFAULT '8.8.4.4',
    mtu INTEGER DEFAULT 1500,
    proxy_enabled BOOLEAN DEFAULT 0,
    proxy_server TEXT,
    proxy_port INTEGER,
    proxy_username TEXT,
    proxy_password TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Gateway Heartbeat Configuration
CREATE TABLE IF NOT EXISTS gateway_heartbeat (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    enabled BOOLEAN DEFAULT 1,
    interval_sec INTEGER DEFAULT 30,
    timeout_sec INTEGER DEFAULT 120,
    destination_url TEXT,
    include_system_stats BOOLEAN DEFAULT 1,
    include_service_status BOOLEAN DEFAULT 1,
    retry_count INTEGER DEFAULT 3,
    retry_interval_sec INTEGER DEFAULT 10,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Gateway Security Configuration
CREATE TABLE IF NOT EXISTS gateway_security (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    firewall_enabled BOOLEAN DEFAULT 1,
    ssh_enabled BOOLEAN DEFAULT 1,
    ssh_port INTEGER DEFAULT 22,
    ssh_password_auth BOOLEAN DEFAULT 0,
    https_only BOOLEAN DEFAULT 1,
    certificate_path TEXT,
    private_key_path TEXT,
    api_key_required BOOLEAN DEFAULT 1,
    session_timeout_min INTEGER DEFAULT 30,
    max_login_attempts INTEGER DEFAULT 5,
    lockout_duration_min INTEGER DEFAULT 15,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Gateway Storage Configuration
CREATE TABLE IF NOT EXISTS gateway_storage (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    history_retention_days INTEGER DEFAULT 30,
    log_retention_days INTEGER DEFAULT 7,
    auto_cleanup_enabled BOOLEAN DEFAULT 1,
    max_database_size_mb INTEGER DEFAULT 1000,
    backup_enabled BOOLEAN DEFAULT 1,
    backup_interval_hours INTEGER DEFAULT 24,
    backup_location TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- SERVICE-SPECIFIC CONFIGURATION TABLES
-- ============================================================================

-- ---------------------------------------------------------------------------
-- LOAD CELL SERVICE
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS load_cell_service_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT NOT NULL DEFAULT 'load_cell_service',
    pipeline_enabled BOOLEAN DEFAULT 1,
    pipeline_server TEXT DEFAULT '127.0.0.1',
    pipeline_port INTEGER DEFAULT 7000,
    polling_interval_ms INTEGER DEFAULT 15,
    log_level TEXT DEFAULT 'info',
    console_logging BOOLEAN DEFAULT 1,
    file_logging BOOLEAN DEFAULT 1,
    log_file_path TEXT,
    max_log_size_mb INTEGER DEFAULT 10,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(service_name) REFERENCES services(name) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS load_cell_datapoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    datapoint_ref TEXT NOT NULL,
    channel INTEGER NOT NULL,
    device_path TEXT NOT NULL,
    
    -- Capacity & Calibration
    capacity REAL NOT NULL,
    capacity_name TEXT DEFAULT 'capacity',
    unit TEXT DEFAULT 'kg',
    known_weight REAL,
    known_weight_raw REAL,
    tare_offset REAL,
    tare_auto BOOLEAN DEFAULT 0,
    shift_bits INTEGER DEFAULT 10,
    zero_offset REAL DEFAULT 0,
    
    -- Filtering Configuration
    median_filter_enabled BOOLEAN DEFAULT 1,
    median_filter_window INTEGER DEFAULT 5,
    moving_avg_enabled BOOLEAN DEFAULT 1,
    moving_avg_window INTEGER DEFAULT 3,
    lowpass_filter_enabled BOOLEAN DEFAULT 0,
    filter_cutoff_frequency REAL DEFAULT 8.0,
    filter_activation_delta_min REAL,
    
    -- Adaptive Deadband
    adaptive_deadband_enabled BOOLEAN DEFAULT 1,
    adaptive_deadband_min REAL DEFAULT 1.0,
    adaptive_deadband_max REAL DEFAULT 20.0,
    adaptive_deadband_grow_rate REAL DEFAULT 1.5,
    adaptive_deadband_shrink_rate REAL DEFAULT 5.0,
    
    -- Publishing & Update Control
    publish_step_grams REAL DEFAULT 50.0,
    publish_on_change BOOLEAN DEFAULT 1,
    max_publish_rate_ms INTEGER DEFAULT 100,
    
    -- Alarm Thresholds
    overload_enabled BOOLEAN DEFAULT 1,
    overload_threshold REAL,
    underload_enabled BOOLEAN DEFAULT 0,
    underload_threshold REAL,
    
    -- Status
    enabled BOOLEAN DEFAULT 1,
    last_calibration TIMESTAMP,
    calibration_expires TIMESTAMP,
    error_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(datapoint_ref) REFERENCES datapoints(name) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_loadcell_dp_name ON load_cell_datapoints(name);
CREATE INDEX IF NOT EXISTS idx_loadcell_dp_ref ON load_cell_datapoints(datapoint_ref);
CREATE INDEX IF NOT EXISTS idx_loadcell_dp_channel ON load_cell_datapoints(channel);

-- ---------------------------------------------------------------------------
-- MODBUS SERVICE
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS modbus_service_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT NOT NULL DEFAULT 'modbus_service',
    
    -- Pipeline Configuration
    pipeline_server TEXT DEFAULT '127.0.0.1',
    pipeline_port INTEGER DEFAULT 7000,
    
    -- Logging
    log_level TEXT DEFAULT 'debug',
    enable_logging BOOLEAN DEFAULT 1,
    log_file_path TEXT,
    
    -- Performance Settings
    read_strategy TEXT DEFAULT 'auto',
    enable_packing BOOLEAN DEFAULT 1,
    max_block_gap INTEGER DEFAULT 5,
    max_block_size INTEGER DEFAULT 125,
    inter_request_delay_ms INTEGER DEFAULT 2,
    
    -- Write Configuration
    default_write_interval_ms INTEGER DEFAULT 0,
    max_write_retries INTEGER DEFAULT 3,
    write_retry_delay_ms INTEGER DEFAULT 50,
    coalesce_writes BOOLEAN DEFAULT 1,
    
    -- Connection Management
    connection_pool_size INTEGER DEFAULT 5,
    connection_timeout_ms INTEGER DEFAULT 5000,
    idle_timeout_sec INTEGER DEFAULT 300,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(service_name) REFERENCES services(name) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS modbus_connections (
    id TEXT PRIMARY KEY,
    service_name TEXT NOT NULL DEFAULT 'modbus_service',
    name TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL,
    
    -- RTU Configuration
    device TEXT,
    baud INTEGER,
    parity TEXT,
    data_bits INTEGER DEFAULT 8,
    stop_bits INTEGER DEFAULT 1,
    flow_control TEXT DEFAULT 'none',
    
    -- TCP Configuration
    host TEXT,
    port INTEGER DEFAULT 502,
    
    -- Timeouts and Retries
    response_timeout_ms INTEGER DEFAULT 500,
    byte_timeout_ms INTEGER DEFAULT 50,
    connect_timeout_ms INTEGER DEFAULT 3000,
    max_retries INTEGER DEFAULT 3,
    retry_delay_ms INTEGER DEFAULT 100,
    
    -- Polling Configuration
    polling_enabled BOOLEAN DEFAULT 1,
    polling_interval_ms INTEGER DEFAULT 100,
    poll_on_demand BOOLEAN DEFAULT 0,
    
    -- Connection Management
    auto_reconnect BOOLEAN DEFAULT 1,
    reconnect_delay_ms INTEGER DEFAULT 5000,
    keep_alive_enabled BOOLEAN DEFAULT 1,
    keep_alive_interval_sec INTEGER DEFAULT 60,
    
    -- Status
    enabled BOOLEAN DEFAULT 1,
    connected BOOLEAN DEFAULT 0,
    last_connected TIMESTAMP,
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(service_name) REFERENCES services(name) ON DELETE CASCADE,
    FOREIGN KEY(type) REFERENCES protocol_types(name)
);

CREATE INDEX IF NOT EXISTS idx_modbus_conn_service ON modbus_connections(service_name);
CREATE INDEX IF NOT EXISTS idx_modbus_conn_type ON modbus_connections(type);
CREATE INDEX IF NOT EXISTS idx_modbus_conn_enabled ON modbus_connections(enabled);

CREATE TABLE IF NOT EXISTS modbus_datapoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    datapoint_ref TEXT NOT NULL,
    connection_id TEXT NOT NULL,
    
    -- Modbus Address Configuration
    slave_id INTEGER NOT NULL,
    register_type TEXT NOT NULL,
    address INTEGER NOT NULL,
    register_count INTEGER DEFAULT 1,
    data_type TEXT NOT NULL,
    
    -- Data Transformation
    scale REAL DEFAULT 1.0,
    offset REAL DEFAULT 0.0,
    byte_order TEXT DEFAULT 'big',
    word_order TEXT DEFAULT 'big',
    bit_mask INTEGER,
    bit_shift INTEGER DEFAULT 0,
    
    -- Access Control
    readable BOOLEAN DEFAULT 1,
    writable BOOLEAN DEFAULT 0,
    write_verify BOOLEAN DEFAULT 1,
    
    -- Polling Configuration
    poll_enabled BOOLEAN DEFAULT 1,
    poll_interval_ms INTEGER,
    poll_priority INTEGER DEFAULT 1,
    poll_on_change_only BOOLEAN DEFAULT 0,
    
    -- Error Handling
    retry_count INTEGER DEFAULT 3,
    timeout_ms INTEGER DEFAULT 1000,
    error_value TEXT,
    ignore_errors BOOLEAN DEFAULT 0,
    
    -- Status
    enabled BOOLEAN DEFAULT 1,
    last_read TIMESTAMP,
    last_write TIMESTAMP,
    read_count INTEGER DEFAULT 0,
    write_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(datapoint_ref) REFERENCES datapoints(name) ON DELETE CASCADE,
    FOREIGN KEY(connection_id) REFERENCES modbus_connections(id) ON DELETE CASCADE,
    FOREIGN KEY(register_type) REFERENCES register_types(name),
    FOREIGN KEY(byte_order) REFERENCES byte_orders(name),
    FOREIGN KEY(word_order) REFERENCES byte_orders(name),
    UNIQUE(connection_id, slave_id, register_type, address)
);

CREATE INDEX IF NOT EXISTS idx_modbus_dp_name ON modbus_datapoints(name);
CREATE INDEX IF NOT EXISTS idx_modbus_dp_ref ON modbus_datapoints(datapoint_ref);
CREATE INDEX IF NOT EXISTS idx_modbus_dp_conn ON modbus_datapoints(connection_id);
CREATE INDEX IF NOT EXISTS idx_modbus_dp_slave ON modbus_datapoints(slave_id);
CREATE INDEX IF NOT EXISTS idx_modbus_dp_addr ON modbus_datapoints(connection_id, slave_id, address);

-- ---------------------------------------------------------------------------
-- NETWORK SERVICE
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS network_service_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT NOT NULL DEFAULT 'network_status',
    
    -- Service Settings
    polling_interval_ms INTEGER DEFAULT 1000,
    push_on_change BOOLEAN DEFAULT 1,
    log_level TEXT DEFAULT 'info',
    
    -- DBus Settings
    use_dbus BOOLEAN DEFAULT 1,
    network_manager_service TEXT DEFAULT 'org.freedesktop.NetworkManager',
    modem_manager_service TEXT DEFAULT 'org.freedesktop.ModemManager1',
    dbus_timeout_ms INTEGER DEFAULT 1000,
    
    -- Monitoring Settings
    monitor_bandwidth BOOLEAN DEFAULT 1,
    monitor_latency BOOLEAN DEFAULT 1,
    ping_target TEXT DEFAULT '8.8.8.8',
    ping_interval_sec INTEGER DEFAULT 30,
    
    -- Performance Settings
    max_consecutive_failures INTEGER DEFAULT 3,
    stats_log_interval_sec INTEGER DEFAULT 300,
    detailed_logging BOOLEAN DEFAULT 1,
    log_connection_details_once BOOLEAN DEFAULT 1,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(service_name) REFERENCES services(name) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS network_interfaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT NOT NULL DEFAULT 'network_status',
    
    interface_type TEXT NOT NULL,
    interface_name TEXT NOT NULL UNIQUE,
    datapoint_ref TEXT,
    display_name TEXT,
    
    -- Configuration
    enabled BOOLEAN DEFAULT 1,
    monitor_enabled BOOLEAN DEFAULT 1,
    dhcp_enabled BOOLEAN DEFAULT 1,
    static_ip TEXT,
    netmask TEXT,
    gateway TEXT,
    
    -- Type-specific Settings
    require_ip BOOLEAN DEFAULT 1,
    min_rssi INTEGER DEFAULT -90,
    min_rsrp INTEGER DEFAULT -110,
    
    -- WiFi Specific
    ssid TEXT,
    password TEXT,
    security_type TEXT,
    auto_connect BOOLEAN DEFAULT 1,
    
    -- Cellular Specific
    apn TEXT,
    username TEXT,
    password_cell TEXT,
    pin TEXT,
    
    -- Status
    connected BOOLEAN DEFAULT 0,
    ip_address TEXT,
    mac_address TEXT,
    signal_strength INTEGER,
    bandwidth_up_kbps INTEGER,
    bandwidth_down_kbps INTEGER,
    latency_ms INTEGER,
    last_connected TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(service_name) REFERENCES services(name) ON DELETE CASCADE,
    FOREIGN KEY(interface_type) REFERENCES network_interface_types(name),
    FOREIGN KEY(datapoint_ref) REFERENCES datapoints(name) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_network_if_service ON network_interfaces(service_name);
CREATE INDEX IF NOT EXISTS idx_network_if_type ON network_interfaces(interface_type);
CREATE INDEX IF NOT EXISTS idx_network_if_enabled ON network_interfaces(enabled);

-- ---------------------------------------------------------------------------
-- GPIO SERVICE
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS gpio_service_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT NOT NULL DEFAULT 'gpio_service',
    
    -- Service Settings
    polling_interval_ms INTEGER DEFAULT 50,
    use_gpiod BOOLEAN DEFAULT 1,
    gpio_chip_path TEXT DEFAULT '/dev/gpiochip0',
    
    -- Logging
    log_level TEXT DEFAULT 'info',
    enable_logging BOOLEAN DEFAULT 1,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(service_name) REFERENCES services(name) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gpio_pins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    datapoint_ref TEXT NOT NULL,
    
    -- Pin Configuration
    pin_number INTEGER NOT NULL,
    direction TEXT NOT NULL, -- 'input', 'output'
    chip_id INTEGER DEFAULT 0,
    
    -- Input Configuration
    pull_mode TEXT DEFAULT 'none', -- 'none', 'up', 'down'
    active_low BOOLEAN DEFAULT 0,
    debounce_ms INTEGER DEFAULT 0,
    edge_detection TEXT DEFAULT 'both', -- 'rising', 'falling', 'both', 'none'
    
    -- Output Configuration
    initial_value BOOLEAN DEFAULT 0,
    drive_mode TEXT DEFAULT 'push-pull', -- 'push-pull', 'open-drain', 'open-source'
    
    -- Status
    enabled BOOLEAN DEFAULT 1,
    current_value BOOLEAN,
    last_change TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(datapoint_ref) REFERENCES datapoints(name) ON DELETE CASCADE,
    UNIQUE(chip_id, pin_number)
);

CREATE INDEX IF NOT EXISTS idx_gpio_pins_dp ON gpio_pins(datapoint_ref);
CREATE INDEX IF NOT EXISTS idx_gpio_pins_chip ON gpio_pins(chip_id, pin_number);

-- ---------------------------------------------------------------------------
-- MQTT SERVICE
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS mqtt_service_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT NOT NULL DEFAULT 'mqtt_service',
    
    -- Broker Settings
    broker_host TEXT NOT NULL DEFAULT 'localhost',
    broker_port INTEGER DEFAULT 1883,
    use_tls BOOLEAN DEFAULT 0,
    tls_ca_cert TEXT,
    tls_client_cert TEXT,
    tls_client_key TEXT,
    
    -- Authentication
    username TEXT,
    password TEXT,
    client_id TEXT,
    
    -- Connection Settings
    keep_alive_sec INTEGER DEFAULT 60,
    clean_session BOOLEAN DEFAULT 1,
    auto_reconnect BOOLEAN DEFAULT 1,
    reconnect_delay_sec INTEGER DEFAULT 5,
    max_reconnect_delay_sec INTEGER DEFAULT 300,
    
    -- QoS Settings
    default_qos INTEGER DEFAULT 1,
    retain_messages BOOLEAN DEFAULT 0,
    
    -- Logging
    log_level TEXT DEFAULT 'info',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(service_name) REFERENCES services(name) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mqtt_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    topic TEXT NOT NULL,
    datapoint_ref TEXT,
    
    -- Topic Configuration
    direction TEXT NOT NULL, -- 'publish', 'subscribe', 'both'
    qos INTEGER DEFAULT 1,
    retain BOOLEAN DEFAULT 0,
    
    -- Payload Configuration
    payload_type TEXT DEFAULT 'json', -- 'json', 'string', 'binary', 'number'
    json_path TEXT,
    encoding TEXT DEFAULT 'utf-8',
    
    -- Publishing
    publish_interval_ms INTEGER,
    publish_on_change BOOLEAN DEFAULT 1,
    
    -- Status
    enabled BOOLEAN DEFAULT 1,
    last_publish TIMESTAMP,
    last_receive TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(datapoint_ref) REFERENCES datapoints(name) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mqtt_topics_dp ON mqtt_topics(datapoint_ref);
CREATE INDEX IF NOT EXISTS idx_mqtt_topics_direction ON mqtt_topics(direction);

-- ---------------------------------------------------------------------------
-- OPC UA SERVICE
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS opcua_service_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT NOT NULL DEFAULT 'opcua_service',
    
    -- Server Settings
    server_url TEXT NOT NULL,
    security_policy TEXT DEFAULT 'None',
    security_mode TEXT DEFAULT 'None',
    
    -- Authentication
    username TEXT,
    password TEXT,
    certificate_path TEXT,
    private_key_path TEXT,
    
    -- Connection Settings
    session_timeout_ms INTEGER DEFAULT 60000,
    secure_channel_lifetime_ms INTEGER DEFAULT 600000,
    
    -- Subscription Settings
    publishing_interval_ms INTEGER DEFAULT 100,
    lifetime_count INTEGER DEFAULT 10000,
    max_keep_alive_count INTEGER DEFAULT 10,
    max_notifications_per_publish INTEGER DEFAULT 0,
    
    -- Logging
    log_level TEXT DEFAULT 'info',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(service_name) REFERENCES services(name) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS opcua_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    datapoint_ref TEXT NOT NULL,
    
    -- Node Configuration
    node_id TEXT NOT NULL,
    namespace_index INTEGER DEFAULT 0,
    
    -- Access
    readable BOOLEAN DEFAULT 1,
    writable BOOLEAN DEFAULT 0,
    
    -- Monitoring
    monitor_enabled BOOLEAN DEFAULT 1,
    sampling_interval_ms INTEGER DEFAULT 100,
    queue_size INTEGER DEFAULT 1,
    discard_oldest BOOLEAN DEFAULT 1,
    
    -- Status
    enabled BOOLEAN DEFAULT 1,
    last_read TIMESTAMP,
    last_write TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(datapoint_ref) REFERENCES datapoints(name) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_opcua_nodes_dp ON opcua_nodes(datapoint_ref);

-- ============================================================================
-- VIEWS FOR CONVENIENT DATA ACCESS
-- ============================================================================

-- Latest Datapoint Values with Details
CREATE VIEW IF NOT EXISTS v_latest_datapoint_values AS
SELECT 
    dv.datapoint,
    dv.value,
    dv.health,
    dv.quality,
    dv.service,
    dv.timestamp_unix,
    datetime(dv.timestamp_unix, 'unixepoch') as timestamp,
    dp.type,
    dp.unit,
    dp.description,
    dp.display_name,
    dp.min_value,
    dp.max_value,
    dp.precision,
    dp.scaling_factor,
    dp.scaling_offset
FROM datapoint_values dv
INNER JOIN datapoints dp ON dv.datapoint = dp.name
WHERE dp.enabled = 1;

-- Service Status Overview
CREATE VIEW IF NOT EXISTS v_service_status AS
SELECT 
    s.id,
    s.name,
    s.display_name,
    s.description,
    s.version,
    s.enabled,
    s.status,
    s.uptime_seconds,
    s.cpu_usage_percent,
    s.memory_usage_kb,
    s.restart_count,
    COUNT(DISTINCT d.id) as device_count,
    COUNT(DISTINCT si.id) as interface_count,
    s.last_restart,
    s.created_at
FROM services s
LEFT JOIN devices d ON d.service = s.name AND d.enabled = 1
LEFT JOIN service_interfaces si ON si.service = s.name AND si.enabled = 1
GROUP BY s.id;

-- Device Summary with Groups
CREATE VIEW IF NOT EXISTS v_device_summary AS
SELECT 
    d.id,
    d.name,
    d.display_name,
    d.type,
    d.service,
    d.protocol,
    d.address,
    d.port,
    d.enabled,
    d.status,
    d.connection_quality,
    d.last_seen,
    d.error_count,
    GROUP_CONCAT(DISTINCT dg.name, ', ') as groups,
    COUNT(DISTINCT dgm.group_id) as group_count
FROM devices d
LEFT JOIN device_group_members dgm ON dgm.device_id = d.id
LEFT JOIN device_groups dg ON dg.id = dgm.group_id
GROUP BY d.id;

-- Active Alarms
CREATE VIEW IF NOT EXISTS v_active_alarms AS
SELECT 
    da.id,
    da.datapoint,
    dp.display_name as datapoint_display_name,
    da.alarm_type,
    da.severity,
    da.triggered_value,
    da.threshold_value,
    da.message,
    da.acknowledged,
    da.acknowledged_by,
    da.acknowledged_at,
    da.timestamp_unix,
    datetime(da.timestamp_unix, 'unixepoch') as timestamp,
    (strftime('%s', 'now') - da.timestamp_unix) as duration_seconds
FROM datapoint_alarms da
INNER JOIN datapoints dp ON da.datapoint = dp.name
WHERE da.cleared = 0
ORDER BY da.severity DESC, da.timestamp_unix DESC;

-- Modbus Connection Status
CREATE VIEW IF NOT EXISTS v_modbus_connections AS
SELECT 
    mc.id,
    mc.name,
    mc.type,
    mc.host,
    mc.port,
    mc.device,
    mc.baud,
    mc.enabled,
    mc.connected,
    mc.last_connected,
    mc.error_count,
    COUNT(md.id) as datapoint_count,
    COUNT(CASE WHEN md.enabled = 1 THEN 1 END) as active_datapoint_count
FROM modbus_connections mc
LEFT JOIN modbus_datapoints md ON md.connection_id = mc.id
GROUP BY mc.id;

-- Load Cell Status
CREATE VIEW IF NOT EXISTS v_load_cell_status AS
SELECT 
    lc.id,
    lc.name,
    lc.datapoint_ref,
    lc.capacity,
    lc.unit,
    lc.channel,
    lc.enabled,
    lc.tare_offset,
    lc.last_calibration,
    dv.value as current_value,
    dv.health,
    dv.quality,
    dv.timestamp_unix,
    datetime(dv.timestamp_unix, 'unixepoch') as last_update
FROM load_cell_datapoints lc
LEFT JOIN datapoint_values dv ON dv.datapoint = lc.datapoint_ref;

-- Network Interface Status
CREATE VIEW IF NOT EXISTS v_network_status AS
SELECT 
    ni.id,
    ni.interface_name,
    ni.interface_type,
    ni.display_name,
    ni.enabled,
    ni.connected,
    ni.ip_address,
    ni.mac_address,
    ni.signal_strength,
    ni.bandwidth_up_kbps,
    ni.bandwidth_down_kbps,
    ni.latency_ms,
    ni.last_connected
FROM network_interfaces ni
WHERE ni.enabled = 1;

-- Recent Events
CREATE VIEW IF NOT EXISTS v_recent_events AS
SELECT 
    el.id,
    el.level,
    el.service,
    el.subsystem,
    el.entity,
    el.event_type,
    el.message,
    el.timestamp_unix,
    datetime(el.timestamp_unix, 'unixepoch') as timestamp,
    (strftime('%s', 'now') - el.timestamp_unix) as age_seconds
FROM event_log el
WHERE el.timestamp_unix > (strftime('%s', 'now') - 86400) -- Last 24 hours
ORDER BY el.timestamp_unix DESC
LIMIT 1000;

-- Datapoint Statistics (aggregated history)
CREATE VIEW IF NOT EXISTS v_datapoint_statistics AS
SELECT 
    datapoint,
    COUNT(*) as sample_count,
    MIN(CAST(value AS REAL)) as min_value,
    MAX(CAST(value AS REAL)) as max_value,
    AVG(CAST(value AS REAL)) as avg_value,
    MIN(timestamp_unix) as first_sample,
    MAX(timestamp_unix) as last_sample,
    datetime(MIN(timestamp_unix), 'unixepoch') as first_sample_time,
    datetime(MAX(timestamp_unix), 'unixepoch') as last_sample_time
FROM datapoint_history
WHERE 
    timestamp_unix > (strftime('%s', 'now') - 86400) -- Last 24 hours
    AND value GLOB '[0-9]*' -- Only numeric values
GROUP BY datapoint;

-- ============================================================================
-- TRIGGERS FOR AUTOMATIC UPDATES
-- ============================================================================

-- Update timestamps on record changes
CREATE TRIGGER IF NOT EXISTS trg_services_update_timestamp 
AFTER UPDATE ON services
BEGIN
    UPDATE services SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_devices_update_timestamp 
AFTER UPDATE ON devices
BEGIN
    UPDATE devices SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_datapoints_update_timestamp 
AFTER UPDATE ON datapoints
BEGIN
    UPDATE datapoints SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_service_interfaces_update_timestamp 
AFTER UPDATE ON service_interfaces
BEGIN
    UPDATE service_interfaces SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Update datapoint_values when history is inserted
CREATE TRIGGER IF NOT EXISTS trg_update_datapoint_values
AFTER INSERT ON datapoint_history
BEGIN
    INSERT OR REPLACE INTO datapoint_values (datapoint, value, health, service, timestamp_unix, quality)
    VALUES (NEW.datapoint, NEW.value, NEW.health, NEW.service, NEW.timestamp_unix, NEW.quality);
END;

-- Check for alarms when datapoint value changes
CREATE TRIGGER IF NOT EXISTS trg_check_datapoint_alarms
AFTER INSERT ON datapoint_history
BEGIN
    -- Check high alarm
    INSERT INTO datapoint_alarms (datapoint, alarm_type, severity, triggered_value, threshold_value, message, timestamp_unix)
    SELECT 
        NEW.datapoint,
        'high',
        'alarm',
        NEW.value,
        dp.alarm_high,
        'Value ' || NEW.value || ' exceeds high threshold ' || dp.alarm_high,
        NEW.timestamp_unix
    FROM datapoints dp
    WHERE dp.name = NEW.datapoint
        AND dp.alarm_enabled = 1
        AND dp.alarm_high IS NOT NULL
        AND CAST(NEW.value AS REAL) > dp.alarm_high
        AND NOT EXISTS (
            SELECT 1 FROM datapoint_alarms 
            WHERE datapoint = NEW.datapoint 
                AND alarm_type = 'high' 
                AND cleared = 0
        );
    
    -- Check low alarm
    INSERT INTO datapoint_alarms (datapoint, alarm_type, severity, triggered_value, threshold_value, message, timestamp_unix)
    SELECT 
        NEW.datapoint,
        'low',
        'alarm',
        NEW.value,
        dp.alarm_low,
        'Value ' || NEW.value || ' below low threshold ' || dp.alarm_low,
        NEW.timestamp_unix
    FROM datapoints dp
    WHERE dp.name = NEW.datapoint
        AND dp.alarm_enabled = 1
        AND dp.alarm_low IS NOT NULL
        AND CAST(NEW.value AS REAL) < dp.alarm_low
        AND NOT EXISTS (
            SELECT 1 FROM datapoint_alarms 
            WHERE datapoint = NEW.datapoint 
                AND alarm_type = 'low' 
                AND cleared = 0
        );
    
    -- Clear high alarm if value returns to normal
    UPDATE datapoint_alarms
    SET cleared = 1, cleared_at = CURRENT_TIMESTAMP
    WHERE datapoint = NEW.datapoint
        AND alarm_type = 'high'
        AND cleared = 0
        AND CAST(NEW.value AS REAL) <= (
            SELECT alarm_high FROM datapoints WHERE name = NEW.datapoint
        );
    
    -- Clear low alarm if value returns to normal
    UPDATE datapoint_alarms
    SET cleared = 1, cleared_at = CURRENT_TIMESTAMP
    WHERE datapoint = NEW.datapoint
        AND alarm_type = 'low'
        AND cleared = 0
        AND CAST(NEW.value AS REAL) >= (
            SELECT alarm_low FROM datapoints WHERE name = NEW.datapoint
        );
END;

-- Auto-cleanup old history based on retention policy
CREATE TRIGGER IF NOT EXISTS trg_cleanup_history
AFTER INSERT ON datapoint_history
BEGIN
    DELETE FROM datapoint_history
    WHERE timestamp_unix < (
        strftime('%s', 'now') - (
            SELECT retention_days * 86400 
            FROM datapoints 
            WHERE name = NEW.datapoint
        )
    )
    AND datapoint = NEW.datapoint;
END;

-- Increment message count on interface publish
CREATE TRIGGER IF NOT EXISTS trg_interface_message_count
AFTER UPDATE OF last_publish ON service_interfaces
BEGIN
    UPDATE service_interfaces 
    SET message_count = message_count + 1 
    WHERE id = NEW.id;
END;

-- Track device connection status changes
CREATE TRIGGER IF NOT EXISTS trg_device_status_change
AFTER UPDATE OF status ON devices
WHEN NEW.status != OLD.status
BEGIN
    INSERT INTO event_log (level, service, subsystem, entity, event_type, message, timestamp_unix)
    VALUES (
        CASE WHEN NEW.status = 'online' THEN 'info' ELSE 'warning' END,
        NEW.service,
        'device_manager',
        NEW.id,
        'device_status_change',
        'Device ' || NEW.name || ' status changed from ' || OLD.status || ' to ' || NEW.status,
        strftime('%s', 'now')
    );
END;

-- ============================================================================
-- DEFAULT DATA INITIALIZATION
-- ============================================================================

-- Insert default tag categories
INSERT OR IGNORE INTO tag_categories (name, display_name, description, color, icon) VALUES
    ('load_monitoring', 'Load Monitoring', 'Load measurement and monitoring tags', '#EF4444', 'weight'),
    ('safety', 'Safety', 'Safety-related tags and interlocks', '#F97316', 'shield'),
    ('position', 'Position Tracking', 'Position and movement tags', '#10B981', 'move'),
    ('sensors', 'Sensors', 'Sensor data tags', '#3B82F6', 'sensor'),
    ('motors', 'Motors & Drives', 'Motor control and status tags', '#8B5CF6', 'zap'),
    ('diagnostics', 'Diagnostics', 'Diagnostic and health monitoring', '#FBBF24', 'activity'),
    ('status', 'Status', 'General status monitoring tags', '#06B6D4', 'info'),
    ('configuration', 'Configuration', 'Configuration parameters', '#6B7280', 'settings'),
    ('alarms', 'Alarms', 'Alarm and event tags', '#DC2626', 'alert-triangle'),
    ('control', 'Control', 'Control command tags', '#7C3AED', 'toggle');

-- Insert default device groups
INSERT OR IGNORE INTO device_groups (name, display_name, description, color, icon) VALUES
    ('load_cells', 'Load Cells', 'Load cell devices', '#EF4444', 'weight'),
    ('plc', 'PLCs', 'Programmable Logic Controllers', '#3B82F6', 'cpu'),
    ('io_modules', 'I/O Modules', 'Input/Output expansion modules', '#10B981', 'grid'),
    ('hmi', 'HMI Devices', 'Human-Machine Interface panels', '#F59E0B', 'monitor'),
    ('drives', 'Motor Drives', 'Variable Frequency Drives', '#8B5CF6', 'zap'),
    ('sensors', 'Sensors', 'Various sensor devices', '#06B6D4', 'sensor'),
    ('network', 'Network Devices', 'Network infrastructure', '#6B7280', 'router');

-- Insert default gateway identity (if not exists)
INSERT OR IGNORE INTO gateway_identity (
    id, name, serial_number, model, firmware_version, 
    deployment_site, asset_id, location_mode, mac_address
) VALUES (
    1, 'CraneIQ-Gateway-001', 'CQGW-2025-001', 'CraneIQ-GW-v2', '2.0.0',
    'Default Site', 'GW-001', 'manual', '00:00:00:00:00:00'
);

-- Insert default datetime config
INSERT OR IGNORE INTO gateway_datetime (id) VALUES (1);

-- Insert default network config
INSERT OR IGNORE INTO gateway_network (id) VALUES (1);

-- Insert default heartbeat config
INSERT OR IGNORE INTO gateway_heartbeat (id) VALUES (1);

-- Insert default security config
INSERT OR IGNORE INTO gateway_security (id) VALUES (1);

-- Insert default storage config
INSERT OR IGNORE INTO gateway_storage (id) VALUES (1);

-- ============================================================================
-- PERFORMANCE OPTIMIZATION
-- ============================================================================

-- Analyze tables for query optimization
ANALYZE;

-- ============================================================================
-- SCHEMA VERSION TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version TEXT PRIMARY KEY,
    description TEXT,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO schema_version (version, description) VALUES
    ('2.0.0', 'Complete CraneIQ database schema with multi-service architecture');

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
