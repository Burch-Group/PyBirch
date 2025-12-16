# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
from __future__ import annotations
from typing import Optional
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from pybirch.scan.movements import Movement, VisaMovement, MovementItem
from pybirch.scan.measurements import Measurement, VisaMeasurement, MeasurementItem
from typing import Callable
import pandas as pd

## NEEDS TO BE TESTED ##
class InstrumentTreeItem:
    def __init__(self, parent: Optional[InstrumentTreeItem] = None, instrument_object: MovementItem | MeasurementItem | None = None, indices: list[int] = [], final_indices: list[int] = [], semaphore: str = "", _runtime_settings: dict | None = None):
        self.instrument_object = instrument_object
        self._runtime_settings = _runtime_settings if _runtime_settings is not None else {}
        self.item_indices = indices
        self.final_indices = final_indices
        self.parent_item = parent
        self.semaphore: str = semaphore
        self.movement_positions: list = []
        self.movement_entries: dict = {}
        self.checked: bool = False  # Add checkbox state
        self._runtime_initialized = False
        self._unique_id = id(self)

        self.deserialized_instrument_data: dict | None = None # To hold deserialized data temporarily

        if self.instrument_object is None:
            self.name = ""
            self.type = ""
            self.adapter = ""
        else:
            self.name = self.instrument_object.instrument.nickname
            self.type = self.instrument_object.instrument.__base_class__().__name__
            self.adapter = self.instrument_object.instrument.adapter

        self.child_items: list[InstrumentTreeItem] = []
        self.instrument_object = instrument_object

        self.headers = ["Name", "Type", "Adapter", "Semaphores"]
        self.columns = [self.name, self.type, self.adapter, self.semaphore]

        # Initialize indices for Movement objects if not provided
        print(f"Initializing InstrumentTreeItem for instrument: {self.name if self.name else 'None'}")
        if instrument_object is None:
            print("No instrument object provided.")
            self.item_indices = []
            self.final_indices = []
        elif instrument_object.instrument.__base_class__() is Movement:
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

    def unique_id(self) -> str:
        """Generate a unique identifier for this MovementItem based on its instrument and settings."""
        if self.instrument_object is None:
            return f"None__{self._unique_id}"
        return f"{self.instrument_object.instrument.name}_{self.instrument_object.instrument.adapter}_{self._unique_id}"

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

    def insert_children(self, row: int, instruments: list[MovementItem | MeasurementItem]) -> bool:
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

    def set_data(self, instrument_object: MovementItem | MeasurementItem | None = None, indices: list[int] = [], final_indices: list[int] = [], semaphore: str = "", checked: bool = False) -> bool:
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
            self.name = self.instrument_object.instrument.nickname
            self.type = self.instrument_object.instrument.__base_class__().__name__
            self.adapter = self.instrument_object.instrument.adapter

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
        # elif checked_count == 0:
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
    
    def reset_children_indices(self):
        if self.child_items:
            for child in self.child_items:
                child.reset_indices()
    
    def reset_indices(self):
        self.item_indices = [0]
        self.reset_children_indices()

    def move_next(self) -> pd.DataFrame | bool:
        if not self._runtime_initialized:
            self._runtime_initialized = True
            self.instrument_object.instrument.initialize()
            self.instrument_object.instrument.settings = self.instrument_object.settings

        
        if self.instrument_object.instrument.__base_class__() is Movement:
            if not self.item_indices or not self.final_indices:
                return False
            for i in reversed(range(len(self.item_indices))):
                if self.item_indices[i] < self.final_indices[i]:
                    self.item_indices[i] += 1
                else:
                    self.reset_indices()
                self.instrument_object.instrument.position = self.instrument_object.positions[self.item_indices[i]]  #type: ignore
                print(f"Moved to position {self.instrument_object.instrument.position}, with index {self.item_indices[i]} out of {self.final_indices[i]}")
                return True
            return False
        
        elif self.instrument_object.instrument.__base_class__() is Measurement:
            self.item_indices = [1]
            print(f"Performing measurement with instrument {self.instrument_object.instrument.name}")
            return self.instrument_object.instrument.measurement_df() #type: ignore
        
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
            "instrument_object": self.instrument_object.serialize() if self.instrument_object else None,
            "child_items": [child.serialize() for child in self.child_items]
        }
        return data
    
    @staticmethod
    def deserialize(data: dict, parent: Optional[InstrumentTreeItem] = None) -> InstrumentTreeItem:
        instrument_object = None  # Placeholder, actual object reconstruction will occur later
        item = InstrumentTreeItem(parent, instrument_object, data.get("item_indices", []), data.get("final_indices", []), data.get("semaphore", ""))
        item.name = data.get("name", "")
        item.type = data.get("type", "")
        item.adapter = data.get("adapter", "")
        item.movement_positions = data.get("movement_positions", [])
        item.movement_entries = data.get("movement_entries", {})
        item.checked = data.get("checked", False)
        item.deserialized_instrument_data = data.get("instrument_object", None)
        
        
        for child_data in data.get("child_items", []):
            child_item = InstrumentTreeItem.deserialize(child_data, item)
            item.child_items.append(child_item)
        
        return item

    def find_pybirch_object(self, known_objects: list[type]) -> tuple[str, str, bool]:
        # Returns a string of the PyBirch object class name, object name, and whether a match was found as a bool
        # Takes, as input, a list of known PyBirch objects (Measurement, Movement, or subclasses) to search through
        if self.deserialized_instrument_data is None:
            return "", "", False
        
        if self.instrument_object is not None:
            return self.instrument_object.instrument.name, self.instrument_object.instrument.__class__.__name__, True
        
        instrument_data = self.deserialized_instrument_data.get("instrument", {})

        pybirch_class_name = instrument_data.get("pybirch_class", "")
        name = instrument_data.get("name", "")
        for obj in known_objects:
            if obj.__class__.__name__ == pybirch_class_name and obj().name == name:
                # Create an instrument_object with this instrument and the deserialized settings
                instrument_instance = obj()
                instrument_instance.deserialize(self.deserialized_instrument_data, initialize=False)
                
                return name, pybirch_class_name, True
        return name, pybirch_class_name, False

    def find_instrument_adapter(self, known_objects: list[str]) -> tuple[str, bool]:
        # Returns a tuple of the instrument adapter string, and whether a match was found as a bool
        if self.instrument_object is None or self.instrument_object.instrument is None:
            return "", False
        
        if self.instrument_object.instrument.adapter and self.instrument_object.instrument.adapter in known_objects:
            return self.instrument_object.instrument.adapter, True
        
        if self.deserialized_instrument_data is None:
            return "", False
        
        instrument_data = self.deserialized_instrument_data.get("instrument", {})
        adapter = instrument_data.get("adapter", "")
        if adapter in known_objects:
            self.instrument_object.instrument.adapter = adapter
            return adapter, True
        return adapter, False

    def structure_to_dict(self) -> dict:
         """Convert this tree item and all its children to a dictionary"""
         result = {
             'name': self.name,
             'type': self.type,
             'adapter': self.adapter,
             'semaphore': self.semaphore,
             'children': []
         }
         
         # Recursively convert all children
         for child in self.child_items:
             result['children'].append(child.structure_to_dict())
         
         return result


    class FastForward:
        def __init__(self, current_item: InstrumentTreeItem):
            self.current_item: InstrumentTreeItem = current_item
            self.stack: list[InstrumentTreeItem] = []
            self.done: bool = False
            self.semaphore: list[str] = []
            self.type: dict[str, list[str]] = {}
            self.adapter: dict[str, list[str]] = {}
            self.unique_ids: list[str] = []
            self.final_item: InstrumentTreeItem | None = None

        def check_if_last(self, next: InstrumentTreeItem) -> bool:
            if next.adapter in self.adapter.keys() and next.semaphore and next.semaphore not in self.adapter[next.adapter]:
                return True

            if self.type.keys() and next.type not in self.type.keys() and (
                (next.semaphore and all(next.semaphore not in sems for sems in self.type.values())) 
                or not next.semaphore): # Completely legible pythonic syntax... nothing to see here
                print(f"Type check failed for type '{next.type}', current types: {list(self.type.keys())}")
                return True
            else:
                print(f"Type check passed for type '{next.type}', current types: {list(self.type.keys())}")
            
            if next.semaphore and self.semaphore and next.semaphore not in self.semaphore:
                print(f"Semaphore '{next.semaphore}' not in current semaphores: {self.semaphore}")
                return True
            
            if next.unique_id() in self.unique_ids:
                return True
            
            return False

        def new_item(self, item: InstrumentTreeItem):
            self.current_item = item
            self.current_item.reset_children_indices()
            if self.check_if_last(item):
                self.final_item = item
                self.done = True
                print(f"FastForward reached final item: {item.name}")
                return self
            print(f"FastForward adding item: {item.name}")
            if item.semaphore and item.semaphore not in self.semaphore:
                self.semaphore.append(item.semaphore)

            if item.unique_id() not in self.unique_ids:
                self.unique_ids.append(item.unique_id())

            for characteristic in ['type', 'adapter']:
                value = getattr(item, characteristic)
                print(f"Processing characteristic '{characteristic}' with value '{value}'")
                if value:
                    getattr(self, characteristic)[value] = (getattr(self, characteristic).get(value, []) + [item.semaphore]) if item.semaphore else getattr(self, characteristic).get(value, [])

            self.stack.append(item)

            return self

    def propagate(self, ff: FastForward) -> FastForward:
        if self.child_items and not self.finished():
            return ff.new_item(self.child_items[0])
        elif self.parent_item and self != self.parent_item.last_child():
            next_sibling = self.parent_item.child(self.child_number() + 1)
            return ff.new_item(next_sibling)
        elif self.parent_item:
            next_item = self.parent_item
            while next_item.finished():
                if next_item.parent():
                    next_item = next_item.parent()
                else:
                    ff.done = True
                    return ff
            return ff.new_item(next_item)
        else:
            ff.done = True
            return ff
        
    def is_ancestor_of(self, descendant: 'InstrumentTreeItem') -> bool:
        """Check if this item is an ancestor of the given descendant item."""
        current = descendant.parent_item
        while current is not None:
            if current == self:
                return True
            current = current.parent_item
        return False
        
    




