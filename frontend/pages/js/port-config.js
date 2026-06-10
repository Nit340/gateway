(function() {
    if (window._portConfigInitialized) return;

    const PortConfig = {
        ports: [],

        init: async function() {
            if (window._portConfigInitializing) return;
            window._portConfigInitializing = true;
            
            console.log("PortConfig initializing...");
            await this.loadPorts();
            this.bindEvents();
            
            window._portConfigInitialized = true;
            window._portConfigInitializing = false;
        },

        loadPorts: async function() {
            try {
                const response = await fetch('/api/port-config?type=external');
                const data = await response.json();
                if (data.success) {
                    this.ports = data.ports;
                    this.renderPorts();
                } else {
                    if (typeof showNotification === 'function') {
                        showNotification('Failed to load port configuration', 'error');
                    }
                }
            } catch (error) {
                console.error('Error loading ports:', error);
                if (typeof showNotification === 'function') {
                    showNotification('Network error loading ports', 'error');
                }
            }
        },

        renderPorts: function() {
            if (!this.ports || !this.ports.length) return;
            
            this.ports.forEach(port => {
                const num = port.port_number;
                const prefix = `port-${num}`;
                
                const labelEl = document.getElementById(`${prefix}-label`);
                const baudEl = document.getElementById(`${prefix}-baud`);
                const dataBitsEl = document.getElementById(`${prefix}-data-bits`);
                const parityEl = document.getElementById(`${prefix}-parity`);
                const stopBitsEl = document.getElementById(`${prefix}-stop-bits`);
                const respTimeoutEl = document.getElementById(`${prefix}-resp-timeout`);
                const byteTimeoutEl = document.getElementById(`${prefix}-byte-timeout`);
                const maxRetriesEl = document.getElementById(`${prefix}-max-retries`);
                const pollIntervalEl = document.getElementById(`${prefix}-poll-interval`);
                const pathEl = document.getElementById(`${prefix}-path`);

                if (labelEl) labelEl.value = port.label || '';
                if (baudEl) baudEl.value = port.baud_rate || 9600;
                if (dataBitsEl) dataBitsEl.value = port.data_bits || 8;
                if (parityEl) parityEl.value = port.parity || 'N';
                if (stopBitsEl) stopBitsEl.value = port.stop_bits || 1;
                if (respTimeoutEl) respTimeoutEl.value = port.response_timeout_ms || 100;
                if (byteTimeoutEl) byteTimeoutEl.value = port.byte_timeout_ms || 100;
                if (maxRetriesEl) maxRetriesEl.value = port.max_retries || 2;
                if (pollIntervalEl) pollIntervalEl.value = port.polling_interval_ms || 300;
                if (pathEl) pathEl.textContent = port.port_value;
            });
        },

        bindEvents: function() {
            document.querySelectorAll('.save-port-btn').forEach(btn => {
                btn.onclick = (e) => {
                    const portNum = e.currentTarget.dataset.port;
                    this.savePort(portNum);
                };
            });

            const refreshBtn = document.getElementById('refresh-ports');
            if (refreshBtn) {
                refreshBtn.onclick = () => this.loadPorts();
            }
        },

        savePort: async function(portNum) {
            const prefix = `port-${portNum}`;
            const port = this.ports.find(p => p.port_number == portNum);
            if (!port) {
                console.error("Port object not found for number:", portNum);
                return;
            }

            const config = {
                id: port.id,
                label: document.getElementById(`${prefix}-label`).value,
                baud_rate: parseInt(document.getElementById(`${prefix}-baud`).value),
                data_bits: parseInt(document.getElementById(`${prefix}-data-bits`).value),
                parity: document.getElementById(`${prefix}-parity`).value,
                stop_bits: parseInt(document.getElementById(`${prefix}-stop-bits`).value),
                response_timeout_ms: parseInt(document.getElementById(`${prefix}-resp-timeout`).value),
                byte_timeout_ms: parseInt(document.getElementById(`${prefix}-byte-timeout`).value),
                max_retries: parseInt(document.getElementById(`${prefix}-max-retries`).value),
                polling_interval_ms: parseInt(document.getElementById(`${prefix}-poll-interval`).value)
            };

            try {
                const response = await fetch('/api/port-config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
                const result = await response.json();
                if (result.success) {
                    this.showAlert();
                    if (typeof showNotification === 'function') {
                        showNotification(`Port ${portNum} configuration saved`, 'success');
                    }
                } else {
                    if (typeof showNotification === 'function') {
                        showNotification(result.message || 'Save failed', 'error');
                    }
                }
            } catch (error) {
                console.error('Error saving port:', error);
                if (typeof showNotification === 'function') {
                    showNotification('Network error saving port', 'error');
                }
            }
        },

        showAlert: function() {
            const alert = document.getElementById('port-save-alert');
            if (alert) {
                alert.classList.remove('hidden');
                setTimeout(() => alert.classList.add('hidden'), 5000);
            }
        }
    };

    window.PortConfig = PortConfig;
    
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        PortConfig.init();
    } else {
        document.addEventListener('DOMContentLoaded', () => PortConfig.init());
    }
})();
