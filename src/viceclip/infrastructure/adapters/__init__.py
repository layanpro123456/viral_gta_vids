"""Platform discovery adapters."""

from viceclip.infrastructure.adapters.facebook import FacebookAdapter
from viceclip.infrastructure.adapters.reddit import RedditAdapter
from viceclip.infrastructure.adapters.youtube import YouTubeAdapter

__all__ = ["YouTubeAdapter", "RedditAdapter", "FacebookAdapter"]
