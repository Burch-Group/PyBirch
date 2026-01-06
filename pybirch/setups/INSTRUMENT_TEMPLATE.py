"""
Template for creating a real VISA instrument.

This file provides a template showing how to create instrument classes
for real hardware using the PyBirch base classes. Copy this file and
modify for your specific instrument.

The key pattern is:
1. Override _connect_impl() with your handshake/identification
2. Override _initialize_impl() with your initialization sequence
3. Override _shutdown_impl() with your cleanup commands
4. Override settings property/setter with your get/set commands
5. Implement _perform_measurement_impl() with your measurement logic
"""

import numpy as np
import time

from pybirch.Instruments.base import (
    VisaBaseMeasurementInstrument,
    VisaBaseMovementInstrument,
)
from pybirch.scan.measurements import Measurement
from pybirch.scan.movements import Movement


# =============================================================================
# EXAMPLE 1: Real Measurement Instrument (e.g., Lock-In Amplifier)
# =============================================================================

class RealLockInAmplifier(VisaBaseMeasurementInstrument):
    """
    Template for a real lock-in amplifier.
    
    Replace the SCPI commands with your instrument's actual commands.
    """
    
    def __init__(self, name: str = "Lock-In", adapter: str = "GPIB::8::INSTR"):
        super().__init__(name, adapter)
        
        # Define what data this instrument returns
        self.data_columns = np.array(["X", "Y", "R", "Theta"])
        self.data_units = np.array(["V", "V", "V", "deg"])
    
    def _connect_impl(self) -> bool:
        """
        Your instrument's connection/identification protocol.
        Return True if connected successfully.
        """
        if self.instrument is None:
            return False
        try:
            # Clear status and query identity
            self.instrument.write("*CLS")
            idn = self.instrument.query("*IDN?")
            # Check if this is the expected instrument
            return "SR830" in idn or "SR860" in idn
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def _initialize_impl(self):
        """
        Your instrument's initialization sequence.
        Set instrument to a known, safe starting state.
        """
        # Example: Reset to defaults, set input configuration
        self.instrument.write("REST")      # Reset to defaults
        self.instrument.write("ISRC 0")    # Input A
        self.instrument.write("ICPL 0")    # AC coupling
        self.instrument.write("SENS 22")   # 1V sensitivity
        self.instrument.write("OFLT 10")   # 1s time constant
    
    def _shutdown_impl(self):
        """
        Your instrument's shutdown sequence.
        Return instrument to safe state, release local control.
        """
        self.instrument.write("LOCL 0")    # Return to local control
    
    @property
    def settings(self) -> dict:
        """
        Query current settings from the instrument.
        
        The scan system calls this to get current instrument state.
        Return a dict that can be passed back to the setter.
        """
        return {
            "sensitivity": int(self.instrument.query("SENS?")),
            "time_constant": int(self.instrument.query("OFLT?")),
            "input_source": int(self.instrument.query("ISRC?")),
            "harmonic": int(self.instrument.query("HARM?")),
            "reference_frequency": float(self.instrument.query("FREQ?")),
        }
    
    @settings.setter
    def settings(self, settings: dict):
        """
        Apply settings to the instrument.
        
        The scan system calls this before each scan to set user-defined settings.
        Only set values that are present in the settings dict.
        """
        if "sensitivity" in settings:
            self.instrument.write(f"SENS {settings['sensitivity']}")
        if "time_constant" in settings:
            self.instrument.write(f"OFLT {settings['time_constant']}")
        if "input_source" in settings:
            self.instrument.write(f"ISRC {settings['input_source']}")
        if "harmonic" in settings:
            self.instrument.write(f"HARM {settings['harmonic']}")
        if "reference_frequency" in settings:
            self.instrument.write(f"FREQ {settings['reference_frequency']}")
    
    def _perform_measurement_impl(self) -> np.ndarray:
        """
        Perform the actual measurement.
        
        Return a 2D numpy array where:
        - Each row is one measurement point
        - Columns correspond to self.data_columns
        """
        # Query all values at once for synchronization
        response = self.instrument.query("SNAP? 1,2,3,4")
        x, y, r, theta = map(float, response.split(","))
        return np.array([[x, y, r, theta]])


# =============================================================================
# EXAMPLE 2: Real Movement Instrument (e.g., Motion Controller)
# =============================================================================

class RealMotionAxis(VisaBaseMovementInstrument):
    """
    Template for a real motion controller axis.
    
    Replace the SCPI commands with your instrument's actual commands.
    """
    
    def __init__(self, name: str = "Stage X", adapter: str = "GPIB::1::INSTR", axis: int = 1):
        super().__init__(name, adapter)
        
        self.axis = axis
        self.position_units = "mm"
        self.position_column = f"axis{axis} position"
    
    def _connect_impl(self) -> bool:
        """Your instrument's identification protocol."""
        if self.instrument is None:
            return False
        try:
            idn = self.instrument.query("*IDN?")
            return "ESP" in idn or "XPS" in idn
        except Exception:
            return False
    
    def _initialize_impl(self):
        """
        Your instrument's initialization/homing sequence.
        """
        # Example: Home the axis
        self.instrument.write(f"{self.axis}OR")  # Home command
        # Wait for homing to complete
        while True:
            status = self.instrument.query(f"{self.axis}MD?")
            if status.strip() == "1":  # Motion done
                break
            time.sleep(0.1)
    
    def _shutdown_impl(self):
        """Your instrument's shutdown sequence."""
        # Example: Stop any motion, disable motor
        self.instrument.write(f"{self.axis}ST")  # Stop
    
    @property
    def position(self) -> float:
        """
        Query current position from the instrument.
        """
        response = self.instrument.query(f"{self.axis}TP")
        return float(response)
    
    @position.setter
    def position(self, value: float):
        """
        Move to the specified position.
        
        This should block until motion is complete (for scanning).
        """
        # Command absolute move
        self.instrument.write(f"{self.axis}PA{value}")
        
        # Wait for motion to complete
        while True:
            status = self.instrument.query(f"{self.axis}MD?")
            if status.strip() == "1":  # Motion done
                break
            time.sleep(0.01)
    
    @property
    def settings(self) -> dict:
        """Query motion parameters from the instrument."""
        return {
            "velocity": float(self.instrument.query(f"{self.axis}VA?")),
            "acceleration": float(self.instrument.query(f"{self.axis}AC?")),
            "deceleration": float(self.instrument.query(f"{self.axis}AG?")),
        }
    
    @settings.setter
    def settings(self, settings: dict):
        """Apply motion parameters to the instrument."""
        if "velocity" in settings:
            self.instrument.write(f"{self.axis}VA{settings['velocity']}")
        if "acceleration" in settings:
            self.instrument.write(f"{self.axis}AC{settings['acceleration']}")
        if "deceleration" in settings:
            self.instrument.write(f"{self.axis}AG{settings['deceleration']}")


# =============================================================================
# WRAPPER CLASSES for Scan System Integration
# =============================================================================

class RealLockInMeasurement(Measurement):
    """
    Wrapper to integrate RealLockInAmplifier with the scan system.
    
    The scan system expects the Measurement base class interface.
    """
    
    def __init__(self, name: str = "Lock-In", adapter: str = "GPIB::8::INSTR"):
        super().__init__(name)
        self._instrument = RealLockInAmplifier(name, adapter)
        self.data_columns = self._instrument.data_columns
        self.data_units = self._instrument.data_units
        self.adapter = adapter
    
    def check_connection(self) -> bool:
        return self._instrument.check_connection()
    
    def connect(self):
        self._instrument.connect()
        self.status = self._instrument.status
    
    def initialize(self):
        self._instrument.initialize()
    
    def shutdown(self):
        self._instrument.shutdown()
    
    def perform_measurement(self) -> np.ndarray:
        return self._instrument.perform_measurement()
    
    @property
    def settings(self) -> dict:
        return self._instrument.settings
    
    @settings.setter
    def settings(self, settings: dict):
        self._instrument.settings = settings


class RealAxisMovement(Movement):
    """
    Wrapper to integrate RealMotionAxis with the scan system.
    """
    
    def __init__(self, name: str = "Stage X", adapter: str = "GPIB::1::INSTR", axis: int = 1):
        super().__init__(name)
        self._instrument = RealMotionAxis(name, adapter, axis)
        self.position_units = self._instrument.position_units
        self.position_column = self._instrument.position_column
        self.adapter = adapter
    
    def check_connection(self) -> bool:
        return self._instrument.check_connection()
    
    def connect(self):
        self._instrument.connect()
        self.status = self._instrument.status
    
    def initialize(self):
        self._instrument.initialize()
    
    def shutdown(self):
        self._instrument.shutdown()
    
    @property
    def position(self) -> float:
        return self._instrument.position
    
    @position.setter
    def position(self, value: float):
        self._instrument.position = value
    
    @property
    def settings(self) -> dict:
        return self._instrument.settings
    
    @settings.setter
    def settings(self, settings: dict):
        self._instrument.settings = settings
