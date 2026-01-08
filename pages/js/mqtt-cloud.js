// pages/js/mqtt-cloud.js

// This function will be called by the router when loading the page
window.initMqttCloud = function() {
    console.log('MQTT Cloud page initialized');
    
    // Initialize all functionality for this page
    initializeMqttCloud();
};

function initializeMqttCloud() {
    console.log('Setting up MQTT Cloud page functionality');
    
    // Initialize button handlers
    initializeButtons();
    
    // Initialize tab switching
    initializeTabs();
    
    // Initialize form interactions
    initializeFormInteractions();
    
    // Initialize modal handlers
    initializeModals();
    
    // Setup live stats update (simulated)
    setupLiveStats();
    
    console.log('MQTT Cloud page setup complete');
}

function initializeButtons() {
    // Save Settings button
    const saveBtn = document.getElementById('save-settings');
    if (saveBtn) {
        saveBtn.addEventListener('click', handleSaveSettings);
    }
    
    // Test Connection button
    const testBtn = document.getElementById('test-connection');
    if (testBtn) {
        testBtn.addEventListener('click', handleTestConnection);
    }
    
    // Reset to Defaults button
    const resetBtn = document.getElementById('reset-settings');
    if (resetBtn) {
        resetBtn.addEventListener('click', handleResetSettings);
    }
    
    // Generate Password button
    const generatePassBtn = document.getElementById('generate-password');
    if (generatePassBtn) {
        generatePassBtn.addEventListener('click', generatePassword);
    }
    
    // Add Tags button
    const addTagsBtn = document.getElementById('add-tags-btn');
    if (addTagsBtn) {
        addTagsBtn.addEventListener('click', showAddTagModal);
    }
    
    // Remove Tags button
    const removeTagsBtn = document.getElementById('remove-tags-btn');
    if (removeTagsBtn) {
        removeTagsBtn.addEventListener('click', removeSelectedTags);
    }
    
    // MQTT Enabled toggle
    const mqttToggle = document.getElementById('mqtt-enabled');
    if (mqttToggle) {
        mqttToggle.addEventListener('change', toggleMqttConnection);
    }
}

function handleSaveSettings() {
    const saveBtn = document.getElementById('save-settings');
    if (!saveBtn) return;
    
    const originalText = saveBtn.innerHTML;
    
    // Show loading state
    saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Saving...';
    saveBtn.disabled = true;
    
    // Simulate API call
    setTimeout(() => {
        // Show success message
        saveBtn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Saved!';
        saveBtn.classList.remove('bg-primary', 'hover:bg-primaryHover');
        saveBtn.classList.add('bg-success', 'hover:bg-emerald-600');
        
        // Revert after 2 seconds
        setTimeout(() => {
            saveBtn.innerHTML = originalText;
            saveBtn.classList.remove('bg-success', 'hover:bg-emerald-600');
            saveBtn.classList.add('bg-primary', 'hover:bg-primaryHover');
            saveBtn.disabled = false;
        }, 2000);
        
        // Show notification
        showNotification('MQTT settings saved successfully!', 'success');
    }, 1500);
}

function handleTestConnection() {
    const testBtn = document.getElementById('test-connection');
    if (!testBtn) return;
    
    const originalText = testBtn.innerHTML;
    
    // Show loading state
    testBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Testing...';
    testBtn.disabled = true;
    
    // Simulate connection test
    setTimeout(() => {
        // Restore button
        testBtn.innerHTML = originalText;
        testBtn.disabled = false;
        
        // Show results modal
        showModal('testResultsModal');
        
        // Update stats with simulated data
        updateStats();
        
        // Show notification
        showNotification('Connection test successful!', 'success');
    }, 2000);
}

function handleResetSettings() {
    if (confirm('Reset all MQTT settings to default values?')) {
        // Reset form values
        document.getElementById('broker-host').value = 'mqtt.company.com';
        document.getElementById('broker-port').value = 8883;
        document.getElementById('client-id').value = 'univa-gw-01';
        document.getElementById('qos-level').value = '1';
        document.getElementById('broker-username').value = 'admin';
        document.getElementById('broker-password').value = '********';
        document.getElementById('publish-topic').value = 'gateway/data';
        document.getElementById('subscribe-topic').value = 'gateway/commands';
        document.getElementById('data-format').value = 'json';
        document.getElementById('publish-interval').value = 60;
        document.getElementById('keep-alive').value = 60;
        
        // Reset toggles
        document.getElementById('retain-messages').checked = true;
        document.getElementById('clean-session').checked = true;
        document.getElementById('tls-enabled').checked = true;
        document.getElementById('mqtt-enabled').checked = true;
        
        showNotification('Settings reset to defaults', 'success');
    }
}

function generatePassword() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*';
    let password = '';
    for (let i = 0; i < 16; i++) {
        password += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    
    const passwordField = document.getElementById('broker-password');
    if (passwordField) {
        // Show password temporarily
        passwordField.type = 'text';
        passwordField.value = password;
        
        // Hide after 3 seconds
        setTimeout(() => {
            passwordField.type = 'password';
            passwordField.value = '********';
        }, 3000);
        
        showNotification('Password generated and copied to field', 'success');
    }
}

function toggleMqttConnection(event) {
    const isEnabled = event.target.checked;
    const statusText = isEnabled ? 'enabled' : 'disabled';
    
    // Update UI based on status
    const connectionStatus = document.querySelector('.status-indicator');
    if (connectionStatus) {
        connectionStatus.className = isEnabled ? 'status-indicator online' : 'status-indicator offline';
        connectionStatus.textContent = isEnabled ? 'Connected' : 'Disconnected';
    }
    
    showNotification(`MQTT connection ${statusText}`, isEnabled ? 'success' : 'warning');
}

function initializeTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.getAttribute('data-tab');
            
            // Remove active class from all buttons and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => {
                content.classList.remove('active');
                content.style.display = 'none';
            });
            
            // Add active class to clicked button
            button.classList.add('active');
            
            // Show corresponding content
            const tabContent = document.getElementById(`tab-${tabId}`);
            if (tabContent) {
                tabContent.classList.add('active');
                tabContent.style.display = 'block';
            }
        });
    });
}

function initializeFormInteractions() {
    // Setup toggle switches
    document.querySelectorAll('.toggle-switch input').forEach(toggle => {
        toggle.addEventListener('change', function() {
            const label = this.nextElementSibling;
            label.style.backgroundColor = this.checked ? '#10B981' : '#CBD5E1';
        });
        
        // Initialize color
        const label = toggle.nextElementSibling;
        label.style.backgroundColor = toggle.checked ? '#10B981' : '#CBD5E1';
    });
    
    // Add form validation
    const formElements = document.querySelectorAll('input, select');
    formElements.forEach(element => {
        element.addEventListener('change', function() {
            validateFormField(this);
        });
    });
}

function validateFormField(element) {
    // Basic validation
    if (element.hasAttribute('required') && !element.value.trim()) {
        element.classList.add('border-red-300', 'bg-red-50');
        return false;
    } else {
        element.classList.remove('border-red-300', 'bg-red-50');
        return true;
    }
}

function initializeModals() {
    // Modal close buttons
    document.querySelectorAll('.modal-close').forEach(button => {
        button.addEventListener('click', function() {
            const modalId = this.getAttribute('data-modal');
            closeModal(modalId);
        });
    });
    
    // Add selected tags button
    const addSelectedBtn = document.getElementById('add-selected-tags');
    if (addSelectedBtn) {
        addSelectedBtn.addEventListener('click', addSelectedTags);
    }
    
    // Upload certificate button
    const uploadCertBtn = document.getElementById('upload-certificate');
    if (uploadCertBtn) {
        uploadCertBtn.addEventListener('click', uploadCertificate);
    }
}

function showAddTagModal() {
    showModal('addTagModal');
}

function addSelectedTags() {
    const selected = document.querySelectorAll('#addTagModal input[type="checkbox"]:checked');
    if (selected.length > 0) {
        showNotification(`${selected.length} tags added successfully!`, 'success');
        closeModal('addTagModal');
        
        // Clear selections
        document.querySelectorAll('#addTagModal input[type="checkbox"]').forEach(cb => {
            cb.checked = false;
        });
    } else {
        alert('Please select at least one tag to add.');
    }
}

function removeSelectedTags() {
    const selected = document.querySelectorAll('#tab-publishing input[type="checkbox"]:checked');
    
    if (selected.length > 0) {
        if (confirm(`Remove ${selected.length} selected tags?`)) {
            selected.forEach(checkbox => {
                const label = checkbox.nextElementSibling;
                if (label) {
                    label.parentElement.remove();
                }
            });
            showNotification(`${selected.length} tags removed`, 'success');
        }
    } else {
        alert('Please select tags to remove.');
    }
}

function uploadCertificate() {
    // Simulate upload
    setTimeout(() => {
        showNotification('Certificate uploaded successfully', 'success');
        closeModal('uploadCertModal');
    }, 1000);
}

function setupLiveStats() {
    // Simulate live stats updates
    setInterval(() => {
        updateStats();
    }, 5000); // Update every 5 seconds
}

function updateStats() {
    // Simulate random stat updates
    const messagesSent = document.getElementById('messages-sent');
    const lastSent = document.getElementById('last-sent');
    const errors = document.getElementById('errors');
    const latency = document.getElementById('latency');
    
    if (messagesSent) {
        const current = parseInt(messagesSent.textContent.replace(',', '')) || 0;
        messagesSent.textContent = (current + Math.floor(Math.random() * 10)).toLocaleString();
    }
    
    if (lastSent) {
        const times = ['Just now', '2.3s ago', '5.1s ago', '10s ago'];
        lastSent.textContent = times[Math.floor(Math.random() * times.length)];
    }
    
    if (latency) {
        latency.textContent = `${Math.floor(Math.random() * 50) + 50} ms`;
    }
    
    // Keep errors at 0 for demo
    if (errors) {
        errors.textContent = '0';
    }
}

// Modal helper functions (should be in common.js, but included here for completeness)
function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
    }
}

// Notification helper (should be in common.js)
function showNotification(message, type = 'success') {
    if (window.showNotification) {
        // Use the global function if available
        window.showNotification(message, type);
    } else {
        // Fallback notification
        alert(message);
    }
}// Cloud Connection Manager - Main JavaScript Module
// This will be called by the router when loading the page

// Global namespace for cloud connection manager
window.CloudConnectionManager = {
    // Configuration
    config: {
        "app": {
            "name": "Univa IoT Gateway",
            "version": "2.4.1",
            "maxConnections": 12
        },
        
        "connectionTypes": {
            "mqtt": {
                "name": "MQTT Broker",
                "description": "Standard IoT messaging protocol",
                "icon": "fa-solid fa-cloud",
                "color": "blue",
                "defaultName": "MQTT Broker",
                "formFile": "connection-forms/mqtt-form.html"
            },
            
            "http": {
                "name": "HTTP Endpoint",
                "description": "REST API endpoints",
                "icon": "fa-solid fa-globe",
                "color": "yellow",
                "defaultName": "HTTP API",
                "formFile": "connection-forms/http-form.html"
            },
            
            "aws": {
                "name": "AWS IoT Core",
                "description": "Amazon Web Services IoT",
                "icon": "fa-brands fa-aws",
                "color": "purple",
                "defaultName": "AWS IoT",
                "formFile": "connection-forms/aws-form.html"
            },
            
            "azure": {
                "name": "Azure IoT Hub",
                "description": "Microsoft Azure IoT",
                "icon": "fa-brands fa-microsoft",
                "color": "blue",
                "defaultName": "Azure IoT Hub",
                "formFile": "connection-forms/azure-form.html"
            },
            
            "grafana": {
                "name": "Grafana Cloud",
                "description": "Monitoring & Dashboards",
                "icon": "fa-solid fa-chart-line",
                "color": "orange",
                "defaultName": "Grafana Cloud",
                "formFile": "connection-forms/grafana-form.html"
            },
            
            "websocket": {
                "name": "WebSocket Server",
                "description": "Real-time bidirectional communication",
                "icon": "fa-solid fa-bolt",
                "color": "green",
                "defaultName": "WebSocket Server",
                "formFile": "connection-forms/websocket-form.html"
            },
            
            "ftp": {
                "name": "FTP Server",
                "description": "File transfer for data logs",
                "icon": "fa-solid fa-folder",
                "color": "orange",
                "defaultName": "FTP Server",
                "formFile": "connection-forms/ftp-form.html"
            },
            
            "udp": {
                "name": "UDP Stream",
                "description": "Low-latency unidirectional streaming",
                "icon": "fa-solid fa-wave-square",
                "color": "purple",
                "defaultName": "UDP Stream",
                "formFile": "connection-forms/udp-form.html"
            }
        },
        
        "defaultStats": {
            "messages": 0,
            "errors": 0,
            "latency": 0,
            "uptime": "0h 0m",
            "lastActive": "Never",
            "bandwidth": "0 MB",
            "successRate": "0%"
        },
        
        "defaultConnections": {
            "mqtt": {
                "id": "mqtt-primary",
                "type": "mqtt",
                "name": "Production MQTT Broker",
                "enabled": true,
                "config": {
                    "host": "broker.company.com",
                    "port": 8883,
                    "protocol": "mqtts",
                    "clientId": "univa-gw-01",
                    "qos": 1,
                    "username": "admin",
                    "password": "",
                    "tls": true,
                    "keepAlive": 60,
                    "cleanSession": true
                },
                "stats": {
                    "messages": 8953,
                    "errors": 0,
                    "latency": 95,
                    "uptime": "8h 12m",
                    "lastActive": "2.3s ago",
                    "bandwidth": "2.4 MB",
                    "successRate": "99.8%"
                }
            },
            "http": {
                "id": "http-analytics",
                "type": "http",
                "name": "Analytics API",
                "enabled": true,
                "config": {
                    "url": "https://api.company.com/v1/data",
                    "method": "POST",
                    "interval": 300,
                    "batchSize": 100,
                    "contentType": "application/json"
                },
                "stats": {
                    "messages": 3245,
                    "errors": 12,
                    "latency": 210,
                    "uptime": "1h 45m",
                    "lastActive": "5 min ago",
                    "bandwidth": "1.2 MB",
                    "successRate": "99.6%"
                }
            }
        }
    },
    
    // State
    connections: {},
    selectedConnectionId: null,
    selectedConnectionType: null,
    
    // Initialize the page
    init: function() {
        console.log('Cloud Connection Manager initialized');
        
        // Load connections
        this.loadConnections();
        
        // Bind event listeners
        this.bindEventListeners();
        
        // Initialize UI
        this.renderConnectionTypes();
        
        console.log('Cloud Connection Manager setup complete');
    },
    
    // Bind event listeners
    bindEventListeners: function() {
        // Handle cancel button
        const cancelBtn = document.getElementById('cancel-btn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', this.cancelChanges.bind(this));
        }
        
        // Handle save button
        const saveBtn = document.getElementById('header-save-btn');
        if (saveBtn) {
            saveBtn.addEventListener('click', this.saveAllConnections.bind(this));
        }
        
        // Handle gateway select
        const gatewaySelect = document.getElementById('gateway-select');
        if (gatewaySelect) {
            gatewaySelect.addEventListener('change', function() {
                if (confirm('Switch to another gateway? Unsaved changes will be lost.')) {
                    window.location.reload();
                } else {
                    this.value = 'Univa-GW-01';
                }
            });
        }
    },
    
    // Load connections from config
    loadConnections: function() {
        Object.values(this.config.defaultConnections).forEach(conn => {
            this.connections[conn.id] = conn;
            this.addConnectionToList(conn.id, conn);
        });
        
        this.updateConnectionCount();
        
        if (Object.keys(this.connections).length > 0 && !this.selectedConnectionId) {
            const firstId = Object.keys(this.connections)[0];
            this.selectConnection(firstId);
        }
    },
    
    // Show connection manager modal
    showConnectionManager: function() {
        this.showModal('connectionManagerModal');
        this.showConnectionTypeSelection();
    },
    
    // Show connection type selection
    showConnectionTypeSelection: function() {
        const typeSelection = document.getElementById('connectionTypeSelection');
        const formContainer = document.getElementById('connectionFormContainer');
        
        if (typeSelection) typeSelection.classList.remove('hidden');
        if (formContainer) formContainer.classList.add('hidden');
        
        this.selectedConnectionType = null;
    },
    
    // Render connection types grid
    renderConnectionTypes: function() {
        const grid = document.getElementById('connectionTypesGrid');
        if (!grid) return;
        
        grid.innerHTML = '';
        
        Object.entries(this.config.connectionTypes).forEach(([type, connectionConfig]) => {
            const card = document.createElement('div');
            card.className = 'connection-type-card';
            card.onclick = () => this.selectConnectionType(type);
            
            const colorMap = {
                blue: '#3B82F6',
                yellow: '#F59E0B',
                purple: '#8B5CF6',
                orange: '#F97316',
                green: '#10B981'
            };
            
            const color = colorMap[connectionConfig.color] || '#3B82F6';
            
            card.innerHTML = `
                <div class="connection-type-icon" style="background-color: ${color}20; color: ${color};">
                    <i class="${connectionConfig.icon}"></i>
                </div>
                <h4 class="font-semibold text-slate-900 text-sm mb-2">${connectionConfig.name}</h4>
                <p class="text-xs text-slate-600">${connectionConfig.description}</p>
            `;
            
            grid.appendChild(card);
        });
    },
    
    // Select connection type
    selectConnectionType: async function(type) {
        this.selectedConnectionType = type;
        const connectionConfig = this.config.connectionTypes[type];
        
        const typeSelection = document.getElementById('connectionTypeSelection');
        const formContainer = document.getElementById('connectionFormContainer');
        const formTitle = document.getElementById('formTitle');
        
        if (typeSelection) typeSelection.classList.add('hidden');
        if (formContainer) formContainer.classList.remove('hidden');
        if (formTitle) formTitle.textContent = `Configure ${connectionConfig.name}`;
        
        await this.renderConnectionForm(type);
    },
    
    // Render connection form
    renderConnectionForm: async function(type) {
        const formContent = document.getElementById('formContent');
        const connectionConfig = this.config.connectionTypes[type];
        
        if (!formContent || !connectionConfig) return;
        
        try {
            // Adjust path for SPA structure
            const formPath = `pages/${connectionConfig.formFile}`;
            const response = await fetch(formPath);
            
            if (!response.ok) throw new Error(`Failed to load form: ${response.status}`);
            
            const html = await response.text();
            formContent.innerHTML = html;
            
            this.initializeForm(type);
            
        } catch (error) {
            console.error('Error loading form:', error);
            formContent.innerHTML = this.createFallbackForm(type);
            this.initializeTemplateFields();
            
            // Add back button
            const backButton = document.createElement('button');
            backButton.onclick = () => this.showConnectionTypeSelection();
            backButton.className = 'mt-4 compact-button border border-slate-300 text-slate-700 hover:bg-slate-50';
            backButton.innerHTML = '<i class="fa-solid fa-arrow-left mr-1"></i> Back to Connection Types';
            formContent.appendChild(backButton);
        }
    },
    
    // Create fallback form
    createFallbackForm: function(type) {
        const connectionConfig = this.config.connectionTypes[type];
        
        return `
            <div class="form-section">
                <h5 class="form-section-title">Connection Configuration</h5>
                <div class="space-y-4">
                    <div>
                        <label class="block text-xs font-medium text-slate-700 mb-1">Connection Name</label>
                        <input type="text" id="field-name" class="w-full compact-input" placeholder="${connectionConfig?.defaultName || 'New Connection'}">
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-slate-700 mb-1">Host / Endpoint</label>
                        <input type="text" id="field-host" class="w-full compact-input" placeholder="example.com">
                    </div>
                </div>
            </div>
        `;
    },
    
    // Initialize form
    initializeForm: function(type) {
        if (type === 'mqtt') {
            this.initializeMqttFormTabs();
        } else if (type === 'http') {
            this.initializeHttpFormTabs();
        } else {
            this.initializeTemplateFields();
        }
    },
    
    // Initialize MQTT form tabs
    initializeMqttFormTabs: function() {
        const tabButtons = document.querySelectorAll('.tab-button');
        tabButtons.forEach(button => {
            button.addEventListener('click', function() {
                const tabName = this.textContent.toLowerCase().includes('connection') ? 'connection' :
                              this.textContent.toLowerCase().includes('topics') ? 'topics' :
                              this.textContent.toLowerCase().includes('publishing') ? 'publishing' : 'advanced';
                
                window.CloudConnectionManager.switchMqttTab(tabName);
            });
        });
        
        // Initialize form-specific logic if available
        if (typeof window.initializeMqttForm === 'function') {
            window.initializeMqttForm();
        }
        
        this.setupToggleSwitches();
    },
    
    // Initialize HTTP form tabs
    initializeHttpFormTabs: function() {
        const tabButtons = document.querySelectorAll('.tab-button');
        tabButtons.forEach(button => {
            button.addEventListener('click', function() {
                const tabName = this.textContent.toLowerCase().includes('connection') ? 'connection' :
                              this.textContent.toLowerCase().includes('payload') ? 'payload' :
                              this.textContent.toLowerCase().includes('publishing') ? 'publishing' : 'advanced';
                
                window.CloudConnectionManager.switchHttpTab(tabName);
            });
        });
        
        if (typeof window.initializeHttpForm === 'function') {
            window.initializeHttpForm();
        }
        
        this.setupToggleSwitches();
    },
    
    // Initialize template fields
    initializeTemplateFields: function() {
        document.querySelectorAll('.toggle-switch input').forEach(toggle => {
            toggle.addEventListener('change', function() {
                const label = this.nextElementSibling;
                label.style.backgroundColor = this.checked ? '#10B981' : '#CBD5E1';
            });
            
            const label = toggle.nextElementSibling;
            label.style.backgroundColor = toggle.checked ? '#10B981' : '#CBD5E1';
        });
        
        document.querySelectorAll('.key-value-list').forEach(list => {
            const addButton = list.querySelector('button');
            if (addButton) {
                addButton.onclick = function() {
                    window.CloudConnectionManager.addKeyValueItem(this);
                };
            }
            
            list.querySelectorAll('.key-value-item button').forEach(btn => {
                btn.onclick = function() {
                    window.CloudConnectionManager.removeKeyValueItem(this);
                };
            });
        });
    },
    
    // Setup toggle switches
    setupToggleSwitches: function() {
        document.querySelectorAll('.toggle-switch input').forEach(toggle => {
            toggle.addEventListener('change', function() {
                const label = this.nextElementSibling;
                label.style.backgroundColor = this.checked ? '#10B981' : '#CBD5E1';
            });
            
            const label = toggle.nextElementSibling;
            label.style.backgroundColor = toggle.checked ? '#10B981' : '#CBD5E1';
        });
    },
    
    // Cancel connection form
    cancelConnectionForm: function() {
        this.showConnectionTypeSelection();
    },
    
    // Save new connection
    saveNewConnection: function() {
        if (!this.selectedConnectionType) return;
        
        const connectionConfig = this.config.connectionTypes[this.selectedConnectionType];
        const formData = this.collectFormDataFromTemplate();
        
        const connectionId = `${this.selectedConnectionType}-${Date.now()}`;
        const name = formData.name || connectionConfig.defaultName;
        
        this.connections[connectionId] = {
            id: connectionId,
            type: this.selectedConnectionType,
            name: name,
            enabled: true,
            config: formData,
            stats: {...this.config.defaultStats}
        };
        
        this.addConnectionToList(connectionId, this.connections[connectionId]);
        
        this.closeModal('connectionManagerModal');
        
        if (window.showNotification) {
            window.showNotification(`${connectionConfig.name} added successfully`, 'success');
        }
        
        this.selectConnection(connectionId);
    },
    
    // Collect form data from template
    collectFormDataFromTemplate: function() {
        const formData = {};
        const formContent = document.getElementById('formContent');
        
        if (!formContent) return formData;
        
        // Collect input values
        formContent.querySelectorAll('input[type="text"], input[type="number"], input[type="password"]').forEach(input => {
            const id = input.id;
            if (id.startsWith('field-')) {
                const fieldName = id.replace('field-', '');
                formData[fieldName] = input.value;
            }
        });
        
        // Collect select values
        formContent.querySelectorAll('select').forEach(select => {
            const id = select.id;
            if (id.startsWith('field-')) {
                const fieldName = id.replace('field-', '');
                formData[fieldName] = select.value;
            }
        });
        
        // Collect checkbox values
        formContent.querySelectorAll('.toggle-switch input[type="checkbox"]').forEach(checkbox => {
            const id = checkbox.id;
            if (id.startsWith('field-')) {
                const fieldName = id.replace('field-', '');
                formData[fieldName] = checkbox.checked;
            }
        });
        
        // Collect radio values
        formContent.querySelectorAll('input[type="radio"]').forEach(radio => {
            const name = radio.name;
            if (name.startsWith('field-')) {
                const fieldName = name.replace('field-', '');
                if (radio.checked) {
                    formData[fieldName] = radio.value;
                }
            }
        });
        
        // Collect key-value pairs
        const keyValueData = {};
        formContent.querySelectorAll('.key-value-item').forEach(item => {
            const inputs = item.querySelectorAll('input[type="text"]');
            if (inputs.length >= 2) {
                const key = inputs[0].value.trim();
                const value = inputs[1].value.trim();
                if (key && value) {
                    keyValueData[key] = value;
                }
            }
        });
        
        if (Object.keys(keyValueData).length > 0) {
            formData.headers = keyValueData;
        }
        
        return formData;
    },
    
    // Add connection to list
    addConnectionToList: function(id, conn) {
        const list = document.getElementById('connectionsList');
        const connectionConfig = this.config.connectionTypes[conn.type];
        
        // Check if already exists
        if (document.querySelector(`[data-connection-id="${id}"]`)) {
            this.updateConnectionItem(id, conn);
            return;
        }
        
        // Remove placeholder if exists
        const placeholder = list.querySelector('.text-center');
        if (placeholder) {
            placeholder.remove();
        }
        
        // Color mapping
        const colorMap = {
            blue: 'border-blue-500 text-blue-600',
            yellow: 'border-yellow-500 text-yellow-600',
            purple: 'border-purple-500 text-purple-600',
            orange: 'border-orange-500 text-orange-600',
            green: 'border-green-500 text-green-600'
        };
        
        const colorClass = colorMap[connectionConfig.color] || 'border-blue-500 text-blue-600';
        
        const html = `
            <div data-connection-id="${id}" class="border-l-4 ${colorClass.split(' ')[0]} p-3 bg-white border ${this.selectedConnectionId === id ? 'border-blue-200 bg-blue-50' : 'border-slate-200'} rounded-lg cursor-pointer hover:border-blue-200 transition-colors" onclick="window.CloudConnectionManager.selectConnection('${id}')">
                <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center gap-2">
                        <i class="${connectionConfig.icon} ${colorClass.split(' ')[1]}"></i>
                        <span class="font-medium text-slate-900 text-sm">${conn.name}</span>
                    </div>
                    <span class="text-xs text-slate-500">${conn.stats.lastActive}</span>
                </div>
                <div class="text-xs text-slate-600 truncate mb-2">${this.getConnectionSummary(conn)}</div>
                <div class="flex justify-between items-center">
                    <span class="text-xs px-2 py-1 rounded ${conn.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}">
                        ${conn.enabled ? 'Active' : 'Inactive'}
                    </span>
                    <span class="text-xs font-medium">${conn.stats.messages.toLocaleString()} msgs</span>
                </div>
            </div>
        `;
        
        list.insertAdjacentHTML('afterbegin', html);
        this.updateConnectionCount();
    },
    
    // Update connection item
    updateConnectionItem: function(id, conn) {
        const item = document.querySelector(`[data-connection-id="${id}"]`);
        if (!item) return;
        
        const connectionConfig = this.config.connectionTypes[conn.type];
        const colorMap = {
            blue: 'text-blue-600',
            yellow: 'text-yellow-600',
            purple: 'text-purple-600',
            orange: 'text-orange-600',
            green: 'text-green-600'
        };
        
        const iconClass = colorMap[connectionConfig.color] || 'text-blue-600';
        
        // Update DOM elements
        const icon = item.querySelector('i');
        const nameSpan = item.querySelector('.font-medium');
        const timeSpan = item.querySelector('.text-xs.text-slate-500');
        const summaryDiv = item.querySelector('.text-slate-600');
        const statusSpan = item.querySelector('.bg-green-100, .bg-gray-100');
        const messagesSpan = item.querySelector('.font-medium:last-child');
        
        if (icon) icon.className = `${connectionConfig.icon} ${iconClass}`;
        if (nameSpan) nameSpan.textContent = conn.name;
        if (timeSpan) timeSpan.textContent = conn.stats.lastActive;
        if (summaryDiv) summaryDiv.textContent = this.getConnectionSummary(conn);
        
        if (statusSpan) {
            statusSpan.className = conn.enabled ? 'text-xs px-2 py-1 rounded bg-green-100 text-green-800' : 'text-xs px-2 py-1 rounded bg-gray-100 text-gray-800';
            statusSpan.textContent = conn.enabled ? 'Active' : 'Inactive';
        }
        
        if (messagesSpan) messagesSpan.textContent = `${conn.stats.messages.toLocaleString()} msgs`;
    },
    
    // Get connection summary
    getConnectionSummary: function(conn) {
        if (conn.type === 'mqtt' && conn.config.host) {
            const protocol = conn.config.protocol || 'mqtt://';
            const port = conn.config.port || (protocol.includes('mqtts') ? 8883 : 1883);
            return `${protocol}${conn.config.host}:${port}`;
        }
        if (conn.type === 'http' && conn.config.url) {
            return conn.config.url;
        }
        if (conn.config.endpoint) return conn.config.endpoint;
        if (conn.config.hostname) return conn.config.hostname;
        return `${this.config.connectionTypes[conn.type]?.name} Connection`;
    },
    
    // Select connection
    selectConnection: function(id) {
        this.selectedConnectionId = id;
        const conn = this.connections[id];
        
        if (!conn) {
            this.showEmptyConnectionState();
            return;
        }
        
        // Update UI for selected connection
        document.querySelectorAll('[data-connection-id]').forEach(el => {
            el.classList.remove('border-blue-200', 'bg-blue-50');
            el.classList.add('border-slate-200');
        });
        
        const selectedEl = document.querySelector(`[data-connection-id="${id}"]`);
        if (selectedEl) {
            selectedEl.classList.add('border-blue-200', 'bg-blue-50');
            selectedEl.classList.remove('border-slate-200');
        }
        
        this.updateConfigurationForConnection(conn);
    },
    
    // Show empty connection state
    showEmptyConnectionState: function() {
        document.getElementById('connectionName').textContent = 'No Connection Selected';
        document.getElementById('connectionDescription').textContent = 'Select a connection to view details';
        document.getElementById('statMessages').textContent = '0';
        document.getElementById('statErrors').textContent = '0';
        document.getElementById('statLastSent').textContent = 'Never';
        document.getElementById('statLatency').textContent = '0 ms';
        
        const diagnosticStatus = document.getElementById('diagnosticStatus');
        if (diagnosticStatus) {
            diagnosticStatus.className = 'status-indicator offline';
            diagnosticStatus.textContent = 'Disconnected';
        }
        
        // Clear diagnostic info
        const diagnosticIds = [
            'diagnosticLastMessage',
            'diagnosticPacketsSent', 
            'diagnosticPacketsReceived',
            'diagnosticLastError',
            'diagnosticLatency'
        ];
        
        diagnosticIds.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = id.includes('Error') ? 'None' : '0';
        });
        
        // Clear downlink commands
        const downlinkCommands = document.getElementById('downlinkCommands');
        if (downlinkCommands) {
            downlinkCommands.innerHTML = `
                <tr>
                    <td colspan="3" class="p-4 text-center text-slate-400 text-xs">
                        No commands received
                    </td>
                </tr>
            `;
        }
        
        // Clear tab content
        const tabContent = document.getElementById('tab-content-connection');
        if (tabContent) {
            tabContent.innerHTML = `
                <div class="text-center py-12 text-slate-400">
                    <i class="fa-solid fa-plug text-3xl mb-3"></i>
                    <p class="text-sm">Select a connection to configure</p>
                    <p class="text-xs mt-1">or click "Add Connection" to create a new one</p>
                </div>
            `;
        }
        
        // Hide other tabs
        const otherTabs = ['topics', 'publishing', 'advanced'];
        otherTabs.forEach(tab => {
            const tabEl = document.getElementById(`tab-content-${tab}`);
            if (tabEl) tabEl.style.display = 'none';
            
            const tabBtn = document.getElementById(`tab-${tab}`);
            if (tabBtn) tabBtn.style.display = 'none';
        });
        
        // Show only connection tab
        const connectionTab = document.getElementById('tab-connection');
        if (connectionTab) {
            connectionTab.style.display = 'block';
            connectionTab.classList.add('active');
        }
    },
    
    // Update configuration for connection
    updateConfigurationForConnection: async function(conn) {
        const connectionConfig = this.config.connectionTypes[conn.type];
        
        // Update basic info
        document.getElementById('connectionName').textContent = conn.name;
        document.getElementById('connectionDescription').textContent = `${connectionConfig.name} - ${connectionConfig.description}`;
        
        // Update stats
        document.getElementById('statMessages').textContent = conn.stats.messages.toLocaleString();
        document.getElementById('statErrors').textContent = conn.stats.errors;
        document.getElementById('statLastSent').textContent = conn.stats.lastActive;
        document.getElementById('statLatency').textContent = conn.stats.latency + ' ms';
        
        // Update diagnostics
        document.getElementById('diagnosticStatus').className = conn.enabled ? 'status-indicator online' : 'status-indicator offline';
        document.getElementById('diagnosticStatus').textContent = conn.enabled ? 'Connected' : 'Disconnected';
        document.getElementById('diagnosticLastMessage').textContent = conn.stats.lastActive;
        document.getElementById('diagnosticPacketsSent').textContent = conn.stats.messages.toLocaleString();
        document.getElementById('diagnosticPacketsReceived').textContent = Math.floor(conn.stats.messages * 0.01).toLocaleString();
        document.getElementById('diagnosticLastError').textContent = conn.stats.errors > 0 ? `${conn.stats.errors} errors` : 'None';
        document.getElementById('diagnosticLatency').textContent = conn.stats.latency + ' ms';
        
        // Update downlink commands
        if (conn.enabled) {
            document.getElementById('downlinkCommands').innerHTML = `
                <tr class="border-t border-slate-100">
                    <td class="p-2">10:43:12</td>
                    <td class="p-2 font-mono">SetSpeed=12</td>
                    <td class="p-2">
                        <span class="px-2 py-1 bg-green-50 text-green-700 rounded text-xs">Accepted</span>
                    </td>
                </tr>
                <tr class="border-t border-slate-100">
                    <td class="p-2">10:41:04</td>
                    <td class="p-2 font-mono">ResetWarning</td>
                    <td class="p-2">
                        <span class="px-2 py-1 bg-red-50 text-red-700 rounded text-xs">Failed</span>
                    </td>
                </tr>
            `;
        }
        
        // Show loading in tab content
        const tabContent = document.getElementById('tab-content-connection');
        if (tabContent) {
            tabContent.innerHTML = '<div class="text-center py-8"><i class="fa-solid fa-spinner fa-spin text-primary text-xl"></i><p class="text-xs text-slate-500 mt-2">Loading configuration...</p></div>';
        }
        
        // Hide other tabs initially
        ['topics', 'publishing', 'advanced'].forEach(tab => {
            const tabEl = document.getElementById(`tab-content-${tab}`);
            if (tabEl) tabEl.style.display = 'none';
        });
        
        // Show all tabs for this connection
        document.querySelectorAll('.tab-button').forEach(tab => {
            tab.style.display = 'block';
            if (tab.id === 'tab-connection') {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });
        
        // Load edit form
        await this.loadConnectionEditForm(conn);
    },
    
    // Load connection edit form
    loadConnectionEditForm: async function(conn) {
        const connectionConfig = this.config.connectionTypes[conn.type];
        const tabContent = document.getElementById('tab-content-connection');
        
        if (!tabContent) return;
        
        try {
            // Adjust path for SPA structure
            const formPath = `pages/${connectionConfig.formFile}`;
            const response = await fetch(formPath);
            
            if (!response.ok) throw new Error(`Failed to load form: ${response.status}`);
            
            const html = await response.text();
            
            tabContent.innerHTML = `
                <div class="space-y-6">
                    <div class="flex justify-between items-center mb-4">
                        <h4 class="text-sm font-semibold text-slate-900">${connectionConfig.name} Configuration</h4>
                        <div class="flex items-center gap-2">
                            <span class="text-xs text-slate-700">Enabled</span>
                            <label class="toggle-switch">
                                <input type="checkbox" id="connection-enabled" ${conn.enabled ? 'checked' : ''}>
                                <span class="toggle-slider"></span>
                            </label>
                        </div>
                    </div>
                    
                    <div class="form-section">
                        <h5 class="form-section-title">Connection Information</h5>
                        <div class="space-y-4">
                            <div>
                                <label class="block text-xs font-medium text-slate-700 mb-1">Connection Name</label>
                                <input type="text" id="edit-connection-name" 
                                       class="w-full compact-input"
                                       value="${conn.name}"
                                       placeholder="Enter connection name">
                            </div>
                        </div>
                    </div>
                    
                    <div id="edit-form-content">
                        ${html}
                    </div>
                    
                    <div class="pt-4 border-t border-slate-200">
                        <div class="flex justify-between items-center">
                            <div class="flex space-x-2">
                                <button onclick="window.CloudConnectionManager.testConnection()" class="compact-button border border-slate-300 text-slate-700 hover:bg-slate-50 flex items-center">
                                    <i class="fa-solid fa-bolt mr-1"></i> Test Connection
                                </button>
                                <button onclick="window.CloudConnectionManager.deleteConnection('${conn.id}')" class="compact-button border border-red-300 text-red-700 hover:bg-red-50 flex items-center">
                                    <i class="fa-solid fa-trash mr-1"></i> Delete
                                </button>
                            </div>
                            <button onclick="window.CloudConnectionManager.saveConnection('${conn.id}')" class="compact-button bg-primary hover:bg-primaryHover text-white flex items-center">
                                <i class="fa-solid fa-save mr-1"></i> Save Changes
                            </button>
                        </div>
                    </div>
                </div>
            `;
            
            this.populateFormWithData(conn);
            this.initializeForm(conn.type);
            
        } catch (error) {
            console.error('Error loading form:', error);
            tabContent.innerHTML = `
                <div class="text-center py-8 text-slate-400">
                    <i class="fa-solid fa-exclamation-triangle text-3xl mb-3"></i>
                    <p class="text-sm">Failed to load configuration form</p>
                    <p class="text-xs mt-1">${error.message}</p>
                </div>
            `;
        }
    },
    
    // Populate form with data
    populateFormWithData: function(conn) {
        const nameInput = document.getElementById('edit-connection-name');
        if (nameInput) nameInput.value = conn.name;
        
        const enabledCheckbox = document.getElementById('connection-enabled');
        if (enabledCheckbox) enabledCheckbox.checked = conn.enabled;
        
        // Populate form fields from config
        Object.entries(conn.config).forEach(([fieldName, value]) => {
            const fieldId = `field-${fieldName}`;
            const element = document.getElementById(fieldId);
            
            if (element) {
                if (element.type === 'checkbox') {
                    element.checked = value;
                } else if (element.type === 'radio') {
                    const radios = document.querySelectorAll(`input[name="${element.name}"][value="${value}"]`);
                    radios.forEach(radio => radio.checked = true);
                } else {
                    element.value = value;
                }
            }
        });
        
        // Populate key-value pairs (headers)
        if (conn.config.headers && typeof conn.config.headers === 'object') {
            const keyValueLists = document.querySelectorAll('.key-value-list');
            keyValueLists.forEach(list => {
                // Clear existing items (except add button)
                const items = list.querySelectorAll('.key-value-item');
                items.forEach(item => {
                    if (!item.querySelector('button[onclick*="addKeyValueItem"]')) {
                        item.remove();
                    }
                });
                
                // Add items from config
                const addButton = list.querySelector('button[onclick*="addKeyValueItem"]');
                if (addButton) {
                    Object.entries(conn.config.headers).forEach(([key, value]) => {
                        const newItem = document.createElement('div');
                        newItem.className = 'key-value-item';
                        newItem.innerHTML = `
                            <input type="text" value="${key}" placeholder="Key" class="compact-input">
                            <input type="text" value="${value}" placeholder="Value" class="compact-input">
                            <button type="button" class="text-red-600 hover:text-red-700" onclick="window.CloudConnectionManager.removeKeyValueItem(this)">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        `;
                        list.insertBefore(newItem, addButton.parentNode);
                    });
                }
            });
        }
    },
    
    // Save connection
    saveConnection: function(connectionId) {
        const conn = this.connections[connectionId];
        if (!conn) return;
        
        // Update name
        const nameInput = document.getElementById('edit-connection-name');
        if (nameInput) {
            conn.name = nameInput.value;
        }
        
        // Update enabled status
        const enabledCheckbox = document.getElementById('connection-enabled');
        if (enabledCheckbox) {
            conn.enabled = enabledCheckbox.checked;
        }
        
        // Update config from form
        const formData = this.collectFormDataFromEditForm();
        conn.config = {...conn.config, ...formData};
        
        // Update UI
        this.updateConnectionItem(connectionId, conn);
        this.updateConfigurationForConnection(conn);
        
        // Show notification
        if (window.showNotification) {
            window.showNotification(`${conn.name} updated successfully`, 'success');
        }
    },
    
    // Collect form data from edit form
    collectFormDataFromEditForm: function() {
        const formData = {};
        const editFormContent = document.getElementById('edit-form-content');
        
        if (!editFormContent) return formData;
        
        // Collect all form fields
        editFormContent.querySelectorAll('input[type="text"], input[type="number"], input[type="password"]').forEach(input => {
            const id = input.id;
            if (id.startsWith('field-')) {
                const fieldName = id.replace('field-', '');
                formData[fieldName] = input.value;
            }
        });
        
        editFormContent.querySelectorAll('select').forEach(select => {
            const id = select.id;
            if (id.startsWith('field-')) {
                const fieldName = id.replace('field-', '');
                formData[fieldName] = select.value;
            }
        });
        
        editFormContent.querySelectorAll('.toggle-switch input[type="checkbox"]').forEach(checkbox => {
            const id = checkbox.id;
            if (id.startsWith('field-')) {
                const fieldName = id.replace('field-', '');
                formData[fieldName] = checkbox.checked;
            }
        });
        
        editFormContent.querySelectorAll('input[type="radio"]').forEach(radio => {
            const name = radio.name;
            if (name.startsWith('field-')) {
                const fieldName = name.replace('field-', '');
                if (radio.checked) {
                    formData[fieldName] = radio.value;
                }
            }
        });
        
        // Collect key-value pairs
        const keyValueData = {};
        editFormContent.querySelectorAll('.key-value-item').forEach(item => {
            const inputs = item.querySelectorAll('input[type="text"]');
            if (inputs.length >= 2) {
                const key = inputs[0].value.trim();
                const value = inputs[1].value.trim();
                if (key && value) {
                    keyValueData[key] = value;
                }
            }
        });
        
        if (Object.keys(keyValueData).length > 0) {
            formData.headers = keyValueData;
        }
        
        return formData;
    },
    
    // Delete connection
    deleteConnection: function(connectionId) {
        const conn = this.connections[connectionId];
        if (!conn) return;
        
        if (!confirm(`Are you sure you want to delete "${conn.name}"?`)) {
            return;
        }
        
        const connName = conn.name;
        delete this.connections[connectionId];
        
        // Remove from UI
        const connectionElement = document.querySelector(`[data-connection-id="${connectionId}"]`);
        if (connectionElement) {
            connectionElement.remove();
        }
        
        this.updateConnectionCount();
        
        // Clear selection if deleted connection was selected
        if (this.selectedConnectionId === connectionId) {
            this.selectedConnectionId = null;
            this.showEmptyConnectionState();
        }
        
        // Show notification
        if (window.showNotification) {
            window.showNotification(`${connName} deleted successfully`, 'success');
        }
    },
    
    // Update connection count
    updateConnectionCount: function() {
        const count = Object.keys(this.connections).length;
        const countElement = document.getElementById('connectionCount');
        
        if (countElement) {
            countElement.textContent = count;
        }
        
        // Show placeholder if no connections
        const connectionsList = document.getElementById('connectionsList');
        if (count === 0 && connectionsList) {
            connectionsList.innerHTML = `
                <div class="text-center py-8 text-slate-400">
                    <i class="fa-solid fa-cloud text-3xl mb-3"></i>
                    <p class="text-sm">No connections yet</p>
                    <p class="text-xs mt-1">Click "Add Connection" to get started</p>
                </div>
            `;
        }
    },
    
    // Modal functions
    showModal: function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) modal.classList.add('active');
    },
    
    closeModal: function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) modal.classList.remove('active');
    },
    
    // Key-value list functions
    addKeyValueItem: function(button) {
        const list = button.closest('.key-value-list');
        if (!list) return;
        
        const keyPlaceholder = list.querySelector('input[placeholder*="Key"]')?.placeholder || 'Key';
        const valuePlaceholder = list.querySelector('input[placeholder*="Value"]')?.placeholder || 'Value';
        
        const item = document.createElement('div');
        item.className = 'key-value-item';
        item.innerHTML = `
            <input type="text" placeholder="${keyPlaceholder}" class="compact-input">
            <input type="text" placeholder="${valuePlaceholder}" class="compact-input">
            <button type="button" class="text-red-600 hover:text-red-700" onclick="window.CloudConnectionManager.removeKeyValueItem(this)">
                <i class="fa-solid fa-trash"></i>
            </button>
        `;
        
        list.insertBefore(item, button.parentNode);
    },
    
    removeKeyValueItem: function(button) {
        const item = button.closest('.key-value-item');
        if (item) item.remove();
    },
    
    // Generate password
    generatePassword: function(fieldId) {
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*';
        let password = '';
        for (let i = 0; i < 16; i++) {
            password += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        const field = document.getElementById(fieldId);
        if (field) field.value = password;
    },
    
    // Tab switching
    switchTab: function(tabName) {
        // Hide all tab contents
        document.querySelectorAll('[id^="tab-content-"]').forEach(tab => {
            tab.style.display = 'none';
        });
        
        // Remove active class from all tabs
        document.querySelectorAll('.tab-button').forEach(button => {
            button.classList.remove('active');
        });
        
        // Show selected tab
        const tabContent = document.getElementById(`tab-content-${tabName}`);
        if (tabContent) tabContent.style.display = 'block';
        
        // Activate selected tab button
        const tabButton = document.getElementById(`tab-${tabName}`);
        if (tabButton) tabButton.classList.add('active');
    },
    
    // MQTT tab switching
    switchMqttTab: function(tabName) {
        document.querySelectorAll('.mqtt-tab-content').forEach(tab => {
            tab.style.display = 'none';
        });
        
        document.querySelectorAll('.tab-button').forEach(button => {
            button.classList.remove('active');
        });
        
        const tabContent = document.getElementById(`mqtt-${tabName}-content`);
        if (tabContent) tabContent.style.display = 'block';
        
        const tabButtons = document.querySelectorAll('.tab-button');
        tabButtons.forEach(button => {
            if (button.textContent.toLowerCase().includes(tabName)) {
                button.classList.add('active');
            }
        });
    },
    
    // HTTP tab switching
    switchHttpTab: function(tabName) {
        document.querySelectorAll('.http-tab-content').forEach(tab => {
            tab.style.display = 'none';
        });
        
        document.querySelectorAll('.tab-button').forEach(button => {
            button.classList.remove('active');
        });
        
        const tabContent = document.getElementById(`http-${tabName}-content`);
        if (tabContent) tabContent.style.display = 'block';
        
        const tabButtons = document.querySelectorAll('.tab-button');
        tabButtons.forEach(button => {
            if (button.textContent.toLowerCase().includes(tabName)) {
                button.classList.add('active');
            }
        });
    },
    
    // Test connection
    testConnection: function() {
        const currentConn = this.connections[this.selectedConnectionId];
        if (!currentConn) {
            if (window.showNotification) {
                window.showNotification('Please select a connection first', 'warning');
            }
            return;
        }
        
        // Show testing notification
        if (window.showNotification) {
            window.showNotification(`Testing ${currentConn.name} connection...`, 'info');
        }
        
        // Simulate connection test
        setTimeout(() => {
            // Update stats
            currentConn.stats.messages += Math.floor(Math.random() * 100);
            currentConn.stats.lastActive = 'Just now';
            currentConn.stats.latency = Math.floor(Math.random() * 200);
            currentConn.stats.successRate = `${98 + Math.floor(Math.random() * 2)}%`;
            
            // Update UI
            this.updateConnectionItem(this.selectedConnectionId, currentConn);
            this.updateConfigurationForConnection(currentConn);
            
            // Show test results modal
            this.showTestResultsModal(currentConn);
            
            // Show success notification
            if (window.showNotification) {
                window.showNotification(`Connection test for ${currentConn.name} successful!`, 'success');
            }
        }, 1500);
    },
    
    // Show test results modal
    showTestResultsModal: function(conn) {
        const modalContent = document.querySelector('#testResultsModal .p-6');
        if (!modalContent) return;
        
        modalContent.innerHTML = `
            <div class="space-y-4">
                <div class="flex items-center justify-between">
                    <span class="text-sm text-slate-700">Connection Status:</span>
                    <span class="status-indicator online">Connected</span>
                </div>
                <div class="flex items-center justify-between">
                    <span class="text-sm text-slate-700">Latency:</span>
                    <span class="text-sm font-mono text-slate-900">${conn.stats.latency} ms</span>
                </div>
                <div class="flex items-center justify-between">
                    <span class="text-sm text-slate-700">Authentication:</span>
                    <span class="text-sm font-mono text-green-600">Success</span>
                </div>
                <div class="flex items-center justify-between">
                    <span class="text-sm text-slate-700">Messages Sent:</span>
                    <span class="text-sm font-mono text-slate-900">${conn.stats.messages.toLocaleString()}</span>
                </div>
            </div>
            <div class="mt-6 p-4 bg-green-50 rounded border border-green-200">
                <div class="flex items-center">
                    <i class="fa-solid fa-check-circle text-green-600 mr-2"></i>
                    <span class="text-sm text-green-800">Connection test successful! All systems operational.</span>
                </div>
            </div>
            <div class="flex justify-end mt-8 pt-6 border-t border-slate-200">
                <button onclick="window.CloudConnectionManager.closeModal('testResultsModal')" class="compact-button bg-primary hover:bg-primaryHover text-white">
                    Close
                </button>
            </div>
        `;
        
        this.showModal('testResultsModal');
    },
    
    // Save all connections
    saveAllConnections: function() {
        if (window.showNotification) {
            window.showNotification('All connections saved successfully!', 'success');
        }
    },
    
    // Cancel changes
    cancelChanges: function() {
        if (confirm('Discard all unsaved changes?')) {
            window.location.reload();
        }
    },
    
    // Show help
    showHelp: function() {
        alert('Cloud Connection Manager Help:\n\n1. Click "Add Connection" to create new cloud connections\n2. Select a connection type (MQTT, HTTP, AWS, Azure, Grafana, WebSocket, FTP, UDP)\n3. Configure the connection settings\n4. Test the connection before saving\n5. Manage multiple connections from the list\n\nMaximum connections: ' + this.config.app.maxConnections);
    }
};


// To this (keep both for compatibility):
window.initMqttCloud = function() {
    console.log('Initializing MQTT Cloud / Connection Manager via router');
    window.CloudConnectionManager.init();
};

// Also keep the cloud connection version for router
window.initCloudConnection = window.initMqttCloud;
// Export global functions for inline onclick handlers
window.showConnectionManager = function() {
    window.CloudConnectionManager.showConnectionManager();
};

window.showHelp = function() {
    window.CloudConnectionManager.showHelp();
};

window.switchTab = function(tabName) {
    window.CloudConnectionManager.switchTab(tabName);
};

window.cancelConnectionForm = function() {
    window.CloudConnectionManager.cancelConnectionForm();
};

window.saveNewConnection = function() {
    window.CloudConnectionManager.saveNewConnection();
};

window.generatePassword = function(fieldId) {
    window.CloudConnectionManager.generatePassword(fieldId);
};

window.addKeyValueItem = function(button) {
    window.CloudConnectionManager.addKeyValueItem(button);
};

window.removeKeyValueItem = function(button) {
    window.CloudConnectionManager.removeKeyValueItem(button);
};

window.closeModal = function(modalId) {
    window.CloudConnectionManager.closeModal(modalId);
};

// Ensure modals exist in layout.html
window.addEventListener('DOMContentLoaded', function() {
    // Check if modals exist, create them if not
    if (!document.getElementById('connectionManagerModal')) {
        console.warn('Connection Manager modal not found in layout.html');
    }
});