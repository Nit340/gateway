// mqtt-cloud.js  — Cloud Connection Manager orchestrator
'use strict';

const API = '/api/cloud-integration';
let _connections  = [];
let _selectedId   = null;
let _selectedType = null;
let _availTags    = [];

// ─── ENTRY ────────────────────────────────────────────────────────────────────
window.initMqttCloud = async function () {
    _bindPageListeners();
    await _loadConnections();
};

// ─── LOAD LIST ────────────────────────────────────────────────────────────────
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

// ─── RENDER LIST ──────────────────────────────────────────────────────────────
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

// ─── SELECT CONNECTION ────────────────────────────────────────────────────────
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

// ─── LOAD FORM HTML ───────────────────────────────────────────────────────────
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

        // Init form UI (toggles, protocol↔port, anonymous hide/show)
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

// ─── POPULATE MQTT ────────────────────────────────────────────────────────────
function _populateMqtt(conn) {
    const c = conn.config || {};
    _sv('field-protocol',    c.protocol    ?? 'mqtts');
    _sv('field-host',        c.host        ?? '');
    _sv('field-port',        c.port        ?? 8883);
    _sv('field-clientId',    c.clientId    ?? '');
    _sv('field-keepAlive',   c.keepAlive   ?? 60);
    _sv('field-username',    c.username    ?? '');
    _sv('field-password',    c.password    ?? '');
    _sc('field-tls',         c.tls         ?? true);
    _sc('field-cleanSession',c.cleanSession ?? true);
    _sc('field-retainMessages', c.retainMessages ?? false);
    _radio('field-qos', String(c.qos ?? 1));
    _sv('field-baseTopic',    c.baseTopic    ?? '');
    _sv('field-json-template',c.jsonTemplate ?? '{"timestamp":"%TIMESTAMP%","device":"%DEVICE_ID%","data":%DATA%}');
    _sv('field-advanced-keep-alive',         c.keepAlive         ?? 60);
    _sv('field-advanced-reconnect-interval', c.reconnectInterval ?? 5);
    _sv('field-advanced-connect-timeout',    c.connectTimeout    ?? 30);
    _sv('field-advanced-max-retries',        c.maxRetries        ?? 5);
    _sc('field-advanced-auto-reconnect',     c.autoReconnect     ?? true);
    _sc('field-advanced-store-forward',      c.storeForward      ?? false);
    _sc('field-advanced-validate-certs',     c.validateCerts     ?? true);
    _sv('field-advanced-log-level',          c.logLevel          ?? 'info');
    _sv('field-advanced-max-log-size',       c.maxLogSize        ?? 10);
    _sv('field-advanced-log-retention',      c.logRetention      ?? 7);
    _sc('field-advanced-connection-logging', c.connLogging       ?? true);
    _sc('field-advanced-message-logging',    c.msgLogging        ?? false);
    _sv('field-advanced-max-inflight',       c.maxInflight       ?? 10);
    _sv('field-advanced-queue-size',         c.queueSize         ?? 100);
    _sv('field-advanced-buffer-size',        c.bufferSize        ?? 1024);
    _sv('field-advanced-ping-timeout',       c.pingTimeout       ?? 10);
    _sc('field-advanced-enable-compression', c.compression       ?? false);
    _sv('field-advanced-compression-level',  c.compressionLevel  ?? 6);
    _sv('field-advanced-min-compress-size',  c.minCompressSize   ?? 256);
    _sv('field-advanced-tls-version',        c.tlsVersion        ?? 'auto');
    _sv('field-advanced-cipher-suite',       c.cipherSuite       ?? 'default');
    _sc('field-advanced-enable-lwt',         c.lwt               ?? false);
    _sv('field-advanced-lwt-topic',          c.lwtTopic          ?? '');
    _sv('field-advanced-lwt-message',        c.lwtMessage        ?? '');
    _sv('field-advanced-lwt-qos',            c.lwtQos            ?? 1);
    _sc('field-advanced-lwt-retain',         c.lwtRetain         ?? false);
    _renderMqttTagsTable(conn);
}

function _renderMqttTagsTable(conn) {
    const tbody = _el('mqtt-tags-table');
    if (!tbody) return;
    const tags = conn.tags || [];
    const base = conn.config?.baseTopic || '';
    tbody.innerHTML = '';
    if (!tags.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="p-4 text-center text-slate-400 text-xs">No tags assigned. Click "Add Tags" to publish data.</td></tr>';
        return;
    }
    tags.forEach(tag => {
        const tr = document.createElement('tr');
        tr.className = 'border-t border-slate-100';
        tr.dataset.tagName = tag.name;
        tr.innerHTML = `
          <td class="p-2"><input type="checkbox" class="tag-select"></td>
          <td class="p-2 font-mono text-xs">${_esc(tag.name)}</td>
          <td class="p-2"><input type="text" class="compact-input text-xs tag-topic" value="${_esc(tag.topic||base)}" placeholder="${_esc(base)}/..."></td>
          <td class="p-2">
            <select class="compact-select text-xs tag-publish-mode">
              <option value="onChange" ${tag.publishMode==='onChange'?'selected':''}>On Change</option>
              <option value="100"  ${tag.publishMode==='100'?'selected':''}>100 ms</option>
              <option value="500"  ${tag.publishMode==='500'?'selected':''}>500 ms</option>
              <option value="1000" ${tag.publishMode==='1000'?'selected':''}>1 sec</option>
              <option value="5000" ${tag.publishMode==='5000'?'selected':''}>5 sec</option>
            </select>
          </td>
          <td class="p-2">
            <div class="flex items-center gap-2">
              <label class="toggle-switch"><input type="checkbox" class="tag-enabled" ${tag.enabled?'checked':''}><span class="toggle-slider"></span></label>
              <button class="text-red-500 hover:text-red-700 text-xs" onclick="window._cloudRemoveTag('${_esc(conn.id)}','${_esc(tag.name)}')"><i class="fa-solid fa-trash"></i></button>
            </div>
          </td>`;
        tbody.appendChild(tr);
    });
}

// ─── POPULATE FTP ─────────────────────────────────────────────────────────────
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
    _renderFtpTagsTable(conn);
}

function _renderFtpTagsTable(conn) {
    // FTP has no datapoints — nothing to render
}

// ─── WIRE SAVE BUTTONS ────────────────────────────────────────────────────────
function _wireFormSaves(conn) {
    if (conn.type === 'mqtt') {
        if (!window.mqttFormLogic) window.mqttFormLogic = {};
        window.mqttFormLogic.saveMqttConnectionSettings = () => _saveMqttConnection(conn.id);
        window.mqttFormLogic.saveMqttTopicSettings      = () => _saveMqttTopics(conn.id);
        window.mqttFormLogic.saveMqttPublishingSettings = () => _saveMqttPublishing(conn.id);
        window.mqttFormLogic.saveMqttAdvancedSettings   = () => _saveMqttAdvanced(conn.id);
    } else {
        // ftp — wire via ftpFormLogic (same pattern as mqtt) AND by button id
        if (!window.ftpFormLogic) window.ftpFormLogic = {};
        window.ftpFormLogic.saveFtpSettings = () => _saveFtp(conn.id);
        const saveBtn = _el('ftp-save-btn');
        if (saveBtn) saveBtn.onclick = () => _saveFtp(conn.id);
    }
}

// ─── WIRE ADD TAGS BTN ────────────────────────────────────────────────────────
function _wireAddTagsBtn(conn) {
    const openFn = () => _openTagsModal(conn);
    window.showAddTagModal = openFn;
    if (!window.mqttFormLogic) window.mqttFormLogic = {};
    window.mqttFormLogic.showAddTagModal = openFn;

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

// ─── SAVE: MQTT ───────────────────────────────────────────────────────────────
async function _saveMqttConnection(id) {
    await _putCfg(id, {
        protocol:_gv('field-protocol'), host:_gv('field-host'), port:+_gv('field-port')||8883,
        clientId:_gv('field-clientId'), keepAlive:+_gv('field-keepAlive')||60,
        username:_gv('field-username'), password:_gv('field-password'),
        tls:_gc('field-tls'), cleanSession:_gc('field-cleanSession'),
        retainMessages:_gc('field-retainMessages'), qos:+_gr('field-qos')||1,
    }, 'Connection settings saved');
}

async function _saveMqttTopics(id) {
    await _putCfg(id, { baseTopic:_gv('field-baseTopic'), jsonTemplate:_gv('field-json-template') }, 'Topics & Format saved');
}

async function _saveMqttPublishing(id) {
    const rows = document.querySelectorAll('#mqtt-tags-table tr[data-tag-name]');
    const tags = [...rows].map(tr => ({
        name: tr.dataset.tagName,
        topic: tr.querySelector('.tag-topic')?.value || '',
        publishMode: tr.querySelector('.tag-publish-mode')?.value || 'onChange',
        enabled: tr.querySelector('.tag-enabled')?.checked ?? true,
    }));
    try {
        await _api('POST', `${API}/connections/${id}/tags`, { tags: tags.map(t=>t.name), publishMode:'onChange', replace:true });
        _toast('Publishing settings saved', 'success');
    } catch { _toast('Save failed', 'error'); }
}

async function _saveMqttAdvanced(id) {
    const conn = _connections.find(c=>c.id===id);
    await _putCfg(id, { ...(conn?.config||{}),
        keepAlive:+_gv('field-advanced-keep-alive')||60,
        reconnectInterval:+_gv('field-advanced-reconnect-interval')||5,
        connectTimeout:+_gv('field-advanced-connect-timeout')||30,
        maxRetries:+_gv('field-advanced-max-retries')||5,
        autoReconnect:_gc('field-advanced-auto-reconnect'),
        storeForward:_gc('field-advanced-store-forward'),
        validateCerts:_gc('field-advanced-validate-certs'),
        logLevel:_gv('field-advanced-log-level'),
        maxLogSize:+_gv('field-advanced-max-log-size')||10,
        logRetention:+_gv('field-advanced-log-retention')||7,
        connLogging:_gc('field-advanced-connection-logging'),
        msgLogging:_gc('field-advanced-message-logging'),
        maxInflight:+_gv('field-advanced-max-inflight')||10,
        queueSize:+_gv('field-advanced-queue-size')||100,
        bufferSize:+_gv('field-advanced-buffer-size')||1024,
        pingTimeout:+_gv('field-advanced-ping-timeout')||10,
        compression:_gc('field-advanced-enable-compression'),
        compressionLevel:+_gv('field-advanced-compression-level')||6,
        minCompressSize:+_gv('field-advanced-min-compress-size')||256,
        tlsVersion:_gv('field-advanced-tls-version'),
        cipherSuite:_gv('field-advanced-cipher-suite'),
        lwt:_gc('field-advanced-enable-lwt'),
        lwtTopic:_gv('field-advanced-lwt-topic'),
        lwtMessage:_gv('field-advanced-lwt-message'),
        lwtQos:+_gv('field-advanced-lwt-qos')||1,
        lwtRetain:_gc('field-advanced-lwt-retain'),
    }, 'Advanced settings saved');
}

// ─── SAVE: FTP ────────────────────────────────────────────────────────────────
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

// ─── SHARED SAVE HELPER ───────────────────────────────────────────────────────
async function _putCfg(id, cfg, msg) {
    try {
        await _api('PUT', `${API}/connections/${id}`, { config: cfg });
        const idx = _connections.findIndex(c=>c.id===id);
        if (idx !== -1) _connections[idx].config = { ...(_connections[idx].config||{}), ...cfg };
        _toast(msg, 'success');
    } catch { _toast('Save failed', 'error'); }
}

// ─── REMOVE TAG (inline trash) ────────────────────────────────────────────────
window._cloudRemoveTag = async function (connId, tagName) {
    if (!confirm(`Remove tag "${tagName}"?`)) return;
    try {
        await _api('DELETE', `${API}/connections/${connId}/tags/${encodeURIComponent(tagName)}`);
        await _selectConnection(connId);
        _toast(`Tag "${tagName}" removed`, 'success');
    } catch { _toast('Remove failed', 'error'); }
};

// ─── ADD TAGS MODAL ───────────────────────────────────────────────────────────
async function _openTagsModal(conn) {
    _showM('addTagsModal');
    _el('tagsSelectedCount').textContent = '0';
    _el('tagsModalBody').innerHTML = '<tr><td colspan="5" class="p-6 text-center text-slate-400">Loading…</td></tr>';

    try {
        const d = await _api('GET', `${API}/available-tags`);
        _availTags = d.tags || [];
        const assigned = new Set((conn.tags || []).map(t => t.name));
        _renderTagsModal(_availTags.filter(t => !assigned.has(t.name)));
    } catch { _el('tagsModalBody').innerHTML = '<tr><td colspan="5" class="p-4 text-center text-red-400">Failed to load tags</td></tr>'; }

    _el('tagSearch').oninput = e => {
        const q = e.target.value.toLowerCase();
        const assigned = new Set((conn.tags || []).map(t => t.name));
        _renderTagsModal(_availTags.filter(t => !assigned.has(t.name) && (t.name.toLowerCase().includes(q) || (t.device||'').toLowerCase().includes(q))));
    };
    _el('selectAllTags').onchange = e => { document.querySelectorAll('.modal-tag-cb').forEach(cb => cb.checked = e.target.checked); _updateTagCount(); };
    _el('tagsCancel').onclick     = () => _hideM('addTagsModal');
    _el('closeTagsModal').onclick = () => _hideM('addTagsModal');
    _el('tagsConfirm').onclick    = async () => {
        const sel = [...document.querySelectorAll('.modal-tag-cb:checked')].map(cb => cb.dataset.tag);
        if (!sel.length) { _toast('Select at least one tag', 'error'); return; }
        _setLoading(_el('tagsConfirm'), true);
        try {
            await _api('POST', `${API}/connections/${conn.id}/tags`, { tags: sel, publishMode:'onChange', replace:false });
            _hideM('addTagsModal');
            await _selectConnection(conn.id);
            _toast(`${sel.length} tag(s) added`, 'success');
        } catch { _toast('Failed to add tags', 'error'); }
        finally { _setLoading(_el('tagsConfirm'), false); }
    };
}

function _renderTagsModal(tags) {
    const tbody = _el('tagsModalBody');
    if (!tags.length) { tbody.innerHTML = '<tr><td colspan="5" class="p-4 text-center text-slate-400">No tags available</td></tr>'; return; }
    tbody.innerHTML = tags.map(t => `
      <tr class="border-t border-slate-100 hover:bg-slate-50">
        <td class="p-2"><input type="checkbox" class="modal-tag-cb" data-tag="${_esc(t.name)}" onchange="window._updateTagCount()"></td>
        <td class="p-2 font-mono text-xs">${_esc(t.name)}</td>
        <td class="p-2 text-xs text-slate-600">${_esc(t.device||'—')}</td>
        <td class="p-2 text-xs text-slate-500">${_esc(t.unit||'—')}</td>
        <td class="p-2"><span class="cc-badge ${t.source==='modbus'?'mqtt':'http'}">${_esc(t.source)}</span></td>
      </tr>`).join('');
}
window._updateTagCount = function () {
    const n = document.querySelectorAll('.modal-tag-cb:checked').length;
    const el = _el('tagsSelectedCount'); if (el) el.textContent = n;
};

// ─── ADD CONNECTION MODAL ─────────────────────────────────────────────────────
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

// ─── STATUS BAR + DIAGNOSTICS ─────────────────────────────────────────────────
function _updateStatusBar(conn) {
    const s = conn?.statistics || {};
    _st('panelName',    conn ? _esc(conn.name) : 'No Connection Selected');
    _st('panelDesc',    conn ? `${conn.type.toUpperCase()} — ${conn.enabled?'Active':'Disabled'} — ${(conn.tags||[]).length} tag(s)` : 'Select a connection');
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
    // Only show delete, no test button
    const db = _el('deleteBtn'); if (db) db.style.display = 'inline-flex';
    // Set toggle to DB value — do NOT use local state
    const tog = _el('enabledToggle');
    if (tog) {
        tog.checked  = conn.enabled;   // from DB
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

// ─── PAGE LISTENERS ───────────────────────────────────────────────────────────
function _bindPageListeners() {
    _el('addConnectionBtn')?.addEventListener('click', _openAddModal);
    _el('refreshBtn')?.addEventListener('click', async () => { await _loadConnections(); _toast('Refreshed','success'); });
    _el('footerSaveBtn')?.addEventListener('click', async () => {
        try { const d = await _api('PUT', `${API}/save-config`, {}); _toast(d.message||'Saved','success'); }
        catch { _toast('Save failed','error'); }
    });

    // ENABLE TOGGLE — fixed: read confirmed state from API response, then re-render
    _el('enabledToggle')?.addEventListener('change', async function () {
        if (!_selectedId) { this.checked = !this.checked; return; }  // revert if no selection
        const previousState = !this.checked;   // what it was before this click
        this.disabled = true;                  // prevent double-click
        try {
            const d = await _api('POST', `${API}/connections/${_selectedId}/toggle`);
            // Use the confirmed value the server read back
            this.checked  = d.enabled;
            this.disabled = false;
            // Update local cache
            const idx = _connections.findIndex(c => c.id === _selectedId);
            if (idx !== -1) _connections[idx].enabled = d.enabled;
            // Re-render list to show new Active/Inactive badge
            _renderList();
            // Update status bar desc
            const conn = _connections[idx];
            if (conn) _updateStatusBar(conn);
            _toast(d.enabled ? 'Connection enabled' : 'Connection disabled', 'success');
        } catch {
            // Revert toggle to previous state on error
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

// ─── UTILS ────────────────────────────────────────────────────────────────────
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
    if (on)  { btn._html=btn.innerHTML; btn.disabled=true; btn.innerHTML='<i class="fa-solid fa-spinner fa-spin mr-1"></i>Working…'; }
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