from __future__ import annotations

import logging
import signal
import sys
import time
from datetime import datetime

from . import monitor, shutdown
from .wakelock import prevent_sleep

logger = logging.getLogger(__name__)


class _NopContext:
    def __enter__(self):
        return []

    def __exit__(self, *exc):
        pass


def run_rich_monitor(
    library_folders: list,
    interval: int,
    stall_timeout: int,
    shutdown_delay: int,
    dry_run: bool,
    no_sleep: bool = True,
) -> None:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress_bar import ProgressBar
    from rich.table import Table
    from rich.text import Text

    console = Console()

    def make_display(state: monitor.MonitorState) -> Panel:
        now = datetime.now().strftime("%H:%M:%S")
        if state.all_done:
            grid = Table.grid(padding=1)
            grid.add_row("[bold green]All downloads complete![/]")
            return Panel(grid, title=f"SteamDC @ {now}", border_style="green")

        dl_count = len(state.active_downloads)
        staging_count = len(state.staging_apps)
        total_mb = state.overall_bytes / monitor._BYTES_PER_MB
        done_mb = state.overall_downloaded / monitor._BYTES_PER_MB
        overall_pct = (done_mb / total_mb * 100) if total_mb > 0 else 0

        grid = Table.grid(padding=(0, 1))
        grid.add_column(justify="left", ratio=1)

        status_text = Text.assemble(
            ("Downloads: ", "bold"),
            (f"{dl_count} active", "green" if dl_count else "dim"),
            (", ", ""),
            (f"{staging_count} staging", "yellow" if staging_count else "dim"),
        )
        grid.add_row(status_text)

        grid.add_row(
            f"Overall: {overall_pct:.1f}% ({done_mb:.0f}/{total_mb:.0f} MB)"
        )
        bar = ProgressBar(
            total=state.overall_bytes or 1,
            completed=state.overall_downloaded,
            width=40,
        )
        grid.add_row(bar)

        if dl_count == 0 and staging_count > 0:
            grid.add_row("[yellow]Post-download staging in progress...[/]")

        for d in state.active_downloads:
            dmb = d.downloaded_bytes / monitor._BYTES_PER_MB
            tmb = d.total_bytes / monitor._BYTES_PER_MB
            sub = Table.grid(padding=(0, 1))
            sub.add_column(justify="left")
            sub.add_row(
                f"[cyan]{d.name}[/]  {d.percent:.1f}% ({dmb:.0f}/{tmb:.0f} MB)"
            )
            pbar = ProgressBar(
                total=d.total_bytes or 1,
                completed=d.downloaded_bytes,
                width=35,
            )
            sub.add_row(pbar)
            grid.add_row(sub)

        if state.stall_seconds > 0 and state.stall_seconds >= interval * 2:
            grid.add_row(
                f"[dim yellow]Download stalled ({state.stall_seconds}s)[/]"
            )

        if dry_run:
            border = "blue"
            title = f"SteamDC @ {now} [DRY RUN]"
        else:
            border = "cyan"
            title = f"SteamDC @ {now}"

        return Panel(grid, title=title, border_style=border)

    state_ref = [None]

    wl_ctx = prevent_sleep() if no_sleep else _NopContext()
    with wl_ctx as wl_msgs:
        for m in wl_msgs:
            console.print(f"[dim]{m}[/]")

        with Live(console=console, screen=False, refresh_per_second=2) as live:
            def signal_handler(sig, frame) -> None:
                logger.info("Monitoring cancelled by user (SIGINT)")
                live.stop()
                console.print("\n[bold yellow]Monitoring cancelled by user.[/]")
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)

            console.print("[bold]SteamDC[/] — Download Completion Shutdown for Steam")
            if dry_run:
                console.print("[bold blue]DRY RUN[/] — system will not shut down.\n")
            else:
                console.print(f"[dim]System will shut down {shutdown_delay}s after downloads complete.[/]\n")

            def on_progress(state: monitor.MonitorState) -> None:
                state_ref[0] = state
                live.update(make_display(state))

            def on_shutdown() -> None:
                if dry_run:
                    logger.info("Dry run — shutdown skipped")
                    console.print("[blue]Dry-run — would have shut down.[/]")
                else:
                    logger.info("Downloads complete, shutdown countdown: %ds", shutdown_delay)
                    console.print("[bold green]Downloads complete![/]")
                    console.print(f"[yellow]Shutting down in {shutdown_delay} seconds... (Ctrl+C to cancel)[/]")
                    try:
                        for i in range(shutdown_delay, 0, -1):
                            logger.debug("Shutdown countdown: %ds", i)
                            live.update(
                                Panel(
                                    f"[bold yellow]Shutting down in {i} seconds...[/]",
                                    border_style="yellow",
                                )
                            )
                            time.sleep(1)
                        live.stop()
                        shutdown.shutdown_system()
                    except KeyboardInterrupt:
                        logger.info("Shutdown cancelled by user in Rich UI")
                        live.stop()
                        console.print("\n[bold yellow]Shutdown cancelled by user.[/]")
                        sys.exit(0)

            monitor.monitor_loop(
                library_folders=library_folders,
                interval=interval,
                stall_timeout=stall_timeout,
                on_progress=on_progress,
                on_shutdown=on_shutdown,
                dry_run=dry_run,
            )
