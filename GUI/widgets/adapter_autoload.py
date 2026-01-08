# type: ignore
import sys, inspect
from pathlib import Path
import os
import pickle
from datetime import datetime
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from pybirch.scan.measurements import Measurement, VisaMeasurement
from pybirch.scan.movements import Movement, VisaMovement
from PySide6 import QtCore, QtWidgets, QtGui
import pyvisa

# Import theme
try:
    from GUI.theme import Theme
except ImportError:
    try:
        from theme import Theme
    except ImportError:
        Theme = None

# Connection status constants
class ConnectionStatus:
    ONLINE = "online"       # Adapter is currently detected and connected
    OFFLINE = "offline"     # Adapter was previously configured but not currently detected  
    UNKNOWN = "unknown"     # Connection status not yet checked
    FAILED = "failed"       # Adapter detected but connection check failed

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
        self.instrument_names = ["None"]
        self.instrument_classes = [BaseInstrument]  # Add actual instrument classes here

        # UI Layout
        layout = QtWidgets.QVBoxLayout(self)

        # Table setup
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Adapter", "Instrument", "Nickname", "Status", ""])
        
        # Apply theme styling to table
        if Theme:
            self.table.setStyleSheet(f"""
                QTableWidget {{
                    background-color: {Theme.colors.background_primary};
                    color: {Theme.colors.text_primary};
                    border: 1px solid {Theme.colors.border_light};
                    gridline-color: {Theme.colors.border_light};
                }}
                QTableWidget::item {{
                    padding: 4px 8px;
                }}
                QTableWidget::item:selected {{
                    background-color: {Theme.colors.accent_primary};
                    color: {Theme.colors.text_inverse};
                }}
                QHeaderView::section {{
                    background-color: {Theme.colors.background_secondary};
                    color: {Theme.colors.text_primary};
                    border: 1px solid {Theme.colors.border_light};
                    padding: 6px;
                    font-weight: bold;
                }}
            """)
        
        # Enable row selection
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        
        # Set fixed row height (50% taller than default for better readability)
        self.table.verticalHeader().setDefaultSectionSize(72)
        self.table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
        
        # Set column resize modes
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)  # Adapter
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)  # Instrument - stretch to fit
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)  # Nickname
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)  # Status
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.Fixed)  # Select checkbox
        header.resizeSection(4, 60)  # Fixed width for checkbox column
        
        # Set minimum section sizes
        header.setMinimumSectionSize(80)
        
        layout.addWidget(self.table)

        # Buttons - Single row
        button_layout = QtWidgets.QHBoxLayout()
        self.refresh_button = QtWidgets.QPushButton("Refresh Adapters")
        if Theme:
            self.refresh_button.setStyleSheet(Theme.primary_button_style())
        self.add_placeholder_button = QtWidgets.QPushButton("Add Placeholder")
        if Theme:
            self.add_placeholder_button.setStyleSheet(Theme.primary_button_style())
        self.check_button = QtWidgets.QPushButton("Check Connections")
        if Theme:
            self.check_button.setStyleSheet(Theme.primary_button_style())
        self.autopair_button = QtWidgets.QPushButton("Autopair")
        if Theme:
            self.autopair_button.setStyleSheet(Theme.primary_button_style())
        self.front_panel_button = QtWidgets.QPushButton("Front Panel")
        if Theme:
            self.front_panel_button.setStyleSheet(Theme.primary_button_style())
        self.settings_button = QtWidgets.QPushButton("Settings")
        if Theme:
            self.settings_button.setStyleSheet(Theme.primary_button_style())

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
        """Load adapters from VISA resource manager while preserving configured adapters.
        
        This method:
        1. Preserves all configured adapters (with instrument assignments)
        2. Marks adapters as online/offline based on current VISA detection
        3. Adds newly detected adapters
        4. Preserves placeholder adapters
        """
        # Store ALL existing configured adapters before clearing
        existing_configs = []
        for row in range(self.table.rowCount()):
            adapter = self.table.item(row, 0).text()
            instrument_combo = self.table.cellWidget(row, 1)
            instrument_name = instrument_combo.currentText() if instrument_combo else "None"
            nickname = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
            status = self.table.item(row, 3).text() if self.table.item(row, 3) else ""
            
            # Store configuration for adapters that have an instrument assigned
            # (not just "None" or empty) or are placeholders
            if instrument_name not in ["None", "No instruments selected", ""] or adapter.startswith("placeholder_"):
                existing_configs.append({
                    'adapter': adapter,
                    'instrument': instrument_name,
                    'nickname': nickname,
                    'was_configured': True
                })
        
        # Clear table and reload VISA resources
        self.table.setRowCount(0)
        try:
            self.resources = list(self.rm.list_resources())
        except Exception:
            self.resources = []
        
        # Track which configured adapters are now online
        online_adapters = set(self.resources)
        added_adapters = set()
        
        # First, add all currently detected VISA resources
        for res in self.resources:
            # Check if this adapter was previously configured
            config = next((c for c in existing_configs if c['adapter'] == res), None)
            if config:
                self.add_row(res, config['instrument'], config['nickname'], 
                           status=ConnectionStatus.ONLINE)
            else:
                self.add_row(res, status=ConnectionStatus.ONLINE)
            added_adapters.add(res)
        
        # Then add configured adapters that are now offline (but not placeholders)
        for config in existing_configs:
            adapter = config['adapter']
            if adapter not in added_adapters and not adapter.startswith("placeholder_"):
                # This adapter was configured but is now offline
                self.add_row(adapter, config['instrument'], config['nickname'],
                           status=ConnectionStatus.OFFLINE)
                added_adapters.add(adapter)
        
        # Finally, add placeholder adapters
        for config in existing_configs:
            adapter = config['adapter']
            if adapter.startswith("placeholder_") and adapter not in added_adapters:
                self.add_row(adapter, config['instrument'], config['nickname'])
                added_adapters.add(adapter)

    def add_row(self, adapter_name, instrument_name=None, nickname="", status=None):
        """Add a new row for the given adapter.
        
        Args:
            adapter_name: The adapter/resource string
            instrument_name: Optional instrument name to pre-select
            nickname: Optional user-defined nickname
            status: Connection status (online/offline/unknown)
        """
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Adapter name - style based on status
        item_adapter = QtWidgets.QTableWidgetItem(adapter_name)
        item_adapter.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        
        # Apply visual styling based on connection status
        if status == ConnectionStatus.OFFLINE:
            # Gray out offline adapters and add indicator
            item_adapter.setForeground(QtGui.QColor("#888888"))
            item_adapter.setToolTip(f"⚠️ Offline - This adapter is not currently detected.\n"
                                   f"Configuration will be preserved until reconnected.")
        elif status == ConnectionStatus.ONLINE:
            item_adapter.setForeground(QtGui.QColor("#00AA00") if Theme is None else QtGui.QColor(Theme.colors.status_success))
            item_adapter.setToolTip("✓ Online - Adapter is currently connected")
        
        self.table.setItem(row, 0, item_adapter)

        # Instrument name dropdown
        combo = QtWidgets.QComboBox()
        combo.addItems(self.instrument_names)
        if instrument_name:
            index = combo.findText(instrument_name)
            if index >= 0:
                combo.setCurrentIndex(index)
            elif instrument_name not in ["None", "No instruments selected", ""]:
                # Instrument was configured but driver not currently loaded - add as placeholder
                combo.addItem(f"⚠️ {instrument_name} (driver not loaded)")
                combo.setCurrentIndex(combo.count() - 1)
        
        self.table.setCellWidget(row, 1, combo)
        
        # Set the row height to match the combobox height
        self.table.setRowHeight(row, 48)

        # Nickname (editable)
        item_nickname = QtWidgets.QTableWidgetItem(nickname)
        item_nickname.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable)
        self.table.setItem(row, 2, item_nickname)

        # Status column - show connection status with icon
        item_status = QtWidgets.QTableWidgetItem()
        item_status.setTextAlignment(QtCore.Qt.AlignCenter)
        item_status.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        
        # Set initial status based on provided status
        if status == ConnectionStatus.ONLINE:
            self._set_status_icon(item_status, "online", "Online")
        elif status == ConnectionStatus.OFFLINE:
            self._set_status_icon(item_status, "offline", "Offline")
        # Otherwise leave blank for unknown status
        
        self.table.setItem(row, 3, item_status)

        # Selection checkbox - single centered checkbox
        checkbox = QtWidgets.QCheckBox()
        checkbox.setStyleSheet("""
            QCheckBox {
                background: transparent;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #999;
                border-radius: 3px;
                background-color: white;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #0078d4;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border: 2px solid #0078d4;
                image: url(none);
            }
        """)
        
        checkbox_widget = QtWidgets.QWidget()
        checkbox_widget.setStyleSheet("background: transparent;")
        layout = QtWidgets.QHBoxLayout(checkbox_widget)
        layout.addWidget(checkbox)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table.setCellWidget(row, 4, checkbox_widget)
    
    def _set_status_icon(self, item: QtWidgets.QTableWidgetItem, status: str, text: str = ""):
        """Set the status icon and text for a table item.
        
        Args:
            item: The QTableWidgetItem to update
            status: Status type ('online', 'offline', 'failed', 'unknown')
            text: Optional text to display alongside icon
        """
        # Create colored circle icon
        icon = QtGui.QPixmap(16, 16)
        icon.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(icon)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        if status == "online":
            painter.setBrush(QtGui.QBrush(QtGui.QColor("#00AA00")))  # Green
            painter.setPen(QtGui.QPen(QtGui.QColor("#008800"), 1))
        elif status == "offline":
            painter.setBrush(QtGui.QBrush(QtGui.QColor("#888888")))  # Gray
            painter.setPen(QtGui.QPen(QtGui.QColor("#666666"), 1))
        elif status == "failed":
            painter.setBrush(QtGui.QBrush(QtGui.QColor("#DD0000")))  # Red
            painter.setPen(QtGui.QPen(QtGui.QColor("#AA0000"), 1))
        else:  # unknown
            painter.setBrush(QtGui.QBrush(QtGui.QColor("#FFAA00")))  # Orange/Yellow
            painter.setPen(QtGui.QPen(QtGui.QColor("#CC8800"), 1))
        
        painter.drawEllipse(2, 2, 12, 12)
        painter.end()
        
        item.setIcon(QtGui.QIcon(icon))
        item.setText(text)

    def add_placeholder(self):
        """Add a simulated placeholder adapter."""
        self.placeholder_count += 1
        placeholder_name = f"placeholder_{self.placeholder_count}"
        self.add_row(placeholder_name)

    def get_selected_rows(self):
        """Return list of row indices that are selected in the table."""
        selected_rows = []
        
        # Check if we should use table selection or checkbox selection
        table_selection = self.table.selectionModel().selectedRows()
        
        if table_selection:
            # Use table row selection
            for selection in table_selection:
                selected_rows.append(selection.row())
        else:
            # Fall back to checkbox selection if no rows are selected
            for i in range(self.table.rowCount()):
                widget = self.table.cellWidget(i, 4)  # Updated to column 4 (Select)
                if widget and widget.findChild(QtWidgets.QCheckBox).isChecked():
                    selected_rows.append(i)
        
        return selected_rows

    def merge_selected(self):
        """Merge an offline adapter with an online adapter (replaces the old placeholder merge).
        
        This allows users to:
        1. Merge an offline configured adapter with a newly detected online adapter
        2. Transfer instrument assignment and nickname from offline to online
        """
        selected_rows = self.get_selected_rows()
        if len(selected_rows) != 2:
            QtWidgets.QMessageBox.warning(self, "Merge Error",
                                          "Please select exactly TWO rows to merge.\n\n"
                                          "Typical use: Select an OFFLINE adapter (gray) and an ONLINE adapter\n"
                                          "to transfer the configuration to the new adapter.")
            return

        # Get status of each row to identify source (offline/placeholder) and target (online)
        adapters = [self.table.item(i, 0).text() for i in selected_rows]
        statuses = [self.table.item(i, 3).text() for i in selected_rows]
        
        # Determine source and target rows
        source_row = None
        target_row = None
        
        # Check for placeholder first (legacy support)
        placeholders = [(i, a) for i, a in zip(selected_rows, adapters) if a.startswith("placeholder_")]
        real_adapters = [(i, a) for i, a in zip(selected_rows, adapters) if not a.startswith("placeholder_")]
        
        if placeholders and real_adapters:
            # Legacy placeholder merge
            source_row = placeholders[0][0]
            target_row = real_adapters[0][0]
        else:
            # Try to identify offline -> online merge
            offline_rows = [(i, a) for i, (a, s) in zip(selected_rows, zip(adapters, statuses)) 
                           if s == "Offline" or self.table.item(i, 0).foreground().color().name() == "#888888"]
            online_rows = [(i, a) for i, (a, s) in zip(selected_rows, zip(adapters, statuses))
                          if s == "Online" or (s != "Offline" and not adapters[selected_rows.index(i)].startswith("placeholder_"))]
            
            if offline_rows and online_rows:
                source_row = offline_rows[0][0]
                target_row = online_rows[0][0]
            else:
                # Just use first as source, second as target
                source_row = selected_rows[0]
                target_row = selected_rows[1]
        
        # Get source data
        source_instrument = self.table.cellWidget(source_row, 1).currentText()
        source_nickname = self.table.item(source_row, 2).text()
        target_adapter = self.table.item(target_row, 0).text()

        # Transfer source data to target row
        target_combo = self.table.cellWidget(target_row, 1)
        if target_combo:
            index = target_combo.findText(source_instrument)
            if index >= 0:
                target_combo.setCurrentIndex(index)
            elif source_instrument and not source_instrument.startswith("⚠️"):
                # Add the instrument if not found
                target_combo.addItem(source_instrument)
                target_combo.setCurrentIndex(target_combo.count() - 1)
        
        self.table.item(target_row, 2).setText(source_nickname)

        # Remove the source row
        self.table.removeRow(source_row)

        QtWidgets.QMessageBox.information(self, "Merge Complete",
                                          f"Configuration transferred to adapter {target_adapter}.")

    def check_connections(self):
        """Check connection to each adapter and display status."""
        for row in range(self.table.rowCount()):
            self.check_connection_for_row(row)

    def check_connection_for_row(self, row):
        """Check connection for a specific row."""
        adapter = self.table.item(row, 0).text()
        status_item = self.table.item(row, 3)
        adapter_item = self.table.item(row, 0)
        
        # Skip placeholders
        if adapter.startswith("placeholder_"):
            self._set_status_icon(status_item, "unknown", "Simulated")
            return
        
        # Check if adapter is in current VISA resources
        try:
            current_resources = list(self.rm.list_resources())
        except Exception:
            current_resources = []
        
        if adapter not in current_resources:
            # Adapter not currently detected
            self._set_status_icon(status_item, "offline", "Offline")
            adapter_item.setForeground(QtGui.QColor("#888888"))
            adapter_item.setToolTip(f"⚠️ Offline - Adapter not currently detected")
            return
        
        # Adapter is detected - try to check actual connection
        instrument = BaseInstrument(adapter)
        connected = instrument.check_connection()
        
        if connected:
            self._set_status_icon(status_item, "online", "Connected")
            adapter_item.setForeground(QtGui.QColor("#00AA00") if Theme is None else QtGui.QColor(Theme.colors.status_success))
            adapter_item.setToolTip("✓ Online and connected")
        else:
            self._set_status_icon(status_item, "failed", "Failed")
            adapter_item.setForeground(QtGui.QColor("#DD0000"))
            adapter_item.setToolTip("✗ Adapter detected but connection check failed")
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

    def serialize(self) -> dict:
        """Serialize the adapter manager data to a dictionary."""
        adapters = []
        for row in range(self.table.rowCount()):
            adapter_item = self.table.item(row, 0)
            instrument_combo = self.table.cellWidget(row, 1)
            nickname_item = self.table.item(row, 2)
            status_item = self.table.item(row, 3)
            checkbox_widget = self.table.cellWidget(row, 4)
            
            if adapter_item and instrument_combo:
                checkbox = checkbox_widget.findChild(QtWidgets.QCheckBox) if checkbox_widget else None
                adapters.append({
                    'adapter': adapter_item.text(),
                    'instrument': instrument_combo.currentText(),
                    'nickname': nickname_item.text() if nickname_item else "",
                    'status': status_item.text() if status_item else "",
                    'selected': checkbox.isChecked() if checkbox else False
                })
        
        return {
            'adapters': adapters,
            'placeholder_count': self.placeholder_count,
            'instrument_names': self.instrument_names
        }
    
    def deserialize(self, data: dict):
        """Deserialize and restore adapter manager data from a dictionary."""
        # Clear existing table
        self.table.setRowCount(0)
        
        # Restore placeholder count and instrument names
        self.placeholder_count = data.get('placeholder_count', 0)
        self.instrument_names = data.get('instrument_names', ["None"])
        
        # Restore adapter rows
        for adapter_data in data.get('adapters', []):
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Adapter name
            adapter_item = QtWidgets.QTableWidgetItem(adapter_data.get('adapter', ''))
            adapter_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.table.setItem(row, 0, adapter_item)
            
            # Instrument dropdown
            combo = QtWidgets.QComboBox()
            combo.addItems(self.instrument_names)
            instrument_name = adapter_data.get('instrument', '')
            index = combo.findText(instrument_name)
            
            # If instrument not found in current list, add it as a placeholder
            if index < 0 and instrument_name and instrument_name not in self.instrument_names:
                # Add the missing instrument as a placeholder to preserve the configuration
                self.instrument_names.append(instrument_name)
                combo.addItem(instrument_name)
                index = combo.findText(instrument_name)
            
            if index >= 0:
                combo.setCurrentIndex(index)
            
            # Set fixed height to match table row height
            combo.setMaximumHeight(28)
            combo.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
            
            self.table.setCellWidget(row, 1, combo)
            
            # Set the row height to match the combobox height
            self.table.setRowHeight(row, 32)
            
            # Nickname
            nickname_item = QtWidgets.QTableWidgetItem(adapter_data.get('nickname', ''))
            nickname_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable)
            self.table.setItem(row, 2, nickname_item)
            
            # Status
            status_item = QtWidgets.QTableWidgetItem(adapter_data.get('status', ''))
            status_item.setTextAlignment(QtCore.Qt.AlignCenter)
            status_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.table.setItem(row, 3, status_item)
            
            # Selection checkbox
            checkbox = QtWidgets.QCheckBox()
            checkbox.setChecked(adapter_data.get('selected', False))
            checkbox_widget = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(checkbox_widget)
            layout.addWidget(checkbox)
            layout.setAlignment(QtCore.Qt.AlignCenter)
            layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 4, checkbox_widget)
    
    def get_configured_instruments(self):
        """Get list of configured instruments with their adapters and nicknames.
        
        Returns:
            List of dicts with keys: 'name', 'adapter', 'nickname', 'class', 'instance'
        """
        configured_instruments = []
        
        for row in range(self.table.rowCount()):
            # Get adapter name
            adapter_item = self.table.item(row, 0)
            if not adapter_item:
                continue
            adapter = adapter_item.text()
            
            # Get instrument name from combobox
            combo = self.table.cellWidget(row, 1)
            if not combo or not isinstance(combo, QtWidgets.QComboBox):
                continue
            instrument_name = combo.currentText()
            
            # Skip if no instrument selected
            if instrument_name == "None" or not instrument_name:
                continue
            
            # Get nickname
            nickname_item = self.table.item(row, 2)
            nickname = nickname_item.text() if nickname_item else ""
            
            # Get instrument class
            instrument_class = None
            instrument_instance = None
            if combo.currentIndex() < len(self.instrument_classes):
                instrument_class = self.instrument_classes[combo.currentIndex()]
                # Try to instantiate it with the adapter
                try:
                    instrument_instance = instrument_class(adapter)
                except Exception:
                    # If instantiation fails, just store the class
                    pass
            
            configured_instruments.append({
                'name': instrument_name,
                'adapter': adapter,
                'nickname': nickname,
                'class': instrument_class,
                'instance': instrument_instance
            })
        
        return configured_instruments


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    window = InstrumentManager()
    window.show()
    app.exec()