"""
Interactive Package Issue & Security Diagnostic Dialog for CachyOS Update Center.
Displays full-text advisories, CVE vulnerabilities, manual intervention instructions,
and 1-click terminal remediation commands.
"""
from typing import List, Optional

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core.online_issue_checker import ProblemReport
from ..core.package_checker import PackageUpdate
from ..styles import CachyColors


class PackageIssueDialog(QDialog):
    """Deep inspection modal for package advisories, security issues, and manual intervention."""

    def __init__(self, package: PackageUpdate, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.package = package
        self.setWindowTitle(f"Sicherheits- & Problem-Diagnose – {package.name}")
        self.resize(840, 580)
        self.setMinimumSize(680, 440)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # ----------------------------------------------------------------------
        # Header Card: Package Identity & Versions
        # ----------------------------------------------------------------------
        header_card = QFrame()
        header_card.setStyleSheet(f"""
            QFrame {{
                background-color: {CachyColors.BG_CARD};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 10px;
                padding: 12px;
            }}
        """)
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(14, 12, 14, 12)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)

        lbl_pkg_name = QLabel(f"📦 {self.package.name}")
        lbl_pkg_name.setStyleSheet("font-size: 18px; font-weight: 700; color: #FFFFFF;")
        title_col.addWidget(lbl_pkg_name)

        ver_text = f"Installiert: <b style='color:#94A3B8;'>{self.package.current_version}</b>  ➔  Ziel: <b style='color:#00D494;'>{self.package.new_version}</b>  |  Repo: <b style='color:#38bdf8;'>{self.package.repo}</b>"
        lbl_ver = QLabel(ver_text)
        lbl_ver.setStyleSheet("font-size: 12px; color: #94A3B8;")
        title_col.addWidget(lbl_ver)

        h_layout.addLayout(title_col, 1)

        # Overall Status Badge
        badge = QLabel()
        badge.setStyleSheet("padding: 6px 14px; border-radius: 6px; font-weight: 700; font-size: 11px;")
        if self.package.has_online_issue:
            badge.setText("🔴 MANUELLER EINGRIFF")
            badge.setStyleSheet("background-color: rgba(239, 68, 68, 0.15); color: #FF455B; border: 1px solid #ef4444; padding: 6px 14px; border-radius: 6px; font-weight: 700; font-size: 11px;")
        elif self.package.has_security_fix:
            badge.setText("🛡️ SICHERHEITS-PATCH")
            badge.setStyleSheet("background-color: rgba(0, 212, 148, 0.15); color: #00D494; border: 1px solid #00D494; padding: 6px 14px; border-radius: 6px; font-weight: 700; font-size: 11px;")
        else:
            badge.setText("ℹ️ DIAGNOSE")
            badge.setStyleSheet("background-color: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid #38bdf8; padding: 6px 14px; border-radius: 6px; font-weight: 700; font-size: 11px;")
        h_layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(header_card)

        # ----------------------------------------------------------------------
        # Scrollable Issues / Reports Area
        # ----------------------------------------------------------------------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
        """)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(12)

        reports: List[ProblemReport] = getattr(self.package, "issues_list", [])
        if not reports and self.package.issue_reason:
            # Fallback single report
            reports = [ProblemReport(
                package_name=self.package.name,
                severity="CRITICAL" if self.package.has_online_issue else "INFO",
                source="Online-Feed",
                title=self.package.issue_reason,
                url=self.package.issue_url,
                reason=self.package.issue_reason,
            )]

        for rep in reports:
            card = self._create_report_card(rep)
            scroll_layout.addWidget(card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # ----------------------------------------------------------------------
        # Bottom Actions Bar
        # ----------------------------------------------------------------------
        bottom_frame = QFrame()
        bottom_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {CachyColors.BG_CARD};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        b_layout = QHBoxLayout(bottom_frame)
        b_layout.setContentsMargins(10, 8, 10, 8)

        self.btn_toggle_exclude = QPushButton()
        self._update_toggle_button_text()
        self.btn_toggle_exclude.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_exclude.clicked.connect(self._on_toggle_exclude)
        b_layout.addWidget(self.btn_toggle_exclude)

        b_layout.addStretch()

        btn_close = QPushButton("Schließen")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {CachyColors.BG_PANEL};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                color: {CachyColors.TEXT_PRIMARY};
                padding: 7px 18px;
                border-radius: 6px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {CachyColors.BG_CARD_HOVER};
                border-color: {CachyColors.BORDER_HOVER};
            }}
        """)
        btn_close.clicked.connect(self.accept)
        b_layout.addWidget(btn_close)

        layout.addWidget(bottom_frame)

    def _update_toggle_button_text(self):
        if self.package.is_selected:
            self.btn_toggle_exclude.setText("❌ Dieses Paket vom Update ausschließen (--ignore)")
            self.btn_toggle_exclude.setStyleSheet("""
                QPushButton {
                    background-color: rgba(239, 68, 68, 0.15);
                    border: 1px solid #ef4444;
                    color: #FF455B;
                    padding: 7px 16px;
                    border-radius: 6px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #ef4444;
                    color: #FFFFFF;
                }
            """)
        else:
            self.btn_toggle_exclude.setText("✅ Dieses Paket trotzdem in das Update aufnehmen")
            self.btn_toggle_exclude.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 212, 148, 0.15);
                    border: 1px solid #00D494;
                    color: #00D494;
                    padding: 7px 16px;
                    border-radius: 6px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #00D494;
                    color: #0d131c;
                }
            """)

    def _on_toggle_exclude(self):
        self.package.is_selected = not self.package.is_selected
        self._update_toggle_button_text()

    def _create_report_card(self, rep: ProblemReport) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {CachyColors.BG_PANEL};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 8px;
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(14, 14, 14, 14)
        c_layout.setSpacing(10)

        # Header with severity badge and source
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        sev_badge = QLabel()
        if rep.severity == "CRITICAL":
            sev_badge.setText("🔴 MANUELLE INTERVENTION")
            sev_badge.setStyleSheet("background: rgba(239, 68, 68, 0.2); color: #FF455B; border: 1px solid #ef4444; padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;")
        elif rep.severity == "SECURITY_FIX":
            sev_badge.setText("🛡️ SICHERHEITS-FIX")
            sev_badge.setStyleSheet("background: rgba(0, 212, 148, 0.2); color: #00D494; border: 1px solid #00D494; padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;")
        elif rep.severity == "VULNERABILITY":
            sev_badge.setText("⚠️ BEKANNTE SICHERHEITSLÜCKE")
            sev_badge.setStyleSheet("background: rgba(245, 158, 11, 0.2); color: #FFB300; border: 1px solid #f59e0b; padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;")
        elif rep.severity == "WARNING":
            sev_badge.setText("⚠️ WARNUNG")
            sev_badge.setStyleSheet("background: rgba(245, 158, 11, 0.2); color: #FFB300; border: 1px solid #f59e0b; padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;")
        else:
            sev_badge.setText("ℹ️ HINWEIS")
            sev_badge.setStyleSheet("background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid #38bdf8; padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;")
        top_row.addWidget(sev_badge)

        source_lbl = QLabel(f"Quelle: {rep.source}")
        source_lbl.setStyleSheet("font-size: 11px; color: #64748B; font-weight: 600;")
        top_row.addWidget(source_lbl)

        if rep.pub_date:
            date_lbl = QLabel(f"Datum: {rep.pub_date[:16]}")
            date_lbl.setStyleSheet("font-size: 11px; color: #64748B;")
            top_row.addWidget(date_lbl)

        top_row.addStretch()

        if rep.url:
            btn_web = QPushButton("🌐 Meldung öffnen")
            btn_web.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_web.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {CachyColors.ACCENT_CYAN};
                    border: none;
                    font-size: 11px;
                    font-weight: 600;
                    text-decoration: underline;
                }}
                QPushButton:hover {{
                    color: #FFFFFF;
                }}
            """)
            btn_web.clicked.connect(lambda _, u=rep.url: QDesktopServices.openUrl(QUrl(u)))
            top_row.addWidget(btn_web)

        c_layout.addLayout(top_row)

        # Title
        title_lbl = QLabel(rep.title)
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #FFFFFF;")
        title_lbl.setWordWrap(True)
        c_layout.addWidget(title_lbl)

        # Reason / Description
        desc_text = rep.description if rep.description else rep.reason
        desc_lbl = QLabel(desc_text)
        desc_lbl.setStyleSheet("font-size: 12px; color: #CBD5E1; line-height: 1.4;")
        desc_lbl.setWordWrap(True)
        c_layout.addWidget(desc_lbl)

        # CVE Chips if available
        if rep.cves:
            cve_layout = QHBoxLayout()
            cve_layout.setSpacing(6)
            cve_label = QLabel("Relevante CVEs:")
            cve_label.setStyleSheet("font-size: 11px; color: #94A3B8; font-weight: 600;")
            cve_layout.addWidget(cve_label)

            for cve in rep.cves[:8]:
                chip = QPushButton(cve)
                chip.setCursor(Qt.CursorShape.PointingHandCursor)
                chip.setStyleSheet("""
                    QPushButton {
                        background-color: #1e293b;
                        border: 1px solid #334155;
                        color: #38bdf8;
                        border-radius: 4px;
                        padding: 2px 6px;
                        font-size: 10px;
                        font-family: monospace;
                    }
                    QPushButton:hover {
                        background-color: #334155;
                        color: #FFFFFF;
                    }
                """)
                cve_url = f"https://security.archlinux.org/issues/{cve}"
                chip.clicked.connect(lambda _, u=cve_url: QDesktopServices.openUrl(QUrl(u)))
                cve_layout.addWidget(chip)

            cve_layout.addStretch()
            c_layout.addLayout(cve_layout)

        # Remediation command box if present
        if rep.remediation_cmd:
            cmd_frame = QFrame()
            cmd_frame.setStyleSheet("""
                QFrame {
                    background-color: #0a0f18;
                    border: 1px dashed #ef4444;
                    border-radius: 6px;
                    padding: 6px;
                }
            """)
            cmd_layout = QHBoxLayout(cmd_frame)
            cmd_layout.setContentsMargins(10, 8, 10, 8)

            lbl_term = QLabel(f"💻 <b>Lösungs-Befehl:</b> <code style='color:#00FFA8;'>{rep.remediation_cmd}</code>")
            lbl_term.setStyleSheet("font-family: monospace; font-size: 12px; color: #FFFFFF;")
            cmd_layout.addWidget(lbl_term, 1)

            btn_copy = QPushButton("📋 Kopieren")
            btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_copy.setMinimumWidth(110)
            btn_copy.setStyleSheet(f"""
                QPushButton {{
                    background-color: {CachyColors.BG_CARD};
                    border: 1px solid {CachyColors.BORDER_SUBTLE};
                    color: {CachyColors.TEXT_PRIMARY};
                    border-radius: 4px;
                    padding: 5px 12px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {CachyColors.BG_CARD_HOVER};
                    border-color: {CachyColors.ACCENT_EMERALD};
                }}
            """)
            btn_copy.clicked.connect(lambda _, c=rep.remediation_cmd, b=btn_copy: self._copy_command(c, b))
            cmd_layout.addWidget(btn_copy)

            c_layout.addWidget(cmd_frame)

        return card

    def _copy_command(self, cmd: str, btn: QPushButton):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(cmd)
            btn.setText("✓ Kopiert!")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 212, 148, 0.2);
                    border: 1px solid #00D494;
                    color: #00D494;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 700;
                }
            """)
