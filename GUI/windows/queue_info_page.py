import sys
from PySide6 import QtCore, QtWidgets, QtGui
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

# Import required widgets
from GUI.widgets.single_entry_widget import SingleEntryWidget
from GUI.widgets.single_checkbox_widget import SingleCheckboxWidget
from GUI.widgets.queue_title_bar import QueueTitleBar
from GUI.widgets.searchable_combobox import SampleSelectWidget, ProjectSelectWidget
from GUI.theme import Theme

# Import UserFieldMainWindow
from GUI.widgets.user_fields.mainwindow import UserFieldMainWindow

from typing import Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from database.services import DatabaseService


class QueueInfoPage(QtWidgets.QWidget):
    """
    A comprehensive queue information page containing:
    - Queue title bar at the top
    - Single entry widget for Queue Name
    - Sample and Project selection (searchable dropdowns when database enabled)
    - User fields section
    - Single checkbox for "Save as default"
    - Set/get data functionality using dictionary objects
    """
    
    # Signals for changes
    sample_changed = QtCore.Signal(object, str)  # (sample_id, display_text)
    project_changed = QtCore.Signal(object, str)  # (project_id, display_text)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._db_service: Optional['DatabaseService'] = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface components."""
        # Create main vertical layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Add queue title bar at the top
        self.title_bar = QueueTitleBar()
        layout.addWidget(self.title_bar)
        
        # Create content area with margins
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(15)
        
        # Add single entry widget for queue/project name
        self.project_name_widget = SingleEntryWidget("Queue Name", "")
        content_layout.addWidget(self.project_name_widget)
        
        # Add sample and project selection widgets
        self.sample_widget = SampleSelectWidget()
        self.project_widget = ProjectSelectWidget()
        
        content_layout.addWidget(self.sample_widget)
        content_layout.addWidget(self.project_widget)
        
        # Connect signals
        self.sample_widget.selection_changed.connect(self._on_sample_changed)
        self.project_widget.selection_changed.connect(self._on_project_changed)
        
        # Add user fields section
        user_fields_label = QtWidgets.QLabel("User Fields")
        user_fields_label.setStyleSheet(Theme.section_title_style())
        content_layout.addWidget(user_fields_label)
        
        self.user_fields_widget = UserFieldMainWindow()
        # Set a reasonable minimum height for the user fields widget
        self.user_fields_widget.setMinimumHeight(200)
        content_layout.addWidget(self.user_fields_widget)
        
        # Add "Save as default" checkbox
        self.save_as_default_widget = SingleCheckboxWidget("Save as default", False)
        content_layout.addWidget(self.save_as_default_widget)
        
        # Add stretch to push content to the top
        content_layout.addStretch()
        
        # Add content widget to main layout
        layout.addWidget(content_widget)
    
    def _on_sample_changed(self, sample_id, display_text):
        """Handle sample selection change."""
        self.sample_changed.emit(sample_id, display_text)
    
    def _on_project_changed(self, project_id, display_text):
        """Handle project selection change."""
        self.project_changed.emit(project_id, display_text)
    
    def set_database_service(self, db_service: 'DatabaseService'):
        """
        Set the database service for loading samples and projects.
        
        When set, the sample and project widgets become searchable dropdowns
        populated from the database.
        
        Args:
            db_service: DatabaseService instance
        """
        self._db_service = db_service
        
        if db_service:
            self.sample_widget.setup_database(db_service)
            self.project_widget.setup_database(db_service)
        else:
            self.sample_widget.set_database_mode(False)
            self.project_widget.set_database_mode(False)
    
    def refresh_database_items(self):
        """Reload samples and projects from database."""
        if self._db_service:
            self.sample_widget.load_items()
            self.project_widget.load_items()
    
    def set_data(self, data: dict) -> None:
        """Set data from a dictionary object.
        
        Expected dictionary structure:
        {
            "project_name": str,  # Queue name
            "sample_id": int or None,  # Database sample ID
            "sample_text": str,  # Sample display text (for non-db mode)
            "project_id": int or None,  # Database project ID  
            "project_text": str,  # Project display text (for non-db mode)
            "user_fields": dict,  # User fields data
            "save_as_default": bool
        }
        
        Args:
            data: Dictionary containing queue info data
        """
        if not isinstance(data, dict):
            return
        
        # Set queue name
        if "project_name" in data:
            self.project_name_widget.set_data({"Queue Name": data["project_name"]})
        
        # Set sample - try ID first, then text
        if "sample_id" in data and data["sample_id"] is not None:
            self.sample_widget.set_selected_id(data["sample_id"])
        elif "sample_text" in data:
            self.sample_widget.set_text(data["sample_text"])
        
        # Set project - try ID first, then text
        if "project_id" in data and data["project_id"] is not None:
            self.project_widget.set_selected_id(data["project_id"])
        elif "project_text" in data:
            self.project_widget.set_text(data["project_text"])
        
        # Set user fields
        if "user_fields" in data:
            self.user_fields_widget.from_dict(data["user_fields"])
        
        # Set save as default checkbox
        if "save_as_default" in data:
            self.save_as_default_widget.set_data({"Save as default": data["save_as_default"]})
    
    def get_data(self) -> dict:
        """Get data as a dictionary object.
        
        Returns:
            Dictionary containing all queue info data including sample/project IDs
        """
        # Get data from each widget
        project_data = self.project_name_widget.get_data()
        user_fields_data = self.user_fields_widget.to_dict()
        save_default_data = self.save_as_default_widget.get_data()
        
        return {
            "project_name": project_data.get("Queue Name", ""),
            "sample_id": self.sample_widget.get_selected_id(),
            "sample_text": self.sample_widget.get_text(),
            "project_id": self.project_widget.get_selected_id(),
            "project_text": self.project_widget.get_text(),
            "user_fields": user_fields_data,
            "save_as_default": save_default_data.get("Save as default", False)
        }
    
    def get_sample_id(self) -> Optional[int]:
        """Get the selected sample database ID."""
        return self.sample_widget.get_selected_id()
    
    def get_project_id(self) -> Optional[int]:
        """Get the selected project database ID."""
        return self.project_widget.get_selected_id()
    
    def clear_data(self) -> None:
        """Clear all data in the page."""
        self.project_name_widget.set_data({"Queue Name": ""})
        self.sample_widget.clear()
        self.project_widget.clear()
        self.user_fields_widget.clear_all()
        self.save_as_default_widget.set_data({"Save as default": False})


def main():
    """Test the QueueInfoPage widget."""
    from GUI.theme import apply_theme
    
    app = QtWidgets.QApplication(sys.argv)
    apply_theme(app)
    
    # Create main window
    main_window = QtWidgets.QMainWindow()
    main_window.setWindowTitle("Queue Info Page Test")
    main_window.resize(800, 600)
    
    # Create queue info page
    queue_info_page = QueueInfoPage()
    main_window.setCentralWidget(queue_info_page)
    
    # Test data
    test_data = {
        "project_name": "Test Queue",
        "sample_text": "S-2026-001",
        "project_text": "Test Project",
        "user_fields": {
            "Custom Field 1": "Value 1",
            "Custom Field 2": "Value 2"
        },
        "save_as_default": True
    }
    
    # Set test data
    queue_info_page.set_data(test_data)
    
    main_window.show()

    # Print data after 2 seconds to test get_data
    def print_data():
        data = queue_info_page.get_data()
        print("Current data:", data)
    
    QtCore.QTimer.singleShot(2000, print_data)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
