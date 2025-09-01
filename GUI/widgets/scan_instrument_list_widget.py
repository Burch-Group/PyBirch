from cProfile import label
import sys
import random
from PySide6 import QtCore, QtWidgets, QtGui
import numpy as np
import pandas as pd
from typing import Callable
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from pybirch.scan.movements import Movement
from pybirch.scan.measurements import Measurement
from pybirch.scan.scan import ScanSettings
from pybirch.setups.fake_setup.lock_in_amplifier.lock_in_amplifier import LockInAmplifierMeasurement, FakeLockinAmplifier

class SettingsCogFrame(QtWidgets.QFrame):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        self.settings_button = QtWidgets.QPushButton()
        self.settings_button.setIcon(QtGui.QIcon.fromTheme("help-about"))
        self.settings_button.setToolTip("Settings")
        self.settings_button.setFixedSize(35, 35)
        layout.setContentsMargins(0, 0, 0, 2)
        layout.addWidget(self.settings_button)
        self.setLayout(layout)

class TrashFrame(QtWidgets.QFrame):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        self.trash_button = QtWidgets.QPushButton()
        self.trash_button.setIcon(QtGui.QIcon.fromTheme("edit-delete"))
        self.trash_button.setToolTip("Delete")
        self.trash_button.setFixedSize(35, 35)
        layout.setContentsMargins(0, 0, 0, 2)
        layout.addWidget(self.trash_button)
        self.setLayout(layout)

# measurement item widget
class MeasurementItemWidget(QtWidgets.QWidget):
    def __init__(self, measurement: Measurement):
        super().__init__()
        self.measurement = measurement
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        self.settings_cog = SettingsCogFrame()
        self.trash_frame = TrashFrame()

        # increase font size
        label = QtWidgets.QLabel(self.measurement.name)
        font = label.font()
        font.setPointSize(11)
        label.setFont(font)

        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(self.settings_cog)
        layout.addWidget(self.trash_frame)  

        self.setLayout(layout)
        self.settings: dict = {}
    
    def open_settings(self):
        if not self.settings_cog.isEnabled():
            return
        # disable settings button
        self.settings_cog.setDisabled(True)
        # open settings UI in separate thread
        QtCore.QThreadPool.globalInstance().start(self._open_settings)

    def _open_settings(self):
        settings = self.measurement.settings_UI()
        self.settings = settings
        # re-enable settings button
        self.settings_cog.setDisabled(False)

class MovementItemWidget(QtWidgets.QWidget):
    def __init__(self, movement: Movement):
        super().__init__()
        self.movement = movement
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        self.settings_cog = SettingsCogFrame()
        self.trash_frame = TrashFrame()

        label = QtWidgets.QLabel(self.movement.name)
        font = label.font()
        font.setPointSize(11)
        label.setFont(font)

        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(self.settings_cog)
        layout.addWidget(self.trash_frame)

        self.setLayout(layout)
        self.settings: dict = {}

        # set hover animation to change color to a slight gray
        self.setStyleSheet("QLabel::hover"
                            "{"
                            "background-color : lightgray;"
                            "}")

    def open_settings(self):
        if not self.settings_cog.isEnabled():
            return
        # disable settings button
        self.settings_cog.setDisabled(True)
        # open settings UI in separate thread
        QtCore.QThreadPool.globalInstance().start(self._open_settings)

    def _open_settings(self):
        settings = self.movement.settings_UI()
        self.settings = settings
        # re-enable settings button
        self.settings_cog.setDisabled(False)

class MovementTitleBar(QtWidgets.QFrame):
    def __init__(self):
        super().__init__()
        self.movement_items: list[MovementItemWidget] = []    
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        self.label = QtWidgets.QLabel("Movement")
        self.add_button = QtWidgets.QPushButton()
        self.add_button.setIcon(QtGui.QIcon.fromTheme("list-add"))
        self.add_button.setToolTip("Add Movement")
        self.add_button.setFixedSize(35, 35)

        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.add_button)
        self.setLayout(layout)

        self.setFrameStyle(QtWidgets.QFrame.StyledPanel | QtWidgets.QFrame.Raised) # type: ignore

    def add(self):
        pass

class MeasurementTitleBar(QtWidgets.QFrame):
    def __init__(self):
        super().__init__()
        self.measurement_items: list[MeasurementItemWidget] = []
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        self.label = QtWidgets.QLabel("Measurement")
        self.add_button = QtWidgets.QPushButton()
        self.add_button.setIcon(QtGui.QIcon.fromTheme("list-add"))
        self.add_button.setToolTip("Add Measurement")
        self.add_button.setFixedSize(35, 35)

        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.add_button)
        self.setLayout(layout)

        self.setFrameStyle(QtWidgets.QFrame.StyledPanel | QtWidgets.QFrame.Raised) # type: ignore

    def add(self):
        pass

# create in window to test
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(window)

    # create test movement and measurement items
    for i in range(5):
        measurement = LockInAmplifierMeasurement(f"Measurement {i}", FakeLockinAmplifier())
        layout.addWidget(MeasurementItemWidget(measurement))

    window.setLayout(layout)
    window.show()
    sys.exit(app.exec())