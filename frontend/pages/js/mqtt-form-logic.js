// mqtt-form-logic.js  — UI-only logic for mqtt-form.html
// Schema-aligned to ilx_iot_gateway config with simplified connection settings
'use strict';

window.initializeMqttForm = function () {
    // Auto-generate client ID if empty
    const cid = document.getElementById('field-clientId');
    if (cid && !cid.value) {
        cid.value = 'univa-gateway-' + Math.random().toString(36).substring(2, 8);
    }
    
    // Auto-generate device token if empty
    const dt = document.getElementById('field-deviceToken');
    if (dt && !dt.value) {
        dt.value = 'dev_' + Math.random().toString(36).substring(2, 10) + Math.random().toString(36).substring(2, 4);
    }
    
    // Set default host if empty
    const host = document.getElementById('field-host');
    if (host && !host.value) {
        host.value = '127.0.0.1';
    }
    
    // Set default port if empty
    const port = document.getElementById('field-port');
    if (port && !port.value) {
        port.value = '1883';
    }
    
    // Set default keep alive if empty
    const keepAlive = document.getElementById('field-keepAlive');
    if (keepAlive && !keepAlive.value) {
        keepAlive.value = '60';
    }
    
    // LWT toggle
    const lwtToggle = document.getElementById('field-advanced-enable-lwt');
    const lwtOpts   = document.getElementById('advanced-lwt-options');
    if (lwtToggle && lwtOpts) {
        lwtToggle.addEventListener('change', function () { 
            lwtOpts.style.display = this.checked ? 'block' : 'none'; 
        });
        lwtOpts.style.display = lwtToggle.checked ? 'block' : 'none';
    }
    
    // Compression toggle
    const compToggle = document.getElementById('field-advanced-enable-compression');
    const compOpts   = document.getElementById('compression-options');
    if (compToggle && compOpts) {
        compToggle.addEventListener('change', function () { 
            compOpts.style.display = this.checked ? 'block' : 'none'; 
        });
        compOpts.style.display = compToggle.checked ? 'block' : 'none';
    }
    
    _setupTagCheckboxListeners();
};

function _setupTagCheckboxListeners() {
    document.addEventListener('click', function (e) {
        if (e.target.classList.contains('tag-select')) _updateCount();
    });
    
    // Also listen for change events on checkboxes
    document.addEventListener('change', function (e) {
        if (e.target.classList.contains('tag-select')) _updateCount();
    });
}

function _updateCount() {
    const n = document.querySelectorAll('.tag-select:checked').length;
    const el = document.getElementById('selected-tags-count');
    if (el) el.textContent = n;
}

// Tab switching
function switchMqttTab(name) {
    // Hide all tab contents
    document.querySelectorAll('.mqtt-tab-content').forEach(t => t.style.display = 'none');
    
    // Remove active class from all tab buttons
    document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
    
    // Show selected tab content
    const content = document.getElementById(`mqtt-${name}-content`);
    if (content) content.style.display = 'block';
    
    // Update active tab button
    document.querySelectorAll('.tab-button').forEach(b => {
        const tabText = b.textContent.trim().toLowerCase();
        if (name === 'connection' && tabText.startsWith('connection')) {
            b.classList.add('active');
        } else if (name === 'topics' && (tabText.startsWith('channels') || tabText.startsWith('topics'))) {
            b.classList.add('active');
        } else if (name === 'publishing' && tabText.startsWith('tag')) {
            b.classList.add('active');
        } else if (name === 'advanced' && tabText.startsWith('advanced')) {
            b.classList.add('active');
        }
    });
}

// Tag table helpers
function toggleAllTags() {
    const all = document.getElementById('select-all-tags');
    const isChecked = all?.checked || false;
    document.querySelectorAll('.tag-select').forEach(cb => {
        cb.checked = isChecked;
    });
    _updateCount();
}

function removeSelectedMqttTags() {
    // Delegate to the real async implementation wired by mqtt-cloud.js
    if (typeof window.removeSelectedTags === 'function') {
        window.removeSelectedTags();
        return;
    }
    // Fallback: DOM-only removal (used when cloud.js is not loaded)
    const sel = document.querySelectorAll('.tag-select:checked');
    if (!sel.length) { 
        alert('Select tags to remove.'); 
        return; 
    }
    if (confirm(`Remove ${sel.length} tag(s)?`)) {
        sel.forEach(cb => {
            const row = cb.closest('tr');
            if (row) row.remove();
        });
        _updateCount();
    }
}

// Channel management
function addPublishChannel() { 
    if (typeof window._addPublishChannel === 'function') {
        window._addPublishChannel(); 
    } else {
        console.warn('_addPublishChannel not available');
    }
}

function addSubscribeChannel() { 
    if (typeof window._addSubscribeChannel === 'function') {
        window._addSubscribeChannel(); 
    } else {
        console.warn('_addSubscribeChannel not available');
    }
}

function handleCertificateUpload(input, spanId) {
    const el = document.getElementById(spanId);
    if (el) el.textContent = input.files[0]?.name || 'No file selected';
}

function generatePassword(fieldId) {
    const el = document.getElementById(fieldId);
    if (el) {
        el.value = [...crypto.getRandomValues(new Uint8Array(12))].map(b =>
            'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*'[b % 72]).join('');
    }
}

// Generate client ID manually (can be called from UI if needed)
function generateClientId() {
    const el = document.getElementById('field-clientId');
    if (el) {
        el.value = 'univa-gateway-' + Math.random().toString(36).substring(2, 10);
    }
}

// Generate device token manually (can be called from UI if needed)
function generateDeviceToken() {
    const el = document.getElementById('field-deviceToken');
    if (el) {
        el.value = 'dev_' + Math.random().toString(36).substring(2, 10) + Math.random().toString(36).substring(2, 6);
    }
}

// showAddTagModal is overridden by mqtt-cloud.js after form injection
function showAddTagModal() { 
    if (typeof window._openTagsModal === 'function') {
        window._openTagsModal();
    } else {
        console.warn('showAddTagModal not yet wired');
    }
}

// Save stubs — overridden by mqtt-cloud.js _wireFormSaves()
function saveMqttConnectionSettings() { 
    if (typeof window.mqttFormLogic?.saveMqttConnectionSettings === 'function') {
        window.mqttFormLogic.saveMqttConnectionSettings();
    } else {
        console.log('save connection: not wired yet');
    }
}

function saveMqttTopicSettings() { 
    if (typeof window.mqttFormLogic?.saveMqttTopicSettings === 'function') {
        window.mqttFormLogic.saveMqttTopicSettings();
    } else {
        console.log('save channels: not wired yet'); 
    }
}

function saveMqttPublishingSettings() { 
    if (typeof window.mqttFormLogic?.saveMqttPublishingSettings === 'function') {
        window.mqttFormLogic.saveMqttPublishingSettings();
    } else {
        console.log('save mappings: not wired yet'); 
    }
}

function saveMqttAdvancedSettings() { 
    if (typeof window.mqttFormLogic?.saveMqttAdvancedSettings === 'function') {
        window.mqttFormLogic.saveMqttAdvancedSettings();
    } else {
        console.log('save advanced: not wired yet'); 
    }
}

// Export all functions to window.mqttFormLogic
window.mqttFormLogic = {
    initializeMqttForm,
    switchMqttTab,
    toggleAllTags,
    removeSelectedMqttTags,
    addPublishChannel,
    addSubscribeChannel,
    handleCertificateUpload,
    generatePassword,
    generateClientId,
    generateDeviceToken,
    showAddTagModal,
    saveMqttConnectionSettings,
    saveMqttTopicSettings,
    saveMqttPublishingSettings,
    saveMqttAdvancedSettings,
};

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on a page with MQTT form
    if (document.getElementById('field-clientId')) {
        window.initializeMqttForm();
    }
});