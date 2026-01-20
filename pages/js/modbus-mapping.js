// modbus-mapping.js - Tag mapping functionality with backend API integration

// This function will be called by the router when loading the page
window.initializeModbusMapping = function() {
    console.log('Modbus Mapping page initialized');
    
    // Page state
    let devices = [];
    let mappings = [];
    let tags = [];
    let selectedDeviceId = null;
    let selectedMappingId = null;
    let currentStep = 1;
    let currentProtocol = 'modbus';

    // API base URL
    const API_BASE = '/api/tag-mapping';

    // Notification system - Fixed to prevent recursion
    function showTagNotification(message, type = 'info', duration = 3000) {
        // Remove existing notification if any
        const existingNotification = document.getElementById('tag-mapping-notification');
        if (existingNotification) {
            existingNotification.remove();
        }
        
        // Create notification element
        const notification = document.createElement('div');
        notification.id = 'tag-mapping-notification';
        notification.className = 'fixed top-4 right-4 z-50 max-w-sm';
        
        // Set colors based on type
        let bgColor = 'bg-blue-500';
        let textColor = 'text-white';
        let borderColor = 'border-blue-500';
        let icon = 'fa-info-circle';
        
        switch (type) {
            case 'success':
                bgColor = 'bg-green-500';
                borderColor = 'border-green-500';
                icon = 'fa-check-circle';
                break;
            case 'error':
                bgColor = 'bg-red-500';
                borderColor = 'border-red-500';
                icon = 'fa-exclamation-circle';
                break;
            case 'warning':
                bgColor = 'bg-yellow-500';
                borderColor = 'border-yellow-500';
                icon = 'fa-exclamation-triangle';
                break;
            case 'info':
            default:
                bgColor = 'bg-blue-500';
                borderColor = 'border-blue-500';
                icon = 'fa-info-circle';
        }
        
        notification.innerHTML = `
            <div class="rounded-lg shadow-lg ${bgColor} ${textColor} border ${borderColor} p-4 flex items-start justify-between animate-fade-in">
                <div class="flex items-center">
                    <i class="fa-solid ${icon} mr-3"></i>
                    <div class="text-sm font-medium">${message}</div>
                </div>
                <button class="ml-4 text-white hover:text-gray-200 focus:outline-none" onclick="document.getElementById('tag-mapping-notification').remove()">
                    <i class="fa-solid fa-times"></i>
                </button>
            </div>
        `;
        
        // Add to document
        document.body.appendChild(notification);
        
        // Auto-remove after duration
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, duration);
    }

    // Helper function to generate unique tag name suggestions
    function generateTagNameSuggestion(baseName, deviceId) {
        if (!baseName || !deviceId) return baseName;
        
        // Get all existing tag names for this device (excluding current mapping if editing)
        const existingTagNames = mappings
            .filter(m => (m.device_id || m.deviceId) === deviceId)
            .filter(m => m.id !== selectedMappingId) // Exclude current mapping when editing
            .map(m => m.tag_name || m.tagName)
            .map(name => name.toLowerCase());
        
        // Check if base name already exists (case-insensitive)
        const baseLower = baseName.toLowerCase();
        if (!existingTagNames.includes(baseLower)) {
            return baseName;
        }
        
        // Try adding number suffixes
        for (let i = 1; i <= 100; i++) {
            const suggestion = `${baseName}_${i}`;
            if (!existingTagNames.includes(suggestion.toLowerCase())) {
                return suggestion;
            }
        }
        
        // Try adding different suffixes
        const suffixes = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'Primary', 'Secondary', 'Backup', 'Main'];
        for (const suffix of suffixes) {
            const suggestion = `${baseName}_${suffix}`;
            if (!existingTagNames.includes(suggestion.toLowerCase())) {
                return suggestion;
            }
        }
        
        // Fallback: add timestamp
        return `${baseName}_${Date.now().toString().slice(-4)}`;
    }

    // Initialize application
    async function initApp() {
        try {
            // Load data from embedded data or fetch from API
            if (window.embeddedData) {
                devices = window.embeddedData.devices || [];
                mappings = window.embeddedData.mappings || [];
            } else {
                // Fallback: fetch from API
                await loadDataFromAPI();
            }
            
            generateTags();
            initDeviceFilters();
            renderMappingsTable();
            renderTagsList();
            setupEventListeners();
            
            console.log('Modbus Mapping app initialized successfully');
        } catch (error) {
            console.error('Error initializing app:', error);
            showTagNotification('Error loading tag mappings. Please refresh the page.', 'error');
        }
    }

    // Load data from API
    async function loadDataFromAPI() {
        try {
            // Load devices
            const devicesResponse = await fetch(`${API_BASE}/devices`);
            if (devicesResponse.ok) {
                const data = await devicesResponse.json();
                devices = data.devices || [];
            }
            
            // Load mappings
            const mappingsResponse = await fetch(`${API_BASE}/filter`);
            if (mappingsResponse.ok) {
                const data = await mappingsResponse.json();
                mappings = data.mappings || [];
            }
        } catch (error) {
            console.error('Error loading data from API:', error);
            throw error;
        }
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
            const device = devices.find(d => d.id === mapping.device_id || d.id === mapping.deviceId);
            return {
                id: mapping.id,
                name: mapping.tag_name || mapping.tagName,
                description: mapping.description || '',
                deviceId: mapping.device_id || mapping.deviceId,
                deviceName: device?.name || 'Unknown',
                deviceProtocol: device?.protocol || 'Unknown',
                value: getRandomValue(mapping),
                lastUpdated: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}),
                unit: mapping.unit || '',
                address: mapping.address,
                category: mapping.category || 'Sensors',
                usedBy: getUsedBy(mapping.category || 'Sensors'),
                dataType: mapping.data_type || mapping.dataType,
                pollInterval: mapping.poll_interval || mapping.pollInterval
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
            'flag': {min: 0, max: 65535},
            'default': {min: 0, max: 100}
        };
        
        const range = ranges[mapping.unit] || ranges.default;
        const random = range.min + Math.random() * (range.max - range.min);
        
        if ((mapping.data_type || mapping.dataType || '').includes('FLOAT')) {
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
                filteredMappings = mappings.filter(m => (m.device_id || m.deviceId) === device.id);
            }
        }
        
        filteredMappings.forEach(mapping => {
            const device = devices.find(d => d.id === (mapping.device_id || mapping.deviceId));
            if (!device) return;
            
            const row = document.createElement('tr');
            row.className = 'hover:bg-slate-50';
            row.dataset.mappingId = mapping.id;
            
            // Data type badge
            let dataTypeClass = 'data-type-badge ';
            const dataType = mapping.data_type || mapping.dataType || '';
            if (dataType.includes('INT16')) dataTypeClass += 'int16';
            else if (dataType.includes('INT32')) dataTypeClass += 'int32';
            else if (dataType.includes('FLOAT')) dataTypeClass += 'float32';
            else if (dataType.includes('UINT')) dataTypeClass += 'uint16';
            else dataTypeClass += 'bool';
            
            // Protocol badge
            let protocolClass = 'protocol-badge ';
            const protocol = device.protocol || 'unknown';
            switch(protocol) {
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
            
            row.innerHTML = `
                <td>
                    <div class="font-medium text-slate-900">${device.name}</div>
                    <div class="text-xs text-slate-500">${device.type}</div>
                </td>
                <td>
                    <span class="${protocolClass}">${protocol.replace('-', ' ').toUpperCase()}</span>
                </td>
                <td class="font-mono">${mapping.address}</td>
                <td>
                    <div class="font-medium">${mapping.tag_name || mapping.tagName}</div>
                    <div class="text-xs text-slate-500 truncate max-w-[150px]">${mapping.description || ''}</div>
                </td>
                <td><span class="${dataTypeClass}">${dataType}</span></td>
                <td>${mapping.unit || ''}</td>
                <td class="font-mono">${mapping.poll_interval || mapping.pollInterval || '200'}</td>
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
        
        // Attach event listeners to action buttons
        attachActionButtonsListeners();
    }

    function attachActionButtonsListeners() {
        // Edit buttons
        document.querySelectorAll('.edit-mapping-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const id = parseInt(this.getAttribute('data-id'));
                editMapping(id);
            });
        });
        
        // Delete buttons
        document.querySelectorAll('.delete-mapping-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const id = parseInt(this.getAttribute('data-id'));
                deleteMapping(id);
            });
        });
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
            if (emptyState) emptyState.classList.remove('hidden');
            return;
        } else {
            if (emptyState) emptyState.classList.add('hidden');
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
            
            const tagElement = document.createElement('div');
            tagElement.className = 'tag-card';
            tagElement.innerHTML = `
                <div class="flex justify-between items-start mb-3">
                    <div class="flex-1 min-w-0">
                        <div class="font-medium text-slate-900 truncate">${tag.name}</div>
                        <div class="text-xs text-slate-500 truncate">${tag.description}</div>
                    </div>
                    <div class="flex flex-col items-end gap-1">
                        <span class="${protocolClass}">${device?.protocol?.replace('-', ' ').toUpperCase() || ''}</span>
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

    // Import CSV function
    async function importCSV() {
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = '.csv';
        
        fileInput.onchange = async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                showTagNotification('Importing CSV file...', 'info');
                const response = await fetch(`${API_BASE}/import-csv`, {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showTagNotification(`CSV import completed! Imported: ${result.imported}, Failed: ${result.failed}`, 'success');
                    
                    // Reload data
                    await loadDataFromAPI();
                    generateTags();
                    renderMappingsTable();
                    renderTagsList();
                } else {
                    showTagNotification(`Import failed: ${result.error}`, 'error');
                }
            } catch (error) {
                console.error('Import error:', error);
                showTagNotification('Error importing CSV file', 'error');
            }
        };
        
        fileInput.click();
    }

    // Export CSV function
    async function exportCSV() {
        try {
            // Get current filters
            const deviceFilter = document.getElementById('deviceFilter').value;
            const device = devices.find(d => d.name === deviceFilter);
            
            // Build query parameters
            let queryParams = new URLSearchParams();
            if (deviceFilter !== 'All Devices' && device) {
                queryParams.append('device_id', device.id);
            }
            
            showTagNotification('Exporting CSV file...', 'info');
            
            // Make request
            const response = await fetch(`${API_BASE}/export-csv?${queryParams.toString()}`);
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'tag_mappings_export.csv';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                showTagNotification('CSV export completed!', 'success');
            } else {
                throw new Error('Export failed');
            }
        } catch (error) {
            console.error('Export error:', error);
            showTagNotification('Error exporting CSV file', 'error');
        }
    }

    // Add new mapping
    function addNewMapping() {
        console.log('Add new mapping clicked');
        
        // Reset selected mapping ID when adding new
        selectedMappingId = null;
        
        if (!selectedDeviceId) {
            // If no device is selected, show device selection modal
            showDeviceSelectionModal();
            return;
        }
        
        const device = devices.find(d => d.id === selectedDeviceId);
        if (!device) {
            showTagNotification('Selected device not found. Please select a device first.', 'error');
            return;
        }
        
        // Reset modal state
        resetModal();
        
        // Update modal title
        const modalTitle = document.getElementById('modalTitle');
        if (modalTitle) modalTitle.textContent = 'Add New Mapping';
        
        // Fill device info
        const deviceName = document.getElementById('mappingDeviceName');
        const protocol = document.getElementById('mappingProtocol');
        if (deviceName) deviceName.textContent = device.name;
        if (protocol) protocol.textContent = formatProtocolText(device.protocol, device.address);
        
        // Set current protocol based on device
        currentProtocol = getProtocolType(device.protocol);
        
        // Load protocol-specific configuration - ONLY for the selected device's protocol
        loadProtocolConfigurationForDevice(device);
        
        // Set default address based on device protocol
        setDefaultAddress(device);
        
        // Show modal
        const modal = document.getElementById('editMappingModal');
        if (modal) {
            modal.classList.add('active');
            console.log('Modal should be visible now');
        } else {
            console.error('Modal element not found!');
        }
    }

    // Helper function to format protocol text
    function formatProtocolText(protocol, address) {
        const protocolMap = {
            'modbus-rtu': 'Modbus RTU',
            'modbus-tcp': 'Modbus TCP',
            'can': 'CAN',
            'ethernet-ip': 'EtherNet/IP'
        };
        
        return `${protocolMap[protocol] || protocol.toUpperCase()} | Address: ${address || 'N/A'}`;
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
        // Remove existing modal if present
        const existingModal = document.getElementById('deviceSelectModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        const modal = document.createElement('div');
        modal.className = 'modal-overlay active';
        modal.id = 'deviceSelectModal';
        
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
                            <div class="p-3 border border-slate-200 rounded-lg hover:bg-slate-50 cursor-pointer device-select-item" data-id="${device.id}">
                                <div class="flex items-center justify-between">
                                    <div>
                                        <div class="font-medium">${device.name}</div>
                                        <div class="text-xs text-slate-500">${device.type} • ${device.protocol}</div>
                                    </div>
                                    <span class="text-xs px-2 py-1 rounded ${device.status === 'online' ? 'bg-green-100 text-green-800' : device.status === 'warning' ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'}">
                                        ${device.status}
                                    </span>
                                </div>
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
        
        // Add event listeners for device selection
        setTimeout(() => {
            document.querySelectorAll('.device-select-item').forEach(item => {
                item.addEventListener('click', function() {
                    const deviceId = this.getAttribute('data-id');
                    selectDeviceForMapping(deviceId);
                });
            });
            
            const closeBtn = document.getElementById('closeDeviceSelectModal');
            const cancelBtn = document.getElementById('cancelDeviceSelect');
            
            if (closeBtn) {
                closeBtn.addEventListener('click', closeDeviceSelectModal);
            }
            
            if (cancelBtn) {
                cancelBtn.addEventListener('click', closeDeviceSelectModal);
            }
        }, 10);
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
    async function editMapping(id) {
        try {
            selectedMappingId = id;
            
            const response = await fetch(`${API_BASE}/${id}`);
            if (!response.ok) {
                throw new Error('Failed to load mapping details');
            }
            
            const mapping = await response.json();
            
            if (mapping.success === false) {
                showTagNotification(mapping.error, 'error');
                return;
            }
            
            selectedDeviceId = mapping.deviceId;
            
            // Find device
            const device = devices.find(d => d.id === mapping.deviceId);
            if (!device) {
                showTagNotification('Device not found', 'error');
                return;
            }
            
            // Reset modal state
            resetModal();
            
            // Update modal title
            const modalTitle = document.getElementById('modalTitle');
            if (modalTitle) modalTitle.textContent = 'Edit Mapping';
            
            // Fill device info
            const deviceName = document.getElementById('mappingDeviceName');
            const protocol = document.getElementById('mappingProtocol');
            if (deviceName) deviceName.textContent = device.name;
            if (protocol) protocol.textContent = formatProtocolText(device.protocol, device.address);
            
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
            document.getElementById('mappingMinValue').value = mapping.minValid || '';
            document.getElementById('mappingMaxValue').value = mapping.maxValid || '';
            document.getElementById('mappingPollInterval').value = mapping.pollInterval;
            document.getElementById('mappingPollPreset').value = getPollPreset(mapping.pollInterval);
            document.getElementById('mappingCategory').value = mapping.category || 'Sensors';
            
            // Set address based on mapping
            const addressInput = document.getElementById('mappingAddressValue');
            if (addressInput) {
                addressInput.value = mapping.address;
            }
            
            // Load protocol-specific fields from mapping data
            if (mapping.registerType) {
                const addressTypeSelect = document.getElementById('mappingAddressType');
                if (addressTypeSelect) {
                    addressTypeSelect.value = mapping.registerType;
                }
            }
            
            if (mapping.registerCount) {
                const registerCountInput = document.getElementById('mappingRegisterCount');
                if (registerCountInput) {
                    registerCountInput.value = mapping.registerCount;
                }
            }
            
            if (mapping.byteOrder) {
                const byteOrderSelect = document.getElementById('mappingByteOrder');
                if (byteOrderSelect) {
                    byteOrderSelect.value = mapping.byteOrder;
                }
            }
            
            // Show modal
            const modal = document.getElementById('editMappingModal');
            if (modal) {
                modal.classList.add('active');
            }
            
            // Go to step 3 for editing
            goToStep(3);
            
        } catch (error) {
            console.error('Error loading mapping:', error);
            showTagNotification('Error loading mapping details', 'error');
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
        if (step1Content) step1Content.classList.add('active');
        
        // Reset form values to defaults
        const tagName = document.getElementById('mappingTagName');
        const description = document.getElementById('mappingDescription');
        const dataType = document.getElementById('mappingDataType');
        const endianness = document.getElementById('mappingEndianness');
        const unit = document.getElementById('mappingUnit');
        const scale = document.getElementById('mappingScale');
        const offset = document.getElementById('mappingOffset');
        const minValue = document.getElementById('mappingMinValue');
        const maxValue = document.getElementById('mappingMaxValue');
        const warning = document.getElementById('mappingWarning');
        const alarm = document.getElementById('mappingAlarm');
        const pollInterval = document.getElementById('mappingPollInterval');
        const pollPreset = document.getElementById('mappingPollPreset');
        const category = document.getElementById('mappingCategory');
        
        // Only reset if we're adding a new mapping (not editing)
        if (!selectedMappingId) {
            if (tagName) tagName.value = '';
            if (description) description.value = '';
            if (dataType) dataType.value = 'INT16';
            if (endianness) endianness.value = 'big-endian';
            if (unit) unit.value = '';
            if (scale) scale.value = '1';
            if (offset) offset.value = '0';
            if (minValue) minValue.value = '';
            if (maxValue) maxValue.value = '';
            if (warning) warning.value = '';
            if (alarm) alarm.value = '';
            if (pollInterval) pollInterval.value = '200';
            if (pollPreset) pollPreset.value = '200';
            if (category) category.value = 'Sensors';
        }
        
        // Reset advanced sections
        const validationSection = document.getElementById('validation-section');
        const validationChevron = document.getElementById('validation-chevron');
        
        if (validationSection) validationSection.classList.add('hidden');
        if (validationChevron) validationChevron.className = 'fa-solid fa-chevron-down text-xs text-slate-400';
    }

    // Update step indicator
    function updateStepIndicator() {
        // Update circles
        for (let i = 1; i <= 3; i++) {
            const circle = document.getElementById(`step${i}`);
            const label = circle ? circle.nextElementSibling : null;
            
            if (circle && label) {
                if (i === currentStep) {
                    circle.className = 'step-circle active';
                    label.className = 'step-label active';
                } else if (i < currentStep) {
                    circle.className = 'step-circle active';
                    label.className = 'step-label';
                } else {
                    circle.className = 'step-circle inactive';
                    label.className = 'step-label';
                }
            }
        }
        
        // Show/hide sections
        document.querySelectorAll('.dynamic-section').forEach(section => {
            section.classList.remove('active');
        });
        const currentStepContent = document.getElementById(`step${currentStep}-content`);
        if (currentStepContent) currentStepContent.classList.add('active');
    }

    // Navigate between steps
    function goToStep(step) {
        if (step >= 1 && step <= 3) {
            currentStep = step;
            updateStepIndicator();
        }
    }

    // Toggle section
    function toggleSection() {
        const section = document.getElementById('validation-section');
        const chevron = document.getElementById('validation-chevron');
        
        if (section && chevron) {
            section.classList.toggle('hidden');
            chevron.className = section.classList.contains('hidden') 
                ? 'fa-solid fa-chevron-down text-xs text-slate-400'
                : 'fa-solid fa-chevron-up text-xs text-slate-400';
        }
    }

    // Delete mapping
    async function deleteMapping(id) {
        if (!confirm('Are you sure you want to delete this mapping?')) {
            return;
        }
        
        try {
            const response = await fetch(`${API_BASE}/${id}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (result.success) {
                showTagNotification('Mapping deleted successfully!', 'success');
                
                // Remove from local state
                mappings = mappings.filter(m => m.id !== id);
                generateTags();
                renderMappingsTable();
                renderTagsList();
                
                // Reset selected mapping ID
                selectedMappingId = null;
            } else {
                showTagNotification(`Delete failed: ${result.error}`, 'error');
            }
        } catch (error) {
            console.error('Delete error:', error);
            showTagNotification('Error deleting mapping', 'error');
        }
    }

    // Setup event listeners
    function setupEventListeners() {
        console.log('Setting up event listeners...');
        
        // Device filter - affects mapping table
        const deviceFilter = document.getElementById('deviceFilter');
        if (deviceFilter) {
            deviceFilter.addEventListener('change', renderMappingsTable);
        }
        
        // Tag filters
        const tagSearch = document.getElementById('tagSearch');
        const tagCategoryFilter = document.getElementById('tagCategoryFilter');
        const tagDeviceFilter = document.getElementById('tagDeviceFilter');
        
        if (tagSearch) tagSearch.addEventListener('input', renderTagsList);
        if (tagCategoryFilter) tagCategoryFilter.addEventListener('change', renderTagsList);
        if (tagDeviceFilter) tagDeviceFilter.addEventListener('change', renderTagsList);
        
        // Add Mapping buttons
        const addMappingBtn = document.getElementById('addMappingBtn');
        const addFirstMappingBtn = document.getElementById('addFirstMappingBtn');
        
        if (addMappingBtn) {
            addMappingBtn.addEventListener('click', function() {
                // Reset selected mapping ID when adding new
                selectedMappingId = null;
                addNewMapping();
            });
            console.log('Add Mapping button listener attached');
        }
        
        if (addFirstMappingBtn) {
            addFirstMappingBtn.addEventListener('click', function() {
                // Reset selected mapping ID when adding new
                selectedMappingId = null;
                addNewMapping();
            });
        }
        
        // Import/Export CSV buttons
        const importCSVBtn = document.getElementById('importCSVBtn');
        const exportCSVBtn = document.getElementById('exportCSVBtn');
        
        if (importCSVBtn) importCSVBtn.addEventListener('click', importCSV);
        if (exportCSVBtn) exportCSVBtn.addEventListener('click', exportCSV);
        
        // Modal tabs
        const protocolTabsContainer = document.getElementById('protocolTabsContainer');
        if (protocolTabsContainer) {
            protocolTabsContainer.addEventListener('click', function(e) {
                const tab = e.target.closest('.tab');
                if (tab && tab.dataset.tab) {
                    const protocol = tab.dataset.tab;
                    loadAddressConfiguration(protocol);
                    loadProtocolSpecificFields(protocol);
                    
                    // Update active tab
                    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                    tab.classList.add('active');
                }
            });
        }
        
        // Step navigation
        const nextStep1Btn = document.getElementById('nextStep1Btn');
        const prevStep2Btn = document.getElementById('prevStep2Btn');
        const nextStep2Btn = document.getElementById('nextStep2Btn');
        const prevStep3Btn = document.getElementById('prevStep3Btn');
        
        if (nextStep1Btn) nextStep1Btn.addEventListener('click', () => goToStep(2));
        if (prevStep2Btn) prevStep2Btn.addEventListener('click', () => goToStep(1));
        if (nextStep2Btn) nextStep2Btn.addEventListener('click', () => goToStep(3));
        if (prevStep3Btn) prevStep3Btn.addEventListener('click', () => goToStep(2));
        
        // Poll preset selector
        const mappingPollPreset = document.getElementById('mappingPollPreset');
        if (mappingPollPreset) {
            mappingPollPreset.addEventListener('change', function() {
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
        const mappingDataType = document.getElementById('mappingDataType');
        if (mappingDataType) {
            mappingDataType.addEventListener('change', function() {
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
        
        // Edit mapping modal controls
        const closeEditMappingModal = document.getElementById('closeEditMappingModal');
        const cancelEditMapping = document.getElementById('cancelEditMapping');
        
        if (closeEditMappingModal) {
            closeEditMappingModal.addEventListener('click', function() {
                document.getElementById('editMappingModal').classList.remove('active');
                selectedMappingId = null;
                selectedDeviceId = null;
            });
        }
        
        if (cancelEditMapping) {
            cancelEditMapping.addEventListener('click', function() {
                document.getElementById('editMappingModal').classList.remove('active');
                selectedMappingId = null;
                selectedDeviceId = null;
            });
        }
        
        // Save mapping
        const saveMappingBtn = document.getElementById('saveMappingBtn');
        if (saveMappingBtn) {
            saveMappingBtn.addEventListener('click', async function() {
                const tagName = document.getElementById('mappingTagName').value.trim();
                const addressValue = document.getElementById('mappingAddressValue').value.trim();
                
                if (!tagName) {
                    showTagNotification('Tag name is required', 'error');
                    return;
                }
                
                if (!addressValue) {
                    showTagNotification('Address value is required', 'error');
                    return;
                }
                
                // Collect form data
                const formData = {
                    deviceId: selectedDeviceId,
                    tagName: tagName,
                    address: addressValue,
                    description: document.getElementById('mappingDescription').value,
                    dataType: document.getElementById('mappingDataType').value,
                    endianness: document.getElementById('mappingEndianness').value,
                    unit: document.getElementById('mappingUnit').value,
                    scale: document.getElementById('mappingScale').value,
                    offset: document.getElementById('mappingOffset').value,
                    minValid: document.getElementById('mappingMinValue').value || '',
                    maxValid: document.getElementById('mappingMaxValue').value || '',
                    pollInterval: document.getElementById('mappingPollInterval').value,
                    category: document.getElementById('mappingCategory').value,
                    protocol: currentProtocol
                };
                
                // Add protocol-specific fields
                const addressType = document.getElementById('mappingAddressType')?.value;
                if (addressType) {
                    formData.registerType = addressType;
                }
                
                // Add register count for modbus
                if (currentProtocol === 'modbus') {
                    const registerCount = document.getElementById('mappingRegisterCount')?.value;
                    if (registerCount) {
                        formData.registerCount = registerCount;
                    }
                    
                    const byteOrder = document.getElementById('mappingByteOrder')?.value;
                    if (byteOrder) {
                        formData.byteOrder = byteOrder;
                    }
                }
                
                try {
                    let response;
                    let method;
                    let url;
                    
                    if (selectedMappingId) {
                        // UPDATE existing mapping
                        console.log('Updating mapping ID:', selectedMappingId);
                        method = 'PUT';
                        url = `${API_BASE}/${selectedMappingId}`;
                    } else {
                        // CREATE new mapping
                        console.log('Creating new mapping');
                        method = 'POST';
                        url = `${API_BASE}`;
                    }
                    
                    showTagNotification('Saving mapping...', 'info');
                    
                    response = await fetch(url, {
                        method: method,
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(formData)
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        showTagNotification(selectedMappingId ? 'Mapping updated successfully!' : 'Mapping added successfully!', 'success');
                        
                        // Reload data
                        await loadDataFromAPI();
                        generateTags();
                        renderMappingsTable();
                        renderTagsList();
                        
                        // Close modal and reset state
                        document.getElementById('editMappingModal').classList.remove('active');
                        selectedMappingId = null;
                        selectedDeviceId = null;
                    } else {
                        // Handle specific error codes
                        if (result.code === 'TAG_001') {
                            // Tag name already exists - suggest alternatives
                            const suggestion = generateTagNameSuggestion(tagName, selectedDeviceId);
                            showTagNotification(`${result.error} Suggested: ${suggestion}`, 'error', 5000);
                            
                            // Auto-fill suggested name
                            document.getElementById('mappingTagName').value = suggestion;
                        } else {
                            showTagNotification(`Error: ${result.error}`, 'error');
                        }
                    }
                } catch (error) {
                    console.error('Save error:', error);
                    showTagNotification('Error saving mapping', 'error');
                }
            });
        }
        
        // Test buttons
        const testDeviceBtn = document.getElementById('testDeviceBtn');
        const validateAllBtn = document.getElementById('validateAllBtn');
        
        if (testDeviceBtn) {
            testDeviceBtn.addEventListener('click', async function() {
                if (!selectedDeviceId) {
                    showTagNotification('Please select a device first', 'error');
                    return;
                }
                
                const btn = this;
                const originalText = btn.innerHTML;
                btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1 text-xs"></i> Testing...';
                btn.disabled = true;
                
                try {
                    const response = await fetch(`${API_BASE}/devices/${selectedDeviceId}/test`, {
                        method: 'POST'
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        showTagNotification(`Device "${result.device_name}" test successful! Ping: ${result.ping_time_ms}ms, Status: ${result.status}`, 'success');
                    } else {
                        showTagNotification(`Test failed: ${result.error}`, 'error');
                    }
                } catch (error) {
                    console.error('Test error:', error);
                    showTagNotification('Error testing device', 'error');
                } finally {
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                }
            });
        }
        
        if (validateAllBtn) {
            validateAllBtn.addEventListener('click', async function() {
                const btn = this;
                const originalText = btn.innerHTML;
                btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1 text-xs"></i> Validating...';
                btn.disabled = true;
                
                try {
                    const response = await fetch(`${API_BASE}/validate-all`, {
                        method: 'POST'
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        if (result.errors && result.errors.length > 0) {
                            showTagNotification(`Validation completed with ${result.errors.length} error(s): ${result.errors.join(', ')}`, 'warning');
                        } else {
                            showTagNotification(`Validation complete! ${result.validated_count} mappings validated successfully.`, 'success');
                        }
                    } else {
                        showTagNotification(`Validation failed: ${result.error}`, 'error');
                    }
                } catch (error) {
                    console.error('Validation error:', error);
                    showTagNotification('Error validating mappings', 'error');
                } finally {
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                }
            });
        }
        
        // Save button
        const saveBtn = document.getElementById('save-btn');
        if (saveBtn) {
            saveBtn.addEventListener('click', async function() {
                const btn = this;
                const original = this.innerHTML;
                this.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Saving...';
                this.disabled = true;
                
                try {
                    const response = await fetch(`${API_BASE}/save-config`, {
                        method: 'PUT'
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        showTagNotification('Configuration saved successfully!', 'success');
                    } else {
                        showTagNotification(`Save failed: ${result.error}`, 'error');
                    }
                } catch (error) {
                    console.error('Save error:', error);
                    showTagNotification('Error saving configuration', 'error');
                } finally {
                    btn.innerHTML = original;
                    btn.disabled = false;
                }
            });
        }
        
        // Cancel button
        const cancelBtn = document.getElementById('cancel-btn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', function() {
                if (confirm('Discard all unsaved changes?')) {
                    showTagNotification('Changes discarded', 'info');
                    initApp(); // Reset to original data
                }
            });
        }
        
        // Reset default button
        const resetDefaultBtn = document.getElementById('resetDefaultBtn');
        if (resetDefaultBtn) {
            resetDefaultBtn.addEventListener('click', function() {
                if (confirm('Reset all mappings to default?')) {
                    initApp();
                    showTagNotification('Reset to default successful!', 'success');
                }
            });
        }
        
        // Reboot gateway button
        const rebootGatewayBtn = document.getElementById('rebootGatewayBtn');
        if (rebootGatewayBtn) {
            rebootGatewayBtn.addEventListener('click', function() {
                if (confirm('Are you sure you want to reboot the gateway? This will interrupt all communications.')) {
                    const btn = this;
                    const originalText = btn.innerHTML;
                    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Rebooting...';
                    btn.disabled = true;
                    
                    setTimeout(() => {
                        btn.innerHTML = originalText;
                        btn.disabled = false;
                        showTagNotification('Gateway reboot initiated!', 'success');
                    }, 2000);
                }
            });
        }
        
        // Validation toggle
        const validationToggle = document.getElementById('validationToggle');
        if (validationToggle) {
            validationToggle.addEventListener('click', toggleSection);
        }
        
        console.log('Event listeners setup complete');
    }

    // Initialize the app
    initApp();
};

// Export the main function
window.initializeModbusMapping = window.initializeModbusMapping;