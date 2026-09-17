"""
Privilege escalation handler using SUDO_ASKPASS and sudo.
"""
import os
import shutil
import subprocess
from typing import Callable, Dict, List, Optional, Tuple


def is_root() -> bool:
    """Returns True if the current process is running as root."""
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def get_askpass_path() -> str:
    """
    Returns the absolute path to the CachyOS askpass helper script,
    ensuring it has execute permissions.
    """
    # 1. Check relative to current file in package
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate = os.path.join(base_dir, "askpass.py")
    if os.path.isfile(candidate):
        try:
            os.chmod(candidate, 0o755)
        except Exception:
            pass
        return candidate

    # 2. Check user-installed location
    user_installed = os.path.expanduser("~/.local/share/cachyos-update-center/cachyos_update_center/askpass.py")
    if os.path.isfile(user_installed):
        try:
            os.chmod(user_installed, 0o755)
        except Exception:
            pass
        return user_installed

    return candidate


def get_authenticated_env() -> Dict[str, str]:
    """Returns a copy of the environment with SUDO_ASKPASS and SSH_ASKPASS configured."""
    env = os.environ.copy()
    askpass = get_askpass_path()
    env["SUDO_ASKPASS"] = askpass
    env["SSH_ASKPASS"] = askpass
    return env


def is_sudo_authenticated() -> bool:
    """Checks if sudo credentials are authenticated without prompting."""
    if is_root():
        return True
    try:
        res = subprocess.run(
            ["sudo", "-n", "true"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=3,
        )
        return res.returncode == 0
    except Exception:
        return False


def authenticate_sudo(status_callback: Optional[Callable[[str], None]] = None) -> bool:
    """
    Ensures that sudo is authenticated. If already warm, returns True immediately.
    Otherwise triggers sudo -A -v using the GUI askpass helper.
    """
    if is_root() or is_sudo_authenticated():
        return True

    env = get_authenticated_env()
    if status_callback:
        status_callback("🔐 Administrator-Rechte erforderlich. Öffne Authentifizierungsdialog...")

    try:
        res = subprocess.run(
            ["sudo", "-A", "-v"],
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return res.returncode == 0
    except Exception as e:
        if status_callback:
            status_callback(f"Authentifizierungsfehler: {e}")
        return False


def has_pkexec() -> bool:
    """Check if pkexec (Polkit) is available."""
    return shutil.which("pkexec") is not None


def has_sudo() -> bool:
    """Check if sudo is available."""
    return shutil.which("sudo") is not None


def get_elevation_prefix() -> List[str]:
    """Returns the elevation command prefix using sudo -A."""
    if is_root():
        return []
    if has_sudo():
        return ["sudo", "-A"]
    if has_pkexec():
        return ["pkexec"]
    return []


def elevate_command(command: List[str]) -> List[str]:
    """Wraps command with sudo -A (or pkexec) if not already root."""
    if is_root() or not command:
        return command
    return get_elevation_prefix() + command


def run_privileged(command: List[str], timeout: int = 180) -> Tuple[int, str, str]:
    """
    Executes a command with elevated privileges using sudo -A and SUDO_ASKPASS.
    Returns (returncode, stdout, stderr).
    """
    if not command:
        return (0, "", "")

    exec_cmd = elevate_command(command)
    if not exec_cmd:
        return (1, "", "Kein Tool zur Rechte-Eskalation (sudo oder pkexec) gefunden.")

    env = get_authenticated_env()
    try:
        proc = subprocess.run(
            exec_cmd,
            env=env,
            stdin=subprocess.DEVNULL,
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

