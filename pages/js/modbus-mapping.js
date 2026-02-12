// modbus-mapping.js — Add Tag / Tag Mapping
'use strict';

let _devices = [];
let _tags    = [];
let _selectedDeviceId   = null;
let _selectedDeviceData = null;
let _editingTagId       = null;

// ─── INIT ────────────────────────────────────────────────────────────────────

function initializeModbusMapping() {
    _loadData();
    _bindStaticListeners();
}

// ─── DATA ────────────────────────────────────────────────────────────────────

async function _loadData() {
    try {
        const [devResp, tagResp] = await Promise.all([
            fetch('/api/datapoints/devices'),
            fetch('/api/datapoints')
        ]);
        _devices = (await devResp.json()).devices || [];
        _tags    = (await tagResp.json()).tags    || [];
        _renderTagsTable();
        _renderTagsBrowser();
        _updateDropdownFilters();
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
    const rows  = devId ? _tags.filter(t => String(t.device_id) === String(devId)) : _tags;

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
        const isLC = tag.type === 'loadcell';
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="font-medium text-slate-900">${_esc(tag.device_name||'—')}</td>
            <td><span class="protocol-badge ${_pClass(tag)}">${_esc(tag.device_type||'—')}</span></td>
            <td class="text-slate-600 font-mono text-xs">${tag.register_address??'—'}</td>
            <td class="font-mono text-xs text-slate-900">${_esc(tag.tag_name)}</td>
            <td class="text-slate-600 text-xs">${_esc(tag.data_type||'—')}</td>
            <td class="text-slate-600 text-xs">${_esc(tag.unit||'—')}</td>
            <td><span class="px-2 py-0.5 rounded-full text-xs font-medium ${tag.enabled?'bg-green-100 text-green-800':'bg-slate-100 text-slate-600'}">${tag.enabled?'Enabled':'Disabled'}</span></td>
            <td class="text-right whitespace-nowrap">
                <button class="text-blue-600 hover:text-blue-800 mr-2" onclick="editTag(${tag.id},'${tag.type}')" title="Edit">
                    <i class="fa-solid fa-pencil text-sm"></i>
                </button>
                ${!isLC?`<button class="text-red-500 hover:text-red-700" onclick="deleteTag(${tag.id},'${tag.type}')" title="Delete"><i class="fa-solid fa-trash text-sm"></i></button>`:''}
            </td>`;
        tbody.appendChild(tr);
    });
}

// ─── RENDER: BROWSER ─────────────────────────────────────────────────────────

function _renderTagsBrowser() {
    const container  = document.getElementById('tagsList');
    const emptyState = document.getElementById('tagsEmptyState');
    if (!container) return;

    const q    = (document.getElementById('tagSearch')?.value||'').toLowerCase();
    const devId= document.getElementById('tagDeviceFilter')?.value||'';
    let rows   = _tags;
    if (devId) rows = rows.filter(t => String(t.device_id)===String(devId));
    if (q)     rows = rows.filter(t =>
        (t.tag_name||'').toLowerCase().includes(q)||
        (t.device_name||'').toLowerCase().includes(q)||
        (t.description||'').toLowerCase().includes(q)
    );

    container.innerHTML = '';
    if (!rows.length) { emptyState?.classList.remove('hidden'); return; }
    emptyState?.classList.add('hidden');

    rows.forEach(tag => {
        const isLC = tag.type === 'loadcell';
        const d = document.createElement('div');
        d.className = 'tag-card';
        d.innerHTML = `
            <div class="tag-card-header">
                <div class="tag-card-name">${_esc(tag.tag_name)}</div>
                <span class="protocol-badge ${_pClass(tag)}">${isLC?'LOADCELL':'MODBUS'}</span>
            </div>
            <div class="tag-card-body">
                <div class="tag-card-row"><span>Device</span><span class="font-medium text-slate-700">${_esc(tag.device_name||'—')}</span></div>
                ${tag.register_address!=null?`<div class="tag-card-row"><span>Address</span><span class="font-mono">${tag.register_address}</span></div>`:''}
                <div class="tag-card-row"><span>Type</span><span>${_esc(tag.data_type||'—')}</span></div>
                ${tag.unit?`<div class="tag-card-row"><span>Unit</span><span>${_esc(tag.unit)}</span></div>`:''}
            </div>
            <div class="tag-card-actions">
                <button class="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1" onclick="editTag(${tag.id},'${tag.type}')">
                    <i class="fa-solid fa-pencil"></i> Edit
                </button>
                <!-- Delete button removed from tag browser - only available in table -->
            </div>`;
        container.appendChild(d);
    });
}

// ─── DROPDOWN FILTERS ────────────────────────────────────────────────────────

function _updateDropdownFilters() {
    ['deviceFilter','tagDeviceFilter'].forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        const cur = sel.value;
        sel.innerHTML = '<option value="">All Devices</option>';
        _devices.forEach(d => {
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
    document.getElementById('tagSearch')?.addEventListener('input', _renderTagsBrowser);
    document.getElementById('tagDeviceFilter')?.addEventListener('change', _renderTagsBrowser);

    // Add tag modal
    document.getElementById('closeAddTagModal')?.addEventListener('click', _closeAddTagModal);
    document.getElementById('cancelAddTag')?.addEventListener('click', _closeAddTagModal);
    document.getElementById('proceedToTagForm')?.addEventListener('click', _proceedToTagForm);
    document.getElementById('modbusFormBack')?.addEventListener('click', () => _showStep('stepDeviceSelect'));
    document.getElementById('lcFormBack')?.addEventListener('click', () => _showStep('stepDeviceSelect'));
    document.getElementById('modbusFormCancel')?.addEventListener('click', _closeAddTagModal);
    document.getElementById('lcFormClose')?.addEventListener('click', _closeAddTagModal);
    document.getElementById('modbusTagForm')?.addEventListener('submit', _handleModbusCreate);
    document.getElementById('mbRegAddress')?.addEventListener('input', e => _autoDetect(e.target.value,'mbDetectedType'));
    document.getElementById('addTagModal')?.addEventListener('click', e => { if(e.target.id==='addTagModal') _closeAddTagModal(); });

    // Edit modal (modbus)
    document.getElementById('closeEditModbusModal')?.addEventListener('click', _closeEditModbus);
    document.getElementById('editModbusCancel')?.addEventListener('click', _closeEditModbus);
    document.getElementById('editModbusForm')?.addEventListener('submit', _handleModbusEdit);
    document.getElementById('editMbRegAddress')?.addEventListener('input', e => _autoDetect(e.target.value,'editMbDetectedType'));
    document.getElementById('editModbusModal')?.addEventListener('click', e => { if(e.target.id==='editModbusModal') _closeEditModbus(); });

    // Edit modal (loadcell)
    document.getElementById('closeEditLcModal')?.addEventListener('click', _closeEditLc);
    document.getElementById('editLcCancel')?.addEventListener('click', _closeEditLc);
    document.getElementById('editLcForm')?.addEventListener('submit', _handleLcEdit);
    document.getElementById('editLcModal')?.addEventListener('click', e => { if(e.target.id==='editLcModal') _closeEditLc(); });

    // CSV
    document.getElementById('importCSVBtn')?.addEventListener('click', importCSV);
    document.getElementById('exportCSVBtn')?.addEventListener('click', exportCSV);

    // Escape
    document.addEventListener('keydown', e => {
        if (e.key !== 'Escape') return;
        if (_vis('addTagModal'))     _closeAddTagModal();
        if (_vis('editModbusModal')) _closeEditModbus();
        if (_vis('editLcModal'))     _closeEditLc();
    });
}

// ─── ADD TAG MODAL ───────────────────────────────────────────────────────────

function _openAddTagModal(preDevId) {
    _selectedDeviceId   = null;
    _selectedDeviceData = null;

    // Clear form
    _clearModbusForm('mb');

    // Reset proceed btn
    const btn = document.getElementById('proceedToTagForm');
    if (btn) { btn.disabled=true; btn.style.opacity='0.4'; btn.style.cursor='not-allowed'; }

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

    if (!_devices.length) {
        list.innerHTML = '<p class="text-sm text-slate-400 text-center py-6">No devices found. Add a device first.</p>';
        return;
    }

    _devices.forEach(dev => {
        const isLC = dev.protocol === 'loadcell';
        const cnt  = _tags.filter(t => String(t.device_id)===String(dev.id)).length;
        const el   = document.createElement('div');
        el.className = 'modal-device-item';
        el.dataset.modalDeviceId = dev.id;
        el.innerHTML = `
            <div class="flex items-center gap-3 min-w-0 flex-1">
                <i class="fa-solid ${isLC?'fa-scale-balanced text-green-600':'fa-ethernet text-blue-600'} text-sm w-4 flex-shrink-0"></i>
                <div class="min-w-0">
                    <div class="text-sm font-semibold text-slate-900 truncate">${_esc(dev.name)}</div>
                    <div class="flex items-center gap-1.5 mt-0.5">
                        <span class="protocol-badge ${_pBadge(dev.protocol)}">${_pLabel(dev.protocol)}</span>
                        <span class="text-xs text-slate-400">${cnt} tag${cnt!==1?'s':''}</span>
                        ${isLC?'<span class="text-xs text-slate-400 italic">· view only</span>':''}
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
        i.querySelector('[data-check]').style.display = 'none';
    });
    el.classList.add('active');
    el.querySelector('[data-check]').style.display = '';

    const dev = _devices.find(d => String(d.id)===String(devId));
    if (!dev) return;
    _selectedDeviceId   = dev.id;
    _selectedDeviceData = dev;

    const prev = document.getElementById('modalSelectedPreview');
    if (prev) {
        prev.classList.remove('hidden');
        document.getElementById('previewDeviceName').textContent = dev.name;
        document.getElementById('previewDeviceProtocol').innerHTML =
            `<span class="protocol-badge ${_pBadge(dev.protocol)}">${_pLabel(dev.protocol)}</span>`;
    }

    const btn = document.getElementById('proceedToTagForm');
    if (btn) { btn.disabled=false; btn.style.opacity='1'; btn.style.cursor='pointer'; }
}

function _proceedToTagForm() {
    if (!_selectedDeviceData) { _toast('Select a device first','error'); return; }
    const proto = _selectedDeviceData.protocol;

    if (proto==='modbus-tcp'||proto==='modbus-rtu') {
        document.getElementById('modbusCtxDevice').textContent  = _selectedDeviceData.name;
        document.getElementById('modbusCtxProtocol').textContent = _pLabel(proto);
        _clearModbusForm('mb');
        _showStep('stepModbusForm');
    } else if (proto==='loadcell') {
        document.getElementById('lcCtxDevice').textContent = _selectedDeviceData.name;
        const lt = _tags.find(t => String(t.device_id)===String(_selectedDeviceId)&&t.tag_name==='load');
        document.getElementById('lcUnitDisplay').textContent = lt?.unit||'kg';
        _showStep('stepLoadcellInfo');
    } else {
        _toast('Unknown protocol: '+proto,'error');
    }
}

function _showStep(id) {
    ['stepDeviceSelect','stepModbusForm','stepLoadcellInfo'].forEach(s => {
        const el = document.getElementById(s);
        if (el) el.style.display = s===id?'block':'none';
    });
}

function _closeAddTagModal() {
    _hideModal('addTagModal');
    _selectedDeviceId = _selectedDeviceData = null;
}

// ─── CREATE TAG ───────────────────────────────────────────────────────────────

async function _handleModbusCreate(e) {
    e.preventDefault();
    const btn = e.submitter || e.target.querySelector('[type=submit]');
    const tagName = document.getElementById('mbTagName')?.value?.trim();
    const address = document.getElementById('mbRegAddress')?.value?.trim();

    if (!tagName)  { _toast('Tag name is required','error'); return; }
    if (!address)  { _toast('Register address is required','error'); return; }
    if (!_selectedDeviceId) { _toast('No device selected','error'); return; }

    // Duplicate check
    const dup = _tags.some(t =>
        String(t.device_id)===String(_selectedDeviceId) && t.tag_name===tagName
    );
    if (dup) { _toast(`"${tagName}" already exists for this device. Use a different name.`,'error'); return; }

    _setLoading(btn, true);
    const addr = parseInt(address,10);

    try {
        const resp = await fetch('/api/datapoints/modbus', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({
                device_id:        _selectedDeviceId,
                tag_name:         tagName,
                register_address: addr,
                register_type:    _regType(addr),
                data_type:        document.getElementById('mbDataType').value,
                byte_order:       document.getElementById('mbByteOrder').value,
                word_order:       document.getElementById('mbWordOrder').value,
                scale_factor:     parseFloat(document.getElementById('mbScale').value)||1.0,
                offset:           parseFloat(document.getElementById('mbOffset').value)||0.0,
                unit:             document.getElementById('mbUnit').value.trim(),
                description:      document.getElementById('mbDescription').value.trim(),
                enabled:          true
            })
        });
        const data = await resp.json();
        if (resp.ok) {
            _closeAddTagModal();
            await _loadData();
            _toast('Tag created successfully','success');
        } else {
            _toast(data.error||'Failed to create tag','error');
        }
    } catch(err) {
        console.error(err);
        _toast('Network error','error');
    } finally {
        _setLoading(btn, false);
    }
}

// ─── EDIT TAG (dispatch) ──────────────────────────────────────────────────────

function editTag(tagId, tagType) {
    const tag = _tags.find(t => t.id==tagId);
    if (!tag) { _toast('Tag not found','error'); return; }

    if (tagType==='loadcell') {
        _openEditLcModal(tag);
    } else {
        _openEditModbusModal(tag);
    }
}

// ─── EDIT MODBUS MODAL ────────────────────────────────────────────────────────

function _openEditModbusModal(tag) {
    const dev = _devices.find(d => String(d.id)===String(tag.device_id));

    document.getElementById('editMbTagId').value            = tag.id;
    document.getElementById('editMbCtxDevice').textContent  = tag.device_name||'—';
    document.getElementById('editMbCtxProtocol').innerHTML  = dev
        ? `<span class="protocol-badge ${_pBadge(dev.protocol)}">${_pLabel(dev.protocol)}</span>` : '—';

    document.getElementById('editMbTagName').value    = tag.tag_name||'';
    document.getElementById('editMbRegAddress').value = tag.register_address??'';
    document.getElementById('editMbDataType').value   = tag.data_type||'int16';
    document.getElementById('editMbByteOrder').value  = tag.byte_order||'big';
    document.getElementById('editMbWordOrder').value  = tag.word_order||'big';
    document.getElementById('editMbScale').value      = tag.scale_factor??1.0;
    document.getElementById('editMbOffset').value     = tag.offset??0.0;
    document.getElementById('editMbUnit').value       = tag.unit||'';
    document.getElementById('editMbDescription').value= tag.description||'';

    _autoDetect(tag.register_address,'editMbDetectedType');
    _showModal('editModbusModal');
}

async function _handleModbusEdit(e) {
    e.preventDefault();
    const btn    = e.submitter || e.target.querySelector('[type=submit]');
    const tagId  = document.getElementById('editMbTagId').value;
    const tagName= document.getElementById('editMbTagName').value.trim();
    const address= document.getElementById('editMbRegAddress').value.trim();

    if (!tagName) { _toast('Tag name is required','error'); return; }
    if (!address) { _toast('Register address is required','error'); return; }

    _setLoading(btn, true);
    const addr = parseInt(address,10);

    try {
        const resp = await fetch(`/api/datapoints/modbus/${tagId}`, {
            method: 'PUT',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({
                tag_name:         tagName,
                register_address: addr,
                register_type:    _regType(addr),
                data_type:        document.getElementById('editMbDataType').value,
                byte_order:       document.getElementById('editMbByteOrder').value,
                word_order:       document.getElementById('editMbWordOrder').value,
                scale_factor:     parseFloat(document.getElementById('editMbScale').value)||1.0,
                offset:           parseFloat(document.getElementById('editMbOffset').value)||0.0,
                unit:             document.getElementById('editMbUnit').value.trim(),
                description:      document.getElementById('editMbDescription').value.trim()
            })
        });
        const data = await resp.json();
        if (resp.ok) {
            _closeEditModbus();
            await _loadData();
            _toast('Tag updated successfully','success');
        } else {
            _toast(data.error||'Failed to update tag','error');
        }
    } catch(err) {
        console.error(err);
        _toast('Network error','error');
    } finally {
        _setLoading(btn, false);
    }
}

function _closeEditModbus() { _hideModal('editModbusModal'); }

// ─── EDIT LOADCELL MODAL ──────────────────────────────────────────────────────

function _openEditLcModal(tag) {
    document.getElementById('editLcTagId').value          = tag.id;
    document.getElementById('editLcCtxDevice').textContent= tag.device_name||'—';
    document.getElementById('editLcTagName').value        = tag.tag_name||'';
    
    // Set data type dropdown to current value, default to float32 if not set
    const dataTypeSelect = document.getElementById('editLcDataType');
    if (dataTypeSelect) {
        dataTypeSelect.value = tag.data_type || 'float32';
    }
    
    document.getElementById('editLcUnit').value           = tag.unit||'';
    _showModal('editLcModal');
}

async function _handleLcEdit(e) {
    e.preventDefault();
    const btn   = e.submitter || e.target.querySelector('[type=submit]');
    const tagId = document.getElementById('editLcTagId').value;
    const unit  = document.getElementById('editLcUnit').value.trim();
    const dataType = document.getElementById('editLcDataType').value;

    _setLoading(btn, true);
    try {
        // Try loadcell endpoint first
        const resp = await fetch(`/api/datapoints/loadcell/${tagId}`, {
            method: 'PUT',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ 
                unit,
                data_type: dataType 
            })
        });
        
        // Fallback: try modbus endpoint if loadcell endpoint 404s
        if (resp.status === 404 || resp.status === 405) {
            const resp2 = await fetch(`/api/datapoints/modbus/${tagId}`, {
                method: 'PUT',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({ 
                    unit,
                    data_type: dataType 
                })
            });
            const d2 = await resp2.json();
            if (resp2.ok) {
                _closeEditLc(); 
                await _loadData();
                _toast('Load cell tag updated successfully','success');
            } else {
                _toast(d2.error||'Failed to update load cell tag','error');
            }
            return;
        }
        
        const data = await resp.json();
        if (resp.ok) {
            _closeEditLc(); 
            await _loadData();
            _toast('Load cell tag updated successfully','success');
        } else {
            _toast(data.error||'Failed to update load cell tag','error');
        }
    } catch(err) {
        console.error(err);
        _toast('Network error','error');
    } finally {
        _setLoading(btn, false);
    }
}

function _closeEditLc() { _hideModal('editLcModal'); }

// ─── DELETE ───────────────────────────────────────────────────────────────────

async function deleteTag(tagId, tagType) {
    if (tagType==='loadcell') { 
        _toast('Load cell tags are auto-managed and cannot be deleted','info'); 
        return; 
    }
    if (!confirm('Delete this tag? This cannot be undone.')) return;

    try {
        const resp = await fetch(`/api/datapoints/${tagId}?type=${tagType}`,{method:'DELETE'});
        const data = await resp.json();
        if (resp.ok) { 
            await _loadData(); 
            _toast('Tag deleted','success'); 
        }
        else { 
            _toast(data.error||'Failed to delete','error'); 
        }
    } catch(err) {
        console.error(err); 
        _toast('Network error','error');
    }
}

// ─── CSV ──────────────────────────────────────────────────────────────────────

async function exportCSV() {
    if (!_tags.length) { _toast('No tags to export','info'); return; }
    const headers = ['device_name','device_type','tag_name','register_address','register_type','data_type','byte_order','word_order','scale_factor','offset','unit','description','enabled'];
    const rows = _tags.map(t => headers.map(h => {
        const v = t[h]??'';
        return typeof v==='string'&&v.includes(',') ? `"${v}"` : v;
    }).join(','));
    const csv  = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv],{type:'text/csv'});
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = `tags_export_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    _toast(`Exported ${_tags.length} tags`,'success');
}

async function importCSV() {
    const input = document.createElement('input');
    input.type  = 'file';
    input.accept= '.csv';
    input.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const text = await file.text();
        const lines = text.trim().split('\n');
        if (lines.length < 2) { _toast('CSV is empty','error'); return; }

        const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
        let imported  = 0, errors = 0;

        for (let i=1; i<lines.length; i++) {
            const cols    = lines[i].split(',').map(c => c.trim().replace(/^"|"$/g,''));
            const row     = {};
            headers.forEach((h,j) => { row[h] = cols[j]||''; });

            const devName = row['device_name']||row['device_id']||'';
            const dev     = _devices.find(d => d.name===devName||String(d.id)===devName);
            if (!dev) { errors++; continue; }

            const addr = parseInt(row['register_address']||'0',10);
            try {
                const resp = await fetch('/api/datapoints/modbus',{
                    method:'POST',
                    headers:{'Content-Type':'application/json'},
                    body: JSON.stringify({
                        device_id:        dev.id,
                        tag_name:         row['tag_name']||`tag_${i}`,
                        register_address: addr,
                        register_type:    row['register_type']||_regType(addr),
                        data_type:        row['data_type']||'int16',
                        byte_order:       row['byte_order']||'big',
                        word_order:       row['word_order']||'big',
                        scale_factor:     parseFloat(row['scale_factor'])||1.0,
                        offset:           parseFloat(row['offset'])||0.0,
                        unit:             row['unit']||'',
                        description:      row['description']||'',
                        enabled:          row['enabled']!=='false'
                    })
                });
                if (resp.ok) imported++; else errors++;
            } catch { errors++; }
        }

        await _loadData();
        _toast(`Imported ${imported} tag${imported!==1?'s':''}${errors?` · ${errors} skipped`:''}`, errors?'warning':'success');
    };
    input.click();
}

// ─── HELPERS ──────────────────────────────────────────────────────────────────

function _regType(n) {
    n = parseInt(n);
    if (isNaN(n))  return 'holding';
    if (n<=9999)   return 'coil';
    if (n<=19999)  return 'discrete';
    if (n<=29999)  return 'input';
    return 'holding';
}

function _autoDetect(val, elId) {
    const el = document.getElementById(elId);
    if (!el) return;
    const n = parseInt(val);
    if (isNaN(n)||val==='') { el.textContent='Enter address…'; el.style.color='#94a3b8'; return; }
    let label, color;
    if      (n<=9999)  { label='Coil (0–9999)';                color='#2563EB'; }
    else if (n<=19999) { label='Discrete Input (10000–19999)';  color='#16A34A'; }
    else if (n<=29999) { label='Input Register (20000–29999)';  color='#D97706'; }
    else if (n<=49999) { label='Holding Register (40000–49999)';color='#7C3AED'; }
    else               { label='Out of range';                  color='#DC2626'; }
    el.textContent = label; el.style.color = color;
}

function _clearModbusForm(prefix) {
    const ids = {
        [`${prefix}TagName`]:'', [`${prefix}RegAddress`]:'',
        [`${prefix}Scale`]:'1.0', [`${prefix}Offset`]:'0.0',
        [`${prefix}Unit`]:'', [`${prefix}Description`]:''
    };
    Object.entries(ids).forEach(([id,v]) => { const el=document.getElementById(id); if(el) el.value=v; });
    [`${prefix}DataType`,`${prefix}ByteOrder`,`${prefix}WordOrder`].forEach(id => {
        const el=document.getElementById(id); if(el) el.selectedIndex=0;
    });
    const det = document.getElementById(`${prefix}DetectedType`);
    if (det) { det.textContent='Enter address…'; det.style.color='#94a3b8'; }
}

function _setLoading(btn, loading) {
    if (!btn) return;
    if (loading) {
        btn._origHTML = btn.innerHTML;
        btn.disabled  = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Saving…';
    } else {
        btn.disabled  = false;
        btn.innerHTML = btn._origHTML || btn.innerHTML;
    }
}

function _pLabel(p)  { return {'modbus-tcp':'Modbus TCP','modbus-rtu':'Modbus RTU','loadcell':'Load Cell'}[p]||p?.toUpperCase()||'—'; }
function _pBadge(p)  { return p==='modbus-tcp'?'modbus-tcp':p==='modbus-rtu'?'modbus-rtu':'loadcell'; }
function _pClass(tag){ if(tag.type==='loadcell')return'loadcell'; const dt=(tag.device_type||'').toLowerCase(); return dt.includes('tcp')?'modbus-tcp':dt.includes('rtu')?'modbus-rtu':'modbus-tcp'; }
function _esc(s)     { return s==null?'':String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function _showModal(id){ const el=document.getElementById(id); if(el){el.style.display='flex';document.body.style.overflow='hidden';} }
function _hideModal(id){ const el=document.getElementById(id); if(el){el.style.display='none';document.body.style.overflow='';} }
function _vis(id)    { const el=document.getElementById(id); return el&&el.style.display==='flex'; }

function _toast(msg, type='info') {
    console.log(`[${type.toUpperCase()}] ${msg}`);
    if (typeof showNotification==='function') { showNotification(msg,type); return; }
    const existing = document.querySelectorAll('.tm-toast');
    const offset   = 24 + existing.length * 56;
    const colors   = {success:'#16A34A',error:'#DC2626',info:'#2563EB',warning:'#D97706'};
    const icons    = {success:'fa-check-circle',error:'fa-circle-xmark',info:'fa-circle-info',warning:'fa-triangle-exclamation'};
    const t = document.createElement('div');
    t.className = 'tm-toast';
    t.style.cssText = `position:fixed;bottom:${offset}px;right:24px;z-index:99999;
        background:${colors[type]||colors.info};color:white;
        padding:10px 16px;border-radius:8px;font-size:13px;font-weight:500;
        box-shadow:0 4px 16px rgba(0,0,0,0.25);display:flex;align-items:center;gap:8px;
        transition:opacity 0.3s,transform 0.3s;transform:translateX(0);min-width:220px;max-width:360px;`;
    t.innerHTML = `<i class="fa-solid ${icons[type]||icons.info} flex-shrink-0"></i><span>${_esc(msg)}</span>`;
    document.body.appendChild(t);
    setTimeout(()=>{ t.style.opacity='0'; t.style.transform='translateX(20px)'; setTimeout(()=>t.remove(),300); }, 3500);
}

// ─── EXPORTS ──────────────────────────────────────────────────────────────────
window.initializeModbusMapping = initializeModbusMapping;
window.editTag   = editTag;
window.deleteTag = deleteTag;
window.importCSV = importCSV;
window.exportCSV = exportCSV;