"""
PyBirch Test Configuration

Shared fixtures and configuration for all tests.
"""

import sys
import os
import tempfile
import logging
import pytest
from unittest import mock

# Ensure project root is in path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# =============================================================================
# Shared Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def project_root_dir():
    """Get the project root directory."""
    return project_root


@pytest.fixture
def temp_directory():
    """Create a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_sample_dir(temp_directory):
    """Create a temporary sample directory."""
    return temp_directory


@pytest.fixture
def mock_wandb():
    """Mock wandb to avoid actual logging during tests."""
    with mock.patch('wandb.init') as mock_init, \
         mock.patch('wandb.login') as mock_login, \
         mock.patch('wandb.finish') as mock_finish, \
         mock.patch('wandb.Table') as mock_table:
        
        # Setup mock return values
        mock_run = mock.MagicMock()
        mock_init.return_value = mock_run
        
        yield {
            'init': mock_init,
            'login': mock_login,
            'finish': mock_finish,
            'Table': mock_table,
            'run': mock_run
        }


# =============================================================================
# Instrument Fixtures
# =============================================================================

@pytest.fixture
def fake_lock_in():
    """Create a FakeLockInAmplifier instance."""
    from pybirch.setups.fake_setup.lock_in_amplifier.lock_in_amplifier import FakeLockInAmplifier
    return FakeLockInAmplifier(name="Test Lock-In", wait=0.0)


@pytest.fixture
def fake_voltmeter():
    """Create a VoltageMeterMeasurement instance."""
    from pybirch.setups.fake_setup.multimeter.multimeter import VoltageMeterMeasurement
    return VoltageMeterMeasurement(name="Test Voltmeter")


@pytest.fixture
def fake_current_source():
    """Create a CurrentSourceMovement instance."""
    from pybirch.setups.fake_setup.multimeter.multimeter import CurrentSourceMovement
    return CurrentSourceMovement(name="Test Current Source")


@pytest.fixture
def fake_x_stage():
    """Create a FakeXStage instance."""
    from pybirch.setups.fake_setup.stage_controller.stage_controller import FakeXStage
    return FakeXStage(name="Test X Stage", use_shared_controller=False)


@pytest.fixture
def fake_y_stage():
    """Create a FakeYStage instance."""
    from pybirch.setups.fake_setup.stage_controller.stage_controller import FakeYStage
    return FakeYStage(name="Test Y Stage", use_shared_controller=False)


@pytest.fixture
def fake_z_stage():
    """Create a FakeZStage instance."""
    from pybirch.setups.fake_setup.stage_controller.stage_controller import FakeZStage
    return FakeZStage(name="Test Z Stage", use_shared_controller=False)


@pytest.fixture
def fake_spectrometer():
    """Create a FakeSpectrometer instance."""
    from pybirch.setups.fake_setup.spectrometer.spectrometer import FakeSpectrometer
    return FakeSpectrometer(name="Test Spectrometer", wait=0.0)


# =============================================================================
# Queue Fixtures
# =============================================================================

@pytest.fixture
def empty_queue():
    """Create an empty Queue instance."""
    from pybirch.queue.queue import Queue
    return Queue(QID="test_queue")


@pytest.fixture
def queue_with_logging(empty_queue):
    """Create a queue with log collection enabled."""
    logs = []
    
    def log_callback(entry):
        logs.append(entry)
    
    empty_queue.add_log_callback(log_callback)
    empty_queue._test_logs = logs
    
    return empty_queue


# =============================================================================
# Skip Markers
# =============================================================================

def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "gui: marks tests that require GUI dependencies"
    )


# =============================================================================
# Test Session Hooks
# =============================================================================

def pytest_sessionstart(session):
    """Called at the start of the test session."""
    logging.info("=" * 60)
    logging.info("PyBirch Test Suite Starting")
    logging.info("=" * 60)


def pytest_sessionfinish(session, exitstatus):
    """Called at the end of the test session."""
    logging.info("=" * 60)
    logging.info(f"PyBirch Test Suite Finished (exit status: {exitstatus})")
    logging.info("=" * 60)


# =============================================================================
# GUI Availability Check
# =============================================================================

@pytest.fixture(scope="session")
def gui_available():
    """Check if GUI dependencies are available."""
    try:
        from GUI.widgets.scan_tree.treemodel import ScanTreeModel
        from GUI.widgets.scan_tree.treeitem import InstrumentTreeItem
        return True
    except ImportError:
        return False


def skip_if_no_gui(gui_available):
    """Skip test if GUI dependencies are not available."""
    if not gui_available:
        pytest.skip("GUI dependencies not available")
