"""
Tree Traverser for PyBirch scan trees.

This module provides the TreeTraverser (formerly FastForward) class that handles
batching items for parallel execution based on semaphores and type compatibility.

The traverser determines which items can execute in parallel by grouping items
that share the same semaphore or have no blocking dependencies.

Usage:
    from pybirch.scan.traverser import TreeTraverser
    
    traverser = TreeTraverser(root_item)
    while not traverser.done:
        batch = traverser.get_batch()
        for item in batch:
            item.move_next()
        traverser = traverser.advance()
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List, Dict, Set
import logging

if TYPE_CHECKING:
    from GUI.widgets.scan_tree.treeitem import InstrumentTreeItem

logger = logging.getLogger(__name__)


class TreeTraverser:
    """
    Traverses an instrument tree and batches compatible items for parallel execution.
    
    The traverser walks through the tree, collecting items that can execute together
    based on their semaphores, types, and adapters. Items with the same semaphore
    can batch together; items with different semaphores create a boundary.
    
    Formerly known as FastForward in treeitem.py.
    
    Attributes:
        current_item: The item currently being processed.
        stack: Items collected for the current batch.
        done: Whether traversal is complete.
        semaphores: Semaphores seen in the current batch.
        types: Mapping of types to their semaphores.
        adapters: Mapping of adapters to their semaphores.
        unique_ids: IDs of items already processed (prevents duplicates).
        final_item: The item that caused traversal to stop (if any).
    """
    
    def __init__(self, current_item: 'InstrumentTreeItem'):
        """
        Initialize the traverser at the given item.
        
        Args:
            current_item: The starting item for traversal.
        """
        self.current_item: 'InstrumentTreeItem' = current_item
        self.stack: List['InstrumentTreeItem'] = []
        self.done: bool = False
        self.semaphores: List[str] = []
        self.types: Dict[str, List[str]] = {}
        self.adapters: Dict[str, List[str]] = {}
        self.unique_ids: List[str] = []
        self.final_item: Optional['InstrumentTreeItem'] = None
    
    @property
    def semaphore(self) -> List[str]:
        """Alias for semaphores (backward compatibility)."""
        return self.semaphores
    
    @semaphore.setter
    def semaphore(self, value: List[str]) -> None:
        self.semaphores = value
    
    @property
    def type(self) -> Dict[str, List[str]]:
        """Alias for types (backward compatibility)."""
        return self.types
    
    @type.setter
    def type(self, value: Dict[str, List[str]]) -> None:
        self.types = value
    
    @property
    def adapter(self) -> Dict[str, List[str]]:
        """Alias for adapters (backward compatibility)."""
        return self.adapters
    
    @adapter.setter
    def adapter(self, value: Dict[str, List[str]]) -> None:
        self.adapters = value
    
    def check_if_last(self, next_item: 'InstrumentTreeItem') -> bool:
        """
        Check if the next item should end the current batch.
        
        An item ends the batch if:
        - It has an adapter conflict (different semaphore for same adapter)
        - It has a type conflict (incompatible type with no shared semaphore)
        - It has a semaphore conflict (different semaphore with existing batch)
        - It was already processed (duplicate ID)
        
        Args:
            next_item: The item to check.
            
        Returns:
            True if this item should end the batch, False if it can join.
        """
        # Check adapter conflict
        if (next_item.adapter in self.adapters.keys() and 
            next_item.semaphore and 
            next_item.semaphore not in self.adapters[next_item.adapter]):
            logger.debug(f"Adapter conflict for '{next_item.adapter}'")
            return True
        
        # Check type conflict
        if (self.types.keys() and 
            next_item.type not in self.types.keys() and 
            ((next_item.semaphore and all(next_item.semaphore not in sems for sems in self.types.values())) 
             or not next_item.semaphore)):
            logger.debug(f"Type check failed for type '{next_item.type}', current types: {list(self.types.keys())}")
            return True
        else:
            logger.debug(f"Type check passed for type '{next_item.type}', current types: {list(self.types.keys())}")
        
        # Check semaphore conflict
        if next_item.semaphore and self.semaphores and next_item.semaphore not in self.semaphores:
            logger.debug(f"Semaphore '{next_item.semaphore}' not in current semaphores: {self.semaphores}")
            return True
        
        # Check for duplicate
        if next_item.unique_id() in self.unique_ids:
            logger.debug(f"Duplicate item detected: {next_item.unique_id()}")
            return True
        
        return False
    
    def new_item(self, item: 'InstrumentTreeItem') -> 'TreeTraverser':
        """
        Process a new item and add it to the batch if compatible.
        
        Args:
            item: The item to process.
            
        Returns:
            Self for method chaining.
        """
        self.current_item = item
        self.current_item.reset_children_indices()
        
        if self.check_if_last(item):
            self.final_item = item
            self.done = True
            logger.debug(f"TreeTraverser reached final item: {item.name}")
            return self
        
        logger.debug(f"TreeTraverser adding item: {item.name}")
        
        if item.semaphore and item.semaphore not in self.semaphores:
            self.semaphores.append(item.semaphore)
        
        if item.unique_id() not in self.unique_ids:
            self.unique_ids.append(item.unique_id())
        
        # Update type and adapter mappings with semaphore info
        for characteristic in ['type', 'adapter']:
            value = getattr(item, characteristic)
            logger.debug(f"Processing characteristic '{characteristic}' with value '{value}'")
            if value:
                mapping = getattr(self, f"{characteristic}s")  # types or adapters
                existing = mapping.get(value, [])
                if item.semaphore:
                    mapping[value] = existing + [item.semaphore]
                else:
                    mapping[value] = existing
        
        self.stack.append(item)
        return self
    
    def get_batch(self) -> List['InstrumentTreeItem']:
        """
        Get the current batch of items for parallel execution.
        
        Returns:
            List of items that can execute together.
        """
        return self.stack.copy()
    
    def clear_batch(self) -> None:
        """Clear the current batch after processing."""
        self.stack.clear()
        self.semaphores.clear()
        self.types.clear()
        self.adapters.clear()
        self.unique_ids.clear()
        self.final_item = None
        self.done = False


# Backward compatibility alias
FastForward = TreeTraverser


def propagate(item: 'InstrumentTreeItem', traverser: TreeTraverser) -> TreeTraverser:
    """
    Propagate traversal from the current item to the next logical item.
    
    This implements the tree walking logic:
    1. If item has children and either isn't finished OR has no instrument (is a container), go to first child
    2. If item has a next sibling, go to that sibling
    3. If item is last child, go back up to parent and check if parent is finished
    
    Args:
        item: The current item.
        traverser: The traverser to update.
        
    Returns:
        The updated traverser.
    """
    item_name = getattr(item, 'name', 'N/A')
    has_children = bool(item.child_items)
    is_finished = item.finished()
    has_instr_obj = item.instrument_object is not None if hasattr(item, 'instrument_object') else False
    
    # Check if this is a container node (has children but no instrument)
    # Container nodes should always traverse to children, regardless of "finished" status
    is_container = has_children and not has_instr_obj
    
    print(f"[propagate] item='{item_name}', has_children={has_children}, finished={is_finished}, has_instrument_object={has_instr_obj}, is_container={is_container}")
    
    # CRITICAL: Items with children should ALWAYS check children first, regardless of own finished status
    # A parent being "finished" just means it moved to all its positions, but children still need to run
    # at each parent position
    if item.child_items:
        # Check if any child is unfinished before traversing
        any_unfinished_child = any(not child.finished() for child in item.child_items)
        print(f"[propagate]   Checking children: any_unfinished_child={any_unfinished_child}")
        
        if any_unfinished_child:
            # Find the first unfinished child
            for child in item.child_items:
                if not child.finished():
                    child_name = getattr(child, 'name', 'N/A')
                    print(f"[propagate] -> Going to unfinished child: '{child_name}'")
                    return traverser.new_item(child)
    
    if item.parent_item and item != item.parent_item.last_child():
        # Go to next sibling
        next_sibling = item.parent_item.child(item.child_number() + 1)
        sibling_name = getattr(next_sibling, 'name', 'N/A')
        print(f"[propagate] -> Going to next sibling: '{sibling_name}'")
        return traverser.new_item(next_sibling)
    elif item.parent_item:
        # Go back up the tree to find unfinished ancestor
        next_item = item.parent_item
        print(f"[propagate] -> Going back up tree, checking parent: '{getattr(next_item, 'name', 'N/A')}'")
        while next_item.finished():
            # Also check if parent is a container with unfinished children
            parent_is_container = bool(next_item.child_items) and (next_item.instrument_object is None if hasattr(next_item, 'instrument_object') else True)
            has_unfinished_children = any(not c.finished() for c in next_item.child_items) if next_item.child_items else False
            print(f"[propagate]    Parent '{getattr(next_item, 'name', 'N/A')}' is finished, is_container={parent_is_container}, has_unfinished_children={has_unfinished_children}")
            
            if parent_is_container and has_unfinished_children:
                print(f"[propagate] -> Container parent has unfinished children, staying at: '{getattr(next_item, 'name', 'N/A')}'")
                return traverser.new_item(next_item)
            
            if next_item.parent():
                next_item = next_item.parent()
            else:
                print(f"[propagate] -> Reached top, traverser done")
                traverser.done = True
                return traverser
        print(f"[propagate] -> Found unfinished ancestor: '{getattr(next_item, 'name', 'N/A')}'")
        return traverser.new_item(next_item)
    else:
        # Root with no children - done
        # But if root has children and is a container, we should have gone to children above
        if has_children:
            # This shouldn't happen if we properly handled containers above
            any_unfinished = any(not child.finished() for child in item.child_items)
            print(f"[propagate] -> Root has children but fell through! any_unfinished={any_unfinished}")
            if any_unfinished:
                for child in item.child_items:
                    if not child.finished():
                        child_name = getattr(child, 'name', 'N/A')
                        print(f"[propagate] -> Emergency: going to unfinished child: '{child_name}'")
                        return traverser.new_item(child)
        
        print(f"[propagate] -> Root with no children or all children finished, traverser done")
        traverser.done = True
        return traverser
