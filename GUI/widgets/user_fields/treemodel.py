# Copyright (C) 2025
# User Fields Tree Model for PyBirch
from __future__ import annotations
from typing import Optional
from PySide6.QtCore import QModelIndex, Qt, QAbstractItemModel, QPersistentModelIndex, QMimeData
from typing import Sequence
from .treeitem import UserFieldTreeItem


class UserFieldTreeModel(QAbstractItemModel):

    def __init__(self, headers: list[str], parent=None):
        super().__init__(parent)
        
        # Create root item
        self.root_item = UserFieldTreeItem()
        # Set the headers on the root item
        self.root_item.headers = headers

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled  # Allow drops on invalid index (root)

        flags = super().flags(index)
        
        # Only the Value column (column 1) should be editable
        if index.column() == 1:  # Value column
            flags |= Qt.ItemFlag.ItemIsEditable
        else:
            # Title column (column 0) is not editable
            flags &= ~Qt.ItemFlag.ItemIsEditable

        # Enable drag and drop for all valid items
        flags |= Qt.ItemFlag.ItemIsDragEnabled
        flags |= Qt.ItemFlag.ItemIsDropEnabled

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

    # Drag and Drop Support Methods
    def supportedDropActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction

    def mimeTypes(self) -> list[str]:
        return ['application/x-userfield-item']

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        import json
        
        if not indexes:
            return QMimeData()
            
        # Get unique rows (in case multiple columns are selected)
        rows = list(set(index.row() for index in indexes))
        parent = indexes[0].parent()
        
        # Collect data for dragged items
        drag_data = []
        for row in rows:
            item_index = self.index(row, 0, parent)
            item = self.get_item(item_index)
            if item:
                drag_data.append({
                    'title': item.title,
                    'value': item.value,
                    'children': [child.to_dict() for child in item.child_items],
                    'source_row': row,
                    'source_parent': self._encode_model_index(parent)
                })
        
        mimeData = QMimeData()
        mimeData.setData('application/x-userfield-item', json.dumps(drag_data).encode())
        return mimeData

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: QModelIndex | QPersistentModelIndex) -> bool:
        import json
        
        if action == Qt.DropAction.IgnoreAction:
            return True
            
        if not data.hasFormat('application/x-userfield-item'):
            return False
            
        try:
            byte_data = data.data('application/x-userfield-item')
            drag_data = json.loads(byte_data.toStdString())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False
            
        # Determine drop position
        if row == -1:
            parent_item = self.get_item(parent)
            row = parent_item.child_count()
        
        # First, remove the original items (in reverse order to maintain indexes)
        items_to_remove = []
        for item_data in drag_data:
            source_parent = self._decode_model_index(item_data.get('source_parent', {}))
            source_row = item_data['source_row']
            items_to_remove.append((source_parent, source_row))
        
        # Sort by row in descending order to remove from bottom up
        items_to_remove.sort(key=lambda x: x[1], reverse=True)
        
        # Insert dragged items at new position first
        for i, item_data in enumerate(drag_data):
            # Skip if dropping on itself
            source_parent = self._decode_model_index(item_data.get('source_parent', {}))
            if (source_parent == parent and 
                item_data['source_row'] == row + i):
                continue
                
            # Insert the item
            success = self.insertUserFields(
                row + i, 
                [item_data['title']], 
                [item_data['value']], 
                parent
            )
            
            if success and item_data.get('children'):
                # Recursively add children
                new_item_index = self.index(row + i, 0, parent)
                self._insert_children_from_dict(item_data['children'], new_item_index)
        
        # Now remove the original items
        for source_parent, source_row in items_to_remove:
            # Adjust source row if items were inserted before it in the same parent
            if source_parent == parent and source_row >= row:
                source_row += len(drag_data)
            self.removeRows(source_row, 1, source_parent)
        
        return True

    def _encode_model_index(self, index: QModelIndex) -> dict:
        """Helper to encode a QModelIndex for serialization"""
        if not index.isValid():
            return {}
        return {
            'row': index.row(),
            'column': index.column(),
            'parent': self._encode_model_index(index.parent())
        }

    def _decode_model_index(self, data: dict) -> QModelIndex:
        """Helper to decode a QModelIndex from serialized data"""
        if not data:
            return QModelIndex()
        
        parent = self._decode_model_index(data.get('parent', {}))
        return self.index(data.get('row', 0), data.get('column', 0), parent)

    def _insert_children_from_dict(self, children_data: list, parent_index: QModelIndex):
        """Helper to recursively insert children from dictionary data"""
        for i, child_data in enumerate(children_data):
            success = self.insertUserFields(
                i, 
                [child_data['title']], 
                [child_data['value']], 
                parent_index
            )
            
            if success and child_data.get('children'):
                child_index = self.index(i, 0, parent_index)
                self._insert_children_from_dict(child_data['children'], child_index)