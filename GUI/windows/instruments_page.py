import sys
from PySide6 import QtCore, QtWidgets, QtGui
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

# Import required widgets
from GUI.widgets.adapter_autoload import InstrumentManager
from GUI.widgets.instrument_autoload import InstrumentAutoLoadWidget


class InstrumentsPage(QtWidgets.QWidget):
    """
    Instruments page widget that combines:
    - Adapter autoload widget on the left
    - Instrument autoload widget on the right
    - Dynamic instrument list synchronization
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.connect_signals()
    
    def init_ui(self):
        """Initialize the user interface components."""
        # Create main layout with splitter for resizable divider
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Create horizontal splitter
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter)
        
        # Create left side (Adapter Manager)
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add title for adapter manager
        adapter_title = QtWidgets.QLabel("Adapter Manager")
        adapter_title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                margin-bottom: 5px;
            }
        """)
        left_layout.addWidget(adapter_title)
        
        # Create adapter manager
        self.adapter_manager = InstrumentManager()
        left_layout.addWidget(self.adapter_manager)
        
        # Create right side (Instrument Selection)
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add title for instrument selection
        instrument_title = QtWidgets.QLabel("Instrument Selection")
        instrument_title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                margin-bottom: 5px;
            }
        """)
        right_layout.addWidget(instrument_title)
        
        # Create instrument autoload widget
        # Use the pybirch instruments directory - this will scan for Measurement/Movement classes
        instruments_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'pybirch', 'setups')
        self.instrument_selector = InstrumentAutoLoadWidget(instruments_dir)
        right_layout.addWidget(self.instrument_selector)
        
        # Add both sides to splitter with equal stretch
        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(right_widget)
        
        # Set initial splitter sizes to equal (50/50 split)
        self.splitter.setSizes([600, 600])
        
        # Allow collapsing of either side
        self.splitter.setCollapsible(0, True)  # Left side can be collapsed
        self.splitter.setCollapsible(1, True)  # Right side can be collapsed
        
    def connect_signals(self):
        """Connect signals between widgets."""
        # Connect instrument selection changes to update adapter dropdown
        if hasattr(self.instrument_selector, 'tree'):
            self.instrument_selector.tree.itemChanged.connect(self.update_adapter_instrument_list)
        
    def update_adapter_instrument_list(self):
        """Update the instrument dropdown list in adapter manager based on selected instruments."""
        # Get selected instruments from the right side
        selected_instruments = self.instrument_selector.get_selected_classes()
        
        # Flatten the instrument names from the nested dictionary
        instrument_names = []
        self._extract_instrument_names(selected_instruments, instrument_names)
        
        # Only use selected instruments (no default instruments)
        # If no instruments are selected, provide an empty list or a placeholder
        if not instrument_names:
            instrument_names = ["No instruments selected"]
        
        # Update the adapter manager's instrument list
        self.adapter_manager.instrument_names = instrument_names
        
        # Update all existing dropdown boxes in the adapter table
        for row in range(self.adapter_manager.table.rowCount()):
            combo_widget = self.adapter_manager.table.cellWidget(row, 1)  # Instrument column
            if combo_widget and isinstance(combo_widget, QtWidgets.QComboBox):
                combo = combo_widget
                current_text = combo.currentText()
                combo.clear()
                combo.addItems(instrument_names)
                # Try to restore previous selection
                index = combo.findText(current_text)
                if index >= 0:
                    combo.setCurrentIndex(index)
    
    def _extract_instrument_names(self, instruments_dict, names_list):
        """Recursively extract instrument names from nested dictionary."""
        for key, value in instruments_dict.items():
            if isinstance(value, dict):
                # It's a nested dictionary (folder)
                self._extract_instrument_names(value, names_list)
            else:
                # It's an instrument class - try to get the .name property
                try:
                    if hasattr(value, 'name') and value.name:
                        names_list.append(value.name)
                    else:
                        # Fallback to class name if no .name property
                        names_list.append(key)
                except Exception:
                    # If any error occurs, fallback to class name
                    names_list.append(key)
    
    def get_data(self) -> dict:
        """Get data from both widgets.
        
        Returns:
            Dictionary containing:
                - 'adapters': Adapter manager data
                - 'instruments': Selected instrument classes
        """
        # Get adapter data
        adapter_data = []
        for row in range(self.adapter_manager.table.rowCount()):
            adapter_item = self.adapter_manager.table.item(row, 0)
            instrument_combo_widget = self.adapter_manager.table.cellWidget(row, 1)
            nickname_item = self.adapter_manager.table.item(row, 2)  # Column 2 is now Nickname
            
            if adapter_item and instrument_combo_widget and isinstance(instrument_combo_widget, QtWidgets.QComboBox):
                adapter_data.append({
                    'adapter': adapter_item.text(),
                    'instrument': instrument_combo_widget.currentText(),
                    'nickname': nickname_item.text() if nickname_item else ""
                })
        
        # Get instrument selection data
        instrument_data = self.instrument_selector.get_selected_classes()
        
        return {
            'adapters': adapter_data,
            'instruments': instrument_data
        }
    
    def set_data(self, data: dict):
        """Set data for both widgets.
        
        Args:
            data: Dictionary containing adapters and instruments data
        """
        if 'instruments' in data:
            # Set instrument selections first
            self.instrument_selector.update_selections_from_dict(data['instruments'])
            # Update adapter instrument list
            self.update_adapter_instrument_list()
        
        if 'adapters' in data:
            # Set adapter data
            for adapter_info in data['adapters']:
                # Add row to adapter manager
                self.adapter_manager.add_row(
                    adapter_info.get('adapter', ''),
                    adapter_info.get('instrument', ''),
                    adapter_info.get('nickname', '')
                )


def main():
    """Test the InstrumentsPage widget."""
    app = QtWidgets.QApplication(sys.argv)
    
    # Create main window
    main_window = QtWidgets.QMainWindow()
    main_window.setWindowTitle("Instruments Page Test")
    main_window.resize(1200, 800)
    
    # Create instruments page
    instruments_page = InstrumentsPage()
    main_window.setCentralWidget(instruments_page)
    
    main_window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
