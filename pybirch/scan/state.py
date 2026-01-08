"""
State machine for PyBirch scan item states.

This module defines the ItemState enum and state transition logic for
InstrumentTreeItem objects, providing a cleaner alternative to multiple
boolean flags.

Usage:
    from pybirch.scan.state import ItemState, ItemStateMachine
    
    state_machine = ItemStateMachine()
    state_machine.transition_to(ItemState.INITIALIZED)
    if state_machine.can_transition_to(ItemState.IN_PROGRESS):
        state_machine.transition_to(ItemState.IN_PROGRESS)
"""

from enum import Enum, auto
from typing import Set, Optional, Callable, Any
import logging

logger = logging.getLogger(__name__)


class ItemState(Enum):
    """State of an instrument tree item during scan execution."""
    
    PENDING = auto()       # Not yet started
    INITIALIZED = auto()   # Connected and initialized
    IN_PROGRESS = auto()   # Currently executing
    COMPLETED = auto()     # Finished successfully
    PAUSED = auto()        # Temporarily stopped
    ABORTED = auto()       # Cancelled by user
    FAILED = auto()        # Error occurred


class ScanState(Enum):
    """Overall state of a scan."""
    
    QUEUED = auto()        # Waiting to start
    STARTING = auto()      # Startup phase
    RUNNING = auto()       # Actively executing
    PAUSED = auto()        # Temporarily paused
    COMPLETING = auto()    # Finishing up
    COMPLETED = auto()     # Finished successfully
    ABORTED = auto()       # Cancelled by user
    FAILED = auto()        # Error occurred


# Valid state transitions for items
VALID_ITEM_TRANSITIONS: dict[ItemState, Set[ItemState]] = {
    ItemState.PENDING: {ItemState.INITIALIZED, ItemState.ABORTED, ItemState.FAILED},
    ItemState.INITIALIZED: {ItemState.IN_PROGRESS, ItemState.PAUSED, ItemState.ABORTED, ItemState.FAILED},
    ItemState.IN_PROGRESS: {ItemState.COMPLETED, ItemState.PAUSED, ItemState.ABORTED, ItemState.FAILED},
    ItemState.PAUSED: {ItemState.IN_PROGRESS, ItemState.ABORTED, ItemState.FAILED},
    ItemState.COMPLETED: set(),  # Terminal state
    ItemState.ABORTED: set(),    # Terminal state
    ItemState.FAILED: set(),     # Terminal state
}

# Valid state transitions for scans
VALID_SCAN_TRANSITIONS: dict[ScanState, Set[ScanState]] = {
    ScanState.QUEUED: {ScanState.STARTING, ScanState.ABORTED},
    ScanState.STARTING: {ScanState.RUNNING, ScanState.ABORTED, ScanState.FAILED},
    ScanState.RUNNING: {ScanState.COMPLETING, ScanState.PAUSED, ScanState.ABORTED, ScanState.FAILED},
    ScanState.PAUSED: {ScanState.RUNNING, ScanState.ABORTED},
    ScanState.COMPLETING: {ScanState.COMPLETED, ScanState.FAILED},
    ScanState.COMPLETED: set(),  # Terminal state
    ScanState.ABORTED: set(),    # Terminal state
    ScanState.FAILED: set(),     # Terminal state
}


class StateMachine:
    """Generic state machine with transition validation."""
    
    def __init__(
        self,
        initial_state: Any,
        valid_transitions: dict[Any, Set[Any]],
        on_transition: Optional[Callable[[Any, Any], None]] = None
    ):
        """
        Initialize the state machine.
        
        Args:
            initial_state: The starting state.
            valid_transitions: Dict mapping states to sets of valid next states.
            on_transition: Optional callback called on successful transitions.
        """
        self._state = initial_state
        self._valid_transitions = valid_transitions
        self._on_transition = on_transition
        self._history: list[Any] = [initial_state]
    
    @property
    def state(self) -> Any:
        """Get current state."""
        return self._state
    
    @property
    def history(self) -> list[Any]:
        """Get state transition history."""
        return self._history.copy()
    
    def can_transition_to(self, new_state: Any) -> bool:
        """
        Check if transition to new_state is valid.
        
        Args:
            new_state: The target state.
            
        Returns:
            True if the transition is allowed.
        """
        valid_next = self._valid_transitions.get(self._state, set())
        return new_state in valid_next
    
    def transition_to(self, new_state: Any, force: bool = False) -> bool:
        """
        Transition to a new state.
        
        Args:
            new_state: The target state.
            force: If True, skip validation (use with caution).
            
        Returns:
            True if transition was successful.
            
        Raises:
            ValueError: If transition is invalid and force=False.
        """
        if not force and not self.can_transition_to(new_state):
            valid_next = self._valid_transitions.get(self._state, set())
            raise ValueError(
                f"Invalid transition from {self._state} to {new_state}. "
                f"Valid transitions: {valid_next}"
            )
        
        old_state = self._state
        self._state = new_state
        self._history.append(new_state)
        
        if self._on_transition:
            self._on_transition(old_state, new_state)
        
        logger.debug(f"State transition: {old_state} -> {new_state}")
        return True
    
    def is_terminal(self) -> bool:
        """Check if current state is terminal (no valid transitions out)."""
        valid_next = self._valid_transitions.get(self._state, set())
        return len(valid_next) == 0
    
    def reset(self, initial_state: Optional[Any] = None) -> None:
        """Reset to initial state or specified state."""
        if initial_state is None:
            initial_state = self._history[0]
        self._state = initial_state
        self._history = [initial_state]


class ItemStateMachine(StateMachine):
    """State machine for instrument tree items."""
    
    def __init__(
        self,
        initial_state: ItemState = ItemState.PENDING,
        on_transition: Optional[Callable[[ItemState, ItemState], None]] = None
    ):
        super().__init__(initial_state, VALID_ITEM_TRANSITIONS, on_transition)
    
    @property
    def is_active(self) -> bool:
        """Check if item is in an active (non-terminal) state."""
        return self._state in {ItemState.INITIALIZED, ItemState.IN_PROGRESS, ItemState.PAUSED}
    
    @property
    def is_finished(self) -> bool:
        """Check if item has finished (terminal state)."""
        return self._state in {ItemState.COMPLETED, ItemState.ABORTED, ItemState.FAILED}
    
    @property
    def is_running(self) -> bool:
        """Check if item is currently running."""
        return self._state == ItemState.IN_PROGRESS
    
    # Convenience methods for common transitions
    def initialize(self) -> bool:
        """Transition from PENDING to INITIALIZED."""
        return self.transition_to(ItemState.INITIALIZED)
    
    def start(self) -> bool:
        """Transition to IN_PROGRESS."""
        return self.transition_to(ItemState.IN_PROGRESS)
    
    def complete(self) -> bool:
        """Transition to COMPLETED."""
        return self.transition_to(ItemState.COMPLETED)
    
    def pause(self) -> bool:
        """Transition to PAUSED."""
        return self.transition_to(ItemState.PAUSED)
    
    def resume(self) -> bool:
        """Transition from PAUSED to IN_PROGRESS."""
        return self.transition_to(ItemState.IN_PROGRESS)
    
    def abort(self) -> bool:
        """Transition to ABORTED."""
        return self.transition_to(ItemState.ABORTED)
    
    def fail(self) -> bool:
        """Transition to FAILED."""
        return self.transition_to(ItemState.FAILED)


class ScanStateMachine(StateMachine):
    """State machine for overall scan state."""
    
    def __init__(
        self,
        initial_state: ScanState = ScanState.QUEUED,
        on_transition: Optional[Callable[[ScanState, ScanState], None]] = None
    ):
        super().__init__(initial_state, VALID_SCAN_TRANSITIONS, on_transition)
    
    @property
    def is_active(self) -> bool:
        """Check if scan is in an active state."""
        return self._state in {ScanState.STARTING, ScanState.RUNNING, ScanState.PAUSED, ScanState.COMPLETING}
    
    @property
    def is_finished(self) -> bool:
        """Check if scan has finished."""
        return self._state in {ScanState.COMPLETED, ScanState.ABORTED, ScanState.FAILED}
    
    @property
    def is_running(self) -> bool:
        """Check if scan is actively running."""
        return self._state == ScanState.RUNNING


def legacy_state_to_item_state(runtime_initialized: bool, finished: bool) -> ItemState:
    """
    Convert legacy boolean flags to ItemState.
    
    This function helps migrate code from the old boolean flag approach
    to the new state machine.
    
    Args:
        runtime_initialized: The _runtime_initialized flag value.
        finished: The result of finished() method.
        
    Returns:
        Corresponding ItemState value.
    """
    if finished:
        return ItemState.COMPLETED
    elif runtime_initialized:
        return ItemState.IN_PROGRESS
    else:
        return ItemState.PENDING


def legacy_flags_to_scan_state(completed: bool, paused: bool, stopped: bool) -> ScanState:
    """
    Convert legacy ScanTreeModel flags to ScanState.
    
    Args:
        completed: The completed flag.
        paused: The paused flag.
        stopped: The stopped flag.
        
    Returns:
        Corresponding ScanState value.
    """
    if completed:
        return ScanState.COMPLETED
    elif stopped:
        return ScanState.ABORTED
    elif paused:
        return ScanState.PAUSED
    else:
        return ScanState.QUEUED
