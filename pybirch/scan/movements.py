import numpy as np
import pandas as pd
from pymeasure.instruments import Instrument
from typing import Callable, Optional
import pickle


class Movement:
    """Base class for movement tools in the PyBirch framework."""

    def __init__(self, name: str):
        self.name = name
        self.nickname = name  # Optional user-defined nickname, given in the GUI at runtime.
        self.adapter = ''
        self.status: bool = False  # Connection status
        self.position_units: str = ''
        self.position_column: str = ''
        self.settings_UI: Callable[[], dict] = lambda: self.settings  # Placeholder for settings UI function

    def check_connection(self) -> bool:
        raise NotImplementedError("Subclasses should implement this method.")

    def position_df(self) -> pd.DataFrame:
        # Return the current position as a pandas DataFrame
        column = f"{self.position_column} ({self.position_units})"
        return pd.DataFrame({column: [self.position]})

    @property
    def position(self) -> float:
        # Get the current position of the instrument
        raise NotImplementedError("Subclasses should implement this method.")

    @position.setter
    def position(self, value: float):
        # Set the position of the instrument
        raise NotImplementedError("Subclasses should implement this method.")

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
        # Initialize the movement equipment
        pass

    def shutdown(self):
        # Shutdown the movement equipment
        pass

    def dict_repr(self) -> dict:
        return {
            "name": self.name,
            "type": self.__class__.__name__,
            "adapter": getattr(self, 'adapter', ''),
            "settings": self.settings
        }
    
    def load_from_dict(self, data: dict, initialize: bool = False):
        self.name = data.get("name", self.name)
        if "settings" in data:
            self.settings = data["settings"]

class VisaMovement(Movement):
    """Adds visa capabilities to the Movement class."""

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


class MovementItem:
    """An object to hold movement settings and positions."""
    def __init__(self, movement: Movement | VisaMovement, settings: dict, positions: np.ndarray):
        self.movement = movement
        self.settings = settings
        self.positions = positions

    def __repr__(self):
        return f"MovementItem(movement={self.movement}, settings={self.settings}, positions={self.positions})"
    def __str__(self):
        return self.__repr__()