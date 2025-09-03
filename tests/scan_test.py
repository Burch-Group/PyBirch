import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from pybirch.scan.scan import Scan, ScanSettings, MeasurementItem, MovementItem
from pybirch.setups.fake_setup.multimeter.multimeter import FakeMultimeter, CurrentSourceMovement, VoltageMeterMeasurement
from pybirch.setups.fake_setup.spectrometer.spectrometer import FakeSpectrometer, SpectrometerMeasurement
from pybirch.setups.fake_setup.stage_controller.stage_controller import FakeLinearStageController, FakeXStage, FakeYStage, FakeZStage
from pybirch.setups.fake_setup.lock_in_amplifier.lock_in_amplifier import FakeLockinAmplifier, LockInAmplifierMeasurement
from pybirch.queue.samples import Sample
import pickle
import wandb

import numpy as np
import pandas as pd
import time

# User fabricates a sample for measurement
sample = Sample(ID="S001")
sample.get_properties()
print(f"Sample properties: {sample.additional_tags}")
print(f"Sample material: {sample.material}")
sample.image = np.random.rand(10, 10)  # Simulated image data


# Sample is saved to a file
sample_directory = os.path.join(os.path.dirname(__file__), '..', "samples")
if not os.path.exists(sample_directory):
    os.makedirs(sample_directory)
sample_file = os.path.join(sample_directory, sample.ID + ".pkl")
with open(sample_file, 'wb') as f:
    pickle.dump(sample, f)


# user logs into wandb
wandb.login()  # For first time users, this will prompt for an API key (hopefully)

# User connects to instruments
multimeter = FakeMultimeter()
spectrometer = FakeSpectrometer()
ametek_lockin_amplifier = FakeLockinAmplifier(name="Lock-in Amplifier", wait=0)
daylight_spectrometer = FakeSpectrometer(name="Daylight Spectrometer", wait=0)
newport_stage_controller = FakeLinearStageController(name="Newport Stage Controller", wait=0)

# User selects measurements and movement objects
voltage_meter = VoltageMeterMeasurement("Voltage Meter", multimeter)
current_source = CurrentSourceMovement("Current Source", multimeter)
x_stage = FakeXStage("X Stage", newport_stage_controller)
y_stage = FakeYStage("Y Stage", newport_stage_controller)
z_stage = FakeZStage("Z Stage", newport_stage_controller)
lock_in_measurement = LockInAmplifierMeasurement("Lock-in Measurement", ametek_lockin_amplifier)
spectrum_measurement = SpectrometerMeasurement("Spectrum Measurement", daylight_spectrometer)

# MeasurementItems are created for each measurement object
measurements = [lock_in_measurement]
measurement_items = []
for measurement in measurements:
    item = MeasurementItem(measurement, measurement.settings)
    measurement_items.append(item)


# Movement settings are defined
x_positions = np.linspace(0, 99, 100)
y_positions = np.linspace(0, 70, 100)
z_positions = np.linspace(0, 50, 2)
current_source_positions = np.linspace(-0.005, 0.005, 2)

fourD_scan_movements = [(x_stage, x_positions),
             (y_stage, y_positions)]

# MovementItems are created for each movement object
movement_items = [MovementItem(movement, movement.settings, positions) for movement, positions in fourD_scan_movements]


test_scan_settings = ScanSettings(
    project_name="test_RTe3",
    job_type="photocurrent",
    scan_type="2D Scan_XY",
    scan_name="Longitudinal",
    measurement_items=measurement_items,
    movement_items=movement_items,
)

if __name__ == "__main__":
    # Create a Scan object
    test_scan = Scan(test_scan_settings, owner='piyush_sakrikar', sample_ID="S001", sample_directory=sample_directory)

    print(f"Scan settings: {test_scan.scan_settings}")

    # Run the scan
    test_scan.run_scan()

