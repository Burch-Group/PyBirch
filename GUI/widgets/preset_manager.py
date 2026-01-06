# Copyright (C) 2025
# Preset Manager for PyBirch
"""
Manages presets for queues and scans.
Provides functionality to save, load, and manage up to 5 presets each.
"""

import sys
import os
import json
import pickle
from pathlib import Path
from typing import Optional, Dict, Any, List

sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from PySide6 import QtCore, QtWidgets, QtGui

# Import theme
try:
    from GUI.theme import Theme
except ImportError:
    try:
        from theme import Theme
    except ImportError:
        Theme = None

from pybirch.queue.queue import Queue
from pybirch.scan.scan import Scan


class PresetManager:
    """
    Manages preset storage and retrieval for queues and scans.
    Presets are stored in the config/presets directory.
    """
    
    MAX_PRESETS = 5
    
    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize the preset manager.
        
        Args:
            base_path: Base path for preset storage. Defaults to config/presets.
        """
        if base_path is None:
            # Default to config/presets in the project root
            project_root = Path(__file__).parent.parent.parent
            base_path = project_root / "config" / "presets"
        
        self.base_path = Path(base_path)
        self.queue_path = self.base_path / "queue"
        self.scan_path = self.base_path / "scan"
        self.settings_path = self.base_path / "settings.json"
        
        # Ensure directories exist
        self.queue_path.mkdir(parents=True, exist_ok=True)
        self.scan_path.mkdir(parents=True, exist_ok=True)
        
        # Load settings
        self.settings = self._load_settings()
    
    def _load_settings(self) -> Dict[str, Any]:
        """Load preset settings from file."""
        default_settings = {
            "show_overwrite_warning": True,
            "queue_preset_names": [""] * self.MAX_PRESETS,
            "scan_preset_names": [""] * self.MAX_PRESETS,
        }
        
        if self.settings_path.exists():
            try:
                with open(self.settings_path, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults
                    for key, value in default_settings.items():
                        if key not in loaded:
                            loaded[key] = value
                    return loaded
            except Exception as e:
                print(f"Error loading preset settings: {e}")
        
        return default_settings
    
    def _save_settings(self):
        """Save preset settings to file."""
        try:
            with open(self.settings_path, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving preset settings: {e}")
    
    def get_show_overwrite_warning(self) -> bool:
        """Get whether to show overwrite warning."""
        return self.settings.get("show_overwrite_warning", True)
    
    def set_show_overwrite_warning(self, value: bool):
        """Set whether to show overwrite warning."""
        self.settings["show_overwrite_warning"] = value
        self._save_settings()
    
    # Queue preset methods
    def save_queue_preset(self, index: int, queue: Queue, name: str = "") -> bool:
        """
        Save a queue as a preset.
        
        Args:
            index: Preset slot index (0-4)
            queue: Queue to save
            name: Optional name for the preset
            
        Returns:
            True if successful, False otherwise
        """
        if not 0 <= index < self.MAX_PRESETS:
            return False
        
        try:
            preset_file = self.queue_path / f"preset_{index}.pkl"
            with open(preset_file, 'wb') as f:
                pickle.dump(queue, f)
            
            # Update preset name
            self.settings["queue_preset_names"][index] = name or f"Queue Preset {index + 1}"
            self._save_settings()
            return True
        except Exception as e:
            print(f"Error saving queue preset: {e}")
            return False
    
    def load_queue_preset(self, index: int) -> Optional[Queue]:
        """
        Load a queue preset.
        
        Args:
            index: Preset slot index (0-4)
            
        Returns:
            The loaded Queue or None if not found/error
        """
        if not 0 <= index < self.MAX_PRESETS:
            return None
        
        preset_file = self.queue_path / f"preset_{index}.pkl"
        if not preset_file.exists():
            return None
        
        try:
            with open(preset_file, 'rb') as f:
                queue = pickle.load(f)
                if isinstance(queue, Queue):
                    return queue
        except Exception as e:
            print(f"Error loading queue preset: {e}")
        
        return None
    
    def delete_queue_preset(self, index: int) -> bool:
        """Delete a queue preset."""
        if not 0 <= index < self.MAX_PRESETS:
            return False
        
        preset_file = self.queue_path / f"preset_{index}.pkl"
        try:
            if preset_file.exists():
                preset_file.unlink()
            self.settings["queue_preset_names"][index] = ""
            self._save_settings()
            return True
        except Exception as e:
            print(f"Error deleting queue preset: {e}")
            return False
    
    def get_queue_preset_names(self) -> List[str]:
        """Get list of queue preset names."""
        return self.settings.get("queue_preset_names", [""] * self.MAX_PRESETS)
    
    def queue_preset_exists(self, index: int) -> bool:
        """Check if a queue preset exists."""
        preset_file = self.queue_path / f"preset_{index}.pkl"
        return preset_file.exists()
    
    # Scan preset methods
    def save_scan_preset(self, index: int, scan: Scan, name: str = "") -> bool:
        """
        Save a scan as a preset.
        
        Args:
            index: Preset slot index (0-4)
            scan: Scan to save
            name: Optional name for the preset
            
        Returns:
            True if successful, False otherwise
        """
        if not 0 <= index < self.MAX_PRESETS:
            return False
        
        try:
            preset_file = self.scan_path / f"preset_{index}.pkl"
            with open(preset_file, 'wb') as f:
                pickle.dump(scan, f)
            
            # Update preset name
            self.settings["scan_preset_names"][index] = name or f"Scan Preset {index + 1}"
            self._save_settings()
            return True
        except Exception as e:
            print(f"Error saving scan preset: {e}")
            return False
    
    def load_scan_preset(self, index: int) -> Optional[Scan]:
        """
        Load a scan preset.
        
        Args:
            index: Preset slot index (0-4)
            
        Returns:
            The loaded Scan or None if not found/error
        """
        if not 0 <= index < self.MAX_PRESETS:
            return None
        
        preset_file = self.scan_path / f"preset_{index}.pkl"
        if not preset_file.exists():
            return None
        
        try:
            with open(preset_file, 'rb') as f:
                scan = pickle.load(f)
                if isinstance(scan, Scan):
                    return scan
        except Exception as e:
            print(f"Error loading scan preset: {e}")
        
        return None
    
    def delete_scan_preset(self, index: int) -> bool:
        """Delete a scan preset."""
        if not 0 <= index < self.MAX_PRESETS:
            return False
        
        preset_file = self.scan_path / f"preset_{index}.pkl"
        try:
            if preset_file.exists():
                preset_file.unlink()
            self.settings["scan_preset_names"][index] = ""
            self._save_settings()
            return True
        except Exception as e:
            print(f"Error deleting scan preset: {e}")
            return False
    
    def get_scan_preset_names(self) -> List[str]:
        """Get list of scan preset names."""
        return self.settings.get("scan_preset_names", [""] * self.MAX_PRESETS)
    
    def scan_preset_exists(self, index: int) -> bool:
        """Check if a scan preset exists."""
        preset_file = self.scan_path / f"preset_{index}.pkl"
        return preset_file.exists()


class PresetDialog(QtWidgets.QDialog):
    """
    Dialog for managing queue and scan presets.
    Allows saving, loading, and deleting presets.
    """
    
    # Signals emitted when presets are loaded
    queue_preset_loaded = QtCore.Signal(object)  # Emits Queue
    scan_preset_loaded = QtCore.Signal(object)   # Emits Scan
    
    def __init__(self, parent=None, queue: Optional[Queue] = None, scan: Optional[Scan] = None):
        """
        Initialize the preset dialog.
        
        Args:
            parent: Parent widget
            queue: Current queue (for saving)
            scan: Current scan (for saving)
        """
        super().__init__(parent)
        self.queue = queue
        self.scan = scan
        self.preset_manager = PresetManager()
        
        self.setWindowTitle("Presets")
        self.setMinimumSize(500, 400)
        
        self.init_ui()
        self.refresh_preset_lists()
    
    def init_ui(self):
        """Initialize the user interface."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Tab widget for Queue and Scan presets
        self.tab_widget = QtWidgets.QTabWidget()
        
        # Queue presets tab
        queue_tab = QtWidgets.QWidget()
        queue_layout = QtWidgets.QVBoxLayout(queue_tab)
        queue_layout.setContentsMargins(12, 12, 12, 12)
        
        queue_label = QtWidgets.QLabel("Queue Presets")
        queue_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        queue_layout.addWidget(queue_label)
        
        self.queue_list = QtWidgets.QListWidget()
        self.queue_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        queue_layout.addWidget(self.queue_list)
        
        queue_buttons = QtWidgets.QHBoxLayout()
        self.queue_save_btn = QtWidgets.QPushButton("Save Current Queue")
        self.queue_save_btn.clicked.connect(self.save_queue_preset)
        self.queue_load_btn = QtWidgets.QPushButton("Load Selected")
        self.queue_load_btn.clicked.connect(self.load_queue_preset)
        self.queue_delete_btn = QtWidgets.QPushButton("Delete")
        self.queue_delete_btn.clicked.connect(self.delete_queue_preset)
        self.queue_rename_btn = QtWidgets.QPushButton("Rename")
        self.queue_rename_btn.clicked.connect(self.rename_queue_preset)
        
        queue_buttons.addWidget(self.queue_save_btn)
        queue_buttons.addWidget(self.queue_load_btn)
        queue_buttons.addWidget(self.queue_rename_btn)
        queue_buttons.addWidget(self.queue_delete_btn)
        queue_layout.addLayout(queue_buttons)
        
        self.tab_widget.addTab(queue_tab, "Queue Presets")
        
        # Scan presets tab
        scan_tab = QtWidgets.QWidget()
        scan_layout = QtWidgets.QVBoxLayout(scan_tab)
        scan_layout.setContentsMargins(12, 12, 12, 12)
        
        scan_label = QtWidgets.QLabel("Scan Presets")
        scan_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        scan_layout.addWidget(scan_label)
        
        self.scan_list = QtWidgets.QListWidget()
        self.scan_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        scan_layout.addWidget(self.scan_list)
        
        scan_buttons = QtWidgets.QHBoxLayout()
        self.scan_save_btn = QtWidgets.QPushButton("Save Current Scan")
        self.scan_save_btn.clicked.connect(self.save_scan_preset)
        self.scan_load_btn = QtWidgets.QPushButton("Load Selected")
        self.scan_load_btn.clicked.connect(self.load_scan_preset)
        self.scan_delete_btn = QtWidgets.QPushButton("Delete")
        self.scan_delete_btn.clicked.connect(self.delete_scan_preset)
        self.scan_rename_btn = QtWidgets.QPushButton("Rename")
        self.scan_rename_btn.clicked.connect(self.rename_scan_preset)
        
        scan_buttons.addWidget(self.scan_save_btn)
        scan_buttons.addWidget(self.scan_load_btn)
        scan_buttons.addWidget(self.scan_rename_btn)
        scan_buttons.addWidget(self.scan_delete_btn)
        scan_layout.addLayout(scan_buttons)
        
        self.tab_widget.addTab(scan_tab, "Scan Presets")
        
        layout.addWidget(self.tab_widget)
        
        # Settings section
        settings_frame = QtWidgets.QFrame()
        settings_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        settings_layout = QtWidgets.QHBoxLayout(settings_frame)
        
        self.warning_checkbox = QtWidgets.QCheckBox("Show overwrite warning when loading presets")
        self.warning_checkbox.setChecked(self.preset_manager.get_show_overwrite_warning())
        self.warning_checkbox.stateChanged.connect(self.on_warning_checkbox_changed)
        settings_layout.addWidget(self.warning_checkbox)
        settings_layout.addStretch()
        
        layout.addWidget(settings_frame)
        
        # Close button
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        
        # Apply theme
        if Theme:
            self.setStyleSheet(f"""
                QDialog {{
                    background-color: {Theme.colors.background_primary};
                    color: {Theme.colors.text_primary};
                }}
                QListWidget {{
                    background-color: {Theme.colors.background_secondary};
                    border: 1px solid {Theme.colors.border_light};
                    border-radius: 4px;
                }}
                QListWidget::item {{
                    padding: 8px;
                    border-bottom: 1px solid {Theme.colors.border_light};
                }}
                QListWidget::item:selected {{
                    background-color: {Theme.colors.accent_primary};
                    color: {Theme.colors.text_inverse};
                }}
                QPushButton {{
                    background-color: {Theme.colors.background_secondary};
                    border: 1px solid {Theme.colors.border_medium};
                    border-radius: 4px;
                    padding: 6px 12px;
                }}
                QPushButton:hover {{
                    background-color: {Theme.colors.background_hover};
                }}
                QTabWidget::pane {{
                    border: 1px solid {Theme.colors.border_light};
                    border-radius: 4px;
                }}
            """)
        
        # Update button states
        self.queue_list.itemSelectionChanged.connect(self.update_queue_button_states)
        self.scan_list.itemSelectionChanged.connect(self.update_scan_button_states)
        self.update_queue_button_states()
        self.update_scan_button_states()
    
    def refresh_preset_lists(self):
        """Refresh both preset lists."""
        # Queue presets
        self.queue_list.clear()
        queue_names = self.preset_manager.get_queue_preset_names()
        for i in range(PresetManager.MAX_PRESETS):
            if self.preset_manager.queue_preset_exists(i):
                name = queue_names[i] or f"Queue Preset {i + 1}"
                item = QtWidgets.QListWidgetItem(f"{i + 1}. {name}")
                item.setData(QtCore.Qt.UserRole, i)
                self.queue_list.addItem(item)
            else:
                item = QtWidgets.QListWidgetItem(f"{i + 1}. (Empty)")
                item.setData(QtCore.Qt.UserRole, i)
                item.setForeground(QtGui.QColor("#999999"))
                self.queue_list.addItem(item)
        
        # Scan presets
        self.scan_list.clear()
        scan_names = self.preset_manager.get_scan_preset_names()
        for i in range(PresetManager.MAX_PRESETS):
            if self.preset_manager.scan_preset_exists(i):
                name = scan_names[i] or f"Scan Preset {i + 1}"
                item = QtWidgets.QListWidgetItem(f"{i + 1}. {name}")
                item.setData(QtCore.Qt.UserRole, i)
                self.scan_list.addItem(item)
            else:
                item = QtWidgets.QListWidgetItem(f"{i + 1}. (Empty)")
                item.setData(QtCore.Qt.UserRole, i)
                item.setForeground(QtGui.QColor("#999999"))
                self.scan_list.addItem(item)
        
        self.update_queue_button_states()
        self.update_scan_button_states()
    
    def update_queue_button_states(self):
        """Update queue button enabled states."""
        selected = self.queue_list.currentItem()
        has_selection = selected is not None
        
        if has_selection:
            index = selected.data(QtCore.Qt.UserRole)
            preset_exists = self.preset_manager.queue_preset_exists(index)
        else:
            preset_exists = False
        
        self.queue_save_btn.setEnabled(self.queue is not None)
        self.queue_load_btn.setEnabled(preset_exists)
        self.queue_delete_btn.setEnabled(preset_exists)
        self.queue_rename_btn.setEnabled(preset_exists)
    
    def update_scan_button_states(self):
        """Update scan button enabled states."""
        selected = self.scan_list.currentItem()
        has_selection = selected is not None
        
        if has_selection:
            index = selected.data(QtCore.Qt.UserRole)
            preset_exists = self.preset_manager.scan_preset_exists(index)
        else:
            preset_exists = False
        
        self.scan_save_btn.setEnabled(self.scan is not None)
        self.scan_load_btn.setEnabled(preset_exists)
        self.scan_delete_btn.setEnabled(preset_exists)
        self.scan_rename_btn.setEnabled(preset_exists)
    
    def save_queue_preset(self):
        """Save current queue to selected preset slot."""
        if self.queue is None:
            QtWidgets.QMessageBox.warning(self, "No Queue", "No queue available to save.")
            return
        
        selected = self.queue_list.currentItem()
        if selected is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Please select a preset slot.")
            return
        
        index = selected.data(QtCore.Qt.UserRole)
        
        # Get preset name
        current_name = self.preset_manager.get_queue_preset_names()[index]
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Preset Name", "Enter a name for this preset:",
            QtWidgets.QLineEdit.Normal, current_name or f"Queue Preset {index + 1}"
        )
        
        if ok:
            if self.preset_manager.save_queue_preset(index, self.queue, name):
                QtWidgets.QMessageBox.information(self, "Success", "Queue preset saved successfully.")
                self.refresh_preset_lists()
            else:
                QtWidgets.QMessageBox.warning(self, "Error", "Failed to save queue preset.")
    
    def load_queue_preset(self):
        """Load selected queue preset."""
        selected = self.queue_list.currentItem()
        if selected is None:
            return
        
        index = selected.data(QtCore.Qt.UserRole)
        
        # Show warning if enabled
        if self.preset_manager.get_show_overwrite_warning():
            reply = QtWidgets.QMessageBox.question(
                self, "Load Preset",
                "This will replace the current queue. Continue?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
        
        queue = self.preset_manager.load_queue_preset(index)
        if queue:
            self.queue_preset_loaded.emit(queue)
            QtWidgets.QMessageBox.information(self, "Success", "Queue preset loaded successfully.")
        else:
            QtWidgets.QMessageBox.warning(self, "Error", "Failed to load queue preset.")
    
    def delete_queue_preset(self):
        """Delete selected queue preset."""
        selected = self.queue_list.currentItem()
        if selected is None:
            return
        
        index = selected.data(QtCore.Qt.UserRole)
        
        reply = QtWidgets.QMessageBox.question(
            self, "Delete Preset",
            "Are you sure you want to delete this preset?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            if self.preset_manager.delete_queue_preset(index):
                self.refresh_preset_lists()
            else:
                QtWidgets.QMessageBox.warning(self, "Error", "Failed to delete preset.")
    
    def rename_queue_preset(self):
        """Rename selected queue preset."""
        selected = self.queue_list.currentItem()
        if selected is None:
            return
        
        index = selected.data(QtCore.Qt.UserRole)
        current_name = self.preset_manager.get_queue_preset_names()[index]
        
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Rename Preset", "Enter new name:",
            QtWidgets.QLineEdit.Normal, current_name
        )
        
        if ok and name:
            self.preset_manager.settings["queue_preset_names"][index] = name
            self.preset_manager._save_settings()
            self.refresh_preset_lists()
    
    def save_scan_preset(self):
        """Save current scan to selected preset slot."""
        if self.scan is None:
            QtWidgets.QMessageBox.warning(self, "No Scan", "No scan available to save.")
            return
        
        selected = self.scan_list.currentItem()
        if selected is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Please select a preset slot.")
            return
        
        index = selected.data(QtCore.Qt.UserRole)
        
        # Get preset name
        current_name = self.preset_manager.get_scan_preset_names()[index]
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Preset Name", "Enter a name for this preset:",
            QtWidgets.QLineEdit.Normal, current_name or f"Scan Preset {index + 1}"
        )
        
        if ok:
            if self.preset_manager.save_scan_preset(index, self.scan, name):
                QtWidgets.QMessageBox.information(self, "Success", "Scan preset saved successfully.")
                self.refresh_preset_lists()
            else:
                QtWidgets.QMessageBox.warning(self, "Error", "Failed to save scan preset.")
    
    def load_scan_preset(self):
        """Load selected scan preset."""
        selected = self.scan_list.currentItem()
        if selected is None:
            return
        
        index = selected.data(QtCore.Qt.UserRole)
        
        # Show warning if enabled
        if self.preset_manager.get_show_overwrite_warning():
            reply = QtWidgets.QMessageBox.question(
                self, "Load Preset",
                "This will replace the current scan. Continue?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
        
        scan = self.preset_manager.load_scan_preset(index)
        if scan:
            self.scan_preset_loaded.emit(scan)
            QtWidgets.QMessageBox.information(self, "Success", "Scan preset loaded successfully.")
        else:
            QtWidgets.QMessageBox.warning(self, "Error", "Failed to load scan preset.")
    
    def delete_scan_preset(self):
        """Delete selected scan preset."""
        selected = self.scan_list.currentItem()
        if selected is None:
            return
        
        index = selected.data(QtCore.Qt.UserRole)
        
        reply = QtWidgets.QMessageBox.question(
            self, "Delete Preset",
            "Are you sure you want to delete this preset?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            if self.preset_manager.delete_scan_preset(index):
                self.refresh_preset_lists()
            else:
                QtWidgets.QMessageBox.warning(self, "Error", "Failed to delete preset.")
    
    def rename_scan_preset(self):
        """Rename selected scan preset."""
        selected = self.scan_list.currentItem()
        if selected is None:
            return
        
        index = selected.data(QtCore.Qt.UserRole)
        current_name = self.preset_manager.get_scan_preset_names()[index]
        
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Rename Preset", "Enter new name:",
            QtWidgets.QLineEdit.Normal, current_name
        )
        
        if ok and name:
            self.preset_manager.settings["scan_preset_names"][index] = name
            self.preset_manager._save_settings()
            self.refresh_preset_lists()
    
    def on_warning_checkbox_changed(self, state):
        """Handle warning checkbox state change."""
        self.preset_manager.set_show_overwrite_warning(state == QtCore.Qt.Checked)


# Example usage
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    
    # Create example queue and scan
    from pybirch.scan.scan import get_empty_scan
    
    queue = Queue(QID="TestQueue")
    scan = get_empty_scan()
    
    dialog = PresetDialog(queue=queue, scan=scan)
    dialog.exec()
    
    sys.exit(app.exec())
