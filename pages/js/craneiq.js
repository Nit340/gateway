// craneiq.js - CraneIQ Pro Configuration Page Script

// Check if already loaded to prevent duplicate declarations
if (typeof window.craneiqLoaded === 'undefined') {
    window.craneiqLoaded = true;

    // Data storage for dataloggers
    let dataloggers = [];
    let nextLoggerId = 1;

    // Device tags mapping
    const deviceTags = {
        'load_cell': [
            { name: 'Current Load', address: '40001', type: 'REAL', description: 'Real-time load measurement' },
            { name: 'Peak Load', address: '40003', type: 'REAL', description: 'Maximum load recorded' },
            { name: 'Load Cell Status', address: '40005', type: 'UINT16', description: 'Sensor health status' }
        ],
        'anti_collision': [
            { name: 'Distance to Obstacle', address: '40101', type: 'REAL', description: 'Closest obstacle distance' },
            { name: 'Collision Warning', address: '40103', type: 'BOOL', description: 'Warning flag' },
            { name: 'Emergency Stop', address: '40104', type: 'BOOL', description: 'Emergency stop triggered' }
        ],
        'emergency_stop': [
            { name: 'E-Stop Status', address: '40201', type: 'BOOL', description: 'Emergency stop button status' },
            { name: 'Stop Timestamp', address: '40202', type: 'UINT32', description: 'Time of last stop' }
        ],
        'hoist_motor': [
            { name: 'Motor Speed', address: '40301', type: 'REAL', description: 'Current motor RPM' },
            { name: 'Motor Current', address: '40303', type: 'REAL', description: 'Motor current draw' },
            { name: 'Motor Temperature', address: '40305', type: 'REAL', description: 'Motor temperature' }
        ],
        'trolley_motor': [
            { name: 'Trolley Position', address: '40401', type: 'REAL', description: 'Trolley position on beam' },
            { name: 'Trolley Speed', address: '40403', type: 'REAL', description: 'Trolley movement speed' }
        ],
        'bridge_motor': [
            { name: 'Bridge Position', address: '40501', type: 'REAL', description: 'Bridge position in bay' },
            { name: 'Bridge Speed', address: '40503', type: 'REAL', description: 'Bridge movement speed' }
        ],
        'encoder_x': [
            { name: 'X Position', address: '40601', type: 'REAL', description: 'X-axis absolute position' },
            { name: 'X Velocity', address: '40603', type: 'REAL', description: 'X-axis velocity' }
        ],
        'encoder_y': [
            { name: 'Y Position', address: '40701', type: 'REAL', description: 'Y-axis absolute position' },
            { name: 'Y Velocity', address: '40703', type: 'REAL', description: 'Y-axis velocity' }
        ],
        'encoder_z': [
            { name: 'Z Position', address: '40801', type: 'REAL', description: 'Z-axis (height) position' },
            { name: 'Z Velocity', address: '40803', type: 'REAL', description: 'Z-axis velocity' }
        ],
        'main_brake': [
            { name: 'Brake Status', address: '40901', type: 'BOOL', description: 'Brake engaged/released' },
            { name: 'Brake Wear', address: '40902', type: 'UINT16', description: 'Brake wear percentage' }
        ],
        'trolley_brake': [
            { name: 'Brake Status', address: '41001', type: 'BOOL', description: 'Brake engaged/released' },
            { name: 'Brake Pressure', address: '41002', type: 'REAL', description: 'Hydraulic pressure' }
        ],
        'weather_station': [
            { name: 'Wind Speed', address: '41101', type: 'REAL', description: 'Current wind speed' },
            { name: 'Wind Direction', address: '41103', type: 'UINT16', description: 'Wind direction in degrees' },
            { name: 'Temperature', address: '41105', type: 'REAL', description: 'Ambient temperature' },
            { name: 'Humidity', address: '41107', type: 'REAL', description: 'Relative humidity' }
        ],
        'vibration_sensor': [
            { name: 'Vibration Level', address: '41201', type: 'REAL', description: 'Vibration magnitude' },
            { name: 'Vibration Frequency', address: '41203', type: 'REAL', description: 'Dominant frequency' }
        ],
        'temperature_sensor': [
            { name: 'Temperature 1', address: '41301', type: 'REAL', description: 'First sensor reading' },
            { name: 'Temperature 2', address: '41302', type: 'REAL', description: 'Second sensor reading' },
            { name: 'Temperature 3', address: '41303', type: 'REAL', description: 'Third sensor reading' }
        ],
        'wind_sensor': [
            { name: 'Wind Speed', address: '41401', type: 'REAL', description: 'Current wind speed' },
            { name: 'Gust Speed', address: '41403', type: 'REAL', description: 'Peak gust speed' }
        ]
    };

    // Priority colors
    const priorityColors = {
        'critical': { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-200' },
        'high': { bg: 'bg-orange-100', text: 'text-orange-800', border: 'border-orange-200' },
        'medium': { bg: 'bg-yellow-100', text: 'text-yellow-800', border: 'border-yellow-200' },
        'low': { bg: 'bg-blue-100', text: 'text-blue-800', border: 'border-blue-200' }
    };

    // Condition display names
    const conditionDisplay = {
        'always': 'Always Log',
        'on_change': 'On Value Change',
        'threshold': 'Threshold Based',
        'scheduled': 'Scheduled Intervals'
    };

    /**
     * Show notification message
     */
    function showNotification(message, type = 'info') {
        if (typeof window.showNotification === 'function') {
            window.showNotification(message, type);
            return;
        }

        const container = document.getElementById('notification-container');
        if (!container) return;

        const notification = document.createElement('div');
        notification.className = `px-4 py-3 rounded-md shadow-lg border transform transition-all duration-300 translate-x-64 opacity-0`;

        const colors = {
            info: 'bg-blue-50 text-blue-800 border-blue-200',
            success: 'bg-green-50 text-green-800 border-green-200',
            warning: 'bg-amber-50 text-amber-800 border-amber-200',
            error: 'bg-red-50 text-red-800 border-red-200'
        };

        notification.className += ` ${colors[type]}`;
        notification.innerHTML = `
            <div class="flex items-center">
                <i class="fa-solid ${type === 'info' ? 'fa-circle-info' : type === 'success' ? 'fa-circle-check' : type === 'warning' ? 'fa-triangle-exclamation' : 'fa-circle-xmark'} mr-2"></i>
                <span>${message}</span>
            </div>
        `;

        container.appendChild(notification);

        // Animate in
        setTimeout(() => {
            notification.classList.remove('translate-x-64', 'opacity-0');
            notification.classList.add('translate-x-0', 'opacity-100');
        }, 10);

        // Remove after 5 seconds
        setTimeout(() => {
            notification.classList.remove('translate-x-0', 'opacity-100');
            notification.classList.add('translate-x-64', 'opacity-0');

            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 5000);
    }

    /**
     * Initialize button event listeners
     */
    function initializeButtons() {
        // Header/Footer buttons
        document.getElementById('reset-btn')?.addEventListener('click', function() {
            if (confirm('Reset all settings to defaults?')) {
                showNotification('Settings reset to defaults', 'info');
            }
        });

        document.getElementById('cancel-btn')?.addEventListener('click', function() {
            if (confirm('Cancel all changes?')) {
                window.location.reload();
            }
        });

        document.getElementById('save-btn')?.addEventListener('click', function() {
            saveConfiguration();
        });

        document.getElementById('test-btn')?.addEventListener('click', function() {
            showNotification('Testing connection to crane...', 'info');
            setTimeout(() => {
                showNotification('Connection test successful!', 'success');
            }, 2000);
        });

        // File upload
        document.getElementById('load-curve-upload')?.addEventListener('click', function() {
            document.getElementById('load-curve-file')?.click();
        });

        document.getElementById('load-curve-file')?.addEventListener('change', function(e) {
            if (e.target.files.length > 0) {
                const fileName = e.target.files[0].name;
                showNotification(`Load curve file uploaded: ${fileName}`, 'success');
            }
        });

        document.getElementById('upload-layout-btn')?.addEventListener('click', function() {
            showNotification('Upload layout dialog opened', 'info');
        });

        document.getElementById('add-peer-btn')?.addEventListener('click', function() {
            showNotification('Add peer crane dialog opened', 'info');
        });

        document.getElementById('add-zone-btn')?.addEventListener('click', function() {
            showNotification('Add new zone dialog opened', 'info');
        });

        // Datalogger modal
        const addDataloggerBtn = document.getElementById('add-datalogger-btn');
        const addDataloggerModal = document.getElementById('add-datalogger-modal');
        const cancelDataloggerBtn = document.getElementById('cancel-datalogger');
        const saveDataloggerBtn = document.getElementById('save-datalogger');

        if (addDataloggerBtn && addDataloggerModal) {
            addDataloggerBtn.addEventListener('click', () => {
                addDataloggerModal.classList.remove('hidden');
            });
        }

        if (cancelDataloggerBtn && addDataloggerModal) {
            cancelDataloggerBtn.addEventListener('click', () => {
                addDataloggerModal.classList.add('hidden');
            });
        }

        if (saveDataloggerBtn) {
            saveDataloggerBtn.addEventListener('click', saveDatalogger);
        }

        // Device select change
        const deviceSelect = document.getElementById('logger-device-select');
        const tagSelect = document.getElementById('logger-tag-select');

        if (deviceSelect && tagSelect) {
            deviceSelect.addEventListener('change', function() {
                const deviceType = this.value;
                tagSelect.disabled = !deviceType;

                if (deviceType && deviceTags[deviceType]) {
                    tagSelect.innerHTML = '<option value="">-- Select a tag --</option>';
                    deviceTags[deviceType].forEach(tag => {
                        const option = document.createElement('option');
                        option.value = JSON.stringify(tag);
                        option.textContent = `${tag.name} (${tag.address})`;
                        tagSelect.appendChild(option);
                    });
                } else {
                    tagSelect.innerHTML = '<option value="">-- First select a device --</option>';
                }

                document.getElementById('tag-description')?.classList.add('hidden');
            });

            tagSelect.addEventListener('change', function() {
                const tagDescription = document.getElementById('tag-description');
                const tagDescText = document.getElementById('tag-desc-text');
                const tagAddress = document.getElementById('tag-address');

                if (this.value && tagDescription && tagDescText && tagAddress) {
                    const tag = JSON.parse(this.value);
                    tagDescText.textContent = tag.description;
                    tagAddress.textContent = `${tag.address} (${tag.type})`;
                    tagDescription.classList.remove('hidden');
                } else if (tagDescription) {
                    tagDescription.classList.add('hidden');
                }
            });
        }

        // Storage calculation
        const storageSizeInput = document.getElementById('logger-storage-size');
        const storageUnitSelect = document.getElementById('logger-storage-unit');
        const samplingRateSelect = document.getElementById('sampling-rate');

        if (storageSizeInput && storageUnitSelect && samplingRateSelect) {
            const updateEstimatedDuration = () => {
                const size = parseFloat(storageSizeInput.value) || 100;
                const unit = storageUnitSelect.value;
                const sampling = parseInt(samplingRateSelect.value) || 5000;

                const storageMB = unit === 'gb' ? size * 1024 : size;
                const bytesPerSample = 4;
                const samplesPerHour = (3600000 / sampling);
                const mbPerHour = (bytesPerSample * samplesPerHour) / (1024 * 1024);
                const estimatedHours = storageMB / mbPerHour;

                const durationElement = document.getElementById('estimated-duration');
                if (durationElement) {
                    durationElement.textContent =
                        estimatedHours >= 8760 ? '>1 year' :
                        estimatedHours >= 720 ? `${Math.round(estimatedHours / 24)} days` :
                        estimatedHours >= 24 ? `${Math.round(estimatedHours / 24)} days` :
                        `${Math.round(estimatedHours)} hours`;
                }
            };

            storageSizeInput.addEventListener('input', updateEstimatedDuration);
            storageUnitSelect.addEventListener('change', updateEstimatedDuration);
            samplingRateSelect.addEventListener('change', updateEstimatedDuration);
        }
    }

    /**
     * Save datalogger configuration
     */
    function saveDatalogger() {
        const deviceSelect = document.getElementById('logger-device-select');
        const tagSelect = document.getElementById('logger-tag-select');
        const priorityInput = document.querySelector('input[name="logger-priority"]:checked');
        const conditionInput = document.querySelector('input[name="logger-condition"]:checked');
        const storageSizeInput = document.getElementById('logger-storage-size');
        const storageUnitSelect = document.getElementById('logger-storage-unit');
        const samplingRateSelect = document.getElementById('sampling-rate');
        const dataFormatSelect = document.getElementById('data-format');

        if (!deviceSelect.value || !tagSelect.value || !priorityInput || !conditionInput) {
            showNotification('Please fill in all required fields', 'warning');
            return;
        }

        const device = deviceSelect.options[deviceSelect.selectedIndex];
        const tag = JSON.parse(tagSelect.value);
        const size = parseFloat(storageSizeInput.value) || 100;
        const unit = storageUnitSelect.value;
        const sampling = parseInt(samplingRateSelect.value) || 5000;

        const logger = {
            id: nextLoggerId++,
            device: {
                name: device.textContent,
                deviceId: deviceSelect.value
            },
            tag: tag,
            priority: priorityInput.value,
            condition: conditionInput.value,
            conditionDetails: getConditionDetails(conditionInput.value),
            storage: {
                size: size,
                unit: unit,
                totalMB: unit === 'gb' ? size * 1024 : size
            },
            sampling: {
                interval: sampling,
                display: samplingRateSelect.options[samplingRateSelect.selectedIndex].text
            },
            dataFormat: dataFormatSelect.options[dataFormatSelect.selectedIndex].text,
            dataRate: calculateDataRate(sampling),
            status: 'active',
            createdAt: new Date().toISOString()
        };

        dataloggers.push(logger);
        renderLoggersTable();
        updateSummaryStats();

        document.getElementById('add-datalogger-modal')?.classList.add('hidden');
        showNotification('Datalogger created successfully', 'success');

        // Reset form
        deviceSelect.value = '';
        tagSelect.innerHTML = '<option value="">-- First select a device --</option>';
        tagSelect.disabled = true;
        document.getElementById('tag-description')?.classList.add('hidden');
    }

    function getConditionDetails(condition) {
        switch (condition) {
            case 'always': return 'Continuous logging';
            case 'on_change': return 'Log when value changes';
            case 'threshold': return 'Log when threshold exceeded';
            case 'scheduled': return 'Log at scheduled intervals';
            default: return 'Custom condition';
        }
    }

    function calculateDataRate(sampling) {
        const bytesPerSample = 4;
        const samplesPerHour = (3600000 / sampling);
        return (bytesPerSample * samplesPerHour) / (1024 * 1024); // MB/hour
    }

    /**
     * Render loggers table
     */
    function renderLoggersTable() {
        const tableBody = document.getElementById('loggers-table-body');
        const noLoggersRow = document.getElementById('no-loggers-row');

        if (!tableBody || !noLoggersRow) return;

        if (dataloggers.length === 0) {
            noLoggersRow.classList.remove('hidden');
            return;
        }

        noLoggersRow.classList.add('hidden');
        tableBody.innerHTML = '';

        dataloggers.forEach((logger) => {
            const priority = priorityColors[logger.priority];

            const row = document.createElement('tr');
            row.className = `hover:bg-slate-50 ${priority.bg.replace('100', '50')}`;

            row.innerHTML = `
                <td class="px-4 py-3">
                    <div class="font-medium text-slate-900">${logger.device.name}</div>
                    <div class="text-xs text-slate-500">${logger.device.deviceId}</div>
                </td>
                <td class="px-4 py-3">
                    <div class="font-medium text-slate-900">${logger.tag.name}</div>
                    <div class="text-xs text-slate-500">${logger.tag.address} • ${logger.tag.type}</div>
                </td>
                <td class="px-4 py-3">
                    <span class="px-2 py-1 text-xs font-medium rounded-full ${priority.bg} ${priority.text}">
                        ${logger.priority.charAt(0).toUpperCase() + logger.priority.slice(1)}
                    </span>
                </td>
                <td class="px-4 py-3">
                    <div class="text-sm font-medium text-slate-900">${conditionDisplay[logger.condition] || logger.condition}</div>
                    <div class="text-xs text-slate-500">${logger.conditionDetails}</div>
                </td>
                <td class="px-4 py-3">
                    <div class="text-sm font-medium text-slate-900">${logger.storage.size} ${logger.storage.unit.toUpperCase()}</div>
                    <div class="text-xs text-slate-500">~${Math.round((logger.storage.totalMB / logger.dataRate))} hours</div>
                </td>
                <td class="px-4 py-3">
                    <div class="text-sm text-slate-900">${logger.sampling.display}</div>
                    <div class="text-xs text-slate-500">${logger.dataFormat}</div>
                </td>
                <td class="px-4 py-3">
                    <span class="px-2 py-1 text-xs font-medium ${logger.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-slate-100 text-slate-800'} rounded-full">
                        ${logger.status === 'active' ? 'Active' : 'Paused'}
                    </span>
                </td>
                <td class="px-4 py-3">
                    <div class="flex items-center gap-2">
                        <button class="delete-logger text-red-600 hover:text-red-800 p-1 rounded hover:bg-red-50"
                                data-id="${logger.id}" title="Delete">
                            <i class="fa-solid fa-trash text-xs"></i>
                        </button>
                        <button class="toggle-logger text-slate-600 hover:text-slate-800 p-1 rounded hover:bg-slate-100"
                                data-id="${logger.id}" title="${logger.status === 'active' ? 'Pause' : 'Activate'}">
                            <i class="fa-solid fa-power-off text-xs ${logger.status === 'active' ? 'text-green-600' : 'text-slate-400'}"></i>
                        </button>
                    </div>
                </td>
            `;

            tableBody.appendChild(row);
        });

        attachLoggerEventListeners();
    }

    /**
     * Attach event listeners to logger action buttons
     */
    function attachLoggerEventListeners() {
        document.querySelectorAll('.delete-logger').forEach(btn => {
            btn.addEventListener('click', function() {
                const loggerId = parseInt(this.dataset.id);
                if (confirm('Delete this datalogger?')) {
                    dataloggers = dataloggers.filter(l => l.id !== loggerId);
                    renderLoggersTable();
                    updateSummaryStats();
                    showNotification('Datalogger deleted', 'success');
                }
            });
        });

        document.querySelectorAll('.toggle-logger').forEach(btn => {
            btn.addEventListener('click', function() {
                const loggerId = parseInt(this.dataset.id);
                const logger = dataloggers.find(l => l.id === loggerId);
                if (logger) {
                    logger.status = logger.status === 'active' ? 'paused' : 'active';
                    renderLoggersTable();
                    updateSummaryStats();
                    showNotification(`Datalogger ${logger.status}`, 'info');
                }
            });
        });
    }

    /**
     * Update summary statistics
     */
    function updateSummaryStats() {
        const activeLoggersCount = document.getElementById('active-loggers-count');
        const totalStorage = document.getElementById('total-storage');
        const totalDataRate = document.getElementById('total-data-rate');
        const bufferHealth = document.getElementById('buffer-health');

        if (activeLoggersCount) {
            activeLoggersCount.textContent = dataloggers.filter(l => l.status === 'active').length;
        }

        if (totalStorage) {
            const storage = dataloggers.reduce((sum, l) => sum + l.storage.totalMB, 0);
            totalStorage.textContent = `${Math.round(storage)} MB`;
        }

        if (totalDataRate) {
            const rate = dataloggers.filter(l => l.status === 'active').reduce((sum, l) => sum + l.dataRate, 0);
            totalDataRate.textContent = `${rate.toFixed(2)} MB/h`;
        }

        if (bufferHealth) {
            const health = dataloggers.length === 0 ? 'N/A' :
                          dataloggers.length < 5 ? 'Good' :
                          dataloggers.length < 10 ? 'Fair' : 'High Load';
            bufferHealth.textContent = health;
        }
    }

    /**
     * Initialize toggle switches
     */
    function initializeToggles() {
        document.querySelectorAll('input[type="checkbox"][class*="peer"]').forEach(toggle => {
            toggle.addEventListener('change', function() {
                const settingName = this.closest('div')?.querySelector('span')?.textContent || 'Setting';
                const status = this.checked ? 'enabled' : 'disabled';
                showNotification(`${settingName} ${status}`, 'info');
            });
        });
    }

    /**
     * Initialize select dropdowns
     */
    function initializeSelects() {
        document.querySelectorAll('select').forEach(select => {
            select.addEventListener('change', function() {
                const settingName = this.previousElementSibling?.textContent || 'Setting';
                const value = this.options[this.selectedIndex].text;
                showNotification(`${settingName} changed to: ${value}`, 'info');
            });
        });
    }

    /**
     * Initialize operating mode buttons
     */
    function initializeModeButtons() {
        const modeButtons = document.querySelectorAll('.flex.bg-slate-100 button');
        modeButtons.forEach(button => {
            button.addEventListener('click', function() {
                modeButtons.forEach(btn => {
                    btn.classList.remove('bg-blue-600', 'text-white', 'shadow');
                    btn.classList.add('text-slate-600', 'hover:bg-slate-50');
                });
                this.classList.add('bg-blue-600', 'text-white', 'shadow');
                this.classList.remove('text-slate-600', 'hover:bg-slate-50');

                const mode = this.textContent;
                showNotification(`Operating mode set to: ${mode}`, 'info');
            });
        });
    }

    /**
     * Save configuration function
     */
    function saveConfiguration() {
        const saveBtn = document.getElementById('save-btn');

        if (saveBtn) {
            saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Saving...';
            saveBtn.disabled = true;
        }

        // Simulate API call
        setTimeout(() => {
            if (saveBtn) {
                saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk mr-2"></i> Save Configuration';
                saveBtn.disabled = false;
            }

            showNotification('CraneIQ configuration saved successfully!', 'success');
        }, 1500);
    }

    /**
     * Load configuration from API
     */
    async function loadConfiguration() {
        try {
            const dataElement = document.getElementById('craneiq-data');
            if (!dataElement) return;

            const endpoints = JSON.parse(dataElement.dataset.apiEndpoints || '{}');
            const response = await fetch(endpoints.load || '/api/craneiq-configuration');

            if (!response.ok) {
                throw new Error('HTTP ' + response.status);
            }

            const config = await response.json();
            console.log('CraneIQ configuration loaded:', config);

            // Populate form with loaded data
            // Add your population logic here

        } catch (error) {
            console.error('Load error:', error);
            showNotification('Failed to load configuration', 'error');
        }
    }

    /**
     * Cleanup function
     */
    function cleanupCraneIQ() {
        // Clear dataloggers
        dataloggers = [];

        // Remove event listeners by cloning and replacing buttons
        const buttons = ['save-btn', 'cancel-btn', 'reset-btn', 'test-btn'];
        buttons.forEach(btnId => {
            const btn = document.getElementById(btnId);
            if (btn) {
                const newBtn = btn.cloneNode(true);
                btn.parentNode.replaceChild(newBtn, btn);
            }
        });

        console.log('CraneIQ cleanup complete');
    }

    /**
     * Initialize CraneIQ page
     */
    window.initCraneIQ = function() {
        console.log('Initializing CraneIQ Pro Configuration');

        // Initialize components
        initializeButtons();
        initializeToggles();
        initializeSelects();
        initializeModeButtons();

        // Render initial state
        renderLoggersTable();
        updateSummaryStats();

        // Load configuration
        loadConfiguration();
    };

    // Add cleanup method to window for router to call
    window.cleanupCraneIQ = cleanupCraneIQ;

    // Cleanup on page unload
    window.addEventListener('beforeunload', function() {
        cleanupCraneIQ();
    });
}

// Export for module system
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initCraneIQ: window.initCraneIQ,
        cleanupCraneIQ: window.cleanupCraneIQ
    };
}