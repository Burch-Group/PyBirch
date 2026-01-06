# Copyright (C) 2025
# Main PyBirch Window
"""
Main window for PyBirch GUI application.

This window contains:
- Queue bar on the left with buttons for navigation
- Stacked widget on the right showing different pages
- Coordination between pages to keep data synchronized
"""

from __future__ import annotations

import sys
import os
from typing import Optional

# Add path to parent directories for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QMessageBox,
    QSplitter
)
from PySide6.QtGui import QCloseEvent

# Import PyBirch components
from pybirch.queue.queue import Queue, ScanState, QueueState
from pybirch.scan.scan import Scan, get_empty_scan

# Import GUI components
try:
    from GUI.widgets.queue_bar import QueueBar
    from GUI.windows.queue_page import QueuePage
    from GUI.windows.queue_info_page import QueueInfoPage
    from GUI.windows.instruments_page import InstrumentsPage
    from GUI.theme import Theme
except ImportError:
    from widgets.queue_bar import QueueBar
    from windows.queue_page import QueuePage
    from windows.queue_info_page import QueueInfoPage
    from windows.instruments_page import InstrumentsPage
    from theme import Theme

# Optional: Import database integration
try:
    from database.services import DatabaseService
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    DatabaseService = None


class MainWindow(QMainWindow):
    """
    Main PyBirch application window.
    
    Layout:
    ┌────────────────────────────────────────┐
    │  Main Window                           │
    ├──────┬─────────────────────────────────┤
    │      │                                 │
    │ Q    │                                 │
    │ u    │      Current Page               │
    │ e    │    (Queue/Info/Instruments)     │
    │ u    │                                 │
    │ e    │                                 │
    │      │                                 │
    │ B    │                                 │
    │ a    │                                 │
    │ r    │                                 │
    │      │                                 │
    └──────┴─────────────────────────────────┘
    
    The queue bar on the left has buttons that switch between pages.
    All pages share the same Queue object so changes are synchronized.
    """
    
    # Signals
    queue_changed = Signal()  # Emitted when queue data changes
    
    def __init__(
        self,
        queue: Optional[Queue] = None,
        db_service: Optional['DatabaseService'] = None,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the main window.
        
        Args:
            queue: PyBirch Queue object to display/edit. Creates new if None.
            db_service: Optional database service for persistence
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Initialize queue
        self.queue = queue or Queue(QID="NewQueue")
        self.db_service = db_service
        
        # Track if we have unsaved changes
        self.has_unsaved_changes = False
        
        # Initialize UI
        self.init_ui()
        self.connect_signals()
        
        # Set window properties
        self.setWindowTitle("PyBirch - Queue Builder")
        self.resize(1400, 900)
        
        # Show the default page (queue info)
        self.show_queue_info_page()
    
    def init_ui(self):
        """Initialize the user interface."""
        # Create central widget with horizontal layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main horizontal splitter for resizable divider
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Create queue bar on the left
        self.queue_bar = QueueBar(self.queue)
        self.queue_bar.setFixedWidth(96)  # Fixed width for icon buttons
        
        # Set up current scan getter for preset dialog
        self.queue_bar.set_current_scan_getter(self.get_current_scan)
        
        # Create stacked widget for pages on the right
        self.pages_stack = QStackedWidget()
        
        # Create pages
        self.queue_info_page = QueueInfoPage()
        self.queue_page = QueuePage(self.queue)
        self.instruments_page = InstrumentsPage()
        
        # Add pages to stack
        self.PAGE_INFO = self.pages_stack.addWidget(self.queue_info_page)
        self.PAGE_QUEUE = self.pages_stack.addWidget(self.queue_page)
        self.PAGE_INSTRUMENTS = self.pages_stack.addWidget(self.instruments_page)
        
        # Add widgets to splitter
        self.main_splitter.addWidget(self.queue_bar)
        self.main_splitter.addWidget(self.pages_stack)
        
        # Set splitter sizes (queue bar takes minimal space, rest to pages)
        self.main_splitter.setStretchFactor(0, 0)  # Queue bar doesn't stretch
        self.main_splitter.setStretchFactor(1, 1)  # Pages take all remaining space
        
        # Make queue bar non-collapsible
        self.main_splitter.setCollapsible(0, False)
        
        # Add splitter to central widget
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.main_splitter)
    
    def connect_signals(self):
        """Connect signals between components."""
        # Connect queue bar buttons to page switching
        self.queue_bar.queue_button.clicked.connect(self.show_queue_page)
        self.queue_bar.info_button.clicked.connect(self.show_queue_info_page)
        self.queue_bar.instruments_button.clicked.connect(self.show_instruments_page)
        
        # Connect preset loading signals
        self.queue_bar.queue_loaded.connect(self.on_queue_preset_loaded)
        self.queue_bar.scan_preset_loaded.connect(self.on_scan_preset_loaded)
        
        # Connect queue info page changes to mark as modified and sync to queue
        # Use the entry_box's textChanged signal from the SingleEntryWidget
        self.queue_info_page.project_name_widget.entry_box.textChanged.connect(self.on_queue_info_changed)
        self.queue_info_page.project_name_widget.entry_box.textChanged.connect(self.sync_info_page_to_queue_silent)
        self.queue_info_page.material_widget.entry_box.textChanged.connect(self.on_queue_info_changed)
        self.queue_info_page.material_widget.entry_box.textChanged.connect(self.sync_info_page_to_queue_silent)
        self.queue_info_page.substrate_widget.entry_box.textChanged.connect(self.on_queue_info_changed)
        self.queue_info_page.substrate_widget.entry_box.textChanged.connect(self.sync_info_page_to_queue_silent)
        
        # Connect queue page changes
        if hasattr(self.queue_page, 'queue_modified'):
            self.queue_page.queue_modified.connect(self.on_queue_modified)
    
    # ==================== Page Navigation ====================
    
    def show_queue_info_page(self):
        """Show the queue information page."""
        # Sync data from queue to page before showing
        self.sync_queue_to_info_page()
        self.pages_stack.setCurrentIndex(self.PAGE_INFO)
        self.setWindowTitle("PyBirch - Queue Information")
    
    def show_queue_page(self):
        """Show the queue (scan list) page."""
        # Sync data from info page to queue before showing queue page
        self.sync_info_page_to_queue()
        
        # Sync configured instruments from instruments page to queue page
        self.sync_configured_instruments_to_queue_page()
        
        self.pages_stack.setCurrentIndex(self.PAGE_QUEUE)
        self.setWindowTitle("PyBirch - Queue")
    
    def show_instruments_page(self):
        """Show the instruments configuration page."""
        self.pages_stack.setCurrentIndex(self.PAGE_INSTRUMENTS)
        self.setWindowTitle("PyBirch - Instruments")
    
    # ==================== Data Synchronization ====================
    
    def sync_queue_to_info_page(self):
        """Sync queue data to the queue info page."""
        # Get data from queue - use metadata dict if available
        queue_metadata = getattr(self.queue, 'metadata', {}) or {}
        data = {
            "project_name": self.queue.QID or "",
            "material": queue_metadata.get('material', ""),
            "substrate": queue_metadata.get('substrate', ""),
            "user_fields": queue_metadata.get('user_fields', {}),
            "save_as_default": queue_metadata.get('save_as_default', False)
        }
        
        # Set data to info page
        self.queue_info_page.set_data(data)
    
    def sync_info_page_to_queue(self):
        """Sync queue info page data back to the queue."""
        # Get data from info page
        data = self.queue_info_page.get_data()
        
        # Update queue
        if data.get("project_name"):
            self.queue.QID = data["project_name"]
        
        # Store all queue info in metadata dict
        if not hasattr(self.queue, 'metadata') or self.queue.metadata is None:
            self.queue.metadata = {}
        self.queue.metadata['material'] = data.get('material', '')
        self.queue.metadata['substrate'] = data.get('substrate', '')
        self.queue.metadata['user_fields'] = data.get('user_fields', {})
        self.queue.metadata['save_as_default'] = data.get('save_as_default', False)
        
        # If database is available, save to database
        if self.db_service and DATABASE_AVAILABLE:
            self.save_queue_to_database(data)
        
        # Mark as changed
        self.on_queue_modified()
    
    def sync_info_page_to_queue_silent(self):
        """Sync queue info page data back to the queue without marking as modified.
        Used for real-time syncing as user types."""
        # Get data from info page
        data = self.queue_info_page.get_data()
        
        # Update queue
        if data.get("project_name"):
            self.queue.QID = data["project_name"]
        
        # Store all queue info in metadata dict
        if not hasattr(self.queue, 'metadata') or self.queue.metadata is None:
            self.queue.metadata = {}
        self.queue.metadata['material'] = data.get('material', '')
        self.queue.metadata['substrate'] = data.get('substrate', '')
        self.queue.metadata['user_fields'] = data.get('user_fields', {})
        self.queue.metadata['save_as_default'] = data.get('save_as_default', False)
    
    def save_queue_to_database(self, queue_info: dict):
        """
        Save queue information to database.
        
        Args:
            queue_info: Dictionary from queue info page
        """
        if not self.db_service:
            return
        
        try:
            # TODO: Implement database save logic
            # This would use the DatabaseQueue or QueueManager classes
            # from pybirch.database_integration
            pass
        except Exception as e:
            QMessageBox.warning(
                self,
                "Database Error",
                f"Failed to save to database: {str(e)}"
            )
    
    # ==================== Change Tracking ====================
    
    @Slot()
    def on_queue_info_changed(self):
        """Handle changes to queue info fields."""
        self.has_unsaved_changes = True
        self.queue_changed.emit()
    
    @Slot()
    def on_queue_modified(self):
        """Handle queue modifications (scans added/removed/changed)."""
        self.has_unsaved_changes = True
        self.queue_changed.emit()
    
    @Slot()
    def on_queue_preset_loaded(self):
        """Handle when a queue preset is loaded."""
        # Refresh all pages with new queue data
        self.sync_queue_to_info_page()
        
        # Refresh the queue page
        if hasattr(self.queue_page, 'refresh'):
            self.queue_page.refresh()
        elif hasattr(self.queue_page, 'scan_list_widget'):
            self.queue_page.scan_list_widget.refresh_table()
        
        # Mark as modified since we changed the queue
        self.has_unsaved_changes = True
        self.queue_changed.emit()
    
    @Slot(object)
    def on_scan_preset_loaded(self, scan):
        """Handle when a scan preset is loaded."""
        from pybirch.scan.scan import Scan
        
        if not isinstance(scan, Scan):
            return
        
        # If we're on the queue page, replace the currently selected scan
        if self.pages_stack.currentIndex() == self.PAGE_QUEUE:
            if hasattr(self.queue_page, 'replace_current_scan'):
                self.queue_page.replace_current_scan(scan)
            elif hasattr(self.queue_page, 'scan_list_widget'):
                # Try to replace selected scan in the scan list
                selected = self.queue_page.scan_list_widget.table.selectionModel().selectedRows()
                if selected:
                    row = selected[0].row()
                    if 0 <= row < len(self.queue.scans):
                        self.queue.scans[row] = scan
                        self.queue_page.scan_list_widget.refresh_table()
                        # Also update scan page if visible
                        if hasattr(self.queue_page, 'scan_page'):
                            self.queue_page.scan_page.set_scan(scan)
                else:
                    # No selection, add as new scan
                    self.queue.enqueue(scan)
                    self.queue_page.scan_list_widget.refresh_table()
        else:
            # Not on queue page, add scan to queue
            self.queue.enqueue(scan)
        
        # Mark as modified
        self.has_unsaved_changes = True
        self.queue_changed.emit()

    def sync_configured_instruments_to_queue_page(self):
        """Sync configured instruments from instruments page to queue page."""
        # Get configured instruments from adapter manager
        if hasattr(self.instruments_page, 'adapter_manager'):
            configured_instruments = self.instruments_page.adapter_manager.get_configured_instruments()
            
            # Pass to queue page
            if hasattr(self.queue_page, 'set_configured_instruments'):
                self.queue_page.set_configured_instruments(configured_instruments)
    
    def get_current_scan(self):
        """Get the currently selected/active scan.
        
        Returns:
            The current Scan object or None if no scan is selected
        """
        # Try to get selected scan from queue page
        if hasattr(self.queue_page, 'get_current_scan'):
            return self.queue_page.get_current_scan()
        
        # Fallback: try to get from scan list widget selection
        if hasattr(self.queue_page, 'scan_list_widget'):
            selected = self.queue_page.scan_list_widget.table.selectionModel().selectedRows()
            if selected:
                row = selected[0].row()
                if 0 <= row < len(self.queue.scans):
                    return self.queue.scans[row]
        
        # If we have scans, return the first one
        if self.queue.scans:
            return self.queue.scans[0]
        
        return None

    # ==================== Window Events ====================
    
    def closeEvent(self, event: QCloseEvent):
        """Handle window close event."""
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before closing?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                # Save and close
                self.save_queue()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                # Close without saving
                event.accept()
            else:
                # Cancel close
                event.ignore()
        else:
            event.accept()
    
    # ==================== File Operations ====================
    
    def save_queue(self):
        """Save the queue to file or database."""
        # Sync info page data to queue first
        self.sync_info_page_to_queue()
        
        # If database available, save there
        if self.db_service and DATABASE_AVAILABLE:
            try:
                # TODO: Implement database save
                self.has_unsaved_changes = False
                QMessageBox.information(self, "Success", "Queue saved to database")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save: {str(e)}")
        else:
            # Otherwise use file save
            from PySide6.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Queue",
                "",
                "Pickle Files (*.pkl);;All Files (*)"
            )
            if file_path:
                try:
                    import pickle
                    with open(file_path, 'wb') as f:
                        pickle.dump(self.queue, f)
                    self.has_unsaved_changes = False
                    QMessageBox.information(self, "Success", f"Queue saved to {file_path}")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to save: {str(e)}")
    
    def load_queue(self):
        """Load a queue from file or database."""
        from PySide6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Queue",
            "",
            "Pickle Files (*.pkl);;All Files (*)"
        )
        if file_path:
            try:
                import pickle
                with open(file_path, 'rb') as f:
                    loaded_queue = pickle.load(f)
                    if isinstance(loaded_queue, Queue):
                        self.queue = loaded_queue
                        # Update queue bar with new queue
                        self.queue_bar.queue = self.queue
                        # Update queue page with new queue
                        self.queue_page.queue = self.queue
                        self.queue_page.refresh_scan_list()
                        # Sync to info page
                        self.sync_queue_to_info_page()
                        self.has_unsaved_changes = False
                        QMessageBox.information(self, "Success", f"Queue loaded from {file_path}")
                    else:
                        QMessageBox.warning(self, "Error", "File does not contain a valid Queue")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load: {str(e)}")
    
    # ==================== Public API ====================
    
    def get_queue(self) -> Queue:
        """Get the current queue object."""
        return self.queue
    
    def set_queue(self, queue: Queue):
        """
        Set a new queue object.
        
        Args:
            queue: New Queue object to display
        """
        self.queue = queue
        self.queue_bar.queue = queue
        self.queue_page.queue = queue
        self.queue_page.refresh_scan_list()
        self.sync_queue_to_info_page()
        self.has_unsaved_changes = False


# ==================== Standalone Testing ====================

def main():
    """Test the main window."""
    from PySide6.QtWidgets import QApplication
    from GUI.theme import apply_theme
    
    app = QApplication(sys.argv)
    apply_theme(app)
    
    # Create a test queue with some scans
    test_queue = Queue(QID="TestQueue")
    
    # Add a few test scans
    for i in range(3):
        scan = get_empty_scan()
        scan.scan_settings.scan_name = f"Test Scan {i+1}"
        scan.scan_settings.project_name = "TestProject"
        test_queue.enqueue(scan)
    
    # Create and show main window
    window = MainWindow(queue=test_queue)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
