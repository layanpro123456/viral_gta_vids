"""Typer CLI commands implementation for ViceClip Archiver."""

from pathlib import Path
from typing import Optional

import typer

from viceclip.application.discover import DiscoverVideosUseCase
from viceclip.application.download import ProcessDownloadQueueUseCase
from viceclip.application.ingest import IngestVideoUseCase
from viceclip.application.stats import GetCatalogStatsUseCase
from viceclip.application.sync import SyncPipelineUseCase
from viceclip.cli.formatting import (
    console,
    print_banner,
    print_config_summary,
    print_discovered_records,
    print_stats_table,
)
from viceclip.infrastructure.adapters.facebook import FacebookAdapter
from viceclip.infrastructure.adapters.reddit import RedditAdapter
from viceclip.infrastructure.adapters.youtube import YouTubeAdapter
from viceclip.infrastructure.config import AppConfig
from viceclip.infrastructure.downloader.ytdlp_acl import YtDlpDownloader
from viceclip.infrastructure.storage.file_store import LocalFileSystemStorage
from viceclip.infrastructure.storage.sqlite_repo import SQLiteVideoRepository

app = typer.Typer(
    name="viceclip",
    help="ViceClip Archiver: Automated discovery, ranking, and archival tool for trending GTA 6 video clips.",
    add_completion=False,
)


def _bootstrap_components(config_path: str = "config.toml") -> tuple[AppConfig, SQLiteVideoRepository, LocalFileSystemStorage]:
    """Load configuration and initialize persistence."""
    cfg = AppConfig.load(config_path)
    repo = SQLiteVideoRepository(cfg.database.db_path)
    storage = LocalFileSystemStorage()
    return cfg, repo, storage


@app.callback()
def main_callback() -> None:
    """ViceClip Archiver CLI Entrypoint."""


@app.command("discover")
def discover_cmd(
    max_results: int = typer.Option(50, "--max-results", "-m", help="Maximum candidates to query per platform adapter."),
    config_path: str = typer.Option("config.toml", "--config", "-c", help="Path to config.toml configuration file."),
) -> None:
    """Discover, score, and queue trending GTA 6 video clips across platforms."""
    print_banner()
    cfg, repo, _ = _bootstrap_components(config_path)

    # Initialize configured platform adapters
    adapters = []
    if cfg.youtube_api_key:
        adapters.append(YouTubeAdapter(api_key=cfg.youtube_api_key))
    else:
        console.print("[dim yellow]Note: YOUTUBE_API_KEY not set. Skipping YouTube Data API adapter.[/dim yellow]")

    # Reddit adapter enabled by default
    adapters.append(RedditAdapter(subreddit="GTA6", user_agent=cfg.reddit_user_agent))

    # Facebook adapter
    if cfg.facebook_access_token:
        adapters.append(FacebookAdapter(access_token=cfg.facebook_access_token, page_ids=cfg.facebook.page_ids))
    else:
        console.print("[dim yellow]Note: FACEBOOK_ACCESS_TOKEN not set. Direct Facebook URL ingestion supported via 'ingest' or 'download --url'.[/dim yellow]")

    console.print(f"[bold cyan]Running discovery across {len(adapters)} adapter(s)...[/bold cyan]")

    use_case = DiscoverVideosUseCase(
        repository=repo,
        adapters=adapters,
        settings=cfg.discovery,
        max_duration_seconds=cfg.archiver.max_duration_seconds,
    )

    with console.status("[bold green]Querying platforms and computing virality scores...[/bold green]"):
        res = use_case.execute(max_results_per_adapter=max_results)

    print_discovered_records(res.records)

    console.print(
        f"\n[bold green]Discovery Complete:[/bold green] "
        f"Processed: [bold]{res.total_found}[/bold] | "
        f"Newly Queued: [bold green]{res.newly_queued}[/bold green] | "
        f"Promoted: [bold cyan]{res.promoted_to_queued}[/bold cyan] | "
        f"Skipped: [bold dim]{res.skipped}[/bold dim]"
    )

    if res.errors:
        for err in res.errors:
            console.print(f"[red]Warning: {err}[/red]")

    repo.close()


@app.command("download")
def download_cmd(
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum queued videos to download in this run."),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="Direct video URL (Facebook, YouTube, Reddit) to ingest and download immediately."),
    config_path: str = typer.Option("config.toml", "--config", "-c", help="Path to config.toml configuration file."),
) -> None:
    """Process queued videos and safely download non-DRM media with companion metadata."""
    print_banner()
    cfg, repo, storage = _bootstrap_components(config_path)

    # Direct URL ingestion shortcut
    if url:
        console.print(f"[bold cyan]Direct Ingest Mode:[/bold cyan] Ingesting URL: {url}")
        ingest_use_case = IngestVideoUseCase(
            repository=repo,
            settings=cfg.discovery,
            max_duration_seconds=cfg.archiver.max_duration_seconds,
        )
        rec, qualified, reason = ingest_use_case.ingest_url(url, force_queue=True)
        console.print(
            f"[green]Successfully enqueued {rec.platform} video:[/green] [bold]{rec.title}[/bold] (Virality: {rec.virality_score:.2f})"
        )
        limit = 1

    downloader = YtDlpDownloader(max_duration_seconds=cfg.archiver.max_duration_seconds)
    use_case = ProcessDownloadQueueUseCase(
        repository=repo,
        downloader=downloader,
        storage=storage,
        settings=cfg.archiver,
    )

    console.print(f"[bold cyan]Starting download worker (batch limit: {limit})...[/bold cyan]")

    with console.status("[bold green]Downloading media and verifying checksums...[/bold green]"):
        result = use_case.execute(limit=limit)

    if result.reconciled_tasks > 0:
        console.print(f"[yellow]Crash Recovery:[/yellow] Reconciled {result.reconciled_tasks} previously interrupted task(s).")

    console.print(
        f"\n[bold green]Download Complete:[/bold green] "
        f"Processed: [bold]{result.total_processed}[/bold] | "
        f"Archived: [bold green]{result.succeeded}[/bold green] | "
        f"Failed: [bold red]{result.failed}[/bold red]"
    )

    if result.errors:
        for err in result.errors:
            console.print(f"[red]Error: {err}[/red]")

    repo.close()


@app.command("ingest")
def ingest_cmd(
    url: str = typer.Argument(..., help="Direct video URL to ingest (Facebook video/reel, YouTube, Reddit)."),
    force: bool = typer.Option(True, "--force/--no-force", help="Force enqueue for download regardless of virality score."),
    config_path: str = typer.Option("config.toml", "--config", "-c", help="Path to config.toml configuration file."),
) -> None:
    """Ingest, extract metadata, and queue a specific video URL (Facebook, YouTube, Reddit)."""
    print_banner()
    cfg, repo, _ = _bootstrap_components(config_path)

    ingest_use_case = IngestVideoUseCase(
        repository=repo,
        settings=cfg.discovery,
        max_duration_seconds=cfg.archiver.max_duration_seconds,
    )

    console.print(f"[bold cyan]Ingesting video URL:[/bold cyan] {url}")
    with console.status("[bold green]Extracting stream metadata and evaluating virality...[/bold green]"):
        rec, qualified, reason = ingest_use_case.ingest_url(url, force_queue=force)

    status_color = "green" if rec.status == "QUEUED" else "yellow"
    console.print(f"[{status_color}]Status: {rec.status}[/{status_color}] | Platform: [cyan]{rec.platform}[/cyan]")
    console.print(f"Title: [bold]{rec.title}[/bold]")
    console.print(f"Creator: [cyan]{rec.creator}[/cyan] | Views: {rec.views:,} | Virality Score: [magenta]{rec.virality_score:.2f}[/magenta]")
    if reason:
        console.print(f"[dim]Evaluation note: {reason}[/dim]")

    repo.close()


@app.command("sync")
def sync_cmd(
    discover_limit: int = typer.Option(50, "--discover-limit", "-m", help="Max candidates per adapter during discovery."),
    download_limit: int = typer.Option(10, "--download-limit", "-l", help="Max queued items to download."),
    config_path: str = typer.Option("config.toml", "--config", "-c", help="Path to config.toml configuration file."),
) -> None:
    """Execute end-to-end sync: discover new viral clips and process the download queue."""
    print_banner()
    cfg, repo, storage = _bootstrap_components(config_path)

    adapters = []
    if cfg.youtube_api_key:
        adapters.append(YouTubeAdapter(api_key=cfg.youtube_api_key))
    adapters.append(RedditAdapter(subreddit="GTA6", user_agent=cfg.reddit_user_agent))
    if cfg.facebook_access_token:
        adapters.append(FacebookAdapter(access_token=cfg.facebook_access_token, page_ids=cfg.facebook.page_ids))

    discover_use_case = DiscoverVideosUseCase(
        repository=repo,
        adapters=adapters,
        settings=cfg.discovery,
        max_duration_seconds=cfg.archiver.max_duration_seconds,
    )
    downloader = YtDlpDownloader(max_duration_seconds=cfg.archiver.max_duration_seconds)
    download_use_case = ProcessDownloadQueueUseCase(
        repository=repo,
        downloader=downloader,
        storage=storage,
        settings=cfg.archiver,
    )

    pipeline = SyncPipelineUseCase(
        discover_use_case=discover_use_case,
        download_use_case=download_use_case,
    )

    console.print("[bold cyan]Executing full pipeline sync...[/bold cyan]")
    sync_res = pipeline.execute(max_discover=discover_limit, max_download=download_limit)

    console.print(
        f"[bold green]Sync Finished:[/bold green] "
        f"Discovered {sync_res.discovery.total_found} candidates ({sync_res.discovery.newly_queued} queued), "
        f"Archived {sync_res.download.succeeded} media file(s)."
    )

    repo.close()


@app.command("stats")
def stats_cmd(
    config_path: str = typer.Option("config.toml", "--config", "-c", help="Path to config.toml configuration file."),
) -> None:
    """Display catalog status statistics and archival progress."""
    print_banner()
    cfg, repo, _ = _bootstrap_components(config_path)
    use_case = GetCatalogStatsUseCase(repo)
    stats = use_case.execute()
    print_stats_table(stats)
    repo.close()


@app.command("config")
def config_cmd(
    config_path: str = typer.Option("config.toml", "--config", "-c", help="Path to config.toml configuration file."),
) -> None:
    """Display loaded configuration parameters and authentication status."""
    print_banner()
    cfg = AppConfig.load(config_path)
    print_config_summary(cfg)


if __name__ == "__main__":
    app()
