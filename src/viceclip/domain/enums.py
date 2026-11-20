"""Domain enumerations for platforms and video archival lifecycle."""

from enum import Enum


class Platform(str, Enum):
    """Supported source platforms."""
    YOUTUBE = "youtube"
    REDDIT = "reddit"
    FACEBOOK = "facebook"
    GENERIC = "generic"

    def __str__(self) -> str:
        return self.value


class VideoStatus(str, Enum):
    """Lifecycle states of a video candidate."""
    DISCOVERED = "DISCOVERED"
    QUEUED = "QUEUED"
    DOWNLOADING = "DOWNLOADING"
    ARCHIVED = "ARCHIVED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

    def __str__(self) -> str:
        return self.value
