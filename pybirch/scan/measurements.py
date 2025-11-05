import numpy as np
import pandas as pd
from pymeasure.instruments import Instrument
from typing import Callable, Optional
from pymeasure.instruments.keithley import Keithley2400

class Measurement:
    """Base class for measurement tools in the PyBirch framework."""

    def __init__(self, name: str):
        self.name = name
        self.nickname = name  # Optional user-defined nickname, given in the GUI at runtime.
        self.adapter = ''
        self.status: bool = False  # Connection status
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

    def serialize(self) -> dict:
        return {
            "name": self.name,
            "nickname": self.nickname,
            "type": self.__class__.__name__,
            "adapter": getattr(self, 'adapter', ''),
            "data_units": self.data_units,
            "data_columns": self.data_columns,
        }

    def deserialize(self, data: dict, initialize: bool = False):
        self.name = data.get("name", self.name)
        self.nickname = data.get("nickname", self.nickname)
        self.adapter = data.get("adapter", getattr(self, 'adapter', ''))
        self.data_units = data.get("data_units", self.data_units)
        self.data_columns = data.get("data_columns", self.data_columns)
        if "settings" in data:
            self.settings = data["settings"]

        # check connection status and, if it fails, set adapter to a placeholder.
        self.status = self.check_connection()
        if not self.status:
            self.adapter = 'placeholder'
        if initialize and self.status:
            self.initialize()

class VisaMeasurement(Measurement):
    """Adds visa capabilities to the Measurement class."""

    def __init__(self, name: str, instrument: type, adapter: str = ''):
        super().__init__(name)
        self.instrument_type = instrument
        self.initialize_instrument(adapter)
    
    def initialize_instrument(self, adapter: str):
        self.instrument = self.instrument_type(adapter) if adapter else self.instrument_type()
        self.adapter = adapter

        try:
            self.status = self.check_connection()
        except Exception as e:
            print(f"Failed to initialize instrument {self.name} with adapter {adapter}: {e}")
            self.status = False


class MeasurementItem:
    """An object to hold measurement settings."""
    def __init__(self, measurement: Measurement | VisaMeasurement, settings: dict):
        self.measurement = measurement
        self.settings = settings

    def __repr__(self):
        return f"MeasurementItem(measurement={self.measurement}, settings={self.settings})"
    def __str__(self):
        return self.__repr__()