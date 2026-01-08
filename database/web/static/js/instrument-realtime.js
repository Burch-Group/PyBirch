/**
 * Instrument Real-Time Updates
 * ============================
 * Handles real-time updates for instrument pages including position tracking.
 */

class InstrumentRealtimeManager {
    /**
     * Initialize instrument realtime manager
     * @param {number} instrumentId - The instrument database ID to monitor
     */
    constructor(instrumentId) {
        this.instrumentId = Number(instrumentId);
        this.realtime = window.pybirchRealtime;
        this.positionElements = {};
        this.statusElement = null;
        
        if (this.realtime) {
            this._setupHandlers();
            this.realtime.subscribeInstrument(this.instrumentId);
            this.realtime.subscribeInstruments();  // Also get general status updates
        }
    }
    
    /**
     * Set up event handlers
     */
    _setupHandlers() {
        // Instrument status updates
        this.realtime.onInstrumentStatus((data) => {
            if (data.instrument_id === this.instrumentId) {
                this.updateStatus(data.status, data.error);
                if (data.settings) {
                    this.updateSettings(data.settings);
                }
            }
        });
        
        // Instrument position updates
        this.realtime.onInstrumentPosition((data) => {
            if (data.instrument_id === this.instrumentId) {
                this.updatePosition(data.position, data.target, data.is_moving);
                if (data.status) {
                    this.updateMovementStatus(data.status);
                }
            }
        });
    }
    
    /**
     * Update instrument status badge
     */
    updateStatus(status, error) {
        const badge = document.querySelector('.status-badge');
        if (badge) {
            updateStatusBadge(badge, status);
        }
        
        // Update status indicator
        const indicator = document.getElementById('instrument-status-indicator');
        if (indicator) {
            indicator.className = `status-indicator status-${status}`;
            indicator.title = status;
        }
        
        // Show/hide error panel
        const errorPanel = document.getElementById('instrument-error-panel');
        if (errorPanel) {
            if (error && status === 'error') {
                errorPanel.style.display = 'block';
                errorPanel.querySelector('.error-message').textContent = error;
            } else {
                errorPanel.style.display = 'none';
            }
        }
    }
    
    /**
     * Update position display
     */
    updatePosition(position, target, isMoving) {
        if (!position) return;
        
        for (const [axis, value] of Object.entries(position)) {
            const axisKey = axis.toLowerCase();
            
            // Find or create position element
            let element = document.getElementById(`position-${axisKey}`);
            if (!element) {
                element = document.querySelector(`[data-axis="${axisKey}"] .position-value`);
            }
            
            if (element) {
                // Format value
                const formattedValue = typeof value === 'number' ? value.toFixed(4) : value;
                element.textContent = formattedValue;
                
                // Add moving class for animation
                if (isMoving) {
                    element.classList.add('moving');
                } else {
                    element.classList.remove('moving');
                }
            }
            
            // Update target if provided
            if (target && target[axis] !== undefined) {
                const targetElement = document.getElementById(`target-${axisKey}`);
                if (targetElement) {
                    const formattedTarget = typeof target[axis] === 'number' ? target[axis].toFixed(4) : target[axis];
                    targetElement.textContent = `→ ${formattedTarget}`;
                    targetElement.style.display = isMoving ? 'inline' : 'none';
                }
            }
        }
        
        // Update position panel overall state
        const positionPanel = document.getElementById('position-panel');
        if (positionPanel) {
            if (isMoving) {
                positionPanel.classList.add('is-moving');
            } else {
                positionPanel.classList.remove('is-moving');
            }
        }
    }
    
    /**
     * Update movement status text
     */
    updateMovementStatus(status) {
        const statusText = document.getElementById('movement-status-text');
        if (statusText) {
            const statusLabels = {
                'idle': 'Idle',
                'moving': 'Moving...',
                'homing': 'Homing...',
                'error': 'Error',
                'connected': 'Connected',
                'disconnected': 'Disconnected'
            };
            statusText.textContent = statusLabels[status] || status;
            statusText.className = `movement-status-text status-${status}`;
        }
    }
    
    /**
     * Update settings display
     */
    updateSettings(settings) {
        const settingsContainer = document.getElementById('current-settings');
        if (settingsContainer && settings) {
            settingsContainer.textContent = JSON.stringify(settings, null, 2);
        }
    }
    
    /**
     * Clean up subscriptions
     */
    destroy() {
        if (this.realtime) {
            this.realtime.unsubscribeInstrument(this.instrumentId);
        }
    }
}

/**
 * Instrument List Page Manager
 * Handles real-time updates on the instruments list page
 */
class InstrumentListRealtimeManager {
    constructor() {
        this.realtime = window.pybirchRealtime;
        
        if (this.realtime) {
            this._setupHandlers();
            this.realtime.subscribeInstruments();
        }
    }
    
    _setupHandlers() {
        // Instrument status updates
        this.realtime.onInstrumentStatus((data) => {
            this.updateInstrumentRow(data.instrument_id, data.status, data.instrument_name);
        });
        
        // Position updates (for showing moving indicators)
        this.realtime.onInstrumentPosition((data) => {
            this.updateInstrumentMoving(data.instrument_id, data.is_moving, data.status);
        });
    }
    
    /**
     * Update an instrument row in the list
     */
    updateInstrumentRow(instrumentId, status, name) {
        const rows = document.querySelectorAll('tbody tr');
        rows.forEach(row => {
            const link = row.querySelector('a[href*="/instruments/"]');
            if (link) {
                const href = link.getAttribute('href');
                const match = href?.match(/\/instruments\/(\d+)/);
                const rowId = match ? parseInt(match[1]) : null;
                
                if (rowId === instrumentId) {
                    // Update status badge
                    const badge = row.querySelector('.status-badge');
                    if (badge && status) {
                        updateStatusBadge(badge, status);
                    }
                    
                    // Add/update connection indicator
                    let indicator = row.querySelector('.instrument-connection');
                    if (!indicator) {
                        const nameCell = row.querySelector('td:first-child a') || row.querySelector('td:nth-child(2) a');
                        if (nameCell) {
                            indicator = document.createElement('span');
                            indicator.className = 'instrument-connection';
                            nameCell.parentNode.insertBefore(indicator, nameCell);
                        }
                    }
                    if (indicator) {
                        indicator.className = `instrument-connection connection-${status}`;
                        indicator.title = status;
                    }
                    
                    highlightRow(row);
                }
            }
        });
    }
    
    /**
     * Update moving indicator for an instrument
     */
    updateInstrumentMoving(instrumentId, isMoving, status) {
        const rows = document.querySelectorAll('tbody tr');
        rows.forEach(row => {
            const link = row.querySelector('a[href*="/instruments/"]');
            if (link) {
                const href = link.getAttribute('href');
                const match = href?.match(/\/instruments\/(\d+)/);
                const rowId = match ? parseInt(match[1]) : null;
                
                if (rowId === instrumentId) {
                    if (isMoving) {
                        row.classList.add('instrument-moving');
                    } else {
                        row.classList.remove('instrument-moving');
                    }
                }
            }
        });
    }
}

// Auto-initialize on instruments list page
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the instruments list page
    if (window.location.pathname === '/instruments' || window.location.pathname === '/instruments/') {
        window.instrumentListManager = new InstrumentListRealtimeManager();
    }
});
