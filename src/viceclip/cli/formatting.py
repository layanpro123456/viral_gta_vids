"""Rich terminal formatting helpers for tables, spinners, and banners."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from viceclip.domain.entities import CatalogStats, VideoRecord
from viceclip.infrastructure.config import AppConfig

console = Console()


def print_banner() -> None:
    """Print application banner."""
    console.print(
        Panel(
            "[bold cyan]ViceClip Archiver[/bold cyan] - [bold magenta]GTA 6 Viral Video Discovery & Archival[/bold magenta]\n"
            "[dim]Specification-Driven • Hexagonal Architecture • Compliance Guardrails[/dim]",
            border_style="cyan",
        )
    )


def print_stats_table(stats: CatalogStats) -> None:
    """Render a Rich table for catalog statistics."""
    table = Table(title="ViceClip Catalog Summary", border_style="magenta", header_style="bold yellow")
    table.add_column("Status", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Percentage", justify="right")

    total = max(stats.total, 1)

    table.add_row("[cyan]QUEUED[/cyan]", str(stats.queued), f"{(stats.queued / total) * 100:.1f}%")
    table.add_row("[green]ARCHIVED[/green]", str(stats.archived), f"{(stats.archived / total) * 100:.1f}%")
    table.add_row("[yellow]DOWNLOADING[/yellow]", str(stats.downloading), f"{(stats.downloading / total) * 100:.1f}%")
    table.add_row("[dim]SKIPPED[/dim]", str(stats.skipped), f"{(stats.skipped / total) * 100:.1f}%")
    table.add_row("[red]FAILED[/red]", str(stats.failed), f"{(stats.failed / total) * 100:.1f}%")
    table.add_section()
    table.add_row("[bold white]TOTAL VIDEOS[/bold white]", str(stats.total), "100.0%")

    console.print(table)


def print_discovered_records(records: list[VideoRecord]) -> None:
    """Render a Rich table of discovered videos."""
    if not records:
        console.print("[yellow]No candidates processed in this run.[/yellow]")
        return

    table = Table(title="Discovered Video Candidates", border_style="blue", header_style="bold cyan")
    table.add_column("Platform", style="dim", width=10)
    table.add_column("Title", style="bold", max_width=40, overflow="ellipsis")
    table.add_column("Creator", style="cyan", max_width=18, overflow="ellipsis")
    table.add_column("Views", justify="right")
    table.add_column("Virality", justify="right", style="magenta")
    table.add_column("Status", style="bold")

    for r in records[:25]:  # Show top 25
        status_color = "green" if r.status == "QUEUED" else "dim"
        table.add_row(
            str(r.platform),
            r.title,
            r.creator,
            f"{r.views:,}",
            f"{r.virality_score:.2f}",
            f"[{status_color}]{r.status}[/{status_color}]",
        )

    console.print(table)


def print_config_summary(config: AppConfig) -> None:
    """Print configuration parameters and credentials status."""
    table = Table(title="Active Configuration", border_style="cyan")
    table.add_column("Setting Section", style="bold yellow")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")

    # Discovery
    table.add_row("Discovery", "Keywords", ", ".join(config.discovery.keywords))
    table.add_row("Discovery", "Exclude Keywords", ", ".join(config.discovery.exclude_keywords))
    table.add_row("Discovery", "Min Virality Score", str(config.discovery.min_virality_score))
    table.add_row("Discovery", "Max Age (hours)", str(config.discovery.max_age_hours))
    table.add_row("Discovery", "Scoring Weights", f"w1={config.discovery.weight_views}, w2={config.discovery.weight_engagement}")

    # Archiver
    table.add_row("Archiver", "Output Directory", config.archiver.output_dir)
    table.add_row("Archiver", "Max Resolution", f"{config.archiver.max_resolution}p")
    table.add_row("Archiver", "Max Duration", f"{config.archiver.max_duration_seconds}s")
    table.add_row("Archiver", "Concurrent Downloads", str(config.archiver.concurrent_downloads))

    # Database & Auth
    table.add_row("Database", "SQLite Path", config.database.db_path)
    yt_status = "[green]Configured[/green]" if config.youtube_api_key else "[yellow]Not Provided (YouTube discovery disabled)[/yellow]"
    table.add_row("Auth", "YOUTUBE_API_KEY", yt_status)
    fb_status = "[green]Configured[/green]" if config.facebook_access_token else "[yellow]Direct URL Ingest Mode (Graph API disabled)[/yellow]"
    table.add_row("Auth", "FACEBOOK_ACCESS_TOKEN", fb_status)
    table.add_row("Auth", "Reddit User-Agent", config.reddit_user_agent)

    console.print(table)
