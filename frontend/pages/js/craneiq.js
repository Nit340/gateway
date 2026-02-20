// craneiq.js
(function () {
    var pipelineWs = null;
    var connected = false;
    var currentRaw = null;
    var capturedZero = null;
    var selectedDevice = null;

    function el(id) { return document.getElementById(id); }
    function safe(id, prop, val) {
        var e = el(id);
        if (!e) return;
        var parts = prop.split('.');
        if (parts.length === 2) { e[parts[0]][parts[1]] = val; }
        else { e[prop] = val; }
    }

    // ---- Load devices on init ----
    function loadDevices() {
        var sel = el('lc-device-select');
        if (!sel) return;
        sel.innerHTML = '<option value="">Loading...</option>';
        sel.disabled = true;

        fetch('/api/pipeline/loadcell-devices')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var devices = data.devices || [];
            if (devices.length === 0) {
                sel.innerHTML = '<option value="">No devices found</option>';
                safe('lc-no-devices', 'style.display', 'block');
                var btn = el('pipeline-connect-btn');
                if (btn) { btn.disabled = true; btn.style.opacity = '0.4'; }
                return;
            }
            sel.innerHTML = '';
            devices.forEach(function(d) {
                var opt = document.createElement('option');
                opt.value = d.id;
                opt.textContent = d.name;
                opt._device = d;
                sel.appendChild(opt);
            });
            sel.disabled = false;
            safe('lc-no-devices', 'style.display', 'none');
            var btn = el('pipeline-connect-btn');
            if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
        })
        .catch(function(e) {
            if (sel) sel.innerHTML = '<option value="">Error loading</option>';
        });
    }

    function getSelectedDevice() {
        var sel = el('lc-device-select');
        if (!sel || !sel.value) return null;
        var opt = sel.options[sel.selectedIndex];
        return opt._device || null;
    }

    // ---- Connect / Disconnect ----
    window.togglePipelineConnection = function () {
        connected ? disconnect() : connect();
    };

    function connect() {
        var dev = getSelectedDevice();
        if (!dev) {
            alert('Please select a Load Cell device.');
            return;
        }
        selectedDevice = dev;

        var btn = el('pipeline-connect-btn');
        if (btn) { btn.textContent = 'Connecting...'; btn.disabled = true; }

        fetch('/api/pipeline/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                host: dev.pipeline_server || '127.0.0.1',
                port: dev.pipeline_port || 7000
            })
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                connected = true;
                safe('lc-device-label', 'textContent', dev.name);
                safe('lc-idle', 'style.display', 'none');
                safe('lc-live', 'style.display', 'block');

                // Pre-fill saved calibration
                if (dev.tare_offset !== null && dev.tare_offset !== undefined) {
                    capturedZero = dev.tare_offset;
                    safe('cal-zero-display', 'textContent', parseFloat(dev.tare_offset).toFixed(2));
                }
                if (dev.known_weight) safe('cal-weight-input', 'value', dev.known_weight);
                if (dev.known_weight_raw) safe('cal-weight-raw-display', 'textContent', parseFloat(dev.known_weight_raw).toFixed(2));

                openWS();
            } else {
                alert('Connection failed: ' + (data.error || 'unknown'));
                resetBtn();
            }
        })
        .catch(function(e) {
            alert('Error: ' + e.message);
            resetBtn();
        });
    }

    function disconnect() {
        closeWS();
        fetch('/api/pipeline/disconnect', { method: 'POST' }).catch(function(){});
        connected = false;
        currentRaw = null;
        capturedZero = null;
        selectedDevice = null;

        safe('lc-idle', 'style.display', 'block');
        safe('lc-live', 'style.display', 'none');
        safe('lc-raw-value', 'textContent', '--');
        safe('lc-device-label', 'textContent', 'Not connected');
        safe('cal-zero-display', 'textContent', '--');
        safe('cal-weight-input', 'value', '');
        safe('cal-weight-raw-display', 'textContent', '-- (use current raw)');
        safe('cal-note', 'value', '');
        safe('cal-status', 'textContent', '');
        resetBtn();
    }

    function resetBtn() {
        var btn = el('pipeline-connect-btn');
        if (!btn) return;
        btn.textContent = 'Connect';
        btn.style.background = '#2563eb';
        btn.style.opacity = '1';
        btn.disabled = false;
    }

    // ---- WebSocket ----
    function openWS() {
        closeWS();
        var proto = location.protocol === 'https:' ? 'wss' : 'ws';
        pipelineWs = new WebSocket(proto + '://' + location.host + '/ws/pipeline/load_raw');

        pipelineWs.onmessage = function(evt) {
            try {
                var msg = JSON.parse(evt.data);
                if (msg.datapoint === 'load_raw') {
                    currentRaw = msg.value;
                    var display = (msg.value !== null && msg.value !== undefined)
                        ? (typeof msg.value === 'number' ? msg.value.toFixed(2) : msg.value)
                        : '--';
                    safe('lc-raw-value', 'textContent', display);
                }
            } catch(e) {}
        };
        pipelineWs.onerror = function() {};
        pipelineWs.onclose = function() {
            if (connected) setTimeout(openWS, 2000);
        };
    }

    function closeWS() {
        if (pipelineWs) {
            pipelineWs.onclose = null;
            pipelineWs.close();
            pipelineWs = null;
        }
    }

    // ---- Calibration ----
    window.captureZero = function() {
        if (currentRaw === null) { safe('cal-status', 'textContent', 'No raw value yet.'); return; }
        capturedZero = currentRaw;
        safe('cal-zero-display', 'textContent', capturedZero.toFixed(2));
        safe('cal-status', 'textContent', 'Zero captured: ' + capturedZero.toFixed(2));
    };

    window.saveCalibration = function() {
        if (!selectedDevice) { safe('cal-status', 'textContent', 'No device selected.'); return; }
        if (capturedZero === null) { safe('cal-status', 'textContent', 'Capture zero state first.'); return; }

        var wi = el('cal-weight-input');
        var knownWeight = wi ? parseFloat(wi.value) : NaN;
        if (isNaN(knownWeight)) { safe('cal-status', 'textContent', 'Enter a valid known weight.'); return; }

        var knownWeightRaw = currentRaw !== null ? currentRaw : (selectedDevice.known_weight_raw || 0);

        safe('cal-status', 'textContent', 'Saving...');

        fetch('/api/pipeline/calibration', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                device_id: selectedDevice.id,
                tare_offset: capturedZero,
                known_weight: knownWeight,
                known_weight_raw: knownWeightRaw
            })
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                safe('cal-status', 'textContent', 'Saved successfully.');
                safe('cal-weight-raw-display', 'textContent', knownWeightRaw.toFixed(2));
                selectedDevice.tare_offset = capturedZero;
                selectedDevice.known_weight = knownWeight;
                selectedDevice.known_weight_raw = knownWeightRaw;
            } else {
                safe('cal-status', 'textContent', 'Error: ' + (data.error || 'unknown'));
            }
        })
        .catch(function(e) { safe('cal-status', 'textContent', 'Error: ' + e.message); });
    };

    // ---- Router hooks ----
    window.initCraneIQ = function() {
        connected = false;
        pipelineWs = null;
        currentRaw = null;
        capturedZero = null;
        selectedDevice = null;
        safe('lc-idle', 'style.display', 'block');
        safe('lc-live', 'style.display', 'none');
        safe('lc-device-label', 'textContent', 'Not connected');
        resetBtn();
        loadDevices();
    };

    window.cleanupCraneIQ = function() {
        if (connected) disconnect();
    };

    window.addEventListener('beforeunload', function() {
        if (connected) disconnect();
    });
})();