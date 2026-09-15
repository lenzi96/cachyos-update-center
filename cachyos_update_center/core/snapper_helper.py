"""
BTRFS Snapper snapshot integration for CachyOS Update Center.
Provides automatic pre-update system restore snapshots.
"""
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .privilege import elevate_command, run_privileged


@dataclass
class SnapshotEntry:
    num: int
    type_str: str
    date_str: str
    user: str
    description: str


class SnapperHelper:
    """Manages BTRFS system restore points via Snapper."""

    @staticmethod
    def is_available() -> bool:
        """Checks if snapper is installed and executable."""
        return shutil.which("snapper") is not None

    @classmethod
    def has_root_config(cls) -> bool:
        """Checks if a 'root' snapper configuration exists."""
        if not cls.is_available():
            return False
        try:
            res = subprocess.run(
                ["snapper", "list-configs"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return "root" in res.stdout
        except Exception:
            return False

    @classmethod
    def create_pre_update_snapshot(cls, description: str = "Vor CachyOS Systemaktualisierung") -> Tuple[bool, str]:
        """
        Creates a pre-update snapshot using pkexec snapper.
        Returns (success, message_or_snapshot_id).
        """
        if not cls.is_available() or not cls.has_root_config():
            return (False, "Snapper ist nicht konfiguriert oder nicht verfügbar.")

        cmd = elevate_command([
            "snapper", "-c", "root", "create",
            "-d", description,
            "-t", "single",
            "-c", "timeline",
        ])

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=20,
            )
            if proc.returncode == 0:
                return (True, f"Wiederherstellungs-Snapshot erfolgreich erstellt: '{description}'")
            return (False, f"Snapshot-Erstellung fehlgeschlagen: {proc.stderr.strip()}")
        except Exception as e:
            return (False, f"Fehler bei Snapshot-Erstellung: {e}")

    @classmethod
    def list_recent_snapshots(cls, max_count: int = 8) -> List[SnapshotEntry]:
        """Retrieves recent root snapshots for display."""
        if not cls.is_available() or not cls.has_root_config():
            return []

        snapshots: List[SnapshotEntry] = []
        try:
            cmd = elevate_command(["snapper", "-c", "root", "list"])
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode != 0:
                return []

            lines = proc.stdout.strip().split("\n")
            # Skip header line(s)
            for line in lines:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 6 and parts[0].isdigit():
                    num = int(parts[0])
                    type_str = parts[1]
                    date_str = parts[3]
                    user = parts[4]
                    desc = parts[6] if len(parts) > 6 else parts[5]

                    snapshots.append(
                        SnapshotEntry(
                            num=num,
                            type_str=type_str,
                            date_str=date_str,
                            user=user,
                            description=desc,
                        )
                    )
            # Return most recent first
            snapshots.reverse()
            return snapshots[:max_count]
        except Exception:
            return []
