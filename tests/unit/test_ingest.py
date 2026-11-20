"""Unit and E2E tests for direct URL ingestion (Facebook, YouTube, Reddit)."""

from pathlib import Path
import tempfile

from typer.testing import CliRunner

from viceclip.application.ingest import IngestVideoUseCase
from viceclip.cli.main import app
from viceclip.domain.enums import Platform, VideoStatus
from viceclip.infrastructure.config import DiscoverySettings
from viceclip.infrastructure.storage.sqlite_repo import SQLiteVideoRepository

runner = CliRunner()


def test_ingest_detect_platform() -> None:
    """Verify platform detection for various URLs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_plat.db")
        repo = SQLiteVideoRepository(db_path)
        use_case = IngestVideoUseCase(repo, DiscoverySettings())

        assert use_case.detect_platform("https://www.facebook.com/watch/?v=999") == Platform.FACEBOOK
        assert use_case.detect_platform("https://fb.watch/test123/") == Platform.FACEBOOK
        assert use_case.detect_platform("https://www.youtube.com/watch?v=abc") == Platform.YOUTUBE
        assert use_case.detect_platform("https://youtu.be/xyz") == Platform.YOUTUBE
        assert use_case.detect_platform("https://reddit.com/r/GTA6/comments/123") == Platform.REDDIT
        assert use_case.detect_platform("https://other-site.com/video.mp4") == Platform.GENERIC

        repo.close()


def test_ingest_facebook_url_queues_candidate() -> None:
    """Verify direct Facebook URL ingestion creates a QUEUED record."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_fb.db")
        repo = SQLiteVideoRepository(db_path)
        use_case = IngestVideoUseCase(repo, DiscoverySettings(min_virality_score=2.0))

        url = "https://www.facebook.com/watch/?v=test_fb_video_42"
        rec, qualified, reason = use_case.ingest_url(url, force_queue=True)

        assert rec.platform == Platform.FACEBOOK
        assert rec.status == VideoStatus.QUEUED
        assert rec.source_url == url

        db_rec = repo.get_by_platform_id(Platform.FACEBOOK, rec.platform_id)
        assert db_rec is not None
        assert db_rec.status == VideoStatus.QUEUED

        repo.close()


def test_cli_ingest_command() -> None:
    """Verify CLI `viceclip ingest <url>` command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "config.toml"
        db_path = Path(tmpdir) / "test.db"
        cfg_path.write_text(
            f"""
            [database]
            db_path = "{db_path.as_posix()}"
            """,
            encoding="utf-8",
        )

        fb_url = "https://fb.watch/viral_gta6_clip/"
        result = runner.invoke(app, ["ingest", fb_url, "--config", str(cfg_path)])

        assert result.exit_code == 0
        assert "Ingesting video URL" in result.output
        assert "facebook" in result.output.lower()
        assert "QUEUED" in result.output
