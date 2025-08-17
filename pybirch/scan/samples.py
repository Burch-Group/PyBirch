import numpy as np
import pandas as pd
import os
import random
import pickle

class Sample():
    """A class to represent a sample in the PyBirch framework."""

    def __init__(self, ID: str, material: str = '', additional_tags: list[str] = [], image: np.ndarray = np.array([])):
        self.ID = ID
        self.material = material
        self.additional_tags = additional_tags
        self.image = image


    def get_properties(self):
        # Implement this when we have access to LabLinQR
        # for now, just add some random properties
        self.material = random.choice(['Au', 'Pt', 'TaAs', 'Graphene'])
        self.additional_tags = random.sample(['asterisk', 'hall_bar', 'cross', 'bulk', 'armylab'], 2)
        return
