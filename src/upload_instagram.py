"""
upload_instagram.py
Upload a video as an Instagram Reel.

Usage:
    python upload_instagram.py video.mp4 "Caption text" [cover.jpg]

Requires:
    pip install instagrapi

Environment variables:
    IG_USERNAME  - Instagram username
    IG_PASSWORD  - Instagram password
    IG_PROXY     - (optional) HTTP/SOCKS proxy, e.g. http://user:pass@host:port
"""
import sys
import os
import time
from pathlib import Path
from instagrapi import Client

SESSION_FILE = Path(__file__).parent.parent / ".ig_session.json"


def upload_reel(video_path, caption="", cover_path=None):
    """Upload a video as an Instagram Reel.

    Args:
        video_path: Path to the mp4 file.
        caption: Post caption / description.
        cover_path: Optional path to a cover image (jpg).

    Returns:
        The media object returned by the Instagram API.
    """
    username = os.environ.get("IG_USERNAME")
    password = os.environ.get("IG_PASSWORD")
    proxy = os.environ.get("IG_PROXY")

    if not username or not password:
        raise EnvironmentError(
            "Set IG_USERNAME and IG_PASSWORD environment variables."
        )

    cl = Client()

    # Use proxy if provided (avoids IP blacklisting in containers)
    if proxy:
        cl.set_proxy(proxy)

    # Add a small delay between API requests to look more human
    cl.delay_range = [1, 3]

    # Reuse saved session if available to avoid repeated logins
    if SESSION_FILE.exists():
        cl.load_settings(SESSION_FILE)
        cl.login(username, password)
    else:
        cl.login(username, password)
    cl.dump_settings(SESSION_FILE)

    kwargs = {"path": video_path, "caption": caption}
    if cover_path:
        kwargs["thumbnail"] = cover_path

    media = cl.clip_upload(**kwargs)
    print(f"Uploaded reel: https://www.instagram.com/reel/{media.code}/")
    return media


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "--help":
        print("Usage: python upload_instagram.py video.mp4 \"Caption\" [cover.jpg]")
        print()
        print("  Uploads a video as an Instagram Reel.")
        print()
        print("Environment variables:")
        print("  IG_USERNAME  - Instagram username")
        print("  IG_PASSWORD  - Instagram password")
        print("  IG_PROXY     - (optional) proxy, e.g. http://user:pass@host:port")
        print("  IG_PROXY     - (optional) proxy, e.g. http://user:pass@host:port")
        print()
        print("Docker usage:")
        print("  docker compose run --rm upload /videos/myclip.mp4 \"My caption\"")
        sys.exit(0 if sys.argv[1] == "--help" else 1)

    video_path = sys.argv[1]
    caption = sys.argv[2] if len(sys.argv) >= 3 else ""
    cover_path = sys.argv[3] if len(sys.argv) >= 4 else None
    upload_reel(video_path, caption, cover_path)
