"""
PyBirch Movement Module

This module provides base classes for movement instruments in the PyBirch
framework. Movements are instruments that can be positioned (motors, stages, etc.)
"""

import logging
import pickle
from typing import Callable, Optional

import numpy as np
import pandas as pd
from pymeasure.instruments import Instrument

logger = logging.getLogger(__name__)


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

    def __base_class__(self):
        return Movement

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

    def serialize(self) -> dict:
        return {
            "name": self.name,
            "nickname": self.nickname,
            "type": self.__base_class__().__name__,
            "pybirch_class": self.__class__.__name__,
            "adapter": getattr(self, 'adapter', ''),
            "position_units": self.position_units,
            "position_column": self.position_column,
        }

    def deserialize(self, data: dict, initialize: bool = False):
        self.name = data.get("name", self.name)
        self.nickname = data.get("nickname", self.nickname)
        self.adapter = data.get("adapter", getattr(self, 'adapter', ''))
        self.position_units = data.get("position_units", self.position_units)
        self.position_column = data.get("position_column", self.position_column)
        if "settings" in data:
            self.settings = data["settings"]

        # check connection status and, if it fails, set adapter to a placeholder.
        self.status = self.check_connection()
        if not self.status:
            self.adapter = 'placeholder'
        if initialize and self.status:
            self.initialize()


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
            logger.error(f"Failed to initialize instrument {self.name} with adapter {adapter}: {e}")
            self.status = False

class MovementItem:
    """An object to hold movement settings and positions."""
    def __init__(self, movement: Movement | VisaMovement, positions: np.ndarray = np.array([]), settings: dict = {}):
        self.instrument = movement
        self.settings = settings
        self.positions = positions

    def __repr__(self):
        return f"MovementItem(movement={self.instrument}, settings={self.settings}, positions={self.positions})"
    def __str__(self):
        return self.__repr__()
    
    def serialize(self) -> dict:
        return {
            "instrument": self.instrument.serialize(),
            "settings": self.settings
        }
    def deserialize(self, data: dict, initialize: bool = False):
        if self.instrument:
            self.instrument.deserialize(data.get("instrument", {}), initialize=initialize)
        self.settings = data.get("settings", {})
    
def empty_MovementItem() -> MovementItem:
    """Create an empty MovementItem for placeholder purposes."""
    class EmptyMovement(Movement):
        def check_connection(self) -> bool:
            return False

    empty_movement = EmptyMovement("Empty Movement")
    return MovementItem(movement=empty_movement, positions=np.array([]), settings={})
