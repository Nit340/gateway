(function() {
    // Page-specific state
    var currentEditingCategory = null;
    
    // Log Category Configuration Data
    var logConfigs = {
        system: {
            title: "System Logs Configuration",
            subtitle: "Configure kernel, watchdog, crash reports, and system events",
            enabled: false,
            config: {
                logLevel: "INFO",
                logFormat: "TIMESTAMP LEVEL MODULE MESSAGE",
                logInterval: "1000",
                maxFileSize: "10",
                retentionDays: "30",
                includeTimestamps: true,
                includeProcessId: true,
                includeThreadId: false,
                bufferSize: "1024",
                flushInterval: "5000"
            }
        },
        network: {
            title: "Network Logs Configuration",
            subtitle: "Configure Ethernet, Wi-Fi, 4G, packet drops, and connectivity logs",
            enabled: true,
            config: {
                logLevel: "DEBUG",
                logFormat: "TIMESTAMP INTERFACE PROTOCOL SOURCE DESTINATION",
                logInterval: "5000",
                maxFileSize: "15",
                retentionDays: "14",
                includeTimestamps: true,
                includePacketData: false,
                includeInterfaceStats: true,
                bufferSize: "2048",
                flushInterval: "10000"
            }
        },
        can: {
            title: "CAN Bus Logs Configuration",
            subtitle: "Configure CAN bus communication, errors, and diagnostic messages",
            enabled: false,
            config: {
                logLevel: "WARN",
                logFormat: "TIMESTAMP CAN_ID DIRECTION DATA LENGTH",
                logInterval: "100",
                maxFileSize: "20",
                retentionDays: "7",
                includeTimestamps: true,
                includeRawData: false,
                includeErrorFrames: true,
                bufferSize: "4096",
                flushInterval: "2000"
            }
        },
        modbus: {
            title: "Modbus Logs Configuration",
            subtitle: "Configure Modbus RTU/TCP communication and protocol errors",
            enabled: false,
            config: {
                logLevel: "ERROR",
                logFormat: "TIMESTAMP DEVICE FUNCTION REGISTER VALUE",
                logInterval: "500",
                maxFileSize: "12",
                retentionDays: "14",
                includeTimestamps: true,
                includeRawBytes: false,
                includeSlaveResponses: true,
                bufferSize: "1024",
                flushInterval: "5000"
            }
        },
        mqtt: {
            title: "MQTT Logs Configuration",
            subtitle: "Configure MQTT broker connections and publish/subscribe operations",
            enabled: false,
            config: {
                logLevel: "INFO",
                logFormat: "TIMESTAMP TOPIC QOS PAYLOAD",
                logInterval: "2000",
                maxFileSize: "8",
                retentionDays: "30",
                includeTimestamps: true,
                includePayload: false,
                includeQoSDetails: true,
                bufferSize: "512",
                flushInterval: "3000"
            }
        },
        security: {
            title: "Security Logs Configuration",
            subtitle: "Configure authentication, access control, and security events",
            enabled: false,
            config: {
                logLevel: "CRITICAL",
                logFormat: "TIMESTAMP SOURCE EVENT USER RESULT",
                logInterval: "0",
                maxFileSize: "5",
                retentionDays: "90",
                includeTimestamps: true,
                includeIPAddress: true,
                includeUserAgent: false,
                bufferSize: "256",
                flushInterval: "1000"
            }
        },
        sensor: {
            title: "Sensor/GPIO Logs Configuration",
            subtitle: "Configure hardware sensor communication and GPIO operations",
            enabled: false,
            config: {
                logLevel: "INFO",
                logFormat: "TIMESTAMP SENSOR TYPE VALUE UNIT",
                logInterval: "10000",
                maxFileSize: "10",
                retentionDays: "7",
                includeTimestamps: true,
                includeRawReadings: false,
                includeCalibrationData: true,
                bufferSize: "512",
                flushInterval: "5000"
            }
        },
        ruleEngine: {
            title: "Rule Engine Logs Configuration",
            subtitle: "Configure rule execution, condition evaluation, and action triggers",
            enabled: false,
            config: {
                logLevel: "DEBUG",
                logFormat: "TIMESTAMP RULE CONDITION ACTION RESULT",
                logInterval: "1000",
                maxFileSize: "15",
                retentionDays: "14",
                includeTimestamps: true,
                includeVariableValues: false,
                includeExecutionTime: true,
                bufferSize: "1024",
                flushInterval: "3000"
            }
        },
        debug: {
            title: "Debug Logs Configuration",
            subtitle: "Configure detailed debugging information (development only)",
            enabled: false,
            config: {
                logLevel: "TRACE",
                logFormat: "TIMESTAMP FILE FUNCTION LINE MESSAGE",
                logInterval: "100",
                maxFileSize: "50",
                retentionDays: "3",
                includeTimestamps: true,
                includeStackTraces: true,
                includeMemoryInfo: true,
                bufferSize: "8192",
                flushInterval: "1000"
            }
        }
    };

    // Public API
    window.initLogging = function () {
        initializeLogging();
    };

    window.cleanupLogging = function () {
        // Clear any intervals or event listeners if needed
    };

    function initializeLogging() {
        try {
            setupEventListeners();
            fetchNetworkSettings();
        } catch (error) {
            showNotification('Error initializing logging page', 'error');
        }
    }

    async function fetchNetworkSettings() {
        try {
            const response = await fetch('/api/network/settings', { credentials: 'same-origin' });
            
            if (response.status === 401) {
                showNotification('Session expired. Please log in again.', 'error');
                return;
            }

            if (!response.ok) {
                throw new Error('Server returned ' + response.status);
            }

            const settings = await response.json();

            if (logConfigs.network) {
                logConfigs.network.enabled = settings.enabled;
                logConfigs.network.config.logLevel = settings.log_level || 'INFO';
                logConfigs.network.config.logInterval = settings.interval_ms || 1800000;
                logConfigs.network.config.maxRows = settings.max_rows;
                logConfigs.network.config.retentionDays = settings.retention_days;
                logConfigs.network.config.maxFileSize = settings.max_file_size_mb || '10';
                logConfigs.network.config.bufferSize = settings.buffer_size_kb || '64';
                logConfigs.network.config.logFormat = settings.log_format || 'TEXT';

                const intervalBadge = document.getElementById('networkIntervalBadge');
                const levelLine = document.getElementById('networkLevelLine');
                if (intervalBadge) {
                    intervalBadge.textContent = settings.enabled ? formatInterval(settings.interval_ms || 1800000) : 'OFF';
                    intervalBadge.className = settings.enabled ? 'text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded' : 'text-xs bg-gray-100 text-gray-800 px-2 py-1 rounded';
                }
                if (levelLine) {
                    levelLine.textContent = `Log Level: ${settings.log_level || 'INFO'}`;
                }
            }
        } catch (error) {
            showNotification('Failed to fetch network settings', 'error');
        }
    }

    function updateStorageProgress() {
        const storageUsed = 156; // Current usage in MB
        const maxStorageInput = document.getElementById('maxStorage');
        if (!maxStorageInput) return;

        const storageTotal = parseInt(maxStorageInput.value) || 300;
        const percentage = (storageUsed / storageTotal) * 100;

        const progressFill = document.querySelector('.storage-progress-fill');
        if (progressFill) {
            progressFill.style.width = `${percentage}%`;

            if (percentage < 70) {
                progressFill.className = 'storage-progress-fill low';
            } else if (percentage < 90) {
                progressFill.className = 'storage-progress-fill medium';
            } else {
                progressFill.className = 'storage-progress-fill high';
            }
        }
    }

    function getCategorySpecificOption(category) {
        const options = {
            'network': 'Include Packet Data',
            'can': 'Include Raw Frame Data',
            'modbus': 'Include Raw Bytes',
            'mqtt': 'Include Payload Data',
            'sensor': 'Include Raw Readings',
            'debug': 'Include Stack Traces',
            'system': 'Include Process Info',
            'security': 'Include IP Address',
            'ruleEngine': 'Include Variable Values',
            'default': 'Include Detailed Data'
        };
        return options[category] || options['default'];
    }

    function getCategorySpecificDescription(category) {
        const descriptions = {
            'network': 'Include full packet payload in logs (increases size)',
            'can': 'Include complete CAN frame data including raw bytes',
            'modbus': 'Include raw Modbus request/response bytes',
            'mqtt': 'Include MQTT message payload content',
            'sensor': 'Include unprocessed sensor readings',
            'debug': 'Include complete stack traces for debugging',
            'system': 'Include process ID and thread information',
            'security': 'Log source IP addresses for security events',
            'ruleEngine': 'Include rule variable values during execution',
            'default': 'Include detailed data in logs'
        };
        return descriptions[category] || descriptions['default'];
    }

    function getCategorySpecificValue(category) {
        const config = logConfigs[category]?.config;
        if (!config) return '';

        const values = {
            'network': config.includePacketData,
            'can': config.includeRawData,
            'modbus': config.includeRawBytes,
            'mqtt': config.includePayload,
            'sensor': config.includeRawReadings,
            'debug': config.includeStackTraces,
            'system': config.includeProcessId || config.includeThreadId,
            'security': config.includeIPAddress,
            'ruleEngine': config.includeVariableValues,
            'default': false
        };

        const value = values[category] || values['default'];
        return value ? 'checked' : '';
    }

    function getDebugOptionName(category) {
        const options = {
            'network': 'Include Interface Statistics',
            'can': 'Include Error Frames',
            'modbus': 'Include Slave Responses',
            'mqtt': 'Include QoS Details',
            'sensor': 'Include Calibration Data',
            'debug': 'Include Memory Info',
            'system': 'Include Thread IDs',
            'security': 'Include User Agent',
            'ruleEngine': 'Include Execution Time',
            'default': 'Include Debug Information'
        };
        return options[category] || options['default'];
    }

    function getDebugOptionDescription(category) {
        const descriptions = {
            'network': 'Include network interface statistics and counters',
            'can': 'Log all CAN error frames and bus errors',
            'modbus': 'Include detailed Modbus slave responses',
            'mqtt': 'Include MQTT Quality of Service level details',
            'sensor': 'Include sensor calibration and accuracy data',
            'debug': 'Include memory usage and allocation information',
            'system': 'Include thread identification in logs',
            'security': 'Include user agent/browser information',
            'ruleEngine': 'Include rule execution timing information',
            'default': 'Include additional debugging information'
        };
        return descriptions[category] || descriptions['default'];
    }

    function getDebugOptionValue(category) {
        const config = logConfigs[category]?.config;
        if (!config) return '';

        const values = {
            'network': config.includeInterfaceStats,
            'can': config.includeErrorFrames,
            'modbus': config.includeSlaveResponses,
            'mqtt': config.includeQoSDetails,
            'sensor': config.includeCalibrationData,
            'debug': config.includeMemoryInfo,
            'system': config.includeThreadId,
            'security': config.includeUserAgent,
            'ruleEngine': config.includeExecutionTime,
            'default': false
        };

        const value = values[category] || values['default'];
        return value ? 'checked' : '';
    }

    function openLogConfigModal(categoryId) {
        currentEditingCategory = categoryId;
        const config = logConfigs[categoryId];
        if (!config) return;

        const titleElement = document.getElementById('logConfigTitle');
        const subtitleElement = document.getElementById('logConfigSubtitle');
        if (titleElement) titleElement.textContent = config.title;
        if (subtitleElement) subtitleElement.textContent = config.subtitle;

        const container = document.getElementById('configContainer');
        if (!container) return;

        container.innerHTML = '';

        const enabledDiv = document.createElement('div');
        enabledDiv.className = 'config-item';
        enabledDiv.innerHTML = `
            <div class="flex items-center justify-between">
                <div>
                    <div class="config-label">Enable Logging</div>
                    <div class="config-description">Turn logging on/off for this category</div>
                </div>
                <label class="toggle-switch">
                    <input type="checkbox" id="modalEnabled" ${config.enabled ? 'checked' : ''}>
                    <span class="toggle-slider"></span>
                </label>
            </div>
        `;
        container.appendChild(enabledDiv);

        const basicGroup = document.createElement('div');
        basicGroup.className = 'config-group';
        basicGroup.innerHTML = `<h3 class="text-sm font-semibold text-slate-900 mb-3">Basic Settings</h3>`;

        const levelOptions = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'TRACE'];
        basicGroup.innerHTML += `
            <div class="config-item">
                <div class="config-label">Log Level</div>
                <select class="w-full compact-select" id="modalLogLevel">
                    ${levelOptions.map(level => `<option value="${level}" ${config.config.logLevel === level ? 'selected' : ''}>${level}</option>`).join('')}
                </select>
                <div class="config-description">Minimum severity level to log</div>
            </div>
        `;

        const formatOptions = [
            { value: 'TIMESTAMP LEVEL MODULE MESSAGE', label: 'Standard (Timestamp + Level + Module + Message)' },
            { value: 'TIMESTAMP LEVEL MESSAGE', label: 'Basic (Timestamp + Level + Message)' },
            { value: 'TIMESTAMP MESSAGE', label: 'Simple (Timestamp + Message)' },
            { value: 'LEVEL MODULE MESSAGE', label: 'Compact (Level + Module + Message - No Timestamp)' },
            { value: 'MODULE MESSAGE', label: 'Minimal (Module + Message)' }
        ];

        basicGroup.innerHTML += `
            <div class="config-item">
                <div class="config-label">Log Format</div>
                <select class="w-full compact-select" id="modalLogFormat">
                    ${formatOptions.map(format => `<option value="${format.value}" ${config.config.logFormat === format.value ? 'selected' : ''}>${format.label}</option>`).join('')}
                </select>
                <div class="config-description">Structure of each log entry</div>
            </div>
        `;

        basicGroup.innerHTML += `
            <div class="config-item">
                <div class="config-label">Log Interval (ms)</div>
                <div class="flex items-center space-x-3">
                    <input type="number" min="0" max="86400000" value="${config.config.logInterval}" class="compact-input flex-1" id="modalLogInterval">
                    <span class="text-sm text-slate-600">ms (0 = real-time)</span>
                </div>
                <div class="config-description">How often to write logs (0 = immediate)</div>
            </div>
        `;
        container.appendChild(basicGroup);

        const advancedGroup = document.createElement('div');
        advancedGroup.className = 'config-group';
        advancedGroup.innerHTML = `<h3 class="text-sm font-semibold text-slate-900 mb-3">Advanced Settings</h3>`;

        advancedGroup.innerHTML += `
            <div class="config-item">
                <div class="config-label">Max File Size</div>
                <div class="flex items-center space-x-3">
                    <input type="number" min="1" max="100" value="${config.config.maxFileSize}" class="compact-input flex-1" id="modalMaxFileSize">
                    <span class="text-sm text-slate-600">MB</span>
                </div>
                <div class="config-description">Maximum size of individual log files</div>
            </div>
        `;

        advancedGroup.innerHTML += `
            <div class="config-item">
                <div class="config-label">Retention Period</div>
                <div class="flex items-center space-x-3">
                    <input type="number" min="1" max="365" value="${config.config.retentionDays}" class="compact-input flex-1" id="modalRetentionDays">
                    <span class="text-sm text-slate-600">days</span>
                </div>
                <div class="config-description">How long to keep logs before deletion</div>
            </div>
        `;

        advancedGroup.innerHTML += `
            <div class="config-item">
                <div class="config-label">Buffer Size</div>
                <div class="flex items-center space-x-3">
                    <input type="number" min="128" max="16384" value="${config.config.bufferSize}" class="compact-input flex-1" id="modalBufferSize">
                    <span class="text-sm text-slate-600">KB</span>
                </div>
                <div class="config-description">Memory buffer for log entries before writing to disk</div>
            </div>
        `;

        advancedGroup.innerHTML += `
            <div class="config-item">
                <div class="config-label">Flush Interval</div>
                <div class="flex items-center space-x-3">
                    <input type="number" min="100" max="30000" value="${config.config.flushInterval}" class="compact-input flex-1" id="modalFlushInterval">
                    <span class="text-sm text-slate-600">ms</span>
                </div>
                <div class="config-description">How often to flush buffer to disk</div>
            </div>
        `;
        container.appendChild(advancedGroup);

        // Options group removed

        const modal = document.getElementById('logConfigModal');
        if (modal) modal.classList.add('active');

        // Disable enable toggle for non-network categories
        if (categoryId !== 'network') {
            const modalEnabled = document.getElementById('modalEnabled');
            if (modalEnabled) {
                modalEnabled.checked = false;
                modalEnabled.disabled = true;
                const desc = modalEnabled.closest('.flex').querySelector('.config-description');
                if (desc) desc.innerHTML = '<span class="text-red-500 font-medium">This log category is not available.</span>';
            }
        }
    }

    function closeLogConfigModal() {
        const modal = document.getElementById('logConfigModal');
        if (modal) modal.classList.remove('active');
        currentEditingCategory = null;
    }

    function saveLogConfig() {
        if (!currentEditingCategory) return;
        const config = logConfigs[currentEditingCategory];
        if (!config) return;

        const modalEnabled = document.getElementById('modalEnabled');
        const modalLogLevel = document.getElementById('modalLogLevel');
        const modalLogFormat = document.getElementById('modalLogFormat');
        const modalLogInterval = document.getElementById('modalLogInterval');
        const modalMaxFileSize = document.getElementById('modalMaxFileSize');
        const modalRetentionDays = document.getElementById('modalRetentionDays');
        const modalBufferSize = document.getElementById('modalBufferSize');
        const modalFlushInterval = document.getElementById('modalFlushInterval');

        if (modalEnabled) config.enabled = modalEnabled.checked;
        if (modalLogLevel) config.config.logLevel = modalLogLevel.value;
        if (modalLogFormat) config.config.logFormat = modalLogFormat.value;
        if (modalLogInterval) config.config.logInterval = modalLogInterval.value;
        if (modalMaxFileSize) config.config.maxFileSize = modalMaxFileSize.value;
        if (modalRetentionDays) config.config.retentionDays = modalRetentionDays.value;
        if (modalBufferSize) config.config.bufferSize = modalBufferSize.value;
        if (modalFlushInterval) config.config.flushInterval = modalFlushInterval.value;

        const detailedDataChecked = document.getElementById('modalIncludeDetailedData')?.checked;
        const debugInfoChecked = document.getElementById('modalIncludeDebugInfo')?.checked;

        switch (currentEditingCategory) {
            case 'network': config.config.includePacketData = detailedDataChecked; config.config.includeInterfaceStats = debugInfoChecked; break;
            case 'can': config.config.includeRawData = detailedDataChecked; config.config.includeErrorFrames = debugInfoChecked; break;
            case 'modbus': config.config.includeRawBytes = detailedDataChecked; config.config.includeSlaveResponses = debugInfoChecked; break;
            case 'mqtt': config.config.includePayload = detailedDataChecked; config.config.includeQoSDetails = debugInfoChecked; break;
            case 'sensor': config.config.includeRawReadings = detailedDataChecked; config.config.includeCalibrationData = debugInfoChecked; break;
            case 'debug': config.config.includeStackTraces = detailedDataChecked; config.config.includeMemoryInfo = debugInfoChecked; break;
            case 'system': config.config.includeProcessId = detailedDataChecked; config.config.includeThreadId = debugInfoChecked; break;
            case 'security': config.config.includeIPAddress = detailedDataChecked; config.config.includeUserAgent = debugInfoChecked; break;
            case 'ruleEngine': config.config.includeVariableValues = detailedDataChecked; config.config.includeExecutionTime = debugInfoChecked; break;
        }

        updateCategoryBadge(currentEditingCategory);
        updateIntervalDisplay(currentEditingCategory);

        if (currentEditingCategory === 'network') {
            syncNetworkSettingsWithAPI(config);
        } else {
            if (modalEnabled && modalEnabled.checked) {
                showNotification('This log category is not available', 'error');
                modalEnabled.checked = false;
                config.enabled = false;
                return;
            }
            showNotification(`Configuration saved for ${config.title}`, 'success');
            closeLogConfigModal();
        }
    }

    async function syncNetworkSettingsWithAPI(config) {
        try {
            const payload = {
                enabled: config.enabled,
                log_level: config.config.logLevel,
                interval_ms: parseInt(config.config.logInterval || 1800000),
                max_rows: parseInt(config.config.maxRows || 10000),
                retention_days: parseInt(config.config.retentionDays || 14),
                max_file_size_mb: parseInt(config.config.maxFileSize || 10),
                buffer_size_kb: parseInt(config.config.bufferSize || 64),
                log_format: config.config.logFormat || 'TEXT',
                flush_interval_ms: parseInt(config.config.flushInterval || 250)
            };

            const response = await fetch('/api/network/settings', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify(payload)
            });

            if (response.status === 401) {
                showNotification('Session expired. Please log in again.', 'error');
                return;
            }

            const result = await response.json();
            if (result.success) {
                const intervalBadge = document.getElementById('networkIntervalBadge');
                const levelLine = document.getElementById('networkLevelLine');
                if (intervalBadge) {
                    intervalBadge.textContent = config.enabled ? formatInterval(config.config.logInterval) : 'OFF';
                    intervalBadge.className = config.enabled ? 'text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded' : 'text-xs bg-gray-100 text-gray-800 px-2 py-1 rounded';
                }
                if (levelLine) {
                    levelLine.textContent = `Log Level: ${config.config.logLevel}`;
                }
                showNotification(`Network monitor configuration saved`, 'success');
                closeLogConfigModal();
            } else {
                showNotification(`Error: ${result.error}`, 'error');
            }
        } catch (error) {
            showNotification('Failed to save network settings to server', 'error');
        }
    }

    function updateCategoryBadge(categoryId) {
        if (categoryId === 'network') return;
        const config = logConfigs[categoryId];
        if (!config) return;

        const button = document.querySelector(`.configure-log-btn[data-category="${categoryId}"]`);
        if (!button) return;

        const card = button.closest('.p-3');
        if (!card) return;

        const badge = card.querySelector('span.bg-');
        if (badge) {
            const level = config.config.logLevel;
            let bgColor = 'gray';
            let text = 'OFF';

            if (config.enabled) {
                switch (level) {
                    case 'CRITICAL': bgColor = 'purple'; text = 'CRITICAL'; break;
                    case 'ERROR': bgColor = 'red'; text = 'ERROR'; break;
                    case 'WARNING': bgColor = 'yellow'; text = 'WARN'; break;
                    case 'INFO': bgColor = 'blue'; text = 'INFO'; break;
                    case 'DEBUG': bgColor = 'green'; text = 'DEBUG'; break;
                    case 'TRACE': bgColor = 'gray'; text = 'TRACE'; break;
                }
            }

            badge.className = `text-xs bg-${bgColor}-100 text-${bgColor}-800 px-2 py-1 rounded`;
            badge.textContent = text;
        }
    }

    function updateIntervalDisplay(categoryId) {
        if (categoryId === 'network') return;
        const config = logConfigs[categoryId];
        if (!config) return;

        const button = document.querySelector(`.configure-log-btn[data-category="${categoryId}"]`);
        if (!button) return;

        const card = button.closest('.p-3');
        if (!card) return;

        const intervalDisplay = card.querySelector('.text-xs:last-of-type');
        if (intervalDisplay) {
            const interval = config.config.logInterval;
            if (interval === '0') {
                intervalDisplay.innerHTML = '<i class="fa-solid fa-clock mr-1"></i> Interval: Real-time';
            } else {
                intervalDisplay.innerHTML = `<i class="fa-solid fa-clock mr-1"></i> Interval: ${formatInterval(interval)}`;
            }
        }
    }

    function formatInterval(ms) {
        const num = parseInt(ms);
        return num >= 1000 ? `${num / 1000}s` : `${ms}ms`;
    }

    function applyGlobalSettings() {
        const globalLevel = document.getElementById('globalLogLevel');
        if (!globalLevel) return;

        if (confirm('Apply global log level to all categories? This will override individual settings.')) {
            const level = globalLevel.value.toUpperCase();
            Object.keys(logConfigs).forEach(categoryId => {
                const config = logConfigs[categoryId];
                if (config && config.enabled) {
                    config.config.logLevel = level;
                    updateCategoryBadge(categoryId);
                }
            });
            showNotification('Global settings applied to all enabled categories.', 'success');
        }
    }

    function showNotification(message, type = 'info') {
        if (typeof window._commonShowNotification === 'function') {
            window._commonShowNotification(message, type);
            return;
        }

        const colors = { success: '#16A34A', error: '#DC2626', info: '#2563EB', warning: '#D97706' };
        const icons = { success: 'fa-check-circle', error: 'fa-circle-xmark', info: 'fa-circle-info', warning: 'fa-triangle-exclamation' };

        const existing = document.querySelectorAll('.logging-toast');
        if (existing.length > 3) existing[0].remove();

        const t = document.createElement('div');
        t.className = 'logging-toast';
        t.style.cssText = `
            position:fixed; bottom:24px; right:24px; z-index:99999;
            background:${colors[type] || colors.info}; color:white;
            padding:12px 20px; border-radius:8px; font-size:14px; font-weight:500;
            box-shadow:0 4px 16px rgba(0,0,0,0.25); display:flex; align-items:center;
            gap:10px; min-width:240px; max-width:360px; pointer-events:none;
            transition:opacity 0.3s ease, transform 0.3s ease;
        `;
        const iconClass = icons[type] || icons.info;
        t.innerHTML = `<i class="fa-solid ${iconClass}" style="font-size:16px;"></i><span>${String(message).replace(/</g, '&lt;')}</span>`;
        document.body.appendChild(t);

        setTimeout(() => {
            t.style.opacity = '0';
            t.style.transform = 'translateX(20px)';
            setTimeout(() => t.remove(), 300);
        }, 3500);
    }

    function setupEventListeners() {
        document.querySelectorAll('.configure-log-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const categoryId = btn.dataset.category;
                openLogConfigModal(categoryId);
            });
        });

        const cancelModal = document.getElementById('cancelConfigBtn');
        const closeModal = document.getElementById('closeLogConfigModal');
        if (cancelModal) cancelModal.addEventListener('click', closeLogConfigModal);
        if (closeModal) closeModal.addEventListener('click', closeLogConfigModal);

        const saveBtn = document.getElementById('saveConfigBtn');
        if (saveBtn) saveBtn.addEventListener('click', saveLogConfig);

        const applyGlobalBtn = document.getElementById('applyGlobalSettings');
        if (applyGlobalBtn) applyGlobalBtn.addEventListener('click', applyGlobalSettings);
    }
})();