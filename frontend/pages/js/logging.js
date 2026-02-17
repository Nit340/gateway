// This function will be called by the router when loading the page
window.initLogging = function() {
    console.log('Device Logging page initialized');
    
    // Initialize all functionality for this page
    initializeLogging();
};

function initializeLogging() {
    console.log('Setting up Device Logging page functionality');
    
    try {
        // Initialize all logging components
        setupEventListeners();
        updateStorageProgress();
        
        console.log('Device Logging page setup complete');
    } catch (error) {
        console.error('Error in initializeLogging:', error);
        // Show notification if needed
        showNotification('Error initializing logging page', 'error');
    }
}

// Log Category Configuration Data
const logConfigs = {
    system: {
        title: "System Logs Configuration",
        subtitle: "Configure kernel, watchdog, crash reports, and system events",
        enabled: true,
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
        enabled: true,
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
        enabled: true,
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
        enabled: true,
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
        enabled: true,
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

// Current editing category
let currentEditingCategory = null;

// Update storage progress bar
function updateStorageProgress() {
    const storageUsed = 156; // Current usage in MB
    const maxStorageInput = document.getElementById('maxStorage');
    if (!maxStorageInput) return;
    
    const storageTotal = parseInt(maxStorageInput.value) || 300;
    const percentage = (storageUsed / storageTotal) * 100;
    
    const progressFill = document.querySelector('.storage-progress-fill');
    if (progressFill) {
        progressFill.style.width = `${percentage}%`;
        
        // Update color based on percentage
        if (percentage < 70) {
            progressFill.className = 'storage-progress-fill low';
        } else if (percentage < 90) {
            progressFill.className = 'storage-progress-fill medium';
        } else {
            progressFill.className = 'storage-progress-fill high';
        }
    }
}

// Helper functions for category-specific options
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

// Open log configuration modal
function openLogConfigModal(categoryId) {
    currentEditingCategory = categoryId;
    const config = logConfigs[categoryId];
    if (!config) return;
    
    // Update modal title
    const titleElement = document.getElementById('logConfigTitle');
    const subtitleElement = document.getElementById('logConfigSubtitle');
    if (titleElement) titleElement.textContent = config.title;
    if (subtitleElement) subtitleElement.textContent = config.subtitle;
    
    // Build configuration form
    const container = document.getElementById('configContainer');
    if (!container) return;
    
    container.innerHTML = '';
    
    // Enabled toggle
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
    
    // Basic Settings Group
    const basicGroup = document.createElement('div');
    basicGroup.className = 'config-group';
    basicGroup.innerHTML = `
        <h3 class="text-sm font-semibold text-slate-900 mb-3">Basic Settings</h3>
    `;
    
    // Log Level
    const levelOptions = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'TRACE'];
    basicGroup.innerHTML += `
        <div class="config-item">
            <div class="config-label">Log Level</div>
            <select class="w-full compact-select" id="modalLogLevel">
                ${levelOptions.map(level => 
                    `<option value="${level}" ${config.config.logLevel === level ? 'selected' : ''}>${level}</option>`
                ).join('')}
            </select>
            <div class="config-description">Minimum severity level to log</div>
        </div>
    `;
    
    // Log Format
    const formatOptions = [
        {value: 'TIMESTAMP LEVEL MODULE MESSAGE', label: 'Standard (Timestamp + Level + Module + Message)'},
        {value: 'TIMESTAMP LEVEL MESSAGE', label: 'Basic (Timestamp + Level + Message)'},
        {value: 'TIMESTAMP MESSAGE', label: 'Simple (Timestamp + Message)'},
        {value: 'LEVEL MODULE MESSAGE', label: 'Compact (Level + Module + Message - No Timestamp)'},
        {value: 'MODULE MESSAGE', label: 'Minimal (Module + Message)'}
    ];
    
    basicGroup.innerHTML += `
        <div class="config-item">
            <div class="config-label">Log Format</div>
            <select class="w-full compact-select" id="modalLogFormat">
                ${formatOptions.map(format => 
                    `<option value="${format.value}" ${config.config.logFormat === format.value ? 'selected' : ''}>
                        ${format.label}
                    </option>`
                ).join('')}
            </select>
            <div class="config-description">Structure of each log entry</div>
        </div>
    `;
    
    // Log Interval
    basicGroup.innerHTML += `
        <div class="config-item">
            <div class="config-label">Log Interval (ms)</div>
            <div class="flex items-center space-x-3">
                <input type="number" min="0" max="60000" value="${config.config.logInterval}" class="compact-input flex-1" id="modalLogInterval">
                <span class="text-sm text-slate-600">ms (0 = real-time)</span>
            </div>
            <div class="config-description">How often to write logs (0 = immediate)</div>
        </div>
    `;
    
    container.appendChild(basicGroup);
    
    // Advanced Settings Group
    const advancedGroup = document.createElement('div');
    advancedGroup.className = 'config-group';
    advancedGroup.innerHTML = `
        <h3 class="text-sm font-semibold text-slate-900 mb-3">Advanced Settings</h3>
    `;
    
    // Max File Size
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
    
    // Retention Days
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
    
    // Buffer Size
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
    
    // Flush Interval
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
    
    // Category-Specific Options Group
    const optionsGroup = document.createElement('div');
    optionsGroup.className = 'config-group';
    optionsGroup.innerHTML = `
        <h3 class="text-sm font-semibold text-slate-900 mb-3">Additional Information</h3>
        <div class="space-y-3">
            <!-- Category-specific detailed data option -->
            <div class="flex items-center justify-between">
                <div>
                    <div class="config-label">${getCategorySpecificOption(categoryId)}</div>
                    <div class="config-description">${getCategorySpecificDescription(categoryId)}</div>
                </div>
                <label class="toggle-switch">
                    <input type="checkbox" id="modalIncludeDetailedData" ${getCategorySpecificValue(categoryId)}>
                    <span class="toggle-slider"></span>
                </label>
            </div>
            
            <!-- Category-specific debug option -->
            <div class="flex items-center justify-between">
                <div>
                    <div class="config-label">${getDebugOptionName(categoryId)}</div>
                    <div class="config-description">${getDebugOptionDescription(categoryId)}</div>
                </div>
                <label class="toggle-switch">
                    <input type="checkbox" id="modalIncludeDebugInfo" ${getDebugOptionValue(categoryId)}>
                    <span class="toggle-slider"></span>
                </label>
            </div>
        </div>
    `;
    container.appendChild(optionsGroup);
    
    // Show modal
    const modal = document.getElementById('logConfigModal');
    if (modal) modal.classList.add('active');
}

// Close log configuration modal
function closeLogConfigModal() {
    const modal = document.getElementById('logConfigModal');
    if (modal) modal.classList.remove('active');
    currentEditingCategory = null;
}

// Save configuration from modal
function saveLogConfig() {
    if (!currentEditingCategory) return;
    
    const config = logConfigs[currentEditingCategory];
    if (!config) return;
    
    // Update configuration
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
    
    // Update category-specific options
    const detailedDataChecked = document.getElementById('modalIncludeDetailedData')?.checked;
    const debugInfoChecked = document.getElementById('modalIncludeDebugInfo')?.checked;
    
    // Update the specific config properties based on category
    switch(currentEditingCategory) {
        case 'network':
            config.config.includePacketData = detailedDataChecked;
            config.config.includeInterfaceStats = debugInfoChecked;
            break;
        case 'can':
            config.config.includeRawData = detailedDataChecked;
            config.config.includeErrorFrames = debugInfoChecked;
            break;
        case 'modbus':
            config.config.includeRawBytes = detailedDataChecked;
            config.config.includeSlaveResponses = debugInfoChecked;
            break;
        case 'mqtt':
            config.config.includePayload = detailedDataChecked;
            config.config.includeQoSDetails = debugInfoChecked;
            break;
        case 'sensor':
            config.config.includeRawReadings = detailedDataChecked;
            config.config.includeCalibrationData = debugInfoChecked;
            break;
        case 'debug':
            config.config.includeStackTraces = detailedDataChecked;
            config.config.includeMemoryInfo = debugInfoChecked;
            break;
        case 'system':
            config.config.includeProcessId = detailedDataChecked;
            config.config.includeThreadId = debugInfoChecked;
            break;
        case 'security':
            config.config.includeIPAddress = detailedDataChecked;
            config.config.includeUserAgent = debugInfoChecked;
            break;
        case 'ruleEngine':
            config.config.includeVariableValues = detailedDataChecked;
            config.config.includeExecutionTime = debugInfoChecked;
            break;
    }
    
    // Update the checkbox on main page
    const mainCheckbox = document.getElementById(`${currentEditingCategory}Logs`);
    if (mainCheckbox) {
        mainCheckbox.checked = config.enabled;
    }
    
    // Update badge on main page
    updateCategoryBadge(currentEditingCategory);
    
    // Update interval display
    updateIntervalDisplay(currentEditingCategory);
    
    showNotification(`Configuration saved for ${config.title}`, 'success');
    closeLogConfigModal();
}

// Update category badge
function updateCategoryBadge(categoryId) {
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
            switch(level) {
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

// Update interval display
function updateIntervalDisplay(categoryId) {
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

// Format interval for display
function formatInterval(ms) {
    const num = parseInt(ms);
    if (num >= 1000) {
        return `${num/1000}s`;
    }
    return `${ms}ms`;
}

// Apply global settings to all categories
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

// Show notification
function showNotification(message, type = 'info') {
    // Use common.js notification function if available
    if (typeof window.showNotification === 'function') {
        window.showNotification(message, type);
    } else {
        // Fallback simple notification
        alert(`${type.toUpperCase()}: ${message}`);
    }
}

// Setup event listeners
function setupEventListeners() {
    // Master controls
    const enableLogging = document.getElementById('enableLogging');
    if (enableLogging) {
        enableLogging.addEventListener('change', function() {
            console.log('Logging enabled:', this.checked);
        });
    }
    
    const globalLogLevel = document.getElementById('globalLogLevel');
    if (globalLogLevel) {
        globalLogLevel.addEventListener('change', function() {
            console.log('Global log level changed to:', this.value);
        });
    }
    
    const maxStorage = document.getElementById('maxStorage');
    if (maxStorage) {
        maxStorage.addEventListener('input', updateStorageProgress);
    }
    
    // Configure log buttons
    document.querySelectorAll('.configure-log-btn').forEach(button => {
        button.addEventListener('click', function() {
            const category = this.getAttribute('data-category');
            openLogConfigModal(category);
        });
    });
    
    // Log categories quick actions
    const selectAllLogs = document.getElementById('selectAllLogs');
    if (selectAllLogs) {
        selectAllLogs.addEventListener('click', function() {
            document.querySelectorAll('#logCategories input[type="checkbox"]').forEach(cb => {
                cb.checked = true;
            });
        });
    }
    
    const deselectAllLogs = document.getElementById('deselectAllLogs');
    if (deselectAllLogs) {
        deselectAllLogs.addEventListener('click', function() {
            document.querySelectorAll('#logCategories input[type="checkbox"]').forEach(cb => {
                cb.checked = false;
            });
        });
    }
    
    const applyGlobalSettingsBtn = document.getElementById('applyGlobalSettings');
    if (applyGlobalSettingsBtn) {
        applyGlobalSettingsBtn.addEventListener('click', applyGlobalSettings);
    }
    
    // Configuration modal controls
    const closeLogConfigModalBtn = document.getElementById('closeLogConfigModal');
    if (closeLogConfigModalBtn) {
        closeLogConfigModalBtn.addEventListener('click', closeLogConfigModal);
    }
    
    const cancelConfigBtn = document.getElementById('cancelConfigBtn');
    if (cancelConfigBtn) {
        cancelConfigBtn.addEventListener('click', closeLogConfigModal);
    }
    
    const saveConfigBtn = document.getElementById('saveConfigBtn');
    if (saveConfigBtn) {
        saveConfigBtn.addEventListener('click', saveLogConfig);
    }
    
    // Footer buttons
    const testLoggingBtn = document.getElementById('testLoggingBtn');
    if (testLoggingBtn) {
        testLoggingBtn.addEventListener('click', function() {
            const btn = this;
            const original = btn.innerHTML;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Testing...';
            btn.disabled = true;
            
            setTimeout(() => {
                btn.innerHTML = original;
                btn.disabled = false;
                showNotification('Logging configuration test successful! All destinations are reachable.', 'success');
            }, 2000);
        });
    }
    
    const rotateNowBtn = document.getElementById('rotateNowBtn');
    if (rotateNowBtn) {
        rotateNowBtn.addEventListener('click', function() {
            if (confirm('Rotate logs now? Current logs will be archived.')) {
                const btn = this;
                const original = btn.innerHTML;
                btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Rotating...';
                btn.disabled = true;
                
                setTimeout(() => {
                    btn.innerHTML = original;
                    btn.disabled = false;
                    showNotification('Log rotation complete! Old logs have been archived.', 'success');
                }, 1500);
            }
        });
    }
    
    // Save buttons
    const footerSaveBtn = document.getElementById('footer-save-btn');
    if (footerSaveBtn) {
        footerSaveBtn.addEventListener('click', saveAllConfigurations);
    }
    
    // Cancel buttons
    const footerCancelBtn = document.getElementById('footer-cancel-btn');
    if (footerCancelBtn) {
        footerCancelBtn.addEventListener('click', function() {
            if (confirm('Discard all unsaved changes?')) {
                // Navigate back to general configuration
                if (window.router && typeof window.router.navigateTo === 'function') {
                    window.router.navigateTo('general-configuration');
                } else {
                    showNotification('Changes discarded', 'info');
                }
            }
        });
    }
    
    // Reset to default button
    const resetToDefaultBtn = document.getElementById('resetToDefaultBtn');
    if (resetToDefaultBtn) {
        resetToDefaultBtn.addEventListener('click', function() {
            if (confirm('Reset all logging settings to default values?')) {
                showNotification('Settings reset to defaults. Please save to apply.', 'info');
            }
        });
    }
    
    // Restart logger button
    const restartLoggerBtn = document.getElementById('restartLoggerBtn');
    if (restartLoggerBtn) {
        restartLoggerBtn.addEventListener('click', function() {
            if (confirm('Restart the logging service? This will temporarily pause logging.')) {
                const btn = this;
                const original = btn.innerHTML;
                btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Restarting...';
                btn.disabled = true;
                
                setTimeout(() => {
                    btn.innerHTML = original;
                    btn.disabled = false;
                    showNotification('Logging service restarted successfully.', 'success');
                }, 2000);
            }
        });
    }
}

// Save all configurations
function saveAllConfigurations() {
    const btn = document.getElementById('footer-save-btn');
    if (!btn) return;
    
    const original = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Saving...';
    btn.disabled = true;
    
    setTimeout(() => {
        btn.innerHTML = original;
        btn.disabled = false;
        
        // Collect all configurations
        const allConfig = {
            global: {
                enabled: document.getElementById('enableLogging')?.checked || false,
                logLevel: document.getElementById('globalLogLevel')?.value || 'info',
                maxStorage: document.getElementById('maxStorage')?.value || '300',
                rotationMode: document.getElementById('rotationMode')?.value || 'fifo-compress',
            },
            categories: logConfigs,
            destinations: {
                local: document.getElementById('localStorage')?.checked || false,
                usb: document.getElementById('usbStorage')?.checked || false,
                cloud: document.getElementById('cloudEndpoint')?.value || '',
                syslog: document.getElementById('syslogServer')?.value || '',
                mqttTopic: document.getElementById('mqttTopic')?.value || '',
                webSocket: document.getElementById('webSocketStreaming')?.checked || false
            },
            rotation: {
                maxFileSize: document.getElementById('maxFileSize')?.value || '20',
                maxFiles: document.getElementById('maxLogFiles')?.value || '10',
                compress: document.getElementById('compressLogs')?.checked || false,
                deleteOldest: document.getElementById('deleteOldest')?.checked || false
            }
        };
        
        console.log('Saving all configurations:', allConfig);
        showNotification('All logging configurations saved successfully!\n\nChanges will take effect after the logging service restarts.', 'success');
    }, 1000);
}

// Cleanup function for router
function cleanupLogging() {
    console.log('Cleaning up logging page resources');
    // Clear any intervals or event listeners if needed
}

// Export for global access
window.cleanupLogging = cleanupLogging;