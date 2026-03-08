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
    let currentViewingDeviceId = null;
    let currentViewingDevice = null;
    let eventListenersBoundToNode = null;
    let isRefreshing = false;

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
            
            .type-virtual {
                background-color: #EDE9FE;
                color: #5B21B6;
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

        await loadDevices();
        renderDevicesTable();
        setupEventListeners();

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

    window.cleanupDeviceManagement = function() {
        eventListenersBoundToNode = null;
        console.log('? Device Management cleaned up');
    };

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
                    <td colspan="8" class="px-6 py-8 text-center text-slate-500">
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
            const protocolBadge = getProtocolBadge(device);
            const address = getDeviceAddress(device);
            
            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="text-xs font-mono text-slate-500">${escapeHtml(device.id)}</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="text-sm font-medium text-slate-900">${escapeHtml(device.name)}</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    ${deviceTypeBadge}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    ${protocolBadge}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="text-sm text-slate-700 font-mono text-xs">${escapeHtml(address)}</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap device-status-cell">&nbsp;</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-500 device-poll-cell">&nbsp;</td>
                <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button class="text-green-600 hover:text-green-800 mr-3" onclick="window.deviceManagement.viewDeviceInline('${device.id}')" title="View Details">
                        <i class="fa-solid fa-eye"></i>
                    </button>
                    <button class="text-blue-600 hover:text-blue-800 mr-3" onclick="window.deviceManagement.editDevice('${device.id}')" title="Edit">
                        <i class="fa-solid fa-edit"></i>
                    </button>
                    <button class="text-amber-600 hover:text-amber-800 mr-3" onclick="window.deviceManagement.duplicateDeviceFromTable('${device.id}')" title="Duplicate">
                        <i class="fa-solid fa-copy"></i>
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
        if (device.protocol === 'vfd-tcp') {
            return `${device.address || 'Not configured'}`;
        } else if (device.protocol === 'vfd-rtu') {
            return device.address || 'Not configured';
        } else if (device.protocol === 'loadcell') {
            return device.address || 'Not configured';
        }
        return device.address || 'Not configured';
    }

    function getDeviceTypeBadge(device) {
        const protocol = (device.protocol || '').toLowerCase();
        let badgeClass = 'device-type-badge ';
        let typeText = '';
        
        if (protocol === 'vfd-tcp' || protocol === 'vfd-rtu' || protocol === 'tcp' || protocol === 'rtu') {
            badgeClass += 'type-modbus-tcp';
            typeText = 'VFD';
        } else if (protocol === 'loadcell') {
            badgeClass += 'type-loadcell';
            typeText = 'Loadcell';
        } else if (protocol === 'virtual') {
            badgeClass += 'type-virtual';
            typeText = 'Virtual';
        } else {
            badgeClass += 'type-modbus-tcp';
            typeText = device.type || 'Unknown';
        }
        
        return `<span class="${badgeClass}">${typeText}</span>`;
    }

    function getProtocolBadge(device) {
        const protocol = (device.protocol || '').toLowerCase();
        let badgeClass = 'device-type-badge ';
        let protoText = '';
        
        if (protocol === 'vfd-tcp' || protocol === 'tcp') {
            badgeClass += 'type-modbus-tcp';
            protoText = 'Modbus TCP';
        } else if (protocol === 'vfd-rtu' || protocol === 'rtu') {
            badgeClass += 'type-modbus-rtu';
            protoText = 'Modbus RTU';
        } else if (protocol === 'loadcell') {
            badgeClass += 'type-loadcell';
            protoText = 'SysFS / IIO';
        } else if (protocol === 'virtual') {
            badgeClass += 'type-virtual';
            protoText = '—';
        } else {
            badgeClass += 'type-modbus-tcp';
            protoText = device.protocol || '—';
        }
        
        return `<span class="${badgeClass}">${protoText}</span>`;
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
        
        if (protocol === 'vfd-tcp' || protocol === 'tcp') {
            typeStyle = { bg: 'bg-blue-50', text: 'text-blue-700', label: 'VFD', proto: 'Modbus TCP' };
        } else if (protocol === 'vfd-rtu' || protocol === 'rtu') {
            typeStyle = { bg: 'bg-green-50', text: 'text-green-700', label: 'VFD', proto: 'Modbus RTU' };
        } else if (protocol === 'loadcell') {
            typeStyle = { bg: 'bg-amber-50', text: 'text-amber-700', label: 'Loadcell', proto: 'SysFS / IIO' };
        } else if (protocol === 'virtual') {
            typeStyle = { bg: 'bg-indigo-50', text: 'text-indigo-700', label: 'Virtual', proto: '—' };
        }
        
        const config = device.config || {};
        const isTCP = protocol === 'vfd-tcp' || protocol === 'tcp';
        
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
                                    <div class="text-xs text-slate-500 mb-0.5">Protocol</div>
                                    <div class="text-sm text-slate-700">${typeStyle.proto || escapeHtml(device.protocol || '—')}</div>
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
        } else if (protocol === 'vfd-rtu') {
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
                                    <div class="text-xs text-slate-500 mb-0.5">SysFS Path</div>
                                    <div class="text-sm font-mono text-slate-700">${escapeHtml(config.device_path || '/sys/bus/iio/devices/iio:device0/in_voltage0_raw')}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Poll Interval (ms)</div>
                                    <div class="text-sm text-slate-700">${config.poll_ms || 10}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Resolution Bits</div>
                                    <div class="text-sm text-slate-700">${config.resolution_bits || 24}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Effective Bits</div>
                                    <div class="text-sm text-slate-700">${config.effective_bits || 14}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Signed</div>
                                    <div class="text-sm text-slate-700">${config.signed ? 'Yes' : 'No'}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Gain</div>
                                    <div class="text-sm text-slate-700">${config.gain ?? 1}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Vref (V)</div>
                                    <div class="text-sm text-slate-700">${config.vref ?? 5}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Raw Range</div>
                                    <div class="text-sm text-slate-700">${config.raw_min ?? 0} � ${config.raw_max ?? 16383}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Capacity Min</div>
                                    <div class="text-sm text-slate-700">${config.capacity_min ?? 0} ${config.unit || 'kg'}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Capacity Max</div>
                                    <div class="text-sm text-slate-700">${config.capacity_max ?? 1000} ${config.unit || 'kg'}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Unit</div>
                                    <div class="text-sm text-slate-700">${config.unit || 'kg'}</div>
                                </div>
            `;
        } else if (protocol === 'virtual') {
            detailsHtml += `
                                <div class="col-span-2">
                                    <div class="p-3 bg-indigo-50 border border-indigo-200 rounded-lg">
                                        <p class="text-xs font-semibold text-indigo-800 mb-2">Auto-created Tags</p>
                                        <div class="flex flex-wrap gap-2">
                                            <span class="inline-flex items-center gap-1 px-2 py-1 bg-indigo-100 text-indigo-700 text-xs font-medium rounded">
                                                <i class="fa-solid fa-network-wired text-xs"></i> lan
                                            </span>
                                            <span class="inline-flex items-center gap-1 px-2 py-1 bg-indigo-100 text-indigo-700 text-xs font-medium rounded">
                                                <i class="fa-solid fa-wifi text-xs"></i> wlan
                                            </span>
                                            <span class="inline-flex items-center gap-1 px-2 py-1 bg-indigo-100 text-indigo-700 text-xs font-medium rounded">
                                                <i class="fa-solid fa-signal text-xs"></i> lte
                                            </span>
                                        </div>
                                    </div>
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
            
            const firstRadio = panel.querySelector('input[name="device-type"][value="vfd"]');
            if (firstRadio) {
                firstRadio.checked = true;
                switchDeviceType('vfd');
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
        const panel = document.getElementById('addDevicePanel');

        // Show/hide protocol sub-section (only visible for VFD)
        const protocolSection = document.getElementById('protocolSelectionSection');
        if (protocolSection) {
            protocolSection.style.display = (type === 'vfd') ? '' : 'none';
        }

        // Resolve VFD -> actual modbus protocol from nested radio
        let resolvedType = type;
        if (type === 'vfd') {
            const vfdProto = panel.querySelector('input[name="vfd-protocol"]:checked');
            resolvedType = vfdProto ? vfdProto.value : 'vfd-rtu';
        }

        const configs = (panel || document).querySelectorAll('.protocol-config');
        configs.forEach(config => config.classList.remove('active'));
        
        const selectedConfig = document.getElementById(`${resolvedType}-config`);
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
            
            const panel = document.getElementById('addDevicePanel');
            let deviceType = document.querySelector('#addDevicePanel input[name="device-type"]:checked')?.value;
            if (!deviceType) {
                showNotification('Please select a device type', 'error');
                isSaving = false;
                return;
            }
            
            let requestData = {
                name: deviceName,
                config: {}
            };
            
            // Resolve VFD -> actual protocol
            if (deviceType === 'vfd') {
                const vfdProto = document.querySelector('#addDevicePanel input[name="vfd-protocol"]:checked')?.value;
                deviceType = vfdProto || 'vfd-rtu';
            }

            if (deviceType === 'vfd-rtu') {
                requestData.type = 'vfd';
                requestData.protocol = 'vfd-rtu';
                requestData.protocol_type = 'rtu';
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
            } else if (deviceType === 'vfd-tcp') {
                requestData.type = 'vfd';
                requestData.protocol = 'vfd-tcp';
                requestData.protocol_type = 'tcp';
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
                    // Device connection
                    device_path: document.getElementById('devicePath')?.value || '/sys/bus/iio/devices/iio:device0/in_voltage0_raw',
                    poll_ms: parseInt(document.getElementById('lcPollMs')?.value) || 10,
                    // ADC hardware parameters
                    resolution_bits: parseInt(document.getElementById('lcResolutionBits')?.value) || 24,
                    effective_bits: parseInt(document.getElementById('lcEffectiveBits')?.value) || 14,
                    signed: document.getElementById('lcSigned')?.value === 'true',
                    gain: parseFloat(document.getElementById('lcGain')?.value) || 1,
                    vref: parseFloat(document.getElementById('lcVref')?.value) || 5,
                    raw_min: parseFloat(document.getElementById('lcRawMin')?.value) || 0,
                    raw_max: parseFloat(document.getElementById('lcRawMax')?.value) || 16383,
                    // Capacity specification
                    capacity_min: parseFloat(document.getElementById('lcCapacityMin')?.value) || 0,
                    capacity_max: parseFloat(document.getElementById('lcCapacityMax')?.value) || 1000,
                    unit: document.getElementById('lcUnit')?.value?.trim() || 'kg',
                    // Auto-generated names (not user input)
                    load_name: 'load_weight',
                    capacity_name: 'capacity'
                };
            } else if (deviceType === 'virtual') {
                requestData.type = 'virtual';
                requestData.protocol = 'virtual';
                requestData.config = {};
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
                
                let deviceTypeValue = 'vfd-rtu';
                const protocol = device.protocol || '';
                
                console.log('Editing device:', device);
                console.log('Protocol:', protocol);
                
                if (protocol === 'vfd-tcp' || protocol === 'tcp') {
                    deviceTypeValue = 'vfd';
                } else if (protocol === 'vfd-rtu' || protocol === 'rtu') {
                    deviceTypeValue = 'vfd';
                } else if (protocol === 'loadcell') {
                    deviceTypeValue = 'loadcell';
                } else if (protocol === 'virtual') {
                    deviceTypeValue = 'virtual';
                }
                
                console.log('Selected device type value:', deviceTypeValue);
                
                const deviceTypeRadio = document.querySelector(`input[name="device-type"][value="${deviceTypeValue}"]`);
                if (deviceTypeRadio) {
                    deviceTypeRadio.checked = true;
                    // For VFD: set the protocol sub-radio based on actual device protocol
                    if (deviceTypeValue === 'vfd') {
                        const vfdProtoVal = (protocol === 'vfd-tcp' || protocol === 'tcp') ? 'vfd-tcp' : 'vfd-rtu';
                        const vfdProtoRadio = panel.querySelector('input[name="vfd-protocol"][value="' + vfdProtoVal + '"]');
                        if (vfdProtoRadio) vfdProtoRadio.checked = true;
                        // Wire vfd-protocol radios
                        panel.querySelectorAll('input[name="vfd-protocol"]').forEach(function(r) {
                            r.addEventListener('change', function() { switchDeviceType('vfd'); });
                        });
                    }
                    switchDeviceType(deviceTypeValue);
                }
                
                setTimeout(() => {
                    const config = device.config || {};
                    
                    if (deviceTypeValue === 'vfd') {
                        const vfdR = document.querySelector('#addDevicePanel input[name="vfd-protocol"]:checked');
                        deviceTypeValue = vfdR ? vfdR.value : 'vfd-rtu';
                    }
                    if (deviceTypeValue === 'vfd-rtu') {
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
                    } else if (deviceTypeValue === 'vfd-tcp') {
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
                            document.getElementById('devicePath').value = config.device_path || '/sys/bus/iio/devices/iio:device0/in_voltage0_raw';
                        if (document.getElementById('lcPollMs'))
                            document.getElementById('lcPollMs').value = config.poll_ms || 10;
                        if (document.getElementById('lcResolutionBits'))
                            document.getElementById('lcResolutionBits').value = config.resolution_bits || 24;
                        if (document.getElementById('lcEffectiveBits'))
                            document.getElementById('lcEffectiveBits').value = config.effective_bits || 14;
                        if (document.getElementById('lcSigned'))
                            document.getElementById('lcSigned').value = config.signed ? 'true' : 'false';
                        if (document.getElementById('lcGain'))
                            document.getElementById('lcGain').value = config.gain ?? 1;
                        if (document.getElementById('lcVref'))
                            document.getElementById('lcVref').value = config.vref ?? 5;
                        if (document.getElementById('lcRawMin'))
                            document.getElementById('lcRawMin').value = config.raw_min ?? 0;
                        if (document.getElementById('lcRawMax'))
                            document.getElementById('lcRawMax').value = config.raw_max ?? 16383;
                        if (document.getElementById('lcCapacityMin'))
                            document.getElementById('lcCapacityMin').value = config.capacity_min ?? 0;
                        if (document.getElementById('lcCapacityMax'))
                            document.getElementById('lcCapacityMax').value = config.capacity_max ?? 1000;
                        if (document.getElementById('lcUnit'))
                            document.getElementById('lcUnit').value = config.unit || 'kg';
                    }
                }, 100);
                
            } catch (error) {
                console.error('Error loading device for edit:', error);
                showNotification('Failed to load device details', 'error');
            }
        },

        deleteDevice: async function(deviceId) {
            const device = devices.find(d => String(d.id) === String(deviceId));
            const deviceName = device ? device.name : 'this device';
            
            const confirmed = await showDeleteConfirmModal(deviceName);
            if (!confirmed) return;
            
            try {
                const response = await fetch(`/api/devices/${deviceId}`, {
                    method: 'DELETE'
                });
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    showNotification('Device and associated datapoints deleted successfully', 'success');
                    const section = document.getElementById('section-details');
                    if (section && currentViewingDeviceId === deviceId) {
                        section.style.display = 'none';
                        currentViewingDeviceId = null;
                    }
                    await refreshData();
                } else {
                    showNotification('Failed to delete device: ' + (result.message || result.error), 'error');
                }
            } catch (error) {
                console.error('Error deleting device:', error);
                showNotification('Error deleting device: ' + error.message, 'error');
            }
        },

        duplicateDeviceFromTable: async function(deviceId) {
            const device = devices.find(d => String(d.id) === String(deviceId));
            const deviceName = device ? device.name : 'this device';
            const confirmed = await showDuplicateDeviceConfirmModal(deviceName);
            if (!confirmed) return;
            await duplicateDevice(deviceId);
        },

        refreshData: refreshData
    };

    // ==================== CONFIRMATION MODALS ====================
    function showDeleteConfirmModal(deviceName) {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:10000;padding:20px;';
            overlay.innerHTML = `
                <div style="background:white;border-radius:12px;padding:28px;max-width:460px;width:100%;box-shadow:0 20px 40px rgba(0,0,0,0.2);">
                    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
                        <div style="width:40px;height:40px;background:#FEF2F2;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                            <i class="fa-solid fa-trash" style="color:#EF4444;font-size:16px;"></i>
                        </div>
                        <div>
                            <h3 style="margin:0;font-size:16px;font-weight:600;color:#1E293B;">Delete Device</h3>
                            <p style="margin:2px 0 0;font-size:13px;color:#64748B;">${escapeHtml(deviceName)}</p>
                        </div>
                    </div>
                    <p style="font-size:14px;color:#374151;margin:0 0 12px;">Are you sure you want to delete this device? This will also permanently delete <strong>all associated tags</strong>.</p>
                    <div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:8px;padding:12px;margin-bottom:20px;display:flex;align-items:flex-start;gap:8px;">
                        <i class="fa-solid fa-triangle-exclamation" style="color:#D97706;margin-top:2px;flex-shrink:0;"></i>
                        <p style="margin:0;font-size:13px;color:#92400E;"><strong>No backup detected.</strong> If you haven't exported your configuration, there is no way to recover this device and its tags after deletion. Consider exporting first.</p>
                    </div>
                    <div style="display:flex;gap:10px;justify-content:flex-end;">
                        <button id="dmDeleteCancelBtn" style="padding:9px 18px;background:white;border:1px solid #CBD5E1;border-radius:8px;font-size:14px;font-weight:500;color:#475569;cursor:pointer;">Cancel</button>
                        <button id="dmDeleteConfirmBtn" style="padding:9px 18px;background:#EF4444;border:none;border-radius:8px;font-size:14px;font-weight:500;color:white;cursor:pointer;">Yes, Delete</button>
                    </div>
                </div>`;
            document.body.appendChild(overlay);
            overlay.querySelector('#dmDeleteCancelBtn').onclick = () => { document.body.removeChild(overlay); resolve(false); };
            overlay.querySelector('#dmDeleteConfirmBtn').onclick = () => { document.body.removeChild(overlay); resolve(true); };
            overlay.onclick = (e) => { if (e.target === overlay) { document.body.removeChild(overlay); resolve(false); } };
        });
    }

    function showDuplicateDeviceConfirmModal(deviceName) {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:10000;padding:20px;';
            overlay.innerHTML = `
                <div style="background:white;border-radius:12px;padding:28px;max-width:460px;width:100%;box-shadow:0 20px 40px rgba(0,0,0,0.2);">
                    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
                        <div style="width:40px;height:40px;background:#EFF6FF;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                            <i class="fa-solid fa-copy" style="color:#3B82F6;font-size:16px;"></i>
                        </div>
                        <div>
                            <h3 style="margin:0;font-size:16px;font-weight:600;color:#1E293B;">Duplicate Device</h3>
                            <p style="margin:2px 0 0;font-size:13px;color:#64748B;">${escapeHtml(deviceName)}</p>
                        </div>
                    </div>
                    <p style="font-size:14px;color:#374151;margin:0 0 16px;">By performing this action, the device will be duplicated along with <strong>all its associated tags</strong>. The new device and all its tags will be named with a <code style="background:#F1F5F9;padding:1px 5px;border-radius:4px;">-001</code> suffix.</p>
                    <div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;padding:12px;margin-bottom:20px;display:flex;align-items:flex-start;gap:8px;">
                        <i class="fa-solid fa-circle-info" style="color:#16A34A;margin-top:2px;flex-shrink:0;"></i>
                        <p style="margin:0;font-size:13px;color:#166534;">Example: <strong>${escapeHtml(deviceName)}</strong> → <strong>${escapeHtml(deviceName)}-001</strong>, and each tag will also get the <code style="background:#DCFCE7;padding:1px 4px;border-radius:3px;">-001</code> suffix.</p>
                    </div>
                    <div style="display:flex;gap:10px;justify-content:flex-end;">
                        <button id="dmDupCancelBtn" style="padding:9px 18px;background:white;border:1px solid #CBD5E1;border-radius:8px;font-size:14px;font-weight:500;color:#475569;cursor:pointer;">Cancel</button>
                        <button id="dmDupConfirmBtn" style="padding:9px 18px;background:#3B82F6;border:none;border-radius:8px;font-size:14px;font-weight:500;color:white;cursor:pointer;">Duplicate Device &amp; Tags</button>
                    </div>
                </div>`;
            document.body.appendChild(overlay);
            overlay.querySelector('#dmDupCancelBtn').onclick = () => { document.body.removeChild(overlay); resolve(false); };
            overlay.querySelector('#dmDupConfirmBtn').onclick = () => { document.body.removeChild(overlay); resolve(true); };
            overlay.onclick = (e) => { if (e.target === overlay) { document.body.removeChild(overlay); resolve(false); } };
        });
    }

    async function duplicateDevice(deviceId) {
        try {
            showNotification('Duplicating device and tags...', 'info');
            const response = await fetch(`/api/devices/${deviceId}/duplicate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const result = await response.json();
            if (response.ok && result.success) {
                showNotification('Device duplicated successfully with all tags (-001 suffix)', 'success');
                await refreshData();
            } else {
                showNotification('Failed to duplicate device: ' + (result.message || result.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            console.error('Error duplicating device:', error);
            showNotification('Error duplicating device: ' + error.message, 'error');
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
            const duplicateNames = duplicates.map(d => `� ${d.name} (${d.type})`).slice(0, 10).join('\n');
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
                <h3 style="margin: 0 0 16px 0; color: #f59e0b;">?? Duplicate Devices Found</h3>
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
            console.log('?? Event listeners already setup, skipping...');
            return;
        }
        eventListenersBoundToNode = anchorNode;
        
        console.log('?? Setting up Device Management event listeners...');
        
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
        
        const addDevicePanel = document.getElementById('addDevicePanel');
        // Wire vfd-protocol radios to update config panel
        document.querySelectorAll('#addDevicePanel input[name="vfd-protocol"]').forEach(function(r) {
            r.addEventListener('change', function() {
                const dt = document.querySelector('#addDevicePanel input[name="device-type"]:checked')?.value;
                if (dt === 'vfd') switchDeviceType('vfd');
            });
        });

        document.querySelectorAll('#addDevicePanel input[name="device-type"]').forEach(radio => {
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
            deleteFromViewBtn.addEventListener('click', async function() {
                if (currentViewingDeviceId) {
                    const device = devices.find(d => String(d.id) === String(currentViewingDeviceId));
                    const deviceName = device ? device.name : 'this device';
                    const confirmed = await showDeleteConfirmModal(deviceName);
                    if (confirmed) {
                        const idToDelete = currentViewingDeviceId;
                        closeInlineView();
                        setTimeout(() => {
                            window.deviceManagement.deleteDevice(idToDelete);
                        }, 300);
                    }
                }
            });
        }
        
        const duplicateDeviceBtn = document.getElementById('duplicateDeviceBtn');
        if (duplicateDeviceBtn) {
            duplicateDeviceBtn.addEventListener('click', async function() {
                if (currentViewingDeviceId) {
                    const device = devices.find(d => String(d.id) === String(currentViewingDeviceId));
                    const deviceName = device ? device.name : 'this device';
                    const confirmed = await showDuplicateDeviceConfirmModal(deviceName);
                    if (confirmed) {
                        await duplicateDevice(currentViewingDeviceId);
                    }
                }
            });
        }
        
        const searchInput = document.getElementById('searchDevices');
        if (searchInput) {
            searchInput.addEventListener('input', renderDevicesTable);
        }
        
        setupImportExportListeners();
        
        console.log('? Device Management event listeners setup complete');
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