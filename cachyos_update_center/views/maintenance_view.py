"""
Maintenance View: System care tools including pacman cache cleaning, orphan removal, and BTRFS snapshots.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.snapper_helper import SnapperHelper
from ..core.system_care import SystemCare
from ..styles import CachyColors


class MaintenanceView(QWidget):
    """System maintenance, cleanup and snapshot control center."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.refresh_data()

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
        # 1. Cache Cleanup Card
        # ----------------------------------------------------------------------
        card_cache = QFrame()
        card_cache.setObjectName("maintCard")
        cc_layout = QHBoxLayout(card_cache)
        cc_layout.setContentsMargins(18, 16, 18, 16)
        cc_layout.setSpacing(16)

        c_icon = QLabel("💾")
        c_icon.setStyleSheet("font-size: 26px;")
        cc_layout.addWidget(c_icon)

        c_text = QVBoxLayout()
        c_text.setSpacing(2)
        c_title = QLabel("Pacman-Paketcache bereinigen")
        c_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {CachyColors.TEXT_PRIMARY};")
        self.c_desc = QLabel("Belegt aktuell: Wird ermittelt...")
        self.c_desc.setStyleSheet(f"font-size: 12px; color: {CachyColors.TEXT_SECONDARY};")
        c_text.addWidget(c_title)
        c_text.addWidget(self.c_desc)
        cc_layout.addLayout(c_text, 1)

        self.btn_clean_cache = QPushButton("Cache bereinigen")
        self.btn_clean_cache.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clean_cache.clicked.connect(self.clean_cache)
        cc_layout.addWidget(self.btn_clean_cache)

        card_cache.setStyleSheet(f"""
            QFrame#maintCard {{
                background-color: {CachyColors.BG_CARD};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 10px;
            }}
        """)
        layout.addWidget(card_cache)

        # ----------------------------------------------------------------------
        # 2. Orphaned Packages Card
        # ----------------------------------------------------------------------
        card_orphans = QFrame()
        card_orphans.setObjectName("maintCard")
        co_layout = QVBoxLayout(card_orphans)
        co_layout.setContentsMargins(18, 16, 18, 16)
        co_layout.setSpacing(12)

        co_header = QHBoxLayout()
        o_icon = QLabel("🧹")
        o_icon.setStyleSheet("font-size: 24px;")
        co_header.addWidget(o_icon)

        o_text = QVBoxLayout()
        o_text.setSpacing(2)
        o_title = QLabel("Verwaiste Pakete (Orphans)")
        o_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {CachyColors.TEXT_PRIMARY};")
        self.o_desc = QLabel("Pakete, die als Abhängigkeit installiert wurden, aber nicht mehr benötigt werden.")
        self.o_desc.setStyleSheet(f"font-size: 12px; color: {CachyColors.TEXT_SECONDARY};")
        o_text.addWidget(o_title)
        o_text.addWidget(self.o_desc)
        co_header.addLayout(o_text, 1)

        self.btn_remove_orphans = QPushButton("Verwaiste Pakete entfernen")
        self.btn_remove_orphans.setProperty("class", "btn-danger")
        self.btn_remove_orphans.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_remove_orphans.clicked.connect(self.remove_orphans)
        co_header.addWidget(self.btn_remove_orphans)
        co_layout.addLayout(co_header)

        self.orphan_list_lbl = QLabel("Keine verwaisten Pakete gefunden.")
        self.orphan_list_lbl.setStyleSheet(f"font-size: 12px; color: {CachyColors.ACCENT_EMERALD}; padding: 6px;")
        self.orphan_list_lbl.setWordWrap(True)
        co_layout.addWidget(self.orphan_list_lbl)

        card_orphans.setStyleSheet(f"""
            QFrame#maintCard {{
                background-color: {CachyColors.BG_CARD};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 10px;
            }}
        """)
        layout.addWidget(card_orphans)

        # ----------------------------------------------------------------------
        # 3. BTRFS Snapper Snapshots Card
        # ----------------------------------------------------------------------
        card_snapshots = QFrame()
        card_snapshots.setObjectName("maintCard")
        cs_layout = QVBoxLayout(card_snapshots)
        cs_layout.setContentsMargins(18, 16, 18, 16)
        cs_layout.setSpacing(12)

        cs_header = QHBoxLayout()
        s_icon = QLabel("📸")
        s_icon.setStyleSheet("font-size: 24px;")
        cs_header.addWidget(s_icon)

        s_text = QVBoxLayout()
        s_text.setSpacing(2)
        s_title = QLabel("BTRFS Wiederherstellungspunkte (Snapper)")
        s_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {CachyColors.TEXT_PRIMARY};")
        s_desc = QLabel("Automatische System-Snapshots vor Updates schützen das System vor Fehlkonfigurationen.")
        s_desc.setStyleSheet(f"font-size: 12px; color: {CachyColors.TEXT_SECONDARY};")
        s_text.addWidget(s_title)
        s_text.addWidget(s_desc)
        cs_header.addLayout(s_text, 1)

        self.btn_create_snap = QPushButton("Snapshot erstellen")
        self.btn_create_snap.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_create_snap.clicked.connect(self.create_snapshot)
        cs_header.addWidget(self.btn_create_snap)
        cs_layout.addLayout(cs_header)

        # Snapshots table
        self.snap_table = QTableWidget()
        self.snap_table.setColumnCount(4)
        self.snap_table.setHorizontalHeaderLabels(["ID", "Typ", "Zeitpunkt", "Beschreibung"])
        self.snap_table.verticalHeader().setVisible(False)
        self.snap_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.snap_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.snap_table.setFixedHeight(140)

        s_hdr = self.snap_table.horizontalHeader()
        s_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        s_hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        s_hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        s_hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        cs_layout.addWidget(self.snap_table)

        card_snapshots.setStyleSheet(f"""
            QFrame#maintCard {{
                background-color: {CachyColors.BG_CARD};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 10px;
            }}
        """)
        layout.addWidget(card_snapshots)

        # ----------------------------------------------------------------------
        # 4. Pacnew Config Files Card
        # ----------------------------------------------------------------------
        card_pacnew = QFrame()
        card_pacnew.setObjectName("maintCard")
        cp_layout = QVBoxLayout(card_pacnew)
        cp_layout.setContentsMargins(18, 16, 18, 16)
        cp_layout.setSpacing(10)

        cp_header = QHBoxLayout()
        p_icon = QLabel("⚙️")
        p_icon.setStyleSheet("font-size: 24px;")
        cp_header.addWidget(p_icon)

        p_text = QVBoxLayout()
        p_text.setSpacing(2)
        p_title = QLabel("Pacnew Konfigurationsprüfung")
        p_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {CachyColors.TEXT_PRIMARY};")
        p_desc = QLabel("Überprüft auf neue Konfigurationsdateien (*.pacnew) nach Paketupdates.")
        p_desc.setStyleSheet(f"font-size: 12px; color: {CachyColors.TEXT_SECONDARY};")
        p_text.addWidget(p_title)
        p_text.addWidget(p_desc)
        cp_header.addLayout(p_text, 1)
        cp_layout.addLayout(cp_header)

        self.pacnew_lbl = QLabel("Keine .pacnew Dateien vorhanden.")
        self.pacnew_lbl.setStyleSheet(f"font-size: 12px; color: {CachyColors.TEXT_MUTED}; padding: 4px;")
        cp_layout.addWidget(self.pacnew_lbl)

        card_pacnew.setStyleSheet(f"""
            QFrame#maintCard {{
                background-color: {CachyColors.BG_CARD};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 10px;
            }}
        """)
        layout.addWidget(card_pacnew)

        layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def refresh_data(self):
        """Refreshes all maintenance metrics."""
        # 1. Cache
        sz = SystemCare.get_cache_size()
        self.c_desc.setText(f"Belegt aktuell im Cache: {sz} (Ältere Versionen können sicher entfernt werden)")

        # 2. Orphans
        orphans = SystemCare.get_orphaned_packages()
        if orphans:
            self.orphan_list_lbl.setText(f"{len(orphans)} verwaiste Pakete gefunden:\n" + ", ".join(orphans[:20]))
            self.orphan_list_lbl.setStyleSheet(f"color: {CachyColors.ACCENT_AMBER}; font-size: 12px;")
            self.btn_remove_orphans.setEnabled(True)
        else:
            self.orphan_list_lbl.setText("Keine verwaisten Pakete gefunden. System ist sauber.")
            self.orphan_list_lbl.setStyleSheet(f"color: {CachyColors.ACCENT_EMERALD}; font-size: 12px;")
            self.btn_remove_orphans.setEnabled(False)

        # 3. Snapshots
        snaps = SnapperHelper.list_recent_snapshots(max_count=6)
        self.snap_table.setRowCount(0)
        for s in snaps:
            row = self.snap_table.rowCount()
            self.snap_table.insertRow(row)
            self.snap_table.setItem(row, 0, QTableWidgetItem(str(s.num)))
            self.snap_table.setItem(row, 1, QTableWidgetItem(s.type_str))
            self.snap_table.setItem(row, 2, QTableWidgetItem(s.date_str))
            self.snap_table.setItem(row, 3, QTableWidgetItem(s.description))

        # 4. Pacnew
        pacnews = SystemCare.find_pacnew_files()
        if pacnews:
            self.pacnew_lbl.setText(f"{len(pacnews)} .pacnew Datei(en) gefunden:\n" + "\n".join(pacnews))
            self.pacnew_lbl.setStyleSheet(f"color: {CachyColors.ACCENT_AMBER}; font-size: 12px;")
        else:
            self.pacnew_lbl.setText("Alle Konfigurationen sind aktuell. Keine .pacnew Dateien gefunden.")
            self.pacnew_lbl.setStyleSheet(f"color: {CachyColors.ACCENT_EMERALD}; font-size: 12px;")

    def clean_cache(self):
        """Triggers paccache cleanup."""
        self.btn_clean_cache.setEnabled(False)
        ok, msg = SystemCare.clean_cache(keep=2)
        self.btn_clean_cache.setEnabled(True)
        self.refresh_data()
        if ok:
            QMessageBox.information(self, "Cache bereinigt", "Der Pacman-Paketcache wurde erfolgreich bereinigt.")
        else:
            QMessageBox.warning(self, "Fehler", f"Cache-Bereinigung fehlgeschlagen:\n{msg}")

    def remove_orphans(self):
        """Removes orphan packages."""
        self.btn_remove_orphans.setEnabled(False)
        ok, msg = SystemCare.remove_orphans()
        self.btn_remove_orphans.setEnabled(True)
        self.refresh_data()
        if ok:
            QMessageBox.information(self, "Bereinigung abgeschlossen", "Verwaiste Pakete wurden erfolgreich deinstalliert.")
        else:
            QMessageBox.warning(self, "Fehler", f"Entfernung fehlgeschlagen:\n{msg}")

    def create_snapshot(self):
        """Creates manual snapshot."""
        self.btn_create_snap.setEnabled(False)
        ok, msg = SnapperHelper.create_pre_update_snapshot("CachyOS Manueller Wiederherstellungspunkt")
        self.btn_create_snap.setEnabled(True)
        self.refresh_data()
        if ok:
            QMessageBox.information(self, "Snapshot erstellt", msg)
        else:
            QMessageBox.warning(self, "Snapshot-Fehler", msg)
