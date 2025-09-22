# type: ignore
import sys, inspect
from pathlib import Path
import os
import pickle
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from pybirch.scan.measurements import Measurement, VisaMeasurement
from pybirch.scan.movements import Movement, VisaMovement
from PySide6 import QtCore, QtWidgets, QtGui

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
    from the specified directory. The classes are displayed in a tree structure, with selectable
    checkboxes on the left side, and a button to refresh the list.
    """
    def __init__(self, directory: str, acceptable_class_types: tuple = (Measurement, Movement, VisaMeasurement, VisaMovement)):
        super().__init__()
        self.directory = directory
        self.pybirch_classes = get_classes_from_directory(self.directory, acceptable_class_types)
        self.acceptable_class_types = acceptable_class_types
        self.init_ui()
        self.populate_tree()
        self.connect_signals()
        self.setWindowTitle("Instrument Auto-Loader")
        self.setWindowIcon(QtGui.QIcon.fromTheme("folder"))
        self.resize(400, 500)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QTreeWidget::item {
                padding: 4px 8px;
            }
        """)
    
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
        layout.addWidget(self.tree)

        # Ensure all objects are collapsed initially
        self.tree.collapseAll()

        # Create the refresh button
        self.refresh_button = QtWidgets.QPushButton("Refresh")
        self.refresh_button.setToolTip("Refresh the list of available classes")
        self.refresh_button.setFixedSize(100, 32)
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
        """Refresh the list of available classes from the directory."""
        self.pybirch_classes = get_classes_from_directory(self.directory, self.acceptable_class_types)
        self.populate_tree()
    
    def handle_item_changed(self, item: QtWidgets.QTreeWidgetItem):
        """Handle changes in item check states."""
        if item.childCount() > 0:
            # If the item is a folder, update all child items
            state = item.checkState(0)
            if state != QtCore.Qt.PartiallyChecked:
                for i in range(item.childCount()):
                    child = item.child(i)
                    child.setCheckState(0, state)
        if item.parent is not None:
            # If the item is a class, update the parent folder's state
            parent = item.parent()
            if parent:
                checked_count = sum(1 for i in range(parent.childCount()) if parent.child(i).checkState(0) == QtCore.Qt.Checked)
                if checked_count == parent.childCount():
                    parent.setCheckState(0, QtCore.Qt.Checked)
                elif checked_count == 0:
                    parent.setCheckState(0, QtCore.Qt.Unchecked)
                else:
                    parent.setCheckState(0, QtCore.Qt.PartiallyChecked)


    def get_selected_classes(self) -> dict[str, type]:
        """Return a dictionary of selected classes."""
        selected_classes = {}

        def traverse(item: QtWidgets.QTreeWidgetItem, current_dict: dict):
            for i in range(item.childCount()):
                child = item.child(i)
                if child.childCount() > 0:
                    # It's a folder
                    folder_dict = {}
                    traverse(child, folder_dict)
                    if folder_dict:
                        current_dict[child.text(0)] = folder_dict
                else:
                    # It's a class
                    if child.checkState(0) == QtCore.Qt.Checked:
                        cls_obj = child.data(0, QtCore.Qt.UserRole)
                        if cls_obj:
                            current_dict[child.text(0)] = cls_obj

        root = self.tree.invisibleRootItem()
        traverse(root, selected_classes)
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

    def update_selections_from_dict(self, selections: dict[str, type]) -> dict[str, type]:
        """Update the tree selections based on a dictionary of selections. Return a list of
        the selections objects not found in the tree."""

        def traverse(item: QtWidgets.QTreeWidgetItem, selections_dict: dict):
            for i in range(item.childCount()):
                child = item.child(i)
                if child.childCount() > 0:
                    # It's a folder
                    if child.text(0) in selections_dict:
                        traverse(child, selections_dict[child.text(0)])
                        # After traversing children, update parent state
                        checked_count = sum(1 for j in range(child.childCount()) if child.child(j).checkState(0) == QtCore.Qt.Checked)
                        if checked_count == child.childCount():
                            child.setCheckState(0, QtCore.Qt.Checked)
                        elif checked_count == 0:
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

# Example usage:
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    directory = os.path.join(os.path.dirname(__file__), '../../pybirch/setups')
    widget = InstrumentAutoLoadWidget(directory)
    widget.show()
    sys.exit(app.exec())
