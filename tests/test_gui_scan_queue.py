"""
PyBirch GUI Tests for Scan and Queue Building

Unit tests for the Qt UI components that build and manage scans and queues.
Uses pytest-qt for Qt widget testing.
"""

import sys
import os
import pytest
from unittest import mock
from typing import Optional, List

# Ensure project root is in path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure Qt API before importing any Qt modules
os.environ.setdefault('QT_API', 'pyside6')

# Skip entire module if PySide6 is not available
pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QTreeWidgetItem

# Import pybirch scan/queue components
from pybirch.scan.scan import Scan, get_empty_scan, ScanSettings
from GUI.widgets.scan_tree.treemodel import ScanTreeModel
from pybirch.queue.queue import Queue, QueueState, ScanState


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def qapp():
    """Create the QApplication instance for the test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    # Don't close the app - pytest-qt manages this


@pytest.fixture
def scan_tree_mainwindow(qapp, qtbot):
    """Create a ScanTreeWidget instance for testing."""
    from GUI.widgets.scan_tree.mainwindow import ScanTreeWidget
    window = ScanTreeWidget()
    qtbot.addWidget(window)
    return window


@pytest.fixture
def scan_page(qapp, qtbot):
    """Create a ScanPage instance for testing."""
    from GUI.windows.scan_page import ScanPage
    page = ScanPage()
    qtbot.addWidget(page)
    return page


@pytest.fixture
def scan_page_with_scan(qapp, qtbot):
    """Create a ScanPage with a pre-configured scan."""
    from GUI.windows.scan_page import ScanPage
    
    scan_settings = ScanSettings(
        project_name="test_project",
        scan_name="test_scan",
        scan_type="measurement",
        job_type="research",
        ScanTree=ScanTreeModel(),
        additional_tags=["test"],
        status="Queued"
    )
    scan = Scan(scan_settings=scan_settings, owner="test_user", sample_id="sample_001")
    
    page = ScanPage(scan=scan)
    qtbot.addWidget(page)
    return page


@pytest.fixture
def queue_page(qapp, qtbot):
    """Create a QueuePage instance for testing."""
    from GUI.windows.queue_page import QueuePage
    
    queue = Queue("test_queue")
    page = QueuePage(queue=queue)
    qtbot.addWidget(page)
    return page


@pytest.fixture
def sample_queue_with_scans(qapp, qtbot):
    """Create a QueuePage with pre-populated scans."""
    from GUI.windows.queue_page import QueuePage
    
    queue = Queue("test_queue")
    
    # Add some test scans
    for i in range(3):
        scan_settings = ScanSettings(
            project_name=f"project_{i}",
            scan_name=f"scan_{i}",
            scan_type="measurement",
            job_type="research",
            ScanTree=ScanTreeModel(),
            additional_tags=[],
            status="Queued"
        )
        scan = Scan(scan_settings=scan_settings, owner="test", sample_id=f"sample_{i}")
        queue.enqueue(scan)
    
    page = QueuePage(queue=queue)
    qtbot.addWidget(page)
    return page


# =============================================================================
# ScanPage Tests
# =============================================================================

class TestScanPage:
    """Tests for the ScanPage widget."""
    
    def test_scan_page_creation(self, scan_page):
        """Test that ScanPage can be created with default settings."""
        assert scan_page is not None
        assert scan_page.scan is not None
        assert scan_page.scan_tree is not None
        assert scan_page.title_bar is not None
    
    def test_scan_page_with_custom_scan(self, scan_page_with_scan):
        """Test that ScanPage correctly displays a custom scan."""
        page = scan_page_with_scan
        
        # Check scan properties
        assert page.scan.scan_settings.scan_name == "test_scan"
        assert page.scan.scan_settings.project_name == "test_project"
        assert page.scan.sample_id == "sample_001"
        assert page.scan.owner == "test_user"
    
    def test_get_empty_scan_creates_valid_scan(self):
        """Test that get_empty_scan creates a properly initialized scan."""
        scan = get_empty_scan()
        
        assert scan is not None
        assert scan.scan_settings is not None
        assert scan.scan_settings.scan_name == "default_scan"
        assert scan.scan_settings.project_name == "default_project"
        assert scan.sample_id is None  # Should be None by default
    
    def test_scan_tree_state_save_and_load(self, scan_page, qtbot):
        """Test that tree state can be saved and loaded correctly."""
        page = scan_page
        
        # Get initial tree state (should be empty or default)
        initial_state = page.scan_tree.save_tree_state()
        
        # Verify tree state is a list
        assert isinstance(initial_state, list)
    
    def test_save_tree_to_scan(self, scan_page_with_scan, qtbot):
        """Test that save_tree_to_scan persists tree state to scan object."""
        page = scan_page_with_scan
        
        # Force save
        page.save_tree_to_scan()
        
        # Verify tree_state is updated on the scan
        assert hasattr(page.scan, 'tree_state')
    
    def test_movement_instruments_initially_empty(self, scan_page):
        """Test that movement instruments list is initially empty."""
        assert scan_page.current_movement_instruments == []
    
    def test_scan_info_changed_signal_exists(self, scan_page):
        """Test that scan_info_changed signal exists."""
        assert hasattr(scan_page, 'scan_info_changed')


# =============================================================================
# ScanTreeMainWindow Tests  
# =============================================================================

class TestScanTreeMainWindow:
    """Tests for the ScanTreeMainWindow widget."""
    
    def test_scan_tree_creation(self, scan_tree_mainwindow):
        """Test that ScanTreeMainWindow can be created."""
        assert scan_tree_mainwindow is not None
        assert scan_tree_mainwindow.view is not None
    
    def test_save_tree_state_empty(self, scan_tree_mainwindow):
        """Test save_tree_state with empty tree."""
        state = scan_tree_mainwindow.save_tree_state()
        assert isinstance(state, list)
        # Empty tree should have no items
        assert len(state) == 0
    
    def test_add_and_save_tree_item(self, scan_tree_mainwindow, qtbot):
        """Test adding a tree item and saving state."""
        window = scan_tree_mainwindow
        
        # Add a tree item
        item = QTreeWidgetItem(window.view)
        item.setText(0, "Test Instrument")
        item.setText(1, "Movement")
        item.setCheckState(0, Qt.CheckState.Checked)
        
        # Save state
        state = window.save_tree_state()
        
        assert len(state) == 1
        assert state[0]['name'] == "Test Instrument"
        assert state[0]['type'] == "Movement"
        assert state[0]['check_state'] == 2  # Checked
    
    def test_save_and_load_tree_state_roundtrip(self, scan_tree_mainwindow, qtbot):
        """Test that tree state survives a save/load roundtrip."""
        window = scan_tree_mainwindow
        
        # Add items
        parent = QTreeWidgetItem(window.view)
        parent.setText(0, "Parent")
        parent.setText(1, "Group")
        parent.setCheckState(0, Qt.CheckState.Checked)
        
        child = QTreeWidgetItem(parent)
        child.setText(0, "Child")
        child.setText(1, "Measurement")
        child.setCheckState(0, Qt.CheckState.Unchecked)
        
        # Save state
        state = window.save_tree_state()
        
        # Clear and reload
        window.view.clear()
        assert window.view.topLevelItemCount() == 0
        
        window.load_tree_state(state)
        
        # Verify structure restored
        assert window.view.topLevelItemCount() == 1
        restored_parent = window.view.topLevelItem(0)
        assert restored_parent.text(0) == "Parent"
        assert restored_parent.childCount() == 1
        restored_child = restored_parent.child(0)
        assert restored_child.text(0) == "Child"
    
    def test_tree_check_states_preserved(self, scan_tree_mainwindow, qtbot):
        """Test that check states are preserved in save/load."""
        window = scan_tree_mainwindow
        
        # Add items with different check states
        checked = QTreeWidgetItem(window.view)
        checked.setText(0, "Checked")
        checked.setCheckState(0, Qt.CheckState.Checked)
        
        unchecked = QTreeWidgetItem(window.view)
        unchecked.setText(0, "Unchecked")
        unchecked.setCheckState(0, Qt.CheckState.Unchecked)
        
        partial = QTreeWidgetItem(window.view)
        partial.setText(0, "Partial")
        partial.setCheckState(0, Qt.CheckState.PartiallyChecked)
        
        state = window.save_tree_state()
        
        assert state[0]['check_state'] == 2  # Checked
        assert state[1]['check_state'] == 0  # Unchecked
        assert state[2]['check_state'] == 1  # PartiallyChecked


# =============================================================================
# QueuePage Tests
# =============================================================================

class TestQueuePage:
    """Tests for the QueuePage widget."""
    
    def test_queue_page_creation(self, queue_page):
        """Test that QueuePage can be created."""
        assert queue_page is not None
        assert queue_page.queue is not None
        assert queue_page.queue_list is not None
    
    def test_queue_initially_empty(self, queue_page):
        """Test that a new queue is empty."""
        assert queue_page.queue.size() == 0
    
    def test_add_new_scan(self, queue_page, qtbot):
        """Test adding a new scan to the queue."""
        page = queue_page
        
        initial_size = page.queue.size()
        page.add_new_scan()
        
        assert page.queue.size() == initial_size + 1
        
        # Verify the scan was created correctly
        handle = page.queue.get_handle(0)
        assert handle is not None
        assert handle.scan is not None
        assert "Scan_" in handle.scan.scan_settings.scan_name
    
    def test_add_multiple_scans(self, queue_page, qtbot):
        """Test adding multiple scans to the queue."""
        page = queue_page
        
        for i in range(5):
            page.add_new_scan()
        
        assert page.queue.size() == 5
        
        # Verify each scan has unique name
        names = set()
        for i in range(5):
            handle = page.queue.get_handle(i)
            names.add(handle.scan.scan_settings.scan_name)
        
        assert len(names) == 5
    
    def test_queue_with_scans(self, sample_queue_with_scans):
        """Test QueuePage with pre-populated scans."""
        page = sample_queue_with_scans
        
        assert page.queue.size() == 3
        
        # Verify scan properties
        for i in range(3):
            handle = page.queue.get_handle(i)
            assert handle.scan.scan_settings.project_name == f"project_{i}"
            assert handle.scan.scan_settings.scan_name == f"scan_{i}"
            assert handle.scan.sample_id == f"sample_{i}"
    
    def test_remove_scan(self, sample_queue_with_scans, qtbot):
        """Test removing a scan from the queue."""
        page = sample_queue_with_scans
        
        # Highlight the first scan
        page.highlighted_index = 0
        page.remove_highlighted_scan()
        
        assert page.queue.size() == 2
    
    def test_move_scan_up(self, sample_queue_with_scans, qtbot):
        """Test moving a scan up in the queue."""
        page = sample_queue_with_scans
        
        # Get scan names before move
        name_at_1 = page.queue.get_handle(1).scan.scan_settings.scan_name
        
        # Highlight and move scan at index 1 up
        page.highlighted_index = 1
        page.move_scan_up()
        
        # Verify the scan moved to position 0
        assert page.queue.get_handle(0).scan.scan_settings.scan_name == name_at_1
    
    def test_move_scan_down(self, sample_queue_with_scans, qtbot):
        """Test moving a scan down in the queue."""
        page = sample_queue_with_scans
        
        # Get scan names before move
        name_at_0 = page.queue.get_handle(0).scan.scan_settings.scan_name
        
        # Highlight and move scan at index 0 down
        page.highlighted_index = 0
        page.move_scan_down()
        
        # Verify the scan moved to position 1
        assert page.queue.get_handle(1).scan.scan_settings.scan_name == name_at_0
    
    def test_queue_refresh(self, sample_queue_with_scans, qtbot):
        """Test queue list refresh."""
        page = sample_queue_with_scans
        
        # Trigger refresh
        page.refresh_queue_list()
        
        # Verify list count matches queue size
        assert page.queue_list.count() == page.queue.size()


# =============================================================================
# Queue and Scan Integration Tests
# =============================================================================

class TestQueueScanIntegration:
    """Integration tests for queue and scan interactions."""
    
    def test_scan_page_in_queue_page(self, queue_page, qtbot):
        """Test that ScanPage is correctly embedded in QueuePage."""
        page = queue_page
        
        # Add a scan
        page.add_new_scan()
        
        # Highlight it
        page.on_scan_highlighted(0)
        
        # Verify scan page was created
        assert page.scan_page is not None
        assert page.scan_page.scan is not None
    
    def test_scan_changes_persist_in_queue(self, queue_page, qtbot):
        """Test that changes to scan in ScanPage persist in queue."""
        page = queue_page
        
        # Add and highlight a scan
        page.add_new_scan()
        page.on_scan_highlighted(0)
        
        # Get the scan from the queue and modify via page
        original_name = page.scan_page.scan.scan_settings.scan_name
        
        # Verify the scan in queue has the same object reference
        queue_scan = page.queue.get_handle(0).scan
        assert queue_scan is page.scan_page.scan
    
    def test_scan_sample_id_preserved(self, qtbot):
        """Test that sample_id is preserved through queue operations."""
        from GUI.windows.queue_page import QueuePage
        
        queue = Queue("test_queue")
        
        # Create scan with sample_id
        scan_settings = ScanSettings(
            project_name="test",
            scan_name="test_scan",
            scan_type="",
            job_type="",
            ScanTree=ScanTreeModel(),
            additional_tags=[],
            status="Queued"
        )
        scan = Scan(scan_settings=scan_settings, owner="test", sample_id="my_sample_123")
        
        queue.enqueue(scan)
        
        # Verify sample_id is preserved
        retrieved_scan = queue.get_handle(0).scan
        assert retrieved_scan.sample_id == "my_sample_123"
    
    def test_queue_serialization_with_sample_id(self):
        """Test that queue serialization includes sample_id."""
        queue = Queue("test_queue")
        
        # Create scan with sample_id
        scan_settings = ScanSettings(
            project_name="test",
            scan_name="test_scan",
            scan_type="",
            job_type="",
            ScanTree=ScanTreeModel(),
            additional_tags=[],
            status="Queued"
        )
        scan = Scan(scan_settings=scan_settings, owner="test", sample_id="sample_xyz")
        
        queue.enqueue(scan)
        
        # Serialize the queue
        serialized = queue.serialize()
        
        # Verify sample_id in serialization
        assert "scans" in serialized
        assert len(serialized["scans"]) == 1
        assert serialized["scans"][0]["sample_id"] == "sample_xyz"


# =============================================================================
# Scan Creation Tests
# =============================================================================

class TestScanCreation:
    """Tests for Scan object creation and initialization."""
    
    def test_scan_with_all_parameters(self):
        """Test creating a Scan with all parameters."""
        scan_settings = ScanSettings(
            project_name="full_project",
            scan_name="full_scan",
            scan_type="iv_curve",
            job_type="characterization",
            ScanTree=ScanTreeModel(),
            additional_tags=["tag1", "tag2"],
            status="Queued"
        )
        
        scan = Scan(
            scan_settings=scan_settings,
            owner="researcher",
            sample_id="sample_full"
        )
        
        assert scan.scan_settings.project_name == "full_project"
        assert scan.scan_settings.scan_name == "full_scan"
        assert scan.owner == "researcher"
        assert scan.sample_id == "sample_full"
    
    def test_scan_without_sample_id(self):
        """Test creating a Scan without sample_id (should default to None)."""
        scan_settings = ScanSettings(
            project_name="test",
            scan_name="test",
            scan_type="",
            job_type="",
            ScanTree=ScanTreeModel(),
            additional_tags=[],
            status="Queued"
        )
        
        scan = Scan(scan_settings=scan_settings, owner="test")
        
        assert scan.sample_id is None
    
    def test_scan_tree_state_attribute(self):
        """Test that scan has tree_state attribute."""
        scan = get_empty_scan()
        
        # tree_state should be settable
        test_state = [{'name': 'test', 'type': 'Movement', 'check_state': 2, 'children': []}]
        scan.tree_state = test_state
        
        assert scan.tree_state == test_state


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in UI components."""
    
    def test_remove_scan_from_empty_queue(self, queue_page):
        """Test removing scan from empty queue - with None index does nothing."""
        page = queue_page
        
        # When highlighted_index is None, remove should do nothing
        page.highlighted_index = None
        page.remove_highlighted_scan()
        
        assert page.queue.size() == 0
    
    def test_remove_invalid_index_raises(self, queue_page):
        """Test that removing with invalid index raises IndexError."""
        page = queue_page
        
        # Setting an invalid index should raise when trying to dequeue
        page.highlighted_index = 0  # Invalid since queue is empty
        
        with pytest.raises(IndexError):
            page.remove_highlighted_scan()
    
    def test_move_first_scan_up(self, sample_queue_with_scans, qtbot):
        """Test moving the first scan up (should do nothing)."""
        page = sample_queue_with_scans
        
        original_name = page.queue.get_handle(0).scan.scan_settings.scan_name
        
        page.highlighted_index = 0
        page.move_scan_up()  # Should do nothing
        
        # Verify scan didn't move
        assert page.queue.get_handle(0).scan.scan_settings.scan_name == original_name
    
    def test_move_last_scan_down(self, sample_queue_with_scans, qtbot):
        """Test moving the last scan down (should do nothing)."""
        page = sample_queue_with_scans
        
        last_idx = page.queue.size() - 1
        original_name = page.queue.get_handle(last_idx).scan.scan_settings.scan_name
        
        page.highlighted_index = last_idx
        page.move_scan_down()  # Should do nothing
        
        # Verify scan didn't move
        assert page.queue.get_handle(last_idx).scan.scan_settings.scan_name == original_name


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
