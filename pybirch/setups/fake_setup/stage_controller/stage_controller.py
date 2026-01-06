"""
Fake Linear Stage Controller for testing and development.

This module demonstrates how to create movement instruments for a multi-axis
stage controller. Each axis (X, Y, Z) is a separate movement instrument that
shares a common controller backend.

Usage:
    # Create individual axis movements
    x_stage = FakeXStage("X Stage")
    y_stage = FakeYStage("Y Stage")
    z_stage = FakeZStage("Z Stage")
    
    # Control positions
    x_stage.connect()
    x_stage.position = 50.0  # Move to 50 mm
    print(f"X position: {x_stage.position}")
"""

import numpy as np

from pybirch.Instruments.base import FakeMovementInstrument, SimulatedDelay
from pybirch.scan.movements import Movement


class FakeAxis(SimulatedDelay):
    """
    A single axis of the fake linear stage controller.
    
    Each axis has its own position and limits, but shares a reference
    to the parent controller for timing simulation.
    """

    def __init__(self, axis: int, controller: "FakeLinearStageController"):
        super().__init__(controller._wait)
        self.axis = str(axis)
        self.controller = controller
        self._position = 0.0
        self._left_limit = 0.0
        self._right_limit = 100.0

    @property
    def position(self) -> float:
        self._delay()
        return self._position
    
    @position.setter
    def position(self, value: float):
        self._delay()
        if self._left_limit <= value <= self._right_limit:
            self._position = value
        else:
            raise ValueError(f"Position {value} out of bounds [{self._left_limit}, {self._right_limit}]")

    @property
    def left_limit(self) -> float:
        self._delay()
        return self._left_limit
    
    @left_limit.setter
    def left_limit(self, value: float):
        self._delay()
        self._left_limit = value

    @property
    def right_limit(self) -> float:
        self._delay()
        return self._right_limit

    @right_limit.setter
    def right_limit(self, value: float):
        self._delay()
        self._right_limit = value


class FakeLinearStageController(SimulatedDelay):
    """
    A fake 3-axis linear stage controller backend.
    
    This represents the hardware controller that manages X, Y, and Z axes.
    """
    
    def __init__(self, name: str = "Mock Linear Stage", wait: float = 0.0):
        super().__init__(wait)
        self.name = name
        self.x = FakeAxis(1, self)
        self.y = FakeAxis(2, self)
        self.z = FakeAxis(3, self)


# Shared controller instance for all axis movements
# In a real application, you might want to manage this differently
_shared_controller = None


def get_shared_controller(wait: float = 0.0) -> FakeLinearStageController:
    """Get or create the shared stage controller instance."""
    global _shared_controller
    if _shared_controller is None:
        _shared_controller = FakeLinearStageController(wait=wait)
    return _shared_controller


class FakeXStage(FakeMovementInstrument):
    """X-axis movement for the fake linear stage."""

    def __init__(self, name: str = "X Stage", use_shared_controller: bool = False):
        super().__init__(name)
        
        if use_shared_controller:
            self.controller = get_shared_controller()
        else:
            self.controller = FakeLinearStageController()
        
        self.position_units = "mm"
        self.position_column = "x position"
        
        self._define_settings({
            "left_limit": 0.0,
            "right_limit": 100.0,
        })
    
    @property
    def position(self) -> float:
        return self.controller.x.position
    
    @position.setter
    def position(self, value: float):
        self.controller.x.position = value
    
    def _initialize_impl(self):
        """Home the X axis."""
        self._delay()
        self.controller.x.position = 0.0
    
    @property
    def settings(self) -> dict:
        """Override to include position and limits."""
        return {
            "position": self.position,
            "units": self.position_units,
            "left_limit": self.controller.x.left_limit,
            "right_limit": self.controller.x.right_limit,
        }
    
    @settings.setter
    def settings(self, settings: dict):
        if "position" in settings:
            self.position = settings["position"]
        if "units" in settings:
            self.position_units = settings["units"]
        if "left_limit" in settings:
            self.controller.x.left_limit = settings["left_limit"]
        if "right_limit" in settings:
            self.controller.x.right_limit = settings["right_limit"]


class FakeYStage(FakeMovementInstrument):
    """Y-axis movement for the fake linear stage."""

    def __init__(self, name: str = "Y Stage", use_shared_controller: bool = False):
        super().__init__(name)
        
        if use_shared_controller:
            self.controller = get_shared_controller()
        else:
            self.controller = FakeLinearStageController()
        
        self.position_units = "mm"
        self.position_column = "y position"
        
        self._define_settings({
            "left_limit": 0.0,
            "right_limit": 100.0,
        })
    
    @property
    def position(self) -> float:
        return self.controller.y.position
    
    @position.setter
    def position(self, value: float):
        self.controller.y.position = value
    
    def _initialize_impl(self):
        """Home the Y axis."""
        self._delay()
        self.controller.y.position = 0.0
    
    @property
    def settings(self) -> dict:
        return {
            "position": self.position,
            "units": self.position_units,
            "left_limit": self.controller.y.left_limit,
            "right_limit": self.controller.y.right_limit,
        }
    
    @settings.setter
    def settings(self, settings: dict):
        if "position" in settings:
            self.position = settings["position"]
        if "units" in settings:
            self.position_units = settings["units"]
        if "left_limit" in settings:
            self.controller.y.left_limit = settings["left_limit"]
        if "right_limit" in settings:
            self.controller.y.right_limit = settings["right_limit"]


class FakeZStage(FakeMovementInstrument):
    """Z-axis movement for the fake linear stage."""

    def __init__(self, name: str = "Z Stage", use_shared_controller: bool = False):
        super().__init__(name)
        
        if use_shared_controller:
            self.controller = get_shared_controller()
        else:
            self.controller = FakeLinearStageController()
        
        self.position_units = "mm"
        self.position_column = "z position"
        
        self._define_settings({
            "left_limit": 0.0,
            "right_limit": 100.0,
        })
    
    @property
    def position(self) -> float:
        return self.controller.z.position
    
    @position.setter
    def position(self, value: float):
        self.controller.z.position = value
    
    def _initialize_impl(self):
        """Home the Z axis."""
        self._delay()
        self.controller.z.position = 0.0
    
    @property
    def settings(self) -> dict:
        return {
            "position": self.position,
            "units": self.position_units,
            "left_limit": self.controller.z.left_limit,
            "right_limit": self.controller.z.right_limit,
        }
    
    @settings.setter
    def settings(self, settings: dict):
        if "position" in settings:
            self.position = settings["position"]
        if "units" in settings:
            self.position_units = settings["units"]
        if "left_limit" in settings:
            self.controller.z.left_limit = settings["left_limit"]
        if "right_limit" in settings:
            self.controller.z.right_limit = settings["right_limit"]


# Legacy-style wrapper classes for backwards compatibility with scan system
class FakeXStageLegacy(Movement):
    """Legacy wrapper for FakeXStage."""
    
    def __init__(self, name: str = "X Stage"):
        super().__init__(name)
        self._impl = FakeXStage(name)
        self.position_units = self._impl.position_units
        self.position_column = self._impl.position_column
        # Expose controller for shared access
        self.instrument = self._impl.controller

    def check_connection(self) -> bool:
        return self._impl.check_connection()

    @property
    def position(self) -> float:
        return self._impl.position
    
    @position.setter
    def position(self, value: float):
        self._impl.position = value
    
    def connect(self):
        self._impl.connect()
        self.status = self._impl.status

    def initialize(self):
        self._impl.initialize()

    def shutdown(self):
        self._impl.shutdown()

    @property
    def settings(self) -> dict:
        return self._impl.settings
    
    @settings.setter
    def settings(self, settings: dict):
        self._impl.settings = settings


class FakeYStageLegacy(Movement):
    """Legacy wrapper for FakeYStage."""
    
    def __init__(self, name: str = "Y Stage"):
        super().__init__(name)
        self._impl = FakeYStage(name)
        self.position_units = self._impl.position_units
        self.position_column = self._impl.position_column
        self.instrument = self._impl.controller

    def check_connection(self) -> bool:
        return self._impl.check_connection()

    @property
    def position(self) -> float:
        return self._impl.position
    
    @position.setter
    def position(self, value: float):
        self._impl.position = value
    
    def connect(self):
        self._impl.connect()
        self.status = self._impl.status

    def initialize(self):
        self._impl.initialize()

    def shutdown(self):
        self._impl.shutdown()

    @property
    def settings(self) -> dict:
        return self._impl.settings
    
    @settings.setter
    def settings(self, settings: dict):
        self._impl.settings = settings


class FakeZStageLegacy(Movement):
    """Legacy wrapper for FakeZStage."""
    
    def __init__(self, name: str = "Z Stage"):
        super().__init__(name)
        self._impl = FakeZStage(name)
        self.position_units = self._impl.position_units
        self.position_column = self._impl.position_column
        self.instrument = self._impl.controller

    def check_connection(self) -> bool:
        return self._impl.check_connection()

    @property
    def position(self) -> float:
        return self._impl.position
    
    @position.setter
    def position(self, value: float):
        self._impl.position = value
    
    def connect(self):
        self._impl.connect()
        self.status = self._impl.status

    def initialize(self):
        self._impl.initialize()

    def shutdown(self):
        self._impl.shutdown()

    @property
    def settings(self) -> dict:
        return self._impl.settings
    
    @settings.setter
    def settings(self, settings: dict):
        self._impl.settings = settings