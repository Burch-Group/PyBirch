"""
Unit Tests for PyBirch Fake Instruments

This module provides thorough testing of the fake instruments without requiring
the full GUI dependencies. Tests cover:

- Instrument creation and initialization
- Connection/disconnection lifecycle
- Settings management (automatic and custom)
- Measurement data format and values
- Movement position control and limits
- Serialization/deserialization

Run with: pytest tests/test_fake_instruments.py -v
"""

import sys
import os
import logging
import numpy as np
import pandas as pd
import pytest

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import fake instruments
from pybirch.setups.fake_setup.lock_in_amplifier.lock_in_amplifier import (
    FakeLockInAmplifier,
    LockInAmplifierMeasurement
)
from pybirch.setups.fake_setup.multimeter.multimeter import (
    FakeMultimeter,
    VoltageMeterMeasurement,
    CurrentSourceMovement
)
from pybirch.setups.fake_setup.stage_controller.stage_controller import (
    FakeAxis,
    FakeLinearStageController,
    FakeXStage,
    FakeYStage,
    FakeZStage,
    get_shared_controller
)
from pybirch.setups.fake_setup.spectrometer.spectrometer import (
    FakeSpectrometer,
    SpectrometerMeasurement
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# Lock-In Amplifier Tests
# =============================================================================

class TestFakeLockInAmplifier:
    """Tests for FakeLockInAmplifier."""
    
    @pytest.fixture
    def lock_in(self):
        """Create a fresh lock-in amplifier instance."""
        return FakeLockInAmplifier(name="Test Lock-In", wait=0.0)
    
    def test_initialization(self, lock_in):
        """Test lock-in amplifier initialization."""
        logger.info("Testing lock-in initialization")
        
        assert lock_in.name == "Test Lock-In"
        assert lock_in.status == True  # Fake instruments start connected
        
        # Check data structure
        assert len(lock_in.data_columns) == 3
        assert list(lock_in.data_columns) == ["X", "Y", "R"]
        assert list(lock_in.data_units) == ["V", "V", "V"]
        
    def test_connection_lifecycle(self, lock_in):
        """Test connect/check/shutdown cycle."""
        logger.info("Testing connection lifecycle")
        
        # Connect
        result = lock_in.connect()
        assert result == True
        assert lock_in.check_connection() == True
        
        # Shutdown
        lock_in.shutdown()
        assert lock_in.status == False
        
    def test_default_settings(self, lock_in):
        """Test default settings values."""
        logger.info("Testing default settings")
        
        settings = lock_in.settings
        
        assert "sensitivity" in settings
        assert "time_constant" in settings
        assert "num_data_points" in settings
        
        assert settings["sensitivity"] == 1.0
        assert settings["time_constant"] == 0.1
        assert settings["num_data_points"] == 10
        
    def test_modify_settings(self, lock_in):
        """Test modifying settings."""
        logger.info("Testing settings modification")
        
        new_settings = {
            "sensitivity": 0.5,
            "time_constant": 0.25,
            "num_data_points": 20
        }
        
        lock_in.settings = new_settings
        
        result = lock_in.settings
        assert result["sensitivity"] == 0.5
        assert result["time_constant"] == 0.25
        assert result["num_data_points"] == 20
        
    def test_measurement_output_shape(self, lock_in):
        """Test measurement output shape."""
        logger.info("Testing measurement output shape")
        
        lock_in.connect()
        lock_in.initialize()
        
        data = lock_in.perform_measurement()
        
        assert isinstance(data, np.ndarray)
        assert data.ndim == 2
        assert data.shape[0] == lock_in._num_data_points
        assert data.shape[1] == 3  # X, Y, R
        
    def test_measurement_r_calculation(self, lock_in):
        """Test that R = sqrt(X^2 + Y^2)."""
        logger.info("Testing R calculation")
        
        lock_in.connect()
        lock_in.initialize()
        
        data = lock_in.perform_measurement()
        X, Y, R = data[:, 0], data[:, 1], data[:, 2]
        
        expected_R = np.sqrt(X**2 + Y**2)
        np.testing.assert_array_almost_equal(R, expected_R, decimal=10)
        
    def test_measurement_df(self, lock_in):
        """Test measurement_df returns proper DataFrame."""
        logger.info("Testing measurement_df")
        
        lock_in.connect()
        lock_in.initialize()
        
        df = lock_in.measurement_df()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df.columns) == 3
        
        # Columns should have units
        expected_cols = ["X (V)", "Y (V)", "R (V)"]
        assert list(df.columns) == expected_cols
        
    def test_columns_method(self, lock_in):
        """Test columns() method returns proper format."""
        logger.info("Testing columns method")
        
        cols = lock_in.columns()
        
        assert isinstance(cols, np.ndarray)
        assert len(cols) == 3
        assert all("(" in c and ")" in c for c in cols)
        
    def test_property_setters(self, lock_in):
        """Test individual property setters."""
        logger.info("Testing property setters")
        
        # Sensitivity
        lock_in.sensitivity = 0.001
        assert lock_in.sensitivity == 0.001
        
        # Time constant
        lock_in.time_constant = 1.0
        assert lock_in.time_constant == 1.0
        
        # Num data points
        lock_in.num_data_points = 100
        assert lock_in.num_data_points == 100
        
    def test_property_validation(self, lock_in):
        """Test that invalid values raise errors."""
        logger.info("Testing property validation")
        
        with pytest.raises(ValueError):
            lock_in.sensitivity = -1.0
            
        with pytest.raises(ValueError):
            lock_in.time_constant = 0.0
            
        with pytest.raises(ValueError):
            lock_in.num_data_points = -5
            
    def test_initialize_resets_settings(self, lock_in):
        """Test that initialize resets to defaults."""
        logger.info("Testing initialize resets settings")
        
        # Change settings
        lock_in.settings = {"sensitivity": 0.5, "time_constant": 0.5, "num_data_points": 5}
        
        # Initialize should reset
        lock_in.initialize()
        
        settings = lock_in.settings
        assert settings["sensitivity"] == 1.0
        assert settings["time_constant"] == 0.1
        assert settings["num_data_points"] == 10
        
    def test_serialize(self, lock_in):
        """Test serialization."""
        logger.info("Testing serialization")
        
        lock_in.nickname = "Custom Name"
        lock_in.settings = {"sensitivity": 0.5}
        
        data = lock_in.serialize()
        
        assert data["name"] == "Test Lock-In"
        assert data["nickname"] == "Custom Name"
        assert data["pybirch_class"] == "FakeLockInAmplifier"
        assert "settings" in data


class TestLockInAmplifierMeasurement:
    """Tests for the LockInAmplifierMeasurement wrapper."""
    
    @pytest.fixture
    def measurement(self):
        return LockInAmplifierMeasurement(name="Wrapped Lock-In")
    
    def test_wrapper_attributes(self, measurement):
        """Test wrapper has correct attributes."""
        logger.info("Testing wrapper attributes")
        
        assert measurement.name == "Wrapped Lock-In"
        assert hasattr(measurement, 'instrument')
        assert isinstance(measurement.instrument, FakeLockInAmplifier)
        
    def test_wrapper_connection(self, measurement):
        """Test wrapper connection methods."""
        logger.info("Testing wrapper connection")
        
        measurement.connect()
        assert measurement.status == True
        assert measurement.check_connection() == True
        
    def test_wrapper_measurement(self, measurement):
        """Test wrapper measurement methods."""
        logger.info("Testing wrapper measurement")
        
        measurement.connect()
        measurement.initialize()
        
        data = measurement.perform_measurement()
        
        assert isinstance(data, np.ndarray)
        assert data.shape[1] == 3


# =============================================================================
# Multimeter Tests
# =============================================================================

class TestFakeMultimeter:
    """Tests for FakeMultimeter backend."""
    
    @pytest.fixture
    def multimeter(self):
        return FakeMultimeter(name="Test Multimeter", wait=0.0)
    
    def test_initialization(self, multimeter):
        """Test multimeter initialization."""
        logger.info("Testing multimeter initialization")
        
        assert multimeter.name == "Test Multimeter"
        assert multimeter.current == 0.0
        assert multimeter.voltage == 0.0
        
    def test_current_property(self, multimeter):
        """Test current property."""
        logger.info("Testing current property")
        
        multimeter.current = 0.001
        assert multimeter.current == 0.001
        
        multimeter.current = -0.005
        assert multimeter.current == -0.005
        
    def test_voltage_property(self, multimeter):
        """Test voltage property."""
        logger.info("Testing voltage property")
        
        multimeter.voltage = 5.0
        assert multimeter.voltage == 5.0


class TestVoltageMeterMeasurement:
    """Tests for VoltageMeterMeasurement."""
    
    @pytest.fixture
    def voltmeter(self):
        return VoltageMeterMeasurement(name="Test Voltmeter")
    
    def test_initialization(self, voltmeter):
        """Test voltmeter initialization."""
        logger.info("Testing voltmeter initialization")
        
        assert voltmeter.name == "Test Voltmeter"
        assert list(voltmeter.data_columns) == ["current", "voltage"]
        assert list(voltmeter.data_units) == ["A", "V"]
        
    def test_measurement_output(self, voltmeter):
        """Test measurement output format."""
        logger.info("Testing measurement output")
        
        voltmeter.connect()
        voltmeter.initialize()
        
        data = voltmeter.perform_measurement()
        
        assert isinstance(data, np.ndarray)
        assert data.shape[1] == 2  # current, voltage
        
    def test_measurement_with_set_current(self, voltmeter):
        """Test measurement reflects set current."""
        logger.info("Testing measurement with set current")
        
        voltmeter.connect()
        voltmeter.initialize()
        
        voltmeter.instrument.current = 0.01  # 10 mA
        
        data = voltmeter.perform_measurement()
        currents = data[:, 0]
        
        # All current values should be 0.01
        np.testing.assert_array_almost_equal(currents, 0.01)


class TestCurrentSourceMovement:
    """Tests for CurrentSourceMovement."""
    
    @pytest.fixture
    def current_source(self):
        return CurrentSourceMovement(name="Test Current Source")
    
    def test_initialization(self, current_source):
        """Test current source initialization."""
        logger.info("Testing current source initialization")
        
        assert current_source.name == "Test Current Source"
        assert current_source.position_units == "A"
        assert current_source.position_column == "current"
        
    def test_position_control(self, current_source):
        """Test position (current) control."""
        logger.info("Testing position control")
        
        current_source.connect()
        current_source.initialize()
        
        assert current_source.position == 0.0
        
        current_source.position = 0.005
        assert current_source.position == 0.005
        
    def test_position_df(self, current_source):
        """Test position_df output."""
        logger.info("Testing position_df")
        
        current_source.connect()
        current_source.position = 0.001
        
        df = current_source.position_df()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df.columns) == 1
        assert "current (A)" in df.columns[0]


# =============================================================================
# Stage Controller Tests
# =============================================================================

class TestFakeLinearStageController:
    """Tests for FakeLinearStageController."""
    
    @pytest.fixture
    def controller(self):
        return FakeLinearStageController(name="Test Controller", wait=0.0)
    
    def test_initialization(self, controller):
        """Test controller initialization."""
        logger.info("Testing controller initialization")
        
        assert controller.name == "Test Controller"
        assert hasattr(controller, 'x')
        assert hasattr(controller, 'y')
        assert hasattr(controller, 'z')
        
    def test_axis_independence(self, controller):
        """Test that axes are independent."""
        logger.info("Testing axis independence")
        
        controller.x.position = 10
        controller.y.position = 20
        controller.z.position = 30
        
        assert controller.x.position == 10
        assert controller.y.position == 20
        assert controller.z.position == 30


class TestFakeAxis:
    """Tests for FakeAxis."""
    
    @pytest.fixture
    def controller(self):
        return FakeLinearStageController()
    
    def test_position_limits(self, controller):
        """Test position limits."""
        logger.info("Testing position limits")
        
        axis = controller.x
        
        # Default limits
        assert axis.left_limit == 0.0
        assert axis.right_limit == 100.0
        
        # Valid position
        axis.position = 50.0
        assert axis.position == 50.0
        
        # Out of bounds
        with pytest.raises(ValueError):
            axis.position = -10.0
            
        with pytest.raises(ValueError):
            axis.position = 150.0
            
    def test_custom_limits(self, controller):
        """Test custom limits."""
        logger.info("Testing custom limits")
        
        axis = controller.x
        
        axis.left_limit = -50.0
        axis.right_limit = 50.0
        
        # Now -30 should be valid
        axis.position = -30.0
        assert axis.position == -30.0
        
        # 60 should be invalid
        with pytest.raises(ValueError):
            axis.position = 60.0


class TestFakeXStage:
    """Tests for FakeXStage."""
    
    @pytest.fixture
    def x_stage(self):
        return FakeXStage(name="Test X Stage", use_shared_controller=False)
    
    def test_initialization(self, x_stage):
        """Test X stage initialization."""
        logger.info("Testing X stage initialization")
        
        assert x_stage.name == "Test X Stage"
        assert x_stage.position_units == "mm"
        assert x_stage.position_column == "x position"
        
    def test_connection(self, x_stage):
        """Test connection."""
        logger.info("Testing X stage connection")
        
        x_stage.connect()
        assert x_stage.check_connection() == True
        
    def test_position(self, x_stage):
        """Test position control."""
        logger.info("Testing X stage position")
        
        x_stage.connect()
        x_stage.initialize()  # Should home to 0
        
        assert x_stage.position == 0.0
        
        x_stage.position = 25.0
        assert x_stage.position == 25.0
        
    def test_settings(self, x_stage):
        """Test settings include position and limits."""
        logger.info("Testing X stage settings")
        
        x_stage.connect()
        x_stage.position = 30.0
        
        settings = x_stage.settings
        
        assert settings["position"] == 30.0
        assert settings["units"] == "mm"
        assert "left_limit" in settings
        assert "right_limit" in settings
        
    def test_settings_setter(self, x_stage):
        """Test settings setter."""
        logger.info("Testing X stage settings setter")
        
        x_stage.connect()
        
        x_stage.settings = {
            "position": 40.0,
            "left_limit": -10.0,
            "right_limit": 90.0
        }
        
        assert x_stage.position == 40.0
        assert x_stage.controller.x.left_limit == -10.0
        assert x_stage.controller.x.right_limit == 90.0


class TestFakeYStage:
    """Tests for FakeYStage."""
    
    @pytest.fixture
    def y_stage(self):
        return FakeYStage(name="Test Y Stage")
    
    def test_initialization(self, y_stage):
        """Test Y stage initialization."""
        logger.info("Testing Y stage initialization")
        
        assert y_stage.name == "Test Y Stage"
        assert y_stage.position_column == "y position"


class TestFakeZStage:
    """Tests for FakeZStage."""
    
    @pytest.fixture
    def z_stage(self):
        return FakeZStage(name="Test Z Stage")
    
    def test_initialization(self, z_stage):
        """Test Z stage initialization."""
        logger.info("Testing Z stage initialization")
        
        assert z_stage.name == "Test Z Stage"
        assert z_stage.position_column == "z position"


class TestSharedController:
    """Tests for shared controller functionality."""
    
    def test_shared_controller_same_instance(self):
        """Test that shared controller returns same instance."""
        logger.info("Testing shared controller")
        
        # Reset global
        import pybirch.setups.fake_setup.stage_controller.stage_controller as sc
        sc._shared_controller = None
        
        x1 = FakeXStage("X1", use_shared_controller=True)
        x2 = FakeXStage("X2", use_shared_controller=True)
        y1 = FakeYStage("Y1", use_shared_controller=True)
        
        # All should share same controller
        assert x1.controller is x2.controller
        assert x1.controller is y1.controller
        
    def test_shared_controller_position_sync(self):
        """Test that shared controller syncs positions."""
        logger.info("Testing shared controller position sync")
        
        # Reset global
        import pybirch.setups.fake_setup.stage_controller.stage_controller as sc
        sc._shared_controller = None
        
        x1 = FakeXStage("X1", use_shared_controller=True)
        x2 = FakeXStage("X2", use_shared_controller=True)
        
        x1.position = 42.0
        
        # x2 should see same position since they share controller
        assert x2.position == 42.0


# =============================================================================
# Spectrometer Tests
# =============================================================================

class TestFakeSpectrometer:
    """Tests for FakeSpectrometer."""
    
    @pytest.fixture
    def spectrometer(self):
        return FakeSpectrometer(name="Test Spectrometer", wait=0.0)
    
    def test_initialization(self, spectrometer):
        """Test spectrometer initialization."""
        logger.info("Testing spectrometer initialization")
        
        assert spectrometer.name == "Test Spectrometer"
        assert list(spectrometer.data_columns) == ["wavelength", "intensity"]
        assert list(spectrometer.data_units) == ["nm", "a.u."]
        
    def test_measurement(self, spectrometer):
        """Test spectrometer measurement."""
        logger.info("Testing spectrometer measurement")
        
        spectrometer.connect()
        spectrometer.initialize()
        
        data = spectrometer.perform_measurement()
        
        assert isinstance(data, np.ndarray)
        assert data.shape[1] == 2  # wavelength, intensity
        assert data.shape[0] > 0
        
    def test_wavelength_range_settings(self, spectrometer):
        """Test wavelength range in settings."""
        logger.info("Testing wavelength range settings")
        
        spectrometer.connect()
        
        settings = spectrometer.settings
        
        assert "left_wavelength" in settings
        assert "right_wavelength" in settings
        
    def test_wavelength_filtering(self, spectrometer):
        """Test that wavelength filtering works."""
        logger.info("Testing wavelength filtering")
        
        spectrometer.connect()
        spectrometer.initialize()
        
        # Set a narrow range
        spectrometer.settings = {
            "left_wavelength": 400.0,
            "right_wavelength": 600.0
        }
        
        data = spectrometer.perform_measurement()
        wavelengths = data[:, 0]
        
        # All wavelengths should be within range
        assert all(wavelengths >= 400.0)
        assert all(wavelengths <= 600.0)


# =============================================================================
# Base Class Tests
# =============================================================================

class TestBaseClassInterface:
    """Tests for base class interface compliance."""
    
    def test_measurement_base_class_method(self):
        """Test __base_class__ returns Measurement."""
        logger.info("Testing measurement __base_class__")
        
        from pybirch.scan.measurements import Measurement
        
        lockin = FakeLockInAmplifier()
        voltmeter = VoltageMeterMeasurement()
        spectrometer = FakeSpectrometer()
        
        assert lockin.__base_class__() is Measurement
        assert voltmeter.__base_class__() is Measurement
        assert spectrometer.__base_class__() is Measurement
        
    def test_movement_base_class_method(self):
        """Test __base_class__ returns Movement."""
        logger.info("Testing movement __base_class__")
        
        from pybirch.scan.movements import Movement
        
        x_stage = FakeXStage()
        current = CurrentSourceMovement()
        
        assert x_stage.__base_class__() is Movement
        assert current.__base_class__() is Movement


class TestSerializationDeserialization:
    """Tests for instrument serialization."""
    
    def test_lock_in_serialize(self):
        """Test lock-in serialization."""
        logger.info("Testing lock-in serialization")
        
        lockin = FakeLockInAmplifier("Serialize Test")
        lockin.nickname = "SN001"
        lockin.settings = {"sensitivity": 0.5, "time_constant": 0.2}
        
        data = lockin.serialize()
        
        assert "name" in data
        assert "nickname" in data
        assert "type" in data
        assert "settings" in data
        assert data["settings"]["sensitivity"] == 0.5
        
    def test_movement_serialize(self):
        """Test movement serialization."""
        logger.info("Testing movement serialization")
        
        stage = FakeXStage("Stage Test")
        stage.position = 35.0
        
        data = stage.serialize()
        
        assert "name" in data
        assert "position_units" in data
        assert "position_column" in data
        assert "settings" in data


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Performance-related tests."""
    
    def test_measurement_speed(self):
        """Test measurement is reasonably fast without wait."""
        logger.info("Testing measurement speed")
        
        import time
        
        lockin = FakeLockInAmplifier(wait=0.0)
        lockin.connect()
        lockin.initialize()
        
        # Time 100 measurements
        start = time.time()
        for _ in range(100):
            lockin.perform_measurement()
        elapsed = time.time() - start
        
        # Should complete in under 1 second
        assert elapsed < 1.0, f"100 measurements took {elapsed:.2f}s"
        logger.info(f"100 measurements completed in {elapsed:.3f}s")
        
    def test_wait_parameter(self):
        """Test that wait parameter adds delay."""
        logger.info("Testing wait parameter")
        
        import time
        
        fast = FakeLockInAmplifier(wait=0.0)
        slow = FakeLockInAmplifier(wait=0.01)
        
        fast.connect()
        slow.connect()
        
        # Time single measurement
        start = time.time()
        fast.perform_measurement()
        fast_time = time.time() - start
        
        start = time.time()
        slow.perform_measurement()
        slow_time = time.time() - start
        
        # Slow should be noticeably slower
        assert slow_time > fast_time
        logger.info(f"Fast: {fast_time:.4f}s, Slow: {slow_time:.4f}s")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
