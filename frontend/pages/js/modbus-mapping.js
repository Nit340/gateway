// modbus-mapping.js — Full version with group dropdown
'use strict';

let _devices = [];
let _tags    = [];
let _selectedDeviceId   = null;
let _selectedDeviceData = null;
let _editingTagId       = null;

// Pagination variables
let _groups = [];
let _browserCurrentPage = 1;
let _browserPageSize = 12;
let _browserTotalPages = 1;
let _selectedGroupColor = 'blue';

// ─── INIT ────────────────────────────────────────────────────────────────────

function initializeModbusMapping() {
    console.log('Initializing Modbus Mapping');
    _loadData();
    _bindStaticListeners();
}

// ─── DATA ────────────────────────────────────────────────────────────────────

async function _loadData() {
    try {
        console.log('Loading modbus mapping data...');
        const [devResp, tagResp, grpResp] = await Promise.all([
            fetch('/api/datapoints/devices'),
            fetch('/api/datapoints'),
            fetch('/api/tag-groups')
        ]);
        
        if (!devResp.ok) {
            console.error('Failed to load devices:', devResp.status);
        }
        const devData = await devResp.json();
        _devices = devData.devices || [];
        console.log('Loaded devices:', _devices);

        if (!tagResp.ok) {
            console.error('Failed to load tags:', tagResp.status);
        }
        const tagData = await tagResp.json();
        _tags = Array.isArray(tagData) ? tagData : (tagData.tags || []);
        console.log('Loaded tags:', _tags);

        const grpData = await grpResp.json();
        _groups = grpData.groups || [];
        console.log('Loaded groups:', _groups);

        // Populate group dropdowns
        _populateGroupDropdowns();

        _renderTagsTable();
        _renderTagsBrowser();
        _updateDropdownFilters();
        _renderGroupsPanel();
        _renderPaginationControls();
    } catch (err) {
        console.error('Failed to load data:', err);
        _toast('Failed to load data', 'error');
    }
}

// ─── POPULATE GROUP DROPDOWNS ─────────────────────────────────────────────────

function _populateGroupDropdowns() {
    // Populate group dropdown in add modal
    const mbGroupSelect = document.getElementById('mbGroup');
    if (mbGroupSelect) {
        const currentValue = mbGroupSelect.value;
        mbGroupSelect.innerHTML = '<option value="">No Group</option>';
        (_groups || []).forEach(g => {
            const option = document.createElement('option');
            option.value = g.name; // Use group name as value
            option.textContent = g.name;
            // Add background color based on group color
            if (g.color) {
                option.style.backgroundColor = g.color === 'blue' ? '#EFF6FF' : 
                                              g.color === 'green' ? '#F0FDF4' :
                                              g.color === 'purple' ? '#FAF5FF' :
                                              g.color === 'orange' ? '#FFF7ED' :
                                              g.color === 'red' ? '#FEF2F2' : '';
            }
            mbGroupSelect.appendChild(option);
        });
        mbGroupSelect.value = currentValue || '';
    }

    // Populate group dropdown in edit modal
    const editMbGroup = document.getElementById('editMbGroup');
    if (editMbGroup) {
        const currentValue = editMbGroup.value;
        editMbGroup.innerHTML = '<option value="">No Group</option>';
        (_groups || []).forEach(g => {
            const option = document.createElement('option');
            option.value = g.name;
            option.textContent = g.name;
            if (g.color) {
                option.style.backgroundColor = g.color === 'blue' ? '#EFF6FF' : 
                                              g.color === 'green' ? '#F0FDF4' :
                                              g.color === 'purple' ? '#FAF5FF' :
                                              g.color === 'orange' ? '#FFF7ED' :
                                              g.color === 'red' ? '#FEF2F2' : '';
            }
            editMbGroup.appendChild(option);
        });
        editMbGroup.value = currentValue || '';
    }
}

// ─── RENDER: TABLE ───────────────────────────────────────────────────────────

function _renderTagsTable() {
    const tbody = document.getElementById('mappingTableBody');
    const count = document.getElementById('mappingCount');
    if (!tbody) return;

    const devId = document.getElementById('deviceFilter')?.value || '';
    const grpId = document.getElementById('groupFilter')?.value || '';
    let rows = _tags || [];
    if (devId) rows = rows.filter(t => String(t.device_id) === String(devId));
    if (grpId) rows = rows.filter(t => String(t.group_id) === String(grpId));

    if (count) count.textContent = rows.length;

    if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="12" class="text-center py-12 text-slate-400">
            <i class="fa-solid fa-tags text-3xl mb-3 block"></i>
            <p class="text-sm">No tags yet. Click <strong>Add Tag</strong> to get started.</p>
        </td></tr>`;
        return;
    }

    tbody.innerHTML = '';
    rows.forEach(tag => {
        // Determine if it's a load cell tag (check protocol or type)
        const isLC = tag.protocol === 'loadcell' || tag.type === 'loadcell';
        const tr = document.createElement('tr');
        
        // Use type-prefixed ID to avoid collisions between loadcell and modbus IDs
        const tagType = isLC ? 'loadcell' : 'modbus';
        tr.id = `tag-row-${tagType}-${tag.id}`;
        tr.className = 'tag-table-row';
        tr.dataset.tagId = tag.id;
        tr.dataset.tagType = tagType;
        
        // Get values with fallbacks
        const deviceName = tag.device_name || tag.deviceName || '—';
        const deviceType = tag.device_type || tag.protocol || (isLC ? 'Load Cell' : 'Modbus');
        const tagName = tag.tag_name || tag.name || '—';
        const dataType = tag.data_type || tag.dataType || '—';
        const unit = tag.unit || '—';
        const address = tag.register_address !== undefined ? tag.register_address : (tag.address !== undefined ? tag.address : '—');
        const registerType = tag.register_type || tag.registerType || '—';
        // Format register type for display (capitalize first letter)
        const registerTypeDisplay = registerType.charAt(0).toUpperCase() + registerType.slice(1);
        const slaveId = tag.slave_id !== undefined ? tag.slave_id : (tag.slaveId !== undefined ? tag.slaveId : 1);
        const groupName = tag.group_name || tag.group || '—';
        const enabled = tag.enabled !== undefined ? tag.enabled : true;
        const writable = tag.writable !== undefined ? tag.writable : false;

        if (isLC) {
            tr.innerHTML = `
                <td class="font-medium text-slate-900">${_esc(deviceName)}</td>
                <td><span class="protocol-badge loadcell">Load Cell</span></td>
                <td class="font-mono text-xs text-slate-900">${_esc(tagName)}</td>
                <td class="text-slate-300">—</td>
                <td class="text-slate-300">—</td>
                <td class="text-slate-300">—</td>
                <td class="text-slate-300">—</td>
                <td class="text-slate-600 text-xs">${_esc(unit)}</td>
                <td class="text-slate-300">—</td>
                <td class="text-slate-300">—</td>
                <td><span class="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">Enabled</span></td>
                <td class="text-right whitespace-nowrap">
                    <button class="text-slate-400 hover:text-slate-600 mr-2" onclick="editTag(${tag.id}, 'loadcell')" title="Edit Unit Only">
                        <i class="fa-solid fa-pencil text-sm"></i>
                    </button>
                </td>`;
        } else {
            tr.innerHTML = `
                <td class="font-medium text-slate-900">${_esc(deviceName)}</td>
                <td><span class="protocol-badge ${tag.device_type === 'tcp' ? 'modbus-tcp' : 'modbus-rtu'}">${_esc(deviceType)}</span></td>
                <td class="font-mono text-xs text-slate-900">${_esc(tagName)}</td>
                <td class="text-slate-600 text-xs text-center">${slaveId}</td>
                <td class="text-slate-600 font-mono text-xs">${address}</td>
                <td class="text-slate-600 text-xs">${_esc(registerTypeDisplay)}</td>
                <td class="text-slate-600 text-xs">${_esc(dataType)}</td>
                <td class="text-slate-600 text-xs">${_esc(unit)}</td>
                <td class="text-slate-600 text-xs">${_esc(groupName)}</td>
                <td><span class="writable-badge ${writable}">${writable ? 'Yes' : 'No'}</span></td>
                <td><span class="px-2 py-0.5 rounded-full text-xs font-medium ${enabled ? 'bg-green-100 text-green-800' : 'bg-slate-100 text-slate-600'}">${enabled ? 'Enabled' : 'Disabled'}</span></td>
                <td class="text-right whitespace-nowrap">
                    <button class="text-blue-600 hover:text-blue-800 mr-2" onclick="editTag(${tag.id}, 'modbus')" title="Edit">
                        <i class="fa-solid fa-pencil text-sm"></i>
                    </button>
                    <button class="text-red-500 hover:text-red-700" onclick="deleteTag(${tag.id}, 'modbus')" title="Delete">
                        <i class="fa-solid fa-trash text-sm"></i>
                    </button>
                </td>`;
        }
        tbody.appendChild(tr);
    });
}

// ─── RENDER: BROWSER WITH PAGINATION ─────────────────────────────────────────

function _renderTagsBrowser() {
    const container  = document.getElementById('tagsList');
    const emptyState = document.getElementById('tagsEmptyState');
    if (!container) return;

    const q    = (document.getElementById('tagSearch')?.value || '').toLowerCase();
    const devId = document.getElementById('tagDeviceFilter')?.value || '';
    const grpId = document.getElementById('tagGroupFilter')?.value || '';
    let rows = _tags || [];
    if (devId) rows = rows.filter(t => String(t.device_id) === String(devId));
    if (grpId) rows = rows.filter(t => String(t.group_id) === String(grpId));
    
    if (q) {
        rows = rows.filter(t => {
            const tagName = (t.tag_name || t.name || '').toLowerCase();
            const devName = (t.device_name || t.deviceName || '').toLowerCase();
            const desc = (t.description || '').toLowerCase();
            return tagName.includes(q) || devName.includes(q) || desc.includes(q);
        });
    }

    // Calculate pagination
    _browserTotalPages = Math.max(1, Math.ceil(rows.length / _browserPageSize));
    _browserCurrentPage = Math.min(_browserCurrentPage, _browserTotalPages);
    
    const startIndex = (_browserCurrentPage - 1) * _browserPageSize;
    const endIndex = Math.min(startIndex + _browserPageSize, rows.length);
    const paginatedRows = rows.slice(startIndex, endIndex);

    container.innerHTML = '';
    if (!rows.length) { 
        emptyState?.classList.remove('hidden'); 
        _renderPaginationControls(0);
        return; 
    }
    emptyState?.classList.add('hidden');

    paginatedRows.forEach(tag => {
        const isLC = tag.protocol === 'loadcell' || tag.type === 'loadcell';
        const d = document.createElement('div');
        d.className = 'tag-card';
        d.dataset.tagId = tag.id;
        d.dataset.tagType = isLC ? 'loadcell' : 'modbus';
        
        // Use click event listener
        d.addEventListener('click', function(e) {
            e.stopPropagation();
            const tagType = isLC ? 'loadcell' : 'modbus';
            console.log(`Tag card clicked: ID ${tag.id}, Type: ${tagType}, Name: ${tag.tag_name || tag.name}`);
            highlightTagRow(tag.id, tagType);
        });
        
        d.style.cursor = 'pointer';
        
        // Get values with fallbacks
        const tagName = tag.tag_name || tag.name || 'Unnamed';
        const deviceName = tag.device_name || tag.deviceName || '—';
        const dataType = isLC ? null : (tag.data_type || tag.dataType || '—');
        const unit = tag.unit || '—';
        const address = tag.register_address !== undefined ? tag.register_address : (tag.address !== undefined ? tag.address : null);
        const registerType = tag.register_type || tag.registerType || null;
        const registerTypeDisplay = registerType ? registerType.charAt(0).toUpperCase() + registerType.slice(1) : null;
        const slaveId = tag.slave_id !== undefined ? tag.slave_id : (tag.slaveId !== undefined ? tag.slaveId : 1);
        const groupName = tag.group_name || tag.group || null;
        const writable = tag.writable !== undefined ? tag.writable : false;
        const retryCount = tag.retry_count || tag.retryCount || 1;
        const timeoutMs = tag.timeout_ms || tag.timeoutMs || 100;
        const registerCount = tag.register_count || tag.registerCount || 1;
        
        let badgeClass = 'modbus-tcp';
        if (isLC) badgeClass = 'loadcell';
        else if (tag.device_type === 'rtu') badgeClass = 'modbus-rtu';
        
        let html = `
            <div class="tag-card-header">
                <div class="tag-card-name">${_esc(tagName)}</div>
                <span class="protocol-badge ${badgeClass}">${isLC ? 'LOADCELL' : 'MODBUS'}</span>
            </div>
            <div class="tag-card-body">
                <div class="tag-card-row">
                    <span>Device</span>
                    <span class="font-medium text-slate-700">${_esc(deviceName)}</span>
                </div>`;
        
        if (!isLC) {
            html += `
                <div class="tag-card-row">
                    <span>Slave ID</span>
                    <span class="font-mono">${slaveId}</span>
                </div>
                <div class="tag-card-row">
                    <span>Address/Type</span>
                    <span class="font-mono">${address} (${registerTypeDisplay})</span>
                </div>
                <div class="tag-card-row">
                    <span>Data Type</span>
                    <span>${_esc(dataType)}</span>
                </div>
                <div class="tag-card-row">
                    <span>Scale/Offset</span>
                    <span>${tag.scale || tag.scale_factor || 1.0} / ${tag.offset || 0.0}</span>
                </div>
                <div class="tag-card-row">
                    <span>Count/Retry</span>
                    <span>${registerCount} / ${retryCount}</span>
                </div>
                <div class="tag-card-row">
                    <span>Timeout/Writable</span>
                    <span>${timeoutMs}ms / ${writable ? 'Yes' : 'No'}</span>
                </div>`;
        } else {
            html += `
                <div class="tag-card-row">
                    <span>Type</span>
                    <span>Load Cell</span>
                </div>`;
        }
        
        if (unit && unit !== '—') {
            html += `
                <div class="tag-card-row">
                    <span>Unit</span>
                    <span>${_esc(unit)}</span>
                </div>`;
        }
        
        if (groupName && groupName !== '—') {
            html += `
                <div class="tag-card-row">
                    <span>Group</span>
                    <span class="inline-flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-${_groupColor(groupName)}-500"></span>${_esc(groupName)}</span>
                </div>`;
        }
        
        if (tag.description) {
            html += `
                <div class="tag-card-row text-slate-500 italic text-xs">
                    <span>${_esc(tag.description)}</span>
                </div>`;
        }
        
        html += `</div>`;
        d.innerHTML = html;
        container.appendChild(d);
    });

    _renderPaginationControls(rows.length);
}

// ─── PAGINATION CONTROLS ────────────────────────────────────────────────────

function _renderPaginationControls(totalItems = 0) {
    let paginationContainer = document.getElementById('browserPagination');
    const browserSection = document.getElementById('tagsList')?.parentElement;
    
    if (!browserSection) return;
    
    if (!paginationContainer) {
        paginationContainer = document.createElement('div');
        paginationContainer.id = 'browserPagination';
        paginationContainer.className = 'flex items-center justify-between mt-6 pt-4 border-t border-slate-200';
        browserSection.appendChild(paginationContainer);
    }

    if (totalItems === 0) {
        paginationContainer.innerHTML = '';
        return;
    }

    const startItem = (_browserCurrentPage - 1) * _browserPageSize + 1;
    const endItem = Math.min(_browserCurrentPage * _browserPageSize, totalItems);

    paginationContainer.innerHTML = `
        <div class="text-sm text-slate-500">
            Showing <span class="font-medium text-slate-900">${startItem}-${endItem}</span> of <span class="font-medium text-slate-900">${totalItems}</span> tags
        </div>
        <div class="flex items-center space-x-2">
            <button 
                class="px-3 py-1.5 text-sm border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors ${_browserCurrentPage === 1 ? 'opacity-50 cursor-not-allowed' : ''}"
                ${_browserCurrentPage === 1 ? 'disabled' : ''}
                onclick="changeBrowserPage(${_browserCurrentPage - 1})">
                <i class="fa-solid fa-chevron-left text-xs"></i>
            </button>
            <span class="text-sm text-slate-600 px-3">
                Page ${_browserCurrentPage} of ${_browserTotalPages}
            </span>
            <button 
                class="px-3 py-1.5 text-sm border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors ${_browserCurrentPage === _browserTotalPages ? 'opacity-50 cursor-not-allowed' : ''}"
                ${_browserCurrentPage === _browserTotalPages ? 'disabled' : ''}
                onclick="changeBrowserPage(${_browserCurrentPage + 1})">
                <i class="fa-solid fa-chevron-right text-xs"></i>
            </button>
        </div>
    `;
}

// ─── PAGE CHANGE FUNCTION ───────────────────────────────────────────────────

function changeBrowserPage(newPage) {
    if (newPage < 1 || newPage > _browserTotalPages) return;
    _browserCurrentPage = newPage;
    _renderTagsBrowser();
}

// ─── HIGHLIGHT TAG ROW ──────────────────────────────────────────────────────

function highlightTagRow(tagId, tagType) {
    console.log(`Attempting to highlight tag ID: ${tagId}, type: ${tagType}`);
    
    // Remove highlight from all rows
    document.querySelectorAll('.tag-table-row').forEach(row => {
        row.classList.remove('bg-yellow-100', 'border-l-4', 'border-yellow-400', 'font-bold');
        row.style.backgroundColor = '';
    });

    // Find the row using type-prefixed ID (avoids loadcell/modbus ID collisions)
    let targetRow = tagType ? document.getElementById(`tag-row-${tagType}-${tagId}`) : null;
    
    // Fallback: match by tagId + tagType dataset
    if (!targetRow && tagType) {
        targetRow = Array.from(document.querySelectorAll('.tag-table-row')).find(row =>
            String(row.dataset.tagId) === String(tagId) && row.dataset.tagType === tagType
        );
    }
    
    // Last resort: match by tagId only
    if (!targetRow) {
        targetRow = Array.from(document.querySelectorAll('.tag-table-row')).find(row => 
            String(row.dataset.tagId) === String(tagId)
        );
    }

    if (targetRow) {
        console.log(`Found row for tag ID ${tagId} (${tagType}), moving to top and highlighting`);
        
        // Move this row to the top of its tbody
        const tbody = targetRow.parentElement;
        if (tbody && tbody.firstChild !== targetRow) {
            tbody.insertBefore(targetRow, tbody.firstChild);
        }
        
        // Apply highlight
        targetRow.classList.add('bg-yellow-100', 'border-l-4', 'border-yellow-400', 'font-bold');
        
        // Scroll the mapping section into view, then the row
        const mappingSection = document.querySelector('#mappingTableBody')?.closest('section');
        if (mappingSection) {
            mappingSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        setTimeout(() => {
            targetRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 300);
        
        // Find tag info and toast
        const tag = (_tags || []).find(t =>
            String(t.id) === String(tagId) &&
            (tagType ? ((tagType === 'loadcell') === (t.protocol === 'loadcell' || t.type === 'loadcell')) : true)
        );
        if (tag) {
            const tagName = tag.tag_name || tag.name || 'Unknown';
            const isLC = tag.protocol === 'loadcell' || tag.type === 'loadcell';
            _toast(`Mapped: ${tagName} (${isLC ? 'Load Cell' : 'Modbus'})`, 'success');
        }
    } else {
        console.error(`Could not find table row for tag ID: ${tagId}`);
        _toast('Tag not visible in current table view', 'info');
    }
}

// ─── DROPDOWN FILTERS ────────────────────────────────────────────────────────

function _updateDropdownFilters() {
    ['deviceFilter', 'tagDeviceFilter'].forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        const cur = sel.value;
        sel.innerHTML = '<option value="">All Devices</option>';
        (_devices || []).forEach(d => {
            const o = document.createElement('option');
            o.value = d.id;
            o.textContent = `${d.name} (${_pLabel(d.protocol)})`;
            sel.appendChild(o);
        });
        sel.value = cur;
    });

    // Group filter dropdowns
    ['groupFilter', 'tagGroupFilter'].forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        const cur = sel.value;
        sel.innerHTML = '<option value="">All Groups</option>';
        (_groups || []).forEach(g => {
            const o = document.createElement('option');
            o.value = g.id;
            o.textContent = g.name;
            sel.appendChild(o);
        });
        sel.value = cur;
    });

    // Also populate the modal group dropdowns
    _populateGroupDropdowns();
}

// ─── EVENT LISTENERS ─────────────────────────────────────────────────────────

function _bindStaticListeners() {
    document.getElementById('addMappingBtn')?.addEventListener('click', () => _openAddTagModal(null));
    document.getElementById('deviceFilter')?.addEventListener('change', _renderTagsTable);
    document.getElementById('groupFilter')?.addEventListener('change', _renderTagsTable);
    document.getElementById('tagSearch')?.addEventListener('input', () => {
        _browserCurrentPage = 1;
        _renderTagsBrowser();
    });
    document.getElementById('tagDeviceFilter')?.addEventListener('change', () => {
        _browserCurrentPage = 1;
        _renderTagsBrowser();
    });
    document.getElementById('tagGroupFilter')?.addEventListener('change', () => {
        _browserCurrentPage = 1;
        _renderTagsBrowser();
    });

    // Group management buttons
    document.getElementById('addTagGroupBtn')?.addEventListener('click', _openAddGroupModal);
    document.getElementById('closeAddGroupModal')?.addEventListener('click', _closeAddGroupModal);
    document.getElementById('cancelAddGroupBtn')?.addEventListener('click', _closeAddGroupModal);
    document.getElementById('saveTagGroupBtn')?.addEventListener('click', _saveTagGroup);

    // Add tag modal
    document.getElementById('closeAddTagModal')?.addEventListener('click', _closeAddTagModal);
    document.getElementById('cancelAddTag')?.addEventListener('click', _closeAddTagModal);
    document.getElementById('proceedToTagForm')?.addEventListener('click', _proceedToTagForm);
    document.getElementById('modbusFormBack')?.addEventListener('click', () => _showStep('stepDeviceSelect'));
    document.getElementById('lcFormBack')?.addEventListener('click', () => _showStep('stepDeviceSelect'));
    document.getElementById('modbusFormCancel')?.addEventListener('click', _closeAddTagModal);
    document.getElementById('lcFormClose')?.addEventListener('click', _closeAddTagModal);
    document.getElementById('modbusTagForm')?.addEventListener('submit', _handleModbusCreate);
    document.getElementById('addTagModal')?.addEventListener('click', e => { if (e.target.id === 'addTagModal') _closeAddTagModal(); });

    // Edit modal (modbus)
    document.getElementById('closeEditModbusModal')?.addEventListener('click', _closeEditModbus);
    document.getElementById('editModbusCancel')?.addEventListener('click', _closeEditModbus);
    document.getElementById('editModbusForm')?.addEventListener('submit', _handleModbusEdit);
    document.getElementById('editModbusModal')?.addEventListener('click', e => { if (e.target.id === 'editModbusModal') _closeEditModbus(); });

    // CSV
    document.getElementById('importCSVBtn')?.addEventListener('click', importCSV);
    document.getElementById('exportCSVBtn')?.addEventListener('click', exportCSV);

    // Save Configuration → pipeline modbus service
    document.getElementById('saveModbusConfigBtn')?.addEventListener('click', saveModbusConfig);

    // Group color picker
    document.querySelectorAll('[data-group-color]').forEach(btn => {
        btn.addEventListener('click', function() {
            _selectedGroupColor = this.dataset.groupColor;
            document.querySelectorAll('[data-group-color]').forEach(b => b.classList.remove('ring-2', 'ring-offset-1'));
            this.classList.add('ring-2', 'ring-offset-1');
        });
    });

    // Escape
    document.addEventListener('keydown', e => {
        if (e.key !== 'Escape') return;
        if (_vis('addTagModal')) _closeAddTagModal();
        if (_vis('editModbusModal')) _closeEditModbus();
    });
}

// ─── ADD TAG MODAL ───────────────────────────────────────────────────────────

function _openAddTagModal(preDevId) {
    _selectedDeviceId = null;
    _selectedDeviceData = null;

    // Clear form
    _clearModbusForm('mb');

    // Reset proceed btn
    const btn = document.getElementById('proceedToTagForm');
    if (btn) {
        btn.disabled = true;
        btn.style.opacity = '0.4';
        btn.style.cursor = 'not-allowed';
    }

    // Hide preview
    document.getElementById('modalSelectedPreview')?.classList.add('hidden');

    _buildModalDeviceList();
    _showStep('stepDeviceSelect');

    if (preDevId != null) {
        setTimeout(() => {
            const item = document.querySelector(`[data-modal-device-id="${preDevId}"]`);
            if (item) item.click();
        }, 20);
    }

    _showModal('addTagModal');
}

function _buildModalDeviceList() {
    const list = document.getElementById('modalDeviceList');
    if (!list) return;
    list.innerHTML = '';

    if (!_devices || !_devices.length) {
        list.innerHTML = '<p class="text-sm text-slate-400 text-center py-6">No devices found. Add a device first.</p>';
        return;
    }

    _devices.forEach(dev => {
        const isLC = dev.protocol === 'loadcell';
        const cnt = (_tags || []).filter(t => String(t.device_id) === String(dev.id)).length;
        const el = document.createElement('div');
        el.className = 'modal-device-item';
        el.dataset.modalDeviceId = dev.id;
        el.innerHTML = `
            <div class="flex items-center gap-3 min-w-0 flex-1">
                <i class="fa-solid ${isLC ? 'fa-scale-balanced text-green-600' : 'fa-ethernet text-blue-600'} text-sm w-4 flex-shrink-0"></i>
                <div class="min-w-0">
                    <div class="text-sm font-semibold text-slate-900 truncate">${_esc(dev.name)}</div>
                    <div class="flex items-center gap-1.5 mt-0.5">
                        <span class="protocol-badge ${_pBadge(dev.protocol)}">${_pLabel(dev.protocol)}</span>
                        <span class="text-xs text-slate-400">${cnt} tag${cnt !== 1 ? 's' : ''}</span>
                        ${isLC ? '<span class="text-xs text-slate-400 italic">· view only</span>' : ''}
                    </div>
                </div>
            </div>
            <i class="fa-solid fa-check text-blue-600 text-sm flex-shrink-0" style="display:none" data-check></i>`;
        el.addEventListener('click', () => _selectDevice(dev.id, el));
        list.appendChild(el);
    });
}

function _selectDevice(devId, el) {
    document.querySelectorAll('.modal-device-item').forEach(i => {
        i.classList.remove('active');
        const check = i.querySelector('[data-check]');
        if (check) check.style.display = 'none';
    });
    el.classList.add('active');
    const check = el.querySelector('[data-check]');
    if (check) check.style.display = '';

    const dev = _devices.find(d => String(d.id) === String(devId));
    if (!dev) return;
    _selectedDeviceId = dev.id;
    _selectedDeviceData = dev;

    const prev = document.getElementById('modalSelectedPreview');
    if (prev) {
        prev.classList.remove('hidden');
        document.getElementById('previewDeviceName').textContent = dev.name;
        document.getElementById('previewDeviceProtocol').innerHTML =
            `<span class="protocol-badge ${_pBadge(dev.protocol)}">${_pLabel(dev.protocol)}</span>`;
    }

    const btn = document.getElementById('proceedToTagForm');
    if (btn) {
        btn.disabled = false;
        btn.style.opacity = '1';
        btn.style.cursor = 'pointer';
    }
}

function _proceedToTagForm() {
    if (!_selectedDeviceData) {
        _toast('Select a device first', 'error');
        return;
    }
    const proto = _selectedDeviceData.protocol;

    if (proto === 'modbus-tcp' || proto === 'modbus-rtu') {
        document.getElementById('modbusCtxDevice').textContent = _selectedDeviceData.name;
        document.getElementById('modbusCtxProtocol').textContent = _pLabel(proto);
        _clearModbusForm('mb');
        _showStep('stepModbusForm');
    } else if (proto === 'loadcell') {
        document.getElementById('lcCtxDevice').textContent = _selectedDeviceData.name;
        const lt = (_tags || []).find(t => String(t.device_id) === String(_selectedDeviceId) && (t.tag_name === 'load' || t.name === 'load'));
        document.getElementById('lcUnitDisplay').textContent = lt?.unit || 'kg';
        _showStep('stepLoadcellInfo');
    } else {
        _toast('Unknown protocol: ' + proto, 'error');
    }
}

function _showStep(id) {
    ['stepDeviceSelect', 'stepModbusForm', 'stepLoadcellInfo'].forEach(s => {
        const el = document.getElementById(s);
        if (el) el.style.display = s === id ? 'block' : 'none';
    });
}

function _closeAddTagModal() {
    _hideModal('addTagModal');
    _selectedDeviceId = null;
    _selectedDeviceData = null;
}

// ─── CREATE TAG ───────────────────────────────────────────────────────────────

async function _handleModbusCreate(e) {
    e.preventDefault();
    const btn = e.submitter || e.target.querySelector('[type=submit]');
    const tagName = document.getElementById('mbTagName')?.value?.trim();
    const address = document.getElementById('mbRegAddress')?.value?.trim();
    const registerType = document.getElementById('mbRegisterType')?.value;
    const groupValue = document.getElementById('mbGroup')?.value || '';

    if (!tagName) {
        _toast('Tag name is required', 'error');
        return;
    }
    if (!address) {
        _toast('Register address is required', 'error');
        return;
    }
    if (!registerType) {
        _toast('Register type is required', 'error');
        return;
    }
    if (!_selectedDeviceId) {
        _toast('No device selected', 'error');
        return;
    }

    // Duplicate check (same device + slave + tag name)
    const newSlaveId = parseInt(document.getElementById('mbSlaveId')?.value) || 1;
    const dup = (_tags || []).some(t =>
        String(t.device_id) === String(_selectedDeviceId) &&
        (t.slave_id ?? 1) === newSlaveId &&
        (t.tag_name === tagName || t.name === tagName)
    );
    if (dup) {
        _toast(`"${tagName}" already exists for this device. Use a different name.`, 'error');
        return;
    }

    _setLoading(btn, true);
    const addr = parseInt(address, 10);

    const payload = {
        device_id: _selectedDeviceId,
        tag_name: tagName,
        slave_id: newSlaveId,
        register_address: addr,
        register_type: registerType,
        data_type: document.getElementById('mbDataType').value,
        byte_order: document.getElementById('mbByteOrder').value,
        word_order: document.getElementById('mbWordOrder').value,
        scale_factor: parseFloat(document.getElementById('mbScale').value) || 1.0,
        offset: parseFloat(document.getElementById('mbOffset').value) || 0.0,
        unit: document.getElementById('mbUnit').value.trim(),
        group: groupValue,
        writable: document.getElementById('mbWritable').checked,
        retry_count: parseInt(document.getElementById('mbRetryCount').value) || 1,
        timeout_ms: parseInt(document.getElementById('mbTimeoutMs').value) || 100,
        register_count: parseInt(document.getElementById('mbRegisterCount').value) || 1,
        description: document.getElementById('mbDescription').value.trim(),
        enabled: true
    };
    
    console.log('Creating tag with payload:', payload);

    try {
        const resp = await fetch('/api/datapoints/modbus', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await resp.json();
        if (resp.ok) {
            _closeAddTagModal();
            await _loadData();
            _toast('Tag created successfully', 'success');
        } else {
            _toast(data.error || 'Failed to create tag', 'error');
        }
    } catch (err) {
        console.error('Error creating tag:', err);
        _toast('Network error', 'error');
    } finally {
        _setLoading(btn, false);
    }
}

// ─── EDIT TAG (dispatch) ──────────────────────────────────────────────────────

function editTag(tagId, tagType) {
    const tag = (_tags || []).find(t => t.id == tagId);
    if (!tag) {
        _toast('Tag not found', 'error');
        return;
    }
    
    if (tagType === 'loadcell') {
        _toast('Load cell tags can only edit unit', 'info');
        // You could open a simple unit edit modal here
        return;
    }
    
    _openEditModbusModal(tag);
}

// ─── EDIT MODBUS MODAL ────────────────────────────────────────────────────────

function _openEditModbusModal(tag) {
    const dev = (_devices || []).find(d => String(d.id) === String(tag.device_id));

    document.getElementById('editMbTagId').value = tag.id;
    document.getElementById('editMbCtxDevice').textContent = tag.device_name || tag.deviceName || '—';
    document.getElementById('editMbCtxProtocol').innerHTML = dev
        ? `<span class="protocol-badge ${_pBadge(dev.protocol)}">${_pLabel(dev.protocol)}</span>` : '—';

    document.getElementById('editMbTagName').value = tag.tag_name || tag.name || '';
    document.getElementById('editMbSlaveId').value = tag.slave_id ?? 1;
    document.getElementById('editMbRegisterType').value = tag.register_type || tag.registerType || 'holding';
    document.getElementById('editMbRegAddress').value = tag.register_address || tag.address || '';
    document.getElementById('editMbRegisterCount').value = tag.register_count || tag.registerCount || 1;
    document.getElementById('editMbDataType').value = tag.data_type || tag.dataType || 'uint16';
    document.getElementById('editMbByteOrder').value = tag.byte_order || tag.byteOrder || 'big';
    document.getElementById('editMbWordOrder').value = tag.word_order || tag.wordOrder || 'big';
    document.getElementById('editMbScale').value = tag.scale_factor || tag.scale || 1.0;
    document.getElementById('editMbOffset').value = tag.offset || 0.0;
    document.getElementById('editMbUnit').value = tag.unit || '';
    
    // Set the group dropdown value - use group name from tag.group or tag.group_name
    const groupValue = tag.group || tag.group_name || '';
    document.getElementById('editMbGroup').value = groupValue;
    
    document.getElementById('editMbWritable').checked = tag.writable || false;
    document.getElementById('editMbRetryCount').value = tag.retry_count || tag.retryCount || 1;
    document.getElementById('editMbTimeoutMs').value = tag.timeout_ms || tag.timeoutMs || 100;
    document.getElementById('editMbDescription').value = tag.description || '';

    _showModal('editModbusModal');
}

async function _handleModbusEdit(e) {
    e.preventDefault();
    const btn = e.submitter || e.target.querySelector('[type=submit]');
    const tagId = document.getElementById('editMbTagId').value;
    const tagName = document.getElementById('editMbTagName').value.trim();
    const address = document.getElementById('editMbRegAddress').value.trim();
    const registerType = document.getElementById('editMbRegisterType').value;
    const groupValue = document.getElementById('editMbGroup')?.value || '';

    if (!tagName) {
        _toast('Tag name is required', 'error');
        return;
    }
    if (!address) {
        _toast('Register address is required', 'error');
        return;
    }
    if (!registerType) {
        _toast('Register type is required', 'error');
        return;
    }

    _setLoading(btn, true);
    const addr = parseInt(address, 10);

    const payload = {
        tag_name: tagName,
        slave_id: parseInt(document.getElementById('editMbSlaveId')?.value) || 1,
        register_address: addr,
        register_type: registerType,
        data_type: document.getElementById('editMbDataType').value,
        byte_order: document.getElementById('editMbByteOrder').value,
        word_order: document.getElementById('editMbWordOrder').value,
        scale_factor: parseFloat(document.getElementById('editMbScale').value) || 1.0,
        offset: parseFloat(document.getElementById('editMbOffset').value) || 0.0,
        unit: document.getElementById('editMbUnit').value.trim(),
        group: groupValue,
        writable: document.getElementById('editMbWritable').checked,
        retry_count: parseInt(document.getElementById('editMbRetryCount').value) || 1,
        timeout_ms: parseInt(document.getElementById('editMbTimeoutMs').value) || 100,
        register_count: parseInt(document.getElementById('editMbRegisterCount').value) || 1,
        description: document.getElementById('editMbDescription').value.trim()
    };
    
    console.log('Updating tag with payload:', payload);

    try {
        const resp = await fetch(`/api/datapoints/modbus/${tagId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await resp.json();
        if (resp.ok) {
            _closeEditModbus();
            await _loadData();
            _toast('Tag updated successfully', 'success');
        } else {
            _toast(data.error || 'Failed to update tag', 'error');
        }
    } catch (err) {
        console.error('Error updating tag:', err);
        _toast('Network error', 'error');
    } finally {
        _setLoading(btn, false);
    }
}

function _closeEditModbus() { _hideModal('editModbusModal'); }

// ─── DELETE ───────────────────────────────────────────────────────────────────

async function deleteTag(tagId, tagType) {
    if (tagType === 'loadcell') {
        _toast('Load cell tags are auto-managed and cannot be deleted', 'info');
        return;
    }
    if (!confirm('Delete this tag? This cannot be undone.')) return;

    try {
        const resp = await fetch(`/api/datapoints/${tagId}?type=${tagType}`, { method: 'DELETE' });
        const data = await resp.json();
        if (resp.ok) {
            await _loadData();
            _toast('Tag deleted', 'success');
        } else {
            _toast(data.error || 'Failed to delete', 'error');
        }
    } catch (err) {
        console.error('Error deleting tag:', err);
        _toast('Network error', 'error');
    }
}

// ─── CSV ──────────────────────────────────────────────────────────────────────

async function exportCSV() {
    if (!_tags || !_tags.length) {
        _toast('No tags to export', 'info');
        return;
    }
    const headers = ['device_name', 'device_type', 'tag_name', 'slave_id', 'register_address', 'register_type', 'data_type', 'byte_order', 'word_order', 'scale_factor', 'offset', 'unit', 'group', 'writable', 'retry_count', 'timeout_ms', 'register_count', 'description', 'enabled'];
    const rows = _tags.map(t => {
        return headers.map(h => {
            let v = t[h];
            if (v === undefined && h === 'tag_name') v = t.name;
            if (v === undefined && h === 'register_address') v = t.address;
            if (v === undefined && h === 'slave_id') v = t.slaveId;
            if (v === undefined && h === 'data_type') v = t.dataType;
            if (v === undefined && h === 'register_type') v = t.registerType;
            if (v === undefined && h === 'scale_factor') v = t.scale;
            if (v === undefined && h === 'retry_count') v = t.retryCount;
            if (v === undefined && h === 'timeout_ms') v = t.timeoutMs;
            if (v === undefined && h === 'register_count') v = t.registerCount;
            if (v === undefined && h === 'group') v = t.group || t.group_name;
            if (v === undefined) v = '';
            return typeof v === 'string' && v.includes(',') ? `"${v}"` : v;
        }).join(',');
    });
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `tags_export_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    _toast(`Exported ${_tags.length} tags`, 'success');
}

async function importCSV() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.csv';
    input.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const text = await file.text();
        const lines = text.trim().split('\n');
        if (lines.length < 2) {
            _toast('CSV is empty', 'error');
            return;
        }

        const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
        let imported = 0, errors = 0;

        for (let i = 1; i < lines.length; i++) {
            const cols = lines[i].split(',').map(c => c.trim().replace(/^"|"$/g, ''));
            const row = {};
            headers.forEach((h, j) => { row[h] = cols[j] || ''; });

            const devName = row['device_name'] || row['device_id'] || '';
            const dev = (_devices || []).find(d => d.name === devName || String(d.id) === devName);
            if (!dev) {
                errors++;
                continue;
            }

            const addr = parseInt(row['register_address'] || '0', 10);
            try {
                const resp = await fetch('/api/datapoints/modbus', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        device_id: dev.id,
                        tag_name: row['tag_name'] || `tag_${i}`,
                        slave_id: parseInt(row['slave_id']) || 1,
                        register_address: addr,
                        register_type: row['register_type'] || 'holding',
                        data_type: row['data_type'] || 'uint16',
                        byte_order: row['byte_order'] || 'big',
                        word_order: row['word_order'] || 'big',
                        scale_factor: parseFloat(row['scale_factor']) || 1.0,
                        offset: parseFloat(row['offset']) || 0.0,
                        unit: row['unit'] || '',
                        group: row['group'] || '',
                        writable: row['writable'] === 'true' || row['writable'] === '1',
                        retry_count: parseInt(row['retry_count']) || 1,
                        timeout_ms: parseInt(row['timeout_ms']) || 100,
                        register_count: parseInt(row['register_count']) || 1,
                        description: row['description'] || '',
                        enabled: row['enabled'] !== 'false'
                    })
                });
                if (resp.ok) imported++;
                else errors++;
            } catch {
                errors++;
            }
        }

        await _loadData();
        _toast(`Imported ${imported} tag${imported !== 1 ? 's' : ''}${errors ? ` · ${errors} skipped` : ''}`, errors ? 'warning' : 'success');
    };
    input.click();
}

// ─── HELPERS ──────────────────────────────────────────────────────────────────

function _clearModbusForm(prefix) {
    const ids = {
        [`${prefix}TagName`]: '',
        [`${prefix}SlaveId`]: '1',
        [`${prefix}RegAddress`]: '',
        [`${prefix}RegisterCount`]: '1',
        [`${prefix}Scale`]: '1.0',
        [`${prefix}Offset`]: '0.0',
        [`${prefix}Unit`]: '',
        [`${prefix}RetryCount`]: '1',
        [`${prefix}TimeoutMs`]: '100',
        [`${prefix}Description`]: ''
    };
    Object.entries(ids).forEach(([id, v]) => {
        const el = document.getElementById(id);
        if (el) el.value = v;
    });
    
    // Reset selects
    const registerType = document.getElementById(`${prefix}RegisterType`);
    if (registerType) registerType.value = 'holding';
    
    const dataType = document.getElementById(`${prefix}DataType`);
    if (dataType) dataType.value = 'uint16';
    
    const byteOrder = document.getElementById(`${prefix}ByteOrder`);
    if (byteOrder) byteOrder.value = 'big';
    
    const wordOrder = document.getElementById(`${prefix}WordOrder`);
    if (wordOrder) wordOrder.value = 'big';
    
    // Reset group dropdown
    const groupSelect = document.getElementById(`${prefix}Group`);
    if (groupSelect) groupSelect.value = '';
    
    // Reset checkbox
    const writable = document.getElementById(`${prefix}Writable`);
    if (writable) writable.checked = false;
}

function _setLoading(btn, loading) {
    if (!btn) return;
    if (loading) {
        btn._origHTML = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Saving…';
    } else {
        btn.disabled = false;
        btn.innerHTML = btn._origHTML || btn.innerHTML;
    }
}

function _pLabel(p) {
    if (!p) return '—';
    const labels = {
        'modbus-tcp': 'Modbus TCP',
        'modbus-rtu': 'Modbus RTU',
        'loadcell': 'Load Cell'
    };
    return labels[p] || p.toUpperCase();
}

function _pBadge(p) {
    if (!p) return '';
    if (p === 'modbus-tcp') return 'modbus-tcp';
    if (p === 'modbus-rtu') return 'modbus-rtu';
    return 'loadcell';
}

function _esc(s) {
    if (s === null || s === undefined) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function _showModal(id) {
    const el = document.getElementById(id);
    if (el) {
        el.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
}

function _hideModal(id) {
    const el = document.getElementById(id);
    if (el) {
        el.style.display = 'none';
        document.body.style.overflow = '';
    }
}

function _vis(id) {
    const el = document.getElementById(id);
    return el && el.style.display === 'flex';
}

function _toast(msg, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${msg}`);

    // Remove existing toasts if too many
    const existing = document.querySelectorAll('.tm-toast');
    if (existing.length > 3) {
        existing[0].remove();
    }

    const colors = {
        success: '#16A34A',
        error: '#DC2626',
        info: '#2563EB',
        warning: '#D97706'
    };
    
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-circle-xmark',
        info: 'fa-circle-info',
        warning: 'fa-triangle-exclamation'
    };

    const t = document.createElement('div');
    t.className = 'tm-toast';
    t.style.cssText = `
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 99999;
        background: ${colors[type] || colors.info};
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 500;
        box-shadow: 0 4px 16px rgba(0,0,0,0.25);
        display: flex;
        align-items: center;
        gap: 10px;
        transition: all 0.3s ease;
        transform: translateX(0);
        opacity: 1;
        min-width: 240px;
        max-width: 360px;
        pointer-events: none;
    `;
    t.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}" style="font-size: 16px;"></i><span>${_esc(msg)}</span>`;

    document.body.appendChild(t);

    setTimeout(() => {
        t.style.opacity = '0';
        t.style.transform = 'translateX(20px)';
        setTimeout(() => t.remove(), 300);
    }, 3500);
}

// ─── SAVE MODBUS CONFIGURATION TO PIPELINE ───────────────────────────────────
// modbus-mapping.js - COMPLETE FIXED saveModbusConfig function
async function saveModbusConfig() {
    console.log('[MODBUS-CFG] Save button clicked');
    
    const btn = document.getElementById('saveModbusConfigBtn');
    const origHTML = btn ? btn.innerHTML : '';
    
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Sending…';
    }

    try {
        // SIMPLE: Just tell backend to save modbus config
        const resp = await fetch('/api/pipeline/modbus-config/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        // Check if response is OK
        if (!resp.ok) {
            const text = await resp.text();
            console.error('[MODBUS-CFG] Server responded with:', resp.status, text);
            throw new Error(`Server error: ${resp.status}`);
        }

        // Try to parse JSON
        let data;
        try {
            data = await resp.json();
        } catch (e) {
            console.error('[MODBUS-CFG] Failed to parse JSON response');
            throw new Error('Invalid response from server');
        }

        if (data.success) {
            _toast('✓ ' + (data.message || 'Configuration sent to modbus service'), 'success');
        } else {
            _toast(data.error || 'Failed to send configuration', 'error');
        }
    } catch (err) {
        console.error('[MODBUS-CFG] Error:', err);
        _toast('Network error: ' + err.message, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = origHTML;
        }
    }
}
// ─── EXPORTS ──────────────────────────────────────────────────────────────────
window.initializeModbusMapping = initializeModbusMapping;
window.editTag = editTag;
window.deleteTag = deleteTag;
window.importCSV = importCSV;
window.exportCSV = exportCSV;
window.highlightTagRow = highlightTagRow;
window.changeBrowserPage = changeBrowserPage;
window.saveModbusConfig = saveModbusConfig;

// ─── GROUPS PANEL ────────────────────────────────────────────────────────────

function _renderGroupsPanel() {
    const container = document.getElementById('tagGroupsContainer');
    if (!container) return;

    if (!_groups.length) {
        container.innerHTML = `<div class="text-center py-6 text-slate-400 text-sm">
            <i class="fa-solid fa-layer-group text-2xl mb-2 block"></i>No groups yet</div>`;
        return;
    }

    container.innerHTML = '';
    _groups.forEach(g => {
        const card = document.createElement('div');
        card.className = 'flex items-center justify-between p-3 bg-white border border-slate-200 rounded-lg';
        card.innerHTML = `
            <div class="flex items-center gap-2">
                <span class="w-3 h-3 rounded-full bg-${g.color || 'blue'}-500"></span>
                <span class="text-sm font-medium text-slate-800">${_esc(g.name)}</span>
                <span class="text-xs text-slate-400">${g.tag_count} tag${g.tag_count !== 1 ? 's' : ''}</span>
            </div>
            <button class="text-slate-400 hover:text-red-500 transition-colors" onclick="_deleteTagGroup(${g.id}, '${_esc(g.name)}')" title="Delete group">
                <i class="fa-solid fa-trash text-xs"></i>
            </button>`;
        container.appendChild(card);
    });
}

function _openAddGroupModal() {
    const m = document.getElementById('addTagGroupModal');
    if (m) {
        m.style.display = 'flex';
        document.getElementById('newGroupName').value = '';
        document.getElementById('newGroupDescription').value = '';
        _selectedGroupColor = 'blue';
        document.querySelectorAll('[data-group-color]').forEach(b => {
            b.classList.toggle('ring-2', b.dataset.groupColor === 'blue');
        });
    }
}

function _closeAddGroupModal() {
    const m = document.getElementById('addTagGroupModal');
    if (m) m.style.display = 'none';
}

async function _saveTagGroup() {
    const name = document.getElementById('newGroupName')?.value.trim();
    if (!name) { _toast('Group name is required', 'error'); return; }
    try {
        const resp = await fetch('/api/tag-groups', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, color: _selectedGroupColor, description: document.getElementById('newGroupDescription')?.value.trim() || '' })
        });
        const data = await resp.json();
        if (resp.ok) {
            _closeAddGroupModal();
            await _loadData();
            _toast('Group created', 'success');
        } else {
            _toast(data.error || 'Failed to create group', 'error');
        }
    } catch (e) {
        _toast('Network error', 'error');
    }
}

async function _deleteTagGroup(groupId, groupName) {
    if (!confirm(`Delete group "${groupName}"?\nTags in this group will become ungrouped.`)) return;
    try {
        const resp = await fetch(`/api/tag-groups/${groupId}`, { method: 'DELETE' });
        const data = await resp.json();
        if (resp.ok) {
            await _loadData();
            _toast('Group deleted', 'success');
        } else {
            _toast(data.error || 'Failed to delete group', 'error');
        }
    } catch (e) {
        _toast('Network error', 'error');
    }
}

// ─── HELPER ──────────────────────────────────────────────────────────────────

function _groupColor(groupName) {
    const g = (_groups || []).find(gr => gr.name === groupName);
    return g ? (g.color || 'blue') : 'slate';
}

window._deleteTagGroup = _deleteTagGroup;