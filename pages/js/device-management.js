// device-management.js - Updated for new backend API
// Supports: Modbus TCP, Modbus RTU, Loadcell devices

// Check if already loaded to prevent duplicate declarations
if (typeof window.deviceManagementLoaded === 'undefined') {
    window.deviceManagementLoaded = true;
    
    (function() {
        'use strict';
        
        // Initialize device-management
        window.initializeDeviceManagement = function() {
            console.log('Device Management page initialized');
            initDeviceManagementApp();
        };

        function initDeviceManagementApp() {
            console.log('Setting up Device Management page functionality');
            
            // Add styles for this page
            addDeviceManagementStyles();
            
            // Initialize the app
            initApp();
            
            // Add debug button
            addDebugButton();
        }

        // Global state - scoped to this IIFE
        let devices = [];
        let groups = [];
        let selectedDeviceId = null;
        let selectedColor = 'blue';
        let selectedGroupId = null;
        let selectedDevicesForAssignment = new Set();
        
        // Fix: Add flag to prevent multiple saves
        let isSaving = false;

        // WebSocket for device status updates
        let deviceWsConnection = null;

        function addDeviceManagementStyles() {
            const style = document.createElement('style');
            style.textContent = `
                /* Add Device Panel - Slides in from right */
                .add-device-panel {
                    position: fixed;
                    right: -400px;
                    top: 0;
                    width: 400px;
                    height: 100vh;
                    background: white;
                    border-left: 1px solid #E2E8F0;
                    box-shadow: -4px 0 20px rgba(0,0,0,0.1);
                    transition: right 0.3s ease;
                    z-index: 1050;
                    overflow-y: auto;
                }
                
                .add-device-panel.active {
                    right: 0;
                }
                
                /* Modal Overlay - Centers modal */
                .modal-overlay {
                    display: none;
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background-color: rgba(0,0,0,0.5);
                    z-index: 1060;
                    align-items: center;
                    justify-content: center;
                    padding: 20px;
                }
                
                .modal-overlay.active {
                    display: flex;
                }
                
                .modal {
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);
                    min-width: 400px;
                    max-width: 90vw;
                    max-height: 90vh;
                    overflow-y: auto;
                    animation: modalSlideIn 0.3s ease;
                }
                
                @keyframes modalSlideIn {
                    from {
                        opacity: 0;
                        transform: translateY(-20px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }
                
                .status-dot {
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    display: inline-block;
                    margin-right: 4px;
                }
                
                .status-online { background-color: #10B981; }
                .status-offline { background-color: #EF4444; }
                .status-warning { background-color: #F59E0B; }
                .status-disabled { background-color: #6B7280; }
                
                .device-type-badge {
                    padding: 4px 12px;
                    border-radius: 6px;
                    font-size: 0.75rem;
                    font-weight: 600;
                }
                
                .type-modbus-tcp {
                    background-color: #DBEAFE;
                    color: #1E40AF;
                }
                
                .type-modbus-rtu {
                    background-color: #D1FAE5;
                    color: #065F46;
                }
                
                .type-loadcell {
                    background-color: #FEF3C7;
                    color: #92400E;
                }
            `;
            
            if (!document.getElementById('device-management-styles')) {
                style.id = 'device-management-styles';
                document.head.appendChild(style);
            }
        }

        function addDebugButton() {
            const debugBtn = document.createElement('button');
            debugBtn.textContent = 'Debug Details Section';
            debugBtn.className = 'fixed bottom-4 right-4 bg-red-500 text-white px-4 py-2 rounded shadow-lg text-sm z-50';
            debugBtn.onclick = debugDetailsSection;
            document.body.appendChild(debugBtn);
        }

        function initApp() {
            // Set up event listeners
            const addDeviceBtn = document.getElementById('addDeviceBtn');
            if (addDeviceBtn) {
                addDeviceBtn.addEventListener('click', openAddDevicePanel);
            }
            
            const addGroupBtn = document.getElementById('addGroupBtn');
            if (addGroupBtn) {
                addGroupBtn.addEventListener('click', openAddGroupModal);
            }
            
            // Close panel/modal buttons
            const closePanelBtn = document.getElementById('closePanelBtn');
            if (closePanelBtn) {
                closePanelBtn.addEventListener('click', closeAddDevicePanel);
            }
            
            // Device type selector
            const deviceTypeButtons = document.querySelectorAll('[data-device-type]');
            deviceTypeButtons.forEach(function(btn) {
                btn.addEventListener('click', function() {
                    selectDeviceType(this.getAttribute('data-device-type'));
                });
            });
            
            // Protocol selector (for Modbus)
            const protocolButtons = document.querySelectorAll('[data-protocol]');
            protocolButtons.forEach(function(btn) {
                btn.addEventListener('click', function() {
                    selectProtocol(this.getAttribute('data-protocol'));
                });
            });
            
            // Save device button
            const saveDeviceBtn = document.getElementById('saveDeviceBtn');
            if (saveDeviceBtn) {
                saveDeviceBtn.addEventListener('click', saveDevice);
            }
            
            // Save group button
            const saveGroupBtn = document.getElementById('saveGroupBtn');
            if (saveGroupBtn) {
                saveGroupBtn.addEventListener('click', saveGroup);
            }
            
            // Color picker
            const colorOptions = document.querySelectorAll('.color-option');
            colorOptions.forEach(function(option) {
                option.addEventListener('click', function() {
                    selectColor(this.getAttribute('data-color'));
                });
            });
            
            // Load initial data
            loadDevices();
            loadGroups();
            
            // Initialize WebSocket
            initializeDeviceWebSocket();
            
            // Expose functions to global scope for HTML onclick handlers
            window.deviceManagement = {
                showDeviceDetails: showDeviceDetails,
                testDevice: testDevice,
                disableDevice: disableDevice,
                deleteDevice: deleteDevice,
                editDevice: editDevice,
                openAssignDevicesModal: openAssignDevicesModal,
                toggleDeviceForAssignment: toggleDeviceForAssignment,
                saveDeviceAssignments: saveDeviceAssignments,
                closeModal: closeModal
            };
        }

        // Load devices from API
        async function loadDevices() {
            try {
                const response = await fetch('/api/devices');
                if (!response.ok) throw new Error('Failed to load devices');
                
                const data = await response.json();
                devices = data.devices || [];
                console.log('Loaded devices:', devices);
                
                renderDeviceTable();
                updateDeviceCount();
            } catch (error) {
                console.error('Error loading devices:', error);
                showNotification('Failed to load devices', 'error');
            }
        }

        // Load groups from API
        async function loadGroups() {
            try {
                const response = await fetch('/api/groups');
                if (!response.ok) throw new Error('Failed to load groups');
                
                const data = await response.json();
                groups = data.groups || [];
                
                // Calculate device counts for each group
                groups.forEach(function(group) {
                    group.device_count = devices.filter(function(d) { 
                        return d.group === group.name; 
                    }).length;
                });
                
                console.log('Loaded groups:', groups);
                renderGroups();
                updateGroupSelects();
            } catch (error) {
                console.error('Error loading groups:', error);
                showNotification('Failed to load groups', 'error');
            }
        }

        function renderDeviceTable() {
            const tbody = document.getElementById('devicesTableBody');
            if (!tbody) return;
            
            if (devices.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center py-8 text-slate-500">No devices found. Click "Add Device" to get started.</td></tr>';
                return;
            }
            
            tbody.innerHTML = '';
            
            devices.forEach(function(device) {
                const row = document.createElement('tr');
                row.id = 'device-' + device.id;
                row.className = 'border-b border-slate-200 hover:bg-slate-50 cursor-pointer';
                row.onclick = function() { showDeviceDetails(device.id); };
                
                // Determine device type badge class
                let typeClass = 'type-modbus-tcp';
                let typeDisplay = device.type;
                
                if (device.protocol === 'modbus-tcp') {
                    typeClass = 'type-modbus-tcp';
                    typeDisplay = 'Modbus TCP';
                } else if (device.protocol === 'modbus-rtu') {
                    typeClass = 'type-modbus-rtu';
                    typeDisplay = 'Modbus RTU';
                } else if (device.protocol === 'loadcell') {
                    typeClass = 'type-loadcell';
                    typeDisplay = 'Loadcell';
                }
                
                // Status class
                let statusClass = 'status-online';
                if (device.status === 'Offline') statusClass = 'status-offline';
                if (device.status === 'Warning') statusClass = 'status-warning';
                if (device.status === 'Disabled') statusClass = 'status-disabled';
                
                row.innerHTML = 
                    '<td class="px-6 py-4">' +
                        '<div class="font-medium text-slate-900">' + device.name + '</div>' +
                        '<div class="text-xs text-slate-500">ID: ' + device.id + '</div>' +
                    '</td>' +
                    '<td class="px-6 py-4">' +
                        '<span class="device-type-badge ' + typeClass + '">' + typeDisplay + '</span>' +
                    '</td>' +
                    '<td class="px-6 py-4 text-sm text-slate-600">' + (device.address || '-') + '</td>' +
                    '<td class="px-6 py-4">' +
                        '<div class="status-indicator">' +
                            '<span class="status-dot ' + statusClass + '"></span>' +
                            '<span class="text-sm text-slate-700">' + (device.status || 'Unknown') + '</span>' +
                        '</div>' +
                    '</td>' +
                    '<td class="px-6 py-4 text-sm text-slate-600">' + (device.lastPoll || 'Never') + '</td>' +
                    '<td class="px-6 py-4 text-sm text-slate-600">' + (device.group || 'None') + '</td>';
                
                tbody.appendChild(row);
            });
        }

        function updateDeviceCount() {
            const countElement = document.getElementById('deviceCount');
            if (countElement) {
                countElement.textContent = devices.length;
            }
        }

        // Initialize WebSocket for device status updates
        function initializeDeviceWebSocket() {
            if (deviceWsConnection) {
                try {
                    deviceWsConnection.close();
                } catch (e) {
                    console.log('Existing device WebSocket already closed');
                }
                deviceWsConnection = null;
            }
            
            const wsUrl = 'ws://' + window.location.host + '/ws/devices';
            console.log('Connecting Device WebSocket:', wsUrl);
            
            deviceWsConnection = new WebSocket(wsUrl);
            
            deviceWsConnection.onopen = function() {
                console.log('Device WebSocket connected');
            };
            
            deviceWsConnection.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    handleDeviceWebSocketMessage(data);
                } catch (e) {
                    console.error('Device WebSocket parse error:', e);
                }
            };
            
            deviceWsConnection.onclose = function() {
                console.log('Device WebSocket disconnected');
                // Reconnect after 3 seconds
                setTimeout(initializeDeviceWebSocket, 3000);
            };
            
            deviceWsConnection.onerror = function(error) {
                console.error('Device WebSocket error:', error);
            };
        }

        function handleDeviceWebSocketMessage(data) {
            if (data.type === 'device_status') {
                // Update device status in table
                const deviceRow = document.getElementById('device-' + data.device_id);
                if (deviceRow) {
                    const statusCell = deviceRow.querySelector('td:nth-child(4)');
                    if (statusCell) {
                        let statusClass = 'status-online';
                        if (data.status === 'Offline') statusClass = 'status-offline';
                        if (data.status === 'Warning') statusClass = 'status-warning';
                        if (data.status === 'Disabled') statusClass = 'status-disabled';
                        
                        statusCell.innerHTML = '<div class="status-indicator">' +
                            '<span class="status-dot ' + statusClass + '"></span>' +
                            '<span class="text-sm text-slate-700">' + data.status + '</span>' +
                            '</div>';
                    }
                    
                    const lastPollCell = deviceRow.querySelector('td:nth-child(5)');
                    if (lastPollCell) {
                        lastPollCell.innerHTML = '<div class="text-sm">' + data.last_poll + '</div>';
                    }
                }
                
                // Update device in memory
                const deviceIndex = devices.findIndex(function(d) { return d.id === data.device_id; });
                if (deviceIndex !== -1) {
                    devices[deviceIndex].status = data.status;
                    devices[deviceIndex].lastPoll = data.last_poll;
                }
                
                // Update details panel if this device is selected
                if (selectedDeviceId === data.device_id) {
                    const deviceStatusElement = document.getElementById('deviceStatus');
                    const lastResponseElement = document.getElementById('lastResponse');
                    if (deviceStatusElement) deviceStatusElement.textContent = data.status;
                    if (lastResponseElement) lastResponseElement.textContent = data.last_poll;
                }
            }
        }

        function renderGroups() {
            const container = document.getElementById('groupsContainer');
            if (!container) return;
            
            container.innerHTML = '';
            
            groups.forEach(function(group) {
                const groupElement = document.createElement('div');
                groupElement.className = 'border border-slate-200 rounded-lg p-4';
                groupElement.innerHTML = '<div class="flex items-center justify-between mb-2">' +
                    '<h4 class="font-medium text-slate-900">' + group.name + '</h4>' +
                    '<span class="w-3 h-3 rounded-full bg-' + group.color + '-500"></span>' +
                    '</div>' +
                    '<div class="text-xs text-slate-500 mb-3">' + (group.device_count || 0) + ' devices</div>' +
                    '<button class="text-xs text-primary hover:text-primaryHover" onclick="window.deviceManagement.openAssignDevicesModal(' + group.id + ')">' +
                    'Assign Devices' +
                    '</button>';
                container.appendChild(groupElement);
            });
        }

        // Debug function
        function debugDetailsSection() {
            const detailsSection = document.getElementById('section-details');
            console.log('=== DEBUG section-details ===');
            console.log('Element exists:', !!detailsSection);
            if (detailsSection) {
                console.log('Current display style:', detailsSection.style.display);
                console.log('Current classes:', detailsSection.className);
                console.log('Parent element:', detailsSection.parentElement);
            }
            
            // Check if there's a modal overlay blocking it
            const modalOverlays = document.querySelectorAll('.modal-overlay');
            console.log('Modal overlays found:', modalOverlays.length);
            
            // Check body classes
            console.log('Body has modal-open class:', document.body.classList.contains('modal-open'));
        }

        async function showDeviceDetails(deviceId) {
            try {
                console.log('Loading details for device:', deviceId);
                
                const response = await fetch('/api/devices/' + deviceId + '/details');
                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error('HTTP ' + response.status + ': ' + errorText);
                }
                
                const device = await response.json();
                console.log('Device data received:', device);
                
                selectedDeviceId = deviceId;
                
                // Update the device information
                const selectedDeviceName = document.getElementById('selectedDeviceName');
                const deviceStatus = document.getElementById('deviceStatus');
                const lastResponse = document.getElementById('lastResponse');
                
                if (selectedDeviceName) {
                    selectedDeviceName.textContent = 'Selected: ' + device.name;
                }
                
                if (deviceStatus) {
                    deviceStatus.textContent = device.status || '-';
                }
                
                if (lastResponse) {
                    lastResponse.textContent = device.lastPoll || '-';
                }
                
                // Display configuration details
                const deviceConfigDisplay = document.getElementById('deviceConfigDisplay');
                if (deviceConfigDisplay) {
                    let configHtml = '<div class="space-y-2 text-sm">';
                    
                    // Add basic device info
                    configHtml += '<div class="grid grid-cols-2 gap-4 mb-4">';
                    configHtml += '<div><strong class="text-slate-700">Device Type:</strong> ' + (device.type || '-') + '</div>';
                    configHtml += '<div><strong class="text-slate-700">Protocol:</strong> ' + (device.protocol || '-') + '</div>';
                    configHtml += '<div><strong class="text-slate-700">Group:</strong> ' + (device.group || 'None') + '</div>';
                    configHtml += '<div><strong class="text-slate-700">Enabled:</strong> ' + (device.enabled ? 'Yes' : 'No') + '</div>';
                    configHtml += '</div>';
                    
                    // Add configuration based on protocol
                    configHtml += '<div class="border-t pt-4">';
                    configHtml += '<h4 class="text-sm font-medium text-slate-700 mb-2">Configuration Details:</h4>';
                    
                    if (device.protocol === 'modbus-tcp' && device.config) {
                        configHtml += '<div class="grid grid-cols-2 gap-2">';
                        configHtml += '<div><strong class="text-slate-600">IP Address:</strong></div><div>' + (device.config.ip_address || '-') + '</div>';
                        configHtml += '<div><strong class="text-slate-600">Port:</strong></div><div>' + (device.config.port || '-') + '</div>';
                        configHtml += '<div><strong class="text-slate-600">Slave ID:</strong></div><div>' + (device.config.slave_id || '-') + '</div>';
                        configHtml += '<div><strong class="text-slate-600">Timeout:</strong></div><div>' + (device.config.timeout_ms || '1000') + ' ms</div>';
                        configHtml += '<div><strong class="text-slate-600">Retry Count:</strong></div><div>' + (device.config.retry_count || '3') + '</div>';
                        configHtml += '<div><strong class="text-slate-600">Polling Interval:</strong></div><div>' + (device.config.polling_interval_ms || '100') + ' ms</div>';
                        configHtml += '</div>';
                    } else if (device.protocol === 'modbus-rtu' && device.config) {
                        configHtml += '<div class="grid grid-cols-2 gap-2">';
                        configHtml += '<div><strong class="text-slate-600">Serial Port:</strong></div><div>' + (device.config.serial_port || '-') + '</div>';
                        configHtml += '<div><strong class="text-slate-600">Baud Rate:</strong></div><div>' + (device.config.baud_rate || '-') + '</div>';
                        configHtml += '<div><strong class="text-slate-600">Parity:</strong></div><div>' + (device.config.parity || '-') + '</div>';
                        configHtml += '<div><strong class="text-slate-600">Data Bits:</strong></div><div>' + (device.config.data_bits || '-') + '</div>';
                        configHtml += '<div><strong class="text-slate-600">Stop Bits:</strong></div><div>' + (device.config.stop_bits || '-') + '</div>';
                        configHtml += '<div><strong class="text-slate-600">Slave ID:</strong></div><div>' + (device.config.slave_id || '-') + '</div>';
                        configHtml += '</div>';
                    } else if (device.protocol === 'loadcell' && device.config) {
                        configHtml += '<div class="grid grid-cols-2 gap-2">';
                        configHtml += '<div><strong class="text-slate-600">Device Path:</strong></div><div>' + (device.config.device_path || '-') + '</div>';
                        configHtml += '<div><strong class="text-slate-600">Channel:</strong></div><div>' + (device.config.channel || '0') + '</div>';
                        
                        if (device.config.calibration) {
                            configHtml += '<div class="col-span-2 mt-2 pt-2 border-t"><strong>Calibration:</strong></div>';
                            configHtml += '<div><strong class="text-slate-600">Capacity:</strong></div><div>' + (device.config.calibration.capacity || '-') + ' ' + (device.config.calibration.unit || 'g') + '</div>';
                            configHtml += '<div><strong class="text-slate-600">Tare Offset:</strong></div><div>' + (device.config.calibration.tare_offset || '0') + '</div>';
                            configHtml += '<div><strong class="text-slate-600">Known Weight:</strong></div><div>' + (device.config.calibration.known_weight || '-') + '</div>';
                        }
                        
                        configHtml += '</div>';
                        configHtml += '<div class="mt-2 p-2 bg-blue-50 rounded text-xs text-blue-700">';
                        configHtml += '<i class="fa-solid fa-info-circle mr-1"></i> Auto-created datapoints: <strong>load</strong> and <strong>' + (device.config.calibration?.capacity_name || 'capacity') + '</strong>';
                        configHtml += '</div>';
                    }
                    
                    configHtml += '</div>';
                    configHtml += '</div>';
                    
                    deviceConfigDisplay.innerHTML = configHtml;
                }
                
                // Show details section
                showSection('details');
                
            } catch (error) {
                console.error('Error loading device details:', error);
                showNotification('Failed to load device details: ' + error.message, 'error');
            }
        }

        function showSection(sectionName) {
            // Hide all sections
            const sections = ['overview', 'details'];
            sections.forEach(function(name) {
                const section = document.getElementById('section-' + name);
                if (section) {
                    section.style.display = 'none';
                }
            });
            
            // Show requested section
            const targetSection = document.getElementById('section-' + sectionName);
            if (targetSection) {
                targetSection.style.display = 'block';
            }
        }

        async function testDevice(deviceId) {
            try {
                const response = await fetch('/api/devices/' + deviceId + '/test', {
                    method: 'POST'
                });
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    showNotification('Device test successful!', 'success');
                } else {
                    showNotification('Device test failed: ' + (result.message || 'Unknown error'), 'error');
                }
            } catch (error) {
                console.error('Error testing device:', error);
                showNotification('Error testing device: ' + error.message, 'error');
            }
        }

        async function disableDevice(deviceId) {
            try {
                const device = devices.find(function(d) { return d.id === deviceId; });
                if (!device) return;
                
                const newEnabledState = !device.enabled;
                
                const response = await fetch('/api/devices/' + deviceId + '/disable', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: newEnabledState })
                });
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    showNotification('Device ' + (newEnabledState ? 'enabled' : 'disabled') + ' successfully', 'success');
                    loadDevices();
                } else {
                    showNotification('Failed to update device: ' + (result.message || 'Unknown error'), 'error');
                }
            } catch (error) {
                console.error('Error updating device:', error);
                showNotification('Error updating device: ' + error.message, 'error');
            }
        }

        async function deleteDevice(deviceId) {
            if (!confirm('Are you sure you want to delete this device? This action cannot be undone.')) {
                return;
            }
            
            try {
                const response = await fetch('/api/devices/' + deviceId, {
                    method: 'DELETE'
                });
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    showNotification('Device deleted successfully', 'success');
                    loadDevices();
                    showSection('overview');
                } else {
                    showNotification('Failed to delete device: ' + (result.message || 'Unknown error'), 'error');
                }
            } catch (error) {
                console.error('Error deleting device:', error);
                showNotification('Error deleting device: ' + error.message, 'error');
            }
        }

        function editDevice(deviceId) {
            // Load device data and open panel for editing
            const device = devices.find(function(d) { return d.id === deviceId; });
            if (!device) return;
            
            openAddDevicePanel(device);
        }

        function openAddDevicePanel(deviceToEdit = null) {
            const panel = document.getElementById('addDevicePanel');
            if (!panel) return;
            
            // Reset form
            document.getElementById('deviceForm').reset();
            selectedDeviceId = deviceToEdit ? deviceToEdit.id : null;
            
            // Update panel title
            const panelTitle = document.getElementById('addDevicePanelTitle');
            if (panelTitle) {
                panelTitle.textContent = deviceToEdit ? 'Edit Device' : 'Add New Device';
            }
            
            // If editing, populate form
            if (deviceToEdit) {
                document.getElementById('deviceName').value = deviceToEdit.name || '';
                
                // Select device type and protocol
                if (deviceToEdit.protocol === 'modbus-tcp') {
                    selectDeviceType('modbus');
                    selectProtocol('modbus-tcp');
                } else if (deviceToEdit.protocol === 'modbus-rtu') {
                    selectDeviceType('modbus');
                    selectProtocol('modbus-rtu');
                } else if (deviceToEdit.protocol === 'loadcell') {
                    selectDeviceType('loadcell');
                }
                
                // Populate config fields based on protocol
                if (deviceToEdit.config) {
                    Object.keys(deviceToEdit.config).forEach(function(key) {
                        const input = document.getElementById(key);
                        if (input) {
                            input.value = deviceToEdit.config[key];
                        }
                    });
                }
                
                // Set group
                const groupSelect = document.getElementById('deviceGroup');
                if (groupSelect && deviceToEdit.group) {
                    groupSelect.value = deviceToEdit.group;
                }
            }
            
            panel.classList.add('active');
        }

        function closeAddDevicePanel() {
            const panel = document.getElementById('addDevicePanel');
            if (panel) {
                panel.classList.remove('active');
            }
            selectedDeviceId = null;
        }

        function selectDeviceType(type) {
            // Update button states
            document.querySelectorAll('[data-device-type]').forEach(function(btn) {
                if (btn.getAttribute('data-device-type') === type) {
                    btn.classList.add('bg-primary', 'text-white');
                    btn.classList.remove('bg-white', 'text-slate-700');
                } else {
                    btn.classList.remove('bg-primary', 'text-white');
                    btn.classList.add('bg-white', 'text-slate-700');
                }
            });
            
            // Show/hide protocol selection
            const protocolSelection = document.getElementById('protocolSelection');
            const deviceConfigSection = document.getElementById('deviceConfigSection');
            
            if (type === 'modbus') {
                if (protocolSelection) protocolSelection.style.display = 'block';
                if (deviceConfigSection) deviceConfigSection.style.display = 'none';
            } else {
                if (protocolSelection) protocolSelection.style.display = 'none';
                selectProtocol(type); // Auto-select protocol for non-modbus types
            }
        }

        function selectProtocol(protocol) {
            // Update button states (for modbus)
            document.querySelectorAll('[data-protocol]').forEach(function(btn) {
                if (btn.getAttribute('data-protocol') === protocol) {
                    btn.classList.add('bg-primary', 'text-white');
                    btn.classList.remove('bg-white', 'text-slate-700');
                } else {
                    btn.classList.remove('bg-primary', 'text-white');
                    btn.classList.add('bg-white', 'text-slate-700');
                }
            });
            
            // Show appropriate config form
            const configSections = document.querySelectorAll('[data-config-type]');
            configSections.forEach(function(section) {
                section.style.display = 'none';
            });
            
            const targetSection = document.querySelector('[data-config-type="' + protocol + '"]');
            if (targetSection) {
                targetSection.style.display = 'block';
            }
            
            const deviceConfigSection = document.getElementById('deviceConfigSection');
            if (deviceConfigSection) {
                deviceConfigSection.style.display = 'block';
            }
        }

        async function saveDevice() {
            if (isSaving) return;
            isSaving = true;
            
            try {
                const deviceName = document.getElementById('deviceName').value;
                if (!deviceName) {
                    showNotification('Please enter a device name', 'error');
                    isSaving = false;
                    return;
                }
                
                // Determine selected protocol
                let protocol = null;
                const activeProtocolBtn = document.querySelector('[data-protocol].bg-primary');
                if (activeProtocolBtn) {
                    protocol = activeProtocolBtn.getAttribute('data-protocol');
                }
                
                // If no protocol button selected, check device type
                const activeTypeBtn = document.querySelector('[data-device-type].bg-primary');
                if (!protocol && activeTypeBtn) {
                    const deviceType = activeTypeBtn.getAttribute('data-device-type');
                    if (deviceType === 'loadcell') {
                        protocol = 'loadcell';
                    }
                }
                
                if (!protocol) {
                    showNotification('Please select a device type and protocol', 'error');
                    isSaving = false;
                    return;
                }
                
                // Determine device type for API
                let type = 'modbus';
                if (protocol === 'loadcell') {
                    type = 'loadcell';
                }
                
                // Get group
                const groupSelect = document.getElementById('deviceGroup');
                const group = groupSelect ? groupSelect.value : '';
                
                // Build config object based on protocol
                const config = {};
                
                if (protocol === 'modbus-tcp') {
                    config.ip_address = document.getElementById('ip_address')?.value || '';
                    config.port = parseInt(document.getElementById('port')?.value || '502');
                    config.slave_id = parseInt(document.getElementById('tcp_slave_id')?.value || '1');
                    config.timeout_ms = parseInt(document.getElementById('tcp_timeout')?.value || '1000');
                    config.retry_count = parseInt(document.getElementById('tcp_retry')?.value || '3');
                    config.polling_interval_ms = parseInt(document.getElementById('tcp_polling')?.value || '100');
                } else if (protocol === 'modbus-rtu') {
                    config.serial_port = document.getElementById('serial_port')?.value || '/dev/ttymxc2';
                    config.baud_rate = parseInt(document.getElementById('baud_rate')?.value || '9600');
                    config.parity = document.getElementById('parity')?.value || 'N';
                    config.data_bits = parseInt(document.getElementById('data_bits')?.value || '8');
                    config.stop_bits = parseInt(document.getElementById('stop_bits')?.value || '1');
                    config.slave_id = parseInt(document.getElementById('rtu_slave_id')?.value || '1');
                    config.timeout_ms = parseInt(document.getElementById('rtu_timeout')?.value || '1000');
                    config.retry_count = parseInt(document.getElementById('rtu_retry')?.value || '3');
                } else if (protocol === 'loadcell') {
                    config.device_path = document.getElementById('device_path')?.value || '/dev/spidev0.0';
                    config.channel = parseInt(document.getElementById('channel')?.value || '0');
                    config.capacity = parseFloat(document.getElementById('capacity')?.value || '40000');
                    config.capacity_name = document.getElementById('capacity_name')?.value || 'capacity';
                }
                
                const deviceData = {
                    type: type,
                    name: deviceName,
                    protocol: protocol,
                    group: group,
                    config: config
                };
                
                let response;
                if (selectedDeviceId) {
                    // Update existing device
                    response = await fetch('/api/devices/' + selectedDeviceId, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(deviceData)
                    });
                } else {
                    // Create new device
                    response = await fetch('/api/devices', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(deviceData)
                    });
                }
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    showNotification(selectedDeviceId ? 'Device updated successfully' : 'Device added successfully', 'success');
                    closeAddDevicePanel();
                    loadDevices();
                } else {
                    showNotification('Failed to save device: ' + (result.message || 'Unknown error'), 'error');
                }
            } catch (error) {
                console.error('Error saving device:', error);
                showNotification('Error saving device: ' + error.message, 'error');
            } finally {
                isSaving = false;
            }
        }

        function openAddGroupModal() {
            const modal = document.getElementById('addGroupModal');
            if (modal) {
                modal.classList.add('active');
            }
        }

        function closeModal(modalId) {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.classList.remove('active');
            }
        }

        function selectColor(color) {
            selectedColor = color;
            
            // Update color options visual state
            document.querySelectorAll('.color-option').forEach(function(option) {
                if (option.getAttribute('data-color') === color) {
                    option.classList.add('ring-2', 'ring-primary', 'ring-offset-2');
                } else {
                    option.classList.remove('ring-2', 'ring-primary', 'ring-offset-2');
                }
            });
        }

        async function saveGroup() {
            try {
                const groupName = document.getElementById('groupName').value;
                const groupDescription = document.getElementById('groupDescription').value;
                
                if (!groupName) {
                    showNotification('Please enter a group name', 'error');
                    return;
                }
                
                const response = await fetch('/api/groups', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: groupName,
                        description: groupDescription,
                        color: selectedColor
                    })
                });
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    showNotification('Group created successfully', 'success');
                    closeModal('addGroupModal');
                    loadGroups();
                    
                    // Reset form
                    document.getElementById('groupName').value = '';
                    document.getElementById('groupDescription').value = '';
                    selectedColor = 'blue';
                } else {
                    showNotification('Failed to create group: ' + (result.message || 'Unknown error'), 'error');
                }
            } catch (error) {
                console.error('Error creating group:', error);
                showNotification('Error creating group: ' + error.message, 'error');
            }
        }

        function updateGroupSelects() {
            const selects = document.querySelectorAll('select[id="deviceGroup"]');
            selects.forEach(function(select) {
                const currentValue = select.value;
                select.innerHTML = '<option value="">No Group</option>';
                
                groups.forEach(function(group) {
                    const option = document.createElement('option');
                    option.value = group.name;
                    option.textContent = group.name;
                    if (group.name === currentValue) {
                        option.selected = true;
                    }
                    select.appendChild(option);
                });
            });
        }

        function openAssignDevicesModal(groupId) {
            selectedGroupId = groupId;
            selectedDevicesForAssignment.clear();
            
            const modal = document.getElementById('assignDevicesModal');
            const deviceList = document.getElementById('assignDevicesList');
            
            if (!modal || !deviceList) return;
            
            // Populate device list
            deviceList.innerHTML = '';
            
            devices.forEach(function(device) {
                const item = document.createElement('div');
                item.className = 'flex items-center p-2 hover:bg-slate-50 rounded';
                item.innerHTML = 
                    '<input type="checkbox" id="assign-device-' + device.id + '" class="mr-2" onchange="window.deviceManagement.toggleDeviceForAssignment(\'' + device.id + '\')">' +
                    '<label for="assign-device-' + device.id + '" class="flex-1 cursor-pointer">' + device.name + '</label>';
                deviceList.appendChild(item);
            });
            
            modal.classList.add('active');
        }

        function toggleDeviceForAssignment(deviceId) {
            if (selectedDevicesForAssignment.has(deviceId)) {
                selectedDevicesForAssignment.delete(deviceId);
            } else {
                selectedDevicesForAssignment.add(deviceId);
            }
        }

        async function saveDeviceAssignments() {
            try {
                const response = await fetch('/api/groups/' + selectedGroupId + '/assign-devices', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        device_ids: Array.from(selectedDevicesForAssignment)
                    })
                });
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    showNotification('Devices assigned successfully', 'success');
                    closeModal('assignDevicesModal');
                    loadDevices();
                    loadGroups();
                } else {
                    showNotification('Failed to assign devices: ' + (result.message || 'Unknown error'), 'error');
                }
            } catch (error) {
                console.error('Error assigning devices:', error);
                showNotification('Error assigning devices: ' + error.message, 'error');
            }
        }

        function showNotification(message, type = 'info', duration = 3000) {
            const notification = document.createElement('div');
            notification.className = 'fixed top-4 right-4 z-50 max-w-sm';
            
            let bgColor = 'bg-blue-500';
            let icon = 'fa-info-circle';
            
            switch (type) {
                case 'success':
                    bgColor = 'bg-green-500';
                    icon = 'fa-check-circle';
                    break;
                case 'error':
                    bgColor = 'bg-red-500';
                    icon = 'fa-exclamation-circle';
                    break;
                case 'warning':
                    bgColor = 'bg-yellow-500';
                    icon = 'fa-exclamation-triangle';
                    break;
            }
            
            notification.innerHTML = 
                '<div class="rounded-lg shadow-lg ' + bgColor + ' text-white p-4 flex items-start justify-between">' +
                    '<div class="flex items-center">' +
                        '<i class="fa-solid ' + icon + ' mr-3"></i>' +
                        '<div class="text-sm font-medium">' + message + '</div>' +
                    '</div>' +
                    '<button class="ml-4 text-white hover:text-gray-200" onclick="this.parentElement.parentElement.remove()">' +
                        '<i class="fa-solid fa-times"></i>' +
                    '</button>' +
                '</div>';
            
            document.body.appendChild(notification);
            
            setTimeout(function() {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, duration);
        }

    })();
}