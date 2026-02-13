// mqtt-cloud.js  — Cloud Connection Manager orchestrator
// Flow: load list → select → inject form HTML → populate from DB → save back to DB
'use strict';

const API = '/api/cloud-integration';
let _connections   = [];
let _selectedId    = null;
let _selectedType  = null;   // for Add modal
let _availTags     = [];     // fetched when Add Tags modal opens

// ─── ENTRY ───────────────────────────────────────────────────────────────────
window.initMqttCloud = async function () {
    _bindPageListeners();
    await _loadConnections();
};

// ─── LOAD LIST ───────────────────────────────────────────────────────────────
async function _loadConnections() {
    try {
        const d = await _api('GET', `${API}/connections`);
        _connections = d.connections || [];
        _renderList();
        // re-select previously selected or first
        const target = _selectedId && _connections.find(c => c.id === _selectedId)
            ? _selectedId : (_connections[0]?.id || null);
        if (target) await _selectConnection(target);
        else _showEmpty();
    } catch (e) { _toast('Failed to load connections', 'error'); }
}

// ─── RENDER LIST ─────────────────────────────────────────────────────────────
function _renderList() {
    const list  = _el('connectionsList');
    const empty = _el('connectionsEmpty');
    if (!list) return;
    list.querySelectorAll('.conn-item').forEach(n => n.remove());
    _el('connectionCount').textContent = _connections.length;
    if (!_connections.length) { if (empty) empty.style.display = ''; return; }
    if (empty) empty.style.display = 'none';

    _connections.forEach(c => {
        const s = c.statistics || {};
        const div = document.createElement('div');
        div.className = `conn-item ${c.type}${c.id === _selectedId ? ' active' : ''}`;
        div.dataset.id = c.id;
        div.innerHTML = `
          <div class="flex items-center justify-between mb-1.5">
            <div class="flex items-center gap-2">
              <i class="${c.type==='mqtt'?'fa-solid fa-cloud text-blue-500':'fa-solid fa-globe text-yellow-500'} text-xs"></i>
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

    const file = conn.type === 'mqtt'
        ? 'pages/connection-forms/mqtt-form.html'
        : 'pages/connection-forms/http-form.html';

    try {
        const r = await fetch(file);
        if (!r.ok) throw new Error(`${r.status}`);
        fc.innerHTML = await r.text();

        // Init form UI logic (toggles, tab switching)
        if (conn.type === 'mqtt' && typeof window.initializeMqttForm === 'function') window.initializeMqttForm();
        if (conn.type === 'http' && typeof window.initializeHttpForm === 'function') window.initializeHttpForm();

        // Populate every field from DB data
        conn.type === 'mqtt' ? _populateMqtt(conn) : _populateHttp(conn);

        // Override all Save buttons to call real API
        _wireFormSaves(conn);

        // Wire the "Add Tags" button inside the form
        _wireAddTagsBtn(conn);

    } catch (e) {
        fc.innerHTML = `<div class="p-8 text-center text-slate-400 text-sm">
          <i class="fa-solid fa-triangle-exclamation text-amber-400 text-2xl mb-2 block"></i>
          Could not load form file: <code>${file}</code>
        </div>`;
    }
}

// ─── POPULATE MQTT FORM ───────────────────────────────────────────────────────
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

    // Topics tab
    _sv('field-baseTopic',    c.baseTopic    ?? '');
    _sv('field-json-template',c.jsonTemplate ?? '{"timestamp":"%TIMESTAMP%","device":"%DEVICE_ID%","data":%DATA%}');

    // Advanced tab
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

    // Populate tag publishing table from mqtt_datapoints
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
          <td class="p-2">
            <input type="text" class="compact-input text-xs tag-topic" value="${_esc(tag.topic||base)}" placeholder="${_esc(base)}/...">
          </td>
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
              <label class="toggle-switch">
                <input type="checkbox" class="tag-enabled" ${tag.enabled?'checked':''}>
                <span class="toggle-slider"></span>
              </label>
              <button class="text-red-500 hover:text-red-700 text-xs" onclick="window._cloudRemoveTag('${_esc(conn.id)}','${_esc(tag.name)}')">
                <i class="fa-solid fa-trash"></i>
              </button>
            </div>
          </td>`;
        tbody.appendChild(tr);
    });
}

// ─── POPULATE HTTP FORM ───────────────────────────────────────────────────────
function _populateHttp(conn) {
    const c = conn.config || {};
    _sv('field-url',         c.url         ?? '');
    _sv('field-method',      c.method      ?? 'POST');
    _sv('field-contentType', c.contentType ?? 'application/json');
    _sv('field-authType',    c.authType    ?? 'none');
    _sv('field-username',    c.username    ?? '');
    _sv('field-password',    c.password    ?? '');
    _sv('field-apiKey',      c.apiKey      ?? '');
    _sv('field-oauth-clientId', c.oauthClientId ?? '');
    _sv('field-oauth-secret',   c.oauthSecret   ?? '');
    _sv('field-oauth-tokenUrl', c.oauthTokenUrl ?? '');

    // Trigger auth-type show/hide
    const authSel = _el('field-authType');
    if (authSel) authSel.dispatchEvent(new Event('change'));

    // Payload tab
    _radio('field-payloadFormat', c.payloadFormat ?? 'json');
    _sv('field-jsonTemplate',   c.jsonTemplate    ?? '');
    _sv('field-timestampFormat',c.timestampFormat ?? 'epoch');
    _sc('field-compression',    c.compression     ?? false);
    _sc('field-encryption',     c.encryption      ?? false);
    _sv('field-dataFilter',     c.dataFilter      ?? '');

    // Trigger payload format show/hide
    const checked = document.querySelector('input[name="field-payloadFormat"]:checked');
    if (checked) checked.dispatchEvent(new Event('change'));

    // Publishing tab
    _radio('field-publishMode', c.publishMode ?? 'realtime');
    _sv('field-batchSize',     c.batchSize    ?? 100);
    _sv('field-batchInterval', c.batchInterval ?? 60);

    // Advanced tab
    _sv('field-timeout',    c.timeout    ?? 30);
    _sv('field-retryCount', c.retryCount ?? 3);
    _sv('field-retryDelay', c.retryDelay ?? 5);
    _sc('field-sslVerify',  c.sslVerify  ?? true);
    _sv('field-proxyServer',    c.proxyServer    ?? '');
    _sv('field-proxyUsername',  c.proxyUsername  ?? '');
    _sv('field-proxyPassword',  c.proxyPassword  ?? '');
    _sv('field-rateLimit',  c.rateLimit  ?? 60);
    _sc('field-throttle',   c.throttle   ?? true);
    _sc('field-storeForward',c.storeForward ?? true);
    _sv('field-maxStorage',     c.maxStorage     ?? 1000);
    _sv('field-retentionPeriod',c.retentionPeriod ?? 24);

    // Publishing tab tags table
    _renderHttpTagsTable(conn);
}

function _renderHttpTagsTable(conn) {
    const tbody = _el('http-tags-table');
    if (!tbody) return;
    const tags = conn.tags || [];
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
          <td class="p-2"><input type="checkbox" class="http-tag-select"></td>
          <td class="p-2 font-mono text-xs">${_esc(tag.name)}</td>
          <td class="p-2">
            <select class="compact-select text-xs tag-publish-mode">
              <option value="onChange" ${tag.publishMode==='onChange'?'selected':''}>On Change</option>
              <option value="1000" ${tag.publishMode==='1000'?'selected':''}>1 sec</option>
              <option value="5000" ${tag.publishMode==='5000'?'selected':''}>5 sec</option>
              <option value="30000"${tag.publishMode==='30000'?'selected':''}>30 sec</option>
            </select>
          </td>
          <td class="p-2 text-xs">
            <select class="compact-select text-xs">
              <option value="high">High</option>
              <option value="medium" selected>Medium</option>
              <option value="low">Low</option>
            </select>
          </td>
          <td class="p-2">
            <div class="flex items-center gap-2">
              <label class="toggle-switch">
                <input type="checkbox" class="tag-enabled" ${tag.enabled?'checked':''}>
                <span class="toggle-slider"></span>
              </label>
              <button class="text-red-500 hover:text-red-700 text-xs" onclick="window._cloudRemoveTag('${_esc(conn.id)}','${_esc(tag.name)}')">
                <i class="fa-solid fa-trash"></i>
              </button>
            </div>
          </td>`;
        tbody.appendChild(tr);
    });
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
        if (!window.httpFormLogic) window.httpFormLogic = {};
        window.httpFormLogic.saveHttpConnectionSettings = () => _saveHttpConnection(conn.id);
        window.httpFormLogic.saveHttpPayloadSettings    = () => _saveHttpPayload(conn.id);
        window.httpFormLogic.saveHttpPublishingSettings = () => _saveHttpPublishing(conn.id);
        window.httpFormLogic.saveHttpAdvancedSettings   = () => _saveHttpAdvanced(conn.id);
    }
}

// ─── WIRE ADD TAGS BUTTON ─────────────────────────────────────────────────────
function _wireAddTagsBtn(conn) {
    // Both forms call showAddTagModal() — we override it here
    if (!window.mqttFormLogic) window.mqttFormLogic = {};
    if (!window.httpFormLogic) window.httpFormLogic = {};
    const openFn = () => _openTagsModal(conn);
    window.mqttFormLogic.showAddTagModal = openFn;
    window.httpFormLogic.showAddTagModal = openFn;
    // Also override the raw global (http-form uses direct call)
    window.showAddTagModal = openFn;
    window.removeKeyValueItem = btn => btn.closest('.key-value-item')?.remove();
    window.addKeyValueItem = btn => {
        const list = btn.closest('.key-value-list');
        const div = document.createElement('div');
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
    const cfg = {
        protocol:       _gv('field-protocol'),
        host:           _gv('field-host'),
        port:           +_gv('field-port') || 8883,
        clientId:       _gv('field-clientId'),
        keepAlive:      +_gv('field-keepAlive') || 60,
        username:       _gv('field-username'),
        password:       _gv('field-password'),
        tls:            _gc('field-tls'),
        cleanSession:   _gc('field-cleanSession'),
        retainMessages: _gc('field-retainMessages'),
        qos:            +_gr('field-qos') || 1,
    };
    await _putCfg(id, cfg, 'Connection settings saved');
}

async function _saveMqttTopics(id) {
    const conn = _connections.find(c => c.id === id);
    const cfg  = { ...(conn?.config||{}), baseTopic: _gv('field-baseTopic'), jsonTemplate: _gv('field-json-template') };
    await _putCfg(id, cfg, 'Topics & Format saved');
}

async function _saveMqttPublishing(id) {
    // Collect rows from the rendered table and PUT to tags endpoint
    const rows = document.querySelectorAll('#mqtt-tags-table tr[data-tag-name]');
    const tags = [...rows].map(tr => ({
        name:        tr.dataset.tagName,
        topic:       tr.querySelector('.tag-topic')?.value || '',
        publishMode: tr.querySelector('.tag-publish-mode')?.value || 'onChange',
        enabled:     tr.querySelector('.tag-enabled')?.checked ?? true,
    }));
    try {
        await _api('POST', `${API}/connections/${id}/tags`, { tags: tags.map(t=>t.name), publishMode: 'onChange', replace: true });
        // Also update individual topic/mode per tag — batch update via config
        const conn = _connections.find(c=>c.id===id);
        if (conn) { conn.tags = tags; }
        _toast('Publishing settings saved', 'success');
    } catch { _toast('Save failed', 'error'); }
}

async function _saveMqttAdvanced(id) {
    const conn = _connections.find(c => c.id === id);
    const cfg  = { ...(conn?.config||{}),
        keepAlive:         +_gv('field-advanced-keep-alive')         || 60,
        reconnectInterval: +_gv('field-advanced-reconnect-interval') || 5,
        connectTimeout:    +_gv('field-advanced-connect-timeout')    || 30,
        maxRetries:        +_gv('field-advanced-max-retries')        || 5,
        autoReconnect:     _gc('field-advanced-auto-reconnect'),
        storeForward:      _gc('field-advanced-store-forward'),
        validateCerts:     _gc('field-advanced-validate-certs'),
        logLevel:          _gv('field-advanced-log-level'),
        maxLogSize:        +_gv('field-advanced-max-log-size')       || 10,
        logRetention:      +_gv('field-advanced-log-retention')      || 7,
        connLogging:       _gc('field-advanced-connection-logging'),
        msgLogging:        _gc('field-advanced-message-logging'),
        maxInflight:       +_gv('field-advanced-max-inflight')       || 10,
        queueSize:         +_gv('field-advanced-queue-size')         || 100,
        bufferSize:        +_gv('field-advanced-buffer-size')        || 1024,
        pingTimeout:       +_gv('field-advanced-ping-timeout')       || 10,
        compression:       _gc('field-advanced-enable-compression'),
        compressionLevel:  +_gv('field-advanced-compression-level')  || 6,
        minCompressSize:   +_gv('field-advanced-min-compress-size')  || 256,
        tlsVersion:        _gv('field-advanced-tls-version'),
        cipherSuite:       _gv('field-advanced-cipher-suite'),
        lwt:               _gc('field-advanced-enable-lwt'),
        lwtTopic:          _gv('field-advanced-lwt-topic'),
        lwtMessage:        _gv('field-advanced-lwt-message'),
        lwtQos:            +_gv('field-advanced-lwt-qos')            || 1,
        lwtRetain:         _gc('field-advanced-lwt-retain'),
    };
    await _putCfg(id, cfg, 'Advanced settings saved');
}

// ─── SAVE: HTTP ───────────────────────────────────────────────────────────────
async function _saveHttpConnection(id) {
    // Collect custom headers
    const headers = {};
    document.querySelectorAll('.key-value-item').forEach(item => {
        const inputs = item.querySelectorAll('input');
        if (inputs[0]?.value) headers[inputs[0].value] = inputs[1]?.value || '';
    });
    const cfg = {
        url:           _gv('field-url'),
        method:        _gv('field-method'),
        contentType:   _gv('field-contentType'),
        authType:      _gv('field-authType'),
        username:      _gv('field-username'),
        password:      _gv('field-password'),
        apiKey:        _gv('field-apiKey'),
        oauthClientId: _gv('field-oauth-clientId'),
        oauthSecret:   _gv('field-oauth-secret'),
        oauthTokenUrl: _gv('field-oauth-tokenUrl'),
        customHeaders: headers,
    };
    await _putCfg(id, cfg, 'Connection settings saved');
}

async function _saveHttpPayload(id) {
    const conn = _connections.find(c=>c.id===id);
    const cfg = { ...(conn?.config||{}),
        payloadFormat:   _gr('field-payloadFormat') || 'json',
        jsonTemplate:    _gv('field-jsonTemplate'),
        timestampFormat: _gv('field-timestampFormat'),
        compression:     _gc('field-compression'),
        encryption:      _gc('field-encryption'),
        dataFilter:      _gv('field-dataFilter'),
    };
    await _putCfg(id, cfg, 'Payload format saved');
}

async function _saveHttpPublishing(id) {
    const rows = document.querySelectorAll('#http-tags-table tr[data-tag-name]');
    const tags = [...rows].map(tr => tr.dataset.tagName);
    try {
        await _api('POST', `${API}/connections/${id}/tags`, { tags, publishMode: _gr('field-publishMode') || 'realtime', replace: true });
        const conn = _connections.find(c=>c.id===id);
        const cfg  = { ...(conn?.config||{}), publishMode: _gr('field-publishMode')||'realtime', batchSize: +_gv('field-batchSize')||100, batchInterval: +_gv('field-batchInterval')||60 };
        await _putCfg(id, cfg, 'Publishing settings saved');
    } catch { _toast('Save failed', 'error'); }
}

async function _saveHttpAdvanced(id) {
    const conn = _connections.find(c=>c.id===id);
    const cfg = { ...(conn?.config||{}),
        timeout:          +_gv('field-timeout')          || 30,
        retryCount:       +_gv('field-retryCount')       || 3,
        retryDelay:       +_gv('field-retryDelay')       || 5,
        sslVerify:        _gc('field-sslVerify'),
        proxyServer:      _gv('field-proxyServer'),
        proxyUsername:    _gv('field-proxyUsername'),
        proxyPassword:    _gv('field-proxyPassword'),
        rateLimit:        +_gv('field-rateLimit')        || 60,
        throttle:         _gc('field-throttle'),
        storeForward:     _gc('field-storeForward'),
        maxStorage:       +_gv('field-maxStorage')       || 1000,
        retentionPeriod:  +_gv('field-retentionPeriod')  || 24,
    };
    await _putCfg(id, cfg, 'Advanced settings saved');
}

async function _putCfg(id, cfg, msg) {
    try {
        await _api('PUT', `${API}/connections/${id}`, { config: cfg });
        const idx = _connections.findIndex(c=>c.id===id);
        if (idx !== -1) _connections[idx].config = { ...(_connections[idx].config||{}), ...cfg };
        _toast(msg, 'success');
    } catch { _toast('Save failed', 'error'); }
}

// ─── REMOVE TAG (called from inline button) ───────────────────────────────────
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
        // Filter out already-assigned tags
        const assigned = new Set((conn.tags || []).map(t => t.name));
        _renderTagsModal(_availTags.filter(t => !assigned.has(t.name)), conn);
    } catch { _el('tagsModalBody').innerHTML = '<tr><td colspan="5" class="p-4 text-center text-red-400">Failed to load tags</td></tr>'; }

    _el('tagSearch').oninput = e => {
        const q = e.target.value.toLowerCase();
        const assigned = new Set((conn.tags || []).map(t => t.name));
        _renderTagsModal(_availTags.filter(t => !assigned.has(t.name) && (t.name.toLowerCase().includes(q) || t.device.toLowerCase().includes(q))), conn);
    };

    _el('selectAllTags').onchange = e => {
        document.querySelectorAll('.modal-tag-cb').forEach(cb => cb.checked = e.target.checked);
        _updateTagCount();
    };

    _el('tagsCancel').onclick  = () => _hideM('addTagsModal');
    _el('closeTagsModal').onclick = () => _hideM('addTagsModal');
    _el('tagsConfirm').onclick = async () => {
        const selected = [...document.querySelectorAll('.modal-tag-cb:checked')].map(cb => cb.dataset.tag);
        if (!selected.length) { _toast('Select at least one tag', 'error'); return; }
        _setLoading(_el('tagsConfirm'), true);
        try {
            await _api('POST', `${API}/connections/${conn.id}/tags`, { tags: selected, publishMode: 'onChange', replace: false });
            _hideM('addTagsModal');
            await _selectConnection(conn.id);
            _toast(`${selected.length} tag(s) added`, 'success');
        } catch { _toast('Failed to add tags', 'error'); }
        finally { _setLoading(_el('tagsConfirm'), false); }
    };
}

function _renderTagsModal(tags, conn) {
    const tbody = _el('tagsModalBody');
    if (!tags.length) { tbody.innerHTML = '<tr><td colspan="5" class="p-4 text-center text-slate-400">No tags available</td></tr>'; return; }
    tbody.innerHTML = tags.map(t => `
      <tr class="border-t border-slate-100 hover:bg-slate-50">
        <td class="p-2"><input type="checkbox" class="modal-tag-cb" data-tag="${_esc(t.name)}" onchange="_updateTagCount()"></td>
        <td class="p-2 font-mono text-xs">${_esc(t.name)}</td>
        <td class="p-2 text-xs text-slate-600">${_esc(t.device||'—')}</td>
        <td class="p-2 text-xs text-slate-500">${_esc(t.unit||'—')}</td>
        <td class="p-2"><span class="cc-badge ${t.source==='modbus'?'mqtt':'http'}">${_esc(t.source)}</span></td>
      </tr>`).join('');
}

window._updateTagCount = function () {
    const n = document.querySelectorAll('.modal-tag-cb:checked').length;
    const el = _el('tagsSelectedCount');
    if (el) el.textContent = n;
};

// ─── ADD CONNECTION MODAL ─────────────────────────────────────────────────────
const _TYPES = {
    mqtt: { name:'MQTT Broker',   desc:'Standard IoT messaging protocol', icon:'fa-solid fa-cloud',  color:'#3B82F6' },
    http: { name:'HTTP Endpoint', desc:'REST API / webhook endpoint',      icon:'fa-solid fa-globe',  color:'#F59E0B' },
};

function _openAddModal() {
    _selectedType = null;
    _showStep1();
    _buildTypeGrid();
    _showM('addConnectionModal');
}

function _buildTypeGrid() {
    const grid = _el('typeGrid');
    if (!grid) return;
    grid.innerHTML = '';
    Object.entries(_TYPES).forEach(([type, info]) => {
        const card = document.createElement('div');
        card.className = 'type-card';
        card.innerHTML = `
          <div style="width:48px;height:48px;border-radius:50%;background:${info.color}22;color:${info.color};display:flex;align-items:center;justify-content:center;margin:0 auto 10px;font-size:20px;">
            <i class="${info.icon}"></i>
          </div>
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
    _el('addHttpFields').classList.toggle('hidden', type !== 'http');
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
        const url = _el('addUrl').value.trim();
        if (!url) { _toast('URL is required', 'error'); return; }
        conn = { url, method: _el('addMethod').value, apiKey: _el('addToken').value.trim() };
    }
    _setLoading(btn, true);
    try {
        const d = await _api('POST', `${API}/connections`, { type: _selectedType, name, enabled: true, connection: conn });
        _hideM('addConnectionModal');
        _selectedId = d.id;
        await _loadConnections();
        _toast(`"${name}" created`, 'success');
    } catch (err) { _toast('Create failed', 'error'); }
    finally { _setLoading(btn, false); }
}

// ─── TEST ─────────────────────────────────────────────────────────────────────
async function _runTest() {
    if (!_selectedId) return;
    const btn = _el('testBtn');
    _setLoading(btn, true);
    try {
        const d = await _api('POST', `${API}/connections/${_selectedId}/test`);
        _el('testResStatus').className = 'font-medium ' + (d.connected ? 'text-green-600' : 'text-red-600');
        _el('testResStatus').textContent = d.connected ? 'Connected' : 'Failed';
        _el('testResLatency').textContent = d.latency + ' ms';
        _el('testResAuth').textContent    = d.details?.auth || '—';
        const msg = _el('testResMsg');
        msg.className = `p-3 rounded-lg border text-sm ${d.connected ? 'bg-green-50 border-green-200 text-green-800' : 'bg-red-50 border-red-200 text-red-800'}`;
        msg.innerHTML = `<i class="fa-solid ${d.connected?'fa-check-circle':'fa-exclamation-circle'} mr-2"></i>${_esc(d.message||'')}`;
        _showM('testModal');
        if (d.connected) { await _loadConnections(); }
    } catch { _toast('Test failed', 'error'); }
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
    const s   = conn?.statistics || {};
    const el  = _el('diagStatus');
    const on  = conn?.enabled;
    if (el) { el.className = 'cc-status '+(on?'online':'offline'); el.textContent = on?'Connected':'Disconnected'; }
    _st('diagLastMsg', s.lastActive||'Never');
    _st('diagSent',    (s.messages||0).toLocaleString());
    _st('diagRecv',    Math.floor((s.ok||0)*0.98).toLocaleString());
    _st('diagError',   s.failed > 0 ? s.failed+' errors' : 'None');
    _st('diagLatency', (s.latency||0)+' ms');
}

function _showActionButtons(conn) {
    ['testBtn','deleteBtn'].forEach(id => { const b = _el(id); if (b) b.style.display = 'inline-flex'; });
    const tog = _el('enabledToggle');
    if (tog) { tog.checked = conn.enabled; tog.disabled = false; }
}

function _showEmpty() {
    _selectedId = null;
    _st('panelName', 'No Connection Selected');
    _st('panelDesc', 'Select a connection to view details');
    const ph = _el('formPlaceholder'); if (ph) ph.style.display = '';
    const fc = _el('formContent');    if (fc) { fc.classList.add('hidden'); fc.innerHTML = ''; }
    ['testBtn','deleteBtn'].forEach(id => { const b = _el(id); if (b) b.style.display = 'none'; });
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
    _el('enabledToggle')?.addEventListener('change', async function () {
        if (!_selectedId) return;
        try { const d = await _api('POST', `${API}/connections/${_selectedId}/toggle`); await _loadConnections(); _toast(d.message||'Toggled','success'); }
        catch { _toast('Toggle failed','error'); }
    });
    _el('testBtn')?.addEventListener('click', _runTest);
    _el('deleteBtn')?.addEventListener('click', async () => {
        const conn = _connections.find(c=>c.id===_selectedId);
        if (!conn || !confirm(`Delete "${conn.name}"? This cannot be undone.`)) return;
        try { await _api('DELETE', `${API}/connections/${_selectedId}`); _selectedId = null; await _loadConnections(); _toast('Deleted','success'); }
        catch { _toast('Delete failed','error'); }
    });
    _el('closeAddModal')?.addEventListener('click', () => _hideM('addConnectionModal'));
    _el('cancelType')?.addEventListener('click',    () => _hideM('addConnectionModal'));
    _el('cancelForm')?.addEventListener('click',    () => _hideM('addConnectionModal'));
    _el('backBtn')?.addEventListener('click',       _showStep1);
    _el('proceedBtn')?.addEventListener('click', () => { if (_selectedType) _showStep2(_selectedType); });
    _el('createForm')?.addEventListener('submit', _handleCreate);
    _el('addConnectionModal')?.addEventListener('click', e => { if (e.target.id==='addConnectionModal') _hideM('addConnectionModal'); });
    _el('closeTestModal')?.addEventListener('click',  () => _hideM('testModal'));
    _el('closeTestModal2')?.addEventListener('click', () => _hideM('testModal'));
    _el('testModal')?.addEventListener('click', e => { if (e.target.id==='testModal') _hideM('testModal'); });
    document.addEventListener('keydown', e => { if (e.key==='Escape') { _hideM('addConnectionModal'); _hideM('addTagsModal'); _hideM('testModal'); }});
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
    if (on)  { btn._html=btn.innerHTML; btn.disabled=true; btn.innerHTML='<i class="fa-solid fa-spinner fa-spin mr-1"></i>Saving…'; }
    else     { btn.disabled=false; btn.innerHTML=btn._html||btn.innerHTML; }
}
function _toast(msg, type='info') {
    if (typeof showNotification === 'function') { showNotification(msg, type); return; }
    const c = {success:'#16A34A',error:'#DC2626',info:'#2563EB',warning:'#D97706'}[type]||'#2563EB';
    const i = {success:'fa-check-circle',error:'fa-circle-xmark',info:'fa-circle-info',warning:'fa-triangle-exclamation'}[type]||'fa-circle-info';
    const n = document.querySelectorAll('.cc-toast').length;
    const t = document.createElement('div');
    t.className='cc-toast';
    t.style.cssText=`position:fixed;bottom:${24+n*52}px;right:24px;z-index:99999;background:${c};color:white;padding:10px 16px;border-radius:8px;font-size:13px;font-weight:500;box-shadow:0 4px 16px rgba(0,0,0,.25);display:flex;align-items:center;gap:8px;max-width:340px;transition:opacity .3s,transform .3s`;
    t.innerHTML=`<i class="fa-solid ${i} flex-shrink-0"></i><span>${_esc(msg)}</span>`;
    document.body.appendChild(t);
    setTimeout(()=>{ t.style.opacity='0'; t.style.transform='translateX(20px)'; setTimeout(()=>t.remove(),300); },3500);
}