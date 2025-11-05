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
        self.instrument_classes = [BaseInstrument]  # Add actual instrument classes here

        # UI Layout
        layout = QtWidgets.QVBoxLayout(self)

        # Table setup
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Adapter", "Instrument", "Nickname", "Status", ""])
        
        # Use ResizeToContents mode for most columns - auto-size to fit their content
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        
        # Set the Select column (column 4) to stretch to fill remaining space
        self.table.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        
        # Set initial minimum column widths based on equal spacing
        QtCore.QTimer.singleShot(0, self.calculate_minimum_column_widths)
        layout.addWidget(self.table)

        # Buttons - Single row
        button_layout = QtWidgets.QHBoxLayout()
        self.refresh_button = QtWidgets.QPushButton("Refresh Adapters")
        self.add_placeholder_button = QtWidgets.QPushButton("Add Placeholder")
        self.check_button = QtWidgets.QPushButton("Check Connections")
        self.autopair_button = QtWidgets.QPushButton("Autopair")
        self.front_panel_button = QtWidgets.QPushButton("Front Panel")
        self.settings_button = QtWidgets.QPushButton("Settings")

        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.add_placeholder_button)
        button_layout.addWidget(self.check_button)
        button_layout.addWidget(self.autopair_button)
        button_layout.addWidget(self.front_panel_button)
        button_layout.addWidget(self.settings_button)
        layout.addLayout(button_layout)

        # Connections
        self.refresh_button.clicked.connect(self.load_adapters)
        self.add_placeholder_button.clicked.connect(self.add_placeholder)
        self.check_button.clicked.connect(self.check_connections)
        self.front_panel_button.clicked.connect(self.open_front_panel)
        self.settings_button.clicked.connect(self.open_settings)
        self.autopair_button.clicked.connect(self.run_autopair)

        # Setup context menu and shortcuts
        self.setup_context_menu()
        self.setup_shortcuts()

        self.load_adapters()

    def set_equal_column_widths(self):
        """Set all columns to equal width initially."""
        if self.table.width() > 0:
            # Calculate equal width for all columns
            table_width = self.table.width()
            # Account for potential scrollbar and margins
            available_width = table_width - 50  # Reserve space for scrollbar/margins
            num_columns = self.table.columnCount()
            
            if num_columns > 0:
                # Set equal width for all columns
                equal_width = available_width // num_columns
                self.column_widths = [equal_width] * num_columns
                for col in range(num_columns):
                    self.table.setColumnWidth(col, equal_width)

    def calculate_minimum_column_widths(self):
        """Calculate minimum column widths based on equal spacing, with Select column getting half space."""
        if self.table.width() > 0:
            # Calculate available width
            table_width = self.table.width()
            available_width = table_width - 50  # Reserve space for scrollbar/margins
            
            if available_width > 0:
                # Calculate base unit: Select gets 0.5 units, others get 1 unit each
                # Total units = 4 columns * 1 unit + 1 select column * 0.5 units = 4.5 units
                total_units = self.table.columnCount()
                base_width = available_width / total_units
                
                # Set minimum widths: regular columns get full width, Select gets half
                regular_min_width = int(base_width)
                select_min_width = int(base_width * 0.5)
                
                # Apply individual minimum widths to columns 0-3 (regular columns)
                for col in range(5):
                    self.table.horizontalHeader().setMinimumSectionSize(regular_min_width)
                    self.table.setColumnWidth(col, regular_min_width)

    def resizeEvent(self, event):
        """Handle widget resize events to recalculate minimum column sizes."""
        super().resizeEvent(event)
        # Recalculate minimum column widths when the widget is resized
        QtCore.QTimer.singleShot(0, self.calculate_minimum_column_widths)

    def setup_context_menu(self):
        """Setup right-click context menu for the table."""
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

    def setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Refresh Adapters
        refresh_shortcut = QtGui.QShortcut(QtGui.QKeySequence("F5"), self)
        refresh_shortcut.activated.connect(self.load_adapters)
        
        # Add Placeholder
        add_placeholder_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+N"), self)
        add_placeholder_shortcut.activated.connect(self.add_placeholder)
        
        # Check Connections
        check_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+T"), self)
        check_shortcut.activated.connect(self.check_connections)
        
        # Autopair
        autopair_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+A"), self)
        autopair_shortcut.activated.connect(self.run_autopair)
        
        # Front Panel
        front_panel_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+F"), self)
        front_panel_shortcut.activated.connect(self.open_front_panel)
        
        # Settings
        settings_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+S"), self)
        settings_shortcut.activated.connect(self.open_settings)
        
        # Duplicate
        duplicate_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+D"), self)
        duplicate_shortcut.activated.connect(self.duplicate_selected)
        
        # Merge
        merge_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+M"), self)
        merge_shortcut.activated.connect(self.merge_selected)
        
        # Delete/Remove
        delete_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Delete"), self)
        delete_shortcut.activated.connect(self.delete_selected)

    def show_context_menu(self, position):
        """Show context menu at the given position."""
        item = self.table.itemAt(position)
        menu = QtWidgets.QMenu(self)

        if item is None:
            # Right-clicked on empty space
            add_placeholder_action = menu.addAction("Add Placeholder")
            add_placeholder_action.triggered.connect(self.add_placeholder)
            
            menu.addSeparator()
            
            refresh_action = menu.addAction("Refresh Adapters")
            refresh_action.triggered.connect(self.load_adapters)
        else:
            # Right-clicked on an item
            row = item.row()
            
            # Get adapter and instrument info for the row
            adapter = self.table.item(row, 0).text()
            instrument_type = self.table.cellWidget(row, 1).currentText()

            # Context menu actions
            duplicate_action = menu.addAction("Duplicate\tCtrl+D")
            duplicate_action.triggered.connect(lambda: self.duplicate_row(row))

            merge_action = menu.addAction("Merge Selected\tCtrl+M")
            merge_action.triggered.connect(self.merge_selected)

            menu.addSeparator()

            front_panel_action = menu.addAction("Open Front Panel\tCtrl+F")
            front_panel_action.triggered.connect(lambda: self.open_front_panel_for_row(row))

            settings_action = menu.addAction("Open Settings\tCtrl+S")
            settings_action.triggered.connect(lambda: self.open_settings_for_row(row))

            menu.addSeparator()

            check_connection_action = menu.addAction("Check Connection\tCtrl+T")
            check_connection_action.triggered.connect(lambda: self.check_connection_for_row(row))

            if not adapter.startswith("placeholder_"):
                menu.addSeparator()
                remove_action = menu.addAction("Remove\tDel")
                remove_action.triggered.connect(lambda: self.remove_row(row))

        # Show menu
        menu.exec(self.table.mapToGlobal(position))

    def load_adapters(self):
        """Load adapters from VISA resource manager while preserving placeholder adapters."""
        # Store existing placeholder adapters before clearing
        existing_placeholders = []
        for row in range(self.table.rowCount()):
            adapter = self.table.item(row, 0).text()
            if adapter.startswith("placeholder_"):
                # Store placeholder data: adapter, instrument, nickname
                instrument_name = self.table.cellWidget(row, 1).currentText()
                nickname = self.table.item(row, 2).text()
                existing_placeholders.append((adapter, instrument_name, nickname))
        
        # Clear table and reload VISA resources
        self.table.setRowCount(0)
        try:
            self.resources = list(self.rm.list_resources())
        except Exception:
            self.resources = []

        # Add VISA resources
        for res in self.resources:
            self.add_row(res)
        
        # Re-add preserved placeholder adapters
        for adapter, instrument_name, nickname in existing_placeholders:
            self.add_row(adapter, instrument_name, nickname)

    def add_row(self, adapter_name, instrument_name=None, nickname=""):
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

        # Nickname (editable)
        item_nickname = QtWidgets.QTableWidgetItem(nickname)
        item_nickname.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable)
        self.table.setItem(row, 2, item_nickname)

        # Status icon (blank initially)
        item_status = QtWidgets.QTableWidgetItem()
        item_status.setTextAlignment(QtCore.Qt.AlignCenter)
        self.table.setItem(row, 3, item_status)

        # Selection checkbox
        checkbox = QtWidgets.QCheckBox()
        checkbox_widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(checkbox_widget)
        layout.addWidget(checkbox)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table.setCellWidget(row, 4, checkbox_widget)

    def add_placeholder(self):
        """Add a simulated placeholder adapter."""
        self.placeholder_count += 1
        placeholder_name = f"placeholder_{self.placeholder_count}"
        self.add_row(placeholder_name)

    def get_selected_rows(self):
        """Return list of row indices that are checked."""
        selected_rows = []
        for i in range(self.table.rowCount()):
            widget = self.table.cellWidget(i, 4)  # Updated to column 4 (Select)
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

        # Get data from placeholder to transfer to real adapter
        placeholder_row = selected_rows[adapters.index(placeholders[0])]
        real_row = selected_rows[adapters.index(real_adapters[0])]

        # Get placeholder data
        placeholder_instrument = self.table.cellWidget(placeholder_row, 1).currentText()
        placeholder_nickname = self.table.item(placeholder_row, 2).text()

        # Transfer placeholder data to real adapter row, keep real adapter string
        self.table.cellWidget(real_row, 1).setCurrentText(placeholder_instrument)
        self.table.item(real_row, 2).setText(placeholder_nickname)

        # Remove the placeholder row
        self.table.removeRow(placeholder_row)

        QtWidgets.QMessageBox.information(self, "Merge Complete",
                                          f"Merged placeholder data to adapter {real_adapters[0]}.")

    def check_connections(self):
        """Check connection to each adapter and display green tick or red cross."""
        for row in range(self.table.rowCount()):
            adapter = self.table.item(row, 0).text()
            status_item = self.table.item(row, 3)  # Updated to column 3 (Status)
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

    def get_selected_instrument(self):
        """Get the first selected instrument's adapter and type."""
        selected_rows = self.get_selected_rows()
        if not selected_rows:
            return None, None
        
        row = selected_rows[0]
        adapter = self.table.item(row, 0).text()
        instrument_type = self.table.cellWidget(row, 1).currentText()
        return adapter, instrument_type

    def open_front_panel(self):
        """Open the front panel UI for the selected instrument."""
        adapter, instrument_type = self.get_selected_instrument()
        if not adapter or not instrument_type:
            QtWidgets.QMessageBox.warning(self, "Selection Error",
                                          "Please select an instrument first.")
            return
        
        # TODO: Implement front panel UI opening based on instrument type
        QtWidgets.QMessageBox.information(self, "Front Panel",
                                          f"Opening front panel for {instrument_type} on {adapter}\n"
                                          "(Front panel UI not yet implemented)")

    def open_settings(self):
        """Open the settings UI for the selected instrument."""
        adapter, instrument_type = self.get_selected_instrument()
        if not adapter or not instrument_type:
            QtWidgets.QMessageBox.warning(self, "Selection Error",
                                          "Please select an instrument first.")
            return
        
        # TODO: Implement settings UI opening based on instrument type
        QtWidgets.QMessageBox.information(self, "Settings",
                                          f"Opening settings for {instrument_type} on {adapter}\n"
                                          "(Settings UI not yet implemented)")

    def run_autopair(self):
        """Run the autopair function with available instrument classes."""
        # TODO: Define actual instrument classes to use for autopairing

        QtWidgets.QMessageBox.information(self, "Autopair", "Starting autopair process...")
        self.auto_pair(self.instrument_classes)
        QtWidgets.QMessageBox.information(self, "Autopair", "Autopair process completed.")

    def duplicate_selected(self):
        """Duplicate the selected adapters."""
        selected_rows = self.get_selected_rows()
        if not selected_rows:
            QtWidgets.QMessageBox.warning(self, "Selection Error",
                                          "Please select at least one adapter to duplicate.")
            return

        for row in reversed(selected_rows):  # Reverse to maintain row indices
            self.duplicate_row(row)

    def duplicate_row(self, row):
        """Duplicate a specific row - preserves the original adapter string."""
        adapter = self.table.item(row, 0).text()
        instrument_type = self.table.cellWidget(row, 1).currentText()
        
        # Keep the same adapter string - do not modify it for VISA compatibility
        # Add the duplicated row with the same adapter string
        self.add_row(adapter, instrument_type)

    def open_front_panel_for_row(self, row):
        """Open front panel for a specific row."""
        adapter = self.table.item(row, 0).text()
        instrument_type = self.table.cellWidget(row, 1).currentText()
        
        # TODO: Implement front panel UI opening based on instrument type
        QtWidgets.QMessageBox.information(self, "Front Panel",
                                          f"Opening front panel for {instrument_type} on {adapter}\n"
                                          "(Front panel UI not yet implemented)")

    def open_settings_for_row(self, row):
        """Open settings for a specific row."""
        adapter = self.table.item(row, 0).text()
        instrument_type = self.table.cellWidget(row, 1).currentText()
        
        # TODO: Implement settings UI opening based on instrument type
        QtWidgets.QMessageBox.information(self, "Settings",
                                          f"Opening settings for {instrument_type} on {adapter}\n"
                                          "(Settings UI not yet implemented)")

    def check_connection_for_row(self, row):
        """Check connection for a specific row."""
        adapter = self.table.item(row, 0).text()
        status_item = self.table.item(row, 3)  # Updated to column 3 (Status)
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

    def remove_row(self, row):
        """Remove a specific row."""
        adapter = self.table.item(row, 0).text()
        reply = QtWidgets.QMessageBox.question(self, "Confirm Remove",
                                               f"Are you sure you want to remove adapter '{adapter}'?",
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            self.table.removeRow(row)

    def delete_selected(self):
        """Delete all selected rows."""
        selected_rows = self.get_selected_rows()
        if not selected_rows:
            QtWidgets.QMessageBox.warning(self, "Selection Error",
                                          "Please select at least one adapter to delete.")
            return

        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(self, "Confirm Delete",
                                               f"Are you sure you want to delete {len(selected_rows)} selected adapter(s)?",
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            # Remove rows in reverse order to maintain indices
            for row in reversed(sorted(selected_rows)):
                self.table.removeRow(row)
        


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    window = InstrumentManager()
    window.show()
    app.exec()