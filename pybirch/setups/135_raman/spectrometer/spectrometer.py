import re
import time
import numpy as np
import pandas as pd

from pymeasure.adapters import FakeAdapter
from pymeasure.instruments import Instrument, fakes
from pybirch.scan.measurements import Measurement

import os

class FakeSpectrometer(fakes.FakeInstrument):
    """A fake spectrometer for simulating a spectrometer instrument."""

    def __init__(self, name: str ="Mock Spectrometer", wait: float = 0, **kwargs):
        super().__init__(
            name=name,
            includeSCPI=False,
            **kwargs
        )
        self._wait = wait
        self._left_wavelength = 93.0  # leftmost wavelength in nm
        self._right_wavelength = 1301.0  # rightmost wavelength in nm
        self._units = np.array(["nm", "a.u."])
        self._spectrum_data = np.loadtxt(os.path.join(os.path.dirname(__file__), "zeophyllite_raman.txt"), delimiter=",")
        self._spectrum = pd.DataFrame(
            data=self._spectrum_data,
            columns=["wavelength", "intensity"]
        )

    @property
    def left_wavelength(self):
        time.sleep(self._wait)
        return self._left_wavelength
    
    @left_wavelength.setter
    def left_wavelength(self, value):
        time.sleep(self._wait)
        if 0 <= value <= self.right_wavelength:
            self._left_wavelength = value
        else:
            raise ValueError("Left wavelength out of bounds")
    
    @property
    def right_wavelength(self):
        time.sleep(self._wait)
        return self._right_wavelength
    
    @right_wavelength.setter
    def right_wavelength(self, value):
        time.sleep(self._wait)
        if self.left_wavelength <= value:
            self._right_wavelength = value
        else:
            raise ValueError("Right wavelength out of bounds")
    
    @property
    def spectrum(self):
        # returns pandas dataframe with wavelength and intensity data.
        time.sleep(self._wait)

        
        mask = (self._spectrum["wavelength"] >= self.left_wavelength) & \
               (self._spectrum["wavelength"] <= self.right_wavelength)
        noise = np.random.normal(0, 0.5*min(self._spectrum["intensity"]), self._spectrum["intensity"].shape)

        spectrum_data = self._spectrum[mask].copy()
        spectrum_data["intensity"] += noise[mask]
        return spectrum_data.reset_index(drop=True)

    @property
    def units(self):    
        time.sleep(self._wait)
        return self._units
    
    @units.setter
    def units(self, value):
        time.sleep(self._wait)
        self._units = value
        self._wavelength_unit, self._intensity_unit = value
    

class SpectrometerMeasurement(Measurement):
    """Measurement class for the spectrometer."""

    def __init__(self, name: str, instrument: FakeSpectrometer):
        super().__init__(name, instrument)
        self.data_units = instrument.units
        self.data_columns = np.array(["wavelength", "intensity"])

    def perform_measurement(self) -> np.ndarray:
        """Perform the measurement and return the result as a numpy array."""
        time.sleep(self.instrument._wait)
        return self.instrument.spectrum.to_numpy()
    
    @property
    def settings(self) -> dict:
        return {
            "left_wavelength": self.instrument.left_wavelength,
            "right_wavelength": self.instrument.right_wavelength,
            "units": self.instrument.units
        }
    @settings.setter
    def settings(self, settings: dict):
        if "left_wavelength" in settings:
            self.instrument.left_wavelength = settings["left_wavelength"]
        if "right_wavelength" in settings:
            self.instrument.right_wavelength = settings["right_wavelength"]
        if "units" in settings:
            self.instrument.units = settings["units"]

    def connect(self):
        # Connect to the spectrometer
        time.sleep(self.instrument._wait)
        return
    
    def initialize(self):
        # Initialize the spectrometer
        time.sleep(self.instrument._wait)
        self.instrument.left_wavelength = 93.0
        self.instrument.right_wavelength = 1301.0
        self.instrument.units = ("nm", "a.u.")

    def shutdown(self):
        # Shutdown the spectrometer
        time.sleep(self.instrument._wait)
        return
    
    