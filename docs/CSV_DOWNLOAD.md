# CSV Download Feature

## Overview

This document specifies the implementation of CSV download functionality for the scan detail page, allowing users to export scan data for further analysis in external tools like Excel, Origin, MATLAB, or Python.

## Requirements

1. **Download raw scan data** - All data points with all columns
2. **Download reduced/filtered data** - Data as currently visualized
3. **Include metadata** - Scan info, timestamp, parameters
4. **Flexible column selection** - Choose which columns to include
5. **Large file handling** - Efficient streaming for big datasets

## CSV Format Specification

### Standard Data Export

```csv
# PyBirch Scan Export
# Scan ID: 42
# Scan Type: Raman Spectroscopy
# Queue: Characterization Run #1
# Date: 2025-01-15 14:30:45
# Total Points: 2505
#
# Columns: point_index, position_x, position_y, wavelength, intensity
point_index,position_x,position_y,wavelength,intensity
1,0.000,0.000,200.0,1234.5
2,0.000,0.000,200.5,1245.2
3,0.000,0.000,201.0,1256.8
...
```

### Column Naming Convention

| Data Type | Column Name Format | Example |
|-----------|-------------------|---------|
| Point index | `point_index` | `point_index` |
| Movement position | `{instrument}_{axis}` | `stage_x`, `piezo_z` |
| Measurement value | `{measurement_name}` | `intensity`, `voltage` |
| Timestamp | `timestamp` | `timestamp` |
| Calculated | `{calculation}_of_{source}` | `max_of_intensity` |

## Backend Implementation

### API Endpoint

```python
# In routes.py

@bp.route('/scans/<int:scan_id>/download')
def download_scan_data(scan_id):
    """
    Download scan data as CSV.
    
    Query Parameters:
        - columns: Comma-separated list of columns to include (default: all)
        - reduced: If 'true', apply current reduction settings
        - format: 'csv' (default) or 'json'
        - include_metadata: 'true' or 'false' (default: true)
    """
    scan = db.get_scan(scan_id)
    if not scan:
        abort(404)
    
    # Get query parameters
    columns = request.args.get('columns', '').split(',') if request.args.get('columns') else None
    include_metadata = request.args.get('include_metadata', 'true') == 'true'
    
    # Generate CSV
    csv_content = generate_csv(scan, columns=columns, include_metadata=include_metadata)
    
    # Create response with download headers
    response = make_response(csv_content)
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=scan_{scan_id}.csv'
    
    return response
```

### CSV Generation Function

```python
# In services.py

import csv
import io
from datetime import datetime

def generate_csv(scan, columns=None, include_metadata=True):
    """
    Generate CSV content for scan data.
    
    Args:
        scan: Scan database object
        columns: List of columns to include, or None for all
        include_metadata: Whether to include header comments
    
    Returns:
        String containing CSV content
    """
    output = io.StringIO()
    
    # Write metadata header
    if include_metadata:
        output.write(f"# PyBirch Scan Export\n")
        output.write(f"# Scan ID: {scan.id}\n")
        output.write(f"# Scan Type: {scan.scan_type}\n")
        output.write(f"# Queue ID: {scan.queue_id}\n")
        output.write(f"# Date: {datetime.now().isoformat()}\n")
        output.write(f"# Total Points: {len(scan.data_points)}\n")
        output.write(f"#\n")
    
    # Determine columns
    if not columns:
        columns = get_all_columns(scan)
    
    # Write CSV header comment
    if include_metadata:
        output.write(f"# Columns: {', '.join(columns)}\n")
    
    # Write CSV data
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    
    for point in scan.data_points:
        row = extract_row_data(point, columns)
        writer.writerow(row)
    
    return output.getvalue()


def get_all_columns(scan):
    """Extract all available column names from scan data."""
    columns = ['point_index']
    
    # Add movement columns
    for mo in scan.movement_objects:
        columns.append(mo.column_name)
    
    # Add measurement columns
    for dp in scan.data_points[:1]:  # Sample first point
        if dp.values:
            columns.extend(dp.values.keys())
    
    return columns


def extract_row_data(data_point, columns):
    """Extract a row of data for CSV export."""
    row = {'point_index': data_point.index}
    
    # Add movement positions
    for mo in data_point.movement_objects:
        row[mo.column_name] = mo.position
    
    # Add measurement values
    if data_point.values:
        row.update(data_point.values)
    
    return row
```

### Streaming for Large Files

```python
from flask import Response

def download_scan_data_streaming(scan_id):
    """Streaming CSV download for large datasets."""
    scan = db.get_scan(scan_id)
    
    def generate():
        # Yield metadata
        yield "# PyBirch Scan Export\n"
        yield f"# Scan ID: {scan.id}\n"
        yield f"# Total Points: {scan.data_point_count}\n"
        yield "#\n"
        
        # Yield header
        columns = get_all_columns(scan)
        yield ','.join(columns) + '\n'
        
        # Yield data rows in batches
        batch_size = 1000
        offset = 0
        
        while True:
            points = get_data_points_batch(scan.id, offset, batch_size)
            if not points:
                break
            
            for point in points:
                row = extract_row_data(point, columns)
                yield ','.join(str(row.get(c, '')) for c in columns) + '\n'
            
            offset += batch_size
    
    return Response(
        generate(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=scan_{scan_id}.csv'}
    )
```

## Frontend Implementation

### Download Button

```html
<div class="download-section">
    <button class="btn btn-primary" id="download-btn" onclick="downloadCSV()">
        <svg class="icon" viewBox="0 0 24 24" width="16" height="16">
            <path d="M12 15V3m0 12l-4-4m4 4l4-4M2 17l.621 2.485A2 2 0 004.561 21h14.878a2 2 0 001.94-1.515L22 17" 
                  stroke="currentColor" stroke-width="2" fill="none"/>
        </svg>
        Download CSV
    </button>
    
    <button class="btn btn-link" onclick="showDownloadOptions()">
        ⚙️ Options
    </button>
</div>

<!-- Download Options Modal -->
<div class="modal" id="download-options-modal">
    <div class="modal-content">
        <h3>Download Options</h3>
        
        <div class="option-group">
            <label>
                <input type="checkbox" id="include-metadata" checked>
                Include metadata header
            </label>
        </div>
        
        <div class="option-group">
            <label>Columns to include:</label>
            <div class="column-checkboxes" id="column-checkboxes">
                <!-- Populated dynamically -->
            </div>
            <div class="column-actions">
                <button onclick="selectAllColumns()">Select All</button>
                <button onclick="selectNoneColumns()">Select None</button>
            </div>
        </div>
        
        <div class="option-group">
            <label>
                <input type="checkbox" id="export-reduced">
                Export reduced data (as currently displayed)
            </label>
        </div>
        
        <div class="modal-actions">
            <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
            <button class="btn btn-primary" onclick="downloadWithOptions()">Download</button>
        </div>
    </div>
</div>
```

### JavaScript Functions

```javascript
// Simple download
function downloadCSV() {
    const scanId = document.getElementById('scan-data').dataset.scanId;
    window.location.href = `/scans/${scanId}/download`;
}

// Download with options
function downloadWithOptions() {
    const scanId = document.getElementById('scan-data').dataset.scanId;
    
    // Gather options
    const includeMetadata = document.getElementById('include-metadata').checked;
    const exportReduced = document.getElementById('export-reduced').checked;
    const selectedColumns = getSelectedColumns();
    
    // Build URL with query parameters
    const params = new URLSearchParams();
    params.set('include_metadata', includeMetadata);
    if (selectedColumns.length > 0) {
        params.set('columns', selectedColumns.join(','));
    }
    if (exportReduced) {
        params.set('reduced', 'true');
        // Add current reduction settings
        params.set('reduce_dim', vizState.reduction.dimension);
        params.set('reduce_method', vizState.reduction.method);
        params.set('reduce_value', vizState.reduction.value);
    }
    
    // Trigger download
    window.location.href = `/scans/${scanId}/download?${params.toString()}`;
    
    closeModal();
}

// Populate column checkboxes
function populateColumnOptions(columns) {
    const container = document.getElementById('column-checkboxes');
    container.innerHTML = columns.map(col => `
        <label class="column-checkbox">
            <input type="checkbox" name="column" value="${col}" checked>
            ${formatColumnName(col)}
        </label>
    `).join('');
}

// Get selected columns
function getSelectedColumns() {
    const checkboxes = document.querySelectorAll('input[name="column"]:checked');
    return Array.from(checkboxes).map(cb => cb.value);
}

// Format column name for display
function formatColumnName(colName) {
    return colName
        .replace(/_/g, ' ')
        .replace(/\b\w/g, l => l.toUpperCase());
}

// Select all/none helpers
function selectAllColumns() {
    document.querySelectorAll('input[name="column"]').forEach(cb => cb.checked = true);
}

function selectNoneColumns() {
    document.querySelectorAll('input[name="column"]').forEach(cb => cb.checked = false);
}

// Modal functions
function showDownloadOptions() {
    document.getElementById('download-options-modal').classList.add('visible');
}

function closeModal() {
    document.getElementById('download-options-modal').classList.remove('visible');
}
```

### CSS for Download UI

```css
/* Download Section */
.download-section {
    display: flex;
    align-items: center;
    gap: 8px;
}

/* Modal */
.modal {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 1000;
    justify-content: center;
    align-items: center;
}

.modal.visible {
    display: flex;
}

.modal-content {
    background: white;
    border-radius: 12px;
    padding: 24px;
    max-width: 500px;
    width: 90%;
    max-height: 80vh;
    overflow-y: auto;
}

.modal-content h3 {
    margin: 0 0 20px 0;
    font-size: 1.25rem;
}

.option-group {
    margin-bottom: 20px;
}

.option-group > label:first-child {
    display: block;
    font-weight: 500;
    margin-bottom: 8px;
}

/* Column Checkboxes */
.column-checkboxes {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 8px;
    max-height: 200px;
    overflow-y: auto;
    padding: 8px;
    background: #f9fafb;
    border-radius: 6px;
    margin-bottom: 8px;
}

.column-checkbox {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.875rem;
}

.column-actions {
    display: flex;
    gap: 8px;
}

.column-actions button {
    font-size: 0.75rem;
    padding: 4px 8px;
    background: none;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    cursor: pointer;
}

.column-actions button:hover {
    background: #f3f4f6;
}

/* Modal Actions */
.modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 24px;
    padding-top: 16px;
    border-top: 1px solid #e5e7eb;
}

/* Icon in button */
.btn .icon {
    flex-shrink: 0;
}
```

## File Naming Convention

```
scan_{scan_id}_{timestamp}.csv

Examples:
- scan_42.csv                    (basic)
- scan_42_20250115_143045.csv    (with timestamp)
- scan_42_reduced_max_z.csv      (reduced data)
```

## Error Handling

```python
@bp.route('/scans/<int:scan_id>/download')
def download_scan_data(scan_id):
    try:
        scan = db.get_scan(scan_id)
        if not scan:
            return jsonify({'error': 'Scan not found'}), 404
        
        if not scan.data_points:
            return jsonify({'error': 'Scan has no data points'}), 400
        
        csv_content = generate_csv(scan)
        # ... response creation
        
    except Exception as e:
        logger.error(f"CSV download error for scan {scan_id}: {e}")
        return jsonify({'error': 'Failed to generate CSV'}), 500
```

```javascript
async function downloadCSV() {
    try {
        const response = await fetch(`/scans/${scanId}/download`);
        
        if (!response.ok) {
            const error = await response.json();
            showError(error.message || 'Download failed');
            return;
        }
        
        // Trigger download
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `scan_${scanId}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        
    } catch (error) {
        showError('Network error. Please try again.');
    }
}
```

## Performance Considerations

1. **Batch Processing** - Load data in chunks for large scans
2. **Streaming Response** - Don't buffer entire file in memory
3. **Progress Indicator** - Show download progress for large files
4. **Compression** - Option for gzip-compressed CSV download
5. **Caching** - Cache generated CSV for repeated downloads

## Testing Checklist

- [ ] Download works for small scans (<100 points)
- [ ] Download works for large scans (>10,000 points)
- [ ] Column selection filters correctly
- [ ] Metadata header toggles on/off
- [ ] Reduced data export matches visualization
- [ ] File opens correctly in Excel
- [ ] File opens correctly in LibreOffice
- [ ] UTF-8 encoding handled properly
- [ ] Special characters escaped correctly
- [ ] Error handling for missing scans
- [ ] Error handling for empty scans

## Future Enhancements

1. **Multiple format support** - JSON, Excel (.xlsx), HDF5
2. **Batch download** - Download multiple scans at once
3. **Email delivery** - Send download link for very large files
4. **Cloud export** - Direct export to Google Sheets, OneDrive
5. **Template-based export** - User-defined CSV templates
