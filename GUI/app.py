# Copyright (C) 2025
# PyBirch GUI Application Entry Point
"""
Main application entry point for PyBirch GUI.

This module provides the main application setup and initialization,
including theme application and window management.
"""

import sys
import os

# Add path to parent directory for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtWidgets import QApplication

from GUI.theme import apply_theme


def create_app() -> QApplication:
    """Create and configure the QApplication instance.
    
    Returns:
        Configured QApplication instance with theme applied.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("PyBirch")
    app.setOrganizationName("PyBirch")
    
    # Apply global theme
    apply_theme(app)
    
    return app


def main():
    """Main entry point for the PyBirch GUI application."""
    app = create_app()
    
    # Import main window
    from GUI.main.main_window import MainWindow
    from pybirch.queue.queue import Queue
    
    # Create a new queue or load from database if available
    queue = Queue(QID="NewQueue")
    
    # Try to initialize database service if available
    db_service = None
    try:
        from database.services import DatabaseService
        # TODO: Configure database path from settings
        # db_service = DatabaseService('pybirch.db')
    except ImportError:
        pass
    
    # Create and show main window
    main_window = MainWindow(queue=queue, db_service=db_service)
    main_window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    from PySide6.QtCore import Qt
    main()
