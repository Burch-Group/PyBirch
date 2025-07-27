import numpy as np
import pandas as pd
import os
import random

class sample():
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

    def load_from_file(self, file_path):
        # Load sample properties from a sample directory using device ID as filename    
        try:
            data = pd.read_csv(os.path.join(file_path, f"{self.ID}.csv"))
            # Parse the data from .csv and set properties
            self.material = data.get('material', None)
            self.additional_tags = data.get('additional_tags', [])
            self.image = data.get('image', None)
        except Exception as e:
            print(f"Error loading sample from file: {e}")
            

    def save_to_file(self, file_path):
        try:
            data = {
                'ID': self.ID,
                'material': self.material,
                'additional_tags': ','.join(self.additional_tags),
                'image': self.image
            }
            df = pd.DataFrame([data])
            df.to_csv(os.path.join(file_path, f"{self.ID}.csv"), index=False)
        except Exception as e:
            print(f"Error saving sample to file: {e}")