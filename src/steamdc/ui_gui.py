from __future__ import annotations

import threading
import time
import urllib.request
from pathlib import Path
from typing import Callable

import customtkinter as ctk

from . import monitor, shutdown, steam
from .wakelock import prevent_sleep

IMG_CACHE_DIR = Path.home() / ".cache" / "steamdc" / "headers"
IMG_SIZE = (184, 69)
STEAM_IMG_URL = "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{}/header.jpg"


def _try_load_image(app_id: str) -> ctk.CTkImage | None:
    try:
        from PIL import Image
    except ImportError:
        return None

    IMG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = IMG_CACHE_DIR / f"{app_id}.jpg"

    if not path.exists():
        try:
            urllib.request.urlretrieve(STEAM_IMG_URL.format(app_id), path)
        except Exception:
            return None

    try:
        pil = Image.open(path)
        return ctk.CTkImage(pil, size=IMG_SIZE)
    except Exception:
        return None


def run_gui() -> None:
    root = steam.find_steam_root()
    if root is None:
        _show_error("Steam installation not found.",
                     "Make sure Steam is installed.")
        return

    libs = steam.find_library_folders(root)
    if not libs:
        _show_error("No Steam library folders found.")
        return

    app = DCSApp(libs)
    app.mainloop()


def _show_error(msg: str, detail: str = "") -> None:
    root = ctk.CTk()
    root.title("SteamDC — Error")
    root.geometry("420x150")
    root.resizable(False, False)
    ctk.CTkLabel(root, text=msg, font=("", 16)).pack(expand=True)
    if detail:
        ctk.CTkLabel(root, text=detail).pack()
    ctk.CTkButton(root, text="OK", command=root.destroy).pack(pady=(10, 15))
    root.mainloop()


class DCSApp(ctk.CTk):
    def __init__(self, library_folders: list[Path]):
        super().__init__()
        self.library_folders = library_folders
        self.title("SteamDC — Download Completion Shutdown")
        self.geometry("680x540")
        self.minsize(520, 420)
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self._selection_frame: SelectionFrame | None = None
        self._monitoring_frame: MonitoringFrame | None = None

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._show_selection()

    def _show_selection(self):
        if self._monitoring_frame is not None:
            self._monitoring_frame.stop()
            self._monitoring_frame.destroy()
            self._monitoring_frame = None
        self._selection_frame = SelectionFrame(self, self.library_folders, self._on_start)
        self._selection_frame.pack(fill="both", expand=True)

    def _on_start(self, target_app_ids: set[str], no_sleep: bool, no_sleep_lid: bool):
        if self._selection_frame is not None:
            self._selection_frame.destroy()
            self._selection_frame = None
        self._monitoring_frame = MonitoringFrame(
            self, self.library_folders, target_app_ids, self._show_selection,
            no_sleep=no_sleep, no_sleep_lid=no_sleep_lid,
        )
        self._monitoring_frame.pack(fill="both", expand=True)

    def _on_close(self):
        if self._monitoring_frame is not None:
            self._monitoring_frame.stop()
        self.destroy()


class SelectionFrame(ctk.CTkFrame):
    def __init__(
        self, master: ctk.CTk,
        library_folders: list[Path],
        on_start: Callable[[set[str], bool, bool], None],
    ):
        super().__init__(master)
        self.library_folders = library_folders
        self.on_start = on_start
        self.check_vars: dict[str, ctk.BooleanVar] = {}
        self.no_sleep_var = ctk.BooleanVar(value=True)
        self.no_sleep_lid_var = ctk.BooleanVar(value=False)
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="SteamDC", font=("", 22, "bold")).pack(pady=(20, 0))
        ctk.CTkLabel(
            self, text="Select which downloads to wait for:", font=("", 14),
        ).pack(pady=(5, 12))

        self.select_all_var = ctk.BooleanVar(value=True)
        self.select_all_cb = ctk.CTkCheckBox(
            self, text="Select All", variable=self.select_all_var,
            command=self._toggle_all,
        )
        self.select_all_cb.pack(pady=(0, 6))

        self.scroll_frame = ctk.CTkScrollableFrame(self, height=280)
        self.scroll_frame.pack(fill="both", expand=True, padx=18, pady=5)

        self.status_label = ctk.CTkLabel(self, text="", font=("", 12))
        self.status_label.pack(pady=(0, 5))

        sleep_frame = ctk.CTkFrame(self, fg_color="transparent")
        sleep_frame.pack(pady=(0, 6))

        ctk.CTkCheckBox(
            sleep_frame, text="Prevent system sleep",
            variable=self.no_sleep_var,
        ).pack(side="left", padx=8)

        self.lid_cb = ctk.CTkCheckBox(
            sleep_frame, text="Prevent lid-close sleep",
            variable=self.no_sleep_lid_var,
        )
        self.lid_cb.pack(side="left", padx=8)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(0, 12))

        self.start_btn = ctk.CTkButton(
            btn_frame, text="Start Monitoring", width=180,
            command=self._start,
        )
        self.start_btn.pack(side="left", padx=6)

        ctk.CTkButton(
            btn_frame, text="Quit", width=100,
            command=self.master._on_close,
        ).pack(side="left", padx=6)

        self._scan()

    def _scan(self):
        state = monitor.check_downloads(self.library_folders)
        if not state.active_downloads:
            self.status_label.configure(
                text="No active downloads detected.\n"
                      "Make sure Steam is running and downloading something.",
                text_color="orange",
            )
            self.start_btn.configure(state="disabled")
            self.select_all_cb.configure(state="disabled")
            return

        for child in self.scroll_frame.winfo_children():
            child.destroy()

        for dl in state.active_downloads:
            var = ctk.BooleanVar(value=True)
            self.check_vars[dl.app_id] = var
            ctk.CTkCheckBox(
                self.scroll_frame,
                text=(
                    f"{dl.name}  ({dl.mb_downloaded:.0f} / {dl.mb_total:.0f} MB,"
                    f" {dl.percent:.1f}%)"
                ),
                variable=var,
            ).pack(anchor="w", pady=3, padx=5)

    def _toggle_all(self):
        val = self.select_all_var.get()
        for var in self.check_vars.values():
            var.set(val)

    def _start(self):
        selected = {aid for aid, var in self.check_vars.items() if var.get()}
        if not selected:
            self.status_label.configure(text="Select at least one game.", text_color="red")
            return
        self.on_start(selected, self.no_sleep_var.get(), self.no_sleep_lid_var.get())


class MonitoringFrame(ctk.CTkFrame):
    def __init__(
        self, master: ctk.CTk,
        library_folders: list[Path],
        target_app_ids: set[str],
        on_cancel: Callable[[], None],
        interval: int = 5,
        stall_timeout: int = 120,
        shutdown_delay: int = 5,
        dry_run: bool = False,
        no_sleep: bool = True,
        no_sleep_lid: bool = False,
    ):
        super().__init__(master)
        self.library_folders = library_folders
        self.target_app_ids = target_app_ids
        self.on_cancel = on_cancel
        self.interval = interval
        self.stall_timeout = stall_timeout
        self.shutdown_delay = shutdown_delay
        self.dry_run = dry_run
        self.no_sleep = no_sleep
        self.no_sleep_lid = no_sleep_lid
        self._cancelled = False
        self._latest_state: monitor.MonitorState | None = None
        self._countdown_val: int | None = None
        self._monitor_thread: threading.Thread | None = None
        self._wake_lock: object | None = None
        self._anim_id: str | None = None
        self._poll_id: str | None = None
        self._anim_states: dict[str, int] = {}
        self._card_img_labels: dict[str, ctk.CTkLabel] = {}
        self._card_status_labels: dict[str, ctk.CTkLabel] = {}
        self._build()

    def _build(self):
        self.title_label = ctk.CTkLabel(
            self, text="Waiting for downloads\u2026", font=("", 18, "bold"),
        )
        self.title_label.pack(pady=(18, 6))

        self.card_scroll = ctk.CTkScrollableFrame(self)
        self.card_scroll.pack(fill="both", expand=True, padx=30, pady=5)

        state = monitor.check_downloads(self.library_folders)
        name_map = {d.app_id: d.name for d in state.active_downloads}

        for app_id in sorted(self.target_app_ids):
            name = name_map.get(app_id, f"App {app_id}")
            self._anim_states[app_id] = 0

            card = ctk.CTkFrame(self.card_scroll, corner_radius=8)
            card.pack(fill="x", padx=10, pady=6)

            img_label = ctk.CTkLabel(
                card, text=name, font=("", 13),
                fg_color=("gray80", "gray30"),
                width=IMG_SIZE[0], height=IMG_SIZE[1],
                corner_radius=6,
            )
            img_label.pack(pady=(10, 4))

            ctk.CTkLabel(card, text=name, font=("", 15, "bold")).pack()

            status = ctk.CTkLabel(card, text="", font=("", 12))
            status.pack(pady=(2, 10))

            self._card_img_labels[app_id] = img_label
            self._card_status_labels[app_id] = status

        self.footer_label = ctk.CTkLabel(
            self,
            text="Your PC will shut down after the selected downloads complete.",
            font=("", 11),
            text_color="gray",
        )
        self.footer_label.pack(pady=(6, 5))

        ctk.CTkButton(
            self, text="Cancel", width=120,
            command=self._cancel,
        ).pack(pady=(0, 12))

        self._start_image_loading()
        self._start_thread()

    def _start_image_loading(self):
        def load_all():
            for app_id in self.target_app_ids:
                if self._cancelled:
                    return
                img = _try_load_image(app_id)
                if img is not None:
                    self.after(0, self._set_card_image, app_id, img)
        threading.Thread(target=load_all, daemon=True).start()

    def _set_card_image(self, app_id: str, img: ctk.CTkImage) -> None:
        if app_id in self._card_img_labels:
            self._card_img_labels[app_id].configure(image=img, text="", fg_color="transparent")

    def _start_thread(self):
        self._monitor_thread = threading.Thread(target=self._run, daemon=True)
        self._monitor_thread.start()
        self._poll_id = self.after(150, self._poll)
        self._anim_id = self.after(500, self._tick_animation)

    def _tick_animation(self):
        if self._cancelled:
            return
        dots_arr = ["", ".", "..", "..."]
        for app_id, label in self._card_status_labels.items():
            self._anim_states[app_id] = (self._anim_states[app_id] + 1) % 4
            label.configure(text=f"Downloading {dots_arr[self._anim_states[app_id]]}")
        self._anim_id = self.after(500, self._tick_animation)

    def _run(self):
        def on_progress(state: monitor.MonitorState) -> None:
            self._latest_state = state

        def on_shutdown() -> None:
            if self.dry_run:
                return
            for i in range(self.shutdown_delay, 0, -1):
                if self._cancelled:
                    return
                self._countdown_val = i
                time.sleep(1)
            if not self._cancelled:
                shutdown.shutdown_system()

        if self.no_sleep:
            ctx = prevent_sleep(lid_close=self.no_sleep_lid)
            self._wake_lock = ctx.__enter__()
        else:
            self._wake_lock = None

        try:
            monitor.monitor_loop(
                library_folders=self.library_folders,
                interval=self.interval,
                stall_timeout=self.stall_timeout,
                on_progress=on_progress,
                on_shutdown=on_shutdown,
                dry_run=self.dry_run,
                target_app_ids=self.target_app_ids,
            )
        finally:
            if self._wake_lock is not None:
                self._wake_lock.__exit__(None, None, None)
                self._wake_lock = None

    def _poll(self):
        if self._cancelled:
            return
        state = self._latest_state
        if state is not None:
            self._update_ui(state)
        self._poll_id = self.after(200, self._poll)

    def _update_ui(self, state: monitor.MonitorState):
        if state.all_done:
            cv = self._countdown_val
            if cv is not None and cv > 0:
                self.title_label.configure(
                    text=f"Shutting down in {cv} seconds\u2026",
                    text_color="yellow",
                )
            else:
                self.title_label.configure(text="Downloads complete!", text_color="green")
            return

    def _cancel(self):
        self._cancelled = True
        if self._anim_id:
            self.after_cancel(self._anim_id)
            self._anim_id = None
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None
        self.on_cancel()

    def stop(self):
        self._cancelled = True
        if self._anim_id:
            self.after_cancel(self._anim_id)
            self._anim_id = None
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None
