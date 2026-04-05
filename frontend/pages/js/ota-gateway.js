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
            showNotification('Update scheduled for 02:00 AM', 'info');
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
            showNotification(`Auto-download: ${this.checked ? 'Enabled' : 'Disabled'}`, 'info');
        });
    }
    
    const autoSecurity = document.getElementById('auto-security');
    if (autoSecurity) {
        autoSecurity.addEventListener('change', function() {
            showNotification(`Auto-install security updates: ${this.checked ? 'Enabled' : 'Disabled'}`, 'info');
        });
    }
    
    const autoReboot = document.getElementById('auto-reboot');
    if (autoReboot) {
        autoReboot.addEventListener('change', function() {
            showNotification(`Auto-reboot after install: ${this.checked ? 'Enabled' : 'Disabled'}`, 'info');
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
            currentUpdate = filteredUpdates[0]; // Show first available update
            showUpdateBanner(currentUpdate);
        }
        
        addLogEntry(`Update check completed. Found ${filteredUpdates.length} update(s)`);
        
        // Update last checked time in log
        const now = new Date();
        addLogEntry(`Last checked: ${now.toLocaleString()}`);
        
    }, 2000);
}

// Update the updates list UI
function updateUpdateList(updates) {
    const updatesList = document.getElementById('updates-list');
    if (!updatesList) return;
    
    // Update existing items
    updates.forEach((update, index) => {
        const item = updatesList.children[index];
        if (item) {
            // Update version
            const versionSpan = item.querySelector('.text-sm.font-bold');
            if (versionSpan) versionSpan.textContent = update.version + (update.type === 'security' ? ' Security Update' : ' Feature Update');
            
            // Update description
            const descP = item.querySelector('.text-sm.text-slate-600');
            if (descP) descP.textContent = update.description;
            
            // Update size
            const sizeSpan = item.querySelector('.fa-download').parentElement;
            if (sizeSpan) sizeSpan.innerHTML = `<i class="fa-solid fa-download mr-1"></i> Size: ${update.size}`;
            
            // Update install button
            const installBtn = item.querySelector('.install-update-btn');
            if (installBtn) {
                installBtn.setAttribute('data-version', update.version);
                installBtn.textContent = update.type === 'security' ? 'Install Now' : 'Install';
            }
            
            // Update badge
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
    
    showNotification(`Auto-update ${autoUpdateEnabled ? 'enabled' : 'disabled'}`, 'info');
    addLogEntry(`Auto-update ${autoUpdateEnabled ? 'enabled' : 'disabled'}`);
    
    if (autoUpdateEnabled) {
        // Check immediately when enabled
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
    
    // Auto-hide after 30 seconds
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
        showNotification('Another update is already in progress', 'warning');
        return;
    }
    
    deploymentInProgress = true;
    currentUpdate = update;
    
    showNotification(`Starting download of ${update.version}...`, 'info');
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
    let speed = 5 + Math.random() * 10; // Random speed between 5-15 MB/s
    const totalSize = parseInt(update.size) * 1024; // Convert MB to KB for calculation
    
    updateDownloadInterval = setInterval(() => {
        if (progress >= 100) {
            clearInterval(updateDownloadInterval);
            
            // Download complete, start verification
            setTimeout(() => {
                verifyUpdate(update);
            }, 500);
            return;
        }
        
        // Increment progress
        progress += Math.random() * 2;
        if (progress > 100) progress = 100;
        
        // Update UI
        const statusPercent = document.getElementById('status-percent');
        if (statusPercent) statusPercent.textContent = `${Math.round(progress)}%`;
        
        const progressFill = document.getElementById('progress-fill');
        if (progressFill) progressFill.style.width = `${progress}%`;
        
        // Update speed (vary slightly)
        speed = Math.max(3, speed + (Math.random() - 0.5) * 2);
        const downloadSpeed = document.getElementById('download-speed');
        if (downloadSpeed) downloadSpeed.textContent = `${speed.toFixed(1)} MB/s`;
        
        // Update ETA
        if (progress > 0) {
            const remaining = (100 - progress) / progress * (Date.now() - startTime) / 1000;
            const minutes = Math.floor(remaining / 60);
            const seconds = Math.floor(remaining % 60);
            const etaElement = document.getElementById('eta');
            if (etaElement) etaElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        }
        
        // Update progress bar color
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
        
        // Add log entries at milestones
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
    
    // Simulate verification process
    setTimeout(() => {
        if (integrityStatus) {
            integrityStatus.textContent = 'Verified ✓';
            integrityStatus.className = 'text-green-400';
        }
        addLogEntry(`Update verified successfully: ${update.version}`);
        
        // Start installation
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
    
    // Update partition B status
    const partitionBStatus = document.getElementById('partition-b-status');
    if (partitionBStatus) {
        partitionBStatus.innerHTML = `${update.version} • <span class="text-amber-600 font-bold animate-pulse">Installing...</span>`;
    }
    
    // Simulate installation
    setTimeout(() => {
        deploymentInProgress = false;
        if (updateDownloadInterval) {
            clearInterval(updateDownloadInterval);
            updateDownloadInterval = null;
        }
        
        // Installation complete
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
        
        // Update partition B status
        if (partitionBStatus) {
            partitionBStatus.innerHTML = `${update.version} • <span class="text-green-600 font-bold">Update complete</span>`;
        }
        
        // Enable install buttons
        document.querySelectorAll('.install-update-btn').forEach(btn => {
            btn.disabled = false;
            btn.classList.remove('opacity-50', 'cursor-not-allowed');
        });
        
        showNotification(`${update.version} installed successfully! Ready for reboot.`, 'success');
        addLogEntry(`Update installed successfully: ${update.version}`);
        
        // Update available updates list (remove installed update)
        const updateIndex = availableUpdates.findIndex(u => u.version === update.version);
        if (updateIndex !== -1) {
            availableUpdates.splice(updateIndex, 1);
            const osVersionElement = document.getElementById('os-version');
            const currentVersion = osVersionElement ? osVersionElement.textContent : '';
            updateUpdateList(availableUpdates.filter(u => u.version !== currentVersion));
        }
        
        // Create reboot button
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
    
    // Drag and drop events
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
        showNotification('Invalid file type. Please upload .img, .tar.gz, or .squashfs files.', 'error');
        return;
    }
    
    currentFile = file;
    
    // Update UI with file info
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
    
    // Enable verify button
    const verifyBtn = document.getElementById('verify-btn');
    if (verifyBtn) {
        verifyBtn.disabled = false;
        verifyBtn.classList.remove('bg-slate-200', 'text-slate-400', 'cursor-not-allowed');
        verifyBtn.classList.add('bg-blue-600', 'text-white', 'hover:bg-blue-700', 'cursor-pointer');
        verifyBtn.onclick = () => verifyAndPrepare(file);
    }
    
    // Auto-fill version from filename
    const versionInput = document.getElementById('image-version');
    if (versionInput) {
        const versionMatch = file.name.match(/v?\d+\.\d+\.\d+/);
        if (versionMatch) {
            versionInput.value = versionMatch[0];
        }
    }
    
    // Simulate checksum calculation
    simulateChecksum(file);
    
    showNotification(`File "${file.name}" uploaded successfully`, 'success');
    addLogEntry(`Manual upload: ${file.name} (${formatFileSize(file.size)})`);
}

// Simulate checksum calculation
function simulateChecksum(file) {
    const checksumInput = document.getElementById('checksum');
    if (!checksumInput) return;
    
    checksumInput.placeholder = 'Calculating...';
    
    setTimeout(() => {
        // Generate fake SHA256 (for demo)
        const fakeHash = 'sha256:' + Array.from({length: 64}, () => 
            Math.floor(Math.random() * 16).toString(16)).join('');
        checksumInput.value = fakeHash;
        checksumInput.placeholder = '';
        
        // Simulate metadata extraction
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
    showNotification(`Verifying ${file.name}...`, 'info');
    addLogEntry('Starting manual image verification');
    
    const verifyBtn = document.getElementById('verify-btn');
    if (!verifyBtn) return;
    
    verifyBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Verifying...';
    verifyBtn.disabled = true;
    
    // Simulate verification process
    setTimeout(() => {
        verifyBtn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Verified Successfully';
        verifyBtn.classList.remove('bg-blue-600');
        verifyBtn.classList.add('bg-green-600');
        
        showNotification('Image verified successfully! Ready for deployment to Partition B.', 'success');
        addLogEntry('Manual image verification passed');
        
        // Update partition B status
        const partitionBStatus = document.getElementById('partition-b-status');
        const versionInput = document.getElementById('image-version');
        const version = versionInput && versionInput.value ? versionInput.value : 'v5.1.0-rc1';
        
        if (partitionBStatus) {
            partitionBStatus.innerHTML = `${version} • <span class="text-blue-600 font-bold">Ready for update</span>`;
        }
        
        // Create deploy button
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
        showNotification('Another update is already in progress', 'warning');
        return;
    }
    
    deploymentInProgress = true;
    
    showNotification('Starting manual deployment to Partition B...', 'info');
    addLogEntry(`Initiating manual deployment of ${version} to Partition B`);
    
    // Update UI
    const partitionBStatus = document.getElementById('partition-b-status');
    if (partitionBStatus) {
        partitionBStatus.innerHTML = `${version} • <span class="text-amber-600 font-bold animate-pulse">Installing...</span>`;
    }
    
    // Update monitor
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
    
    // Disable action buttons during deployment
    document.querySelectorAll('button:not(#cancel-btn):not(#reset-btn)').forEach(btn => {
        if (!btn.id.includes('cancel') && !btn.id.includes('reset')) {
            btn.disabled = true;
            btn.classList.add('opacity-50', 'cursor-not-allowed');
        }
    });
    
    // Simulate manual deployment
    simulateManualDeployment(version);
}

// Simulate manual deployment
function simulateManualDeployment(version) {
    let progress = 0;
    
    const interval = setInterval(() => {
        if (progress >= 100) {
            clearInterval(interval);
            deploymentInProgress = false;
            
            // Deployment complete
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
            
            // Update partition B status
            const partitionBStatus = document.getElementById('partition-b-status');
            if (partitionBStatus) {
                partitionBStatus.innerHTML = `${version} • <span class="text-green-600 font-bold">Update complete</span>`;
            }
            
            // Enable action buttons
            document.querySelectorAll('button:not(#cancel-btn):not(#reset-btn)').forEach(btn => {
                btn.disabled = false;
                btn.classList.remove('opacity-50', 'cursor-not-allowed');
            });
            
            showNotification(`Manual deployment of ${version} completed! Ready for reboot.`, 'success');
            addLogEntry(`Manual deployment completed: ${version}`);
            
            // Create reboot button
            createRebootButton(version);
            return;
        }
        
        // Increment progress
        progress += Math.random() * 3;
        if (progress > 100) progress = 100;
        
        // Update progress
        const statusPercent = document.getElementById('status-percent');
        if (statusPercent) statusPercent.textContent = `${Math.round(progress)}%`;
        
        const progressFill = document.getElementById('progress-fill');
        if (progressFill) progressFill.style.width = `${progress}%`;
        
        // Add log entries
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
        if (confirm(`Reboot into updated Partition B (${version})? System will restart in 10 seconds.`)) {
            simulateReboot(version);
        }
    });
    
    buttonContainer.appendChild(rebootBtn);
}

// Initialize radio buttons
function initializeRadioButtons() {
    const radios = document.querySelectorAll('input[name="strategy"]');
    radios.forEach(radio => {
        radio.addEventListener('change', function() {
            // Remove active styles from all labels
            document.querySelectorAll('label[id^="strategy-"]').forEach(label => {
                label.classList.remove('border-blue-500', 'bg-blue-50');
                label.classList.add('border-slate-200');
                label.querySelector('span').classList.remove('text-blue-900');
                label.querySelector('span').classList.add('text-slate-700');
            });
            
            // Add active style to selected label
            const label = this.closest('label');
            label.classList.remove('border-slate-200');
            label.classList.add('border-blue-500', 'bg-blue-50');
            label.querySelector('span').classList.remove('text-slate-700');
            label.querySelector('span').classList.add('text-blue-900');
            
            const strategyName = this.value === 'seamless' ? 'Seamless A/B' : 'Maintenance Window';
            showNotification(`Update strategy changed to: ${strategyName}`, 'info');
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
                showNotification('Force override enabled. Safety constraints will be ignored!', 'warning');
                
                // Show PIN prompt
                setTimeout(() => {
                    const pin = prompt('Enter admin PIN to confirm force override:');
                    if (pin !== '7392') { // Default PIN for demo
                        this.checked = false;
                        if (forceWarning) forceWarning.classList.add('hidden');
                        showNotification('Invalid PIN. Force override cancelled.', 'error');
                    } else {
                        showNotification('Force override confirmed. Proceed with caution!', 'warning');
                        addLogEntry('Force override enabled (Admin PIN verified)');
                    }
                }, 300);
            } else {
                if (forceWarning) forceWarning.classList.add('hidden');
                showNotification('Force override disabled. Safety constraints active.', 'info');
                addLogEntry('Force override disabled');
            }
        });
    }
}

// ============================================================================
// FACTORY RESET FUNCTIONALITY
// ============================================================================

// Show factory reset password dialog
function showFactoryResetDialog() {
    // Create modal overlay
    const modal = document.createElement('div');
    modal.id = 'factory-reset-modal';
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
    modal.innerHTML = `
        <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-lg font-bold text-red-600 flex items-center">
                    <i class="fa-solid fa-triangle-exclamation mr-2"></i>
                    Factory Reset
                </h3>
                <button id="close-modal-btn" class="text-slate-400 hover:text-slate-600">
                    <i class="fa-solid fa-xmark text-xl"></i>
                </button>
            </div>
            <div class="mb-4">
                <div class="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
                    <p class="text-sm text-red-700">
                        <i class="fa-solid fa-circle-exclamation mr-1"></i>
                        <strong>Warning:</strong> This will trigger a factory reset on the gateway device.
                        All configuration and data may be wiped. This action cannot be undone.
                    </p>
                </div>
                <label class="block text-sm font-medium text-slate-700 mb-2">
                    Enter Admin Password
                </label>
                <input type="password" id="factory-reset-password" 
                    class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-red-500"
                    placeholder="Enter your admin password">
            </div>
            <div class="flex space-x-3">
                <button id="confirm-factory-reset-btn" 
                    class="flex-1 bg-red-600 hover:bg-red-700 text-white font-medium py-2 rounded-lg transition-colors">
                    Confirm Factory Reset
                </button>
                <button id="cancel-factory-reset-btn" 
                    class="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium py-2 rounded-lg transition-colors">
                    Cancel
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Focus the password input
    const passwordInput = document.getElementById('factory-reset-password');
    if (passwordInput) {
        setTimeout(() => passwordInput.focus(), 100);
    }
    
    // Close modal function
    const closeModal = () => {
        if (modal && modal.parentNode) {
            modal.parentNode.removeChild(modal);
        }
    };
    
    // Handle confirm button click
    const confirmBtn = document.getElementById('confirm-factory-reset-btn');
    if (confirmBtn) {
        confirmBtn.addEventListener('click', async () => {
            const password = passwordInput ? passwordInput.value : '';
            
            if (!password) {
                showNotification('Please enter your admin password', 'warning');
                return;
            }
            
            // Disable buttons during request
            confirmBtn.disabled = true;
            confirmBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Sending...';
            const cancelBtn = document.getElementById('cancel-factory-reset-btn');
            if (cancelBtn) cancelBtn.disabled = true;
            
            try {
                // Send factory reset command to backend
                const response = await fetch('/api/pipeline/factory-reset', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ password: password })
                });
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    // Success - show success message and close modal
                    closeModal();
                    showNotification('Factory reset command sent successfully! The device will reset shortly.', 'success');
                    addLogEntry('Factory reset command sent via pipeline');
                    
                    // Update UI to show factory reset is in progress
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
                    
                    // Simulate reset countdown (take 1 minute to simulate DB restore)
                    let countdown = 60;
                    const countdownInterval = setInterval(() => {
                        const statusTextEl = document.getElementById('status-text');
                        if (statusTextEl) {
                            statusTextEl.textContent = `Restoring DB Configuration: ${countdown}s remaining...`;
                        }
                        
                        // Update progress bar
                        const progressFill = document.getElementById('progress-fill');
                        const statusPercent = document.getElementById('status-percent');
                        if (progressFill && statusPercent) {
                            const percent = Math.round(((60 - countdown) / 60) * 100);
                            progressFill.style.width = `${percent}%`;
                            progressFill.className = 'h-full bg-red-500 transition-all duration-1000';
                            statusPercent.textContent = `${percent}%`;
                            statusPercent.className = 'text-red-500 font-bold';
                        }
                        
                        // Add occasional log entries
                        if (countdown % 15 === 0 && countdown > 0) {
                            addLogEntry(`Restoring tables... ${countdown}s left`);
                        }

                        countdown--;
                        
                        if (countdown < 0) {
                            clearInterval(countdownInterval);
                            // Simulate reboot after factory reset
                            if (statusTextEl) statusTextEl.textContent = 'Database Restored. Rebooting...';
                            simulateReboot('factory-reset');
                        }
                    }, 1000);
                    
                } else {
                    // Error - show error message
                    const errorMsg = result.error || 'Invalid password or command failed';
                    showNotification(`Factory reset failed: ${errorMsg}`, 'error');
                    addLogEntry(`Factory reset failed: ${errorMsg}`);
                    
                    // Re-enable buttons
                    if (confirmBtn) {
                        confirmBtn.disabled = false;
                        confirmBtn.innerHTML = 'Confirm Factory Reset';
                    }
                    if (cancelBtn) cancelBtn.disabled = false;
                }
                
            } catch (error) {
                console.error('Factory reset error:', error);
                showNotification('Failed to send factory reset command. Check network connection.', 'error');
                addLogEntry(`Factory reset error: ${error.message}`);
                
                // Re-enable buttons
                if (confirmBtn) {
                    confirmBtn.disabled = false;
                    confirmBtn.innerHTML = 'Confirm Factory Reset';
                }
                if (cancelBtn) cancelBtn.disabled = false;
            }
        });
    }
    
    // Handle cancel button click
    const cancelBtn = document.getElementById('cancel-factory-reset-btn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', closeModal);
    }
    
    // Handle close button click
    const closeBtn = document.getElementById('close-modal-btn');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeModal);
    }
    
    // Close modal when clicking outside
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });
    
    // Handle Enter key in password input
    if (passwordInput) {
        passwordInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const confirmBtn = document.getElementById('confirm-factory-reset-btn');
                if (confirmBtn) {
                    confirmBtn.click();
                }
            }
        });
    }
}

// ============================================================================
// END FACTORY RESET FUNCTIONALITY
// ============================================================================

// Initialize recovery buttons
function initializeRecoveryButtons() {
    // Rollback button
    const rollbackBtn = document.getElementById('rollback-btn');
    if (rollbackBtn) {
        rollbackBtn.addEventListener('click', function() {
            if (confirm('Are you sure you want to rollback to Partition A? This will switch active partition immediately.')) {
                simulateRollback();
            }
        });
    }
    
    // Restore button
    const restoreBtn = document.getElementById('restore-btn');
    if (restoreBtn) {
        restoreBtn.addEventListener('click', function() {
            if (confirm('Restore previous OS version v5.0.3? This will overwrite current partition.')) {
                simulateRestore();
            }
        });
    }
    
    // Factory reset button - NEW IMPLEMENTATION
    const factoryBtn = document.getElementById('factory-btn');
    if (factoryBtn) {
        // Remove any existing listeners by cloning and replacing
        const newFactoryBtn = factoryBtn.cloneNode(true);
        factoryBtn.parentNode.replaceChild(newFactoryBtn, factoryBtn);
        
        newFactoryBtn.addEventListener('click', function() {
            // Show password prompt dialog
            showFactoryResetDialog();
        });
    }
    
    // Recovery image upload
    const uploadRecoveryBtn = document.getElementById('upload-recovery-btn');
    if (uploadRecoveryBtn) {
        uploadRecoveryBtn.addEventListener('click', function() {
            const fileInput = document.getElementById('recovery-file');
            if (!fileInput || fileInput.files.length === 0) {
                showNotification('Please select a recovery image file first', 'warning');
                return;
            }
            
            const file = fileInput.files[0];
            showNotification(`Uploading recovery image: ${file.name}`, 'info');
            addLogEntry(`Uploading recovery image: ${file.name}`);
            
            // Simulate upload
            setTimeout(() => {
                const currentRecovery = document.getElementById('current-recovery');
                if (currentRecovery) currentRecovery.textContent = `Current: ${file.name}`;
                showNotification('Recovery image uploaded successfully', 'success');
                addLogEntry('Recovery image uploaded and verified');
            }, 2000);
        });
    }
}

// Initialize system status updates
function initializeSystemStatus() {
    // Update uptime every minute
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
    
    // Store interval for cleanup
    window.otaUptimeInterval = uptimeInterval;
}

// Initialize live monitor
function initializeLiveMonitor() {
    // Clear log button
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
    // Helper function to safely add event listener
    function addSafeEventListener(id, event, handler) {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener(event, handler);
            return true;
        }
        return false;
    }
    
    // Add event listeners safely
    addSafeEventListener('save-btn', 'click', saveChanges);
    addSafeEventListener('reset-btn', 'click', () => {
        if (confirm('Reset all settings to defaults?')) {
            resetSettings();
        }
    });
    addSafeEventListener('cancel-btn', 'click', () => {
        if (confirm('Cancel all pending operations?')) {
            cancelOperations();
        }
    });
    
    // Required buttons (these should exist in the OTA Gateway HTML)
    const snapshotBtn = document.getElementById('snapshot-btn');
    if (snapshotBtn) {
        snapshotBtn.addEventListener('click', function() {
            showNotification('Creating system snapshot...', 'info');
            addLogEntry('Creating system snapshot');
            
            setTimeout(() => {
                showNotification('System snapshot created successfully', 'success');
                addLogEntry('System snapshot saved');
            }, 2000);
        });
    }
    
    const debugBtn = document.getElementById('debug-btn');
    if (debugBtn) {
        debugBtn.addEventListener('click', function() {
            showNotification('Collecting debug information...', 'info');
            addLogEntry('Starting debug bundle collection');
            
            setTimeout(() => {
                showNotification('Debug bundle downloaded', 'success');
                addLogEntry('Debug bundle collection complete');
            }, 3000);
        });
    }
}

// Simulated operations
function simulateRollback() {
    showNotification('Initiating rollback to Partition A...', 'warning');
    addLogEntry('Starting rollback to Partition A');
    
    const partitionA = document.getElementById('partition-a');
    const partitionB = document.getElementById('partition-b');
    const partitionAStatus = document.getElementById('partition-a-status');
    const partitionBStatus = document.getElementById('partition-b-status');
    const partitionBNext = document.getElementById('partition-b-next');
    
    if (partitionA && partitionB) {
        // Swap partition styles
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
        
        // Swap status text
        if (partitionAStatus && partitionBStatus) {
            const tempStatus = partitionAStatus.textContent;
            partitionAStatus.textContent = partitionBStatus.textContent;
            partitionBStatus.textContent = tempStatus;
        }
    }
    
    setTimeout(() => {
        showNotification('Rollback complete! System is now running on Partition A.', 'success');
        addLogEntry('Rollback completed successfully');
    }, 1500);
}

function simulateRestore() {
    showNotification('Starting OS restore to v5.0.3...', 'info');
    addLogEntry('Initiating OS restore to v5.0.3');
    
    setTimeout(() => {
        showNotification('OS restore completed. Reboot required.', 'success');
        addLogEntry('OS restore completed');
    }, 3000);
}

function simulateReboot(version) {
    const rebootMessage = version === 'factory-reset' 
        ? 'Factory reset complete. Rebooting with factory defaults...'
        : `Rebooting into ${version}`;
    
    showNotification(rebootMessage, 'warning');
    addLogEntry(rebootMessage);
    
    // Show reboot overlay
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
    
    // Simulate reboot completion
    setTimeout(() => {
        document.body.removeChild(rebootOverlay);
        
        if (version === 'factory-reset') {
            // Reset all UI to factory defaults
            resetSettings();
            
            // Update system info to factory version
            const osVersion = document.getElementById('os-version');
            const osStatus = document.getElementById('os-status');
            if (osVersion) osVersion.textContent = 'v5.0.1-factory';
            if (osStatus) {
                osStatus.textContent = 'FACTORY';
                osStatus.classList.remove('bg-green-100', 'text-green-700', 'bg-blue-100', 'text-blue-700');
                osStatus.classList.add('bg-slate-100', 'text-slate-700');
            }
            
            // Reset partition status
            const partitionAStatus = document.getElementById('partition-a-status');
            const partitionBStatus = document.getElementById('partition-b-status');
            if (partitionAStatus) partitionAStatus.textContent = 'v5.0.1-factory • Factory Default';
            if (partitionBStatus) partitionBStatus.textContent = 'v5.0.1-factory • Target for OTA';
            
            // Reset partition styling
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
            
            showNotification('Factory reset complete! System is now running factory defaults.', 'success');
            addLogEntry('Factory reset completed, system restored to factory defaults');
        } else {
            // Update system info
            const osVersion = document.getElementById('os-version');
            const osStatus = document.getElementById('os-status');
            if (osVersion) osVersion.textContent = version;
            if (osStatus) {
                osStatus.textContent = version.includes('beta') ? 'TESTING' : 'STABLE';
                osStatus.classList.replace('bg-green-100', version.includes('beta') ? 'bg-blue-100' : 'bg-green-100');
                osStatus.classList.replace('text-green-700', version.includes('beta') ? 'text-blue-700' : 'text-green-700');
            }
            
            showNotification(`Reboot complete! System is now running ${version}`, 'success');
            addLogEntry(`System rebooted into ${version}`);
        }
        
        // Update last OTA date
        const now = new Date();
        const formattedDate = now.toISOString().split('T')[0];
        const lastOta = document.getElementById('last-ota');
        if (lastOta) {
            lastOta.innerHTML = `${formattedDate} <span class="text-green-600 text-xs ml-1">(Success)</span>`;
        }
        
        // Check for updates after reboot
        setTimeout(() => {
            checkForUpdates(true);
        }, 3000);
    }, 5000);
}

// Save changes function
function saveChanges() {
    showNotification('Saving configuration changes...', 'info');
    addLogEntry('Saving configuration');
    
    // Collect settings
    const strategyRadio = document.querySelector('input[name="strategy"]:checked');
    const strategy = strategyRadio ? strategyRadio.value : 'seamless';
    
    const safety = {
        crane: document.getElementById('crane-safety')?.checked || false,
        acs: document.getElementById('acs-safety')?.checked || false,
        ups: document.getElementById('ups-safety')?.checked || false,
        force: document.getElementById('force-toggle')?.checked || false
    };
    
    // Auto-update settings
    const autoSettings = {
        download: document.getElementById('auto-download')?.checked || false,
        security: document.getElementById('auto-security')?.checked || false,
        reboot: document.getElementById('auto-reboot')?.checked || false
    };
    
    // Simulate API call
    setTimeout(() => {
        showNotification('Configuration saved successfully!', 'success');
        addLogEntry('Configuration saved');
    }, 1000);
}

// Reset settings
function resetSettings() {
    showNotification('Resetting settings to defaults...', 'info');
    addLogEntry('Resetting all settings');
    
    // Reset file upload
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
    
    // Reset inputs
    const imageVersion = document.getElementById('image-version');
    if (imageVersion) imageVersion.value = '';
    
    const checksum = document.getElementById('checksum');
    if (checksum) checksum.value = '';
    
    // Reset metadata
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
    
    // Reset verify button
    const verifyBtn = document.getElementById('verify-btn');
    if (verifyBtn) {
        verifyBtn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Verify & Prepare Deployment';
        verifyBtn.disabled = true;
        verifyBtn.classList.remove('bg-green-600', 'bg-blue-600', 'text-white');
        verifyBtn.classList.add('bg-slate-200', 'text-slate-400', 'cursor-not-allowed');
    }
    
    // Clear button container
    const buttonContainer = document.getElementById('button-container');
    if (buttonContainer) buttonContainer.innerHTML = '';
    
    // Reset current file
    currentFile = null;
    
    // Reset partition B status
    const partitionBStatus = document.getElementById('partition-b-status');
    if (partitionBStatus) {
        partitionBStatus.textContent = 'v5.0.3 • Target for OTA';
        partitionBStatus.classList.remove('text-blue-600', 'text-amber-600', 'text-green-600', 'font-bold');
    }
    
    // Reset auto-update toggle
    autoUpdateEnabled = true;
    const autoUpdateToggle = document.getElementById('auto-update-toggle');
    if (autoUpdateToggle) {
        autoUpdateToggle.innerHTML = '<i class="fa-solid fa-robot mr-2"></i> Auto-Update: On';
        autoUpdateToggle.className = 'px-4 py-2 text-sm font-medium bg-blue-100 hover:bg-blue-200 text-blue-700 rounded-md transition-colors';
    }
    
    // Reset auto-update checkboxes
    const autoDownload = document.getElementById('auto-download');
    if (autoDownload) autoDownload.checked = true;
    
    const autoSecurity = document.getElementById('auto-security');
    if (autoSecurity) autoSecurity.checked = true;
    
    const autoReboot = document.getElementById('auto-reboot');
    if (autoReboot) autoReboot.checked = false;
    
    setTimeout(() => {
        showNotification('Settings reset to defaults', 'success');
    }, 500);
}

// Cancel operations
function cancelOperations() {
    if (deploymentInProgress) {
        if (confirm('Cancel deployment in progress?')) {
            deploymentInProgress = false;
            
            // Stop download/installation
            if (updateDownloadInterval) {
                clearInterval(updateDownloadInterval);
                updateDownloadInterval = null;
            }
            
            // Reset monitor UI
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
            
            // Reset partition B status
            const partitionBStatus = document.getElementById('partition-b-status');
            if (partitionBStatus) partitionBStatus.textContent = 'v5.0.3 • Target for OTA';
            
            // Enable install buttons
            document.querySelectorAll('.install-update-btn').forEach(btn => {
                btn.disabled = false;
                btn.classList.remove('opacity-50', 'cursor-not-allowed');
            });
            
            // Enable other buttons
            document.querySelectorAll('button:not(#cancel-btn):not(#reset-btn)').forEach(btn => {
                btn.disabled = false;
                btn.classList.remove('opacity-50', 'cursor-not-allowed');
            });
            
            showNotification('Deployment cancelled', 'warning');
            addLogEntry('Deployment cancelled by user');
        }
    } else {
        showNotification('No operations to cancel', 'info');
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

function showNotification(message, type = 'info') {
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
}

// Export for global access
window.cleanupOtaGateway = cleanupOtaGateway;