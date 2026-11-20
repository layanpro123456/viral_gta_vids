"""Use case: Query catalog statistics."""

from viceclip.domain.entities import CatalogStats
from viceclip.ports.repository import IVideoRepository


class GetCatalogStatsUseCase:
    """Retrieves current catalog metrics."""

    def __init__(self, repository: IVideoRepository) -> None:
        self.repository = repository

    def execute(self) -> CatalogStats:
        """Fetch current summary statistics from repository."""
        return self.repository.get_stats()
