"""Application use cases coordinating domain policies and ports."""

from viceclip.application.discover import DiscoverResult, DiscoverVideosUseCase
from viceclip.application.download import DownloadQueueResult, ProcessDownloadQueueUseCase
from viceclip.application.ingest import IngestVideoUseCase
from viceclip.application.stats import GetCatalogStatsUseCase
from viceclip.application.sync import SyncResult, SyncPipelineUseCase

__all__ = [
    "DiscoverVideosUseCase",
    "DiscoverResult",
    "ProcessDownloadQueueUseCase",
    "DownloadQueueResult",
    "GetCatalogStatsUseCase",
    "SyncPipelineUseCase",
    "SyncResult",
    "IngestVideoUseCase",
]
