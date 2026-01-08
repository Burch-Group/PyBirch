# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
from __future__ import annotations


import sys
from PySide6.QtWidgets import QApplication
from mainwindow import ScanTreeWidget

# Backward compatibility alias
MainWindow = ScanTreeWidget


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ScanTreeWidget()
    window.show()
    sys.exit(app.exec())
