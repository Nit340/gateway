// pages/js/diagnostics.js

// This function will be called by the router when loading the page
window.initDiagnostics = function() {
    
    // Initialize all functionality for this page
    initializeDiagnosticsPage();
    
    // Load initial data (but don't start auto updates yet)
    loadInitialLogs();
    initializeTerminalSession();
    
};

// Application state for diagnostics
let diagnosticsState = {
    terminalConnected: false,
    liveLogsEnabled: false,
    charts: {},
    serialConnected: false,
    rfScanning: false,
    packetCaptureActive: false,
    unsavedChanges: false,
    sessionTimer: null,
    logStreamInterval: null,
    chartUpdateInterval: null,
    lastNetUpdate: 0,
    lastCPULogUpdate: 0,
    sessionStartTime: null,
    sessionDuration: 30 * 60, // 30 minutes in seconds
    autoUpdatesActive: false
};

function initializeDiagnosticsPage() {
    
    // Initialize all components
    initializeLogViewer();
    initializeTerminal();
    initializeDiagnosticTools();
    initializeFooterButtons();
    initializeCharts(); // Initialize charts but don't start updates
    
    // Setup event listeners
    setupDiagnosticsEventListeners();
    
}

function initializeLogViewer() {
    // Log search functionality
    const logSearch = document.getElementById('log-search');
    if (logSearch) {
        logSearch.addEventListener('input', filterLogs);
    }
    
    // Log level filter
    const logLevel = document.getElementById('log-level');
    if (logLevel) {
        logLevel.addEventListener('change', filterLogs);
    }
    
    // Category checkboxes - REMOVED
    
    // Live stream toggle
    const networkToggleBtn = document.getElementById('network-monitor-toggle-btn');
    if (networkToggleBtn) {
        networkToggleBtn.addEventListener('change', function() {
            if (this.checked && !diagnosticsState.liveLogsEnabled) {
                // Just load last 10 logs once
                fetch(`/api/network/logs?level=All+Levels&limit=10`)
                    .then(r => r.json())
                    .then(data => {
                        const logs = Array.isArray(data) ? data : (data.logs || []);
                        const logConsole = document.getElementById('log-console');
                        if (logConsole) {
                            logConsole.innerHTML = '';
                            logs.forEach(log => addLogEntry(log));
                        }
                    });
            }
        });
    }

    const liveStreamToggle = document.getElementById('liveStream');
    if (liveStreamToggle) {
        liveStreamToggle.addEventListener('click', function() {
            diagnosticsState.liveLogsEnabled = !diagnosticsState.liveLogsEnabled;
            if (diagnosticsState.liveLogsEnabled) {
                this.style.cssText = 'background:#16a34a;color:#fff;opacity:1;transition:none';
                this.innerHTML = '<i class="fa-solid fa-circle-dot mr-1"></i> Live';
                startLogStream();
            } else {
                this.style.cssText = 'background:#cbd5e1;color:#475569;opacity:1;transition:none';
                this.innerHTML = '<i class="fa-solid fa-circle mr-1"></i> Live';
                clearInterval(diagnosticsState.logStreamInterval);
            }
        });
    }
    // Export logs button
    const exportLogsBtn = document.getElementById('export-logs-btn');
    if (exportLogsBtn) {
        exportLogsBtn.addEventListener('click', downloadLogs);
    }
    
    // Clear logs button
    const clearLogsBtn = document.getElementById('clear-logs-btn');
    if (clearLogsBtn) {
        clearLogsBtn.addEventListener('click', clearLogConsole);
    }
    
    // Auto-scroll status indicator
    updateAutoScrollStatus();
    
    // Load current state on init
    loadNetworkMonitorState();
    
    // Set initial placeholder
    const logConsole = document.getElementById('log-console');
    if (logConsole) {
        logConsole.innerHTML = '<div class="text-slate-500 italic">Enable Live Stream to start receiving network logs.</div>';
    }
}

function initializeTerminal() {
    // Command history buttons
    document.querySelectorAll('#command-history button').forEach(btn => {
        btn.addEventListener('click', function() {
            const command = this.dataset.command;
            if (command) {
                executeCommand(command);
            }
        });
    });
    
    // Terminal buttons
    const connectBtn = document.getElementById('connect-terminal-btn');
    const disconnectBtn = document.getElementById('disconnect-terminal-btn');
    const sendBtn = document.getElementById('send-command-btn');
    const terminalInput = document.getElementById('terminal-input');
    
    if (connectBtn) {
        connectBtn.addEventListener('click', connectTerminal);
    }
    
    if (disconnectBtn) {
        disconnectBtn.addEventListener('click', disconnectTerminal);
    }
    
    if (sendBtn) {
        sendBtn.addEventListener('click', sendCommand);
    }
    
    if (terminalInput) {
        terminalInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendCommand();
            }
        });
    }
}

function initializeDiagnosticTools() {
    // Tab functionality
    const tabs = ['tab-packet', 'tab-serial', 'tab-rf'];
    
    tabs.forEach(tabId => {
        const tab = document.getElementById(tabId);
        if (tab) {
            tab.addEventListener('click', function() {
                // Deactivate all tabs
                tabs.forEach(t => {
                    document.getElementById(t).classList.remove('border-primary', 'text-primary');
                    document.getElementById(t).classList.add('border-transparent', 'text-slate-500');
                    const contentId = t.replace('tab-', 'content-');
                    const content = document.getElementById(contentId);
                    if (content) content.classList.add('hidden');
                });
                
                // Activate clicked tab
                this.classList.remove('border-transparent', 'text-slate-500');
                this.classList.add('border-primary', 'text-primary');
                const contentId = tabId.replace('tab-', 'content-');
                const content = document.getElementById(contentId);
                if (content) content.classList.remove('hidden');
            });
        }
    });
    
    // Initialize tab contents
    initializePacketCapture();
    initializeSerialMonitor();
    initializeRFScanner();
}

function initializePacketCapture() {
    // Packet capture controls
    const startCaptureBtn = document.getElementById('start-capture-btn');
    const captureSettingsBtn = document.getElementById('capture-settings-btn');
    
    if (startCaptureBtn) {
        startCaptureBtn.addEventListener('click', startPacketCapture);
    }
    
    if (captureSettingsBtn) {
        captureSettingsBtn.addEventListener('click', showCaptureSettings);
    }
    
    // Capture duration buttons
    document.querySelectorAll('#content-packet button[onclick^="setCaptureDuration"]').forEach(btn => {
        btn.addEventListener('click', function() {
            const seconds = this.textContent.replace('s', '');
            if (!isNaN(seconds)) {
                setCaptureDuration(parseInt(seconds));
            }
        });
    });
    
    // Protocol filter checkboxes
    document.querySelectorAll('#content-packet input[type="checkbox"]').forEach(cb => {
        cb.addEventListener('change', function() {
            diagnosticsState.unsavedChanges = true;
            window.showNotification('Capture settings updated', 'info');
        });
    });
}

function initializeSerialMonitor() {
    // Serial connection button
    const connectSerialBtn = document.getElementById('connect-serial-btn');
    if (connectSerialBtn) {
        connectSerialBtn.addEventListener('click', connectSerial);
    }
    
    // Serial clear button
    const clearSerialBtn = document.getElementById('clear-serial-btn');
    if (clearSerialBtn) {
        clearSerialBtn.addEventListener('click', clearSerialConsole);
    }
}

function initializeRFScanner() {
    // RF scan button
    const startRFScanBtn = document.getElementById('start-rf-scan-btn');
    if (startRFScanBtn) {
        startRFScanBtn.addEventListener('click', startRFScan);
    }
    
    // RF export button
    const exportRFBtn = document.getElementById('export-rf-btn');
    if (exportRFBtn) {
        exportRFBtn.addEventListener('click', exportRFScan);
    }
    
    // RF sensitivity slider
    const sensitivitySlider = document.getElementById('sensitivity');
    if (sensitivitySlider) {
        sensitivitySlider.addEventListener('input', function() {
            updateSensitivityValue(this.value);
        });
    }
    
    // RF format radio buttons
    document.querySelectorAll('input[name="rfFormat"]').forEach(radio => {
        radio.addEventListener('change', function() {
            window.showNotification(`RF output format set to ${this.value.toUpperCase()}`, 'info');
        });
    });
}

function initializeFooterButtons() {
    // Quick diagnostics button
    const quickDiagnosticsBtn = document.getElementById('quick-diagnostics-btn');
    if (quickDiagnosticsBtn) {
        quickDiagnosticsBtn.addEventListener('click', runQuickDiagnostics);
    }
    
    // Save settings button
    const saveBtn = document.getElementById('save-diagnostics-btn');
    if (saveBtn) {
        saveBtn.addEventListener('click', saveDiagnosticsSettings);
    }
    
    // Start Auto Updates button
    const startAutoBtn = document.getElementById('start-auto-btn');
    if (startAutoBtn) {
        startAutoBtn.addEventListener('click', startAllAutoUpdates);
    }
    
    // Stop Auto Updates button
    const stopAutoBtn = document.getElementById('stop-auto-btn');
    if (stopAutoBtn) {
        stopAutoBtn.addEventListener('click', stopAllAutoUpdates);
    }
}

function setupDiagnosticsEventListeners() {
    // Mark unsaved changes on input
    document.querySelectorAll('#pageContent input, #pageContent select, #pageContent textarea').forEach(element => {
        element.addEventListener('change', markUnsavedChanges);
    });
}

// ==================== LOG FUNCTIONS ====================

function loadInitialLogs() {
    // Initial logs are now handled by the live stream when enabled.
}

function addLogEntry(log) {
    const logConsole = document.getElementById('log-console');
    if (!logConsole) return;
    
    const logElement = document.createElement('div');
    logElement.className = 'mb-1';
    let ts = '', lvl = 'INFO', cat = '', msg = '';
    if (typeof log === 'string') {
        // Parse plain text line e.g. "2024-01-01 12:00:00 INFO ethernet: eth0 connected"
        const m = log.match(/^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[\S]*)\s+(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+(.*)/i);
        if (m) { ts = m[1]; lvl = m[2]; msg = m[3]; }
        else { msg = log; }
    } else {
        ts = log.created_at || log.time || '';
        lvl = log.level || 'INFO';
        cat = log.iface_type || log.category || '';
        msg = log.iface_name
            ? `${log.iface_name} — ${log.connected ? 'UP' : 'DOWN'}${log.ip ? ' | ' + log.ip : ''}`
            : (log.message || JSON.stringify(log));
    }

    logElement.innerHTML = `
        <span class="text-emerald-500">[${ts}]</span>
        <span class="${getLogLevelColor(lvl)} ml-2">${lvl.padEnd(5)}</span>
        <span class="text-slate-400 ml-2">${cat}:</span>
        <span class="text-slate-300 ml-1">${msg}</span>
    `;
    logConsole.appendChild(logElement);
    
    // Auto-scroll if enabled
    if (diagnosticsState.liveLogsEnabled) {
        logConsole.scrollTop = logConsole.scrollHeight;
    }
}

function getLogLevelColor(level) {
    switch(level) {
        case 'ERROR': return 'text-red-500';
        case 'WARN': return 'text-yellow-500';
        case 'INFO': return 'text-blue-500';
        case 'DEBUG': return 'text-slate-500';
        default: return 'text-slate-300';
    }
}

function filterLogs() {
    // Restart stream with new level if active
    if (diagnosticsState.liveLogsEnabled) {
        startLogStream();
    }
}

function updateAutoScrollStatus() {
    const statusElement = document.getElementById('autoscroll-status');
    if (statusElement) {
        const enabled = diagnosticsState.liveLogsEnabled;
        statusElement.textContent = `Auto-scroll: ${enabled ? 'ON' : 'OFF'}`;
        statusElement.className = `text-xs ${enabled ? 'text-emerald-400 bg-emerald-900/30' : 'text-slate-400 bg-slate-700'} px-2 py-1 rounded`;
    }
}

async function downloadLogs() {
    window.showNotification('Downloading logs...', 'info');
    try {
        const level = document.getElementById('log-level')?.value || 'All Levels';
        const response = await fetch(`/api/network/logs?level=${encodeURIComponent(level)}&limit=5000`);
        const data = await response.json();
        const logs = Array.isArray(data) ? data : (data.logs || []);
        const text = logs.join('\n');
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `network-logs-${new Date().toISOString().split('T')[0]}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        window.showNotification('Logs downloaded successfully', 'success');
    } catch(e) {
        window.showNotification('Failed to download logs', 'error');
    }
}

function clearLogConsole() {
    const logConsole = document.getElementById('log-console');
    if (logConsole) {
        logConsole.innerHTML = '<div class="text-slate-400">[Logs cleared]</div>';
        window.showNotification('Log console cleared', 'info');
    }
}

// ==================== TERMINAL FUNCTIONS ====================

function initializeTerminalSession() {
    // Load initial terminal output (static, not auto-updating)
    const terminalOutput = document.getElementById('terminal-output');
    if (terminalOutput) {
        const initialOutput = `
            <div class="mb-4">
                <span class="text-emerald-500">root@univa-gw:~$</span> <span class="text-white">uname -a</span><br>
                Linux univa-gw 5.10.0-21-arm64 #1 SMP Debian 5.10.162-1 (2023-01-21) aarch64 GNU/Linux
            </div>
            <div class="mb-4">
                <span class="text-emerald-500">root@univa-gw:~$</span> <span class="text-white">top -b -n 1 | head -n 5</span><br>
                top - 09:45:02 up 2 days, 14:12,  1 user,  load average: 0.45, 0.32, 0.28<br>
                Tasks: 112 total,   1 running, 111 sleeping,   0 stopped,   0 zombie<br>
                %Cpu(s):  4.2 us,  1.8 sy,  0.0 ni, 93.8 id,  0.1 wa,  0.0 hi,  0.1 si,  0.0 st<br>
                MiB Mem :   3920.0 total,   1452.2 free,    824.5 used,   1643.3 buff/cache<br>
                MiB Swap:      0.0 total,      0.0 free,      0.0 used.   2850.1 avail Mem
            </div>
            <div class="mb-4">
                <span class="text-emerald-500">root@univa-gw:~$</span> <span class="text-white">rf-test-tool --scan</span><br>
                Scanning 433MHz band...<br>
                [+] Channel 1 (433.100): RSSI -92 dBm (Clear)<br>
                [+] Channel 2 (433.200): RSSI -88 dBm (Clear)<br>
                [!] Channel 3 (433.300): RSSI -45 dBm (BUSY)<br>
                Scan complete.
            </div>
            <div id="terminal-cursor">
                <span class="text-emerald-500">root@univa-gw:~$</span> <span class="animate-pulse bg-slate-500 w-2 h-4 inline-block align-middle ml-1"></span>
            </div>
        `;
        terminalOutput.innerHTML = initialOutput;
        
        // Set session timer display (static, won't count down until started)
        const timerElement = document.getElementById('session-timer');
        if (timerElement) {
            timerElement.textContent = 'Session: Not Connected';
        }
    }
}

function startSessionTimer() {
    if (diagnosticsState.sessionTimer) {
        clearInterval(diagnosticsState.sessionTimer);
    }
    
    let timeLeft = diagnosticsState.sessionDuration;
    
    diagnosticsState.sessionTimer = setInterval(() => {
        if (timeLeft <= 0) {
            clearInterval(diagnosticsState.sessionTimer);
            disconnectTerminal();
            return;
        }
        
        timeLeft--;
        const minutes = Math.floor(timeLeft / 60);
        const seconds = timeLeft % 60;
        
        const timerElement = document.getElementById('session-timer');
        if (timerElement) {
            timerElement.textContent = `Session expires in ${minutes}:${seconds.toString().padStart(2, '0')}`;
            
            // Warning when less than 5 minutes
            if (timeLeft < 300) {
                timerElement.classList.add('text-amber-600');
            }
        }
    }, 1000);
}

function executeCommand(command) {
    const terminalInput = document.getElementById('terminal-input');
    if (terminalInput) {
        terminalInput.value = command;
        sendCommand();
    }
}

function sendCommand() {
    const terminalInput = document.getElementById('terminal-input');
    const command = terminalInput ? terminalInput.value.trim() : '';
    if (!command) return;

    const terminalOutput = document.getElementById('terminal-output');
    const cursor = document.getElementById('terminal-cursor');
    
    if (!terminalOutput || !cursor) return;
    
    // Add command to output
    const commandElement = document.createElement('div');
    commandElement.className = 'mb-2';
    commandElement.innerHTML = `
        <span class="text-emerald-500">root@univa-gw:~$</span> <span class="text-white">${command}</span>
    `;
    
    cursor.parentNode.insertBefore(commandElement, cursor);
    
    const processingElement = document.createElement('div');
    processingElement.className = 'text-slate-500 text-sm italic mb-1';
    processingElement.textContent = 'Processing...';
    cursor.parentNode.insertBefore(processingElement, cursor);

    fetch('/api/terminal/exec', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command })
    })
    .then(r => r.json())
    .then(data => {
        processingElement.remove();
        const responseElement = document.createElement('div');
        responseElement.className = 'mb-4 text-slate-300 text-sm';
        responseElement.innerHTML = (data.output || data.error || 'No output').replace(/\n/g, '<br>');
        cursor.parentNode.insertBefore(responseElement, cursor);
        terminalOutput.scrollTop = terminalOutput.scrollHeight;
    })
    .catch(err => {
        processingElement.remove();
        const responseElement = document.createElement('div');
        responseElement.className = 'mb-4 text-red-400 text-sm';
        responseElement.textContent = 'Error: ' + err.message;
        cursor.parentNode.insertBefore(responseElement, cursor);
    });
    
    if (terminalInput) {
        terminalInput.value = '';
        terminalInput.focus();
    }
    
    // Scroll to show new command
    terminalOutput.scrollTop = terminalOutput.scrollHeight;
}

function getCommandResponse(command) {
    const responses = {
        'help': 'Available commands: status, scan, test, clear, reboot, ping, ifconfig, netstat',
        'status': 'System Status:<br>CPU: 34.2%<br>Memory: 68.5%<br>Network: Connected<br>RF: Active<br>Modbus: Running',
        'scan': 'Scanning network...<br>Found 12 devices<br>3 Modbus devices<br>2 RF endpoints',
        'test': 'Running diagnostics...<br>All systems operational<br>No errors detected',
        'clear': 'Terminal cleared',
        'reboot': 'System reboot initiated<br>Disconnecting in 5 seconds...',
        'uname -a': 'Linux univa-gw 5.10.0-21-arm64 #1 SMP Debian 5.10.162-1 (2023-01-21) aarch64 GNU/Linux',
        'df -h': 'Filesystem      Size  Used Avail Use% Mounted on<br>/dev/root        29G   12G   16G  44% /<br>/dev/mmcblk0p1  253M   52M  201M  21% /boot',
        'top -b -n 1 | head -n 5': 'top - 09:45:02 up 2 days, 14:12,  1 user,  load average: 0.45, 0.32, 0.28<br>Tasks: 112 total,   1 running, 111 sleeping,   0 stopped,   0 zombie<br>%Cpu(s):  4.2 us,  1.8 sy,  0.0 ni, 93.8 id,  0.1 wa,  0.0 hi,  0.1 si,  0.0 st<br>MiB Mem :   3920.0 total,   1452.2 free,    824.5 used,   1643.3 buff/cache<br>MiB Swap:      0.0 total,      0.0 free,      0.0 used.   2850.1 avail Mem',
        'rf-test-tool --scan': 'Scanning 433MHz band...<br>[+] Channel 1 (433.100): RSSI -92 dBm (Clear)<br>[+] Channel 2 (433.200): RSSI -88 dBm (Clear)<br>[!] Channel 3 (433.300): RSSI -45 dBm (BUSY)<br>Scan complete.',
        'ping -c 3 8.8.8.8': 'PING 8.8.8.8 (8.8.8.8): 56 data bytes<br>64 bytes from 8.8.8.8: icmp_seq=0 ttl=117 time=12.3 ms<br>64 bytes from 8.8.8.8: icmp_seq=1 ttl=117 time=11.8 ms<br>64 bytes from 8.8.8.8: icmp_seq=2 ttl=117 time=12.1 ms<br><br>--- 8.8.8.8 ping statistics ---<br>3 packets transmitted, 3 packets received, 0.0% packet loss<br>round-trip min/avg/max/stddev = 11.8/12.1/12.3/0.2 ms',
        'ifconfig eth0': 'eth0: flags=4163&lt;UP,BROADCAST,RUNNING,MULTICAST&gt;  mtu 1500<br>inet 192.168.1.105  netmask 255.255.255.0  broadcast 192.168.1.255<br>inet6 fe80::ba27:ebff:feb4:1c6b  prefixlen 64  scopeid 0x20&lt;link&gt;<br>ether b8:27:eb:b4:1c:6b  txqueuelen 1000  (Ethernet)<br>RX packets 123456  bytes 98765432 (94.2 MiB)<br>TX packets 98765  bytes 12345678 (11.7 MiB)'
    };
    
    return responses[command] || `Command not found: ${command}<br>Type 'help' for available commands`;
}

function connectTerminal() {
    if (diagnosticsState.terminalConnected) {
        window.showNotification('Terminal is already connected', 'info');
        return;
    }
    
    window.showConfirmationDialog({
        message: 'Connect to gateway terminal? This will start a new SSH session.',
        confirmText: 'Connect',
        cancelText: 'Cancel'
    }).then(confirmed => {
        if (confirmed) {
            diagnosticsState.terminalConnected = true;
            diagnosticsState.sessionStartTime = Date.now();
            
            // Update button states
            const connectBtn = document.getElementById('connect-terminal-btn');
            const disconnectBtn = document.getElementById('disconnect-terminal-btn');
            
            if (connectBtn) connectBtn.disabled = true;
            if (disconnectBtn) disconnectBtn.disabled = false;
            
            // Start session timer
            startSessionTimer();
            
            // Add connection message to terminal
            const terminalOutput = document.getElementById('terminal-output');
            const cursor = document.getElementById('terminal-cursor');
            
            if (terminalOutput && cursor) {
                const connectionMessage = document.createElement('div');
                connectionMessage.className = 'mb-4 text-emerald-400';
                connectionMessage.innerHTML = `<i class="fa-solid fa-plug mr-2"></i> SSH connection established to univa-gw<br>`;
                cursor.parentNode.insertBefore(connectionMessage, cursor);
                terminalOutput.scrollTop = terminalOutput.scrollHeight;
            }
            
            window.showNotification('Terminal connected successfully', 'success');
        }
    });
}

function disconnectTerminal() {
    if (!diagnosticsState.terminalConnected) {
        window.showNotification('Terminal is not connected', 'info');
        return;
    }
    
    window.showConfirmationDialog({
        message: 'Disconnect terminal session? Any active commands will be terminated.',
        confirmText: 'Disconnect',
        cancelText: 'Cancel'
    }).then(confirmed => {
        if (confirmed) {
            diagnosticsState.terminalConnected = false;
            
            // Clear timer
            if (diagnosticsState.sessionTimer) {
                clearInterval(diagnosticsState.sessionTimer);
                diagnosticsState.sessionTimer = null;
            }
            
            // Update button states
            const connectBtn = document.getElementById('connect-terminal-btn');
            const disconnectBtn = document.getElementById('disconnect-terminal-btn');
            
            if (connectBtn) connectBtn.disabled = false;
            if (disconnectBtn) disconnectBtn.disabled = true;
            
            // Update timer display
            const timerElement = document.getElementById('session-timer');
            if (timerElement) {
                timerElement.textContent = 'Session: Disconnected';
                timerElement.classList.remove('text-amber-600');
            }
            
            // Add disconnection message to terminal
            const terminalOutput = document.getElementById('terminal-output');
            const cursor = document.getElementById('terminal-cursor');
            
            if (terminalOutput && cursor) {
                const disconnectionMessage = document.createElement('div');
                disconnectionMessage.className = 'mb-4 text-red-400';
                disconnectionMessage.innerHTML = `<i class="fa-solid fa-plug-circle-xmark mr-2"></i> SSH connection terminated<br>`;
                cursor.parentNode.insertBefore(disconnectionMessage, cursor);
                terminalOutput.scrollTop = terminalOutput.scrollHeight;
            }
            
            window.showNotification('Terminal disconnected', 'info');
        }
    });
}

// ==================== CHART FUNCTIONS ====================

function initializeCharts() {
    // Check if Plotly is loaded
    if (typeof Plotly === 'undefined') {
        console.error('Plotly not loaded');
        return;
    }
    
    // Initialize static charts with sample data
    initStaticCharts();
}

function initStaticCharts() {
    // CPU/Memory Chart - Static initial data
    const cpuTrace = {
        x: Array.from({length: 30}, (_, i) => i),
        y: Array.from({length: 30}, () => 0), // Start with zeros
        mode: 'lines',
        name: 'CPU',
        line: {color: '#2563EB', width: 2}
    };

    const memTrace = {
        x: Array.from({length: 30}, (_, i) => i),
        y: Array.from({length: 30}, () => 0), // Start with zeros
        mode: 'lines',
        name: 'RAM',
        line: {color: '#10B981', width: 2}
    };

    diagnosticsState.charts.cpu = Plotly.newPlot('chart-cpu', [cpuTrace, memTrace], {
        margin: {t: 10, r: 10, b: 30, l: 40},
        showlegend: false,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        xaxis: {showgrid: true, gridcolor: '#E2E8F0', zeroline: false, showticklabels: false},
        yaxis: {showgrid: true, gridcolor: '#E2E8F0', zeroline: false, range: [0, 100], ticksuffix: '%'},
        title: {text: 'Click "Start Monitoring" to begin', font: {size: 12, color: '#64748B'}}
    });

    // RF Signal Chart - Static data
    const rfTrace = {
        x: ['433.1', '433.2', '433.3', '433.4', '433.5', '433.6', '433.7', '433.8', '433.9'],
        y: [-95, -90, -85, -80, -75, -80, -85, -90, -95],
        type: 'bar',
        marker: {color: '#CBD5E1'}
    };

    diagnosticsState.charts.rf = Plotly.newPlot('chart-rf', [rfTrace], {
        margin: {t: 10, r: 10, b: 40, l: 40},
        showlegend: false,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        xaxis: {showgrid: true, gridcolor: '#E2E8F0', zeroline: false},
        yaxis: {showgrid: true, gridcolor: '#E2E8F0', zeroline: false, title: 'dBm'},
        title: {text: 'Static data - Start monitoring for updates', font: {size: 12, color: '#64748B'}}
    });

    // Network Chart - Static initial data
    const netInTrace = {
        x: Array.from({length: 15}, (_, i) => i),
        y: Array.from({length: 15}, () => 0),
        mode: 'lines',
        name: 'In',
        line: {color: '#2563EB', width: 2}
    };

    const netOutTrace = {
        x: Array.from({length: 15}, (_, i) => i),
        y: Array.from({length: 15}, () => 0),
        mode: 'lines',
        name: 'Out',
        line: {color: '#10B981', width: 2}
    };

    diagnosticsState.charts.net = Plotly.newPlot('chart-net', [netInTrace, netOutTrace], {
        margin: {t: 10, r: 10, b: 30, l: 40},
        showlegend: false,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        xaxis: {showgrid: true, gridcolor: '#E2E8F0', zeroline: false, showticklabels: false},
        yaxis: {showgrid: true, gridcolor: '#E2E8F0', zeroline: false, title: 'KB/s'},
        title: {text: 'Waiting for network data...', font: {size: 12, color: '#64748B'}}
    });
}

function startChartUpdates() {
    if (diagnosticsState.chartUpdateInterval) {
        clearInterval(diagnosticsState.chartUpdateInterval);
    }
    
    diagnosticsState.chartUpdateInterval = setInterval(() => {
        // Update CPU chart with realistic-looking data
        if (diagnosticsState.charts.cpu) {
            // Simulate CPU usage between 20-50%
            const newCPUValue = Math.random() * 30 + 20;
            // Simulate RAM usage between 40-70%
            const newRAMValue = Math.random() * 30 + 40;
            
            Plotly.extendTraces('chart-cpu', {
                y: [[newCPUValue], [newRAMValue]]
            }, [0, 1]);

            // Shift data if too long (keep last 60 points)
            Plotly.relayout('chart-cpu', {
                'xaxis.range': [0, 60],
                'title.text': 'Live Monitoring'
            });
        }

        // Update network chart less frequently
        if (diagnosticsState.charts.net) {
            const now = Date.now();
            if (now - diagnosticsState.lastNetUpdate > 2000) { // Update every 2 seconds
                const newInValue = Math.random() * 800 + 200;
                const newOutValue = Math.random() * 400 + 100;
                
                Plotly.extendTraces('chart-net', {
                    y: [[newInValue], [newOutValue]]
                }, [0, 1]);

                // Shift data if too long (keep last 30 points)
                Plotly.relayout('chart-net', {
                    'xaxis.range': [0, 30],
                    'title.text': 'Live Network I/O'
                });
                
                diagnosticsState.lastNetUpdate = now;
            }
        }
        
        // Update RF chart periodically
        if (diagnosticsState.charts.rf && Math.random() > 0.7) { // 30% chance each update
            const newRFData = Array.from({length: 9}, () => Math.random() * 30 - 100);
            Plotly.restyle('chart-rf', 'y', [newRFData]);
            Plotly.relayout('chart-rf', {
                'title.text': 'Live RF Signal'
            });
        }
    }, 1000); // Update every second
    
    window.showNotification('Chart monitoring started', 'success');
}

function stopChartUpdates() {
    if (diagnosticsState.chartUpdateInterval) {
        clearInterval(diagnosticsState.chartUpdateInterval);
        diagnosticsState.chartUpdateInterval = null;
        window.showNotification('Chart monitoring stopped', 'info');
    }
}

// ==================== LOG STREAM FUNCTIONS ====================

async function startLogStream() {
    if (diagnosticsState.logStreamInterval) {
        clearInterval(diagnosticsState.logStreamInterval);
    }
    
    // Clear console for fresh stream
    const logConsole = document.getElementById('log-console');
    if (logConsole) logConsole.innerHTML = '';
    
    const fetchLogs = async () => {
        if (!diagnosticsState.liveLogsEnabled) return;
        
        const selectedLevel = document.getElementById('log-level')?.value || 'All Levels';
        try {
            const isLive = diagnosticsState.liveLogsEnabled;
            const response = await fetch(`/api/network/logs?level=${encodeURIComponent(selectedLevel)}${isLive ? '' : '&limit=10'}`);
            if (response.ok) {
                const data = await response.json();
                const logs = Array.isArray(data) ? data : (data.logs || []);
                if (logConsole) {
                    logConsole.innerHTML = '';
                    logs.forEach(log => addLogEntry(log));
                } else {
                }
            } else {
            }
        } catch (error) {
        }
    };

    // Immediate first call
    await fetchLogs();
    
    // Repeat every 5 seconds
    diagnosticsState.logStreamInterval = setInterval(fetchLogs, 5000);
    window.showNotification('Live log stream started', 'success');
}

async function loadNetworkMonitorState() {
    try {
        const res = await fetch('/api/network/settings');
        if (res.ok) {
            const settings = await res.json();
            updateNetworkToggleUI(settings.enabled);
        }
    } catch (e) {
    }
}

async function toggleNetworkMonitor() {
    try {
        const res = await fetch('/api/network/settings');
        if (!res.ok) return;
        const settings = await res.json();
        const newEnabled = !settings.enabled;

        const putRes = await fetch('/api/network/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...settings, enabled: newEnabled })
        });

        if (putRes.ok) {
            updateNetworkToggleUI(newEnabled);
            
            // Auto-start live stream if monitor was started
            if (newEnabled && !diagnosticsState.liveLogsEnabled) {
                diagnosticsState.liveLogsEnabled = true;
                const toggle = document.getElementById('liveStream');
                if (toggle) toggle.checked = true;
                startLogStream();
            }
            
            window.showNotification(
                `Network monitor ${newEnabled ? 'started' : 'stopped'}`, 
                newEnabled ? 'success' : 'info'
            );
        }
    } catch (e) {
        window.showNotification('Failed to toggle network monitor', 'error');
    }
}

function updateNetworkToggleUI(enabled) {
    const btn = document.getElementById('network-monitor-toggle-btn');
    if (!btn) return;
    if (enabled) {
        btn.innerHTML = '<i class="fa-solid fa-stop mr-1"></i> Stop Network Monitor';
        btn.classList.remove('bg-emerald-600', 'hover:bg-emerald-700');
        btn.classList.add('bg-red-600', 'hover:bg-red-700');
    } else {
        btn.innerHTML = '<i class="fa-solid fa-play mr-1"></i> Start Network Monitor';
        btn.classList.remove('bg-red-600', 'hover:bg-red-700');
        btn.classList.add('bg-emerald-600', 'hover:bg-emerald-700');
    }
}

function stopLogStream() {
    if (diagnosticsState.logStreamInterval) {
        clearInterval(diagnosticsState.logStreamInterval);
        diagnosticsState.logStreamInterval = null;
        
        // Reset to placeholder
        const logConsole = document.getElementById('log-console');
        if (logConsole) {
            logConsole.innerHTML = '<div class="text-slate-500 italic">Enable Live Stream to start receiving network logs.</div>';
        }
        
        window.showNotification('Live log stream stopped', 'info');
    }
}

// ==================== DIAGNOSTIC TOOLS FUNCTIONS ====================

function setCaptureDuration(seconds) {
    const customDuration = document.getElementById('customDuration');
    if (customDuration) {
        customDuration.value = seconds;
    }
    window.showNotification(`Capture duration set to ${seconds} seconds`, 'info');
}

function updateBufferValue(value) {
    const bufferValue = document.getElementById('bufferValue');
    if (bufferValue) {
        bufferValue.textContent = `${value} MB`;
    }
}

function updateSensitivityValue(value) {
    const sensitivityValue = document.getElementById('sensitivityValue');
    if (sensitivityValue) {
        sensitivityValue.textContent = `${value} dBm`;
    }
}

function clearSerialConsole() {
    const console = document.getElementById('serial-console');
    if (console) {
        console.innerHTML = '<div>> Console cleared</div>';
        window.showNotification('Serial console cleared', 'info');
    }
}

function exportRFScan() {
    window.showNotification('RF scan data exported successfully', 'success');
}

function startPacketCapture() {
    if (diagnosticsState.packetCaptureActive) {
        window.showNotification('Packet capture already active', 'warning');
        return;
    }
    
    diagnosticsState.packetCaptureActive = true;
    
    // Update button state
    const startBtn = document.getElementById('start-capture-btn');
    if (startBtn) {
        startBtn.innerHTML = '<i class="fa-solid fa-stop mr-2"></i> Stop Capture';
        startBtn.classList.remove('bg-primary');
        startBtn.classList.add('bg-red-500', 'hover:bg-red-600');
        startBtn.onclick = stopPacketCapture;
    }
    
    window.showNotification('Packet capture started...', 'info');
    
    // Simulate capture progress
    setTimeout(() => {
        // Simulate finding packets
        window.showNotification('Capturing packets... 15% complete', 'info');
    }, 1000);
    
    setTimeout(() => {
        window.showNotification('Capturing packets... 45% complete', 'info');
    }, 2000);
    
    setTimeout(() => {
        diagnosticsState.packetCaptureActive = false;
        
        // Reset button state
        if (startBtn) {
            startBtn.innerHTML = '<i class="fa-solid fa-play mr-2"></i> Start Capture';
            startBtn.classList.remove('bg-red-500', 'hover:bg-red-600');
            startBtn.classList.add('bg-primary', 'hover:bg-primaryHover');
            startBtn.onclick = startPacketCapture;
        }
        
        window.showNotification('Packet capture completed. 1.2MB captured.', 'success');
    }, 3000);
}

function stopPacketCapture() {
    if (!diagnosticsState.packetCaptureActive) return;
    
    diagnosticsState.packetCaptureActive = false;
    
    const startBtn = document.getElementById('start-capture-btn');
    if (startBtn) {
        startBtn.innerHTML = '<i class="fa-solid fa-play mr-2"></i> Start Capture';
        startBtn.classList.remove('bg-red-500', 'hover:bg-red-600');
        startBtn.classList.add('bg-primary', 'hover:bg-primaryHover');
        startBtn.onclick = startPacketCapture;
    }
    
    window.showNotification('Packet capture stopped', 'info');
}

function connectSerial() {
    if (diagnosticsState.serialConnected) {
        window.showNotification('Serial port already connected', 'info');
        return;
    }
    
    diagnosticsState.serialConnected = true;
    
    // Update button state
    const connectBtn = document.getElementById('connect-serial-btn');
    if (connectBtn) {
        connectBtn.innerHTML = '<i class="fa-solid fa-plug-circle-xmark mr-2"></i> Disconnect Serial';
        connectBtn.classList.remove('bg-primary');
        connectBtn.classList.add('bg-red-500', 'hover:bg-red-600');
        connectBtn.onclick = disconnectSerial;
    }
    
    window.showNotification('Serial port connected', 'success');
    
    // Add sample serial data
    setTimeout(() => {
        const console = document.getElementById('serial-console');
        if (console) {
            const newEntry = document.createElement('div');
            newEntry.textContent = '> Received: 01 03 00 00 00 02 C4 0B';
            console.appendChild(newEntry);
            console.scrollTop = console.scrollHeight;
        }
    }, 1000);
}

function disconnectSerial() {
    if (!diagnosticsState.serialConnected) return;
    
    diagnosticsState.serialConnected = false;
    
    const connectBtn = document.getElementById('connect-serial-btn');
    if (connectBtn) {
        connectBtn.innerHTML = '<i class="fa-solid fa-plug mr-2"></i> Connect Serial';
        connectBtn.classList.remove('bg-red-500', 'hover:bg-red-600');
        connectBtn.classList.add('bg-primary', 'hover:bg-primaryHover');
        connectBtn.onclick = connectSerial;
    }
    
    window.showNotification('Serial port disconnected', 'info');
}

function startRFScan() {
    if (diagnosticsState.rfScanning) {
        window.showNotification('RF scan already in progress', 'warning');
        return;
    }
    
    diagnosticsState.rfScanning = true;
    
    // Update button state
    const scanBtn = document.getElementById('start-rf-scan-btn');
    if (scanBtn) {
        scanBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Scanning...';
        scanBtn.disabled = true;
    }
    
    window.showNotification('RF scan started...', 'info');
    
    // Simulate scan progress
    setTimeout(() => {
        window.showNotification('Scanning 433MHz band... 33% complete', 'info');
    }, 1000);
    
    setTimeout(() => {
        window.showNotification('Scanning 433MHz band... 66% complete', 'info');
    }, 2000);
    
    setTimeout(() => {
        diagnosticsState.rfScanning = false;
        
        // Update results
        const results = document.getElementById('rf-results');
        if (results) {
            results.innerHTML = `
                <div class="text-xs text-emerald-600">433.1 MHz: -92 dBm (Clear)</div>
                <div class="text-xs text-emerald-600">433.2 MHz: -88 dBm (Clear)</div>
                <div class="text-xs font-medium text-amber-600">433.3 MHz: -45 dBm (BUSY)</div>
                <div class="text-xs text-emerald-600">433.4 MHz: -78 dBm (Clear)</div>
                <div class="text-xs text-emerald-600">433.5 MHz: -85 dBm (Clear)</div>
            `;
        }
        
        // Reset button
        if (scanBtn) {
            scanBtn.innerHTML = '<i class="fa-solid fa-satellite-dish mr-2"></i> Start RF Scan';
            scanBtn.disabled = false;
        }
        
        window.showNotification('RF scan completed', 'success');
    }, 3000);
}

function showCaptureSettings() {
    window.showNotification('Capture settings modal would open here', 'info');
    // This would open a modal with advanced capture settings
}

// ==================== AUTO UPDATES CONTROL ====================

function startAllAutoUpdates() {
    if (diagnosticsState.autoUpdatesActive) {
        window.showNotification('Auto updates already active', 'info');
        return;
    }
    
    diagnosticsState.autoUpdatesActive = true;
    
    // Start all monitoring features
    startChartUpdates();
    
    // Enable live logs if toggle is on
    const liveStreamToggle = document.getElementById('liveStream');
    if (liveStreamToggle && liveStreamToggle.checked) {
        startLogStream();
    }
    
    // Update UI
    const startBtn = document.getElementById('start-auto-btn');
    const stopBtn = document.getElementById('stop-auto-btn');
    
    if (startBtn) {
        startBtn.disabled = true;
        startBtn.classList.add('opacity-50');
    }
    
    if (stopBtn) {
        stopBtn.disabled = false;
        stopBtn.classList.remove('opacity-50');
    }
    
    window.showNotification('All auto-updates started', 'success');
}

function stopAllAutoUpdates() {
    if (!diagnosticsState.autoUpdatesActive) {
        window.showNotification('Auto updates not active', 'info');
        return;
    }
    
    diagnosticsState.autoUpdatesActive = false;
    
    // Stop all monitoring features
    stopChartUpdates();
    stopLogStream();
    
    // Update UI
    const startBtn = document.getElementById('start-auto-btn');
    const stopBtn = document.getElementById('stop-auto-btn');
    
    if (startBtn) {
        startBtn.disabled = false;
        startBtn.classList.remove('opacity-50');
    }
    
    if (stopBtn) {
        stopBtn.disabled = true;
        stopBtn.classList.add('opacity-50');
    }
    
    window.showNotification('All auto-updates stopped', 'info');
}

// ==================== FOOTER ACTIONS ====================

function runQuickDiagnostics() {
    window.showNotification('Running quick diagnostics...', 'info');
    
    // Simulate diagnostic checks
    setTimeout(() => {
        window.showNotification('✓ Network connectivity: OK', 'success');
    }, 500);
    
    setTimeout(() => {
        window.showNotification('✓ Modbus devices: 3 found', 'success');
    }, 1000);
    
    setTimeout(() => {
        window.showNotification('✓ RF signal: Good (-65dBm)', 'success');
    }, 1500);
    
    setTimeout(() => {
        window.showNotification('✓ System resources: Normal', 'success');
    }, 2000);
    
    setTimeout(() => {
        window.showNotification('Diagnostics completed - All systems OK', 'success');
    }, 2500);
}

function saveDiagnosticsSettings() {
    window.showConfirmationDialog({
        message: 'Save all diagnostics configuration settings?',
        confirmText: 'Save',
        cancelText: 'Cancel'
    }).then(confirmed => {
        if (confirmed) {
            const saveBtn = document.getElementById('save-diagnostics-btn');
            const originalText = saveBtn.innerHTML;
            
            saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Saving...';
            saveBtn.disabled = true;
            
            setTimeout(() => {
                saveBtn.innerHTML = originalText;
                saveBtn.disabled = false;
                diagnosticsState.unsavedChanges = false;
                window.showNotification('Diagnostics settings saved successfully', 'success');
            }, 1500);
        }
    });
}

function markUnsavedChanges() {
    diagnosticsState.unsavedChanges = true;
    
    // Update save button to indicate unsaved changes
    const saveBtn = document.getElementById('save-diagnostics-btn');
    if (saveBtn) {
        saveBtn.classList.add('bg-amber-500', 'hover:bg-amber-600');
        saveBtn.classList.remove('bg-primary', 'hover:bg-primaryHover');
    }
}

// ==================== CLEANUP ====================

function cleanupDiagnostics() {
    
    // Cleanup all intervals
    if (diagnosticsState.sessionTimer) {
        clearInterval(diagnosticsState.sessionTimer);
        diagnosticsState.sessionTimer = null;
    }
    
    if (diagnosticsState.logStreamInterval) {
        clearInterval(diagnosticsState.logStreamInterval);
        diagnosticsState.logStreamInterval = null;
    }
    
    if (diagnosticsState.chartUpdateInterval) {
        clearInterval(diagnosticsState.chartUpdateInterval);
        diagnosticsState.chartUpdateInterval = null;
    }
    
    // Reset all active states
    diagnosticsState.terminalConnected = false;
    diagnosticsState.liveLogsEnabled = false;
    diagnosticsState.serialConnected = false;
    diagnosticsState.rfScanning = false;
    diagnosticsState.packetCaptureActive = false;
    diagnosticsState.autoUpdatesActive = false;
    
    // Cleanup charts
    if (diagnosticsState.charts.cpu) {
        Plotly.purge('chart-cpu');
    }
    if (diagnosticsState.charts.rf) {
        Plotly.purge('chart-rf');
    }
    if (diagnosticsState.charts.net) {
        Plotly.purge('chart-net');
    }
    
}

// Add cleanup to window unload
window.addEventListener('beforeunload', cleanupDiagnostics);

// Export cleanup function for router
window.cleanupDiagnostics = cleanupDiagnostics;