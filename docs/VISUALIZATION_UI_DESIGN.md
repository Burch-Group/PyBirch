# Visualization UI Design

## Overview

This document defines the user interface design for the advanced visualization features on the scan detail page. The goal is to create an intuitive, standard interface that scientists will find familiar and easy to use.

## Design Principles

1. **Familiarity** - Follow conventions from established tools (ImageJ, Origin, MATLAB)
2. **Progressive Disclosure** - Simple by default, advanced options available on demand
3. **Immediate Feedback** - Changes update visualization instantly
4. **Accessibility** - Colorblind-friendly defaults, keyboard navigation

## Page Layout

### Overall Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│ ← Back to Scans                              [Download CSV] [Export]│
├─────────────────────────────────────────────────────────────────────┤
│ Scan: Raman Map - Sample A                                          │
│ Queue: Characterization Run #42 | Date: 2025-01-15 14:30            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────┐ ┌─────────────────────┐  │
│  │                                      │ │ VISUALIZATION       │  │
│  │                                      │ │ CONTROLS            │  │
│  │                                      │ │                     │  │
│  │         MAIN VISUALIZATION           │ │ Type: [Heatmap ▼]  │  │
│  │              AREA                    │ │                     │  │
│  │                                      │ │ X-Axis: [Pos X ▼]  │  │
│  │          (Chart.js or                │ │ Y-Axis: [Pos Y ▼]  │  │
│  │           Plotly.js)                 │ │                     │  │
│  │                                      │ │ Measurement:        │  │
│  │                                      │ │ [Intensity ▼]       │  │
│  │                                      │ │                     │  │
│  │                                      │ │ ─────────────────── │  │
│  │                                      │ │ DIMENSION REDUCTION │  │
│  │                                      │ │                     │  │
│  └──────────────────────────────────────┘ │ Reduce: [Pos Z ▼]  │  │
│                                            │ Method: [Slice ▼]  │  │
│                                            │ Value: [══●══] 2.5 │  │
│                                            │                     │  │
│                                            │ ─────────────────── │  │
│                                            │ APPEARANCE          │  │
│                                            │                     │  │
│                                            │ Color: [Viridis ▼] │  │
│                                            │ Scale: [Linear ▼]  │  │
│                                            └─────────────────────┘  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│ DATA TABLE                                                          │
│ ┌─────────┬─────────┬─────────┬─────────────┐                      │
│ │ Point # │ Pos X   │ Pos Y   │ Intensity   │ [Show/Hide columns]  │
│ ├─────────┼─────────┼─────────┼─────────────┤                      │
│ │ 1       │ 0.00    │ 0.00    │ 1234.5      │                      │
│ │ 2       │ 0.00    │ 0.50    │ 1245.2      │                      │
│ │ ...     │ ...     │ ...     │ ...         │                      │
│ └─────────┴─────────┴─────────┴─────────────┘                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Specifications

### 1. Visualization Type Selector

```html
<div class="control-group">
    <label for="viz-type">Visualization Type</label>
    <select id="viz-type" class="form-select">
        <option value="line">📈 Line Chart</option>
        <option value="scatter">⚫ Scatter Plot</option>
        <option value="heatmap">🗺️ Heatmap</option>
    </select>
</div>
```

**Behavior:**
- Default: Auto-detect based on data dimensions
- Line/Scatter: Use Chart.js
- Heatmap: Use Plotly.js
- Switching type preserves axis selections where applicable

### 2. Axis Selectors

```html
<div class="axis-selectors">
    <div class="control-group">
        <label for="x-axis">X-Axis</label>
        <select id="x-axis" class="form-select">
            <option value="position_x">Position X (µm)</option>
            <option value="position_y">Position Y (µm)</option>
            <option value="time">Time (s)</option>
            <option value="index">Point Index</option>
        </select>
    </div>
    <div class="control-group">
        <label for="y-axis">Y-Axis</label>
        <select id="y-axis" class="form-select">
            <!-- Options populated dynamically -->
        </select>
    </div>
</div>
```

**Behavior:**
- Options generated from scan's movement objects and measurement columns
- Y-axis cannot be same as X-axis
- For heatmaps, add Z-axis (color) selector

### 3. Dimension Reduction Panel

```html
<div class="reduction-panel" id="reduction-panel">
    <h4>Dimension Reduction</h4>
    <p class="help-text">
        This scan has 3 dimensions. Select how to reduce to 2D.
    </p>
    
    <div class="control-group">
        <label for="reduce-dim">Reduce Dimension</label>
        <select id="reduce-dim" class="form-select">
            <option value="position_z">Position Z</option>
        </select>
    </div>
    
    <div class="control-group">
        <label>Reduction Method</label>
        <div class="radio-group">
            <label class="radio-option">
                <input type="radio" name="reduce-method" value="slice" checked>
                <span>Slice at position</span>
            </label>
            <label class="radio-option">
                <input type="radio" name="reduce-method" value="max">
                <span>Maximum</span>
            </label>
            <label class="radio-option">
                <input type="radio" name="reduce-method" value="min">
                <span>Minimum</span>
            </label>
            <label class="radio-option">
                <input type="radio" name="reduce-method" value="mean">
                <span>Average</span>
            </label>
        </div>
    </div>
    
    <!-- Shown only when "slice" is selected -->
    <div class="slice-controls" id="slice-controls">
        <label for="slice-slider">Position: <span id="slice-value">2.5</span> µm</label>
        <input type="range" id="slice-slider" min="0" max="10" step="0.5" value="2.5">
    </div>
</div>
```

**Behavior:**
- Only shown when data has 3+ dimensions
- Slice slider updates visualization in real-time
- Method change triggers immediate recalculation

### 4. Color Scale Selector (Heatmaps)

```html
<div class="color-controls" id="color-controls">
    <div class="control-group">
        <label for="colorscale">Color Scale</label>
        <select id="colorscale" class="form-select">
            <option value="Viridis">Viridis (default)</option>
            <option value="Plasma">Plasma</option>
            <option value="Inferno">Inferno</option>
            <option value="Cividis">Cividis (colorblind)</option>
            <option value="RdBu">Red-Blue (diverging)</option>
            <option value="Greys">Grayscale</option>
        </select>
        <div class="colorscale-preview" id="colorscale-preview"></div>
    </div>
    
    <div class="control-group">
        <label for="scale-type">Scale Type</label>
        <select id="scale-type" class="form-select">
            <option value="linear">Linear</option>
            <option value="log">Logarithmic</option>
        </select>
    </div>
</div>
```

### 5. Download/Export Section

```html
<div class="export-controls">
    <button class="btn btn-primary" onclick="downloadCSV()">
        📥 Download CSV
    </button>
    <div class="dropdown">
        <button class="btn btn-secondary dropdown-toggle">
            📤 Export Chart
        </button>
        <div class="dropdown-menu">
            <a href="#" onclick="exportChart('png')">PNG Image</a>
            <a href="#" onclick="exportChart('svg')">SVG Vector</a>
            <a href="#" onclick="exportChart('json')">Chart Data (JSON)</a>
        </div>
    </div>
</div>
```

## CSS Styling

```css
/* Control Panel */
.visualization-controls {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 16px;
    max-width: 280px;
}

.control-group {
    margin-bottom: 16px;
}

.control-group label {
    display: block;
    font-weight: 600;
    margin-bottom: 4px;
    font-size: 0.875rem;
    color: #374151;
}

.form-select {
    width: 100%;
    padding: 8px 12px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    font-size: 0.875rem;
    background: white;
}

.form-select:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

/* Radio Options */
.radio-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.radio-option {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
}

.radio-option input[type="radio"] {
    margin: 0;
}

/* Slider */
input[type="range"] {
    width: 100%;
    height: 6px;
    -webkit-appearance: none;
    background: #e5e7eb;
    border-radius: 3px;
}

input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 18px;
    height: 18px;
    background: #3b82f6;
    border-radius: 50%;
    cursor: pointer;
}

/* Help Text */
.help-text {
    font-size: 0.75rem;
    color: #6b7280;
    margin-bottom: 12px;
}

/* Section Dividers */
.reduction-panel h4,
.appearance-panel h4 {
    font-size: 0.8rem;
    text-transform: uppercase;
    color: #9ca3af;
    letter-spacing: 0.05em;
    margin: 20px 0 12px 0;
    padding-top: 16px;
    border-top: 1px solid #e5e7eb;
}

/* Buttons */
.btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    border: none;
    transition: all 0.15s ease;
}

.btn-primary {
    background: #3b82f6;
    color: white;
}

.btn-primary:hover {
    background: #2563eb;
}

.btn-secondary {
    background: #f3f4f6;
    color: #374151;
    border: 1px solid #d1d5db;
}

.btn-secondary:hover {
    background: #e5e7eb;
}
```

## JavaScript Interaction Logic

```javascript
// State management
const vizState = {
    type: 'auto',
    xAxis: null,
    yAxis: null,
    zAxis: null,  // For heatmaps
    reduction: {
        dimension: null,
        method: 'slice',
        value: null
    },
    colorscale: 'Viridis',
    scaleType: 'linear'
};

// Initialize controls
function initializeControls(scanData) {
    // Populate axis options
    populateAxisOptions(scanData.columns);
    
    // Set defaults based on data
    setSmartDefaults(scanData);
    
    // Show/hide dimension reduction if needed
    updateReductionVisibility(scanData.dimensions);
    
    // Add event listeners
    attachEventListeners();
}

// Smart defaults
function setSmartDefaults(scanData) {
    const dims = scanData.dimensions;
    
    if (dims === 1) {
        vizState.type = 'line';
        vizState.xAxis = scanData.movementColumns[0];
        vizState.yAxis = scanData.measurementColumns[0];
    } else if (dims === 2) {
        vizState.type = 'heatmap';
        vizState.xAxis = scanData.movementColumns[0];
        vizState.yAxis = scanData.movementColumns[1];
        vizState.zAxis = scanData.measurementColumns[0];
    } else {
        vizState.type = 'heatmap';
        // Set up reduction for extra dimensions
        vizState.reduction.dimension = scanData.movementColumns[2];
        vizState.reduction.value = scanData.dimCenters[2];
    }
}

// Update visualization on any change
function updateVisualization() {
    const processedData = applyReductions(rawData, vizState.reduction);
    
    if (vizState.type === 'heatmap') {
        renderHeatmap(processedData);
    } else {
        renderLineChart(processedData);
    }
}

// Debounce slider for performance
const debouncedUpdate = debounce(updateVisualization, 100);

document.getElementById('slice-slider').addEventListener('input', (e) => {
    vizState.reduction.value = parseFloat(e.target.value);
    document.getElementById('slice-value').textContent = e.target.value;
    debouncedUpdate();
});
```

## Responsive Design

### Mobile/Tablet Layout

```css
@media (max-width: 1024px) {
    .visualization-layout {
        flex-direction: column;
    }
    
    .visualization-controls {
        max-width: none;
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
    }
    
    .control-group {
        flex: 1;
        min-width: 200px;
    }
}

@media (max-width: 640px) {
    .control-group {
        min-width: 100%;
    }
    
    .export-controls {
        flex-direction: column;
    }
    
    .btn {
        width: 100%;
        justify-content: center;
    }
}
```

## Accessibility Features

1. **Keyboard Navigation**
   - All controls accessible via Tab key
   - Arrow keys for radio buttons
   - Enter/Space to activate buttons

2. **Screen Reader Support**
   - ARIA labels on all controls
   - Live regions for dynamic updates
   - Descriptive alt text for charts

3. **Color Contrast**
   - All text meets WCAG AA contrast requirements
   - Focus indicators clearly visible
   - Error states don't rely solely on color

```html
<div role="region" aria-label="Visualization controls">
    <div class="control-group">
        <label for="viz-type" id="viz-type-label">Visualization Type</label>
        <select id="viz-type" 
                aria-labelledby="viz-type-label"
                aria-describedby="viz-type-help">
            ...
        </select>
        <span id="viz-type-help" class="visually-hidden">
            Choose between line chart, scatter plot, or heatmap visualization
        </span>
    </div>
</div>
```

## Standard Implementation References

| Feature | Reference Implementation |
|---------|-------------------------|
| Axis selectors | Origin, MATLAB Plot Tools |
| Colorscale picker | Matplotlib, Plotly |
| Slider controls | ImageJ, Fiji |
| Dimension reduction | xarray, NetCDF viewers |
| Export options | Plotly, Google Charts |

## Implementation Timeline

1. **Week 1:** Basic type selector and axis controls
2. **Week 2:** Plotly.js heatmap integration
3. **Week 3:** Dimension reduction UI
4. **Week 4:** Export/download functionality
5. **Week 5:** Polish, accessibility, testing
