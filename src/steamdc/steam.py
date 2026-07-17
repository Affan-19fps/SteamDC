from __future__ import annotations

import platform
import re
from pathlib import Path
from typing import Any

from .vdf import load_acf


class ManifestCache:
    def __init__(self) -> None:
        self._file_cache: dict[Path, tuple[int, dict[str, Any]]] = {}
        self._list_cache: dict[Path, tuple[int, list[Path]]] = {}

    def get_manifest(self, path: Path) -> dict[str, Any] | None:
        try:
            mtime_ns = path.stat().st_mtime_ns
        except OSError:
            return None
        entry = self._file_cache.get(path)
        if entry is not None and entry[0] == mtime_ns:
            return entry[1]
        return None

    def set_manifest(self, path: Path, data: dict[str, Any]) -> None:
        try:
            mtime_ns = path.stat().st_mtime_ns
        except OSError:
            return
        self._file_cache[path] = (mtime_ns, data)

    def get_manifest_list(self, folder: Path) -> list[Path] | None:
        try:
            mtime = folder.stat().st_mtime_ns
        except OSError:
            return None
        entry = self._list_cache.get(folder)
        if entry is not None and entry[0] == mtime:
            return entry[1]
        return None

    def set_manifest_list(self, folder: Path, manifests: list[Path]) -> None:
        try:
            mtime = folder.stat().st_mtime_ns
        except OSError:
            return
        self._list_cache[folder] = (mtime, manifests)

    def clear(self) -> None:
        self._file_cache.clear()
        self._list_cache.clear()


def find_steam_root() -> Path | None:
    system = platform.system()
    if system == "Windows":
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\WOW6432Node\Valve\Steam",
            ) as key:
                path = winreg.QueryValueEx(key, "InstallPath")[0]
                return Path(path)
        except (OSError, FileNotFoundError):
            pass
        candidates = [
            Path("C:/Program Files (x86)/Steam"),
            Path("C:/Program Files/Steam"),
        ]
        for p in candidates:
            if p.exists():
                return p
    elif system == "Linux":
        candidates = [
            Path.home() / ".steam" / "steam",
            Path.home() / ".local" / "share" / "Steam",
            Path("/usr/share/steam"),
        ]
        for p in candidates:
            if p.exists():
                return p
    elif system == "Darwin":
        candidates = [
            Path.home() / "Library" / "Application Support" / "Steam",
        ]
        for p in candidates:
            if p.exists():
                return p
    return None


def find_library_folders(steam_root: Path) -> list[Path]:
    folders = []
    main_apps = steam_root / "steamapps"
    if main_apps.exists():
        folders.append(main_apps)

    vdf_path = main_apps / "libraryfolders.vdf"
    if vdf_path.exists():
        try:
            data = load_acf(vdf_path)
            libfolders = data.get("libraryfolders", {})
            for key in sorted(libfolders.keys(), key=lambda k: int(k) if k.isdigit() else k):
                entry = libfolders[key]
                if isinstance(entry, dict):
                    path_val = entry.get("path", "")
                    cleaned = path_val.replace("\\\\", "\\")
                    lib_path = Path(cleaned) / "steamapps"
                    if lib_path.exists() and lib_path not in folders:
                        folders.append(lib_path)
        except Exception:
            pass

    return folders


def get_app_id(path: Path) -> str | None:
    m = re.search(r"appmanifest_(\d+)\.acf$", path.name)
    return m.group(1) if m else None


def read_manifest(
    acf_path: Path,
    cache: ManifestCache | None = None,
) -> dict[str, Any]:
    if cache is not None:
        cached = cache.get_manifest(acf_path)
        if cached is not None:
            return cached
    data = load_acf(acf_path)
    if cache is not None:
        cache.set_manifest(acf_path, data)
    return data


def find_all_manifests(
    library_folders: list[Path],
    cache: ManifestCache | None = None,
) -> list[Path]:
    manifests = []
    for folder in library_folders:
        if cache is not None:
            cached = cache.get_manifest_list(folder)
            if cached is not None:
                manifests.extend(cached)
                continue
        pattern = "appmanifest_*.acf"
        found = sorted(folder.glob(pattern))
        manifests.extend(found)
        if cache is not None:
            cache.set_manifest_list(folder, found)
    return manifests


def get_downloading_folders(library_folders: list[Path]) -> list[Path]:
    folders = []
    for lib in library_folders:
        dl = lib / "downloading"
        if dl.exists():
            folders.append(dl)
    return folders


class AppInfo:
    def __init__(self, manifest_data: dict[str, Any]):
        state = manifest_data.get("AppState", manifest_data)
        self.app_id: str = str(state.get("appid", ""))
        self.name: str = str(state.get("name", "Unknown"))
        self.state_flags: int = int(state.get("StateFlags", 0))
        self.bytes_to_download: int = _safe_int(state, "BytesToDownload")
        self.bytes_downloaded: int = _safe_int(state, "BytesDownloaded")
        self.bytes_to_stage: int = _safe_int(state, "BytesToStage", 0)
        self.bytes_staged: int = _safe_int(state, "BytesStaged", 0)

    @property
    def is_installed(self) -> bool:
        return bool(self.state_flags & 4)

    @property
    def is_downloading(self) -> bool:
        return bool(self.state_flags & 2)

    @property
    def download_pct(self) -> float:
        if self.bytes_to_download > 0:
            return (self.bytes_downloaded / self.bytes_to_download) * 100
        return 100.0

    @property
    def is_download_complete(self) -> bool:
        if self.bytes_to_download > 0:
            return self.bytes_downloaded >= self.bytes_to_download
        return True

    @property
    def has_pending_download(self) -> bool:
        return self.bytes_to_download > 0 and self.bytes_downloaded < self.bytes_to_download


def _safe_int(data: dict, key: str, default: int = 0) -> int:
    try:
        v = data.get(key, default)
        return int(v) if v is not None else default
    except (ValueError, TypeError):
        return default
