# api_server.py - Run on port 8080
import json
import time
import datetime
import random
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler

config_data = {
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
        'current_date': datetime.datetime.now().strftime('%Y-%m-%d'),
        'current_time': datetime.datetime.now().strftime('%H:%M'),
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

class APIHandler(BaseHTTPRequestHandler):
    
    def _set_headers(self, content_type='application/json'):
        self.send_response(200)
        self.send_header('Content-type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
    
    def _safe_write(self, data):
        """Safely write data, handling connection interruptions"""
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, socket.error) as e:
            # Client disconnected, ignore error
            print("Client disconnected: {}".format(e))
    
    def do_GET(self):
        if self.path == '/api/general-configuration':
            try:
                self._set_headers()
                response_data = json.dumps(config_data).encode('utf-8')
                self._safe_write(response_data)
            except Exception as e:
                print("Error processing GET request: {}".format(e))
        else:
            try:
                self.send_response(404)
                self.end_headers()
            except:
                pass  # If client already disconnected, ignore error
    
    def do_PUT(self):
        if self.path == '/api/general-configuration':
            try:
                length = int(self.headers.get('Content-Length', 0))
                if length:
                    data = json.loads(self.rfile.read(length).decode('utf-8'))
                    
                    # Update config
                    for key in data:
                        if key in config_data and isinstance(config_data[key], dict):
                            config_data[key].update(data[key])
                        elif key in config_data:
                            config_data[key] = data[key]
                
                self._set_headers()
                response = json.dumps({
                    'success': True,
                    'message': 'Configuration saved successfully'
                }).encode('utf-8')
                self._safe_write(response)
            except Exception as e:
                try:
                    self.send_response(500)
                    self.end_headers()
                    response = json.dumps({
                        'success': False,
                        'message': 'Error: ' + str(e)
                    }).encode('utf-8')
                    self._safe_write(response)
                except:
                    pass  # If client already disconnected, ignore error
        else:
            try:
                self.send_response(404)
                self.end_headers()
            except:
                pass
    
    def do_POST(self):
        if self.path == '/api/general-configuration/wifi-scan':
            try:
                time.sleep(1)  # Simulate scanning delay
                self._set_headers()
                response = json.dumps({
                    'success': True,
                    'networks': [
                        {'ssid': 'Port_WiFi_5G', 'signal': 4},
                        {'ssid': 'Guest_WiFi', 'signal': 3},
                        {'ssid': 'Crane_Control', 'signal': 2}
                    ]
                }).encode('utf-8')
                self._safe_write(response)
            except Exception as e:
                print("Error in WiFi scan request: {}".format(e))
        
        elif self.path == '/api/general-configuration/time-sync':
            try:
                now = datetime.datetime.now()
                config_data['date_time']['current_date'] = now.strftime('%Y-%m-%d')
                config_data['date_time']['current_time'] = now.strftime('%H:%M')
                
                self._set_headers()
                response = json.dumps({
                    'success': True,
                    'message': 'Time synchronized successfully',
                    'current_date': config_data['date_time']['current_date'],
                    'current_time': config_data['date_time']['current_time']
                }).encode('utf-8')
                self._safe_write(response)
            except Exception as e:
                print("Error in time sync request: {}".format(e))
        else:
            try:
                self.send_response(404)
                self.end_headers()
            except:
                pass
    
    def do_OPTIONS(self):
        try:
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
        except:
            pass  # If client already disconnected, ignore error
    
    def handle(self):
        """Override handle method to catch all exceptions"""
        try:
            BaseHTTPRequestHandler.handle(self)
        except (ConnectionResetError, BrokenPipeError, socket.error):
            # Ignore connection-related errors
            pass
    
    def log_message(self, format, *args):
        # Optional: quiet logging, but can log errors if needed
        pass

def run():
    port = 8080
    server = HTTPServer(('0.0.0.0', port), APIHandler)
    print('API Server running on port ' + str(port))
    print('Endpoints:')
    print('  GET  /api/general-configuration')
    print('  PUT  /api/general-configuration')
    print('  POST /api/general-configuration/wifi-scan')
    print('  POST /api/general-configuration/time-sync')
    print('Press Ctrl+C to stop server')
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down server...')
        server.server_close()
        print('Server stopped.')

if __name__ == '__main__':
    run()