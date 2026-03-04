// rules.js - Rules Engine Page Script
// FIXED: All groups have Add buttons, proper rule type selection, no static data

if (typeof window.rulesLoaded === 'undefined') {
    window.rulesLoaded = true;

    // ========== EMPTY INITIAL DATA ==========
    let rules = []; // Start with empty array - no static data

    var selectedRuleId = null;
    
    // Store group data for the currently editing rule
    var currentGroupData = {
        hoist: { enabled: true, datapoints: [] },
        ct: { enabled: true, datapoints: [] },
        lt: { enabled: true, datapoints: [] }
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
        var d = new Date(iso);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }

    // ========== NOTIFICATION SYSTEM ==========
    function showNotification(message, type = 'info') {
        const existingNotifications = document.querySelectorAll('.notification-toast');
        existingNotifications.forEach(notification => {
            notification.remove();
        });
        
        const notification = document.createElement('div');
        notification.className = 'notification-toast fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg border transition-all duration-300 transform translate-x-0 opacity-100';
        
        const typeStyles = {
            success: 'bg-emerald-50 text-emerald-800 border-emerald-200',
            error: 'bg-red-50 text-red-800 border-red-200',
            warning: 'bg-amber-50 text-amber-800 border-amber-200',
            info: 'bg-blue-50 text-blue-800 border-blue-200'
        };
        
        notification.className += ' ' + (typeStyles[type] || typeStyles.info);
        
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        
        notification.innerHTML = `
            <div class="flex items-center">
                <i class="fa-solid ${icons[type] || icons.info} mr-2"></i>
                <span class="text-sm font-medium">${message}</span>
                <button class="ml-4 text-gray-500 hover:text-gray-700 close-notification">
                    <i class="fa-solid fa-times"></i>
                </button>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        const closeBtn = notification.querySelector('.close-notification');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                notification.remove();
            });
        }
        
        setTimeout(() => {
            if (notification.parentNode) {
                notification.classList.add('fade-out');
                setTimeout(() => notification.remove(), 300);
            }
        }, 3000);
    }

    // ========== RENDER RULES LIST ==========
    function renderRulesList() {
        var container = document.getElementById('rules-list');
        if (!container) return;

        if (!rules.length) {
            container.innerHTML = '<div class="text-center py-12 text-slate-400"><i class="fa-solid fa-inbox text-3xl mb-3 block"></i>No rules yet. Click "Create New Rule" to get started.</div>';
            return;
        }

        container.innerHTML = rules.map(function(rule) {
            var isSelected = rule.id === selectedRuleId;
            
            // Special styling for group rules
            var isGroupRule = rule.ruleType === 'group';
            var isEmergencyRule = rule.ruleType === 'emergency';
            var ruleTypeBadge = '';
            
            if (isGroupRule) {
                ruleTypeBadge = '<span class="ml-2 text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">GROUP</span>';
            } else if (isEmergencyRule) {
                ruleTypeBadge = '<span class="ml-2 text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded">EMERGENCY</span>';
            }
            
            return `<div class="p-4 rounded-lg border cursor-pointer transition-all ${isSelected ? 'border-primary bg-blue-50' : 'border-slate-200 bg-white hover:border-blue-200 hover:bg-slate-50'}" onclick="window.selectRule('${rule.id}')">
                <div class="flex items-start justify-between gap-2">
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${priorityColors[rule.priority] || priorityColors.low}">${rule.priority}</span>
                            <span class="w-2 h-2 rounded-full ${rule.enabled ? 'bg-green-500' : 'bg-slate-300'} flex-shrink-0"></span>
                            ${ruleTypeBadge}
                        </div>
                        <div class="font-medium text-sm text-slate-900 truncate">${rule.name}</div>
                        <div class="text-xs text-slate-500 mt-1 flex items-center gap-1">
                            <i class="fa-solid fa-microchip text-[10px]"></i>
                            ${isGroupRule ? `${Object.keys(rule.groups || {}).filter(g => rule.groups[g]?.enabled).length} groups enabled` : (rule.trigger?.device || 'No device')}
                        </div>
                    </div>
                    <div class="text-right flex-shrink-0">
                        <div class="text-sm font-semibold text-slate-900">${rule.triggerCount || 0}</div>
                        <div class="text-[10px] text-slate-400">triggers</div>
                    </div>
                </div>
                <div class="mt-2 text-xs text-slate-400 flex items-center gap-2">
                    <i class="fa-regular fa-clock"></i>
                    <span>Last: ${formatDate(rule.lastTriggered)}</span>
                </div>
            </div>`;
        }).join('');

        updateStatistics();
    }

    // ========== RENDER RULE EDITOR ==========
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
            
            // Reset current group data
            currentGroupData = {
                hoist: { enabled: true, datapoints: [] },
                ct: { enabled: true, datapoints: [] },
                lt: { enabled: true, datapoints: [] }
            };
            
            // Show empty state with message to select rule type
            content.innerHTML = `<div class="text-center py-12 text-slate-400">
                <i class="fa-solid fa-arrow-left text-3xl mb-3 block"></i>
                <p>Select a rule type from the dropdown above to get started</p>
            </div>`;
            return;
        }

        if (titleEl) titleEl.textContent = 'Edit Rule: ' + rule.name;
        if (idDisplay) idDisplay.textContent = rule.id.toUpperCase();
        if (statusToggle) { statusToggle.checked = rule.enabled; }

        // Load group data if it's a group rule
        if (rule.ruleType === 'group' && rule.groups) {
            currentGroupData = {
                hoist: { 
                    enabled: rule.groups.hoist?.enabled !== false, 
                    datapoints: rule.groups.hoist?.datapoints || [] 
                },
                ct: { 
                    enabled: rule.groups.ct?.enabled !== false, 
                    datapoints: rule.groups.ct?.datapoints || [] 
                },
                lt: { 
                    enabled: rule.groups.lt?.enabled !== false, 
                    datapoints: rule.groups.lt?.datapoints || [] 
                }
            };
        }

        // Check rule type
        if (rule.ruleType === 'group') {
            content.innerHTML = renderGroupRuleEditor(rule);
        } else if (rule.ruleType === 'emergency') {
            content.innerHTML = renderEmergencyRuleEditor(rule);
        }
    }

    // Emergency rule editor
    function renderEmergencyRuleEditor(rule) {
        return `<div class="space-y-6">
            <!-- Rule name -->
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1.5">Rule Name <span class="text-red-500">*</span></label>
                <input type="text" id="rule-name-input" value="${rule ? rule.name : ''}" placeholder="e.g., Overload Emergency Stop" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm">
            </div>
            
            <!-- Description -->
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1.5">Description</label>
                <textarea id="rule-desc-input" rows="2" placeholder="Describe what this rule does..." class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm">${rule ? rule.description : ''}</textarea>
                <p class="text-xs text-amber-600 mt-1 flex items-center gap-1">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    Emergency rules are for critical overload situations that require immediate action
                </p>
            </div>
            
            <!-- Priority (fixed to critical) -->
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1.5">Priority</label>
                <div class="grid grid-cols-4 gap-2">
                    <button type="button" class="py-2 px-3 rounded-lg border text-xs font-semibold border-primary bg-primary text-white">Critical</button>
                    <button type="button" disabled class="py-2 px-3 rounded-lg border text-xs font-semibold border-slate-200 text-slate-400 bg-slate-50">High</button>
                    <button type="button" disabled class="py-2 px-3 rounded-lg border text-xs font-semibold border-slate-200 text-slate-400 bg-slate-50">Medium</button>
                    <button type="button" disabled class="py-2 px-3 rounded-lg border text-xs font-semibold border-slate-200 text-slate-400 bg-slate-50">Low</button>
                </div>
                <p class="text-xs text-slate-500 mt-1">Emergency rules are always critical priority</p>
            </div>
            
            <!-- HOIST Group - Emergency overload monitoring -->
            <div class="border border-red-200 rounded-xl p-4 bg-red-50/20">
                <div class="flex items-center justify-between mb-4">
                    <div class="flex items-center gap-2">
                        <div class="w-6 h-6 bg-red-100 rounded-full flex items-center justify-center">
                            <i class="fa-solid fa-crane text-red-600 text-xs"></i>
                        </div>
                        <span class="font-semibold text-sm text-red-800">HOIST Overload Monitoring</span>
                    </div>
                    <label class="toggle-switch scale-75">
                        <input type="checkbox" id="hoist-enabled" ${currentGroupData.hoist.enabled ? 'checked' : ''} onchange="window.toggleGroup('hoist', this.checked)">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                
                <!-- Datapoint dropdown and Add button -->
                <div class="flex gap-2 mb-3">
                    <select id="hoist-datapoint-select" class="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm">
                        <option value="">Select Datapoint...</option>
                        <option value="hoist_up_current_load">hoist_up - current_load (Overload)</option>
                        <option value="hoist_up_temperature">hoist_up - temperature</option>
                        <option value="hoist_down_current_load">hoist_down - current_load (Overload)</option>
                        <option value="hoist_down_temperature">hoist_down - temperature</option>
                    </select>
                    <button type="button" class="px-4 py-2 bg-red-600 text-white rounded-lg text-sm hover:bg-red-700 transition-colors" onclick="window.addDatapoint('hoist')">
                        <i class="fa-solid fa-plus mr-1"></i> Add
                    </button>
                </div>
                
                <!-- List of added datapoints -->
                <div id="hoist-datapoints-list" class="space-y-2 mt-3">
                    ${renderDatapointsList(currentGroupData.hoist.datapoints, 'hoist')}
                </div>
                
                <!-- Overload threshold -->
                <div class="mt-4 pt-3 border-t border-red-100">
                    <label class="block text-xs font-medium text-slate-600 mb-2">Overload Threshold</label>
                    <div class="flex items-center gap-2">
                        <input type="number" id="overload-threshold" value="${rule?.overloadThreshold || 90}" class="w-24 border border-slate-300 rounded-lg px-3 py-2 text-sm">
                        <span class="text-sm text-slate-600">% of rated capacity</span>
                    </div>
                    <p class="text-xs text-slate-500 mt-1">Alert triggers when load exceeds this percentage</p>
                </div>
            </div>
            
            <!-- Change Rule Type Button (now just returns to empty state) -->
            <div class="flex justify-center pt-2">
                <button type="button" class="text-sm text-primary hover:text-primaryHover" onclick="window.clearRuleEditor()">
                    <i class="fa-solid fa-arrow-left mr-1"></i> Back to Rule Selection
                </button>
            </div>
        </div>`;
    }

    // Helper function to render the list of added datapoints
    function renderDatapointsList(datapoints, group) {
        if (!datapoints || datapoints.length === 0) {
            return `<div class="text-sm text-slate-500 italic p-2">No datapoints added yet</div>`;
        }
        
        return datapoints.map((dp, index) => {
            // Format the display name
            const displayName = dp.replace(/_/g, ' ');
            return `
                <div class="flex items-center justify-between bg-white p-2 rounded-lg border border-slate-200">
                    <span class="text-sm text-slate-700">${displayName}</span>
                    <button type="button" class="text-red-500 hover:text-red-700" onclick="window.removeDatapoint('${group}', ${index})">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </div>
            `;
        }).join('');
    }

    // Group rule editor with all three groups
    function renderGroupRuleEditor(rule) {
        return `<div class="space-y-6">
            <!-- Rule name -->
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1.5">Rule Name <span class="text-red-500">*</span></label>
                <input type="text" id="rule-name-input" value="${rule ? rule.name : ''}" placeholder="e.g., Crane Group Monitoring" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm">
            </div>
            
            <!-- Description -->
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1.5">Description</label>
                <textarea id="rule-desc-input" rows="2" placeholder="Describe what this rule does..." class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm">${rule ? rule.description : ''}</textarea>
            </div>
            
            <!-- Priority -->
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1.5">Priority</label>
                <div class="grid grid-cols-4 gap-2">
                    ${['critical','high','medium','low'].map(function(p) {
                        var active = rule && rule.priority === p;
                        return `<button type="button" class="py-2 px-3 rounded-lg border text-xs font-semibold transition-all ${active ? 'border-primary bg-primary text-white' : 'border-slate-200 text-slate-600 hover:border-primary hover:text-primary'}" onclick="window.setPriority('${rule ? rule.id : 'new'}', '${p}')">${p.charAt(0).toUpperCase() + p.slice(1)}</button>`;
                    }).join('')}
                </div>
            </div>
            
            <!-- HOIST Group -->
            <div class="border border-purple-200 rounded-xl p-4 bg-purple-50/20">
                <div class="flex items-center justify-between mb-4">
                    <div class="flex items-center gap-2">
                        <div class="w-6 h-6 bg-purple-100 rounded-full flex items-center justify-center">
                            <i class="fa-solid fa-crane text-purple-600 text-xs"></i>
                        </div>
                        <span class="font-semibold text-sm text-purple-800">HOIST Group</span>
                    </div>
                    <label class="toggle-switch scale-75">
                        <input type="checkbox" id="hoist-enabled" ${currentGroupData.hoist.enabled ? 'checked' : ''} onchange="window.toggleGroup('hoist', this.checked)">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                
                <!-- Datapoint dropdown and Add button -->
                <div class="flex gap-2 mb-3">
                    <select id="hoist-datapoint-select" class="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm">
                        <option value="">Select Datapoint...</option>
                        <option value="hoist_up_current_load">hoist_up - current_load</option>
                        <option value="hoist_up_speed">hoist_up - speed</option>
                        <option value="hoist_up_temperature">hoist_up - temperature</option>
                        <option value="hoist_down_current_load">hoist_down - current_load</option>
                        <option value="hoist_down_speed">hoist_down - speed</option>
                        <option value="hoist_down_temperature">hoist_down - temperature</option>
                        <option value="hoist_up_position">hoist_up - position</option>
                        <option value="hoist_down_position">hoist_down - position</option>
                    </select>
                    <button type="button" class="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm hover:bg-purple-700 transition-colors" onclick="window.addDatapoint('hoist')">
                        <i class="fa-solid fa-plus mr-1"></i> Add
                    </button>
                </div>
                
                <!-- List of added datapoints -->
                <div id="hoist-datapoints-list" class="space-y-2 mt-3">
                    ${renderDatapointsList(currentGroupData.hoist.datapoints, 'hoist')}
                </div>
            </div>
            
            <!-- CT Group -->
            <div class="border border-cyan-200 rounded-xl p-4 bg-cyan-50/20">
                <div class="flex items-center justify-between mb-4">
                    <div class="flex items-center gap-2">
                        <div class="w-6 h-6 bg-cyan-100 rounded-full flex items-center justify-center">
                            <i class="fa-solid fa-arrows-left-right text-cyan-600 text-xs"></i>
                        </div>
                        <span class="font-semibold text-sm text-cyan-800">CT Group</span>
                    </div>
                    <label class="toggle-switch scale-75">
                        <input type="checkbox" id="ct-enabled" ${currentGroupData.ct.enabled ? 'checked' : ''} onchange="window.toggleGroup('ct', this.checked)">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                
                <!-- Datapoint dropdown and Add button -->
                <div class="flex gap-2 mb-3">
                    <select id="ct-datapoint-select" class="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm">
                        <option value="">Select Datapoint...</option>
                        <option value="ct_left_position">ct_left - position</option>
                        <option value="ct_left_speed">ct_left - speed</option>
                        <option value="ct_left_current">ct_left - current</option>
                        <option value="ct_right_position">ct_right - position</option>
                        <option value="ct_right_speed">ct_right - speed</option>
                        <option value="ct_right_current">ct_right - current</option>
                        <option value="ct_left_temperature">ct_left - temperature</option>
                        <option value="ct_right_temperature">ct_right - temperature</option>
                    </select>
                    <button type="button" class="px-4 py-2 bg-cyan-600 text-white rounded-lg text-sm hover:bg-cyan-700 transition-colors" onclick="window.addDatapoint('ct')">
                        <i class="fa-solid fa-plus mr-1"></i> Add
                    </button>
                </div>
                
                <!-- List of added datapoints -->
                <div id="ct-datapoints-list" class="space-y-2 mt-3">
                    ${renderDatapointsList(currentGroupData.ct.datapoints, 'ct')}
                </div>
            </div>
            
            <!-- LT Group -->
            <div class="border border-emerald-200 rounded-xl p-4 bg-emerald-50/20">
                <div class="flex items-center justify-between mb-4">
                    <div class="flex items-center gap-2">
                        <div class="w-6 h-6 bg-emerald-100 rounded-full flex items-center justify-center">
                            <i class="fa-solid fa-arrows-up-down text-emerald-600 text-xs"></i>
                        </div>
                        <span class="font-semibold text-sm text-emerald-800">LT Group</span>
                    </div>
                    <label class="toggle-switch scale-75">
                        <input type="checkbox" id="lt-enabled" ${currentGroupData.lt.enabled ? 'checked' : ''} onchange="window.toggleGroup('lt', this.checked)">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                
                <!-- Datapoint dropdown and Add button -->
                <div class="flex gap-2 mb-3">
                    <select id="lt-datapoint-select" class="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm">
                        <option value="">Select Datapoint...</option>
                        <option value="lt_forward_speed">lt_forward - speed</option>
                        <option value="lt_forward_position">lt_forward - position</option>
                        <option value="lt_forward_current">lt_forward - current</option>
                        <option value="lt_backward_speed">lt_backward - speed</option>
                        <option value="lt_backward_position">lt_backward - position</option>
                        <option value="lt_backward_current">lt_backward - current</option>
                        <option value="lt_forward_temperature">lt_forward - temperature</option>
                        <option value="lt_backward_temperature">lt_backward - temperature</option>
                    </select>
                    <button type="button" class="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm hover:bg-emerald-700 transition-colors" onclick="window.addDatapoint('lt')">
                        <i class="fa-solid fa-plus mr-1"></i> Add
                    </button>
                </div>
                
                <!-- List of added datapoints -->
                <div id="lt-datapoints-list" class="space-y-2 mt-3">
                    ${renderDatapointsList(currentGroupData.lt.datapoints, 'lt')}
                </div>
            </div>
            
            <!-- Back button -->
            <div class="flex justify-center pt-2">
                <button type="button" class="text-sm text-primary hover:text-primaryHover" onclick="window.clearRuleEditor()">
                    <i class="fa-solid fa-arrow-left mr-1"></i> Back to Rule Selection
                </button>
            </div>
        </div>`;
    }

    // New function to create a group rule
    window.createGroupRule = function() {
        // Reset group data for new group rule
        currentGroupData = {
            hoist: { enabled: true, datapoints: [] },
            ct: { enabled: true, datapoints: [] },
            lt: { enabled: true, datapoints: [] }
        };
        
        // Create a temporary rule object for the editor
        var tempRule = {
            id: 'temp',
            name: '',
            description: '',
            priority: 'medium',
            ruleType: 'group',
            groups: {
                hoist: { enabled: true, datapoints: [] },
                ct: { enabled: true, datapoints: [] },
                lt: { enabled: true, datapoints: [] }
            }
        };
        
        document.getElementById('wizard-content').innerHTML = renderGroupRuleEditor(tempRule);
        document.getElementById('rule-editor-title').textContent = 'Create New Group Rule';
    };

    // New function to create an emergency rule
    window.createEmergencyRule = function() {
        // Reset group data for emergency rule
        currentGroupData = {
            hoist: { enabled: true, datapoints: [] },
            ct: { enabled: false, datapoints: [] },
            lt: { enabled: false, datapoints: [] }
        };
        
        // Create a temporary rule object for the editor
        var tempRule = {
            id: 'temp',
            name: '',
            description: '',
            priority: 'critical',
            ruleType: 'emergency',
            overloadThreshold: 90
        };
        
        document.getElementById('wizard-content').innerHTML = renderEmergencyRuleEditor(tempRule);
        document.getElementById('rule-editor-title').textContent = 'Create New Emergency Rule';
    };

    // New function to clear editor (go back to empty state)
    window.clearRuleEditor = function() {
        if (confirm('Discard unsaved changes?')) {
            selectedRuleId = null;
            renderRulesList();
            
            // Reset current group data
            currentGroupData = {
                hoist: { enabled: true, datapoints: [] },
                ct: { enabled: true, datapoints: [] },
                lt: { enabled: true, datapoints: [] }
            };
            
            document.getElementById('rule-editor-title').textContent = 'Create New Rule';
            document.getElementById('rule-id-display').textContent = 'RULE-NEW';
            document.getElementById('rule-status-toggle').checked = true;
            
            // Show empty state
            document.getElementById('wizard-content').innerHTML = `<div class="text-center py-12 text-slate-400">
                <i class="fa-solid fa-arrow-left text-3xl mb-3 block"></i>
                <p>Select a rule type from the dropdown above to get started</p>
            </div>`;
        }
    };

    // New function to toggle group enabled state
    window.toggleGroup = function(group, enabled) {
        if (currentGroupData[group]) {
            currentGroupData[group].enabled = enabled;
        }
    };

    // Generic function to add datapoint to any group
    window.addDatapoint = function(group) {
        const select = document.getElementById(`${group}-datapoint-select`);
        if (!select) {
            showNotification('Could not find dropdown', 'error');
            return;
        }
        
        const selectedValue = select.value;
        
        if (!selectedValue) {
            showNotification('Please select a datapoint', 'warning');
            return;
        }
        
        // Check if datapoint already exists
        if (currentGroupData[group].datapoints.includes(selectedValue)) {
            showNotification('This datapoint is already added', 'warning');
            return;
        }
        
        // Add to current group data
        currentGroupData[group].datapoints.push(selectedValue);
        
        // Update the list display
        const listElement = document.getElementById(`${group}-datapoints-list`);
        if (listElement) {
            listElement.innerHTML = renderDatapointsList(currentGroupData[group].datapoints, group);
        }
        
        // Reset select
        select.value = '';
        
        showNotification('Datapoint added successfully', 'success');
    };

    // Generic function to remove datapoint from any group
    window.removeDatapoint = function(group, index) {
        // Remove from current group data
        currentGroupData[group].datapoints.splice(index, 1);
        
        // Update the list display
        const listElement = document.getElementById(`${group}-datapoints-list`);
        if (listElement) {
            listElement.innerHTML = renderDatapointsList(currentGroupData[group].datapoints, group);
        }
        
        showNotification('Datapoint removed', 'info');
    };

    function updateStatistics() {
        var total   = rules.length;
        var active  = rules.filter(function(r){ return r.enabled; }).length;
        var triggers = rules.reduce(function(sum, r){ return sum + (r.triggerCount || 0); }, 0);
        
        // Update stats if elements exist
        var totalEl = document.getElementById('total-rules');
        var activeEl = document.getElementById('active-rules');
        var triggersEl = document.getElementById('total-triggers');
        
        if (totalEl) totalEl.textContent = total;
        if (activeEl) activeEl.textContent = active;
        if (triggersEl) triggersEl.textContent = triggers;
    }

    // ========== WINDOW ACTIONS ==========
    window.selectRule = function(id) {
        selectedRuleId = id;
        renderRulesList();
        renderRuleEditor(id);
    };

    window.setPriority = function(ruleId, priority) {
        // For new rules (not saved yet), we just update the UI
        if (ruleId === 'new') {
            showNotification(`Priority set to ${priority}`, 'success');
            return;
        }
        
        var rule = rules.find(function(r){ return r.id === ruleId; });
        if (rule) { 
            rule.priority = priority; 
            renderRulesList(); 
            renderRuleEditor(ruleId);
            showNotification(`Priority set to ${priority}`, 'success');
        }
    };

    window.startCreatingNewRule = function() {
        selectedRuleId = null;
        renderRulesList();
        renderRuleEditor(null);
        showNotification('Creating new rule', 'info');
    };

    window.saveRule = function() {
        // Check what type of editor we're in
        const isGroupRule = document.getElementById('hoist-datapoint-select') !== null;
        const isEmergencyRule = document.getElementById('overload-threshold') !== null;
        
        if (!isGroupRule && !isEmergencyRule) {
            showNotification('Please create a rule first', 'warning');
            return;
        }
        
        if (isEmergencyRule) {
            // Get current enabled states
            const hoistEnabled = document.getElementById('hoist-enabled');
            
            currentGroupData.hoist.enabled = hoistEnabled ? hoistEnabled.checked : false;
            
            // Validate at least one datapoint
            if (currentGroupData.hoist.datapoints.length === 0) {
                showNotification('At least one HOIST datapoint is required', 'warning');
                return;
            }
            
            // Get overload threshold
            const overloadThreshold = document.getElementById('overload-threshold')?.value || 90;
            
            // Save emergency rule
            var emergencyRuleData = {
                id: selectedRuleId || 'emergency_' + Date.now(),
                name: document.getElementById('rule-name-input')?.value || 'New Emergency Rule',
                enabled: document.getElementById('rule-status-toggle')?.checked || true,
                ruleType: 'emergency',
                priority: 'critical',
                description: document.getElementById('rule-desc-input')?.value || 'Emergency overload protection rule',
                overloadThreshold: parseInt(overloadThreshold),
                groups: {
                    hoist: {
                        enabled: currentGroupData.hoist.enabled,
                        datapoints: currentGroupData.hoist.datapoints || []
                    }
                },
                triggerCount: 0,
                lastTriggered: null,
                created: new Date().toISOString()
            };
            
            if (selectedRuleId) {
                const index = rules.findIndex(r => r.id === selectedRuleId);
                if (index !== -1) {
                    rules[index] = { ...rules[index], ...emergencyRuleData };
                }
            } else {
                rules.push(emergencyRuleData);
                selectedRuleId = emergencyRuleData.id;
            }
        } else if (isGroupRule) {
            // Get current enabled states
            const hoistEnabled = document.getElementById('hoist-enabled');
            const ctEnabled = document.getElementById('ct-enabled');
            const ltEnabled = document.getElementById('lt-enabled');
            
            currentGroupData.hoist.enabled = hoistEnabled ? hoistEnabled.checked : false;
            currentGroupData.ct.enabled = ctEnabled ? ctEnabled.checked : false;
            currentGroupData.lt.enabled = ltEnabled ? ltEnabled.checked : false;
            
            // Validate at least one group has datapoints if enabled
            const hasData = (currentGroupData.hoist.enabled && currentGroupData.hoist.datapoints.length > 0) ||
                           (currentGroupData.ct.enabled && currentGroupData.ct.datapoints.length > 0) ||
                           (currentGroupData.lt.enabled && currentGroupData.lt.datapoints.length > 0);
            
            if (!hasData) {
                showNotification('At least one enabled group must have datapoints', 'warning');
                return;
            }
            
            // Save group rule
            var groupRuleData = {
                id: selectedRuleId || 'group_' + Date.now(),
                name: document.getElementById('rule-name-input')?.value || 'New Group Rule',
                enabled: document.getElementById('rule-status-toggle')?.checked || true,
                ruleType: 'group',
                priority: 'medium',
                description: document.getElementById('rule-desc-input')?.value || '',
                groups: {
                    hoist: {
                        enabled: currentGroupData.hoist.enabled,
                        datapoints: currentGroupData.hoist.datapoints || []
                    },
                    ct: {
                        enabled: currentGroupData.ct.enabled,
                        datapoints: currentGroupData.ct.datapoints || []
                    },
                    lt: {
                        enabled: currentGroupData.lt.enabled,
                        datapoints: currentGroupData.lt.datapoints || []
                    }
                },
                triggerCount: 0,
                lastTriggered: null,
                created: new Date().toISOString()
            };
            
            if (selectedRuleId) {
                const index = rules.findIndex(r => r.id === selectedRuleId);
                if (index !== -1) {
                    rules[index] = { ...rules[index], ...groupRuleData };
                }
            } else {
                rules.push(groupRuleData);
                selectedRuleId = groupRuleData.id;
            }
        }
        
        renderRulesList();
        renderRuleEditor(selectedRuleId);
        showNotification('Rule saved successfully', 'success');
    };

    window.testRule = function() {
        showNotification('Testing rule...', 'info');
        setTimeout(function(){ showNotification('Test alert triggered!', 'success'); }, 1500);
    };

    window.showFilterModal = function() { 
        showNotification('Filter — coming soon', 'info'); 
    };
    
    window.toggleSortOrder = function() { 
        rules.reverse(); 
        renderRulesList(); 
        showNotification('Rules reordered', 'success');
    };
    
    window.refreshRules = function() { 
        renderRulesList(); 
        showNotification('Rules refreshed', 'success'); 
    };
    
    window.showImportModal = function() { 
        showNotification('Import Rules — coming soon', 'info'); 
    };
    
    window.goToStep = function(n) { 
        showNotification(`Step ${n} — coming soon`, 'info'); 
    };

    // ========== CLEANUP ==========
    function cleanupRules() {
        selectedRuleId = null;
        console.log('Rules cleanup complete');
    }

    // ========== INIT ==========
    window.initRules = function() {
        console.log('Initializing Rules Engine');
        renderRulesList();
        renderRuleEditor(null);
        showNotification('Rules page loaded', 'info');
    };

    window.cleanupRules = cleanupRules;
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', window.initRules);
    } else {
        window.initRules();
    }
    
    window.addEventListener('beforeunload', cleanupRules);
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { initRules: window.initRules, cleanupRules: window.cleanupRules };
}