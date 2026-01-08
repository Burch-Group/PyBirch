from typing import TYPE_CHECKING
import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from pybirch.scan.movements import MovementItem

class ScanExtension:
    """Base class for all scan extensions in the PyBirch framework."""

    def __init__(self):
        raise NotImplementedError("Subclasses should implement this method.")
    
    def startup(self):
        """This method is run when a scan is started."""
        pass
    
    def save_data(self, data: pd.DataFrame, measurement_name: str):
        """This method is run when a scan saves data."""
        pass

    def move_to_positions(self, items_to_move: list[tuple["MovementItem", float]]):
        """This method is run when a scan moves instruments to position."""
        pass

    def take_measurements(self):
        """This method is run when a scan takes measurements."""
        pass

    def execute(self):
        """This method is run when a scan is executed."""
        pass

    def shutdown(self):
        """This method is run when a scan is shutdown."""
        pass
