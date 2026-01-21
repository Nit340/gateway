// device-management.js - Complete fixed version with IIFE and reload protection

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
                
                /* Protocol config sections */
                .protocol-config {
                    display: none;
                }
                
                .protocol-config.active {
                    display: block;
                }
                
                /* Action dropdowns */
                .action-dropdown {
                    position: relative;
                    display: inline-block;
                }
                
                .action-dropdown-content {
                    display: none;
                    position: absolute;
                    right: 0;
                    background-color: white;
                    min-width: 160px;
                    box-shadow: 0 8px 16px rgba(0,0,0,0.1);
                    z-index: 100;
                    border: 1px solid #E2E8F0;
                    border-radius: 6px;
                    padding: 4px 0;
                    top: 100%;
                    margin-top: 2px;
                }
                
                .action-dropdown-content.show {
                    display: block;
                }
                
                .action-dropdown-content a {
                    color: #475569;
                    padding: 8px 16px;
                    text-decoration: none;
                    display: block;
                    font-size: 13px;
                    transition: background-color 0.2s;
                }
                
                .action-dropdown-content a:hover {
                    background-color: #F8FAFC;
                    color: #2563EB;
                }
                
                /* Drag and drop styles */
                #dropArea.dragover {
                    border-color: #2563EB;
                    background-color: #EFF6FF;
                }
                
                #dropArea.dragover i {
                    color: #2563EB;
                }
                
                .hidden {
                    display: none !important;
                }
                
                /* Notification styles */
                .notification-toast {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    z-index: 2000;
                    padding: 12px 16px;
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    animation: slideIn 0.3s ease;
                }
                
                .notification-toast.fade-out {
                    opacity: 0;
                    transform: translateX(100%);
                    transition: all 0.3s ease;
                }
                
                @keyframes slideIn {
                    from {
                        opacity: 0;
                        transform: translateX(100%);
                    }
                    to {
                        opacity: 1;
                        transform: translateX(0);
                    }
                }
                
                /* Responsive adjustments */
                @media (max-width: 768px) {
                    .add-device-panel {
                        width: 100%;
                        right: -100%;
                    }
                    
                    .modal {
                        min-width: 95%;
                        margin: 10px;
                    }
                }
                
                /* Prevent body scroll when modal is open */
                body.modal-open {
                    overflow: hidden;
                }

                /* Action button styles */
                .action-btn {
                    display: inline-flex;
                    align-items: center;
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-size: 13px;
                    cursor: pointer;
                    transition: all 0.2s;
                    border: none;
                    background: none;
                }
                
                .action-btn:hover {
                    background-color: #f8fafc;
                }
                
                .action-btn i {
                    margin-right: 4px;
                    font-size: 12px;
                }
                
                .action-btn.edit { color: #3b82f6; }
                .action-btn.view { color: #10b981; }
                .action-btn.duplicate { color: #8b5cf6; }
                .action-btn.disable { color: #f59e0b; }
                .action-btn.delete { color: #ef4444; }
                
                /* Status indicator styles */
                .status-indicator {
                    display: inline-flex;
                    align-items: center;
                    gap: 4px;
                }
                
                .status-dot {
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    display: inline-block;
                }
                
                .status-online { background-color: #10b981; }
                .status-offline { background-color: #ef4444; }
                .status-warning { background-color: #f59e0b; }
                .status-disabled { background-color: #6b7280; }
            `;
            document.head.appendChild(style);
        }

        async function initApp() {
            try {
                // Ensure all modals are closed on init
                closeAllModals();
                
                // Hide details section by default
                const detailsSection = document.getElementById('section-details');
                if (detailsSection) {
                    detailsSection.style.display = 'none';
                }
                
                // Load devices and groups from API
                await loadDevices();
                await loadGroups();
                
                renderDevicesTable();
                renderGroups();
                setupEventListeners();
                initGroupModal();
                initializeDeviceWebSocket();
                
            } catch (error) {
                console.error('Error initializing app:', error);
                showNotification('Failed to load device data', 'error');
            }
        }

        function closeAllModals() {
            // Close Add Device Panel
            const addDevicePanel = document.getElementById('addDevicePanel');
            if (addDevicePanel) {
                addDevicePanel.classList.remove('active');
            }
            
            // Close all modal overlays
            document.querySelectorAll('.modal-overlay').forEach(function(modal) {
                modal.classList.remove('active');
            });
            
            // Close all dropdowns
            closeAllDropdowns();
            
            // Enable body scroll
            document.body.classList.remove('modal-open');
        }

        function setupClickOutsideListeners() {
            document.addEventListener('click', function(event) {
                // Close dropdowns when clicking outside
                const dropdowns = document.querySelectorAll('.action-dropdown-content.show');
                dropdowns.forEach(function(dropdown) {
                    if (!dropdown.closest('.action-dropdown').contains(event.target)) {
                        dropdown.classList.remove('show');
                    }
                });
                
                // Close modals when clicking on overlay
                const modals = document.querySelectorAll('.modal-overlay.active');
                modals.forEach(function(modal) {
                    if (event.target === modal) {
                        modal.classList.remove('active');
                        document.body.classList.remove('modal-open');
                    }
                });
            });
        }

        function setupEscapeKeyListener() {
            document.addEventListener('keydown', function(event) {
                if (event.key === 'Escape') {
                    closeAllModals();
                    closeAllDropdowns();
                }
            });
        }

        async function loadDevices() {
            try {
                const response = await fetch('/api/device-management/devices');
                if (!response.ok) throw new Error('HTTP ' + response.status);
                
                const data = await response.json();
                devices = data.devices || [];
                console.log('Loaded devices:', devices.length);
                
            } catch (error) {
                console.error('Error loading devices:', error);
                devices = [];
            }
        }

        async function loadGroups() {
            try {
                const response = await fetch('/api/device-management/groups');
                if (!response.ok) throw new Error('HTTP ' + response.status);
                
                const data = await response.json();
                groups = data.groups || [];
                console.log('Loaded groups:', groups.length);
                
                // Update group filter dropdown
                const groupFilter = document.getElementById('groupFilter');
                if (groupFilter) {
                    groupFilter.innerHTML = '<option value="All Groups">All Groups</option>';
                    groups.forEach(function(group) {
                        const option = document.createElement('option');
                        option.value = group.name;
                        option.textContent = group.name;
                        groupFilter.appendChild(option);
                    });
                }
                
                // Update device group select
                const deviceGroupSelect = document.getElementById('deviceGroupSelect');
                if (deviceGroupSelect) {
                    deviceGroupSelect.innerHTML = '<option value="None">None</option>';
                    groups.forEach(function(group) {
                        const option = document.createElement('option');
                        option.value = group.name;
                        option.textContent = group.name;
                        deviceGroupSelect.appendChild(option);
                    });
                }
                
            } catch (error) {
                console.error('Error loading groups:', error);
                groups = [];
            }
        }

        function initializeDeviceWebSocket() {
            // Close existing connection if any
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
                    devices[deviceIndex].details.status = data.status;
                    devices[deviceIndex].details.lastResponse = data.last_poll;
                }
                
                // Update details panel if this device is selected
                if (selectedDeviceId === data.device_id) {
                    const device = devices.find(function(d) { return d.id === data.device_id; });
                    if (device) {
                        const deviceStatusElement = document.getElementById('deviceStatus');
                        const lastResponseElement = document.getElementById('lastResponse');
                        if (deviceStatusElement) deviceStatusElement.textContent = device.details.status;
                        if (lastResponseElement) lastResponseElement.textContent = device.details.lastResponse;
                    }
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
                    '<div class="text-xs text-slate-500 mb-3">' + group.device_count + ' devices</div>' +
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
        
        const response = await fetch('/api/device-management/devices/' + deviceId + '/details');
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
            lastResponse.textContent = device.last_response || '-';
        }
        
        // Display configuration details
        const deviceConfigDisplay = document.getElementById('deviceConfigDisplay');
        if (deviceConfigDisplay) {
            let configHtml = '<div class="space-y-2 text-sm">';
            
            // Add basic device info
            configHtml += '<div class="grid grid-cols-2 gap-4 mb-4">';
            configHtml += '<div><strong class="text-slate-700">Device Type:</strong> ' + (device.type || '-') + '</div>';
            configHtml += '<div><strong class="text-slate-700">Protocol:</strong> ' + (device.protocol || '-') + '</div>';
            configHtml += '<div><strong class="text-slate-700">Address:</strong> ' + (device.address || '-') + '</div>';
            configHtml += '<div><strong class="text-slate-700">Group:</strong> ' + (device.group || 'None') + '</div>';
            configHtml += '</div>';
            
            // Add configuration based on device type
            configHtml += '<div class="border-t pt-4">';
            configHtml += '<h4 class="text-sm font-medium text-slate-700 mb-2">Configuration Details:</h4>';
            
            if (device.type === 'Modbus TCP' && device.config) {
                configHtml += '<div class="grid grid-cols-2 gap-2">';
                configHtml += '<div><strong class="text-slate-600">IP Address:</strong></div><div>' + (device.config.ip_address || '-') + '</div>';
                configHtml += '<div><strong class="text-slate-600">Port:</strong></div><div>' + (device.config.port || '-') + '</div>';
                configHtml += '<div><strong class="text-slate-600">Slave Address:</strong></div><div>' + (device.config.slave_address || '-') + '</div>';
                configHtml += '<div><strong class="text-slate-600">Polling Interval:</strong></div><div>' + (device.config.polling_interval || '1000') + ' ms</div>';
                configHtml += '<div><strong class="text-slate-600">Timeout:</strong></div><div>' + (device.config.timeout || '5000') + ' ms</div>';
                configHtml += '<div><strong class="text-slate-600">Retry Count:</strong></div><div>' + (device.config.retry_count || '3') + '</div>';
                configHtml += '</div>';
            } else if (device.type === 'Modbus RTU' && device.config) {
                configHtml += '<div class="grid grid-cols-2 gap-2">';
                configHtml += '<div><strong class="text-slate-600">Slave Address:</strong></div><div>' + (device.config.slave_address || '-') + '</div>';
                configHtml += '<div><strong class="text-slate-600">Baud Rate:</strong></div><div>' + (device.config.baud_rate || '-') + '</div>';
                configHtml += '<div><strong class="text-slate-600">Parity:</strong></div><div>' + (device.config.parity || '-') + '</div>';
                configHtml += '<div><strong class="text-slate-600">Stop Bits:</strong></div><div>' + (device.config.stop_bits || '-') + '</div>';
                configHtml += '<div><strong class="text-slate-600">Polling Interval:</strong></div><div>' + (device.config.polling_interval || '500') + ' ms</div>';
                configHtml += '</div>';
            } else if (device.type === 'CAN' && device.config) {
                configHtml += '<div class="grid grid-cols-2 gap-2">';
                configHtml += '<div><strong class="text-slate-600">CAN ID:</strong></div><div>' + (device.config.can_id || '-') + '</div>';
                configHtml += '<div><strong class="text-slate-600">Protocol:</strong></div><div>' + (device.config.protocol || '-') + '</div>';
                configHtml += '<div><strong class="text-slate-600">Bitrate:</strong></div><div>' + (device.config.bitrate || '-') + '</div>';
                configHtml += '</div>';
            } else if (device.type === 'Wireless' && device.config) {
                configHtml += '<div class="grid grid-cols-2 gap-2">';
                configHtml += '<div><strong class="text-slate-600">RF Address:</strong></div><div>' + (device.config.rf_address || '-') + '</div>';
                configHtml += '<div><strong class="text-slate-600">Signal Strength:</strong></div><div>' + (device.config.signal_strength || '-') + ' dBm</div>';
                configHtml += '</div>';
            } else if (device.type === 'ACS Sensor' && device.config) {
                configHtml += '<div class="grid grid-cols-2 gap-2">';
                configHtml += '<div><strong class="text-slate-600">Sensor ID:</strong></div><div>' + (device.config.sensor_id || '-') + '</div>';
                configHtml += '<div><strong class="text-slate-600">Sampling Rate:</strong></div><div>' + (device.config.sampling_rate || '-') + '</div>';
                configHtml += '<div><strong class="text-slate-600">Sensitivity:</strong></div><div>' + (device.config.sensitivity || '-') + '</div>';
                configHtml += '</div>';
            } else if (device.config && typeof device.config === 'object') {
                // Generic display for any other device type
                configHtml += '<div class="space-y-1">';
                for (const [key, value] of Object.entries(device.config)) {
                    const formattedKey = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                    configHtml += '<div><strong class="text-slate-600">' + formattedKey + ':</strong> ' + value + '</div>';
                }
                configHtml += '</div>';
            } else {
                configHtml += '<div class="text-slate-500 italic">No configuration details available</div>';
            }
            
            configHtml += '</div></div>';
            deviceConfigDisplay.innerHTML = configHtml;
        }
        
        // CRITICAL: Show the details section
        const detailsSection = document.getElementById('section-details');
        if (detailsSection) {
            console.log('Setting section-details display to block');
            detailsSection.style.display = 'block';
            detailsSection.classList.remove('hidden');
            
            // Scroll to it
            setTimeout(() => {
                detailsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 100);
            
            console.log('After setting display:', detailsSection.style.display);
        } else {
            console.error('section-details element not found!');
        }
        
        // Close any modals that might be blocking the view
        closeAllModals();
        
        // Close all dropdowns
        closeAllDropdowns();
        
        console.log('Device details loaded successfully');
        
    } catch (error) {
        console.error('Error loading device details:', error);
        showNotification('Failed to load device details: ' + error.message, 'error');
    }
}

        // ==================================================
        // DEVICE ACTION METHODS - All actions go here
        // ==================================================

        async function editDevice(deviceId) {
            try {
                const response = await fetch('/api/device-management/devices/' + deviceId + '/details');
                if (!response.ok) throw new Error('HTTP ' + response.status);
                
                const device = await response.json();
                
                // Open the add device panel in edit mode
                openAddDevicePanel();
                
                document.getElementById('deviceNameInput').value = device.name;
                document.getElementById('deviceGroupSelect').value = device.group || 'None';
                
                // Map device type to protocol
                let protocol = 'modbus-rtu';
                if (device.type === 'CAN') protocol = 'canbus';
                if (device.type === 'Wireless') protocol = 'wireless';
                if (device.type === 'Modbus TCP') protocol = 'modbus-tcp';
                if (device.type === 'ACS Sensor') protocol = 'acs';
                
                document.querySelector('input[name="device-type"][value="' + protocol + '"]').checked = true;
                document.querySelector('input[name="device-type"][value="' + protocol + '"]').dispatchEvent(new Event('change'));
                
                // Populate configuration fields based on device type
                if (device.type === 'Modbus TCP' && device.config) {
                    setTimeout(() => {
                        document.getElementById('modbusTcpIp').value = device.config.ip_address || '192.168.1.100';
                        document.getElementById('modbusTcpPort').value = device.config.port || 502;
                        document.getElementById('modbusTcpSlaveAddress').value = device.config.slave_address || 1;
                        document.getElementById('modbusTcpPolling').value = device.config.polling_interval || 1000;
                        document.getElementById('modbusTcpTimeout').value = device.config.timeout || 5000;
                    }, 100);
                } else if (device.type === 'Modbus RTU' && device.config) {
                    setTimeout(() => {
                        document.getElementById('modbusAddress').value = device.config.slave_address || 1;
                        document.getElementById('baudRate').value = device.config.baud_rate || 9600;
                        document.getElementById('parity').value = device.config.parity || 'None';
                        document.getElementById('stopBits').value = device.config.stop_bits || 1;
                        document.getElementById('pollingInterval').value = device.config.polling_interval || 500;
                    }, 100);
                } else if (device.type === 'CAN' && device.config) {
                    setTimeout(() => {
                        document.getElementById('canId').value = device.config.can_id || '0x000';
                        document.getElementById('canProtocol').value = device.config.protocol || 'CANOpen';
                        document.getElementById('bitrate').value = device.config.bitrate || '500K';
                    }, 100);
                } else if (device.type === 'Wireless' && device.config) {
                    setTimeout(() => {
                        document.getElementById('rfAddress').value = device.config.rf_address || 'RF:0x00';
                    }, 100);
                } else if (device.type === 'ACS Sensor' && device.config) {
                    setTimeout(() => {
                        document.getElementById('acsSensorId').value = device.config.sensor_id || 'ACS-001';
                        document.getElementById('acsSamplingRate').value = device.config.sampling_rate || '10 Hz';
                        document.getElementById('acsSensitivity').value = device.config.sensitivity || 'Medium';
                        document.getElementById('acsCalibration').value = device.config.calibration || 1.0;
                    }, 100);
                }
                
                // Store device ID for update
                document.getElementById('saveDeviceBtn').dataset.deviceId = deviceId;
                
                closeAllDropdowns();
                
            } catch (error) {
                console.error('Error loading device for edit:', error);
                showNotification('Failed to load device for editing', 'error');
            }
        }

        async function disableDevice(deviceId) {
            const device = devices.find(function(d) { return d.id === deviceId; });
            if (!device) return;
            
            const isDisabled = device.status === 'Disabled';
            const action = isDisabled ? 'enable' : 'disable';
            
            if (confirm((isDisabled ? 'Enable' : 'Disable') + ' ' + device.name + '?')) {
                try {
                    const response = await fetch('/api/device-management/devices/' + deviceId + '/disable', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ disabled: !isDisabled })
                    });
                    
                    if (!response.ok) throw new Error('HTTP ' + response.status);
                    
                    const result = await response.json();
                    
                    // Update local state
                    device.status = result.status;
                    device.details.status = result.status;
                    
                    renderDevicesTable();
                    showNotification('Device ' + device.name + ' ' + (isDisabled ? 'enabled' : 'disabled') + ' successfully', 'success');
                    
                } catch (error) {
                    console.error('Error disabling device:', error);
                    showNotification('Failed to ' + action + ' device', 'error');
                }
            }
            closeAllDropdowns();
        }

        async function deleteDevice(deviceId) {
            const device = devices.find(function(d) { return d.id === deviceId; });
            if (!device) return;
            
            if (confirm('Are you sure you want to delete ' + device.name + '? This action cannot be undone.')) {
                try {
                    const response = await fetch('/api/device-management/devices/' + deviceId, {
                        method: 'DELETE'
                    });
                    
                    if (!response.ok) throw new Error('HTTP ' + response.status);
                    
                    // Remove from local state
                    devices = devices.filter(function(d) { return d.id !== deviceId; });
                    renderDevicesTable();
                    
                    if (selectedDeviceId === deviceId) {
                        const detailsSection = document.getElementById('section-details');
                        if (detailsSection) {
                            detailsSection.style.display = 'none';
                        }
                        selectedDeviceId = null;
                    }
                    
                    showNotification('Device ' + device.name + ' deleted successfully', 'success');
                    
                } catch (error) {
                    console.error('Error deleting device:', error);
                    showNotification('Failed to delete device', 'error');
                }
            }
            closeAllDropdowns();
        }

        async function pingDevice(deviceId) {
            try {
                const response = await fetch('/api/device-management/devices/' + deviceId + '/test', {
                    method: 'POST'
                });
                
                if (!response.ok) throw new Error('HTTP ' + response.status);
                
                const result = await response.json();
                showNotification('Ping response: ' + result.ping_time_ms + 'ms', 'success');
                
            } catch (error) {
                console.error('Error pinging device:', error);
                showNotification('Ping failed', 'error');
            }
        }

        async function duplicateDevice(deviceId) {
    const device = devices.find(function(d) { return d.id === deviceId; });
    if (!device) return;
    
    if (confirm('Are you sure you want to duplicate "' + device.name + '"? All tag mappings will also be duplicated.')) {
        try {
            const response = await fetch('/api/device-management/devices/' + deviceId + '/duplicate', {
                method: 'POST'
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error('HTTP ' + response.status + ': ' + errorText);
            }
            
            const result = await response.json();
            
            if (!result.success) {
                throw new Error(result.error || 'Duplication failed');
            }
            
            // Reload devices
            await loadDevices();
            renderDevicesTable();
            
            showNotification('Device "' + result.new_device.name + '" duplicated successfully with ' + result.tags_duplicated + ' tag(s)', 'success');
            
        } catch (error) {
            console.error('Error duplicating device:', error);
            showNotification('Failed to duplicate device: ' + error.message, 'error');
        }
    }
    closeAllDropdowns();
}

        async function getDevicePackets(deviceId) {
            try {
                const response = await fetch('/api/device-management/devices/' + deviceId + '/packets');
                if (!response.ok) throw new Error('HTTP ' + response.status);
                
                const data = await response.json();
                
                // Display packets in a modal or alert
                let packetText = 'Recent packets for device:\n\n';
                data.packets.forEach(function(packet) {
                    const time = new Date(packet.timestamp).toLocaleTimeString();
                    const direction = packet.direction === 'tx' ? '→ TX' : '← RX';
                    packetText += time + ' ' + direction + ' ' + packet.data_hex + '\n';
                });
                
                alert(packetText);
                
            } catch (error) {
                console.error('Error getting packets:', error);
                showNotification('Failed to get device packets', 'error');
            }
        }

        // ==================================================
        // END OF DEVICE ACTION METHODS
        // ==================================================

        function openAddDevicePanel() {
            const addDevicePanel = document.getElementById('addDevicePanel');
            if (addDevicePanel) {
                addDevicePanel.classList.add('active');
                document.body.classList.add('modal-open');
            }
        }

        function toggleDropdown(deviceId) {
            const dropdown = document.getElementById('dropdown-' + deviceId);
            const isVisible = dropdown.classList.contains('show');
            
            closeAllDropdowns();
            
            if (!isVisible) {
                dropdown.classList.add('show');
                
                // Close dropdown when clicking outside
                setTimeout(function() {
                    const closeHandler = function(e) {
                        if (!dropdown.contains(e.target) && !e.target.classList.contains('dropdown-toggle')) {
                            dropdown.classList.remove('show');
                            document.removeEventListener('click', closeHandler);
                        }
                    };
                    document.addEventListener('click', closeHandler);
                }, 0);
            }
        }

        function closeAllDropdowns() {
            document.querySelectorAll('.action-dropdown-content').forEach(function(dropdown) {
                dropdown.classList.remove('show');
            });
        }

        function openAssignDevicesModal(groupId) {
            selectedGroupId = groupId;
            selectedDevicesForAssignment.clear();
            
            document.querySelectorAll('.group-item').forEach(function(item) {
                item.classList.remove('border-primary', 'bg-blue-50');
                if (parseInt(item.dataset.groupId) === groupId) {
                    item.classList.add('border-primary', 'bg-blue-50');
                }
            });
            
            renderAssignDevicesList();
            
            // Open the modal
            const assignDevicesModal = document.getElementById('assignDevicesModal');
            if (assignDevicesModal) {
                assignDevicesModal.classList.add('active');
                document.body.classList.add('modal-open');
            }
        }

        function renderAssignDevicesList() {
            const container = document.getElementById('assignDevicesList');
            if (!container) return;
            
            container.innerHTML = '';
            
            if (devices.length === 0) {
                container.innerHTML = '<div class="text-center text-slate-500 py-4">No devices available</div>';
                return;
            }
            
            devices.forEach(function(device) {
                const isSelected = selectedDevicesForAssignment.has(device.id);
                
                const deviceElement = document.createElement('label');
                deviceElement.className = 'flex items-center p-3 border rounded-lg cursor-pointer hover:bg-slate-50 ' + (isSelected ? 'border-primary bg-blue-50' : 'border-slate-300');
                deviceElement.innerHTML = '<input type="checkbox" class="h-4 w-4 text-primary focus:ring-primary border-slate-300 rounded" ' + (isSelected ? 'checked' : '') + ' value="' + device.id + '" onchange="window.deviceManagement.toggleDeviceSelection(\'' + device.id + '\', this.checked)">' +
                    '<div class="ml-3 flex-1">' +
                    '<div class="flex justify-between">' +
                    '<div class="font-medium text-sm text-slate-900">' + device.name + '</div>' +
                    '<div class="text-xs text-slate-500">' + device.type + '</div>' +
                    '</div>' +
                    '<div class="flex justify-between mt-1">' +
                    '<div class="text-xs text-slate-600">' + device.address + '</div>' +
                    '<div class="text-xs ' + (device.status === 'Online' ? 'text-green-600' : 'text-red-600') + '">' + device.status + '</div>' +
                    '</div>' +
                    '</div>';
                container.appendChild(deviceElement);
            });
            
            updateSelectedDevicesCount();
        }

        function toggleDeviceSelection(deviceId, isSelected) {
            if (isSelected) {
                selectedDevicesForAssignment.add(deviceId);
            } else {
                selectedDevicesForAssignment.delete(deviceId);
            }
            updateSelectedDevicesCount();
        }

        function updateSelectedDevicesCount() {
            const countElement = document.getElementById('selectedDevicesCount');
            if (countElement) {
                countElement.textContent = selectedDevicesForAssignment.size;
            }
        }

        async function assignDevicesToGroup() {
            if (!selectedGroupId) {
                alert('Please select a group first.');
                return;
            }
            
            if (selectedDevicesForAssignment.size === 0) {
                alert('Please select at least one device to assign.');
                return;
            }
            
            try {
                const deviceIds = Array.from(selectedDevicesForAssignment);
                const response = await fetch('/api/device-management/groups/' + selectedGroupId + '/assign-devices', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ device_ids: deviceIds })
                });
                
                if (!response.ok) throw new Error('HTTP ' + response.status);
                
                const result = await response.json();
                
                // Update local state
                deviceIds.forEach(function(deviceId) {
                    const device = devices.find(function(d) { return d.id === deviceId; });
                    if (device) {
                        const group = groups.find(function(g) { return g.id === selectedGroupId; });
                        if (group) {
                            device.group = group.name;
                        }
                    }
                });
                
                // Reload groups to update counts
                await loadGroups();
                renderDevicesTable();
                renderGroups();
                
                // Close the modal
                const assignDevicesModal = document.getElementById('assignDevicesModal');
                if (assignDevicesModal) {
                    assignDevicesModal.classList.remove('active');
                    document.body.classList.remove('modal-open');
                }
                
                showNotification('Successfully assigned ' + result.assigned_count + ' device(s) to group.', 'success');
                
            } catch (error) {
                console.error('Error assigning devices:', error);
                showNotification('Failed to assign devices to group', 'error');
            }
        }

        function addNewGroup() {
            document.getElementById('groupNameInput').value = '';
            document.getElementById('groupDescription').value = '';
            
            const colorSelection = document.querySelector('#addGroupModal .flex.space-x-2');
            if (colorSelection) {
                colorSelection.querySelectorAll('button').forEach(function(btn) {
                    btn.classList.remove('border-blue-700');
                    btn.classList.add('border-transparent');
                });
                const firstButton = colorSelection.querySelector('button[data-color="blue"]');
                if (firstButton) {
                    firstButton.classList.remove('border-transparent');
                    firstButton.classList.add('border-blue-700');
                }
            }
            
            // Open the modal
            const addGroupModal = document.getElementById('addGroupModal');
            if (addGroupModal) {
                addGroupModal.classList.add('active');
                document.body.classList.add('modal-open');
            }
            selectedColor = 'blue';
        }

        async function saveNewGroup() {
            const nameInput = document.getElementById('groupNameInput');
            
            if (!nameInput.value.trim()) {
                alert('Please enter a group name.');
                return;
            }
            
            const selectedColorBtn = document.querySelector('#addGroupModal .flex.space-x-2 button.border-blue-700');
            const color = selectedColorBtn ? selectedColorBtn.dataset.color : 'blue';
            
            try {
                const response = await fetch('/api/device-management/groups', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        name: nameInput.value,
                        color: color,
                        description: document.getElementById('groupDescription').value
                    })
                });
                
                if (!response.ok) throw new Error('HTTP ' + response.status);
                
                const result = await response.json();
                
                // Reload groups
                await loadGroups();
                renderGroups();
                
                nameInput.value = '';
                document.getElementById('groupDescription').value = '';
                
                // Close the modal
                const addGroupModal = document.getElementById('addGroupModal');
                if (addGroupModal) {
                    addGroupModal.classList.remove('active');
                    document.body.classList.remove('modal-open');
                }
                
                showNotification('Group "' + result.group.name + '" created successfully.', 'success');
                
            } catch (error) {
                console.error('Error saving group:', error);
                showNotification('Failed to create group', 'error');
            }
        }

        // CSV Export/Import Functions
        async function exportDevices() {
            try {
                const response = await fetch('/api/device-management/export', {
                    method: 'POST'
                });
                
                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error('HTTP ' + response.status + ': ' + errorText);
                }
                
                // Get the blob and create download link
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                
                // Get filename from Content-Disposition header or use default
                const contentDisposition = response.headers.get('Content-Disposition');
                let filename = 'devices_export.csv';
                
                if (contentDisposition) {
                    const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                    if (filenameMatch) {
                        filename = filenameMatch[1];
                    }
                }
                
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                showNotification('Devices exported successfully!', 'success');
                
            } catch (error) {
                console.error('Error exporting:', error);
                showNotification('Failed to export devices: ' + error.message, 'error');
            }
        }

        async function importCSVFile(file) {
            if (!file.name.endsWith('.csv')) {
                showNotification('Please select a CSV file', 'error');
                return;
            }
            
            const formData = new FormData();
            formData.append('file', file);
            
            const importBtn = document.getElementById('importBtn');
            const originalText = importBtn.innerHTML;
            
            importBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Importing...';
            importBtn.disabled = true;
            
            try {
                const response = await fetch('/api/device-management/import', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Import failed');
                }
                
                const result = await response.json();
                
                // Reload devices and groups
                await loadDevices();
                await loadGroups();
                renderDevicesTable();
                renderGroups();
                
                showNotification(
                    `Successfully imported ${result.devices_added} devices, updated ${result.devices_updated} devices. ${result.devices_skipped} skipped.`,
                    'success'
                );
                
            } catch (error) {
                console.error('Error importing:', error);
                showNotification('Failed to import devices: ' + error.message, 'error');
            } finally {
                importBtn.innerHTML = originalText;
                importBtn.disabled = false;
            }
        }

        function downloadCSVTemplate() {
            const templateData = [
                ['Device ID', 'Device Name', 'Type', 'Address/ID', 'Group', 'Configuration JSON'],
                ['1', 'LoadCell-Front', 'Modbus RTU', 'Slave 01', 'Safety Sensors', '{"slave_address":1,"baud_rate":9600,"parity":"None","stop_bits":1,"polling_interval":500}'],
                ['2', 'BoomAngleSensor', 'CAN', '0x212', 'Crane-01', '{"can_id":"0x212","protocol":"CANOpen","bitrate":"500K"}'],
                ['3', 'ACS-Node-Left', 'Wireless', 'RF:0x09', 'Safety Sensors', '{"rf_address":"RF:0x09","signal_strength":-70}'],
                ['4', 'PLC-Main', 'Modbus TCP', '192.168.1.100:502', 'Crane-01', '{"ip_address":"192.168.1.100","port":502,"slave_address":1,"polling_interval":1000,"timeout":5000,"retry_count":3}'],
                ['', 'New-Device', 'ACS Sensor', 'ACS-001', 'New Group', '']
            ];
            
            let csv = '';
            templateData.forEach(row => {
                csv += row.map(v => {
                    // Escape quotes and wrap in quotes if contains comma
                    const escaped = (v || '').toString().replace(/"/g, '""');
                    return v.includes(',') ? `"${escaped}"` : escaped;
                }).join(',') + '\n';
            });
            
            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            
            link.href = URL.createObjectURL(blob);
            link.download = 'device_import_template.csv';
            link.style.display = 'none';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        function handleFiles(files) {
            if (files.length > 0) {
                const file = files[0];
                importCSVFile(file);
            }
        }

        function handleFileSelect(e) {
            const files = e.target.files;
            if (files.length > 0) {
                const file = files[0];
                importCSVFile(file);
            }
        }

        // Save Configuration Handler
        async function handleSaveConfiguration() {
            const saveBtn = document.getElementById('footer-save-btn');
            if (!saveBtn) return;
            
            const originalText = saveBtn.innerHTML;
            
            saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Saving...';
            saveBtn.disabled = true;
            
            try {
                // Note: In real implementation, you would save device configuration changes
                // For now, just show success
                await new Promise(function(resolve) { setTimeout(resolve, 1000); });
                
                saveBtn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Saved!';
                saveBtn.classList.remove('bg-primary', 'hover:bg-primaryHover');
                saveBtn.classList.add('bg-success', 'hover:bg-emerald-600');
                
                setTimeout(function() {
                    saveBtn.innerHTML = originalText;
                    saveBtn.classList.remove('bg-success', 'hover:bg-emerald-600');
                    saveBtn.classList.add('bg-primary', 'hover:bg-primaryHover');
                    saveBtn.disabled = false;
                }, 2000);
                
                showNotification('Device configuration saved successfully', 'success');
                
            } catch (error) {
                console.error('Save error:', error);
                
                saveBtn.innerHTML = '<i class="fa-solid fa-exclamation-triangle mr-2"></i> Failed!';
                saveBtn.classList.remove('bg-primary', 'hover:bg-primaryHover');
                saveBtn.classList.add('bg-red-500', 'hover:bg-red-600');
                
                setTimeout(function() {
                    saveBtn.innerHTML = originalText;
                    saveBtn.classList.remove('bg-red-500', 'hover:bg-red-600');
                    saveBtn.classList.add('bg-primary', 'hover:bg-primaryHover');
                    saveBtn.disabled = false;
                }, 3000);
                
                showNotification('Save failed: ' + error.message, 'error');
            }
        }

        // Notification System
        function showNotification(message, type) {
            if (!type) type = 'info';
            
            // Remove existing notifications
            const existingNotifications = document.querySelectorAll('.notification-toast');
            existingNotifications.forEach(function(notification) {
                notification.remove();
            });
            
            // Create notification element
            const notification = document.createElement('div');
            notification.className = 'notification-toast fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg border transition-all duration-300 transform translate-x-0 opacity-100';
            
            // Set styles based on type
            const typeStyles = {
                success: 'bg-emerald-50 text-emerald-800 border-emerald-200',
                error: 'bg-red-50 text-red-800 border-red-200',
                warning: 'bg-amber-50 text-amber-800 border-amber-200',
                info: 'bg-blue-50 text-blue-800 border-blue-200'
            };
            
            notification.className += ' ' + (typeStyles[type] || typeStyles.info);
            
            // Add icon based on type
            const icons = {
                success: 'fa-check-circle',
                error: 'fa-exclamation-circle',
                warning: 'fa-exclamation-triangle',
                info: 'fa-info-circle'
            };
            
            notification.innerHTML = '<div class="flex items-center">' +
                '<i class="fa-solid ' + (icons[type] || icons.info) + ' mr-2"></i>' +
                '<span class="text-sm font-medium">' + message + '</span>' +
                '<button class="ml-4 text-gray-500 hover:text-gray-700 close-notification">' +
                '<i class="fa-solid fa-times"></i>' +
                '</button>' +
                '</div>';
            
            // Add to document
            document.body.appendChild(notification);
            
            // Add close handler
            const closeBtn = notification.querySelector('.close-notification');
            if (closeBtn) {
                closeBtn.addEventListener('click', function() {
                    notification.remove();
                });
            }
            
            // Auto-remove after 5 seconds
            setTimeout(function() {
                if (notification.parentNode) {
                    notification.classList.add('fade-out');
                    setTimeout(function() { notification.remove(); }, 300);
                }
            }, 5000);
        }

        // ==================================================
        // FIXED: Save Device Handler (Prevents Multiple Saves)
        // ==================================================
        async function handleSaveDevice(event) {
            if (isSaving) return;
            
            isSaving = true;
            console.log('Save device button clicked - handling');
            
            // Get form elements with null checks
            const deviceNameInput = document.getElementById('deviceNameInput');
            const deviceGroupSelect = document.getElementById('deviceGroupSelect');
            const deviceTypeElement = document.querySelector('input[name="device-type"]:checked');
            const saveDeviceBtn = document.getElementById('saveDeviceBtn');
            
            // ADD NULL CHECKS
            if (!deviceNameInput || !deviceGroupSelect) {
                console.error('Required form elements not found');
                showNotification('Form elements missing. Please refresh the page.', 'error');
                isSaving = false;
                return;
            }
            
            if (!deviceTypeElement) {
                console.error('No device type selected');
                showNotification('Please select a device type.', 'error');
                isSaving = false;
                return;
            }
            
            const deviceName = deviceNameInput.value.trim();
            const deviceGroup = deviceGroupSelect.value;
            const deviceType = deviceTypeElement.value;
            
            console.log('Device data:', { deviceName, deviceGroup, deviceType });
            
            if (!deviceName) {
                alert('Please enter a device name.');
                isSaving = false;
                return;
            }
            
            const typeMap = {
                'modbus-rtu': 'Modbus RTU',
                'modbus-tcp': 'Modbus TCP',
                'canbus': 'CAN',
                'wireless': 'Wireless',
                'acs': 'ACS Sensor'
            };
            
            let address = 'N/A';
            let config = {};
            
            // Get protocol-specific fields with null checks
            if (deviceType === 'modbus-rtu') {
                const slaveAddress = document.getElementById('modbusAddress');
                const baudRate = document.getElementById('baudRate');
                const parity = document.getElementById('parity');
                const stopBits = document.getElementById('stopBits');
                const pollingInterval = document.getElementById('pollingInterval');
                
                if (!slaveAddress || !baudRate || !parity || !stopBits || !pollingInterval) {
                    showNotification('Modbus RTU configuration fields not found', 'error');
                    console.error('Missing RTU fields:', { slaveAddress, baudRate, parity, stopBits, pollingInterval });
                    isSaving = false;
                    return;
                }
                
                address = 'Slave ' + slaveAddress.value;
                config = {
                    slave_address: parseInt(slaveAddress.value) || 1,
                    baud_rate: parseInt(baudRate.value) || 9600,
                    parity: parity.value || 'None',
                    stop_bits: parseInt(stopBits.value) || 1,
                    polling_interval: parseInt(pollingInterval.value) || 500
                };
                
                console.log('RTU config created:', config);
                
            } else if (deviceType === 'modbus-tcp') {
                // Get all TCP form elements - USING CORRECT IDs FROM HTML
                const ip = document.getElementById('modbusTcpIp');
                const port = document.getElementById('modbusTcpPort');
                const slaveAddress = document.getElementById('modbusTcpSlaveAddress');
                const polling = document.getElementById('modbusTcpPolling'); // CHANGED from modbusTcpPollingInterval
                const timeout = document.getElementById('modbusTcpTimeout');
                
                console.log('TCP form elements:', { ip, port, slaveAddress, polling, timeout });
                
                // Check if all TCP fields exist
                if (!ip || !port || !slaveAddress || !polling || !timeout) {
                    showNotification('Modbus TCP configuration fields not found. Please ensure the TCP form is visible.', 'error');
                    console.error('Missing TCP fields:', { 
                        ip: ip ? 'found' : 'missing', 
                        port: port ? 'found' : 'missing',
                        slaveAddress: slaveAddress ? 'found' : 'missing',
                        polling: polling ? 'found' : 'missing',
                        timeout: timeout ? 'found' : 'missing'
                    });
                    isSaving = false;
                    return;
                }
                
                address = ip.value + ':' + port.value;
                config = {
                    ip_address: ip.value,
                    port: parseInt(port.value) || 502,
                    slave_address: parseInt(slaveAddress.value) || 1,
                    polling_interval: parseInt(polling.value) || 1000, // CHANGED from pollingInterval
                    timeout: parseInt(timeout.value) || 5000,
                    retry_count: 3 // Default value since HTML doesn't have this field
                };
                
                console.log('TCP config created:', config);
                
            } else if (deviceType === 'canbus') {
                const canId = document.getElementById('canId');
                const canProtocol = document.getElementById('canProtocol');
                const bitrate = document.getElementById('bitrate');
                
                if (!canId || !canProtocol || !bitrate) {
                    showNotification('CAN configuration fields not found', 'error');
                    console.error('Missing CAN fields:', { canId, canProtocol, bitrate });
                    isSaving = false;
                    return;
                }
                
                address = canId.value;
                config = {
                    can_id: address,
                    protocol: canProtocol.value || 'CANOpen',
                    bitrate: bitrate.value || '500K'
                };
                
            } else if (deviceType === 'wireless') {
                const rfAddress = document.getElementById('rfAddress');
                
                if (!rfAddress) {
                    showNotification('Wireless configuration fields not found', 'error');
                    console.error('Missing Wireless fields:', { rfAddress });
                    isSaving = false;
                    return;
                }
                
                address = rfAddress.value;
                config = {
                    rf_address: address,
                    signal_strength: -70
                };
                
            } else if (deviceType === 'acs') {
                const sensorId = document.getElementById('acsSensorId');
                const samplingRate = document.getElementById('acsSamplingRate');
                const sensitivity = document.getElementById('acsSensitivity');
                const calibration = document.getElementById('acsCalibration');
                
                if (!sensorId || !samplingRate || !sensitivity || !calibration) {
                    showNotification('ACS Sensor configuration fields not found', 'error');
                    console.error('Missing ACS fields:', { sensorId, samplingRate, sensitivity, calibration });
                    isSaving = false;
                    return;
                }
                
                address = sensorId.value;
                config = {
                    sensor_id: address,
                    sampling_rate: samplingRate.value || '10 Hz',
                    sensitivity: sensitivity.value || 'Medium',
                    calibration: parseFloat(calibration.value) || 1.0
                };
            }
            
            const deviceData = {
                name: deviceName,
                type: typeMap[deviceType],
                address: address,
                group: deviceGroup === 'None' ? '' : deviceGroup,
                config: config
            };
            
            console.log('Device data to save:', deviceData);
            
            // Check if updating existing device
            const deviceId = saveDeviceBtn.dataset.deviceId;
            
            // Disable button and show loading
            const originalBtnHTML = saveDeviceBtn.innerHTML;
            saveDeviceBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Saving...';
            saveDeviceBtn.disabled = true;
            
            try {
                let response;
                if (deviceId) {
                    // Update existing device
                    response = await fetch('/api/device-management/devices/' + deviceId, {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(deviceData)
                    });
                } else {
                    // Add new device
                    response = await fetch('/api/device-management/devices', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(deviceData)
                    });
                }
                
                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error('HTTP ' + response.status + ': ' + errorText);
                }
                
                const result = await response.json();
                
                // Reload devices
                await loadDevices();
                renderDevicesTable();
                await loadGroups();
                renderGroups();
                
                // Close the panel
                const addDevicePanel = document.getElementById('addDevicePanel');
                if (addDevicePanel) {
                    addDevicePanel.classList.remove('active');
                    document.body.classList.remove('modal-open');
                }
                
                showNotification('Device "' + deviceName + '" ' + (deviceId ? 'updated' : 'added') + ' successfully.', 'success');
                
            } catch (error) {
                console.error('Error saving device:', error);
                showNotification('Failed to save device: ' + error.message, 'error');
            } finally {
                // Re-enable button
                saveDeviceBtn.innerHTML = originalBtnHTML;
                saveDeviceBtn.disabled = false;
                isSaving = false;
            }
        }

        function addDebugButton() {
            // Don't add in production
            if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
                return;
            }
            
            const debugBtn = document.createElement('button');
            debugBtn.textContent = 'Debug Details Section';
            debugBtn.id = 'debugDetailsBtn';
            debugBtn.style.position = 'fixed';
            debugBtn.style.bottom = '20px';
            debugBtn.style.right = '20px';
            debugBtn.style.zIndex = '9999';
            debugBtn.style.padding = '10px';
            debugBtn.style.backgroundColor = 'red';
            debugBtn.style.color = 'white';
            debugBtn.style.border = 'none';
            debugBtn.style.borderRadius = '5px';
            debugBtn.style.fontSize = '12px';
            
            debugBtn.onclick = function() {
                debugDetailsSection();
                
                // Also try to manually show the section
                const detailsSection = document.getElementById('section-details');
                if (detailsSection) {
                    console.log('Manually toggling section');
                    if (detailsSection.style.display === 'none') {
                        detailsSection.style.display = 'block';
                        console.log('Set display to block');
                    } else {
                        detailsSection.style.display = 'none';
                        console.log('Set display to none');
                    }
                }
            };
            
            document.body.appendChild(debugBtn);
        }

        function setupEventListeners() {
            console.log('Setting up event listeners...');
            
            // Add click outside listeners
            setupClickOutsideListeners();
            
            // Add escape key listener
            setupEscapeKeyListener();
            
            // FIXED: Use event delegation for save button
            document.addEventListener('click', function(event) {
                if (event.target.id === 'saveDeviceBtn' || event.target.closest('#saveDeviceBtn')) {
                    event.preventDefault();
                    handleSaveDevice(event);
                }
            });
            
            // Add device panel
            const addDeviceBtn = document.getElementById('addDeviceBtn');
            if (addDeviceBtn) {
                addDeviceBtn.addEventListener('click', function() {
                    openAddDevicePanel();
                    document.getElementById('deviceNameInput').value = '';
                    document.getElementById('deviceGroupSelect').value = 'None';
                    document.querySelector('input[name="device-type"][value="modbus-rtu"]').checked = true;
                    document.querySelector('input[name="device-type"][value="modbus-rtu"]').dispatchEvent(new Event('change'));
                    delete document.getElementById('saveDeviceBtn').dataset.deviceId;
                });
            }

            const closeAddDevicePanel = document.getElementById('closeAddDevicePanel');
            if (closeAddDevicePanel) {
                closeAddDevicePanel.addEventListener('click', function() {
                    const addDevicePanel = document.getElementById('addDevicePanel');
                    if (addDevicePanel) {
                        addDevicePanel.classList.remove('active');
                        document.body.classList.remove('modal-open');
                    }
                });
            }

            const cancelAddDevice = document.getElementById('cancelAddDevice');
            if (cancelAddDevice) {
                cancelAddDevice.addEventListener('click', function() {
                    const addDevicePanel = document.getElementById('addDevicePanel');
                    if (addDevicePanel) {
                        addDevicePanel.classList.remove('active');
                        document.body.classList.remove('modal-open');
                    }
                });
            }

            // Protocol selection
            document.querySelectorAll('input[name="device-type"]').forEach(function(radio) {
                radio.addEventListener('change', function() {
                    console.log('Device type changed to:', this.value);
                    
                    // Hide all protocol configs
                    document.querySelectorAll('.protocol-config').forEach(function(config) {
                        config.classList.remove('active');
                    });
                    
                    // Show selected protocol config
                    const configId = this.value + '-config';
                    const configElement = document.getElementById(configId);
                    if (configElement) {
                        configElement.classList.add('active');
                        console.log('Showing config:', configId);
                    } else {
                        console.error('Config element not found:', configId);
                    }
                });
            });

            // Add group modal
            const addGroupBtn = document.getElementById('addGroupBtn');
            if (addGroupBtn) {
                addGroupBtn.addEventListener('click', addNewGroup);
            }
            
            const closeGroupModal = document.getElementById('closeGroupModal');
            if (closeGroupModal) {
                closeGroupModal.addEventListener('click', function() {
                    const addGroupModal = document.getElementById('addGroupModal');
                    if (addGroupModal) {
                        addGroupModal.classList.remove('active');
                        document.body.classList.remove('modal-open');
                    }
                });
            }
            
            const cancelGroupBtn = document.getElementById('cancelGroupBtn');
            if (cancelGroupBtn) {
                cancelGroupBtn.addEventListener('click', function() {
                    const addGroupModal = document.getElementById('addGroupModal');
                    if (addGroupModal) {
                        addGroupModal.classList.remove('active');
                        document.body.classList.remove('modal-open');
                    }
                });
            }
            
            const saveGroupBtn = document.getElementById('saveGroupBtn');
            if (saveGroupBtn) {
                saveGroupBtn.addEventListener('click', saveNewGroup);
            }
            
            // Color selection
            const colorSelection = document.querySelector('#addGroupModal .flex.space-x-2');
            if (colorSelection) {
                colorSelection.addEventListener('click', function(e) {
                    if (e.target.dataset.color) {
                        selectedColor = e.target.dataset.color;
                        
                        this.querySelectorAll('button').forEach(function(btn) {
                            btn.classList.remove('border-blue-700');
                            btn.classList.add('border-transparent');
                        });
                        
                        e.target.classList.remove('border-transparent');
                        e.target.classList.add('border-blue-700');
                    }
                });
            }

            // Filters
            const searchInput = document.getElementById('searchInput');
            if (searchInput) {
                searchInput.addEventListener('input', function(e) {
                    filterDevices();
                });
            }
            
            const deviceTypeFilter = document.getElementById('deviceTypeFilter');
            if (deviceTypeFilter) {
                deviceTypeFilter.addEventListener('change', function(e) {
                    filterDevices();
                });
            }
            
            const statusFilter = document.getElementById('statusFilter');
            if (statusFilter) {
                statusFilter.addEventListener('change', function(e) {
                    filterDevices();
                });
            }
            
            const groupFilter = document.getElementById('groupFilter');
            if (groupFilter) {
                groupFilter.addEventListener('change', function(e) {
                    filterDevices();
                });
            }

            // Scan Networks button
            const scanNetworksBtn = document.getElementById('scanNetworksBtn');
            if (scanNetworksBtn) {
                scanNetworksBtn.addEventListener('click', function() {
                    const scanDeviceTypeModal = document.getElementById('scanDeviceTypeModal');
                    if (scanDeviceTypeModal) {
                        scanDeviceTypeModal.classList.add('active');
                        document.body.classList.add('modal-open');
                    }
                });
            }
            
            // Scan modal event listeners
            const closeScanModal = document.getElementById('closeScanModal');
            if (closeScanModal) {
                closeScanModal.addEventListener('click', function() {
                    const scanDeviceTypeModal = document.getElementById('scanDeviceTypeModal');
                    if (scanDeviceTypeModal) {
                        scanDeviceTypeModal.classList.remove('active');
                        document.body.classList.remove('modal-open');
                    }
                });
            }
            
            const cancelScanBtn = document.getElementById('cancelScanBtn');
            if (cancelScanBtn) {
                cancelScanBtn.addEventListener('click', function() {
                    const scanDeviceTypeModal = document.getElementById('scanDeviceTypeModal');
                    if (scanDeviceTypeModal) {
                        scanDeviceTypeModal.classList.remove('active');
                        document.body.classList.remove('modal-open');
                    }
                });
            }
            
            // Assign Devices Modal
            const closeAssignModal = document.getElementById('closeAssignModal');
            if (closeAssignModal) {
                closeAssignModal.addEventListener('click', function() {
                    const assignDevicesModal = document.getElementById('assignDevicesModal');
                    if (assignDevicesModal) {
                        assignDevicesModal.classList.remove('active');
                        document.body.classList.remove('modal-open');
                    }
                });
            }
            
            const cancelAssignBtn = document.getElementById('cancelAssignBtn');
            if (cancelAssignBtn) {
                cancelAssignBtn.addEventListener('click', function() {
                    const assignDevicesModal = document.getElementById('assignDevicesModal');
                    if (assignDevicesModal) {
                        assignDevicesModal.classList.remove('active');
                        document.body.classList.remove('modal-open');
                    }
                });
            }
            
            const assignDevicesBtn = document.getElementById('assignDevicesBtn');
            if (assignDevicesBtn) {
                assignDevicesBtn.addEventListener('click', assignDevicesToGroup);
            }
            
            // Quick actions in assign modal
            const selectAllBtn = document.getElementById('selectAllBtn');
            if (selectAllBtn) {
                selectAllBtn.addEventListener('click', function() {
                    devices.forEach(function(device) {
                        selectedDevicesForAssignment.add(device.id);
                    });
                    renderAssignDevicesList();
                });
            }
            
            const deselectAllBtn = document.getElementById('deselectAllBtn');
            if (deselectAllBtn) {
                deselectAllBtn.addEventListener('click', function() {
                    selectedDevicesForAssignment.clear();
                    renderAssignDevicesList();
                });
            }
            
            const selectOnlineBtn = document.getElementById('selectOnlineBtn');
            if (selectOnlineBtn) {
                selectOnlineBtn.addEventListener('click', function() {
                    devices.forEach(function(device) {
                        if (device.status === 'Online') {
                            selectedDevicesForAssignment.add(device.id);
                        }
                    });
                    renderAssignDevicesList();
                });
            }
            
            const selectByTypeBtn = document.getElementById('selectByTypeBtn');
            if (selectByTypeBtn) {
                selectByTypeBtn.addEventListener('click', function() {
                    const typeToSelect = prompt('Enter device type to select (e.g., Modbus RTU, CAN, Wireless):', 'Modbus RTU');
                    if (typeToSelect) {
                        devices.forEach(function(device) {
                            if (device.type === typeToSelect) {
                                selectedDevicesForAssignment.add(device.id);
                            }
                        });
                        renderAssignDevicesList();
                    }
                });
            }
            
            // Group selection in assign modal
            document.querySelectorAll('.group-item').forEach(function(item) {
                item.addEventListener('click', function() {
                    const groupId = parseInt(this.dataset.groupId);
                    selectedGroupId = groupId;
                    
                    document.querySelectorAll('.group-item').forEach(function(i) {
                        i.classList.remove('border-primary', 'bg-blue-50');
                    });
                    this.classList.add('border-primary', 'bg-blue-50');
                });
            });

            // Refresh button
            const refreshBtn = document.getElementById('refreshBtn');
            if (refreshBtn) {
                refreshBtn.addEventListener('click', async function() {
                    this.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Refreshing...';
                    this.disabled = true;
                    
                    try {
                        await loadDevices();
                        await loadGroups();
                        renderDevicesTable();
                        renderGroups();
                        showNotification('Device list refreshed successfully!', 'success');
                    } catch (error) {
                        console.error('Error refreshing:', error);
                        showNotification('Failed to refresh device list', 'error');
                    } finally {
                        this.innerHTML = '<i class="fa-solid fa-sync mr-2 text-slate-400"></i> Refresh';
                        this.disabled = false;
                    }
                });
            }
            
            // Export button
            const exportBtn = document.getElementById('exportBtn');
            if (exportBtn) {
                exportBtn.addEventListener('click', exportDevices);
            }

            // Import functionality
            const browseFilesBtn = document.getElementById('browseFilesBtn');
            if (browseFilesBtn) {
                browseFilesBtn.addEventListener('click', function() {
                    document.getElementById('fileInput').click();
                });
            }

            const fileInput = document.getElementById('fileInput');
            if (fileInput) {
                fileInput.addEventListener('change', handleFileSelect);
            }

            // Drag and drop functionality
            const dropArea = document.getElementById('dropArea');
            if (dropArea) {
                ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(function(eventName) {
                    dropArea.addEventListener(eventName, preventDefaults, false);
                });

                function preventDefaults(e) {
                    e.preventDefault();
                    e.stopPropagation();
                }

                ['dragenter', 'dragover'].forEach(function(eventName) {
                    dropArea.addEventListener(eventName, highlight, false);
                });

                ['dragleave', 'drop'].forEach(function(eventName) {
                    dropArea.addEventListener(eventName, unhighlight, false);
                });

                function highlight() {
                    dropArea.classList.add('border-primary', 'bg-blue-50');
                }

                function unhighlight() {
                    dropArea.classList.remove('border-primary', 'bg-blue-50');
                }

                dropArea.addEventListener('drop', function(e) {
                    const dt = e.dataTransfer;
                    const files = dt.files;
                    handleFiles(files);
                }, false);
            }

            // Template download button
            const downloadCsvTemplateBtn = document.getElementById('downloadCsvTemplateBtn');
            if (downloadCsvTemplateBtn) {
                downloadCsvTemplateBtn.addEventListener('click', downloadCSVTemplate);
            }

            const scanRfBtn = document.getElementById('scanRfBtn');
            if (scanRfBtn) {
                scanRfBtn.addEventListener('click', async function() {
                    this.innerHTML = 'Scanning...';
                    this.disabled = true;
                    
                    try {
                        const response = await fetch('/api/device-management/wireless/scan', {
                            method: 'POST'
                        });
                        
                        if (!response.ok) throw new Error('HTTP ' + response.status);
                        
                        const result = await response.json();
                        
                        if (result.devices_found && result.devices_found.length > 0) {
                            const device = result.devices_found[0];
                            document.getElementById('rfAddress').value = device.rf_address;
                            document.getElementById('signalStrengthDisplay').textContent = device.signal_strength + ' dBm';
                            showNotification('Found wireless device: ' + device.rf_address, 'success');
                        } else {
                            showNotification('No wireless devices found', 'warning');
                        }
                        
                    } catch (error) {
                        console.error('Error scanning wireless:', error);
                        showNotification('Wireless scan failed', 'error');
                    } finally {
                        this.innerHTML = 'Scan';
                        this.disabled = false;
                    }
                });
            }
            
            const startPairingBtn = document.getElementById('startPairingBtn');
            if (startPairingBtn) {
                startPairingBtn.addEventListener('click', async function() {
                    const rfAddress = document.getElementById('rfAddress').value;
                    if (!rfAddress || rfAddress === 'Auto-Assign') {
                        alert('Please enter or scan for an RF address first.');
                        return;
                    }
                    
                    this.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Pairing...';
                    this.disabled = true;
                    
                    try {
                        const response = await fetch('/api/device-management/wireless/pair', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({ rf_address: rfAddress })
                        });
                        
                        if (!response.ok) throw new Error('HTTP ' + response.status);
                        
                        const result = await response.json();
                        showNotification('Wireless device paired successfully! Pairing code: ' + result.pairing_code, 'success');
                        
                    } catch (error) {
                        console.error('Error pairing wireless:', error);
                        showNotification('Wireless pairing failed', 'error');
                    } finally {
                        this.innerHTML = '<i class="fa-solid fa-link mr-2"></i> Start Pairing';
                        this.disabled = false;
                    }
                });
            }

            // Save buttons
            const footerSaveBtn = document.getElementById('footer-save-btn');
            if (footerSaveBtn) {
                footerSaveBtn.addEventListener('click', handleSaveConfiguration);
            }
            
            // Cancel/Back button
            const footerCancelBtn = document.getElementById('footer-cancel-btn');
            if (footerCancelBtn) {
                footerCancelBtn.addEventListener('click', function() {
                    if (confirm('Go back? Unsaved changes will be lost.')) {
                        window.history.back();
                    }
                });
            }
            
            console.log('Event listeners setup complete');
        }

        function filterDevices() {
            const typeFilter = document.getElementById('deviceTypeFilter').value;
            const statusFilter = document.getElementById('statusFilter').value;
            const groupFilter = document.getElementById('groupFilter').value;
            const searchTerm = document.getElementById('searchInput').value.toLowerCase();
            
            let filteredDevices = devices;
            
            if (searchTerm) {
                filteredDevices = filteredDevices.filter(function(device) {
                    return device.name.toLowerCase().includes(searchTerm) ||
                           device.type.toLowerCase().includes(searchTerm) ||
                           device.address.toLowerCase().includes(searchTerm);
                });
            }
            
            if (typeFilter !== 'All Device Types') {
                filteredDevices = filteredDevices.filter(function(device) { return device.type === typeFilter; });
            }
            
            if (statusFilter !== 'All Status') {
                filteredDevices = filteredDevices.filter(function(device) { return device.status === statusFilter; });
            }
            
            if (groupFilter !== 'All Groups') {
                filteredDevices = filteredDevices.filter(function(device) { return device.group === groupFilter; });
            }
            
            renderFilteredTable(filteredDevices);
        }

        function renderDevicesTable() {
            const tbody = document.getElementById('devicesTableBody');
            if (!tbody) return;
            
            tbody.innerHTML = '';
            
            devices.forEach(function(device) {
                const row = document.createElement('tr');
                row.className = 'hover:bg-slate-50 transition-colors';
                row.id = 'device-' + device.id;
                row.dataset.deviceId = device.id;
                
                let statusColor = 'bg-green-500';
                if (device.status === 'Offline') {
                    statusColor = 'bg-red-500';
                } else if (device.status === 'Warning') {
                    statusColor = 'bg-yellow-500';
                } else if (device.status === 'Disabled') {
                    statusColor = 'bg-gray-500';
                }
                
                let typeColor = 'bg-blue-100 text-blue-800';
                if (device.type === 'CAN') typeColor = 'bg-orange-100 text-orange-800';
                if (device.type === 'Wireless') typeColor = 'bg-purple-100 text-purple-800';
                if (device.type === 'Modbus TCP') typeColor = 'bg-cyan-100 text-cyan-800';
                if (device.type === 'ACS Sensor') typeColor = 'bg-indigo-100 text-indigo-800';
                
                row.innerHTML = '<td class="p-4">' +  // Column 1: Device Name ONLY
                    '<div class="font-medium text-slate-900">' + device.name + '</div>' +
                    '</td>' +
                    '<td class="p-4">' +  // Column 2: Type
                    '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ' + typeColor + '">' +
                    device.type + 
                    '</span>' +
                    '</td>' +
                    '<td class="p-4">' +  // Column 3: Address/ID
                    '<div class="text-sm font-mono">' + device.address + '</div>' +
                    '</td>' +
                    '<td class="p-4">' +  // Column 4: Status
                    '<div class="flex items-center">' +
                    '<span class="w-2 h-2 rounded-full ' + statusColor + ' mr-2"></span>' +
                    '<span class="text-sm text-slate-700">' + device.status + '</span>' +
                    '</div>' +
                    '</td>' +
                    '<td class="p-4">' +  // Column 5: Last Poll
                    '<div class="text-sm">' + device.lastPoll + '</div>' +
                    '</td>' +
                    '<td class="p-4 text-right">' +  // Column 6: Actions
                    '<div class="action-dropdown flex justify-end">' +
                    '<button class="text-slate-500 hover:text-slate-700 text-sm font-medium dropdown-toggle" onclick="window.deviceManagement.toggleDropdown(\'' + device.id + '\')">' +
                    '<i class="fas fa-ellipsis-v"></i>' +  // Three-dot icon instead of "Edit ?"
                    '</button>' +
                    '<div class="action-dropdown-content" id="dropdown-' + device.id + '">' +
                    '<a href="#" onclick="window.deviceManagement.editDevice(\'' + device.id + '\')"><i class="fas fa-edit mr-2"></i>Edit Device</a>' +
                    '<a href="#" onclick="window.deviceManagement.showDeviceDetails(\'' + device.id + '\')"><i class="fas fa-eye mr-2"></i>View Details</a>' +
                    '<a href="#" onclick="window.deviceManagement.duplicateDevice(\'' + device.id + '\')"><i class="fas fa-copy mr-2"></i>Duplicate Device</a>' +
                    '<a href="#" onclick="window.deviceManagement.disableDevice(\'' + device.id + '\')"><i class="fas fa-ban mr-2"></i>' + (device.status === 'Disabled' ? 'Enable Device' : 'Disable Device') + '</a>' +
                    '<a href="#" onclick="window.deviceManagement.deleteDevice(\'' + device.id + '\')" class="text-red-600"><i class="fas fa-trash mr-2"></i>Delete Device</a>' +
                    '</div>' +
                    '</div>' +
                    '</td>';
                
                tbody.appendChild(row);
            });
        }

        function renderFilteredTable(filteredDevices) {
            const tbody = document.getElementById('devicesTableBody');
            if (!tbody) return;
            
            tbody.innerHTML = '';
            
            filteredDevices.forEach(function(device) {
                const row = document.createElement('tr');
                row.className = 'hover:bg-slate-50 transition-colors';
                row.id = 'device-' + device.id;
                row.dataset.deviceId = device.id;
                
                let statusColor = 'bg-green-500';
                if (device.status === 'Offline') {
                    statusColor = 'bg-red-500';
                } else if (device.status === 'Warning') {
                    statusColor = 'bg-yellow-500';
                } else if (device.status === 'Disabled') {
                    statusColor = 'bg-gray-500';
                }
                
                let typeColor = 'bg-blue-100 text-blue-800';
                if (device.type === 'CAN') typeColor = 'bg-orange-100 text-orange-800';
                if (device.type === 'Wireless') typeColor = 'bg-purple-100 text-purple-800';
                if (device.type === 'Modbus TCP') typeColor = 'bg-cyan-100 text-cyan-800';
                if (device.type === 'ACS Sensor') typeColor = 'bg-indigo-100 text-indigo-800';
                
                row.innerHTML = '<td class="p-4">' +  // Column 1: Device Name ONLY
                    '<div class="font-medium text-slate-900">' + device.name + '</div>' +
                    '</td>' +
                    '<td class="p-4">' +  // Column 2: Type
                    '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ' + typeColor + '">' +
                    device.type +
                    '</span>' +
                    '</td>' +
                    '<td class="p-4">' +  // Column 3: Address/ID
                    '<div class="text-sm font-mono">' + device.address + '</div>' +
                    '</td>' +
                    '<td class="p-4">' +  // Column 4: Status
                    '<div class="flex items-center">' +
                    '<span class="w-2 h-2 rounded-full ' + statusColor + ' mr-2"></span>' +
                    '<span class="text-sm text-slate-700">' + device.status + '</span>' +
                    '</div>' +
                    '</td>' +
                    '<td class="p-4">' +  // Column 5: Last Poll
                    '<div class="text-sm">' + device.lastPoll + '</div>' +
                    '</td>' +
                    '<td class="p-4 text-right">' +  // Column 6: Actions
                    '<div class="action-dropdown flex justify-end">' +
                    '<button class="text-slate-500 hover:text-slate-700 text-sm font-medium dropdown-toggle" onclick="window.deviceManagement.toggleDropdown(\'' + device.id + '\')">' +
                    '<i class="fas fa-ellipsis-v"></i>' +  // Three-dot icon instead of "Edit ?"
                    '</button>' +
                    '<div class="action-dropdown-content" id="dropdown-' + device.id + '">' +
                    '<a href="#" onclick="window.deviceManagement.editDevice(\'' + device.id + '\')"><i class="fas fa-edit mr-2"></i>Edit Device</a>' +
                    '<a href="#" onclick="window.deviceManagement.showDeviceDetails(\'' + device.id + '\')"><i class="fas fa-eye mr-2"></i>View Details</a>' +
                    '<a href="#" onclick="window.deviceManagement.duplicateDevice(\'' + device.id + '\')"><i class="fas fa-copy mr-2"></i>Duplicate Device</a>' +
                    '<a href="#" onclick="window.deviceManagement.disableDevice(\'' + device.id + '\')"><i class="fas fa-ban mr-2"></i>' + (device.status === 'Disabled' ? 'Enable Device' : 'Disable Device') + '</a>' +
                    '<a href="#" onclick="window.deviceManagement.deleteDevice(\'' + device.id + '\')" class="text-red-600"><i class="fas fa-trash mr-2"></i>Delete Device</a>' +
                    '</div>' +
                    '</div>' +
                    '</td>';
                
                tbody.appendChild(row);
            });
        }

        function initGroupModal() {
            const colorSelection = document.querySelector('#addGroupModal .flex.space-x-2');
            if (colorSelection) {
                const firstButton = colorSelection.querySelector('button');
                if (firstButton) {
                    firstButton.classList.remove('border-transparent');
                    firstButton.classList.add('border-blue-700');
                }
            }
        }

        // Cleanup function
        function cleanupDeviceManagement() {
            // Close WebSocket
            if (deviceWsConnection) {
                try {
                    deviceWsConnection.close();
                } catch (e) {
                    console.log('Device WebSocket already closed');
                }
                deviceWsConnection = null;
            }
            
            // Clear selected devices
            selectedDevicesForAssignment.clear();
            selectedDeviceId = null;
            selectedGroupId = null;
            
            // Clear arrays
            devices = [];
            groups = [];
            
            // Reset saving flag
            isSaving = false;
            
            console.log('Device management cleanup complete');
        }

        // Expose cleanup method
        window.cleanupDeviceManagement = cleanupDeviceManagement;

        // Make functions available globally
        window.deviceManagement = {
            toggleDropdown: toggleDropdown,
            editDevice: editDevice,
            showDeviceDetails: showDeviceDetails,
            disableDevice: disableDevice,
            deleteDevice: deleteDevice,
            duplicateDevice: duplicateDevice,
            pingDevice: pingDevice,
            getDevicePackets: getDevicePackets,
            openAssignDevicesModal: openAssignDevicesModal,
            toggleDeviceSelection: toggleDeviceSelection,
            assignDevicesToGroup: assignDevicesToGroup,
            addNewGroup: addNewGroup,
            saveNewGroup: saveNewGroup,
            exportDevices: exportDevices,
            importCSVFile: importCSVFile,
            cleanup: cleanupDeviceManagement,
            handleSaveDevice: handleSaveDevice,
            debugDetailsSection: debugDetailsSection
        };

        // Cleanup on page unload
        window.addEventListener('beforeunload', function() {
            cleanupDeviceManagement();
        });
    })(); // End of IIFE
}