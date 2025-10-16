# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
from __future__ import annotations
from typing import Callable, Optional
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from PySide6.QtCore import QModelIndex, Qt, QAbstractItemModel, QPersistentModelIndex, QThreadPool
from treeitem import InstrumentTreeItem
from pybirch.scan.movements import Movement, VisaMovement
from pybirch.scan.measurements import Measurement, VisaMeasurement
import pickle

from phd_student import PhDStudent



class ScanTreeModel(QAbstractItemModel):

    def __init__(self, headers: list, filename: Optional[str] = None, parent=None, update_interface: Optional[Callable] = None, next_item: Optional[InstrumentTreeItem] = None):
        super().__init__(parent)

        if filename:
            self.restore_model_from_pickle(filename)
        else:
            self.root_item = InstrumentTreeItem()
        
        # Set the headers on the root item
        self.root_item.headers = headers
        self.update_interface = update_interface
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(20)  # Limit to 20 threads for safety
        self.completed = False
        self.paused = False
        self.stopped = False
        self.next_item = next_item


    def start_scan(self) -> bool:
        if self.root_item.child_count() == 0:
            return False
        
        next_item = self.root_item.child_items[0] if self.next_item is None else self.next_item
        
        while next_item is not self.root_item:
            if self.update_interface:
                self.update_interface()
            
            if self.stopped or self.paused:
                return False

            fast_forward = InstrumentTreeItem.FastForward(next_item)
            if not next_item.finished():
                fast_forward = fast_forward.new_item(next_item)

            while not fast_forward.done:
                fast_forward = fast_forward.new_item(fast_forward.current_item)
                if fast_forward.done:
                    break
            
            # Execute the stack in parallel with QT multithreading by mapping the move_next function to each item in the stack, 
            # and assigning this work to a virtual PhD student
            if len(fast_forward.stack) == 0:
                virtual_lab_group = []
                for item in fast_forward.stack:
                    worker = PhDStudent(
                        item.move_next
                    ) 

                    # If necessary, connect signals here
                    # worker.signals.result.connect()
                    # worker.signals.finished.connect()
                    # worker.signals.progress.connect()
                    virtual_lab_group.append(worker)
                
                # Execute
                for worker in virtual_lab_group:
                    self.threadpool.start(worker)
                
                self.threadpool.waitForDone()  # Wait for all threads to complete

            next_item = fast_forward.final_item
            if next_item is None:
                break

        self.completed = True
        return True
        
    def flags(self, index: QModelIndex) -> Qt.ItemFlags:  # type: ignore
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        flags = super().flags(index)
        if index.column() == 0:
            # Editable, selectable, enabled, user-checkable
            flags |= Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsUserCheckable
        elif index.column() == 1:
            # Not editable
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
        default_instruments: list[Movement | VisaMovement | Measurement | VisaMeasurement] = [Measurement('Default Instrument') for _ in range(count)]
        
        self.beginInsertRows(parent, position, position + count - 1)
        success: bool = parent_item.insert_children(position, default_instruments)
        self.endInsertRows()

        return success

    def insertInstruments(self, position: int, instrument_objects: list[Movement | VisaMovement | Measurement | VisaMeasurement], parent: QModelIndex = QModelIndex()) -> bool:
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
        if child_item:
            parent_item: InstrumentTreeItem = child_item.parent()
        else:
            parent_item = None

        if parent_item == self.root_item or not parent_item:
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

    def setData(self, index: QModelIndex, role: int, instrument_object: Movement | VisaMovement | Measurement | VisaMeasurement = Measurement('default'), indices: list[int] = [], final_indices: list[int] = []) -> bool: #type: ignore
        if role != Qt.ItemDataRole.EditRole:
            return False

        item: InstrumentTreeItem = self.get_item(index)
        result: bool = item.set_data(instrument_object, indices, final_indices)

        if result:
            self.dataChanged.emit(index, index,
                                  [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

        return result

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if role != Qt.ItemDataRole.DisplayRole and role != Qt.ItemDataRole.EditRole:
            return None

        item: InstrumentTreeItem = self.get_item(index)
        if not item:
            return None

        # Return the appropriate column data
        if index.column() < len(item.columns):
            return item.columns[index.column()]
        return None

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        # The number of columns is determined by the headers
        return len(self.root_item.headers)

## NEEDS TO BE FINISHED ##
    def pickle_model(self, filename: str) -> None:
        with open(filename, 'wb') as output:
            pickle.dump(self, output, pickle.HIGHEST_PROTOCOL)

    def restore_model_from_pickle(self, filename: str):
        with open(filename, 'rb') as input:
            model: ScanTreeModel = pickle.load(input)
            self.root_data = model.root_data
            self.root_item = model.root_item
            self.layoutChanged.emit()

    def _repr_recursion(self, item: InstrumentTreeItem, indent: int = 0) -> str:
        result = " " * indent + repr(item) + "\n"
        for child in item.child_items:
            result += self._repr_recursion(child, indent + 2)
        return result

    def __repr__(self) -> str:
        return self._repr_recursion(self.root_item)
