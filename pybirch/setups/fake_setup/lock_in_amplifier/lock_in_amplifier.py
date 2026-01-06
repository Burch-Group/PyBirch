"""
Fake Lock-In Amplifier instrument for testing and development.

This module demonstrates how to create a measurement instrument using the
simplified PyBirch instrument architecture. The FakeLockInAmplifier simulates
a lock-in amplifier that returns X, Y, and R data.

Usage:
    # Create and use the measurement class directly
    measurement = LockInAmplifierMeasurement("My Lock-In")
    measurement.connect()
    measurement.initialize()
    data = measurement.perform_measurement()
    
    # Access settings
    measurement.settings = {"sensitivity": 1e-6, "time_constant": 0.3}
    print(measurement.settings)
"""

import numpy as np

from pybirch.Instruments.base import FakeMeasurementInstrument
from pybirch.scan.measurements import Measurement


class FakeLockInAmplifier(FakeMeasurementInstrument):
    """
    A fake lock-in amplifier for simulating lock-in measurements.
    
    This instrument simulates X, Y, and R (magnitude) measurements with
    configurable sensitivity, time constant, and number of data points.
    """

    def __init__(self, name: str = "Mock Lock-in Amplifier", wait: float = 0.0):
        super().__init__(name, wait)
        
        # Define data columns and units
        self.data_columns = np.array(["X", "Y", "R"])
        self.data_units = np.array(["V", "V", "V"])
        
        # Define instrument settings with defaults
        self._define_settings({
            "sensitivity": 1.0,      # Sensitivity in V
            "time_constant": 0.1,    # Time constant in seconds
            "num_data_points": 10,   # Number of data points per measurement
        })
    
    def _initialize_impl(self):
        """Reset instrument to default state."""
        self._delay()
        self._reset_settings_to_defaults()
    
    def _shutdown_impl(self):
        """Cleanup on shutdown."""
        self._delay()
    
    def _perform_measurement_impl(self) -> np.ndarray:
        """
        Perform a simulated lock-in measurement.
        
        Returns:
            2D array with shape (num_data_points, 3) containing X, Y, R data.
        """
        self._delay()
        n = self._num_data_points
        
        # Simulate noisy X and Y data
        X_data = np.random.normal(-3, 0.5, n)
        Y_data = np.random.normal(2, 0.5, n)
        R_data = np.sqrt(X_data**2 + Y_data**2)
        
        return np.column_stack([X_data, Y_data, R_data])
    
    # Properties for direct access to settings (optional convenience)
    @property
    def sensitivity(self) -> float:
        self._delay()
        return self._sensitivity
    
    @sensitivity.setter
    def sensitivity(self, value: float):
        self._delay()
        if value <= 0:
            raise ValueError("Sensitivity must be positive")
        self._sensitivity = value
    
    @property
    def time_constant(self) -> float:
        self._delay()
        return self._time_constant
    
    @time_constant.setter
    def time_constant(self, value: float):
        self._delay()
        if value <= 0:
            raise ValueError("Time constant must be positive")
        self._time_constant = value
    
    @property
    def num_data_points(self) -> int:
        self._delay()
        return self._num_data_points
    
    @num_data_points.setter
    def num_data_points(self, value: int):
        self._delay()
        if value <= 0:
            raise ValueError("Number of data points must be positive")
        self._num_data_points = value


class LockInAmplifierMeasurement(Measurement):
    """
    Measurement wrapper for the FakeLockInAmplifier.
    
    This class wraps the FakeLockInAmplifier to conform to the standard
    PyBirch Measurement interface for use in scans.
    """

    def __init__(self, name: str = "Lock-In Measurement"):
        super().__init__(name)
        self.instrument = FakeLockInAmplifier()
        self.data_units = self.instrument.data_units
        self.data_columns = self.instrument.data_columns

    def check_connection(self) -> bool:
        return self.instrument.check_connection()

    def perform_measurement(self) -> np.ndarray:
        return self.instrument.perform_measurement()
    
    def connect(self):
        self.instrument.connect()
        self.status = self.instrument.status

    def initialize(self):
        self.instrument.initialize()

    def shutdown(self):
        self.instrument.shutdown()

    @property
    def settings(self) -> dict:
        return self.instrument.settings
    
    @settings.setter
    def settings(self, settings: dict):
        self.instrument.settings = settings