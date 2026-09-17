"""
Packages View: Detailed table of pending updates with search, filtering, and selective choices.
Includes deep issue diagnostics, Arch News intervention alerts, CVE vulnerability badges,
and interactive modal problem inspection.
"""
from typing import List, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
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
from ..dialogs.package_issue_dialog import PackageIssueDialog
from ..styles import CachyColors


class PackagesView(QWidget):
    """Interactive list of packages available for update with security & issue intelligence."""

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
        filter_layout.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Paket suchen (Name, Beschreibung)...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.search_input, 2)

        # Category filter combo
        self.combo_filter = QComboBox()
        self.combo_filter.addItems([
            "Alle Repositorien",
            "Nur CachyOS",
            "Nur Arch / System",
            "Nur AUR",
            "⚠️ Nur mit Problemen / Interventionen",
            "🛡️ Nur Sicherheits-Updates (CVE-Fixes)",
        ])
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
        # Online Issue Warning Banner with Quick Actions
        # ----------------------------------------------------------------------
        self.issue_banner = QFrame()
        self.issue_banner.setObjectName("issueBanner")
        self.issue_banner.setVisible(False)
        ib_layout = QHBoxLayout(self.issue_banner)
        ib_layout.setContentsMargins(14, 10, 14, 10)
        ib_layout.setSpacing(12)

        ib_icon = QLabel("🛡️")
        ib_icon.setStyleSheet("font-size: 18px;")
        ib_layout.addWidget(ib_icon)

        self.ib_text = QLabel("")
        self.ib_text.setStyleSheet(f"color: {CachyColors.TEXT_PRIMARY}; font-size: 12px;")
        self.ib_text.setWordWrap(True)
        ib_layout.addWidget(self.ib_text, 1)

        # Quick action buttons on the banner
        self.btn_banner_issues = QPushButton("⚠️ Problem-Pakete filtern")
        self.btn_banner_issues.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_banner_issues.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.2);
                border: 1px solid #ef4444;
                color: #FF455B;
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: #FFFFFF;
            }
        """)
        self.btn_banner_issues.clicked.connect(lambda: self.combo_filter.setCurrentIndex(4))
        ib_layout.addWidget(self.btn_banner_issues)

        self.btn_banner_sec = QPushButton("🛡️ Sicherheits-Fixes filtern")
        self.btn_banner_sec.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_banner_sec.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 212, 148, 0.2);
                border: 1px solid #00D494;
                color: #00D494;
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #00D494;
                color: #0d131c;
            }
        """)
        self.btn_banner_sec.clicked.connect(lambda: self.combo_filter.setCurrentIndex(5))
        ib_layout.addWidget(self.btn_banner_sec)

        self.issue_banner.setStyleSheet(f"""
            QFrame#issueBanner {{
                background-color: rgba(23, 34, 48, 0.95);
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-left: 4px solid {CachyColors.ACCENT_EMERALD};
                border-radius: 8px;
            }}
        """)
        layout.addWidget(self.issue_banner)

        # ----------------------------------------------------------------------
        # Package Table
        # ----------------------------------------------------------------------
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Auswahl", "Paketname", "Diagnose & Status", "Repositorium", "Installiert", "Verfügbar", "Größe", "Beschreibung"
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
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table, 1)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.cellClicked.connect(self._on_cell_clicked)

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

        lbl_hint = QLabel("💡 Tipp: Klicke auf ein Paket oder Badge für die detaillierte Sicherheits- & Problemanalyse.")
        lbl_hint.setStyleSheet("font-size: 11px; color: #64748B;")
        bottom_layout.addWidget(lbl_hint)

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

        self.table.blockSignals(True)
        self.table.setRowCount(0)
        selected_count = 0
        visible_count = 0

        issues_count = sum(1 for p in self.packages if p.has_online_issue and getattr(p, "issue_severity", "") == "CRITICAL")
        warnings_count = sum(1 for p in self.packages if p.has_online_issue and getattr(p, "issue_severity", "") != "CRITICAL")
        sec_fix_count = sum(1 for p in self.packages if getattr(p, "has_security_fix", False))

        if issues_count > 0 or sec_fix_count > 0 or warnings_count > 0:
            parts = []
            if issues_count > 0:
                parts.append(f"<b style='color:#FF455B;'>{issues_count} Paket(e)</b> mit manueller Intervention automatisch abgewählt")
            if sec_fix_count > 0:
                parts.append(f"<b style='color:#00FFA8;'>{sec_fix_count} Sicherheits-Patch(es)</b> verfügbar")
            if warnings_count > 0:
                parts.append(f"<b style='color:#FFB300;'>{warnings_count} Hinweis(e) / Warnung(en)</b>")

            self.ib_text.setText("🛡️ <b>Online-Sicherheitsüberprüfung aktiv:</b> " + " &nbsp;•&nbsp; ".join(parts))
            self.btn_banner_issues.setVisible(issues_count > 0 or warnings_count > 0)
            self.btn_banner_sec.setVisible(sec_fix_count > 0)
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
            elif filter_idx == 4 and not pkg.has_online_issue:
                continue
            elif filter_idx == 5 and not getattr(pkg, "has_security_fix", False):
                continue

            # Search text
            if search_text and (search_text not in pkg.name.lower() and search_text not in pkg.description.lower()):
                continue

            row = self.table.rowCount()
            self.table.insertRow(row)
            visible_count += 1

            # 0. Checkbox item
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk_item.setCheckState(Qt.CheckState.Checked if pkg.is_selected else Qt.CheckState.Unchecked)
            chk_item.setData(Qt.ItemDataRole.UserRole, pkg.name)
            self.table.setItem(row, 0, chk_item)
            if pkg.is_selected:
                selected_count += 1

            # 1. Name
            name_item = QTableWidgetItem(pkg.name)
            name_item.setForeground(Qt.GlobalColor.white)
            if pkg.has_online_issue:
                if getattr(pkg, "issue_severity", "") == "CRITICAL":
                    name_item.setText(f"⛔ {pkg.name}")
                    name_item.setForeground(QColor("#FF455B"))
                else:
                    name_item.setText(f"⚠️ {pkg.name}")
                    name_item.setForeground(QColor("#FFB300"))
                name_item.setToolTip(f"Online-Problem: {pkg.issue_reason}\nDoppelklick für Details & Lösung.")
            elif getattr(pkg, "has_security_fix", False):
                name_item.setText(f"🛡️ {pkg.name}")
                name_item.setForeground(QColor("#00FFA8"))
                name_item.setToolTip(f"Sicherheits-Fix: {pkg.issue_reason}\nDoppelklick für CVE-Übersicht.")
            elif pkg.is_kernel:
                name_item.setText(f"🐧 {pkg.name}")
            self.table.setItem(row, 1, name_item)

            # 2. Diagnose & Status Badge Column
            diag_item = QTableWidgetItem()
            diag_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if pkg.has_online_issue:
                if getattr(pkg, "issue_severity", "") == "CRITICAL":
                    diag_item.setText("🔴 Intervention nötig  🔍")
                    diag_item.setForeground(QColor("#FF455B"))
                    diag_item.setToolTip(f"Kritisches Problem: {pkg.issue_reason}\nKlicken für Details und Lösungsbefehl.")
                else:
                    diag_item.setText("⚠️ Warnung / Audit  🔍")
                    diag_item.setForeground(QColor("#FFB300"))
                    diag_item.setToolTip(f"Hinweis: {pkg.issue_reason}\nKlicken für Details.")
            elif getattr(pkg, "has_security_fix", False):
                diag_item.setText("🛡️ Sicherheits-Fix  🔍")
                diag_item.setForeground(QColor("#00D494"))
                diag_item.setToolTip(f"{pkg.issue_reason}\nKlicken für CVE-Liste.")
            else:
                diag_item.setText("✓ Sicher & Bereit")
                diag_item.setForeground(QColor("#64748B"))
                diag_item.setToolTip("Keine bekannten Breaking Changes oder offenen Sicherheitswarnungen.")
            self.table.setItem(row, 2, diag_item)

            # 3. Repo
            repo_item = QTableWidgetItem(pkg.repo)
            if pkg.is_cachyos:
                repo_item.setForeground(QColor("#00D494"))
            elif pkg.is_aur:
                repo_item.setForeground(QColor("#00D2FF"))
            self.table.setItem(row, 3, repo_item)

            # 4. Current Version
            self.table.setItem(row, 4, QTableWidgetItem(pkg.current_version))

            # 5. New Version
            new_v_item = QTableWidgetItem(pkg.new_version)
            new_v_item.setForeground(QColor("#00FFA8"))
            self.table.setItem(row, 5, new_v_item)

            # 6. Size
            self.table.setItem(row, 6, QTableWidgetItem(pkg.size_text or "-"))

            # 7. Description
            desc_text = pkg.description or "-"
            if pkg.has_online_issue:
                desc_text = f"[⚠️ {pkg.issue_reason}] {desc_text}"
            desc_item = QTableWidgetItem(desc_text)
            if pkg.has_online_issue:
                desc_item.setToolTip(f"Quelle: {pkg.issue_url or 'Online-Feed'}")
                desc_item.setForeground(QColor("#FFB300"))
            elif getattr(pkg, "has_security_fix", False):
                desc_item.setForeground(QColor("#00FFA8"))
            self.table.setItem(row, 7, desc_item)

        self.table.blockSignals(False)
        self.summary_lbl.setText(f"{selected_count} von {len(self.packages)} Paketen ausgewählt ({sec_fix_count} Sicherheits-Fixes)")
        self.btn_install_selected.setEnabled(selected_count > 0)

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() == 0:
            pkg_name = item.data(Qt.ItemDataRole.UserRole)
            if pkg_name:
                for p in self.packages:
                    if p.name == pkg_name:
                        p.is_selected = (item.checkState() == Qt.CheckState.Checked)
                        break

            selected_count = sum(1 for p in self.packages if p.is_selected)
            sec_fix_count = sum(1 for p in self.packages if getattr(p, "has_security_fix", False))
            self.summary_lbl.setText(f"{selected_count} von {len(self.packages)} Paketen ausgewählt ({sec_fix_count} Sicherheits-Fixes)")
            self.btn_install_selected.setEnabled(selected_count > 0)

    def _on_cell_clicked(self, row: int, col: int):
        # If user clicks specifically on the Diagnose & Status column (column 2)
        if col == 2:
            self._open_dialog_for_row(row)

    def _on_cell_double_clicked(self, row: int, col: int):
        # If user double-clicks any column except checkbox
        if col != 0:
            self._open_dialog_for_row(row)

    def _open_dialog_for_row(self, row: int):
        chk_item = self.table.item(row, 0)
        if not chk_item:
            return
        pkg_name = chk_item.data(Qt.ItemDataRole.UserRole)
        for pkg in self.packages:
            if pkg.name == pkg_name:
                # Open issue dialog if there are issues, security fixes, or just to inspect package
                dlg = PackageIssueDialog(pkg, self)
                dlg.exec()
                # Re-apply to update checkbox and stats if user toggled selection in modal
                self.apply_filter()
                break

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
        sec_fix_count = sum(1 for p in self.packages if getattr(p, "has_security_fix", False))
        self.summary_lbl.setText(f"{selected_count} von {len(self.packages)} Paketen ausgewählt ({sec_fix_count} Sicherheits-Fixes)")
        self.btn_install_selected.setEnabled(selected_count > 0)

    def _on_install_clicked(self):
        selected_names = [p.name for p in self.packages if p.is_selected]
        # If all selected, pass None to do full upgrade
        if len(selected_names) == len(self.packages):
            self.request_install_selected.emit([])
        else:
            self.request_install_selected.emit(selected_names)
