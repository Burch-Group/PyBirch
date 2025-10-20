# Copyright (C) 2025
# User Fields Main Window for PyBirch
from __future__ import annotations

import sys
from pathlib import Path
import json

from typing import Optional

from PySide6.QtCore import QModelIndex, Qt, Slot
from PySide6.QtWidgets import (QAbstractItemView, QMainWindow, QTreeView,
                               QWidget, QInputDialog, QMessageBox, QDialog,
                               QFileDialog)
from PySide6.QtTest import QAbstractItemModelTester

from treemodel import UserFieldTreeModel, UserFieldTreeItem


class UserFieldMainWindow(QMainWindow):
    def __init__(self, parent: Optional[QWidget] = None, dict: dict = {}):
        super().__init__(parent)
        self.resize(600, 400)

        self.view = QTreeView()
        self.view.setAlternatingRowColors(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setAnimated(False)
        self.view.setAllColumnsShowFocus(True)
        self.setCentralWidget(self.view)

        # Create menu bar
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        self.exit_action = file_menu.addAction("&Exit")
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.triggered.connect(self.close)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        edit_menu.triggered.connect(self.update_actions)
        
        self.insert_row_action = edit_menu.addAction("Insert Row")
        self.insert_row_action.setShortcut("Ctrl+R")
        self.insert_row_action.triggered.connect(self.insert_row)
        
        edit_menu.addSeparator()
        
        self.remove_row_action = edit_menu.addAction("Remove Row")
        self.remove_row_action.setShortcut("Del")
        self.remove_row_action.triggered.connect(self.remove_row)
        
        edit_menu.addSeparator()
        
        self.insert_child_action = edit_menu.addAction("Insert Child")
        self.insert_child_action.setShortcut("Ctrl+N")
        self.insert_child_action.triggered.connect(self.insert_child)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        help_menu.addSeparator()
        about_qt_action = help_menu.addAction("About Qt", lambda: QMessageBox.aboutQt(self))
        about_qt_action.setShortcut("F1")

        self.setWindowTitle("User Fields Editor")

        # Add right-click context menu with same actions as in the menu bar
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self.view.addAction(self.insert_row_action)
        self.view.addAction(self.remove_row_action)
        self.view.addAction(self.insert_child_action)
        
        self.statusBar().showMessage("Ready")

        # Create the model
        headers = ["Title", "Value"]
        self.model = UserFieldTreeModel(headers, parent=self)

        if dict:
            self.model.from_dict(dict)
        else:
            # Add some sample data
            self.model.insertUserFields(0, ["Sample Field 1"], ["Value 1"])
        
        # Set up the view
        if "-t" in sys.argv:
            QAbstractItemModelTester(self.model, self)
        self.view.setModel(self.model)
        self.view.expandAll()

        for column in range(len(headers)):
            self.view.resizeColumnToContents(column)

        # Remove sample data
        if not dict:
            self.model.removeRows(0, self.model.rowCount())

        selection_model = self.view.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self.update_actions)

        self.update_actions()

    def get_title_from_user(self, current_title: str = "") -> str:
        """Show input dialog to get title from user"""
        title, ok = QInputDialog.getText(
            self, 
            "Enter Title", 
            "Title:", 
            text=current_title
        )
        if ok and title.strip():
            return title.strip()
        return ""

    @Slot()
    def insert_child(self) -> None:
        selection_model = self.view.selectionModel()
        if not selection_model:
            return
            
        index: QModelIndex = selection_model.currentIndex()
        
        # Get title from user
        title = self.get_title_from_user()
        if not title:
            return

        # Insert the child
        if not self.model.insertUserFields(0, [title], [""], index):
            return
            
        self.view.expand(index)
        self.update_actions()

    @Slot()
    def insert_row(self) -> None:
        selection_model = self.view.selectionModel()
        if not selection_model:
            return
            
        index: QModelIndex = selection_model.currentIndex()
        parent: QModelIndex = index.parent()

        # Get title from user
        title = self.get_title_from_user()
        if not title:
            return

        # Insert row after current row
        row = index.row() + 1 if index.isValid() else 0
        if not self.model.insertUserFields(row, [title], [""], parent):
            return

        self.update_actions()

        # Select the new row
        new_index = self.model.index(row, 0, parent)
        if selection_model and new_index.isValid():
            self.view.setCurrentIndex(new_index)

    @Slot()
    def remove_row(self) -> None:
        selection_model = self.view.selectionModel()
        if not selection_model:
            return
            
        index: QModelIndex = selection_model.currentIndex()
        if not index.isValid():
            return

        # Confirm deletion
        item = self.model.get_item(index)
        reply = QMessageBox.question(
            self, 
            "Confirm Delete", 
            f"Are you sure you want to delete '{item.title}' and all its children?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.model.removeRow(index.row(), index.parent()):
                self.update_actions()

    @Slot()
    def update_actions(self) -> None:
        selection_model = self.view.selectionModel()
        if not selection_model:
            return
            
        has_selection: bool = not selection_model.selection().isEmpty()
        self.remove_row_action.setEnabled(has_selection)

        current_index = selection_model.currentIndex()
        has_current: bool = current_index.isValid()
        self.insert_row_action.setEnabled(True)  # Always allow inserting rows
        self.insert_child_action.setEnabled(True)  # Always allow inserting children

        if has_current:
            self.view.closePersistentEditor(current_index)
            item = self.model.get_item(current_index)
            msg = f"Selected: {item.title}"
            self.statusBar().showMessage(msg)
        else:
            self.statusBar().showMessage("Ready")

    def to_dict(self) -> dict:
        """Export the current tree structure to a dictionary"""
        return self.model.to_dict()

    def from_dict(self, data: dict) -> bool:
        """Import tree structure from a dictionary"""
        success = self.model.from_dict(data)
        if success:
            self.view.expandAll()
            for column in range(self.model.columnCount()):
                self.view.resizeColumnToContents(column)
        return success

    def clear_all(self) -> None:
        """Clear all data from the tree"""
        self.model.clear()

    def export_to_json_string(self) -> str:
        """Export the tree structure to a JSON string"""
        data = self.to_dict()
        return json.dumps(data, indent=2)

    def import_from_json_string(self, json_string: str) -> bool:
        """Import tree structure from a JSON string"""
        try:
            data = json.loads(json_string)
            return self.from_dict(data)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            return False