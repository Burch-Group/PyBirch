import re
import time
import numpy as np
import pandas as pd

from pymeasure.adapters import FakeAdapter
from pymeasure.instruments import Instrument, fakes


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
    def __init__(self, name="Mock Linear Stage", wait=.1, **kwargs):
        super().__init__(
            name=name,
            includeSCPI=False,
            **kwargs
        )
        self._wait = wait
        self.x = FakeAxis(1, self)
        self.y = FakeAxis(2, self)
        self.z = FakeAxis(3, self)

