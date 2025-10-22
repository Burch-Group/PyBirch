# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
from __future__ import annotations

import sys, os
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from PySide6.QtCore import (QAbstractItemModel, QItemSelectionModel,
                            QModelIndex, Qt, Slot, QTimer)
from PySide6.QtWidgets import (QAbstractItemView, QMainWindow, QTreeWidget, QTreeWidgetItem,
                               QWidget, QHeaderView)
from PySide6.QtTest import QAbstractItemModelTester

from PySide6.QtWidgets import QDialog

from treemodel import ScanTreeModel, InstrumentTreeItem

from widgets.available_instrument_widget import AvailableInstrumentWidget

from pybirch.scan.movements import Movement, VisaMovement
from pybirch.scan.measurements import Measurement, VisaMeasurement

from typing import Sequence


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget = None): #type: ignore
        super().__init__(parent)
        self.resize(573, 468)

        self.view = QTreeWidget()
        self.view.setAlternatingRowColors(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setAnimated(False)
        self.view.setAllColumnsShowFocus(True)
        
        # Enable drag and drop for reordering items
        self.view.setDragEnabled(True)
        self.view.setAcceptDrops(True)
        self.view.setDropIndicatorShown(True)
        self.view.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        
        # Connect itemChanged signal for checkbox handling (like instrument_autoload)
        self.view.itemChanged.connect(self.handle_item_changed)
        self.setCentralWidget(self.view)

        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        self.exit_action = file_menu.addAction("&Exit")
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.triggered.connect(self.close)

        actions_menu = menubar.addMenu("&Actions")
        actions_menu.triggered.connect(self.update_actions)
        self.insert_row_action = actions_menu.addAction("Insert Row")
        self.insert_row_action.setShortcut("Ctrl+R")
        self.insert_row_action.triggered.connect(self.insert_row)
        actions_menu.addSeparator()
        self.remove_row_action = actions_menu.addAction("Remove Row")
        self.remove_row_action.setShortcut("Del")
        self.remove_row_action.triggered.connect(self.remove_row)
        actions_menu.addSeparator()
        self.insert_child_action = actions_menu.addAction("Insert Child")
        self.insert_child_action.setShortcut("Ctrl+N")
        self.insert_child_action.triggered.connect(self.insert_child)
        actions_menu.addSeparator()
        self.copy_row_action = actions_menu.addAction("Copy Row")
        self.copy_row_action.setShortcut("Ctrl+C")
        self.copy_row_action.triggered.connect(self.copy_row)
        self.cut_row_action = actions_menu.addAction("Cut Row")
        self.cut_row_action.setShortcut("Ctrl+X")
        self.cut_row_action.triggered.connect(self.cut_row)
        actions_menu.addSeparator()
        self.paste_row_action = actions_menu.addAction("Paste Row")
        self.paste_row_action.setShortcut("Ctrl+V")
        self.paste_row_action.triggered.connect(self.paste_row)
        actions_menu.addSeparator()
        self.select_instrument_action = actions_menu.addAction("Select Instrument")
        self.select_instrument_action.setShortcut("Ctrl+S")
        self.select_instrument_action.triggered.connect(self.select_instrument)
        actions_menu.addSeparator()
        self.select_all_action = actions_menu.addAction("Select All")
        self.select_all_action.setShortcut("Ctrl+A")
        self.select_all_action.triggered.connect(self.select_all_instruments)
        self.deselect_all_action = actions_menu.addAction("Deselect All")
        self.deselect_all_action.setShortcut("Ctrl+D")
        self.deselect_all_action.triggered.connect(self.deselect_all_instruments)
        actions_menu.addSeparator()
        self.show_selected_action = actions_menu.addAction("Show Selected")
        self.show_selected_action.triggered.connect(self.show_selected_instruments)
        help_menu = menubar.addMenu("&Help")
        help_menu.addSeparator()
        about_qt_action = help_menu.addAction("About Qt", qApp.aboutQt)  # noqa: F821  #type: ignore
        about_qt_action.setShortcut("F1")

        self.setWindowTitle("Editable Tree Model")

        # Add right click context menu with same actions as in the menu bar
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self.view.addAction(self.insert_row_action)
        self.view.addAction(self.remove_row_action)
        self.view.addAction(self.insert_child_action)
        self.view.addAction(self.copy_row_action)
        self.view.addAction(self.cut_row_action)
        self.view.addAction(self.paste_row_action)
        self.view.addAction(self.select_instrument_action)
        # Add separator and checkbox actions
        from PySide6.QtGui import QAction
        separator = QAction(self)
        separator.setSeparator(True)
        self.view.addAction(separator)
        self.view.addAction(self.select_all_action)
        self.view.addAction(self.deselect_all_action)
        self.view.addAction(self.show_selected_action)
        self.statusBar().showMessage("Ready")
        

        headers = ["Instrument Name", "Type", "Adapter", "Semaphores"]
        self.view.setHeaderLabels(headers)

        # Apply column sizing approach from adapter_autoload
        # Use ResizeToContents mode for most columns - auto-size to fit their content
        self.view.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        # Set the Semaphores column (column 3) to stretch to fill remaining space
        self.view.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        # Disable cascading section resizes - only the resized column changes size
        self.view.header().setCascadingSectionResizes(False)
        
        # Set initial minimum column widths based on equal spacing
        QTimer.singleShot(0, self.calculate_minimum_column_widths)

        # Initialize with empty tree
        self.view.clear()

        selection_model = self.view.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self.update_actions)

        self.copied_item: QTreeWidgetItem | None = None
        self.cut_item: QTreeWidgetItem | None = None  # Track cut item for deletion

        self.update_actions()
        
    def sync_checkbox_to_tree_item(self, item: QTreeWidgetItem) -> None:
        """Sync QTreeWidgetItem checkbox state to InstrumentTreeItem"""
        try:
            instrument_tree_item = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if instrument_tree_item and hasattr(instrument_tree_item, 'set_checked'):
                is_checked = item.checkState(0) == Qt.CheckState.Checked
                instrument_tree_item.set_checked(is_checked, update_children=False, update_parent=False)
        except Exception as e:
            pass  # Silent fail

    def handle_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle changes in item check states (copied from instrument_autoload)"""
        if column != 0:  # Only handle changes in the first column (checkbox column)
            return
        
        # Sync the checkbox state to InstrumentTreeItem
        self.sync_checkbox_to_tree_item(item)
        
        # Check if this is a user-initiated change on a parent item
        is_parent_item = item.childCount() > 0
        item_state = item.checkState(0)
            
        if is_parent_item:
            # If the item is a parent, update all child items (unless partially checked)
            if item_state != Qt.CheckState.PartiallyChecked:
                for i in range(item.childCount()):
                    child = item.child(i)
                    if child:
                        child.setCheckState(0, item_state)
                        self.sync_checkbox_to_tree_item(child)  # Sync child too
        else:
            # If the item is a child, update the parent folder's state
            parent = item.parent()
            if parent is not None:
                checked_count = sum(1 for i in range(parent.childCount()) 
                                  if parent.child(i) and parent.child(i).checkState(0) == Qt.CheckState.Checked)
                if checked_count == parent.childCount():
                    parent.setCheckState(0, Qt.CheckState.Checked)
                elif checked_count == 0:
                    # Don't automatically uncheck parent when all children are deselected
                    # Keep the parent's current state unchanged
                    pass  # No automatic state change when all children are deselected
                else:
                    parent.setCheckState(0, Qt.CheckState.PartiallyChecked)

        
        self.update_actions()

    @Slot()
    def handle_item_clicked(self, index: QModelIndex) -> None:
        """Legacy method - no longer needed with QTreeWidget"""
        pass

    @Slot()
    def handle_checkbox_toggle(self, index: QModelIndex) -> None:
        """Legacy method - no longer needed with QTreeWidget"""
        pass

    @Slot()
    def insert_child(self) -> None:
        current_item = self.view.currentItem()
        if not current_item:
            current_item = self.view.invisibleRootItem()

        # Select the new instrument using the Available Instrument Widget
        instrument_list = self.get_available_instruments()

        dialog = AvailableInstrumentWidget(instrument_list)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_instrument = dialog.selected_instrument
            if selected_instrument:
                # Create a new tree widget item
                child_item = QTreeWidgetItem(current_item)
                child_item.setText(0, selected_instrument.nickname)
                child_item.setText(1, selected_instrument.__class__.__bases__[0].__name__)
                child_item.setText(2, selected_instrument.adapter)
                child_item.setText(3, "")  # Empty semaphore initially
                
                # Set checkbox functionality
                child_item.setFlags(child_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                child_item.setCheckState(0, Qt.CheckState.Unchecked)
                
                # Store the instrument object as user data
                child_item.setData(0, Qt.ItemDataRole.UserRole, selected_instrument)
                
                # Create and store InstrumentTreeItem object for persistent data
                from .treeitem import InstrumentTreeItem
                instrument_tree_item = InstrumentTreeItem(instrument_object=selected_instrument)
                child_item.setData(0, Qt.ItemDataRole.UserRole + 1, instrument_tree_item)
                
                # Expand the parent item
                current_item.setExpanded(True)
        
        self.update_actions()

    @Slot()
    def insert_row(self) -> None:
        current_item = self.view.currentItem()
        if not current_item:
            # Insert at root level
            parent = self.view.invisibleRootItem()
        else:
            # Insert at same level as current item
            parent = current_item.parent()
            if not parent:
                parent = self.view.invisibleRootItem()

        # Select instrument for the new row
        instrument_list = self.get_available_instruments()
        dialog = AvailableInstrumentWidget(instrument_list)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_instrument = dialog.selected_instrument
            if selected_instrument:
                # Create a new tree widget item
                new_item = QTreeWidgetItem(parent)
                new_item.setText(0, selected_instrument.nickname)
                new_item.setText(1, selected_instrument.__class__.__bases__[0].__name__)
                new_item.setText(2, selected_instrument.adapter)
                new_item.setText(3, "")  # Empty semaphore initially
                
                # Set checkbox functionality
                new_item.setFlags(new_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                new_item.setCheckState(0, Qt.CheckState.Unchecked)
                
                # Store the instrument object as user data
                new_item.setData(0, Qt.ItemDataRole.UserRole, selected_instrument)
                
                # Create and store InstrumentTreeItem object for persistent data
                from .treeitem import InstrumentTreeItem
                instrument_tree_item = InstrumentTreeItem(instrument_object=selected_instrument)
                new_item.setData(0, Qt.ItemDataRole.UserRole + 1, instrument_tree_item)
                
                # Select the new item
                self.view.setCurrentItem(new_item)
        
        self.update_actions()

    def copy_row(self) -> None:
        current_item = self.view.currentItem()
        if current_item:
            self.copied_item = current_item
            self.cut_item = None  # Clear any cut operation

    def cut_row(self) -> None:
        current_item = self.view.currentItem()
        if current_item:
            self.copied_item = current_item
            self.cut_item = current_item  # Mark for deletion on paste

    def paste_row(self) -> None:
        if not self.copied_item:
            return

        current_item = self.view.currentItem()
        if not current_item:
            parent = self.view.invisibleRootItem()
        else:
            parent = current_item.parent()
            if not parent:
                parent = self.view.invisibleRootItem()

        # Clone the copied item
        new_item = self.copied_item.clone()
        parent.addChild(new_item)
        
        # If this was a cut operation, remove the original item
        if self.cut_item and self.cut_item == self.copied_item:
            cut_parent = self.cut_item.parent()
            if cut_parent:
                cut_parent.removeChild(self.cut_item)
            else:
                # Remove from root
                root = self.view.invisibleRootItem()
                root.removeChild(self.cut_item)
            # Clear the cut operation
            self.cut_item = None
        
        self.update_actions()

    @Slot()
    def remove_row(self) -> None:
        current_item = self.view.currentItem()
        if current_item:
            parent = current_item.parent()
            if parent:
                parent.removeChild(current_item)
            else:
                # Remove from root
                root = self.view.invisibleRootItem()
                root.removeChild(current_item)
        self.update_actions()

    @Slot()
    def update_actions(self) -> None:
        current_item = self.view.currentItem()
        has_current = current_item is not None
        
        self.remove_row_action.setEnabled(has_current)
        self.insert_row_action.setEnabled(True)  # Always enabled
        self.copy_row_action.setEnabled(has_current)
        self.cut_row_action.setEnabled(has_current)
        self.paste_row_action.setEnabled(self.copied_item is not None)

        # Update status bar with selected instruments count
        selected_items = self.get_selected_instruments()
        selected_count = len(selected_items)
        if selected_count == 0:
            self.statusBar().showMessage("Ready - No instruments selected")
        elif selected_count == 1:
            self.statusBar().showMessage(f"Ready - 1 instrument selected")
        else:
            self.statusBar().showMessage(f"Ready - {selected_count} instruments selected")

    @Slot()
    def select_instrument(self) -> None:
        current_item = self.view.currentItem()
        if not current_item:
            return

        instrument_data = self.get_available_instruments()
        dialog = AvailableInstrumentWidget(instrument_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_instrument_object = dialog.selected_instrument
            if selected_instrument_object:
                # Update the current item with the new instrument
                current_item.setText(0, selected_instrument_object.nickname)
                current_item.setText(1, selected_instrument_object.__class__.__bases__[0].__name__)
                current_item.setText(2, selected_instrument_object.adapter)
                # Keep existing semaphore value in column 3
                
                # Set checkbox functionality if not already set
                current_item.setFlags(current_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                if current_item.checkState(0) == Qt.CheckState.Unchecked and current_item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                    pass  # Keep current state
                else:
                    current_item.setCheckState(0, Qt.CheckState.Unchecked)
                
                # Store the instrument object as user data
                current_item.setData(0, Qt.ItemDataRole.UserRole, selected_instrument_object)
                
                # Create and store InstrumentTreeItem object for persistent data
                from .treeitem import InstrumentTreeItem
                instrument_tree_item = InstrumentTreeItem(instrument_object=selected_instrument_object)
                current_item.setData(0, Qt.ItemDataRole.UserRole + 1, instrument_tree_item)

    def get_selected_instruments(self) -> list:
        """Return a list of selected (checked) instruments (copied from instrument_autoload pattern)"""
        selected_instruments = []

        def traverse(item: QTreeWidgetItem):
            if item.checkState(0) == Qt.CheckState.Checked:
                # Get the instrument object from user data
                instrument_obj = item.data(0, Qt.ItemDataRole.UserRole)
                if instrument_obj:
                    selected_instruments.append(instrument_obj)
            
            # Traverse children
            for i in range(item.childCount()):
                child = item.child(i)
                if child:
                    traverse(child)

        root = self.view.invisibleRootItem()
        traverse(root)
        return selected_instruments

    @Slot()
    def select_all_instruments(self) -> None:
        """Select all instruments in the tree"""
        def set_all_checked(item: QTreeWidgetItem, checked: bool):
            for i in range(item.childCount()):
                child = item.child(i)
                if child:
                    # Only set checkbox for items that have instruments (user data)
                    instrument_obj = child.data(0, Qt.ItemDataRole.UserRole)
                    if instrument_obj:
                        child.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                    set_all_checked(child, checked)

        root = self.view.invisibleRootItem()
        set_all_checked(root, True)

    @Slot()
    def deselect_all_instruments(self) -> None:
        """Deselect all instruments in the tree"""
        def set_all_checked(item: QTreeWidgetItem, checked: bool):
            for i in range(item.childCount()):
                child = item.child(i)
                if child:
                    # Only set checkbox for items that have instruments (user data)
                    instrument_obj = child.data(0, Qt.ItemDataRole.UserRole)
                    if instrument_obj:
                        child.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                    set_all_checked(child, checked)

        root = self.view.invisibleRootItem()
        set_all_checked(root, False)

    @Slot()
    def show_selected_instruments(self) -> None:
        """Show a message box with the selected instruments"""
        from PySide6.QtWidgets import QMessageBox
        
        selected_items = self.get_selected_instruments()
        if not selected_items:
            QMessageBox.information(self, "Selected Instruments", "No instruments are currently selected.")
            return
        
        message = f"Selected {len(selected_items)} instrument(s):\n\n"
        for item in selected_items:
            message += f"• {item.nickname} ({item.__class__.__bases__[0].__name__}) - {item.adapter}\n"
        
        QMessageBox.information(self, "Selected Instruments", message)

    def calculate_minimum_column_widths(self):
        """Calculate minimum column widths based on equal spacing, with Semaphores column getting half space."""
        if self.view.width() > 0:
            # Calculate available width
            tree_width = self.view.width()
            available_width = tree_width - 50  # Reserve space for scrollbar/margins
            
            if available_width > 0:
                # Calculate base unit
                total_units = self.view.columnCount()
                base_width = available_width / total_units
                
                # Set minimum widths
                regular_min_width = int(base_width)
                
                # Apply individual minimum widths to columns 0-3
                for col in range(4):
                    self.view.header().setMinimumSectionSize(regular_min_width)
                    self.view.setColumnWidth(col, regular_min_width)
                
    def resizeEvent(self, event):
        """Handle widget resize events to recalculate minimum column sizes."""
        super().resizeEvent(event)
        # Recalculate minimum column widths when the widget is resized
        QTimer.singleShot(0, self.calculate_minimum_column_widths)

    def get_available_instruments(self) -> Sequence[Movement | VisaMovement | Measurement | VisaMeasurement]:
        # Placeholder for actual instrument retrieval logic
        
        instrument_objects = [
            Measurement('Keithley 2400'),
            Measurement('Agilent 34401A'),
            Measurement('Tektronix TDS2024C'),
            Movement('Newport XPS Series'),
            Movement('Thorlabs K-Cube'),
            Measurement('Yokogawa GS200')
        ]

        return instrument_objects
    

