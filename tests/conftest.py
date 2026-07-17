from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from tests.fakes import (
    COMPLETED_DOWNLOAD_ACF,
    DOWNLOADING_ACF,
    INSTALLED_ACF,
    INSTALLED_WITH_UPDATE_ACF,
    LIBRARY_FOLDERS_VDF,
    MALFORMED_ACF,
    PARTIAL_DOWNLOAD_ACF,
)


@pytest.fixture
def steam_root(tmp_path: Path) -> Path:
    root = tmp_path / "steam"
    root.mkdir()
    return root


@pytest.fixture
def library_folder(steam_root: Path) -> Path:
    lib = steam_root / "steamapps"
    lib.mkdir()
    return lib


@pytest.fixture
def secondary_library(tmp_path: Path) -> Path:
    lib = tmp_path / "secondary" / "steamapps"
    lib.mkdir(parents=True)
    return lib


@pytest.fixture
def downloading_folder(library_folder: Path) -> Path:
    dl = library_folder / "downloading"
    dl.mkdir()
    return dl


@pytest.fixture
def blank_manifest(library_folder: Path) -> Path:
    """An app that is fully installed (no pending work)."""
    p = library_folder / "appmanifest_240.acf"
    p.write_text(INSTALLED_ACF, encoding="utf-8")
    return p


@pytest.fixture
def active_manifest(library_folder: Path) -> Path:
    """An app actively downloading."""
    p = library_folder / "appmanifest_1446890.acf"
    p.write_text(DOWNLOADING_ACF, encoding="utf-8")
    return p


@pytest.fixture
def updating_manifest(library_folder: Path) -> Path:
    """An installed app with a pending update."""
    p = library_folder / "appmanifest_730.acf"
    p.write_text(INSTALLED_WITH_UPDATE_ACF, encoding="utf-8")
    return p


@pytest.fixture
def partial_manifest(library_folder: Path) -> Path:
    """A fresh download at 0%."""
    p = library_folder / "appmanifest_440.acf"
    p.write_text(PARTIAL_DOWNLOAD_ACF, encoding="utf-8")
    return p


@pytest.fixture
def corrupted_manifest(library_folder: Path) -> Path:
    """A malformed ACF file."""
    p = library_folder / "appmanifest_999.acf"
    p.write_text(MALFORMED_ACF, encoding="utf-8")
    return p


@pytest.fixture
def library_vdf(steam_root: Path) -> Path:
    """libraryfolders.vdf pointing to two library paths."""
    p = steam_root / "steamapps" / "libraryfolders.vdf"
    p.write_text(LIBRARY_FOLDERS_VDF, encoding="utf-8")
    return p


@pytest.fixture
def library_setup(
    library_folder: Path,
    secondary_library: Path,
    blank_manifest: Path,
    active_manifest: Path,
    updating_manifest: Path,
    partial_manifest: Path,
    corrupted_manifest: Path,
) -> dict[str, Path]:
    """Complete multi-library setup with various manifest states."""
    return {
        "primary": library_folder,
        "secondary": secondary_library,
        "blank": blank_manifest,
        "active": active_manifest,
        "updating": updating_manifest,
        "partial": partial_manifest,
        "corrupted": corrupted_manifest,
    }
