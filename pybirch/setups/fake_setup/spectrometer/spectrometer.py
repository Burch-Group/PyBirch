"""
Fake Spectrometer instrument for testing and development.

This module demonstrates how to create a measurement instrument that reads
from a data file and returns spectrum data with configurable wavelength range.

Usage:
    spectrometer = SpectrometerMeasurement("Spectrometer")
    spectrometer.connect()
    spectrometer.settings = {"left_wavelength": 400, "right_wavelength": 800}
    spectrum = spectrometer.perform_measurement()
"""

import os
import numpy as np
import pandas as pd

from pybirch.Instruments.base import FakeMeasurementInstrument
from pybirch.scan.measurements import Measurement


class FakeSpectrometer(FakeMeasurementInstrument):
    """
    A fake spectrometer that returns simulated spectrum data.
    
    This instrument loads spectrum data from a file and returns a
    subset based on the configured wavelength range, with added noise.
    """

    def __init__(self, name: str = "Mock Spectrometer", wait: float = 0.0):
        super().__init__(name, wait)
        
        # Define data columns and units
        self.data_columns = np.array(["wavelength", "intensity"])
        self.data_units = np.array(["nm", "a.u."])
        
        # Load reference spectrum data
        data_file = os.path.join(os.path.dirname(__file__), "zeophyllite_raman.txt")
        self._spectrum_data = np.loadtxt(data_file, delimiter=",")
        self._spectrum = pd.DataFrame(
            data=self._spectrum_data,
            columns=["wavelength", "intensity"]
        )
        
        # Define settings with defaults
        self._define_settings({
            "left_wavelength": 93.0,     # nm
            "right_wavelength": 1301.0,  # nm
        })
    
    def _initialize_impl(self):
        """Reset to default wavelength range."""
        self._delay()
        self._reset_settings_to_defaults()
    
    def _perform_measurement_impl(self) -> np.ndarray:
        """
        Return spectrum data within the configured wavelength range.
        
        Returns:
            2D array with columns [wavelength, intensity].
        """
        self._delay()
        
        # Filter by wavelength range
        mask = (
            (self._spectrum["wavelength"] >= self._left_wavelength) & 
            (self._spectrum["wavelength"] <= self._right_wavelength)
        )
        
        # Add noise to intensity
        noise = np.random.normal(
            0, 
            0.5 * min(self._spectrum["intensity"]), 
            self._spectrum["intensity"].shape
        )
        
        spectrum_data = self._spectrum[mask].copy()
        spectrum_data["intensity"] = spectrum_data["intensity"] + noise[mask]
        
        return spectrum_data.to_numpy()
    
    # Convenience properties with validation
    @property
    def left_wavelength(self) -> float:
        self._delay()
        return self._left_wavelength
    
    @left_wavelength.setter
    def left_wavelength(self, value: float):
        self._delay()
        if value < 0:
            raise ValueError("Left wavelength must be non-negative")
        if value > self._right_wavelength:
            raise ValueError("Left wavelength must be <= right wavelength")
        self._left_wavelength = value
    
    @property
    def right_wavelength(self) -> float:
        self._delay()
        return self._right_wavelength
    
    @right_wavelength.setter
    def right_wavelength(self, value: float):
        self._delay()
        if value < self._left_wavelength:
            raise ValueError("Right wavelength must be >= left wavelength")
        self._right_wavelength = value


class SpectrometerMeasurement(Measurement):
    """
    Measurement wrapper for the FakeSpectrometer.
    
    This class wraps the FakeSpectrometer to conform to the standard
    PyBirch Measurement interface for use in scans.
    """

    def __init__(self, name: str = "Spectrometer Measurement"):
        super().__init__(name)
        self.instrument = FakeSpectrometer()
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
    
    