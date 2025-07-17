class Movement:
    # Base class for movement in the PyBirch framework

    def __init__(self, name, instrument):
        self.name = name
        self.instrument = instrument
        self.position_shape = None
        self.position_units = None

    @property
    def position(self):
        # Get the current position of the instrument
        raise NotImplementedError("Subclasses should implement this method.")

    @position.setter
    def position(self, value):
        # Set the position of the instrument
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
        # Initialize the movement equipment
        pass

    def shutdown(self):
        # Shutdown the movement equipment
        pass
