# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
from __future__ import annotations

import sys, os
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from PySide6.QtCore import (QAbstractItemModel, QItemSelectionModel,
                            QModelIndex, Qt, Slot)
from PySide6.QtWidgets import (QAbstractItemView, QMainWindow, QTreeView,
                               QWidget)
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

        self.view = QTreeView()
        self.view.setAlternatingRowColors(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setAnimated(False)
        self.view.setAllColumnsShowFocus(True)
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
        self.copy_row_action = actions_menu.addAction("Copy Row")  # Placeholder for future functionality
        self.copy_row_action.setShortcut("Ctrl+C")
        self.copy_row_action.triggered.connect(self.copy_row)
        actions_menu.addSeparator()
        self.paste_row_action = actions_menu.addAction("Paste Row")  # Placeholder for future functionality
        self.paste_row_action.setShortcut("Ctrl+V")
        self.paste_row_action.triggered.connect(self.paste_row)
        actions_menu.addSeparator()
        self.select_instrument_action = actions_menu.addAction("Select Instrument")
        self.select_instrument_action.setShortcut("Ctrl+S")
        self.select_instrument_action.triggered.connect(self.select_instrument)
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
        self.view.addAction(self.paste_row_action)
        self.view.addAction(self.select_instrument_action)
        self.statusBar().showMessage("Ready")
        

        headers = ["Instrument Name", "Type", "Adapter"]

        file = Path(__file__).parent / "default.txt"
        self.model = ScanTreeModel(headers, parent=self)

        if "-t" in sys.argv:
            QAbstractItemModelTester(self.model, self)
        self.view.setModel(self.model)
        self.view.expandAll()

        for column in range(len(headers)):
            self.view.resizeColumnToContents(column)

        selection_model = self.view.selectionModel()
        selection_model.selectionChanged.connect(self.update_actions)

        self.copied_item: InstrumentTreeItem | None = None

        self.update_actions()

    @Slot()
    def insert_child(self) -> None:
        selection_model = self.view.selectionModel()
        index: QModelIndex = selection_model.currentIndex()
        model = self.view.model()  # This is our ScanTreeModel
        assert isinstance(model, ScanTreeModel)  # Runtime check for type safety

        # Select the new instrument using the Available Instrument Widget. Insert as the first child of the current item, in both the ScanTreeModel and the view.
        instrument_list = self.get_available_instruments()

        dialog = AvailableInstrumentWidget(instrument_list)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_instrument = dialog.selected_instrument
            # create a child item in the model with the selected instrument name and adapter
            if selected_instrument:
                if not model.insertInstruments(0, [selected_instrument], index):
                    return
                # The instrument object is already set during insertInstruments, no need to call setData
            self.view.expand(index)
        self.update_actions()

    def tree_item_from_index(self, index: QModelIndex) -> InstrumentTreeItem:
        if index.isValid():
            item: InstrumentTreeItem = index.internalPointer()  # type: ignore
            if item:
                return item

        return self.model.root_item

    def index_from_tree_item(self, item: InstrumentTreeItem) -> QModelIndex:
        if item == self.model.root_item:
            return QModelIndex()

        parent_item = item.parent()
        if not parent_item:
            return QModelIndex()

        parent_index = self.index_from_tree_item(parent_item)
        row = parent_item.child_items.index(item)

        return self.model.index(row, 0, parent_index)
    

    @Slot()
    def insert_row(self) -> None:
        index: QModelIndex = self.view.selectionModel().currentIndex()
        model: QAbstractItemModel = self.view.model()
        parent: QModelIndex = index.parent()

        if not model.insertRow(index.row() + 1, parent):
            return

        self.update_actions()

        for column in range(model.columnCount(parent)):
            child: QModelIndex = model.index(index.row() + 1, column, parent)
            model.setData(child, "[No data]", Qt.ItemDataRole.EditRole)

        # Select instrument for the new row
        new_index = model.index(index.row() + 1, 0, parent)
        self.view.setCurrentIndex(new_index)
        self.select_instrument()
        self.update_actions()

    def copy_row(self) -> None:
        index: QModelIndex = self.view.selectionModel().currentIndex()
        if not index.isValid():
            return
        self.copied_item = self.tree_item_from_index(index)

    def paste_row(self) -> None:
        if not self.copied_item:
            return

        index: QModelIndex = self.view.selectionModel().currentIndex()
        if not index.isValid():
            return

        model: QAbstractItemModel = self.view.model()
        parent: QModelIndex = index.parent()

        # Insert a new row at the current index position
        if not model.insertRow(index.row(), parent):
            return

        # Copy data from the copied item to the new row
        for column in range(model.columnCount(parent)):
            child: QModelIndex = model.index(index.row(), column, parent)
            data = self.copied_item.columns[column] if column < len(self.copied_item.columns) else "[No data]"
            model.setData(child, data, Qt.ItemDataRole.EditRole)
            # If the copied item has an associated instrument object, set it in the new row
            if column == 0 and self.copied_item.instrument_object:
                self.tree_item_from_index(child).set_data(self.copied_item.instrument_object)


        self.update_actions()

    @Slot()
    def remove_column(self) -> None:
        model: QAbstractItemModel = self.view.model()
        column: int = self.view.selectionModel().currentIndex().column()

        if model.removeColumn(column):
            self.update_actions()

    @Slot()
    def remove_row(self) -> None:
        index: QModelIndex = self.view.selectionModel().currentIndex()
        model: QAbstractItemModel = self.view.model()

        if model.removeRow(index.row(), index.parent()):
            self.update_actions()

    @Slot()
    def update_actions(self) -> None:
        selection_model = self.view.selectionModel()
        has_selection: bool = not selection_model.selection().isEmpty()
        self.remove_row_action.setEnabled(has_selection)

        current_index = selection_model.currentIndex()
        has_current: bool = current_index.isValid()
        self.insert_row_action.setEnabled(has_current)

        if has_current:
            self.view.closePersistentEditor(current_index)


    @Slot()
    def select_instrument(self) -> None:
        instrument_data = self.get_available_instruments()

        index: QModelIndex = self.view.selectionModel().currentIndex()

        dialog = AvailableInstrumentWidget(instrument_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_instrument_object = dialog.selected_instrument
            if selected_instrument_object:
                # Set the data in the selected row to the instrument
                self.tree_item_from_index(index).set_data(selected_instrument_object)


    def get_available_instruments(self) -> Sequence[Movement | VisaMovement | Measurement | VisaMeasurement]:
        # Placeholder for actual instrument retrieval logic
        
        instrument_objects = [
            Measurement('Keithley 2400'),
            Measurement('Agilent 34401A'),
            Measurement('Tektronix TDS2024C')
        ]

        return instrument_objects
    

