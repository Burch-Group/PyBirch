# 1D Line and 2D Heatmap Visualization

## Overview

This document outlines the implementation plan for providing users with flexible visualization options for scan data. Users should be able to switch between 1D line/scatter plots and 2D heatmap visualizations depending on their data and analysis needs.

## Current State

Currently, the scan detail page uses Chart.js for 1D scatter/line plots. This works well for:
- Single-axis scans (e.g., IV curves)
- Time-series data
- Simple 2D relationships (X vs Y)

## Proposed Features

### 1. Visualization Type Selector

Add a dropdown or toggle button to switch between visualization modes:

```html
<div class="viz-type-selector">
    <label>Visualization Type:</label>
    <select id="vizType" onchange="updateVisualization()">
        <option value="line">1D Line Chart</option>
        <option value="scatter">1D Scatter Plot</option>
        <option value="heatmap">2D Heatmap</option>
    </select>
</div>
```

### 2. 1D Line/Scatter Visualization

**Library:** Chart.js (already implemented)

**Features:**
- Line interpolation options (linear, step, cubic)
- Point markers toggle
- Multi-series overlay support
- Axis label customization
- Zoom and pan capabilities

**Data Format:**
```javascript
{
    datasets: [{
        label: 'Measurement',
        data: [{x: 0, y: 10}, {x: 1, y: 15}, {x: 2, y: 12}],
        borderColor: 'rgb(75, 192, 192)',
        tension: 0.1  // Line smoothing
    }]
}
```

### 3. 2D Heatmap Visualization

**Library:** Plotly.js (recommended for heatmaps)

**CDN:** `https://cdn.plot.ly/plotly-3.3.1.min.js`

**Features:**
- Color scale selection (Viridis, Plasma, Inferno, Magma, Cividis)
- Interactive hover with value display
- Color bar with min/max labels
- Axis tick customization for categorical or numerical axes
- Annotations for specific cells

**Data Format:**
```javascript
{
    z: [[1, 20, 30], [20, 1, 60], [30, 60, 1]],  // 2D array of values
    x: ['x1', 'x2', 'x3'],  // X-axis labels (optional)
    y: ['y1', 'y2', 'y3'],  // Y-axis labels (optional)
    type: 'heatmap',
    colorscale: 'Viridis',
    showscale: true
}
```

## Implementation Plan

### Phase 1: Backend Data Preparation

1. **Modify `get_visualization_data()` in services.py**
   - Add logic to reshape 1D data into 2D grid when applicable
   - Return grid dimensions and axis values
   - Handle irregular grids gracefully

```python
def get_visualization_data(scan_id, output_format='auto'):
    """
    Args:
        scan_id: The scan ID
        output_format: 'line', 'heatmap', or 'auto'
    
    Returns:
        dict with keys:
            - 'line_data': [{x, y, ...}, ...]
            - 'heatmap_data': {'z': [[...]], 'x': [...], 'y': [...]}
            - 'dimensions': number of movement dimensions
            - 'suggested_type': 'line' or 'heatmap'
    """
```

2. **Grid Detection Logic**
   - Detect if data points form a regular 2D grid
   - Identify X and Y axes from movement columns
   - Reshape measurement values into 2D matrix

### Phase 2: Frontend Visualization

1. **Add Plotly.js to templates**
```html
<script src="https://cdn.plot.ly/plotly-3.3.1.min.js"></script>
```

2. **Create visualization container**
```html
<div id="visualization-container">
    <div id="line-chart" style="display: none;"></div>
    <div id="heatmap-chart" style="display: none;"></div>
</div>
```

3. **Implement switching logic**
```javascript
function updateVisualization() {
    const vizType = document.getElementById('vizType').value;
    
    if (vizType === 'heatmap') {
        document.getElementById('line-chart').style.display = 'none';
        document.getElementById('heatmap-chart').style.display = 'block';
        renderHeatmap(heatmapData);
    } else {
        document.getElementById('heatmap-chart').style.display = 'none';
        document.getElementById('line-chart').style.display = 'block';
        renderLineChart(lineData, vizType);
    }
}
```

4. **Heatmap rendering function**
```javascript
function renderHeatmap(data) {
    const trace = {
        z: data.z,
        x: data.x,
        y: data.y,
        type: 'heatmap',
        colorscale: 'Viridis',
        hoverongaps: false
    };
    
    const layout = {
        title: 'Scan Heatmap',
        xaxis: { title: data.xLabel },
        yaxis: { title: data.yLabel }
    };
    
    Plotly.newPlot('heatmap-chart', [trace], layout);
}
```

### Phase 3: Smart Defaults

1. **Auto-detect best visualization**
   - 1 movement axis → Line chart
   - 2 movement axes (regular grid) → Heatmap
   - 2+ axes (irregular) → Line chart with dimension reduction options

2. **Show suggestion to user**
```html
<div class="viz-suggestion" v-if="suggestedType !== selectedType">
    💡 Suggested: {{ suggestedType }} for this data type
</div>
```

## UI Mockup

```
┌─────────────────────────────────────────────────────────────┐
│ Scan: IV Measurement - Run 001                              │
├─────────────────────────────────────────────────────────────┤
│ Visualization Type: [Line Chart ▼]  Color Scale: [Viridis▼]│
│                                                             │
│ X-Axis: [voltage ▼]  Y-Axis: [current ▼]                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│     ┌──────────────────────────────────────────┐           │
│     │                    *                      │           │
│     │                 *     *                   │           │
│     │              *           *                │           │
│     │           *                 *             │           │
│  Y  │        *                       *          │           │
│     │     *                             *       │           │
│     │  *                                   *    │           │
│     └──────────────────────────────────────────┘           │
│                         X                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Color Scale Options

| Name | Best For |
|------|----------|
| Viridis | General purpose, perceptually uniform |
| Plasma | High contrast, colorblind-friendly |
| Inferno | Dark backgrounds, high intensity range |
| Magma | Similar to Inferno, slightly softer |
| Cividis | Colorblind-optimized |
| RdBu | Diverging data (e.g., positive/negative) |
| Hot | Temperature or intensity data |

## Accessibility Considerations

1. **Colorblind-friendly defaults** - Use Viridis or Cividis by default
2. **Value labels on hover** - Always show exact values
3. **Download options** - Allow export as PNG/SVG for publications
4. **High contrast mode** - Option for high contrast color schemes

## References

- [Plotly.js Heatmaps](https://plotly.com/javascript/heatmaps/)
- [Chart.js Line Charts](https://www.chartjs.org/docs/latest/charts/line.html)
- [ColorBrewer2 Color Schemes](https://colorbrewer2.org/)
- [Matplotlib Colormaps](https://matplotlib.org/stable/tutorials/colors/colormaps.html)
