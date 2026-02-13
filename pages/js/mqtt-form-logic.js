// mqtt-form-logic.js  — UI-only logic for mqtt-form.html
// Save functions are overridden by mqtt-cloud.js after form injection.
'use strict';
let mqttTopics = [];

window.initializeMqttForm = function () {
    mqttTopics = [];
    // Auto-generate client ID if empty
    const cid = document.getElementById('field-clientId');
    if (cid && !cid.value) {
        cid.value = 'univa-gateway-' + Math.random().toString(36).substring(2, 8);
    }
    // LWT toggle
    const lwtToggle = document.getElementById('field-advanced-enable-lwt');
    const lwtOpts   = document.getElementById('advanced-lwt-options');
    if (lwtToggle && lwtOpts) {
        lwtToggle.addEventListener('change', function () { lwtOpts.style.display = this.checked ? 'block' : 'none'; });
        lwtOpts.style.display = lwtToggle.checked ? 'block' : 'none';
    }
    // Compression toggle
    const compToggle = document.getElementById('field-advanced-enable-compression');
    const compOpts   = document.getElementById('compression-options');
    if (compToggle && compOpts) {
        compToggle.addEventListener('change', function () { compOpts.style.display = this.checked ? 'block' : 'none'; });
        compOpts.style.display = compToggle.checked ? 'block' : 'none';
    }
    _initTopics();
    _setupTagCheckboxListeners();
};

function _initTopics() {
    _updateTopicList();
    _updateTopicDropdowns();
}

function _updateTopicList() {
    const base = document.getElementById('field-baseTopic')?.value || '';
    mqttTopics = base ? [{ fullTopic: base }] : [];
    document.querySelectorAll('#custom-topics-container input[type="text"]').forEach(inp => {
        if (inp.value) mqttTopics.push({ fullTopic: base ? `${base}/${inp.value}` : inp.value });
    });
    _updateTopicDropdowns();
}

function _updateTopicDropdowns() {
    const opts = mqttTopics.map(t => `<option value="${t.fullTopic}">${t.fullTopic}</option>`).join('') ||
        '<option value="">No topics defined</option>';
    document.querySelectorAll('#mqtt-tags-table select.topic-select').forEach(s => s.innerHTML = opts);
}

function _setupTagCheckboxListeners() {
    document.addEventListener('click', function (e) {
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
    document.querySelectorAll('.mqtt-tab-content').forEach(t => t.style.display = 'none');
    document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
    const content = document.getElementById(`mqtt-${name}-content`);
    if (content) content.style.display = 'block';
    // Activate matching button
    document.querySelectorAll('.tab-button').forEach(b => {
        if (b.textContent.trim().toLowerCase().startsWith(name.charAt(0).toUpperCase() + name.slice(1).toLowerCase().charAt(0))) {
            b.classList.add('active');
        }
    });
    if (name === 'topics') _updateTopicList();
}

// Tag table helpers
function toggleAllTags() {
    const all = document.getElementById('select-all-tags');
    document.querySelectorAll('.tag-select').forEach(cb => cb.checked = all?.checked);
    _updateCount();
}

function removeSelectedMqttTags() {
    const sel = document.querySelectorAll('.tag-select:checked');
    if (!sel.length) { alert('Select tags to remove.'); return; }
    if (confirm(`Remove ${sel.length} tag(s)?`)) {
        sel.forEach(cb => cb.closest('tr')?.remove());
        _updateCount();
    }
}

function addNewCustomTopic() {
    const container = document.getElementById('custom-topics-container');
    if (!container) return;
    const div = document.createElement('div');
    div.className = 'custom-topic-item';
    div.innerHTML = `<div class="flex items-center gap-2">
      <input type="text" class="w-full compact-input" placeholder="topic-name" onchange="window.mqttFormLogic.updateAllTopicOptions()">
      <button type="button" class="compact-button border border-red-300 text-red-700 hover:bg-red-50" onclick="window.mqttFormLogic.removeCustomTopic(this)">
        <i class="fa-solid fa-trash"></i>
      </button>
    </div>`;
    container.appendChild(div);
    _updateTopicList();
}

function removeCustomTopic(btn) {
    btn.closest('.custom-topic-item')?.remove();
    _updateTopicList();
}

function handleCertificateUpload(input, spanId) {
    const el = document.getElementById(spanId);
    if (el) el.textContent = input.files[0]?.name || 'No file selected';
}

function generatePassword(fieldId) {
    const el = document.getElementById(fieldId);
    if (el) el.value = [...crypto.getRandomValues(new Uint8Array(12))].map(b =>
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*'[b % 72]).join('');
}

// showAddTagModal is overridden by mqtt-cloud.js after form injection
function showAddTagModal() { console.warn('showAddTagModal not yet wired'); }

// Save stubs — overridden by mqtt-cloud.js _wireFormSaves()
function saveMqttConnectionSettings() { console.log('save connection: not wired yet'); }
function saveMqttTopicSettings()      { console.log('save topics: not wired yet'); }
function saveMqttPublishingSettings() { console.log('save publishing: not wired yet'); }
function saveMqttAdvancedSettings()   { console.log('save advanced: not wired yet'); }

window.mqttFormLogic = {
    initializeMqttForm,
    switchMqttTab,
    toggleAllTags,
    removeSelectedMqttTags,
    addNewCustomTopic,
    removeCustomTopic,
    updateAllTopicOptions: _updateTopicList,
    handleCertificateUpload,
    generatePassword,
    showAddTagModal,
    saveMqttConnectionSettings,
    saveMqttTopicSettings,
    saveMqttPublishingSettings,
    
    saveMqttAdvancedSettings,
};