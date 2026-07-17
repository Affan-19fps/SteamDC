from __future__ import annotations

import argparse
import signal
import sys
import time
from datetime import datetime

from . import __version__, monitor, shutdown, steam
from .wakelock import can_prevent_lid_sleep, can_prevent_sleep, prevent_sleep


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="steamdc",
        description="Download Completion Shutdown for Steam — automatically shuts down your PC when Steam downloads finish.",
    )
    p.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Polling interval in seconds (default: 5)",
    )
    p.add_argument(
        "--stall-timeout",
        type=int,
        default=120,
        help="Seconds of no activity before considering downloads done (default: 120)",
    )
    p.add_argument(
        "--shutdown-delay",
        type=int,
        default=5,
        help="Seconds to wait before shutdown after downloads complete (default: 5)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Monitor but don't actually shut down",
    )
    p.add_argument(
        "--no-rich",
        action="store_true",
        help="Disable rich progress bars (plain output)",
    )
    p.add_argument(
        "--gui",
        action="store_true",
        help="Launch desktop GUI instead of terminal monitoring",
    )
    p.add_argument(
        "--allow-sleep",
        action="store_true",
        help="Allow the system to sleep during monitoring (default: prevented)",
    )
    p.add_argument(
        "--no-sleep-lid",
        action="store_true",
        help="Also prevent lid-close sleep (Linux: native, Windows: admin required)",
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"steamdc v{__version__}",
    )
    return p


def run() -> None:
    args = build_parser().parse_args()

    if args.gui:
        try:
            from .ui_gui import run_gui
            run_gui()
            return
        except ImportError:
            print("[!] GUI dependencies not installed.")
            print("    Install with: pip install steamdc[gui]")
            sys.exit(1)

    steam_root = steam.find_steam_root()
    if steam_root is None:
        print("[!] Steam installation not found.")
        print("    Make sure Steam is installed, or specify the path manually.")
        sys.exit(1)

    library_folders = steam.find_library_folders(steam_root)
    if not library_folders:
        print("[!] No Steam library folders found.")
        sys.exit(1)

    print(f"[*] Steam root: {steam_root}")
    print("[*] Library folders:")
    for f in library_folders:
        print(f"      {f}")
    print()

    if not shutdown.can_shutdown() and not args.dry_run:
        print("[!] Shutdown not available on this system.")
        print("    Use --dry-run to monitor without shutting down.")
        sys.exit(1)

    _print_sleep_messages(args)

    if not args.no_rich:
        try:
            from .ui_rich import run_rich_monitor

            run_rich_monitor(
                library_folders=library_folders,
                interval=args.interval,
                stall_timeout=args.stall_timeout,
                shutdown_delay=args.shutdown_delay,
                dry_run=args.dry_run,
                no_sleep=not args.allow_sleep,
                no_sleep_lid=args.no_sleep_lid,
            )
            return
        except ImportError:
            pass

    run_plain_monitor(
        library_folders=library_folders,
        interval=args.interval,
        stall_timeout=args.stall_timeout,
        shutdown_delay=args.shutdown_delay,
        dry_run=args.dry_run,
        no_sleep=not args.allow_sleep,
        no_sleep_lid=args.no_sleep_lid,
    )


def _print_sleep_messages(args: argparse.Namespace) -> None:
    if args.allow_sleep:
        print("[*] Sleep prevention disabled (--allow-sleep)")
        return
    can_sleep = can_prevent_sleep()
    can_lid = can_prevent_lid_sleep() if args.no_sleep_lid else None
    if can_sleep:
        print("[*] Wake-lock active — system will not idle-sleep")
    else:
        print("[*] Wake-lock not available on this system")
    if args.no_sleep_lid:
        if can_lid:
            print("[*] Lid-close sleep prevented")
        else:
            print("[*] Lid-close prevention not available (admin required on Windows)")


def run_plain_monitor(
    library_folders: list,
    interval: int,
    stall_timeout: int,
    shutdown_delay: int,
    dry_run: bool,
    no_sleep: bool = True,
    no_sleep_lid: bool = False,
) -> None:
    def on_progress(state: monitor.MonitorState) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        if state.all_done:
            print(f"[{now}] All downloads complete!")
            return
        total_mb = state.overall_bytes / (1024 * 1024)
        done_mb = state.overall_downloaded / (1024 * 1024)
        pct = (done_mb / total_mb * 100) if total_mb > 0 else 0
        status = (
            f"[{now}] Downloads: {len(state.active_downloads)} active,"
            f" {len(state.staging_apps)} staging"
        )
        if state.active_downloads:
            status += f" | {pct:.1f}% ({done_mb:.0f}/{total_mb:.0f} MB)"
        print(status)
        for d in state.active_downloads:
            bar_len = 20
            filled = int(d.percent / 100 * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            dmb = d.downloaded_bytes / (1024 * 1024)
            tmb = d.total_bytes / (1024 * 1024)
            print(f"  {d.name}: |{bar}| {d.percent:.1f}% ({dmb:.0f}/{tmb:.0f} MB)")

    def on_shutdown() -> None:
        if dry_run:
            print("[*] Dry-run — would have shut down.")
        else:
            print(f"\n[*] Shutting down in {shutdown_delay} seconds... (Ctrl+C to cancel)")
            try:
                time.sleep(shutdown_delay)
            except KeyboardInterrupt:
                print("\n[*] Shutdown cancelled by user.")
                sys.exit(0)
            shutdown.shutdown_system()

    def handle_sigint(sig, frame) -> None:
        print("\n[*] Monitoring cancelled by user.")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    print("[*] Monitoring Steam downloads... (Ctrl+C to cancel)")
    if dry_run:
        print("[*] DRY RUN — system will not shut down.\n")
    else:
        print(f"[*] System will shut down {shutdown_delay}s after downloads complete.\n")

    _run_with_sleep_lock(
        no_sleep, no_sleep_lid,
        monitor.monitor_loop,
        library_folders=library_folders,
        interval=interval,
        stall_timeout=stall_timeout,
        on_progress=on_progress,
        on_shutdown=on_shutdown,
        dry_run=dry_run,
    )


def _run_with_sleep_lock(
    no_sleep: bool,
    no_sleep_lid: bool,
    target, /, **kwargs,
) -> None:
    if no_sleep:
        with prevent_sleep(lid_close=no_sleep_lid) as msgs:
            for m in msgs:
                print(f"[*] {m}")
            target(**kwargs)
    else:
        target(**kwargs)
