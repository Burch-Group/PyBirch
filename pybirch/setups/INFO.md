# PyBirch Setups

Setups folder contains instrument definitions for each experimental setup, along with their measurement and movement classes. The scan procedure will pull from these files automatically to give users an option of instruments to use.

## Creating New Instruments

PyBirch provides base classes that simplify creating new instruments. The key benefits:

- **Clear customization hooks** - Override `_connect_impl()`, `_initialize_impl()`, `_shutdown_impl()` with your proprietary commands
- **Flexible settings management** - Use automatic settings OR override the `settings` property for complex instruments
- **VISA and non-VISA support** - Choose the appropriate base class for your hardware
- **Simulated instruments** - Easy to create fake instruments for testing

### Architecture Overview

The base classes use a template pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│  Public Interface (used by scan system)                         │
│  • connect() → calls _connect_impl()                            │
│  • initialize() → calls _initialize_impl()                      │
│  • shutdown() → calls _shutdown_impl()                          │
│  • settings property → override OR use _define_settings()       │
│  • perform_measurement() → calls _perform_measurement_impl()    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  YOUR CODE (override these with proprietary commands)           │
│  • _connect_impl() - handshake, identification                  │
│  • _initialize_impl() - reset to known state                    │
│  • _shutdown_impl() - cleanup, safe state                       │
│  • _perform_measurement_impl() - actual measurement             │
│  • settings property (optional override)                        │
└─────────────────────────────────────────────────────────────────┘
```

### Example: Simple Fake Instrument (automatic settings)

```python
from pybirch.Instruments.base import FakeMeasurementInstrument
import numpy as np

class MySpectrometer(FakeMeasurementInstrument):
    def __init__(self, name="My Spectrometer"):
        super().__init__(name)
        
        # Define what data this instrument returns
        self.data_columns = np.array(["wavelength", "intensity"])
        self.data_units = np.array(["nm", "counts"])
        
        # Option A: Use automatic settings (creates self._integration_time, etc.)
        self._define_settings({
            "integration_time": 100.0,
            "averages": 1,
        })
    
    def _perform_measurement_impl(self) -> np.ndarray:
        wavelengths = np.linspace(400, 800, 100)
        intensities = np.random.random(100) * self._integration_time
        return np.column_stack([wavelengths, intensities])
```

### Example: Real VISA Instrument (custom settings)

```python
from pybirch.Instruments.base import VisaBaseMeasurementInstrument
import numpy as np

class SR830LockIn(VisaBaseMeasurementInstrument):
    """Stanford Research SR830 Lock-In Amplifier."""
    
    def __init__(self, name="SR830", adapter="GPIB::8"):
        super().__init__(name, adapter)
        self.data_columns = np.array(["X", "Y", "R", "Theta"])
        self.data_units = np.array(["V", "V", "V", "deg"])
    
    def _connect_impl(self) -> bool:
        # Proprietary connection handshake
        try:
            self.instrument.write("*CLS")
            idn = self.instrument.query("*IDN?")
            return "SR830" in idn
        except Exception:
            return False
    
    def _initialize_impl(self):
        # Proprietary initialization sequence
        self.instrument.write("REST")  # Reset to defaults
        self.instrument.write("ISRC 0")  # Input A
        self.instrument.write("SENS 22")  # 1V sensitivity
    
    def _shutdown_impl(self):
        # Return to local control
        self.instrument.write("LOCL 0")
    
    @property
    def settings(self) -> dict:
        # Option B: Custom settings - query instrument directly
        return {
            "sensitivity": int(self.instrument.query("SENS?")),
            "time_constant": int(self.instrument.query("OFLT?")),
            "input_source": int(self.instrument.query("ISRC?")),
            "harmonic": int(self.instrument.query("HARM?")),
        }
    
    @settings.setter
    def settings(self, settings: dict):
        # Custom settings - send proprietary commands
        if "sensitivity" in settings:
            self.instrument.write(f"SENS {settings['sensitivity']}")
        if "time_constant" in settings:
            self.instrument.write(f"OFLT {settings['time_constant']}")
        if "input_source" in settings:
            self.instrument.write(f"ISRC {settings['input_source']}")
        if "harmonic" in settings:
            self.instrument.write(f"HARM {settings['harmonic']}")
    
    def _perform_measurement_impl(self) -> np.ndarray:
        data = self.instrument.query("SNAP? 1,2,3,4")
        x, y, r, theta = map(float, data.split(","))
        return np.array([[x, y, r, theta]])
```

### Example: Real Movement Instrument

```python
from pybirch.Instruments.base import VisaBaseMovementInstrument

class ESP301Axis(VisaBaseMovementInstrument):
    """Newport ESP301 Motion Controller - Single Axis."""
    
    def __init__(self, name="ESP301 X", adapter="GPIB::1", axis=1):
        super().__init__(name, adapter)
        self.axis = axis
        self.position_units = "mm"
        self.position_column = f"axis{axis} position"
    
    def _connect_impl(self) -> bool:
        try:
            idn = self.instrument.query("*IDN?")
            return "ESP301" in idn
        except Exception:
            return False
    
    def _initialize_impl(self):
        # Home the axis
        self.instrument.write(f"{self.axis}OR")
        # Wait for motion to complete
        while self.instrument.query(f"{self.axis}MD?") != "1":
            time.sleep(0.1)
    
    @property
    def position(self) -> float:
        return float(self.instrument.query(f"{self.axis}TP"))
    
    @position.setter
    def position(self, value: float):
        self.instrument.write(f"{self.axis}PA{value}")
        # Wait for motion to complete
        while self.instrument.query(f"{self.axis}MD?") != "1":
            time.sleep(0.01)
    
    @property
    def settings(self) -> dict:
        return {
            "velocity": float(self.instrument.query(f"{self.axis}VA?")),
            "acceleration": float(self.instrument.query(f"{self.axis}AC?")),
        }
    
    @settings.setter
    def settings(self, settings: dict):
        if "velocity" in settings:
            self.instrument.write(f"{self.axis}VA{settings['velocity']}")
        if "acceleration" in settings:
            self.instrument.write(f"{self.axis}AC{settings['acceleration']}")
```

## Settings Management Options

### Option A: Automatic Settings (simple instruments)

Call `_define_settings()` in `__init__` for automatic handling:

```python
def __init__(self, name):
    super().__init__(name)
    self._define_settings({
        "gain": 1.0,
        "filter_enabled": True,
    })
    
# Automatic attributes created:
# self._gain = 1.0
# self._filter_enabled = True

# settings property automatically works:
# self.settings → {"gain": 1.0, "filter_enabled": True}
# self.settings = {"gain": 2.0} → self._gain = 2.0
```

### Option B: Custom Settings (complex instruments)

Override the `settings` property for proprietary commands:

```python
@property
def settings(self) -> dict:
    # Query instrument directly
    return {
        "gain": int(self.instrument.query("GAIN?")),
        "filter": self.instrument.query("FILT?") == "1",
    }

@settings.setter
def settings(self, settings: dict):
    # Send proprietary commands
    if "gain" in settings:
        self.instrument.write(f"GAIN {settings['gain']}")
    if "filter" in settings:
        self.instrument.write(f"FILT {'1' if settings['filter'] else '0'}")
```

## Folder Structure

Each setup folder (e.g., `fake_setup/`) contains instrument subfolders:

```
fake_setup/
├── lock_in_amplifier/
│   ├── lock_in_amplifier.py    # Instrument implementation
│   └── lock_in_amplifier_ui.py # Optional GUI panel
├── spectrometer/
│   └── spectrometer.py
└── stage_controller/
    └── stage_controller.py
```

## Methods to Override

### Measurement Instruments

| Method | Required | Description |
|--------|----------|-------------|
| `_perform_measurement_impl()` | **Yes** | Return measurement data as 2D numpy array |
| `_connect_impl()` | No | Connection/handshake protocol, return True/False |
| `_initialize_impl()` | No | Reset instrument to known state |
| `_shutdown_impl()` | No | Cleanup on shutdown |
| `settings` property | No | Override for custom get/set logic |

### Movement Instruments

| Property/Method | Required | Description |
|-----------------|----------|-------------|
| `position` (property) | **Yes** | Get/set current position |
| `_connect_impl()` | No | Connection/handshake protocol |
| `_initialize_impl()` | No | Home or reset position |
| `_shutdown_impl()` | No | Cleanup on shutdown |
| `settings` property | No | Override for custom get/set logic |