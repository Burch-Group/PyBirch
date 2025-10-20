# Copyright (C) 2025
# User Fields Widget Entry Point for PyBirch
from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication
from mainwindow import UserFieldMainWindow


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = UserFieldMainWindow()
    window.show()
    sys.exit(app.exec())