/**
 * PyBirch Database Web UI JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize copy buttons
    initCopyButtons();
    
    // Initialize search autocomplete
    initSearchAutocomplete();
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
