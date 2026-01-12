// general-config.js - Clean and fixed version

// Helper functions
function setInputValue(selector, value) {
    if (value === undefined || value === null) return;
    const element = document.querySelector(selector);
    if (element) element.value = value;
}

function setRadioValue(selector, value) {
    if (value === undefined || value === null) return;
    const radios = document.querySelectorAll(selector);
    radios.forEach(radio => {
        if (radio.value === value) {
            radio.checked = true;
            radio.dispatchEvent(new Event('change'));
        }
    });
}

function setSelectValue(selector, value) {
    if (value === undefined || value === null) return;
    const select = document.querySelector(selector);
    if (select) {
        for (let i = 0; i < select.options.length; i++) {
            if (select.options[i].value === value) {
                select.selectedIndex = i;
                break;
            }
        }
    }
}

function getInputValue(selector) {
    const element = document.querySelector(selector);
    return element ? element.value : '';
}

function getRadioValue(selector) {
    const radio = document.querySelector(selector + ':checked');
    return radio ? radio.value : '';
}

function getSelectValue(selector) {
    const select = document.querySelector(selector);
    return select ? select.options[select.selectedIndex].value : '';
}

// Network Toggle Functions
function initializeNetworkToggles() {
    const networkModeRadios = document.querySelectorAll('input[name="network-mode"]');
    networkModeRadios.forEach(radio => {
        radio.addEventListener('change', toggleNetworkConfig);
    });
    
    const ipAssignmentRadios = document.querySelectorAll('input[name="ip-assignment"]');
    ipAssignmentRadios.forEach(radio => {
        radio.addEventListener('change', toggleIPAssignment);
    });
    
    toggleNetworkConfig();
    toggleIPAssignment();
}

function toggleNetworkConfig() {
    const networkMode = document.querySelector('input[name="network-mode"]:checked');
    if (!networkMode) return;
    
    const mode = networkMode.value;
    const ethernetConfig = document.getElementById('ethernet-config');
    const wifiConfig = document.getElementById('wifi-config');
    const cellularConfig = document.getElementById('cellular-config');
    
    if (ethernetConfig) ethernetConfig.style.display = 'none';
    if (wifiConfig) wifiConfig.style.display = 'none';
    if (cellularConfig) cellularConfig.style.display = 'none';
    
    if (mode === 'ethernet' && ethernetConfig) {
        ethernetConfig.style.display = 'block';
    } else if (mode === 'wifi' && wifiConfig) {
        wifiConfig.style.display = 'block';
    } else if (mode === 'lte' && cellularConfig) {
        cellularConfig.style.display = 'block';
    }
}

function toggleIPAssignment() {
    const ipAssignment = document.querySelector('input[name="ip-assignment"]:checked');
    const staticConfig = document.getElementById('static-ip-config');
    
    if (!staticConfig) return;
    
    if (ipAssignment && ipAssignment.value === 'static') {
        staticConfig.classList.remove('hidden');
    } else {
        staticConfig.classList.add('hidden');
    }
}

// WiFi Signal Functions
function updateWiFiSignalStrength(strength) {
    const signalBars = document.querySelectorAll('#wifi-config .signal-bar');
    if (!signalBars.length) return;
    
    // Reset all bars
    signalBars.forEach(bar => {
        bar.className = 'signal-bar none';
    });
    
    // Activate bars based on strength (0-4)
    const effectiveStrength = Math.min(Math.max(strength, 0), 4);
    
    for (let i = 0; i <= effectiveStrength; i++) {
        if (i < signalBars.length) {
            const bar = signalBars[i];
            if (i === 0) bar.className = 'signal-bar poor';
            else if (i === 1) bar.className = 'signal-bar fair';
            else if (i === 2) bar.className = 'signal-bar good';
            else if (i === 3) bar.className = 'signal-bar good';
            else if (i === 4) bar.className = 'signal-bar excellent';
        }
    }
}

function getSignalStrengthText(strength) {
    const strengthTexts = ['None', 'Poor', 'Fair', 'Good', 'Excellent'];
    return strengthTexts[Math.min(Math.max(strength, 0), 4)] || 'Unknown';
}

function updateWiFiSignalDisplay(strength) {
    const wifiConfig = document.getElementById('wifi-config');
    if (!wifiConfig || wifiConfig.style.display === 'none') {
        return;
    }
    
    updateWiFiSignalStrength(strength);
    
    // Update strength text
    const strengthText = getSignalStrengthText(strength);
    const strengthSpans = wifiConfig.querySelectorAll('.signal-strength + span, .signal-strength + .ml-2');
    strengthSpans.forEach(span => {
        if (!span.querySelector('i')) {
            span.textContent = strengthText;
        }
    });
}

// Notification System
function showNotification(message, type = 'info') {
    // Remove existing notifications
    const existingNotifications = document.querySelectorAll('.notification-toast');
    existingNotifications.forEach(notification => {
        notification.remove();
    });
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = 'notification-toast fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg border transition-all duration-300 transform translate-x-0 opacity-100';
    
    // Set styles based on type
    const typeStyles = {
        success: 'bg-emerald-50 text-emerald-800 border-emerald-200',
        error: 'bg-red-50 text-red-800 border-red-200',
        warning: 'bg-amber-50 text-amber-800 border-amber-200',
        info: 'bg-blue-50 text-blue-800 border-blue-200'
    };
    
    notification.className += ' ' + (typeStyles[type] || typeStyles.info);
    
    // Add icon based on type
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    
    notification.innerHTML = `
        <div class="flex items-center">
            <i class="fa-solid ${icons[type] || icons.info} mr-2"></i>
            <span class="text-sm font-medium">${message}</span>
            <button class="ml-4 text-gray-500 hover:text-gray-700 close-notification">
                <i class="fa-solid fa-times"></i>
            </button>
        </div>
    `;
    
    // Add to document
    document.body.appendChild(notification);
    
    // Add close handler
    const closeBtn = notification.querySelector('.close-notification');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            notification.remove();
        });
    }
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.classList.add('fade-out');
            setTimeout(() => notification.remove(), 300);
        }
    }, 5000);
}

// Collect Form Data for API (single JSON) - FIXED VERSION
function collectFormData() {
    const configData = {
        gateway_identity: {
            name: getInputValue('[name="gateway-name"]'),
            deployment_site: getInputValue('[name="deployment-site"]'),
            location_mode: getRadioValue('[name="location-mode"]'),
            latitude: parseFloat(getInputValue('[name="latitude"]')) || 0,
            longitude: parseFloat(getInputValue('[name="longitude"]')) || 0,
            asset_id: getInputValue('[name="asset-id"]')
        },
        date_time: {
            timezone: getSelectValue('[name="timezone"]'),
            ntp_server: getSelectValue('[name="ntp-server"]'),
            date_format: getSelectValue('[name="date-format"]'),
            time_format: getSelectValue('[name="time-format"]'),
            language: getSelectValue('[name="language"]')
        },
        network: {
            mode: getRadioValue('[name="network-mode"]')
        },
        heartbeat: {
            interval: parseInt(getInputValue('[name="heartbeat-interval"]')) || 30,
            offline_threshold: parseInt(getInputValue('[name="offline-threshold"]')) || 120
        },
        mac_address: document.querySelector('[data-mac-address]') ? document.querySelector('[data-mac-address]').textContent : '00:1A:2B:3C:4D:5E'
    };
    
    const networkMode = configData.network.mode;
    
    if (networkMode === 'ethernet') {
        configData.network.ethernet = {
            ip_assignment: getRadioValue('[name="ip-assignment"]')
        };
        
        if (configData.network.ethernet.ip_assignment === 'static') {
            configData.network.ethernet.static_ip = getInputValue('[name="static-ip"]');
            configData.network.ethernet.subnet_mask = getInputValue('[name="subnet-mask"]');
            configData.network.ethernet.gateway = getInputValue('[name="gateway"]');
            configData.network.ethernet.dns1 = getInputValue('[name="dns1"]');
            configData.network.ethernet.dns2 = getInputValue('[name="dns2"]');
        }
    } else if (networkMode === 'wifi') {
        const ssid = getInputValue('[name="wifi-ssid"]');
        const password = getInputValue('[name="wifi-password"]');
        
        configData.network.wifi = {};
        if (ssid) configData.network.wifi.ssid = ssid;
        if (password) configData.network.wifi.password = password;
    } else if (networkMode === 'lte') {
        configData.network.cellular = {
            apn: getInputValue('[name="apn"]') || 'internet'
        };
        
        const username = getInputValue('[name="cellular-username"]');
        const password = getInputValue('[name="cellular-password"]');
        
        if (username) configData.network.cellular.username = username;
        if (password) configData.network.cellular.password = password;
    }
    
    return configData;
}

// Save Configuration Handler
async function handleSaveConfiguration() {
    const saveBtn = document.getElementById('save-btn');
    if (!saveBtn) return;
    
    const originalText = saveBtn.innerHTML;
    
    saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Saving...';
    saveBtn.disabled = true;
    
    const configData = collectFormData();
    
    try {
        const response = await fetch('/api/general-configuration', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(configData)
        });
        
        if (!response.ok) {
            throw new Error('HTTP ' + response.status);
        }
        
        const result = await response.json();
        
        saveBtn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Saved!';
        saveBtn.classList.remove('bg-primary', 'hover:bg-primaryHover');
        saveBtn.classList.add('bg-success', 'hover:bg-emerald-600');
        
        setTimeout(() => {
            saveBtn.innerHTML = originalText;
            saveBtn.classList.remove('bg-success', 'hover:bg-emerald-600');
            saveBtn.classList.add('bg-primary', 'hover:bg-primaryHover');
            saveBtn.disabled = false;
        }, 2000);
        
        showNotification(result.message || 'Saved successfully', 'success');
        
    } catch (error) {
        console.error('Save error:', error);
        
        saveBtn.innerHTML = '<i class="fa-solid fa-exclamation-triangle mr-2"></i> Failed!';
        saveBtn.classList.remove('bg-primary', 'hover:bg-primaryHover');
        saveBtn.classList.add('bg-red-500', 'hover:bg-red-600');
        
        setTimeout(() => {
            saveBtn.innerHTML = originalText;
            saveBtn.classList.remove('bg-red-500', 'hover:bg-red-600');
            saveBtn.classList.add('bg-primary', 'hover:bg-primaryHover');
            saveBtn.disabled = false;
        }, 3000);
        
        showNotification('Save failed: ' + error.message, 'error');
    }
}

// Main initialization
window.initGeneralConfig = function() {
    console.log('General Configuration initialized');
    
    loadConfiguration().then(() => {
        initializeGeneralConfig();
        initializeWebSocket();
    }).catch(error => {
        console.error('Load error:', error);
        initializeGeneralConfig();
        initializeWebSocket();
        showNotification('Load failed', 'error');
    });
};

function initializeGeneralConfig() {
    initializeButtons();
    initializeNetworkToggles();
    console.log('Configuration setup complete');
}

// WebSocket
let wsConnection = null;
let reconnectInterval = null;

function initializeWebSocket() {
    const wsUrl = 'ws://' + window.location.host + '/ws';
    console.log('Connecting WebSocket:', wsUrl);
    
    wsConnection = new WebSocket(wsUrl);
    
    wsConnection.onopen = function() {
        console.log('WebSocket connected');
        if (reconnectInterval) {
            clearInterval(reconnectInterval);
            reconnectInterval = null;
        }
    };
    
    wsConnection.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        } catch (e) {
            console.error('WebSocket parse error:', e);
        }
    };
    
    wsConnection.onclose = function() {
        console.log('WebSocket disconnected');
        
        if (!reconnectInterval) {
            reconnectInterval = setInterval(() => {
                console.log('Reconnecting WebSocket...');
                initializeWebSocket();
            }, 5000);
        }
    };
    
    wsConnection.onerror = function(error) {
        console.error('WebSocket error:', error);
    };
}

function handleWebSocketMessage(data) {
    console.log('WebSocket:', data.type);
    
    switch (data.type) {
        case 'initial':
            setInputValue('[name="date"]', data.current_date);
            setInputValue('[name="time"]', data.current_time);
            if (data.wifi_signal_strength !== undefined) {
                updateWiFiSignalDisplay(data.wifi_signal_strength);
            }
            break;
            
        case 'wifi_signal_update':
            updateWiFiSignalDisplay(data.strength);
            break;
            
        case 'time_update':
            setInputValue('[name="date"]', data.current_date);
            setInputValue('[name="time"]', data.current_time);
            break;
            
        case 'time_synced':
            showNotification('Time synchronized', 'success');
            break;
    }
}

function syncTimeViaWebSocket() {
    if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
        wsConnection.send(JSON.stringify({ type: 'sync_time' }));
        return true;
    }
    return false;
}

// Load configuration from API
async function loadConfiguration() {
    try {
        const response = await fetch('/api/general-configuration');
        if (!response.ok) {
            throw new Error('HTTP ' + response.status);
        }
        
        const config = await response.json();
        populateFormWithConfig(config);
        console.log('Configuration loaded:', config);
        
    } catch (error) {
        console.error('Load error:', error);
        throw error;
    }
}

function populateFormWithConfig(config) {
    // Gateway Identity
    if (config.gateway_identity) {
        const id = config.gateway_identity;
        setInputValue('[name="gateway-name"]', id.name);
        setInputValue('[name="serial-number"]', id.serial_number);
        setInputValue('[name="deployment-site"]', id.deployment_site);
        setRadioValue('[name="location-mode"]', id.location_mode);
        setInputValue('[name="latitude"]', id.latitude);
        setInputValue('[name="longitude"]', id.longitude);
        setInputValue('[name="asset-id"]', id.asset_id);
    }
    
    // Date & Time
    if (config.date_time) {
        const dt = config.date_time;
        setSelectValue('[name="timezone"]', dt.timezone);
        setSelectValue('[name="ntp-server"]', dt.ntp_server);
        setSelectValue('[name="date-format"]', dt.date_format);
        setSelectValue('[name="time-format"]', dt.time_format);
        setSelectValue('[name="language"]', dt.language);
    }
    
    // Network
    if (config.network) {
        const net = config.network;
        setRadioValue('[name="network-mode"]', net.mode);
        
        if (net.ethernet) {
            setRadioValue('[name="ip-assignment"]', net.ethernet.ip_assignment || 'dhcp');
            setInputValue('[name="static-ip"]', net.ethernet.static_ip || '192.168.1.50');
            setInputValue('[name="subnet-mask"]', net.ethernet.subnet_mask || '255.255.255.0');
            setInputValue('[name="gateway"]', net.ethernet.gateway || '192.168.1.1');
            setInputValue('[name="dns1"]', net.ethernet.dns1 || '8.8.8.8');
            setInputValue('[name="dns2"]', net.ethernet.dns2 || '8.8.4.4');
        }
        
        if (net.wifi) {
            setInputValue('[name="wifi-ssid"]', net.wifi.ssid || '');
            setInputValue('[name="wifi-password"]', net.wifi.password || '');
        }
        
        if (net.cellular) {
            setInputValue('[name="apn"]', net.cellular.apn || 'internet');
            setInputValue('[name="cellular-username"]', net.cellular.username || '');
            setInputValue('[name="cellular-password"]', net.cellular.password || '');
        }
        
        setTimeout(() => toggleNetworkConfig(), 100);
    }
    
    // Heartbeat
    if (config.heartbeat) {
        setInputValue('[name="heartbeat-interval"]', config.heartbeat.interval);
        setInputValue('[name="offline-threshold"]', config.heartbeat.offline_threshold);
    }
    
    // MAC Address
    if (config.mac_address) {
        const macElement = document.querySelector('[data-mac-address]');
        if (macElement) macElement.textContent = config.mac_address;
    }
}

// Button Handlers
function initializeButtons() {
    // Refresh
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            if (confirm('Refresh page?')) {
                location.reload();
            }
        });
    }
    
    // Save
    const saveBtn = document.getElementById('save-btn');
    if (saveBtn) {
        saveBtn.addEventListener('click', handleSaveConfiguration);
    }
    
    // Sync Time
    const syncBtn = document.querySelector('.sync-time-btn');
    if (syncBtn) {
        syncBtn.addEventListener('click', function() {
            const originalHTML = syncBtn.innerHTML;
            syncBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
            syncBtn.disabled = true;
            
            if (syncTimeViaWebSocket()) {
                setTimeout(() => {
                    syncBtn.innerHTML = '<i class="fa-solid fa-rotate mr-2"></i> Sync Now';
                    syncBtn.disabled = false;
                }, 1000);
            } else {
                showNotification('Not connected', 'warning');
                syncBtn.innerHTML = '<i class="fa-solid fa-rotate mr-2"></i> Sync Now';
                syncBtn.disabled = false;
            }
        });
    }
    
    // Hide WiFi scan button
    const scanBtn = document.querySelector('#wifi-config .scan-wifi-btn');
    if (scanBtn) {
        scanBtn.style.display = 'none';
    }
}

// Cleanup
window.addEventListener('beforeunload', function() {
    if (wsConnection) {
        wsConnection.close();
    }
    
    if (reconnectInterval) {
        clearInterval(reconnectInterval);
    }
});

// Export for module system
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initGeneralConfig: window.initGeneralConfig,
        loadConfiguration: loadConfiguration,
        handleSaveConfiguration: handleSaveConfiguration
    };
}