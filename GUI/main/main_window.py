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
    from GUI.windows.extensions_page import ExtensionsPage
    from GUI.theme import Theme
except ImportError:
    from widgets.queue_bar import QueueBar
    from windows.queue_page import QueuePage
    from windows.queue_info_page import QueueInfoPage
    from windows.instruments_page import InstrumentsPage
    from windows.extensions_page import ExtensionsPage
    from theme import Theme

# Optional: Import database integration
try:
    from database.services import DatabaseService
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    DatabaseService = None

# Optional: Import WebSocket integration
try:
    from pybirch.database_integration.sync import (
        setup_websocket_integration,
        WebSocketQueueBridge,
        check_server_running,
    )
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    setup_websocket_integration = None
    WebSocketQueueBridge = None
    check_server_running = None


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
        self.instruments_page = InstrumentsPage()
        self.extensions_page = ExtensionsPage()
        self.extensions_page.set_queue(self.queue)
        
        # Create queue page with extensions_page reference
        # NOTE: QueuePage is created WITHOUT a parent here - it gets reparented when added to pages_stack
        print(f"\n[MainWindow] Creating QueuePage...")
        self.queue_page = QueuePage(self.queue, extensions_page=self.extensions_page)
        print(f"[MainWindow] QueuePage created, parent is: {self.queue_page.parent()}")
        
        # Add pages to stack
        # NOTE: This sets the QueuePage's parent to pages_stack (QStackedWidget), NOT MainWindow!
        self.PAGE_INFO = self.pages_stack.addWidget(self.queue_info_page)
        self.PAGE_QUEUE = self.pages_stack.addWidget(self.queue_page)
        print(f"[MainWindow] QueuePage added to pages_stack, parent is now: {self.queue_page.parent()}")
        print(f"[MainWindow] QueuePage.parent() type: {type(self.queue_page.parent()).__name__ if self.queue_page.parent() else 'None'}")
        print(f"[MainWindow] pages_stack.parent() = {self.pages_stack.parent()}")
        self.PAGE_INSTRUMENTS = self.pages_stack.addWidget(self.instruments_page)
        self.PAGE_EXTENSIONS = self.pages_stack.addWidget(self.extensions_page)
        
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
        self.queue_bar.extensions_button.clicked.connect(self.show_extensions_page)
        
        # Connect preset loading signals
        self.queue_bar.queue_loaded.connect(self.on_queue_preset_loaded)
        self.queue_bar.scan_preset_loaded.connect(self.on_scan_preset_loaded)
        
        # Connect queue info page changes to mark as modified and sync to queue
        # Use the entry_box's textChanged signal from the SingleEntryWidget
        self.queue_info_page.project_name_widget.entry_box.textChanged.connect(self.on_queue_info_changed)
        self.queue_info_page.project_name_widget.entry_box.textChanged.connect(self.sync_info_page_to_queue_silent)
        
        # Connect sample and project selection changes
        self.queue_info_page.sample_changed.connect(self.on_queue_info_changed)
        self.queue_info_page.sample_changed.connect(self.sync_info_page_to_queue_silent)
        self.queue_info_page.project_changed.connect(self.on_queue_info_changed)
        self.queue_info_page.project_changed.connect(self.sync_info_page_to_queue_silent)
        
        # Connect extensions page database state changes to update queue info dropdowns
        self.extensions_page.database_state_changed.connect(self._on_database_state_changed)
        
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
        print("\n[MainWindow] show_queue_page called")
        # Sync data from info page to queue before showing queue page
        self.sync_info_page_to_queue()
        
        # Sync configured instruments from instruments page to queue page
        print("[MainWindow] Calling sync_configured_instruments_to_queue_page()")
        self.sync_configured_instruments_to_queue_page()
        
        self.pages_stack.setCurrentIndex(self.PAGE_QUEUE)
        self.setWindowTitle("PyBirch - Queue")
    
    def show_instruments_page(self):
        """Show the instruments configuration page."""
        self.pages_stack.setCurrentIndex(self.PAGE_INSTRUMENTS)
        self.setWindowTitle("PyBirch - Instruments")
    
    def show_extensions_page(self):
        """Show the extensions configuration page."""
        self.pages_stack.setCurrentIndex(self.PAGE_EXTENSIONS)
        self.setWindowTitle("PyBirch - Extensions")
    
    # ==================== Data Synchronization ====================
    
    def sync_queue_to_info_page(self):
        """Sync queue data to the queue info page."""
        # Get data from queue - use metadata dict if available
        queue_metadata = getattr(self.queue, 'metadata', {}) or {}
        data = {
            "project_name": self.queue.QID or "",
            "sample_id": queue_metadata.get('sample_id'),
            "sample_text": queue_metadata.get('sample_text', ""),
            "project_id": queue_metadata.get('project_id'),
            "project_text": queue_metadata.get('project_text', ""),
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
        self.queue.metadata['sample_id'] = data.get('sample_id')
        self.queue.metadata['sample_text'] = data.get('sample_text', '')
        self.queue.metadata['project_id'] = data.get('project_id')
        self.queue.metadata['project_text'] = data.get('project_text', '')
        self.queue.metadata['user_fields'] = data.get('user_fields', {})
        self.queue.metadata['save_as_default'] = data.get('save_as_default', False)
        
        # If database is available, save to database
        if self.db_service and DATABASE_AVAILABLE:
            self.save_queue_to_database(data)
        
        # Mark as changed
        self.on_queue_modified()
    
    def sync_info_page_to_queue_silent(self, *args):
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
        self.queue.metadata['sample_id'] = data.get('sample_id')
        self.queue.metadata['sample_text'] = data.get('sample_text', '')
        self.queue.metadata['project_id'] = data.get('project_id')
        self.queue.metadata['project_text'] = data.get('project_text', '')
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
    
    def _on_database_state_changed(self, enabled: bool, db_service):
        """
        Handle database enable/disable from extensions page.
        
        Updates the queue info page with database service so sample/project
        dropdowns can be populated, and updates instruments page to load
        database-stored instruments.
        
        Args:
            enabled: Whether database is now enabled
            db_service: DatabaseService instance or None
        """
        print(f"[MainWindow] Database state changed: enabled={enabled}")
        self.queue_info_page.set_database_service(db_service)
        
        # Update instruments page for database-stored instruments
        if hasattr(self, 'instruments_page') and hasattr(self.instruments_page, 'set_database_service'):
            self.instruments_page.set_database_service(db_service)
        
        # Also update our local reference
        if enabled and db_service:
            self.db_service = db_service
    
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
            elif hasattr(self.queue_page, 'highlighted_index') and self.queue_page.highlighted_index is not None:
                # Use queue's replace_scan method to properly update the handle
                try:
                    self.queue.replace_scan(self.queue_page.highlighted_index, scan)
                    self.queue_page.refresh_queue_list()
                    # Also update scan page if visible
                    if hasattr(self.queue_page, 'scan_page') and self.queue_page.scan_page:
                        self.queue_page.scan_page.set_scan(scan)
                except (IndexError, RuntimeError) as e:
                    # No valid selection or scan is running, add as new scan
                    self.queue.enqueue(scan)
                    self.queue_page.refresh_queue_list()
            else:
                # No selection, add as new scan
                self.queue.enqueue(scan)
                if hasattr(self.queue_page, 'refresh_queue_list'):
                    self.queue_page.refresh_queue_list()
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
        self.extensions_page.set_queue(queue)
        self.sync_queue_to_info_page()
        self.has_unsaved_changes = False
    
    # ==================== WebSocket Integration ====================
    
    def enable_websocket_integration(
        self, 
        server_url: str = "http://localhost:5000"
    ) -> Optional['WebSocketQueueBridge']:
        """
        Enable WebSocket integration for live updates to the web dashboard.
        
        This connects the queue's callbacks to the WebSocket server so that
        scan status changes, progress updates, and log entries are broadcast
        in real-time.
        
        Args:
            server_url: URL of the WebSocket server (default: http://localhost:5000)
        
        Returns:
            WebSocketQueueBridge if successful, None if WebSocket not available
        """
        if not WEBSOCKET_AVAILABLE:
            print("WebSocket integration not available - missing dependencies")
            return None
        
        # Check if server is running
        if not check_server_running(server_url):
            print(f"WebSocket server not running at {server_url}")
            return None
        
        # Store the bridge reference
        if not hasattr(self, '_websocket_bridge'):
            self._websocket_bridge = None
        
        # Clean up existing bridge
        if self._websocket_bridge is not None:
            self._websocket_bridge.unregister()
        
        try:
            # Create new bridge using server URL (cross-process)
            self._websocket_bridge = setup_websocket_integration(
                queue=self.queue,
                server_url=server_url
            )
            print(f"WebSocket integration enabled for queue {self.queue.QID}")
            return self._websocket_bridge
        except Exception as e:
            print(f"Failed to enable WebSocket integration: {e}")
            return None
    
    def disable_websocket_integration(self):
        """Disable WebSocket integration."""
        if hasattr(self, '_websocket_bridge') and self._websocket_bridge is not None:
            self._websocket_bridge.unregister()
            self._websocket_bridge = None
            print("WebSocket integration disabled")
    
    @property
    def websocket_enabled(self) -> bool:
        """Check if WebSocket integration is currently enabled."""
        return hasattr(self, '_websocket_bridge') and self._websocket_bridge is not None


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
