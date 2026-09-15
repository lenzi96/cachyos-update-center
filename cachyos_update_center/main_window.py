"""
Main Window for CachyOS Update Center.
Coordinates navigation, background package inspection, and update flows.
"""
import os
import shutil
import subprocess
from typing import List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .core.mirror_rater import MirrorRater
from .core.news_checker import NewsChecker
from .core.online_issue_checker import OnlineIssueChecker
from .core.package_checker import PackageChecker, PackageUpdate
from .styles import CACHY_STYLESHEET, CachyColors
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

        # Online Issue Checking
        if all_pkgs:
            self.status_text.emit("Prüfe Pakete online auf gemeldete Probleme & manuelle Eingriffe...")
            pkg_names = [p.name for p in all_pkgs]
            issues = OnlineIssueChecker.check_packages(pkg_names)
            for p in all_pkgs:
                if p.name.lower() in issues:
                    rep = issues[p.name.lower()]
                    p.has_online_issue = True
                    p.issue_reason = rep.reason
                    p.issue_url = rep.url
                    p.is_auto_excluded = True
                    p.is_selected = False  # Auto-exclude by default!

        self.packages_loaded.emit(all_pkgs)

        # Check news
        self.status_text.emit("Lade Systemankündigungen...")
        news = NewsChecker.fetch_latest_news()
        self.news_loaded.emit(news)



class MainWindow(QMainWindow):
    """Primary application window for CachyOS Update Center."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CachyOS Update Center")
        self.resize(1060, 700)
        self.setMinimumSize(920, 580)

        self.packages: List[PackageUpdate] = []
        self.check_worker: Optional[PackageCheckWorker] = None

        self.init_ui()
        self.apply_styles()
        self.start_initial_check()

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
        sidebar.setFixedWidth(230)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 20, 14, 16)
        sidebar_layout.setSpacing(8)

        # App Brand Header
        brand_frame = QFrame()
        brand_layout = QHBoxLayout(brand_frame)
        brand_layout.setContentsMargins(4, 0, 4, 16)
        brand_layout.setSpacing(12)

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "app_icon_64.png")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "app_icon.svg")

        logo_lbl = QLabel()
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(42, 42, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_lbl.setPixmap(pixmap)
        else:
            logo_lbl.setText("⚡")
            logo_lbl.setStyleSheet("font-size: 28px;")

        brand_text = QVBoxLayout()
        brand_text.setSpacing(1)
        title_lbl = QLabel("CachyOS")
        title_lbl.setStyleSheet(f"font-weight: 800; font-size: 16px; color: {CachyColors.ACCENT_EMERALD_LIGHT};")
        sub_title = QLabel("Update Center")
        sub_title.setStyleSheet(f"font-size: 12px; color: {CachyColors.TEXT_SECONDARY}; font-weight: 600;")
        brand_text.addWidget(title_lbl)
        brand_text.addWidget(sub_title)

        brand_layout.addWidget(logo_lbl)
        brand_layout.addLayout(brand_text, 1)
        sidebar_layout.addWidget(brand_frame)

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

        # System Info Pill at bottom of sidebar
        sys_pill = QFrame()
        sys_pill.setStyleSheet(f"""
            background-color: {CachyColors.BG_CARD};
            border: 1px solid {CachyColors.BORDER_SUBTLE};
            border-radius: 8px;
            padding: 8px;
        """)
        sp_layout = QVBoxLayout(sys_pill)
        sp_layout.setContentsMargins(6, 6, 6, 6)
        sp_layout.setSpacing(2)

        k_ver = PackageChecker.get_running_kernel()
        sp_k = QLabel(f"🐧 {k_ver.split('-')[0]}")
        sp_k.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {CachyColors.TEXT_PRIMARY};")
        sp_desc = QLabel("CachyOS x86-64-v3/v4")
        sp_desc.setStyleSheet(f"font-size: 10px; color: {CachyColors.ACCENT_EMERALD};")

        sp_layout.addWidget(sp_k)
        sp_layout.addWidget(sp_desc)
        sidebar_layout.addWidget(sys_pill)

        root_layout.addWidget(sidebar)

        # ----------------------------------------------------------------------
        # Main Content Stack
        # ----------------------------------------------------------------------
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
        self.stack.addWidget(self.view_settings)

        root_layout.addWidget(self.stack, 1)

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
        excluded_count = sum(1 for p in packages if p.has_online_issue)

        self.view_dashboard.update_package_stats(len(packages), cachy_count, aur_count, excluded_count)
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

