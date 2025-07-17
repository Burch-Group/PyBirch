import re
import time
import numpy as np
import pandas as pd

from pymeasure.adapters import FakeAdapter
from pymeasure.instruments import Instrument, fakes


class FakeSpectrometer(fakes.FakeInstrument):
    """A fake spectrometer for simulating a spectrometer instrument."""

    def __init__(self, name="Mock Spectrometer", wait=.1, **kwargs):
        super().__init__(
            name=name,
            includeSCPI=False,
            **kwargs
        )
        self._wait = wait
        self._left_wavelength = 93.0  # leftmost wavelength in nm
        self._right_wavelength = 1301.0  # rightmost wavelength in nm
        self._units = np.array(["nm", "a.u."])
        self._spectrum_data = np.loadtxt("zeophyllite_raman.txt", delimiter=",")
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
        if not isinstance(value, tuple) or len(value) != 2:
            raise ValueError("Units must be a tuple of (wavelength_unit, intensity_unit)")
        self._wavelength_unit, self._intensity_unit = value
    


