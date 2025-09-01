import sys
import random
from PySide6 import QtCore, QtWidgets, QtGui
import numpy as np
import pandas as pd
from typing import Callable


class RangeWidget(QtWidgets.QWidget):
    def __init__(self, start: float = 0.0, stop: float = 0.0, n_step: int = 0):
        super().__init__()

        self.start: float = start
        self.stop: float = stop
        self.n_step: int = n_step
        self.valid_entry: bool = False
        self.enabled: bool = False

        # create a three item QHBoxLayout with a radio button, a label, and three double spin boxes
        self.layouts = QtWidgets.QHBoxLayout(self)

        self.radio_button = QtWidgets.QRadioButton()
        self.label = QtWidgets.QLabel("Range")
        self.start_spin_box = QtWidgets.QDoubleSpinBox()
        self.stop_spin_box = QtWidgets.QDoubleSpinBox()
        self.n_step_spin_box = QtWidgets.QDoubleSpinBox()
        self.caution_icon = QtWidgets.QLabel("⚠️")
        self.caution_icon.setVisible(False)

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



    def update_start(self, value: float):
        self.start = value
        self.check_if_valid()

    def update_stop(self, value: float):
        self.stop = value
        self.check_if_valid()

    def update_step(self, value: int):
        self.n_step = value
        self.check_if_valid()

    def check_if_valid(self):
        if self.start == self.stop:
            self.valid_entry = False
        elif self.n_step <= 0:
            self.valid_entry = False
        else:
            self.valid_entry = True
        self.caution_icon.setVisible(not self.valid_entry)

    def set_entry(self, entry: tuple[float, float, int]):
        self.start, self.stop, self.n_step = entry

    def get_entry(self) -> tuple[float, float, int]:
        return (self.start, self.stop, self.n_step)

    def get_positions(self) -> list[float]:
        if not self.valid_entry:
            return []
        return np.linspace(self.start, self.stop, self.n_step).tolist()

    def set_enabled(self, enabled: bool):
        self.start_spin_box.setEnabled(enabled)
        self.stop_spin_box.setEnabled(enabled)
        self.n_step_spin_box.setEnabled(enabled)
        self.caution_icon.setVisible(enabled and not self.valid_entry)
        self.enabled = enabled

class DiscreteWidget(QtWidgets.QWidget):
    def __init__(self, position_str: str = ""):
        super().__init__()

        self.position_str = position_str
        self.positions: list[float] = [float(x) for x in position_str.split(",") if x.strip().replace('.','',1).isdigit()]
        self.valid_entry: bool = False
        self.enabled: bool = False

        # create a three item QHBoxLayout with a radio button, a label, and a line edit
        self.layouts = QtWidgets.QHBoxLayout(self)

        self.radio_button = QtWidgets.QRadioButton()
        self.label = QtWidgets.QLabel("Discrete (CSV)")
        self.line_edit = QtWidgets.QLineEdit()
        self.caution_icon = QtWidgets.QLabel("⚠️")
        self.caution_icon.setVisible(False)

        self.layouts.addWidget(self.radio_button)
        self.layouts.addWidget(self.label)
        self.layouts.addWidget(self.line_edit)
        self.layouts.addWidget(self.caution_icon)

        self.setLayout(self.layouts)

        self.line_edit.textChanged.connect(self.update_positions)
        self.radio_button.toggled.connect(self.set_enabled)

        self.line_edit.setEnabled(False)


    def update_positions(self, text: str):
        try:
            # convert the text to a list of floats
            self.positions = [float(x) for x in text.strip().split(",")]
            self.valid_entry = True
            self.caution_icon.setVisible(False)
        except ValueError:
            self.valid_entry = False
            self.caution_icon.setVisible(True)
            pass

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
    def __init__(self, positions: list[float] = []):
        super().__init__()

        # allows user input of python code in a line edit to generate positions
        self.layouts = QtWidgets.QHBoxLayout(self)
        self.line_edit = QtWidgets.QLineEdit(self)
        self.radio_button = QtWidgets.QRadioButton()
        self.label = QtWidgets.QLabel("Advanced (Python)")
        self.caution_icon = QtWidgets.QLabel("⚠️")
        self.caution_icon.setVisible(False)
        self.valid_entry: bool = False
        self.enabled: bool = False

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
        try:
            # evaluate the text as a python expression
            self.positions = eval(text)
            if isinstance(self.positions, (list, tuple)) and all(isinstance(x, (int, float)) for x in self.positions):
                self.valid_entry = True
                self.caution_icon.setVisible(False)
            else:
                self.valid_entry = False
                self.caution_icon.setVisible(True)
                self.positions = []

        except Exception:
            self.valid_entry = False
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
        if self.advanced_widget.radio_button.isChecked():
            return self.advanced_widget.get_positions()
        elif self.discrete_widget.radio_button.isChecked():
            return self.discrete_widget.get_positions()
        elif self.range_widget.radio_button.isChecked():
            return self.range_widget.get_positions()
        return []
    
    def get_entries(self) -> dict:
        return {
            "advanced": self.advanced_widget.get_entry(),
            "discrete": self.discrete_widget.get_entry(),
            "range": self.range_widget.get_entry()
        }
    
    def set_entries(self, entries: dict):
        self.advanced_widget.set_entry(entries.get("advanced", ""))
        self.discrete_widget.set_entry(entries.get("discrete", ""))
        self.range_widget.set_entry(entries.get("range", ""))

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