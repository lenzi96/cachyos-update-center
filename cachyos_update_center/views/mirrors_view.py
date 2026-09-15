"""
Mirrors View: Dedicated mirror ranking, latency benchmarking, and pacman configuration.
"""
from typing import List
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core.mirror_rater import MirrorRater, MirrorResult
from ..styles import CachyColors
from ..widgets.mirror_card import MirrorCard


class MirrorBenchmarkWorker(QThread):
    """Background worker for non-blocking mirror benchmarking."""
    status_updated = pyqtSignal(str)
    benchmark_finished = pyqtSignal(list)

    def __init__(self, target: str, country: str, max_mirrors: int, parent=None):
        super().__init__(parent)
        self.target = target
        self.country = country
        self.max_mirrors = max_mirrors

    def run(self):
        results = MirrorRater.benchmark_mirrors(
            target=self.target,
            entry_country=self.country,
            max_mirrors=self.max_mirrors,
            status_callback=lambda s: self.status_updated.emit(s),
        )
        self.benchmark_finished.emit(results)


class MirrorApplyWorker(QThread):
    """Background worker for applying mirror ranking via pkexec."""
    log_line = pyqtSignal(str)
    apply_finished = pyqtSignal(bool, str)

    def __init__(self, country: str, parent=None):
        super().__init__(parent)
        self.country = country

    def run(self):
        ok, out = MirrorRater.apply_ranking_systemwide(
            entry_country=self.country,
            line_callback=lambda l: self.log_line.emit(l),
        )
        self.apply_finished.emit(ok, out)


class MirrorsView(QWidget):
    """Mirror ranking and rating configuration view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.benchmark_worker: MirrorBenchmarkWorker = None
        self.apply_worker: MirrorApplyWorker = None
        self.init_ui()
        self.load_current_status()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # ----------------------------------------------------------------------
        # Top Control Card
        # ----------------------------------------------------------------------
        control_card = QFrame()
        control_card.setObjectName("controlCard")
        cc_layout = QVBoxLayout(control_card)
        cc_layout.setContentsMargins(18, 16, 18, 16)
        cc_layout.setSpacing(14)

        # Title & Subtitle
        header_row = QHBoxLayout()
        icon_lbl = QLabel("🌐")
        icon_lbl.setStyleSheet("font-size: 24px;")
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        title_lbl = QLabel("CachyOS & Arch Linux Spiegelserver-Bewertung")
        title_lbl.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {CachyColors.TEXT_PRIMARY};")
        desc_lbl = QLabel("Ermittelt automatisch die schnellsten und latenzärmsten Server für maximale Download-Raten.")
        desc_lbl.setStyleSheet(f"font-size: 12px; color: {CachyColors.TEXT_SECONDARY};")
        header_text.addWidget(title_lbl)
        header_text.addWidget(desc_lbl)
        header_row.addWidget(icon_lbl)
        header_row.addLayout(header_text, 1)
        cc_layout.addLayout(header_row)

        # Settings row for inputs
        settings_row = QHBoxLayout()
        settings_row.setSpacing(16)

        # Country
        c_layout = QVBoxLayout()
        c_layout.setSpacing(4)
        c_title = QLabel("Startland (Geo-Ping):")
        c_title.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {CachyColors.TEXT_MUTED};")
        self.combo_country = QComboBox()
        self.combo_country.addItem("Deutschland (DE)", "DE")
        self.combo_country.addItem("Österreich (AT)", "AT")
        self.combo_country.addItem("Schweiz (CH)", "CH")
        self.combo_country.addItem("Automatisch (GeoIP)", "AUTO")
        self.combo_country.addItem("Weltweit (Global)", "US")
        c_layout.addWidget(c_title)
        c_layout.addWidget(self.combo_country)
        settings_row.addLayout(c_layout, 1)

        # Target repo
        t_layout = QVBoxLayout()
        t_layout.setSpacing(4)
        t_title = QLabel("Zu bewertendes Repositorium:")
        t_title.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {CachyColors.TEXT_MUTED};")
        self.combo_target = QComboBox()
        self.combo_target.addItem("CachyOS Repositorien (x86-64-v3/v4)", "cachyos")
        self.combo_target.addItem("Arch Linux Repositorien", "arch")
        t_layout.addWidget(t_title)
        t_layout.addWidget(self.combo_target)
        settings_row.addLayout(t_layout, 1)

        # Count
        num_layout = QVBoxLayout()
        num_layout.setSpacing(4)
        num_title = QLabel("Max. Server:")
        num_title.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {CachyColors.TEXT_MUTED};")
        self.spin_count = QSpinBox()
        self.spin_count.setRange(3, 20)
        self.spin_count.setValue(8)
        num_layout.addWidget(num_title)
        num_layout.addWidget(self.spin_count)
        settings_row.addLayout(num_layout)

        cc_layout.addLayout(settings_row)

        # Dedicated action buttons row
        btn_box = QHBoxLayout()
        btn_box.setSpacing(12)

        self.btn_benchmark = QPushButton("  ⚡ Spiegelserver bewerten (Benchmark)")
        self.btn_benchmark.setIcon(QIcon.fromTheme("system-run"))
        self.btn_benchmark.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_benchmark.clicked.connect(self.start_benchmark)

        self.btn_apply = QPushButton("  💾 Als System-Spiegelserver anwenden")
        self.btn_apply.setProperty("class", "btn-primary")
        self.btn_apply.setIcon(QIcon.fromTheme("document-save"))
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.clicked.connect(self.start_apply_mirrors)

        btn_box.addWidget(self.btn_benchmark)
        btn_box.addWidget(self.btn_apply)
        btn_box.addStretch()

        cc_layout.addLayout(btn_box)


        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        cc_layout.addWidget(self.progress_bar)

        # Status text
        self.status_lbl = QLabel("Bereit für die Spiegelserver-Bewertung.")
        self.status_lbl.setStyleSheet(f"font-size: 12px; color: {CachyColors.TEXT_MUTED};")
        cc_layout.addWidget(self.status_lbl)

        control_card.setStyleSheet(f"""
            QFrame#controlCard {{
                background-color: {CachyColors.BG_CARD};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 10px;
            }}
        """)
        main_layout.addWidget(control_card)

        # ----------------------------------------------------------------------
        # Current Active Mirror Status Pill
        # ----------------------------------------------------------------------
        self.current_pill = QFrame()
        cp_layout = QHBoxLayout(self.current_pill)
        cp_layout.setContentsMargins(14, 10, 14, 10)
        cp_layout.setSpacing(10)

        cp_icon = QLabel("📌")
        self.cp_text = QLabel("Aktueller Haupt-Server: Wird geladen...")
        self.cp_text.setStyleSheet(f"font-size: 12px; color: {CachyColors.TEXT_SECONDARY};")
        cp_layout.addWidget(cp_icon)
        cp_layout.addWidget(self.cp_text, 1)

        self.current_pill.setStyleSheet(f"""
            QFrame {{
                background-color: {CachyColors.BG_PANEL};
                border: 1px solid {CachyColors.BORDER_SUBTLE};
                border-radius: 8px;
            }}
        """)
        main_layout.addWidget(self.current_pill)

        # ----------------------------------------------------------------------
        # Results Scroll Area
        # ----------------------------------------------------------------------
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(10)
        self.results_layout.addStretch()

        self.scroll_area.setWidget(self.results_container)
        main_layout.addWidget(self.scroll_area, 1)

    def load_current_status(self):
        """Loads current pacman mirror status into view."""
        info = MirrorRater.get_current_active_mirrors()
        cachy_p = info.get("cachy_primary", "Standard")
        mtime = info.get("last_modified", "Unbekannt")
        self.cp_text.setText(f"Aktiver CachyOS-Server: {cachy_p}  |  Letzte Aktualisierung: {mtime}")

    def start_benchmark(self):
        """Launches benchmark in background thread."""
        target = self.combo_target.currentData()
        country = self.combo_country.currentData()
        if country == "AUTO":
            country = MirrorRater.detect_country_code()
        max_m = self.spin_count.value()

        self.btn_benchmark.setEnabled(False)
        self.btn_apply.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_lbl.setText("Bewertung gestartet...")

        # Clear previous results
        for i in reversed(range(self.results_layout.count() - 1)):
            widget = self.results_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        self.benchmark_worker = MirrorBenchmarkWorker(target, country, max_m)
        self.benchmark_worker.status_updated.connect(self._on_status_updated)
        self.benchmark_worker.benchmark_finished.connect(self._on_benchmark_finished)
        self.benchmark_worker.start()

    def _on_status_updated(self, text: str):
        self.status_lbl.setText(text)

    def _on_benchmark_finished(self, results: List[MirrorResult]):
        self.btn_benchmark.setEnabled(True)
        self.btn_apply.setEnabled(True)
        self.progress_bar.setVisible(False)

        if not results:
            self.status_lbl.setText("Keine Ergebnisse ermittelt oder Verbindungstest fehlgeschlagen.")
            return

        self.status_lbl.setText(f"Bewertung abgeschlossen: {len(results)} Spiegelserver nach Latenz und Durchsatz sortiert.")

        # Insert cards before the stretch item
        for m in results:
            card = MirrorCard(m)
            self.results_layout.insertWidget(self.results_layout.count() - 1, card)

    def start_apply_mirrors(self):
        """Applies mirrors system-wide via pkexec."""
        country = self.combo_country.currentData()
        if country == "AUTO":
            country = MirrorRater.detect_country_code()

        self.btn_benchmark.setEnabled(False)
        self.btn_apply.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_lbl.setText("Schreibe Spiegelserver über Polkit in /etc/pacman.d/...")

        self.apply_worker = MirrorApplyWorker(country)
        self.apply_worker.log_line.connect(lambda l: self.status_lbl.setText(l))
        self.apply_worker.apply_finished.connect(self._on_apply_finished)
        self.apply_worker.start()

    def _on_apply_finished(self, success: bool, output: str):
        self.btn_benchmark.setEnabled(True)
        self.btn_apply.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.load_current_status()

        if success:
            QMessageBox.information(
                self,
                "Spiegelserver aktualisiert",
                "Die Spiegelserver wurden erfolgreich bewertet und systemweit in /etc/pacman.d/ eingetragen!",
            )
            self.status_lbl.setText("Spiegelserver erfolgreich im System angewendet.")
        else:
            QMessageBox.warning(
                self,
                "Fehler beim Anwenden",
                f"Spiegelserver konnten nicht gespeichert werden:\n{output[:300]}",
            )
            self.status_lbl.setText("Fehler beim Anwenden der Spiegelserver.")
