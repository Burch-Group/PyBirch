import re
import time
import numpy as np
import pandas as pd

from pymeasure.adapters import FakeAdapter
from pymeasure.instruments import Instrument, fakes

from pybirch.scan.measurements import Measurement
from pybirch.scan.movements import Movement


class FakeMultimeter(fakes.FakeInstrument):
    """A fake multimeter for simulating a multimeter instrument."""

    def __init__(self, name: str ="Mock Multimeter", wait: float = 0, **kwargs):
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
        self._current = value
    
    @property
    def voltage(self):
        time.sleep(self._wait)
        return self._voltage
    
    @voltage.setter
    def voltage(self, value):
        time.sleep(self._wait)
        self._voltage = value


# define a measurement subclass for the voltage_meter of the multimeter
# instrument is a placeholder; will be replaced with actual instrument instance at runtime
# We do not use a VisaMeasurement subclass here because FakeMultimeter does not use a visa adapter
class VoltageMeterMeasurement(Measurement):
    def __init__(self, name: str):
        super().__init__(name)
        self.instrument = FakeMultimeter()
        self.data_dimensions = (2,1)  # 1 column for current, 1 column for voltage
        self.data_units = np.array(["A","V"])
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
            
        data = np.array([currents, voltages]).T
        return data

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
    
    @property
    def settings(self):
        # Get the current settings of the instrument, as a dictionary
        return {
            "current": self.instrument.current,
            "voltage": self.instrument.voltage,
            "units": self.instrument._units,
            "wait": self.instrument._wait
        }
    
    @settings.setter
    def settings(self, settings):
        # Set the settings of the instrument, from a dictionary
        time.sleep(self.instrument._wait)
        if "current" in settings:
            self.instrument.current = settings["current"]
        if "voltage" in settings:
            self.instrument.voltage = settings["voltage"]
        if "units" in settings:
            self.instrument._units = np.array(settings["units"])
        if "wait" in settings:
            self.instrument._wait = settings["wait"]




# next a movement subclass for the current source of the multimeter
class CurrentSourceMovement(Movement):
    def __init__(self, name: str):
        super().__init__(name)
        self.instrument = FakeMultimeter()
        self.position_shape = (1,)  # 1D position
        self.position_units = "A"
        self.position_column = "current"

    @property
    def position(self):
        time.sleep(self.instrument._wait)
        return self.instrument.current
    
    @position.setter
    def position(self, value):
        time.sleep(self.instrument._wait)
        self.instrument.current = value
    
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
    
    @property
    def settings(self):
        # Get the current settings of the instrument, as a dictionary
        return {
            "current": self.instrument.current,
            "units": self.instrument._units,
            "wait": self.instrument._wait
        }
    
    @settings.setter
    def settings(self, settings):
        # Set the settings of the instrument, from a dictionary
        time.sleep(self.instrument._wait)
        if "current" in settings:
            self.instrument.current = settings["current"]
        if "units" in settings:
            self.instrument._units = np.array(settings["units"])
        if "wait" in settings:
            self.instrument._wait = settings["wait"]




