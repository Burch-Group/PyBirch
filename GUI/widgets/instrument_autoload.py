# type: ignore
import sys, inspect
from pathlib import Path
import os
import pickle
import logging
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from pybirch.scan.measurements import Measurement, VisaMeasurement
from pybirch.scan.movements import Movement, VisaMovement
from PySide6 import QtCore, QtWidgets, QtGui
from shiboken6 import isValid

logger = logging.getLogger(__name__)

# Import theme
try:
    from GUI.theme import Theme
except ImportError:
    try:
        from theme import Theme
    except ImportError:
        Theme = None

def get_classes_from_file(file_path: str, acceptable_class_types: tuple = (type,)) -> list[tuple[str, type]]:
    """Return a list of class names defined in the specified module."""
    module_name = Path(file_path).stem
    if module_name not in sys.modules:
        sys.path.append(str(Path(file_path).parent))
        __import__(module_name)
    all_classes = [(cls_name, cls_obj) for cls_name, cls_obj in inspect.getmembers(sys.modules[module_name]) if inspect.isclass(cls_obj)]
    filtered_classes = [(cls_name, cls_obj) for cls_name, cls_obj in all_classes if issubclass(cls_obj, acceptable_class_types) and (cls_obj not in acceptable_class_types)]
    return filtered_classes

def get_classes_from_directory(directory: str, acceptable_class_types: tuple = (type,)) -> dict[str, list[tuple[str, type]]]:
    """Return a dictionary of class names defined in all modules within the specified directory."""
    directory_name = os.path.basename(directory)
    classes_dict = {}
    for file in os.listdir(directory):
        if file.endswith(".py") and not file.startswith("__"):
            file_path = os.path.join(directory, file)
            classes = get_classes_from_file(file_path, acceptable_class_types)
            if classes:
                classes_dict.setdefault(directory_name, []).extend(classes)

    for subdir in os.listdir(directory):

        subdir_path = os.path.join(directory, subdir)
        if os.path.isdir(subdir_path) and not subdir.startswith("__"):
            subdir_classes = get_classes_from_directory(subdir_path, acceptable_class_types)
            if subdir_classes:
                classes_dict[subdir] = subdir_classes

    return classes_dict

class InstrumentAutoLoadWidget(QtWidgets.QWidget):
    """
    A widget to automatically load and display available Measurement and Movement classes
    from the specified directory and database. The classes are displayed in a tree structure, 
    with selectable checkboxes on the left side, and a button to refresh the list.
    
    Now supports loading instrument definitions from the database via InstrumentFactory.
    Database instruments are shown under a "📦 Database Instruments" section.
    
    Auto-discovery: When "Show bound only" is enabled, only shows database instruments
    that are bound to this computer (via ComputerBinding) or marked as public.
    """
    def __init__(self, directory: str, acceptable_class_types: tuple = (Measurement, Movement, VisaMeasurement, VisaMovement), 
                 db_service=None, enable_database: bool = True, filter_by_computer: bool = False):
        super().__init__()
        self.directory = directory
        self.pybirch_classes = get_classes_from_directory(self.directory, acceptable_class_types)
        self.acceptable_class_types = acceptable_class_types
        self.db_service = db_service
        self.enable_database = enable_database
        self._instrument_factory = None
        self._database_classes = {}  # Cache of database instrument classes
        self._filter_by_computer = filter_by_computer  # Auto-discovery filter
        self._computer_info = None  # Cache computer info
        
        # Get computer info for auto-discovery filtering
        self._load_computer_info()
        
        # Load database instruments if enabled
        if self.enable_database:
            self._load_database_instruments()
        
        self.init_ui()
        self.populate_tree()
        self.connect_signals()
        self.setWindowTitle("Instrument Auto-Loader")
        self.setWindowIcon(QtGui.QIcon.fromTheme("folder"))
        self.resize(400, 500)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        # Styling handled by global theme
    
    def _load_computer_info(self):
        """Load identifying information about this computer for auto-discovery."""
        try:
            from pybirch.Instruments.factory import get_computer_info
            self._computer_info = get_computer_info()
            logger.debug(f"Computer info: {self._computer_info.get('computer_name', 'unknown')}")
        except Exception as e:
            logger.warning(f"Could not get computer info: {e}")
            self._computer_info = {'computer_name': 'unknown', 'computer_id': '', 'username': ''}
    
    def _load_database_instruments(self):
        """Load instrument definitions from the database using InstrumentFactory.
        
        If _filter_by_computer is True, only loads definitions that:
        - Have an instrument instance bound to this computer, OR
        - Are marked as public (is_public=True)
        """
        try:
            from pybirch.Instruments.factory import InstrumentFactory
            
            # Get or create the factory
            if self._instrument_factory is None:
                self._instrument_factory = InstrumentFactory(self.db_service)
            
            # Get all definitions from database
            definitions = self._instrument_factory.get_available_definitions()
            
            # Filter by computer binding if enabled
            allowed_definition_ids = None
            if self._filter_by_computer and self.db_service and self._computer_info:
                computer_name = self._computer_info.get('computer_name', '')
                if computer_name:
                    allowed_definition_ids = set(
                        self.db_service.get_definition_ids_for_computer(
                            computer_name=computer_name,
                            include_public=True  # Always include public definitions
                        )
                    )
                    logger.debug(f"Auto-discovery: {len(allowed_definition_ids)} definitions for computer '{computer_name}'")
            
            # Organize by category/type
            self._database_classes = {
                'measurement': [],
                'movement': []
            }
            
            for defn in definitions:
                # Skip if filtering by computer and this definition isn't allowed
                if allowed_definition_ids is not None and defn.get('id') not in allowed_definition_ids:
                    logger.debug(f"Skipping {defn.get('name')} - not bound to this computer")
                    continue
                
                try:
                    # Create the class from the definition
                    cls = self._instrument_factory.create_class_from_definition(defn)
                    if cls:
                        instrument_type = defn.get('instrument_type', 'measurement')
                        display_name = defn.get('display_name', defn['name'])
                        self._database_classes[instrument_type].append((defn['name'], cls, defn))
                        logger.debug(f"Loaded database instrument: {defn['name']} ({instrument_type})")
                except Exception as e:
                    logger.warning(f"Failed to create class for {defn.get('name', 'unknown')}: {e}")
            
            filter_status = "filtered" if self._filter_by_computer else "all"
            logger.info(f"Loaded {sum(len(v) for v in self._database_classes.values())} instruments from database ({filter_status})")
            
        except ImportError as e:
            logger.warning(f"Could not import InstrumentFactory: {e}")
            self._database_classes = {}
        except Exception as e:
            logger.warning(f"Failed to load database instruments: {e}")
            self._database_classes = {}
    
    def set_database_service(self, db_service):
        """Set the database service and reload database instruments."""
        self.db_service = db_service
        if self._instrument_factory:
            self._instrument_factory.db_service = db_service
        self._load_database_instruments()
        self.refresh_classes()
    
    @property
    def filter_by_computer(self) -> bool:
        """Get the current auto-discovery filter setting."""
        return self._filter_by_computer
    
    @filter_by_computer.setter
    def filter_by_computer(self, value: bool):
        """Set the auto-discovery filter and refresh the list."""
        if self._filter_by_computer != value:
            self._filter_by_computer = value
            if hasattr(self, 'filter_checkbox'):
                self.filter_checkbox.setChecked(value)
            else:
                # If checkbox doesn't exist yet, just update the internal state
                self._load_database_instruments()
                if hasattr(self, 'tree'):
                    self.populate_tree()
    
    @property
    def computer_info(self) -> dict:
        """Get the current computer identification info.
        
        Returns:
            Dictionary with 'computer_name' (hostname), 'computer_id' (MAC), 'username'
        """
        return self._computer_info.copy() if self._computer_info else {}
    
    def init_ui(self):
        """Initialize the user interface components."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Create the tree widget
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectItems)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        
        # Enable smooth animations and optimize performance
        self.tree.setAnimated(True)  # Enable smooth expand/collapse animations
        self.tree.setUniformRowHeights(True)  # Improves performance when all rows have same height
        self.tree.setIndentation(20)  # Set consistent indentation
        
        # Track if we're in the middle of programmatic updates to avoid recursion
        self._updating_items = False
        
        layout.addWidget(self.tree)

        # Ensure all objects are collapsed initially
        self.tree.collapseAll()

        # Create filter checkbox for auto-discovery (only show if database is enabled)
        if self.enable_database:
            filter_container = QtWidgets.QWidget()
            filter_layout = QtWidgets.QHBoxLayout(filter_container)
            filter_layout.setContentsMargins(0, 4, 0, 4)
            filter_layout.setSpacing(8)
            
            self.filter_checkbox = QtWidgets.QCheckBox("Show bound instruments only")
            self.filter_checkbox.setChecked(self._filter_by_computer)
            computer_name = self._computer_info.get('computer_name', 'unknown') if self._computer_info else 'unknown'
            self.filter_checkbox.setToolTip(
                f"When checked, only show database instruments bound to this computer ({computer_name}) "
                "or marked as public. Uncheck to see all database instruments."
            )
            filter_layout.addWidget(self.filter_checkbox)
            filter_layout.addStretch()
            
            layout.addWidget(filter_container)

        # Create the refresh button
        self.refresh_button = QtWidgets.QPushButton("Refresh")
        self.refresh_button.setToolTip("Refresh the list of available classes")
        self.refresh_button.setFixedSize(100, 32)
        if Theme:
            self.refresh_button.setStyleSheet(Theme.primary_button_style())
        else:
            self.refresh_button.setStyleSheet("""
                QPushButton {
                    border: none;
                    border-radius: 4px;
                    background-color: #0078d7;
                    color: white;
                }
                QPushButton:hover {
                    background-color: #0056a1;
                }
                QPushButton:pressed {
                    background-color: #003f6b;
                }
            """)

        # Create the 'control' button
        self.open_front_panel_button = QtWidgets.QPushButton("Control")
        self.open_front_panel_button.setToolTip("Open the instrument front panel")
        self.open_front_panel_button.setFixedSize(100, 32)
        if Theme:
            self.open_front_panel_button.setStyleSheet(Theme.primary_button_style())
        else:
            self.open_front_panel_button.setStyleSheet("""
                QPushButton {
                    border: none;
                    border-radius: 4px;
                    background-color: #0078d7;
                    color: white;
                }
                QPushButton:hover {
                    background-color: #0056a1;
                }
                QPushButton:pressed {
                    background-color: #003f6b;
                }
            """)

        # Create the 'open instrument settings panel' button
        self.open_settings_panel_button = QtWidgets.QPushButton("Settings")
        self.open_settings_panel_button.setToolTip("Open the instrument settings panel")
        self.open_settings_panel_button.setFixedSize(100, 32)
        if Theme:
            self.open_settings_panel_button.setStyleSheet(Theme.primary_button_style())
        else:
            self.open_settings_panel_button.setStyleSheet("""
                QPushButton {
                    border: none;
                    border-radius: 4px;
                    background-color: #0078d7;
                    color: white;
                }
                QPushButton:hover {
                    background-color: #0056a1;
                }
                QPushButton:pressed {
                    background-color: #003f6b;
                }
            """)

        # Button container
        button_container = QtWidgets.QWidget()
        button_layout = QtWidgets.QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(4)
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.open_front_panel_button)
        button_layout.addWidget(self.open_settings_panel_button)
        button_layout.addStretch()
        layout.addWidget(button_container)


    def populate_tree(self, parent: QtWidgets.QTreeWidgetItem = None):
        """Populate the tree widget with the available classes."""
        self.tree.clear()
        root = self.tree.invisibleRootItem()
        
        def add_items(parent_item: QtWidgets.QTreeWidgetItem, classes_dict: dict[str, list[tuple[str, type]]]):
            for key, value in classes_dict.items():
                if isinstance(value, dict):
                    folder_item = QtWidgets.QTreeWidgetItem(parent_item, [key])
                    folder_item.setFlags(folder_item.flags() | QtCore.Qt.ItemIsUserCheckable)
                    folder_item.setCheckState(0, QtCore.Qt.Unchecked)
                    add_items(folder_item, value)
                else:
                    for cls_name, cls_obj in value:
                        class_item = QtWidgets.QTreeWidgetItem(parent_item, [cls_name])
                        class_item.setFlags(class_item.flags() | QtCore.Qt.ItemIsUserCheckable)
                        class_item.setCheckState(0, QtCore.Qt.Unchecked)
                        class_item.setData(0, QtCore.Qt.UserRole, cls_obj)

        add_items(root, self.pybirch_classes)
        
        # Add database instruments section if there are any
        if self._database_classes and any(self._database_classes.values()):
            db_folder = QtWidgets.QTreeWidgetItem(root, ["📦 Database Instruments"])
            db_folder.setFlags(db_folder.flags() | QtCore.Qt.ItemIsUserCheckable)
            db_folder.setCheckState(0, QtCore.Qt.Unchecked)
            db_folder.setToolTip(0, "Instruments loaded from database")
            
            # Add measurement instruments
            if self._database_classes.get('measurement'):
                measurement_folder = QtWidgets.QTreeWidgetItem(db_folder, ["Measurements"])
                measurement_folder.setFlags(measurement_folder.flags() | QtCore.Qt.ItemIsUserCheckable)
                measurement_folder.setCheckState(0, QtCore.Qt.Unchecked)
                
                for cls_name, cls_obj, defn in self._database_classes['measurement']:
                    class_item = QtWidgets.QTreeWidgetItem(measurement_folder, [cls_name])
                    class_item.setFlags(class_item.flags() | QtCore.Qt.ItemIsUserCheckable)
                    class_item.setCheckState(0, QtCore.Qt.Unchecked)
                    class_item.setData(0, QtCore.Qt.UserRole, cls_obj)
                    class_item.setData(0, QtCore.Qt.UserRole + 1, defn)  # Store definition for reference
                    class_item.setToolTip(0, f"Database ID: {defn.get('id', 'N/A')}\nBase: {defn.get('base_class', 'N/A')}")
            
            # Add movement instruments
            if self._database_classes.get('movement'):
                movement_folder = QtWidgets.QTreeWidgetItem(db_folder, ["Movements"])
                movement_folder.setFlags(movement_folder.flags() | QtCore.Qt.ItemIsUserCheckable)
                movement_folder.setCheckState(0, QtCore.Qt.Unchecked)
                
                for cls_name, cls_obj, defn in self._database_classes['movement']:
                    class_item = QtWidgets.QTreeWidgetItem(movement_folder, [cls_name])
                    class_item.setFlags(class_item.flags() | QtCore.Qt.ItemIsUserCheckable)
                    class_item.setCheckState(0, QtCore.Qt.Unchecked)
                    class_item.setData(0, QtCore.Qt.UserRole, cls_obj)
                    class_item.setData(0, QtCore.Qt.UserRole + 1, defn)  # Store definition for reference
                    class_item.setToolTip(0, f"Database ID: {defn.get('id', 'N/A')}\nBase: {defn.get('base_class', 'N/A')}")
            
            # Expand the database folder
            self.tree.expandItem(db_folder)
        
        # Expand just the top-level items
        for i in range(root.childCount()):
            top_level_item = root.child(i)
            if top_level_item:
                self.tree.expandItem(top_level_item)

    def connect_signals(self):
        """Connect signals to their respective slots."""
        self.refresh_button.clicked.connect(self.refresh_classes)
        self.tree.itemChanged.connect(self.handle_item_changed)
        self.open_front_panel_button.clicked.connect(self.open_front_panel)
        self.open_settings_panel_button.clicked.connect(self.open_settings)
        
        # Connect filter checkbox if database is enabled
        if self.enable_database and hasattr(self, 'filter_checkbox'):
            self.filter_checkbox.stateChanged.connect(self._on_filter_changed)
    
    def _on_filter_changed(self, state):
        """Handle filter checkbox state change."""
        self._filter_by_computer = (state == QtCore.Qt.Checked)
        logger.debug(f"Auto-discovery filter changed: {self._filter_by_computer}")
        
        # Reload database instruments with new filter setting
        self._load_database_instruments()
        self.populate_tree()

    def open_settings(self):
        """Open the instrument front panel using measurement.settings_UI() if available."""
        selection_model = self.tree.selectedItems()
        if not selection_model:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Please select a class to open its settings panel.")
            return
        selected_item = selection_model[0]
        cls_obj = selected_item.data(0, QtCore.Qt.UserRole)
        if cls_obj and hasattr(cls_obj, 'settings_UI') and callable(getattr(cls_obj, 'settings_UI')):
            try:
                instance = cls_obj()
                settings = instance.settings_UI()
                instance.settings = settings
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to open settings panel: {e}")
        else:
            QtWidgets.QMessageBox.information(self, "No Settings Panel", "The selected class does not have a settings panel.")
        
    def open_front_panel(self):
        """Open the instrument front panel using measurement.front_panel() if available."""
        selection_model = self.tree.selectedItems()
        if not selection_model:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Please select a class to open its front panel.")
            return
        selected_item = selection_model[0]
        cls_obj = selected_item.data(0, QtCore.Qt.UserRole)
        if cls_obj and hasattr(cls_obj, 'front_panel') and callable(getattr(cls_obj, 'front_panel')):
            try:
                instance = cls_obj()
                instance.front_panel()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to open front panel: {e}")
        else:
            QtWidgets.QMessageBox.information(self, "No Front Panel", "The selected class does not have a front panel.")
        


    def refresh_classes(self):
        """Refresh the list of available classes from the directory and database while preserving checked items."""
        # Save current selections before refreshing
        current_selections = self.get_selected_classes()
        
        # Refresh the classes from directory
        self.pybirch_classes = get_classes_from_directory(self.directory, self.acceptable_class_types)
        
        # Refresh database instruments if enabled
        if self.enable_database:
            self._load_database_instruments()
        
        # Repopulate the tree
        self.populate_tree()
        
        # Restore selections for items that are still available
        if current_selections:
            self.update_selections_from_dict(current_selections)
    
    def handle_item_changed(self, item: QtWidgets.QTreeWidgetItem):
        """Handle changes in item check states with performance optimization"""
        # Skip processing if we're already updating items (prevents recursion/lag)
        if self._updating_items:
            return
            
        # Defer heavy operations to avoid blocking expand/collapse animations
        QtCore.QTimer.singleShot(0, lambda: self._process_item_change(item))
    
    def _process_item_change(self, item: QtWidgets.QTreeWidgetItem):
        """Process item changes with batch updates for better performance"""
        # Check if item is valid (not deleted by tree.clear())
        if not item or not isValid(item):
            return
            
        self._updating_items = True
        try:
            # Batch update child/parent states
            if item.childCount() > 0:
                # If the item is a folder, update all child items
                state = item.checkState(0)
                if state != QtCore.Qt.PartiallyChecked:
                    self._update_children_state(item, state)
            
            if item.parent() is not None:
                # If the item is a class, update the parent folder's state
                self._update_parent_state(item)
        finally:
            self._updating_items = False
    
    def _update_children_state(self, parent_item: QtWidgets.QTreeWidgetItem, state: QtCore.Qt.CheckState):
        """Efficiently update all children states"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if child and child.checkState(0) != state:
                child.setCheckState(0, state)
    
    def _update_parent_state(self, child_item: QtWidgets.QTreeWidgetItem):
        """Efficiently update parent state based on children"""
        parent = child_item.parent()
        if parent:
            checked_count = sum(1 for i in range(parent.childCount()) 
                              if parent.child(i).checkState(0) == QtCore.Qt.Checked)
            
            if checked_count == parent.childCount():
                if parent.checkState(0) != QtCore.Qt.Checked:
                    parent.setCheckState(0, QtCore.Qt.Checked)
            elif checked_count == 0:
                if parent.checkState(0) != QtCore.Qt.Unchecked:
                    parent.setCheckState(0, QtCore.Qt.Unchecked)
            else:
                if parent.checkState(0) != QtCore.Qt.PartiallyChecked:
                    parent.setCheckState(0, QtCore.Qt.PartiallyChecked)


    def get_selected_classes(self) -> dict[str, type]:
        """Return a dictionary of selected classes and folder states."""
        selected_classes = {}
        folder_states = {}

        def traverse(item: QtWidgets.QTreeWidgetItem, current_dict: dict, current_folder_states: dict, path: str = ""):
            for i in range(item.childCount()):
                child = item.child(i)
                child_path = f"{path}/{child.text(0)}" if path else child.text(0)
                
                if child.childCount() > 0:
                    # It's a folder - save its state
                    current_folder_states[child_path] = child.checkState(0)
                    folder_dict = {}
                    folder_states_dict = {}
                    traverse(child, folder_dict, folder_states_dict, child_path)
                    if folder_dict or any(state != QtCore.Qt.Unchecked for state in folder_states_dict.values()):
                        current_dict[child.text(0)] = folder_dict
                        current_folder_states.update(folder_states_dict)
                else:
                    # It's a class
                    if child.checkState(0) == QtCore.Qt.Checked:
                        cls_obj = child.data(0, QtCore.Qt.UserRole)
                        if cls_obj:
                            current_dict[child.text(0)] = cls_obj

        root = self.tree.invisibleRootItem()
        traverse(root, selected_classes, folder_states)
        
        # Store folder states in the result
        if hasattr(self, '_folder_states'):
            self._folder_states = folder_states
        else:
            setattr(self, '_folder_states', folder_states)
            
        return selected_classes
        
    def save_selected_classes(self, filepath: str):
        """Save the selected classes to a file."""
        selected_classes = self.get_selected_classes()
        with open(filepath, 'wb') as f:
            pickle.dump(selected_classes, f)
    
    def load_selected_classes(self, filepath: str) -> dict[str, type]:
        """Load selected classes from a file."""
        with open(filepath, 'rb') as f:
            selected_classes = pickle.load(f)
        return selected_classes

    def _serialize_selections(self, selections: dict) -> dict:
        """Convert selections dict to JSON-serializable format (class names instead of objects)."""
        result = {}
        for key, value in selections.items():
            if isinstance(value, dict):
                result[key] = self._serialize_selections(value)
            elif isinstance(value, type):
                # Store class name and module for later restoration
                result[key] = {
                    '__class_name__': value.__name__,
                    '__module__': getattr(value, '__module__', '')
                }
            else:
                result[key] = str(value)
        return result
    
    def _deserialize_selections(self, data: dict) -> dict:
        """Convert JSON selections back to dict with class references."""
        result = {}
        for key, value in data.items():
            if isinstance(value, dict):
                if '__class_name__' in value:
                    # This is a serialized class reference - just store the class name
                    # The actual matching will be done by update_selections_from_dict
                    result[key] = value['__class_name__']
                else:
                    result[key] = self._deserialize_selections(value)
            else:
                result[key] = value
        return result

    def serialize(self) -> dict:
        """Serialize the instrument autoload widget data to a dictionary."""
        selected_classes = self.get_selected_classes()
        folder_states = getattr(self, '_folder_states', {})
        
        # Convert folder states to JSON-serializable format
        json_folder_states = {}
        for path, state in folder_states.items():
            json_folder_states[path] = state.value if hasattr(state, 'value') else int(state)
        
        return {
            'selected_classes': self._serialize_selections(selected_classes),
            'folder_states': json_folder_states,
            'directory': self.directory,
            'acceptable_class_types': [cls.__name__ for cls in self.acceptable_class_types]
        }
    
    def deserialize(self, data: dict):
        """Deserialize and restore instrument autoload widget data from a dictionary."""
        # Restore folder states (convert back to Qt CheckState)
        if 'folder_states' in data:
            restored_states = {}
            for path, state_value in data['folder_states'].items():
                if state_value == 2:
                    restored_states[path] = QtCore.Qt.Checked
                elif state_value == 1:
                    restored_states[path] = QtCore.Qt.PartiallyChecked
                else:
                    restored_states[path] = QtCore.Qt.Unchecked
            self._folder_states = restored_states
        
        # Restore selected classes
        if 'selected_classes' in data:
            selections = self._deserialize_selections(data['selected_classes'])
            self.update_selections_from_dict_by_name(selections)

    def update_selections_from_dict(self, selections: dict[str, type]) -> dict[str, type]:
        """Update the tree selections based on a dictionary of selections. Return a list of
        the selections objects not found in the tree."""

        # Get the stored folder states if available
        folder_states = getattr(self, '_folder_states', {})

        def traverse(item: QtWidgets.QTreeWidgetItem, selections_dict: dict, path: str = ""):
            for i in range(item.childCount()):
                child = item.child(i)
                child_path = f"{path}/{child.text(0)}" if path else child.text(0)
                
                if child.childCount() > 0:
                    # It's a folder
                    if child.text(0) in selections_dict:
                        traverse(child, selections_dict[child.text(0)], child_path)
                    
                    # Restore explicit folder state if it was saved
                    if child_path in folder_states:
                        child.setCheckState(0, folder_states[child_path])
                    else:
                        # Fall back to calculating state based on children
                        checked_count = sum(1 for j in range(child.childCount()) if child.child(j).checkState(0) == QtCore.Qt.Checked)
                        partially_checked_count = sum(1 for j in range(child.childCount()) if child.child(j).checkState(0) == QtCore.Qt.PartiallyChecked)
                        
                        if checked_count == child.childCount() and partially_checked_count == 0:
                            child.setCheckState(0, QtCore.Qt.Checked)
                        elif checked_count == 0 and partially_checked_count == 0:
                            child.setCheckState(0, QtCore.Qt.Unchecked)
                        else:
                            child.setCheckState(0, QtCore.Qt.PartiallyChecked)
                else:
                    # It's a class
                    cls_obj = child.data(0, QtCore.Qt.UserRole)
                    if cls_obj and child.text(0) in selections_dict and selections_dict[child.text(0)] == cls_obj:
                        child.setCheckState(0, QtCore.Qt.Checked)

        root = self.tree.invisibleRootItem()
        traverse(root, selections)

        # Now, find any selections not found in the tree
        not_found = {}
        def find_not_found(selections_dict: dict, current_dict: dict):
            for key, value in selections_dict.items():
                if isinstance(value, dict):
                    if key in current_dict and isinstance(current_dict[key], dict):
                        find_not_found(value, current_dict[key])
                    else:
                        not_found[key] = value
                else:
                    if key not in current_dict or current_dict[key] != value:
                        not_found[key] = value
        find_not_found(selections, self.get_selected_classes())
        
        return not_found
    
    def update_selections_from_dict_by_name(self, selections: dict) -> dict:
        """Update the tree selections based on class names (for JSON deserialization).
        
        This method matches selections by class name string instead of class object reference.
        Used when restoring from JSON where class objects aren't preserved.
        
        Args:
            selections: Dict with structure {folder: {class_name: "ClassName", ...}, ...}
        
        Returns:
            Dict of selections that couldn't be matched in the tree
        """
        # Get the stored folder states if available
        folder_states = getattr(self, '_folder_states', {})
        not_found = {}

        def traverse(item: QtWidgets.QTreeWidgetItem, selections_dict: dict, path: str = ""):
            for i in range(item.childCount()):
                child = item.child(i)
                child_path = f"{path}/{child.text(0)}" if path else child.text(0)
                
                if child.childCount() > 0:
                    # It's a folder
                    if child.text(0) in selections_dict:
                        traverse(child, selections_dict[child.text(0)], child_path)
                    
                    # Restore explicit folder state if it was saved
                    if child_path in folder_states:
                        child.setCheckState(0, folder_states[child_path])
                    else:
                        # Calculate state based on children
                        checked_count = sum(1 for j in range(child.childCount()) 
                                          if child.child(j).checkState(0) == QtCore.Qt.Checked)
                        partially_checked_count = sum(1 for j in range(child.childCount()) 
                                                     if child.child(j).checkState(0) == QtCore.Qt.PartiallyChecked)
                        
                        if checked_count == child.childCount() and partially_checked_count == 0:
                            child.setCheckState(0, QtCore.Qt.Checked)
                        elif checked_count == 0 and partially_checked_count == 0:
                            child.setCheckState(0, QtCore.Qt.Unchecked)
                        else:
                            child.setCheckState(0, QtCore.Qt.PartiallyChecked)
                else:
                    # It's a class - match by name
                    class_name = child.text(0)
                    if class_name in selections_dict:
                        # Check if the selection is a string (class name) or has the name stored
                        selection = selections_dict[class_name]
                        if isinstance(selection, str) and selection == class_name:
                            child.setCheckState(0, QtCore.Qt.Checked)
                        elif isinstance(selection, str):
                            # The value is the class name
                            child.setCheckState(0, QtCore.Qt.Checked)

        root = self.tree.invisibleRootItem()
        traverse(root, selections)
        
        return not_found

# Example usage:
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    directory = os.path.join(os.path.dirname(__file__), '../../pybirch/setups')
    widget = InstrumentAutoLoadWidget(directory)
    widget.show()
    sys.exit(app.exec())
