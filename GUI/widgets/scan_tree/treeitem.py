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
    def __init__(self, parent: 'InstrumentTreeItem' = None, instrument_object: Movement | VisaMovement | Measurement | VisaMeasurement = Measurement('default'), indices: list[int] = [], final_indices: list[int] = [], semaphore: str = ""):  #type: ignore
        self.instrument_object = instrument_object
        self.item_indices = indices
        self.final_indices = final_indices
        self.parent_item = parent
        self.semaphore: str = semaphore
        if self.instrument_object is None:
            self.name = ""
            self.type = ""
            self.adapter = ""
        else:
            self.name = instrument_object.nickname
            self.type = instrument_object.__class__.__bases__[0].__name__
            self.adapter = instrument_object.adapter

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
                self.final_indices = [len(instrument_object.positions) - 1]  #type: ignore
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

    def set_data(self, instrument_object: Movement | VisaMovement | Measurement | VisaMeasurement = Measurement('Default Instrument'), indices: list[int] = [], final_indices: list[int] = [], semaphore: str = "") -> bool:
        self.instrument_object = instrument_object
        self.item_indices = indices
        self.final_indices = final_indices
        self.semaphore = semaphore

        if self.instrument_object is None:
            self.name = ""
            self.type = ""
            self.adapter = ""
        else:
            self.name = instrument_object.nickname
            self.type = instrument_object.__class__.__bases__[0].__name__
            self.adapter = instrument_object.adapter

        self.columns = [self.name, self.type, self.adapter, self.semaphore]
        return True

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
            if next == next.parent().last_child() and not next.child_items:
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
        




