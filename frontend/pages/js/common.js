// Common utilities and functions used across multiple pages

/**
 * Shows a notification message
 * @param {string} message - The message to display
 * @param {string} type - Notification type: 'success', 'error', 'warning', 'info'
 * @returns {HTMLElement} The notification element
 */
function showNotification(message, type = 'success') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 px-4 py-3 rounded-lg shadow-lg z-50 transition-all duration-300 transform translate-x-full`;
    
    // Add type-specific styling
    if (type === 'success') {
        notification.className += ' bg-emerald-50 border border-emerald-200 text-emerald-800';
    } else if (type === 'error') {
        notification.className += ' bg-red-50 border border-red-200 text-red-800';
    } else if (type === 'warning') {
        notification.className += ' bg-amber-50 border border-amber-200 text-amber-800';
    } else if (type === 'info') {
        notification.className += ' bg-blue-50 border border-blue-200 text-blue-800';
    }
    
    // Set icon based on type
    let icon = 'fa-circle-info';
    if (type === 'success') icon = 'fa-circle-check';
    if (type === 'error') icon = 'fa-circle-exclamation';
    if (type === 'warning') icon = 'fa-triangle-exclamation';
    
    notification.innerHTML = `
        <div class="flex items-center">
            <i class="fa-solid ${icon} mr-3"></i>
            <span class="font-medium">${message}</span>
            <button class="ml-4 text-slate-400 hover:text-slate-600 close-notification" aria-label="Close notification">
                <i class="fa-solid fa-times"></i>
            </button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.classList.remove('translate-x-full');
    }, 10);
    
    // Add close button functionality
    const closeBtn = notification.querySelector('.close-notification');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            closeNotification(notification);
        });
    }
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        closeNotification(notification);
    }, 5000);
    
    return notification;
}

/**
 * Closes a notification
 * @param {HTMLElement} notification - The notification element to close
 */
function closeNotification(notification) {
    if (!notification || !notification.parentNode) return;
    
    notification.style.opacity = '0';
    notification.style.transform = 'translateX(100%)';
    setTimeout(() => {
        if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
        }
    }, 300);
}

/**
 * Shows the loading indicator
 */
function showLoadingIndicator() {
    const loadingIndicator = document.getElementById('loadingIndicator');
    if (loadingIndicator) loadingIndicator.classList.add('active');
}

/**
 * Hides the loading indicator
 */
function hideLoadingIndicator() {
    const loadingIndicator = document.getElementById('loadingIndicator');
    if (loadingIndicator) loadingIndicator.classList.remove('active');
}

/**
 * Toggles the mobile sidebar
 * @param {boolean|null} show - Whether to show or hide the sidebar (null toggles)
 */
function toggleMobileSidebar(show = null) {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('mobileOverlay');
    
    if (show === null) {
        show = !sidebar.classList.contains('active');
    }
    
    if (sidebar) {
        if (show) {
            sidebar.classList.add('active');
        } else {
            sidebar.classList.remove('active');
        }
    }
    
    if (overlay) {
        if (show) {
            overlay.classList.add('active');
        } else {
            overlay.classList.remove('active');
        }
    }
}

/**
 * Shows a confirmation dialog
 * @param {string} message - The confirmation message
 * @param {string} confirmText - Text for confirm button
 * @param {string} cancelText - Text for cancel button
 * @returns {Promise<boolean>} Resolves to true if confirmed, false if cancelled
 */
async function showConfirmationDialog(message, confirmText = 'Yes', cancelText = 'No') {
    return new Promise((resolve) => {
        // Create dialog overlay
        const overlay = document.createElement('div');
        overlay.className = 'fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4';
        
        // Create dialog
        const dialog = document.createElement('div');
        dialog.className = 'bg-white rounded-xl shadow-xl max-w-md w-full';
        dialog.innerHTML = `
            <div class="p-6">
                <div class="flex items-center mb-4">
                    <i class="fa-solid fa-circle-question text-blue-500 text-2xl mr-3"></i>
                    <h3 class="text-lg font-semibold text-slate-800">Confirmation</h3>
                </div>
                <p class="text-slate-600 mb-6">${message}</p>
                <div class="flex justify-end space-x-3">
                    <button class="px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 transition-colors cancel-btn">
                        ${cancelText}
                    </button>
                    <button class="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primaryHover transition-colors confirm-btn">
                        ${confirmText}
                    </button>
                </div>
            </div>
        `;
        
        overlay.appendChild(dialog);
        document.body.appendChild(overlay);
        
        // Handle button clicks
        const confirmBtn = dialog.querySelector('.confirm-btn');
        const cancelBtn = dialog.querySelector('.cancel-btn');
        
        const handleConfirm = () => {
            cleanup();
            resolve(true);
        };
        
        const handleCancel = () => {
            cleanup();
            resolve(false);
        };
        
        const handleKeydown = (e) => {
            if (e.key === 'Escape') handleCancel();
            if (e.key === 'Enter') handleConfirm();
        };
        
        confirmBtn.addEventListener('click', handleConfirm);
        cancelBtn.addEventListener('click', handleCancel);
        document.addEventListener('keydown', handleKeydown);
        
        const cleanup = () => {
            confirmBtn.removeEventListener('click', handleConfirm);
            cancelBtn.removeEventListener('click', handleCancel);
            document.removeEventListener('keydown', handleKeydown);
            document.body.removeChild(overlay);
        };
        
        // Focus the confirm button
        setTimeout(() => confirmBtn.focus(), 100);
    });
}

/**
 * Validates an email address
 * @param {string} email - Email address to validate
 * @returns {boolean} True if valid
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * Validates an IP address
 * @param {string} ip - IP address to validate
 * @returns {boolean} True if valid
 */
function isValidIP(ip) {
    const ipRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    return ipRegex.test(ip);
}

/**
 * Formats a date for display
 * @param {Date|string} date - Date to format
 * @returns {string} Formatted date string
 */
function formatDate(date) {
    if (!date) return '';
    
    const d = new Date(date);
    if (isNaN(d.getTime())) return '';
    
    return d.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Debounces a function
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Throttles a function
 * @param {Function} func - Function to throttle
 * @param {number} limit - Time limit in milliseconds
 * @returns {Function} Throttled function
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * Copies text to clipboard
 * @param {string} text - Text to copy
 * @returns {Promise<boolean>} Success status
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showNotification('Copied to clipboard!', 'success');
        return true;
    } catch (err) {
        console.error('Failed to copy: ', err);
        showNotification('Failed to copy to clipboard', 'error');
        return false;
    }
}

/**
 * Generates a unique ID
 * @returns {string} Unique ID
 */
function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

/**
 * Sanitizes HTML input
 * @param {string} input - Input to sanitize
 * @returns {string} Sanitized input
 */
function sanitizeInput(input) {
    const div = document.createElement('div');
    div.textContent = input;
    return div.innerHTML;
}

/**
 * Initializes common event listeners
 */
function initCommonEventListeners() {
    // Mobile menu button
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', () => {
            toggleMobileSidebar();
        });
    }
    
    // Mobile overlay
    const mobileOverlay = document.getElementById('mobileOverlay');
    if (mobileOverlay) {
        mobileOverlay.addEventListener('click', () => {
            toggleMobileSidebar(false);
        });
    }
    
    // Handle responsive behavior
    window.addEventListener('resize', () => {
        if (window.innerWidth > 1024) {
            toggleMobileSidebar(false);
        }
    });
    
    // Handle escape key for closing modals
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            // Close any active dropdowns
            document.querySelectorAll('.action-dropdown-content.show').forEach(dropdown => {
                dropdown.classList.remove('show');
            });
            
            // Close any active panels
            const addDevicePanel = document.getElementById('addDevicePanel');
            if (addDevicePanel && addDevicePanel.classList.contains('active')) {
                addDevicePanel.classList.remove('active');
            }
            
            // Close any active modals
            document.querySelectorAll('.modal-overlay.active').forEach(modal => {
                modal.classList.remove('active');
            });
        }
    });
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.action-dropdown')) {
            document.querySelectorAll('.action-dropdown-content.show').forEach(dropdown => {
                dropdown.classList.remove('show');
            });
        }
    });
}

/**
 * Formats file size for display
 * @param {number} bytes - File size in bytes
 * @returns {string} Formatted file size
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Downloads data as a file
 * @param {string} data - Data to download
 * @param {string} filename - Name of the file
 * @param {string} type - MIME type
 */
function downloadFile(data, filename, type = 'text/plain') {
    const blob = new Blob([data], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

/**
 * Reads a file as text
 * @param {File} file - File to read
 * @returns {Promise<string>} File content
 */
function readFileAsText(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = (e) => reject(e);
        reader.readAsText(file);
    });
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initCommonEventListeners();

});

// Export functions for global access
window.showNotification = showNotification;
window.closeNotification = closeNotification;
window.showLoadingIndicator = showLoadingIndicator;
window.hideLoadingIndicator = hideLoadingIndicator;
window.toggleMobileSidebar = toggleMobileSidebar;
window.showConfirmationDialog = showConfirmationDialog;
window.isValidEmail = isValidEmail;
window.isValidIP = isValidIP;
window.formatDate = formatDate;
window.debounce = debounce;
window.throttle = throttle;
window.copyToClipboard = copyToClipboard;
window.generateId = generateId;
window.sanitizeInput = sanitizeInput;
window.formatFileSize = formatFileSize;
window.downloadFile = downloadFile;
window.readFileAsText = readFileAsText;