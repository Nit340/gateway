// modbus-mapping.js - Fixed with proper device loading and click handling
let devices = [];
let tags = [];
let selectedDeviceId = null;
let selectedDeviceData = null;

// ==================== INITIALIZATION ====================

function initializeModbusMapping() {
    console.log('🚀 Initializing Tag Mapping...');
    
    // Check if modal exists, if not create it
    ensureModalExists();
    
    // Load data first
    loadDevicesAndTags();
    
    // Setup event listeners
    setupEventListeners();
    
    console.log('✅ Tag Mapping initialized');
}

function ensureModalExists() {
    let modal = document.getElementById('createTagModal');
    
    if (!modal) {
        console.log('Modal not found, creating it...');
        createModalHTML();
        modal = document.getElementById('createTagModal');
    }
    
    return modal;
}

function createModalHTML() {
    // Remove any existing modal
    const existingModal = document.getElementById('createTagModal');
    if (existingModal) existingModal.remove();
    
    const modalHTML = `
    <div class="modal-overlay" id="createTagModal" style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 9999; align-items: center; justify-content: center;">
        <div class="modal" style="background: white; border-radius: 8px; width: 90%; max-width: 500px; max-height: 90vh; overflow-y: auto;">
            <div class="p-6">
                <!-- Modal Header -->
                <div class="flex items-center justify-between mb-6">
                    <h2 class="text-lg font-semibold text-gray-900">
                        <i class="fa-solid fa-plus mr-2 text-blue-600"></i>
                        Create New Tag
                    </h2>
                    <button class="text-gray-400 hover:text-gray-600" id="closeCreateTagModal">
                        <i class="fa-solid fa-xmark text-lg"></i>
                    </button>
                </div>
                
                <!-- Step 1: Device Selection -->
                <div class="modal-step active" id="deviceSelectionStep">
                    <div class="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200 text-sm text-blue-800">
                        <i class="fa-solid fa-info-circle mr-2"></i>
                        First, select the device you want to create a tag for
                    </div>
                    
                    <div class="mb-5">
                        <label class="block text-sm font-medium text-gray-700 mb-2">
                            Select Device <span class="text-red-500">*</span>
                        </label>
                        <select class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white text-sm" id="modalDeviceSelect">
                            <option value="">-- Choose a device --</option>
                            <!-- Devices will be populated -->
                        </select>
                    </div>
                    
                    <!-- Device Info (shown when device selected) -->
                    <div class="hidden mb-5 p-4 bg-gray-50 rounded-lg border border-gray-200" id="modalDeviceInfo">
                        <div class="grid grid-cols-2 gap-4 text-sm">
                            <div>
                                <div class="text-xs text-gray-500 mb-1">Device Type</div>
                                <div class="font-medium text-gray-900" id="modalDeviceType">-</div>
                            </div>
                            <div>
                                <div class="text-xs text-gray-500 mb-1">Protocol</div>
                                <div class="font-medium text-gray-900" id="modalDeviceProtocol">-</div>
                            </div>
                        </div>
                        <div class="mt-3 text-xs text-gray-600" id="modalDeviceHint"></div>
                    </div>
                    
                    <!-- Footer -->
                    <div class="flex justify-end space-x-2 pt-4 border-t border-gray-200">
                        <button type="button" class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50" id="cancelDeviceSelection">
                            Cancel
                        </button>
                        <button type="button" class="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed" id="proceedToForm" disabled>
                            Next: Configure Tag <i class="fa-solid fa-arrow-right ml-1"></i>
                        </button>
                    </div>
                </div>
                
                <!-- Step 2a: Load Cell Form -->
                <div class="modal-step" id="loadcellFormStep" style="display: none;">
                    <!-- Load cell form content -->
                    <div class="mb-4 p-3 bg-green-50 rounded-lg border border-green-200">
                        <div class="text-xs text-green-700 mb-1">Selected Device</div>
                        <div class="text-sm font-medium text-green-900" id="loadcellFormDeviceName">-</div>
                    </div>
                    
                    <div class="mb-6 p-3 bg-blue-50 rounded-lg border border-blue-200 text-sm text-blue-800">
                        <i class="fa-solid fa-info-circle mr-2"></i>
                        Load cell tags are auto-created when device is added. These values cannot be edited.
                    </div>
                    
                    <div class="flex justify-between space-x-2 pt-4 border-t border-gray-200">
                        <button type="button" class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50" id="backFromLoadcell">
                            <i class="fa-solid fa-arrow-left mr-1"></i> Back
                        </button>
                        <button type="button" class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50" id="closeFromLoadcell">
                            Close
                        </button>
                    </div>
                </div>
                
                <!-- Step 2b: Modbus Form -->
                <div class="modal-step" id="modbusFormStep" style="display: none;">
                    <!-- Modbus form content -->
                    <div class="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
                        <div class="grid grid-cols-2 gap-3">
                            <div>
                                <div class="text-xs text-blue-700 mb-1">Selected Device</div>
                                <div class="text-sm font-medium text-blue-900" id="modbusFormDeviceName">-</div>
                            </div>
                            <div>
                                <div class="text-xs text-blue-700 mb-1">Protocol</div>
                                <div class="text-sm font-medium text-blue-900" id="modbusFormProtocol">-</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="mb-6 p-3 bg-amber-50 rounded-lg border border-amber-200 text-sm text-amber-800">
                        <i class="fa-solid fa-lightbulb mr-2"></i>
                        <strong>Auto-Detection:</strong> Register type will be detected from the address you enter
                    </div>
                    
                    <form id="modbusCreateForm">
                        <!-- Form fields -->
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                Tag Name <span class="text-red-500">*</span>
                            </label>
                            <input type="text" class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" 
                                   id="modbusFormTagName" placeholder="e.g., temperature_sensor_1" required>
                        </div>
                        
                        <div class="flex justify-between space-x-2 pt-4 border-t border-gray-200">
                            <button type="button" class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50" id="backFromModbus">
                                <i class="fa-solid fa-arrow-left mr-1"></i> Back
                            </button>
                            <div class="flex space-x-2">
                                <button type="button" class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50" id="cancelFromModbus">
                                    Cancel
                                </button>
                                <button type="submit" class="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-lg hover:bg-blue-700">
                                    <i class="fa-solid fa-check mr-2"></i> Create Tag
                                </button>
                            </div>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    console.log('✅ Modal HTML created');
}

// ==================== LOAD DATA ====================

async function loadDevicesAndTags() {
    try {
        console.log('📥 Loading devices and tags...');
        
        // Load devices
        const devicesResponse = await fetch('/api/datapoints/devices');
        const devicesData = await devicesResponse.json();
        devices = devicesData.devices || [];
        console.log(`Loaded ${devices.length} devices`);
        
        // Load tags
        const tagsResponse = await fetch('/api/datapoints');
        const tagsData = await tagsResponse.json();
        tags = tagsData.tags || [];
        console.log(`Loaded ${tags.length} tags`);
        
        // Populate device select dropdown
        populateDeviceSelectDropdown();
        
        // Render tables
        renderTagsTable();
        renderTagsBrowser();
        updateTagCount();
        
    } catch (error) {
        console.error('Error loading data:', error);
        showTagNotification('Failed to load data', 'error');
    }
}

function populateDeviceSelectDropdown() {
    const select = document.getElementById('modalDeviceSelect');
    if (!select) {
        console.error('Device select dropdown not found');
        return;
    }
    
    // Clear and add options
    select.innerHTML = '<option value="">-- Choose a device --</option>';
    
    devices.forEach(device => {
        const option = document.createElement('option');
        option.value = device.id;
        option.textContent = `${device.name} (${device.type})`;
        option.dataset.protocol = device.protocol;
        select.appendChild(option);
    });
    
    console.log(`Populated dropdown with ${devices.length} devices`);
}

// ==================== EVENT LISTENERS ====================

function setupEventListeners() {
    console.log('🔧 Setting up event listeners...');
    
    // 1. Add Mapping button
    const addMappingBtn = document.getElementById('addMappingBtn');
    if (addMappingBtn) {
        console.log('Found Add Mapping button');
        
        // Remove existing listeners and reattach
        const newBtn = addMappingBtn.cloneNode(true);
        addMappingBtn.parentNode.replaceChild(newBtn, addMappingBtn);
        
        newBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('Add Mapping button clicked');
            openCreateTagModal();
        });
    }
    
    // 2. Modal close buttons
    document.getElementById('closeCreateTagModal')?.addEventListener('click', closeModal);
    document.getElementById('cancelDeviceSelection')?.addEventListener('click', closeModal);
    document.getElementById('closeFromLoadcell')?.addEventListener('click', closeModal);
    document.getElementById('cancelFromModbus')?.addEventListener('click', closeModal);
    
    // 3. Device selection
    const deviceSelect = document.getElementById('modalDeviceSelect');
    if (deviceSelect) {
        deviceSelect.addEventListener('change', function(e) {
            console.log('Device selection changed:', e.target.value);
            handleDeviceSelection(e);
        });
    }
    
    // 4. Proceed button
    const proceedBtn = document.getElementById('proceedToForm');
    if (proceedBtn) {
        proceedBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Proceed button clicked');
            proceedToDeviceForm();
        });
    }
    
    // 5. Back buttons
    document.getElementById('backFromLoadcell')?.addEventListener('click', backToDeviceSelection);
    document.getElementById('backFromModbus')?.addEventListener('click', backToDeviceSelection);
    
    // 6. Modbus form submission
    const modbusForm = document.getElementById('modbusCreateForm');
    if (modbusForm) {
        modbusForm.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('Modbus form submitted');
            handleModbusTagCreate(e);
        });
    }
    
    // 7. Modal overlay click to close
    const modal = document.getElementById('createTagModal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                closeModal();
            }
        });
    }
    
    // 8. Escape key to close
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const modal = document.getElementById('createTagModal');
            if (modal && modal.style.display === 'flex') {
                closeModal();
            }
        }
    });
    
    console.log('✅ Event listeners setup complete');
}

// ==================== MODAL FUNCTIONS ====================

function openCreateTagModal() {
    console.log('🎯 Opening create tag modal...');
    
    const modal = ensureModalExists();
    
    if (!modal) {
        console.error('Cannot open modal - not found');
        showTagNotification('Cannot open modal', 'error');
        return;
    }
    
    // Reset state
    selectedDeviceId = null;
    selectedDeviceData = null;
    
    // Reset UI
    document.getElementById('modalDeviceSelect').value = '';
    document.getElementById('modalDeviceInfo').classList.add('hidden');
    document.getElementById('proceedToForm').disabled = true;
    
    // Show first step
    showModalStep('deviceSelectionStep');
    
    // Display modal
    modal.style.display = 'flex';
    setTimeout(() => {
        modal.style.opacity = '1';
    }, 10);
    
    // Prevent body scroll
    document.body.style.overflow = 'hidden';
    
    console.log('✅ Modal opened');
}

function closeModal() {
    console.log('Closing modal...');
    
    const modal = document.getElementById('createTagModal');
    if (modal) {
        modal.style.opacity = '0';
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
    }
    
    // Restore body scroll
    document.body.style.overflow = '';
    
    console.log('✅ Modal closed');
}

function showModalStep(stepId) {
    console.log(`Showing step: ${stepId}`);
    
    // Hide all steps
    const steps = document.querySelectorAll('.modal-step');
    steps.forEach(step => {
        step.style.display = 'none';
        step.classList.remove('active');
    });
    
    // Show the requested step
    const step = document.getElementById(stepId);
    if (step) {
        step.style.display = 'block';
        step.classList.add('active');
    }
}

function handleDeviceSelection(event) {
    const deviceId = event.target.value;
    const deviceInfo = document.getElementById('modalDeviceInfo');
    const proceedBtn = document.getElementById('proceedToForm');
    
    console.log(`Device selected: ${deviceId}`);
    
    if (!deviceId) {
        selectedDeviceId = null;
        selectedDeviceData = null;
        deviceInfo?.classList.add('hidden');
        proceedBtn.disabled = true;
        return;
    }
    
    // Find device
    const device = devices.find(d => d.id == deviceId);
    if (!device) {
        console.error(`Device ${deviceId} not found`);
        return;
    }
    
    selectedDeviceId = deviceId;
    selectedDeviceData = device;
    
    // Update device info display
    if (deviceInfo) {
        document.getElementById('modalDeviceType').textContent = device.type;
        document.getElementById('modalDeviceProtocol').textContent = device.protocol.toUpperCase();
        
        // Set hint
        const hint = document.getElementById('modalDeviceHint');
        if (device.protocol === 'loadcell') {
            hint.innerHTML = '<i class="fa-solid fa-scale-balanced mr-1 text-green-600"></i> Load cell tags are auto-created. You can view the configuration.';
        } else {
            hint.innerHTML = '<i class="fa-solid fa-microchip mr-1 text-blue-600"></i> Configure Modbus register address and data type.';
        }
        
        deviceInfo.classList.remove('hidden');
    }
    
    // Enable proceed button
    if (proceedBtn) {
        proceedBtn.disabled = false;
    }
    
    console.log(`Device selected: ${device.name} (${device.protocol})`);
}

function proceedToDeviceForm() {
    console.log('Proceeding to device form...');
    
    if (!selectedDeviceData) {
        showTagNotification('Please select a device first', 'error');
        return;
    }
    
    console.log(`Selected protocol: ${selectedDeviceData.protocol}`);
    
    if (selectedDeviceData.protocol === 'loadcell') {
        showLoadcellForm();
    } else if (selectedDeviceData.protocol === 'modbus-tcp' || selectedDeviceData.protocol === 'modbus-rtu') {
        showModbusForm();
    } else {
        showTagNotification('Unknown device protocol', 'error');
    }
}

function backToDeviceSelection() {
    console.log('Going back to device selection');
    showModalStep('deviceSelectionStep');
}

function showLoadcellForm() {
    console.log('Showing loadcell form');
    
    // Update device name
    const deviceNameEl = document.getElementById('loadcellFormDeviceName');
    if (deviceNameEl) {
        deviceNameEl.textContent = selectedDeviceData.name;
    }
    
    // Show the form
    showModalStep('loadcellFormStep');
}

function showModbusForm() {
    console.log('Showing modbus form');
    
    // Update device info
    const deviceNameEl = document.getElementById('modbusFormDeviceName');
    const protocolEl = document.getElementById('modbusFormProtocol');
    
    if (deviceNameEl) deviceNameEl.textContent = selectedDeviceData.name;
    if (protocolEl) protocolEl.textContent = selectedDeviceData.protocol.toUpperCase();
    
    // Reset form
    const form = document.getElementById('modbusCreateForm');
    if (form) form.reset();
    
    // Show the form
    showModalStep('modbusFormStep');
}

// ==================== FORM HANDLING ====================

async function handleModbusTagCreate(event) {
    event.preventDefault();
    console.log('Handling modbus tag creation...');
    
    // Get form values
    const tagName = document.getElementById('modbusFormTagName')?.value;
    const registerAddress = document.getElementById('modbusFormAddress')?.value;
    
    if (!tagName || !registerAddress) {
        showTagNotification('Please fill all required fields', 'error');
        return;
    }
    
    const tagData = {
        device_id: selectedDeviceId,
        tag_name: tagName,
        register_address: parseInt(registerAddress),
        register_type: 'holding', // Default
        data_type: 'int16',
        byte_order: 'big',
        word_order: 'big',
        scale_factor: 1.0,
        offset: 0.0,
        unit: '',
        description: '',
        enabled: true
    };
    
    console.log('Creating tag:', tagData);
    
    try {
        const response = await fetch('/api/datapoints/modbus', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(tagData)
        });
        
        if (response.ok) {
            showTagNotification('Tag created successfully', 'success');
            closeModal();
            // Reload tags
            loadDevicesAndTags();
        } else {
            const error = await response.json();
            showTagNotification(error.error || 'Failed to create tag', 'error');
        }
    } catch (error) {
        console.error('Error creating tag:', error);
        showTagNotification('Failed to create tag', 'error');
    }
}

// ==================== RENDER FUNCTIONS ====================

function renderTagsTable() {
    const tbody = document.getElementById('mappingTableBody');
    if (!tbody) return;
    
    if (tags.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center py-8 text-gray-500">
                    <i class="fa-solid fa-tags text-4xl mb-3 text-gray-300"></i>
                    <p class="text-sm">No tags configured. Click "Add Mapping" to create your first tag.</p>
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = '';
    tags.forEach(tag => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="font-medium text-gray-900">${tag.device_name || 'Unknown'}</td>
            <td>
                <span class="px-2 py-0.5 rounded-full text-xs font-medium ${tag.type === 'loadcell' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'}">
                    ${tag.device_type || 'Unknown'}
                </span>
            </td>
            <td class="text-gray-600">${tag.register_address || '-'}</td>
            <td class="font-mono text-sm text-gray-900">${tag.tag_name}</td>
            <td class="text-gray-600">${tag.data_type || '-'}</td>
            <td class="text-gray-600">${tag.unit || '-'}</td>
            <td>
                <span class="px-2 py-0.5 rounded-full text-xs font-medium ${tag.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}">
                    ${tag.enabled ? 'Enabled' : 'Disabled'}
                </span>
            </td>
            <td class="text-right">
                <button class="text-blue-600 hover:text-blue-800 mr-2" onclick="editTag(${tag.id}, '${tag.type}')" title="Edit">
                    <i class="fa-solid fa-pencil text-sm"></i>
                </button>
                <button class="text-red-600 hover:text-red-800" onclick="deleteTag(${tag.id}, '${tag.type}')" title="Delete">
                    <i class="fa-solid fa-trash text-sm"></i>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function renderTagsBrowser() {
    const container = document.getElementById('tagsList');
    if (!container) return;
    
    // Similar to renderTagsTable but for the grid view
}

function updateTagCount() {
    const countEl = document.getElementById('mappingCount');
    if (countEl) {
        countEl.textContent = tags.length;
    }
}

// ==================== NOTIFICATIONS ====================

function showTagNotification(message, type = 'info') {
    console.log(`Notification (${type}): ${message}`);
    
    // Simple alert for now - you can replace with your notification system
    alert(`${type.toUpperCase()}: ${message}`);
}

// ==================== TAG ACTIONS ====================

function editTag(tagId, tagType) {
    console.log(`Edit tag ${tagId} (${tagType})`);
    showTagNotification('Edit functionality coming soon', 'info');
}

async function deleteTag(tagId, tagType) {
    if (!confirm('Are you sure you want to delete this tag?')) return;
    
    console.log(`Delete tag ${tagId} (${tagType})`);
    showTagNotification('Delete functionality coming soon', 'info');
}

// ==================== EXPORT FUNCTIONS ====================

window.initializeModbusMapping = initializeModbusMapping;
window.editTag = editTag;
window.deleteTag = deleteTag;
window.importCSV = function() { showTagNotification('CSV import coming soon', 'info'); };
window.exportCSV = function() { showTagNotification('CSV export coming soon', 'info'); };
window.openCreateTagModal = openCreateTagModal; // For debugging