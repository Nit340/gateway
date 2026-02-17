// alerts.js - Alert Messages & Event Classes Page Script

if (typeof window.alertsLoaded === 'undefined') {
    window.alertsLoaded = true;

    // ========== STATIC DATA ==========
    let alertClasses = [
        { id: 1, name: 'Critical', severity: 5, color: '#DC2626', icon: 'fa-triangle-exclamation', description: 'Immediate action required' },
        { id: 2, name: 'High',     severity: 4, color: '#F97316', icon: 'fa-circle-exclamation',   description: 'Attention required soon' },
        { id: 3, name: 'Warning',  severity: 3, color: '#F59E0B', icon: 'fa-exclamation',          description: 'Monitor situation closely' },
        { id: 4, name: 'Info',     severity: 2, color: '#3B82F6', icon: 'fa-circle-info',          description: 'Informational message' },
        { id: 5, name: 'Low',      severity: 1, color: '#10B981', icon: 'fa-circle-check',         description: 'Normal operation information' }
    ];

    let alertMessages = [
        { id: 1, name: 'Critical Temperature', message: '🔥 CRITICAL: {device} temperature is {value}°C (Threshold: {threshold}°C)', classId: 1, channels: ['mqtt', 'email', 'sms', 'dashboard'] },
        { id: 2, name: 'Device Offline',        message: '📴 {device} is offline at {timestamp}',                                    classId: 2, channels: ['email', 'dashboard'] },
        { id: 3, name: 'High Vibration',        message: '⚠️ WARNING: {device} vibration is {value} mm/s',                          classId: 3, channels: ['mqtt', 'email', 'dashboard'] },
        { id: 4, name: 'Low Battery',           message: '🔋 {device} battery is at {value}%',                                       classId: 4, channels: ['dashboard'] },
        { id: 5, name: 'System Startup',        message: '✅ {device} started successfully at {timestamp}',                          classId: 5, channels: ['dashboard'] }
    ];

    const severityBg    = { 5: '#DC2626', 4: '#F97316', 3: '#F59E0B', 2: '#3B82F6', 1: '#10B981' };
    const severityColor = { 5: 'white',   4: 'white',   3: '#1E293B', 2: 'white',   1: 'white'   };

    const channelColors = {
        mqtt:      'bg-orange-100 text-orange-700',
        email:     'bg-blue-100  text-blue-700',
        sms:       'bg-green-100 text-green-700',
        dashboard: 'bg-slate-100 text-slate-700',
        push:      'bg-pink-100  text-pink-700',
        webhook:   'bg-purple-100 text-purple-700'
    };

    // ========== TOAST ==========
    function showToast(message, type) {
        type = type || 'info';
        if (typeof window.showNotification === 'function') { window.showNotification(message, type); return; }
        var container = document.getElementById('toast-container');
        if (!container) return;
        var icons   = { success: 'fa-circle-check', error: 'fa-circle-xmark', warning: 'fa-triangle-exclamation', info: 'fa-circle-info' };
        var colors  = { success: 'bg-green-50 text-green-800 border-green-200', error: 'bg-red-50 text-red-800 border-red-200', warning: 'bg-amber-50 text-amber-800 border-amber-200', info: 'bg-blue-50 text-blue-800 border-blue-200' };
        var toast   = document.createElement('div');
        toast.className = 'px-4 py-3 rounded-md shadow-lg border transform transition-all duration-300 translate-x-64 opacity-0 ' + (colors[type] || colors.info);
        toast.innerHTML = '<div class="flex items-center gap-2"><i class="fa-solid ' + (icons[type] || icons.info) + '"></i><span class="text-sm font-medium">' + message + '</span><button class="ml-4 opacity-50 hover:opacity-100" onclick="this.closest(\'div\').parentElement.remove()"><i class="fa-solid fa-times"></i></button></div>';
        container.appendChild(toast);
        setTimeout(function() { toast.classList.replace('translate-x-64','translate-x-0'); toast.classList.replace('opacity-0','opacity-100'); }, 10);
        setTimeout(function() { toast.classList.replace('translate-x-0','translate-x-64'); toast.classList.replace('opacity-100','opacity-0'); setTimeout(function(){ toast.remove(); }, 300); }, 5000);
    }

    // ========== RENDER ALERT CLASSES ==========
    function renderAlertClassesTable() {
        var tbody = document.getElementById('alert-classes-table');
        if (!tbody) return;
        tbody.innerHTML = alertClasses.map(function(cls) {
            return '<tr class="hover:bg-slate-50 transition-colors">' +
                '<td class="px-4 py-3 font-medium text-slate-900">' + cls.name +
                    '<div class="text-xs text-slate-500">' + cls.description + '</div></td>' +
                '<td class="px-4 py-3">' +
                    '<span class="inline-flex items-center justify-center w-8 h-8 rounded-full text-xs font-bold" style="background-color:' + severityBg[cls.severity] + ';color:' + severityColor[cls.severity] + '">' + cls.severity + '</span>' +
                '</td>' +
                '<td class="px-4 py-3"><div class="flex items-center gap-2"><div class="w-4 h-4 rounded" style="background-color:' + cls.color + '"></div><span class="text-xs text-slate-600">' + cls.color + '</span></div></td>' +
                '<td class="px-4 py-3"><i class="fa-solid ' + cls.icon + '" style="color:' + cls.color + '"></i></td>' +
                '<td class="px-4 py-3 text-xs text-slate-600">' + cls.description + '</td>' +
                '<td class="px-4 py-3"><div class="flex items-center gap-2">' +
                    '<button class="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors" onclick="window.editAlertClass(' + cls.id + ')" title="Edit"><i class="fa-solid fa-pen text-xs"></i></button>' +
                    '<button class="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors' + (cls.id <= 5 ? ' opacity-40 cursor-not-allowed' : '') + '" ' + (cls.id <= 5 ? 'disabled' : 'onclick="window.deleteAlertClass(' + cls.id + ')"') + ' title="Delete"><i class="fa-solid fa-trash text-xs"></i></button>' +
                '</div></td></tr>';
        }).join('');
    }

    // ========== RENDER ALERT MESSAGES ==========
    function renderAlertMessagesTable() {
        var tbody = document.getElementById('alert-messages-table');
        if (!tbody) return;
        tbody.innerHTML = alertMessages.map(function(msg) {
            var cls = alertClasses.find(function(c) { return c.id === msg.classId; });
            var clsBadge = cls
                ? '<span class="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium" style="background-color:' + cls.color + '20;color:' + cls.color + ';border:1px solid ' + cls.color + '40"><i class="fa-solid ' + cls.icon + ' text-[10px]"></i>' + cls.name + '</span>'
                : '<span class="text-slate-400 text-xs">Unknown</span>';
            var channelBadges = msg.channels.map(function(ch) {
                return '<span class="px-2 py-0.5 rounded text-xs font-medium ' + (channelColors[ch] || 'bg-slate-100 text-slate-600') + '">' + ch + '</span>';
            }).join('');
            return '<tr class="hover:bg-slate-50 transition-colors">' +
                '<td class="px-4 py-3 font-medium text-slate-900">' + msg.name + '</td>' +
                '<td class="px-4 py-3 text-sm text-slate-600 font-mono max-w-xs" title="' + msg.message + '" style="max-width:220px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + msg.message + '</td>' +
                '<td class="px-4 py-3">' + clsBadge + '</td>' +
                '<td class="px-4 py-3"><div class="flex flex-wrap gap-1">' + channelBadges + '</div></td>' +
                '<td class="px-4 py-3"><div class="flex items-center gap-2">' +
                    '<button class="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors" onclick="window.editAlertMessage(' + msg.id + ')" title="Edit"><i class="fa-solid fa-pen text-xs"></i></button>' +
                    '<button class="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors" onclick="window.deleteAlertMessage(' + msg.id + ')" title="Delete"><i class="fa-solid fa-trash text-xs"></i></button>' +
                '</div></td></tr>';
        }).join('');
    }

    // ========== WINDOW ACTIONS ==========
    window.editAlertClass = function(id) {
        var cls = alertClasses.find(function(c){ return c.id === id; });
        if (cls) showToast('Edit "' + cls.name + '" class — coming soon', 'info');
    };

    window.deleteAlertClass = function(id) {
        var cls = alertClasses.find(function(c){ return c.id === id; });
        if (cls && confirm('Delete class "' + cls.name + '"?')) {
            alertClasses = alertClasses.filter(function(c){ return c.id !== id; });
            renderAlertClassesTable();
            showToast('"' + cls.name + '" deleted', 'success');
        }
    };

    window.editAlertMessage = function(id) {
        var msg = alertMessages.find(function(m){ return m.id === id; });
        if (msg) showToast('Edit "' + msg.name + '" — coming soon', 'info');
    };

    window.deleteAlertMessage = function(id) {
        var msg = alertMessages.find(function(m){ return m.id === id; });
        if (msg && confirm('Delete "' + msg.name + '"?')) {
            alertMessages = alertMessages.filter(function(m){ return m.id !== id; });
            renderAlertMessagesTable();
            showToast('"' + msg.name + '" deleted', 'success');
        }
    };

    window.showAddAlertClassModal   = function() { showToast('Add Alert Class — coming soon', 'info'); };
    window.showAddAlertMessageModal = function() { showToast('Add Alert Message — coming soon', 'info'); };

    window.exportConfiguration = function() {
        var config = { alertClasses: alertClasses, alertMessages: alertMessages, timestamp: new Date().toISOString() };
        var a = document.createElement('a');
        a.href = 'data:application/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(config, null, 2));
        a.download = 'alert-config-' + new Date().toISOString().split('T')[0] + '.json';
        a.click();
        showToast('Configuration exported', 'success');
    };

    window.showLivePreview = function() {
        if (!alertMessages.length) { showToast('No alert messages to preview', 'warning'); return; }
        showToast('Live Preview — coming soon', 'info');
    };

    // Wire data-action buttons
    function initializeButtons() {
        document.querySelectorAll('[data-action]').forEach(function(btn) {
            if (btn.dataset.actionBound) return;
            btn.dataset.actionBound = 'true';
            btn.addEventListener('click', function() {
                var fn = this.dataset.action.replace(/\(.*\)$/, '');
                var args = (this.dataset.action.match(/\((.*)\)/) || ['',''])[1];
                try {
                    if (args) { new Function('return window.' + fn + '(' + args + ')')(); }
                    else      { if (typeof window[fn] === 'function') window[fn](); }
                } catch(e) { console.warn('data-action error:', e); }
            });
        });
    }

    // ========== CLEANUP ==========
    function cleanupAlerts() {
        document.querySelectorAll('[data-action-bound]').forEach(function(btn) {
            btn.removeAttribute('data-action-bound');
        });
        console.log('Alerts cleanup complete');
    }

    // ========== INIT ==========
    window.initAlerts = function() {
        console.log('Initializing Alert Messages & Event Classes');
        renderAlertClassesTable();
        renderAlertMessagesTable();
        initializeButtons();
    };

    window.cleanupAlerts = cleanupAlerts;
    window.addEventListener('beforeunload', cleanupAlerts);
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { initAlerts: window.initAlerts, cleanupAlerts: window.cleanupAlerts };
}