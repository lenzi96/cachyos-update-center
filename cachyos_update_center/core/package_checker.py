"""
Package check and inspection module for CachyOS, Arch repos, and AUR.
"""
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class PackageUpdate:
    name: str
    current_version: str
    new_version: str
    repo: str
    size_text: str = ""
    description: str = ""
    is_cachyos: bool = False
    is_kernel: bool = False
    is_aur: bool = False
    is_selected: bool = True
    has_online_issue: bool = False
    issue_reason: str = ""
    issue_url: str = ""
    is_auto_excluded: bool = False



class PackageChecker:
    """Detects available updates across official repos, CachyOS, AUR, and Flatpak."""

    @staticmethod
    def get_running_kernel() -> str:
        """Returns currently active running kernel release."""
        try:
            return os.uname().release
        except Exception:
            return "Unbekannt"

    @classmethod
    def is_kernel_reboot_required(cls) -> bool:
        """
        Checks if the currently running kernel version matches
        the modules installed in /usr/lib/modules/.
        """
        running = cls.get_running_kernel()
        modules_dir = f"/usr/lib/modules/{running}"
        # If the directory for the running kernel was removed or replaced by an update
        if not os.path.isdir(modules_dir):
            return True
        return False

    @staticmethod
    def check_official_updates() -> List[PackageUpdate]:
        """
        Uses checkupdates to discover pending Pacman / CachyOS updates.
        Format of checkupdates: 'pkgname old_ver -> new_ver'
        """
        updates: List[PackageUpdate] = []
        if not shutil.which("checkupdates"):
            return updates

        try:
            proc = subprocess.run(
                ["checkupdates"],
                capture_output=True,
                text=True,
                timeout=45,
            )
            if proc.returncode != 0 and not proc.stdout:
                return updates

            # Collect package names to batch query repo info
            lines = [line.strip() for line in proc.stdout.strip().split("\n") if line.strip()]
            package_names = []
            parsed_rows = []
            for line in lines:
                parts = line.split()
                # Expected: [pkgname, old_version, "->", new_version]
                if len(parts) >= 4 and parts[2] == "->":
                    name = parts[0]
                    old_ver = parts[1]
                    new_ver = parts[3]
                    package_names.append(name)
                    parsed_rows.append((name, old_ver, new_ver))

            # Batch query repo and description via pacman -Si
            repo_map = PackageChecker._fetch_repo_metadata(package_names)

            for name, old_ver, new_ver in parsed_rows:
                info = repo_map.get(name, {})
                repo = info.get("repo", "System")
                desc = info.get("desc", "")
                size = info.get("size", "")

                is_cachy = "cachyos" in repo.lower() or "cachyos" in name.lower()
                is_kern = "linux" in name.lower() or "kernel" in name.lower() or "ucode" in name.lower()

                updates.append(
                    PackageUpdate(
                        name=name,
                        current_version=old_ver,
                        new_version=new_ver,
                        repo=repo,
                        size_text=size,
                        description=desc,
                        is_cachyos=is_cachy,
                        is_kernel=is_kern,
                        is_aur=False,
                        is_selected=True,
                    )
                )
        except Exception:
            pass

        return updates

    @staticmethod
    def check_aur_updates() -> List[PackageUpdate]:
        """Uses yay to check for AUR updates."""
        updates: List[PackageUpdate] = []
        if not shutil.which("yay"):
            return updates

        try:
            proc = subprocess.run(
                ["yay", "-Qua"],
                capture_output=True,
                text=True,
                timeout=45,
            )
            if proc.returncode != 0 and not proc.stdout:
                return updates

            for line in proc.stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                # Format: pkgname old_ver -> new_ver
                if len(parts) >= 4 and parts[2] == "->":
                    name = parts[0]
                    old_ver = parts[1]
                    new_ver = parts[3]
                    is_cachy = "cachyos" in name.lower()
                    is_kern = "linux" in name.lower() or "kernel" in name.lower()

                    updates.append(
                        PackageUpdate(
                            name=name,
                            current_version=old_ver,
                            new_version=new_ver,
                            repo="AUR",
                            size_text="",
                            description="AUR Community Paket",
                            is_cachyos=is_cachy,
                            is_kernel=is_kern,
                            is_aur=True,
                            is_selected=True,
                        )
                    )
        except Exception:
            pass

        return updates

    @staticmethod
    def check_flatpak_updates() -> List[PackageUpdate]:
        """Checks for Flatpak updates if flatpak command is present."""
        updates: List[PackageUpdate] = []
        if not shutil.which("flatpak"):
            return updates

        try:
            proc = subprocess.run(
                ["flatpak", "remote-ls", "--updates", "--columns=name,application,version,branch"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode == 0 and proc.stdout:
                for line in proc.stdout.strip().split("\n"):
                    parts = line.strip().split("\t")
                    if len(parts) >= 2:
                        name = parts[0].strip()
                        app_id = parts[1].strip()
                        ver = parts[2].strip() if len(parts) > 2 else "latest"
                        updates.append(
                            PackageUpdate(
                                name=name or app_id,
                                current_version="Installiert",
                                new_version=ver,
                                repo="Flatpak",
                                size_text="",
                                description=app_id,
                                is_cachyos=False,
                                is_kernel=False,
                                is_aur=False,
                                is_selected=True,
                            )
                        )
        except Exception:
            pass

        return updates

    @staticmethod
    def _fetch_repo_metadata(pkg_names: List[str]) -> Dict[str, dict]:
        """Queries pacman -Si for a list of packages to discover repository and download size."""
        if not pkg_names:
            return {}

        res_dict = {}
        try:
            # Query in batches of 50 to avoid shell limit
            for i in range(0, len(pkg_names), 50):
                batch = pkg_names[i : i + 50]
                proc = subprocess.run(
                    ["pacman", "-Si"] + batch,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                if proc.returncode == 0 and proc.stdout:
                    cur_name = ""
                    cur_repo = ""
                    cur_desc = ""
                    cur_size = ""

                    for line in proc.stdout.split("\n"):
                        line = line.strip()
                        if line.startswith("Repository") or line.startswith("Repositorium"):
                            cur_repo = line.split(":", 1)[1].strip()
                        elif line.startswith("Name"):
                            cur_name = line.split(":", 1)[1].strip()
                        elif line.startswith("Description") or line.startswith("Beschreibung"):
                            cur_desc = line.split(":", 1)[1].strip()
                        elif line.startswith("Download Size") or line.startswith("Download-Größe"):
                            cur_size = line.split(":", 1)[1].strip()
                        elif not line and cur_name:
                            res_dict[cur_name] = {
                                "repo": cur_repo,
                                "desc": cur_desc,
                                "size": cur_size,
                            }
                            cur_name = ""
                            cur_repo = ""
                            cur_desc = ""
                            cur_size = ""
                    if cur_name:
                        res_dict[cur_name] = {
                            "repo": cur_repo,
                            "desc": cur_desc,
                            "size": cur_size,
                        }
        except Exception:
            pass

        return res_dict
