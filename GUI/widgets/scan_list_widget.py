import sys
from PySide6 import QtCore, QtWidgets, QtGui
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from pybirch.scan.scan import Scan, get_empty_scan
from pybirch.queue.queue import Queue
import pickle


class ScanTableWidget(QtWidgets.QWidget):
    """
    A widget to display and manage a list of scans in a table format.
    Includes buttons for adding, removing, and clearing scans.
    """

    def __init__(self, queue: Queue):
        super().__init__()
        self.queue = queue
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        """Initialize the user interface components."""
        # Create the main vertical layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        # Create the table widget
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(4)
        # set initial column width
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 100)
        self.table.setHorizontalHeaderLabels(["Name", "Status", "Type", "Job"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows) # type: ignore
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers) # type: ignore
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection) # type: ignore
        layout.addWidget(self.table)

        # increase row height for better readability
        self.table.verticalHeader().setDefaultSectionSize(45)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet("""
            QTableWidget {
                border: none;
            }
            QTableWidget::item {
                padding: 4px 8px;
            }
        """)

        # Increase font size for better readability
        font = QtGui.QFont()
        font.setPointSize(10)
        self.table.setFont(font)
        self.table.horizontalHeader().setFont(font)

        # Create button container for action buttons
        button_container = QtWidgets.QWidget()
        button_layout = QtWidgets.QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(4)
        
        # Add Scan button
        self.add_button = QtWidgets.QPushButton("Add Scan")
        self.add_button.setToolTip("Add a new scan")
        button_layout.addWidget(self.add_button)
        
        # Remove Scan button
        self.remove_button = QtWidgets.QPushButton("Remove Scan")
        self.remove_button.setToolTip("Remove the selected scan")
        button_layout.addWidget(self.remove_button)
        
        # Clear All button
        self.clear_button = QtWidgets.QPushButton("Clear All")
        self.clear_button.setToolTip("Clear all scans from the list")
        button_layout.addWidget(self.clear_button)

        # Save/Load Queue Buttons
        self.save_button = QtWidgets.QPushButton("Save Queue")
        self.save_button.setToolTip("Save the current queue to a file")
        button_layout.addWidget(self.save_button)
        self.load_button = QtWidgets.QPushButton("Load Queue")
        self.load_button.setToolTip("Load a queue from a file")
        button_layout.addWidget(self.load_button)
        
        # Add stretch to push buttons to the left
        button_layout.addStretch()
        
        layout.addWidget(button_container)
        
        # Populate the table with initial data
        self.refresh_table()
        self.table.resizeColumnsToContents()

        if not self.queue.scans:
            self.add_scan()
            self.table.resizeColumnsToContents()
            self.queue.scans.pop(0)
            self.refresh_table()

    def connect_signals(self):
        """Connect signals to their respective slots."""
        self.add_button.clicked.connect(self.add_scan)
        self.remove_button.clicked.connect(self.remove_scan)
        self.clear_button.clicked.connect(self.clear_scans)
        self.save_button.clicked.connect(self.save_queue)
        self.load_button.clicked.connect(self.load_queue)

    def refresh_table(self):
        """Refresh the table to display the current list of scans."""
        self.table.setRowCount(len(self.queue.scans))
        for row, scan in enumerate(self.queue.scans):
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(scan.scan_settings.scan_name))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(scan.scan_settings.status))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(scan.scan_settings.scan_type))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(scan.scan_settings.job_type))
    
    def add_scan(self):
        """Add a new scan to the list."""
        new_scan = get_empty_scan()
        self.queue.enqueue(new_scan)
        self.refresh_table()

    def remove_scan(self):
        """Remove the selected scan from the list."""
        selected_rows = self.table.selectionModel().selectedRows()
        for index in sorted(selected_rows, reverse=True):
            self.queue.dequeue(index.row())
        self.refresh_table()

    def clear_scans(self):
        """Clear all scans from the list."""
        self.queue.clear()
        self.refresh_table()

    def save_queue(self):
        """Save the current queue to a file."""
        options = QtWidgets.QFileDialog.Options() # type: ignore
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Queue", "", "Pickle Files (*.pkl);;All Files (*)", options=options)
        if file_path:
            with open(file_path, 'wb') as f:
                pickle.dump(self.queue, f)
    
    def load_queue(self):
        """Load a queue from a file."""
        options = QtWidgets.QFileDialog.Options() # type: ignore
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Queue", "", "Pickle Files (*.pkl);;All Files (*)", options=options)
        
        # if there are scans in the current queue, confirm before loading
        if self.queue.scans:
            reply = QtWidgets.QMessageBox.question(self, "Confirm Load", "This will overwrite the current queue. Do you want to continue?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No) # type: ignore
            if reply == QtWidgets.QMessageBox.No: # type: ignore
                return

        if file_path:
            with open(file_path, 'rb') as f:
                self.queue = pickle.load(f)
            self.refresh_table()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")

    # Example usage with dummy data
    queue = Queue(QID="Q001")
    widget = ScanTableWidget(queue)
    widget.resize(600, 400)
    widget.show()
    
    sys.exit(app.exec())