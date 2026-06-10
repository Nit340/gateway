// alerts.js - Alert Messages & Event Classes Page Script
// STATIC VERSION - No WebSockets, no backend connections

if (typeof window.alertsLoaded === 'undefined') {
    window.alertsLoaded = true;

    // ========== NOTIFICATION SYSTEM ==========
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
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.classList.add('fade-out');
                setTimeout(() => notification.remove(), 300);
            }
        }, 3000);
    }

    // ========== WINDOW ACTIONS ==========
    window.editAlertClass = function(id) {
        const classNames = {1: 'Critical', 2: 'High', 3: 'Warning', 4: 'Info', 5: 'Low'};
        showNotification(`Edit "${classNames[id]}" class — coming soon`, 'info');
    };

    window.deleteAlertClass = function(id) {
        const classNames = {1: 'Critical', 2: 'High', 3: 'Warning', 4: 'Info', 5: 'Low'};
        if (id <= 5) {
            showNotification('Cannot delete default classes', 'warning');
            return;
        }
        if (confirm(`Delete class "${classNames[id]}"?`)) {
            // In static version, just show notification
            showNotification(`"${classNames[id]}" deleted (demo)`, 'success');
        }
    };

    window.editAlertMessage = function(id) {
        const messageNames = {
            1: 'Critical Temperature', 
            2: 'Device Offline', 
            3: 'High Vibration', 
            4: 'Low Battery', 
            5: 'System Startup'
        };
        showNotification(`Edit "${messageNames[id]}" — coming soon`, 'info');
    };

    window.deleteAlertMessage = function(id) {
        const messageNames = {
            1: 'Critical Temperature', 
            2: 'Device Offline', 
            3: 'High Vibration', 
            4: 'Low Battery', 
            5: 'System Startup'
        };
        if (confirm(`Delete "${messageNames[id]}"?`)) {
            showNotification(`"${messageNames[id]}" deleted (demo)`, 'success');
        }
    };

    window.showAddAlertClassModal = function() { 
        showNotification('Add Alert Class — coming soon', 'info'); 
    };
    
    window.showAddAlertMessageModal = function() { 
        showNotification('Add Alert Message — coming soon', 'info'); 
    };

    window.exportConfiguration = function() {
        // Static demo data
        const demoConfig = {
            alertClasses: [
                { id: 1, name: 'Critical', severity: 5, color: '#DC2626', icon: 'fa-triangle-exclamation', description: 'Immediate action required' },
                { id: 2, name: 'High', severity: 4, color: '#F97316', icon: 'fa-circle-exclamation', description: 'Attention required soon' },
                { id: 3, name: 'Warning', severity: 3, color: '#F59E0B', icon: 'fa-exclamation', description: 'Monitor situation closely' },
                { id: 4, name: 'Info', severity: 2, color: '#3B82F6', icon: 'fa-circle-info', description: 'Informational message' },
                { id: 5, name: 'Low', severity: 1, color: '#10B981', icon: 'fa-circle-check', description: 'Normal operation information' }
            ],
            alertMessages: [
                { id: 1, name: 'Critical Temperature', message: '🔥 CRITICAL: {device} temperature is {value}°C', classId: 1, channels: ['mqtt', 'email', 'sms', 'dashboard'] },
                { id: 2, name: 'Device Offline', message: '📴 {device} is offline at {timestamp}', classId: 2, channels: ['email', 'dashboard'] },
                { id: 3, name: 'High Vibration', message: '⚠️ WARNING: {device} vibration is {value} mm/s', classId: 3, channels: ['mqtt', 'email', 'dashboard'] },
                { id: 4, name: 'Low Battery', message: '🔋 {device} battery is at {value}%', classId: 4, channels: ['dashboard'] },
                { id: 5, name: 'System Startup', message: '✅ {device} started successfully', classId: 5, channels: ['dashboard'] }
            ],
            timestamp: new Date().toISOString(),
            note: 'This is a static demo export'
        };
        
        var a = document.createElement('a');
        a.href = 'data:application/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(demoConfig, null, 2));
        a.download = 'alert-config-' + new Date().toISOString().split('T')[0] + '.json';
        a.click();
        showNotification('Configuration exported (demo)', 'success');
    };

    window.showLivePreview = function() {
        showNotification('Live Preview — coming soon', 'info');
    };

    // ========== CLEANUP ==========
    function cleanupAlerts() {

    }

    // ========== INIT ==========
    window.initAlerts = function() {

        // Nothing to initialize - using static HTML content
        showNotification('Alerts page loaded', 'info');
    };

    window.cleanupAlerts = cleanupAlerts;
    
    // Auto-initialize if DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', window.initAlerts);
    } else {
        window.initAlerts();
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { initAlerts: window.initAlerts, cleanupAlerts: window.cleanupAlerts };
}