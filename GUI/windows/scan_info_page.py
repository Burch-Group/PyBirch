# Copyright (C) 2025
# Scan Info Page Widget for PyBirch
from __future__ import annotations

import sys
import os
from typing import Optional

# Add path to parent directories for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFrame, QPushButton)

# Import the required widgets
from widgets.single_entry_widget import SingleEntryWidget
from widgets.user_fields.mainwindow import UserFieldMainWindow
from pybirch.scan.scan import Scan, get_empty_scan

# Import theme
try:
    from GUI.theme import Theme, apply_theme
except ImportError:
    from theme import Theme, apply_theme


class ScanInfoPage(QWidget):
    """
    Scan Info page widget that contains:
    - SingleEntryWidget for "Job Type"
    - User Fields box for custom user fields
    - Cancel and Done buttons at the bottom
    """
    
    # Signals for cancel and done actions
    cancelled = Signal()
    done = Signal()
    
    def __init__(self, scan: Optional[Scan] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Use provided scan or create empty one
        self.scan = scan if scan is not None else get_empty_scan()
        
        self.init_ui()
        self.connect_signals()
        
    def init_ui(self):
        """Initialize the user interface"""
        # Main vertical layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # Create Scan Name single entry widget
        self.scan_name_widget = SingleEntryWidget("Scan Name", "")
        main_layout.addWidget(self.scan_name_widget)
        
        # Create Job Type single entry widget
        self.job_type_widget = SingleEntryWidget("Job Type", "")
        main_layout.addWidget(self.job_type_widget)
        
        # Create User Fields group box
        user_fields_group = QGroupBox("User Fields")
        user_fields_layout = QVBoxLayout(user_fields_group)
        user_fields_layout.setContentsMargins(10, 15, 10, 10)
        
        # Create user fields widget (embedded, no window decorations)
        # Pass None as parent to prevent it from appearing in the layout
        self.user_fields_widget = UserFieldMainWindow(parent=None)
        
        # Hide the QMainWindow container completely - we only use its view
        self.user_fields_widget.hide()
        
        # Enable drag and drop for user fields tree view
        self.user_fields_widget.view.setDragEnabled(True)
        self.user_fields_widget.view.setAcceptDrops(True)
        self.user_fields_widget.view.setDropIndicatorShown(True)
        self.user_fields_widget.view.setDragDropMode(self.user_fields_widget.view.DragDropMode.InternalMove)
        
        # Add the central widget (tree view) directly to the layout
        user_fields_layout.addWidget(self.user_fields_widget.view)
        
        main_layout.addWidget(user_fields_group, 1)  # Give it stretch factor
        
        # Create button row at the bottom
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_button = QPushButton("Cancel")
        if Theme:
            self.cancel_button.setStyleSheet(Theme.danger_button_style())
        button_layout.addWidget(self.cancel_button)
        
        self.done_button = QPushButton("Done")
        if Theme:
            self.done_button.setStyleSheet(Theme.primary_button_style())
        button_layout.addWidget(self.done_button)
        
        main_layout.addLayout(button_layout)
        
    def connect_signals(self):
        """Connect button signals"""
        self.cancel_button.clicked.connect(self.on_cancel)
        self.done_button.clicked.connect(self.on_done)
        
    def on_cancel(self):
        """Handle cancel button click"""
        self.cancelled.emit()
        
    def on_done(self):
        """Handle done button click - save data to scan settings"""
        # Save data to scan settings
        data = self.get_data()
        self.scan.scan_settings.scan_name = data['scan_name']
        self.scan.scan_settings.job_type = data['job_type']
        self.scan.scan_settings.user_fields = data['user_fields']
        
        self.done.emit()
        
    def load_from_scan(self, scan: Optional[Scan] = None):
        """Load data from the scan settings
        
        Args:
            scan: Optional scan object. If provided, updates the internal scan reference.
                  If None, uses the existing internal scan.
        """
        if scan is not None:
            self.scan = scan
            
        data = {
            'scan_name': getattr(self.scan.scan_settings, 'scan_name', ''),
            'job_type': getattr(self.scan.scan_settings, 'job_type', ''),
            'user_fields': getattr(self.scan.scan_settings, 'user_fields', {})
        }
        self.set_data(data)
        
    def set_data(self, data: dict) -> None:
        """Set all data on the page from a dictionary
        
        Args:
            data: Dictionary containing:
                - 'scan_name': String value for scan name
                - 'job_type': String value for job type
                - 'user_fields': Dictionary for user fields
        """
        # Set scan name
        if 'scan_name' in data:
            self.scan_name_widget.set_value(str(data['scan_name']))
        
        # Set job type
        if 'job_type' in data:
            self.job_type_widget.set_value(str(data['job_type']))
            
        # Set user fields
        if 'user_fields' in data and isinstance(data['user_fields'], dict):
            self.user_fields_widget.from_dict(data['user_fields'])
    
    def get_data(self) -> dict:
        """Get all data from the page as a dictionary
        
        Returns:
            Dictionary containing:
                - 'scan_name': String value from scan name widget
                - 'job_type': String value from job type widget
                - 'user_fields': Dictionary from user fields widget
        """
        return {
            'scan_name': self.scan_name_widget.get_value(),
            'job_type': self.job_type_widget.get_value(),
            'user_fields': self.user_fields_widget.to_dict()
        }
    
    def clear_data(self) -> None:
        """Clear all data on the page"""
        self.scan_name_widget.set_value("")
        self.job_type_widget.set_value("")
        self.user_fields_widget.clear_all()


def main():
    """Test the ScanInfoPage widget"""
    from PySide6.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    apply_theme(app)
    
    # Create main window
    main_window = QMainWindow()
    main_window.setWindowTitle("Scan Info Page Test")
    main_window.resize(800, 600)
    
    # Create central widget with layout
    central_widget = QWidget()
    main_window.setCentralWidget(central_widget)
    layout = QVBoxLayout(central_widget)
    
    # Create scan info page
    scan_info_page = ScanInfoPage()
    layout.addWidget(scan_info_page)
    
    main_window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()