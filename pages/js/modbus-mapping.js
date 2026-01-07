// modbus-mapping.js - Protocol Mapping functionality
window.initializeModbusMapping = function() {
    console.log('Initializing Modbus Mapping...');
    
    // Add CSS styles for the page
    const styles = document.createElement('style');
    styles.textContent = `
        .compact-input:focus, .compact-select:focus {
            outline: none;
            border-color: #2563EB;
            box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
        }
        
        .hidden {
            display: none !important;
        }
        
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
    `;
    document.head.appendChild(styles);
    
    // Initialize the application
    initApp();
    
    // Set up event listeners
    setupEventListeners();
    
    console.log('Modbus Mapping initialized successfully');
};

// Global state
let devices = [];
let mappings = [];
let tags = [];
let selectedDeviceId = null;
let selectedMappingId = null;
let currentStep = 1;
let currentProtocol = 'modbus';

// Sample data
const sampleDevices = [
    {
        id: 1,
        name: 'LoadCell_1',
        type: 'Load Cell',
        protocol: 'modbus-rtu',
        address: '01',
        status: 'online',
        pollRate: '200',
        tags: 4,
        description: 'Main hoist load cell'
    },
    {
        id: 2,
        name: 'Inclin_Arm',
        type: 'Inclinometer',
        protocol: 'modbus-tcp',
        address: '192.168.1.21:502',
        status: 'online',
        pollRate: '500',
        tags: 3,
        description: 'Boom angle sensor'
    },
    {
        id: 3,
        name: 'HoistDrive',
        type: 'Drive Controller',
        protocol: 'can',
        address: '0x32',
        status: 'offline',
        pollRate: '100',
        tags: 6,
        description: 'Main hoist drive'
    },
    {
        id: 4,
        name: 'WindSensor',
        type: 'Wind Sensor',
        protocol: 'modbus-rtu',
        address: '02',
        status: 'warning',
        pollRate: '1000',
        tags: 2,
        description: 'Wind speed sensor'
    },
    {
        id: 5,
        name: 'PLC_Main',
        type: 'PLC Controller',
        protocol: 'ethernet-ip',
        address: '192.168.1.10',
        status: 'online',
        pollRate: '100',
        tags: 8,
        description: 'Main PLC controller'
    }
];

const sampleMappings = [
    {
        id: 1,
        deviceId: 1,
        address: '30001',
        tagName: 'Hoist_Load',
        dataType: 'INT16',
        scale: '0.01',
        offset: '0',
        unit: 'tons',
        pollInterval: '200',
        category: 'Load Monitoring',
        description: 'Main hoist load measurement',
        minValid: '0',
        maxValid: '200',
        endianness: 'big-endian',
        protocol: 'modbus'
    },
    {
        id: 2,
        deviceId: 2,
        address: '40002',
        tagName: 'Boom_Angle',
        dataType: 'FLOAT32',
        scale: '0.1',
        offset: '0',
        unit: 'degrees',
        pollInterval: '500',
        category: 'Position Tracking',
        description: 'Boom angle measurement',
        minValid: '-10',
        maxValid: '85',
        endianness: 'little-endian',
        protocol: 'modbus'
    },
    {
        id: 3,
        deviceId: 3,
        address: '0x100',
        tagName: 'Motor_RPM',
        dataType: 'INT16',
        scale: '1',
        offset: '0',
        unit: 'RPM',
        pollInterval: '100',
        category: 'Motor',
        description: 'Motor rotation speed',
        minValid: '-100',
        maxValid: '3000',
        endianness: 'big-endian',
        protocol: 'can'
    },
    {
        id: 4,
        deviceId: 1,
        address: '30002',
        tagName: 'Hoist_Height',
        dataType: 'INT32',
        scale: '0.01',
        offset: '0',
        unit: 'meters',
        pollInterval: '200',
        category: 'Position Tracking',
        description: 'Hoist height measurement',
        minValid: '0',
        maxValid: '100',
        endianness: 'big-endian',
        protocol: 'modbus'
    },
    {
        id: 5,
        deviceId: 1,
        address: '30003',
        tagName: 'Load_Sway',
        dataType: 'FLOAT32',
        scale: '0.5',
        offset: '0',
        unit: 'degrees',
        pollInterval: '500',
        category: 'Safety',
        description: 'Load sway angle',
        minValid: '-30',
        maxValid: '30',
        endianness: 'little-endian',
        protocol: 'modbus'
    },
    {
        id: 6,
        deviceId: 2,
        address: '40003',
        tagName: 'Wind_Speed',
        dataType: 'FLOAT32',
        scale: '0.1',
        offset: '0',
        unit: 'm/s',
        pollInterval: '1000',
        category: 'Safety',
        description: 'Wind speed measurement',
        minValid: '0',
        maxValid: '50',
        endianness: 'little-endian',
        protocol: 'modbus'
    },
    {
        id: 7,
        deviceId: 5,
        address: 'Tag_1',
        tagName: 'System_Pressure',
        dataType: 'FLOAT32',
        scale: '0.01',
        offset: '0',
        unit: 'bar',
        pollInterval: '100',
        category: 'Sensors',
        description: 'Hydraulic system pressure',
        minValid: '0',
        maxValid: '350',
        endianness: 'big-endian',
        protocol: 'ethernet'
    }
];

// Initialize application
function initApp() {
    devices = [...sampleDevices];
    mappings = [...sampleMappings];
    
    generateTags();
    initDeviceFilters();
    renderMappingsTable();
    renderTagsList();
    setupModalEventListeners();
}

// Initialize device filter dropdowns
function initDeviceFilters() {
    const mappingDeviceFilter = document.getElementById('deviceFilter');
    const tagDeviceFilter = document.getElementById('tagDeviceFilter');
    
    if (mappingDeviceFilter) {
        // Clear existing options except "All Devices"
        while (mappingDeviceFilter.options.length > 1) {
            mappingDeviceFilter.remove(1);
        }
        
        // Add device options
        devices.forEach(device => {
            const option = document.createElement('option');
            option.value = device.name;
            option.textContent = device.name;
            mappingDeviceFilter.appendChild(option);
        });
    }
    
    if (tagDeviceFilter) {
        // Clear existing options except "All Devices"
        while (tagDeviceFilter.options.length > 1) {
            tagDeviceFilter.remove(1);
        }
        
        // Add device options
        devices.forEach(device => {
            const option = document.createElement('option');
            option.value = device.name;
            option.textContent = device.name;
            tagDeviceFilter.appendChild(option);
        });
    }
}

// Generate tags from mappings
function generateTags() {
    tags = mappings.map(mapping => {
        const device = devices.find(d => d.id === mapping.deviceId);
        return {
            id: mapping.id,
            name: mapping.tagName,
            description: mapping.description,
            deviceId: mapping.deviceId,
            deviceName: device?.name || 'Unknown',
            deviceProtocol: device?.protocol || 'Unknown',
            value: getRandomValue(mapping),
            lastUpdated: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}),
            unit: mapping.unit,
            address: mapping.address,
            category: mapping.category,
            usedBy: getUsedBy(mapping.category),
            dataType: mapping.dataType,
            pollInterval: mapping.pollInterval
        };
    });
}

function getRandomValue(mapping) {
    const ranges = {
        'tons': {min: 0, max: 200},
        'degrees': {min: -10, max: 85},
        'meters': {min: 0, max: 100},
        'm/s': {min: 0, max: 50},
        'RPM': {min: -100, max: 3000},
        'bar': {min: 0, max: 350},
        'flag': {min: 0, max: 65535},
        'default': {min: 0, max: 100}
    };
    
    const range = ranges[mapping.unit] || ranges.default;
    const random = range.min + Math.random() * (range.max - range.min);
    
    if (mapping.dataType.includes('FLOAT')) {
        return random.toFixed(2);
    } else {
        return Math.round(random);
    }
}

function getUsedBy(category) {
    const usage = {
        'Load Monitoring': ['Rules', 'CraneIQ', 'Dash'],
        'Safety': ['Rules', 'Alerts'],
        'Position Tracking': ['CraneIQ', 'Dash'],
        'Sensors': ['Rules', 'Dash'],
        'Motor': ['Rules', 'CraneIQ'],
        'Diagnostic': ['Rules', 'Logging'],
        'Status': ['Dash', 'Alerts'],
        'Configuration': ['System'],
        'default': ['Rules', 'Dash']
    };
    return usage[category] || usage.default;
}

// Render mappings table
function renderMappingsTable() {
    const tbody = document.getElementById('mappingTableBody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    const deviceFilter = document.getElementById('deviceFilter').value;
    let filteredMappings = mappings;
    
    if (deviceFilter !== 'All Devices') {
        const deviceName = deviceFilter;
        const device = devices.find(d => d.name === deviceName);
        if (device) {
            filteredMappings = mappings.filter(m => m.deviceId === device.id);
        }
    }
    
    filteredMappings.forEach(mapping => {
        const device = devices.find(d => d.id === mapping.deviceId);
        if (!device) return;
        
        const row = document.createElement('tr');
        row.className = 'hover:bg-slate-50';
        row.dataset.mappingId = mapping.id;
        
        // Data type badge
        let dataTypeClass = 'data-type-badge ';
        if (mapping.dataType.includes('INT16')) dataTypeClass += 'int16';
        else if (mapping.dataType.includes('INT32')) dataTypeClass += 'int32';
        else if (mapping.dataType.includes('FLOAT')) dataTypeClass += 'float32';
        else if (mapping.dataType.includes('UINT')) dataTypeClass += 'uint16';
        else dataTypeClass += 'bool';
        
        // Protocol badge
        let protocolClass = 'protocol-badge ';
        switch(device.protocol) {
            case 'modbus-rtu':
            case 'modbus-tcp':
                protocolClass += 'modbus'; break;
            case 'can':
                protocolClass += 'can'; break;
            case 'ethernet-ip':
                protocolClass += 'ethernet'; break;
            default:
                protocolClass += 'serial';
        }
        
        // Status indicator
        let statusIndicator = '';
        switch(device.status) {
            case 'online':
                statusIndicator = '<span class="status-indicator online mr-1"></span>';
                break;
            case 'offline':
                statusIndicator = '<span class="status-indicator offline mr-1"></span>';
                break;
            case 'warning':
                statusIndicator = '<span class="status-indicator warning mr-1"></span>';
                break;
        }
        
        row.innerHTML = `
            <td>
                <div class="font-medium text-slate-900 flex items-center">
                    ${statusIndicator}${device.name}
                </div>
                <div class="text-xs text-slate-500">${device.type}</div>
            </td>
            <td>
                <span class="${protocolClass}">${device.protocol.replace('-', ' ').toUpperCase()}</span>
            </td>
            <td class="font-mono">${mapping.address}</td>
            <td>
                <div class="font-medium">${mapping.tagName}</div>
                <div class="text-xs text-slate-500 truncate max-w-[150px]">${mapping.description}</div>
            </td>
            <td><span class="${dataTypeClass}">${mapping.dataType}</span></td>
            <td>${mapping.unit}</td>
            <td class="font-mono">${mapping.pollInterval}</td>
            <td class="text-right">
                <div class="flex justify-end space-x-1">
                    <button class="w-6 h-6 rounded border border-slate-300 flex items-center justify-center text-slate-500 hover:text-primary hover:border-primary text-xs edit-mapping-btn" data-id="${mapping.id}">
                        <i class="fa-solid fa-pen"></i>
                    </button>
                    <button class="w-6 h-6 rounded border border-slate-300 flex items-center justify-center text-slate-500 hover:text-danger hover:border-danger text-xs delete-mapping-btn" data-id="${mapping.id}">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            </td>
        `;
        
        tbody.appendChild(row);
    });
    
    // Update mapping count
    const mappingCount = document.getElementById('mappingCount');
    if (mappingCount) {
        mappingCount.textContent = filteredMappings.length;
    }
    
    // Re-attach event listeners for the new buttons
    attachRowEventListeners();
}

// Render tags list
function renderTagsList() {
    const container = document.getElementById('tagsList');
    const emptyState = document.getElementById('tagsEmptyState');
    
    if (!container) return;
    
    const searchTerm = document.getElementById('tagSearch').value.toLowerCase();
    const categoryFilter = document.getElementById('tagCategoryFilter').value;
    const deviceFilter = document.getElementById('tagDeviceFilter').value;
    
    let filteredTags = tags;
    
    // Apply filters
    if (searchTerm) {
        filteredTags = filteredTags.filter(tag => 
            tag.name.toLowerCase().includes(searchTerm) ||
            tag.description.toLowerCase().includes(searchTerm) ||
            tag.deviceName.toLowerCase().includes(searchTerm)
        );
    }
    
    if (categoryFilter) {
        filteredTags = filteredTags.filter(tag => tag.category === categoryFilter);
    }
    
    if (deviceFilter) {
        const device = devices.find(d => d.name === deviceFilter);
        if (device) {
            filteredTags = filteredTags.filter(tag => tag.deviceId === device.id);
        }
    }
    
    // Show/hide empty state
    if (filteredTags.length === 0) {
        container.innerHTML = '';
        if (emptyState) {
            emptyState.classList.remove('hidden');
        }
        return;
    } else {
        if (emptyState) {
            emptyState.classList.add('hidden');
        }
    }
    
    container.innerHTML = '';
    
    filteredTags.forEach(tag => {
        const device = devices.find(d => d.id === tag.deviceId);
        const mapping = mappings.find(m => m.id === tag.id);
        
        let protocolClass = 'protocol-badge ';
        if (device) {
            switch(device.protocol) {
                case 'modbus-rtu':
                case 'modbus-tcp':
                    protocolClass += 'modbus'; break;
                case 'can':
                    protocolClass += 'can'; break;
                case 'ethernet-ip':
                    protocolClass += 'ethernet'; break;
                default:
                    protocolClass += 'serial';
            }
        }
        
        // Data type badge
        let dataTypeClass = 'data-type-badge ';
        if (tag.dataType.includes('INT16')) dataTypeClass += 'int16';
        else if (tag.dataType.includes('INT32')) dataTypeClass += 'int32';
        else if (tag.dataType.includes('FLOAT')) dataTypeClass += 'float32';
        else if (tag.dataType.includes('UINT')) dataTypeClass += 'uint16';
        else dataTypeClass += 'bool';
        
        // Status indicator
        let statusIndicator = '';
        if (device) {
            switch(device.status) {
                case 'online':
                    statusIndicator = '<span class="status-indicator online mr-1"></span>';
                    break;
                case 'offline':
                    statusIndicator = '<span class="status-indicator offline mr-1"></span>';
                    break;
                case 'warning':
                    statusIndicator = '<span class="status-indicator warning mr-1"></span>';
                    break;
            }
        }
        
        const tagElement = document.createElement('div');
        tagElement.className = 'tag-card';
        tagElement.dataset.tagId = tag.id;
        tagElement.innerHTML = `
            <div class="flex justify-between items-start mb-3">
                <div class="flex-1 min-w-0">
                    <div class="font-medium text-slate-900 truncate flex items-center">
                        ${statusIndicator}${tag.name}
                    </div>
                    <div class="text-xs text-slate-500 truncate">${tag.description}</div>
                </div>
                <div class="flex flex-col items-end gap-1">
                    <span class="${protocolClass}">${device?.protocol.replace('-', ' ').toUpperCase() || ''}</span>
                    <span class="${dataTypeClass}">${tag.dataType}</span>
                </div>
            </div>
            
            <div class="flex items-center justify-between text-xs mb-3">
                <div class="flex items-center space-x-2">
                    <span class="device-badge">${tag.deviceName}</span>
                    <span class="text-slate-600">
                        <i class="fa-solid fa-hashtag mr-1"></i>${tag.address}
                    </span>
                </div>
                <div class="text-slate-500">
                    <i class="fa-solid fa-clock mr-1"></i>${tag.lastUpdated}
                </div>
            </div>
            
            <div class="flex items-center justify-between mb-3">
                <div class="text-xl font-bold text-primary">${tag.value}</div>
                <div class="flex flex-col items-end">
                    <div class="text-sm font-medium">${tag.unit}</div>
                    <div class="text-xs text-slate-500">Poll: ${tag.pollInterval}ms</div>
                </div>
            </div>
            
            <div class="mt-2 flex flex-wrap gap-1">
                ${tag.usedBy.map(module => 
                    `<span class="text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-800">${module}</span>`
                ).join('')}
                <span class="text-xs px-1.5 py-0.5 rounded bg-slate-200 text-slate-700">${mapping?.category || 'General'}</span>
            </div>
        `;
        container.appendChild(tagElement);
    });
}

// Attach event listeners to table row buttons
function attachRowEventListeners() {
    // Edit buttons
    document.querySelectorAll('.edit-mapping-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const id = parseInt(this.dataset.id);
            editMapping(id);
        });
    });
    
    // Delete buttons
    document.querySelectorAll('.delete-mapping-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const id = parseInt(this.dataset.id);
            deleteMapping(id);
        });
    });
}

// Import CSV function
function importCSV() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.csv';
    
    input.onchange = function(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        const reader = new FileReader();
        reader.onload = function(e) {
            const content = e.target.result;
            // Parse CSV (simplified - in real app use a proper CSV parser)
            const lines = content.split('\n');
            const headers = lines[0].split(',');
            
            // Validate CSV structure
            const requiredHeaders = ['Device', 'Protocol', 'Address', 'Tag Name', 'Data Type', 'Unit'];
            const missingHeaders = requiredHeaders.filter(h => !headers.includes(h));
            
            if (missingHeaders.length > 0) {
                showNotification(`Invalid CSV format. Missing headers: ${missingHeaders.join(', ')}`, 'error');
                return;
            }
            
            // Process rows
            let importedCount = 0;
            for (let i = 1; i < lines.length; i++) {
                if (!lines[i].trim()) continue;
                
                const values = lines[i].split(',');
                if (values.length >= 6) {
                    const deviceName = values[0].replace(/"/g, '');
                    const protocol = values[1].replace(/"/g, '');
                    const address = values[2].replace(/"/g, '');
                    const tagName = values[3].replace(/"/g, '');
                    const dataType = values[4].replace(/"/g, '');
                    const unit = values[5].replace(/"/g, '');
                    
                    // Find or create device
                    let device = devices.find(d => d.name === deviceName);
                    if (!device) {
                        device = {
                            id: Math.max(...devices.map(d => d.id)) + 1,
                            name: deviceName,
                            type: 'Imported Device',
                            protocol: protocol,
                            address: address,
                            status: 'online',
                            pollRate: '1000',
                            tags: 0,
                            description: 'Imported from CSV'
                        };
                        devices.push(device);
                    }
                    
                    // Create mapping
                    const newMapping = {
                        id: mappings.length > 0 ? Math.max(...mappings.map(m => m.id)) + 1 : 1,
                        deviceId: device.id,
                        address: address,
                        tagName: tagName,
                        dataType: dataType,
                        endianness: 'big-endian',
                        scale: '1',
                        offset: '0',
                        unit: unit,
                        pollInterval: '1000',
                        category: 'Imported',
                        description: `Imported mapping for ${tagName}`,
                        protocol: getProtocolType(protocol)
                    };
                    
                    mappings.push(newMapping);
                    importedCount++;
                    
                    // Update device tag count
                    device.tags = mappings.filter(m => m.deviceId === device.id).length;
                }
            }
            
            generateTags();
            initDeviceFilters();
            renderMappingsTable();
            renderTagsList();
            
            showNotification(`Successfully imported ${importedCount} mappings from CSV`, 'success');
        };
        reader.readAsText(file);
    };
    
    input.click();
}

// Export CSV function
function exportCSV() {
    // Create CSV content
    let csvContent = "Device,Protocol,Address,Tag Name,Data Type,Unit,Scale,Offset,Poll Interval,Category,Description,Min Valid,Max Valid,Endianness\n";
    
    mappings.forEach(mapping => {
        const device = devices.find(d => d.id === mapping.deviceId);
        const protocol = device ? device.protocol : 'Unknown';
        const deviceName = device ? device.name : 'Unknown';
        
        csvContent += `"${deviceName}","${protocol}","${mapping.address}","${mapping.tagName}","${mapping.dataType}","${mapping.unit}","${mapping.scale}","${mapping.offset}","${mapping.pollInterval}","${mapping.category}","${mapping.description}","${mapping.minValid || ''}","${mapping.maxValid || ''}","${mapping.endianness || 'big-endian'}"\n`;
    });
    
    // Create download link
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `tag_mappings_${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showNotification('CSV export completed!', 'success');
}

// Add new mapping
function addNewMapping() {
    if (!selectedDeviceId) {
        // If no device is selected, show device selection modal
        showDeviceSelectionModal();
        return;
    }
    
    const device = devices.find(d => d.id === selectedDeviceId);
    if (!device) {
        showNotification('Selected device not found. Please select a device first.', 'warning');
        return;
    }
    
    // Reset modal state
    resetModal();
    
    // Update modal title
    document.getElementById('modalTitle').textContent = 'Add New Mapping';
    
    // Fill device info
    document.getElementById('mappingDeviceName').textContent = device.name;
    document.getElementById('mappingProtocol').textContent = formatProtocolText(device.protocol, device.address);
    
    // Set current protocol based on device
    currentProtocol = getProtocolType(device.protocol);
    
    // Load protocol-specific configuration - ONLY for the selected device's protocol
    loadProtocolConfigurationForDevice(device);
    
    // Set default address based on device protocol
    setDefaultAddress(device);
    
    // Show modal
    document.getElementById('editMappingModal').classList.remove('hidden');
}

// Helper function to format protocol text
function formatProtocolText(protocol, address) {
    const protocolMap = {
        'modbus-rtu': 'Modbus RTU',
        'modbus-tcp': 'Modbus TCP',
        'can': 'CAN',
        'ethernet-ip': 'EtherNet/IP'
    };
    
    return `${protocolMap[protocol] || protocol.toUpperCase()} | Address: ${address}`;
}

// Set default address based on protocol
function setDefaultAddress(device) {
    const addressInput = document.getElementById('mappingAddressValue');
    if (!addressInput) return;
    
    switch(getProtocolType(device.protocol)) {
        case 'modbus':
            addressInput.value = '40001';
            break;
        case 'can':
            addressInput.value = '0x100';
            break;
        case 'ethernet':
            addressInput.value = 'Tag_1';
            break;
        default:
            addressInput.value = '1';
    }
}

// Show device selection modal
function showDeviceSelectionModal() {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.id = 'deviceSelectModal';
    modal.style.display = 'flex';
    
    modal.innerHTML = `
        <div class="modal" style="max-width: 400px;">
            <div class="p-5">
                <div class="flex items-center justify-between mb-5">
                    <h2 class="text-base font-semibold text-slate-800">Select a Device</h2>
                    <button class="text-slate-400 hover:text-slate-600" id="closeDeviceSelectModal">
                        <i class="fa-solid fa-xmark text-base"></i>
                    </button>
                </div>
                
                <p class="text-sm text-slate-600 mb-4">Please select a device to add mappings to:</p>
                
                <div class="space-y-2 max-h-60 overflow-y-auto" id="deviceSelectList">
                    ${devices.map(device => `
                        <div class="p-3 border border-slate-200 rounded-lg hover:bg-slate-50 cursor-pointer flex items-center justify-between device-select-item"
                             data-device-id="${device.id}">
                            <div>
                                <div class="font-medium">${device.name}</div>
                                <div class="text-xs text-slate-500">${device.type} • ${device.protocol}</div>
                            </div>
                            <span class="text-xs px-2 py-1 rounded ${device.status === 'online' ? 'bg-green-100 text-green-800' : device.status === 'warning' ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'}">
                                ${device.status}
                            </span>
                        </div>
                    `).join('')}
                </div>
                
                <div class="mt-6 pt-4 border-t border-slate-200 flex justify-end">
                    <button class="compact-button border border-slate-300 text-slate-700 hover:bg-slate-50" id="cancelDeviceSelect">
                        Cancel
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Add event listeners
    document.getElementById('closeDeviceSelectModal').addEventListener('click', closeDeviceSelectModal);
    document.getElementById('cancelDeviceSelect').addEventListener('click', closeDeviceSelectModal);
    
    document.querySelectorAll('.device-select-item').forEach(item => {
        item.addEventListener('click', function() {
            const deviceId = parseInt(this.dataset.deviceId);
            selectDeviceForMapping(deviceId);
        });
    });
}

// Select device for mapping
function selectDeviceForMapping(deviceId) {
    selectedDeviceId = deviceId;
    closeDeviceSelectModal();
    addNewMapping();
}

// Close device selection modal
function closeDeviceSelectModal() {
    const modal = document.getElementById('deviceSelectModal');
    if (modal) {
        modal.remove();
    }
}

// Edit mapping
function editMapping(id) {
    selectedMappingId = id;
    const mapping = mappings.find(m => m.id === id);
    const device = mapping ? devices.find(d => d.id === mapping.deviceId) : null;
    
    if (mapping && device) {
        // Set the selected device
        selectedDeviceId = device.id;
        
        // Reset modal state
        resetModal();
        
        // Update modal title
        document.getElementById('modalTitle').textContent = 'Edit Mapping';
        
        // Fill device info
        document.getElementById('mappingDeviceName').textContent = device.name;
        document.getElementById('mappingProtocol').textContent = formatProtocolText(device.protocol, device.address);
        
        // Set current protocol
        currentProtocol = getProtocolType(device.protocol);
        
        // Load protocol configuration - ONLY for the selected device's protocol
        loadProtocolConfigurationForDevice(device);
        
        // Fill form with existing data
        document.getElementById('mappingTagName').value = mapping.tagName;
        document.getElementById('mappingDescription').value = mapping.description || '';
        document.getElementById('mappingDataType').value = mapping.dataType;
        document.getElementById('mappingEndianness').value = mapping.endianness || 'big-endian';
        document.getElementById('mappingUnit').value = mapping.unit || '';
        document.getElementById('mappingScale').value = mapping.scale || '1';
        document.getElementById('mappingOffset').value = mapping.offset || '0';
        document.getElementById('mappingPollInterval').value = mapping.pollInterval;
        document.getElementById('mappingPollPreset').value = getPollPreset(mapping.pollInterval);
        document.getElementById('mappingCategory').value = mapping.category || 'Sensors';
        
        // Set address based on mapping
        const addressInput = document.getElementById('mappingAddressValue');
        if (addressInput) {
            addressInput.value = mapping.address;
        }
        
        // Show modal
        document.getElementById('editMappingModal').classList.remove('hidden');
        
        // Go to step 3 for editing
        goToStep(3);
    }
}

// Helper functions
function getProtocolType(protocol) {
    if (protocol.includes('modbus')) return 'modbus';
    if (protocol === 'can') return 'can';
    if (protocol.includes('ethernet')) return 'ethernet';
    return 'modbus';
}

function getPollPreset(interval) {
    const presets = {
        '100': '100',
        '200': '200',
        '500': '500',
        '1000': '1000',
        '5000': '5000'
    };
    return presets[interval] || 'custom';
}

// Load protocol-specific configuration for a specific device (only show that protocol)
function loadProtocolConfigurationForDevice(device) {
    currentProtocol = getProtocolType(device.protocol);
    
    // Create tabs container with only the device's protocol
    const tabsContainer = document.getElementById('protocolTabsContainer');
    if (!tabsContainer) return;
    
    // Only show tab for the device's protocol
    let protocolName = '';
    switch(currentProtocol) {
        case 'modbus':
            protocolName = 'Modbus';
            break;
        case 'can':
            protocolName = 'CAN';
            break;
        case 'ethernet':
            protocolName = 'EtherNet/IP';
            break;
        default:
            protocolName = 'Advanced';
    }
    
    tabsContainer.innerHTML = `
        <div class="flex space-x-1">
            <div class="tab active" data-tab="${currentProtocol}">${protocolName}</div>
        </div>
    `;
    
    // Load address configuration
    loadAddressConfiguration(currentProtocol);
    
    // Load protocol-specific fields
    loadProtocolSpecificFields(currentProtocol);
}

// Load address configuration
function loadAddressConfiguration(protocol) {
    const addressTypeContainer = document.getElementById('address-type-container');
    const addressValueContainer = document.getElementById('address-value-container');
    
    if (!addressTypeContainer || !addressValueContainer) return;
    
    let addressTypeOptions = '';
    let addressValuePlaceholder = '';
    
    switch(protocol) {
        case 'modbus':
            addressTypeOptions = `
                <label class="block text-xs font-medium text-slate-700 mb-1">Register Type</label>
                <select class="w-full compact-select bg-white" id="mappingAddressType">
                    <option value="holding">Holding Register (4x)</option>
                    <option value="input">Input Register (3x)</option>
                    <option value="coil">Coil (0x)</option>
                    <option value="discrete">Discrete Input (1x)</option>
                </select>
            `;
            addressValuePlaceholder = 'e.g., 40001';
            break;
            
        case 'can':
            addressTypeOptions = `
                <label class="block text-xs font-medium text-slate-700 mb-1">CAN ID Type</label>
                <select class="w-full compact-select bg-white" id="mappingAddressType">
                    <option value="standard">Standard (11-bit)</option>
                    <option value="extended">Extended (29-bit)</option>
                    <option value="canopen">CANOpen</option>
                    <option value="j1939">J1939</option>
                </select>
            `;
            addressValuePlaceholder = 'e.g., 0x212';
            break;
            
        case 'ethernet':
            addressTypeOptions = `
                <label class="block text-xs font-medium text-slate-700 mb-1">Data Type</label>
                <select class="w-full compact-select bg-white" id="mappingAddressType">
                    <option value="tag">Tag Name</option>
                    <option value="symbolic">Symbolic Address</option>
                    <option value="direct">Direct Address</option>
                </select>
            `;
            addressValuePlaceholder = 'e.g., MotorRPM';
            break;
            
        default:
            addressTypeOptions = `
                <label class="block text-xs font-medium text-slate-700 mb-1">Address Type</label>
                <select class="w-full compact-select bg-white" id="mappingAddressType">
                    <option value="decimal">Decimal</option>
                    <option value="hex">Hexadecimal</option>
                    <option value="binary">Binary</option>
                </select>
            `;
            addressValuePlaceholder = 'Enter address';
    }
    
    addressTypeContainer.innerHTML = addressTypeOptions;
    addressValueContainer.innerHTML = `
        <label class="block text-xs font-medium text-slate-700 mb-1">Address Value</label>
        <input type="text" class="w-full compact-input font-mono" placeholder="${addressValuePlaceholder}" id="mappingAddressValue">
    `;
}

// Load protocol-specific fields
function loadProtocolSpecificFields(protocol) {
    const container = document.getElementById('protocol-specific-fields');
    if (!container) return;
    
    let fields = '';
    
    switch(protocol) {
        case 'modbus':
            fields = `
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-medium text-slate-700 mb-1">Register Count</label>
                        <input type="number" min="1" max="125" value="1" class="w-full compact-input" id="mappingRegisterCount">
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-slate-700 mb-1">Byte Order</label>
                        <select class="w-full compact-select bg-white" id="mappingByteOrder">
                            <option value="0">0-based (ABCD)</option>
                            <option value="1">1-based (BADC)</option>
                        </select>
                    </div>
                </div>
            `;
            break;
            
        case 'can':
            fields = `
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-medium text-slate-700 mb-1">DLC (Bytes)</label>
                        <select class="w-full compact-select bg-white" id="mappingDLC">
                            <option value="1">1 byte</option>
                            <option value="2">2 bytes</option>
                            <option value="4" selected>4 bytes</option>
                            <option value="8">8 bytes</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-slate-700 mb-1">Start Byte</label>
                        <input type="number" min="0" max="7" value="0" class="w-full compact-input" id="mappingStartByte">
                    </div>
                </div>
            `;
            break;
            
        case 'ethernet':
            fields = `
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-medium text-slate-700 mb-1">Data Size</label>
                        <select class="w-full compact-select bg-white" id="mappingDataSize">
                            <option value="BOOL">BOOL (1 bit)</option>
                            <option value="SINT">SINT (8-bit)</option>
                            <option value="INT">INT (16-bit)</option>
                            <option value="DINT" selected>DINT (32-bit)</option>
                            <option value="REAL">REAL (32-bit float)</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-slate-700 mb-1">Array Size</label>
                        <input type="number" min="1" value="1" class="w-full compact-input" id="mappingArraySize">
                    </div>
                </div>
            `;
            break;
            
        default:
            fields = '';
    }
    
    container.innerHTML = fields;
}

// Reset modal state
function resetModal() {
    currentStep = 1;
    updateStepIndicator();
    
    // Show step 1, hide others
    document.querySelectorAll('.dynamic-section').forEach(section => {
        section.classList.remove('active');
    });
    const step1Content = document.getElementById('step1-content');
    if (step1Content) {
        step1Content.classList.add('active');
    }
    
    // Reset form values
    const tagNameInput = document.getElementById('mappingTagName');
    if (tagNameInput) tagNameInput.value = '';
    
    const descriptionInput = document.getElementById('mappingDescription');
    if (descriptionInput) descriptionInput.value = '';
    
    const dataTypeSelect = document.getElementById('mappingDataType');
    if (dataTypeSelect) dataTypeSelect.value = 'INT16';
    
    const endiannessSelect = document.getElementById('mappingEndianness');
    if (endiannessSelect) endiannessSelect.value = 'big-endian';
    
    const unitSelect = document.getElementById('mappingUnit');
    if (unitSelect) unitSelect.value = '';
    
    const scaleInput = document.getElementById('mappingScale');
    if (scaleInput) scaleInput.value = '1';
    
    const offsetInput = document.getElementById('mappingOffset');
    if (offsetInput) offsetInput.value = '0';
    
    const pollIntervalInput = document.getElementById('mappingPollInterval');
    if (pollIntervalInput) pollIntervalInput.value = '200';
    
    const pollPresetSelect = document.getElementById('mappingPollPreset');
    if (pollPresetSelect) pollPresetSelect.value = '200';
    
    const categorySelect = document.getElementById('mappingCategory');
    if (categorySelect) categorySelect.value = 'Sensors';
}

// Update step indicator
function updateStepIndicator() {
    // Update circles
    for (let i = 1; i <= 3; i++) {
        const circle = document.getElementById(`step${i}`);
        const label = circle ? circle.nextElementSibling : null;
        
        if (circle) {
            if (i === currentStep) {
                circle.className = 'step-circle active';
                if (label) label.className = 'step-label active';
            } else if (i < currentStep) {
                circle.className = 'step-circle active';
                if (label) label.className = 'step-label';
            } else {
                circle.className = 'step-circle inactive';
                if (label) label.className = 'step-label';
            }
        }
    }
    
    // Show/hide sections
    document.querySelectorAll('.dynamic-section').forEach(section => {
        section.classList.remove('active');
    });
    
    const currentStepContent = document.getElementById(`step${currentStep}-content`);
    if (currentStepContent) {
        currentStepContent.classList.add('active');
    }
}

// Navigate between steps
function goToStep(step) {
    if (step >= 1 && step <= 3) {
        currentStep = step;
        updateStepIndicator();
    }
}

// Delete mapping
function deleteMapping(id) {
    const mapping = mappings.find(m => m.id === id);
    if (!mapping) return;
    
    showConfirmationDialog(`Delete mapping "${mapping.tagName}"?`, 'Delete', 'Cancel')
        .then(confirmed => {
            if (confirmed) {
                // Remove mapping
                mappings = mappings.filter(m => m.id !== id);
                
                // Update device tag count
                const device = devices.find(d => d.id === mapping.deviceId);
                if (device) {
                    device.tags = mappings.filter(m => m.deviceId === device.id).length;
                }
                
                generateTags();
                renderMappingsTable();
                renderTagsList();
                
                showNotification('Mapping deleted successfully!', 'success');
            }
        });
}

// Setup modal event listeners
function setupModalEventListeners() {
    // Close modal button
    const closeModalBtn = document.getElementById('closeEditMappingModal');
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', function() {
            document.getElementById('editMappingModal').classList.add('hidden');
        });
    }
    
    // Cancel edit button
    const cancelEditBtn = document.getElementById('cancelEditMapping');
    if (cancelEditBtn) {
        cancelEditBtn.addEventListener('click', function() {
            document.getElementById('editMappingModal').classList.add('hidden');
        });
    }
    
    // Step navigation
    const nextStep1Btn = document.getElementById('nextStep1Btn');
    if (nextStep1Btn) {
        nextStep1Btn.addEventListener('click', () => goToStep(2));
    }
    
    const prevStep2Btn = document.getElementById('prevStep2Btn');
    if (prevStep2Btn) {
        prevStep2Btn.addEventListener('click', () => goToStep(1));
    }
    
    const nextStep2Btn = document.getElementById('nextStep2Btn');
    if (nextStep2Btn) {
        nextStep2Btn.addEventListener('click', () => goToStep(3));
    }
    
    const prevStep3Btn = document.getElementById('prevStep3Btn');
    if (prevStep3Btn) {
        prevStep3Btn.addEventListener('click', () => goToStep(2));
    }
    
    // Poll preset selector
    const pollPresetSelect = document.getElementById('mappingPollPreset');
    if (pollPresetSelect) {
        pollPresetSelect.addEventListener('change', function() {
            const customInput = document.getElementById('mappingPollInterval');
            if (this.value === 'custom') {
                customInput.style.display = 'block';
                customInput.value = '500';
            } else {
                customInput.style.display = 'none';
                document.getElementById('mappingPollInterval').value = this.value;
            }
        });
    }
    
    // Data type change
    const dataTypeSelect = document.getElementById('mappingDataType');
    if (dataTypeSelect) {
        dataTypeSelect.addEventListener('change', function() {
            const optionsContainer = document.getElementById('data-type-options');
            const dataType = this.value;
            
            let options = '';
            
            if (dataType === 'STRING') {
                options = `
                    <div class="grid grid-cols-2 gap-3 mt-3">
                        <div>
                            <label class="block text-xs font-medium text-slate-700 mb-1">String Length</label>
                            <input type="number" min="1" max="255" value="20" class="w-full compact-input" id="mappingStringLength">
                        </div>
                        <div>
                            <label class="block text-xs font-medium text-slate-700 mb-1">Encoding</label>
                            <select class="w-full compact-select bg-white" id="mappingStringEncoding">
                                <option value="ascii">ASCII</option>
                                <option value="utf8">UTF-8</option>
                            </select>
                        </div>
                    </div>
                `;
            } else if (dataType === 'BOOL') {
                options = `
                    <div class="grid grid-cols-2 gap-3 mt-3">
                        <div>
                            <label class="block text-xs font-medium text-slate-700 mb-1">Bit Position</label>
                            <input type="number" min="0" max="15" value="0" class="w-full compact-input" id="mappingBitPosition">
                        </div>
                        <div>
                            <label class="block text-xs font-medium text-slate-700 mb-1">Inverted Logic</label>
                            <select class="w-full compact-select bg-white" id="mappingInverted">
                                <option value="false">Normal (1=ON)</option>
                                <option value="true">Inverted (0=ON)</option>
                            </select>
                        </div>
                    </div>
                `;
            }
            
            if (optionsContainer) {
                optionsContainer.innerHTML = options;
            }
        });
    }
    
    // Save mapping button
    const saveMappingBtn = document.getElementById('saveMappingBtn');
    if (saveMappingBtn) {
        saveMappingBtn.addEventListener('click', function() {
            const tagName = document.getElementById('mappingTagName').value.trim();
            const addressValue = document.getElementById('mappingAddressValue').value.trim();
            
            if (!tagName) {
                showNotification('Tag name is required', 'error');
                return;
            }
            
            if (!addressValue) {
                showNotification('Address value is required', 'error');
                return;
            }
            
            // Construct address based on protocol
            let address = addressValue;
            const addressTypeSelect = document.getElementById('mappingAddressType');
            const addressType = addressTypeSelect ? addressTypeSelect.value : '';
            
            if (currentProtocol === 'modbus' && addressType) {
                const prefixes = {
                    'holding': '4',
                    'input': '3',
                    'coil': '0',
                    'discrete': '1'
                };
                if (prefixes[addressType]) {
                    address = prefixes[addressType] + addressValue;
                }
            }
            
            if (selectedMappingId) {
                // Update existing mapping
                const mapping = mappings.find(m => m.id === selectedMappingId);
                if (mapping) {
                    Object.assign(mapping, {
                        tagName: tagName,
                        address: address,
                        description: document.getElementById('mappingDescription').value,
                        dataType: document.getElementById('mappingDataType').value,
                        endianness: document.getElementById('mappingEndianness').value,
                        unit: document.getElementById('mappingUnit').value,
                        scale: document.getElementById('mappingScale').value,
                        offset: document.getElementById('mappingOffset').value,
                        pollInterval: document.getElementById('mappingPollInterval').value,
                        category: document.getElementById('mappingCategory').value,
                        protocol: currentProtocol
                    });
                    
                    showNotification('Mapping updated successfully!', 'success');
                }
            } else {
                // Add new mapping
                const newMapping = {
                    id: mappings.length > 0 ? Math.max(...mappings.map(m => m.id)) + 1 : 1,
                    deviceId: selectedDeviceId,
                    address: address,
                    tagName: tagName,
                    dataType: document.getElementById('mappingDataType').value,
                    endianness: document.getElementById('mappingEndianness').value,
                    scale: document.getElementById('mappingScale').value,
                    offset: document.getElementById('mappingOffset').value,
                    unit: document.getElementById('mappingUnit').value,
                    pollInterval: document.getElementById('mappingPollInterval').value,
                    category: document.getElementById('mappingCategory').value,
                    description: document.getElementById('mappingDescription').value,
                    protocol: currentProtocol
                };
                
                mappings.push(newMapping);
                
                // Update device tag count
                const device = devices.find(d => d.id === selectedDeviceId);
                if (device) {
                    device.tags = mappings.filter(m => m.deviceId === selectedDeviceId).length;
                }
                
                showNotification('Mapping added successfully!', 'success');
            }
            
            // Refresh UI
            generateTags();
            renderMappingsTable();
            renderTagsList();
            
            // Close modal
            document.getElementById('editMappingModal').classList.add('hidden');
        });
    }
}

// Setup main event listeners
function setupEventListeners() {
    // Device filter - affects mapping table
    const deviceFilter = document.getElementById('deviceFilter');
    if (deviceFilter) {
        deviceFilter.addEventListener('change', renderMappingsTable);
    }

    // Tag filters
    const tagSearch = document.getElementById('tagSearch');
    if (tagSearch) {
        tagSearch.addEventListener('input', renderTagsList);
    }
    
    const tagCategoryFilter = document.getElementById('tagCategoryFilter');
    if (tagCategoryFilter) {
        tagCategoryFilter.addEventListener('change', renderTagsList);
    }
    
    const tagDeviceFilter = document.getElementById('tagDeviceFilter');
    if (tagDeviceFilter) {
        tagDeviceFilter.addEventListener('change', renderTagsList);
    }

    // Add Mapping button
    const addMappingBtn = document.getElementById('addMappingBtn');
    if (addMappingBtn) {
        addMappingBtn.addEventListener('click', addNewMapping);
    }

    const addFirstMappingBtn = document.getElementById('addFirstMappingBtn');
    if (addFirstMappingBtn) {
        addFirstMappingBtn.addEventListener('click', addNewMapping);
    }

    // Import/Export buttons
    const importCSVBtn = document.getElementById('importCSVBtn');
    if (importCSVBtn) {
        importCSVBtn.addEventListener('click', importCSV);
    }

    const exportCSVBtn = document.getElementById('exportCSVBtn');
    if (exportCSVBtn) {
        exportCSVBtn.addEventListener('click', exportCSV);
    }

    // Footer buttons
    const testDeviceBtn = document.getElementById('testDeviceBtn');
    if (testDeviceBtn) {
        testDeviceBtn.addEventListener('click', function() {
            if (!selectedDeviceId) {
                showNotification('Please select a device first', 'warning');
                return;
            }
            const device = devices.find(d => d.id === selectedDeviceId);
            const btn = this;
            const originalText = btn.innerHTML;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1 text-xs"></i> Testing...';
            btn.disabled = true;
            
            setTimeout(() => {
                btn.innerHTML = originalText;
                btn.disabled = false;
                showNotification(`Device "${device.name}" test successful! Response time: ${Math.floor(Math.random() * 100)}ms`, 'success');
            }, 1500);
        });
    }

    const validateAllBtn = document.getElementById('validateAllBtn');
    if (validateAllBtn) {
        validateAllBtn.addEventListener('click', function() {
            const btn = this;
            const originalText = btn.innerHTML;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1 text-xs"></i> Validating...';
            btn.disabled = true;
            
            setTimeout(() => {
                btn.innerHTML = originalText;
                btn.disabled = false;
                showNotification(`Validation complete! ${mappings.length} mappings validated successfully.`, 'success');
            }, 2000);
        });
    }

    // Save button
    const saveBtn = document.getElementById('saveBtn');
    if (saveBtn) {
        saveBtn.addEventListener('click', function() {
            const btn = this;
            const original = btn.innerHTML;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Saving...';
            btn.disabled = true;
            
            setTimeout(() => {
                btn.innerHTML = original;
                btn.disabled = false;
                showNotification('Configuration saved successfully!', 'success');
            }, 1000);
        });
    }

    // Cancel button
    const cancelBtn = document.getElementById('cancelBtn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function() {
            showConfirmationDialog('Discard all unsaved changes?', 'Discard', 'Keep Editing')
                .then(confirmed => {
                    if (confirmed) {
                        // Navigate back to general configuration
                        if (window.router && typeof window.router.navigateTo === 'function') {
                            window.router.navigateTo('general-configuration');
                        } else {
                            // Fallback to URL change
                            window.location.href = '?page=general-configuration';
                        }
                    }
                });
        });
    }

    // Reboot button
    const rebootBtn = document.getElementById('rebootBtn');
    if (rebootBtn) {
        rebootBtn.addEventListener('click', function() {
            showConfirmationDialog('Reboot gateway? All connections will be interrupted.', 'Reboot', 'Cancel')
                .then(confirmed => {
                    if (confirmed) {
                        showNotification('Gateway reboot initiated...', 'info');
                        // In a real implementation, this would call an API
                    }
                });
        });
    }

    // Reset button
    const resetBtn = document.getElementById('resetBtn');
    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            showConfirmationDialog('Reset all mappings to default? This cannot be undone.', 'Reset', 'Cancel')
                .then(confirmed => {
                    if (confirmed) {
                        // Reset to sample data
                        devices = [...sampleDevices];
                        mappings = [...sampleMappings];
                        generateTags();
                        renderMappingsTable();
                        renderTagsList();
                        showNotification('Mappings reset to default values', 'success');
                    }
                });
        });
    }
}

// Initialize when DOM is loaded (for standalone testing)
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        // Only auto-init if we're not using the router
        if (typeof initializeModbusMapping === 'function' && !window.router) {
            initializeModbusMapping();
        }
    });
}