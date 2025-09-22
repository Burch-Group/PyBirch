import sys
from PySide6 import QtCore, QtWidgets, QtGui
import numpy as np
import pandas as pd
from typing import Callable
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from pybirch.scan.movements import Movement
from pybirch.scan.measurements import Measurement
from pybirch.setups.fake_setup.lock_in_amplifier.lock_in_amplifier import LockInAmplifierMeasurement, FakeLockinAmplifier
from pybirch.setups.fake_setup.multimeter.multimeter import VoltageMeterMeasurement, FakeMultimeter, CurrentSourceMovement

class SettingsCogFrame(QtWidgets.QFrame):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        self.settings_button = QtWidgets.QPushButton()
        self.settings_button.setIcon(QtGui.QIcon.fromTheme("document-properties"))
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
        self.setFixedHeight(55)

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
        self.setFixedHeight(55)

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


class MeasurementFrame(QtWidgets.QFrame):
    def __init__(self, available_measurements: list[Measurement]):
        super().__init__()
        self.available_measurements = available_measurements
        self.measurement_items: list[MeasurementItemWidget] = []
        self.init_ui()

    def init_ui(self):
        self.layouts = QtWidgets.QVBoxLayout(self)
        self.title_bar = TitleBar("Measurement")
        self.layouts.addWidget(self.title_bar)
        self.layouts.addStretch()
        self.setLayout(self.layouts)
        self.title_bar.add_button.clicked.connect(self.measurement_selection)

    def add_measurement_item(self, measurement: Measurement):
        new_item = MeasurementItemWidget(measurement)
        self.measurement_items.append(new_item)
        # remove stretch from layout
        self.layouts.removeItem(self.layouts.itemAt(self.layouts.count() - 1))
        # add widget to layout
        self.layouts.addWidget(self.measurement_items[-1])
        self.measurement_items[-1].trash_frame.trash_button.clicked.connect(lambda: self.remove_measurement_item(new_item))
        self.layouts.addStretch()

    def remove_measurement_item(self, item: MeasurementItemWidget):
        if item in self.measurement_items:
            self.measurement_items.remove(item)
            item.setParent(None)
            item.deleteLater()

    def measurement_selection(self):
        # Create a simple popdown menu of available measurements for the user to select from
        menu = QtWidgets.QMenu(self)
        for measurement in self.available_measurements:
            action = menu.addAction(measurement.name)
            action.triggered.connect(lambda checked, m=measurement: self.add_measurement_item(m))
        menu.exec(QtGui.QCursor.pos())
    
    def clear_measurements(self):
        for item in self.measurement_items:
            item.setParent(None)
            item.deleteLater()
        self.measurement_items = []
        # remove all widgets from layout except title bar
        while self.layouts.count() > 1:
            item = self.layouts.takeAt(1)
            if item.widget():
                item.widget().setParent(None)
        self.layouts.addStretch()
    
    def full_refresh(self, new_measurements: list[Measurement]):
        self.clear_measurements()
        for measurement in new_measurements:
            self.add_measurement_item(measurement)


class TitleBar(QtWidgets.QFrame):
    def __init__(self, name: str):
        super().__init__()
        self.init_ui(name)

    def init_ui(self, name: str):
        layout = QtWidgets.QHBoxLayout(self)
        self.label = QtWidgets.QLabel(name)
        font = self.label.font()
        font.setPointSize(11)
        self.label.setFont(font)
        self.add_button = QtWidgets.QPushButton()
        self.add_button.setIcon(QtGui.QIcon.fromTheme("list-add"))
        self.add_button.setToolTip(f"Add {name}")
        self.add_button.setFixedSize(35, 35)
        self.setFixedHeight(55)

        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.add_button)
        self.setLayout(layout)

        self.setFrameStyle(QtWidgets.QFrame.StyledPanel | QtWidgets.QFrame.Raised) # type: ignore

class MovementFrame(QtWidgets.QFrame):
    def __init__(self, available_movements: list[Movement]):
        super().__init__()
        self.available_movements = available_movements
        self.movement_items: list[MovementItemWidget] = []
        self.init_ui()

    def init_ui(self):
        self.layouts = QtWidgets.QVBoxLayout(self)
        self.title_bar = TitleBar("Movement")
        self.layouts.addWidget(self.title_bar)
        self.setLayout(self.layouts)
        self.title_bar.add_button.clicked.connect(self.movement_selection)

    def add_movement_item(self, movement: Movement):
        self.movement_items.append(MovementItemWidget(movement))
        # add widget to layout
        self.layouts.addWidget(self.movement_items[-1])
        self.movement_items[-1].trash_frame.trash_button.clicked.connect(lambda: self.remove_movement_item(self.movement_items[-1]))

    def remove_movement_item(self, item: MovementItemWidget):
        if item in self.movement_items:
            self.movement_items.remove(item)
            item.setParent(None)
            item.deleteLater()

    def movement_selection(self):
        # Create a simple popdown menu of available movements for the user to select from
        menu = QtWidgets.QMenu(self)
        for movement in self.available_movements:
            action = menu.addAction(movement.name)
            action.triggered.connect(lambda checked, m=movement: self.add_movement_item(m))
        menu.exec(QtGui.QCursor.pos())

    def clear_movements(self):
        for item in self.movement_items:
            item.setParent(None)
            item.deleteLater()
        self.movement_items = []
        # remove all widgets from layout except title bar
        while self.layouts.count() > 1:
            item = self.layouts.takeAt(1)
            if item.widget():
                item.widget().setParent(None)
    
    def full_refresh(self, new_movements: list[Movement]):
        self.clear_movements()
        for movement in new_movements:
            self.add_movement_item(movement)

# create in window to test
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(window)
    measurement_frame = MeasurementFrame([LockInAmplifierMeasurement("Lock-in Amplifier"), VoltageMeterMeasurement("Voltage Meter")])
    layout.addWidget(measurement_frame)

    window.setLayout(layout)
    window.show()
    sys.exit(app.exec())