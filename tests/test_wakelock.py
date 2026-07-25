from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from steamdc.wakelock import (
    _set_thread_execution_state,
    can_prevent_sleep,
    prevent_sleep,
)


class TestSetThreadExecutionState:
    def test_non_windows_returns_none(self):
        with patch("steamdc.wakelock.sys.platform", "linux"):
            result = _set_thread_execution_state(0x80000000)
            assert result is None

    def test_win32_success(self):
        with patch("steamdc.wakelock.sys.platform", "win32"):
            mock_fn = MagicMock(return_value=1)
            mock_ctypes = MagicMock()
            mock_ctypes.windll.kernel32.SetThreadExecutionState = mock_fn
            mock_ctypes.wintypes.DWORD = int
            with patch.dict("sys.modules", {"ctypes": mock_ctypes, "ctypes.wintypes": mock_ctypes.wintypes}):
                result = _set_thread_execution_state(0x80000000)
                assert result == 1
                mock_fn.assert_called_once_with(0x80000000)

    def test_win32_ctypes_error(self):
        with patch("steamdc.wakelock.sys.platform", "win32"):
            mock_fn = MagicMock(side_effect=OSError)
            mock_ctypes = MagicMock()
            mock_ctypes.windll.kernel32.SetThreadExecutionState = mock_fn
            mock_ctypes.wintypes.DWORD = int
            with patch.dict("sys.modules", {"ctypes": mock_ctypes, "ctypes.wintypes": mock_ctypes.wintypes}):
                result = _set_thread_execution_state(0x80000000)
                assert result is None


class TestCanPreventSleep:
    def test_windows_available(self):
        with patch("steamdc.wakelock.sys.platform", "win32"):
            with patch("steamdc.wakelock._set_thread_execution_state") as mock_stes:
                mock_stes.side_effect = [1, 1]
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

    def test_linux_returns_false(self):
        with patch("steamdc.wakelock.sys.platform", "linux"):
            assert can_prevent_sleep() is False

    def test_unknown_platform(self):
        with patch("steamdc.wakelock.sys.platform", "unknown"):
            assert can_prevent_sleep() is False


class TestPreventSleepWindows:
    def test_acquire_and_release(self):
        with patch("steamdc.wakelock.sys.platform", "win32"):
            with patch("steamdc.wakelock._set_thread_execution_state") as mock_stes:
                mock_stes.return_value = 1
                with prevent_sleep() as msgs:
                    assert "Wake-lock active" in msgs[0]
                assert mock_stes.call_count == 2

    def test_failure_returns_error_message(self):
        with patch("steamdc.wakelock.sys.platform", "win32"):
            with patch("steamdc.wakelock._set_thread_execution_state") as mock_stes:
                mock_stes.return_value = None
                with prevent_sleep() as msgs:
                    assert any("failed" in m for m in msgs)

    def test_linux_noop_does_nothing(self):
        with patch("steamdc.wakelock.sys.platform", "linux"):
            with prevent_sleep() as msgs:
                assert msgs == []


class TestPreventSleepMacOS:
    def test_acquire_and_release(self):
        with patch("steamdc.wakelock.sys.platform", "darwin"):
            mock_proc = MagicMock()
            with patch("steamdc.wakelock.subprocess.Popen") as mock_popen:
                mock_popen.return_value = mock_proc
                with prevent_sleep() as msgs:
                    assert any("caffeinate" in m for m in msgs)
                mock_proc.terminate.assert_called_once()

    def test_caffeinate_not_found(self):
        with patch("steamdc.wakelock.sys.platform", "darwin"):
            with patch("steamdc.wakelock.subprocess.Popen") as mock_popen:
                mock_popen.side_effect = FileNotFoundError
                with prevent_sleep() as msgs:
                    assert any("not found" in m for m in msgs)

    def test_terminate_timeout_expired(self):
        with patch("steamdc.wakelock.sys.platform", "darwin"):
            mock_proc = MagicMock()
            mock_proc.wait.side_effect = subprocess.TimeoutExpired("caffeinate", 5)
            with patch("steamdc.wakelock.subprocess.Popen") as mock_popen:
                mock_popen.return_value = mock_proc
                with prevent_sleep() as msgs:
                    assert any("caffeinate" in m for m in msgs)
                mock_proc.terminate.assert_called_once()
                mock_proc.kill.assert_called_once()


class TestPreventSleepOther:
    def test_noop_for_non_win_non_mac(self):
        with patch("steamdc.wakelock.sys.platform", "linux"):
            with prevent_sleep() as msgs:
                assert msgs == []
