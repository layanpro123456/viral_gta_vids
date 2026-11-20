# Software Design Document (SDD): ViceClip Archiver

## 1. System Architecture
ViceClip Archiver follows a modular, pipeline-based CLI architecture. Each stage (Discovery, Scoring, Queueing, Archival) is decoupled via a local SQLite database, allowing independent execution, retries, and testability.

```text
+-------------------------------------------------------------------+
|                        CLI Entrypoint (Typer)                     |
|           [ discover | download | sync | stats | config ]         |
+----------------------------------+--------------------------------+
                                   |
        +--------------------------+--------------------------+
        |                                                     |
        v                                                     v
+-----------------------+                           +-------------------+
|   Discovery Engine    |                           |  Archival Worker  |
| - YouTube API Adapter |                           | - yt-dlp Wrapper  |
| - Reddit API Adapter  |                           | - FFmpeg Muxer    |
| - Virality Scorer     |                           | - Hasher/Verifier |
+-----------+-----------+                           +---------+---------+
            |                                                 |
            +----------------------+   +----------------------+
                                   |   |
                                   v   v
                     +-------------------------------+
                     |    Storage & State Layer      |
                     | - SQLite DB (Metadata/Queue)  |
                     | - Local Filesystem (Media)    |
                     +-------------------------------+
```

## 2. Technology Stack
- **Language:** Python 3.11+
- **CLI Framework:** `Typer` + `Rich` (for progress bars and formatted tables)
- **HTTP & API Clients:** `httpx` (async-capable HTTP client), official API SDKs where applicable
- **Media Acquisition:** `yt-dlp` (configured strictly for non-DRM, publicly accessible streams) + `ffmpeg`
- **Database:** SQLite3 with `SQLAlchemy` or `aiosqlite`
- **Configuration:** `Pydantic Settings` loading from `config.toml` and `.env`

## 3. Data Model (SQLite Schema)

### `videos` Table
Stores discovered video metadata, virality metrics, and archival status.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Internal record ID |
| `platform` | `TEXT` | `NOT NULL` | Source platform (`youtube`, `reddit`, etc.) |
| `platform_id` | `TEXT` | `NOT NULL` | Unique video ID on the source platform |
| `title` | `TEXT` | `NOT NULL` | Video title |
| `creator` | `TEXT` | `NOT NULL` | Channel or author name |
| `source_url` | `TEXT` | `NOT NULL` | Original canonical URL |
| `published_at` | `DATETIME` | `NOT NULL` | UTC publication timestamp |
| `views` | `INTEGER` | `DEFAULT 0` | View count at discovery |
| `likes` | `INTEGER` | `DEFAULT 0` | Like count at discovery |
| `comments` | `INTEGER` | `DEFAULT 0` | Comment count at discovery |
| `virality_score` | `REAL` | `DEFAULT 0.0` | Computed virality score |
| `status` | `TEXT` | `NOT NULL` | `DISCOVERED`, `QUEUED`, `DOWNLOADING`, `ARCHIVED`, `FAILED`, `SKIPPED` |
| `local_path` | `TEXT` | `NULLABLE` | Relative path to archived media file |
| `file_sha256` | `TEXT` | `NULLABLE` | Integrity hash of downloaded file |
| `error_message` | `TEXT` | `NULLABLE` | Last error if `status == FAILED` |
| `discovered_at` | `DATETIME` | `DEFAULT CURRENT_TIMESTAMP` | Record creation time |

*Unique Constraint:* `UNIQUE(platform, platform_id)`

## 4. Component Design

### 4.1 Discovery Adapters (`src/discovery/`)
All platform integrations implement a shared abstract base class:
- `BaseAdapter.fetch_trending(keywords: list[str], max_results: int) -> list[VideoCandidate]`
- **YouTubeAdapter:** Uses YouTube Data API v3 (`search.list` + `videos.list` for statistics) with an API key supplied via `YOUTUBE_API_KEY`.
- **RedditAdapter:** Uses authenticated OAuth2 / public JSON API calls to fetch top video posts from gaming subreddits (e.g., `r/GTA6`).
- **FacebookAdapter:** Interacts with Facebook Graph API and public reels/watch feeds, extracting video metadata, view counts, and engagement. Supports direct URL ingestion (`viceclip ingest` / `viceclip download --url`).

### 4.2 Virality Scorer (`src/scoring/virality.py`)
- Pure function module that accepts `VideoCandidate` objects and `ScoringConfig`.
- Filters out videos below `min_score`, exceeding `max_duration_seconds`, or matching `exclude_keywords` (e.g., `"fake"`, `"clickbait"`).

### 4.3 Archival Worker (`src/archiver/downloader.py`)
- Pulls records with `status = 'QUEUED'` in descending order of `virality_score`.
- Enforces concurrency limits (default: 2 concurrent downloads) and per-domain rate throttling.
- Organizes files deterministically:
  ```text
  archive/
  └── YYYY-MM-DD/
      └── {platform}_{platform_id}_{sanitized_title}/
          ├── video.mp4
          ├── thumbnail.jpg
          └── metadata.json
  ```

## 5. Configuration Design (`config.toml`)
```toml
[discovery]
keywords = ["GTA 6", "Grand Theft Auto VI", "#GTA6", "Vice City"]
exclude_keywords = ["prank", "mod showcase"]
max_age_hours = 48
min_virality_score = 3.5

[archiver]
output_dir = "./archive"
max_resolution = 1080
max_duration_seconds = 300
concurrent_downloads = 2
rate_limit_sleep_seconds = 3
```

## 6. Security, Ethics & Compliance Guardrails
- **No DRM Circumvention:** The archival layer explicitly rejects DRM-protected streams and never attempts to bypass encryption or paywalls.
- **Credential Safety:** API keys are loaded strictly from environment variables (`.env`), never committed to source control or written to `metadata.json`.
- **Path Sanitization:** All video titles are sanitized to prevent directory traversal (`../`) or invalid OS filename characters.
- **Attribution Preservation:** Every archived video stores the original `creator`, `source_url`, and license information (when provided by the API) in `metadata.json`.