// ftp-form-logic.js — UI-only logic for ftp-form.html
// Save function is overridden by mqtt-cloud.js after form injection.
'use strict';

window.initializeFtpForm = function () {


    // Anonymous login toggle — hides username/password fields
    const anonToggle   = document.getElementById('field-anonymous');
    const credFields   = document.getElementById('ftp-credential-fields');
    if (anonToggle && credFields) {
        anonToggle.addEventListener('change', function () {
            credFields.style.display = this.checked ? 'none' : 'block';
        });
        credFields.style.display = anonToggle.checked ? 'none' : 'block';
    }

    // Protocol change — auto-update default port
    const protocolSel = document.getElementById('field-protocol');
    const portInput   = document.getElementById('field-port');
    if (protocolSel && portInput) {
        protocolSel.addEventListener('change', function () {
            const defaults = { ftp: '21', sftp: '22', ftps: '990' };
            const known = ['21', '22', '990'];
            if (known.includes(portInput.value)) {
                portInput.value = defaults[this.value] || '21';
            }
        });
    }

    // Transfer mode — hide for SFTP
    const modeSel = document.getElementById('field-mode');
    if (protocolSel && modeSel) {
        function _applyMode() {
            const row = modeSel.closest('div.space-y-4 > div') || modeSel.closest('div');
            if (row) row.style.display = protocolSel.value === 'sftp' ? 'none' : '';
        }
        protocolSel.addEventListener('change', _applyMode);
        _applyMode();
    }


};

function generateFtpPassword(fieldId) {
    const el = document.getElementById(fieldId);
    if (el) el.value = [...crypto.getRandomValues(new Uint8Array(12))].map(b =>
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*'[b % 72]).join('');
}

function saveFtpSettings() { }

window.ftpFormLogic = {
    initializeFtpForm,
    generateFtpPassword,
    saveFtpSettings,
};