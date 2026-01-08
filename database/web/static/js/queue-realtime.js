/**
 * Queue Real-Time Updates
 * =======================
 * Handles real-time updates for queue pages.
 */

class QueueRealtimeManager {
    /**
     * Initialize queue realtime manager
     * @param {string|number} queueId - The queue ID to monitor
     */
    constructor(queueId) {
        this.queueId = String(queueId);
        this.realtime = window.pybirchRealtime;
        this.logContainer = null;
        this.maxLogEntries = 100;
        
        if (this.realtime) {
            this._setupHandlers();
            this.realtime.subscribeQueue(this.queueId);
        }
    }
    
    /**
     * Set up event handlers
     */
    _setupHandlers() {
        // Queue status updates
        this.realtime.onQueueStatus((data) => {
            if (data.queue_id === this.queueId || !data.queue_id) {
                this.updateStatus(data.status);
                if (data.completed_scans !== undefined && data.total_scans !== undefined) {
                    this.updateProgress(data.completed_scans, data.total_scans);
                }
                if (data.current_scan) {
                    this.highlightCurrentScan(data.current_scan);
                }
            }
        });
        
        // Queue log entries
        this.realtime.onQueueLog((data) => {
            if (data.queue_id === this.queueId) {
                this.appendLog(data.level, data.message, data.timestamp, data.scan_id);
            }
        });
        
        // Scan status updates (for scans in this queue)
        this.realtime.onScanStatus((data) => {
            this.updateScanInList(data.scan_id, data.status, data.progress);
        });
    }
    
    /**
     * Update queue status badge
     */
    updateStatus(status) {
        const badge = document.querySelector('.status-badge');
        if (badge) {
            updateStatusBadge(badge, status);
        }
        
        // Also update in header if exists
        const headerBadge = document.querySelector('.detail-header .status-badge');
        if (headerBadge) {
            updateStatusBadge(headerBadge, status);
        }
    }
    
    /**
     * Update progress bar and text
     */
    updateProgress(completed, total) {
        const progressBar = document.querySelector('.progress-bar');
        if (progressBar) {
            const progress = total > 0 ? completed / total : 0;
            updateProgressBar(progressBar, progress, completed, total);
        }
        
        // Update progress text
        const progressText = document.querySelector('.progress-text, dd:has(.progress-bar) + dd, .progress-bar + *');
        if (progressText && progressText.textContent.includes('/')) {
            progressText.textContent = `${completed} / ${total} scans`;
        }
    }
    
    /**
     * Highlight the currently running scan in the list
     */
    highlightCurrentScan(scanId) {
        // Remove previous highlight
        document.querySelectorAll('tr.current-scan').forEach(row => {
            row.classList.remove('current-scan');
        });
        
        // Find and highlight current scan row
        const rows = document.querySelectorAll('tbody tr');
        rows.forEach(row => {
            const link = row.querySelector('a[href*="/scans/"]');
            if (link && link.textContent.includes(scanId)) {
                row.classList.add('current-scan');
                highlightRow(row);
            }
        });
    }
    
    /**
     * Update a scan's status in the queue's scan list
     */
    updateScanInList(scanId, status, progress) {
        const rows = document.querySelectorAll('tbody tr');
        rows.forEach(row => {
            const link = row.querySelector('a[href*="/scans/"]');
            if (link) {
                // Check if this row is for the scan
                const href = link.getAttribute('href');
                if (href && (link.textContent.includes(scanId) || href.includes(scanId))) {
                    // Update status badge
                    const badge = row.querySelector('.status-badge');
                    if (badge) {
                        updateStatusBadge(badge, status);
                    }
                    
                    // Update progress cell if exists
                    const progressCell = row.querySelector('td:nth-child(4)');
                    if (progressCell && progress !== undefined) {
                        const total = progressCell.textContent.split('/')[1]?.trim() || '?';
                        const completed = Math.round(progress * parseInt(total) || 0);
                        progressCell.textContent = `${completed} / ${total}`;
                    }
                    
                    highlightRow(row);
                }
            }
        });
    }
    
    /**
     * Set log container element
     */
    setLogContainer(element) {
        this.logContainer = element;
    }
    
    /**
     * Append a log entry to the log panel
     */
    appendLog(level, message, timestamp, scanId) {
        if (!this.logContainer) {
            this.logContainer = document.getElementById('queue-log-panel');
        }
        
        if (!this.logContainer) return;
        
        const entry = document.createElement('div');
        entry.className = `log-entry ${level}`;
        
        const time = formatTimestamp(timestamp);
        const scanInfo = scanId ? ` [${escapeHtml(scanId)}]` : '';
        
        entry.innerHTML = `<span class="log-timestamp">${time}</span>${scanInfo} ${escapeHtml(message)}`;
        
        this.logContainer.appendChild(entry);
        
        // Limit entries
        while (this.logContainer.children.length > this.maxLogEntries) {
            this.logContainer.removeChild(this.logContainer.firstChild);
        }
        
        // Auto-scroll to bottom
        this.logContainer.scrollTop = this.logContainer.scrollHeight;
    }
    
    /**
     * Clean up subscriptions
     */
    destroy() {
        if (this.realtime) {
            this.realtime.unsubscribeQueue(this.queueId);
        }
    }
}

/**
 * Queue List Page Manager
 * Handles real-time updates on the queues list page
 */
class QueueListRealtimeManager {
    constructor() {
        this.realtime = window.pybirchRealtime;
        
        if (this.realtime) {
            this._setupHandlers();
        }
    }
    
    _setupHandlers() {
        this.realtime.onQueueStatus((data) => {
            this.updateQueueRow(data.queue_id, data.status, data.completed_scans, data.total_scans);
        });
    }
    
    /**
     * Update a queue row in the list
     */
    updateQueueRow(queueId, status, completed, total) {
        const rows = document.querySelectorAll('tbody tr');
        rows.forEach(row => {
            const link = row.querySelector('a[href*="/queues/"]');
            if (link) {
                const href = link.getAttribute('href');
                // Extract queue ID from href
                const match = href?.match(/\/queues\/(\d+)/);
                const rowQueueId = match ? match[1] : null;
                
                if (rowQueueId === String(queueId) || link.textContent.includes(queueId)) {
                    // Update status badge
                    const badge = row.querySelector('.status-badge');
                    if (badge && status) {
                        updateStatusBadge(badge, status);
                    }
                    
                    // Update progress cell (usually 5th column)
                    if (completed !== undefined && total !== undefined) {
                        const progressCell = row.querySelector('td:nth-child(5)');
                        if (progressCell) {
                            progressCell.textContent = `${completed} / ${total}`;
                        }
                    }
                    
                    highlightRow(row);
                }
            }
        });
    }
}

// Auto-initialize on queues list page
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the queues list page
    if (window.location.pathname === '/queues' || window.location.pathname === '/queues/') {
        window.queueListManager = new QueueListRealtimeManager();
    }
});
