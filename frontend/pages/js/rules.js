// rules.js - Rules Engine Page Script

if (typeof window.rulesLoaded === 'undefined') {
    window.rulesLoaded = true;

    // ========== STATE ==========
    let rules          = [];
    let availableTags  = [];   // flat list of all modbus tag names
    let selectedRuleId = null;

    let currentGroupData = {
        hoist: { enabled: true, datapoints: [] },
        ct:    { enabled: true, datapoints: [] },
        lt:    { enabled: true, datapoints: [] }
    };

    // ========== HELPERS ==========
    var priorityColors = {
        critical: 'bg-red-100 text-red-700 border border-red-200',
        high:     'bg-orange-100 text-orange-700 border border-orange-200',
        medium:   'bg-yellow-100 text-yellow-700 border border-yellow-200',
        low:      'bg-slate-100 text-slate-600 border border-slate-200'
    };

    function formatDate(iso) {
        if (!iso) return 'Never';
        return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }

    function genId(prefix) {
        return prefix + '_' + Date.now();
    }

    // ========== NOTIFICATIONS ==========
    function showNotification(message, type) {
        type = type || 'info';
        document.querySelectorAll('.notification-toast').forEach(function(n) { n.remove(); });
        var n = document.createElement('div');
        var styles = {
            success: 'bg-emerald-50 text-emerald-800 border-emerald-200',
            error:   'bg-red-50 text-red-800 border-red-200',
            warning: 'bg-amber-50 text-amber-800 border-amber-200',
            info:    'bg-blue-50 text-blue-800 border-blue-200'
        };
        var icons = {
            success: 'fa-check-circle', error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle', info: 'fa-info-circle'
        };
        n.className = 'notification-toast fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg border ' + (styles[type] || styles.info);
        n.innerHTML = '<div class="flex items-center">' +
            '<i class="fa-solid ' + (icons[type] || 'fa-info-circle') + ' mr-2"></i>' +
            '<span class="text-sm font-medium">' + message + '</span>' +
            '<button class="ml-4 text-gray-500 hover:text-gray-700" onclick="this.closest(\'.notification-toast\').remove()">' +
              '<i class="fa-solid fa-times"></i></button></div>';
        document.body.appendChild(n);
        setTimeout(function() {
            if (n.parentNode) { n.classList.add('fade-out'); setTimeout(function() { n.remove(); }, 300); }
        }, 3000);
    }

    // ========== LOAD TAGS FROM DB ==========
    async function loadTags() {
        try {
            const res  = await fetch('/api/rules/tags');
            const data = await res.json();
            if (data.success) availableTags = data.tags || [];
        } catch(e) {
            console.warn('[Rules] Failed to load tags:', e);
        }
    }

    // ========== LOAD RULES FROM DB ==========
    async function loadRules() {
        try {
            const res  = await fetch('/api/rules');
            const data = await res.json();
            if (data.success) {
                rules = (data.rules || []).map(function(r) {
                    return {
                        id:             r.id,
                        name:           r.name,
                        ruleType:       r.rule_type,
                        priority:       r.priority,
                        description:    r.description,
                        enabled:        !!r.enabled,
                        groups:         r.groups || {},
                        relayDatapoint: r.relay_datapoint || 'relay2',
                        triggerCount:   r.trigger_count || 0,
                        lastTriggered:  r.last_triggered || null
                    };
                });
            }
        } catch(e) {
            console.warn('[Rules] Failed to load rules:', e);
        }
    }

    // ========== BUILD TAG OPTIONS ==========
    function buildTagOptions(selectedVal) {
        if (!availableTags.length) return '<option value="">No tags found</option>';
        return '<option value="">Select tag...</option>' +
            availableTags.map(function(t) {
                return '<option value="' + t + '"' + (t === selectedVal ? ' selected' : '') + '>' + t + '</option>';
            }).join('');
    }

    // ========== RENDER RULES LIST ==========
    function renderRulesList() {
        var container = document.getElementById('rules-list');
        if (!container) return;

        if (!rules.length) {
            container.innerHTML = '<div class="text-center py-12 text-slate-400">' +
                '<i class="fa-solid fa-inbox text-3xl mb-3 block"></i>' +
                '<p class="text-sm">No rules yet.</p></div>';
            updateStatistics();
            return;
        }

        container.innerHTML = rules.map(function(rule) {
            var sel   = rule.id === selectedRuleId;
            var badge = rule.ruleType === 'group'
                ? '<span class="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">GROUP</span>'
                : '<span class="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded">EMERGENCY</span>';

            return '<div class="p-4 rounded-lg border cursor-pointer transition-all ' +
                (sel ? 'border-primary bg-blue-50' : 'border-slate-200 bg-white hover:border-blue-200 hover:bg-slate-50') +
                '" onclick="window.selectRule(\'' + rule.id + '\')">' +
                '<div class="flex items-start justify-between gap-2">' +
                  '<div class="flex-1 min-w-0">' +
                    '<div class="flex items-center gap-1.5 mb-2">' +
                      '<span class="inline-flex px-2 py-0.5 rounded text-[10px] font-semibold uppercase ' + (priorityColors[rule.priority] || priorityColors.low) + '">' + rule.priority + '</span>' +
                      '<span class="w-2 h-2 rounded-full ' + (rule.enabled ? 'bg-green-500' : 'bg-slate-300') + '"></span>' +
                      badge +
                    '</div>' +
                    '<div class="font-medium text-sm text-slate-900 truncate">' + rule.name + '</div>' +
                  '</div>' +
                  '<div class="text-right flex-shrink-0">' +
                    '<div class="text-sm font-semibold">' + (rule.triggerCount || 0) + '</div>' +
                    '<div class="text-[10px] text-slate-400">triggers</div>' +
                  '</div>' +
                '</div>' +
                '<div class="mt-2 text-xs text-slate-400"><i class="fa-regular fa-clock mr-1"></i>Last: ' + formatDate(rule.lastTriggered) + '</div>' +
              '</div>';
        }).join('');

        updateStatistics();
    }

    // ========== RENDER DATAPOINTS LIST ==========
    function renderDatapointsList(datapoints, alias) {
        if (!datapoints || !datapoints.length)
            return '<div class="text-xs text-slate-400 italic px-1">No tags added yet</div>';
        return datapoints.map(function(tag, i) {
            return '<div class="flex items-center justify-between bg-white px-3 py-1.5 rounded-lg border border-slate-200">' +
                '<span class="text-sm font-mono text-slate-700">' + tag + '</span>' +
                '<button type="button" class="text-red-400 hover:text-red-600 ml-2" ' +
                  'onclick="window.removeDatapoint(\'' + alias + '\',' + i + ')">' +
                  '<i class="fa-solid fa-xmark text-xs"></i>' +
                '</button>' +
              '</div>';
        }).join('');
    }

    // ========== GROUP RULE EDITOR ==========
    function renderGroupRuleEditor(rule) {
        function groupSection(alias, label) {
            var colors = {
                hoist: { border:'border-purple-200', bg:'bg-purple-50/20', iconBg:'bg-purple-100', iconTxt:'text-purple-600', title:'text-purple-800', btn:'bg-purple-600 hover:bg-purple-700' },
                ct:    { border:'border-cyan-200',   bg:'bg-cyan-50/20',   iconBg:'bg-cyan-100',   iconTxt:'text-cyan-600',   title:'text-cyan-800',   btn:'bg-cyan-600 hover:bg-cyan-700'   },
                lt:    { border:'border-emerald-200',bg:'bg-emerald-50/20',iconBg:'bg-emerald-100',iconTxt:'text-emerald-600',title:'text-emerald-800',btn:'bg-emerald-600 hover:bg-emerald-700'}
            }[alias];
            var gdata = currentGroupData[alias];

            return '<div class="border ' + colors.border + ' rounded-xl p-4 ' + colors.bg + '">' +
                '<div class="flex items-center justify-between mb-3">' +
                  '<div class="flex items-center gap-2">' +
                    '<div class="w-6 h-6 ' + colors.iconBg + ' rounded-full flex items-center justify-center">' +
                      '<i class="fa-solid fa-layer-group ' + colors.iconTxt + ' text-xs"></i>' +
                    '</div>' +
                    '<span class="font-semibold text-sm ' + colors.title + '">' + label + '</span>' +
                  '</div>' +
                  '<label class="toggle-switch scale-75">' +
                    '<input type="checkbox" id="' + alias + '-enabled" ' + (gdata.enabled ? 'checked' : '') +
                      ' onchange="window.toggleGroup(\'' + alias + '\',this.checked)">' +
                    '<span class="toggle-slider"></span>' +
                  '</label>' +
                '</div>' +
                '<div class="flex gap-2 mb-3">' +
                  '<select id="' + alias + '-select" class="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm">' +
                    buildTagOptions() +
                  '</select>' +
                  '<button type="button" class="px-3 py-2 ' + colors.btn + ' text-white rounded-lg text-sm transition-colors" ' +
                    'onclick="window.addDatapoint(\'' + alias + '\')">' +
                    '<i class="fa-solid fa-plus"></i>' +
                  '</button>' +
                '</div>' +
                '<div id="' + alias + '-datapoints-list" class="space-y-1.5">' +
                  renderDatapointsList(gdata.datapoints, alias) +
                '</div>' +
              '</div>';
        }

        var curPriority = (rule && rule.priority) || 'medium';
        var priorityBtns = ['critical','high','medium','low'].map(function(p) {
            var active = p === curPriority;
            return '<button type="button" id="prio-' + p + '" class="py-2 px-3 rounded-lg border text-xs font-semibold transition-all ' +
                (active ? 'border-primary bg-primary text-white' : 'border-slate-200 text-slate-600 hover:border-primary hover:text-primary') +
                '" onclick="window.setPriority(\'' + (rule ? rule.id : 'new') + '\',\'' + p + '\')">' +
                p.charAt(0).toUpperCase() + p.slice(1) + '</button>';
        }).join('');

        return '<div class="space-y-5">' +
            '<div><label class="block text-sm font-medium text-slate-700 mb-1.5">Rule Name <span class="text-red-500">*</span></label>' +
            '<input type="text" id="rule-name-input" value="' + (rule ? rule.name : '') + '" ' +
              'placeholder="e.g., Crane Group Monitoring" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"></div>' +

            '<div><label class="block text-sm font-medium text-slate-700 mb-1.5">Description</label>' +
            '<textarea id="rule-desc-input" rows="2" placeholder="Describe what this rule does..." ' +
              'class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm">' + (rule ? rule.description : '') + '</textarea></div>' +

            '<div><label class="block text-sm font-medium text-slate-700 mb-1.5">Priority</label>' +
            '<div class="grid grid-cols-4 gap-2">' + priorityBtns + '</div></div>' +

            groupSection('hoist', 'HOIST Group') +
            groupSection('ct',    'CT Group') +
            groupSection('lt',    'LT Group') +

            '<div class="flex items-center justify-between pt-3 border-t border-slate-100">' +
              '<button type="button" class="text-sm text-slate-500 hover:text-slate-700" onclick="window.clearRuleEditor()">' +
                '<i class="fa-solid fa-arrow-left mr-1"></i> Back</button>' +
              '<button type="button" class="px-5 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primaryHover transition-colors shadow-sm flex items-center gap-2" onclick="window.saveRule()">' +
                '<i class="fa-solid fa-floppy-disk"></i> Save Rule</button>' +
            '</div>' +
          '</div>';
    }

    // ========== EMERGENCY RULE EDITOR ==========
    // Emergency rule = relay tag dropdown only. No HOIST section.
    function renderEmergencyRuleEditor(rule) {
        var relayVal = (rule && rule.relayDatapoint) ? rule.relayDatapoint : '';

        return '<div class="space-y-5">' +
            '<div><label class="block text-sm font-medium text-slate-700 mb-1.5">Rule Name <span class="text-red-500">*</span></label>' +
            '<input type="text" id="rule-name-input" value="' + (rule ? rule.name : '') + '" ' +
              'placeholder="e.g., Overload Emergency Stop" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"></div>' +

            '<div><label class="block text-sm font-medium text-slate-700 mb-1.5">Description</label>' +
            '<textarea id="rule-desc-input" rows="2" placeholder="Describe what this emergency rule does..." ' +
              'class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm">' + (rule ? rule.description : '') + '</textarea>' +
            '<p class="text-xs text-amber-600 mt-1 flex items-center gap-1">' +
              '<i class="fa-solid fa-triangle-exclamation"></i> Emergency rules trigger an immediate hardware relay output</p></div>' +

            '<div><label class="block text-sm font-medium text-slate-700 mb-1.5">Priority</label>' +
            '<div class="grid grid-cols-4 gap-2">' +
              '<button type="button" class="py-2 px-3 rounded-lg border text-xs font-semibold bg-primary border-primary text-white">Critical</button>' +
              '<button type="button" disabled class="py-2 px-3 rounded-lg border text-xs font-semibold border-slate-200 text-slate-400 bg-slate-50">High</button>' +
              '<button type="button" disabled class="py-2 px-3 rounded-lg border text-xs font-semibold border-slate-200 text-slate-400 bg-slate-50">Medium</button>' +
              '<button type="button" disabled class="py-2 px-3 rounded-lg border text-xs font-semibold border-slate-200 text-slate-400 bg-slate-50">Low</button>' +
            '</div>' +
            '<p class="text-xs text-slate-500 mt-1">Emergency rules are always critical priority</p></div>' +

            '<div class="border border-red-200 rounded-xl p-4 bg-red-50/20">' +
              '<div class="flex items-center gap-2 mb-3">' +
                '<div class="w-6 h-6 bg-red-100 rounded-full flex items-center justify-center">' +
                  '<i class="fa-solid fa-bolt text-red-600 text-xs"></i></div>' +
                '<span class="font-semibold text-sm text-red-800">Emergency Output Relay</span>' +
              '</div>' +
              '<label class="block text-xs font-medium text-slate-600 mb-1.5">Relay Tag</label>' +
              '<select id="relay-tag-input" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm">' +
                buildTagOptions(relayVal) +
              '</select>' +
              '<p class="text-xs text-slate-500 mt-1.5">Tag sent to <span class="font-mono">gpio_service</span> when this rule triggers</p>' +
            '</div>' +

            '<div class="flex items-center justify-between pt-3 border-t border-slate-100">' +
              '<button type="button" class="text-sm text-slate-500 hover:text-slate-700" onclick="window.clearRuleEditor()">' +
                '<i class="fa-solid fa-arrow-left mr-1"></i> Back</button>' +
              '<button type="button" class="px-5 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors shadow-sm flex items-center gap-2" onclick="window.saveRule()">' +
                '<i class="fa-solid fa-floppy-disk"></i> Save Rule</button>' +
            '</div>' +
          '</div>';
    }

    // ========== RENDER EDITOR ==========
    function renderRuleEditor(ruleId) {
        var rule    = ruleId ? rules.find(function(r) { return r.id === ruleId; }) : null;
        var content = document.getElementById('wizard-content');
        var titleEl = document.getElementById('rule-editor-title');
        var idDisp  = document.getElementById('rule-id-display');
        var toggle  = document.getElementById('rule-status-toggle');
        if (!content) return;

        if (!rule) {
            if (titleEl) titleEl.textContent = 'Create New Rule';
            if (idDisp)  idDisp.textContent  = 'RULE-NEW';
            if (toggle)  toggle.checked      = true;
            resetGroupData();
            content.innerHTML = '<div class="text-center py-16 text-slate-400">' +
                '<i class="fa-solid fa-diagram-project text-4xl mb-4 block"></i>' +
                '<p class="text-sm">Use the buttons above to create a Group Rule or Emergency Rule.</p></div>';
            return;
        }

        if (titleEl) titleEl.textContent = 'Edit Rule: ' + rule.name;
        if (idDisp)  idDisp.textContent  = rule.id.toUpperCase();
        if (toggle)  toggle.checked      = rule.enabled;

        resetGroupData();
        if (rule.groups) {
            ['hoist','ct','lt'].forEach(function(alias) {
                var gdata = rule.groups[alias] || null;
                if (gdata) {
                    currentGroupData[alias].enabled    = gdata.enabled !== false;
                    currentGroupData[alias].datapoints = gdata.datapoints || [];
                }
            });
        }

        if (rule.ruleType === 'group')     content.innerHTML = renderGroupRuleEditor(rule);
        if (rule.ruleType === 'emergency') content.innerHTML = renderEmergencyRuleEditor(rule);
    }

    function resetGroupData() {
        currentGroupData = {
            hoist: { enabled: true, datapoints: [] },
            ct:    { enabled: true, datapoints: [] },
            lt:    { enabled: true, datapoints: [] }
        };
    }

    function updateStatistics() {
        var totalEl    = document.getElementById('total-rules');
        var activeEl   = document.getElementById('active-rules');
        var triggersEl = document.getElementById('total-triggers');
        if (totalEl)    totalEl.textContent    = rules.length;
        if (activeEl)   activeEl.textContent   = rules.filter(function(r) { return r.enabled; }).length;
        if (triggersEl) triggersEl.textContent = rules.reduce(function(s, r) { return s + (r.triggerCount || 0); }, 0);
    }

    // ========== WINDOW ACTIONS ==========
    window.selectRule = function(id) {
        selectedRuleId = id;
        renderRulesList();
        renderRuleEditor(id);
    };

    window.createGroupRule = function() {
        selectedRuleId = null;
        resetGroupData();
        var content = document.getElementById('wizard-content');
        var titleEl = document.getElementById('rule-editor-title');
        if (titleEl) titleEl.textContent = 'Create Group Rule';
        var tempRule = { id: 'new', name: '', description: '', priority: 'medium', ruleType: 'group', groups: {} };
        if (content) content.innerHTML = renderGroupRuleEditor(tempRule);
    };

    window.createEmergencyRule = function() {
        selectedRuleId = null;
        resetGroupData();
        var content = document.getElementById('wizard-content');
        var titleEl = document.getElementById('rule-editor-title');
        if (titleEl) titleEl.textContent = 'Create Emergency Rule';
        var tempRule = { id: 'new', name: '', description: '', priority: 'critical', ruleType: 'emergency', relayDatapoint: 'relay2' };
        if (content) content.innerHTML = renderEmergencyRuleEditor(tempRule);
    };

    window.clearRuleEditor = function() {
        selectedRuleId = null;
        resetGroupData();
        renderRulesList();
        renderRuleEditor(null);
    };

    window.toggleGroup = function(alias, enabled) {
        if (currentGroupData[alias]) currentGroupData[alias].enabled = enabled;
    };

    window.addDatapoint = function(alias) {
        var select = document.getElementById(alias + '-select');
        if (!select || !select.value) { showNotification('Select a tag first', 'warning'); return; }
        var tag = select.value;
        if (currentGroupData[alias].datapoints.includes(tag)) { showNotification('Tag already added', 'warning'); return; }
        currentGroupData[alias].datapoints.push(tag);
        var list = document.getElementById(alias + '-datapoints-list');
        if (list) list.innerHTML = renderDatapointsList(currentGroupData[alias].datapoints, alias);
        select.value = '';
        showNotification('Tag added', 'success');
    };

    window.removeDatapoint = function(alias, index) {
        currentGroupData[alias].datapoints.splice(index, 1);
        var list = document.getElementById(alias + '-datapoints-list');
        if (list) list.innerHTML = renderDatapointsList(currentGroupData[alias].datapoints, alias);
        showNotification('Tag removed', 'info');
    };

    window.setPriority = function(ruleId, priority) {
        ['critical','high','medium','low'].forEach(function(p) {
            var btn = document.getElementById('prio-' + p);
            if (!btn) return;
            if (p === priority) {
                btn.className = 'py-2 px-3 rounded-lg border text-xs font-semibold transition-all border-primary bg-primary text-white';
            } else {
                btn.className = 'py-2 px-3 rounded-lg border text-xs font-semibold transition-all border-slate-200 text-slate-600 hover:border-primary hover:text-primary';
            }
        });
        var rule = rules.find(function(r) { return r.id === ruleId; });
        if (rule) rule.priority = priority;
    };

    window.saveRule = async function() {
        var nameEl   = document.getElementById('rule-name-input');
        var descEl   = document.getElementById('rule-desc-input');
        var toggleEl = document.getElementById('rule-status-toggle');

        if (!nameEl || !nameEl.value.trim()) { showNotification('Rule name is required', 'warning'); return; }

        var isEmergency = !!document.getElementById('relay-tag-input');
        var isGroup     = !isEmergency && !!document.getElementById('hoist-select');

        if (!isEmergency && !isGroup) { showNotification('Please create a rule first', 'warning'); return; }

        var ruleId = selectedRuleId && selectedRuleId !== 'new' ? selectedRuleId : genId(isEmergency ? 'emergency' : 'group');

        var ruleData = {
            id:          ruleId,
            name:        nameEl.value.trim(),
            description: descEl ? descEl.value.trim() : '',
            enabled:     toggleEl ? toggleEl.checked : true,
            ruleType:    isEmergency ? 'emergency' : 'group',
            priority:    isEmergency ? 'critical' : 'medium'
        };

        if (isEmergency) {
            var relayEl = document.getElementById('relay-tag-input');
            ruleData.relayDatapoint = relayEl ? relayEl.value : '';
            ruleData.groups = {};

        } else {
            // Sync toggle states from DOM
            ['hoist','ct','lt'].forEach(function(alias) {
                var chk = document.getElementById(alias + '-enabled');
                if (chk) currentGroupData[alias].enabled = chk.checked;
            });

            var hasData = ['hoist','ct','lt'].some(function(alias) {
                return currentGroupData[alias].enabled && currentGroupData[alias].datapoints.length > 0;
            });
            if (!hasData) { showNotification('At least one group must have tags added', 'warning'); return; }

            // Grab current priority from active button
            ['critical','high','medium','low'].forEach(function(p) {
                var btn = document.getElementById('prio-' + p);
                if (btn && btn.classList.contains('bg-primary')) ruleData.priority = p;
            });

            // Build groups keyed by alias (hoist / ct / lt)
            ruleData.groups = {};
            ['hoist','ct','lt'].forEach(function(alias) {
                ruleData.groups[alias] = {
                    enabled:    currentGroupData[alias].enabled,
                    datapoints: currentGroupData[alias].datapoints.slice()
                };
            });
        }

        // Save to DB via API
        try {
            var res  = await fetch('/api/rules/save', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ rule: ruleData })
            });
            var data = await res.json();
            if (!data.success) { showNotification('Save failed: ' + (data.error || 'unknown'), 'error'); return; }
        } catch(e) {
            showNotification('Could not reach server', 'error');
            return;
        }

        // Reload from DB and re-render
        await loadRules();
        selectedRuleId = ruleId;
        renderRulesList();
        renderRuleEditor(ruleId);
        showNotification('Rule saved', 'success');
    };

    window.testRule        = function() { showNotification('Testing rule...', 'info'); setTimeout(function() { showNotification('Test alert triggered!', 'success'); }, 1500); };
    window.showFilterModal = function() { showNotification('Filter — coming soon', 'info'); };
    window.toggleSortOrder = function() { rules.reverse(); renderRulesList(); };
    window.refreshRules    = function() { loadRules().then(function() { renderRulesList(); renderRuleEditor(selectedRuleId); showNotification('Refreshed', 'success'); }); };
    window.showImportModal = function() { showNotification('Import — coming soon', 'info'); };
    window.goToStep        = function(n) { showNotification('Step ' + n + ' — coming soon', 'info'); };

    // ========== INIT ==========
    window.initRules = async function() {
        console.log('[Rules] Initializing');
        await loadTags();
        await loadRules();
        renderRulesList();
        renderRuleEditor(null);
    };

    window.cleanupRules = function() { selectedRuleId = null; };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', window.initRules);
    } else {
        window.initRules();
    }

    window.addEventListener('beforeunload', window.cleanupRules);
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { initRules: window.initRules, cleanupRules: window.cleanupRules };
}