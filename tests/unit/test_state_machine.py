"""Unit tests for the video lifecycle state machine."""

import pytest

from viceclip.domain.enums import VideoStatus
from viceclip.domain.exceptions import InvalidStateTransitionError
from viceclip.domain.state_machine import can_transition, validate_transition


def test_legal_transitions() -> None:
    """Test valid forward transitions."""
    # DISCOVERED -> QUEUED
    assert can_transition(VideoStatus.DISCOVERED, VideoStatus.QUEUED)
    validate_transition(VideoStatus.DISCOVERED, VideoStatus.QUEUED)

    # DISCOVERED -> SKIPPED
    assert can_transition(VideoStatus.DISCOVERED, VideoStatus.SKIPPED)

    # QUEUED -> DOWNLOADING
    assert can_transition(VideoStatus.QUEUED, VideoStatus.DOWNLOADING)

    # DOWNLOADING -> ARCHIVED
    assert can_transition(VideoStatus.DOWNLOADING, VideoStatus.ARCHIVED)

    # DOWNLOADING -> FAILED
    assert can_transition(VideoStatus.DOWNLOADING, VideoStatus.FAILED)

    # DOWNLOADING -> QUEUED (Crash recovery / retry)
    assert can_transition(VideoStatus.DOWNLOADING, VideoStatus.QUEUED)

    # FAILED -> QUEUED
    assert can_transition(VideoStatus.FAILED, VideoStatus.QUEUED)


def test_illegal_transitions_raise() -> None:
    """Test that illegal transitions raise InvalidStateTransitionError."""
    # ARCHIVED is terminal
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(VideoStatus.ARCHIVED, VideoStatus.QUEUED)

    with pytest.raises(InvalidStateTransitionError):
        validate_transition(VideoStatus.ARCHIVED, VideoStatus.DOWNLOADING)

    # Cannot jump directly from DISCOVERED to ARCHIVED
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(VideoStatus.DISCOVERED, VideoStatus.ARCHIVED)

    # Cannot transition directly from QUEUED to ARCHIVED without DOWNLOADING
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(VideoStatus.QUEUED, VideoStatus.ARCHIVED)
