from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from steamdc.wakelock import (
    _set_thread_execution_state,
    can_prevent_lid_sleep,
    can_prevent_sleep,
    prevent_sleep,
)


class TestSetThreadExecutionState:
    def test_non_windows_returns_none(self):
        with patch("steamdc.wakelock.sys.platform", "linux"):
            result = _set_thread_execution_state(0x80000001)
            assert result is None

    def test_success(self):
        with patch("steamdc.wakelock.sys.platform", "win32"):
            with patch("steamdc.wakelock.sys.modules") as mock_modules:
                mock_ctypes = MagicMock()
                mock_fn = MagicMock(return_value=0x80000001)
                mock_ctypes.windll.kernel32.SetThreadExecutionState = mock_fn
                mock_ctypes.wintypes.DWORD = int
                mock_modules.__getitem__.side_effect = lambda k: {
                    "ctypes": mock_ctypes,
                    "ctypes.wintypes": mock_ctypes.wintypes,
                }.get(k, __import__(k))
                result = _set_thread_execution_state(0x80000001)
                assert result == 0x80000001
                mock_fn.assert_called_once_with(0x80000001)

    def test_ctypes_error(self):
        with patch("steamdc.wakelock.sys.platform", "win32"):
            with patch("steamdc.wakelock.sys.modules") as mock_modules:
                mock_ctypes = MagicMock()
                mock_ctypes.windll.kernel32.SetThreadExecutionState.side_effect = OSError
                mock_ctypes.wintypes.DWORD = int
                mock_modules.__getitem__.side_effect = lambda k: {
                    "ctypes": mock_ctypes,
                    "ctypes.wintypes": mock_ctypes.wintypes,
                }.get(k, __import__(k))
                result = _set_thread_execution_state(0x80000001)
                assert result is None


class TestCanPreventSleep:
    def test_windows_available(self):
        with patch("steamdc.wakelock.sys.platform", "win32"):
            with patch("steamdc.wakelock._set_thread_execution_state") as mock_stes:
                mock_stes.side_effect = [0x80000001, 0x80000001]
                assert can_prevent_sleep() is True
                assert mock_stes.call_count == 2

    def test_windows_unavailable(self):
        with patch("steamdc.wakelock.sys.platform", "win32"):
            with patch("steamdc.wakelock._set_thread_execution_state") as mock_stes:
                mock_stes.return_value = None
                assert can_prevent_sleep() is False

    def test_macos_available(self):
        with patch("steamdc.wakelock.sys.platform", "darwin"):
            with patch("steamdc.wakelock.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock()
                assert can_prevent_sleep() is True

    def test_macos_unavailable(self):
        with patch("steamdc.wakelock.sys.platform", "darwin"):
            with patch("steamdc.wakelock.subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.CalledProcessError(127, "which")
                assert can_prevent_sleep() is False

    def test_unknown_platform(self):
        with patch("steamdc.wakelock.sys.platform", "unknown"):
            assert can_prevent_sleep() is False


class TestCanPreventLidSleep:
    def test_windows_available(self):
        with patch("steamdc.wakelock.sys.platform", "win32"):
            with patch("steamdc.wakelock.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock()
                assert can_prevent_lid_sleep() is True

    def test_windows_not_found(self):
        with patch("steamdc.wakelock.sys.platform", "win32"):
            with patch("steamdc.wakelock.subprocess.run") as mock_run:
                mock_run.side_effect = FileNotFoundError
                assert can_prevent_lid_sleep() is False

    def test_macos_returns_false(self):
        with patch("steamdc.wakelock.sys.platform", "darwin"):
            assert can_prevent_lid_sleep() is False

    def test_unknown_platform(self):
        with patch("steamdc.wakelock.sys.platform", "unknown"):
            assert can_prevent_lid_sleep() is False


class TestPreventSleepWindows:
    def test_acquire_and_release(self):
        with patch("steamdc.wakelock.sys.platform", "win32"):
            with patch("steamdc.wakelock._set_thread_execution_state") as mock_stes:
                mock_stes.return_value = 0x80000001
                with prevent_sleep(lid_close=False) as msgs:
                    assert "Wake-lock active" in msgs[0]
                mock_stes.assert_any_call(0x80000001 | 0x00000001)
                mock_stes.assert_any_call(0x80000000)

    def test_lid_close_restores_original(self):
        with patch("steamdc.wakelock.sys.platform", "win32"):
            with patch("steamdc.wakelock._set_thread_execution_state") as mock_stes:
                mock_stes.return_value = 0x80000001
                with patch("steamdc.wakelock._get_current_lid_action") as mock_get_lid:
                    mock_get_lid.return_value = (1, 1)
                    with patch("steamdc.wakelock._set_lid_action", return_value=None) as mock_set_lid:
                        with prevent_sleep(lid_close=True) as msgs:
                            assert any("Lid-close sleep prevented" in m for m in msgs)
                        mock_set_lid.assert_any_call(0, 0)
                        mock_set_lid.assert_any_call(1, 1)

    def test_failure_returns_error_message(self):
        with patch("steamdc.wakelock.sys.platform", "win32"):
            with patch("steamdc.wakelock._set_thread_execution_state") as mock_stes:
                mock_stes.return_value = None
                with prevent_sleep() as msgs:
                    assert any("failed" in m for m in msgs)


class TestPreventSleepMacOS:
    def test_acquire_and_release(self):
        with patch("steamdc.wakelock.sys.platform", "darwin"):
            mock_proc = MagicMock()
            with patch("steamdc.wakelock.subprocess.Popen") as mock_popen:
                mock_popen.return_value = mock_proc
                with prevent_sleep(lid_close=False) as msgs:
                    assert any("caffeinate" in m for m in msgs)
                mock_proc.terminate.assert_called_once()

    def test_caffeinate_not_found(self):
        with patch("steamdc.wakelock.sys.platform", "darwin"):
            with patch("steamdc.wakelock.subprocess.Popen") as mock_popen:
                mock_popen.side_effect = FileNotFoundError
                with prevent_sleep() as msgs:
                    assert any("not found" in m for m in msgs)

    def test_lid_close_not_supported(self):
        with patch("steamdc.wakelock.sys.platform", "darwin"):
            with patch("steamdc.wakelock.subprocess.Popen") as mock_popen:
                mock_popen.return_value = MagicMock()
                with prevent_sleep(lid_close=True) as msgs:
                    assert any("not supported on macOS" in m for m in msgs)

