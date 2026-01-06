"""
Base classes for PyBirch instruments.

This module provides abstract base classes that simplify creating new instruments
for both VISA and non-VISA backends. The architecture supports:

- Measurement instruments (sensors, detectors, etc.)
- Movement instruments (stages, motors, etc.)
- Both VISA-based and simulated/custom backends

ARCHITECTURE OVERVIEW
---------------------
The base classes provide a template pattern where:
- Common interface methods (connect, initialize, shutdown, settings) are defined
- Subclasses override specific `_impl` methods with proprietary instrument commands
- Settings management can be automatic OR fully custom

CUSTOMIZATION HOOKS
-------------------
For each instrument, you can override these methods with your proprietary commands:

    _connect_impl()      -> Your instrument's connection/handshake protocol
    _initialize_impl()   -> Your instrument's initialization sequence  
    _shutdown_impl()     -> Your instrument's cleanup/safe-state commands
    
For settings, you have two options:

    Option A - Automatic settings (simple instruments):
        Call self._define_settings({...}) in __init__ and settings are handled automatically
        
    Option B - Custom settings (complex instruments):
        Override the settings property getter/setter with your own logic

EXAMPLE: Simple fake instrument with automatic settings
-------------------------------------------------------
    class MyFakeInstrument(FakeMeasurementInstrument):
        def __init__(self, name="My Instrument"):
            super().__init__(name)
            self.data_columns = np.array(["value"])
            self.data_units = np.array(["V"])
            self._define_settings({"gain": 1.0, "filter": True})
        
        def _perform_measurement_impl(self):
            return np.array([[self._gain * np.random.random()]])

EXAMPLE: Real VISA instrument with proprietary commands
-------------------------------------------------------
    class MyLockin(VisaBaseMeasurementInstrument):
        def __init__(self, name="SR830", adapter="GPIB::8"):
            super().__init__(name, adapter)
            self.data_columns = np.array(["X", "Y"])
            self.data_units = np.array(["V", "V"])
        
        def _connect_impl(self) -> bool:
            # Proprietary connection handshake
            try:
                self.instrument.write("*RST")
                idn = self.instrument.query("*IDN?")
                return "SR830" in idn
            except:
                return False
        
        def _initialize_impl(self):
            # Proprietary initialization sequence
            self.instrument.write("SENS 22")      # Set sensitivity
            self.instrument.write("OFLT 10")      # Set time constant
            self.instrument.write("ISRC 0")       # Set input source
        
        def _shutdown_impl(self):
            # Proprietary shutdown commands
            self.instrument.write("LOCL 0")       # Return to local control
        
        @property
        def settings(self) -> dict:
            # Custom settings getter - query instrument directly
            return {
                "sensitivity": int(self.instrument.query("SENS?")),
                "time_constant": int(self.instrument.query("OFLT?")),
                "input_source": int(self.instrument.query("ISRC?")),
            }
        
        @settings.setter
        def settings(self, settings: dict):
            # Custom settings setter - send proprietary commands
            if "sensitivity" in settings:
                self.instrument.write(f"SENS {settings['sensitivity']}")
            if "time_constant" in settings:
                self.instrument.write(f"OFLT {settings['time_constant']}")
            if "input_source" in settings:
                self.instrument.write(f"ISRC {settings['input_source']}")
        
        def _perform_measurement_impl(self):
            x = float(self.instrument.query("OUTP? 1"))
            y = float(self.instrument.query("OUTP? 2"))
            return np.array([[x, y]])
"""

import numpy as np
import pandas as pd
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Type, Union
import time


class InstrumentSettingsMixin:
    """
    Mixin providing automatic settings management for instruments.
    
    This is OPTIONAL - if you need custom settings logic for proprietary
    instrument commands, override the settings property/setter directly
    in your subclass instead of using _define_settings().
    
    Usage for simple instruments:
        def __init__(self):
            self._define_settings({
                "gain": 1.0,
                "averages": 10,
            })
        
        # Now self.settings automatically gets/sets self._gain, self._averages
    
    Usage for complex instruments:
        # Don't call _define_settings(), instead override settings directly:
        @property
        def settings(self) -> dict:
            return {"gain": self.instrument.query("GAIN?")}
        
        @settings.setter  
        def settings(self, settings: dict):
            if "gain" in settings:
                self.instrument.write(f"GAIN {settings['gain']}")
    """
    
    def __init__(self):
        self._settings_keys: List[str] = []
        self._settings_defaults: Dict[str, Any] = {}
        self._use_auto_settings = False
    
    def _define_settings(self, settings_dict: Dict[str, Any]):
        """
        Define settings for automatic management (optional).
        
        Call this in __init__ if you want automatic settings handling.
        Don't call this if you're overriding the settings property/setter.
        
        Args:
            settings_dict: Dictionary mapping setting names to default values.
                          Each setting will be stored as self._<name>.
        """
        self._settings_keys = list(settings_dict.keys())
        self._settings_defaults = settings_dict.copy()
        self._use_auto_settings = True
        
        for key, default_value in settings_dict.items():
            setattr(self, f"_{key}", default_value)
    
    def _get_auto_settings(self) -> Dict[str, Any]:
        """Get settings when using automatic settings management."""
        if not self._use_auto_settings:
            return {}
        return {key: getattr(self, f"_{key}", self._settings_defaults.get(key)) 
                for key in self._settings_keys}
    
    def _set_auto_settings(self, settings: Dict[str, Any]):
        """Set settings when using automatic settings management."""
        if not self._use_auto_settings:
            return
        for key, value in settings.items():
            if key in self._settings_keys:
                setattr(self, f"_{key}", value)
    
    def _reset_settings_to_defaults(self):
        """Reset all settings to their default values."""
        for key, default_value in self._settings_defaults.items():
            setattr(self, f"_{key}", default_value)


class BaseMeasurementInstrument(InstrumentSettingsMixin, ABC):
    """
    Abstract base class for non-VISA measurement instruments.
    
    REQUIRED to implement:
        - _perform_measurement_impl() -> np.ndarray
    
    OPTIONAL to override (for proprietary instrument commands):
        - _connect_impl() -> bool
        - _initialize_impl()
        - _shutdown_impl()
        - settings property (if not using _define_settings())
    
    In __init__, you should set:
        - self.data_columns: np.ndarray of column names
        - self.data_units: np.ndarray of units for each column
        - Either call self._define_settings({...}) OR override settings property
    """
    
    def __init__(self, name: str):
        InstrumentSettingsMixin.__init__(self)
        self.name = name
        self.nickname = name
        self.adapter = ''
        self.status: bool = False
        self.data_units: np.ndarray = np.array([])
        self.data_columns: np.ndarray = np.array([])
        self.settings_UI: Callable[[], dict] = lambda: self.settings
    
    def __base_class__(self):
        from pybirch.scan.measurements import Measurement
        return Measurement
    
    # -------------------------------------------------------------------------
    # OVERRIDE THESE METHODS with your proprietary instrument commands
    # -------------------------------------------------------------------------
    
    @abstractmethod
    def _perform_measurement_impl(self) -> np.ndarray:
        """
        REQUIRED: Implement your measurement logic here.
        
        Returns:
            2D numpy array where each row is a data point and each column
            corresponds to self.data_columns.
        """
        pass
    
    def _connect_impl(self) -> bool:
        """
        OPTIONAL: Override with your instrument's connection protocol.
        
        Example for a real instrument:
            def _connect_impl(self) -> bool:
                try:
                    self.instrument.write("*RST")
                    response = self.instrument.query("*IDN?")
                    return "ExpectedModel" in response
                except Exception:
                    return False
        
        Returns:
            True if connection successful, False otherwise.
        """
        return True
    
    def _initialize_impl(self):
        """
        OPTIONAL: Override with your instrument's initialization sequence.
        
        Example for a real instrument:
            def _initialize_impl(self):
                self.instrument.write("INIT")
                self.instrument.write("SENS 1E-6")
                self.instrument.write("OFLT 10")
        """
        if self._use_auto_settings:
            self._reset_settings_to_defaults()
    
    def _shutdown_impl(self):
        """
        OPTIONAL: Override with your instrument's shutdown sequence.
        
        Example for a real instrument:
            def _shutdown_impl(self):
                self.instrument.write("OUTP OFF")
                self.instrument.write("LOCL 0")  # Return to local
        """
        pass
    
    # -------------------------------------------------------------------------
    # Public interface - these call your _impl methods
    # -------------------------------------------------------------------------
    
    def connect(self):
        """Connect to the instrument. Calls _connect_impl()."""
        self.status = self._connect_impl()
        return self.status
    
    def check_connection(self) -> bool:
        """Check if the instrument is connected."""
        return self.status
    
    def initialize(self):
        """Initialize the instrument. Calls _initialize_impl()."""
        self._initialize_impl()
    
    def shutdown(self):
        """Shutdown the instrument. Calls _shutdown_impl()."""
        self._shutdown_impl()
        self.status = False
    
    def perform_measurement(self) -> np.ndarray:
        """Perform a measurement. Calls _perform_measurement_impl()."""
        return self._perform_measurement_impl()
    
    def measurement_df(self) -> pd.DataFrame:
        """Convert the raw measurement data to a pandas DataFrame."""
        columns = self.columns()
        return pd.DataFrame(self.perform_measurement(), columns=columns)
    
    def columns(self) -> np.ndarray:
        """Return column names with units appended."""
        return np.array([f"{col} ({unit})" for col, unit in zip(self.data_columns, self.data_units)])
    
    @property
    def settings(self) -> dict:
        """
        Get current instrument settings.
        
        Override this if you need custom logic (e.g., querying instrument directly).
        Default implementation uses automatic settings from _define_settings().
        """
        return self._get_auto_settings()
    
    @settings.setter
    def settings(self, settings: dict):
        """
        Set instrument settings from a dictionary.
        
        Override this if you need custom logic (e.g., sending proprietary commands).
        Default implementation uses automatic settings from _define_settings().
        """
        self._set_auto_settings(settings)
    
    def serialize(self) -> dict:
        """Serialize instrument state for saving."""
        return {
            "name": self.name,
            "nickname": self.nickname,
            "type": self.__base_class__().__name__,
            "pybirch_class": self.__class__.__name__,
            "adapter": getattr(self, 'adapter', ''),
            "data_units": self.data_units.tolist() if isinstance(self.data_units, np.ndarray) else self.data_units,
            "data_columns": self.data_columns.tolist() if isinstance(self.data_columns, np.ndarray) else self.data_columns,
            "settings": self.settings,
        }
    
    def deserialize(self, data: dict, initialize: bool = False):
        """Deserialize instrument state from saved data."""
        self.name = data.get("name", self.name)
        self.nickname = data.get("nickname", self.nickname)
        self.adapter = data.get("adapter", getattr(self, 'adapter', ''))
        if "data_units" in data:
            self.data_units = np.array(data["data_units"])
        if "data_columns" in data:
            self.data_columns = np.array(data["data_columns"])
        if "settings" in data:
            self.settings = data["settings"]
        
        self.status = self.check_connection()
        if not self.status:
            self.adapter = 'placeholder'
        if initialize and self.status:
            self.initialize()


class BaseMovementInstrument(InstrumentSettingsMixin, ABC):
    """
    Abstract base class for non-VISA movement instruments.
    
    REQUIRED to implement:
        - position property (getter and setter)
    
    OPTIONAL to override (for proprietary instrument commands):
        - _connect_impl() -> bool
        - _initialize_impl()
        - _shutdown_impl()
        - settings property (if not using _define_settings())
    
    In __init__, you should set:
        - self.position_units: str
        - self.position_column: str
        - Either call self._define_settings({...}) OR override settings property
    """
    
    def __init__(self, name: str):
        InstrumentSettingsMixin.__init__(self)
        self.name = name
        self.nickname = name
        self.adapter = ''
        self.status: bool = False
        self.position_units: str = ''
        self.position_column: str = ''
        self.settings_UI: Callable[[], dict] = lambda: self.settings
    
    def __base_class__(self):
        from pybirch.scan.movements import Movement
        return Movement
    
    # -------------------------------------------------------------------------
    # OVERRIDE THESE with your proprietary instrument commands
    # -------------------------------------------------------------------------
    
    @property
    @abstractmethod
    def position(self) -> float:
        """
        REQUIRED: Get the current position.
        
        Example for a real instrument:
            @property
            def position(self) -> float:
                return float(self.instrument.query("POS?"))
        """
        pass
    
    @position.setter
    @abstractmethod
    def position(self, value: float):
        """
        REQUIRED: Set the position.
        
        Example for a real instrument:
            @position.setter
            def position(self, value: float):
                self.instrument.write(f"MOVE {value}")
                while self.instrument.query("MOVING?") == "1":
                    time.sleep(0.01)
        """
        pass
    
    def _connect_impl(self) -> bool:
        """
        OPTIONAL: Override with your instrument's connection protocol.
        
        Returns:
            True if connection successful, False otherwise.
        """
        return True
    
    def _initialize_impl(self):
        """
        OPTIONAL: Override with your instrument's initialization/homing sequence.
        
        Example for a real instrument:
            def _initialize_impl(self):
                self.instrument.write("HOME")
                while self.instrument.query("HOMING?") == "1":
                    time.sleep(0.1)
        """
        pass
    
    def _shutdown_impl(self):
        """
        OPTIONAL: Override with your instrument's shutdown sequence.
        """
        pass
    
    # -------------------------------------------------------------------------
    # Public interface
    # -------------------------------------------------------------------------
    
    def connect(self):
        """Connect to the instrument. Calls _connect_impl()."""
        self.status = self._connect_impl()
        return self.status
    
    def check_connection(self) -> bool:
        """Check if the instrument is connected."""
        return self.status
    
    def initialize(self):
        """Initialize the instrument. Calls _initialize_impl()."""
        self._initialize_impl()
    
    def shutdown(self):
        """Shutdown the instrument. Calls _shutdown_impl()."""
        self._shutdown_impl()
        self.status = False
    
    def position_df(self) -> pd.DataFrame:
        """Return the current position as a pandas DataFrame."""
        column = f"{self.position_column} ({self.position_units})"
        return pd.DataFrame({column: [self.position]})
    
    @property
    def settings(self) -> dict:
        """
        Get current instrument settings.
        
        Override this if you need custom logic (e.g., querying instrument directly).
        Default implementation uses automatic settings from _define_settings().
        """
        return self._get_auto_settings()
    
    @settings.setter
    def settings(self, settings: dict):
        """
        Set instrument settings from a dictionary.
        
        Override this if you need custom logic (e.g., sending proprietary commands).
        Default implementation uses automatic settings from _define_settings().
        """
        self._set_auto_settings(settings)
    
    def serialize(self) -> dict:
        """Serialize instrument state for saving."""
        return {
            "name": self.name,
            "nickname": self.nickname,
            "type": self.__base_class__().__name__,
            "pybirch_class": self.__class__.__name__,
            "adapter": getattr(self, 'adapter', ''),
            "position_units": self.position_units,
            "position_column": self.position_column,
            "settings": self.settings,
        }
    
    def deserialize(self, data: dict, initialize: bool = False):
        """Deserialize instrument state from saved data."""
        self.name = data.get("name", self.name)
        self.nickname = data.get("nickname", self.nickname)
        self.adapter = data.get("adapter", getattr(self, 'adapter', ''))
        self.position_units = data.get("position_units", self.position_units)
        self.position_column = data.get("position_column", self.position_column)
        if "settings" in data:
            self.settings = data["settings"]
        
        self.status = self.check_connection()
        if not self.status:
            self.adapter = 'placeholder'
        if initialize and self.status:
            self.initialize()


class VisaBaseMeasurementInstrument(BaseMeasurementInstrument):
    """
    Base class for VISA-based measurement instruments.
    
    This class handles VISA adapter management. Your subclass should:
    - Override _connect_impl() with your handshake/identification protocol
    - Override _initialize_impl() with your initialization commands
    - Override _shutdown_impl() with your cleanup commands
    - Override settings property/setter with your proprietary get/set commands
    - Implement _perform_measurement_impl() with your measurement commands
    
    The VISA instrument is available as self.instrument after connection.
    
    Example:
        class MySR830(VisaBaseMeasurementInstrument):
            def __init__(self, name="SR830", adapter="GPIB::8"):
                super().__init__(name, adapter)
                self.data_columns = np.array(["X", "Y", "R"])
                self.data_units = np.array(["V", "V", "V"])
            
            def _connect_impl(self) -> bool:
                try:
                    self.instrument.write("*CLS")
                    idn = self.instrument.query("*IDN?")
                    return "SR830" in idn
                except:
                    return False
            
            def _initialize_impl(self):
                self.instrument.write("REST")  # Reset to defaults
            
            @property
            def settings(self) -> dict:
                return {
                    "sensitivity": int(self.instrument.query("SENS?")),
                    "time_constant": int(self.instrument.query("OFLT?")),
                }
            
            @settings.setter
            def settings(self, settings: dict):
                if "sensitivity" in settings:
                    self.instrument.write(f"SENS {settings['sensitivity']}")
                if "time_constant" in settings:
                    self.instrument.write(f"OFLT {settings['time_constant']}")
            
            def _perform_measurement_impl(self):
                data = self.instrument.query("SNAP? 1,2,3")  # X, Y, R
                x, y, r = map(float, data.split(","))
                return np.array([[x, y, r]])
    """
    
    def __init__(self, name: str, adapter: str = '', instrument_class: Optional[Type] = None):
        super().__init__(name)
        self.adapter = adapter
        self.instrument_class = instrument_class
        self.instrument = None
        
        if adapter:
            self._create_instrument(adapter)
    
    def _create_instrument(self, adapter: str):
        """
        Create the instrument instance. Override if you need custom instantiation.
        
        By default, this creates an instance of instrument_class with the adapter.
        If no instrument_class is provided, it creates a raw pyvisa resource.
        """
        self.adapter = adapter
        try:
            if self.instrument_class:
                self.instrument = self.instrument_class(adapter)
            else:
                # Create raw pyvisa resource for direct SCPI control
                import pyvisa
                rm = pyvisa.ResourceManager()
                self.instrument = rm.open_resource(adapter)
        except Exception as e:
            print(f"Failed to create instrument {self.name} with adapter {adapter}: {e}")
            self.instrument = None
    
    def _connect_impl(self) -> bool:
        """
        Override this with your instrument's identification/handshake protocol.
        
        Default implementation just checks if instrument exists.
        """
        return self.instrument is not None


class VisaBaseMovementInstrument(BaseMovementInstrument):
    """
    Base class for VISA-based movement instruments.
    
    Same pattern as VisaBaseMeasurementInstrument - override the _impl methods
    and settings property/setter with your proprietary commands.
    
    Example:
        class MyESP301Axis(VisaBaseMovementInstrument):
            def __init__(self, name="ESP301 X", adapter="GPIB::1", axis=1):
                super().__init__(name, adapter)
                self.axis = axis
                self.position_units = "mm"
                self.position_column = f"axis{axis} position"
            
            def _connect_impl(self) -> bool:
                try:
                    idn = self.instrument.query("*IDN?")
                    return "ESP301" in idn
                except:
                    return False
            
            def _initialize_impl(self):
                self.instrument.write(f"{self.axis}OR")  # Home axis
            
            @property
            def position(self) -> float:
                return float(self.instrument.query(f"{self.axis}TP"))
            
            @position.setter
            def position(self, value: float):
                self.instrument.write(f"{self.axis}PA{value}")  # Move absolute
                self.instrument.query(f"{self.axis}WS")  # Wait for stop
            
            @property
            def settings(self) -> dict:
                return {
                    "velocity": float(self.instrument.query(f"{self.axis}VA?")),
                    "acceleration": float(self.instrument.query(f"{self.axis}AC?")),
                }
            
            @settings.setter
            def settings(self, settings: dict):
                if "velocity" in settings:
                    self.instrument.write(f"{self.axis}VA{settings['velocity']}")
                if "acceleration" in settings:
                    self.instrument.write(f"{self.axis}AC{settings['acceleration']}")
    """
    
    def __init__(self, name: str, adapter: str = '', instrument_class: Optional[Type] = None):
        super().__init__(name)
        self.adapter = adapter
        self.instrument_class = instrument_class
        self.instrument = None
        
        if adapter:
            self._create_instrument(adapter)
    
    def _create_instrument(self, adapter: str):
        """Create the instrument instance."""
        self.adapter = adapter
        try:
            if self.instrument_class:
                self.instrument = self.instrument_class(adapter)
            else:
                import pyvisa
                rm = pyvisa.ResourceManager()
                self.instrument = rm.open_resource(adapter)
        except Exception as e:
            print(f"Failed to create instrument {self.name} with adapter {adapter}: {e}")
            self.instrument = None
    
    def _connect_impl(self) -> bool:
        """Override with your instrument's identification protocol."""
        return self.instrument is not None


# -------------------------------------------------------------------------
# Helper classes for simulated/fake instruments
# -------------------------------------------------------------------------

class SimulatedDelay:
    """
    Mixin to add simulated communication delays to fake instruments.
    
    Usage:
        class MyFakeInstrument(SimulatedDelay, BaseMeasurementInstrument):
            def __init__(self, name, wait=0.01):
                SimulatedDelay.__init__(self, wait)
                BaseMeasurementInstrument.__init__(self, name)
    """
    
    def __init__(self, wait: float = 0.0):
        self._wait = wait
    
    def _delay(self):
        """Apply the simulated delay."""
        if self._wait > 0:
            time.sleep(self._wait)


class FakeMeasurementInstrument(SimulatedDelay, BaseMeasurementInstrument):
    """
    Convenience base class for fake/simulated measurement instruments.
    
    Use this for testing and development. Fake instruments are always
    "connected" and can use the automatic settings management.
    """
    
    def __init__(self, name: str, wait: float = 0.0):
        SimulatedDelay.__init__(self, wait)
        BaseMeasurementInstrument.__init__(self, name)
        self.status = True  # Fake instruments are always "connected"
    
    def _connect_impl(self) -> bool:
        self._delay()
        return True
    
    def check_connection(self) -> bool:
        return True


class FakeMovementInstrument(SimulatedDelay, BaseMovementInstrument):
    """
    Convenience base class for fake/simulated movement instruments.
    
    Use this for testing and development. Fake instruments are always
    "connected" and can use the automatic settings management.
    """
    
    def __init__(self, name: str, wait: float = 0.0):
        SimulatedDelay.__init__(self, wait)
        BaseMovementInstrument.__init__(self, name)
        self.status = True  # Fake instruments are always "connected"
    
    def _connect_impl(self) -> bool:
        self._delay()
        return True
    
    def check_connection(self) -> bool:
        return True


# -------------------------------------------------------------------------
# Legacy compatibility
# -------------------------------------------------------------------------

def get_legacy_measurement_class():
    """Get the legacy Measurement class for backwards compatibility."""
    from pybirch.scan.measurements import Measurement
    return Measurement

def get_legacy_movement_class():
    """Get the legacy Movement class for backwards compatibility."""
    from pybirch.scan.movements import Movement
    return Movement
