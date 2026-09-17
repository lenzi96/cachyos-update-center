"""
Main Window for CachyOS Update Center.
Coordinates navigation, background package inspection, and update flows.
"""
import os
import shutil
import subprocess
from typing import List, Optional

from PyQt6.QtCore import QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .core.mirror_rater import MirrorRater
from .core.news_checker import NewsChecker
from .core.online_issue_checker import OnlineIssueChecker
from .core.package_checker import PackageChecker, PackageUpdate
from .styles import CACHY_STYLESHEET, CachyColors
from .updater import UpdateCheckerWorker, UpdateDialog, UpdateInfo
from .views.dashboard_view import DashboardView
from .views.execution_view import ExecutionView
from .views.maintenance_view import MaintenanceView
from .views.mirrors_view import MirrorsView
from .views.packages_view import PackagesView
from .views.settings_view import SettingsView


class PackageCheckWorker(QThread):
    """Background inspection worker to discover pending updates without freezing UI."""
    packages_loaded = pyqtSignal(list)
    news_loaded = pyqtSignal(list)
    status_text = pyqtSignal(str)

    def __init__(self, include_aur: bool = True, parent=None):
        super().__init__(parent)
        self.include_aur = include_aur

    def run(self):
        self.status_text.emit("Prüfe offizielle Repositorien...")
        official_pkgs = PackageChecker.check_official_updates()

        aur_pkgs = []
        if self.include_aur:
            self.status_text.emit("Prüfe AUR-Pakete...")
            aur_pkgs = PackageChecker.check_aur_updates()

        all_pkgs = official_pkgs + aur_pkgs

        # Online Issue & Security Checking
        if all_pkgs:
            self.status_text.emit("Prüfe Pakete online auf gemeldete Probleme, Sicherheits-Fixes & manuelle Eingriffe...")
            issues = OnlineIssueChecker.check_packages_detailed(all_pkgs)
            for p in all_pkgs:
                p_lower = p.name.lower()
                if p_lower in issues:
                    reps = issues[p_lower]
                    p.issues_list = reps
                    has_crit = any(r.severity == "CRITICAL" for r in reps)
                    has_sec_fix = any(r.is_security_fix for r in reps)
                    has_vuln = any(r.severity == "VULNERABILITY" for r in reps)
                    has_warn = any(r.severity == "WARNING" for r in reps)

                    rep = reps[0]
                    p.issue_reason = rep.reason
                    p.issue_url = rep.url
                    p.remediation_cmd = rep.remediation_cmd or ""

                    if has_crit:
                        p.has_online_issue = True
                        p.issue_severity = "CRITICAL"
                        p.is_auto_excluded = True
                        p.is_selected = False  # Auto-exclude breaking changes
                    elif has_vuln:
                        p.has_online_issue = True
                        p.issue_severity = "VULNERABILITY"
                    elif has_warn:
                        p.has_online_issue = True
                        p.issue_severity = "WARNING"

                    if has_sec_fix:
                        p.has_security_fix = True
                        if not p.issue_severity:
                            p.issue_severity = "SECURITY_FIX"

        self.packages_loaded.emit(all_pkgs)

        # Check news
        self.status_text.emit("Lade Systemankündigungen...")
        news = NewsChecker.fetch_latest_news()
        self.news_loaded.emit(news)


class MainWindow(QMainWindow):
    """Primary application window for CachyOS Update Center."""

    TAB_TITLES = {
        0: ("⚡ System-Übersicht", "Systemzustand, anstehende Updates und Schnellstart mit automatischer Spiegel-Bewertung"),
        1: ("📦 Paket-Verwaltung", "Detaillierte Paketliste mit automatischer Ausschlussfunktion problematischer Versionen"),
        2: ("🌐 Spiegelserver-Bewertung", "Live-Latenzmessung und pacman.d Ranglisten-Generierung für CachyOS & Arch"),
        3: ("▶ Aktualisierungs-Pipeline", "4-Phasen-Ausführung mit BTRFS-Snapshot, Spiegelservern & Live-Terminal"),
        4: ("🧹 Systempflege & Snapshots", "BTRFS Snapshots, Pacman-Cache bereinigen, verwaiste Pakete & Pacnew-Dateien"),
        5: ("⚙️ Einstellungen", "Konfiguration der Spiegelserver-Bewertung, Schutzfilter und GitHub-Updater"),
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CachyOS Update Center")
        self.resize(1120, 720)
        self.setMinimumSize(960, 600)

        # Window Icon
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "app_icon_64.png")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "app_icon.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.packages: List[PackageUpdate] = []
        self.check_worker: Optional[PackageCheckWorker] = None
        self.bg_github_worker: Optional[UpdateCheckerWorker] = None
        self.github_update_info: Optional[UpdateInfo] = None

        self.init_ui()
        self.apply_styles()
        self.start_initial_check()

        # Start silent GitHub update check in background
        QTimer.singleShot(1500, self.start_background_app_update_check)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ----------------------------------------------------------------------
        # Sidebar Navigation
        # ----------------------------------------------------------------------
        sidebar = QFrame()
        sidebar.setObjectName("navSidebar")
        sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 18, 14, 16)
        sidebar_layout.setSpacing(6)

        # App Brand Header
        brand_frame = QFrame()
        brand_layout = QHBoxLayout(brand_frame)
        brand_layout.setContentsMargins(4, 0, 4, 14)
        brand_layout.setSpacing(12)

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "app_icon_64.png")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "app_icon.svg")

        logo_lbl = QLabel()
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(38, 38, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_lbl.setPixmap(pixmap)
        else:
            logo_lbl.setText("⚡")
            logo_lbl.setStyleSheet("font-size: 26px;")
        logo_lbl.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(0, 212, 148, 0.2), stop:1 rgba(0, 171, 119, 0.08));
            border: 1px solid rgba(0, 212, 148, 0.35);
            border-radius: 10px;
            padding: 3px;
        """)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(2)
        title_lbl = QLabel("CachyOS")
        title_lbl.setStyleSheet(f"font-weight: 800; font-size: 16px; color: {CachyColors.TEXT_PRIMARY}; letter-spacing: 0.3px;")
        sub_title = QLabel(f"UPDATE CENTER v{__version__}")
        sub_title.setStyleSheet(f"""
            font-size: 9px;
            color: {CachyColors.ACCENT_EMERALD_LIGHT};
            font-weight: 800;
            letter-spacing: 0.8px;
            background: rgba(0, 212, 148, 0.12);
            border: 1px solid rgba(0, 212, 148, 0.25);
            border-radius: 4px;
            padding: 1px 5px;
        """)
        brand_text.addWidget(title_lbl)
        brand_text.addWidget(sub_title)

        brand_layout.addWidget(logo_lbl)
        brand_layout.addLayout(brand_text, 1)
        sidebar_layout.addWidget(brand_frame)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"background-color: {CachyColors.BORDER_SUBTLE}; max-height: 1px; margin: 4px 0px 8px 0px; border: none;")
        sidebar_layout.addWidget(div)

        # Navigation Buttons
        self.nav_buttons = []
        self.btn_nav_dashboard = self._create_nav_button("⚡  Übersicht", 0)
        self.btn_nav_packages = self._create_nav_button("📦  Pakete", 1)
        self.btn_nav_mirrors = self._create_nav_button("🌐  Spiegelserver", 2)
        self.btn_nav_execution = self._create_nav_button("▶  Update-Prozess", 3)
        self.btn_nav_maintenance = self._create_nav_button("🧹  Wartung && Snapshots", 4)
        self.btn_nav_settings = self._create_nav_button("⚙️  Einstellungen", 5)

        sidebar_layout.addWidget(self.btn_nav_dashboard)
        sidebar_layout.addWidget(self.btn_nav_packages)
        sidebar_layout.addWidget(self.btn_nav_mirrors)
        sidebar_layout.addWidget(self.btn_nav_execution)
        sidebar_layout.addWidget(self.btn_nav_maintenance)
        sidebar_layout.addWidget(self.btn_nav_settings)

        sidebar_layout.addStretch()

        # Sidebar Footer Card (GitHub Updater & System Info)
        footer_card = QFrame()
        footer_card.setObjectName("footerCard")
        footer_card.setStyleSheet(f"""
            QFrame#footerCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #162232, stop:1 #0d141e);
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 10px;
            }}
        """)
        footer_layout = QVBoxLayout(footer_card)
        footer_layout.setContentsMargins(12, 10, 12, 10)
        footer_layout.setSpacing(4)

        lbl_app_status = QLabel(f"● Update Center v{__version__}")
        lbl_app_status.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {CachyColors.ACCENT_EMERALD};")

        k_ver = PackageChecker.get_running_kernel()
        lbl_kernel_info = QLabel(f"🐧 {k_ver.split('-')[0]}  │  x86-64-v3/v4")
        lbl_kernel_info.setStyleSheet(f"font-size: 10px; color: {CachyColors.TEXT_MUTED};")

        self.btn_sidebar_app_update = QPushButton("Auf App-Updates prüfen...")
        self.btn_sidebar_app_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sidebar_app_update.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.05);
                color: {CachyColors.TEXT_PRIMARY};
                font-size: 11px;
                font-weight: 600;
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 6px 8px;
                margin-top: 4px;
            }}
            QPushButton:hover {{
                background: rgba(0, 212, 148, 0.15);
                color: {CachyColors.ACCENT_EMERALD_LIGHT};
                border-color: {CachyColors.ACCENT_EMERALD};
            }}
        """)
        self.btn_sidebar_app_update.clicked.connect(self.show_app_update_dialog)

        footer_layout.addWidget(lbl_app_status)
        footer_layout.addWidget(lbl_kernel_info)
        footer_layout.addWidget(self.btn_sidebar_app_update)
        sidebar_layout.addWidget(footer_card)

        root_layout.addWidget(sidebar)

        # ----------------------------------------------------------------------
        # Right Main Column (Top Header Bar + Content Stack)
        # ----------------------------------------------------------------------
        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Top Header Bar
        self.top_header_bar = QFrame()
        self.top_header_bar.setObjectName("topHeaderBar")
        self.top_header_bar.setFixedHeight(54)
        top_layout = QHBoxLayout(self.top_header_bar)
        top_layout.setContentsMargins(22, 8, 22, 8)
        top_layout.setSpacing(14)

        header_title_box = QVBoxLayout()
        header_title_box.setSpacing(1)
        self.lbl_view_title = QLabel("⚡ System-Übersicht")
        self.lbl_view_title.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {CachyColors.TEXT_PRIMARY};")
        self.lbl_view_subtitle = QLabel("Systemzustand, anstehende Updates und Schnellstart mit vorheriger Spiegel-Bewertung")
        self.lbl_view_subtitle.setStyleSheet(f"font-size: 11px; color: {CachyColors.TEXT_MUTED};")
        header_title_box.addWidget(self.lbl_view_title)
        header_title_box.addWidget(self.lbl_view_subtitle)
        top_layout.addLayout(header_title_box, 1)

        # Right Action Buttons in Top Bar
        self.btn_top_app_update = QPushButton(f"🔄 App-Update (v{__version__})")
        self.btn_top_app_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_top_app_update.clicked.connect(self.show_app_update_dialog)
        top_layout.addWidget(self.btn_top_app_update)

        self.btn_top_refresh = QPushButton("  Aktualisieren")
        self.btn_top_refresh.setIcon(QIcon.fromTheme("view-refresh"))
        self.btn_top_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_top_refresh.clicked.connect(self.start_initial_check)
        top_layout.addWidget(self.btn_top_refresh)

        right_layout.addWidget(self.top_header_bar)

        # Main Content Stack
        self.stack = QStackedWidget()

        # 0: Dashboard
        self.view_dashboard = DashboardView()
        self.view_dashboard.request_check_updates.connect(self.start_initial_check)
        self.view_dashboard.request_start_update.connect(lambda: self.launch_update_pipeline())
        self.view_dashboard.request_open_mirrors.connect(lambda: self.switch_tab(2))
        self.view_dashboard.request_open_packages.connect(lambda: self.switch_tab(1))
        self.stack.addWidget(self.view_dashboard)

        # 1: Packages
        self.view_packages = PackagesView()
        self.view_packages.request_refresh.connect(self.start_initial_check)
        self.view_packages.request_install_selected.connect(self.launch_update_pipeline)
        self.stack.addWidget(self.view_packages)

        # 2: Mirrors
        self.view_mirrors = MirrorsView()
        self.stack.addWidget(self.view_mirrors)

        # 3: Execution View
        self.view_execution = ExecutionView()
        self.view_execution.request_back_to_dashboard.connect(lambda: self.switch_tab(0))
        self.stack.addWidget(self.view_execution)

        # 4: Maintenance
        self.view_maintenance = MaintenanceView()
        self.stack.addWidget(self.view_maintenance)

        # 5: Settings
        self.view_settings = SettingsView()
        self.view_settings.request_open_updater.connect(self.show_app_update_dialog)
        self.stack.addWidget(self.view_settings)

        right_layout.addWidget(self.stack, 1)
        root_layout.addWidget(right_column, 1)

        # Set initial active tab
        self.switch_tab(0)

    def _create_nav_button(self, text: str, index: int) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("class", "nav-btn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self.switch_tab(index))
        self.nav_buttons.append(btn)
        return btn

    def switch_tab(self, index: int):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setProperty("active", "true" if i == index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        title, subtitle = self.TAB_TITLES.get(index, ("CachyOS Update Center", ""))
        self.lbl_view_title.setText(title)
        self.lbl_view_subtitle.setText(subtitle)

    def apply_styles(self):
        self.setStyleSheet(CACHY_STYLESHEET)

    def start_initial_check(self):
        """Dispatches background thread to discover available updates."""
        inc_aur = self.view_settings.config.get("include_aur", True)
        self.check_worker = PackageCheckWorker(include_aur=inc_aur)
        self.check_worker.packages_loaded.connect(self._on_packages_loaded)
        self.check_worker.news_loaded.connect(self._on_news_loaded)
        self.check_worker.start()

    def _on_packages_loaded(self, packages: List[PackageUpdate]):
        self.packages = packages
        cachy_count = sum(1 for p in packages if p.is_cachyos)
        aur_count = sum(1 for p in packages if p.is_aur)
        excluded_count = sum(1 for p in packages if p.has_online_issue and getattr(p, "issue_severity", "") == "CRITICAL")
        sec_fix_count = sum(1 for p in packages if getattr(p, "has_security_fix", False))

        self.view_dashboard.update_package_stats(len(packages), cachy_count, aur_count, excluded_count, sec_fix_count)
        self.view_packages.set_packages(packages)


        # Update mirrors status on dashboard
        mirror_info = MirrorRater.get_current_active_mirrors()
        self.view_dashboard.update_mirror_stats(mirror_info)

        # Update package button label with count badge
        if packages:
            self.btn_nav_packages.setText(f"📦  Pakete ({len(packages)})")
        else:
            self.btn_nav_packages.setText("📦  Pakete")

    def _on_news_loaded(self, news_items):
        for item in news_items:
            if item.is_critical:
                self.view_dashboard.show_critical_news(
                    f"⚠️ Manuelle Intervention erforderlich: {item.title}\n{item.summary}"
                )
                break

    def launch_update_pipeline(self, selected_packages: Optional[List[str]] = None):
        """
        Triggers the 4-step update sequence.
        Always respects the user's mirror rating preference!
        """
        # Ensure root authentication upfront with modal dialog parented to MainWindow
        from .core.privilege import is_root, is_sudo_authenticated
        if not is_root() and not is_sudo_authenticated():
            from .askpass import AskpassDialog
            dlg = AskpassDialog(parent=self, verify_direct=True)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                # User cancelled authentication
                return

        cfg = self.view_settings.config
        rate_always = cfg.get("rate_mirrors_always", True)
        entry_c = cfg.get("entry_country", "DE")
        if entry_c == "AUTO":
            entry_c = MirrorRater.detect_country_code()

        create_snap = cfg.get("create_snapshot", True)
        inc_aur = cfg.get("include_aur", True)
        auto_exclude = cfg.get("auto_exclude_issues", True)

        # Switch to Execution View
        self.switch_tab(3)

        self.view_execution.start_pipeline(
            rate_mirrors_first=rate_always,
            create_snapshot=create_snap,
            include_aur=inc_aur,
            entry_country=entry_c,
            selected_packages=selected_packages,
            auto_exclude_issues=auto_exclude,
        )

    def start_background_app_update_check(self):
        """Silently queries GitHub releases in the background without popups."""
        self.bg_github_worker = UpdateCheckerWorker(parent=self)
        self.bg_github_worker.finished.connect(self._on_bg_app_update_finished)
        self.bg_github_worker.start()

    def _on_bg_app_update_finished(self, info: UpdateInfo):
        """Called when multi-component/GitHub update check completes; alerts user if new release is found."""
        self.github_update_info = info
        if info.gui_has_update:
            badge_text = f"● Update verfügbar! (v{info.gui_remote})"
            tip = (
                f"Eine neuere Version von CachyOS Update Center ist verfügbar!\n"
                f"• Installiert: v{info.gui_local}\n"
                f"• Auf GitHub: v{info.gui_remote}\n"
                f"Klicken, um Changelog einzusehen und direkt zu aktualisieren."
            )

            self.btn_sidebar_app_update.setText(badge_text)
            self.btn_sidebar_app_update.setProperty("class", "btn-update-pending")
            self.btn_sidebar_app_update.setToolTip(tip)
            self.btn_sidebar_app_update.style().unpolish(self.btn_sidebar_app_update)
            self.btn_sidebar_app_update.style().polish(self.btn_sidebar_app_update)

            self.btn_top_app_update.setText(badge_text)
            self.btn_top_app_update.setProperty("class", "btn-update-pending")
            self.btn_top_app_update.setToolTip(tip)
            self.btn_top_app_update.style().unpolish(self.btn_top_app_update)
            self.btn_top_app_update.style().polish(self.btn_top_app_update)

    def show_app_update_dialog(self):
        """Displays modal UpdateDialog matching Cachy Security Suite design."""
        dlg = UpdateDialog(self)
        dlg.exec()


