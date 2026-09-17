"""
Mirror rating, benchmarking, and configuration module for CachyOS and Arch Linux.
"""
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional, Tuple

from .privilege import elevate_command, get_authenticated_env, run_privileged


@dataclass
class MirrorResult:
    rank: int
    url: str
    country: str
    speed_text: str
    speed_kb: float
    ping_ms: int
    repo_type: str  # 'cachyos' or 'arch'
    active: bool = False


class MirrorRater:
    """Handles mirror ranking, benchmarking, and list updates."""

    PACMAN_D = "/etc/pacman.d"
    ARCH_MIRRORS = "/etc/pacman.d/mirrorlist"
    CACHY_MIRRORS = "/etc/pacman.d/cachyos-mirrorlist"
    CACHY_V3_MIRRORS = "/etc/pacman.d/cachyos-v3-mirrorlist"
    CACHY_V4_MIRRORS = "/etc/pacman.d/cachyos-v4-mirrorlist"

    @staticmethod
    def is_rate_mirrors_available() -> bool:
        return shutil.which("rate-mirrors") is not None

    @staticmethod
    def is_cachyos_rate_mirrors_available() -> bool:
        return shutil.which("cachyos-rate-mirrors") is not None

    @classmethod
    def get_current_active_mirrors(cls) -> dict:
        """Parses currently active (uncommented) servers from pacman mirrorlists."""
        cachy_servers = []
        arch_servers = []
        last_modified = None

        if os.path.exists(cls.CACHY_MIRRORS):
            try:
                mtime = os.path.getmtime(cls.CACHY_MIRRORS)
                last_modified = datetime.fromtimestamp(mtime).strftime("%d.%m.%Y %H:%M")
                with open(cls.CACHY_MIRRORS, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("Server =") or line.startswith("Server="):
                            url = line.split("=", 1)[1].strip()
                            cachy_servers.append(url)
            except Exception:
                pass

        if os.path.exists(cls.ARCH_MIRRORS):
            try:
                with open(cls.ARCH_MIRRORS, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("Server =") or line.startswith("Server="):
                            url = line.split("=", 1)[1].strip()
                            arch_servers.append(url)
            except Exception:
                pass

        return {
            "cachyos": cachy_servers,
            "arch": arch_servers,
            "last_modified": last_modified or "Unbekannt",
            "cachy_primary": cachy_servers[0] if cachy_servers else "Standard-CDN",
            "arch_primary": arch_servers[0] if arch_servers else "Standard-Mirror",
        }

    @staticmethod
    def detect_country_code() -> str:
        """Attempts to detect the user's country code via GeoIP."""
        try:
            res = subprocess.run(
                ["curl", "--connect-timeout", "4", "-sSL", "https://geoip.kde.org/v1/ubiquity"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                match = re.search(r"<CountryCode>([A-Z]{2})</CountryCode>", res.stdout)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return "DE"

    @classmethod
    def benchmark_mirrors(
        cls,
        target: str = "cachyos",
        entry_country: str = "DE",
        max_mirrors: int = 8,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> List[MirrorResult]:
        """
        Runs rate-mirrors in client mode (no root required) to evaluate and rank mirrors.
        target: 'cachyos' or 'arch'
        """
        if not cls.is_rate_mirrors_available():
            if status_callback:
                status_callback("rate-mirrors ist nicht installiert.")
            return []

        cmd = [
            "rate-mirrors",
            "--entry-country", entry_country,
            "--max-mirrors-to-output", str(max_mirrors),
            target,
        ]

        if status_callback:
            status_callback(f"Starte Spiegelserver-Bewertung für '{target.upper()}' (Land: {entry_country})...")

        results: List[MirrorResult] = []
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            current_rank = 1
            # Patterns to parse rate-mirrors output:
            # 1. Results line:
            # #   1. SpeedTestResult { speed: 12.2 MB/s; elapsed: 484ms; connection_time: 49ms } -> https://mirror5.krfoss.org/cachyos/repo/
            # #   3. [SE] SpeedTestResult { speed: 11.8 MB/s; elapsed: 499ms; connection_time: 113ms } -> https://mirror.zyner.org/cachyos/repo/
            result_pattern = re.compile(
                r"#\s+(\d+)\.\s+(?:\[([A-Z]{2})\]\s+)?SpeedTestResult\s*\{\s*speed:\s*([^;]+);\s*elapsed:[^;]+;\s*connection_time:\s*(\d+)ms\s*\}\s*->\s*(https?://[^\s]+)"
            )
            # Intermediate testing lines:
            # # [SE] SpeedTestResult { speed: 11.4 MB/s; elapsed: 519ms; connection_time: 232ms }
            explore_pattern = re.compile(r"#\s+EXPLORING\s+([A-Z]{2})")

            for line in iter(process.stdout.readline, ""):
                line_str = line.strip()
                if not line_str:
                    continue

                if status_callback:
                    if "EXPLORING" in line_str:
                        m = explore_pattern.search(line_str)
                        if m:
                            status_callback(f"Untersuche Region: {m.group(1)}...")
                    elif "RE-TESTING" in line_str:
                        status_callback("Prüfe Top-Spiegelserver erneut auf Stabilität...")
                    elif "TESTING UNLABELED" in line_str:
                        status_callback("Teste weitere globale Spiegelserver...")

                res_match = result_pattern.search(line_str)
                if res_match:
                    rank_str, country, speed_str, ping_str, url = res_match.groups()
                    country = country or cls._extract_country_from_url(url)
                    speed_kb = cls._parse_speed_kb(speed_str)
                    ping_ms = int(ping_str)

                    results.append(
                        MirrorResult(
                            rank=int(rank_str),
                            url=url,
                            country=country,
                            speed_text=speed_str.strip(),
                            speed_kb=speed_kb,
                            ping_ms=ping_ms,
                            repo_type=target,
                            active=(int(rank_str) == 1),
                        )
                    )

            process.wait()
            if status_callback:
                status_callback(f"Bewertung abgeschlossen: {len(results)} Spiegelserver ermittelt.")

        except Exception as e:
            if status_callback:
                status_callback(f"Fehler bei der Spiegelserver-Bewertung: {e}")

        return results

    @classmethod
    def apply_ranking_systemwide(
        cls,
        entry_country: str = "DE",
        line_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[bool, str]:
        """
        Executes cachyos-rate-mirrors via pkexec to re-rank and write all mirrorlists.
        Returns (success: bool, output_summary: str).
        """
        if not cls.is_cachyos_rate_mirrors_available():
            # Fallback if only rate-mirrors is available
            return cls._apply_via_rate_mirrors_direct(entry_country, line_callback)

        env_prefix = f"RATE_MIRRORS_ENTRY_COUNTRY={entry_country}"
        script = f"export {env_prefix} && /usr/bin/cachyos-rate-mirrors"
        cmd = elevate_command(["bash", "-c", script])

        if line_callback:
            line_callback(f"▶ Starte 'cachyos-rate-mirrors' mit Administrator-Rechten (Land: {entry_country})...\n")

        try:
            proc = subprocess.Popen(
                cmd,
                env=get_authenticated_env(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            all_lines = []
            for line in iter(proc.stdout.readline, ""):
                clean_line = line.rstrip()
                all_lines.append(clean_line)
                if line_callback:
                    line_callback(clean_line)

            proc.wait()
            success = (proc.returncode == 0)
            return (success, "\n".join(all_lines))
        except Exception as e:
            msg = f"Fehler bei Ausführung von cachyos-rate-mirrors: {e}"
            if line_callback:
                line_callback(msg)
            return (False, msg)

    @classmethod
    def _apply_via_rate_mirrors_direct(
        cls,
        entry_country: str,
        line_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[bool, str]:
        """Fallback when cachyos-rate-mirrors script is missing but rate-mirrors exists."""
        tmp_cachy = "/tmp/cachyos-mirrorlist.new"
        tmp_arch = "/tmp/mirrorlist.new"

        cmd_str = (
            f"rate-mirrors --entry-country {entry_country} --save {tmp_arch} arch && "
            f"rate-mirrors --entry-country {entry_country} --save {tmp_cachy} cachyos && "
            f"install -m 0644 {tmp_arch} {cls.ARCH_MIRRORS} && "
            f"install -m 0644 {tmp_cachy} {cls.CACHY_MIRRORS} && "
            f"install -m 0644 {tmp_cachy} {cls.CACHY_V3_MIRRORS} && "
            f"install -m 0644 {tmp_cachy} {cls.CACHY_V4_MIRRORS} && "
            f"sed -i 's|/$arch/|/$arch_v3/|g' {cls.CACHY_V3_MIRRORS} && "
            f"sed -i 's|/$arch/|/$arch_v4/|g' {cls.CACHY_V4_MIRRORS}"
        )

        cmd = elevate_command(["bash", "-c", cmd_str])
        try:
            proc = subprocess.Popen(
                cmd,
                env=get_authenticated_env(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            all_lines = []
            for line in iter(proc.stdout.readline, ""):
                clean_line = line.rstrip()
                all_lines.append(clean_line)
                if line_callback:
                    line_callback(clean_line)
            proc.wait()
            return (proc.returncode == 0, "\n".join(all_lines))
        except Exception as e:
            return (False, str(e))

    @staticmethod
    def _parse_speed_kb(speed_str: str) -> float:
        """Converts e.g. '12.2 MB/s' or '750 KB/s' to KB/s float."""
        try:
            parts = speed_str.strip().split()
            if len(parts) >= 2:
                val = float(parts[0])
                unit = parts[1].upper()
                if "MB" in unit:
                    return val * 1024.0
                elif "GB" in unit:
                    return val * 1024.0 * 1024.0
                return val
        except Exception:
            pass
        return 0.0

    @staticmethod
    def _extract_country_from_url(url: str) -> str:
        """Guesses country code from domain TLD if possible."""
        match = re.search(r"https?://(?:[^/]+\.)?([a-z]{2})(?:/|$)", url)
        if match:
            tld = match.group(1).upper()
            if tld not in ("COM", "ORG", "NET", "DEV", "GG", "IO"):
                return tld
        return "GLOBAL"
