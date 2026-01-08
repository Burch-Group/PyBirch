import sys
from PySide6 import QtCore, QtWidgets, QtGui
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

# Import required widgets
from GUI.widgets.adapter_autoload import InstrumentManager
from GUI.widgets.instrument_autoload import InstrumentAutoLoadWidget
from GUI.widgets.instrument_config_manager import get_config_manager
from GUI.theme import Theme


class InstrumentsPage(QtWidgets.QWidget):
    """
    Instruments page widget that combines:
    - Adapter autoload widget on the left
    - Instrument autoload widget on the right
    - Dynamic instrument list synchronization
    - Automatic configuration persistence
    """
    
    # Signal emitted when configuration changes (for auto-save)
    config_changed = QtCore.Signal()
    
    def __init__(self, parent=None, auto_load=True):
        super().__init__(parent)
        self.config_manager = get_config_manager()
        self._auto_save_enabled = True
        self._loading_config = False  # Prevent save during load
        
        self.init_ui()
        self.connect_signals()
        
        # Load saved configuration if auto_load is enabled
        if auto_load:
            QtCore.QTimer.singleShot(100, self.load_saved_config)
    
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
        adapter_title.setStyleSheet(Theme.section_title_style())
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
        instrument_title.setStyleSheet(Theme.section_title_style())
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
            # Also connect for auto-save
            self.instrument_selector.tree.itemChanged.connect(self._schedule_auto_save)
        
        # Connect adapter table changes for auto-save
        self.adapter_manager.table.itemChanged.connect(self._schedule_auto_save)
        
        # Override the refresh method to prevent interference during refresh
        if hasattr(self.instrument_selector, 'refresh_classes'):
            original_refresh = self.instrument_selector.refresh_classes
            
            def safe_refresh():
                # Temporarily disconnect the signal during refresh
                if hasattr(self.instrument_selector, 'tree'):
                    try:
                        self.instrument_selector.tree.itemChanged.disconnect(self.update_adapter_instrument_list)
                        self.instrument_selector.tree.itemChanged.disconnect(self._schedule_auto_save)
                    except RuntimeError:
                        pass  # Signal wasn't connected
                
                # Perform the refresh
                original_refresh()
                
                # Reconnect the signal after refresh and update once
                if hasattr(self.instrument_selector, 'tree'):
                    self.instrument_selector.tree.itemChanged.connect(self.update_adapter_instrument_list)
                    self.instrument_selector.tree.itemChanged.connect(self._schedule_auto_save)
                
                # Update adapter list once after refresh is complete
                self.update_adapter_instrument_list()
            
            self.instrument_selector.refresh_classes = safe_refresh
    
    def _schedule_auto_save(self):
        """Schedule an auto-save operation (debounced)."""
        if not self._auto_save_enabled or self._loading_config:
            return
        
        # Use a timer to debounce rapid changes
        if not hasattr(self, '_save_timer'):
            self._save_timer = QtCore.QTimer(self)
            self._save_timer.setSingleShot(True)
            self._save_timer.timeout.connect(self._do_auto_save)
        
        # Reset timer - save will happen 500ms after last change
        self._save_timer.start(500)
    
    def _do_auto_save(self):
        """Perform the actual auto-save."""
        if self._loading_config:
            return
        self.save_config()
        self.config_changed.emit()
        
    def update_adapter_instrument_list(self):
        """Update the instrument dropdown list in adapter manager based on selected instruments."""
        # Get selected instruments from the right side
        selected_instruments = self.instrument_selector.get_selected_classes()
        
        # Flatten the instrument names from the nested dictionary
        instrument_names = []
        instrument_classes = []
        self._extract_instrument_names_and_classes(selected_instruments, instrument_names, instrument_classes)
        
        # Only use selected instruments (no default instruments)
        # If no instruments are selected, provide an empty list or a placeholder
        if not instrument_names:
            instrument_names = ["No instruments selected"]
            instrument_classes = []
        
        # Update the adapter manager's instrument list and classes
        self.adapter_manager.instrument_names = instrument_names
        self.adapter_manager.instrument_classes = instrument_classes  # Pass the actual classes for autopair
        
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
    
    def _extract_instrument_names_and_classes(self, instruments_dict, names_list, classes_list):
        """Recursively extract instrument names and classes from nested dictionary."""
        for key, value in instruments_dict.items():
            if isinstance(value, dict):
                # It's a nested dictionary (folder)
                self._extract_instrument_names_and_classes(value, names_list, classes_list)
            else:
                # It's an instrument class - try to get the .name property
                try:
                    if hasattr(value, 'name') and value.name:
                        names_list.append(value.name)
                    else:
                        # Fallback to class name if no .name property
                        names_list.append(key)
                    
                    # Add the actual class to the classes list for autopair functionality
                    classes_list.append(value)
                except Exception:
                    # If any error occurs, fallback to class name
                    names_list.append(key)
                    classes_list.append(value)
    
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

    def serialize(self) -> dict:
        """Serialize the entire instruments page data to a dictionary."""
        return {
            'adapter_manager': self.adapter_manager.serialize(),
            'instrument_selector': self.instrument_selector.serialize(),
            'splitter_sizes': self.splitter.sizes()
        }
    
    def deserialize(self, data: dict):
        """Deserialize and restore instruments page data from a dictionary."""
        # Restore instrument selector first (right panel)
        if 'instrument_selector' in data:
            self.instrument_selector.deserialize(data['instrument_selector'])
            # Update adapter instrument list after restoring selections
            self.update_adapter_instrument_list()
        
        # Restore adapter manager (left panel)
        if 'adapter_manager' in data:
            self.adapter_manager.deserialize(data['adapter_manager'])
        
        # Restore splitter sizes
        if 'splitter_sizes' in data:
            self.splitter.setSizes(data['splitter_sizes'])
    
    def save_config(self) -> bool:
        """Save current configuration to persistent storage.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            data = self.serialize()
            return self.config_manager.save_config(data)
        except Exception as e:
            print(f"Error saving instrument config: {e}")
            return False
    
    def load_saved_config(self) -> bool:
        """Load configuration from persistent storage.
        
        Returns:
            True if configuration was loaded, False if no config exists or error
        """
        self._loading_config = True
        try:
            data = self.config_manager.load_config()
            if data:
                self.deserialize(data)
                print(f"Loaded instrument configuration from {self.config_manager.config_path}")
                return True
            return False
        except Exception as e:
            print(f"Error loading instrument config: {e}")
            return False
        finally:
            self._loading_config = False
    
    def reset_config(self):
        """Reset configuration to defaults and delete saved config."""
        self._loading_config = True
        try:
            # Delete saved config
            self.config_manager.delete_config()
            
            # Clear adapter manager
            self.adapter_manager.table.setRowCount(0)
            self.adapter_manager.load_adapters()
            
            # Reset instrument selector
            self.instrument_selector.populate_tree()
            
            # Reset splitter
            self.splitter.setSizes([600, 600])
            
            print("Instrument configuration reset to defaults")
        finally:
            self._loading_config = False
    
    def set_auto_save(self, enabled: bool):
        """Enable or disable auto-save functionality."""
        self._auto_save_enabled = enabled
    
    def set_database_service(self, db_service):
        """Set the database service for loading database-stored instruments.
        
        Args:
            db_service: DatabaseService instance or None
        """
        # Pass to the instrument selector widget
        if hasattr(self.instrument_selector, 'set_database_service'):
            self.instrument_selector.set_database_service(db_service)


def main():
    """Test the InstrumentsPage widget."""
    from GUI.theme import apply_theme
    
    app = QtWidgets.QApplication(sys.argv)
    apply_theme(app)
    
    # Create main window
    main_window = QtWidgets.QMainWindow()
    main_window.setWindowTitle("Instruments Page Test")
    main_window.resize(1200, 800)
    
    # Create instruments page (with auto-load enabled by default)
    instruments_page = InstrumentsPage()
    main_window.setCentralWidget(instruments_page)
    
    main_window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
