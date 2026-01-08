import sys
import random
from PySide6 import QtCore, QtWidgets, QtGui
import numpy as np
import pandas as pd
from typing import Callable

# Import theme
try:
    from GUI.theme import Theme
except ImportError:
    try:
        from theme import Theme
    except ImportError:
        Theme = None


class RangeWidget(QtWidgets.QWidget):
    """Widget for specifying a range of positions with start, stop, and number of steps."""
    
    def __init__(self, start: float = 0.0, stop: float = 0.0, n_step: int = 0):
        super().__init__()

        self.start: float = start
        self.stop: float = stop
        self.n_step: int = n_step
        self.valid_entry: bool = False
        self.enabled: bool = False
        self.validation_message: str = ""

        # create a three item QHBoxLayout with a radio button, a label, and three double spin boxes
        self.layouts = QtWidgets.QHBoxLayout(self)

        self.radio_button = QtWidgets.QRadioButton()
        self.label = QtWidgets.QLabel("Range")
        self.start_spin_box = QtWidgets.QDoubleSpinBox()
        self.stop_spin_box = QtWidgets.QDoubleSpinBox()
        self.n_step_spin_box = QtWidgets.QDoubleSpinBox()
        
        # Configure start and stop spin boxes for wide range of values
        self.start_spin_box.setDecimals(6)  # High precision
        self.start_spin_box.setMinimum(-1e9)  # Allow large negative values
        self.start_spin_box.setMaximum(1e9)   # Allow large positive values
        self.start_spin_box.setSingleStep(0.1)  # Reasonable step size
        
        self.stop_spin_box.setDecimals(6)  # High precision
        self.stop_spin_box.setMinimum(-1e9)  # Allow large negative values
        self.stop_spin_box.setMaximum(1e9)   # Allow large positive values
        self.stop_spin_box.setSingleStep(0.1)  # Reasonable step size
        
        # Configure n_step_spin_box for integer values
        self.n_step_spin_box.setDecimals(0)  # No decimal places
        self.n_step_spin_box.setMinimum(0)   # Allow 0 for validation
        self.n_step_spin_box.setMaximum(10000)  # Reasonable maximum
        self.caution_icon = QtWidgets.QLabel("⚠️")
        self.caution_icon.setVisible(False)
        self.caution_icon.setCursor(QtCore.Qt.CursorShape.WhatsThisCursor)

        self.layouts.addWidget(self.radio_button)
        self.layouts.addWidget(self.label)
        self.layouts.addWidget(self.start_spin_box)
        self.layouts.addWidget(self.stop_spin_box)
        self.layouts.addWidget(self.n_step_spin_box)
        self.layouts.addWidget(self.caution_icon)

        self.setLayout(self.layouts)

        self.start_spin_box.valueChanged.connect(self.update_start)
        self.stop_spin_box.valueChanged.connect(self.update_stop)
        self.n_step_spin_box.valueChanged.connect(self.update_step)
        self.radio_button.toggled.connect(self.set_enabled)
        
        # Initial validation check
        self.check_if_valid()



    def update_start(self, value: float):
        self.start = value
        self.check_if_valid()

    def update_stop(self, value: float):
        self.stop = value
        self.check_if_valid()

    def update_step(self, value):
        self.n_step = int(value)  # Ensure integer conversion
        self.check_if_valid()

    def check_if_valid(self):
        """Validate the range entry and update the caution icon with appropriate tooltip."""
        if self.start == self.stop:
            self.valid_entry = False
            self.validation_message = "Start and stop values cannot be equal"
        elif self.n_step <= 0:
            self.valid_entry = False
            self.validation_message = "Number of steps must be greater than 0"
        else:
            self.valid_entry = True
            self.validation_message = ""
        self.caution_icon.setToolTip(self.validation_message)
        self.caution_icon.setVisible(not self.valid_entry)

    def set_entry(self, entry: tuple[float, float, int]):
        if entry and len(entry) == 3:
            self.start, self.stop, self.n_step = entry
            # Update the spin boxes to reflect the loaded values
            self.start_spin_box.setValue(float(self.start))
            self.stop_spin_box.setValue(float(self.stop)) 
            self.n_step_spin_box.setValue(float(self.n_step))  # QDoubleSpinBox expects float
            self.check_if_valid()
            # Update caution icon visibility based on current enabled state
            if hasattr(self, 'enabled'):
                self.caution_icon.setVisible(self.enabled and not self.valid_entry)

    def get_entry(self) -> tuple[float, float, int]:
        return (self.start, self.stop, self.n_step)

    def get_positions(self) -> list[float]:
        print(f"[RangeWidget.get_positions] start={self.start}, stop={self.stop}, n_step={self.n_step}, valid_entry={self.valid_entry}")
        if not self.valid_entry:
            print(f"[RangeWidget.get_positions] -> returning [] (not valid)")
            return []
        positions = np.linspace(self.start, self.stop, self.n_step).tolist()
        print(f"[RangeWidget.get_positions] -> returning {len(positions)} positions")
        return positions

    def set_enabled(self, enabled: bool):
        self.start_spin_box.setEnabled(enabled)
        self.stop_spin_box.setEnabled(enabled)
        self.n_step_spin_box.setEnabled(enabled)
        self.caution_icon.setVisible(enabled and not self.valid_entry)
        self.enabled = enabled

class DiscreteWidget(QtWidgets.QWidget):
    """Widget for specifying discrete position values as comma-separated values."""
    
    def __init__(self, position_str: str = ""):
        super().__init__()

        self.position_str = position_str
        self.positions: list[float] = [float(x) for x in position_str.split(",") if x.strip().replace('.','',1).isdigit()]
        self.valid_entry: bool = False
        self.enabled: bool = False
        self.validation_message: str = ""

        # create a three item QHBoxLayout with a radio button, a label, and a line edit
        self.layouts = QtWidgets.QHBoxLayout(self)

        self.radio_button = QtWidgets.QRadioButton()
        self.label = QtWidgets.QLabel("Discrete (CSV)")
        self.line_edit = QtWidgets.QLineEdit()
        self.caution_icon = QtWidgets.QLabel("⚠️")
        self.caution_icon.setVisible(False)
        self.caution_icon.setCursor(QtCore.Qt.CursorShape.WhatsThisCursor)

        self.layouts.addWidget(self.radio_button)
        self.layouts.addWidget(self.label)
        self.layouts.addWidget(self.line_edit)
        self.layouts.addWidget(self.caution_icon)

        self.setLayout(self.layouts)

        self.line_edit.textChanged.connect(self.update_positions)
        self.radio_button.toggled.connect(self.set_enabled)

        self.line_edit.setEnabled(False)


    def update_positions(self, text: str):
        """Parse comma-separated values and validate."""
        try:
            # convert the text to a list of floats
            self.positions = [float(x) for x in text.strip().split(",")]
            self.valid_entry = True
            self.validation_message = ""
            self.caution_icon.setToolTip("")
            self.caution_icon.setVisible(False)
        except ValueError:
            self.valid_entry = False
            self.validation_message = "Invalid format: Enter comma-separated numbers (e.g., 1.0, 2.5, 3.0)"
            self.caution_icon.setToolTip(self.validation_message)
            self.caution_icon.setVisible(True)

    def set_positions(self, positions: list[float]):
        self.positions = positions
        # convert the list of floats to a comma separated string
        text = ", ".join([str(x) for x in positions])
        self.line_edit.setText(text)

    def get_positions(self) -> list[float]:
        return self.positions

    def set_enabled(self, enabled: bool):
        self.line_edit.setEnabled(enabled)
        self.caution_icon.setVisible(enabled and not self.valid_entry)
        self.enabled = enabled

    def set_entry(self, text: str):
        self.line_edit.setText(text)
    
    def get_entry(self) -> str:
        return self.line_edit.text()

class AdvancedWidget(QtWidgets.QWidget):
    """Widget for specifying positions using Python expressions (e.g., list comprehensions)."""
    
    def __init__(self, positions: list[float] = []):
        super().__init__()

        # allows user input of python code in a line edit to generate positions
        self.layouts = QtWidgets.QHBoxLayout(self)
        self.line_edit = QtWidgets.QLineEdit(self)
        self.radio_button = QtWidgets.QRadioButton()
        self.label = QtWidgets.QLabel("Advanced (Python)")
        self.caution_icon = QtWidgets.QLabel("⚠️")
        self.caution_icon.setVisible(False)
        self.caution_icon.setCursor(QtCore.Qt.CursorShape.WhatsThisCursor)
        self.valid_entry: bool = False
        self.enabled: bool = False
        self.validation_message: str = ""

        self.layouts.addWidget(self.radio_button)
        self.layouts.addWidget(self.label)
        self.layouts.addWidget(self.line_edit)
        self.layouts.addWidget(self.caution_icon)
        self.setLayout(self.layouts)
        self.positions = positions

        self.line_edit.textChanged.connect(self.update_positions)
        self.radio_button.toggled.connect(self.set_enabled)

        self.line_edit.setEnabled(False)

    def update_positions(self, text: str):
        """Evaluate Python expression and validate result is a list of numbers."""
        try:
            # evaluate the text as a python expression
            self.positions = eval(text)
            if isinstance(self.positions, (list, tuple)) and all(isinstance(x, (int, float)) for x in self.positions):
                self.valid_entry = True
                self.validation_message = ""
                self.caution_icon.setToolTip("")
                self.caution_icon.setVisible(False)
            else:
                self.valid_entry = False
                self.validation_message = "Expression must return a list of numbers"
                self.caution_icon.setToolTip(self.validation_message)
                self.caution_icon.setVisible(True)
                self.positions = []

        except Exception as e:
            self.valid_entry = False
            self.validation_message = f"Invalid Python expression: {str(e)}"
            self.caution_icon.setToolTip(self.validation_message)
            self.caution_icon.setVisible(True)

    def get_positions(self) -> list[float]:
        return self.positions

    def set_positions(self, positions: list[float]):
        self.positions = positions

    def set_entry(self, text: str):
        self.line_edit.setText(text)

    def get_entry(self) -> str:
        return self.line_edit.text()

    def set_enabled(self, enabled: bool):
        self.line_edit.setEnabled(enabled)
        self.caution_icon.setVisible(enabled and not self.valid_entry)
        self.enabled = enabled



class MovementPositionsSubwidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.layouts = QtWidgets.QVBoxLayout(self)

        self.advanced_widget = AdvancedWidget()
        self.discrete_widget = DiscreteWidget()
        self.range_widget = RangeWidget()

        self.layouts.addWidget(self.range_widget)
        self.layouts.addWidget(self.discrete_widget)
        self.layouts.addWidget(self.advanced_widget)
        

        # connect the radio buttons by putting them in a button group
        self.button_group = QtWidgets.QButtonGroup(self)
        self.button_group.addButton(self.advanced_widget.radio_button)
        self.button_group.addButton(self.discrete_widget.radio_button)
        self.button_group.addButton(self.range_widget.radio_button)

        self.setLayout(self.layouts)

    def get_positions(self) -> list[float]:
        advanced_checked = self.advanced_widget.radio_button.isChecked()
        discrete_checked = self.discrete_widget.radio_button.isChecked()
        range_checked = self.range_widget.radio_button.isChecked()
        print(f"[MovementPositionsSubwidget.get_positions] advanced={advanced_checked}, discrete={discrete_checked}, range={range_checked}")
        if advanced_checked:
            return self.advanced_widget.get_positions()
        elif discrete_checked:
            return self.discrete_widget.get_positions()
        elif range_checked:
            return self.range_widget.get_positions()
        print(f"[MovementPositionsSubwidget.get_positions] -> No radio button checked, returning []")
        return []
    
    def get_entries(self) -> dict:
        # Determine which radio button is currently selected
        selected_mode = None
        if self.advanced_widget.radio_button.isChecked():
            selected_mode = "advanced"
        elif self.discrete_widget.radio_button.isChecked():
            selected_mode = "discrete"
        elif self.range_widget.radio_button.isChecked():
            selected_mode = "range"
        
        return {
            "advanced": self.advanced_widget.get_entry(),
            "discrete": self.discrete_widget.get_entry(),
            "range": self.range_widget.get_entry(),
            "selected_mode": selected_mode  # Save which radio button is selected
        }
    
    def set_entries(self, entries: dict):
        # First, set all the entries without triggering radio button changes
        self.advanced_widget.set_entry(entries.get("advanced", ""))
        self.discrete_widget.set_entry(entries.get("discrete", ""))
        # Range expects a tuple/list of 3 values, not an empty string
        range_entry = entries.get("range", None)
        if range_entry:
            self.range_widget.set_entry(range_entry)
        
        # Then restore which radio button was selected
        selected_mode = entries.get("selected_mode", None)
        
        # Temporarily disconnect the button group to avoid conflicts
        self.button_group.setExclusive(False)
        
        # Clear all radio buttons first
        self.advanced_widget.radio_button.setChecked(False)
        self.discrete_widget.radio_button.setChecked(False)
        self.range_widget.radio_button.setChecked(False)
        
        # Set the correct radio button based on saved mode
        if selected_mode == "advanced":
            self.advanced_widget.radio_button.setChecked(True)
        elif selected_mode == "discrete":
            self.discrete_widget.radio_button.setChecked(True)
        elif selected_mode == "range":
            self.range_widget.radio_button.setChecked(True)
        else:
            # Default to range if no mode specified
            self.range_widget.radio_button.setChecked(True)
            
        # Re-enable exclusive mode for the button group
        self.button_group.setExclusive(True)

    def check_if_enabled(self):
        return self.advanced_widget.enabled or self.discrete_widget.enabled or self.range_widget.enabled

    def check_if_valid(self) -> bool:
        return (
            (self.advanced_widget.valid_entry and self.advanced_widget.enabled) or
            (self.discrete_widget.valid_entry and self.discrete_widget.enabled) or
            (self.range_widget.valid_entry and self.range_widget.enabled)
        )


class MovementPositionsTitleBar(QtWidgets.QFrame):
    def __init__(self, movement_name: str):
        super().__init__()
        self.movement_name = movement_name

        self.init_ui()

    def init_ui(self):
        self.layouts = QtWidgets.QHBoxLayout(self)

        self.collapse_arrow_button = QtWidgets.QPushButton("▼")
        self.collapse_arrow_button.setFixedWidth(35)
        self.collapse_arrow_button.setCheckable(True)
        # Set font to ensure arrow renders properly
        arrow_font = QtGui.QFont("Segoe UI Symbol", 12)
        self.collapse_arrow_button.setFont(arrow_font)
        if Theme:
            self.collapse_arrow_button.setStyleSheet(Theme.icon_button_style())

        self.layouts.addWidget(self.collapse_arrow_button)
        
        self.title_label = QtWidgets.QLabel(self.movement_name)
        self.layouts.addWidget(self.title_label)
        self.title_label.setAlignment(QtCore.Qt.AlignCenter) # type: ignore

        self.caution_icon = QtWidgets.QLabel("")
        self.caution_icon.setFixedWidth(35)
        self.layouts.addWidget(self.caution_icon)

        # Typing doesnt recognize qframe types. I don't know why. Ignoring this to remove the hated red squiggles
        self.setFrameStyle(QtWidgets.QFrame.StyledPanel | QtWidgets.QFrame.Raised) # type: ignore

        self.initial_size = self.sizeHint().height()

class MovementPositionsWidget(QtWidgets.QFrame):
    def __init__(self, movement_name: str):
        super().__init__()
        self.layouts = QtWidgets.QVBoxLayout(self)
        self.movement_name = movement_name
        self.small_subwidget = MovementPositionsSubwidget()
        self.title_bar = MovementPositionsTitleBar(self.movement_name)

        self.animation = QtCore.QPropertyAnimation(self.small_subwidget, b"maximumHeight")
        self.animation.setDuration(100) # Animation duration in ms

        self.title_bar.collapse_arrow_button.toggled.connect(self.toggle_content)

        self.layouts.addWidget(self.title_bar)
        self.layouts.addWidget(self.small_subwidget)

        self.setLayout(self.layouts)

        self.setFrameStyle(QtWidgets.QFrame.StyledPanel | QtWidgets.QFrame.Plain) # type: ignore

        self.small_subwidget.advanced_widget.radio_button.toggled.connect(self.update_caution_icon)
        self.small_subwidget.discrete_widget.radio_button.toggled.connect(self.update_caution_icon)
        self.small_subwidget.range_widget.radio_button.toggled.connect(self.update_caution_icon)

    def get_positions(self) -> list[float]:
        return self.small_subwidget.get_positions()

    def get_entries(self) -> dict:
        return self.small_subwidget.get_entries()

    def set_entries(self, entries: dict):
        self.small_subwidget.set_entries(entries)

    def toggle_content(self, checked):
        if not checked:
            # Expand
            self.title_bar.collapse_arrow_button.setText("▼")
            self.animation.setStartValue(0)
            self.animation.setEndValue(self.small_subwidget.sizeHint().height())
        else:
            # Collapse
            self.title_bar.collapse_arrow_button.setText("▲")
            self.animation.setStartValue(self.small_subwidget.height())
            self.animation.setEndValue(0)
        self.animation.start()
        self.title_bar.setFixedHeight(self.title_bar.sizeHint().height())
        self.update_caution_icon()

    def update_caution_icon(self):
        if self.title_bar.collapse_arrow_button.isChecked():
            self.title_bar.caution_icon.setText("" if self.small_subwidget.check_if_valid() else "⚠️")
        else:
            self.title_bar.caution_icon.setText("" if self.small_subwidget.check_if_enabled() else "⚠️")

# place in window to test

if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    widget = MovementPositionsWidget("Test Movement")
    widget.show()
    app.exec()