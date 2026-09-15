"""
Theme constants and stylesheet for CachyOS Update Center.
Designed with CachyOS Emerald & Slate dark aesthetics.
"""

class CachyColors:
    BG_DARKEST = "#090d14"
    BG_DARK = "#0d131c"
    BG_PANEL = "#131b26"
    BG_CARD = "#172230"
    BG_CARD_HOVER = "#1e2c3e"
    BG_INPUT = "#101823"

    BORDER_SUBTLE = "#233348"
    BORDER_HOVER = "#364d6c"
    BORDER_ACTIVE = "#00D494"

    ACCENT_EMERALD = "#00D494"
    ACCENT_EMERALD_LIGHT = "#00FFA8"
    ACCENT_EMERALD_DARK = "#008F66"
    ACCENT_EMERALD_GLOW = "rgba(0, 212, 148, 0.25)"

    ACCENT_CYAN = "#00D2FF"
    ACCENT_AMBER = "#FFB300"
    ACCENT_RED = "#FF455B"
    ACCENT_PURPLE = "#A855F7"

    TEXT_PRIMARY = "#F8FAFC"
    TEXT_SECONDARY = "#94A3B8"
    TEXT_MUTED = "#64748B"


CACHY_STYLESHEET = f"""
/* Global Reset & Base */
QWidget {{
    background-color: transparent;
    color: {CachyColors.TEXT_PRIMARY};
    font-family: "Inter", "Cantarell", "Noto Sans", "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
    font-size: 13px;
    outline: none;
}}

QMainWindow, QDialog {{
    background-color: {CachyColors.BG_DARK};
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: {CachyColors.BG_DARK};
    width: 8px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {CachyColors.BORDER_SUBTLE};
    min-height: 24px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: {CachyColors.ACCENT_EMERALD};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background: {CachyColors.BG_DARK};
    height: 8px;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background: {CachyColors.BORDER_SUBTLE};
    min-width: 24px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {CachyColors.ACCENT_EMERALD};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* Cards & Containers */
QFrame.cachy-card {{
    background-color: {CachyColors.BG_CARD};
    border: 1px solid {CachyColors.BORDER_SUBTLE};
    border-radius: 10px;
}}
QFrame.cachy-card:hover {{
    border-color: {CachyColors.BORDER_HOVER};
}}

QFrame.cachy-panel {{
    background-color: {CachyColors.BG_PANEL};
    border: 1px solid {CachyColors.BORDER_SUBTLE};
    border-radius: 8px;
}}

/* Sidebar navigation */
QFrame#navSidebar {{
    background-color: {CachyColors.BG_DARKEST};
    border-right: 1px solid {CachyColors.BORDER_SUBTLE};
}}

QPushButton.nav-btn {{
    background-color: transparent;
    color: {CachyColors.TEXT_SECONDARY};
    text-align: left;
    padding: 10px 16px;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton.nav-btn:hover {{
    background-color: {CachyColors.BG_PANEL};
    color: {CachyColors.TEXT_PRIMARY};
}}
QPushButton.nav-btn[active="true"] {{
    background-color: {CachyColors.BG_CARD};
    color: {CachyColors.ACCENT_EMERALD_LIGHT};
    font-weight: 600;
    border-left: 3px solid {CachyColors.ACCENT_EMERALD};
}}

/* Buttons */
QPushButton {{
    background-color: {CachyColors.BG_CARD};
    color: {CachyColors.TEXT_PRIMARY};
    border: 1px solid {CachyColors.BORDER_SUBTLE};
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {CachyColors.BG_CARD_HOVER};
    border-color: {CachyColors.BORDER_HOVER};
}}
QPushButton:pressed {{
    background-color: {CachyColors.BG_PANEL};
}}
QPushButton:disabled {{
    background-color: {CachyColors.BG_PANEL};
    color: {CachyColors.TEXT_MUTED};
    border-color: {CachyColors.BORDER_SUBTLE};
}}

/* Primary Accent Button */
QPushButton.btn-primary {{
    background-color: {CachyColors.ACCENT_EMERALD};
    color: #03140e;
    border: 1px solid {CachyColors.ACCENT_EMERALD_LIGHT};
    font-weight: 700;
    border-radius: 7px;
    padding: 10px 20px;
}}
QPushButton.btn-primary:hover {{
    background-color: {CachyColors.ACCENT_EMERALD_LIGHT};
    color: #020d09;
}}
QPushButton.btn-primary:pressed {{
    background-color: {CachyColors.ACCENT_EMERALD_DARK};
    color: #ffffff;
}}
QPushButton.btn-primary:disabled {{
    background-color: #17362a;
    color: #4a7565;
    border-color: #1b4334;
}}

/* Danger Button */
QPushButton.btn-danger {{
    background-color: rgba(255, 69, 91, 0.15);
    color: {CachyColors.ACCENT_RED};
    border: 1px solid {CachyColors.ACCENT_RED};
    font-weight: 600;
}}
QPushButton.btn-danger:hover {{
    background-color: {CachyColors.ACCENT_RED};
    color: #ffffff;
}}

/* Inputs & Search */
QLineEdit, QComboBox, QSpinBox {{
    background-color: {CachyColors.BG_INPUT};
    color: {CachyColors.TEXT_PRIMARY};
    border: 1px solid {CachyColors.BORDER_SUBTLE};
    border-radius: 6px;
    padding: 7px 12px;
    font-size: 13px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {CachyColors.ACCENT_EMERALD};
    background-color: {CachyColors.BG_DARK};
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 25px;
    border-left: 1px solid {CachyColors.BORDER_SUBTLE};
}}
QComboBox QAbstractItemView {{
    background-color: {CachyColors.BG_CARD};
    color: {CachyColors.TEXT_PRIMARY};
    selection-background-color: {CachyColors.BG_CARD_HOVER};
    border: 1px solid {CachyColors.BORDER_SUBTLE};
    border-radius: 4px;
    padding: 4px;
}}

/* CheckBoxes */
QCheckBox {{
    color: {CachyColors.TEXT_PRIMARY};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid {CachyColors.BORDER_SUBTLE};
    background-color: {CachyColors.BG_INPUT};
}}
QCheckBox::indicator:hover {{
    border-color: {CachyColors.ACCENT_EMERALD};
}}
QCheckBox::indicator:checked {{
    background-color: {CachyColors.ACCENT_EMERALD};
    border-color: {CachyColors.ACCENT_EMERALD_LIGHT};
    image: url(/usr/share/icons/breeze-dark/actions/16/dialog-ok.svg);
}}

/* Tables */
QTableWidget {{
    background-color: {CachyColors.BG_PANEL};
    border: 1px solid {CachyColors.BORDER_SUBTLE};
    border-radius: 8px;
    gridline-color: {CachyColors.BORDER_SUBTLE};
    color: {CachyColors.TEXT_PRIMARY};
}}
QTableWidget::item {{
    padding: 8px 10px;
    border-bottom: 1px solid {CachyColors.BORDER_SUBTLE};
}}
QTableWidget::item:selected {{
    background-color: rgba(0, 212, 148, 0.15);
    color: {CachyColors.ACCENT_EMERALD_LIGHT};
}}
QHeaderView::section {{
    background-color: {CachyColors.BG_DARKEST};
    color: {CachyColors.TEXT_SECONDARY};
    padding: 8px 10px;
    border: none;
    border-bottom: 2px solid {CachyColors.BORDER_SUBTLE};
    font-weight: 600;
    font-size: 12px;
}}

/* Progress Bar */
QProgressBar {{
    border: 1px solid {CachyColors.BORDER_SUBTLE};
    border-radius: 6px;
    background-color: {CachyColors.BG_INPUT};
    height: 12px;
    text-align: center;
    font-size: 11px;
    color: {CachyColors.TEXT_PRIMARY};
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {CachyColors.ACCENT_EMERALD_DARK},
        stop:1 {CachyColors.ACCENT_EMERALD_LIGHT});
    border-radius: 5px;
}}

/* Badges and Tags */
QLabel.badge-cachy {{
    background-color: rgba(0, 212, 148, 0.15);
    color: {CachyColors.ACCENT_EMERALD};
    border: 1px solid {CachyColors.ACCENT_EMERALD};
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel.badge-aur {{
    background-color: rgba(0, 210, 255, 0.15);
    color: {CachyColors.ACCENT_CYAN};
    border: 1px solid {CachyColors.ACCENT_CYAN};
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel.badge-arch {{
    background-color: rgba(168, 85, 247, 0.15);
    color: {CachyColors.ACCENT_PURPLE};
    border: 1px solid {CachyColors.ACCENT_PURPLE};
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel.badge-warning {{
    background-color: rgba(255, 179, 0, 0.15);
    color: {CachyColors.ACCENT_AMBER};
    border: 1px solid {CachyColors.ACCENT_AMBER};
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}
"""
