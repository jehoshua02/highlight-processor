# Copilot Workspace Instructions

## Project Overview
**Highlight Processor** — a local video processing pipeline for creating Instagram Reels and YouTube Shorts from gameplay/highlight clips. Runs entirely via Docker Compose.

**Pipeline:** Raw video → crop to 9:16 (1080×1920) → remove vocals (Spleeter AI) → upload to Instagram Reels (Graph API) or YouTube Shorts (YouTube Data API v3).

## Architecture

### Source Files (`src/`)
| File | Purpose |
|---|---|
| `crop_video.py` | Center-crops video to 9:16, resizes to 1080×1920, outputs AAC audio |
| `scrub_voices.py` | Extracts audio → Spleeter 2-stem separation → replaces with accompaniment only |
| `process_one_video.py` | Orchestrates crop → scrub; uses `_processing` suffix for intermediates, renames to `_final` on success |
| `process_all_videos.py` | Batch runner; scans folder for unprocessed videos, processes sequentially |
| `instagram_upload.py` | 3-step Graph API upload: create container → poll status → publish. Uses ngrok URL for public file access |
| `youtube_upload.py` | YouTube Shorts upload via Data API v3 resumable upload. Title and description derived from filename. Includes `--auth` OAuth flow for obtaining refresh token |
| `webhook_server.py` | Flask app for Meta webhook verification (GET) and event receipt (POST) at `/webhook/instagram` |

### Docker Services (`docker-compose.yml`)
- **crop / scrub_voices / process / process_all** — Processing services sharing one image (`Dockerfile`, Python 3.10-slim + ffmpeg + moviepy + spleeter)
- **instagram_upload** — Instagram Reels upload service using same image
- **youtube_upload** — YouTube Shorts upload service using same image
- **webhook** — Minimal Flask image (`Dockerfile.webhook`)
- **file-server** — nginx:alpine serving `./videos/` as static files + proxying `/webhook/` to Flask
- **ngrok** — Public tunnel so Instagram can fetch video files

### Environment Variables (from `.env`, not committed)
- `IG_USER_ID`, `IG_ACCESS_TOKEN` — Instagram Graph API credentials
- `NGROK_AUTHTOKEN`, `NGROK_URL` — ngrok tunnel config
- `IG_WEBHOOK_VERIFY_TOKEN` — webhook verification secret
- `YT_CLIENT_ID`, `YT_CLIENT_SECRET` — YouTube OAuth2 credentials from Google Cloud Console
- `YT_REFRESH_TOKEN` — YouTube OAuth2 refresh token (obtain via `--auth`)

## Coding Conventions
- **Python 3.10**, no type hints, no `argparse` — CLI args via `sys.argv`
- **Error handling:** `print()` + `sys.exit(1)` pattern (no exceptions propagated in CLI mode); `process_one_video` uses `try/finally` for cleanup
- **Output via `print()`**, not `logging` (except `webhook_server.py`)
- **Docstrings** on all modules and most functions
- **File naming suffixes:** `_cropped_9_16`, `_novocals`, `_final`, `_processing` (in-progress)
- **Idempotency:** `process_all_videos.py` skips already-processed files by checking suffixes
- Every script has `if __name__ == "__main__"` with `--help` support and Docker usage examples
- **Docker pattern:** One shared image for processing services; each service differs only by entrypoint

## Key Dependencies
- `moviepy 1.0.3` — video editing
- `spleeter 2.4.0` — AI vocal separation
- `Flask ≥3.0` — webhook server
- `numpy <2.0`, `Pillow <10.0` — pinned for compatibility
- System: `ffmpeg`, `libsndfile1`

## Running
All operations run via Docker Compose:
```
docker compose run --rm process "/videos/myclip.mp4"
docker compose run --rm process_all
docker compose run --rm instagram_upload "/videos/clip_final.mp4" "Caption"
docker compose run --rm youtube_upload "/videos/clip_final.mp4"
docker compose run --rm -p 8080:8080 youtube_upload --auth
```
