"""
Step Indicator widget displaying the 4-step update progression.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ..styles import CachyColors


class StepIndicator(QFrame):
    """Visual progress indicator for the 4-phase update pipeline."""

    PHASES = [
        ("⚡", "Spiegelserver", "Bewertung & Ranking"),
        ("📸", "Snapshot", "BTRFS Sicherung"),
        ("📦", "Pakete", "Download & Upgrade"),
        ("🧹", "Wartung", "Cache & Systemgesundheit"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.step_widgets = []
        self.setObjectName("stepIndicator")
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        for i, (icon, title, subtitle) in enumerate(self.PHASES):
            step_box = QFrame()
            step_box.setObjectName(f"stepBox_{i}")
            box_layout = QHBoxLayout(step_box)
            box_layout.setContentsMargins(10, 8, 10, 8)
            box_layout.setSpacing(10)

            # Icon / badge
            badge = QLabel(icon)
            badge.setFixedSize(32, 32)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(f"""
                background-color: {CachyColors.BG_PANEL};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 16px;
                font-size: 14px;
            """)

            # Texts
            text_layout = QVBoxLayout()
            text_layout.setSpacing(1)
            t_lbl = QLabel(title)
            t_lbl.setStyleSheet(f"font-weight: 700; font-size: 12px; color: {CachyColors.TEXT_SECONDARY};")
            sub_lbl = QLabel(subtitle)
            sub_lbl.setStyleSheet(f"font-size: 10px; color: {CachyColors.TEXT_MUTED};")

            text_layout.addWidget(t_lbl)
            text_layout.addWidget(sub_lbl)

            box_layout.addWidget(badge)
            box_layout.addLayout(text_layout)

            step_box.setStyleSheet(f"""
                QFrame#stepBox_{i} {{
                    background-color: {CachyColors.BG_CARD};
                    border: 1px solid {CachyColors.BORDER_SUBTLE};
                    border-radius: 8px;
                }}
            """)

            self.step_widgets.append((step_box, badge, t_lbl, sub_lbl))
            layout.addWidget(step_box, 1)

            # Arrow divider between steps (except last)
            if i < len(self.PHASES) - 1:
                arrow = QLabel("➔")
                arrow.setStyleSheet(f"color: {CachyColors.TEXT_MUTED}; font-size: 14px;")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(arrow)

    def set_step_state(self, step_index: int, state: str):
        """
        state: 'pending', 'active', 'completed', 'failed'
        """
        if not (0 <= step_index < len(self.step_widgets)):
            return

        box, badge, t_lbl, sub_lbl = self.step_widgets[step_index]
        icon, title, subtitle = self.PHASES[step_index]

        if state == "active":
            box.setStyleSheet(f"""
                QFrame#stepBox_{step_index} {{
                    background-color: {CachyColors.BG_CARD_HOVER};
                    border: 2px solid {CachyColors.ACCENT_EMERALD};
                    border-radius: 8px;
                }}
            """)
            badge.setStyleSheet(f"""
                background-color: {CachyColors.ACCENT_EMERALD};
                color: #000000;
                border-radius: 16px;
                font-size: 14px;
            """)
            t_lbl.setStyleSheet(f"font-weight: 800; font-size: 12px; color: {CachyColors.ACCENT_EMERALD_LIGHT};")
            sub_lbl.setStyleSheet(f"font-size: 10px; color: {CachyColors.TEXT_PRIMARY};")
            badge.setText(icon)

        elif state == "completed":
            box.setStyleSheet(f"""
                QFrame#stepBox_{step_index} {{
                    background-color: {CachyColors.BG_CARD};
                    border: 1px solid {CachyColors.ACCENT_EMERALD_DARK};
                    border-radius: 8px;
                }}
            """)
            badge.setStyleSheet(f"""
                background-color: rgba(0, 212, 148, 0.2);
                border: 1px solid {CachyColors.ACCENT_EMERALD};
                color: {CachyColors.ACCENT_EMERALD_LIGHT};
                border-radius: 16px;
                font-weight: bold;
                font-size: 13px;
            """)
            t_lbl.setStyleSheet(f"font-weight: 700; font-size: 12px; color: {CachyColors.TEXT_PRIMARY};")
            sub_lbl.setStyleSheet(f"font-size: 10px; color: {CachyColors.TEXT_SECONDARY};")
            badge.setText("✓")

        elif state == "failed":
            box.setStyleSheet(f"""
                QFrame#stepBox_{step_index} {{
                    background-color: rgba(255, 69, 91, 0.1);
                    border: 1px solid {CachyColors.ACCENT_RED};
                    border-radius: 8px;
                }}
            """)
            badge.setStyleSheet(f"""
                background-color: {CachyColors.ACCENT_RED};
                color: #ffffff;
                border-radius: 16px;
                font-weight: bold;
                font-size: 13px;
            """)
            t_lbl.setStyleSheet(f"font-weight: 700; font-size: 12px; color: {CachyColors.ACCENT_RED};")
            badge.setText("✕")

        else:  # pending
            box.setStyleSheet(f"""
                QFrame#stepBox_{step_index} {{
                    background-color: {CachyColors.BG_CARD};
                    border: 1px solid {CachyColors.BORDER_SUBTLE};
                    border-radius: 8px;
                }}
            """)
            badge.setStyleSheet(f"""
                background-color: {CachyColors.BG_PANEL};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 16px;
                font-size: 14px;
            """)
            t_lbl.setStyleSheet(f"font-weight: 700; font-size: 12px; color: {CachyColors.TEXT_SECONDARY};")
            sub_lbl.setStyleSheet(f"font-size: 10px; color: {CachyColors.TEXT_MUTED};")
            badge.setText(icon)

    def reset_all(self):
        for i in range(len(self.step_widgets)):
            self.set_step_state(i, "pending")
