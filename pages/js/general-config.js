// general-config.js - Updated with better network handling
window.initGeneralConfig = function() {
    console.log('General Configuration page initialized');
    
    // Load configuration from API and then initialize
    loadConfiguration().then(() => {
        initializeGeneralConfig();
    }).catch(error => {
        console.error('Failed to load configuration:', error);
        // Initialize with default values even if API fails
        initializeGeneralConfig();
        showNotification('Could not load configuration. Using default values.', 'error');
    });
};

function initializeGeneralConfig() {
    console.log('Setting up General Configuration page functionality');
    
    // Initialize button handlers
    initializeButtons();
    
    // Initialize network configuration toggles
    initializeNetworkToggles();
    
    // Initialize WiFi signal strength
    initializeWiFiSignal();
    
    // Initialize form validation and interactions
    initializeFormInteractions();
    
    console.log('General Configuration page setup complete');
}

// API Integration Functions
async function loadConfiguration() {
    try {
        // Make API call to load current configuration
        const response = await fetch('/api/general-configuration', {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            credentials: 'include'
        });
        
        if (!response.ok) {
            if (response.status === 401) {
                // Redirect to login if unauthorized
                window.location.href = '/login';
                return;
            }
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const config = await response.json();
        
        // Populate form fields with configuration data
        populateFormWithConfig(config);
        
        console.log('Configuration loaded successfully:', config);
        
        // Show success notification
        showNotification('Configuration loaded successfully', 'success');
        
    } catch (error) {
        console.error('Error loading configuration:', error);
        throw error;
    }
}

function populateFormWithConfig(config) {
    // SECTION A: Gateway Identity
    if (config.gateway_identity) {
        const identity = config.gateway_identity;
        setInputValue('[name="gateway-name"]', identity.name);
        setInputValue('[name="serial-number"]', identity.serial_number);
        setInputValue('[name="deployment-site"]', identity.deployment_site);
        setRadioValue('[name="location-mode"]', identity.location_mode);
        setInputValue('[name="latitude"]', identity.latitude);
        setInputValue('[name="longitude"]', identity.longitude);
        setInputValue('[name="asset-id"]', identity.asset_id);
    }
    
    // SECTION B: Date, Time & Localization
    if (config.date_time) {
        const dateTime = config.date_time;
        setSelectValue('[name="timezone"]', dateTime.timezone);
        setSelectValue('[name="ntp-server"]', dateTime.ntp_server);
        setInputValue('[name="date"]', dateTime.current_date);
        setInputValue('[name="time"]', dateTime.current_time);
        setSelectValue('[name="date-format"]', dateTime.date_format);
        setSelectValue('[name="time-format"]', dateTime.time_format);
        setSelectValue('[name="language"]', dateTime.language);
    }
    
    // SECTION C: Network Configuration
    if (config.network) {
        const network = config.network;
        setRadioValue('[name="network-mode"]', network.mode);
        
        // Load network-specific configuration
        if (network.ethernet) {
            setRadioValue('[name="ip-assignment"]', network.ethernet.ip_assignment || 'dhcp');
            setInputValue('[name="static-ip"]', network.ethernet.static_ip || '192.168.1.50');
            setInputValue('[name="subnet-mask"]', network.ethernet.subnet_mask || '255.255.255.0');
            setInputValue('[name="gateway"]', network.ethernet.gateway || '192.168.1.1');
            setInputValue('[name="dns1"]', network.ethernet.dns1 || '8.8.8.8');
            setInputValue('[name="dns2"]', network.ethernet.dns2 || '8.8.4.4');
        }
        
        if (network.wifi) {
            setInputValue('[name="wifi-ssid"]', network.wifi.ssid || '');
            setInputValue('[name="wifi-password"]', network.wifi.password || '');
            updateWiFiSignalStrength(network.wifi.signal_strength || 0);
        }
        
        if (network.cellular) {
            setInputValue('[name="apn"]', network.cellular.apn || 'internet');
            setInputValue('[name="cellular-username"]', network.cellular.username || '');
            setInputValue('[name="cellular-password"]', network.cellular.password || '');
        }
        
        // Trigger network toggle to show correct section
        setTimeout(() => toggleNetworkConfig(), 100);
    }
    
    // SECTION D: System Heartbeat
    if (config.heartbeat) {
        const heartbeat = config.heartbeat;
        setInputValue('[name="heartbeat-interval"]', heartbeat.interval);
        setInputValue('[name="offline-threshold"]', heartbeat.offline_threshold);
    }
    
    // Update MAC address display if available
    if (config.mac_address) {
        const macElement = document.querySelector('[data-mac-address]');
        if (macElement) {
            macElement.textContent = config.mac_address;
        }
    }
}

// Helper functions for setting form values
function setInputValue(selector, value) {
    if (value === undefined || value === null) return;
    const element = document.querySelector(selector);
    if (element) {
        element.value = value;
    }
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
            if (select.options[i].value === value || 
                select.options[i].text.includes(value)) {
                select.selectedIndex = i;
                break;
            }
        }
    }
}

// Button Handlers
function initializeButtons() {
    // Handle Refresh button
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            if (confirm('Refresh page? Any unsaved changes will be lost.')) {
                location.reload();
            }
        });
    }
    
    // Handle Save Changes button
    const saveBtn = document.getElementById('save-btn');
    if (saveBtn) {
        saveBtn.addEventListener('click', function() {
            handleSaveConfiguration();
        });
    }
    
    // Handle Sync Now button
    const syncBtn = document.querySelector('.sync-time-btn');
    if (syncBtn) {
        syncBtn.addEventListener('click', function() {
            handleTimeSync();
        });
    }
}

// Save Configuration Handler
async function handleSaveConfiguration() {
    const saveBtn = document.getElementById('save-btn');
    if (!saveBtn) return;
    
    // Validate form before saving
    if (!validateRequiredFields()) {
        showNotification('Please fill in all required fields', 'error');
        return;
    }
    
    const originalText = saveBtn.innerHTML;
    
    // Show loading state
    saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Saving...';
    saveBtn.disabled = true;
    
    // Collect all form data
    const configData = collectFormData();
    
    try {
        // Make API call to save configuration
        const response = await fetch('/api/general-configuration', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify(configData)
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.message || `HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        // Show success message
        saveBtn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Saved Successfully!';
        saveBtn.classList.remove('bg-primary', 'hover:bg-primaryHover');
        saveBtn.classList.add('bg-success', 'hover:bg-emerald-600');
        
        // Revert after 2 seconds
        setTimeout(() => {
            saveBtn.innerHTML = originalText;
            saveBtn.classList.remove('bg-success', 'hover:bg-emerald-600');
            saveBtn.classList.add('bg-primary', 'hover:bg-primaryHover');
            saveBtn.disabled = false;
        }, 2000);
        
        // Show notification
        showNotification(result.message || 'Configuration saved successfully!', 'success');
        
        // Refresh configuration data after a short delay
        setTimeout(() => {
            loadConfiguration().catch(() => {
                // Silently handle refresh errors
            });
        }, 500);
        
    } catch (error) {
        console.error('Error saving configuration:', error);
        
        // Show error state
        saveBtn.innerHTML = '<i class="fa-solid fa-exclamation-triangle mr-2"></i> Save Failed!';
        saveBtn.classList.remove('bg-primary', 'hover:bg-primaryHover');
        saveBtn.classList.add('bg-red-500', 'hover:bg-red-600');
        
        // Revert after 3 seconds
        setTimeout(() => {
            saveBtn.innerHTML = originalText;
            saveBtn.classList.remove('bg-red-500', 'hover:bg-red-600');
            saveBtn.classList.add('bg-primary', 'hover:bg-primaryHover');
            saveBtn.disabled = false;
        }, 3000);
        
        showNotification(`Failed to save configuration: ${error.message}`, 'error');
    }
}

// Collect Form Data for API - Updated for dynamic network config
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
        }
    };
    
    // Add network-specific configuration based on selected mode
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
        configData.network.wifi = {
            ssid: getInputValue('[name="wifi-ssid"]'),
            password: getInputValue('[name="wifi-password"]')
        };
    } else if (networkMode === 'lte') {
        configData.network.cellular = {
            apn: getInputValue('[name="apn"]'),
            username: getInputValue('[name="cellular-username"]'),
            password: getInputValue('[name="cellular-password"]')
        };
    }
    
    return configData;
}

// Helper functions for getting form values
function getInputValue(selector) {
    const element = document.querySelector(selector);
    return element ? element.value : '';
}

function getRadioValue(selector) {
    const radio = document.querySelector(`${selector}:checked`);
    return radio ? radio.value : '';
}

function getSelectValue(selector) {
    const select = document.querySelector(selector);
    return select ? select.options[select.selectedIndex].value : '';
}

// Time Sync Handler
async function handleTimeSync() {
    try {
        const syncBtn = document.querySelector('.sync-time-btn');
        if (syncBtn) {
            const originalHTML = syncBtn.innerHTML;
            syncBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
            syncBtn.disabled = true;
        }
        
        // Make API call to sync time
        const response = await fetch('/api/general-configuration/time-sync', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        // Update form fields with synced time
        if (result.current_date && result.current_time) {
            setInputValue('[name="date"]', result.current_date);
            setInputValue('[name="time"]', result.current_time);
        }
        
        // Restore button
        if (syncBtn) {
            syncBtn.innerHTML = '<i class="fa-solid fa-rotate mr-2"></i> Sync Now';
            syncBtn.disabled = false;
        }
        
        // Show notification
        showNotification(result.message || 'Time synchronized successfully', 'success');
        
    } catch (error) {
        console.error('Error syncing time:', error);
        
        // Fallback to client time if API fails
        const now = new Date();
        const date = now.toISOString().split('T')[0];
        const time = now.toTimeString().split(' ')[0].substring(0, 5);
        
        setInputValue('[name="date"]', date);
        setInputValue('[name="time"]', time);
        
        // Restore button
        const syncBtn = document.querySelector('.sync-time-btn');
        if (syncBtn) {
            syncBtn.innerHTML = '<i class="fa-solid fa-rotate mr-2"></i> Sync Now';
            syncBtn.disabled = false;
        }
        
        showNotification(`Time synced to local time: ${date} ${time}`, 'info');
    }
}

// WiFi Scan Handler
async function scanWiFi() {
    const wifiConfig = document.getElementById('wifi-config');
    if (!wifiConfig) return;
    
    const scanButton = wifiConfig.querySelector('.scan-wifi-btn');
    if (!scanButton) return;
    
    const originalHTML = scanButton.innerHTML;
    
    // Show scanning animation
    scanButton.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
    scanButton.disabled = true;
    
    try {
        // Make API call to scan WiFi
        const response = await fetch('/api/general-configuration/wifi-scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (result.success && result.networks && result.networks.length > 0) {
            // Populate WiFi networks dropdown
            updateWiFiNetworksList(result.networks);
            
            // Update signal strength with the strongest network
            const strongestNetwork = result.networks.reduce((prev, current) => 
                (prev.signal > current.signal) ? prev : current
            );
            
            updateWiFiSignalStrength(strongestNetwork.signal);
            
            // Auto-select the strongest network
            const ssidInput = document.querySelector('[name="wifi-ssid"]');
            if (ssidInput) {
                ssidInput.value = strongestNetwork.ssid;
            }
            
            // Show notification
            showNotification(`Found ${result.networks.length} WiFi network(s)`, 'success');
        } else {
            updateWiFiSignalStrength(0); // No networks found
            showNotification('No WiFi networks found', 'warning');
        }
        
    } catch (error) {
        console.error('Error scanning WiFi:', error);
        
        // Fallback to random signal for demo
        const randomStrength = Math.floor(Math.random() * 4) + 1;
        updateWiFiSignalStrength(randomStrength);
        
        showNotification('WiFi scan completed (demo mode)', 'info');
    } finally {
        // Restore button
        scanButton.innerHTML = originalHTML;
        scanButton.disabled = false;
    }
}

// Update WiFi Networks List
function updateWiFiNetworksList(networks) {
    const ssidInput = document.querySelector('[name="wifi-ssid"]');
    if (!ssidInput) return;
    
    // Convert input to datalist for autocomplete
    const datalistId = 'wifi-networks-list';
    let datalist = document.getElementById(datalistId);
    
    if (!datalist) {
        datalist = document.createElement('datalist');
        datalist.id = datalistId;
        ssidInput.setAttribute('list', datalistId);
        ssidInput.parentNode.appendChild(datalist);
    }
    
    // Clear existing options
    datalist.innerHTML = '';
    
    // Add new options
    networks.forEach(network => {
        const option = document.createElement('option');
        option.value = network.ssid;
        option.textContent = `${network.ssid} (${['None', 'Poor', 'Fair', 'Good', 'Excellent'][network.signal]})`;
        datalist.appendChild(option);
    });
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
    
    // Initialize on page load
    toggleNetworkConfig();
    toggleIPAssignment();
}

function toggleNetworkConfig() {
    const networkMode = document.querySelector('input[name="network-mode"]:checked')?.value;
    if (!networkMode) return;
    
    const ethernetConfig = document.getElementById('ethernet-config');
    const wifiConfig = document.getElementById('wifi-config');
    const cellularConfig = document.getElementById('cellular-config');
    
    // Hide all config sections
    if (ethernetConfig) ethernetConfig.style.display = 'none';
    if (wifiConfig) wifiConfig.style.display = 'none';
    if (cellularConfig) cellularConfig.style.display = 'none';
    
    // Show only the selected config
    if (networkMode === 'ethernet' && ethernetConfig) {
        ethernetConfig.style.display = 'block';
    } else if (networkMode === 'wifi' && wifiConfig) {
        wifiConfig.style.display = 'block';
        // Update WiFi signal strength when WiFi is selected
        const currentSSID = getInputValue('[name="wifi-ssid"]');
        if (currentSSID) {
            updateWiFiSignalStrength(3); // Default to "Good"
        } else {
            updateWiFiSignalStrength(0); // No network
        }
    } else if (networkMode === 'lte' && cellularConfig) {
        cellularConfig.style.display = 'block';
    }
}

function toggleIPAssignment() {
    const ipAssignment = document.querySelector('input[name="ip-assignment"]:checked')?.value;
    const staticConfig = document.getElementById('static-ip-config');
    
    if (!staticConfig) return;
    
    if (ipAssignment === 'static') {
        staticConfig.classList.remove('hidden');
    } else {
        staticConfig.classList.add('hidden');
    }
}

// WiFi Signal Functions
function initializeWiFiSignal() {
    const scanBtn = document.querySelector('#wifi-config .scan-wifi-btn');
    if (scanBtn) {
        scanBtn.addEventListener('click', scanWiFi);
    }
}

function updateWiFiSignalStrength(strength) {
    const signalBars = document.querySelectorAll('#wifi-config .signal-bar');
    const strengthTexts = ['None', 'Poor', 'Fair', 'Good', 'Excellent'];
    
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
    
    // Update strength text
    const wifiConfig = document.getElementById('wifi-config');
    if (wifiConfig) {
        const strengthSpans = wifiConfig.querySelectorAll('.signal-strength + span, .signal-strength + .ml-2');
        strengthSpans.forEach(span => {
            if (span.textContent.includes('None') || 
                span.textContent.includes('Poor') || 
                span.textContent.includes('Fair') || 
                span.textContent.includes('Good') || 
                span.textContent.includes('Excellent')) {
                span.textContent = strengthTexts[effectiveStrength];
            }
        });
    }
}

// Form Validation Functions
function initializeFormInteractions() {
    const formElements = document.querySelectorAll('input, select, textarea');
    formElements.forEach(element => {
        element.addEventListener('change', function() {
            validateFormField(this);
        });
        
        // Real-time validation for required fields
        if (element.hasAttribute('required')) {
            element.addEventListener('input', function() {
                validateFormField(this);
            });
        }
    });
    
    validateRequiredFields();
}

function validateFormField(element) {
    // Basic validation for required fields
    if (element.hasAttribute('required') && !element.value.trim()) {
        element.classList.add('border-red-300', 'bg-red-50');
        return false;
    } else {
        element.classList.remove('border-red-300', 'bg-red-50');
        return true;
    }
}

function validateRequiredFields() {
    const requiredFields = document.querySelectorAll('[required]');
    let allValid = true;
    
    requiredFields.forEach(field => {
        if (!validateFormField(field)) {
            allValid = false;
        }
    });
    
    return allValid;
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
    notification.className = `notification-toast fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg border transition-all duration-300 transform translate-x-0 opacity-100`;
    
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

// Export functions if needed for module system
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initGeneralConfig,
        loadConfiguration,
        handleSaveConfiguration,
        handleTimeSync,
        scanWiFi
    };
}