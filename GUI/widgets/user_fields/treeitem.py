# Copyright (C) 2025
# User Fields Tree Item for PyBirch
from __future__ import annotations
from typing import Optional


class UserFieldTreeItem:
    def __init__(self, title: str = "", value: str = "", parent: Optional['UserFieldTreeItem'] = None):
        self.title = title
        self.value = value
        self.parent_item = parent
        self.child_items: list[UserFieldTreeItem] = []
        
        # Headers for the tree view
        self.headers = ["Title", "Value"]
        # Data columns corresponding to the headers
        self.columns = [self.title, self.value]

    def child(self, number: int) -> 'UserFieldTreeItem':
        """Return the child item at the given index"""
        if number < 0 or number >= len(self.child_items):
            return None  # type: ignore
        return self.child_items[number]

    def last_child(self) -> 'UserFieldTreeItem':
        """Return the last child item"""
        return self.child_items[-1] if self.child_items else None  # type: ignore

    def child_count(self) -> int:
        """Return the number of child items"""
        return len(self.child_items)

    def child_number(self) -> int:
        """Return this item's position in its parent's child list"""
        if self.parent_item:
            return self.parent_item.child_items.index(self)
        return 0

    def insert_children(self, row: int, count: int, titles: Optional[list[str]] = None, values: Optional[list[str]] = None) -> bool:
        """Insert children at the specified row"""
        if row < 0 or row > len(self.child_items):
            return False

        if titles is None:
            titles = ["New Field"] * count
        if values is None:
            values = [""] * count

        # Ensure we have the right number of titles and values
        titles = titles[:count] + ["New Field"] * max(0, count - len(titles))
        values = values[:count] + [""] * max(0, count - len(values))

        for i in range(count):
            item = UserFieldTreeItem(titles[i], values[i], self)
            self.child_items.insert(row + i, item)

        return True

    def parent(self) -> Optional['UserFieldTreeItem']:
        """Return the parent item"""
        return self.parent_item

    def remove_children(self, position: int, count: int) -> bool:
        """Remove children starting at position"""
        if position < 0 or position + count > len(self.child_items):
            return False

        for _ in range(count):
            self.child_items.pop(position)

        return True

    def set_data(self, title: Optional[str] = None, value: Optional[str] = None) -> bool:
        """Set the title and/or value for this item"""
        if title is not None:
            self.title = title
        if value is not None:
            self.value = value
        
        # Update the columns array to reflect changes
        self.columns = [self.title, self.value]
        return True

    def data(self, column: int) -> str:
        """Return data for the specified column"""
        if column == 0:
            return self.title
        elif column == 1:
            return self.value
        return ""

    def to_dict(self) -> dict:
        """Convert this tree item and all its children to a dictionary"""
        result = {
            'title': self.title,
            'value': self.value,
            'children': []
        }
        
        # Recursively convert all children
        for child in self.child_items:
            result['children'].append(child.to_dict())
        
        return result

    @classmethod
    def from_dict(cls, data: dict, parent: Optional['UserFieldTreeItem'] = None) -> 'UserFieldTreeItem':
        """Create a tree item from a dictionary"""
        # Create the item with title and value
        item = cls(
            title=data.get('title', ''),
            value=data.get('value', ''),
            parent=parent
        )
        
        # Recursively create children
        children_data = data.get('children', [])
        for child_data in children_data:
            child_item = cls.from_dict(child_data, parent=item)
            item.child_items.append(child_item)
        
        return item

    def __repr__(self) -> str:
        return f"UserFieldTreeItem(title='{self.title}', value='{self.value}', children={len(self.child_items)})"