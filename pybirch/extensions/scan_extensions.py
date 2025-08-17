import numpy as np
import pandas as pd
from pybirch.scan.scan import MovementDict, Scan

class ScanExtension:
    """Base class for all scan extensions in the PyBirch framework."""

    def __init__(self):
        raise NotImplementedError("Subclasses should implement this method.")
    
    def startup(self, scan: Scan):
        """This method is run when a scan is started."""
        pass
    
    def save_data(self, scan: Scan, data: pd.DataFrame, measurement_name: str):
        """This method is run when a scan saves data."""
        pass

    def move_to_positions(self, scan: Scan, items_to_move: list[tuple[MovementDict, float]]):
        """This method is run when a scan moves instruments to position."""
        pass

    def take_measurements(self, scan: Scan):
        """This method is run when a scan takes measurements."""
        pass

    def execute(self, scan: Scan):
        """This method is run when a scan is executed."""
        pass

    def shutdown(self, scan: Scan):
        """This method is run when a scan is shutdown."""
        pass
