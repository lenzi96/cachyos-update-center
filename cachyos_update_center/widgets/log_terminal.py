"""
Embedded Terminal Log Widget with ANSI / keyword syntax coloring and autoscroll.
"""
import re
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ..styles import CachyColors


class LogTerminal(QFrame):
    """Modern dark terminal view for real-time command output."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logTerminal")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        # Terminal Header Bar
        header = QFrame()
        header.setStyleSheet(f"""
            background-color: {CachyColors.BG_DARKEST};
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            border-bottom: 1px solid {CachyColors.BORDER_SUBTLE};
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 6, 12, 6)
        header_layout.setSpacing(8)

        # Dot indicators
        dot_red = QLabel("●")
        dot_red.setStyleSheet("color: #ef4444; font-size: 11px;")
        dot_yellow = QLabel("●")
        dot_yellow.setStyleSheet("color: #f59e0b; font-size: 11px;")
        dot_green = QLabel("●")
        dot_green.setStyleSheet("color: #10b981; font-size: 11px;")

        title_lbl = QLabel("  Live-Ausgabe / Terminal Protokoll")
        title_lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {CachyColors.TEXT_SECONDARY};")

        header_layout.addWidget(dot_red)
        header_layout.addWidget(dot_yellow)
        header_layout.addWidget(dot_green)
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()

        # Action Buttons
        self.btn_copy = QPushButton("Kopieren")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.setStyleSheet("""
            QPushButton {
                padding: 3px 8px;
                font-size: 11px;
                background-color: transparent;
                border: 1px solid #233348;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1e2c3e;
            }
        """)
        self.btn_copy.clicked.connect(self.copy_log)

        self.btn_clear = QPushButton("Leeren")
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                padding: 3px 8px;
                font-size: 11px;
                background-color: transparent;
                border: 1px solid #233348;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1e2c3e;
            }
        """)
        self.btn_clear.clicked.connect(self.clear_log)

        header_layout.addWidget(self.btn_copy)
        header_layout.addWidget(self.btn_clear)

        layout.addWidget(header)

        # Text Console
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        font = QFont("JetBrains Mono", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.text_edit.setFont(font)
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: #06090e;
                color: #e2e8f0;
                border: none;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                padding: 10px;
                line-height: 1.4;
            }}
        """)
        layout.addWidget(self.text_edit, 1)

        self.setStyleSheet(f"""
            QFrame#logTerminal {{
                background-color: #06090e;
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 8px;
            }}
        """)

    def append_line(self, line: str):
        """Appends a line of text with color highlighting."""
        # Strip ANSI escape codes for clean display
        clean_text = re.sub(r"\x1b\[[0-9;]*[mGKH]", "", line)

        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        lower = clean_text.lower()

        if "==>" in clean_text or "phase" in lower or "starte" in lower:
            fmt.setForeground(QColor(CachyColors.ACCENT_EMERALD_LIGHT))
            fmt.setFontWeight(QFont.Weight.Bold)
        elif "error" in lower or "fehler" in lower or "failed" in lower or "❌" in clean_text:
            fmt.setForeground(QColor(CachyColors.ACCENT_RED))
            fmt.setFontWeight(QFont.Weight.Bold)
        elif "warning" in lower or "warnung" in lower or "hinweis" in lower or "⚠️" in clean_text:
            fmt.setForeground(QColor(CachyColors.ACCENT_AMBER))
        elif "success" in lower or "erfolgreich" in lower or "fertig" in lower or "✅" in clean_text or "done" in lower:
            fmt.setForeground(QColor(CachyColors.ACCENT_EMERALD))
        elif "http" in lower or "server =" in lower:
            fmt.setForeground(QColor(CachyColors.ACCENT_CYAN))
        else:
            fmt.setForeground(QColor("#cbd5e1"))

        cursor.insertText(clean_text + "\n", fmt)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()

    def clear_log(self):
        self.text_edit.clear()

    def copy_log(self):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.text_edit.toPlainText())
