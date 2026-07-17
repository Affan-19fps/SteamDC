from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from steamdc.cli import build_parser, run_plain_monitor
from steamdc.monitor import DownloadProgress, MonitorState


class TestBuildParser:
    def test_defaults(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.interval == 5
        assert args.stall_timeout == 120
        assert args.shutdown_delay == 5
        assert not args.dry_run
        assert not args.no_rich

    def test_custom_values(self):
        parser = build_parser()
        args = parser.parse_args([
            "--interval", "15",
            "--stall-timeout", "300",
            "--shutdown-delay", "30",
            "--dry-run",
            "--no-rich",
        ])
        assert args.interval == 15
        assert args.stall_timeout == 300
        assert args.shutdown_delay == 30
        assert args.dry_run
        assert args.no_rich

    def test_version(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--version"])


class _NopCtx:
    def __enter__(self):
        return []
    def __exit__(self, *exc):
        pass


class TestRunPlainMonitor:
    @patch("steamdc.cli.monitor.monitor_loop")
    @patch("steamdc.cli.prevent_sleep", return_value=_NopCtx())
    def test_delegates_to_monitor_loop(self, mock_sleep, mock_monitor_loop):
        """run_plain_monitor creates callbacks and passes them to monitor_loop."""
        on_shutdown = MagicMock()
        run_plain_monitor(
            library_folders=[Path("/fake")],
            interval=30,
            stall_timeout=120,
            shutdown_delay=10,
            dry_run=False,
        )

        mock_monitor_loop.assert_called_once()
        call_kwargs = mock_monitor_loop.call_args[1]
        assert call_kwargs["interval"] == 30
        assert call_kwargs["stall_timeout"] == 120
        assert not call_kwargs["dry_run"]

    @patch("steamdc.cli.monitor.monitor_loop")
    def test_dry_run_flag_forwarded(self, mock_monitor_loop):
        run_plain_monitor(
            library_folders=[Path("/fake")],
            interval=30,
            stall_timeout=120,
            shutdown_delay=10,
            dry_run=True,
        )

        call_kwargs = mock_monitor_loop.call_args[1]
        assert call_kwargs["dry_run"] is True

    @patch("steamdc.cli.monitor.monitor_loop")
    def test_on_shutdown_callback_dry_run(self, mock_monitor_loop):
        """The on_shutdown callback prints and returns when dry_run is True."""
        run_plain_monitor(
            library_folders=[Path("/fake")],
            interval=30,
            stall_timeout=120,
            shutdown_delay=10,
            dry_run=True,
        )

        call_kwargs = mock_monitor_loop.call_args[1]
        shutdown_cb = call_kwargs["on_shutdown"]
        shutdown_cb()
        mock_monitor_loop.reset_mock()

    @patch("steamdc.cli.monitor.monitor_loop")
    def test_on_shutdown_callback_real(self, mock_monitor_loop):
        """The on_shutdown callback calls shutdown.shutdown_system when not dry_run."""
        with patch("steamdc.cli.shutdown.shutdown_system") as mock_shutdown:
            with patch("steamdc.cli.time.sleep"):
                run_plain_monitor(
                    library_folders=[Path("/fake")],
                    interval=30,
                    stall_timeout=120,
                    shutdown_delay=10,
                    dry_run=False,
                )

                call_kwargs = mock_monitor_loop.call_args[1]
                shutdown_cb = call_kwargs["on_shutdown"]
                shutdown_cb()
                mock_shutdown.assert_called_once()

    @patch("steamdc.cli.monitor.monitor_loop")
    def test_on_progress_callback_with_active_downloads(self, mock_monitor_loop):
        """on_progress handles active downloads without crashing."""
        run_plain_monitor(
            library_folders=[Path("/fake")],
            interval=30,
            stall_timeout=120,
            shutdown_delay=10,
            dry_run=False,
        )

        call_kwargs = mock_monitor_loop.call_args[1]
        on_progress = call_kwargs["on_progress"]

        dp = DownloadProgress(app_id="730", name="CS2", total_bytes=5000, downloaded_bytes=2000, percent=40.0)
        state = MonitorState(active_downloads=[dp], overall_bytes=5000, overall_downloaded=2000)
        on_progress(state)

    @patch("steamdc.cli.monitor.monitor_loop")
    def test_on_progress_callback_empty(self, mock_monitor_loop):
        """on_progress handles empty state without crashing."""
        run_plain_monitor(
            library_folders=[Path("/fake")],
            interval=30,
            stall_timeout=120,
            shutdown_delay=10,
            dry_run=False,
        )

        call_kwargs = mock_monitor_loop.call_args[1]
        on_progress = call_kwargs["on_progress"]

        state = MonitorState()
        on_progress(state)

    @patch("steamdc.cli.monitor.monitor_loop")
    def test_on_progress_callback_all_done(self, mock_monitor_loop):
        """on_progress handles all_done state without crashing."""
        run_plain_monitor(
            library_folders=[Path("/fake")],
            interval=30,
            stall_timeout=120,
            shutdown_delay=10,
            dry_run=False,
        )

        call_kwargs = mock_monitor_loop.call_args[1]
        on_progress = call_kwargs["on_progress"]

        state = MonitorState(all_done=True)
        on_progress(state)


class TestRun:
    @patch("steamdc.cli.steam.find_steam_root")
    def test_run_exits_when_no_steam(self, mock_find_root):
        mock_find_root.return_value = None
        testargs = ["steamdc"]
        with patch.object(sys, "argv", testargs):
            with pytest.raises(SystemExit):
                from steamdc.cli import run
                run()

    @patch("steamdc.cli.steam.find_steam_root")
    @patch("steamdc.cli.steam.find_library_folders")
    def test_run_exits_when_no_libraries(self, mock_find_libs, mock_find_root):
        mock_find_root.return_value = Path("/fake/steam")
        mock_find_libs.return_value = []
        testargs = ["steamdc"]
        with patch.object(sys, "argv", testargs):
            with pytest.raises(SystemExit):
                from steamdc.cli import run
                run()

    @patch("steamdc.cli.steam.find_steam_root")
    @patch("steamdc.cli.steam.find_library_folders")
    @patch("steamdc.cli.shutdown.can_shutdown")
    @patch("steamdc.cli.can_prevent_sleep", return_value=True)
    def test_run_plain_monitor_called(self, mock_sleep, mock_can_shutdown, mock_find_libs, mock_find_root):
        mock_find_root.return_value = Path("/fake/steam")
        mock_find_libs.return_value = [Path("/fake/steam/steamapps")]
        mock_can_shutdown.return_value = True
        testargs = ["steamdc", "--no-rich"]

        with patch("steamdc.cli.run_plain_monitor") as mock_plain:
            with patch.object(sys, "argv", testargs):
                from steamdc.cli import run
                run()

                mock_plain.assert_called_once()

    @patch("steamdc.cli.steam.find_steam_root")
    @patch("steamdc.cli.steam.find_library_folders")
    @patch("steamdc.cli.shutdown.can_shutdown")
    def test_run_exits_when_shutdown_unavailable(self, mock_can_shutdown, mock_find_libs, mock_find_root):
        """Exits when shutdown is not available and not in dry-run mode."""
        mock_find_root.return_value = Path("/fake/steam")
        mock_find_libs.return_value = [Path("/fake/steam/steamapps")]
        mock_can_shutdown.return_value = False
        testargs = ["steamdc", "--no-rich"]

        with patch.object(sys, "argv", testargs):
            with pytest.raises(SystemExit):
                from steamdc.cli import run
                run()


