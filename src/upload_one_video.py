"""upload_one_video.py
Upload a single video to all platforms: Instagram Reels, YouTube Shorts,
and TikTok.

Runs each upload sequentially and reports results at the end.
A single platform failure does not prevent the others from running.

Usage:
    python upload_one_video.py <video_path>

Required environment variables:
    IG_USER_ID, IG_ACCESS_TOKEN, NGROK_URL        (Instagram)
    YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN  (YouTube)
    TT_CLIENT_KEY, TT_CLIENT_SECRET, TT_ACCESS_TOKEN, TT_REFRESH_TOKEN, NGROK_URL  (TikTok)
"""

import sys
import os

from instagram_upload import upload_reel
from youtube_upload import upload_short
from tiktok_upload import upload_tiktok

PLATFORMS = [
    ("Instagram Reels", upload_reel),
    ("YouTube Shorts", upload_short),
    ("TikTok", upload_tiktok),
]


def upload_one_video(filepath):
    """Upload one video to every platform, collecting results."""
    results = []

    for name, upload_fn in PLATFORMS:
        print("=" * 60)
        print(f"  Uploading to {name}")
        print("=" * 60)
        print()
        try:
            upload_fn(filepath)
            results.append((name, True, None))
        except SystemExit:
            results.append((name, False, "upload exited with error"))
        except Exception as exc:
            results.append((name, False, str(exc)))
        print()

    # Summary
    print("=" * 60)
    print("  Upload Summary")
    print("=" * 60)
    failed = 0
    for name, ok, err in results:
        if ok:
            print(f"  {name}: OK")
        else:
            print(f"  {name}: FAILED — {err}")
            failed += 1
    print()

    if failed:
        print(f"{failed} of {len(results)} uploads failed.")
        sys.exit(1)
    else:
        print("All uploads succeeded!")


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
