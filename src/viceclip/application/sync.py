"""Use case: Full synchronization pipeline (Discovery -> Scored Queue -> Download)."""

from dataclasses import dataclass

from viceclip.application.discover import DiscoverResult, DiscoverVideosUseCase
from viceclip.application.download import DownloadQueueResult, ProcessDownloadQueueUseCase


@dataclass
class SyncResult:
    """Consolidated results of a full sync run."""
    discovery: DiscoverResult
    download: DownloadQueueResult


class SyncPipelineUseCase:
    """Coordinates end-to-end sync."""

    def __init__(
        self,
        discover_use_case: DiscoverVideosUseCase,
        download_use_case: ProcessDownloadQueueUseCase,
    ) -> None:
        self.discover_use_case = discover_use_case
        self.download_use_case = download_use_case

    def execute(self, max_discover: int = 50, max_download: int = 10) -> SyncResult:
        """Run discovery then immediately process archival queue."""
        disc_result = self.discover_use_case.execute(max_results_per_adapter=max_discover)
        down_result = self.download_use_case.execute(limit=max_download)
        return SyncResult(discovery=disc_result, download=down_result)
