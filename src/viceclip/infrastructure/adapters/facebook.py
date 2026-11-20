"""Facebook video discovery and extraction adapter."""

from datetime import datetime, timezone
import re
import time
from typing import Any, Optional, Sequence

import httpx
import yt_dlp

from viceclip.domain.entities import VideoCandidate
from viceclip.domain.enums import Platform
from viceclip.ports.discovery import IDiscoveryAdapter

# Facebook URL pattern matcher (watch, reels, fb.watch)
FB_URL_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:www\.|m\.|web\.)?(?:facebook\.com\/(?:watch\/?\?v=|reel\/|.*\/videos\/)|fb\.watch\/)([0-9a-zA-Z_-]+)"
)


class FacebookAdapter(IDiscoveryAdapter):
    """Discovery and stream extraction adapter for Facebook public videos and reels."""

    GRAPH_API_BASE = "https://graph.facebook.com/v19.0"

    def __init__(
        self,
        access_token: Optional[str] = None,
        page_ids: Sequence[str] = ("GTA6News", "RockstarGames"),
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.access_token = access_token
        self.page_ids = list(page_ids)
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self._client = client or httpx.Client(
            headers={"User-Agent": "ViceClipArchiver/0.1.0"},
            timeout=15.0,
        )

    @property
    def platform(self) -> Platform:
        return Platform.FACEBOOK

    @staticmethod
    def is_facebook_url(url: str) -> bool:
        """Check if a URL matches Facebook video or reel domain patterns."""
        return bool(FB_URL_REGEX.search(url)) or "facebook.com" in url or "fb.watch" in url

    def extract_from_url(self, url: str) -> Optional[VideoCandidate]:
        """Extract VideoCandidate metadata directly from a public Facebook URL via yt-dlp."""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception:
            return None

        if not info:
            return None

        video_id = str(info.get("id") or info.get("display_id") or "fb_unknown")
        title = info.get("title") or info.get("description") or f"Facebook Video {video_id}"
        # Truncate title if it's a long description
        title = title.split("\n")[0][:100]

        uploader = info.get("uploader") or info.get("channel") or "Facebook Creator"
        views = int(info.get("view_count") or 0)
        likes = int(info.get("like_count") or 0)
        comments = int(info.get("comment_count") or 0)
        duration = int(info.get("duration") or 0) if info.get("duration") else None

        # Publication date
        upload_date = info.get("upload_date")  # YYYYMMDD
        if upload_date and len(upload_date) == 8:
            try:
                pub_dt = datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=timezone.utc)
            except ValueError:
                pub_dt = datetime.now(timezone.utc)
        else:
            pub_dt = datetime.now(timezone.utc)

        thumb = info.get("thumbnail")

        return VideoCandidate(
            platform=Platform.FACEBOOK,
            platform_id=video_id,
            title=title,
            creator=uploader,
            source_url=url,
            published_at=pub_dt,
            views=views,
            likes=likes,
            comments=comments,
            duration_seconds=duration,
            thumbnail_url=thumb,
        )

    def fetch_trending(self, keywords: Sequence[str], max_results: int = 50) -> list[VideoCandidate]:
        """Fetch candidates across configured Facebook pages via Graph API (when token provided)."""
        if not self.access_token:
            return []

        candidates: list[VideoCandidate] = []
        for page_id in self.page_ids:
            if len(candidates) >= max_results:
                break
            url = f"{self.GRAPH_API_BASE}/{page_id}/videos"
            params = {
                "access_token": self.access_token,
                "fields": "id,description,created_time,views,likes.summary(true),comments.summary(true),length,permalink_url",
                "limit": min(max_results - len(candidates), 25),
            }
            try:
                resp = self._client.get(url, params=params)
                if resp.status_code != 200:
                    continue
                data = resp.json()
            except Exception:
                continue

            for item in data.get("data", []):
                vid_id = str(item.get("id"))
                desc = item.get("description", "Facebook GTA 6 Video")
                title = desc.split("\n")[0][:100]

                # Match keywords in description
                title_lower = title.lower()
                matches_keyword = any(kw.lower() in title_lower for kw in keywords)
                if not matches_keyword:
                    continue

                created_str = item.get("created_time", "")
                try:
                    pub_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pub_dt = datetime.now(timezone.utc)

                views = int(item.get("views", 0))
                likes = int(item.get("likes", {}).get("summary", {}).get("total_count", 0))
                comments = int(item.get("comments", {}).get("summary", {}).get("total_count", 0))
                duration = int(item.get("length", 0)) if item.get("length") else None
                permalink = item.get("permalink_url") or f"https://www.facebook.com/watch/?v={vid_id}"

                cand = VideoCandidate(
                    platform=Platform.FACEBOOK,
                    platform_id=vid_id,
                    title=title,
                    creator=page_id,
                    source_url=permalink,
                    published_at=pub_dt,
                    views=views,
                    likes=likes,
                    comments=comments,
                    duration_seconds=duration,
                )
                candidates.append(cand)

        return candidates[:max_results]
