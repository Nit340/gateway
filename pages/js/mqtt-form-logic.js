// mqtt-form-logic.js
// Global variables for MQTT form
let mqttTopics = [];
let topicFormats = {};

// Initialize MQTT form
window.initializeMqttForm = function() {
    console.log('Initializing MQTT form');
    mqttTopics = [];
    topicFormats = {};
    
    // Generate random ID for client ID
    const randomId = Math.random().toString(36).substring(2, 8);
    const clientIdInput = document.getElementById('field-clientId');
    if (clientIdInput && clientIdInput.value.includes('${randomId}')) {
        clientIdInput.value = `univa-gateway-${randomId}`;
    }
    
    // Setup event listeners for toggle switches
    const batchingToggle = document.getElementById('field-enableBatching');
    const batchingOptions = document.getElementById('batching-options');
    if (batchingToggle && batchingOptions) {
        batchingToggle.addEventListener('change', function() {
            batchingOptions.style.display = this.checked ? 'block' : 'none';
        });
    }
    
    // Advanced tab toggle switches
    const lwtToggle = document.getElementById('field-advanced-enable-lwt');
    const lwtOptions = document.getElementById('advanced-lwt-options');
    if (lwtToggle && lwtOptions) {
        lwtToggle.addEventListener('change', function() {
            lwtOptions.style.display = this.checked ? 'block' : 'none';
        });
    }
    
    const compressionToggle = document.getElementById('field-advanced-enable-compression');
    const compressionOptions = document.getElementById('compression-options');
    if (compressionToggle && compressionOptions) {
        compressionToggle.addEventListener('change', function() {
            compressionOptions.style.display = this.checked ? 'block' : 'none';
        });
    }
    
    // Setup event listeners for publish mode radio buttons
    const publishModeRadios = document.querySelectorAll('input[name="field-publishMode"]');
    publishModeRadios.forEach(radio => {
        radio.addEventListener('change', updatePublishMode);
    });
    
    // Initialize topics and formats
    initializeTopicsAndFormats();
    
    // Initialize publish mode
    updatePublishMode();
    
    // Add event listeners to tag checkboxes for all tables
    setupTagCheckboxListeners();
    
    console.log('MQTT form initialized successfully');
};

// Initialize topics and formats
function initializeTopicsAndFormats() {
    // Load default topics
    updateTopicList();
    
    // Initialize topic format mappings
    updateTopicFormatMappings();
    
    // Populate sample data in publishing tables
    populateSamplePublishingData();
}

// Update the list of available topics
function updateTopicList() {
    const baseTopic = document.getElementById('field-baseTopic');
    if (!baseTopic) return;
    
    const baseTopicValue = baseTopic.value;
    const topics = [];
    
    // Add standard topics
    const standardTopics = [
        { id: 'telemetry', value: getValueById('field-telemetryTopic') },
        { id: 'alarm', value: getValueById('field-alarmTopic') },
        { id: 'event', value: getValueById('field-eventTopic') },
        { id: 'command', value: getValueById('field-commandTopic') }
    ];
    
    standardTopics.forEach(topic => {
        if (topic.value) {
            const fullTopic = baseTopicValue ? `${baseTopicValue}/${topic.value}` : topic.value;
            topics.push({
                id: topic.id,
                name: topic.value,
                fullTopic: fullTopic,
                type: 'standard'
            });
        }
    });
    
    // Add custom topics
    const customTopicInputs = document.querySelectorAll('#custom-topics-container input[type="text"]');
    customTopicInputs.forEach((input, index) => {
        if (input.value) {
            const fullTopic = baseTopicValue ? `${baseTopicValue}/${input.value}` : input.value;
            topics.push({
                id: `custom-${index}`,
                name: input.value,
                fullTopic: fullTopic,
                type: 'custom'
            });
        }
    });
    
    mqttTopics = topics;
    
    // Update topic dropdowns in publishing tables
    updateTopicDropdowns();
    
    // Update topic format mappings
    updateTopicFormatMappings();
}

function getValueById(id) {
    const element = document.getElementById(id);
    return element ? element.value : '';
}

// Update topic dropdowns in all publishing tables
function updateTopicDropdowns() {
    // Get topic options HTML
    const topicOptions = generateTopicOptions();
    
    // Update dropdowns in OnChange table
    const onchangeDropdowns = document.querySelectorAll('#mqtt-tags-table-onchange select.topic-select');
    onchangeDropdowns.forEach(dropdown => {
        dropdown.innerHTML = topicOptions;
    });
    
    // Update dropdowns in Periodic table
    const periodicDropdowns = document.querySelectorAll('#mqtt-tags-table-periodic select.topic-select');
    periodicDropdowns.forEach(dropdown => {
        dropdown.innerHTML = topicOptions;
    });
    
    // Update dropdowns in Event table
    const eventDropdowns = document.querySelectorAll('#mqtt-tags-table-event select.topic-select');
    eventDropdowns.forEach(dropdown => {
        dropdown.innerHTML = topicOptions;
    });
}

// Generate HTML options for topic dropdowns
function generateTopicOptions() {
    let options = '<option value="">-- Select Topic --</option>';
    
    mqttTopics.forEach(topic => {
        options += `<option value="${topic.fullTopic}">${topic.name} (${topic.fullTopic})</option>`;
    });
    
    // Add custom topic option
    options += '<option value="custom">Custom Topic...</option>';
    
    return options;
}

// Update all topic options when topics change
function updateAllTopicOptions() {
    updateTopicList();
}

// Add a custom topic
function addCustomTopic(type) {
    const topicInput = document.getElementById(`field-${type}Topic`);
    if (topicInput && topicInput.value) {
        // Add to custom topics container if not already there
        const existingTopics = Array.from(document.querySelectorAll('#custom-topics-container input')).map(input => input.value);
        if (!existingTopics.includes(topicInput.value)) {
            addCustomTopicItem(topicInput.value);
        }
    }
    updateTopicList();
}

// Add new custom topic
function addNewCustomTopic() {
    const container = document.getElementById('custom-topics-container');
    const div = document.createElement('div');
    div.className = 'custom-topic-item';
    div.innerHTML = `
        <div class="flex items-center gap-2">
            <input type="text" 
                   class="w-full compact-input"
                   placeholder="Enter topic name"
                   onchange="window.mqttFormLogic.updateAllTopicOptions()">
            <button type="button" class="compact-button border border-red-300 text-red-700 hover:bg-red-50" onclick="window.mqttFormLogic.removeCustomTopic(this)">
                <i class="fa-solid fa-trash"></i>
            </button>
        </div>
    `;
    container.appendChild(div);
    updateTopicList();
}

// Add custom topic item
function addCustomTopicItem(topicName) {
    const container = document.getElementById('custom-topics-container');
    const div = document.createElement('div');
    div.className = 'custom-topic-item';
    div.innerHTML = `
        <div class="flex items-center gap-2">
            <input type="text" 
                   class="w-full compact-input"
                   value="${topicName}"
                   onchange="window.mqttFormLogic.updateAllTopicOptions()">
            <button type="button" class="compact-button border border-red-300 text-red-700 hover:bg-red-50" onclick="window.mqttFormLogic.removeCustomTopic(this)">
                <i class="fa-solid fa-trash"></i>
            </button>
        </div>
    `;
    container.appendChild(div);
}

// Remove custom topic
function removeCustomTopic(button) {
    const item = button.closest('.custom-topic-item');
    if (item) {
        item.remove();
        updateTopicList();
    }
}

// Update topic format mappings
function updateTopicFormatMappings() {
    const container = document.getElementById('topic-format-mappings');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (mqttTopics.length === 0) {
        container.innerHTML = '<p class="text-xs text-slate-500">No topics configured yet</p>';
        return;
    }
    
    mqttTopics.forEach((topic, index) => {
        const div = document.createElement('div');
        div.className = 'flex items-center justify-between p-2 border border-slate-200 rounded';
        div.innerHTML = `
            <div>
                <span class="text-xs font-medium text-slate-700">${topic.name}</span>
                <p class="text-xs text-slate-500">${topic.fullTopic}</p>
            </div>
            <button type="button" 
                    onclick="window.mqttFormLogic.editTopicFormat('${topic.id}')"
                    class="compact-button border border-slate-300 text-slate-700 hover:bg-slate-50 text-xs">
                <i class="fa-solid fa-edit mr-1"></i> Edit Format
            </button>
        `;
        container.appendChild(div);
    });
}

// Edit topic format
function editTopicFormat(topicId) {
    const topic = mqttTopics.find(t => t.id === topicId);
    if (!topic) return;
    
    // Load existing format or create default
    const existingFormat = topicFormats[topicId] || getDefaultFormatForTopic(topic);
    
    const container = document.getElementById('format-templates-container');
    if (!container) return;
    
    container.innerHTML = `
        <div class="space-y-4">
            <div class="flex justify-between items-center">
                <h6 class="text-sm font-medium text-slate-700">Format for: ${topic.name}</h6>
                <button type="button" 
                        onclick="window.mqttFormLogic.closeFormatEditor()"
                        class="compact-button border border-slate-300 text-slate-700 hover:bg-slate-50 text-xs">
                    <i class="fa-solid fa-times mr-1"></i> Close
                </button>
            </div>
            
            <div>
                <label class="block text-xs font-medium text-slate-700 mb-1">Payload Format</label>
                <div class="radio-group">
                    <label class="radio-option">
                        <input type="radio" name="format-${topicId}-payload" value="json" ${existingFormat.payloadFormat === 'json' ? 'checked' : ''}>
                        <span class="text-xs">JSON</span>
                    </label>
                    <label class="radio-option">
                        <input type="radio" name="format-${topicId}-payload" value="csv" ${existingFormat.payloadFormat === 'csv' ? 'checked' : ''}>
                        <span class="text-xs">CSV</span>
                    </label>
                    <label class="radio-option">
                        <input type="radio" name="format-${topicId}-payload" value="keyvalue" ${existingFormat.payloadFormat === 'keyvalue' ? 'checked' : ''}>
                        <span class="text-xs">Key-Value Pairs</span>
                    </label>
                </div>
            </div>
            
            <div id="format-template-${topicId}">
                ${generateFormatTemplate(topicId, existingFormat)}
            </div>
            
            <div class="flex justify-end">
                <button type="button" 
                        onclick="window.mqttFormLogic.saveTopicFormat('${topicId}')"
                        class="compact-button bg-primary hover:bg-primaryHover text-white text-xs">
                    <i class="fa-solid fa-save mr-1"></i> Save Format
                </button>
            </div>
        </div>
    `;
    
    // Add event listener for payload format change
    const radios = container.querySelectorAll(`input[name="format-${topicId}-payload"]`);
    radios.forEach(radio => {
        radio.addEventListener('change', function() {
            updateFormatTemplate(topicId, this.value);
        });
    });
}

// Get default format for topic
function getDefaultFormatForTopic(topic) {
    let payloadFormat = 'json';
    let template = '';
    
    if (topic.name.includes('alarm') || topic.name.includes('alert')) {
        template = `{
  "timestamp": "%TIMESTAMP%",
  "device": "%DEVICE_ID%",
  "alarm_id": "%ALARM_ID%",
  "severity": "%SEVERITY%",
  "message": "%MESSAGE%",
  "value": %VALUE%
}`;
    } else if (topic.name.includes('event')) {
        template = `{
  "timestamp": "%TIMESTAMP%",
  "device": "%DEVICE_ID%",
  "event_type": "%EVENT_TYPE%",
  "description": "%DESCRIPTION%",
  "data": %DATA%
}`;
    } else {
        template = `{
  "timestamp": "%TIMESTAMP%",
  "device": "%DEVICE_ID%",
  "data": %DATA%
}`;
    }
    
    return {
        payloadFormat: payloadFormat,
        template: template,
        topicId: topic.id
    };
}

// Generate format template
function generateFormatTemplate(topicId, format) {
    const textareaHeight = format.payloadFormat === 'json' ? '32' : '24';
    
    if (format.payloadFormat === 'json') {
        return `
            <div>
                <label class="block text-xs font-medium text-slate-700 mb-1">JSON Template</label>
                <textarea id="format-template-textarea-${topicId}" 
                          class="w-full compact-input font-mono text-xs h-${textareaHeight}"
                          placeholder='{"timestamp":"%TIMESTAMP%","device":"%DEVICE_ID%","data":%DATA%}'>${format.template || ''}</textarea>
                <p class="help-text">Use placeholders like %TAG_NAME%, %TIMESTAMP%, %DEVICE_ID%</p>
            </div>
        `;
    } else if (format.payloadFormat === 'csv') {
        return `
            <div class="space-y-2">
                <div>
                    <label class="block text-xs font-medium text-slate-700 mb-1">CSV Headers</label>
                    <input type="text" id="format-csv-headers-${topicId}" 
                           class="w-full compact-input"
                           value="${format.csvHeaders || 'timestamp,device_id,tag_name,tag_value,quality'}"
                           placeholder="timestamp,device_id,tag_name,tag_value,quality">
                </div>
                <div>
                    <label class="block text-xs font-medium text-slate-700 mb-1">CSV Template</label>
                    <textarea id="format-template-textarea-${topicId}" 
                              class="w-full compact-input font-mono text-xs h-${textareaHeight}"
                              placeholder="%TIMESTAMP%,%DEVICE_ID%,%TAG_NAME%,%TAG_VALUE%,%QUALITY%">${format.csvTemplate || ''}</textarea>
                </div>
            </div>
        `;
    } else if (format.payloadFormat === 'keyvalue') {
        return `
            <div>
                <label class="block text-xs font-medium text-slate-700 mb-1">Key-Value Template</label>
                <textarea id="format-template-textarea-${topicId}" 
                          class="w-full compact-input font-mono text-xs h-${textareaHeight}"
                          placeholder="timestamp=%TIMESTAMP%\ndevice=%DEVICE_ID%\ndata=%DATA%">${format.template || ''}</textarea>
                <p class="help-text">One key-value pair per line</p>
            </div>
        `;
    }
}

// Update format template when payload format changes
function updateFormatTemplate(topicId, payloadFormat) {
    const existingFormat = topicFormats[topicId] || getDefaultFormatForTopic(mqttTopics.find(t => t.id === topicId));
    existingFormat.payloadFormat = payloadFormat;
    
    const container = document.getElementById(`format-template-${topicId}`);
    if (container) {
        container.innerHTML = generateFormatTemplate(topicId, existingFormat);
    }
}

// Save topic format
function saveTopicFormat(topicId) {
    const payloadFormatRadio = document.querySelector(`input[name="format-${topicId}-payload"]:checked`);
    const templateTextarea = document.getElementById(`format-template-textarea-${topicId}`);
    
    if (!payloadFormatRadio || !templateTextarea) return;
    
    const payloadFormat = payloadFormatRadio.value;
    const template = templateTextarea.value;
    
    topicFormats[topicId] = {
        payloadFormat: payloadFormat,
        template: template,
        topicId: topicId
    };
    
    if (payloadFormat === 'csv') {
        const csvHeaders = document.getElementById(`format-csv-headers-${topicId}`);
        if (csvHeaders) {
            topicFormats[topicId].csvHeaders = csvHeaders.value;
        }
    }
    
    alert(`Format saved for topic: ${mqttTopics.find(t => t.id === topicId).name}`);
    closeFormatEditor();
}

// Close format editor
function closeFormatEditor() {
    const container = document.getElementById('format-templates-container');
    if (container) {
        container.innerHTML = `
            <div class="p-4 border border-slate-200 rounded bg-slate-50">
                <p class="text-xs text-slate-500 text-center">Select a topic to configure its message format</p>
            </div>
        `;
    }
}

// Populate sample publishing data
function populateSamplePublishingData() {
    // Sample data for OnChange mode
    const onchangeTable = document.getElementById('mqtt-tags-table-onchange');
    if (!onchangeTable) return;
    
    const sampleOnChangeData = [
        { name: 'Hoist_Load', defaultTopic: 'telemetry' },
        { name: 'Boom_Angle', defaultTopic: 'telemetry' },
        { name: 'WindSpeed', defaultTopic: 'alarm' }
    ];
    
    sampleOnChangeData.forEach((tag, index) => {
        const row = document.createElement('tr');
        row.className = 'border-t border-slate-100';
        row.innerHTML = `
            <td class="p-2"><input type="checkbox" class="tag-select-onchange"></td>
            <td class="p-2 font-mono">${tag.name}</td>
            <td class="p-2">
                <select class="w-full compact-select text-xs topic-select" onchange="window.mqttFormLogic.updateFormatDropdown(this, 'onchange', ${index})">
                    ${generateTopicOptions()}
                </select>
            </td>
            <td class="p-2">
                <select class="w-full compact-select text-xs">
                    <option value="onChange" ${index === 0 ? 'selected' : ''}>On Change</option>
                    <option value="100">100 ms</option>
                    <option value="500" ${index === 1 ? 'selected' : ''}>500 ms</option>
                    <option value="1000">1 sec</option>
                    <option value="5000">5 sec</option>
                </select>
            </td>
            <td class="p-2">
                <select class="w-full compact-select text-xs">
                    <option value="0">0</option>
                    <option value="1" ${index !== 2 ? 'selected' : ''}>1</option>
                    <option value="2" ${index === 2 ? 'selected' : ''}>2</option>
                </select>
            </td>
            <td class="p-2">
                <select class="w-full compact-select text-xs format-select" id="format-onchange-${index}">
                    <option value="">-- Select Format --</option>
                </select>
            </td>
            <td class="p-2">
                <label class="toggle-switch">
                    <input type="checkbox" checked>
                    <span class="toggle-slider"></span>
                </label>
            </td>
        `;
        onchangeTable.appendChild(row);
        
        // Set default topic
        setTimeout(() => {
            const select = row.querySelector('.topic-select');
            const topic = mqttTopics.find(t => t.name === tag.defaultTopic);
            if (topic && select) {
                select.value = topic.fullTopic;
                updateFormatDropdown(select, 'onchange', index);
            }
        }, 100);
    });
    
    // Sample data for Periodic mode
    const periodicTable = document.getElementById('mqtt-tags-table-periodic');
    if (periodicTable) {
        const samplePeriodicData = [
            { name: 'Temperature', defaultTopic: 'telemetry' },
            { name: 'Pressure', defaultTopic: 'telemetry' }
        ];
        
        samplePeriodicData.forEach((tag, index) => {
            const row = document.createElement('tr');
            row.className = 'border-t border-slate-100';
            row.innerHTML = `
                <td class="p-2"><input type="checkbox" class="tag-select-periodic"></td>
                <td class="p-2 font-mono">${tag.name}</td>
                <td class="p-2">
                    <select class="w-full compact-select text-xs topic-select" onchange="window.mqttFormLogic.updateFormatDropdown(this, 'periodic', ${index})">
                        ${generateTopicOptions()}
                    </select>
                </td>
                <td class="p-2">
                    <select class="w-full compact-select text-xs">
                        <option value="float" selected>Float</option>
                        <option value="integer">Integer</option>
                        <option value="boolean">Boolean</option>
                        <option value="string">String</option>
                    </select>
                </td>
                <td class="p-2">
                    <select class="w-full compact-select text-xs">
                        <option value="low">Low</option>
                        <option value="medium" selected>Medium</option>
                        <option value="high">High</option>
                        <option value="critical">Critical</option>
                    </select>
                </td>
                <td class="p-2">
                    <select class="w-full compact-select text-xs format-select" id="format-periodic-${index}">
                        <option value="">-- Select Format --</option>
                    </select>
                </td>
                <td class="p-2">
                    <label class="toggle-switch">
                        <input type="checkbox" checked>
                        <span class="toggle-slider"></span>
                    </label>
                </td>
                <td class="p-2">
                    <label class="toggle-switch">
                        <input type="checkbox" checked>
                        <span class="toggle-slider"></span>
                    </label>
                </td>
            `;
            periodicTable.appendChild(row);
        });
    }
    
    // Sample data for Event mode
    const eventTable = document.getElementById('mqtt-tags-table-event');
    if (eventTable) {
        const sampleEventData = [
            { name: 'Overload_Alert', defaultTopic: 'alarm', type: 'alarm', severity: 'high' },
            { name: 'Wind_Alert', defaultTopic: 'alarm', type: 'warning', severity: 'medium' },
            { name: 'Maintenance_Event', defaultTopic: 'event', type: 'info', severity: 'low' }
        ];
        
        sampleEventData.forEach((event, index) => {
            const row = document.createElement('tr');
            row.className = 'border-t border-slate-100';
            row.innerHTML = `
                <td class="p-2"><input type="checkbox" class="tag-select-event"></td>
                <td class="p-2 font-mono">${event.name}</td>
                <td class="p-2">
                    <select class="w-full compact-select text-xs topic-select" onchange="window.mqttFormLogic.updateFormatDropdown(this, 'event', ${index})">
                        ${generateTopicOptions()}
                    </select>
                </td>
                <td class="p-2">
                    <select class="w-full compact-select text-xs">
                        <option value="alarm" ${event.type === 'alarm' ? 'selected' : ''}>Alarm</option>
                        <option value="warning" ${event.type === 'warning' ? 'selected' : ''}>Warning</option>
                        <option value="info" ${event.type === 'info' ? 'selected' : ''}>Info</option>
                        <option value="emergency">Emergency</option>
                    </select>
                </td>
                <td class="p-2">
                    <select class="w-full compact-select text-xs">
                        <option value="low" ${event.severity === 'low' ? 'selected' : ''}>Low</option>
                        <option value="medium" ${event.severity === 'medium' ? 'selected' : ''}>Medium</option>
                        <option value="high" ${event.severity === 'high' ? 'selected' : ''}>High</option>
                        <option value="critical">Critical</option>
                    </select>
                </td>
                <td class="p-2">
                    <select class="w-full compact-select text-xs format-select" id="format-event-${index}">
                        <option value="">-- Select Format --</option>
                    </select>
                </td>
                <td class="p-2">
                    <select class="w-full compact-select text-xs">
                        <option value="threshold" ${index < 2 ? 'selected' : ''}>Threshold Breach</option>
                        <option value="state" ${index === 2 ? 'selected' : ''}>State Change</option>
                        <option value="rate">Rate of Change</option>
                        <option value="custom">Custom Logic</option>
                    </select>
                </td>
                <td class="p-2">
                    <label class="toggle-switch">
                        <input type="checkbox" checked>
                        <span class="toggle-slider"></span>
                    </label>
                </td>
            `;
            eventTable.appendChild(row);
        });
    }
    
    updateSelectedTagsCount();
}

// Update format dropdown based on selected topic
function updateFormatDropdown(select, mode, rowIndex) {
    if (!select) return;
    
    const selectedTopic = select.value;
    const formatSelect = document.getElementById(`format-${mode}-${rowIndex}`);
    
    if (!formatSelect) return;
    
    // Clear existing options
    formatSelect.innerHTML = '<option value="">-- Select Format --</option>';
    
    if (!selectedTopic || selectedTopic === 'custom') {
        // Add default formats for custom topic
        formatSelect.innerHTML += `
            <option value="json">JSON Format</option>
            <option value="csv">CSV Format</option>
            <option value="keyvalue">Key-Value Format</option>
        `;
        return;
    }
    
    // Find topic and its format
    const topic = mqttTopics.find(t => t.fullTopic === selectedTopic);
    if (topic && topicFormats[topic.id]) {
        const format = topicFormats[topic.id];
        formatSelect.innerHTML += `<option value="${topic.id}" selected>${format.payloadFormat.toUpperCase()} - ${topic.name}</option>`;
    } else {
        // Add default format options
        formatSelect.innerHTML += `
            <option value="json">JSON Format</option>
            <option value="csv">CSV Format</option>
            <option value="keyvalue">Key-Value Format</option>
        `;
    }
}

// Setup event listeners for tag checkboxes
function setupTagCheckboxListeners() {
    // Use event delegation since checkboxes are dynamically added
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('tag-select-onchange') || 
            e.target.classList.contains('tag-select-periodic') || 
            e.target.classList.contains('tag-select-event')) {
            updateSelectedTagsCount();
        }
    });
}

// Function to update UI based on selected publish mode
function updatePublishMode() {
    const selectedModeRadio = document.querySelector('input[name="field-publishMode"]:checked');
    if (!selectedModeRadio) return;
    
    const selectedMode = selectedModeRadio.value;
    const helpText = document.getElementById('publish-mode-help');
    const periodicOptions = document.getElementById('periodic-options');
    const eventOptions = document.getElementById('event-options');
    const titleElement = document.getElementById('tag-selection-title');
    
    // Update title based on mode
    const titles = {
        'onChange': 'Select Tags to Publish',
        'periodic': 'Select Data Points for Periodic Publishing',
        'event': 'Select Events to Monitor and Publish'
    };
    if (titleElement) {
        titleElement.textContent = titles[selectedMode];
    }
    
    // Update help text
    const helpTexts = {
        'onChange': 'Publish individual tag values when they change',
        'periodic': 'Publish batched data at regular intervals',
        'event': 'Publish only when specific events occur'
    };
    if (helpText) {
        helpText.textContent = helpTexts[selectedMode];
    }
    
    // Show/hide options sections
    if (periodicOptions) {
        periodicOptions.style.display = selectedMode === 'periodic' ? 'block' : 'none';
    }
    if (eventOptions) {
        eventOptions.style.display = selectedMode === 'event' ? 'block' : 'none';
    }
    
    // Show/hide tag tables
    const tagTableOnchange = document.getElementById('tag-table-onchange');
    const tagTablePeriodic = document.getElementById('tag-table-periodic');
    const tagTableEvent = document.getElementById('tag-table-event');
    
    if (tagTableOnchange) tagTableOnchange.style.display = selectedMode === 'onChange' ? 'block' : 'none';
    if (tagTablePeriodic) tagTablePeriodic.style.display = selectedMode === 'periodic' ? 'block' : 'none';
    if (tagTableEvent) tagTableEvent.style.display = selectedMode === 'event' ? 'block' : 'none';
    
    // Update selected tags count
    updateSelectedTagsCount();
}

// Tab switching for MQTT form
function switchMqttTab(tabName) {
    // Hide all tab contents
    document.querySelectorAll('.mqtt-tab-content').forEach(tab => {
        tab.style.display = 'none';
    });
    
    // Remove active class from all tab buttons
    document.querySelectorAll('.tab-button').forEach(button => {
        button.classList.remove('active');
    });
    
    // Show selected tab content
    const tabContent = document.getElementById(`mqtt-${tabName}-content`);
    if (tabContent) {
        tabContent.style.display = 'block';
    }
    
    // Activate tab button
    const tabButtons = document.querySelectorAll('.tab-button');
    tabButtons.forEach(button => {
        if (button.textContent.toLowerCase().includes(tabName.charAt(0).toUpperCase() + tabName.slice(1))) {
            button.classList.add('active');
        }
    });
    
    // When switching to Topics & Format tab, refresh topic list
    if (tabName === 'topics') {
        updateTopicList();
    }
}

// Tag management functions
function toggleAllTags(mode) {
    let selector = '';
    let checkboxId = '';
    
    switch(mode) {
        case 'onChange':
            selector = '.tag-select-onchange';
            checkboxId = 'select-all-tags-onchange';
            break;
        case 'periodic':
            selector = '.tag-select-periodic';
            checkboxId = 'select-all-tags-periodic';
            break;
        case 'event':
            selector = '.tag-select-event';
            checkboxId = 'select-all-tags-event';
            break;
    }
    
    const selectAll = document.getElementById(checkboxId);
    if (!selectAll) return;
    
    const checkboxes = document.querySelectorAll(selector);
    checkboxes.forEach(cb => {
        cb.checked = selectAll.checked;
    });
    updateSelectedTagsCount();
}

function updateSelectedTagsCount() {
    const selectedModeRadio = document.querySelector('input[name="field-publishMode"]:checked');
    if (!selectedModeRadio) return;
    
    const selectedMode = selectedModeRadio.value;
    let selector = '';
    
    switch(selectedMode) {
        case 'onChange':
            selector = '.tag-select-onchange:checked';
            break;
        case 'periodic':
            selector = '.tag-select-periodic:checked';
            break;
        case 'event':
            selector = '.tag-select-event:checked';
            break;
    }
    
    const checkboxes = document.querySelectorAll(selector);
    const countElement = document.getElementById('selected-tags-count');
    if (countElement) {
        countElement.textContent = checkboxes.length;
    }
}

function removeSelectedMqttTags() {
    const selectedModeRadio = document.querySelector('input[name="field-publishMode"]:checked');
    if (!selectedModeRadio) return;
    
    const selectedMode = selectedModeRadio.value;
    let selector = '';
    
    switch(selectedMode) {
        case 'onChange':
            selector = '.tag-select-onchange:checked';
            break;
        case 'periodic':
            selector = '.tag-select-periodic:checked';
            break;
        case 'event':
            selector = '.tag-select-event:checked';
            break;
    }
    
    const selected = document.querySelectorAll(selector);
    if (selected.length === 0) {
        alert('Please select items to remove.');
        return;
    }
    
    const itemType = selectedMode === 'event' ? 'events' : 'tags';
    if (confirm(`Remove ${selected.length} selected ${itemType}?`)) {
        selected.forEach(checkbox => {
            const row = checkbox.closest('tr');
            if (row) row.remove();
        });
        updateSelectedTagsCount();
        alert(`${selected.length} ${itemType} removed successfully.`);
    }
}

// Handle certificate upload
function handleCertificateUpload(input, nameSpanId) {
    const fileName = input.files[0]?.name || 'No file selected';
    const nameSpan = document.getElementById(nameSpanId);
    if (nameSpan) {
        nameSpan.textContent = fileName;
    }
}

// Generate random password
function generatePassword(fieldId) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*';
    let password = '';
    for (let i = 0; i < 12; i++) {
        password += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    const field = document.getElementById(fieldId);
    if (field) {
        field.value = password;
    }
}

// Save functions for each tab
function saveMqttConnectionSettings() {
    alert('MQTT Connection settings saved!');
}

function saveMqttTopicSettings() {
    alert('MQTT Topics & Format settings saved!');
}

function saveMqttPublishingSettings() {
    alert('MQTT Publishing settings saved!');
}

function saveMqttAdvancedSettings() {
    alert('MQTT Advanced settings saved!');
}

// Show add tag modal
function showAddTagModal() {
    const selectedModeRadio = document.querySelector('input[name="field-publishMode"]:checked');
    if (!selectedModeRadio) return;
    
    const publishMode = selectedModeRadio.value;
    const modalTitle = publishMode === 'event' ? 'Add New Event' : 'Add New Tag';
    
    // Simple modal for demonstration
    const itemName = prompt(`Enter ${publishMode === 'event' ? 'Event' : 'Tag'} Name:`);
    if (itemName) {
        // Add to appropriate table
        addNewItemToTable(publishMode, itemName);
    }
}

// Add new item to table
function addNewItemToTable(mode, itemName) {
    let tableId;
    const rowIndex = document.querySelectorAll(`#mqtt-tags-table-${mode} tr`).length;
    
    let rowHtml = '';
    switch(mode) {
        case 'onChange':
            rowHtml = `
                <tr class="border-t border-slate-100">
                    <td class="p-2"><input type="checkbox" class="tag-select-onchange"></td>
                    <td class="p-2 font-mono">${itemName}</td>
                    <td class="p-2">
                        <select class="w-full compact-select text-xs topic-select" onchange="window.mqttFormLogic.updateFormatDropdown(this, 'onchange', ${rowIndex})">
                            ${generateTopicOptions()}
                        </select>
                    </td>
                    <td class="p-2">
                        <select class="w-full compact-select text-xs">
                            <option value="onChange" selected>On Change</option>
                            <option value="100">100 ms</option>
                            <option value="500">500 ms</option>
                            <option value="1000">1 sec</option>
                            <option value="5000">5 sec</option>
                        </select>
                    </td>
                    <td class="p-2">
                        <select class="w-full compact-select text-xs">
                            <option value="0">0</option>
                            <option value="1" selected>1</option>
                            <option value="2">2</option>
                        </select>
                    </td>
                    <td class="p-2">
                        <select class="w-full compact-select text-xs format-select" id="format-onchange-${rowIndex}">
                            <option value="">-- Select Format --</option>
                        </select>
                    </td>
                    <td class="p-2">
                        <label class="toggle-switch">
                            <input type="checkbox" checked>
                            <span class="toggle-slider"></span>
                        </label>
                    </td>
                </tr>
            `;
            break;
        case 'periodic':
            rowHtml = `
                <tr class="border-t border-slate-100">
                    <td class="p-2"><input type="checkbox" class="tag-select-periodic"></td>
                    <td class="p-2 font-mono">${itemName}</td>
                    <td class="p-2">
                        <select class="w-full compact-select text-xs topic-select" onchange="window.mqttFormLogic.updateFormatDropdown(this, 'periodic', ${rowIndex})">
                            ${generateTopicOptions()}
                        </select>
                    </td>
                    <td class="p-2">
                        <select class="w-full compact-select text-xs">
                            <option value="float" selected>Float</option>
                            <option value="integer">Integer</option>
                            <option value="boolean">Boolean</option>
                            <option value="string">String</option>
                        </select>
                    </td>
                    <td class="p-2">
                        <select class="w-full compact-select text-xs">
                            <option value="low">Low</option>
                            <option value="medium" selected>Medium</option>
                            <option value="high">High</option>
                            <option value="critical">Critical</option>
                        </select>
                    </td>
                    <td class="p-2">
                        <select class="w-full compact-select text-xs format-select" id="format-periodic-${rowIndex}">
                            <option value="">-- Select Format --</option>
                        </select>
                    </td>
                    <td class="p-2">
                        <label class="toggle-switch">
                            <input type="checkbox" checked>
                            <span class="toggle-slider"></span>
                        </label>
                    </td>
                    <td class="p-2">
                        <label class="toggle-switch">
                            <input type="checkbox" checked>
                            <span class="toggle-slider"></span>
                        </label>
                    </td>
                </tr>
            `;
            break;
        case 'event':
            rowHtml = `
                <tr class="border-t border-slate-100">
                    <td class="p-2"><input type="checkbox" class="tag-select-event"></td>
                    <td class="p-2 font-mono">${itemName}</td>
                    <td class="p-2">
                        <select class="w-full compact-select text-xs topic-select" onchange="window.mqttFormLogic.updateFormatDropdown(this, 'event', ${rowIndex})">
                            ${generateTopicOptions()}
                        </select>
                    </td>
                    <td class="p-2">
                        <select class="w-full compact-select text-xs">
                            <option value="alarm">Alarm</option>
                            <option value="warning">Warning</option>
                            <option value="info" selected>Info</option>
                            <option value="emergency">Emergency</option>
                        </select>
                    </td>
                    <td class="p-2">
                        <select class="w-full compact-select text-xs">
                            <option value="low" selected>Low</option>
                            <option value="medium">Medium</option>
                            <option value="high">High</option>
                            <option value="critical">Critical</option>
                        </select>
                    </td>
                    <td class="p-2">
                        <select class="w-full compact-select text-xs format-select" id="format-event-${rowIndex}">
                            <option value="">-- Select Format --</option>
                        </select>
                    </td>
                    <td class="p-2">
                        <select class="w-full compact-select text-xs">
                            <option value="threshold" selected>Threshold Breach</option>
                            <option value="state">State Change</option>
                            <option value="rate">Rate of Change</option>
                            <option value="custom">Custom Logic</option>
                        </select>
                    </td>
                    <td class="p-2">
                        <label class="toggle-switch">
                            <input type="checkbox" checked>
                            <span class="toggle-slider"></span>
                        </label>
                    </td>
                </tr>
            `;
            break;
    }
    
    const table = document.getElementById(`mqtt-tags-table-${mode}`);
    if (table) {
        table.insertAdjacentHTML('beforeend', rowHtml);
        updateSelectedTagsCount();
    }
}

// Export functions to global scope
window.mqttFormLogic = {
    initializeMqttForm,
    updateAllTopicOptions,
    addCustomTopic,
    addNewCustomTopic,
    removeCustomTopic,
    editTopicFormat,
    closeFormatEditor,
    saveTopicFormat,
    switchMqttTab,
    toggleAllTags,
    removeSelectedMqttTags,
    handleCertificateUpload,
    generatePassword,
    updateFormatDropdown,
    showAddTagModal,
    saveMqttConnectionSettings,
    saveMqttTopicSettings,
    saveMqttPublishingSettings,
    saveMqttAdvancedSettings
};