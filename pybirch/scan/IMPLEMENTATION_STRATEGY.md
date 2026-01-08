# PyBirch Scan System Refactoring - Implementation Strategy

## Overview

This document outlines the systematic approach to modernizing the PyBirch scan system while maintaining backward compatibility and ensuring no regressions.

## Goals

1. **Remove wandb coupling** - Eliminate direct wandb dependency from core scan logic
2. **Modernize type system** - Replace `__base_class__()` with Protocol pattern
3. **Improve state management** - State machine instead of boolean flags
4. **Decouple traversal logic** - Extract `FastForward` into `TreeTraverser`
5. **Better cancellation handling** - Implement `CancellationToken` pattern
6. **Code quality** - Remove duplicate imports, use logging, fix type hints

---

## Phase 1: Test Foundation (MUST DO FIRST)

### 1.1 Create Baseline Tests
- Test scan creation and serialization
- Test tree traversal with `FastForward`
- Test `move_next()` for Movement and Measurement items
- Test parallel execution
- Test pause/abort/restart functionality
- Test data saving pipeline

### 1.2 Verify Tests Pass
- Run all tests against current implementation
- Document any existing failures
- Establish baseline coverage

---

## Phase 2: Remove wandb

### 2.1 Changes Required

| File | Change |
|------|--------|
| `scan.py` | Remove `import wandb`, `wandb.login()`, `wandb.init()`, `wandb.finish()`, `self.run`, `self.wandb_tables` |
| `scan.py` | Remove wandb table creation in `startup()` |
| `scan.py` | Remove wandb logging in `_save_data_async()` |
| `scan.py` | Update `__getstate__`/`__setstate__` to remove wandb references |

### 2.2 Replacement Strategy
- Data saving will rely solely on extensions
- Extensions can implement wandb, database, file-based logging as needed
- No changes to extension interface required

---

## Phase 3: Protocol Classes

### 3.1 Define Protocols

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class MovementProtocol(Protocol):
    name: str
    nickname: str
    adapter: str
    position: float
    position_units: str
    position_column: str
    
    def connect(self) -> None: ...
    def initialize(self) -> None: ...
    def shutdown(self) -> None: ...
    def check_connection(self) -> bool: ...

@runtime_checkable
class MeasurementProtocol(Protocol):
    name: str
    nickname: str
    adapter: str
    
    def connect(self) -> None: ...
    def initialize(self) -> None: ...
    def shutdown(self) -> None: ...
    def measurement_df(self) -> pd.DataFrame: ...
    def columns(self) -> np.ndarray: ...
```

### 3.2 Migration Path
1. Create `protocols.py` with Protocol definitions
2. Update `Movement` and `Measurement` to satisfy protocols
3. Replace `instrument.__base_class__()` checks with `isinstance(instrument, Protocol)`
4. Remove `__base_class__()` methods

---

## Phase 4: State Machine

### 4.1 Define States

```python
class ItemState(Enum):
    PENDING = auto()      # Not yet started
    INITIALIZED = auto()  # Connected and initialized
    IN_PROGRESS = auto()  # Currently executing
    COMPLETED = auto()    # Finished successfully
    PAUSED = auto()       # Temporarily stopped
    ABORTED = auto()      # Cancelled by user
    FAILED = auto()       # Error occurred
```

### 4.2 Valid Transitions

```
PENDING -> INITIALIZED -> IN_PROGRESS -> COMPLETED
                      \-> PAUSED -> IN_PROGRESS
                      \-> ABORTED
                      \-> FAILED
```

### 4.3 Implementation
- Add `_state: ItemState` to `InstrumentTreeItem`
- Add `transition_to(new_state)` method with validation
- Replace `_runtime_initialized`, `finished()` logic with state checks

---

## Phase 5: TreeTraverser

### 5.1 Extract from FastForward

Current inner class responsibilities:
1. Track visited items (`unique_ids`)
2. Check parallelization constraints (`semaphore`, `type`, `adapter`)
3. Build execution batch (`stack`)
4. Determine next item (`final_item`)

### 5.2 New Design

```python
@dataclass
class TraversalResult:
    batch: List[InstrumentTreeItem]  # Items to execute in parallel
    next_start: Optional[InstrumentTreeItem]  # Where to continue
    is_complete: bool

class TreeTraverser:
    def __init__(self):
        self.visited: Set[str] = set()
        self.semaphores: List[str] = []
        self.types: Dict[str, List[str]] = {}
        self.adapters: Dict[str, List[str]] = {}
    
    def collect_batch(self, start: InstrumentTreeItem) -> TraversalResult:
        """Collect parallelizable items starting from given node."""
        ...
    
    def can_parallelize(self, item: InstrumentTreeItem) -> bool:
        """Check if item can run with current batch."""
        ...
    
    def reset(self) -> None:
        """Clear state for new traversal."""
        ...
```

---

## Phase 6: CancellationToken

### 6.1 Implementation

```python
@dataclass
class CancellationToken:
    _cancelled: Event = field(default_factory=Event)
    _paused: Event = field(default_factory=Event)
    
    def __post_init__(self):
        self._paused.set()  # Not paused initially
    
    def cancel(self) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    
    @property
    def is_cancelled(self) -> bool: ...
    
    def wait_if_paused(self, timeout: float = None) -> bool: ...
    def check_cancelled(self) -> None:  # Raises if cancelled
        ...
```

### 6.2 Integration
- Pass `CancellationToken` to `Scan.execute()`
- Check token in main loop instead of `_stop_event`
- Pass to `TreeTraverser` for interruptible traversal

---

## Phase 7: Code Quality

### 7.1 Fixes
- Remove duplicate `import os` in `scan.py`
- Remove `sys.path.append()` calls
- Replace `print()` with `logging`
- Add proper type hints
- Remove `# type: ignore` where possible

### 7.2 Logging Setup

```python
import logging

logger = logging.getLogger(__name__)

# Replace print statements
logger.info(f"Starting scan: {self.scan_settings.scan_name}")
logger.debug(f"Moved to position {position}")
logger.error(f"Error connecting: {e}")
```

---

## Execution Order

1. ✅ Create documentation (this file, notes.md, issues.md)
2. 🔲 Write comprehensive tests
3. 🔲 Run baseline tests (verify green)
4. 🔲 Remove wandb (run tests)
5. 🔲 Add Protocol classes (run tests)
6. 🔲 Implement State Machine (run tests)
7. 🔲 Extract TreeTraverser (run tests)
8. 🔲 Add CancellationToken (run tests)
9. 🔲 Code quality fixes (run tests)
10. 🔲 Final verification

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking existing scans | Tests first, incremental changes |
| Serialization changes break pickled scans | Add migration path in `__setstate__` |
| Thread safety issues | Keep existing Lock patterns |
| Extension compatibility | Don't change extension interface |

---

## Success Criteria

- [ ] All existing tests pass
- [ ] All new tests pass
- [ ] No `wandb` imports remain
- [ ] No `__base_class__()` calls remain
- [ ] State machine correctly tracks item states
- [ ] TreeTraverser is standalone and testable
- [ ] CancellationToken provides clean abort
- [ ] No `print()` statements remain (use logging)
- [ ] Type hints are complete
