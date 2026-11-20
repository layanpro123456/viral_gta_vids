"""Pure domain models, state machine policies, and scoring algorithms."""

from viceclip.domain.entities import CatalogStats, ScoringWeights, VideoCandidate, VideoRecord
from viceclip.domain.enums import Platform, VideoStatus
from viceclip.domain.exceptions import (
    ConfigurationError,
    DomainError,
    DRMProtectedError,
    DurationExceededError,
    InvalidStateTransitionError,
    VideoUnavailableError,
)
from viceclip.domain.scoring import compute_virality_score, is_candidate_qualified
from viceclip.domain.state_machine import validate_transition

__all__ = [
    "Platform",
    "VideoStatus",
    "VideoCandidate",
    "VideoRecord",
    "ScoringWeights",
    "CatalogStats",
    "DomainError",
    "InvalidStateTransitionError",
    "DRMProtectedError",
    "VideoUnavailableError",
    "DurationExceededError",
    "ConfigurationError",
    "compute_virality_score",
    "is_candidate_qualified",
    "validate_transition",
]
