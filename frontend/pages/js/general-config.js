// general-config.js
// Matching the exact theme and style of the reference

console.log('✅ general-config.js loaded - Script is running');

// Wrap everything in an IIFE to prevent duplicate declaration errors
(function() {
    // Check if already initialized
    if (window._generalConfigInitialized) {
        console.log('⏳ General Config already initialized, skipping...');
        return;
    }
    
    // Helper functions
    const setInputValue = function(selector, value) {
        if (value === undefined || value === null) return;
        const element = document.querySelector(selector);
        if (element) {
            element.value = value;
            element.dispatchEvent(new Event('change', { bubbles: true }));
            console.log(`📝 Set ${selector} = ${value}`);
        } else {
            console.warn(`⚠️ Element not found: ${selector}`);
        }
    };

    const setRadioValue = function(selector, value) {
        if (value === undefined || value === null) return;
        const radios = document.querySelectorAll(selector);
        radios.forEach(radio => {
            if (radio.value === value) {
                radio.checked = true;
                radio.dispatchEvent(new Event('change', { bubbles: true }));
                console.log(`📻 Set radio ${selector} = ${value}`);
            }
        });
    };

    const setSelectValue = function(selector, value) {
        if (value === undefined || value === null) return;
        const select = document.querySelector(selector);
        if (select) {
            select.value = value;
            select.dispatchEvent(new Event('change', { bubbles: true }));
            console.log(`📋 Set select ${selector} = ${value}`);
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
        return select ? select.value : '';
    };

    // Initialize password toggles
    const initializePasswordToggles = function() {
        document.querySelectorAll('.toggle-password').forEach(button => {
            // Remove existing listeners
            const newButton = button.cloneNode(true);
            button.parentNode.replaceChild(newButton, button);
            
            newButton.addEventListener('click', function(e) {
                e.preventDefault();
                const input = this.closest('.relative').querySelector('input');
                const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
                input.setAttribute('type', type);
                const icon = this.querySelector('i');
                if (icon) {
                    icon.className = type === 'password' ? 'fa-solid fa-eye' : 'fa-solid fa-eye-slash';
                }
            });
        });
    };

    // Network Toggle Functions
    const setNetworkMode = function(mode) {
        console.log('📶 Setting network mode:', mode);
        
        // Update radio buttons
        document.querySelectorAll('input[name="network-mode"]').forEach(r => {
            r.checked = (r.value === mode);
        });
        
        // Hide all config sections
        const ethernetConfig = document.getElementById('ethernet-config');
        const wifiConfig = document.getElementById('wifi-config');
        const cellularConfig = document.getElementById('cellular-config');
        
        if (ethernetConfig) ethernetConfig.style.display = 'none';
        if (wifiConfig) wifiConfig.style.display = 'none';
        if (cellularConfig) cellularConfig.style.display = 'none';
        
        // Show selected config
        if (mode === 'ethernet' && ethernetConfig) {
            ethernetConfig.style.display = 'block';
        } else if (mode === 'wifi' && wifiConfig) {
            wifiConfig.style.display = 'block';
            updateWiFiSignalDisplay(3); // Default to good signal
        } else if (mode === 'lte' && cellularConfig) {
            cellularConfig.style.display = 'block';
        }
    };

    const initializeNetworkToggles = function() {
        // Network mode change
        document.querySelectorAll('input[name="network-mode"]').forEach(radio => {
            radio.addEventListener('change', function() {
                setNetworkMode(this.value);
            });
        });
        
        // IP assignment toggle
        document.querySelectorAll('input[name="ip-assignment"]').forEach(radio => {
            radio.addEventListener('change', toggleIPAssignment);
        });
        
        // Initialize with default mode
        const checkedMode = document.querySelector('input[name="network-mode"]:checked');
        if (checkedMode) {
            setNetworkMode(checkedMode.value);
        } else {
            setNetworkMode('wifi');
        }
        
        toggleIPAssignment();
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
        // strength can be 0-4 (0=none, 1=poor, 2=fair, 3=good, 4=excellent)
        const signalBars = document.querySelectorAll('#wifi-config .signal-bar');
        const strengthClasses = ['none', 'poor', 'fair', 'good', 'excellent'];
        
        if (!signalBars.length) return;
        
        // Reset all bars to none
        signalBars.forEach(bar => {
            bar.className = 'signal-bar none';
        });
        
        // Activate bars from left to right
        const effectiveStrength = Math.min(Math.max(Math.floor(strength), 0), 4);
        
        for (let i = 0; i <= effectiveStrength; i++) {
            if (i < signalBars.length) {
                signalBars[i].className = `signal-bar ${strengthClasses[i]}`;
            }
        }
    };

    const getSignalStrengthText = function(strength) {
        const texts = ['None', 'Poor', 'Fair', 'Good', 'Excellent'];
        return texts[Math.min(Math.max(Math.floor(strength), 0), 4)] || 'Unknown';
    };

    const updateWiFiSignalDisplay = function(strength) {
        updateWiFiSignalStrength(strength);
        
        const label = document.querySelector('#wifi-config .signal-label');
        if (label) {
            label.textContent = getSignalStrengthText(strength);
        }
    };

    // WiFi scan function
    window.scanWiFi = function() {
        const scanButton = document.querySelector('#wifi-config button.ml-2');
        if (!scanButton) return;
        
        const originalHTML = scanButton.innerHTML;
        
        // Show scanning animation
        scanButton.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
        scanButton.disabled = true;
        
        // Simulate WiFi scan
        setTimeout(() => {
            const randomStrength = Math.floor(Math.random() * 4) + 1;
            updateWiFiSignalDisplay(randomStrength);
            
            scanButton.innerHTML = '<i class="fa-solid fa-rotate"></i>';
            scanButton.disabled = false;
            
            showNotification(`WiFi scan complete. Signal strength: ${getSignalStrengthText(randomStrength)}`, 'info');
        }, 1500);
    };

    // Notification System
    const showNotification = function(message, type = 'success') {
        let container = document.getElementById('gc-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'gc-toast-container';
            container.className = 'fixed top-4 right-4 z-[9999] flex flex-col gap-2';
            document.body.appendChild(container);
        }
        
        const notification = document.createElement('div');
        notification.className = `gc-toast px-4 py-3 rounded-lg shadow-lg border transition-all duration-300`;
        
        if (type === 'success') {
            notification.className += ' bg-emerald-50 border-emerald-200 text-emerald-800';
        } else if (type === 'error') {
            notification.className += ' bg-red-50 border-red-200 text-red-800';
        } else if (type === 'warning') {
            notification.className += ' bg-yellow-50 border-yellow-200 text-yellow-800';
        } else {
            notification.className += ' bg-blue-50 border-blue-200 text-blue-800';
        }
        
        const iconClass = type === 'success' ? 'fa-circle-check' : 
                         type === 'error' ? 'fa-circle-exclamation' : 
                         type === 'warning' ? 'fa-triangle-exclamation' : 'fa-circle-info';
        
        notification.innerHTML = `
            <div class="flex items-center">
                <i class="fa-solid ${iconClass} mr-3"></i>
                <span class="font-medium">${message}</span>
                <button class="ml-4 text-slate-400 hover:text-slate-600" onclick="this.parentElement.parentElement.remove()">
                    <i class="fa-solid fa-times"></i>
                </button>
            </div>
        `;
        
        container.appendChild(notification);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.classList.add('hide');
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.remove();
                    }
                }, 300);
            }
        }, 5000);
    };

    // Collect Form Data for API
    const collectFormData = function() {
        const wifiSsid = getInputValue('[name="wifi-ssid"]');
        const wifiPassword = getInputValue('[name="wifi-password"]');
        const networkMode = getRadioValue('[name="network-mode"]') || 'wifi';
        
        const formData = {
            gateway_identity: {
                name: getInputValue('[name="gateway-name"]') || 'Univa-GW-01',
                serial_number: getInputValue('[name="serial-number"]') || 'GW2025-1190021',
                deployment_site: getInputValue('[name="deployment-site"]') || 'Chennai Port - Zone A',
                location_mode: getRadioValue('[name="location-mode"]') || 'manual',
                latitude: parseFloat(getInputValue('[name="latitude"]')) || 12.99123,
                longitude: parseFloat(getInputValue('[name="longitude"]')) || 80.12312,
                asset_id: getInputValue('[name="asset-id"]') || 'CRN-CT-12'
            },
            date_time: {
                timezone: getSelectValue('[name="timezone"]') || 'Asia/Kolkata',
                ntp_server: getSelectValue('[name="ntp-server"]') || 'pool.ntp.org',
                date_format: getSelectValue('[name="date-format"]') || 'DD/MM/YYYY',
                time_format: getSelectValue('[name="time-format"]') || '24-hour',
                language: getSelectValue('[name="language"]') || 'en'
            },
            network: {
                mode: networkMode,
                wifi: {
                    ssid: wifiSsid,
                    password: wifiPassword
                },
                ethernet: {
                    ip_assignment: getRadioValue('[name="ip-assignment"]') || 'dhcp',
                    static_ip: getInputValue('[name="static-ip"]'),
                    subnet_mask: getInputValue('[name="subnet-mask"]'),
                    gateway: getInputValue('[name="gateway"]'),
                    dns1: getInputValue('[name="dns1"]'),
                    dns2: getInputValue('[name="dns2"]')
                },
                cellular: {
                    apn: getInputValue('[name="apn"]') || 'internet',
                    username: getInputValue('[name="cellular-username"]'),
                    password: getInputValue('[name="cellular-password"]')
                }
            },
            heartbeat: {
                interval: parseInt(getInputValue('[name="heartbeat-interval"]')) || 30,
                offline_threshold: parseInt(getInputValue('[name="offline-threshold"]')) || 120
            },
            mac_address: document.querySelector('[data-mac-address]')?.textContent.trim() || '00:1A:2B:3C:4D:5E'
        };

        // Debug log
        console.log('📦 Collected Form Data:', JSON.stringify(formData, null, 2));
        return formData;
    };

    // Save Configuration Handler
    const handleSaveConfiguration = async function() {
        console.log('💾 Save button clicked');
        const saveBtn = document.getElementById('save-btn');
        if (!saveBtn) return;
        
        const originalText = saveBtn.innerHTML;
        
        // Show loading state
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Saving...';
        saveBtn.disabled = true;
        saveBtn.classList.remove('bg-primary', 'hover:bg-primaryHover');
        saveBtn.classList.add('bg-gray-500', 'cursor-wait');
        
        const configData = collectFormData();
        
        console.log('📤 Sending to backend:', JSON.stringify(configData, null, 2));
        
        try {
            console.log('🌐 Making API call to /api/general-configuration');
            const response = await fetch('/api/general-configuration', {
                method: 'PUT',
                headers: { 
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(configData)
            });
            
            const result = await response.json();
            console.log('📥 Server response:', result);
            
            if (!response.ok) {
                throw new Error(result.message || `HTTP ${response.status}`);
            }
            
            // Success state
            saveBtn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Saved Successfully!';
            saveBtn.classList.remove('bg-gray-500', 'cursor-wait');
            saveBtn.classList.add('bg-success', 'hover:bg-emerald-600');
            
            showNotification(result.message || 'Configuration saved successfully!', 'success');
            
            // Reset button after 2 seconds
            setTimeout(() => {
                saveBtn.innerHTML = originalText;
                saveBtn.classList.remove('bg-success', 'hover:bg-emerald-600');
                saveBtn.classList.add('bg-primary', 'hover:bg-primaryHover');
                saveBtn.disabled = false;
            }, 2000);
            
        } catch (error) {
            console.error('❌ Save error:', error);
            
            // Error state
            saveBtn.innerHTML = '<i class="fa-solid fa-exclamation-triangle mr-2"></i> Failed!';
            saveBtn.classList.remove('bg-gray-500', 'cursor-wait');
            saveBtn.classList.add('bg-danger', 'hover:bg-red-600');
            
            showNotification(`Save failed: ${error.message}`, 'error');
            
            // Reset button after 3 seconds
            setTimeout(() => {
                saveBtn.innerHTML = originalText;
                saveBtn.classList.remove('bg-danger', 'hover:bg-red-600');
                saveBtn.classList.add('bg-primary', 'hover:bg-primaryHover');
                saveBtn.disabled = false;
            }, 3000);
        }
    };

    // Load Configuration
    const loadConfiguration = async function() {
        try {
            console.log('📥 Loading configuration from backend...');
            
            console.log('🌐 Making API call to /api/general-configuration');
            const response = await fetch('/api/general-configuration');
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const config = await response.json();
            console.log('📥 Configuration loaded:', config);
            
            populateFormWithConfig(config);
            
        } catch (error) {
            console.error('❌ Load error:', error);
            throw error;
        }
    };

    const populateFormWithConfig = function(config) {
        console.log('📝 Populating form with config:', config);
        
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
            
            // WiFi
            const wifi = net.wifi || {};
            setInputValue('[name="wifi-ssid"]', wifi.ssid || '');
            setInputValue('[name="wifi-password"]', wifi.password || '');
            
            // Ethernet
            const eth = net.ethernet || {};
            setRadioValue('[name="ip-assignment"]', eth.ip_assignment || 'dhcp');
            setInputValue('[name="static-ip"]', eth.static_ip || '');
            setInputValue('[name="subnet-mask"]', eth.subnet_mask || '');
            setInputValue('[name="gateway"]', eth.gateway || '');
            setInputValue('[name="dns1"]', eth.dns1 || '');
            setInputValue('[name="dns2"]', eth.dns2 || '');
            
            // Cellular
            const cell = net.cellular || {};
            setInputValue('[name="apn"]', cell.apn || 'internet');
            setInputValue('[name="cellular-username"]', cell.username || '');
            setInputValue('[name="cellular-password"]', cell.password || '');
            
            // Network Mode
            setNetworkMode(net.mode || 'wifi');
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
        // Refresh button
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            const newRefreshBtn = refreshBtn.cloneNode(true);
            refreshBtn.parentNode.replaceChild(newRefreshBtn, refreshBtn);
            
            newRefreshBtn.addEventListener('click', function() {
                if (confirm('Refresh page? Any unsaved changes will be lost.')) {
                    location.reload();
                }
            });
        }
        
        // Save button
        const saveBtn = document.getElementById('save-btn');
        if (saveBtn) {
            const newSaveBtn = saveBtn.cloneNode(true);
            saveBtn.parentNode.replaceChild(newSaveBtn, saveBtn);
            
            newSaveBtn.addEventListener('click', handleSaveConfiguration);
            console.log('✅ Save button initialized');
        }
        
        // Sync time button
        const syncBtn = document.querySelector('.sync-time-btn');
        if (syncBtn) {
            const newSyncBtn = syncBtn.cloneNode(true);
            syncBtn.parentNode.replaceChild(newSyncBtn, syncBtn);
            
            newSyncBtn.addEventListener('click', function() {
                const originalHTML = this.innerHTML;
                this.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i>';
                this.disabled = true;
                
                // Try to sync via WebSocket if connected
                if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
                    wsConnection.send(JSON.stringify({ type: 'sync_time' }));
                    
                    setTimeout(() => {
                        this.innerHTML = '<i class="fa-solid fa-rotate mr-2"></i> Sync Now';
                        this.disabled = false;
                    }, 1000);
                } else {
                    // Fallback to simulated sync
                    setTimeout(() => {
                        this.innerHTML = '<i class="fa-solid fa-rotate mr-2"></i> Sync Now';
                        this.disabled = false;
                        showNotification('Time synchronized (simulated)', 'success');
                    }, 1000);
                }
            });
        }
    };

    // WebSocket
    let wsConnection = null;
    let reconnectTimeout = null;
    let signalPollInterval = null;

    const initializeWebSocket = function() {
        // Close existing connection if any
        if (wsConnection) {
            try {
                wsConnection.close();
            } catch (e) {
                console.log('Existing WebSocket closed');
            }
            wsConnection = null;
        }
        
        // Clear any pending reconnect
        if (reconnectTimeout) {
            clearTimeout(reconnectTimeout);
            reconnectTimeout = null;
        }
        
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/general`;
        
        console.log('🔌 Connecting WebSocket:', wsUrl);
        wsConnection = new WebSocket(wsUrl);
        
        wsConnection.onopen = function() {
            console.log('✅ WebSocket connected');
            if (reconnectTimeout) {
                clearTimeout(reconnectTimeout);
                reconnectTimeout = null;
            }
            startSignalPolling();
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
            console.log('🔌 WebSocket disconnected');
            if (!document.getElementById('save-btn')) {
                console.log('Page no longer active, skipping reconnect');
                return;
            }
            if (!reconnectTimeout) {
                reconnectTimeout = setTimeout(() => {
                    reconnectTimeout = null;
                    console.log('🔄 Reconnecting WebSocket...');
                    initializeWebSocket();
                }, 5000);
            }
        };
        
        wsConnection.onerror = function(error) {
            console.error('❌ WebSocket error:', error);
        };
    };

    const startSignalPolling = function() {
        stopSignalPolling();
        signalPollInterval = setInterval(() => {
            const wifiPanel = document.getElementById('wifi-config');
            if (!wifiPanel || wifiPanel.style.display === 'none') return;
            
            if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
                wsConnection.send(JSON.stringify({ type: 'get_wifi_signal' }));
            }
        }, 10000);
    };

    const stopSignalPolling = function() {
        if (signalPollInterval) {
            clearInterval(signalPollInterval);
            signalPollInterval = null;
        }
    };

    const handleWebSocketMessage = function(data) {
        console.log('WebSocket message:', data.type);
        
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
                showNotification('Time synchronized successfully', 'success');
                break;
                
            case 'pong':
                console.log('Pong received');
                break;
        }
    };

    // Cleanup function
    const cleanupGeneralConfig = function() {
        stopSignalPolling();
        
        if (wsConnection) {
            try { 
                wsConnection.close(); 
            } catch (e) {}
            wsConnection = null;
        }
        
        if (reconnectTimeout) {
            clearTimeout(reconnectTimeout);
            reconnectTimeout = null;
        }
        
        window._generalConfigInitializing = false;
        console.log('🧹 Cleanup complete');
    };

    // Main initialization
    window.initGeneralConfig = function() {
        console.log('🚀 initGeneralConfig CALLED at', new Date().toISOString());
        
        if (window._generalConfigInitializing) {
            console.log('⏳ Already initializing, skipping...');
            return;
        }
        window._generalConfigInitializing = true;

        console.log('🚀 Initializing General Configuration...');

        cleanupGeneralConfig();
        initializeButtons();
        initializeNetworkToggles();
        initializePasswordToggles();

        console.log('📥 Starting loadConfiguration...');
        loadConfiguration().then(() => {
            console.log('✅ loadConfiguration completed, initializing WebSocket');
            initializeWebSocket();
            window._generalConfigInitializing = false;
            window._generalConfigInitialized = true;
            console.log('✅ General Configuration initialized');
        }).catch(error => {
            console.error('❌ Load error:', error);
            initializeWebSocket();
            showNotification('Failed to load configuration', 'warning');
            window._generalConfigInitializing = false;
        });
    };

    window.cleanupGeneralConfig = cleanupGeneralConfig;
    window.showNotification = showNotification;

    // Auto-initialize if we're on the right page
    if (document.querySelector('[name="gateway-name"]')) {
        console.log('🔄 Auto-initializing from script');
        setTimeout(() => {
            if (window.initGeneralConfig) {
                window.initGeneralConfig();
            }
        }, 100);
    }
})();