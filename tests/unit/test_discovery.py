"""Tests for discovery adapters and DiscoverVideosUseCase."""

from datetime import datetime, timezone
import json

import httpx
import pytest
import respx

from viceclip.application.discover import DiscoverVideosUseCase
from viceclip.domain.entities import VideoCandidate
from viceclip.domain.enums import Platform, VideoStatus
from viceclip.infrastructure.adapters.reddit import RedditAdapter
from viceclip.infrastructure.adapters.youtube import YouTubeAdapter, parse_iso8601_duration
from viceclip.infrastructure.config import DiscoverySettings
from viceclip.infrastructure.storage.sqlite_repo import SQLiteVideoRepository


def test_parse_iso8601_duration() -> None:
    """Verify ISO 8601 duration string parsing."""
    assert parse_iso8601_duration("PT1M30S") == 90
    assert parse_iso8601_duration("PT45S") == 45
    assert parse_iso8601_duration("PT1H2M10S") == 3730
    assert parse_iso8601_duration("invalid") is None


@respx.mock
def test_youtube_adapter_two_tier_fetch() -> None:
    """Verify YouTubeAdapter performs 2-tier discovery (search then videos)."""
    search_mock = respx.get(YouTubeAdapter.SEARCH_URL).respond(
        status_code=200,
        json={
            "items": [
                {"id": {"videoId": "yt_123"}},
                {"id": {"videoId": "yt_456"}},
            ]
        },
    )

    videos_mock = respx.get(YouTubeAdapter.VIDEOS_URL).respond(
        status_code=200,
        json={
            "items": [
                {
                    "id": "yt_123",
                    "snippet": {
                        "title": "GTA 6 Official Trailer 2 Breakdown",
                        "channelTitle": "ViceCityGuru",
                        "publishedAt": "2026-11-19T10:00:00Z",
                        "thumbnails": {"high": {"url": "https://img.youtube.com/123.jpg"}},
                    },
                    "statistics": {
                        "viewCount": "100000",
                        "likeCount": "8000",
                        "commentCount": "1200",
                    },
                    "contentDetails": {
                        "duration": "PT2M45S",
                    },
                }
            ]
        },
    )

    adapter = YouTubeAdapter(api_key="mock_key")
    candidates = adapter.fetch_trending(keywords=["GTA 6"], max_results=10)

    assert search_mock.called
    assert videos_mock.called
    assert len(candidates) == 1
    c = candidates[0]
    assert c.platform_id == "yt_123"
    assert c.title == "GTA 6 Official Trailer 2 Breakdown"
    assert c.views == 100000
    assert c.duration_seconds == 165


@respx.mock
def test_reddit_adapter_video_filter() -> None:
    """Verify RedditAdapter identifies video posts and skips text posts."""
    respx.get("https://www.reddit.com/r/GTA6/hot.json").respond(
        status_code=200,
        json={
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "post_text",
                            "title": "Just a discussion post about map size",
                            "author": "mapper",
                            "is_video": False,
                            "score": 500,
                            "num_comments": 40,
                            "created_utc": 1732000000.0,
                        }
                    },
                    {
                        "data": {
                            "id": "post_vid",
                            "title": "Insane car physics in GTA 6 leak clip",
                            "author": "carfan",
                            "is_video": True,
                            "score": 2500,
                            "num_comments": 300,
                            "created_utc": 1732000000.0,
                            "permalink": "/r/GTA6/comments/post_vid/insane_car_physics/",
                            "media": {
                                "reddit_video": {
                                    "duration": 45,
                                }
                            },
                        }
                    },
                ]
            }
        },
    )

    adapter = RedditAdapter(subreddit="GTA6")
    candidates = adapter.fetch_trending(keywords=["GTA 6"], max_results=10)

    assert len(candidates) == 1
    assert candidates[0].platform_id == "post_vid"
    assert candidates[0].duration_seconds == 45
    assert candidates[0].likes == 2500


def test_discover_videos_use_case() -> None:
    """Verify DiscoverVideosUseCase orchestrates scoring, filtering, and queueing."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = f.name

    repo = SQLiteVideoRepository(temp_path)

    # Create dummy adapter returning 2 candidates: 1 viral, 1 disqualified (keyword)
    now = datetime.now(timezone.utc)
    cand_viral = VideoCandidate(
        platform=Platform.YOUTUBE,
        platform_id="viral_1",
        title="Real Vice City Gameplay",
        creator="RockstarFan",
        source_url="https://youtube.com/watch?v=viral_1",
        published_at=now,
        views=80000,
        likes=5000,
        comments=600,
        duration_seconds=90,
    )
    cand_excluded = VideoCandidate(
        platform=Platform.YOUTUBE,
        platform_id="excluded_1",
        title="GTA 6 Prank in real life",
        creator="PrankChannel",
        source_url="https://youtube.com/watch?v=excluded_1",
        published_at=now,
        views=90000,
        likes=3000,
        comments=400,
        duration_seconds=60,
    )

    class MockAdapter:
        @property
        def platform(self) -> Platform:
            return Platform.YOUTUBE

        def fetch_trending(self, keywords: list[str], max_results: int = 50) -> list[VideoCandidate]:
            return [cand_viral, cand_excluded]

    settings = DiscoverySettings(
        min_virality_score=3.5,
        exclude_keywords=["prank"],
    )

    use_case = DiscoverVideosUseCase(
        repository=repo,
        adapters=[MockAdapter()],
        settings=settings,
    )

    result = use_case.execute()
    assert result.total_found == 2
    assert result.newly_queued == 1
    assert result.skipped == 1

    queued_vids = repo.get_queued()
    assert len(queued_vids) == 1
    assert queued_vids[0].platform_id == "viral_1"

    skipped_vid = repo.get_by_platform_id(Platform.YOUTUBE, "excluded_1")
    assert skipped_vid is not None
    assert skipped_vid.status == VideoStatus.SKIPPED

    repo.close()
