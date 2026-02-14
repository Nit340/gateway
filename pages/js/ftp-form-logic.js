// ftp-form-logic.js — UI-only logic for ftp-form.html
// Save function is overridden by mqtt-cloud.js after form injection.
'use strict';

window.initializeFtpForm = function () {
    console.log('Initializing FTP form');

    // Anonymous login toggle — hides username/password fields
    const anonToggle   = document.getElementById('field-anonymous');
    const credFields   = document.getElementById('ftp-credential-fields');
    if (anonToggle && credFields) {
        anonToggle.addEventListener('change', function () {
            credFields.style.display = this.checked ? 'none' : 'block';
        });
        // Apply initial state
        credFields.style.display = anonToggle.checked ? 'none' : 'block';
    }

    // Protocol change — auto-update default port
    const protocolSel = document.getElementById('field-protocol');
    const portInput   = document.getElementById('field-port');
    if (protocolSel && portInput) {
        protocolSel.addEventListener('change', function () {
            const defaults = { ftp: '21', sftp: '22', ftps: '990' };
            // Only auto-update if user hasn't customised it beyond the known defaults
            const known = ['21', '22', '990'];
            if (known.includes(portInput.value)) {
                portInput.value = defaults[this.value] || '21';
            }
        });
    }

    // Transfer mode — hide for SFTP (SFTP has no active/passive)
    const modeSel = document.getElementById('field-mode');
    if (protocolSel && modeSel) {
        function _applyMode() {
            const row = modeSel.closest('div.space-y-4 > div') || modeSel.closest('div');
            if (row) row.style.display = protocolSel.value === 'sftp' ? 'none' : '';
        }
        protocolSel.addEventListener('change', _applyMode);
        _applyMode();
    }

    // Tag checkbox select-all listener
    document.addEventListener('click', function (e) {
        if (e.target.classList.contains('ftp-tag-select')) _updateFtpTagCount();
    });

    _updateFtpTagCount();
    console.log('FTP form initialized successfully');
};

function _updateFtpTagCount() {
    const total = document.querySelectorAll('#ftp-tags-table tr[data-tag-name]').length;
    const el    = document.getElementById('ftp-tag-count');
    if (el) el.textContent = total;
}

function removeFtpTags() {
    const sel = document.querySelectorAll('.ftp-tag-select:checked');
    if (!sel.length) { alert('Select tags to remove.'); return; }
    if (confirm(`Remove ${sel.length} tag(s)?`)) {
        sel.forEach(cb => cb.closest('tr')?.remove());
        _updateFtpTagCount();
    }
}

function generateFtpPassword(fieldId) {
    const el = document.getElementById(fieldId);
    if (el) el.value = [...crypto.getRandomValues(new Uint8Array(12))].map(b =>
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*'[b % 72]).join('');
}

// showAddTagModal and saveFtpSettings are overridden by mqtt-cloud.js after injection
function showAddTagModal()  { console.warn('showAddTagModal not yet wired'); }
function saveFtpSettings()  { console.log('saveFtpSettings: not wired yet'); }

window.ftpFormLogic = {
    initializeFtpForm,
    removeFtpTags,
    generateFtpPassword,
    showAddTagModal,
    saveFtpSettings,
};