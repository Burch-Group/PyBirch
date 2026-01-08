# Dimension Reduction Strategies for Multi-Dimensional Scans

## Overview

When scans involve more than two movement dimensions (e.g., X, Y, Z positions), the data becomes too complex to visualize directly in 2D. This document outlines strategies for reducing higher-dimensional data to 2D for visualization while preserving meaningful information.

## Problem Statement

Consider a 3D scan with:
- X positions: 10 points (0-9 µm)
- Y positions: 10 points (0-9 µm)  
- Z positions: 5 points (0-4 µm)

This produces 10 × 10 × 5 = 500 measurement points. To visualize as a 2D heatmap, we must reduce one dimension.

## Dimension Reduction Strategies

### 1. Slice at Position/Index

**Concept:** Select a specific value along one dimension, showing only data at that position.

**Example:** Show XY heatmap at Z = 2 µm

**UI Implementation:**
```html
<div class="dimension-control">
    <label>Z Position:</label>
    <input type="range" id="z-slider" min="0" max="4" value="2" 
           oninput="updateSlice('z', this.value)">
    <span id="z-value">2.0 µm</span>
</div>
```

**Backend Logic:**
```python
def slice_at_position(data, dimension, position):
    """
    Extract 2D slice from N-dimensional data.
    
    Args:
        data: N-dimensional numpy array
        dimension: Axis to slice (e.g., 'z')
        position: Value or index to slice at
        
    Returns:
        (N-1)-dimensional array
    """
    axis_index = get_axis_index(dimension)
    slice_index = find_nearest_index(data.coords[dimension], position)
    return data.isel({dimension: slice_index})
```

**Advantages:**
- Preserves exact measured values
- Intuitive - like taking a cross-section
- Interactive slider for exploration

**Disadvantages:**
- Only shows one slice at a time
- May miss features at other positions

---

### 2. Maximum Value Projection

**Concept:** For each XY position, show the maximum value across all Z positions.

**Example:** Show the brightest intensity at each XY point across the Z stack.

**Implementation:**
```python
def max_projection(data, dimension):
    """Maximum intensity projection along dimension."""
    return data.max(dim=dimension)
```

```javascript
// Frontend aggregation
function maxProjection(data3D, axis) {
    const result = [];
    for (let i = 0; i < data3D.length; i++) {
        const row = [];
        for (let j = 0; j < data3D[i].length; j++) {
            let maxVal = -Infinity;
            for (let k = 0; k < data3D[i][j].length; k++) {
                maxVal = Math.max(maxVal, data3D[i][j][k]);
            }
            row.push(maxVal);
        }
        result.push(row);
    }
    return result;
}
```

**Advantages:**
- Shows "best" signal at each position
- Useful for finding features/peaks
- Common in microscopy (MIP - Maximum Intensity Projection)

**Use Cases:**
- Finding brightest Raman peaks
- Detecting defects or hotspots
- Identifying material boundaries

---

### 3. Minimum Value Projection

**Concept:** For each XY position, show the minimum value across all Z positions.

**Implementation:**
```python
def min_projection(data, dimension):
    """Minimum intensity projection along dimension."""
    return data.min(dim=dimension)
```

**Advantages:**
- Shows lowest signal regions
- Useful for absorption/attenuation data
- Identifies valleys or defects

**Use Cases:**
- Finding absorption minima
- Identifying voids or gaps
- Detecting shadowing effects

---

### 4. Average (Mean) Projection

**Concept:** For each XY position, show the average value across all Z positions.

**Implementation:**
```python
def mean_projection(data, dimension):
    """Average projection along dimension."""
    return data.mean(dim=dimension)
```

**Advantages:**
- Reduces noise through averaging
- Shows overall trend
- Less sensitive to outliers than max/min

**Disadvantages:**
- May obscure sharp features
- Doesn't show variation

---

### 5. Sum Projection

**Concept:** Sum all values along the reduced dimension.

**Implementation:**
```python
def sum_projection(data, dimension):
    """Sum projection along dimension."""
    return data.sum(dim=dimension)
```

**Use Cases:**
- Total integrated intensity
- Counting applications
- When magnitude matters more than concentration

---

### 6. Standard Deviation Projection

**Concept:** Show variability at each position.

**Implementation:**
```python
def std_projection(data, dimension):
    """Standard deviation projection along dimension."""
    return data.std(dim=dimension)
```

**Use Cases:**
- Identifying regions of high variability
- Quality control
- Finding dynamic features

---

## UI Design

### Control Panel Layout

```
┌─────────────────────────────────────────────────────────────┐
│ DIMENSION REDUCTION                                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Display Axes:                                               │
│   X-Axis: [Position X ▼]    Y-Axis: [Position Y ▼]         │
│                                                             │
│ Reduce Dimension: [Position Z ▼]                           │
│                                                             │
│ Reduction Method:                                           │
│   ○ Slice at position                                       │
│      └─ Position: [═══●═════] 2.5 µm                       │
│                                                             │
│   ○ Maximum value                                           │
│   ○ Minimum value                                           │
│   ○ Average                                                 │
│   ○ Sum                                                     │
│   ○ Standard deviation                                      │
│                                                             │
│ [Apply] [Reset to Default]                                  │
└─────────────────────────────────────────────────────────────┘
```

### Interactive Slice Explorer

For the "slice at position" option, provide an interactive slider:

```javascript
function createSliceSlider(dimension, values) {
    const container = document.getElementById('slice-controls');
    container.innerHTML = `
        <div class="slice-slider">
            <label>${dimension.label}:</label>
            <input type="range" 
                   min="0" 
                   max="${values.length - 1}" 
                   value="${Math.floor(values.length / 2)}"
                   oninput="updateSlice('${dimension.name}', this.value)">
            <span class="slider-value">${values[Math.floor(values.length / 2)]}</span>
            <span class="slider-unit">${dimension.unit}</span>
        </div>
    `;
}
```

### Multi-Dimension Support

For scans with 4+ dimensions, allow sequential reduction:

```
Original: X × Y × Z × Time (10 × 10 × 5 × 20 = 10,000 points)
                ↓
Step 1: Reduce Time → Average
Result: X × Y × Z (10 × 10 × 5 = 500 points)
                ↓
Step 2: Reduce Z → Slice at z=2
Result: X × Y (10 × 10 = 100 points)
                ↓
Display as 2D heatmap
```

## Backend API Design

### Endpoint: `/api/scans/<scan_id>/reduce`

**Request:**
```json
{
    "display_axes": ["position_x", "position_y"],
    "reductions": [
        {
            "dimension": "position_z",
            "method": "slice",
            "value": 2.5
        },
        {
            "dimension": "time",
            "method": "max"
        }
    ],
    "measurement": "intensity"
}
```

**Response:**
```json
{
    "data": {
        "z": [[1.2, 1.5, ...], [1.8, 2.1, ...], ...],
        "x": [0, 0.5, 1.0, 1.5, ...],
        "y": [0, 0.5, 1.0, 1.5, ...],
        "x_label": "Position X (µm)",
        "y_label": "Position Y (µm)",
        "z_label": "Intensity (max over Z, slice at t=0)"
    },
    "original_shape": [10, 10, 5, 20],
    "reduced_shape": [10, 10]
}
```

## Implementation Priority

1. **Phase 1:** Slice at position (most intuitive)
2. **Phase 2:** Max/Min/Average projections
3. **Phase 3:** Sum and Std projections
4. **Phase 4:** Multi-step reduction for 4+ dimensions

## References

- [xarray indexing and selecting data](https://docs.xarray.dev/en/stable/user-guide/indexing.html)
- [NumPy array manipulation](https://numpy.org/doc/stable/reference/routines.array-manipulation.html)
- [ImageJ Z-Projections](https://imagej.net/imaging/z-projection)
- [Pangeo - Open, Reproducible Geoscience](https://pangeo.io/)
