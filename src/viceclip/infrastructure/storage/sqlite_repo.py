"""SQLite implementation of IVideoRepository with WAL mode and crash recovery."""

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Optional

from viceclip.domain.entities import CatalogStats, VideoCandidate, VideoRecord
from viceclip.domain.enums import Platform, VideoStatus
from viceclip.domain.state_machine import validate_transition
from viceclip.ports.repository import IVideoRepository


class SQLiteVideoRepository(IVideoRepository):
    """Robust SQLite repository honoring WAL mode and state invariants."""

    def __init__(self, db_path: str = "./viceclip.db") -> None:
        self.db_path = db_path
        # Ensure parent directory exists if nested
        parent = Path(db_path).parent
        if parent and not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._configure_connection()
        self.initialize_schema()

    def _configure_connection(self) -> None:
        """Apply performance and concurrency pragmas (ADR-002)."""
        cursor = self._conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA foreign_keys = ON;")
        self._conn.commit()

    def initialize_schema(self) -> None:
        """Create videos table and optimal query indexes."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                platform_id TEXT NOT NULL,
                title TEXT NOT NULL,
                creator TEXT NOT NULL,
                source_url TEXT NOT NULL,
                published_at TEXT NOT NULL,
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                virality_score REAL DEFAULT 0.0,
                status TEXT NOT NULL,
                local_path TEXT,
                file_sha256 TEXT,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(platform, platform_id)
            );
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_videos_status_score ON videos(status, virality_score DESC);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_videos_platform_id ON videos(platform, platform_id);"
        )
        self._conn.commit()

    def _row_to_record(self, row: sqlite3.Row) -> VideoRecord:
        """Convert a database row into a domain VideoRecord entity."""
        pub_dt = datetime.fromisoformat(row["published_at"])
        disc_dt = datetime.fromisoformat(row["discovered_at"]) if row["discovered_at"] else None
        return VideoRecord(
            id=row["id"],
            platform=Platform(row["platform"]),
            platform_id=row["platform_id"],
            title=row["title"],
            creator=row["creator"],
            source_url=row["source_url"],
            published_at=pub_dt,
            views=row["views"],
            likes=row["likes"],
            comments=row["comments"],
            virality_score=row["virality_score"],
            status=VideoStatus(row["status"]),
            local_path=row["local_path"],
            file_sha256=row["file_sha256"],
            error_message=row["error_message"],
            retry_count=row["retry_count"],
            discovered_at=disc_dt,
        )

    def get_by_platform_id(self, platform: Platform, platform_id: str) -> Optional[VideoRecord]:
        """Fetch a single record by unique platform and platform_id."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM videos WHERE platform = ? AND platform_id = ? LIMIT 1;",
            (str(platform), platform_id),
        )
        row = cursor.fetchone()
        return self._row_to_record(row) if row else None

    def upsert_candidate(
        self, candidate: VideoCandidate, score: float, status: VideoStatus
    ) -> tuple[VideoRecord, bool]:
        """Insert or update a discovered video candidate."""
        cursor = self._conn.cursor()
        existing = self.get_by_platform_id(candidate.platform, candidate.platform_id)

        pub_str = candidate.published_at.isoformat()
        now_str = datetime.now(timezone.utc).isoformat()

        if existing is None:
            # Newly discovered video
            cursor.execute(
                """
                INSERT INTO videos (
                    platform, platform_id, title, creator, source_url, published_at,
                    views, likes, comments, virality_score, status, discovered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    str(candidate.platform),
                    candidate.platform_id,
                    candidate.title,
                    candidate.creator,
                    candidate.source_url,
                    pub_str,
                    candidate.views,
                    candidate.likes,
                    candidate.comments,
                    score,
                    str(status),
                    now_str,
                ),
            )
            self._conn.commit()
            rec = self.get_by_platform_id(candidate.platform, candidate.platform_id)
            assert rec is not None
            return rec, True

        # Existing record: update metrics and conditionally promote status
        new_status = existing.status
        if existing.status == VideoStatus.SKIPPED and status == VideoStatus.QUEUED:
            new_status = VideoStatus.QUEUED

        cursor.execute(
            """
            UPDATE videos SET
                title = ?,
                creator = ?,
                views = ?,
                likes = ?,
                comments = ?,
                virality_score = ?,
                status = ?
            WHERE id = ?;
            """,
            (
                candidate.title,
                candidate.creator,
                candidate.views,
                candidate.likes,
                candidate.comments,
                score,
                str(new_status),
                existing.id,
            ),
        )
        self._conn.commit()
        updated = self.get_by_platform_id(candidate.platform, candidate.platform_id)
        assert updated is not None
        return updated, False

    def get_queued(self, limit: int = 50) -> list[VideoRecord]:
        """Fetch videos with status QUEUED ordered by virality_score descending."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT * FROM videos
            WHERE status = 'QUEUED'
            ORDER BY virality_score DESC
            LIMIT ?;
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        return [self._row_to_record(r) for r in rows]

    def update_status(
        self,
        record_id: int,
        status: VideoStatus,
        error_message: Optional[str] = None,
        local_path: Optional[str] = None,
        file_sha256: Optional[str] = None,
    ) -> None:
        """Transition status honoring state machine policies."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE id = ?;", (record_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Record with ID {record_id} not found in database.")

        current_status = VideoStatus(row["status"])
        validate_transition(current_status, status, str(record_id))

        cursor.execute(
            """
            UPDATE videos SET
                status = ?,
                error_message = ?,
                local_path = COALESCE(?, local_path),
                file_sha256 = COALESCE(?, file_sha256)
            WHERE id = ?;
            """,
            (str(status), error_message, local_path, file_sha256, record_id),
        )
        self._conn.commit()

    def reconcile_crashed_tasks(self) -> int:
        """Reset records stuck in DOWNLOADING state back to QUEUED."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            UPDATE videos
            SET status = 'QUEUED', retry_count = retry_count + 1
            WHERE status = 'DOWNLOADING';
            """
        )
        recovered_count = cursor.rowcount
        self._conn.commit()
        return max(recovered_count, 0)

    def get_stats(self) -> CatalogStats:
        """Return counts of videos partitioned by status."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT status, COUNT(*) as count
            FROM videos
            GROUP BY status;
            """
        )
        counts = {row["status"]: row["count"] for row in cursor.fetchall()}
        total = sum(counts.values())

        return CatalogStats(
            total=total,
            discovered=counts.get(str(VideoStatus.DISCOVERED), 0),
            queued=counts.get(str(VideoStatus.QUEUED), 0),
            downloading=counts.get(str(VideoStatus.DOWNLOADING), 0),
            archived=counts.get(str(VideoStatus.ARCHIVED), 0),
            failed=counts.get(str(VideoStatus.FAILED), 0),
            skipped=counts.get(str(VideoStatus.SKIPPED), 0),
        )

    def close(self) -> None:
        """Close database connection."""
        self._conn.close()
