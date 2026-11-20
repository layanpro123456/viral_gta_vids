"""ViceClip Archiver: Modern Dark-Mode Desktop GUI (CustomTkinter)."""

from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
import threading
from typing import Any, List, Optional
import webbrowser

import customtkinter as ctk

from viceclip.application.discover import DiscoverVideosUseCase
from viceclip.application.download import ProcessDownloadQueueUseCase
from viceclip.application.ingest import IngestVideoUseCase
from viceclip.domain.entities import CatalogStats, VideoRecord
from viceclip.domain.enums import Platform, VideoStatus
from viceclip.infrastructure.adapters.facebook import FacebookAdapter
from viceclip.infrastructure.adapters.reddit import RedditAdapter
from viceclip.infrastructure.adapters.youtube import YouTubeAdapter
from viceclip.infrastructure.config import AppConfig
from viceclip.infrastructure.downloader.ytdlp_acl import YtDlpDownloader
from viceclip.infrastructure.storage.file_store import LocalFileSystemStorage
from viceclip.infrastructure.storage.sqlite_repo import SQLiteVideoRepository

# Appearance Settings
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# Brand Colors
COLOR_BG = "#0B0818"
COLOR_SIDEBAR = "#110D24"
COLOR_CARD = "#171230"
COLOR_CARD_HOVER = "#211A42"
COLOR_PINK = "#FF2A85"
COLOR_PINK_HOVER = "#D81B6D"
COLOR_CYAN = "#00F0FF"
COLOR_CYAN_HOVER = "#00C2CF"
COLOR_TEXT_DIM = "#9E9AA8"
COLOR_TEXT_MAIN = "#FFFFFF"


def open_folder(path: str) -> None:
    """Open folder in OS default file manager."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    abs_path = str(p.resolve())
    if sys.platform == "win32":
        os.startfile(abs_path)
    elif sys.platform == "darwin":
        subprocess.run(["open", abs_path], check=False)
    else:
        subprocess.run(["xdg-open", abs_path], check=False)


class ViceClipDesktopApp(ctk.CTk):
    """Main ViceClip Archiver Desktop Application."""

    def __init__(self, config_path: str = "config.toml") -> None:
        super().__init__()
        self.config_path = config_path

        # Core Engine Initialization
        self.cfg = AppConfig.load(self.config_path)
        self.repo = SQLiteVideoRepository(self.cfg.database.db_path)
        self.storage = LocalFileSystemStorage()
        self.downloader = YtDlpDownloader(max_duration_seconds=self.cfg.archiver.max_duration_seconds)

        # Window Setup
        self.title("ViceClip Archiver — GTA 6 Viral Discovery & Archival Engine")
        self.geometry("1120x720")
        self.minsize(980, 640)
        self.configure(fg_color=COLOR_BG)

        # Layout: Grid 1x2 (Sidebar + Content Area)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._build_sidebar()
        self._build_content_area()

        # Start on Discovery View
        self.select_tab("discover")
        self.update_stats()

    # ==================== SIDEBAR ====================
    def _build_sidebar(self) -> None:
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=COLOR_SIDEBAR)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar_frame.grid_rowconfigure(7, weight=1)

        # App Brand Header
        self.brand_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="VICECLIP",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=COLOR_PINK,
        )
        self.brand_label.grid(row=0, column=0, padx=20, pady=(24, 0), sticky="w")

        self.sub_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="GTA 6 ARCHIVER",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_CYAN,
        )
        self.sub_label.grid(row=1, column=0, padx=22, pady=(0, 20), sticky="w")

        # Nav Buttons
        self.btn_discover = self._create_nav_button("🔍  Discovery", lambda: self.select_tab("discover"), 2)
        self.btn_ingest = self._create_nav_button("⚡  Direct Ingest", lambda: self.select_tab("ingest"), 3)
        self.btn_queue = self._create_nav_button("📥  Download Queue", lambda: self.select_tab("queue"), 4)
        self.btn_stats = self._create_nav_button("📊  Catalog Stats", lambda: self.select_tab("stats"), 5)
        self.btn_settings = self._create_nav_button("⚙️  Settings", lambda: self.select_tab("settings"), 6)

        # Bottom Info
        self.footer_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="v0.1.0 • Non-DRM Safe",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_DIM,
        )
        self.footer_label.grid(row=8, column=0, padx=20, pady=15, sticky="s")

    def _create_nav_button(self, text: str, command: Any, row: int) -> ctk.CTkButton:
        btn = ctk.CTkButton(
            self.sidebar_frame,
            text=text,
            command=command,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="transparent",
            text_color=COLOR_TEXT_MAIN,
            hover_color=COLOR_CARD,
            anchor="w",
            height=42,
            corner_radius=8,
        )
        btn.grid(row=row, column=0, padx=14, pady=6, sticky="ew")
        return btn

    # ==================== MAIN CONTENT AREA ====================
    def _build_content_area(self) -> None:
        self.content_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=COLOR_BG)
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # Tab Frames Container
        self.tabs: dict[str, ctk.CTkFrame] = {
            "discover": self._create_discover_tab(),
            "ingest": self._create_ingest_tab(),
            "queue": self._create_queue_tab(),
            "stats": self._create_stats_tab(),
            "settings": self._create_settings_tab(),
        }

    def select_tab(self, tab_name: str) -> None:
        """Switch active view and highlight current nav item."""
        for name, frame in self.tabs.items():
            if name == tab_name:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()

        # Update button highlights
        buttons = {
            "discover": self.btn_discover,
            "ingest": self.btn_ingest,
            "queue": self.btn_queue,
            "stats": self.btn_stats,
            "settings": self.btn_settings,
        }
        for name, btn in buttons.items():
            if name == tab_name:
                btn.configure(fg_color=COLOR_PINK, text_color="#FFFFFF")
            else:
                btn.configure(fg_color="transparent", text_color=COLOR_TEXT_MAIN)

        if tab_name == "stats":
            self.update_stats()
        elif tab_name == "queue":
            self.refresh_queue_table()

    # ==================== TAB 1: DISCOVERY ====================
    def _create_discover_tab(self) -> ctk.CTkFrame:
        tab = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        # Top Control Card
        ctrl = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        ctrl.grid(row=0, column=0, sticky="ew", pady=(0, 15), padx=0)
        ctrl.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            ctrl, text="🔍 Trending Content Discovery", font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, columnspan=3, padx=16, pady=(14, 8), sticky="w")

        # Platform checkmarks
        plat_frame = ctk.CTkFrame(ctrl, fg_color="transparent")
        plat_frame.grid(row=1, column=0, columnspan=3, padx=16, pady=4, sticky="w")

        self.cb_yt = ctk.CTkCheckBox(plat_frame, text="YouTube Data API", text_color=COLOR_TEXT_MAIN)
        self.cb_yt.select()
        self.cb_yt.pack(side="left", padx=(0, 16))

        self.cb_reddit = ctk.CTkCheckBox(plat_frame, text="Reddit (r/GTA6)", text_color=COLOR_TEXT_MAIN)
        self.cb_reddit.select()
        self.cb_reddit.pack(side="left", padx=(0, 16))

        self.cb_fb = ctk.CTkCheckBox(plat_frame, text="Facebook (Reels & Pages)", text_color=COLOR_TEXT_MAIN)
        self.cb_fb.select()
        self.cb_fb.pack(side="left", padx=(0, 16))

        # Query Keywords & Virality Threshold
        input_frame = ctk.CTkFrame(ctrl, fg_color="transparent")
        input_frame.grid(row=2, column=0, columnspan=3, padx=16, pady=(8, 16), sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)

        self.disc_keyword_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Keywords (comma-separated, e.g. GTA 6, Vice City, #GTA6)",
            height=38,
        )
        self.disc_keyword_entry.insert(0, ", ".join(self.cfg.discovery.keywords))
        self.disc_keyword_entry.grid(row=0, column=0, sticky="ew", padx=(0, 12))

        self.btn_run_discovery = ctk.CTkButton(
            input_frame,
            text="Run Discovery",
            command=self._on_run_discovery,
            fg_color=COLOR_PINK,
            hover_color=COLOR_PINK_HOVER,
            font=ctk.CTkFont(weight="bold"),
            height=38,
            width=140,
        )
        self.btn_run_discovery.grid(row=0, column=1)

        # Status & Results Heading
        self.disc_status_label = ctk.CTkLabel(
            tab, text="Ready to query platforms.", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_DIM
        )
        self.disc_status_label.grid(row=1, column=0, sticky="w", pady=(0, 6))

        # Scrollable candidates list
        self.disc_scroll = ctk.CTkScrollableFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        self.disc_scroll.grid(row=2, column=0, sticky="nsew")
        self.disc_scroll.grid_columnconfigure(1, weight=1)

        return tab

    def _on_run_discovery(self) -> None:
        self.btn_run_discovery.configure(state="disabled", text="Discovering...")
        self.disc_status_label.configure(text="Querying enabled platforms and computing virality scores...", text_color=COLOR_CYAN)

        def worker() -> None:
            raw_kws = self.disc_keyword_entry.get()
            keywords = [k.strip() for k in raw_kws.split(",") if k.strip()]
            self.cfg.discovery.keywords = keywords

            adapters = []
            if self.cb_yt.get() and self.cfg.youtube_api_key:
                adapters.append(YouTubeAdapter(api_key=self.cfg.youtube_api_key))
            if self.cb_reddit.get():
                adapters.append(RedditAdapter(subreddit="GTA6", user_agent=self.cfg.reddit_user_agent))
            if self.cb_fb.get() and self.cfg.facebook_access_token:
                adapters.append(FacebookAdapter(access_token=self.cfg.facebook_access_token, page_ids=self.cfg.facebook.page_ids))

            use_case = DiscoverVideosUseCase(
                repository=self.repo,
                adapters=adapters,
                settings=self.cfg.discovery,
                max_duration_seconds=self.cfg.archiver.max_duration_seconds,
            )
            res = use_case.execute(max_results_per_adapter=25)

            # UI Update on main thread
            self.after(0, lambda: self._render_discovery_results(res))

        threading.Thread(target=worker, daemon=True).start()

    def _render_discovery_results(self, res: Any) -> None:
        self.btn_run_discovery.configure(state="normal", text="Run Discovery")
        self.disc_status_label.configure(
            text=f"Found: {res.total_found} | Newly Queued: {res.newly_queued} | Promoted: {res.promoted_to_queued} | Skipped: {res.skipped}",
            text_color="#10B981" if res.newly_queued > 0 else COLOR_TEXT_MAIN,
        )

        # Clear scroll area
        for widget in self.disc_scroll.winfo_children():
            widget.destroy()

        if not res.records:
            ctk.CTkLabel(
                self.disc_scroll,
                text="No new candidates discovered for configured criteria.",
                text_color=COLOR_TEXT_DIM,
            ).pack(pady=20)
            return

        for idx, rec in enumerate(res.records):
            item_frame = ctk.CTkFrame(self.disc_scroll, fg_color=COLOR_SIDEBAR, corner_radius=8)
            item_frame.pack(fill="x", padx=8, pady=4)
            item_frame.grid_columnconfigure(1, weight=1)

            # Platform Tag
            plat_color = "#FF0000" if rec.platform == Platform.YOUTUBE else ("#FF4500" if rec.platform == Platform.REDDIT else "#1877F2")
            ctk.CTkLabel(
                item_frame, text=f" {rec.platform.upper()} ", fg_color=plat_color, corner_radius=4,
                font=ctk.CTkFont(size=10, weight="bold"), text_color="#FFFFFF"
            ).grid(row=0, column=0, padx=8, pady=8)

            # Title & Creator
            info_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
            info_frame.grid(row=0, column=1, sticky="w", padx=4)
            ctk.CTkLabel(
                info_frame, text=rec.title[:65], font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
            ).pack(anchor="w")
            ctk.CTkLabel(
                info_frame,
                text=f"{rec.creator} • {rec.views:,} views • Score: {rec.virality_score:.2f}",
                font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_DIM, anchor="w"
            ).pack(anchor="w")

            # Status Badge
            stat_color = "#10B981" if rec.status == VideoStatus.QUEUED else ("#3B82F6" if rec.status == VideoStatus.ARCHIVED else COLOR_TEXT_DIM)
            ctk.CTkLabel(
                item_frame, text=rec.status, text_color=stat_color, font=ctk.CTkFont(size=12, weight="bold")
            ).grid(row=0, column=2, padx=12)

    # ==================== TAB 2: DIRECT INGEST ====================
    def _create_ingest_tab(self) -> ctk.CTkFrame:
        tab = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        card.pack(fill="x", padx=0, pady=(0, 20))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card, text="⚡ Direct Video URL Ingestion", font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, padx=20, pady=(18, 6), sticky="w")

        ctk.CTkLabel(
            card,
            text="Paste any public video link from Facebook (Reel/Video), YouTube, or Reddit.\nExtracts stream details, calculates virality score, and enqueues or downloads immediately.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_DIM,
            justify="left",
        ).grid(row=1, column=0, padx=20, pady=(0, 16), sticky="w")

        self.ingest_url_entry = ctk.CTkEntry(
            card, placeholder_text="Enter video URL (e.g. https://www.facebook.com/reel/... or https://youtu.be/...)", height=42
        )
        self.ingest_url_entry.grid(row=2, column=0, padx=20, pady=8, sticky="ew")

        # Action Buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.grid(row=3, column=0, padx=20, pady=(10, 20), sticky="w")

        self.btn_ingest_queue = ctk.CTkButton(
            btn_frame, text="Add to Queue", command=lambda: self._on_ingest(download_now=False),
            fg_color=COLOR_CYAN, hover_color=COLOR_CYAN_HOVER, text_color="#000000", font=ctk.CTkFont(weight="bold"), height=36
        )
        self.btn_ingest_queue.pack(side="left", padx=(0, 12))

        self.btn_ingest_download = ctk.CTkButton(
            btn_frame, text="Download Now", command=lambda: self._on_ingest(download_now=True),
            fg_color=COLOR_PINK, hover_color=COLOR_PINK_HOVER, font=ctk.CTkFont(weight="bold"), height=36
        )
        self.btn_ingest_download.pack(side="left")

        # Result Details Card
        self.ingest_result_card = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        self.ingest_result_card.pack(fill="both", expand=True)
        self.ingest_result_card.grid_columnconfigure(0, weight=1)

        self.ingest_status_lbl = ctk.CTkLabel(
            self.ingest_result_card, text="Waiting for URL input...", font=ctk.CTkFont(size=13), text_color=COLOR_TEXT_DIM
        )
        self.ingest_status_lbl.pack(pady=30)

        return tab

    def _on_ingest(self, download_now: bool) -> None:
        url = self.ingest_url_entry.get().strip()
        if not url:
            self.ingest_status_lbl.configure(text="Please enter a valid URL.", text_color="#EF4444")
            return

        self.ingest_status_lbl.configure(text="Extracting stream details and evaluating virality...", text_color=COLOR_CYAN)

        def worker() -> None:
            use_case = IngestVideoUseCase(
                repository=self.repo,
                settings=self.cfg.discovery,
                max_duration_seconds=self.cfg.archiver.max_duration_seconds,
            )
            rec, qualified, reason = use_case.ingest_url(url, force_queue=True)

            if download_now:
                down_uc = ProcessDownloadQueueUseCase(
                    repository=self.repo,
                    downloader=self.downloader,
                    storage=self.storage,
                    settings=self.cfg.archiver,
                )
                res = down_uc.execute(limit=1)
                rec = self.repo.get_by_platform_id(rec.platform, rec.platform_id) or rec

            self.after(0, lambda: self._show_ingest_result(rec, download_now))

        threading.Thread(target=worker, daemon=True).start()

    def _show_ingest_result(self, rec: VideoRecord, was_downloaded: bool) -> None:
        for widget in self.ingest_result_card.winfo_children():
            widget.destroy()

        header = "Downloaded Successfully!" if was_downloaded and rec.status == VideoStatus.ARCHIVED else "Queued for Download"
        header_color = "#10B981" if rec.status in (VideoStatus.ARCHIVED, VideoStatus.QUEUED) else "#EF4444"

        ctk.CTkLabel(
            self.ingest_result_card, text=f"✔ {header}", font=ctk.CTkFont(size=18, weight="bold"), text_color=header_color
        ).pack(anchor="w", padx=20, pady=(20, 8))

        info_box = ctk.CTkFrame(self.ingest_result_card, fg_color=COLOR_SIDEBAR, corner_radius=8)
        info_box.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(info_box, text=f"Title: {rec.title}", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=14, pady=(10, 2))
        ctk.CTkLabel(info_box, text=f"Platform: {rec.platform.capitalize()} • Creator: {rec.creator}", text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=14, pady=2)
        ctk.CTkLabel(info_box, text=f"Views: {rec.views:,} • Likes: {rec.likes:,} • Virality Score: {rec.virality_score:.2f}", text_color=COLOR_CYAN).pack(anchor="w", padx=14, pady=(2, 10))

        if rec.local_path:
            ctk.CTkLabel(self.ingest_result_card, text=f"Media: {rec.local_path}", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=20, pady=4)
            ctk.CTkButton(
                self.ingest_result_card, text="Open in Folder", command=lambda: open_folder(str(Path(rec.local_path).parent)),
                fg_color=COLOR_CARD_HOVER, width=130
            ).pack(anchor="w", padx=20, pady=8)

    # ==================== TAB 3: DOWNLOAD QUEUE ====================
    def _create_queue_tab(self) -> ctk.CTkFrame:
        tab = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        # Control Card
        ctrl = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        ctrl.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        ctrl.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(ctrl, text="📥 Archival Download Queue", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, columnspan=3, padx=16, pady=(14, 8), sticky="w")

        # Action Buttons
        self.btn_start_download = ctk.CTkButton(
            ctrl, text="Process Queue", command=self._on_process_queue,
            fg_color=COLOR_PINK, hover_color=COLOR_PINK_HOVER, font=ctk.CTkFont(weight="bold"), height=36
        )
        self.btn_start_download.grid(row=1, column=0, padx=16, pady=(0, 16))

        self.btn_open_archive = ctk.CTkButton(
            ctrl, text="Open Archive Folder", command=lambda: open_folder(self.cfg.archiver.output_dir),
            fg_color=COLOR_CARD_HOVER, height=36
        )
        self.btn_open_archive.grid(row=1, column=1, padx=(0, 16), pady=(0, 16))

        self.queue_status_lbl = ctk.CTkLabel(tab, text="", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_DIM)
        self.queue_status_lbl.grid(row=1, column=0, sticky="w", pady=(0, 6))

        # Queue scroll list
        self.queue_scroll = ctk.CTkScrollableFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        self.queue_scroll.grid(row=2, column=0, sticky="nsew")
        self.queue_scroll.grid_columnconfigure(1, weight=1)

        return tab

    def refresh_queue_table(self) -> None:
        for widget in self.queue_scroll.winfo_children():
            widget.destroy()

        queued = self.repo.get_queued(limit=50)
        self.queue_status_lbl.configure(text=f"{len(queued)} video(s) currently waiting in queue.")

        if not queued:
            ctk.CTkLabel(self.queue_scroll, text="No videos in queue. Run discovery or ingest URLs to add items.", text_color=COLOR_TEXT_DIM).pack(pady=30)
            return

        for rec in queued:
            item = ctk.CTkFrame(self.queue_scroll, fg_color=COLOR_SIDEBAR, corner_radius=8)
            item.pack(fill="x", padx=8, pady=4)
            item.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(item, text=f" {rec.platform.upper()} ", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_CYAN).grid(row=0, column=0, padx=8, pady=8)
            info = ctk.CTkFrame(item, fg_color="transparent")
            info.grid(row=0, column=1, sticky="w", padx=4)
            ctk.CTkLabel(info, text=rec.title[:65], font=ctk.CTkFont(size=13, weight="bold"), anchor="w").pack(anchor="w")
            ctk.CTkLabel(info, text=f"{rec.creator} • Virality Score: {rec.virality_score:.2f}", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_DIM, anchor="w").pack(anchor="w")

            ctk.CTkLabel(item, text="QUEUED", font=ctk.CTkFont(size=12, weight="bold"), text_color="#10B981").grid(row=0, column=2, padx=14)

    def _on_process_queue(self) -> None:
        self.btn_start_download.configure(state="disabled", text="Archiving...")
        self.queue_status_lbl.configure(text="Downloading media streams and verifying checksums...", text_color=COLOR_CYAN)

        def worker() -> None:
            use_case = ProcessDownloadQueueUseCase(
                repository=self.repo,
                downloader=self.downloader,
                storage=self.storage,
                settings=self.cfg.archiver,
            )
            res = use_case.execute(limit=10)
            self.after(0, lambda: self._on_download_complete(res))

        threading.Thread(target=worker, daemon=True).start()

    def _on_download_complete(self, res: Any) -> None:
        self.btn_start_download.configure(state="normal", text="Process Queue")
        self.queue_status_lbl.configure(
            text=f"Batch complete: {res.succeeded} archived, {res.failed} failed.",
            text_color="#10B981" if res.succeeded > 0 else COLOR_TEXT_MAIN,
        )
        self.refresh_queue_table()

    # ==================== TAB 4: CATALOG STATS ====================
    def _create_stats_tab(self) -> ctk.CTkFrame:
        tab = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_columnconfigure(2, weight=1)

        # Title
        ctk.CTkLabel(tab, text="📊 Catalog Ledger Statistics", font=ctk.CTkFont(size=20, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 20)
        )

        # 6 Metric Cards
        self.stat_cards = {}
        cards_info = [
            ("total", "Total Discovered", 1, 0, COLOR_TEXT_MAIN),
            ("queued", "Waiting in Queue", 1, 1, COLOR_CYAN),
            ("archived", "Archived Files", 1, 2, "#10B981"),
            ("downloading", "In Flight", 2, 0, "#F59E0B"),
            ("skipped", "Filtered / Skipped", 2, 1, COLOR_TEXT_DIM),
            ("failed", "Failed / Error", 2, 2, "#EF4444"),
        ]

        for key, label, r, c, color in cards_info:
            card = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
            card.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_DIM).pack(pady=(18, 4))
            val_lbl = ctk.CTkLabel(card, text="0", font=ctk.CTkFont(size=32, weight="bold"), text_color=color)
            val_lbl.pack(pady=(0, 18))
            self.stat_cards[key] = val_lbl

        # Reconcile & Refresh
        btn_box = ctk.CTkFrame(tab, fg_color="transparent")
        btn_box.grid(row=3, column=0, columnspan=3, pady=25, sticky="w")

        ctk.CTkButton(btn_box, text="Refresh Statistics", command=self.update_stats, fg_color=COLOR_PINK, height=36).pack(side="left", padx=(0, 12))
        ctk.CTkButton(btn_box, text="Reconcile Crashed Tasks", command=self._reconcile_tasks, fg_color=COLOR_CARD_HOVER, height=36).pack(side="left")

        return tab

    def update_stats(self) -> None:
        stats = self.repo.get_stats()
        self.stat_cards["total"].configure(text=str(stats.total))
        self.stat_cards["queued"].configure(text=str(stats.queued))
        self.stat_cards["archived"].configure(text=str(stats.archived))
        self.stat_cards["downloading"].configure(text=str(stats.downloading))
        self.stat_cards["skipped"].configure(text=str(stats.skipped))
        self.stat_cards["failed"].configure(text=str(stats.failed))

    def _reconcile_tasks(self) -> None:
        recovered = self.repo.reconcile_crashed_tasks()
        self.update_stats()

    # ==================== TAB 5: SETTINGS ====================
    def _create_settings_tab(self) -> ctk.CTkFrame:
        tab = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(tab, text="⚙️ Archiver Configuration", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(0, 16))

        # Card: Archival Paths
        card1 = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        card1.pack(fill="x", pady=8)
        ctk.CTkLabel(card1, text="Storage & Limits", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(12, 6))

        ctk.CTkLabel(card1, text="Archive Output Directory", text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=16)
        self.setting_out_dir = ctk.CTkEntry(card1, height=36)
        self.setting_out_dir.insert(0, self.cfg.archiver.output_dir)
        self.setting_out_dir.pack(fill="x", padx=16, pady=(2, 10))

        ctk.CTkLabel(card1, text="Max Video Resolution (p)", text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=16)
        self.setting_res = ctk.CTkComboBox(card1, values=["720", "1080", "1440", "2160"], height=36)
        self.setting_res.set(str(self.cfg.archiver.max_resolution))
        self.setting_res.pack(anchor="w", padx=16, pady=(2, 16))

        # Card: API Keys
        card2 = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        card2.pack(fill="x", pady=8)
        ctk.CTkLabel(card2, text="API Credentials (Saved to .env)", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(12, 6))

        ctk.CTkLabel(card2, text="YouTube Data API v3 Key", text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=16)
        self.setting_yt_key = ctk.CTkEntry(card2, placeholder_text="AIzaSy...", height=36)
        if self.cfg.youtube_api_key:
            self.setting_yt_key.insert(0, self.cfg.youtube_api_key)
        self.setting_yt_key.pack(fill="x", padx=16, pady=(2, 10))

        ctk.CTkLabel(card2, text="Facebook Access Token (Optional)", text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=16)
        self.setting_fb_token = ctk.CTkEntry(card2, placeholder_text="EAAB...", height=36)
        if self.cfg.facebook_access_token:
            self.setting_fb_token.insert(0, self.cfg.facebook_access_token)
        self.setting_fb_token.pack(fill="x", padx=16, pady=(2, 16))

        # Save Button
        self.btn_save_settings = ctk.CTkButton(
            tab, text="Save Settings", command=self._on_save_settings, fg_color=COLOR_PINK, height=38, width=140
        )
        self.btn_save_settings.pack(anchor="w", pady=15)

        return tab

    def _on_save_settings(self) -> None:
        self.cfg.archiver.output_dir = self.setting_out_dir.get().strip()
        self.cfg.archiver.max_resolution = int(self.setting_res.get())
        yt_k = self.setting_yt_key.get().strip()
        fb_t = self.setting_fb_token.get().strip()
        self.cfg.youtube_api_key = yt_k if yt_k else None
        self.cfg.facebook_access_token = fb_t if fb_t else None

        # Persist to .env
        env_lines = []
        if self.cfg.youtube_api_key:
            env_lines.append(f"YOUTUBE_API_KEY={self.cfg.youtube_api_key}")
        if self.cfg.facebook_access_token:
            env_lines.append(f"FACEBOOK_ACCESS_TOKEN={self.cfg.facebook_access_token}")

        env_path = Path(".env")
        env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")

        self.btn_save_settings.configure(text="✔ Saved!")
        self.after(2000, lambda: self.btn_save_settings.configure(text="Save Settings"))


def launch_gui(config_path: str = "config.toml") -> None:
    """Entrypoint function to run desktop application."""
    app = ViceClipDesktopApp(config_path=config_path)
    app.mainloop()


if __name__ == "__main__":
    launch_gui()
