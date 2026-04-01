// This function will be called by the router when loading the page
window.initOtaGateway = function() {
    // Initialize all functionality for this page
    initializeOtaGateway();
};

// Available updates data (moved to global scope)
const availableUpdates = [
    {
        version: "v5.0.5",
        type: "security",
        critical: true,
        size: "452 MB",
        description: "Security patches for kernel vulnerabilities and network stack improvements.",
        released: "2025-03-15",
        changelog: [
            "Fixed CVE-2025-1234 (Kernel memory leak)",
            "Fixed CVE-2025-5678 (Network stack vulnerability)",
            "Improved system stability",
            "Updated security certificates"
        ]
    },
    {
        version: "v5.1.0",
        type: "feature",
        critical: false,
        size: "1.2 GB",
        description: "Major feature release with improved container runtime and enhanced monitoring.",
        released: "2025-03-10",
        changelog: [
            "New container runtime v2.0",
            "Enhanced monitoring dashboard",
            "Added USB 3.2 device support",
            "Improved network performance"
        ]
    },
    {
        version: "v5.2.0-beta",
        type: "beta",
        critical: false,
        size: "1.5 GB",
        description: "Preview of upcoming features. Not recommended for production systems.",
        released: "2025-03-05",
        changelog: [
            "Experimental GPU acceleration",
            "New API endpoints",
            "Enhanced logging system",
            "Beta features enabled"
        ]
    }
];

// Global variables
let currentFile = null;
let deploymentInProgress = false;
let autoUpdateEnabled = true;
let updateCheckInterval;
let currentUpdate = null;
let updateDownloadInterval;
let loadingOverlay = null;

function initializeOtaGateway() {
    try {
        // Initialize all OTA components
        initializeUpdateSystem();
        initializeFileUpload();
        initializeRadioButtons();
        initializeSafetyToggle();
        initializeRecoveryButtons();
        initializeSystemStatus();
        initializeLiveMonitor();
        initializeButtons();
        
        // Check for updates on load
        setTimeout(() => {
            checkForUpdates(true); // Silent check on load
        }, 1000);
        
        // Setup periodic update checks (every 5 minutes)
        updateCheckInterval = setInterval(() => {
            if (autoUpdateEnabled) {
                checkForUpdates(true);
            }
        }, 5 * 60 * 1000); // 5 minutes
        
        addLogEntry('System initialized');
        addLogEntry('Auto-update system: Enabled');
        addLogEntry('Next automatic check: ' + new Date(Date.now() + 5 * 60 * 1000).toLocaleTimeString());

    } catch (error) {
        console.error('Error in initializeOtaGateway:', error);
    }
}

// ============================================================================
// LOADING OVERLAY FUNCTIONS
// ============================================================================

function showLoadingOverlay(message = 'Processing...') {
    if (loadingOverlay) {
        loadingOverlay.remove();
    }
    
    loadingOverlay = document.createElement('div');
    loadingOverlay.id = 'factory-reset-loading';
    loadingOverlay.className = 'fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50';
    loadingOverlay.innerHTML = `
        <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-8 text-center">
            <div class="flex justify-center mb-4">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-red-600"></div>
            </div>
            <h3 class="text-lg font-semibold text-slate-800 mb-2">${message}</h3>
            <p class="text-sm text-slate-500">Please wait, this may take a moment...</p>
        </div>
    `;
    
    document.body.appendChild(loadingOverlay);
}

function hideLoadingOverlay() {
    if (loadingOverlay && loadingOverlay.parentNode) {
        loadingOverlay.parentNode.removeChild(loadingOverlay);
        loadingOverlay = null;
    }
}

// ============================================================================
// CUSTOM DIALOG FUNCTIONS (No alerts)
// ============================================================================

function showConfirmDialog(title, message, confirmText, cancelText, onConfirm) {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
    modal.innerHTML = `
        <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
            <div class="flex items-center mb-4">
                <div class="h-10 w-10 bg-red-100 rounded-full flex items-center justify-center mr-3">
                    <i class="fa-solid fa-triangle-exclamation text-red-600 text-lg"></i>
                </div>
                <h3 class="text-lg font-bold text-slate-800">${title}</h3>
            </div>
            <p class="text-slate-600 mb-6">${message}</p>
            <div class="flex space-x-3">
                <button id="confirm-dialog-btn" class="flex-1 bg-red-600 hover:bg-red-700 text-white font-medium py-2 rounded-lg transition-colors">
                    ${confirmText}
                </button>
                <button id="cancel-dialog-btn" class="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium py-2 rounded-lg transition-colors">
                    ${cancelText}
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    const confirmBtn = document.getElementById('confirm-dialog-btn');
    const cancelBtn = document.getElementById('cancel-dialog-btn');
    
    const closeModal = () => {
        if (modal && modal.parentNode) {
            modal.parentNode.removeChild(modal);
        }
    };
    
    if (confirmBtn) {
        confirmBtn.addEventListener('click', () => {
            closeModal();
            if (onConfirm) onConfirm();
        });
    }
    
    if (cancelBtn) {
        cancelBtn.addEventListener('click', closeModal);
    }
    
    // Close on outside click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });
}

function showNotificationDialog(title, message, type = 'info') {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
    
    const colors = {
        info: { icon: 'fa-circle-info', bg: 'bg-blue-100', text: 'text-blue-600', btn: 'bg-blue-600 hover:bg-blue-700' },
        success: { icon: 'fa-circle-check', bg: 'bg-green-100', text: 'text-green-600', btn: 'bg-green-600 hover:bg-green-700' },
        warning: { icon: 'fa-triangle-exclamation', bg: 'bg-amber-100', text: 'text-amber-600', btn: 'bg-amber-600 hover:bg-amber-700' },
        error: { icon: 'fa-circle-xmark', bg: 'bg-red-100', text: 'text-red-600', btn: 'bg-red-600 hover:bg-red-700' }
    };
    
    const color = colors[type] || colors.info;
    
    modal.innerHTML = `
        <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
            <div class="flex items-center mb-4">
                <div class="h-10 w-10 ${color.bg} rounded-full flex items-center justify-center mr-3">
                    <i class="fa-solid ${color.icon} ${color.text} text-lg"></i>
                </div>
                <h3 class="text-lg font-bold text-slate-800">${title}</h3>
            </div>
            <p class="text-slate-600 mb-6">${message}</p>
            <button id="notification-dialog-btn" class="w-full ${color.btn} text-white font-medium py-2 rounded-lg transition-colors">
                OK
            </button>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    const okBtn = document.getElementById('notification-dialog-btn');
    if (okBtn) {
        okBtn.addEventListener('click', () => {
            if (modal && modal.parentNode) {
                modal.parentNode.removeChild(modal);
            }
        });
    }
}

function showPasswordDialog(title, message, onConfirm) {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
    modal.innerHTML = `
        <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
            <div class="flex items-center mb-4">
                <div class="h-10 w-10 bg-red-100 rounded-full flex items-center justify-center mr-3">
                    <i class="fa-solid fa-lock text-red-600 text-lg"></i>
                </div>
                <h3 class="text-lg font-bold text-slate-800">${title}</h3>
            </div>
            <p class="text-slate-600 mb-4">${message}</p>
            <div class="mb-4">
                <input type="password" id="password-input" 
                    class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-red-500"
                    placeholder="Enter admin password">
            </div>
            <div class="flex space-x-3">
                <button id="confirm-password-btn" class="flex-1 bg-red-600 hover:bg-red-700 text-white font-medium py-2 rounded-lg transition-colors">
                    Confirm
                </button>
                <button id="cancel-password-btn" class="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium py-2 rounded-lg transition-colors">
                    Cancel
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    const passwordInput = document.getElementById('password-input');
    const confirmBtn = document.getElementById('confirm-password-btn');
    const cancelBtn = document.getElementById('cancel-password-btn');
    
    const closeModal = () => {
        if (modal && modal.parentNode) {
            modal.parentNode.removeChild(modal);
        }
    };
    
    if (passwordInput) {
        setTimeout(() => passwordInput.focus(), 100);
        passwordInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                if (confirmBtn) confirmBtn.click();
            }
        });
    }
    
    if (confirmBtn) {
        confirmBtn.addEventListener('click', () => {
            const password = passwordInput ? passwordInput.value : '';
            closeModal();
            if (onConfirm) onConfirm(password);
        });
    }
    
    if (cancelBtn) {
        cancelBtn.addEventListener('click', closeModal);
    }
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });
}

function initializeUpdateSystem() {
    // Check for updates button
    const checkUpdatesBtn = document.getElementById('check-updates-btn');
    if (checkUpdatesBtn) {
        checkUpdatesBtn.addEventListener('click', function() {
            checkForUpdates(false);
        });
    }
    
    // Auto-update toggle
    const autoUpdateToggle = document.getElementById('auto-update-toggle');
    if (autoUpdateToggle) {
        autoUpdateToggle.addEventListener('click', function() {
            toggleAutoUpdate();
        });
    }
    
    // Install update buttons
    document.querySelectorAll('.install-update-btn').forEach(button => {
        button.addEventListener('click', function() {
            const version = this.getAttribute('data-version');
            const update = availableUpdates.find(u => u.version === version);
            if (update) {
                startUpdateDownload(update);
            }
        });
    });
    
    // Update banner buttons
    const installNowBtn = document.getElementById('install-now-btn');
    if (installNowBtn) {
        installNowBtn.addEventListener('click', function() {
            if (currentUpdate) {
                startUpdateDownload(currentUpdate);
                hideUpdateBanner();
            }
        });
    }
    
    const scheduleBtn = document.getElementById('schedule-btn');
    if (scheduleBtn) {
        scheduleBtn.addEventListener('click', function() {
            showNotificationDialog('Update Scheduled', 'Update scheduled for 02:00 AM', 'info');
            hideUpdateBanner();
        });
    }
    
    const dismissBtn = document.getElementById('dismiss-btn');
    if (dismissBtn) {
        dismissBtn.addEventListener('click', function() {
            hideUpdateBanner();
        });
    }
    
    // Auto-update settings
    const autoDownload = document.getElementById('auto-download');
    if (autoDownload) {
        autoDownload.addEventListener('change', function() {
            showNotificationDialog('Auto-Download', `Auto-download: ${this.checked ? 'Enabled' : 'Disabled'}`, 'info');
        });
    }
    
    const autoSecurity = document.getElementById('auto-security');
    if (autoSecurity) {
        autoSecurity.addEventListener('change', function() {
            showNotificationDialog('Auto-Install', `Auto-install security updates: ${this.checked ? 'Enabled' : 'Disabled'}`, 'info');
        });
    }
    
    const autoReboot = document.getElementById('auto-reboot');
    if (autoReboot) {
        autoReboot.addEventListener('change', function() {
            showNotificationDialog('Auto-Reboot', `Auto-reboot after install: ${this.checked ? 'Enabled' : 'Disabled'}`, 'info');
        });
    }
}

// Check for updates
function checkForUpdates(silent = false) {
    const checkingUpdates = document.getElementById('checking-updates');
    const updatesList = document.getElementById('updates-list');
    const noUpdates = document.getElementById('no-updates');
    const checkUpdatesBtn = document.getElementById('check-updates-btn');
    
    if (!silent && checkingUpdates && updatesList && noUpdates && checkUpdatesBtn) {
        checkingUpdates.classList.remove('hidden');
        updatesList.classList.add('hidden');
        noUpdates.classList.add('hidden');
        checkUpdatesBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Checking...';
        checkUpdatesBtn.disabled = true;
    }
    
    // Simulate API call to check for updates
    setTimeout(() => {
        const osVersionElement = document.getElementById('os-version');
        const currentVersion = osVersionElement ? osVersionElement.textContent : '';
        const filteredUpdates = availableUpdates.filter(update => 
            update.version !== currentVersion
        );
        
        if (!silent) {
            if (checkingUpdates) checkingUpdates.classList.add('hidden');
            if (checkUpdatesBtn) {
                checkUpdatesBtn.innerHTML = '<i class="fa-solid fa-arrows-rotate mr-2"></i> Check for Updates';
                checkUpdatesBtn.disabled = false;
            }
            
            if (filteredUpdates.length > 0) {
                if (updatesList) updatesList.classList.remove('hidden');
                updateUpdateList(filteredUpdates);
            } else {
                if (noUpdates) noUpdates.classList.remove('hidden');
            }
        }
        
        // Show banner if there are updates
        if (filteredUpdates.length > 0 && !deploymentInProgress) {
            currentUpdate = filteredUpdates[0];
            showUpdateBanner(currentUpdate);
        }
        
        addLogEntry(`Update check completed. Found ${filteredUpdates.length} update(s)`);
        
        const now = new Date();
        addLogEntry(`Last checked: ${now.toLocaleString()}`);
        
    }, 2000);
}

// Update the updates list UI
function updateUpdateList(updates) {
    const updatesList = document.getElementById('updates-list');
    if (!updatesList) return;
    
    updates.forEach((update, index) => {
        const item = updatesList.children[index];
        if (item) {
            const versionSpan = item.querySelector('.text-sm.font-bold');
            if (versionSpan) versionSpan.textContent = update.version + (update.type === 'security' ? ' Security Update' : ' Feature Update');
            
            const descP = item.querySelector('.text-sm.text-slate-600');
            if (descP) descP.textContent = update.description;
            
            const sizeSpan = item.querySelector('.fa-download').parentElement;
            if (sizeSpan) sizeSpan.innerHTML = `<i class="fa-solid fa-download mr-1"></i> Size: ${update.size}`;
            
            const installBtn = item.querySelector('.install-update-btn');
            if (installBtn) {
                installBtn.setAttribute('data-version', update.version);
                installBtn.textContent = update.type === 'security' ? 'Install Now' : 'Install';
            }
            
            const badgeSpan = item.querySelector('.text-xs.bg-red-100, .text-xs.bg-blue-100, .text-xs.bg-purple-100');
            if (badgeSpan) {
                badgeSpan.className = 'text-xs px-2 py-0.5 rounded-full font-bold';
                if (update.type === 'security') {
                    badgeSpan.classList.add('bg-red-100', 'text-red-700');
                    badgeSpan.textContent = 'CRITICAL';
                } else if (update.type === 'feature') {
                    badgeSpan.classList.add('bg-blue-100', 'text-blue-700');
                    badgeSpan.textContent = 'FEATURE';
                } else {
                    badgeSpan.classList.add('bg-purple-100', 'text-purple-700');
                    badgeSpan.textContent = 'BETA';
                }
            }
        }
    });
}

// Toggle auto-update
function toggleAutoUpdate() {
    autoUpdateEnabled = !autoUpdateEnabled;
    const button = document.getElementById('auto-update-toggle');
    if (!button) return;
    
    const status = autoUpdateEnabled ? 'On' : 'Off';
    
    button.innerHTML = `<i class="fa-solid fa-robot mr-2"></i> Auto-Update: ${status}`;
    button.className = `px-4 py-2 text-sm font-medium rounded-md transition-colors ${autoUpdateEnabled ? 'bg-blue-100 hover:bg-blue-200 text-blue-700' : 'bg-slate-100 hover:bg-slate-200 text-slate-700'}`;
    
    showNotificationDialog('Auto-Update', `Auto-update ${autoUpdateEnabled ? 'enabled' : 'disabled'}`, 'info');
    addLogEntry(`Auto-update ${autoUpdateEnabled ? 'enabled' : 'disabled'}`);
    
    if (autoUpdateEnabled) {
        checkForUpdates(true);
    }
}

// Show update banner
function showUpdateBanner(update) {
    const banner = document.getElementById('update-banner');
    if (!banner) return;
    
    const title = banner.querySelector('h3');
    const desc = banner.querySelector('p');
    
    if (title) title.textContent = `${update.type === 'security' ? 'Security ' : ''}Update available`;
    if (desc) desc.textContent = `${update.version} - ${update.description.substring(0, 60)}...`;
    
    banner.classList.remove('hidden');
    
    setTimeout(() => {
        if (banner.classList.contains('hidden')) return;
        hideUpdateBanner();
    }, 30000);
}

// Hide update banner
function hideUpdateBanner() {
    const banner = document.getElementById('update-banner');
    if (banner) banner.classList.add('hidden');
}

// Start update download
function startUpdateDownload(update) {
    if (deploymentInProgress) {
        showNotificationDialog('Update In Progress', 'Another update is already in progress', 'warning');
        return;
    }
    
    deploymentInProgress = true;
    currentUpdate = update;
    
    showNotificationDialog('Download Started', `Starting download of ${update.version}...`, 'info');
    addLogEntry(`Starting download: ${update.version} (${update.size})`);
    
    // Update UI
    const updateBadge = document.getElementById('update-badge');
    if (updateBadge) updateBadge.classList.remove('hidden');
    
    const statusText = document.getElementById('status-text');
    if (statusText) statusText.textContent = `Downloading ${update.version}...`;
    
    const currentOperation = document.getElementById('current-operation');
    if (currentOperation) currentOperation.textContent = 'Downloading';
    
    const statusPercent = document.getElementById('status-percent');
    if (statusPercent) statusPercent.textContent = '0%';
    
    const progressFill = document.getElementById('progress-fill');
    if (progressFill) {
        progressFill.style.width = '0%';
        progressFill.className = 'h-full bg-blue-500 transition-all duration-1000';
    }
    
    // Disable install buttons
    document.querySelectorAll('.install-update-btn').forEach(btn => {
        btn.disabled = true;
        btn.classList.add('opacity-50', 'cursor-not-allowed');
    });
    
    // Start download simulation
    simulateUpdateDownload(update);
}

// Simulate update download
function simulateUpdateDownload(update) {
    let progress = 0;
    let speed = 5 + Math.random() * 10;
    
    updateDownloadInterval = setInterval(() => {
        if (progress >= 100) {
            clearInterval(updateDownloadInterval);
            setTimeout(() => {
                verifyUpdate(update);
            }, 500);
            return;
        }
        
        progress += Math.random() * 2;
        if (progress > 100) progress = 100;
        
        const statusPercent = document.getElementById('status-percent');
        if (statusPercent) statusPercent.textContent = `${Math.round(progress)}%`;
        
        const progressFill = document.getElementById('progress-fill');
        if (progressFill) progressFill.style.width = `${progress}%`;
        
        speed = Math.max(3, speed + (Math.random() - 0.5) * 2);
        const downloadSpeed = document.getElementById('download-speed');
        if (downloadSpeed) downloadSpeed.textContent = `${speed.toFixed(1)} MB/s`;
        
        if (progress > 0) {
            const remaining = (100 - progress) / progress * (Date.now() - startTime) / 1000;
            const minutes = Math.floor(remaining / 60);
            const seconds = Math.floor(remaining % 60);
            const etaElement = document.getElementById('eta');
            if (etaElement) etaElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        }
        
        const progressFillElement = document.getElementById('progress-fill');
        if (progressFillElement) {
            if (progress < 30) {
                progressFillElement.className = 'h-full bg-blue-500 transition-all duration-1000';
            } else if (progress < 70) {
                progressFillElement.className = 'h-full bg-amber-500 transition-all duration-1000';
            } else {
                progressFillElement.className = 'h-full bg-green-500 transition-all duration-1000';
            }
        }
        
        if (Math.round(progress) % 25 === 0 && Math.round(progress) > 0) {
            addLogEntry(`Download progress: ${Math.round(progress)}%`);
        }
        
    }, 200);
    
    const startTime = Date.now();
    addLogEntry(`Download started: ${update.version}`);
}

// Verify downloaded update
function verifyUpdate(update) {
    const statusText = document.getElementById('status-text');
    if (statusText) statusText.textContent = `Verifying ${update.version}...`;
    
    const currentOperation = document.getElementById('current-operation');
    if (currentOperation) currentOperation.textContent = 'Verifying';
    
    const integrityStatus = document.getElementById('integrity-status');
    if (integrityStatus) {
        integrityStatus.textContent = 'Checking...';
        integrityStatus.className = 'text-amber-400';
    }
    
    addLogEntry(`Verifying update integrity: ${update.version}`);
    
    setTimeout(() => {
        if (integrityStatus) {
            integrityStatus.textContent = 'Verified ✓';
            integrityStatus.className = 'text-green-400';
        }
        addLogEntry(`Update verified successfully: ${update.version}`);
        
        setTimeout(() => {
            installUpdate(update);
        }, 1000);
    }, 3000);
}

// Install update
function installUpdate(update) {
    const statusText = document.getElementById('status-text');
    if (statusText) statusText.textContent = `Installing ${update.version} to Partition B...`;
    
    const currentOperation = document.getElementById('current-operation');
    if (currentOperation) currentOperation.textContent = 'Installing';
    
    const progressFill = document.getElementById('progress-fill');
    if (progressFill) progressFill.className = 'h-full animate-progress';
    
    addLogEntry(`Starting installation: ${update.version} to Partition B`);
    
    const partitionBStatus = document.getElementById('partition-b-status');
    if (partitionBStatus) {
        partitionBStatus.innerHTML = `${update.version} • <span class="text-amber-600 font-bold animate-pulse">Installing...</span>`;
    }
    
    setTimeout(() => {
        deploymentInProgress = false;
        if (updateDownloadInterval) {
            clearInterval(updateDownloadInterval);
            updateDownloadInterval = null;
        }
        
        if (statusText) statusText.textContent = `Update ${update.version} installed successfully!`;
        if (currentOperation) currentOperation.textContent = 'Ready to reboot';
        if (progressFill) {
            progressFill.className = 'h-full bg-green-500';
            progressFill.style.width = '100%';
        }
        
        const statusPercent = document.getElementById('status-percent');
        if (statusPercent) statusPercent.textContent = '100%';
        
        const updateBadge = document.getElementById('update-badge');
        if (updateBadge) updateBadge.classList.add('hidden');
        
        if (partitionBStatus) {
            partitionBStatus.innerHTML = `${update.version} • <span class="text-green-600 font-bold">Update complete</span>`;
        }
        
        document.querySelectorAll('.install-update-btn').forEach(btn => {
            btn.disabled = false;
            btn.classList.remove('opacity-50', 'cursor-not-allowed');
        });
        
        showNotificationDialog('Update Complete', `${update.version} installed successfully! Ready for reboot.`, 'success');
        addLogEntry(`Update installed successfully: ${update.version}`);
        
        const updateIndex = availableUpdates.findIndex(u => u.version === update.version);
        if (updateIndex !== -1) {
            availableUpdates.splice(updateIndex, 1);
            const osVersionElement = document.getElementById('os-version');
            const currentVersion = osVersionElement ? osVersionElement.textContent : '';
            updateUpdateList(availableUpdates.filter(u => u.version !== currentVersion));
        }
        
        createRebootButton(update.version);
        
    }, 5000);
}

// Initialize file upload functionality
function initializeFileUpload() {
    const dropArea = document.getElementById('upload-dropzone');
    if (!dropArea) return;
    
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.img,.tar.gz,.squashfs';
    fileInput.style.display = 'none';
    fileInput.multiple = false;
    
    dropArea.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileSelect);
    dropArea.parentNode.appendChild(fileInput);
    
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });
    
    dropArea.addEventListener('drop', handleDrop, false);
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    function highlight() {
        dropArea.classList.add('border-blue-400', 'bg-blue-50');
    }
    
    function unhighlight() {
        dropArea.classList.remove('border-blue-400', 'bg-blue-50');
    }
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }
}

// Handle file selection
function handleFileSelect(e) {
    const files = e.target.files;
    handleFiles(files);
}

// Process uploaded files
function handleFiles(files) {
    if (files.length === 0) return;
    
    const file = files[0];
    const validExtensions = ['.img', '.tar.gz', '.squashfs'];
    const fileName = file.name.toLowerCase();
    
    if (!validExtensions.some(ext => fileName.endsWith(ext))) {
        showNotificationDialog('Invalid File', 'Invalid file type. Please upload .img, .tar.gz, or .squashfs files.', 'error');
        return;
    }
    
    currentFile = file;
    
    const dropArea = document.getElementById('upload-dropzone');
    const icon = document.getElementById('upload-icon');
    const text = document.getElementById('upload-text');
    const subtext = document.getElementById('upload-subtext');
    
    if (icon) {
        icon.innerHTML = '<i class="fa-solid fa-file-circle-check text-green-500 text-xl"></i>';
        icon.classList.remove('bg-blue-50');
        icon.classList.add('bg-green-50');
    }
    
    if (text) {
        text.textContent = file.name;
        text.classList.add('font-mono', 'text-sm');
    }
    
    if (subtext) subtext.textContent = `${formatFileSize(file.size)} • Ready for verification`;
    
    const verifyBtn = document.getElementById('verify-btn');
    if (verifyBtn) {
        verifyBtn.disabled = false;
        verifyBtn.classList.remove('bg-slate-200', 'text-slate-400', 'cursor-not-allowed');
        verifyBtn.classList.add('bg-blue-600', 'text-white', 'hover:bg-blue-700', 'cursor-pointer');
        verifyBtn.onclick = () => verifyAndPrepare(file);
    }
    
    const versionInput = document.getElementById('image-version');
    if (versionInput) {
        const versionMatch = file.name.match(/v?\d+\.\d+\.\d+/);
        if (versionMatch) {
            versionInput.value = versionMatch[0];
        }
    }
    
    simulateChecksum(file);
    
    showNotificationDialog('File Uploaded', `File "${file.name}" uploaded successfully`, 'success');
    addLogEntry(`Manual upload: ${file.name} (${formatFileSize(file.size)})`);
}

// Simulate checksum calculation
function simulateChecksum(file) {
    const checksumInput = document.getElementById('checksum');
    if (!checksumInput) return;
    
    checksumInput.placeholder = 'Calculating...';
    
    setTimeout(() => {
        const fakeHash = 'sha256:' + Array.from({length: 64}, () => 
            Math.floor(Math.random() * 16).toString(16)).join('');
        checksumInput.value = fakeHash;
        checksumInput.placeholder = '';
        simulateMetadataExtraction(file);
    }, 1000);
}

// Simulate metadata extraction
function simulateMetadataExtraction(file) {
    const metadataKernel = document.getElementById('metadata-kernel');
    const metadataBuild = document.getElementById('metadata-build');
    const metadataSig = document.getElementById('metadata-sig');
    
    if (metadataKernel) metadataKernel.textContent = 'Extracting...';
    if (metadataBuild) metadataBuild.textContent = 'Extracting...';
    if (metadataSig) metadataSig.textContent = 'Verifying...';
    
    setTimeout(() => {
        if (metadataKernel) {
            metadataKernel.textContent = '6.2.0-LTS';
            metadataKernel.className = 'font-mono text-green-600';
        }
        
        setTimeout(() => {
            const buildId = 'BUILD-' + Date.now().toString().slice(-8);
            if (metadataBuild) {
                metadataBuild.textContent = buildId;
                metadataBuild.className = 'font-mono text-green-600';
            }
            
            setTimeout(() => {
                if (metadataSig) {
                    metadataSig.textContent = 'Verified ✓';
                    metadataSig.className = 'font-mono text-green-600 font-bold';
                }
            }, 300);
        }, 300);
    }, 500);
}

// Verify and prepare manual deployment
function verifyAndPrepare(file) {
    showNotificationDialog('Verifying', `Verifying ${file.name}...`, 'info');
    addLogEntry('Starting manual image verification');
    
    const verifyBtn = document.getElementById('verify-btn');
    if (!verifyBtn) return;
    
    verifyBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Verifying...';
    verifyBtn.disabled = true;
    
    setTimeout(() => {
        verifyBtn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Verified Successfully';
        verifyBtn.classList.remove('bg-blue-600');
        verifyBtn.classList.add('bg-green-600');
        
        showNotificationDialog('Verification Complete', 'Image verified successfully! Ready for deployment to Partition B.', 'success');
        addLogEntry('Manual image verification passed');
        
        const partitionBStatus = document.getElementById('partition-b-status');
        const versionInput = document.getElementById('image-version');
        const version = versionInput && versionInput.value ? versionInput.value : 'v5.1.0-rc1';
        
        if (partitionBStatus) {
            partitionBStatus.innerHTML = `${version} • <span class="text-blue-600 font-bold">Ready for update</span>`;
        }
        
        createManualDeployButton(version);
    }, 2000);
}

// Create manual deployment button
function createManualDeployButton(version) {
    const buttonContainer = document.getElementById('button-container');
    if (!buttonContainer) return;
    
    buttonContainer.innerHTML = '';
    
    const deployBtn = document.createElement('button');
    deployBtn.id = 'deploy-btn';
    deployBtn.className = 'w-full bg-green-600 hover:bg-green-700 text-white font-medium py-2.5 rounded-md flex items-center justify-center transition-colors mt-2';
    deployBtn.innerHTML = '<i class="fa-solid fa-rocket mr-2"></i> Deploy to Partition B';
    
    deployBtn.addEventListener('click', () => startManualDeployment(version));
    buttonContainer.appendChild(deployBtn);
}

// Start manual deployment
function startManualDeployment(version) {
    if (deploymentInProgress) {
        showNotificationDialog('Deployment In Progress', 'Another update is already in progress', 'warning');
        return;
    }
    
    deploymentInProgress = true;
    
    showNotificationDialog('Deployment Started', `Starting manual deployment of ${version} to Partition B...`, 'info');
    addLogEntry(`Initiating manual deployment of ${version} to Partition B`);
    
    const partitionBStatus = document.getElementById('partition-b-status');
    if (partitionBStatus) {
        partitionBStatus.innerHTML = `${version} • <span class="text-amber-600 font-bold animate-pulse">Installing...</span>`;
    }
    
    const updateBadge = document.getElementById('update-badge');
    if (updateBadge) updateBadge.classList.remove('hidden');
    
    const statusText = document.getElementById('status-text');
    if (statusText) statusText.textContent = `Installing ${version}...`;
    
    const currentOperation = document.getElementById('current-operation');
    if (currentOperation) currentOperation.textContent = 'Installing';
    
    const statusPercent = document.getElementById('status-percent');
    if (statusPercent) statusPercent.textContent = '0%';
    
    const progressFill = document.getElementById('progress-fill');
    if (progressFill) {
        progressFill.style.width = '0%';
        progressFill.className = 'h-full animate-progress';
    }
    
    document.querySelectorAll('button:not(#cancel-btn):not(#reset-btn)').forEach(btn => {
        if (!btn.id.includes('cancel') && !btn.id.includes('reset')) {
            btn.disabled = true;
            btn.classList.add('opacity-50', 'cursor-not-allowed');
        }
    });
    
    simulateManualDeployment(version);
}

// Simulate manual deployment
function simulateManualDeployment(version) {
    let progress = 0;
    
    const interval = setInterval(() => {
        if (progress >= 100) {
            clearInterval(interval);
            deploymentInProgress = false;
            
            const statusText = document.getElementById('status-text');
            if (statusText) statusText.textContent = `Manual deployment complete!`;
            
            const currentOperation = document.getElementById('current-operation');
            if (currentOperation) currentOperation.textContent = 'Ready to reboot';
            
            const progressFill = document.getElementById('progress-fill');
            if (progressFill) {
                progressFill.className = 'h-full bg-green-500';
                progressFill.style.width = '100%';
            }
            
            const statusPercent = document.getElementById('status-percent');
            if (statusPercent) statusPercent.textContent = '100%';
            
            const updateBadge = document.getElementById('update-badge');
            if (updateBadge) updateBadge.classList.add('hidden');
            
            const partitionBStatus = document.getElementById('partition-b-status');
            if (partitionBStatus) {
                partitionBStatus.innerHTML = `${version} • <span class="text-green-600 font-bold">Update complete</span>`;
            }
            
            document.querySelectorAll('button:not(#cancel-btn):not(#reset-btn)').forEach(btn => {
                btn.disabled = false;
                btn.classList.remove('opacity-50', 'cursor-not-allowed');
            });
            
            showNotificationDialog('Deployment Complete', `Manual deployment of ${version} completed! Ready for reboot.`, 'success');
            addLogEntry(`Manual deployment completed: ${version}`);
            
            createRebootButton(version);
            return;
        }
        
        progress += Math.random() * 3;
        if (progress > 100) progress = 100;
        
        const statusPercent = document.getElementById('status-percent');
        if (statusPercent) statusPercent.textContent = `${Math.round(progress)}%`;
        
        const progressFill = document.getElementById('progress-fill');
        if (progressFill) progressFill.style.width = `${progress}%`;
        
        if (Math.round(progress) % 25 === 0 && Math.round(progress) > 0) {
            addLogEntry(`Manual installation progress: ${Math.round(progress)}%`);
        }
        
    }, 200);
}

// Create reboot button
function createRebootButton(version) {
    const buttonContainer = document.getElementById('button-container');
    if (!buttonContainer) return;
    
    buttonContainer.innerHTML = '';
    
    const rebootBtn = document.createElement('button');
    rebootBtn.id = 'reboot-btn';
    rebootBtn.className = 'w-full bg-purple-600 hover:bg-purple-700 text-white font-medium py-2.5 rounded-md flex items-center justify-center transition-colors mt-2';
    rebootBtn.innerHTML = '<i class="fa-solid fa-power-off mr-2"></i> Reboot into Partition B';
    
    rebootBtn.addEventListener('click', () => {
        showConfirmDialog('Confirm Reboot', `Reboot into updated Partition B (${version})? System will restart.`, 'Reboot Now', 'Cancel', () => {
            simulateReboot(version);
        });
    });
    
    buttonContainer.appendChild(rebootBtn);
}

// Initialize radio buttons
function initializeRadioButtons() {
    const radios = document.querySelectorAll('input[name="strategy"]');
    radios.forEach(radio => {
        radio.addEventListener('change', function() {
            document.querySelectorAll('label[id^="strategy-"]').forEach(label => {
                label.classList.remove('border-blue-500', 'bg-blue-50');
                label.classList.add('border-slate-200');
                label.querySelector('span').classList.remove('text-blue-900');
                label.querySelector('span').classList.add('text-slate-700');
            });
            
            const label = this.closest('label');
            label.classList.remove('border-slate-200');
            label.classList.add('border-blue-500', 'bg-blue-50');
            label.querySelector('span').classList.remove('text-slate-700');
            label.querySelector('span').classList.add('text-blue-900');
            
            const strategyName = this.value === 'seamless' ? 'Seamless A/B' : 'Maintenance Window';
            showNotificationDialog('Strategy Updated', `Update strategy changed to: ${strategyName}`, 'info');
            addLogEntry(`Update strategy: ${strategyName}`);
        });
    });
}

// Initialize safety toggle
function initializeSafetyToggle() {
    const forceToggle = document.getElementById('force-toggle');
    const forceWarning = document.getElementById('force-warning');
    
    if (forceToggle) {
        forceToggle.addEventListener('change', function() {
            if (this.checked) {
                if (forceWarning) forceWarning.classList.remove('hidden');
                showNotificationDialog('Force Override', 'Force override enabled. Safety constraints will be ignored!', 'warning');
                
                setTimeout(() => {
                    showPasswordDialog('Admin Verification', 'Enter admin PIN to confirm force override:', (pin) => {
                        if (pin !== '7392') {
                            this.checked = false;
                            if (forceWarning) forceWarning.classList.add('hidden');
                            showNotificationDialog('Invalid PIN', 'Invalid PIN. Force override cancelled.', 'error');
                        } else {
                            showNotificationDialog('Force Override', 'Force override confirmed. Proceed with caution!', 'warning');
                            addLogEntry('Force override enabled (Admin PIN verified)');
                        }
                    });
                }, 300);
            } else {
                if (forceWarning) forceWarning.classList.add('hidden');
                showNotificationDialog('Force Override', 'Force override disabled. Safety constraints active.', 'info');
                addLogEntry('Force override disabled');
            }
        });
    }
}

// ============================================================================
// FACTORY RESET FUNCTIONALITY WITH LOADING SCREEN
// ============================================================================

// Initialize recovery buttons
function initializeRecoveryButtons() {
    // Rollback button
    const rollbackBtn = document.getElementById('rollback-btn');
    if (rollbackBtn) {
        rollbackBtn.addEventListener('click', function() {
            showConfirmDialog('Confirm Rollback', 'Are you sure you want to rollback to Partition A? This will switch active partition immediately.', 'Rollback Now', 'Cancel', () => {
                simulateRollback();
            });
        });
    }
    
    // Restore button
    const restoreBtn = document.getElementById('restore-btn');
    if (restoreBtn) {
        restoreBtn.addEventListener('click', function() {
            showConfirmDialog('Confirm Restore', 'Restore previous OS version v5.0.3? This will overwrite current partition.', 'Restore Now', 'Cancel', () => {
                simulateRestore();
            });
        });
    }
    
    // Factory reset button - NEW with loading screen
    const factoryBtn = document.getElementById('factory-btn');
    if (factoryBtn) {
        const newFactoryBtn = factoryBtn.cloneNode(true);
        factoryBtn.parentNode.replaceChild(newFactoryBtn, factoryBtn);
        
        newFactoryBtn.addEventListener('click', function() {
            showConfirmDialog(
                '⚠️ Factory Reset Warning',
                'This will trigger a factory reset on the gateway device. All configuration and data will be wiped. This action cannot be undone.\n\nAre you ABSOLUTELY sure you want to proceed?',
                'Yes, Factory Reset',
                'Cancel',
                () => {
                    // Show password dialog after confirmation
                    showPasswordDialog(
                        'Admin Authentication',
                        'Please enter your admin password to confirm factory reset:',
                        async (password) => {
                            if (!password) {
                                showNotificationDialog('Authentication Failed', 'Password is required', 'error');
                                return;
                            }
                            await sendFactoryReset(password);
                        }
                    );
                }
            );
        });
    }
    
    // Recovery image upload
    const uploadRecoveryBtn = document.getElementById('upload-recovery-btn');
    if (uploadRecoveryBtn) {
        uploadRecoveryBtn.addEventListener('click', function() {
            const fileInput = document.getElementById('recovery-file');
            if (!fileInput || fileInput.files.length === 0) {
                showNotificationDialog('No File', 'Please select a recovery image file first', 'warning');
                return;
            }
            
            const file = fileInput.files[0];
            showNotificationDialog('Uploading', `Uploading recovery image: ${file.name}`, 'info');
            addLogEntry(`Uploading recovery image: ${file.name}`);
            
            setTimeout(() => {
                const currentRecovery = document.getElementById('current-recovery');
                if (currentRecovery) currentRecovery.textContent = `Current: ${file.name}`;
                showNotificationDialog('Upload Complete', 'Recovery image uploaded successfully', 'success');
                addLogEntry('Recovery image uploaded and verified');
            }, 2000);
        });
    }
}

// Send factory reset command with loading screen
async function sendFactoryReset(password) {
    // Show loading overlay
    showLoadingOverlay('Sending factory reset command...');
    addLogEntry('Initiating factory reset');
    
    try {
        const response = await fetch('/api/pipeline/factory-reset', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ password: password })
        });
        
        const result = await response.json();
        
        // Hide loading overlay
        hideLoadingOverlay();
        
        if (response.ok && result.success) {
            showNotificationDialog('Factory Reset', 'Factory reset command sent successfully! The device will reset shortly.', 'success');
            addLogEntry('Factory reset command sent to pipeline');
            
            // Update UI
            const statusText = document.getElementById('status-text');
            if (statusText) statusText.textContent = 'Factory Reset in Progress...';
            
            const currentOperation = document.getElementById('current-operation');
            if (currentOperation) currentOperation.textContent = 'Factory Resetting';
            
            const updateBadge = document.getElementById('update-badge');
            if (updateBadge) {
                updateBadge.classList.remove('hidden');
                updateBadge.classList.add('bg-red-500');
                updateBadge.textContent = 'Factory Reset';
            }
            
            // Show countdown dialog
            const countdownDialog = document.createElement('div');
            countdownDialog.className = 'fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50';
            countdownDialog.innerHTML = `
                <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-8 text-center">
                    <div class="flex justify-center mb-4">
                        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-red-600"></div>
                    </div>
                    <h3 class="text-lg font-semibold text-slate-800 mb-2">Factory Reset in Progress</h3>
                    <p class="text-sm text-slate-500 mb-4">The device will reset in <span id="countdown-number" class="font-bold text-red-600">10</span> seconds</p>
                    <div class="h-2 bg-slate-200 rounded-full overflow-hidden">
                        <div id="countdown-bar" class="h-full bg-red-600 transition-all duration-1000" style="width: 100%"></div>
                    </div>
                </div>
            `;
            document.body.appendChild(countdownDialog);
            
            let countdown = 10;
            const countdownInterval = setInterval(() => {
                countdown--;
                const countdownNumber = document.getElementById('countdown-number');
                const countdownBar = document.getElementById('countdown-bar');
                
                if (countdownNumber) countdownNumber.textContent = countdown;
                if (countdownBar) countdownBar.style.width = `${(countdown / 10) * 100}%`;
                
                if (countdown <= 0) {
                    clearInterval(countdownInterval);
                    if (countdownDialog && countdownDialog.parentNode) {
                        countdownDialog.parentNode.removeChild(countdownDialog);
                    }
                    simulateReboot('factory-reset');
                }
            }, 1000);
            
        } else {
            const errorMsg = result.error || 'Invalid password or command failed';
            showNotificationDialog('Factory Reset Failed', errorMsg, 'error');
            addLogEntry(`Factory reset failed: ${errorMsg}`);
        }
        
    } catch (error) {
        hideLoadingOverlay();
        console.error('Factory reset error:', error);
        showNotificationDialog('Connection Error', 'Failed to send factory reset command. Check network connection.', 'error');
        addLogEntry(`Factory reset error: ${error.message}`);
    }
}

// Initialize system status updates
function initializeSystemStatus() {
    const uptimeInterval = setInterval(() => {
        const uptimeElement = document.getElementById('uptime');
        if (uptimeElement) {
            const match = uptimeElement.textContent.match(/(\d+)d (\d+)h (\d+)m/);
            if (match) {
                let [_, days, hours, minutes] = match;
                minutes = parseInt(minutes) + 1;
                
                if (minutes >= 60) {
                    minutes = 0;
                    hours = parseInt(hours) + 1;
                }
                if (hours >= 24) {
                    hours = 0;
                    days = parseInt(days) + 1;
                }
                
                uptimeElement.textContent = `${days}d ${hours}h ${minutes}m`;
            }
        }
    }, 60000);
    
    window.otaUptimeInterval = uptimeInterval;
}

// Initialize live monitor
function initializeLiveMonitor() {
    const clearLogBtn = document.getElementById('clear-log');
    if (clearLogBtn) {
        clearLogBtn.addEventListener('click', function() {
            const logContainer = document.getElementById('log-container');
            if (logContainer) logContainer.innerHTML = '';
            addLogEntry('Log cleared');
        });
    }
}

// Initialize all buttons
function initializeButtons() {
    function addSafeEventListener(id, event, handler) {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener(event, handler);
            return true;
        }
        return false;
    }
    
    addSafeEventListener('save-btn', 'click', saveChanges);
    addSafeEventListener('reset-btn', 'click', () => {
        showConfirmDialog('Reset Settings', 'Reset all settings to defaults?', 'Reset', 'Cancel', () => {
            resetSettings();
        });
    });
    addSafeEventListener('cancel-btn', 'click', () => {
        if (deploymentInProgress) {
            showConfirmDialog('Cancel Deployment', 'Cancel deployment in progress?', 'Cancel Deployment', 'Continue', () => {
                cancelOperations();
            });
        } else {
            showNotificationDialog('No Operations', 'No operations to cancel', 'info');
        }
    });
    
    const snapshotBtn = document.getElementById('snapshot-btn');
    if (snapshotBtn) {
        snapshotBtn.addEventListener('click', function() {
            showLoadingOverlay('Creating system snapshot...');
            addLogEntry('Creating system snapshot');
            
            setTimeout(() => {
                hideLoadingOverlay();
                showNotificationDialog('Snapshot Created', 'System snapshot created successfully', 'success');
                addLogEntry('System snapshot saved');
            }, 2000);
        });
    }
    
    const debugBtn = document.getElementById('debug-btn');
    if (debugBtn) {
        debugBtn.addEventListener('click', function() {
            showLoadingOverlay('Collecting debug information...');
            addLogEntry('Starting debug bundle collection');
            
            setTimeout(() => {
                hideLoadingOverlay();
                showNotificationDialog('Debug Bundle', 'Debug bundle downloaded', 'success');
                addLogEntry('Debug bundle collection complete');
            }, 3000);
        });
    }
}

// Simulated operations
function simulateRollback() {
    showLoadingOverlay('Initiating rollback to Partition A...');
    addLogEntry('Starting rollback to Partition A');
    
    const partitionA = document.getElementById('partition-a');
    const partitionB = document.getElementById('partition-b');
    const partitionAStatus = document.getElementById('partition-a-status');
    const partitionBStatus = document.getElementById('partition-b-status');
    const partitionBNext = document.getElementById('partition-b-next');
    
    if (partitionA && partitionB) {
        partitionA.classList.remove('bg-green-50', 'border-green-200');
        partitionA.classList.add('bg-slate-50', 'border-slate-200', 'opacity-80');
        const partitionACheck = partitionA.querySelector('.fa-circle-check');
        if (partitionACheck) {
            partitionACheck.classList.remove('text-green-500');
            partitionACheck.classList.add('text-slate-400');
        }
        
        partitionB.classList.remove('bg-slate-50', 'border-slate-200', 'opacity-80');
        partitionB.classList.add('bg-green-50', 'border-green-200');
        const partitionBText = partitionB.querySelector('.text-slate-600');
        if (partitionBText) partitionBText.classList.replace('text-slate-600', 'text-green-600');
        
        if (partitionBNext) {
            partitionBNext.textContent = 'Active';
            partitionBNext.classList.replace('bg-blue-100', 'bg-green-100');
            partitionBNext.classList.replace('text-blue-700', 'text-green-700');
        }
        
        const partitionBIcon = partitionB.querySelector('.fa-solid');
        if (partitionBIcon) partitionBIcon.classList.replace('text-slate-400', 'text-green-500');
        
        if (partitionAStatus && partitionBStatus) {
            const tempStatus = partitionAStatus.textContent;
            partitionAStatus.textContent = partitionBStatus.textContent;
            partitionBStatus.textContent = tempStatus;
        }
    }
    
    setTimeout(() => {
        hideLoadingOverlay();
        showNotificationDialog('Rollback Complete', 'Rollback complete! System is now running on Partition A.', 'success');
        addLogEntry('Rollback completed successfully');
    }, 1500);
}

function simulateRestore() {
    showLoadingOverlay('Starting OS restore to v5.0.3...');
    addLogEntry('Initiating OS restore to v5.0.3');
    
    setTimeout(() => {
        hideLoadingOverlay();
        showNotificationDialog('Restore Complete', 'OS restore completed. Reboot required.', 'success');
        addLogEntry('OS restore completed');
    }, 3000);
}

function simulateReboot(version) {
    const rebootMessage = version === 'factory-reset' 
        ? 'Factory reset complete. Rebooting with factory defaults...'
        : `Rebooting into ${version}`;
    
    showNotificationDialog('System Reboot', rebootMessage, 'warning');
    addLogEntry(rebootMessage);
    
    const rebootOverlay = document.createElement('div');
    rebootOverlay.className = 'fixed inset-0 bg-slate-900 flex items-center justify-center z-50';
    rebootOverlay.innerHTML = `
        <div class="text-center">
            <div class="text-6xl mb-4 animate-spin">⚙️</div>
            <h3 class="text-2xl text-white font-bold mb-2">System Rebooting</h3>
            <p class="text-slate-300">${version === 'factory-reset' ? 'Factory reset complete. ' : 'Switching to ' + version + '. '}This may take up to 2 minutes.</p>
            <div class="mt-6 h-1 w-64 bg-slate-700 rounded-full overflow-hidden mx-auto">
                <div class="h-full bg-green-500 animate-pulse"></div>
            </div>
        </div>
    `;
    
    document.body.appendChild(rebootOverlay);
    
    setTimeout(() => {
        document.body.removeChild(rebootOverlay);
        
        if (version === 'factory-reset') {
            resetSettings();
            
            const osVersion = document.getElementById('os-version');
            const osStatus = document.getElementById('os-status');
            if (osVersion) osVersion.textContent = 'v5.0.1-factory';
            if (osStatus) {
                osStatus.textContent = 'FACTORY';
                osStatus.classList.remove('bg-green-100', 'text-green-700', 'bg-blue-100', 'text-blue-700');
                osStatus.classList.add('bg-slate-100', 'text-slate-700');
            }
            
            const partitionAStatus = document.getElementById('partition-a-status');
            const partitionBStatus = document.getElementById('partition-b-status');
            if (partitionAStatus) partitionAStatus.textContent = 'v5.0.1-factory • Factory Default';
            if (partitionBStatus) partitionBStatus.textContent = 'v5.0.1-factory • Target for OTA';
            
            const partitionA = document.getElementById('partition-a');
            const partitionB = document.getElementById('partition-b');
            if (partitionA) {
                partitionA.classList.add('bg-green-50', 'border-green-200');
                partitionA.classList.remove('bg-slate-50', 'opacity-80');
            }
            if (partitionB) {
                partitionB.classList.add('bg-slate-50', 'border-slate-200', 'opacity-80');
                partitionB.classList.remove('bg-green-50', 'border-green-200');
            }
            
            showNotificationDialog('Factory Reset Complete', 'System is now running factory defaults.', 'success');
            addLogEntry('Factory reset completed, system restored to factory defaults');
        } else {
            const osVersion = document.getElementById('os-version');
            const osStatus = document.getElementById('os-status');
            if (osVersion) osVersion.textContent = version;
            if (osStatus) {
                osStatus.textContent = version.includes('beta') ? 'TESTING' : 'STABLE';
                osStatus.classList.replace('bg-green-100', version.includes('beta') ? 'bg-blue-100' : 'bg-green-100');
                osStatus.classList.replace('text-green-700', version.includes('beta') ? 'text-blue-700' : 'text-green-700');
            }
            
            showNotificationDialog('Reboot Complete', `System is now running ${version}`, 'success');
            addLogEntry(`System rebooted into ${version}`);
        }
        
        const now = new Date();
        const formattedDate = now.toISOString().split('T')[0];
        const lastOta = document.getElementById('last-ota');
        if (lastOta) {
            lastOta.innerHTML = `${formattedDate} <span class="text-green-600 text-xs ml-1">(Success)</span>`;
        }
        
        setTimeout(() => {
            checkForUpdates(true);
        }, 3000);
    }, 5000);
}

// Save changes function
function saveChanges() {
    showNotificationDialog('Saving', 'Saving configuration changes...', 'info');
    addLogEntry('Saving configuration');
    
    setTimeout(() => {
        showNotificationDialog('Saved', 'Configuration saved successfully!', 'success');
        addLogEntry('Configuration saved');
    }, 1000);
}

// Reset settings
function resetSettings() {
    showNotificationDialog('Resetting', 'Resetting settings to defaults...', 'info');
    addLogEntry('Resetting all settings');
    
    const uploadIcon = document.getElementById('upload-icon');
    if (uploadIcon) {
        uploadIcon.innerHTML = '<i class="fa-solid fa-file-arrow-up text-blue-600 text-xl"></i>';
        uploadIcon.classList.remove('bg-green-50');
        uploadIcon.classList.add('bg-blue-50');
    }
    
    const uploadText = document.getElementById('upload-text');
    if (uploadText) {
        uploadText.textContent = 'Click to upload OS image';
        uploadText.classList.remove('font-mono', 'text-sm');
    }
    
    const uploadSubtext = document.getElementById('upload-subtext');
    if (uploadSubtext) uploadSubtext.textContent = 'or drag and drop (.img, .tar.gz, .squashfs)';
    
    const imageVersion = document.getElementById('image-version');
    if (imageVersion) imageVersion.value = '';
    
    const checksum = document.getElementById('checksum');
    if (checksum) checksum.value = '';
    
    const metadataKernel = document.getElementById('metadata-kernel');
    if (metadataKernel) {
        metadataKernel.textContent = '--';
        metadataKernel.className = 'font-mono text-slate-400';
    }
    
    const metadataBuild = document.getElementById('metadata-build');
    if (metadataBuild) {
        metadataBuild.textContent = '--';
        metadataBuild.className = 'font-mono text-slate-400';
    }
    
    const metadataSig = document.getElementById('metadata-sig');
    if (metadataSig) {
        metadataSig.textContent = 'Not Verified';
        metadataSig.className = 'font-mono text-slate-400';
    }
    
    const verifyBtn = document.getElementById('verify-btn');
    if (verifyBtn) {
        verifyBtn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Verify & Prepare Deployment';
        verifyBtn.disabled = true;
        verifyBtn.classList.remove('bg-green-600', 'bg-blue-600', 'text-white');
        verifyBtn.classList.add('bg-slate-200', 'text-slate-400', 'cursor-not-allowed');
    }
    
    const buttonContainer = document.getElementById('button-container');
    if (buttonContainer) buttonContainer.innerHTML = '';
    
    currentFile = null;
    
    const partitionBStatus = document.getElementById('partition-b-status');
    if (partitionBStatus) {
        partitionBStatus.textContent = 'v5.0.3 • Target for OTA';
        partitionBStatus.classList.remove('text-blue-600', 'text-amber-600', 'text-green-600', 'font-bold');
    }
    
    autoUpdateEnabled = true;
    const autoUpdateToggle = document.getElementById('auto-update-toggle');
    if (autoUpdateToggle) {
        autoUpdateToggle.innerHTML = '<i class="fa-solid fa-robot mr-2"></i> Auto-Update: On';
        autoUpdateToggle.className = 'px-4 py-2 text-sm font-medium bg-blue-100 hover:bg-blue-200 text-blue-700 rounded-md transition-colors';
    }
    
    const autoDownload = document.getElementById('auto-download');
    if (autoDownload) autoDownload.checked = true;
    
    const autoSecurity = document.getElementById('auto-security');
    if (autoSecurity) autoSecurity.checked = true;
    
    const autoReboot = document.getElementById('auto-reboot');
    if (autoReboot) autoReboot.checked = false;
    
    setTimeout(() => {
        showNotificationDialog('Reset Complete', 'Settings reset to defaults', 'success');
    }, 500);
}

// Cancel operations
function cancelOperations() {
    if (deploymentInProgress) {
        deploymentInProgress = false;
        
        if (updateDownloadInterval) {
            clearInterval(updateDownloadInterval);
            updateDownloadInterval = null;
        }
        
        const statusText = document.getElementById('status-text');
        if (statusText) statusText.textContent = 'System Idle';
        
        const currentOperation = document.getElementById('current-operation');
        if (currentOperation) currentOperation.textContent = 'Idle';
        
        const statusPercent = document.getElementById('status-percent');
        if (statusPercent) statusPercent.textContent = '0%';
        
        const progressFill = document.getElementById('progress-fill');
        if (progressFill) {
            progressFill.style.width = '0%';
            progressFill.className = 'h-full bg-green-500';
        }
        
        const downloadSpeed = document.getElementById('download-speed');
        if (downloadSpeed) downloadSpeed.textContent = '0 MB/s';
        
        const eta = document.getElementById('eta');
        if (eta) eta.textContent = '--:--';
        
        const integrityStatus = document.getElementById('integrity-status');
        if (integrityStatus) {
            integrityStatus.textContent = 'Pending';
            integrityStatus.className = 'text-green-400';
        }
        
        const updateBadge = document.getElementById('update-badge');
        if (updateBadge) updateBadge.classList.add('hidden');
        
        const partitionBStatus = document.getElementById('partition-b-status');
        if (partitionBStatus) partitionBStatus.textContent = 'v5.0.3 • Target for OTA';
        
        document.querySelectorAll('.install-update-btn').forEach(btn => {
            btn.disabled = false;
            btn.classList.remove('opacity-50', 'cursor-not-allowed');
        });
        
        document.querySelectorAll('button:not(#cancel-btn):not(#reset-btn)').forEach(btn => {
            btn.disabled = false;
            btn.classList.remove('opacity-50', 'cursor-not-allowed');
        });
        
        showNotificationDialog('Cancelled', 'Deployment cancelled', 'warning');
        addLogEntry('Deployment cancelled by user');
    } else {
        showNotificationDialog('No Operation', 'No operations to cancel', 'info');
    }
}

// Add log entry
function addLogEntry(message) {
    const logContainer = document.getElementById('log-container');
    if (!logContainer) return;
    
    const timestamp = new Date().toLocaleTimeString('en-US', {hour12: false});
    const logEntry = document.createElement('div');
    logEntry.textContent = `[${timestamp}] ${message}`;
    logContainer.appendChild(logEntry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

// Utility functions
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Clean up intervals on page unload
function cleanupOtaGateway() {
    if (updateCheckInterval) {
        clearInterval(updateCheckInterval);
        updateCheckInterval = null;
    }
    
    if (updateDownloadInterval) {
        clearInterval(updateDownloadInterval);
        updateDownloadInterval = null;
    }
    
    if (window.otaUptimeInterval) {
        clearInterval(window.otaUptimeInterval);
        window.otaUptimeInterval = null;
    }
    
    if (loadingOverlay) {
        loadingOverlay.remove();
        loadingOverlay = null;
    }
}

// Export for global access
window.cleanupOtaGateway = cleanupOtaGateway;