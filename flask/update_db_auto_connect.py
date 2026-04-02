import sqlite3
import os

db_path = r'c:\Users\naresh kumar\Desktop\gateway\gateway_config.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(general_configuration)")
        cols = [r[1] for r in cursor.fetchall()]
        if 'auto_connect' not in cols:
            cursor.execute("ALTER TABLE general_configuration ADD COLUMN auto_connect INTEGER DEFAULT 1")
            print("Added auto_connect column with DEFAULT 1")
        else:
            cursor.execute("UPDATE general_configuration SET auto_connect = 1 WHERE auto_connect IS NULL OR auto_connect = 0")
            print("Updated auto_connect to 1")
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
else:
    print("DB not found")
