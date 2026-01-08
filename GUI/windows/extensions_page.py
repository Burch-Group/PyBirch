# Copyright (C) 2025
# Extensions Page Widget for PyBirch
"""
Extensions page for managing PyBirch extensions like WebSocket integration,
database sync, and other optional features.
"""

from __future__ import annotations

import sys
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING

# Add path to parent directories for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, 
    QPushButton, QCheckBox, QGroupBox, QScrollArea,
    QLineEdit, QSpinBox, QMessageBox, QSizePolicy
)
from PySide6.QtGui import QFont

# Import theme
try:
    from GUI.theme import Theme
except ImportError:
    from theme import Theme

if TYPE_CHECKING:
    from pybirch.queue.queue import Queue


# Default config path for extension settings
DEFAULT_CONFIG_DIR = Path(__file__).parent.parent.parent / "config" / "default"
EXTENSIONS_CONFIG_FILE = "extensions_config.json"


class ExtensionToggleWidget(QFrame):
    """
    A widget for toggling an extension on/off with description and status.
    """
    
    toggled = Signal(bool)  # Emitted when toggle state changes
    
    def __init__(
        self,
        name: str,
        description: str,
        icon: str = "🔌",
        available: bool = True,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.name = name
        self.description = description
        self.available = available
        
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            ExtensionToggleWidget {{
                background-color: {Theme.colors.background_secondary};
                border: 1px solid {Theme.colors.border_light};
                border-radius: 8px;
                padding: 12px;
            }}
            ExtensionToggleWidget:hover {{
                border-color: {Theme.colors.accent_primary};
            }}
        """)
        
        self.init_ui(icon)
    
    def init_ui(self, icon: str):
        """Initialize the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)
        
        # Icon
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Segoe UI Emoji", 24))
        icon_label.setFixedWidth(40)
        layout.addWidget(icon_label)
        
        # Text content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        # Name
        name_label = QLabel(self.name)
        name_label.setFont(Theme.get_font(size=Theme.fonts.size_lg, bold=True))
        name_label.setStyleSheet(f"color: {Theme.colors.text_primary};")
        text_layout.addWidget(name_label)
        
        # Description
        desc_label = QLabel(self.description)
        desc_label.setFont(Theme.get_font(size=Theme.fonts.size_sm))
        desc_label.setStyleSheet(f"color: {Theme.colors.text_secondary};")
        desc_label.setWordWrap(True)
        text_layout.addWidget(desc_label)
        
        layout.addLayout(text_layout, 1)
        
        # Toggle switch / status
        right_layout = QVBoxLayout()
        right_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        if self.available:
            self.toggle = QCheckBox()
            self.toggle.setStyleSheet(f"""
                QCheckBox {{
                    spacing: 8px;
                }}
                QCheckBox::indicator {{
                    width: 40px;
                    height: 22px;
                    border-radius: 11px;
                    background-color: {Theme.colors.border_light};
                }}
                QCheckBox::indicator:checked {{
                    background-color: {Theme.colors.accent_success};
                }}
            """)
            self.toggle.toggled.connect(self._on_toggled)
            right_layout.addWidget(self.toggle)
            
            self.status_label = QLabel("Disabled")
            self.status_label.setFont(Theme.get_font(size=Theme.fonts.size_sm))
            self.status_label.setStyleSheet(f"color: {Theme.colors.text_secondary};")
            right_layout.addWidget(self.status_label)
        else:
            self.toggle = None
            unavailable_label = QLabel("Not Available")
            unavailable_label.setFont(Theme.get_font(size=Theme.fonts.size_sm, bold=True))
            unavailable_label.setStyleSheet(f"color: {Theme.colors.accent_warning};")
            right_layout.addWidget(unavailable_label)
        
        layout.addLayout(right_layout)
    
    def _on_toggled(self, checked: bool):
        """Handle toggle state change."""
        if self.status_label:
            self.status_label.setText("Enabled" if checked else "Disabled")
            color = Theme.colors.accent_success if checked else Theme.colors.text_secondary
            self.status_label.setStyleSheet(f"color: {color};")
        self.toggled.emit(checked)
    
    def is_enabled(self) -> bool:
        """Check if extension is enabled."""
        return self.toggle.isChecked() if self.toggle else False
    
    def set_enabled(self, enabled: bool):
        """Set the enabled state."""
        if self.toggle:
            self.toggle.setChecked(enabled)


class ExtensionsPage(QWidget):
    """
    Extensions management page for PyBirch.
    
    Allows users to enable/disable:
    - WebSocket Integration (live updates to web dashboard)
    - Database Integration (automatic scan persistence)
    - W&B Integration (experiment tracking)
    """
    
    # Signal emitted when extension settings change
    settings_changed = Signal()
    
    # Signal emitted when database is enabled/disabled (bool enabled, DatabaseService or None)
    database_state_changed = Signal(bool, object)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Extension widgets
        self._extension_widgets: Dict[str, ExtensionToggleWidget] = {}
        
        # Queue reference (set later)
        self._queue: Optional['Queue'] = None
        
        # WebSocket bridge reference
        self._websocket_bridge = None
        
        # Database service and extension factory
        self._db_service = None
        self._database_enabled = False
        
        # Config path
        self.config_dir = DEFAULT_CONFIG_DIR
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.config_dir / EXTENSIONS_CONFIG_FILE
        
        self.init_ui()
        self.connect_signals()
        
        # Load saved settings after a short delay
        QTimer.singleShot(100, self.load_settings)
    
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Header
        header = QLabel("Extensions")
        header.setFont(Theme.get_font(size=24, bold=True))
        header.setStyleSheet(f"color: {Theme.colors.text_primary};")
        layout.addWidget(header)
        
        subtitle = QLabel("Enable or disable optional features and integrations")
        subtitle.setFont(Theme.get_font(size=Theme.fonts.size_base))
        subtitle.setStyleSheet(f"color: {Theme.colors.text_secondary};")
        layout.addWidget(subtitle)
        
        # Scroll area for extensions
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(12)
        
        # Check availability of extensions
        websocket_available = self._check_websocket_available()
        database_available = self._check_database_available()
        wandb_available = self._check_wandb_available()
        
        # WebSocket Integration
        websocket_widget = ExtensionToggleWidget(
            name="WebSocket Integration",
            description="Enable real-time updates to the web dashboard. "
                       "Broadcasts scan progress, status changes, and data points via WebSocket.",
            icon="🌐",
            available=websocket_available
        )
        self._extension_widgets['websocket'] = websocket_widget
        scroll_layout.addWidget(websocket_widget)
        
        # Database Integration
        database_widget = ExtensionToggleWidget(
            name="Database Integration",
            description="Automatically persist scans and measurements to the database. "
                       "Enables scan history, data retrieval, and project management.",
            icon="🗄️",
            available=database_available
        )
        self._extension_widgets['database'] = database_widget
        scroll_layout.addWidget(database_widget)
        
        # W&B Integration
        wandb_widget = ExtensionToggleWidget(
            name="Weights & Biases Integration",
            description="Log experiments to Weights & Biases for tracking, "
                       "visualization, and collaboration.",
            icon="📊",
            available=wandb_available
        )
        self._extension_widgets['wandb'] = wandb_widget
        scroll_layout.addWidget(wandb_widget)
        
        # Server settings group (for WebSocket)
        self.server_settings = QGroupBox("WebSocket Server Settings")
        self.server_settings.setFont(Theme.get_font(size=Theme.fonts.size_base, bold=True))
        server_layout = QVBoxLayout(self.server_settings)
        
        # Server URL
        url_layout = QHBoxLayout()
        url_label = QLabel("Server URL:")
        url_label.setMinimumWidth(100)
        self.server_url_input = QLineEdit("http://localhost:5000")
        self.server_url_input.setPlaceholderText("http://localhost:5000")
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.server_url_input)
        server_layout.addLayout(url_layout)
        
        # Data point interval
        interval_layout = QHBoxLayout()
        interval_label = QLabel("Data broadcast interval:")
        interval_label.setMinimumWidth(100)
        self.data_interval_spin = QSpinBox()
        self.data_interval_spin.setRange(1, 100)
        self.data_interval_spin.setValue(1)
        self.data_interval_spin.setSuffix(" points")
        self.data_interval_spin.setToolTip("Broadcast every N data points (1 = all points)")
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.data_interval_spin)
        interval_layout.addStretch()
        server_layout.addLayout(interval_layout)
        
        scroll_layout.addWidget(self.server_settings)
        
        # Update server settings visibility
        self.server_settings.setVisible(websocket_available)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setStyleSheet(Theme.success_button_style())
        self.save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_btn)
        
        self.apply_btn = QPushButton("Apply Now")
        self.apply_btn.setStyleSheet(Theme.primary_button_style())
        self.apply_btn.clicked.connect(self.apply_settings)
        button_layout.addWidget(self.apply_btn)
        
        layout.addLayout(button_layout)
    
    def connect_signals(self):
        """Connect signals."""
        for widget in self._extension_widgets.values():
            widget.toggled.connect(self._on_extension_toggled)
    
    def _check_websocket_available(self) -> bool:
        """Check if WebSocket integration is available."""
        try:
            from pybirch.database_integration.sync import setup_websocket_integration
            return True
        except ImportError:
            return False
    
    def _check_database_available(self) -> bool:
        """Check if database integration is available."""
        try:
            from database.services import DatabaseService
            return True
        except ImportError:
            return False
    
    def _check_wandb_available(self) -> bool:
        """Check if W&B integration is available."""
        try:
            import wandb
            return True
        except ImportError:
            return False
    
    def _on_extension_toggled(self, checked: bool):
        """Handle extension toggle."""
        self.settings_changed.emit()
    
    def set_queue(self, queue: 'Queue'):
        """Set the queue reference for applying extensions.
        
        Also auto-applies WebSocket integration if enabled in settings.
        """
        self._queue = queue
        
        # Auto-apply WebSocket if enabled in saved settings
        if self._extension_widgets.get('websocket') and self._extension_widgets['websocket'].is_enabled():
            # Use a timer to ensure GUI is fully loaded
            QTimer.singleShot(500, self._auto_enable_websocket)
    
    def _auto_enable_websocket(self):
        """Auto-enable WebSocket integration silently (no message boxes)."""
        if self._queue is None:
            return
        
        try:
            from pybirch.database_integration.sync import (
                setup_websocket_integration,
                check_server_running
            )
            
            server_url = self.server_url_input.text() or "http://localhost:5000"
            
            # Check if server is running (silently)
            if not check_server_running(server_url):
                print(f"[Extensions] WebSocket server not available at {server_url} - skipping auto-enable")
                return
            
            # Disable existing bridge if any
            if self._websocket_bridge is not None:
                self._websocket_bridge.unregister()
            
            # Create new bridge
            self._websocket_bridge = setup_websocket_integration(
                queue=self._queue,
                server_url=server_url
            )
            
            print(f"[Extensions] WebSocket auto-enabled for queue {self._queue.QID}")
            
        except Exception as e:
            print(f"[Extensions] Failed to auto-enable WebSocket: {e}")
    
    def get_settings(self) -> Dict[str, Any]:
        """Get current extension settings."""
        return {
            'websocket': {
                'enabled': self._extension_widgets['websocket'].is_enabled(),
                'server_url': self.server_url_input.text(),
                'data_interval': self.data_interval_spin.value(),
            },
            'database': {
                'enabled': self._extension_widgets['database'].is_enabled(),
            },
            'wandb': {
                'enabled': self._extension_widgets['wandb'].is_enabled(),
            }
        }
    
    def set_settings(self, settings: Dict[str, Any]):
        """Set extension settings."""
        if 'websocket' in settings:
            ws = settings['websocket']
            self._extension_widgets['websocket'].set_enabled(ws.get('enabled', False))
            self.server_url_input.setText(ws.get('server_url', 'http://localhost:5000'))
            self.data_interval_spin.setValue(ws.get('data_interval', 1))
        
        if 'database' in settings:
            db_enabled = settings['database'].get('enabled', False)
            self._extension_widgets['database'].set_enabled(db_enabled)
            # Auto-apply database setting
            if db_enabled:
                self._enable_database()
        
        if 'wandb' in settings:
            self._extension_widgets['wandb'].set_enabled(
                settings['wandb'].get('enabled', False)
            )
    
    def save_settings(self):
        """Save settings to file."""
        try:
            settings = self.get_settings()
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
            
            QMessageBox.information(
                self, "Settings Saved",
                "Extension settings have been saved."
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Save Error",
                f"Failed to save settings: {str(e)}"
            )
    
    def load_settings(self):
        """Load settings from file."""
        if not self.config_path.exists():
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            self.set_settings(settings)
        except Exception as e:
            print(f"Failed to load extension settings: {e}")
    
    def apply_settings(self):
        """Apply current settings (enable/disable extensions)."""
        settings = self.get_settings()
        
        # Apply WebSocket integration
        if settings['websocket']['enabled']:
            self._enable_websocket()
        else:
            self._disable_websocket()
        
        # Apply database integration
        if settings['database']['enabled']:
            self._enable_database()
        else:
            self._disable_database()
        
        # Apply wandb integration (TODO: implement)
        
        QMessageBox.information(
            self, "Settings Applied",
            "Extension settings have been applied."
        )
    
    def _enable_websocket(self):
        """Enable WebSocket integration."""
        if self._queue is None:
            QMessageBox.warning(
                self, "No Queue",
                "No queue available. Open a queue first."
            )
            return
        
        try:
            from pybirch.database_integration.sync import (
                setup_websocket_integration,
                check_server_running
            )
            
            server_url = self.server_url_input.text() or "http://localhost:5000"
            
            # Check if server is running
            if not check_server_running(server_url):
                QMessageBox.warning(
                    self, "Server Not Running",
                    f"Cannot connect to WebSocket server at {server_url}.\n"
                    "Please start the web server first using:\n\n"
                    "  python -m database.run_web"
                )
                return
            
            # Disable existing bridge if any
            if self._websocket_bridge is not None:
                self._websocket_bridge.unregister()
            
            # Create new bridge using server URL (cross-process communication)
            self._websocket_bridge = setup_websocket_integration(
                queue=self._queue,
                server_url=server_url
            )
            
            print(f"[Extensions] WebSocket integration enabled for queue {self._queue.QID}")
            
        except ConnectionError as e:
            QMessageBox.warning(
                self, "Connection Error",
                str(e)
            )
        except Exception as e:
            QMessageBox.warning(
                self, "WebSocket Error",
                f"Failed to enable WebSocket: {str(e)}"
            )
    
    def _disable_websocket(self):
        """Disable WebSocket integration."""
        if self._websocket_bridge is not None:
            self._websocket_bridge.unregister()
            self._websocket_bridge = None
            print("[Extensions] WebSocket integration disabled")
    
    def _enable_database(self):
        """Enable database integration - adds DatabaseExtension to scans when run."""
        print("[Extensions] _enable_database() called")
        try:
            from database.services import DatabaseService
            from pybirch.database_integration import DatabaseExtension
            
            # Get database path from config or use default
            import os
            # Default to database/pybirch.db relative to the project root
            default_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'database', 'pybirch.db')
            db_path = os.environ.get('PYBIRCH_DATABASE_PATH', default_db_path)
            
            print(f"[Extensions] Database path: {db_path}")
            print(f"[Extensions] Database file exists: {os.path.exists(db_path)}")
            
            # Create database service if not exists
            if self._db_service is None:
                self._db_service = DatabaseService(db_path)
                print(f"[Extensions] Created new DatabaseService")
            
            self._database_enabled = True
            print(f"[Extensions] Database integration enabled (path: {db_path})")
            
            # Emit signal so other components can use the db_service
            self.database_state_changed.emit(True, self._db_service)
            
        except ImportError as e:
            print(f"[Extensions] Import error: {e}")
            QMessageBox.warning(
                self, "Database Error",
                f"Database integration not available: {str(e)}"
            )
        except Exception as e:
            print(f"[Extensions] Exception: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(
                self, "Database Error",
                f"Failed to enable database integration: {str(e)}"
            )
    
    def _disable_database(self):
        """Disable database integration."""
        self._database_enabled = False
        # Don't close db_service - it may be used elsewhere
        print("[Extensions] Database integration disabled")
        
        # Emit signal
        self.database_state_changed.emit(False, None)
    
    def create_queue_record(self, queue: 'Queue', sample_id: Optional[int] = None, project_id: Optional[int] = None) -> Optional[int]:
        """
        Create a database record for a queue.
        
        Args:
            queue: The PyBirch Queue object
            sample_id: Database sample ID to link to (optional)
            project_id: Database project ID to link to (optional)
            
        Returns:
            Database queue ID, or None if database not enabled
        """
        if not self._database_enabled or self._db_service is None:
            return None
        
        try:
            from pybirch.database_integration.managers.queue_manager import QueueManager
            
            queue_manager = QueueManager(self._db_service)
            db_queue = queue_manager.create_queue_from_pybirch(
                queue,
                sample_id=sample_id,
                project_id=project_id,
            )
            queue_id = db_queue['id']
            print(f"[Extensions] Created database queue record: {db_queue['queue_id']} (ID: {queue_id})")
            return queue_id
        except Exception as e:
            print(f"[Extensions] Failed to create queue record: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_database_extension_for_scan(self, scan: 'Scan', sample_id: Optional[int] = None, project_id: Optional[int] = None, queue_id: Optional[int] = None) -> 'DatabaseExtension':
        """
        Create a DatabaseExtension for a scan.
        
        Call this before running a scan to enable database persistence.
        
        Args:
            scan: The scan to create an extension for
            sample_id: Database sample ID to link to (optional)
            project_id: Database project ID to link to (optional)
            queue_id: Database queue ID to link to (optional)
            
        Returns:
            DatabaseExtension instance, or None if database not enabled
        """
        if not self._database_enabled or self._db_service is None:
            return None
        
        try:
            from pybirch.database_integration import DatabaseExtension
            
            ext = DatabaseExtension(
                db_service=self._db_service,
                owner=scan.owner,
                scan_settings=scan.scan_settings,
                sample_id=sample_id,
                project_id=project_id,
                queue_id=queue_id,
            )
            return ext
        except Exception as e:
            print(f"[Extensions] Failed to create DatabaseExtension: {e}")
            return None
    
    def add_extensions_to_scan(self, scan: 'Scan', sample_id: Optional[int] = None, project_id: Optional[int] = None, queue_id: Optional[int] = None):
        """
        Add enabled extensions to a scan before execution.
        
        Call this before running scan.startup() to add all enabled extensions.
        
        Args:
            scan: The scan to add extensions to
            sample_id: Database sample ID to link scans to (optional)
            project_id: Database project ID to link scans to (optional)
            queue_id: Database queue ID to link scans to (optional)
        """
        print(f"[Extensions] add_extensions_to_scan called for {scan.scan_settings.scan_name}")
        print(f"[Extensions]   database_enabled: {self._database_enabled}")
        print(f"[Extensions]   db_service: {self._db_service}")
        print(f"[Extensions]   sample_id: {sample_id}, project_id: {project_id}, queue_id: {queue_id}")
        
        # Initialize extensions list if needed
        if not hasattr(scan.scan_settings, 'extensions') or scan.scan_settings.extensions is None:
            scan.scan_settings.extensions = []
        
        # Remove any existing DatabaseExtension to avoid duplicates
        from pybirch.database_integration.extensions.database_extension import DatabaseExtension
        original_count = len(scan.scan_settings.extensions)
        scan.scan_settings.extensions = [
            ext for ext in scan.scan_settings.extensions 
            if not isinstance(ext, DatabaseExtension)
        ]
        removed_count = original_count - len(scan.scan_settings.extensions)
        if removed_count > 0:
            print(f"[Extensions] Removed {removed_count} existing DatabaseExtension(s)")
        
        # Add database extension if enabled
        if self._database_enabled:
            ext = self.create_database_extension_for_scan(scan, sample_id=sample_id, project_id=project_id, queue_id=queue_id)
            if ext:
                scan.scan_settings.extensions.append(ext)
                scan.extensions = scan.scan_settings.extensions
                print(f"[Extensions] Added DatabaseExtension to scan {scan.scan_settings.scan_name}")
                print(f"[Extensions]   Total extensions now: {len(scan.extensions)}")
            else:
                print(f"[Extensions] Failed to create DatabaseExtension for {scan.scan_settings.scan_name}")
        else:
            # Still update scan.extensions in case we removed old ones
            scan.extensions = scan.scan_settings.extensions
            print(f"[Extensions] Database not enabled, skipping extension for {scan.scan_settings.scan_name}")
    
    @property
    def websocket_enabled(self) -> bool:
        """Check if WebSocket is enabled."""
        return self._websocket_bridge is not None
    
    @property
    def database_enabled(self) -> bool:
        """Check if database integration is enabled."""
        return self._database_enabled
    
    @property
    def db_service(self):
        """Get the database service (if database is enabled)."""
        return self._db_service if self._database_enabled else None
    
    def enable_websocket_for_queue(self, queue: 'Queue'):
        """
        Enable WebSocket integration for a specific queue.
        
        Args:
            queue: The queue to enable WebSocket for
        """
        self._queue = queue
        if self._extension_widgets['websocket'].is_enabled():
            self._enable_websocket()


# Standalone testing
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    from GUI.theme import apply_theme
    
    app = QApplication(sys.argv)
    apply_theme(app)
    
    page = ExtensionsPage()
    page.resize(600, 500)
    page.show()
    
    sys.exit(app.exec())
