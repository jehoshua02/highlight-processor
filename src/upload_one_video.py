"""upload_one_video.py
Upload a single video to all platforms: Instagram Reels, YouTube Shorts,
and TikTok — in parallel.

Each platform runs in its own thread. A single platform failure does not
prevent the others from completing.

When a sidecar_path is provided, platforms already marked as "done" are
skipped, and results are written back immediately as each upload completes.

Usage:
    python upload_one_video.py <video_path>

Required environment variables:
    IG_USER_ID, IG_ACCESS_TOKEN, NGROK_URL        (Instagram)
    YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN  (YouTube)
    TT_CLIENT_KEY, TT_CLIENT_SECRET, TT_ACCESS_TOKEN, TT_REFRESH_TOKEN, NGROK_URL  (TikTok)
"""

import sys
import os
import json
import time
import threading
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from instagram_upload import upload_reel
from youtube_upload import upload_short
from tiktok_upload import upload_tiktok


def _is_ngrok_up():
    """Quick check whether the ngrok tunnel is reachable."""
    ngrok_url = os.environ.get("NGROK_URL", "").strip()
    if not ngrok_url:
        return False
    try:
        req = Request(ngrok_url, method="HEAD")
        with urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _now():
    """ISO-formatted UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


PLATFORMS = [
    ("Instagram Reels", upload_reel),
    ("YouTube Shorts", upload_short),
    ("TikTok", upload_tiktok),
]


def _platform_key(name):
    """Convert display name to sidecar step key, e.g. 'upload_instagram_reels'."""
    return "upload_" + name.lower().replace(" ", "_")


def upload_one_video(filepath, sidecar_path=None, skip_platforms=None):
    """Upload one video to every platform in parallel, collecting results.

    If sidecar_path is provided, platforms already marked "done" are skipped
    and each result is written to the sidecar immediately on completion.
    skip_platforms is an optional set of platform display names to skip
    entirely (e.g. {"TikTok"}).

    Returns a dict of {platform_name: (ok, error_or_none)}.
    """
    results = {}
    lock = threading.Lock()
    skip_platforms = skip_platforms or set()

    # Read sidecar for skip detection and write-back
    sidecar = None
    sidecar_lock = threading.Lock()
    if sidecar_path and os.path.exists(sidecar_path):
        with open(sidecar_path) as f:
            sidecar = json.load(f)

    def _save_sidecar():
        """Write sidecar to disk (caller must hold sidecar_lock)."""
        if not sidecar_path or sidecar is None:
            return
        tmp = sidecar_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(sidecar, f, indent=2)
        os.replace(tmp, sidecar_path)

    # Check ngrok availability for Instagram
    ngrok_up = _is_ngrok_up()

    # Skip platforms already done
    skip = set()
    if sidecar:
        for name, _ in PLATFORMS:
            key = _platform_key(name)
            if sidecar.get("steps", {}).get(key, {}).get("status") == "done":
                skip.add(name)
                results[name] = (True, None)
                print(f"  ✔ {name}: already uploaded (skipping)")

    def _upload(name, upload_fn):
        key = _platform_key(name)
        started = _now()
        t0 = time.time()
        if sidecar:
            with sidecar_lock:
                sidecar.setdefault("steps", {})[key] = {
                    "status": "in_progress", "started_at": started,
                }
                _save_sidecar()
        try:
            print(f"  ↗ {name}: uploading…")
            upload_fn(filepath)
            with lock:
                results[name] = (True, None)
            if sidecar:
                with sidecar_lock:
                    sidecar["steps"][key] = {
                        "status": "done",
                        "started_at": started,
                        "completed_at": _now(),
                        "duration_seconds": round(time.time() - t0, 1),
                    }
                    _save_sidecar()
            print(f"  ✔ {name}: done")
        except SystemExit:
            err = "upload exited with error"
            with lock:
                results[name] = (False, err)
            if sidecar:
                with sidecar_lock:
                    sidecar["steps"][key] = {
                        "status": "failed",
                        "started_at": started,
                        "completed_at": _now(),
                        "duration_seconds": round(time.time() - t0, 1),
                        "error": err,
                    }
                    _save_sidecar()
            print(f"  ✘ {name}: {err}")
        except Exception as exc:
            with lock:
                results[name] = (False, str(exc))
            if sidecar:
                with sidecar_lock:
                    sidecar["steps"][key] = {
                        "status": "failed",
                        "started_at": started,
                        "completed_at": _now(),
                        "duration_seconds": round(time.time() - t0, 1),
                        "error": str(exc),
                    }
                    _save_sidecar()
            print(f"  ✘ {name}: {exc}")

    threads = []
    for name, upload_fn in PLATFORMS:
        if name in skip:
            continue
        if name in skip_platforms:
            print(f"  ⏭ {name}: skipped (--skip-upload-tt)")
            continue
        if name == "Instagram Reels" and not ngrok_up:
            key = _platform_key(name)
            print(f"  ⚠ Skipping {name} — ngrok is not reachable")
            with lock:
                results[name] = (False, "ngrok not reachable")
            if sidecar:
                with sidecar_lock:
                    sidecar.setdefault("steps", {})[key] = {
                        "status": "failed",
                        "started_at": _now(),
                        "completed_at": _now(),
                        "error": "ngrok not reachable",
                    }
                    _save_sidecar()
            continue
        t = threading.Thread(target=_upload, args=(name, upload_fn))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Summary
    failed = sum(1 for ok, _ in results.values() if not ok)
    succeeded = sum(1 for ok, _ in results.values() if ok)
    print(f"  Uploads: {succeeded} succeeded, {failed} failed out of {len(results)}")

    if failed:
        for name, (ok, err) in results.items():
            if not ok:
                print(f"    ✘ {name}: {err}")
    else:
        print("  All uploads succeeded!")

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "--help":
        print("Usage: python upload_one_video.py <video_path>")
        print()
        print("  Uploads a _final video to Instagram Reels, YouTube Shorts,")
        print("  and TikTok in one command.")
        print()
        print("Docker usage:")
        print('  docker compose run --rm upload_one_video "/videos/clip_final.mp4"')
        sys.exit(0 if sys.argv[-1] == "--help" else 1)

    filepath = sys.argv[1]
    results = upload_one_video(filepath)
    if any(not ok for ok, _ in results.values()):
        sys.exit(1)
