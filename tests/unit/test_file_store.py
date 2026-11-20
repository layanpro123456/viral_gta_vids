"""Unit tests for LocalFileSystemStorage."""

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

import pytest

from viceclip.domain.entities import VideoRecord
from viceclip.domain.enums import Platform, VideoStatus
from viceclip.infrastructure.storage.file_store import LocalFileSystemStorage


def test_sanitize_filename() -> None:
    """Verify filename sanitization against invalid OS characters and directory traversal."""
    store = LocalFileSystemStorage()

    assert store.sanitize_filename("Normal Title") == "Normal_Title"
    assert store.sanitize_filename("GTA 6: Vice City / Police! [4K]") == "GTA_6_Vice_City_Police!_[4K]"
    assert store.sanitize_filename("../../../etc/passwd") == "etc_passwd"
    assert store.sanitize_filename("..\\..\\windows\\system32") == "windows_system32"
    assert store.sanitize_filename("   ") == "untitled"
    # Length truncation
    long_name = "a" * 100
    assert len(store.sanitize_filename(long_name, max_length=50)) == 50


def test_create_asset_directory_and_sidecar() -> None:
    """Verify deterministic asset directory hierarchy and sidecar metadata."""
    store = LocalFileSystemStorage()

    with tempfile.TemporaryDirectory() as tmpdir:
        pub_dt = datetime(2026, 11, 20, 15, 30, tzinfo=timezone.utc)
        record = VideoRecord(
            platform=Platform.YOUTUBE,
            platform_id="abc999",
            title="GTA 6 Speedrun Leak",
            creator="LeakMaster",
            source_url="https://youtube.com/watch?v=abc999",
            published_at=pub_dt,
            views=100000,
            likes=7500,
            comments=850,
            virality_score=5.25,
            status=VideoStatus.ARCHIVED,
        )

        asset_dir = store.create_asset_directory(tmpdir, record)
        assert Path(asset_dir).exists()
        assert "2026-11-20" in asset_dir
        assert "youtube_abc999_GTA_6_Speedrun_Leak" in asset_dir

        # Create dummy media file to compute sha256
        dummy_media = Path(asset_dir) / "video.mp4"
        dummy_media.write_bytes(b"Simulated MP4 video bytes for hash verification")

        checksum = store.compute_file_sha256(str(dummy_media))
        assert len(checksum) == 64  # SHA-256 hex string

        meta_file = store.write_sidecar_metadata(
            directory=asset_dir,
            record=record,
            media_relative_path="video.mp4",
            file_sha256=checksum,
        )
        assert Path(meta_file).is_file()

        with open(meta_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["title"] == "GTA 6 Speedrun Leak"
        assert data["file_sha256"] == checksum
        assert data["metrics"]["virality_score"] == 5.25
        assert "compliance_notice" in data
