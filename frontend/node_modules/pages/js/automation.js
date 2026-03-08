// pages/js/automation.js - Clean version with script reload protection

// Check if already loaded to prevent duplicate declarations
if (typeof window.automationLoaded === 'undefined') {
    window.automationLoaded = true;
    
    // ==================== APPLICATION STATE ====================
    let appState = {
        jobs: [],
        executionHistory: [],
        tags: [],
        editingJobId: null,
        unsavedChanges: false,
        maxConcurrentJobs: 5,
        cpuUsage: 45
    };

    // ==================== HELPER FUNCTIONS ====================
    const setInputValue = function(selector, value) {
        if (value === undefined || value === null) return;
        const element = document.querySelector(selector);
        if (element) element.value = value;
    };

    const setRadioValue = function(selector, value) {
        if (value === undefined || value === null) return;
        const radios = document.querySelectorAll(selector);
        radios.forEach(radio => {
            if (radio.value === value) {
                radio.checked = true;
                radio.dispatchEvent(new Event('change'));
            }
        });
    };

    const setCheckboxValues = function(selector, values) {
        if (!values || !Array.isArray(values)) return;
        const checkboxes = document.querySelectorAll(selector);
        checkboxes.forEach(checkbox => {
            checkbox.checked = values.includes(checkbox.value);
        });
    };

    const getInputValue = function(selector) {
        const element = document.querySelector(selector);
        return element ? element.value : '';
    };

    const getRadioValue = function(selector) {
        const radio = document.querySelector(selector + ':checked');
        return radio ? radio.value : '';
    };

    const getCheckboxValues = function(selector) {
        const checkboxes = document.querySelectorAll(selector + ':checked');
        return Array.from(checkboxes).map(cb => cb.value);
    };

    const getSelectValue = function(selector) {
        const select = document.querySelector(selector);
        return select ? select.options[select.selectedIndex].value : '';
    };

    // ==================== NOTIFICATION SYSTEM ====================
    const showNotification = function(message, type = 'info') {
        // Remove existing notifications
        const existingNotifications = document.querySelectorAll('.notification-toast');
        existingNotifications.forEach(notification => {
            notification.remove();
        });
        
        // Create notification element
        const notification = document.createElement('div');
        notification.className = 'notification-toast fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg border transition-all duration-300 transform translate-x-0 opacity-100';
        
        // Set styles based on type
        const typeStyles = {
            success: 'bg-emerald-50 text-emerald-800 border-emerald-200',
            error: 'bg-red-50 text-red-800 border-red-200',
            warning: 'bg-amber-50 text-amber-800 border-amber-200',
            info: 'bg-blue-50 text-blue-800 border-blue-200'
        };
        
        notification.className += ' ' + (typeStyles[type] || typeStyles.info);
        
        // Add icon based on type
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        
        notification.innerHTML = `
            <div class="flex items-center">
                <i class="fa-solid ${icons[type] || icons.info} mr-2"></i>
                <span class="text-sm font-medium">${message}</span>
                <button class="ml-4 text-gray-500 hover:text-gray-700 close-notification">
                    <i class="fa-solid fa-times"></i>
                </button>
            </div>
        `;
        
        // Add to document
        document.body.appendChild(notification);
        
        // Add close handler
        const closeBtn = notification.querySelector('.close-notification');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                notification.remove();
            });
        }
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.classList.add('fade-out');
                setTimeout(() => notification.remove(), 300);
            }
        }, 5000);
    };

    // ==================== MODAL FUNCTIONS ====================
    const showModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    };

    const closeModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = 'auto';
        }
    };

    // ==================== JOB MANAGEMENT ====================
    const loadInitialData = function() {
        // Mock data - in real app, this would come from API
        appState.jobs = [
            {
                id: 1,
                name: 'Modbus Poll',
                type: 'interval',
                schedule: '10 seconds',
                nextRun: '10 sec',
                action: 'Publish Modbus Data',
                status: 'enabled',
                enabled: true,
                tags: ['modbus', 'polling'],
                description: 'Poll Modbus devices every 10 seconds'
            },
            {
                id: 2,
                name: 'Daily Reset',
                type: 'daily',
                schedule: '00:00',
                nextRun: 'Tomorrow 00:00',
                action: 'Reset Counters',
                status: 'enabled',
                enabled: true,
                tags: ['reset', 'daily'],
                description: 'Reset daily counters at midnight'
            },
            {
                id: 3,
                name: 'Publish MQTT',
                type: 'cron',
                schedule: '15:30',
                nextRun: 'Today 15:30',
                action: 'Publish MQTT',
                status: 'disabled',
                enabled: false,
                tags: ['mqtt', 'publish'],
                description: 'Publish data to MQTT broker'
            },
            {
                id: 4,
                name: 'Health Check',
                type: 'hourly',
                schedule: '01:00',
                nextRun: 'Next hour',
                action: 'System Diagnostics',
                status: 'enabled',
                enabled: true,
                tags: ['health', 'diagnostics'],
                description: 'Run system health diagnostics'
            }
        ];
        
        appState.executionHistory = [
            {
                timestamp: '2025-06-12 02:00:01',
                job: 'Daily Export',
                trigger: 'Scheduled',
                duration: '14 sec',
                status: 'success',
                message: 'Export completed successfully'
            },
            {
                timestamp: '2025-06-12 01:00:00',
                job: 'Health Check',
                trigger: 'Scheduled',
                duration: '5 sec',
                status: 'success',
                message: 'All systems normal'
            },
            {
                timestamp: '2025-06-12 00:30:00',
                job: 'Modbus Poll',
                trigger: 'Interval',
                duration: '2 sec',
                status: 'success',
                message: 'Data collected successfully'
            },
            {
                timestamp: '2025-06-11 23:45:00',
                job: 'OTA Stage 1',
                trigger: 'Scheduled',
                duration: '57 sec',
                status: 'failed',
                message: 'Network timeout'
            }
        ];
        
        appState.tags = ['modbus', 'mqtt', 'export', 'cleanup', 'safety', 'diagnostics', 'polling', 'reset', 'daily', 'health'];
        
        renderJobsTable();
        renderHistoryTable();
        renderConflicts();
        updateStats();
        updateTagsDisplay();
    };

    const renderJobsTable = function() {
        const tbody = document.getElementById('jobTableBody');
        if (!tbody) return;
        
        tbody.innerHTML = '';
        
        appState.jobs.forEach(job => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-slate-50 transition';
            
            const typeClass = job.type;
            
            const statusBadge = job.enabled ? 
                'bg-green-100 text-green-800' : 
                'bg-slate-100 text-slate-800';
            
            row.innerHTML = `
                <td class="px-6 py-4 font-medium text-slate-900">
                    ${job.name}
                    <div class="flex flex-wrap gap-1 mt-1">
                        ${job.tags.map(tag => `
                            <span class="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">${tag}</span>
                        `).join('')}
                    </div>
                </td>
                <td class="px-6 py-4">
                    <span class="job-type-indicator job-type ${typeClass}"></span>
                    ${job.type.charAt(0).toUpperCase() + job.type.slice(1)}
                </td>
                <td class="px-6 py-4 text-slate-600">${job.schedule}</td>
                <td class="px-6 py-4 font-medium">${job.nextRun}</td>
                <td class="px-6 py-4 text-slate-600">${job.action}</td>
                <td class="px-6 py-4">
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusBadge}">
                        ${job.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                </td>
                <td class="px-6 py-4 text-right">
                    <div class="flex justify-end space-x-2">
                        <button class="text-slate-400 hover:text-primary transition-colors" onclick="window.toggleJob(${job.id})" title="${job.enabled ? 'Disable' : 'Enable'}">
                            <i class="fa-solid fa-power-off ${!job.enabled ? 'text-slate-300' : ''}"></i>
                        </button>
                        <button class="text-slate-400 hover:text-primary transition-colors" onclick="window.editJob(${job.id})" title="Edit">
                            <i class="fa-solid fa-pen-to-square"></i>
                        </button>
                        <button class="text-slate-400 hover:text-primary transition-colors" onclick="window.runJobNow(${job.id})" title="Run Now">
                            <i class="fa-solid fa-play"></i>
                        </button>
                    </div>
                </td>
            `;
            tbody.appendChild(row);
        });
    };

    const renderHistoryTable = function() {
        const tbody = document.getElementById('historyTableBody');
        if (!tbody) return;
        
        tbody.innerHTML = '';
        
        appState.executionHistory.forEach(history => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-slate-50 transition';
            
            const statusColor = history.status === 'success' ? 
                'bg-green-100 text-green-800' : 
                history.status === 'running' ?
                'bg-blue-100 text-blue-800' :
                'bg-red-100 text-red-800';
            
            row.innerHTML = `
                <td class="px-6 py-4 font-mono text-sm">${history.timestamp}</td>
                <td class="px-6 py-4 font-medium">${history.job}</td>
                <td class="px-6 py-4 text-slate-600">${history.trigger}</td>
                <td class="px-6 py-4">${history.duration}</td>
                <td class="px-6 py-4">
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColor}">
                        ${history.status.charAt(0).toUpperCase() + history.status.slice(1)}
                    </span>
                </td>
                <td class="px-6 py-4 text-slate-600">${history.message}</td>
            `;
            tbody.appendChild(row);
        });
    };

    const renderConflicts = function() {
        const conflictsList = document.getElementById('conflicts-list');
        if (!conflictsList) return;
        
        // Simple conflict detection
        const scheduledTimes = {};
        const conflicts = [];
        
        appState.jobs.forEach(job => {
            if (job.enabled && job.schedule) {
                if (scheduledTimes[job.schedule]) {
                    conflicts.push({
                        job1: scheduledTimes[job.schedule],
                        job2: job.name,
                        time: job.schedule
                    });
                } else {
                    scheduledTimes[job.schedule] = job.name;
                }
            }
        });
        
        if (conflicts.length > 0) {
            conflictsList.innerHTML = conflicts.map(conflict => `
                <div class="flex items-center justify-between p-2 bg-white border border-slate-200 rounded">
                    <div>
                        <p class="text-sm font-medium text-slate-900">${conflict.job1} & ${conflict.job2}</p>
                        <p class="text-xs text-slate-500">Both scheduled for ${conflict.time}</p>
                    </div>
                    <span class="text-xs text-amber-600 font-medium">Warning</span>
                </div>
            `).join('');
        } else {
            conflictsList.innerHTML = '<p class="text-sm text-slate-500">No conflicts detected</p>';
        }
    };

    const updateStats = function() {
        const totalJobs = document.getElementById('total-jobs');
        const enabledJobs = document.getElementById('enabled-jobs');
        const disabledJobs = document.getElementById('disabled-jobs');
        const activeJobsCount = document.getElementById('active-jobs-count');
        
        if (totalJobs) totalJobs.textContent = appState.jobs.length;
        if (enabledJobs) enabledJobs.textContent = appState.jobs.filter(j => j.enabled).length;
        if (disabledJobs) disabledJobs.textContent = appState.jobs.filter(j => !j.enabled).length;
        if (activeJobsCount) activeJobsCount.textContent = appState.jobs.filter(j => j.enabled).length;
        
        // Update resource bars
        const concurrentJobsBar = document.getElementById('concurrent-jobs-bar');
        const currentConcurrentJobs = document.getElementById('current-concurrent-jobs');
        const maxConcurrentJobs = document.getElementById('max-concurrent-jobs');
        const cpuUsageBar = document.getElementById('cpu-usage-bar');
        const cpuUsageSpan = document.getElementById('cpu-usage');
        
        if (concurrentJobsBar) {
            const runningJobs = appState.executionHistory.filter(h => h.status === 'running').length;
            const percent = (runningJobs / appState.maxConcurrentJobs) * 100;
            concurrentJobsBar.style.width = percent + '%';
            if (currentConcurrentJobs) currentConcurrentJobs.textContent = runningJobs;
            if (maxConcurrentJobs) maxConcurrentJobs.textContent = appState.maxConcurrentJobs;
        }
        
        if (cpuUsageBar && cpuUsageSpan) {
            cpuUsageBar.style.width = appState.cpuUsage + '%';
            cpuUsageSpan.textContent = appState.cpuUsage;
        }
    };

    const updateTagsDisplay = function() {
        const container = document.getElementById('selectedTags');
        if (!container) return;
        
        container.innerHTML = '';
        
        appState.tags.forEach(tag => {
            const span = document.createElement('span');
            span.className = 'inline-flex items-center bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded mr-1 mb-1';
            span.innerHTML = `
                ${tag}
                <button class="ml-1 text-blue-600 hover:text-blue-800" onclick="window.removeTag('${tag}')">
                    <i class="fa-solid fa-times text-xs"></i>
                </button>
            `;
            container.appendChild(span);
        });
    };

    // ==================== JOB ACTIONS ====================
    const createNewJob = function() {
        appState.editingJobId = null;
        const modalTitle = document.getElementById('modalTitle');
        const deleteBtn = document.getElementById('deleteJobBtn');
        const runNowBtn = document.getElementById('runNowBtn');
        
        if (modalTitle) modalTitle.textContent = 'Create Scheduled Job';
        if (deleteBtn) deleteBtn.style.display = 'none';
        if (runNowBtn) runNowBtn.style.display = 'inline-block';
        
        resetJobForm();
        showModal('createJobModal');
    };

    const editJob = function(jobId) {
        const job = appState.jobs.find(j => j.id === jobId);
        if (!job) return;
        
        appState.editingJobId = jobId;
        const modalTitle = document.getElementById('modalTitle');
        const deleteBtn = document.getElementById('deleteJobBtn');
        const runNowBtn = document.getElementById('runNowBtn');
        
        if (modalTitle) modalTitle.textContent = 'Edit Scheduled Job';
        if (deleteBtn) deleteBtn.style.display = 'inline-block';
        if (runNowBtn) runNowBtn.style.display = 'inline-block';
        
        // Populate form with job data
        setInputValue('#jobName', job.name);
        setInputValue('#jobDescription', job.description || '');
        
        // Set job type
        setRadioValue('input[name="jobType"]', job.type);
        showTriggerConfig(job.type);
        
        // Set tags
        appState.tags = [...job.tags];
        updateTagsDisplay();
        
        // Set action type (default to publish)
        setRadioValue('input[name="actionType"]', 'publish');
        showActionConfig('publish');
        
        showModal('createJobModal');
    };

    const saveJob = function() {
        const jobName = getInputValue('#jobName').trim();
        if (!jobName) {
            showNotification('Please enter a job name', 'error');
            return;
        }
        
        const jobType = getRadioValue('input[name="jobType"]');
        const actionType = getRadioValue('input[name="actionType"]');
        
        const jobData = {
            name: jobName,
            type: jobType,
            description: getInputValue('#jobDescription'),
            actionType: actionType,
            enabled: true,
            tags: [...appState.tags],
            schedule: getScheduleDisplay(jobType),
            nextRun: getNextRunDisplay(jobType),
            action: getActionDisplay(actionType)
        };
        
        if (appState.editingJobId) {
            // Update existing job
            const index = appState.jobs.findIndex(j => j.id === appState.editingJobId);
            if (index !== -1) {
                appState.jobs[index] = { ...appState.jobs[index], ...jobData };
                showNotification('Job updated successfully', 'success');
            }
        } else {
            // Create new job
            const newJob = {
                id: appState.jobs.length > 0 ? Math.max(...appState.jobs.map(j => j.id)) + 1 : 1,
                ...jobData,
                status: 'enabled'
            };
            appState.jobs.push(newJob);
            showNotification('Job created successfully', 'success');
        }
        
        renderJobsTable();
        renderConflicts();
        updateStats();
        closeModal('createJobModal');
        markUnsavedChanges();
    };

    const deleteJob = function() {
        if (!appState.editingJobId) return;
        
        if (confirm('Are you sure you want to delete this job?')) {
            appState.jobs = appState.jobs.filter(j => j.id !== appState.editingJobId);
            renderJobsTable();
            renderConflicts();
            updateStats();
            closeModal('createJobModal');
            showNotification('Job deleted successfully', 'success');
            markUnsavedChanges();
        }
    };

    const toggleJob = function(jobId) {
        const job = appState.jobs.find(j => j.id === jobId);
        if (!job) return;
        
        job.enabled = !job.enabled;
        job.status = job.enabled ? 'enabled' : 'disabled';
        renderJobsTable();
        showNotification(`Job ${job.enabled ? 'enabled' : 'disabled'}`, 'success');
        markUnsavedChanges();
    };

    const runJobNow = function(jobId = null) {
        if (jobId) {
            const job = appState.jobs.find(j => j.id === jobId);
            if (job) {
                showNotification(`Running job: ${job.name}`, 'info');
                // Add to execution history
                const historyEntry = {
                    timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
                    job: job.name,
                    trigger: 'Manual',
                    duration: '0 sec',
                    status: 'running',
                    message: 'Job started manually'
                };
                appState.executionHistory.unshift(historyEntry);
                if (appState.executionHistory.length > 50) {
                    appState.executionHistory.pop();
                }
                renderHistoryTable();
                
                // Simulate job completion after 2 seconds
                setTimeout(() => {
                    historyEntry.status = 'success';
                    historyEntry.duration = '2 sec';
                    historyEntry.message = 'Job completed successfully';
                    renderHistoryTable();
                    updateStats();
                }, 2000);
            }
        } else {
            showNotification('Please select a job to run', 'warning');
        }
    };

    // ==================== FORM HANDLING ====================
    const resetJobForm = function() {
        setInputValue('#jobName', '');
        setInputValue('#jobDescription', '');
        setRadioValue('input[name="jobType"]', 'daily');
        setRadioValue('input[name="actionType"]', 'publish');
        showTriggerConfig('daily');
        showActionConfig('publish');
        appState.tags = [];
        updateTagsDisplay();
    };

    const showTriggerConfig = function(type) {
        // Hide all trigger configs
        document.querySelectorAll('.trigger-config').forEach(el => {
            el.classList.add('hidden');
        });
        
        // Show selected trigger config
        const configId = type + 'Config';
        const configElement = document.getElementById(configId);
        if (configElement) {
            configElement.classList.remove('hidden');
        }
    };

    const showActionConfig = function(type) {
        // Hide all action configs
        document.querySelectorAll('.action-config-section').forEach(el => {
            el.classList.remove('active');
        });
        
        // Show selected action config
        const configId = type + 'Action';
        const configElement = document.getElementById(configId);
        if (configElement) {
            configElement.classList.add('active');
        }
    };

    const generateCronExpression = function() {
        // Simple cron generator for common patterns
        const cronExamples = [
            '0 * * * *',    // Every hour
            '0 0 * * *',    // Daily at midnight
            '0 6 * * *',    // Daily at 6 AM
            '0 9,17 * * *', // 9 AM and 5 PM daily
            '*/5 * * * *',  // Every 5 minutes
            '0 0 * * 0',    // Weekly on Sunday
        ];
        
        const randomCron = cronExamples[Math.floor(Math.random() * cronExamples.length)];
        const cronInput = document.getElementById('cronExpression');
        if (cronInput) cronInput.value = randomCron;
    };

    const addTag = function() {
        const tagInput = document.getElementById('newTag');
        if (!tagInput) return;
        
        const tag = tagInput.value.trim().toLowerCase();
        
        if (!tag) {
            showNotification('Please enter a tag', 'error');
            return;
        }
        
        if (appState.tags.includes(tag)) {
            showNotification('Tag already exists', 'warning');
            return;
        }
        
        appState.tags.push(tag);
        updateTagsDisplay();
        tagInput.value = '';
        markUnsavedChanges();
    };

    const removeTag = function(tag) {
        appState.tags = appState.tags.filter(t => t !== tag);
        updateTagsDisplay();
        markUnsavedChanges();
    };

    // ==================== UTILITY FUNCTIONS ====================
    const getScheduleDisplay = function(type) {
        switch(type) {
            case 'interval': return 'Every 10 seconds';
            case 'daily': return 'Daily at 06:00';
            case 'weekly': return 'Weekly Mon,Tue,Thu at 12:30';
            case 'monthly': return 'Monthly on day 1 at 00:00';
            case 'cron': return 'Cron: 0 15 * * *';
            case 'sunrise': return 'Sunrise -30min';
            default: return 'Custom';
        }
    };

    const getNextRunDisplay = function(type) {
        switch(type) {
            case 'interval': return '10 seconds';
            case 'daily': return 'Tomorrow 06:00';
            case 'weekly': return 'Next Mon 12:30';
            case 'monthly': return 'Next month 1st';
            case 'cron': return 'Today 15:30';
            case 'sunrise': return 'Tomorrow sunrise';
            default: return 'Pending';
        }
    };

    const getActionDisplay = function(type) {
        switch(type) {
            case 'publish': return 'Publish Data';
            case 'log': return 'Log Message';
            case 'output': return 'Set Output';
            case 'rule': return 'Run Rule Engine';
            case 'file': return 'File Operation';
            case 'system': return 'System Action';
            default: return 'Custom Action';
        }
    };

    const checkConflicts = function() {
        renderConflicts();
        
        const conflicts = document.querySelectorAll('#conflicts-list .text-amber-600').length;
        
        if (conflicts > 0) {
            showNotification(`Found ${conflicts} potential conflict${conflicts > 1 ? 's' : ''}`, 'warning');
        } else {
            showNotification('No conflicts detected', 'success');
        }
    };

    const exportJobs = function() {
        const exportData = {
            jobs: appState.jobs,
            timestamp: new Date().toISOString(),
            version: '1.0'
        };
        
        const dataStr = JSON.stringify(exportData, null, 2);
        const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
        
        const exportFileDefaultName = `scheduler-jobs-${new Date().toISOString().split('T')[0]}.json`;
        
        const linkElement = document.createElement('a');
        linkElement.setAttribute('href', dataUri);
        linkElement.setAttribute('download', exportFileDefaultName);
        linkElement.click();
        
        showNotification('Jobs exported successfully', 'success');
    };

    const importJobs = function() {
        // Create file input element
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = '.json';
        
        fileInput.onchange = function(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            const reader = new FileReader();
            reader.onload = function(e) {
                try {
                    const imported = JSON.parse(e.target.result);
                    if (imported.jobs && Array.isArray(imported.jobs)) {
                        appState.jobs = imported.jobs;
                        renderJobsTable();
                        renderConflicts();
                        updateStats();
                        showNotification('Jobs imported successfully', 'success');
                        markUnsavedChanges();
                    } else {
                        showNotification('Invalid file format', 'error');
                    }
                } catch (error) {
                    showNotification('Error parsing file', 'error');
                }
            };
            reader.readAsText(file);
        };
        
        fileInput.click();
    };

    const runAllJobs = function() {
        if (confirm('Run all enabled jobs now?')) {
            showNotification('Running all jobs...', 'info');
            appState.jobs.filter(j => j.enabled).forEach(job => {
                runJobNow(job.id);
            });
        }
    };

    const resetAllJobs = function() {
        if (confirm('Reset all jobs to default settings?')) {
            showNotification('All jobs reset', 'info');
            // In real app, this would reset to defaults
        }
    };

    const disableAllJobs = function() {
        if (confirm('Disable all scheduled jobs?')) {
            appState.jobs.forEach(job => {
                job.enabled = false;
                job.status = 'disabled';
            });
            renderJobsTable();
            renderConflicts();
            updateStats();
            showNotification('All jobs disabled', 'success');
            markUnsavedChanges();
        }
    };

    const saveAllSettings = function() {
        const saveBtn = document.getElementById('save-btn');
        if (!saveBtn) return;
        
        const originalText = saveBtn.innerHTML;
        
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Saving...';
        saveBtn.disabled = true;
        
        // Simulate API call
        setTimeout(() => {
            saveBtn.innerHTML = originalText;
            saveBtn.disabled = false;
            
            appState.unsavedChanges = false;
            showNotification('All scheduler settings saved successfully', 'success');
        }, 1500);
    };

    const cancelChanges = function() {
        if (appState.unsavedChanges) {
            if (confirm('Discard all unsaved scheduler changes?')) {
                window.location.reload();
            }
        } else {
            window.location.reload();
        }
    };

    const showHelp = function() {
        showNotification('Opening scheduler documentation...', 'info');
    };

    const markUnsavedChanges = function() {
        appState.unsavedChanges = true;
        
        // Update save button
        const saveBtn = document.getElementById('save-btn');
        if (saveBtn && !saveBtn.disabled) {
            saveBtn.classList.add('bg-orange-500', 'hover:bg-orange-600');
        }
    };

    // ==================== LOAD CONFIGURATION ====================
    const loadConfiguration = async function() {
        try {
            // In a real app, this would fetch from API
            // const response = await fetch('/api/scheduler/jobs');
            // const config = await response.json();
            // populateFormWithConfig(config);
            
            // For now, use mock data
            loadInitialData();
            
            console.log('Automation configuration loaded');
            
        } catch (error) {
            console.error('Load error:', error);
            showNotification('Failed to load configuration', 'error');
        }
    };

    // ==================== INITIALIZATION ====================
    const initializeAutomation = function() {
        console.log('Automation module initializing...');
        
        // Set up event listeners
        setupEventListeners();
        
        // Load initial data
        loadConfiguration();
        
        console.log('Automation module initialized');
    };

    const setupEventListeners = function() {
        // Job type change listener
        document.querySelectorAll('input[name="jobType"]').forEach(radio => {
            radio.addEventListener('change', function() {
                showTriggerConfig(this.value);
                markUnsavedChanges();
            });
        });
        
        // Action type change listener
        document.querySelectorAll('input[name="actionType"]').forEach(radio => {
            radio.addEventListener('change', function() {
                showActionConfig(this.value);
                markUnsavedChanges();
            });
        });
        
        // Save button
        const saveBtn = document.getElementById('save-btn');
        if (saveBtn) {
            saveBtn.addEventListener('click', saveAllSettings);
        }
        
        // Export button
        const exportBtn = document.getElementById('export-btn');
        if (exportBtn) {
            exportBtn.addEventListener('click', exportJobs);
        }
        
        // Import button
        const importBtn = document.getElementById('import-btn');
        if (importBtn) {
            importBtn.addEventListener('click', importJobs);
        }
        
        // Run all button
        const runAllBtn = document.getElementById('run-all-btn');
        if (runAllBtn) {
            runAllBtn.addEventListener('click', runAllJobs);
        }
        
        // Form change listeners
        document.querySelectorAll('#createJobModal input, #createJobModal select, #createJobModal textarea').forEach(element => {
            element.addEventListener('change', markUnsavedChanges);
        });
        
        // Add tag on Enter key
        const newTagInput = document.getElementById('newTag');
        if (newTagInput) {
            newTagInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    addTag();
                }
            });
        }
    };

    // ==================== CLEANUP ====================
    const cleanupAutomation = function() {
        console.log('Cleaning up automation module...');
        
        // Remove event listeners if needed
        const saveBtn = document.getElementById('save-btn');
        if (saveBtn) {
            const newSaveBtn = saveBtn.cloneNode(true);
            saveBtn.parentNode.replaceChild(newSaveBtn, saveBtn);
        }
        
        // Clear any intervals/timeouts
        // (none in this module)
        
        console.log('Automation cleanup complete');
    };

    // ==================== EXPORT PUBLIC API ====================
    window.initAutomation = initializeAutomation;
    window.cleanupAutomation = cleanupAutomation;
    
    // Expose functions needed by HTML onclick handlers
    window.createNewJob = createNewJob;
    window.editJob = editJob;
    window.toggleJob = toggleJob;
    window.runJobNow = runJobNow;
    window.deleteJob = deleteJob;
    window.saveJob = saveJob;
    window.closeModal = closeModal;
    window.showModal = showModal;
    window.checkConflicts = checkConflicts;
    window.exportJobs = exportJobs;
    window.importJobs = importJobs;
    window.runAllJobs = runAllJobs;
    window.disableAllJobs = disableAllJobs;
    window.generateCronExpression = generateCronExpression;
    window.addTag = addTag;
    window.removeTag = removeTag;
    window.showHelp = showHelp;
}

// Export for module system
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initAutomation: window.initAutomation,
        loadConfiguration: loadConfiguration,
        saveAllSettings: saveAllSettings
    };
}