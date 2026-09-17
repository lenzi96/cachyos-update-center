"""
Dashboard View: Central overview of updates, mirror status, and quick update launcher.
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core.mirror_rater import MirrorRater
from ..core.package_checker import PackageChecker
from ..core.snapper_helper import SnapperHelper
from ..styles import CachyColors


class DashboardView(QWidget):
    """Main dashboard displaying system health and update overview."""

    request_check_updates = pyqtSignal()
    request_start_update = pyqtSignal()  # triggers full update pipeline
    request_open_mirrors = pyqtSignal()  # navigates to mirrors tab
    request_open_packages = pyqtSignal()  # navigates to packages tab

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(18)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # ----------------------------------------------------------------------
        # 1. System Status Header Banner
        # ----------------------------------------------------------------------
        self.header_card = QFrame()
        self.header_card.setObjectName("headerCard")
        header_card_layout = QHBoxLayout(self.header_card)
        header_card_layout.setContentsMargins(24, 20, 24, 20)
        header_card_layout.setSpacing(20)

        # Status Icon
        self.status_icon = QLabel("⚡")
        self.status_icon.setFixedSize(54, 54)
        self.status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_icon.setStyleSheet(f"""
            background-color: rgba(0, 212, 148, 0.15);
            border: 2px solid {CachyColors.ACCENT_EMERALD};
            border-radius: 27px;
            font-size: 26px;
        """)

        # Texts
        header_text = QVBoxLayout()
        header_text.setSpacing(4)
        self.status_title = QLabel("Update-Status wird ermittelt...")
        self.status_title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {CachyColors.TEXT_PRIMARY};")
        self.status_desc = QLabel("Prüfe CachyOS Repositorien, Arch-Spiegelserver und AUR...")
        self.status_desc.setStyleSheet(f"font-size: 13px; color: {CachyColors.TEXT_SECONDARY};")
        header_text.addWidget(self.status_title)
        header_text.addWidget(self.status_desc)

        header_card_layout.addWidget(self.status_icon)
        header_card_layout.addLayout(header_text, 1)

        # Main Action Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        self.btn_check = QPushButton("  Aktualisierungen suchen")
        self.btn_check.setIcon(QIcon.fromTheme("view-refresh"))
        self.btn_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check.clicked.connect(self.request_check_updates.emit)

        self.btn_update_now = QPushButton("  ⚡ Jetzt aktualisieren")
        self.btn_update_now.setProperty("class", "btn-primary")
        self.btn_update_now.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update_now.setMinimumWidth(170)
        self.btn_update_now.clicked.connect(self.request_start_update.emit)


        btn_box.addWidget(self.btn_check)
        btn_box.addWidget(self.btn_update_now)
        header_card_layout.addLayout(btn_box)

        self.header_card.setStyleSheet(f"""
            QFrame#headerCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #172635, stop:1 #0f1822);
                border: 1px solid rgba(0, 212, 148, 0.3);
                border-radius: 12px;
            }}
        """)
        layout.addWidget(self.header_card)

        # ----------------------------------------------------------------------
        # 2. Stat Cards Grid (3 Cards)
        # ----------------------------------------------------------------------
        grid_layout = QHBoxLayout()
        grid_layout.setSpacing(16)

        # Card 1: Packages
        self.card_pkgs = self._create_card(
            icon="📦",
            title="Ausstehende Pakete",
            value="0 Pakete",
            subtitle="Offizielle Repos & AUR",
            badge_text="Prüfung läuft",
            on_click=self.request_open_packages.emit,
        )
        grid_layout.addWidget(self.card_pkgs)

        # Card 2: Mirror Status (Highlight: Immer mit vorheriger Bewertung)
        self.card_mirrors = self._create_card(
            icon="🌐",
            title="Spiegelserver",
            value="Optimiert",
            subtitle="Letzte Bewertung: Kürzlich",
            badge_text="Vor-Update Aktiv",
            badge_color=CachyColors.ACCENT_EMERALD,
            on_click=self.request_open_mirrors.emit,
        )
        grid_layout.addWidget(self.card_mirrors)

        # Card 3: Kernel & Safety
        kernel_rel = PackageChecker.get_running_kernel()
        has_snapper = SnapperHelper.is_available() and SnapperHelper.has_root_config()
        snap_badge = "BTRFS Snapper Bereit" if has_snapper else "Kein Snapshot-Tool"
        snap_color = CachyColors.ACCENT_EMERALD if has_snapper else CachyColors.ACCENT_AMBER

        self.card_system = self._create_card(
            icon="🛡️",
            title="Kernel & Ausfallsicherung",
            value=kernel_rel.split("-")[0] if "-" in kernel_rel else kernel_rel,
            subtitle=f"Kernel: {kernel_rel}",
            badge_text=snap_badge,
            badge_color=snap_color,
        )
        grid_layout.addWidget(self.card_system)

        layout.addLayout(grid_layout)

        # ----------------------------------------------------------------------
        # 3. Mirror Banner Guarantee ("Immer vorherige Spiegelserver-Bewertung")
        # ----------------------------------------------------------------------
        mirror_banner = QFrame()
        mirror_banner.setObjectName("mirrorBanner")
        mb_layout = QHBoxLayout(mirror_banner)
        mb_layout.setContentsMargins(18, 14, 18, 14)
        mb_layout.setSpacing(14)

        mb_icon = QLabel("⚡")
        mb_icon.setStyleSheet("font-size: 20px;")
        mb_layout.addWidget(mb_icon)

        mb_text = QVBoxLayout()
        mb_text.setSpacing(2)
        mb_title = QLabel("CachyOS Geschwindigkeits-Garantie: Immer mit vorheriger Spiegelserver-Bewertung")
        mb_title.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {CachyColors.ACCENT_EMERALD_LIGHT};")
        self.mb_desc = QLabel(
            "Vor jeder Systemaktualisierung wird automatisch eine Live-Latenz- und Durchsatz-Bewertung der "
            "CachyOS- und Arch-Server durchgeführt. Dadurch lädt dein System stets mit Höchstgeschwindigkeit."
        )
        self.mb_desc.setStyleSheet(f"font-size: 12px; color: {CachyColors.TEXT_SECONDARY};")
        self.mb_desc.setWordWrap(True)
        mb_text.addWidget(mb_title)
        mb_text.addWidget(self.mb_desc)
        mb_layout.addLayout(mb_text, 1)

        btn_test_mirrors = QPushButton("Spiegelserver testen")
        btn_test_mirrors.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_test_mirrors.clicked.connect(self.request_open_mirrors.emit)
        mb_layout.addWidget(btn_test_mirrors)

        mirror_banner.setStyleSheet(f"""
            QFrame#mirrorBanner {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 212, 148, 0.12), stop:1 rgba(0, 212, 148, 0.03));
                border: 1px solid rgba(0, 212, 148, 0.35);
                border-radius: 10px;
            }}
        """)
        layout.addWidget(mirror_banner)

        # ----------------------------------------------------------------------
        # 4. News / Manual Intervention Container
        # ----------------------------------------------------------------------
        self.news_container = QFrame()
        self.news_container.setObjectName("newsContainer")
        self.news_container.setVisible(False)
        nc_layout = QHBoxLayout(self.news_container)
        nc_layout.setContentsMargins(16, 12, 16, 12)
        nc_layout.setSpacing(12)

        self.news_icon = QLabel("⚠️")
        self.news_icon.setStyleSheet("font-size: 20px;")
        nc_layout.addWidget(self.news_icon)

        self.news_label = QLabel("")
        self.news_label.setStyleSheet(f"font-size: 12px; color: {CachyColors.TEXT_PRIMARY}; font-weight: 500;")
        self.news_label.setWordWrap(True)
        nc_layout.addWidget(self.news_label, 1)

        self.news_container.setStyleSheet(f"""
            QFrame#newsContainer {{
                background-color: rgba(255, 179, 0, 0.12);
                border: 1px solid {CachyColors.ACCENT_AMBER};
                border-radius: 8px;
            }}
        """)
        layout.addWidget(self.news_container)

        layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _create_card(
        self,
        icon: str,
        title: str,
        value: str,
        subtitle: str,
        badge_text: str = "",
        badge_color: str = CachyColors.TEXT_SECONDARY,
        on_click=None,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("statCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(8)

        top_row = QHBoxLayout()
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 20px;")
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-weight: 600; font-size: 12px; color: {CachyColors.TEXT_SECONDARY};")
        top_row.addWidget(icon_lbl)
        top_row.addWidget(title_lbl)
        top_row.addStretch()

        if badge_text:
            badge = QLabel(badge_text)
            badge.setObjectName("cardBadge")
            badge.setStyleSheet(f"""
                QLabel#cardBadge {{
                    background-color: rgba(255, 255, 255, 0.06);
                    color: {badge_color};
                    border: 1px solid {badge_color};
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-size: 10px;
                    font-weight: 700;
                }}
            """)
            top_row.addWidget(badge)

        val_lbl = QLabel(value)
        val_lbl.setObjectName("cardValue")
        val_lbl.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {CachyColors.TEXT_PRIMARY};")

        sub_lbl = QLabel(subtitle)
        sub_lbl.setObjectName("cardSubtitle")
        sub_lbl.setStyleSheet(f"font-size: 11px; color: {CachyColors.TEXT_MUTED};")

        card_layout.addLayout(top_row)
        card_layout.addWidget(val_lbl)
        card_layout.addWidget(sub_lbl)

        card.setStyleSheet(f"""
            QFrame#statCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #182434, stop:1 #131c28);
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 10px;
            }}
            QFrame#statCard:hover {{
                border-color: {CachyColors.BORDER_HOVER};
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1d2c40, stop:1 #172230);
            }}
        """)

        if on_click:
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.mousePressEvent = lambda e: on_click()

        return card

    def update_package_stats(self, count: int, cachy_count: int, aur_count: int, excluded_count: int = 0, sec_fix_count: int = 0):
        """Updates dashboard with current package numbers, security fixes, and auto-exclusion notice."""
        val_lbl = self.card_pkgs.findChild(QLabel, "cardValue")
        sub_lbl = self.card_pkgs.findChild(QLabel, "cardSubtitle")
        badge = self.card_pkgs.findChild(QLabel, "cardBadge")

        if count == 0:
            if val_lbl:
                val_lbl.setText("Alles aktuell")
            if sub_lbl:
                sub_lbl.setText("Keine ausstehenden Aktualisierungen")
            if badge:
                badge.setText("System Up-to-date")
                badge.setStyleSheet(f"color: {CachyColors.ACCENT_EMERALD}; border: 1px solid {CachyColors.ACCENT_EMERALD}; border-radius: 4px; padding: 2px 6px; font-size: 10px;")

            self.status_title.setText("System ist auf dem neuesten Stand")
            self.status_desc.setText("Alle CachyOS-, Arch- und AUR-Pakete sind aktuell.")
            self.status_icon.setText("✓")
            self.status_icon.setStyleSheet(f"""
                background-color: rgba(0, 212, 148, 0.15);
                border: 2px solid {CachyColors.ACCENT_EMERALD};
                border-radius: 27px;
                font-size: 26px;
                color: {CachyColors.ACCENT_EMERALD};
            """)
            self.btn_update_now.setEnabled(False)
        else:
            if val_lbl:
                val_lbl.setText(f"{count} Updates")
            if sub_lbl:
                extra_notes = []
                if sec_fix_count > 0:
                    extra_notes.append(f"🛡️ {sec_fix_count} Security-Fixes")
                if excluded_count > 0:
                    extra_notes.append(f"⛔ {excluded_count} ausgeschlossen")
                notes_str = f" | {' • '.join(extra_notes)}" if extra_notes else ""
                sub_lbl.setText(f"CachyOS: {cachy_count} | AUR: {aur_count}{notes_str}")
            if badge:
                if excluded_count > 0:
                    badge_text = f"⛔ {excluded_count} Intervention nötig"
                    badge_color = CachyColors.ACCENT_RED
                elif sec_fix_count > 0:
                    badge_text = f"🛡️ {sec_fix_count} Sicherheits-Fixes"
                    badge_color = CachyColors.ACCENT_EMERALD
                else:
                    badge_text = f"{count} Verfügbar"
                    badge_color = CachyColors.ACCENT_CYAN
                badge.setText(badge_text)
                badge.setStyleSheet(f"color: {badge_color}; border: 1px solid {badge_color}; border-radius: 4px; padding: 2px 6px; font-size: 10px;")

            self.status_title.setText(f"{count} Aktualisierungen verfügbar")
            desc_text = f"{cachy_count} optimierte CachyOS-Pakete und {aur_count} AUR-Pakete bereit zur Installation."
            if sec_fix_count > 0:
                desc_text += f"\n🛡️ Sicherheits-Audit: {sec_fix_count} Paket(e) beheben bekannte CVE-Sicherheitslücken."
            if excluded_count > 0:
                desc_text += f"\n⛔ Schutzschild aktiv: {excluded_count} Paket(e) wegen manueller Eingriffserfordernis vorab abgewählt."
            self.status_desc.setText(desc_text)
            self.status_icon.setText("⚡")
            self.status_icon.setStyleSheet(f"""
                background-color: rgba(0, 212, 148, 0.2);
                border: 2px solid {CachyColors.ACCENT_EMERALD_LIGHT};
                border-radius: 27px;
                font-size: 26px;
            """)
            self.btn_update_now.setEnabled(True)


    def update_mirror_stats(self, mirror_info: dict):
        """Updates mirror status card."""
        sub_lbl = self.card_mirrors.findChild(QLabel, "cardSubtitle")
        if sub_lbl and "last_modified" in mirror_info:
            sub_lbl.setText(f"Zuletzt bewertet: {mirror_info['last_modified']}")

    def show_critical_news(self, text: str):
        """Displays critical announcement banner."""
        self.news_label.setText(text)
        self.news_container.setVisible(True)
