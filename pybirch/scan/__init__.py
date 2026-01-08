"""
PyBirch Scan Module

This module provides core scanning functionality for the PyBirch framework:
- Scan: Main scan execution engine
- Movement/Measurement: Base instrument classes
- State machines for item and scan states
- Tree traversal for parallel execution
- Cancellation tokens for clean abort handling
- Protocol definitions for type checking
"""

from pybirch.scan.scan import Scan, ScanSettings, get_empty_scan
from pybirch.scan.movements import Movement, VisaMovement, MovementItem
from pybirch.scan.measurements import Measurement, VisaMeasurement, MeasurementItem
from pybirch.scan.protocols import (
    MovementProtocol,
    MeasurementProtocol,
    is_movement,
    is_measurement,
    get_instrument_type,
)
from pybirch.scan.state import (
    ItemState,
    ScanState,
    StateMachine,
    ItemStateMachine,
    ScanStateMachine,
)
from pybirch.scan.traverser import TreeTraverser, propagate
from pybirch.scan.cancellation import (
    CancellationToken,
    CancellationTokenSource,
    CancellationError,
    CancellationType,
)

__all__ = [
    # Core
    "Scan",
    "ScanSettings",
    "get_empty_scan",
    # Instruments
    "Movement",
    "VisaMovement",
    "MovementItem",
    "Measurement",
    "VisaMeasurement", 
    "MeasurementItem",
    # Protocols
    "MovementProtocol",
    "MeasurementProtocol",
    "is_movement",
    "is_measurement",
    "get_instrument_type",
    # State
    "ItemState",
    "ScanState",
    "StateMachine",
    "ItemStateMachine",
    "ScanStateMachine",
    # Traversal
    "TreeTraverser",
    "propagate",
    # Cancellation
    "CancellationToken",
    "CancellationTokenSource",
    "CancellationError",
    "CancellationType",
]