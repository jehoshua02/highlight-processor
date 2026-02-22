"""upload_one_video.py
Upload a single video to all platforms: Instagram Reels, YouTube Shorts,
and TikTok — in parallel.

Each platform runs in its own thread. A single platform failure does not
prevent the others from completing.

Usage:
    python upload_one_video.py <video_path>

Required environment variables:
    IG_USER_ID, IG_ACCESS_TOKEN, NGROK_URL        (Instagram)
    YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN  (YouTube)
    TT_CLIENT_KEY, TT_CLIENT_SECRET, TT_ACCESS_TOKEN, TT_REFRESH_TOKEN, NGROK_URL  (TikTok)
"""

import sys
import os
import threading
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


PLATFORMS = [
    ("Instagram Reels", upload_reel),
    ("YouTube Shorts", upload_short),
    ("TikTok", upload_tiktok),
]


def upload_one_video(filepath):
    """Upload one video to every platform in parallel, collecting results."""
    results = {}
    lock = threading.Lock()

    # Check ngrok availability for Instagram
    ngrok_up = _is_ngrok_up()

    def _upload(name, upload_fn):
        try:
            print(f"  ↗ {name}: uploading…")
            upload_fn(filepath)
            with lock:
                results[name] = (True, None)
            print(f"  ✔ {name}: done")
        except SystemExit:
            with lock:
                results[name] = (False, "upload exited with error")
            print(f"  ✘ {name}: upload exited with error")
        except Exception as exc:
            with lock:
                results[name] = (False, str(exc))
            print(f"  ✘ {name}: {exc}")

    threads = []
    for name, upload_fn in PLATFORMS:
        if name == "Instagram Reels" and not ngrok_up:
            print(f"  ⚠ Skipping {name} — ngrok is not reachable")
            with lock:
                results[name] = (False, "ngrok not reachable")
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
        sys.exit(1)
    else:
        print("  All uploads succeeded!")


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
    upload_one_video(filepath)
