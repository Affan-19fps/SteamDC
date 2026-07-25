from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from steamdc.cli import build_parser, run_plain_monitor, _print_sleep_messages
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

    @patch("steamdc.cli.monitor.monitor_loop")
    def test_on_shutdown_keyboard_interrupt(self, mock_monitor_loop):
        """KeyboardInterrupt during shutdown countdown exits cleanly."""
        run_plain_monitor(
            library_folders=[Path("/fake")],
            interval=30,
            stall_timeout=120,
            shutdown_delay=10,
            dry_run=False,
        )

        call_kwargs = mock_monitor_loop.call_args[1]
        shutdown_cb = call_kwargs["on_shutdown"]

        with patch("steamdc.cli.shutdown.shutdown_system") as mock_shutdown:
            with patch("steamdc.cli.time.sleep", side_effect=KeyboardInterrupt):
                with pytest.raises(SystemExit):
                    shutdown_cb()
                mock_shutdown.assert_not_called()

    @patch("steamdc.cli.monitor.monitor_loop")
    def test_on_shutdown_dry_run_skips_shutdown(self, mock_monitor_loop):
        """Dry-run on_shutdown prints and does not call shutdown_system."""
        run_plain_monitor(
            library_folders=[Path("/fake")],
            interval=30,
            stall_timeout=120,
            shutdown_delay=10,
            dry_run=True,
        )

        call_kwargs = mock_monitor_loop.call_args[1]
        shutdown_cb = call_kwargs["on_shutdown"]

        with patch("steamdc.cli.shutdown.shutdown_system") as mock_shutdown:
            shutdown_cb()
            mock_shutdown.assert_not_called()

    def test_run_plain_monitor_no_sleep_disabled(self):
        """no_sleep=False passes through to target without sleep lock."""
        with patch("steamdc.cli.monitor.monitor_loop") as mock_monitor_loop:
            run_plain_monitor(
                library_folders=[Path("/fake")],
                interval=30,
                stall_timeout=120,
                shutdown_delay=10,
                dry_run=False,
                no_sleep=False,
            )
            mock_monitor_loop.assert_called_once()

    def test_sigint_handler(self):
        """The SIGINT handler logs and exits."""
        with patch("steamdc.cli.monitor.monitor_loop"):
            with patch("steamdc.cli.signal.signal") as mock_signal:
                run_plain_monitor(
                    library_folders=[Path("/fake")],
                    interval=30,
                    stall_timeout=120,
                    shutdown_delay=10,
                    dry_run=False,
                )

                captured_handler = mock_signal.call_args[0][1]

                with patch("steamdc.cli.logger") as mock_logger:
                    with pytest.raises(SystemExit):
                        captured_handler(None, None)
                    mock_logger.info.assert_called_once()


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

    @patch("steamdc.cli.steam.find_steam_root")
    def test_run_dry_run_bypasses_shutdown_check(self, mock_find_root):
        """--dry-run skips the shutdown-available check entirely."""
        mock_find_root.return_value = Path("/fake/steam")
        testargs = ["steamdc", "--no-rich", "--dry-run"]

        with patch("steamdc.cli.steam.find_library_folders", return_value=[Path("/fake/steam/steamapps")]):
            with patch("steamdc.cli.run_plain_monitor") as mock_plain:
                with patch.object(sys, "argv", testargs):
                    from steamdc.cli import run
                    run()
                    mock_plain.assert_called_once()

    @patch("steamdc.cli.steam.find_steam_root")
    def test_run_rich_fallback_on_import_error(self, mock_find_root):
        """When rich import fails, falls through to plain monitor."""
        mock_find_root.return_value = Path("/fake/steam")

        with patch("steamdc.cli.steam.find_library_folders", return_value=[Path("/fake/steam/steamapps")]):
            with patch("steamdc.cli.shutdown.can_shutdown", return_value=True):
                with patch("steamdc.cli.can_prevent_sleep", return_value=True):
                    with patch("steamdc.cli.run_plain_monitor") as mock_plain:
                        with patch.object(sys, "argv", ["steamdc"]):
                            # Mark ui_rich as failed import so relative import raises ImportError
                            with patch.dict("sys.modules", {"steamdc.ui_rich": None}):
                                from steamdc.cli import run
                                run()
                                mock_plain.assert_called_once()

    @patch("steamdc.cli.steam.find_steam_root")
    def test_run_gui_mode(self, mock_find_root):
        """--gui flag launches the GUI and returns."""
        mock_find_root.return_value = Path("/fake")
        mock_gui = MagicMock()
        mock_gui.run_gui = MagicMock()

        with patch.dict("sys.modules", {"steamdc.ui_gui": mock_gui}):
            with patch.object(sys, "argv", ["steamdc", "--gui"]):
                from steamdc.cli import run
                run()
                mock_gui.run_gui.assert_called_once()

    @patch("steamdc.cli.steam.find_steam_root")
    def test_run_gui_import_error(self, mock_find_root):
        """When --gui is used but ui_gui can't be imported, exits with error."""
        mock_find_root.return_value = Path("/fake")

        with patch.dict("sys.modules", {"steamdc.ui_gui": None}):
            with patch.object(sys, "argv", ["steamdc", "--gui"]):
                with pytest.raises(SystemExit):
                    from steamdc.cli import run
                    run()

    @patch("steamdc.cli.steam.find_steam_root")
    def test_run_rich_monitor_success(self, mock_find_root):
        """When rich UI is available, run_rich_monitor is called."""
        mock_find_root.return_value = Path("/fake/steam")

        mock_rich = MagicMock()
        fake_run = MagicMock()

        with patch("steamdc.cli.steam.find_library_folders", return_value=[Path("/fake/steam/steamapps")]):
            with patch("steamdc.cli.shutdown.can_shutdown", return_value=True):
                with patch("steamdc.cli.can_prevent_sleep", return_value=True):
                    with patch.object(sys, "argv", ["steamdc"]):
                        with patch.dict("sys.modules", {"steamdc.ui_rich": mock_rich}):
                            mock_rich.run_rich_monitor = fake_run
                            from steamdc.cli import run
                            run()
                            fake_run.assert_called_once()


class TestPrintSleepMessages:
    def test_allow_sleep(self):
        args = MagicMock()
        args.allow_sleep = True
        _print_sleep_messages(args)

    def test_can_prevent_sleep(self):
        args = MagicMock()
        args.allow_sleep = False
        with patch("steamdc.cli.can_prevent_sleep", return_value=True):
            _print_sleep_messages(args)

    def test_cannot_prevent_sleep(self):
        args = MagicMock()
        args.allow_sleep = False
        with patch("steamdc.cli.can_prevent_sleep", return_value=False):
            _print_sleep_messages(args)


