import sys
from PySide6 import QtCore, QtWidgets, QtGui
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
try:
    from pybirch.queue.queue import Queue
except ImportError:
    # Fallback if queue module doesn't exist
    Queue = object
import pickle

class QueueTitleBar(QtWidgets.QWidget):
    """
    A title bar widget for the queue interface with various control buttons.
    Contains the 'Queue' label on the left and right-aligned buttons for:
    - Info
    - WandB
    - Presets
    - Save/Load
    """
    
    def __init__(self, queue=None, title: str = "Queue"):
        super().__init__()
        self.queue = queue
        self.init_ui(title)
        self.connect_signals()
        self.default_savepath = ""
        self.default_loadpath = ""

    def init_ui(self, title: str):
        """Initialize the user interface components."""
        # Create the main horizontal layout
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        # Add "Queue" label on the left
        self.queue_label = QtWidgets.QLabel(title)
        self.queue_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.queue_label)
        
        # Add stretch to push buttons to the right
        layout.addStretch()
        
        # Create button container for right-aligned buttons
        button_container = QtWidgets.QWidget()
        button_layout = QtWidgets.QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(4)
        
        # Info button
        self.info_button = QtWidgets.QPushButton()
        self.info_button.setIcon(QtGui.QIcon.fromTheme("dialog-information"))
        self.info_button.setToolTip("Show queue information")
        self.info_button.setFixedSize(32, 32)
        self.info_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 4px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        
        # WandB button
        self.wandb_button = QtWidgets.QPushButton()
        self.wandb_button.setIcon(QtGui.QIcon.fromTheme("applications-internet"))
        self.wandb_button.setToolTip("WandB integration")
        self.wandb_button.setFixedSize(32, 32)
        self.wandb_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 4px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        
        # Presets button. Bold P as the logo
        self.presets_button = QtWidgets.QPushButton("P")
        self.presets_button.setToolTip("Manage presets")
        self.presets_button.setFixedSize(32, 32)
        self.presets_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 4px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        
        # Save button
        self.save_button = QtWidgets.QPushButton()
        self.save_button.setIcon(QtGui.QIcon.fromTheme("document-save"))
        self.save_button.setToolTip("Save configuration")
        self.save_button.setFixedSize(32, 32)
        self.save_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 4px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)

        # Load button
        self.load_button = QtWidgets.QPushButton()
        self.load_button.setIcon(QtGui.QIcon.fromTheme("document-open"))
        self.load_button.setToolTip("Load configuration")
        self.load_button.setFixedSize(32, 32)
        self.load_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 4px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        
        # Add buttons to button layout
        button_layout.addWidget(self.info_button)
        button_layout.addWidget(self.wandb_button)
        button_layout.addWidget(self.presets_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.load_button)
        
        # Add button container to main layout
        layout.addWidget(button_container)
        
        # Set overall widget styling
        self.setStyleSheet("""
            QueueTitleBar {
                background-color: #f5f5f5;
                border-bottom: 1px solid #cccccc;
            }
        """)
        
        # Set fixed height for the title bar
        self.setFixedHeight(40)

    def connect_signals(self):
        """Connect button signals to their respective slots."""
        self.info_button.clicked.connect(self.on_info_clicked)
        self.wandb_button.clicked.connect(self.on_wandb_clicked)
        self.presets_button.clicked.connect(self.on_presets_clicked)
        self.save_button.clicked.connect(self.on_save_clicked)
        self.load_button.clicked.connect(self.on_load_clicked)

    # Signal handler methods
    def on_info_clicked(self):
        """Handle info button click."""
        print("Queue Info button clicked")
        # TODO: Implement queue info dialog or panel

    def on_wandb_clicked(self):
        """Handle WandB button click."""
        print("Queue WandB button clicked")
        # TODO: Implement WandB integration for queue

    def on_presets_clicked(self):
        """Handle presets button click."""
        print("Queue Presets button clicked")
        # TODO: Implement queue presets management

    def on_save_clicked(self):
        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.AnyFile) # type: ignore
        if self.default_savepath:
            dialog.setDirectory(self.default_savepath)
        if dialog.exec():
            selected_files = dialog.selectedFiles()
            if selected_files:
                file_path = selected_files[0]
                print(f"Selected file to save: {file_path}")
                self.save_queue_to_file(file_path)
                self.default_savepath = os.path.dirname(file_path)
            
    def save_queue_to_file(self, file_path: str):
        with open(file_path, 'wb') as f:
            pickle.dump(self.queue, f)

    def on_load_clicked(self):
        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile) # type: ignore
        dialog.setNameFilter("Pickle Files (*.pkl *.pickle);;JSON Files (*.json)")
        if self.default_loadpath:
            dialog.setDirectory(self.default_loadpath)
        if dialog.exec():
            selected_files = dialog.selectedFiles()
            if selected_files:
                file_path = selected_files[0]
                print(f"Selected file to load: {file_path}")
                self.load_queue_from_file(file_path)
                self.default_loadpath = os.path.dirname(file_path)

    def load_queue_from_file(self, file_path: str):
        with open(file_path, 'rb') as f:
            self.queue = pickle.load(f)
            self.update_ui()

    def update_ui(self):
        """Update the UI elements based on the current queue state."""
        pass

def main():
    """Test the QueueTitleBar widget."""
    app = QtWidgets.QApplication(sys.argv)
    
    # Create a main window to display the title bar
    main_window = QtWidgets.QMainWindow()
    main_window.setWindowTitle("Queue Title Bar Test")
    main_window.resize(600, 400)
    
    # Create and set the title bar as a widget
    title_bar = QueueTitleBar()
    central_widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(central_widget)
    layout.addWidget(title_bar)
    layout.addStretch()  # Push title bar to top
    
    main_window.setCentralWidget(central_widget)
    main_window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()