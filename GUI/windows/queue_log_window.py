# Copyright (C) 2025
# Queue Log Window Widget for PyBirch
from __future__ import annotations

import sys
import os
from typing import Optional, List, Dict
from datetime import datetime

# Add path to parent directories for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame, QTextEdit,
    QLabel, QPushButton, QMainWindow, QComboBox, QCheckBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QApplication, QToolBar, QStatusBar, QGroupBox, QScrollArea
)
from PySide6.QtGui import QColor, QTextCharFormat, QFont, QBrush, QAction

from pybirch.queue.queue import Queue, ScanState, QueueState, ScanHandle, LogEntry

# Import theme
try:
    from GUI.theme import Theme, apply_theme, get_status_color
except ImportError:
    from theme import Theme, apply_theme, get_status_color


class LogTextEdit(QTextEdit):
    """Custom text edit for displaying logs with color formatting."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setFont(Theme.get_font(monospace=True, size=Theme.fonts.size_sm))
        # Use white background to match theme
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Theme.colors.background_primary};
                color: {Theme.colors.text_primary};
                border: 1px solid {Theme.colors.border_medium};
                border-radius: {Theme.BORDER_RADIUS_SM}px;
                padding: 8px;
            }}
        """)
        
        # Color formats for different log levels using theme colors
        self.formats = {
            "INFO": self._create_format(Theme.colors.log_info),
            "WARNING": self._create_format(Theme.colors.log_warning),
            "ERROR": self._create_format(Theme.colors.log_error),
            "DEBUG": self._create_format(Theme.colors.log_debug),
        }
        
        # Default format - use primary text color for light background
        self.default_format = self._create_format(Theme.colors.text_primary)
        
    def _create_format(self, color: str) -> QTextCharFormat:
        """Create a text format with the specified color."""
        fmt = QTextCharFormat()
        fmt.setForeground(QBrush(QColor(color)))
        return fmt
        
    def append_log(self, entry: LogEntry):
        """Append a log entry with appropriate formatting."""
        fmt = self.formats.get(entry.level, self.default_format)
        
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(str(entry) + "\n", fmt)
        
        # Auto-scroll to bottom
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class ScanStatusWidget(QFrame):
    """Widget showing the status of a single scan."""
    
    def __init__(self, handle: ScanHandle, parent=None):
        super().__init__(parent)
        self.handle = handle
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.init_ui()
        self.update_display()
        
    def init_ui(self):
        """Initialize the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Scan name
        self.name_label = QLabel()
        self.name_label.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {Theme.colors.text_primary};")
        self.name_label.setFont(Theme.get_font(bold=True))
        self.name_label.setMinimumWidth(150)
        layout.addWidget(self.name_label)
        
        # Status indicator
        self.status_label = QLabel()
        self.status_label.setFixedWidth(80)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Progress bar (text-based)
        self.progress_label = QLabel()
        self.progress_label.setFixedWidth(100)
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_label)
        
        # Duration
        self.duration_label = QLabel()
        self.duration_label.setFixedWidth(80)
        self.duration_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.duration_label)
        
        layout.addStretch()
        
    def update_display(self):
        """Update the display based on current handle state."""
        scan = self.handle.scan
        state = self.handle.state
        
        # Name
        self.name_label.setText(scan.scan_settings.scan_name or "Unnamed")
        
        # Status with color
        state_colors = {
            ScanState.QUEUED: ("#666", "#e0e0e0"),
            ScanState.RUNNING: ("white", "#0078d4"),
            ScanState.PAUSED: (Theme.colors.text_primary, Theme.colors.accent_warning),
            ScanState.COMPLETED: (Theme.colors.text_inverse, Theme.colors.accent_success),
            ScanState.ABORTED: (Theme.colors.text_inverse, "#fd7e14"),
            ScanState.FAILED: (Theme.colors.text_inverse, Theme.colors.accent_error),
        }
        fg, bg = state_colors.get(state, (Theme.colors.text_primary, Theme.colors.border_medium))
        self.status_label.setText(state.name)
        self.status_label.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border-radius: {Theme.BORDER_RADIUS_SM}px; padding: 2px;"
        )
        
        # Progress
        progress = int(self.handle.progress * 100)
        self.progress_label.setText(f"{progress}%")
        
        # Duration
        if self.handle.duration is not None:
            mins, secs = divmod(int(self.handle.duration), 60)
            self.duration_label.setText(f"{mins:02d}:{secs:02d}")
        else:
            self.duration_label.setText("--:--")
            
        # Background color based on state using theme colors
        if state == ScanState.RUNNING:
            self.setStyleSheet(f"QFrame {{ background-color: {Theme.colors.background_hover}; }}")
        elif state == ScanState.PAUSED:
            self.setStyleSheet(f"QFrame {{ background-color: {Theme.colors.status_paused}; }}")
        elif state == ScanState.FAILED:
            self.setStyleSheet(f"QFrame {{ background-color: {Theme.colors.status_failed}; }}")
        else:
            self.setStyleSheet("")


class QueueLogWindow(QMainWindow):
    """
    Window for displaying queue logs and scan status.
    
    Shows:
    - Live log output from all scans
    - Status overview of all scans in the queue
    - Filtering options for logs
    """
    
    def __init__(self, queue: Queue, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.queue = queue
        
        # Track scan status widgets
        self.scan_widgets: Dict[str, ScanStatusWidget] = {}
        
        # Log filter settings
        self.filter_scan_id: Optional[str] = None
        self.filter_level: Optional[str] = None
        self.auto_scroll = True
        
        # Update timer
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_status_display)
        self.update_timer.start(500)  # Update every 500ms
        
        self.init_ui()
        
        self.setWindowTitle("Queue Log Viewer")
        self.resize(1000, 700)
        
    def init_ui(self):
        """Initialize the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create toolbar
        self.create_toolbar()
        
        # Create splitter for status and logs
        splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(splitter)
        
        # Top section - Scan status overview
        status_group = QGroupBox("Scan Status")
        status_layout = QVBoxLayout(status_group)
        
        # Scroll area for scan widgets
        self.status_scroll = QScrollArea()
        self.status_scroll.setWidgetResizable(True)
        self.status_scroll.setMinimumHeight(100)  # Ensure minimum height for status area
        
        self.status_container = QWidget()
        self.status_layout = QVBoxLayout(self.status_container)
        self.status_layout.setSpacing(4)
        self.status_layout.addStretch()
        
        self.status_scroll.setWidget(self.status_container)
        status_layout.addWidget(self.status_scroll)
        
        splitter.addWidget(status_group)
        
        # Bottom section - Log output
        log_group = QGroupBox("Log Output")
        log_layout = QVBoxLayout(log_group)
        
        # Filter bar
        filter_layout = QHBoxLayout()
        
        filter_label = QLabel("Filter:")
        filter_layout.addWidget(filter_label)
        
        # Scan filter
        scan_label = QLabel("Scan:")
        filter_layout.addWidget(scan_label)
        
        self.scan_filter_combo = QComboBox()
        self.scan_filter_combo.addItem("All Scans", None)
        self.scan_filter_combo.setMinimumWidth(150)
        self.scan_filter_combo.currentIndexChanged.connect(self._on_scan_filter_changed)
        self.scan_filter_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {Theme.colors.background_primary};
                color: {Theme.colors.text_primary};
                border: 1px solid {Theme.colors.border_medium};
                border-radius: {Theme.BORDER_RADIUS_SM}px;
                padding: 6px 10px;
            }}
            QComboBox:hover {{
                border-color: {Theme.colors.accent_primary};
            }}
            QComboBox::drop-down {{
                border: none;
                background: transparent;
                width: 24px;
            }}
            QComboBox::down-arrow {{
                image: none;
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {Theme.colors.text_secondary};
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Theme.colors.background_primary};
                border: 1px solid {Theme.colors.border_medium};
                selection-background-color: {Theme.colors.accent_primary};
                selection-color: {Theme.colors.text_inverse};
            }}
        """)
        filter_layout.addWidget(self.scan_filter_combo)
        
        # Level filter
        level_label = QLabel("Level:")
        filter_layout.addWidget(level_label)
        
        self.level_filter_combo = QComboBox()
        self.level_filter_combo.addItem("All Levels", None)
        self.level_filter_combo.addItem("INFO", "INFO")
        self.level_filter_combo.addItem("WARNING", "WARNING")
        self.level_filter_combo.addItem("ERROR", "ERROR")
        self.level_filter_combo.addItem("DEBUG", "DEBUG")
        self.level_filter_combo.currentIndexChanged.connect(self._on_level_filter_changed)
        self.level_filter_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {Theme.colors.background_primary};
                color: {Theme.colors.text_primary};
                border: 1px solid {Theme.colors.border_medium};
                border-radius: {Theme.BORDER_RADIUS_SM}px;
                padding: 6px 10px;
            }}
            QComboBox:hover {{
                border-color: {Theme.colors.accent_primary};
            }}
            QComboBox::drop-down {{
                border: none;
                background: transparent;
                width: 24px;
            }}
            QComboBox::down-arrow {{
                image: none;
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {Theme.colors.text_secondary};
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Theme.colors.background_primary};
                border: 1px solid {Theme.colors.border_medium};
                selection-background-color: {Theme.colors.accent_primary};
                selection-color: {Theme.colors.text_inverse};
            }}
        """)
        filter_layout.addWidget(self.level_filter_combo)
        
        filter_layout.addStretch()
        
        # Auto-scroll checkbox
        self.auto_scroll_check = QCheckBox("Auto-scroll")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.stateChanged.connect(self._on_auto_scroll_changed)
        filter_layout.addWidget(self.auto_scroll_check)
        
        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_logs)
        filter_layout.addWidget(clear_btn)
        
        log_layout.addLayout(filter_layout)
        
        # Log text display
        self.log_text = LogTextEdit()
        log_layout.addWidget(self.log_text)
        
        splitter.addWidget(log_group)
        
        # Set splitter proportions - give more space to status section initially
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        # Set initial sizes: status area gets 150px, log gets the rest
        splitter.setSizes([150, 400])
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Initial population
        self.update_status_display()
        self.update_scan_filter_combo()
        self.reload_filtered_logs()
        
    def create_toolbar(self):
        """Create the toolbar."""
        toolbar = QToolBar("Log Controls")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Export logs button
        export_btn = QPushButton("📥 Export Logs")
        export_btn.setToolTip("Export logs to a file")
        export_btn.clicked.connect(self.export_logs)
        toolbar.addWidget(export_btn)
        
        toolbar.addSeparator()
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setToolTip("Refresh status display")
        refresh_btn.clicked.connect(self.refresh_all)
        toolbar.addWidget(refresh_btn)
        
        toolbar.addSeparator()
        
        # Queue status label
        self.queue_status_label = QLabel("Queue: IDLE")
        self.queue_status_label.setStyleSheet(f"font-weight: bold; padding: 4px; color: {Theme.colors.text_secondary};")
        toolbar.addWidget(self.queue_status_label)
        
    def add_log_entry(self, entry: LogEntry):
        """Add a log entry to the display."""
        # Check filters
        if self.filter_scan_id and entry.scan_id != self.filter_scan_id:
            return
        if self.filter_level and entry.level != self.filter_level:
            return
            
        # Add to text display
        self.log_text.append_log(entry)
        
        # Update scan filter combo if new scan
        self.update_scan_filter_combo()
        
    def update_status_display(self):
        """Update the scan status display."""
        # Update queue status label
        status = self.queue.get_status()
        state_colors = {
            "IDLE": Theme.colors.text_secondary,
            "RUNNING": Theme.colors.accent_primary,
            "PAUSED": Theme.colors.accent_warning,
            "STOPPING": "#fd7e14",
        }
        color = state_colors.get(status["state"], Theme.colors.text_primary)
        self.queue_status_label.setText(f"Queue: {status['state']}")
        self.queue_status_label.setStyleSheet(f"font-weight: bold; padding: 4px; color: {color};")
        
        # Update or create scan widgets
        current_scan_ids = set()
        
        for handle in self.queue._scan_handles:
            scan_id = handle.scan_id
            current_scan_ids.add(scan_id)
            
            if scan_id in self.scan_widgets:
                # Update existing widget
                self.scan_widgets[scan_id].handle = handle
                self.scan_widgets[scan_id].update_display()
            else:
                # Create new widget
                widget = ScanStatusWidget(handle)
                self.scan_widgets[scan_id] = widget
                # Insert before stretch
                self.status_layout.insertWidget(self.status_layout.count() - 1, widget)
                
        # Remove widgets for scans no longer in queue
        for scan_id in list(self.scan_widgets.keys()):
            if scan_id not in current_scan_ids:
                widget = self.scan_widgets.pop(scan_id)
                self.status_layout.removeWidget(widget)
                widget.deleteLater()
                
        # Update status bar
        running = len([h for h in self.queue._scan_handles if h.state == ScanState.RUNNING])
        total = len(self.queue._scan_handles)
        self.status_bar.showMessage(f"Total: {total} scans | Running: {running}")
        
    def update_scan_filter_combo(self):
        """Update the scan filter combo box with current scans."""
        current_selection = self.scan_filter_combo.currentData()
        
        self.scan_filter_combo.blockSignals(True)
        self.scan_filter_combo.clear()
        self.scan_filter_combo.addItem("All Scans", None)
        
        for handle in self.queue._scan_handles:
            self.scan_filter_combo.addItem(
                handle.scan.scan_settings.scan_name or handle.scan_id,
                handle.scan_id
            )
            
        # Restore selection
        for i in range(self.scan_filter_combo.count()):
            if self.scan_filter_combo.itemData(i) == current_selection:
                self.scan_filter_combo.setCurrentIndex(i)
                break
                
        self.scan_filter_combo.blockSignals(False)
        
    def _on_scan_filter_changed(self, index: int):
        """Handle scan filter change."""
        self.filter_scan_id = self.scan_filter_combo.itemData(index)
        self.reload_filtered_logs()
        
    def _on_level_filter_changed(self, index: int):
        """Handle level filter change."""
        self.filter_level = self.level_filter_combo.itemData(index)
        self.reload_filtered_logs()
        
    def _on_auto_scroll_changed(self, state: int):
        """Handle auto-scroll checkbox change."""
        self.auto_scroll = state == Qt.CheckState.Checked.value
        
    def reload_filtered_logs(self):
        """Reload logs with current filter settings."""
        self.log_text.clear()
        
        logs = self.queue.get_logs(
            scan_id=self.filter_scan_id if self.filter_scan_id else None,
            level=self.filter_level if self.filter_level else None
        )
        
        for entry in logs:
            self.log_text.append_log(entry)
            
    def clear_logs(self):
        """Clear the log display (not the queue's log history)."""
        self.log_text.clear()
        
    def refresh_all(self):
        """Refresh all displays."""
        self.update_status_display()
        self.reload_filtered_logs()
        
    def export_logs(self):
        """Export logs to a file."""
        from PySide6.QtWidgets import QFileDialog
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Logs", "", "Text Files (*.txt);;Log Files (*.log);;All Files (*)"
        )
        
        if filepath:
            try:
                logs = self.queue.get_logs(
                    scan_id=self.filter_scan_id if self.filter_scan_id else None,
                    level=self.filter_level if self.filter_level else None
                )
                
                with open(filepath, 'w') as f:
                    f.write(f"PyBirch Queue Log Export\n")
                    f.write(f"Queue ID: {self.queue.QID}\n")
                    f.write(f"Exported: {datetime.now().isoformat()}\n")
                    f.write("=" * 60 + "\n\n")
                    
                    for entry in logs:
                        f.write(str(entry) + "\n")
                        
                self.status_bar.showMessage(f"Logs exported to {filepath}", 5000)
                
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Export Error", f"Failed to export logs: {str(e)}")
                
    def closeEvent(self, event):
        """Handle window close event."""
        self.update_timer.stop()
        event.accept()


def main():
    """Test the QueueLogWindow widget."""
    app = QApplication(sys.argv)
    apply_theme(app)
    
    from pybirch.scan.scan import get_empty_scan
    
    # Create a test queue with some scans
    queue = Queue("test_queue")
    
    for i in range(3):
        scan = get_empty_scan()
        scan.scan_settings.scan_name = f"Test Scan {i + 1}"
        queue.enqueue(scan)
    
    # Add some test log entries
    queue._log("test_1", "Test Scan 1", "INFO", "This is an info message")
    queue._log("test_1", "Test Scan 1", "WARNING", "This is a warning message")
    queue._log("test_2", "Test Scan 2", "ERROR", "This is an error message")
    
    window = QueueLogWindow(queue)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
