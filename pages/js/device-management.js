// device-management.js - Complete Fixed Version with Import/Export and View Details
// Matches backend API structure exactly

if (typeof window.deviceManagementLoaded === 'undefined') {
    window.deviceManagementLoaded = true;
    
    (function() {
        'use strict';
        
        window.initializeDeviceManagement = function() {
            console.log('Device Management page initialized');
            initDeviceManagementApp();
        };

        function initDeviceManagementApp() {
            addDeviceManagementStyles();
            initApp();
        }

        // ==================== STATE ====================
        let devices = [];
        let groups = [];
        let selectedDeviceId = null;
        let selectedColor = 'blue';
        let isSaving = false;
        let deviceWsConnection = null;
        let currentViewingDeviceId = null;
        let currentViewingDevice = null;
        let eventListenersSetup = false; // Flag to prevent duplicate listeners

        // ==================== STYLES ====================
        function addDeviceManagementStyles() {
            if (document.getElementById('device-management-styles')) return;
            
            const style = document.createElement('style');
            style.id = 'device-management-styles';
            style.textContent = `
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
                
                .protocol-config {
                    display: none;
                }
                
                .protocol-config.active {
                    display: block;
                }
                
                .device-type-option input:checked + div {
                    color: #2563EB;
                }
                
                .device-type-option:has(input:checked) {
                    border-color: #2563EB;
                    background-color: #EFF6FF;
                }
                
                .status-dot {
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    display: inline-block;
                    margin-right: 6px;
                }
                
                .status-online { background-color: #10B981; }
                .status-offline { background-color: #EF4444; }
                .status-warning { background-color: #F59E0B; }
                
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
                
                .animate-fade-in {
                    animation: fadeIn 0.3s ease;
                }
                
                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
                
                /* View Details Modal specific styles */
                .device-details-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                }
                
                .detail-section {
                    background: #f8fafc;
                    padding: 16px;
                    border-radius: 8px;
                    border-left: 4px solid #3b82f6;
                }
                
                .detail-section h4 {
                    margin-top: 0;
                    margin-bottom: 12px;
                    color: #1e293b;
                    font-weight: 600;
                    font-size: 0.875rem;
                }
                
                .detail-item {
                    margin-bottom: 8px;
                }
                
                .detail-label {
                    font-size: 0.75rem;
                    color: #64748b;
                    margin-bottom: 2px;
                }
                
                .detail-value {
                    font-size: 0.875rem;
                    color: #1e293b;
                    font-weight: 500;
                }
                
                .config-table {
                    width: 100%;
                    border-collapse: collapse;
                }
                
                .config-table td {
                    padding: 6px 12px;
                    border-bottom: 1px solid #e2e8f0;
                }
                
                .config-table tr:last-child td {
                    border-bottom: none;
                }
                
                /* Refresh button styles */
                .refresh-btn-container {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                
                .refresh-btn {
                    padding: 6px 12px;
                    background: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 6px;
                    color: #64748b;
                    font-size: 14px;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    gap: 4px;
                    transition: all 0.2s;
                }
                
                .refresh-btn:hover {
                    background: #f1f5f9;
                    border-color: #cbd5e1;
                    color: #475569;
                }
                
                .refresh-btn:active {
                    background: #e2e8f0;
                }
                
                .refresh-btn i {
                    font-size: 12px;
                }
                
                .refresh-btn.spinning i {
                    animation: spin 1s linear infinite;
                }
                
                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
            `;
            
            document.head.appendChild(style);
        }

        // ==================== INITIALIZATION ====================
        async function initApp() {
            console.log('Initializing Device Management...');
            
            await loadDevices();
            await loadGroups();
            renderDevicesTable();
            renderGroups();
            setupEventListeners();
            connectDeviceWebSocket();
            
            console.log('Device Management initialized successfully');
        }

        // ==================== DATA LOADING ====================
        async function loadDevices() {
            try {
                const response = await fetch('/api/devices');
                const data = await response.json();
                
                if (data.devices) {
                    devices = data.devices;
                    console.log('Loaded devices:', devices);
                } else {
                    devices = [];
                    console.warn('No devices returned from API');
                }
            } catch (error) {
                console.error('Error loading devices:', error);
                showNotification('Failed to load devices', 'error');
                devices = [];
            }
        }

        async function loadGroups() {
            try {
                const response = await fetch('/api/groups');
                const data = await response.json();
                
                if (data.groups) {
                    groups = data.groups;
                    updateGroupSelect();
                } else {
                    groups = [];
                }
            } catch (error) {
                console.error('Error loading groups:', error);
                groups = [];
            }
        }

        function updateGroupSelect() {
            const groupSelect = document.getElementById('deviceGroupSelect');
            if (!groupSelect) return;
            
            groupSelect.innerHTML = '<option value="">None</option>';
            groups.forEach(group => {
                const option = document.createElement('option');
                option.value = group.name;
                option.textContent = group.name;
                groupSelect.appendChild(option);
            });
        }

        // ==================== RENDERING ====================
        function renderDevicesTable() {
            const tbody = document.getElementById('devicesTableBody');
            if (!tbody) return;
            
            const searchTerm = document.getElementById('searchDevices')?.value.toLowerCase() || '';
            
            let filteredDevices = devices;
            if (searchTerm) {
                filteredDevices = devices.filter(device =>
                    device.name.toLowerCase().includes(searchTerm) ||
                    (device.type && device.type.toLowerCase().includes(searchTerm)) ||
                    (device.protocol && device.protocol.toLowerCase().includes(searchTerm))
                );
            }
            
            if (filteredDevices.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="6" class="px-6 py-8 text-center text-slate-500">
                            <i class="fa-solid fa-inbox text-3xl mb-2 block"></i>
                            <p>No devices found</p>
                        </td>
                    </tr>
                `;
                return;
            }
            
            tbody.innerHTML = '';
            
            filteredDevices.forEach(device => {
                const row = document.createElement('tr');
                row.className = 'hover:bg-slate-50';
                row.id = `device-${device.id}`;
                
                // Get display values
                const deviceTypeBadge = getDeviceTypeBadge(device);
                const statusBadge = getStatusBadge(device);
                const address = getDeviceAddress(device);
                const lastPoll = device.lastPoll || device.last_poll || 'Never';
                
                row.innerHTML = `
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="text-sm font-medium text-slate-900">${escapeHtml(device.name)}</div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        ${deviceTypeBadge}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="text-sm text-slate-700 font-mono text-xs">${escapeHtml(address)}</div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        ${statusBadge}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                        ${escapeHtml(lastPoll)}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button class="text-green-600 hover:text-green-800 mr-3" onclick="window.deviceManagement.viewDevice('${device.id}')" title="View Details">
                            <i class="fa-solid fa-eye"></i>
                        </button>
                        <button class="text-blue-600 hover:text-blue-800 mr-3" onclick="window.deviceManagement.editDevice('${device.id}')" title="Edit">
                            <i class="fa-solid fa-edit"></i>
                        </button>
                        <button class="text-red-600 hover:text-red-800" onclick="window.deviceManagement.deleteDevice('${device.id}')" title="Delete">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </td>
                `;
                
                tbody.appendChild(row);
            });
        }

        function getDeviceAddress(device) {
            if (device.protocol === 'modbus-tcp') {
                return `${device.address || 'Not configured'}`;
            } else if (device.protocol === 'modbus-rtu') {
                return device.address || 'Not configured';
            } else if (device.protocol === 'loadcell') {
                return device.address || 'Not configured';
            }
            return device.address || 'Not configured';
        }

        function getDeviceTypeBadge(device) {
            let badgeClass = 'device-type-badge ';
            let typeText = '';
            
            const protocol = (device.protocol || '').toLowerCase();
            
            if (protocol === 'modbus-tcp' || protocol === 'tcp') {
                badgeClass += 'type-modbus-tcp';
                typeText = 'Modbus TCP';
            } else if (protocol === 'modbus-rtu' || protocol === 'rtu') {
                badgeClass += 'type-modbus-rtu';
                typeText = 'Modbus RTU';
            } else if (protocol === 'loadcell') {
                badgeClass += 'type-loadcell';
                typeText = 'Loadcell';
            } else {
                badgeClass += 'type-modbus-tcp';
                typeText = device.type || 'Unknown';
            }
            
            return `<span class="${badgeClass}">${typeText}</span>`;
        }

        function getStatusBadge(device) {
            const status = device.status || 'Offline';
            let dotClass = 'status-dot ';
            
            if (status === 'Online') {
                dotClass += 'status-online';
            } else if (status === 'Warning') {
                dotClass += 'status-warning';
            } else {
                dotClass += 'status-offline';
            }
            
            return `
                <div class="flex items-center">
                    <span class="${dotClass}"></span>
                    <span class="text-sm text-slate-700">${status}</span>
                </div>
            `;
        }

        function renderGroups() {
            const container = document.getElementById('groupsContainer');
            if (!container) return;
            
            if (groups.length === 0) {
                container.innerHTML = `
                    <div class="col-span-4 text-center py-8 text-slate-500">
                        <i class="fa-solid fa-layer-group text-3xl mb-2 block"></i>
                        <p>No groups created yet</p>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = '';
            
            groups.forEach(group => {
                const groupCard = document.createElement('div');
                groupCard.className = 'border border-slate-200 rounded-lg p-4 hover:shadow-md transition-shadow';
                
                const color = group.color || 'blue';
                const deviceCount = devices.filter(d => d.group === group.name).length;
                
                groupCard.innerHTML = `
                    <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center">
                            <div class="w-3 h-3 rounded-full bg-${color}-500 mr-2"></div>
                            <h3 class="font-medium text-slate-900">${escapeHtml(group.name)}</h3>
                        </div>
                        <button class="text-slate-400 hover:text-red-600" onclick="window.deviceManagement.deleteGroup('${group.id}')" title="Delete Group">
                            <i class="fa-solid fa-trash text-sm"></i>
                        </button>
                    </div>
                    <p class="text-sm text-slate-600">${deviceCount} device${deviceCount !== 1 ? 's' : ''}</p>
                    ${group.description ? `<p class="text-xs text-slate-500 mt-1">${escapeHtml(group.description)}</p>` : ''}
                `;
                
                container.appendChild(groupCard);
            });
        }

        // ==================== VIEW DEVICE DETAILS ====================
        function renderDeviceDetails(device) {
            const contentDiv = document.getElementById('deviceDetailsContent');
            if (!contentDiv) return;
            
            console.log('Rendering device details:', device);
            
            // Create status badge
            let statusBadge = '';
            if (device.status === 'Online') {
                statusBadge = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">Online</span>';
            } else if (device.status === 'Warning') {
                statusBadge = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">Warning</span>';
            } else {
                statusBadge = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">Offline</span>';
            }
            
            // Create type badge
            let typeBadge = '';
            const protocol = device.protocol || '';
            if (protocol.includes('tcp')) {
                typeBadge = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">Modbus TCP</span>';
            } else if (protocol.includes('rtu')) {
                typeBadge = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">Modbus RTU</span>';
            } else if (protocol === 'loadcell') {
                typeBadge = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">Loadcell</span>';
            }
            
            // Get the actual device type from the API response
            let deviceType = device.type || device.device_type || 'Unknown';
            
            // Create details HTML based on device type
            let detailsHtml = '';
            
            if (deviceType === 'Modbus' || deviceType === 'modbus') {
                const config = device.config || {};
                const isTCP = device.protocol === 'modbus-tcp' || device.protocol === 'tcp';
                
                detailsHtml = `
                    <div class="space-y-6">
                        <!-- Basic Information -->
                        <div class="detail-section">
                            <h4 class="font-semibold text-slate-900 mb-3">Basic Information</h4>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div class="detail-item">
                                    <div class="detail-label">Device Name</div>
                                    <div class="detail-value">${escapeHtml(device.name)}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Device Type</div>
                                    <div class="detail-value">${typeBadge}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Status</div>
                                    <div class="detail-value">${statusBadge}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Device ID</div>
                                    <div class="detail-value font-mono">${escapeHtml(device.id)}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Group</div>
                                    <div class="detail-value">${escapeHtml(device.group || 'None')}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Last Polled</div>
                                    <div class="detail-value">${escapeHtml(device.lastPoll || 'Never')}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Protocol</div>
                                    <div class="detail-value">${escapeHtml(device.protocol || 'Unknown')}</div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Connection Details -->
                        <div class="detail-section">
                            <h4 class="font-semibold text-slate-900 mb-3">Connection Details</h4>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                ${isTCP ? `
                                    <div class="detail-item">
                                        <div class="detail-label">IP Address</div>
                                        <div class="detail-value font-mono">${escapeHtml(config.ip_address || device.address || 'Not configured')}</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Port</div>
                                        <div class="detail-value">${config.port || 502}</div>
                                    </div>
                                ` : `
                                    <div class="detail-item">
                                        <div class="detail-label">Serial Port</div>
                                        <div class="detail-value font-mono">${escapeHtml(config.serial_port || device.address || '/dev/ttyUSB0')}</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Baud Rate</div>
                                        <div class="detail-value">${config.baud_rate || 9600}</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Data Bits</div>
                                        <div class="detail-value">${config.data_bits || 8}</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Parity</div>
                                        <div class="detail-value">${config.parity || 'None'}</div>
                                    </div>
                                    <div class="detail-item">
                                        <div class="detail-label">Stop Bits</div>
                                        <div class="detail-value">${config.stop_bits || 1}</div>
                                    </div>
                                `}
                                <div class="detail-item">
                                    <div class="detail-label">Slave Address</div>
                                    <div class="detail-value">${config.slave_id || 1}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Timeout (ms)</div>
                                    <div class="detail-value">${config.timeout_ms || 1000}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Retry Count</div>
                                    <div class="detail-value">${config.retry_count || 3}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Polling Interval (ms)</div>
                                    <div class="detail-value">${config.polling_interval_ms || 100}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            } else if (deviceType === 'Loadcell' || deviceType === 'loadcell') {
                const config = device.config || {};
                
                // Extract calibration and other settings from config
                const calibration = config.calibration || {};
                const service = config.service || {};
                const filters = config.filters || {};
                
                // For backward compatibility, also check direct config properties
                const devicePath = config.device_path || device.address || '/dev/spidev0.0';
                const capacity = config.capacity || calibration.capacity || 40000;
                const unit = calibration.unit || 'g';
                
                detailsHtml = `
                    <div class="space-y-6">
                        <!-- Basic Information -->
                        <div class="detail-section">
                            <h4 class="font-semibold text-slate-900 mb-3">Basic Information</h4>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div class="detail-item">
                                    <div class="detail-label">Device Name</div>
                                    <div class="detail-value">${escapeHtml(device.name)}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Device Type</div>
                                    <div class="detail-value">${typeBadge}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Status</div>
                                    <div class="detail-value">${statusBadge}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Device ID</div>
                                    <div class="detail-value font-mono">${escapeHtml(device.id)}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Group</div>
                                    <div class="detail-value">${escapeHtml(device.group || 'None')}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Last Polled</div>
                                    <div class="detail-value">${escapeHtml(device.lastPoll || 'Never')}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Protocol</div>
                                    <div class="detail-value">${escapeHtml(device.protocol || 'loadcell')}</div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Connection Details -->
                        <div class="detail-section">
                            <h4 class="font-semibold text-slate-900 mb-3">Connection Details</h4>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div class="detail-item">
                                    <div class="detail-label">Device Path</div>
                                    <div class="detail-value font-mono">${escapeHtml(devicePath)}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Channel</div>
                                    <div class="detail-value">${config.channel || 0}</div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Calibration Details -->
                        <div class="detail-section">
                            <h4 class="font-semibold text-slate-900 mb-3">Calibration</h4>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div class="detail-item">
                                    <div class="detail-label">Capacity</div>
                                    <div class="detail-value">${capacity} ${unit}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Tare Offset</div>
                                    <div class="detail-value">${calibration.tare_offset || config.tare_offset || 0}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Known Weight</div>
                                    <div class="detail-value">${calibration.known_weight || config.known_weight || 1000}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Unit</div>
                                    <div class="detail-value">${unit}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Capacity Name</div>
                                    <div class="detail-value">${calibration.capacity_name || 'capacity'}</div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Service Settings -->
                        <div class="detail-section">
                            <h4 class="font-semibold text-slate-900 mb-3">Service Settings</h4>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div class="detail-item">
                                    <div class="detail-label">Polling Interval (ms)</div>
                                    <div class="detail-value">${config.polling_interval_ms || service.polling_interval_ms || 15}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            } else {
                // Fallback for unknown device types
                detailsHtml = `
                    <div class="detail-section">
                        <h4 class="font-semibold text-slate-900 mb-3">Device Information</h4>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div class="detail-item">
                                <div class="detail-label">Device Name</div>
                                <div class="detail-value">${escapeHtml(device.name)}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">Device ID</div>
                                <div class="detail-value font-mono">${escapeHtml(device.id)}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">Type</div>
                                <div class="detail-value">${escapeHtml(deviceType)}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">Status</div>
                                <div class="detail-value">${statusBadge}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">Protocol</div>
                                <div class="detail-value">${escapeHtml(device.protocol || 'Unknown')}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">Last Polled</div>
                                <div class="detail-value">${escapeHtml(device.lastPoll || 'Never')}</div>
                            </div>
                        </div>
                        <div class="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded">
                            <p class="text-sm text-yellow-800">Detailed configuration not available for this device type.</p>
                        </div>
                    </div>
                `;
            }
            
            contentDiv.innerHTML = detailsHtml;
        }

        // ==================== MODAL CONTROL FUNCTIONS ====================
        function openViewModal(deviceId) {
            window.deviceManagement.viewDevice(deviceId);
        }

        function closeViewModal() {
            const modal = document.getElementById('viewDeviceModal');
            if (modal) {
                modal.classList.remove('active');
            }
            currentViewingDeviceId = null;
            currentViewingDevice = null;
        }

        // ==================== DUPLICATE DEVICE FUNCTION ====================
        async function duplicateDevice(deviceId) {
            try {
                console.log(`Duplicating device: ${deviceId}`);
                
                // Call backend duplicate endpoint - it handles device AND datapoints
                const response = await fetch(`/api/devices/${deviceId}/duplicate`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    showNotification(result.message, 'success');
                    console.log(`Device duplicated: ${result.device_name} (ID: ${result.device_id})`);
                    console.log(`Datapoints copied: ${result.datapoints_copied}`);
                    
                    closeViewModal();
                    
                    // Reload devices
                    await loadDevices();
                    renderDevicesTable();
                } else {
                    showNotification('Failed to duplicate device: ' + (result.message || result.error), 'error');
                }
                
            } catch (error) {
                console.error('Error duplicating device:', error);
                showNotification('Error duplicating device: ' + error.message, 'error');
            }
        }

        // ==================== DUPLICATE MODBUS DATAPOINTS ====================
        async function duplicateModbusDatapoints(sourceDeviceId, targetDeviceId) {
            try {
                console.log(`Duplicating datapoints from device ${sourceDeviceId} to ${targetDeviceId}`);
                
                // Load ALL datapoints to filter by source device
                const response = await fetch('/api/datapoints');
                const data = await response.json();
                
                if (!data.datapoints) {
                    console.log('No datapoints found to duplicate');
                    return;
                }
                
                // Filter datapoints for the source device
                const sourceDatapoints = data.datapoints.filter(dp => 
                    dp.device_id === sourceDeviceId && dp.type === 'Modbus'
                );
                
                console.log(`Found ${sourceDatapoints.length} datapoints to duplicate`);
                
                // For each datapoint, create a new one with SAME name
                for (const datapoint of sourceDatapoints) {
                    // Keep the same datapoint name
                    const datapointName = datapoint.name;
                    
                    // Create new datapoint
                    const datapointData = {
                        device_id: targetDeviceId,
                        tag_name: datapointName,
                        register_address: datapoint.register_address,
                        register_type: datapoint.register_type,
                        data_type: datapoint.data_type,
                        byte_order: datapoint.byte_order || 'big',
                        word_order: datapoint.word_order || 'big',
                        scale_factor: datapoint.scale_factor || 1.0,
                        offset: datapoint.offset || 0.0,
                        unit: datapoint.unit || '',
                        description: datapoint.description || ''
                    };
                    
                    console.log(`Creating datapoint: ${datapointName} for device ${targetDeviceId}`);
                    
                    const createResponse = await fetch('/api/datapoints/modbus', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(datapointData)
                    });
                    
                    const result = await createResponse.json();
                    
                    if (!createResponse.ok || !result.success) {
                        console.warn(`Failed to duplicate datapoint ${datapoint.name}:`, result.message);
                    } else {
                        console.log(`Successfully duplicated datapoint: ${datapointName}`);
                    }
                }
                
                console.log('Datapoints duplication completed');
                
            } catch (error) {
                console.error('Error duplicating datapoints:', error);
                // Don't show error notification to user as device was created successfully
            }
        }

        // ==================== DUPLICATE LOADCELL DATAPOINTS ====================
        async function duplicateLoadcellDatapoints(sourceDeviceId, targetDeviceId) {
            try {
                console.log(`Duplicating loadcell datapoints from device ${sourceDeviceId} to ${targetDeviceId}`);
                
                // Get datapoints for the source device
                const response = await fetch(`/api/devices/${sourceDeviceId}/datapoints`);
                const data = await response.json();
                
                if (!data.datapoints || data.datapoints.length === 0) {
                    console.log('No loadcell datapoints found to duplicate');
                    return;
                }
                
                console.log(`Found ${data.datapoints.length} loadcell datapoints to duplicate`);
                
                // For each datapoint, create a new one with SAME name
                for (const datapoint of data.datapoints) {
                    // Keep the same datapoint name
                    const datapointName = datapoint.name;
                    
                    // Create new datapoint
                    const datapointData = {
                        device_id: targetDeviceId,
                        tag_name: datapointName
                    };
                    
                    console.log(`Creating loadcell datapoint: ${datapointName} for device ${targetDeviceId}`);
                    
                    const createResponse = await fetch('/api/datapoints/loadcell', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(datapointData)
                    });
                    
                    const result = await createResponse.json();
                    
                    if (!createResponse.ok || !result.success) {
                        console.warn(`Failed to duplicate loadcell datapoint ${datapoint.name}:`, result.message);
                    } else {
                        console.log(`Successfully duplicated loadcell datapoint: ${datapointName}`);
                    }
                }
                
                console.log('Loadcell datapoints duplication completed');
                
            } catch (error) {
                console.error('Error duplicating loadcell datapoints:', error);
                // Don't show error notification to user as device was created successfully
            }
        }

        // ==================== REFRESH FUNCTION ====================
        async function refreshData() {
            const refreshBtn = document.getElementById('refreshBtn');
            if (refreshBtn) {
                refreshBtn.classList.add('spinning');
                refreshBtn.disabled = true;
            }
            
            try {
                await Promise.all([
                    loadDevices(),
                    loadGroups()
                ]);
                
                renderDevicesTable();
                renderGroups();
                showNotification('Data refreshed successfully', 'success');
            } catch (error) {
                console.error('Error refreshing data:', error);
                showNotification('Failed to refresh data', 'error');
            } finally {
                if (refreshBtn) {
                    refreshBtn.classList.remove('spinning');
                    refreshBtn.disabled = false;
                }
            }
        }

        // ==================== ADD/EDIT DEVICE ====================
        function openAddDevicePanel() {
            selectedDeviceId = null;
            const panel = document.getElementById('addDevicePanel');
            if (panel) {
                panel.classList.add('active');
                
                // Reset form
                document.getElementById('deviceNameInput').value = '';
                document.getElementById('deviceGroupSelect').value = '';
                
                // Select first device type (Modbus RTU)
                const firstRadio = document.querySelector('input[name="device-type"][value="modbus-rtu"]');
                if (firstRadio) {
                    firstRadio.checked = true;
                    switchDeviceType('modbus-rtu');
                }
            }
        }

        function closeAddDevicePanel() {
            const panel = document.getElementById('addDevicePanel');
            if (panel) {
                panel.classList.remove('active');
            }
            selectedDeviceId = null;
        }

        function switchDeviceType(type) {
            const configs = document.querySelectorAll('.protocol-config');
            configs.forEach(config => config.classList.remove('active'));
            
            const selectedConfig = document.getElementById(`${type}-config`);
            if (selectedConfig) {
                selectedConfig.classList.add('active');
            }
        }

        async function saveDevice() {
            if (isSaving) return;
            isSaving = true;
            
            try {
                const deviceName = document.getElementById('deviceNameInput').value.trim();
                if (!deviceName) {
                    showNotification('Please enter a device name', 'error');
                    isSaving = false;
                    return;
                }
                
                const deviceType = document.querySelector('input[name="device-type"]:checked')?.value;
                if (!deviceType) {
                    showNotification('Please select a device type', 'error');
                    isSaving = false;
                    return;
                }
                
                const group = document.getElementById('deviceGroupSelect')?.value || '';
                
                // Build request based on backend API structure
                let requestData = {
                    name: deviceName,
                    group: group,
                    config: {}
                };
                
                if (deviceType === 'modbus-rtu') {
                    requestData.type = 'modbus';
                    requestData.protocol = 'modbus-rtu';
                    requestData.device_type = 'rtu'; // Add device_type for backend
                    requestData.config = {
                        serial_port: document.getElementById('serialPort')?.value || '/dev/ttyUSB0',
                        slave_id: parseInt(document.getElementById('modbusAddress')?.value) || 1,
                        baud_rate: parseInt(document.getElementById('baudRate')?.value) || 9600,
                        data_bits: parseInt(document.getElementById('dataBits')?.value) || 8,
                        parity: document.getElementById('parity')?.value || 'None',
                        stop_bits: parseInt(document.getElementById('stopBits')?.value) || 1,
                        timeout_ms: 1000,
                        retry_count: 3,
                        polling_interval_ms: 100
                    };
                } else if (deviceType === 'modbus-tcp') {
                    requestData.type = 'modbus';
                    requestData.protocol = 'modbus-tcp';
                    requestData.device_type = 'tcp'; // Add device_type for backend
                    requestData.config = {
                        ip_address: document.getElementById('modbusTcpIp')?.value || '192.168.1.100',
                        port: parseInt(document.getElementById('modbusTcpPort')?.value) || 502,
                        slave_id: parseInt(document.getElementById('modbusTcpSlaveAddress')?.value) || 1,
                        timeout_ms: 1000,
                        retry_count: 3,
                        polling_interval_ms: 100
                    };
                } else if (deviceType === 'loadcell') {
                    requestData.type = 'loadcell';
                    requestData.protocol = 'loadcell';
                    requestData.config = {
                        device_path: document.getElementById('devicePath')?.value || '/dev/spidev0.0',
                        channel: 0,
                        capacity: parseFloat(document.getElementById('capacity')?.value) || 40000.0,
                        capacity_name: 'capacity'
                    };
                }
                
                const method = selectedDeviceId ? 'PUT' : 'POST';
                const url = selectedDeviceId ? `/api/devices/${selectedDeviceId}` : '/api/devices';
                
                console.log('Saving device:', requestData);
                
                const response = await fetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestData)
                });
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    showNotification(
                        selectedDeviceId ? 'Device updated successfully' : 'Device added successfully',
                        'success'
                    );
                    closeAddDevicePanel();
                    await loadDevices();
                    renderDevicesTable();
                } else {
                    showNotification('Failed to save device: ' + (result.message || result.error || 'Unknown error'), 'error');
                }
            } catch (error) {
                console.error('Error saving device:', error);
                showNotification('Error saving device: ' + error.message, 'error');
            } finally {
                isSaving = false;
            }
        }

        // ==================== DEVICE ACTIONS ====================
        window.deviceManagement = {
            viewDevice: async function(deviceId) {
                try {
                    // Show modal
                    const modal = document.getElementById('viewDeviceModal');
                    if (modal) {
                        modal.classList.add('active');
                    }
                    
                    // Show loading
                    const contentDiv = document.getElementById('deviceDetailsContent');
                    if (contentDiv) {
                        contentDiv.innerHTML = `
                            <div class="text-center py-8 text-slate-500">
                                <i class="fa-solid fa-spinner fa-spin text-2xl mb-2"></i>
                                <p>Loading device details...</p>
                            </div>
                        `;
                    }
                    
                    // Load device details
                    const response = await fetch(`/api/devices/${deviceId}/details`);
                    const device = await response.json();
                    
                    console.log('Device details API response:', device);
                    
                    if (!device || device.error) {
                        showNotification('Device not found', 'error');
                        return;
                    }
                    
                    // Store device ID for later use
                    currentViewingDeviceId = deviceId;
                    currentViewingDevice = device;
                    
                    // Render device details
                    renderDeviceDetails(device);
                    
                } catch (error) {
                    console.error('Error loading device for view:', error);
                    showNotification('Failed to load device details', 'error');
                }
            },

            editDevice: async function(deviceId) {
                try {
                    // Get device details from API
                    const response = await fetch(`/api/devices/${deviceId}/details`);
                    const device = await response.json();
                    
                    if (!device || device.error) {
                        showNotification('Device not found', 'error');
                        return;
                    }
                    
                    selectedDeviceId = deviceId;
                    
                    // Open panel
                    const panel = document.getElementById('addDevicePanel');
                    if (panel) {
                        panel.classList.add('active');
                    }
                    
                    // Fill common fields
                    document.getElementById('deviceNameInput').value = device.name || '';
                    document.getElementById('deviceGroupSelect').value = device.group || '';
                    
                    // Determine device type from protocol and device_type
                    let deviceTypeValue = 'modbus-rtu';
                    const protocol = device.protocol || '';
                    const deviceType = device.device_type || '';
                    
                    console.log('Editing device:', device);
                    console.log('Protocol:', protocol, 'Device Type:', deviceType);
                    
                    if (protocol === 'modbus-tcp' || deviceType === 'tcp' || device.protocol === 'tcp') {
                        deviceTypeValue = 'modbus-tcp';
                    } else if (protocol === 'modbus-rtu' || deviceType === 'rtu' || device.protocol === 'rtu') {
                        deviceTypeValue = 'modbus-rtu';
                    } else if (protocol === 'loadcell' || device.type === 'Loadcell' || device.type === 'loadcell') {
                        deviceTypeValue = 'loadcell';
                    }
                    
                    console.log('Selected device type value:', deviceTypeValue);
                    
                    // Select device type
                    const deviceTypeRadio = document.querySelector(`input[name="device-type"][value="${deviceTypeValue}"]`);
                    if (deviceTypeRadio) {
                        deviceTypeRadio.checked = true;
                        switchDeviceType(deviceTypeValue);
                    }
                    
                    // Fill device-specific fields
                    setTimeout(() => {
                        const config = device.config || {};
                        
                        if (deviceTypeValue === 'modbus-rtu') {
                            if (document.getElementById('serialPort')) 
                                document.getElementById('serialPort').value = config.serial_port || '/dev/ttyUSB0';
                            if (document.getElementById('modbusAddress')) 
                                document.getElementById('modbusAddress').value = config.slave_id || 1;
                            if (document.getElementById('baudRate')) 
                                document.getElementById('baudRate').value = config.baud_rate || 9600;
                            if (document.getElementById('dataBits')) 
                                document.getElementById('dataBits').value = config.data_bits || 8;
                            if (document.getElementById('parity')) 
                                document.getElementById('parity').value = config.parity || 'None';
                            if (document.getElementById('stopBits')) 
                                document.getElementById('stopBits').value = config.stop_bits || 1;
                        } else if (deviceTypeValue === 'modbus-tcp') {
                            if (document.getElementById('modbusTcpIp')) 
                                document.getElementById('modbusTcpIp').value = config.ip_address || '192.168.1.100';
                            if (document.getElementById('modbusTcpPort')) 
                                document.getElementById('modbusTcpPort').value = config.port || 502;
                            if (document.getElementById('modbusTcpSlaveAddress')) 
                                document.getElementById('modbusTcpSlaveAddress').value = config.slave_id || 1;
                        } else if (deviceTypeValue === 'loadcell') {
                            if (document.getElementById('devicePath')) 
                                document.getElementById('devicePath').value = config.device_path || '/dev/spidev0.0';
                            if (document.getElementById('capacity')) 
                                document.getElementById('capacity').value = config.capacity || 40000;
                        }
                    }, 100);
                    
                } catch (error) {
                    console.error('Error loading device for edit:', error);
                    showNotification('Failed to load device details', 'error');
                }
            },

            deleteDevice: async function(deviceId) {
                if (!confirm('Are you sure you want to delete this device? This action cannot be undone.')) {
                    return;
                }
                
                try {
                    const response = await fetch(`/api/devices/${deviceId}`, {
                        method: 'DELETE'
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok && result.success) {
                        showNotification('Device deleted successfully', 'success');
                        await loadDevices();
                        renderDevicesTable();
                    } else {
                        showNotification('Failed to delete device: ' + (result.message || result.error), 'error');
                    }
                } catch (error) {
                    console.error('Error deleting device:', error);
                    showNotification('Error deleting device: ' + error.message, 'error');
                }
            },

            deleteGroup: async function(groupId) {
                if (!confirm('Are you sure you want to delete this group?')) {
                    return;
                }
                
                // Note: Add group delete API call when backend supports it
                showNotification('Group delete not yet implemented', 'warning');
            }
        };

        // ==================== GROUP MANAGEMENT ====================
        function openAddGroupModal() {
            const modal = document.getElementById('addGroupModal');
            if (modal) {
                modal.classList.add('active');
                document.getElementById('groupNameInput').value = '';
                document.getElementById('groupDescription').value = '';
                selectedColor = 'blue';
                
                // Reset color selection
                document.querySelectorAll('[data-color]').forEach(btn => {
                    btn.classList.remove('border-2');
                    if (btn.dataset.color === 'blue') {
                        btn.classList.add('border-2');
                    }
                });
            }
        }

        function closeAddGroupModal() {
            const modal = document.getElementById('addGroupModal');
            if (modal) {
                modal.classList.remove('active');
            }
        }

        async function saveGroup() {
            const name = document.getElementById('groupNameInput').value.trim();
            if (!name) {
                showNotification('Please enter a group name', 'error');
                return;
            }
            
            const description = document.getElementById('groupDescription').value.trim();
            
            try {
                const response = await fetch('/api/groups', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: name,
                        description: description,
                        color: selectedColor
                    })
                });
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    showNotification('Group created successfully', 'success');
                    closeAddGroupModal();
                    await loadGroups();
                    renderGroups();
                } else {
                    showNotification('Failed to create group: ' + (result.message || result.error), 'error');
                }
            } catch (error) {
                console.error('Error creating group:', error);
                showNotification('Error creating group: ' + error.message, 'error');
            }
        }

        // ==================== IMPORT / EXPORT ====================
        async function exportDevices() {
            try {
                showNotification('Preparing export...', 'info');
                
                const response = await fetch('/api/devices/export/csv');
                
                if (!response.ok) {
                    throw new Error('Export failed');
                }
                
                // Get the blob
                const blob = await response.blob();
                
                // Get filename from Content-Disposition header or use default
                const contentDisposition = response.headers.get('Content-Disposition');
                let filename = 'devices_export.csv';
                if (contentDisposition) {
                    const matches = /filename="(.+)"/.exec(contentDisposition);
                    if (matches && matches[1]) {
                        filename = matches[1];
                    }
                }
                
                // Create download link
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                
                // Cleanup
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                showNotification('Devices exported successfully', 'success');
                
            } catch (error) {
                console.error('Export error:', error);
                showNotification('Failed to export devices: ' + error.message, 'error');
            }
        }

        async function importDevices() {
            const fileInput = document.getElementById('fileInput');
            const file = fileInput?.files[0];
            
            if (!file) {
                showNotification('Please select a CSV file to import', 'error');
                return;
            }
            
            // Validate file type
            if (!file.name.endsWith('.csv')) {
                showNotification('Please select a valid CSV file', 'error');
                return;
            }
            
            try {
                showNotification('Importing devices...', 'info');
                
                // Show import status
                const statusDiv = document.getElementById('importStatus');
                const statusText = document.getElementById('statusText');
                const statusCount = document.getElementById('statusCount');
                const progressBar = document.getElementById('progressBar');
                
                if (statusDiv) {
                    statusDiv.classList.remove('hidden');
                    statusText.textContent = 'Importing...';
                    statusCount.textContent = '0/0 devices';
                    progressBar.style.width = '0%';
                }
                
                // Create FormData
                const formData = new FormData();
                formData.append('file', file);
                
                // Upload file
                const response = await fetch('/api/devices/import/csv', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    // Update progress
                    if (progressBar) {
                        progressBar.style.width = '100%';
                    }
                    if (statusText) {
                        statusText.textContent = 'Import Complete';
                    }
                    if (statusCount) {
                        statusCount.textContent = `${result.imported_count} devices imported`;
                    }
                    
                    // Show success message
                    let message = `Successfully imported ${result.imported_count} device(s)`;
                    if (result.errors && result.errors.length > 0) {
                        message += `\nWarnings: ${result.errors.length} row(s) had errors`;
                        console.warn('Import errors:', result.errors);
                    }
                    
                    showNotification(message, 'success', 5000);
                    
                    // Reload devices
                    await loadDevices();
                    renderDevicesTable();
                    
                    // Clear file input
                    fileInput.value = '';
                    
                    // Hide status after delay
                    setTimeout(() => {
                        if (statusDiv) {
                            statusDiv.classList.add('hidden');
                        }
                    }, 3000);
                    
                } else {
                    throw new Error(result.error || 'Import failed');
                }
                
            } catch (error) {
                console.error('Import error:', error);
                showNotification('Failed to import devices: ' + error.message, 'error');
                
                const statusDiv = document.getElementById('importStatus');
                if (statusDiv) {
                    statusDiv.classList.add('hidden');
                }
            }
        }

        async function downloadCsvTemplate() {
            try {
                const response = await fetch('/api/devices/template/csv');
                
                if (!response.ok) {
                    throw new Error('Failed to download template');
                }
                
                const blob = await response.blob();
                
                // Create download link
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'device_import_template.csv';
                document.body.appendChild(a);
                a.click();
                
                // Cleanup
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                showNotification('Template downloaded', 'success');
                
            } catch (error) {
                console.error('Template download error:', error);
                showNotification('Failed to download template: ' + error.message, 'error');
            }
        }

        function setupImportExportListeners() {
            // Export button
            const exportBtn = document.getElementById('exportBtn');
            if (exportBtn && !exportBtn.hasListener) {
                exportBtn.addEventListener('click', exportDevices);
                exportBtn.hasListener = true;
            }
            
            // Import button
            const importBtn = document.getElementById('importBtn');
            if (importBtn && !importBtn.hasListener) {
                importBtn.addEventListener('click', importDevices);
                importBtn.hasListener = true;
            }
            
            // Template download button
            const templateBtn = document.getElementById('downloadCsvTemplateBtn');
            if (templateBtn && !templateBtn.hasListener) {
                templateBtn.addEventListener('click', downloadCsvTemplate);
                templateBtn.hasListener = true;
            }
            
            // File input
            const fileInput = document.getElementById('fileInput');
            
            if (fileInput && !fileInput.hasListener) {
                fileInput.addEventListener('change', function() {
                    if (importBtn) {
                        importBtn.disabled = !this.files || this.files.length === 0;
                    }
                });
                fileInput.hasListener = true;
            }
            
            // Browse files button
            const browseBtn = document.getElementById('browseFilesBtn');
            if (browseBtn && !browseBtn.hasListener) {
                browseBtn.addEventListener('click', () => {
                    fileInput?.click();
                });
                browseBtn.hasListener = true;
            }
            
            // Drag and drop
            const dropArea = document.getElementById('dropArea');
            
            if (dropArea && !dropArea.hasListener) {
                dropArea.addEventListener('click', () => {
                    fileInput?.click();
                });
                
                dropArea.addEventListener('dragover', (e) => {
                    e.preventDefault();
                    dropArea.classList.add('border-blue-500', 'bg-blue-50');
                });
                
                dropArea.addEventListener('dragleave', (e) => {
                    e.preventDefault();
                    dropArea.classList.remove('border-blue-500', 'bg-blue-50');
                });
                
                dropArea.addEventListener('drop', (e) => {
                    e.preventDefault();
                    dropArea.classList.remove('border-blue-500', 'bg-blue-50');
                    
                    const files = e.dataTransfer.files;
                    if (files.length > 0) {
                        fileInput.files = files;
                        
                        // Trigger change event
                        const event = new Event('change');
                        fileInput.dispatchEvent(event);
                    }
                });
                dropArea.hasListener = true;
            }
        }

        // ==================== WEBSOCKET ====================
        function connectDeviceWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/devices`;
            
            try {
                deviceWsConnection = new WebSocket(wsUrl);
                
                deviceWsConnection.onopen = () => {
                    console.log('Device WebSocket connected');
                };
                
                deviceWsConnection.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (data.type === 'device_status') {
                            updateDeviceStatus(data.device_id, data.status, data.last_poll);
                        }
                    } catch (error) {
                        console.error('WebSocket message error:', error);
                    }
                };
                
                deviceWsConnection.onclose = () => {
                    console.log('Device WebSocket disconnected, reconnecting...');
                    setTimeout(connectDeviceWebSocket, 5000);
                };
            } catch (error) {
                console.error('WebSocket connection error:', error);
            }
        }

        function updateDeviceStatus(deviceId, status, lastPoll) {
            const device = devices.find(d => d.id.toString() === deviceId.toString());
            if (device) {
                device.status = status;
                device.lastPoll = lastPoll;
                renderDevicesTable();
            }
        }

        // ==================== EVENT LISTENERS ====================
        function setupEventListeners() {
            // Prevent duplicate event listeners
            if (eventListenersSetup) {
                return;
            }
            
            eventListenersSetup = true;
            
            // Refresh button
            const refreshBtn = document.getElementById('refreshBtn');
            if (refreshBtn && !refreshBtn.hasListener) {
                refreshBtn.addEventListener('click', refreshData);
                refreshBtn.hasListener = true;
            }
            
            // Add Device
            const addDeviceBtn = document.getElementById('addDeviceBtn');
            const closeAddDevicePanelBtn = document.getElementById('closeAddDevicePanel');
            const cancelAddDeviceBtn = document.getElementById('cancelAddDevice');
            const saveDeviceBtn = document.getElementById('saveDeviceBtn');
            
            if (addDeviceBtn && !addDeviceBtn.hasListener) {
                addDeviceBtn.addEventListener('click', openAddDevicePanel);
                addDeviceBtn.hasListener = true;
            }
            if (closeAddDevicePanelBtn && !closeAddDevicePanelBtn.hasListener) {
                closeAddDevicePanelBtn.addEventListener('click', closeAddDevicePanel);
                closeAddDevicePanelBtn.hasListener = true;
            }
            if (cancelAddDeviceBtn && !cancelAddDeviceBtn.hasListener) {
                cancelAddDeviceBtn.addEventListener('click', closeAddDevicePanel);
                cancelAddDeviceBtn.hasListener = true;
            }
            if (saveDeviceBtn && !saveDeviceBtn.hasListener) {
                saveDeviceBtn.addEventListener('click', saveDevice);
                saveDeviceBtn.hasListener = true;
            }
            
            // Device Type radios
            document.querySelectorAll('input[name="device-type"]').forEach(radio => {
                if (!radio.hasListener) {
                    radio.addEventListener('change', function() {
                        switchDeviceType(this.value);
                    });
                    radio.hasListener = true;
                }
            });
            
            // View Details Modal
            const closeViewModalBtn = document.getElementById('closeViewModal');
            const closeViewDetailsBtn = document.getElementById('closeViewDetailsBtn');
            const editFromViewBtn = document.getElementById('editFromViewBtn');
            const deleteFromViewBtn = document.getElementById('deleteFromViewBtn');
            const duplicateDeviceBtn = document.getElementById('duplicateDeviceBtn');
            
            if (closeViewModalBtn && !closeViewModalBtn.hasListener) {
                closeViewModalBtn.addEventListener('click', closeViewModal);
                closeViewModalBtn.hasListener = true;
            }
            if (closeViewDetailsBtn && !closeViewDetailsBtn.hasListener) {
                closeViewDetailsBtn.addEventListener('click', closeViewModal);
                closeViewDetailsBtn.hasListener = true;
            }
            if (editFromViewBtn && !editFromViewBtn.hasListener) {
                editFromViewBtn.addEventListener('click', function() {
                    if (currentViewingDeviceId) {
                        closeViewModal();
                        setTimeout(() => {
                            window.deviceManagement.editDevice(currentViewingDeviceId);
                        }, 300);
                    }
                });
                editFromViewBtn.hasListener = true;
            }
            if (deleteFromViewBtn && !deleteFromViewBtn.hasListener) {
                deleteFromViewBtn.addEventListener('click', function() {
                    if (currentViewingDeviceId) {
                        if (confirm('Are you sure you want to delete this device?')) {
                            closeViewModal();
                            setTimeout(() => {
                                window.deviceManagement.deleteDevice(currentViewingDeviceId);
                            }, 300);
                        }
                    }
                });
                deleteFromViewBtn.hasListener = true;
            }
            if (duplicateDeviceBtn && !duplicateDeviceBtn.hasListener) {
                duplicateDeviceBtn.addEventListener('click', function() {
                    if (currentViewingDeviceId) {
                        duplicateDevice(currentViewingDeviceId);
                    }
                });
                duplicateDeviceBtn.hasListener = true;
            }
            
            // Add Group
            const addGroupBtn = document.getElementById('addGroupBtn');
            const closeGroupModalBtn = document.getElementById('closeGroupModal');
            const cancelGroupBtn = document.getElementById('cancelGroupBtn');
            const saveGroupBtn = document.getElementById('saveGroupBtn');
            
            if (addGroupBtn && !addGroupBtn.hasListener) {
                addGroupBtn.addEventListener('click', openAddGroupModal);
                addGroupBtn.hasListener = true;
            }
            if (closeGroupModalBtn && !closeGroupModalBtn.hasListener) {
                closeGroupModalBtn.addEventListener('click', closeAddGroupModal);
                closeGroupModalBtn.hasListener = true;
            }
            if (cancelGroupBtn && !cancelGroupBtn.hasListener) {
                cancelGroupBtn.addEventListener('click', closeAddGroupModal);
                cancelGroupBtn.hasListener = true;
            }
            if (saveGroupBtn && !saveGroupBtn.hasListener) {
                saveGroupBtn.addEventListener('click', saveGroup);
                saveGroupBtn.hasListener = true;
            }
            
            // Color selection
            document.querySelectorAll('[data-color]').forEach(btn => {
                if (!btn.hasListener) {
                    btn.addEventListener('click', function() {
                        selectedColor = this.dataset.color;
                        document.querySelectorAll('[data-color]').forEach(b => b.classList.remove('border-2'));
                        this.classList.add('border-2');
                    });
                    btn.hasListener = true;
                }
            });
            
            // Search
            const searchInput = document.getElementById('searchDevices');
            if (searchInput && !searchInput.hasListener) {
                searchInput.addEventListener('input', renderDevicesTable);
                searchInput.hasListener = true;
            }
            
            // Import/Export
            setupImportExportListeners();
            
            console.log('Event listeners setup complete');
        }

        // ==================== UTILITY ====================
        function escapeHtml(text) {
            if (text === null || text === undefined) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function showNotification(message, type = 'info', duration = 3000) {
            const notification = document.createElement('div');
            notification.className = 'fixed top-4 right-4 z-50 max-w-sm animate-fade-in';
            
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
            
            notification.innerHTML = `
                <div class="rounded-lg shadow-lg ${bgColor} text-white p-4 flex items-start justify-between">
                    <div class="flex items-center">
                        <i class="fa-solid ${icon} mr-3"></i>
                        <div class="text-sm font-medium">${message}</div>
                    </div>
                    <button class="ml-4 text-white hover:text-gray-200" onclick="this.parentElement.parentElement.remove()">
                        <i class="fa-solid fa-times"></i>
                    </button>
                </div>
            `;
            
            document.body.appendChild(notification);
            
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, duration);
        }

    })();
}