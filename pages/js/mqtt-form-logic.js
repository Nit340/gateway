// MQTT Form Logic Handler
const MqttFormHandler = {
    
    init: function() {
        console.log('Initializing MQTT form handler');
        this.bindEvents();
        this.setupToggleSwitches();
        this.generateRandomClientId();
    },
    
    bindEvents: function() {
        // Tab navigation
        document.addEventListener('click', (e) => {
            if (e.target.hasAttribute('data-tab')) {
                this.switchMqttTab(e.target.dataset.tab);
            }
        });
        
        // Action buttons
        document.addEventListener('click', (e) => {
            if (e.target.hasAttribute('data-action')) {
                this.handleAction(e.target.dataset.action, e.target);
            }
        });
        
        // Topic input changes
        const topicInputs = ['baseTopic', 'telemetryTopic', 'alarmTopic', 'eventTopic', 'commandTopic'];
        topicInputs.forEach(id => {
            const element = document.getElementById(`field-${id}`);
            if (element) {
                element.addEventListener('change', () => this.handleTopicChange());
            }
        });
        
        // Publish mode changes
        document.addEventListener('change', (e) => {
            if (e.target.name === 'field-publishMode') {
                this.updatePublishMode();
            }
        });
    },
    
    switchMqttTab: function(tabName) {
        // Hide all tab contents
        document.querySelectorAll('.mqtt-tab-content').forEach(tab => {
            tab.style.display = 'none';
        });
        
        // Remove active class from all tab buttons
        document.querySelectorAll('[data-tab]').forEach(button => {
            button.classList.remove('active');
        });
        
        // Show selected tab content
        const tabContent = document.getElementById(`mqtt-${tabName}-content`);
        if (tabContent) {
            tabContent.style.display = 'block';
        }
        
        // Activate tab button
        const activeButton = document.querySelector(`[data-tab="${tabName}"]`);
        if (activeButton) {
            activeButton.classList.add('active');
        }
        
        console.log(`Switched to ${tabName} tab`);
    },
    
    handleAction: function(action, element) {
        console.log('Action:', action, element);
        
        switch(action) {
            case 'generate-password':
                const targetField = element.dataset.target;
                this.generatePassword(targetField);
                break;
                
            case 'save-mqtt-connection':
                this.saveMqttConnectionSettings();
                break;
                
            case 'save-mqtt-topics':
                this.saveMqttTopicSettings();
                break;
                
            case 'save-mqtt-publishing':
                this.saveMqttPublishingSettings();
                break;
                
            case 'save-mqtt-advanced':
                this.saveMqttAdvancedSettings();
                break;
                
            case 'add-custom-topic':
                const topicType = element.dataset.topicType;
                this.addCustomTopic(topicType);
                break;
                
            case 'add-new-custom-topic':
                this.addNewCustomTopic();
                break;
                
            case 'show-add-tag-modal':
                this.showAddTagModal();
                break;
                
            case 'remove-selected-tags':
                this.removeSelectedTags();
                break;
        }
    },
    
    generateRandomClientId: function() {
        const randomId = Math.random().toString(36).substring(2, 8);
        const clientIdInput = document.getElementById('field-clientId');
        if (clientIdInput) {
            clientIdInput.value = `univa-gateway-${randomId}`;
        }
    },
    
    generatePassword: function(fieldId) {
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*';
        let password = '';
        for (let i = 0; i < 12; i++) {
            password += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        const field = document.getElementById(fieldId);
        if (field) {
            field.value = password;
            showNotification('Password generated successfully', 'success');
        }
    },
    
    setupToggleSwitches: function() {
        // This will be called after the form loads
        console.log('Setting up toggle switches');
    },
    
    handleTopicChange: function() {
        console.log('Topic changed - would update topic list here');
    },
    
    updatePublishMode: function() {
        const selectedMode = document.querySelector('input[name="field-publishMode"]:checked')?.value || 'onChange';
        const helpText = document.getElementById('publish-mode-help');
        
        if (helpText) {
            const helpTexts = {
                'onChange': 'Publish individual tag values when they change',
                'periodic': 'Publish batched data at regular intervals',
                'event': 'Publish only when specific events occur'
            };
            helpText.textContent = helpTexts[selectedMode];
        }
        
        console.log(`Publish mode changed to: ${selectedMode}`);
    },
    
    addCustomTopic: function(type) {
        const topicInput = document.getElementById(`field-${type}Topic`);
        if (topicInput && topicInput.value) {
            // Add to custom topics container
            this.addCustomTopicItem(topicInput.value);
            showNotification(`Topic "${topicInput.value}" added to custom topics`, 'success');
        }
    },
    
    addNewCustomTopic: function() {
        const container = document.getElementById('custom-topics-container');
        const div = document.createElement('div');
        div.className = 'custom-topic-item';
        div.innerHTML = `
            <div class="flex items-center gap-2">
                <input type="text" 
                       class="w-full compact-input"
                       placeholder="Enter topic name">
                <button type="button" class="compact-button border border-red-300 text-red-700 hover:bg-red-50" data-action="remove-custom-topic">
                    <i class="fa-solid fa-trash"></i>
                </button>
            </div>
        `;
        container.appendChild(div);
        
        showNotification('Custom topic field added', 'info');
    },
    
    addCustomTopicItem: function(topicName) {
        const container = document.getElementById('custom-topics-container');
        const div = document.createElement('div');
        div.className = 'custom-topic-item';
        div.innerHTML = `
            <div class="flex items-center gap-2">
                <input type="text" 
                       class="w-full compact-input"
                       value="${topicName}">
                <button type="button" class="compact-button border border-red-300 text-red-700 hover:bg-red-50" data-action="remove-custom-topic">
                    <i class="fa-solid fa-trash"></i>
                </button>
            </div>
        `;
        container.appendChild(div);
    },
    
    showAddTagModal: function() {
        const publishMode = document.querySelector('input[name="field-publishMode"]:checked')?.value || 'onChange';
        const modalTitle = publishMode === 'event' ? 'Add New Event' : 'Add New Tag';
        const itemName = prompt(`Enter ${publishMode === 'event' ? 'Event' : 'Tag'} Name:`);
        if (itemName) {
            showNotification(`${itemName} added successfully`, 'success');
        }
    },
    
    removeSelectedTags: function() {
        const selectedMode = document.querySelector('input[name="field-publishMode"]:checked')?.value || 'onChange';
        const itemType = selectedMode === 'event' ? 'events' : 'tags';
        
        if (confirm(`Remove selected ${itemType}? This is a demo - no actual data will be removed.`)) {
            showNotification(`Selected ${itemType} removed successfully`, 'success');
        }
    },
    
    saveMqttConnectionSettings: function() {
        const settings = {
            protocol: document.getElementById('field-protocol')?.value,
            host: document.getElementById('field-host')?.value,
            port: document.getElementById('field-port')?.value,
            clientId: document.getElementById('field-clientId')?.value,
            keepAlive: document.getElementById('field-keepAlive')?.value,
            username: document.getElementById('field-username')?.value,
            password: document.getElementById('field-password')?.value,
            tls: document.getElementById('field-tls')?.checked,
            qos: document.querySelector('input[name="field-qos"]:checked')?.value,
            cleanSession: document.getElementById('field-cleanSession')?.checked,
            retainMessages: document.getElementById('field-retainMessages')?.checked
        };
        
        console.log('Saving MQTT connection settings:', settings);
        showNotification('MQTT connection settings saved!', 'success');
    },
    
    saveMqttTopicSettings: function() {
        console.log('Saving MQTT topic settings');
        showNotification('MQTT topic settings saved!', 'success');
    },
    
    saveMqttPublishingSettings: function() {
        console.log('Saving MQTT publishing settings');
        showNotification('MQTT publishing settings saved!', 'success');
    },
    
    saveMqttAdvancedSettings: function() {
        console.log('Saving MQTT advanced settings');
        showNotification('MQTT advanced settings saved!', 'success');
    }
};

// Initialize MQTT form when loaded
window.initializeMqttForm = function() {
    // Wait a bit for the DOM to be ready
    setTimeout(() => {
        MqttFormHandler.init();
        console.log('MQTT form initialized successfully');
    }, 100);
};