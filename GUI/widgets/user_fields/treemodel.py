# Copyright (C) 2025
# User Fields Tree Model for PyBirch
from __future__ import annotations
from typing import Optional
from PySide6.QtCore import QModelIndex, Qt, QAbstractItemModel, QPersistentModelIndex
from treeitem import UserFieldTreeItem


class UserFieldTreeModel(QAbstractItemModel):

    def __init__(self, headers: list[str], parent=None):
        super().__init__(parent)
        
        # Create root item
        self.root_item = UserFieldTreeItem()
        # Set the headers on the root item
        self.root_item.headers = headers

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        flags = super().flags(index)
        
        # Only the Value column (column 1) should be editable
        if index.column() == 1:  # Value column
            flags |= Qt.ItemFlag.ItemIsEditable
        else:
            # Title column (column 0) is not editable
            flags &= ~Qt.ItemFlag.ItemIsEditable

        return flags

    def get_item(self, index: QModelIndex | QPersistentModelIndex = QModelIndex()) -> UserFieldTreeItem:
        if index.isValid():
            item: UserFieldTreeItem = index.internalPointer()
            if item:
                return item

        return self.root_item

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section < len(self.root_item.headers):
                return self.root_item.headers[section]

        return None

    def index(self, row: int, column: int, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> QModelIndex:
        if parent.isValid() and parent.column() != 0:
            return QModelIndex()

        parent_item: UserFieldTreeItem = self.get_item(parent)
        if not parent_item:
            return QModelIndex()

        child_item: UserFieldTreeItem = parent_item.child(row)
        if child_item:
            return self.createIndex(row, column, child_item)
        return QModelIndex()

    def insertRows(self, position: int, count: int, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> bool:
        """Standard QAbstractItemModel insertRows method"""
        parent_item: UserFieldTreeItem = self.get_item(parent)
        if not parent_item:
            return False

        self.beginInsertRows(parent, position, position + count - 1)
        success: bool = parent_item.insert_children(position, count)
        self.endInsertRows()

        return success

    def insertUserFields(self, position: int, titles: list[str], values: Optional[list[str]] = None, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> bool:
        """Custom method to insert user fields with specific titles and values"""
        parent_item: UserFieldTreeItem = self.get_item(parent)
        if not parent_item:
            return False

        if values is None:
            values = [""] * len(titles)

        self.beginInsertRows(parent, position, position + len(titles) - 1)
        success: bool = parent_item.insert_children(position, len(titles), titles, values)
        self.endInsertRows()

        return success

    def parent(self, index: QModelIndex | QPersistentModelIndex = QModelIndex()) -> QModelIndex: #type: ignore
        if not index.isValid():
            return QModelIndex()

        child_item: UserFieldTreeItem = self.get_item(index)
        if child_item:
            parent_item: Optional[UserFieldTreeItem] = child_item.parent()
        else:
            parent_item = None

        if parent_item == self.root_item or not parent_item:
            return QModelIndex()

        return self.createIndex(parent_item.child_number(), 0, parent_item)

    def removeRows(self, position: int, rows: int, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> bool:
        parent_item: UserFieldTreeItem = self.get_item(parent)
        if not parent_item:
            return False

        self.beginRemoveRows(parent, position, position + rows - 1)
        success: bool = parent_item.remove_children(position, rows)
        self.endRemoveRows()

        return success

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        if parent.isValid() and parent.column() > 0:
            return 0

        parent_item: UserFieldTreeItem = self.get_item(parent)
        if not parent_item:
            return 0
        return parent_item.child_count()

    def setData(self, index: QModelIndex | QPersistentModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if role != Qt.ItemDataRole.EditRole:
            return False

        if not index.isValid():
            return False

        item: UserFieldTreeItem = self.get_item(index)
        if not item:
            return False

        # Handle editing of columns
        if index.column() == 0:  # Title column
            # Don't allow editing of title column through the view
            return False
        elif index.column() == 1:  # Value column
            # Update the value
            item.value = str(value) if value is not None else ""
            item.columns[1] = item.value
            
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
            return True
        
        return False

    def setUserFieldData(self, index: QModelIndex | QPersistentModelIndex, title: Optional[str] = None, value: Optional[str] = None) -> bool:
        """Custom method to set both title and value for an item"""
        if not index.isValid():
            return False

        item: UserFieldTreeItem = self.get_item(index)
        if not item:
            return False

        result: bool = item.set_data(title, value)

        if result:
            # Emit dataChanged for all columns since data affects multiple columns
            first_column = self.index(index.row(), 0, index.parent())
            last_column = self.index(index.row(), self.columnCount() - 1, index.parent())
            self.dataChanged.emit(first_column, last_column, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

        return result

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if role != Qt.ItemDataRole.DisplayRole and role != Qt.ItemDataRole.EditRole:
            return None

        item: UserFieldTreeItem = self.get_item(index)
        if not item:
            return None

        # Return the appropriate column data
        return item.data(index.column())

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        # The number of columns is determined by the headers
        return len(self.root_item.headers)

    def to_dict(self) -> dict:
        """Export the entire tree model to a dictionary"""
        result = {
            'headers': self.root_item.headers,
            'children': []
        }
        
        # Export all root-level children
        for child in self.root_item.child_items:
            result['children'].append(child.to_dict())
        
        return result

    def from_dict(self, data: dict) -> bool:
        """Import tree structure from a dictionary"""
        try:
            # Clear existing data
            self.beginResetModel()
            
            # Set headers
            headers = data.get('headers', ['Title', 'Value'])
            self.root_item = UserFieldTreeItem()
            self.root_item.headers = headers
            
            # Import children
            children_data = data.get('children', [])
            for child_data in children_data:
                child_item = UserFieldTreeItem.from_dict(child_data, parent=self.root_item)
                self.root_item.child_items.append(child_item)
            
            self.endResetModel()
            return True
            
        except Exception as e:
            print(f"Error importing from dictionary: {e}")
            return False

    def clear(self) -> None:
        """Clear all data from the model"""
        self.beginResetModel()
        self.root_item.child_items.clear()
        self.endResetModel()

    def _repr_recursion(self, item: UserFieldTreeItem, indent: int = 0) -> str:
        result = " " * indent + repr(item) + "\n"
        for child in item.child_items:
            result += self._repr_recursion(child, indent + 2)
        return result

    def __repr__(self) -> str:
        return self._repr_recursion(self.root_item)