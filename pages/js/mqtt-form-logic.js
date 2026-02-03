// mqtt-form-logic.js
// Global variables for MQTT form
let mqttTopics = [];

// Initialize MQTT form
window.initializeMqttForm = function() {
    console.log('Initializing MQTT form');
    mqttTopics = [];
    
    // Generate random ID for client ID
    const randomId = Math.random().toString(36).substring(2, 8);
    const clientIdInput = document.getElementById('field-clientId');
    if (clientIdInput && clientIdInput.value.includes('${randomId}')) {
        clientIdInput.value = `univa-gateway-${randomId}`;
    }
    
    // Advanced tab toggle switches
    const lwtToggle = document.getElementById('field-advanced-enable-lwt');
    const lwtOptions = document.getElementById('advanced-lwt-options');
    if (lwtToggle && lwtOptions) {
        lwtToggle.addEventListener('change', function() {
            lwtOptions.style.display = this.checked ? 'block' : 'none';
        });
    }
    
    const compressionToggle = document.getElementById('field-advanced-enable-compression');
    const compressionOptions = document.getElementById('compression-options');
    if (compressionToggle && compressionOptions) {
        compressionToggle.addEventListener('change', function() {
            compressionOptions.style.display = this.checked ? 'block' : 'none';
        });
    }
    
    // Initialize topics
    initializeTopics();
    
    // Add event listeners to tag checkboxes
    setupTagCheckboxListeners();
    
    console.log('MQTT form initialized successfully');
};

// Initialize topics
function initializeTopics() {
    // Load default topics
    updateTopicList();
    
    // Populate sample data in publishing table
    updateTopicDropdowns();
}

// Update the list of available topics
function updateTopicList() {
    const baseTopic = document.getElementById('field-baseTopic');
    if (!baseTopic) return;
    
    const baseTopicValue = baseTopic.value;
    const topics = [];
    
    // Add base topic
    if (baseTopicValue) {
        topics.push({
            id: 'base',
            name: 'base',
            fullTopic: baseTopicValue,
            type: 'base'
        });
    }
    
    // Add custom topics
    const customTopicInputs = document.querySelectorAll('#custom-topics-container input[type="text"]');
    customTopicInputs.forEach((input, index) => {
        if (input.value) {
            const fullTopic = baseTopicValue ? `${baseTopicValue}/${input.value}` : input.value;
            topics.push({
                id: `custom-${index}`,
                name: input.value,
                fullTopic: fullTopic,
                type: 'custom'
            });
        }
    });
    
    mqttTopics = topics;
    updateTopicDropdowns();
}

// Update topic dropdowns in publishing table
function updateTopicDropdowns() {
    const topicOptions = generateTopicOptions();
    const topicSelects = document.querySelectorAll('#mqtt-tags-table select.topic-select');
    topicSelects.forEach(select => {
        select.innerHTML = topicOptions;
    });
}

// Generate HTML options for topic dropdowns
function generateTopicOptions() {
    let options = '';
    
    if (mqttTopics.length === 0) {
        const baseTopic = document.getElementById('field-baseTopic');
        if (baseTopic && baseTopic.value) {
            options = `<option value="${baseTopic.value}">${baseTopic.value} (base)</option>`;
        }
    } else {
        mqttTopics.forEach(topic => {
            options += `<option value="${topic.fullTopic}">${topic.fullTopic}</option>`;
        });
    }
    
    return options;
}

// Update all topic options when topics change
function updateAllTopicOptions() {
    updateTopicList();
}

// Add new custom topic
function addNewCustomTopic() {
    const container = document.getElementById('custom-topics-container');
    const div = document.createElement('div');
    div.className = 'custom-topic-item';
    div.innerHTML = `
        <div class="flex items-center gap-2">
            <input type="text" 
                   class="w-full compact-input"
                   placeholder="Enter topic name"
                   onchange="window.mqttFormLogic.updateAllTopicOptions()">
            <button type="button" class="compact-button border border-red-300 text-red-700 hover:bg-red-50" onclick="window.mqttFormLogic.removeCustomTopic(this)">
                <i class="fa-solid fa-trash"></i>
            </button>
        </div>
    `;
    container.appendChild(div);
    updateTopicList();
}

// Remove custom topic
function removeCustomTopic(button) {
    const item = button.closest('.custom-topic-item');
    if (item) {
        item.remove();
        updateTopicList();
    }
}

// Setup event listeners for tag checkboxes
function setupTagCheckboxListeners() {
    // Use event delegation since checkboxes are dynamically added
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('tag-select')) {
            updateSelectedTagsCount();
        }
    });
}

// Tab switching for MQTT form
function switchMqttTab(tabName) {
    // Hide all tab contents
    document.querySelectorAll('.mqtt-tab-content').forEach(tab => {
        tab.style.display = 'none';
    });
    
    // Remove active class from all tab buttons
    document.querySelectorAll('.tab-button').forEach(button => {
        button.classList.remove('active');
    });
    
    // Show selected tab content
    const tabContent = document.getElementById(`mqtt-${tabName}-content`);
    if (tabContent) {
        tabContent.style.display = 'block';
    }
    
    // Activate tab button
    const tabButtons = document.querySelectorAll('.tab-button');
    tabButtons.forEach(button => {
        if (button.textContent.toLowerCase().includes(tabName.charAt(0).toUpperCase() + tabName.slice(1))) {
            button.classList.add('active');
        }
    });
    
    // When switching to Topics & Format tab, refresh topic list
    if (tabName === 'topics') {
        updateTopicList();
    }
}

// Tag management functions
function toggleAllTags() {
    const selectAll = document.getElementById('select-all-tags');
    if (!selectAll) return;
    
    const checkboxes = document.querySelectorAll('.tag-select');
    checkboxes.forEach(cb => {
        cb.checked = selectAll.checked;
    });
    updateSelectedTagsCount();
}

function updateSelectedTagsCount() {
    const checkboxes = document.querySelectorAll('.tag-select:checked');
    const countElement = document.getElementById('selected-tags-count');
    if (countElement) {
        countElement.textContent = checkboxes.length;
    }
}

function removeSelectedMqttTags() {
    const selected = document.querySelectorAll('.tag-select:checked');
    if (selected.length === 0) {
        alert('Please select items to remove.');
        return;
    }
    
    if (confirm(`Remove ${selected.length} selected tags?`)) {
        selected.forEach(checkbox => {
            const row = checkbox.closest('tr');
            if (row) row.remove();
        });
        updateSelectedTagsCount();
        alert(`${selected.length} tags removed successfully.`);
    }
}

// Handle certificate upload
function handleCertificateUpload(input, nameSpanId) {
    const fileName = input.files[0]?.name || 'No file selected';
    const nameSpan = document.getElementById(nameSpanId);
    if (nameSpan) {
        nameSpan.textContent = fileName;
    }
}

// Generate random password
function generatePassword(fieldId) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*';
    let password = '';
    for (let i = 0; i < 12; i++) {
        password += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    const field = document.getElementById(fieldId);
    if (field) {
        field.value = password;
    }
}

// Show add tag modal
function showAddTagModal() {
    const tagName = prompt('Enter Tag Name:');
    if (tagName) {
        addNewItemToTable(tagName);
    }
}

// Add new item to table
function addNewItemToTable(tagName) {
    const rowIndex = document.querySelectorAll('#mqtt-tags-table tr').length;
    const topicOptions = generateTopicOptions();
    
    const rowHtml = `
        <tr class="border-t border-slate-100">
            <td class="p-2"><input type="checkbox" class="tag-select"></td>
            <td class="p-2 font-mono">${tagName}</td>
            <td class="p-2">
                <select class="w-full compact-select text-xs topic-select">
                    ${topicOptions}
                </select>
            </td>
            <td class="p-2">
                <select class="w-full compact-select text-xs publish-rate-select">
                    <option value="onChange" selected>On Change</option>
                    <option value="100">100 ms</option>
                    <option value="500">500 ms</option>
                    <option value="1000">1 sec</option>
                    <option value="5000">5 sec</option>
                </select>
            </td>
            <td class="p-2">
                <label class="toggle-switch">
                    <input type="checkbox" class="enabled-toggle" checked>
                    <span class="toggle-slider"></span>
                </label>
            </td>
        </tr>
    `;
    
    const table = document.getElementById('mqtt-tags-table');
    if (table) {
        table.insertAdjacentHTML('beforeend', rowHtml);
        updateSelectedTagsCount();
    }
}

// Save functions for each tab
function saveMqttConnectionSettings() {
    alert('MQTT Connection settings saved!');
}

function saveMqttTopicSettings() {
    alert('MQTT Topics & Format settings saved!');
}

function saveMqttPublishingSettings() {
    alert('MQTT Publishing settings saved!');
}

function saveMqttAdvancedSettings() {
    alert('MQTT Advanced settings saved!');
}

// Export functions to global scope
window.mqttFormLogic = {
    initializeMqttForm,
    updateAllTopicOptions,
    addNewCustomTopic,
    removeCustomTopic,
    switchMqttTab,
    toggleAllTags,
    removeSelectedMqttTags,
    handleCertificateUpload,
    generatePassword,
    showAddTagModal,
    saveMqttConnectionSettings,
    saveMqttTopicSettings,
    saveMqttPublishingSettings,
    saveMqttAdvancedSettings
};