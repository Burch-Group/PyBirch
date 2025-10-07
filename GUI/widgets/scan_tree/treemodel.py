# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
from __future__ import annotations
from typing import Callable, Optional
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from PySide6.QtCore import QModelIndex, Qt, QAbstractItemModel
from treeitem import InstrumentTreeItem
import pickle


class ScanTreeModel(QAbstractItemModel):

    def __init__(self, headers: list, filename: str, parent=None, update_interface: Optional[Callable] = None):
        super().__init__(parent)

        self.headers = headers
        self.restore_model_from_pickle(filename)
        self.update_interface = update_interface


## NEEDS TO BE TESTED ##
    def start_scan(self) -> bool:
        move_next: Callable = self.root_item.move_next
        i = 0
        while move_next != True:
            if type(move_next) == Callable:
                move_next = move_next()

            if self.update_interface:
                self.update_interface()

            i += 1
            if i > 10000:
                print("Scan appears to be stuck in an infinite loop. Aborting.")
                return False

        return True


    def columnCount(self, parent: QModelIndex = None) -> int: #type: ignore
        return self.root_item.column_count()

    def data(self, index: QModelIndex, role: int = None): #type: ignore
        if not index.isValid():
            return None

        if role != Qt.ItemDataRole.DisplayRole and role != Qt.ItemDataRole.EditRole:
            return None

        item: InstrumentTreeItem = self.get_item(index)

        return item.data(index.column())

    def flags(self, index: QModelIndex) -> Qt.ItemFlags: #type: ignore
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        return Qt.ItemFlag.ItemIsEditable | QAbstractItemModel.flags(self, index)

    def get_item(self, index: QModelIndex = QModelIndex()) -> InstrumentTreeItem:
        if index.isValid():
            item: InstrumentTreeItem = index.internalPointer()
            if item:
                return item

        return self.root_item

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.root_item.data(section)

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

    def insertColumns(self, position: int, columns: int, #type: ignore
                      parent: QModelIndex = QModelIndex()) -> bool:
        self.beginInsertColumns(parent, position, position + columns - 1)
        success: bool = self.root_item.insert_columns(position, columns)
        self.endInsertColumns()

        return success

    def insertRows(self, position: int, rows: int, #type: ignore
                   parent: QModelIndex = QModelIndex()) -> bool:
        parent_item: InstrumentTreeItem = self.get_item(parent)
        if not parent_item:
            return False

        self.beginInsertRows(parent, position, position + rows - 1)
        column_count = self.root_item.column_count()
        success: bool = parent_item.insert_children(position, rows, column_count)
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

    def removeColumns(self, position: int, columns: int, #type: ignore
                      parent: QModelIndex = QModelIndex()) -> bool:
        self.beginRemoveColumns(parent, position, position + columns - 1)
        success: bool = self.root_item.remove_columns(position, columns)
        self.endRemoveColumns()

        if self.root_item.column_count() == 0:
            self.removeRows(0, self.rowCount())

        return success

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

    def setData(self, index: QModelIndex, value, role: int) -> bool: #type: ignore
        if role != Qt.ItemDataRole.EditRole:
            return False

        item: InstrumentTreeItem = self.get_item(index)
        result: bool = item.set_data(index.column(), value)

        if result:
            self.dataChanged.emit(index, index,
                                  [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

        return result

    def setHeaderData(self, section: int, orientation: Qt.Orientation, value,
                      role: int = None) -> bool: #type: ignore
        if role != Qt.ItemDataRole.EditRole or orientation != Qt.Orientation.Horizontal:
            return False

        result: bool = self.root_item.set_data(section, value)

        if result:
            self.headerDataChanged.emit(orientation, section, section)

        return result

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
