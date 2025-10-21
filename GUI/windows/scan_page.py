# Copyright (C) 2025
# Scan Page Widget for PyBirch
from __future__ import annotations

import sys
import os
from typing import Optional, List

# Add path to parent directories for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from PySide6.QtCore import Qt, QModelIndex, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                               QScrollArea, QFrame, QTreeWidgetItem)

# Import the required widgets
from widgets.scan_title_bar import ScanTitleBar
from widgets.scan_tree.mainwindow import MainWindow as ScanTreeMainWindow
from widgets.movement_positions import MovementPositionsWidget
from pybirch.scan.scan import Scan, get_empty_scan
from pybirch.scan.movements import Movement, VisaMovement
from pybirch.scan.measurements import Measurement, VisaMeasurement


class ScanPage(QWidget):
    """
    Main scan page widget that combines:
    - ScanTitleBar at the top
    - ScanTreeMainWindow on the left
    - MovementPositions widgets on the right (for movement instruments only)
    """
    
    # Signal emitted when movement instruments are selected/deselected
    movement_instruments_changed = Signal(list)
    
    def __init__(self, scan: Optional[Scan] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Use provided scan or create empty one
        self.scan = scan if scan is not None else get_empty_scan()
        
        # Track movement instruments currently displayed
        self.current_movement_instruments: List[str] = []
        
        self.init_ui()
        self.connect_signals()
        
    def init_ui(self):
        """Initialize the user interface"""
        # Main vertical layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create scan title bar
        self.title_bar = ScanTitleBar(self.scan)
        main_layout.addWidget(self.title_bar)
        
        # Create horizontal splitter for scan tree and movement positions
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)
        
        # Create scan tree widget (left side)
        self.scan_tree = ScanTreeMainWindow()
        self.scan_tree.setWindowTitle("")  # Remove window title since it's embedded
        
        # Remove the menu bar and status bar for embedded use
        self.scan_tree.menuBar().hide()
        self.scan_tree.statusBar().hide()
        
        # Create a frame to contain the scan tree
        scan_tree_frame = QFrame()
        scan_tree_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        scan_tree_layout = QVBoxLayout(scan_tree_frame)
        scan_tree_layout.setContentsMargins(5, 5, 5, 5)
        scan_tree_layout.addWidget(self.scan_tree.view)  # Add just the tree view
        
        self.splitter.addWidget(scan_tree_frame)
        
        # Create movement positions container (right side)
        self.movement_container = QFrame()
        self.movement_container.setFrameStyle(QFrame.Shape.StyledPanel)
        self.movement_layout = QVBoxLayout(self.movement_container)
        self.movement_layout.setContentsMargins(5, 5, 5, 5)
        self.movement_layout.setSpacing(5)
        
        # Create scroll area for movement positions
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Widget to contain all movement position widgets
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(5, 5, 5, 5)
        self.scroll_layout.setSpacing(5)
        self.scroll_layout.addStretch()  # Push widgets to top
        
        self.scroll_area.setWidget(self.scroll_widget)
        self.movement_layout.addWidget(self.scroll_area)
        
        self.splitter.addWidget(self.movement_container)
        
        # Set initial splitter sizes (60% scan tree, 40% movement positions)
        self.splitter.setStretchFactor(0, 60)
        self.splitter.setStretchFactor(1, 40)
        
        # Store movement position widgets
        self.movement_widgets: dict[str, MovementPositionsWidget] = {}
        
    def connect_signals(self):
        """Connect signals between components"""
        # Connect scan tree selection changes to update movement positions
        if self.scan_tree.view.selectionModel():
            self.scan_tree.view.selectionModel().selectionChanged.connect(
                self.on_scan_tree_selection_changed
            )
            
        # Connect tree widget changes to update movement positions
        # This is the key signal for checkbox changes
        self.scan_tree.view.itemChanged.connect(self.on_item_changed)
        
        # Connect to QTreeWidget's itemSelectionChanged signal
        self.scan_tree.view.itemSelectionChanged.connect(self.update_movement_positions)
        
        # Connect to the specific action methods that add instruments
        if hasattr(self.scan_tree, 'insert_child'):
            original_insert_child = self.scan_tree.insert_child
            def patched_insert_child():
                original_insert_child()
                # Delay the update slightly to ensure the item is fully added
                from PySide6.QtCore import QTimer
                QTimer.singleShot(100, self.update_movement_positions)
            self.scan_tree.insert_child = patched_insert_child
            
        if hasattr(self.scan_tree, 'insert_row'):
            original_insert_row = self.scan_tree.insert_row
            def patched_insert_row():
                original_insert_row()
                from PySide6.QtCore import QTimer
                QTimer.singleShot(100, self.update_movement_positions)
            self.scan_tree.insert_row = patched_insert_row
            
    def on_item_changed(self, item, column):
        """Handle when an item is changed (especially checkbox changes)"""
        if column == 0:  # Only care about changes in the first column (checkbox column)
            self.update_movement_positions()
        
    def on_scan_tree_selection_changed(self):
        """Handle selection changes in the scan tree"""
        # For now, update all movement positions when selection changes
        # In the future, this could be more selective
        self.update_movement_positions()
        
    def update_movement_positions(self):
        """Update the movement positions widgets based on scan tree content"""
        # Get all movement instruments from the scan tree (CHECKED AND PARTIALLY CHECKED ITEMS)
        movement_instruments = self.get_movement_instruments_from_tree()
        

        
        # Get current unique IDs being displayed
        current_unique_ids = set(self.movement_widgets.keys())
        new_unique_ids = {unique_id for _, unique_id, _, _ in movement_instruments}
        
        # Remove widgets for instruments that are no longer checked/partially checked
        ids_to_remove = current_unique_ids - new_unique_ids
        
        for unique_id in ids_to_remove:
            # Save current settings to the tree item before removing widget
            widget = self.movement_widgets[unique_id]
            tree_item = getattr(widget, 'tree_item', None)
            if tree_item:
                self.save_movement_settings_to_tree_item(tree_item, widget)
            
            # Remove the widget
            widget = self.movement_widgets.pop(unique_id)
            self.scroll_layout.removeWidget(widget)
            widget.deleteLater()
                
        # Add widgets for newly checked movement instruments (in tree order)
        ids_to_add = new_unique_ids - current_unique_ids
        
        for instrument_name, unique_id, tree_item, instrument_obj in movement_instruments:
            if unique_id in ids_to_add:
                # Use the instrument object nickname to ensure we get the correct name
                display_name = instrument_obj.nickname if instrument_obj else instrument_name
                widget = MovementPositionsWidget(display_name)
                # Store references for saving settings (add as dynamic attributes)
                setattr(widget, 'tree_item', tree_item)
                setattr(widget, 'unique_id', unique_id)
                setattr(widget, 'instrument_object', instrument_obj)
                
                # Ensure the TreeItem has the necessary attributes
                instrument_tree_item = tree_item.data(0, Qt.ItemDataRole.UserRole + 1)
                if instrument_tree_item:
                    if not hasattr(instrument_tree_item, 'movement_positions'):
                        instrument_tree_item.movement_positions = []
                    if not hasattr(instrument_tree_item, 'movement_entries'):
                        instrument_tree_item.movement_entries = {}
                
                # Restore saved settings from tree item (this will initialize defaults if none exist)
                self.restore_movement_settings_from_tree_item(tree_item, widget)
                
                # Connect widget changes to save settings back to tree item
                self.connect_widget_changes_to_tree_item(widget, tree_item)
                
                self.movement_widgets[unique_id] = widget
                # Insert before the stretch (maintains tree order)
                self.scroll_layout.insertWidget(
                    self.scroll_layout.count() - 1, widget
                )
                
        # Update the current instruments list (convert back to simple list for compatibility)
        self.current_movement_instruments = [name for name, _, _, _ in movement_instruments]
        self.movement_instruments_changed.emit(self.current_movement_instruments)
        
    def get_movement_instruments_from_tree(self) -> List[tuple]:
        """Extract movement instrument info from the scan tree (QTreeWidget) - CHECKED AND PARTIALLY CHECKED ITEMS
        
        Returns a list of tuples: (instrument_name, unique_id, tree_item, instrument_object)
        This allows multiple instances and preserves tree order.
        """
        movement_instruments = []
        name_counters = {}  # Track how many times each name appears to create unique IDs
        
        def traverse_tree_widget_item(item, path=""):
            """Recursively traverse QTreeWidgetItem to find CHECKED/PARTIALLY CHECKED movement instruments"""
            # Process items that are checked or partially checked
            check_state = item.checkState(0)
            if check_state in (Qt.CheckState.Checked, Qt.CheckState.PartiallyChecked):
                # Get the instrument object from user data
                instrument_object = item.data(0, Qt.ItemDataRole.UserRole)
                if instrument_object:
                    # Check if it's a movement instrument (not measurement)
                    if isinstance(instrument_object, (Movement, VisaMovement)):
                        # Get the instrument name from the tree item text
                        instrument_name = item.text(0)  # First column contains the name
                        if instrument_name:
                            # Create unique identifier that handles identical instruments at same level
                            base_path = f"{path}/{instrument_name}" if path else instrument_name
                            
                            # Track count of this exact path to handle duplicates
                            if base_path not in name_counters:
                                name_counters[base_path] = 0
                            else:
                                name_counters[base_path] += 1
                            
                            # Create truly unique ID by appending count if needed
                            if name_counters[base_path] == 0:
                                unique_id = base_path
                            else:
                                unique_id = f"{base_path}#{name_counters[base_path]}"
                                
                            movement_instruments.append((instrument_name, unique_id, item, instrument_object))
                        
            # Always traverse children regardless of parent check state
            # Build path for unique identification
            current_path = f"{path}/{item.text(0)}" if path else item.text(0)
            for i in range(item.childCount()):
                child = item.child(i)
                if child:
                    traverse_tree_widget_item(child, current_path)
                
        # Start traversal from root (invisible root item)
        root = self.scan_tree.view.invisibleRootItem()
        for i in range(root.childCount()):
            top_level_item = root.child(i)
            if top_level_item:
                traverse_tree_widget_item(top_level_item)
        
        return movement_instruments
    
    def manual_update_movement_positions(self):
        """Manually trigger movement positions update - useful for testing"""
        self.update_movement_positions()
        
    def get_movement_positions(self) -> dict:
        """Get positions for all movement instruments"""
        positions = {}
        for unique_id, widget in self.movement_widgets.items():
            positions[unique_id] = widget.get_positions()
        return positions
        
    def save_movement_settings_to_tree_item(self, tree_item, widget):
        """Save movement position settings to the InstrumentTreeItem"""
        try:
            # Get the InstrumentTreeItem object from the QTreeWidgetItem
            instrument_tree_item = tree_item.data(0, Qt.ItemDataRole.UserRole + 1)
            
            if instrument_tree_item:
                # Ensure the attributes exist
                if not hasattr(instrument_tree_item, 'movement_positions'):
                    instrument_tree_item.movement_positions = []
                if not hasattr(instrument_tree_item, 'movement_entries'):
                    instrument_tree_item.movement_entries = {}
                    
                # Save current widget state
                positions = widget.get_positions()
                entries = widget.get_entries()
                
                instrument_tree_item.movement_positions = positions
                instrument_tree_item.movement_entries = entries
            else:
                # Try to create one if it doesn't exist
                instrument_obj = tree_item.data(0, Qt.ItemDataRole.UserRole)
                if instrument_obj:
                    from widgets.scan_tree.treeitem import InstrumentTreeItem
                    instrument_tree_item = InstrumentTreeItem(instrument_object=instrument_obj)
                    tree_item.setData(0, Qt.ItemDataRole.UserRole + 1, instrument_tree_item)
                    # Now save the settings
                    self.save_movement_settings_to_tree_item(tree_item, widget)
        except Exception as e:
            pass  # Silent fail
            
    def restore_movement_settings_from_tree_item(self, tree_item, widget):
        """Restore movement position settings from the InstrumentTreeItem"""
        try:
            # Get the InstrumentTreeItem object from the QTreeWidgetItem
            instrument_tree_item = tree_item.data(0, Qt.ItemDataRole.UserRole + 1)
            
            if instrument_tree_item:
                # Initialize attributes if they don't exist
                if not hasattr(instrument_tree_item, 'movement_positions'):
                    instrument_tree_item.movement_positions = []
                if not hasattr(instrument_tree_item, 'movement_entries'):
                    instrument_tree_item.movement_entries = {}
                
                # Restore settings if they exist
                if instrument_tree_item.movement_entries:
                    widget.set_entries(instrument_tree_item.movement_entries)
            else:
                # Try to create one if it doesn't exist
                instrument_obj = tree_item.data(0, Qt.ItemDataRole.UserRole)
                if instrument_obj:
                    from widgets.scan_tree.treeitem import InstrumentTreeItem
                    instrument_tree_item = InstrumentTreeItem(instrument_object=instrument_obj)
                    tree_item.setData(0, Qt.ItemDataRole.UserRole + 1, instrument_tree_item)
        except Exception as e:
            pass  # Silent fail
            

            
    def initialize_default_settings(self, tree_item, widget, instrument_tree_item):
        """Initialize default settings for a movement instrument"""
        try:
            # Get the instrument object to populate default settings
            instrument_object = tree_item.data(0, Qt.ItemDataRole.UserRole)
            if instrument_object and hasattr(instrument_object, 'positions'):
                # Initialize with instrument's available positions
                default_entries = {
                    'mode': 'discrete',  # Default to discrete mode
                    'positions': instrument_object.positions if hasattr(instrument_object, 'positions') else []
                }
                # Save default settings to tree item
                instrument_tree_item.movement_entries = default_entries
                instrument_tree_item.movement_positions = instrument_object.positions if hasattr(instrument_object, 'positions') else []
                
                # Apply default settings to widget
                widget.set_entries(default_entries)
        except Exception as e:
            pass  # Silent fail
            
    def connect_widget_changes_to_tree_item(self, widget, tree_item):
        """Connect widget signals to save changes when needed (no autosave)"""
        # No autosave - settings will be saved only when widget is removed
        pass
            
    def on_widget_settings_changed(self, widget, tree_item):
        """Handle when widget settings change - save to tree item"""
        try:
            self.save_movement_settings_to_tree_item(tree_item, widget)
        except Exception as e:
            pass  # Silent fail
        
    def set_movement_positions(self, positions: dict):
        """Set positions for movement instruments"""
        for instrument_name, instrument_positions in positions.items():
            if instrument_name in self.movement_widgets:
                # This would need to be implemented in MovementPositionsWidget
                # widget = self.movement_widgets[instrument_name]
                # widget.set_positions(instrument_positions)
                pass
                
    def get_scan_tree_data(self):
        """Get the scan tree data from QTreeWidget"""
        # Since we're using QTreeWidget now, we can implement a simple export
        # This could be enhanced later if needed
        data = []
        
        def export_item(item):
            """Export a single tree widget item"""
            item_data = {
                'text': [item.text(i) for i in range(item.columnCount())],
                'checked': item.checkState(0) == Qt.CheckState.Checked,
                'instrument_object': item.data(0, Qt.ItemDataRole.UserRole),
                'children': []
            }
            
            # Export children
            for i in range(item.childCount()):
                child = item.child(i)
                if child:
                    item_data['children'].append(export_item(child))
                    
            return item_data
            
        # Export all top-level items
        root = self.scan_tree.view.invisibleRootItem()
        for i in range(root.childCount()):
            top_level_item = root.child(i)
            if top_level_item:
                data.append(export_item(top_level_item))
                
        return data
        
    def set_scan_tree_data(self, data):
        """Set the scan tree data to QTreeWidget"""
        if not data:
            return
            
        # Clear existing items
        self.scan_tree.view.clear()
        
        def import_item(item_data, parent_item=None):
            """Import a single tree widget item"""
            if parent_item is None:
                item = QTreeWidgetItem(self.scan_tree.view)
            else:
                item = QTreeWidgetItem(parent_item)
                
            # Set text for all columns
            for i, text in enumerate(item_data.get('text', [])):
                item.setText(i, text)
                
            # Set checkbox state
            if item_data.get('checked', False):
                item.setCheckState(0, Qt.CheckState.Checked)
            else:
                item.setCheckState(0, Qt.CheckState.Unchecked)
                
            # Set checkbox flags
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                
            # Set instrument object
            instrument_obj = item_data.get('instrument_object')
            if instrument_obj:
                item.setData(0, Qt.ItemDataRole.UserRole, instrument_obj)
                
            # Import children
            for child_data in item_data.get('children', []):
                import_item(child_data, item)
                
        # Import all items
        for item_data in data:
            import_item(item_data)
            
        # Update movement positions after loading data
        self.update_movement_positions()


def main():
    """Test the ScanPage widget"""
    from PySide6.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    
    # Create main window
    main_window = QMainWindow()
    main_window.setWindowTitle("Scan Page Test")
    main_window.resize(1200, 800)
    
    # Create scan page
    scan_page = ScanPage()
    main_window.setCentralWidget(scan_page)
    
    main_window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
