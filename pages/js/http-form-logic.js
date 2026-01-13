// http-form-logic.js
// Initialize HTTP form
window.initializeHttpForm = function() {
    console.log('Initializing HTTP form');
    
    // Setup authentication type change
    const authTypeSelect = document.getElementById('field-authType');
    const basicAuthFields = document.getElementById('basic-auth-fields');
    const tokenAuthFields = document.getElementById('token-auth-fields');
    const oauth2Fields = document.getElementById('oauth2-fields');
    
    if (authTypeSelect) {
        authTypeSelect.addEventListener('change', function() {
            const authType = this.value;
            
            // Show/hide appropriate auth fields
            if (basicAuthFields) basicAuthFields.style.display = authType === 'basic' ? 'block' : 'none';
            if (tokenAuthFields) tokenAuthFields.style.display = authType === 'bearer' || authType === 'apiKey' ? 'block' : 'none';
            if (oauth2Fields) oauth2Fields.style.display = authType === 'oauth2' ? 'block' : 'none';
        });
        
        // Trigger initial state
        authTypeSelect.dispatchEvent(new Event('change'));
    }
    
    // Setup payload format change
    const payloadRadios = document.querySelectorAll('input[name="field-payloadFormat"]');
    const jsonOptions = document.getElementById('json-format-options');
    const xmlOptions = document.getElementById('xml-format-options');
    const customOptions = document.getElementById('custom-format-options');
    
    payloadRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            const format = this.value;
            
            if (jsonOptions) jsonOptions.style.display = format === 'json' ? 'block' : 'none';
            if (xmlOptions) xmlOptions.style.display = format === 'xml' ? 'block' : 'none';
            if (customOptions) customOptions.style.display = format === 'custom' ? 'block' : 'none';
        });
    });
    
    // Setup publishing mode change
    const publishRadios = document.querySelectorAll('input[name="field-publishMode"]');
    const batchSettings = document.getElementById('batch-settings');
    const conditionalSettings = document.getElementById('conditional-settings');
    
    publishRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            const mode = this.value;
            
            if (batchSettings) batchSettings.style.display = mode === 'batch' ? 'block' : 'none';
            if (conditionalSettings) conditionalSettings.style.display = mode === 'conditional' ? 'block' : 'none';
        });
    });
    
    // Setup store & forward toggle
    const storeForwardToggle = document.getElementById('field-storeForward');
    const storeForwardOptions = document.getElementById('store-forward-options');
    
    if (storeForwardToggle && storeForwardOptions) {
        storeForwardToggle.addEventListener('change', function() {
            storeForwardOptions.style.display = this.checked ? 'block' : 'none';
        });
        
        // Trigger initial state
        storeForwardToggle.dispatchEvent(new Event('change'));
    }
    
    // Setup toggle switches
    document.querySelectorAll('.toggle-switch input').forEach(toggle => {
        toggle.addEventListener('change', function() {
            const label = this.nextElementSibling;
            if (label) {
                label.style.backgroundColor = this.checked ? '#10B981' : '#CBD5E1';
            }
        });
        
        // Set initial color
        const label = toggle.nextElementSibling;
        if (label) {
            label.style.backgroundColor = toggle.checked ? '#10B981' : '#CBD5E1';
        }
    });
    
    // Initialize tag selection
    updateHttpSelectedTagsCount();
    
    console.log('HTTP form initialized successfully');
};

// Tab switching for HTTP form
function switchHttpTab(tabName) {
    // Hide all tab contents
    document.querySelectorAll('.http-tab-content').forEach(tab => {
        tab.style.display = 'none';
    });
    
    // Remove active class from all tab buttons
    document.querySelectorAll('.tab-button').forEach(button => {
        button.classList.remove('active');
    });
    
    // Show selected tab content
    const tabContent = document.getElementById(`http-${tabName}-content`);
    if (tabContent) {
        tabContent.style.display = 'block';
    }
    
    // Activate tab button
    const tabButtons = document.querySelectorAll('.tab-button');
    tabButtons.forEach(button => {
        if (button.textContent.toLowerCase().includes(tabName)) {
            button.classList.add('active');
        }
    });
}

// Tag management functions for HTTP form
function toggleAllHttpTags() {
    const selectAll = document.getElementById('http-select-all-tags');
    const checkboxes = document.querySelectorAll('.http-tag-select');
    checkboxes.forEach(cb => {
        cb.checked = selectAll.checked;
    });
    updateHttpSelectedTagsCount();
}

function updateHttpSelectedTagsCount() {
    const checkboxes = document.querySelectorAll('.http-tag-select:checked');
    const countElement = document.getElementById('http-selected-tags-count');
    if (countElement) {
        countElement.textContent = checkboxes.length;
    }
}

function removeSelectedHttpTags() {
    const selected = document.querySelectorAll('.http-tag-select:checked');
    if (selected.length === 0) {
        alert('Please select tags to remove.');
        return;
    }
    
    if (confirm(`Remove ${selected.length} selected tag(s)?`)) {
        selected.forEach(checkbox => {
            const row = checkbox.closest('tr');
            if (row) row.remove();
        });
        updateHttpSelectedTagsCount();
        alert(`${selected.length} tag(s) removed successfully.`);
    }
}

// Add event listeners to tag checkboxes
function setupHttpTagListeners() {
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('http-tag-select')) {
            updateHttpSelectedTagsCount();
        }
    });
}

// Save functions for each tab
function saveHttpConnectionSettings() {
    alert('HTTP Connection settings saved!');
}

function saveHttpPayloadSettings() {
    alert('HTTP Payload Format settings saved!');
}

function saveHttpPublishingSettings() {
    alert('HTTP Publishing settings saved!');
}

function saveHttpAdvancedSettings() {
    alert('HTTP Advanced settings saved!');
}

// Generate password
function generateHttpPassword(fieldId) {
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

// Add key-value item
function addKeyValueItemHttp(button) {
    const list = button.closest('.key-value-list');
    const div = document.createElement('div');
    div.className = 'key-value-item';
    div.innerHTML = `
        <input type="text" placeholder="Header Name" class="compact-input">
        <input type="text" placeholder="Header Value" class="compact-input">
        <button type="button" class="text-red-600 hover:text-red-700" onclick="window.httpFormLogic.removeKeyValueItem(this)">
            <i class="fa-solid fa-trash"></i>
        </button>
    `;
    
    if (list) {
        const addButtonContainer = list.querySelector('.p-2.text-center');
        if (addButtonContainer) {
            list.insertBefore(div, addButtonContainer);
        }
    }
}

// Remove key-value item
function removeKeyValueItem(button) {
    const item = button.closest('.key-value-item');
    if (item) {
        item.remove();
    }
}

// Export functions to global scope
window.httpFormLogic = {
    initializeHttpForm,
    switchHttpTab,
    toggleAllHttpTags,
    removeSelectedHttpTags,
    generateHttpPassword,
    addKeyValueItemHttp,
    removeKeyValueItem,
    saveHttpConnectionSettings,
    saveHttpPayloadSettings,
    saveHttpPublishingSettings,
    saveHttpAdvancedSettings
};

// Setup initial listeners when this file loads
document.addEventListener('DOMContentLoaded', function() {
    setupHttpTagListeners();
});