// device-management.js - Full version with Loadcell limit enforcement and fixed import/export

(function() {
    'use strict';
        
    window.initializeDeviceManagement = function() {

        initDeviceManagementApp();
    };

    function initDeviceManagementApp() {
        addDeviceManagementStyles();
        initApp();
    }

    // ==================== STATE ====================
    let userRole = 'user';
    let devices = [];
    let selectedDeviceId = null;
    let isSaving = false;
    let currentViewingDeviceId = null;
    let currentViewingDevice = null;
    let portConfig = { modbus: [], loadcell: [] };
    let eventListenersBoundToNode = null;
    let isRefreshing = false;
    let pipelineStatus = { modbus_service: null, loadcell_service: null, services: [] };

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
                display: inline-block;
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
            
            .type-external {
                background-color: #F0FDF4;
                color: #166534;
            }
            
            .ext-protocol-config {
                display: block;
            }
            
            .animate-fade-in {
                animation: fadeIn 0.3s ease;
            }
            
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            
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


        await fetchUserRole();
        await loadPortConfig();
        await loadDevices();
        renderDevicesTable();
        setupEventListeners();
        applyRoleAccess();
        startStatusPolling();


    }

    // ==================== ROLE BASED ACCESS ====================
    async function fetchUserRole() {
        try {
            const res = await fetch('/api/auth/session-role', { credentials: 'same-origin' });
            if (res.ok) {
                const data = await res.json();
                userRole = (data.user_role || data.role || window.__userRole || 'user').toLowerCase();
            }
        } catch (e) {
            userRole = (window.__userRole || 'user').toLowerCase();
        }
        window.__userRole = userRole;

    }

    function isAdmin() {
        return userRole === 'admin';
    }

    function applyRoleAccess() {
        const admin = isAdmin();
        _setAdcFieldsEditable(admin);
    }

    function _setAdcFieldsEditable(admin) {
        const protectedInputs = ['lcResolutionBits', 'lcEffectiveBits', 'lcGain', 'lcVref', 'lcRawMin', 'lcRawMax'];
        const protectedSelects = ['lcSigned'];

        protectedInputs.forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            if (admin) {
                el.removeAttribute('readonly');
                el.classList.remove('bg-slate-100', 'text-slate-500', 'cursor-not-allowed');
                el.classList.add('focus:ring-2', 'focus:ring-primary', 'focus:border-primary');
            } else {
                el.setAttribute('readonly', true);
                el.classList.add('bg-slate-100', 'text-slate-500', 'cursor-not-allowed');
            }
        });

        protectedSelects.forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            if (admin) {
                el.removeAttribute('disabled');
                el.classList.remove('bg-slate-100', 'text-slate-500', 'cursor-not-allowed');
            } else {
                el.setAttribute('disabled', true);
                el.classList.add('bg-slate-100', 'text-slate-500', 'cursor-not-allowed');
            }
        });

        const protectedBadges = document.querySelectorAll('#addDevicePanel .fa-lock');
        protectedBadges.forEach(icon => {
            const badge = icon.closest('span');
            if (!badge) return;
            if (admin) {
                badge.innerHTML = '<i class="fa-solid fa-lock-open text-xs"></i> Admin Editable';
                badge.classList.remove('bg-amber-50', 'border-amber-200', 'text-amber-700');
                badge.classList.add('bg-blue-50', 'border-blue-200', 'text-blue-700');
            } else {
                badge.innerHTML = '<i class="fa-solid fa-lock text-xs"></i> Protected';
                badge.classList.remove('bg-blue-50', 'border-blue-200', 'text-blue-700');
                badge.classList.add('bg-amber-50', 'border-amber-200', 'text-amber-700');
            }
        });
    }

    function _setEditPanelAdcFieldsEditable(admin) {
        const editProtectedInputs = ['editLcResolutionBits', 'editLcEffectiveBits', 'editLcGain', 'editLcVref', 'editLcRawMin', 'editLcRawMax'];
        const editProtectedSelects = ['editLcSigned'];

        editProtectedInputs.forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            if (admin) {
                el.removeAttribute('readonly');
                el.classList.remove('bg-slate-100', 'text-slate-500', 'cursor-not-allowed');
                el.classList.add('focus:ring-2', 'focus:ring-primary', 'focus:border-primary');
            } else {
                el.setAttribute('readonly', true);
                el.classList.add('bg-slate-100', 'text-slate-500', 'cursor-not-allowed');
            }
        });

        editProtectedSelects.forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            if (admin) {
                el.removeAttribute('disabled');
                el.classList.remove('bg-slate-100', 'text-slate-500', 'cursor-not-allowed');
            } else {
                el.setAttribute('disabled', true);
                el.classList.add('bg-slate-100', 'text-slate-500', 'cursor-not-allowed');
            }
        });

        const editBadges = document.querySelectorAll('#editDevicePanel .fa-lock, #editDeviceConfigFields .fa-lock');
        editBadges.forEach(icon => {
            const badge = icon.closest('span');
            if (!badge) return;
            if (admin) {
                badge.innerHTML = '<i class="fa-solid fa-lock-open text-xs"></i> Admin Editable';
                badge.classList.remove('bg-amber-50', 'border-amber-200', 'text-amber-700');
                badge.classList.add('bg-blue-50', 'border-blue-200', 'text-blue-700');
            } else {
                badge.innerHTML = '<i class="fa-solid fa-lock text-xs"></i> Protected';
                badge.classList.remove('bg-blue-50', 'border-blue-200', 'text-blue-700');
                badge.classList.add('bg-amber-50', 'border-amber-200', 'text-amber-700');
            }
        });
    }

    // ==================== LOAD PORT CONFIG ====================
    async function loadPortConfig() {
        try {
            const res = await fetch('/api/port-config', { credentials: 'same-origin' });
            const data = await res.json();
            if (data.success && data.ports) {
                portConfig.modbus = data.ports.filter(p => p.device_type === 'modbus');
                portConfig.loadcell = data.ports.filter(p => p.device_type === 'loadcell');
                populatePortDropdowns();
            }
        } catch (e) {
            console.warn('Could not load port config from backend, using defaults:', e);
        }
    }

    function populatePortDropdowns() {
        const serialPortEl = document.getElementById('serialPort');
        if (serialPortEl && portConfig.modbus.length) {
            serialPortEl.innerHTML = portConfig.modbus.map(p =>
                `<option value="${p.port_value}">${p.label}</option>`
            ).join('');
        }

        const extSerialPortEl = document.getElementById('extSerialPort');
        if (extSerialPortEl && portConfig.modbus.length) {
            extSerialPortEl.innerHTML = portConfig.modbus.map(p =>
                `<option value="${p.port_value}">${p.label}</option>`
            ).join('');
        }

        const devicePathEl = document.getElementById('devicePath');
        if (devicePathEl && portConfig.loadcell.length) {
            devicePathEl.innerHTML = portConfig.loadcell.map(p =>
                `<option value="${p.port_value}">${p.label}</option>`
            ).join('');
        }
    }

    // ==================== DATA LOADING ====================
    async function loadDevices() {
        try {
            const response = await fetch('/api/devices', { credentials: 'same-origin' });
            const data = await response.json();
            
            if (data.devices) {
                devices = data.devices;

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

            return;
        }
        
        isRefreshing = true;
        const refreshBtn = document.getElementById('refreshBtn');
        const refreshIcon = refreshBtn?.querySelector('i');
        
        try {
            if (refreshIcon) {
                refreshIcon.classList.add('fa-spin');
            }
            

            
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
        if (_statusPollInterval) { clearInterval(_statusPollInterval); _statusPollInterval = null; }

    };

    // ==================== SERVICE STATUS POLLING ====================
    const lastConnectedAt = { modbus: null, loadcell: null, virtual: null };
    let _statusPollInterval = null;

    function startStatusPolling() {
        fetchAndApplyPipelineStatus();
        _statusPollInterval = setInterval(fetchAndApplyPipelineStatus, 5000);
        setInterval(applyStatusToTable, 30000);
    }

    async function fetchAndApplyPipelineStatus() {
        try {
            const res = await fetch('/api/pipeline/status', { credentials: 'same-origin' });
            const data = await res.json();
            pipelineStatus = {
                modbus_service: data.modbus_service || null,
                loadcell_service: data.loadcell_service || null,
                services: data.services || [],
            };
            const now = new Date();
            if (pipelineStatus.modbus_service) lastConnectedAt.modbus = now;
            if (pipelineStatus.loadcell_service) lastConnectedAt.loadcell = now;
            if (pipelineStatus.services.includes('network_status')) lastConnectedAt.virtual = now;
        } catch (e) {}
        applyStatusToTable();
    }

    function getDeviceOnlineStatus(device) {
        const protocol = (device.protocol || '').toLowerCase();
        if (protocol === 'ext-rtu' || protocol === 'ext-tcp') {
            return pipelineStatus.modbus_service ? 'Online' : 'Offline';
        }
        if (protocol === 'loadcell') {
            return pipelineStatus.loadcell_service ? 'Online' : 'Offline';
        }
        if (protocol === 'virtual') {
            return pipelineStatus.services.includes('network_status') ? 'Online' : 'Offline';
        }
        return 'Offline';
    }

    function buildStatusBadgeHtml(status) {
        if (status === 'Online') {
            return `<div class="flex items-center gap-1.5">
                <span class="status-dot status-online"></span>
                <span class="text-sm text-slate-700">Online</span>
            </div>`;
        }
        return `<div class="flex items-center gap-1.5">
            <span class="status-dot status-offline"></span>
            <span class="text-sm text-slate-700">Offline</span>
        </div>`;
    }

    function applyStatusToTable() {
        // Last Poll column is intentionally left blank
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
                (device.protocol && device.protocol.toLowerCase().includes(searchTerm)) ||
                (device.config && device.config.device_type && 
                 device.config.device_type.toLowerCase().includes(searchTerm))
            );
        }
        
        if (filteredDevices.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" class="px-6 py-8 text-center text-slate-500">
                        <i class="fa-solid fa-inbox text-3xl mb-2 block"></i>
                        <p>${searchTerm ? 'No devices match your search' : 'No devices found'}</p>
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = '';
        
        filteredDevices.forEach((device, idx) => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-slate-50';
            row.id = `device-${device.id}`;
            const rowIndex = idx + 1;
            
            const deviceTypeBadge = getDeviceTypeBadge(device);
            const deviceInitType = getDeviceInitType(device);
            const protocolBadge = getProtocolBadge(device);
            const address = getDeviceAddress(device);
            const status = getDeviceOnlineStatus(device);
            const statusBadge = buildStatusBadgeHtml(status);
            
            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="text-sm text-slate-500">${rowIndex}</div>
                </td>
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
                    <div class="text-sm text-slate-700">${escapeHtml(deviceInitType)}</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    ${protocolBadge}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="text-sm text-slate-700 font-mono text-xs" title="${getAddressTooltip(device)}">${escapeHtml(address)}</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap device-status-cell"></td>
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

    function getDeviceInitType(device) {
        const protocol = (device.protocol || '').toLowerCase();
        
        if (protocol === 'ext-rtu' || protocol === 'ext-tcp') {
            if (device.config && device.config.device_type) {
                return device.config.device_type.charAt(0).toUpperCase() + 
                       device.config.device_type.slice(1);
            }
            return '—';
        }
        
        if (protocol === 'loadcell') {
            return 'Loadcell';
        }
        
        return '—';
    }

    function getDeviceTypeBadge(device) {
        const protocol = (device.protocol || '').toLowerCase();
        let badgeClass = 'device-type-badge ';
        let typeText = '';
        
        if (protocol === 'loadcell') {
            badgeClass += 'type-loadcell';
            typeText = 'Loadcell';
        } else if (protocol === 'ext-rtu' || protocol === 'ext-tcp') {
            badgeClass += 'type-external';
            typeText = 'External';
        } else if (protocol === 'virtual') {
            badgeClass += 'type-virtual';
            typeText = 'Virtual';
        } else {
            badgeClass += 'type-modbus-tcp';
            typeText = device.type || 'Unknown';
        }
        
        return `<span class="${badgeClass}">${escapeHtml(typeText)}</span>`;
    }

    function getProtocolBadge(device) {
        const protocol = (device.protocol || '').toLowerCase();

        if (protocol === 'loadcell' || protocol === 'virtual') {
            return `<span class="text-sm text-slate-400">—</span>`;
        }

        let badgeClass = 'device-type-badge ';
        let protoText = '';

        if (protocol === 'ext-tcp') {
            badgeClass += 'type-modbus-tcp';
            protoText = 'Modbus TCP';
        } else if (protocol === 'ext-rtu') {
            badgeClass += 'type-modbus-rtu';
            protoText = 'Modbus RTU';
        } else {
            badgeClass += 'type-modbus-tcp';
            protoText = device.protocol || '—';
        }

        return `<span class="${badgeClass}">${protoText}</span>`;
    }

    function getAddressTooltip(device) {
        const protocol = (device.protocol || '').toLowerCase();
        if (protocol === 'ext-tcp') {
            return 'TCP/IP Address:Port';
        } else if (protocol === 'ext-rtu') {
            return 'Serial Port';
        } else if (protocol === 'loadcell') {
            const config = device.config || {};
            if (config.lc_mode === 'differential') {
                return 'Differential Mode - Fixed Channel 1';
            } else {
                return 'Single Point Mode - Selected channel';
            }
        }
        return 'Device Address/Identifier';
    }

    function getDeviceAddress(device) {
        if (device.protocol === 'ext-tcp') {
            const config = device.config || {};
            const ip = config.ip_address || device.address || 'Not configured';
            const port = config.port || '502';
            if (ip.includes(':')) return ip;
            return `${ip}:${port}`;
        } else if (device.protocol === 'ext-rtu') {
            const config = device.config || {};
            const serialPort = config.serial_port || device.address || '/dev/ttymxc5';
            const entry = portConfig.modbus.find(p => p.port_value === serialPort);
            return entry ? entry.label : (serialPort === '/dev/ttymxc2' ? 'Port 2' : 'Port 1');
        } else if (device.protocol === 'loadcell') {
            const config = device.config || {};
            const lcMode = config.lc_mode || 'single_ended';
            if (lcMode === 'single_ended') {
                const entry = portConfig.loadcell.find(p => p.port_value === config.device_path);
                return entry ? entry.label : 'Channel 1';
            } else {
                return 'Channel 1';
            }
        }
        return device.address || 'Not configured';
    }

    // ==================== VIEW DEVICE DETAILS ====================
    function renderDeviceDetails(device) {
        const contentDiv = document.getElementById('deviceDetailsContent');
        if (!contentDiv) return;
        
        const status = getDeviceOnlineStatus(device);
        const statusStyle = status === 'Online'
            ? { dot: 'bg-green-500', bg: 'bg-green-50', text: 'text-green-700', label: 'Online' }
            : { dot: 'bg-red-500',   bg: 'bg-red-50',   text: 'text-red-700',   label: 'Offline' };
        
        const protocol = (device.protocol || '').toLowerCase();
        let typeStyle = { bg: 'bg-slate-100', text: 'text-slate-700', label: device.type || 'Unknown' };
        
        if (protocol === 'loadcell') {
            typeStyle = { bg: 'bg-amber-50', text: 'text-amber-700', label: 'Loadcell', proto: null };
        } else if (protocol === 'virtual') {
            typeStyle = { bg: 'bg-indigo-50', text: 'text-indigo-700', label: 'Virtual', proto: '—' };
        } else if (protocol === 'ext-rtu' || protocol === 'ext-tcp') {
            typeStyle = { 
                bg: protocol === 'ext-rtu' ? 'bg-green-50' : 'bg-blue-50', 
                text: protocol === 'ext-rtu' ? 'text-green-700' : 'text-blue-700', 
                label: 'External',
                proto: protocol === 'ext-rtu' ? 'Modbus RTU' : 'Modbus TCP'
            };
        }
        
        const deviceInitType = getDeviceInitType(device);
        const config = device.config || {};
        const isTCP = protocol === 'ext-tcp';
        const isRTU = protocol === 'ext-rtu';
        
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
                                    <div class="text-xs text-slate-500 mb-0.5">Device</div>
                                    <div><span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${typeStyle.bg} ${typeStyle.text}">${typeStyle.label}</span></div>
                                </div>
        `;
        
        if ((isRTU || isTCP) && deviceInitType !== '—') {
            detailsHtml += `
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Device Type</div>
                                    <div class="text-sm font-medium text-slate-900">${escapeHtml(deviceInitType)}</div>
                                </div>
            `;
        }
        
        if ((isRTU || isTCP) && config.model_name) {
            detailsHtml += `
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Model Name</div>
                                    <div class="text-sm text-slate-700">${escapeHtml(config.model_name)}</div>
                                </div>
            `;
        }
        
        detailsHtml += `
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Device ID</div>
                                    <div class="text-sm font-mono text-slate-600">${escapeHtml(device.id)}</div>
                                </div>`;

        if (isRTU || isTCP) {
            detailsHtml += `
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Protocol</div>
                                    <div class="text-sm text-slate-700">${typeStyle.proto || escapeHtml(device.protocol || '—')}</div>
                                </div>`;
        }

        detailsHtml += `
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
                                    <div class="text-xs text-slate-500 mb-0.5">Slave ID</div>
                                    <div class="text-sm text-slate-700">${config.slave_id || 1}</div>
                                </div>
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
        } else if (isRTU) {
            const rtuPortEntry = portConfig.modbus.find(p => p.port_value === config.serial_port);
            const rtuPortLabel = rtuPortEntry ? rtuPortEntry.label : (config.serial_port === '/dev/ttymxc2' ? 'Port 2' : 'Port 1');
            detailsHtml += `
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Slave ID</div>
                                    <div class="text-sm text-slate-700">${config.slave_id || 1}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Serial Port</div>
                                    <div class="text-sm font-mono text-slate-700">${rtuPortLabel}</div>
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
            const lcMode = config.lc_mode || 'single_ended';
            const lcModeLabel = lcMode === 'single_ended' ? 'Single Point' : 'Differential';

            if (lcMode === 'single_ended') {
                const chEntry = portConfig.loadcell.find(p => p.port_value === config.device_path);
                const chLabel = chEntry ? chEntry.label : 'Channel 1';
                detailsHtml += `
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Mode</div>
                                    <div class="text-sm text-slate-700">${lcModeLabel}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Channel</div>
                                    <div class="text-sm font-mono text-slate-700">${chLabel}</div>
                                </div>
                `;
            } else {
                detailsHtml += `
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Mode</div>
                                    <div class="text-sm text-slate-700">${lcModeLabel}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Channel</div>
                                    <div class="text-sm font-mono text-slate-700">Channel 1 (fixed)</div>
                                </div>
                `;
            }
            
            detailsHtml += `
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
                                    <div class="text-sm text-slate-700">${config.raw_min ?? 0} to ${config.raw_max ?? 16383}</div>
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
                                    <div class="text-xs text-slate-500 mb-0.5">Deadband</div>
                                    <div class="text-sm text-slate-700">${config.deadband ?? 0} ${config.unit || 'kg'}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Overload</div>
                                    <div class="text-sm text-slate-700">${config.overload ?? 0} ${config.unit || 'kg'}</div>
                                </div>
                                <div>
                                    <div class="text-xs text-slate-500 mb-0.5">Unit</div>
                                    <div class="text-sm text-slate-700 font-semibold">
                                        ${config.unit === 'ton'
                                            ? '<span class="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 border border-blue-200 text-blue-700 text-xs font-semibold rounded">ton <span class="font-normal text-blue-500">Metric Ton</span></span>'
                                            : '<span class="inline-flex items-center gap-1 px-2 py-0.5 bg-orange-50 border border-orange-200 text-orange-700 text-xs font-semibold rounded">kg <span class="font-normal text-orange-500">Kilogram</span></span>'
                                        }
                                    </div>
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

    // ==================== ADD DEVICE ====================
    function openAddDevicePanel() {
        selectedDeviceId = null;
        const panel = document.getElementById('addDevicePanel');
        if (panel) {
            panel.classList.add('active');
            populatePortDropdowns();
            document.getElementById('deviceNameInput').value = '';
            document.getElementById('extDeviceTypeInit').value = '';
            document.getElementById('extModelName').value = '';

            const loadcellCount = devices.filter(d => d.protocol === 'loadcell').length;

            const lcRadio = panel.querySelector('input[name="device-type"][value="loadcell"]');
            const lcLabel = lcRadio ? lcRadio.closest('label') : null;
            if (lcRadio) {
                lcRadio.disabled = loadcellCount >= 2;
                if (lcLabel) {
                    lcLabel.title = loadcellCount >= 2 ? 'Maximum 2 Loadcell devices allowed' : '';
                    lcLabel.style.opacity = loadcellCount >= 2 ? '0.45' : '';
                    lcLabel.style.cursor = loadcellCount >= 2 ? 'not-allowed' : '';
                }
            }

            const deviceTypeRadios = panel.querySelectorAll('input[name="device-type"]');
            deviceTypeRadios.forEach(radio => {
                radio.removeEventListener('change', handleDeviceTypeChangeWithLimit);
                radio.addEventListener('change', handleDeviceTypeChangeWithLimit);
            });

            const singleEndedRadio = panel.querySelector('input[name="lc-mode"][value="single_ended"]');
            if (singleEndedRadio) {
                singleEndedRadio.checked = true;
                handleLcModeChange();
            }

            panel.querySelectorAll('input[name="ext-protocol"]').forEach(r => {
                r.removeEventListener('change', handleExtProtocolChange);
                r.addEventListener('change', handleExtProtocolChange);
            });

            const lcDefaultRadio = panel.querySelector('input[name="device-type"][value="loadcell"]');
            if (lcDefaultRadio && !lcDefaultRadio.disabled) {
                lcDefaultRadio.checked = true;
                switchDeviceType('loadcell');
            } else {
                const extRadio = panel.querySelector('input[name="device-type"][value="external"]');
                if (extRadio) {
                    extRadio.checked = true;
                    switchDeviceType('external');
                }
            }
        }
    }

    function handleDeviceTypeChangeWithLimit(event) {
        const selectedValue = event.target.value;
        const loadcellCount = devices.filter(d => d.protocol === 'loadcell').length;
        
        if (selectedValue === 'loadcell' && loadcellCount >= 2) {
            showNotification('Maximum 2 Loadcell devices allowed. Please delete an existing one first.', 'warning');
            const extRadio = document.querySelector('#addDevicePanel input[name="device-type"][value="external"]');
            if (extRadio) {
                extRadio.checked = true;
                switchDeviceType('external');
            }
            return;
        }
        
        switchDeviceType(selectedValue);
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

        const configs = (panel || document).querySelectorAll('.protocol-config');
        configs.forEach(config => config.classList.remove('active'));

        const configIdMap = {
            'loadcell': 'loadcell-config',
            'external': 'external-config',
        };
        const configDivId = configIdMap[type] || (type + '-config');
        const selectedConfig = document.getElementById(configDivId);
        if (selectedConfig) {
            selectedConfig.classList.add('active');
        }

        if (type === 'loadcell') {
            document.querySelectorAll('input[name="lc-mode"]').forEach(r => {
                r.removeEventListener('change', handleLcModeChange);
                r.addEventListener('change', handleLcModeChange);
            });
            handleLcModeChange();
        }

        if (type === 'external') {
            document.querySelectorAll('input[name="ext-protocol"]').forEach(r => {
                r.removeEventListener('change', handleExtProtocolChange);
                r.addEventListener('change', handleExtProtocolChange);
            });
            handleExtProtocolChange();
        }
    }

    function handleExtProtocolChange() {
        const proto = document.querySelector('input[name="ext-protocol"]:checked')?.value || 'ext-rtu';
        const rtuEl = document.getElementById('ext-rtu-config');
        const tcpEl = document.getElementById('ext-tcp-config');
        if (rtuEl) rtuEl.style.display = proto === 'ext-rtu' ? 'block' : 'none';
        if (tcpEl) tcpEl.style.display = proto === 'ext-tcp' ? 'block' : 'none';
    }

    function handleLcModeChange() {
        const mode = document.querySelector('input[name="lc-mode"]:checked')?.value || 'single_ended';
        const singleEl = document.getElementById('lcSingleEndedChannels');
        const diffEl = document.getElementById('lcDifferentialInfo');
        if (singleEl) singleEl.style.display = mode === 'single_ended' ? 'block' : 'none';
        if (diffEl) diffEl.style.display = mode === 'differential' ? 'block' : 'none';
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
            
            let deviceType = document.querySelector('#addDevicePanel input[name="device-type"]:checked')?.value;
            if (!deviceType) {
                showNotification('Please select a device type', 'error');
                isSaving = false;
                return;
            }
            
            const duplicateName = devices.find(d => d.name.trim().toLowerCase() === deviceName.toLowerCase());
            if (duplicateName) {
                showNotification(`A device named "${deviceName}" already exists. Please use a different name.`, 'error');
                isSaving = false;
                return;
            }

            if (!selectedDeviceId) {
                if (deviceType === 'loadcell') {
                    const existing = devices.filter(d => d.protocol === 'loadcell').length;
                    if (existing >= 2) {
                        showNotification('Maximum 2 Loadcell devices allowed. Delete an existing one first.', 'error');
                        isSaving = false;
                        return;
                    }
                }
            }

            let requestData = {
                name: deviceName,
                config: {}
            };
            
            if (deviceType === 'loadcell') {
                requestData.type = 'loadcell';
                requestData.protocol = 'loadcell';
                const lcMode = document.querySelector('input[name="lc-mode"]:checked')?.value || 'single_ended';

                const defaultCh1 = portConfig.loadcell[0]?.port_value ?? '/sys/bus/iio/devices/iio:device0/in_voltage0_raw';

                let devicePath;
                if (lcMode === 'single_ended') {
                    devicePath = document.getElementById('devicePath')?.value || defaultCh1;
                } else {
                    devicePath = defaultCh1;
                }
                
                requestData.config = {
                    lc_mode: lcMode,
                    device_path: devicePath,
                    poll_ms: parseInt(document.getElementById('lcPollMs')?.value) || 10,
                    resolution_bits: parseInt(document.getElementById('lcResolutionBits')?.value) || 24,
                    effective_bits: parseInt(document.getElementById('lcEffectiveBits')?.value) || 14,
                    signed: document.getElementById('lcSigned')?.value === 'true',
                    gain: parseFloat(document.getElementById('lcGain')?.value) ?? 1,
                    vref: parseFloat(document.getElementById('lcVref')?.value) ?? 5,
                    raw_min: parseInt(document.getElementById('lcRawMin')?.value) ?? 0,
                    raw_max: parseInt(document.getElementById('lcRawMax')?.value) ?? 16383,
                    capacity_min: parseFloat(document.getElementById('lcCapacityMin')?.value) || 0,
                    capacity_max: parseFloat(document.getElementById('lcCapacityMax')?.value) || 1000,
                    deadband: parseFloat(document.getElementById('lcDeadband')?.value) || 0,
                    overload: parseFloat(document.getElementById('lcOverload')?.value) || 0,
                    unit: document.getElementById('lcUnit')?.value?.trim() || 'kg',
                    load_name: 'load_weight',
                    capacity_name: 'capacity'
                };
            } else if (deviceType === 'external') {
                const extProto = document.querySelector('#addDevicePanel input[name="ext-protocol"]:checked')?.value || 'ext-rtu';
                const extDeviceTypeInit = document.getElementById('extDeviceTypeInit')?.value?.trim() || '';
                const extModelName = document.getElementById('extModelName')?.value?.trim() || '';
                
                if (!extDeviceTypeInit) {
                    showNotification('Please enter a Device Type (e.g., VFD, Sensor, Meter)', 'error');
                    isSaving = false;
                    return;
                }
                
                if (extProto === 'ext-rtu') {
                    requestData.type = 'external';
                    requestData.protocol = 'ext-rtu';
                    requestData.protocol_type = 'rtu';
                    requestData.device_type_init = extDeviceTypeInit;
                    requestData.model_name = extModelName;
                    requestData.config = {
                        slave_id: parseInt(document.getElementById('extRtuSlaveId')?.value) || 1,
                        serial_port: document.getElementById('extSerialPort')?.value || '/dev/ttymxc5',
                        baud_rate: parseInt(document.getElementById('extBaudRate')?.value) || 9600,
                        data_bits: parseInt(document.getElementById('extDataBits')?.value) || 8,
                        parity: document.getElementById('extParity')?.value || 'N',
                        stop_bits: parseInt(document.getElementById('extStopBits')?.value) || 1,
                        response_timeout_ms: parseInt(document.getElementById('extRtuResponseTimeout')?.value) || 100,
                        byte_timeout_ms: parseInt(document.getElementById('extRtuByteTimeout')?.value) || 100,
                        max_retries: parseInt(document.getElementById('extRtuMaxRetries')?.value) || 2,
                        polling_interval_ms: parseInt(document.getElementById('extRtuPollingInterval')?.value) || 300
                    };
                } else {
                    requestData.type = 'external';
                    requestData.protocol = 'ext-tcp';
                    requestData.protocol_type = 'tcp';
                    requestData.device_type_init = extDeviceTypeInit;
                    requestData.model_name = extModelName;
                    requestData.config = {
                        slave_id: parseInt(document.getElementById('extTcpSlaveId')?.value) || 1,
                        ip_address: document.getElementById('extTcpIp')?.value || '192.168.1.100',
                        port: parseInt(document.getElementById('extTcpPort')?.value) || 502,
                        response_timeout_ms: parseInt(document.getElementById('extTcpResponseTimeout')?.value) || 100,
                        byte_timeout_ms: parseInt(document.getElementById('extTcpByteTimeout')?.value) || 100,
                        max_retries: parseInt(document.getElementById('extTcpMaxRetries')?.value) || 2,
                        polling_interval_ms: parseInt(document.getElementById('extTcpPollingInterval')?.value) || 300
                    };
                }
            }
            
            const response = await fetch('/api/devices', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestData)
            });

            const result = await response.json();

            if (response.ok && result.success) {
                showNotification('Device added successfully', 'success');
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

    // ==================== EDIT CONFIG FIELDS BUILDER ====================
    function _buildEditConfigFields(proto, cfg) {
        const sel = (id, label, val, opts) => `
            <div><label class="block text-sm font-medium text-slate-700 mb-1">${label}</label>
            <select id="${id}" class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:border-primary bg-white">
                ${opts.map(o => `<option value="${o.v}" ${String(o.v)===String(val)?'selected':''}>${o.l}</option>`).join('')}
            </select></div>`;
        const inp = (id, label, val, type='text', extra='') => `
            <div><label class="block text-sm font-medium text-slate-700 mb-1">${label}</label>
            <input type="${type}" id="${id}" value="${val ?? ''}" ${extra} class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:border-primary"></div>`;

        if (proto === 'ext-rtu') {
            const portOpts = portConfig.modbus.length
                ? portConfig.modbus.map(p => ({v: p.port_value, l: p.label}))
                : [{v:'/dev/ttymxc5', l:'Port 1'},{v:'/dev/ttymxc2', l:'Port 2'}];
            
            return `<div class="space-y-4">
                <div class="grid grid-cols-2 gap-4">
                    ${inp('editDeviceType','Device Type', cfg.device_type||cfg.device_type_init||'')}
                    ${inp('editModelName','Model Name', cfg.model_name||'')}
                </div>
                <p class="text-xs text-slate-400 -mt-2 mb-2">Device Type will appear in the "Device Type" column (e.g., VFD, Sensor, Meter)</p>
                ${inp('editSlaveId','Slave ID', cfg.slave_id||1,'number','min="1" max="247"')}
                ${sel('editSerialPort','Serial Port', cfg.serial_port||'/dev/ttymxc5', portOpts)}
                <p class="text-xs text-slate-400 mt-1 mb-2">This will be displayed as the Address/ID in the table view</p>
                <div class="grid grid-cols-2 gap-4">
                    ${sel('editBaudRate','Baud Rate', cfg.baud_rate||9600, [9600,19200,38400,57600,115200].map(v=>({v,l:v})))}
                    ${sel('editDataBits','Data Bits', cfg.data_bits||8, [8,7,6,5].map(v=>({v,l:v})))}
                </div>
                <div class="grid grid-cols-2 gap-4">
                    ${sel('editParity','Parity', cfg.parity||'N', [{v:'N',l:'N'},{v:'E',l:'E'},{v:'O',l:'O'}])}
                    ${sel('editStopBits','Stop Bits', cfg.stop_bits||1, [{v:1,l:'1'},{v:2,l:'2'}])}
                </div>
                <div class="grid grid-cols-3 gap-3">
                    ${inp('editResponseTimeout','Response Timeout (ms)', cfg.response_timeout_ms||100,'number','min="10" max="10000"')}
                    ${inp('editByteTimeout','Byte Timeout (ms)', cfg.byte_timeout_ms||100,'number','min="10" max="10000"')}
                    ${inp('editMaxRetries','Max Retries', cfg.max_retries||2,'number','min="0" max="10"')}
                </div>
                ${inp('editPollingInterval','Polling Interval (ms)', cfg.polling_interval_ms||300,'number','min="10" max="10000"')}
            </div>`;
        }
        if (proto === 'ext-tcp') {
            return `<div class="space-y-4">
                <div class="grid grid-cols-2 gap-4">
                    ${inp('editDeviceType','Device Type', cfg.device_type||cfg.device_type_init||'')}
                    ${inp('editModelName','Model Name', cfg.model_name||'')}
                </div>
                <p class="text-xs text-slate-400 -mt-2 mb-2">Device Type will appear in the "Device Type" column (e.g., VFD, Sensor, Meter)</p>
                ${inp('editSlaveId','Slave ID', cfg.slave_id||1,'number','min="1" max="247"')}
                <div class="grid grid-cols-2 gap-4">
                    ${inp('editTcpIp','IP Address', cfg.ip_address||'192.168.1.100')}
                    ${inp('editTcpPort','Port', cfg.port||502,'number','min="1" max="65535"')}
                </div>
                <p class="text-xs text-slate-400 mt-1 mb-2">Address will be displayed as IP:Port in the table view</p>
                <div class="grid grid-cols-3 gap-3">
                    ${inp('editResponseTimeout','Response Timeout (ms)', cfg.response_timeout_ms||100,'number','min="10" max="10000"')}
                    ${inp('editByteTimeout','Byte Timeout (ms)', cfg.byte_timeout_ms||100,'number','min="10" max="10000"')}
                    ${inp('editMaxRetries','Max Retries', cfg.max_retries||2,'number','min="0" max="10"')}
                </div>
                ${inp('editPollingInterval','Polling Interval (ms)', cfg.polling_interval_ms||300,'number','min="10" max="10000"')}
            </div>`;
        }
        if (proto === 'loadcell') {
            const mode = cfg.lc_mode || 'single_ended';
            const chOpts = portConfig.loadcell.length
                ? portConfig.loadcell.map(p => ({v: p.port_value, l: p.label}))
                : [
                    {v:'/sys/bus/iio/devices/iio:device0/in_voltage0_raw', l:'Channel 1'},
                    {v:'/sys/bus/iio/devices/iio:device1/in_voltage0_raw', l:'Channel 2'}
                  ];

            const singleChannel = `
                <div id="editLcChSingle" style="${mode==='single_ended'?'':'display:none'}">
                    ${sel('editDevicePath','Channel', cfg.device_path||chOpts[0].v, chOpts)}
                    <p class="text-xs text-slate-400 mt-1">IIO sysfs channel path (sysfs_hx711)</p>
                </div>`;

            const diffInfo = `
                <div id="editLcChDiff" style="${mode==='differential'?'':'display:none'}">
                    <div class="flex items-center gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                        <i class="fa-solid fa-circle-info text-blue-500 text-sm"></i>
                        <p class="text-xs text-blue-700">Differential mode uses <strong>Channel 1</strong> as the fixed input channel.</p>
                    </div>
                </div>`;

            const adminLockBadge = `<span class="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700 font-medium" title="Sensitive ADC hardware configuration. Users are not permitted to change these values."><i class="fa-solid fa-lock text-xs"></i> Protected</span>`;

            return `<div class="space-y-4">
                ${sel('editLcMode','Mode', mode, [{v:'single_ended',l:'Single Point'},{v:'differential',l:'Differential'}])}
                ${singleChannel}
                ${diffInfo}
                ${inp('editPollMs','Poll Interval (ms)', cfg.poll_ms||10,'text','pattern="[0-9]*" inputmode="numeric" onkeypress="return event.charCode >= 48 && event.charCode <= 57"')}

                <!-- ADC Hardware Parameters (Protected) -->
                <div>
                    <div class="flex items-center gap-2 mb-3 border-b border-slate-100 pb-2">
                        <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">ADC Hardware Parameters</p>
                        ${adminLockBadge}
                    </div>
                    <div class="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-3">
                        <p class="text-xs text-amber-700 flex items-start gap-1.5">
                            <i class="fa-solid fa-triangle-exclamation mt-0.5 flex-shrink-0"></i>
                            <span>These are sensitive ADC hardware configuration values. Users are <strong>not permitted</strong> to modify them. Contact your Administrator if changes are required.</span>
                        </p>
                    </div>
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-xs font-medium text-slate-600 mb-1">Resolution Bits</label>
                            <input type="number" value="${cfg.resolution_bits ?? 24}" readonly id="editLcResolutionBits"
                                class="w-full rounded-lg border-slate-200 border px-3 py-2 text-sm bg-slate-100 text-slate-500 cursor-not-allowed"
                                title="Sensitive ADC configuration — not user-editable">
                        </div>
                        <div>
                            <label class="block text-xs font-medium text-slate-600 mb-1">Effective Bits</label>
                            <input type="number" value="${cfg.effective_bits ?? 14}" readonly id="editLcEffectiveBits"
                                class="w-full rounded-lg border-slate-200 border px-3 py-2 text-sm bg-slate-100 text-slate-500 cursor-not-allowed"
                                title="Sensitive ADC configuration — not user-editable">
                        </div>
                        <div>
                            <label class="block text-xs font-medium text-slate-600 mb-1">Signed / Unsigned</label>
                            <select disabled id="editLcSigned"
                                class="w-full rounded-lg border-slate-200 border px-3 py-2 text-sm bg-slate-100 text-slate-500 cursor-not-allowed"
                                title="Sensitive ADC configuration — not user-editable">
                                <option value="false" ${!cfg.signed?'selected':''}>Unsigned</option>
                                <option value="true" ${cfg.signed?'selected':''}>Signed</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-xs font-medium text-slate-600 mb-1">Gain</label>
                            <input type="number" value="${cfg.gain ?? 1}" readonly id="editLcGain"
                                class="w-full rounded-lg border-slate-200 border px-3 py-2 text-sm bg-slate-100 text-slate-500 cursor-not-allowed"
                                title="Sensitive ADC configuration — not user-editable">
                        </div>
                        <div>
                            <label class="block text-xs font-medium text-slate-600 mb-1">Vref (V)</label>
                            <input type="number" value="${cfg.vref ?? 5}" readonly id="editLcVref"
                                class="w-full rounded-lg border-slate-200 border px-3 py-2 text-sm bg-slate-100 text-slate-500 cursor-not-allowed"
                                title="Sensitive ADC configuration — not user-editable">
                        </div>
                    </div>
                </div>

                <!-- Raw Value Range (Protected) -->
                <div>
                    <div class="flex items-center gap-2 mb-3 border-b border-slate-100 pb-2">
                        <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Raw Value Range</p>
                        ${adminLockBadge}
                    </div>
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-xs font-medium text-slate-600 mb-1">Raw Min</label>
                            <input type="number" value="${cfg.raw_min ?? 0}" readonly id="editLcRawMin"
                                class="w-full rounded-lg border-slate-200 border px-3 py-2 text-sm bg-slate-100 text-slate-500 cursor-not-allowed"
                                title="Sensitive ADC configuration — not user-editable">
                        </div>
                        <div>
                            <label class="block text-xs font-medium text-slate-600 mb-1">Raw Max</label>
                            <input type="number" value="${cfg.raw_max ?? 16383}" readonly id="editLcRawMax"
                                class="w-full rounded-lg border-slate-200 border px-3 py-2 text-sm bg-slate-100 text-slate-500 cursor-not-allowed"
                                title="Sensitive ADC configuration — not user-editable">
                        </div>
                    </div>
                </div>

                <!-- Capacity Specification -->
                <div>
                    <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 border-b border-slate-100 pb-2">Capacity Specification</p>
                    <div class="grid grid-cols-2 gap-3 mt-3">
                        ${inp('editCapacityMin','Min', cfg.capacity_min||0,'number','step="0.1"')}
                        ${inp('editCapacityMax','Max', cfg.capacity_max||1000,'number','step="0.1"')}
                    </div>
                    <div class="grid grid-cols-3 gap-3 mt-3">
                        ${inp('editDeadband','Deadband', cfg.deadband||0,'number','step="0.1"')}
                        ${inp('editOverload','Overload', cfg.overload||0,'number','step="0.1"')}
                        <div>
                            <label class="block text-sm font-medium text-slate-700 mb-1">Unit</label>
                            <select id="editUnit" class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:border-primary bg-white">
                                <option value="kg" ${(!cfg.unit || cfg.unit==='kg')?'selected':''}>kg</option>
                                <option value="ton" ${cfg.unit==='ton'?'selected':''}>ton</option>
                            </select>
                        </div>
                    </div>
                    <p class="mt-2 text-xs text-slate-400">
                        <i class="fa-solid fa-circle-info mr-1"></i>
                        <em>load_name</em> and <em>capacity_name</em> are auto-generated.
                        Capacity values are stored in the selected unit and applied throughout the system.
                    </p>
                </div>
            </div>`;
        }
        return '<p class="text-sm text-slate-500">No editable configuration for this device type.</p>';
    }

    async function saveEditDevice() {
        if (isSaving) return;
        isSaving = true;
        try {
            const deviceName = document.getElementById('editDeviceNameInput')?.value.trim();
            if (!deviceName) { showNotification('Please enter a device name', 'error'); isSaving = false; return; }
            if (!selectedDeviceId) { showNotification('No device selected for edit', 'error'); isSaving = false; return; }

            const duplicateEditName = devices.find(d => d.name.trim().toLowerCase() === deviceName.toLowerCase() && String(d.id) !== String(selectedDeviceId));
            if (duplicateEditName) {
                showNotification(`A device named "${deviceName}" already exists. Please use a different name.`, 'error');
                isSaving = false;
                return;
            }

            const cfg = {};
            const g = id => document.getElementById(id);
            const editDeviceType = g('editDeviceType')?.value?.trim() || '';
            const editModelName = g('editModelName')?.value?.trim() || '';
            
            if (g('editSlaveId')) cfg.slave_id = parseInt(g('editSlaveId').value) || 1;
            if (g('editResponseTimeout')) cfg.response_timeout_ms = parseInt(g('editResponseTimeout').value) || 100;
            if (g('editByteTimeout')) cfg.byte_timeout_ms = parseInt(g('editByteTimeout').value) || 100;
            if (g('editMaxRetries')) cfg.max_retries = parseInt(g('editMaxRetries').value) || 2;
            if (g('editPollingInterval')) cfg.polling_interval_ms = parseInt(g('editPollingInterval').value) || 300;
            if (g('editSerialPort')) cfg.serial_port = g('editSerialPort').value;
            if (g('editBaudRate')) cfg.baud_rate = parseInt(g('editBaudRate').value) || 9600;
            if (g('editDataBits')) cfg.data_bits = parseInt(g('editDataBits').value) || 8;
            if (g('editParity')) cfg.parity = g('editParity').value || 'N';
            if (g('editStopBits')) cfg.stop_bits = parseInt(g('editStopBits').value) || 1;
            if (g('editTcpIp')) cfg.ip_address = g('editTcpIp').value;
            if (g('editTcpPort')) cfg.port = parseInt(g('editTcpPort').value) || 502;
            
            if (g('editLcMode')) {
                cfg.lc_mode = g('editLcMode').value;
                const defaultCh1 = portConfig.loadcell[0]?.port_value ?? '/sys/bus/iio/devices/iio:device0/in_voltage0_raw';
                if (cfg.lc_mode === 'single_ended') {
                    cfg.device_path = g('editDevicePath')?.value || defaultCh1;
                } else {
                    cfg.device_path = defaultCh1;
                }
            }
            if (g('editPollMs')) { let _rawPollMs = g('editPollMs').value.trim(); cfg.poll_ms = _rawPollMs !== '' ? parseInt(_rawPollMs, 10) : 10; }
            if (g('editCapacityMin')) cfg.capacity_min = parseFloat(g('editCapacityMin').value) || 0;
            if (g('editCapacityMax')) cfg.capacity_max = parseFloat(g('editCapacityMax').value) || 1000;
            if (g('editDeadband')) cfg.deadband = parseFloat(g('editDeadband').value) || 0;
            if (g('editOverload')) cfg.overload = parseFloat(g('editOverload').value) || 0;
            if (g('editUnit')) cfg.unit = g('editUnit').value?.trim() || 'kg';
            // ADC protected fields (admin-only, always persisted)
            if (g('editLcResolutionBits')) cfg.resolution_bits = parseInt(g('editLcResolutionBits').value) || 24;
            if (g('editLcEffectiveBits')) cfg.effective_bits = parseInt(g('editLcEffectiveBits').value) || 14;
            if (g('editLcSigned')) cfg.signed = g('editLcSigned').value === 'true';
            if (g('editLcGain')) cfg.gain = parseFloat(g('editLcGain').value) ?? 1;
            if (g('editLcVref')) cfg.vref = parseFloat(g('editLcVref').value) ?? 5;
            if (g('editLcRawMin')) cfg.raw_min = parseInt(g('editLcRawMin').value) ?? 0;
            if (g('editLcRawMax')) cfg.raw_max = parseInt(g('editLcRawMax').value) ?? 16383;

            const response = await fetch(`/api/devices/${selectedDeviceId}`, {
                method: 'PUT',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: deviceName,
                    config: cfg,
                    device_type_init: editDeviceType,
                    model_name: editModelName
                })
            });
            const result = await response.json();
            if (response.ok && result.success) {
                showNotification('Device updated successfully', 'success');
                closeEditPanel();
                await refreshData();
            } else {
                showNotification('Failed to save device: ' + (result.message || result.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            showNotification('Error saving device: ' + error.message, 'error');
        } finally {
            isSaving = false;
        }
    }

    function closeEditPanel() {
        const panel = document.getElementById('editDevicePanel');
        if (panel) {
            panel.classList.remove('active');
        }
        selectedDeviceId = null;
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
                
                const response = await fetch(`/api/devices/${deviceId}/details`, { credentials: 'same-origin' });
                const device = await response.json();
                
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
                const response = await fetch(`/api/devices/${deviceId}/details`, { credentials: 'same-origin' });
                const device = await response.json();
                if (!device || device.error) { 
                    showNotification('Device not found', 'error'); 
                    return; 
                }

                selectedDeviceId = deviceId;
                const proto = (device.protocol || '').toLowerCase();
                const config = device.config || {};

                const deviceIdEl = document.getElementById('editDeviceIdDisplay');
                if (deviceIdEl) {
                    deviceIdEl.textContent = device.id;
                }
                
                const typeLabels = {
                    'loadcell': 'Loadcell',
                    'ext-rtu': 'External',
                    'ext-tcp': 'External',
                    'external': 'External'
                };
                
                const protocolLabels = {
                    'loadcell': '—',
                    'ext-rtu': 'Modbus RTU',
                    'ext-tcp': 'Modbus TCP',
                    'external': '—'
                };
                
                const typeBadge = document.getElementById('editDeviceTypeBadge');
                if (typeBadge) {
                    typeBadge.textContent = typeLabels[proto] || proto.toUpperCase();
                }
                
                const protocolBadge = document.getElementById('editDeviceProtocolBadge');
                const protocolBadgeWrapper = protocolBadge ? protocolBadge.closest('div') : null;
                if (protocolBadge) {
                    protocolBadge.textContent = protocolLabels[proto] || proto.toUpperCase();
                }
                if (protocolBadgeWrapper) {
                    protocolBadgeWrapper.style.display = proto === 'loadcell' ? 'none' : '';
                }

                const addressHint = document.getElementById('editDeviceAddressHint');
                if (addressHint) {
                    if (proto === 'ext-tcp') {
                        addressHint.textContent = 'Address will be displayed as IP:Port in the table view';
                    } else if (proto === 'ext-rtu') {
                        addressHint.textContent = 'Serial port selection determines the Address/ID display';
                    } else if (proto === 'loadcell') {
                        addressHint.textContent = 'Channel selection determines the Address/ID display';
                    }
                }

                const nameInput = document.getElementById('editDeviceNameInput');
                if (nameInput) {
                    nameInput.value = device.name || '';
                }

                const cfgDiv = document.getElementById('editDeviceConfigFields');
                if (cfgDiv) {
                    cfgDiv.innerHTML = _buildEditConfigFields(proto, config);
                }

                _setEditPanelAdcFieldsEditable(isAdmin());

                const panel = document.getElementById('editDevicePanel');
                if (panel) {
                    panel.classList.add('active');
                }

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
                    method: 'DELETE',
                    credentials: 'same-origin'
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
            
            if (device && device.protocol === 'loadcell') {
                const loadcellCount = devices.filter(d => d.protocol === 'loadcell').length;
                if (loadcellCount >= 2) {
                    showNotification('Cannot duplicate Loadcell device - maximum limit of 2 Loadcell devices already reached.', 'error');
                    return;
                }
            }
            
            const deviceName = device ? device.name : 'this device';
            const confirmed = await showDuplicateDeviceConfirmModal(deviceName);
            if (!confirmed) return;
            await duplicateDevice(deviceId);
        },

        refreshData: refreshData
    };

    async function duplicateDevice(deviceId) {
        try {
            showNotification('Duplicating device and tags...', 'info');
            const response = await fetch(`/api/devices/${deviceId}/duplicate`, {
                method: 'POST',
                credentials: 'same-origin',
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

    // ==================== IMPORT / EXPORT ====================
    async function exportDevices() {
        try {
            showNotification('Preparing export...', 'info');
            
            const response = await fetch('/api/devices/export/csv', { credentials: 'same-origin' });
            
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
            const text = await file.text();
            const lines = text.split('\n');
            if (lines.length < 2) {
                showNotification('CSV file is empty', 'error');
                return;
            }
            
            const headers = lines[0].toLowerCase().split(',').map(h => h.trim().replace(/^["']|["']$/g, ''));
            
            const nameIndex = headers.findIndex(h => h === 'name');
            const deviceTypeIndex = headers.findIndex(h => h === 'device type');
            const protocolIndex = headers.findIndex(h => h === 'protocol');
            
            if (nameIndex === -1) {
                showNotification('CSV must have a "Name" column', 'error');
                return;
            }
            
            // Parse all rows
            const rows = [];
            for (let i = 1; i < lines.length; i++) {
                if (!lines[i].trim()) continue;
                
                const row = [];
                let inQuote = false;
                let current = '';
                const cols = lines[i].split('');
                
                for (let j = 0; j < cols.length; j++) {
                    const char = cols[j];
                    if (char === '"') {
                        inQuote = !inQuote;
                    } else if (char === ',' && !inQuote) {
                        row.push(current.trim());
                        current = '';
                    } else {
                        current += char;
                    }
                }
                row.push(current.trim());
                
                const cleanRow = row.map(cell => cell.replace(/^["']|["']$/g, ''));
                
                if (cleanRow.length > nameIndex && cleanRow[nameIndex]) {
                    rows.push(cleanRow);
                }
            }
            
            if (rows.length === 0) {
                showNotification('No valid data found in CSV', 'error');
                return;
            }

            // Deduplicate within the CSV itself (keep first occurrence)
            const seenCsvNames = new Set();
            const uniqueRows = [];
            const intraCsvDupes = [];
            for (const row of rows) {
                const nameKey = (row[nameIndex] || '').toLowerCase();
                if (seenCsvNames.has(nameKey)) {
                    intraCsvDupes.push(row[nameIndex]);
                } else {
                    seenCsvNames.add(nameKey);
                    uniqueRows.push(row);
                }
            }
            if (intraCsvDupes.length > 0) {
                showNotification(`Removed ${intraCsvDupes.length} duplicate row(s) from CSV (kept first occurrence): ${intraCsvDupes.slice(0,3).join(', ')}${intraCsvDupes.length > 3 ? '...' : ''}`, 'warning', 5000);
            }

            // Build device list from deduplicated rows
            const currentLoadcellCount = devices.filter(d => d.protocol === 'loadcell').length;
            let loadcellToImport = 0;
            const importDevicesList = [];
            
            for (const row of uniqueRows) {
                const name = row[nameIndex] || '';
                const deviceType = deviceTypeIndex >= 0 ? (row[deviceTypeIndex] || '').toLowerCase() : '';
                const protocol = protocolIndex >= 0 ? (row[protocolIndex] || '').toLowerCase() : '';
                
                const isLoadcell = deviceType === 'loadcell' || protocol === 'loadcell';
                
                importDevicesList.push({
                    name,
                    deviceType,
                    protocol,
                    isLoadcell,
                    rowData: row
                });
                
                if (isLoadcell) loadcellToImport++;
            }
            
            // Check against existing devices
            const existingDeviceNames = new Set(devices.map(d => d.name.toLowerCase()));
            const duplicates = [];
            const newDevices = [];
            
            for (const dev of importDevicesList) {
                if (existingDeviceNames.has(dev.name.toLowerCase())) {
                    duplicates.push({ name: dev.name, type: dev.isLoadcell ? 'Loadcell' : 'External' });
                } else {
                    newDevices.push(dev);
                }
            }

            // Determine effective loadcell count based on action user will choose
            // For 'skip': only newDevices loadcells are added
            // For 'replace': duplicate loadcells replace existing ones (net change = newLC in new - replaced LC count)
            const newLoadcells = newDevices.filter(d => d.isLoadcell).length;
            if (currentLoadcellCount + newLoadcells > 2) {
                showNotification(`Cannot import — would exceed maximum of 2 Loadcell devices. Currently have ${currentLoadcellCount}, trying to add ${newLoadcells} new.`, 'error');
                return;
            }
            
            // Determine duplicate action
            let action = 'none';
            if (duplicates.length > 0) {
                action = await showDuplicateConfirmation(duplicates, newDevices.length);
                if (action === 'cancel') {
                    showNotification('Import cancelled', 'info');
                    return;
                }
                // For 'replace': also check loadcell limit including replaced ones
                if (action === 'replace') {
                    const replacedLoadcells = duplicates.filter(d => d.type === 'Loadcell').length;
                    const totalLoadcellsAfterReplace = currentLoadcellCount - replacedLoadcells + loadcellToImport;
                    if (totalLoadcellsAfterReplace > 2) {
                        showNotification(`Cannot replace — would exceed maximum of 2 Loadcell devices after replacement.`, 'error');
                        return;
                    }
                }
            }
            
            // Build status UI
            const statusDiv = document.getElementById('importStatus');
            const statusText = document.getElementById('statusText');
            const statusCount = document.getElementById('statusCount');
            const progressBar = document.getElementById('progressBar');
            
            if (statusDiv) {
                statusDiv.classList.remove('hidden');
                if (statusText) statusText.textContent = 'Importing...';
                if (statusCount) statusCount.textContent = `0/${uniqueRows.length} devices`;
                if (progressBar) progressBar.style.width = '0%';
            }
            
            let url = '/api/devices/import/csv';
            if (action === 'skip') {
                url = '/api/devices/import/csv?skip_existing=true';
            } else if (action === 'replace') {
                url = '/api/devices/import/csv?replace_existing=true';
            }
            
            try {
                const formData = new FormData();
                formData.append('file', file);
                
                const response = await fetch(url, {
                    method: 'POST',
                    credentials: 'same-origin',
                    body: formData
                });
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    handleImportSuccess(result, fileInput, statusDiv, statusText, statusCount, progressBar);
                } else {
                    throw new Error(result.error || result.message || 'Import failed');
                }
            } catch (error) {
                console.error('Import error:', error);
                showNotification(`Import failed: ${error.message}`, 'error');
                if (statusDiv) statusDiv.classList.add('hidden');
            }
            
        } catch (error) {
            console.error('Import error:', error);
            showNotification(`Import failed: ${error.message}`, 'error');
            
            const statusDiv = document.getElementById('importStatus');
            if (statusDiv) statusDiv.classList.add('hidden');
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
        
        if (fileInput) {
            fileInput.value = '';
            // Reset drop area label and button text
            const dropAreaLabel = document.querySelector('#dropArea p.text-sm');
            const browseFilesBtn = document.getElementById('browseFilesBtn');
            if (dropAreaLabel) dropAreaLabel.textContent = 'Drag & drop CSV file here';
            if (browseFilesBtn) browseFilesBtn.textContent = 'Browse Files';
        }
        
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
                padding: 20px;
            `;
            
            const dialog = document.createElement('div');
            dialog.style.cssText = `
                background: white;
                padding: 24px;
                border-radius: 12px;
                max-width: 500px;
                width: 100%;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
            `;
            
            dialog.innerHTML = `
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                    <div style="width: 40px; height: 40px; background: #FEF3C7; border-radius: 50%; display: flex; align-items: center; justify-content: center;">
                        <i class="fa-solid fa-triangle-exclamation" style="color: #D97706; font-size: 20px;"></i>
                    </div>
                    <div>
                        <h3 style="margin: 0; font-size: 16px; font-weight: 600; color: #1E293B;">Duplicate Devices Found</h3>
                        <p style="margin: 2px 0 0; font-size: 13px; color: #64748B;">${duplicates.length} device(s) with same name</p>
                    </div>
                </div>
                <div style="background: #F8FAFC; border-radius: 8px; padding: 12px; margin-bottom: 16px; max-height: 200px; overflow-y: auto;">
                    <p style="margin: 0 0 8px 0; font-size: 12px; font-weight: 600; color: #475569;">Duplicate devices:</p>
                    <p style="margin: 0; font-size: 12px; font-family: monospace; color: #334155; white-space: pre-wrap;">${escapeHtml(duplicateNames)}${escapeHtml(moreText)}</p>
                </div>
                <p style="font-size: 14px; color: #374151; margin: 0 0 8px 0;">${newDevicesCount} new device(s) will be imported.</p>
                <p style="font-size: 14px; color: #374151; margin: 0 0 20px 0;">How would you like to proceed?</p>
                <div style="display: flex; gap: 12px;">
                    <button id="replaceBtn" style="flex: 1; padding: 10px 16px; background: #EF4444; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 500; font-size: 14px;">
                        Replace Existing
                    </button>
                    <button id="skipBtn" style="flex: 1; padding: 10px 16px; background: #3B82F6; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 500; font-size: 14px;">
                        Skip Duplicates
                    </button>
                    <button id="cancelBtn" style="flex: 1; padding: 10px 16px; background: #6B7280; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 500; font-size: 14px;">
                        Cancel
                    </button>
                </div>
            `;
            
            overlay.appendChild(dialog);
            document.body.appendChild(overlay);
            
            const replaceBtn = dialog.querySelector('#replaceBtn');
            const skipBtn = dialog.querySelector('#skipBtn');
            const cancelBtn = dialog.querySelector('#cancelBtn');
            
            const cleanup = () => {
                if (overlay.parentNode) overlay.remove();
            };
            
            replaceBtn.onclick = () => {
                cleanup();
                resolve('replace');
            };
            
            skipBtn.onclick = () => {
                cleanup();
                resolve('skip');
            };
            
            cancelBtn.onclick = () => {
                cleanup();
                resolve('cancel');
            };
            
            overlay.onclick = (e) => {
                if (e.target === overlay) {
                    cleanup();
                    resolve('cancel');
                }
            };
        });
    }

    async function downloadCsvTemplate() {
        try {
            const response = await fetch('/api/devices/template/csv', { credentials: 'same-origin' });
            
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
                const importBtn = document.getElementById('importBtn');
                if (importBtn) {
                    importBtn.disabled = !this.files || this.files.length === 0;
                }
                // Show selected filename in drop area
                const dropAreaLabel = document.querySelector('#dropArea p.text-sm');
                const browseFilesBtn = document.getElementById('browseFilesBtn');
                if (this.files && this.files.length > 0) {
                    if (dropAreaLabel) dropAreaLabel.textContent = this.files[0].name;
                    if (browseFilesBtn) browseFilesBtn.textContent = 'Change File';
                } else {
                    if (dropAreaLabel) dropAreaLabel.textContent = 'Drag & drop CSV file here';
                    if (browseFilesBtn) browseFilesBtn.textContent = 'Browse Files';
                }
            });
            fileInput.hasListener = true;
        }
        
        const browseBtn = document.getElementById('browseFilesBtn');
        if (browseBtn && !browseBtn.hasListener) {
            browseBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // prevent event from bubbling up to dropArea
                fileInput?.click();
            });
            browseBtn.hasListener = true;
        }
        
        const dropArea = document.getElementById('dropArea');
        
        if (dropArea && !dropArea.hasListener) {
            dropArea.addEventListener('click', (e) => {
                // Only trigger file dialog if the click is directly on the dropArea,
                // not from a child button (like browseFilesBtn) which handles its own click
                if (e.target === dropArea || (e.target !== browseBtn && !browseBtn?.contains(e.target))) {
                    fileInput?.click();
                }
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

            return;
        }
        eventListenersBoundToNode = anchorNode;
        

        
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
        
        document.querySelectorAll('#addDevicePanel input[name="ext-protocol"]').forEach(r => {
            r.addEventListener('change', handleExtProtocolChange);
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
                    if (device && device.protocol === 'loadcell') {
                        const loadcellCount = devices.filter(d => d.protocol === 'loadcell').length;
                        if (loadcellCount >= 2) {
                            showNotification('Cannot duplicate Loadcell device - maximum limit of 2 Loadcell devices already reached.', 'error');
                            return;
                        }
                    }
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
        
        const saveEditBtn = document.getElementById('saveEditBtn');
        if (saveEditBtn) saveEditBtn.addEventListener('click', saveEditDevice);

        const closeEditPanelBtn = document.getElementById('closeEditPanel');
        if (closeEditPanelBtn) closeEditPanelBtn.addEventListener('click', closeEditPanel);

        const cancelEditBtn = document.getElementById('cancelEditBtn');
        if (cancelEditBtn) cancelEditBtn.addEventListener('click', closeEditPanel);

        document.addEventListener('change', function(e) {
            if (e.target && e.target.id === 'editLcMode') {
                const mode = e.target.value;
                const s = document.getElementById('editLcChSingle');
                const d = document.getElementById('editLcChDiff');
                if (s) s.style.display = mode === 'single_ended' ? '' : 'none';
                if (d) d.style.display = mode === 'differential' ? '' : 'none';
            }
        });

        setupImportExportListeners();


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
        notification.className = 'fixed top-4 left-1/2 -translate-x-1/2 z-[9999] max-w-sm animate-fade-in';
        notification.style.cssText = 'position:fixed;top:16px;left:50%;transform:translateX(-50%);z-index:99999;max-width:420px;width:max-content;';
        
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