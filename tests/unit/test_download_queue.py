"""Unit tests for ProcessDownloadQueueUseCase."""

from datetime import datetime, timezone
from pathlib import Path
import tempfile

import pytest

from viceclip.application.download import ProcessDownloadQueueUseCase
from viceclip.domain.entities import VideoCandidate, VideoRecord
from viceclip.domain.enums import Platform, VideoStatus
from viceclip.domain.exceptions import DRMProtectedError
from viceclip.infrastructure.config import ArchiverSettings
from viceclip.infrastructure.storage.file_store import LocalFileSystemStorage
from viceclip.infrastructure.storage.sqlite_repo import SQLiteVideoRepository


class MockSuccessDownloader:
    """Mock downloader that writes a fake MP4 file."""

    def download_media(self, record: VideoRecord, output_directory: str, max_resolution: int = 1080) -> tuple[str, str | None]:
        out_dir = Path(output_directory)
        media_path = out_dir / "video.mp4"
        media_path.write_bytes(b"Fake MP4 video content for testing")
        return str(media_path), None


class MockDRMDownloader:
    """Mock downloader that simulates DRM protected stream rejection."""

    def download_media(self, record: VideoRecord, output_directory: str, max_resolution: int = 1080) -> tuple[str, str | None]:
        raise DRMProtectedError("Stream marked as DRM-protected.")


def test_process_download_queue_success() -> None:
    """Verify queue processing transitions record to ARCHIVED with checksum and sidecar."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        repo = SQLiteVideoRepository(db_path)
        storage = LocalFileSystemStorage()

        cand = VideoCandidate(
            platform=Platform.YOUTUBE,
            platform_id="vid_arch_1",
            title="Awesome GTA 6 Stunt",
            creator="StuntMaster",
            source_url="https://youtube.com/watch?v=vid_arch_1",
            published_at=datetime.now(timezone.utc),
            views=50000,
        )
        rec, _ = repo.upsert_candidate(cand, score=5.0, status=VideoStatus.QUEUED)

        settings = ArchiverSettings(
            output_dir=str(Path(tmpdir) / "archive"),
            rate_limit_sleep_seconds=0.0,
        )

        use_case = ProcessDownloadQueueUseCase(
            repository=repo,
            downloader=MockSuccessDownloader(),
            storage=storage,
            settings=settings,
        )

        result = use_case.execute(limit=5)
        assert result.total_processed == 1
        assert result.succeeded == 1
        assert result.failed == 0

        # Check database record status
        updated = repo.get_by_platform_id(Platform.YOUTUBE, "vid_arch_1")
        assert updated is not None
        assert updated.status == VideoStatus.ARCHIVED
        assert updated.local_path is not None
        assert updated.file_sha256 is not None
        assert Path(updated.local_path).exists()

        repo.close()


def test_process_download_queue_drm_rejection() -> None:
    """Verify DRM protected streams fail gracefully and mark record as FAILED."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_drm.db")
        repo = SQLiteVideoRepository(db_path)
        storage = LocalFileSystemStorage()

        cand = VideoCandidate(
            platform=Platform.YOUTUBE,
            platform_id="vid_drm_1",
            title="DRM Encrypted GTA 6 Video",
            creator="ProtectedChannel",
            source_url="https://youtube.com/watch?v=vid_drm_1",
            published_at=datetime.now(timezone.utc),
            views=80000,
        )
        rec, _ = repo.upsert_candidate(cand, score=5.0, status=VideoStatus.QUEUED)

        settings = ArchiverSettings(
            output_dir=str(Path(tmpdir) / "archive"),
            rate_limit_sleep_seconds=0.0,
        )

        use_case = ProcessDownloadQueueUseCase(
            repository=repo,
            downloader=MockDRMDownloader(),
            storage=storage,
            settings=settings,
        )

        result = use_case.execute(limit=5)
        assert result.total_processed == 1
        assert result.succeeded == 0
        assert result.failed == 1

        updated = repo.get_by_platform_id(Platform.YOUTUBE, "vid_drm_1")
        assert updated is not None
        assert updated.status == VideoStatus.FAILED
        assert "DRM" in str(updated.error_message)

        repo.close()
