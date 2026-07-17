from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from steamdc.shutdown import can_shutdown, shutdown_system


class TestCanShutdown:
    @patch("steamdc.shutdown.platform.system", return_value="Windows")
    def test_windows(self, mock_system):
        assert can_shutdown() is True

    @patch("steamdc.shutdown.platform.system", return_value="Darwin")
    def test_macos(self, mock_system):
        assert can_shutdown() is True

    @patch("steamdc.shutdown.platform.system", return_value="UnknownOS")
    def test_unknown(self, mock_system):
        assert can_shutdown() is False


class TestShutdownSystem:
    @patch("steamdc.shutdown.platform.system", return_value="Windows")
    @patch("steamdc.shutdown.subprocess.run")
    def test_windows_command(self, mock_run, mock_system):
        shutdown_system()
        mock_run.assert_called_once_with(
            ["shutdown", "/s", "/f", "/t", "0"], check=True
        )

    @patch("steamdc.shutdown.platform.system", return_value="Darwin")
    @patch("steamdc.shutdown.subprocess.run")
    def test_macos_command(self, mock_run, mock_system):
        shutdown_system()
        mock_run.assert_called_once_with(
            ["sudo", "shutdown", "-h", "now"], check=True
        )

    @patch("steamdc.shutdown.platform.system", return_value="UnknownOS")
    def test_unsupported_os(self, mock_system):
        with pytest.raises(SystemExit):
            shutdown_system()
