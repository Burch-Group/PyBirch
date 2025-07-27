import numpy as np
import pandas as pd
from pymeasure.instruments import Instrument

class Measurement:
    """Base class for measurement tools in the PyBirch framework."""
    
    def __init__(self, name, instrument):
        self.name = name
        self.instrument = instrument
        self.data_dimensions = None
        self.data_units = None
        self.data_columns = None
        
    def perform_measurement(self):
        # Perform the measurement and return the result as a pandas DataFrame
        raise NotImplementedError("Subclasses should implement this method.")
    
    @property
    def settings(self):
        # Get the current settings of the instrument, as a dictionary
        raise NotImplementedError("Subclasses should implement this method.")
    
    @settings.setter
    def settings(self, dict):
        # Set the settings of the instrument, from a dictionary
        raise NotImplementedError("Subclasses should implement this method.")

    def connect(self):
        # Connect to the instrument
        raise NotImplementedError("Subclasses should implement this method.")

    def initialize(self):
        # Initialize the measurement equipment
        pass

    def shutdown(self):
        # Shutdown the measurement equipment
        pass


