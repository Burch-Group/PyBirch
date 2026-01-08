# Visualization Fix Implementation Plan

## Overview

This document outlines the plan to fix visualization issues in the PyBirch database web interface. Currently:
1. Visualizations are blank
2. The x-axis shows point index instead of actual measurement/movement positions
3. The system doesn't properly handle multiple measurement objects per scan
4. High-dimensional scans (4+ movement objects) are not accommodated

## Current State Analysis

### Database Structure (Already Correct)
- `MeasurementObject`: Each scan can have multiple measurement objects
  - `columns`: JSON array defining the column names (e.g., `['current', 'voltage']`)
  - `unit`: Measurement unit
  - `instrument_name`: Associated instrument
- `MeasurementDataPoint`: Individual data points
  - `values`: JSON dict with actual values (e.g., `{'current': -0.001, 'voltage': -0.016}`)
  - `sequence_index`: Order of the point
  - `extra_data`: Can store movement positions

### Test Data Example
- IV Scan: columns=['current', 'voltage'], values={'current': X, 'voltage': Y}
- Raman Scan: columns=['wavelength', 'intensity'], values={'wavelength': X, 'intensity': Y}

### Current Visualization Code Issues
In `scan_detail.html`:
```javascript
labels: dataPoints.map(p => p.point_index),  // Using sequence index, not actual X values
datasets: [{
    data: dataPoints.map(p => p.value),      // 'value' doesn't exist, should use p.values
}]
```

## Implementation Tasks

### Phase 1: Fix Data Retrieval (Backend)

#### Task 1.1: Update `get_scan_data_points` in services.py
- Group data points by measurement object
- Return data organized by measurement name
- Include column metadata for proper axis labeling

#### Task 1.2: Update `scan_detail` route in routes.py
- Fetch data points per measurement object
- Pass structured data to template including:
  - Measurement name
  - Column names (for axis labels)
  - Actual values

### Phase 2: Fix Visualization (Frontend)

#### Task 2.1: Update scan_detail.html Template
- Create separate chart for each measurement object
- Use actual column values for X and Y axes
- Smart axis detection:
  - If 2 columns: Use first as X, second as Y
  - If 1 column: Use sequence_index as X
  - If 3+ columns: Create multi-series chart or dropdown selector

#### Task 2.2: Handle High-Dimensional Data
- For 1D data (like Raman spectra): Simple line chart
- For 2D data (like IV curves): Simple line chart with proper axes
- For 3D+ data: 
  - Show 2D slice with dimension selector
  - Or heatmap visualization
  - Or provide data table with export

#### Task 2.3: Movement Position Integration
- Store movement positions in `extra_data` when saving data points
- Display movement positions in data table
- Allow filtering/grouping by movement position

### Phase 3: API Improvements

#### Task 3.1: Create measurement-specific data endpoint
- `GET /api/v1/measurements/<id>/data` - already exists, verify it works
- `GET /api/v1/scans/<id>/measurements/<name>/data` - new endpoint for convenience

#### Task 3.2: Add visualization hints to measurement objects
- `default_x_column`: Which column to use for X-axis
- `default_y_column`: Which column to use for Y-axis
- `visualization_type`: 'line', 'scatter', 'heatmap', etc.

## File Changes Required

### database/services.py
- Modify `get_scan_data_points()` to return organized data
- Add `get_measurement_data_for_visualization()` method

### database/web/routes.py
- Update `scan_detail()` route to pass better structured data
- Add new API endpoints if needed

### database/web/templates/scan_detail.html
- Complete rewrite of visualization section
- Per-measurement-object charts
- Proper axis labels from column names
- Handle different data shapes

### database/web/static/css/main.css (if exists)
- Add styles for multiple chart containers

## Visualization Protocol for High-Dimensional Scans

### Principle
Each measurement object gets its own visualization, not the scan as a whole.
This is because different instruments may:
- Measure at different positions (sparse vs dense)
- Have different data shapes (scalars vs spectra)
- Have different column structures

### Standard Visualization Rules

1. **Single Column** (rare): 
   - Y-axis: The column value
   - X-axis: Sequence index

2. **Two Columns** (most common):
   - X-axis: First column (e.g., wavelength, current)
   - Y-axis: Second column (e.g., intensity, voltage)
   - Type: Line chart

3. **Three+ Columns**:
   - Default: Show first two columns as X/Y
   - Dropdown to select which columns to plot
   - Option for multi-series (all columns vs first column)

4. **With Movement Positions**:
   - Show position selector if data spans multiple positions
   - Enable filtering/coloring by position
   - Group data by position for comparison

## Success Criteria

1. IV scan shows voltage vs current (not index vs undefined)
2. Raman scan shows intensity vs wavelength
3. Each measurement object has its own chart
4. Charts have proper axis labels with units
5. High-dimensional data has reasonable default view
6. Data table shows actual column values

## Timeline

- Phase 1: 30 minutes
- Phase 2: 60 minutes
- Phase 3: 30 minutes
- Testing: 15 minutes

Total: ~2.5 hours
