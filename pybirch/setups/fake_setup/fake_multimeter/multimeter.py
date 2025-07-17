import re
import time
import numpy as np
import pandas as pd

from pymeasure.adapters import FakeAdapter
from pymeasure.instruments import Instrument, fakes

from pybirch.scan.measurement import Measurement
from pybirch.scan.movement import Movement


class FakeMultimeter(fakes.FakeInstrument):
    """A fake multimeter for simulating a multimeter instrument."""

    def __init__(self, name="Mock Multimeter", wait=.1, **kwargs):
        super().__init__(
            name=name,
            includeSCPI=False,
            **kwargs
        )
        self._wait = wait
        self._current = 0.0
        self._voltage = 0.0
        self._units = np.array(["amperes", "volts"])

    @property
    def current(self):
        time.sleep(self._wait)
        return self._current
    
    @current.setter
    def current(self, value):
        time.sleep(self._wait)
        if value >= 0:
            self._current = value
        else:
            raise ValueError("Current must be non-negative")
    
    @property
    def voltage(self):
        time.sleep(self._wait)
        return self._voltage
    
    @voltage.setter
    def voltage(self, value):
        time.sleep(self._wait)
        if value >= 0:
            self._voltage = value
        else:
            raise ValueError("Voltage must be non-negative")

# define a measurement subclass for the voltage_meter of the multimeter
# instrument is a placeholder; will be replaced with actual instrument instance at runtime
class VoltageMeterMeasurement(Measurement):
    def __init__(self, name, instrument):
        super().__init__(name, instrument)
        self.data_dimensions = (2,1)  # 1 column for current, 1 column for voltage
        self.data_units = np.array(["amperes","volts"])
        self.data_columns = np.array(["current", "voltage"])
        self.num_data_points = 10

    def perform_measurement(self):
        # Simulate a measurement by reading the current and voltage
        time.sleep(self.instrument._wait)
        currents = []
        voltages = []
        for _ in range(self.num_data_points):
            currents.append(self.instrument.current)
            voltages.append(self.instrument.voltage + np.random.normal(0, 0.01))
            
        data = np.array([[currents, voltages]])
        return pd.DataFrame(data, columns=self.data_columns)

    def connect(self):
        # Connect to the multimeter
        # pretend there are some functions here
        time.sleep(self.instrument._wait)
        return
    
    def initialize(self):
        # Initialize the multimeter
        time.sleep(self.instrument._wait)
        self.instrument.current = 0.0
        self.instrument.voltage = 0.0
        return
    
    def shutdown(self):
        return
    
    def settings(self):
        # Get the current settings of the instrument, as a dictionary
        return {
            "current": self.instrument.current,
            "voltage": self.instrument.voltage,
            "units": self.instrument._units,
            "wait": self.instrument._wait
        }
    
    @settings.setter
    def settings(self, settings_dict):
        # Set the settings of the instrument, from a dictionary
        time.sleep(self.instrument._wait)
        if "current" in settings_dict:
            self.instrument.current = settings_dict["current"]
        if "voltage" in settings_dict:
            self.instrument.voltage = settings_dict["voltage"]
        if "units" in settings_dict:
            self.instrument._units = np.array(settings_dict["units"])
        if "wait" in settings_dict:
            self.instrument._wait = settings_dict["wait"]




# next a movement subclass for the current source of the multimeter
class CurrentSourceMovement(Movement):
    def __init__(self, name, instrument):
        super().__init__(name, instrument)
        self.position_shape = (1,)  # 1D position
        self.position_units = "amperes"

    @property
    def position(self):
        time.sleep(self.instrument._wait)
        return self.instrument.current
    
    @position.setter
    def position(self, value):
        time.sleep(self.instrument._wait)
        if value >= 0:
            self.instrument.current = value
        else:
            raise ValueError("Current must be non-negative")
    
    def connect(self):
        # Connect to the multimeter
        time.sleep(self.instrument._wait)
        return
    
    def initialize(self):
        # Initialize the current source
        time.sleep(self.instrument._wait)
        self.instrument.current = 0.0
        return
    
    def shutdown(self):
        return
    
    def settings(self):
        # Get the current settings of the instrument, as a dictionary
        return {
            "current": self.instrument.current,
            "units": self.instrument._units,
            "wait": self.instrument._wait
        }
    
    @settings.setter
    def settings(self, settings_dict):
        # Set the settings of the instrument, from a dictionary
        time.sleep(self.instrument._wait)
        if "current" in settings_dict:
            self.instrument.current = settings_dict["current"]
        if "units" in settings_dict:
            self.instrument._units = np.array(settings_dict["units"])
        if "wait" in settings_dict:
            self.instrument._wait = settings_dict["wait"]


voltage_meter = Measurement("Voltage Meter", FakeMultimeter())