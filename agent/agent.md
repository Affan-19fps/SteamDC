# SteamDC — Agent Guide

## Overview
Monitors Steam download progress via local `.acf` manifest files and shuts down the PC when all downloads are done. No Steam API involved — purely filesystem monitoring.

## Repo Structure
```
D:\GithubProjects\SteamDC\
├── src/steamdc/
│   ├── __init__.py       # __version__ = "0.1.0"
│   ├── __main__.py       # calls cli.run()
│   ├── cli.py            # argparse CLI, dispatches to rich/plain/GUI monitor
│   ├── monitor.py        # Core polling loop, MonitorState, check_downloads()
│   ├── steam.py          # Steam root discovery, .acf manifest parsing, AppInfo
│   ├── vdf.py            # VDF/ACF parser and serializer
│   ├── shutdown.py       # OS-specific shutdown (Windows/macOS)
│   ├── wakelock.py       # Sleep prevention (SetThreadExecutionState / caffeinate)
│   ├── ui_rich.py        # Rich terminal UI with live progress bars
│   └── ui_gui.py         # Optional customtkinter GUI
├── tests/
│   ├── test_vdf.py / test_vdf_edge.py / test_steam.py
│   ├── test_monitor.py / test_cli.py / test_shutdown.py / test_wakelock.py
│   └── conftest.py / fakes.py
├── pyproject.toml        # Build config & CLI entry point
├── SteamDC.spec          # PyInstaller spec
└── agent/agent.md        # This file
```

## Key Files & Responsibilities

### `cli.py` — Entry & CLI
- `run()`: parses args, finds Steam root, dispatches to rich/plain/GUI monitor
- `run_plain_monitor()`: plain-text fallback with callbacks
- `_run_with_sleep_lock()`: wraps monitor with sleep prevention
- **Args**: `--interval` (5s), `--stall-timeout` (120s), `--shutdown-delay` (5s), `--dry-run`, `--no-rich`, `--gui`, `--allow-sleep`, `--no-sleep-lid`

### `monitor.py` — Core Loop
- `monitor_loop()`: polls every `interval` seconds, calls `check_downloads()`, tracks progress
- `check_downloads()`: scans all manifests, returns `MonitorState`
- `MonitorState`: `active_downloads`, `staging_apps`, `overall_bytes`, `overall_downloaded`, `stall_seconds`, `all_done`, `target_app_ids`
- Completion detection: when all apps done + no staging, increments `completion_counter` up to `stall_timeout`

### `steam.py` — Steam Filesystem Access
- `find_steam_root()`: Windows (registry → `C:\Program Files (x86)\Steam`), Linux (`~/.steam/steam`), macOS (`~/Library/Application Support/Steam`)
- `find_library_folders()`: reads `steamapps/` + `libraryfolders.vdf`
- `find_all_manifests()`: globs `appmanifest_*.acf` across all libraries
- `read_manifest()`: cached `.acf` reading via `vdf.load_acf()`
- `AppInfo`: dataclass — `app_id`, `name`, `state_flags`, `bytes_to_download`, `bytes_downloaded`, `bytes_to_stage`, `bytes_staged`
- `ManifestCache`: time-aware cache using `st_mtime_ns`

### `vdf.py` — Valve VDF/ACF Parser
- `parse_vdf(text)` → dict: recursive descent parser
- `load_acf(path)` / `save_acf(data, path)`: read/write `.acf` files
- Inner `_Parser` class: tokenizer + recursive deserializer

### `shutdown.py`
- `shutdown_system()`: OS-specific shutdown command
- `can_shutdown()`: True for Windows/macOS

### `wakelock.py`
- `prevent_sleep(lid_close=False)`: context manager — `SetThreadExecutionState` on Windows, `caffeinate` on macOS
- `can_prevent_sleep()` / `can_prevent_lid_sleep()`: capability checks

### `ui_rich.py` — Rich Terminal UI
- `run_rich_monitor()`: `rich.live.Live` with per-game + overall progress bars
- Staging indicator, stall timeout, dry-run badge, shutdown countdown

### `ui_gui.py` — Desktop GUI
- `run_gui()`: launches `DCSApp` (customtkinter, 680x540)
- `SelectionFrame`: checkboxes for active downloads, start button
- `MonitoringFrame`: per-app cards with header images, animated status, progress
- Downloads game header images from `steamstatic.com`

## Dependencies
- **Runtime**: Python >= 3.10, `rich` >= 13.0
- **Optional [gui]**: `customtkinter` >= 5.2, `Pillow` >= 10.0
- **Dev**: pytest, ruff, PyInstaller, coverage

## Existing Features
- Real-time progress (per-game + overall)
- Smart Steam root + library discovery
- Staging-aware (waits for post-download install)
- Stall detection (configurable timeout)
- Dry-run mode
- Sleep/lid-close prevention
- Cross-platform (Windows/macOS/Linux with varying support)
- Two UIs: rich terminal + optional desktop GUI

## No Network Throttling
The project has **zero** bandwidth capping or traffic shaping. All monitoring is file-based. The only network activity is fetching game header images in the optional GUI.

## Testing
- `pytest` with `--cov` for coverage (target: 90%)
- Tests use temporary directory fixtures with fake `.acf` files (see `conftest.py` / `fakes.py`)
- Run: `pytest`

## Build
- `PyInstaller` via `SteamDC.spec` → `SteamDC.exe`
- Pre-built binary: `SteamDC_/SteamDC.exe`
