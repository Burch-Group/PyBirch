"""
Data Manager
============
Manages measurement data persistence to the database.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
import numpy as np
import pandas as pd

try:
    from database.services import DatabaseService
    from database.models import MeasurementObject, MeasurementDataPoint, MeasurementDataArray
except ImportError:
    DatabaseService = None
    MeasurementObject = None
    MeasurementDataPoint = None
    MeasurementDataArray = None


class DataManager:
    """
    Manages measurement data persistence to the database.
    
    Handles buffered writes, batch inserts, and data retrieval
    for scan measurement data.
    """
    
    def __init__(
        self,
        db_service: 'DatabaseService',
        buffer_size: int = 100,
        auto_flush: bool = True,
    ):
        """
        Initialize the DataManager.
        
        Args:
            db_service: Database service instance for persistence operations
            buffer_size: Number of data points to buffer before flushing
            auto_flush: Whether to auto-flush when buffer is full
        """
        self.db = db_service
        self.buffer_size = buffer_size
        self.auto_flush = auto_flush
        
        # Buffers: {scan_id: {measurement_name: [data_points]}}
        self._buffers: Dict[int, Dict[str, List[Dict]]] = {}
        
        # Measurement object cache: {(scan_id, measurement_name): db_id}
        self._measurement_objects: Dict[tuple, int] = {}
        
        # Sequence counters: {(scan_id, measurement_name): int}
        self._sequence_counters: Dict[tuple, int] = {}
    
    def create_measurement_object(
        self,
        scan_id: int,
        name: str,
        instrument_name: Optional[str] = None,
        columns: Optional[List[str]] = None,
        unit: Optional[str] = None,
        data_type: str = 'numeric',
    ) -> Dict[str, Any]:
        """
        Create a measurement object record for a scan.
        
        Args:
            scan_id: Database scan ID
            name: Measurement name (e.g., 'voltage', 'current')
            instrument_name: Name of the instrument
            columns: List of data column names
            unit: Unit of measurement
            data_type: Type of data ('numeric', 'array', 'image')
            
        Returns:
            Dictionary with created measurement object data
        """
        key = (scan_id, name)
        
        # Check if already exists
        if key in self._measurement_objects:
            return self.db.get_measurement_object(self._measurement_objects[key])
        
        data = {
            'scan_id': scan_id,
            'name': name,
            'instrument_name': instrument_name,
            'columns': columns,
            'unit': unit,
            'data_type': data_type,
        }
        
        mo = self.db.create_measurement_object(data)
        self._measurement_objects[key] = mo['id']
        self._sequence_counters[key] = 0
        
        return mo
    
    def save_data_point(
        self,
        scan_id: int,
        measurement_name: str,
        values: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        Save a single data point to the buffer.
        
        Args:
            scan_id: Database scan ID
            measurement_name: Name of the measurement
            values: Dictionary of values (column_name: value)
            timestamp: Timestamp for the data point
            
        Returns:
            True if successful
        """
        key = (scan_id, measurement_name)
        
        # Get or create measurement object
        if key not in self._measurement_objects:
            # Auto-create measurement object
            columns = list(values.keys())
            self.create_measurement_object(scan_id, measurement_name, columns=columns)
        
        # Initialize buffer if needed
        if scan_id not in self._buffers:
            self._buffers[scan_id] = {}
        if measurement_name not in self._buffers[scan_id]:
            self._buffers[scan_id][measurement_name] = []
        
        # Create data point
        data_point = {
            'measurement_object_id': self._measurement_objects[key],
            'sequence_index': self._sequence_counters[key],
            'values': values,
            'timestamp': (timestamp or datetime.now()).isoformat(),
        }
        
        self._buffers[scan_id][measurement_name].append(data_point)
        self._sequence_counters[key] += 1
        
        # Auto-flush if buffer is full
        if self.auto_flush and len(self._buffers[scan_id][measurement_name]) >= self.buffer_size:
            self.flush(scan_id, measurement_name)
        
        return True
    
    def save_dataframe(
        self,
        scan_id: int,
        measurement_name: str,
        data: pd.DataFrame,
        instrument_name: Optional[str] = None,
    ) -> int:
        """
        Save a DataFrame of measurement data.
        
        Args:
            scan_id: Database scan ID
            measurement_name: Name of the measurement
            data: DataFrame containing measurement data
            instrument_name: Name of the instrument
            
        Returns:
            Number of data points saved
        """
        key = (scan_id, measurement_name)
        
        # Get or create measurement object
        if key not in self._measurement_objects:
            columns = list(data.columns)
            self.create_measurement_object(
                scan_id, 
                measurement_name, 
                instrument_name=instrument_name,
                columns=columns
            )
        
        # Convert DataFrame rows to data points
        count = 0
        for idx, row in data.iterrows():
            values = row.to_dict()
            # Convert numpy types to native Python types
            values = {k: self._convert_value(v) for k, v in values.items()}
            self.save_data_point(scan_id, measurement_name, values)
            count += 1
        
        return count
    
    def save_array(
        self,
        scan_id: int,
        measurement_name: str,
        data: np.ndarray,
        data_format: str = 'numpy',
        extra_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Save an array (spectrum, image, etc.) to the database.
        
        Args:
            scan_id: Database scan ID
            measurement_name: Name of the measurement
            data: NumPy array to save
            data_format: Format identifier ('numpy', 'json')
            extra_data: Additional metadata
            
        Returns:
            Dictionary with created data array record
        """
        key = (scan_id, measurement_name)
        
        # Get or create measurement object
        if key not in self._measurement_objects:
            self.create_measurement_object(
                scan_id, 
                measurement_name, 
                data_type='array'
            )
        
        # Serialize array
        if data_format == 'numpy':
            import io
            buffer = io.BytesIO()
            np.save(buffer, data)
            data_blob = buffer.getvalue()
        else:
            data_blob = data.tobytes()
        
        array_data = {
            'measurement_object_id': self._measurement_objects[key],
            'sequence_index': self._sequence_counters.get(key, 0),
            'data_blob': data_blob,
            'data_format': data_format,
            'shape': list(data.shape),
            'dtype': str(data.dtype),
            'timestamp': datetime.now().isoformat(),
            'extra_data': extra_data,
        }
        
        self._sequence_counters[key] = self._sequence_counters.get(key, 0) + 1
        
        return self.db.create_measurement_data_array(array_data)
    
    def flush(self, scan_id: Optional[int] = None, measurement_name: Optional[str] = None):
        """
        Flush buffered data to the database.
        
        Args:
            scan_id: Specific scan to flush (None for all)
            measurement_name: Specific measurement to flush (None for all)
        """
        if scan_id is not None and measurement_name is not None:
            # Flush specific measurement
            self._flush_measurement(scan_id, measurement_name)
        elif scan_id is not None:
            # Flush all measurements for a scan
            if scan_id in self._buffers:
                for mname in list(self._buffers[scan_id].keys()):
                    self._flush_measurement(scan_id, mname)
        else:
            # Flush everything
            for sid in list(self._buffers.keys()):
                for mname in list(self._buffers[sid].keys()):
                    self._flush_measurement(sid, mname)
    
    def _flush_measurement(self, scan_id: int, measurement_name: str):
        """Flush buffer for a specific measurement."""
        if scan_id not in self._buffers:
            return
        if measurement_name not in self._buffers[scan_id]:
            return
        
        data_points = self._buffers[scan_id][measurement_name]
        if not data_points:
            return
        
        # Bulk insert
        if hasattr(self.db, 'bulk_create_data_points'):
            self.db.bulk_create_data_points(data_points)
        else:
            # Fallback to individual inserts
            for dp in data_points:
                self.db.create_measurement_data_point(dp)
        
        # Clear buffer
        self._buffers[scan_id][measurement_name] = []
    
    def get_data(
        self,
        scan_id: int,
        measurement_name: str,
        start_index: Optional[int] = None,
        end_index: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Get measurement data as a DataFrame.
        
        Args:
            scan_id: Database scan ID
            measurement_name: Name of the measurement
            start_index: Starting sequence index (inclusive)
            end_index: Ending sequence index (exclusive)
            
        Returns:
            DataFrame with measurement data
        """
        key = (scan_id, measurement_name)
        mo_id = self._measurement_objects.get(key)
        
        if not mo_id:
            # Try to find in database
            mo = self.db.get_measurement_object_by_name(scan_id, measurement_name)
            if mo:
                mo_id = mo['id']
                self._measurement_objects[key] = mo_id
            else:
                return pd.DataFrame()
        
        # Get data points
        data_points = self.db.get_measurement_data(
            mo_id, 
            start_index=start_index, 
            end_index=end_index
        )
        
        if not data_points:
            return pd.DataFrame()
        
        # Convert to DataFrame
        rows = []
        for dp in data_points:
            row = dp.get('values', {})
            row['_sequence_index'] = dp.get('sequence_index')
            row['_timestamp'] = dp.get('timestamp')
            rows.append(row)
        
        return pd.DataFrame(rows)
    
    def get_data_count(self, scan_id: int, measurement_name: Optional[str] = None) -> int:
        """Get count of data points for a scan."""
        if hasattr(self.db, 'get_data_point_count'):
            return self.db.get_data_point_count(scan_id, measurement_name)
        return 0
    
    def clear_buffers(self, scan_id: Optional[int] = None):
        """Clear data buffers without saving."""
        if scan_id is not None:
            if scan_id in self._buffers:
                del self._buffers[scan_id]
        else:
            self._buffers.clear()
    
    def _convert_value(self, value: Any) -> Any:
        """Convert numpy types to native Python types."""
        if isinstance(value, (np.integer, np.floating)):
            return value.item()
        elif isinstance(value, np.ndarray):
            return value.tolist()
        elif pd.isna(value):
            return None
        return value
