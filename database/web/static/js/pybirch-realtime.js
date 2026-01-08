/**
 * PyBirch Real-Time WebSocket Client
 * ===================================
 * Core WebSocket client for real-time updates using Socket.IO.
 * 
 * Features:
 * - Auto-reconnection with exponential backoff
 * - Room-based subscriptions for scalability
 * - Event dispatcher pattern
 * - Connection state management
 * 
 * Usage:
 *   const realtime = new PyBirchRealtime();
 *   realtime.connect();
 *   realtime.onScanStatus((data) => console.log(data));
 *   realtime.subscribeScan('SCAN_001');
 */

class PyBirchRealtime {
    constructor(options = {}) {
        this.socket = null;
        this.connected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
        this.reconnectDelay = options.reconnectDelay || 1000;
        this.maxReconnectDelay = options.maxReconnectDelay || 30000;
        
        // Subscription tracking
        this.subscriptions = {
            scans: new Set(),
            queues: new Set(),
            instruments: false,
            instrumentIds: new Set()
        };
        
        // Event callbacks
        this.callbacks = {
            connect: [],
            disconnect: [],
            scanStatus: [],
            queueStatus: [],
            dataPoint: [],
            instrumentStatus: [],
            instrumentPosition: [],
            queueLog: [],
            scanLog: [],
            error: []
        };
        
        // Connection status element ID
        this.statusElementId = options.statusElementId || 'connection-status';
    }
    
    /**
     * Connect to the WebSocket server
     */
    connect() {
        if (typeof io === 'undefined') {
            console.warn('Socket.IO not loaded. Real-time features disabled.');
            return false;
        }
        
        try {
            this.socket = io({
                transports: ['websocket', 'polling'],
                reconnection: true,
                reconnectionAttempts: this.maxReconnectAttempts,
                reconnectionDelay: this.reconnectDelay,
                reconnectionDelayMax: this.maxReconnectDelay
            });
            
            this._setupEventHandlers();
            return true;
        } catch (error) {
            console.error('Failed to initialize WebSocket:', error);
            this._triggerCallbacks('error', { type: 'connection', error: error.message });
            return false;
        }
    }
    
    /**
     * Disconnect from the WebSocket server
     */
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
            this.connected = false;
            this._updateStatusIndicator('disconnected');
        }
    }
    
    /**
     * Set up Socket.IO event handlers
     */
    _setupEventHandlers() {
        // Connection events
        this.socket.on('connect', () => {
            this.connected = true;
            this.reconnectAttempts = 0;
            this._updateStatusIndicator('connected');
            this._resubscribeAll();
            this._triggerCallbacks('connect', { timestamp: new Date().toISOString() });
            console.log('PyBirch Realtime: Connected');
        });
        
        this.socket.on('disconnect', (reason) => {
            this.connected = false;
            this._updateStatusIndicator('disconnected');
            this._triggerCallbacks('disconnect', { reason, timestamp: new Date().toISOString() });
            console.log('PyBirch Realtime: Disconnected -', reason);
        });
        
        this.socket.on('connect_error', (error) => {
            this.reconnectAttempts++;
            this._updateStatusIndicator('connecting');
            this._triggerCallbacks('error', { type: 'connect_error', error: error.message });
            console.warn('PyBirch Realtime: Connection error -', error.message);
        });
        
        // Business events
        this.socket.on('scan_status', (data) => {
            this._triggerCallbacks('scanStatus', data);
        });
        
        this.socket.on('queue_status', (data) => {
            this._triggerCallbacks('queueStatus', data);
        });
        
        this.socket.on('data_point', (data) => {
            this._triggerCallbacks('dataPoint', data);
        });
        
        this.socket.on('instrument_status', (data) => {
            this._triggerCallbacks('instrumentStatus', data);
        });
        
        this.socket.on('instrument_position', (data) => {
            this._triggerCallbacks('instrumentPosition', data);
        });
        
        this.socket.on('queue_log', (data) => {
            this._triggerCallbacks('queueLog', data);
        });
        
        this.socket.on('scan_log', (data) => {
            this._triggerCallbacks('scanLog', data);
        });
        
        // Subscription confirmations
        this.socket.on('subscribed', (data) => {
            console.log('PyBirch Realtime: Subscribed to', data);
        });
    }
    
    /**
     * Resubscribe to all rooms after reconnection
     */
    _resubscribeAll() {
        this.subscriptions.scans.forEach(scanId => {
            this.socket.emit('subscribe_scan', { scan_id: scanId });
        });
        
        this.subscriptions.queues.forEach(queueId => {
            this.socket.emit('subscribe_queue', { queue_id: queueId });
        });
        
        if (this.subscriptions.instruments) {
            this.socket.emit('subscribe_instruments');
        }
        
        if (this.subscriptions.allQueues) {
            this.socket.emit('subscribe_queues');
        }
        
        if (this.subscriptions.allScans) {
            this.socket.emit('subscribe_scans');
        }
        
        this.subscriptions.instrumentIds.forEach(instrumentId => {
            this.socket.emit('subscribe_instrument', { instrument_id: instrumentId });
        });
    }
    
    /**
     * Update connection status indicator in the DOM
     */
    _updateStatusIndicator(status) {
        const element = document.getElementById(this.statusElementId);
        if (element) {
            element.className = `connection-status ${status}`;
            element.title = status.charAt(0).toUpperCase() + status.slice(1);
        }
        
        // Also update any status text elements
        const textElements = document.querySelectorAll('.connection-status-text');
        textElements.forEach(el => {
            el.textContent = status.charAt(0).toUpperCase() + status.slice(1);
            el.className = `connection-status-text ${status}`;
        });
    }
    
    /**
     * Trigger registered callbacks for an event
     */
    _triggerCallbacks(event, data) {
        if (this.callbacks[event]) {
            this.callbacks[event].forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Error in ${event} callback:`, error);
                }
            });
        }
    }
    
    // ==================== Subscription Methods ====================
    
    /**
     * Subscribe to updates for a specific scan
     */
    subscribeScan(scanId) {
        if (!scanId) return;
        scanId = String(scanId);
        
        this.subscriptions.scans.add(scanId);
        if (this.connected && this.socket) {
            this.socket.emit('subscribe_scan', { scan_id: scanId });
        }
    }
    
    /**
     * Unsubscribe from a specific scan
     */
    unsubscribeScan(scanId) {
        if (!scanId) return;
        scanId = String(scanId);
        
        this.subscriptions.scans.delete(scanId);
        if (this.connected && this.socket) {
            this.socket.emit('unsubscribe_scan', { scan_id: scanId });
        }
    }
    
    /**
     * Subscribe to updates for a specific queue
     */
    subscribeQueue(queueId) {
        if (!queueId) return;
        queueId = String(queueId);
        
        this.subscriptions.queues.add(queueId);
        if (this.connected && this.socket) {
            this.socket.emit('subscribe_queue', { queue_id: queueId });
        }
    }
    
    /**
     * Unsubscribe from a specific queue
     */
    unsubscribeQueue(queueId) {
        if (!queueId) return;
        queueId = String(queueId);
        
        this.subscriptions.queues.delete(queueId);
        if (this.connected && this.socket) {
            this.socket.emit('unsubscribe_queue', { queue_id: queueId });
        }
    }
    
    /**
     * Subscribe to all instrument status updates
     */
    subscribeInstruments() {
        this.subscriptions.instruments = true;
        if (this.connected && this.socket) {
            this.socket.emit('subscribe_instruments');
        }
    }
    
    /**
     * Unsubscribe from instrument updates
     */
    unsubscribeInstruments() {
        this.subscriptions.instruments = false;
        if (this.connected && this.socket) {
            this.socket.emit('unsubscribe_instruments');
        }
    }
    
    /**
     * Subscribe to all queue status updates (global - for dashboard)
     */
    subscribeQueues() {
        this.subscriptions.allQueues = true;
        if (this.connected && this.socket) {
            this.socket.emit('subscribe_queues');
        }
    }
    
    /**
     * Unsubscribe from all queue updates
     */
    unsubscribeQueues() {
        this.subscriptions.allQueues = false;
        if (this.connected && this.socket) {
            this.socket.emit('unsubscribe_queues');
        }
    }
    
    /**
     * Subscribe to all scan status updates (global - for dashboard)
     */
    subscribeScans() {
        this.subscriptions.allScans = true;
        if (this.connected && this.socket) {
            this.socket.emit('subscribe_scans');
        }
    }
    
    /**
     * Unsubscribe from all scan updates
     */
    unsubscribeScans() {
        this.subscriptions.allScans = false;
        if (this.connected && this.socket) {
            this.socket.emit('unsubscribe_scans');
        }
    }
    
    /**
     * Subscribe to a specific instrument's position updates
     */
    subscribeInstrument(instrumentId) {
        if (!instrumentId) return;
        instrumentId = Number(instrumentId);
        
        this.subscriptions.instrumentIds.add(instrumentId);
        if (this.connected && this.socket) {
            this.socket.emit('subscribe_instrument', { instrument_id: instrumentId });
        }
    }
    
    /**
     * Unsubscribe from a specific instrument
     */
    unsubscribeInstrument(instrumentId) {
        if (!instrumentId) return;
        instrumentId = Number(instrumentId);
        
        this.subscriptions.instrumentIds.delete(instrumentId);
        if (this.connected && this.socket) {
            this.socket.emit('unsubscribe_instrument', { instrument_id: instrumentId });
        }
    }
    
    // ==================== Callback Registration ====================
    
    /**
     * Register callback for connection event
     */
    onConnect(callback) {
        this.callbacks.connect.push(callback);
        return this;
    }
    
    /**
     * Register callback for disconnection event
     */
    onDisconnect(callback) {
        this.callbacks.disconnect.push(callback);
        return this;
    }
    
    /**
     * Register callback for scan status updates
     */
    onScanStatus(callback) {
        this.callbacks.scanStatus.push(callback);
        return this;
    }
    
    /**
     * Register callback for queue status updates
     */
    onQueueStatus(callback) {
        this.callbacks.queueStatus.push(callback);
        return this;
    }
    
    /**
     * Register callback for data point events (live charting)
     */
    onDataPoint(callback) {
        this.callbacks.dataPoint.push(callback);
        return this;
    }
    
    /**
     * Register callback for instrument status updates
     */
    onInstrumentStatus(callback) {
        this.callbacks.instrumentStatus.push(callback);
        return this;
    }
    
    /**
     * Register callback for instrument position updates
     */
    onInstrumentPosition(callback) {
        this.callbacks.instrumentPosition.push(callback);
        return this;
    }
    
    /**
     * Register callback for queue log entries
     */
    onQueueLog(callback) {
        this.callbacks.queueLog.push(callback);
        return this;
    }
    
    /**
     * Register callback for scan log entries
     */
    onScanLog(callback) {
        this.callbacks.scanLog.push(callback);
        return this;
    }
    
    /**
     * Register callback for errors
     */
    onError(callback) {
        this.callbacks.error.push(callback);
        return this;
    }
    
    /**
     * Remove all callbacks for a specific event
     */
    clearCallbacks(event) {
        if (this.callbacks[event]) {
            this.callbacks[event] = [];
        }
    }
    
    // ==================== Utility Methods ====================
    
    /**
     * Check if currently connected
     */
    isConnected() {
        return this.connected;
    }
    
    /**
     * Get current subscriptions
     */
    getSubscriptions() {
        return {
            scans: Array.from(this.subscriptions.scans),
            queues: Array.from(this.subscriptions.queues),
            instruments: this.subscriptions.instruments,
            instrumentIds: Array.from(this.subscriptions.instrumentIds)
        };
    }
}

// ==================== Global Instance ====================

// Create global instance for easy access
window.pybirchRealtime = null;

/**
 * Initialize the global PyBirch realtime instance
 * Call this after the page loads
 */
function initPyBirchRealtime(options = {}) {
    if (!window.pybirchRealtime) {
        window.pybirchRealtime = new PyBirchRealtime(options);
    }
    return window.pybirchRealtime;
}

// ==================== UI Helper Functions ====================

/**
 * Update a status badge element
 */
function updateStatusBadge(element, status) {
    if (!element) return;
    
    // Remove existing status classes
    element.className = element.className.replace(/status-\w+/g, '');
    element.classList.add(`status-badge`, `status-${status}`);
    element.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    
    // Add highlight animation
    element.classList.add('status-updated');
    setTimeout(() => element.classList.remove('status-updated'), 2000);
}

/**
 * Update a progress bar element
 */
function updateProgressBar(element, progress, completed, total) {
    if (!element) return;
    
    const fillElement = element.querySelector('.progress-fill');
    if (fillElement) {
        const percent = Math.min(100, Math.max(0, progress * 100));
        fillElement.style.width = `${percent}%`;
    }
    
    const textElement = element.querySelector('.progress-text') || element.nextElementSibling;
    if (textElement && completed !== undefined && total !== undefined) {
        textElement.textContent = `${completed} / ${total}`;
    }
}

/**
 * Highlight a table row briefly
 */
function highlightRow(row) {
    if (!row) return;
    row.classList.add('status-updated');
    setTimeout(() => row.classList.remove('status-updated'), 2000);
}

/**
 * Format a timestamp for display
 */
function formatTimestamp(isoString) {
    const date = new Date(isoString);
    return date.toLocaleTimeString();
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
