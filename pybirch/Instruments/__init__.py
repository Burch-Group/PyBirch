"""
PyBirch Instruments Package

This package provides base classes and utilities for creating instrument
drivers for the PyBirch measurement framework.

Base Classes:
-------------
- BaseMeasurementInstrument: For non-VISA measurement instruments
- BaseMovementInstrument: For non-VISA movement instruments  
- VisaBaseMeasurementInstrument: For VISA-based measurement instruments
- VisaBaseMovementInstrument: For VISA-based movement instruments
- FakeMeasurementInstrument: For simulated measurement instruments
- FakeMovementInstrument: For simulated movement instruments

Mixins:
-------
- InstrumentSettingsMixin: Automatic settings management
- SimulatedDelay: Add communication delays to fake instruments

Quick Start:
------------
To create a new measurement instrument:

    from pybirch.Instruments.base import FakeMeasurementInstrument
    
    class MyInstrument(FakeMeasurementInstrument):
        def __init__(self, name="My Instrument"):
            super().__init__(name)
            self.data_columns = np.array(["value"])
            self.data_units = np.array(["V"])
            self._define_settings({"gain": 1.0})
        
        def _perform_measurement_impl(self):
            return np.array([[self._gain * np.random.random()]])

To create a new movement instrument:

    from pybirch.Instruments.base import FakeMovementInstrument
    
    class MyStage(FakeMovementInstrument):
        def __init__(self, name="My Stage"):
            super().__init__(name)
            self.position_units = "mm"
            self.position_column = "position"
            self._position = 0.0
        
        @property
        def position(self):
            return self._position
        
        @position.setter
        def position(self, value):
            self._position = value

See pybirch/setups/fake_setup/ for complete examples.
"""

from pybirch.Instruments.base import (
    # Base classes
    BaseMeasurementInstrument,
    BaseMovementInstrument,
    VisaBaseMeasurementInstrument,
    VisaBaseMovementInstrument,
    
    # Fake instrument helpers
    FakeMeasurementInstrument,
    FakeMovementInstrument,
    
    # Mixins
    InstrumentSettingsMixin,
    SimulatedDelay,
    
    # Legacy compatibility
    get_legacy_measurement_class,
    get_legacy_movement_class,
)

__all__ = [
    # Base classes
    "BaseMeasurementInstrument",
    "BaseMovementInstrument",
    "VisaBaseMeasurementInstrument", 
    "VisaBaseMovementInstrument",
    
    # Fake instrument helpers
    "FakeMeasurementInstrument",
    "FakeMovementInstrument",
    
    # Mixins
    "InstrumentSettingsMixin",
    "SimulatedDelay",
    
    # Legacy compatibility
    "get_legacy_measurement_class",
    "get_legacy_movement_class",
]
