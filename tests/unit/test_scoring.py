"""Unit tests for virality scoring formula and candidate filtering."""

from datetime import datetime, timedelta, timezone

import pytest

from viceclip.domain.entities import ScoringWeights, VideoCandidate
from viceclip.domain.enums import Platform
from viceclip.domain.scoring import compute_virality_score, is_candidate_qualified


def test_virality_score_basic_calculation() -> None:
    """Verify standard virality score calculation with known parameters."""
    # views = 10,000, age = 10 hours, likes = 500, comments = 100
    # views_per_hour = 1,000 -> log10(1001) ~ 3.00043
    # velocity_term = 0.7 * 3.00043 ~ 2.1003
    # engagement_ratio = (500 + 200) / 10000 = 700 / 10000 = 0.07 (7%)
    # engagement_term = 0.3 * 0.07 * 100 = 2.1
    # total score ~ 4.2003
    score = compute_virality_score(
        views=10000,
        age_hours=10.0,
        likes=500,
        comments=100,
        weights=ScoringWeights(w1=0.7, w2=0.3),
    )
    assert 4.19 <= score <= 4.21


def test_virality_score_zero_views_and_zero_age() -> None:
    """Verify that zero views and zero age do not cause division by zero."""
    score = compute_virality_score(
        views=0,
        age_hours=0.0,
        likes=0,
        comments=0,
    )
    # views_per_hour = 0 / 1 = 0 -> log10(1) = 0
    # engagement_ratio = 0 / 1 = 0
    assert score == 0.0


def test_virality_score_negative_inputs_sanitized() -> None:
    """Negative values should be clamped to 0."""
    score = compute_virality_score(views=-50, age_hours=-5, likes=-10, comments=-5)
    assert score == 0.0


def test_is_candidate_qualified_passes() -> None:
    """Candidate with high views and engagement passes qualification."""
    now = datetime.now(timezone.utc)
    candidate = VideoCandidate(
        platform=Platform.YOUTUBE,
        platform_id="test123",
        title="Epic GTA 6 Vice City Police Chase",
        creator="ViceCityGamer",
        source_url="https://youtube.com/watch?v=test123",
        published_at=now - timedelta(hours=5),
        views=50000,
        likes=3500,
        comments=400,
        duration_seconds=120,
    )
    qualified, score, reason = is_candidate_qualified(
        candidate=candidate,
        min_score=3.5,
        max_duration_seconds=300,
        max_age_hours=48.0,
        exclude_keywords=["prank", "mod showcase"],
    )
    assert qualified is True
    assert score >= 3.5
    assert reason is None


def test_is_candidate_qualified_rejected_keyword() -> None:
    """Candidate with blacklisted keyword is rejected."""
    now = datetime.now(timezone.utc)
    candidate = VideoCandidate(
        platform=Platform.YOUTUBE,
        platform_id="test456",
        title="Crazy GTA 6 PRANK on Vice City cops!",
        creator="Prankster",
        source_url="https://youtube.com/watch?v=test456",
        published_at=now - timedelta(hours=2),
        views=100000,
        likes=8000,
        comments=1000,
        duration_seconds=60,
    )
    qualified, score, reason = is_candidate_qualified(
        candidate=candidate,
        min_score=3.0,
        exclude_keywords=["prank"],
    )
    assert qualified is False
    assert reason is not None
    assert "excluded keyword" in reason.lower()


def test_is_candidate_qualified_rejected_duration() -> None:
    """Candidate exceeding maximum duration is rejected."""
    now = datetime.now(timezone.utc)
    candidate = VideoCandidate(
        platform=Platform.YOUTUBE,
        platform_id="test789",
        title="GTA 6 10-Hour Vice City Ambience",
        creator="ChillGamer",
        source_url="https://youtube.com/watch?v=test789",
        published_at=now - timedelta(hours=1),
        views=200000,
        likes=10000,
        comments=500,
        duration_seconds=36000,
    )
    qualified, score, reason = is_candidate_qualified(
        candidate=candidate,
        max_duration_seconds=300,
    )
    assert qualified is False
    assert reason is not None
    assert "exceeds max limit" in reason.lower()


def test_is_candidate_qualified_rejected_age() -> None:
    """Candidate older than max_age_hours is rejected."""
    now = datetime.now(timezone.utc)
    candidate = VideoCandidate(
        platform=Platform.YOUTUBE,
        platform_id="testold",
        title="GTA 6 Trailer Reaction",
        creator="OldGamer",
        source_url="https://youtube.com/watch?v=testold",
        published_at=now - timedelta(hours=72),
        views=10000,
        likes=500,
        comments=50,
        duration_seconds=90,
    )
    qualified, score, reason = is_candidate_qualified(
        candidate=candidate,
        max_age_hours=48.0,
    )
    assert qualified is False
    assert reason is not None
    assert "exceeds max limit" in reason.lower()
