import re
import time
import numpy as np
import pandas as pd

from pymeasure.adapters import FakeAdapter
from pymeasure.instruments import Instrument, fakes
from pybirch.scan.measurements import Measurement


class FakeLockinAmplifier(fakes.FakeInstrument):
    """A fake lock-in amplifier for simulating a lock-in instrument."""

    def __init__(self, name: str ="Mock Lock-in Amplifier", wait: float = 0, **kwargs):
        super().__init__(
            name=name,
            includeSCPI=False,
            **kwargs
        )

        # variables to simulate the lock-in amplifier's state; these do not exist for real instruments
        self._wait = wait
        self._num_data_points = 100
        self._sensitivity = 1.0  # Sensitivity in V
        self._units = np.array(["V", "V", "V"])  # X, Y, R units
        self._time_constant = 0.1  # Time constant in seconds
        self.data_columns = np.array(["X", "Y", "R"])  # Data columns for X, Y, R
    
    def connect(self):
        """Connect to the lock-in amplifier."""
        time.sleep(self._wait)
        return

    def initialize(self):
        """Initialize the lock-in amplifier."""
        time.sleep(self._wait)
        self._num_data_points = 100
        self._sensitivity = 1.0
        self._time_constant = 0.1
        return
    
    def shutdown(self):
        """Shutdown the lock-in amplifier."""
        time.sleep(self._wait)
        return

    def perform_measurement(self) -> np.ndarray:
        """Perform a measurement and return the results as a numpy array."""
        time.sleep(self._wait)
        return self.data

    @property
    def sensitivity(self):
        time.sleep(self._wait)
        return self._sensitivity
    
    @sensitivity.setter
    def sensitivity(self, value):
        time.sleep(self._wait)
        if value > 0:
            self._sensitivity = value
        else:
            raise ValueError("Sensitivity must be positive")
    
    @property
    def time_constant(self):
        time.sleep(self._wait)
        return self._time_constant
    
    @time_constant.setter
    def time_constant(self, value):
        time.sleep(self._wait)
        if value > 0:
            self._time_constant = value
        else:
            raise ValueError("Time constant must be positive")
        
    @property
    def num_data_points(self):
        time.sleep(self._wait)
        return self._num_data_points

    @num_data_points.setter
    def num_data_points(self, value):
        time.sleep(self._wait)
        if value > 0:
            self._num_data_points = value
        else:
            raise ValueError("Number of data points must be positive")
    
    @property
    def data(self):
        time.sleep(self._wait)
        X_data = np.random.normal(-3, 0.5, self._num_data_points)
        Y_data = np.random.normal(2, 0.5, self._num_data_points)
        R_data = np.sqrt(X_data**2 + Y_data**2)
        return np.array([X_data, Y_data, R_data]).T

    @property
    def settings(self) -> dict:
        return {
            "sensitivity": self.sensitivity,
            "time_constant": self.time_constant,
            "num_data_points": self.num_data_points
        }
    
    @settings.setter
    def settings(self, settings: dict):
        time.sleep(self._wait)
        if "sensitivity" in settings:
            self.sensitivity = settings["sensitivity"]
        if "time_constant" in settings:
            self.time_constant = settings["time_constant"]
        if "num_data_points" in settings:
            self.num_data_points = settings["num_data_points"]
    

class LockInAmplifierMeasurement(Measurement):
    """Measurement class for the lock-in amplifier."""

    def __init__(self, name: str, instrument: FakeLockinAmplifier):
        super().__init__(name, instrument)
        self.data_units = self.instrument._units
        self.data_columns = self.instrument.data_columns

    def perform_measurement(self) -> np.ndarray:
        """Perform the measurement."""
        return self.instrument.perform_measurement()
    def connect(self):
        self.instrument.connect()
    def initialize(self):
        """Initialize the lock-in amplifier."""
        self.instrument.initialize()
    def shutdown(self):
        """Shutdown the lock-in amplifier."""
        self.instrument.shutdown()
    @property
    def settings(self) -> dict:
        return {
            "sensitivity": self.instrument.sensitivity,
            "time_constant": self.instrument.time_constant,
            "num_data_points": self.instrument.num_data_points
        }
    @settings.setter
    def settings(self, settings: dict):
        """Set the settings of the lock-in amplifier."""
        self.instrument.settings = settings
    

