"""
GitHub Program Updater for CachyOS Update Center.
Checks for updates to the application itself on GitHub and performs direct upgrades.
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt6.QtCore import QThread, pyqtSignal

from .. import __version__

DEFAULT_GITHUB_REPO = "cachyos/cachyos-update-center"
CONFIG_FILE = Path.home() / ".config" / "cachyos-update-center" / "config.json"


def get_repo_dir() -> Path:
    """Returns the root directory of the application repository."""
    return Path(__file__).resolve().parent.parent.parent


def get_github_repo() -> str:
    """Gets the currently configured GitHub repository (owner/repo)."""
    # 1. Check saved config file
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("github_repo"):
                    return cfg["github_repo"]
        except Exception:
            pass

    # 2. Check git remote origin
    repo_dir = get_repo_dir()
    if (repo_dir / ".git").is_dir() and shutil.which("git"):
        try:
            res = subprocess.run(
                ["git", "-C", str(repo_dir), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                url = res.stdout.strip()
                m = re.search(r"github\.com[:/]([^/]+)/([^/\.]+)", url)
                if m:
                    r = f"{m.group(1)}/{m.group(2)}"
                    return r[:-4] if r.endswith(".git") else r
        except Exception:
            pass

    return DEFAULT_GITHUB_REPO


def set_github_repo(repo_str: str) -> None:
    """Saves configured GitHub repository and updates git origin if in git repo."""
    repo_clean = repo_str.strip()
    m = re.search(r"github\.com[:/]([^/]+)/([^/\.]+)", repo_clean)
    if m:
        repo_clean = f"{m.group(1)}/{m.group(2)}"
        if repo_clean.endswith(".git"):
            repo_clean = repo_clean[:-4]

    # Save to config.json
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        data["github_repo"] = repo_clean
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

    # Update git remote if in git repo
    repo_dir = get_repo_dir()
    if (repo_dir / ".git").is_dir() and shutil.which("git") and repo_clean:
        target_url = f"https://github.com/{repo_clean}.git"
        check_rem = subprocess.run(["git", "-C", str(repo_dir), "remote"], capture_output=True, text=True, check=False)
        if "origin" in check_rem.stdout:
            subprocess.run(["git", "-C", str(repo_dir), "remote", "set-url", "origin", target_url], check=False)
        else:
            subprocess.run(["git", "-C", str(repo_dir), "remote", "add", "origin", target_url], check=False)


def compare_versions(v1: str, v2: str) -> int:
    """Uses vercmp if available, else numeric fallback."""
    v1_clean = v1.lstrip("v").strip()
    v2_clean = v2.lstrip("v").strip()

    if shutil.which("vercmp"):
        try:
            res = subprocess.run(["vercmp", v1_clean, v2_clean], capture_output=True, text=True, check=False)
            return int(res.stdout.strip())
        except Exception:
            pass

    parts1 = [int(p) for p in re.findall(r"\d+", v1_clean)]
    parts2 = [int(p) for p in re.findall(r"\d+", v2_clean)]
    return (parts1 > parts2) - (parts1 < parts2)


@dataclass
class GitHubUpdateInfo:
    installed_version: str = __version__
    remote_version: str = "Unbekannt"
    has_update: bool = False
    github_repo: str = DEFAULT_GITHUB_REPO
    release_url: str = ""
    release_notes: str = ""
    tarball_url: str = ""
    checked_at: Optional[datetime.datetime] = None
    check_error: Optional[str] = None


class GitHubUpdateCheckerWorker(QThread):
    """Background worker that queries the GitHub API for latest releases or tags."""
    finished = pyqtSignal(GitHubUpdateInfo)

    def run(self):
        info = GitHubUpdateInfo()
        info.installed_version = __version__
        info.checked_at = datetime.datetime.now()
        repo = get_github_repo()
        info.github_repo = repo

        try:
            # 1. Check GitHub Releases API
            url = f"https://api.github.com/repos/{repo}/releases/latest"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": f"CachyOS-Update-Center/{info.installed_version}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    tag = data.get("tag_name", "").lstrip("v").strip()
                    if tag:
                        info.remote_version = tag
                        info.release_url = data.get("html_url", "")
                        info.release_notes = data.get("body", "")
                        for asset in data.get("assets", []):
                            if asset.get("name", "").endswith((".tar.gz", ".zip")):
                                info.tarball_url = asset.get("browser_download_url", "")
                                break

        except urllib.error.HTTPError as e:
            if e.code == 404:
                # No release published yet, check tags or commits
                info = self._fallback_check_tags(info, repo)
            else:
                info.check_error = f"GitHub API Fehler ({e.code}): {e.reason}"
                info.remote_version = info.installed_version
        except Exception as exc:
            info.check_error = f"Verbindung zu GitHub nicht möglich: {exc}"
            info.remote_version = info.installed_version

        # Compare versions
        if info.installed_version and info.remote_version and info.remote_version != "Unbekannt":
            cmp_res = compare_versions(info.installed_version, info.remote_version)
            info.has_update = cmp_res < 0

        self.finished.emit(info)

    def _fallback_check_tags(self, info: GitHubUpdateInfo, repo: str) -> GitHubUpdateInfo:
        """Fallback to check tags if no release exists."""
        try:
            url = f"https://api.github.com/repos/{repo}/tags"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": f"CachyOS-Update-Center/{info.installed_version}"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    tags = json.loads(resp.read().decode("utf-8"))
                    if tags and isinstance(tags, list):
                        latest_tag = tags[0].get("name", "").lstrip("v").strip()
                        if latest_tag:
                            info.remote_version = latest_tag
                            info.release_url = f"https://github.com/{repo}/releases/tag/v{latest_tag}"
                            info.release_notes = f"Tag v{latest_tag} auf GitHub verfügbar."
                            return info
        except Exception:
            pass
        info.remote_version = info.installed_version
        return info


@dataclass
class UpdateStep:
    name: str
    command: List[str]
    description: str


class GitHubUpdateExecWorker(QThread):
    """Executes update steps with real-time log output."""
    step_started = pyqtSignal(int, int, str)  # current, total, name
    output_line = pyqtSignal(str)
    completed = pyqtSignal(bool, str)

    def __init__(self, steps: List[UpdateStep]):
        super().__init__()
        self.steps = steps
        self.process: Optional[subprocess.Popen] = None
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass

    def run(self):
        total = len(self.steps)
        if total == 0:
            self.completed.emit(True, "Keine Schritte auszuführen.")
            return

        for idx, step in enumerate(self.steps, start=1):
            if self._is_cancelled:
                self.output_line.emit("\n[!] Vorgang vom Benutzer abgebrochen.")
                self.completed.emit(False, "Aktualisierung abgebrochen.")
                return

            self.step_started.emit(idx, total, step.name)
            self.output_line.emit("==================================================")
            self.output_line.emit(f"[{idx}/{total}] {step.name}")
            self.output_line.emit(f"Befehl: {' '.join(step.command)}")
            self.output_line.emit("==================================================\n")

            try:
                self.process = subprocess.Popen(
                    step.command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                )

                if self.process.stdout:
                    for line in iter(self.process.stdout.readline, ""):
                        if self._is_cancelled:
                            break
                        self.output_line.emit(line.rstrip())

                self.process.wait()
                ret = self.process.returncode if self.process else 1

                if ret != 0:
                    self.output_line.emit(f"\n❌ Schritt '{step.name}' mit Fehlercode {ret} beendet.")
                    self.completed.emit(False, f"Fehler bei Schritt '{step.name}' (Code {ret})")
                    return
                else:
                    self.output_line.emit(f"\n✅ Schritt '{step.name}' erfolgreich abgeschlossen.\n")

            except Exception as e:
                self.output_line.emit(f"\n❌ Fehler bei Ausführung: {e}")
                self.completed.emit(False, str(e))
                return

        self.completed.emit(True, "CachyOS Update Center wurde erfolgreich auf die neueste Version aktualisiert!")
