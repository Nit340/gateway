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
            'general-configuration': 'pages/js/general-configuration.js',
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
        
        this.currentPage = page;
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
            
            // Initialize page-specific functionality
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
        
        if (!scriptName || this.loadedScripts.has(scriptName)) {
            return;
        }
        
        console.log(`Attempting to load script: ${scriptName} for page: ${page}`);
        
        try {
            // Load the script dynamically
            const script = document.createElement('script');
            script.src = scriptName;
            script.type = 'text/javascript';
            
            // Add to document
            document.head.appendChild(script);
            
            // Wait for script to load
            await new Promise((resolve, reject) => {
                script.onload = resolve;
                script.onerror = () => {
                    console.warn(`Script failed to load: ${scriptName}`);
                    reject(new Error(`Failed to load ${scriptName}`));
                };
            });
            
            // Mark as loaded
            this.loadedScripts.add(scriptName);
            
            console.log(`Successfully loaded: ${scriptName}`);
            
        } catch (error) {
            console.warn(`Could not load script ${scriptName}:`, error.message);
            // Don't throw error - allow page to load without script
            // Script might not exist yet, and that's okay
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
        // Clear any conflicting global state from previous pages
        this.cleanupPreviousPage();
        
        // Page-specific initialization
        switch(page) {
            case 'general-configuration':
                this.initGeneralConfig();
                break;
            case 'device-management':
                this.initDeviceManagement();
                break;
            case 'modbus-mapping':
                this.initModbusMapping();
                break;
            case 'mqtt-cloud':
                this.initMqttCloud();
                break;
            case 'ota-gateway':
                this.initOtaGateway();
                break;
            case 'data-retention':
                this.initDataRetention();
                break;
            case 'logging':
                this.initLogging();
                break;
            case 'security':
                this.initSecurity();
                break;
            case 'diagnostics':
                this.initDiagnostics();
                break;
            case 'license':
                this.initLicense();
                break;
            case 'automation':
                this.initAutomation();
                break;
            case 'alerts':
                this.initAlerts();
                break;
            case 'rules':
                this.initRules();
                break;
            case 'backup':
                this.initBackup();
                break;
            case 'notification':
                this.initNotification();
                break;
            case 'craneiq':
                this.initCraneIQ();
                break;
            default:
                console.log(`No specific initialization for page: ${page}`);
        }
    }
    
    // Add cleanup method to prevent conflicts
    cleanupPreviousPage() {
        // Clean up WebSocket connections from other pages
        if (window.deviceManagement && window.deviceManagement.cleanup) {
            window.deviceManagement.cleanup();
        }
        
        // Clear any modals or overlays
        document.querySelectorAll('.modal-overlay, .modal').forEach(el => {
            el.classList.remove('active');
        });
        
        document.body.classList.remove('modal-open');
        
        // Clear any active notifications
        document.querySelectorAll('.notification-toast').forEach(el => {
            el.remove();
        });
    }
    
    // Page-specific initialization methods
    initLicense() {
        if (typeof window.initLicense === 'function') {
            window.initLicense();
        } else {
            console.log('initLicense function not found');
        }
    }
    
    initDiagnostics() {
        if (typeof window.initDiagnostics === 'function') {
            window.initDiagnostics();
        } else {
            console.log('initDiagnostics function not found');
        }
    }
    
    initSecurity() {
        if (typeof window.initSecurity === 'function') {
            window.initSecurity();
        } else {
            console.log('initSecurity function not found');
        }
    }
    
    initLogging() {
        if (typeof window.initLogging === 'function') {
            window.initLogging();
        } else {
            console.log('initLogging function not found');
        }
    }
    
    initOtaGateway() {
        if (typeof window.initOtaGateway === 'function') {
            window.initOtaGateway();
        } else {
            console.log('initOtaGateway function not found');
        }
    }
    
    initDataRetention() {
        if (typeof window.initDataRetention === 'function') {
            window.initDataRetention();
        } else {
            console.log('initDataRetention function not found');
        }
    }
    
    initMqttCloud() {
        if (typeof window.initMqttCloud === 'function') {
            window.initMqttCloud();
        } else {
            console.log('initMqttCloud function not found');
        }
    }
    
    initModbusMapping() {
        if (typeof window.initializeModbusMapping === 'function') {
            window.initializeModbusMapping();
        } else {
            console.log('initializeModbusMapping function not found');
        }
    }
    
    initDeviceManagement() {
        if (typeof window.initializeDeviceManagement === 'function') {
            window.initializeDeviceManagement();
        } else {
            console.log('initializeDeviceManagement function not found');
        }
    }
    
    initGeneralConfig() {
        if (typeof window.initGeneralConfig === 'function') {
            window.initGeneralConfig();
        } else {
            console.log('initGeneralConfig function not found');
        }
    }
    
    // Add these new initialization methods for other pages
    initAutomation() {
        if (typeof window.initAutomation === 'function') {
            window.initAutomation();
        } else {
            console.log('initAutomation function not found');
        }
    }
    
    initAlerts() {
        if (typeof window.initAlerts === 'function') {
            window.initAlerts();
        } else {
            console.log('initAlerts function not found');
        }
    }
    
    initRules() {
        if (typeof window.initRules === 'function') {
            window.initRules();
        } else {
            console.log('initRules function not found');
        }
    }
    
    initBackup() {
        if (typeof window.initBackup === 'function') {
            window.initBackup();
        } else {
            console.log('initBackup function not found');
        }
    }
    
    initNotification() {
        if (typeof window.initNotification === 'function') {
            window.initNotification();
        } else {
            console.log('initNotification function not found');
        }
    }
    
    initCraneIQ() {
        if (typeof window.initCraneIQ === 'function') {
            window.initCraneIQ();
        } else {
            console.log('initCraneIQ function not found');
        }
    }
}

// Export for global access
window.Router = Router;