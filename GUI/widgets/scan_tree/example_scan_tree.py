import numpy as np
from pathlib import Path
import sys

# Add the parent directory to the path to allow imports
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))

from GUI.widgets.scan_tree.treemodel import ScanTreeModel
from pybirch.scan.scan import Scan, ScanSettings
from pybirch.scan.movements import MovementItem
from pybirch.scan.measurements import MeasurementItem
from pybirch.GUI.widgets.scan_tree.treeitem import InstrumentTreeItem
from pybirch.setups.fake_setup.stage_controller.stage_controller import FakeXStage, FakeYStage
from pybirch.setups.fake_setup.spectrometer.spectrometer import SpectrometerMeasurement
from pybirch.setups.fake_setup.multimeter.multimeter import VoltageMeasurement

def create_example_scan():
    """Create and return a complete example scan with X/Y stages, spectrometer, and multimeter."""
    # Create movement instruments
    x_stage = FakeXStage("X Stage")
    y_stage = FakeYStage("Y Stage")
    
    # Create measurement instruments
    spectrometer = SpectrometerMeasurement("Spectrometer")
    multimeter = VoltageMeasurement("Multimeter")
    
    # Define scan parameters
    x_positions = np.linspace(0, 100, 101)  # 0 to 100mm in 1mm steps
    y_positions = np.linspace(0, 100, 101)  # 0 to 100mm in 1mm steps
    
    # Create movement items
    x_movement = MovementItem(
        movement=x_stage,
        positions=x_positions
    )
    
    y_movement = MovementItem(
        movement=y_stage,
        positions=y_positions
    )
    
    # Create measurement items
    spectrometer_measurement = MeasurementItem(
        measurement=spectrometer
    )
    
    multimeter_measurement = MeasurementItem(
        measurement=multimeter
    )
    
    # Create scan settings
    scan_settings = ScanSettings(
        project_name="example_project",
        scan_name="2D_spectral_scan",
        scan_type="2D Raster",
        ScanTree=setup_scan_tree(),
        job_type="Optical Characterization",
        additional_tags=["example", "2d_scan", "spectral"]
    )
    
    # Create the scan
    scan = Scan(
        scan_settings=scan_settings,
        owner="example_user",
        sample_ID="SAMPLE_001"
    )
    
    # Set up the scan tree
    
    
    return scan

def setup_scan_tree() -> ScanTreeModel:
    """Set up the scan tree structure for the example scan."""
    
    # Create movement instruments
    x_stage = FakeXStage("X Stage")
    y_stage = FakeYStage("Y Stage")
    
    # Create measurement instruments
    spectrometer = SpectrometerMeasurement("Spectrometer")
    multimeter = VoltageMeasurement("Multimeter")
    
    # Define scan parameters
    x_positions = np.linspace(0, 100, 101)  # 0 to 100mm in 1mm steps
    y_positions = np.linspace(0, 100, 101)  # 0 to 100mm in 1mm steps
    
    # Create movement items
    x_movement = MovementItem(
        movement=x_stage,
        positions=x_positions
    )
    
    y_movement = MovementItem(
        movement=y_stage,
        positions=y_positions
    )
    
    # Create measurement items
    spectrometer_measurement = MeasurementItem(
        measurement=spectrometer
    )
    
    multimeter_measurement = MeasurementItem(
        measurement=multimeter
    )

    # Create instrument tree items
    x_item = InstrumentTreeItem(
        parent=None,
        instrument_object=x_movement,
        item_indices=[0],
        final_indices=[100]
    )
    
    y_item = InstrumentTreeItem(
        parent=x_item,
        instrument_object=y_movement,
        item_indices=[0],
        final_indices=[100]
    )
    
    # Create measurement items as children of Y stage
    spec_item = InstrumentTreeItem(
        parent=y_item,
        instrument_object=spectrometer_measurement,
        item_indices=[0],
        final_indices=[0]
    )
    
    mult_item = InstrumentTreeItem(
        parent=y_item,
        instrument_object=multimeter_measurement,
        item_indices=[0],
        final_indices=[0]
    )
    
    # Set up the tree structure
    x_item.child_items = [y_item]
    y_item.child_items = [spec_item, mult_item]  # Both measurements are children of Y stage
    
    return ScanTreeModel(
        root_item=x_item
    )

def run_example_scan():
    """Create, set up, and run the example scan."""
    print("Creating example scan...")
    scan = create_example_scan()
    
    print("Starting scan...")
    try:
        scan.run_scan()
        print("Scan completed successfully!")
    except Exception as e:
        print(f"Error during scan: {str(e)}")
        raise

if __name__ == "__main__":
    run_example_scan()