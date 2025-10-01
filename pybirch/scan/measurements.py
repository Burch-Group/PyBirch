import numpy as np
import pandas as pd
from pymeasure.instruments import Instrument
from typing import Callable
from pymeasure.instruments.keithley import Keithley2400

class Measurement:
    """Base class for measurement tools in the PyBirch framework."""

    def __init__(self, name: str):
        self.name = name
        self.data_units: np.ndarray = np.array([])
        self.data_columns: np.ndarray = np.array([])
        self.settings_UI: Callable[[], dict] = lambda: self.settings  # Placeholder for settings UI function

    def check_connection(self) -> bool:
        raise NotImplementedError("Subclasses should implement this method.")

    def perform_measurement(self) -> np.ndarray:
        # Perform the measurement and return the result as a 2D numpy array
        raise NotImplementedError("Subclasses should implement this method.")
    
    def measurement_df(self) -> pd.DataFrame:
        # Convert the raw measurement data to a pandas DataFrame
        # append units to data_columns
        columns = self.columns()
        return pd.DataFrame(self.perform_measurement(), columns=columns)
    
    def columns(self) -> np.ndarray:
        # Return the columns of the measurement data
        return np.array([f"{col} ({unit})" for col, unit in zip(self.data_columns, self.data_units)])

    @property
    def settings(self) -> dict:
        # Get the current settings of the instrument, as a dictionary
        raise NotImplementedError("Subclasses should implement this method.")
    
    @settings.setter
    def settings(self, settings: dict):
        # Set the settings of the instrument, from a dictionary
        raise NotImplementedError("Subclasses should implement this method.")

    def connect(self):
        # Connect to the instrument
        raise NotImplementedError("Subclasses should implement this method.")

    def initialize(self):
        # Initialize the measurement equipment
        pass

    def shutdown(self):
        # Shutdown the measurement equipment
        pass

class VisaMeasurement(Measurement):
    """Adds visa capabilities to the Measurement class."""

    def __init__(self, name: str, instrument: type, adapter: str = ''):
        super().__init__(name)
        self.instrument_type = instrument
        self.initialize_instrument(adapter)
    
    def initialize_instrument(self, adapter: str):
        self.instrument = self.instrument_type(adapter) if adapter else self.instrument_type()
        self.adapter = adapter



class MeasurementItem:
    """An object to hold measurement settings."""
    def __init__(self, measurement: Measurement | VisaMeasurement, settings: dict):
        self.measurement = measurement
        self.settings = settings

    def __repr__(self):
        return f"MeasurementItem(measurement={self.measurement}, settings={self.settings})"
    def __str__(self):
        return self.__repr__()