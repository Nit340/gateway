// general-config.js
// FIX BUG-12: Removed the window.generalConfigLoaded guard that wrapped the entire file.
// That guard caused all const declarations (wsConnection, initializeWebSocket, etc.) to be
// skipped on the second SPA visit, making the module rely on fragile closure state from
// the first visit. Now the IIFE runs fully every time the script loads.
    // Helper functions
    const setInputValue = function(selector, value) {
        if (value === undefined || value === null) return;
        const element = document.querySelector(selector);
        if (element) element.value = value;
    };

    const setRadioValue = function(selector, value) {
        if (value === undefined || value === null) return;
        const radios = document.querySelectorAll(selector);
        radios.forEach(radio => {
            if (radio.value === value) {
                radio.checked = true;
                radio.dispatchEvent(new Event('change'));
            }
        });
    };

    const setSelectValue = function(selector, value) {
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
    };

    const getInputValue = function(selector) {
        const element = document.querySelector(selector);
        return element ? element.value : '';
    };

    const getRadioValue = function(selector) {
        const radio = document.querySelector(selector + ':checked');
        return radio ? radio.value : '';
    };

    const getSelectValue = function(selector) {
        const select = document.querySelector(selector);
        return select ? select.options[select.selectedIndex].value : '';
    };

    // Network Toggle Functions
    const initializeNetworkToggles = function() {
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
    };

    const toggleNetworkConfig = function() {
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
    };

    const toggleIPAssignment = function() {
        const ipAssignment = document.querySelector('input[name="ip-assignment"]:checked');
        const staticConfig = document.getElementById('static-ip-config');
        
        if (!staticConfig) return;
        
        if (ipAssignment && ipAssignment.value === 'static') {
            staticConfig.classList.remove('hidden');
        } else {
            staticConfig.classList.add('hidden');
        }
    };

    // WiFi Signal Functions
    const updateWiFiSignalStrength = function(strength) {
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
    };

    const getSignalStrengthText = function(strength) {
        const strengthTexts = ['None', 'Poor', 'Fair', 'Good', 'Excellent'];
        return strengthTexts[Math.min(Math.max(strength, 0), 4)] || 'Unknown';
    };

    const updateWiFiSignalDisplay = function(strength) {
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
    };

    // Notification System
    const showNotification = function(message, type = 'info') {
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
    };

    // Collect Form Data for API (single JSON) - FIXED VERSION
    const collectFormData = function() {
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
    };

    // Save Configuration Handler
    const handleSaveConfiguration = async function() {
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
    };

    // Main initialization
    window.initGeneralConfig = function() {
        // Guard against double-init from router calling twice
        if (window._generalConfigInitializing) {
            console.log('General Configuration already initializing, skipping duplicate call');
            return;
        }
        window._generalConfigInitializing = true;

        console.log('General Configuration initialized');

        // Clean up any existing connections first
        cleanupGeneralConfig();

        loadConfiguration().then(() => {
            initializeGeneralConfig();
            initializeWebSocket();
            window._generalConfigInitializing = false;
        }).catch(error => {
            console.error('Load error:', error);
            initializeGeneralConfig();
            initializeWebSocket();
            showNotification('Load failed', 'error');
            window._generalConfigInitializing = false;
        });
    };

    const initializeGeneralConfig = function() {
        initializeButtons();
        initializeNetworkToggles();
        console.log('Configuration setup complete');
    };

    // WebSocket
    let wsConnection = null;
    let reconnectTimeout = null;

    const initializeWebSocket = function() {
        // Close existing connection if any
        if (wsConnection) {
            try {
                wsConnection.close();
            } catch (e) {
                console.log('Existing WebSocket already closed');
            }
            wsConnection = null;
        }

        // Clear any pending reconnect
        if (reconnectTimeout) {
            clearTimeout(reconnectTimeout);
            reconnectTimeout = null;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = protocol + '//' + window.location.host + '/ws/general';
        console.log('Connecting WebSocket:', wsUrl);

        wsConnection = new WebSocket(wsUrl);

        wsConnection.onopen = function() {
            console.log('WebSocket connected');
            // Clear any pending reconnect on successful connect
            if (reconnectTimeout) {
                clearTimeout(reconnectTimeout);
                reconnectTimeout = null;
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
            // FIX BUG-11: Only reconnect if we're still on the General Config page.
            // Without this guard, navigating away causes an infinite zombie WS loop
            // that runs for the entire browser session, trying to update DOM elements
            // that no longer exist.
            if (!document.getElementById('save-btn')) {
                console.log('General config page no longer active, skipping WS reconnect');
                return;
            }
            if (!reconnectTimeout) {
                reconnectTimeout = setTimeout(function() {
                    reconnectTimeout = null;
                    console.log('Reconnecting WebSocket...');
                    initializeWebSocket();
                }, 5000);
            }
        };

        wsConnection.onerror = function(error) {
            console.error('WebSocket error:', error);
        };
    };

    const handleWebSocketMessage = function(data) {
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
    };

    const syncTimeViaWebSocket = function() {
        if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
            wsConnection.send(JSON.stringify({ type: 'sync_time' }));
            return true;
        }
        return false;
    };

    // Load configuration from API
    const loadConfiguration = async function() {
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
    };

    const populateFormWithConfig = function(config) {
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
    };

    // Button Handlers
    const initializeButtons = function() {
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
    };

    // Cleanup function
    const cleanupGeneralConfig = function() {
        // Close WebSocket
        if (wsConnection) {
            try {
                wsConnection.close();
            } catch (e) {
                console.log('WebSocket already closed');
            }
            wsConnection = null;
        }
        
        // Clear reconnect timeout
        if (reconnectTimeout) {
            clearTimeout(reconnectTimeout);
            reconnectTimeout = null;
        }
        
        // Remove event listeners if needed
        const saveBtn = document.getElementById('save-btn');
        if (saveBtn) {
            const newSaveBtn = saveBtn.cloneNode(true);
            saveBtn.parentNode.replaceChild(newSaveBtn, saveBtn);
        }
        
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            const newRefreshBtn = refreshBtn.cloneNode(true);
            refreshBtn.parentNode.replaceChild(newRefreshBtn, refreshBtn);
        }
        
        // Reset init guard so navigating back to this page works
        window._generalConfigInitializing = false;
        console.log('General config cleanup complete');
    };

    // Add cleanup method to window for router to call
    window.cleanupGeneralConfig = cleanupGeneralConfig;

    // Cleanup on page unload
    window.addEventListener('beforeunload', function() {
        cleanupGeneralConfig();
    });
// FIX BUG-12: Removed the orphaned closing brace that belonged to the
// now-deleted window.generalConfigLoaded guard block.

// FIX BUG-13: module.exports previously referenced loadConfiguration and
// handleSaveConfiguration as bare names — both are const-declared inside the
// (now removed) guard block, making them out-of-scope in any non-browser env
// and causing ReferenceError. Now we only export what is safely on window.
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initGeneralConfig: window.initGeneralConfig,
        cleanupGeneralConfig: window.cleanupGeneralConfig
    };
}