# Project Specification: ViceClip Archiver (Viral GTA 6 Video Tool)

## 1. Overview
**ViceClip Archiver** is an automated discovery, ranking, and archival tool designed to identify trending and viral *Grand Theft Auto VI* (GTA 6) video clips across supported platforms and archive publicly accessible, non-DRM media along with structured metadata.

## 2. Goals & Non-Goals
### Goals
- **Automated Discovery:** Query official platform APIs to find trending GTA 6 content based on configurable keywords, tags, and engagement velocity.
- **Virality Scoring:** Rank discovered videos using a transparent, configurable scoring formula (views per hour, like-to-view ratio, and comment engagement).
- **Reliable Archival:** Download non-DRM, publicly accessible videos (such as Creative Commons or authorized creator clips) with automatic deduplication, format selection, and metadata sidecar files (`.json`).
- **Compliance First:** Respect API rate limits, platform Terms of Service, and copyright attribution metadata.

### Non-Goals
- Bypassing Digital Rights Management (DRM), paywalls, or private account access controls.
- Automated re-uploading or redistribution of copyrighted material without creator permission.
- Providing a public-facing video hosting or streaming service.

## 3. User Personas & Use Cases
- **Content Researcher / Analyst:** Tracks trending GTA 6 community reactions, trailer breakdowns, and gameplay trends over time.
- **Personal Archivist:** Saves high-engagement community clips locally with organized folder structures and searchable metadata.

## 4. Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **FR-01** | **Keyword & Tag Discovery** | High | System queries configured sources (YouTube Data API v3, Reddit API, Facebook Graph API/reels) using customizable queries (`"GTA 6"`, `"#GTA6"`, `"Vice City"`). |
| **FR-02** | **Virality Scoring Engine** | High | System calculates a virality score for each candidate video and filters out items below a user-defined threshold. |
| **FR-03** | **Deduplication** | High | System checks the local metadata store by `(platform, platform_video_id)` before queueing a download to prevent duplicate fetches. |
| **FR-04** | **Media Download & Metadata** | High | System downloads non-DRM media in the configured resolution (e.g., up to 1080p MP4) and writes a companion metadata JSON file containing creator credit, source URL, and timestamp. Supports YouTube, Reddit, and Facebook. |
| **FR-05** | **CLI Interface** | High | Users can trigger discovery, direct URL ingestion, download queues, configuration checks, and status reports via CLI commands (`discover`, `ingest`, `download`, `sync`, `stats`, `config`). |
| **FR-06** | **Rate Limit & Retry Handling** | Medium | System implements exponential backoff for HTTP `429`/`5xx` responses and honors `Retry-After` headers. |
| **FR-07** | **Scheduled Sync Mode** | Low | Optional cron/daemon mode to run discovery and archival on a configurable interval. |

## 5. Virality Scoring Specification
To prioritize genuinely viral clips over older high-view videos, the system computes a normalized virality score $S$ for each video:

$$S = w_1 \cdot \log_{10}\left(\frac{V}{\max(A, 1)} + 1\right) + w_2 \cdot \left(\frac{L + 2C}{\max(V, 1)}\right) \cdot 100$$

Where:
- $V$ = Total view count
- $A$ = Age of the video in hours since publication
- $L$ = Total like count
- $C$ = Total comment count
- $w_1, w_2$ = Configurable weights (default: $w_1 = 0.7$, $w_2 = 0.3$)

## 6. Non-Functional Requirements
- **Performance:** Discovery queries should process up to 500 candidate items in under 10 seconds (excluding external API latency).
- **Reliability:** Interrupted downloads must clean up partial `.part` files or resume cleanly on the next run.
- **Portability:** Must run on Linux, macOS, and Windows (Python 3.11+ with `ffmpeg` installed).
- **Observability:** Structured logging (JSON or human-readable console logs) with configurable verbosity (`INFO`, `DEBUG`, `ERROR`).