from measurement import Measurement
import numpy as np
import pandas as pd
import time
import os
from movement import Movement
import wandb
from procedure import Scan
from pymeasure.instruments import Instrument
from pymeasure.experiment import Results, Procedure


class Queue:
    """A simple queue class to manage scans in the PyBirch framework."""
    def __init__(self, QID: str):
        self.scans: list[Scan] = []
        self.QID = QID

    def enqueue(self, item):
        self.items.append(item)

    def dequeue(self):
        if not self.is_empty():
            return self.items.pop(0)
        raise IndexError("Queue is empty")

    def is_empty(self):
        return len(self.items) == 0

    def size(self):
        return len(self.items)
