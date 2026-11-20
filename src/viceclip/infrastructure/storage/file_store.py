"""Filesystem storage manager: path sanitization, SHA-256 hashing, and sidecar metadata."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from viceclip.domain.entities import VideoRecord
from viceclip.ports.storage import IFileSystemStorage

# Characters not permitted in Windows/Linux filenames
FORBIDDEN_CHARS_REGEX = re.compile(r'[\\/*?:"<>|]')


class LocalFileSystemStorage(IFileSystemStorage):
    """Deterministic filesystem asset manager."""

    def sanitize_filename(self, name: str, max_length: int = 60) -> str:
        """Sanitize a string into a safe, cross-platform filename."""
        # Replace forbidden characters with underscore
        clean = FORBIDDEN_CHARS_REGEX.sub("_", name)
        # Collapse multiple spaces or underscores
        clean = re.sub(r"[\s_]+", "_", clean).strip("._ ")
        # Prevent empty filename
        if not clean:
            clean = "untitled"
        # Truncate length to prevent path length overflow
        return clean[:max_length]

    def create_asset_directory(self, base_output_dir: str, record: VideoRecord) -> str:
        """Build deterministic directory path: base/YYYY-MM-DD/{platform}_{platform_id}_{sanitized_title}."""
        date_folder = record.published_at.strftime("%Y-%m-%d")
        safe_title = self.sanitize_filename(record.title)
        dir_name = f"{record.platform}_{record.platform_id}_{safe_title}"

        asset_path = Path(base_output_dir) / date_folder / dir_name
        asset_path.mkdir(parents=True, exist_ok=True)
        return str(asset_path)

    def compute_file_sha256(self, filepath: str) -> str:
        """Compute SHA-256 hexadecimal checksum of a file in 64KB blocks."""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                sha256.update(block)
        return sha256.hexdigest()

    def write_sidecar_metadata(
        self,
        directory: str,
        record: VideoRecord,
        media_relative_path: str,
        file_sha256: str,
    ) -> str:
        """Generate and save structured metadata.json sidecar file."""
        meta_path = Path(directory) / "metadata.json"
        metadata: dict[str, Any] = {
            "title": record.title,
            "creator": record.creator,
            "source_url": record.source_url,
            "platform": str(record.platform),
            "platform_id": record.platform_id,
            "published_at": record.published_at.isoformat(),
            "archived_at": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "views": record.views,
                "likes": record.likes,
                "comments": record.comments,
                "virality_score": record.virality_score,
            },
            "media_file": media_relative_path,
            "file_sha256": file_sha256,
            "compliance_notice": "Publicly accessible, non-DRM media archived for research and non-commercial analysis. All rights belong to original creator.",
        }

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        return str(meta_path)
