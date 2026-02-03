// modbus-mapping.js - Updated for new backend API
// Supports: Modbus TCP, Modbus RTU datapoints (Loadcell datapoints are auto-created)

window.initializeModbusMapping = function() {
    console.log('Modbus Mapping page initialized');
    
    // Page state
    let devices = [];
    let mappings = [];
    let selectedDeviceId = null;
    let selectedMappingId = null;
    let currentProtocol = 'modbus-tcp';

    // API endpoints
    const API_BASE = '/api/datapoints';

    // Notification system
    function showTagNotification(message, type = 'info', duration = 3000) {
        const existingNotification = document.getElementById('tag-mapping-notification');
        if (existingNotification) {
            existingNotification.remove();
        }
        
        const notification = document.createElement('div');
        notification.id = 'tag-mapping-notification';
        notification.className = 'fixed top-4 right-4 z-50 max-w-sm';
        
        let bgColor = 'bg-blue-500';
        let textColor = 'text-white';
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
            <div class="rounded-lg shadow-lg ${bgColor} ${textColor} p-4 flex items-start justify-between animate-fade-in">
                <div class="flex items-center">
                    <i class="fa-solid ${icon} mr-3"></i>
                    <div class="text-sm font-medium">${message}</div>
                </div>
                <button class="ml-4 text-white hover:text-gray-200 focus:outline-none" onclick="document.getElementById('tag-mapping-notification').remove()">
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

    // Generate unique tag name suggestions
    function generateTagNameSuggestion(baseName, deviceId) {
        if (!baseName || !deviceId) return baseName;
        
        const existingTagNames = mappings
            .filter(m => m.device_id === deviceId)
            .filter(m => m.id !== selectedMappingId)
            .map(m => m.tag_name.toLowerCase());
        
        const baseLower = baseName.toLowerCase();
        if (!existingTagNames.includes(baseLower)) {
            return baseName;
        }
        
        let counter = 1;
        let newName = baseName + '_' + counter;
        
        while (existingTagNames.includes(newName.toLowerCase())) {
            counter++;
            newName = baseName + '_' + counter;
        }
        
        return newName;
    }

    // Initialize the page
    async function init() {
        try {
            await loadDevices();
            await loadMappings();
            renderDeviceSelect();
            renderMappingsTable();
            setupEventListeners();
            updateStats();
            
            showTagNotification('Page loaded successfully', 'success');
        } catch (error) {
            console.error('Initialization error:', error);
            showTagNotification('Failed to initialize page: ' + error.message, 'error');
        }
    }

    // Load devices from API
    async function loadDevices() {
        try {
            const response = await fetch(`${API_BASE}/devices`);
            if (!response.ok) throw new Error('Failed to load devices');
            
            const data = await response.json();
            devices = data.devices || [];
            
            console.log('Loaded devices:', devices);
        } catch (error) {
            console.error('Error loading devices:', error);
            throw error;
        }
    }

    // Load datapoints/mappings from API
    async function loadMappings() {
        try {
            const response = await fetch(API_BASE);
            if (!response.ok) throw new Error('Failed to load datapoints');
            
            const data = await response.json();
            mappings = data.datapoints || [];
            
            console.log('Loaded datapoints:', mappings);
        } catch (error) {
            console.error('Error loading datapoints:', error);
            throw error;
        }
    }

    // Render device selector
    function renderDeviceSelect() {
        const deviceSelect = document.getElementById('deviceSelect');
        if (!deviceSelect) return;
        
        deviceSelect.innerHTML = '<option value="">All Devices</option>';
        
        // Filter only Modbus devices (no loadcell)
        const modbusDevices = devices.filter(d => 
            d.protocol === 'modbus-tcp' || d.protocol === 'modbus-rtu'
        );
        
        modbusDevices.forEach(device => {
            const option = document.createElement('option');
            option.value = device.id;
            option.textContent = `${device.name} (${device.type})`;
            deviceSelect.appendChild(option);
        });
    }

    // Render mappings table
    function renderMappingsTable() {
        const tbody = document.getElementById('mappingsTableBody');
        if (!tbody) return;
        
        // Filter mappings
        let filteredMappings = mappings;
        
        // Filter by selected device
        const deviceSelect = document.getElementById('deviceSelect');
        if (deviceSelect && deviceSelect.value) {
            filteredMappings = filteredMappings.filter(m => m.device_id === deviceSelect.value);
        }
        
        // Filter by search
        const searchInput = document.getElementById('searchInput');
        if (searchInput && searchInput.value) {
            const searchTerm = searchInput.value.toLowerCase();
            filteredMappings = filteredMappings.filter(m =>
                m.tag_name.toLowerCase().includes(searchTerm) ||
                m.device_name.toLowerCase().includes(searchTerm)
            );
        }
        
        // Filter only Modbus datapoints (exclude loadcell)
        filteredMappings = filteredMappings.filter(m => 
            m.device_type && (m.device_type.includes('Modbus') || m.device_type.includes('TCP') || m.device_type.includes('RTU'))
        );
        
        if (filteredMappings.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center py-8 text-slate-500">No datapoints found. Add a datapoint to get started.</td></tr>';
            return;
        }
        
        tbody.innerHTML = '';
        
        filteredMappings.forEach(mapping => {
            const row = document.createElement('tr');
            row.className = 'border-b border-slate-200 hover:bg-slate-50';
            row.innerHTML = `
                <td class="px-4 py-3 text-sm text-slate-900">${mapping.tag_name}</td>
                <td class="px-4 py-3 text-sm text-slate-600">${mapping.device_name}</td>
                <td class="px-4 py-3 text-sm text-slate-600">${mapping.device_type}</td>
                <td class="px-4 py-3 text-sm text-slate-600">${mapping.register_address || '-'}</td>
                <td class="px-4 py-3 text-sm text-slate-600">${mapping.register_type || '-'}</td>
                <td class="px-4 py-3 text-sm text-slate-600">${mapping.data_type || '-'}</td>
                <td class="px-4 py-3 text-sm text-slate-600">${mapping.unit || '-'}</td>
                <td class="px-4 py-3">
                    <div class="flex gap-2">
                        <button class="text-blue-600 hover:text-blue-800" onclick="window.modbusMapping.editMapping(${mapping.id})" title="Edit">
                            <i class="fa-solid fa-edit"></i>
                        </button>
                        <button class="text-red-600 hover:text-red-800" onclick="window.modbusMapping.deleteMapping(${mapping.id})" title="Delete">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </div>
                </td>
            `;
            tbody.appendChild(row);
        });
    }

    // Update statistics
    function updateStats() {
        const totalMappings = mappings.filter(m => 
            m.device_type && (m.device_type.includes('Modbus') || m.device_type.includes('TCP') || m.device_type.includes('RTU'))
        ).length;
        
        const totalDevices = devices.filter(d => 
            d.protocol === 'modbus-tcp' || d.protocol === 'modbus-rtu'
        ).length;
        
        const totalMappingsEl = document.getElementById('totalMappings');
        const totalDevicesEl = document.getElementById('totalDevices');
        
        if (totalMappingsEl) totalMappingsEl.textContent = totalMappings;
        if (totalDevicesEl) totalDevicesEl.textContent = totalDevices;
    }

    // Setup event listeners
    function setupEventListeners() {
        const addMappingBtn = document.getElementById('addMappingBtn');
        if (addMappingBtn) {
            addMappingBtn.addEventListener('click', openAddMappingModal);
        }
        
        const deviceSelect = document.getElementById('deviceSelect');
        if (deviceSelect) {
            deviceSelect.addEventListener('change', renderMappingsTable);
        }
        
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', renderMappingsTable);
        }
        
        const saveMappingBtn = document.getElementById('saveMappingBtn');
        if (saveMappingBtn) {
            saveMappingBtn.addEventListener('click', saveMapping);
        }
        
        const closeMappingModalBtn = document.getElementById('closeMappingModalBtn');
        if (closeMappingModalBtn) {
            closeMappingModalBtn.addEventListener('click', closeMappingModal);
        }
        
        // Device selector in modal
        const mappingDeviceSelect = document.getElementById('mappingDeviceSelect');
        if (mappingDeviceSelect) {
            mappingDeviceSelect.addEventListener('change', onDeviceSelectChange);
        }
    }

    // Open add mapping modal
    function openAddMappingModal() {
        selectedMappingId = null;
        
        const modal = document.getElementById('addMappingModal');
        if (!modal) return;
        
        // Reset form
        const form = document.getElementById('mappingForm');
        if (form) form.reset();
        
        // Populate device selector
        const mappingDeviceSelect = document.getElementById('mappingDeviceSelect');
        if (mappingDeviceSelect) {
            mappingDeviceSelect.innerHTML = '<option value="">Select Device</option>';
            
            const modbusDevices = devices.filter(d => 
                d.protocol === 'modbus-tcp' || d.protocol === 'modbus-rtu'
            );
            
            modbusDevices.forEach(device => {
                const option = document.createElement('option');
                option.value = device.id;
                option.textContent = `${device.name} (${device.type})`;
                option.dataset.protocol = device.protocol;
                mappingDeviceSelect.appendChild(option);
            });
        }
        
        // Update modal title
        const modalTitle = document.getElementById('mappingModalTitle');
        if (modalTitle) {
            modalTitle.textContent = 'Add Modbus Datapoint';
        }
        
        // Show protocol-specific fields
        const protocolFields = document.getElementById('protocolFields');
        if (protocolFields) {
            protocolFields.style.display = 'none';
        }
        
        modal.classList.add('active');
    }

    // Close mapping modal
    function closeMappingModal() {
        const modal = document.getElementById('addMappingModal');
        if (modal) {
            modal.classList.remove('active');
        }
        selectedMappingId = null;
    }

    // On device select change in modal
    function onDeviceSelectChange(event) {
        const deviceId = event.target.value;
        const selectedOption = event.target.options[event.target.selectedIndex];
        const protocol = selectedOption.dataset.protocol;
        
        selectedDeviceId = deviceId;
        currentProtocol = protocol;
        
        const protocolFields = document.getElementById('protocolFields');
        if (!protocolFields) return;
        
        if (deviceId) {
            protocolFields.style.display = 'block';
            
            // Show info message
            const protocolInfo = document.getElementById('protocolInfo');
            if (protocolInfo) {
                if (protocol === 'modbus-tcp') {
                    protocolInfo.textContent = 'Configuring Modbus TCP datapoint';
                } else if (protocol === 'modbus-rtu') {
                    protocolInfo.textContent = 'Configuring Modbus RTU datapoint';
                }
            }
        } else {
            protocolFields.style.display = 'none';
        }
    }

    // Edit mapping
    async function editMapping(mappingId) {
        try {
            const mapping = mappings.find(m => m.id === mappingId);
            if (!mapping) {
                showTagNotification('Datapoint not found', 'error');
                return;
            }
            
            selectedMappingId = mappingId;
            
            const modal = document.getElementById('addMappingModal');
            if (!modal) return;
            
            // Update modal title
            const modalTitle = document.getElementById('mappingModalTitle');
            if (modalTitle) {
                modalTitle.textContent = 'Edit Modbus Datapoint';
            }
            
            // Populate device selector
            const mappingDeviceSelect = document.getElementById('mappingDeviceSelect');
            if (mappingDeviceSelect) {
                mappingDeviceSelect.innerHTML = '<option value="">Select Device</option>';
                
                const modbusDevices = devices.filter(d => 
                    d.protocol === 'modbus-tcp' || d.protocol === 'modbus-rtu'
                );
                
                modbusDevices.forEach(device => {
                    const option = document.createElement('option');
                    option.value = device.id;
                    option.textContent = `${device.name} (${device.type})`;
                    option.dataset.protocol = device.protocol;
                    if (device.id === mapping.device_id) {
                        option.selected = true;
                    }
                    mappingDeviceSelect.appendChild(option);
                });
                
                // Trigger change event to show fields
                mappingDeviceSelect.dispatchEvent(new Event('change'));
            }
            
            // Populate form fields
            document.getElementById('tagName').value = mapping.tag_name || '';
            document.getElementById('registerAddress').value = mapping.register_address || '';
            document.getElementById('registerType').value = mapping.register_type || 'holding';
            document.getElementById('dataType').value = mapping.data_type || 'int16';
            document.getElementById('byteOrder').value = mapping.byte_order || 'big';
            document.getElementById('wordOrder').value = mapping.word_order || 'big';
            document.getElementById('scaleFactor').value = mapping.scale_factor || 1.0;
            document.getElementById('offset').value = mapping.offset || 0.0;
            document.getElementById('unit').value = mapping.unit || '';
            document.getElementById('description').value = mapping.description || '';
            
            modal.classList.add('active');
            
        } catch (error) {
            console.error('Error editing mapping:', error);
            showTagNotification('Failed to load datapoint: ' + error.message, 'error');
        }
    }

    // Save mapping
    async function saveMapping() {
        try {
            const deviceId = document.getElementById('mappingDeviceSelect').value;
            if (!deviceId) {
                showTagNotification('Please select a device', 'error');
                return;
            }
            
            const tagName = document.getElementById('tagName').value;
            if (!tagName) {
                showTagNotification('Please enter a tag name', 'error');
                return;
            }
            
            const registerAddress = parseInt(document.getElementById('registerAddress').value);
            if (isNaN(registerAddress)) {
                showTagNotification('Please enter a valid register address', 'error');
                return;
            }
            
            const mappingData = {
                device_id: deviceId,
                tag_name: tagName,
                register_address: registerAddress,
                register_type: document.getElementById('registerType').value || 'holding',
                data_type: document.getElementById('dataType').value || 'int16',
                byte_order: document.getElementById('byteOrder').value || 'big',
                word_order: document.getElementById('wordOrder').value || 'big',
                scale_factor: parseFloat(document.getElementById('scaleFactor').value) || 1.0,
                offset: parseFloat(document.getElementById('offset').value) || 0.0,
                unit: document.getElementById('unit').value || '',
                description: document.getElementById('description').value || ''
            };
            
            let response;
            if (selectedMappingId) {
                // Update existing
                response = await fetch(`${API_BASE}/modbus/${selectedMappingId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(mappingData)
                });
            } else {
                // Create new
                response = await fetch(`${API_BASE}/modbus`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(mappingData)
                });
            }
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                showTagNotification(selectedMappingId ? 'Datapoint updated successfully' : 'Datapoint added successfully', 'success');
                closeMappingModal();
                await loadMappings();
                renderMappingsTable();
                updateStats();
            } else {
                showTagNotification('Failed to save datapoint: ' + (result.message || result.error || 'Unknown error'), 'error');
            }
            
        } catch (error) {
            console.error('Error saving mapping:', error);
            showTagNotification('Error saving datapoint: ' + error.message, 'error');
        }
    }

    // Delete mapping
    async function deleteMapping(mappingId) {
        if (!confirm('Are you sure you want to delete this datapoint?')) {
            return;
        }
        
        try {
            const response = await fetch(`${API_BASE}/${mappingId}?type=modbus`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                showTagNotification('Datapoint deleted successfully', 'success');
                await loadMappings();
                renderMappingsTable();
                updateStats();
            } else {
                showTagNotification('Failed to delete datapoint: ' + (result.message || 'Unknown error'), 'error');
            }
            
        } catch (error) {
            console.error('Error deleting mapping:', error);
            showTagNotification('Error deleting datapoint: ' + error.message, 'error');
        }
    }

    // Expose functions globally
    window.modbusMapping = {
        editMapping: editMapping,
        deleteMapping: deleteMapping
    };

    // Initialize on load
    init();
};