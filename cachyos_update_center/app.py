"""
Application bootstrap and entry point for CachyOS Update Center.
"""
import os
import shutil
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

from . import __app_name__, __display_name__, __version__
from .main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationDisplayName(__display_name__)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(__app_name__)

    # Set application icon
    base_res = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")
    icon_path = os.path.join(base_res, "app_icon_256.png")
    if not os.path.exists(icon_path):
        icon_path = os.path.join(base_res, "app_icon.svg")

    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        app_icon = QIcon.fromTheme("system-software-update")
        if not app_icon.isNull():
            app.setWindowIcon(app_icon)

    # Check mirror rating tools
    if not shutil.which("rate-mirrors") and not shutil.which("cachyos-rate-mirrors"):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Spiegelserver-Werkzeug nicht gefunden")
        msg.setText(
            "Weder 'cachyos-rate-mirrors' noch 'rate-mirrors' wurden im System-Pfad gefunden.\n\n"
            "Bitte stelle sicher, dass 'cachyos-rate-mirrors' oder 'rate-mirrors' installiert ist."
        )
        msg.exec()

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
