// craneiq.js
// ============================================================
// PART 1: Load Cell logic
// - Auto-loads single LC device (no device select)
// - Calibration in modal (pipeline-dependent)
// - Filters always visible, user-entered, saved independently
// ============================================================
(function () {
    var pipelineWs = null;
    var connected = false;
    var currentRaw = null;
    var capturedZero = null;
    var capturedWeightRaw = null;   // raw value snapshotted when user places known weight
    var selectedDevice = null;   // the one LC device loaded from DB
    var rawDatapoint = null;     // e.g. "loadcells.MyScale.raw"

    function el(id) { return document.getElementById(id); }

    // ---- Auto-load single LC device on init ----
    function loadDevice() {
        fetch('/api/pipeline/loadcell-devices', { credentials: 'same-origin' })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var devices = data.devices || [];
            if (devices.length === 0) {
                var btn = el('pipeline-connect-btn');
                if (btn) { btn.disabled = true; btn.classList.add('opacity-40'); }
                var lbl = el('lc-device-label');
                if (lbl) lbl.textContent = 'No device   add one in Device Management';
                return;
            }
            selectedDevice = devices[0];
            rawDatapoint = 'loadcells.' + selectedDevice.name + '.raw';
            var lbl = el('lc-device-label');
            if (lbl) lbl.textContent = selectedDevice.name;
            // Populate filter fields from saved device data
            populateFilters(selectedDevice);
        })
        .catch(function() {});
    }

    // ============================================================
    // DYNAMIC FILTER BUILDER
    // Filters are stored as ordered arrays. UI renders cards in
    // DOM order  that order IS the processing order in the JSON.
    // Drag-to-reorder uses HTML5 drag-and-drop.
    // ============================================================

    // Default parameters per filter type
    var FILTER_DEFAULTS = {
        Median:              { window_size: 3 },
        MovingAverage:       { window_size: 5 },
        Kalman:              { process_noise: 0.01, measurement_noise: 0.1 },
        AdaptiveDeadband:    { grow_rate: 0.8, shrink_rate: 0.1, min_deadband: 1.0, max_deadband: 20.0 },
        LowPass:             { alpha: 0.1 },
        NotchFilter:         { center_frequency: 60.0, q: 30.0 },
        HysteresisQuantizer: { step_size: 10.0, hysteresis_margin: 0.75 }
    };

    var FILTER_LABELS = {
        Median:              'Median',
        MovingAverage:       'Moving Average',
        Kalman:              'Kalman',
        AdaptiveDeadband:    'Adaptive Deadband',
        LowPass:             'Low Pass',
        NotchFilter:         'Notch Filter',
        HysteresisQuantizer: 'Hysteresis Quantizer'
    };

    // Build the parameter fields HTML for a given type + values
    function _filterParamFields(type, params) {
        params = params || FILTER_DEFAULTS[type] || {};
        var inp = 'class="w-full text-xs border border-slate-300 rounded px-2 py-1 focus:ring-1 focus:ring-blue-500 focus:border-blue-500"';
        switch (type) {
            case 'Median':
            case 'MovingAverage':
                return '<label class="block text-xs text-slate-500 mb-0.5">Window Size</label>' +
                       '<input type="number" min="1" max="999" ' + inp + ' data-param="window_size" value="' + (params.window_size || 3) + '">';
            case 'Kalman':
                return '<div class="grid grid-cols-2 gap-2">' +
                    '<div><label class="block text-xs text-slate-500 mb-0.5">Process Noise</label>' +
                    '<input type="number" step="0.0001" ' + inp + ' data-param="process_noise" value="' + (params.process_noise || 0.01) + '"></div>' +
                    '<div><label class="block text-xs text-slate-500 mb-0.5">Meas. Noise</label>' +
                    '<input type="number" step="0.001" ' + inp + ' data-param="measurement_noise" value="' + (params.measurement_noise || 0.1) + '"></div>' +
                    '</div>';
            case 'AdaptiveDeadband':
                return '<div class="grid grid-cols-2 gap-2">' +
                    '<div><label class="block text-xs text-slate-500 mb-0.5">Grow Rate</label>' +
                    '<input type="number" step="0.01" ' + inp + ' data-param="grow_rate" value="' + (params.grow_rate || 0.8) + '"></div>' +
                    '<div><label class="block text-xs text-slate-500 mb-0.5">Shrink Rate</label>' +
                    '<input type="number" step="0.01" ' + inp + ' data-param="shrink_rate" value="' + (params.shrink_rate || 0.1) + '"></div>' +
                    '<div><label class="block text-xs text-slate-500 mb-0.5">Min Deadband</label>' +
                    '<input type="number" step="0.1" ' + inp + ' data-param="min_deadband" value="' + (params.min_deadband || 1.0) + '"></div>' +
                    '<div><label class="block text-xs text-slate-500 mb-0.5">Max Deadband</label>' +
                    '<input type="number" step="0.1" ' + inp + ' data-param="max_deadband" value="' + (params.max_deadband || 20.0) + '"></div>' +
                    '</div>';
            case 'LowPass':
                return '<div class="grid grid-cols-2 gap-2">' +
                    '<div><label class="block text-xs text-slate-500 mb-0.5">Alpha (01) <span class="text-slate-400 italic">or</span></label>' +
                    '<input type="number" step="0.01" min="0.01" max="0.99" ' + inp + ' data-param="alpha" value="' + (params.alpha !== undefined ? params.alpha : 0.1) + '"></div>' +
                    '<div><label class="block text-xs text-slate-500 mb-0.5">Cutoff Freq (Hz) <span class="text-slate-400 italic">optional</span></label>' +
                    '<input type="number" step="0.1" min="0" ' + inp + ' data-param="cutoff_frequency" value="' + (params.cutoff_frequency !== undefined ? params.cutoff_frequency : '') + '" placeholder="leave blank to use alpha"></div>' +
                    '</div>';
            case 'NotchFilter':
                return '<div class="grid grid-cols-2 gap-2">' +
                    '<div><label class="block text-xs text-slate-500 mb-0.5">Center Freq (Hz)</label>' +
                    '<input type="number" step="0.1" min="0.1" ' + inp + ' data-param="center_frequency" value="' + (params.center_frequency || 60.0) + '"></div>' +
                    '<div><label class="block text-xs text-slate-500 mb-0.5">Q Factor</label>' +
                    '<input type="number" step="0.1" min="0.1" ' + inp + ' data-param="q" value="' + (params.q || 30.0) + '"></div>' +
                    '</div>';
            case 'HysteresisQuantizer':
                return '<div class="grid grid-cols-2 gap-2">' +
                    '<div><label class="block text-xs text-slate-500 mb-0.5">Step Size</label>' +
                    '<input type="number" step="0.1" min="0.01" ' + inp + ' data-param="step_size" value="' + (params.step_size || 10.0) + '"></div>' +
                    '<div><label class="block text-xs text-slate-500 mb-0.5">Hysteresis Margin (01)</label>' +
                    '<input type="number" step="0.01" min="0" max="1" ' + inp + ' data-param="hysteresis_margin" value="' + (params.hysteresis_margin !== undefined ? params.hysteresis_margin : 0.75) + '"></div>' +
                    '</div>';
            default:
                return '';
        }
    }

    // Create a filter card DOM element
    function _makeFilterCard(type, params, enabled) {
        if (enabled === undefined) enabled = true;
        var card = document.createElement('div');
        card.className = 'lc-filter-card bg-white rounded-lg border border-slate-200 p-3 select-none';
        card.draggable = true;
        card.dataset.filterType = type;

        var badgeClass = 'lc-badge-' + type;
        card.innerHTML =
            '<div class="flex items-center gap-2 mb-2">' +
                // Drag handle
                '<span class="lc-drag-handle flex-shrink-0" title="Drag to reorder">' +
                    '<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">' +
                        '<circle cx="9" cy="5" r="1" fill="currentColor"/><circle cx="15" cy="5" r="1" fill="currentColor"/>' +
                        '<circle cx="9" cy="12" r="1" fill="currentColor"/><circle cx="15" cy="12" r="1" fill="currentColor"/>' +
                        '<circle cx="9" cy="19" r="1" fill="currentColor"/><circle cx="15" cy="19" r="1" fill="currentColor"/>' +
                    '</svg>' +
                '</span>' +
                // Type badge
                '<span class="text-xs font-semibold px-2 py-0.5 rounded ' + badgeClass + '">' + (FILTER_LABELS[type] || type) + '</span>' +
                // Spacer
                '<span class="flex-1"></span>' +
                // Enabled toggle
                '<label class="relative inline-flex items-center cursor-pointer flex-shrink-0">' +
                    '<input type="checkbox" class="sr-only peer lc-filter-enabled" ' + (enabled ? 'checked' : '') + '>' +
                    '<div class="w-8 h-4 bg-slate-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[\'\'] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-blue-600"></div>' +
                '</label>' +
                // Remove button
                '<button class="lc-filter-remove flex-shrink-0 text-slate-300 hover:text-red-500 transition-colors" title="Remove filter">' +
                    '<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">' +
                        '<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>' +
                    '</svg>' +
                '</button>' +
            '</div>' +
            '<div class="lc-filter-params">' + _filterParamFields(type, params) + '</div>';

        // Remove button
        card.querySelector('.lc-filter-remove').addEventListener('click', function() {
            card.parentNode.removeChild(card);
            _refreshFilterBadges(card.closest('#lc-raw-filter-list') || card.closest('#lc-weight-filter-list'));
            _updateEmptyStates();
        });

        // Drag-and-drop
        card.addEventListener('dragstart', function(e) {
            e.dataTransfer.effectAllowed = 'move';
            card.classList.add('dragging');
            window._lcDragging = card;
        });
        card.addEventListener('dragend', function() {
            card.classList.remove('dragging');
            document.querySelectorAll('.lc-filter-card').forEach(function(c) { c.classList.remove('drag-over'); });
            window._lcDragging = null;
            _refreshFilterBadges(card.closest('#lc-raw-filter-list') || card.closest('#lc-weight-filter-list'));
        });
        card.addEventListener('dragover', function(e) {
            e.preventDefault();
            if (window._lcDragging && window._lcDragging !== card) {
                card.classList.add('drag-over');
                var list = card.parentNode;
                var draggingRect = window._lcDragging.getBoundingClientRect();
                var cardRect     = card.getBoundingClientRect();
                if (e.clientY < cardRect.top + cardRect.height / 2) {
                    list.insertBefore(window._lcDragging, card);
                } else {
                    list.insertBefore(window._lcDragging, card.nextSibling);
                }
            }
        });
        card.addEventListener('dragleave', function() {
            card.classList.remove('drag-over');
        });
        card.addEventListener('drop', function(e) {
            e.preventDefault();
            card.classList.remove('drag-over');
        });

        return card;
    }

    // Refresh [raw[0]], [raw[1]]  index badges in a list container
    function _refreshFilterBadges(list) {
        if (!list) return;
        var cards = list.querySelectorAll('.lc-filter-card');
        var prefix = list.id === 'lc-raw-filter-list' ? 'raw' : 'weight';
        cards.forEach(function(card, idx) {
            var existingBadge = card.querySelector('.lc-index-badge');
            if (existingBadge) existingBadge.remove();
            var badge = document.createElement('span');
            badge.className = 'lc-index-badge text-xs text-slate-400 font-mono ml-1';
            badge.textContent = prefix + '[' + idx + ']';
            card.querySelector('.lc-drag-handle').after(badge);
        });
    }

    function _updateEmptyStates() {
        var rawList   = document.getElementById('lc-raw-filter-list');
        var weightList = document.getElementById('lc-weight-filter-list');
        var rawEmpty   = document.getElementById('lc-raw-empty');
        var wEmpty     = document.getElementById('lc-weight-empty');
        if (rawList && rawEmpty) {
            var hasRaw = rawList.querySelectorAll('.lc-filter-card').length > 0;
            rawEmpty.style.display = hasRaw ? 'none' : '';
            rawEmpty.classList.toggle('hidden', hasRaw);
        }
        if (weightList && wEmpty) {
            var hasWeight = weightList.querySelectorAll('.lc-filter-card').length > 0;
            wEmpty.style.display = hasWeight ? 'none' : '';
            wEmpty.classList.toggle('hidden', hasWeight);
        }
    }

    // Add a filter card to a list
    function _appendFilter(listId, type, params, enabled) {
        var list = document.getElementById(listId);
        if (!list) return;
        var card = _makeFilterCard(type, params, enabled);
        list.appendChild(card);
        _refreshFilterBadges(list);
        _updateEmptyStates();
    }

    // Public: add raw filter from "Add" button
    window.lcAddRawFilter = function() {
        var sel = document.getElementById('lc-add-raw-type');
        if (sel) _appendFilter('lc-raw-filter-list', sel.value, null, true);
    };

    // Public: add weight filter from "Add" button
    window.lcAddWeightFilter = function() {
        var sel = document.getElementById('lc-add-weight-type');
        if (sel) _appendFilter('lc-weight-filter-list', sel.value, null, true);
    };

    // Read all filter cards from a list into an array of {type, enabled, parameters}
    function _readFilterList(listId) {
        var list = document.getElementById(listId);
        if (!list) return [];
        var out = [];
        list.querySelectorAll('.lc-filter-card').forEach(function(card) {
            var type    = card.dataset.filterType;
            var enabled = card.querySelector('.lc-filter-enabled').checked;
            var params  = {};
            card.querySelectorAll('[data-param]').forEach(function(inp) {
                var key = inp.dataset.param;
                var raw = inp.value.trim();
                // LowPass: cutoff_frequency is optional  omit from JSON if blank
                if (raw === '') return;
                var val = parseFloat(raw);
                if (isNaN(val)) return;
                // integers for window_size
                params[key] = (key === 'window_size') ? Math.round(val) : val;
            });
            out.push({ type: type, enabled: enabled, parameters: params });
        });
        return out;
    }

    // ---- Populate filter inputs from device object ----
    function populateFilters(dev) {
        var rawFilters    = dev.raw_filters    || [];
        var weightFilters = dev.weight_filters || [];
        var levels        = dev.levels         || [];

        // Clear existing cards
        var rawList    = document.getElementById('lc-raw-filter-list');
        var weightList = document.getElementById('lc-weight-filter-list');
        if (rawList)    rawList.innerHTML    = '';
        if (weightList) weightList.innerHTML = '';

        // Render raw filters in order  every entry gets its own card
        rawFilters.forEach(function(f) {
            _appendFilter('lc-raw-filter-list', f.type, f.parameters, f.enabled !== false);
        });

        // Render weight filters in order
        weightFilters.forEach(function(f) {
            _appendFilter('lc-weight-filter-list', f.type, f.parameters, f.enabled !== false);
        });

        _updateEmptyStates();

        function setVal(id, v) { var e = document.getElementById(id); if (e && v !== undefined && v !== null) e.value = v; }
        function setChk(id, v) { var e = document.getElementById(id); if (e) e.checked = !!v; }

        // Levels (fixed set)
        ['low', 'normal', 'high'].forEach(function(name) {
            var lvl = (levels || []).find(function(l) { return l.name === name; });
            setChk('lc-level-' + name + '-enabled', lvl ? lvl.enabled !== false : true);
            setVal('lc-level-' + name + '-ratio',   lvl ? lvl.ratio : (name === 'normal' ? 0.6 : 0.2));
        });
    }

    // ---- Build filter arrays from UI  DOM order IS processing order ----
    function buildFiltersFromUI() {
        var rawFilters    = _readFilterList('lc-raw-filter-list');
        var weightFilters = _readFilterList('lc-weight-filter-list');

        function getVal(id, fallback) { var e = document.getElementById(id); return e ? parseFloat(e.value) : fallback; }
        function isChk(id, fallback)  { var e = document.getElementById(id); return e ? e.checked : !!fallback; }

        var levels = ['low', 'normal', 'high'].map(function(name) {
            return {
                name:    name,
                enabled: isChk('lc-level-' + name + '-enabled', true),
                ratio:   getVal('lc-level-' + name + '-ratio', name === 'normal' ? 0.6 : 0.2)
            };
        });

        return { rawFilters: rawFilters, weightFilters: weightFilters, levels: levels };
    }

    // ---- Save filters (no pipeline needed) ----
    window.saveLoadcellFilters = function() {
        if (!selectedDevice) {
            var s = document.getElementById('lc-filter-status');
            if (s) s.textContent = 'No device loaded.';
            return;
        }
        var s = document.getElementById('lc-filter-status');
        var saveBtn = document.getElementById('lc-save-filters-btn');

        // Update button to show "Send to Pipeline"
        var origBtnHTML = saveBtn ? saveBtn.innerHTML : null;
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Sending to Pipeline…';
        }
        if (s) s.textContent = 'Saving…';

        var built = buildFiltersFromUI();

        fetch('/api/pipeline/filters', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                device_id:      selectedDevice.id,
                raw_filters:    built.rawFilters,
                weight_filters: built.weightFilters,
                levels:         built.levels
            })
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                selectedDevice.raw_filters    = built.rawFilters;
                selectedDevice.weight_filters = built.weightFilters;
                selectedDevice.levels         = built.levels;

                if (data.pipeline_sent) {
                    if (s) {
                        s.textContent = '✓ Configured — sent to pipeline (' + (data.target_service || 'service') + ')';
                        s.style.color = '#16a34a';
                    }
                    if (saveBtn) {
                        saveBtn.innerHTML = '<i class="fa-solid fa-check mr-1"></i> Sent to Pipeline';
                        saveBtn.style.background = '#16a34a';
                        saveBtn.style.color = 'white';
                    }
                } else {
                    // Saved to DB but pipeline not connected — config is queued
                    var isQueued = data.pipeline_message && data.pipeline_message.indexOf('pending') !== -1;
                    if (s) {
                        s.textContent = isQueued
                            ? '⏳ Queued — will configure Load Cell when pipeline is available'
                            : '✓ Saved' + (data.pipeline_message ? ' — ' + data.pipeline_message : '');
                        s.style.color = isQueued ? '#d97706' : '#16a34a';
                    }
                    if (saveBtn) {
                        saveBtn.innerHTML = isQueued
                            ? '<i class="fa-solid fa-clock mr-1"></i> Queued'
                            : '<i class="fa-solid fa-check mr-1"></i> Saved';
                    }
                }
            } else {
                if (s) { s.textContent = '✗ Error: ' + (data.error || 'unknown'); s.style.color = '#dc2626'; }
                if (saveBtn) saveBtn.innerHTML = origBtnHTML || 'Configure Load Cell';
            }
            // Restore button after delay
            setTimeout(function() {
                if (s) { s.textContent = ''; s.style.color = ''; }
                if (saveBtn) {
                    saveBtn.disabled = false;
                    saveBtn.innerHTML = origBtnHTML || 'Configure Load Cell';
                    saveBtn.style.background = '';
                    saveBtn.style.color = '';
                }
            }, 5000);
        })
        .catch(function(e) {
            if (s) { s.textContent = '✗ ' + e.message; s.style.color = '#dc2626'; }
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = origBtnHTML || 'Configure Load Cell';
            }
        });
    };

    // ---- Connect / Disconnect ----
    window.togglePipelineConnection = function () {
        connected ? disconnect() : connect();
    };

    // ---- load_raw whitelist toggle ----
    var loadRawEnabled = false;

    window.toggleLoadRaw = function() {
        loadRawEnabled = !loadRawEnabled;
        fetch('/api/pipeline/load-raw-toggle', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: loadRawEnabled })
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            setLoadRawToggleUI(data.load_raw_enabled);
        })
        .catch(function() {
            // revert optimistic toggle on error
            loadRawEnabled = !loadRawEnabled;
        });
    };

    function setLoadRawToggleUI(isOn) {
        loadRawEnabled = isOn;
        var btn = el('lc-raw-toggle-btn');
        if (!btn) return;
        if (isOn) {
            btn.textContent = 'Raw: ON';
            btn.className = 'px-4 py-2 text-sm font-semibold rounded-lg border border-green-400 bg-green-50 text-green-700 hover:bg-green-100 transition-colors';
        } else {
            btn.textContent = 'Raw: OFF';
            btn.className = 'px-4 py-2 text-sm font-semibold rounded-lg border border-slate-300 bg-slate-50 text-slate-600 hover:bg-slate-100 transition-colors';
        }
    }


    function connect() {
        if (!selectedDevice) { alert('No Load Cell device found.'); return; }
        // UI-only connect: just open the WebSocket for live data display.
        // The pipeline thread runs permanently in the background -- we do NOT
        // call /api/pipeline/connect or /api/pipeline/disconnect from here.
        connected = true;
        setConnectionUI(true);
        openWS();
    }

    function disconnect() {
        // UI-only disconnect: close the WebSocket and reset display.
        // Does NOT touch the pipeline thread or call any pipeline API.
        connected = false;
        currentRaw = null;
        capturedZero = null;
        capturedWeightRaw = null;
        closeWS();
        setConnectionUI(false);
    }

    function setConnectionUI(isConnected) {
        var btn  = el('pipeline-connect-btn');
        var dot  = el('lc-status-dot');
        var txt  = el('lc-status-text');
        var bar  = el('lc-live-bar');
        var calBtn = el('lc-calibrate-btn');

        if (btn) {
            btn.textContent = isConnected ? 'Disconnect' : 'Connect';
            btn.className   = isConnected
                ? 'px-4 py-2 text-sm font-semibold rounded-lg bg-red-50 text-red-600 border border-red-300 hover:bg-red-100 transition-colors'
                : 'px-4 py-2 text-sm font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors';
            btn.disabled = false;
        }
        if (dot) dot.className = isConnected ? 'w-2 h-2 rounded-full bg-green-500' : 'w-2 h-2 rounded-full bg-slate-300';
        if (txt) txt.textContent = isConnected ? 'Connected' : 'Disconnected';
        if (bar) bar.style.display = isConnected ? 'flex' : 'none';
        if (calBtn) calBtn.style.display = isConnected ? 'inline-flex' : 'none';
    }

    function resetBtn() {
        var btn = el('pipeline-connect-btn');
        if (!btn) return;
        btn.textContent = 'Connect';
        btn.className = 'px-4 py-2 text-sm font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors';
        btn.disabled = false;
    }

    // ---- WebSocket ----
    function updateRawDisplay(value) {
        currentRaw = value;
        var display = (value !== null && value !== undefined)
            ? (typeof value === 'number' ? value.toFixed(2) : value)
            : '--';
        var rv = el('lc-raw-value');
        if (rv) rv.textContent = display;
        var mr = el('cal-modal-raw');
        if (mr) mr.textContent = display;   // keep modal in sync
    }

    // Reconnect state -- exponential back-off capped at 15 s
    var _wsReconnectTimer  = null;
    var _wsReconnectDelay  = 2000;   // ms, doubles on each failure up to _WS_MAX_DELAY
    var _WS_MAX_DELAY      = 15000;
    var _wsConnected       = false;  // tracks whether the WS handshake succeeded

    function _scheduleWsReconnect() {
        if (!connected) return;          // user disconnected -- do not reconnect
        if (_wsReconnectTimer) return;   // already scheduled
        _wsReconnectTimer = setTimeout(function() {
            _wsReconnectTimer = null;
            if (connected) openWS();
        }, _wsReconnectDelay);
        // Exponential back-off with a cap
        _wsReconnectDelay = Math.min(_wsReconnectDelay * 2, _WS_MAX_DELAY);
    }

    function _resetWsBackoff() {
        _wsReconnectDelay = 2000;
    }

    function openWS() {
        closeWS();
        var proto = location.protocol === 'https:' ? 'wss' : 'ws';
        _wsConnected = false;
        pipelineWs = new WebSocket(proto + '://' + location.host + '/ws/pipeline/load_raw');

        pipelineWs.onopen = function() {
            _wsConnected = true;
            _resetWsBackoff();
            // Fallback: if the backend had no buffered value yet (load_raw was None when
            // we connected), poll the REST status endpoint to pick up the latest value.
            fetch('/api/pipeline/status', { credentials: 'same-origin' })
                .then(function(r) { return r.json(); })
                .then(function(d) {
                    var rawKey = rawDatapoint || 'load_raw';
                    if (d[rawKey] !== null && d[rawKey] !== undefined && currentRaw === null) {
                        updateRawDisplay(d[rawKey]);
                    }
                })
                .catch(function() {});
        };

        pipelineWs.onmessage = function(evt) {
            try {
                var msg = JSON.parse(evt.data);
                if (msg.datapoint === (rawDatapoint || 'load_raw')) {
                    updateRawDisplay(msg.value);
                }
                // Handle any whitelisted datapoint updates (weight, capacity, etc.)
                if (msg.datapoint && msg.datapoint.startsWith('loadcells.')) {
                    _handleLoadcellDp(msg.datapoint, msg.value);
                }
            } catch(e) {}
        };

        pipelineWs.onerror = function(e) {
            // Log but do not crash -- onclose will fire right after and handle reconnect
            console.warn('[WS] error event', e);
        };

        pipelineWs.onclose = function(evt) {
            _wsConnected = false;
            // evt.code 1000 = normal close (we called closeWS intentionally),
            // anything else is unexpected -- schedule a reconnect.
            if (connected && evt.code !== 1000) {
                _scheduleWsReconnect();
            }
        };
    }

    function closeWS() {
        if (_wsReconnectTimer) {
            clearTimeout(_wsReconnectTimer);
            _wsReconnectTimer = null;
        }
        _resetWsBackoff();
        if (pipelineWs) {
            pipelineWs.onclose = null;   // prevent reconnect on intentional close
            pipelineWs.onerror = null;
            pipelineWs.close(1000, 'user disconnect');
            pipelineWs = null;
        }
        _wsConnected = false;
    }

    // Handle live loadcell datapoint updates arriving over WebSocket.
    // Only updates display fields -- never triggers any pipeline operation.
    function _handleLoadcellDp(dp, value) {
        if (!selectedDevice) return;
        var prefix = 'loadcells.' + selectedDevice.name + '.';
        if (!dp.startsWith(prefix)) return;
        var field = dp.slice(prefix.length);
        if (field === 'weight_kg') {
            var wv = el('lc-weight-value');
            if (wv) wv.textContent = (value !== null && value !== undefined)
                ? parseFloat(value).toFixed(2) : '--';
        } else if (field === 'capacity') {
            var cv = el('lc-capacity-value');
            if (cv) cv.textContent = (value !== null && value !== undefined)
                ? parseFloat(value).toFixed(0) : '--';
        } else if (field === 'tared') {
            var tv = el('lc-tared-value');
            if (tv) tv.textContent = (value !== null && value !== undefined)
                ? parseFloat(value).toFixed(2) : '--';
        }
    }

    // ---- Calibration modal ----
    window.openCalibrationModal = function() {
        var modal = el('lc-cal-modal');
        if (!modal) return;
        modal.style.display = 'flex';
        // Pre-fill from saved device data
        if (selectedDevice) {
            if (selectedDevice.tare_offset !== null && selectedDevice.tare_offset !== undefined) {
                capturedZero = selectedDevice.tare_offset;
                var zd = el('cal-zero-display');
                if (zd) zd.textContent = parseFloat(selectedDevice.tare_offset).toFixed(2);
            }
            if (selectedDevice.known_weight) {
                var wi = el('cal-weight-input');
                if (wi) wi.value = selectedDevice.known_weight;
            }
            if (selectedDevice.known_weight_raw) {
                var wr = el('cal-weight-raw-display');
                if (wr) wr.textContent = parseFloat(selectedDevice.known_weight_raw).toFixed(2);
            }
        }
        // Show current raw
        var mr = el('cal-modal-raw');
        if (mr) mr.textContent = currentRaw !== null ? parseFloat(currentRaw).toFixed(2) : '--';
    };

    window.closeCalibrationModal = function() {
        var modal = el('lc-cal-modal');
        if (modal) modal.style.display = 'none';
        var s = el('cal-status'); if (s) s.textContent = '';
    };

    window.captureZero = function() {
        var s = el('cal-status');
        if (currentRaw === null) { if (s) s.textContent = 'No raw value yet.'; return; }
        capturedZero = currentRaw;
        var zd = el('cal-zero-display');
        if (zd) zd.textContent = capturedZero.toFixed(2);
        if (s)  s.textContent  = 'Zero captured: ' + capturedZero.toFixed(2);
    };

    window.captureWeightRaw = function() {
        var s = el('cal-status');
        if (currentRaw === null) { if (s) s.textContent = 'No raw value yet.'; return; }
        capturedWeightRaw = currentRaw;
        var wr = el('cal-weight-raw-display');
        if (wr) wr.textContent = capturedWeightRaw.toFixed(2);
        if (s)  s.textContent  = 'Weight raw captured: ' + capturedWeightRaw.toFixed(2);
    };

    window.saveCalibration = function() {
        var s = el('cal-status');
        if (!selectedDevice) { if (s) s.textContent = 'No device.'; return; }
        if (capturedZero === null) { if (s) s.textContent = 'Capture zero state first.'; return; }

        var wi = el('cal-weight-input');
        var knownWeight = wi ? parseFloat(wi.value) : NaN;
        if (isNaN(knownWeight)) { if (s) s.textContent = 'Enter a valid known weight.'; return; }

        // Use explicitly captured weight raw -- fall back to current live raw, then DB value.
        // capturedWeightRaw is set by the "Capture Weight Raw" button when user places the known
        // weight on the scale, ensuring the correct raw value is stored even if the live stream
        // fluctuates before the user clicks Save.
        var knownWeightRaw = capturedWeightRaw !== null
            ? capturedWeightRaw
            : (currentRaw !== null ? currentRaw : (selectedDevice.known_weight_raw || 0));
        if (s) s.textContent = 'Saving...';

        fetch('/api/pipeline/calibration', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                device_id:        selectedDevice.id,
                tare_offset:      capturedZero,
                known_weight:     knownWeight,
                known_weight_raw: knownWeightRaw
            })
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                if (s) s.textContent = 'Saved ?';
                var wr = el('cal-weight-raw-display');
                if (wr) wr.textContent = knownWeightRaw.toFixed(2);
                selectedDevice.tare_offset      = capturedZero;
                selectedDevice.known_weight     = knownWeight;
                selectedDevice.known_weight_raw = knownWeightRaw;
                capturedWeightRaw = null;   // reset for next calibration session
                setTimeout(window.closeCalibrationModal, 1200);
            } else {
                if (s) s.textContent = 'Error: ' + (data.error || 'unknown');
            }
        })
        .catch(function(e) { if (s) s.textContent = 'Error: ' + e.message; });
    };

    // ---- Router hooks ----
    window.initCraneIQ = function() {
        connected = false;
        pipelineWs = null;
        currentRaw = null;
        capturedZero = null;
        capturedWeightRaw = null;
        selectedDevice = null;
        rawDatapoint = null;
        setConnectionUI(false);
        loadDevice();
        initStaticUI();
        // Sync load_raw toggle state from backend
        fetch('/api/pipeline/load-raw-toggle', { credentials: 'same-origin' })
            .then(function(r) { return r.json(); })
            .then(function(d) { setLoadRawToggleUI(d.load_raw_enabled || false); })
            .catch(function() { setLoadRawToggleUI(false); });
    };

    window.cleanupCraneIQ = function() {
        if (connected) disconnect();
        closeCalibrationModal();
        cleanupStaticUI();
    };

    window.addEventListener('beforeunload', function() {
        if (connected) disconnect();
    });
})();


// ============================================================
// PART 2: Static UI logic   NEW sections (no backend)
// ============================================================
(function () {
    'use strict';

    // ---- State ----
    var dataloggers = [];
    var nextLoggerId = 1;

    // ---- Device tags map ----
    var deviceTags = {
        load_cell: [
            { name: 'Current Load',    address: '40001', type: 'REAL',   description: 'Real-time load measurement in kg' },
            { name: 'Peak Load',       address: '40003', type: 'REAL',   description: 'Maximum load recorded in current session' },
            { name: 'Load Cell Status',address: '40005', type: 'UINT16', description: 'Sensor health status (0=OK, 1=Warning, 2=Error)' }
        ],
        anti_collision: [
            { name: 'Distance to Obstacle', address: '40101', type: 'REAL', description: 'Closest obstacle distance in meters' },
            { name: 'Collision Warning',    address: '40103', type: 'BOOL', description: 'Warning flag when approaching obstacle' },
            { name: 'Emergency Stop',       address: '40104', type: 'BOOL', description: 'Emergency stop triggered by anti-collision' }
        ],
        emergency_stop: [
            { name: 'E-Stop Status',  address: '40201', type: 'BOOL',   description: 'Emergency stop button status' },
            { name: 'Stop Timestamp', address: '40202', type: 'UINT32', description: 'Unix timestamp of last stop' }
        ],
        hoist_motor: [
            { name: 'Motor Speed',       address: '40301', type: 'REAL', description: 'Current motor RPM' },
            { name: 'Motor Current',     address: '40303', type: 'REAL', description: 'Motor current draw in Amps' },
            { name: 'Motor Temperature', address: '40305', type: 'REAL', description: 'Motor winding temperature in  C' }
        ],
        trolley_motor: [
            { name: 'Trolley Position', address: '40401', type: 'REAL', description: 'Trolley position on beam in meters' },
            { name: 'Trolley Speed',    address: '40403', type: 'REAL', description: 'Trolley movement speed m/s' }
        ],
        bridge_motor: [
            { name: 'Bridge Position', address: '40501', type: 'REAL', description: 'Bridge position in bay (meters)' },
            { name: 'Bridge Speed',    address: '40503', type: 'REAL', description: 'Bridge movement speed m/s' }
        ],
        encoder_x: [
            { name: 'X Position', address: '40601', type: 'REAL', description: 'X-axis absolute position in meters' },
            { name: 'X Velocity', address: '40603', type: 'REAL', description: 'X-axis velocity m/s' }
        ],
        encoder_y: [
            { name: 'Y Position', address: '40701', type: 'REAL', description: 'Y-axis absolute position in meters' },
            { name: 'Y Velocity', address: '40703', type: 'REAL', description: 'Y-axis velocity m/s' }
        ],
        encoder_z: [
            { name: 'Z Position', address: '40801', type: 'REAL', description: 'Z-axis (height) position in meters' },
            { name: 'Z Velocity', address: '40803', type: 'REAL', description: 'Z-axis velocity m/s' }
        ],
        main_brake: [
            { name: 'Brake Status', address: '40901', type: 'BOOL',   description: 'Brake engaged (1) or released (0)' },
            { name: 'Brake Wear',   address: '40902', type: 'UINT16', description: 'Brake wear percentage (0-100)' }
        ],
        trolley_brake: [
            { name: 'Brake Status',   address: '41001', type: 'BOOL', description: 'Brake engaged (1) or released (0)' },
            { name: 'Brake Pressure', address: '41002', type: 'REAL', description: 'Hydraulic pressure in bar' }
        ],
        weather_station: [
            { name: 'Wind Speed',    address: '41101', type: 'REAL',   description: 'Current wind speed in m/s' },
            { name: 'Wind Direction',address: '41103', type: 'UINT16', description: 'Wind direction in degrees (0-360)' },
            { name: 'Temperature',   address: '41105', type: 'REAL',   description: 'Ambient temperature in  C' },
            { name: 'Humidity',      address: '41107', type: 'REAL',   description: 'Relative humidity percentage' }
        ],
        vibration_sensor: [
            { name: 'Vibration Level',    address: '41201', type: 'REAL', description: 'Vibration magnitude in mm/s' },
            { name: 'Vibration Frequency',address: '41203', type: 'REAL', description: 'Dominant frequency in Hz' }
        ],
        temperature_sensor: [
            { name: 'Temperature 1', address: '41301', type: 'REAL', description: 'First sensor reading  C' },
            { name: 'Temperature 2', address: '41302', type: 'REAL', description: 'Second sensor reading  C' },
            { name: 'Temperature 3', address: '41303', type: 'REAL', description: 'Third sensor reading  C' }
        ],
        wind_sensor: [
            { name: 'Wind Speed', address: '41401', type: 'REAL', description: 'Current wind speed in m/s' },
            { name: 'Gust Speed', address: '41403', type: 'REAL', description: 'Peak gust speed in m/s' }
        ]
    };

    var priorityColors = {
        critical: { bg: 'bg-red-100',    text: 'text-red-800' },
        high:     { bg: 'bg-orange-100', text: 'text-orange-800' },
        medium:   { bg: 'bg-yellow-100', text: 'text-yellow-800' },
        low:      { bg: 'bg-blue-100',   text: 'text-blue-800' }
    };

    var conditionDisplay = {
        always:    'Always Log',
        on_change: 'On Value Change',
        threshold: 'Threshold Based',
        periodic:  'Periodic Intervals'
    };

    // ---- Helpers ----
    function showNotification(message, type) {
        type = type || 'info';
        var container = document.getElementById('notification-container');
        if (!container) return;
        var colors = {
            info:    'bg-blue-50 text-blue-800 border-blue-200',
            success: 'bg-green-50 text-green-800 border-green-200',
            warning: 'bg-amber-50 text-amber-800 border-amber-200',
            error:   'bg-red-50 text-red-800 border-red-200'
        };
        var n = document.createElement('div');
        n.className = 'px-4 py-3 rounded-md shadow-lg border pointer-events-auto transform transition-all duration-300 opacity-0 translate-x-8 ' + (colors[type] || colors.info);
        n.textContent = message;
        container.appendChild(n);
        setTimeout(function() { n.classList.remove('opacity-0', 'translate-x-8'); }, 10);
        setTimeout(function() {
            n.classList.add('opacity-0', 'translate-x-8');
            setTimeout(function() { n.remove(); }, 300);
        }, 4000);
    }

    function calculateDataRate(samplingMs) {
        var bytesPerSample = 4;
        var samplesPerHour = 3600000 / samplingMs;
        return (bytesPerSample * samplesPerHour) / (1024 * 1024);
    }

    function calculateEstimatedDuration(storageMB, dataRateMBPerHour) {
        var hours = storageMB / dataRateMBPerHour;
        if (hours >= 8760) return '>1 year';
        if (hours >= 720)  return Math.round(hours / 730) + ' months';
        if (hours >= 24)   return Math.round(hours / 24) + ' days';
        return Math.round(hours) + ' hours';
    }

    function getConditionDetails(condition) {
        var map = {
            always:    'Continuous logging',
            on_change: 'Log when value changes',
            threshold: 'Log when threshold exceeded',
            periodic:  'Log at set intervals'
        };
        return map[condition] || 'Custom condition';
    }

    // ---- Operating Mode buttons ----
    function initModeButtons() {
        var container = document.getElementById('operating-mode-btns');
        if (!container) return;
        var btns = container.querySelectorAll('.mode-btn');
        btns.forEach(function(btn) {
            btn.addEventListener('click', function() {
                btns.forEach(function(b) {
                    b.classList.remove('bg-blue-600', 'text-white', 'shadow');
                    b.classList.add('text-slate-600');
                });
                btn.classList.add('bg-blue-600', 'text-white', 'shadow');
                btn.classList.remove('text-slate-600');
                showNotification('Operating mode: ' + btn.textContent.trim(), 'info');
            });
        });
    }

    // ---- Upload layout button ----
    function initLayoutBtn() {
        var btn = document.getElementById('upload-layout-btn');
        if (btn) {
            btn.addEventListener('click', function() {
                showNotification('Select a floor plan or CAD file to upload', 'info');
            });
        }
    }

    // ---- Add peer / add zone buttons ----
    function initZoneButtons() {
        var peerBtn = document.getElementById('add-peer-btn');
        if (peerBtn) peerBtn.addEventListener('click', function() { showNotification('Add peer crane for multi-crane coordination', 'info'); });

        var zoneBtn = document.getElementById('add-zone-btn');
        if (zoneBtn) zoneBtn.addEventListener('click', function() { showNotification('Define new safety or operational zone', 'info'); });
    }

    // ---- Load curve upload ----
    function initLoadCurve() {
        var area = document.getElementById('load-curve-upload');
        var fileInput = document.getElementById('load-curve-file');
        if (area && fileInput) {
            area.addEventListener('click', function() { fileInput.click(); });
            fileInput.addEventListener('change', function(e) {
                if (e.target.files.length > 0) {
                    showNotification('Load curve file: ' + e.target.files[0].name, 'success');
                }
            });
        }
    }

    // ---- Datalogger modal ----
    function openDrawer() {
        var drawer   = document.getElementById('add-datalogger-modal');
        var backdrop = document.getElementById('drawer-backdrop');
        if (!drawer) return;
        // Make backdrop visible then fade in
        if (backdrop) {
            backdrop.classList.remove('hidden');
            setTimeout(function() { backdrop.classList.remove('opacity-0'); backdrop.classList.add('opacity-100'); }, 10);
        }
        // Slide drawer in from left
        drawer.classList.remove('-translate-x-full');
        drawer.classList.add('translate-x-0');
    }

    function closeDrawer() {
        var drawer   = document.getElementById('add-datalogger-modal');
        var backdrop = document.getElementById('drawer-backdrop');
        if (!drawer) return;
        // Slide drawer back out
        drawer.classList.remove('translate-x-0');
        drawer.classList.add('-translate-x-full');
        // Fade out backdrop then hide
        if (backdrop) {
            backdrop.classList.remove('opacity-100');
            backdrop.classList.add('opacity-0');
            setTimeout(function() { backdrop.classList.add('hidden'); }, 310);
        }
    }

    function initDataloggerModal() {
        var addBtn     = document.getElementById('add-datalogger-btn');
        var modal      = document.getElementById('add-datalogger-modal');
        var cancelBtn  = document.getElementById('cancel-datalogger');
        var closeBtn   = document.getElementById('close-drawer-btn');
        var backdrop   = document.getElementById('drawer-backdrop');
        var saveBtn    = document.getElementById('save-datalogger');
        var deviceSel  = document.getElementById('logger-device-select');
        var tagSel     = document.getElementById('logger-tag-select');
        var storageSz  = document.getElementById('logger-storage-size');
        var storageUn  = document.getElementById('logger-storage-unit');
        var sampRate   = document.getElementById('sampling-rate');

        if (!modal) return;

        if (addBtn)   addBtn.addEventListener('click', openDrawer);
        if (backdrop) backdrop.addEventListener('click', function() { closeDrawer(); resetModalForm(); });
        if (closeBtn) closeBtn.addEventListener('click', function() { closeDrawer(); resetModalForm(); });

        if (cancelBtn) cancelBtn.addEventListener('click', function() {
            closeDrawer();
            resetModalForm();
        });

        if (saveBtn) saveBtn.addEventListener('click', saveDatalogger);

        // Device ? populate tags
        if (deviceSel && tagSel) {
            deviceSel.addEventListener('change', function() {
                var dt = deviceTags[this.value];
                tagSel.disabled = !dt;
                tagSel.innerHTML = dt
                    ? '<option value="">-- Select a tag --</option>'
                    : '<option value="">-- First select a device --</option>';
                if (dt) {
                    dt.forEach(function(tag) {
                        var o = document.createElement('option');
                        o.value = JSON.stringify(tag);
                        o.textContent = tag.name + ' (' + tag.address + ')';
                        tagSel.appendChild(o);
                    });
                }
                document.getElementById('tag-description').classList.add('hidden');
            });

            tagSel.addEventListener('change', function() {
                var desc = document.getElementById('tag-description');
                var descTxt = document.getElementById('tag-desc-text');
                var addrTxt = document.getElementById('tag-address');
                if (this.value && desc && descTxt && addrTxt) {
                    try {
                        var tag = JSON.parse(this.value);
                        descTxt.textContent = tag.description;
                        addrTxt.textContent = tag.address + ' (' + tag.type + ')';
                        desc.classList.remove('hidden');
                    } catch(e) { desc.classList.add('hidden'); }
                } else if (desc) { desc.classList.add('hidden'); }
            });
        }

        // Condition radio panels
        var condRadios = document.querySelectorAll('input[name="logger-condition"]');
        condRadios.forEach(function(r) {
            r.addEventListener('change', function() {
                updateConditionPanel(this.value);
            });
        });
        // Show default panel (periodic is checked by default)
        updateConditionPanel('periodic');

        // Duration estimate
        function updateDuration() {
            if (!storageSz || !storageUn || !sampRate) return;
            var size    = parseFloat(storageSz.value) || 100;
            var unit    = storageUn.value;
            var ms      = parseInt(sampRate.value) || 5000;
            var mb      = unit === 'gb' ? size * 1024 : size;
            var rate    = calculateDataRate(ms);
            var dur     = calculateEstimatedDuration(mb, rate);
            var el      = document.getElementById('estimated-duration');
            if (el) el.textContent = dur;
        }
        if (storageSz) storageSz.addEventListener('input', updateDuration);
        if (storageUn) storageUn.addEventListener('change', updateDuration);
        if (sampRate)  sampRate.addEventListener('change', updateDuration);
        updateDuration();
    }

    function updateConditionPanel(value) {
        var panels = ['always-config', 'on-change-config', 'threshold-config', 'periodic-config'];
        var map = { always: 'always-config', on_change: 'on-change-config', threshold: 'threshold-config', periodic: 'periodic-config' };
        panels.forEach(function(id) {
            var el = document.getElementById(id);
            if (el) el.style.display = (id === map[value]) ? 'block' : 'none';
        });
    }

    function resetModalForm() {
        var deviceSel = document.getElementById('logger-device-select');
        var tagSel    = document.getElementById('logger-tag-select');
        if (deviceSel) deviceSel.value = '';
        if (tagSel) { tagSel.innerHTML = '<option value="">-- First select a device --</option>'; tagSel.disabled = true; }
        var desc = document.getElementById('tag-description');
        if (desc) desc.classList.add('hidden');
        document.querySelectorAll('input[name="logger-priority"]').forEach(function(i) { i.checked = false; });
        document.querySelectorAll('input[name="logger-condition"]').forEach(function(i) {
            if (i.value === 'periodic') i.checked = true; else i.checked = false;
        });
        updateConditionPanel('periodic');
    }

    function saveDatalogger() {
        var deviceSel    = document.getElementById('logger-device-select');
        var tagSel       = document.getElementById('logger-tag-select');
        var priorityIn   = document.querySelector('input[name="logger-priority"]:checked');
        var conditionIn  = document.querySelector('input[name="logger-condition"]:checked');
        var storageSz    = document.getElementById('logger-storage-size');
        var storageUn    = document.getElementById('logger-storage-unit');
        var sampRate     = document.getElementById('sampling-rate');
        var dataFmt      = document.getElementById('data-format');

        if (!deviceSel  || !deviceSel.value)  return showNotification('Please select a device', 'warning');
        if (!tagSel     || !tagSel.value)      return showNotification('Please select a data tag', 'warning');
        if (!priorityIn)                       return showNotification('Please select a priority level', 'warning');
        if (!conditionIn)                      return showNotification('Please select a logging condition', 'warning');

        try {
            var deviceName = deviceSel.options[deviceSel.selectedIndex].textContent;
            var tag        = JSON.parse(tagSel.value);
            var size       = parseFloat(storageSz.value) || 100;
            var unit       = storageUn.value;
            var ms         = parseInt(sampRate.value) || 5000;
            var dataRate   = calculateDataRate(ms);
            var storageMB  = unit === 'gb' ? size * 1024 : size;

            var logger = {
                id:         nextLoggerId++,
                device:     { name: deviceName, deviceId: deviceSel.value },
                tag:        tag,
                priority:   priorityIn.value,
                condition:  conditionIn.value,
                condDetail: getConditionDetails(conditionIn.value),
                storage:    { size: size, unit: unit, totalMB: storageMB },
                sampling:   { interval: ms, display: sampRate.options[sampRate.selectedIndex].text },
                dataFormat: dataFmt.options[dataFmt.selectedIndex].text,
                dataRate:   dataRate,
                status:     'active',
                createdAt:  new Date().toISOString()
            };

            dataloggers.push(logger);
            renderLoggersTable();
            updateSummaryStats();
            closeDrawer();
            showNotification('Datalogger created successfully', 'success');
            resetModalForm();
        } catch (err) {
            showNotification('Error creating datalogger', 'error');
        }
    }

    function renderLoggersTable() {
        var tbody     = document.getElementById('loggers-table-body');
        var emptyRow  = document.getElementById('no-loggers-row');
        if (!tbody || !emptyRow) return;

        if (dataloggers.length === 0) {
            emptyRow.classList.remove('hidden');
            // Remove any dynamically added rows
            Array.from(tbody.querySelectorAll('tr:not(#no-loggers-row)')).forEach(function(r){ r.remove(); });
            return;
        }

        emptyRow.classList.add('hidden');
        // Remove old dynamic rows
        Array.from(tbody.querySelectorAll('tr:not(#no-loggers-row)')).forEach(function(r){ r.remove(); });

        dataloggers.forEach(function(logger) {
            var pc  = priorityColors[logger.priority] || priorityColors.medium;
            var dur = calculateEstimatedDuration(logger.storage.totalMB, logger.dataRate);
            var row = document.createElement('tr');
            row.className = 'hover:bg-slate-50';
            row.innerHTML =
                '<td class="px-4 py-3"><div class="font-medium text-slate-900">' + logger.device.name + '</div><div class="text-xs text-slate-500">' + logger.device.deviceId + '</div></td>' +
                '<td class="px-4 py-3"><div class="font-medium text-slate-900">' + logger.tag.name + '</div><div class="text-xs text-slate-500">' + logger.tag.address + ' \u2022 ' + logger.tag.type + '</div></td>' +
                '<td class="px-4 py-3"><span class="px-2 py-1 text-xs font-medium rounded-full ' + pc.bg + ' ' + pc.text + '">' + logger.priority.charAt(0).toUpperCase() + logger.priority.slice(1) + '</span></td>' +
                '<td class="px-4 py-3"><div class="text-sm font-medium text-slate-900">' + (conditionDisplay[logger.condition] || logger.condition) + '</div><div class="text-xs text-slate-500">' + logger.condDetail + '</div></td>' +
                '<td class="px-4 py-3"><div class="text-sm font-medium text-slate-900">' + logger.storage.size + ' ' + logger.storage.unit.toUpperCase() + '</div><div class="text-xs text-slate-500">~' + dur + '</div></td>' +
                '<td class="px-4 py-3"><div class="text-sm text-slate-900">' + logger.sampling.display + '</div><div class="text-xs text-slate-500">' + logger.dataFormat + '</div></td>' +
                '<td class="px-4 py-3"><span class="px-2 py-1 text-xs font-medium rounded-full ' + (logger.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-slate-100 text-slate-800') + '">' + (logger.status === 'active' ? 'Active' : 'Paused') + '</span></td>' +
                '<td class="px-4 py-3"><div class="flex items-center gap-2">' +
                  '<button class="delete-logger text-red-600 hover:text-red-800 p-1 rounded hover:bg-red-50 text-xs" data-id="' + logger.id + '" title="Delete">&#x1F5D1;</button>' +
                  '<button class="toggle-logger p-1 rounded hover:bg-slate-100 text-xs ' + (logger.status === 'active' ? 'text-green-600' : 'text-slate-400') + '" data-id="' + logger.id + '" title="Toggle">&#x23FC;</button>' +
                '</div></td>';
            tbody.appendChild(row);
        });

        // Attach event listeners for delete / toggle
        tbody.querySelectorAll('.delete-logger').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var id = parseInt(this.dataset.id);
                if (confirm('Delete this datalogger?')) {
                    dataloggers = dataloggers.filter(function(l){ return l.id !== id; });
                    renderLoggersTable();
                    updateSummaryStats();
                    showNotification('Datalogger deleted', 'success');
                }
            });
        });
        tbody.querySelectorAll('.toggle-logger').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var id = parseInt(this.dataset.id);
                var logger = dataloggers.find(function(l){ return l.id === id; });
                if (logger) {
                    logger.status = logger.status === 'active' ? 'paused' : 'active';
                    renderLoggersTable();
                    updateSummaryStats();
                    showNotification('Datalogger ' + logger.status, 'info');
                }
            });
        });
    }

    function updateSummaryStats() {
        var activeEl   = document.getElementById('active-loggers-count');
        var storageEl  = document.getElementById('total-storage');
        var rateEl     = document.getElementById('total-data-rate');
        var healthEl   = document.getElementById('buffer-health');

        var activeCount = dataloggers.filter(function(l){ return l.status === 'active'; }).length;
        var totalMB     = dataloggers.reduce(function(s, l){ return s + l.storage.totalMB; }, 0);
        var totalRate   = dataloggers.filter(function(l){ return l.status === 'active'; }).reduce(function(s, l){ return s + l.dataRate; }, 0);
        var health      = dataloggers.length === 0 ? 'N/A' : dataloggers.length < 5 ? 'Good' : dataloggers.length < 10 ? 'Fair' : 'High Load';

        if (activeEl)  activeEl.textContent  = activeCount;
        if (storageEl) storageEl.textContent = Math.round(totalMB) + ' MB';
        if (rateEl)    rateEl.textContent    = totalRate.toFixed(2) + ' MB/h';
        if (healthEl)  healthEl.textContent  = health;
    }

    // ---- Public init / cleanup ----
    window.initStaticUI = function() {
        dataloggers  = [];
        nextLoggerId = 1;
        initModeButtons();
        initLayoutBtn();
        initZoneButtons();
        initLoadCurve();
        initDataloggerModal();
        renderLoggersTable();
        updateSummaryStats();
    };

    window.cleanupStaticUI = function() {
        dataloggers  = [];
        nextLoggerId = 1;
    };

    // If initCraneIQ hasn't been overridden yet (standalone load), expose directly
    if (typeof window.initCraneIQ === 'undefined') {
        window.initCraneIQ = function() { window.initStaticUI(); };
    }

})();