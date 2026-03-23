// mqtt-cloud.js    Cloud Connection Manager orchestrator
'use strict';

const API = '/api/cloud-integration';
let _connections  = [];
let _selectedId   = null;
let _selectedType = null;
let _availTags    = [];

// --- ENTRY --------------------------------------------------------------------
window.initMqttCloud = async function () {
    _bindPageListeners();
    await _loadConnections();
};

// --- LOAD LIST ----------------------------------------------------------------
async function _loadConnections() {
    try {
        const d = await _api('GET', `${API}/connections`);
        _connections = d.connections || [];
        _renderList();
        const target = _selectedId && _connections.find(c => c.id === _selectedId)
            ? _selectedId : (_connections[0]?.id || null);
        if (target) await _selectConnection(target);
        else _showEmpty();
    } catch { _toast('Failed to load connections', 'error'); }
}

// --- RENDER LIST --------------------------------------------------------------
function _renderList() {
    const list  = _el('connectionsList');
    const empty = _el('connectionsEmpty');
    if (!list) return;
    list.querySelectorAll('.conn-item').forEach(n => n.remove());
    _el('connectionCount').textContent = _connections.length;
    if (!_connections.length) { if (empty) empty.style.display = ''; return; }
    if (empty) empty.style.display = 'none';

    _connections.forEach(c => {
        const s   = c.statistics || {};
        const icon = { mqtt:'fa-cloud text-blue-500', ftp:'fa-folder-open text-emerald-500' }[c.type] || 'fa-plug';
        const div = document.createElement('div');
        div.className = `conn-item ${c.type}${c.id === _selectedId ? ' active' : ''}`;
        div.dataset.id = c.id;
        div.innerHTML = `
          <div class="flex items-center justify-between mb-1.5">
            <div class="flex items-center gap-2">
              <i class="fa-solid ${icon} text-xs"></i>
              <span class="font-medium text-slate-900 text-sm truncate max-w-[130px]">${_esc(c.name)}</span>
            </div>
            <span class="text-xs text-slate-400 flex-shrink-0">${_esc(s.lastActive||'Never')}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="cc-badge ${c.type}">${c.type.toUpperCase()}</span>
            <span class="text-xs px-2 py-0.5 rounded-full ${c.enabled?'bg-green-100 text-green-800':'bg-slate-100 text-slate-500'}">
              ${c.enabled?'Active':'Inactive'}
            </span>
          </div>`;
        div.addEventListener('click', () => _selectConnection(c.id));
        list.appendChild(div);
    });
}

// --- SELECT CONNECTION --------------------------------------------------------
async function _selectConnection(id) {
    _selectedId = id;
    document.querySelectorAll('.conn-item').forEach(el =>
        el.classList.toggle('active', el.dataset.id === id)
    );
    let conn;
    try {
        conn = await _api('GET', `${API}/connections/${id}`);
        const idx = _connections.findIndex(c => c.id === id);
        if (idx !== -1) _connections[idx] = conn;
    } catch { _toast('Failed to load connection', 'error'); return; }

    _updateStatusBar(conn);

    _showActionButtons(conn);
    await _loadForm(conn);
}

// --- LOAD FORM HTML -----------------------------------------------------------
async function _loadForm(conn) {
    const ph = _el('formPlaceholder');
    const fc = _el('formContent');
    if (!fc) return;

    // Remember which tab is currently active so we can restore it after reload
    const activeTabBtn = fc.querySelector?.('.tab-button.active');
    let _activeTabName = null;
    if (activeTabBtn) {
        const txt = activeTabBtn.textContent.trim().toLowerCase();
        if      (txt.startsWith('connection')) _activeTabName = 'connection';
        else if (txt.startsWith('channel') || txt.startsWith('topic')) _activeTabName = 'topics';
        else if (txt.startsWith('tag'))        _activeTabName = 'publishing';
        else if (txt.startsWith('advanced'))   _activeTabName = 'advanced';
    }

    ph.style.display = 'none';
    fc.classList.remove('hidden');
    fc.innerHTML = '<div class="p-10 text-center"><i class="fa-solid fa-spinner fa-spin text-primary text-2xl"></i></div>';

    const fileMap = {
        mqtt: 'pages/connection-forms/mqtt-form.html',
        ftp:  'pages/connection-forms/ftp-form.html',
    };
    const file = fileMap[conn.type];

    try {
        const r = await fetch(file);
        if (!r.ok) throw new Error(`${r.status}`);
        fc.innerHTML = await r.text();

        // Init form UI
        if (conn.type === 'mqtt' && typeof window.initializeMqttForm  === 'function') window.initializeMqttForm();
        if (conn.type === 'ftp'  && typeof window.initializeFtpForm   === 'function') window.initializeFtpForm();

        // Populate every field from DB
        if (conn.type === 'mqtt') _populateMqtt(conn);
        else _populateFtp(conn);

        // Override Save buttons to call real API
        _wireFormSaves(conn);

        // Wire Add Tags button
        _wireAddTagsBtn(conn);

        // Restore the previously active tab (prevents flicker back to Connection tab)
        if (_activeTabName && typeof switchMqttTab === 'function') {
            switchMqttTab(_activeTabName);
        }

    } catch {
        fc.innerHTML = `<div class="p-8 text-center text-slate-400 text-sm">
          <i class="fa-solid fa-triangle-exclamation text-amber-400 text-2xl mb-2 block"></i>
          Could not load <code>${file}</code>
        </div>`;
    }
}

// --- POPULATE MQTT ------------------------------------------------------------
function _populateMqtt(conn) {
    const c = conn.config || {};
    
    // SIMPLIFIED CONNECTION SETTINGS
    _sc('field-enabled',       c.enabled        ?? true);
    _sv('field-host',          c.host           ?? '127.0.0.1');
    _sv('field-port',          c.port           ?? 1883);
    _sv('field-clientId',      c.client_id      ?? _generateClientId());
    _sv('field-deviceToken',   c.device_token   ?? _generateDeviceToken());
    _sv('field-keepAlive',     c.keepalive_sec  ?? 60);
    _sv('field-username',      c.username       ?? '');
    _sv('field-password',      c.password       ?? '');
    
    // Channels
    const channels = c.channels || {};
    _renderPublishChannels(channels.publish   || []);
    _renderSubscribeChannels(channels.subscribe || []);
    
    // Mappings
    _renderMappingsTable(conn);
}

// --- GENERATE CLIENT ID -------------------------------------------------------
function _generateClientId() {
    return 'univa-gateway-' + Math.random().toString(36).substring(2, 10);
}

// --- GENERATE DEVICE TOKEN ----------------------------------------------------
function _generateDeviceToken() {
    return 'dev_' + Math.random().toString(36).substring(2, 10) + Math.random().toString(36).substring(2, 6);
}

// --- RENDER PUBLISH CHANNELS --------------------------------------------------
function _renderPublishChannels(list) {
    const tbody = _el('publish-channels-table');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!list.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="p-4 text-center text-slate-400 text-xs">No publish channels. Click "Add Publish Channel".</td></tr>`;
        return;
    }
    list.forEach((ch, idx) => {
        const tr = document.createElement('tr');
        tr.className = 'border-t border-slate-100';
        tr.dataset.idx = idx;
        tr.innerHTML = `
          <td class="p-2"><input type="text" class="compact-input text-xs ch-name"  value="${_esc(ch.name||'')}"  placeholder="channel name"></td>
          <td class="p-2"><input type="text" class="compact-input text-xs ch-topic" value="${_esc(ch.topic||'')}" placeholder="gateway/topic"></td>
          <td class="p-2 text-center">
            <select class="compact-select text-xs ch-qos">
              <option value="0" ${(ch.qos??0)===0?'selected':''}>0</option>
              <option value="1" ${ch.qos===1?'selected':''}>1</option>
              <option value="2" ${ch.qos===2?'selected':''}>2</option>
            </select>
          </td>
          <td class="p-2 text-center"><input type="checkbox" class="ch-retain" ${ch.retain?'checked':''}></td>
          <td class="p-2 text-center"><input type="radio" name="pub-default" class="ch-default" value="${idx}" ${ch.default?'checked':''}></td>
          <td class="p-2"><button class="text-red-500 hover:text-red-700 text-xs" onclick="this.closest('tr').remove()"><i class="fa-solid fa-trash"></i></button></td>`;
        tbody.appendChild(tr);
    });
}

// --- RENDER SUBSCRIBE CHANNELS ------------------------------------------------
function _renderSubscribeChannels(list) {
    const tbody = _el('subscribe-channels-table');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!list.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="p-4 text-center text-slate-400 text-xs">No subscribe channels. Click "Add Subscribe Channel".</td></tr>`;
        return;
    }
    list.forEach((ch, idx) => {
        const tr = document.createElement('tr');
        tr.className = 'border-t border-slate-100';
        tr.dataset.idx = idx;
        tr.innerHTML = `
          <td class="p-2"><input type="text" class="compact-input text-xs sch-name"  value="${_esc(ch.name||'')}"  placeholder="channel name"></td>
          <td class="p-2"><input type="text" class="compact-input text-xs sch-topic" value="${_esc(ch.topic||'')}" placeholder="gateway/topic"></td>
          <td class="p-2 text-center">
            <select class="compact-select text-xs sch-qos">
              <option value="0" ${(ch.qos??0)===0?'selected':''}>0</option>
              <option value="1" ${ch.qos===1?'selected':''}>1</option>
              <option value="2" ${ch.qos===2?'selected':''}>2</option>
            </select>
          </td>
          <td class="p-2 text-center"><input type="radio" name="sub-default" class="sch-default" value="${idx}" ${ch.default?'checked':''}></td>
          <td class="p-2"><button class="text-red-500 hover:text-red-700 text-xs" onclick="this.closest('tr').remove()"><i class="fa-solid fa-trash"></i></button></td>`;
        tbody.appendChild(tr);
    });
}

// --- ADD CHANNEL ROWS ---------------------------------------------------------
window._addPublishChannel = function () {
    const tbody = _el('publish-channels-table');
    if (!tbody) return;
    const empty = tbody.querySelector('td[colspan]');
    if (empty) empty.closest('tr').remove();
    const idx = tbody.querySelectorAll('tr').length;
    const tr = document.createElement('tr');
    tr.className = 'border-t border-slate-100';
    tr.dataset.idx = idx;
    tr.innerHTML = `
      <td class="p-2"><input type="text" class="compact-input text-xs ch-name"  placeholder="channel name"></td>
      <td class="p-2"><input type="text" class="compact-input text-xs ch-topic" placeholder="gateway/topic"></td>
      <td class="p-2 text-center">
        <select class="compact-select text-xs ch-qos">
          <option value="0" selected>0</option><option value="1">1</option><option value="2">2</option>
        </select>
      </td>
      <td class="p-2 text-center"><input type="checkbox" class="ch-retain"></td>
      <td class="p-2 text-center"><input type="radio" name="pub-default" class="ch-default" value="${idx}"></td>
      <td class="p-2"><button class="text-red-500 hover:text-red-700 text-xs" onclick="this.closest('tr').remove()"><i class="fa-solid fa-trash"></i></button></td>`;
    tbody.appendChild(tr);
};

window._addSubscribeChannel = function () {
    const tbody = _el('subscribe-channels-table');
    if (!tbody) return;
    const empty = tbody.querySelector('td[colspan]');
    if (empty) empty.closest('tr').remove();
    const idx = tbody.querySelectorAll('tr').length;
    const tr = document.createElement('tr');
    tr.className = 'border-t border-slate-100';
    tr.dataset.idx = idx;
    tr.innerHTML = `
      <td class="p-2"><input type="text" class="compact-input text-xs sch-name"  placeholder="channel name"></td>
      <td class="p-2"><input type="text" class="compact-input text-xs sch-topic" placeholder="gateway/topic"></td>
      <td class="p-2 text-center">
        <select class="compact-select text-xs sch-qos">
          <option value="0" selected>0</option><option value="1">1</option><option value="2">2</option>
        </select>
      </td>
      <td class="p-2 text-center"><input type="radio" name="sub-default" class="sch-default" value="${idx}"></td>
      <td class="p-2"><button class="text-red-500 hover:text-red-700 text-xs" onclick="this.closest('tr').remove()"><i class="fa-solid fa-trash"></i></button></td>`;
    tbody.appendChild(tr);
};

// --- RENDER MAPPINGS TABLE ----------------------------------------------------
// New and improved: groups as cards, individuals in table
function _renderMappingsTable(conn) {
    const groupsContainer = _el('groups-container');
    const individualSection = _el('individual-tags-section');
    const noMappingsMsg = _el('no-mappings-message');
    const individualTable = _el('individual-tags-table');
    
    if (!groupsContainer) return;
    
    const mappings = conn.config?.mappings || [];
    const groups = mappings.filter(m => !!m.alias);
    const individuals = mappings.filter(m => !m.alias);
    
    // Update stats
    _st('stat-group-count', groups.length);
    _st('stat-individual-count', individuals.reduce((sum, m) => sum + _flattenDatapoints(m.datapoints || {}).length, 0));
    
    if (!mappings.length) {
        noMappingsMsg.style.display = 'block';
        groupsContainer.style.display = 'none';
        individualSection.style.display = 'none';
        return;
    }
    
    noMappingsMsg.style.display = 'none';
    
    // Render Groups as Cards
    if (groups.length) {
        groupsContainer.style.display = 'block';
        // Build publish channel options for dropdowns
        const pubChannelOptions = _getPublishChannelOptions();
        groupsContainer.innerHTML = groups.map((mapping, idx) => {
            const points = _flattenDatapoints(mapping.datapoints || {});
            const groupId = `group-${idx}`;
            const currentChannel = mapping.channel || '';
            
            return `
                <div class="group-card border-2 border-blue-200 rounded-xl overflow-hidden bg-white shadow-sm" data-group-idx="${idx}">
                    <!-- Group Header   large prominent bar -->
                    <div class="bg-gradient-to-r from-blue-600 to-blue-500 px-4 py-3 flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <input type="checkbox" class="tag-select group-select w-4 h-4" data-group="${idx}" onchange="window._updateTagCount()">
                            <i class="fa-solid fa-layer-group text-black text-base"></i>
                            <span class="font-semibold text-black text-base">${_esc(mapping.alias)}</span>
                            <span class="bg-white/20 text-black text-xs px-2 py-0.5 rounded-full">${points.length} tag${points.length !== 1 ? 's' : ''}</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <button class="text-white/70 hover:text-white" onclick="window._toggleGroup('${groupId}')" title="Collapse / expand">
                                <i class="fa-solid fa-chevron-down text-sm"></i>
                            </button>
                            <button class="text-white/80 hover:text-white bg-white/15 hover:bg-white/25 rounded px-2 py-1 text-xs flex items-center gap-1"
                                    onclick="window._openGroupTagsModal('${_esc(conn.id)}', ${idx})" title="Add tags from device list">
                                <i class="fa-solid fa-plus text-xs"></i> Add Tags
                            </button>
                            <button class="text-white/80 hover:text-white bg-white/15 hover:bg-white/25 rounded px-2 py-1 text-xs flex items-center gap-1"
                                    onclick="window._editGroupName('${_esc(conn.id)}', ${idx}, '${_esc(mapping.alias)}')" title="Rename group">
                                <i class="fa-solid fa-pen text-xs"></i> Edit
                            </button>
                            <button class="text-white/70 hover:text-red-200" onclick="window._cloudRemoveMapping('${_esc(conn.id)}',${idx})" title="Remove group">
                                <i class="fa-solid fa-trash text-sm"></i>
                            </button>
                        </div>
                    </div>

                    <!-- Channel + Type Assignment Row (applies to ALL tags in this group) -->
                    <div class="bg-blue-50 border-b border-blue-100 px-4 py-2 flex items-center gap-4 flex-wrap">
                        <div class="flex items-center gap-2">
                            <i class="fa-solid fa-broadcast-tower text-blue-400 text-xs"></i>
                            <span class="text-xs font-semibold text-blue-700 whitespace-nowrap">Channel:</span>
                            <select class="compact-select text-xs group-channel-select"
                                    style="min-width:160px"
                                    data-conn="${_esc(conn.id)}" data-group-idx="${idx}"
                                    onchange="window._updateGroupChannel('${_esc(conn.id)}', ${idx}, this.value)">
                                <option value="">⚙️ default channel</option>
                                ${pubChannelOptions.filter(ch => ch.dir === 'publish').length ? `<optgroup label="📤 Publish">` : ''}
                                ${pubChannelOptions.filter(ch => ch.dir === 'publish').map(ch => `<option value="${_esc(ch.name)}" ${currentChannel === ch.name ? 'selected' : ''}>↗️ ${_esc(ch.name)}${ch.topic ? ' ('+_esc(ch.topic)+')' : ''}</option>`).join('')}
                                ${pubChannelOptions.filter(ch => ch.dir === 'publish').length ? `</optgroup>` : ''}
                                ${pubChannelOptions.filter(ch => ch.dir === 'subscribe').length ? `<optgroup label="📥 Subscribe">` : ''}
                                ${pubChannelOptions.filter(ch => ch.dir === 'subscribe').map(ch => `<option value="${_esc(ch.name)}" ${currentChannel === ch.name ? 'selected' : ''}>↙️ ${_esc(ch.name)}${ch.topic ? ' ('+_esc(ch.topic)+')' : ''}</option>`).join('')}
                                ${pubChannelOptions.filter(ch => ch.dir === 'subscribe').length ? `</optgroup>` : ''}
                                ${currentChannel && !pubChannelOptions.find(c => c.name === currentChannel)
                                    ? `<option value="${_esc(currentChannel)}" selected>📌 ${_esc(currentChannel)}</option>` : ''}
                            </select>
                        </div>
                        <div class="flex items-center gap-2">
                            <i class="fa-solid fa-tag text-blue-400 text-xs"></i>
                            <span class="text-xs font-semibold text-blue-700 whitespace-nowrap">Type (all tags):</span>
                            <select class="compact-select text-xs group-type-select"
                                    style="min-width:100px"
                                    data-group-idx="${idx}">
                                ${['int','float','string','bool'].map(t => {
                                    // Detect current common type from first tag
                                    const firstDtype = points[0]?.dtype || 'float';
                                    return `<option value="${t}" ${firstDtype===t?'selected':''}>${t}</option>`;
                                }).join('')}
                            </select>
                        </div>
                        <span class="text-xs text-blue-400 italic ml-auto">All tags share the same channel &amp; type</span>
                    </div>
                    
                    <!-- Group Tags Table -->
                    <div id="${groupId}" class="group-tags">
                        <table class="w-full text-xs">
                            <thead class="bg-slate-50 text-slate-500 border-b border-slate-100">
                                <tr>
                                    <th class="p-2 pl-8 w-8"></th>
                                    <th class="p-2 text-left font-medium">Tag Name</th>
                                    <th class="p-2 text-left font-medium w-36">Alias <span class="text-slate-400 font-normal">(optional)</span></th>
                                    <th class="p-2 text-left font-medium w-32">Type</th>
                                    <th class="p-2 text-center font-medium w-24">Channel</th>
                                    <th class="p-2 w-12"></th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-100">
                                ${points.map(({name, dtype, alias}) => `
                                    <tr class="hover:bg-slate-50" data-tag-row data-group-idx="${idx}" data-tag-name="${_esc(name)}">
                                        <td class="p-2 pl-8 w-8">
                                            <input type="checkbox" class="tag-select" data-tag="${_esc(name)}" data-group="${idx}" onchange="window._updateTagCount()">
                                        </td>
                                        <td class="p-2 font-mono text-xs">
                                            <i class="fa-regular fa-circle-dot text-blue-300 mr-1"></i>${_esc(name)}
                                        </td>
                                        <td class="p-2">
                                            <input type="text" class="compact-input text-xs tag-alias-input"
                                                   value="${_esc(alias||'')}"
                                                   placeholder="optional alias..."
                                                   data-tag="${_esc(name)}"
                                                   data-group-idx="${idx}"
                                                   title="Alias for this tag inside the group JSON (optional)">
                                        </td>
                                        <td class="p-2">
                                            <span class="text-xs text-slate-400 italic">via group</span>
                                        </td>
                                        <td class="p-2 text-center">
                                            <span class="text-xs text-slate-400 italic">via group</span>
                                        </td>
                                        <td class="p-2 w-12 text-center">
                                            <button class="text-red-400 hover:text-red-600" onclick="window._cloudRemoveTagFromMapping('${_esc(conn.id)}',${idx},'${_esc(name)}')" title="Remove tag">
                                                <i class="fa-solid fa-xmark"></i>
                                            </button>
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        }).join('');
    } else {
        groupsContainer.style.display = 'none';
    }
    
    // Render Individual Tags
    if (individuals.length) {
        individualSection.style.display = 'block';
        
        const allIndividualTags = [];
        individuals.forEach((mapping, mIdx) => {
            const points = _flattenDatapoints(mapping.datapoints || {});
            const alias  = mapping.alias || '';   // alias lives at top level for individuals
            points.forEach(({name, dtype}) => {
                allIndividualTags.push({
                    mappingIdx: mIdx,
                    name,
                    dtype,
                    alias,
                    channel: mapping.channel || ''
                });
            });
        });
        
        const pubChannelOptionsInd = _getPublishChannelOptions();
        individualTable.innerHTML = allIndividualTags.map((item, idx) => `
            <tr class="hover:bg-amber-50/50" data-individual-idx="${idx}" data-mapping-idx="${item.mappingIdx}" data-tag-name="${_esc(item.name)}">
                <td class="p-2">
                    <input type="checkbox" class="tag-select individual-select" data-tag="${_esc(item.name)}" onchange="window._updateTagCount()">
                </td>
                <td class="p-2 font-mono text-xs">
                    <i class="fa-regular fa-tag text-amber-400 mr-1"></i>${_esc(item.name)}
                </td>
                <td class="p-2">
                    <input type="text" class="compact-input text-xs tag-alias-input"
                           value="${_esc(item.alias)}"
                           placeholder="optional alias..."
                           data-tag="${_esc(item.name)}"
                           title="Alias for this tag in published JSON (optional)">
                </td>
                <td class="p-2">
                    <select class="compact-select text-xs tag-type-select" data-tag="${_esc(item.name)}" data-mapping-idx="${item.mappingIdx}">
                        <option value="int"    ${item.dtype==='int'    ?'selected':''}>int</option>
                        <option value="float"  ${item.dtype==='float'  ?'selected':''}>float</option>
                        <option value="string" ${item.dtype==='string' ?'selected':''}>string</option>
                        <option value="bool"   ${item.dtype==='bool'   ?'selected':''}>bool</option>
                    </select>
                </td>
                <td class="p-2">
                    <select class="compact-select text-xs tag-channel" data-mapping-idx="${item.mappingIdx}"
                            onchange="window._updateIndividualChannel('${_esc(conn.id)}', ${item.mappingIdx}, '${_esc(item.name)}', this.value)">
                        <option value="">⚙️ default</option>
                        ${pubChannelOptionsInd.filter(ch => ch.dir === 'publish').length ? `<optgroup label="📤 Publish">` : ''}
                        ${pubChannelOptionsInd.filter(ch => ch.dir === 'publish').map(ch => `<option value="${_esc(ch.name)}" ${item.channel === ch.name ? 'selected' : ''}>↗️ ${_esc(ch.name)}${ch.topic ? ' ('+_esc(ch.topic)+')' : ''}</option>`).join('')}
                        ${pubChannelOptionsInd.filter(ch => ch.dir === 'publish').length ? `</optgroup>` : ''}
                        ${pubChannelOptionsInd.filter(ch => ch.dir === 'subscribe').length ? `<optgroup label="📥 Subscribe">` : ''}
                        ${pubChannelOptionsInd.filter(ch => ch.dir === 'subscribe').map(ch => `<option value="${_esc(ch.name)}" ${item.channel === ch.name ? 'selected' : ''}>↙️ ${_esc(ch.name)}${ch.topic ? ' ('+_esc(ch.topic)+')' : ''}</option>`).join('')}
                        ${pubChannelOptionsInd.filter(ch => ch.dir === 'subscribe').length ? `</optgroup>` : ''}
                        ${item.channel && !pubChannelOptionsInd.find(c => c.name === item.channel)
                            ? `<option value="${_esc(item.channel)}" selected>📌 ${_esc(item.channel)}</option>` : ''}
                    </select>
                </td>
                <td class="p-2 text-center">
                    <button class="text-red-400 hover:text-red-600" onclick="window._cloudRemoveMapping('${_esc(conn.id)}',${item.mappingIdx})" title="Remove tag">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </td>
            </tr>
        `).join('');
    } else {
        individualSection.style.display = 'none';
    }
}

function _flattenDatapoints(dp) {
    const out = [];
    ['bool','int','float','string'].forEach(dtype => (dp[dtype]||[]).forEach(entry => {
        if (typeof entry === 'string') {
            out.push({ name: entry, dtype, alias: '' });
        } else {
            out.push({ name: entry.name, dtype, alias: entry.alias || '' });
        }
    }));
    return out;
}

// Default alias: last segment of dot-path, e.g. "loadcells.load.weight" -> "weight"
// Full name with dots replaced by underscores is also acceptable  user can edit it.
function _defaultAlias(tagName) {
    const parts = (tagName || '').split('.');
    return parts[parts.length - 1];
}

// Get all channels (publish + subscribe) for use in mapping dropdowns
function _getPublishChannelOptions() {
    return _getAllChannelOptions();
}

function _getAllChannelOptions() {
    const options = [];
    // Publish channels
    document.querySelectorAll('#publish-channels-table tr[data-idx]').forEach(tr => {
        const name = tr.querySelector('.ch-name')?.value.trim();
        const topic = tr.querySelector('.ch-topic')?.value.trim();
        if (name) options.push({ name, topic: topic || '', dir: 'publish' });
    });
    // Subscribe channels
    document.querySelectorAll('#subscribe-channels-table tr[data-idx]').forEach(tr => {
        const name = tr.querySelector('.sch-name')?.value.trim();
        const topic = tr.querySelector('.sch-topic')?.value.trim();
        if (name) options.push({ name, topic: topic || '', dir: 'subscribe' });
    });
    // Fallback to in-memory if tables not rendered yet
    if (!options.length && _selectedId) {
        const conn = _connections.find(c => c.id === _selectedId);
        (conn?.config?.channels?.publish || []).forEach(ch => {
            if (ch.name) options.push({ name: ch.name, topic: ch.topic || '', dir: 'publish' });
        });
        (conn?.config?.channels?.subscribe || []).forEach(ch => {
            if (ch.name) options.push({ name: ch.name, topic: ch.topic || '', dir: 'subscribe' });
        });
    }
    return options;
}

// Update group channel assignment live
window._updateGroupChannel = async function(connId, groupIdx, channel) {
    const conn = _connections.find(c => c.id === connId);
    if (!conn) return;
    const mappings = conn.config?.mappings || [];
    const groups = mappings.filter(m => !!m.alias);
    const mapping = groups[groupIdx];
    if (!mapping) return;
    if (channel) mapping.channel = channel;
    else delete mapping.channel;
    try {
        await _api('PUT', `${API}/connections/${connId}`, { config: { mappings } });
        _toast('Group channel updated', 'success');
    } catch { _toast('Update failed', 'error'); }
};

// Helper to update individual tag channel
window._updateIndividualChannel = async function(connId, mappingIdx, tagName, channel) {
    const conn = _connections.find(c => c.id === connId);
    if (!conn) return;
    
    const mappings = conn.config?.mappings || [];
    const mapping = mappings[mappingIdx];
    if (!mapping || !!mapping.alias) return; // Don't update groups here
    
    // Update the channel for this mapping
    if (channel) {
        mapping.channel = channel;
    } else {
        delete mapping.channel;
    }
    
    try {
        await _api('PUT', `${API}/connections/${connId}`, { config: { mappings } });
        // No need to reload, just update locally
        _toast('Channel updated', 'success');
    } catch {
        _toast('Update failed', 'error');
    }
};

// Toggle group expansion
window._toggleGroup = function(groupId) {
    const group = document.getElementById(groupId);
    const btn = event.currentTarget;
    if (group) {
        if (group.style.display === 'none') {
            group.style.display = 'block';
            btn.innerHTML = '<i class="fa-solid fa-chevron-down"></i>';
        } else {
            group.style.display = 'none';
            btn.innerHTML = '<i class="fa-solid fa-chevron-right"></i>';
        }
    }
};

// Collapse all groups
window.collapseAllGroups = function() {
    document.querySelectorAll('.group-tags').forEach(group => {
        group.style.display = 'none';
    });
    document.querySelectorAll('.group-card .fa-chevron-down').forEach(icon => {
        icon.className = 'fa-solid fa-chevron-right';
    });
};

// Expand all groups
window.expandAllGroups = function() {
    document.querySelectorAll('.group-tags').forEach(group => {
        group.style.display = 'block';
    });
    document.querySelectorAll('.group-card .fa-chevron-right').forEach(icon => {
        icon.className = 'fa-solid fa-chevron-down';
    });
};

// Toggle all individual tags
window.toggleAllIndividual = function() {
    const all = document.getElementById('select-all-individual');
    const isChecked = all?.checked || false;
    document.querySelectorAll('.individual-select').forEach(cb => {
        cb.checked = isChecked;
    });
    _updateTagCount();
};

// Remove selected tags (both from groups and individuals)
window.removeSelectedTags = async function() {
    const selected = document.querySelectorAll('.tag-select:checked');
    if (!selected.length) {
        _toast('No tags selected', 'error');
        return;
    }

    if (!confirm(`Remove ${selected.length} selected tag(s)?`)) return;

    if (!_selectedId) { _toast('No connection selected', 'error'); return; }
    const conn = _connections.find(c => c.id === _selectedId);
    if (!conn) { _toast('Connection not found', 'error'); return; }

    // Find the Remove Selected button for loading state
    const removeBtn = document.querySelector('button[onclick*="removeSelectedTags"]');
    _setLoading(removeBtn, true);

    try {
        // Deep-clone mappings so we can mutate safely
        let mappings = JSON.parse(JSON.stringify(conn.config?.mappings || []));
        const groups = mappings.filter(m => !!m.alias);

        // Collect what to remove, keyed by visual group index or individual tag name
        const groupsToDelete   = new Set();   // visual group indices (whole group removal)
        const groupTagsToStrip = {};          // visual group index -> Set of tag names
        const individualTags   = new Set();   // tag names for individual mappings

        selected.forEach(cb => {
            const rawGroup = cb.dataset.group;
            const tagName  = cb.dataset.tag;

            if (rawGroup !== undefined && !tagName) {
                // Group-header checkbox ? remove entire group
                groupsToDelete.add(parseInt(rawGroup));
            } else if (rawGroup !== undefined && tagName) {
                // Individual tag row inside a group
                const gi = parseInt(rawGroup);
                if (!groupTagsToStrip[gi]) groupTagsToStrip[gi] = new Set();
                groupTagsToStrip[gi].add(tagName);
            } else if (tagName) {
                // Row in the individual tags table
                individualTags.add(tagName);
            }
        });

        // 1. Process groups
        const updatedGroups = groups.map((mapping, visIdx) => {
            if (groupsToDelete.has(visIdx)) return null; // mark for full removal

            if (groupTagsToStrip[visIdx]) {
                const toStrip = groupTagsToStrip[visIdx];
                const dp = mapping.datapoints || {};
                ['bool', 'int', 'float', 'string'].forEach(dtype => {
                    if (dp[dtype]) dp[dtype] = dp[dtype].filter(entry => {
                        const n = typeof entry === 'string' ? entry : entry.name;
                        return !toStrip.has(n);
                    });
                });
                mapping.datapoints = dp;
            }
            return mapping;
        }).filter(Boolean);

        // 2. Process individual mappings  remove entries whose single tag is in the set
        const updatedIndividuals = mappings
            .filter(m => !m.alias)
            .filter(m => {
                const pts = _flattenDatapoints(m.datapoints || {});
                // Remove mapping if ALL its tags are in the individual removal set
                return !pts.every(p => individualTags.has(p.name));
            });

        const newMappings = [...updatedGroups, ...updatedIndividuals];

        await _api('PUT', `${API}/connections/${_selectedId}`, { config: { mappings: newMappings } });
        conn.config.mappings = newMappings;

        await _selectConnection(_selectedId);
        _toast(`${selected.length} tag(s) removed`, 'success');
    } catch (err) {
        console.error('removeSelectedTags error:', err);
        _toast('Failed to remove tags', 'error');
    } finally {
        _setLoading(removeBtn, false);
    }
};

// Update the _updateTagCount function to handle the new structure
window._updateTagCount = function() {
    const n = document.querySelectorAll('.tag-select:checked').length;
    const el = document.getElementById('selected-tags-count');
    if (el) el.textContent = n;
    
    // Update select all in individual table
    const individualCheckboxes = document.querySelectorAll('.individual-select');
    const checkedIndividuals = document.querySelectorAll('.individual-select:checked');
    const selectAll = document.getElementById('select-all-individual');
    if (selectAll) {
        if (individualCheckboxes.length > 0) {
            selectAll.checked = individualCheckboxes.length === checkedIndividuals.length;
            selectAll.indeterminate = checkedIndividuals.length > 0 && checkedIndividuals.length < individualCheckboxes.length;
        }
    }
};

// --- POPULATE FTP -------------------------------------------------------------
function _populateFtp(conn) {
    const c = conn.config || {};
    _sv('field-host',            c.host            ?? '');
    _sv('field-port',            c.port            ?? 21);
    _sv('field-protocol',        c.protocol        ?? 'ftp');
    _sv('field-mode',            c.mode            ?? 'passive');
    _sv('field-username',        c.username        ?? '');
    _sv('field-password',        c.password        ?? '');
    _sc('field-anonymous',       c.anonymous       ?? false);
    _sv('field-remotePath',      c.remotePath      ?? '/uploads/');
    _sv('field-filenamePattern', c.filenamePattern ?? 'data_${DATE}.csv');
    _sv('field-fileFormat',      c.fileFormat      ?? 'csv');
    _sv('field-maxFileSize',     c.maxFileSize     ?? 10485760);
    _sv('field-uploadInterval',  c.uploadInterval  ?? 300);
    _sc('field-appendMode',      c.appendMode      ?? true);
    _sc('field-compressFiles',   c.compressFiles   ?? true);
    _sv('field-retryAttempts',   c.retryAttempts   ?? 3);
}

// --- WIRE SAVE BUTTONS --------------------------------------------------------
function _wireFormSaves(conn) {
    if (conn.type === 'mqtt') {
        if (!window.mqttFormLogic) window.mqttFormLogic = {};
        window.mqttFormLogic.saveMqttConnectionSettings = () => _saveMqttConnection(conn.id);
        window.mqttFormLogic.saveMqttChannelSettings = () => _saveMqttChannels(conn.id);
        window.mqttFormLogic.saveMqttPublishingSettings = () => _saveMqttPublishing(conn.id);
    } else {
        if (!window.ftpFormLogic) window.ftpFormLogic = {};
        window.ftpFormLogic.saveFtpSettings = () => _saveFtp(conn.id);
        const saveBtn = _el('ftp-save-btn');
        if (saveBtn) saveBtn.onclick = () => _saveFtp(conn.id);
    }
}

// --- WIRE ADD TAGS BTN --------------------------------------------------------
function _wireAddTagsBtn(conn) {
    const openFn = () => _openTagsModal(conn);
    window.showAddTagModal = openFn;
    if (!window.mqttFormLogic) window.mqttFormLogic = {};
    
    // Add all the new methods
    Object.assign(window.mqttFormLogic, {
        showAddTagModal: openFn,
        collapseAllGroups:    window.collapseAllGroups    || function() {},
        expandAllGroups:      window.expandAllGroups      || function() {},
        toggleAllIndividual:  window.toggleAllIndividual  || function() {},
        removeSelectedTags:   () => window.removeSelectedTags(),
    });

    window.removeKeyValueItem = btn => btn.closest('.key-value-item')?.remove();
    window.addKeyValueItem    = btn => {
        const list = btn.closest('.key-value-list');
        const div  = document.createElement('div');
        div.className = 'key-value-item';
        div.innerHTML = `<input type="text" placeholder="Header Name" class="compact-input"><input type="text" placeholder="Value" class="compact-input"><button type="button" class="text-red-600" onclick="window.removeKeyValueItem(this)"><i class="fa-solid fa-trash"></i></button>`;
        list?.insertBefore(div, btn.closest('.p-2') || null);
    };
    window.generatePassword = id => {
        const el = _el(id);
        if (el) el.value = [...crypto.getRandomValues(new Uint8Array(12))].map(b=>'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*'[b%72]).join('');
    };

    // Expose custom-tag modal opener so mqtt-form.html button can call it
    window.mqttFormLogic = window.mqttFormLogic || {};
    window.mqttFormLogic.openCustomTagModal = () => _openCustomTagModal(conn);
}

// --- SAVE: MQTT CONNECTION ----------------------------------------------------
async function _saveMqttConnection(id) {
    await _putCfg(id, {
        enabled:       _gc('field-enabled'),
        host:          _gv('field-host') || '127.0.0.1',
        port:          +_gv('field-port') || 1883,
        client_id:     _gv('field-clientId') || _generateClientId(),
        device_token:  _gv('field-deviceToken') || _generateDeviceToken(),
        keepalive_sec: +_gv('field-keepAlive') || 60,
        username:      _gv('field-username'),
        password:      _gv('field-password'),
    }, 'Connection settings saved');
}

// --- SAVE: MQTT CHANNELS ------------------------------------------------------
async function _saveMqttChannels(id) {
    // Save channels (publish + subscribe arrays)
    const publish = [];
    document.querySelectorAll('#publish-channels-table tr[data-idx]').forEach(tr => {
        publish.push({
            name:    tr.querySelector('.ch-name')?.value.trim()  || '',
            topic:   tr.querySelector('.ch-topic')?.value.trim() || '',
            qos:     +(tr.querySelector('.ch-qos')?.value  ?? 0),
            retain:  tr.querySelector('.ch-retain')?.checked ?? false,
            default: tr.querySelector('.ch-default')?.checked ?? false,
        });
    });
    const subscribe = [];
    document.querySelectorAll('#subscribe-channels-table tr[data-idx]').forEach(tr => {
        subscribe.push({
            name:    tr.querySelector('.sch-name')?.value.trim()  || '',
            topic:   tr.querySelector('.sch-topic')?.value.trim() || '',
            qos:     +(tr.querySelector('.sch-qos')?.value  ?? 0),
            default: tr.querySelector('.sch-default')?.checked ?? false,
        });
    });
    await _putCfg(id, { channels: { publish, subscribe } }, 'Channel settings saved');
}

// --- SAVE: MQTT PUBLISHING (MAPPINGS) -----------------------------------------
async function _saveMqttPublishing(id) {
    const conn = _connections.find(c => c.id === id);
    if (!conn) return;
    const existingMappings = conn.config?.mappings || [];
    const updatedMappings = [];

    // -- PASS 1: groups go through as-is; collect individual tags into buckets --
    // bucket key: "channel||dtype"  ?  [tagName, ...]
    const individualBuckets = {};   // key ? { channel, dtype, names[] }

    existingMappings.forEach((mapping, mIdx) => {
        const isGroup = !!mapping.alias;

        if (isGroup) {
            // GROUP: per-tag alias lives INSIDE datapoints as {name, alias} if set, else plain string
            const visualIdx   = _getGroupVisualIdx(existingMappings, mIdx);
            const typeSel     = document.querySelector(`.group-type-select[data-group-idx="${visualIdx}"]`);
            const dtype       = typeSel ? typeSel.value : _detectGroupType(mapping.datapoints);
            const allTagNames = _flattenDatapoints(mapping.datapoints || {}).map(p => p.name);
            const tagEntries  = allTagNames.map(name => {
                const aliasInput = document.querySelector(`.tag-alias-input[data-tag="${CSS.escape(name)}"][data-group-idx="${visualIdx}"]`);
                const alias      = aliasInput?.value.trim() || '';
                // alias entered ? {name, alias} inside datapoints; no alias ? plain string
                return alias ? { name, alias } : name;
            });
            const { type: _drop, ...mappingWithoutType } = mapping;
            updatedMappings.push({ ...mappingWithoutType, datapoints: { [dtype]: tagEntries } });
        }
    });

    // -- INDIVIDUAL tags: read directly from every DOM row in the individual table --
    // This is more reliable than iterating existingMappings because:
    //   1. After a previous save, multiple tags can share the same mapping-idx
    //   2. data-tag-name lookup can collide with group table rows
    // Each individual tag gets its own mapping entry.
    // alias moves to top-level; datapoints contains plain string or {name} object.
    // No alias entered ? plain string inside datapoints, no alias key at top.
    document.querySelectorAll('#individual-tags-table tr[data-individual-idx]').forEach(row => {
        const tagName = row.dataset.tagName;
        if (!tagName) return;
        const typeSel    = row.querySelector('.tag-type-select');
        const chSel      = row.querySelector('.tag-channel');
        const aliasInput = row.querySelector('.tag-alias-input');
        const dtype      = typeSel?.value || 'float';
        const channel    = chSel?.value.trim() || '';
        const alias      = aliasInput?.value.trim();
        // alias typed ? {name, alias} object inside datapoints (alias lives INSIDE, not top-level)
        // no alias     ? plain string inside datapoints, no alias key anywhere
        const tagEntry   = alias ? { name: tagName, alias } : tagName;
        const entry      = { datapoints: { [dtype]: [tagEntry] } };
        if (channel) entry.channel = channel;
        updatedMappings.push(entry);
    });

    await _putCfg(id, { mappings: updatedMappings }, 'Mapping settings saved');
}

// Get the visual (groups-only) index for a group mapping
function _getGroupVisualIdx(mappings, targetMIdx) {
    let gIdx = 0;
    for (let i = 0; i < mappings.length; i++) {
        if (mappings[i].alias) {
            if (i === targetMIdx) return gIdx;
            gIdx++;
        }
    }
    return 0;
}

// Detect the dominant type from existing datapoints (first non-empty bucket)
function _detectGroupType(dp) {
    for (const t of ['float','int','string','bool']) {
        if (dp && dp[t] && dp[t].length) return t;
    }
    return 'float';
}

// --- SAVE: FTP ----------------------------------------------------------------
async function _saveFtp(id) {
    const cfg = {
        host:            _gv('field-host'),
        port:            +_gv('field-port') || 21,
        protocol:        _gv('field-protocol'),
        mode:            _gv('field-mode'),
        username:        _gv('field-username'),
        password:        _gv('field-password'),
        anonymous:       _gc('field-anonymous'),
        remotePath:      _gv('field-remotePath'),
        filenamePattern: _gv('field-filenamePattern'),
        fileFormat:      _gv('field-fileFormat'),
        maxFileSize:     +_gv('field-maxFileSize') || 10485760,
        uploadInterval:  +_gv('field-uploadInterval') || 300,
        appendMode:      _gc('field-appendMode'),
        compressFiles:   _gc('field-compressFiles'),
        retryAttempts:   +_gv('field-retryAttempts') || 3,
    };
    await _putCfg(id, cfg, 'FTP settings saved');
}

// --- SHARED SAVE HELPER -------------------------------------------------------
async function _putCfg(id, cfg, msg) {
    try {
        await _api('PUT', `${API}/connections/${id}`, { config: cfg });
        const idx = _connections.findIndex(c=>c.id===id);
        if (idx !== -1) _connections[idx].config = { ...(_connections[idx].config||{}), ...cfg };
        _toast(msg, 'success');
    } catch { _toast('Save failed', 'error'); }
}

// --- REMOVE MAPPING -----------------------------------------------------------
window._cloudRemoveMapping = async function (connId, mappingIdx) {
    const conn = _connections.find(c => c.id === connId);
    if (!conn) return;
    const mappings = conn.config?.mappings || [];
    const label = mappings[mappingIdx]?.alias || mappings[mappingIdx]?.datapoints ? JSON.stringify(mappings[mappingIdx]?.datapoints).substring(0,30) : `mapping #${mappingIdx + 1}`;
    if (!confirm(`Remove "${label}"?`)) return;
    mappings.splice(mappingIdx, 1);
    try {
        await _api('PUT', `${API}/connections/${connId}`, { config: { mappings } });
        await _selectConnection(connId);
        _toast('Mapping removed', 'success');
    } catch { _toast('Remove failed', 'error'); }
};

// --- REMOVE SINGLE TAG FROM GROUP MAPPING ------------------------------------
window._cloudRemoveTagFromMapping = async function (connId, mappingIdx, tagName) {
    const conn = _connections.find(c => c.id === connId);
    if (!conn || !confirm(`Remove tag "${tagName}"?`)) return;
    const mappings = conn.config?.mappings || [];
    const dp = mappings[mappingIdx]?.datapoints || {};
    ['bool','int','float','string'].forEach(dtype => {
        if (dp[dtype]) dp[dtype] = dp[dtype].filter(n => (typeof n === 'string' ? n : n.name) !== tagName);
    });
    try {
        await _api('PUT', `${API}/connections/${connId}`, { config: { mappings } });
        await _selectConnection(connId);
        _toast(`Tag "${tagName}" removed`, 'success');
    } catch { _toast('Remove failed', 'error'); }
};

// --- RENAME GROUP -------------------------------------------------------------
window._editGroupName = async function(connId, groupVisualIdx, currentAlias) {
    const newAlias = prompt('Rename group:', currentAlias);
    if (!newAlias || newAlias.trim() === '' || newAlias.trim() === currentAlias) return;

    const conn = _connections.find(c => c.id === connId);
    if (!conn) return;

    const mappings = conn.config?.mappings || [];
    const groups   = mappings.filter(m => !!m.alias);
    const mapping  = groups[groupVisualIdx];
    if (!mapping) return;

    // Find real index in full mappings array
    let realIdx = -1, gCount = 0;
    for (let i = 0; i < mappings.length; i++) {
        if (mappings[i].alias) {
            if (gCount === groupVisualIdx) { realIdx = i; break; }
            gCount++;
        }
    }
    if (realIdx === -1) { _toast('Group not found', 'error'); return; }

    const updatedMappings = mappings.map((m, i) =>
        i === realIdx ? { ...m, alias: newAlias.trim() } : m
    );

    try {
        await _api('PUT', `${API}/connections/${connId}`, { config: { mappings: updatedMappings } });
        conn.config.mappings = updatedMappings;
        await _selectConnection(connId);
        _toast(`Group renamed to "${newAlias.trim()}"`, 'success');
    } catch { _toast('Rename failed', 'error'); }
};

// --- CUSTOM TAG MODAL ---------------------------------------------------------
// Opens a small modal to type a free-form tag name and add it as an individual mapping.
function _openCustomTagModal(conn) {
    // Remove any stale instance
    const stale = _el('customTagModal');
    if (stale) stale.remove();

    const chOptions = _getPublishChannelOptions();
    const chOptHtml = [
        '<option value="">default channel</option>',
        ...chOptions.filter(ch => ch.dir === 'publish').map(ch =>
            `<option value="${_esc(ch.name)}">⬆ ${_esc(ch.name)}${ch.topic ? ' ('+_esc(ch.topic)+')' : ''}</option>`),
        ...chOptions.filter(ch => ch.dir === 'subscribe').map(ch =>
            `<option value="${_esc(ch.name)}">⬇ ${_esc(ch.name)}${ch.topic ? ' ('+_esc(ch.topic)+')' : ''}</option>`),
    ].join('');

    const modal = document.createElement('div');
    modal.id = 'customTagModal';
    modal.style.cssText = 'position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.45);backdrop-filter:blur(2px);';
    modal.innerHTML = `
        <div style="background:#fff;border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,0.25);width:100%;max-width:420px;margin:0 16px;overflow:hidden;">
            <!-- Header -->
            <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid #E2E8F0;">
                <div style="display:flex;align-items:center;gap:8px;">
                    <i class="fa-solid fa-wand-magic-sparkles" style="color:#8B5CF6;"></i>
                    <span style="font-weight:600;font-size:14px;color:#1E293B;">Custom Tag</span>
                </div>
                <button id="closeCustomTagModal" style="background:none;border:none;cursor:pointer;color:#94A3B8;font-size:17px;line-height:1;">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>

            <!-- Body -->
            <div style="padding:18px;display:flex;flex-direction:column;gap:14px;">
                <p style="font-size:12px;color:#64748B;margin:0;">
                    Define a tag with any name you choose. It will be added as an individual mapping.
                </p>

                <!-- Tag name -->
                <div>
                    <label style="display:block;font-size:12px;font-weight:500;color:#475569;margin-bottom:5px;">
                        <i class="fa-solid fa-tag" style="color:#8B5CF6;margin-right:4px;"></i>Tag Name <span style="color:#F87171;">*</span>
                    </label>
                    <input id="customTagName" type="text" class="compact-input"
                           style="width:100%;box-sizing:border-box;"
                           placeholder="e.g. crane.load.weight, custom_sensor_01">
                </div>

                <!-- Data type -->
                <div>
                    <label style="display:block;font-size:12px;font-weight:500;color:#475569;margin-bottom:5px;">
                        <i class="fa-solid fa-code" style="color:#94A3B8;margin-right:4px;"></i>Data Type
                    </label>
                    <select id="customTagDtype" class="compact-select" style="width:100%;box-sizing:border-box;">
                        <option value="float" selected>float</option>
                        <option value="int">int</option>
                        <option value="string">string</option>
                        <option value="bool">bool</option>
                    </select>
                </div>

                <!-- Channel -->
                <div>
                    <label style="display:block;font-size:12px;font-weight:500;color:#475569;margin-bottom:5px;">
                        <i class="fa-solid fa-broadcast-tower" style="color:#94A3B8;margin-right:4px;"></i>Channel
                    </label>
                    <select id="customTagChannel" class="compact-select" style="width:100%;box-sizing:border-box;">${chOptHtml}</select>
                </div>
            </div>

            <!-- Footer -->
            <div style="display:flex;align-items:center;justify-content:flex-end;gap:10px;padding:12px 18px;border-top:1px solid #E2E8F0;background:#F8FAFC;">
                <button id="cancelCustomTag" class="compact-button" style="border:1px solid #CBD5E1;color:#475569;background:#fff;">
                    Cancel
                </button>
                <button id="confirmCustomTag" class="compact-button" style="background:#8B5CF6;color:#fff;">
                    <i class="fa-solid fa-plus" style="margin-right:4px;"></i> Add Tag
                </button>
            </div>
        </div>`;

    document.body.appendChild(modal);

    // Focus the input
    setTimeout(() => _el('customTagName')?.focus(), 50);

    const close = () => { modal.remove(); document.body.style.overflow = ''; };

    _el('closeCustomTagModal').onclick = close;
    _el('cancelCustomTag').onclick     = close;
    modal.addEventListener('click', e => { if (e.target === modal) close(); });
    document.addEventListener('keydown', function _esc_handler(e) {
        if (e.key === 'Escape') { close(); document.removeEventListener('keydown', _esc_handler); }
    });

    _el('confirmCustomTag').onclick = async () => {
        const tagName = (_el('customTagName')?.value || '').trim();
        if (!tagName) {
            _el('customTagName').style.borderColor = '#F87171';
            _el('customTagName').focus();
            return;
        }
        const dtype   = _el('customTagDtype')?.value  || 'float';
        const channel = _el('customTagChannel')?.value || '';

        const existingMappings = (_connections.find(c => c.id === conn.id)?.config?.mappings) || [];
        const newEntry = { datapoints: { [dtype]: [tagName] } };
        if (channel) newEntry.channel = channel;
        const newMappings = [...existingMappings, newEntry];

        const btn = _el('confirmCustomTag');
        _setLoading(btn, true);
        try {
            await _api('PUT', `${API}/connections/${conn.id}`, { config: { mappings: newMappings } });
            close();
            await _selectConnection(conn.id);
            _toast(`Custom tag "${tagName}" added`, 'success');
        } catch {
            _toast('Failed to add custom tag', 'error');
        } finally {
            _setLoading(btn, false);
        }
    };
}

// --- ADD TAGS MODAL -----------------------------------------------------------
async function _openTagsModal(conn) {
    _showM('addTagsModal');
    _el('tagsSelectedCount').textContent = '0';
    _el('tagsModalBody').innerHTML = '<tr><td colspan="6" class="p-6 text-center text-slate-400"><i class="fa-solid fa-spinner fa-spin mr-2"></i>Loading tags...</td></tr>';

    // Inject mode controls (group vs individual) + channel select
    const chOptions = _getPublishChannelOptions();
    const chOptHtml = [
        '<option value="">⚙️ default channel</option>',
        chOptions.filter(ch => ch.dir === 'publish').length ? '<optgroup label="📤 Publish">' : '',
        ...chOptions.filter(ch => ch.dir === 'publish').map(ch =>
            `<option value="${_esc(ch.name)}">↗️ ${_esc(ch.name)}${ch.topic ? ' ('+_esc(ch.topic)+')':''}</option>`),
        chOptions.filter(ch => ch.dir === 'publish').length ? '</optgroup>' : '',
        chOptions.filter(ch => ch.dir === 'subscribe').length ? '<optgroup label="📥 Subscribe">' : '',
        ...chOptions.filter(ch => ch.dir === 'subscribe').map(ch =>
            `<option value="${_esc(ch.name)}">↙️ ${_esc(ch.name)}${ch.topic ? ' ('+_esc(ch.topic)+')':''}</option>`),
        chOptions.filter(ch => ch.dir === 'subscribe').length ? '</optgroup>' : '',
    ].join('');

    if (!_el('modal-mapping-controls')) {
        const footer = _el('tagsCancel')?.closest('div');
        if (footer) {
            const ctrl = document.createElement('div');
            ctrl.id = 'modal-mapping-controls';
            ctrl.innerHTML = `
                <div class="border-t border-slate-200 px-5 pt-4 pb-2">
                    <!-- Mode toggle -->
                    <div class="flex gap-2 mb-4">
                        <button id="modal-mode-individual" onclick="window._setModalMode('individual')"
                                class="modal-mode-btn active flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg border-2 border-amber-400 bg-amber-50 text-amber-700 text-xs font-semibold transition-all">
                            <i class="fa-regular fa-tag"></i> Individual Tags
                        </button>
                        <button id="modal-mode-group" onclick="window._setModalMode('group')"
                                class="modal-mode-btn flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg border-2 border-slate-200 bg-white text-slate-500 text-xs font-semibold transition-all">
                            <i class="fa-solid fa-layer-group"></i> Group
                        </button>
                    </div>
                    <!-- Group alias (shown only in group mode) -->
                    <div id="modal-group-fields" style="display:none" class="mb-3">
                        <label class="block text-xs font-medium text-slate-600 mb-1">
                            <i class="fa-solid fa-layer-group text-blue-500 mr-1"></i>Group Name <span class="text-red-400">*</span>
                        </label>
                        <input id="modal-alias-input" type="text" class="compact-input w-full"
                               placeholder="e.g. crane_sensors, motor_group">
                        <p class="text-xs text-slate-400 mt-1">All selected tags publish together under this name</p>
                    </div>
                    <!-- Channel select (always shown) -->
                    <div>
                        <label class="block text-xs font-medium text-slate-600 mb-1">
                            <i class="fa-solid fa-broadcast-tower text-slate-400 mr-1"></i>Channel
                        </label>
                        <select id="modal-channel-input" class="compact-select w-full">${chOptHtml}</select>
                    </div>
                </div>`;
            footer.parentElement.insertBefore(ctrl, footer);
        }
    } else {
        // Reset on re-open, refresh channel options
        _sv('modal-alias-input', '');
        const chSel = _el('modal-channel-input');
        if (chSel) chSel.innerHTML = chOptHtml;
        window._setModalMode('individual');
    }

    // Mode switcher
    window._setModalMode = function(mode) {
        const isGroup = mode === 'group';
        const gFields = _el('modal-group-fields');
        const btnInd  = _el('modal-mode-individual');
        const btnGrp  = _el('modal-mode-group');
        if (gFields) gFields.style.display = isGroup ? 'block' : 'none';
        if (btnInd) {
            btnInd.className = `modal-mode-btn flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg border-2 text-xs font-semibold transition-all ${!isGroup ? 'border-amber-400 bg-amber-50 text-amber-700' : 'border-slate-200 bg-white text-slate-500'}`;
        }
        if (btnGrp) {
            btnGrp.className = `modal-mode-btn flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg border-2 text-xs font-semibold transition-all ${isGroup ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-slate-200 bg-white text-slate-500'}`;
        }
    };
    window._setModalMode('individual');

    try {
        const d = await _api('GET', `${API}/available-tags`);
        _availTags = d.tags || [];
        _renderTagsModal(_availTags);
    } catch { 
        _el('tagsModalBody').innerHTML = '<tr><td colspan="5" class="p-4 text-center text-red-400">Failed to load tags</td></tr>'; 
    }

    _el('tagSearch').oninput = e => {
        const q = e.target.value.toLowerCase();
        _renderTagsModal(_availTags.filter(t => t.name.toLowerCase().includes(q) || (t.device||'').toLowerCase().includes(q)));
    };
    
    _el('selectAllTags').onchange = e => { 
        document.querySelectorAll('.modal-tag-cb').forEach(cb => cb.checked = e.target.checked); 
        _updateTagCount(); 
    };
    
    _el('tagsCancel').onclick     = () => _hideM('addTagsModal');
    _el('closeTagsModal').onclick = () => _hideM('addTagsModal');
    
    _el('tagsConfirm').onclick    = async () => {
        const checked = [...document.querySelectorAll('.modal-tag-cb:checked')];
        if (!checked.length) { 
            _toast('Select at least one tag', 'error'); 
            return; 
        }

        const alias   = _gv('modal-alias-input').trim();
        const channel = _gv('modal-channel-input').trim();
        const existingMappings = (_connections.find(c => c.id === conn.id)?.config?.mappings) || [];
        let newMappings;

        if (alias) {
            // -- GROUP: all selected tags in one mapping, dtype from type-select per row --
            const datapoints = {};
            checked.forEach(cb => {
                const dtype = cb.dataset.dtype || 'float';
                if (!datapoints[dtype]) datapoints[dtype] = [];
                datapoints[dtype].push(cb.dataset.tag);
            });
            const newMapping = { alias, datapoints };
            if (channel) newMapping.channel = channel;
            newMappings = [...existingMappings, newMapping];
        } else {
            // INDIVIDUAL: one mapping entry per tag
            const addedMappings = [];
            checked.forEach(cb => {
                const dtype = cb.dataset.dtype || 'float';
                const m = { datapoints: { [dtype]: [cb.dataset.tag] } };
                if (channel) m.channel = channel;
                addedMappings.push(m);
            });
            newMappings = [...existingMappings, ...addedMappings];
        }

        _setLoading(_el('tagsConfirm'), true);
        try {
            await _api('PUT', `${API}/connections/${conn.id}`, { config: { mappings: newMappings } });
            _hideM('addTagsModal');
            await _selectConnection(conn.id);
            if (alias) {
                _toast(`${checked.length} tag(s) added to group "${alias}"`, 'success');
            } else {
                _toast(`${checked.length} tag(s) added as individual mappings`, 'success');
            }
        } catch { 
            _toast('Failed to add tags', 'error'); 
        }
        finally { 
            _setLoading(_el('tagsConfirm'), false); 
        }
    };
}
// --- ADD TAGS TO EXISTING GROUP -----------------------------------------------
window._openGroupTagsModal = async function(connId, groupVisualIdx) {
    const conn = _connections.find(c => c.id === connId);
    if (!conn) return;

    // Find the actual mapping by visual group index
    const mappings = conn.config?.mappings || [];
    const groups   = mappings.filter(m => !!m.alias);
    const mapping  = groups[groupVisualIdx];
    if (!mapping) return;

    // Get existing tag names in this group so we can grey them out
    const existingNames = new Set(_flattenDatapoints(mapping.datapoints || {}).map(p => p.name));

    _showM('addTagsModal');
    _el('tagsSelectedCount').textContent = '0';
    _el('tagsModalBody').innerHTML = '<tr><td colspan="6" class="p-6 text-center text-slate-400">Loading...</td></tr>';

    // Replace / inject controls  show locked "adding to group X" banner, no mode toggle
    const existingCtrl = _el('modal-mapping-controls');
    if (existingCtrl) existingCtrl.remove();

    const footer = _el('tagsCancel')?.closest('div');
    if (footer) {
        const ctrl = document.createElement('div');
        ctrl.id = 'modal-mapping-controls';
        ctrl.innerHTML = `
            <div class="border-t border-blue-200 px-5 pt-4 pb-3 bg-blue-50">
                <div class="flex items-center gap-2 text-blue-700 text-xs font-semibold">
                    <i class="fa-solid fa-layer-group"></i>
                    Adding tags to group: <span class="bg-blue-600 text-white px-2 py-0.5 rounded-full ml-1">${_esc(mapping.alias)}</span>
                </div>
                <p class="text-xs text-blue-500 mt-1">Selected tags will be added to this group. Already-added tags are greyed out.</p>
            </div>`;
        footer.parentElement.insertBefore(ctrl, footer);
    }

    try {
        const d = await _api('GET', `${API}/available-tags`);
        _availTags = d.tags || [];
        _renderTagsModal(_availTags, existingNames);
    } catch {
        _el('tagsModalBody').innerHTML = '<tr><td colspan="6" class="p-4 text-center text-red-400">Failed to load tags</td></tr>';
    }

    _el('tagSearch').oninput = e => {
        const q = e.target.value.toLowerCase();
        _renderTagsModal(
            _availTags.filter(t => t.name.toLowerCase().includes(q) || (t.device||'').toLowerCase().includes(q)),
            existingNames
        );
    };

    _el('selectAllTags').onchange = e => {
        document.querySelectorAll('.modal-tag-cb:not(:disabled)').forEach(cb => cb.checked = e.target.checked);
        _updateTagCount();
    };

    _el('tagsCancel').onclick     = () => _hideM('addTagsModal');
    _el('closeTagsModal').onclick = () => _hideM('addTagsModal');

    _el('tagsConfirm').onclick = async () => {
        const checked = [...document.querySelectorAll('.modal-tag-cb:checked')];
        if (!checked.length) { _toast('Select at least one tag', 'error'); return; }

        // Find the real mapping index
        const allMappings = conn.config?.mappings || [];
        let realIdx = -1, gCount = 0;
        for (let i = 0; i < allMappings.length; i++) {
            if (!!allMappings[i].alias) {
                if (gCount === groupVisualIdx) { realIdx = i; break; }
                gCount++;
            }
        }
        if (realIdx === -1) { _toast('Group not found', 'error'); return; }

        // Merge new tags into the group's datapoints
        const dp = { ...(allMappings[realIdx].datapoints || {}) };
        checked.forEach(cb => {
            const dtype = cb.dataset.dtype || 'float';
            if (!dp[dtype]) dp[dtype] = [];
            if (!dp[dtype].includes(cb.dataset.tag)) dp[dtype].push(cb.dataset.tag);
        });

        const updatedMappings = allMappings.map((m, i) =>
            i === realIdx ? { ...m, datapoints: dp } : m
        );

        _setLoading(_el('tagsConfirm'), true);
        try {
            await _api('PUT', `${API}/connections/${connId}`, { config: { mappings: updatedMappings } });
            _hideM('addTagsModal');
            await _selectConnection(connId);
            _toast(`${checked.length} tag(s) added to group "${mapping.alias}"`, 'success');
        } catch {
            _toast('Failed to add tags', 'error');
        } finally {
            _setLoading(_el('tagsConfirm'), false);
        }
    };
};

function _renderTagsModal(tags, disabledNames = new Set()) {
    const tbody = _el('tagsModalBody');
    if (!tags.length) { 
        tbody.innerHTML = '<tr><td colspan="6" class="p-4 text-center text-slate-400">No tags available</td></tr>'; 
        return; 
    }
    tbody.innerHTML = tags.map(t => {
        const isVirtual  = t.source === 'virtual';
        const isDisabled = disabledNames.has(t.name);
        // Determine badge class based on source
        let sourceBadgeClass = 'http'; // default
        if (isVirtual) {
            sourceBadgeClass = 'virtual';
        } else if (t.source === 'modbus-rtu' || t.source === 'modbus-tcp' || t.source === 'modbus') {
            sourceBadgeClass = 'mqtt'; // modbus uses mqtt badge style
        } else if (t.source === 'loadcell') {
            sourceBadgeClass = 'ftp';
        }
        const deviceDisplay = t.device
            ? (isVirtual
                ? `<span class="inline-flex items-center gap-1"><i class="fa-solid fa-microchip text-violet-400 text-xs"></i>${_esc(t.device)}</span>`
                : _esc(t.device))
            : (isVirtual ? '<span class="text-violet-400 italic text-xs">virtual</span>' : '');
        return `
      <tr class="border-t border-slate-100 ${isDisabled ? 'opacity-40 bg-slate-50' : 'hover:bg-slate-50'}${isVirtual && !isDisabled ? ' bg-violet-50/30' : ''}">
        <td class="p-3"><input type="checkbox" class="modal-tag-cb" data-tag="${_esc(t.name)}" data-dtype="${_esc(t.dtype||'float')}" ${isDisabled ? 'disabled' : ''} onchange="window._syncModalTagType(this); window._updateTagCount()"></td>
        <td class="p-3 font-mono text-sm">${_esc(t.name)}${isDisabled ? ' <span class="text-xs text-slate-400 font-sans italic">already added</span>' : ''}</td>
        <td class="p-3 text-sm text-slate-600">${deviceDisplay}</td>
        <td class="p-3 text-sm text-slate-500">${_esc(t.unit||'')}</td>
        <td class="p-3">
          <select class="compact-select text-xs modal-tag-type" data-tag="${_esc(t.name)}" ${isDisabled ? 'disabled' : ''}
                  onchange="this.closest('tr').querySelector('.modal-tag-cb').dataset.dtype = this.value">
            <option value="int"    ${(t.dtype||'float')==='int'    ?'selected':''}>int</option>
            <option value="float"  ${(t.dtype||'float')==='float'  ?'selected':''}>float</option>
            <option value="string" ${(t.dtype||'float')==='string' ?'selected':''}>string</option>
            <option value="bool"   ${(t.dtype||'float')==='bool'   ?'selected':''}>bool</option>
          </select>
        </td>
        <td class="p-3"><span class="cc-badge ${sourceBadgeClass}">${_esc(t.source)}</span></td>
      </tr>`;
    }).join('');
}

window._syncModalTagType = function(cb) {
    // Keep dtype in sync with the type-select on the same row
    const sel = cb.closest('tr')?.querySelector('.modal-tag-type');
    if (sel) cb.dataset.dtype = sel.value;
};

window._updateTagCount = function() {
    const n = document.querySelectorAll('.modal-tag-cb:checked').length;
    const el = _el('tagsSelectedCount'); if (el) el.textContent = n;
};

// --- ADD CONNECTION MODAL -----------------------------------------------------
const _TYPES = {
    mqtt: { name:'MQTT Broker',   desc:'Standard IoT messaging protocol', icon:'fa-cloud',       color:'#3B82F6' },
    ftp:  { name:'FTP Server',    desc:'File transfer FTP/SFTP/FTPS',      icon:'fa-folder-open', color:'#10B981' },
};

function _openAddModal() {
    _selectedType = null;
    _showStep1();
    _buildTypeGrid();
    _showM('addConnectionModal');
}

function _buildTypeGrid() {
    const grid = _el('typeGrid'); if (!grid) return;
    grid.innerHTML = '';
    Object.entries(_TYPES).forEach(([type, info]) => {
        const card = document.createElement('div');
        card.className = 'type-card';
        card.innerHTML = `
          <div style="width:48px;height:48px;border-radius:50%;background:${info.color}22;color:${info.color};display:flex;align-items:center;justify-content:center;margin:0 auto 10px;font-size:20px;"><i class="fa-solid ${info.icon}"></i></div>
          <div class="font-semibold text-slate-900 text-sm mb-1">${info.name}</div>
          <div class="text-xs text-slate-500">${info.desc}</div>`;
        card.addEventListener('click', () => {
            document.querySelectorAll('.type-card').forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            _selectedType = type;
            _el('typePreview').classList.remove('hidden');
            _el('typePreviewName').textContent = info.name;
            const btn = _el('proceedBtn');
            btn.disabled = false; btn.style.opacity = '1'; btn.style.cursor = 'pointer';
        });
        grid.appendChild(card);
    });
}

function _showStep1() {
    _el('stepType').style.display = '';
    _el('stepForm').style.display = 'none';
    const btn = _el('proceedBtn');
    btn.disabled = true; btn.style.opacity = '.4'; btn.style.cursor = 'not-allowed';
    _el('typePreview').classList.add('hidden');
}

function _showStep2(type) {
    _el('stepType').style.display = 'none';
    _el('stepForm').style.display = '';
    _el('formCtxName').textContent = _TYPES[type]?.name || type;
    _el('addName').value = '';
    _el('addMqttFields').classList.toggle('hidden', type !== 'mqtt');
    _el('addFtpFields').classList.toggle('hidden',  type !== 'ftp');
}

async function _handleCreate(e) {
    e.preventDefault();
    const btn  = e.target.querySelector('[type=submit]');
    const name = _el('addName').value.trim();
    if (!name) { _toast('Name is required', 'error'); return; }
    if (!_selectedType) { _toast('Select a type', 'error'); return; }
    let conn = {};
    if (_selectedType === 'mqtt') {
        const host = _el('addHost').value.trim();
        if (!host) { _toast('Broker host is required', 'error'); return; }
        conn = { host, port: +_el('addPort').value||1883, username: _el('addUsername').value.trim(), password: _el('addPassword').value };
    } else {
        const host = _el('addFtpHost').value.trim();
        if (!host) { _toast('FTP host is required', 'error'); return; }
        conn = { host, port: +_el('addFtpPort').value||21, protocol: _el('addFtpProtocol').value, username: _el('addFtpUser').value.trim(), password: _el('addFtpPass').value };
    }
    _setLoading(btn, true);
    try {
        const d = await _api('POST', `${API}/connections`, { type:_selectedType, name, enabled:true, connection:conn });
        _hideM('addConnectionModal');
        _selectedId = d.id;
        await _loadConnections();
        _toast(`"${name}" created`, 'success');
    } catch { _toast('Create failed', 'error'); }
    finally { _setLoading(btn, false); }
}

// --- STATUS BAR ----------------------------------------------------------------
function _updateStatusBar(conn) {
    const s = conn?.statistics || {};
    _st('panelName',    conn ? _esc(conn.name) : 'No Connection Selected');
    _st('panelDesc',    conn ? `${conn.type.toUpperCase()}   ${conn.enabled?'Active':'Disabled'}   ${(conn.config?.mappings||[]).reduce((a,m)=>a+_flattenDatapoints(m.datapoints||{}).length,0)} tag(s)` : 'Select a connection');
    _st('statMessages', (s.messages||0).toLocaleString());
    _st('statErrors',   (s.failed  ||0).toLocaleString());
    _st('statLastSent', s.lastActive||'Never');
    _st('statLatency',  (s.latency ||0)+' ms');
}

function _showActionButtons(conn) {
    const db = _el('deleteBtn'); if (db) db.style.display = 'inline-flex';
    const tog = _el('enabledToggle');
    if (tog) {
        tog.checked  = conn.enabled;
        tog.disabled = false;
    }
}

function _showEmpty() {
    _selectedId = null;
    _st('panelName', 'No Connection Selected');
    _st('panelDesc', 'Select a connection to view details');
    const ph = _el('formPlaceholder'); if (ph) ph.style.display = '';
    const fc = _el('formContent');    if (fc) { fc.classList.add('hidden'); fc.innerHTML = ''; }
    const db = _el('deleteBtn');      if (db) db.style.display = 'none';
    const tog = _el('enabledToggle'); if (tog) { tog.checked = false; tog.disabled = true; }
}

// --- PAGE LISTENERS -----------------------------------------------------------
function _bindPageListeners() {
    _el('addConnectionBtn')?.addEventListener('click', _openAddModal);
    _el('refreshBtn')?.addEventListener('click', async () => { await _loadConnections(); _toast('Refreshed','success'); });
    _el('footerSaveBtn')?.addEventListener('click', async () => {
        try { const d = await _api('PUT', `${API}/save-config`, {}); _toast(d.message||'Saved','success'); }
        catch { _toast('Save failed','error'); }
    });

    _el('enabledToggle')?.addEventListener('change', async function () {
        if (!_selectedId) { this.checked = !this.checked; return; }
        const previousState = !this.checked;
        this.disabled = true;
        try {
            const d = await _api('POST', `${API}/connections/${_selectedId}/toggle`);
            this.checked  = d.enabled;
            this.disabled = false;
            const idx = _connections.findIndex(c => c.id === _selectedId);
            if (idx !== -1) _connections[idx].enabled = d.enabled;
            _renderList();
            const conn = _connections[idx];
            if (conn) _updateStatusBar(conn);
            _toast(d.enabled ? 'Connection enabled' : 'Connection disabled', 'success');
        } catch {
            this.checked  = previousState;
            this.disabled = false;
            _toast('Toggle failed', 'error');
        }
    });

    _el('deleteBtn')?.addEventListener('click', async () => {
        const conn = _connections.find(c=>c.id===_selectedId);
        if (!conn || !confirm(`Delete "${conn.name}"? This cannot be undone.`)) return;
        try { await _api('DELETE', `${API}/connections/${_selectedId}`); _selectedId = null; await _loadConnections(); _toast('Deleted','success'); }
        catch { _toast('Delete failed','error'); }
    });
    _el('closeAddModal')?.addEventListener('click',  () => _hideM('addConnectionModal'));
    _el('cancelType')?.addEventListener('click',     () => _hideM('addConnectionModal'));
    _el('cancelForm')?.addEventListener('click',     () => _hideM('addConnectionModal'));
    _el('backBtn')?.addEventListener('click',        _showStep1);
    _el('proceedBtn')?.addEventListener('click',     () => { if (_selectedType) _showStep2(_selectedType); });
    _el('createForm')?.addEventListener('submit',    _handleCreate);
    _el('addConnectionModal')?.addEventListener('click', e => { if (e.target.id==='addConnectionModal') _hideM('addConnectionModal'); });
    document.addEventListener('keydown', e => { if (e.key==='Escape') { _hideM('addConnectionModal'); _hideM('addTagsModal'); }});
}

// --- UTILS --------------------------------------------------------------------
async function _api(method, url, body) {
    const opts = { method, headers: {'Content-Type':'application/json'} };
    if (body !== undefined) opts.body = JSON.stringify(body);
    const r = await fetch(url, opts);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || r.statusText);
    return d;
}
function _el(id)      { return document.getElementById(id); }
function _gv(id)      { return _el(id)?.value ?? ''; }
function _gc(id)      { return _el(id)?.checked ?? false; }
function _gr(name)    { return document.querySelector(`input[name="${name}"]:checked`)?.value ?? ''; }
function _sv(id, v)   { const e=_el(id); if (e) e.value = v; }
function _sc(id, v)   { const e=_el(id); if (e) e.checked = v; }
function _st(id, t)   { const e=_el(id); if (e) e.textContent = t; }
function _radio(name, val) { const r=document.querySelector(`input[name="${name}"][value="${val}"]`); if(r) r.checked=true; }
function _showM(id)   { const e=_el(id); if (e) { e.style.display='flex'; document.body.style.overflow='hidden'; } }
function _hideM(id)   { const e=_el(id); if (e) { e.style.display='none'; document.body.style.overflow=''; } }
function _esc(s)      { return s==null?'':String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function _setLoading(btn, on) {
    if (!btn) return;
    if (on)  { btn._html=btn.innerHTML; btn.disabled=true; btn.innerHTML='<i class="fa-solid fa-spinner fa-spin mr-1"></i>Working '; }
    else     { btn.disabled=false; btn.innerHTML=btn._html||btn.innerHTML; }
}
function _toast(msg, type='info') {
    if (typeof showNotification === 'function') { showNotification(msg, type); return; }
    const c = {success:'#16A34A',error:'#DC2626',info:'#2563EB',warning:'#D97706'}[type]||'#2563EB';
    const i = {success:'fa-check-circle',error:'fa-circle-xmark',info:'fa-circle-info',warning:'fa-triangle-exclamation'}[type]||'fa-circle-info';
    const n = document.querySelectorAll('.cc-toast').length;
    const t = document.createElement('div'); t.className='cc-toast';
    t.style.cssText=`position:fixed;bottom:${24+n*52}px;right:24px;z-index:99999;background:${c};color:white;padding:10px 16px;border-radius:8px;font-size:13px;font-weight:500;box-shadow:0 4px 16px rgba(0,0,0,.25);display:flex;align-items:center;gap:8px;max-width:340px;transition:opacity .3s,transform .3s`;
    t.innerHTML=`<i class="fa-solid ${i} flex-shrink-0"></i><span>${_esc(msg)}</span>`;
    document.body.appendChild(t);
    setTimeout(()=>{ t.style.opacity='0'; t.style.transform='translateX(20px)'; setTimeout(()=>t.remove(),300); },3500);
}