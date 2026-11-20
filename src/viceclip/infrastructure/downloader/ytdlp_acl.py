"""yt-dlp Anti-Corruption Layer enforcing ADR-003, non-DRM guardrails, and duration limits."""

from pathlib import Path
from typing import Any, Optional

import yt_dlp

from viceclip.domain.entities import VideoRecord
from viceclip.domain.exceptions import (
    DomainError,
    DRMProtectedError,
    DurationExceededError,
    VideoUnavailableError,
)
from viceclip.ports.downloader import IMediaDownloader


class YtDlpDownloader(IMediaDownloader):
    """Anti-corruption wrapper around yt-dlp library."""

    def __init__(self, max_duration_seconds: int = 300) -> None:
        self.max_duration_seconds = max_duration_seconds

    def _cleanup_partial_files(self, directory: Path) -> None:
        """Purge unfinalized .part and .ytdl files on failure."""
        if not directory.exists():
            return
        for item in directory.glob("*.part*"):
            try:
                item.unlink(missing_ok=True)
            except OSError:
                pass
        for item in directory.glob("*.ytdl"):
            try:
                item.unlink(missing_ok=True)
            except OSError:
                pass

    def download_media(
        self,
        record: VideoRecord,
        output_directory: str,
        max_resolution: int = 1080,
    ) -> tuple[str, Optional[str]]:
        """Validate stream safety and download non-DRM media."""
        out_dir = Path(output_directory)
        out_dir.mkdir(parents=True, exist_ok=True)

        # 1. Pre-flight extraction options (no download)
        inspect_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        try:
            with yt_dlp.YoutubeDL(inspect_opts) as ydl:
                info = ydl.extract_info(record.source_url, download=False)
        except Exception as exc:
            msg = str(exc).lower()
            if "drm" in msg:
                raise DRMProtectedError(f"DRM protection detected: {exc}") from exc
            if "private" in msg or "unavailable" in msg or "removed" in msg:
                raise VideoUnavailableError(f"Video unavailable: {exc}") from exc
            raise DomainError(f"Pre-flight extraction failed: {exc}") from exc

        if not info:
            raise VideoUnavailableError("No metadata returned by extractor.")

        # Guard 1: Rejection of Live Streams
        if info.get("is_live"):
            raise DomainError("Live streams cannot be archived.")

        # Guard 2: Rejection of DRM Streams
        if info.get("drm"):
            raise DRMProtectedError("Stream marked as DRM-protected.")

        # Check formats for DRM indicators
        for fmt in info.get("formats", []):
            if fmt.get("has_drm") or fmt.get("drm"):
                raise DRMProtectedError("Format contains DRM encryption.")

        # Guard 3: Maximum Duration Check
        duration = info.get("duration")
        if duration and duration > self.max_duration_seconds:
            raise DurationExceededError(
                f"Video duration ({duration}s) exceeds maximum allowed ({self.max_duration_seconds}s)"
            )

        # 2. Execution options for actual download
        target_template = str(out_dir / "video.%(ext)s")
        download_opts = {
            "outtmpl": target_template,
            "format": f"bestvideo[height<={max_resolution}]+bestaudio/best[height<={max_resolution}]/best",
            "writethumbnail": True,
            "quiet": True,
            "no_warnings": True,
            "updatetime": False,
        }

        try:
            with yt_dlp.YoutubeDL(download_opts) as ydl:
                ydl.download([record.source_url])
        except Exception as exc:
            self._cleanup_partial_files(out_dir)
            msg = str(exc).lower()
            if "drm" in msg:
                raise DRMProtectedError(f"DRM error during download: {exc}") from exc
            raise DomainError(f"Media download failed: {exc}") from exc

        # 3. Discover downloaded video and thumbnail files
        media_file: Optional[Path] = None
        thumb_file: Optional[Path] = None

        for child in out_dir.iterdir():
            if child.name.startswith("video.") and not child.name.endswith((".part", ".ytdl")):
                media_file = child
                break

        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            candidate_thumb = out_dir / f"video{ext}"
            if candidate_thumb.exists():
                thumb_file = candidate_thumb
                break

        if not media_file or not media_file.exists():
            self._cleanup_partial_files(out_dir)
            raise DomainError("Download finished but target media file not found on disk.")

        return str(media_file), str(thumb_file) if thumb_file else None
