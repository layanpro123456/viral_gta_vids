"""Port definition for video metadata and queue repository."""

from typing import Optional, Protocol

from viceclip.domain.entities import CatalogStats, VideoCandidate, VideoRecord
from viceclip.domain.enums import Platform, VideoStatus


class IVideoRepository(Protocol):
    """Repository port interface for catalog persistence and state ledger."""

    def initialize_schema(self) -> None:
        """Create database tables and indexes if they do not exist."""
        ...

    def upsert_candidate(
        self, candidate: VideoCandidate, score: float, status: VideoStatus
    ) -> tuple[VideoRecord, bool]:
        """Insert or update a discovered video candidate.

        Returns:
            (record, is_new): The stored record and whether it was newly inserted.
        """
        ...

    def get_by_platform_id(self, platform: Platform, platform_id: str) -> Optional[VideoRecord]:
        """Fetch a single record by unique platform and platform_id."""
        ...

    def get_queued(self, limit: int = 50) -> list[VideoRecord]:
        """Fetch videos with status QUEUED ordered by virality_score descending."""
        ...

    def update_status(
        self,
        record_id: int,
        status: VideoStatus,
        error_message: Optional[str] = None,
        local_path: Optional[str] = None,
        file_sha256: Optional[str] = None,
    ) -> None:
        """Transition status and update file/error metadata."""
        ...

    def reconcile_crashed_tasks(self) -> int:
        """Reset records stuck in DOWNLOADING state back to QUEUED."""
        ...

    def get_stats(self) -> CatalogStats:
        """Return counts of videos partitioned by status."""
        ...

    def close(self) -> None:
        """Safely close repository connections."""
        ...
