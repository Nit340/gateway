// rules.js - Rules Engine Page Script

if (typeof window.rulesLoaded === 'undefined') {
    window.rulesLoaded = true;

    // ========== STATIC DATA ==========
    let rules = [
        {
            id: 'rule_001', name: 'High Load Warning', enabled: true, priority: 'high',
            description: 'Trigger warning when crane load exceeds 90% of capacity',
            trigger: { device: 'Load Cell LC-001', parameter: 'current_load', operator: '>', value: '22500', unit: 'kg' },
            alertMessage: 'High Load Warning', alertClass: 'Warning',
            triggerCount: 45, lastTriggered: '2025-06-12T10:30:00Z', created: '2025-01-15T08:00:00Z'
        },
        {
            id: 'rule_002', name: 'Emergency Stop Alert', enabled: true, priority: 'critical',
            description: 'Immediate alert when emergency stop is activated',
            trigger: { device: 'Emergency Stop ESM-001', parameter: 'e_stop_status', operator: '==', value: 'true', unit: 'boolean' },
            alertMessage: 'Critical Temperature', alertClass: 'Critical',
            triggerCount: 3, lastTriggered: '2025-06-10T14:22:00Z', created: '2025-01-15T08:00:00Z'
        },
        {
            id: 'rule_003', name: 'Device Offline Detection', enabled: true, priority: 'medium',
            description: 'Alert when a critical device goes offline',
            trigger: { device: 'Any Modbus Device', parameter: 'connection_status', operator: '==', value: 'offline', unit: 'status' },
            alertMessage: 'Device Offline', alertClass: 'High',
            triggerCount: 12, lastTriggered: '2025-06-11T18:45:00Z', created: '2025-01-20T09:00:00Z'
        },
        {
            id: 'rule_004', name: 'High Temperature Warning', enabled: true, priority: 'medium',
            description: 'Warn when motor temperature exceeds safe threshold',
            trigger: { device: 'Hoist Motor HM-001', parameter: 'motor_temperature', operator: '>', value: '75', unit: '°C' },
            alertMessage: 'High Vibration', alertClass: 'Warning',
            triggerCount: 28, lastTriggered: '2025-06-12T09:15:00Z', created: '2025-02-01T10:00:00Z'
        },
        {
            id: 'rule_005', name: 'Wind Speed Safety', enabled: false, priority: 'high',
            description: 'Stop crane operations when wind speed exceeds safety limits',
            trigger: { device: 'Weather Station WS-001', parameter: 'wind_speed', operator: '>', value: '50', unit: 'km/h' },
            alertMessage: 'Critical Temperature', alertClass: 'Critical',
            triggerCount: 0, lastTriggered: null, created: '2025-03-01T11:00:00Z'
        }
    ];

    var selectedRuleId = null;

    // ========== HELPERS ==========
    var priorityColors = {
        critical: 'bg-red-100 text-red-700 border border-red-200',
        high:     'bg-orange-100 text-orange-700 border border-orange-200',
        medium:   'bg-yellow-100 text-yellow-700 border border-yellow-200',
        low:      'bg-slate-100 text-slate-600 border border-slate-200'
    };

    function formatDate(iso) {
        if (!iso) return 'Never';
        var d = new Date(iso);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
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

    // ========== RENDER RULES LIST (left panel) ==========
    function renderRulesList() {
        var container = document.getElementById('rules-list');
        if (!container) return;

        if (!rules.length) {
            container.innerHTML = '<div class="text-center py-12 text-slate-400"><i class="fa-solid fa-inbox text-3xl mb-3 block"></i>No rules yet</div>';
            return;
        }

        container.innerHTML = rules.map(function(rule) {
            var isSelected = rule.id === selectedRuleId;
            return '<div class="p-3 rounded-lg border cursor-pointer transition-all ' + (isSelected ? 'border-primary bg-blue-50' : 'border-slate-200 bg-white hover:border-blue-200 hover:bg-slate-50') + '" onclick="window.selectRule(\'' + rule.id + '\')">' +
                '<div class="flex items-start justify-between gap-2">' +
                    '<div class="flex-1 min-w-0">' +
                        '<div class="flex items-center gap-2 mb-1">' +
                            '<span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ' + (priorityColors[rule.priority] || priorityColors.low) + '">' + rule.priority + '</span>' +
                            '<span class="w-2 h-2 rounded-full ' + (rule.enabled ? 'bg-green-500' : 'bg-slate-300') + ' flex-shrink-0"></span>' +
                        '</div>' +
                        '<div class="font-medium text-sm text-slate-900 truncate">' + rule.name + '</div>' +
                        '<div class="text-xs text-slate-500 mt-0.5 truncate">' + rule.trigger.device + '</div>' +
                    '</div>' +
                    '<div class="text-right flex-shrink-0">' +
                        '<div class="text-xs font-semibold text-slate-900">' + rule.triggerCount + '</div>' +
                        '<div class="text-[10px] text-slate-400">triggers</div>' +
                    '</div>' +
                '</div>' +
            '</div>';
        }).join('');

        updateStatistics();
    }

    // ========== RENDER RULE EDITOR (right panel) ==========
    function renderRuleEditor(ruleId) {
        var rule = ruleId ? rules.find(function(r){ return r.id === ruleId; }) : null;
        var content = document.getElementById('wizard-content');
        var titleEl = document.getElementById('rule-editor-title');
        var idDisplay = document.getElementById('rule-id-display');
        var statusToggle = document.getElementById('rule-status-toggle');
        if (!content) return;

        if (!rule) {
            if (titleEl) titleEl.textContent = 'Create New Rule';
            if (idDisplay) idDisplay.textContent = 'RULE-NEW';
            if (statusToggle) statusToggle.checked = true;
            content.innerHTML = renderStep1(null);
            return;
        }

        if (titleEl) titleEl.textContent = 'Edit Rule: ' + rule.name;
        if (idDisplay) idDisplay.textContent = rule.id.toUpperCase();
        if (statusToggle) { statusToggle.checked = rule.enabled; }

        content.innerHTML = renderStep1(rule);
    }

    function renderStep1(rule) {
        var t = rule ? rule.trigger : {};
        return '<div class="space-y-6">' +
            // Rule name
            '<div>' +
                '<label class="block text-sm font-semibold text-slate-700 mb-1.5">Rule Name</label>' +
                '<input type="text" id="rule-name-input" value="' + (rule ? rule.name : '') + '" placeholder="e.g., High Temperature Alert" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:border-primary">' +
            '</div>' +
            // Description
            '<div>' +
                '<label class="block text-sm font-semibold text-slate-700 mb-1.5">Description</label>' +
                '<textarea id="rule-desc-input" rows="2" placeholder="Describe what this rule does..." class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:border-primary">' + (rule ? rule.description : '') + '</textarea>' +
            '</div>' +
            // Priority
            '<div>' +
                '<label class="block text-sm font-semibold text-slate-700 mb-1.5">Priority</label>' +
                '<div class="grid grid-cols-4 gap-2">' +
                    ['critical','high','medium','low'].map(function(p) {
                        var active = rule && rule.priority === p;
                        return '<button type="button" class="py-2 px-3 rounded-lg border text-xs font-semibold transition-all ' + (active ? 'border-primary bg-primary text-white' : 'border-slate-200 text-slate-600 hover:border-primary hover:text-primary') + '" onclick="window.setPriority(\'' + (rule ? rule.id : 'new') + '\',\'' + p + '\')">' + p.charAt(0).toUpperCase() + p.slice(1) + '</button>';
                    }).join('') +
                '</div>' +
            '</div>' +
            // Trigger section
            '<div class="bg-slate-50 rounded-xl border border-slate-200 p-4 space-y-4">' +
                '<div class="flex items-center gap-2 mb-1">' +
                    '<div class="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center"><i class="fa-solid fa-bolt text-blue-600 text-xs"></i></div>' +
                    '<span class="font-semibold text-sm text-slate-800">Trigger Condition</span>' +
                '</div>' +
                '<div class="grid grid-cols-2 gap-3">' +
                    '<div><label class="block text-xs font-medium text-slate-600 mb-1">Device</label>' +
                    '<input type="text" value="' + (t.device || '') + '" placeholder="e.g., Load Cell LC-001" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"></div>' +

                    '<div><label class="block text-xs font-medium text-slate-600 mb-1">Parameter</label>' +
                    '<input type="text" value="' + (t.parameter || '') + '" placeholder="e.g., current_load" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"></div>' +
                '</div>' +
                '<div class="grid grid-cols-3 gap-3">' +
                    '<div><label class="block text-xs font-medium text-slate-600 mb-1">Operator</label>' +
                    '<select class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm">' +
                        ['>', '<', '>=', '<=', '==', '!='].map(function(op){ return '<option ' + (t.operator === op ? 'selected' : '') + '>' + op + '</option>'; }).join('') +
                    '</select></div>' +

                    '<div><label class="block text-xs font-medium text-slate-600 mb-1">Value</label>' +
                    '<input type="text" value="' + (t.value || '') + '" placeholder="e.g., 22500" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"></div>' +

                    '<div><label class="block text-xs font-medium text-slate-600 mb-1">Unit</label>' +
                    '<input type="text" value="' + (t.unit || '') + '" placeholder="e.g., kg, °C" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"></div>' +
                '</div>' +
            '</div>' +
            // Alert assignment
            '<div class="bg-slate-50 rounded-xl border border-slate-200 p-4 space-y-3">' +
                '<div class="flex items-center gap-2 mb-1">' +
                    '<div class="w-6 h-6 bg-amber-100 rounded-full flex items-center justify-center"><i class="fa-solid fa-bell text-amber-600 text-xs"></i></div>' +
                    '<span class="font-semibold text-sm text-slate-800">Alert Action</span>' +
                '</div>' +
                '<div><label class="block text-xs font-medium text-slate-600 mb-1">Alert Message</label>' +
                '<select class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm">' +
                    ['Critical Temperature','Device Offline','High Vibration','Low Battery','System Startup'].map(function(name) {
                        var sel = rule && rule.alertMessage === name ? 'selected' : '';
                        return '<option ' + sel + '>' + name + '</option>';
                    }).join('') +
                '</select></div>' +
            '</div>' +
        '</div>';
    }

    function updateStatistics() {
        var total   = rules.length;
        var active  = rules.filter(function(r){ return r.enabled; }).length;
        var triggers = rules.reduce(function(sum, r){ return sum + r.triggerCount; }, 0);
        var els = { 'total-rules': total, 'active-rules': active, 'total-triggers': triggers };
        Object.keys(els).forEach(function(id) {
            var el = document.getElementById(id);
            if (el) el.textContent = els[id];
        });
    }

    // ========== WINDOW ACTIONS ==========
    window.selectRule = function(id) {
        selectedRuleId = id;
        renderRulesList();
        renderRuleEditor(id);
    };

    window.setPriority = function(ruleId, priority) {
        var rule = rules.find(function(r){ return r.id === ruleId; });
        if (rule) { rule.priority = priority; renderRulesList(); renderRuleEditor(ruleId); }
    };

    window.startCreatingNewRule = function() {
        selectedRuleId = null;
        renderRulesList();
        renderRuleEditor(null);
    };

    window.saveRule = function() {
        showToast('Rule saved — coming soon', 'info');
    };

    window.testRule = function() {
        showToast('Testing rule...', 'info');
        setTimeout(function(){ showToast('Test alert triggered!', 'success'); }, 1500);
    };

    window.redirectToAlerts = function() {
        if (window.router) window.router.navigateTo('alerts');
        else showToast('Navigate to Alerts page', 'info');
    };

    window.showFilterModal   = function() { showToast('Filter — coming soon', 'info'); };
    window.toggleSortOrder   = function() { rules.reverse(); renderRulesList(); };
    window.refreshRules      = function() { renderRulesList(); showToast('Rules refreshed', 'success'); };
    window.showImportModal   = function() { showToast('Import Rules — coming soon', 'info'); };
    window.goToStep          = function(n) { showToast('Step ' + n + ' — coming soon', 'info'); };

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
    function cleanupRules() {
        document.querySelectorAll('[data-action-bound]').forEach(function(btn) {
            btn.removeAttribute('data-action-bound');
        });
        selectedRuleId = null;
        console.log('Rules cleanup complete');
    }

    // ========== INIT ==========
    window.initRules = function() {
        console.log('Initializing Rules Engine');
        renderRulesList();
        renderRuleEditor(null);
        initializeButtons();
    };

    window.cleanupRules = cleanupRules;
    window.addEventListener('beforeunload', cleanupRules);
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { initRules: window.initRules, cleanupRules: window.cleanupRules };
}