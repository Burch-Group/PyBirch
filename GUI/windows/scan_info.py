# Copyright (C) 2025
# Scan Info Page Widget for PyBirch
from __future__ import annotations

import sys
import os
from typing import Optional

# Add path to parent directories for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

user_fields_path = os.path.join(os.path.dirname(__file__), '..', 'widgets', 'user_fields')
if user_fields_path not in sys.path:
    sys.path.insert(0, user_fields_path)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QFrame)

# Import the required widgets
from widgets.scan_title_bar import ScanTitleBar
from widgets.single_entry_widget import SingleEntryWidget
from widgets.user_fields.mainwindow import UserFieldMainWindow
from pybirch.scan.scan import Scan, get_empty_scan


class ScanInfoPage(QWidget):
    """
    Scan Info page widget that combines:
    - ScanTitleBar at the top
    - SingleEntryWidget for "Job Type"
    - User Fields box for custom user fields
    """
    
    def __init__(self, scan: Optional[Scan] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Use provided scan or create empty one
        self.scan = scan if scan is not None else get_empty_scan()
        
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface"""
        # Main vertical layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)
        
        # Create scan title bar
        self.title_bar = ScanTitleBar(self.scan, title="Scan Info")
        main_layout.addWidget(self.title_bar)
        
        # Create content area with margins
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(15)
        
        # Create Job Type single entry widget
        self.job_type_widget = SingleEntryWidget("Job Type", "")
        content_layout.addWidget(self.job_type_widget)
        
        # Create User Fields group box
        user_fields_group = QGroupBox("User Fields")
        user_fields_layout = QVBoxLayout(user_fields_group)
        user_fields_layout.setContentsMargins(10, 15, 10, 10)
        
        # Create user fields widget (embedded, no window decorations)
        # Add the user_fields directory to path for treemodel import
        
        self.user_fields_widget = UserFieldMainWindow(parent=self)
        
        # Remove window decorations for embedded use
        self.user_fields_widget.menuBar().hide()
        self.user_fields_widget.statusBar().hide()
        self.user_fields_widget.setWindowFlags(Qt.WindowType.Widget)
        
        # Enable drag and drop for user fields tree view
        self.user_fields_widget.view.setDragEnabled(True)
        self.user_fields_widget.view.setAcceptDrops(True)
        self.user_fields_widget.view.setDropIndicatorShown(True)
        self.user_fields_widget.view.setDragDropMode(self.user_fields_widget.view.DragDropMode.InternalMove)
        
        # Add the central widget (tree view) directly to the layout
        user_fields_layout.addWidget(self.user_fields_widget.view)
        
        content_layout.addWidget(user_fields_group)
        
        # Add content widget to main layout
        main_layout.addWidget(content_widget)
        
    def set_data(self, data: dict) -> None:
        """Set all data on the page from a dictionary
        
        Args:
            data: Dictionary containing:
                - 'job_type': String value for job type
                - 'user_fields': Dictionary for user fields
        """
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
                - 'job_type': String value from job type widget
                - 'user_fields': Dictionary from user fields widget
        """
        return {
            'job_type': self.job_type_widget.get_value(),
            'user_fields': self.user_fields_widget.to_dict()
        }
    
    def clear_data(self) -> None:
        """Clear all data on the page"""
        self.job_type_widget.set_value("")
        self.user_fields_widget.clear_all()


def main():
    """Test the ScanInfoPage widget"""
    from PySide6.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    
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