# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
from __future__ import annotations
from typing import Callable, Optional
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from PySide6.QtCore import QModelIndex, Qt, QAbstractItemModel, QPersistentModelIndex, QThreadPool
from .treeitem import InstrumentTreeItem
from pybirch.scan.movements import Movement, VisaMovement, MovementItem
from pybirch.scan.measurements import Measurement, VisaMeasurement, MeasurementItem
import pickle



class ScanTreeModel(QAbstractItemModel):

    def __init__(self, filename: Optional[str] = None, root_item: Optional[InstrumentTreeItem] = None, parent=None, update_interface: Optional[Callable] = None, next_item: Optional[InstrumentTreeItem] = None):
        super().__init__(parent)

        if filename:
            self.restore_model_from_pickle(filename)
        elif root_item:
            self.root_item = root_item
        else:
            self.root_item = InstrumentTreeItem()
        
        # Set the headers on the root item
        self.root_item.headers = ["Name", "Type", "Adapter", "Semaphores"]
        self.update_interface = update_interface
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(20)  # Limit to 20 threads for safety
        self.completed = False
        self.paused = False
        self.stopped = False
        self.next_item = next_item

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:  # type: ignore
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        flags = super().flags(index)
        
        # Add checkbox functionality to the first column (instrument name)
        if index.column() == 0:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        
        # Only the semaphore column (column 3) should be editable
        if index.column() == 3:  # Semaphore column
            flags |= Qt.ItemFlag.ItemIsEditable
        else:
            # All other columns are not editable (except checkbox)
            flags &= ~Qt.ItemFlag.ItemIsEditable

        return flags

    def get_item(self, index: QModelIndex | QPersistentModelIndex = QModelIndex()) -> InstrumentTreeItem:
        if index.isValid():
            item: InstrumentTreeItem = index.internalPointer()
            if item:
                return item

        return self.root_item

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.root_item.headers[section]

        return None

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex: #type: ignore
        if parent.isValid() and parent.column() != 0:
            return QModelIndex()

        parent_item: InstrumentTreeItem = self.get_item(parent)
        if not parent_item:
            return QModelIndex()

        child_item: InstrumentTreeItem = parent_item.child(row)
        if child_item:
            return self.createIndex(row, column, child_item)
        return QModelIndex()

    def insertRows(self, position: int, count: int, parent: QModelIndex = QModelIndex()) -> bool: #type: ignore
        """Standard QAbstractItemModel insertRows method"""
        parent_item: InstrumentTreeItem = self.get_item(parent)
        if not parent_item:
            return False

        # Create default instruments for standard insertRows calls
        default_instruments = [MeasurementItem(Measurement('Default Instrument'), {}) for _ in range(count)]
        
        self.beginInsertRows(parent, position, position + count - 1)
        success: bool = parent_item.insert_children(position, default_instruments)
        self.endInsertRows()

        return success

    def insertInstruments(self, position: int, instrument_objects: list[MeasurementItem | MovementItem], parent: QModelIndex = QModelIndex()) -> bool:
        """Custom method to insert specific instrument objects"""
        parent_item: InstrumentTreeItem = self.get_item(parent)
        if not parent_item:
            return False

        self.beginInsertRows(parent, position, position + len(instrument_objects) - 1)
        success: bool = parent_item.insert_children(position, instrument_objects)
        self.endInsertRows()

        return success

    def parent(self, index: QModelIndex = QModelIndex()) -> QModelIndex: #type: ignore
        if not index.isValid():
            return QModelIndex()

        child_item: InstrumentTreeItem = self.get_item(index)
        if child_item and child_item.parent():
            parent_item: Optional[InstrumentTreeItem] = child_item.parent()
        else:
            parent_item = None

        if not parent_item or parent_item == self.root_item:
            return QModelIndex()

        return self.createIndex(parent_item.child_number(), 0, parent_item)

    def removeRows(self, position: int, rows: int, #type: ignore
                   parent: QModelIndex = QModelIndex()) -> bool:
        parent_item: InstrumentTreeItem = self.get_item(parent)
        if not parent_item:
            return False

        self.beginRemoveRows(parent, position, position + rows - 1)
        success: bool = parent_item.remove_children(position, rows)
        self.endRemoveRows()

        return success

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int: #type: ignore
        if parent.isValid() and parent.column() > 0:
            return 0

        parent_item: InstrumentTreeItem = self.get_item(parent)
        if not parent_item:
            return 0
        return parent_item.child_count()

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool: #type: ignore
        if not index.isValid():
            return False

        item: InstrumentTreeItem = self.get_item(index)
        if not item:
            return False

        # Handle checkbox state changes for the first column
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            checked = value == Qt.CheckState.Checked
            # Only update if the state actually changed
            if item.checked != checked:
                item.set_checked(checked, update_children=True, update_parent=True)
                # Emit dataChanged for the specific index and its children/parent
                self._emit_checkbox_changes(index)
            return True

        if role != Qt.ItemDataRole.EditRole:
            return False

        # Handle editing of the semaphore column (column 3)
        if index.column() == 3:
            # Update the semaphore value
            item.semaphore = str(value) if value is not None else ""
            # Update the columns array to reflect the change
            item.columns[3] = item.semaphore
            
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
            return True
        
        # For other columns, we don't allow direct editing
        return False

    def setInstrumentData(self, index: QModelIndex, instrument_object: MeasurementItem | MovementItem, indices: list[int] = [], final_indices: list[int] = [], semaphore: str = "") -> bool:
        """Custom method to set instrument data for an item"""
        if not index.isValid():
            return False

        item: InstrumentTreeItem = self.get_item(index)
        if not item:
            return False

        result: bool = item.set_data(instrument_object, indices, final_indices, semaphore)

        if result:
            # Emit dataChanged for all columns since instrument data affects multiple columns
            first_column = self.index(index.row(), 0, index.parent())
            last_column = self.index(index.row(), self.columnCount() - 1, index.parent())
            self.dataChanged.emit(first_column, last_column, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

        return result

    def _emit_checkbox_changes(self, changed_index: QModelIndex) -> None:
        """Emit dataChanged signals for checkbox state changes"""
        # Emit for the changed item itself
        first_col_index = self.index(changed_index.row(), 0, changed_index.parent())
        self.dataChanged.emit(first_col_index, first_col_index, [Qt.ItemDataRole.CheckStateRole])
        
        # Emit for all children recursively
        item = self.get_item(changed_index)
        self._emit_children_changes(changed_index, item)
        
        # Emit for parent chain
        parent_index = changed_index.parent()
        while parent_index.isValid():
            parent_first_col = self.index(parent_index.row(), 0, parent_index.parent())
            self.dataChanged.emit(parent_first_col, parent_first_col, [Qt.ItemDataRole.CheckStateRole])
            parent_index = parent_index.parent()

    def _emit_children_changes(self, parent_index: QModelIndex, parent_item: InstrumentTreeItem) -> None:
        """Recursively emit dataChanged for all children"""
        for row in range(parent_item.child_count()):
            child_index = self.index(row, 0, parent_index)
            if child_index.isValid():
                self.dataChanged.emit(child_index, child_index, [Qt.ItemDataRole.CheckStateRole])
                child_item = self.get_item(child_index)
                if child_item and child_item.child_count() > 0:
                    self._emit_children_changes(child_index, child_item)

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        item: InstrumentTreeItem = self.get_item(index)
        if not item:
            return None

        # Handle checkbox state for the first column
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            return item.get_check_state()

        if role != Qt.ItemDataRole.DisplayRole and role != Qt.ItemDataRole.EditRole:
            return None

        # Return the appropriate column data
        if index.column() < len(item.columns):
            return item.columns[index.column()]
        return None

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        # The number of columns is determined by the headers
        return len(self.root_item.headers)
    
    def serialize_model(self) -> dict:
        return {
            "root_data": self.root_data,
            "root_item": self.root_item.serialize()
        }

    def deserialize_model(self, data: dict) -> None:
        self.root_data = data.get("root_data", {})
        self.root_item = InstrumentTreeItem.deserialize(data.get("root_item", {}))
        self.layoutChanged.emit()

## NEEDS TO BE FINISHED ##
    def pickle_model(self, filename: str) -> None:
        with open(filename, 'wb') as f:
            pickle.dump(self.serialize_model(), f)

    def restore_model_from_pickle(self, filename: str):
        with open(filename, 'rb') as input:
            data = pickle.load(input)
            self.deserialize_model(data)

    def _repr_recursion(self, item: InstrumentTreeItem, indent: int = 0) -> str:
        result = " " * indent + repr(item) + "\n"
        for child in item.child_items:
            result += self._repr_recursion(child, indent + 2)
        return result

    def __repr__(self) -> str:
        return self._repr_recursion(self.root_item)

    def get_selected_instruments(self) -> list[InstrumentTreeItem]:
        """Return a list of selected (checked) instrument items."""
        selected_items = []

        def traverse(item: InstrumentTreeItem):
            # Only include items that are checked and have a valid instrument object
            if item.checked and item.instrument_object and item != self.root_item:
                selected_items.append(item)
            for child in item.child_items:
                traverse(child)

        traverse(self.root_item)
        return selected_items

    def set_all_checked(self, checked: bool) -> None:
        """Set all items to checked or unchecked state."""
        def traverse(item: InstrumentTreeItem):
            item.set_checked(checked, update_children=False, update_parent=False)
            for child in item.child_items:
                traverse(child)

        traverse(self.root_item)
        # Emit dataChanged for all items with instruments
        self._emit_all_checkbox_changes()

    def _emit_all_checkbox_changes(self) -> None:
        """Emit dataChanged for all items in the tree"""
        def emit_for_item(item: InstrumentTreeItem, parent_index: QModelIndex):
            for row in range(item.child_count()):
                child_index = self.index(row, 0, parent_index)
                if child_index.isValid():
                    self.dataChanged.emit(child_index, child_index, [Qt.ItemDataRole.CheckStateRole])
                    child_item = self.get_item(child_index)
                    if child_item and child_item.child_count() > 0:
                        emit_for_item(child_item, child_index)
        
        emit_for_item(self.root_item, QModelIndex())

    def get_instrument_count(self) -> int:
        """Return the total number of instrument items in the tree."""
        count = 0

        def traverse(item: InstrumentTreeItem):
            nonlocal count
            if item.instrument_object and item != self.root_item:
                count += 1
            for child in item.child_items:
                traverse(child)

        traverse(self.root_item)
        return count
    
    def get_movement_items(self) -> list[InstrumentTreeItem]:
        """Return a list of all movement instrument items."""
        movement_items = []

        def traverse(item: InstrumentTreeItem):
            if item.instrument_object and item.instrument_object.instrument.__base_class__() is Movement:
                movement_items.append(item)
            for child in item.child_items:
                traverse(child)

        traverse(self.root_item)
        return movement_items
    
    def get_measurement_items(self) -> list[InstrumentTreeItem]:
        """Return a list of all measurement instrument items."""
        measurement_items = []

        def traverse(item: InstrumentTreeItem):
            if item.instrument_object and item.instrument_object.instrument.__base_class__() is Measurement:
                measurement_items.append(item)
            for child in item.child_items:
                traverse(child)

        traverse(self.root_item)
        return measurement_items
    
    def get_all_instrument_items(self) -> list[InstrumentTreeItem]:
        """Return a list of all instrument items."""
        all_items = []

        def traverse(item: InstrumentTreeItem):
            if item.instrument_object:
                all_items.append(item)
            for child in item.child_items:
                traverse(child)

        traverse(self.root_item)
        return all_items

    def serialize(self) -> dict:
        """Serialize the entire model to a dictionary."""
        return {
            "root_item": self.root_item.serialize(),
            "completed": self.completed,
            "paused": self.paused,
            "stopped": self.stopped,
            "next_item": self.next_item.serialize() if self.next_item else None
        }

    def deserialize(self, data: dict) -> None:
        """Deserialize the model from a dictionary."""
        self.root_item = InstrumentTreeItem.deserialize(data.get("root_item", {}))
        self.completed = data.get("completed", False)
        self.paused = data.get("paused", False)
        self.stopped = data.get("stopped", False)
        next_item_data = data.get("next_item", None)
        if next_item_data:
            self.next_item = InstrumentTreeItem.deserialize(next_item_data)
        else:
            self.next_item = None
        self.layoutChanged.emit()