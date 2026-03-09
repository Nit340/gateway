// rules.js - Rules Engine Page Script

if (typeof window.rulesLoaded === 'undefined') {
    window.rulesLoaded = true;

    // ========== STATE ==========
    let rules          = [];
    let availableTags  = [];   // flat list of all modbus tag names
    let selectedRuleId = null;
    let currentRelayTag = '';  // Store the current relay tag

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

    // ========== UI CONTROLS ==========
    function showEditor(show) {
        var header = document.getElementById('rule-editor-header');
        var wizardContent = document.getElementById('wizard-content');
        var emptyState = document.getElementById('empty-state');
        
        if (show) {
            if (header) header.style.display = 'block';
            if (wizardContent) wizardContent.style.display = 'block';
            if (emptyState) emptyState.style.display = 'none';
        } else {
            if (header) header.style.display = 'none';
            if (wizardContent) wizardContent.style.display = 'none';
            if (emptyState) emptyState.style.display = 'flex';
        }
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
            if (data.success) availableTags = data.tags || [];  // [{name, device_name}]
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
                        relayDatapoint: r.relay_datapoint || '',
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
                var name  = typeof t === 'object' ? t.name : t;
                var label = typeof t === 'object' ? t.device_name + ' - ' + t.name : t;
                return '<option value="' + name + '"' + (name === selectedVal ? ' selected' : '') + '>' + label + '</option>';
            }).join('');
    }

    // ========== RENDER RULES LIST ==========
    function renderRulesList() {
        var container = document.getElementById('rules-list');
        if (!container) return;

        if (!rules.length) {
            container.innerHTML = '<div class="text-center py-12 text-slate-400">' +
                '<i class="fa-solid fa-inbox text-3xl mb-3 block"></i>' +
                '<p class="text-sm">No rules yet.</p>' +
                '<p class="text-xs mt-2">Click the buttons above to create your first rule</p></div>';
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
            return '<div class="tag-item">' +
                '<span class="tag-name"><i class="fa-solid fa-tag text-xs text-slate-400 mr-2"></i>' + tag + '</span>' +
                '<button type="button" class="remove-tag" ' +
                  'onclick="window.removeDatapoint(\'' + alias + '\',' + i + ')">' +
                  '<i class="fa-solid fa-xmark"></i>' +
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

            // Show add button and selector for ALL groups (hoist, ct, lt) with inline styles to ensure visibility
            var addSection = '<div class="flex gap-2 mb-3" style="display: flex !important; visibility: visible !important;">' +
                  '<select id="' + alias + '-select" class="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm" style="background-color: white; color: #1e293b; border: 1px solid #cbd5e1;">' +
                    buildTagOptions() +
                  '</select>' +
                  '<button type="button" class="add-tag-btn px-3 py-2 text-white rounded-lg text-sm transition-colors shadow-sm" style="opacity: 1; background-color: ' + 
                    (alias === 'hoist' ? '#9333ea' : alias === 'ct' ? '#0891b2' : '#059669') + ';" onclick="window.addDatapoint(\'' + alias + '\')">' +
                    '<i class="fa-solid fa-plus mr-1"></i> Add Tag</button>' +
                  '</div>';

            return '<div class="group-section border ' + colors.border + ' rounded-xl p-4 ' + colors.bg + '" style="margin-bottom: 1rem;">' +
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
                
                // Add section for ALL groups
                addSection +
                
                // Datapoints list
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
              'placeholder="e.g., Crane Group Monitoring" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary"></div>' +

            '<div><label class="block text-sm font-medium text-slate-700 mb-1.5">Description</label>' +
            '<textarea id="rule-desc-input" rows="2" placeholder="Describe what this rule does..." ' +
              'class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary">' + (rule ? rule.description : '') + '</textarea></div>' +

            '<div><label class="block text-sm font-medium text-slate-700 mb-1.5">Priority</label>' +
            '<div class="grid grid-cols-4 gap-2">' + priorityBtns + '</div></div>' +

            groupSection('hoist', 'HOIST Group') +
            groupSection('ct',    'CT Group') +
            groupSection('lt',    'LT Group') +

            // Individual Save button for Group Rule
            '<div class="flex items-center justify-between pt-3 border-t border-slate-100">' +
              '<button type="button" class="text-sm text-slate-500 hover:text-slate-700" onclick="window.clearRuleEditor()">' +
                '<i class="fa-solid fa-arrow-left mr-1"></i> Back to list</button>' +
              '<button type="button" class="save-rule-btn px-5 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-700 transition-colors shadow-sm flex items-center gap-2" onclick="window.saveGroupRule()">' +
                '<i class="fa-solid fa-floppy-disk"></i> Save Group Rule</button>' +
            '</div>' +
          '</div>';
    }

    // ========== EMERGENCY RULE EDITOR ==========
    function renderEmergencyRuleEditor(rule) {
        var relayVal = (rule && rule.relayDatapoint) ? rule.relayDatapoint : currentRelayTag;
        
        // Update currentRelayTag if rule has a value
        if (rule && rule.relayDatapoint) {
            currentRelayTag = rule.relayDatapoint;
        }

        return '<div class="space-y-5">' +
            '<div><label class="block text-sm font-medium text-slate-700 mb-1.5">Rule Name <span class="text-red-500">*</span></label>' +
            '<input type="text" id="rule-name-input" value="' + (rule ? rule.name : '') + '" ' +
              'placeholder="e.g., Overload Emergency Stop" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary"></div>' +

            '<div><label class="block text-sm font-medium text-slate-700 mb-1.5">Description</label>' +
            '<textarea id="rule-desc-input" rows="2" placeholder="Describe what this emergency rule does..." ' +
              'class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary">' + (rule ? rule.description : '') + '</textarea>' +
            '<p class="text-xs text-amber-600 mt-1 flex items-center gap-1">' +
              '<i class="fa-solid fa-triangle-exclamation"></i> Emergency rules trigger an immediate hardware relay output</p></div>' +

            '<div><label class="block text-sm font-medium text-slate-700 mb-1.5">Priority</label>' +
            '<div class="grid grid-cols-4 gap-2">' +
              '<button type="button" class="py-2 px-3 rounded-lg border text-xs font-semibold bg-red-600 border-red-600 text-white">Critical</button>' +
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
              
              <!-- Add button for Relay Tag -->
              '<div class="flex gap-2" style="display: flex !important; gap: 0.5rem; margin-bottom: 0.75rem;">' +
                '<select id="relay-tag-input" class="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-red-500/20 focus:border-red-500" style="background-color: white; color: #1e293b;">' +
                  buildTagOptions(relayVal) +
                '</select>' +
                '<button type="button" class="px-3 py-2 bg-red-600 text-white rounded-lg text-sm transition-colors shadow-sm hover:bg-red-700" style="background-color: #dc2626;" onclick="window.addRelayTag()">' +
                  '<i class="fa-solid fa-plus mr-1"></i> Add' +
                '</button>' +
              '</div>' +
              
              <!-- Display selected relay tag -->
              '<div id="relay-tag-display" class="mt-3">' +
                (relayVal ? '<div class="tag-item"><span class="tag-name"><i class="fa-solid fa-tag text-xs text-slate-400 mr-2"></i>' + relayVal + '</span>' +
                '<button type="button" class="remove-tag" onclick="window.removeRelayTag()">' +
                  '<i class="fa-solid fa-xmark"></i></button></div>' : '<div class="text-xs text-slate-400 italic px-1">No relay tag selected</div>') +
              '</div>' +
              
              '<p class="text-xs text-slate-500 mt-1.5">Tag sent to <span class="font-mono">gpio_service</span> when this rule triggers</p>' +
            '</div>' +

            // Individual Save button for Emergency Rule
            '<div class="flex items-center justify-between pt-3 border-t border-slate-100">' +
              '<button type="button" class="text-sm text-slate-500 hover:text-slate-700" onclick="window.clearRuleEditor()">' +
                '<i class="fa-solid fa-arrow-left mr-1"></i> Back to list</button>' +
              '<button type="button" class="save-rule-btn px-5 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors shadow-sm flex items-center gap-2" onclick="window.saveEmergencyRule()">' +
                '<i class="fa-solid fa-floppy-disk"></i> Save Emergency Rule</button>' +
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
            showEditor(false);
            return;
        }

        showEditor(true);

        if (titleEl) titleEl.textContent = 'Edit Rule: ' + rule.name;
        if (idDisp)  idDisp.textContent  = rule.id.toUpperCase();
        if (toggle)  toggle.checked      = rule.enabled;

        resetGroupData();
        
        // Reset currentRelayTag
        currentRelayTag = '';
        
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
        currentRelayTag = '';
        var content = document.getElementById('wizard-content');
        var titleEl = document.getElementById('rule-editor-title');
        var idDisp  = document.getElementById('rule-id-display');
        var toggle  = document.getElementById('rule-status-toggle');
        
        if (titleEl) titleEl.textContent = 'Create Group Rule';
        if (idDisp) idDisp.textContent = 'RULE-NEW';
        if (toggle) toggle.checked = true;
        
        var tempRule = { id: 'new', name: '', description: '', priority: 'medium', ruleType: 'group', groups: {} };
        if (content) {
            content.innerHTML = renderGroupRuleEditor(tempRule);
            showEditor(true);
        }
    };

    window.createEmergencyRule = function() {
        selectedRuleId = null;
        resetGroupData();
        currentRelayTag = '';
        var content = document.getElementById('wizard-content');
        var titleEl = document.getElementById('rule-editor-title');
        var idDisp  = document.getElementById('rule-id-display');
        var toggle  = document.getElementById('rule-status-toggle');
        
        if (titleEl) titleEl.textContent = 'Create Emergency Rule';
        if (idDisp) idDisp.textContent = 'RULE-NEW';
        if (toggle) toggle.checked = true;
        
        var tempRule = { id: 'new', name: '', description: '', priority: 'critical', ruleType: 'emergency', relayDatapoint: '' };
        if (content) {
            content.innerHTML = renderEmergencyRuleEditor(tempRule);
            showEditor(true);
        }
    };

    window.clearRuleEditor = function() {
        selectedRuleId = null;
        resetGroupData();
        currentRelayTag = '';
        renderRulesList();
        renderRuleEditor(null);
        showEditor(false);
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
        showNotification('Tag added to ' + alias.toUpperCase(), 'success');
    };

    window.removeDatapoint = function(alias, index) {
        currentGroupData[alias].datapoints.splice(index, 1);
        var list = document.getElementById(alias + '-datapoints-list');
        if (list) list.innerHTML = renderDatapointsList(currentGroupData[alias].datapoints, alias);
        showNotification('Tag removed from ' + alias.toUpperCase(), 'info');
    };

    // Function for adding relay tag in emergency rule
    window.addRelayTag = function() {
        var select = document.getElementById('relay-tag-input');
        if (!select || !select.value) { 
            showNotification('Select a relay tag first', 'warning'); 
            return; 
        }
        var tag = select.value;
        
        // Store the relay tag
        currentRelayTag = tag;
        
        // Update the relay tag in the display
        var display = document.getElementById('relay-tag-display');
        if (display) {
            display.innerHTML = '<div class="tag-item"><span class="tag-name"><i class="fa-solid fa-tag text-xs text-slate-400 mr-2"></i>' + tag + '</span>' +
                '<button type="button" class="remove-tag" onclick="window.removeRelayTag()">' +
                '<i class="fa-solid fa-xmark"></i></button></div>';
        }
        
        showNotification('Relay tag selected: ' + tag, 'success');
    };

    // Function for removing relay tag
    window.removeRelayTag = function() {
        currentRelayTag = '';
        var display = document.getElementById('relay-tag-display');
        if (display) {
            display.innerHTML = '<div class="text-xs text-slate-400 italic px-1">No relay tag selected</div>';
        }
        var select = document.getElementById('relay-tag-input');
        if (select) {
            select.value = '';
        }
        showNotification('Relay tag removed', 'info');
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

    // ========== INDIVIDUAL RULE SAVE FUNCTIONS ==========
    
    // Save Group Rule
    window.saveGroupRule = async function() {
        console.log('[Rules] Saving Group Rule');
        
        var nameEl = document.getElementById('rule-name-input');
        var descEl = document.getElementById('rule-desc-input');
        var toggleEl = document.getElementById('rule-status-toggle');

        if (!nameEl || !nameEl.value.trim()) { 
            showNotification('Rule name is required', 'warning'); 
            return; 
        }

        // Sync toggle states from DOM
        ['hoist','ct','lt'].forEach(function(alias) {
            var chk = document.getElementById(alias + '-enabled');
            if (chk) currentGroupData[alias].enabled = chk.checked;
        });

        var hasData = ['hoist','ct','lt'].some(function(alias) {
            return currentGroupData[alias].enabled && currentGroupData[alias].datapoints.length > 0;
        });
        
        if (!hasData) { 
            showNotification('At least one group must have tags added', 'warning'); 
            return; 
        }

        var ruleId = selectedRuleId && selectedRuleId !== 'new' ? selectedRuleId : genId('group');

        var priority = 'medium';
        // Grab current priority from active button
        ['critical','high','medium','low'].forEach(function(p) {
            var btn = document.getElementById('prio-' + p);
            if (btn && btn.classList.contains('bg-primary')) priority = p;
        });

        // Build groups
        var groups = {};
        ['hoist','ct','lt'].forEach(function(alias) {
            groups[alias] = {
                enabled: currentGroupData[alias].enabled,
                datapoints: currentGroupData[alias].datapoints.slice()
            };
        });

        var ruleData = {
            id: ruleId,
            name: nameEl.value.trim(),
            description: descEl ? descEl.value.trim() : '',
            enabled: toggleEl ? toggleEl.checked : true,
            ruleType: 'group',
            priority: priority,
            groups: groups
        };

        await saveRuleToServer(ruleData);
    };

    // Save Emergency Rule
    window.saveEmergencyRule = async function() {
        console.log('[Rules] Saving Emergency Rule');
        
        var nameEl = document.getElementById('rule-name-input');
        var descEl = document.getElementById('rule-desc-input');
        var toggleEl = document.getElementById('rule-status-toggle');

        if (!nameEl || !nameEl.value.trim()) { 
            showNotification('Rule name is required', 'warning'); 
            return; 
        }

        if (!currentRelayTag) {
            showNotification('Please select a relay tag using the Add button', 'warning');
            return;
        }

        var ruleId = selectedRuleId && selectedRuleId !== 'new' ? selectedRuleId : genId('emergency');

        var ruleData = {
            id: ruleId,
            name: nameEl.value.trim(),
            description: descEl ? descEl.value.trim() : '',
            enabled: toggleEl ? toggleEl.checked : true,
            ruleType: 'emergency',
            priority: 'critical',
            relayDatapoint: currentRelayTag,
            groups: {}
        };

        await saveRuleToServer(ruleData);
    };

    // ========== COMMON SERVER SAVE FUNCTION ==========
    async function saveRuleToServer(ruleData) {
        console.log('[Rules] Saving to server:', ruleData);
        
        try {
            showNotification('Saving rule...', 'info');
            
            var res = await fetch('/api/rules/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ rule: ruleData })
            });
            
            var data = await res.json();
            
            if (!data.success) { 
                showNotification('Save failed: ' + (data.error || 'unknown'), 'error'); 
                return false; 
            }
            
            console.log('[Rules] Save successful, server response:', data);
            
            // Reload from DB and re-render
            await loadRules();
            selectedRuleId = ruleData.id;
            renderRulesList();
            renderRuleEditor(ruleData.id);
            
            showNotification('Rule saved successfully', 'success');
            return true;
            
        } catch(e) {
            console.error('[Rules] Save error:', e);
            showNotification('Could not reach server', 'error');
            return false;
        }
    }

    // ========== JSON PIPELINE TRIGGER ==========
    window.triggerJsonPipeline = async function() {
        console.log('[Rules] Triggering JSON Pipeline');
        
        var statusEl = document.getElementById('pipeline-status');
        if (statusEl) statusEl.textContent = 'Running...';
        
        try {
            showNotification('Triggering JSON pipeline...', 'info');
            
            // This is the endpoint that triggers the JSON pipeline
            var res = await fetch('/api/rules/pipeline/trigger', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    timestamp: new Date().toISOString(),
                    action: 'generate_json_pipeline'
                })
            });
            
            var data = await res.json();
            
            if (data.success) {
                if (statusEl) statusEl.textContent = 'Completed';
                showNotification('JSON pipeline triggered successfully', 'success');
            } else {
                if (statusEl) statusEl.textContent = 'Failed';
                showNotification('Pipeline trigger failed: ' + (data.error || 'unknown'), 'error');
            }
            
        } catch(e) {
            console.error('[Rules] Pipeline error:', e);
            if (statusEl) statusEl.textContent = 'Error';
            showNotification('Could not trigger pipeline', 'error');
        }
        
        // Reset status after 5 seconds
        setTimeout(function() {
            if (statusEl) statusEl.textContent = 'Ready';
        }, 5000);
    };

    window.testRule = function() { 
        showNotification('Testing rule...', 'info'); 
        setTimeout(function() { 
            showNotification('Test alert triggered!', 'success'); 
        }, 1500); 
    };
    
    window.showFilterModal = function() { 
        showNotification('Filter — coming soon', 'info'); 
    };
    
    window.toggleSortOrder = function() { 
        rules.reverse(); 
        renderRulesList(); 
    };
    
    window.refreshRules = function() { 
        loadRules().then(function() { 
            renderRulesList(); 
            renderRuleEditor(selectedRuleId); 
            showNotification('Refreshed', 'success'); 
        }); 
    };
    
    window.showImportModal = function() { 
        showNotification('Import — coming soon', 'info'); 
    };

    // ========== INIT ==========
    window.initRules = async function() {
        console.log('[Rules] Initializing');
        await loadTags();
        await loadRules();
        renderRulesList();
        renderRuleEditor(null);
        showEditor(false);
        
        // Ensure pipeline status is set
        var statusEl = document.getElementById('pipeline-status');
        if (statusEl) statusEl.textContent = 'Ready';
    };

    window.cleanupRules = function() { 
        selectedRuleId = null; 
        currentRelayTag = '';
    };

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