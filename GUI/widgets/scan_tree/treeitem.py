# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
from __future__ import annotations
from typing import Optional
from pybirch.scan.movements import Movement, VisaMovement
from pybirch.scan.measurements import Measurement, VisaMeasurement

class InstrumentTreeItem:
    def __init__(self, data: list, parent: 'InstrumentTreeItem' = None, instrument_object: Optional[Movement | VisaMovement | Measurement | VisaMeasurement] = None, indices: list[int] = [], final_indices: list[int] = []):  #type: ignore
        self.item_data = data
        self.item_indices = indices
        self.final_indices = final_indices
        self.parent_item = parent
        self.child_items = []
        self.instrument_object = instrument_object
        if not self.item_indices and instrument_object in [Movement, VisaMovement]:
            self.item_indices = [0]
        if not self.final_indices and instrument_object in [Movement, VisaMovement]:
            self.final_indices = [len(instrument_object.positions) - 1]  #type: ignore

    def child(self, number: int) -> 'InstrumentTreeItem':
        if number < 0 or number >= len(self.child_items):
            return None  #type: ignore
        return self.child_items[number]

    def last_child(self):
        return self.child_items[-1] if self.child_items else None

    def child_count(self) -> int:
        return len(self.child_items)

    def child_number(self) -> int:
        if self.parent_item:
            return self.parent_item.child_items.index(self)
        return 0

    def column_count(self) -> int:
        return len(self.item_data)

    def data(self, column: int):
        if column < 0 or column >= len(self.item_data):
            return None
        return self.item_data[column]

    def insert_children(self, position: int, count: int, columns: int) -> bool:
        if position < 0 or position > len(self.child_items):
            return False

        for row in range(count):
            data = [None] * columns
            item = InstrumentTreeItem(data.copy(), self)
            self.child_items.insert(position, item)

        return True

    def insert_columns(self, position: int, columns: int) -> bool:
        if position < 0 or position > len(self.item_data):
            return False

        for column in range(columns):
            self.item_data.insert(position, None)

        for child in self.child_items:
            child.insert_columns(position, columns)

        return True

    def parent(self):
        return self.parent_item

    def remove_children(self, position: int, count: int) -> bool:
        if position < 0 or position + count > len(self.child_items):
            return False

        for row in range(count):
            self.child_items.pop(position)

        return True

    def remove_columns(self, position: int, columns: int) -> bool:
        if position < 0 or position + columns > len(self.item_data):
            return False

        for column in range(columns):
            self.item_data.pop(position)

        for child in self.child_items:
            child.remove_columns(position, columns)

        return True

    def set_data(self, column: int, value):
        if column < 0 or column >= len(self.item_data):
            return False

        self.item_data[column] = value
        return True

    def finished(self) -> bool:
        if self.instrument_object in [Movement, VisaMovement]:
            return self.item_indices == self.final_indices
        return True
    
    def reset_indices(self):
        if self.instrument_object in [Movement, VisaMovement]:
            self.item_indices = [0]
        
    def move_next(self) -> bool:
        if self.instrument_object in [Movement, VisaMovement]:

            if self.finished():
                return False
            
            for i in reversed(range(len(self.item_indices))):
                if self.item_indices[i] < self.final_indices[i]:
                    self.item_indices[i] += 1
                    self.instrument_object.position = self.instrument_object.positions[self.item_indices[i]]  #type: ignore
                    return True
                else:
                    self.item_indices[i] = 0
            return False
        return True

    def __repr__(self) -> str:
        result = f"<treeitem.TreeItem at 0x{id(self):x}"
        for d in self.item_data:
            result += f' "{d}"' if d else " <None>"
        result += f", {len(self.child_items)} children>"
        return result
