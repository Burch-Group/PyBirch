"""
Fake Multimeter instrument for testing and development.

This module demonstrates how to create both measurement and movement instruments
using the simplified PyBirch instrument architecture. The multimeter has:
- A voltage meter (measurement)
- A current source (movement)

Usage:
    # Voltage measurement
    voltage_meter = VoltageMeterMeasurement("Voltage Meter")
    voltage_meter.connect()
    data = voltage_meter.perform_measurement()
    
    # Current source movement
    current_source = CurrentSourceMovement("Current Source")
    current_source.connect()
    current_source.position = 0.001  # Set to 1 mA
"""

import numpy as np

from pybirch.Instruments.base import (
    FakeMeasurementInstrument,
    FakeMovementInstrument,
    SimulatedDelay,
)
from pybirch.scan.measurements import Measurement
from pybirch.scan.movements import Movement


class FakeMultimeter(SimulatedDelay):
    """
    A fake multimeter backend for simulating voltage and current measurements.
    
    This class represents the hardware layer - the actual instrument that can
    measure voltage and source current.
    """

    def __init__(self, name: str = "Mock Multimeter", wait: float = 0.0):
        super().__init__(wait)
        self.name = name
        self._current = 0.0
        self._voltage = 0.0

    @property
    def current(self) -> float:
        self._delay()
        return self._current
    
    @current.setter
    def current(self, value: float):
        self._delay()
        self._current = value
    
    @property
    def voltage(self) -> float:
        self._delay()
        return self._voltage
    
    @voltage.setter
    def voltage(self, value: float):
        self._delay()
        self._voltage = value


class VoltageMeterMeasurement(FakeMeasurementInstrument):
    """
    Voltage measurement from the fake multimeter.
    
    This demonstrates a measurement instrument that reads from a shared
    instrument backend (FakeMultimeter).
    """

    def __init__(self, name: str = "Voltage Meter"):
        super().__init__(name)
        self.instrument = FakeMultimeter()
        
        # Define data columns and units
        self.data_columns = np.array(["current", "voltage"])
        self.data_units = np.array(["A", "V"])
        
        # Define settings
        self._define_settings({
            "num_data_points": 10,
        })
    
    def _perform_measurement_impl(self) -> np.ndarray:
        """Measure current and voltage from the multimeter."""
        self._delay()
        n = self._num_data_points
        
        currents = np.full(n, self.instrument.current)
        voltages = self.instrument.voltage + np.random.normal(0, 0.01, n)
        
        return np.column_stack([currents, voltages])
    
    def _initialize_impl(self):
        """Reset multimeter to zero."""
        self._delay()
        self.instrument.current = 0.0
        self.instrument.voltage = 0.0


class CurrentSourceMovement(FakeMovementInstrument):
    """
    Current source control from the fake multimeter.
    
    This demonstrates a movement instrument that controls the current
    output of the multimeter.
    """

    def __init__(self, name: str = "Current Source"):
        super().__init__(name)
        self.instrument = FakeMultimeter()
        
        # Define position properties
        self.position_units = "A"
        self.position_column = "current"
        
        # No additional settings needed beyond position
        self._define_settings({})
    
    @property
    def position(self) -> float:
        self._delay()
        return self.instrument.current
    
    @position.setter
    def position(self, value: float):
        self._delay()
        self.instrument.current = value
    
    def _initialize_impl(self):
        """Reset current to zero."""
        self._delay()
        self.instrument.current = 0.0


# Legacy-style wrapper classes for backwards compatibility
class VoltageMeterMeasurementLegacy(Measurement):
    """Legacy wrapper for VoltageMeterMeasurement."""

    def __init__(self, name: str = "Voltage Meter"):
        super().__init__(name)
        self._impl = VoltageMeterMeasurement(name)
        self.data_columns = self._impl.data_columns
        self.data_units = self._impl.data_units

    def check_connection(self) -> bool:
        return self._impl.check_connection()

    def perform_measurement(self) -> np.ndarray:
        return self._impl.perform_measurement()
    
    def connect(self):
        self._impl.connect()
        self.status = self._impl.status

    def initialize(self):
        self._impl.initialize()

    def shutdown(self):
        self._impl.shutdown()

    @property
    def settings(self) -> dict:
        return self._impl.settings
    
    @settings.setter
    def settings(self, settings: dict):
        self._impl.settings = settings


class CurrentSourceMovementLegacy(Movement):
    """Legacy wrapper for CurrentSourceMovement."""

    def __init__(self, name: str = "Current Source"):
        super().__init__(name)
        self._impl = CurrentSourceMovement(name)
        self.position_units = self._impl.position_units
        self.position_column = self._impl.position_column

    def check_connection(self) -> bool:
        return self._impl.check_connection()

    @property
    def position(self) -> float:
        return self._impl.position
    
    @position.setter
    def position(self, value: float):
        self._impl.position = value
    
    def connect(self):
        self._impl.connect()
        self.status = self._impl.status

    def initialize(self):
        self._impl.initialize()

    def shutdown(self):
        self._impl.shutdown()

    @property
    def settings(self) -> dict:
        return self._impl.settings
    
    @settings.setter
    def settings(self, settings: dict):
        self._impl.settings = settings




