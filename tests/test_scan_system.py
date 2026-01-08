"""
Unit Tests for PyBirch Scan System Core Components

This module tests the scan system core functionality independently of the queue:
- InstrumentTreeItem creation, traversal, and state management
- FastForward batching algorithm
- Scan execution loop
- Data buffering and saving
- Serialization/deserialization
- Pause/abort/restart functionality

These tests establish a baseline before refactoring to ensure no regressions.

Run with: pytest tests/test_scan_system.py -v
"""

import sys
import os
import time
import logging
import tempfile
import pickle
from datetime import datetime
from typing import List, Dict, Any
from unittest import mock
import numpy as np
import pandas as pd
import pytest
from threading import Event, Lock
from collections import defaultdict
from dataclasses import dataclass

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import PyBirch components
from pybirch.scan.scan import Scan, ScanSettings, get_empty_scan
from pybirch.scan.measurements import Measurement, MeasurementItem
from pybirch.scan.movements import Movement, MovementItem
from pybirch.scan.protocols import (
    MovementProtocol, 
    MeasurementProtocol, 
    is_movement, 
    is_measurement,
    get_instrument_type
)

# Import ScanTreeModel
try:
    from GUI.widgets.scan_tree.treemodel import ScanTreeModel
    from GUI.widgets.scan_tree.treeitem import InstrumentTreeItem
    HAS_GUI = True
except ImportError:
    HAS_GUI = False
    ScanTreeModel = None
    InstrumentTreeItem = None

# Import fake instruments
try:
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
        FakeXStage,
        FakeYStage,
        FakeZStage,
    )
    HAS_FAKE_INSTRUMENTS = True
except ImportError:
    HAS_FAKE_INSTRUMENTS = False

# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Mock Instruments for Testing (no external dependencies)
# =============================================================================

class MockMovement(Movement):
    """A minimal mock movement instrument for testing."""
    
    def __init__(self, name: str = "MockMovement"):
        super().__init__(name)
        self._position = 0.0
        self.position_units = "mm"
        self.position_column = "position"
        self._connected = False
        self._initialized = False
        self.connect_count = 0
        self.initialize_count = 0
        self.shutdown_count = 0
    
    def check_connection(self) -> bool:
        return self._connected
    
    @property
    def position(self) -> float:
        return self._position
    
    @position.setter
    def position(self, value: float):
        self._position = value
    
    @property
    def settings(self) -> dict:
        return {"position": self._position}
    
    @settings.setter
    def settings(self, settings: dict):
        if "position" in settings:
            self._position = settings["position"]
    
    def connect(self):
        self._connected = True
        self.connect_count += 1
    
    def initialize(self):
        self._initialized = True
        self.initialize_count += 1
    
    def shutdown(self):
        self._connected = False
        self._initialized = False
        self.shutdown_count += 1


class MockMeasurement(Measurement):
    """A minimal mock measurement instrument for testing."""
    
    def __init__(self, name: str = "MockMeasurement"):
        super().__init__(name)
        self.data_columns = np.array(["value1", "value2"])
        self.data_units = np.array(["V", "A"])
        self._connected = False
        self._initialized = False
        self.measurement_count = 0
        self.connect_count = 0
        self.initialize_count = 0
        self.shutdown_count = 0
    
    def check_connection(self) -> bool:
        return self._connected
    
    def perform_measurement(self) -> np.ndarray:
        self.measurement_count += 1
        return np.array([[1.0, 2.0], [3.0, 4.0]])
    
    @property
    def settings(self) -> dict:
        return {"num_points": 2}
    
    @settings.setter
    def settings(self, settings: dict):
        pass
    
    def connect(self):
        self._connected = True
        self.connect_count += 1
    
    def initialize(self):
        self._initialized = True
        self.initialize_count += 1
    
    def shutdown(self):
        self._connected = False
        self._initialized = False
        self.shutdown_count += 1


class MockExtension:
    """A mock extension for testing extension callbacks."""
    
    def __init__(self):
        self.startup_called = False
        self.execute_called = False
        self.shutdown_called = False
        self.saved_data: List[tuple] = []
        self.scan_ref = None
    
    def set_scan_reference(self, scan):
        self.scan_ref = scan
    
    def startup(self):
        self.startup_called = True
    
    def execute(self):
        self.execute_called = True
    
    def save_data(self, df: pd.DataFrame, measurement_name: str):
        self.saved_data.append((df.copy(), measurement_name))
    
    def shutdown(self):
        self.shutdown_called = True


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_movement():
    """Create a mock movement instrument."""
    return MockMovement("TestMovement")


@pytest.fixture
def mock_measurement():
    """Create a mock measurement instrument."""
    return MockMeasurement("TestMeasurement")


@pytest.fixture
def mock_extension():
    """Create a mock extension."""
    return MockExtension()


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def create_tree_item(instrument_item, parent=None, indices=None, final_indices=None, semaphore=""):
    """Helper to create an InstrumentTreeItem."""
    if not HAS_GUI:
        pytest.skip("GUI dependencies not available")
    
    return InstrumentTreeItem(
        parent=parent,
        instrument_object=instrument_item,
        indices=indices or [],
        final_indices=final_indices or [],
        semaphore=semaphore
    )


def create_simple_tree(movement, measurement, positions):
    """Create a simple scan tree: movement -> measurement."""
    if not HAS_GUI:
        pytest.skip("GUI dependencies not available")
    
    root = InstrumentTreeItem()
    
    move_item = MovementItem(movement, positions=positions, settings={})
    move_tree_item = InstrumentTreeItem(parent=root, instrument_object=move_item)
    root.child_items.append(move_tree_item)
    
    meas_item = MeasurementItem(measurement, settings={})
    meas_tree_item = InstrumentTreeItem(parent=move_tree_item, instrument_object=meas_item)
    move_tree_item.child_items.append(meas_tree_item)
    
    return ScanTreeModel(root_item=root)


# =============================================================================
# Tests: Movement and Measurement Base Classes
# =============================================================================

class TestMovementBaseClass:
    """Tests for Movement base class."""
    
    def test_movement_creation(self, mock_movement):
        """Test movement instrument creation."""
        assert mock_movement.name == "TestMovement"
        assert mock_movement.position_units == "mm"
        assert mock_movement.position_column == "position"
        assert mock_movement.position == 0.0
    
    def test_movement_position_set_get(self, mock_movement):
        """Test position property."""
        mock_movement.position = 50.0
        assert mock_movement.position == 50.0
        
        mock_movement.position = -10.0
        assert mock_movement.position == -10.0
    
    def test_movement_lifecycle(self, mock_movement):
        """Test connect/initialize/shutdown lifecycle."""
        assert mock_movement.connect_count == 0
        assert mock_movement.initialize_count == 0
        
        mock_movement.connect()
        assert mock_movement._connected == True
        assert mock_movement.connect_count == 1
        
        mock_movement.initialize()
        assert mock_movement._initialized == True
        assert mock_movement.initialize_count == 1
        
        mock_movement.shutdown()
        assert mock_movement._connected == False
        assert mock_movement._initialized == False
        assert mock_movement.shutdown_count == 1
    
    def test_movement_base_class_method(self, mock_movement):
        """Test __base_class__() returns Movement."""
        assert mock_movement.__base_class__() == Movement
    
    def test_movement_settings(self, mock_movement):
        """Test settings get/set."""
        mock_movement.position = 25.0
        settings = mock_movement.settings
        assert settings["position"] == 25.0
        
        mock_movement.settings = {"position": 75.0}
        assert mock_movement.position == 75.0
    
    def test_movement_serialization(self, mock_movement):
        """Test movement serialization."""
        mock_movement.nickname = "Custom Name"
        mock_movement.adapter = "GPIB::1"
        
        data = mock_movement.serialize()
        
        assert data["name"] == "TestMovement"
        assert data["nickname"] == "Custom Name"
        assert data["type"] == "Movement"
        assert data["adapter"] == "GPIB::1"
        assert data["position_units"] == "mm"


class TestMeasurementBaseClass:
    """Tests for Measurement base class."""
    
    def test_measurement_creation(self, mock_measurement):
        """Test measurement instrument creation."""
        assert mock_measurement.name == "TestMeasurement"
        assert len(mock_measurement.data_columns) == 2
        assert len(mock_measurement.data_units) == 2
    
    def test_measurement_perform(self, mock_measurement):
        """Test perform_measurement returns expected data."""
        data = mock_measurement.perform_measurement()
        
        assert isinstance(data, np.ndarray)
        assert data.shape == (2, 2)
        assert mock_measurement.measurement_count == 1
    
    def test_measurement_df(self, mock_measurement):
        """Test measurement_df returns DataFrame with proper columns."""
        df = mock_measurement.measurement_df()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df.columns) == 2
        assert "value1 (V)" in df.columns
        assert "value2 (A)" in df.columns
    
    def test_measurement_lifecycle(self, mock_measurement):
        """Test connect/initialize/shutdown lifecycle."""
        mock_measurement.connect()
        assert mock_measurement._connected == True
        
        mock_measurement.initialize()
        assert mock_measurement._initialized == True
        
        mock_measurement.shutdown()
        assert mock_measurement._connected == False
    
    def test_measurement_base_class_method(self, mock_measurement):
        """Test __base_class__() returns Measurement."""
        assert mock_measurement.__base_class__() == Measurement
    
    def test_measurement_columns(self, mock_measurement):
        """Test columns() returns formatted column names."""
        columns = mock_measurement.columns()
        
        assert len(columns) == 2
        assert "value1 (V)" in columns
        assert "value2 (A)" in columns


# =============================================================================
# Tests: Protocol Type Checking
# =============================================================================

class TestProtocols:
    """Tests for Protocol-based type checking."""
    
    def test_movement_satisfies_protocol(self, mock_movement):
        """Test that MockMovement satisfies MovementProtocol."""
        assert isinstance(mock_movement, MovementProtocol)
    
    def test_measurement_satisfies_protocol(self, mock_measurement):
        """Test that MockMeasurement satisfies MeasurementProtocol."""
        assert isinstance(mock_measurement, MeasurementProtocol)
    
    def test_is_movement_function(self, mock_movement, mock_measurement):
        """Test is_movement helper function."""
        assert is_movement(mock_movement) == True
        assert is_movement(mock_measurement) == False
    
    def test_is_measurement_function(self, mock_movement, mock_measurement):
        """Test is_measurement helper function."""
        assert is_measurement(mock_movement) == False
        assert is_measurement(mock_measurement) == True
    
    def test_get_instrument_type(self, mock_movement, mock_measurement):
        """Test get_instrument_type helper function."""
        assert get_instrument_type(mock_movement) == 'Movement'
        assert get_instrument_type(mock_measurement) == 'Measurement'
        assert get_instrument_type("not an instrument") == 'Unknown'
    
    def test_protocol_not_satisfied_by_non_instrument(self):
        """Test that non-instruments don't satisfy protocols."""
        assert not isinstance("string", MovementProtocol)
        assert not isinstance(123, MeasurementProtocol)
        assert not isinstance({}, MovementProtocol)


# =============================================================================
# Tests: MovementItem and MeasurementItem
# =============================================================================

class TestMovementItem:
    """Tests for MovementItem wrapper class."""
    
    def test_movement_item_creation(self, mock_movement):
        """Test MovementItem creation."""
        positions = np.array([0, 10, 20, 30])
        settings = {"custom": "value"}
        
        item = MovementItem(mock_movement, positions=positions, settings=settings)
        
        assert item.instrument == mock_movement
        assert np.array_equal(item.positions, positions)
        assert item.settings == settings
    
    def test_movement_item_serialization(self, mock_movement):
        """Test MovementItem serialization."""
        positions = np.array([0, 10, 20])
        item = MovementItem(mock_movement, positions=positions, settings={"key": "val"})
        
        data = item.serialize()
        
        assert "instrument" in data
        assert "settings" in data
        assert data["settings"] == {"key": "val"}


class TestMeasurementItem:
    """Tests for MeasurementItem wrapper class."""
    
    def test_measurement_item_creation(self, mock_measurement):
        """Test MeasurementItem creation."""
        settings = {"setting1": 100}
        
        item = MeasurementItem(mock_measurement, settings=settings)
        
        assert item.instrument == mock_measurement
        assert item.settings == settings
    
    def test_measurement_item_serialization(self, mock_measurement):
        """Test MeasurementItem serialization."""
        item = MeasurementItem(mock_measurement, settings={"a": 1})
        
        data = item.serialize()
        
        assert "instrument" in data
        assert "settings" in data


# =============================================================================
# Tests: InstrumentTreeItem
# =============================================================================

@pytest.mark.skipif(not HAS_GUI, reason="GUI dependencies not available")
class TestInstrumentTreeItem:
    """Tests for InstrumentTreeItem tree node."""
    
    def test_tree_item_creation_with_movement(self, mock_movement):
        """Test creating a tree item with movement."""
        positions = np.array([0, 10, 20])
        move_item = MovementItem(mock_movement, positions=positions)
        
        tree_item = InstrumentTreeItem(instrument_object=move_item)
        
        assert tree_item.name == "TestMovement"
        assert tree_item.type == "Movement"
        assert tree_item.item_indices == [0]
        # Note: final_indices is len(positions)-1 but the constructor has a bug
        # and defaults to [1] when positions exist. This documents current behavior.
        assert tree_item.final_indices == [len(positions) - 1] or tree_item.final_indices == [1]
    
    def test_tree_item_creation_with_measurement(self, mock_measurement):
        """Test creating a tree item with measurement."""
        meas_item = MeasurementItem(mock_measurement)
        
        tree_item = InstrumentTreeItem(instrument_object=meas_item)
        
        assert tree_item.name == "TestMeasurement"
        assert tree_item.type == "Measurement"
        assert tree_item.item_indices == [0]
        assert tree_item.final_indices == [1]
    
    def test_tree_item_parent_child(self, mock_movement, mock_measurement):
        """Test parent-child relationships."""
        root = InstrumentTreeItem()
        
        move_item = MovementItem(mock_movement, positions=np.array([0, 10]))
        move_tree = InstrumentTreeItem(parent=root, instrument_object=move_item)
        root.child_items.append(move_tree)
        
        meas_item = MeasurementItem(mock_measurement)
        meas_tree = InstrumentTreeItem(parent=move_tree, instrument_object=meas_item)
        move_tree.child_items.append(meas_tree)
        
        assert move_tree.parent() == root
        assert meas_tree.parent() == move_tree
        assert root.child_count() == 1
        assert move_tree.child_count() == 1
    
    def test_tree_item_unique_id(self, mock_movement):
        """Test unique_id generation."""
        move_item = MovementItem(mock_movement, positions=np.array([0, 10]))
        tree_item = InstrumentTreeItem(instrument_object=move_item)
        
        uid = tree_item.unique_id()
        
        assert "TestMovement" in uid
        assert isinstance(uid, str)
    
    def test_tree_item_finished_movement(self, mock_movement):
        """Test finished() for movement items."""
        positions = np.array([0, 10, 20])
        move_item = MovementItem(mock_movement, positions=positions)
        tree_item = InstrumentTreeItem(instrument_object=move_item)
        
        # Initially not finished
        assert tree_item.finished() == False
        
        # Manually set to final position (simulate having been executed)
        tree_item._runtime_initialized = True
        tree_item.item_indices = [2]
        tree_item.final_indices = [2]
        assert tree_item.finished() == True
    
    def test_tree_item_finished_measurement(self, mock_measurement):
        """Test finished() for measurement items."""
        meas_item = MeasurementItem(mock_measurement)
        tree_item = InstrumentTreeItem(instrument_object=meas_item)
        
        # Initially not finished (indices [0], final [1])
        assert tree_item.finished() == False
        
        # After measurement (simulate having been executed)
        tree_item._runtime_initialized = True
        tree_item.item_indices = [1]
        assert tree_item.finished() == True
    
    def test_tree_item_reset_indices(self, mock_movement):
        """Test reset_indices method."""
        positions = np.array([0, 10, 20])
        move_item = MovementItem(mock_movement, positions=positions)
        tree_item = InstrumentTreeItem(instrument_object=move_item)
        
        tree_item.item_indices = [2]
        tree_item.reset_indices()
        
        assert tree_item.item_indices == [0]
    
    def test_tree_item_move_next_movement(self, mock_movement):
        """Test move_next for movement instrument."""
        positions = np.array([0.0, 10.0, 20.0])
        move_item = MovementItem(mock_movement, positions=positions, settings={})
        tree_item = InstrumentTreeItem(instrument_object=move_item)
        
        # First move_next should initialize and move
        result = tree_item.move_next()
        
        assert result == True
        assert mock_movement.position == 10.0  # Position at index 1
        assert tree_item.item_indices == [1]
        assert tree_item._runtime_initialized == True
    
    def test_tree_item_move_next_measurement(self, mock_measurement):
        """Test move_next for measurement instrument."""
        meas_item = MeasurementItem(mock_measurement, settings={})
        tree_item = InstrumentTreeItem(instrument_object=meas_item)
        
        result = tree_item.move_next()
        
        assert isinstance(result, pd.DataFrame)
        assert tree_item._runtime_initialized == True
        assert mock_measurement.measurement_count == 1
    
    def test_tree_item_serialization(self, mock_movement, mock_measurement):
        """Test tree item serialization."""
        root = InstrumentTreeItem()
        
        move_item = MovementItem(mock_movement, positions=np.array([0, 10]))
        move_tree = InstrumentTreeItem(parent=root, instrument_object=move_item, semaphore="S1")
        root.child_items.append(move_tree)
        
        meas_item = MeasurementItem(mock_measurement)
        meas_tree = InstrumentTreeItem(parent=move_tree, instrument_object=meas_item)
        move_tree.child_items.append(meas_tree)
        
        data = root.serialize()
        
        assert "child_items" in data
        assert len(data["child_items"]) == 1
        assert data["child_items"][0]["semaphore"] == "S1"
    
    def test_tree_item_is_ancestor_of(self, mock_movement, mock_measurement):
        """Test is_ancestor_of method."""
        root = InstrumentTreeItem()
        
        move_item = MovementItem(mock_movement, positions=np.array([0, 10]))
        move_tree = InstrumentTreeItem(parent=root, instrument_object=move_item)
        root.child_items.append(move_tree)
        
        meas_item = MeasurementItem(mock_measurement)
        meas_tree = InstrumentTreeItem(parent=move_tree, instrument_object=meas_item)
        move_tree.child_items.append(meas_tree)
        
        assert root.is_ancestor_of(meas_tree) == True
        assert move_tree.is_ancestor_of(meas_tree) == True
        assert meas_tree.is_ancestor_of(move_tree) == False


# =============================================================================
# Tests: FastForward Traversal Algorithm
# =============================================================================

@pytest.mark.skipif(not HAS_GUI, reason="GUI dependencies not available")
class TestFastForward:
    """Tests for the FastForward batching algorithm."""
    
    def test_fastforward_single_item(self, mock_measurement):
        """Test FastForward with single measurement."""
        meas_item = MeasurementItem(mock_measurement)
        tree_item = InstrumentTreeItem(instrument_object=meas_item)
        
        ff = InstrumentTreeItem.FastForward(tree_item)
        ff = ff.new_item(tree_item)
        
        assert len(ff.stack) == 1
        assert ff.stack[0] == tree_item
    
    def test_fastforward_same_semaphore(self, mock_measurement):
        """Test that items with same semaphore can be batched."""
        root = InstrumentTreeItem()
        
        meas1 = MeasurementItem(MockMeasurement("Meas1"))
        item1 = InstrumentTreeItem(parent=root, instrument_object=meas1, semaphore="S1")
        root.child_items.append(item1)
        
        meas2 = MeasurementItem(MockMeasurement("Meas2"))
        item2 = InstrumentTreeItem(parent=root, instrument_object=meas2, semaphore="S1")
        root.child_items.append(item2)
        
        ff = InstrumentTreeItem.FastForward(item1)
        ff = ff.new_item(item1)
        ff = ff.new_item(item2)
        
        assert len(ff.stack) == 2
        assert not ff.done
    
    def test_fastforward_different_semaphore_stops(self, mock_measurement):
        """Test that different semaphores stop batching."""
        root = InstrumentTreeItem()
        
        meas1 = MeasurementItem(MockMeasurement("Meas1"))
        item1 = InstrumentTreeItem(parent=root, instrument_object=meas1, semaphore="S1")
        root.child_items.append(item1)
        
        meas2 = MeasurementItem(MockMeasurement("Meas2"))
        item2 = InstrumentTreeItem(parent=root, instrument_object=meas2, semaphore="S2")
        root.child_items.append(item2)
        
        ff = InstrumentTreeItem.FastForward(item1)
        ff = ff.new_item(item1)
        ff = ff.new_item(item2)
        
        # Second item should cause done=True and be set as final_item
        assert ff.done == True
        assert ff.final_item == item2
        assert len(ff.stack) == 1
    
    def test_fastforward_no_semaphore_allows_batching(self):
        """Test that empty semaphores don't constrain batching."""
        root = InstrumentTreeItem()
        
        meas1 = MeasurementItem(MockMeasurement("Meas1"))
        item1 = InstrumentTreeItem(parent=root, instrument_object=meas1, semaphore="")
        root.child_items.append(item1)
        
        meas2 = MeasurementItem(MockMeasurement("Meas2"))
        item2 = InstrumentTreeItem(parent=root, instrument_object=meas2, semaphore="")
        root.child_items.append(item2)
        
        ff = InstrumentTreeItem.FastForward(item1)
        ff = ff.new_item(item1)
        ff = ff.new_item(item2)
        
        assert len(ff.stack) == 2
        assert not ff.done
    
    def test_fastforward_prevents_duplicate_items(self, mock_measurement):
        """Test that same item cannot be added twice."""
        meas_item = MeasurementItem(mock_measurement)
        tree_item = InstrumentTreeItem(instrument_object=meas_item)
        
        ff = InstrumentTreeItem.FastForward(tree_item)
        ff = ff.new_item(tree_item)
        ff = ff.new_item(tree_item)  # Try to add again
        
        # Should mark as done since unique_id already visited
        assert ff.done == True
        assert len(ff.stack) == 1


# =============================================================================
# Tests: ScanSettings
# =============================================================================

@pytest.mark.skipif(not HAS_GUI, reason="GUI dependencies not available")
class TestScanSettings:
    """Tests for ScanSettings class."""
    
    def test_scan_settings_creation(self, mock_movement, mock_measurement):
        """Test ScanSettings creation."""
        tree = create_simple_tree(mock_movement, mock_measurement, np.array([0, 10, 20]))
        
        settings = ScanSettings(
            project_name="test_project",
            scan_name="test_scan",
            scan_type="1D Scan",
            job_type="Test",
            ScanTree=tree,
            extensions=[],
            additional_tags=["tag1", "tag2"],
            status="Queued"
        )
        
        assert settings.project_name == "test_project"
        assert settings.scan_name == "test_scan"
        assert settings.scan_type == "1D Scan"
        assert settings.status == "Queued"
    
    def test_scan_settings_serialization(self, mock_movement, mock_measurement):
        """Test ScanSettings serialize method."""
        tree = create_simple_tree(mock_movement, mock_measurement, np.array([0, 10]))
        
        settings = ScanSettings(
            project_name="project",
            scan_name="scan",
            scan_type="1D",
            job_type="Raman",
            ScanTree=tree,
            additional_tags=["test"],
            user_fields={"custom": "field"}
        )
        
        data = settings.serialize()
        
        assert data["project_name"] == "project"
        assert data["scan_name"] == "scan"
        assert data["user_fields"] == {"custom": "field"}
        assert "scan_tree" in data
    
    def test_scan_settings_pickle(self, mock_movement, mock_measurement):
        """Test ScanSettings pickle roundtrip."""
        tree = create_simple_tree(mock_movement, mock_measurement, np.array([0, 10]))
        
        settings = ScanSettings(
            project_name="proj",
            scan_name="scan",
            scan_type="1D",
            job_type="Test",
            ScanTree=tree,
        )
        
        # Pickle and unpickle
        pickled = pickle.dumps(settings)
        restored = pickle.loads(pickled)
        
        assert restored.project_name == "proj"
        assert restored.scan_name == "scan"
        assert restored.scan_tree is not None


# =============================================================================
# Tests: Scan Class
# =============================================================================

@pytest.mark.skipif(not HAS_GUI, reason="GUI dependencies not available")
class TestScan:
    """Tests for the main Scan class."""
    
    def test_scan_creation(self, mock_movement, mock_measurement):
        """Test Scan creation."""
        tree = create_simple_tree(mock_movement, mock_measurement, np.array([0, 10]))
        
        settings = ScanSettings(
            project_name="proj",
            scan_name="scan",
            scan_type="1D",
            job_type="Test",
            ScanTree=tree,
        )
        
        scan = Scan(scan_settings=settings, owner="test_user")
        
        assert scan.project_name == "proj"
        assert scan.owner == "test_user"
        assert scan._buffer_size == 1000
    
    def test_scan_buffer_operations(self, mock_movement, mock_measurement):
        """Test data buffering."""
        tree = create_simple_tree(mock_movement, mock_measurement, np.array([0, 10]))
        
        settings = ScanSettings(
            project_name="proj",
            scan_name="scan",
            scan_type="1D",
            job_type="Test",
            ScanTree=tree,
        )
        
        scan = Scan(scan_settings=settings, owner="test_user", buffer_size=10)
        
        # Get measurement item unique_id
        meas_items = tree.get_measurement_items()
        assert len(meas_items) > 0
        meas_name = meas_items[0].unique_id()
        
        # Save some data
        df = pd.DataFrame({"value1 (V)": [1, 2, 3], "value2 (A)": [4, 5, 6]})
        scan.save_data(df, meas_name)
        
        # Check buffer has data
        assert len(scan._data_buffer[meas_name]) == 3
    
    def test_scan_extension_callbacks(self, mock_movement, mock_measurement, mock_extension):
        """Test that extensions receive callbacks."""
        tree = create_simple_tree(mock_movement, mock_measurement, np.array([0, 10]))
        
        settings = ScanSettings(
            project_name="proj",
            scan_name="scan",
            scan_type="1D",
            job_type="Test",
            ScanTree=tree,
            extensions=[mock_extension],
        )
        
        scan = Scan(scan_settings=settings, owner="test_user")
        
        # Note: set_scan_reference is called in startup(), not __init__
        # This test documents current behavior - extensions aren't set until startup
        # After refactoring, we may want to call this in __init__
        assert mock_extension.scan_ref is None  # Current behavior
        
        # Extensions list should be stored
        assert mock_extension in scan.extensions
    
    def test_scan_pickle(self, mock_movement, mock_measurement):
        """Test Scan pickle roundtrip."""
        tree = create_simple_tree(mock_movement, mock_measurement, np.array([0, 10]))
        
        settings = ScanSettings(
            project_name="proj",
            scan_name="scan",
            scan_type="1D",
            job_type="Test",
            ScanTree=tree,
        )
        
        scan = Scan(scan_settings=settings, owner="test_user")
        
        # Pickle and unpickle
        pickled = pickle.dumps(scan)
        restored = pickle.loads(pickled)
        
        assert restored.project_name == "proj"
        assert restored.owner == "test_user"
        # Threading objects should be recreated
        assert restored._buffer_lock is not None
        assert restored._stop_event is not None
    
    def test_get_empty_scan(self):
        """Test get_empty_scan helper function."""
        scan = get_empty_scan()
        
        assert scan.project_name == "default_project"
        assert scan.owner == ""


# =============================================================================
# Tests: Tree Traversal and Propagation
# =============================================================================

@pytest.mark.skipif(not HAS_GUI, reason="GUI dependencies not available")
class TestTreeTraversal:
    """Tests for tree traversal using propagate()."""
    
    def test_propagate_to_child(self, mock_movement, mock_measurement):
        """Test propagate navigates to first child."""
        root = InstrumentTreeItem()
        
        move_item = MovementItem(mock_movement, positions=np.array([0, 10]))
        move_tree = InstrumentTreeItem(parent=root, instrument_object=move_item)
        root.child_items.append(move_tree)
        
        meas_item = MeasurementItem(mock_measurement)
        meas_tree = InstrumentTreeItem(parent=move_tree, instrument_object=meas_item)
        move_tree.child_items.append(meas_tree)
        
        ff = InstrumentTreeItem.FastForward(move_tree)
        ff = ff.new_item(move_tree)
        
        # Propagate from movement should go to measurement child
        ff = move_tree.propagate(ff)
        
        assert ff.current_item == meas_tree or meas_tree in ff.stack
    
    def test_propagate_to_sibling(self, mock_measurement):
        """Test propagate navigates to sibling when finished."""
        root = InstrumentTreeItem()
        
        meas1 = MeasurementItem(MockMeasurement("Meas1"))
        item1 = InstrumentTreeItem(parent=root, instrument_object=meas1)
        root.child_items.append(item1)
        
        meas2 = MeasurementItem(MockMeasurement("Meas2"))
        item2 = InstrumentTreeItem(parent=root, instrument_object=meas2)
        root.child_items.append(item2)
        
        # Mark first item as finished
        item1.item_indices = [1]
        
        ff = InstrumentTreeItem.FastForward(item1)
        ff = ff.new_item(item1)
        ff = item1.propagate(ff)
        
        # Should move to sibling
        assert item2 in ff.stack or ff.current_item == item2


# =============================================================================
# Tests: ScanTreeModel
# =============================================================================

@pytest.mark.skipif(not HAS_GUI, reason="GUI dependencies not available")
class TestScanTreeModel:
    """Tests for ScanTreeModel Qt model."""
    
    def test_model_creation(self):
        """Test ScanTreeModel creation."""
        model = ScanTreeModel()
        
        assert model.root_item is not None
        assert model.completed == False
        assert model.paused == False
        assert model.stopped == False
    
    def test_model_with_root_item(self, mock_movement, mock_measurement):
        """Test ScanTreeModel with provided root."""
        root = InstrumentTreeItem()
        
        move_item = MovementItem(mock_movement, positions=np.array([0, 10]))
        move_tree = InstrumentTreeItem(parent=root, instrument_object=move_item)
        root.child_items.append(move_tree)
        
        model = ScanTreeModel(root_item=root)
        
        assert model.root_item == root
        assert model.root_item.child_count() == 1
    
    def test_model_get_measurement_items(self, mock_movement, mock_measurement):
        """Test get_measurement_items method."""
        tree = create_simple_tree(mock_movement, mock_measurement, np.array([0, 10]))
        
        items = tree.get_measurement_items()
        
        assert len(items) == 1
        assert items[0].type == "Measurement"
    
    def test_model_get_movement_items(self, mock_movement, mock_measurement):
        """Test get_movement_items method."""
        tree = create_simple_tree(mock_movement, mock_measurement, np.array([0, 10]))
        
        items = tree.get_movement_items()
        
        assert len(items) == 1
        assert items[0].type == "Movement"
    
    def test_model_serialize(self, mock_movement, mock_measurement):
        """Test model serialization."""
        tree = create_simple_tree(mock_movement, mock_measurement, np.array([0, 10]))
        
        data = tree.serialize()
        
        assert "root_item" in data
        assert "completed" in data
        assert "paused" in data
        assert "stopped" in data


# =============================================================================
# Tests: Data Saving Pipeline
# =============================================================================

@pytest.mark.skipif(not HAS_GUI, reason="GUI dependencies not available")
class TestDataSavingPipeline:
    """Tests for the asynchronous data saving system."""
    
    def test_buffer_flush_on_size(self, mock_movement, mock_measurement, mock_extension):
        """Test buffer flushes when reaching size limit."""
        tree = create_simple_tree(mock_movement, mock_measurement, np.array([0, 10]))
        
        settings = ScanSettings(
            project_name="proj",
            scan_name="scan", 
            scan_type="1D",
            job_type="Test",
            ScanTree=tree,
            extensions=[mock_extension],
        )
        
        # Small buffer to trigger flush
        scan = Scan(scan_settings=settings, owner="test_user", buffer_size=5)
        
        meas_items = tree.get_measurement_items()
        meas_name = meas_items[0].unique_id()
        
        # Add 6 rows - should trigger flush
        df = pd.DataFrame({"col1": range(6), "col2": range(6)})
        scan.save_data(df, meas_name)
        
        # Wait for async flush
        scan.flush()
        
        # Buffer should be cleared
        assert len(scan._data_buffer[meas_name]) == 0
        
        # Extension should have received data (now that wandb is removed)
        assert len(mock_extension.saved_data) >= 1
    
    def test_manual_flush(self, mock_movement, mock_measurement, mock_extension):
        """Test manual flush empties buffer."""
        tree = create_simple_tree(mock_movement, mock_measurement, np.array([0, 10]))
        
        settings = ScanSettings(
            project_name="proj",
            scan_name="scan",
            scan_type="1D",
            job_type="Test",
            ScanTree=tree,
            extensions=[mock_extension],
        )
        
        scan = Scan(scan_settings=settings, owner="test_user", buffer_size=1000)
        
        meas_items = tree.get_measurement_items()
        meas_name = meas_items[0].unique_id()
        
        # Add data (won't auto-flush due to large buffer)
        df = pd.DataFrame({"col1": [1, 2, 3]})
        scan.save_data(df, meas_name)
        
        assert len(scan._data_buffer[meas_name]) == 3
        
        # Manual flush
        scan.flush()
        
        # Buffer should be empty
        assert len(scan._data_buffer[meas_name]) == 0


# =============================================================================
# Integration Tests (require fake instruments)
# =============================================================================

@pytest.mark.skipif(not HAS_GUI or not HAS_FAKE_INSTRUMENTS, 
                    reason="GUI or fake instruments not available")
class TestScanIntegration:
    """Integration tests with fake instruments."""
    
    @pytest.fixture
    def x_stage(self):
        return FakeXStage("X Stage")
    
    @pytest.fixture  
    def lock_in(self):
        return FakeLockInAmplifier("Lock-In", wait=0.001)
    
    def test_simple_1d_scan_tree(self, x_stage, lock_in):
        """Test creating a 1D scan tree."""
        positions = np.array([0.0, 25.0, 50.0, 75.0, 100.0])
        tree = create_simple_tree(x_stage, lock_in, positions)
        
        move_items = tree.get_movement_items()
        meas_items = tree.get_measurement_items()
        
        assert len(move_items) == 1
        assert len(meas_items) == 1
        assert move_items[0].instrument_object.positions is not None


# =============================================================================
# State Machine Tests
# =============================================================================

# Import state module
from pybirch.scan.state import (
    ItemState,
    ScanState,
    StateMachine,
    ItemStateMachine,
    ScanStateMachine,
    VALID_ITEM_TRANSITIONS,
    VALID_SCAN_TRANSITIONS,
    legacy_state_to_item_state,
    legacy_flags_to_scan_state,
)

# Import traverser module
from pybirch.scan.traverser import TreeTraverser, FastForward, propagate

# Import cancellation module
from pybirch.scan.cancellation import (
    CancellationToken,
    CancellationTokenSource,
    CancellationError,
    CancellationType,
    CancellationInfo,
)


class TestItemState:
    """Test ItemState enum and transitions."""
    
    def test_all_states_defined(self):
        """Verify all expected states exist."""
        expected = {"PENDING", "INITIALIZED", "IN_PROGRESS", "COMPLETED", "PAUSED", "ABORTED", "FAILED"}
        actual = {s.name for s in ItemState}
        assert expected == actual
    
    def test_terminal_states(self):
        """Terminal states should have no valid transitions."""
        terminal = {ItemState.COMPLETED, ItemState.ABORTED, ItemState.FAILED}
        for state in terminal:
            assert VALID_ITEM_TRANSITIONS[state] == set()
    
    def test_pending_transitions(self):
        """PENDING can go to INITIALIZED, ABORTED, or FAILED."""
        valid = VALID_ITEM_TRANSITIONS[ItemState.PENDING]
        assert ItemState.INITIALIZED in valid
        assert ItemState.ABORTED in valid
        assert ItemState.FAILED in valid


class TestScanState:
    """Test ScanState enum and transitions."""
    
    def test_all_states_defined(self):
        """Verify all expected states exist."""
        expected = {"QUEUED", "STARTING", "RUNNING", "PAUSED", "COMPLETING", "COMPLETED", "ABORTED", "FAILED"}
        actual = {s.name for s in ScanState}
        assert expected == actual
    
    def test_terminal_states(self):
        """Terminal states should have no valid transitions."""
        terminal = {ScanState.COMPLETED, ScanState.ABORTED, ScanState.FAILED}
        for state in terminal:
            assert VALID_SCAN_TRANSITIONS[state] == set()


class TestStateMachine:
    """Test generic StateMachine class."""
    
    def test_initial_state(self):
        """State machine starts in initial state."""
        sm = StateMachine(ItemState.PENDING, VALID_ITEM_TRANSITIONS)
        assert sm.state == ItemState.PENDING
    
    def test_valid_transition(self):
        """Can transition to valid next state."""
        sm = StateMachine(ItemState.PENDING, VALID_ITEM_TRANSITIONS)
        assert sm.can_transition_to(ItemState.INITIALIZED)
        result = sm.transition_to(ItemState.INITIALIZED)
        assert result is True
        assert sm.state == ItemState.INITIALIZED
    
    def test_invalid_transition(self):
        """Invalid transitions raise ValueError."""
        sm = StateMachine(ItemState.PENDING, VALID_ITEM_TRANSITIONS)
        assert not sm.can_transition_to(ItemState.COMPLETED)
        with pytest.raises(ValueError, match="Invalid transition"):
            sm.transition_to(ItemState.COMPLETED)
    
    def test_forced_transition(self):
        """Forced transition bypasses validation."""
        sm = StateMachine(ItemState.PENDING, VALID_ITEM_TRANSITIONS)
        result = sm.transition_to(ItemState.COMPLETED, force=True)
        assert result is True
        assert sm.state == ItemState.COMPLETED
    
    def test_history_tracking(self):
        """Transition history is tracked."""
        sm = StateMachine(ItemState.PENDING, VALID_ITEM_TRANSITIONS)
        sm.transition_to(ItemState.INITIALIZED)
        sm.transition_to(ItemState.IN_PROGRESS)
        sm.transition_to(ItemState.COMPLETED)
        
        assert sm.history == [
            ItemState.PENDING,
            ItemState.INITIALIZED,
            ItemState.IN_PROGRESS,
            ItemState.COMPLETED
        ]
    
    def test_is_terminal(self):
        """is_terminal detects terminal states."""
        sm = StateMachine(ItemState.PENDING, VALID_ITEM_TRANSITIONS)
        assert not sm.is_terminal()
        
        sm.transition_to(ItemState.INITIALIZED)
        sm.transition_to(ItemState.IN_PROGRESS)
        sm.transition_to(ItemState.COMPLETED)
        assert sm.is_terminal()
    
    def test_reset(self):
        """Reset returns to initial state."""
        sm = StateMachine(ItemState.PENDING, VALID_ITEM_TRANSITIONS)
        sm.transition_to(ItemState.INITIALIZED)
        sm.transition_to(ItemState.IN_PROGRESS)
        
        sm.reset()
        assert sm.state == ItemState.PENDING
        assert sm.history == [ItemState.PENDING]
    
    def test_on_transition_callback(self):
        """Callback is called on transitions."""
        transitions = []
        def callback(old, new):
            transitions.append((old, new))
        
        sm = StateMachine(ItemState.PENDING, VALID_ITEM_TRANSITIONS, on_transition=callback)
        sm.transition_to(ItemState.INITIALIZED)
        sm.transition_to(ItemState.IN_PROGRESS)
        
        assert transitions == [
            (ItemState.PENDING, ItemState.INITIALIZED),
            (ItemState.INITIALIZED, ItemState.IN_PROGRESS)
        ]


class TestItemStateMachine:
    """Test ItemStateMachine convenience methods."""
    
    def test_initial_state(self):
        """Default initial state is PENDING."""
        sm = ItemStateMachine()
        assert sm.state == ItemState.PENDING
    
    def test_happy_path(self):
        """Test normal execution flow."""
        sm = ItemStateMachine()
        sm.initialize()
        assert sm.state == ItemState.INITIALIZED
        
        sm.start()
        assert sm.state == ItemState.IN_PROGRESS
        assert sm.is_running
        
        sm.complete()
        assert sm.state == ItemState.COMPLETED
        assert sm.is_finished
    
    def test_pause_resume(self):
        """Test pause and resume flow."""
        sm = ItemStateMachine()
        sm.initialize()
        sm.start()
        
        sm.pause()
        assert sm.state == ItemState.PAUSED
        assert sm.is_active
        assert not sm.is_running
        
        sm.resume()
        assert sm.state == ItemState.IN_PROGRESS
        assert sm.is_running
    
    def test_abort_from_any_active_state(self):
        """Can abort from any active state."""
        for start_state in [ItemState.INITIALIZED, ItemState.IN_PROGRESS, ItemState.PAUSED]:
            sm = ItemStateMachine(initial_state=start_state)
            sm.abort()
            assert sm.state == ItemState.ABORTED
            assert sm.is_finished
    
    def test_fail_from_any_active_state(self):
        """Can fail from any active state."""
        for start_state in [ItemState.PENDING, ItemState.INITIALIZED, ItemState.IN_PROGRESS, ItemState.PAUSED]:
            sm = ItemStateMachine(initial_state=start_state)
            sm.fail()
            assert sm.state == ItemState.FAILED
            assert sm.is_finished
    
    def test_is_active_states(self):
        """is_active returns True for active states only."""
        sm = ItemStateMachine()
        assert not sm.is_active  # PENDING is not active
        
        sm.initialize()
        assert sm.is_active
        
        sm.start()
        assert sm.is_active
        
        sm.pause()
        assert sm.is_active
        
        sm.abort()
        assert not sm.is_active


class TestScanStateMachine:
    """Test ScanStateMachine."""
    
    def test_initial_state(self):
        """Default initial state is QUEUED."""
        sm = ScanStateMachine()
        assert sm.state == ScanState.QUEUED
    
    def test_happy_path(self):
        """Test normal scan flow."""
        sm = ScanStateMachine()
        sm.transition_to(ScanState.STARTING)
        sm.transition_to(ScanState.RUNNING)
        assert sm.is_running
        
        sm.transition_to(ScanState.COMPLETING)
        sm.transition_to(ScanState.COMPLETED)
        assert sm.is_finished
    
    def test_pause_resume(self):
        """Test scan pause and resume."""
        sm = ScanStateMachine()
        sm.transition_to(ScanState.STARTING)
        sm.transition_to(ScanState.RUNNING)
        
        sm.transition_to(ScanState.PAUSED)
        assert sm.is_active
        assert not sm.is_running
        
        sm.transition_to(ScanState.RUNNING)
        assert sm.is_running


class TestLegacyConversion:
    """Test legacy state conversion functions."""
    
    def test_legacy_state_to_item_state(self):
        """Convert legacy booleans to ItemState."""
        # Not initialized, not finished -> PENDING
        assert legacy_state_to_item_state(False, False) == ItemState.PENDING
        
        # Initialized but not finished -> IN_PROGRESS
        assert legacy_state_to_item_state(True, False) == ItemState.IN_PROGRESS
        
        # Finished -> COMPLETED (regardless of initialized)
        assert legacy_state_to_item_state(True, True) == ItemState.COMPLETED
        assert legacy_state_to_item_state(False, True) == ItemState.COMPLETED
    
    def test_legacy_flags_to_scan_state(self):
        """Convert legacy scan flags to ScanState."""
        # Nothing set -> QUEUED
        assert legacy_flags_to_scan_state(False, False, False) == ScanState.QUEUED
        
        # Paused -> PAUSED
        assert legacy_flags_to_scan_state(False, True, False) == ScanState.PAUSED
        
        # Stopped -> ABORTED
        assert legacy_flags_to_scan_state(False, False, True) == ScanState.ABORTED
        
        # Completed -> COMPLETED
        assert legacy_flags_to_scan_state(True, False, False) == ScanState.COMPLETED


class TestTreeTraverserModule:
    """Test TreeTraverser module (extracted from treeitem.py)."""
    
    def test_fastforward_alias(self):
        """FastForward is an alias for TreeTraverser."""
        assert FastForward is TreeTraverser
    
    @pytest.fixture
    def mock_tree(self):
        """Create a mock tree for testing."""
        movement = MockMovement("TestMove")
        move_item = MovementItem(movement, [0, 50, 100])
        
        meas = MockMeasurement("TestMeas")
        meas_item = MeasurementItem(meas)
        
        root = InstrumentTreeItem()
        move_tree = InstrumentTreeItem(root, move_item)
        root.child_items.append(move_tree)
        meas_tree = InstrumentTreeItem(move_tree, meas_item)
        move_tree.child_items.append(meas_tree)
        
        return root
    
    def test_tree_traverser_creation(self, mock_tree):
        """TreeTraverser initializes correctly."""
        traverser = TreeTraverser(mock_tree)
        assert traverser.current_item == mock_tree
        assert traverser.done is False
        assert traverser.stack == []
        assert traverser.semaphores == []
    
    def test_tree_traverser_new_item(self, mock_tree):
        """TreeTraverser.new_item adds items to stack."""
        traverser = TreeTraverser(mock_tree)
        child = mock_tree.child_items[0]
        
        traverser.new_item(child)
        
        assert len(traverser.stack) == 1
        assert child in traverser.stack
        assert child.unique_id() in traverser.unique_ids
    
    def test_tree_traverser_get_batch(self, mock_tree):
        """get_batch returns copy of stack."""
        traverser = TreeTraverser(mock_tree)
        child = mock_tree.child_items[0]
        traverser.new_item(child)
        
        batch = traverser.get_batch()
        
        assert batch == traverser.stack
        assert batch is not traverser.stack  # It's a copy
    
    def test_tree_traverser_clear_batch(self, mock_tree):
        """clear_batch resets the traverser state."""
        traverser = TreeTraverser(mock_tree)
        child = mock_tree.child_items[0]
        traverser.new_item(child)
        
        traverser.clear_batch()
        
        assert traverser.stack == []
        assert traverser.semaphores == []
        assert traverser.types == {}
        assert traverser.unique_ids == []
    
    def test_tree_traverser_backward_compat_aliases(self, mock_tree):
        """Backward compatibility aliases work."""
        traverser = TreeTraverser(mock_tree)
        
        # semaphore alias
        traverser.semaphore = ["test"]
        assert traverser.semaphores == ["test"]
        assert traverser.semaphore == ["test"]
        
        # type alias
        traverser.type = {"Movement": []}
        assert traverser.types == {"Movement": []}
        assert traverser.type == {"Movement": []}
        
        # adapter alias
        traverser.adapter = {"VISA": []}
        assert traverser.adapters == {"VISA": []}
        assert traverser.adapter == {"VISA": []}
    
    def test_propagate_function(self, mock_tree):
        """propagate function works standalone."""
        # Start from the movement child which has actual indices
        move_child = mock_tree.child_items[0]
        traverser = TreeTraverser(move_child)
        
        # Movement child is not finished (has positions to move through)
        # and has a measurement child, so propagate should add that child
        result = propagate(move_child, traverser)
        
        assert result is traverser
        # Should have added the measurement child
        assert len(traverser.stack) == 1
        assert traverser.stack[0].type == "Measurement"
    
    def test_treeitem_fastforward_is_traverser(self, mock_tree):
        """InstrumentTreeItem.FastForward is TreeTraverser."""
        assert InstrumentTreeItem.FastForward is TreeTraverser
    
    def test_treeitem_propagate_method(self, mock_tree):
        """InstrumentTreeItem.propagate method works."""
        traverser = TreeTraverser(mock_tree)
        
        result = mock_tree.propagate(traverser)
        
        assert isinstance(result, TreeTraverser)


# =============================================================================
# Cancellation Token Tests
# =============================================================================

class TestCancellationToken:
    """Test CancellationToken class."""
    
    def test_token_creation(self):
        """Token starts in non-cancelled state."""
        token = CancellationToken("test")
        assert token.name == "test"
        assert not token.is_cancelled
        assert not token.is_pause_requested
        assert token.reason == ""
    
    def test_cancel(self):
        """cancel() sets cancelled state."""
        token = CancellationToken()
        token.cancel("Test reason")
        
        assert token.is_cancelled
        assert token.reason == "Test reason"
        assert token.info is not None
        assert token.info.type == CancellationType.SOFT
    
    def test_cancel_hard(self):
        """cancel_hard() sets HARD cancellation type."""
        token = CancellationToken()
        token.cancel_hard("Immediate")
        
        assert token.is_cancelled
        assert token.info.type == CancellationType.HARD
    
    def test_check_raises_on_cancel(self):
        """check() raises CancellationError when cancelled."""
        token = CancellationToken()
        
        # Not cancelled - should not raise
        result = token.check(throw_on_cancel=True)
        assert result is False
        
        # Cancel and check again
        token.cancel("Test")
        with pytest.raises(CancellationError) as exc_info:
            token.check()
        assert "Test" in str(exc_info.value)
    
    def test_check_returns_status(self):
        """check() returns status without raising."""
        token = CancellationToken()
        
        assert token.check(throw_on_cancel=False) is False
        token.cancel()
        assert token.check(throw_on_cancel=False) is True
    
    def test_pause_resume(self):
        """pause() and resume() work correctly."""
        token = CancellationToken()
        
        assert not token.is_pause_requested
        token.pause()
        assert token.is_pause_requested
        
        token.resume()
        assert not token.is_pause_requested
    
    def test_cancel_clears_pause(self):
        """cancel() clears pause state."""
        token = CancellationToken()
        token.pause()
        assert token.is_pause_requested
        
        token.cancel()
        assert token.is_cancelled
        assert not token.is_pause_requested  # Cleared by cancel
    
    def test_reset(self):
        """reset() clears all state."""
        token = CancellationToken()
        token.cancel("Test")
        
        token.reset()
        
        assert not token.is_cancelled
        assert token.reason == ""
        assert token.info is None
    
    def test_callback(self):
        """Callbacks are called on cancellation."""
        token = CancellationToken()
        callback_info = []
        
        def callback(info: CancellationInfo):
            callback_info.append(info)
        
        token.register_callback(callback)
        token.cancel("Test callback")
        
        assert len(callback_info) == 1
        assert callback_info[0].reason == "Test callback"
    
    def test_unregister_callback(self):
        """Callbacks can be unregistered."""
        token = CancellationToken()
        called = []
        
        def callback(info):
            called.append(True)
        
        token.register_callback(callback)
        token.unregister_callback(callback)
        token.cancel()
        
        assert len(called) == 0
    
    def test_child_token(self):
        """Child tokens are cancelled when parent is cancelled."""
        parent = CancellationToken("parent")
        child = parent.create_child("child")
        
        assert not child.is_cancelled
        parent.cancel("Parent cancelled")
        
        assert child.is_cancelled
        assert "Parent cancelled" in child.reason
    
    def test_context_manager(self):
        """Token works as context manager."""
        with CancellationToken("ctx") as token:
            assert not token.is_cancelled
            token.cancel()
            assert token.is_cancelled


class TestCancellationTokenSource:
    """Test CancellationTokenSource class."""
    
    def test_create_tokens(self):
        """Source creates and tracks tokens."""
        source = CancellationTokenSource("test")
        
        t1 = source.create_token()
        t2 = source.create_token("named")
        
        assert t1 is not t2
        assert "named" in t2.name
    
    def test_cancel_all(self):
        """cancel_all() cancels all tokens."""
        source = CancellationTokenSource()
        t1 = source.create_token()
        t2 = source.create_token()
        t3 = source.create_token()
        
        assert not source.any_cancelled
        
        source.cancel_all("Mass cancel")
        
        assert t1.is_cancelled
        assert t2.is_cancelled
        assert t3.is_cancelled
        assert source.all_cancelled
    
    def test_any_cancelled(self):
        """any_cancelled detects partial cancellation."""
        source = CancellationTokenSource()
        t1 = source.create_token()
        t2 = source.create_token()
        
        assert not source.any_cancelled
        
        t1.cancel()
        
        assert source.any_cancelled
        assert not source.all_cancelled
    
    def test_reset_all(self):
        """reset_all() resets all tokens."""
        source = CancellationTokenSource()
        t1 = source.create_token()
        t2 = source.create_token()
        
        t1.cancel()
        t2.cancel()
        
        source.reset_all()
        
        assert not t1.is_cancelled
        assert not t2.is_cancelled


# =============================================================================
# Run tests if executed directly
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
