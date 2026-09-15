#!/usr/bin/env python3
"""
CachyOS Update Center - Graphical Installation & Setup Wizard.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

REPO_DIR = Path(__file__).resolve().parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

INSTALLER_STYLESHEET = """
QWidget {
    background-color: transparent;
    color: #F8FAFC;
    font-family: "Inter", "Cantarell", "Noto Sans", "Segoe UI", Roboto, sans-serif;
    font-size: 13px;
    outline: none;
}

QMainWindow {
    background-color: #090d14;
}

QFrame.wizard-card {
    background-color: #131b26;
    border: 1px solid #233348;
    border-radius: 10px;
    padding: 16px;
}

QPushButton {
    background-color: #172230;
    color: #F8FAFC;
    border: 1px solid #233348;
    border-radius: 6px;
    padding: 9px 20px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #1e2c3e;
    border-color: #364d6c;
}

QPushButton.btn-primary {
    background-color: #00D494;
    color: #03140e;
    border: 1px solid #00FFA8;
    font-weight: 800;
}

QPushButton.btn-primary:hover {
    background-color: #00FFA8;
}

QProgressBar {
    border: 1px solid #233348;
    border-radius: 6px;
    background-color: #0d131c;
    height: 14px;
    text-align: center;
    font-size: 11px;
}

QProgressBar::chunk {
    background-color: #00D494;
    border-radius: 5px;
}

QCheckBox {
    spacing: 8px;
    font-size: 13px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #233348;
    background-color: #101823;
}

QCheckBox::indicator:checked {
    background-color: #00D494;
    border-color: #00FFA8;
}
"""


class InstallWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, make_desktop_shortcut=True):
        super().__init__()
        self.make_desktop_shortcut = make_desktop_shortcut

    def run(self):
        try:
            bin_dir = Path.home() / ".local" / "bin"
            app_dir = Path.home() / ".local" / "share" / "applications"
            share_dir = Path.home() / ".local" / "share" / "cachyos-update-center"
            hicolor_dir = Path.home() / ".local" / "share" / "icons" / "hicolor"
            pixmaps_dir = Path.home() / ".local" / "share" / "pixmaps"

            self.progress.emit(10, "Erstelle Zielverzeichnisse...")
            bin_dir.mkdir(parents=True, exist_ok=True)
            app_dir.mkdir(parents=True, exist_ok=True)
            share_dir.mkdir(parents=True, exist_ok=True)
            pixmaps_dir.mkdir(parents=True, exist_ok=True)

            self.progress.emit(30, "Kopiere Anwendungsdateien...")
            dest_pkg = share_dir / "cachyos_update_center"
            if dest_pkg.exists():
                shutil.rmtree(dest_pkg)
            shutil.copytree(REPO_DIR / "cachyos_update_center", dest_pkg)
            shutil.copy(REPO_DIR / "main.py", share_dir / "main.py")

            self.progress.emit(50, "Installiere Standalone-Launcher...")
            dest_bin = bin_dir / "cachyos-update-center"
            shutil.copy(REPO_DIR / "cachyos-update-center", dest_bin)
            dest_bin.chmod(0o755)

            self.progress.emit(70, "Installiere Anwendungs-Icons...")
            svg_icon = REPO_DIR / "cachyos_update_center" / "resources" / "app_icon.svg"
            svg_dest = hicolor_dir / "scalable" / "apps" / "cachyos-update-center.svg"
            svg_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(svg_icon, svg_dest)
            shutil.copy(svg_icon, pixmaps_dir / "cachyos-update-center.svg")

            for sz in (16, 24, 32, 48, 64, 128, 256, 512):
                png_src = REPO_DIR / "cachyos_update_center" / "resources" / f"app_icon_{sz}.png"
                if png_src.exists():
                    dest_png_dir = hicolor_dir / f"{sz}x{sz}" / "apps"
                    dest_png_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy(png_src, dest_png_dir / "cachyos-update-center.png")

            self.progress.emit(85, "Registriere Desktop-Menüeintrag...")
            desktop_file = app_dir / "cachyos-update-center.desktop"
            shutil.copy(REPO_DIR / "cachyos-update-center.desktop", desktop_file)
            desktop_file.chmod(0o644)

            if self.make_desktop_shortcut:
                dt_dir = Path.home() / "Desktop"
                if not dt_dir.exists() and (Path.home() / "Schreibtisch").exists():
                    dt_dir = Path.home() / "Schreibtisch"
                if dt_dir.exists():
                    shutil.copy(REPO_DIR / "cachyos-update-center.desktop", dt_dir / "cachyos-update-center.desktop")
                    (dt_dir / "cachyos-update-center.desktop").chmod(0o755)

            self.progress.emit(95, "Aktualisiere Desktop- & Icon-Datenbanken...")
            subprocess.run(["update-desktop-database", str(app_dir)], check=False)
            subprocess.run(["gtk-update-icon-cache", "-f", "-t", str(hicolor_dir)], check=False)

            self.progress.emit(100, "Installation erfolgreich abgeschlossen!")
            self.finished.emit(True, "Installation vollständig!")
        except Exception as e:
            self.finished.emit(False, str(e))


class InstallerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CachyOS Update Center - Installations-Assistent")
        self.resize(680, 520)
        self.setFixedSize(680, 520)

        self.worker = None
        self.init_ui()
        self.setStyleSheet(INSTALLER_STYLESHEET)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(16)

        # Header Hero
        header = QFrame()
        header.setStyleSheet("background-color: #131b26; border: 1px solid #233348; border-radius: 10px; padding: 12px;")
        hl = QHBoxLayout(header)
        hl.setSpacing(14)

        icon_path = REPO_DIR / "cachyos_update_center" / "resources" / "app_icon_64.png"
        icon_lbl = QLabel()
        if icon_path.exists():
            icon_lbl.setPixmap(QPixmap(str(icon_path)).scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            icon_lbl.setText("⚡")
            icon_lbl.setStyleSheet("font-size: 28px;")
        hl.addWidget(icon_lbl)

        htext = QVBoxLayout()
        htext.setSpacing(2)
        t_lbl = QLabel("CachyOS Update Center")
        t_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #00FFA8;")
        sub_lbl = QLabel("Grafischer Installations- und Einrichtungsassistent")
        sub_lbl.setStyleSheet("font-size: 12px; color: #94A3B8;")
        htext.addWidget(t_lbl)
        htext.addWidget(sub_lbl)
        hl.addLayout(htext, 1)
        root_layout.addWidget(header)

        # Pages Stack
        self.stack = QStackedWidget()

        # Page 0: Welcome & System Audit
        self.page_welcome = self._create_page_welcome()
        self.stack.addWidget(self.page_welcome)

        # Page 1: Options
        self.page_options = self._create_page_options()
        self.stack.addWidget(self.page_options)

        # Page 2: Progress
        self.page_progress = self._create_page_progress()
        self.stack.addWidget(self.page_progress)

        # Page 3: Complete
        self.page_complete = self._create_page_complete()
        self.stack.addWidget(self.page_complete)

        root_layout.addWidget(self.stack, 1)

        # Bottom Buttons
        self.btn_bar = QHBoxLayout()
        self.btn_bar.addStretch()

        self.btn_back = QPushButton("Zurück")
        self.btn_back.clicked.connect(self.go_back)
        self.btn_back.setEnabled(False)

        self.btn_next = QPushButton("Weiter")
        self.btn_next.setProperty("class", "btn-primary")
        self.btn_next.clicked.connect(self.go_next)

        self.btn_bar.addWidget(self.btn_back)
        self.btn_bar.addWidget(self.btn_next)
        root_layout.addLayout(self.btn_bar)

    def _create_page_welcome(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 8, 0, 0)
        l.setSpacing(14)

        card = QFrame()
        card.setProperty("class", "wizard-card")
        cl = QVBoxLayout(card)
        cl.setSpacing(10)

        t = QLabel("Willkommen zur Installation des CachyOS Update Centers!")
        t.setStyleSheet("font-size: 14px; font-weight: 700; color: #F8FAFC;")
        cl.addWidget(t)

        desc = QLabel(
            "Das Update Center bietet modernstes Paket- und Systemmanagement für CachyOS mit der einzigartigen "
            "Garantie: <b>Immer mit vorheriger Spiegelserver-Bewertung</b> für schnellste Downloads und maximale "
            "Zuverlässigkeit bei jeder Aktualisierung."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #94A3B8; font-size: 12px; line-height: 1.4;")
        cl.addWidget(desc)

        # System Checks
        cl.addWidget(QLabel("<b>Systemvoraussetzungen:</b>"))

        checks = [
            ("CachyOS / Arch Linux Kernel", True),
            ("cachyos-rate-mirrors / rate-mirrors", shutil.which("rate-mirrors") is not None),
            ("Pacman & checkupdates", shutil.which("checkupdates") is not None),
            ("AUR-Unterstützung (yay)", shutil.which("yay") is not None),
            ("BTRFS Snapshot-Schutz (Snapper)", shutil.which("snapper") is not None),
        ]

        for name, ok in checks:
            row = QHBoxLayout()
            icon = "✅" if ok else "⚠️"
            lbl_name = QLabel(f"{icon}  {name}")
            status = "Installiert & Verfügbar" if ok else "Optional / Nicht gefunden"
            color = "#00D494" if ok else "#FFB300"
            lbl_status = QLabel(status)
            lbl_status.setStyleSheet(f"color: {color}; font-weight: 600; font-size: 11px;")
            row.addWidget(lbl_name)
            row.addStretch()
            row.addWidget(lbl_status)
            cl.addLayout(row)

        l.addWidget(card)
        l.addStretch()
        return w

    def _create_page_options(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 8, 0, 0)
        l.setSpacing(14)

        card = QFrame()
        card.setProperty("class", "wizard-card")
        cl = QVBoxLayout(card)
        cl.setSpacing(12)

        t = QLabel("Installations-Optionen")
        t.setStyleSheet("font-size: 14px; font-weight: 700; color: #F8FAFC;")
        cl.addWidget(t)

        self.chk_shortcut = QCheckBox("Desktop-Verknüpfung auf dem Schreibtisch erstellen")
        self.chk_shortcut.setChecked(True)
        cl.addWidget(self.chk_shortcut)

        self.chk_menu = QCheckBox("Im Anwendungsmenü (XDG Applications) registrieren")
        self.chk_menu.setChecked(True)
        self.chk_menu.setEnabled(False)
        cl.addWidget(self.chk_menu)

        self.chk_bin = QCheckBox("Befehl 'cachyos-update-center' in ~/.local/bin bereitstellen")
        self.chk_bin.setChecked(True)
        self.chk_bin.setEnabled(False)
        cl.addWidget(self.chk_bin)

        l.addWidget(card)
        l.addStretch()
        return w

    def _create_page_progress(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 8, 0, 0)
        l.setSpacing(14)

        card = QFrame()
        card.setProperty("class", "wizard-card")
        cl = QVBoxLayout(card)
        cl.setSpacing(14)

        t = QLabel("Installation wird durchgeführt...")
        t.setStyleSheet("font-size: 14px; font-weight: 700; color: #F8FAFC;")
        cl.addWidget(t)

        self.pbar = QProgressBar()
        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)
        cl.addWidget(self.pbar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #090d14; border: 1px solid #233348; color: #cbd5e1; font-family: monospace; font-size: 11px;")
        cl.addWidget(self.log_text, 1)

        l.addWidget(card)
        return w

    def _create_page_complete(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 8, 0, 0)
        l.setSpacing(14)

        card = QFrame()
        card.setProperty("class", "wizard-card")
        cl = QVBoxLayout(card)
        cl.setSpacing(14)

        t = QLabel("🎉 Installation erfolgreich abgeschlossen!")
        t.setStyleSheet("font-size: 16px; font-weight: 800; color: #00FFA8;")
        cl.addWidget(t)

        msg = QLabel(
            "Das CachyOS Update Center wurde erfolgreich in deinem Benutzerverzeichnis installiert.\n\n"
            "Du kannst die Anwendung jederzeit über das Anwendungsmenü oder mit dem Befehl 'cachyos-update-center' starten."
        )
        msg.setStyleSheet("color: #94A3B8; font-size: 12px; line-height: 1.4;")
        cl.addWidget(msg)

        self.chk_launch = QCheckBox("CachyOS Update Center jetzt starten")
        self.chk_launch.setChecked(True)
        cl.addWidget(self.chk_launch)

        l.addWidget(card)
        l.addStretch()
        return w

    def go_next(self):
        idx = self.stack.currentIndex()
        if idx == 0:
            self.stack.setCurrentIndex(1)
            self.btn_back.setEnabled(True)
        elif idx == 1:
            self.stack.setCurrentIndex(2)
            self.btn_back.setEnabled(False)
            self.btn_next.setEnabled(False)
            self.start_installation()
        elif idx == 3:
            if self.chk_launch.isChecked():
                subprocess.Popen([str(Path.home() / ".local" / "bin" / "cachyos-update-center")])
            self.close()

    def go_back(self):
        idx = self.stack.currentIndex()
        if idx == 1:
            self.stack.setCurrentIndex(0)
            self.btn_back.setEnabled(False)

    def start_installation(self):
        self.worker = InstallWorker(make_desktop_shortcut=self.chk_shortcut.isChecked())
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, val: int, msg: str):
        self.pbar.setValue(val)
        self.log_text.append(f"[{val}%] {msg}")

    def _on_finished(self, ok: bool, err: str):
        if ok:
            self.stack.setCurrentIndex(3)
            self.btn_next.setText("Fertigstellen")
            self.btn_next.setEnabled(True)
        else:
            QMessageBox.critical(self, "Installationsfehler", f"Fehler bei der Installation:\n{err}")
            self.btn_back.setEnabled(True)


def main():
    app = QApplication(sys.argv)
    win = InstallerWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
