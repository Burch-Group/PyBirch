# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
from __future__ import annotations
from typing import Optional, Callable
import sys, os
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from pybirch.scan.movements import Movement, VisaMovement, MovementItem
from pybirch.scan.measurements import Measurement, VisaMeasurement, MeasurementItem
from pybirch.scan.protocols import is_movement, is_measurement
from pybirch.scan.traverser import TreeTraverser, propagate as _propagate
import pandas as pd

logger = logging.getLogger(__name__)

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
            # Use protocol-based type detection
            if is_movement(self.instrument_object.instrument):
                self.type = "Movement"
            elif is_measurement(self.instrument_object.instrument):
                self.type = "Measurement"
            else:
                self.type = "Unknown"
            self.adapter = self.instrument_object.instrument.adapter

        self.child_items: list[InstrumentTreeItem] = []
        self.instrument_object = instrument_object

        self.headers = ["Name", "Type", "Adapter", "Semaphores"]
        self.columns = [self.name, self.type, self.adapter, self.semaphore]

        # Initialize indices for Movement objects if not provided
        logger.debug(f"Initializing InstrumentTreeItem for instrument: {self.name if self.name else 'None'}")
        if instrument_object is None:
            logger.debug("No instrument object provided.")
            self.item_indices = []
            self.final_indices = []
        elif is_movement(instrument_object.instrument):
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
            # Use protocol-based type detection
            if is_movement(self.instrument_object.instrument):
                self.type = "Movement"
            elif is_measurement(self.instrument_object.instrument):
                self.type = "Measurement"
            else:
                self.type = "Unknown"
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
        has_item_indices = bool(self.item_indices)
        has_final_indices = bool(self.final_indices)
        
        # If we have an instrument but haven't been executed yet, we're not finished
        # This prevents single-position movements from appearing "finished" before execution
        if self.instrument_object is not None and not self._runtime_initialized:
            print(f"[finished] item='{self.name}': has instrument but not yet executed -> finished=False")
            return False
        
        if self.item_indices and self.final_indices:
            result = self.item_indices == self.final_indices
            print(f"[finished] item='{self.name}': item_indices={self.item_indices}, final_indices={self.final_indices} -> finished={result}")
            return result
        
        # All other items are finished when they have been performed once
        print(f"[finished] item='{self.name}': has_item_indices={has_item_indices}, has_final_indices={has_final_indices} -> finished=True (default)")
        return True
    
    def reset_children_indices(self):
        if self.child_items:
            for child in self.child_items:
                child.reset_indices()
    
    def reset_indices(self):
        self.item_indices = [0]
        self.reset_children_indices()

    def move_next(self) -> pd.DataFrame | bool:
        print(f"[move_next] item='{self.name}': instrument_object={self.instrument_object is not None}")
        # Check if instrument_object exists before accessing it
        if self.instrument_object is None:
            print(f"[move_next] item='{self.name}': FAILED - no instrument_object!")
            logger.warning(f"move_next called on item {self.name} with no instrument_object")
            return False
        if self.instrument_object.instrument is None:
            print(f"[move_next] item='{self.name}': FAILED - instrument_object has no instrument!")
            logger.warning(f"move_next called on item {self.name} with no instrument")
            return False
        print(f"[move_next] item='{self.name}': instrument={type(self.instrument_object.instrument).__name__}")
            
        if not self._runtime_initialized:
            self._runtime_initialized = True
            self.instrument_object.instrument.initialize()
            self.instrument_object.instrument.settings = self.instrument_object.settings

        
        if is_movement(self.instrument_object.instrument):
            if not self.item_indices or not self.final_indices:
                return False
            for i in reversed(range(len(self.item_indices))):
                if self.item_indices[i] < self.final_indices[i]:
                    self.item_indices[i] += 1
                else:
                    self.reset_indices()
                self.instrument_object.instrument.position = self.instrument_object.positions[self.item_indices[i]]  #type: ignore
                logger.debug(f"Moved to position {self.instrument_object.instrument.position}, with index {self.item_indices[i]} out of {self.final_indices[i]}")
                return True
            return False
        
        elif is_measurement(self.instrument_object.instrument):
            self.item_indices = [1]
            logger.debug(f"Performing measurement with instrument {self.instrument_object.instrument.name}")
            return self.instrument_object.instrument.measurement_df() #type: ignore
        
        return False

    def serialize(self) -> dict:
        # Convert movement_positions to list if it's a numpy array
        movement_positions = self.movement_positions
        if hasattr(movement_positions, 'tolist'):  # numpy array
            movement_positions = movement_positions.tolist()
        elif not isinstance(movement_positions, list):
            movement_positions = list(movement_positions) if movement_positions else []
        
        # Convert item_indices and final_indices to lists if they're numpy arrays
        item_indices = self.item_indices
        if hasattr(item_indices, 'tolist'):  # numpy array
            item_indices = item_indices.tolist()
        elif not isinstance(item_indices, list):
            item_indices = list(item_indices) if item_indices else []
            
        final_indices = self.final_indices
        if hasattr(final_indices, 'tolist'):  # numpy array
            final_indices = final_indices.tolist()
        elif not isinstance(final_indices, list):
            final_indices = list(final_indices) if final_indices else []
        
        data = {
            "name": self.name,
            "type": self.type,
            "adapter": self.adapter,
            "semaphore": self.semaphore,
            "item_indices": item_indices,
            "final_indices": final_indices,
            "movement_positions": movement_positions,
            "movement_entries": self.movement_entries,
            "checked": self.checked,
            "instrument_object": self.instrument_object.serialize() if self.instrument_object else None,
            "child_items": [child.serialize() for child in self.child_items]
        }
        #Traverse through the tree and find if any of the data is a numpy array. If so, raise an error and log the problematic data.
        def check_for_numpy(data):
            if isinstance(data, dict):
                for key, value in data.items():
                    if hasattr(value, 'tolist'):
                        logger.error(f"Numpy array found in key '{key}': {value}")
                        raise ValueError(f"Numpy array found in key '{key}'")
                    check_for_numpy(value)
            elif isinstance(data, list):
                for item in data:
                    check_for_numpy(item)
        
        check_for_numpy(data)
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

    # FastForward is now imported from traverser module
    # Keep as inner class alias for backward compatibility
    FastForward = TreeTraverser

    def propagate(self, ff: TreeTraverser) -> TreeTraverser:
        """
        Propagate traversal to the next item in the tree.
        
        This is a convenience method that delegates to the traverser module.
        """
        return _propagate(self, ff)
        
    def is_ancestor_of(self, descendant: 'InstrumentTreeItem') -> bool:
        """Check if this item is an ancestor of the given descendant item."""
        current = descendant.parent_item
        while current is not None:
            if current == self:
                return True
            current = current.parent_item
        return False




