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
    
    # Device management tables (new) - WITHOUT firmware_version
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
            group_id INTEGER,
            config_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES device_groups(id)
        )
    ''')
    
   
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tag_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            tag_name TEXT NOT NULL,
            description TEXT,
            address TEXT NOT NULL,
            data_type TEXT NOT NULL,
            endianness TEXT DEFAULT 'big-endian',
            scale REAL DEFAULT 1.0,
            offset REAL DEFAULT 0.0,
            unit TEXT,
            poll_interval INTEGER DEFAULT 200,
            category TEXT,
            min_valid REAL,
            max_valid REAL,
            protocol_config TEXT,  -- JSON with protocol-specific config
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(device_id, tag_name),
            FOREIGN KEY (device_id) REFERENCES device_management(id) ON DELETE CASCADE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tag_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            color TEXT DEFAULT 'blue',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    
    # Insert default categories if not exists
    default_categories = [
        ('Load Monitoring', 'Load measurement tags', 'red'),
        ('Safety', 'Safety-related tags', 'orange'),
        ('Position Tracking', 'Position and movement tags', 'green'),
        ('Sensors', 'Sensor data tags', 'blue'),
        ('Motor', 'Motor control tags', 'purple'),
        ('Diagnostic', 'Diagnostic and health tags', 'yellow'),
        ('Status', 'Status monitoring tags', 'cyan'),
        ('Configuration', 'Configuration tags', 'gray')
    ]
    
    for category in default_categories:
        cursor.execute('''
            INSERT OR IGNORE INTO tag_categories (name, description, color)
            VALUES (?, ?, ?)
        ''', category)
    
    conn.commit()
    conn.close()
    print("Database initialized with all tables")
    print("✓ Device management table created WITHOUT firmware_version column")
    print("✓ Tag mapping tables created with default categories")

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
        
        # Deep merge of configuration
        for key in config_data:
            if key in current and isinstance(current[key], dict) and isinstance(config_data[key], dict):
                # Recursive merge for nested dictionaries
                def merge_dicts(dict1, dict2):
                    for k, v in dict2.items():
                        if k in dict1 and isinstance(dict1[k], dict) and isinstance(v, dict):
                            merge_dicts(dict1[k], v)
                        else:
                            dict1[k] = v
                
                merge_dicts(current[key], config_data[key])
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

def get_device_count():
    """Get total number of devices"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM device_management')
        count = cursor.fetchone()[0]
        
        conn.close()
        return count
    except:
        return 0

def get_group_count():
    """Get total number of groups"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM device_groups')
        count = cursor.fetchone()[0]
        
        conn.close()
        return count
    except:
        return 0

def get_tag_count():
    """Get total number of tag mappings"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM tag_mappings')
        count = cursor.fetchone()[0]
        
        conn.close()
        return count
    except:
        return 0

def get_database_stats():
    """Get database statistics"""
    return {
        'devices': get_device_count(),
        'groups': get_group_count(),
        'tags': get_tag_count()
    }

def reset_database():
    """Reset database - DANGEROUS: Only for development"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Drop all tables
        cursor.execute('DROP TABLE IF EXISTS tag_mappings')
        cursor.execute('DROP TABLE IF EXISTS tag_categories')
        cursor.execute('DROP TABLE IF EXISTS device_management')
        cursor.execute('DROP TABLE IF EXISTS device_groups')
        cursor.execute('DROP TABLE IF EXISTS general_configuration')
        
        conn.commit()
        conn.close()
        
        print("Database reset complete")
        print("Re-initializing database...")
        init_database()
        
        return True
    except Exception as e:
        print("Error resetting database: {}".format(e))
        return False

def backup_database(backup_file='gateway_config_backup.db'):
    """Create a backup of the database"""
    try:
        import shutil
        import os
        
        if os.path.exists(DB_FILE):
            shutil.copy2(DB_FILE, backup_file)
            print("Database backed up to: {}".format(backup_file))
            return True
        else:
            print("Database file not found: {}".format(DB_FILE))
            return False
    except Exception as e:
        print("Error backing up database: {}".format(e))
        return False

def restore_database(backup_file='gateway_config_backup.db'):
    """Restore database from backup"""
    try:
        import shutil
        import os
        
        if os.path.exists(backup_file):
            # Close any existing connections
            import sqlite3
            try:
                sqlite3.connect(DB_FILE).close()
            except:
                pass
            
            shutil.copy2(backup_file, DB_FILE)
            print("Database restored from: {}".format(backup_file))
            return True
        else:
            print("Backup file not found: {}".format(backup_file))
            return False
    except Exception as e:
        print("Error restoring database: {}".format(e))
        return False

# Test function to verify database structure
def test_database_structure():
    """Test database structure and print schema"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        print("\n=== Database Structure ===")
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            print(f"\nTable: {table_name}")
            
            # Get table schema
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            for col in columns:
                col_id, col_name, col_type, not_null, default_val, pk = col
                print(f"  {col_name}: {col_type} {'PK' if pk else ''} {'NOT NULL' if not_null else ''} {f'DEFAULT {default_val}' if default_val else ''}")
        
        # Get row counts
        print("\n=== Row Counts ===")
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"{table_name}: {count} rows")
        
        conn.close()
        return True
    except Exception as e:
        print("Error testing database structure: {}".format(e))
        return False

# Initialize database when module is imported
if __name__ == '__main__':
    print("Initializing database...")
    init_database()
    test_database_structure()
else:
    # Auto-initialize when module is imported
    init_database()