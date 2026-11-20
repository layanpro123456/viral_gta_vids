"""YouTube Data API v3 discovery adapter implementing ADR-004."""

from datetime import datetime, timezone
import re
import time
from typing import Any, Optional, Sequence

import httpx

from viceclip.domain.entities import VideoCandidate
from viceclip.domain.enums import Platform
from viceclip.ports.discovery import IDiscoveryAdapter

# Regex for ISO 8601 duration (e.g. PT1H2M34S, PT45S, PT3M)
ISO_DURATION_REGEX = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


def parse_iso8601_duration(duration_str: str) -> Optional[int]:
    """Parse ISO 8601 duration string into total seconds."""
    match = ISO_DURATION_REGEX.match(duration_str)
    if not match:
        return None
    parts = match.groupdict()
    days = int(parts.get("days") or 0)
    hours = int(parts.get("hours") or 0)
    minutes = int(parts.get("minutes") or 0)
    seconds = int(parts.get("seconds") or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


class YouTubeAdapter(IDiscoveryAdapter):
    """Quota-optimized YouTube Data API v3 adapter."""

    SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
    VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.api_key = api_key
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self._client = client or httpx.Client(timeout=15.0)

    @property
    def platform(self) -> Platform:
        return Platform.YOUTUBE

    def _get_with_retry(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """Perform HTTP GET with exponential backoff on 429 and 5xx."""
        for attempt in range(self.max_retries):
            try:
                response = self._client.get(url, params=params)
                if response.status_code == 429 or response.status_code >= 500:
                    retry_after = response.headers.get("Retry-After")
                    sleep_time = float(retry_after) if retry_after else (self.backoff_factor ** attempt)
                    time.sleep(sleep_time)
                    continue
                response.raise_for_status()
                return response.json()
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"YouTube API request failed after {self.max_retries} retries: {exc}") from exc
                time.sleep(self.backoff_factor ** attempt)
        raise RuntimeError("YouTube API request exceeded retry attempts.")

    def fetch_trending(self, keywords: Sequence[str], max_results: int = 50) -> list[VideoCandidate]:
        """Fetch candidates across keywords using 2-tier ID harvesting and details batching."""
        if not self.api_key:
            # Without API key, YouTube API cannot be reached
            return []

        harvested_ids: set[str] = set()
        candidates: list[VideoCandidate] = []

        # Tier 1: Search for IDs (harvest up to max_results distinct video IDs)
        for kw in keywords:
            if len(harvested_ids) >= max_results:
                break
            remaining = max_results - len(harvested_ids)
            fetch_limit = min(remaining, 50)

            params = {
                "key": self.api_key,
                "part": "id",
                "q": kw,
                "type": "video",
                "maxResults": fetch_limit,
                "order": "viewCount",
                "relevanceLanguage": "en",
            }
            try:
                data = self._get_with_retry(self.SEARCH_URL, params)
            except Exception:
                continue

            for item in data.get("items", []):
                vid_id = item.get("id", {}).get("videoId")
                if vid_id:
                    harvested_ids.add(vid_id)

        if not harvested_ids:
            return []

        # Tier 2: Batch fetch video details & statistics in batches of 50
        id_list = list(harvested_ids)
        for i in range(0, len(id_list), 50):
            batch = id_list[i : i + 50]
            params = {
                "key": self.api_key,
                "part": "snippet,statistics,contentDetails",
                "id": ",".join(batch),
            }
            try:
                data = self._get_with_retry(self.VIDEOS_URL, params)
            except Exception:
                continue

            for item in data.get("items", []):
                vid_id = item["id"]
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                content_details = item.get("contentDetails", {})

                # Parse publication time
                pub_raw = snippet.get("publishedAt", "")
                try:
                    pub_dt = datetime.fromisoformat(pub_raw.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pub_dt = datetime.now(timezone.utc)

                duration_sec = parse_iso8601_duration(content_details.get("duration", ""))
                thumb = snippet.get("thumbnails", {}).get("high", {}).get("url")

                candidate = VideoCandidate(
                    platform=Platform.YOUTUBE,
                    platform_id=vid_id,
                    title=snippet.get("title", ""),
                    creator=snippet.get("channelTitle", "Unknown Channel"),
                    source_url=f"https://www.youtube.com/watch?v={vid_id}",
                    published_at=pub_dt,
                    views=int(stats.get("viewCount", 0)),
                    likes=int(stats.get("likeCount", 0)),
                    comments=int(stats.get("commentCount", 0)),
                    duration_seconds=duration_sec,
                    thumbnail_url=thumb,
                )
                candidates.append(candidate)

        return candidates
