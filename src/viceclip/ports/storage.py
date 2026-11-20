"""Port definition for filesystem asset storage and sidecar metadata."""

from typing import Protocol

from viceclip.domain.entities import VideoRecord


class IFileSystemStorage(Protocol):
    """Port interface for filesystem operations, path sanitization, and sidecar metadata."""

    def sanitize_filename(self, name: str) -> str:
        """Sanitize a string for safe use in file/directory paths across OSes."""
        ...

    def create_asset_directory(self, base_output_dir: str, record: VideoRecord) -> str:
        """Create and return deterministic directory path: base/YYYY-MM-DD/platform_id_title."""
        ...

    def compute_file_sha256(self, filepath: str) -> str:
        """Compute SHA-256 hexadecimal checksum of a file."""
        ...

    def write_sidecar_metadata(
        self,
        directory: str,
        record: VideoRecord,
        media_relative_path: str,
        file_sha256: str,
    ) -> str:
        """Write metadata.json sidecar file in the asset directory."""
        ...
