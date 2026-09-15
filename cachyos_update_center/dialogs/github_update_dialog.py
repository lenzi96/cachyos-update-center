"""
GitHub Update Dialog for CachyOS Update Center.
Provides in-app updates directly from GitHub releases or git repository.
"""
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QTextCursor
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.github_updater import (
    GitHubUpdateCheckerWorker,
    GitHubUpdateExecWorker,
    GitHubUpdateInfo,
    UpdateStep,
    get_github_repo,
    get_repo_dir,
    set_github_repo,
)
from ..styles import CachyColors


class GitHubUpdateDialog(QDialog):
    """Modern modal dialog for updating CachyOS Update Center itself from GitHub."""

    app_restarted = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Programm-Aktualisierung – CachyOS Update Center")
        self.resize(780, 600)
        self.setMinimumSize(700, 520)

        self.checker_worker: Optional[GitHubUpdateCheckerWorker] = None
        self.exec_worker: Optional[GitHubUpdateExecWorker] = None
        self.latest_info: Optional[GitHubUpdateInfo] = None
        self.app_was_updated: bool = False

        self.init_ui()
        self.start_check()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(22, 20, 22, 20)
        root_layout.setSpacing(14)

        # ----------------------------------------------------------------------
        # Top Header
        # ----------------------------------------------------------------------
        header_layout = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(2)

        title_lbl = QLabel("Programm-Aktualisierung (GitHub)")
        title_lbl.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {CachyColors.TEXT_PRIMARY};")
        desc_lbl = QLabel("Überprüfe und aktualisiere das CachyOS Update Center direkt über GitHub.")
        desc_lbl.setStyleSheet(f"font-size: 12px; color: {CachyColors.TEXT_SECONDARY};")
        desc_lbl.setWordWrap(True)

        header_text.addWidget(title_lbl)
        header_text.addWidget(desc_lbl)
        header_layout.addLayout(header_text, 1)

        # Header Action Buttons
        self.btn_refresh = QPushButton("  Auf Updates prüfen")
        self.btn_refresh.setIcon(QIcon.fromTheme("view-refresh"))
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.start_check)
        header_layout.addWidget(self.btn_refresh)

        self.btn_update_now = QPushButton("  🚀 Programm aktualisieren")
        self.btn_update_now.setProperty("class", "btn-primary")
        self.btn_update_now.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update_now.setEnabled(False)
        self.btn_update_now.clicked.connect(self.run_github_update)
        header_layout.addWidget(self.btn_update_now)

        root_layout.addLayout(header_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background: transparent;
            }}
            QProgressBar::chunk {{
                background-color: {CachyColors.ACCENT_EMERALD};
                border-radius: 2px;
            }}
        """)
        root_layout.addWidget(self.progress_bar)

        # ----------------------------------------------------------------------
        # Tab Navigation
        # ----------------------------------------------------------------------
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 8px;
                background-color: {CachyColors.BG_DARK};
                top: -1px;
            }}
            QTabBar::tab {{
                background-color: {CachyColors.BG_PANEL};
                color: {CachyColors.TEXT_SECONDARY};
                padding: 8px 18px;
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
                font-weight: 600;
                font-size: 12px;
            }}
            QTabBar::tab:selected {{
                background-color: {CachyColors.BG_CARD};
                color: {CachyColors.ACCENT_EMERALD_LIGHT};
                border-bottom: 2px solid {CachyColors.ACCENT_EMERALD};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {CachyColors.BG_CARD_HOVER};
                color: {CachyColors.TEXT_PRIMARY};
            }}
        """)

        # Tab 1: Status & Versions
        self.tab_status = QWidget()
        self._init_status_tab()
        self.tabs.addTab(self.tab_status, "Status && Versionen")

        # Tab 2: Changelog / Release Notes
        self.tab_changelog = QWidget()
        self._init_changelog_tab()
        self.tabs.addTab(self.tab_changelog, "Release-Notizen && Changelog")

        # Tab 3: Terminal Output
        self.tab_log = QWidget()
        self._init_log_tab()
        self.tabs.addTab(self.tab_log, "Terminal-Ausgabe")

        root_layout.addWidget(self.tabs, 1)

        # ----------------------------------------------------------------------
        # Bottom Bar
        # ----------------------------------------------------------------------
        bottom_layout = QHBoxLayout()
        self.lbl_status = QLabel("Bereit.")
        self.lbl_status.setStyleSheet(f"font-size: 12px; color: {CachyColors.TEXT_SECONDARY};")
        self.lbl_status.setWordWrap(True)
        bottom_layout.addWidget(self.lbl_status, 1)

        self.btn_restart = QPushButton("🔄 Anwendung neu starten")
        self.btn_restart.setProperty("class", "btn-primary")
        self.btn_restart.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_restart.setVisible(False)
        self.btn_restart.clicked.connect(self.restart_application)
        bottom_layout.addWidget(self.btn_restart)

        self.btn_close = QPushButton("Schließen")
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.close)
        bottom_layout.addWidget(self.btn_close)

        root_layout.addLayout(bottom_layout)

    def _init_status_tab(self):
        layout = QVBoxLayout(self.tab_status)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Card 1: Version Comparison
        card_ver = QFrame()
        card_ver.setObjectName("cardVer")
        card_ver.setStyleSheet(f"""
            QFrame#cardVer {{
                background-color: {CachyColors.BG_CARD};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 10px;
                padding: 16px;
            }}
            QFrame#cardVer QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        cv_layout = QHBoxLayout(card_ver)
        cv_layout.setSpacing(16)

        icon_lbl = QLabel("⚡")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setFixedSize(44, 44)
        icon_lbl.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(0, 212, 148, 0.2), stop:1 rgba(0, 171, 119, 0.08));
            border: 1px solid rgba(0, 212, 148, 0.35);
            border-radius: 22px;
            font-size: 22px;
        """)
        cv_layout.addWidget(icon_lbl)

        ver_text = QVBoxLayout()
        ver_text.setSpacing(4)
        t_lbl = QLabel("CachyOS Update Center GUI")
        t_lbl.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {CachyColors.TEXT_PRIMARY};")

        self.lbl_versions = QLabel("Installiert: v...  │  Auf GitHub: v...")
        self.lbl_versions.setStyleSheet(f"font-size: 12px; color: {CachyColors.TEXT_SECONDARY};")
        ver_text.addWidget(t_lbl)
        ver_text.addWidget(self.lbl_versions)
        cv_layout.addLayout(ver_text, 1)

        self.badge_status = QLabel("Wird geprüft...")
        self.badge_status.setStyleSheet(f"""
            background-color: {CachyColors.BG_PANEL};
            color: {CachyColors.TEXT_MUTED};
            padding: 5px 12px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 11px;
            border: 1px solid {CachyColors.BORDER_SUBTLE};
        """)
        cv_layout.addWidget(self.badge_status)
        layout.addWidget(card_ver)

        # Card 2: GitHub Repository Config
        card_repo = QFrame()
        card_repo.setObjectName("cardRepo")
        card_repo.setStyleSheet(f"""
            QFrame#cardRepo {{
                background-color: {CachyColors.BG_CARD};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 10px;
                padding: 16px;
            }}
            QFrame#cardRepo QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        cr_layout = QHBoxLayout(card_repo)
        cr_layout.setSpacing(14)

        repo_icon = QLabel("🌐")
        repo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        repo_icon.setFixedSize(40, 40)
        repo_icon.setStyleSheet(f"""
            background: rgba(0, 210, 255, 0.12);
            border: 1px solid rgba(0, 210, 255, 0.3);
            border-radius: 20px;
            font-size: 20px;
        """)
        cr_layout.addWidget(repo_icon)

        repo_text = QVBoxLayout()
        repo_text.setSpacing(2)
        r_title = QLabel("Verknüpftes GitHub Repository")
        r_title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {CachyColors.TEXT_PRIMARY};")
        self.lbl_repo_name = QLabel(f"https://github.com/{get_github_repo()}")
        self.lbl_repo_name.setStyleSheet(f"font-size: 12px; color: {CachyColors.ACCENT_CYAN};")
        repo_text.addWidget(r_title)
        repo_text.addWidget(self.lbl_repo_name)
        cr_layout.addLayout(repo_text, 1)

        self.btn_edit_repo = QPushButton("Repository ändern")
        self.btn_edit_repo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_edit_repo.clicked.connect(self.edit_github_repo)
        cr_layout.addWidget(self.btn_edit_repo)
        layout.addWidget(card_repo)

        # Card 3: Git & Source Directory Status
        card_dir = QFrame()
        card_dir.setObjectName("cardDir")
        card_dir.setStyleSheet(f"""
            QFrame#cardDir {{
                background-color: {CachyColors.BG_CARD};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 10px;
                padding: 14px;
            }}
            QFrame#cardDir QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        cd_layout = QVBoxLayout(card_dir)
        cd_layout.setSpacing(4)
        repo_dir = get_repo_dir()
        is_git = (repo_dir / ".git").is_dir()

        d_title = QLabel(f"Quellverzeichnis: {repo_dir}")
        d_title.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {CachyColors.TEXT_PRIMARY};")
        d_sub = QLabel("Git-Repository aktiv (Aktualisierungen via git pull)" if is_git else "Lokale Standalone-Installation")
        d_sub.setStyleSheet(f"font-size: 11px; color: {CachyColors.ACCENT_EMERALD if is_git else CachyColors.TEXT_MUTED};")
        cd_layout.addWidget(d_title)
        cd_layout.addWidget(d_sub)
        layout.addWidget(card_dir)

        layout.addStretch()

    def _init_changelog_tab(self):
        layout = QVBoxLayout(self.tab_changelog)
        layout.setContentsMargins(12, 12, 12, 12)

        self.txt_changelog = QTextBrowser()
        self.txt_changelog.setOpenExternalLinks(True)
        self.txt_changelog.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {CachyColors.BG_CARD};
                color: {CachyColors.TEXT_PRIMARY};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 12px;
                font-size: 13px;
                line-height: 1.5;
            }}
        """)
        layout.addWidget(self.txt_changelog)

    def _init_log_tab(self):
        layout = QVBoxLayout(self.tab_log)
        layout.setContentsMargins(12, 12, 12, 12)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        font = QFont("JetBrains Mono", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.txt_log.setFont(font)
        self.txt_log.setStyleSheet(f"""
            QTextEdit {{
                background-color: #06090e;
                color: #cbd5e1;
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        layout.addWidget(self.txt_log)

    def start_check(self):
        """Starts GitHub check in worker thread."""
        self.btn_refresh.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.badge_status.setText("Wird geprüft...")
        self.lbl_status.setText("Frage GitHub API ab...")

        self.checker_worker = GitHubUpdateCheckerWorker()
        self.checker_worker.finished.connect(self._on_check_finished)
        self.checker_worker.start()

    def _on_check_finished(self, info: GitHubUpdateInfo):
        self.latest_info = info
        self.btn_refresh.setEnabled(True)
        self.progress_bar.setVisible(False)

        self.lbl_versions.setText(f"Installiert: v{info.installed_version}  │  Auf GitHub: v{info.remote_version}")
        self.lbl_repo_name.setText(f"https://github.com/{info.github_repo}")

        if info.has_update:
            self.badge_status.setText("⬆ Update verfügbar")
            self.badge_status.setStyleSheet(f"""
                background-color: {CachyColors.ACCENT_AMBER};
                color: #000000;
                padding: 5px 12px;
                border-radius: 6px;
                font-weight: 800;
                font-size: 11px;
            """)
            self.btn_update_now.setEnabled(True)
            self.lbl_status.setText(f"Eine neue Version (v{info.remote_version}) ist auf GitHub verfügbar!")
        else:
            self.badge_status.setText("✓ Aktuell")
            self.badge_status.setStyleSheet(f"""
                background-color: rgba(0, 212, 148, 0.15);
                color: {CachyColors.ACCENT_EMERALD};
                border: 1px solid {CachyColors.ACCENT_EMERALD};
                padding: 5px 12px;
                border-radius: 6px;
                font-weight: 700;
                font-size: 11px;
            """)
            self.btn_update_now.setEnabled(True)
            self.btn_update_now.setText("  Neu installieren")
            self.lbl_status.setText("CachyOS Update Center ist auf dem neuesten Stand.")

        # Update changelog
        if info.release_notes:
            self.txt_changelog.setMarkdown(f"## Version v{info.remote_version}\n\n{info.release_notes}")
        else:
            self.txt_changelog.setMarkdown(
                f"### CachyOS Update Center v{info.installed_version}\n\n"
                "- Integrierte automatische Spiegelserver-Bewertung vor Updates\n"
                "- Echtzeit-Online-Problemprüfung & Auto-Ausschluss problematischer Pakete\n"
                "- BTRFS Snapper Snapshot-Schutz\n"
                "- Unterstützung für Pacman, CachyOS v3/v4 und AUR (yay)\n"
            )

        if info.check_error:
            self.txt_log.append(f"[Hinweis] {info.check_error}\n")

    def edit_github_repo(self):
        curr = get_github_repo()
        repo, ok = QInputDialog.getText(
            self,
            "GitHub-Repository verknüpfen",
            "Gib dein GitHub-Repository im Format 'Benutzername/Repository' ein:\n"
            "(z. B. CachyOS/cachyos-update-center oder julian/cachyos-update-center):",
            text=curr,
        )
        if ok and repo.strip():
            set_github_repo(repo.strip())
            self.lbl_repo_name.setText(f"https://github.com/{get_github_repo()}")
            QMessageBox.information(
                self,
                "GitHub verknüpft",
                f"Repository erfolgreich verknüpft:\nhttps://github.com/{get_github_repo()}",
            )
            self.start_check()

    def run_github_update(self):
        """Executes git pull or source update + install.sh."""
        repo_dir = get_repo_dir()
        installer = repo_dir / "install.sh"
        if not installer.exists():
            QMessageBox.warning(self, "Fehler", f"install.sh nicht gefunden in:\n{repo_dir}")
            return

        steps: List[UpdateStep] = []

        # Step 1: Git pull if git repository
        if (repo_dir / ".git").is_dir() and shutil.which("git"):
            steps.append(
                UpdateStep(
                    name="GitHub Quellcode synchronisieren (git pull)",
                    command=["git", "-C", str(repo_dir), "pull", "--rebase"],
                    description="Holt die neuesten Code-Änderungen von GitHub",
                )
            )

        # Step 2: Run install.sh to install binaries and desktop entries
        steps.append(
            UpdateStep(
                name="CachyOS Update Center neu installieren",
                command=["bash", str(installer)],
                description="Installiert Launcher, Anwendungsdateien und Icons",
            )
        )

        # Switch to terminal tab
        self.tabs.setCurrentIndex(2)
        self.btn_refresh.setEnabled(False)
        self.btn_update_now.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_status.setText("Aktualisiere Programm über GitHub...")

        self.exec_worker = GitHubUpdateExecWorker(steps)
        self.exec_worker.output_line.connect(self._on_log_line)
        self.exec_worker.completed.connect(self._on_update_completed)
        self.exec_worker.start()

    def _on_log_line(self, line: str):
        cursor = self.txt_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(line + "\n")
        self.txt_log.setTextCursor(cursor)
        self.txt_log.ensureCursorVisible()

    def _on_update_completed(self, success: bool, msg: str):
        self.progress_bar.setVisible(False)
        self.btn_refresh.setEnabled(True)

        if success:
            self.app_was_updated = True
            self.lbl_status.setText("Aktualisierung erfolgreich!")
            self.btn_restart.setVisible(True)
            QMessageBox.information(
                self,
                "Update abgeschlossen",
                "Das CachyOS Update Center wurde erfolgreich über GitHub aktualisiert!\n\n"
                "Klicke auf 'Anwendung neu starten', um die aktualisierte Version zu laden.",
            )
        else:
            self.lbl_status.setText(f"Fehler beim Update: {msg}")
            self.btn_update_now.setEnabled(True)
            QMessageBox.warning(self, "Update fehlgeschlagen", f"Aktualisierung konnte nicht abgeschlossen werden:\n{msg}")

    def restart_application(self):
        """Restarts the running application."""
        self.close()
        python = sys.executable
        os.execl(python, python, *sys.argv)
