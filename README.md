# SteamDC

**Download Completion Shutdown for Steam**

No more guessing 2-hour timers for `shutdown /s /f /t`. This tool monitors Steam's download progress in real-time and shuts down your PC the moment everything's actually done — even if your internet speed tanks mid-download.

## Features

- **Real-time progress** — per-game and overall progress bars
- **Smart detection** — reads Steam's `.acf` manifest files directly, no injection or API hacks
- **Staging aware** — waits for post-download staging/installing to finish too
- **Stall detection** — if downloads stall out, waits a configurable period before shutting down
- **Cross-platform** — Windows, Linux, macOS
- **Rich UI** — beautiful terminal output with `rich` (falls back to plain mode)
- **Dry-run mode** — see what would happen without actually shutting down

## Installation

```bash
pip install steamdc
```

Or run from source:

```bash
git clone https://github.com/lowlevel-ad/SteamDC
cd SteamDC
pip install -e .
```

## Usage

```bash
# Default — poll every 30s, shutdown 10s after downloads complete
steamdc

# Dry-run — monitor without shutting down
steamdc --dry-run

# Custom polling and stall settings
steamdc --interval 15 --stall-timeout 300

# Plain output (no rich progress bars)
steamdc --no-rich

# Help
steamdc --help
```

## How it works

Steam stores download state in `.acf` manifest files inside each library folder's `steamapps/` directory. `steamdc` parses these files to read `BytesDownloaded` / `BytesToDownload` and monitors the `steamapps/downloading/` directories for post-download staging activity. Once all bytes are accounted for and no new activity is detected for the stall timeout window, it triggers a system shutdown.

No reverse engineering, no Steam client API, no injection. Just file watching.

## License

MIT
