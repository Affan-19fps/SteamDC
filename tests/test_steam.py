from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from steamdc.steam import (
    AppInfo,
    ManifestCache,
    _safe_int,
    find_all_manifests,
    find_library_folders,
    find_steam_root,
    get_app_id,
    get_downloading_folders,
    read_manifest,
)


class TestManifestCache:
    def test_cache_miss_returns_none(self, tmp_path):
        cache = ManifestCache()
        p = tmp_path / "test.acf"
        p.write_text('"x" "y"', encoding="utf-8")
        assert cache.get_manifest(p) is None

    def test_cache_hit_returns_data(self, tmp_path):
        cache = ManifestCache()
        p = tmp_path / "test.acf"
        p.write_text('"x" "y"', encoding="utf-8")
        from steamdc.vdf import load_acf
        data = load_acf(p)
        cache.set_manifest(p, data)
        result = cache.get_manifest(p)
        assert result == data

    def test_cache_miss_after_modification(self, tmp_path):
        cache = ManifestCache()
        p = tmp_path / "test.acf"
        p.write_text('"x" "y"', encoding="utf-8")
        from steamdc.vdf import load_acf
        data = load_acf(p)
        cache.set_manifest(p, data)
        time.sleep(0.01)
        p.write_text('"a" "b"', encoding="utf-8")
        assert cache.get_manifest(p) is None

    def test_get_manifest_os_error_returns_none(self):
        cache = ManifestCache()
        result = cache.get_manifest(Path("/nonexistent/file.acf"))
        assert result is None

    def test_set_manifest_nonexistent_path_no_error(self):
        cache = ManifestCache()
        cache.set_manifest(Path("/nonexistent/file.acf"), {})
        assert cache.get_manifest(Path("/nonexistent/file.acf")) is None

    def test_manifest_list_cache(self, tmp_path):
        cache = ManifestCache()
        p1 = tmp_path / "appmanifest_1.acf"
        p1.write_text('"x" "y"', encoding="utf-8")
        manifests = [p1]
        cache.set_manifest_list(tmp_path, manifests)
        result = cache.get_manifest_list(tmp_path)
        assert result == manifests

    def test_manifest_list_cache_miss_after_change(self, tmp_path):
        cache = ManifestCache()
        p1 = tmp_path / "appmanifest_1.acf"
        p1.write_text('"x" "y"', encoding="utf-8")
        cache.set_manifest_list(tmp_path, [p1])
        time.sleep(0.01)
        p2 = tmp_path / "appmanifest_2.acf"
        p2.write_text('"a" "b"', encoding="utf-8")
        result = cache.get_manifest_list(tmp_path)
        assert result is None

    def test_manifest_list_os_error_returns_none(self):
        cache = ManifestCache()
        result = cache.get_manifest_list(Path("/nonexistent"))
        assert result is None

    def test_set_manifest_list_nonexistent_path_no_error(self):
        cache = ManifestCache()
        cache.set_manifest_list(Path("/nonexistent"), [])
        assert cache.get_manifest_list(Path("/nonexistent")) is None

    def test_clear(self, tmp_path):
        cache = ManifestCache()
        p = tmp_path / "test.acf"
        p.write_text('"x" "y"', encoding="utf-8")
        from steamdc.vdf import load_acf
        data = load_acf(p)
        cache.set_manifest(p, data)
        cache.set_manifest_list(tmp_path, [p])
        cache.clear()
        assert cache.get_manifest(p) is None
        assert cache.get_manifest_list(tmp_path) is None


class TestFindSteamRoot:
    @patch("steamdc.steam.platform.system", return_value="Windows")
    def test_windows_registry_path(self, mock_system):
        mock_winreg = MagicMock()
        with patch.dict("sys.modules", {"winreg": mock_winreg}):
            mock_winreg.OpenKey.return_value.__enter__.return_value = MagicMock()
            mock_winreg.QueryValueEx.return_value = ("C:\\Program Files (x86)\\Steam",)

            result = find_steam_root()
            assert result == Path("C:\\Program Files (x86)\\Steam")

    @patch("steamdc.steam.platform.system", return_value="Windows")
    def test_windows_registry_fallback(self, mock_system):
        mock_winreg = MagicMock()
        with patch.dict("sys.modules", {"winreg": mock_winreg}):
            mock_winreg.OpenKey.side_effect = FileNotFoundError("not found")

            with patch("pathlib.Path.exists", return_value=True):
                result = find_steam_root()
                assert result is not None

    @patch("steamdc.steam.platform.system", return_value="Windows")
    def test_windows_not_found(self, mock_system):
        mock_winreg = MagicMock()
        with patch.dict("sys.modules", {"winreg": mock_winreg}):
            mock_winreg.OpenKey.side_effect = OSError("no steam")

            with patch("pathlib.Path.exists", return_value=False):
                result = find_steam_root()
                assert result is None

    @patch("steamdc.steam.platform.system", return_value="Linux")
    def test_linux_path(self, mock_system):
        with patch("pathlib.Path.exists", return_value=True):
            result = find_steam_root()
            assert result is not None
            assert ".steam" in str(result) or ".local" in str(result)

    @patch("steamdc.steam.platform.system", return_value="Linux")
    def test_linux_not_found(self, mock_system):
        with patch("pathlib.Path.exists", return_value=False):
            result = find_steam_root()
            assert result is None

    @patch("steamdc.steam.platform.system", return_value="Darwin")
    def test_macos_path(self, mock_system):
        with patch("pathlib.Path.exists", return_value=True):
            result = find_steam_root()
            assert result is not None
            assert "Application Support" in str(result)

    @patch("steamdc.steam.platform.system", return_value="Darwin")
    def test_macos_not_found(self, mock_system):
        with patch("pathlib.Path.exists", return_value=False):
            result = find_steam_root()
            assert result is None


class TestFindLibraryFolders:
    def test_basic(self, steam_root):
        lib = steam_root / "steamapps"
        lib.mkdir()
        result = find_library_folders(steam_root)
        assert len(result) == 1
        assert result[0] == lib

    def test_with_vdf(self, steam_root):
        lib = steam_root / "steamapps"
        lib.mkdir()
        vdf = lib / "libraryfolders.vdf"
        vdf.write_text(
            '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"D:\\\\Extra"\n\t}\n}',
            encoding="utf-8",
        )
        extra = Path("D:\\Extra") / "steamapps"
        with patch("pathlib.Path.exists", side_effect=lambda p=True: True if p is True else Path(p).exists()):
            pass

    def test_with_vdf_extra_library(self, steam_root, tmp_path):
        lib = steam_root / "steamapps"
        lib.mkdir()
        extra_root = tmp_path / "extralib"
        extra_steamapps = extra_root / "steamapps"
        extra_steamapps.mkdir(parents=True)

        vdf_content = (
            '"libraryfolders"\n'
            '{\n'
            f'\t"0"\n'
            '\t{\n'
            f'\t\t"path"\t\t"{extra_root.as_posix()}"\n'
            '\t}\n'
            '}'
        )
        vdf = lib / "libraryfolders.vdf"
        vdf.write_text(vdf_content, encoding="utf-8")

        result = find_library_folders(steam_root)
        assert len(result) == 2
        assert lib in result
        assert extra_steamapps in result

    def test_no_steamapps(self, steam_root):
        result = find_library_folders(steam_root)
        assert result == []

    def test_corrupted_vdf(self, steam_root):
        lib = steam_root / "steamapps"
        lib.mkdir()
        vdf = lib / "libraryfolders.vdf"
        vdf.write_text("not valid vdf {{", encoding="utf-8")
        result = find_library_folders(steam_root)
        assert len(result) == 1
        assert result[0] == lib

    def test_duplicate_paths(self, steam_root):
        lib = steam_root / "steamapps"
        lib.mkdir()
        vdf = lib / "libraryfolders.vdf"
        vdf.write_text(
            '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"C:\\\\dupe"\n\t}\n\t"1"\n\t{\n\t\t"path"\t\t"C:\\\\dupe"\n\t}\n}',
            encoding="utf-8",
        )
        with patch("pathlib.Path.exists", return_value=True):
            result = find_library_folders(steam_root)
            assert len(result) == 2


class TestGetAppId:
    def test_valid(self):
        p = Path("appmanifest_240.acf")
        assert get_app_id(p) == "240"

    def test_invalid(self):
        p = Path("somefile.txt")
        assert get_app_id(p) is None

    def test_no_match(self):
        p = Path("appmanifest_.acf")
        assert get_app_id(p) is None


class TestReadManifest:
    def test_valid(self, blank_manifest):
        data = read_manifest(blank_manifest)
        assert data["AppState"]["name"] == "Counter-Strike: Source"

    def test_not_found(self):
        with pytest.raises(FileNotFoundError):
            read_manifest(Path("nonexistent.acf"))

    def test_with_cache(self, blank_manifest):
        cache = ManifestCache()
        data1 = read_manifest(blank_manifest, cache=cache)
        assert data1["AppState"]["name"] == "Counter-Strike: Source"
        data2 = read_manifest(blank_manifest, cache=cache)
        assert data2 == data1

    def test_with_cache_stale_entry(self, blank_manifest):
        cache = ManifestCache()
        data1 = read_manifest(blank_manifest, cache=cache)
        time.sleep(0.01)
        blank_manifest.write_text('"AppState" { "appid" "999" "name" "Changed" }', encoding="utf-8")
        data2 = read_manifest(blank_manifest, cache=cache)
        assert data2["AppState"]["name"] == "Changed"


class TestFindAllManifests:
    def test_basic(self, library_setup):
        folders = [library_setup["primary"]]
        result = find_all_manifests(folders)
        assert len(result) == 5
        names = {p.name for p in result}
        assert "appmanifest_240.acf" in names
        assert "appmanifest_1446890.acf" in names
        assert "appmanifest_730.acf" in names
        assert "appmanifest_440.acf" in names
        assert "appmanifest_999.acf" in names

    def test_empty_library(self):
        result = find_all_manifests([Path("/nonexistent")])
        assert result == []

    def test_multiple_libraries(self, library_setup, secondary_library):
        secondary_manifest = secondary_library / "appmanifest_123.acf"
        secondary_manifest.write_text(
            '"AppState"\n{\n\t"appid"\t\t"123"\n\t"name"\t\t"Other Game"\n}',
            encoding="utf-8",
        )
        folders = [library_setup["primary"], secondary_library]
        result = find_all_manifests(folders)
        assert len(result) >= 6

    def test_with_cache(self, library_setup):
        cache = ManifestCache()
        folders = [library_setup["primary"]]
        result1 = find_all_manifests(folders, cache=cache)
        assert len(result1) == 5
        result2 = find_all_manifests(folders, cache=cache)
        assert result2 == result1


class TestGetDownloadingFolders:
    def test_with_downloading(self, library_folder, downloading_folder):
        folders = [library_folder]
        result = get_downloading_folders(folders)
        assert len(result) == 1
        assert result[0] == downloading_folder

    def test_without_downloading(self, library_folder):
        folders = [library_folder]
        result = get_downloading_folders(folders)
        assert result == []


class TestAppInfo:
    def test_installed(self):
        info = AppInfo({
            "AppState": {
                "appid": "240",
                "name": "CS:S",
                "StateFlags": "4",
                "BytesToDownload": "1000",
                "BytesDownloaded": "1000",
            }
        })
        assert info.is_installed
        assert not info.is_downloading
        assert info.is_download_complete
        assert not info.has_pending_download
        assert info.download_pct == 100.0

    def test_downloading(self):
        info = AppInfo({
            "AppState": {
                "appid": "730",
                "name": "CS2",
                "StateFlags": "2",
                "BytesToDownload": "5000",
                "BytesDownloaded": "2000",
            }
        })
        assert not info.is_installed
        assert info.is_downloading
        assert not info.is_download_complete
        assert info.has_pending_download
        assert info.download_pct == 40.0

    def test_installed_with_update(self):
        info = AppInfo({
            "AppState": {
                "appid": "730",
                "name": "CS2",
                "StateFlags": "6",
                "BytesToDownload": "5000",
                "BytesDownloaded": "2000",
            }
        })
        assert info.is_installed
        assert info.is_downloading
        assert info.has_pending_download

    def test_partial_download(self):
        info = AppInfo({
            "AppState": {
                "appid": "440",
                "name": "TF2",
                "StateFlags": "2",
                "BytesToDownload": "4000",
                "BytesDownloaded": "0",
            }
        })
        assert info.has_pending_download
        assert info.download_pct == 0.0
        assert not info.is_download_complete

    def test_completed_staging(self):
        info = AppInfo({
            "AppState": {
                "appid": "570",
                "name": "Dota 2",
                "StateFlags": "4",
                "BytesToDownload": "6000",
                "BytesDownloaded": "6000",
                "BytesToStage": "6000",
                "BytesStaged": "3500",
            }
        })
        assert info.is_download_complete
        assert not info.has_pending_download
        assert info.is_installed

    def test_no_bytes_fields(self):
        info = AppInfo({
            "AppState": {
                "appid": "228980",
                "name": "Redistributables",
                "StateFlags": "6",
            }
        })
        assert info.bytes_to_download == 0
        assert info.bytes_downloaded == 0
        assert info.download_pct == 100.0
        assert info.is_download_complete
        assert not info.has_pending_download

    def test_empty_state_fallback(self):
        info = AppInfo({})
        assert info.app_id == ""
        assert info.name == "Unknown"
        assert info.state_flags == 0
        assert info.bytes_to_download == 0


class TestSafeInt:
    def test_normal_int(self):
        assert _safe_int({"x": "42"}, "x") == 42

    def test_missing_key(self):
        assert _safe_int({}, "x") == 0

    def test_none_value(self):
        assert _safe_int({"x": None}, "x") == 0

    def test_invalid_string(self):
        assert _safe_int({"x": "not-a-number"}, "x") == 0

    def test_custom_default(self):
        assert _safe_int({}, "x", -1) == -1
