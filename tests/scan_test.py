import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from pybirch.scan.measurements import Measurement
from pybirch.scan.movements import Movement
from pybirch.scan.scan import Scan, ScanSettings, MeasurementDict, MovementDict
from pymeasure.instruments import Instrument
from pymeasure.experiment import Results, Procedure, Worker
from pybirch.setups.fake_setup.multimeter import FakeMultimeter
from pybirch.setups.fake_setup.multimeter import VoltageMeterMeasurement
from pybirch.setups.fake_setup.multimeter import CurrentSourceMovement
from pybirch.setups.fake_setup.spectrometer import FakeSpectrometer, SpectrometerMeasurement
from pybirch.setups.fake_setup.stage_controller import FakeLinearStageController, FakeAxis, FakeXStage, FakeYStage, FakeZStage
from pybirch.setups.fake_setup.lock_in_amplifier import FakeLockinAmplifier, LockInAmplifierMeasurement
from pybirch.scan.samples import Sample
import pickle
import wandb


import numpy as np
import pandas as pd
import time

# User fabricates a sample
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
wandb.login(key="cf01e3ff29ae47c8fe9b4ea58b9d1c8da2b2dbc3")  # Replace with your actual WandB API key

# User connects to instruments
multimeter = FakeMultimeter()
spectrometer = FakeSpectrometer()
ametek_lockin_amplifier = FakeLockinAmplifier(name="Lock-in Amplifier", wait=0.1)
daylight_spectrometer = FakeSpectrometer(name="Daylight Spectrometer", wait=0.1)
newport_stage_controller = FakeLinearStageController(name="Newport Stage Controller", wait=0.1)

# User selects measurements and movements
voltage_meter = VoltageMeterMeasurement("Voltage Meter", multimeter)
current_source = CurrentSourceMovement("Current Source", multimeter)
x_stage = FakeXStage("X Stage", newport_stage_controller)
y_stage = FakeYStage("Y Stage", newport_stage_controller)
z_stage = FakeZStage("Z Stage", newport_stage_controller)
lock_in_measurement = LockInAmplifierMeasurement("Lock-in Measurement", ametek_lockin_amplifier)
spectrum_measurement = SpectrometerMeasurement("Spectrum Measurement", daylight_spectrometer)

# MeasurementDicts are created for each measurement
measurements = [voltage_meter, spectrum_measurement, lock_in_measurement]
measurement_dicts = []
for measurement in measurements:
    item = MeasurementDict(measurement, measurement.settings)
    measurement_dicts.append(item)


# MovementDicts are created for each movement

x_positions = np.linspace(0, 99, 2)
y_positions = np.linspace(0, 70, 3)
z_positions = np.linspace(0, 50, 2)
current_source_positions = np.linspace(-0.005, 0.005, 2)

movements = [(x_stage, x_positions),
             (y_stage, y_positions),
             (z_stage, z_positions),
             (current_source, current_source_positions)]

movement_dicts = []


for movement, positions in movements:
    item = MovementDict(movement, movement.settings, positions)
    movement_dicts.append(item)


test_scan_settings = ScanSettings(
    project_name="test_RTe3",
    job_type="photocurrent",
    scan_type="5D Scan_XYZVA",
    scan_name="Test Scan",
    measurement_dicts=measurement_dicts,
    movement_dicts=movement_dicts,
)

if __name__ == "__main__":
    # Create a Scan object
    test_scan = Scan(test_scan_settings, owner='piyush_sakrikar', sample_ID="S001", sample_directory=sample_directory)

    print(f"Scan settings: {test_scan.scan_settings}")

    # Start the scan
    test_scan.startup()
    test_scan.execute()
    test_scan.shutdown()

    

