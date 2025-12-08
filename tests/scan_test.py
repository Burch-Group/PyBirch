import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from GUI.widgets.scan_tree.example_scan_tree import create_example_scan
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

# Generate scan
scan = create_example_scan()

if __name__ == "__main__":
    # Create a Scan object
    test_scan = scan
    # Run the scan
    test_scan.run_scan()

