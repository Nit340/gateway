# flask/tests/test_pipeline_logic.py
import sys
import os
import unittest
import json
import sqlite3
from unittest.mock import MagicMock, patch

# Ensure flask dir is in path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from pipeline import _handle_received_loadcell_config
from mqtt_cloud import build_iot_gateway_config

class TestPipelineLogic(unittest.TestCase):
    def setUp(self):
        # Use a unique DB file name per test to avoid concurrency/locking issues
        import uuid
        self.db_file = "test_gateway_{}.db".format(uuid.uuid4().hex[:8])
        
        # Initial schema setup
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE loadcell_device (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                raw_filters TEXT,
                weight_filters TEXT,
                levels TEXT,
                tare_offset FLOAT,
                known_weight FLOAT,
                known_weight_raw FLOAT,
                pipeline_server TEXT,
                pipeline_port INTEGER,
                log_level TEXT,
                poll_ms INTEGER,
                unit TEXT,
                enabled INTEGER DEFAULT 1,
                updated_at TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE cloud_connections (
                id TEXT PRIMARY KEY,
                type TEXT,
                name TEXT,
                enabled INTEGER,
                config TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE general_configuration (
                id INTEGER PRIMARY KEY DEFAULT 1,
                config TEXT
            )
        ''')
        cursor.execute("INSERT INTO general_configuration (id, config) VALUES (1, '{}')")
        cursor.execute("INSERT INTO loadcell_device (name, enabled) VALUES (?, ?)", ("TestDevice", 1))
        conn.commit()
        conn.close()

        # Patch DB in database module directly
        self.patch_db_file = patch("database.DB_FILE", self.db_file)
        self.patch_db_conn = patch("database.get_db_connection", lambda: sqlite3.connect(self.db_file))
        self.patch_pipeline_db = patch("pipeline.DB_FILE", self.db_file)
        self.patch_mqtt_db = patch("mqtt_cloud.get_db_connection", lambda: sqlite3.connect(self.db_file))

        self.patch_db_file.start()
        self.patch_db_conn.start()
        self.patch_pipeline_db.start()
        self.patch_mqtt_db.start()

    def tearDown(self):
        self.patch_db_file.stop()
        self.patch_db_conn.stop()
        self.patch_pipeline_db.stop()
        self.patch_mqtt_db.stop()
        if os.path.exists(self.db_file):
            try: os.remove(self.db_file)
            except: pass

    def test_loadcell_config_storage(self):
        # Mock config object
        mock_cfg = MagicMock()
        mock_cfg.name = "loadcell_config"
        mock_cfg.version = 101
        mock_cfg.value = json.dumps({
            "load_cells": [{
                "name": "TestDevice",
                "filter": {
                    "raw": [{"type": "moving_average", "size": 10}],
                    "weight": [{"type": "kalman", "q": 0.1, "r": 1.0}]
                },
                "levels": {"parameters": {"ratios": [{"min": 0, "max": 100, "label": "Full"}]}},
                "calibration": {"parameters": {"ref_weight": {"value": 50, "unit": "kg"}, "ref_raw": 1000}},
                "device": {"parameters": {"poll_ms": 500}}
            }]
        })

        # Run handler
        _handle_received_loadcell_config(mock_cfg)

        # Verify DB update (opening fresh connection to avoid lock)
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT raw_filters, weight_filters, known_weight, poll_ms FROM loadcell_device WHERE name = 'TestDevice'")
        row = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(row)
        self.assertIn("moving_average", row[0])
        self.assertIn("kalman", row[1])
        self.assertEqual(row[2], 50.0)
        self.assertEqual(row[3], 500)

    def test_iot_gateway_empty_config(self):
        # With empty cloud_connections, build_iot_gateway_config should return an empty config (previously was None)
        config = build_iot_gateway_config()
        print("\nDEBUG CONFIG:", json.dumps(config))
        self.assertIsNotNone(config, "Config should not be None even if no connections exist")
        self.assertEqual(config.get("version"), 2)
        self.assertEqual(len(config.get("servers", {})), 0)
        self.assertEqual(len(config.get("mappings", [])), 0)

if __name__ == '__main__':
    unittest.main()
