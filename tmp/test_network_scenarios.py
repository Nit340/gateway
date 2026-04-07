import sys
import os
import time
import json
import sqlite3
import unittest
from unittest.mock import MagicMock

# Add path to backend
sys.path.append(r'c:\Users\naresh kumar\Desktop\gateway\flask')

# Import modules to test
import database
import pipeline

class TestNetworkScenarios(unittest.TestCase):
    def setUp(self):
        # Reset pipeline state
        with pipeline.pipeline_state["lock"]:
            pipeline.pipeline_state["network_route_pending"] = None
        
        # Mock database functions to avoid side effects on real DB
        self.mock_config = {
            'network': {
                'auto_connect': True,
                'last_route_select': 0
            }
        }
        database.get_general_configuration = MagicMock(return_value=self.mock_config)
        
        # Mock client
        self.client = MagicMock()
        self.client.datapoint_set = MagicMock(return_value=True)
        self.client.publish_datapoint = MagicMock(return_value=True)
        self.client.datapoint_update = MagicMock(return_value=True)

    def test_scenario_2_auto_on_restart(self):
        """Scenario 2: Auto ON Restart -> Should force Route 0"""
        self.mock_config['network']['auto_connect'] = True
        pipeline._flush_pending_network_route(self.client)
        
        # Check if 0 was sent
        self.client.datapoint_set.assert_called_with('network_route_select', 0)

    def test_scenario_7_manual_restart_restore(self):
        """Scenario 7: Manual Restart (WiFi) -> Should restore Route 4 from DB"""
        self.mock_config['network']['auto_connect'] = False
        self.mock_config['network']['last_route_select'] = 4
        
        pipeline._flush_pending_network_route(self.client)
        
        # Check if 4 was sent
        self.client.datapoint_set.assert_called_with('network_route_select', 4)

    def test_scenario_10_manual_restart_lte(self):
        """Scenario 10: Manual Restart (LTE) -> Should restore Route 3 from DB"""
        self.mock_config['network']['auto_connect'] = False
        self.mock_config['network']['last_route_select'] = 3
        
        pipeline._flush_pending_network_route(self.client)
        
        # Check if 3 was sent
        self.client.datapoint_set.assert_called_with('network_route_select', 3)

    def test_scenario_1_toggle_auto_on(self):
        """Scenario 1 & 9: Toggle Auto ON -> Should send Route 0"""
        self.mock_config['network']['auto_connect'] = True
        
        # Simulate memory-only update (like frontend POST)
        with pipeline.pipeline_state["lock"]:
             pipeline.pipeline_state["network_route_pending"] = 0
             
        pipeline._flush_pending_network_route(self.client)
        self.client.datapoint_set.assert_called_with('network_route_select', 0)

if __name__ == '__main__':
    print("RUNNING NETWORK SCENARIO TESTS...")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestNetworkScenarios)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    
    if result.wasSuccessful():
        print("\nALL SCENARIO TESTS PASSED ✅")
    else:
        print("\nSOME TESTS FAILED ❌")
        sys.exit(1)
