# Copyright (C) 2025
# Queue Page Widget for PyBirch
from __future__ import annotations

import sys
import os
from typing import Optional, List, Set

# Add path to parent directories for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from PySide6.QtCore import Qt, Signal, Slot, QTimer, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame, QListWidget,
    QListWidgetItem, QLabel, QPushButton, QMenuBar, QMenu, QToolBar,
    QMainWindow, QStackedWidget, QMessageBox, QComboBox, QProgressBar,
    QAbstractItemView, QApplication, QStyle, QCheckBox
)
from PySide6.QtGui import QAction, QIcon, QColor, QFont

from pybirch.queue.queue import Queue, ScanState, QueueState, ExecutionMode, ScanHandle, LogEntry
from pybirch.scan.scan import Scan, get_empty_scan

# Import theme
try:
    from GUI.theme import Theme, apply_theme, get_status_color
except ImportError:
    from theme import Theme, apply_theme, get_status_color

# Import sibling modules
try:
    from windows.scan_page import ScanPage
    from windows.queue_log_window import QueueLogWindow
except ImportError:
    from GUI.windows.scan_page import ScanPage
    from GUI.windows.queue_log_window import QueueLogWindow


class ScanListItemWidget(QWidget):
    """Custom widget for displaying scan information with right-justified status."""
    
    # Signal emitted when checkbox state changes
    checkbox_changed = Signal(int, bool)  # index, checked
    
    def __init__(self, handle: ScanHandle, index: int, parent=None):
        super().__init__(parent)
        self.handle = handle
        self.index = index
        # Make widget background transparent so selection highlight shows through
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.init_ui()
        self.update_display()
        
    def init_ui(self):
        """Initialize the UI layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        # Checkbox on the left with transparent background
        self.checkbox = QCheckBox()
        self.checkbox.setStyleSheet("QCheckBox { background: transparent; }")
        self.checkbox.stateChanged.connect(self._on_checkbox_changed)
        layout.addWidget(self.checkbox)
        
        # Left side: scan name
        self.name_label = QLabel()
        self.name_label.setFont(Theme.get_font(size=Theme.fonts.size_base, bold=True))
        self.name_label.setStyleSheet(f"color: {Theme.colors.text_primary}; background: transparent;")
        
        layout.addWidget(self.name_label, 1)
        
        # Right side: status label (right-justified)
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.status_label.setFont(Theme.get_font(size=Theme.fonts.size_sm, bold=True))
        self.status_label.setMinimumWidth(80)
        
        layout.addWidget(self.status_label)
        
    def update_display(self):
        """Update the display based on scan state."""
        scan = self.handle.scan
        state = self.handle.state
        
        # Update labels
        name = scan.scan_settings.scan_name or "Unnamed Scan"
        self.name_label.setText(name)
        
        # Status with progress if applicable
        status_text = state.name
        if self.handle.progress > 0:
            status_text += f" ({self.handle.progress * 100:.0f}%)"
        self.status_label.setText(status_text)
        
        # Status color
        status_color = get_status_color(state.name)
        self.status_label.setStyleSheet(f"""
            color: {status_color};
            padding: 2px 6px;
            border-radius: 3px;
        """)
    
    def _on_checkbox_changed(self, state):
        """Handle checkbox state change."""
        self.checkbox_changed.emit(self.index, state == Qt.CheckState.Checked.value)
    
    def is_checked(self) -> bool:
        """Return whether the checkbox is checked."""
        return self.checkbox.isChecked()
    
    def set_checked(self, checked: bool):
        """Set the checkbox state."""
        self.checkbox.setChecked(checked)


class ScanListItem(QListWidgetItem):
    """Custom list item for displaying scan information with checkbox."""
    
    def __init__(self, handle: ScanHandle, index: int):
        super().__init__()
        self.handle = handle
        self.scan_index = index
        self.widget: Optional[ScanListItemWidget] = None
        self.update_display()
        
    def update_display(self):
        """Update the display text and styling based on scan state."""
        scan = self.handle.scan
        state = self.handle.state
        
        # Build display text (fallback for when widget isn't set)
        name = scan.scan_settings.scan_name or "Unnamed Scan"
        project = scan.scan_settings.project_name or "No Project"
        status = state.name
        progress = f"{self.handle.progress * 100:.0f}%" if self.handle.progress > 0 else ""
        
        display_text = f"{name}\n{project}"
        if progress:
            display_text += f" ({progress})"
            
        self.setText(display_text)
        
        # Update the custom widget if it exists
        if self.widget:
            self.widget.update_display()
        
        # Set background color based on state using theme
        bg_color = get_status_color(state.name)
        self.setBackground(QColor(bg_color))
        
        # Set font using theme
        font = Theme.get_font(size=Theme.fonts.size_sm)
        if state == ScanState.RUNNING:
            font.setBold(True)
        self.setFont(font)
        
        # Set size hint for two-line display
        self.setSizeHint(QSize(200, 50))
        self.setSizeHint(QSize(200, 50))


class QueueListWidget(QListWidget):
    """Custom list widget for the scan queue with selection and checkbox support."""
    
    # Signal emitted when a scan is highlighted (clicked)
    scan_highlighted = Signal(int)  # Emits scan index
    # Signal emitted when checkbox selection changes
    selection_changed = Signal(list)  # Emits list of selected indices
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.itemClicked.connect(self._on_item_clicked)
        
        # Enable context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        
        # Set very light grey highlight color
        self.setStyleSheet("""
            QListWidget::item:selected {
                background-color: #f0f0f0;
            }
            QListWidget::item:selected:active {
                background-color: #f0f0f0;
            }
        """)
        
    def _on_item_clicked(self, item: ScanListItem):
        """Handle item click - emit highlight signal."""
        if isinstance(item, ScanListItem):
            self.scan_highlighted.emit(item.scan_index)
    
    def _show_context_menu(self, position):
        """Show context menu at the given position."""
        item = self.itemAt(position)
        
        # Get parent queue page to access methods
        parent_page = self.parent()
        while parent_page and not isinstance(parent_page, QueuePage):
            parent_page = parent_page.parent()
        
        if not parent_page:
            return
        
        menu = QMenu(self)
        
        if not isinstance(item, ScanListItem):
            # Clicked on empty space - show "Add New Scan" option
            add_action = menu.addAction("Add New Scan")
            add_action.triggered.connect(parent_page.add_new_scan)
            menu.exec(self.mapToGlobal(position))
            return
        
        # Start action
        start_action = menu.addAction("Start")
        start_action.triggered.connect(lambda: parent_page.start_single_scan(item.scan_index))
        
        # Pause action
        pause_action = menu.addAction("Pause")
        pause_action.triggered.connect(lambda: parent_page.pause_single_scan(item.scan_index))
        
        # Resume action
        resume_action = menu.addAction("Resume")
        resume_action.triggered.connect(lambda: parent_page.resume_single_scan(item.scan_index))
        
        menu.addSeparator()
        
        # Abort action
        abort_action = menu.addAction("Abort")
        abort_action.triggered.connect(lambda: parent_page.abort_single_scan(item.scan_index))
        
        # Restart action
        restart_action = menu.addAction("Restart")
        restart_action.triggered.connect(lambda: parent_page.restart_single_scan(item.scan_index))
        
        menu.addSeparator()
        
        # Move up action
        move_up_action = menu.addAction("Move Up")
        move_up_action.triggered.connect(lambda: parent_page.move_scan_to(item.scan_index, item.scan_index - 1))
        move_up_action.setEnabled(item.scan_index > 0)
        
        # Move down action
        move_down_action = menu.addAction("Move Down")
        move_down_action.triggered.connect(lambda: parent_page.move_scan_to(item.scan_index, item.scan_index + 1))
        move_down_action.setEnabled(item.scan_index < self.count() - 1)
        
        menu.addSeparator()
        
        # Remove action
        remove_action = menu.addAction("Remove")
        remove_action.triggered.connect(lambda: parent_page.remove_scan_at(item.scan_index))
        
        menu.exec(self.mapToGlobal(position))
    
    def _on_widget_checkbox_changed(self, index: int, checked: bool):
        """Handle checkbox change from widget."""
        self._emit_selection()
        
    def _emit_selection(self):
        """Emit the current checkbox selection."""
        selected_indices = []
        for i in range(self.count()):
            item = self.item(i)
            if isinstance(item, ScanListItem) and item.widget and item.widget.is_checked():
                selected_indices.append(item.scan_index)
        self.selection_changed.emit(selected_indices)
        
    def get_checked_indices(self) -> List[int]:
        """Get list of checked scan indices."""
        indices = []
        for i in range(self.count()):
            item = self.item(i)
            if isinstance(item, ScanListItem) and item.widget and item.widget.is_checked():
                indices.append(item.scan_index)
        return indices
    
    def select_all(self):
        """Check all items."""
        for i in range(self.count()):
            item = self.item(i)
            if isinstance(item, ScanListItem) and item.widget:
                item.widget.set_checked(True)
                
    def deselect_all(self):
        """Uncheck all items."""
        for i in range(self.count()):
            item = self.item(i)
            if isinstance(item, ScanListItem) and item.widget:
                item.widget.set_checked(False)


class QueuePage(QMainWindow):
    """
    Main queue management page that combines:
    - Menu bar at the top with queue controls and navigation
    - Queue list on the left with checkboxes and click-to-highlight
    - Scan page on the right showing the currently highlighted scan
    """
    
    # Signal to open log window
    open_log_window = Signal()
    
    def __init__(self, queue: Optional[Queue] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Initialize queue
        self.queue = queue if queue is not None else Queue("default_queue")
        
        # Currently highlighted scan index
        self.highlighted_index: Optional[int] = None
        
        # Log window reference
        self.log_window: Optional[QueueLogWindow] = None
        
        # Store configured instruments from adapter manager
        self.configured_instruments: Optional[List] = None
        
        # Update timer for refreshing the queue list
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.refresh_queue_list)
        self.update_timer.start(1000)  # Update every second
        
        self.init_ui()
        self.connect_signals()
        self.setup_queue_callbacks()
        
        self.setWindowTitle("Queue Manager")
        self.resize(1400, 900)
        
    def init_ui(self):
        """Initialize the user interface."""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create toolbar
        self.create_toolbar()
        
        # Create main content area with splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)
        
        # Left panel - Queue list
        self.create_queue_panel()
        
        # Right panel - Scan details
        self.create_scan_panel()
        
        # Set splitter proportions (30% queue, 70% scan details)
        self.splitter.setStretchFactor(0, 30)
        self.splitter.setStretchFactor(1, 70)
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
    def create_menu_bar(self):
        """Create the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        new_scan_action = QAction("&New Scan", self)
        new_scan_action.setShortcut("Ctrl+N")
        new_scan_action.triggered.connect(self.add_new_scan)
        file_menu.addAction(new_scan_action)
        
        file_menu.addSeparator()
        
        save_queue_action = QAction("&Save Queue", self)
        save_queue_action.setShortcut("Ctrl+S")
        save_queue_action.triggered.connect(self.save_queue)
        file_menu.addAction(save_queue_action)
        
        load_queue_action = QAction("&Load Queue", self)
        load_queue_action.setShortcut("Ctrl+O")
        load_queue_action.triggered.connect(self.load_queue)
        file_menu.addAction(load_queue_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Queue menu
        queue_menu = menubar.addMenu("&Queue")
        
        start_action = QAction("&Start Selected", self)
        start_action.setShortcut("F5")
        start_action.triggered.connect(self.start_selected_scans)
        queue_menu.addAction(start_action)
        
        start_all_action = QAction("Start &All", self)
        start_all_action.setShortcut("Shift+F5")
        start_all_action.triggered.connect(self.start_all_scans)
        queue_menu.addAction(start_all_action)
        
        queue_menu.addSeparator()
        
        pause_action = QAction("&Pause Selected", self)
        pause_action.triggered.connect(self.pause_selected_scans)
        queue_menu.addAction(pause_action)
        
        resume_action = QAction("&Resume Selected", self)
        resume_action.triggered.connect(self.resume_selected_scans)
        queue_menu.addAction(resume_action)
        
        queue_menu.addSeparator()
        
        abort_action = QAction("A&bort Selected", self)
        abort_action.triggered.connect(self.abort_selected_scans)
        queue_menu.addAction(abort_action)
        
        restart_action = QAction("R&estart Selected", self)
        restart_action.triggered.connect(self.restart_selected_scans)
        queue_menu.addAction(restart_action)
        
        queue_menu.addSeparator()
        
        clear_action = QAction("&Clear Completed", self)
        clear_action.triggered.connect(self.clear_completed)
        queue_menu.addAction(clear_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        log_action = QAction("&Log Window", self)
        log_action.setShortcut("Ctrl+L")
        log_action.triggered.connect(self.show_log_window)
        view_menu.addAction(log_action)
        
        view_menu.addSeparator()
        
        refresh_action = QAction("&Refresh", self)
        refresh_action.setShortcut("F6")
        refresh_action.triggered.connect(self.refresh_queue_list)
        view_menu.addAction(refresh_action)
        
        # Execution mode submenu
        mode_menu = view_menu.addMenu("Execution &Mode")
        
        self.serial_mode_action = QAction("&Serial", self)
        self.serial_mode_action.setCheckable(True)
        self.serial_mode_action.setChecked(True)
        self.serial_mode_action.triggered.connect(lambda: self.set_execution_mode(ExecutionMode.SERIAL))
        mode_menu.addAction(self.serial_mode_action)
        
        self.parallel_mode_action = QAction("&Parallel", self)
        self.parallel_mode_action.setCheckable(True)
        self.parallel_mode_action.triggered.connect(lambda: self.set_execution_mode(ExecutionMode.PARALLEL))
        mode_menu.addAction(self.parallel_mode_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def create_toolbar(self):
        """Create the toolbar with quick access buttons."""
        toolbar = QToolBar("Queue Controls")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Add scan button
        add_btn = QPushButton("➕ Add Scan")
        add_btn.setToolTip("Add a new scan to the queue")
        add_btn.clicked.connect(self.add_new_scan)
        toolbar.addWidget(add_btn)
        
        toolbar.addSeparator()
        
        # Start button
        self.start_btn = QPushButton("▶ Start")
        self.start_btn.setToolTip("Start selected scans (or all if none selected)")
        self.start_btn.clicked.connect(self.start_selected_or_all)
        self.start_btn.setStyleSheet(Theme.success_button_style())
        toolbar.addWidget(self.start_btn)
        
        # Pause button
        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.setToolTip("Pause selected scans")
        self.pause_btn.clicked.connect(self.pause_selected_scans)
        self.pause_btn.setStyleSheet(Theme.warning_button_style())
        toolbar.addWidget(self.pause_btn)
        
        # Resume button
        self.resume_btn = QPushButton("▶ Resume")
        self.resume_btn.setToolTip("Resume selected scans")
        self.resume_btn.clicked.connect(self.resume_selected_scans)
        self.resume_btn.setStyleSheet(Theme.primary_button_style())
        toolbar.addWidget(self.resume_btn)
        
        # Abort button
        self.abort_btn = QPushButton("⏹ Abort")
        self.abort_btn.setToolTip("Abort selected scans")
        self.abort_btn.clicked.connect(self.abort_selected_scans)
        self.abort_btn.setStyleSheet(Theme.danger_button_style())
        toolbar.addWidget(self.abort_btn)
        
        toolbar.addSeparator()
        
        # Execution mode selector
        mode_label = QLabel("Mode: ")
        toolbar.addWidget(mode_label)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Serial", ExecutionMode.SERIAL)
        self.mode_combo.addItem("Parallel", ExecutionMode.PARALLEL)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_combo_changed)
        toolbar.addWidget(self.mode_combo)
        
        toolbar.addSeparator()
        
        # Log window button
        log_btn = QPushButton("📋 Logs")
        log_btn.setToolTip("Open the queue log window")
        log_btn.clicked.connect(self.show_log_window)
        toolbar.addWidget(log_btn)
        
        # Add stretch
        spacer = QWidget()
        spacer.setFixedWidth(20)
        toolbar.addWidget(spacer)
        
        # Queue status label
        self.status_label = QLabel("Queue: IDLE | 0 scans")
        toolbar.addWidget(self.status_label)
        
    def create_queue_panel(self):
        """Create the left panel with queue list."""
        queue_frame = QFrame()
        queue_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        queue_layout = QVBoxLayout(queue_frame)
        queue_layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        header_layout = QHBoxLayout()
        
        queue_label = QLabel("Scan Queue")
        queue_label.setStyleSheet(Theme.section_title_style())
        header_layout.addWidget(queue_label)
        
        header_layout.addStretch()
        
        # Select all / Deselect all buttons
        select_all_btn = QPushButton("Select All")
        select_all_btn.setFixedWidth(80)
        select_all_btn.clicked.connect(self._select_all_scans)
        header_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Deselect")
        deselect_all_btn.setFixedWidth(80)
        deselect_all_btn.clicked.connect(self._deselect_all_scans)
        header_layout.addWidget(deselect_all_btn)
        
        queue_layout.addLayout(header_layout)
        
        # Queue list
        self.queue_list = QueueListWidget()
        queue_layout.addWidget(self.queue_list)
        
        # Bottom controls
        bottom_layout = QHBoxLayout()
        
        move_up_btn = QPushButton("↑")
        move_up_btn.setToolTip("Move selected scan up")
        move_up_btn.setFixedWidth(40)
        move_up_btn.clicked.connect(self.move_scan_up)
        bottom_layout.addWidget(move_up_btn)
        
        move_down_btn = QPushButton("↓")
        move_down_btn.setToolTip("Move selected scan down")
        move_down_btn.setFixedWidth(40)
        move_down_btn.clicked.connect(self.move_scan_down)
        bottom_layout.addWidget(move_down_btn)
        
        bottom_layout.addStretch()
        
        remove_btn = QPushButton("Remove")
        remove_btn.setToolTip("Remove highlighted scan from queue")
        remove_btn.clicked.connect(self.remove_highlighted_scan)
        bottom_layout.addWidget(remove_btn)
        
        queue_layout.addLayout(bottom_layout)
        
        self.splitter.addWidget(queue_frame)
        
    def create_scan_panel(self):
        """Create the right panel with scan details."""
        scan_frame = QFrame()
        scan_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        scan_layout = QVBoxLayout(scan_frame)
        scan_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header for scan details
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 10, 10, 10)
        
        self.scan_header_label = QLabel("No Scan Selected")
        self.scan_header_label.setStyleSheet(Theme.section_title_style())
        header_layout.addWidget(self.scan_header_label)
        
        header_layout.addStretch()
        
        # Progress bar for current scan
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setVisible(False)
        header_layout.addWidget(self.progress_bar)
        
        # State label
        self.state_label = QLabel("")
        self.state_label.setStyleSheet(f"font-weight: bold; padding: 4px 8px; border-radius: {Theme.BORDER_RADIUS_SM}px;")
        header_layout.addWidget(self.state_label)
        
        scan_layout.addWidget(header_widget)
        
        # Stacked widget to show either placeholder or scan page
        self.scan_stack = QStackedWidget()
        
        # Placeholder widget
        placeholder = QWidget()
        placeholder_layout = QVBoxLayout(placeholder)
        placeholder_label = QLabel("Select a scan from the queue to view details")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_label.setStyleSheet(f"color: {Theme.colors.text_secondary}; font-size: {Theme.fonts.size_lg}px;")
        placeholder_layout.addWidget(placeholder_label)
        self.scan_stack.addWidget(placeholder)
        
        # Scan page (will be created when a scan is selected)
        self.scan_page: Optional[ScanPage] = None
        
        scan_layout.addWidget(self.scan_stack)
        
        self.splitter.addWidget(scan_frame)
        
    def connect_signals(self):
        """Connect signals between components."""
        self.queue_list.scan_highlighted.connect(self.on_scan_highlighted)
        self.queue_list.selection_changed.connect(self.on_selection_changed)
        
    def setup_queue_callbacks(self):
        """Setup callbacks for queue events."""
        self.queue.add_log_callback(self._on_log_entry)
        self.queue.add_state_callback(self._on_state_change)
        self.queue.add_progress_callback(self._on_progress_update)
        
    def _on_log_entry(self, entry: LogEntry):
        """Handle log entries from the queue."""
        # Forward to log window if open
        if self.log_window and self.log_window.isVisible():
            self.log_window.add_log_entry(entry)
            
    def _on_state_change(self, scan_id: str, state: ScanState):
        """Handle scan state changes."""
        # Refresh the queue list to show updated states
        QTimer.singleShot(0, self.refresh_queue_list)
        
    def _on_progress_update(self, scan_id: str, progress: float):
        """Handle progress updates."""
        # Update progress bar if this is the highlighted scan
        if self.highlighted_index is not None:
            handle = self.queue.get_handle(self.highlighted_index)
            if handle.scan_id == scan_id:
                self.progress_bar.setValue(int(progress * 100))
                
    def _on_mode_combo_changed(self, index: int):
        """Handle execution mode combo box change."""
        mode = self.mode_combo.itemData(index)
        self.set_execution_mode(mode)
        
    # ==================== Queue List Management ====================
    
    def refresh_queue_list(self):
        """Refresh the queue list display."""
        # Store current highlight
        current_highlight = self.highlighted_index
        
        # Block signals during update
        self.queue_list.blockSignals(True)
        
        # Remember checked items
        checked_indices = self.queue_list.get_checked_indices()
        
        self.queue_list.clear()
        
        for i, handle in enumerate(self.queue._scan_handles):
            item = ScanListItem(handle, i)
            # Clear text since we're using a custom widget
            item.setText("")
            self.queue_list.addItem(item)
            
            # Create and set custom widget for right-justified status
            widget = ScanListItemWidget(handle, i)
            item.widget = widget
            # Restore checked state
            if i in checked_indices:
                widget.set_checked(True)
            # Connect checkbox signal
            widget.checkbox_changed.connect(self.queue_list._on_widget_checkbox_changed)
            self.queue_list.setItemWidget(item, widget)
            
        # Restore highlight
        if current_highlight is not None and current_highlight < self.queue_list.count():
            self.queue_list.setCurrentRow(current_highlight)
            
        self.queue_list.blockSignals(False)
        
        # Update status label
        status = self.queue.get_status()
        self.status_label.setText(
            f"Queue: {status['state']} | {status['total_scans']} scans"
        )
        
        # Update highlighted scan details if visible
        if self.highlighted_index is not None:
            self._update_highlighted_scan_display()
            
    def _select_all_scans(self):
        """Select all scans."""
        self.queue_list.select_all()
        
    def _deselect_all_scans(self):
        """Deselect all scans."""
        self.queue_list.deselect_all()
        
    # ==================== Scan Highlighting ====================
    
    @Slot(int)
    def on_scan_highlighted(self, index: int):
        """Handle when a scan is highlighted (clicked)."""
        self.highlighted_index = index
        
        if index < 0 or index >= self.queue.size():
            self._show_placeholder()
            return
            
        handle = self.queue.get_handle(index)
        
        # Update header
        self.scan_header_label.setText(
            f"{handle.scan.scan_settings.scan_name} - {handle.scan.scan_settings.project_name}"
        )
        
        # Update state label
        self._update_state_label(handle.state)
        
        # Update progress bar
        if handle.is_active():
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(int(handle.progress * 100))
        else:
            self.progress_bar.setVisible(False)
        
        # Create or update scan page
        if self.scan_page is not None:
            # Save current scan page state before removing
            self.scan_page.save_tree_to_scan()
            
            # Remove old scan page
            self.scan_stack.removeWidget(self.scan_page)
            self.scan_page.deleteLater()
            
        # Pass configured instruments to ScanPage
        self.scan_page = ScanPage(handle.scan, available_instruments=self.configured_instruments)
        # Connect scan_info_changed signal to refresh queue list immediately
        self.scan_page.scan_info_changed.connect(self.refresh_queue_list)
        self.scan_stack.addWidget(self.scan_page)
        self.scan_stack.setCurrentWidget(self.scan_page)
        
    def _update_highlighted_scan_display(self):
        """Update the display for the currently highlighted scan."""
        if self.highlighted_index is None:
            return
            
        if self.highlighted_index >= self.queue.size():
            self._show_placeholder()
            return
            
        handle = self.queue.get_handle(self.highlighted_index)
        self._update_state_label(handle.state)
        
        if handle.is_active():
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(int(handle.progress * 100))
        else:
            self.progress_bar.setVisible(False)
            
    def _update_state_label(self, state: ScanState):
        """Update the state label appearance."""
        state_styles = {
            ScanState.QUEUED: ("Queued", f"background-color: {Theme.colors.background_tertiary}; color: {Theme.colors.text_primary};"),
            ScanState.RUNNING: ("Running", f"background-color: {Theme.colors.accent_primary}; color: {Theme.colors.text_inverse};"),
            ScanState.PAUSED: ("Paused", f"background-color: {Theme.colors.accent_warning}; color: {Theme.colors.text_primary};"),
            ScanState.COMPLETED: ("Completed", f"background-color: {Theme.colors.accent_success}; color: {Theme.colors.text_inverse};"),
            ScanState.ABORTED: ("Aborted", "background-color: #fd7e14; color: white;"),
            ScanState.FAILED: ("Failed", f"background-color: {Theme.colors.accent_error}; color: {Theme.colors.text_inverse};"),
        }
        
        text, style = state_styles.get(state, ("Unknown", ""))
        self.state_label.setText(text)
        self.state_label.setStyleSheet(f"font-weight: bold; padding: 4px 8px; border-radius: {Theme.BORDER_RADIUS_SM}px; {style}")
        
    def _show_placeholder(self):
        """Show the placeholder widget."""
        self.highlighted_index = None
        self.scan_header_label.setText("No Scan Selected")
        self.state_label.setText("")
        self.progress_bar.setVisible(False)
        self.scan_stack.setCurrentIndex(0)
        
    @Slot(list)
    def on_selection_changed(self, indices: List[int]):
        """Handle checkbox selection changes."""
        # Could update UI based on selection, e.g., enable/disable buttons
        pass
        
    # ==================== Queue Operations ====================
    
    def add_new_scan(self):
        """Add a new empty scan to the queue."""
        new_scan = get_empty_scan()
        new_scan.scan_settings.scan_name = f"Scan_{self.queue.size() + 1}"
        self.queue.enqueue(new_scan)
        self.refresh_queue_list()
        
        # Highlight the new scan
        self.queue_list.setCurrentRow(self.queue.size() - 1)
        self.on_scan_highlighted(self.queue.size() - 1)
        
    def remove_highlighted_scan(self):
        """Remove the currently highlighted scan."""
        if self.highlighted_index is None:
            return
            
        try:
            self.queue.dequeue(self.highlighted_index)
            self.refresh_queue_list()
            self._show_placeholder()
        except RuntimeError as e:
            QMessageBox.warning(self, "Cannot Remove", str(e))
            
    def move_scan_up(self):
        """Move the highlighted scan up in the queue."""
        if self.highlighted_index is None or self.highlighted_index <= 0:
            return
            
        try:
            self.queue.move_scan(self.highlighted_index, self.highlighted_index - 1)
            self.highlighted_index -= 1
            self.refresh_queue_list()
            self.queue_list.setCurrentRow(self.highlighted_index)
        except Exception as e:
            QMessageBox.warning(self, "Cannot Move", str(e))
            
    def move_scan_down(self):
        """Move the highlighted scan down in the queue."""
        if self.highlighted_index is None or self.highlighted_index >= self.queue.size() - 1:
            return
            
        try:
            self.queue.move_scan(self.highlighted_index, self.highlighted_index + 1)
            self.highlighted_index += 1
            self.refresh_queue_list()
            self.queue_list.setCurrentRow(self.highlighted_index)
        except Exception as e:
            QMessageBox.warning(self, "Cannot Move", str(e))
    
    # ==================== Context Menu Helper Methods ====================
    
    def start_single_scan(self, index: int):
        """Start a single scan by index."""
        try:
            self.queue.start(indices=[index])
            self.refresh_queue_list()
        except RuntimeError as e:
            QMessageBox.warning(self, "Cannot Start", str(e))
    
    def pause_single_scan(self, index: int):
        """Pause a single scan by index."""
        try:
            handle = self.queue.get_handle(index)
            self.queue.pause(handle.scan_id)
            self.refresh_queue_list()
        except Exception as e:
            QMessageBox.warning(self, "Cannot Pause", str(e))
    
    def resume_single_scan(self, index: int):
        """Resume a single scan by index."""
        try:
            handle = self.queue.get_handle(index)
            self.queue.resume(handle.scan_id)
            self.refresh_queue_list()
        except Exception as e:
            QMessageBox.warning(self, "Cannot Resume", str(e))
    
    def abort_single_scan(self, index: int):
        """Abort a single scan by index."""
        try:
            handle = self.queue.get_handle(index)
            self.queue.abort(handle.scan_id)
            self.refresh_queue_list()
        except Exception as e:
            QMessageBox.warning(self, "Cannot Abort", str(e))
    
    def restart_single_scan(self, index: int):
        """Restart a single scan by index."""
        try:
            handle = self.queue.get_handle(index)
            self.queue.restart(handle.scan_id)
            self.refresh_queue_list()
        except Exception as e:
            QMessageBox.warning(self, "Cannot Restart", str(e))
    
    def remove_scan_at(self, index: int):
        """Remove a scan at the given index."""
        try:
            self.queue.dequeue(index)
            self.refresh_queue_list()
            if self.highlighted_index == index:
                self._show_placeholder()
        except RuntimeError as e:
            QMessageBox.warning(self, "Cannot Remove", str(e))
    
    def move_scan_to(self, from_index: int, to_index: int):
        """Move a scan from one index to another."""
        if to_index < 0 or to_index >= self.queue.size():
            return
        try:
            self.queue.move_scan(from_index, to_index)
            if self.highlighted_index == from_index:
                self.highlighted_index = to_index
            self.refresh_queue_list()
            self.queue_list.setCurrentRow(to_index)
        except Exception as e:
            QMessageBox.warning(self, "Cannot Move", str(e))
            
    # ==================== Scan Execution Controls ====================
    
    def start_selected_or_all(self):
        """Start selected scans, or all if none selected."""
        indices = self.queue_list.get_checked_indices()
        if indices:
            self.start_selected_scans()
        else:
            self.start_all_scans()
            
    def start_selected_scans(self):
        """Start the selected (checked) scans."""
        indices = self.queue_list.get_checked_indices()
        if not indices:
            QMessageBox.information(self, "No Selection", "Please select scans to start using the checkboxes.")
            return
            
        try:
            self.queue.start(indices=indices)
            self.refresh_queue_list()
        except RuntimeError as e:
            QMessageBox.warning(self, "Cannot Start", str(e))
            
    def start_all_scans(self):
        """Start all queued scans."""
        try:
            self.queue.start()
            self.refresh_queue_list()
        except RuntimeError as e:
            QMessageBox.warning(self, "Cannot Start", str(e))
            
    def pause_selected_scans(self):
        """Pause the selected scans."""
        indices = self.queue_list.get_checked_indices()
        if not indices:
            # Pause entire queue
            self.queue.pause()
        else:
            for i in indices:
                handle = self.queue.get_handle(i)
                self.queue.pause(handle.scan_id)
        self.refresh_queue_list()
        
    def resume_selected_scans(self):
        """Resume the selected scans."""
        indices = self.queue_list.get_checked_indices()
        if not indices:
            # Resume entire queue
            self.queue.resume()
        else:
            for i in indices:
                handle = self.queue.get_handle(i)
                self.queue.resume(handle.scan_id)
        self.refresh_queue_list()
        
    def abort_selected_scans(self):
        """Abort the selected scans."""
        indices = self.queue_list.get_checked_indices()
        if not indices:
            # Confirm aborting entire queue
            reply = QMessageBox.question(
                self, "Abort All",
                "No scans selected. Abort entire queue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.queue.abort()
        else:
            for i in indices:
                handle = self.queue.get_handle(i)
                self.queue.abort(handle.scan_id)
        self.refresh_queue_list()
        
    def restart_selected_scans(self):
        """Restart the selected scans."""
        indices = self.queue_list.get_checked_indices()
        if not indices:
            QMessageBox.information(self, "No Selection", "Please select scans to restart using the checkboxes.")
            return
            
        for i in indices:
            try:
                handle = self.queue.get_handle(i)
                self.queue.restart(handle.scan_id)
            except Exception as e:
                QMessageBox.warning(self, "Cannot Restart", f"Error restarting scan: {str(e)}")
        self.refresh_queue_list()
        
    def clear_completed(self):
        """Clear completed/aborted/failed scans from the queue."""
        # Remove finished scans from the end to avoid index issues
        indices_to_remove = []
        for i, handle in enumerate(self.queue._scan_handles):
            if handle.is_finished():
                indices_to_remove.append(i)
                
        for i in reversed(indices_to_remove):
            try:
                self.queue.dequeue(i)
            except Exception:
                pass
                
        self.refresh_queue_list()
        if self.highlighted_index is not None and self.highlighted_index >= self.queue.size():
            self._show_placeholder()
            
    # ==================== Execution Mode ====================
    
    def set_execution_mode(self, mode: ExecutionMode):
        """Set the queue execution mode."""
        try:
            self.queue.execution_mode = mode
            
            # Update UI
            self.serial_mode_action.setChecked(mode == ExecutionMode.SERIAL)
            self.parallel_mode_action.setChecked(mode == ExecutionMode.PARALLEL)
            self.mode_combo.setCurrentIndex(0 if mode == ExecutionMode.SERIAL else 1)
            
        except RuntimeError as e:
            QMessageBox.warning(self, "Cannot Change Mode", str(e))
            
    # ==================== File Operations ====================
    
    def save_queue(self):
        """Save the queue to a file."""
        from PySide6.QtWidgets import QFileDialog
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Queue", "", "Queue Files (*.queue);;All Files (*)"
        )
        
        if filepath:
            try:
                self.queue.save(filepath)
                self.statusBar().showMessage(f"Queue saved to {filepath}", 5000)
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save queue: {str(e)}")
                
    def load_queue(self):
        """Load a queue from a file."""
        from PySide6.QtWidgets import QFileDialog
        
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Queue", "", "Queue Files (*.queue);;All Files (*)"
        )
        
        if filepath:
            try:
                self.queue = Queue.load(filepath)
                self.setup_queue_callbacks()
                self.refresh_queue_list()
                self._show_placeholder()
                self.statusBar().showMessage(f"Queue loaded from {filepath}", 5000)
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to load queue: {str(e)}")
                
    # ==================== Log Window ====================
    
    def show_log_window(self):
        """Show the queue log window."""
        if self.log_window is None:
            self.log_window = QueueLogWindow(self.queue, self)
            
        # Populate with existing logs
        for entry in self.queue.get_logs():
            self.log_window.add_log_entry(entry)
            
        self.log_window.show()
        self.log_window.raise_()
        self.log_window.activateWindow()
        
    # ==================== Help ====================
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self, "About Queue Manager",
            "PyBirch Queue Manager\n\n"
            "Manage and execute scan queues with real-time monitoring.\n\n"
            "Features:\n"
            "• Serial or parallel scan execution\n"
            "• Pause, resume, and abort controls\n"
            "• Live logging and progress tracking\n"
            "• Queue persistence (save/load)"
        )
        
    def closeEvent(self, event):
        """Handle window close event."""
        # Stop the update timer
        self.update_timer.stop()
        
        # Close log window if open
        if self.log_window:
            self.log_window.close()
            
        # Check for running scans
        running = self.queue.get_handles_by_state(ScanState.RUNNING)
        if running:
            reply = QMessageBox.question(
                self, "Scans Running",
                f"{len(running)} scan(s) are still running. Abort and close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            else:
                self.queue.abort()
                
        event.accept()
    
    def set_configured_instruments(self, configured_instruments: List):
        """
        Set the configured instruments from adapter manager.
        This will be used when creating new ScanPage instances.
        
        Args:
            configured_instruments: List of dicts with keys: 'name', 'adapter', 'nickname', 'class', 'instance'
        """
        self.configured_instruments = configured_instruments
        
        # If a scan page is currently displayed, update it with the new instruments
        if self.scan_page is not None and self.highlighted_index is not None:
            # Refresh the current scan page to use new instruments
            self.on_scan_highlighted(self.highlighted_index)


def main():
    """Test the QueuePage widget."""
    app = QApplication(sys.argv)
    apply_theme(app)
    
    # Create a test queue with some scans
    queue = Queue("test_queue")
    
    for i in range(3):
        scan = get_empty_scan()
        scan.scan_settings.scan_name = f"Test Scan {i + 1}"
        scan.scan_settings.project_name = "Test Project"
        queue.enqueue(scan)
    
    window = QueuePage(queue)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
