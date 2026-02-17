// http-form-logic.js — UI-only logic for http-form.html
// Save functions are overridden by mqtt-cloud.js after form injection.
'use strict';

window.initializeHttpForm = function () {
    // Auth type show/hide
    const authSel      = document.getElementById('field-authType');
    const basicFields  = document.getElementById('basic-auth-fields');
    const tokenFields  = document.getElementById('token-auth-fields');
    const oauth2Fields = document.getElementById('oauth2-fields');

    function _applyAuth(val) {
        if (basicFields)  basicFields.style.display  = val === 'basic'                    ? 'block' : 'none';
        if (tokenFields)  tokenFields.style.display  = (val === 'bearer' || val === 'apiKey') ? 'block' : 'none';
        if (oauth2Fields) oauth2Fields.style.display = val === 'oauth2'                   ? 'block' : 'none';
    }

    if (authSel) {
        authSel.addEventListener('change', function () { _applyAuth(this.value); });
        _applyAuth(authSel.value);
    }

    // Payload format show/hide
    const jsonOpts   = document.getElementById('json-format-options');
    const xmlOpts    = document.getElementById('xml-format-options');
    const customOpts = document.getElementById('custom-format-options');

    function _applyFormat(val) {
        if (jsonOpts)   jsonOpts.style.display   = val === 'json'   ? 'block' : 'none';
        if (xmlOpts)    xmlOpts.style.display    = val === 'xml'    ? 'block' : 'none';
        if (customOpts) customOpts.style.display = val === 'custom' ? 'block' : 'none';
    }

    document.querySelectorAll('input[name="field-payloadFormat"]').forEach(r => {
        r.addEventListener('change', function () { _applyFormat(this.value); });
    });
    const checked = document.querySelector('input[name="field-payloadFormat"]:checked');
    if (checked) _applyFormat(checked.value);

    // Publish mode show/hide
    const batchSettings       = document.getElementById('batch-settings');
    const conditionalSettings = document.getElementById('conditional-settings');

    document.querySelectorAll('input[name="field-publishMode"]').forEach(r => {
        r.addEventListener('change', function () {
            if (batchSettings)       batchSettings.style.display       = this.value === 'batch'       ? 'block' : 'none';
            if (conditionalSettings) conditionalSettings.style.display = this.value === 'conditional' ? 'block' : 'none';
        });
    });

    // Store & forward toggle
    const sfToggle  = document.getElementById('field-storeForward');
    const sfOptions = document.getElementById('store-forward-options');
    if (sfToggle && sfOptions) {
        sfToggle.addEventListener('change', function () { sfOptions.style.display = this.checked ? 'block' : 'none'; });
        sfOptions.style.display = sfToggle.checked ? 'block' : 'none';
    }

    _updateHttpTagCount();
};

// Tab switching
function switchHttpTab(name) {
    document.querySelectorAll('.http-tab-content').forEach(t => t.style.display = 'none');
    document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
    const content = document.getElementById(`http-${name}-content`);
    if (content) content.style.display = 'block';
    document.querySelectorAll('.tab-button').forEach(b => {
        if (b.getAttribute('onclick')?.includes(`'${name}'`)) b.classList.add('active');
    });
}

function toggleAllHttpTags() {
    const all = document.getElementById('http-select-all-tags');
    document.querySelectorAll('.http-tag-select').forEach(cb => cb.checked = all?.checked);
    _updateHttpTagCount();
}

function _updateHttpTagCount() {
    const n  = document.querySelectorAll('.http-tag-select:checked').length;
    const el = document.getElementById('http-selected-tags-count');
    if (el) el.textContent = n;
}

function removeSelectedHttpTags() {
    const sel = document.querySelectorAll('.http-tag-select:checked');
    if (!sel.length) { alert('Select tags to remove.'); return; }
    if (confirm(`Remove ${sel.length} tag(s)?`)) {
        sel.forEach(cb => cb.closest('tr')?.remove());
        _updateHttpTagCount();
    }
}

function addKeyValueItemHttp(btn) {
    const list = btn.closest('.key-value-list');
    const div  = document.createElement('div');
    div.className = 'key-value-item';
    div.innerHTML = `
      <input type="text" placeholder="Header Name"  class="compact-input">
      <input type="text" placeholder="Header Value" class="compact-input">
      <button type="button" class="text-red-600 hover:text-red-700" onclick="window.httpFormLogic.removeKeyValueItem(this)">
        <i class="fa-solid fa-trash"></i>
      </button>`;
    const addRow = list?.querySelector('.p-2.text-center');
    if (addRow) list.insertBefore(div, addRow);
}

function removeKeyValueItem(btn) { btn.closest('.key-value-item')?.remove(); }

function generateHttpPassword(fieldId) {
    const el = document.getElementById(fieldId);
    if (el) el.value = [...crypto.getRandomValues(new Uint8Array(12))].map(b =>
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*'[b % 72]).join('');
}

// showAddTagModal overridden by mqtt-cloud.js after form injection
function showAddTagModal() { console.warn('showAddTagModal not yet wired'); }

// Save stubs — overridden by mqtt-cloud.js _wireFormSaves()
function saveHttpConnectionSettings() { console.log('save connection: not wired yet'); }
function saveHttpPayloadSettings()    { console.log('save payload: not wired yet'); }
function saveHttpPublishingSettings() { console.log('save publishing: not wired yet'); }
function saveHttpAdvancedSettings()   { console.log('save advanced: not wired yet'); }

window.httpFormLogic = {
    initializeHttpForm,
    switchHttpTab,
    toggleAllHttpTags,
    removeSelectedHttpTags,
    addKeyValueItemHttp,
    removeKeyValueItem,
    generateHttpPassword,
    showAddTagModal,
    saveHttpConnectionSettings,
    saveHttpPayloadSettings,
    saveHttpPublishingSettings,
    saveHttpAdvancedSettings,
};

document.addEventListener('DOMContentLoaded', function () {
    document.addEventListener('click', function (e) {
        if (e.target.classList.contains('http-tag-select')) _updateHttpTagCount();
    });
});