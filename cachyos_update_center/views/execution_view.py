"""
Execution View: Displays real-time progress of the 4-phase update pipeline with embedded terminal.
"""
import subprocess
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.update_runner import UpdatePipelineWorker
from ..styles import CachyColors
from ..widgets.log_terminal import LogTerminal
from ..widgets.step_indicator import StepIndicator


class ExecutionView(QWidget):
    """View managing the active update process and displaying live logs."""

    request_back_to_dashboard = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker: UpdatePipelineWorker = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # ----------------------------------------------------------------------
        # 1. 4-Phase Step Indicator
        # ----------------------------------------------------------------------
        self.step_indicator = StepIndicator()
        layout.addWidget(self.step_indicator)

        # ----------------------------------------------------------------------
        # 2. Overall Progress Bar
        # ----------------------------------------------------------------------
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Fortschritt: %p%")
        self.progress_bar.setFixedHeight(18)
        layout.addWidget(self.progress_bar)

        # ----------------------------------------------------------------------
        # 3. Kernel Reboot Notification Banner
        # ----------------------------------------------------------------------
        self.reboot_banner = QFrame()
        self.reboot_banner.setObjectName("rebootBanner")
        self.reboot_banner.setVisible(False)
        rb_layout = QHBoxLayout(self.reboot_banner)
        rb_layout.setContentsMargins(16, 12, 16, 12)
        rb_layout.setSpacing(12)

        rb_icon = QLabel("🔄")
        rb_icon.setStyleSheet("font-size: 22px;")
        rb_layout.addWidget(rb_icon)

        rb_text = QVBoxLayout()
        rb_text.setSpacing(2)
        rb_title = QLabel("Neustart erforderlich")
        rb_title.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {CachyColors.ACCENT_CYAN};")
        rb_desc = QLabel("Ein neuer CachyOS-Kernel wurde installiert. Starte das System neu, um den Kernel zu aktivieren.")
        rb_desc.setStyleSheet(f"font-size: 11px; color: {CachyColors.TEXT_PRIMARY};")
        rb_text.addWidget(rb_title)
        rb_text.addWidget(rb_desc)
        rb_layout.addLayout(rb_text, 1)

        btn_reboot_now = QPushButton("Jetzt neu starten")
        btn_reboot_now.setProperty("class", "btn-primary")
        btn_reboot_now.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reboot_now.clicked.connect(self._reboot_system)
        rb_layout.addWidget(btn_reboot_now)

        self.reboot_banner.setStyleSheet(f"""
            QFrame#rebootBanner {{
                background-color: rgba(56, 189, 248, 0.15);
                border: 1px solid {CachyColors.ACCENT_CYAN};
                border-radius: 8px;
            }}
        """)
        layout.addWidget(self.reboot_banner)

        # ----------------------------------------------------------------------
        # 4. Embedded Live Terminal
        # ----------------------------------------------------------------------
        self.terminal = LogTerminal()
        layout.addWidget(self.terminal, 1)

        # ----------------------------------------------------------------------
        # 5. Bottom Controls
        # ----------------------------------------------------------------------
        bottom_bar = QHBoxLayout()
        self.status_text = QLabel("Bereit zum Aktualisieren...")
        self.status_text.setStyleSheet(f"color: {CachyColors.TEXT_SECONDARY}; font-weight: 500;")
        bottom_bar.addWidget(self.status_text)
        bottom_bar.addStretch()

        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setProperty("class", "btn-danger")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.cancel_pipeline)
        bottom_bar.addWidget(self.btn_cancel)

        self.btn_back = QPushButton("Zurück zur Übersicht")
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.clicked.connect(self.request_back_to_dashboard.emit)
        self.btn_back.setEnabled(False)
        bottom_bar.addWidget(self.btn_back)

        layout.addLayout(bottom_bar)

    def start_pipeline(
        self,
        rate_mirrors_first: bool = True,
        create_snapshot: bool = True,
        include_aur: bool = True,
        entry_country: str = "DE",
        selected_packages=None,
        auto_exclude_issues: bool = True,
    ):
        """Initializes and runs the update pipeline."""
        self.terminal.clear_log()
        self.step_indicator.reset_all()
        self.progress_bar.setValue(0)
        self.reboot_banner.setVisible(False)
        self.btn_cancel.setEnabled(True)
        self.btn_back.setEnabled(False)
        self.status_text.setText("Initialisiere Aktualisierungsprozess...")

        self.worker = UpdatePipelineWorker(
            rate_mirrors_first=rate_mirrors_first,
            create_snapshot=create_snapshot,
            include_aur=include_aur,
            entry_country=entry_country,
            selected_packages=selected_packages,
            auto_exclude_issues=auto_exclude_issues,
        )


        self.worker.step_started.connect(self._on_step_started)
        self.worker.step_completed.connect(self._on_step_completed)
        self.worker.progress_percent.connect(self.progress_bar.setValue)
        self.worker.terminal_line.connect(self.terminal.append_line)
        self.worker.pipeline_finished.connect(self._on_pipeline_finished)
        self.worker.reboot_advised.connect(self.reboot_banner.setVisible)

        self.worker.start()

    def _on_step_started(self, idx: int, title: str):
        self.step_indicator.set_step_state(idx, "active")
        self.status_text.setText(f"Aktiver Schritt: {title}...")

    def _on_step_completed(self, idx: int, success: bool):
        self.step_indicator.set_step_state(idx, "completed" if success else "failed")

    def _on_pipeline_finished(self, success: bool, msg: str):
        self.btn_cancel.setEnabled(False)
        self.btn_back.setEnabled(True)
        self.status_text.setText(msg)

    def cancel_pipeline(self):
        """Cancels running process."""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Aktualisierung abbrechen",
                "Möchtest du den laufenden Aktualisierungsprozess wirklich abbrechen?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.worker.cancel()
                self.status_text.setText("Abbruch angefordert...")

    def _reboot_system(self):
        """Invokes system reboot."""
        try:
            subprocess.run(["systemctl", "reboot"], check=False)
        except Exception as e:
            QMessageBox.warning(self, "Neustart-Fehler", f"Neustart konnte nicht ausgelöst werden: {e}")
