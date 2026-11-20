"""Reddit discovery adapter fetching video posts from GTA 6 communities."""

from datetime import datetime, timezone
import time
from typing import Any, Optional, Sequence

import httpx

from viceclip.domain.entities import VideoCandidate
from viceclip.domain.enums import Platform
from viceclip.ports.discovery import IDiscoveryAdapter


class RedditAdapter(IDiscoveryAdapter):
    """Discovery adapter fetching top video submissions from Reddit."""

    BASE_URL = "https://www.reddit.com"

    def __init__(
        self,
        subreddit: str = "GTA6",
        user_agent: str = "ViceClipArchiver/0.1.0",
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.subreddit = subreddit
        self.user_agent = user_agent
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self._client = client or httpx.Client(
            headers={"User-Agent": self.user_agent},
            follow_redirects=True,
            timeout=15.0,
        )

    @property
    def platform(self) -> Platform:
        return Platform.REDDIT

    def _get_with_retry(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """Perform HTTP GET with backoff."""
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
                    raise RuntimeError(f"Reddit API request failed: {exc}") from exc
                time.sleep(self.backoff_factor ** attempt)
        return {}

    def fetch_trending(self, keywords: Sequence[str], max_results: int = 50) -> list[VideoCandidate]:
        """Fetch trending video clips from subreddit."""
        url = f"{self.BASE_URL}/r/{self.subreddit}/hot.json"
        params = {"limit": max(min(max_results, 100), 10)}

        try:
            data = self._get_with_retry(url, params=params)
        except Exception:
            return []

        children = data.get("data", {}).get("children", [])
        candidates: list[VideoCandidate] = []

        for item in children:
            post = item.get("data", {})
            # Check if this post is video content
            is_video = post.get("is_video", False)
            post_hint = post.get("post_hint", "")
            media = post.get("media") or {}
            reddit_video = media.get("reddit_video") or {}

            if not (is_video or post_hint == "hosted:video" or reddit_video):
                continue

            post_id = post.get("id", "")
            if not post_id:
                continue

            created_utc = post.get("created_utc", 0.0)
            try:
                pub_dt = datetime.fromtimestamp(created_utc, timezone.utc)
            except (ValueError, OSError):
                pub_dt = datetime.now(timezone.utc)

            score = int(post.get("score", 0))
            num_comments = int(post.get("num_comments", 0))
            # Reddit public API does not expose raw view counts; we estimate views from upvote velocity
            estimated_views = max(score * 15, 100)

            duration = reddit_video.get("duration")
            thumb = post.get("thumbnail")
            if thumb in ("default", "self", "nsfw", ""):
                thumb = None

            permalink = post.get("permalink", f"/r/{self.subreddit}/comments/{post_id}/")
            source_url = f"https://www.reddit.com{permalink}"

            candidate = VideoCandidate(
                platform=Platform.REDDIT,
                platform_id=post_id,
                title=post.get("title", ""),
                creator=f"u/{post.get('author', 'unknown')}",
                source_url=source_url,
                published_at=pub_dt,
                views=estimated_views,
                likes=score,
                comments=num_comments,
                duration_seconds=duration,
                thumbnail_url=thumb,
            )
            candidates.append(candidate)

        return candidates[:max_results]
