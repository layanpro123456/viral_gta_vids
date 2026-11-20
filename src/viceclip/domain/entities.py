"""Pure domain entities and dataclasses."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from viceclip.domain.enums import Platform, VideoStatus


@dataclass(frozen=True)
class ScoringWeights:
    """Weights for the virality formula."""
    w1: float = 0.7
    w2: float = 0.3


@dataclass
class VideoCandidate:
    """A raw candidate discovered from a platform adapter."""
    platform: Platform
    platform_id: str
    title: str
    creator: str
    source_url: str
    published_at: datetime
    views: int = 0
    likes: int = 0
    comments: int = 0
    duration_seconds: Optional[int] = None
    thumbnail_url: Optional[str] = None

    @property
    def age_in_hours(self) -> float:
        """Calculate age in hours relative to current UTC time."""
        now = datetime.now(timezone.utc)
        pub = self.published_at if self.published_at.tzinfo else self.published_at.replace(tzinfo=timezone.utc)
        delta = now - pub
        hours = delta.total_seconds() / 3600.0
        return max(hours, 0.0)


@dataclass
class VideoRecord:
    """The aggregate entity representing a video in the catalog ledger."""
    platform: Platform
    platform_id: str
    title: str
    creator: str
    source_url: str
    published_at: datetime
    views: int = 0
    likes: int = 0
    comments: int = 0
    virality_score: float = 0.0
    status: VideoStatus = VideoStatus.DISCOVERED
    local_path: Optional[str] = None
    file_sha256: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    discovered_at: Optional[datetime] = None
    id: Optional[int] = None

    @classmethod
    def from_candidate(
        cls, candidate: VideoCandidate, virality_score: float, status: VideoStatus = VideoStatus.DISCOVERED
    ) -> "VideoRecord":
        """Factory method to construct a VideoRecord from a VideoCandidate."""
        return cls(
            platform=candidate.platform,
            platform_id=candidate.platform_id,
            title=candidate.title,
            creator=candidate.creator,
            source_url=candidate.source_url,
            published_at=candidate.published_at,
            views=candidate.views,
            likes=candidate.likes,
            comments=candidate.comments,
            virality_score=virality_score,
            status=status,
            discovered_at=datetime.now(timezone.utc),
        )


@dataclass(frozen=True)
class CatalogStats:
    """Aggregated video counts across all lifecycle statuses."""
    total: int = 0
    discovered: int = 0
    queued: int = 0
    downloading: int = 0
    archived: int = 0
    failed: int = 0
    skipped: int = 0
