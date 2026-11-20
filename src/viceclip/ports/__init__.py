"""Abstract port protocols for driven and driving adapters."""

from viceclip.ports.discovery import IDiscoveryAdapter
from viceclip.ports.downloader import IMediaDownloader
from viceclip.ports.repository import IVideoRepository
from viceclip.ports.storage import IFileSystemStorage

__all__ = [
    "IVideoRepository",
    "IDiscoveryAdapter",
    "IMediaDownloader",
    "IFileSystemStorage",
]
