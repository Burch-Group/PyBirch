from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit
from PySide6.QtCore import Qt


class SingleEntryWidget(QWidget):
    """
    A widget with a title on the left, a colon, and a text entry box on the right.
    Layout: [Title] : [Text Entry Box]
    """
    
    def __init__(self, title: str = "Title", value: str = "", parent=None):
        super().__init__(parent)
        
        # Create layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Create title label
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # Create colon label
        self.colon_label = QLabel(":")
        
        # Create text entry box
        self.entry_box = QLineEdit(value)
        
        # Add widgets to layout
        layout.addWidget(self.title_label)
        layout.addWidget(self.colon_label)
        layout.addWidget(self.entry_box)
        
        # Set stretch factors (title takes minimal space, entry box takes remaining space)
        layout.setStretchFactor(self.title_label, 0)
        layout.setStretchFactor(self.colon_label, 0)
        layout.setStretchFactor(self.entry_box, 1)
    
    def set_title(self, title: str) -> None:
        """Set the title text"""
        self.title_label.setText(title)
    
    def get_title(self) -> str:
        """Get the title text"""
        return self.title_label.text()
    
    def set_value(self, value: str) -> None:
        """Set the entry box value"""
        self.entry_box.setText(value)
    
    def get_value(self) -> str:
        """Get the entry box value"""
        return self.entry_box.text()
    
    def set_data(self, data: dict) -> None:
        """Set title and value from a dictionary where title is key and value is the dict value
        
        Args:
            data: Dictionary with single key-value pair where key becomes title, value becomes entry value
        """
        if data:
            # Get the first (and presumably only) key-value pair
            title, value = next(iter(data.items()))
            self.set_title(str(title))
            self.set_value(str(value))
    
    def get_data(self) -> dict:
        """Get data as a dictionary where title is key and entry value is the dict value
        
        Returns:
            Dictionary with title as key and entry value as value
        """
        return {
            self.get_title(): self.get_value()
        }


# Test the widget if run directly
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QVBoxLayout, QMainWindow, QPushButton
    
    class TestWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Single Entry Widget Test")
            self.setGeometry(200, 200, 400, 200)
            
            # Create central widget and layout
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            layout = QVBoxLayout(central_widget)
            
            # Create test widgets
            self.widget1 = SingleEntryWidget("Name", "John Doe")
            self.widget2 = SingleEntryWidget("Email", "john@example.com")
            self.widget3 = SingleEntryWidget("Phone")
            
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
            self.widget3.set_data({'Updated Title': 'Updated Value'})
    
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
