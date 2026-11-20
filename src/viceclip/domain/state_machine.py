"""State machine rules and transition validation for video lifecycle."""

from viceclip.domain.enums import VideoStatus
from viceclip.domain.exceptions import InvalidStateTransitionError

# Matrix of legal status transitions: current_status -> set of allowed next_statuses
LEGAL_TRANSITIONS: dict[VideoStatus, set[VideoStatus]] = {
    VideoStatus.DISCOVERED: {VideoStatus.QUEUED, VideoStatus.SKIPPED},
    VideoStatus.QUEUED: {VideoStatus.DOWNLOADING, VideoStatus.SKIPPED},
    VideoStatus.DOWNLOADING: {VideoStatus.ARCHIVED, VideoStatus.FAILED, VideoStatus.QUEUED},
    VideoStatus.ARCHIVED: set(),  # Terminal state
    VideoStatus.FAILED: {VideoStatus.QUEUED},  # Allowed for manual or automated retry
    VideoStatus.SKIPPED: {VideoStatus.QUEUED},  # Allowed if engagement re-scoring promotes it
}


def validate_transition(from_status: VideoStatus, to_status: VideoStatus, video_id: str | None = None) -> None:
    """Ensure a state transition is legal according to domain policies.

    Raises:
        InvalidStateTransitionError if the transition is prohibited.
    """
    allowed = LEGAL_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise InvalidStateTransitionError(
            from_status=str(from_status),
            to_status=str(to_status),
            video_id=video_id,
        )


def can_transition(from_status: VideoStatus, to_status: VideoStatus) -> bool:
    """Check if a transition is legal without throwing an exception."""
    return to_status in LEGAL_TRANSITIONS.get(from_status, set())
