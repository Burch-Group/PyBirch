import numpy as np
import pandas as pd
import sys
import os
import time
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from pybirch.scan.movements import Movement, MovementItem
from pybirch.scan.measurements import Measurement, MeasurementItem
from pybirch.extensions.scan_extensions import ScanExtension
from GUI.widgets.scan_tree.treeitem import InstrumentTreeItem
from GUI.widgets.scan_tree.treemodel import ScanTreeModel
import wandb
import os
import pickle
from itertools import compress
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque
from threading import Lock, Event
from typing import List, Dict, Any, Optional, Tuple

class ScanSettings:
    """A class to hold scan settings, including movement and measurement dictionaries."""
    def __init__(self, project_name: str, scan_name: str, scan_type: str, job_type: str, ScanTree: ScanTreeModel, extensions: list[ScanExtension] = [], additional_tags: list[str] = [], status: str = "Queued", user_fields: dict | None = None):
        
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

        # Contains all necessary info to run the scan
        self.scan_tree = ScanTree

        self.start_date = ""

        self.end_date = ""

        # List of ScanExtension objects
        self.extensions = extensions

        self.status = status

        self.wandb_link: str = ""
        
        # User-defined fields (dictionary)
        self.user_fields: dict = user_fields if user_fields is not None else {}

    def serialize(self) -> dict:
        """Serialize the scan settings into a dictionary."""
        data = {
            "project_name": self.project_name,
            "scan_name": self.scan_name,
            "scan_type": self.scan_type,
            "job_type": self.job_type,
            "additional_tags": self.additional_tags,
            "scan_tree": self.scan_tree.serialize(),
            "status": self.status,
            "wandb_link": self.wandb_link,
            "user_fields": self.user_fields
        }
        return data


    def __getstate__(self):
        """Prepare state for pickling - serialize ScanTreeModel to dict."""
        state = self.__dict__.copy()
        # Serialize the scan_tree (ScanTreeModel) to a dictionary
        if hasattr(self, 'scan_tree') and self.scan_tree is not None:
            state['_scan_tree_data'] = self.scan_tree.serialize()
            del state['scan_tree']
        return state
    
    def __setstate__(self, state):
        """Restore state after unpickling - deserialize ScanTreeModel from dict."""
        # Restore scan_tree from serialized data
        scan_tree_data = state.pop('_scan_tree_data', None)
        self.__dict__.update(state)
        
        if scan_tree_data is not None:
            from GUI.widgets.scan_tree.treeitem import InstrumentTreeItem
            self.scan_tree = ScanTreeModel()
            # Restore root_item
            self.scan_tree.root_item = InstrumentTreeItem.deserialize(scan_tree_data.get("root_item", {}))
            # Restore state flags
            self.scan_tree.completed = scan_tree_data.get("completed", False)
            self.scan_tree.paused = scan_tree_data.get("paused", False)
            self.scan_tree.stopped = scan_tree_data.get("stopped", False)
            # Restore next_item if present
            next_item_data = scan_tree_data.get("next_item")
            if next_item_data:
                self.scan_tree.next_item = InstrumentTreeItem.deserialize(next_item_data)
        else:
            self.scan_tree = ScanTreeModel()

    def __repr__(self):
        return f"ScanSettings(project_name={self.project_name}, \nscan_name={self.scan_name}, \nscan_type={self.scan_type}, \njob_type={self.job_type})"
    def __str__(self):
        return self.__repr__()


class Scan():
    """Base class for scans in the PyBirch framework."""
    def __init__(self, scan_settings: ScanSettings, owner: str, master_index: int = 0, indices: np.ndarray = np.array([]), buffer_size: int = 1000, max_workers: int = 2):

        # scan settings
        self.scan_settings = scan_settings

        self.project_name = scan_settings.project_name

        self.extensions = scan_settings.extensions

        # e.g. 'piyush_sakrikar'
        self.owner = owner

        self.current_item = None
        
        # Tree state for GUI persistence (stores scan tree widget state)
        self.tree_state: list = []

        self._max_workers = 1000 # essentially no default limit
        self._buffer_size = buffer_size
        self._data_buffer: Dict[str, List[Dict]] = {}
        self._buffer_lock = Lock()
        self._stop_event = Event()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, 
                                          thread_name_prefix='save_worker_')
        self._pending_futures: deque = deque(maxlen=100)  # Keep last 100 futures for error checking
        
        # Initialize buffer for each measurement
        for item in self.scan_settings.scan_tree.get_measurement_items():
            self._data_buffer[item.unique_id()] = []

    def startup(self):

        # Initialize all scan extensions
        # Pass scan reference to extensions that support it (e.g., DatabaseExtension)
        for extension in self.extensions:
            if hasattr(extension, 'set_scan_reference'):
                extension.set_scan_reference(self)
            extension.startup()

        print(f"Starting up scan: {self.scan_settings.scan_name} owned by {self.owner}")

        self.scan_settings.start_date = time.strftime("%H:%M:%S", time.localtime())

        # Initialize wandb run, add tags and metadata (MOVE TO EXTENSIONS)
        wandb.login()
        tags = [self.scan_settings.scan_type, *self.scan_settings.additional_tags]
        tags = [tag for tag in tags if tag]  # Remove empty tags
        self.run = wandb.init(project=self.project_name, 
                   name=self.scan_settings.scan_name, 
                   job_type=self.scan_settings.job_type,
                   tags=tags, 
                   config={
                        "scan_name": self.scan_settings.scan_name,
                        "scan_type": self.scan_settings.scan_type,
                        "job_type": self.scan_settings.job_type,
                        "owner": self.owner,
                        "scan_settings": self.scan_settings.serialize()
                })
        
        # Create a wandb table for each measurement tool
        self.wandb_tables = {}
        for item in self.scan_settings.scan_tree.get_measurement_items():
            self.wandb_tables[item.unique_id()] = wandb.Table(columns=[*item.instrument_object.instrument.columns().tolist(), *[f"{m.instrument_object.instrument.position_column} M({m.instrument_object.instrument.position_units})" for m in self.scan_settings.scan_tree.get_movement_items()]], log_mode="INCREMENTAL")

    def save_data(self, data: pd.DataFrame, measurement_name: str):
        """Save data to the buffer for asynchronous processing.
        
        Args:
            data: DataFrame containing the measurement data
            measurement_name: Name of the measurement for which to save data
        """
        if measurement_name not in self._data_buffer:
            self._data_buffer[measurement_name] = []
            
        # Convert DataFrame rows to dicts and add to buffer
        rows = []
        for row in data.itertuples(index=False):
            row_dict = {col: val for col, val in zip(data.columns, row)}
            rows.append(row_dict)

        with self._buffer_lock:
            self._data_buffer[measurement_name].extend(rows)
            # Check if we've reached the buffer size and need to flush
            if len(self._data_buffer[measurement_name]) >= self._buffer_size:
                self._flush_buffer(measurement_name)
                
    def _flush_buffer(self, measurement_name: str):
        """Flush the data buffer for a specific measurement."""
        if not self._data_buffer[measurement_name]:
            return
            
        # Get the data and clear the buffer
        data_to_save = self._data_buffer[measurement_name].copy()
        self._data_buffer[measurement_name].clear()
            
        if not data_to_save:
            return
            
        # Submit the save task to the thread pool
        print(f"Flushing buffer for {measurement_name} with {len(data_to_save)} rows.")
        future = self._executor.submit(
            self._save_data_async,
            data_to_save,
            measurement_name
        )
        self._pending_futures.append(future)
        
    def _save_data_async(self, data: List[Dict], measurement_name: str):
        """Background task to save data to wandb and extensions."""
        try:
            # Log to wandb
            for row in data:
                self.run.log({measurement_name: row})
                
            # Add to wandb table
            table = self.wandb_tables[measurement_name]
            for row in data:
                table.add_data(*[row.get(col, None) for col in table.columns])
                
            # Save to extensions
            df = pd.DataFrame(data)
            for extension in self.extensions:
                extension.save_data(df, measurement_name)
                
        except Exception as e:
            print(f"Error saving data for {measurement_name}: {str(e)}")
            # Re-raise to be handled by the future
            raise
            
    def flush(self):
        """Flush all buffered data to disk and wait for completion."""
        # Flush all measurement buffers
        for measurement_name in list(self._data_buffer.keys()):
            with self._buffer_lock:
                self._flush_buffer(measurement_name)
            
        # Wait for all pending saves to complete
        for future in list(self._pending_futures):
            try:
                future.result(timeout=30)  # 30 second timeout per future
            except Exception as e:
                print(f"Error during save operation: {str(e)}")
                
    def __del__(self):
        """Ensure all data is saved when the scan is destroyed."""
        self.shutdown()

    def execute(self):
        """Execute the scan procedure using the FastForward traversal and move_next functionality."""
        print(f"Starting scan: {self.scan_settings.scan_name} owned by {self.owner}")
        root_item = self.scan_settings.scan_tree.root_item
        # Initialize all extensions
        for extension in self.extensions:
            extension.execute()

        current_item = self.current_item if self.current_item else root_item

        # Connect to all instruments in the scan tree
        print("Connecting to instruments...")
        connected_instruments = set()
        
        def connect_instrument(item):
            if hasattr(item, 'instrument_object') and item.instrument_object is not None:
                # Get the actual instrument object
                instr = item.instrument_object.instrument
                    
                # Only connect once per unique instrument
                if instr not in connected_instruments:
                    try:
                        if hasattr(instr, 'connect') and callable(instr.connect):
                            instr.connect()
                            print(f"Connected to {instr.name}" if hasattr(instr, 'name') else f"Connected to {instr.__class__.__name__}")
                            connected_instruments.add(instr)
                    except Exception as e:
                        print(f"Error connecting to instrument {instr}: {str(e)}")
                        raise

        def initialize_instrument_if_IMR_start(item):
            if hasattr(item, 'instrument_object') and item.instrument_object is not None:
                # Get the actual instrument object
                instr = item.instrument_object.instrument
                    
                # Initialize
                try:
                    if item._runtime_initialized and hasattr(instr, 'initialize') and callable(instr.initialize):
                        instr.initialize()
                        instr.settings = item._runtime_settings
                        print(f"Initialized {instr.name}" if hasattr(instr, 'name') else f"Initialized {instr.__class__.__name__}")
                except Exception as e:
                    print(f"Error initializing instrument {instr}: {str(e)}")
                    raise

        def save_settings(item):
            if hasattr(item, 'instrument_object') and item.instrument_object is not None:
                # Get the actual instrument object
                instr = item.instrument_object.instrument
                if item._runtime_initialized and hasattr(instr, 'settings') and callable(instr.settings):
                    item._runtime_settings = instr.settings

        # Traverse the tree and connect to all instruments, initializing instruments if starting in the middle of a scan
        def traverse_and_connect(item):
            connect_instrument(item)
            initialize_instrument_if_IMR_start(item)
            for child in getattr(item, 'child_items', []):
                traverse_and_connect(child)

        def traverse_and_save(item):
            save_settings(item)
            for child in getattr(item, 'child_items', []):
                traverse_and_save(child)

        
        # Start traversal from root item
        traverse_and_connect(root_item)
        print(f"Successfully connected to {len(connected_instruments)} instruments")
        print("All instruments connected. Starting scan...")

        first_iteration = True

        # Main scan loop
        while True:
            if hasattr(self, '_stop_event') and self._stop_event.is_set():
                print("Scan stopped by user")

                # save current position in scan, in case it is necessary to continue
                self.current_item = current_item

                # save current settings for instruments that have already been initialized
                traverse_and_save(root_item)
                break

            # Use FastForward to get the next item to process
            ff = InstrumentTreeItem.FastForward(current_item)
            ff = ff.new_item(current_item)

            while not ff.done and ff.current_item is not None:
                ff = ff.current_item.propagate(ff)
                if ff.done:
                    break

            # Process the stack of items in parallel
            if ff.stack:
                print(f"Processing items in parallel: {[item.unique_id() for item in ff.stack]}")
                
                with ThreadPoolExecutor(max_workers=min(len(ff.stack),self._max_workers)) as executor:
                    # Submit all move_next tasks
                    future_to_item = {
                        executor.submit(item.move_next): item 
                        for item in ff.stack
                    }
                    
                    # Process results as they complete
                    for future in as_completed(future_to_item):
                        item = future_to_item[future]
                        try:
                            result = future.result()
                            if isinstance(result, pd.DataFrame):
                                # This was a measurement
                                # Add movement positions to the result, including only the relevant, ancestral movements
                                for movement_item in self.scan_settings.scan_tree.get_movement_items():
                                    if movement_item.is_ancestor_of(item):
                                        movement_instr = movement_item.instrument_object.instrument
                                        position_col = f"{movement_instr.position_column} M({movement_instr.position_units})"
                                        result[position_col] = movement_instr.position

                                # Save the measurement data
                                self.save_data(result, item.unique_id())
                        except Exception as exc:
                            print(f"{item.unique_id()} generated an exception: {exc}")
                            # Optionally re-raise if you want the scan to stop on error
                            # raise

            # Check if we've completed all movements
            if all(item.finished() for item in self.scan_settings.scan_tree.get_all_instrument_items()):
                print("All movements completed")
                break

            # Get the next item to process
            if ff.final_item is None:
                break
            current_item = ff.final_item

        # Final flush of any remaining data
        self.flush()
        print("Scan ended successfully")

    
    def shutdown(self):
        for extension in self.extensions:
            extension.shutdown()

        # Shutdown all movement and measurement tools
        for item in self.scan_settings.scan_tree.get_all_instrument_items():
            if item.instrument_object is not None:
                try:
                    if hasattr(item.instrument_object.instrument, 'shutdown') and callable(item.instrument_object.instrument.shutdown):
                        item.instrument_object.instrument.shutdown()
                        print(f"Shutdown {item.instrument_object.instrument.name}" if hasattr(item.instrument_object.instrument, 'name') else f"Shutdown {item.instrument_object.instrument.__class__.__name__}")
                except Exception as e:
                    print(f"Error shutting down instrument {item.instrument_object.instrument}: {str(e)}")

        # Finish the wandb run
        wandb.finish()

        self.scan_settings.end_date = time.strftime("%H:%M:%S", time.localtime())

    def run_scan(self):
        self.startup()
        self.execute()
        self.shutdown()

    def __getstate__(self):
        """Prepare state for pickling - exclude unpicklable objects."""
        state = self.__dict__.copy()
        # Remove unpicklable threading objects
        state.pop('_executor', None)
        state.pop('_buffer_lock', None)
        state.pop('_stop_event', None)
        state.pop('_pending_futures', None)
        state.pop('run', None)  # wandb run object
        state.pop('wandb_tables', None)  # wandb tables
        return state
    
    def __setstate__(self, state):
        """Restore state after unpickling - recreate unpicklable objects."""
        self.__dict__.update(state)
        # Recreate threading objects
        self._buffer_lock = Lock()
        self._stop_event = Event()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='save_worker_')
        self._pending_futures = deque(maxlen=100)
        # Initialize empty wandb references (will be set on startup)
        self.run = None
        self.wandb_tables = {}

    def __repr__(self):
        return f"Scan(project_name={self.project_name}, scan_settings={self.scan_settings}, owner={self.owner})"
    def __str__(self):
        return self.__repr__()

def get_empty_scan() -> Scan:
    """Create an empty scan with default settings."""
    scan_settings = ScanSettings(
        project_name="default_project",
        scan_name="default_scan",
        scan_type="",
        job_type="",
        ScanTree=ScanTreeModel(),
        additional_tags=[],
        status="Queued"
    )
    return Scan(scan_settings=scan_settings, owner="")