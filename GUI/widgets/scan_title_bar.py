import sys
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import Signal
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from pybirch.scan.scan import Scan, get_empty_scan
import pickle

# Import theme
try:
    from GUI.theme import Theme, apply_theme
except ImportError:
    try:
        from theme import Theme, apply_theme
    except ImportError:
        Theme = None
        apply_theme = None

# Import preset manager
try:
    from GUI.widgets.preset_manager import PresetManager, PresetDialog
except ImportError:
    try:
        from widgets.preset_manager import PresetManager, PresetDialog
    except ImportError:
        PresetManager = None
        PresetDialog = None

class ScanTitleBar(QtWidgets.QWidget):
    """
    A title bar widget for the scan interface with various control buttons.
    Contains the 'Scan' label on the left and right-aligned buttons for:
    - Info
    - WandB
    - Presets
    - Save/Load
    """
    
    # Signal emitted when info button is clicked
    info_clicked = Signal()
    
    # Signal emitted when a scan preset is loaded
    scan_preset_loaded = Signal(object)
    
    # Signal emitted when state should be saved before preset operations
    save_state_requested = Signal()
    
    def __init__(self, scan: Scan, title: str = "Scan"):
        super().__init__()
        self.scan = scan
        self.init_ui(title)
        self.connect_signals()
        self.default_savepath = ""
        self.default_loadpath = ""
    
    def set_title(self, title: str):
        """Update the title displayed in the title bar"""
        self.scan_label.setText(title if title else "Scan")

    def init_ui(self, title: str):
        """Initialize the user interface components."""
        # Create the main horizontal layout
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        # Add "Scan" label on the left
        self.scan_label = QtWidgets.QLabel(title)
        if Theme:
            self.scan_label.setStyleSheet(Theme.title_label_style())
        else:
            self.scan_label.setStyleSheet("""
                QLabel {
                    font-size: 16px;
                    font-weight: bold;
                }
            """)
        layout.addWidget(self.scan_label)
        
        # Add stretch to push buttons to the right
        layout.addStretch()
        
        # Create button container for right-aligned buttons
        button_container = QtWidgets.QWidget()
        button_layout = QtWidgets.QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(4)
        
        # Info button
        self.info_button = QtWidgets.QPushButton("ℹ")
        self.info_button.setToolTip("Show scan information")
        self.info_button.setFixedSize(32, 32)
        self.info_button.setFont(QtGui.QFont("Segoe UI", 14))
        if Theme:
            self.info_button.setStyleSheet(Theme.icon_button_style())
        else:
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
        self.wandb_button = QtWidgets.QPushButton("🌐")
        self.wandb_button.setToolTip("WandB integration")
        self.wandb_button.setFixedSize(32, 32)
        self.wandb_button.setFont(QtGui.QFont("Segoe UI", 14))
        if Theme:
            self.wandb_button.setStyleSheet(Theme.icon_button_style())
        else:
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
        if Theme:
            self.presets_button.setStyleSheet(Theme.icon_button_style())
        else:
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
        self.save_button = QtWidgets.QPushButton("💾")
        self.save_button.setToolTip("Save configuration")
        self.save_button.setFixedSize(32, 32)
        self.save_button.setFont(QtGui.QFont("Segoe UI", 14))
        if Theme:
            self.save_button.setStyleSheet(Theme.icon_button_style())
        else:
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
        self.load_button = QtWidgets.QPushButton("📂")
        self.load_button.setToolTip("Load configuration")
        self.load_button.setFixedSize(32, 32)
        self.load_button.setFont(QtGui.QFont("Segoe UI", 14))
        if Theme:
            self.load_button.setStyleSheet(Theme.icon_button_style())
        else:
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
        if Theme:
            self.setStyleSheet(f"""
                ScanTitleBar {{
                    background-color: {Theme.colors.background_secondary};
                    border-bottom: 1px solid {Theme.colors.border_light};
                }}
            """)
        else:
            self.setStyleSheet("""
                ScanTitleBar {
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
        self.info_clicked.emit()

    def on_wandb_clicked(self):
        """Handle WandB button click."""
        print("WandB button clicked")
        # TODO: Implement WandB integration

    def on_presets_clicked(self):
        """Handle presets button click."""
        if PresetDialog is None:
            QtWidgets.QMessageBox.warning(self, "Error", "Preset manager not available.")
            return
        
        # Request parent to save current state before showing dialog
        self.save_state_requested.emit()
        
        # Create dialog with current scan only (no queue in scan title bar context)
        dialog = PresetDialog(self, queue=None, scan=self.scan)
        
        # Connect scan preset loaded signal
        dialog.scan_preset_loaded.connect(self.on_scan_preset_loaded)
        
        # Switch to scan presets tab
        dialog.tab_widget.setCurrentIndex(1)
        
        dialog.exec()
    
    def on_scan_preset_loaded(self, scan):
        """Handle when a scan preset is loaded from the dialog."""
        if isinstance(scan, Scan):
            # Update our internal scan reference
            self.scan = scan
            # Emit signal so parent can update
            self.scan_preset_loaded.emit(scan)
            # Update UI
            self.update_ui()

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
                self.save_scan_to_file(file_path)
                self.default_savepath = os.path.dirname(file_path)
            
    def save_scan_to_file(self, file_path: str):
        with open(file_path, 'wb') as f:
            pickle.dump(self.scan, f)

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
                self.load_scan_from_file(file_path)
                self.default_loadpath = os.path.dirname(file_path)

    def load_scan_from_file(self, file_path: str):
        with open(file_path, 'rb') as f:
            self.scan = pickle.load(f)
            self.update_ui()

    def update_ui(self):
        """Update the UI elements based on the current scan state."""
        pass

def main():
    """Test the ScanTitleBar widget."""
    app = QtWidgets.QApplication(sys.argv)
    
    # Apply theme if available
    if Theme and apply_theme:
        apply_theme(app)
    
    # Create a main window to display the title bar
    main_window = QtWidgets.QMainWindow()
    main_window.setWindowTitle("Scan Title Bar Test")
    main_window.resize(600, 400)
    
    # Create and set the title bar as a widget
    title_bar = ScanTitleBar(get_empty_scan())
    central_widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(central_widget)
    layout.addWidget(title_bar)
    layout.addStretch()  # Push title bar to top
    
    main_window.setCentralWidget(central_widget)
    main_window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()