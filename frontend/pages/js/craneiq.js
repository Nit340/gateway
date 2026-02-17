// craneiq.js - CraneIQ Pro Configuration Page Script
// Uses static data, no API endpoint connections

// Check if already loaded to prevent duplicate declarations
if (typeof window.craneiqLoaded === 'undefined') {
    window.craneiqLoaded = true;

    // ==================== STATIC DATA ====================
    
    // Datalogger storage
    let dataloggers = [];
    let nextLoggerId = 1;

    // Device tags mapping - comprehensive list for all devices
    const deviceTags = {
        'load_cell': [
            { name: 'Current Load', address: '40001', type: 'REAL', description: 'Real-time load measurement in kg' },
            { name: 'Peak Load', address: '40003', type: 'REAL', description: 'Maximum load recorded in current session' },
            { name: 'Load Cell Status', address: '40005', type: 'UINT16', description: 'Sensor health status (0=OK, 1=Warning, 2=Error)' }
        ],
        'anti_collision': [
            { name: 'Distance to Obstacle', address: '40101', type: 'REAL', description: 'Closest obstacle distance in meters' },
            { name: 'Collision Warning', address: '40103', type: 'BOOL', description: 'Warning flag when approaching obstacle' },
            { name: 'Emergency Stop', address: '40104', type: 'BOOL', description: 'Emergency stop triggered by anti-collision' }
        ],
        'emergency_stop': [
            { name: 'E-Stop Status', address: '40201', type: 'BOOL', description: 'Emergency stop button status' },
            { name: 'Stop Timestamp', address: '40202', type: 'UINT32', description: 'Unix timestamp of last stop' }
        ],
        'hoist_motor': [
            { name: 'Motor Speed', address: '40301', type: 'REAL', description: 'Current motor RPM' },
            { name: 'Motor Current', address: '40303', type: 'REAL', description: 'Motor current draw in Amps' },
            { name: 'Motor Temperature', address: '40305', type: 'REAL', description: 'Motor winding temperature in °C' }
        ],
        'trolley_motor': [
            { name: 'Trolley Position', address: '40401', type: 'REAL', description: 'Trolley position on beam in meters' },
            { name: 'Trolley Speed', address: '40403', type: 'REAL', description: 'Trolley movement speed m/s' }
        ],
        'bridge_motor': [
            { name: 'Bridge Position', address: '40501', type: 'REAL', description: 'Bridge position in bay (meters)' },
            { name: 'Bridge Speed', address: '40503', type: 'REAL', description: 'Bridge movement speed m/s' }
        ],
        'encoder_x': [
            { name: 'X Position', address: '40601', type: 'REAL', description: 'X-axis absolute position in meters' },
            { name: 'X Velocity', address: '40603', type: 'REAL', description: 'X-axis velocity m/s' }
        ],
        'encoder_y': [
            { name: 'Y Position', address: '40701', type: 'REAL', description: 'Y-axis absolute position in meters' },
            { name: 'Y Velocity', address: '40703', type: 'REAL', description: 'Y-axis velocity m/s' }
        ],
        'encoder_z': [
            { name: 'Z Position', address: '40801', type: 'REAL', description: 'Z-axis (height) position in meters' },
            { name: 'Z Velocity', address: '40803', type: 'REAL', description: 'Z-axis velocity m/s' }
        ],
        'main_brake': [
            { name: 'Brake Status', address: '40901', type: 'BOOL', description: 'Brake engaged (1) or released (0)' },
            { name: 'Brake Wear', address: '40902', type: 'UINT16', description: 'Brake wear percentage (0-100)' }
        ],
        'trolley_brake': [
            { name: 'Brake Status', address: '41001', type: 'BOOL', description: 'Brake engaged (1) or released (0)' },
            { name: 'Brake Pressure', address: '41002', type: 'REAL', description: 'Hydraulic pressure in bar' }
        ],
        'weather_station': [
            { name: 'Wind Speed', address: '41101', type: 'REAL', description: 'Current wind speed in m/s' },
            { name: 'Wind Direction', address: '41103', type: 'UINT16', description: 'Wind direction in degrees (0-360)' },
            { name: 'Temperature', address: '41105', type: 'REAL', description: 'Ambient temperature in °C' },
            { name: 'Humidity', address: '41107', type: 'REAL', description: 'Relative humidity percentage' }
        ],
        'vibration_sensor': [
            { name: 'Vibration Level', address: '41201', type: 'REAL', description: 'Vibration magnitude in mm/s' },
            { name: 'Vibration Frequency', address: '41203', type: 'REAL', description: 'Dominant frequency in Hz' }
        ],
        'temperature_sensor': [
            { name: 'Temperature 1', address: '41301', type: 'REAL', description: 'First sensor reading °C' },
            { name: 'Temperature 2', address: '41302', type: 'REAL', description: 'Second sensor reading °C' },
            { name: 'Temperature 3', address: '41303', type: 'REAL', description: 'Third sensor reading °C' }
        ],
        'wind_sensor': [
            { name: 'Wind Speed', address: '41401', type: 'REAL', description: 'Current wind speed in m/s' },
            { name: 'Gust Speed', address: '41403', type: 'REAL', description: 'Peak gust speed in m/s' }
        ]
    };

    // Priority colors for dataloggers
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

    // ==================== HELPER FUNCTIONS ====================

    /**
     * Show notification message
     */
    function showNotification(message, type = 'info') {
        // Use common.js notification if available
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

        notification.className += ` ${colors[type] || colors.info}`;
        notification.innerHTML = `
            <div class="flex items-center">
                <i class="fa-solid ${type === 'info' ? 'fa-circle-info' : type === 'success' ? 'fa-circle-check' : type === 'warning' ? 'fa-triangle-exclamation' : 'fa-circle-xmark'} mr-2"></i>
                <span>${message}</span>
            </div>
        `;

        container.appendChild(notification);

        setTimeout(() => {
            notification.classList.remove('translate-x-64', 'opacity-0');
            notification.classList.add('translate-x-0', 'opacity-100');
        }, 10);

        setTimeout(() => {
            notification.classList.remove('translate-x-0', 'opacity-100');
            notification.classList.add('translate-x-64', 'opacity-0');
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }

    function calculateDataRate(samplingInterval) {
        const bytesPerSample = 4;
        const samplesPerHour = 3600000 / samplingInterval;
        return (bytesPerSample * samplesPerHour) / (1024 * 1024);
    }

    function getConditionDetails(condition) {
        const details = {
            'always': 'Continuous logging',
            'on_change': 'Log when value changes',
            'threshold': 'Log when threshold exceeded',
            'scheduled': 'Log at scheduled intervals'
        };
        return details[condition] || 'Custom condition';
    }

    function calculateEstimatedDuration(storageMB, dataRateMBPerHour) {
        const hours = storageMB / dataRateMBPerHour;
        if (hours >= 8760) return '>1 year';
        if (hours >= 720) return `${Math.round(hours / 730)} months`;
        if (hours >= 24) return `${Math.round(hours / 24)} days`;
        return `${Math.round(hours)} hours`;
    }

    // ==================== BUTTON EVENT HANDLERS ====================

    function initializeButtons() {
        console.log('Initializing CraneIQ buttons...');

        document.getElementById('reset-btn')?.addEventListener('click', function() {
            if (confirm('Reset all CraneIQ settings to defaults?')) {
                showNotification('Settings reset to defaults', 'info');
            }
        });

        document.getElementById('cancel-btn')?.addEventListener('click', function() {
            if (confirm('Discard all changes?')) {
                showNotification('Changes discarded', 'info');
            }
        });

        document.getElementById('save-btn')?.addEventListener('click', saveConfiguration);
        
        document.getElementById('test-btn')?.addEventListener('click', function() {
            showNotification('Testing crane connection...', 'info');
            setTimeout(() => showNotification('Connection test successful!', 'success'), 2000);
        });

        document.getElementById('upload-layout-btn')?.addEventListener('click', function() {
            showNotification('Upload layout feature - Select floor plan or CAD drawing', 'info');
        });

        document.getElementById('add-peer-btn')?.addEventListener('click', function() {
            showNotification('Add peer crane for multi-crane coordination', 'info');
        });

        document.getElementById('add-zone-btn')?.addEventListener('click', function() {
            showNotification('Define new safety or operational zone', 'info');
        });

        const loadCurveUpload = document.getElementById('load-curve-upload');
        const loadCurveFile = document.getElementById('load-curve-file');
        
        if (loadCurveUpload && loadCurveFile) {
            loadCurveUpload.addEventListener('click', () => loadCurveFile.click());
            loadCurveFile.addEventListener('change', function(e) {
                if (e.target.files.length > 0) {
                    showNotification(`Load curve file uploaded: ${e.target.files[0].name}`, 'success');
                }
            });
        }

        initializeDataloggerModal();
    }

    function initializeDataloggerModal() {
        const addBtn = document.getElementById('add-datalogger-btn');
        const modal = document.getElementById('add-datalogger-modal');
        const cancelBtn = document.getElementById('cancel-datalogger');
        const saveBtn = document.getElementById('save-datalogger');

        if (addBtn && modal) addBtn.addEventListener('click', () => modal.classList.remove('hidden'));
        if (cancelBtn && modal) {
            cancelBtn.addEventListener('click', () => {
                modal.classList.add('hidden');
                resetDataloggerForm();
            });
        }
        if (saveBtn) saveBtn.addEventListener('click', saveDatalogger);

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
                const tagDesc = document.getElementById('tag-description');
                const tagDescText = document.getElementById('tag-desc-text');
                const tagAddress = document.getElementById('tag-address');

                if (this.value && tagDesc && tagDescText && tagAddress) {
                    try {
                        const tag = JSON.parse(this.value);
                        tagDescText.textContent = tag.description;
                        tagAddress.textContent = `${tag.address} (${tag.type})`;
                        tagDesc.classList.remove('hidden');
                    } catch (e) {
                        tagDesc.classList.add('hidden');
                    }
                } else if (tagDesc) {
                    tagDesc.classList.add('hidden');
                }
            });
        }

        const storageSizeInput = document.getElementById('logger-storage-size');
        const storageUnitSelect = document.getElementById('logger-storage-unit');
        const samplingRateSelect = document.getElementById('sampling-rate');

        if (storageSizeInput && storageUnitSelect && samplingRateSelect) {
            const updateDuration = () => {
                const size = parseFloat(storageSizeInput.value) || 100;
                const unit = storageUnitSelect.value;
                const sampling = parseInt(samplingRateSelect.value) || 5000;
                const storageMB = unit === 'gb' ? size * 1024 : size;
                const dataRate = calculateDataRate(sampling);
                const duration = calculateEstimatedDuration(storageMB, dataRate);
                const el = document.getElementById('estimated-duration');
                if (el) el.textContent = duration;
            };

            storageSizeInput.addEventListener('input', updateDuration);
            storageUnitSelect.addEventListener('change', updateDuration);
            samplingRateSelect.addEventListener('change', updateDuration);
            updateDuration();
        }
    }

    function resetDataloggerForm() {
        const deviceSelect = document.getElementById('logger-device-select');
        const tagSelect = document.getElementById('logger-tag-select');
        if (deviceSelect) deviceSelect.value = '';
        if (tagSelect) {
            tagSelect.innerHTML = '<option value="">-- First select a device --</option>';
            tagSelect.disabled = true;
        }
        document.getElementById('tag-description')?.classList.add('hidden');
        document.querySelectorAll('input[name="logger-priority"]').forEach(i => i.checked = false);
        document.querySelectorAll('input[name="logger-condition"]').forEach(i => i.checked = false);
    }

    function saveDatalogger() {
        const deviceSelect = document.getElementById('logger-device-select');
        const tagSelect = document.getElementById('logger-tag-select');
        const priorityInput = document.querySelector('input[name="logger-priority"]:checked');
        const conditionInput = document.querySelector('input[name="logger-condition"]:checked');
        const storageSizeInput = document.getElementById('logger-storage-size');
        const storageUnitSelect = document.getElementById('logger-storage-unit');
        const samplingRateSelect = document.getElementById('sampling-rate');
        const dataFormatSelect = document.getElementById('data-format');

        if (!deviceSelect?.value) return showNotification('Please select a device', 'warning');
        if (!tagSelect?.value) return showNotification('Please select a data tag', 'warning');
        if (!priorityInput) return showNotification('Please select a priority level', 'warning');
        if (!conditionInput) return showNotification('Please select a logging condition', 'warning');

        try {
            const device = deviceSelect.options[deviceSelect.selectedIndex];
            const tag = JSON.parse(tagSelect.value);
            const size = parseFloat(storageSizeInput.value) || 100;
            const unit = storageUnitSelect.value;
            const sampling = parseInt(samplingRateSelect.value) || 5000;
            const dataRate = calculateDataRate(sampling);
            const storageMB = unit === 'gb' ? size * 1024 : size;

            const logger = {
                id: nextLoggerId++,
                device: { name: device.textContent, deviceId: deviceSelect.value },
                tag: tag,
                priority: priorityInput.value,
                condition: conditionInput.value,
                conditionDetails: getConditionDetails(conditionInput.value),
                storage: { size: size, unit: unit, totalMB: storageMB },
                sampling: { 
                    interval: sampling, 
                    display: samplingRateSelect.options[samplingRateSelect.selectedIndex].text 
                },
                dataFormat: dataFormatSelect.options[dataFormatSelect.selectedIndex].text,
                dataRate: dataRate,
                status: 'active',
                createdAt: new Date().toISOString()
            };

            dataloggers.push(logger);
            renderLoggersTable();
            updateSummaryStats();
            document.getElementById('add-datalogger-modal')?.classList.add('hidden');
            showNotification('Datalogger created successfully', 'success');
            resetDataloggerForm();
        } catch (error) {
            console.error('Error saving datalogger:', error);
            showNotification('Error creating datalogger', 'error');
        }
    }

    function renderLoggersTable() {
        const tableBody = document.getElementById('loggers-table-body');
        const noLoggersRow = document.getElementById('no-loggers-row');
        if (!tableBody || !noLoggersRow) return;

        if (dataloggers.length === 0) {
            noLoggersRow.classList.remove('hidden');
            return;
        }

        noLoggersRow.classList.add('hidden');
        tableBody.innerHTML = dataloggers.map(logger => {
            const priority = priorityColors[logger.priority];
            const duration = calculateEstimatedDuration(logger.storage.totalMB, logger.dataRate);
            
            return `
                <tr class="hover:bg-slate-50 ${priority.bg.replace('100', '50')}">
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
                        <div class="text-sm font-medium text-slate-900">${conditionDisplay[logger.condition]}</div>
                        <div class="text-xs text-slate-500">${logger.conditionDetails}</div>
                    </td>
                    <td class="px-4 py-3">
                        <div class="text-sm font-medium text-slate-900">${logger.storage.size} ${logger.storage.unit.toUpperCase()}</div>
                        <div class="text-xs text-slate-500">~${duration}</div>
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
                            <button class="delete-logger text-red-600 hover:text-red-800 p-1 rounded hover:bg-red-50" data-id="${logger.id}">
                                <i class="fa-solid fa-trash text-xs"></i>
                            </button>
                            <button class="toggle-logger text-slate-600 hover:text-slate-800 p-1 rounded hover:bg-slate-100" data-id="${logger.id}">
                                <i class="fa-solid fa-power-off text-xs ${logger.status === 'active' ? 'text-green-600' : 'text-slate-400'}"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        attachLoggerEventListeners();
    }

    function attachLoggerEventListeners() {
        document.querySelectorAll('.delete-logger').forEach(btn => {
            btn.addEventListener('click', function() {
                const id = parseInt(this.dataset.id);
                if (confirm('Delete this datalogger?')) {
                    dataloggers = dataloggers.filter(l => l.id !== id);
                    renderLoggersTable();
                    updateSummaryStats();
                    showNotification('Datalogger deleted', 'success');
                }
            });
        });

        document.querySelectorAll('.toggle-logger').forEach(btn => {
            btn.addEventListener('click', function() {
                const logger = dataloggers.find(l => l.id === parseInt(this.dataset.id));
                if (logger) {
                    logger.status = logger.status === 'active' ? 'paused' : 'active';
                    renderLoggersTable();
                    updateSummaryStats();
                    showNotification(`Datalogger ${logger.status}`, 'info');
                }
            });
        });
    }

    function updateSummaryStats() {
        const activeCount = document.getElementById('active-loggers-count');
        const totalStorage = document.getElementById('total-storage');
        const totalDataRate = document.getElementById('total-data-rate');
        const bufferHealth = document.getElementById('buffer-health');

        if (activeCount) activeCount.textContent = dataloggers.filter(l => l.status === 'active').length;
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

    function initializeToggles() {
        document.querySelectorAll('input[type="checkbox"][class*="peer"]').forEach(toggle => {
            toggle.addEventListener('change', function() {
                const settingName = this.closest('div')?.querySelector('span')?.textContent || 'Setting';
                showNotification(`${settingName} ${this.checked ? 'enabled' : 'disabled'}`, 'info');
            });
        });
    }

    function initializeSelects() {
        document.querySelectorAll('select').forEach(select => {
            select.addEventListener('change', function() {
                const label = this.previousElementSibling;
                const settingName = label?.textContent || 'Setting';
                const value = this.options[this.selectedIndex]?.text;
                if (value) showNotification(`${settingName} changed to: ${value}`, 'info');
            });
        });
    }

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
                showNotification(`Operating mode set to: ${this.textContent.trim()}`, 'info');
            });
        });
    }

    function saveConfiguration() {
        const saveBtn = document.getElementById('save-btn');
        if (saveBtn) {
            const originalHTML = saveBtn.innerHTML;
            saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Saving...';
            saveBtn.disabled = true;

            setTimeout(() => {
                saveBtn.innerHTML = originalHTML;
                saveBtn.disabled = false;
                showNotification('CraneIQ configuration saved successfully!', 'success');
                console.log('Configuration saved (static data):', { dataloggers, timestamp: new Date().toISOString() });
            }, 1500);
        }
    }

    function cleanupCraneIQ() {
        console.log('Cleaning up CraneIQ...');
        dataloggers = [];
        nextLoggerId = 1;
        const buttons = ['save-btn', 'cancel-btn', 'reset-btn', 'test-btn', 
                        'upload-layout-btn', 'add-peer-btn', 'add-zone-btn', 'add-datalogger-btn'];
        buttons.forEach(btnId => {
            const btn = document.getElementById(btnId);
            if (btn?.parentNode) {
                const newBtn = btn.cloneNode(true);
                btn.parentNode.replaceChild(newBtn, btn);
            }
        });
        console.log('CraneIQ cleanup complete');
    }

    window.initCraneIQ = function() {
        console.log('Initializing CraneIQ Pro Configuration');
        try {
            initializeButtons();
            initializeToggles();
            initializeSelects();
            initializeModeButtons();
            renderLoggersTable();
            updateSummaryStats();
            console.log('CraneIQ initialized successfully - using static data');
        } catch (error) {
            console.error('Error initializing CraneIQ:', error);
            showNotification('Error initializing page', 'error');
        }
    };

    window.cleanupCraneIQ = cleanupCraneIQ;
    window.addEventListener('beforeunload', cleanupCraneIQ);
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initCraneIQ: window.initCraneIQ,
        cleanupCraneIQ: window.cleanupCraneIQ
    };
}