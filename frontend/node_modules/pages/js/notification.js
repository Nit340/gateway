// notification.js - Notification Channels Page Script

if (typeof window.notificationLoaded === 'undefined') {
    window.notificationLoaded = true;

    // ========== STATIC DATA ==========
    let channels = [
        {
            id: 'mqtt-primary',
            name: 'MQTT Alert Broker',
            type: 'mqtt',
            status: 'active',
            config: { brokerUrl: 'mqtt.factory.com:1883', topic: 'factory/alerts', username: 'univa_gateway', password: '••••••••' }
        },
        {
            id: 'email-primary',
            name: 'Corporate SMTP',
            type: 'email',
            status: 'active',
            config: { smtpServer: 'smtp.gmail.com', port: 587, username: 'alerts@factory.com', password: '••••••••', fromEmail: 'alerts@factory.com', toEmails: 'ops-team@factory.com, supervisor@factory.com' }
        },
        {
            id: 'sms-twilio',
            name: 'Twilio SMS',
            type: 'sms',
            status: 'inactive',
            config: { provider: 'Twilio', accountSid: 'AC•••••••••', fromNumber: '+1-555-0000', phoneNumbers: '+1-555-0100, +1-555-0200' }
        }
    ];

    // ========== HELPERS ==========
    function getChannelIcon(type) {
        var icons = { mqtt: 'fa-satellite-dish', email: 'fa-envelope', sms: 'fa-mobile-screen', webhook: 'fa-code-branch', push: 'fa-bell' };
        return icons[type] || 'fa-plug';
    }

    function getChannelColorClass(type) {
        var colors = { mqtt: 'bg-orange-100 text-orange-600', email: 'bg-blue-100 text-blue-600', sms: 'bg-green-100 text-green-600', webhook: 'bg-purple-100 text-purple-600', push: 'bg-pink-100 text-pink-600' };
        return colors[type] || 'bg-slate-100 text-slate-600';
    }

    function getConnectionInfo(channel) {
        switch (channel.type) {
            case 'mqtt':    return channel.config.brokerUrl + ' &bull; ' + channel.config.topic;
            case 'email':   return channel.config.smtpServer + ':' + channel.config.port + ' &rarr; ' + channel.config.toEmails;
            case 'sms':     return channel.config.phoneNumbers || 'Not configured';
            default:        return channel.config.server || 'Not configured';
        }
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
        toast.innerHTML = '<div class="flex items-center gap-2"><i class="fa-solid ' + (icons[type] || icons.info) + '"></i><span class="text-sm font-medium">' + message + '</span><button class="ml-4 opacity-50 hover:opacity-100" onclick="this.closest(\'div\').parentElement.remove()"><i class="fa-solid fa-times"></i></button></div>';
        container.appendChild(toast);
        setTimeout(function() { toast.classList.replace('translate-x-64','translate-x-0'); toast.classList.replace('opacity-0','opacity-100'); }, 10);
        setTimeout(function() { toast.classList.replace('translate-x-0','translate-x-64'); toast.classList.replace('opacity-100','opacity-0'); setTimeout(function(){ toast.remove(); }, 300); }, 5000);
    }

    // ========== RENDER CHANNELS LIST ==========
    function renderChannelsList() {
        var container = document.getElementById('channels-list');
        if (!container) return;

        if (!channels.length) {
            container.innerHTML = '<tr><td colspan="5" class="px-6 py-8 text-center text-slate-400"><i class="fa-solid fa-inbox text-2xl mb-2 block"></i>No channels configured</td></tr>';
            return;
        }

        container.innerHTML = channels.map(function(ch) {
            var statusBadge = ch.status === 'active'
                ? '<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-700 border border-green-100"><span class="w-1.5 h-1.5 rounded-full bg-green-500"></span>Active</span>'
                : '<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200"><span class="w-1.5 h-1.5 rounded-full bg-slate-400"></span>Inactive</span>';
            return '<tr class="hover:bg-slate-50 transition-colors">' +
                '<td class="px-6 py-4">' +
                    '<div class="flex items-center gap-3">' +
                        '<div class="w-8 h-8 rounded-lg ' + getChannelColorClass(ch.type) + ' flex items-center justify-center"><i class="fa-solid ' + getChannelIcon(ch.type) + ' text-sm"></i></div>' +
                        '<div><div class="font-medium text-slate-900">' + ch.name + '</div><div class="text-xs text-slate-500">' + ch.type.toUpperCase() + '</div></div>' +
                    '</div>' +
                '</td>' +
                '<td class="px-6 py-4 text-slate-600 text-sm">' + ch.type.toUpperCase() + '</td>' +
                '<td class="px-6 py-4">' + statusBadge + '</td>' +
                '<td class="px-6 py-4 text-slate-600 text-sm">' + getConnectionInfo(ch) + '</td>' +
                '<td class="px-6 py-4 text-right">' +
                    '<button class="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors mr-1" onclick="window.editChannel(\'' + ch.id + '\')" title="Edit"><i class="fa-solid fa-pen text-xs"></i></button>' +
                    '<button class="p-1.5 text-slate-400 ' + (ch.status === 'active' ? 'hover:text-red-600 hover:bg-red-50' : 'hover:text-green-600 hover:bg-green-50') + ' rounded transition-colors" onclick="window.toggleChannelStatus(\'' + ch.id + '\')" title="' + (ch.status === 'active' ? 'Disable' : 'Enable') + '"><i class="fa-solid ' + (ch.status === 'active' ? 'fa-power-off' : 'fa-play') + ' text-xs"></i></button>' +
                '</td>' +
            '</tr>';
        }).join('');

        updateOnlineCount();
    }

    function updateOnlineCount() {
        var el = document.getElementById('online-count');
        if (el) el.textContent = channels.filter(function(c){ return c.status === 'active'; }).length;
    }

    // ========== WINDOW ACTIONS ==========
    window.editChannel = function(id) {
        var ch = channels.find(function(c){ return c.id === id; });
        if (ch) showToast('Edit "' + ch.name + '" — coming soon', 'info');
    };

    window.toggleChannelStatus = function(id) {
        var ch = channels.find(function(c){ return c.id === id; });
        if (ch) {
            ch.status = ch.status === 'active' ? 'inactive' : 'active';
            renderChannelsList();
            showToast(ch.name + ' ' + (ch.status === 'active' ? 'enabled' : 'disabled'), 'info');
        }
    };

    window.showAddChannelModal = function() { showToast('Add Channel — coming soon', 'info'); };

    window.testChannel = function(type) {
        showToast('Sending test via ' + type + '...', 'info');
        setTimeout(function() { showToast('Test ' + type + ' sent successfully!', 'success'); }, 1500);
    };

    window.testAllChannels = function() {
        showToast('Testing all channels...', 'info');
        setTimeout(function() { showToast('All channel tests complete!', 'success'); }, 2000);
    };

    // Wire data-action buttons
    function initializeButtons() {
        document.querySelectorAll('[data-action]').forEach(function(btn) {
            if (btn.dataset.actionBound) return;
            btn.dataset.actionBound = 'true';
            btn.addEventListener('click', function() {
                var raw = this.dataset.action;
                var fn  = raw.replace(/\(.*\)$/, '');
                var args = (raw.match(/\((.*)\)/) || ['',''])[1];
                try {
                    if (args) { new Function('return window.' + fn + '(' + args + ')')(); }
                    else      { if (typeof window[fn] === 'function') window[fn](); }
                } catch(e) { console.warn('data-action error:', e); }
            });
        });
    }

    // ========== CLEANUP ==========
    function cleanupNotification() {
        document.querySelectorAll('[data-action-bound]').forEach(function(btn) {
            btn.removeAttribute('data-action-bound');
        });
        console.log('Notification cleanup complete');
    }

    // ========== INIT ==========
    window.initNotification = function() {
        console.log('Initializing Notification Channels');
        renderChannelsList();
        initializeButtons();
    };

    window.cleanupNotification = cleanupNotification;
    window.addEventListener('beforeunload', cleanupNotification);
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { initNotification: window.initNotification, cleanupNotification: window.cleanupNotification };
}