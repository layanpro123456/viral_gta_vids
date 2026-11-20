"""Integration tests for SQLiteVideoRepository."""

from datetime import datetime, timezone
import os
import tempfile

import pytest

from viceclip.domain.entities import VideoCandidate
from viceclip.domain.enums import Platform, VideoStatus
from viceclip.domain.exceptions import InvalidStateTransitionError
from viceclip.infrastructure.storage.sqlite_repo import SQLiteVideoRepository


@pytest.fixture
def repo() -> SQLiteVideoRepository:
    """Fixture providing an isolated SQLite repository using a temporary file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = f.name

    repository = SQLiteVideoRepository(temp_path)
    yield repository
    repository.close()
    if os.path.exists(temp_path):
        os.remove(temp_path)
    wal_path = temp_path + "-wal"
    if os.path.exists(wal_path):
        os.remove(wal_path)
    shm_path = temp_path + "-shm"
    if os.path.exists(shm_path):
        os.remove(shm_path)


def test_upsert_and_deduplication(repo: SQLiteVideoRepository) -> None:
    """Verify deduplication by (platform, platform_id) and field updates."""
    candidate = VideoCandidate(
        platform=Platform.YOUTUBE,
        platform_id="vid_101",
        title="First Title",
        creator="ChannelA",
        source_url="https://youtube.com/watch?v=vid_101",
        published_at=datetime.now(timezone.utc),
        views=1000,
        likes=50,
        comments=10,
    )

    # 1. Initial insert
    rec, is_new = repo.upsert_candidate(candidate, score=2.5, status=VideoStatus.SKIPPED)
    assert is_new is True
    assert rec.platform_id == "vid_101"
    assert rec.status == VideoStatus.SKIPPED
    assert rec.views == 1000

    # 2. Second insert with higher engagement: should update, not duplicate
    candidate.views = 20000
    candidate.likes = 1200
    rec2, is_new2 = repo.upsert_candidate(candidate, score=4.8, status=VideoStatus.QUEUED)
    assert is_new2 is False
    assert rec2.id == rec.id
    assert rec2.views == 20000
    # Verified promotion from SKIPPED to QUEUED when qualified
    assert rec2.status == VideoStatus.QUEUED


def test_state_transitions_and_validation(repo: SQLiteVideoRepository) -> None:
    """Verify legal and illegal state transitions in database."""
    candidate = VideoCandidate(
        platform=Platform.YOUTUBE,
        platform_id="vid_202",
        title="Transition Test",
        creator="ChannelB",
        source_url="https://youtube.com/watch?v=vid_202",
        published_at=datetime.now(timezone.utc),
        views=5000,
    )
    rec, _ = repo.upsert_candidate(candidate, score=4.0, status=VideoStatus.QUEUED)
    assert rec.id is not None

    # QUEUED -> DOWNLOADING (Legal)
    repo.update_status(rec.id, VideoStatus.DOWNLOADING)
    updated = repo.get_by_platform_id(Platform.YOUTUBE, "vid_202")
    assert updated is not None
    assert updated.status == VideoStatus.DOWNLOADING

    # DOWNLOADING -> ARCHIVED (Legal)
    repo.update_status(
        rec.id,
        VideoStatus.ARCHIVED,
        local_path="archive/2026-11-20/vid_202/video.mp4",
        file_sha256="abc123hash",
    )
    archived = repo.get_by_platform_id(Platform.YOUTUBE, "vid_202")
    assert archived is not None
    assert archived.status == VideoStatus.ARCHIVED
    assert archived.local_path == "archive/2026-11-20/vid_202/video.mp4"
    assert archived.file_sha256 == "abc123hash"

    # ARCHIVED -> QUEUED (Illegal)
    with pytest.raises(InvalidStateTransitionError):
        repo.update_status(rec.id, VideoStatus.QUEUED)


def test_crash_recovery(repo: SQLiteVideoRepository) -> None:
    """Verify reconciliation resets stuck DOWNLOADING tasks back to QUEUED."""
    candidate1 = VideoCandidate(
        platform=Platform.YOUTUBE,
        platform_id="crash_1",
        title="Crash Test 1",
        creator="ChannelC",
        source_url="https://youtube.com/watch?v=crash_1",
        published_at=datetime.now(timezone.utc),
        views=3000,
    )
    rec, _ = repo.upsert_candidate(candidate1, score=4.0, status=VideoStatus.QUEUED)
    assert rec.id is not None
    repo.update_status(rec.id, VideoStatus.DOWNLOADING)

    # Reconcile crashed tasks
    recovered = repo.reconcile_crashed_tasks()
    assert recovered == 1

    rec_after = repo.get_by_platform_id(Platform.YOUTUBE, "crash_1")
    assert rec_after is not None
    assert rec_after.status == VideoStatus.QUEUED
    assert rec_after.retry_count == 1


def test_catalog_statistics(repo: SQLiteVideoRepository) -> None:
    """Verify aggregated statistics calculation."""
    for i in range(3):
        c = VideoCandidate(
            platform=Platform.YOUTUBE,
            platform_id=f"stat_{i}",
            title=f"Stat {i}",
            creator="Tester",
            source_url=f"https://youtube.com/watch?v=stat_{i}",
            published_at=datetime.now(timezone.utc),
        )
        repo.upsert_candidate(c, score=4.0, status=VideoStatus.QUEUED)

    stats = repo.get_stats()
    assert stats.total == 3
    assert stats.queued == 3
    assert stats.archived == 0
