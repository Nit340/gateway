import sys
import os
import json

# Add parent directory to path to import general
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import general
    from general import network_status_state, update_network_status_field
    
    print("Testing ETH0_IP_Address...")
    update_network_status_field("network_status/ETH0_IP_Address", "192.168.1.50")
    
    print("Testing ETH0_MAC_Address...")
    update_network_status_field("network_status/ETH0_MAC_Address", "00:11:22:33:44:55")
    
    print("Testing WiFi_IP_Address...")
    update_network_status_field("network_status/WiFi_IP_Address", "10.0.0.5")
    
    print("\nResulting network_status_state (structured):")
    snapshot = {
        'lan': network_status_state.get('lan', {}),
        'wlan': network_status_state.get('wlan', {}),
        'lte': network_status_state.get('lte', {})
    }
    print(json.dumps(snapshot, indent=2))
    
    # Verify values
    assert snapshot['lan']['eth0']['ip'] == "192.168.1.50"
    assert snapshot['lan']['eth0']['mac'] == "00:11:22:33:44:55"
    assert snapshot['wlan']['ip'] == "10.0.0.5"
    
    print("\nSUCCESS: Network status state updated correctly with individual datapoints.")

except Exception as e:
    print("\nFAILED: {}".format(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)
