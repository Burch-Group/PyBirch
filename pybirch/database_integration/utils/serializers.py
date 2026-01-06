"""
Serializers
===========
Functions for converting PyBirch objects to database-compatible formats.
"""

import json
import base64
from datetime import datetime
from typing import Any, Dict, Optional, List

# Try to import numpy
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def serialize_scan_settings(scan_settings: 'ScanSettings') -> Dict[str, Any]:
    """
    Serialize PyBirch ScanSettings to a dictionary for database storage.
    
    Args:
        scan_settings: PyBirch ScanSettings object
        
    Returns:
        Dictionary representation
    """
    return {
        'scan_type': getattr(scan_settings, 'scan_type', None),
        'num_scans': getattr(scan_settings, 'num_scans', 1),
        'scan_rate': getattr(scan_settings, 'scan_rate', None),
        'dwell_time': getattr(scan_settings, 'dwell_time', None),
        'measurements': _serialize_measurement_items(scan_settings),
        'movements': _serialize_movement_items(scan_settings),
        'metadata': getattr(scan_settings, 'metadata', {}),
        'extra_settings': _get_extra_settings(scan_settings),
    }


def _serialize_measurement_items(scan_settings: 'ScanSettings') -> List[Dict]:
    """Serialize measurement items."""
    items = []
    measurements = getattr(scan_settings, 'measurement_items', [])
    
    for item in measurements:
        items.append({
            'name': getattr(item, 'name', str(item)),
            'instrument': getattr(item, 'instrument_name', None),
            'settings': getattr(item, 'settings', {}),
        })
    
    return items


def _serialize_movement_items(scan_settings: 'ScanSettings') -> List[Dict]:
    """Serialize movement items."""
    items = []
    movements = getattr(scan_settings, 'movement_items', [])
    
    for item in movements:
        items.append({
            'name': getattr(item, 'name', str(item)),
            'instrument': getattr(item, 'instrument_name', None),
            'start': getattr(item, 'start', None),
            'stop': getattr(item, 'stop', None),
            'step': getattr(item, 'step', None),
            'num_points': getattr(item, 'num_points', None),
            'settings': getattr(item, 'settings', {}),
        })
    
    return items


def _get_extra_settings(scan_settings: 'ScanSettings') -> Dict[str, Any]:
    """Get additional settings not covered by standard fields."""
    exclude = {
        'scan_type', 'num_scans', 'scan_rate', 'dwell_time',
        'measurement_items', 'movement_items', 'metadata'
    }
    
    extra = {}
    for key, value in vars(scan_settings).items():
        if key not in exclude and not key.startswith('_'):
            try:
                json.dumps(value)  # Check if serializable
                extra[key] = value
            except (TypeError, ValueError):
                extra[key] = str(value)
    
    return extra


def deserialize_scan_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deserialize scan settings from database.
    
    Args:
        data: Dictionary from database
        
    Returns:
        Dictionary that can be used to reconstruct ScanSettings
    """
    return data  # Currently just returns as-is


def serialize_equipment_settings(settings: Any) -> Dict[str, Any]:
    """
    Serialize instrument settings to a dictionary.
    
    Args:
        settings: InstrumentSettings object or dict
        
    Returns:
        Dictionary representation
    """
    if settings is None:
        return {}
    
    if isinstance(settings, dict):
        return _make_json_serializable(settings)
    
    # Try to get settings from object
    if hasattr(settings, 'to_dict'):
        return _make_json_serializable(settings.to_dict())
    
    if hasattr(settings, '__dict__'):
        return _make_json_serializable({
            k: v for k, v in vars(settings).items()
            if not k.startswith('_')
        })
    
    return {'value': str(settings)}


def _make_json_serializable(obj: Any) -> Any:
    """Make an object JSON serializable."""
    if obj is None:
        return None
    
    if isinstance(obj, (str, int, float, bool)):
        return obj
    
    if isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    
    if isinstance(obj, (list, tuple)):
        return [_make_json_serializable(v) for v in obj]
    
    if isinstance(obj, datetime):
        return obj.isoformat()
    
    if HAS_NUMPY:
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        if isinstance(obj, np.bool_):
            return bool(obj)
    
    # Fallback: convert to string
    return str(obj)


def deserialize_equipment_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deserialize equipment settings from database.
    
    Args:
        data: Dictionary from database
        
    Returns:
        Dictionary of settings
    """
    return data or {}


def serialize_numpy_array(arr: 'np.ndarray') -> Dict[str, Any]:
    """
    Serialize a NumPy array for database storage.
    
    Args:
        arr: NumPy array
        
    Returns:
        Dictionary with base64-encoded data and metadata
    """
    if not HAS_NUMPY:
        raise RuntimeError("NumPy not available")
    
    return {
        'dtype': str(arr.dtype),
        'shape': arr.shape,
        'data': base64.b64encode(arr.tobytes()).decode('ascii'),
        'format': 'numpy_b64',
    }


def deserialize_numpy_array(data: Dict[str, Any]) -> 'np.ndarray':
    """
    Deserialize a NumPy array from database storage.
    
    Args:
        data: Dictionary with encoded array
        
    Returns:
        NumPy array
    """
    if not HAS_NUMPY:
        raise RuntimeError("NumPy not available")
    
    if data.get('format') != 'numpy_b64':
        raise ValueError(f"Unknown format: {data.get('format')}")
    
    dtype = np.dtype(data['dtype'])
    shape = tuple(data['shape'])
    raw = base64.b64decode(data['data'])
    
    return np.frombuffer(raw, dtype=dtype).reshape(shape)


def serialize_dataframe(df: 'pd.DataFrame') -> Dict[str, Any]:
    """
    Serialize a pandas DataFrame for database storage.
    
    Args:
        df: DataFrame
        
    Returns:
        Dictionary with column data
    """
    return {
        'columns': df.columns.tolist(),
        'index': df.index.tolist(),
        'data': df.values.tolist(),
        'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
        'format': 'pandas_dict',
    }


def deserialize_dataframe(data: Dict[str, Any]) -> 'pd.DataFrame':
    """
    Deserialize a DataFrame from database storage.
    
    Args:
        data: Dictionary with DataFrame data
        
    Returns:
        pandas DataFrame
    """
    import pandas as pd
    
    df = pd.DataFrame(
        data['data'],
        index=data['index'],
        columns=data['columns'],
    )
    
    # Restore dtypes where possible
    for col, dtype_str in data.get('dtypes', {}).items():
        try:
            df[col] = df[col].astype(dtype_str)
        except (ValueError, TypeError):
            pass
    
    return df


def format_scan_id(prefix: str = 'SCAN') -> str:
    """
    Generate a formatted scan ID.
    
    Args:
        prefix: Prefix for the ID
        
    Returns:
        Formatted ID string like 'SCAN-20250101-001'
    """
    from datetime import datetime
    import random
    
    date_str = datetime.now().strftime('%Y%m%d')
    random_suffix = f"{random.randint(0, 999):03d}"
    
    return f"{prefix}-{date_str}-{random_suffix}"


def format_queue_id(prefix: str = 'Q') -> str:
    """
    Generate a formatted queue ID.
    
    Args:
        prefix: Prefix for the ID
        
    Returns:
        Formatted ID string like 'Q-20250101-001'
    """
    return format_scan_id(prefix)
