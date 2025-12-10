// shared-config.js
class SharedConfig {
    constructor() {
        // Load from localStorage or initialize with defaults
        this.load();
        
        // If no config exists, initialize with empty structure
        if (!this.config) {
            this.config = {
                eventClasses: [],
                alertDefinitions: [],
                channels: [],
                routingRules: [],
                notificationTypes: [],
                lastSync: new Date().toISOString()
            };
            this.save();
        }
    }
    
    load() {
        try {
            const saved = localStorage.getItem('univa_shared_config');
            if (saved) {
                this.config = JSON.parse(saved);
                console.log('Shared config loaded:', this.config);
            }
        } catch (error) {
            console.error('Error loading shared config:', error);
            this.config = null;
        }
    }
    
    save() {
        try {
            this.config.lastSync = new Date().toISOString();
            localStorage.setItem('univa_shared_config', JSON.stringify(this.config));
            console.log('Shared config saved');
        } catch (error) {
            console.error('Error saving shared config:', error);
        }
    }
    
    // Sync from other systems
    syncFromAlertsSystem(data) {
        if (data.eventClasses) {
            this.config.eventClasses = data.eventClasses;
        }
        if (data.alertDefinitions) {
            this.config.alertDefinitions = data.alertDefinitions;
        }
        this.save();
    }
    
    syncFromRulesEngine(data) {
        if (data.rules) {
            // Map rules to alert definitions
            const alertDefs = data.rules.map(rule => ({
                id: `RULE-${rule.id || Date.now()}`,
                name: rule.name,
                code: this.generateAlertCode(rule),
                class: this.getEventClassForSeverity(rule.severity),
                source: rule.device || 'Custom',
                enabled: rule.enabled !== false
            }));
            
            // Merge with existing alert definitions
            this.config.alertDefinitions = [
                ...this.config.alertDefinitions.filter(ad => !ad.id.startsWith('RULE-')),
                ...alertDefs
            ];
        }
        this.save();
    }
    
    syncFromNotificationsSystem(data) {
        if (data.channels) {
            this.config.channels = data.channels;
        }
        if (data.notificationTypes) {
            this.config.notificationTypes = data.notificationTypes;
        }
        this.save();
    }
    
    // Helper methods
    generateAlertCode(rule) {
        const prefix = rule.triggerType === 'tag' ? 'T' : 
                      rule.triggerType === 'device' ? 'D' : 
                      rule.triggerType === 'schedule' ? 'S' : 'C';
        return `${prefix}${String(rule.id || Date.now()).slice(-4)}`;
    }
    
    getEventClassForSeverity(severity) {
        const severityMap = {
            5: 'Critical Fault',
            4: 'Major Warning',
            3: 'Warning',
            2: 'Minor Info',
            1: 'Information'
        };
        return severityMap[severity] || 'Information';
    }
    
    // Get data for each system
    getEventClasses() {
        return this.config.eventClasses || [];
    }
    
    getAlertDefinitions() {
        return this.config.alertDefinitions || [];
    }
    
    getChannels() {
        return this.config.channels || [];
    }
    
    getNotificationTypes() {
        return this.config.notificationTypes || [];
    }
    
    // Check if sync is needed
    needsSync() {
        const lastSync = new Date(this.config.lastSync);
        const now = new Date();
        const hoursSinceSync = (now - lastSync) / (1000 * 60 * 60);
        return hoursSinceSync > 1; // More than 1 hour since last sync
    }
}

// Create global instance
window.sharedConfig = new SharedConfig();