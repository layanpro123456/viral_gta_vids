"""Pure domain virality scoring and candidate qualification algorithms."""

import math
from typing import Sequence

from viceclip.domain.entities import ScoringWeights, VideoCandidate


def compute_virality_score(
    views: int,
    age_hours: float,
    likes: int,
    comments: int,
    weights: ScoringWeights = ScoringWeights(),
) -> float:
    """Compute the normalized virality score S.

    Formula:
        S = w1 * log10(V / max(A, 1) + 1) + w2 * ((L + 2*C) / max(V, 1)) * 100

    Guards against division by zero and negative metric values.
    """
    v = max(int(views), 0)
    a = max(float(age_hours), 1.0)
    l = max(int(likes), 0)
    c = max(int(comments), 0)

    # Velocity term: log10 of views per hour + 1
    views_per_hour = v / a
    velocity_term = weights.w1 * math.log10(views_per_hour + 1.0)

    # Engagement ratio term: weighted likes and comments per view (as percentage)
    v_norm = max(v, 1)
    engagement_ratio = (l + 2.0 * c) / v_norm
    engagement_term = weights.w2 * engagement_ratio * 100.0

    score = velocity_term + engagement_term
    return round(score, 4)


def is_candidate_qualified(
    candidate: VideoCandidate,
    min_score: float = 3.5,
    max_duration_seconds: int = 300,
    max_age_hours: float = 48.0,
    exclude_keywords: Sequence[str] = (),
    weights: ScoringWeights = ScoringWeights(),
) -> tuple[bool, float, str | None]:
    """Evaluate whether a VideoCandidate qualifies for the archival queue.

    Returns:
        (is_qualified, score, rejection_reason)
    """
    # 1. Keyword exclusion check
    title_lower = candidate.title.lower()
    for kw in exclude_keywords:
        if kw.strip() and kw.lower() in title_lower:
            score = compute_virality_score(
                candidate.views, candidate.age_in_hours, candidate.likes, candidate.comments, weights
            )
            return False, score, f"Title matched excluded keyword: '{kw}'"

    # 2. Maximum duration check
    if candidate.duration_seconds is not None and candidate.duration_seconds > max_duration_seconds:
        score = compute_virality_score(
            candidate.views, candidate.age_in_hours, candidate.likes, candidate.comments, weights
        )
        return False, score, f"Duration ({candidate.duration_seconds}s) exceeds max limit ({max_duration_seconds}s)"

    # 3. Maximum age check
    if candidate.age_in_hours > max_age_hours:
        score = compute_virality_score(
            candidate.views, candidate.age_in_hours, candidate.likes, candidate.comments, weights
        )
        return False, score, f"Age ({candidate.age_in_hours:.1f}h) exceeds max limit ({max_age_hours}h)"

    # 4. Virality score threshold check
    score = compute_virality_score(
        candidate.views, candidate.age_in_hours, candidate.likes, candidate.comments, weights
    )
    if score < min_score:
        return False, score, f"Score ({score:.2f}) below minimum threshold ({min_score:.2f})"

    return True, score, None
