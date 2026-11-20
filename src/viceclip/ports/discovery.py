"""Port definition for platform discovery adapters."""

from typing import Protocol, Sequence

from viceclip.domain.entities import VideoCandidate
from viceclip.domain.enums import Platform


class IDiscoveryAdapter(Protocol):
    """Adapter port interface for querying platform APIs."""

    @property
    def platform(self) -> Platform:
        """The platform handled by this adapter."""
        ...

    def fetch_trending(self, keywords: Sequence[str], max_results: int = 50) -> list[VideoCandidate]:
        """Query platform API for trending videos matching keywords.

        Returns:
            List of raw VideoCandidate objects with populated statistics.
        """
        ...
