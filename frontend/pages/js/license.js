// pages/js/license.js

// This function will be called by the router when loading the page
window.initLicense = function() {
    console.log('License page initialized');
    
    // Create and initialize the license application
    window.licenseApp = new LicenseApplication();
    window.licenseApp.init();
};

class LicenseApplication {
    constructor() {
        this.appState = {
            licenseData: {
                type: 'pro',
                status: 'active',
                expiry: '2026-08-12',
                activationDate: '2024-03-15',
                gatewayId: 'GW-3920A9',
                cloudLinked: true,
                autoRenewal: true
            },
            features: [
                { id: 1, name: 'CraneIQ Pro', category: 'Safety', status: 'active', source: 'cloud', expiry: '2026-08-12', limits: 'Full Access', trial: false },
                { id: 2, name: 'Anti-Collision Module', category: 'Safety', status: 'active', source: 'cloud', expiry: '2026-08-12', limits: 'Full Access', trial: false },
                { id: 3, name: 'Rule Engine Pro', category: 'Automation', status: 'active', source: 'local', expiry: '2026-08-12', limits: 'Unlimited Rules', trial: false },
                { id: 4, name: 'Alerts & Event Pack', category: 'Monitoring', status: 'inactive', source: 'none', expiry: '--', limits: 'Basic Only', trial: false },
                { id: 5, name: 'Logging Pro', category: 'Diagnostics', status: 'active', source: 'cloud', expiry: '2026-08-12', limits: '1 Year Retention', trial: false },
                { id: 6, name: 'Protocol Expansion', category: 'Connectivity', status: 'active', source: 'local', expiry: '2026-08-12', limits: 'All Protocols', trial: false },
                { id: 7, name: 'Advanced Analytics', category: 'Analytics', status: 'trial', source: 'trial', expiry: '2024-04-10', limits: 'Limited Access', trial: true },
                { id: 8, name: 'Data Historian', category: 'Storage', status: 'inactive', source: 'none', expiry: '--', limits: '30 Days', trial: false }
            ],
            trials: [
                { id: 1, name: 'CraneIQ Pro Trial', daysLeft: 10, startDate: '2024-03-15', endDate: '2024-04-15' },
                { id: 2, name: 'Anti-Collision Module', daysLeft: 5, startDate: '2024-03-20', endDate: '2024-04-10' }
            ],
            licenseLogs: [
                { timestamp: '2024-03-20 14:30:22', type: 'sync', message: 'Synced with cloud - All entitlements updated', user: 'System' },
                { timestamp: '2024-03-20 09:15:45', type: 'activation', message: 'License key validated and activated', user: 'Admin' },
                { timestamp: '2024-03-19 16:20:33', type: 'trial', message: 'Started Advanced Analytics trial', user: 'Admin' },
                { timestamp: '2024-03-18 11:05:12', type: 'sync', message: 'Cloud subscription renewed - Enterprise tier', user: 'System' },
                { timestamp: '2024-03-15 10:30:00', type: 'activation', message: 'Pro license activated on gateway GW-3920A9', user: 'System' },
                { timestamp: '2024-03-10 15:45:22', type: 'feature', message: 'Anti-Collision module enabled', user: 'Admin' }
            ],
            unsavedChanges: false
        };
        
        // Systems
        this.modalSystem = null;
        this.toastSystem = null;
    }

    init() {
        console.log('License application initialized');
        
        // Initialize systems
        this.modalSystem = new ModalSystem();
        this.toastSystem = new ToastSystem();
        
        // Load initial data
        this.loadInitialData();
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Render dynamic content
        this.renderFeaturesTable();
        this.renderLicenseLogs();
    }

    loadInitialData() {
        // Update license overview
        this.updateLicenseOverview();
    }

    setupEventListeners() {
        // Cancel button
        const cancelBtn = document.getElementById('license-cancel-btn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                this.handleCancel();
            });
        }
        
        // Auto-sync toggle
        const autoSync = document.getElementById('autoSync');
        if (autoSync) {
            autoSync.addEventListener('change', () => {
                this.toastSystem.show(`Auto-sync ${autoSync.checked ? 'enabled' : 'disabled'}`, 'info');
                this.markUnsavedChanges();
            });
        }
        
        // Input change listeners
        document.querySelectorAll('#pageContent input, #pageContent select, #pageContent textarea').forEach(element => {
            element.addEventListener('change', () => {
                this.markUnsavedChanges();
            });
        });
    }

    handleCancel() {
        if (this.appState.unsavedChanges) {
            this.showConfirm({
                title: 'Discard Changes',
                message: 'Discard all unsaved license settings?',
                type: 'warning',
                onConfirm: () => {
                    window.location.reload();
                }
            });
        } else {
            window.location.reload();
        }
    }

    // ==================== MODAL & TOAST SYSTEMS ====================
    // Note: These should be moved to common.js for reuse across pages
    // For now, defining them here for completeness

    showConfirm(options) {
        const modal = new ModalSystem();
        
        const {
            title = 'Confirm Action',
            message = 'Are you sure you want to proceed?',
            confirmText = 'Confirm',
            cancelText = 'Cancel',
            type = 'warning',
            onConfirm = null,
            onCancel = null
        } = options;

        const content = document.createElement('div');
        content.style.cssText = `
            color: #475569;
            line-height: 1.5;
        `;
        content.innerHTML = `<p>${message}</p>`;

        modal.show({
            title,
            content,
            type,
            buttons: [
                {
                    text: cancelText,
                    onClick: () => {
                        if (onCancel) onCancel();
                    }
                },
                {
                    text: confirmText,
                    primary: true,
                    onClick: () => {
                        if (onConfirm) onConfirm();
                    }
                }
            ],
            onClose: onCancel
        });
    }

    showAlert(options) {
        const modal = new ModalSystem();
        
        const {
            title = 'Alert',
            message = '',
            type = 'info',
            buttonText = 'OK',
            onClose = null
        } = options;

        const content = document.createElement('div');
        content.style.cssText = `
            color: #475569;
            line-height: 1.5;
        `;
        content.innerHTML = `<p>${message}</p>`;

        modal.show({
            title,
            content,
            type,
            buttons: [{
                text: buttonText,
                primary: true,
                onClick: () => {
                    if (onClose) onClose();
                }
            }],
            onClose
        });
    }

    // ==================== FEATURES TABLE ====================
    renderFeaturesTable() {
        const tableBody = document.getElementById('features-table');
        if (!tableBody) return;

        tableBody.innerHTML = '';

        this.appState.features.forEach(feature => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-slate-50';
            
            // Status icon
            let statusIcon = '';
            let statusClass = '';
            let statusText = '';
            
            if (feature.status === 'active') {
                statusIcon = 'fa-check';
                statusClass = 'feature-active';
                statusText = 'Active';
            } else if (feature.status === 'trial') {
                statusIcon = 'fa-clock';
                statusClass = 'feature-trial';
                statusText = 'Trial';
            } else {
                statusIcon = 'fa-xmark';
                statusClass = 'feature-inactive';
                statusText = 'Inactive';
            }
            
            // Source badge
            let sourceBadge = '';
            if (feature.source === 'cloud') {
                sourceBadge = '<span class="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">Cloud</span>';
            } else if (feature.source === 'local') {
                sourceBadge = '<span class="text-xs bg-slate-100 text-slate-800 px-2 py-1 rounded">Local</span>';
            } else if (feature.source === 'trial') {
                sourceBadge = '<span class="text-xs bg-amber-100 text-amber-800 px-2 py-1 rounded">Trial</span>';
            } else {
                sourceBadge = '<span class="text-xs bg-slate-100 text-slate-800 px-2 py-1 rounded">--</span>';
            }
            
            row.innerHTML = `
                <td class="px-6 py-4">
                    <div class="flex items-center">
                        <div class="${statusClass} mr-3">
                            <i class="fa-solid ${statusIcon} text-xs"></i>
                        </div>
                        <div>
                            <div class="font-medium text-slate-900">${feature.name}</div>
                            <div class="text-xs text-slate-500">${feature.description || ''}</div>
                        </div>
                    </div>
                </td>
                <td class="px-6 py-4">
                    <span class="text-sm text-slate-700">${feature.category}</span>
                </td>
                <td class="px-6 py-4 text-center">
                    <span class="text-xs font-medium px-2 py-1 rounded ${feature.status === 'active' ? 'bg-success/20 text-success' : feature.status === 'trial' ? 'bg-warning/20 text-warning' : 'bg-slate-100 text-slate-600'}">
                        ${statusText}
                    </span>
                </td>
                <td class="px-6 py-4">
                    ${sourceBadge}
                </td>
                <td class="px-6 py-4">
                    <span class="text-sm text-slate-700">${feature.expiry}</span>
                </td>
                <td class="px-6 py-4">
                    <span class="text-sm text-slate-700">${feature.limits}</span>
                </td>
                <td class="px-6 py-4 text-right">
                    <button class="text-primary hover:text-primaryHover text-sm font-medium" onclick="window.licenseApp.toggleFeature(${feature.id})">
                        ${feature.status === 'active' ? 'Disable' : 'Enable'}
                    </button>
                </td>
            `;
            
            tableBody.appendChild(row);
        });
    }

    toggleFeature(featureId) {
        const feature = this.appState.features.find(f => f.id === featureId);
        if (!feature) return;

        this.showConfirm({
            title: feature.status === 'active' ? 'Disable Feature' : 'Enable Feature',
            message: feature.status === 'active' 
                ? `Disable ${feature.name}? This will restrict access to this feature.`
                : `Enable ${feature.name}? Ensure you have valid license entitlement.`,
            onConfirm: () => {
                feature.status = feature.status === 'active' ? 'inactive' : 'active';
                this.renderFeaturesTable();
                
                this.toastSystem.show(`${feature.name} ${feature.status === 'active' ? 'enabled' : 'disabled'}`, 'success');
                
                // Add to logs
                this.addLicenseLog('feature', `${feature.name} ${feature.status === 'active' ? 'enabled' : 'disabled'}`);
                
                this.markUnsavedChanges();
            }
        });
    }

    // ==================== LICENSE KEY MANAGEMENT ====================
    generateDemoKey() {
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
        let key = '';
        for (let i = 0; i < 24; i++) {
            if (i > 0 && i % 6 === 0) key += '-';
            key += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        document.getElementById('license-key').value = key;
    }

    validateLicense() {
        const licenseKey = document.getElementById('license-key').value.trim();
        if (!licenseKey) {
            this.toastSystem.show('Please enter a license key', 'warning');
            return;
        }

        this.toastSystem.show('Validating license key...', 'info');
        
        // Simulate validation
        setTimeout(() => {
            this.showConfirm({
                title: 'License Validated',
                message: `License key validated successfully. Activate Pro license with all premium features?`,
                type: 'success',
                onConfirm: () => {
                    this.toastSystem.show('License activated successfully!', 'success');
                    
                    // Update license data
                    this.appState.licenseData.type = 'pro';
                    this.appState.licenseData.status = 'active';
                    this.updateLicenseOverview();
                    
                    // Add to logs
                    this.addLicenseLog('activation', 'Pro license activated from key');
                    
                    this.markUnsavedChanges();
                }
            });
        }, 1500);
    }

    // ==================== CLOUD FUNCTIONS ====================
    syncWithCloud() {
        this.toastSystem.show('Syncing with cloud...', 'info');
        
        setTimeout(() => {
            this.toastSystem.show('Cloud sync completed successfully', 'success');
            this.addLicenseLog('sync', 'Manual cloud sync completed');
            this.markUnsavedChanges();
        }, 2000);
    }

    syncNow() {
        this.toastSystem.show('Starting immediate sync...', 'info');
        
        setTimeout(() => {
            this.toastSystem.show('Sync completed. 3 entitlements updated.', 'success');
            this.addLicenseLog('sync', 'Immediate sync requested');
            this.markUnsavedChanges();
        }, 1500);
    }

    // ==================== TRIAL FUNCTIONS ====================
    startTrial(feature) {
        const featureNames = {
            'rule-engine': 'Rule Engine Pro',
            'analytics': 'Advanced Analytics',
            'historian': 'Data Historian'
        };
        
        this.showConfirm({
            title: 'Start Trial',
            message: `Start 14-day trial for ${featureNames[feature]}?`,
            onConfirm: () => {
                this.toastSystem.show(`${featureNames[feature]} trial started`, 'success');
                
                // Add trial
                this.appState.trials.push({
                    id: this.appState.trials.length + 1,
                    name: featureNames[feature] + ' Trial',
                    daysLeft: 14,
                    startDate: new Date().toISOString().split('T')[0],
                    endDate: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
                });
                
                this.addLicenseLog('trial', `${featureNames[feature]} trial started`);
                this.markUnsavedChanges();
            }
        });
    }

    // ==================== LICENSE LOGS ====================
    renderLicenseLogs() {
        const logsContainer = document.getElementById('license-logs');
        if (!logsContainer) return;

        logsContainer.innerHTML = this.appState.licenseLogs.map(log => {
            let icon = '';
            let color = '';
            
            switch(log.type) {
                case 'activation':
                    icon = 'fa-key';
                    color = 'text-emerald-600';
                    break;
                case 'sync':
                    icon = 'fa-cloud-arrow-down';
                    color = 'text-blue-600';
                    break;
                case 'trial':
                    icon = 'fa-clock';
                    color = 'text-amber-600';
                        break;
                case 'feature':
                    icon = 'fa-toggle-on';
                    color = 'text-purple-600';
                    break;
                default:
                    icon = 'fa-info-circle';
                    color = 'text-slate-600';
            }
            
            return `
                <div class="flex items-start gap-3 p-3 border-b border-border last:border-0">
                    <i class="fa-solid ${icon} ${color} mt-1"></i>
                    <div class="flex-1">
                        <div class="text-sm text-slate-900">${log.message}</div>
                        <div class="text-xs text-slate-500 mt-1">${log.timestamp} • ${log.user}</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    addLicenseLog(type, message) {
        const now = new Date();
        const timestamp = now.toISOString().replace('T', ' ').substring(0, 19);
        
        this.appState.licenseLogs.unshift({
            timestamp,
            type,
            message,
            user: 'Admin'
        });
        
        // Keep only last 50 logs
        if (this.appState.licenseLogs.length > 50) {
            this.appState.licenseLogs.pop();
        }
        
        this.renderLicenseLogs();
    }

    // ==================== OTHER FUNCTIONS ====================
    updateLicenseOverview() {
        // Update UI based on current license data
        // This would update the DOM elements with current state
    }

    markUnsavedChanges() {
        this.appState.unsavedChanges = true;
        const saveBtn = document.querySelector('#license-footer button:last-child');
        if (saveBtn && !saveBtn.disabled) {
            saveBtn.classList.add('bg-orange-500', 'hover:bg-orange-600');
        }
    }

    // ==================== PUBLIC API ====================
    // These methods are called from HTML onclick handlers
    showRenewalOptions() { /* Implementation */ }
    showTransferModal() { /* Implementation */ }
    deactivateLicense() { /* Implementation */ }
    showAllFeatures() { /* Implementation */ }
    importLicenseFile() { /* Implementation */ }
    exportLicense() { /* Implementation */ }
    showLicenseHistory() { /* Implementation */ }
    showSyncSettings() { /* Implementation */ }
    unlinkCloud() { /* Implementation */ }
    upgradeTrial(trialId) { /* Implementation */ }
    extendTrial(trialId) { /* Implementation */ }
    cancelTrial(trialId) { /* Implementation */ }
    filterLogs(type) { /* Implementation */ }
    exportLogs() { /* Implementation */ }
    runLicenseCheck() { /* Implementation */ }
    showBackupModal() { /* Implementation */ }
    resetTrials() { /* Implementation */ }
    saveSettings() { /* Implementation */ }
}

// ModalSystem and ToastSystem classes (should be in common.js)
// Defining simplified versions here for completeness

class ModalSystem {
    constructor() {
        this.modalContainer = document.createElement('div');
        this.modalContainer.className = 'modal-backdrop';
        document.body.appendChild(this.modalContainer);
    }

    show(options) {
        // Simplified implementation
        console.log('Modal shown:', options.title);
    }

    hide() {
        // Simplified implementation
        console.log('Modal hidden');
    }
}

class ToastSystem {
    show(message, type = 'info', duration = 3000) {
        // Simplified implementation
        console.log('Toast:', message, type);
        
        // Use the existing showNotification from common.js if available
        if (typeof window.showNotification === 'function') {
            window.showNotification(message, type);
        }
    }
}