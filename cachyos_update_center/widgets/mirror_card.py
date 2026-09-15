"""
Mirror Card Widget displaying latency, speed, and country rating.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ..core.mirror_rater import MirrorResult
from ..styles import CachyColors


class MirrorCard(QFrame):
    """Card widget for displaying a single benchmarked mirror."""

    def __init__(self, mirror: MirrorResult, parent=None):
        super().__init__(parent)
        self.mirror = mirror
        self.setObjectName("mirrorCard")
        self.setProperty("class", "cachy-card")
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        # Rank badge
        rank_lbl = QLabel(f"#{self.mirror.rank}")
        rank_lbl.setFixedWidth(36)
        if self.mirror.rank == 1:
            rank_lbl.setStyleSheet(f"""
                background-color: {CachyColors.ACCENT_EMERALD};
                color: #04120c;
                font-weight: 800;
                font-size: 13px;
                border-radius: 6px;
                padding: 4px;
            """)
        else:
            rank_lbl.setStyleSheet(f"""
                background-color: {CachyColors.BG_PANEL};
                color: {CachyColors.TEXT_SECONDARY};
                font-weight: 700;
                font-size: 12px;
                border-radius: 6px;
                padding: 4px;
            """)
        rank_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(rank_lbl)

        # Country badge
        country_lbl = QLabel(self.mirror.country)
        country_lbl.setFixedWidth(44)
        country_lbl.setStyleSheet(f"""
            background-color: rgba(56, 189, 248, 0.15);
            color: {CachyColors.ACCENT_CYAN};
            border: 1px solid rgba(56, 189, 248, 0.4);
            border-radius: 4px;
            padding: 2px 4px;
            font-weight: 700;
            font-size: 11px;
        """)
        country_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(country_lbl)

        # Center info: URL & repo type
        center_layout = QVBoxLayout()
        center_layout.setSpacing(2)

        url_lbl = QLabel(self.mirror.url)
        url_lbl.setStyleSheet(f"font-weight: 600; color: {CachyColors.TEXT_PRIMARY}; font-size: 13px;")
        url_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        sub_lbl = QLabel(f"Typ: {self.mirror.repo_type.upper()} Repositorium")
        sub_lbl.setStyleSheet(f"color: {CachyColors.TEXT_MUTED}; font-size: 11px;")

        center_layout.addWidget(url_lbl)
        center_layout.addWidget(sub_lbl)
        layout.addLayout(center_layout, 1)

        # Right side: Ping and Speed
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)

        # Ping
        ping_color = CachyColors.ACCENT_EMERALD if self.mirror.ping_ms < 100 else (
            CachyColors.ACCENT_AMBER if self.mirror.ping_ms < 250 else CachyColors.ACCENT_RED
        )
        ping_box = QVBoxLayout()
        ping_box.setSpacing(1)
        ping_val = QLabel(f"{self.mirror.ping_ms} ms")
        ping_val.setStyleSheet(f"font-weight: 700; color: {ping_color}; font-size: 13px;")
        ping_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        ping_title = QLabel("Latenz")
        ping_title.setStyleSheet(f"font-size: 10px; color: {CachyColors.TEXT_MUTED};")
        ping_title.setAlignment(Qt.AlignmentFlag.AlignRight)
        ping_box.addWidget(ping_val)
        ping_box.addWidget(ping_title)
        stats_layout.addLayout(ping_box)

        # Speed
        speed_box = QVBoxLayout()
        speed_box.setSpacing(1)
        speed_val = QLabel(self.mirror.speed_text)
        speed_val.setStyleSheet(f"font-weight: 800; color: {CachyColors.ACCENT_EMERALD_LIGHT}; font-size: 14px;")
        speed_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        speed_title = QLabel("Durchsatz")
        speed_title.setStyleSheet(f"font-size: 10px; color: {CachyColors.TEXT_MUTED};")
        speed_title.setAlignment(Qt.AlignmentFlag.AlignRight)
        speed_box.addWidget(speed_val)
        speed_box.addWidget(speed_title)
        stats_layout.addLayout(speed_box)

        layout.addLayout(stats_layout)

        # Apply card styling
        self.setStyleSheet(f"""
            QFrame#mirrorCard {{
                background-color: {CachyColors.BG_CARD};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 8px;
            }}
            QFrame#mirrorCard:hover {{
                border-color: {CachyColors.ACCENT_EMERALD};
                background-color: {CachyColors.BG_CARD_HOVER};
            }}
        """)
