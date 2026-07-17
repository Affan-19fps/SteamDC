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

# Windows power scheme GUID for lid-close action
LID_CLOSE_SUBGROUP = "{4f971e89-eebd-4455-a8de-9e59040e7347}"
LID_CLOSE_SETTING = "{5ca83367-6e45-459f-a27b-476b1d01c936}"


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


class WindowsSleepPreventer:
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_AWAYMODE_REQUIRED = 0x00000040

    def __init__(self):
        self._supported = sys.platform == "win32"

    def prevent_sleep(self) -> bool:
        if not self._supported:
            return False
        try:
            import ctypes
            import ctypes.wintypes as wintypes
            kernel32 = ctypes.windll.kernel32
            fn = kernel32.SetThreadExecutionState
            fn.argtypes = [wintypes.DWORD]
            fn.restype = wintypes.DWORD
            flags = self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED | self.ES_AWAYMODE_REQUIRED
            result = fn(flags)
            return result != 0
        except Exception:
            logger.warning("WindowsSleepPreventer.prevent_sleep failed", exc_info=True)
            return False

    def allow_sleep(self) -> bool:
        if not self._supported:
            return False
        try:
            import ctypes
            import ctypes.wintypes as wintypes
            kernel32 = ctypes.windll.kernel32
            fn = kernel32.SetThreadExecutionState
            fn.argtypes = [wintypes.DWORD]
            fn.restype = wintypes.DWORD
            result = fn(self.ES_CONTINUOUS)
            return result != 0
        except Exception:
            logger.warning("WindowsSleepPreventer.allow_sleep failed", exc_info=True)
            return False


def _get_active_power_scheme() -> str | None:
    try:
        out = subprocess.run(
            ["powercfg", "/getactivescheme"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return out.split()[2] if out.split() else None
    except (subprocess.CalledProcessError, FileNotFoundError, IndexError):
        return None


def _set_lid_action(ac_action: int, dc_action: int) -> str | None:
    scheme = _get_active_power_scheme()
    if scheme is None:
        return "Could not determine active power scheme"
    try:
        subprocess.run(
            ["powercfg", "/setacvalueindex",
             scheme, LID_CLOSE_SUBGROUP, LID_CLOSE_SETTING, str(ac_action)],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["powercfg", "/setdcvalueindex",
             scheme, LID_CLOSE_SUBGROUP, LID_CLOSE_SETTING, str(dc_action)],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["powercfg", "/s", scheme],
            capture_output=True, text=True, check=True,
        )
        return None
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip()
        if "You do not have the required" in error_msg.lower() or "access denied" in error_msg.lower():
            return "Administrator privileges required to change lid-close behavior"
        return f"powercfg failed: {error_msg or e}"
    except FileNotFoundError:
        return "powercfg not found"


def _get_current_lid_action() -> tuple[int, int] | None:
    scheme = _get_active_power_scheme()
    if scheme is None:
        return None
    try:
        out = subprocess.run(
            ["powercfg", "/query", scheme,
             LID_CLOSE_SUBGROUP, LID_CLOSE_SETTING],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        ac_val = None
        dc_val = None
        for line in out.splitlines():
            stripped = line.strip()
            if "Current AC Power Setting Index:" in stripped:
                parts = stripped.split()
                raw = parts[-1]
                if raw.startswith("0x") or raw.startswith("0X"):
                    ac_val = int(raw, 16)
            elif "Current DC Power Setting Index:" in stripped:
                parts = stripped.split()
                raw = parts[-1]
                if raw.startswith("0x") or raw.startswith("0X"):
                    dc_val = int(raw, 16)
        if ac_val is not None and dc_val is not None:
            return (ac_val, dc_val)
        return None
    except Exception:
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


def can_prevent_lid_sleep() -> bool:
    if sys.platform == "win32":
        scheme = _get_active_power_scheme()
        if scheme is None:
            return False
        try:
            subprocess.run(
                ["powercfg", "/query", scheme,
                 LID_CLOSE_SUBGROUP, LID_CLOSE_SETTING],
                capture_output=True, check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False
        except FileNotFoundError:
            return False
    return False


@contextmanager
def prevent_sleep(*, lid_close: bool = False) -> Generator[list[str], None, None]:
    messages: list[str] = []
    restore_lid = None
    proc = None

    if sys.platform == "win32":
        prev = _set_thread_execution_state(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        )
        if prev is not None:
            messages.append("Wake-lock active (idle sleep prevented)")
            if lid_close:
                original = _get_current_lid_action()
                if original is not None:
                    ac_val, dc_val = original
                    err = _set_lid_action(0, 0)
                    if err:
                        messages.append(f"Lid-close sleep: {err}")
                    else:
                        restore_lid = (ac_val, dc_val)
                        messages.append("Lid-close sleep prevented")
                else:
                    messages.append("Lid-close: could not read current setting")
        else:
            messages.append("Wake-lock: SetThreadExecutionState failed")

    elif sys.platform == "darwin":
        try:
            proc = subprocess.Popen(
                ["caffeinate", "-i", "-s"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            messages.append("Wake-lock active via caffeinate")
            if lid_close:
                messages.append("Lid-close: not supported on macOS")
        except FileNotFoundError:
            messages.append("Wake-lock: caffeinate not found (macOS required)")
            proc = None

    try:
        yield messages
    finally:
        if sys.platform == "win32":
            _set_thread_execution_state(ES_CONTINUOUS)
            if restore_lid is not None:
                ac_val, dc_val = restore_lid
                err = _set_lid_action(ac_val, dc_val)
                if err:
                    logger.warning("Failed to restore lid-close action: %s", err)
        elif sys.platform == "darwin" and proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

