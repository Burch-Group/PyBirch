# type: ignore
from PySide6 import QtCore, QtWidgets, QtGui


class AvailableInstrumentWidget(QtWidgets.QDialog):
    """
    A standalone dialog window that lists all available instruments (with connectivity info),
    and lets the user select exactly one to continue.
    """

    def __init__(self, instrument_data, parent=None):
        """
        instrument_data: list of Measurement or Movement objects from InstrumentManager
        Each object should have 'name', 'adapter', and 'status' attributes.
        """
        super().__init__(parent)
        self.setWindowTitle("Available Instruments")
        self.resize(600, 300)
        self.setModal(True)

        self.instrument_data = instrument_data
        self.selected_instrument = None

        layout = QtWidgets.QVBoxLayout(self)

        # Table setup
        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Instrument", "Adapter", "Status", "Select"])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.table)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.continue_button = QtWidgets.QPushButton("Continue")
        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.continue_button)
        layout.addLayout(button_layout)
        self.continue_button.setDefault(True)

        # Populate the table
        self.load_instruments()

        # Button connections
        self.cancel_button.clicked.connect(self.reject)
        self.continue_button.clicked.connect(self.on_continue)

    # --------------------------------------------------------------------------
    def load_instruments(self):
        """Populate table with instrument data."""
        self.table.setRowCount(0)
        self.radio_group = QtWidgets.QButtonGroup(self)
        self.radio_group.setExclusive(True)

        for idx, inst in enumerate(self.instrument_data):
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Instrument name
            item_name = QtWidgets.QTableWidgetItem(inst.name)
            item_name.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.table.setItem(row, 0, item_name)

            # Adapter string
            item_adapter = QtWidgets.QTableWidgetItem(inst.adapter)
            item_adapter.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.table.setItem(row, 1, item_adapter)

            # Status indicator (green check/red cross emoji)
            status_icon = "✅" if inst.status else "❌"

            status_item = QtWidgets.QTableWidgetItem()
            status_item.setTextAlignment(QtCore.Qt.AlignCenter)
            status_item.setText(status_icon)
            self.table.setItem(row, 2, status_item)

            # Radio button for selection
            radio = QtWidgets.QRadioButton()
            radio_widget = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(radio_widget)
            layout.addWidget(radio)
            layout.setAlignment(QtCore.Qt.AlignCenter)
            layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 3, radio_widget)
            self.radio_group.addButton(radio, row)

    # --------------------------------------------------------------------------
    def on_continue(self):
        """Get selected instrument and close dialog."""
        selected_id = self.radio_group.checkedId()
        print("Selected ID:", selected_id)
        if selected_id == -1:
            # if no selection, check if user has highlighted a row instead
            selected_items = self.table.selectedItems()
            print("Selected items:", selected_items)
            if selected_items:
                selected_id = selected_items[0].row()
                print("Using selected row:", selected_id)
            else:
                QtWidgets.QMessageBox.warning(self, "No Selection", "Please select an instrument to continue.")
                return

        self.selected_instrument = self.instrument_data[selected_id]
        self.accept()

    # --------------------------------------------------------------------------
    @staticmethod
    def select_instrument(instrument_data, parent=None):
        """
        Convenience static method to open the dialog and return the selected instrument dict.
        Returns None if canceled.
        """
        dialog = AvailableInstrumentWidget(instrument_data, parent)
        result = dialog.exec()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.selected_instrument
        return None


# ------------------------------------------------------------------------------
# Example standalone test:
if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    # Example data from the InstrumentManager
    sample_data = [
        {"name": "Oscilloscope", "adapter": "GPIB0::5::INSTR", "status": True},
        {"name": "Multimeter", "adapter": "COM3", "status": False},
        {"name": "Signal Generator", "adapter": "USB0::0x1234::0x5678::INSTR", "status": True},
    ]

    selected = AvailableInstrumentWidget.select_instrument(sample_data)
    if selected:
        print("Selected instrument:", selected)
    else:
        print("User cancelled.")

    app.exec()