# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
from __future__ import annotations
from typing import Optional
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from pybirch.scan.movements import Movement, VisaMovement
from pybirch.scan.measurements import Measurement, VisaMeasurement
from typing import Callable
import pandas as pd

## NEEDS TO BE TESTED ##
class InstrumentTreeItem:
    def __init__(self, parent: Optional[InstrumentTreeItem] = None, instrument_object: Movement | VisaMovement | Measurement | VisaMeasurement | None = None, indices: list[int] = [], final_indices: list[int] = [], semaphore: str = ""):
        self.instrument_object = instrument_object
        self.item_indices = indices
        self.final_indices = final_indices
        self.parent_item = parent
        self.semaphore: str = semaphore
        self.movement_positions: list = []
        self.movement_entries: dict = {}
        self.checked: bool = False  # Add checkbox state
        if self.instrument_object is None:
            self.name = ""
            self.type = ""
            self.adapter = ""
        else:
            self.name = self.instrument_object.nickname
            self.type = self.instrument_object.__class__.__bases__[0].__name__
            self.adapter = self.instrument_object.adapter

        self.child_items: list[InstrumentTreeItem] = []
        self.instrument_object = instrument_object

        self.headers = ["Name", "Type", "Adapter", "Semaphores"]
        self.columns = [self.name, self.type, self.adapter, self.semaphore]

        # Initialize indices for Movement objects if not provided
        if instrument_object is None:
            self.item_indices = []
            self.final_indices = []
        elif issubclass(instrument_object.__class__, (Movement, VisaMovement)):
            if not self.item_indices:
                self.item_indices = [0]
            if not self.final_indices:
                # Check if the movement object has positions attribute, otherwise default to 1
                try:
                    positions = getattr(instrument_object, 'positions', None)
                    if positions and len(positions) > 0:
                        self.final_indices = [len(positions) - 1]
                    else:
                        # Default if no positions attribute or empty positions
                        self.final_indices = [1]
                except Exception:
                    # Default if any error accessing positions
                    self.final_indices = [1]
        else:
            # For Measurement objects, indices are always [0] to [1]
            self.item_indices = [0]
            self.final_indices = [1]



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

    def insert_children(self, row: int, instruments: list[Movement | VisaMovement | Measurement | VisaMeasurement]) -> bool:
        if row < 0 or row > len(self.child_items):
            return False

        for i, instrument in enumerate(instruments):
            item = InstrumentTreeItem(self, instrument_object=instrument)
            self.child_items.insert(row + i, item)

        return True

    def parent(self):
        return self.parent_item

    def remove_children(self, position: int, count: int) -> bool:
        if position < 0 or position + count > len(self.child_items):
            return False

        for row in range(count):
            self.child_items.pop(position)

        return True

    def set_data(self, instrument_object: Movement | VisaMovement | Measurement | VisaMeasurement | None = None, indices: list[int] = [], final_indices: list[int] = [], semaphore: str = "", checked: bool = False) -> bool:
        self.instrument_object = instrument_object
        self.item_indices = indices
        self.final_indices = final_indices
        self.semaphore = semaphore
        self.checked = checked

        if self.instrument_object is None:
            self.name = ""
            self.type = ""
            self.adapter = ""
        else:
            self.name = self.instrument_object.nickname
            self.type = self.instrument_object.__class__.__bases__[0].__name__
            self.adapter = self.instrument_object.adapter

        self.columns = [self.name, self.type, self.adapter, self.semaphore]
        return True

    def set_checked(self, checked: bool, update_children: bool = True, update_parent: bool = True) -> None:
        """Set the checked state and optionally propagate to children/parent"""
        self.checked = checked
        
        if update_children:
            # Update all children to the same state
            for child in self.child_items:
                child.set_checked(checked, update_children=True, update_parent=False)
        
        if update_parent and self.parent_item:
            self.parent_item._update_check_state_from_children()
    
    def _update_check_state_from_children(self) -> None:
        """Update this item's check state based on children states"""
        if not self.child_items:
            return
            
        checked_count = sum(1 for child in self.child_items if child.checked)
        
        if checked_count == len(self.child_items):
            self.checked = True
        elif checked_count == 0:
            print(self.checked)
            # self.checked = False
        else:
            # For partial states, we'll use False but the model will handle partial display
            self.checked = False
    
    def get_check_state(self):
        """Get the Qt check state (for use with Qt.CheckStateRole)"""
        from PySide6.QtCore import Qt
        
        if not self.child_items:
            return Qt.CheckState.Checked if self.checked else Qt.CheckState.Unchecked
        
        # For parent items, check if we have a partial state
        checked_count = sum(1 for child in self.child_items if child.checked)
        
        if checked_count == len(self.child_items):
            return Qt.CheckState.Checked
        elif checked_count == 0:
            return Qt.CheckState.Unchecked
        else:
            return Qt.CheckState.PartiallyChecked

    def finished(self) -> bool:
        if self.item_indices and self.final_indices:
            return self.item_indices == self.final_indices
        
        # All other items are finished when they have been performed once
        return True
    
    def reset_indices(self):
        if self.instrument_object in [Movement, VisaMovement]:
            self.item_indices = [0]
        if self.child_items:
            for child in self.child_items:
                child.reset_indices()

    def move_next(self) -> pd.DataFrame | bool:
        if self.instrument_object in [Movement, VisaMovement]:
            if not self.item_indices or not self.final_indices:
                return False
            for i in reversed(range(len(self.item_indices))):
                if self.item_indices[i] < self.final_indices[i]:
                    self.item_indices[i] += 1
                    self.instrument_object.position = self.instrument_object.positions[self.item_indices[i]]  #type: ignore
                    return True
                else:
                    self.item_indices[i] = 0
            return False
        
        elif self.instrument_object in [Measurement, VisaMeasurement]:
            self.item_indices = [1]
            return self.instrument_object.measurement_df() #type: ignore
        
        return False

    def serialize(self) -> dict:
        data = {
            "name": self.name,
            "type": self.type,
            "adapter": self.adapter,
            "semaphore": self.semaphore,
            "item_indices": self.item_indices,
            "final_indices": self.final_indices,
            "movement_positions": self.movement_positions,
            "movement_entries": self.movement_entries,
            "checked": self.checked,
            "child_items": [child.serialize() for child in self.child_items]
        }
        return data
    
    @staticmethod
    def deserialize(data: dict, parent: Optional[InstrumentTreeItem] = None) -> InstrumentTreeItem:
        instrument_object = None  # Placeholder, actual object reconstruction would depend on more context
        item = InstrumentTreeItem(parent, instrument_object, data.get("item_indices", []), data.get("final_indices", []), data.get("semaphore", ""))
        item.name = data.get("name", "")
        item.type = data.get("type", "")
        item.adapter = data.get("adapter", "")
        item.movement_positions = data.get("movement_positions", [])
        item.movement_entries = data.get("movement_entries", {})
        item.checked = data.get("checked", False)
        
        for child_data in data.get("child_items", []):
            child_item = InstrumentTreeItem.deserialize(child_data, item)
            item.child_items.append(child_item)
        
        return item

    def find_instrument_object(self) -> None:
        # To be implemented based on application context
        return

    class FastForward:
        def __init__(self, current_item: InstrumentTreeItem):
            self.current_item: InstrumentTreeItem = current_item
            self.stack: list[InstrumentTreeItem] = []
            self.done: bool = False
            self.semaphore: list[str] = []
            self.type: dict[str, list[str]] = {}
            self.adapter: dict[str, list[str]] = {}
            self.final_item: InstrumentTreeItem | None = None

        def check_if_last(self, next: InstrumentTreeItem) -> bool:
            if next.adapter in self.adapter.keys() and next.semaphore not in self.adapter[next.adapter]:
                return True
            if next.type not in self.type.keys() and all(
                next.semaphore not in sems for sems in self.type.values()
            ):
                return True
            if next.semaphore and self.semaphore and next.semaphore not in self.semaphore:
                return True
            if next.parent() and next == next.parent().last_child() and not next.child_items: # type: ignore
                return True
            return False

        def new_item(self, item: InstrumentTreeItem):
            self.current_item = item
            if self.check_if_last(item):
                self.final_item = item
                self.done = True
                return self
            
            if item.semaphore and item.semaphore not in self.semaphore:
                self.semaphore.append(item.semaphore)

            for characteristic in ['type', 'adapter']:
                value = getattr(item, characteristic)
                if value:
                    getattr(self, characteristic)[value] = getattr(self, characteristic).get(value, []) + [item]

            self.stack.append(item)

            return self

    def propagate(self, ff: FastForward) -> FastForward:
        if self.child_items:
            return ff.new_item(self.child_items[0])
        elif self.parent_item and self != self.parent_item.last_child():
            next_sibling = self.parent_item.child(self.child_number() + 1)
            return ff.new_item(next_sibling)
        elif self.parent_item:
            return ff.new_item(self.parent_item)
        else:
            ff.done = True
            return ff
        
    




