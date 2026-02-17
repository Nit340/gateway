// This function will be called by the router when loading the page
window.initSecurity = function() {
    console.log('Security & Access Control page initialized');
    
    // Initialize all functionality for this page
    initializeSecurity();
};

function initializeSecurity() {
    console.log('Setting up Security & Access Control page functionality');
    
    // Initialize application state
    initializeAppState();
    
    // Initialize button handlers
    initializeButtons();
    
    // Initialize form interactions
    initializeFormInteractions();
    
    // Initialize data
    loadInitialData();
    
    console.log('Security & Access Control page setup complete');
}

// ==================== APPLICATION STATE ====================
function initializeAppState() {
    window.securityState = {
        users: [],
        apiKeys: [],
        firewallRules: [],
        auditLogs: [],
        ipWhitelist: [],
        blockedPorts: [],
        allowedCommands: [],
        certificates: {},
        unsavedChanges: false,
        currentEditingUser: null,
        currentGeneratedApiKey: null
    };
}

// ==================== BUTTON HANDLERS ====================
function initializeButtons() {
    // User Management
    document.getElementById('addUserBtn')?.addEventListener('click', showAddUserModal);
    document.getElementById('customRoleBtn')?.addEventListener('click', showCustomRoleModal);
    
    // API Keys
    document.getElementById('generateApiKeyBtn')?.addEventListener('click', showApiKeyModal);
    document.getElementById('regenerateWebhookBtn')?.addEventListener('click', regenerateWebhookSecret);
    
    // SSH Access
    document.getElementById('uploadSshKeyBtn')?.addEventListener('click', () => simulateFileUpload('sshKeyFile'));
    document.getElementById('addCommandBtn')?.addEventListener('click', addAllowedCommand);
    
    // Firewall
    document.getElementById('addFirewallRuleBtn')?.addEventListener('click', showFirewallRuleModal);
    document.getElementById('addIpAddressBtn')?.addEventListener('click', addIpAddress);
    document.getElementById('addBlockedPortBtn')?.addEventListener('click', addBlockedPort);
    
    // Certificates
    document.getElementById('uploadHttpsCertBtn')?.addEventListener('click', () => simulateFileUpload('httpsCertFile'));
    document.getElementById('uploadHttpsKeyBtn')?.addEventListener('click', () => simulateFileUpload('httpsKeyFile'));
    document.getElementById('uploadMqttCaBtn')?.addEventListener('click', () => simulateFileUpload('mqttCaFile'));
    document.getElementById('uploadMqttCertBtn')?.addEventListener('click', () => simulateFileUpload('mqttCertFile'));
    document.getElementById('uploadMqttKeyBtn')?.addEventListener('click', () => simulateFileUpload('mqttKeyFile'));
    document.getElementById('generateSelfSignedBtn')?.addEventListener('click', generateSelfSignedCert);
    
    // Audit Log
    document.getElementById('auditTimeRange')?.addEventListener('change', filterAuditLog);
    document.getElementById('auditEventType')?.addEventListener('change', filterAuditLog);
    document.getElementById('auditUsername')?.addEventListener('change', filterAuditLog);
    document.getElementById('auditIpAddress')?.addEventListener('keyup', filterAuditLog);
    document.getElementById('exportAuditBtn')?.addEventListener('click', exportAuditLog);
    document.getElementById('refreshAuditBtn')?.addEventListener('click', refreshAuditLog);
    
    // Footer Actions
    document.getElementById('securityScanBtn')?.addEventListener('click', runSecurityScan);
    document.getElementById('resetDefaultsBtn')?.addEventListener('click', resetToDefaults);
    document.getElementById('lockSystemBtn')?.addEventListener('click', lockSystem);
    document.getElementById('save-btn')?.addEventListener('click', handleSaveAllSettings);
    
    // Gateway select
    const gatewaySelect = document.getElementById('gateway-select');
    if (gatewaySelect) {
        gatewaySelect.addEventListener('change', function() {
            if (window.securityState.unsavedChanges) {
                showConfirmationDialog('Switch to another gateway? Unsaved security changes will be lost.', 'Switch Gateway', 'Stay')
                    .then(confirmed => {
                        if (confirmed) {
                            window.location.reload();
                        } else {
                            this.value = 'Univa-GW-01';
                        }
                    });
            } else {
                window.location.reload();
            }
        });
    }
}

// ==================== FORM INTERACTIONS ====================
function initializeFormInteractions() {
    // Mark unsaved changes on any form change
    document.querySelectorAll('input, select, textarea').forEach(element => {
        element.addEventListener('change', markUnsavedChanges);
    });
    
    // Initialize toggle switches
    document.querySelectorAll('.toggle-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', markUnsavedChanges);
    });
}

function markUnsavedChanges() {
    window.securityState.unsavedChanges = true;
    
    const saveBtn = document.getElementById('save-btn');
    if (saveBtn) {
        saveBtn.classList.add('bg-orange-500', 'hover:bg-orange-600');
    }
}

// ==================== MODAL SYSTEM ====================
function showAddUserModal() {
    const modalContent = `
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Full Name *</label>
                <input type="text" id="userFullName" required class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:border-primary" placeholder="John Doe">
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Username *</label>
                <input type="text" id="userUsername" required class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:border-primary" placeholder="johndoe">
                <p class="text-xs text-slate-500 mt-1">Lowercase letters and numbers only</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Email *</label>
                <input type="email" id="userEmail" required class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:border-primary" placeholder="john@example.com">
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Role *</label>
                <select id="userRole" required class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:border-primary">
                    <option value="">Select Role</option>
                    <option value="admin">Administrator</option>
                    <option value="engineer">Engineer</option>
                    <option value="technician">Technician</option>
                    <option value="operator">Operator</option>
                    <option value="viewer">Viewer</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Password *</label>
                <input type="password" id="userPassword" required class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:border-primary" placeholder="Enter password">
                <div class="flex items-center justify-between mt-1">
                    <div id="passwordStrength" class="password-strength"></div>
                    <span id="passwordStrengthText" class="text-xs text-slate-500 ml-2">Strength</span>
                </div>
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Confirm Password *</label>
                <input type="password" id="userConfirmPassword" required class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:border-primary" placeholder="Confirm password">
                <p id="passwordMatchError" class="text-xs text-red-500 mt-1 hidden">Passwords do not match</p>
            </div>
            <div class="flex items-center">
                <input type="checkbox" id="userEnable2FA" class="h-4 w-4 text-primary rounded border-slate-300 focus:ring-primary">
                <label for="userEnable2FA" class="ml-2 text-sm text-slate-700">Enable Two-Factor Authentication</label>
            </div>
        </div>
    `;
    
    showCustomModal({
        title: 'Add New User',
        content: modalContent,
        buttons: [
            {
                text: 'Cancel',
                type: 'secondary',
                action: () => {}
            },
            {
                text: 'Create User',
                type: 'primary',
                action: () => addNewUser()
            }
        ]
    });
}

function showApiKeyModal() {
    const modalContent = `
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Key Name *</label>
                <input type="text" id="apiKeyName" class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:border-primary" placeholder="e.g., Mobile App Integration">
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-2">Permissions</label>
                <div class="space-y-2">
                    <label class="flex items-center">
                        <input type="checkbox" class="api-permission h-4 w-4 text-primary rounded border-slate-300 focus:ring-primary" value="read">
                        <span class="ml-2 text-sm text-slate-700">Read Access</span>
                    </label>
                    <label class="flex items-center">
                        <input type="checkbox" class="api-permission h-4 w-4 text-primary rounded border-slate-300 focus:ring-primary" value="write">
                        <span class="ml-2 text-sm text-slate-700">Write Access</span>
                    </label>
                    <label class="flex items-center">
                        <input type="checkbox" class="api-permission h-4 w-4 text-primary rounded border-slate-300 focus:ring-primary" value="admin">
                        <span class="ml-2 text-sm text-slate-700">Admin Access</span>
                    </label>
                </div>
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Expiration</label>
                <select id="apiKeyExpiry" class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:border-primary">
                    <option value="never">Never Expires</option>
                    <option value="30">30 Days</option>
                    <option value="90">90 Days</option>
                    <option value="365">1 Year</option>
                    <option value="custom">Custom Date</option>
                </select>
            </div>
            <div id="customExpiryDate" class="hidden">
                <label class="block text-sm font-medium text-slate-700 mb-1">Custom Expiry Date</label>
                <input type="date" id="apiKeyCustomDate" class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm">
            </div>
        </div>
    `;
    
    showCustomModal({
        title: 'Generate API Key',
        content: modalContent,
        buttons: [
            {
                text: 'Cancel',
                type: 'secondary',
                action: () => {}
            },
            {
                text: 'Generate Key',
                type: 'primary',
                action: () => generateApiKey()
            }
        ]
    });
}

function showFirewallRuleModal() {
    const modalContent = `
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Rule Name</label>
                <input type="text" id="ruleName" class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm" placeholder="e.g., Allow SSH from Internal">
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Protocol</label>
                <select id="ruleProtocol" class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm">
                    <option value="tcp">TCP</option>
                    <option value="udp">UDP</option>
                    <option value="icmp">ICMP</option>
                    <option value="any">Any</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Port / Port Range</label>
                <input type="text" id="rulePort" class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm" placeholder="22 or 80-90">
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Source IP / Network</label>
                <input type="text" id="ruleSource" class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm" placeholder="192.168.1.0/24 or 0.0.0.0/0 for any">
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Action</label>
                <select id="ruleAction" class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm">
                    <option value="allow">Allow</option>
                    <option value="deny">Deny</option>
                    <option value="reject">Reject</option>
                </select>
            </div>
        </div>
    `;
    
    showCustomModal({
        title: 'Add Firewall Rule',
        content: modalContent,
        buttons: [
            {
                text: 'Cancel',
                type: 'secondary',
                action: () => {}
            },
            {
                text: 'Add Rule',
                type: 'primary',
                action: () => addFirewallRule()
            }
        ]
    });
}

// ==================== CUSTOM MODAL SYSTEM ====================
function showCustomModal(options) {
    const { title, content, buttons } = options;
    
    // Create modal overlay
    const overlay = document.createElement('div');
    overlay.className = 'fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4';
    overlay.id = 'customModalOverlay';
    
    // Create modal
    const modal = document.createElement('div');
    modal.className = 'bg-white rounded-xl shadow-xl max-w-md w-full max-h-[90vh] overflow-y-auto';
    
    modal.innerHTML = `
        <div class="p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="font-semibold text-lg text-slate-800">${title}</h3>
                <button class="text-slate-400 hover:text-slate-600 close-modal" aria-label="Close modal">
                    <i class="fa-solid fa-times"></i>
                </button>
            </div>
            <div class="mb-6 modal-content">
                ${content}
            </div>
            <div class="flex justify-end space-x-3 modal-buttons">
                ${buttons.map(btn => `
                    <button class="px-4 py-2 rounded-lg text-sm font-medium ${btn.type === 'primary' ? 'bg-primary text-white hover:bg-primaryHover' : 'border border-slate-300 text-slate-700 hover:bg-slate-50'}">
                        ${btn.text}
                    </button>
                `).join('')}
            </div>
        </div>
    `;
    
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    
    // Add event listeners
    const closeBtn = overlay.querySelector('.close-modal');
    closeBtn.addEventListener('click', () => {
        document.body.removeChild(overlay);
    });
    
    // Add button actions
    const modalButtons = overlay.querySelectorAll('.modal-buttons button');
    modalButtons.forEach((button, index) => {
        button.addEventListener('click', () => {
            buttons[index].action();
            document.body.removeChild(overlay);
        });
    });
    
    // Close on escape
    const handleKeydown = (e) => {
        if (e.key === 'Escape') {
            document.body.removeChild(overlay);
            document.removeEventListener('keydown', handleKeydown);
        }
    };
    document.addEventListener('keydown', handleKeydown);
}

// ==================== USER MANAGEMENT ====================
function loadUsers() {
    // Mock data
    window.securityState.users = [
        {
            id: 1,
            username: 'admin',
            fullName: 'System Admin',
            email: 'admin@innospace.com',
            role: 'admin',
            status: 'online',
            lastLogin: new Date().toISOString(),
            twoFactorEnabled: true,
            avatarColor: 'indigo'
        },
        {
            id: 2,
            username: 'ops01',
            fullName: 'Ops User',
            email: 'ops@innospace.com',
            role: 'operator',
            status: 'online',
            lastLogin: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
            twoFactorEnabled: false,
            avatarColor: 'orange'
        },
        {
            id: 3,
            username: 'tech01',
            fullName: 'Technician User',
            email: 'tech@innospace.com',
            role: 'technician',
            status: 'online',
            lastLogin: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(),
            twoFactorEnabled: true,
            avatarColor: 'blue'
        }
    ];
    
    renderUsersTable();
}

function renderUsersTable() {
    const tbody = document.getElementById('userTableBody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    window.securityState.users.forEach(user => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-slate-50 transition cursor-pointer';
        row.addEventListener('click', () => editUser(user.id));
        
        const lastLogin = new Date(user.lastLogin);
        const now = new Date();
        const diffDays = Math.floor((now - lastLogin) / (1000 * 60 * 60 * 24));
        let lastLoginText = 'Today';
        
        if (diffDays === 1) lastLoginText = 'Yesterday';
        else if (diffDays > 1) lastLoginText = `${diffDays} days ago`;
        
        row.innerHTML = `
            <td class="px-6 py-3 font-medium text-slate-900">
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-full bg-${user.avatarColor}-100 flex items-center justify-center text-${user.avatarColor}-600 font-bold text-xs">
                        ${user.fullName.split(' ').map(n => n[0]).join('').toUpperCase()}
                    </div>
                    <div>
                        <div class="font-semibold">${user.username}</div>
                        <div class="text-xs text-slate-500">${user.fullName}</div>
                    </div>
                </div>
            </td>
            <td class="px-6 py-3">
                <span class="bg-${getRoleColor(user.role)}-100 text-${getRoleColor(user.role)}-800 text-xs px-2 py-0.5 rounded-full font-medium">
                    ${capitalizeFirstLetter(user.role)}
                </span>
            </td>
            <td class="px-6 py-3">
                <span class="status-dot ${user.status}"></span>
            </td>
            <td class="px-6 py-3 text-slate-500">${lastLoginText}</td>
            <td class="px-6 py-3 ${user.twoFactorEnabled ? 'text-green-600' : 'text-red-400'}">
                <i class="fa-solid fa-${user.twoFactorEnabled ? 'check' : 'times'}-circle"></i>
            </td>
            <td class="px-6 py-3 text-right">
                <button class="text-slate-400 hover:text-primary" onclick="event.stopPropagation(); editUser(${user.id})">
                    <i class="fa-solid fa-pen-to-square"></i>
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

function addNewUser() {
    const fullName = document.getElementById('userFullName')?.value;
    const username = document.getElementById('userUsername')?.value;
    const email = document.getElementById('userEmail')?.value;
    const password = document.getElementById('userPassword')?.value;
    const confirmPassword = document.getElementById('userConfirmPassword')?.value;
    const role = document.getElementById('userRole')?.value;
    const enable2FA = document.getElementById('userEnable2FA')?.checked;
    
    // Validation
    if (!fullName || !username || !email || !password || !role) {
        showNotification('Please fill all required fields', 'error');
        return;
    }
    
    if (password !== confirmPassword) {
        showNotification('Passwords do not match', 'error');
        return;
    }
    
    if (password.length < 8) {
        showNotification('Password must be at least 8 characters', 'error');
        return;
    }
    
    // Add user
    const newUser = {
        id: window.securityState.users.length + 1,
        username: username,
        fullName: fullName,
        email: email,
        role: role,
        status: 'online',
        lastLogin: new Date().toISOString(),
        twoFactorEnabled: enable2FA,
        avatarColor: 'blue'
    };
    
    window.securityState.users.push(newUser);
    renderUsersTable();
    showNotification('User created successfully', 'success');
    markUnsavedChanges();
}

function editUser(userId) {
    const user = window.securityState.users.find(u => u.id === userId);
    if (!user) return;
    
    window.securityState.currentEditingUser = user;
    
    const modalContent = `
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Username</label>
                <input type="text" id="editUsername" value="${user.username}" class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm" readonly>
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Full Name</label>
                <input type="text" id="editFullName" value="${user.fullName}" class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm">
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Email</label>
                <input type="email" id="editEmail" value="${user.email}" class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm">
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Role</label>
                <select id="editRole" class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm">
                    <option value="admin" ${user.role === 'admin' ? 'selected' : ''}>Administrator</option>
                    <option value="engineer" ${user.role === 'engineer' ? 'selected' : ''}>Engineer</option>
                    <option value="technician" ${user.role === 'technician' ? 'selected' : ''}>Technician</option>
                    <option value="operator" ${user.role === 'operator' ? 'selected' : ''}>Operator</option>
                    <option value="viewer" ${user.role === 'viewer' ? 'selected' : ''}>Viewer</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Two-Factor Authentication</label>
                <div class="flex items-center">
                    <input type="checkbox" id="editTwoFactor" ${user.twoFactorEnabled ? 'checked' : ''} class="h-4 w-4 text-primary rounded border-slate-300 focus:ring-primary">
                    <label for="editTwoFactor" class="ml-2 text-sm text-slate-700">Enabled</label>
                </div>
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Reset Password (Optional)</label>
                <input type="password" id="editPassword" class="w-full rounded-lg border-slate-300 border px-3 py-2 text-sm" placeholder="Leave blank to keep current">
            </div>
        </div>
    `;
    
    showCustomModal({
        title: 'Edit User',
        content: modalContent,
        buttons: [
            {
                text: 'Delete User',
                type: 'secondary',
                action: () => deleteUser()
            },
            {
                text: 'Cancel',
                type: 'secondary',
                action: () => {}
            },
            {
                text: 'Save Changes',
                type: 'primary',
                action: () => saveUserChanges()
            }
        ]
    });
}

function saveUserChanges() {
    if (!window.securityState.currentEditingUser) return;
    
    const user = window.securityState.currentEditingUser;
    const newPassword = document.getElementById('editPassword')?.value;
    
    // Update user
    user.fullName = document.getElementById('editFullName')?.value || user.fullName;
    user.email = document.getElementById('editEmail')?.value || user.email;
    user.role = document.getElementById('editRole')?.value || user.role;
    user.twoFactorEnabled = document.getElementById('editTwoFactor')?.checked || false;
    
    if (newPassword) {
        showNotification('Password updated', 'info');
    }
    
    renderUsersTable();
    showNotification('User updated successfully', 'success');
    markUnsavedChanges();
}

function deleteUser() {
    if (!window.securityState.currentEditingUser || window.securityState.currentEditingUser.username === 'admin') {
        showNotification('Cannot delete admin user', 'error');
        return;
    }
    
    showConfirmationDialog(`Delete user "${window.securityState.currentEditingUser.username}"? This action cannot be undone.`, 'Delete', 'Cancel')
        .then(confirmed => {
            if (confirmed) {
                window.securityState.users = window.securityState.users.filter(u => u.id !== window.securityState.currentEditingUser.id);
                renderUsersTable();
                showNotification('User deleted successfully', 'success');
                markUnsavedChanges();
            }
        });
}

// ==================== API KEY MANAGEMENT ====================
function loadApiKeys() {
    // Mock data
    window.securityState.apiKeys = [
        {
            id: 1,
            name: 'CI Pipeline',
            key: 'AK-001',
            scope: ['telemetry:write'],
            expires: '2026-06-01'
        },
        {
            id: 2,
            name: 'Mobile App',
            key: 'AK-002',
            scope: ['telemetry:read'],
            expires: null
        }
    ];
    
    renderApiKeysTable();
}

function renderApiKeysTable() {
    const tbody = document.getElementById('apiKeysTableBody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    window.securityState.apiKeys.forEach(key => {
        const expiresText = key.expires ? 
            new Date(key.expires).toLocaleDateString('en-US', { month: 'short', year: 'numeric' }) : 
            '<span class="text-green-600">Never</span>';
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="px-4 py-3 font-medium">
                ${key.name} 
                <span class="text-xs text-slate-400 block font-normal">${key.key}</span>
            </td>
            <td class="px-4 py-3">
                ${key.scope.map(scope => 
                    `<span class="bg-slate-100 text-slate-600 text-xs px-2 py-0.5 rounded mr-1">${scope}</span>`
                ).join('')}
            </td>
            <td class="px-4 py-3 ${key.expires ? 'text-slate-600' : 'text-green-600'}">
                ${expiresText}
            </td>
            <td class="px-4 py-3 text-right">
                <button class="text-red-500 hover:text-red-700 text-xs font-medium" onclick="revokeApiKey(${key.id})">
                    Revoke
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

function generateApiKey() {
    const name = document.getElementById('apiKeyName')?.value;
    if (!name) {
        showNotification('Please enter a key name', 'error');
        return;
    }
    
    // Generate random key
    const key = 'sk_' + Array.from(crypto.getRandomValues(new Uint8Array(32)))
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');
    
    const newKey = {
        id: window.securityState.apiKeys.length + 1,
        name: name,
        key: key,
        scope: ['read'],
        expires: null
    };
    
    window.securityState.apiKeys.push(newKey);
    window.securityState.currentGeneratedApiKey = key;
    renderApiKeysTable();
    
    // Show key to user
    showNotification(`API key generated: ${key}`, 'success');
    markUnsavedChanges();
}

function revokeApiKey(keyId) {
    showConfirmationDialog('Revoke this API key? This action cannot be undone.', 'Revoke', 'Cancel')
        .then(confirmed => {
            if (confirmed) {
                window.securityState.apiKeys = window.securityState.apiKeys.filter(k => k.id !== keyId);
                renderApiKeysTable();
                showNotification('API key revoked', 'success');
                markUnsavedChanges();
            }
        });
}

// ==================== FIREWALL MANAGEMENT ====================
function loadFirewallRules() {
    // Mock data
    window.securityState.firewallRules = [
        { id: 1, name: 'SSH Management', port: '22', protocol: 'TCP', source: '192.168.1.0/24', action: 'allow' },
        { id: 2, name: 'HTTP Dashboard', port: '80', protocol: 'TCP', source: 'Any', action: 'allow' }
    ];
    
    window.securityState.ipWhitelist = ['192.168.0.0/24', '10.0.0.5'];
    window.securityState.blockedPorts = [23, 21, 8000];
    window.securityState.allowedCommands = ['cat', 'ls', 'ifconfig', 'ping', 'tail', 'grep', 'df', 'ps'];
    
    renderFirewallRules();
    renderIpWhitelist();
    renderBlockedPorts();
    renderAllowedCommands();
}

function renderFirewallRules() {
    const tbody = document.getElementById('firewallRulesTableBody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    window.securityState.firewallRules.forEach(rule => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="px-4 py-2 font-medium">${rule.name}</td>
            <td class="px-4 py-2 font-mono">${rule.port}</td>
            <td class="px-4 py-2">${rule.protocol}</td>
            <td class="px-4 py-2 text-slate-600">${rule.source}</td>
            <td class="px-4 py-2 text-right">
                <span class="bg-${rule.action === 'allow' ? 'green' : 'red'}-100 text-${rule.action === 'allow' ? 'green' : 'red'}-800 text-xs px-2 py-0.5 rounded-full">
                    ${capitalizeFirstLetter(rule.action)}
                </span>
                <button class="ml-2 text-slate-400 hover:text-red-500 text-xs" onclick="removeFirewallRule(${rule.id})">
                    <i class="fa-solid fa-trash"></i>
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

function addFirewallRule() {
    const name = document.getElementById('ruleName')?.value;
    const port = document.getElementById('rulePort')?.value;
    const source = document.getElementById('ruleSource')?.value;
    
    if (!name || !port || !source) {
        showNotification('Please fill all required fields', 'error');
        return;
    }
    
    const newRule = {
        id: window.securityState.firewallRules.length + 1,
        name: name,
        port: port,
        protocol: document.getElementById('ruleProtocol')?.value || 'tcp',
        source: source,
        action: document.getElementById('ruleAction')?.value || 'allow'
    };
    
    window.securityState.firewallRules.push(newRule);
    renderFirewallRules();
    showNotification('Firewall rule added', 'success');
    markUnsavedChanges();
}

function removeFirewallRule(ruleId) {
    showConfirmationDialog('Remove this firewall rule?', 'Remove', 'Cancel')
        .then(confirmed => {
            if (confirmed) {
                window.securityState.firewallRules = window.securityState.firewallRules.filter(r => r.id !== ruleId);
                renderFirewallRules();
                showNotification('Firewall rule removed', 'success');
                markUnsavedChanges();
            }
        });
}

// ==================== IP WHITELIST ====================
function renderIpWhitelist() {
    const container = document.getElementById('ipWhitelist');
    if (!container) return;
    
    container.innerHTML = '';
    
    window.securityState.ipWhitelist.forEach((ip, index) => {
        const div = document.createElement('div');
        div.className = 'flex items-center';
        div.innerHTML = `
            <input type="text" value="${ip}" class="flex-1 rounded-lg border-slate-300 border px-3 py-2 text-sm font-mono">
            <button class="ml-2 text-red-500 hover:text-red-700" onclick="removeIpAddress(${index})">
                <i class="fa-solid fa-times"></i>
            </button>
        `;
        container.appendChild(div);
    });
}

function addIpAddress() {
    const input = document.getElementById('newIpAddress');
    const ip = input?.value.trim();
    
    if (!ip) {
        showNotification('Please enter an IP address', 'error');
        return;
    }
    
    if (window.securityState.ipWhitelist.includes(ip)) {
        showNotification('IP address already in whitelist', 'warning');
        return;
    }
    
    window.securityState.ipWhitelist.push(ip);
    renderIpWhitelist();
    input.value = '';
    showNotification('IP address added to whitelist', 'success');
    markUnsavedChanges();
}

function removeIpAddress(index) {
    window.securityState.ipWhitelist.splice(index, 1);
    renderIpWhitelist();
    showNotification('IP address removed from whitelist', 'success');
    markUnsavedChanges();
}

// ==================== BLOCKED PORTS ====================
function renderBlockedPorts() {
    const container = document.getElementById('blockedPorts');
    if (!container) return;
    
    container.innerHTML = '';
    
    window.securityState.blockedPorts.forEach((port, index) => {
        const span = document.createElement('span');
        span.className = 'bg-red-100 text-red-800 text-xs px-3 py-1 rounded-full font-mono flex items-center';
        span.innerHTML = `
            ${port}
            <button class="ml-1 text-red-500 hover:text-red-700" onclick="removeBlockedPort(${index})">
                <i class="fa-solid fa-times text-xs"></i>
            </button>
        `;
        container.appendChild(span);
    });
}

function addBlockedPort() {
    const input = document.getElementById('newBlockedPort');
    const port = parseInt(input?.value);
    
    if (!port || port < 1 || port > 65535) {
        showNotification('Please enter a valid port number (1-65535)', 'error');
        return;
    }
    
    if (window.securityState.blockedPorts.includes(port)) {
        showNotification('Port already blocked', 'warning');
        return;
    }
    
    window.securityState.blockedPorts.push(port);
    renderBlockedPorts();
    input.value = '';
    showNotification(`Port ${port} added to blocked list`, 'success');
    markUnsavedChanges();
}

function removeBlockedPort(index) {
    window.securityState.blockedPorts.splice(index, 1);
    renderBlockedPorts();
    showNotification('Port removed from blocked list', 'success');
    markUnsavedChanges();
}

// ==================== SSH ALLOWED COMMANDS ====================
function renderAllowedCommands() {
    const container = document.getElementById('allowedCommands');
    if (!container) return;
    
    container.innerHTML = '';
    
    window.securityState.allowedCommands.forEach((cmd, index) => {
        const span = document.createElement('span');
        span.className = 'bg-blue-100 text-blue-800 text-xs px-3 py-1 rounded-full font-mono flex items-center';
        span.innerHTML = `
            ${cmd}
            <button class="ml-1 text-blue-500 hover:text-blue-700" onclick="removeAllowedCommand(${index})">
                <i class="fa-solid fa-times text-xs"></i>
            </button>
        `;
        container.appendChild(span);
    });
}

function addAllowedCommand() {
    const input = document.getElementById('newCommand');
    const cmd = input?.value.trim();
    
    if (!cmd) {
        showNotification('Please enter a command', 'error');
        return;
    }
    
    if (window.securityState.allowedCommands.includes(cmd)) {
        showNotification('Command already in allowed list', 'warning');
        return;
    }
    
    window.securityState.allowedCommands.push(cmd);
    renderAllowedCommands();
    input.value = '';
    showNotification(`Command "${cmd}" added`, 'success');
    markUnsavedChanges();
}

function removeAllowedCommand(index) {
    window.securityState.allowedCommands.splice(index, 1);
    renderAllowedCommands();
    showNotification('Command removed', 'success');
    markUnsavedChanges();
}

// ==================== AUDIT LOG ====================
function loadAuditLogs() {
    // Mock data
    window.securityState.auditLogs = [
        { timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000), user: 'admin', event: 'Login', resource: '/api/auth/login', ip: '192.168.1.100', status: 'success' },
        { timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000), user: 'ops01', event: 'User Modified', resource: '/api/users/tech01', ip: '10.0.0.15', status: 'warning' },
        { timestamp: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000), user: 'unknown', event: 'Failed Login', resource: '/api/auth/login', ip: '203.0.113.5', status: 'failed' }
    ];
    
    filterAuditLog();
}

function filterAuditLog() {
    const timeRange = document.getElementById('auditTimeRange')?.value;
    const eventType = document.getElementById('auditEventType')?.value;
    const username = document.getElementById('auditUsername')?.value;
    const ipFilter = document.getElementById('auditIpAddress')?.value.toLowerCase();
    
    const now = new Date();
    let filteredLogs = [...window.securityState.auditLogs];
    
    // Filter by time range
    if (timeRange && timeRange !== 'custom') {
        const hours = parseInt(timeRange);
        const cutoffTime = new Date(now.getTime() - hours * 60 * 60 * 1000);
        filteredLogs = filteredLogs.filter(log => log.timestamp >= cutoffTime);
    }
    
    // Filter by event type
    if (eventType && eventType !== 'all') {
        filteredLogs = filteredLogs.filter(log => {
            if (eventType === 'login') return log.event.toLowerCase().includes('login');
            if (eventType === 'ssh') return log.event.toLowerCase().includes('ssh');
            if (eventType === 'user') return log.event.toLowerCase().includes('user');
            if (eventType === 'api') return log.event.toLowerCase().includes('api') || log.user === 'API Key';
            if (eventType === 'cert') return log.event.toLowerCase().includes('certificate');
            return true;
        });
    }
    
    // Filter by username
    if (username && username !== 'all') {
        filteredLogs = filteredLogs.filter(log => log.user.toLowerCase() === username.toLowerCase());
    }
    
    // Filter by IP
    if (ipFilter) {
        filteredLogs = filteredLogs.filter(log => log.ip.includes(ipFilter));
    }
    
    renderAuditLog(filteredLogs);
}

function renderAuditLog(logs) {
    const tbody = document.getElementById('auditLogTableBody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    logs.forEach(log => {
        const row = document.createElement('tr');
        row.className = 'audit-row hover:bg-slate-50';
        
        const timeStr = log.timestamp.toLocaleString('en-US', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        const statusClass = {
            'success': 'bg-green-100 text-green-800',
            'warning': 'bg-yellow-100 text-yellow-800',
            'failed': 'bg-red-100 text-red-800',
            'blocked': 'bg-red-100 text-red-800',
            'api': 'bg-blue-100 text-blue-800'
        }[log.status] || 'bg-slate-100 text-slate-800';
        
        row.innerHTML = `
            <td class="px-6 py-3 font-mono text-xs text-slate-600">${timeStr}</td>
            <td class="px-6 py-3 font-medium">${log.user}</td>
            <td class="px-6 py-3">${log.event}</td>
            <td class="px-6 py-3 text-slate-500">${log.resource}</td>
            <td class="px-6 py-3 font-mono text-xs">${log.ip}</td>
            <td class="px-6 py-3">
                <span class="${statusClass} text-xs px-2 py-0.5 rounded-full">
                    ${capitalizeFirstLetter(log.status)}
                </span>
            </td>
        `;
        tbody.appendChild(row);
    });
    
    const countElement = document.getElementById('auditLogCount');
    if (countElement) {
        countElement.textContent = `Showing ${logs.length} of ${window.securityState.auditLogs.length} events`;
    }
}

function refreshAuditLog() {
    // Simulate refresh
    showNotification('Audit log refreshed', 'success');
    filterAuditLog();
}

function exportAuditLog() {
    const logs = window.securityState.auditLogs.map(log => ({
        timestamp: log.timestamp.toISOString(),
        user: log.user,
        event: log.event,
        resource: log.resource,
        ip: log.ip,
        status: log.status
    }));
    
    // Use common.js downloadFile function
    if (typeof window.downloadFile === 'function') {
        const csvContent = "Timestamp,User,Event,Resource,IP Address,Status\n" +
            logs.map(log => 
                `"${log.timestamp}","${log.user}","${log.event}","${log.resource}","${log.ip}","${log.status}"`
            ).join("\n");
        
        window.downloadFile(csvContent, `audit-log-${new Date().toISOString().split('T')[0]}.csv`, 'text/csv');
        showNotification('Audit log exported successfully', 'success');
    } else {
        showNotification('Export feature not available', 'error');
    }
}

// ==================== SECURITY ACTIONS ====================
function runSecurityScan() {
    showNotification('Starting security scan...', 'info');
    
    // Simulate scan
    setTimeout(() => {
        const issues = Math.floor(Math.random() * 5);
        if (issues === 0) {
            showNotification('Security scan completed: No issues found', 'success');
            document.getElementById('securityStatus').innerHTML = `
                <i class="fa-solid fa-shield-halved"></i> System Secure
            `;
        } else {
            showNotification(`Security scan completed: Found ${issues} issues`, 'warning');
            document.getElementById('securityStatus').innerHTML = `
                <i class="fa-solid fa-triangle-exclamation"></i> ${issues} Issues Found
            `;
            document.getElementById('securityStatus').className = 
                'inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800';
        }
    }, 2000);
}

function resetToDefaults() {
    showConfirmationDialog('Reset all security settings to defaults? This cannot be undone.', 'Reset', 'Cancel')
        .then(confirmed => {
            if (confirmed) {
                // Reset form values
                document.getElementById('passwordMinLength').value = 8;
                document.getElementById('passwordExpiry').value = 90;
                document.getElementById('requireSpecialChars').checked = true;
                document.getElementById('requireNumbers').checked = true;
                document.getElementById('requireUppercase').checked = true;
                document.getElementById('preventReuse').checked = false;
                document.getElementById('lockoutAttempts').value = 5;
                document.getElementById('lockoutDuration').value = 15;
                document.getElementById('captchaToggle').checked = false;
                document.getElementById('sessionTimeout').value = 15;
                document.getElementById('maxSessions').value = 3;
                
                // Reset data
                loadInitialData();
                
                showNotification('All settings reset to defaults', 'success');
                markUnsavedChanges();
            }
        });
}

function lockSystem() {
    showConfirmationDialog('Lock the system? All users will be logged out immediately.', 'Lock', 'Cancel')
        .then(confirmed => {
            if (confirmed) {
                showNotification('System locked. All users logged out.', 'warning');
            }
        });
}

// ==================== SAVE SETTINGS ====================
function handleSaveAllSettings() {
    const settings = {
        authentication: {
            passwordMinLength: document.getElementById('passwordMinLength')?.value,
            passwordExpiry: document.getElementById('passwordExpiry')?.value,
            requireSpecialChars: document.getElementById('requireSpecialChars')?.checked,
            requireNumbers: document.getElementById('requireNumbers')?.checked,
            requireUppercase: document.getElementById('requireUppercase')?.checked,
            preventReuse: document.getElementById('preventReuse')?.checked,
            lockoutAttempts: document.getElementById('lockoutAttempts')?.value,
            lockoutDuration: document.getElementById('lockoutDuration')?.value,
            captchaEnabled: document.getElementById('captchaToggle')?.checked,
            sessionTimeout: document.getElementById('sessionTimeout')?.value,
            maxSessions: document.getElementById('maxSessions')?.value,
            twoFactorMode: document.querySelector('input[name="twoFactorMode"]:checked')?.value
        },
        users: window.securityState.users,
        apiKeys: window.securityState.apiKeys,
        firewallRules: window.securityState.firewallRules,
        ipWhitelist: window.securityState.ipWhitelist,
        blockedPorts: window.securityState.blockedPorts,
        allowedCommands: window.securityState.allowedCommands
    };
    
    const saveBtn = document.getElementById('save-btn');
    const originalText = saveBtn.innerHTML;
    
    // Show loading state
    saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Saving...';
    saveBtn.disabled = true;
    
    // Simulate API call
    setTimeout(() => {
        // Show success message
        saveBtn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Saved Successfully!';
        saveBtn.classList.remove('bg-primary', 'hover:bg-primaryHover');
        saveBtn.classList.add('bg-success', 'hover:bg-emerald-600');
        
        // Revert after 2 seconds
        setTimeout(() => {
            saveBtn.innerHTML = originalText;
            saveBtn.classList.remove('bg-success', 'hover:bg-emerald-600');
            saveBtn.classList.add('bg-primary', 'hover:bg-primaryHover');
            saveBtn.disabled = false;
        }, 2000);
        
        // Clear unsaved changes flag
        window.securityState.unsavedChanges = false;
        
        // Show notification
        showNotification('Security settings saved successfully!', 'success');
        
        console.log('Saved settings:', settings);
    }, 1500);
}

// ==================== UTILITY FUNCTIONS ====================
function loadInitialData() {
    loadUsers();
    loadApiKeys();
    loadFirewallRules();
    loadAuditLogs();
    renderRoles();
}

function renderRoles() {
    const rolesList = document.getElementById('rolesList');
    if (!rolesList) return;
    
    const roles = [
        { name: 'Admin', description: 'Full system access. Cannot be deleted.', users: 1, locked: true },
        { name: 'Engineer', description: 'Technical config & diagnostics.', users: 3, locked: true },
        { name: 'Technician', description: 'Device maintenance & sensor management.', users: 2, locked: false },
        { name: 'Operator', description: 'Basic monitoring and operations.', users: 1, locked: false },
        { name: 'Viewer', description: 'Read-only access to dashboards.', users: 0, locked: false }
    ];
    
    rolesList.innerHTML = roles.map(role => `
        <div class="p-4 hover:bg-slate-50 cursor-pointer group">
            <div class="flex justify-between items-center mb-1">
                <span class="font-medium text-slate-900 text-sm">${role.name}</span>
                <i class="fa-solid fa-${role.locked ? 'lock' : 'pencil'} text-slate-300 text-xs group-hover:text-primary"></i>
            </div>
            <p class="text-xs text-slate-500 mb-2">${role.description}</p>
            <div class="flex items-center justify-between text-xs">
                <span class="bg-slate-100 text-slate-600 px-2 py-0.5 rounded">${role.users} User${role.users !== 1 ? 's' : ''}</span>
                <span class="text-primary opacity-0 group-hover:opacity-100 transition">Edit Permissions ></span>
            </div>
        </div>
    `).join('');
}

function showCustomRoleModal() {
    showNotification('Custom role feature coming soon', 'info');
}

function regenerateWebhookSecret() {
    const secret = 'whsec_' + Array.from(crypto.getRandomValues(new Uint8Array(24)))
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');
    
    document.getElementById('webhookSecret').value = secret;
    showNotification('Webhook secret regenerated', 'success');
    markUnsavedChanges();
}

function simulateFileUpload(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    
    const filename = `uploaded_${inputId}_${Date.now()}.pem`;
    input.value = filename;
    showNotification(`File "${filename}" uploaded`, 'success');
    markUnsavedChanges();
}

function generateSelfSignedCert() {
    showNotification('Generating self-signed certificate...', 'info');
    
    setTimeout(() => {
        showNotification('Self-signed certificate generated successfully', 'success');
        markUnsavedChanges();
    }, 1000);
}

function getRoleColor(role) {
    const colors = {
        'admin': 'purple',
        'engineer': 'blue',
        'technician': 'blue',
        'operator': 'slate',
        'viewer': 'gray'
    };
    return colors[role] || 'slate';
}

function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
}