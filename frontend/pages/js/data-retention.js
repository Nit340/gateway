// This function will be called by the router when loading the page
window.initDataRetention = function() {
    console.log('Data Retention page initialized');
    
    // Initialize all functionality for this page
    initializeDataRetention();
};

function initializeDataRetention() {
    console.log('Setting up Data Retention page functionality');
    
    // Initialize application state
    initializeAppState();
    
    // Initialize button handlers
    initializeButtons();
    
    // Initialize form interactions
    initializeFormInteractions();
    
    // Initialize modal system
    initializeModals();
    
    console.log('Data Retention page setup complete');
}

// ==================== APPLICATION STATE ====================
function initializeAppState() {
    window.dataRetentionState = {
        unsavedChanges: false,
        storageUsage: {
            total: 4096,
            used: 1380,
            remaining: 2716
        }
    };
}

// ==================== BUTTON HANDLERS ====================
function initializeButtons() {
    // Handle Save button
    const saveBtn = document.getElementById('save-btn');
    if (saveBtn) {
        saveBtn.addEventListener('click', function() {
            handleSaveAllSettings();
        });
    }
    
    // Handle gateway select change
    const gatewaySelect = document.getElementById('gateway-select');
    if (gatewaySelect) {
        gatewaySelect.addEventListener('change', function() {
            if (window.dataRetentionState.unsavedChanges) {
                showConfirm({
                    title: 'Switch Gateway',
                    message: 'Switch to another gateway? Unsaved retention settings will be lost.',
                    onConfirm: () => {
                        window.location.reload();
                    },
                    onCancel: () => {
                        this.value = 'Univa-GW-01';
                    }
                });
            } else {
                window.location.reload();
            }
        });
    }
}

// ==================== FORM INTERACTIONS ====================
function initializeFormInteractions() {
    // Mark unsaved changes on any form change
    document.querySelectorAll('input, select, textarea').forEach(element => {
        element.addEventListener('change', function() {
            markUnsavedChanges();
        });
    });
    
    // Initialize toggle switches
    document.querySelectorAll('.toggle-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', markUnsavedChanges);
    });
}

function markUnsavedChanges() {
    window.dataRetentionState.unsavedChanges = true;
    
    const saveBtn = document.getElementById('save-btn');
    if (saveBtn) {
        saveBtn.classList.add('bg-orange-500', 'hover:bg-orange-600');
    }
}

// ==================== MODAL SYSTEM ====================
function initializeModals() {
    // This will use the showNotification and showConfirmationDialog from common.js
    // If custom modals are needed, they can be added here
}

// ==================== MANUAL ACTION FUNCTIONS ====================
function exportStoredData() {
    showConfirmationDialog('Export all stored data to external storage? This may take several minutes.', 'Export', 'Cancel')
        .then(confirmed => {
            if (confirmed) {
                showNotification('Starting data export...', 'info');
                setTimeout(() => {
                    showNotification('Data export completed successfully', 'success');
                }, 3000);
            }
        });
}

function clearNonCriticalData() {
    showConfirmationDialog('Clear all non-critical data (telemetry, events, alerts)? Critical safety logs will be preserved.', 'Clear', 'Cancel')
        .then(confirmed => {
            if (confirmed) {
                showNotification('Clearing non-critical data...', 'warning');
                setTimeout(() => {
                    showNotification('Non-critical data cleared successfully', 'success');
                    markUnsavedChanges();
                }, 2000);
            }
        });
}

function fullResetStorage() {
    showConfirmationDialog('Reset ALL storage including critical safety logs? This action is irreversible and requires administrator approval.', 'Reset All Data', 'Cancel')
        .then(confirmed => {
            if (confirmed) {
                const adminPassword = prompt('Enter administrator password to confirm full storage reset:');
                if (adminPassword === 'admin123') {
                    showNotification('Resetting all storage...', 'error');
                    setTimeout(() => {
                        showNotification('Storage fully reset. System will restart.', 'success');
                        setTimeout(() => {
                            window.location.reload();
                        }, 2000);
                    }, 3000);
                } else {
                    showNotification('Administrator password incorrect. Reset cancelled.', 'error');
                }
            }
        });
}

// ==================== OTHER ACTION FUNCTIONS ====================
function runDiagnostics() {
    showNotification('Running system diagnostics...', 'info');
    setTimeout(() => {
        showNotification('Diagnostics completed successfully', 'success');
    }, 2000);
}

function exportLogsNow() {
    showConfirmationDialog('Export all logs now? This may take several minutes.', 'Export', 'Cancel')
        .then(confirmed => {
            if (confirmed) {
                showNotification('Starting log export...', 'info');
                setTimeout(() => {
                    showNotification('Log export completed successfully', 'success');
                }, 3000);
            }
        });
}

function purgeOldData() {
    showConfirmationDialog('Purge data older than retention policy? This will permanently delete old data.', 'Purge', 'Cancel')
        .then(confirmed => {
            if (confirmed) {
                showNotification('Purging old data...', 'warning');
                setTimeout(() => {
                    showNotification('Old data purged successfully', 'success');
                    markUnsavedChanges();
                }, 2000);
            }
        });
}

function showStorageAnalytics() {
    // Simple notification for now - can be expanded to a modal
    showNotification('Storage analytics feature coming soon!', 'info');
}

// ==================== SETTINGS MANAGEMENT ====================
function handleSaveAllSettings() {
    const settings = {
        storageSummary: {
            highUsageWarning: document.getElementById('highUsageWarning').value,
            criticalPurgeTrigger: document.getElementById('criticalPurgeTrigger').value
        },
        dataCategories: {
            telemetry: {
                enabled: document.getElementById('telemetryEnabled').checked,
                retention: document.getElementById('telemetryRetention').value,
                maxSize: document.getElementById('telemetryMaxSize').value,
                compression: document.getElementById('telemetryCompression').value,
                purgePriority: document.getElementById('telemetryPriority').value,
                syncBeforeDelete: document.getElementById('telemetrySync').checked
            },
            events: {
                enabled: document.getElementById('eventsEnabled').checked,
                retention: document.getElementById('eventsRetention').value,
                maxSize: document.getElementById('eventsMaxSize').value,
                compression: document.getElementById('eventsCompression').value,
                purgePriority: document.getElementById('eventsPriority').value,
                syncBeforeDelete: document.getElementById('eventsSync').checked
            },
            alerts: {
                enabled: document.getElementById('alertsEnabled').checked,
                retention: document.getElementById('alertsRetention').value,
                maxSize: document.getElementById('alertsMaxSize').value,
                compression: document.getElementById('alertsCompression').value,
                purgePriority: document.getElementById('alertsPriority').value,
                syncBeforeDelete: document.getElementById('alertsSync').checked
            },
            craneiq: {
                enabled: document.getElementById('craneiqEnabled').checked,
                retention: document.getElementById('craneiqRetention').value,
                maxSize: document.getElementById('craneiqMaxSize').value,
                compression: document.getElementById('craneiqCompression').value,
                purgePriority: 'critical',
                syncBeforeDelete: true
            },
            ota: {
                enabled: document.getElementById('otaEnabled').checked,
                retention: document.getElementById('otaRetention').value,
                maxSize: document.getElementById('otaMaxSize').value,
                compression: document.getElementById('otaCompression').value,
                purgePriority: document.getElementById('otaPriority').value
            }
        },
        offlineBuffering: {
            enabled: document.getElementById('offlineBuffering').checked,
            maxQueueSize: document.getElementById('maxQueueSize').value,
            retryInterval: document.getElementById('retryInterval').value,
            maxRetryTime: document.getElementById('maxRetryTime').value
        }
    };
    
    const saveBtn = document.getElementById('save-btn');
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
        
        // Clear unsaved changes flag
        window.dataRetentionState.unsavedChanges = false;
        
        // Show notification
        showNotification('Retention settings saved successfully!', 'success');
        
        console.log('Saved settings:', settings);
    }, 1500);
}