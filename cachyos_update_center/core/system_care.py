"""
Post-update maintenance, cache cleaning, orphan removal, and pacnew checks.
"""
import glob
import os
import shutil
import subprocess
from typing import List, Optional, Tuple

from .privilege import elevate_command, get_authenticated_env, run_privileged


class SystemCare:
    """System health and post-update maintenance manager."""

    PACMAN_CACHE_DIR = "/var/cache/pacman/pkg"

    @classmethod
    def get_cache_size(cls) -> str:
        """Returns human-readable size of pacman package cache."""
        if not os.path.exists(cls.PACMAN_CACHE_DIR):
            return "0 MB"
        try:
            res = subprocess.run(
                ["du", "-sh", cls.PACMAN_CACHE_DIR],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Even if returncode != 0 due to some unreadable tmp directories, du still outputs total
            out = res.stdout.strip()
            if out:
                last_line = out.split("\n")[-1]
                parts = last_line.split()
                if parts:
                    return parts[0]
        except Exception:
            pass
        return "ca. 4 GB"


    @classmethod
    def clean_cache(cls, keep: int = 2) -> Tuple[bool, str]:
        """Runs paccache to clean unneeded package versions."""
        if not shutil.which("paccache"):
            # Fallback to pacman -Sc
            cmd = elevate_command(["pacman", "-Sc", "--noconfirm"])
        else:
            cmd = elevate_command(["paccache", f"-rk{keep}"])

        try:
            proc = subprocess.run(
                cmd,
                env=get_authenticated_env(),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return (proc.returncode == 0, proc.stdout or proc.stderr)
        except Exception as e:
            return (False, str(e))

    @classmethod
    def get_orphaned_packages(cls) -> List[str]:
        """Lists unneeded orphaned dependencies via pacman -Qtdq."""
        try:
            res = subprocess.run(
                ["pacman", "-Qtdq"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0 and res.stdout:
                return [p.strip() for p in res.stdout.strip().split("\n") if p.strip()]
        except Exception:
            pass
        return []

    @classmethod
    def remove_orphans(cls, packages: Optional[List[str]] = None) -> Tuple[bool, str]:
        """Removes orphaned packages."""
        if packages is None:
            packages = cls.get_orphaned_packages()

        if not packages:
            return (True, "Keine verwaisten Pakete gefunden.")

        cmd = elevate_command(["pacman", "-Rns", "--noconfirm"] + packages)
        try:
            proc = subprocess.run(
                cmd,
                env=get_authenticated_env(),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return (proc.returncode == 0, proc.stdout or proc.stderr)
        except Exception as e:
            return (False, str(e))

    @classmethod
    def find_pacnew_files(cls) -> List[str]:
        """Finds .pacnew and .pacsave configuration files in /etc."""
        files = []
        try:
            for root, _, filenames in os.walk("/etc"):
                for fn in filenames:
                    if fn.endswith(".pacnew") or fn.endswith(".pacsave"):
                        files.append(os.path.join(root, fn))
        except Exception:
            pass
        return files

    @classmethod
    def check_failed_services(cls) -> List[str]:
        """Checks if any systemd system services are currently failed."""
        try:
            res = subprocess.run(
                ["systemctl", "--failed", "--no-legend", "--plain"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout:
                lines = [l.strip().split()[0] for l in res.stdout.strip().split("\n") if l.strip()]
                return lines
        except Exception:
            pass
        return []
