"""
Update manager and maintenance center for CachyOS Update Center.
Includes multi-component status checks (GUI, Spiegelserver-Engine, Snapper Snapshot Schutz, Online-Sicherheitsfeed),
batch updating queue, background silent checking, changelog viewer, and 1-click self-update from GitHub.
Modeled after the architecture of Cachy Security Suite (aur-scanner-gui).
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from typing import List, Optional, Tuple

from PyQt6.QtCore import QDateTime, QProcess, QSettings, QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
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

# Ensure parent directory is in sys.path for direct script execution
_pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

import cachyos_update_center

try:
    from .styles import CachyColors
    from .core.mirror_rater import MirrorRater
    from .core.package_checker import PackageChecker
    from .core.snapper_helper import SnapperHelper
except (ImportError, ValueError):
    from cachyos_update_center.styles import CachyColors
    from cachyos_update_center.core.mirror_rater import MirrorRater
    from cachyos_update_center.core.package_checker import PackageChecker
    from cachyos_update_center.core.snapper_helper import SnapperHelper



@dataclass
class UpdateInfo:
    gui_installed: str = cachyos_update_center.__version__
    gui_remote: str = cachyos_update_center.__version__
    gui_has_update: bool = False

    github_repo: Optional[str] = None
    github_release_url: Optional[str] = None
    github_tarball_url: Optional[str] = None
    github_asset_api_url: Optional[str] = None
    github_release_notes: Optional[str] = None
    github_auth_error: bool = False
    github_error_message: Optional[str] = None

    mirrors_rater_available: bool = False
    mirrors_rater_version: str = "Unbekannt"
    mirrors_last_modified: str = "Unbekannt"
    mirrors_need_rating: bool = False

    snapper_available: bool = False
    snapper_configured: bool = False
    kernel_version: str = ""

    online_feed_status: str = "Bereit"
    online_issues_count: int = 0
    check_error: Optional[str] = None
    checked_at: Optional[datetime.datetime] = None

    def total_updates_pending(self) -> int:
        count = 0
        if self.gui_has_update:
            count += 1
        if self.mirrors_need_rating:
            count += 1
        return count


DEFAULT_GITHUB_REPO = "lenzi96/cachyos-update-center"


def get_github_repo() -> Optional[str]:
    """Retrieves configured or git-detected GitHub repository (e.g. 'owner/repo')."""
    settings = QSettings("CachyOS", "CachyOSUpdateCenter")
    custom = settings.value("updater/github_repo", "").strip()
    if custom:
        return custom

    source_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        res = subprocess.run(
            ["git", "-C", source_dir, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            url = res.stdout.strip()
            m = re.search(r"github\.com[:/]([^/]+)/([^/\.]+)", url)
            if m:
                repo = f"{m.group(1)}/{m.group(2)}"
                return repo[:-4] if repo.endswith(".git") else repo
    except Exception:
        pass
    return DEFAULT_GITHUB_REPO


def set_github_repo(repo_str: str) -> None:
    """Saves configured GitHub repository and updates git remote origin if in git repo."""
    repo_clean = repo_str.strip()
    m = re.search(r"github\.com[:/]([^/]+)/([^/\.]+)", repo_clean)
    if m:
        repo_clean = f"{m.group(1)}/{m.group(2)}"
        if repo_clean.endswith(".git"):
            repo_clean = repo_clean[:-4]

    settings = QSettings("CachyOS", "CachyOSUpdateCenter")
    settings.setValue("updater/github_repo", repo_clean)

    source_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.isdir(os.path.join(source_dir, ".git")) and repo_clean:
        target_url = f"https://github.com/{repo_clean}.git"
        check_rem = subprocess.run(["git", "-C", source_dir, "remote"], capture_output=True, text=True, check=False)
        if "origin" in check_rem.stdout:
            subprocess.run(["git", "-C", source_dir, "remote", "set-url", "origin", target_url], check=False)
        else:
            subprocess.run(["git", "-C", source_dir, "remote", "add", "origin", target_url], check=False)


def get_github_token() -> Optional[str]:
    """Retrieves GitHub personal access token from QSettings, env, or ~/.git-credentials."""
    settings = QSettings("CachyOS", "CachyOSUpdateCenter")
    token = settings.value("updater/github_token", "").strip()
    if token:
        return token
    env_token = os.environ.get("GITHUB_TOKEN", "").strip() or os.environ.get("GH_TOKEN", "").strip()
    if env_token:
        return env_token
    git_cred_path = os.path.expanduser("~/.git-credentials")
    if os.path.exists(git_cred_path):
        try:
            with open(git_cred_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "github.com" in line:
                        m = re.search(r":([^@:]+)@github\.com", line)
                        if m:
                            tok = m.group(1).strip()
                            if tok.startswith("github_pat_") or tok.startswith("ghp_"):
                                return tok
        except Exception:
            pass
    cfg_token_path = os.path.expanduser("~/.config/cachyos-update-center/token")
    if os.path.exists(cfg_token_path):
        try:
            with open(cfg_token_path, "r", encoding="utf-8") as f:
                t = f.read().strip()
                if t:
                    return t
        except Exception:
            pass
    return None


def set_github_token(token_str: str) -> None:
    """Saves configured GitHub personal access token in QSettings and config file."""
    token_clean = token_str.strip()
    settings = QSettings("CachyOS", "CachyOSUpdateCenter")
    settings.setValue("updater/github_token", token_clean)

    cfg_token_path = os.path.expanduser("~/.config/cachyos-update-center/token")
    try:
        os.makedirs(os.path.dirname(cfg_token_path), exist_ok=True)
        with open(cfg_token_path, "w", encoding="utf-8") as f:
            f.write(token_clean)
    except Exception:
        pass


def compare_versions(v1: str, v2: str) -> int:
    """Uses vercmp if available, else numeric fallback."""
    v1_clean = v1.lstrip("v").strip()
    v2_clean = v2.lstrip("v").strip()

    if shutil.which("vercmp"):
        try:
            res = subprocess.run(
                ["vercmp", v1_clean, v2_clean],
                capture_output=True,
                text=True,
                check=False,
            )
            return int(res.stdout.strip())
        except Exception:
            pass

    parts1 = [int(p) for p in re.findall(r"\d+", v1_clean)]
    parts2 = [int(p) for p in re.findall(r"\d+", v2_clean)]
    return (parts1 > parts2) - (parts1 < parts2)


class UpdateCheckerWorker(QThread):
    finished = pyqtSignal(UpdateInfo)

    def run(self):
        info = UpdateInfo()
        info.gui_installed = cachyos_update_center.__version__
        info.checked_at = datetime.datetime.now()

        # 1. Check Mirror Rater Engine
        info.mirrors_rater_available = (shutil.which("cachyos-rate-mirrors") is not None) or (shutil.which("rate-mirrors") is not None)
        if shutil.which("cachyos-rate-mirrors"):
            info.mirrors_rater_version = "cachyos-rate-mirrors (System)"
        elif shutil.which("rate-mirrors"):
            info.mirrors_rater_version = "rate-mirrors (Arch)"
        else:
            info.mirrors_rater_version = "Nicht installiert"

        m_info = MirrorRater.get_current_active_mirrors()
        info.mirrors_last_modified = m_info.get("last_modified", "Unbekannt")

        # 2. Check Snapper & Kernel
        info.snapper_available = SnapperHelper.is_available()
        info.snapper_configured = SnapperHelper.has_root_config() if info.snapper_available else False
        info.kernel_version = PackageChecker.get_running_kernel()

        # 3. Check GitHub Releases API
        gh_repo = get_github_repo()
        gh_token = get_github_token()
        if gh_repo:
            info.github_repo = gh_repo
            try:
                gh_url = f"https://api.github.com/repos/{gh_repo}/releases/latest"
                headers = {
                    "User-Agent": f"cachyos-update-center/{info.gui_installed}",
                    "Accept": "application/vnd.github+json",
                }
                if gh_token:
                    headers["Authorization"] = f"Bearer {gh_token}"
                gh_req = urllib.request.Request(
                    gh_url,
                    headers=headers,
                )
                with urllib.request.urlopen(gh_req, timeout=8) as gh_resp:
                    if gh_resp.status == 200:
                        gh_data = json.loads(gh_resp.read().decode())
                        tag = gh_data.get("tag_name", "").lstrip("v").strip()
                        if tag:
                            info.gui_remote = tag
                            info.github_release_url = gh_data.get("html_url", "")
                            info.github_release_notes = gh_data.get("body", "")
                            for asset in gh_data.get("assets", []):
                                if asset.get("name", "").endswith((".tar.gz", ".zip")):
                                    info.github_tarball_url = asset.get("browser_download_url", "")
                                    info.github_asset_api_url = asset.get("url", "")
                                    break
                            if not info.github_tarball_url:
                                info.github_tarball_url = gh_data.get("tarball_url", "") or f"https://github.com/{gh_repo}/archive/refs/tags/v{tag}.tar.gz"
            except urllib.error.HTTPError as err:
                if err.code in (401, 403, 404):
                    info.github_auth_error = True
                    if not gh_token:
                        info.github_error_message = "Repository ist privat oder nicht erreichbar. Bitte GitHub-Token hinterlegen."
                    else:
                        info.github_error_message = f"GitHub-Fehler {err.code}: Token ungültig oder unzureichende Rechte."
                else:
                    info.github_error_message = f"GitHub HTTP-Fehler {err.code}"
            except Exception as err:
                info.github_error_message = f"Netzwerkfehler: {str(err)}"

        # Compare GUI versions
        if info.gui_installed and info.gui_remote and info.gui_remote != "Unbekannt":
            cmp_gui = compare_versions(info.gui_installed, info.gui_remote)
            info.gui_has_update = cmp_gui < 0

        self.finished.emit(info)


@dataclass
class UpdateStep:
    name: str
    command: List[str]
    description: str
    is_gui_update: bool = False


class BatchUpdateWorker(QThread):
    step_started = pyqtSignal(int, int, str)
    output_line = pyqtSignal(str)
    all_completed = pyqtSignal(bool, str, bool)

    def __init__(self, steps: List[UpdateStep]):
        super().__init__()
        self.steps = steps
        self.process: Optional[subprocess.Popen] = None
        self._is_cancelled = False
        self.gui_was_updated = False

    def cancel(self):
        self._is_cancelled = True
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=1)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass

    def run(self):
        total = len(self.steps)
        if total == 0:
            self.all_completed.emit(True, "Keine anstehenden Aufgaben.", False)
            return

        all_success = True
        for idx, step in enumerate(self.steps, start=1):
            if self._is_cancelled:
                self.output_line.emit("\n[!] Vorgang durch Benutzer abgebrochen.")
                self.all_completed.emit(False, "Aktualisierung abgebrochen.", self.gui_was_updated)
                return

            self.step_started.emit(idx, total, step.name)
            self.output_line.emit(f"\n=======================================================")
            self.output_line.emit(f"[{idx}/{total}] {step.name}")
            self.output_line.emit(f"Befehl: {' '.join(step.command)}")
            self.output_line.emit(f"=======================================================\n")

            env = os.environ.copy()
            _pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if "PYTHONPATH" in env and env["PYTHONPATH"]:
                env["PYTHONPATH"] = f"{_pkg_root}:{env['PYTHONPATH']}"
            else:
                env["PYTHONPATH"] = _pkg_root

            try:
                self.process = subprocess.Popen(
                    step.command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env,
                )

                for line in iter(self.process.stdout.readline, ""):
                    if self._is_cancelled:
                        break
                    line_clean = line.rstrip()
                    if line_clean:
                        self.output_line.emit(line_clean)

                self.process.stdout.close()
                ret = self.process.wait()

                if ret != 0 and not self._is_cancelled:
                    all_success = False
                    self.output_line.emit(f"\n[✗] Schritt '{step.name}' schlug fehl (Exit Code {ret})")
                    break
                elif not self._is_cancelled:
                    self.output_line.emit(f"\n[✓] Schritt '{step.name}' erfolgreich abgeschlossen.")
                    if step.is_gui_update:
                        self.gui_was_updated = True

            except Exception as exc:
                all_success = False
                self.output_line.emit(f"\n[FEHLER] Ausnahme bei Ausführung: {exc}")
                break

        if self._is_cancelled:
            self.all_completed.emit(False, "Vorgang abgebrochen.", self.gui_was_updated)
        elif all_success:
            self.all_completed.emit(True, "Alle Aktualisierungen erfolgreich durchgeführt!", self.gui_was_updated)
        else:
            self.all_completed.emit(False, "Ein oder mehrere Schritte schlugen fehl.", self.gui_was_updated)


class UpdateDialog(QDialog):
    """
    Modern modal update and maintenance dialog for CachyOS Update Center.
    Matches the design and workflow of the Cachy Security Suite (aur-scanner-gui).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update & Wartungs-Center – CachyOS")
        self.resize(780, 600)
        self.setMinimumSize(700, 520)

        self.checker_worker: Optional[UpdateCheckerWorker] = None
        self.batch_worker: Optional[BatchUpdateWorker] = None
        self.latest_info: Optional[UpdateInfo] = None

        self.init_ui()
        self.start_check()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 18, 20, 16)
        root_layout.setSpacing(12)

        # ----------------------------------------------------------------------
        # Top Header
        # ----------------------------------------------------------------------
        header_layout = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(2)

        lbl_title = QLabel("CachyOS Update & Wartungs-Center")
        lbl_title.setStyleSheet(f"font-size: 19px; font-weight: 800; color: {CachyColors.TEXT_PRIMARY};")
        lbl_desc = QLabel("Verwalte CachyOS Update Center, Spiegelserver-Engine, Snapper-Snapshots und GitHub-Releases.")
        lbl_desc.setStyleSheet(f"font-size: 11px; color: {CachyColors.TEXT_SECONDARY};")
        lbl_desc.setWordWrap(True)

        header_text.addWidget(lbl_title)
        header_text.addWidget(lbl_desc)
        header_layout.addLayout(header_text)
        header_layout.addStretch()

        self.btn_refresh = QPushButton("  Auf Updates prüfen")
        self.btn_refresh.setIcon(QIcon.fromTheme("view-refresh"))
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.start_check)
        header_layout.addWidget(self.btn_refresh)

        self.btn_update_all = QPushButton("  🚀 Alle aktualisieren")
        self.btn_update_all.setProperty("class", "btn-primary")
        self.btn_update_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update_all.setEnabled(False)
        self.btn_update_all.clicked.connect(self.run_update_all)
        header_layout.addWidget(self.btn_update_all)

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
        # Tab Widget
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
                font-size: 11px;
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

        # Tab 1: Status & Komponenten
        self.tab_components = QWidget()
        self.init_components_tab()
        self.tabs.addTab(self.tab_components, "Status && Komponenten")

        # Tab 2: Was ist neu? (Changelog)
        self.tab_changelog = QWidget()
        self.init_changelog_tab()
        self.tabs.addTab(self.tab_changelog, "Was ist neu? (Changelog)")

        # Tab 3: Terminal-Ausgabe
        self.tab_log = QWidget()
        self.init_log_tab()
        self.tabs.addTab(self.tab_log, "Terminal-Ausgabe")

        root_layout.addWidget(self.tabs, stretch=1)

        # ----------------------------------------------------------------------
        # Bottom Bar
        # ----------------------------------------------------------------------
        bottom_layout = QHBoxLayout()
        self.lbl_status_summary = QLabel("Bereit.")
        self.lbl_status_summary.setStyleSheet(f"font-size: 11px; color: {CachyColors.TEXT_SECONDARY};")
        self.lbl_status_summary.setWordWrap(True)
        bottom_layout.addWidget(self.lbl_status_summary, 1)

        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setProperty("class", "btn-danger")
        self.btn_cancel.clicked.connect(self.cancel_active_process)
        bottom_layout.addWidget(self.btn_cancel)

        self.btn_restart = QPushButton("🔄 Anwendung neu starten")
        self.btn_restart.setProperty("class", "btn-primary")
        self.btn_restart.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_restart.setVisible(False)
        self.btn_restart.clicked.connect(self.restart_application)
        bottom_layout.addWidget(self.btn_restart)

        btn_close = QPushButton("Schließen")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(btn_close)

        root_layout.addLayout(bottom_layout)

    def init_components_tab(self):
        scroll = QScrollArea(self.tab_components)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(12)

        # ----------------------------------------------------------------------
        # Card 1: CachyOS Update Center (GUI)
        # ----------------------------------------------------------------------
        card_gui = QFrame()
        card_gui.setObjectName("cardGui")
        card_gui.setStyleSheet(f"""
            QFrame#cardGui {{
                background-color: {CachyColors.BG_CARD};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 10px;
            }}
            QFrame#cardGui QLabel {{ background: transparent; border: none; }}
        """)
        c1_layout = QHBoxLayout(card_gui)
        c1_layout.setContentsMargins(14, 12, 14, 12)
        c1_layout.setSpacing(14)

        icon_c1 = QLabel("⚡")
        icon_c1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_c1.setFixedSize(40, 40)
        icon_c1.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(0, 212, 148, 0.2), stop:1 rgba(0, 171, 119, 0.08));
            border: 1px solid rgba(0, 212, 148, 0.35);
            border-radius: 20px;
            font-size: 20px;
        """)
        c1_layout.addWidget(icon_c1)

        c1_text = QVBoxLayout()
        c1_text.setSpacing(2)
        lbl_c1_title = QLabel("CachyOS Update Center (Grafische Oberfläche)")
        lbl_c1_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {CachyColors.TEXT_PRIMARY};")
        self.lbl_c1_version = QLabel(f"Installiert: v{cachyos_update_center.__version__}")
        self.lbl_c1_version.setStyleSheet(f"font-size: 11px; color: {CachyColors.TEXT_SECONDARY};")
        self.lbl_c1_github = QLabel("GitHub: Prüfe...")
        self.lbl_c1_github.setStyleSheet(f"font-size: 10px; color: {CachyColors.TEXT_MUTED};")
        c1_text.addWidget(lbl_c1_title)
        c1_text.addWidget(self.lbl_c1_version)
        c1_text.addWidget(self.lbl_c1_github)
        c1_layout.addLayout(c1_text, stretch=1)

        self.badge_c1 = QLabel("✓ Aktuell")
        self.badge_c1.setStyleSheet(f"""
            background-color: rgba(0, 212, 148, 0.15);
            color: {CachyColors.ACCENT_EMERALD};
            border: 1px solid {CachyColors.ACCENT_EMERALD};
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 11px;
        """)
        c1_layout.addWidget(self.badge_c1)

        c1_btn_layout = QVBoxLayout()
        c1_btn_layout.setSpacing(4)

        self.btn_update_gui = QPushButton("Neu installieren")
        self.btn_update_gui.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update_gui.clicked.connect(self.reinstall_gui)
        c1_btn_layout.addWidget(self.btn_update_gui)

        self.btn_link_github = QPushButton("🔗 GitHub-Repo...")
        self.btn_link_github.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_link_github.setStyleSheet(f"""
            QPushButton {{
                padding: 4px 8px;
                border-radius: 5px;
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                background: rgba(255, 255, 255, 0.05);
                color: {CachyColors.TEXT_SECONDARY};
                font-size: 10px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: rgba(255, 255, 255, 0.1);
                color: {CachyColors.TEXT_PRIMARY};
            }}
        """)
        self.btn_link_github.clicked.connect(self.configure_github_repo)
        c1_btn_layout.addWidget(self.btn_link_github)

        c1_layout.addLayout(c1_btn_layout)
        layout.addWidget(card_gui)

        # ----------------------------------------------------------------------
        # Card 2: Spiegelserver-Bewertungs-Engine (CLI)
        # ----------------------------------------------------------------------
        card_mirrors = QFrame()
        card_mirrors.setObjectName("cardMirrors")
        card_mirrors.setStyleSheet(f"""
            QFrame#cardMirrors {{
                background-color: {CachyColors.BG_CARD};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 10px;
            }}
            QFrame#cardMirrors QLabel {{ background: transparent; border: none; }}
        """)
        c2_layout = QHBoxLayout(card_mirrors)
        c2_layout.setContentsMargins(14, 12, 14, 12)
        c2_layout.setSpacing(14)

        icon_c2 = QLabel("🌐")
        icon_c2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_c2.setFixedSize(40, 40)
        icon_c2.setStyleSheet(f"""
            background: rgba(0, 210, 255, 0.12);
            border: 1px solid rgba(0, 210, 255, 0.3);
            border-radius: 20px;
            font-size: 20px;
        """)
        c2_layout.addWidget(icon_c2)

        c2_text = QVBoxLayout()
        c2_text.setSpacing(2)
        lbl_c2_title = QLabel("Spiegelserver-Bewertungs-Engine (cachyos-rate-mirrors)")
        lbl_c2_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {CachyColors.TEXT_PRIMARY};")
        self.lbl_c2_status = QLabel("Prüfe Engine-Status...")
        self.lbl_c2_status.setStyleSheet(f"font-size: 11px; color: {CachyColors.TEXT_SECONDARY};")
        self.lbl_c2_sub = QLabel("Zuletzt bewertet: Kürzlich")
        self.lbl_c2_sub.setStyleSheet(f"font-size: 10px; color: {CachyColors.TEXT_MUTED};")
        c2_text.addWidget(lbl_c2_title)
        c2_text.addWidget(self.lbl_c2_status)
        c2_text.addWidget(self.lbl_c2_sub)
        c2_layout.addLayout(c2_text, stretch=1)

        self.badge_c2 = QLabel("✓ Bereit")
        self.badge_c2.setStyleSheet(f"""
            background-color: rgba(0, 212, 148, 0.15);
            color: {CachyColors.ACCENT_EMERALD};
            border: 1px solid {CachyColors.ACCENT_EMERALD};
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 11px;
        """)
        c2_layout.addWidget(self.badge_c2)

        self.btn_rate_mirrors = QPushButton("Spiegel bewerten")
        self.btn_rate_mirrors.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rate_mirrors.clicked.connect(self.benchmark_and_rate_mirrors)
        c2_layout.addWidget(self.btn_rate_mirrors)
        layout.addWidget(card_mirrors)

        # ----------------------------------------------------------------------
        # Card 3: BTRFS Snapper Snapshot-Schutz & Kernel
        # ----------------------------------------------------------------------
        card_snap = QFrame()
        card_snap.setObjectName("cardSnap")
        card_snap.setStyleSheet(f"""
            QFrame#cardSnap {{
                background-color: {CachyColors.BG_CARD};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 10px;
            }}
            QFrame#cardSnap QLabel {{ background: transparent; border: none; }}
        """)
        c3_layout = QHBoxLayout(card_snap)
        c3_layout.setContentsMargins(14, 12, 14, 12)
        c3_layout.setSpacing(14)

        icon_c3 = QLabel("🛡️")
        icon_c3.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_c3.setFixedSize(40, 40)
        icon_c3.setStyleSheet(f"""
            background: rgba(168, 85, 247, 0.15);
            border: 1px solid rgba(168, 85, 247, 0.3);
            border-radius: 20px;
            font-size: 20px;
        """)
        c3_layout.addWidget(icon_c3)

        c3_text = QVBoxLayout()
        c3_text.setSpacing(2)
        lbl_c3_title = QLabel("Ausfallsicherung & BTRFS-Snapshots (Snapper)")
        lbl_c3_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {CachyColors.TEXT_PRIMARY};")
        self.lbl_c3_status = QLabel("Prüfe Snapper-Konfiguration...")
        self.lbl_c3_status.setStyleSheet(f"font-size: 11px; color: {CachyColors.TEXT_SECONDARY};")
        self.lbl_c3_kernel = QLabel("Kernel: Linux CachyOS")
        self.lbl_c3_kernel.setStyleSheet(f"font-size: 10px; color: {CachyColors.TEXT_MUTED};")
        c3_text.addWidget(lbl_c3_title)
        c3_text.addWidget(self.lbl_c3_status)
        c3_text.addWidget(self.lbl_c3_kernel)
        c3_layout.addLayout(c3_text, stretch=1)

        self.badge_c3 = QLabel("✓ Aktiv")
        self.badge_c3.setStyleSheet(f"""
            background-color: rgba(0, 212, 148, 0.15);
            color: {CachyColors.ACCENT_EMERALD};
            border: 1px solid {CachyColors.ACCENT_EMERALD};
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 11px;
        """)
        c3_layout.addWidget(self.badge_c3)

        self.btn_create_snap = QPushButton("Snapshot anlegen")
        self.btn_create_snap.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_create_snap.clicked.connect(self.create_snapshot_step)
        c3_layout.addWidget(self.btn_create_snap)
        layout.addWidget(card_snap)

        # ----------------------------------------------------------------------
        # Card 4: Online-Sicherheitsfilter & Paketdatenbank
        # ----------------------------------------------------------------------
        card_filter = QFrame()
        card_filter.setObjectName("cardFilter")
        card_filter.setStyleSheet(f"""
            QFrame#cardFilter {{
                background-color: {CachyColors.BG_CARD};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 10px;
            }}
            QFrame#cardFilter QLabel {{ background: transparent; border: none; }}
        """)
        c4_layout = QHBoxLayout(card_filter)
        c4_layout.setContentsMargins(14, 12, 14, 12)
        c4_layout.setSpacing(14)

        icon_c4 = QLabel("📡")
        icon_c4.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_c4.setFixedSize(40, 40)
        icon_c4.setStyleSheet(f"""
            background: rgba(255, 179, 0, 0.15);
            border: 1px solid rgba(255, 179, 0, 0.3);
            border-radius: 20px;
            font-size: 20px;
        """)
        c4_layout.addWidget(icon_c4)

        c4_text = QVBoxLayout()
        c4_text.setSpacing(2)
        lbl_c4_title = QLabel("Online-Problemprüfung & Auto-Ausschluss")
        lbl_c4_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {CachyColors.TEXT_PRIMARY};")
        lbl_c4_desc = QLabel("Arch News Feed & CachyOS RSS Feeds live angebunden")
        lbl_c4_desc.setStyleSheet(f"font-size: 11px; color: {CachyColors.TEXT_SECONDARY};")
        c4_text.addWidget(lbl_c4_title)
        c4_text.addWidget(lbl_c4_desc)
        c4_layout.addLayout(c4_text, stretch=1)

        self.badge_c4 = QLabel("✓ Geschützt")
        self.badge_c4.setStyleSheet(f"""
            background-color: rgba(0, 212, 148, 0.15);
            color: {CachyColors.ACCENT_EMERALD};
            border: 1px solid {CachyColors.ACCENT_EMERALD};
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 11px;
        """)
        c4_layout.addWidget(self.badge_c4)

        self.btn_refresh_news = QPushButton("Feeds abfragen")
        self.btn_refresh_news.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh_news.clicked.connect(self.refresh_online_feeds)
        c4_layout.addWidget(self.btn_refresh_news)
        layout.addWidget(card_filter)

        layout.addStretch()

        scroll.setWidget(container)
        tab_layout = QVBoxLayout(self.tab_components)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)

    def init_changelog_tab(self):
        layout = QVBoxLayout(self.tab_changelog)
        layout.setContentsMargins(12, 12, 12, 12)

        self.txt_changelog = QTextBrowser()
        self.txt_changelog.setOpenExternalLinks(True)
        self.txt_changelog.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {CachyColors.BG_CARD};
                color: {CachyColors.TEXT_PRIMARY};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 14px;
                font-size: 12px;
                line-height: 1.5;
            }}
        """)
        layout.addWidget(self.txt_changelog)

    def load_changelog(self) -> str:
        content = ""
        if self.latest_info and self.latest_info.github_release_notes:
            content += f"# Neuestes GitHub-Release (v{self.latest_info.gui_remote})\n\n{self.latest_info.github_release_notes}\n\n---\n\n"

        candidates = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "CHANGELOG.md"),
            os.path.expanduser("~/.local/share/cachyos-update-center/CHANGELOG.md"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "CHANGELOG.md"),
            "/usr/share/cachyos-update-center/CHANGELOG.md",
        ]
        for p in candidates:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        content += f.read()
                        return content
                except Exception:
                    pass

        if content:
            return content

        return f"# CachyOS Update Center v{cachyos_update_center.__version__}\n\n- Garantierte vorherige Spiegelserver-Bewertung\n- Automatische Online-Problemprüfung\n- Snapper Snapshot-Schutz\n- Modernes Emerald-GUI"

    def init_log_tab(self):
        layout = QVBoxLayout(self.tab_log)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        log_header = QHBoxLayout()
        lbl_out = QLabel("Live-Befehlsausgabe:")
        lbl_out.setStyleSheet(f"font-weight: 600; font-size: 11px; color: {CachyColors.TEXT_SECONDARY};")
        log_header.addWidget(lbl_out)
        log_header.addStretch()

        btn_clear = QPushButton("Log leeren")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.clicked.connect(lambda: self.txt_log.clear())
        log_header.addWidget(btn_clear)
        layout.addLayout(log_header)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFont(QFont("JetBrains Mono, monospace", 9))
        self.txt_log.setStyleSheet(f"""
            QTextEdit {{
                background-color: #06090e;
                color: #e2e8f0;
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        layout.addWidget(self.txt_log, stretch=1)

    def start_check(self):
        self.btn_refresh.setEnabled(False)
        self.btn_update_all.setEnabled(False)
        self.progress_bar.setVisible(True)

        self.badge_c1.setText("Prüfe...")
        self.badge_c1.setStyleSheet(f"background-color: rgba(0, 210, 255, 0.15); color: {CachyColors.ACCENT_CYAN}; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 11px;")

        self.lbl_c1_github.setText("Frage GitHub API ab...")
        self.lbl_status_summary.setText("Überprüfe Systemkomponenten und GitHub-Releases...")

        self.checker_worker = UpdateCheckerWorker()
        self.checker_worker.finished.connect(self.on_check_finished)
        self.checker_worker.start()

    def on_check_finished(self, info: UpdateInfo):
        self.btn_refresh.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.latest_info = info

        # 1. Update GUI Card
        if info.github_auth_error:
            self.lbl_c1_version.setText(f"Installiert: v{info.gui_installed}  │  Verfügbar: Nicht abrufbar (404/Privat)")
            self.lbl_c1_github.setText(f"GitHub: {info.github_error_message or 'Repository ist privat'}")
            self.lbl_c1_github.setStyleSheet(f"color: {CachyColors.ACCENT_RED}; font-size: 11px;")
            self.badge_c1.setText("⚠️ Token erforderlich")
            self.badge_c1.setStyleSheet(f"background-color: rgba(255, 69, 91, 0.2); color: {CachyColors.ACCENT_RED}; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 11px;")
            self.btn_link_github.setText("🔑 Token hinterlegen...")
            self.btn_update_gui.setEnabled(False)
        else:
            self.lbl_c1_version.setText(f"Installiert: v{info.gui_installed}  │  Verfügbar: v{info.gui_remote}")
            self.btn_link_github.setText("🔗 GitHub-Repo...")
            if info.github_repo:
                self.lbl_c1_github.setText(f"GitHub: {info.github_repo} (Releases aktiv)")
                self.lbl_c1_github.setStyleSheet(f"color: {CachyColors.TEXT_MUTED}; font-size: 11px;")
            else:
                self.lbl_c1_github.setText("GitHub: Noch nicht verknüpft")

            if info.gui_has_update:
                self.badge_c1.setText(f"⬆ Update verfügbar (v{info.gui_remote})")
                self.badge_c1.setStyleSheet("background-color: #ea580c; color: #ffffff; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 11px;")
                self.btn_update_gui.setText("Jetzt aktualisieren")
                self.btn_update_gui.setProperty("class", "btn-primary")
                self.btn_update_gui.setEnabled(True)
            else:
                self.badge_c1.setText("✓ Aktuell")
                self.badge_c1.setStyleSheet(f"""
                    background-color: rgba(0, 212, 148, 0.15);
                    color: {CachyColors.ACCENT_EMERALD};
                    border: 1px solid {CachyColors.ACCENT_EMERALD};
                    padding: 4px 10px;
                    border-radius: 6px;
                    font-weight: 600;
                    font-size: 11px;
                """)
                self.btn_update_gui.setText("Neu installieren")
                self.btn_update_gui.setEnabled(True)

        # 2. Update Mirrors Card
        self.lbl_c2_status.setText(f"Engine: {info.mirrors_rater_version}")
        self.lbl_c2_sub.setText(f"Zuletzt bewertet: {info.mirrors_last_modified}")
        if not info.mirrors_rater_available:
            self.badge_c2.setText("Nicht installiert")
            self.badge_c2.setStyleSheet(f"background-color: rgba(255, 69, 91, 0.15); color: {CachyColors.ACCENT_RED}; border: 1px solid {CachyColors.ACCENT_RED}; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 11px;")
        else:
            self.badge_c2.setText("✓ Bereit")
            self.badge_c2.setStyleSheet(f"background-color: rgba(0, 212, 148, 0.15); color: {CachyColors.ACCENT_EMERALD}; border: 1px solid {CachyColors.ACCENT_EMERALD}; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 11px;")

        # 3. Update Snapper Card
        if info.snapper_available:
            self.lbl_c3_status.setText("BTRFS Snapper: Konfiguration 'root' aktiv" if info.snapper_configured else "BTRFS Snapper vorhanden (keine root-Konfig)")
            self.badge_c3.setText("✓ Bereit" if info.snapper_configured else "Konfigurieren")
            self.badge_c3.setStyleSheet(f"background-color: rgba(0, 212, 148, 0.15); color: {CachyColors.ACCENT_EMERALD}; border: 1px solid {CachyColors.ACCENT_EMERALD}; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 11px;")
        else:
            self.lbl_c3_status.setText("Snapper nicht installiert (Snapshots deaktiviert)")
            self.badge_c3.setText("Inaktiv")
            self.badge_c3.setStyleSheet(f"background-color: rgba(100, 116, 139, 0.15); color: {CachyColors.TEXT_MUTED}; border: 1px solid {CachyColors.BORDER_SUBTLE}; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 11px;")
        self.lbl_c3_kernel.setText(f"Kernel: {info.kernel_version}")

        # Update Changelog
        self.txt_changelog.setMarkdown(self.load_changelog())

        # Enable "Update All" button if update pending
        pending = info.total_updates_pending()
        if pending > 0:
            self.btn_update_all.setEnabled(True)
            self.btn_update_all.setText(f"  🚀 Alle aktualisieren ({pending})")
            self.lbl_status_summary.setText(f"{pending} Aktualisierung(en) verfügbar.")
        else:
            self.btn_update_all.setEnabled(False)
            self.btn_update_all.setText("  ✓ Alles auf neuestem Stand")
            self.lbl_status_summary.setText("Alle Komponenten und Schutzschilde sind auf dem neuesten Stand.")

        if info.check_error:
            self.txt_log.append(f"[Hinweis] {info.check_error}\n")

    def configure_github_repo(self):
        curr = get_github_repo() or ""
        repo, ok = QInputDialog.getText(
            self,
            "GitHub-Repository verknüpfen",
            "Gib dein GitHub-Repository im Format 'Benutzername/Repository' ein:\n"
            "(z. B. lenzi96/cachyos-update-center oder die HTTPS-URL):",
            text=curr,
        )
        if ok and repo.strip():
            set_github_repo(repo.strip())
            curr_token = get_github_token() or ""
            masked_token = (curr_token[:8] + "..." + curr_token[-4:]) if len(curr_token) > 12 else curr_token
            tok, tok_ok = QInputDialog.getText(
                self,
                "GitHub Access Token (optional)",
                "Gib dein GitHub Personal Access Token (PAT) ein\n"
                "(Erforderlich für private Repositories, optional für öffentliche Repositories):\n"
                f"Aktuell hinterlegt: {masked_token if masked_token else 'Keins'}",
                text=curr_token,
            )
            if tok_ok and tok.strip():
                set_github_token(tok.strip())
            active_repo = get_github_repo()
            QMessageBox.information(
                self,
                "GitHub verknüpft",
                f"Das Update-Center ist jetzt mit GitHub verknüpft:\nhttps://github.com/{active_repo}\n\nUpdates werden künftig direkt von dort bezogen.",
            )
            self.start_check()

    def reinstall_gui(self):
        source_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        installer = os.path.join(source_dir, "install.sh")

        steps = []
        if os.path.exists(installer) and os.path.isdir(os.path.join(source_dir, ".git")):
            try:
                res = subprocess.run(["git", "-C", source_dir, "remote"], capture_output=True, text=True, check=False)
                if "origin" in res.stdout:
                    steps.append(UpdateStep("GitHub Quellcode synchronisieren (git pull)", ["git", "-C", source_dir, "pull", "--rebase"], "Aktualisiere lokale Dateien vom GitHub-Repository"))
            except Exception:
                pass
            steps.append(UpdateStep("CachyOS Update Center Reinstallation", ["bash", installer], "Installiere grafische Oberfläche neu", is_gui_update=True))
        else:
            ver = self.latest_info.gui_remote if self.latest_info else cachyos_update_center.__version__
            asset_url = self.latest_info.github_asset_api_url if self.latest_info else ""
            tarball_url = self.latest_info.github_tarball_url if self.latest_info else ""
            updater_script = os.path.abspath(__file__)
            tok = get_github_token()
            cmd = [
                sys.executable,
                updater_script,
                "--download-and-install",
                "--version",
                ver,
                "--asset-url",
                asset_url or "",
                "--tarball-url",
                tarball_url or "",
            ]
            if tok:
                cmd.extend(["--token", tok])
            steps.append(UpdateStep(
                f"CachyOS Update Center v{ver} herunterladen & installieren",
                cmd,
                "Lädt das offizielle GitHub Release-Archiv herunter und installiert die neue Version",
                is_gui_update=True,
            ))

        self.execute_batch_steps(steps)

    def benchmark_and_rate_mirrors(self):
        cmd = ["cachyos-rate-mirrors"]
        if os.geteuid() != 0 and shutil.which("pkexec"):
            cmd = ["pkexec", "cachyos-rate-mirrors"]

        steps = [
            UpdateStep("Spiegelserver bewerten (cachyos-rate-mirrors)", cmd, "Führt Live-Benchmark durch und aktualisiert /etc/pacman.d/ Ranglisten")
        ]
        self.execute_batch_steps(steps)

    def create_snapshot_step(self):
        cmd = ["pkexec", "snapper", "-c", "root", "create", "-d", "Manuelles Backup via CachyOS Update Center"]
        steps = [
            UpdateStep("BTRFS Snapshot anlegen", cmd, "Erstellt einen neuen Wiederherstellungspunkt")
        ]
        self.execute_batch_steps(steps)

    def refresh_online_feeds(self):
        cmd = [sys.executable, "-c", "from cachyos_update_center.core.online_issue_checker import OnlineIssueChecker; items = OnlineIssueChecker.fetch_all_issues(); print(f'Erfolgreich {len(items)} Online-Meldungen analysiert.')"]
        steps = [
            UpdateStep("Online-Sicherheitsfeeds abrufen", cmd, "Fragt Arch Linux News und CachyOS Ankündigungen ab")
        ]
        self.execute_batch_steps(steps)

    def run_update_all(self):
        if not self.latest_info:
            return

        steps: List[UpdateStep] = []

        # 1. Snapshot
        if self.latest_info.snapper_available and self.latest_info.snapper_configured:
            steps.append(UpdateStep("BTRFS Vorab-Snapshot", ["pkexec", "snapper", "-c", "root", "create", "-d", "Automatischer Snapshot vor Komponenten-Update"], "Sicherheits-Wiederherstellungspunkt"))

        # 2. GUI
        if self.latest_info.gui_has_update:
            source_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            installer = os.path.join(source_dir, "install.sh")
            if os.path.exists(installer) and os.path.isdir(os.path.join(source_dir, ".git")):
                steps.append(UpdateStep("Quellcode aktualisieren (git pull)", ["git", "-C", source_dir, "pull", "--rebase"], "Git Pull"))
                steps.append(UpdateStep("CachyOS Update Center GUI", ["bash", installer], "GUI Reinstallation", is_gui_update=True))
            else:
                updater_script = os.path.abspath(__file__)
                tok = get_github_token()
                cmd = [
                    sys.executable,
                    updater_script,
                    "--download-and-install",
                    "--version",
                    self.latest_info.gui_remote,
                    "--asset-url",
                    self.latest_info.github_asset_api_url or "",
                    "--tarball-url",
                    self.latest_info.github_tarball_url or "",
                ]
                if tok:
                    cmd.extend(["--token", tok])
                steps.append(UpdateStep(
                    f"CachyOS Update Center v{self.latest_info.gui_remote} herunterladen & installieren",
                    cmd,
                    "Lädt das offizielle GitHub Release-Archiv herunter und installiert die neue Version",
                    is_gui_update=True,
                ))

        if not steps:
            QMessageBox.information(self, "Aktuell", "Es stehen keine ausstehenden Updates an.")
            return

        self.execute_batch_steps(steps)

    def execute_batch_steps(self, steps: List[UpdateStep]):
        self.btn_refresh.setEnabled(False)
        self.btn_update_all.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.progress_bar.setVisible(True)

        # Switch to terminal tab
        self.tabs.setCurrentIndex(2)

        self.batch_worker = BatchUpdateWorker(steps)
        self.batch_worker.step_started.connect(self.on_step_started)
        self.batch_worker.output_line.connect(self.on_log_line)
        self.batch_worker.all_completed.connect(self.on_batch_completed)
        self.batch_worker.start()

    def cancel_active_process(self):
        if self.batch_worker:
            self.batch_worker.cancel()
            self.btn_cancel.setEnabled(False)

    def on_step_started(self, current: int, total: int, title: str):
        self.lbl_status_summary.setText(f"Führe aus ({current}/{total}): {title}...")

    def on_log_line(self, line: str):
        cursor = self.txt_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(line + "\n")
        self.txt_log.setTextCursor(cursor)
        self.txt_log.ensureCursorVisible()

    def on_batch_completed(self, success: bool, message: str, gui_was_updated: bool):
        self.progress_bar.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(True)
        self.btn_refresh.setEnabled(True)

        self.lbl_status_summary.setText(message)

        if success:
            self.txt_log.append(f"\n[✓] {message}\n")
            if gui_was_updated:
                self.btn_restart.setVisible(True)
                reply = QMessageBox.question(
                    self,
                    "Update abgeschlossen - Neustart?",
                    "Das CachyOS Update Center wurde erfolgreich aktualisiert!\n\n"
                    "Möchtest du die Anwendung jetzt neu starten, um die Änderungen zu übernehmen?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.restart_application()
            else:
                QMessageBox.information(self, "Erfolg", message)
        else:
            self.txt_log.append(f"\n[✗] {message}\n")
            QMessageBox.warning(self, "Hinweis", f"{message}\n\nDetails findest du im Terminal-Ausgabe-Reiter.")

        self.start_check()

    def restart_application(self):
        """Cleanly restarts CachyOS Update Center."""
        launcher = shutil.which("cachyos-update-center") or sys.executable
        if launcher == sys.executable:
            QProcess.startDetached(sys.executable, sys.argv)
        else:
            QProcess.startDetached(launcher, [])
        QApplication.quit()


def download_and_install_release(version: str = "", asset_url: str = "", tarball_url: str = "", token: str = "") -> int:
    """
    Downloads GitHub release tarball, extracts it to /tmp, and executes install.sh.
    Supports both public repositories and private repositories with token.
    Modeled directly on aur-scanner-gui / Cachy Security Suite updater.
    """
    repo = get_github_repo() or DEFAULT_GITHUB_REPO
    token = token.strip() if token else (get_github_token() or "")

    if token:
        try:
            tag_slug = f"tags/v{version}" if version and not version.startswith("v") else (f"tags/{version}" if version else "latest")
            api_rel = f"https://api.github.com/repos/{repo}/releases/{tag_slug}"
            req = urllib.request.Request(api_rel, headers={
                "User-Agent": "cachyos-update-center",
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                version = data.get("tag_name", "").lstrip("v").strip() or version
                for asset in data.get("assets", []):
                    if asset.get("name", "").endswith((".tar.gz", ".zip")):
                        asset_url = asset.get("url", "")
                        tarball_url = asset.get("browser_download_url", "")
                        break
        except Exception:
            pass

    if not version:
        try:
            gh_url = f"https://api.github.com/repos/{repo}/releases/latest"
            headers = {"User-Agent": "cachyos-update-center", "Accept": "application/vnd.github+json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            req = urllib.request.Request(gh_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                version = data.get("tag_name", "").lstrip("v").strip()
                for asset in data.get("assets", []):
                    if asset.get("name", "").endswith((".tar.gz", ".zip")):
                        tarball_url = asset.get("browser_download_url", "")
                        asset_url = asset.get("url", "")
                        break
        except Exception as e:
            print(f"[FEHLER] Konnte Release-Informationen von GitHub nicht abrufen: {e}")
            return 1

    print("=======================================================")
    print("  CachyOS Update Center - Automatischer Release-Updater ")
    print("=======================================================")
    print(f"Ziel-Version : v{version}")
    print(f"Repository   : {repo}")
    print(f"Token aktiv  : {'Ja' if token else 'Nein (Öffentliches Repo)'}")
    print("-------------------------------------------------------")

    tmp_dir = tempfile.mkdtemp(prefix="cachy_update_")
    tar_path = os.path.join(tmp_dir, f"cachyos-update-center-v{version}.tar.gz")
    unpack_dir = os.path.join(tmp_dir, "unpacked")

    try:
        tag_name = version if version.startswith("v") else f"v{version}"
        clean_version = version.lstrip("v")

        # Select proper download URL
        download_url = ""
        if token and asset_url and asset_url.strip():
            download_url = asset_url.strip()
        elif tarball_url and tarball_url.strip():
            download_url = tarball_url.strip()
        else:
            if token:
                download_url = f"https://api.github.com/repos/{repo}/tarball/{tag_name}"
            else:
                download_url = f"https://github.com/{repo}/archive/refs/tags/{tag_name}.tar.gz"

        is_release_asset = ("/releases/assets/" in download_url)
        accept_header = "application/octet-stream" if is_release_asset else "application/vnd.github+json"

        print(f"[1/4] Lade Release-Paket herunter ({download_url})...")
        curl_bin = shutil.which("curl")
        download_ok = False

        if curl_bin:
            curl_cmd = [curl_bin, "-sSL", "-f"]
            if token and "api.github.com" in download_url:
                curl_cmd.extend(["-H", f"Authorization: Bearer {token}"])
            curl_cmd.extend(["-H", f"Accept: {accept_header}", download_url, "-o", tar_path])
            res = subprocess.run(curl_cmd, check=False)
            if res.returncode == 0 and os.path.exists(tar_path) and os.path.getsize(tar_path) > 1000:
                download_ok = True

        if not download_ok:
            class NoAuthRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
                    if new_req and "Authorization" in new_req.headers:
                        del new_req.headers["Authorization"]
                    return new_req

            opener = urllib.request.build_opener(NoAuthRedirect)
            headers = {"User-Agent": "CachyOS-Update-Center", "Accept": accept_header}
            if token and "api.github.com" in download_url:
                headers["Authorization"] = f"Bearer {token}"
            req = urllib.request.Request(download_url, headers=headers)
            try:
                with opener.open(req, timeout=30) as resp, open(tar_path, "wb") as out_f:
                    shutil.copyfileobj(resp, out_f)
                if os.path.exists(tar_path) and os.path.getsize(tar_path) > 1000:
                    download_ok = True
            except Exception as e:
                print(f"[Hinweis] urllib Download: {e}")

        if not download_ok:
            # Fallback to shallow git clone of release tag
            print("[Hinweis] Direktdownload nicht möglich, verwende git clone Fallback...")
            clone_dir = os.path.join(tmp_dir, "clone")
            clone_repo = f"https://{token}@github.com/{repo}.git" if token else f"https://github.com/{repo}.git"
            res_clone = subprocess.run(["git", "clone", "--depth", "1", "--branch", tag_name, clone_repo, clone_dir], check=False)
            if res_clone.returncode == 0 and os.path.isdir(clone_dir):
                unpack_dir = clone_dir
                download_ok = True
            else:
                print("[FEHLER] Herunterladen des Release-Archivs fehlgeschlagen.")
                return 1

        if os.path.exists(tar_path) and os.path.getsize(tar_path) > 1000:
            size_mb = os.path.getsize(tar_path) / (1024 * 1024)
            print(f"✓ Download erfolgreich ({size_mb:.2f} MB)")

            print("[2/4] Entpacke Archiv...")
            os.makedirs(unpack_dir, exist_ok=True)
            res_tar = subprocess.run(["tar", "-xzf", tar_path, "-C", unpack_dir], check=False)
            if res_tar.returncode != 0:
                print("[FEHLER] Archiv konnte nicht entpackt werden.")
                return 1
            print("✓ Entpacken abgeschlossen.")

        installer_path = None
        for root, dirs, files in os.walk(unpack_dir):
            if "install.sh" in files:
                installer_path = os.path.join(root, "install.sh")
                break

        if not installer_path:
            print("[FEHLER] install.sh im entpackten Release-Archiv nicht gefunden.")
            return 1

        print(f"[3/4] Führe Installation aus ({installer_path})...")
        os.chmod(installer_path, 0o755)
        res_inst = subprocess.run(["bash", installer_path], check=False)
        if res_inst.returncode != 0:
            print(f"[FEHLER] Installation schlug fehl mit Exit-Code {res_inst.returncode}")
            return res_inst.returncode

        print("[4/4] Bereinige temporäre Dateien...")
        print(f"✓ CachyOS Update Center wurde erfolgreich auf v{version} aktualisiert!")
        return 0

    finally:
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass


if __name__ == "__main__":
    if any(arg in sys.argv for arg in ("--download-and-install", "-h", "--help")):
        import argparse
        parser = argparse.ArgumentParser(description="CachyOS Update Center Standalone Release Installer")
        parser.add_argument("--download-and-install", action="store_true")
        parser.add_argument("--version", default="")
        parser.add_argument("--asset-url", default="")
        parser.add_argument("--tarball-url", default="")
        parser.add_argument("--token", default="")
        args, _ = parser.parse_known_args()
        if args.download_and_install:
            sys.exit(download_and_install_release(args.version, args.asset_url, args.tarball_url, args.token))
