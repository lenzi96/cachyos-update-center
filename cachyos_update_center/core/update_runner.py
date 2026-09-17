"""
Background update execution pipeline with real-time log streaming and phase tracking.
Always supports prior mirror rating (Spiegelserver-Bewertung).
"""
import os
import shutil
import subprocess
import time
from typing import List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from .mirror_rater import MirrorRater
from .online_issue_checker import OnlineIssueChecker
from .package_checker import PackageChecker
from .privilege import elevate_command
from .snapper_helper import SnapperHelper
from .system_care import SystemCare


class UpdatePipelineWorker(QThread):
    """
    Executes the 4-step update sequence:
    1. Mirror Rating & Application (Spiegelserver-Bewertung)
    2. BTRFS / Snapper Safety Snapshot
    3. Online Issue Checking & Auto-Exclusion + Package Update (Pacman / AUR / Flatpak)
    4. Post-Update Care & Reboot Check
    """

    step_started = pyqtSignal(int, str)       # step_index (0..3), step_title
    step_completed = pyqtSignal(int, bool)     # step_index, success
    progress_percent = pyqtSignal(int)         # 0..100
    terminal_line = pyqtSignal(str)            # text line
    pipeline_finished = pyqtSignal(bool, str)  # overall_success, summary_msg
    reboot_advised = pyqtSignal(bool)          # True if reboot recommended

    def __init__(
        self,
        rate_mirrors_first: bool = True,
        create_snapshot: bool = True,
        include_aur: bool = True,
        entry_country: str = "DE",
        selected_packages: Optional[List[str]] = None,
        clean_cache_after: bool = True,
        auto_exclude_issues: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.rate_mirrors_first = rate_mirrors_first
        self.create_snapshot = create_snapshot
        self.include_aur = include_aur
        self.entry_country = entry_country
        self.selected_packages = selected_packages
        self.clean_cache_after = clean_cache_after
        self.auto_exclude_issues = auto_exclude_issues
        self._is_cancelled = False
        self._current_process: Optional[subprocess.Popen] = None


    def cancel(self):
        """Requests cancellation of running pipeline."""
        self._is_cancelled = True
        if self._current_process and self._current_process.poll() is None:
            try:
                self._current_process.terminate()
            except Exception:
                pass

    def run(self):
        overall_success = True
        summary_lines = []

        self.terminal_line.emit("🚀 Starte CachyOS Update-Pipeline...\n")
        self.progress_percent.emit(5)

        # ----------------------------------------------------------------------
        # PHASE 1: Spiegelserver-Bewertung (immer vorher oder optional)
        # ----------------------------------------------------------------------
        self.step_started.emit(0, "Spiegelserver bewerten & optimieren")
        if self.rate_mirrors_first:
            self.terminal_line.emit("==================================================")
            self.terminal_line.emit(f"⚡ PHASE 1: Spiegelserver-Bewertung (Land: {self.entry_country})")
            self.terminal_line.emit("==================================================")

            ok, output = MirrorRater.apply_ranking_systemwide(
                entry_country=self.entry_country,
                line_callback=lambda l: self.terminal_line.emit(l),
            )
            self.step_completed.emit(0, ok)
            if not ok:
                self.terminal_line.emit("⚠️ Hinweis: Spiegelserver-Bewertung meldete Fehler oder wurde abgebrochen. Fahre mit bestehenden Spiegelservern fort.")
            else:
                self.terminal_line.emit("✅ Spiegelserver erfolgreich bewertet und in pacman.d aktualisiert.\n")
        else:
            self.terminal_line.emit("ℹ️ Spiegelserver-Bewertung übersprungen (in Optionen deaktiviert).\n")
            self.step_completed.emit(0, True)

        self.progress_percent.emit(25)
        if self._is_cancelled:
            self.pipeline_finished.emit(False, "Aktualisierung vom Benutzer abgebrochen.")
            return

        # ----------------------------------------------------------------------
        # PHASE 2: BTRFS Snapper Snapshot
        # ----------------------------------------------------------------------
        self.step_started.emit(1, "System-Wiederherstellungspunkt erstellen")
        if self.create_snapshot and SnapperHelper.is_available() and SnapperHelper.has_root_config():
            self.terminal_line.emit("==================================================")
            self.terminal_line.emit("📸 PHASE 2: BTRFS Snapper-Snapshot anlegen")
            self.terminal_line.emit("==================================================")
            self.terminal_line.emit("Erstelle Root-Snapshot als Ausfallsicherung...")

            ok, msg = SnapperHelper.create_pre_update_snapshot("CachyOS Update Center Vor-Update-Sicherung")
            self.terminal_line.emit(msg + "\n")
            self.step_completed.emit(1, ok)
        else:
            self.terminal_line.emit("ℹ️ Snapper Snapshot übersprungen (nicht konfiguriert oder deaktiviert).\n")
            self.step_completed.emit(1, True)

        self.progress_percent.emit(45)
        if self._is_cancelled:
            self.pipeline_finished.emit(False, "Aktualisierung vom Benutzer abgebrochen.")
            return

        # ----------------------------------------------------------------------
        # PHASE 3: Paket-Update (Pacman / AUR) mit Online-Problemprüfung
        # ----------------------------------------------------------------------
        self.step_started.emit(2, "Pakete prüfen, filtern & aktualisieren")
        self.terminal_line.emit("==================================================")
        self.terminal_line.emit("📦 PHASE 3: System-Paketaktualisierung & Online-Prüfung")
        self.terminal_line.emit("==================================================")

        # Online Issue Checking & Auto-Exclusion
        ignore_flags: List[str] = []
        if self.auto_exclude_issues:
            self.terminal_line.emit("🔍 Prüfe ausstehende Pakete online auf gemeldete Fehler & manuelle Eingriffe...")

            # Determine candidate packages
            candidate_names = list(self.selected_packages) if self.selected_packages else []
            if not candidate_names:
                # Fetch current updates to get package list
                pending_official = PackageChecker.check_official_updates()
                candidate_names = [p.name for p in pending_official]

            issues = OnlineIssueChecker.check_packages(candidate_names)
            critical_issues = {p: rep for p, rep in issues.items() if rep.auto_exclude}
            if critical_issues:
                self.terminal_line.emit(f"⚠️ {len(critical_issues)} Paket(e) mit bekannten Online-Problemen/Interventionen erkannt:")
                excluded_names = []
                for pkg_name, rep in critical_issues.items():
                    self.terminal_line.emit(f"   ➔ '{pkg_name}': {rep.title} ({rep.source})")
                    self.terminal_line.emit(f"     Grund: {rep.reason}")
                    self.terminal_line.emit(f"     🛡️ Automatisch ausgeschlossen (--ignore {pkg_name})")
                    excluded_names.append(pkg_name)

                if self.selected_packages:
                    # Filter out from selected packages
                    self.selected_packages = [p for p in self.selected_packages if p not in excluded_names]
                    if not self.selected_packages:
                        self.terminal_line.emit("\nℹ️ Alle gewählten Pakete wurden wegen Online-Problemen ausgeschlossen. Kein Update erforderlich.")
                        self.step_completed.emit(2, True)
                        self.progress_percent.emit(85)
                        # Jump to phase 4
                        return

                # Build --ignore argument
                ignore_flags = ["--ignore", ",".join(excluded_names)]
            else:
                self.terminal_line.emit("✅ Online-Prüfung ergab keine bekannten kritischen Probleme für die anstehenden Pakete.\n")

        # Decide update command
        if self.include_aur and shutil.which("yay"):
            self.terminal_line.emit("Verwende yay für offizielle Repositorien und AUR...\n")
            if self.selected_packages:
                update_cmd = ["yay", "-S", "--noconfirm", "--needed"] + self.selected_packages
            else:
                update_cmd = ["yay", "-Syu", "--noconfirm", "--needed"] + ignore_flags
        else:
            self.terminal_line.emit("Verwende pacman mit Polkit-Autorisierung...\n")
            if self.selected_packages:
                update_cmd = elevate_command(["pacman", "-S", "--noconfirm", "--needed"] + self.selected_packages)
            else:
                update_cmd = elevate_command(["pacman", "-Syu", "--noconfirm", "--needed"] + ignore_flags)

        update_ok = self._run_process_stream(update_cmd)
        self.step_completed.emit(2, update_ok)
        if not update_ok:
            overall_success = False
            self.terminal_line.emit("\n❌ Fehler während der Paketaktualisierung aufgetreten!\n")
        else:
            self.terminal_line.emit("\n✅ Paketaktualisierung erfolgreich abgeschlossen.\n")


        self.progress_percent.emit(85)
        if self._is_cancelled:
            self.pipeline_finished.emit(False, "Aktualisierung vom Benutzer abgebrochen.")
            return

        # ----------------------------------------------------------------------
        # PHASE 4: Post-Update Wartung & Systempflege
        # ----------------------------------------------------------------------
        self.step_started.emit(3, "Post-Update Wartung & Systemprüfung")
        self.terminal_line.emit("==================================================")
        self.terminal_line.emit("🧹 PHASE 4: Nachbereitung & Systemgesundheit")
        self.terminal_line.emit("==================================================")

        # Cache cleanup
        if self.clean_cache_after:
            self.terminal_line.emit("Bereinige ältere Paket-Cache-Versionen...")
            c_ok, c_msg = SystemCare.clean_cache(keep=2)
            if c_ok:
                self.terminal_line.emit("Cache erfolgreich bereinigt.")
            else:
                self.terminal_line.emit(f"Hinweis bei Cache-Bereinigung: {c_msg}")

        # Check for pacnew files
        pacnews = SystemCare.find_pacnew_files()
        if pacnews:
            self.terminal_line.emit(f"⚠️ Hinweis: {len(pacnews)} .pacnew/.pacsave Konfigurationsdateien gefunden.")

        # Check kernel reboot requirement
        needs_reboot = PackageChecker.is_kernel_reboot_required()
        if needs_reboot:
            self.terminal_line.emit("\n🔄 WICHTIG: Ein neuer Kernel wurde installiert. Ein Neustart wird empfohlen.")
            self.reboot_advised.emit(True)
        else:
            self.terminal_line.emit("Systemdienste und Kernel laufen einwandfrei.")
            self.reboot_advised.emit(False)

        self.step_completed.emit(3, True)
        self.progress_percent.emit(100)

        status_msg = "Systemaktualisierung erfolgreich abgeschlossen!" if overall_success else "Aktualisierung mit Fehlern beendet."
        self.terminal_line.emit(f"\n🎉 {status_msg}")
        self.pipeline_finished.emit(overall_success, status_msg)

    def _run_process_stream(self, cmd: List[str]) -> bool:
        """Executes command and streams its stdout/stderr to terminal_line signal."""
        try:
            self._current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            for line in iter(self._current_process.stdout.readline, ""):
                if self._is_cancelled:
                    break
                self.terminal_line.emit(line.rstrip())

            self._current_process.wait()
            ret = self._current_process.returncode
            self._current_process = None
            return ret == 0
        except Exception as e:
            self.terminal_line.emit(f"Ausführungsfehler: {e}")
            return False
