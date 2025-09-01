import numpy as np
import pandas as pd
from pymeasure.instruments import Instrument
from typing import Callable

class Movement:
    """Base class for movement tools in the PyBirch framework."""

    def __init__(self, name: str, instrument: Instrument):
        self.name = name
        self.instrument = instrument
        self.position_units: str = ''
        self.position_column: str = ''
        self.settings_UI: Callable[[], dict] = lambda: self.settings  # Placeholder for settings UI function

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

    def __str__(self):
        return f"Movement(name={self.name}, instrument={self.instrument.name})"


class MovementItem:
    """An object to hold movement settings and positions."""
    def __init__(self, movement: Movement, settings: dict, positions: np.ndarray):
        self.movement = movement
        self.settings = settings
        self.positions = positions

    def __repr__(self):
        return f"MovementItem(movement={self.movement}, settings={self.settings}, positions={self.positions})"
    def __str__(self):
        return self.__repr__()