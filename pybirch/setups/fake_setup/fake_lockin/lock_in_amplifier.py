import re
import time
import numpy as np
import pandas as pd

from pymeasure.adapters import FakeAdapter
from pymeasure.instruments import Instrument, fakes


class FakeLockinAmplifier(fakes.FakeInstrument):
    """A fake lock-in amplifier for simulating a lock-in instrument."""

    def __init__(self, name="Mock Lock-in Amplifier", wait=.1, **kwargs):
        super().__init__(
            name=name,
            includeSCPI=False,
            **kwargs
        )
        self._wait = wait
        self._num_data_points = 100
        self._sensitivity = 1.0  # Sensitivity in V
        self._units = np.array(["volts", "volts", "volts"])  # X, Y, R units
        self._time_constant = 0.1  # Time constant in seconds
    
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
        return pd.DataFrame({"X": X_data, "Y": Y_data, "R": R_data})
