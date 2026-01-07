// This function will be called by the router when loading the page
window.initGeneralConfig = function() {
    console.log('General Configuration page initialized');
    
    // Initialize all functionality for this page
    initializeGeneralConfig();
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
    const syncBtn = document.querySelector('.fa-rotate').closest('button');
    if (syncBtn) {
        syncBtn.addEventListener('click', function() {
            handleTimeSync();
        });
    }
}

function handleSaveConfiguration() {
    const saveBtn = document.getElementById('save-btn');
    if (!saveBtn) return;
    
    const originalText = saveBtn.innerHTML;
    
    // Show loading state
    saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Saving...';
    saveBtn.disabled = true;
    
    // Simulate API call
    setTimeout(() => {
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
        showNotification('Configuration saved successfully!', 'success');
    }, 1500);
}

function handleTimeSync() {
    // Get current time
    const now = new Date();
    const date = now.toISOString().split('T')[0];
    const time = now.toTimeString().split(' ')[0].substring(0, 5);
    
    // Update form fields
    const dateInput = document.querySelector('input[type="date"]');
    const timeInput = document.querySelector('input[type="time"]');
    
    if (dateInput) dateInput.value = date;
    if (timeInput) timeInput.value = time;
    
    // Show notification
    showNotification(`Time synced to ${date} ${time}`, 'success');
}

function initializeNetworkToggles() {
    // Network mode toggle
    const networkModeRadios = document.querySelectorAll('input[name="network-mode"]');
    networkModeRadios.forEach(radio => {
        radio.addEventListener('change', toggleNetworkConfig);
    });
    
    // IP assignment toggle
    const ipAssignmentRadios = document.querySelectorAll('input[name="ip-assignment"]');
    ipAssignmentRadios.forEach(radio => {
        radio.addEventListener('change', toggleIPAssignment);
    });
    
    // Initialize to show Ethernet config by default
    toggleNetworkConfig();
    toggleIPAssignment();
}

function toggleNetworkConfig() {
    const networkMode = document.querySelector('input[name="network-mode"]:checked')?.value;
    if (!networkMode) return;
    
    // Hide all config sections
    const ethernetConfig = document.getElementById('ethernet-config');
    const wifiConfig = document.getElementById('wifi-config');
    const cellularConfig = document.getElementById('cellular-config');
    
    if (ethernetConfig) ethernetConfig.style.display = 'none';
    if (wifiConfig) wifiConfig.style.display = 'none';
    if (cellularConfig) cellularConfig.style.display = 'none';
    
    // Show selected config
    if (networkMode === 'ethernet' && ethernetConfig) {
        ethernetConfig.style.display = 'block';
    } else if (networkMode === 'wifi' && wifiConfig) {
        wifiConfig.style.display = 'block';
        updateWiFiSignalStrength(3); // Start with "Good" signal
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

function initializeWiFiSignal() {
    // Find scan button and add click handler
    const scanBtn = document.querySelector('#wifi-config button[onclick*="scanWiFi"]');
    if (scanBtn) {
        scanBtn.removeAttribute('onclick'); // Remove inline onclick
        scanBtn.addEventListener('click', scanWiFi);
    }
    
    // Initialize WiFi signal strength display
    updateWiFiSignalStrength(3); // Default to "Good"
}

function updateWiFiSignalStrength(strength) {
    // strength can be 0-4 (0=none, 1=poor, 2=fair, 3=good, 4=excellent)
    const signalBars = document.querySelectorAll('#wifi-config .signal-bar');
    const strengthTexts = ['None', 'Poor', 'Fair', 'Good', 'Excellent'];
    
    if (!signalBars.length) return;
    
    // Reset all bars to none
    signalBars.forEach(bar => {
        bar.className = 'signal-bar none';
    });
    
    // Activate bars from left to right
    for (let i = 0; i <= strength; i++) {
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
                span.textContent = strengthTexts[strength];
            }
        });
    }
}

function scanWiFi() {
    const wifiConfig = document.getElementById('wifi-config');
    if (!wifiConfig) return;
    
    const scanButton = wifiConfig.querySelector('button');
    if (!scanButton) return;
    
    const originalHTML = scanButton.innerHTML;
    
    // Show scanning animation
    scanButton.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
    scanButton.disabled = true;
    
    // Simulate WiFi scan
    setTimeout(() => {
        // Random signal strength between 1-4
        const randomStrength = Math.floor(Math.random() * 4) + 1;
        updateWiFiSignalStrength(randomStrength);
        
        // Restore button
        scanButton.innerHTML = originalHTML;
        scanButton.disabled = false;
        
        // Show notification
        const strengthText = ['None', 'Poor', 'Fair', 'Good', 'Excellent'][randomStrength];
        showNotification(`WiFi scan complete. Signal strength: ${strengthText}`, 'success');
    }, 1500);
}

function initializeFormInteractions() {
    // Add change listeners to all form elements for validation
    const formElements = document.querySelectorAll('input, select, textarea');
    formElements.forEach(element => {
        element.addEventListener('change', function() {
            validateFormField(this);
        });
    });
    
    // Validate required fields on page load
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