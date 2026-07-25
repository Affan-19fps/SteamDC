from __future__ import annotations

import logging
import subprocess
import sys
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)


# Windows SetThreadExecutionState constants
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
ES_AWAYMODE_REQUIRED = 0x00000040


def _set_thread_execution_state(flags: int) -> int | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        import ctypes.wintypes as wintypes
        kernel32 = ctypes.windll.kernel32
        fn = kernel32.SetThreadExecutionState
        fn.argtypes = [wintypes.DWORD]
        fn.restype = wintypes.DWORD
        return fn(flags)
    except Exception:
        logger.warning("SetThreadExecutionState failed", exc_info=True)
        return None


def can_prevent_sleep() -> bool:
    if sys.platform == "win32":
        return _set_thread_execution_state(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        ) is not None and _set_thread_execution_state(ES_CONTINUOUS) is not None
    elif sys.platform == "darwin":
        try:
            subprocess.run(
                ["which", "caffeinate"],
                capture_output=True, check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False
    return False

@contextmanager
def prevent_sleep() -> Generator[list[str], None, None]:
    messages: list[str] = []
    proc = None

    if sys.platform == "win32":
        prev = _set_thread_execution_state(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        )
        if prev is not None:
            messages.append("Wake-lock active (idle sleep prevented)")
        else:
            messages.append("Wake-lock: SetThreadExecutionState failed")

    elif sys.platform == "darwin":
        try:
            proc = subprocess.Popen(
                ["caffeinate", "-i", "-s"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            messages.append("Wake-lock active via caffeinate")
        except FileNotFoundError:
            messages.append("Wake-lock: caffeinate not found (macOS required)")
            proc = None

    try:
        yield messages
    finally:
        if sys.platform == "win32":
            _set_thread_execution_state(ES_CONTINUOUS)
        elif sys.platform == "darwin" and proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

