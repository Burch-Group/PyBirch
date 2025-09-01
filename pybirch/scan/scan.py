import numpy as np
import pandas as pd
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from pybirch.scan.movements import Movement, MovementItem
from pybirch.scan.measurements import Measurement, MeasurementItem
from pybirch.extensions.scan_extensions import ScanExtension
import wandb
import os
from pybirch.queue.samples import Sample
import pickle
from itertools import compress

class ScanSettings:
    """A class to hold scan settings, including movement and measurement dictionaries."""
    def __init__(self, project_name: str, scan_name: str, scan_type: str, job_type: str, measurement_items: list[MeasurementItem], movement_items: list[MovementItem], extensions: list[ScanExtension] = [], additional_tags: list[str] = [], completed: bool = False):
        
        # Name of the project, e.g. 'rare_earth_tritellurides', 'trilayer_twisted_graphene', etc.
        self.project_name = project_name
        
        # test1234, etc. 
        self.scan_name = scan_name

        # 1D Scan, Focus Scan, 2D Scan, etc.
        self.scan_type = scan_type

        # Raman, Photocurrent, Transport, AFM, etc.
        self.job_type = job_type

        # List of additional tags for the scan
        self.additional_tags = additional_tags

        # List of Measurement_Dict objects
        self.measurement_items = measurement_items

        # List of Movement_Dict objects
        self.movement_items = movement_items

        # List of ScanExtension objects
        self.extensions = extensions

        self.completed = completed

        self.wandb_link: str = ""

    def __repr__(self):
        return f"ScanSettings(project_name={self.project_name}, \nscan_name={self.scan_name}, \nscan_type={self.scan_type}, \njob_type={self.job_type}, \nmeasurement_items={self.measurement_items}, \nmovement_items={self.movement_items})"
    def __str__(self):
        return self.__repr__()


class Scan():
    """Base class for scans in the PyBirch framework."""
    # sample directory is under pybirch/samples
    def __init__(self, scan_settings: ScanSettings, owner: str, sample_ID: str, sample_directory: str = os.path.join(os.path.dirname(__file__), '..', "samples"), master_index: int = 0, indices: np.ndarray = np.array([])):

        # scan settings
        self.scan_settings = scan_settings

        self.project_name = scan_settings.project_name

        self.extensions = scan_settings.extensions

        # e.g. 'piyush_sakrikar'
        self.owner = owner

        self.master_index = master_index

        # indices for each movement tool, initialized to 0
        if indices.size == 0:
            self.indices = np.zeros(len(scan_settings.movement_items), dtype=int)
        else:
            self.indices = indices

        # e.g. 'S001', 'S002', etc. format is, of yet, unknown
        self.sample_ID = sample_ID
        self.sample_directory = sample_directory


    def startup(self):

        # Initialize all scan extensions
        for extension in self.extensions:
            extension.startup()

        print(f"Starting up scan: {self.scan_settings.scan_name} for sample {self.sample_ID} owned by {self.owner}")
        print(f"Sample directory: {self.sample_directory}")

        sample_file = os.path.join(self.sample_directory, self.sample_ID + ".pkl")
        with open(sample_file, 'rb') as file:
            try:
                self.sample = pickle.load(file)
            except EOFError:
                print(f"Sample file {sample_file} is empty. Creating a new sample.")
                self.sample = Sample(ID=self.sample_ID, material='', additional_tags=[], image=np.array([]))
        
        print(f"Loaded sample: {self.sample}")
        print(f"Sample material: {self.sample.material}")
        print(f"Sample additional tags: {self.sample.additional_tags}")
        
        # Initialize all movement objects
        for item in self.scan_settings.movement_items:
            item.movement.connect()
            item.movement.initialize()
            item.movement.settings = item.settings

        # Initialize all measurement objects
        for item in self.scan_settings.measurement_items:
            item.measurement.connect()
            item.measurement.initialize()
            item.measurement.settings = item.settings

        # Initialize wandb run, add tags and metadata (MOVE TO EXTENSIONS)
        wandb.login()
        tags = [self.scan_settings.scan_type, str(self.sample.material), *self.sample.additional_tags, *self.scan_settings.additional_tags]
        tags = [tag for tag in tags if tag]  # Remove empty tags. Lovely unintelligible pythonic syntax is an added bonus
        self.run = wandb.init(project=self.project_name, 
                   group=self.sample.ID,
                   name=self.scan_settings.scan_name, 
                   job_type=self.scan_settings.job_type,
                   tags=tags, 
                   config={
                        "scan_name": self.scan_settings.scan_name,
                        "scan_type": self.scan_settings.scan_type,
                        "job_type": self.scan_settings.job_type,
                        "sample_ID": self.sample.ID,
                        "owner": self.owner,
                        "sample_material": self.sample.material,
                        "sample": self.sample,
                        "measurement_tools": [m.measurement.name for m in self.scan_settings.measurement_items],
                        "movement_tools": [m.movement.name for m in self.scan_settings.movement_items],
                        "measurement_settings": {m.measurement.name: m.settings for m in self.scan_settings.measurement_items},
                        "movement_settings": {m.movement.name: m.settings for m in self.scan_settings.movement_items},
                        "implemented_measurement_settings": {m.measurement.name: m.settings for m in self.scan_settings.measurement_items},
                        "implemented_movement_settings": {m.movement.name: m.settings for m in self.scan_settings.movement_items},
                        "movement_positions": {m.movement.name: m.positions for m in self.scan_settings.movement_items}
                })
        
        # Create a wandb table for each measurement tool
        self.wandb_tables = {}
        for item in self.scan_settings.measurement_items:
            self.wandb_tables[item.measurement.name] = wandb.Table(columns=[*item.measurement.columns().tolist(), *[f"{m.movement.position_column} M({m.movement.position_units})" for m in self.scan_settings.movement_items]], log_mode="INCREMENTAL")
    
    def save_data(self, data: pd.DataFrame, measurement_name: str):
        # self.emit(f'data_{self.sample_ID}_{measurement_name}',data)
        # Save the data to a pandas DataFrame and log it to wandb
        # log message
        print(f"Saving data for {measurement_name} at indices {self.indices} with shape {data.shape}")
        print(f"Real Positions: ({') ('.join([f'{m.movement.position_column}: {m.positions[self.indices[i]]}' for i, m in enumerate(self.scan_settings.movement_items)])})\n")
        
        for extension in self.extensions:
            extension.save_data(data, measurement_name)
        
        for row in data.itertuples(index=False):
            # convert to dict
            row_data = list(row)

            row_dict = {col: val for col, val in zip(data.columns, row_data)}
            # log data to wandb
            self.run.log({measurement_name: row_dict})
            
            self.wandb_tables[measurement_name].add_data(*row_data)

    def move_to_positions(self, items_to_move: list[tuple[MovementItem, float]]):
        for extension in self.extensions:
            extension.move_to_positions(items_to_move)

        for movement_item, position in items_to_move:
            movement_item.movement.position = position

    def take_measurements(self):
        for extension in self.extensions:
            extension.take_measurements()
        
        # Get the current position of each movement tool
        position_data: dict[str, float] = {}
        for movement_tool in self.scan_settings.movement_items:
            position_data[movement_tool.movement.name] = movement_tool.movement.position

        # Perform measurements at the current position, add movement positions to each measurement, save as individual DataFrames
        for item in self.scan_settings.measurement_items:
            data = item.measurement.measurement_df()

            # Add position
            for movement_tool in self.scan_settings.movement_items:
                position = position_data[movement_tool.movement.name]
                data[f"{movement_tool.movement.position_column} M({movement_tool.movement.position_units})"] = pd.Series([position] * data.shape[0], index=data.index)

            # Save the data
            self.save_data(data, item.measurement.name)

        
    def execute(self):
        """Execute the scan procedure."""

        print(f"Starting scan: {self.scan_settings.scan_name} for sample {self.sample_ID} owned by {self.owner}")

        # Perform the scan by iterating over all movement positions and performing measurements
        num_movement_tools = len(self.scan_settings.movement_items)

        positions = [self.scan_settings.movement_items[i].positions for i in range(num_movement_tools)]
        total_positions = np.prod([len(pos) for pos in positions])

        # Initialize previous indices to NaN for each movement tool; all movement tools will be moved in the first iteration
        previous_indices = np.array([np.nan for _ in range(num_movement_tools)])

        for extension in self.extensions:
            extension.execute()

        while True:

            # create np mask for changed indices
            mask = self.indices != previous_indices
            mask = mask.tolist()
            previous_indices = self.indices.copy()

            # create array of (movement_dict, position) tuples for changed indices
            items_to_move = [(self.scan_settings.movement_items[i], float(positions[i][self.indices[i]])) for i in range(num_movement_tools)]
            items_to_move = list(compress(items_to_move, mask))
            self.move_to_positions(items_to_move)

            # Take measurements at the current position
            self.take_measurements()

            # Update index for next position
            self.master_index += 1
            if self.master_index >= total_positions:
                break

            # Update indices for each movement tool
            for i in range(num_movement_tools):
                self.indices[i] += 1
                if self.indices[i] >= len(positions[i]):
                    self.indices[i] = 0
                else:
                    break
        
        # Log the table to wandb
        for measurement_name in self.wandb_tables:
            self.run.log({measurement_name: self.wandb_tables[measurement_name]})

    
    def shutdown(self):
        for extension in self.extensions:
            extension.shutdown()


        # Shutdown all movement and measurement tools
        for item in self.scan_settings.movement_items:
            item.movement.shutdown()

        for item in self.scan_settings.measurement_items:
            item.measurement.shutdown()

        # Finish the wandb run
        wandb.finish()

    def run_scan(self):
        self.startup()
        self.execute()
        self.shutdown()

    def __repr__(self):
        return f"Scan(project_name={self.project_name}, scan_settings={self.scan_settings}, owner={self.owner}, sample_ID={self.sample.ID})"
    def __str__(self):
        return self.__repr__()
    
    def __getstate__(self):
        # Return a dictionary of the object's state, excluding wandb and sample
        state = self.__dict__.copy()
        del state['sample']
        return state
    
    def __setstate__(self, state):
        self.__dict__.update(state)

        # Reinitialize wandb and sample
        wandb.init(project=self.project_name,
                   config=self.scan_settings.__dict__,
                   group=self.sample.ID,
                   name=self.scan_settings.scan_name,
                   job_type=self.scan_settings.job_type,
                   tags=[self.scan_settings.scan_type, str(self.sample.material), *self.sample.additional_tags, *self.scan_settings.additional_tags],
                   )
        self.sample = Sample(self.sample.ID)
        self.sample = pickle.load(open(os.path.join(self.sample_directory, self.sample.ID + ".pkl"), 'rb'))

