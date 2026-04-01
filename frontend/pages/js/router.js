class Router {
    constructor() {
        this.routes = {
            'general-configuration': 'general-configuration.html',
            'device-management': 'device-management.html',
            'field-integration': 'modbus-mapping.html',
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
            'field-integration': 'Field Integration',
            'mqtt-cloud': 'Cloud Integration',
            'ota-gateway': 'OTA Gateway & Recovery',
            'craneiq': 'CraneIQ Configuration',
            'data-retention': 'Data Retention',
            'logging': 'Logging',
            'diagnostics': 'Diagnostics & Live Terminal',
            'security': 'Security & Access Control',
            'license': 'Licensing & Subscriptions',
            'automation': 'Scheduler / Automation',
            'alerts': 'Alerts & Event',
            'rules': 'Rule Engine',
            'backup': 'Backup & Restore',
            'notification': 'Notification'
        };
        
        // UPDATED: Scripts are in pages/js/ directory
        this.pageScripts = {
            'device-management': 'pages/js/device-management.js',
            'mqtt-cloud': 'pages/js/mqtt-cloud.js',
            'general-configuration': 'pages/js/general-config.js',
            'field-integration': 'pages/js/modbus-mapping.js',
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
        this.initializedPages = new Set(); // NEW: Track initialized pages
        this.currentInitializationTimer = null; // NEW: Track initialization timer
        
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
        
        // Load initial page from URL path or default
        const pathPage = window.location.pathname.replace(/^\//, '');
        const initialPage = pathPage && this.routes[pathPage] ? pathPage : 'general-configuration';
        
        this.initialLoad(initialPage);
    }
    
    initialLoad(page) {
        this.currentPage = page;
        this.loadPage(page);
        this.updateActiveNavLink();
        
        // Update URL without adding to history
        window.history.replaceState({ page }, '', `/${page}`);
    }
    
    navigateTo(page, updateHistory = true) {
        if (this.currentPage === page) return;
        

        
        this.previousPage = this.currentPage;
        this.currentPage = page;
        
        // Clean up previous page before loading new one
        if (this.previousPage) {
            this.cleanupPageScripts(this.previousPage);
            this.cleanupPreviousPage();
        }
        
        this.loadPage(page);
        this.updateActiveNavLink();
        
        if (updateHistory) {
            window.history.pushState({ page }, '', `/${page}`);
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
            
            // Load page-specific script
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
        
        // Check if script is already loaded and cached
        if (this.loadedScripts.has(scriptName)) {

            return Promise.resolve();
        }
        

        
        const loadPromise = new Promise(async (resolve, reject) => {
            try {
                // Check if script is already in DOM (cached by browser)
                const existingScript = document.querySelector(`script[src="${scriptName}"]`);
                if (existingScript) {

                    this.loadedScripts.add(scriptName);
                    resolve();
                    return;
                }
                
                const script = document.createElement('script');
                script.src = scriptName;
                script.type = 'text/javascript';
                script.setAttribute('data-page', page);
                script.setAttribute('data-router-loaded', 'true');
                
                script.onload = () => {

                    this.loadedScripts.add(scriptName);
                    resolve();
                };
                
                script.onerror = (error) => {
                    console.warn(`Failed to load script: ${scriptName}`, error);
                    this.scriptPromises.delete(scriptName);
                    this.loadedScripts.delete(scriptName);
                    reject(new Error(`Failed to load ${scriptName}`));
                };
                
                document.head.appendChild(script);
                
            } catch (error) {
                console.warn(`Script load error for ${page}:`, error.message);
                this.scriptPromises.delete(scriptName);
                this.loadedScripts.delete(scriptName);
                reject(error);
            }
        });
        
        this.scriptPromises.set(scriptName, loadPromise);
        return loadPromise;
    }
    
    cleanupPageScripts(page) {
        const scriptName = this.pageScripts[page];
        
        if (!scriptName) return;
        
        // Remove from initialized pages
        this.initializedPages.delete(page);
        
        // CRITICAL FIX: Also remove from loaded scripts cache
        // This forces the script to re-execute on next navigation
        // Fixes modal/event listener issues after navigation
        this.loadedScripts.delete(scriptName);

        
        // Remove script promise (but keep in loadedScripts for caching)
        this.scriptPromises.delete(scriptName);
        
        // Clean up page-specific global variables and connections
        switch(page) {
            case 'general-configuration':
                // Clean up general WS
                if (typeof window.wsConnection !== 'undefined' && window.wsConnection) {
                    try { window.wsConnection.close(); } catch (e) {}
                    window.wsConnection = null;
                }
                // Clean up network status WS + timers via public API
                if (window.networkStatusLive && typeof window.networkStatusLive.disconnect === 'function') {
                    window.networkStatusLive.disconnect();
                }
                // Clear reconnect interval
                if (typeof window.reconnectInterval !== 'undefined' && window.reconnectInterval) {
                    clearInterval(window.reconnectInterval);
                    window.reconnectInterval = null;
                }
                // Clear global flag
                delete window.general_configuration_initialized;
                // Call cleanup if exists
                if (typeof window.cleanupGeneralConfig === 'function') {
                    window.cleanupGeneralConfig();
                }
                break;
                
            case 'device-management':
                // Clean up WebSocket
                if (typeof window.deviceWsConnection !== 'undefined' && window.deviceWsConnection) {
                    try {
                        window.deviceWsConnection.close();
                    } catch (e) {

                    }
                    window.deviceWsConnection = null;
                }
                
                // Clear global flag
                delete window.device_management_initialized;
                
                // Call cleanup function if it exists
                if (typeof window.cleanupDeviceManagement === 'function') {
                    window.cleanupDeviceManagement();
                }
                break;
                
            case 'field-integration':
                // Clear global flag
                delete window.field_integration_initialized;
                
                // Call cleanup if exists
                if (typeof window.cleanupModbusMapping === 'function') {
                    window.cleanupModbusMapping();
                }
                break;
                
            case 'mqtt-cloud':
                // Clean up MQTT connections if any
                if (typeof window.mqttClient !== 'undefined' && window.mqttClient) {
                    try {
                        window.mqttClient.end();
                    } catch (e) {

                    }
                    window.mqttClient = null;
                }
                
                // Clear global flag
                delete window.mqtt_cloud_initialized;
                
                if (typeof window.cleanupMqttCloud === 'function') {
                    window.cleanupMqttCloud();
                }
                break;
                
            case 'ota-gateway':
                delete window.ota_gateway_initialized;
                if (typeof window.cleanupOtaGateway === 'function') {
                    window.cleanupOtaGateway();
                }
                break;
                
            case 'data-retention':
                delete window.data_retention_initialized;
                if (typeof window.cleanupDataRetention === 'function') {
                    window.cleanupDataRetention();
                }
                break;
                
            case 'logging':
                delete window.logging_initialized;
                if (typeof window.cleanupLogging === 'function') {
                    window.cleanupLogging();
                }
                break;
                
            case 'security':
                delete window.security_initialized;
                if (typeof window.cleanupSecurity === 'function') {
                    window.cleanupSecurity();
                }
                break;
                
            case 'diagnostics':
                // Clean up terminal if active
                if (typeof window.terminal !== 'undefined' && window.terminal) {
                    try {
                        window.terminal.dispose();
                    } catch (e) {

                    }
                    window.terminal = null;
                }
                
                delete window.diagnostics_initialized;
                if (typeof window.cleanupDiagnostics === 'function') {
                    window.cleanupDiagnostics();
                }
                break;
                
            case 'license':
                delete window.license_initialized;
                if (typeof window.cleanupLicense === 'function') {
                    window.cleanupLicense();
                }
                break;
                
            case 'automation':
                delete window.automation_initialized;
                if (typeof window.cleanupAutomation === 'function') {
                    window.cleanupAutomation();
                }
                break;
                
            case 'alerts':
                delete window.alerts_initialized;
                this.initializedPages.delete(page);
                if (typeof window.cleanupAlerts === 'function') {

                    window.cleanupAlerts();
                }
                break;

            case 'rules':
                delete window.rules_initialized;
                this.initializedPages.delete(page);
                if (typeof window.cleanupRules === 'function') {

                    window.cleanupRules();
                }
                break;
                
            case 'backup':
                delete window.backup_initialized;
                this.initializedPages.delete(page);
                if (typeof window.cleanupBackup === 'function') {

                    window.cleanupBackup();
                }
                break;

            case 'notification':
                delete window.notification_initialized;
                this.initializedPages.delete(page);
                if (typeof window.cleanupNotification === 'function') {

                    window.cleanupNotification();
                }
                break;
                
            case 'craneiq':
                delete window.craneiq_initialized;
                if (typeof window.cleanupCraneIQ === 'function') {

                    window.cleanupCraneIQ();
                }
                break;
        }
        

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
        // Clear any previous initialization timer
        if (this.currentInitializationTimer) {
            clearTimeout(this.currentInitializationTimer);
            this.currentInitializationTimer = null;
        }
        
        // Check if page is already initialized (prevent duplicate initialization)
        if (this.initializedPages.has(page)) {

            return;
        }
        
        // Also check global flag (extra protection)
        const globalFlag = `${page.replace(/-/g, '_')}_initialized`;
        if (window[globalFlag]) {

            return;
        }

        // Lock immediately BEFORE the timer - blocks any concurrent calls
        this.initializedPages.add(page);
        window[globalFlag] = true;
        

        
        // Set a new timer for initialization
        this.currentInitializationTimer = setTimeout(() => {

            
            switch(page) {
                case 'general-configuration':
                    if (typeof window.initGeneralConfig === 'function') {

                        window.initGeneralConfig();
                        this.initializedPages.add(page);
                        window.general_configuration_initialized = true;
                    } else {
                        console.warn('initGeneralConfig function not found');
                    }
                    break;
                    
                case 'device-management':
                    if (typeof window.initializeDeviceManagement === 'function') {

                        window.initializeDeviceManagement();
                        this.initializedPages.add(page);
                        window.device_management_initialized = true;
                    } else {
                        console.warn('initializeDeviceManagement function not found');
                    }
                    break;
                    
                case 'field-integration':
                    if (typeof window.initializeModbusMapping === 'function') {

                        window.initializeModbusMapping();
                        this.initializedPages.add(page);
                        window.field_integration_initialized = true;
                    } else {
                        console.warn('initializeModbusMapping function not found');
                    }
                    break;
                    
                case 'mqtt-cloud':
                    if (typeof window.initMqttCloud === 'function') {

                        window.initMqttCloud();
                        this.initializedPages.add(page);
                        window.mqtt_cloud_initialized = true;
                    } else {
                        console.warn('initMqttCloud function not found');
                    }
                    break;
                    
                case 'ota-gateway':
                    if (typeof window.initOtaGateway === 'function') {

                        window.initOtaGateway();
                        this.initializedPages.add(page);
                        window.ota_gateway_initialized = true;
                    } else {
                        console.warn('initOtaGateway function not found');
                    }
                    break;
                    
                case 'data-retention':
                    if (typeof window.initDataRetention === 'function') {

                        window.initDataRetention();
                        this.initializedPages.add(page);
                        window.data_retention_initialized = true;
                    } else {
                        console.warn('initDataRetention function not found');
                    }
                    break;
                    
                case 'logging':
                    if (typeof window.initLogging === 'function') {

                        window.initLogging();
                        this.initializedPages.add(page);
                        window.logging_initialized = true;
                    } else {
                        console.warn('initLogging function not found');
                    }
                    break;
                    
                case 'security':
                    if (typeof window.initSecurity === 'function') {

                        window.initSecurity();
                        this.initializedPages.add(page);
                        window.security_initialized = true;
                    } else {
                        console.warn('initSecurity function not found');
                    }
                    break;
                    
                case 'diagnostics':
                    if (typeof window.initDiagnostics === 'function') {

                        window.initDiagnostics();
                        this.initializedPages.add(page);
                        window.diagnostics_initialized = true;
                    } else {
                        console.warn('initDiagnostics function not found');
                    }
                    break;
                    
                case 'license':
                    if (typeof window.initLicense === 'function') {

                        window.initLicense();
                        this.initializedPages.add(page);
                        window.license_initialized = true;
                    } else {
                        console.warn('initLicense function not found');
                    }
                    break;
                    
                case 'automation':
                    if (typeof window.initAutomation === 'function') {

                        window.initAutomation();
                        this.initializedPages.add(page);
                        window.automation_initialized = true;
                    } else {
                        console.warn('initAutomation function not found');
                    }
                    break;
                    
                case 'alerts':
                    if (typeof window.initAlerts === 'function') {

                        window.initAlerts();
                        this.initializedPages.add(page);
                        window.alerts_initialized = true;
                    } else {
                        console.warn('initAlerts function not found');
                    }
                    break;

                case 'rules':
                    if (typeof window.initRules === 'function') {

                        window.initRules();
                        this.initializedPages.add(page);
                        window.rules_initialized = true;
                    } else {
                        console.warn('initRules function not found');
                    }
                    break;
                case 'backup':
                    if (typeof window.initBackup === 'function') {

                        window.initBackup();
                        this.initializedPages.add(page);
                        window.backup_initialized = true;
                    } else {
                        console.warn('initBackup function not found');
                    }
                    break;

                case 'notification':
                    if (typeof window.initNotification === 'function') {

                        window.initNotification();
                        this.initializedPages.add(page);
                        window.notification_initialized = true;
                    } else {
                        console.warn('initNotification function not found');
                    }
                    break;
                    
                case 'craneiq':
                    if (typeof window.initCraneIQ === 'function') {

                        window.initCraneIQ();
                        this.initializedPages.add(page);
                        window.craneiq_initialized = true;
                    } else {
                        console.warn('initCraneIQ function not found');
                    }
                    break;
                    
                default:

            }
            
            this.currentInitializationTimer = null;
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
            // Remove from initialized pages so it re-initializes
            this.initializedPages.delete(this.currentPage);
            
            // Clear global flag
            const globalFlag = `${this.currentPage.replace(/-/g, '_')}_initialized`;
            delete window[globalFlag];
            
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