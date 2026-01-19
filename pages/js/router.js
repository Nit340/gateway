class Router {
    constructor() {
        this.routes = {
            'general-configuration': 'general-configuration.html',
            'device-management': 'device-management.html',
            'modbus-mapping': 'modbus-mapping.html',
            'mqtt-cloud': 'mqtt-cloud.html',
            'ota-gateway': 'ota-gateway.html',
            'craneiq': 'craneiq.html',
            'data-retention': 'data-retention.html',
            'logging': 'loggar.html',
            'diagnostics': 'diagnostics.html',
            'security': 'security.html',
            'license': 'license.html',
            'automation': 'automation.html',
            'alerts': 'alerts.html',
            'rules': 'rules.html',
            'backup': 'backup.html',
            'notification': 'notification.html'
        };
        
        this.currentPage = null;
        this.previousPage = null;
        
        this.pageTitles = {
            'general-configuration': 'General Configuration',
            'device-management': 'Device Management',
            'modbus-mapping': 'Modbus Tag Mapping',
            'mqtt-cloud': 'MQTT Cloud Integration',
            'ota-gateway': 'OTA Gateway & Recovery',
            'craneiq': 'CraneIQ Configuration',
            'data-retention': 'Data Retention',
            'logging': 'Logging',
            'diagnostics': 'Diagnostics & Live Terminal',
            'security': 'Security & Access Control',
            'license': 'Licensing & Subscriptions',
            'automation': 'Scheduler / Automation',
            'alerts': 'Alerts & Event Classes',
            'rules': 'Rule Engine',
            'backup': 'Backup & Restore',
            'notification': 'Notification & Alerts'
        };
        
        // UPDATED: Scripts are in pages/js/ directory
        this.pageScripts = {
            'device-management': 'pages/js/device-management.js',
            'mqtt-cloud': 'pages/js/mqtt-cloud.js',
            'general-configuration': 'pages/js/general-config.js',
            'modbus-mapping': 'pages/js/modbus-mapping.js',
            'ota-gateway': 'pages/js/ota-gateway.js',
            'data-retention': 'pages/js/data-retention.js',
            'logging': 'pages/js/loggar.js',
            'security': 'pages/js/security.js',
            'diagnostics': 'pages/js/diagnostics.js',
            'license': 'pages/js/license.js',
            'alerts': 'pages/js/alerts.js',
            'automation': 'pages/js/automation.js',
            'backup': 'pages/js/backup.js',
            'craneiq': 'pages/js/craneiq.js',
            'notification': 'pages/js/notification.js',
            'rules': 'pages/js/rules.js'
        };
        
        this.loadedScripts = new Set();
        this.scriptPromises = new Map();
        
        this.init();
    }
    
    init() {
        // Handle navigation clicks
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = link.dataset.page;
                if (page && this.routes[page]) {
                    this.navigateTo(page);
                }
            });
        });
        
        // Handle browser back/forward buttons
        window.addEventListener('popstate', (event) => {
            if (event.state && event.state.page) {
                this.loadPage(event.state.page, false);
            }
        });
        
        // Load initial page from URL or default
        const urlParams = new URLSearchParams(window.location.search);
        const pageParam = urlParams.get('page');
        const initialPage = pageParam && this.routes[pageParam] ? pageParam : 'general-configuration';
        
        this.initialLoad(initialPage);
    }
    
    initialLoad(page) {
        this.currentPage = page;
        this.loadPage(page);
        this.updateActiveNavLink();
        
        // Update URL without adding to history
        window.history.replaceState({ page }, '', `?page=${page}`);
    }
    
    navigateTo(page, updateHistory = true) {
        if (this.currentPage === page) return;
        
        this.previousPage = this.currentPage;
        this.currentPage = page;
        
        // Clean up previous page before loading new one
        if (this.previousPage) {
            this.cleanupPageScripts(this.previousPage);
        }
        
        this.loadPage(page);
        this.updateActiveNavLink();
        
        if (updateHistory) {
            window.history.pushState({ page }, '', `?page=${page}`);
        }
        
        // Close sidebar on mobile after navigation
        if (window.innerWidth <= 1024) {
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('mobileOverlay');
            if (sidebar) sidebar.classList.remove('active');
            if (overlay) overlay.classList.remove('active');
        }
    }
    
    async loadPage(page) {
        const loadingIndicator = document.getElementById('loadingIndicator');
        const contentArea = document.getElementById('pageContent');
        
        // Show loading indicator
        if (loadingIndicator) loadingIndicator.classList.add('active');
        
        try {
            // Update page title
            const pageTitleElement = document.getElementById('pageTitle');
            if (pageTitleElement) {
                pageTitleElement.textContent = this.pageTitles[page] || page;
            }
            
            // Load page content
            const response = await fetch(`pages/${this.routes[page]}`);
            
            if (!response.ok) {
                throw new Error(`Failed to load page: ${response.status}`);
            }
            
            const html = await response.text();
            
            // Update content area
            if (contentArea) contentArea.innerHTML = html;
            
            // Load and initialize page-specific script
            await this.loadPageScript(page);
            
            // Initialize page-specific functionality with delay
            this.initializePageScripts(page);
            
            // Scroll to top
            window.scrollTo(0, 0);
            
        } catch (error) {
            console.error('Error loading page:', error);
            if (contentArea) {
                contentArea.innerHTML = `
                    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                        <div class="bg-red-50 border border-red-200 rounded-xl p-8 text-center">
                            <i class="fa-solid fa-triangle-exclamation text-red-500 text-4xl mb-4"></i>
                            <h2 class="text-xl font-semibold text-red-800 mb-2">Failed to Load Page</h2>
                            <p class="text-red-600 mb-4">The requested page could not be loaded. Please try again.</p>
                            <button onclick="window.router.navigateTo('general-configuration')" class="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primaryHover transition-colors">
                                Go to Home
                            </button>
                        </div>
                    </div>
                `;
            }
        } finally {
            // Hide loading indicator
            setTimeout(() => {
                if (loadingIndicator) loadingIndicator.classList.remove('active');
            }, 300);
        }
    }
    
    async loadPageScript(page) {
        const scriptName = this.pageScripts[page];
        
        if (!scriptName) {
            return Promise.resolve();
        }
        
        // Check if script is already loading
        if (this.scriptPromises.has(scriptName)) {
            return this.scriptPromises.get(scriptName);
        }
        
        console.log(`Loading script: ${scriptName} for page: ${page}`);
        
        const loadPromise = new Promise(async (resolve, reject) => {
            try {
                // Remove any existing script with same src to prevent duplicates
                const existingScripts = document.querySelectorAll(`script[src="${scriptName}"]`);
                existingScripts.forEach(script => {
                    if (script.parentNode) {
                        script.parentNode.removeChild(script);
                    }
                });
                
                // Clear module cache for this script
                delete window[`${page.replace('-', '_')}_loaded`];
                
                const script = document.createElement('script');
                script.src = scriptName;
                script.type = 'text/javascript';
                script.setAttribute('data-page', page);
                
                script.onload = () => {
                    console.log(`Successfully loaded: ${scriptName}`);
                    resolve();
                };
                
                script.onerror = (error) => {
                    console.warn(`Failed to load script: ${scriptName}`, error);
                    this.scriptPromises.delete(scriptName);
                    reject(new Error(`Failed to load ${scriptName}`));
                };
                
                document.head.appendChild(script);
                
            } catch (error) {
                console.warn(`Script load error for ${page}:`, error.message);
                this.scriptPromises.delete(scriptName);
                reject(error);
            }
        });
        
        this.scriptPromises.set(scriptName, loadPromise);
        this.loadedScripts.add(scriptName);
        
        return loadPromise;
    }
    
    cleanupPageScripts(page) {
        const scriptName = this.pageScripts[page];
        
        if (!scriptName) return;
        
        // Remove script promise
        this.scriptPromises.delete(scriptName);
        this.loadedScripts.delete(scriptName);
        
        // Clean up page-specific global variables and connections
        switch(page) {
            case 'general-configuration':
                // Clean up WebSocket
                if (typeof window.wsConnection !== 'undefined' && window.wsConnection) {
                    try {
                        window.wsConnection.close();
                    } catch (e) {
                        console.log('WebSocket already closed');
                    }
                    window.wsConnection = null;
                }
                
                // Clear reconnect interval
                if (typeof window.reconnectInterval !== 'undefined' && window.reconnectInterval) {
                    clearInterval(window.reconnectInterval);
                    window.reconnectInterval = null;
                }
                
                // Clear functions
                delete window.initGeneralConfig;
                break;
                
            case 'device-management':
                // Clean up WebSocket
                if (typeof window.deviceWsConnection !== 'undefined' && window.deviceWsConnection) {
                    try {
                        window.deviceWsConnection.close();
                    } catch (e) {
                        console.log('Device WebSocket already closed');
                    }
                    window.deviceWsConnection = null;
                }
                
                // Clear global functions and state
                if (window.deviceManagement) {
                    delete window.deviceManagement;
                }
                delete window.initializeDeviceManagement;
                break;
                
            case 'modbus-mapping':
                // Clear modbus mapping state
                delete window.initializeModbusMapping;
                break;
                
            case 'mqtt-cloud':
                // Clean up MQTT connections if any
                if (typeof window.mqttClient !== 'undefined' && window.mqttClient) {
                    try {
                        window.mqttClient.end();
                    } catch (e) {
                        console.log('MQTT client already disconnected');
                    }
                    window.mqttClient = null;
                }
                delete window.initMqttCloud;
                break;
                
            case 'ota-gateway':
                delete window.initOtaGateway;
                break;
                
            case 'data-retention':
                delete window.initDataRetention;
                break;
                
            case 'logging':
                delete window.initLogging;
                break;
                
            case 'security':
                if (window.userManagement) {
                    delete window.userManagement;
                }
                delete window.initSecurity;
                break;
                
            case 'diagnostics':
                // Clean up terminal if active
                if (typeof window.terminal !== 'undefined' && window.terminal) {
                    try {
                        window.terminal.dispose();
                    } catch (e) {
                        console.log('Terminal already disposed');
                    }
                    window.terminal = null;
                }
                delete window.initDiagnostics;
                break;
                
            case 'license':
                delete window.initLicense;
                break;
                
            case 'automation':
                delete window.initAutomation;
                break;
                
            case 'alerts':
                delete window.initAlerts;
                break;
                
            case 'rules':
                delete window.initRules;
                break;
                
            case 'backup':
                delete window.initBackup;
                break;
                
            case 'notification':
                delete window.initNotification;
                break;
                
            case 'craneiq':
                delete window.initCraneIQ;
                break;
        }
        
        console.log(`Cleaned up resources for page: ${page}`);
    }
    
    updateActiveNavLink() {
        document.querySelectorAll('.nav-link').forEach(link => {
            if (link.dataset.page === this.currentPage) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    }
    
    initializePageScripts(page) {
        // Add delay to ensure DOM is fully loaded and script is ready
        setTimeout(() => {
            switch(page) {
                case 'general-configuration':
                    if (typeof window.initGeneralConfig === 'function') {
                        console.log('Initializing General Configuration');
                        window.initGeneralConfig();
                    } else {
                        console.warn('initGeneralConfig function not found');
                    }
                    break;
                    
                case 'device-management':
                    if (typeof window.initializeDeviceManagement === 'function') {
                        console.log('Initializing Device Management');
                        window.initializeDeviceManagement();
                    } else {
                        console.warn('initializeDeviceManagement function not found');
                    }
                    break;
                    
                case 'modbus-mapping':
                    if (typeof window.initializeModbusMapping === 'function') {
                        console.log('Initializing Modbus Mapping');
                        window.initializeModbusMapping();
                    } else {
                        console.warn('initializeModbusMapping function not found');
                    }
                    break;
                    
                case 'mqtt-cloud':
                    if (typeof window.initMqttCloud === 'function') {
                        console.log('Initializing MQTT Cloud');
                        window.initMqttCloud();
                    } else {
                        console.warn('initMqttCloud function not found');
                    }
                    break;
                    
                case 'ota-gateway':
                    if (typeof window.initOtaGateway === 'function') {
                        console.log('Initializing OTA Gateway');
                        window.initOtaGateway();
                    } else {
                        console.warn('initOtaGateway function not found');
                    }
                    break;
                    
                case 'data-retention':
                    if (typeof window.initDataRetention === 'function') {
                        console.log('Initializing Data Retention');
                        window.initDataRetention();
                    } else {
                        console.warn('initDataRetention function not found');
                    }
                    break;
                    
                case 'logging':
                    if (typeof window.initLogging === 'function') {
                        console.log('Initializing Logging');
                        window.initLogging();
                    } else {
                        console.warn('initLogging function not found');
                    }
                    break;
                    
                case 'security':
                    if (typeof window.initSecurity === 'function') {
                        console.log('Initializing Security');
                        window.initSecurity();
                    } else {
                        console.warn('initSecurity function not found');
                    }
                    break;
                    
                case 'diagnostics':
                    if (typeof window.initDiagnostics === 'function') {
                        console.log('Initializing Diagnostics');
                        window.initDiagnostics();
                    } else {
                        console.warn('initDiagnostics function not found');
                    }
                    break;
                    
                case 'license':
                    if (typeof window.initLicense === 'function') {
                        console.log('Initializing License');
                        window.initLicense();
                    } else {
                        console.warn('initLicense function not found');
                    }
                    break;
                    
                case 'automation':
                    if (typeof window.initAutomation === 'function') {
                        console.log('Initializing Automation');
                        window.initAutomation();
                    } else {
                        console.warn('initAutomation function not found');
                    }
                    break;
                    
                case 'alerts':
                    if (typeof window.initAlerts === 'function') {
                        console.log('Initializing Alerts');
                        window.initAlerts();
                    } else {
                        console.warn('initAlerts function not found');
                    }
                    break;
                    
                case 'rules':
                    if (typeof window.initRules === 'function') {
                        console.log('Initializing Rules');
                        window.initRules();
                    } else {
                        console.warn('initRules function not found');
                    }
                    break;
                    
                case 'backup':
                    if (typeof window.initBackup === 'function') {
                        console.log('Initializing Backup');
                        window.initBackup();
                    } else {
                        console.warn('initBackup function not found');
                    }
                    break;
                    
                case 'notification':
                    if (typeof window.initNotification === 'function') {
                        console.log('Initializing Notification');
                        window.initNotification();
                    } else {
                        console.warn('initNotification function not found');
                    }
                    break;
                    
                case 'craneiq':
                    if (typeof window.initCraneIQ === 'function') {
                        console.log('Initializing CraneIQ');
                        window.initCraneIQ();
                    } else {
                        console.warn('initCraneIQ function not found');
                    }
                    break;
                    
                default:
                    console.log(`No specific initialization for page: ${page}`);
            }
        }, 150); // 150ms delay to ensure DOM is ready
    }
    
    cleanupPreviousPage() {
        // Close any open modals or overlays
        document.querySelectorAll('.modal-overlay, .modal, .add-device-panel').forEach(el => {
            el.classList.remove('active');
        });
        
        document.body.classList.remove('modal-open');
        
        // Clear any active dropdowns
        document.querySelectorAll('.action-dropdown-content.show').forEach(el => {
            el.classList.remove('show');
        });
        
        // Clear any active notifications
        document.querySelectorAll('.notification-toast').forEach(el => {
            el.remove();
        });
    }
    
    // Public method to reload current page
    reloadCurrentPage() {
        if (this.currentPage) {
            this.loadPage(this.currentPage);
        }
    }
    
    // Public method to get current page
    getCurrentPage() {
        return this.currentPage;
    }
    
    // Public method to check if page exists
    hasPage(page) {
        return this.routes.hasOwnProperty(page);
    }
}

// Initialize router when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.router = new Router();
    
    // Expose router for global access
    window.Router = Router;
});

// Export for module system if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Router;
}