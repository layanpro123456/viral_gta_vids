"""Use case: Direct video URL ingestion (e.g. Facebook videos/reels, YouTube, Reddit)."""

from datetime import datetime, timezone
import re
from typing import Optional

from viceclip.domain.entities import VideoCandidate, VideoRecord
from viceclip.domain.enums import Platform, VideoStatus
from viceclip.domain.scoring import is_candidate_qualified
from viceclip.infrastructure.adapters.facebook import FacebookAdapter
from viceclip.infrastructure.config import DiscoverySettings
from viceclip.ports.repository import IVideoRepository


class IngestVideoUseCase:
    """Ingests a single video URL directly into the archival catalog."""

    def __init__(
        self,
        repository: IVideoRepository,
        settings: DiscoverySettings,
        max_duration_seconds: int = 300,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.max_duration_seconds = max_duration_seconds
        self.fb_adapter = FacebookAdapter()

    def detect_platform(self, url: str) -> Platform:
        """Detect the source platform from URL domain."""
        url_lower = url.lower()
        if "facebook.com" in url_lower or "fb.watch" in url_lower:
            return Platform.FACEBOOK
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return Platform.YOUTUBE
        if "reddit.com" in url_lower or "v.redd.it" in url_lower:
            return Platform.REDDIT
        return Platform.GENERIC

    def ingest_url(
        self,
        url: str,
        force_queue: bool = True,
    ) -> tuple[VideoRecord, bool, Optional[str]]:
        """Extract metadata from URL, compute virality score, and record into database.

        Returns:
            (record, is_qualified, rejection_reason_or_none)
        """
        platform = self.detect_platform(url)

        # Attempt metadata extraction via adapter
        candidate: Optional[VideoCandidate] = None
        if platform == Platform.FACEBOOK or True:
            candidate = self.fb_adapter.extract_from_url(url)

        if candidate is None:
            # Fallback candidate structure if offline or extraction unavailable
            clean_id = re.sub(r"[^a-zA-Z0-9_-]", "_", url.split("/")[-1] or "direct_video")[:30]
            candidate = VideoCandidate(
                platform=platform,
                platform_id=f"{platform}_{clean_id}",
                title=f"Direct {platform.capitalize()} Video",
                creator=f"{platform.capitalize()} Creator",
                source_url=url,
                published_at=datetime.now(timezone.utc),
                views=10000,
                likes=500,
                comments=50,
            )

        qualified, score, reason = is_candidate_qualified(
            candidate=candidate,
            min_score=self.settings.min_virality_score,
            max_duration_seconds=self.max_duration_seconds,
            max_age_hours=self.settings.max_age_hours,
            exclude_keywords=self.settings.exclude_keywords,
            weights=self.settings.scoring_weights,
        )

        status = VideoStatus.QUEUED if (force_queue or qualified) else VideoStatus.SKIPPED
        record, _ = self.repository.upsert_candidate(candidate, score, status)
        return record, qualified, reason
