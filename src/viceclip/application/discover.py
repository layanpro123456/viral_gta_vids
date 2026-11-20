"""Use case: Discover, score, filter, and queue trending video candidates."""

from dataclasses import dataclass, field
from typing import Sequence

from viceclip.domain.entities import VideoRecord
from viceclip.domain.enums import VideoStatus
from viceclip.domain.scoring import is_candidate_qualified
from viceclip.infrastructure.config import DiscoverySettings
from viceclip.ports.discovery import IDiscoveryAdapter
from viceclip.ports.repository import IVideoRepository


@dataclass
class DiscoverResult:
    """Summary metrics of a discovery execution."""
    total_found: int = 0
    newly_queued: int = 0
    promoted_to_queued: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    records: list[VideoRecord] = field(default_factory=list)


class DiscoverVideosUseCase:
    """Coordinates platform adapters, virality scoring, and deduplicated persistence."""

    def __init__(
        self,
        repository: IVideoRepository,
        adapters: Sequence[IDiscoveryAdapter],
        settings: DiscoverySettings,
        max_duration_seconds: int = 300,
    ) -> None:
        self.repository = repository
        self.adapters = adapters
        self.settings = settings
        self.max_duration_seconds = max_duration_seconds

    def execute(self, max_results_per_adapter: int = 50) -> DiscoverResult:
        """Run discovery across all configured adapters and record results."""
        result = DiscoverResult()

        for adapter in self.adapters:
            try:
                candidates = adapter.fetch_trending(
                    keywords=self.settings.keywords,
                    max_results=max_results_per_adapter,
                )
            except Exception as exc:
                result.errors.append(f"Adapter {adapter.platform} failed: {exc}")
                continue

            for candidate in candidates:
                result.total_found += 1
                qualified, score, reason = is_candidate_qualified(
                    candidate=candidate,
                    min_score=self.settings.min_virality_score,
                    max_duration_seconds=self.max_duration_seconds,
                    max_age_hours=self.settings.max_age_hours,
                    exclude_keywords=self.settings.exclude_keywords,
                    weights=self.settings.scoring_weights,
                )

                target_status = VideoStatus.QUEUED if qualified else VideoStatus.SKIPPED

                existing = self.repository.get_by_platform_id(candidate.platform, candidate.platform_id)
                record, is_new = self.repository.upsert_candidate(candidate, score, target_status)
                result.records.append(record)

                if is_new:
                    if record.status == VideoStatus.QUEUED:
                        result.newly_queued += 1
                    else:
                        result.skipped += 1
                else:
                    if existing and existing.status == VideoStatus.SKIPPED and record.status == VideoStatus.QUEUED:
                        result.promoted_to_queued += 1
                    elif record.status == VideoStatus.SKIPPED:
                        result.skipped += 1

        return result
