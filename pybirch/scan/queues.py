from pybirch.scan.measurements import Measurement
import numpy as np
import pandas as pd
import time
import os
from pybirch.scan.movements import Movement
import wandb
from pybirch.scan.scan import Scan
from pymeasure.instruments import Instrument
from pymeasure.experiment import Results, Procedure
import pickle


class Queue:
    """A queue class to manage scans in the PyBirch framework."""

    def __init__(self, QID: str, scans: list[Scan] = []):
        self.scans = scans
        self.QID = QID

    def enqueue(self, item: Scan):
        self.scans.append(item)

    def dequeue(self, index: int = 0) -> Scan:
        if not self.is_empty():
            return self.scans.pop(index)
        raise IndexError("Queue is empty")

    def is_empty(self) -> bool:
        return len(self.scans) == 0

    def size(self) -> int:
        return len(self.scans)
    
    def clear(self):
        self.scans = []
    
    def start(self):
        for scan in self.scans:
            if not scan.scan_settings.completed:
                scan.run_scan()
                scan.scan_settings.completed = True
    
    

