import sys
from PySide6 import QtCore, QtWidgets, QtGui
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from pybirch.scan.scan import Scan, get_empty_scan
import pickle
from pybirch.queue.queue import Queue

class QueueBar(QtWidgets.QWidget):
    """
    A vertical queue bar widget for the queue interface with various control buttons.
    From top to bottom, contains buttons for:
    - Queue
    - Info
    - Instruments
    - Presets
    - Save
    - Load
    - Extensions
    """

    def __init__(self, queue: Queue):
        super().__init__()
        self.queue = queue
        self.init_ui()
        self.connect_signals()
        self.default_savepath = ""
        self.default_loadpath = ""

    def init_ui(self):
        """Initialize the user interface components."""
        # Create the main vertical layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        # Queue button
        self.queue_button = QtWidgets.QPushButton("Q")
        self.queue_button.setFont(QtGui.QFont("Arial", 18))
        self.queue_button.setToolTip("Show queue")
        self.queue_button.setFixedSize(64, 64)
        self.queue_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
        """)
        layout.addWidget(self.queue_button)

        # Info button
        self.info_button = QtWidgets.QPushButton()
        self.info_button.setIcon(QtGui.QIcon.fromTheme("dialog-information"))
        self.info_button.setIconSize(QtCore.QSize(24, 24))
        self.info_button.setToolTip("Show queue information")
        self.info_button.setFixedSize(64, 64)
        self.info_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
        """)
        layout.addWidget(self.info_button)

        # Instruments button
        self.instruments_button = QtWidgets.QPushButton()
        self.instruments_button.setIcon(QtGui.QIcon.fromTheme("media-playback-start"))
        self.instruments_button.setToolTip("Show instruments")
        self.instruments_button.setIconSize(QtCore.QSize(24, 24))
        self.instruments_button.setFixedSize(64, 64)
        self.instruments_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
        """)
        layout.addWidget(self.instruments_button)

        # Presets button
        self.presets_button = QtWidgets.QPushButton("P")
        self.presets_button.setToolTip("Choose queue preset")
        self.presets_button.setFont(QtGui.QFont("Arial", 18))
        self.presets_button.setIconSize(QtCore.QSize(24, 24))
        self.presets_button.setFixedSize(64, 64)
        self.presets_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
        """)
        layout.addWidget(self.presets_button)

        # Save button
        self.save_button = QtWidgets.QPushButton()
        self.save_button.setIcon(QtGui.QIcon.fromTheme("document-save"))
        self.save_button.setToolTip("Save queue to file")
        self.save_button.setIconSize(QtCore.QSize(24, 24))
        self.save_button.setFixedSize(64, 64)
        self.save_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
        """)
        layout.addWidget(self.save_button)

        # Load button
        self.load_button = QtWidgets.QPushButton()
        self.load_button.setIcon(QtGui.QIcon.fromTheme("document-open"))
        self.load_button.setIconSize(QtCore.QSize(24, 24))
        self.load_button.setToolTip("Load queue from file")
        self.load_button.setFixedSize(64, 64)
        self.load_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
        """)
        layout.addWidget(self.load_button)

        # Extensions button
        self.extensions_button = QtWidgets.QPushButton()
        self.extensions_button.setIcon(QtGui.QIcon.fromTheme("applications-system"))
        self.extensions_button.setIconSize(QtCore.QSize(24, 24))
        self.extensions_button.setToolTip("Show extensions")
        self.extensions_button.setFixedSize(64, 64)
        self.extensions_button.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
        """)
        layout.addWidget(self.extensions_button)
        layout.addStretch()
        self.setLayout(layout)
        self.setFixedWidth(96)
    
    def connect_signals(self):
        """Connect signals to their respective slots."""
        self.queue_button.clicked.connect(self.on_queue_clicked)
        self.info_button.clicked.connect(self.on_info_clicked)
        self.instruments_button.clicked.connect(self.on_instruments_clicked)
        self.presets_button.clicked.connect(self.on_presets_clicked)
        self.save_button.clicked.connect(self.on_save_clicked)
        self.load_button.clicked.connect(self.on_load_clicked)
        self.extensions_button.clicked.connect(self.on_extensions_clicked)
    
    def on_queue_clicked(self):
        """Handle the queue button click event."""
        print("Queue button clicked")
        # Implement the logic to show the queue
    def on_info_clicked(self):
        """Handle the info button click event."""
        print("Info button clicked")
        # Implement the logic to show queue information
    def on_instruments_clicked(self):
        """Handle the instruments button click event."""
        print("Instruments button clicked")
        # Implement the logic to show instruments
    def on_presets_clicked(self):
        """Handle the presets button click event."""
        print("Presets button clicked")
        # Implement the logic to load queue from file

    def on_save_clicked(self):
        """Handle the save button click event."""
        print("Save button clicked")
        options = QtWidgets.QFileDialog.Options() # type: ignore
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Queue", self.default_savepath, "Pickle Files (*.pkl);;All Files (*)", options=options)
        if file_path:
            self.default_savepath = file_path
            with open(file_path, 'wb') as f:
                pickle.dump(self.queue, f)
            print(f"Queue saved to {file_path}")

    def on_load_clicked(self):
        """Handle the load button click event."""
        print("Load button clicked")
        options = QtWidgets.QFileDialog.Options() # type: ignore
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Queue", self.default_loadpath, "Pickle Files (*.pkl);;All Files (*)", options=options)
        if file_path:
            self.default_loadpath = file_path
            with open(file_path, 'rb') as f:
                loaded_queue = pickle.load(f)
                if isinstance(loaded_queue, Queue):
                    self.queue = loaded_queue
                    print(f"Queue loaded from {file_path}")
                else:
                    print("Error: Loaded file is not a Queue instance")
    
    def on_extensions_clicked(self):
        """Handle the extensions button click event."""
        print("Extensions button clicked")
        # Implement the logic to show extensions

# Example usage:
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    example_queue = Queue(QID="ExampleQueue")
    queue_bar = QueueBar(queue=example_queue)
    queue_bar.show()
    sys.exit(app.exec())
    

