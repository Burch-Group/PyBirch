/**
 * Scan Real-Time Updates
 * ======================
 * Handles real-time updates for scan pages including live data charting.
 */

class ScanRealtimeManager {
    /**
     * Initialize scan realtime manager
     * @param {string|number} scanId - The scan ID to monitor
     * @param {Object} chartConfig - Optional chart configuration
     */
    constructor(scanId, chartConfig = {}) {
        this.scanId = String(scanId);
        this.realtime = window.pybirchRealtime;
        this.chart = null;
        this.chartConfig = chartConfig;
        this.dataBuffer = {};  // Buffer for each measurement
        this.maxDataPoints = chartConfig.maxDataPoints || 1000;
        this.startTime = null;
        this.elapsedTimeInterval = null;
        
        if (this.realtime) {
            this._setupHandlers();
            this.realtime.subscribeScan(this.scanId);
        }
    }
    
    /**
     * Set up event handlers
     */
    _setupHandlers() {
        // Scan status updates
        this.realtime.onScanStatus((data) => {
            if (data.scan_id === this.scanId) {
                this.updateStatus(data.status, data.message);
                if (data.progress !== undefined) {
                    this.updateProgress(data.progress);
                }
                
                // Handle lifecycle events
                if (data.status === 'running' && !this.startTime) {
                    this.startTime = new Date();
                    this._startElapsedTimer();
                } else if (data.status === 'completed' || data.status === 'aborted' || data.status === 'failed') {
                    this._stopElapsedTimer();
                }
            }
        });
        
        // Live data points
        this.realtime.onDataPoint((data) => {
            if (data.scan_id === this.scanId) {
                this.addDataPoint(data.measurement, data.data, data.sequence_index);
            }
        });
    }
    
    /**
     * Update scan status badge
     */
    updateStatus(status, message) {
        const badge = document.querySelector('.status-badge');
        if (badge) {
            updateStatusBadge(badge, status);
        }
        
        // Update status message if element exists
        const messageEl = document.getElementById('scan-status-message');
        if (messageEl && message) {
            messageEl.textContent = message;
        }
        
        // Update live indicator visibility
        const liveIndicator = document.querySelector('.live-indicator');
        if (liveIndicator) {
            liveIndicator.style.display = status === 'running' ? 'inline-flex' : 'none';
        }
    }
    
    /**
     * Update progress bar
     */
    updateProgress(progress) {
        const progressBar = document.querySelector('.progress-bar');
        if (progressBar) {
            updateProgressBar(progressBar, progress);
        }
        
        // Update percentage text
        const percentEl = document.getElementById('scan-progress-percent');
        if (percentEl) {
            percentEl.textContent = `${Math.round(progress * 100)}%`;
        }
        
        // Update point count if we have total
        const totalPoints = parseInt(document.getElementById('scan-total-points')?.textContent || '0');
        if (totalPoints > 0) {
            const completedEl = document.getElementById('scan-completed-points');
            if (completedEl) {
                completedEl.textContent = Math.round(progress * totalPoints);
            }
        }
    }
    
    /**
     * Initialize Chart.js for live data visualization
     */
    initChart(canvasId, options = {}) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || typeof Chart === 'undefined') {
            console.warn('Chart.js not available or canvas not found');
            return null;
        }
        
        const ctx = canvas.getContext('2d');
        
        this.chart = new Chart(ctx, {
            type: options.type || 'scatter',
            data: {
                datasets: []
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 0  // Disable animation for real-time performance
                },
                scales: {
                    x: {
                        type: 'linear',
                        title: {
                            display: true,
                            text: options.xLabel || 'X'
                        }
                    },
                    y: {
                        type: 'linear',
                        title: {
                            display: true,
                            text: options.yLabel || 'Y'
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    title: {
                        display: !!options.title,
                        text: options.title || ''
                    }
                },
                ...options.chartOptions
            }
        });
        
        return this.chart;
    }
    
    /**
     * Add a data point to the chart
     */
    addDataPoint(measurement, data, sequenceIndex) {
        // Initialize buffer for this measurement if needed
        if (!this.dataBuffer[measurement]) {
            this.dataBuffer[measurement] = [];
            
            // Add new dataset to chart if exists
            if (this.chart) {
                const colorIndex = Object.keys(this.dataBuffer).length - 1;
                const colors = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];
                const color = colors[colorIndex % colors.length];
                
                this.chart.data.datasets.push({
                    label: measurement,
                    data: [],
                    borderColor: color,
                    backgroundColor: color + '40',
                    pointRadius: 2,
                    pointHoverRadius: 4,
                    showLine: true,
                    tension: 0.1
                });
            }
        }
        
        // Add to buffer
        this.dataBuffer[measurement].push({ ...data, _seq: sequenceIndex });
        
        // Trim buffer if too large
        if (this.dataBuffer[measurement].length > this.maxDataPoints) {
            this.dataBuffer[measurement].shift();
        }
        
        // Update chart
        if (this.chart) {
            this._updateChart(measurement, data);
        }
        
        // Update data point counter
        this._updateDataPointCounter();
    }
    
    /**
     * Update chart with new data point
     */
    _updateChart(measurement, data) {
        const datasetIndex = Object.keys(this.dataBuffer).indexOf(measurement);
        if (datasetIndex === -1 || !this.chart.data.datasets[datasetIndex]) return;
        
        // Determine x and y values from data
        const keys = Object.keys(data).filter(k => !k.startsWith('_'));
        let x, y;
        
        if (keys.length >= 2) {
            // Use first two columns as x, y
            x = data[keys[0]];
            y = data[keys[1]];
        } else if (keys.length === 1) {
            // Single value - use sequence as x
            x = this.dataBuffer[measurement].length - 1;
            y = data[keys[0]];
        } else {
            return;
        }
        
        // Add point to dataset
        this.chart.data.datasets[datasetIndex].data.push({ x, y });
        
        // Trim dataset if too large
        const maxPoints = this.maxDataPoints;
        if (this.chart.data.datasets[datasetIndex].data.length > maxPoints) {
            this.chart.data.datasets[datasetIndex].data.shift();
        }
        
        // Update chart (throttled)
        if (!this._chartUpdatePending) {
            this._chartUpdatePending = true;
            requestAnimationFrame(() => {
                this.chart.update('none');
                this._chartUpdatePending = false;
            });
        }
    }
    
    /**
     * Update data point counter in UI
     */
    _updateDataPointCounter() {
        const counter = document.getElementById('live-data-count');
        if (counter) {
            let total = 0;
            for (const measurement in this.dataBuffer) {
                total += this.dataBuffer[measurement].length;
            }
            counter.textContent = total;
        }
    }
    
    /**
     * Start elapsed time display
     */
    _startElapsedTimer() {
        const elapsedEl = document.getElementById('scan-elapsed-time');
        if (!elapsedEl) return;
        
        this.elapsedTimeInterval = setInterval(() => {
            const elapsed = Math.floor((new Date() - this.startTime) / 1000);
            const hours = Math.floor(elapsed / 3600);
            const minutes = Math.floor((elapsed % 3600) / 60);
            const seconds = elapsed % 60;
            
            if (hours > 0) {
                elapsedEl.textContent = `${hours}h ${minutes}m ${seconds}s`;
            } else if (minutes > 0) {
                elapsedEl.textContent = `${minutes}m ${seconds}s`;
            } else {
                elapsedEl.textContent = `${seconds}s`;
            }
        }, 1000);
    }
    
    /**
     * Stop elapsed time display
     */
    _stopElapsedTimer() {
        if (this.elapsedTimeInterval) {
            clearInterval(this.elapsedTimeInterval);
            this.elapsedTimeInterval = null;
        }
    }
    
    /**
     * Get buffered data for a measurement
     */
    getData(measurement) {
        return this.dataBuffer[measurement] || [];
    }
    
    /**
     * Get all buffered data
     */
    getAllData() {
        return { ...this.dataBuffer };
    }
    
    /**
     * Clear chart and data buffer
     */
    clearData() {
        this.dataBuffer = {};
        if (this.chart) {
            this.chart.data.datasets = [];
            this.chart.update();
        }
    }
    
    /**
     * Clean up subscriptions and timers
     */
    destroy() {
        if (this.realtime) {
            this.realtime.unsubscribeScan(this.scanId);
        }
        this._stopElapsedTimer();
        if (this.chart) {
            this.chart.destroy();
        }
    }
}

/**
 * Scan List Page Manager
 * Handles real-time updates on the scans list page
 */
class ScanListRealtimeManager {
    constructor() {
        this.realtime = window.pybirchRealtime;
        
        if (this.realtime) {
            this._setupHandlers();
        }
    }
    
    _setupHandlers() {
        this.realtime.onScanStatus((data) => {
            this.updateScanRow(data.scan_id, data.status, data.progress);
        });
    }
    
    /**
     * Update a scan row in the list
     */
    updateScanRow(scanId, status, progress) {
        const rows = document.querySelectorAll('tbody tr');
        rows.forEach(row => {
            // Check data attribute first
            const rowScanId = row.getAttribute('data-scan-id');
            if (rowScanId === String(scanId)) {
                this._updateRow(row, status);
                return;
            }
            
            // Fall back to link check
            const link = row.querySelector('a[href*="/scans/"]');
            if (link) {
                const href = link.getAttribute('href');
                if (href && (link.textContent.includes(scanId) || href.includes(`/scans/${scanId}`))) {
                    this._updateRow(row, status);
                }
            }
        });
    }
    
    _updateRow(row, status) {
        const badge = row.querySelector('.status-badge');
        if (badge) {
            updateStatusBadge(badge, status);
        }
        highlightRow(row);
    }
}

// Auto-initialize on scans list page
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the scans list page
    if (window.location.pathname === '/scans' || window.location.pathname === '/scans/') {
        window.scanListManager = new ScanListRealtimeManager();
    }
});
