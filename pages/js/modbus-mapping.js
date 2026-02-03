// modbus-mapping.js - JavaScript for Tag Mapping page
let currentMappings = [];
let allDevices = [];
let allTags = [];
let currentDevice = null;
let currentStep = 1;
let currentProtocol = '';

// ============================================================================
// INITIALIZATION
// ============================================================================

function initializeModbusMapping() {
    console.log('Initializing Modbus Mapping...');
    
    // Load devices and tags
    loadDevices();
    loadTags();
    
    // Setup event listeners
    setupEventListeners();
    
    // Initialize UI components
    initializeUI();
    
    console.log('Modbus Mapping initialized');
}

function initializeUI() {
    // Initialize device filter dropdown
    initializeDeviceFilter();
    
    // Initialize protocol tabs if needed
    initializeProtocolTabs();
}

function setupEventListeners() {
    // Add Mapping Button
    document.getElementById('addMappingBtn')?.addEventListener('click', showAddMappingModal);
    document.getElementById('addFirstMappingBtn')?.addEventListener('click', showAddMappingModal);
    
    // Modal controls
    document.getElementById('closeEditMappingModal')?.addEventListener('click', closeEditMappingModal);
    document.getElementById('cancelEditMapping')?.addEventListener('click', closeEditMappingModal);
    
    // Step navigation
    document.getElementById('nextStep1Btn')?.addEventListener('click', () => goToStep(2));
    document.getElementById('nextStep2Btn')?.addEventListener('click', () => goToStep(3));
    document.getElementById('prevStep2Btn')?.addEventListener('click', () => goToStep(1));
    document.getElementById('prevStep3Btn')?.addEventListener('click', () => goToStep(2));
    
    // Save mapping
    document.getElementById('saveMappingBtn')?.addEventListener('click', saveMapping);
    
    // Device filter
    document.getElementById('deviceFilter')?.addEventListener('change', filterMappingsByDevice);
    
    // Tag search
    document.getElementById('tagSearch')?.addEventListener('input', filterTags);
    document.getElementById('tagCategoryFilter')?.addEventListener('change', filterTags);
    document.getElementById('tagDeviceFilter')?.addEventListener('change', filterTags);
    
    // Poll interval custom input
    document.getElementById('mappingPollPreset')?.addEventListener('change', handlePollPresetChange);
    
    // Footer buttons
    document.getElementById('save-btn')?.addEventListener('click', saveConfiguration);
    document.getElementById('cancel-btn')?.addEventListener('click', cancelChanges);
    document.getElementById('testDeviceBtn')?.addEventListener('click', testSelectedDevice);
    document.getElementById('validateAllBtn')?.addEventListener('click', validateAllMappings);
}

// ============================================================================
// DATA LOADING
// ============================================================================

async function loadDevices() {
    try {
        const response = await fetch('/api/datapoints/devices');
        if (!response.ok) throw new Error('Failed to load devices');
        
        const data = await response.json();
        allDevices = data.devices || [];
        
        // Populate device filters
        populateDeviceFilters();
    } catch (error) {
        console.error('Error loading devices:', error);
        showNotification('Failed to load devices', 'error');
    }
}

async function loadTags() {
    try {
        const response = await fetch('/api/datapoints');
        if (!response.ok) throw new Error('Failed to load tags');
        
        const data = await response.json();
        allTags = data.tags || [];
        currentMappings = allTags;
        
        // Update UI
        updateMappingTable();
        updateTagsList();
        updateTagCount();
    } catch (error) {
        console.error('Error loading tags:', error);
        showNotification('Failed to load tags', 'error');
    }
}

// ============================================================================
// UI UPDATES
// ============================================================================

function updateMappingTable() {
    const tableBody = document.getElementById('mappingTableBody');
    if (!tableBody) return;
    
    tableBody.innerHTML = '';
    
    if (currentMappings.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center py-8 text-slate-500">
                    <i class="fa-solid fa-tags text-2xl mb-2 block"></i>
                    No tags found. Click "Add Mapping" to create your first tag.
                </td>
            </tr>
        `;
        return;
    }
    
    currentMappings.forEach(mapping => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-slate-50 transition-colors';
        
        // Protocol badge
        let protocolBadge = '';
        if (mapping.type === 'modbus') {
            const protocolType = mapping.device_type?.toLowerCase().includes('tcp') ? 'tcp' : 'rtu';
            protocolBadge = `<span class="protocol-badge modbus">Modbus ${protocolType.toUpperCase()}</span>`;
        } else if (mapping.type === 'loadcell') {
            protocolBadge = `<span class="protocol-badge serial">Loadcell</span>`;
        }
        
        // Data type badge
        const dataTypeBadge = mapping.data_type ? 
            `<span class="data-type-badge ${mapping.data_type.toLowerCase()}">${mapping.data_type.toUpperCase()}</span>` : 
            '<span class="text-slate-400 text-xs">-</span>';
        
        // Status indicator
        const statusIndicator = mapping.enabled ? 
            '<span class="status-indicator online">Online</span>' : 
            '<span class="status-indicator offline">Disabled</span>';
        
        // Actions
        const actions = `
            <div class="flex justify-end space-x-1">
                <button class="text-blue-600 hover:text-blue-800" onclick="editMapping('${mapping.id}', '${mapping.type}')">
                    <i class="fa-solid fa-pen text-xs"></i>
                </button>
                <button class="text-red-600 hover:text-red-800" onclick="deleteMapping('${mapping.id}', '${mapping.type}')">
                    <i class="fa-solid fa-trash text-xs"></i>
                </button>
            </div>
        `;
        
        row.innerHTML = `
            <td class="py-2">
                <div class="font-medium text-slate-900 text-xs">${mapping.device_name || 'Unknown'}</div>
                <div class="text-slate-500 text-xs">${mapping.device_id || ''}</div>
            </td>
            <td class="py-2">${protocolBadge}</td>
            <td class="py-2">
                ${mapping.register_address !== undefined ? `<code class="text-xs font-mono">${mapping.register_address}</code>` : '-'}
            </td>
            <td class="py-2">
                <div class="font-medium text-slate-900">${mapping.tag_name}</div>
                ${mapping.description ? `<div class="text-slate-500 text-xs truncate max-w-xs">${mapping.description}</div>` : ''}
            </td>
            <td class="py-2">${dataTypeBadge}</td>
            <td class="py-2">${mapping.unit || '-'}</td>
            <td class="py-2">${statusIndicator}</td>
            <td class="py-2">${actions}</td>
        `;
        
        tableBody.appendChild(row);
    });
}

function updateTagsList() {
    const tagsList = document.getElementById('tagsList');
    const emptyState = document.getElementById('tagsEmptyState');
    
    if (!tagsList) return;
    
    if (allTags.length === 0) {
        tagsList.innerHTML = '';
        if (emptyState) emptyState.classList.remove('hidden');
        return;
    }
    
    if (emptyState) emptyState.classList.add('hidden');
    tagsList.innerHTML = '';
    
    allTags.forEach(tag => {
        const tagCard = document.createElement('div');
        tagCard.className = 'tag-card';
        
        // Category color
        const categoryColors = {
            'Sensors': 'bg-blue-100 text-blue-800',
            'Motor': 'bg-green-100 text-green-800',
            'Safety': 'bg-red-100 text-red-800',
            'Diagnostic': 'bg-yellow-100 text-yellow-800',
            'Load Monitoring': 'bg-purple-100 text-purple-800',
            'Position Tracking': 'bg-indigo-100 text-indigo-800',
            'Status': 'bg-gray-100 text-gray-800',
            'Configuration': 'bg-orange-100 text-orange-800'
        };
        
        const categoryClass = categoryColors[tag.category] || 'bg-gray-100 text-gray-800';
        
        tagCard.innerHTML = `
            <div class="flex items-start justify-between mb-2">
                <div>
                    <h3 class="font-medium text-slate-900 text-sm">${tag.tag_name}</h3>
                    <div class="text-xs text-slate-500">${tag.device_name}</div>
                </div>
                <span class="text-xs px-2 py-0.5 rounded-full ${categoryClass}">${tag.category || 'Uncategorized'}</span>
            </div>
            
            <div class="mb-3">
                <div class="text-xs text-slate-600 mb-1">Address</div>
                <div class="font-mono text-xs bg-slate-50 p-1 rounded">
                    ${tag.register_address !== undefined ? `Reg ${tag.register_address}` : 'Auto-generated'}
                </div>
            </div>
            
            <div class="grid grid-cols-2 gap-2 text-xs">
                <div>
                    <div class="text-slate-600">Type</div>
                    <div class="font-medium">${tag.data_type || 'N/A'}</div>
                </div>
                <div>
                    <div class="text-slate-600">Unit</div>
                    <div class="font-medium">${tag.unit || '-'}</div>
                </div>
            </div>
            
            ${tag.description ? `
                <div class="mt-3 pt-2 border-t border-slate-200">
                    <div class="text-xs text-slate-500 italic">${tag.description}</div>
                </div>
            ` : ''}
        `;
        
        tagCard.addEventListener('click', () => {
            highlightMappingRow(tag.id);
        });
        
        tagsList.appendChild(tagCard);
    });
}

function updateTagCount() {
    const countElement = document.getElementById('mappingCount');
    if (countElement) {
        countElement.textContent = currentMappings.length;
    }
}

// ============================================================================
// FILTER FUNCTIONS
// ============================================================================

function filterMappingsByDevice() {
    const deviceFilter = document.getElementById('deviceFilter');
    const selectedDevice = deviceFilter.value;
    
    if (selectedDevice === 'All Devices') {
        currentMappings = allTags;
    } else {
        currentMappings = allTags.filter(tag => tag.device_name === selectedDevice);
    }
    
    updateMappingTable();
    updateTagCount();
}

function filterTags() {
    const searchTerm = document.getElementById('tagSearch').value.toLowerCase();
    const categoryFilter = document.getElementById('tagCategoryFilter').value;
    const deviceFilter = document.getElementById('tagDeviceFilter').value;
    
    let filteredTags = allTags;
    
    // Search by tag name or description
    if (searchTerm) {
        filteredTags = filteredTags.filter(tag => 
            tag.tag_name.toLowerCase().includes(searchTerm) ||
            (tag.description && tag.description.toLowerCase().includes(searchTerm))
        );
    }
    
    // Filter by category
    if (categoryFilter) {
        filteredTags = filteredTags.filter(tag => tag.category === categoryFilter);
    }
    
    // Filter by device
    if (deviceFilter) {
        filteredTags = filteredTags.filter(tag => tag.device_name === deviceFilter);
    }
    
    // Update UI
    allTags = filteredTags;
    updateTagsList();
}

// ============================================================================
// MODAL FUNCTIONS
// ============================================================================

function showAddMappingModal() {
    const modal = document.getElementById('editMappingModal');
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
        
        // Reset form
        resetMappingForm();
        goToStep(1);
        updateModalTitle('Add New Tag');
    }
}

function closeEditMappingModal() {
    const modal = document.getElementById('editMappingModal');
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

function goToStep(step) {
    currentStep = step;
    
    // Update step indicators
    for (let i = 1; i <= 3; i++) {
        const stepCircle = document.getElementById(`step${i}`);
        const stepContent = document.getElementById(`step${i}-content`);
        
        if (stepCircle) {
            stepCircle.className = i === step ? 'step-circle active' : 'step-circle inactive';
        }
        
        if (stepContent) {
            stepContent.className = i === step ? 'dynamic-section active' : 'dynamic-section';
        }
    }
}

function resetMappingForm() {
    // Reset all form fields
    document.getElementById('mappingTagName').value = '';
    document.getElementById('mappingRegisterAddress').value = '';
    document.getElementById('mappingDataType').value = 'int16';
    document.getElementById('mappingUnit').value = '';
    document.getElementById('mappingDescription').value = '';
    document.getElementById('mappingScale').value = '1';
    document.getElementById('mappingOffset').value = '0';
    document.getElementById('mappingPollPreset').value = '200';
    document.getElementById('mappingCategory').value = 'Sensors';
    
    // Clear device selection
    currentDevice = null;
    currentProtocol = '';
    
    // Update UI
    document.getElementById('mappingDeviceName').textContent = '-';
    document.getElementById('mappingProtocol').textContent = '-';
}

// ============================================================================
// DEVICE SELECTION
// ============================================================================

function selectDevice(deviceId) {
    const device = allDevices.find(d => d.id === deviceId);
    if (!device) return;
    
    currentDevice = device;
    currentProtocol = device.protocol;
    
    // Update UI
    document.getElementById('mappingDeviceName').textContent = device.name;
    document.getElementById('mappingProtocol').textContent = device.type;
    
    // Load protocol-specific form
    loadProtocolForm(device.protocol);
}

function loadProtocolForm(protocol) {
    const tabsContainer = document.getElementById('protocolTabsContainer');
    
    if (protocol.startsWith('modbus')) {
        tabsContainer.innerHTML = `
            <div class="flex space-x-1 border-b border-slate-200">
                <div class="tab active" data-tab="address">Address</div>
                <div class="tab" data-tab="polling">Polling</div>
                <div class="tab" data-tab="advanced">Advanced</div>
            </div>
        `;
        
        // Load modbus form
        loadModbusForm();
    } else if (protocol === 'loadcell') {
        tabsContainer.innerHTML = `
            <div class="text-sm text-slate-600 p-2">
                Loadcell tags are auto-created. Edit device settings to configure loadcell parameters.
            </div>
        `;
    }
}

function loadModbusForm() {
    const addressTypeContainer = document.getElementById('address-type-container');
    const addressValueContainer = document.getElementById('address-value-container');
    const protocolFields = document.getElementById('protocol-specific-fields');
    
    if (addressTypeContainer) {
        addressTypeContainer.innerHTML = `
            <div>
                <label class="block text-xs font-medium text-slate-700 mb-1">Register Type</label>
                <select class="w-full compact-select bg-white" id="mappingRegisterType">
                    <option value="holding">Holding Register</option>
                    <option value="input">Input Register</option>
                    <option value="coil">Coil</option>
                    <option value="discrete">Discrete Input</option>
                </select>
            </div>
        `;
    }
    
    if (addressValueContainer) {
        addressValueContainer.innerHTML = `
            <div>
                <label class="block text-xs font-medium text-slate-700 mb-1">Register Address *</label>
                <input type="number" class="w-full compact-input" placeholder="0-65535" id="mappingRegisterAddress" min="0" max="65535">
            </div>
        `;
    }
    
    if (protocolFields) {
        protocolFields.innerHTML = `
            <div class="grid grid-cols-2 gap-3">
                <div>
                    <label class="block text-xs font-medium text-slate-700 mb-1">Slave ID</label>
                    <input type="number" class="w-full compact-input" value="1" min="1" max="247" id="mappingSlaveId">
                </div>
                <div>
                    <label class="block text-xs font-medium text-slate-700 mb-1">Function Code</label>
                    <select class="w-full compact-select bg-white" id="mappingFunctionCode">
                        <option value="3">03 - Read Holding Registers</option>
                        <option value="4">04 - Read Input Registers</option>
                        <option value="1">01 - Read Coils</option>
                        <option value="2">02 - Read Discrete Inputs</option>
                        <option value="5">05 - Write Single Coil</option>
                        <option value="6">06 - Write Single Register</option>
                    </select>
                </div>
            </div>
        `;
    }
}

// ============================================================================
// SAVE/UPDATE FUNCTIONS
// ============================================================================

async function saveMapping() {
    try {
        const deviceId = currentDevice?.id;
        if (!deviceId) {
            showNotification('Please select a device first', 'warning');
            return;
        }
        
        const tagData = {
            device_id: deviceId,
            tag_name: document.getElementById('mappingTagName').value.trim(),
            register_address: parseInt(document.getElementById('mappingRegisterAddress').value) || 0,
            register_type: document.getElementById('mappingRegisterType')?.value || 'holding',
            data_type: document.getElementById('mappingDataType').value,
            byte_order: 'big', // Default for now
            word_order: 'big', // Default for now
            scale_factor: parseFloat(document.getElementById('mappingScale').value) || 1.0,
            offset: parseFloat(document.getElementById('mappingOffset').value) || 0.0,
            unit: document.getElementById('mappingUnit').value || '',
            description: document.getElementById('mappingDescription').value || '',
            enabled: true
        };
        
        // Validate required fields
        if (!tagData.tag_name) {
            showNotification('Tag name is required', 'warning');
            return;
        }
        
        if (tagData.register_address === undefined || tagData.register_address < 0) {
            showNotification('Valid register address is required', 'warning');
            return;
        }
        
        const response = await fetch('/api/datapoints/modbus', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(tagData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to save tag');
        }
        
        const result = await response.json();
        showNotification(result.message || 'Tag saved successfully', 'success');
        
        // Reload tags and close modal
        await loadTags();
        closeEditMappingModal();
        
    } catch (error) {
        console.error('Error saving tag:', error);
        showNotification(error.message || 'Failed to save tag', 'error');
    }
}

async function editMapping(tagId, tagType) {
    try {
        // For now, just show the edit modal
        // You would fetch the tag details here
        showNotification('Edit functionality coming soon', 'info');
    } catch (error) {
        console.error('Error editing tag:', error);
        showNotification('Failed to edit tag', 'error');
    }
}

async function deleteMapping(tagId, tagType) {
    if (!confirm('Are you sure you want to delete this tag?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/datapoints/${tagId}?type=${tagType}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to delete tag');
        }
        
        const result = await response.json();
        showNotification(result.message || 'Tag deleted successfully', 'success');
        
        // Reload tags
        await loadTags();
        
    } catch (error) {
        console.error('Error deleting tag:', error);
        showNotification(error.message || 'Failed to delete tag', 'error');
    }
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

function populateDeviceFilters() {
    const deviceFilter = document.getElementById('deviceFilter');
    const tagDeviceFilter = document.getElementById('tagDeviceFilter');
    
    if (deviceFilter) {
        deviceFilter.innerHTML = '<option>All Devices</option>';
        allDevices.forEach(device => {
            const option = document.createElement('option');
            option.value = device.name;
            option.textContent = `${device.name} (${device.type})`;
            deviceFilter.appendChild(option);
        });
    }
    
    if (tagDeviceFilter) {
        tagDeviceFilter.innerHTML = '<option value="">All Devices</option>';
        allDevices.forEach(device => {
            const option = document.createElement('option');
            option.value = device.name;
            option.textContent = device.name;
            tagDeviceFilter.appendChild(option);
        });
    }
}

function highlightMappingRow(tagId) {
    // Remove highlight from all rows
    document.querySelectorAll('#mappingTableBody tr').forEach(row => {
        row.classList.remove('selected-device-row');
    });
    
    // Find and highlight the row
    const rows = document.querySelectorAll('#mappingTableBody tr');
    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        // This is a simplified approach - you'd need to match the tag ID
        if (row.textContent.includes(tagId.toString())) {
            row.classList.add('selected-device-row');
            row.scrollIntoView({ behavior: 'smooth', block: 'center' });
            break;
        }
    }
}

function handlePollPresetChange() {
    const preset = document.getElementById('mappingPollPreset');
    const customInput = document.getElementById('mappingPollInterval');
    
    if (preset.value === 'custom') {
        customInput.style.display = 'block';
        customInput.value = '';
        customInput.focus();
    } else {
        customInput.style.display = 'none';
    }
}

function updateModalTitle(title) {
    const titleElement = document.getElementById('modalTitle');
    if (titleElement) {
        titleElement.textContent = title;
    }
}

function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    const chevron = document.getElementById(sectionId.replace('section', 'chevron'));
    
    if (section && chevron) {
        const isHidden = section.classList.contains('hidden');
        section.classList.toggle('hidden');
        chevron.className = isHidden ? 
            'fa-solid fa-chevron-up text-xs text-slate-400' : 
            'fa-solid fa-chevron-down text-xs text-slate-400';
    }
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function showNotification(message, type = 'info') {
    // You can implement your notification system here
    console.log(`${type.toUpperCase()}: ${message}`);
    alert(`${type.toUpperCase()}: ${message}`); // Simple alert for now
}

async function saveConfiguration() {
    showNotification('Configuration saved successfully!', 'success');
    // Implement actual save logic here
}

function cancelChanges() {
    if (confirm('Are you sure you want to cancel? All unsaved changes will be lost.')) {
        location.reload(); // Reload the page
    }
}

async function testSelectedDevice() {
    showNotification('Testing device connection...', 'info');
    // Implement device testing logic here
}

async function validateAllMappings() {
    showNotification('Validating all mappings...', 'info');
    // Implement validation logic here
}

function importCSV() {
    showNotification('Import CSV functionality coming soon', 'info');
}

function exportCSV() {
    showNotification('Export CSV functionality coming soon', 'info');
}

// ============================================================================
// INITIALIZE WHEN PAGE LOADS
// ============================================================================

// Expose function globally for router
window.initializeModbusMapping = initializeModbusMapping;

// Auto-initialize if script is loaded directly
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeModbusMapping);
} else {
    initializeModbusMapping();
}