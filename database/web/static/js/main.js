/**
 * PyBirch Database Web UI JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize copy buttons
    initCopyButtons();
    
    // Initialize search autocomplete
    initSearchAutocomplete();
    
    // Initialize QR scanner modal
    initQRScannerModal();
});

/**
 * Copy to clipboard functionality
 */
function initCopyButtons() {
    document.querySelectorAll('.copy-btn').forEach(button => {
        button.addEventListener('click', function() {
            const text = this.dataset.copy;
            navigator.clipboard.writeText(text).then(() => {
                const originalText = this.textContent;
                this.textContent = 'Copied!';
                setTimeout(() => {
                    this.textContent = originalText;
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy:', err);
            });
        });
    });
}

/**
 * Search autocomplete (placeholder for future enhancement)
 */
function initSearchAutocomplete() {
    const searchInput = document.querySelector('.nav-search input');
    if (!searchInput) return;
    
    let debounceTimeout;
    
    searchInput.addEventListener('input', function() {
        clearTimeout(debounceTimeout);
        
        const query = this.value.trim();
        if (query.length < 2) return;
        
        debounceTimeout = setTimeout(() => {
            // Future: Could add autocomplete dropdown here
            // fetch(`/api/search?q=${encodeURIComponent(query)}&limit=5`)
        }, 300);
    });
}

/**
 * Handle PyBirch URI links
 * If PyBirch isn't registered as a protocol handler, show a helpful message
 */
document.querySelectorAll('a[href^="pybirch://"]').forEach(link => {
    link.addEventListener('click', function(e) {
        // Store the original href
        const pybirchUri = this.href;
        
        // Try to open - if it fails, the protocol isn't registered
        // We can't detect this directly, so we'll just let it try
        
        // Show a brief indicator that we tried
        const originalText = this.textContent;
        this.textContent = 'Opening...';
        
        setTimeout(() => {
            this.textContent = originalText;
        }, 1500);
    });
});

/**
 * Confirm dangerous actions
 */
document.querySelectorAll('[data-confirm]').forEach(element => {
    element.addEventListener('click', function(e) {
        const message = this.dataset.confirm || 'Are you sure?';
        if (!confirm(message)) {
            e.preventDefault();
        }
    });
});

/**
 * Format dates to local timezone
 */
document.querySelectorAll('[data-datetime]').forEach(element => {
    const isoDate = element.dataset.datetime;
    if (isoDate) {
        const date = new Date(isoDate);
        element.textContent = date.toLocaleString();
    }
});

/**
 * Pin/Unpin functionality
 */
function initPinButtons() {
    document.querySelectorAll('.pin-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            const entityType = this.dataset.entityType;
            const entityId = this.dataset.entityId;
            const isPinned = this.classList.contains('pinned');
            const url = isPinned 
                ? `/unpin/${entityType}/${entityId}` 
                : `/pin/${entityType}/${entityId}`;
            
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Reload page to reorder items
                    window.location.reload();
                } else if (data.error) {
                    alert(data.error);
                }
            })
            .catch(err => {
                console.error('Pin error:', err);
                // Fallback: submit as form
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = url;
                document.body.appendChild(form);
                form.submit();
            });
        });
    });
}

// Initialize pin buttons on page load
document.addEventListener('DOMContentLoaded', function() {
    initPinButtons();
});

/**
 * Live search filter for tables
 */
function initTableFilter(inputSelector, tableSelector) {
    const input = document.querySelector(inputSelector);
    const table = document.querySelector(tableSelector);
    
    if (!input || !table) return;
    
    input.addEventListener('input', function() {
        const filter = this.value.toLowerCase();
        const rows = table.querySelectorAll('tbody tr');
        
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(filter) ? '' : 'none';
        });
    });
}

/**
 * Searchable Select with Pinned Items
 * Converts a <select> with class "searchable-select" into a searchable dropdown
 * with pinned items at the top (fetched from user's pins)
 */
function initSearchableSelects() {
    document.querySelectorAll('select.searchable-select').forEach(select => {
        if (select.dataset.searchableInitialized) return;
        select.dataset.searchableInitialized = 'true';
        
        const entityType = select.dataset.entityType || select.name.replace('_id', '').replace('[]', '');
        const wrapper = document.createElement('div');
        wrapper.className = 'searchable-select-wrapper';
        
        // Create the custom dropdown structure
        const display = document.createElement('div');
        display.className = 'searchable-select-display';
        
        const selectedText = document.createElement('span');
        selectedText.className = 'selected-text';
        selectedText.textContent = select.options[select.selectedIndex]?.text || 'Select...';
        
        const arrow = document.createElement('span');
        arrow.className = 'dropdown-arrow';
        arrow.innerHTML = '▼';
        
        display.appendChild(selectedText);
        display.appendChild(arrow);
        
        const dropdown = document.createElement('div');
        dropdown.className = 'searchable-select-dropdown';
        
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.className = 'searchable-select-search';
        searchInput.placeholder = 'Search...';
        
        const optionsList = document.createElement('div');
        optionsList.className = 'searchable-select-options';
        
        dropdown.appendChild(searchInput);
        dropdown.appendChild(optionsList);
        
        // Insert wrapper before select and move select inside
        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(display);
        wrapper.appendChild(dropdown);
        wrapper.appendChild(select);
        select.style.display = 'none';
        
        // Fetch pinned IDs for this entity type
        let pinnedIds = [];
        fetch(`/api/pins/${entityType}`)
            .then(r => r.json())
            .then(data => {
                if (data.pinned_ids) {
                    pinnedIds = data.pinned_ids;
                    renderOptions();
                }
            })
            .catch(() => {
                // If fetch fails, still render options without pins
                renderOptions();
            });
        
        function renderOptions(filter = '') {
            optionsList.innerHTML = '';
            const filterLower = filter.toLowerCase();
            
            // Collect all options
            const options = Array.from(select.options);
            const pinnedOptions = [];
            const unpinnedOptions = [];
            
            options.forEach(opt => {
                // Search in text and data attributes (name, username, email)
                if (filterLower) {
                    const text = opt.text.toLowerCase();
                    const name = (opt.dataset.name || '').toLowerCase();
                    const username = (opt.dataset.username || '').toLowerCase();
                    const email = (opt.dataset.email || '').toLowerCase();
                    
                    if (!text.includes(filterLower) && 
                        !name.includes(filterLower) && 
                        !username.includes(filterLower) && 
                        !email.includes(filterLower)) {
                        return;
                    }
                }
                
                const optionDiv = document.createElement('div');
                optionDiv.className = 'searchable-option';
                optionDiv.dataset.value = opt.value;
                
                const optValue = parseInt(opt.value);
                const isPinned = pinnedIds.includes(optValue);
                
                if (isPinned) {
                    optionDiv.classList.add('pinned-option');
                    optionDiv.innerHTML = `<span class="pin-icon">📌</span> ${opt.text}`;
                    pinnedOptions.push(optionDiv);
                } else {
                    optionDiv.textContent = opt.text;
                    unpinnedOptions.push(optionDiv);
                }
                
                if (opt.value === select.value) {
                    optionDiv.classList.add('selected');
                }
                
                optionDiv.addEventListener('click', () => {
                    select.value = opt.value;
                    select.dispatchEvent(new Event('change'));
                    selectedText.textContent = opt.text;
                    closeDropdown();
                    renderOptions(); // Re-render to update selected state
                });
            });
            
            // Add pinned section if there are pinned items
            if (pinnedOptions.length > 0) {
                const pinnedSection = document.createElement('div');
                pinnedSection.className = 'pinned-section-header';
                pinnedSection.textContent = 'Pinned';
                optionsList.appendChild(pinnedSection);
                pinnedOptions.forEach(opt => optionsList.appendChild(opt));
                
                if (unpinnedOptions.length > 0) {
                    const divider = document.createElement('div');
                    divider.className = 'options-divider';
                    optionsList.appendChild(divider);
                }
            }
            
            // Add unpinned options
            unpinnedOptions.forEach(opt => optionsList.appendChild(opt));
            
            // Empty state
            if (pinnedOptions.length === 0 && unpinnedOptions.length === 0) {
                const empty = document.createElement('div');
                empty.className = 'searchable-option disabled';
                empty.textContent = filter ? 'No matches found' : 'No options available';
                optionsList.appendChild(empty);
            }
        }
        
        function openDropdown() {
            wrapper.classList.add('open');
            searchInput.value = '';
            searchInput.focus();
            renderOptions();
        }
        
        function closeDropdown() {
            wrapper.classList.remove('open');
        }
        
        // Event listeners
        display.addEventListener('click', (e) => {
            e.stopPropagation();
            if (wrapper.classList.contains('open')) {
                closeDropdown();
            } else {
                // Close other open dropdowns
                document.querySelectorAll('.searchable-select-wrapper.open').forEach(w => {
                    if (w !== wrapper) w.classList.remove('open');
                });
                openDropdown();
            }
        });
        
        searchInput.addEventListener('input', () => {
            renderOptions(searchInput.value);
        });
        
        searchInput.addEventListener('click', (e) => e.stopPropagation());
        dropdown.addEventListener('click', (e) => e.stopPropagation());
        
        // Initial render
        renderOptions();
        
        // Add QR scan button if this entity type supports it
        if (entityType) {
            addQRScanButton(wrapper, select, entityType);
        }
    });
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', () => {
        document.querySelectorAll('.searchable-select-wrapper.open').forEach(w => {
            w.classList.remove('open');
        });
    });
}

// Initialize searchable selects on page load
document.addEventListener('DOMContentLoaded', function() {
    initSearchableSelects();
    initSetDefaultLinks();
});

/**
 * Set Default Links
 * Allows users to set the current selection as their default for future forms
 */
function initSetDefaultLinks() {
    document.querySelectorAll('.set-default-link').forEach(link => {
        link.addEventListener('click', async function(e) {
            e.preventDefault();
            
            const fieldName = this.dataset.field;
            const selectElement = document.getElementById(fieldName);
            
            if (!selectElement) {
                console.error('Select element not found:', fieldName);
                return;
            }
            
            const value = selectElement.value || null;
            const prefKey = 'default_' + fieldName;
            
            try {
                const response = await fetch('/api/user/preferences', {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ [prefKey]: value ? parseInt(value) : null })
                });
                
                if (response.ok) {
                    // Show success feedback
                    const originalText = this.textContent;
                    this.textContent = '✓ Saved!';
                    this.style.color = 'green';
                    setTimeout(() => {
                        this.textContent = originalText;
                        this.style.color = '';
                    }, 2000);
                } else {
                    const data = await response.json();
                    alert(data.error || 'Failed to save preference');
                }
            } catch (err) {
                console.error('Error saving preference:', err);
                alert('Error saving preference');
            }
        });
    });
}

/**
 * QR Scanner Modal for searchable selects
 * Allows scanning QR codes to populate dropdown fields
 */
let qrScannerModal = null;
let qrScannerStream = null;
let qrScannerCallback = null;
let qrScannerExpectedType = null;

function initQRScannerModal() {
    // Create modal HTML if it doesn't exist
    if (!document.getElementById('qr-scanner-modal')) {
        const modalHtml = `
            <div id="qr-scanner-modal" class="qr-scanner-modal" style="display: none;">
                <div class="qr-scanner-content">
                    <div class="qr-scanner-header">
                        <h3>📷 Scan QR Code</h3>
                        <button type="button" class="qr-scanner-close" onclick="closeQRScanner()">&times;</button>
                    </div>
                    <div class="qr-scanner-body">
                        <div id="qr-scanner-video-container">
                            <video id="qr-scanner-video" autoplay playsinline></video>
                            <div class="qr-scanner-overlay">
                                <div class="qr-scanner-frame"></div>
                            </div>
                        </div>
                        <div id="qr-scanner-status" class="qr-scanner-status">
                            Initializing camera...
                        </div>
                        <div id="qr-scanner-result" class="qr-scanner-result" style="display: none;"></div>
                    </div>
                    <div class="qr-scanner-footer">
                        <button type="button" class="btn btn-secondary" onclick="closeQRScanner()">Cancel</button>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }
    qrScannerModal = document.getElementById('qr-scanner-modal');
}

function openQRScanner(selectElement, expectedType) {
    if (!qrScannerModal) {
        initQRScannerModal();
    }
    
    qrScannerExpectedType = expectedType;
    qrScannerCallback = (entityId, displayName) => {
        // Find the option with this value and select it
        const option = selectElement.querySelector(`option[value="${entityId}"]`);
        if (option) {
            selectElement.value = entityId;
            selectElement.dispatchEvent(new Event('change'));
            
            // Update the searchable-select display if it exists
            const wrapper = selectElement.closest('.searchable-select-wrapper');
            if (wrapper) {
                const display = wrapper.querySelector('.selected-text');
                if (display) {
                    display.textContent = displayName;
                }
            }
        } else {
            // Option doesn't exist in dropdown - show error
            alert(`${expectedType} found but not available in this dropdown. The ${expectedType} may not be associated with the current lab/project.`);
        }
    };
    
    qrScannerModal.style.display = 'flex';
    document.getElementById('qr-scanner-status').textContent = 'Initializing camera...';
    document.getElementById('qr-scanner-result').style.display = 'none';
    
    startQRScanner();
}

function closeQRScanner() {
    if (qrScannerStream) {
        qrScannerStream.getTracks().forEach(track => track.stop());
        qrScannerStream = null;
    }
    if (qrScannerModal) {
        qrScannerModal.style.display = 'none';
    }
    qrScannerCallback = null;
    qrScannerExpectedType = null;
}

async function startQRScanner() {
    const video = document.getElementById('qr-scanner-video');
    const statusEl = document.getElementById('qr-scanner-status');
    
    try {
        // Request camera access
        qrScannerStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment' }
        });
        
        video.srcObject = qrScannerStream;
        statusEl.textContent = `Point camera at a ${qrScannerExpectedType || 'entity'} QR code`;
        
        // Start scanning with BarcodeDetector if available, else use jsQR library
        if ('BarcodeDetector' in window) {
            scanWithBarcodeDetector(video);
        } else {
            // Fallback: load jsQR dynamically and use canvas-based scanning
            await loadJsQR();
            scanWithJsQR(video);
        }
        
    } catch (err) {
        console.error('Camera error:', err);
        statusEl.textContent = 'Camera access denied. Please allow camera permissions and try again.';
    }
}

async function scanWithBarcodeDetector(video) {
    const barcodeDetector = new BarcodeDetector({ formats: ['qr_code'] });
    
    const scan = async () => {
        if (!qrScannerStream) return;
        
        try {
            const barcodes = await barcodeDetector.detect(video);
            if (barcodes.length > 0) {
                const url = barcodes[0].rawValue;
                await processScannedQR(url);
                return;
            }
        } catch (err) {
            console.error('Scan error:', err);
        }
        
        // Continue scanning
        if (qrScannerStream) {
            requestAnimationFrame(scan);
        }
    };
    
    // Wait for video to be ready
    video.onloadedmetadata = () => {
        video.play();
        scan();
    };
}

// Load jsQR library dynamically if BarcodeDetector not available
async function loadJsQR() {
    if (window.jsQR) return;
    
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js';
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

function scanWithJsQR(video) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    
    const scan = () => {
        if (!qrScannerStream) return;
        
        if (video.readyState === video.HAVE_ENOUGH_DATA) {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            
            const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            const code = jsQR(imageData.data, imageData.width, imageData.height);
            
            if (code) {
                processScannedQR(code.data);
                return;
            }
        }
        
        // Continue scanning
        if (qrScannerStream) {
            requestAnimationFrame(scan);
        }
    };
    
    video.onloadedmetadata = () => {
        video.play();
        scan();
    };
}

async function processScannedQR(url) {
    const statusEl = document.getElementById('qr-scanner-status');
    const resultEl = document.getElementById('qr-scanner-result');
    
    statusEl.textContent = 'Processing...';
    
    try {
        // Call API to resolve the QR code URL
        const apiUrl = `/api/resolve-qr?url=${encodeURIComponent(url)}` + 
            (qrScannerExpectedType ? `&expected_type=${qrScannerExpectedType}` : '');
        
        const response = await fetch(apiUrl);
        const data = await response.json();
        
        if (data.success) {
            // Success - show result and close
            statusEl.textContent = '✓ Found!';
            resultEl.innerHTML = `<strong>${data.display_name}</strong> (${data.entity_type})`;
            resultEl.style.display = 'block';
            resultEl.className = 'qr-scanner-result success';
            
            // Call the callback to update the select
            if (qrScannerCallback) {
                qrScannerCallback(data.entity_id, data.display_name);
            }
            
            // Close after a brief delay
            setTimeout(() => {
                closeQRScanner();
            }, 1000);
            
        } else {
            // Error
            statusEl.textContent = 'Scan failed';
            resultEl.innerHTML = data.error || 'Unknown error';
            resultEl.style.display = 'block';
            resultEl.className = 'qr-scanner-result error';
            
            // Resume scanning after showing error
            setTimeout(() => {
                resultEl.style.display = 'none';
                statusEl.textContent = `Point camera at a ${qrScannerExpectedType || 'entity'} QR code`;
                // Restart scanning
                const video = document.getElementById('qr-scanner-video');
                if ('BarcodeDetector' in window) {
                    scanWithBarcodeDetector(video);
                } else {
                    scanWithJsQR(video);
                }
            }, 2000);
        }
        
    } catch (err) {
        console.error('API error:', err);
        statusEl.textContent = 'Error processing QR code';
        resultEl.innerHTML = 'Network error. Please try again.';
        resultEl.style.display = 'block';
        resultEl.className = 'qr-scanner-result error';
    }
}

/**
 * Add QR scan button to a searchable select wrapper
 */
function addQRScanButton(wrapper, selectElement, entityType) {
    // Don't add if already exists
    if (wrapper.querySelector('.qr-scan-btn')) return;
    
    // Entity types that have QR codes
    const qrEnabledTypes = ['sample', 'precursor', 'equipment', 'procedure', 'project', 'lab', 'location', 'instrument', 'template'];
    
    if (!qrEnabledTypes.includes(entityType)) return;
    
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'qr-scan-btn';
    btn.title = `Scan ${entityType} QR code`;
    btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect></svg>`;
    
    btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        openQRScanner(selectElement, entityType);
    });
    
    wrapper.appendChild(btn);
}
