from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import steam
from .steam import ManifestCache

logger = logging.getLogger(__name__)

_BYTES_PER_MB = 1024 * 1024


@dataclass
class DownloadProgress:
    app_id: str
    name: str
    total_bytes: int
    downloaded_bytes: int
    percent: float

    @property
    def mb_total(self) -> float:
        return self.total_bytes / _BYTES_PER_MB

    @property
    def mb_downloaded(self) -> float:
        return self.downloaded_bytes / _BYTES_PER_MB


@dataclass
class MonitorState:
    active_downloads: list[DownloadProgress] = field(default_factory=list)
    staging_apps: list[str] = field(default_factory=list)
    overall_bytes: int = 0
    overall_downloaded: int = 0
    stall_seconds: int = 0
    all_done: bool = False
    target_app_ids: set[str] | None = None


ProgressCallback = Callable[[MonitorState], None]


def _has_staging_activity(dl_folder: Path) -> list[str]:
    items = []
    if not dl_folder.exists():
        return items
    try:
        for entry in dl_folder.iterdir():
            items.append(entry.name)
    except PermissionError:
        logger.warning("Permission denied accessing staging folder %s", dl_folder)
    return items


def check_downloads(
    library_folders: list[Path],
    manifest_cache: ManifestCache | None = None,
) -> MonitorState:
    state = MonitorState()
    manifests = steam.find_all_manifests(library_folders, cache=manifest_cache)

    for mf in manifests:
        try:
            data = steam.read_manifest(mf, cache=manifest_cache)
            info = steam.AppInfo(data)
            if info.has_pending_download:
                dp = DownloadProgress(
                    app_id=info.app_id,
                    name=info.name,
                    total_bytes=info.bytes_to_download,
                    downloaded_bytes=info.bytes_downloaded,
                    percent=info.download_pct,
                )
                state.active_downloads.append(dp)
                state.overall_bytes += info.bytes_to_download
                state.overall_downloaded += info.bytes_downloaded
        except (OSError, ValueError, KeyError) as e:
            logger.warning("Failed to parse manifest %s: %s", mf, e)

    dl_folders = steam.get_downloading_folders(library_folders)
    for dlf in dl_folders:
        for name in _has_staging_activity(dlf):
            if name not in state.staging_apps:
                state.staging_apps.append(name)

    return state


def monitor_loop(
    library_folders: list[Path],
    interval: int = 30,
    stall_timeout: int = 120,
    on_progress: ProgressCallback | None = None,
    on_shutdown: Callable[[], None] | None = None,
    dry_run: bool = False,
    target_app_ids: set[str] | None = None,
) -> None:
    completion_counter = 0
    previous_app_bytes: dict[str, int] = {}
    ever_saw_content = False
    manifest_cache = ManifestCache()

    while True:
        state = check_downloads(library_folders, manifest_cache=manifest_cache)

        if target_app_ids is not None:
            state.active_downloads = [
                d for d in state.active_downloads if d.app_id in target_app_ids
            ]
            state.staging_apps = [s for s in state.staging_apps if s in target_app_ids]
            state.overall_bytes = sum(d.total_bytes for d in state.active_downloads)
            state.overall_downloaded = sum(d.downloaded_bytes for d in state.active_downloads)
            state.target_app_ids = target_app_ids

        current_app_bytes: dict[str, int] = {}
        for dl in state.active_downloads:
            current_app_bytes[dl.app_id] = dl.downloaded_bytes

        made_progress = False
        for app_id, dl_bytes in current_app_bytes.items():
            prev = previous_app_bytes.get(app_id)
            if prev is not None and dl_bytes > prev:
                made_progress = True
                break

        for app_id in current_app_bytes:
            if app_id not in previous_app_bytes:
                made_progress = True
                break

        stale_app_ids = [
            app_id
            for app_id in previous_app_bytes
            if app_id not in current_app_bytes
        ]
        previous_app_bytes = current_app_bytes

        has_content = bool(state.active_downloads) or bool(state.staging_apps)

        if has_content:
            ever_saw_content = True
            if made_progress or stale_app_ids:
                if made_progress:
                    logger.debug(
                        "Download progress detected for apps: %s",
                        [a for a, b in current_app_bytes.items()
                         if previous_app_bytes.get(a) is not None and b > previous_app_bytes[a]],
                    )
                completion_counter = 0
        elif ever_saw_content:
            completion_counter += interval
            logger.debug("No content, completion counter: %ds", completion_counter)

        if completion_counter >= stall_timeout:
            logger.info("All downloads complete (stall timeout of %ds reached)", stall_timeout)
            state.all_done = True
            if on_progress:
                on_progress(state)
            break

        if state.active_downloads or state.staging_apps:
            state.stall_seconds = completion_counter if not made_progress else 0
            if state.stall_seconds > 0 and state.stall_seconds >= interval * 2:
                logger.info("Download stalled (%ds without progress)", state.stall_seconds)

        if on_progress:
            on_progress(state)

        time.sleep(interval)

    if on_shutdown and not dry_run:
        on_shutdown()
