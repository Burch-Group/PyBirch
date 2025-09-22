import re
import time
import numpy as np
import pandas as pd

from pymeasure.adapters import FakeAdapter
from pymeasure.instruments import Instrument, fakes
from pybirch.scan.movements import Movement


class FakeAxis:
    """A fake axis for simulating a linear stage controller."""

    def __init__(self, axis, controller):
        self.axis = str(axis)
        self.controller = controller
        self._position = 0.0
        self._left_limit = 0.0
        self._right_limit = 100.0
        self._units = np.array(["mm"])  # Units for position


    @property
    def position(self):
        time.sleep(self.controller._wait)
        return self._position
    
    @position.setter
    def position(self, value):
        time.sleep(self.controller._wait)
        if self.left_limit <= value <= self.right_limit:
            self._position = value
        else:
            raise ValueError("Position out of bounds")

    @property
    def left_limit(self):
        time.sleep(self.controller._wait)
        return 0.0
    
    @left_limit.setter
    def left_limit(self, value):
        time.sleep(self.controller._wait)
        self._left_limit = value

    @property
    def right_limit(self):
        time.sleep(self.controller._wait)
        return self._right_limit

    @right_limit.setter
    def right_limit(self, value):
        time.sleep(self.controller._wait)
        self._right_limit = value



class FakeLinearStageController(fakes.FakeInstrument):
    def __init__(self, name: str ="Mock Linear Stage", wait: float = 0, **kwargs):
        super().__init__(
            name=name,
            includeSCPI=False,
            **kwargs
        )
        self._wait = wait
        self.x = FakeAxis(1, self)
        self.y = FakeAxis(2, self)
        self.z = FakeAxis(3, self)

class FakeXStage(Movement):
    def __init__(self, name: str):
        super().__init__(name)
        self.instrument = FakeLinearStageController()
        self.position_units = "mm"
        self.position_column = "x position"
    
    @property
    def position(self) -> float:
        return self.instrument.x.position
    @position.setter
    def position(self, value: float):
        self.instrument.x.position = value
    @property
    def settings(self) -> dict:
        return {
            "position": self.position,
            "units": self.position_units,
            "left_limit": self.instrument.x.left_limit,
            "right_limit": self.instrument.x.right_limit
        }
    @settings.setter
    def settings(self, settings: dict):
        if "position" in settings:
            self.position = settings["position"]
        if "units" in settings:
            self.position_units = settings["units"]
        if "left_limit" in settings:
            self.instrument.x.left_limit = settings["left_limit"]
        if "right_limit" in settings:
            self.instrument.x.right_limit = settings["right_limit"]

    def connect(self):
        # Connect to the instrument
        time.sleep(self.instrument._wait)
        return  
    def initialize(self):
        # Initialize the movement equipment
        time.sleep(self.instrument._wait)
        self.instrument.x.position = 0.0
        return
    def shutdown(self):
        # Shutdown the movement equipment
        time.sleep(self.instrument._wait)
        return
    
class FakeYStage(Movement):
    def __init__(self, name: str):
        super().__init__(name)
        self.instrument = FakeLinearStageController()
        self.position_units = "mm"
        self.position_column = "y position"

    @property
    def position(self) -> float:
        return self.instrument.y.position

    @position.setter
    def position(self, value: float):
        self.instrument.y.position = value

    @property
    def settings(self) -> dict:
        return {
            "position": self.position,
            "units": self.position_units,
            "left_limit": self.instrument.y.left_limit,
            "right_limit": self.instrument.y.right_limit
        }

    @settings.setter
    def settings(self, settings: dict):
        if "position" in settings:
            self.position = settings["position"]
        if "units" in settings:
            self.position_units = settings["units"]
        if "left_limit" in settings:
            self.instrument.y.left_limit = settings["left_limit"]
        if "right_limit" in settings:
            self.instrument.y.right_limit = settings["right_limit"]

    def connect(self):
        # Connect to the instrument
        time.sleep(self.instrument._wait)
        return

    def initialize(self):
        # Initialize the movement equipment
        time.sleep(self.instrument._wait)
        self.instrument.y.position = 0.0
        return

    def shutdown(self):
        # Shutdown the movement equipment
        time.sleep(self.instrument._wait)
        return
    
class FakeZStage(Movement):
    def __init__(self, name: str):
        super().__init__(name)
        self.instrument = FakeLinearStageController()
        self.position_units = "mm"
        self.position_column = "z position"

    @property
    def position(self) -> float:
        return self.instrument.z.position

    @position.setter
    def position(self, value: float):
        self.instrument.z.position = value

    @property
    def settings(self) -> dict:
        return {
            "position": self.position,
            "units": self.position_units,
            "left_limit": self.instrument.z.left_limit,
            "right_limit": self.instrument.z.right_limit
        }

    @settings.setter
    def settings(self, settings: dict):
        if "position" in settings:
            self.position = settings["position"]
        if "units" in settings:
            self.position_units = settings["units"]
        if "left_limit" in settings:
            self.instrument.z.left_limit = settings["left_limit"]
        if "right_limit" in settings:
            self.instrument.z.right_limit = settings["right_limit"]

    def connect(self):
        # Connect to the instrument
        time.sleep(self.instrument._wait)
        return

    def initialize(self):
        # Initialize the movement equipment
        time.sleep(self.instrument._wait)
        self.instrument.z.position = 0.0
        return

    def shutdown(self):
        # Shutdown the movement equipment
        time.sleep(self.instrument._wait)
        return