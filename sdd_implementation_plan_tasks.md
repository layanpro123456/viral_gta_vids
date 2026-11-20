# Implementation Plan & Verification Checklist

This roadmap breaks down the development of **ViceClip Archiver** into iterative, testable milestones following Specification-Driven Development (SDD).

## Phase 1: Project Scaffolding & Configuration
- [x] Initialize Python project with `pyproject.toml` (Python 3.11+, `typer`, `rich`, `httpx`, `pydantic-settings`, `yt-dlp`, `pytest`).
- [x] Create directory structure (`src/viceclip/domain`, `src/viceclip/ports`, `src/viceclip/application`, `src/viceclip/infrastructure`, `src/viceclip/cli`, `tests/`).
- [x] Implement `config.toml` loader and `.env` validation using Pydantic.
- [x] Set up structured logging and a `.gitignore` excluding `.env`, `*.db`, and `archive/`.

## Phase 2: Storage & State Layer
- [x] Implement SQLite schema migration/initialization script (`videos` table with unique constraint on `(platform, platform_id)` and WAL mode).
- [x] Build repository methods: `upsert_candidate()`, `get_queued()`, `update_status()`, `reconcile_crashed_tasks()`, and `get_stats()`.
- [x] Write unit tests verifying deduplication and state transitions (`DISCOVERED -> QUEUED -> DOWNLOADING -> ARCHIVED`).

## Phase 3: Discovery & Virality Scoring
- [x] Define `VideoCandidate` model and `IDiscoveryAdapter` interface protocol.
- [x] Implement `compute_virality_score()` with configurable weights and keyword/duration exclusion filters.
- [x] Implement `YouTubeAdapter` using YouTube Data API v3 with quota-aware batching (search ID harvesting + 50-video batch details).
- [x] Implement `RedditAdapter` for trending GTA 6 community clips.
- [x] Write unit tests with mocked API responses (using `respx`) to validate scoring and filtering logic.

## Phase 4: Archival Pipeline
- [x] Implement safe filename/path sanitizer (`LocalFileSystemStorage`) to prevent path traversal and OS-incompatible names.
- [x] Build `YtDlpDownloader` Anti-Corruption Layer wrapper around `yt-dlp` enforcing:
  - Format selection (e.g., `bestvideo[height<=1080]+bestaudio/best`)
  - Duration cap (`max_duration_seconds`)
  - Non-DRM pre-flight check and graceful skipping of restricted/live streams
  - Companion `metadata.json` generation and SHA-256 checksum calculation
- [x] Implement retry logic with exponential backoff for transient network failures.

## Phase 5: CLI Integration & Verification
- [x] Wire up Typer commands:
  - `viceclip discover` — Fetches and scores new candidates.
  - `viceclip download` — Processes queued items into `archive/`.
  - `viceclip sync` — Runs discovery followed by download.
  - `viceclip stats` — Displays Rich table of archived/queued/failed counts.
  - `viceclip config` — Displays active configuration parameters and authentication status.
- [x] Run end-to-end integration test suite (25/25 tests passing, 80% coverage).
- [x] Verify all Acceptance Criteria from `functional_non_functional_specification.md`.
