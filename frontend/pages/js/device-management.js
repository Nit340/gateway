// device-management.js - Complete Fixed Version with Updated Modbus Parameters

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
    let selectedDeviceId = null;
    let isSaving = false;
    let deviceWsConnection = null;
    let currentViewingDeviceId = null;
    let currentViewingDevice = null;
    let eventListenersBoundToNode = null;
    let isRefreshing = false;

    // ==================== WEBSOCKET FIX PATCH VARIABLES ====================
    let wsConnectionAttempts = 0;
    let wsReconnectTimeout = null;

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
            
            /* View Details specific styles */
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

        wsConnectionAttempts = 0;

        await loadDevices();
        renderDevicesTable();
        setupEventListeners();
        connectDeviceWebSocket();

        console.log('Device Management initialized successfully');

        window.addEventListener('beforeunload', cleanupWebSocket);
        window.addEventListener('pagehide',     cleanupWebSocket);
        window.addEventListener('popstate',     cleanupWebSocket);
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

    // ==================== REFRESH FUNCTIONALITY ====================
    async function refreshData() {
        if (isRefreshing) {
            console.log('Refresh already in progress');
            return;
        }
        
        isRefreshing = true;
        const refreshBtn = document.getElementById('refreshBtn');
        const refreshIcon = refreshBtn?.querySelector('i');
        
        try {
            if (refreshIcon) {
                refreshIcon.classList.add('fa-spin');
            }
            
            console.log('Refreshing device data...');
            
            await loadDevices();
            renderDevicesTable();
                    
            showNotification('Data refreshed successfully', 'success', 2000);
            
        } catch (error) {
            console.error('Error refreshing data:', error);
            showNotification('Failed to refresh data', 'error');
        } finally {
            if (refreshIcon) {
                refreshIcon.classList.remove('fa-spin');
            }
            isRefreshing = false;
        }
    }

    // ==================== WEBSOCKET CONNECTION ====================
    function connectDeviceWebSocket() {
        if (deviceWsConnection && 
            (deviceWsConnection.readyState === WebSocket.OPEN || 
             deviceWsConnection.readyState === WebSocket.CONNECTING)) {
            console.log('Device WebSocket already connected or connecting');
            return;
        }

        if (wsReconnectTimeout) {
            clearTimeout(wsReconnectTimeout);
            wsReconnectTimeout = null;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/devices`;
        
        console.log('Connecting to device WebSocket:', wsUrl);
        
        try {
            deviceWsConnection = new WebSocket(wsUrl);
            
            deviceWsConnection.onopen = () => {
                console.log('Device WebSocket connected');
                wsConnectionAttempts = 0;
                showNotification('Real-time updates enabled', 'success', 2000);
            };
            
            deviceWsConnection.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'initial_devices' && data.devices) {
                        console.log('Received initial device status:', data.devices.length, 'devices');
                        data.devices.forEach(device => {
                            handleDeviceStatusUpdate({
                                type: 'device_status',
                                device_id: device.device_id,
                                status: device.status,
                                last_poll: device.last_poll
                            });
                        });
                    } else {
                        handleDeviceStatusUpdate(data);
                    }
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };
            
            deviceWsConnection.onerror = (error) => {
                console.error('Device WebSocket error:', error);
            };
            
            deviceWsConnection.onclose = () => {
                console.log('Device WebSocket disconnected');
                deviceWsConnection = null;

                if (document.getElementById('devicesTableBody') && wsConnectionAttempts < 5) {
                    wsConnectionAttempts++;
                    const delay = Math.min(1000 * Math.pow(2, wsConnectionAttempts), 30000);
                    console.log(`Reconnecting in ${delay/1000}s (attempt ${wsConnectionAttempts}/5)`);

                    wsReconnectTimeout = setTimeout(() => {
                        connectDeviceWebSocket();
                    }, delay);
                } else if (wsConnectionAttempts >= 5) {
                    console.log('Max WebSocket reconnection attempts reached');
                    const existing = document.getElementById('ws-retry-banner');
                    if (!existing) {
                        const banner = document.createElement('div');
                        banner.id = 'ws-retry-banner';
                        banner.className = 'fixed bottom-4 right-4 z-50 bg-yellow-50 border border-yellow-300 rounded-lg shadow-lg p-4 flex items-center gap-3 max-w-sm';
                        banner.innerHTML = `
                            <i class="fa-solid fa-triangle-exclamation text-yellow-500 text-lg"></i>
                            <span class="text-sm text-yellow-800 flex-1">Real-time updates disconnected.</span>
                            <button id="ws-retry-btn" class="px-3 py-1 text-xs font-semibold bg-yellow-500 text-white rounded hover:bg-yellow-600">Retry</button>
                            <button onclick="this.parentElement.remove()" class="text-yellow-500 hover:text-yellow-700 ml-1"><i class="fa-solid fa-times"></i></button>
                        `;
                        document.body.appendChild(banner);
                        document.getElementById('ws-retry-btn').addEventListener('click', function() {
                            banner.remove();
                            wsConnectionAttempts = 0;
                            connectDeviceWebSocket();
                        });
                    }
                }
            };
        } catch (error) {
            console.error('WebSocket connection error:', error);
        }
    }

    function cleanupWebSocket() {
        if (wsReconnectTimeout) {
            clearTimeout(wsReconnectTimeout);
            wsReconnectTimeout = null;
        }
        
        if (deviceWsConnection) {
            console.log('Closing WebSocket connection...');
            try {
                deviceWsConnection.close();
            } catch (e) {
                console.error('Error closing WebSocket:', e);
            }
            deviceWsConnection = null;
        }
        
        wsConnectionAttempts = 0;
    }

    window.cleanupDeviceManagement = function() {
        cleanupWebSocket();
        eventListenersBoundToNode = null;
        window.removeEventListener('beforeunload', cleanupWebSocket);
        window.removeEventListener('pagehide',     cleanupWebSocket);
        window.removeEventListener('popstate',     cleanupWebSocket);
        console.log('✅ Device Management cleaned up');
    };

    function handleDeviceStatusUpdate(data) {
        if (data.type === 'device_status') {
            const deviceId = data.device_id;
            const status = data.status;
            const lastPoll = data.last_poll;
            
            const device = devices.find(d => d.id === deviceId);
            if (device && device.status !== status) {
                console.log(`Device ${deviceId} status changed: ${device.status} -> ${status}`);
            }
            
            if (device) {
                device.status = status;
                device.lastPoll = lastPoll;
            }
            
            updateDeviceRowUI(deviceId, status, lastPoll);
            
            if (currentViewingDeviceId === deviceId) {
                updateInlineViewStatus(status, lastPoll);
            }
        }
    }

    function updateInlineViewStatus(status, lastPoll) {
        const statusElement = document.getElementById('viewDeviceStatus');
        const pollElement = document.getElementById('viewDeviceLastPoll');
        
        if (statusElement) {
            const statusDotClass = status === 'Online' ? 'status-online' : 
                                 status === 'Warning' ? 'status-warning' : 'status-offline';
            statusElement.innerHTML = `
                <div class="flex items-center gap-1.5">
                    <span class="w-2 h-2 rounded-full ${statusDotClass}"></span>
                    <span class="text-sm text-slate-700">${status}</span>
                </div>
            `;
        }
        
        if (pollElement) {
            pollElement.textContent = lastPoll || 'Never';
        }
    }

    function updateDeviceRowUI(deviceId, status, lastPoll) {
        const row = document.querySelector(`tr[id="device-${deviceId}"]`);
        if (!row) return;
        
        const statusCell = row.querySelector('.device-status-cell');
        if (statusCell) {
            statusCell.innerHTML = getStatusBadge({ status: status, lastPoll: lastPoll });
        }
        
        const pollCell = row.querySelector('.device-poll-cell');
        if (pollCell) {
            pollCell.textContent = lastPoll || 'Never';
        }
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
                        <p>${searchTerm ? 'No devices match your search' : 'No devices found'}</p>
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
                <td class="px-6 py-4 whitespace-nowrap device-status-cell">
                    ${statusBadge}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-500 device-poll-cell">
                    ${escapeHtml(lastPoll)}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button class="text-green-600 hover:text-green-800 mr-3" onclick="window.deviceManagement.viewDeviceInline('${device.id}')" title="View Details">
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
            <div class="flex items-center gap-1.5">
                <span class="${dotClass}"></span>
                <span class="text-sm text-slate-700">${status}</span>
            </div>
        `;
    }

    // ==================== VIEW DEVICE DETAILS ====================
    function renderDeviceDetails(device) {
        const contentDiv = document.getElementById('deviceDetailsContent');
        if (!contentDiv) return;
        
        console.log('Rendering device details:', device);
        
        const statusConfig = {
            'Online': { dot: 'bg-green-500', bg: 'bg-green-50', text: 'text-green-700', label: 'Online' },
            'Warning': { dot: 'bg-yellow-500', bg: 'bg-yellow-50', text: 'text-yellow-700', label: 'Warning' },
            'Offline': { dot: 'bg-red-500', bg: 'bg-red-50', text: 'text-red-700', label: 'Offline' }
        };
        
        const status = device.status || 'Offline';
        const statusStyle = statusConfig[status] || statusConfig['Offline'];
        
        const protocol = (device.protocol || '').toLowerCase();
        let typeStyle = { bg: 'bg-slate-100', text: 'text-slate-700', label: device.type || 'Unknown' };
        
        if (protocol === 'modbus-tcp' || protocol === 'tcp') {
            typeStyle = { bg: 'bg-blue-50', text: 'text-blue-700', label: 'Modbus TCP' };
        } else if (protocol === 'modbus-rtu' || protocol === 'rtu') {
            typeStyle = { bg: 'bg-green-50', text: 'text-green-700', label: 'Modbus RTU' };
        } else if (protocol === 'loadcell') {
            typeStyle = { bg: 'bg-amber-50', text: 'text-amber-700', label: 'Loadcell' };
        }
        
        const config = device.config || {};
        const isTCP = protocol === 'modbus-tcp' || protocol === 'tcp';
        
        let detailsHtml = `
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div class="space-y-4">
                    <div class="bg-white rounded-lg border border-slate-200 overflow-hidden">
                        <div class="px-4 py-2 bg-slate-50 border-b border-slate-200">
                            <h3 class="text-xs font-semibold text-slate-600 uppercase tracking-wider">Basic Information</h3>
                        </div>
                        <div class="p-4">
                            <div class="grid grid-cols-2 gap-3">
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Device Name</div>
                                    <div class="text-sm font-medium text-slate-900">${escapeHtml(device.name)}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Device Type</div>
                                    <div><span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${typeStyle.bg} ${typeStyle.text}">${typeStyle.label}</span></div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Status</div>
                                    <div class="flex items-center gap-1.5">
                                        <span class="w-2 h-2 rounded-full ${statusStyle.dot}"></span>
                                        <span class="text-sm text-slate-700">${status}</span>
                                    </div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Device ID</div>
                                    <div class="text-sm font-mono text-slate-600">${escapeHtml(device.id)}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Last Polled</div>
                                    <div class="text-sm text-slate-700">${escapeHtml(device.lastPoll || 'Never')}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Protocol</div>
                                    <div class="text-sm text-slate-700">${escapeHtml(device.protocol || 'Unknown')}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="space-y-4">
                    <div class="bg-white rounded-lg border border-slate-200 overflow-hidden">
                        <div class="px-4 py-2 bg-slate-50 border-b border-slate-200">
                            <h3 class="text-xs font-semibold text-slate-600 uppercase tracking-wider">Connection Details</h3>
                        </div>
                        <div class="p-4">
                            <div class="grid grid-cols-2 gap-3">
        `;
        
        if (isTCP) {
            detailsHtml += `
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">IP Address</div>
                                    <div class="text-sm font-mono text-slate-700">${escapeHtml(config.ip_address || device.address || '192.168.1.100')}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Port</div>
                                    <div class="text-sm text-slate-700">${config.port || 502}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Response Timeout (ms)</div>
                                    <div class="text-sm text-slate-700">${config.response_timeout_ms || 100}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Byte Timeout (ms)</div>
                                    <div class="text-sm text-slate-700">${config.byte_timeout_ms || 100}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Max Retries</div>
                                    <div class="text-sm text-slate-700">${config.max_retries || 2}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Polling Interval (ms)</div>
                                    <div class="text-sm text-slate-700">${config.polling_interval_ms || 300}</div>
                                </div>
            `;
        } else if (protocol === 'modbus-rtu') {
            detailsHtml += `
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Serial Port</div>
                                    <div class="text-sm font-mono text-slate-700">${escapeHtml(config.serial_port || device.address || '/dev/ttymxc5')}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Baud Rate</div>
                                    <div class="text-sm text-slate-700">${config.baud_rate || 9600}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Data Bits</div>
                                    <div class="text-sm text-slate-700">${config.data_bits || 8}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Parity</div>
                                    <div class="text-sm text-slate-700">${config.parity || 'N'}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Stop Bits</div>
                                    <div class="text-sm text-slate-700">${config.stop_bits || 1}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Response Timeout (ms)</div>
                                    <div class="text-sm text-slate-700">${config.response_timeout_ms || 100}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Byte Timeout (ms)</div>
                                    <div class="text-sm text-slate-700">${config.byte_timeout_ms || 100}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Max Retries</div>
                                    <div class="text-sm text-slate-700">${config.max_retries || 2}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Polling Interval (ms)</div>
                                    <div class="text-sm text-slate-700">${config.polling_interval_ms || 300}</div>
                                </div>
            `;
        } else if (protocol === 'loadcell') {
            detailsHtml += `
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Device Path</div>
                                    <div class="text-sm font-mono text-slate-700">${escapeHtml(config.device_path || device.address || '/dev/spidev0.0')}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Channel</div>
                                    <div class="text-sm text-slate-700">${config.channel || 0}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Capacity</div>
                                    <div class="text-sm text-slate-700">${config.capacity || 40000} g</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Unit</div>
                                    <div class="text-sm text-slate-700">${config.unit || 'g'}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Shift Bits</div>
                                    <div class="text-sm text-slate-700">${config.shift_bits || 10}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Polling Interval (ms)</div>
                                    <div class="text-sm text-slate-700">${config.polling_interval_ms || 15}</div>
                                </div>
            `;
        }
        
        detailsHtml += `
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        contentDiv.innerHTML = detailsHtml;
    }

    // ==================== INLINE VIEW FUNCTIONS ====================
    function closeInlineView() {
        const section = document.getElementById('section-details');
        if (section) {
            section.style.display = 'none';
        }
        currentViewingDeviceId = null;
        currentViewingDevice = null;
        const selectedNameEl = document.getElementById('selectedDeviceName');
        if (selectedNameEl) {
            selectedNameEl.textContent = 'No device selected';
        }
    }

    // ==================== DUPLICATE DEVICE FUNCTION ====================
    async function duplicateDevice(deviceId) {
        try {
            console.log(`Duplicating device: ${deviceId}`);
            
            const response = await fetch(`/api/devices/${deviceId}/duplicate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                showNotification(result.message, 'success');
                console.log(`Device duplicated: ${result.device_name} (ID: ${result.device_id})`);
                
                closeInlineView();
                await refreshData();
            } else {
                showNotification('Failed to duplicate device: ' + (result.message || result.error), 'error');
            }
            
        } catch (error) {
            console.error('Error duplicating device:', error);
            showNotification('Error duplicating device: ' + error.message, 'error');
        }
    }

    // ==================== ADD/EDIT DEVICE ====================
    function openAddDevicePanel() {
        selectedDeviceId = null;
        const panel = document.getElementById('addDevicePanel');
        if (panel) {
            panel.classList.add('active');
            
            document.getElementById('deviceNameInput').value = '';
            
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
            
            let requestData = {
                name: deviceName,
                config: {}
            };
            
            if (deviceType === 'modbus-rtu') {
                requestData.type = 'modbus';
                requestData.protocol = 'modbus-rtu';
                requestData.device_type = 'rtu';
                requestData.config = {
                    serial_port: document.getElementById('serialPort')?.value || '/dev/ttymxc5',
                    baud_rate: parseInt(document.getElementById('baudRate')?.value) || 9600,
                    data_bits: parseInt(document.getElementById('dataBits')?.value) || 8,
                    parity: document.getElementById('parity')?.value || 'N',
                    stop_bits: parseInt(document.getElementById('stopBits')?.value) || 1,
                    response_timeout_ms: parseInt(document.getElementById('responseTimeout')?.value) || 100,
                    byte_timeout_ms: parseInt(document.getElementById('byteTimeout')?.value) || 100,
                    max_retries: parseInt(document.getElementById('maxRetries')?.value) || 2,
                    polling_interval_ms: parseInt(document.getElementById('pollingInterval')?.value) || 300
                };
            } else if (deviceType === 'modbus-tcp') {
                requestData.type = 'modbus';
                requestData.protocol = 'modbus-tcp';
                requestData.device_type = 'tcp';
                requestData.config = {
                    ip_address: document.getElementById('modbusTcpIp')?.value || '192.168.1.100',
                    port: parseInt(document.getElementById('modbusTcpPort')?.value) || 502,
                    response_timeout_ms: parseInt(document.getElementById('tcpResponseTimeout')?.value) || 100,
                    byte_timeout_ms: parseInt(document.getElementById('tcpByteTimeout')?.value) || 100,
                    max_retries: parseInt(document.getElementById('tcpMaxRetries')?.value) || 2,
                    polling_interval_ms: parseInt(document.getElementById('tcpPollingInterval')?.value) || 300
                };
            } else if (deviceType === 'loadcell') {
                requestData.type = 'loadcell';
                requestData.protocol = 'loadcell';
                requestData.config = {
                    device_path: document.getElementById('devicePath')?.value || '/dev/spidev0.0',
                    channel: parseInt(document.getElementById('lcChannel')?.value) || 0,
                    capacity: parseFloat(document.getElementById('capacity')?.value) || 40000.0,
                    unit: document.getElementById('lcUnit')?.value?.trim() || 'g',
                    shift_bits: parseInt(document.getElementById('lcShiftBits')?.value) || 10,
                    polling_interval_ms: parseInt(document.getElementById('lcPollingInterval')?.value) || 15,
                    load_name: 'load',
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
                await refreshData();
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
        viewDeviceInline: async function(deviceId) {
            try {
                const section = document.getElementById('section-details');
                if (section) {
                    section.style.display = 'block';
                }
                
                const contentDiv = document.getElementById('deviceDetailsContent');
                if (contentDiv) {
                    contentDiv.innerHTML = `
                        <div class="flex flex-col items-center justify-center py-12 text-slate-400">
                            <i class="fa-solid fa-spinner fa-spin text-3xl mb-2"></i>
                            <p class="text-sm">Loading device details...</p>
                        </div>
                    `;
                }
                
                const selectedNameEl = document.getElementById('selectedDeviceName');
                if (selectedNameEl) {
                    selectedNameEl.textContent = 'Loading...';
                }
                
                const response = await fetch(`/api/devices/${deviceId}/details`);
                const device = await response.json();
                
                console.log('Device details API response:', device);
                
                if (!device || device.error) {
                    showNotification('Device not found', 'error');
                    return;
                }
                
                currentViewingDeviceId = deviceId;
                currentViewingDevice = device;
                
                if (selectedNameEl) {
                    selectedNameEl.textContent = device.name;
                }
                
                renderDeviceDetails(device);
                
            } catch (error) {
                console.error('Error loading device for view:', error);
                showNotification('Failed to load device details', 'error');
            }
        },

        editDevice: async function(deviceId) {
            try {
                const response = await fetch(`/api/devices/${deviceId}/details`);
                const device = await response.json();
                
                if (!device || device.error) {
                    showNotification('Device not found', 'error');
                    return;
                }
                
                selectedDeviceId = deviceId;
                
                const panel = document.getElementById('addDevicePanel');
                if (panel) {
                    panel.classList.add('active');
                }
                
                document.getElementById('deviceNameInput').value = device.name || '';
                
                let deviceTypeValue = 'modbus-rtu';
                const protocol = device.protocol || '';
                
                console.log('Editing device:', device);
                console.log('Protocol:', protocol);
                
                if (protocol === 'modbus-tcp' || protocol === 'tcp') {
                    deviceTypeValue = 'modbus-tcp';
                } else if (protocol === 'modbus-rtu' || protocol === 'rtu') {
                    deviceTypeValue = 'modbus-rtu';
                } else if (protocol === 'loadcell') {
                    deviceTypeValue = 'loadcell';
                }
                
                console.log('Selected device type value:', deviceTypeValue);
                
                const deviceTypeRadio = document.querySelector(`input[name="device-type"][value="${deviceTypeValue}"]`);
                if (deviceTypeRadio) {
                    deviceTypeRadio.checked = true;
                    switchDeviceType(deviceTypeValue);
                }
                
                setTimeout(() => {
                    const config = device.config || {};
                    
                    if (deviceTypeValue === 'modbus-rtu') {
                        if (document.getElementById('serialPort')) 
                            document.getElementById('serialPort').value = config.serial_port || '/dev/ttymxc5';
                        if (document.getElementById('baudRate')) 
                            document.getElementById('baudRate').value = config.baud_rate || 9600;
                        if (document.getElementById('dataBits')) 
                            document.getElementById('dataBits').value = config.data_bits || 8;
                        if (document.getElementById('parity')) 
                            document.getElementById('parity').value = config.parity || 'N';
                        if (document.getElementById('stopBits')) 
                            document.getElementById('stopBits').value = config.stop_bits || 1;
                        if (document.getElementById('responseTimeout')) 
                            document.getElementById('responseTimeout').value = config.response_timeout_ms || 100;
                        if (document.getElementById('byteTimeout')) 
                            document.getElementById('byteTimeout').value = config.byte_timeout_ms || 100;
                        if (document.getElementById('maxRetries')) 
                            document.getElementById('maxRetries').value = config.max_retries || 2;
                        if (document.getElementById('pollingInterval')) 
                            document.getElementById('pollingInterval').value = config.polling_interval_ms || 300;
                    } else if (deviceTypeValue === 'modbus-tcp') {
                        if (document.getElementById('modbusTcpIp')) 
                            document.getElementById('modbusTcpIp').value = config.ip_address || '192.168.1.100';
                        if (document.getElementById('modbusTcpPort')) 
                            document.getElementById('modbusTcpPort').value = config.port || 502;
                        if (document.getElementById('tcpResponseTimeout')) 
                            document.getElementById('tcpResponseTimeout').value = config.response_timeout_ms || 100;
                        if (document.getElementById('tcpByteTimeout')) 
                            document.getElementById('tcpByteTimeout').value = config.byte_timeout_ms || 100;
                        if (document.getElementById('tcpMaxRetries')) 
                            document.getElementById('tcpMaxRetries').value = config.max_retries || 2;
                        if (document.getElementById('tcpPollingInterval')) 
                            document.getElementById('tcpPollingInterval').value = config.polling_interval_ms || 300;
                    } else if (deviceTypeValue === 'loadcell') {
                        if (document.getElementById('devicePath')) 
                            document.getElementById('devicePath').value = config.device_path || '/dev/spidev0.0';
                        if (document.getElementById('lcChannel'))
                            document.getElementById('lcChannel').value = config.channel ?? 0;
                        if (document.getElementById('capacity')) 
                            document.getElementById('capacity').value = config.capacity || 40000;
                        if (document.getElementById('lcUnit'))
                            document.getElementById('lcUnit').value = config.unit || 'g';
                        if (document.getElementById('lcShiftBits'))
                            document.getElementById('lcShiftBits').value = config.shift_bits ?? 10;
                        if (document.getElementById('lcPollingInterval'))
                            document.getElementById('lcPollingInterval').value = config.polling_interval_ms || 15;
                    }
                }, 100);
                
            } catch (error) {
                console.error('Error loading device for edit:', error);
                showNotification('Failed to load device details', 'error');
            }
        },

        deleteDevice: async function(deviceId) {
            if (!confirm('Are you sure you want to delete this device?\n\nThis will also delete all associated datapoints/tags.\n\nThis action cannot be undone.')) {
                return;
            }
            
            try {
                const response = await fetch(`/api/devices/${deviceId}`, {
                    method: 'DELETE'
                });
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    showNotification('Device and associated datapoints deleted successfully', 'success');
                    await refreshData();
                } else {
                    showNotification('Failed to delete device: ' + (result.message || result.error), 'error');
                }
            } catch (error) {
                console.error('Error deleting device:', error);
                showNotification('Error deleting device: ' + error.message, 'error');
            }
        },

        refreshData: refreshData
    };

    // ==================== IMPORT / EXPORT ====================
    async function exportDevices() {
        try {
            showNotification('Preparing export...', 'info');
            
            const response = await fetch('/api/devices/export/csv');
            
            if (!response.ok) {
                throw new Error('Export failed');
            }
            
            const blob = await response.blob();
            
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'devices_export.csv';
            if (contentDisposition) {
                const matches = /filename="(.+)"/.exec(contentDisposition);
                if (matches && matches[1]) {
                    filename = matches[1];
                }
            }
            
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            
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
        
        if (!file.name.endsWith('.csv')) {
            showNotification('Please select a valid CSV file', 'error');
            return;
        }
        
        try {
            showNotification('Checking for duplicates...', 'info');
            
            const statusDiv = document.getElementById('importStatus');
            const statusText = document.getElementById('statusText');
            const statusCount = document.getElementById('statusCount');
            const progressBar = document.getElementById('progressBar');
            
            if (statusDiv) {
                statusDiv.classList.remove('hidden');
                statusText.textContent = 'Checking...';
                statusCount.textContent = '0/0 devices';
                progressBar.style.width = '0%';
            }
            
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch('/api/devices/import/csv', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.requires_confirmation && result.duplicates && result.duplicates.length > 0) {
                const action = await showDuplicateConfirmation(result.duplicates, result.new_devices_count);
                
                if (action === 'cancel') {
                    showNotification('Import cancelled', 'info');
                    if (statusDiv) statusDiv.classList.add('hidden');
                    return;
                }
                
                const formData2 = new FormData();
                formData2.append('file', file);
                
                const confirmUrl = action === 'skip' 
                    ? '/api/devices/import/csv?skip_existing=true'
                    : '/api/devices/import/csv?replace_existing=true';
                
                statusText.textContent = 'Importing...';
                
                const response2 = await fetch(confirmUrl, {
                    method: 'POST',
                    body: formData2
                });
                
                const result2 = await response2.json();
                
                if (response2.ok && result2.success) {
                    handleImportSuccess(result2, fileInput, statusDiv, statusText, statusCount, progressBar);
                } else {
                    throw new Error(result2.error || 'Import failed');
                }
            } else if (response.ok && result.success) {
                handleImportSuccess(result, fileInput, statusDiv, statusText, statusCount, progressBar);
            } else {
                throw new Error(result.error || 'Import failed');
            }
            
        } catch (error) {
            console.error('Import error:', error);
            showNotification(`Import failed: ${error.message}`, 'error');
            
            const statusDiv = document.getElementById('importStatus');
            if (statusDiv) {
                statusDiv.classList.add('hidden');
            }
        }
    }
    
    function handleImportSuccess(result, fileInput, statusDiv, statusText, statusCount, progressBar) {
        if (progressBar) {
            progressBar.style.width = '100%';
        }
        if (statusText) {
            statusText.textContent = 'Import Complete';
        }
        if (statusCount) {
            let countText = '';
            if (result.imported_count > 0) countText += `${result.imported_count} imported`;
            if (result.replaced_count > 0) countText += `, ${result.replaced_count} replaced`;
            if (result.skipped_count > 0) countText += `, ${result.skipped_count} skipped`;
            statusCount.textContent = countText || '0 devices';
        }
        
        let message = result.message;
        if (result.errors && result.errors.length > 0) {
            message += `\nWarnings: ${result.errors.length} row(s) had errors`;
            console.warn('Import errors:', result.errors);
        }
        
        showNotification(message, 'success', 5000);
        
        refreshData();
        
        if (fileInput) fileInput.value = '';
        
        setTimeout(() => {
            if (statusDiv) {
                statusDiv.classList.add('hidden');
            }
        }, 3000);
    }
    
    function showDuplicateConfirmation(duplicates, newDevicesCount) {
        return new Promise((resolve) => {
            const duplicateNames = duplicates.map(d => `• ${d.name} (${d.type})`).slice(0, 10).join('\n');
            const moreText = duplicates.length > 10 ? `\n... and ${duplicates.length - 10} more` : '';
            
            const message = `Found ${duplicates.length} duplicate device(s) with the same name:\n\n${duplicateNames}${moreText}\n\n${newDevicesCount} new device(s) will be imported.\n\nHow would you like to proceed?`;
            
            const overlay = document.createElement('div');
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
            `;
            
            const dialog = document.createElement('div');
            dialog.style.cssText = `
                background: white;
                padding: 24px;
                border-radius: 8px;
                max-width: 500px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            `;
            
            dialog.innerHTML = `
                <h3 style="margin: 0 0 16px 0; color: #f59e0b;">⚠️ Duplicate Devices Found</h3>
                <p style="white-space: pre-wrap; margin: 16px 0; font-family: monospace; font-size: 13px; color: #666;">${escapeHtml(message)}</p>
                <div style="display: flex; gap: 12px; margin-top: 20px;">
                    <button id="replaceBtn" style="flex: 1; padding: 10px 16px; background: #ef4444; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 500;">
                        Replace Existing
                    </button>
                    <button id="skipBtn" style="flex: 1; padding: 10px 16px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 500;">
                        Skip Duplicates
                    </button>
                    <button id="cancelBtn" style="flex: 1; padding: 10px 16px; background: #6b7280; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 500;">
                        Cancel Import
                    </button>
                </div>
            `;
            
            overlay.appendChild(dialog);
            document.body.appendChild(overlay);
            
            const replaceBtn = dialog.querySelector('#replaceBtn');
            const skipBtn = dialog.querySelector('#skipBtn');
            const cancelBtn = dialog.querySelector('#cancelBtn');
            
            replaceBtn.onclick = () => {
                document.body.removeChild(overlay);
                resolve('replace');
            };
            
            skipBtn.onclick = () => {
                document.body.removeChild(overlay);
                resolve('skip');
            };
            
            cancelBtn.onclick = () => {
                document.body.removeChild(overlay);
                resolve('cancel');
            };
        });
    }

    async function downloadCsvTemplate() {
        try {
            const response = await fetch('/api/devices/template/csv');
            
            if (!response.ok) {
                throw new Error('Failed to download template');
            }
            
            const blob = await response.blob();
            
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'device_import_template.csv';
            document.body.appendChild(a);
            a.click();
            
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showNotification('Template downloaded', 'success');
            
        } catch (error) {
            console.error('Template download error:', error);
            showNotification('Failed to download template: ' + error.message, 'error');
        }
    }

    function setupImportExportListeners() {
        const exportBtn = document.getElementById('exportBtn');
        if (exportBtn && !exportBtn.hasListener) {
            exportBtn.addEventListener('click', exportDevices);
            exportBtn.hasListener = true;
        }
        
        const importBtn = document.getElementById('importBtn');
        if (importBtn && !importBtn.hasListener) {
            importBtn.addEventListener('click', importDevices);
            importBtn.hasListener = true;
        }
        
        const templateBtn = document.getElementById('downloadCsvTemplateBtn');
        if (templateBtn && !templateBtn.hasListener) {
            templateBtn.addEventListener('click', downloadCsvTemplate);
            templateBtn.hasListener = true;
        }
        
        const fileInput = document.getElementById('fileInput');
        
        if (fileInput && !fileInput.hasListener) {
            fileInput.addEventListener('change', function() {
                if (importBtn) {
                    importBtn.disabled = !this.files || this.files.length === 0;
                }
            });
            fileInput.hasListener = true;
        }
        
        const browseBtn = document.getElementById('browseFilesBtn');
        if (browseBtn && !browseBtn.hasListener) {
            browseBtn.addEventListener('click', () => {
                fileInput?.click();
            });
            browseBtn.hasListener = true;
        }
        
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
                    
                    const event = new Event('change');
                    fileInput.dispatchEvent(event);
                }
            });
            dropArea.hasListener = true;
        }
    }

    // ==================== EVENT LISTENERS ====================
    function setupEventListeners() {
        const anchorNode = document.getElementById('addDeviceBtn');
        if (anchorNode && document.contains(anchorNode) && eventListenersBoundToNode === anchorNode) {
            console.log('📌 Event listeners already setup, skipping...');
            return;
        }
        eventListenersBoundToNode = anchorNode;
        
        console.log('📌 Setting up Device Management event listeners...');
        
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', refreshData);
        }
        
        const addDeviceBtn = document.getElementById('addDeviceBtn');
        const closeAddDevicePanelBtn = document.getElementById('closeAddDevicePanel');
        const cancelAddDeviceBtn = document.getElementById('cancelAddDevice');
        const saveDeviceBtn = document.getElementById('saveDeviceBtn');
        
        if (addDeviceBtn) {
            addDeviceBtn.addEventListener('click', openAddDevicePanel);
        }
        if (closeAddDevicePanelBtn) {
            closeAddDevicePanelBtn.addEventListener('click', closeAddDevicePanel);
        }
        if (cancelAddDeviceBtn) {
            cancelAddDeviceBtn.addEventListener('click', closeAddDevicePanel);
        }
        if (saveDeviceBtn) {
            saveDeviceBtn.addEventListener('click', saveDevice);
        }
        
        document.querySelectorAll('input[name="device-type"]').forEach(radio => {
            radio.addEventListener('change', function() {
                switchDeviceType(this.value);
            });
        });
        
        const closeDetailsBtn = document.getElementById('closeDetailsBtn');
        if (closeDetailsBtn) {
            closeDetailsBtn.addEventListener('click', closeInlineView);
        }
        
        const closeViewDetailsBtn = document.getElementById('closeViewDetailsBtn');
        if (closeViewDetailsBtn) {
            closeViewDetailsBtn.addEventListener('click', closeInlineView);
        }
        
        const editFromViewBtn = document.getElementById('editFromViewBtn');
        if (editFromViewBtn) {
            editFromViewBtn.addEventListener('click', function() {
                if (currentViewingDeviceId) {
                    closeInlineView();
                    setTimeout(() => {
                        window.deviceManagement.editDevice(currentViewingDeviceId);
                    }, 300);
                }
            });
        }
        
        const deleteFromViewBtn = document.getElementById('deleteFromViewBtn');
        if (deleteFromViewBtn) {
            deleteFromViewBtn.addEventListener('click', function() {
                if (currentViewingDeviceId) {
                    if (confirm('Are you sure you want to delete this device?')) {
                        closeInlineView();
                        setTimeout(() => {
                            window.deviceManagement.deleteDevice(currentViewingDeviceId);
                        }, 300);
                    }
                }
            });
        }
        
        const duplicateDeviceBtn = document.getElementById('duplicateDeviceBtn');
        if (duplicateDeviceBtn) {
            duplicateDeviceBtn.addEventListener('click', function() {
                if (currentViewingDeviceId) {
                    duplicateDevice(currentViewingDeviceId);
                }
            });
        }
        
        const searchInput = document.getElementById('searchDevices');
        if (searchInput) {
            searchInput.addEventListener('input', renderDevicesTable);
        }
        
        setupImportExportListeners();
        
        console.log('✅ Device Management event listeners setup complete');
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