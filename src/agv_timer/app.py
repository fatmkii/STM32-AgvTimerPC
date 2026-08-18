from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AGV 节拍测量")
    app.setOrganizationName("STM32 AGV Timer")

    window = MainWindow()
    window.show()
    return app.exec()
