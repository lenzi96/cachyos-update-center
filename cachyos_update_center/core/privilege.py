"""
Privilege escalation handler using Polkit (pkexec) or sudo.
"""
import os
import shutil
import subprocess
from typing import List, Tuple, Optional


def is_root() -> bool:
    """Returns True if the current process is running as root."""
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def has_pkexec() -> bool:
    """Check if pkexec (Polkit) is available."""
    return shutil.which("pkexec") is not None


def has_sudo() -> bool:
    """Check if sudo is available."""
    return shutil.which("sudo") is not None


def get_elevation_prefix() -> List[str]:
    """Returns the elevation command prefix (pkexec or sudo)."""
    if is_root():
        return []
    if has_pkexec():
        return ["pkexec"]
    if has_sudo():
        return ["sudo"]
    return []


def elevate_command(command: List[str]) -> List[str]:
    """Wraps command with pkexec or sudo if not already root."""
    if is_root() or not command:
        return command
    return get_elevation_prefix() + command


def run_privileged(command: List[str], timeout: int = 180) -> Tuple[int, str, str]:
    """
    Executes a command with elevated privileges using pkexec if not root.
    Returns (returncode, stdout, stderr).
    """
    if not command:
        return (0, "", "")

    exec_cmd = elevate_command(command)
    if not exec_cmd:
        return (1, "", "Kein Tool zur Rechte-Eskalation (pkexec oder sudo) gefunden.")

    try:
        proc = subprocess.run(
            exec_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        return (proc.returncode, proc.stdout, proc.stderr)
    except subprocess.TimeoutExpired:
        return (124, "", f"Befehl nach {timeout} Sekunden abgelaufen.")
    except Exception as e:
        return (1, "", f"Fehler bei Ausführung: {str(e)}")
