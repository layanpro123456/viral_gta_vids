"""Use case: Process queued videos and archive media with sidecar metadata."""

from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import Optional

from viceclip.domain.entities import VideoRecord
from viceclip.domain.enums import VideoStatus
from viceclip.infrastructure.config import ArchiverSettings
from viceclip.ports.downloader import IMediaDownloader
from viceclip.ports.repository import IVideoRepository
from viceclip.ports.storage import IFileSystemStorage


@dataclass
class DownloadQueueResult:
    """Summary of download queue execution."""
    reconciled_tasks: int = 0
    total_processed: int = 0
    succeeded: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


class ProcessDownloadQueueUseCase:
    """Orchestrates queue pickup, safe downloading, checksumming, and state transitions."""

    def __init__(
        self,
        repository: IVideoRepository,
        downloader: IMediaDownloader,
        storage: IFileSystemStorage,
        settings: ArchiverSettings,
    ) -> None:
        self.repository = repository
        self.downloader = downloader
        self.storage = storage
        self.settings = settings

    def execute(self, limit: int = 10) -> DownloadQueueResult:
        """Process queued items in descending order of virality score."""
        result = DownloadQueueResult()

        # Step 1: Reconcile any crashed tasks from previous runs
        result.reconciled_tasks = self.repository.reconcile_crashed_tasks()

        # Step 2: Fetch queued records
        queued = self.repository.get_queued(limit=limit)
        if not queued:
            return result

        for record in queued:
            assert record.id is not None
            result.total_processed += 1

            # Step 3: Transition to DOWNLOADING
            try:
                self.repository.update_status(record.id, VideoStatus.DOWNLOADING)
            except Exception as exc:
                result.failed += 1
                result.errors.append(f"Failed to set status DOWNLOADING for {record.platform_id}: {exc}")
                continue

            # Step 4: Prepare output directory and execute download
            try:
                asset_dir = self.storage.create_asset_directory(self.settings.output_dir, record)
                media_path, _ = self.downloader.download_media(
                    record=record,
                    output_directory=asset_dir,
                    max_resolution=self.settings.max_resolution,
                )

                # Step 5: Compute integrity checksum and write sidecar
                file_sha256 = self.storage.compute_file_sha256(media_path)
                rel_media_name = Path(media_path).name
                self.storage.write_sidecar_metadata(
                    directory=asset_dir,
                    record=record,
                    media_relative_path=rel_media_name,
                    file_sha256=file_sha256,
                )

                # Step 6: Mark ARCHIVED
                self.repository.update_status(
                    record_id=record.id,
                    status=VideoStatus.ARCHIVED,
                    local_path=media_path,
                    file_sha256=file_sha256,
                )
                result.succeeded += 1

            except Exception as exc:
                result.failed += 1
                err_msg = str(exc)
                result.errors.append(f"Archival failed for {record.platform_id}: {err_msg}")
                try:
                    self.repository.update_status(
                        record_id=record.id,
                        status=VideoStatus.FAILED,
                        error_message=err_msg,
                    )
                except Exception:
                    pass

            # Step 7: Rate-limit pause
            if self.settings.rate_limit_sleep_seconds > 0:
                time.sleep(self.settings.rate_limit_sleep_seconds)

        return result
