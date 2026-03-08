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
    _updateDiagnostics(conn);
    _showActionButtons(conn);
    await _loadForm(conn);
}

// --- LOAD FORM HTML -----------------------------------------------------------
async function _loadForm(conn) {
    const ph = _el('formPlaceholder');
    const fc = _el('formContent');
    if (!fc) return;
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
    const groups = mappings.filter(m => m.alias);
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
                            <i class="fa-solid fa-layer-group text-white text-base"></i>
                            <span class="font-semibold text-white text-base">${_esc(mapping.alias)}</span>
                            <span class="bg-white/20 text-white text-xs px-2 py-0.5 rounded-full">${points.length} tag${points.length !== 1 ? 's' : ''}</span>
                        </div>
                        <div class="flex items-center gap-3">
                            <button class="text-white/70 hover:text-white" onclick="window._toggleGroup('${groupId}')">
                                <i class="fa-solid fa-chevron-down text-sm"></i>
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
                                <option value="">  default channel  </option>
                                ${pubChannelOptions.filter(ch => ch.dir === 'publish').length ? `<optgroup label="↑ Publish">` : ''}
                                ${pubChannelOptions.filter(ch => ch.dir === 'publish').map(ch => `<option value="${_esc(ch.name)}" ${currentChannel === ch.name ? 'selected' : ''}>↑ ${_esc(ch.name)}${ch.topic ? ' ('+_esc(ch.topic)+')' : ''}</option>`).join('')}
                                ${pubChannelOptions.filter(ch => ch.dir === 'publish').length ? `</optgroup>` : ''}
                                ${pubChannelOptions.filter(ch => ch.dir === 'subscribe').length ? `<optgroup label="↓ Subscribe">` : ''}
                                ${pubChannelOptions.filter(ch => ch.dir === 'subscribe').map(ch => `<option value="${_esc(ch.name)}" ${currentChannel === ch.name ? 'selected' : ''}>↓ ${_esc(ch.name)}${ch.topic ? ' ('+_esc(ch.topic)+')' : ''}</option>`).join('')}
                                ${pubChannelOptions.filter(ch => ch.dir === 'subscribe').length ? `</optgroup>` : ''}
                                ${currentChannel && !pubChannelOptions.find(c => c.name === currentChannel)
                                    ? `<option value="${_esc(currentChannel)}" selected>${_esc(currentChannel)}</option>` : ''}
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
                                    <th class="p-2 text-left font-medium w-32">Type</th>
                                    <th class="p-2 text-center font-medium w-24">Channel</th>
                                    <th class="p-2 w-12"></th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-100">
                                ${points.map(({name, dtype}) => `
                                    <tr class="hover:bg-slate-50" data-tag-row data-group-idx="${idx}" data-tag-name="${_esc(name)}">
                                        <td class="p-2 pl-8 w-8">
                                            <input type="checkbox" class="tag-select" data-tag="${_esc(name)}" data-group="${idx}" onchange="window._updateTagCount()">
                                        </td>
                                        <td class="p-2 font-mono text-xs">
                                            <i class="fa-regular fa-circle-dot text-blue-300 mr-1"></i>${_esc(name)}
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
            points.forEach(({name, dtype}) => {
                allIndividualTags.push({
                    mappingIdx: mIdx,
                    name,
                    dtype,
                    channel: mapping.channel || ''
                });
            });
        });
        
        const pubChannelOptionsInd = _getPublishChannelOptions();
        individualTable.innerHTML = allIndividualTags.map((item, idx) => `
            <tr class="hover:bg-slate-50" data-individual-idx="${idx}" data-mapping-idx="${item.mappingIdx}" data-tag-name="${_esc(item.name)}">
                <td class="p-2">
                    <input type="checkbox" class="tag-select individual-select" data-tag="${_esc(item.name)}" onchange="window._updateTagCount()">
                </td>
                <td class="p-2 font-mono text-xs">${_esc(item.name)}</td>
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
                        <option value="">  default  </option>
                        ${pubChannelOptionsInd.filter(ch => ch.dir === 'publish').length ? `<optgroup label="↑ Publish">` : ''}
                        ${pubChannelOptionsInd.filter(ch => ch.dir === 'publish').map(ch => `<option value="${_esc(ch.name)}" ${item.channel === ch.name ? 'selected' : ''}>↑ ${_esc(ch.name)}${ch.topic ? ' ('+_esc(ch.topic)+')' : ''}</option>`).join('')}
                        ${pubChannelOptionsInd.filter(ch => ch.dir === 'publish').length ? `</optgroup>` : ''}
                        ${pubChannelOptionsInd.filter(ch => ch.dir === 'subscribe').length ? `<optgroup label="↓ Subscribe">` : ''}
                        ${pubChannelOptionsInd.filter(ch => ch.dir === 'subscribe').map(ch => `<option value="${_esc(ch.name)}" ${item.channel === ch.name ? 'selected' : ''}>↓ ${_esc(ch.name)}${ch.topic ? ' ('+_esc(ch.topic)+')' : ''}</option>`).join('')}
                        ${pubChannelOptionsInd.filter(ch => ch.dir === 'subscribe').length ? `</optgroup>` : ''}
                        ${item.channel && !pubChannelOptionsInd.find(c => c.name === item.channel)
                            ? `<option value="${_esc(item.channel)}" selected>${_esc(item.channel)}</option>` : ''}
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
    ['bool','int','float','string'].forEach(dtype => (dp[dtype]||[]).forEach(name => out.push({name,dtype})));
    return out;
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
    const groups = mappings.filter(m => m.alias);
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
    if (!mapping || mapping.alias) return; // Don't update groups here
    
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
window.removeSelectedTags = function() {
    const selected = document.querySelectorAll('.tag-select:checked');
    if (!selected.length) {
        _toast('No tags selected', 'error');
        return;
    }
    
    if (!confirm(`Remove ${selected.length} selected tag(s)?`)) return;
    
    // Group selected tags by mapping
    const toRemove = {
        groups: new Set(),
        individuals: []
    };
    
    selected.forEach(cb => {
        const groupIdx = cb.dataset.group;
        const tagName = cb.dataset.tag;
        
        if (groupIdx !== undefined && !tagName) {
            // Group header checkbox
            toRemove.groups.add(parseInt(groupIdx));
        } else if (groupIdx !== undefined && tagName) {
            // Tag within a group
            toRemove.individuals.push({
                type: 'group',
                groupIdx: parseInt(groupIdx),
                tagName
            });
        } else if (tagName) {
            // Individual tag
            toRemove.individuals.push({
                type: 'individual',
                tagName
            });
        }
    });
    
    // This would need to be implemented with actual API calls
    // For now, show what would be removed
    console.log('Would remove:', toRemove);
    _toast('Remove selected tags - implement API call', 'warning');
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
        collapseAllGroups: window.collapseAllGroups || function() {},
        expandAllGroups: window.expandAllGroups || function() {},
        toggleAllIndividual: window.toggleAllIndividual || function() {},
        removeSelectedTags: window.removeSelectedTags || function() {}
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
            // GROUP: one shared type + channel for all tags
            const visualIdx = _getGroupVisualIdx(existingMappings, mIdx);
            const typeSel   = document.querySelector(`.group-type-select[data-group-idx="${visualIdx}"]`);
            const dtype     = typeSel ? typeSel.value : _detectGroupType(mapping.datapoints);
            const allTagNames = _flattenDatapoints(mapping.datapoints || {}).map(p => p.name);
            updatedMappings.push({
                ...mapping,
                datapoints: { [dtype]: allTagNames },
            });

        }
    });

    // -- INDIVIDUAL tags: read directly from every DOM row in the individual table --
    // This is more reliable than iterating existingMappings because:
    //   1. After a previous save, multiple tags can share the same mapping-idx
    //   2. data-tag-name lookup can collide with group table rows
    // We read every <tr data-individual-idx> row directly from the DOM.
    document.querySelectorAll('#individual-tags-table tr[data-individual-idx]').forEach(row => {
        const tagName = row.dataset.tagName;
        if (!tagName) return;
        const typeSel = row.querySelector('.tag-type-select');
        const chSel   = row.querySelector('.tag-channel');
        const dtype   = typeSel?.value || 'float';
        const channel = chSel?.value.trim() || '';
        const entry   = { datapoints: { [dtype]: [tagName] } };
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
    const label = mappings[mappingIdx]?.alias || `mapping #${mappingIdx + 1}`;
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
        if (dp[dtype]) dp[dtype] = dp[dtype].filter(n => n !== tagName);
    });
    try {
        await _api('PUT', `${API}/connections/${connId}`, { config: { mappings } });
        await _selectConnection(connId);
        _toast(`Tag "${tagName}" removed`, 'success');
    } catch { _toast('Remove failed', 'error'); }
};

// --- ADD TAGS MODAL -----------------------------------------------------------
async function _openTagsModal(conn) {
    _showM('addTagsModal');
    _el('tagsSelectedCount').textContent = '0';
    _el('tagsModalBody').innerHTML = '<tr><td colspan="5" class="p-6 text-center text-slate-400">Loading </td></tr>';

    // Inject alias + channel controls for creating a group
    if (!_el('modal-mapping-controls')) {
        const footer = _el('tagsCancel')?.closest('div');
        if (footer) {
            const ctrl = document.createElement('div');
            ctrl.id = 'modal-mapping-controls';
            ctrl.className = 'bg-slate-50 p-4 rounded-lg mb-4 border border-slate-200';
            ctrl.innerHTML = `
                <h6 class="text-xs font-semibold text-slate-700 mb-3">Create Group (Optional)</h6>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-xs font-medium text-slate-600 mb-1">
                            <i class="fa-regular fa-layer-group text-blue-500 mr-1"></i>Group Alias
                        </label>
                        <input id="modal-alias-input" type="text" class="compact-input w-full" placeholder="e.g., motor_group, sensor_panel">
                        <p class="help-text mt-1">All selected tags will be grouped under this name</p>
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-slate-600 mb-1">
                            <i class="fa-regular fa-envelope text-amber-500 mr-1"></i>Channel Override
                        </label>
                        <input id="modal-channel-input" type="text" class="compact-input w-full" placeholder="e.g., telemetry_channel">
                        <p class="help-text mt-1">Optional: Override default channel for this group</p>
                    </div>
                </div>
                <p class="text-xs text-slate-400 mt-2">
                    <i class="fa-regular fa-circle-info mr-1"></i> 
                    Leave Alias empty to add tags individually
                </p>`;
            footer.parentElement.insertBefore(ctrl, footer);
        }
    } else {
        // Reset values on re-open
        _sv('modal-alias-input', '');
        _sv('modal-channel-input', '');
    }

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
function _renderTagsModal(tags) {
    const tbody = _el('tagsModalBody');
    if (!tags.length) { 
        tbody.innerHTML = '<tr><td colspan="6" class="p-4 text-center text-slate-400">No tags available</td></tr>'; 
        return; 
    }
    tbody.innerHTML = tags.map(t => {
        const isVirtual = t.source === 'virtual';
        const sourceBadgeClass = isVirtual ? 'virtual' : (t.source === 'modbus' ? 'mqtt' : (t.source === 'loadcell' ? 'ftp' : 'http'));
        const deviceDisplay = t.device
            ? (isVirtual
                ? `<span class="inline-flex items-center gap-1"><i class="fa-solid fa-microchip text-violet-400 text-xs"></i>${_esc(t.device)}</span>`
                : _esc(t.device))
            : (isVirtual ? '<span class="text-violet-400 italic text-xs">virtual</span>' : '—');
        return `
      <tr class="border-t border-slate-100 hover:bg-slate-50${isVirtual ? ' bg-violet-50/30' : ''}">
        <td class="p-3"><input type="checkbox" class="modal-tag-cb" data-tag="${_esc(t.name)}" data-dtype="${_esc(t.dtype||'float')}" onchange="window._syncModalTagType(this); window._updateTagCount()"></td>
        <td class="p-3 font-mono text-sm">${_esc(t.name)}</td>
        <td class="p-3 text-sm text-slate-600">${deviceDisplay}</td>
        <td class="p-3 text-sm text-slate-500">${_esc(t.unit||'—')}</td>
        <td class="p-3">
          <select class="compact-select text-xs modal-tag-type" data-tag="${_esc(t.name)}"
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

// --- STATUS BAR + DIAGNOSTICS -------------------------------------------------
function _updateStatusBar(conn) {
    const s = conn?.statistics || {};
    _st('panelName',    conn ? _esc(conn.name) : 'No Connection Selected');
    _st('panelDesc',    conn ? `${conn.type.toUpperCase()}   ${conn.enabled?'Active':'Disabled'}   ${(conn.config?.mappings||[]).reduce((a,m)=>a+_flattenDatapoints(m.datapoints||{}).length,0)} tag(s)` : 'Select a connection');
    _st('statMessages', (s.messages||0).toLocaleString());
    _st('statErrors',   (s.failed  ||0).toLocaleString());
    _st('statLastSent', s.lastActive||'Never');
    _st('statLatency',  (s.latency ||0)+' ms');
}

function _updateDiagnostics(conn) {
    const s = conn?.statistics || {};
    const el = _el('diagStatus');
    if (el) { el.className = 'cc-status '+(conn?.enabled?'online':'offline'); el.textContent = conn?.enabled?'Connected':'Disconnected'; }
    _st('diagLastMsg', s.lastActive||'Never');
    _st('diagSent',    (s.messages||0).toLocaleString());
    _st('diagRecv',    Math.floor((s.ok||0)*0.98).toLocaleString());
    _st('diagError',   s.failed > 0 ? s.failed+' errors' : 'None');
    _st('diagLatency', (s.latency||0)+' ms');
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