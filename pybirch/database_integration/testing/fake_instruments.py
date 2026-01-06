"""
Fake Instruments for Testing
============================
Mock measurement and movement instruments for testing the database integration
without requiring real hardware.
"""

import numpy as np
import pandas as pd
import time
from typing import Optional, Dict, Any, List

# Import base classes
try:
    from pybirch.Instruments.base import (
        BaseMeasurementInstrument,
        BaseMovementInstrument,
    )
except ImportError:
    # Provide minimal fallback classes for testing
    class BaseMeasurementInstrument:
        def __init__(self, name: str):
            self.name = name
            self.nickname = name
            self.adapter = ''
            self.status = False
            self.data_units = np.array([])
            self.data_columns = np.array([])
            self._settings_keys = []
            self._settings_defaults = {}
            self._use_auto_settings = False
        
        def _define_settings(self, settings_dict):
            self._settings_keys = list(settings_dict.keys())
            self._settings_defaults = settings_dict.copy()
            self._use_auto_settings = True
            for key, default_value in settings_dict.items():
                setattr(self, f"_{key}", default_value)
        
        def _get_auto_settings(self):
            return {key: getattr(self, f"_{key}", self._settings_defaults.get(key)) 
                    for key in self._settings_keys}
        
        def _set_auto_settings(self, settings):
            for key, value in settings.items():
                if key in self._settings_keys:
                    setattr(self, f"_{key}", value)
        
        @property
        def settings(self):
            return self._get_auto_settings()
        
        @settings.setter
        def settings(self, settings):
            self._set_auto_settings(settings)
        
        def connect(self):
            self.status = True
            return True
        
        def check_connection(self):
            return self.status
        
        def initialize(self):
            pass
        
        def shutdown(self):
            self.status = False
        
        def columns(self):
            return np.array([f"{col} ({unit})" for col, unit in zip(self.data_columns, self.data_units)])
        
        def measurement_df(self):
            return pd.DataFrame(self.perform_measurement(), columns=self.columns())
        
        def perform_measurement(self):
            return self._perform_measurement_impl()
    
    class BaseMovementInstrument:
        def __init__(self, name: str):
            self.name = name
            self.nickname = name
            self.adapter = ''
            self.status = False
            self.position = 0.0
            self.position_column = 'position'
            self.position_units = 'mm'
            self._settings_keys = []
            self._settings_defaults = {}
            self._use_auto_settings = False
        
        def _define_settings(self, settings_dict):
            self._settings_keys = list(settings_dict.keys())
            self._settings_defaults = settings_dict.copy()
            self._use_auto_settings = True
            for key, default_value in settings_dict.items():
                setattr(self, f"_{key}", default_value)
        
        def _get_auto_settings(self):
            return {key: getattr(self, f"_{key}", self._settings_defaults.get(key)) 
                    for key in self._settings_keys}
        
        def _set_auto_settings(self, settings):
            for key, value in settings.items():
                if key in self._settings_keys:
                    setattr(self, f"_{key}", value)
        
        @property
        def settings(self):
            return self._get_auto_settings()
        
        @settings.setter
        def settings(self, settings):
            self._set_auto_settings(settings)
        
        def connect(self):
            self.status = True
            return True
        
        def check_connection(self):
            return self.status
        
        def initialize(self):
            pass
        
        def shutdown(self):
            self.status = False
        
        def move_to(self, position: float):
            self._move_to_impl(position)
            self.position = position


class FakeMultimeter(BaseMeasurementInstrument):
    """
    Fake multimeter that returns random voltage/current readings.
    Useful for testing data flow without real hardware.
    """
    
    def __init__(self, name: str = "Fake_Multimeter"):
        super().__init__(name)
        self.data_columns = np.array(["Voltage", "Current"])
        self.data_units = np.array(["V", "A"])
        self._define_settings({
            "range": "auto",
            "nplc": 1.0,
            "averaging": 1,
        })
        
        # Simulation parameters
        self._base_voltage = 1.0
        self._base_current = 0.001
        self._noise_level = 0.01
    
    def _perform_measurement_impl(self) -> np.ndarray:
        """Generate fake measurement data with noise."""
        noise_v = np.random.normal(0, self._noise_level * self._base_voltage)
        noise_i = np.random.normal(0, self._noise_level * self._base_current)
        
        voltage = self._base_voltage + noise_v
        current = self._base_current + noise_i
        
        # Apply averaging
        if self._averaging > 1:
            voltages = [self._base_voltage + np.random.normal(0, self._noise_level * self._base_voltage) 
                       for _ in range(self._averaging)]
            currents = [self._base_current + np.random.normal(0, self._noise_level * self._base_current) 
                       for _ in range(self._averaging)]
            voltage = np.mean(voltages)
            current = np.mean(currents)
        
        return np.array([[voltage, current]])
    
    def set_output(self, voltage: float, current: float):
        """Set the simulated output values."""
        self._base_voltage = voltage
        self._base_current = current


class FakeSpectrometer(BaseMeasurementInstrument):
    """
    Fake spectrometer that returns simulated spectrum data.
    Generates Gaussian peaks with optional noise.
    """
    
    def __init__(self, name: str = "Fake_Spectrometer", num_pixels: int = 1024):
        super().__init__(name)
        self._num_pixels = num_pixels
        
        # Create wavelength columns
        self.data_columns = np.array([f"pixel_{i}" for i in range(num_pixels)])
        self.data_units = np.array(["counts"] * num_pixels)
        
        self._define_settings({
            "integration_time": 100,  # ms
            "gain": 1.0,
            "wavelength_start": 400,  # nm
            "wavelength_end": 800,    # nm
        })
        
        # Simulation parameters
        self._peak_positions = [500, 600, 700]  # nm
        self._peak_widths = [10, 15, 20]        # nm
        self._peak_heights = [1000, 800, 600]   # counts
        self._noise_level = 10  # counts
    
    def _perform_measurement_impl(self) -> np.ndarray:
        """Generate fake spectrum data with Gaussian peaks."""
        wavelengths = np.linspace(
            self._wavelength_start, 
            self._wavelength_end, 
            self._num_pixels
        )
        
        spectrum = np.zeros(self._num_pixels)
        
        # Add Gaussian peaks
        for pos, width, height in zip(self._peak_positions, self._peak_widths, self._peak_heights):
            gaussian = height * np.exp(-((wavelengths - pos) ** 2) / (2 * width ** 2))
            spectrum += gaussian * self._gain
        
        # Add noise
        noise = np.random.normal(0, self._noise_level, self._num_pixels)
        spectrum += noise
        
        # Scale by integration time
        spectrum *= (self._integration_time / 100.0)
        
        return spectrum.reshape(1, -1)
    
    def columns(self) -> np.ndarray:
        """Override to return wavelength-based column names."""
        wavelengths = np.linspace(
            self._wavelength_start, 
            self._wavelength_end, 
            self._num_pixels
        )
        return np.array([f"{wl:.1f} nm" for wl in wavelengths])
    
    def set_peaks(self, positions: List[float], widths: List[float], heights: List[float]):
        """Set the simulated peak parameters."""
        self._peak_positions = positions
        self._peak_widths = widths
        self._peak_heights = heights


class FakeLockin(BaseMeasurementInstrument):
    """
    Fake lock-in amplifier that returns simulated X, Y, R, Theta values.
    """
    
    def __init__(self, name: str = "Fake_Lockin"):
        super().__init__(name)
        self.data_columns = np.array(["X", "Y", "R", "Theta"])
        self.data_units = np.array(["V", "V", "V", "deg"])
        
        self._define_settings({
            "sensitivity": 1e-6,
            "time_constant": 100,  # ms
            "filter_slope": 12,    # dB/oct
            "reference_frequency": 1000,  # Hz
        })
        
        # Simulation parameters
        self._signal_amplitude = 1e-7  # V
        self._signal_phase = 45.0      # degrees
        self._noise_floor = 1e-9       # V
    
    def _perform_measurement_impl(self) -> np.ndarray:
        """Generate fake lock-in measurement data."""
        # Calculate X and Y from amplitude and phase
        phase_rad = np.radians(self._signal_phase)
        x_clean = self._signal_amplitude * np.cos(phase_rad)
        y_clean = self._signal_amplitude * np.sin(phase_rad)
        
        # Add noise
        x = x_clean + np.random.normal(0, self._noise_floor)
        y = y_clean + np.random.normal(0, self._noise_floor)
        
        # Calculate R and Theta
        r = np.sqrt(x**2 + y**2)
        theta = np.degrees(np.arctan2(y, x))
        
        return np.array([[x, y, r, theta]])
    
    def set_signal(self, amplitude: float, phase: float):
        """Set the simulated signal parameters."""
        self._signal_amplitude = amplitude
        self._signal_phase = phase


class FakeStage(BaseMovementInstrument):
    """
    Fake linear stage for testing movement and positioning.
    """
    
    def __init__(self, name: str = "Fake_Stage", axis: str = "X"):
        super().__init__(name)
        self.axis = axis
        self.position = 0.0
        self.position_column = f"{axis}_position"
        self.position_units = "mm"
        
        self._define_settings({
            "velocity": 10.0,     # mm/s
            "acceleration": 50.0, # mm/s^2
            "min_position": -50.0,
            "max_position": 50.0,
        })
        
        # Simulation parameters
        self._move_delay = 0.01  # seconds per mm
        self._position_noise = 0.001  # mm
    
    def _move_to_impl(self, position: float):
        """Simulate moving to a position."""
        # Check limits
        if position < self._min_position:
            position = self._min_position
        elif position > self._max_position:
            position = self._max_position
        
        # Simulate movement time
        distance = abs(position - self.position)
        move_time = distance * self._move_delay
        time.sleep(move_time)
        
        # Add position noise
        self.position = position + np.random.normal(0, self._position_noise)
    
    def move_to(self, position: float):
        """Move to the specified position."""
        self._move_to_impl(position)
    
    def get_position(self) -> float:
        """Get current position."""
        return self.position
    
    def home(self):
        """Home the stage (move to 0)."""
        self.move_to(0.0)


class FakePiezo(BaseMovementInstrument):
    """
    Fake piezo stage for fine positioning.
    """
    
    def __init__(self, name: str = "Fake_Piezo", axis: str = "Z"):
        super().__init__(name)
        self.axis = axis
        self.position = 0.0
        self.position_column = f"{axis}_piezo"
        self.position_units = "um"  # Microns
        
        self._define_settings({
            "closed_loop": True,
            "servo_bandwidth": 100,  # Hz
            "min_position": 0.0,
            "max_position": 100.0,   # um
        })
        
        # Simulation parameters
        self._position_noise = 0.001  # um (nanometer precision)
        self._response_time = 0.001   # seconds
    
    def _move_to_impl(self, position: float):
        """Simulate moving to a position."""
        # Check limits
        if position < self._min_position:
            position = self._min_position
        elif position > self._max_position:
            position = self._max_position
        
        # Simulate response time
        time.sleep(self._response_time)
        
        # Add position noise (smaller than mechanical stage)
        self.position = position + np.random.normal(0, self._position_noise)
    
    def move_to(self, position: float):
        """Move to the specified position."""
        self._move_to_impl(position)
    
    def get_position(self) -> float:
        """Get current position."""
        return self.position


class FakeTemperatureController(BaseMeasurementInstrument):
    """
    Fake temperature controller that simulates heating/cooling.
    """
    
    def __init__(self, name: str = "Fake_TempController"):
        super().__init__(name)
        self.data_columns = np.array(["Temperature", "Setpoint", "Heater_Power"])
        self.data_units = np.array(["K", "K", "%"])
        
        self._define_settings({
            "setpoint": 300.0,   # K
            "ramp_rate": 10.0,   # K/min
            "p_gain": 50.0,
            "i_gain": 10.0,
            "d_gain": 0.0,
        })
        
        # Simulation state
        self._temperature = 300.0  # K
        self._heater_power = 0.0   # %
        self._last_time = time.time()
    
    def _perform_measurement_impl(self) -> np.ndarray:
        """Simulate temperature measurement and control."""
        # Update temperature based on setpoint
        current_time = time.time()
        dt = current_time - self._last_time
        self._last_time = current_time
        
        # Simple proportional control simulation
        error = self._setpoint - self._temperature
        max_rate = self._ramp_rate / 60.0  # Convert to K/s
        
        if abs(error) > 0.1:
            # Move towards setpoint
            change = min(abs(error), max_rate * dt) * np.sign(error)
            self._temperature += change
            self._heater_power = min(100, max(0, error * self._p_gain))
        else:
            # At setpoint, add small noise
            self._temperature += np.random.normal(0, 0.01)
            self._heater_power = 50 + np.random.normal(0, 1)
        
        return np.array([[self._temperature, self._setpoint, self._heater_power]])
    
    def set_temperature(self, temperature: float):
        """Set target temperature."""
        self._setpoint = temperature


# Convenience function to create a set of test instruments
def create_test_instruments():
    """
    Create a standard set of fake instruments for testing.
    
    Returns:
        dict: Dictionary of instrument name -> instrument instance
    """
    return {
        'multimeter': FakeMultimeter("Test_DMM"),
        'spectrometer': FakeSpectrometer("Test_Spectrometer"),
        'lockin': FakeLockin("Test_Lockin"),
        'x_stage': FakeStage("X_Stage", axis="X"),
        'y_stage': FakeStage("Y_Stage", axis="Y"),
        'z_piezo': FakePiezo("Z_Piezo", axis="Z"),
        'temp_controller': FakeTemperatureController("Temp_Controller"),
    }
