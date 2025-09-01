import numpy as np
import pandas as pd
from pymeasure.instruments import Instrument
from typing import Callable

class Measurement:
    """Base class for measurement tools in the PyBirch framework."""

    def __init__(self, name: str, instrument: Instrument):
        self.name = name
        self.instrument = instrument
        self.data_units: np.ndarray = np.array([])
        self.data_columns: np.ndarray = np.array([])
        self.settings_UI: Callable[[], dict] = lambda: self.settings  # Placeholder for settings UI function

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

    def __str__(self):
        return f"Measurement(name={self.name}, instrument={self.instrument.name})"

class MeasurementItem:
    """An object to hold measurement settings."""
    def __init__(self, measurement: Measurement, settings: dict):
        self.measurement = measurement
        self.settings = settings

    def __repr__(self):
        return f"MeasurementItem(measurement={self.measurement}, settings={self.settings})"
    def __str__(self):
        return self.__repr__()
