//initialize device-management
 // Add this to your router or as a separate JS file
window.initializeDeviceManagement = function() {
    console.log('Device Management page initialized');
    
    // Initialize all functionality for this page
    initDeviceManagementApp(); // Different name to avoid recursion
};

function initDeviceManagementApp() {
    console.log('Setting up Device Management page functionality');
    
    // Initialize the app
    initApp();
    
    // Add styles for this page
    addDeviceManagementStyles();
}


// Device data
const deviceData = [
    {
        id: 'loadcell',
        name: 'LoadCell-Front',
        type: 'Modbus RTU',
        address: 'Slave 01',
        status: 'Online',
        lastPoll: '2 sec ago',
        firmware: '1.2.4',
        group: 'Safety Sensors',
        details: {
            status: 'Online',
            lastResponse: '2 sec ago',
            retries: 0,
            signalStrength: 'N/A (Wired)',
            firmwareVersion: '1.2.4'
        }
    },
    {
        id: 'boomangle',
        name: 'BoomAngleSensor',
        type: 'CAN',
        address: '0x212',
        status: 'Online',
        lastPoll: '500 ms ago',
        firmware: '2.1.0',
        group: 'Crane-01',
        details: {
            status: 'Online',
            lastResponse: '500 ms ago',
            retries: 0,
            signalStrength: 'Good',
            firmwareVersion: '2.1.0'
        }
    },
    {
        id: 'acs',
        name: 'ACS-Node-Left',
        type: 'Wireless',
        address: 'RF:0x09',
        status: 'Offline',
        lastPoll: '20 sec ago',
        firmware: '1.5.2',
        group: 'Safety Sensors',
        details: {
            status: 'Offline',
            lastResponse: '20 sec ago',
            retries: 3,
            signalStrength: '-70 dBm',
            firmwareVersion: '1.5.2'
        }
    },
    {
        id: 'io',
        name: 'IO-Mod-CT-3',
        type: 'Wireless',
        address: 'RF:0x11',
        status: 'Online',
        lastPoll: '1 sec ago',
        firmware: '3.0.1',
        group: 'Motors & Brakes',
        details: {
            status: 'Online',
            lastResponse: '1 sec ago',
            retries: 0,
            signalStrength: '-65 dBm',
            firmwareVersion: '3.0.1'
        }
    },
    {
        id: 'modbustcp',
        name: 'PLC-Main',
        type: 'Modbus TCP',
        address: '192.168.1.100:502',
        status: 'Online',
        lastPoll: '1 sec ago',
        firmware: '2.3.0',
        group: 'Crane-01',
        details: {
            status: 'Online',
            lastResponse: '1 sec ago',
            retries: 0,
            signalStrength: 'N/A (Wired)',
            firmwareVersion: '2.3.0'
        }
    }
];

// Group data
const groupData = [
    { id: 1, name: 'Crane 01', deviceCount: 3, color: 'blue' },
    { id: 2, name: 'Crane 02', deviceCount: 2, color: 'green' },
    { id: 3, name: 'Safety Sensors', deviceCount: 5, color: 'purple' },
    { id: 4, name: 'Motors & Brakes', deviceCount: 4, color: 'orange' }
];

// Global state
let devices = [];
let groups = [];
let selectedDeviceId = null;
let selectedColor = 'blue';
let selectedGroupId = null;
let selectedDevicesForAssignment = new Set();

function addDeviceManagementStyles() {
    // Add styles specific to device management page
    const style = document.createElement('style');
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
            z-index: 50;
            overflow-y: auto;
        }
        
        .add-device-panel.active {
            right: 0;
        }
        
        .protocol-config {
            display: none;
        }
        
        .protocol-config.active {
            display: block;
        }
        
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
            z-index: 1000;
            border: 1px solid #E2E8F0;
            border-radius: 6px;
            padding: 4px 0;
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
        
        .show {
            display: block;
        }
        
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(0,0,0,0.5);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        
        .modal-overlay.active {
            display: flex;
        }
        
        .modal {
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);
            min-width: 400px;
            max-width: 500px;
            max-height: 90vh;
            overflow-y: auto;
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
        
        .main-content-with-sidebar {
            margin-left: 0;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
    `;
    document.head.appendChild(style);
}

function initApp() {
    devices = [...deviceData];
    groups = [...groupData];
    
    renderDevicesTable();
    renderGroups();
    setupEventListeners();
    initGroupModal();
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

function renderDevicesTable() {
    const tbody = document.getElementById('devicesTableBody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    devices.forEach(device => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-slate-50 transition-colors';
        row.id = `device-${device.id}`;
        row.dataset.deviceId = device.id;
        
        let statusColor = 'bg-green-500';
        if (device.status === 'Offline') {
            statusColor = 'bg-red-500';
        } else if (device.status === 'Warning') {
            statusColor = 'bg-yellow-500';
        }
        
        let typeColor = 'bg-blue-100 text-blue-800';
        if (device.type === 'CAN') typeColor = 'bg-orange-100 text-orange-800';
        if (device.type === 'Wireless') typeColor = 'bg-purple-100 text-purple-800';
        if (device.type === 'Modbus TCP') typeColor = 'bg-cyan-100 text-cyan-800';
        if (device.type === 'ACS Sensor') typeColor = 'bg-indigo-100 text-indigo-800';
        
        row.innerHTML = `
            <td class="p-4">
                <div class="font-medium text-slate-900">${device.name}</div>
                <div class="text-xs text-slate-500 mt-1">Firmware: ${device.firmware}</div>
            </td>
            <td class="p-4">
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${typeColor}">
                    ${device.type}
                </span>
            </td>
            <td class="p-4">
                <div class="font-mono text-sm">${device.address}</div>
            </td>
            <td class="p-4">
                <div class="flex items-center">
                    <span class="w-2 h-2 rounded-full ${statusColor} mr-2"></span>
                    <span class="text-sm text-slate-700">${device.status}</span>
                </div>
            </td>
            <td class="p-4">
                <div class="text-sm">${device.lastPoll}</div>
            </td>
            <td class="p-4 text-right">
                <div class="action-dropdown flex justify-end">
                    <button class="text-primary hover:text-primaryHover text-sm font-medium dropdown-toggle" onclick="window.deviceManagement.toggleDropdown('${device.id}')">
                        Edit ▾
                    </button>
                    <div class="action-dropdown-content" id="dropdown-${device.id}">
                        <a href="#" onclick="window.deviceManagement.editDevice('${device.id}')">Edit Device</a>
                        <a href="#" onclick="window.deviceManagement.showDeviceDetails('${device.id}')">View Details</a>
                        <a href="#" onclick="window.deviceManagement.disableDevice('${device.id}')">Disable Device</a>
                        <a href="#" onclick="window.deviceManagement.deleteDevice('${device.id}')" class="text-red-600">Delete Device</a>
                    </div>
                </div>
            </td>
        `;
        
        tbody.appendChild(row);
    });
}

function renderGroups() {
    const container = document.getElementById('groupsContainer');
    if (!container) return;
    
    container.innerHTML = '';
    
    groups.forEach(group => {
        const groupElement = document.createElement('div');
        groupElement.className = 'border border-slate-200 rounded-lg p-4';
        groupElement.innerHTML = `
            <div class="flex items-center justify-between mb-2">
                <h4 class="font-medium text-slate-900">${group.name}</h4>
                <span class="w-3 h-3 rounded-full bg-${group.color}-500"></span>
            </div>
            <div class="text-xs text-slate-500 mb-3">${group.deviceCount} devices</div>
            <button class="text-xs text-primary hover:text-primaryHover" onclick="window.deviceManagement.openAssignDevicesModal(${group.id})">
                Assign Devices →
            </button>
        `;
        container.appendChild(groupElement);
    });
}

function showDeviceDetails(deviceId) {
    const device = devices.find(d => d.id === deviceId);
    if (!device) return;
    
    selectedDeviceId = deviceId;
    
    document.getElementById('selectedDeviceTitle').textContent = 'Device Details';
    document.getElementById('selectedDeviceName').textContent = `Selected: ${device.name}`;
    document.getElementById('deviceStatus').textContent = device.details.status;
    document.getElementById('lastResponse').textContent = device.details.lastResponse;
    document.getElementById('retries').textContent = device.details.retries;
    document.getElementById('signalStrength').textContent = device.details.signalStrength;
    document.getElementById('firmwareVersion').textContent = device.details.firmwareVersion;
    
    document.getElementById('section-details').style.display = 'block';
    
    closeAllDropdowns();
}

function toggleDropdown(deviceId) {
    const dropdown = document.getElementById(`dropdown-${deviceId}`);
    const isVisible = dropdown.classList.contains('show');
    
    closeAllDropdowns();
    
    if (!isVisible) {
        dropdown.classList.add('show');
        
        setTimeout(() => {
            const closeHandler = (e) => {
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
    document.querySelectorAll('.action-dropdown-content').forEach(dropdown => {
        dropdown.classList.remove('show');
    });
}

function editDevice(deviceId) {
    const device = devices.find(d => d.id === deviceId);
    if (!device) return;
    
    document.getElementById('addDevicePanel').classList.add('active');
    document.getElementById('deviceNameInput').value = device.name;
    document.getElementById('deviceGroupSelect').value = device.group;
    
    let protocol = 'modbus-rtu';
    if (device.type === 'CAN') protocol = 'canbus';
    if (device.type === 'Wireless') protocol = 'wireless';
    if (device.type === 'Modbus TCP') protocol = 'modbus-tcp';
    if (device.type === 'ACS Sensor') protocol = 'acs';
    
    document.querySelector(`input[name="device-type"][value="${protocol}"]`).checked = true;
    document.querySelector(`input[name="device-type"][value="${protocol}"]`).dispatchEvent(new Event('change'));
    
    if (protocol === 'modbus-rtu') {
        const slaveMatch = device.address.match(/Slave\s*(\d+)/);
        if (slaveMatch) {
            document.getElementById('modbusAddress').value = slaveMatch[1];
        }
    } else if (protocol === 'modbus-tcp') {
        const tcpMatch = device.address.match(/(\d+\.\d+\.\d+\.\d+):(\d+)/);
        if (tcpMatch) {
            document.getElementById('modbusTcpIp').value = tcpMatch[1];
            document.getElementById('modbusTcpPort').value = tcpMatch[2];
        }
    } else if (protocol === 'canbus') {
        document.getElementById('canId').value = device.address;
    } else if (protocol === 'wireless') {
        document.getElementById('rfAddress').value = device.address;
    } else if (protocol === 'acs') {
        document.getElementById('acsSensorId').value = device.address;
    }
    
    closeAllDropdowns();
}

function disableDevice(deviceId) {
    const device = devices.find(d => d.id === deviceId);
    if (!device) return;
    
    if (confirm(`Disable ${device.name}?`)) {
        device.status = device.status === 'Disabled' ? 'Online' : 'Disabled';
        renderDevicesTable();
        alert(`Device ${device.name} ${device.status === 'Disabled' ? 'disabled' : 'enabled'} successfully.`);
    }
    closeAllDropdowns();
}

function deleteDevice(deviceId) {
    const device = devices.find(d => d.id === deviceId);
    if (!device) return;
    
    if (confirm(`Are you sure you want to delete ${device.name}? This action cannot be undone.`)) {
        devices = devices.filter(d => d.id !== deviceId);
        renderDevicesTable();
        
        if (selectedDeviceId === deviceId) {
            document.getElementById('section-details').style.display = 'none';
            selectedDeviceId = null;
        }
        
        alert(`Device ${device.name} deleted successfully.`);
    }
    closeAllDropdowns();
}

function openAssignDevicesModal(groupId) {
    selectedGroupId = groupId;
    selectedDevicesForAssignment.clear();
    
    document.querySelectorAll('.group-item').forEach(item => {
        item.classList.remove('border-primary', 'bg-blue-50');
        if (parseInt(item.dataset.groupId) === groupId) {
            item.classList.add('border-primary', 'bg-blue-50');
        }
    });
    
    renderAssignDevicesList();
    document.getElementById('assignDevicesModal').classList.add('active');
}

function renderAssignDevicesList() {
    const container = document.getElementById('assignDevicesList');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (devices.length === 0) {
        container.innerHTML = '<div class="text-center text-slate-500 py-4">No devices available</div>';
        return;
    }
    
    devices.forEach(device => {
        const isSelected = selectedDevicesForAssignment.has(device.id);
        
        const deviceElement = document.createElement('label');
        deviceElement.className = `flex items-center p-3 border rounded-lg cursor-pointer hover:bg-slate-50 ${isSelected ? 'border-primary bg-blue-50' : 'border-slate-300'}`;
        deviceElement.innerHTML = `
            <input type="checkbox" class="h-4 w-4 text-primary focus:ring-primary border-slate-300 rounded" ${isSelected ? 'checked' : ''} value="${device.id}" onchange="window.deviceManagement.toggleDeviceSelection('${device.id}', this.checked)">
            <div class="ml-3 flex-1">
                <div class="flex justify-between">
                    <div class="font-medium text-sm text-slate-900">${device.name}</div>
                    <div class="text-xs text-slate-500">${device.type}</div>
                </div>
                <div class="flex justify-between mt-1">
                    <div class="text-xs text-slate-600">${device.address}</div>
                    <div class="text-xs ${device.status === 'Online' ? 'text-green-600' : 'text-red-600'}">${device.status}</div>
                </div>
            </div>
        `;
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

function assignDevicesToGroup() {
    if (!selectedGroupId) {
        alert('Please select a group first.');
        return;
    }
    
    if (selectedDevicesForAssignment.size === 0) {
        alert('Please select at least one device to assign.');
        return;
    }
    
    const group = groups.find(g => g.id === selectedGroupId);
    if (!group) return;
    
    let assignedCount = 0;
    
    selectedDevicesForAssignment.forEach(deviceId => {
        const device = devices.find(d => d.id === deviceId);
        if (device) {
            device.group = group.name;
            assignedCount++;
        }
    });
    
    updateGroupDeviceCounts();
    renderDevicesTable();
    renderGroups();
    
    document.getElementById('assignDevicesModal').classList.remove('active');
    alert(`Successfully assigned ${assignedCount} device(s) to ${group.name}.`);
}

function updateGroupDeviceCounts() {
    groups.forEach(group => {
        group.deviceCount = devices.filter(d => d.group === group.name).length;
    });
}

function addNewGroup() {
    document.getElementById('groupNameInput').value = '';
    document.getElementById('groupDescription').value = '';
    
    const colorSelection = document.querySelector('#addGroupModal .flex.space-x-2');
    if (colorSelection) {
        colorSelection.querySelectorAll('button').forEach(btn => {
            btn.classList.remove('border-blue-700');
            btn.classList.add('border-transparent');
        });
        const firstButton = colorSelection.querySelector('button[data-color="blue"]');
        if (firstButton) {
            firstButton.classList.remove('border-transparent');
            firstButton.classList.add('border-blue-700');
        }
    }
    
    document.getElementById('addGroupModal').classList.add('active');
    selectedColor = 'blue';
}

function saveNewGroup() {
    const nameInput = document.getElementById('groupNameInput');
    
    if (!nameInput.value.trim()) {
        alert('Please enter a group name.');
        return;
    }
    
    const selectedColorBtn = document.querySelector('#addGroupModal .flex.space-x-2 button.border-blue-700');
    const color = selectedColorBtn ? selectedColorBtn.dataset.color : 'blue';
    
    const newGroup = {
        id: groups.length + 1,
        name: nameInput.value,
        deviceCount: 0,
        color: color
    };
    
    groups.push(newGroup);
    renderGroups();
    updateGroupDeviceCounts();
    
    const groupFilter = document.getElementById('groupFilter');
    const option = document.createElement('option');
    option.value = newGroup.name;
    option.textContent = newGroup.name;
    groupFilter.appendChild(option);
    
    const deviceGroupSelect = document.getElementById('deviceGroupSelect');
    const option2 = document.createElement('option');
    option2.value = newGroup.name;
    option2.textContent = newGroup.name;
    deviceGroupSelect.appendChild(option2);
    
    nameInput.value = '';
    document.getElementById('groupDescription').value = '';
    document.getElementById('addGroupModal').classList.remove('active');
    
    alert(`Group "${newGroup.name}" created successfully.`);
}

// CSV Export/Import Functions
function convertToCSV(devicesArray) {
    if (devicesArray.length === 0) return '';
    
    const headers = ['Device Name', 'Type', 'Address/ID', 'Status', 'Last Poll', 'Firmware', 'Group'];
    
    let csv = headers.join(',') + '\n';
    
    devicesArray.forEach(device => {
        const row = [
            `"${device.name.replace(/"/g, '""')}"`,
            `"${device.type.replace(/"/g, '""')}"`,
            `"${device.address.replace(/"/g, '""')}"`,
            `"${device.status.replace(/"/g, '""')}"`,
            `"${device.lastPoll.replace(/"/g, '""')}"`,
            `"${device.firmware.replace(/"/g, '""')}"`,
            `"${device.group.replace(/"/g, '""')}"`
        ];
        csv += row.join(',') + '\n';
    });
    
    return csv;
}

function downloadCSV(csvContent, fileName = 'devices-export.csv') {
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    
    if (navigator.msSaveBlob) {
        navigator.msSaveBlob(blob, fileName);
    } else {
        link.href = URL.createObjectURL(blob);
        link.download = fileName;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
}

function parseCSV(csvText) {
    const lines = csvText.split('\n');
    if (lines.length < 2) return [];
    
    const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
    const devices = [];
    
    for (let i = 1; i < lines.length; i++) {
        if (!lines[i].trim()) continue;
        
        const values = [];
        let currentValue = '';
        let insideQuotes = false;
        
        for (let char of lines[i]) {
            if (char === '"') {
                insideQuotes = !insideQuotes;
            } else if (char === ',' && !insideQuotes) {
                values.push(currentValue);
                currentValue = '';
            } else {
                currentValue += char;
            }
        }
        values.push(currentValue);
        
        const device = {};
        
        headers.forEach((header, index) => {
            if (values[index] !== undefined) {
                device[header] = values[index].trim().replace(/"/g, '');
            }
        });
        
        if (device['Device Name']) {
            devices.push({
                id: `imported-${Date.now()}-${i}`,
                name: device['Device Name'] || 'Imported Device',
                type: device['Type'] || 'Unknown',
                address: device['Address/ID'] || 'N/A',
                status: device['Status'] || 'Online',
                lastPoll: device['Last Poll'] || 'Just now',
                firmware: device['Firmware'] || '1.0.0',
                group: device['Group'] || 'None',
                details: {
                    status: device['Status'] || 'Online',
                    lastResponse: device['Last Poll'] || 'Just now',
                    retries: 0,
                    signalStrength: 'N/A',
                    firmwareVersion: device['Firmware'] || '1.0.0'
                }
            });
        }
    }
    
    return devices;
}

function downloadCSVTemplate() {
    const templateHeaders = ['Device Name', 'Type', 'Address/ID', 'Status', 'Last Poll', 'Firmware', 'Group'];
    const exampleRows = [
        ['LoadCell-Front', 'Modbus RTU', 'Slave 01', 'Online', '2 sec ago', '1.2.4', 'Safety Sensors'],
        ['BoomAngleSensor', 'CAN', '0x212', 'Online', '500 ms ago', '2.1.0', 'Crane-01'],
        ['ACS-Node-Left', 'Wireless', 'RF:0x09', 'Offline', '20 sec ago', '1.5.2', 'Safety Sensors'],
        ['PLC-Main', 'Modbus TCP', '192.168.1.100:502', 'Online', '1 sec ago', '2.3.0', 'Crane-01']
    ];
    
    let csv = templateHeaders.join(',') + '\n';
    exampleRows.forEach(row => {
        csv += row.map(v => `"${v}"`).join(',') + '\n';
    });
    
    downloadCSV(csv, 'device-template.csv');
}

function setupEventListeners() {
    // Add device panel
    document.getElementById('addDeviceBtn').addEventListener('click', function() {
        document.getElementById('addDevicePanel').classList.add('active');
        document.getElementById('deviceNameInput').value = '';
        document.getElementById('deviceGroupSelect').value = 'None';
        document.querySelector('input[name="device-type"][value="modbus-rtu"]').checked = true;
        document.querySelector('input[name="device-type"][value="modbus-rtu"]').dispatchEvent(new Event('change'));
    });

    document.getElementById('closeAddDevicePanel').addEventListener('click', function() {
        document.getElementById('addDevicePanel').classList.remove('active');
    });

    document.getElementById('cancelAddDevice').addEventListener('click', function() {
        document.getElementById('addDevicePanel').classList.remove('active');
    });

    // Protocol selection
    document.querySelectorAll('input[name="device-type"]').forEach(radio => {
        radio.addEventListener('change', function() {
            document.querySelectorAll('.protocol-config').forEach(config => {
                config.classList.remove('active');
            });
            
            const configId = this.value + '-config';
            const configElement = document.getElementById(configId);
            if (configElement) {
                configElement.classList.add('active');
            }
        });
    });

    // Save device
    document.getElementById('saveDeviceBtn').addEventListener('click', function() {
        const deviceName = document.getElementById('deviceNameInput').value.trim();
        const deviceGroup = document.getElementById('deviceGroupSelect').value;
        const deviceType = document.querySelector('input[name="device-type"]:checked').value;
        
        if (!deviceName) {
            alert('Please enter a device name.');
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
        if (deviceType === 'modbus-rtu') {
            const slaveAddress = document.getElementById('modbusAddress').value;
            address = `Slave ${slaveAddress}`;
        } else if (deviceType === 'modbus-tcp') {
            const ip = document.getElementById('modbusTcpIp').value;
            const port = document.getElementById('modbusTcpPort').value;
            address = `${ip}:${port}`;
        } else if (deviceType === 'canbus') {
            address = document.getElementById('canId').value;
        } else if (deviceType === 'wireless') {
            address = document.getElementById('rfAddress').value;
        } else if (deviceType === 'acs') {
            address = document.getElementById('acsSensorId').value;
        }
        
        const newDevice = {
            id: `device-${Date.now()}`,
            name: deviceName,
            type: typeMap[deviceType],
            address: address,
            status: 'Online',
            lastPoll: 'Just now',
            firmware: '1.0.0',
            group: deviceGroup,
            details: {
                status: 'Online',
                lastResponse: 'Just now',
                retries: 0,
                signalStrength: 'N/A',
                firmwareVersion: '1.0.0'
            }
        };
        
        devices.push(newDevice);
        updateGroupDeviceCounts();
        renderDevicesTable();
        renderGroups();
        
        document.getElementById('addDevicePanel').classList.remove('active');
        alert(`Device "${deviceName}" added successfully.`);
    });

    // Add group modal
    document.getElementById('addGroupBtn').addEventListener('click', addNewGroup);
    
    document.getElementById('closeGroupModal').addEventListener('click', function() {
        document.getElementById('addGroupModal').classList.remove('active');
    });
    
    document.getElementById('cancelGroupBtn').addEventListener('click', function() {
        document.getElementById('addGroupModal').classList.remove('active');
    });
    
    document.getElementById('saveGroupBtn').addEventListener('click', saveNewGroup);
    
    // Color selection
    const colorSelection = document.querySelector('#addGroupModal .flex.space-x-2');
    if (colorSelection) {
        colorSelection.addEventListener('click', function(e) {
            if (e.target.dataset.color) {
                selectedColor = e.target.dataset.color;
                
                this.querySelectorAll('button').forEach(btn => {
                    btn.classList.remove('border-blue-700');
                    btn.classList.add('border-transparent');
                });
                
                e.target.classList.remove('border-transparent');
                e.target.classList.add('border-blue-700');
            }
        });
    }

    // Device actions in details section
    document.getElementById('pingDeviceBtn').addEventListener('click', function() {
        if (!selectedDeviceId) return;
        const device = devices.find(d => d.id === selectedDeviceId);
        if (!device) return;
        
        this.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Pinging...';
        this.disabled = true;
        
        setTimeout(() => {
            this.innerHTML = 'Ping Device';
            this.disabled = false;
            alert(`Ping response from ${device.name}: OK (2ms)`);
        }, 1000);
    });
    
    document.getElementById('viewPacketsBtn').addEventListener('click', function() {
        if (!selectedDeviceId) return;
        const device = devices.find(d => d.id === selectedDeviceId);
        if (!device) return;
        
        alert(`Showing last 10 packets for ${device.name}. In a real application, this would open a packet viewer.`);
    });
    
    document.getElementById('disableDeviceBtn').addEventListener('click', function() {
        if (!selectedDeviceId) return;
        disableDevice(selectedDeviceId);
    });
    
    document.getElementById('deleteDeviceBtn').addEventListener('click', function() {
        if (!selectedDeviceId) return;
        deleteDevice(selectedDeviceId);
    });
    
    document.getElementById('duplicateDeviceBtn').addEventListener('click', function() {
        if (!selectedDeviceId) return;
        const device = devices.find(d => d.id === selectedDeviceId);
        if (!device) return;
        
        const duplicatedDevice = {
            ...device,
            id: `device-${Date.now()}`,
            name: `${device.name} (Copy)`,
            status: 'Online',
            lastPoll: 'Just now'
        };
        
        devices.push(duplicatedDevice);
        renderDevicesTable();
        alert(`Device "${device.name}" duplicated successfully.`);
    });

    // Filters
    document.getElementById('searchInput').addEventListener('input', function(e) {
        const searchTerm = e.target.value.toLowerCase();
        const filteredDevices = deviceData.filter(device => 
            device.name.toLowerCase().includes(searchTerm) ||
            device.type.toLowerCase().includes(searchTerm) ||
            device.address.toLowerCase().includes(searchTerm)
        );
        updateTable(filteredDevices);
    });
    
    document.getElementById('deviceTypeFilter').addEventListener('change', function(e) {
        filterDevices();
    });
    
    document.getElementById('statusFilter').addEventListener('change', function(e) {
        filterDevices();
    });
    
    document.getElementById('groupFilter').addEventListener('change', function(e) {
        filterDevices();
    });

    // Scan Networks button
    document.getElementById('scanNetworksBtn').addEventListener('click', function() {
        document.getElementById('scanDeviceTypeModal').classList.add('active');
    });
    
    // Scan modal event listeners
    document.getElementById('closeScanModal').addEventListener('click', function() {
        document.getElementById('scanDeviceTypeModal').classList.remove('active');
    });
    
    document.getElementById('cancelScanBtn').addEventListener('click', function() {
        document.getElementById('scanDeviceTypeModal').classList.remove('active');
    });
    
    // Assign Devices Modal
    document.getElementById('closeAssignModal').addEventListener('click', function() {
        document.getElementById('assignDevicesModal').classList.remove('active');
    });
    
    document.getElementById('cancelAssignBtn').addEventListener('click', function() {
        document.getElementById('assignDevicesModal').classList.remove('active');
    });
    
    document.getElementById('assignDevicesBtn').addEventListener('click', assignDevicesToGroup);
    
    // Quick actions in assign modal
    document.getElementById('selectAllBtn').addEventListener('click', function() {
        devices.forEach(device => {
            selectedDevicesForAssignment.add(device.id);
        });
        renderAssignDevicesList();
    });
    
    document.getElementById('deselectAllBtn').addEventListener('click', function() {
        selectedDevicesForAssignment.clear();
        renderAssignDevicesList();
    });
    
    document.getElementById('selectOnlineBtn').addEventListener('click', function() {
        devices.forEach(device => {
            if (device.status === 'Online') {
                selectedDevicesForAssignment.add(device.id);
            }
        });
        renderAssignDevicesList();
    });
    
    document.getElementById('selectByTypeBtn').addEventListener('click', function() {
        const typeToSelect = prompt('Enter device type to select (e.g., Modbus RTU, CAN, Wireless):', 'Modbus RTU');
        if (typeToSelect) {
            devices.forEach(device => {
                if (device.type === typeToSelect) {
                    selectedDevicesForAssignment.add(device.id);
                }
            });
            renderAssignDevicesList();
        }
    });
    
    // Group selection in assign modal
    document.querySelectorAll('.group-item').forEach(item => {
        item.addEventListener('click', function() {
            const groupId = parseInt(this.dataset.groupId);
            selectedGroupId = groupId;
            
            document.querySelectorAll('.group-item').forEach(i => {
                i.classList.remove('border-primary', 'bg-blue-50');
            });
            this.classList.add('border-primary', 'bg-blue-50');
        });
    });

    // Refresh button
    document.getElementById('refreshBtn').addEventListener('click', function() {
        this.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Refreshing...';
        this.disabled = true;
        
        setTimeout(() => {
            this.innerHTML = '<i class="fa-solid fa-sync mr-2 text-slate-400"></i> Refresh';
            this.disabled = false;
            alert('Device list refreshed successfully!');
        }, 1000);
    });
    
    // Export button
    document.getElementById('exportBtn').addEventListener('click', function() {
        const exportAll = document.getElementById('export-all-devices').checked;
        const exportTimestamp = document.getElementById('export-timestamp').checked;
        
        let devicesToExport = exportAll ? devices : devices.filter(d => d.status === 'Online');
        
        if (devicesToExport.length === 0) {
            alert('No devices to export.');
            return;
        }
        
        let csvContent = convertToCSV(devicesToExport);
        
        if (exportTimestamp) {
            const timestamp = new Date().toISOString().replace(/:/g, '-').split('.')[0];
            const filename = `devices-export-${timestamp}.csv`;
            downloadCSV(csvContent, filename);
        } else {
            downloadCSV(csvContent, 'devices-export.csv');
        }
        
        alert(`Exported ${devicesToExport.length} devices to CSV.`);
    });

    // Import functionality
    document.getElementById('browseFilesBtn').addEventListener('click', function() {
        document.getElementById('fileInput').click();
    });

    document.getElementById('fileInput').addEventListener('change', handleFileSelect);

    // Drag and drop functionality
    const dropArea = document.getElementById('dropArea');
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
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

    document.getElementById('importBtn').addEventListener('click', function() {
        const content = this.dataset.fileContent;
        const filename = this.dataset.fileName;
        
        if (!content) {
            alert('Please select a CSV file first.');
            return;
        }
        
        const overwrite = document.getElementById('import-overwrite').checked;
        const useTemplate = document.getElementById('import-template').checked;
        
        const importStatus = document.getElementById('importStatus');
        const statusText = document.getElementById('statusText');
        const statusCount = document.getElementById('statusCount');
        const progressBar = document.getElementById('progressBar');
        
        importStatus.classList.remove('hidden');
        statusText.textContent = 'Processing CSV file...';
        progressBar.style.width = '30%';
        
        try {
            const importedDevices = parseCSV(content);
            
            if (importedDevices.length === 0) {
                statusText.textContent = 'No valid devices found in CSV';
                progressBar.style.width = '0%';
                setTimeout(() => {
                    importStatus.classList.add('hidden');
                }, 3000);
                alert('No valid devices found in the CSV file. Please check the format.');
                return;
            }
            
            statusText.textContent = `Importing ${importedDevices.length} devices...`;
            progressBar.style.width = '60%';
            statusCount.textContent = `0/${importedDevices.length} devices`;
            
            setTimeout(() => {
                if (overwrite) {
                    devices = [...importedDevices];
                } else {
                    devices = [...devices, ...importedDevices];
                }
                
                updateGroupDeviceCounts();
                renderDevicesTable();
                renderGroups();
                
                progressBar.style.width = '100%';
                statusText.textContent = 'Import completed successfully!';
                statusCount.textContent = `${importedDevices.length} devices imported`;
                
                setTimeout(() => {
                    importStatus.classList.add('hidden');
                    progressBar.style.width = '0%';
                    
                    const importBtn = document.getElementById('importBtn');
                    importBtn.disabled = true;
                    importBtn.innerHTML = '<i class="fa-solid fa-upload mr-2"></i> Import from CSV';
                    delete importBtn.dataset.fileContent;
                    delete importBtn.dataset.fileName;
                    
                    alert(`Successfully imported ${importedDevices.length} devices from CSV.`);
                }, 3000);
                
            }, 1000);
            
        } catch (error) {
            statusText.textContent = 'Error importing CSV file';
            statusCount.textContent = 'Invalid format';
            progressBar.style.width = '0%';
            console.error('Import error:', error);
            
            setTimeout(() => {
                importStatus.classList.add('hidden');
                alert('Error importing CSV file. Please ensure it has the correct format.');
            }, 3000);
        }
    });

    // Template download button
    document.getElementById('downloadCsvTemplateBtn').addEventListener('click', downloadCSVTemplate);

    document.getElementById('scanRfBtn').addEventListener('click', function() {
        this.innerHTML = 'Scanning...';
        this.disabled = true;
        
        setTimeout(() => {
            this.innerHTML = 'Scan';
            this.disabled = false;
            document.getElementById('rfAddress').value = 'RF:0x' + Math.floor(Math.random() * 256).toString(16).toUpperCase();
            document.getElementById('signalStrengthDisplay').textContent = `-${60 + Math.floor(Math.random() * 20)} dBm`;
        }, 1500);
    });
    
    document.getElementById('startPairingBtn').addEventListener('click', function() {
        this.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Pairing...';
        this.disabled = true;
        
        setTimeout(() => {
            this.innerHTML = '<i class="fa-solid fa-link mr-2"></i> Start Pairing';
            this.disabled = false;
            alert('Wireless device paired successfully!');
        }, 2000);
    });

    // Save buttons
    document.getElementById('footer-save-btn').addEventListener('click', saveConfiguration);
    
    // Cancel/Back button
    document.getElementById('footer-cancel-btn').addEventListener('click', function() {
        if (confirm('Go back? Unsaved changes will be lost.')) {
            window.history.back();
        }
    });
}

function filterDevices() {
    const typeFilter = document.getElementById('deviceTypeFilter').value;
    const statusFilter = document.getElementById('statusFilter').value;
    const groupFilter = document.getElementById('groupFilter').value;
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    
    let filteredDevices = [...deviceData];
    
    if (searchTerm) {
        filteredDevices = filteredDevices.filter(device => 
            device.name.toLowerCase().includes(searchTerm) ||
            device.type.toLowerCase().includes(searchTerm) ||
            device.address.toLowerCase().includes(searchTerm)
        );
    }
    
    if (typeFilter !== 'All Device Types') {
        filteredDevices = filteredDevices.filter(device => device.type === typeFilter);
    }
    
    if (statusFilter !== 'All Status') {
        filteredDevices = filteredDevices.filter(device => device.status === statusFilter);
    }
    
    if (groupFilter !== 'All Groups') {
        filteredDevices = filteredDevices.filter(device => device.group === groupFilter);
    }
    
    updateTable(filteredDevices);
}

function updateTable(filteredDevices) {
    devices = filteredDevices;
    renderDevicesTable();
}

function saveConfiguration() {
    const footerSaveBtn = document.getElementById('footer-save-btn');
    
    footerSaveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Saving...';
    footerSaveBtn.disabled = true;
    
    setTimeout(() => {
        footerSaveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk mr-2"></i> Save Changes';
        footerSaveBtn.disabled = false;
        
        alert('Device configuration saved successfully!');
    }, 1500);
}

// File handling functions
function handleFiles(files) {
    if (files.length > 0) {
        const file = files[0];
        
        if (!file.name.endsWith('.csv')) {
            alert('Please select a CSV file.');
            return;
        }
        
        readFile(file);
    }
}

function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        const file = files[0];
        
        if (!file.name.endsWith('.csv')) {
            alert('Please select a CSV file.');
            return;
        }
        
        readFile(file);
    }
}

function readFile(file) {
    const reader = new FileReader();
    reader.onload = function(e) {
        const content = e.target.result;
        processFile(content, file.name);
    };
    
    reader.onerror = function() {
        alert('Error reading file. Please try again.');
    };
    
    reader.readAsText(file);
}

function processFile(content, filename) {
    if (!content.trim()) {
        alert('The file is empty.');
        return;
    }
    
    const importBtn = document.getElementById('importBtn');
    importBtn.disabled = false;
    importBtn.innerHTML = `<i class="fa-solid fa-upload mr-2"></i> Import from ${filename}`;
    
    importBtn.dataset.fileContent = content;
    importBtn.dataset.fileName = filename;
}

// Make functions available globally
window.deviceManagement = {
    toggleDropdown,
    editDevice,
    showDeviceDetails,
    disableDevice,
    deleteDevice,
    openAssignDevicesModal,
    toggleDeviceSelection,
    assignDevicesToGroup,
    addNewGroup,
    saveNewGroup};