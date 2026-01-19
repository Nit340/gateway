// mqtt-cloud.js
// Initialize Cloud Connection Manager
window.initMqttCloud = function() {
    console.log('Cloud Connection Manager page initialized');
    initCloudConnectionManager();
};

function initCloudConnectionManager() {
    console.log('Setting up Cloud Connection Manager functionality');
    
    // Initialize the app
    initApp();
    
    // Add styles for this page
    addCloudConnectionStyles();
    
    // Expose functions globally - Use a different approach to avoid conflicts
    if (!window.cloudConnections) {
        window.cloudConnections = {};
    }
    
    // Add all functions individually
    Object.assign(window.cloudConnections, {
        showConnectionManager,
        showHelp,
        switchTab,
        refreshConnections,
        cancelChanges,
        saveAllConnections,
        closeModal,
        cancelConnectionForm,
        saveNewConnection,
        testConnection,
        addKeyValueItem,
        removeKeyValueItem,
        selectConnection,
        deleteConnection,
        saveConnection
    });
    
    console.log('cloudConnections functions exposed:', Object.keys(window.cloudConnections));
}

// Configuration - Keep as is
const config = {
    "app": {
        "name": "Univa IoT Gateway",
        "version": "2.4.1",
        "maxConnections": 12
    },
    
    "connectionTypes": {
        "mqtt": {
            "name": "MQTT Broker",
            "description": "Standard IoT messaging protocol",
            "icon": "fa-solid fa-cloud",
            "color": "blue",
            "defaultName": "MQTT Broker",
            "formFile": "pages/connection-forms/mqtt-form.html"
        },
        
        "http": {
            "name": "HTTP Endpoint",
            "description": "REST API endpoints",
            "icon": "fa-solid fa-globe",
            "color": "yellow",
            "defaultName": "HTTP API",
            "formFile": "pages/connection-forms/http-form.html"
        }
    },
    
    "defaultStats": {
        "messages": 0,
        "errors": 0,
        "latency": 0,
        "uptime": "0h 0m",
        "lastActive": "Never",
        "bandwidth": "0 MB",
        "successRate": "0%"
    },
    
    "defaultConnections": {
        "mqtt": {
            "id": "mqtt-primary",
            "type": "mqtt",
            "name": "Production MQTT Broker",
            "enabled": true,
            "config": {
                "host": "broker.company.com",
                "port": 8883,
                "protocol": "mqtts",
                "clientId": "univa-gw-01",
                "qos": 1,
                "username": "admin",
                "password": "",
                "tls": true,
                "keepAlive": 60,
                "cleanSession": true
            },
            "stats": {
                "messages": 8953,
                "errors": 0,
                "latency": 95,
                "uptime": "8h 12m",
                "lastActive": "2.3s ago",
                "bandwidth": "2.4 MB",
                "successRate": "99.8%"
            }
        },
        "http": {
            "id": "http-analytics",
            "type": "http",
            "name": "Analytics API",
            "enabled": true,
            "config": {
                "url": "https://api.company.com/v1/data",
                "method": "POST",
                "interval": 300,
                "batchSize": 100,
                "contentType": "application/json"
            },
            "stats": {
                "messages": 3245,
                "errors": 12,
                "latency": 210,
                "uptime": "1h 45m",
                "lastActive": "5 min ago",
                "bandwidth": "1.2 MB",
                "successRate": "99.6%"
            }
        }
    }
};

// Global state
let connections = {};
let selectedConnectionId = null;
let selectedConnectionType = null;

function addCloudConnectionStyles() {
    // Add styles specific to cloud connection page
    const style = document.createElement('style');
    style.textContent = `
        /* Modal Styles */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        
        .modal.active {
            display: flex;
        }
        
        .modal-content {
            background: white;
            border-radius: 8px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            max-width: 600px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
        }
        
        /* Compact Table Styles */
        .compact-table {
            font-size: 12px;
        }
        
        .compact-table th {
            padding: 8px 12px;
            font-size: 11px;
            white-space: nowrap;
        }
        
        .compact-table td {
            padding: 8px 12px;
            font-size: 12px;
        }
        
        /* Status Indicators */
        .status-indicator {
            display: inline-flex;
            align-items: center;
            font-size: 12px;
        }
        
        .status-indicator.online::before {
            content: '';
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #10B981;
            margin-right: 4px;
            animation: pulse 2s infinite;
        }
        
        .status-indicator.offline::before {
            content: '';
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #EF4444;
            margin-right: 4px;
        }
        
        .status-indicator.warning::before {
            content: '';
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #F59E0B;
            margin-right: 4px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        /* Protocol Badges */
        .protocol-badge {
            font-size: 9px;
            padding: 1px 6px;
            border-radius: 8px;
            font-weight: 600;
            text-transform: uppercase;
            white-space: nowrap;
        }
        
        .protocol-badge.mqtt {
            background: #EFF6FF;
            color: #2563EB;
            border: 1px solid #BFDBFE;
        }
        
        .protocol-badge.http {
            background: #FEF3C7;
            color: #D97706;
            border: 1px solid #FDE68A;
        }
        
        /* Card Styles */
        .config-card {
            background: white;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        
        /* Form Styles */
        .compact-input {
            padding: 6px 10px;
            font-size: 13px;
            border-radius: 6px;
            border: 1px solid #E2E8F0;
            transition: all 0.2s;
        }
        
        .compact-input:focus {
            outline: none;
            border-color: #2563EB;
            box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
        }
        
        .compact-select {
            padding: 6px 10px;
            font-size: 13px;
            border-radius: 6px;
            border: 1px solid #E2E8F0;
            transition: all 0.2s;
        }
        
        .compact-select:focus {
            outline: none;
            border-color: #2563EB;
            box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
        }
        
        .compact-button {
            padding: 6px 12px;
            font-size: 13px;
            border-radius: 6px;
            transition: all 0.2s;
            cursor: pointer;
            border: none;
        }
        
        /* Toggle Switch */
        .toggle-switch {
            position: relative;
            display: inline-block;
            width: 36px;
            height: 20px;
        }
        
        .toggle-switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        
        .toggle-slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #CBD5E1;
            transition: .4s;
            border-radius: 34px;
        }
        
        .toggle-slider:before {
            position: absolute;
            content: "";
            height: 14px;
            width: 14px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }
        
        input:checked + .toggle-slider {
            background-color: #10B981;
        }
        
        input:checked + .toggle-slider:before {
            transform: translateX(16px);
        }
        
        /* Tab Styles */
        .tab-button {
            padding: 8px 16px;
            font-size: 12px;
            font-weight: 500;
            color: #64748B;
            border-bottom: 2px solid transparent;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .tab-button:hover {
            color: #2563EB;
            border-bottom-color: #E2E8F0;
        }
        
        .tab-button.active {
            color: #2563EB;
            border-bottom-color: #2563EB;
            font-weight: 600;
        }
        
        /* Form Tabs */
        .form-tab-content {
            display: none;
        }
        
        .form-tab-content.active {
            display: block;
        }
        
        /* Form section styling */
        .form-section {
            background: #F8FAFC;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 12px;
        }
        
        .form-section-title {
            font-size: 13px;
            font-weight: 600;
            color: #1E293B;
            margin-bottom: 12px;
        }
        
        .radio-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .radio-option {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .key-value-list {
            border: 1px solid #E2E8F0;
            border-radius: 6px;
            overflow: hidden;
        }
        
        .key-value-item {
            display: flex;
            gap: 8px;
            padding: 8px;
            border-bottom: 1px solid #E2E8F0;
            align-items: center;
        }
        
        .key-value-item:last-child {
            border-bottom: none;
        }
        
        /* Connection Manager Styles */
        .connection-type-card {
            border: 2px solid #E2E8F0;
            border-radius: 12px;
            padding: 16px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
            background: white;
        }
        
        .connection-type-card:hover {
            border-color: #2563EB;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.1);
            transform: translateY(-2px);
        }
        
        .connection-type-icon {
            width: 56px;
            height: 56px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 12px;
            font-size: 20px;
        }
        
        .help-text {
            font-size: 11px;
            color: #64748B;
            margin-top: 2px;
            line-height: 1.4;
        }
        
        .form-input-group {
            display: flex;
            gap: 8px;
            align-items: center;
        }
    `;
    document.head.appendChild(style);
}

function initApp() {
    connections = {};
    selectedConnectionId = null;
    selectedConnectionType = null;
    
    renderConnectionTypes();
    loadConnections();
    setupEventListeners();
    
    console.log('App initialized, connections loaded:', Object.keys(connections).length);
    
    // Debug: Check if connections are properly set up
    setTimeout(() => {
        console.log('Available connections:', Object.keys(connections));
        if (window.cloudConnections) {
            console.log('cloudConnections object:', window.cloudConnections);
            console.log('selectConnection function exists:', typeof window.cloudConnections.selectConnection);
        }
    }, 500);
}

function setupEventListeners() {
    // Handle gateway select
    const gatewaySelect = document.getElementById('gateway-select');
    if (gatewaySelect) {
        gatewaySelect.addEventListener('change', function() {
            if (confirm('Switch to another gateway? Unsaved changes will be lost.')) {
                location.reload();
            } else {
                this.value = 'Univa-GW-01';
            }
        });
    }
}

// Cloud Connection Manager Functions
function showConnectionManager() {
    showModal('connectionManagerModal');
    showConnectionTypeSelection();
}

function showConnectionTypeSelection() {
    document.getElementById('connectionTypeSelection').classList.remove('hidden');
    document.getElementById('connectionFormContainer').classList.add('hidden');
    selectedConnectionType = null;
}

function renderConnectionTypes() {
    const grid = document.getElementById('connectionTypesGrid');
    if (!grid) return;
    
    grid.innerHTML = '';
    
    Object.entries(config.connectionTypes).forEach(([type, connectionConfig]) => {
        const card = document.createElement('div');
        card.className = 'connection-type-card';
        card.onclick = () => selectConnectionType(type);
        
        const colorMap = {
            blue: '#3B82F6',
            yellow: '#F59E0B',
            purple: '#8B5CF6',
            orange: '#F97316',
            green: '#10B981'
        };
        
        const color = colorMap[connectionConfig.color] || '#3B82F6';
        
        card.innerHTML = `
            <div class="connection-type-icon" style="background-color: ${color}20; color: ${color};">
                <i class="${connectionConfig.icon}"></i>
            </div>
            <h4 class="font-semibold text-slate-900 text-sm mb-2">${connectionConfig.name}</h4>
            <p class="text-xs text-slate-600">${connectionConfig.description}</p>
        `;
        
        grid.appendChild(card);
    });
}

async function selectConnectionType(type) {
    selectedConnectionType = type;
    const connectionConfig = config.connectionTypes[type];
    
    document.getElementById('formTitle').textContent = `Configure ${connectionConfig.name}`;
    document.getElementById('connectionTypeSelection').classList.add('hidden');
    document.getElementById('connectionFormContainer').classList.remove('hidden');
    
    await renderConnectionForm(type);
}

async function renderConnectionForm(type) {
    const formContent = document.getElementById('formContent');
    const connectionConfig = config.connectionTypes[type];
    
    try {
        const response = await fetch(connectionConfig.formFile);
        if (!response.ok) throw new Error(`Failed to load form: ${response.status}`);
        
        const html = await response.text();
        formContent.innerHTML = html;
        
        initializeForm(type);
        
    } catch (error) {
        console.error('Error loading form:', error);
        formContent.innerHTML = createFallbackForm(type);
        initializeTemplateFields();
        
        const backButton = document.createElement('button');
        backButton.onclick = showConnectionTypeSelection;
        backButton.className = 'mt-4 compact-button border border-slate-300 text-slate-700 hover:bg-slate-50';
        backButton.innerHTML = '<i class="fa-solid fa-arrow-left mr-1"></i> Back to Connection Types';
        formContent.appendChild(backButton);
    }
}

function createFallbackForm(type) {
    if (type === 'mqtt') {
        return `
            <div class="form-section">
                <h5 class="form-section-title">Connection Configuration</h5>
                <div class="space-y-4">
                    <div>
                        <label class="block text-xs font-medium text-slate-700 mb-1">Connection Name</label>
                        <input type="text" id="field-name" class="w-full compact-input" placeholder="${config.connectionTypes[type]?.defaultName || 'New Connection'}">
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-slate-700 mb-1">Host / Endpoint</label>
                        <input type="text" id="field-host" class="w-full compact-input" placeholder="example.com">
                    </div>
                </div>
            </div>
        `;
    } else {
        return `
            <div class="form-section">
                <h5 class="form-section-title">Connection Configuration</h5>
                <div class="space-y-4">
                    <div>
                        <label class="block text-xs font-medium text-slate-700 mb-1">Connection Name</label>
                        <input type="text" id="field-name" class="w-full compact-input" placeholder="${config.connectionTypes[type]?.defaultName || 'New Connection'}">
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-slate-700 mb-1">Host / Endpoint</label>
                        <input type="text" id="field-host" class="w-full compact-input" placeholder="example.com">
                    </div>
                </div>
            </div>
        `;
    }
}

function initializeForm(type) {
    if (type === 'mqtt') {
        // Wait a moment for DOM to be ready, then initialize MQTT form
        setTimeout(() => {
            if (typeof window.initializeMqttForm === 'function') {
                window.initializeMqttForm();
            }
        }, 100);
    } else if (type === 'http') {
        // Wait a moment for DOM to be ready, then initialize HTTP form
        setTimeout(() => {
            if (typeof window.initializeHttpForm === 'function') {
                window.initializeHttpForm();
            }
        }, 100);
    } else {
        initializeTemplateFields();
    }
}

function initializeTemplateFields() {
    document.querySelectorAll('.toggle-switch input').forEach(toggle => {
        toggle.addEventListener('change', function() {
            const label = this.nextElementSibling;
            label.style.backgroundColor = this.checked ? '#10B981' : '#CBD5E1';
        });
        
        const label = toggle.nextElementSibling;
        label.style.backgroundColor = toggle.checked ? '#10B981' : '#CBD5E1';
    });
    
    document.querySelectorAll('.key-value-list').forEach(list => {
        const addButton = list.querySelector('button');
        if (addButton) {
            addButton.onclick = function() {
                window.cloudConnections.addKeyValueItem(this);
            };
        }
        
        list.querySelectorAll('.key-value-item button').forEach(btn => {
            btn.onclick = function() {
                window.cloudConnections.removeKeyValueItem(this);
            };
        });
    });
}

function cancelConnectionForm() {
    showConnectionTypeSelection();
}

function saveNewConnection() {
    if (!selectedConnectionType) return;
    
    const connectionConfig = config.connectionTypes[selectedConnectionType];
    const formData = collectFormDataFromTemplate();
    
    const connectionId = `${selectedConnectionType}-${Date.now()}`;
    const name = formData.name || connectionConfig.defaultName;
    
    connections[connectionId] = {
        id: connectionId,
        type: selectedConnectionType,
        name: name,
        enabled: true,
        config: formData,
        stats: {...config.defaultStats}
    };
    
    addConnectionToList(connectionId, connections[connectionId]);
    
    closeModal('connectionManagerModal');
    
    showNotification(`${connectionConfig.name} added successfully`, 'success');
    
    selectConnection(connectionId);
}

function collectFormDataFromTemplate() {
    const formData = {};
    const formContent = document.getElementById('formContent');
    
    if (!formContent) return formData;
    
    formContent.querySelectorAll('input[type="text"], input[type="number"], input[type="password"]').forEach(input => {
        const id = input.id;
        if (id.startsWith('field-')) {
            const fieldName = id.replace('field-', '');
            formData[fieldName] = input.value;
        }
    });
    
    formContent.querySelectorAll('select').forEach(select => {
        const id = select.id;
        if (id.startsWith('field-')) {
            const fieldName = id.replace('field-', '');
            formData[fieldName] = select.value;
        }
    });
    
    formContent.querySelectorAll('.toggle-switch input[type="checkbox"]').forEach(checkbox => {
        const id = checkbox.id;
        if (id.startsWith('field-')) {
            const fieldName = id.replace('field-', '');
            formData[fieldName] = checkbox.checked;
        }
    });
    
    formContent.querySelectorAll('input[type="radio"]').forEach(radio => {
        const name = radio.name;
        if (name.startsWith('field-')) {
            const fieldName = name.replace('field-', '');
            if (radio.checked) {
                formData[fieldName] = radio.value;
            }
        }
    });
    
    const keyValueData = {};
    formContent.querySelectorAll('.key-value-item').forEach(item => {
        const inputs = item.querySelectorAll('input[type="text"]');
        if (inputs.length >= 2) {
            const key = inputs[0].value.trim();
            const value = inputs[1].value.trim();
            if (key && value) {
                keyValueData[key] = value;
            }
        }
    });
    
    if (Object.keys(keyValueData).length > 0) {
        formData.headers = keyValueData;
    }
    
    return formData;
}

function loadConnections() {
    // Load default connections
    Object.values(config.defaultConnections).forEach(conn => {
        connections[conn.id] = conn;
        addConnectionToList(conn.id, conn);
    });
    
    updateConnectionCount();
    
    // Auto-select the first connection if none is selected
    const connectionIds = Object.keys(connections);
    if (connectionIds.length > 0 && !selectedConnectionId) {
        const firstId = connectionIds[0];
        console.log('Auto-selecting first connection:', firstId);
        selectConnection(firstId);
    }
}

function addConnectionToList(id, conn) {
    const list = document.getElementById('connectionsList');
    const connectionConfig = config.connectionTypes[conn.type];
    
    if (!list) return;
    
    // Check if connection already exists in the list
    if (document.querySelector(`[data-connection-id="${id}"]`)) {
        updateConnectionItem(id, conn);
        return;
    }
    
    // Remove the placeholder if it exists
    const placeholder = list.querySelector('.text-center');
    if (placeholder) {
        placeholder.remove();
    }
    
    const colorMap = {
        blue: 'border-blue-500 text-blue-600',
        yellow: 'border-yellow-500 text-yellow-600',
        purple: 'border-purple-500 text-purple-600',
        orange: 'border-orange-500 text-orange-600',
        green: 'border-green-500 text-green-600'
    };
    
    const colorClass = colorMap[connectionConfig.color] || 'border-blue-500 text-blue-600';
    const isSelected = selectedConnectionId === id;
    
    // Create HTML string with inline onclick
    const html = `
        <div data-connection-id="${id}" 
             onclick="if(window.cloudConnections && window.cloudConnections.selectConnection) { window.cloudConnections.selectConnection('${id}'); } else { console.error('selectConnection not available'); }"
             class="border-l-4 ${colorClass.split(' ')[0]} p-3 bg-white border ${isSelected ? 'border-blue-200 bg-blue-50' : 'border-slate-200'} rounded-lg cursor-pointer hover:border-blue-200 transition-colors">
            <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2">
                    <i class="${connectionConfig.icon} ${colorClass.split(' ')[1]}"></i>
                    <span class="font-medium text-slate-900 text-sm">${conn.name}</span>
                </div>
                <span class="text-xs text-slate-500">${conn.stats.lastActive}</span>
            </div>
            <div class="text-xs text-slate-600 truncate mb-2">${getConnectionSummary(conn)}</div>
            <div class="flex justify-between items-center">
                <span class="text-xs px-2 py-1 rounded ${conn.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}">
                    ${conn.enabled ? 'Active' : 'Inactive'}
                </span>
                <span class="text-xs font-medium">${conn.stats.messages.toLocaleString()} msgs</span>
            </div>
        </div>
    `;
    
    list.insertAdjacentHTML('afterbegin', html);
    updateConnectionCount();
}

function updateConnectionItem(id, conn) {
    const item = document.querySelector(`[data-connection-id="${id}"]`);
    if (!item) return;
    
    const connectionConfig = config.connectionTypes[conn.type];
    const colorMap = {
        blue: 'text-blue-600',
        yellow: 'text-yellow-600',
        purple: 'text-purple-600',
        orange: 'text-orange-600',
        green: 'text-green-600'
    };
    
    const iconClass = colorMap[connectionConfig.color] || 'text-blue-600';
    
    item.querySelector('i').className = `${connectionConfig.icon} ${iconClass}`;
    item.querySelector('.font-medium').textContent = conn.name;
    item.querySelector('.text-xs.text-slate-500').textContent = conn.stats.lastActive;
    item.querySelector('.text-slate-600').textContent = getConnectionSummary(conn);
    item.querySelector('.bg-green-100, .bg-gray-100').className = conn.enabled ? 'text-xs px-2 py-1 rounded bg-green-100 text-green-800' : 'text-xs px-2 py-1 rounded bg-gray-100 text-gray-800';
    item.querySelector('.bg-green-100, .bg-gray-100').textContent = conn.enabled ? 'Active' : 'Inactive';
    item.querySelector('.font-medium:last-child').textContent = `${conn.stats.messages.toLocaleString()} msgs`;
}

function getConnectionSummary(conn) {
    if (conn.type === 'mqtt' && conn.config.host) {
        const protocol = conn.config.protocol || 'mqtt://';
        const port = conn.config.port || (protocol.includes('mqtts') ? 8883 : 1883);
        return `${protocol}${conn.config.host}:${port}`;
    }
    if (conn.type === 'http' && conn.config.url) {
        return conn.config.url;
    }
    if (conn.config.endpoint) return conn.config.endpoint;
    if (conn.config.hostname) return conn.config.hostname;
    return `${config.connectionTypes[conn.type]?.name} Connection`;
}

// CRITICAL FUNCTION: This must work for connections to be selectable
function selectConnection(id) {
    console.log('selectConnection called with id:', id);
    
    // Validate connection exists
    if (!connections[id]) {
        console.error('Connection not found:', id);
        showEmptyConnectionState();
        return;
    }
    
    // Update selected ID
    selectedConnectionId = id;
    const conn = connections[id];
    
    // Update UI for all connection items
    const allItems = document.querySelectorAll('[data-connection-id]');
    allItems.forEach(el => {
        const itemId = el.getAttribute('data-connection-id');
        el.classList.remove('border-blue-200', 'bg-blue-50');
        el.classList.add('border-slate-200');
        
        if (itemId === id) {
            el.classList.add('border-blue-200', 'bg-blue-50');
            el.classList.remove('border-slate-200');
        }
    });
    
    // Update the configuration panel
    updateConfigurationForConnection(conn);
}

function showEmptyConnectionState() {
    document.getElementById('connectionName').textContent = 'No Connection Selected';
    document.getElementById('connectionDescription').textContent = 'Select a connection to view details';
    document.getElementById('statMessages').textContent = '0';
    document.getElementById('statErrors').textContent = '0';
    document.getElementById('statLastSent').textContent = 'Never';
    document.getElementById('statLatency').textContent = '0 ms';
    
    // Disable and reset the enabled toggle
    const enabledToggle = document.getElementById('mqtt-enabled');
    if (enabledToggle) {
        enabledToggle.checked = false;
        enabledToggle.disabled = true;
        const slider = enabledToggle.nextElementSibling;
        if (slider) {
            slider.style.backgroundColor = '#CBD5E1';
        }
    }
    
    document.getElementById('diagnosticStatus').className = 'status-indicator offline';
    document.getElementById('diagnosticStatus').textContent = 'Disconnected';
    document.getElementById('diagnosticLastMessage').textContent = 'Never';
    document.getElementById('diagnosticPacketsSent').textContent = '0';
    document.getElementById('diagnosticPacketsReceived').textContent = '0';
    document.getElementById('diagnosticLastError').textContent = 'None';
    document.getElementById('diagnosticLatency').textContent = '0 ms';
    
    document.getElementById('downlinkCommands').innerHTML = `
        <tr>
            <td colspan="3" class="p-4 text-center text-slate-400 text-xs">
                No commands received
            </td>
        </tr>
    `;
    
    document.getElementById('tab-content-connection').innerHTML = `
        <div class="text-center py-12 text-slate-400">
            <i class="fa-solid fa-plug text-3xl mb-3"></i>
            <p class="text-sm">Select a connection to configure</p>
            <p class="text-xs mt-1">or click "Add Connection" to create a new one</p>
        </div>
    `;
    
    document.getElementById('tab-content-topics').style.display = 'none';
    document.getElementById('tab-content-publishing').style.display = 'none';
    document.getElementById('tab-content-advanced').style.display = 'none';
    
    document.querySelectorAll('.tab-button').forEach(tab => {
        if (tab.id === 'tab-connection') {
            tab.style.display = 'block';
            tab.classList.add('active');
        } else {
            tab.style.display = 'none';
            tab.classList.remove('active');
        }
    });
}

async function updateConfigurationForConnection(conn) {
    // SAFETY CHECK: Don't run if we're not on the cloud connections page
    const isOnCloudPage = document.getElementById('connectionName') !== null;
    if (!isOnCloudPage) {
        console.log('Not on cloud connections page, skipping update');
        return;
    }
    
    const connectionConfig = config.connectionTypes[conn.type];
    if (!connectionConfig) {
        console.error('Connection type not found:', conn.type);
        return;
    }
    
    // Update basic info
    document.getElementById('connectionName').textContent = conn.name;
    document.getElementById('connectionDescription').textContent = `${connectionConfig.name} - ${connectionConfig.description}`;
    
    // Update stats
    document.getElementById('statMessages').textContent = conn.stats.messages.toLocaleString();
    document.getElementById('statErrors').textContent = conn.stats.errors;
    document.getElementById('statLastSent').textContent = conn.stats.lastActive;
    document.getElementById('statLatency').textContent = conn.stats.latency + ' ms';
    
    // Update enabled toggle
    const enabledToggle = document.getElementById('mqtt-enabled');
    if (enabledToggle) {
        enabledToggle.checked = conn.enabled;
        enabledToggle.disabled = false;
        
        // Update the toggle slider color
        const slider = enabledToggle.nextElementSibling;
        if (slider) {
            slider.style.backgroundColor = conn.enabled ? '#10B981' : '#CBD5E1';
        }
    }
    
    // Update diagnostics
    const statusElement = document.getElementById('diagnosticStatus');
    if (statusElement) {
        statusElement.className = conn.enabled ? 'status-indicator online' : 'status-indicator offline';
        statusElement.textContent = conn.enabled ? 'Connected' : 'Disconnected';
    }
    
    document.getElementById('diagnosticLastMessage').textContent = conn.stats.lastActive;
    document.getElementById('diagnosticPacketsSent').textContent = conn.stats.messages.toLocaleString();
    document.getElementById('diagnosticPacketsReceived').textContent = Math.floor(conn.stats.messages * 0.01).toLocaleString();
    document.getElementById('diagnosticLastError').textContent = conn.stats.errors > 0 ? `${conn.stats.errors} errors` : 'None';
    document.getElementById('diagnosticLatency').textContent = conn.stats.latency + ' ms';
    
    // Update downlink commands
    if (conn.enabled) {
        document.getElementById('downlinkCommands').innerHTML = `
            <tr class="border-t border-slate-100">
                <td class="p-2">10:43:12</td>
                <td class="p-2 font-mono">SetSpeed=12</td>
                <td class="p-2">
                    <span class="px-2 py-1 bg-green-50 text-green-700 rounded text-xs">Accepted</span>
                </td>
            </tr>
            <tr class="border-t border-slate-100">
                <td class="p-2">10:41:04</td>
                <td class="p-2 font-mono">ResetWarning</td>
                <td class="p-2">
                    <span class="px-2 py-1 bg-red-50 text-red-700 rounded text-xs">Failed</span>
                </td>
            </tr>
        `;
    } else {
        document.getElementById('downlinkCommands').innerHTML = `
            <tr>
                <td colspan="3" class="p-4 text-center text-slate-400 text-xs">
                    No commands received
                </td>
            </tr>
        `;
    }
    
    // Clear and show loading indicator for configuration
    const tabContent = document.getElementById('tab-content-connection');
    if (tabContent) {
        tabContent.innerHTML = '<div class="text-center py-8"><i class="fa-solid fa-spinner fa-spin text-primary text-xl"></i><p class="text-xs text-slate-500 mt-2">Loading configuration...</p></div>';
    }
    
    // Show only connection tab for now
    document.getElementById('tab-content-topics').style.display = 'none';
    document.getElementById('tab-content-publishing').style.display = 'none';
    document.getElementById('tab-content-advanced').style.display = 'none';
    
    // Update tab buttons
    document.querySelectorAll('.tab-button').forEach(tab => {
        if (tab.id === 'tab-connection') {
            tab.style.display = 'block';
            tab.classList.add('active');
        } else {
            tab.style.display = 'none';
            tab.classList.remove('active');
        }
    });
    
    // Load the connection-specific edit form
    await loadConnectionEditForm(conn);
}

async function loadConnectionEditForm(conn) {
    const connectionConfig = config.connectionTypes[conn.type];
    const tabContent = document.getElementById('tab-content-connection');
    
    if (!connectionConfig || !tabContent) {
        tabContent.innerHTML = `
            <div class="text-center py-8 text-slate-400">
                <i class="fa-solid fa-exclamation-triangle text-3xl mb-3"></i>
                <p class="text-sm">Failed to load configuration</p>
            </div>
        `;
        return;
    }
    
    try {
        const response = await fetch(connectionConfig.formFile);
        if (!response.ok) throw new Error(`Failed to load form: ${response.status}`);
        
        const html = await response.text();
        
        tabContent.innerHTML = `
            <div class="space-y-6">
                <div class="flex justify-between items-center mb-4">
                    <h4 class="text-sm font-semibold text-slate-900">${connectionConfig.name} Configuration</h4>
                    <div class="flex items-center gap-2">
                        <span class="text-xs text-slate-700">Enabled</span>
                        <label class="toggle-switch">
                            <input type="checkbox" id="connection-enabled" ${conn.enabled ? 'checked' : ''}>
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                </div>
                
                <div class="form-section">
                    <h5 class="form-section-title">Connection Information</h5>
                    <div class="space-y-4">
                        <div>
                            <label class="block text-xs font-medium text-slate-700 mb-1">Connection Name</label>
                            <input type="text" id="edit-connection-name" 
                                   class="w-full compact-input"
                                   value="${conn.name}"
                                   placeholder="Enter connection name">
                        </div>
                    </div>
                </div>
                
                <div id="edit-form-content">
                    ${html}
                </div>
                
                <div class="pt-4 border-t border-slate-200">
                    <div class="flex justify-between items-center">
                        <div class="flex space-x-2">
                            <button onclick="if(window.cloudConnections && window.cloudConnections.testConnection) window.cloudConnections.testConnection()" class="compact-button border border-slate-300 text-slate-700 hover:bg-slate-50 flex items-center">
                                <i class="fa-solid fa-bolt mr-1"></i> Test Connection
                            </button>
                            <button onclick="if(window.cloudConnections && window.cloudConnections.deleteConnection) window.cloudConnections.deleteConnection('${conn.id}')" class="compact-button border border-red-300 text-red-700 hover:bg-red-50 flex items-center">
                                <i class="fa-solid fa-trash mr-1"></i> Delete
                            </button>
                        </div>
                        <button onclick="if(window.cloudConnections && window.cloudConnections.saveConnection) window.cloudConnections.saveConnection('${conn.id}')" class="compact-button bg-primary hover:bg-primaryHover text-white flex items-center">
                            <i class="fa-solid fa-save mr-1"></i> Save Changes
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        // Populate form with connection data
        populateFormWithData(conn);
        
        // Initialize form-specific JavaScript
        if (conn.type === 'mqtt' && typeof window.initializeMqttForm === 'function') {
            setTimeout(() => {
                window.initializeMqttForm();
            }, 100);
        } else if (conn.type === 'http' && typeof window.initializeHttpForm === 'function') {
            setTimeout(() => {
                window.initializeHttpForm();
            }, 100);
        }
        
    } catch (error) {
        console.error('Error loading form:', error);
        tabContent.innerHTML = `
            <div class="text-center py-8 text-slate-400">
                <i class="fa-solid fa-exclamation-triangle text-3xl mb-3"></i>
                <p class="text-sm">Failed to load configuration form</p>
                <p class="text-xs mt-1">${error.message}</p>
            </div>
        `;
    }
}

function populateFormWithData(conn) {
    const nameInput = document.getElementById('edit-connection-name');
    if (nameInput) nameInput.value = conn.name;
    
    const enabledCheckbox = document.getElementById('connection-enabled');
    if (enabledCheckbox) enabledCheckbox.checked = conn.enabled;
    
    Object.entries(conn.config).forEach(([fieldName, value]) => {
        const fieldId = `field-${fieldName}`;
        const element = document.getElementById(fieldId);
        
        if (element) {
            if (element.type === 'checkbox') {
                element.checked = value;
            } else if (element.type === 'radio') {
                document.querySelectorAll(`input[name="${element.name}"][value="${value}"]`).forEach(radio => {
                    radio.checked = true;
                });
            } else {
                element.value = value;
            }
        }
    });
    
    if (conn.config.headers && typeof conn.config.headers === 'object') {
        const keyValueLists = document.querySelectorAll('.key-value-list');
        keyValueLists.forEach(list => {
            const items = list.querySelectorAll('.key-value-item');
            items.forEach(item => {
                if (!item.querySelector('button[onclick*="addKeyValueItem"]')) {
                    item.remove();
                }
            });
            
            const addButton = list.querySelector('button[onclick*="addKeyValueItem"]');
            if (addButton) {
                Object.entries(conn.config.headers).forEach(([key, value]) => {
                    const newItem = document.createElement('div');
                    newItem.className = 'key-value-item';
                    newItem.innerHTML = `
                        <input type="text" value="${key}" placeholder="Key" class="compact-input">
                        <input type="text" value="${value}" placeholder="Value" class="compact-input">
                        <button type="button" class="text-red-600 hover:text-red-700" onclick="if(window.cloudConnections && window.cloudConnections.removeKeyValueItem) window.cloudConnections.removeKeyValueItem(this)">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    `;
                    list.insertBefore(newItem, addButton.parentNode);
                });
            }
        });
    }
}

function saveConnection(connectionId) {
    const conn = connections[connectionId];
    if (!conn) return;
    
    const nameInput = document.getElementById('edit-connection-name');
    if (nameInput) {
        conn.name = nameInput.value;
    }
    
    const enabledCheckbox = document.getElementById('connection-enabled');
    if (enabledCheckbox) {
        conn.enabled = enabledCheckbox.checked;
    }
    
    const formData = collectFormDataFromEditForm();
    
    conn.config = {...conn.config, ...formData};
    
    updateConnectionItem(connectionId, conn);
    updateConfigurationForConnection(conn);
    
    showNotification(`${conn.name} updated successfully`, 'success');
}

function collectFormDataFromEditForm() {
    const formData = {};
    
    const editFormContent = document.getElementById('edit-form-content');
    if (!editFormContent) return formData;
    
    editFormContent.querySelectorAll('input[type="text"], input[type="number"], input[type="password"]').forEach(input => {
        const id = input.id;
        if (id.startsWith('field-')) {
            const fieldName = id.replace('field-', '');
            formData[fieldName] = input.value;
        }
    });
    
    editFormContent.querySelectorAll('select').forEach(select => {
        const id = select.id;
        if (id.startsWith('field-')) {
            const fieldName = id.replace('field-', '');
            formData[fieldName] = select.value;
        }
    });
    
    editFormContent.querySelectorAll('.toggle-switch input[type="checkbox"]').forEach(checkbox => {
        const id = checkbox.id;
        if (id.startsWith('field-')) {
            const fieldName = id.replace('field-', '');
            formData[fieldName] = checkbox.checked;
        }
    });
    
    editFormContent.querySelectorAll('input[type="radio"]').forEach(radio => {
        const name = radio.name;
        if (name.startsWith('field-')) {
            const fieldName = name.replace('field-', '');
            if (radio.checked) {
                formData[fieldName] = radio.value;
            }
        }
    });
    
    const keyValueData = {};
    editFormContent.querySelectorAll('.key-value-item').forEach(item => {
        const inputs = item.querySelectorAll('input[type="text"]');
        if (inputs.length >= 2) {
            const key = inputs[0].value.trim();
            const value = inputs[1].value.trim();
            if (key && value) {
                keyValueData[key] = value;
            }
        }
    });
    
    if (Object.keys(keyValueData).length > 0) {
        formData.headers = keyValueData;
    }
    
    return formData;
}

function deleteConnection(connectionId) {
    if (!confirm(`Are you sure you want to delete "${connections[connectionId]?.name}"?`)) {
        return;
    }
    
    const connName = connections[connectionId]?.name || 'Connection';
    delete connections[connectionId];
    
    const connectionElement = document.querySelector(`[data-connection-id="${connectionId}"]`);
    if (connectionElement) {
        connectionElement.remove();
    }
    
    updateConnectionCount();
    
    if (selectedConnectionId === connectionId) {
        selectedConnectionId = null;
        showEmptyConnectionState();
    }
    
    showNotification(`${connName} deleted successfully`, 'success');
}

function updateConnectionCount() {
    const count = Object.keys(connections).length;
    const countElement = document.getElementById('connectionCount');
    if (countElement) {
        countElement.textContent = count;
    }
    
    const connectionsList = document.getElementById('connectionsList');
    if (connectionsList && count === 0) {
        connectionsList.innerHTML = `
            <div class="text-center py-8 text-slate-400">
                <i class="fa-solid fa-cloud text-3xl mb-3"></i>
                <p class="text-sm">No connections yet</p>
                <p class="text-xs mt-1">Click "Add Connection" to get started</p>
            </div>
        `;
    }
}

// Helper Functions
function showNotification(message, type = 'info') {
    // Check for infinite recursion
    if (arguments.callee.caller === arguments.callee) {
        console.error('Infinite recursion detected in showNotification');
        return;
    }
    
    const colors = {
        success: 'bg-green-100 border-green-200 text-green-800',
        error: 'bg-red-100 border-red-200 text-red-800',
        info: 'bg-blue-100 border-blue-200 text-blue-800',
        warning: 'bg-yellow-100 border-yellow-200 text-yellow-800'
    };
    
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 px-4 py-2 rounded-lg border ${colors[type]} shadow-lg z-50 text-sm`;
    notification.innerHTML = `
        <div class="flex items-center gap-2">
            <i class="fa-solid ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'}"></i>
            <span>${message}</span>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
        }
    }, 3000);
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
    }
}

function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
    }
}

// Key-Value List Functions
function addKeyValueItem(button) {
    const list = button.closest('.key-value-list');
    const keyPlaceholder = list.querySelector('input[placeholder*="Key"]')?.placeholder || 'Key';
    const valuePlaceholder = list.querySelector('input[placeholder*="Value"]')?.placeholder || 'Value';
    
    const item = document.createElement('div');
    item.className = 'key-value-item';
    item.innerHTML = `
        <input type="text" placeholder="${keyPlaceholder}" class="compact-input">
        <input type="text" placeholder="${valuePlaceholder}" class="compact-input">
        <button type="button" class="text-red-600 hover:text-red-700" onclick="if(window.cloudConnections && window.cloudConnections.removeKeyValueItem) window.cloudConnections.removeKeyValueItem(this)">
            <i class="fa-solid fa-trash"></i>
        </button>
    `;
    
    list.insertBefore(item, button.parentNode);
}

function removeKeyValueItem(button) {
    const item = button.closest('.key-value-item');
    if (item) {
        item.remove();
    }
}

// Tab Switching Functions
function switchTab(tabName) {
    const conn = connections[selectedConnectionId];
    
    document.querySelectorAll('[id^="tab-content-"]').forEach(tab => {
        tab.style.display = 'none';
    });
    
    document.querySelectorAll('.tab-button').forEach(button => {
        button.classList.remove('active');
    });
    
    const tabContent = document.getElementById(`tab-content-${tabName}`);
    if (tabContent) {
        tabContent.style.display = 'block';
    }
    
    const tabButton = document.getElementById(`tab-${tabName}`);
    if (tabButton) {
        tabButton.classList.add('active');
    }
}

function refreshConnections() {
    showNotification('Refreshing connections...', 'info');
    
    setTimeout(() => {
        Object.values(connections).forEach(conn => {
            conn.stats.lastActive = `${Math.floor(Math.random() * 10)}s ago`;
            updateConnectionItem(conn.id, conn);
        });
        
        if (selectedConnectionId) {
            updateConfigurationForConnection(connections[selectedConnectionId]);
        }
        
        showNotification('Connections refreshed', 'success');
    }, 1000);
}

function cancelChanges() {
    if (confirm('Discard all unsaved changes?')) {
        showNotification('Changes discarded', 'info');
    }
}

function saveAllConnections() {
    showNotification('All connections saved successfully!', 'success');
}

function testConnection() {
    const currentConn = connections[selectedConnectionId];
    if (!currentConn) {
        showNotification('Please select a connection first', 'warning');
        return;
    }
    
    showNotification(`Testing ${currentConn.name} connection...`, 'info');
    
    setTimeout(() => {
        currentConn.stats.messages += Math.floor(Math.random() * 100);
        currentConn.stats.lastActive = 'Just now';
        currentConn.stats.latency = Math.floor(Math.random() * 200);
        currentConn.stats.successRate = `${98 + Math.floor(Math.random() * 2)}%`;
        
        updateConnectionItem(selectedConnectionId, currentConn);
        updateConfigurationForConnection(currentConn);
        
        showModal('testResultsModal');
        
        showNotification(`Connection test for ${currentConn.name} successful!`, 'success');
    }, 1500);
}

function showHelp() {
    alert('Cloud Connection Manager Help:\n\n1. Click "Add Connection" to create new cloud connections\n2. Select a connection type (MQTT or HTTP)\n3. Configure the connection settings\n4. Test the connection before saving\n5. Manage multiple connections from the list\n\nMaximum connections: ' + config.app.maxConnections);
}