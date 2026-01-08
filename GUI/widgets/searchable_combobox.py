"""
Searchable ComboBox Widget
==========================
A dropdown widget with search functionality for selecting items from a list.
Can be used with database integration for dynamic data loading.
"""

from typing import Optional, List, Dict, Any, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QCompleter, QLineEdit, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QStringListModel

from GUI.theme import Theme


class SearchableComboBox(QWidget):
    """
    A widget combining a label with a searchable dropdown.
    
    Features:
    - Type to filter items
    - Shows display text but stores ID
    - Can load items dynamically from database
    - Falls back to text entry when database not available
    """
    
    # Signal emitted when selection changes (id, display_text)
    selection_changed = Signal(object, str)
    
    # Signal emitted when text changes (for non-database mode)
    text_changed = Signal(str)
    
    def __init__(
        self, 
        label: str, 
        placeholder: str = "",
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        
        self._label_text = label
        self._placeholder = placeholder
        self._items: List[Dict[str, Any]] = []
        self._selected_id: Optional[int] = None
        self._database_mode = False
        self._data_loader: Optional[Callable[[], List[Dict]]] = None
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Label
        self.label = QLabel(self._label_text)
        self.label.setFixedWidth(120)
        self.label.setStyleSheet(f"color: {Theme.colors.text_primary};")
        layout.addWidget(self.label)
        
        # Combo box (editable for search)
        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo.setMinimumHeight(30)
        
        line_edit = self.combo.lineEdit()
        if line_edit:
            line_edit.setPlaceholderText(self._placeholder)
        
        # Setup completer for search
        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.combo.setCompleter(self.completer)
        
        # Connect signals
        self.combo.currentIndexChanged.connect(self._on_index_changed)
        line_edit = self.combo.lineEdit()
        if line_edit:
            line_edit.textChanged.connect(self._on_text_changed)
        
        layout.addWidget(self.combo)
        
        # Apply styling
        self._apply_style()
    
    def _apply_style(self):
        """Apply theme styling."""
        c = Theme.colors
        self.combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {c.background_tertiary};
                border: 1px solid {c.border_medium};
                border-radius: 4px;
                padding: 5px 10px;
                color: {c.text_primary};
                font-size: 13px;
            }}
            QComboBox:focus {{
                border-color: {c.accent_primary};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 10px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {c.text_secondary};
            }}
            QComboBox QAbstractItemView {{
                background-color: {c.background_secondary};
                border: 1px solid {c.border_medium};
                selection-background-color: {c.accent_primary};
                selection-color: {c.text_primary};
            }}
        """)
    
    def set_database_mode(self, enabled: bool, data_loader: Optional[Callable[[], List[Dict]]] = None):
        """
        Enable or disable database mode.
        
        In database mode, items are loaded from a data loader function.
        In non-database mode, the combo acts as a simple text entry.
        
        Args:
            enabled: Whether to enable database mode
            data_loader: Function that returns list of dicts with 'id' and 'display' keys
        """
        self._database_mode = enabled
        self._data_loader = data_loader
        
        if enabled and data_loader:
            self.load_items()
        else:
            # Clear items and allow free text entry
            self.combo.clear()
            self._items = []
            self._selected_id = None
    
    def load_items(self):
        """Load items from the data loader."""
        if not self._data_loader:
            return
        
        try:
            self._items = self._data_loader()
            self._update_combo_items()
        except Exception as e:
            print(f"[SearchableComboBox] Failed to load items: {e}")
            self._items = []
    
    def _update_combo_items(self):
        """Update the combo box with current items."""
        # Store current text
        current_text = self.combo.currentText()
        
        # Block signals during update
        self.combo.blockSignals(True)
        
        self.combo.clear()
        self.combo.addItem("")  # Empty option
        
        display_texts = [""]
        for item in self._items:
            display = item.get('display', str(item.get('id', '')))
            self.combo.addItem(display, item.get('id'))
            display_texts.append(display)
        
        # Update completer
        self.completer.setModel(QStringListModel(display_texts))
        
        # Restore text if possible
        if current_text:
            index = self.combo.findText(current_text)
            if index >= 0:
                self.combo.setCurrentIndex(index)
            else:
                self.combo.setCurrentText(current_text)
        
        self.combo.blockSignals(False)
    
    def _on_index_changed(self, index: int):
        """Handle combo box selection change."""
        if index <= 0:
            self._selected_id = None
            self.selection_changed.emit(None, "")
        else:
            item_id = self.combo.itemData(index)
            self._selected_id = item_id
            display = self.combo.currentText()
            self.selection_changed.emit(item_id, display)
    
    def _on_text_changed(self, text: str):
        """Handle text changes."""
        self.text_changed.emit(text)
        
        # In database mode, try to match text to an item
        if self._database_mode and text:
            for i, item in enumerate(self._items):
                if item.get('display', '').lower() == text.lower():
                    self._selected_id = item.get('id')
                    self.selection_changed.emit(self._selected_id, text)
                    return
        
        # No match found or not in database mode
        if not self._database_mode:
            self.selection_changed.emit(None, text)
    
    def get_selected_id(self) -> Optional[int]:
        """Get the currently selected item ID (database mode only)."""
        return self._selected_id
    
    def get_text(self) -> str:
        """Get the current text value."""
        return self.combo.currentText()
    
    def set_selected_id(self, item_id: Optional[int]):
        """
        Set selection by item ID.
        
        Args:
            item_id: The ID to select, or None to clear
        """
        self._selected_id = item_id
        
        if item_id is None:
            self.combo.setCurrentIndex(0)
            return
        
        # Find item with matching ID
        for i in range(self.combo.count()):
            if self.combo.itemData(i) == item_id:
                self.combo.setCurrentIndex(i)
                return
        
        # ID not found, try to find in items list for display
        for item in self._items:
            if item.get('id') == item_id:
                self.combo.setCurrentText(item.get('display', str(item_id)))
                return
    
    def set_text(self, text: str):
        """
        Set the combo box text directly.
        
        Args:
            text: The text to set
        """
        # Try to find matching item first
        index = self.combo.findText(text, Qt.MatchFlag.MatchExactly)
        if index >= 0:
            self.combo.setCurrentIndex(index)
            self._selected_id = self.combo.itemData(index)
        else:
            self.combo.setCurrentText(text)
            self._selected_id = None
    
    def get_data(self) -> Dict[str, Any]:
        """
        Get widget data as dictionary.
        
        Returns:
            Dict with label as key, containing id and text
        """
        return {
            self._label_text: {
                'id': self._selected_id,
                'text': self.combo.currentText()
            }
        }
    
    def set_data(self, data: Dict[str, Any]):
        """
        Set widget data from dictionary.
        
        Args:
            data: Dict with label as key containing id and/or text
        """
        if self._label_text not in data:
            return
        
        value = data[self._label_text]
        
        if isinstance(value, dict):
            # New format with id and text
            if 'id' in value and value['id'] is not None:
                self.set_selected_id(value['id'])
            elif 'text' in value:
                self.set_text(value['text'])
        else:
            # Legacy format - just text
            self.set_text(str(value) if value else "")
    
    def clear(self):
        """Clear the selection."""
        self.combo.setCurrentIndex(0)
        self._selected_id = None


class SampleSelectWidget(SearchableComboBox):
    """Specialized searchable combo for selecting samples."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Sample", "Select or search sample...", parent)
    
    def setup_database(self, db_service):
        """
        Setup database connection for loading samples.
        
        Args:
            db_service: DatabaseService instance
        """
        def load_samples():
            return db_service.get_samples_simple_list()
        
        self.set_database_mode(True, load_samples)


class ProjectSelectWidget(SearchableComboBox):
    """Specialized searchable combo for selecting projects."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Project", "Select or search project...", parent)
    
    def setup_database(self, db_service):
        """
        Setup database connection for loading projects.
        
        Args:
            db_service: DatabaseService instance
        """
        def load_projects():
            return db_service.get_projects_simple_list()
        
        self.set_database_mode(True, load_projects)


# Testing
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
    from GUI.theme import apply_theme
    
    app = QApplication(sys.argv)
    apply_theme(app)
    
    window = QMainWindow()
    window.setWindowTitle("SearchableComboBox Test")
    window.resize(400, 200)
    
    central = QWidget()
    layout = QVBoxLayout(central)
    
    # Test widgets
    sample_widget = SampleSelectWidget()
    project_widget = ProjectSelectWidget()
    
    # Add some test items
    sample_widget._items = [
        {'id': 1, 'display': 'S-2026-001 - Test Sample 1 (Silicon)'},
        {'id': 2, 'display': 'S-2026-002 - Test Sample 2 (GaAs)'},
        {'id': 3, 'display': 'S-2026-003 - Test Sample 3 (InP)'},
    ]
    sample_widget._database_mode = True
    sample_widget._update_combo_items()
    
    project_widget._items = [
        {'id': 1, 'display': 'Project Alpha (PA)'},
        {'id': 2, 'display': 'Project Beta (PB)'},
        {'id': 3, 'display': 'Project Gamma (PG)'},
    ]
    project_widget._database_mode = True
    project_widget._update_combo_items()
    
    layout.addWidget(sample_widget)
    layout.addWidget(project_widget)
    layout.addStretch()
    
    window.setCentralWidget(central)
    window.show()
    
    sys.exit(app.exec())
