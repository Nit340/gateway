// general-config.js


(function () {
    if (window._generalConfigInitialized || window._generalConfigInitializing) return;

    // =========================================================================
    // HELPERS
    // =========================================================================
    var $ = function (s) { return document.querySelector(s); };

    var setInputValue = function (s, v) {
        if (v === undefined || v === null) return;
        var el = $(s); if (el) { el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); }
    };
    var setRadioValue = function (s, v) {
        if (v === undefined || v === null) return;
        document.querySelectorAll(s).forEach(function (r) {
            if (r.value === v) { r.checked = true; r.dispatchEvent(new Event('change', { bubbles: true })); }
        });
    };
    var setSelectValue = function (s, v) {
        if (v === undefined || v === null) return;
        var el = $(s); if (el) { el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); }
    };
    var getInputValue = function (s) { var e = $(s); return e ? e.value : ''; };
    var getRadioValue = function (s) { var e = $(s + ':checked'); return e ? e.value : ''; };
    var getSelectValue = function (s) { var e = $(s); return e ? e.value : ''; };

    var el = function (id) { return document.getElementById(id); };
    var txt = function (id, v) { var e = el(id); if (e && v !== undefined && v !== null && v !== '') e.textContent = v; };
    var show = function (id) { var e = el(id); if (e) e.classList.remove('hidden'); };
    var hide = function (id) { var e = el(id); if (e) e.classList.add('hidden'); };
    var isUp = function (v) { return v === 1 || v === true || v === '1'; };

    // =========================================================================
    // FIELD TIMESTAMP TRACKING FOR STALE DATA DETECTION
    // =========================================================================
    var _fieldTimestamps = {};
    var _FIELD_TIMEOUT = 30000;

    var updateFieldTimestamp = function (datapoint) {
        _fieldTimestamps[datapoint] = Date.now();
    };

    var isFieldStale = function (datapoint) {
        var ts = _fieldTimestamps[datapoint];
        if (!ts) return true;
        var timeout = _FIELD_TIMEOUT;
        if (datapoint.includes('.mac') || datapoint.includes('.imei') || datapoint.includes('.iccid') || datapoint.includes('.imsi')) {
            timeout = 3600000;
        }
        return (Date.now() - ts) > timeout;
    };

    var markAllFieldsStale = function () {
        var newTimestamps = {};
        for (var dp in _fieldTimestamps) {
            if (dp.includes('.mac') || dp.includes('.imei') || dp.includes('.iccid') || dp.includes('.imsi') || dp.includes('serial_number')) {
                newTimestamps[dp] = _fieldTimestamps[dp];
            }
        }
        _fieldTimestamps = newTimestamps;
    };

    // =========================================================================
    // PASSWORD TOGGLES
    // =========================================================================
    var initializePasswordToggles = function () {
        document.querySelectorAll('.toggle-password').forEach(function (btn) {
            var f = btn.cloneNode(true);
            btn.parentNode.replaceChild(f, btn);
            f.addEventListener('click', function (e) {
                e.preventDefault();
                var inp = this.closest('.relative').querySelector('input');
                var type = inp.getAttribute('type') === 'password' ? 'text' : 'password';
                inp.setAttribute('type', type);
                var ic = this.querySelector('i');
                if (ic) ic.className = type === 'password' ? 'fa-solid fa-eye' : 'fa-solid fa-eye-slash';
            });
        });
    };

    // =========================================================================
    // UPDATE GLOBAL MAC DISPLAY
    // =========================================================================
    var updateGlobalMacDisplay = function () {
        var mode = getRadioValue('[name="network-mode"]') || 'wifi';

        var ethRow = el('global-mac-eth-row');
        var wifiRow = el('global-mac-wifi-row');
        var lteRow = el('global-mac-lte-row');

        if (ethRow) ethRow.style.display = 'none';
        if (wifiRow) wifiRow.style.display = 'none';
        if (lteRow) lteRow.style.display = 'none';

        if (mode === 'ethernet') {
            if (ethRow) {
                ethRow.style.display = '';
                var e0 = _cache.lan.eth0 || {};
                var e1 = _cache.lan.eth1 || {};
                var macValue = '--';
                if (_selectedEth === 'eth0' && e0.mac && !isFieldStale('net.lan.eth0.mac')) {
                    macValue = e0.mac.toUpperCase();
                } else if (_selectedEth === 'eth1' && e1.mac && !isFieldStale('net.lan.eth1.mac')) {
                    macValue = e1.mac.toUpperCase();
                } else if (!_selectedEth && isUp(e0.state)) {
                    macValue = e0.mac ? e0.mac.toUpperCase() : '--';
                } else if (!_selectedEth && isUp(e1.state)) {
                    macValue = e1.mac ? e1.mac.toUpperCase() : '--';
                }
                if (el('global-mac-eth')) {
                    el('global-mac-eth').textContent = macValue;
                }
            }
        } else if (mode === 'wifi') {
            if (wifiRow) {
                wifiRow.style.display = '';
                var w = _cache.wlan;
                var wifiMac = (w.mac && !isFieldStale('net.wlan.mac')) ? w.mac.toUpperCase() : '--';
                if (el('global-mac-wifi')) {
                    el('global-mac-wifi').textContent = wifiMac;
                }
            }
        } else if (mode === 'lte') {
            if (lteRow) {
                lteRow.style.display = '';
                var l = _cache.lte;
                var lteMac = (!isFieldStale('net.lte.imei') && l.imei) ? l.imei : '--';
                if (el('global-mac-lte')) {
                    el('global-mac-lte').textContent = lteMac;
                }
            }
        }
    };

    // =========================================================================
    // NETWORK MODE TAB
    // =========================================================================
    var setNetworkMode = function (mode) {
        document.querySelectorAll('input[name="network-mode"]').forEach(function (r) { r.checked = r.value === mode; });
        ['ethernet-config', 'wifi-config', 'cellular-config'].forEach(function (id) {
            var e = el(id); if (e) e.style.display = 'none';
        });
        var map = { ethernet: 'ethernet-config', wifi: 'wifi-config', lte: 'cellular-config' };
        var e = el(map[mode] || 'wifi-config');
        if (e) e.style.display = 'block';
        document.querySelectorAll('.net-mode-tab').forEach(function (tab) {
            if (tab.dataset.mode === mode) tab.classList.add('active');
            else tab.classList.remove('active');
        });
        updateGlobalMacDisplay();
    };

    var _syncNetworkTabs = function (activeMode) {
        document.querySelectorAll('.net-mode-tab').forEach(function (tab) {
            var mode = tab.dataset.mode;
            tab.classList.remove('active');
            if (mode === activeMode) {
                tab.classList.add('active');
            }
        });
    };

    // =========================================================================
    // UPDATE TAB CONNECTED STATE
    // =========================================================================
    var _updateTabConnectedState = function (mode, connected) {
        var tab = document.getElementById('net-tab-' + mode);
        var btn = document.getElementById(mode + '-connect-btn');
        var lbl = document.getElementById(mode + '-connect-label');

        if (_acEnabled) {
            if (tab) {
                if (connected) tab.classList.add('connected');
                else tab.classList.remove('connected');
            }
            if (btn) {
                if (connected) {
                    btn.classList.add('is-connected');
                    if (lbl) lbl.textContent = 'Connected';
                } else {
                    btn.classList.remove('is-connected');
                    if (lbl) lbl.textContent = 'Connect';
                }
            }
            if (mode === 'ethernet') {
                var e0 = _cache.lan.eth0 || {};
                var e1 = _cache.lan.eth1 || {};
                var e0Up = isUp(e0.state);
                var e1Up = isUp(e1.state);
                
                ['eth0', 'eth1'].forEach(function (iface) {
                    var card = document.getElementById(iface + '-card');
                    if (!card) return;
                    var portUp = (iface === 'eth0') ? e0Up : e1Up;
                    var radio = document.getElementById(iface + '-radio');
                    var icon = document.getElementById(iface + '-radio-icon');
                    
                    if (portUp) {
                        card.style.borderColor = '#10b981';
                        card.style.background = '#f0fdf4';
                        if (radio) radio.className = 'w-5 h-5 rounded-full border-2 border-emerald-500 bg-emerald-500 flex items-center justify-center transition-colors';
                        if (icon) icon.classList.remove('opacity-0');
                    } else {
                        card.style.borderColor = '';
                        card.style.background = '';
                        if (radio) radio.className = 'w-5 h-5 rounded-full border-2 border-slate-300 flex items-center justify-center transition-colors';
                        if (icon) icon.classList.add('opacity-0');
                    }
                });
            }
        } else {
            // Auto OFF: tab always reflects live connection state (green = physically connected).
            // The Connect button label additionally requires the user to have clicked Connect
            // this session, so it doesn't say "Connected" on a link the user didn't choose.
            var clickKey = (mode === 'ethernet') ? ('ethernet-' + (_selectedEth || 'eth0')) : mode;
            var userClicked = !!_manualConnectClicked[clickKey];

            // Clear the clicked flag if the link went down
            if (userClicked && !connected) {
                _manualConnectClicked[clickKey] = false;
                userClicked = false;
            }

            // Tab: green whenever the interface is physically up, regardless of who initiated it
            if (tab) {
                if (connected) tab.classList.add('connected');
                else tab.classList.remove('connected');
            }

            // Button: green + "Connected" label only after explicit Connect click
            if (btn) {
                if (userClicked && connected) {
                    btn.classList.add('is-connected');
                    if (lbl) lbl.textContent = 'Connected';
                } else {
                    btn.classList.remove('is-connected');
                    if (lbl) lbl.textContent = 'Connect';
                }
            }

            // Ethernet port cards: also colour by live link state when auto is OFF
            if (mode === 'ethernet') {
                var e0 = _cache.lan.eth0 || {};
                var e1 = _cache.lan.eth1 || {};
                var e0Up = isUp(e0.state);
                var e1Up = isUp(e1.state);
                ['eth0', 'eth1'].forEach(function (iface) {
                    var card = document.getElementById(iface + '-card');
                    if (!card) return;
                    var portUp = (iface === 'eth0') ? e0Up : e1Up;
                    var radio = document.getElementById(iface + '-radio');
                    var icon  = document.getElementById(iface + '-radio-icon');
                    if (portUp) {
                        card.style.borderColor = '#10b981';
                        card.style.background  = '#f0fdf4';
                        if (radio) radio.className = 'w-5 h-5 rounded-full border-2 border-emerald-500 bg-emerald-500 flex items-center justify-center transition-colors';
                        if (icon)  icon.classList.remove('opacity-0');
                    } else {
                        card.style.borderColor = '';
                        card.style.background  = '';
                        if (radio) radio.className = 'w-5 h-5 rounded-full border-2 border-slate-300 flex items-center justify-center transition-colors';
                        if (icon)  icon.classList.add('opacity-0');
                    }
                });
            }
        }
    };

    // =========================================================================
    // CONNECT BUTTONS
    // =========================================================================
    var _ROUTE_MAP = { ethernet: 1, wifi: 4, lte: 3 };
    var _manualConnectClicked = {};

    var _sendNetworkRoute = function (mode) {
        var routeNum;
        if (mode === 'ethernet') {
            routeNum = (_selectedEth === 'eth1') ? 2 : 1;
        } else {
            routeNum = _ROUTE_MAP[mode] !== undefined ? _ROUTE_MAP[mode] : 4;
        }

        // 1. Persist the route to the database so it survives a restart
        fetch('/api/general-configuration', {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ network: { last_route_select: routeNum } })
        }).catch(function (e) {
            console.warn('[CONNECT] failed to persist route:', e);
        });

        // 2. Send the route to the pipeline
        return fetch('/api/pipeline', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ datapoint: 'net.route', value: routeNum })
}).then(function (r) { return r.json(); })
          .catch(function (e) { console.warn('[CONNECT] failed to send network route:', e); });
    };

    var _initConnectButtons = function () {
        ['ethernet', 'wifi', 'lte'].forEach(function (mode) {
            var btn = document.getElementById(mode + '-connect-btn');
            if (!btn || btn.dataset.connectBound) return;
            btn.dataset.connectBound = '1';
            
            var newBtn = btn.cloneNode(true);
            btn.parentNode.replaceChild(newBtn, btn);
            
            newBtn.addEventListener('click', function () {
                if (_acEnabled) {
                    _sendNetworkRoute(mode);
                    showNotification('Connecting via ' + mode.toUpperCase() + '… (Auto mode active)', 'info');
                    return;
                }
                
                if (mode === 'ethernet') {
                    var thisPort = _selectedEth || 'eth0';
                    var otherPort = (thisPort === 'eth0') ? 'eth1' : 'eth0';
                    _manualConnectClicked['ethernet-' + otherPort] = false;
                    _manualConnectClicked['ethernet-' + thisPort] = true;
                } else {
                    _manualConnectClicked[mode] = true;
                }
                
                _sendNetworkRoute(mode);
                showNotification('Connecting via ' + mode.toUpperCase() + '…', 'info');
                
                var lbl = document.getElementById(mode + '-connect-label');
                if (lbl) lbl.textContent = 'Connecting…';
            });
        });
    };

    // =========================================================================
    // AUTO HIGHLIGHT
    // =========================================================================
    var _autoHighlightedMode = null;
    var _autoHighlightedEth = null;

    // BUGFIX: Prevent _autoHighlight from switching the visible panel before
    // loadConfiguration has applied the saved mode (prevents snap-to-wifi on refresh).
    var _configLoaded = false;

    var _autoHighlight = function () {
        var mode = getRadioValue('[name="network-mode"]') || 'wifi';
        if (mode !== 'auto') return;
        if (!_configLoaded) return; // don't hijack the tab before config is applied

        var e0State = (!isFieldStale('net.lan.eth0.state')) ? _cache.lan.eth0.state : null;
        var e1State = (!isFieldStale('net.lan.eth1.state')) ? _cache.lan.eth1.state : null;
        var wState = (!isFieldStale('net.wlan.state')) ? _cache.wlan.state : null;
        var lState = (!isFieldStale('net.lte.state')) ? _cache.lte.state : null;

        var e0Up = isUp(e0State);
        var e1Up = isUp(e1State);
        var wUp  = isUp(wState);
        var lUp  = isUp(lState);

        var activeMode = null;
        var activeEth = null;

        if (e0Up) {
            activeMode = 'ethernet'; activeEth = 'eth0';
        } else if (e1Up) {
            activeMode = 'ethernet'; activeEth = 'eth1';
        } else if (wUp) {
            activeMode = 'wifi';
        } else if (lUp) {
            activeMode = 'lte';
        }

        var ethTab  = document.getElementById('net-tab-ethernet');
        var wifiTab = document.getElementById('net-tab-wifi');
        var lteTab  = document.getElementById('net-tab-lte');

        if (ethTab)  { if (e0Up || e1Up) ethTab.classList.add('connected');  else ethTab.classList.remove('connected'); }
        if (wifiTab) { if (wUp)  wifiTab.classList.add('connected'); else wifiTab.classList.remove('connected'); }
        if (lteTab)  { if (lUp)  lteTab.classList.add('connected');  else lteTab.classList.remove('connected'); }

        if (activeMode === _autoHighlightedMode && activeEth === _autoHighlightedEth) return;
        _autoHighlightedMode = activeMode;
        _autoHighlightedEth = activeEth;

        ['ethernet-config', 'wifi-config', 'cellular-config'].forEach(function (id) {
            var e = el(id); if (e) e.style.display = 'none';
        });
        var panelMap = { ethernet: 'ethernet-config', wifi: 'wifi-config', lte: 'cellular-config' };
        if (activeMode && panelMap[activeMode]) {
            var p = el(panelMap[activeMode]); if (p) p.style.display = 'block';
        }

        if (activeMode === 'ethernet') {
            _setEthCardSelected(activeEth);
        } else {
            _setEthCardSelected(null);
        }

        updateGlobalMacDisplay();
    };

    // =========================================================================
    // RENDER ETHERNET
    // =========================================================================
    var stateBadge = function (id, up) {
        var e = el(id); if (!e) return;
        e.textContent = up ? 'Connected' : 'No link';
        e.className = 'text-xs px-2 py-0.5 rounded-full font-medium ' +
            (up ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-500');
    };

    var renderEthernet = function () {
        var e0 = _cache.lan.eth0 || {};
        var e1 = _cache.lan.eth1 || {};

        txt('eth0-ip', (e0.ip && !isFieldStale('net.lan.eth0.ip')) ? e0.ip : '--');
        txt('eth0-mac', (e0.mac && !isFieldStale('net.lan.eth0.mac')) ? e0.mac : '--');

        var eth0State = e0.state;
        if (isFieldStale('net.lan.eth0.state')) eth0State = null;
        stateBadge('eth0-state-badge', isUp(eth0State));

        txt('eth1-ip', (e1.ip && !isFieldStale('net.lan.eth1.ip')) ? e1.ip : '--');
        txt('eth1-mac', (e1.mac && !isFieldStale('net.lan.eth1.mac')) ? e1.mac : '--');

        var eth1State = e1.state;
        if (isFieldStale('net.lan.eth1.state')) eth1State = null;
        stateBadge('eth1-state-badge', isUp(eth1State));

        updateGlobalMacDisplay();
        _autoHighlight();
        
        var e0Up = isUp(eth0State);
        var e1Up = isUp(eth1State);
        
        if (_acEnabled) {
            _updateTabConnectedState('ethernet', e0Up || e1Up);
        } else {
            var selPort = _selectedEth || 'eth0';
            var selPortUp = (selPort === 'eth0') ? e0Up : e1Up;
            _updateTabConnectedState('ethernet', selPortUp);
        }
    };

    // =========================================================================
    // WIFI RENDER
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
        var bars = document.querySelectorAll('#wifi-signal-bars .signal-bar');
        var classes = ['none', 'poor', 'fair', 'good', 'excellent'];
        var level = dbmToBars(dbm);
        bars.forEach(function (b) { b.className = 'signal-bar none'; });
        for (var i = 0; i <= level; i++) { if (bars[i]) bars[i].className = 'signal-bar ' + classes[i]; }
    };

    var renderWifi = function () {
        var w = _cache.wlan;

        var state = w.state;
        if (isFieldStale('net.wlan.state')) state = null;
        var wifiUp = isUp(state);
        stateBadge('wifi-state-badge', wifiUp);

        var panel = el('wifi-live-panel');
        if (panel) {
            panel.style.background = wifiUp ? '#f0fdf4' : '';
            panel.style.borderColor = wifiUp ? '#86efac' : '';
        }

        var liveSsid = el('wifi-live-ssid');
        if (liveSsid) {
            var ssidVal = (w.ssid && !isFieldStale('net.wlan.ssid')) ? w.ssid : '';
            liveSsid.textContent = ssidVal ? 'SSID : ' + ssidVal : '';
            liveSsid.style.color = wifiUp ? '#15803d' : '';
        }

        var wifiSignal = (w.signal_quality !== undefined && w.signal_quality !== null) ? w.signal_quality : w.signal;
        var signalStale = isFieldStale('net.wlan.signal') && isFieldStale('net.wlan.signal_quality');
        if (wifiSignal !== undefined && wifiSignal !== null && !signalStale) {
            updateWifiBars(wifiSignal);
            var e = el('wifi-signal-dbm');
            if (e) e.textContent = wifiSignal + ' dBm';
        } else {
            var e = el('wifi-signal-dbm');
            if (e) e.textContent = '--';
        }

        txt('wifi-ip', (w.ip && !isFieldStale('net.wlan.ip')) ? w.ip : '--');
        txt('wifi-mac', (w.mac && !isFieldStale('net.wlan.mac')) ? w.mac : '--');
        txt('wifi-bssid', (w.bssid && !isFieldStale('net.wlan.bssid')) ? w.bssid : '--');

        var freq = (w.frequency && !isFieldStale('net.wlan.frequency')) ? w.frequency + ' MHz' : '--';
        txt('wifi-freq', freq);

        if (w.ssid && !isFieldStale('net.wlan.ssid')) {
            var hid = el('wifi-ssid-value');
            var lbl = el('wifi-ssid-label');
            if (hid && (!hid.value || hid.value === 'Univa-Guest')) {
                hid.value = w.ssid;
                if (lbl) lbl.textContent = w.ssid;
            }
        }

        updateGlobalMacDisplay();
        _autoHighlight();
        _updateTabConnectedState('wifi', wifiUp);
    };

    // =========================================================================
    // WIFI SCAN AND CONNECT
    // =========================================================================
    var _wifiNetworks = [];
    var _wifiPanel = null;

    var _dbmLevel = function (dbm) {
        dbm = parseInt(dbm) || -100;
        if (dbm >= -55) return 4;
        if (dbm >= -65) return 3;
        if (dbm >= -75) return 2;
        if (dbm >= -85) return 1;
        return 0;
    };

    var _wifiArcIcon = function (dbm) {
        var lvl = _dbmLevel(dbm);
        var color = lvl >= 3 ? '#2563eb' : lvl === 2 ? '#f59e0b' : '#ef4444';
        var dim = '#e2e8f0';
        var arcs = '';
        var sizes = [[4, 4], [8, 8], [12, 12], [16, 16]];
        for (var i = 0; i < 4; i++) {
            var w = sizes[i][0], h = sizes[i][1];
            var c = (i < lvl) ? color : dim;
            arcs += '<span style="position:absolute;bottom:0;left:50%;transform:translateX(-50%);' +
                'width:' + w + 'px;height:' + h + 'px;border-radius:50%;' +
                'border:2px solid ' + c + ';"></span>';
        }
        return '<span style="position:relative;display:inline-block;width:18px;height:16px;flex-shrink:0;">' + arcs + '</span>';
    };

    var _createPanel = function () {
        if (_wifiPanel) return _wifiPanel;
        var p = document.createElement('div');
        p.id = 'wifi-dropdown-panel';
        p.style.cssText =
            'display:none;position:fixed;z-index:99999;background:#fff;' +
            'border:1px solid #e2e8f0;border-radius:12px;' +
            'box-shadow:0 8px 30px rgba(0,0,0,0.15);' +
            'min-width:260px;max-height:320px;overflow-y:auto;' +
            'font-family:inherit;font-size:14px;';
        document.body.appendChild(p);
        _wifiPanel = p;
        return p;
    };

    var _positionPanel = function () {
        var btn = el('wifi-scan-btn');
        if (!btn || !_wifiPanel) return;
        var r = btn.getBoundingClientRect();
        _wifiPanel.style.left = r.left + 'px';
        _wifiPanel.style.width = Math.max(r.right - r.left + 200, 260) + 'px';
        if (window.innerHeight - r.bottom > 200) {
            _wifiPanel.style.top = (r.bottom + 6) + 'px';
            _wifiPanel.style.bottom = 'auto';
        } else {
            _wifiPanel.style.top = 'auto';
            _wifiPanel.style.bottom = (window.innerHeight - r.top + 6) + 'px';
        }
    };

    var _closePanel = function () {
        if (_wifiPanel) _wifiPanel.style.display = 'none';
    };

    var _renderPanel = function (networks) {
        var p = _createPanel();
        if (!networks || !networks.length) {
            p.innerHTML =
                '<div style="padding:20px;text-align:center;color:#94a3b8;">' +
                '<i class="fa-solid fa-wifi" style="font-size:24px;color:#cbd5e1;display:block;margin-bottom:8px;"></i>' +
                'No networks found</div>';
            return;
        }
        p.innerHTML = networks.map(function (n) {
            var ssid = n.ssid || '';
            var dbm = n.signal_quality || -100;
            var sec = n.security || 'Open';
            var ch = n.channel ? 'ch ' + n.channel : '';
            var lock = (sec && sec.toLowerCase() !== 'open')
                ? '<i class="fa-solid fa-lock" style="color:#94a3b8;font-size:11px;"></i>' : '';
            return '<div class="wifi-row" data-ssid="' + ssid.replace(/"/g, '&quot;') + '" ' +
                'style="display:flex;align-items:center;gap:12px;padding:11px 14px;' +
                'cursor:pointer;border-bottom:1px solid #f1f5f9;">' +
                _wifiArcIcon(dbm) +
                '<span style="flex:1;min-width:0;">' +
                '<span style="display:block;font-size:13px;font-weight:500;color:#1e293b;' +
                'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + ssid + '</span>' +
                '<span style="font-size:11px;color:#94a3b8;">' + sec + (ch ? ' · ' + ch : '') + '</span>' +
                '</span>' + lock +
                '</div>';
        }).join('');

        p.querySelectorAll('.wifi-row').forEach(function (row) {
            row.addEventListener('mouseenter', function () { this.style.background = '#f0f9ff'; });
            row.addEventListener('mouseleave', function () { this.style.background = ''; });
            row.addEventListener('click', function () {
                var ssid = this.dataset.ssid;
                var lbl = el('wifi-ssid-label');
                if (lbl) lbl.textContent = ssid;
                var hid = el('wifi-ssid-value');
                if (hid) hid.value = ssid;
                var hint = el('wifi-ssid-hint');
                if (hint) hint.textContent = 'Selected: ' + ssid;
                _closePanel();
            });
        });
    };

    var _doScanWifi = function () {
        var btn = el('wifi-scan-btn');
        var icon = el('wifi-scan-icon');
        var hint = el('wifi-ssid-hint');

        if (btn) btn.disabled = true;
        if (icon) icon.className = 'fa-solid fa-rotate fa-spin text-sm';
        if (hint) hint.textContent = 'Searching for networks...';

        var p = _createPanel();
        p.innerHTML =
            '<div style="padding:20px;text-align:center;color:#64748b;">' +
            '<i class="fa-solid fa-rotate fa-spin" style="font-size:20px;color:#2563eb;display:block;margin-bottom:8px;"></i>' +
            'Searching... this takes a few seconds</div>';
        _positionPanel();
        p.style.display = 'block';

        fetch('/api/wifi/scan', { credentials: 'same-origin' })
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (data) {
                var networks = Array.isArray(data) ? data : (data.networks || []);
                _wifiNetworks = networks;
                _renderPanel(networks);
                _positionPanel();
                var count = networks.length;
                if (hint) hint.textContent = count + ' network' + (count !== 1 ? 's' : '') + ' found — click one to select';
            })
            .catch(function (err) {
                if (p) p.innerHTML =
                    '<div style="padding:20px;text-align:center;color:#ef4444;">' +
                    '<i class="fa-solid fa-triangle-exclamation" style="display:block;margin-bottom:8px;"></i>' +
                    'Network search failed: ' + err.message + '</div>';
                if (hint) hint.textContent = 'Network search failed';
            })
            .then(function () {
                if (btn) btn.disabled = false;
                if (icon) icon.className = 'fa-solid fa-rotate text-sm';
            });
    };

    // =========================================================================
    // WIFI AUTO-CONNECT TOGGLE (FIXED - SCENARIO 2)
    // =========================================================================
    var _acEnabled = false;
    var _acTimer = null;

    var _setAcUi = function (enabled, busy) {
        var track = el('ac-track');
        var thumb = el('ac-thumb');
        var label = el('ac-label');
        var btn = el('wifi-auto-connect-btn');
        if (!track || !thumb) return;

        if (busy) {
            track.style.background = '#93c5fd';
            thumb.style.transform = 'translateX(12px)';
            if (label) label.textContent = 'Connecting…';
            if (btn) { btn.setAttribute('aria-pressed', 'true'); btn.style.borderColor = '#93c5fd'; btn.style.color = '#2563eb'; }
        } else if (enabled) {
            track.style.background = '#2563eb';
            thumb.style.transform = 'translateX(12px)';
            if (label) label.textContent = 'Auto';
            if (btn) { btn.setAttribute('aria-pressed', 'true'); btn.style.borderColor = '#2563eb'; btn.style.color = '#2563eb'; btn.style.background = '#eff6ff'; }
        } else {
            track.style.background = '#cbd5e1';
            thumb.style.transform = 'translateX(0px)';
            if (label) label.textContent = 'Auto';
            if (btn) { btn.setAttribute('aria-pressed', 'false'); btn.style.borderColor = '#cbd5e1'; btn.style.color = '#64748b'; btn.style.background = '#fff'; }
        }
    };

    // NO LONGER USED: Replacing with UI-based selection in _stopAutoConnect
    var _getCurrentActiveRouteFresh = function () {
        return { route: null, mode: null, eth: null };
    };

    // FIXED: Complete _stopAutoConnect function
    // When turning OFF auto, automatically send the current active route
    var _stopAutoConnect = function () {
    // Determine the route based on the CURRENT VIEWED TAB in the UI
    var viewedMode = getRadioValue('[name="network-mode"]') || 'wifi';
    var routeNum = 4;
    var ethIface = null;

    if (viewedMode === 'ethernet') {
        ethIface = _selectedEth || 'eth0';
        routeNum = (ethIface === 'eth1') ? 2 : 1;
    } else {
        routeNum = _ROUTE_MAP[viewedMode] !== undefined ? _ROUTE_MAP[viewedMode] : 4;
    }
    
    // Disable auto-connect flag immediately
    _acEnabled = false;
    
    if (_acTimer) { 
        clearInterval(_acTimer); 
        _acTimer = null; 
    }
    _setAcUi(false, false);
    
    // Persist auto_connect: false to backend
    fetch('/api/general-configuration', {
        method: 'PUT',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ network: { auto_connect: false, last_route_select: routeNum } })
    }).then(function () {
        // Send the route corresponding to the CURRENTLY VIEWED tab
        // Specialized endpoint supports 0=auto, 1=eth0, 2=eth1, 3=lte, 4=wifi
        return fetch('/api/pipeline/network-route-select', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ network_route_select: routeNum })
        });
    }).catch(function (e) {
        console.warn('[AUTO-OFF] failed to switch route:', e);
    });
    
    // Mark the viewed interface as manually connected
    if (viewedMode === 'ethernet' && ethIface) {
        _manualConnectClicked['ethernet-' + ethIface] = true;
    } else {
        _manualConnectClicked[viewedMode] = true;
    }
    
    // Update UI to show connected state for all interfaces based on current link status
    ['ethernet', 'wifi', 'lte'].forEach(function (m) {
        var isLinkUp = false;
        if (m === 'ethernet') {
            isLinkUp = isUp((_cache.lan.eth0 || {}).state) || isUp((_cache.lan.eth1 || {}).state);
        } else if (m === 'wifi') {
            isLinkUp = isUp((_cache.wlan || {}).state);
        } else if (m === 'lte') {
            isLinkUp = isUp((_cache.lte || {}).state);
        }
        _updateTabConnectedState(m, isLinkUp);
    });

    showNotification('Auto-connect disabled. ' + viewedMode.toUpperCase() + ' route selected.', 'info');
};

    var _toggleAutoConnect = function () {
        if (_acEnabled) {
            _stopAutoConnect();
            return;
        }
        
        _acEnabled = true;
        _manualConnectClicked = {};
        _setAcUi(true, false);
        
        var e0State = _cache.lan.eth0.state;
        var e1State = _cache.lan.eth1.state;
        var lState = _cache.lte.state;
        var wState = _cache.wlan.state;
        
        var e0Up = isUp(e0State);
        var e1Up = isUp(e1State);
        var lUp = isUp(lState);
        var wUp = isUp(wState);
        
        _updateTabConnectedState('ethernet', e0Up || e1Up);
        _updateTabConnectedState('lte', lUp);
        _updateTabConnectedState('wifi', wUp);
        
        fetch('/api/general-configuration', {
            method: 'PUT',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ network: { auto_connect: true } })
        }).then(function () {
            // Explicitly tell the pipeline to use "Auto" (0) mode
            return fetch('/api/pipeline/network-route-select', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ network_route_select: 0 })
            });
        }).catch(function (e) {
            console.warn('[AUTO-CONNECT] failed to persist ON:', e);
        });
        
        showNotification('Auto-connect enabled. Gateway will automatically use active connection.', 'success');
    };

    var initWifiScanAndConnect = function () {
        _createPanel();

        var scanBtn = el('wifi-scan-btn');
        if (scanBtn) {
            scanBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                _doScanWifi();
            });
        }

        var acBtn = el('wifi-auto-connect-btn');
        if (acBtn && !acBtn.dataset.acBound) {
            acBtn.dataset.acBound = '1';
            acBtn.addEventListener('click', _toggleAutoConnect);
        }

        document.addEventListener('click', function (e) {
            if (!_wifiPanel || _wifiPanel.style.display === 'none') return;
            var btn = el('wifi-scan-btn');
            if (btn && btn.contains(e.target)) return;
            if (_wifiPanel.contains(e.target)) return;
            _closePanel();
        });

        window.addEventListener('scroll', function () {
            if (_wifiPanel && _wifiPanel.style.display !== 'none') _positionPanel();
        }, true);
        window.addEventListener('resize', function () {
            if (_wifiPanel && _wifiPanel.style.display !== 'none') _positionPanel();
        });

        var saved = (el('wifi-ssid-value') || {}).value || 'Univa-Guest';
        var lbl = el('wifi-ssid-label');
        if (lbl) lbl.textContent = saved;
    };

    // =========================================================================
    // ETHERNET INTERFACE SELECTION
    // =========================================================================
    var _selectedEth = null;

    var _setEthCardSelected = function (which) {
        _selectedEth = which;
        ['eth0', 'eth1'].forEach(function (iface) {
            var card = document.getElementById(iface + '-card');
            var radio = document.getElementById(iface + '-radio');
            var icon = document.getElementById(iface + '-radio-icon');
            if (!card) return;
            if (iface === which) {
                card.style.borderColor = '#2563EB';
                card.style.background = '#EFF6FF';
                if (radio) radio.className = 'w-5 h-5 rounded-full border-2 border-emerald-500 bg-emerald-500 flex items-center justify-center transition-colors';
                if (icon) icon.classList.remove('opacity-0');
            } else {
                card.style.borderColor = '';
                card.style.background = '';
                if (radio) radio.className = 'w-5 h-5 rounded-full border-2 border-slate-300 flex items-center justify-center transition-colors';
                if (icon) icon.classList.add('opacity-0');
            }
        });

        updateGlobalMacDisplay();
    };

    var initEthernetSelectButtons = function () {
        ['eth0', 'eth1'].forEach(function (iface) {
            var card = document.getElementById(iface + '-card');
            if (!card) return;
            var newCard = card.cloneNode(true);
            card.parentNode.replaceChild(newCard, card);
            
            newCard.addEventListener('click', function () {
                _setEthCardSelected(iface);
                _selectedEth = iface;
                updateGlobalMacDisplay();

                if (_acEnabled) {
                    var e0Up = isUp((_cache.lan.eth0 || {}).state);
                    var e1Up = isUp((_cache.lan.eth1 || {}).state);
                    var thisPortUp = (iface === 'eth0') ? e0Up : e1Up;
                    
                    if (thisPortUp) {
                        var tab = document.getElementById('net-tab-ethernet');
                        var btn = document.getElementById('ethernet-connect-btn');
                        var lbl = document.getElementById('ethernet-connect-label');
                        if (tab) tab.classList.add('connected');
                        if (btn) btn.classList.add('is-connected');
                        if (lbl) lbl.textContent = 'Connected';
                    }
                } else {
                    var portKey = 'ethernet-' + iface;
                    var isPortConnected = isUp((_cache.lan[iface] || {}).state);
                    
                    if (!_manualConnectClicked[portKey]) {
                        var btn = document.getElementById('ethernet-connect-btn');
                        var lbl = document.getElementById('ethernet-connect-label');
                        var tab = document.getElementById('net-tab-ethernet');
                        if (btn) btn.classList.remove('is-connected');
                        if (lbl) lbl.textContent = 'Connect';
                        if (tab) tab.classList.remove('connected');
                    } else if (_manualConnectClicked[portKey] && isPortConnected) {
                        var btn = document.getElementById('ethernet-connect-btn');
                        var lbl = document.getElementById('ethernet-connect-label');
                        var tab = document.getElementById('net-tab-ethernet');
                        if (btn) btn.classList.add('is-connected');
                        if (lbl) lbl.textContent = 'Connected';
                        if (tab) tab.classList.add('connected');
                    }
                }
            });
        });
    };

    // =========================================================================
    // RENDER LTE
    // =========================================================================
    var renderLte = function () {
        var l = _cache.lte;

        if (l.power !== undefined && !isFieldStale('net.lte.power')) {
            if (!isUp(l.power)) {
                show('lte-power-off-alert');
                hide('lte-live-panel');
                return;
            } else {
                hide('lte-power-off-alert');
            }
        } else if (l.power === undefined) {
            show('lte-power-off-alert');
            hide('lte-live-panel');
            return;
        }

        show('lte-live-panel');

        var state = l.state;
        if (isFieldStale('net.lte.state')) state = null;
        var lteUp = isUp(state);
        stateBadge('lte-state-badge', lteUp);

        var pct = (!isFieldStale('net.lte.signal_pct') && l.signal_pct !== undefined)
            ? parseInt(l.signal_pct) || 0
            : 0;
        var fill = el('lte-signal-fill');
        if (fill) fill.style.width = pct + '%';
        var barColor = pct >= 70 ? 'bg-emerald-500' : pct >= 40 ? 'bg-yellow-400' : 'bg-red-400';
        if (fill) fill.className = 'h-full rounded-full transition-all ' + barColor;
        var pctEl = el('lte-signal-pct');
        if (pctEl) pctEl.textContent = pct + '%';

        txt('lte-ip', (!isFieldStale('net.lte.ip') && l.ip) ? l.ip : '--');
        txt('lte-operator-name', (!isFieldStale('net.lte.operator_name') && l.operator_name) ? l.operator_name : '--');
        txt('lte-operator-id', (!isFieldStale('net.lte.operator_id') && l.operator_id) ? l.operator_id : '--');
        txt('lte-tech', (!isFieldStale('net.lte.tech') && l.tech) ? l.tech : '--');
        txt('lte-imei', (!isFieldStale('net.lte.imei') && l.imei) ? l.imei : '--');
        txt('lte-iccid', (!isFieldStale('net.lte.iccid') && l.iccid) ? l.iccid : '--');
        txt('lte-imsi', (!isFieldStale('net.lte.imsi') && l.imsi) ? l.imsi : '--');

        updateGlobalMacDisplay();
        _autoHighlight();
        _updateTabConnectedState('lte', lteUp);
    };

    // =========================================================================
    // APPLY SNAPSHOT OR DELTA
    // =========================================================================
    var _cache = { lan: { eth0: {}, eth1: {} }, wlan: {}, lte: {} };
    var _liveConnected = false;

    var mergeInto = function (target, src) {
        if (!src || typeof src !== 'object') return;
        Object.keys(src).forEach(function (k) {
            var v = src[k];
            if (v !== null && v !== undefined && v !== '') {
                if (typeof v === 'object' && !Array.isArray(v)) {
                    if (!target[k] || typeof target[k] !== 'object') target[k] = {};
                    mergeInto(target[k], v);
                } else { target[k] = v; }
            }
        });
    };

    var updateCacheFromDelta = function (datapoint, value, path) {
        updateFieldTimestamp(datapoint);

        if (path) {
            var type = path.type;
            var device = path.device;
            var field = path.field;

            if (type === 'lte' && _cache.lte) {
                _cache.lte[field] = value;
            } else if (type === 'wlan' && _cache.wlan) {
                _cache.wlan[field] = value;
                if (field === 'signal') {
                    _cache.wlan.signal_quality = value;
                } else if (field === 'signal_quality') {
                    _cache.wlan.signal = value;
                }
            } else if (type === 'lan' && _cache.lan) {
                if (device && _cache.lan[device]) {
                    _cache.lan[device][field] = value;
                } else if (_cache.lan[field] !== undefined) {
                    _cache.lan[field] = value;
                }
            }
            return true;
        }

        var parts = datapoint.split('.');
        if (parts.length >= 3 && parts[0] === 'net') {
            var iface = parts[1];
            var field = parts[2];

            if (iface === 'lte' && _cache.lte) {
                _cache.lte[field] = value;
            } else if (iface === 'wlan' && _cache.wlan) {
                _cache.wlan[field] = value;
                if (field === 'signal') {
                    _cache.wlan.signal_quality = value;
                } else if (field === 'signal_quality') {
                    _cache.wlan.signal = value;
                }
            } else if (iface === 'lan' && _cache.lan) {
                if (parts.length >= 4) {
                    var eth = parts[2];
                    var subfield = parts[3];
                    if (_cache.lan[eth]) {
                        _cache.lan[eth][subfield] = value;
                    }
                } else if (_cache.lan[field] !== undefined) {
                    _cache.lan[field] = value;
                }
            }
            return true;
        }

        return false;
    };

    var updateTimestampsFromObject = function (obj, prefix) {
        if (!obj || typeof obj !== 'object') return;
        for (var key in obj) {
            if (obj.hasOwnProperty(key)) {
                if (typeof obj[key] === 'object' && obj[key] !== null) {
                    updateTimestampsFromObject(obj[key], prefix + '.' + key);
                } else {
                    _fieldTimestamps[prefix + '.' + key] = Date.now();
                }
            }
        }
    };

    var applySnapshot = function (data) {
        if (!data) return;

        if (data.type === 'network_status_delta' && data.datapoint) {
            updateCacheFromDelta(data.datapoint, data.value, data.path);
            if (data.datapoint.includes('.lte.')) {
                renderLte();
            } else if (data.datapoint.includes('.wlan.')) {
                renderWifi();
            } else if (data.datapoint.includes('.lan.')) {
                renderEthernet();
            }
            return;
        }

        if (data.type === 'network_status_initial' && data.data) {
            markAllFieldsStale();
            mergeInto(_cache.lan, data.data.lan || {});
            mergeInto(_cache.wlan, data.data.wlan || {});
            mergeInto(_cache.lte, data.data.lte || {});

            if (data.data.lan) {
                updateTimestampsFromObject(data.data.lan, 'net.lan');
            }
            if (data.data.wlan) {
                updateTimestampsFromObject(data.data.wlan, 'net.wlan');
            }
            if (data.data.lte) {
                updateTimestampsFromObject(data.data.lte, 'net.lte');
            }

            renderEthernet();
            renderWifi();
            renderLte();
            return;
        }

        if (data.lan || data.wlan || data.lte) {
            markAllFieldsStale();
            mergeInto(_cache.lan, data.lan || {});
            mergeInto(_cache.wlan, data.wlan || {});
            mergeInto(_cache.lte, data.lte || {});
            renderEthernet();
            renderWifi();
            renderLte();
        }
    };

    // =========================================================================
    // LIVE BUTTON + WEBSOCKET (FIXED)
    // =========================================================================
    var _netWs = null;
    var _netActive = false;
    var _netReconnect = null;
    var _netAttempts = 0;

    var setLiveBtnState = function (connected) {
        var btn = el('live-btn-network');
        if (btn) {
            btn.className = connected
                ? 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold text-white bg-emerald-500 transition-colors'
                : 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold text-white bg-slate-400 transition-colors';
            btn.innerHTML = connected
                ? '<i class="fa-solid fa-circle-dot fa-beat"></i> Live'
                : '<i class="fa-solid fa-tower-broadcast"></i> Live';
        }
    };

    var connectNetworkStatusWs = function () {
        if (!_netActive) return;
        if (_netWs && (_netWs.readyState === WebSocket.OPEN || _netWs.readyState === WebSocket.CONNECTING)) return;
        if (_netReconnect) { clearTimeout(_netReconnect); _netReconnect = null; }

        var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        var url = protocol + '//' + window.location.host + '/ws/network-status';
        
        try {
            _netWs = new WebSocket(url);
            
            _netWs.onopen = function () {
                _liveConnected = true;
                _netAttempts = 0;
                setLiveBtnState(true);
            };

            _netWs.onmessage = function (ev) {
                try {
                    var data = JSON.parse(ev.data);
                    applySnapshot(data);
                } catch (e) { console.warn('[NET-STATUS] bad message:', e); }
            };

            _netWs.onclose = function (event) {
                _liveConnected = false;
                _netWs = null;
                setLiveBtnState(false);
                if (_netActive) {
                    var delay = Math.min(30000, 2000 * Math.pow(2, _netAttempts));
                    _netAttempts++;
                    _netReconnect = setTimeout(connectNetworkStatusWs, delay);
                }
            };

            _netWs.onerror = function (error) {
                console.warn('[NET-STATUS] WebSocket error:', error);
                if (_netWs) {
                    _netWs.close();
                }
            };
        } catch (e) {
            console.warn('[NET-STATUS] WebSocket create failed:', e);
            if (_netActive) {
                _netReconnect = setTimeout(connectNetworkStatusWs, 5000);
            }
        }
    };

    var disconnectNetworkStatusWs = function () {
        _netActive = false;
        _liveConnected = false;
        setLiveBtnState(false);
        if (_netReconnect) { 
            clearTimeout(_netReconnect); 
            _netReconnect = null; 
        }
        if (_netWs) {
            try {
                _netWs.close();
            } catch (e) {}
            _netWs = null;
        }
        _netAttempts = 0;
    };

    window.networkStatusLive = {
        connect: function () { 
            if (!_netActive) {
                _netActive = true;
                connectNetworkStatusWs();
            }
        },
        disconnect: disconnectNetworkStatusWs,
        cache: function () { return _cache; }
    };

    // =========================================================================
    // GENERAL WS
    // =========================================================================
    var _wsRetryDelay = 5000;
    var _wsRetryTimer = null;
    var _generalWs = null;
    
    var initializeWebSocket = function () {
        if (_generalWs && (_generalWs.readyState === WebSocket.OPEN || _generalWs.readyState === WebSocket.CONNECTING)) return;
        if (_wsRetryTimer) clearTimeout(_wsRetryTimer);
        
        var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        var url = protocol + '//' + window.location.host + '/ws/general';
        
        try {
            _generalWs = new WebSocket(url);
            
            _generalWs.onopen = function () {
                _wsRetryDelay = 5000;
            };
            
            _generalWs.onmessage = function (ev) {
                try {
                    var d = JSON.parse(ev.data);
                    if (d.type === 'time_update' || d.type === 'time_synced' || d.type === 'initial') {
                        if (d.current_date) {
                            setInputValue('[name="date"]', d.formatted_date || formatDate(d.current_date));
                        }
                        var raw24 = formatTime(d.current_time || '');
                        var tfmt = getSelectValue('[name="time-format"]') || '24-hour';
                        var displayTime = formatTimeDisplay(raw24, tfmt);
                        setInputValue('[name="time"]', displayTime);
                        updateTimeDisplayLabel(raw24);
                    }
                } catch (e) { }
            };
            
            _generalWs.onerror = function (e) {
                console.warn('[GENERAL-WS] error:', e);
            };
            
            _generalWs.onclose = function () {
                _wsRetryDelay = Math.min(_wsRetryDelay * 2, 60000);
                _wsRetryTimer = setTimeout(initializeWebSocket, _wsRetryDelay);
            };
        } catch (e) {
            _wsRetryTimer = setTimeout(initializeWebSocket, _wsRetryDelay);
        }
    };

    // =========================================================================
    // DATE / TIME FORMATTERS
    // =========================================================================
    var getActiveTimezone = function () {
        return getSelectValue('[name="timezone"]') || 'Asia/Kolkata';
    };

    var formatDate = function (isoDate, fmt) {
        if (!isoDate) return '';
        var tz = getActiveTimezone();
        var parts = isoDate.split('-');
        if (parts.length !== 3) return isoDate;
        var offsetStr = tz === 'GMT' ? '+00:00' : '+05:30';
        var d = new Date(parts[0] + '-' + parts[1] + '-' + parts[2] + 'T12:00:00' + offsetStr);
        fmt = fmt || getSelectValue('[name="date-format"]') || 'DD/MM/YYYY';
        var dd = String(d.toLocaleDateString('en-IN', { day: '2-digit', timeZone: tz })).padStart(2, '0');
        var mm = String(d.toLocaleDateString('en-IN', { month: '2-digit', timeZone: tz })).padStart(2, '0');
        var yyyy = d.toLocaleDateString('en-IN', { year: 'numeric', timeZone: tz });
        if (fmt === 'MM/DD/YYYY') return mm + '/' + dd + '/' + yyyy;
        if (fmt === 'YYYY-MM-DD') return yyyy + '-' + mm + '-' + dd;
        return dd + '/' + mm + '/' + yyyy;
    };

    var formatTime = function (hhmm) {
        if (!hhmm) return '';
        var parts = hhmm.split(':');
        var h = parseInt(parts[0]) || 0;
        var min = (parts[1] || '00').substring(0, 2);
        return String(h).padStart(2, '0') + ':' + min;
    };

    var formatTimeDisplay = function (hhmm, fmt) {
        if (!hhmm) return '';
        var parts = hhmm.split(':');
        var h = parseInt(parts[0]) || 0;
        var min = (parts[1] || '00').substring(0, 2);
        return String(h).padStart(2, '0') + ':' + min;
    };

    var updateTimeDisplayLabel = function (hhmm) {
        var fmt = getSelectValue('[name="time-format"]') || '24-hour';
        var lbl = document.querySelector('[data-time-display]');
        if (lbl) lbl.textContent = formatTimeDisplay(hhmm, fmt);
    };

    var getISTNow = function () {
        var tz = getActiveTimezone();
        var now = new Date();
        var dateStr = now.toLocaleDateString('en-CA', { timeZone: tz });
        var timeStr = now.toLocaleTimeString('en-GB', { timeZone: tz, hour: '2-digit', minute: '2-digit', hour12: false });
        return { date: dateStr, time: timeStr };
    };

    // =========================================================================
    // LIVE DATE + TIME INPUTS
    // =========================================================================
    var _clockTimer = null;

    var _buildDateStr = function (now, tz, dateFmt) {
        var d = now.toLocaleDateString('en-GB', { timeZone: tz, day: '2-digit', month: '2-digit', year: 'numeric' });
        var parts = d.split('/');
        if (dateFmt === 'MM/DD/YYYY') return parts[1] + '/' + parts[0] + '/' + parts[2];
        if (dateFmt === 'YYYY-MM-DD') return parts[2] + '-' + parts[1] + '-' + parts[0];
        return d;
    };

    var _buildTimeStr = function (now, tz) {
        return now.toLocaleTimeString('en-GB', {
            timeZone: tz, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
        });
    };

    var _tickInputs = function () {
        var now = new Date();
        var tz = getActiveTimezone();
        var dateFmt = getSelectValue('[name="date-format"]') || 'DD/MM/YYYY';

        var dateEl = document.querySelector('[name="date"]');
        var timeEl = document.querySelector('[name="time"]');

        if (dateEl && document.activeElement !== dateEl) {
            dateEl.value = _buildDateStr(now, tz, dateFmt);
        }
        if (timeEl && document.activeElement !== timeEl) {
            timeEl.value = _buildTimeStr(now, tz);
            timeEl.placeholder = 'HH:MM';
        }

        var hint = document.getElementById('manual-tz-hint');
        if (hint) hint.textContent = tz === 'Asia/Kolkata' ? 'IST (UTC+05:30)' : 'GMT (UTC+00:00)';
    };

    var startLiveInputs = function () {
        _tickInputs();
        if (_clockTimer) clearInterval(_clockTimer);
        _clockTimer = setInterval(_tickInputs, 1000);
    };

    var onTimezoneChange = function () { _tickInputs(); };

    var initTimezoneInteraction = function () {
        var tzSel = document.getElementById('timezone-select');
        if (tzSel) tzSel.addEventListener('change', onTimezoneChange);
        var dfSel = document.querySelector('[name="date-format"]');
        if (dfSel) dfSel.addEventListener('change', _tickInputs);
        startLiveInputs();
    };

    var showNotification = function (msg, type) {
        type = type || 'success';
        var c = el('gc-toast-container');
        if (!c) {
            c = document.createElement('div');
            c.id = 'gc-toast-container';
            c.className = 'fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex flex-col items-center gap-2';
            document.body.appendChild(c);
        }
        var n = document.createElement('div');
        var colors = { success: ' bg-emerald-50 border-emerald-200 text-emerald-800', error: ' bg-red-50 border-red-200 text-red-800', warning: ' bg-yellow-50 border-yellow-200 text-yellow-800', info: ' bg-blue-50 border-blue-200 text-blue-800' };
        var icons = { success: 'fa-circle-check', error: 'fa-circle-exclamation', warning: 'fa-triangle-exclamation', info: 'fa-circle-info' };
        n.className = 'gc-toast px-4 py-3 rounded-lg shadow-lg border transition-all duration-300' + (colors[type] || colors.info);
        n.innerHTML = '<div class="flex items-center"><i class="fa-solid ' + (icons[type] || 'fa-circle-info') + ' mr-3"></i><span class="font-medium">' + msg + '</span><button class="ml-4 text-slate-400 hover:text-slate-600" onclick="this.parentElement.parentElement.remove()"><i class="fa-solid fa-times"></i></button></div>';
        c.appendChild(n);
        setTimeout(function () {
            if (n.parentNode) { n.classList.add('hide'); setTimeout(function () { if (n.parentNode) n.remove(); }, 300); }
        }, 5000);
    };

    // =========================================================================
    // COLLECT FORM DATA
    // =========================================================================
    var collectFormData = function () {
        var l = _cache.lte || {};
        var w = _cache.wlan || {};
        var e0 = (_cache.lan || {}).eth0 || {};
        var e1 = (_cache.lan || {}).eth1 || {};
        var _ethSel = _selectedEth || 'eth0';
        return {
            gateway_identity: {
                name: getInputValue('[name="gateway-name"]') || 'Univa-GW-01',
                serial_number: getInputValue('[name="serial-number"]') || 'GW2025-1190021',
                deployment_site: getInputValue('[name="deployment-site"]') || 'Chennai Port - Zone A',
                location_mode: getRadioValue('[name="location-mode"]') || 'manual',
                latitude: parseFloat(getInputValue('[name="latitude"]')) || 12.99123,
                longitude: parseFloat(getInputValue('[name="longitude"]')) || 80.12312,
                asset_id: getInputValue('[name="asset-id"]') || 'CRN-CT-12'
            },
            date_time: {
                timezone: getActiveTimezone(),
                ntp_server: getSelectValue('[name="ntp-server"]') || 'time.google.com',
                date_format: getSelectValue('[name="date-format"]') || 'DD/MM/YYYY',
                time_format: getSelectValue('[name="time-format"]') || '24-hour'
            },
            network: {
                mode: getRadioValue('[name="network-mode"]') || 'wifi',
                eth_selected: _ethSel,
                auto_connect: _acEnabled,
                wifi: {
                    ssid: (function () { var h = el('wifi-ssid-value'); return h ? h.value : getInputValue('[name="wifi-ssid"]'); }()),
                    password: getInputValue('[name="wifi-password"]'),
                    live_state: w.state,
                    live_signal_quality: w.signal_quality,
                    live_ip: w.ip || '',
                    live_mac: w.mac || '',
                    live_bssid: w.bssid || '',
                    live_frequency: w.frequency || 0
                },
                ethernet: {
                    ip_assignment: getRadioValue('[name="ip-assignment"]') || 'dhcp',
                    static_ip: getInputValue('[name="static-ip"]'),
                    subnet_mask: getInputValue('[name="subnet-mask"]'),
                    gateway: getInputValue('[name="gateway"]'),
                    dns1: getInputValue('[name="dns1"]'),
                    dns2: getInputValue('[name="dns2"]'),
                    live_eth0_ip: e0.ip || '',
                    live_eth0_mac: e0.mac || '',
                    live_eth0_state: e0.state,
                    live_eth1_ip: e1.ip || '',
                    live_eth1_mac: e1.mac || '',
                    live_eth1_state: e1.state
                },
                cellular: {
                    apn: getInputValue('[name="cellular-apn"]'),
                    username: getInputValue('[name="cellular-username"]'),
                    password: getInputValue('[name="cellular-password"]'),
                    live_state: l.state,
                    live_power: l.power,
                    live_signal_pct: l.signal_pct,
                    live_imei: l.imei || '',
                    live_operator_id: l.operator_id || '',
                    live_operator_name: l.operator_name || '',
                    live_ip: l.ip || '',
                    live_iccid: l.iccid || '',
                    live_imsi: l.imsi || '',
                    live_tech: l.tech || ''
                }
            },
            heartbeat: (function () {
                var rawInterval = parseInt(getInputValue('[name="heartbeat-interval"]'));
                var rawThreshold = parseInt(getInputValue('[name="offline-threshold"]'));
                var interval = (!isNaN(rawInterval) && rawInterval >= 0) ? rawInterval : 30;
                var offline_threshold = (!isNaN(rawThreshold) && rawThreshold >= 0) ? rawThreshold : 120;
                return { interval: interval, offline_threshold: offline_threshold };
            }()),
            mac_address: (function () { var m = $('[data-mac-address]'); return m ? m.textContent.trim() : ''; }())
        };
    };

    // =========================================================================
    // SAVE
    // =========================================================================
    var toggleLoader = function (show, text, isSuccess) {
        var loader = el('gc-page-loader');
        if (!loader) return;
        var sub = el('gc-loader-sub');
        var mainText = el('gc-loader-main');
        var iconContainer = el('gc-loader-icon-container');

        if (text && sub) sub.textContent = text;

        if (isSuccess === true) {
            if (mainText) mainText.textContent = 'Success';
            if (iconContainer) iconContainer.innerHTML = '<i class="fa-solid fa-circle-check text-5xl text-emerald-500 mb-2"></i>';
        } else if (isSuccess === false) {
            if (mainText) mainText.textContent = 'Failed';
            if (iconContainer) iconContainer.innerHTML = '<i class="fa-solid fa-triangle-exclamation text-5xl text-red-500 mb-2"></i>';
        } else {
            if (mainText) mainText.textContent = 'Processing';
            if (iconContainer) iconContainer.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin text-5xl text-primary mb-2"></i>';
        }

        if (show) {
            loader.classList.remove('opacity-0', 'pointer-events-none');
        } else {
            loader.classList.add('opacity-0', 'pointer-events-none');
        }
    };

    var handleSaveConfiguration = function () {
        var btn = el('save-btn'); if (!btn) return;

        var hbRaw = parseInt(getInputValue('[name="heartbeat-interval"]'));
        var otRaw = parseInt(getInputValue('[name="offline-threshold"]'));
        if (!isNaN(hbRaw) && hbRaw < 0) {
            showNotification('Heartbeat interval cannot be negative.', 'warning');
            return;
        }
        if (!isNaN(otRaw) && otRaw < 0) {
            showNotification('Offline threshold cannot be negative.', 'warning');
            return;
        }

        var orig = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Saving…';
        btn.disabled = true;
        btn.classList.remove('bg-primary', 'hover:bg-primaryHover');
        btn.classList.add('bg-gray-500', 'cursor-wait');

        toggleLoader(true, 'Please wait while settings are applied...');

        fetch('/api/general-configuration', {
            method: 'PUT', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify(collectFormData())
        })
            .then(function (r) { if (!r.ok) return r.json().then(function (e) { throw new Error(e.message || 'HTTP ' + r.status); }); return r.json(); })
            .then(function (result) {
                toggleLoader(true, 'Configuration saved successfully!', true);
                btn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Save Success';
                btn.classList.remove('bg-gray-500', 'cursor-wait');
                btn.classList.add('bg-emerald-600', 'hover:bg-emerald-700');
                window.dispatchEvent(new Event('gateway-config-saved'));
                setTimeout(function () {
                    toggleLoader(false);
                    btn.innerHTML = orig; btn.classList.remove('bg-emerald-600', 'hover:bg-emerald-700'); btn.classList.add('bg-primary', 'hover:bg-primaryHover'); btn.disabled = false;
                }, 2000);
            })
            .catch(function (err) {
                toggleLoader(true, err.message, false);
                btn.innerHTML = '<i class="fa-solid fa-exclamation-triangle mr-2"></i> Failed!';
                btn.classList.remove('bg-gray-500', 'cursor-wait');
                btn.classList.add('bg-red-600', 'hover:bg-red-700');
                setTimeout(function () {
                    toggleLoader(false);
                    btn.innerHTML = orig; btn.classList.remove('bg-red-600', 'hover:bg-red-700'); btn.classList.add('bg-primary', 'hover:bg-primaryHover'); btn.disabled = false;
                }, 3000);
            });
    };

    // =========================================================================
    // LOAD CONFIGURATION
    // =========================================================================
    var loadConfiguration = function () {
        return new Promise(function (resolve, reject) {
            fetch('/api/general-configuration', { credentials: 'same-origin' })
                .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
                .then(function (cfg) {
                    populateFormWithConfig(cfg);
                    _configLoaded = true;
                    if (cfg._realtime) {
                        if (cfg._realtime.current_date) setInputValue('[name="date"]', formatDate(cfg._realtime.current_date));
                        if (cfg._realtime.current_time) {
                            var raw24 = formatTime(cfg._realtime.current_time);
                            var tfmt = getSelectValue('[name="time-format"]') || '24-hour';
                            var displayTime = formatTimeDisplay(raw24, tfmt);
                            setInputValue('[name="time"]', displayTime);
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
            setInputValue('[name="gateway-name"]', id.name);
            setInputValue('[name="serial-number"]', id.serial_number);
            setInputValue('[name="deployment-site"]', id.deployment_site);
            setRadioValue('[name="location-mode"]', id.location_mode);
            setInputValue('[name="latitude"]', id.latitude);
            setInputValue('[name="longitude"]', id.longitude);
            setInputValue('[name="asset-id"]', id.asset_id);
        }
        if (cfg.date_time) {
            setSelectValue('[name="timezone"]', cfg.date_time.timezone);
            setSelectValue('[name="ntp-server"]', cfg.date_time.ntp_server);
            setSelectValue('[name="date-format"]', cfg.date_time.date_format);
            setSelectValue('[name="time-format"]', cfg.date_time.time_format);
        }
        if (cfg.network) {
            var n = cfg.network, w = n.wifi || {}, e = n.ethernet || {}, c = n.cellular || {};
            setInputValue('[name="wifi-ssid"]', w.ssid || '');
            if (w.ssid) {
                var hid = el('wifi-ssid-value');
                if (hid) hid.value = w.ssid;
                var lbl = el('wifi-ssid-label');
                if (lbl) lbl.textContent = w.ssid;
            }
            setInputValue('[name="wifi-password"]', w.password || '');
            setRadioValue('[name="ip-assignment"]', e.ip_assignment || 'dhcp');
            setInputValue('[name="static-ip"]', e.static_ip || '');
            setInputValue('[name="subnet-mask"]', e.subnet_mask || '');
            setInputValue('[name="gateway"]', e.gateway || '');
            setInputValue('[name="dns1"]', e.dns1 || '');
            setInputValue('[name="dns2"]', e.dns2 || '');
            setInputValue('[name="cellular-apn"]', c.apn || '');
            setInputValue('[name="cellular-username"]', c.username || '');
            setInputValue('[name="cellular-password"]', c.password || '');

            // BUGFIX: Set _acEnabled and _manualConnectClicked BEFORE setNetworkMode
            // so that when the mode radio fires its change event, the tab connected
            // state is already correct and is not wiped by the change handler.
            if (n.auto_connect) {
                _acEnabled = true;
                _manualConnectClicked = {};
                _setAcUi(true, false);
            } else {
                _acEnabled = false;
                // Pre-populate _manualConnectClicked from last_route_select
                // so the Connect button shows green for the already-connected interface.
                var lrs = n.last_route_select || 0;
                if (lrs === 1) { _manualConnectClicked['ethernet-eth0'] = true; }
                else if (lrs === 2) { _manualConnectClicked['ethernet-eth1'] = true; }
                else if (lrs === 3) { _manualConnectClicked['lte'] = true; }
                else if (lrs === 4) { _manualConnectClicked['wifi'] = true; }
                _setAcUi(false, false);
            }

            if (n.mode === 'ethernet') {
                var savedEth = n.eth_selected || 'eth0';
                _selectedEth = savedEth;
                _setEthCardSelected(savedEth);
            }
            setNetworkMode(n.mode || 'wifi');
        }
        if (cfg.heartbeat) {
            setInputValue('[name="heartbeat-interval"]', cfg.heartbeat.interval);
            setInputValue('[name="offline-threshold"]', cfg.heartbeat.offline_threshold);
        }
        if (cfg.mac_address) { var m = $('[data-mac-address]'); if (m) m.textContent = cfg.mac_address; }
        updateGlobalMacDisplay();
    };

    // =========================================================================
    // INITIALIZE NETWORK TOGGLES
    // =========================================================================
    var initializeNetworkToggles = function () {
        document.querySelectorAll('.net-mode-tab').forEach(function (tab) {
            tab.addEventListener('click', function () {
                var mode = this.dataset.mode;
                var radio = document.getElementById('net-radio-' + mode);
                if (radio && !radio.checked) {
                    radio.checked = true;
                    radio.dispatchEvent(new Event('change', { bubbles: true }));
                }
            });
        });

        document.querySelectorAll('input[name="network-mode"]').forEach(function (r) {
            r.addEventListener('change', function () {
                var newMode = this.value;
                setNetworkMode(newMode);
                _syncNetworkTabs(newMode);
                if (newMode !== 'ethernet') { _setEthCardSelected(null); }
                _autoHighlightedMode = null;
                _autoHighlightedEth = null;

                if (!_acEnabled) {
                    _manualConnectClicked[newMode] = false;
                    var btn = document.getElementById(newMode + '-connect-btn');
                    var lbl = document.getElementById(newMode + '-connect-label');
                    var tab = document.getElementById('net-tab-' + newMode);
                    if (btn) btn.classList.remove('is-connected');
                    if (lbl) lbl.textContent = 'Connect';
                    if (tab) tab.classList.remove('connected');
                }

                var modeToSave = this.value;
                var payload = { network: { mode: modeToSave } };
                if (modeToSave === 'ethernet') { payload.network.eth_selected = _selectedEth || 'eth0'; }
                fetch('/api/general-configuration', {
                    method: 'PUT',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                })
                    .catch(function (e) {
                        console.warn('[NET-MODE] failed to persist network_mode:', e);
                    });
                updateGlobalMacDisplay();
            });
        });

        _initConnectButtons();

        document.querySelectorAll('input[name="ip-assignment"]').forEach(function (r) {
            r.addEventListener('change', toggleIPAssignment);
        });
        var c = document.querySelector('input[name="network-mode"]:checked');
        var initMode = c ? c.value : 'wifi';
        setNetworkMode(initMode);
        _syncNetworkTabs(initMode);
        toggleIPAssignment();
    };

    var toggleIPAssignment = function () {
        var ip = $('input[name="ip-assignment"]:checked');
        var box = el('static-ip-config');
        if (!box) return;
        if (ip && ip.value === 'static') box.classList.remove('hidden');
        else box.classList.add('hidden');
    };

    // =========================================================================
    // BUTTONS
    // =========================================================================
    var initializeButtons = function () {
        var refreshBtn = el('refresh-btn');
        if (refreshBtn) {
            var nb = refreshBtn.cloneNode(true);
            refreshBtn.parentNode.replaceChild(nb, refreshBtn);
            nb.addEventListener('click', function () { if (confirm('Refresh? Unsaved changes will be lost.')) location.reload(); });
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
                var orig = this.innerHTML; this.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i>'; this.disabled = true;
                var payload = {
                    timezone: getActiveTimezone(),
                    ntp_server: getSelectValue('[name="ntp-server"]') || 'time.google.com',
                    date_format: getSelectValue('[name="date-format"]') || 'DD/MM/YYYY',
                    time_format: getSelectValue('[name="time-format"]') || '24-hour'
                };
                fetch('/api/sync-time', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                })
                    .then(function (r) {
                        var ok = r.ok;
                        var status = r.status;
                        return r.json().then(function (data) { return { ok: ok, status: status, data: data }; });
                    })
                    .then(function (res) {
                        var fmt = getSelectValue('[name="date-format"]') || 'DD/MM/YYYY';
                        var tfmt = getSelectValue('[name="time-format"]') || '24-hour';

                        if (!res.ok) {
                            var errMsg = (res.data && (res.data.error || res.data.detail)) || ('Server error ' + res.status);
                            var ist = getISTNow();
                            var displayDate = formatDate(ist.date, fmt);
                            var raw24 = formatTime(ist.time);
                            var displayTime = formatTimeDisplay(raw24, tfmt);
                            setInputValue('[name="date"]', displayDate);
                            setInputValue('[name="time"]', raw24);
                            updateTimeDisplayLabel(raw24);
                            showNotification('Sync failed: ' + errMsg + '  \u2014 showing browser time', 'warning');
                            return;
                        }

                        var data = res.data;
                        var displayDate = data.formatted_date || formatDate(data.current_date, fmt);
                        var raw24 = formatTime(data.current_time || '');
                        var displayTime = formatTimeDisplay(raw24, tfmt);
                        setInputValue('[name="date"]', displayDate);
                        setInputValue('[name="time"]', raw24);
                        updateTimeDisplayLabel(raw24);
                        showNotification('Time synchronized  ' + displayDate + ' ' + displayTime + ' (' + getActiveTimezone() + ')', 'success');
                    })
                    .catch(function () {
                        var ist = getISTNow();
                        var fmt = getSelectValue('[name="date-format"]') || 'DD/MM/YYYY';
                        var tfmt = getSelectValue('[name="time-format"]') || '24-hour';
                        var displayDate = formatDate(ist.date, fmt);
                        var raw24 = formatTime(ist.time);
                        var displayTime = formatTimeDisplay(raw24, tfmt);
                        setInputValue('[name="date"]', displayDate);
                        setInputValue('[name="time"]', raw24);
                        updateTimeDisplayLabel(raw24);
                        showNotification('Server unreachable  \u2014 time set from browser  ' + displayDate + ' ' + displayTime + ' (' + getActiveTimezone() + ')', 'warning');
                    })
                    .then(function () { nsy.innerHTML = orig; nsy.disabled = false; });
            });
        }
    };

    // =========================================================================
    // INIT
    // =========================================================================
    var cleanup = function () { window._generalConfigInitializing = false; window._generalConfigInitialized = false; };

    window.initGeneralConfig = function () {
        if (window._generalConfigInitialized || window._generalConfigInitializing) return;
        window._generalConfigInitializing = true;
        window._generalConfigInitialized = true;
        initializeButtons();
        initializePasswordToggles();
        initWifiScanAndConnect();
        initEthernetSelectButtons();
        initializeWebSocket();
        initTimezoneInteraction();
        _netActive = true;
        connectNetworkStatusWs();
        loadConfiguration()
            .then(function () {
                initializeNetworkToggles();
                window._generalConfigInitializing = false;
            })
            .catch(function (err) { console.error('Load error:', err); showNotification('Failed to load config', 'warning'); initializeNetworkToggles(); window._generalConfigInitializing = false; });
    };

    window.cleanupGeneralConfig = cleanup;
    window.showNotification = showNotification;
})();