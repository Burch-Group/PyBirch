# Copyright (C) 2025
# Scan Page Widget for PyBirch
from __future__ import annotations

import sys
import os
import logging
from typing import Optional, List

# Configure module logger
logger = logging.getLogger(__name__)

# Add path to parent directories for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from PySide6.QtCore import Qt, QModelIndex, Signal, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                               QScrollArea, QFrame, QTreeWidgetItem, QStackedWidget)

# Import theme
try:
    from GUI.theme import Theme, apply_theme
except ImportError:
    from theme import Theme, apply_theme


class ScanTreeFrame(QFrame):
    """Custom frame that handles resize events for the embedded scan tree."""
    
    def __init__(self, scan_tree_main_window):
        super().__init__()
        self.scan_tree = scan_tree_main_window
        
    def resizeEvent(self, event):
        """Handle resize events and trigger column resize for scan tree."""
        super().resizeEvent(event)
        # Trigger the scan tree's column width recalculation when the frame is resized
        if hasattr(self.scan_tree, 'calculate_minimum_column_widths'):
            QTimer.singleShot(0, self.scan_tree.calculate_minimum_column_widths)

# Import the required widgets
from widgets.scan_title_bar import ScanTitleBar
from widgets.scan_tree.mainwindow import ScanTreeWidget as ScanTreeMainWindow
from widgets.movement_positions import MovementPositionsWidget
from pybirch.scan.scan import Scan, get_empty_scan
from pybirch.scan.movements import Movement, VisaMovement
from pybirch.scan.measurements import Measurement, VisaMeasurement

# Import scan info page
try:
    from windows.scan_info_page import ScanInfoPage
except ImportError:
    from GUI.windows.scan_info_page import ScanInfoPage


class ScanPage(QWidget):
    """
    Main scan page widget that combines:
    - ScanTitleBar at the top
    - ScanTreeMainWindow on the left
    - MovementPositions widgets on the right (for movement instruments only)
    """
    
    # Signal emitted when movement instruments are selected/deselected
    movement_instruments_changed = Signal(list)
    
    # Signal emitted when scan info is changed (name, job type, etc.)
    scan_info_changed = Signal()
    
    def __init__(self, scan: Optional[Scan] = None, parent: Optional[QWidget] = None, 
                 available_instruments: Optional[List] = None):
        """
        Initialize scan page.
        
        Args:
            scan: The scan object to display/edit
            parent: Parent widget
            available_instruments: Optional list of configured instruments from adapter manager.
                                 Each item is a dict with keys: 'name', 'adapter', 'nickname', 'class', 'instance'
        """
        super().__init__(parent)
        
        # Use provided scan or create empty one
        self.scan = scan if scan is not None else get_empty_scan()
        
        # Store configured instruments for passing to scan tree
        self.available_instruments = available_instruments
        
        # Track movement instruments currently displayed
        self.current_movement_instruments: List[str] = []
        
        # Flag to prevent multiple simultaneous updates
        self._updating_movement_positions = False
        
        # Flag to prevent saving during tree loading
        self._loading_tree = False
        
        self.init_ui()
        self.connect_signals()
        
        # Load tree state from scan if available
        self.load_tree_from_scan()
        
    def init_ui(self):
        """Initialize the user interface"""
        # Main vertical layout with 20pt margins
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)  # 20pt margins on all sides
        main_layout.setSpacing(0)
        
        # Create scan title bar with scan name if available
        initial_title = self.scan.scan_settings.scan_name if self.scan.scan_settings.scan_name else "Scan"
        self.title_bar = ScanTitleBar(self.scan, title=initial_title)
        main_layout.addWidget(self.title_bar)
        
        # Create stacked widget to switch between scan tree and scan info
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)
        
        # Page 0: Scan tree and movement positions splitter
        self.scan_tree_page = QWidget()
        scan_tree_page_layout = QVBoxLayout(self.scan_tree_page)
        scan_tree_page_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create horizontal splitter for scan tree and movement positions
        self.splitter = QSplitter()
        self.splitter.setOrientation(Qt.Orientation.Horizontal)
        
        # Set 20pt spacing between the two widgets in the splitter
        self.splitter.setHandleWidth(20)  # Set the handle width to 20pt for spacing
        
        scan_tree_page_layout.addWidget(self.splitter)

        
        # Create scan tree widget (left side) with configured instruments
        self.scan_tree = ScanTreeMainWindow(available_instruments=self.available_instruments)
        self.scan_tree.setWindowTitle("")  # Remove window title since it's embedded
        
        # Remove the menu bar and status bar for embedded use
        self.scan_tree.menuBar().hide()
        self.scan_tree.statusBar().hide()
        
        # Create a custom frame to contain the scan tree that handles resize events
        scan_tree_frame = ScanTreeFrame(self.scan_tree)
        scan_tree_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        scan_tree_layout = QVBoxLayout(scan_tree_frame)
        scan_tree_layout.setContentsMargins(10, 10, 10, 10)  # 10pt margins
        scan_tree_layout.addWidget(self.scan_tree.view)  # Add just the tree view
        
        # Store reference to frame for resize handling
        self.scan_tree_frame = scan_tree_frame
        
        self.splitter.addWidget(scan_tree_frame)
        
        # Create movement positions container (right side)
        self.movement_container = QFrame()
        self.movement_container.setFrameStyle(QFrame.Shape.StyledPanel)
        self.movement_layout = QVBoxLayout(self.movement_container)
        self.movement_layout.setContentsMargins(10, 10, 10, 10)  # 10pt margins
        self.movement_layout.setSpacing(5)
        
        # Create scroll area for movement positions
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Widget to contain all movement position widgets
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(10, 10, 10, 10)  # 10pt margins
        self.scroll_layout.setSpacing(5)
        self.scroll_layout.addStretch()  # Push widgets to top
        
        self.scroll_area.setWidget(self.scroll_widget)
        self.movement_layout.addWidget(self.scroll_area)
        
        self.splitter.addWidget(self.movement_container)
        
        # Set initial splitter sizes to equal (50% scan tree, 50% movement positions)
        self.splitter.setStretchFactor(0, 50)
        self.splitter.setStretchFactor(1, 50)
        
        # Store movement position widgets
        self.movement_widgets: dict[str, MovementPositionsWidget] = {}
        
        # Add scan tree page to stacked widget
        self.stacked_widget.addWidget(self.scan_tree_page)
        
        # Page 1: Scan info page
        self.scan_info_page = ScanInfoPage(self.scan, parent=self)
        self.stacked_widget.addWidget(self.scan_info_page)
        
        # Start with scan tree page visible
        self.stacked_widget.setCurrentIndex(0)
        
    def connect_signals(self):
        """Connect signals between components"""
        # Connect title bar info button to show scan info page
        self.title_bar.info_clicked.connect(self.show_scan_info_page)
        
        # Connect title bar preset loaded signal
        self.title_bar.scan_preset_loaded.connect(self.on_scan_preset_loaded)
        
        # Connect title bar save state requested signal to save tree before preset operations
        self.title_bar.save_state_requested.connect(self.save_tree_to_scan)
        
        # Connect scan info page signals
        self.scan_info_page.cancelled.connect(self.show_scan_tree_page)
        self.scan_info_page.done.connect(self.on_scan_info_done)
        
        # Connect scan tree selection changes to update movement positions
        if self.scan_tree.view.selectionModel():
            self.scan_tree.view.selectionModel().selectionChanged.connect(
                self.on_scan_tree_selection_changed
            )
            
        # Connect tree widget changes to update movement positions and save tree state
        # This is the key signal for checkbox changes
        self.scan_tree.view.itemChanged.connect(self.on_item_changed)
        self.scan_tree.view.itemChanged.connect(self.save_tree_to_scan)
        
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
                QTimer.singleShot(100, self.save_tree_to_scan)
            self.scan_tree.insert_child = patched_insert_child
            
        if hasattr(self.scan_tree, 'insert_row'):
            original_insert_row = self.scan_tree.insert_row
            def patched_insert_row():
                original_insert_row()
                from PySide6.QtCore import QTimer
                QTimer.singleShot(100, self.update_movement_positions)
                QTimer.singleShot(100, self.save_tree_to_scan)
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
    
    def show_scan_info_page(self):
        """Switch to the scan info page"""
        # Load current scan data into the info page
        self.scan_info_page.load_from_scan(self.scan)
        # Switch to scan info page (index 1)
        self.stacked_widget.setCurrentIndex(1)
    
    def show_scan_tree_page(self):
        """Switch back to the scan tree page"""
        # Switch to scan tree page (index 0)
        self.stacked_widget.setCurrentIndex(0)
    
    def on_scan_info_done(self):
        """Handle when user clicks done on the scan info page"""
        # The scan info page's on_done method already saves to scan.scan_settings
        # Update the title bar with the new scan name
        scan_name = self.scan.scan_settings.scan_name
        self.title_bar.set_title(scan_name if scan_name else "Scan")
        # Emit signal to notify that scan info has changed
        self.scan_info_changed.emit()
        # Switch back to the scan tree page
        self.show_scan_tree_page()
    
    def on_scan_preset_loaded(self, scan):
        """Handle when a scan preset is loaded from the title bar"""
        # Update the scan reference
        self.scan = scan
        
        # Update title bar with new scan name
        scan_name = self.scan.scan_settings.scan_name if self.scan.scan_settings else "Scan"
        self.title_bar.set_title(scan_name if scan_name else "Scan")
        self.title_bar.scan = scan
        
        # Update scan info page
        self.scan_info_page.scan = scan
        self.scan_info_page.load_from_scan(scan)
        
        # Load tree state from the new scan
        self.load_tree_from_scan()
        
        # Emit signal to notify that scan info has changed
        self.scan_info_changed.emit()
    
    def load_tree_from_scan(self):
        """Load tree state from the scan object if available."""
        if hasattr(self.scan, 'tree_state') and self.scan.tree_state:
            # Set loading flag to prevent save operations during load
            self._loading_tree = True
            
            # Clear existing movement widgets before loading
            for unique_id in list(self.movement_widgets.keys()):
                widget = self.movement_widgets.pop(unique_id)
                self.scroll_layout.removeWidget(widget)
                widget.deleteLater()
            
            self.scan_tree.load_tree_state(self.scan.tree_state)
            
            # Clear loading flag
            self._loading_tree = False
            
            # Update movement positions after loading tree
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self.update_movement_positions)
    
    def save_tree_to_scan(self):
        """Save the current tree state to the scan object."""
        # Skip saving during tree loading to prevent overwriting restored data
        if self._loading_tree:
            return
            
        # First, save all current widget settings to their respective tree items
        self.save_all_widget_settings()
        # Then save the tree state
        self.scan.tree_state = self.scan_tree.save_tree_state()
        logger.debug("save_tree_to_scan: Saved tree_state with %d items", len(self.scan.tree_state))
        for item in self.scan.tree_state:
            logger.debug("  Item: %s, movement_entries: %s", item.get('name'), item.get('movement_entries'))
        
        # Also sync to scan_settings.scan_tree for execution
        self.sync_tree_to_scan_settings()
    
    def sync_tree_to_scan_settings(self):
        """
        Sync the GUI tree state to scan_settings.scan_tree for scan execution.
        
        This builds the ScanTreeModel with InstrumentTreeItem objects that have
        actual instrument instances attached.
        """
        from GUI.widgets.scan_tree.treemodel import ScanTreeModel
        from GUI.widgets.scan_tree.treeitem import InstrumentTreeItem
        from pybirch.scan.movements import MovementItem
        from pybirch.scan.measurements import MeasurementItem
        from pybirch.scan.protocols import is_movement
        import numpy as np
        
        logger.debug("sync_tree_to_scan_settings: Starting sync")
        
        # Create a new ScanTreeModel
        scan_tree_model = ScanTreeModel()
        
        def build_tree_item(item_data: dict, parent: InstrumentTreeItem | None = None) -> InstrumentTreeItem:
            """Build InstrumentTreeItem from GUI tree state dict."""
            # Get instrument info
            instr_name = item_data.get('instrument_name', item_data.get('name', ''))
            instr_nickname = item_data.get('instrument_nickname', item_data.get('name', ''))
            instr_adapter = item_data.get('instrument_adapter', item_data.get('adapter', ''))
            instr_type = item_data.get('type', '')
            
            # Find matching configured instrument
            instrument_object = None
            for inst_config in self.available_instruments:
                config_name = inst_config.get('name', '')
                config_nickname = inst_config.get('nickname', '')
                config_adapter = inst_config.get('adapter', '')
                
                # Match by name, nickname, or adapter
                if (config_name == instr_name or 
                    config_nickname == instr_name or
                    config_name == instr_nickname or
                    config_nickname == instr_nickname or
                    (config_adapter and config_adapter == instr_adapter)):
                    
                    instance = inst_config.get('instance')
                    if instance:
                        # Create wrapper based on instrument type
                        settings = item_data.get('movement_entries', {}).get('settings', {})
                        
                        if is_movement(instance):
                            positions = item_data.get('movement_positions', [])
                            if isinstance(positions, list):
                                positions = np.array(positions)
                            instrument_object = MovementItem(instance, positions=positions, settings=settings)
                            
                            # Also set final_indices based on positions
                            if len(positions) > 0:
                                final_indices = [len(positions) - 1]
                            else:
                                final_indices = []
                        else:
                            instrument_object = MeasurementItem(instance, settings=settings)
                            final_indices = [0]
                        
                        logger.debug(f"  Matched '{instr_name}' to {type(instance).__name__}")
                        break
            
            # Create InstrumentTreeItem
            tree_item = InstrumentTreeItem(
                parent=parent,
                instrument_object=instrument_object,
                indices=[0] if instrument_object else [],
                final_indices=final_indices if instrument_object else [],
                semaphore=item_data.get('semaphore', '')
            )
            tree_item.name = instr_nickname or instr_name
            tree_item.type = instr_type
            tree_item.adapter = instr_adapter
            tree_item.movement_positions = item_data.get('movement_positions', [])
            tree_item.movement_entries = item_data.get('movement_entries', {})
            tree_item.checked = item_data.get('check_state', 0) == 2  # Qt.Checked = 2
            
            # Build children
            for child_data in item_data.get('children', []):
                child_item = build_tree_item(child_data, tree_item)
                tree_item.child_items.append(child_item)
            
            return tree_item
        
        # Build tree from state
        if hasattr(self.scan, 'tree_state') and self.scan.tree_state:
            for item_data in self.scan.tree_state:
                child_item = build_tree_item(item_data, scan_tree_model.root_item)
                scan_tree_model.root_item.child_items.append(child_item)
        
        # Update scan_settings.scan_tree
        self.scan.scan_settings.scan_tree = scan_tree_model
        
        logger.debug(f"sync_tree_to_scan_settings: Built tree with {len(scan_tree_model.root_item.child_items)} top-level items")
    
    def save_all_widget_settings(self):
        """Save settings from all movement widgets to their respective tree items."""
        logger.debug("save_all_widget_settings: %d widgets to save", len(self.movement_widgets))
        for unique_id, widget in self.movement_widgets.items():
            tree_item = getattr(widget, 'tree_item', None)
            if tree_item:
                logger.debug("  Saving widget %s", unique_id)
                self.save_movement_settings_to_tree_item(tree_item, widget)
        
    def update_movement_positions(self):
        """Update the movement positions widgets based on scan tree content"""
        # Prevent re-entrant calls
        if self._updating_movement_positions:
            return
        
        # Skip updates during tree loading - will be called after load completes
        if self._loading_tree:
            return
            
        self._updating_movement_positions = True
        
        try:
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
                    if not instrument_tree_item:
                        # Create new InstrumentTreeItem if it doesn't exist
                        from widgets.scan_tree.treeitem import InstrumentTreeItem
                        from pybirch.scan.movements import MovementItem
                        from pybirch.scan.measurements import MeasurementItem
                        
                        # Wrap raw instrument in appropriate Item wrapper
                        if isinstance(instrument_obj, (Movement, VisaMovement)):
                            wrapped_instrument = MovementItem(instrument_obj, settings={})
                        else:
                            wrapped_instrument = MeasurementItem(instrument_obj, settings={})
                        
                        instrument_tree_item = InstrumentTreeItem(
                            parent=None,
                            instrument_object=wrapped_instrument
                        )
                        tree_item.setData(0, Qt.ItemDataRole.UserRole + 1, instrument_tree_item)
                    
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
        finally:
            self._updating_movement_positions = False
        
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
            
            # Save current widget state
            positions = widget.get_positions()
            entries = widget.get_entries()
            print(f"[ScanPage] save_movement_settings_to_tree_item: name={tree_item.text(0)}")
            print(f"[ScanPage]   positions count: {len(positions)}")
            print(f"[ScanPage]   entries: {entries}")
            logger.debug("save_movement_settings_to_tree_item: entries=%s", entries)
            
            if instrument_tree_item:
                instrument_tree_item.movement_positions = positions
                instrument_tree_item.movement_entries = entries
                logger.debug("  Saved to existing instrument_tree_item")
            else:
                # Try to create one if it doesn't exist
                instrument_obj = tree_item.data(0, Qt.ItemDataRole.UserRole)
                if instrument_obj:
                    from widgets.scan_tree.treeitem import InstrumentTreeItem
                    from pybirch.scan.movements import MovementItem
                    from pybirch.scan.measurements import MeasurementItem
                    
                    # Wrap raw instrument in appropriate Item wrapper
                    if isinstance(instrument_obj, (Movement, VisaMovement)):
                        wrapped_instrument = MovementItem(instrument_obj, settings={})
                    else:
                        wrapped_instrument = MeasurementItem(instrument_obj, settings={})
                    
                    instrument_tree_item = InstrumentTreeItem(
                        parent=None,
                        instrument_object=wrapped_instrument
                    )
                    # Save the settings
                    positions = widget.get_positions()
                    entries = widget.get_entries()
                    instrument_tree_item.movement_positions = positions
                    instrument_tree_item.movement_entries = entries
                    
                    tree_item.setData(0, Qt.ItemDataRole.UserRole + 1, instrument_tree_item)
        except Exception as e:
            logger.warning("Error saving movement settings: %s", e)
            
    def restore_movement_settings_from_tree_item(self, tree_item, widget):
        """Restore movement position settings from the InstrumentTreeItem"""
        try:
            # Get the InstrumentTreeItem object from the QTreeWidgetItem
            instrument_tree_item = tree_item.data(0, Qt.ItemDataRole.UserRole + 1)
            logger.debug("restore_movement_settings: instrument_tree_item=%s", instrument_tree_item)
            
            if instrument_tree_item:
                # Restore settings if they exist
                logger.debug("  movement_entries: %s", getattr(instrument_tree_item, 'movement_entries', None))
                if hasattr(instrument_tree_item, 'movement_entries') and instrument_tree_item.movement_entries:
                    logger.debug("  Calling widget.set_entries with: %s", instrument_tree_item.movement_entries)
                    widget.set_entries(instrument_tree_item.movement_entries)
            else:
                # Try to create one if it doesn't exist
                instrument_obj = tree_item.data(0, Qt.ItemDataRole.UserRole)
                if instrument_obj:
                    from widgets.scan_tree.treeitem import InstrumentTreeItem
                    from pybirch.scan.movements import MovementItem
                    from pybirch.scan.measurements import MeasurementItem
                    
                    # Wrap raw instrument in appropriate Item wrapper
                    if isinstance(instrument_obj, (Movement, VisaMovement)):
                        wrapped_instrument = MovementItem(instrument_obj, settings={})
                    else:
                        wrapped_instrument = MeasurementItem(instrument_obj, settings={})
                    
                    instrument_tree_item = InstrumentTreeItem(
                        parent=None,
                        instrument_object=wrapped_instrument
                    )
                    tree_item.setData(0, Qt.ItemDataRole.UserRole + 1, instrument_tree_item)
        except Exception as e:
            print(f"Error restoring movement settings: {e}")  # Debug
            

            
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

    def resizeEvent(self, event):
        """Handle resize events and trigger column resize for embedded scan tree."""
        super().resizeEvent(event)
        # Trigger the scan tree's column width recalculation when the page is resized
        if hasattr(self, 'scan_tree') and hasattr(self.scan_tree, 'calculate_minimum_column_widths'):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self.scan_tree.calculate_minimum_column_widths)


def main():
    """Test the ScanPage widget"""
    from PySide6.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    apply_theme(app)
    
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
