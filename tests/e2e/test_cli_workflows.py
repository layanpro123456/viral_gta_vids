"""End-to-end integration tests for Typer CLI commands."""

from pathlib import Path
import tempfile

from typer.testing import CliRunner

from viceclip.cli.main import app

runner = CliRunner()


def test_cli_help() -> None:
    """Verify CLI help text displays available commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ViceClip Archiver" in result.output
    assert "discover" in result.output
    assert "download" in result.output
    assert "sync" in result.output
    assert "stats" in result.output
    assert "config" in result.output


def test_cli_config_command() -> None:
    """Verify config display command."""
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "Active Configuration" in result.output
    assert "GTA 6" in result.output


def test_cli_stats_command() -> None:
    """Verify stats command runs on fresh database."""
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

        result = runner.invoke(app, ["stats", "--config", str(cfg_path)])
        assert result.exit_code == 0
        assert "ViceClip Catalog Summary" in result.output
        assert "TOTAL VIDEOS" in result.output


def test_cli_download_empty_queue() -> None:
    """Verify download command handles empty queue gracefully."""
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

        result = runner.invoke(app, ["download", "--config", str(cfg_path)])
        assert result.exit_code == 0
        assert "Processed: 0" in result.output
