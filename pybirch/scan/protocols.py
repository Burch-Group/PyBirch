"""
Protocol definitions for PyBirch scan system instruments.

This module defines type protocols for Movement and Measurement instruments,
providing a more Pythonic way to check instrument types than the legacy
__base_class__() method.

Usage:
    from pybirch.scan.protocols import MovementProtocol, MeasurementProtocol
    
    if isinstance(instrument, MovementProtocol):
        instrument.position = 50.0
    elif isinstance(instrument, MeasurementProtocol):
        df = instrument.measurement_df()
"""

from typing import Protocol, runtime_checkable, Callable, Any
import numpy as np
import pandas as pd


@runtime_checkable
class InstrumentProtocol(Protocol):
    """Base protocol for all PyBirch instruments."""
    
    name: str
    nickname: str
    adapter: str
    status: bool
    
    def check_connection(self) -> bool:
        """Check if the instrument is connected."""
        ...
    
    def connect(self) -> None:
        """Connect to the instrument."""
        ...
    
    def initialize(self) -> None:
        """Initialize the instrument to default state."""
        ...
    
    def shutdown(self) -> None:
        """Shutdown the instrument."""
        ...
    
    @property
    def settings(self) -> dict:
        """Get current instrument settings."""
        ...
    
    @settings.setter
    def settings(self, settings: dict) -> None:
        """Set instrument settings."""
        ...
    
    def serialize(self) -> dict:
        """Serialize instrument state to a dictionary."""
        ...
    
    def deserialize(self, data: dict, initialize: bool = False) -> None:
        """Restore instrument state from a dictionary."""
        ...


@runtime_checkable
class MovementProtocol(Protocol):
    """Protocol for movement instruments (stages, current sources, etc.)."""
    
    name: str
    nickname: str
    adapter: str
    status: bool
    position_units: str
    position_column: str
    
    @property
    def position(self) -> float:
        """Get current position."""
        ...
    
    @position.setter
    def position(self, value: float) -> None:
        """Set position (move to target)."""
        ...
    
    def check_connection(self) -> bool:
        """Check if the instrument is connected."""
        ...
    
    def connect(self) -> None:
        """Connect to the instrument."""
        ...
    
    def initialize(self) -> None:
        """Initialize the instrument to default state."""
        ...
    
    def shutdown(self) -> None:
        """Shutdown the instrument."""
        ...
    
    @property
    def settings(self) -> dict:
        """Get current instrument settings."""
        ...
    
    @settings.setter
    def settings(self, settings: dict) -> None:
        """Set instrument settings."""
        ...
    
    def position_df(self) -> pd.DataFrame:
        """Return the current position as a DataFrame."""
        ...
    
    def serialize(self) -> dict:
        """Serialize instrument state to a dictionary."""
        ...


@runtime_checkable
class MeasurementProtocol(Protocol):
    """Protocol for measurement instruments (lock-ins, multimeters, etc.)."""
    
    name: str
    nickname: str
    adapter: str
    status: bool
    data_units: np.ndarray
    data_columns: np.ndarray
    
    def check_connection(self) -> bool:
        """Check if the instrument is connected."""
        ...
    
    def connect(self) -> None:
        """Connect to the instrument."""
        ...
    
    def initialize(self) -> None:
        """Initialize the instrument to default state."""
        ...
    
    def shutdown(self) -> None:
        """Shutdown the instrument."""
        ...
    
    @property
    def settings(self) -> dict:
        """Get current instrument settings."""
        ...
    
    @settings.setter
    def settings(self, settings: dict) -> None:
        """Set instrument settings."""
        ...
    
    def perform_measurement(self) -> np.ndarray:
        """Perform a measurement and return raw data."""
        ...
    
    def measurement_df(self) -> pd.DataFrame:
        """Perform a measurement and return as DataFrame."""
        ...
    
    def columns(self) -> np.ndarray:
        """Return column names with units."""
        ...
    
    def serialize(self) -> dict:
        """Serialize instrument state to a dictionary."""
        ...


def is_movement(instrument: Any) -> bool:
    """
    Check if an instrument is a Movement type.
    
    This function provides compatibility with the legacy __base_class__() method
    while using modern Protocol checking.
    
    Args:
        instrument: The instrument to check.
        
    Returns:
        True if the instrument is a Movement type.
    """
    # First try Protocol check
    if isinstance(instrument, MovementProtocol):
        return True
    
    # Fall back to legacy check for backward compatibility
    if hasattr(instrument, '__base_class__'):
        from pybirch.scan.movements import Movement
        return instrument.__base_class__() is Movement
    
    return False


def is_measurement(instrument: Any) -> bool:
    """
    Check if an instrument is a Measurement type.
    
    This function provides compatibility with the legacy __base_class__() method
    while using modern Protocol checking.
    
    Args:
        instrument: The instrument to check.
        
    Returns:
        True if the instrument is a Measurement type.
    """
    # First try Protocol check
    if isinstance(instrument, MeasurementProtocol):
        return True
    
    # Fall back to legacy check for backward compatibility
    if hasattr(instrument, '__base_class__'):
        from pybirch.scan.measurements import Measurement
        return instrument.__base_class__() is Measurement
    
    return False


def get_instrument_type(instrument: Any) -> str:
    """
    Get the type of an instrument as a string.
    
    Args:
        instrument: The instrument to check.
        
    Returns:
        'Movement', 'Measurement', or 'Unknown'.
    """
    if is_movement(instrument):
        return 'Movement'
    elif is_measurement(instrument):
        return 'Measurement'
    return 'Unknown'
