"""
Packages View: Detailed table of pending updates with search, filtering, and selective choices.
"""
from typing import List, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.package_checker import PackageUpdate
from ..styles import CachyColors


class PackagesView(QWidget):
    """Interactive list of packages available for update."""

    request_refresh = pyqtSignal()
    request_install_selected = pyqtSignal(list)  # sends list of package names

    def __init__(self, parent=None):
        super().__init__(parent)
        self.packages: List[PackageUpdate] = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # ----------------------------------------------------------------------
        # Top Filter Bar
        # ----------------------------------------------------------------------
        filter_card = QFrame()
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(14, 12, 14, 12)
        filter_layout.setSpacing(14)

        # Search field
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Paket suchen (Name, Beschreibung)...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.search_input, 2)

        # Category filter combo
        self.combo_filter = QComboBox()
        self.combo_filter.addItems(["Alle Repositorien", "Nur CachyOS", "Nur Arch / System", "Nur AUR"])
        self.combo_filter.currentIndexChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.combo_filter, 1)

        # Select all checkbox
        self.chk_select_all = QCheckBox("Alle auswählen")
        self.chk_select_all.setChecked(True)
        self.chk_select_all.stateChanged.connect(self.toggle_select_all)
        filter_layout.addWidget(self.chk_select_all)

        # Refresh button
        self.btn_refresh = QPushButton("Neu laden")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.request_refresh.emit)
        filter_layout.addWidget(self.btn_refresh)

        filter_card.setStyleSheet(f"""
            QFrame {{
                background-color: {CachyColors.BG_CARD};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 8px;
            }}
        """)
        layout.addWidget(filter_card)

        # ----------------------------------------------------------------------
        # Online Issue Warning Banner
        # ----------------------------------------------------------------------
        self.issue_banner = QFrame()
        self.issue_banner.setObjectName("issueBanner")
        self.issue_banner.setVisible(False)
        ib_layout = QHBoxLayout(self.issue_banner)
        ib_layout.setContentsMargins(14, 10, 14, 10)
        ib_layout.setSpacing(10)

        ib_icon = QLabel("🛡️")
        ib_icon.setStyleSheet("font-size: 18px;")
        ib_layout.addWidget(ib_icon)

        self.ib_text = QLabel("")
        self.ib_text.setStyleSheet(f"color: {CachyColors.ACCENT_AMBER}; font-weight: 600; font-size: 12px;")
        self.ib_text.setWordWrap(True)
        ib_layout.addWidget(self.ib_text, 1)

        self.issue_banner.setStyleSheet(f"""
            QFrame#issueBanner {{
                background-color: rgba(255, 179, 0, 0.12);
                border: 1px solid {CachyColors.ACCENT_AMBER};
                border-radius: 8px;
            }}
        """)
        layout.addWidget(self.issue_banner)

        # ----------------------------------------------------------------------
        # Package Table
        # ----------------------------------------------------------------------
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Auswahl", "Paketname", "Repositorium", "Installiert", "Verfügbar", "Größe", "Beschreibung"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Column sizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table, 1)

        # ----------------------------------------------------------------------
        # Bottom Summary & Action Bar
        # ----------------------------------------------------------------------
        bottom_bar = QFrame()
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(14, 10, 14, 10)
        bottom_layout.setSpacing(16)

        self.summary_lbl = QLabel("0 Pakete verfügbar")
        self.summary_lbl.setStyleSheet(f"font-weight: 600; color: {CachyColors.TEXT_SECONDARY};")
        bottom_layout.addWidget(self.summary_lbl)
        bottom_layout.addStretch()

        self.btn_install_selected = QPushButton("  ⚡ Ausgewählte aktualisieren (inkl. Spiegelserver-Bewertung)")
        self.btn_install_selected.setProperty("class", "btn-primary")
        self.btn_install_selected.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_install_selected.clicked.connect(self._on_install_clicked)
        bottom_layout.addWidget(self.btn_install_selected)

        bottom_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {CachyColors.BG_PANEL};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 8px;
            }}
        """)
        layout.addWidget(bottom_bar)

    def set_packages(self, packages: List[PackageUpdate]):
        """Populates the table with new package data."""
        self.packages = packages
        self.apply_filter()

    def apply_filter(self):
        """Filters rows according to search text and category selection."""
        search_text = self.search_input.text().lower()
        filter_idx = self.combo_filter.currentIndex()

        self.table.setRowCount(0)
        selected_count = 0
        visible_count = 0
        issues_count = sum(1 for p in self.packages if p.has_online_issue)

        if issues_count > 0:
            problematic_names = [p.name for p in self.packages if p.has_online_issue]
            self.ib_text.setText(
                f"Automatische Schutzfunktion aktiv: {issues_count} Paket(e) ({', '.join(problematic_names)}) "
                f"wurden wegen bekannter Online-Probleme oder manueller Eingriffserfordernis abgewählt."
            )
            self.issue_banner.setVisible(True)
        else:
            self.issue_banner.setVisible(False)

        for pkg in self.packages:
            # Filter category
            if filter_idx == 1 and not pkg.is_cachyos:
                continue
            elif filter_idx == 2 and (pkg.is_cachyos or pkg.is_aur):
                continue
            elif filter_idx == 3 and not pkg.is_aur:
                continue

            # Search text
            if search_text and (search_text not in pkg.name.lower() and search_text not in pkg.description.lower()):
                continue

            row = self.table.rowCount()
            self.table.insertRow(row)
            visible_count += 1

            # Checkbox item
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk_item.setCheckState(Qt.CheckState.Checked if pkg.is_selected else Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, chk_item)
            if pkg.is_selected:
                selected_count += 1

            # Name
            name_item = QTableWidgetItem(pkg.name)
            name_item.setForeground(Qt.GlobalColor.white)
            if pkg.has_online_issue:
                name_item.setText(f"⚠️ {pkg.name}")
                name_item.setToolTip(f"Online-Problem gemeldet: {pkg.issue_reason}")
                name_item.setForeground(Qt.GlobalColor.yellow)
            elif pkg.is_kernel:
                name_item.setText(f"🐧 {pkg.name}")
            self.table.setItem(row, 1, name_item)

            # Repo
            repo_item = QTableWidgetItem(pkg.repo)
            if pkg.is_cachyos:
                repo_item.setForeground(Qt.GlobalColor.green)
            elif pkg.is_aur:
                repo_item.setForeground(Qt.GlobalColor.cyan)
            self.table.setItem(row, 2, repo_item)

            # Versions
            self.table.setItem(row, 3, QTableWidgetItem(pkg.current_version))
            new_v_item = QTableWidgetItem(pkg.new_version)
            new_v_item.setForeground(Qt.GlobalColor.green)
            self.table.setItem(row, 4, new_v_item)

            # Size
            self.table.setItem(row, 5, QTableWidgetItem(pkg.size_text or "-"))

            # Desc
            desc_text = pkg.description or "-"
            if pkg.has_online_issue:
                desc_text = f"[⚠️ AUSGESCHLOSSEN: {pkg.issue_reason}] {desc_text}"
            desc_item = QTableWidgetItem(desc_text)
            if pkg.has_online_issue:
                desc_item.setToolTip(f"Quelle: {pkg.issue_url or 'Online-Feed'}")
                desc_item.setForeground(Qt.GlobalColor.yellow)
            self.table.setItem(row, 6, desc_item)


        self.table.itemChanged.connect(self._on_item_changed)
        self.summary_lbl.setText(f"{selected_count} von {len(self.packages)} Paketen ausgewählt")
        self.btn_install_selected.setEnabled(selected_count > 0)

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() == 0:
            row = item.row()
            if row < len(self.packages):
                self.packages[row].is_selected = (item.checkState() == Qt.CheckState.Checked)

            selected_count = sum(1 for p in self.packages if p.is_selected)
            self.summary_lbl.setText(f"{selected_count} von {len(self.packages)} Paketen ausgewählt")
            self.btn_install_selected.setEnabled(selected_count > 0)

    def toggle_select_all(self, state):
        checked = (state == Qt.CheckState.Checked.value or state == 2)
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        for pkg in self.packages:
            pkg.is_selected = checked
        self.table.blockSignals(False)

        selected_count = len(self.packages) if checked else 0
        self.summary_lbl.setText(f"{selected_count} von {len(self.packages)} Paketen ausgewählt")
        self.btn_install_selected.setEnabled(selected_count > 0)

    def _on_install_clicked(self):
        selected_names = [p.name for p in self.packages if p.is_selected]
        # If all selected, pass None to do full upgrade
        if len(selected_names) == len(self.packages):
            self.request_install_selected.emit([])
        else:
            self.request_install_selected.emit(selected_names)
