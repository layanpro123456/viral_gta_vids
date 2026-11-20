"""Port definition for media download engine."""

from typing import Optional, Protocol

from viceclip.domain.entities import VideoRecord


class IMediaDownloader(Protocol):
    """Adapter port interface for media stream extraction and downloading."""

    def download_media(
        self,
        record: VideoRecord,
        output_directory: str,
        max_resolution: int = 1080,
    ) -> tuple[str, Optional[str]]:
        """Download non-DRM media stream to the specified directory.

        Returns:
            (media_filepath, thumbnail_filepath_or_none)

        Raises:
            DRMProtectedError: If media stream contains DRM protection.
            DurationExceededError: If duration exceeds limit.
            VideoUnavailableError: If media is deleted/private.
        """
        ...
