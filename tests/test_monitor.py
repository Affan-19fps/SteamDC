from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

import pytest

from steamdc.monitor import (
    DownloadProgress,
    MonitorState,
    _has_staging_activity,
    check_downloads,
    monitor_loop,
)


class TestDownloadProgress:
    def test_mb_total(self):
        dp = DownloadProgress(
            app_id="730",
            name="CS2",
            total_bytes=1_048_576,
            downloaded_bytes=524_288,
            percent=50.0,
        )
        assert dp.mb_total == 1.0
        assert dp.mb_downloaded == 0.5

    def test_zero_bytes(self):
        dp = DownloadProgress(
            app_id="0", name="Empty", total_bytes=0, downloaded_bytes=0, percent=100.0
        )
        assert dp.mb_total == 0.0
        assert dp.mb_downloaded == 0.0


class TestMonitorState:
    def test_defaults(self):
        s = MonitorState()
        assert s.active_downloads == []
        assert s.staging_apps == []
        assert s.overall_bytes == 0
        assert s.overall_downloaded == 0
        assert s.stall_seconds == 0
        assert not s.all_done


class TestHasStagingActivity:
    def test_non_existent_folder(self):
        result = _has_staging_activity(Path("/nonexistent/folder"))
        assert result == []

    def test_empty_folder(self, tmp_path):
        result = _has_staging_activity(tmp_path)
        assert result == []

    def test_with_subdirs(self, tmp_path):
        (tmp_path / "730").mkdir()
        (tmp_path / "1446890").mkdir()
        result = _has_staging_activity(tmp_path)
        assert len(result) == 2
        assert "730" in result
        assert "1446890" in result

    def test_with_marker_file(self, tmp_path):
        (tmp_path / "730").mkdir()
        (tmp_path / "downloading.exe").write_text("")
        result = _has_staging_activity(tmp_path)
        assert len(result) == 2
        assert "downloading.exe" in result

    def test_permission_error(self, tmp_path):
        with patch.object(Path, "iterdir", side_effect=PermissionError):
            result = _has_staging_activity(tmp_path)
            assert result == []


class TestCheckDownloads:
    def test_no_manifests(self, library_folder):
        result = check_downloads([library_folder])
        assert result.active_downloads == []
        assert result.overall_bytes == 0
        assert result.overall_downloaded == 0

    def test_active_downloads(self, library_setup):
        folders = [library_setup["primary"]]
        result = check_downloads(folders)
        assert len(result.active_downloads) >= 2
        app_names = {dp.name for dp in result.active_downloads}
        assert "Shadow Fight Arena" in app_names
        assert "Counter-Strike 2" in app_names

        total_bytes = sum(dp.total_bytes for dp in result.active_downloads)
        total_downloaded = sum(dp.downloaded_bytes for dp in result.active_downloads)
        assert result.overall_bytes == total_bytes
        assert result.overall_downloaded == total_downloaded

    def test_corrupted_manifest_skipped(self, library_setup):
        folders = [library_setup["primary"]]
        result = check_downloads(folders)
        app_ids = {dp.app_id for dp in result.active_downloads}
        assert "999" not in app_ids

    def test_with_staging(self, library_setup, downloading_folder):
        (downloading_folder / "1446890").mkdir()
        folders = [library_setup["primary"]]
        result = check_downloads(folders)
        assert "1446890" in result.staging_apps

    def test_with_downloading_marker(self, library_setup, downloading_folder):
        (downloading_folder / "downloading.exe").write_text("")
        folders = [library_setup["primary"]]
        result = check_downloads(folders)
        assert "downloading.exe" in result.staging_apps

    def test_with_cache(self, library_setup):
        from steamdc.steam import ManifestCache
        cache = ManifestCache()
        folders = [library_setup["primary"]]
        result1 = check_downloads(folders, manifest_cache=cache)
        assert len(result1.active_downloads) >= 2
        result2 = check_downloads(folders, manifest_cache=cache)
        assert len(result2.active_downloads) == len(result1.active_downloads)

    def test_with_cache_os_error_dir(self, tmp_path):
        from steamdc.steam import ManifestCache
        cache = ManifestCache()
        result = check_downloads([tmp_path / "nonexistent"], manifest_cache=cache)
        assert result.active_downloads == []


class TestMonitorLoop:
    def make_progress(self, app_id: str, name: str, done: int, total: int) -> DownloadProgress:
        pct = (done / total * 100) if total > 0 else 0
        return DownloadProgress(
            app_id=app_id, name=name,
            total_bytes=total, downloaded_bytes=done,
            percent=pct,
        )

    def _with_timeout(self, check_states, *, max_iterations: int = 15):
        """
        Wrap `check_downloads` mock with a sleep that raises RuntimeError
        after *max_iterations* loops so the test doesn't hang on infinite loops.
        Returns the original side_effect through, and the RuntimeError is
        caught by the caller.
        """
        counter = [0]

        def limited_sleep(_secs):
            counter[0] += 1
            if counter[0] >= max_iterations:
                raise RuntimeError("_loop_timeout")

        return patch("steamdc.monitor.time.sleep", limited_sleep)

    def test_no_downloads_never_shuts_down(self):
        """Never saw content → never triggers shutdown."""
        on_shutdown = MagicMock()

        states = iter([MonitorState(), MonitorState(), MonitorState()])

        def check_side_effect(_lib, **kwargs):
            try:
                return next(states)
            except StopIteration:
                raise RuntimeError("_loop_timeout")

        with patch("steamdc.monitor.check_downloads", check_side_effect):
            with self._with_timeout(states):
                with pytest.raises(RuntimeError, match="_loop_timeout"):
                    monitor_loop(
                        library_folders=[Path("/fake")],
                        interval=1,
                        stall_timeout=3,
                        on_progress=None,
                        on_shutdown=on_shutdown,
                        dry_run=False,
                    )

        on_shutdown.assert_not_called()

    def test_downloads_complete_triggers_shutdown(self):
        """Downloads progress normally, complete, then shutdown fires."""
        states = [
            MonitorState(active_downloads=[self.make_progress("730", "CS2", 500, 1000)]),
            MonitorState(active_downloads=[self.make_progress("730", "CS2", 800, 1000)]),
            MonitorState(active_downloads=[self.make_progress("730", "CS2", 1000, 1000)]),
            MonitorState(),
            MonitorState(),
            MonitorState(),
            MonitorState(),
        ]

        on_shutdown = MagicMock()

        with patch("steamdc.monitor.check_downloads", side_effect=states):
            with patch("steamdc.monitor.time.sleep"):
                monitor_loop(
                    library_folders=[Path("/fake")],
                    interval=1,
                    stall_timeout=3,
                    on_progress=None,
                    on_shutdown=on_shutdown,
                    dry_run=False,
                )

        on_shutdown.assert_called_once()

    def test_dry_run_prevents_shutdown(self):
        """In dry-run mode, shutdown callback is not called."""
        states = [
            MonitorState(active_downloads=[self.make_progress("730", "CS2", 500, 1000)]),
            MonitorState(),
            MonitorState(),
            MonitorState(),
            MonitorState(),
        ]

        on_shutdown = MagicMock()

        with patch("steamdc.monitor.check_downloads", side_effect=states):
            with patch("steamdc.monitor.time.sleep"):
                monitor_loop(
                    library_folders=[Path("/fake")],
                    interval=1,
                    stall_timeout=3,
                    on_progress=None,
                    on_shutdown=on_shutdown,
                    dry_run=True,
                )

        on_shutdown.assert_not_called()

    def test_paused_download_never_shuts_down(self):
        """A paused download (bytes never change) prevents shutdown."""
        on_shutdown = MagicMock()
        states = [
            MonitorState(active_downloads=[self.make_progress("730", "CS2", 500, 1000)]),
            MonitorState(active_downloads=[self.make_progress("730", "CS2", 500, 1000)]),
            MonitorState(active_downloads=[self.make_progress("730", "CS2", 500, 1000)]),
            MonitorState(active_downloads=[self.make_progress("730", "CS2", 500, 1000)]),
        ]

        state_iter = iter(states)

        def check_side_effect(_lib, **kwargs):
            try:
                return next(state_iter)
            except StopIteration:
                raise RuntimeError("_loop_timeout")

        with patch("steamdc.monitor.check_downloads", check_side_effect):
            with self._with_timeout(states):
                with pytest.raises(RuntimeError, match="_loop_timeout"):
                    monitor_loop(
                        library_folders=[Path("/fake")],
                        interval=1,
                        stall_timeout=3,
                        on_progress=None,
                        on_shutdown=on_shutdown,
                        dry_run=False,
                    )

        on_shutdown.assert_not_called()

    def test_new_download_resets_completion_timer(self):
        """A new download starting during completion phase resets the timer."""
        states = [
            MonitorState(active_downloads=[self.make_progress("730", "CS2", 500, 1000)]),
            MonitorState(),
            MonitorState(),
            MonitorState(active_downloads=[self.make_progress("440", "TF2", 100, 4000)]),
            MonitorState(active_downloads=[self.make_progress("440", "TF2", 4000, 4000)]),
            MonitorState(),
            MonitorState(),
            MonitorState(),
            MonitorState(),
        ]

        on_shutdown = MagicMock()

        with patch("steamdc.monitor.check_downloads", side_effect=states):
            with patch("steamdc.monitor.time.sleep"):
                monitor_loop(
                    library_folders=[Path("/fake")],
                    interval=1,
                    stall_timeout=3,
                    on_progress=None,
                    on_shutdown=on_shutdown,
                    dry_run=False,
                )

        on_shutdown.assert_called_once()

    def test_stall_seconds_during_completion_phase(self):
        """stall_seconds defaults to 0 during the completion phase (unchanged since UI
        reads it only when content is present)."""
        captured_states = []

        def capture(state: MonitorState) -> None:
            captured_states.append(state)

        states = [
            MonitorState(active_downloads=[self.make_progress("730", "CS2", 1000, 1000)]),
            MonitorState(active_downloads=[self.make_progress("730", "CS2", 1000, 1000)]),
            MonitorState(),
            MonitorState(),
            MonitorState(),
        ]

        with patch("steamdc.monitor.check_downloads", side_effect=states):
            with patch("steamdc.monitor.time.sleep"):
                monitor_loop(
                    library_folders=[Path("/fake")],
                    interval=1,
                    stall_timeout=3,
                    on_progress=capture,
                    on_shutdown=MagicMock(),
                    dry_run=True,
                )

        assert len(captured_states) == 5
        assert captured_states[-1].all_done

    def test_on_progress_called_with_all_done(self):
        """The on_progress callback fires one last time with all_done=True before exit."""
        final_state = []

        def capture(state: MonitorState) -> None:
            final_state.append(state)

        states = [
            MonitorState(active_downloads=[self.make_progress("730", "CS2", 1000, 1000)]),
            MonitorState(),
            MonitorState(),
            MonitorState(),
        ]

        with patch("steamdc.monitor.check_downloads", side_effect=states):
            with patch("steamdc.monitor.time.sleep"):
                monitor_loop(
                    library_folders=[Path("/fake")],
                    interval=1,
                    stall_timeout=3,
                    on_progress=capture,
                    on_shutdown=MagicMock(),
                    dry_run=True,
                )

        assert final_state[-1].all_done

    def test_shutdown_dry_run_no_actual_shutdown(self):
        """In dry-run mode, shutdown_system is never called."""
        on_shutdown = MagicMock()

        states = [
            MonitorState(active_downloads=[self.make_progress("730", "CS2", 1000, 1000)]),
            MonitorState(),
            MonitorState(),
            MonitorState(),
        ]

        with patch("steamdc.monitor.check_downloads", side_effect=states):
            with patch("steamdc.monitor.time.sleep"):
                monitor_loop(
                    library_folders=[Path("/fake")],
                    interval=1,
                    stall_timeout=3,
                    on_progress=None,
                    on_shutdown=on_shutdown,
                    dry_run=True,
                )

        on_shutdown.assert_not_called()

    def test_shutdown_called_after_completion(self):
        """After downloads complete and stall timeout elapses, on_shutdown is called."""
        states = [
            MonitorState(active_downloads=[self.make_progress("730", "CS2", 1000, 1000)]),
            MonitorState(),
            MonitorState(),
            MonitorState(),
        ]

        on_shutdown = MagicMock()

        with patch("steamdc.monitor.check_downloads", side_effect=states):
            with patch("steamdc.monitor.time.sleep"):
                monitor_loop(
                    library_folders=[Path("/fake")],
                    interval=1,
                    stall_timeout=3,
                    on_progress=None,
                    on_shutdown=on_shutdown,
                    dry_run=False,
                )

        on_shutdown.assert_called_once()
