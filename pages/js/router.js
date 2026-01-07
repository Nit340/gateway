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
            'logging': 'logging.html',
            'diagnostics': 'diagnostics.html',
            'security': 'security.html',
            'license': 'license.html',
            'automation': 'automation.html',
            'alerts': 'alerts.html',
            'rules': 'rules.html',
            'backup': 'backup.html',
            'notification': 'notification.html'
        };
        
        this.currentPage = 'general-configuration';
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
        
        // Handle gateway select change
        const gatewaySelect = document.getElementById('gateway-select');
        if (gatewaySelect) {
            gatewaySelect.addEventListener('change', function() {
                if (confirm('Switch to another gateway? Unsaved changes will be lost.')) {
                    location.reload();
                } else {
                    this.value = 'Univa-GW-01';
                }
            });
        }
        
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
        
        this.navigateTo(initialPage, false);
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
            toggleMobileSidebar(false);
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
            
            // Initialize page-specific scripts
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
    // Page-specific initialization
    switch(page) {
        case 'general-configuration':
            this.initGeneralConfig();
            break;
        case 'device-management':
            this.initDeviceManagement();
            break;
        case 'modbus-mapping':
            this.initModbusMapping(); // Changed from initializeProtocolMapping()
            break;
        // Add other pages as you create them
        default:
            console.log(`No specific initialization for page: ${page}`);
    }
}
initModbusMapping() {
    // Call the global initialization function
    if (typeof window.initializeModbusMapping === 'function') {
        window.initializeModbusMapping();
    } else {
        console.log('initializeModbusMapping function not found - ensure modbus-mapping.js is loaded');
    }
}

    initDeviceManagement() {
        // Call the global initialization function
        if (typeof window.initializeDeviceManagement === 'function') {
            window.initializeDeviceManagement();
        }
    }

    initGeneralConfig() {
        // Call the global initialization function
        if (typeof window.initGeneralConfig === 'function') {
            window.initGeneralConfig();
        } else {
            console.log('initGeneralConfig function not found - this is normal if the page doesn\'t define it');
        }
    }
}

// Export for global access
window.Router = Router;