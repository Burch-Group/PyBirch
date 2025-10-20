# type: ignore
import sys, inspect
from pathlib import Path
import os
import pickle
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from pybirch.scan.measurements import Measurement, VisaMeasurement
from pybirch.scan.movements import Movement, VisaMovement
from PySide6 import QtCore, QtWidgets, QtGui
import pyvisa

# uses pyvisa resource manager to automatically detect and load all available adapters (COM and GPIB) as strings

# then display these in a QTableWidget, along with a corresponding instrument name (optional), and the status of the connection. Allow
# user to select an instrument name from a dropdown list for each adapter.
# Also allow the user to add placeholder adapters (e.g. for simulated instruments). The adapter 
# string for these will be placeholder_X where X is a number that increments with each new placeholder
# added. 

# Finally, allow the user to merge a placeholder adapter with a real adapter by selecting both and pressing a button, so that the placeholder
# is replaced with the real adapter string, but the instrument name is retained.

# There should also be a button to check the connection to each adapter, which will utilize the 
# check_connection method of the corresponding instrument class, and display a green tick or red cross
# next to the adapter string in the list.
import random

# Simulated instrument classes
class BaseInstrument:
    def __init__(self, resource_name):
        self.resource_name = resource_name

    def check_connection(self):
        # Simulated connection check: 50% chance of success. Let's be realistic.
        return random.random() < 0.5


class InstrumentManager(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Instrument Adapter Manager")
        self.resize(800, 400)

        # PyVISA resource manager
        try:
            self.rm = pyvisa.ResourceManager()
            self.resources = list(self.rm.list_resources())
        except Exception as e:
            print("Could not initialize VISA:", e)
            self.resources = []

        self.placeholder_count = 0
        self.instrument_names = ["Oscilloscope", "Multimeter", "Power Supply", "Signal Generator", "Custom"]

        # UI Layout
        layout = QtWidgets.QVBoxLayout(self)

        # Table setup
        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Adapter", "Instrument", "Status", "Select"])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.table)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        self.refresh_button = QtWidgets.QPushButton("Refresh Adapters")
        self.add_placeholder_button = QtWidgets.QPushButton("Add Placeholder")
        self.merge_button = QtWidgets.QPushButton("Merge Selected")
        self.check_button = QtWidgets.QPushButton("Check Connections")

        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.add_placeholder_button)
        button_layout.addWidget(self.merge_button)
        button_layout.addWidget(self.check_button)
        layout.addLayout(button_layout)

        # Connections
        self.refresh_button.clicked.connect(self.load_adapters)
        self.add_placeholder_button.clicked.connect(self.add_placeholder)
        self.merge_button.clicked.connect(self.merge_selected)
        self.check_button.clicked.connect(self.check_connections)

        self.load_adapters()

    def load_adapters(self):
        """Load adapters from VISA resource manager."""
        self.table.setRowCount(0)
        try:
            self.resources = list(self.rm.list_resources())
        except Exception:
            self.resources = []

        for res in self.resources:
            self.add_row(res)

    def add_row(self, adapter_name, instrument_name=None):
        """Add a new row for the given adapter."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Adapter name
        item_adapter = QtWidgets.QTableWidgetItem(adapter_name)
        item_adapter.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        self.table.setItem(row, 0, item_adapter)

        # Instrument name dropdown
        combo = QtWidgets.QComboBox()
        combo.addItems(self.instrument_names)
        if instrument_name:
            index = combo.findText(instrument_name)
            if index >= 0:
                combo.setCurrentIndex(index)
        self.table.setCellWidget(row, 1, combo)

        # Status icon (blank initially)
        item_status = QtWidgets.QTableWidgetItem()
        item_status.setTextAlignment(QtCore.Qt.AlignCenter)
        self.table.setItem(row, 2, item_status)

        # Selection checkbox
        checkbox = QtWidgets.QCheckBox()
        checkbox_widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(checkbox_widget)
        layout.addWidget(checkbox)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table.setCellWidget(row, 3, checkbox_widget)

    def add_placeholder(self):
        """Add a simulated placeholder adapter."""
        self.placeholder_count += 1
        placeholder_name = f"placeholder_{self.placeholder_count}"
        self.add_row(placeholder_name)

    def get_selected_rows(self):
        """Return list of row indices that are checked."""
        selected_rows = []
        for i in range(self.table.rowCount()):
            widget = self.table.cellWidget(i, 3)
            if widget and widget.findChild(QtWidgets.QCheckBox).isChecked():
                selected_rows.append(i)
        return selected_rows

    def merge_selected(self):
        """Merge a placeholder with a real adapter."""
        selected_rows = self.get_selected_rows()
        if len(selected_rows) != 2:
            QtWidgets.QMessageBox.warning(self, "Merge Error",
                                          "Please select exactly TWO rows (one placeholder and one real adapter).")
            return

        # Identify placeholder and real adapter
        adapters = [self.table.item(i, 0).text() for i in selected_rows]
        placeholders = [a for a in adapters if a.startswith("placeholder_")]
        real_adapters = [a for a in adapters if not a.startswith("placeholder_")]

        if len(placeholders) != 1 or len(real_adapters) != 1:
            QtWidgets.QMessageBox.warning(self, "Merge Error",
                                          "You must select one placeholder and one real adapter.")
            return

        # Keep instrument name from placeholder
        placeholder_row = selected_rows[adapters.index(placeholders[0])]
        real_row = selected_rows[adapters.index(real_adapters[0])]

        instrument_name = self.table.cellWidget(placeholder_row, 1).currentText()

        # Replace placeholder adapter with real one
        self.table.item(placeholder_row, 0).setText(real_adapters[0])
        self.table.cellWidget(placeholder_row, 1).setCurrentText(instrument_name)

        # Remove the real adapter row
        self.table.removeRow(real_row if real_row > placeholder_row else real_row)

        QtWidgets.QMessageBox.information(self, "Merge Complete",
                                          f"Merged placeholder with adapter {real_adapters[0]}.")

    def check_connections(self):
        """Check connection to each adapter and display green tick or red cross."""
        for row in range(self.table.rowCount()):
            adapter = self.table.item(row, 0).text()
            status_item = self.table.item(row, 2)
            instrument = BaseInstrument(adapter)
            connected = instrument.check_connection()

            icon = QtGui.QPixmap(16, 16)
            icon.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(icon)
            painter.setBrush(QtGui.QBrush(QtCore.Qt.green if connected else QtCore.Qt.red))
            painter.setPen(QtCore.Qt.black)
            painter.drawEllipse(0, 0, 15, 15)
            painter.end()

            status_item.setIcon(QtGui.QIcon(icon))
            status_item.setText("Connected" if connected else "Failed")

    def auto_pair(self, instrument_classes):
        """Automatically pair adapters with instruments by doing a pairwise search with the check_connection method."""
        for row in range(self.table.rowCount()):
            adapter = self.table.item(row, 0).text()
            if adapter.startswith("placeholder_"):
                continue  # Skip placeholders

            for inst_class in instrument_classes:
                instrument = inst_class(adapter)
                if instrument.check_connection():
                    # Found a match, set the instrument name
                    combo = self.table.cellWidget(row, 1)
                    index = combo.findText(inst_class.__name__)
                    if index >= 0:
                        combo.setCurrentIndex(index)
                    break
        


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    window = InstrumentManager()
    window.show()
    app.exec()