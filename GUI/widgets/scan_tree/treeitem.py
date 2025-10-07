# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
from __future__ import annotations
from typing import Optional
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from pybirch.scan.movements import Movement, VisaMovement
from pybirch.scan.measurements import Measurement, VisaMeasurement
from typing import Callable

## NEEDS TO BE TESTED ##
class InstrumentTreeItem:
    def __init__(self, data: list, parent: 'InstrumentTreeItem' = None, instrument_object: Optional[Movement | VisaMovement | Measurement | VisaMeasurement] = None, indices: list[int] = [], final_indices: list[int] = []):  #type: ignore
        self.item_data = data
        self.item_indices = indices
        self.final_indices = final_indices
        self.parent_item = parent
        self.child_items: list[InstrumentTreeItem] = []
        self.instrument_object = instrument_object

        # Initialize indices for Movement objects if not provided
        if instrument_object is not None and issubclass(instrument_object.__class__, (Movement, VisaMovement)):
            if not self.item_indices:
                self.item_indices = [0]
            if not self.final_indices:
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
        if self.item_indices and self.final_indices:
            return self.item_indices == self.final_indices
        
        # All other items are finished when they have been performed once
        return False
    
    def reset_indices(self):
        if self.instrument_object in [Movement, VisaMovement]:
            self.item_indices = [0]
        if self.child_items:
            for child in self.child_items:
                child.reset_indices()

    def check_parent_callback(self) -> Callable | bool:
        # if there is no parent, the scan is finished. Woo!
        if not self.parent():
            return True

        # if object has children, we must always call move_next on the parent
        if self.child_items:
            return self.parent().move_next

        # if the object has no children and is not the last child, return True to indicate higher calls can move on
        if not self.parent().last_child() == self:
            return True
        
        # if this is the last child, return the move_next of the parent, which will be called by the UI
        else:
            return self.parent().move_next

    def reset_children_indices(self):
        if self.child_items:
            for child in self.child_items:
                child.reset_indices()

    def move_next(self, log: bool = False) -> Callable | bool:

        # if there is no instrument object, we cannot do anything. Higher calls should move on.
        if self.instrument_object is None:
            if log:
                print("No instrument object assigned to this tree item.")
            return self.check_parent_callback()

        # if this is a finished item we move on
        if self.finished() and all(child.finished() for child in self.child_items):
            if log:
                print(f"Item {self.instrument_object.name} finished.")
            return self.check_parent_callback()

        # If it is an unfinished movement object and its children are finished, we move to the next position
        if self.item_indices and self.final_indices and all(child.finished() for child in self.child_items):
            for i in reversed(range(len(self.item_indices))):
                if self.item_indices[i] < self.final_indices[i]:
                    self.item_indices[i] += 1
                    for j in range(i + 1, len(self.item_indices)):
                        self.item_indices[j] = 0
                    self.instrument_object.move_to_position(self.item_indices)  #type: ignore
                    break
            # And reset children indices if they exist
            self.reset_children_indices()

            if log:
                print(f"Moved {self.instrument_object.name} to position {self.item_indices}.")

        # If, instead, it is a measurement object, we perform measurement and move on
        elif issubclass(self.instrument_object.__class__, (Measurement, VisaMeasurement)):
            self.instrument_object.perform_measurement()  #type: ignore

            if log:
                print(f"Performed measurement {self.instrument_object.name}.")

            # After performing a measurement, we are finished and can move on
            return self.check_parent_callback()

        ###### if we reach here, we have a movement/conditional object whose children are not finished ######

        # Call move_next on child items if they exist
        if self.child_items:
            for child in self.child_items:
                next = child.move_next()

                # if the child is finished, we can move to the next child
                if next == True:
                    continue

                # if the child returned a callable, return the callable to be executed by the UI
                else:
                    if log:
                        print(f"Moving into child item {child.instrument_object.name if child.instrument_object else 'No Instrument'}")
                    return next

            # if we reach here, all children are finished
            # if this item is not finished, we move next
            if not self.finished():
                if log:
                    print(f"All children of {self.instrument_object.name if self.instrument_object else 'No Instrument'} finished, moving to next position.")
                return self.move_next
            
            # if this item is finished, let higher calls know they can move on
            if log:
                print(f"All children of {self.instrument_object.name if self.instrument_object else 'No Instrument'} finished, item also finished.")
            return self.check_parent_callback()
        
        # if this is not finished and has no children, we move next. Strange case.
        elif not self.finished():
            if log:
                print(f"Item {self.instrument_object.name if self.instrument_object else 'No Instrument'} has no children, moving to next position.")
            return self.move_next
        
        # if this is finished and has no children, let higher calls know they can move on
        if log:
            print(f"Item {self.instrument_object.name if self.instrument_object else 'No Instrument'} has no children and is finished.")
        return self.check_parent_callback()



    def __repr__(self) -> str:
        result = f"<treeitem.TreeItem at 0x{id(self):x}"
        for d in self.item_data:
            result += f' "{d}"' if d else " <None>"
        result += f", {len(self.child_items)} children>"
        return result
