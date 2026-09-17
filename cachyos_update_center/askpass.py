#!/usr/bin/env python3
"""
CachyOS Update Center - Graphical Askpass Helper with Session Caching
Provides a secure, native CachyOS-styled password prompt for sudo / yay.
Caches authentication in RAM tmpfs during the active update session so the user is only prompted ONCE.
Outputs the password to stdout (required by SUDO_ASKPASS).
"""
import os
import shutil
import subprocess
import sys
import time
from typing import Optional

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont, QKeySequence, QShortcut
    from PyQt6.QtWidgets import (
        QApplication,
        QDialog,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QVBoxLayout,
    )
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


def get_auth_token_file() -> str:
    """Returns the RAM-backed path for the session auth token."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid() if hasattr(os, 'getuid') else 1000}")
    if not os.path.isdir(runtime_dir):
        runtime_dir = "/tmp"
    return os.path.join(runtime_dir, "cachyos_update_center_auth.token")


def _wipe_file(path: str):
    """Securely zeroes and unlinks a file."""
    if os.path.exists(path):
        try:
            size = os.path.getsize(path)
            with open(path, "wb") as f:
                f.write(b"\x00" * max(size, 64))
            os.unlink(path)
        except Exception:
            try:
                os.unlink(path)
            except Exception:
                pass


def check_cached_password() -> Optional[str]:
    """Checks if a valid, unexpired session password exists in memory tmpfs."""
    token_path = get_auth_token_file()

    if not os.path.isfile(token_path):
        return None

    # Max validity: 15 minutes (900 seconds)
    try:
        mtime = os.path.getmtime(token_path)
        if time.time() - mtime > 900:
            _wipe_file(token_path)
            return None
    except Exception:
        return None

    # Read cached password
    try:
        with open(token_path, "r", encoding="utf-8") as f:
            pwd = f.read().rstrip("\r\n")
        return pwd if pwd else None
    except Exception:
        return None


def save_cached_password(pwd: str):
    """Saves the password to RAM-backed session storage with 0600 permissions."""
    if not pwd:
        return
    token_path = get_auth_token_file()
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(token_path, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(pwd)
    except Exception:
        pass


def verify_sudo_password(pwd: str) -> bool:
    """Directly verifies password via sudo -S -k -v. Returns True if valid."""
    if not pwd:
        return False
    try:
        proc = subprocess.run(
            ["sudo", "-S", "-k", "-v"],
            input=pwd + "\n",
            text=True,
            capture_output=True,
            timeout=10,
        )
        return proc.returncode == 0
    except Exception:
        return False


def run_fallback_askpass(prompt: str) -> int:
    """Fallback to kdialog, zenity, or terminal getpass if PyQt6 is not usable."""
    pwd = None
    # 1. Try kdialog (KDE native)
    if shutil.which("kdialog"):
        try:
            res = subprocess.run(
                ["kdialog", "--password", prompt, "--title", "CachyOS Update Center"],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                pwd = res.stdout.rstrip("\r\n")
        except Exception:
            pass

    # 2. Try zenity (GNOME / GTK native)
    if pwd is None and shutil.which("zenity"):
        try:
            res = subprocess.run(
                ["zenity", "--password", f"--title=CachyOS Update Center: {prompt}"],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                pwd = res.stdout.rstrip("\r\n")
        except Exception:
            pass

    # 3. Terminal fallback
    if pwd is None:
        try:
            import getpass
            pwd = getpass.getpass(f"{prompt} ")
        except Exception:
            return 1

    if pwd:
        save_cached_password(pwd)
        sys.stdout.write(pwd + "\n")
        sys.stdout.flush()
        return 0
    return 1


if PYQT_AVAILABLE:
    class AskpassDialog(QDialog):
        def __init__(self, prompt_text: str = "Administrator-Passwort:", parent=None, verify_direct: bool = False):
            super().__init__(parent)
            self.verify_direct = verify_direct
            self.result_password = ""
            self.setWindowTitle("CachyOS Update Center - Legitimierung")
            self.setMinimumWidth(440)
            self.setModal(True)
            if parent is None:
                self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

            self.setStyleSheet("""
                QDialog {
                    background-color: #0d131c;
                    border: 1px solid #1f2f42;
                    border-radius: 12px;
                }
                QLabel#TitleLabel {
                    color: #ffffff;
                    font-size: 15px;
                    font-weight: bold;
                }
                QLabel#SubLabel {
                    color: #94a3b8;
                    font-size: 12px;
                }
                QLineEdit {
                    background-color: #172230;
                    border: 1px solid #2a3b4c;
                    border-radius: 8px;
                    padding: 8px 12px;
                    color: #ffffff;
                    font-size: 14px;
                    selection-background-color: #00D494;
                    selection-color: #000000;
                }
                QLineEdit:focus {
                    border: 1px solid #00D494;
                    background-color: #1a2737;
                }
                QPushButton#ToggleBtn {
                    background-color: #172230;
                    border: 1px solid #2a3b4c;
                    border-radius: 8px;
                    color: #94a3b8;
                    font-size: 13px;
                    padding: 8px 12px;
                }
                QPushButton#ToggleBtn:hover {
                    color: #ffffff;
                    border-color: #00D494;
                }
                QPushButton#BtnCancel {
                    background-color: #172230;
                    border: 1px solid #2a3b4c;
                    border-radius: 8px;
                    color: #cbd5e1;
                    font-size: 13px;
                    font-weight: 500;
                    padding: 8px 18px;
                    min-height: 20px;
                }
                QPushButton#BtnCancel:hover {
                    background-color: #223246;
                    color: #ffffff;
                }
                QPushButton#BtnConfirm {
                    background-color: #00D494;
                    border: none;
                    border-radius: 8px;
                    color: #000000;
                    font-size: 13px;
                    font-weight: bold;
                    padding: 8px 22px;
                    min-height: 20px;
                }
                QPushButton#BtnConfirm:hover {
                    background-color: #00eba4;
                }
                QPushButton#BtnConfirm:pressed {
                    background-color: #00b87f;
                }
            """)

            layout = QVBoxLayout(self)
            layout.setContentsMargins(24, 20, 24, 20)
            layout.setSpacing(14)

            # Header
            header_layout = QHBoxLayout()
            icon_label = QLabel("🛡️")
            icon_font = QFont()
            icon_font.setPointSize(24)
            icon_label.setFont(icon_font)
            header_layout.addWidget(icon_label)

            text_layout = QVBoxLayout()
            title_lbl = QLabel("Administrator-Rechte erforderlich")
            title_lbl.setObjectName("TitleLabel")
            text_layout.addWidget(title_lbl)

            # Clean user info
            user = os.environ.get("USER", "Benutzer")
            sub_lbl = QLabel(f"Bitte gib das Kennwort für '{user}' ein, um die Aktualisierung durchzuführen.")
            sub_lbl.setObjectName("SubLabel")
            sub_lbl.setWordWrap(True)
            text_layout.addWidget(sub_lbl)
            header_layout.addLayout(text_layout)
            layout.addLayout(header_layout)

            # Password row
            input_layout = QHBoxLayout()
            input_layout.setSpacing(6)
            self.txt_pass = QLineEdit()
            self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
            self.txt_pass.setPlaceholderText("Passwort eingeben...")
            self.txt_pass.returnPressed.connect(self._on_confirm)
            self.txt_pass.textChanged.connect(self._on_text_changed)
            input_layout.addWidget(self.txt_pass)

            self.btn_toggle = QPushButton("👁")
            self.btn_toggle.setObjectName("ToggleBtn")
            self.btn_toggle.setToolTip("Passwort anzeigen / verbergen")
            self.btn_toggle.setFixedWidth(42)
            self.btn_toggle.clicked.connect(self._toggle_visibility)
            input_layout.addWidget(self.btn_toggle)
            layout.addLayout(input_layout)

            # Error label
            self.lbl_error = QLabel("")
            self.lbl_error.setStyleSheet("color: #FF455B; font-size: 12px; font-weight: bold;")
            self.lbl_error.setVisible(False)
            layout.addWidget(self.lbl_error)

            # Action Buttons
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()

            self.btn_cancel = QPushButton("Abbrechen")
            self.btn_cancel.setObjectName("BtnCancel")
            self.btn_cancel.clicked.connect(self.reject)
            btn_layout.addWidget(self.btn_cancel)

            self.btn_confirm = QPushButton("Bestätigen")
            self.btn_confirm.setObjectName("BtnConfirm")
            self.btn_confirm.clicked.connect(self._on_confirm)
            btn_layout.addWidget(self.btn_confirm)

            layout.addLayout(btn_layout)

            # Shortcuts
            QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.reject)

            self.txt_pass.setFocus()

        def _on_text_changed(self):
            self.lbl_error.setVisible(False)
            self.txt_pass.setStyleSheet("")

        def _toggle_visibility(self):
            if self.txt_pass.echoMode() == QLineEdit.EchoMode.Password:
                self.txt_pass.setEchoMode(QLineEdit.EchoMode.Normal)
                self.btn_toggle.setText("🔒")
            else:
                self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
                self.btn_toggle.setText("👁")

        def _on_confirm(self):
            pwd = self.txt_pass.text()
            if not pwd:
                self.txt_pass.setStyleSheet("border: 1px solid #FF455B; background-color: #1a2737;")
                return

            if self.verify_direct:
                self.btn_confirm.setEnabled(False)
                self.btn_confirm.setText("Prüfe...")
                QApplication.processEvents()

                ok = verify_sudo_password(pwd)
                self.btn_confirm.setEnabled(True)
                self.btn_confirm.setText("Bestätigen")

                if not ok:
                    self.lbl_error.setText("❌ Ungültiges Passwort. Bitte erneut versuchen.")
                    self.lbl_error.setVisible(True)
                    self.txt_pass.setStyleSheet("border: 1px solid #FF455B; background-color: #1a2737;")
                    self.txt_pass.selectAll()
                    self.txt_pass.setFocus()
                    return

            save_cached_password(pwd)
            self.result_password = pwd
            self.accept()


def run_pyqt_askpass(prompt: str) -> int:
    """Displays the CachyOS Emerald Dark password dialog."""
    if not PYQT_AVAILABLE:
        return run_fallback_askpass(prompt)

    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    try:
        dlg = AskpassDialog(prompt)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_password:
            save_cached_password(dlg.result_password)
            sys.stdout.write(dlg.result_password + "\n")
            sys.stdout.flush()
            return 0
        return 1
    except Exception:
        return run_fallback_askpass(prompt)


def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Administrator-Passwort:"

    # 1. First check if a cached session token exists (avoids multiple prompts!)
    cached = check_cached_password()
    if cached is not None:
        sys.stdout.write(cached + "\n")
        sys.stdout.flush()
        sys.exit(0)

    # 2. Prompt user via GUI if no cached token
    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"):
        sys.exit(run_pyqt_askpass(prompt))
    else:
        sys.exit(run_fallback_askpass(prompt))


if __name__ == "__main__":
    main()
