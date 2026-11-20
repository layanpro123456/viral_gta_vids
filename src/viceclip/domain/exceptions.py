"""Domain-specific exceptions."""


class DomainError(Exception):
    """Base exception for all domain logic failures."""


class InvalidStateTransitionError(DomainError):
    """Raised when an illegal video status transition is attempted."""

    def __init__(self, from_status: str, to_status: str, video_id: str | None = None) -> None:
        msg = f"Invalid state transition from {from_status} to {to_status}"
        if video_id:
            msg += f" for video {video_id}"
        super().__init__(msg)
        self.from_status = from_status
        self.to_status = to_status
        self.video_id = video_id


class DRMProtectedError(DomainError):
    """Raised when a stream is flagged as DRM protected (strictly rejected)."""


class VideoUnavailableError(DomainError):
    """Raised when a video is private, deleted, or geoblocked."""


class DurationExceededError(DomainError):
    """Raised when a video exceeds configured maximum duration."""


class ConfigurationError(DomainError):
    """Raised when application configuration is invalid or missing required values."""
