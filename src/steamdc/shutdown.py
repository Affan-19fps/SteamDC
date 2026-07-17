from __future__ import annotations

import platform
import subprocess
import sys


def shutdown_system() -> None:
    system = platform.system()
    if system == "Windows":
        subprocess.run(["shutdown", "/s", "/f", "/t", "0"], check=True)
    elif system == "Darwin":
        subprocess.run(["sudo", "shutdown", "-h", "now"], check=True)
    else:
        print(f"Unsupported OS: {system}. Please shut down manually.")
        sys.exit(1)


def can_shutdown() -> bool:
    system = platform.system()
    if system == "Windows":
        return True
    elif system == "Darwin":
        return True
    return False
