"""
Settings View: Preferences for mirror rating, update behavior, and system maintenance.
"""
import json
import os
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..styles import CachyColors
from ..updater import get_github_repo


class SettingsView(QWidget):
    """Configuration management view."""

    settings_changed = pyqtSignal(dict)
    request_open_updater = pyqtSignal()
    CONFIG_FILE = Path.home() / ".config" / "cachyos-update-center" / "config.json"

    DEFAULT_CONFIG = {
        "rate_mirrors_always": True,
        "entry_country": "DE",
        "max_mirrors": 8,
        "include_aur": True,
        "include_flatpak": False,
        "create_snapshot": True,
        "clean_cache_after": True,
        "notify_reboot": True,
        "auto_exclude_issues": True,
    }


    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = dict(self.DEFAULT_CONFIG)
        self.load_config()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        # ----------------------------------------------------------------------
        # Group 1: Spiegelserver-Bewertung (Priority Feature)
        # ----------------------------------------------------------------------
        group_mirrors = self._create_group("🌐 Spiegelserver && Geschwindigkeits-Optimierung")

        self.chk_rate_always = QCheckBox("Spiegelserver immer vor jeder Aktualisierung bewerten (Empfohlen)")
        self.chk_rate_always.setChecked(self.config.get("rate_mirrors_always", True))
        self.chk_rate_always.setStyleSheet(f"font-weight: 700; color: {CachyColors.ACCENT_EMERALD_LIGHT};")
        group_mirrors.layout().addWidget(self.chk_rate_always)

        lbl_desc = QLabel(
            "Führt vor jedem Update-Lauf automatisch cachyos-rate-mirrors aus. Gewährleistet, "
            "dass Downloads mit maximaler Geschwindigkeit von den am besten angebundenen Spiegeln geladen werden."
        )
        lbl_desc.setStyleSheet(f"font-size: 11px; color: {CachyColors.TEXT_MUTED}; margin-left: 26px;")
        lbl_desc.setWordWrap(True)
        group_mirrors.layout().addWidget(lbl_desc)

        row_country = QHBoxLayout()
        lbl_c = QLabel("Standard-Startland für Geo-Ping:")
        lbl_c.setStyleSheet(f"font-size: 12px; color: {CachyColors.TEXT_SECONDARY};")
        self.combo_country = QComboBox()
        self.combo_country.addItem("Deutschland (DE)", "DE")
        self.combo_country.addItem("Österreich (AT)", "AT")
        self.combo_country.addItem("Schweiz (CH)", "CH")
        self.combo_country.addItem("Automatisch (GeoIP)", "AUTO")
        self.combo_country.addItem("Weltweit (Global)", "US")

        # Set saved country
        saved_c = self.config.get("entry_country", "DE")
        idx = self.combo_country.findData(saved_c)
        if idx >= 0:
            self.combo_country.setCurrentIndex(idx)

        row_country.addWidget(lbl_c)
        row_country.addWidget(self.combo_country)
        row_country.addStretch()
        group_mirrors.layout().addLayout(row_country)

        row_count = QHBoxLayout()
        lbl_cnt = QLabel("Anzahl aktiver Top-Spiegelserver:")
        lbl_cnt.setStyleSheet(f"font-size: 12px; color: {CachyColors.TEXT_SECONDARY};")
        self.spin_count = QSpinBox()
        self.spin_count.setRange(3, 25)
        self.spin_count.setValue(self.config.get("max_mirrors", 8))
        row_count.addWidget(lbl_cnt)
        row_count.addWidget(self.spin_count)
        row_count.addStretch()
        group_mirrors.layout().addLayout(row_count)

        layout.addWidget(group_mirrors)

        # ----------------------------------------------------------------------
        # Group 2: Paketquellen & Snapshot-Sicherheit
        # ----------------------------------------------------------------------
        group_sources = self._create_group("📦 Paketquellen && Systemsicherheit")

        self.chk_include_aur = QCheckBox("AUR-Pakete (Arch User Repository via yay) einbeziehen")
        self.chk_include_aur.setChecked(self.config.get("include_aur", True))
        group_sources.layout().addWidget(self.chk_include_aur)

        self.chk_create_snapshot = QCheckBox("Automatischer BTRFS Wiederherstellungspunkt (Snapper) vor Update anlegen")
        self.chk_create_snapshot.setChecked(self.config.get("create_snapshot", True))
        group_sources.layout().addWidget(self.chk_create_snapshot)

        self.chk_auto_exclude = QCheckBox("Vor Update online auf Probleme prüfen && automatisch ausschließen (Empfohlen)")
        self.chk_auto_exclude.setChecked(self.config.get("auto_exclude_issues", True))
        self.chk_auto_exclude.setStyleSheet(f"font-weight: 700; color: {CachyColors.ACCENT_EMERALD_LIGHT};")
        group_sources.layout().addWidget(self.chk_auto_exclude)

        lbl_auto_desc = QLabel(
            "Fragt Arch- und CachyOS-Newsfeeds online ab. Pakete mit manueller Eingriffserfordernis "
            "oder gemeldeten Regressionen werden automatisch abgewählt und mit '--ignore' geschützt."
        )
        lbl_auto_desc.setStyleSheet(f"font-size: 11px; color: {CachyColors.TEXT_MUTED}; margin-left: 26px;")
        lbl_auto_desc.setWordWrap(True)
        group_sources.layout().addWidget(lbl_auto_desc)

        layout.addWidget(group_sources)


        # ----------------------------------------------------------------------
        # Group 3: Nachbereitung & Systemgesundheit
        # ----------------------------------------------------------------------
        group_post = self._create_group("🧹 Nachbereitung && Systempflege")

        self.chk_clean_cache = QCheckBox("Paket-Cache nach erfolgreicher Aktualisierung aufräumen (paccache)")
        self.chk_clean_cache.setChecked(self.config.get("clean_cache_after", True))
        group_post.layout().addWidget(self.chk_clean_cache)

        self.chk_notify_reboot = QCheckBox("Benachrichtigung anzeigen, wenn ein Kernel-Neustart ansteht")
        self.chk_notify_reboot.setChecked(self.config.get("notify_reboot", True))
        group_post.layout().addWidget(self.chk_notify_reboot)

        layout.addWidget(group_post)

        # ----------------------------------------------------------------------
        # Group 4: Anwendungs-Aktualisierung (GitHub)
        # ----------------------------------------------------------------------
        group_app = self._create_group("🔄 Anwendungs-Aktualisierung (GitHub)")

        app_info_row = QHBoxLayout()
        lbl_app_ver = QLabel(f"Installierte Version: v{__version__}  │  Repository: {get_github_repo()}")
        lbl_app_ver.setStyleSheet(f"font-size: 12px; color: {CachyColors.TEXT_SECONDARY};")
        app_info_row.addWidget(lbl_app_ver)
        app_info_row.addStretch()

        self.btn_check_github = QPushButton("  🚀 GitHub Update Center öffnen")
        self.btn_check_github.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check_github.clicked.connect(self.request_open_updater.emit)
        app_info_row.addWidget(self.btn_check_github)
        group_app.layout().addLayout(app_info_row)

        lbl_app_desc = QLabel(
            "Prüft direkt auf GitHub Releases oder Git-Commits, zeigt Release-Notes & Changelogs an "
            "und aktualisiert das CachyOS Update Center mit einem Klick."
        )
        lbl_app_desc.setStyleSheet(f"font-size: 11px; color: {CachyColors.TEXT_MUTED};")
        lbl_app_desc.setWordWrap(True)
        group_app.layout().addWidget(lbl_app_desc)

        layout.addWidget(group_app)

        # ----------------------------------------------------------------------
        # Save Button Bar
        # ----------------------------------------------------------------------
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()

        self.btn_reset = QPushButton("Standardwerte wiederherstellen")
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.clicked.connect(self.reset_defaults)
        btn_bar.addWidget(self.btn_reset)

        self.btn_save = QPushButton("  Einstellungen speichern")
        self.btn_save.setProperty("class", "btn-primary")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.clicked.connect(self.save_config)
        btn_bar.addWidget(self.btn_save)

        layout.addLayout(btn_bar)
        layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _create_group(self, title: str) -> QFrame:
        group = QFrame()
        group.setObjectName("settingsGroup")
        gl = QVBoxLayout(group)
        gl.setContentsMargins(18, 16, 18, 16)
        gl.setSpacing(12)

        lbl = QLabel(title)
        lbl.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {CachyColors.TEXT_PRIMARY};")
        gl.addWidget(lbl)

        group.setStyleSheet(f"""
            QFrame#settingsGroup {{
                background-color: {CachyColors.BG_CARD};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 10px;
            }}
        """)
        return group

    def load_config(self):
        """Loads configuration from JSON file."""
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.config.update(data)
            except Exception:
                pass

    def save_config(self):
        """Saves current widget values to disk."""
        self.config["rate_mirrors_always"] = self.chk_rate_always.isChecked()
        self.config["entry_country"] = self.combo_country.currentData()
        self.config["max_mirrors"] = self.spin_count.value()
        self.config["include_aur"] = self.chk_include_aur.isChecked()
        self.config["create_snapshot"] = self.chk_create_snapshot.isChecked()
        self.config["clean_cache_after"] = self.chk_clean_cache.isChecked()
        self.config["notify_reboot"] = self.chk_notify_reboot.isChecked()
        self.config["auto_exclude_issues"] = self.chk_auto_exclude.isChecked()

        try:
            self.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            QMessageBox.information(self, "Gespeichert", "Einstellungen wurden erfolgreich gespeichert.")
            self.settings_changed.emit(self.config)
        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Einstellungen konnten nicht gespeichert werden: {e}")

    def reset_defaults(self):
        self.config = dict(self.DEFAULT_CONFIG)
        self.chk_rate_always.setChecked(True)
        self.chk_include_aur.setChecked(True)
        self.chk_create_snapshot.setChecked(True)
        self.chk_clean_cache.setChecked(True)
        self.chk_notify_reboot.setChecked(True)
        self.chk_auto_exclude.setChecked(True)
        self.spin_count.setValue(8)
        idx = self.combo_country.findData("DE")
        if idx >= 0:
            self.combo_country.setCurrentIndex(idx)
        self.save_config()

