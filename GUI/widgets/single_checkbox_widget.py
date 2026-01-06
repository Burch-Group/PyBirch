from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QCheckBox
from PySide6.QtCore import Qt

# Import theme
try:
    from GUI.theme import Theme
except ImportError:
    try:
        from theme import Theme
    except ImportError:
        Theme = None


class SingleCheckboxWidget(QWidget):
    """
    A widget with a checkbox on the left and a title on the right.
    Layout: [Checkbox] [Title]
    """
    
    def __init__(self, title: str = "Title", checked: bool = False, parent=None):
        super().__init__(parent)
        
        # Create layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Create checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(checked)
        
        # Create title label
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        # Add widgets to layout
        layout.addWidget(self.checkbox)
        layout.addWidget(self.title_label)
        
        # Set stretch factors (checkbox takes minimal space, title takes remaining space)
        layout.setStretchFactor(self.checkbox, 0)
        layout.setStretchFactor(self.title_label, 1)
    
    def set_title(self, title: str) -> None:
        """Set the title text"""
        self.title_label.setText(title)
    
    def get_title(self) -> str:
        """Get the title text"""
        return self.title_label.text()
    
    def set_checked(self, checked: bool) -> None:
        """Set the checkbox state"""
        self.checkbox.setChecked(checked)
    
    def is_checked(self) -> bool:
        """Get the checkbox state"""
        return self.checkbox.isChecked()
    
    def set_data(self, data: dict) -> None:
        """Set title and checked state from a dictionary where title is key and checked state is the dict value
        
        Args:
            data: Dictionary with single key-value pair where key becomes title, value becomes checked state
        """
        if data:
            # Get the first (and presumably only) key-value pair
            title, checked = next(iter(data.items()))
            self.set_title(str(title))
            # Convert value to boolean
            if isinstance(checked, bool):
                self.set_checked(checked)
            elif isinstance(checked, str):
                self.set_checked(checked.lower() in ('true', '1', 'yes', 'on'))
            else:
                self.set_checked(bool(checked))
    
    def get_data(self) -> dict:
        """Get data as a dictionary where title is key and checked state is the dict value
        
        Returns:
            Dictionary with title as key and checked state as value
        """
        return {
            self.get_title(): self.is_checked()
        }


# Test the widget if run directly
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QVBoxLayout, QMainWindow, QPushButton
    
    class TestWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Single Checkbox Widget Test")
            self.setGeometry(200, 200, 400, 200)
            
            # Create central widget and layout
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            layout = QVBoxLayout(central_widget)
            
            # Create test widgets
            self.widget1 = SingleCheckboxWidget("Enable Feature A", True)
            self.widget2 = SingleCheckboxWidget("Enable Feature B", False)
            self.widget3 = SingleCheckboxWidget("Enable Feature C")
            
            layout.addWidget(self.widget1)
            layout.addWidget(self.widget2)
            layout.addWidget(self.widget3)
            
            # Add test buttons
            test_button = QPushButton("Test Get Data")
            test_button.clicked.connect(self.test_get_data)
            layout.addWidget(test_button)
            
            set_button = QPushButton("Test Set Data")
            set_button.clicked.connect(self.test_set_data)
            layout.addWidget(set_button)
            
        def test_get_data(self):
            print("Widget 1 data:", self.widget1.get_data())
            print("Widget 2 data:", self.widget2.get_data())
            print("Widget 3 data:", self.widget3.get_data())
            
        def test_set_data(self):
            self.widget3.set_data({'Updated Feature': True})
    
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
