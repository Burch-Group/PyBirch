import sys
from PySide6 import QtCore, QtWidgets, QtGui
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

# Import required widgets
from GUI.widgets.single_entry_widget import SingleEntryWidget
from GUI.widgets.single_checkbox_widget import SingleCheckboxWidget
from GUI.widgets.queue_title_bar import QueueTitleBar

# Import UserFieldMainWindow
from GUI.widgets.user_fields.mainwindow import UserFieldMainWindow

class QueueInfoPage(QtWidgets.QWidget):
    """
    A comprehensive queue information page containing:
    - Queue title bar at the top
    - Single entry widgets for Project Name, Material, and Substrate
    - User fields section
    - Single checkbox for "Save as default"
    - Set/get data functionality using dictionary objects
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
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
        
        # Add single entry widgets
        self.project_name_widget = SingleEntryWidget("Project Name", "")
        self.material_widget = SingleEntryWidget("Material", "")
        self.substrate_widget = SingleEntryWidget("Substrate", "")
        
        content_layout.addWidget(self.project_name_widget)
        content_layout.addWidget(self.material_widget)
        content_layout.addWidget(self.substrate_widget)
        
        # Add user fields section
        user_fields_label = QtWidgets.QLabel("User Fields")
        user_fields_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                margin-top: 10px;
                margin-bottom: 5px;
            }
        """)
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
    
    def set_data(self, data: dict) -> None:
        """Set data from a dictionary object.
        
        Expected dictionary structure:
        {
            "project_name": str,
            "material": str, 
            "substrate": str,
            "user_fields": dict,  # User fields data
            "save_as_default": bool
        }
        
        Args:
            data: Dictionary containing queue info data
        """
        if not isinstance(data, dict):
            return
        
        # Set project name
        if "project_name" in data:
            self.project_name_widget.set_data({"Project Name": data["project_name"]})
        
        # Set material
        if "material" in data:
            self.material_widget.set_data({"Material": data["material"]})
        
        # Set substrate
        if "substrate" in data:
            self.substrate_widget.set_data({"Substrate": data["substrate"]})
        
        # Set user fields
        if "user_fields" in data:
            self.user_fields_widget.from_dict(data["user_fields"])
        
        # Set save as default checkbox
        if "save_as_default" in data:
            self.save_as_default_widget.set_data({"Save as default": data["save_as_default"]})
    
    def get_data(self) -> dict:
        """Get data as a dictionary object.
        
        Returns:
            Dictionary containing all queue info data
        """
        # Get data from each widget
        project_data = self.project_name_widget.get_data()
        material_data = self.material_widget.get_data()
        substrate_data = self.substrate_widget.get_data()
        user_fields_data = self.user_fields_widget.to_dict()
        save_default_data = self.save_as_default_widget.get_data()
        
        return {
            "project_name": project_data.get("Project Name", ""),
            "material": material_data.get("Material", ""),
            "substrate": substrate_data.get("Substrate", ""),
            "user_fields": user_fields_data,
            "save_as_default": save_default_data.get("Save as default", False)
        }
    
    def clear_data(self) -> None:
        """Clear all data in the page."""
        self.project_name_widget.set_data({"Project Name": ""})
        self.material_widget.set_data({"Material": ""})
        self.substrate_widget.set_data({"Substrate": ""})
        self.user_fields_widget.clear_all()
        self.save_as_default_widget.set_data({"Save as default": False})


def main():
    """Test the QueueInfoPage widget."""
    app = QtWidgets.QApplication(sys.argv)
    
    # Create main window
    main_window = QtWidgets.QMainWindow()
    main_window.setWindowTitle("Queue Info Page Test")
    main_window.resize(800, 600)
    
    # Create queue info page
    queue_info_page = QueueInfoPage()
    main_window.setCentralWidget(queue_info_page)
    
    # Test data
    test_data = {
        "project_name": "Sample Project",
        "material": "Silicon",
        "substrate": "SiO2",
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
