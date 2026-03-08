// backup.js - System Backup & Recovery Page Script

if (typeof window.backupLoaded === 'undefined') {
    window.backupLoaded = true;

    // ========== STATIC DATA ==========
    var backupData = [
        { id: 1, name: 'DailyBackup_20250612',  type: 'Full System',  date: '2025-06-12 02:00', size: '220 MB',  checksum: 'a1b2c3d4', location: 'Local',    encrypted: true  },
        { id: 2, name: 'ConfigOnly_20250610',   type: 'Config Only',  date: '2025-06-10 14:13', size: '32 MB',   checksum: 'e5f6g7h8', location: 'Cloud S3', encrypted: true  },
        { id: 3, name: 'OTA_SafePoint',         type: 'Pre-OTA',      date: '2025-06-09 11:02', size: '1.2 GB',  checksum: 'i9j0k1l2', location: 'USB',      encrypted: false },
        { id: 4, name: 'ManualBackup_20250605', type: 'Full System',  date: '2025-06-05 16:30', size: '215 MB',  checksum: 'm3n4o5p6', location: 'Local',    encrypted: true  },
        { id: 5, name: 'PreUpdate_Snapshot',    type: 'Config Only',  date: '2025-06-01 09:00', size: '28 MB',   checksum: 'q7r8s9t0', location: 'Cloud S3', encrypted: false }
    ];

    var snapshots = [
        { id: 's1', name: 'Pre_ACS_Update',       date: '2025-06-12 11:05', description: 'Before ACS module update' },
        { id: 's2', name: 'Pre_FW_v2.4.1',        date: '2025-06-08 08:00', description: 'Before firmware 2.4.1'    },
        { id: 's3', name: 'Initial_Config_Backup', date: '2025-05-20 14:30', description: 'Initial production setup' }
    ];

    var filteredData = backupData.slice();

    // ========== HELPERS ==========
    function getTypeInfo(type) {
        var map = {
            'Full System': { icon: 'fa-server',       color: 'bg-blue-100 text-blue-600',   badge: 'bg-blue-100 text-blue-700 border border-blue-200'   },
            'Config Only': { icon: 'fa-gears',        color: 'bg-purple-100 text-purple-600', badge: 'bg-purple-100 text-purple-700 border border-purple-200' },
            'Pre-OTA':     { icon: 'fa-microchip',    color: 'bg-amber-100 text-amber-600',  badge: 'bg-amber-100 text-amber-700 border border-amber-200'  }
        };
        return map[type] || { icon: 'fa-file-zipper', color: 'bg-slate-100 text-slate-600', badge: 'bg-slate-100 text-slate-600' };
    }

    // ========== TOAST ==========
    function showToast(message, type) {
        type = type || 'info';
        if (typeof window.showNotification === 'function') { window.showNotification(message, type); return; }
        var container = document.getElementById('toast-container');
        if (!container) return;
        var icons  = { success: 'fa-circle-check', error: 'fa-circle-xmark', warning: 'fa-triangle-exclamation', info: 'fa-circle-info' };
        var colors = { success: 'bg-green-50 text-green-800 border-green-200', error: 'bg-red-50 text-red-800 border-red-200', warning: 'bg-amber-50 text-amber-800 border-amber-200', info: 'bg-blue-50 text-blue-800 border-blue-200' };
        var toast  = document.createElement('div');
        toast.className = 'px-4 py-3 rounded-md shadow-lg border transform transition-all duration-300 translate-x-64 opacity-0 ' + (colors[type] || colors.info);
        toast.innerHTML = '<div class="flex items-center gap-2"><i class="fa-solid ' + (icons[type]||icons.info) + '"></i><span class="text-sm font-medium">' + message + '</span><button class="ml-4 opacity-50 hover:opacity-100" onclick="this.closest(\'div\').parentElement.remove()"><i class="fa-solid fa-times"></i></button></div>';
        container.appendChild(toast);
        setTimeout(function() { toast.classList.replace('translate-x-64','translate-x-0'); toast.classList.replace('opacity-0','opacity-100'); }, 10);
        setTimeout(function() { toast.classList.replace('translate-x-0','translate-x-64'); toast.classList.replace('opacity-100','opacity-0'); setTimeout(function(){ toast.remove(); }, 300); }, 5000);
    }

    // ========== RENDER BACKUP TABLE ==========
    function renderBackupTable() {
        var tbody = document.getElementById('backup-table-body');
        if (!tbody) return;

        if (!filteredData.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-10 text-center text-slate-400"><i class="fa-solid fa-inbox text-3xl mb-2 block"></i>No backup files found</td></tr>';
            updateTableSummary(0);
            return;
        }

        tbody.innerHTML = filteredData.map(function(b) {
            var info = getTypeInfo(b.type);
            var encBadge = b.encrypted ? '<span class="ml-2 text-[10px] px-1.5 py-0.5 bg-green-50 text-green-700 rounded border border-green-200 font-medium"><i class="fa-solid fa-lock text-[8px] mr-0.5"></i>AES</span>' : '';
            var locIcon  = b.location === 'Cloud S3' ? 'fa-cloud' : b.location === 'USB' ? 'fa-usb' : 'fa-hard-drive';
            return '<tr class="hover:bg-slate-50 transition-colors group" data-id="' + b.id + '">' +
                '<td class="px-6 py-4">' +
                    '<div class="flex items-center gap-3">' +
                        '<div class="w-8 h-8 rounded ' + info.color + ' flex items-center justify-center text-xs flex-shrink-0"><i class="fa-solid ' + info.icon + '"></i></div>' +
                        '<div>' +
                            '<div class="font-medium text-slate-900">' + b.name + encBadge + '</div>' +
                            '<div class="text-xs text-slate-500 flex items-center gap-1 mt-0.5"><i class="fa-solid ' + locIcon + ' text-[10px]"></i>' + b.location + '</div>' +
                        '</div>' +
                    '</div>' +
                '</td>' +
                '<td class="px-6 py-4 text-slate-600">' + b.date + '</td>' +
                '<td class="px-6 py-4"><span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ' + info.badge + '">' + b.type + '</span></td>' +
                '<td class="px-6 py-4 text-slate-600 font-medium">' + b.size + '</td>' +
                '<td class="px-6 py-4 font-mono text-xs text-slate-500">' + b.checksum + '</td>' +
                '<td class="px-6 py-4 text-right">' +
                    '<div class="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">' +
                        '<button class="p-1.5 text-slate-500 hover:text-green-600 hover:bg-green-50 rounded transition-colors" onclick="window.restoreBackup(\'' + b.name + '\')" title="Restore"><i class="fa-solid fa-rotate-left text-xs"></i></button>' +
                        '<button class="p-1.5 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors" onclick="window.downloadBackup(\'' + b.name + '\')" title="Download"><i class="fa-solid fa-download text-xs"></i></button>' +
                        '<button class="p-1.5 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded transition-colors" onclick="window.deleteBackup(' + b.id + ')" title="Delete"><i class="fa-solid fa-trash text-xs"></i></button>' +
                    '</div>' +
                '</td>' +
            '</tr>';
        }).join('');

        updateTableSummary(filteredData.length);
    }

    function updateTableSummary(count) {
        var el = document.getElementById('table-summary');
        if (el) el.textContent = 'Showing ' + count + ' of ' + backupData.length + ' backup files';
    }

    // ========== SEARCH ==========
    function searchBackups(e) {
        var q = e.target.value.trim().toLowerCase();
        filteredData = q
            ? backupData.filter(function(b){ return b.name.toLowerCase().includes(q) || b.type.toLowerCase().includes(q) || b.location.toLowerCase().includes(q); })
            : backupData.slice();
        renderBackupTable();
    }

    // ========== SCHEDULE TOGGLE ==========
    function handleScheduleToggle() {
        var toggle = document.getElementById('schedule-toggle');
        var status = document.getElementById('schedule-status');
        if (toggle && status) {
            status.textContent = toggle.checked ? 'Enabled' : 'Disabled';
            status.className = 'text-xs font-medium ' + (toggle.checked ? 'text-green-600' : 'text-slate-400');
            showToast('Scheduled backup ' + (toggle.checked ? 'enabled' : 'disabled'), toggle.checked ? 'success' : 'info');
        }
    }

    // ========== ACCORDION ==========
    function toggleAccordion(sectionId) {
        var content = document.getElementById(sectionId + '-content');
        var icon    = document.getElementById('accordion-icon');
        if (!content) return;
        var isOpen  = content.classList.contains('show');
        content.classList.toggle('show', !isOpen);
        if (icon) icon.style.transform = isOpen ? 'rotate(0deg)' : 'rotate(180deg)';
    }
    window.toggleAccordion = toggleAccordion;

    // ========== WINDOW ACTIONS ==========
    window.restoreBackup = function(name) {
        if (confirm('Restore from "' + name + '"? Current configuration will be overwritten.')) {
            showToast('Restore initiated — simulated', 'info');
        }
    };

    window.downloadBackup = function(name) {
        showToast('Downloading ' + name + '...', 'info');
        setTimeout(function(){ showToast(name + ' downloaded', 'success'); }, 1500);
    };

    window.deleteBackup = function(id) {
        var b = backupData.find(function(x){ return x.id === id; });
        if (b && confirm('Delete backup "' + b.name + '"? This cannot be undone.')) {
            backupData = backupData.filter(function(x){ return x.id !== id; });
            filteredData = filteredData.filter(function(x){ return x.id !== id; });
            renderBackupTable();
            showToast('"' + b.name + '" deleted', 'success');
        }
    };

    window.saveSchedule    = function() { showToast('Schedule saved', 'success'); };
    window.clearFilters    = function() { filteredData = backupData.slice(); renderBackupTable(); showToast('Filters cleared', 'info'); };
    window.purgeOldBackups = function() {
        if (confirm('Auto-purge backups beyond retention limit?')) { showToast('Old backups purged', 'success'); }
    };
    window.generateReport  = function() { showToast('Usage report — coming soon', 'info'); };

    // Modal stubs (modals are in the HTML, we just show/hide them)
    window.showBackupModal = function() {
        var el = document.getElementById('create-backup-modal');
        if (el) { el.classList.remove('hidden'); el.classList.add('active'); }
        else showToast('Create Backup modal — coming soon', 'info');
    };

    // Wire data-action buttons
    function initializeButtons() {
        document.querySelectorAll('[data-action]').forEach(function(btn) {
            if (btn.dataset.actionBound) return;
            btn.dataset.actionBound = 'true';
            btn.addEventListener('click', function() {
                var raw  = this.dataset.action;
                var fn   = raw.replace(/\(.*\)$/, '');
                var args = (raw.match(/\((.*)\)/) || ['',''])[1];
                try {
                    if (args) { new Function('return window.' + fn + '(' + args + ')')(); }
                    else      { if (typeof window[fn] === 'function') window[fn](); }
                } catch(e) { console.warn('data-action error:', e); }
            });
        });

        // Wire modal-trigger buttons (data-modal attribute)
        document.querySelectorAll('.modal-trigger[data-modal]').forEach(function(btn) {
            if (btn.dataset.modalBound) return;
            btn.dataset.modalBound = 'true';
            btn.addEventListener('click', function() {
                var modalId = this.dataset.modal;
                var modal   = document.getElementById(modalId);
                if (modal) { modal.classList.remove('hidden'); document.body.style.overflow = 'hidden'; }
                else showToast('Modal not available yet', 'info');
            });
        });

        // Wire schedule toggle
        var schedToggle = document.getElementById('schedule-toggle');
        if (schedToggle) schedToggle.addEventListener('change', handleScheduleToggle);

        // Wire search
        var searchInput = document.getElementById('search-backups');
        if (searchInput) searchInput.addEventListener('input', searchBackups);

        // Wire accordion header click
        var accordionHeaders = document.querySelectorAll('.accordion-header[data-action]');
        accordionHeaders.forEach(function(h) {
            if (h.dataset.headerBound) return;
            h.dataset.headerBound = 'true';
            h.addEventListener('click', function() {
                var raw = this.dataset.action;
                var fn  = raw.replace(/\(.*\)$/, '');
                var args = (raw.match(/\((.*)\)/) || ['',''])[1];
                try {
                    if (args) { new Function('return window.' + fn + '(' + args + ')')(); }
                    else      { if (typeof window[fn] === 'function') window[fn](); }
                } catch(e) { console.warn('accordion action error:', e); }
            });
        });

        // Open accordion by default
        var accContent = document.getElementById('scheduled-backups-content');
        var accIcon    = document.getElementById('accordion-icon');
        if (accContent) { accContent.classList.add('show'); if (accIcon) accIcon.style.transform = 'rotate(180deg)'; }
    }

    // ========== CLEANUP ==========
    function cleanupBackup() {
        document.querySelectorAll('[data-action-bound],[data-modal-bound],[data-header-bound]').forEach(function(el) {
            el.removeAttribute('data-action-bound');
            el.removeAttribute('data-modal-bound');
            el.removeAttribute('data-header-bound');
        });
        filteredData = backupData.slice();
        console.log('Backup cleanup complete');
    }

    // ========== INIT ==========
    window.initBackup = function() {
        console.log('Initializing System Backup & Recovery');
        filteredData = backupData.slice();
        renderBackupTable();
        initializeButtons();
    };

    window.cleanupBackup = cleanupBackup;
    window.addEventListener('beforeunload', cleanupBackup);
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { initBackup: window.initBackup, cleanupBackup: window.cleanupBackup };
}