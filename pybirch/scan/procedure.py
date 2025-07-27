import pymeasure
import numpy as np
import pandas as pd
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter
from movement import Movement
from measurement import Measurement
import wandb
import os
from sample import sample

class Movement_Dict:
    """A dictionary-like object to hold movement settings and positions."""
    def __init__(self, movement: Movement, settings: dict, positions: np.ndarray):
        self.movement = movement
        self.settings = settings
        self.positions = positions

class Measurement_Dict:
    """A dictionary-like object to hold measurement settings."""
    def __init__(self, measurement: Measurement, settings: dict):
        self.measurement = measurement
        self.settings = settings

class ScanSettings:
    """A class to hold scan settings, including movement and measurement dictionaries."""
    def __init__(self, scan_name: str, scan_type: str, job_type: str, measurement_dicts: list[Measurement_Dict], movement_dicts: list[Movement_Dict], additional_tags: list[str] = []):
        # S001, S002, etc.
        self.scan_name = scan_name

        # 1D Scan, Focus Scan, 2D Scan, etc.
        self.scan_type = scan_type

        # Raman, Photocurrent, Transport, AFM, etc.
        self.job_type = job_type

        # List of additional tags for the scan
        self.additional_tags = additional_tags

        # List of Measurement_Dict objects
        self.measurement_dicts = measurement_dicts

        # List of Movement_Dict objects
        self.movement_dicts = movement_dicts


class Scan(Procedure):
    """Base class for scans in the PyBirch framework."""
    # sample directory is under pybirch/samples
    def __init__(self, project_name: str, scan_settings: ScanSettings, owner: str, sample_ID: str, directory: str, sample_directory: str = os.path.join("samples"), **kwargs):
        super().__init__(name=scan_settings.scan_name, **kwargs)

        # rare earth tritellurides, trilayer twisted graphene, axial higgs, etc.
        self.project_name = project_name

        # scan settings
        self.scan_settings = scan_settings

        # owner of the scan, e.g. 'piyush_sakrikar'
        self.owner = owner

        # sample to be scanned
        self.sample = sample(sample_ID)
        self.sample.load_from_file(os.path.join(sample_directory, sample_ID))
        self.sample_directory = sample_directory

        # directory to save the scan data
        self.directory = directory
        self.file_name = os.path.join(directory, scan_settings.scan_name)


    def initialize(self):

        for item in self.scan_settings.movement_dicts:
            item.movement.connect()
            item.movement.initialize()
            item.movement.settings = item.settings


        for item in self.scan_settings.measurement_dicts:
            item.measurement.connect()
            item.measurement.initialize()
            item.measurement.settings = item.settings

        # Initialize wandb run, add tags and metadata
        wandb.login()
        wandb.init(project=self.project_name, 
                   group=self.sample.ID,
                   name=self.scan_settings.scan_name, 
                   job_type=self.scan_settings.job_type,
                   tags=[self.scan_settings.scan_type, str(self.sample.material), *self.sample.additional_tags, *self.scan_settings.additional_tags], 
                   config={
                        "scan_name": self.scan_settings.scan_name,
                        "scan_type": self.scan_settings.scan_type,
                        "job_type": self.scan_settings.job_type,
                        "sample_ID": self.sample.ID,
                        "owner": self.owner,
                        "sample_material": self.sample.material,
                        "sample": self.sample,
                        "measurement_tools": [m.measurement.name for m in self.scan_settings.measurement_dicts],
                        "movement_tools": [m.movement.name for m in self.scan_settings.movement_dicts],
                        "measurement_settings": {m.measurement.name: m.settings for m in self.scan_settings.measurement_dicts},
                        "movement_settings": {m.movement.name: m.settings for m in self.scan_settings.movement_dicts},
                        "implemented_measurement_settings": {m.measurement.name: m.settings for m in self.scan_settings.measurement_dicts},
                        "implemented_movement_settings": {m.movement.name: m.settings for m in self.scan_settings.movement_dicts},
                        "movement_positions": {m.movement.name: m.positions for m in self.scan_settings.movement_dicts},
                        "filepath": self.file_name
                })

        return

    def save_data(self, data: pd.DataFrame):
        # write to file_name
        if not os.path.exists(self.file_name):
            os.makedirs(self.file_name)
        data.to_csv(self.file_name, mode='a', header=not os.path.exists(self.file_name), index=False)

        # also save to wandb, row by row from dataframe
        for _, row in data.iterrows():
            wandb.log(row.to_dict())

    def move_to_positions(self, items_to_move):
        for movement_dict, position in items_to_move:
            movement_dict.movement.position = position

    def take_measurements(self):
        # Get the current position of each movement tool
        position_data: dict[str, pd.DataFrame] = {}
        for movement_tool in self.scan_settings.movement_dicts:
            position_data[movement_tool.movement.name] = movement_tool.movement.position

        # Perform measurements at the current position, add movement positions to each measurement, save as individual DataFrames
        for item in self.scan_settings.measurement_dicts:
            data = item.measurement.perform_measurement()

            # Add position dataframes
            for movement_tool in self.scan_settings.movement_dicts:
                position = position_data[movement_tool.movement.name]
                
                # position is a dataframe, concatenate it with the measurement data, copying the position to each row
                position_df = pd.DataFrame([position] * len(data), columns=movement_tool.settings['columns'])
                data = pd.concat([data, position_df], axis=1)

            # Save the data
            self.save_data(data)

    def execute(self, master_index: int = 0, indices: np.ndarray = np.array([])):
        # should move master index and indices to integerparameters in __init__


        # Perform the scan by iterating over all movement positions and performing measurements
        num_movement_tools = len(self.scan_settings.movement_dicts)

        # If indices is empty, initialize it to zeros for each movement tool, else we are resuming a scan
        if indices == np.array([]):
            indices = np.array([0 for _ in range(num_movement_tools)])
        positions = np.array([self.scan_settings.movement_dicts[i].positions for i in range(num_movement_tools)])
        total_positions = np.prod([len(pos) for pos in positions])

        # Initialize previous indices to NaN for each movement tool; all movement tools will be moved in the first iteration
        previous_indices = np.array([np.nan for _ in range(num_movement_tools)])

        while True:

            # create np mask for changed indices
            mask = indices != previous_indices
            previous_indices = indices.copy()

            # create array of (movement_dict, position) tuples for changed indices
            items_to_move = [(self.scan_settings.movement_dicts[i], positions[i][indices[i]]) for i in range(num_movement_tools) if mask[i]]

            self.move_to_positions(items_to_move)

            # Take measurements at the current position
            self.take_measurements()

            # Update index for next position
            master_index += 1
            if master_index >= total_positions:
                break

            # Update indices for each movement tool
            for i in range(num_movement_tools):
                indices[i] += 1
                if indices[i] >= len(positions[i]):
                    indices[i] = 0
                else:
                    break
    
        return