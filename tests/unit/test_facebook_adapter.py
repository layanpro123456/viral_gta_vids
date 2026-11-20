"""Unit tests for FacebookAdapter."""

from datetime import datetime, timezone

import pytest
import respx

from viceclip.domain.enums import Platform
from viceclip.infrastructure.adapters.facebook import FacebookAdapter


def test_is_facebook_url() -> None:
    """Verify Facebook video URL pattern matching."""
    adapter = FacebookAdapter()

    assert adapter.is_facebook_url("https://www.facebook.com/watch/?v=123456789") is True
    assert adapter.is_facebook_url("https://facebook.com/reel/987654321") is True
    assert adapter.is_facebook_url("https://fb.watch/abcdEFG123/") is True
    assert adapter.is_facebook_url("https://www.facebook.com/gaming/videos/1122334455/") is True

    # Non-Facebook URLs
    assert adapter.is_facebook_url("https://www.youtube.com/watch?v=abc") is False
    assert adapter.is_facebook_url("https://reddit.com/r/GTA6/comments/123") is False


@respx.mock
def test_facebook_adapter_graph_api() -> None:
    """Verify Graph API parsing for configured pages."""
    page_id = "GTA6News"
    mock_url = f"{FacebookAdapter.GRAPH_API_BASE}/{page_id}/videos"

    respx.get(mock_url).respond(
        status_code=200,
        json={
            "data": [
                {
                    "id": "fb_vid_101",
                    "description": "GTA 6 Vice City graphics engine comparison clip!",
                    "created_time": "2026-11-19T14:00:00+00:00",
                    "views": 45000,
                    "likes": {"summary": {"total_count": 3200}},
                    "comments": {"summary": {"total_count": 410}},
                    "length": 85,
                    "permalink_url": "https://www.facebook.com/watch/?v=fb_vid_101",
                },
                {
                    "id": "fb_vid_non_gta",
                    "description": "Unrelated cooking video",
                    "created_time": "2026-11-19T14:00:00+00:00",
                    "views": 500,
                    "likes": {"summary": {"total_count": 10}},
                    "comments": {"summary": {"total_count": 2}},
                    "length": 60,
                },
            ]
        },
    )

    adapter = FacebookAdapter(access_token="mock_token", page_ids=[page_id])
    candidates = adapter.fetch_trending(keywords=["GTA 6"], max_results=10)

    assert len(candidates) == 1
    c = candidates[0]
    assert c.platform == Platform.FACEBOOK
    assert c.platform_id == "fb_vid_101"
    assert "Vice City graphics" in c.title
    assert c.views == 45000
    assert c.likes == 3200
    assert c.comments == 410
    assert c.duration_seconds == 85
