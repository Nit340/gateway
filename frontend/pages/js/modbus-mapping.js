// modbus-mapping.js — Fixed API response handling
'use strict';

let _devices = [];
let _tags    = [];
let _selectedDeviceId   = null;
let _selectedDeviceData = null;
let _editingTagId       = null;

// Pagination variables
let _browserCurrentPage = 1;
let _browserPageSize = 12;
let _browserTotalPages = 1;

// ─── INIT ────────────────────────────────────────────────────────────────────

function initializeModbusMapping() {
    _loadData();
    _bindStaticListeners();
}

// ─── DATA ────────────────────────────────────────────────────────────────────

async function _loadData() {
    try {
        // First load devices
        const devResp = await fetch('/api/datapoints/devices');
        const devData = await devResp.json();
        _devices = devData.devices || [];
        
        // Then load tags - the API returns an array directly
        const tagResp = await fetch('/api/datapoints');
        const tagData = await tagResp.json();
        
        // Check if tagData is an array or has a tags property
        if (Array.isArray(tagData)) {
            _tags = tagData;
        } else if (tagData.tags && Array.isArray(tagData.tags)) {
            _tags = tagData.tags;
        } else {
            _tags = [];
        }
        
        console.log('Devices loaded:', _devices);
        console.log('Tags loaded:', _tags);
        
        _renderTagsTable();
        _renderTagsBrowser();
        _updateDropdownFilters();
        _renderPaginationControls();
    } catch (err) {
        console.error('Failed to load data:', err);
        _toast('Failed to load data', 'error');
    }
}

// ─── RENDER: TABLE ───────────────────────────────────────────────────────────

function _renderTagsTable() {
    const tbody = document.getElementById('mappingTableBody');
    const count = document.getElementById('mappingCount');
    if (!tbody) return;

    const devId = document.getElementById('deviceFilter')?.value || '';
    let rows = _tags || [];
    
    if (devId) {
        rows = rows.filter(t => String(t.device_id) === String(devId));
    }

    if (count) count.textContent = rows.length;

    if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-12 text-slate-400">
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
        
        // Use consistent ID format
        tr.id = `tag-row-${tag.id}`;
        tr.className = 'tag-table-row';
        tr.dataset.tagId = tag.id;
        tr.dataset.tagType = isLC ? 'loadcell' : 'modbus';
        
        // Get values with fallbacks
        const deviceName = tag.device_name || tag.deviceName || '—';
        const deviceType = tag.device_type || tag.protocol || (isLC ? 'Load Cell' : 'Modbus');
        const tagName = tag.tag_name || tag.name || '—';
        const dataType = tag.data_type || (isLC ? 'float32' : '—');
        const unit = tag.unit || '—';
        const address = tag.register_address !== undefined ? tag.register_address : '—';
        const enabled = tag.enabled !== undefined ? tag.enabled : true;
        
        tr.innerHTML = `
            <td class="font-medium text-slate-900">${_esc(deviceName)}</td>
            <td><span class="protocol-badge ${_pClass(isLC, deviceType)}">${_esc(deviceType)}</span></td>
            <td class="text-slate-600 font-mono text-xs">${address}</td>
            <td class="font-mono text-xs text-slate-900">${_esc(tagName)}</td>
            <td class="text-slate-600 text-xs">${_esc(dataType)}</td>
            <td class="text-slate-600 text-xs">${_esc(unit)}</td>
            <td><span class="px-2 py-0.5 rounded-full text-xs font-medium ${enabled ? 'bg-green-100 text-green-800' : 'bg-slate-100 text-slate-600'}">${enabled ? 'Enabled' : 'Disabled'}</span></td>
            <td class="text-right whitespace-nowrap">
                <button class="text-blue-600 hover:text-blue-800 mr-2" onclick="editTag(${tag.id}, '${isLC ? 'loadcell' : 'modbus'}')" title="Edit">
                    <i class="fa-solid fa-pencil text-sm"></i>
                </button>
                ${!isLC ? `<button class="text-red-500 hover:text-red-700" onclick="deleteTag(${tag.id}, 'modbus')" title="Delete"><i class="fa-solid fa-trash text-sm"></i></button>` : ''}
            </td>`;
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
    let rows = _tags || [];
    
    if (devId) {
        rows = rows.filter(t => String(t.device_id) === String(devId));
    }
    
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
            console.log(`Tag card clicked: ID ${tag.id}, Type: ${isLC ? 'loadcell' : 'modbus'}, Name: ${tag.tag_name || tag.name}`);
            highlightTagRow(tag.id);
        });
        
        d.style.cursor = 'pointer';
        
        // Get values with fallbacks
        const tagName = tag.tag_name || tag.name || 'Unnamed';
        const deviceName = tag.device_name || tag.deviceName || '—';
        const dataType = tag.data_type || (isLC ? 'float32' : '—');
        const unit = tag.unit || '—';
        const address = tag.register_address !== undefined ? tag.register_address : null;
        
        d.innerHTML = `
            <div class="tag-card-header">
                <div class="tag-card-name">${_esc(tagName)}</div>
                <span class="protocol-badge ${_pClass(isLC, tag.device_type || tag.protocol)}">${isLC ? 'LOADCELL' : 'MODBUS'}</span>
            </div>
            <div class="tag-card-body">
                <div class="tag-card-row">
                    <span>Device</span>
                    <span class="font-medium text-slate-700">${_esc(deviceName)}</span>
                </div>
                ${address !== null ? `
                <div class="tag-card-row">
                    <span>Address</span>
                    <span class="font-mono">${address}</span>
                </div>` : ''}
                <div class="tag-card-row">
                    <span>Type</span>
                    <span>${_esc(dataType)}</span>
                </div>
                ${unit && unit !== '—' ? `
                <div class="tag-card-row">
                    <span>Unit</span>
                    <span>${_esc(unit)}</span>
                </div>` : ''}
                ${isLC ? `
                <div class="tag-card-row text-xs text-green-600">
                    <span><i class="fa-solid fa-scale-balanced mr-1"></i> Load Cell Tag</span>
                </div>` : ''}
            </div>`;
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

function highlightTagRow(tagId) {
    console.log(`Attempting to highlight tag ID: ${tagId}`);
    
    // Remove highlight from all rows
    document.querySelectorAll('.tag-table-row').forEach(row => {
        row.classList.remove('bg-yellow-100', 'border-l-4', 'border-yellow-400', 'font-bold');
        row.style.backgroundColor = '';
    });

    // Try multiple selectors to find the row
    let targetRow = document.getElementById(`tag-row-${tagId}`);
    
    if (!targetRow) {
        targetRow = document.querySelector(`.tag-table-row[data-tag-id="${tagId}"]`);
    }
    
    if (!targetRow) {
        targetRow = document.querySelector(`tr[data-tag-id="${tagId}"]`);
    }
    
    // Try with string comparison
    if (!targetRow) {
        targetRow = Array.from(document.querySelectorAll('.tag-table-row')).find(row => 
            String(row.dataset.tagId) === String(tagId)
        );
    }

    if (targetRow) {
        console.log(`Found row for tag ID ${tagId}, applying highlight`);
        targetRow.classList.add('bg-yellow-100', 'border-l-4', 'border-yellow-400', 'font-bold');
        
        // Scroll the row into view smoothly
        targetRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        // Find tag info
        const tag = (_tags || []).find(t => String(t.id) === String(tagId));
        if (tag) {
            const tagName = tag.tag_name || tag.name || 'Unknown';
            const isLC = tag.protocol === 'loadcell' || tag.type === 'loadcell';
            _toast(`Selected: ${tagName} (${isLC ? 'Load Cell' : 'Modbus'})`, 'success');
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
}

// ─── EVENT LISTENERS ─────────────────────────────────────────────────────────

function _bindStaticListeners() {
    document.getElementById('addMappingBtn')?.addEventListener('click', () => _openAddTagModal(null));
    document.getElementById('deviceFilter')?.addEventListener('change', _renderTagsTable);
    document.getElementById('tagSearch')?.addEventListener('input', () => {
        _browserCurrentPage = 1;
        _renderTagsBrowser();
    });
    document.getElementById('tagDeviceFilter')?.addEventListener('change', () => {
        _browserCurrentPage = 1;
        _renderTagsBrowser();
    });

    // Add tag modal
    document.getElementById('closeAddTagModal')?.addEventListener('click', _closeAddTagModal);
    document.getElementById('cancelAddTag')?.addEventListener('click', _closeAddTagModal);
    document.getElementById('proceedToTagForm')?.addEventListener('click', _proceedToTagForm);
    document.getElementById('modbusFormBack')?.addEventListener('click', () => _showStep('stepDeviceSelect'));
    document.getElementById('lcFormBack')?.addEventListener('click', () => _showStep('stepDeviceSelect'));
    document.getElementById('modbusFormCancel')?.addEventListener('click', _closeAddTagModal);
    document.getElementById('lcFormClose')?.addEventListener('click', _closeAddTagModal);
    document.getElementById('modbusTagForm')?.addEventListener('submit', _handleModbusCreate);
    document.getElementById('mbRegAddress')?.addEventListener('input', e => _autoDetect(e.target.value, 'mbDetectedType'));
    document.getElementById('addTagModal')?.addEventListener('click', e => { if (e.target.id === 'addTagModal') _closeAddTagModal(); });

    // Edit modal (modbus)
    document.getElementById('closeEditModbusModal')?.addEventListener('click', _closeEditModbus);
    document.getElementById('editModbusCancel')?.addEventListener('click', _closeEditModbus);
    document.getElementById('editModbusForm')?.addEventListener('submit', _handleModbusEdit);
    document.getElementById('editMbRegAddress')?.addEventListener('input', e => _autoDetect(e.target.value, 'editMbDetectedType'));
    document.getElementById('editModbusModal')?.addEventListener('click', e => { if (e.target.id === 'editModbusModal') _closeEditModbus(); });

    // Edit modal (loadcell)
    document.getElementById('closeEditLcModal')?.addEventListener('click', _closeEditLc);
    document.getElementById('editLcCancel')?.addEventListener('click', _closeEditLc);
    document.getElementById('editLcForm')?.addEventListener('submit', _handleLcEdit);
    document.getElementById('editLcModal')?.addEventListener('click', e => { if (e.target.id === 'editLcModal') _closeEditLc(); });

    // CSV
    document.getElementById('importCSVBtn')?.addEventListener('click', importCSV);
    document.getElementById('exportCSVBtn')?.addEventListener('click', exportCSV);

    // Escape
    document.addEventListener('keydown', e => {
        if (e.key !== 'Escape') return;
        if (_vis('addTagModal')) _closeAddTagModal();
        if (_vis('editModbusModal')) _closeEditModbus();
        if (_vis('editLcModal')) _closeEditLc();
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

    if (!tagName) {
        _toast('Tag name is required', 'error');
        return;
    }
    if (!address) {
        _toast('Register address is required', 'error');
        return;
    }
    if (!_selectedDeviceId) {
        _toast('No device selected', 'error');
        return;
    }

    // Duplicate check
    const dup = (_tags || []).some(t =>
        String(t.device_id) === String(_selectedDeviceId) && 
        (t.tag_name === tagName || t.name === tagName)
    );
    if (dup) {
        _toast(`"${tagName}" already exists for this device. Use a different name.`, 'error');
        return;
    }

    _setLoading(btn, true);
    const addr = parseInt(address, 10);

    try {
        const resp = await fetch('/api/datapoints/modbus', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                device_id: _selectedDeviceId,
                tag_name: tagName,
                register_address: addr,
                register_type: _regType(addr),
                data_type: document.getElementById('mbDataType').value,
                byte_order: document.getElementById('mbByteOrder').value,
                word_order: document.getElementById('mbWordOrder').value,
                scale_factor: parseFloat(document.getElementById('mbScale').value) || 1.0,
                offset: parseFloat(document.getElementById('mbOffset').value) || 0.0,
                unit: document.getElementById('mbUnit').value.trim(),
                description: document.getElementById('mbDescription').value.trim(),
                enabled: true
            })
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
        console.error(err);
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
        _openEditLcModal(tag);
    } else {
        _openEditModbusModal(tag);
    }
}

// ─── EDIT MODBUS MODAL ────────────────────────────────────────────────────────

function _openEditModbusModal(tag) {
    const dev = (_devices || []).find(d => String(d.id) === String(tag.device_id));

    document.getElementById('editMbTagId').value = tag.id;
    document.getElementById('editMbCtxDevice').textContent = tag.device_name || tag.deviceName || '—';
    document.getElementById('editMbCtxProtocol').innerHTML = dev
        ? `<span class="protocol-badge ${_pBadge(dev.protocol)}">${_pLabel(dev.protocol)}</span>` : '—';

    document.getElementById('editMbTagName').value = tag.tag_name || tag.name || '';
    document.getElementById('editMbRegAddress').value = tag.register_address ?? '';
    document.getElementById('editMbDataType').value = tag.data_type || 'int16';
    document.getElementById('editMbByteOrder').value = tag.byte_order || 'big';
    document.getElementById('editMbWordOrder').value = tag.word_order || 'big';
    document.getElementById('editMbScale').value = tag.scale_factor ?? 1.0;
    document.getElementById('editMbOffset').value = tag.offset ?? 0.0;
    document.getElementById('editMbUnit').value = tag.unit || '';
    document.getElementById('editMbDescription').value = tag.description || '';

    _autoDetect(tag.register_address, 'editMbDetectedType');
    _showModal('editModbusModal');
}

async function _handleModbusEdit(e) {
    e.preventDefault();
    const btn = e.submitter || e.target.querySelector('[type=submit]');
    const tagId = document.getElementById('editMbTagId').value;
    const tagName = document.getElementById('editMbTagName').value.trim();
    const address = document.getElementById('editMbRegAddress').value.trim();

    if (!tagName) {
        _toast('Tag name is required', 'error');
        return;
    }
    if (!address) {
        _toast('Register address is required', 'error');
        return;
    }

    _setLoading(btn, true);
    const addr = parseInt(address, 10);

    try {
        const resp = await fetch(`/api/datapoints/modbus/${tagId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tag_name: tagName,
                register_address: addr,
                register_type: _regType(addr),
                data_type: document.getElementById('editMbDataType').value,
                byte_order: document.getElementById('editMbByteOrder').value,
                word_order: document.getElementById('editMbWordOrder').value,
                scale_factor: parseFloat(document.getElementById('editMbScale').value) || 1.0,
                offset: parseFloat(document.getElementById('editMbOffset').value) || 0.0,
                unit: document.getElementById('editMbUnit').value.trim(),
                description: document.getElementById('editMbDescription').value.trim()
            })
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
        console.error(err);
        _toast('Network error', 'error');
    } finally {
        _setLoading(btn, false);
    }
}

function _closeEditModbus() { _hideModal('editModbusModal'); }

// ─── EDIT LOADCELL MODAL ──────────────────────────────────────────────────────

function _openEditLcModal(tag) {
    document.getElementById('editLcTagId').value = tag.id;
    document.getElementById('editLcCtxDevice').textContent = tag.device_name || tag.deviceName || '—';
    document.getElementById('editLcTagName').value = tag.tag_name || tag.name || '';

    const dataTypeSelect = document.getElementById('editLcDataType');
    if (dataTypeSelect) {
        dataTypeSelect.value = tag.data_type || 'float32';
    }

    document.getElementById('editLcUnit').value = tag.unit || '';
    _showModal('editLcModal');
}

async function _handleLcEdit(e) {
    e.preventDefault();
    const btn = e.submitter || e.target.querySelector('[type=submit]');
    const tagId = document.getElementById('editLcTagId').value;
    const unit = document.getElementById('editLcUnit').value.trim();
    const dataType = document.getElementById('editLcDataType').value;

    _setLoading(btn, true);
    try {
        const resp = await fetch(`/api/datapoints/loadcell/${tagId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                unit,
                data_type: dataType
            })
        });

        if (resp.status === 404 || resp.status === 405) {
            const resp2 = await fetch(`/api/datapoints/modbus/${tagId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    unit,
                    data_type: dataType
                })
            });
            const d2 = await resp2.json();
            if (resp2.ok) {
                _closeEditLc();
                await _loadData();
                _toast('Load cell tag updated successfully', 'success');
            } else {
                _toast(d2.error || 'Failed to update load cell tag', 'error');
            }
            return;
        }

        const data = await resp.json();
        if (resp.ok) {
            _closeEditLc();
            await _loadData();
            _toast('Load cell tag updated successfully', 'success');
        } else {
            _toast(data.error || 'Failed to update load cell tag', 'error');
        }
    } catch (err) {
        console.error(err);
        _toast('Network error', 'error');
    } finally {
        _setLoading(btn, false);
    }
}

function _closeEditLc() { _hideModal('editLcModal'); }

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
        console.error(err);
        _toast('Network error', 'error');
    }
}

// ─── CSV ──────────────────────────────────────────────────────────────────────

async function exportCSV() {
    if (!_tags || !_tags.length) {
        _toast('No tags to export', 'info');
        return;
    }
    const headers = ['device_name', 'device_type', 'tag_name', 'register_address', 'register_type', 'data_type', 'byte_order', 'word_order', 'scale_factor', 'offset', 'unit', 'description', 'enabled'];
    const rows = _tags.map(t => headers.map(h => {
        let v = t[h];
        if (v === undefined && h === 'tag_name') v = t.name;
        if (v === undefined) v = '';
        return typeof v === 'string' && v.includes(',') ? `"${v}"` : v;
    }).join(','));
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
                        register_address: addr,
                        register_type: row['register_type'] || _regType(addr),
                        data_type: row['data_type'] || 'int16',
                        byte_order: row['byte_order'] || 'big',
                        word_order: row['word_order'] || 'big',
                        scale_factor: parseFloat(row['scale_factor']) || 1.0,
                        offset: parseFloat(row['offset']) || 0.0,
                        unit: row['unit'] || '',
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

function _regType(n) {
    n = parseInt(n);
    if (isNaN(n)) return 'holding';
    if (n <= 9999) return 'coil';
    if (n <= 19999) return 'discrete';
    if (n <= 29999) return 'input';
    return 'holding';
}

function _autoDetect(val, elId) {
    const el = document.getElementById(elId);
    if (!el) return;
    const n = parseInt(val);
    if (isNaN(n) || val === '') {
        el.textContent = 'Enter address…';
        el.style.color = '#94a3b8';
        return;
    }
    let label, color;
    if (n <= 9999) {
        label = 'Coil (0–9999)';
        color = '#2563EB';
    } else if (n <= 19999) {
        label = 'Discrete Input (10000–19999)';
        color = '#16A34A';
    } else if (n <= 29999) {
        label = 'Input Register (20000–29999)';
        color = '#D97706';
    } else if (n <= 49999) {
        label = 'Holding Register (40000–49999)';
        color = '#7C3AED';
    } else {
        label = 'Out of range';
        color = '#DC2626';
    }
    el.textContent = label;
    el.style.color = color;
}

function _clearModbusForm(prefix) {
    const ids = {
        [`${prefix}TagName`]: '',
        [`${prefix}RegAddress`]: '',
        [`${prefix}Scale`]: '1.0',
        [`${prefix}Offset`]: '0.0',
        [`${prefix}Unit`]: '',
        [`${prefix}Description`]: ''
    };
    Object.entries(ids).forEach(([id, v]) => {
        const el = document.getElementById(id);
        if (el) el.value = v;
    });
    [`${prefix}DataType`, `${prefix}ByteOrder`, `${prefix}WordOrder`].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.selectedIndex = 0;
    });
    const det = document.getElementById(`${prefix}DetectedType`);
    if (det) {
        det.textContent = 'Enter address…';
        det.style.color = '#94a3b8';
    }
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

function _pClass(isLC, deviceType) {
    if (isLC) return 'loadcell';
    const dt = (deviceType || '').toLowerCase();
    if (dt.includes('tcp')) return 'modbus-tcp';
    if (dt.includes('rtu')) return 'modbus-rtu';
    return 'modbus-tcp';
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

// ─── EXPORTS ──────────────────────────────────────────────────────────────────
window.initializeModbusMapping = initializeModbusMapping;
window.editTag = editTag;
window.deleteTag = deleteTag;
window.importCSV = importCSV;
window.exportCSV = exportCSV;
window.highlightTagRow = highlightTagRow;
window.changeBrowserPage = changeBrowserPage;