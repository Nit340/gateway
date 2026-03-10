// general-config.js
console.log('general-config.js loaded');

(function () {
    if (window._generalConfigInitialized || window._generalConfigInitializing) return;

    // =========================================================================
    // HELPERS
    // =========================================================================
    var $ = function (s) { return document.querySelector(s); };

    var setInputValue = function (s, v) {
        if (v === undefined || v === null) return;
        var el = $(s); if (el) { el.value = v; el.dispatchEvent(new Event('change', {bubbles:true})); }
    };
    var setRadioValue = function (s, v) {
        if (v === undefined || v === null) return;
        document.querySelectorAll(s).forEach(function (r) {
            if (r.value === v) { r.checked = true; r.dispatchEvent(new Event('change', {bubbles:true})); }
        });
    };
    var setSelectValue = function (s, v) {
        if (v === undefined || v === null) return;
        var el = $(s); if (el) { el.value = v; el.dispatchEvent(new Event('change', {bubbles:true})); }
    };
    var getInputValue  = function (s) { var e=$(s); return e?e.value:''; };
    var getRadioValue  = function (s) { var e=$(s+':checked'); return e?e.value:''; };
    var getSelectValue = function (s) { var e=$(s); return e?e.value:''; };

    var el  = function (id) { return document.getElementById(id); };
    var txt = function (id, v) { var e=el(id); if(e && v!==undefined && v!==null && v!=='') e.textContent=v; };
    var show = function (id) { var e=el(id); if(e) e.classList.remove('hidden'); };
    var hide = function (id) { var e=el(id); if(e) e.classList.add('hidden'); };
    var isUp = function (v)  { return v===1||v===true||v==='1'; };

    // =========================================================================
    // PASSWORD TOGGLES
    // =========================================================================
    var initializePasswordToggles = function () {
        document.querySelectorAll('.toggle-password').forEach(function (btn) {
            var f = btn.cloneNode(true);
            btn.parentNode.replaceChild(f, btn);
            f.addEventListener('click', function (e) {
                e.preventDefault();
                var inp  = this.closest('.relative').querySelector('input');
                var type = inp.getAttribute('type') === 'password' ? 'text' : 'password';
                inp.setAttribute('type', type);
                var ic = this.querySelector('i');
                if (ic) ic.className = type==='password' ? 'fa-solid fa-eye' : 'fa-solid fa-eye-slash';
            });
        });
    };

    // =========================================================================
    // NETWORK MODE TAB
    // =========================================================================
    var setNetworkMode = function (mode) {
        document.querySelectorAll('input[name="network-mode"]').forEach(function (r) { r.checked = r.value===mode; });
        ['ethernet-config','wifi-config','cellular-config'].forEach(function (id) {
            var e = el(id); if (e) e.style.display = 'none';
        });
        var map = {ethernet:'ethernet-config', wifi:'wifi-config', lte:'cellular-config'};
        var e = el(map[mode]||'wifi-config');
        if (e) e.style.display = 'block';
    };

    var initializeNetworkToggles = function () {
        document.querySelectorAll('input[name="network-mode"]').forEach(function (r) {
            r.addEventListener('change', function () { setNetworkMode(this.value); });
        });
        document.querySelectorAll('input[name="ip-assignment"]').forEach(function (r) {
            r.addEventListener('change', toggleIPAssignment);
        });
        var c = $('input[name="network-mode"]:checked');
        setNetworkMode(c ? c.value : 'wifi');
        toggleIPAssignment();
    };

    var toggleIPAssignment = function () {
        var ip  = $('input[name="ip-assignment"]:checked');
        var box = el('static-ip-config');
        if (!box) return;
        if (ip && ip.value === 'static') box.classList.remove('hidden');
        else                             box.classList.add('hidden');
    };

    // =========================================================================
    // LIVE CACHE  (never blanked   old values persist until overwritten)
    // =========================================================================
    var _cache = { lan: { eth0:{}, eth1:{} }, wlan:{}, lte:{} };
    var _liveConnected = false;

    var mergeInto = function (target, src) {
        if (!src || typeof src !== 'object') return;
        Object.keys(src).forEach(function (k) {
            var v = src[k];
            if (v !== null && v !== undefined && v !== '') {
                if (typeof v === 'object' && !Array.isArray(v)) {
                    if (!target[k]||typeof target[k]!=='object') target[k]={};
                    mergeInto(target[k], v);
                } else { target[k] = v; }
            }
        });
    };

    // =========================================================================
    // RENDER ETHERNET
    // Fields: eth0.ip, eth0.mac, eth0.state  /  eth1.ip, eth1.mac, eth1.state
    // =========================================================================
    var stateBadge = function (id, up) {
        var e = el(id); if (!e) return;
        e.textContent = up ? 'Connected' : 'No link';
        e.className = 'text-xs px-2 py-0.5 rounded-full font-medium ' +
            (up ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-500');
    };

    var renderEthernet = function () {
        // Panel always visible - no guard needed
        var e0 = _cache.lan.eth0 || {};
        var e1 = _cache.lan.eth1 || {};
        txt('eth0-ip',  e0.ip  || '--');
        txt('eth0-mac', e0.mac || '--');
        stateBadge('eth0-state-badge', isUp(e0.state));
        txt('eth1-ip',  e1.ip  || '--');
        txt('eth1-mac', e1.mac || '--');
        stateBadge('eth1-state-badge', isUp(e1.state));
        // Update global MAC if eth0 connected
        if (isUp(e0.state) && e0.mac) {
            var m = $('[data-mac-address]'); if (m) m.textContent = e0.mac;
        }
    };

    // =========================================================================
    // RENDER WIFI
    // Fields: state, signal_quality (dBm signed), ssid, bssid, mac, ip, frequency
    // =========================================================================
    var dbmToBars = function (dbm) {
        dbm = parseInt(dbm) || 0;
        if (dbm >= -55) return 4;
        if (dbm >= -65) return 3;
        if (dbm >= -75) return 2;
        if (dbm >= -85) return 1;
        return 0;
    };

    var updateWifiBars = function (dbm) {
        var bars    = document.querySelectorAll('#wifi-signal-bars .signal-bar');
        var classes = ['none','poor','fair','good','excellent'];
        var level   = dbmToBars(dbm);
        bars.forEach(function (b) { b.className='signal-bar none'; });
        for (var i=0; i<=level; i++) { if(bars[i]) bars[i].className='signal-bar '+classes[i]; }
    };

    var renderWifi = function () {
        // Panel always visible - no guard needed
        var w = _cache.wlan;
        stateBadge('wifi-state-badge', isUp(w.state));
        // signal_quality is dBm (signed negative number)
        if (w.signal_quality !== undefined && w.signal_quality !== null) {
            updateWifiBars(w.signal_quality);
            var e = el('wifi-signal-dbm');
            if (e) e.textContent = w.signal_quality + ' dBm';
        }
        txt('wifi-ip',   w.ip        || '--');
        txt('wifi-mac',  w.mac       || '--');
        txt('wifi-bssid',w.bssid     || '--');
        var freq = w.frequency ? w.frequency + ' MHz' : '--';
        txt('wifi-freq', freq);
        // Update SSID input if empty (don't overwrite user's edit)
        if (w.ssid && !getInputValue('[name="wifi-ssid"]')) setInputValue('[name="wifi-ssid"]', w.ssid);
        // Update global MAC
        if (isUp(w.state) && w.mac) {
            var m = $('[data-mac-address]'); if (m) m.textContent = w.mac;
        }
    };

    // =========================================================================
    // RENDER LTE
    // power=0  ? show amber alert only, hide live panel
    // power=1  ? hide alert, show live panel with all fields
    // Fields: state, power, signal_pct (0-100%), imei, operator_id, operator_name,
    //         ip, iccid, imsi, tech
    // =========================================================================
    var renderLte = function () {
        var l = _cache.lte;

        // power_state check
        if (l.power !== undefined) {
            if (!isUp(l.power)) {
                // Hardware off   show alert, hide live panel
                show('lte-power-off-alert');
                hide('lte-live-panel');
                return;
            } else {
                hide('lte-power-off-alert');
            }
        }

        show('lte-live-panel');
        stateBadge('lte-state-badge', isUp(l.state));

        // Signal percent bar
        var pct = parseInt(l.signal_pct) || 0;
        var fill = el('lte-signal-fill');
        if (fill) fill.style.width = pct + '%';
        var barColor = pct >= 70 ? 'bg-emerald-500' : pct >= 40 ? 'bg-yellow-400' : 'bg-red-400';
        if (fill) fill.className = 'h-full rounded-full transition-all ' + barColor;
        var pctEl = el('lte-signal-pct');
        if (pctEl) pctEl.textContent = pct + '%';

        txt('lte-ip',            l.ip            || '--');
        txt('lte-operator-name', l.operator_name || '--');
        txt('lte-operator-id',   l.operator_id   || '--');
        txt('lte-tech',          l.tech          || '--');
        txt('lte-imei',          l.imei          || '--');
        txt('lte-iccid',         l.iccid         || '--');
        txt('lte-imsi',          l.imsi          || '--');
    };

    // =========================================================================
    // APPLY SNAPSHOT  (called on every WS message)
    // =========================================================================
    var applySnapshot = function (data) {
        if (!data) return;
        mergeInto(_cache.lan,  data.lan  || {});
        mergeInto(_cache.wlan, data.wlan || {});
        mergeInto(_cache.lte,  data.lte  || {});

        // Do NOT auto-switch tabs - stay on whichever tab the user is on.
        // Just update the values in the background.

        // Render each interface
        renderEthernet();
        renderWifi();
        renderLte();
    };

    // =========================================================================
    // LIVE BUTTON + WEBSOCKET
    // =========================================================================
    var _netWs        = null;
    var _netActive    = false;
    var _netReconnect = null;
    var _netAttempts  = 0;   // connection attempt counter

        var setLiveBtnState = function (connected) {
        // Update indicator badge
        var btn = el('live-btn-network');
        if (btn) {
            btn.className = connected
                ? 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold text-white bg-emerald-500 transition-colors'
                : 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold text-white bg-slate-400 transition-colors';
            btn.innerHTML = connected
                ? '<i class="fa-solid fa-circle-dot fa-beat"></i> Live'
                : '<i class="fa-solid fa-tower-broadcast"></i> Live';
        }
        // Update status bar
        var bar  = el('net-ws-status');
        var icon = el('net-ws-icon');
        var txt  = el('net-ws-status-text');
        if (bar) {
            if (connected) {
                bar.className = 'mb-4 flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs';
                if (icon) icon.className = 'fa-solid fa-circle-dot fa-beat text-emerald-500';
                if (txt)  txt.textContent = 'Live   receiving network data from pipeline';
            } else {
                bar.className = 'mb-4 flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-xs';
                if (icon) icon.className = 'fa-solid fa-circle-notch fa-spin text-amber-400';
                if (txt && txt.textContent.indexOf('Connecting') === -1) txt.textContent = 'Reconnecting to live network data...';
            }
        }
    };

    var hideLivePanels = function () {
        // Panels stay visible; just hide the power-off alert
        hide('lte-power-off-alert');
    };

    var connectNetworkStatusWs = function () {
        if (_netWs && (_netWs.readyState === WebSocket.OPEN || _netWs.readyState === WebSocket.CONNECTING)) return;
        _netAttempts++;
        var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        var url      = protocol + '//' + window.location.host + '/ws/network-status';
        console.log('[NET] Connecting:', url);
        // Update status bar: first attempt = Connecting, subsequent = Reconnecting
        var bar = el('net-ws-status'); var icon = el('net-ws-icon'); var txt = el('net-ws-status-text');
        if (bar) {
            bar.className = 'mb-4 flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-100 text-slate-500 text-xs';
            if (icon) icon.className = 'fa-solid fa-circle-notch fa-spin text-slate-400';
            if (txt)  txt.textContent = _netAttempts <= 1 ? 'Connecting to live network data...' : 'Reconnecting... (attempt ' + _netAttempts + ')';
        }
        try { _netWs = new WebSocket(url); }
        catch (e) { return; }

        _netWs.onopen = function () {
            _liveConnected = true;
            _netAttempts = 0;
            setLiveBtnState(true);
            _netWs.send(JSON.stringify({type:'get_snapshot'}));
        };
        _netWs.onmessage = function (ev) {
            try {
                var msg = JSON.parse(ev.data);
                if (msg.type==='network_status_initial'||msg.type==='network_status_update') {
                    applySnapshot(msg.data);
                }
            } catch(e) { console.warn('[NET] parse error', e); }
        };
        _netWs.onerror = function (e) { /* connection error handled in onclose */ };
        _netWs.onclose = function (ev) {
            _liveConnected = false;
            setLiveBtnState(false);
            console.log('[NET] closed code='+ev.code);
            // On first failure (1006 = TCP refused), check if API is reachable
            // to distinguish nginx WS proxy issue from server down
            if (ev.code === 1006 && _netAttempts === 1) {
                fetch('/api/general-configuration', {credentials:'same-origin'})
                .then(function(r) {
                    if (r.ok) {
                        // API works but WS fails = nginx not proxying /ws/ correctly
                        var txt = el('net-ws-status-text');
                        var bar = el('net-ws-status');
                        var icon = el('net-ws-icon');
                        if (bar) bar.className = 'mb-4 flex items-center gap-2 px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs';
                        if (icon) icon.className = 'fa-solid fa-triangle-exclamation text-red-500';
                        if (txt)  txt.textContent = 'Server reachable but WebSocket failed   check nginx /ws/ proxy config (proxy_read_timeout, Connection upgrade)';
                    }
                })
                .catch(function() { /* server unreachable - normal reconnect message shown */ });
            }
            // Exponential backoff: 3s, 6s, 12s ... max 30s
            var delay = Math.min(3000 * Math.pow(2, Math.min(_netAttempts - 1, 0)), 30000);
            if (_netActive) _netReconnect = setTimeout(connectNetworkStatusWs, delay);
        };
        // keepalive
        var ping = setInterval(function () {
            if (_netWs && _netWs.readyState===WebSocket.OPEN) _netWs.send(JSON.stringify({type:'ping'}));
            else clearInterval(ping);
        }, 30000);
    };

    var disconnectNetworkStatusWs = function () {
        _netActive    = false;
        _liveConnected = false;
        _netAttempts  = 0;
        clearTimeout(_netReconnect);
        if (_netWs) { _netWs.close(1000,'user stopped'); _netWs=null; }
        setLiveBtnState(false);
        hideLivePanels();
        var txt = el('net-ws-status-text');
        if (txt) txt.textContent = 'Reconnecting...';
    };

    var initLiveButton = function () { /* auto-connect - no button click needed */ };

    // Public API
    window.networkStatusLive = {
        connect:    function () { _netActive=true; connectNetworkStatusWs(); },
        disconnect: disconnectNetworkStatusWs,
        cache:      function () { return _cache; }
    };

    // =========================================================================
    // GENERAL WS  (/ws/general    time sync only now)
    // =========================================================================
    var _wsRetryDelay = 5000;
    var _wsRetryTimer = null;
    var initializeWebSocket = function () {
        if (window.ws && (window.ws.readyState===WebSocket.OPEN||window.ws.readyState===WebSocket.CONNECTING)) return;
        clearTimeout(_wsRetryTimer);
        var protocol = window.location.protocol==='https:'?'wss:':'ws:';
        var url = protocol+'//'+window.location.host+'/ws/general';
        try { window.ws = new WebSocket(url); } catch(e) { return; }
        window.ws.onopen = function () {
            console.log('[WS/general] connected');
            _wsRetryDelay = 5000; // reset backoff
        };
        window.ws.onmessage = function (ev) {
            try {
                var d = JSON.parse(ev.data);
                if (d.type==='time_update') {
                    setInputValue('[name="date"]', d.formatted_date || formatDate(d.current_date));
                    // Always store 24h in the input; use display label for 12h preference
                    var raw24 = formatTime(d.current_time || (d.formatted_time||'').replace(/\s*(AM|PM)$/i,''));
                    setInputValue('[name="time"]', raw24);
                    updateTimeDisplayLabel(raw24);
                }
            } catch(e) {}
        };
        window.ws.onerror = function (e) { /* handled in onclose */ };
        window.ws.onclose = function () {
            _wsRetryDelay = Math.min(_wsRetryDelay * 2, 60000); // exponential backoff up to 60s
            _wsRetryTimer = setTimeout(initializeWebSocket, _wsRetryDelay);
        };
    };

    // =========================================================================
    // DATE / TIME FORMATTERS  (respects selected timezone)
    // =========================================================================
    // Returns the IANA timezone string currently selected in the UI.
    // Falls back to Asia/Kolkata so behaviour is unchanged when no selection exists.
    var getActiveTimezone = function () {
        return getSelectValue('[name="timezone"]') || 'Asia/Kolkata';
    };

    // Legacy alias kept so all existing call-sites that reference IST still work.
    // Each use re-evaluates at call-time so it picks up live UI changes.
    var IST = 'Asia/Kolkata'; // initial default  overridden below via property

    var formatDate = function (isoDate, fmt) {
        if (!isoDate) return '';
        var tz = getActiveTimezone();
        // Parse ISO date safely
        var parts = isoDate.split('-');
        if (parts.length !== 3) return isoDate;
        // Build a date at noon in the active timezone to avoid UTC-day-shift issues
        var offsetStr = tz === 'GMT' ? '+00:00' : '+05:30'; // IST default
        var d = new Date(parts[0] + '-' + parts[1] + '-' + parts[2] + 'T12:00:00' + offsetStr);
        fmt = fmt || getSelectValue('[name="date-format"]') || 'DD/MM/YYYY';
        var dd   = String(d.toLocaleDateString('en-IN', {day:'2-digit',   timeZone: tz})).padStart(2,'0');
        var mm   = String(d.toLocaleDateString('en-IN', {month:'2-digit', timeZone: tz})).padStart(2,'0');
        var yyyy = d.toLocaleDateString('en-IN', {year:'numeric', timeZone: tz});
        if (fmt === 'MM/DD/YYYY') return mm + '/' + dd + '/' + yyyy;
        if (fmt === 'YYYY-MM-DD') return yyyy + '-' + mm + '-' + dd;
        return dd + '/' + mm + '/' + yyyy; // DD/MM/YYYY default
    };

    // Always returns HH:mm (24-hour)  safe to set on <input type="time">
    var formatTime = function (hhmm) {
        if (!hhmm) return '';
        var parts = hhmm.split(':');
        var h = parseInt(parts[0]) || 0;
        var min = (parts[1] || '00').substring(0, 2);
        return String(h).padStart(2,'0') + ':' + min;
    };

    // Returns a human-readable string respecting the user's format preference
    // Use this for notifications and display labels  NOT for <input type="time">
    var formatTimeDisplay = function (hhmm, fmt) {
        if (!hhmm) return '';
        fmt = fmt || getSelectValue('[name="time-format"]') || '24-hour';
        var parts = hhmm.split(':');
        var h = parseInt(parts[0]) || 0;
        var min = (parts[1] || '00').substring(0, 2);
        if (fmt === '12-hour') {
            var ampm = h >= 12 ? 'PM' : 'AM';
            h = h % 12 || 12;
            return h + ':' + min + ' ' + ampm;
        }
        return String(h).padStart(2,'0') + ':' + min;
    };

    // Updates the optional display label next to the time input (if present)
    var updateTimeDisplayLabel = function (hhmm) {
        var fmt  = getSelectValue('[name="time-format"]') || '24-hour';
        var lbl  = document.querySelector('[data-time-display]');
        if (lbl) lbl.textContent = formatTimeDisplay(hhmm, fmt);
    };

    // Get current date+time strings in the active timezone from the browser
    var getISTNow = function () {
        var tz  = getActiveTimezone();
        var now = new Date();
        var dateStr = now.toLocaleDateString('en-CA', { timeZone: tz }); // YYYY-MM-DD
        var timeStr = now.toLocaleTimeString('en-GB', { timeZone: tz, hour: '2-digit', minute: '2-digit', hour12: false });
        return { date: dateStr, time: timeStr };
    };



    // =========================================================================
    // LIVE DATE + TIME INPUTS   tick every second, respect timezone + format
    // =========================================================================
    var _clockTimer = null;

    // Build a formatted date string from a JS Date for the active date-format
    var _buildDateStr = function (now, tz, dateFmt) {
        var d     = now.toLocaleDateString('en-GB', { timeZone: tz, day: '2-digit', month: '2-digit', year: 'numeric' });
        var parts = d.split('/'); // [DD, MM, YYYY]
        if (dateFmt === 'MM/DD/YYYY') return parts[1] + '/' + parts[0] + '/' + parts[2];
        if (dateFmt === 'YYYY-MM-DD') return parts[2] + '-' + parts[1] + '-' + parts[0];
        return d; // DD/MM/YYYY
    };

    // Build a formatted time string for the active time-format
    var _buildTimeStr = function (now, tz, timeFmt) {
        var h12 = timeFmt === '12-hour';
        return now.toLocaleTimeString('en-GB', {
            timeZone: tz, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: h12
        });
    };

    // Push current date+time into the two inputs every second
    var _tickInputs = function () {
        var now     = new Date();
        var tz      = getActiveTimezone();
        var dateFmt = getSelectValue('[name="date-format"]') || 'DD/MM/YYYY';
        var timeFmt = getSelectValue('[name="time-format"]') || '24-hour';

        var dateEl = document.querySelector('[name="date"]');
        var timeEl = document.querySelector('[name="time"]');

        // Only overwrite if the user is not actively editing that field
        if (dateEl && document.activeElement !== dateEl) {
            dateEl.value = _buildDateStr(now, tz, dateFmt);
        }
        if (timeEl && document.activeElement !== timeEl) {
            timeEl.value = _buildTimeStr(now, tz, timeFmt);
        }

        // Keep hint in sync
        var hint = document.getElementById('manual-tz-hint');
        if (hint) hint.textContent = tz === 'Asia/Kolkata' ? 'IST (UTC+05:30)' : 'GMT (UTC+00:00)';
    };

    var startLiveInputs = function () {
        _tickInputs();
        if (_clockTimer) clearInterval(_clockTimer);
        _clockTimer = setInterval(_tickInputs, 1000);
    };

    // When timezone or format dropdowns change: immediately refresh inputs
    var onTimezoneChange = function () { _tickInputs(); };
    var onTimeFormatChange = function () { _tickInputs(); };

    var initTimezoneInteraction = function () {
        var tzSel = document.getElementById('timezone-select');
        if (tzSel) tzSel.addEventListener('change', onTimezoneChange);
        var tfSel = document.querySelector('[name="time-format"]');
        if (tfSel) tfSel.addEventListener('change', onTimeFormatChange);
        var dfSel = document.querySelector('[name="date-format"]');
        if (dfSel) dfSel.addEventListener('change', _tickInputs);
        startLiveInputs();
    };

    var showNotification = function (msg, type) {
        type = type||'success';
        var c = el('gc-toast-container');
        if (!c) {
            c = document.createElement('div');
            c.id = 'gc-toast-container';
            c.className = 'fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex flex-col items-center gap-2';
            document.body.appendChild(c);
        }
        var n = document.createElement('div');
        var colors = {success:' bg-emerald-50 border-emerald-200 text-emerald-800',error:' bg-red-50 border-red-200 text-red-800',warning:' bg-yellow-50 border-yellow-200 text-yellow-800',info:' bg-blue-50 border-blue-200 text-blue-800'};
        var icons  = {success:'fa-circle-check',error:'fa-circle-exclamation',warning:'fa-triangle-exclamation',info:'fa-circle-info'};
        n.className = 'gc-toast px-4 py-3 rounded-lg shadow-lg border transition-all duration-300'+(colors[type]||colors.info);
        n.innerHTML = '<div class="flex items-center"><i class="fa-solid '+(icons[type]||'fa-circle-info')+' mr-3"></i><span class="font-medium">'+msg+'</span><button class="ml-4 text-slate-400 hover:text-slate-600" onclick="this.parentElement.parentElement.remove()"><i class="fa-solid fa-times"></i></button></div>';
        c.appendChild(n);
        setTimeout(function () {
            if (n.parentNode) { n.classList.add('hide'); setTimeout(function(){if(n.parentNode)n.remove();},300); }
        }, 5000);
    };

    // =========================================================================
    // COLLECT FORM DATA  (live cache included in payload)
    // =========================================================================
    var collectFormData = function () {
        var l   = _cache.lte  || {};
        var w   = _cache.wlan || {};
        var e0  = (_cache.lan||{}).eth0 || {};
        var e1  = (_cache.lan||{}).eth1 || {};
        return {
            gateway_identity: {
                name:            getInputValue('[name="gateway-name"]')    || 'Univa-GW-01',
                serial_number:   getInputValue('[name="serial-number"]')   || 'GW2025-1190021',
                deployment_site: getInputValue('[name="deployment-site"]') || 'Chennai Port - Zone A',
                location_mode:   getRadioValue('[name="location-mode"]')   || 'manual',
                latitude:        parseFloat(getInputValue('[name="latitude"]'))  || 12.99123,
                longitude:       parseFloat(getInputValue('[name="longitude"]')) || 80.12312,
                asset_id:        getInputValue('[name="asset-id"]')        || 'CRN-CT-12'
            },
            date_time: {
                timezone:    getActiveTimezone(),
                ntp_server:  getSelectValue('[name="ntp-server"]')  || 'time.google.com',
                date_format: getSelectValue('[name="date-format"]') || 'DD/MM/YYYY',
                time_format: getSelectValue('[name="time-format"]') || '24-hour'
            },
            network: {
                mode: getRadioValue('[name="network-mode"]') || 'wifi',
                wifi: {
                    ssid:     getInputValue('[name="wifi-ssid"]'),
                    password: getInputValue('[name="wifi-password"]'),
                    // live snapshot
                    live_state:          w.state,
                    live_signal_quality: w.signal_quality,
                    live_ip:             w.ip    || '',
                    live_mac:            w.mac   || '',
                    live_bssid:          w.bssid || '',
                    live_frequency:      w.frequency || 0
                },
                ethernet: {
                    ip_assignment: getRadioValue('[name="ip-assignment"]') || 'dhcp',
                    static_ip:     getInputValue('[name="static-ip"]'),
                    subnet_mask:   getInputValue('[name="subnet-mask"]'),
                    gateway:       getInputValue('[name="gateway"]'),
                    dns1:          getInputValue('[name="dns1"]'),
                    dns2:          getInputValue('[name="dns2"]'),
                    // live snapshot
                    live_eth0_ip:    e0.ip    || '',
                    live_eth0_mac:   e0.mac   || '',
                    live_eth0_state: e0.state,
                    live_eth1_ip:    e1.ip    || '',
                    live_eth1_mac:   e1.mac   || '',
                    live_eth1_state: e1.state
                },
                cellular: {
                    apn:      getInputValue('[name="apn"]')             || 'internet',
                    username: getInputValue('[name="cellular-username"]'),
                    password: getInputValue('[name="cellular-password"]'),
                    // live snapshot
                    live_state:         l.state,
                    live_power:         l.power,
                    live_signal_pct:    l.signal_pct,
                    live_imei:          l.imei          || '',
                    live_operator_id:   l.operator_id   || '',
                    live_operator_name: l.operator_name || '',
                    live_ip:            l.ip            || '',
                    live_iccid:         l.iccid         || '',
                    live_imsi:          l.imsi          || '',
                    live_tech:          l.tech          || ''
                }
            },
            heartbeat: {
                interval:          parseInt(getInputValue('[name="heartbeat-interval"]')) || 30,
                offline_threshold: parseInt(getInputValue('[name="offline-threshold"]'))  || 120
            },
            mac_address: (function () { var m=$('[data-mac-address]'); return m?m.textContent.trim():''; }())
        };
    };

    // =========================================================================
    // SAVE
    // =========================================================================
    var handleSaveConfiguration = function () {
        var btn = el('save-btn'); if (!btn) return;
        var orig = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Saving…';
        btn.disabled  = true;
        btn.classList.remove('bg-primary','hover:bg-primaryHover');
        btn.classList.add('bg-gray-500','cursor-wait');

        fetch('/api/general-configuration', {
            method:'PUT', credentials:'same-origin',
            headers:{'Content-Type':'application/json','Accept':'application/json'},
            body: JSON.stringify(collectFormData())
        })
        .then(function (r) { if(!r.ok) return r.json().then(function(e){throw new Error(e.message||'HTTP '+r.status);}); return r.json(); })
        .then(function (result) {
            btn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Save Success';
            btn.classList.remove('bg-gray-500','cursor-wait');
            btn.classList.add('bg-emerald-600','hover:bg-emerald-700');
            showNotification(result.message||'Configuration saved successfully!', 'success');
            window.dispatchEvent(new Event('gateway-config-saved'));
            setTimeout(function () { btn.innerHTML=orig; btn.classList.remove('bg-emerald-600','hover:bg-emerald-700'); btn.classList.add('bg-primary','hover:bg-primaryHover'); btn.disabled=false; }, 2500);
        })
        .catch(function (err) {
            btn.innerHTML = '<i class="fa-solid fa-exclamation-triangle mr-2"></i> Failed!';
            btn.classList.remove('bg-gray-500','cursor-wait');
            btn.classList.add('bg-red-600','hover:bg-red-700');
            showNotification('Save failed: '+err.message, 'error');
            setTimeout(function () { btn.innerHTML=orig; btn.classList.remove('bg-red-600','hover:bg-red-700'); btn.classList.add('bg-primary','hover:bg-primaryHover'); btn.disabled=false; }, 3000);
        });
    };

    // =========================================================================
    // LOAD CONFIGURATION
    // =========================================================================
    var loadConfiguration = function () {
        return new Promise(function (resolve, reject) {
            fetch('/api/general-configuration', {credentials:'same-origin'})
            .then(function (r) { if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); })
            .then(function (cfg) {
                populateFormWithConfig(cfg);
                // Only set date/time from _realtime if server provides it,
                // otherwise leave as-is (WS time_update will keep it current)
                if (cfg._realtime) {
                    if (cfg._realtime.current_date) setInputValue('[name="date"]', formatDate(cfg._realtime.current_date));
                    if (cfg._realtime.current_time) {
                        var raw24 = formatTime(cfg._realtime.current_time);
                        setInputValue('[name="time"]', raw24);
                        updateTimeDisplayLabel(raw24);
                    }
                }
                resolve(cfg);
            }).catch(reject);
        });
    };

    var populateFormWithConfig = function (cfg) {
        if (cfg.gateway_identity) {
            var id = cfg.gateway_identity;
            setInputValue('[name="gateway-name"]',    id.name);
            setInputValue('[name="serial-number"]',   id.serial_number);
            setInputValue('[name="deployment-site"]', id.deployment_site);
            setRadioValue('[name="location-mode"]',   id.location_mode);
            setInputValue('[name="latitude"]',        id.latitude);
            setInputValue('[name="longitude"]',       id.longitude);
            setInputValue('[name="asset-id"]',        id.asset_id);
        }
        if (cfg.date_time) {
            setSelectValue('[name="timezone"]',    cfg.date_time.timezone);
            setSelectValue('[name="ntp-server"]',  cfg.date_time.ntp_server);
            setSelectValue('[name="date-format"]', cfg.date_time.date_format);
            setSelectValue('[name="time-format"]', cfg.date_time.time_format);
        }
        if (cfg.network) {
            var n=cfg.network, w=n.wifi||{}, e=n.ethernet||{}, c=n.cellular||{};
            setInputValue('[name="wifi-ssid"]',         w.ssid     ||'');
            setInputValue('[name="wifi-password"]',     w.password ||'');
            setRadioValue('[name="ip-assignment"]',     e.ip_assignment||'dhcp');
            setInputValue('[name="static-ip"]',         e.static_ip||'');
            setInputValue('[name="subnet-mask"]',       e.subnet_mask||'');
            setInputValue('[name="gateway"]',           e.gateway||'');
            setInputValue('[name="dns1"]',              e.dns1||'');
            setInputValue('[name="dns2"]',              e.dns2||'');
            setInputValue('[name="apn"]',               c.apn||'internet');
            setInputValue('[name="cellular-username"]', c.username||'');
            setInputValue('[name="cellular-password"]', c.password||'');
            setNetworkMode(n.mode||'wifi');
        }
        if (cfg.heartbeat) {
            setInputValue('[name="heartbeat-interval"]', cfg.heartbeat.interval);
            setInputValue('[name="offline-threshold"]',  cfg.heartbeat.offline_threshold);
        }
        if (cfg.mac_address) { var m=$('[data-mac-address]'); if(m) m.textContent=cfg.mac_address; }
    };

    // =========================================================================
    // BUTTONS
    // =========================================================================
    var initializeButtons = function () {
        var refreshBtn = el('refresh-btn');
        if (refreshBtn) {
            var nb = refreshBtn.cloneNode(true);
            refreshBtn.parentNode.replaceChild(nb, refreshBtn);
            nb.addEventListener('click', function () { if(confirm('Refresh? Unsaved changes will be lost.')) location.reload(); });
        }
        var saveBtn = el('save-btn');
        if (saveBtn) {
            var ns = saveBtn.cloneNode(true);
            saveBtn.parentNode.replaceChild(ns, saveBtn);
            ns.addEventListener('click', handleSaveConfiguration);
        }
        var syncBtn = $('.sync-time-btn');
        if (syncBtn) {
            var nsy = syncBtn.cloneNode(true);
            syncBtn.parentNode.replaceChild(nsy, syncBtn);
            nsy.addEventListener('click', function () {
                var orig=this.innerHTML; this.innerHTML='<i class="fa-solid fa-spinner fa-spin mr-2"></i>'; this.disabled=true;
                var payload = {
                    timezone:    getActiveTimezone(),
                    ntp_server:  getSelectValue('[name="ntp-server"]')  || 'time.google.com',
                    date_format: getSelectValue('[name="date-format"]') || 'DD/MM/YYYY',
                    time_format: getSelectValue('[name="time-format"]') || '24-hour'
                };
                fetch('/api/sync-time', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                })
                .then(function(r){ return r.json(); })
                .then(function(data){
                    var fmt     = getSelectValue('[name="date-format"]') || 'DD/MM/YYYY';
                    var tfmt    = getSelectValue('[name="time-format"]') || '24-hour';
                    var displayDate = data.formatted_date || formatDate(data.current_date, fmt);
                    // Always store 24h in input; format for display/notification separately
                    var raw24   = formatTime(data.current_time || '');
                    var displayTime = formatTimeDisplay(raw24, tfmt);
                    setInputValue('[name="date"]', displayDate);
                    setInputValue('[name="time"]', raw24);
                    updateTimeDisplayLabel(raw24);
                    showNotification('Time synchronized  ' + displayDate + ' ' + displayTime + ' (' + getActiveTimezone() + ')', 'success');
                })
                .catch(function(){
                    // Server unreachable  use browser IST time directly
                    var ist     = getISTNow();
                    var fmt     = getSelectValue('[name="date-format"]') || 'DD/MM/YYYY';
                    var tfmt    = getSelectValue('[name="time-format"]') || '24-hour';
                    var displayDate = formatDate(ist.date, fmt);
                    var raw24   = formatTime(ist.time);
                    var displayTime = formatTimeDisplay(raw24, tfmt);
                    setInputValue('[name="date"]', displayDate);
                    setInputValue('[name="time"]', raw24);
                    updateTimeDisplayLabel(raw24);
                    showNotification('Time set from browser  ' + displayDate + ' ' + displayTime + ' (' + getActiveTimezone() + ')', 'warning');
                })
                .then(function(){ nsy.innerHTML=orig; nsy.disabled=false; });
            });
        }


    };
    // =========================================================================
    // INIT
    // =========================================================================
    var cleanup = function () { window._generalConfigInitializing = false; window._generalConfigInitialized = false; };

    window.initGeneralConfig = function () {
        // Strong double-init guard - set both flags immediately
        if (window._generalConfigInitialized || window._generalConfigInitializing) return;
        window._generalConfigInitialized  = true;
        window._generalConfigInitializing = true;
        cleanup();
        initializeButtons();
        initializeNetworkToggles();
        initializePasswordToggles();
        initLiveButton();
        initializeWebSocket();
        initTimezoneInteraction();
        // Auto-connect network status WebSocket on page open
        _netActive = true;
        connectNetworkStatusWs();
        loadConfiguration()
        .then(function () { window._generalConfigInitializing=false; })
        .catch(function (err) { console.error('Load error:',err); showNotification('Failed to load config','warning'); window._generalConfigInitializing=false; });
    };

    window.cleanupGeneralConfig = cleanup;
    window.showNotification     = showNotification;

    // Router handles initialization - no auto-trigger needed
})();