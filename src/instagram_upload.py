"""instagram_upload.py
Upload a processed video to Instagram Reels via the Graph API.

The video must be publicly accessible — we use the ngrok file-server URL
that is already configured in docker-compose.

Caption is derived automatically from the video filename.

Usage:
    python instagram_upload.py /videos/clip_final.mp4

Required environment variables:
    IG_USER_ID          Instagram / Facebook Page-backed IG user ID
    IG_ACCESS_TOKEN     Long-lived access token with publish permissions
    NGROK_URL           Base ngrok URL (e.g. https://brief-presently-snipe.ngrok-free.app)
"""

import sys
import os
import json
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote
from urllib.error import HTTPError

GRAPH_API = "https://graph.instagram.com/v21.0"
POLL_INTERVAL = 30       # seconds between status checks
POLL_TIMEOUT = 600       # give up after 10 minutes
MAX_RATE_LIMIT_RETRIES = 5  # retry this many times on rate-limit errors


def _require_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"Error: environment variable {name} is not set.")
        sys.exit(1)
    return value


def _api(method, url, params=None):
    """Make a Graph API request and return parsed JSON."""
    if params:
        data = urlencode(params).encode()
    else:
        data = None

    req = Request(url, data=data, method=method)
    try:
        with urlopen(req) as resp:
            return json.loads(resp.read())
    except HTTPError as exc:
        body = exc.read().decode()
        print(f"API error {exc.code}: {body}")
        sys.exit(1)


def validate_file(filepath):
    """Ensure the file exists and has the _final suffix."""
    if not os.path.isfile(filepath):
        print(f"Error: file not found: {filepath}")
        sys.exit(1)

    name = os.path.splitext(os.path.basename(filepath))[0]
    if not name.endswith("_final"):
        print(f"Error: only processed videos (ending with _final) can be uploaded.")
        print(f"       Got: {os.path.basename(filepath)}")
        sys.exit(1)


def build_video_url(filepath, ngrok_base):
    """Build the public ngrok URL for the given video file."""
    filename = os.path.basename(filepath)
    encoded = quote(filename)
    return f"{ngrok_base.rstrip('/')}/{encoded}"


def _preflight_check(video_url):
    """Verify the video URL is reachable and returns video content."""
    req = Request(video_url, method="HEAD")
    req.add_header("ngrok-skip-browser-warning", "true")
    try:
        with urlopen(req) as resp:
            ct = resp.headers.get("Content-Type", "")
            cl = resp.headers.get("Content-Length", "?")
            print(f"  Pre-flight OK: {ct}, {int(cl)/(1024*1024):.1f} MB")
            if "video" not in ct and "octet-stream" not in ct:
                print(f"  Warning: unexpected Content-Type '{ct}' — Instagram may reject this.")
    except HTTPError as exc:
        print(f"  Pre-flight FAILED ({exc.code}) — Instagram won't be able to fetch the video.")
        print(f"  Check that ngrok + file-server are running and the URL is correct.")
        sys.exit(1)
    except Exception as exc:
        print(f"  Pre-flight FAILED: {exc}")
        sys.exit(1)


def create_container(user_id, token, video_url, caption=None):
    """Step 1: Create a media container for the Reel."""
    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "access_token": token,
    }
    if caption:
        params["caption"] = caption

    url = f"{GRAPH_API}/{user_id}/media"
    print(f"Creating media container …")
    result = _api("POST", url, params)
    container_id = result.get("id")
    if not container_id:
        print(f"Unexpected response: {result}")
        sys.exit(1)
    print(f"  Container ID: {container_id}")
    return container_id


def wait_for_container(container_id, token):
    """Step 2: Poll until the container is ready (status FINISHED)."""
    url = f"{GRAPH_API}/{container_id}"
    params = urlencode({"fields": "status_code,status", "access_token": token})
    poll_url = f"{url}?{params}"

    start = time.time()
    rate_limit_retries = 0
    while True:
        elapsed = time.time() - start
        if elapsed > POLL_TIMEOUT:
            print(f"Timed out after {POLL_TIMEOUT}s waiting for container to finish.")
            sys.exit(1)

        req = Request(poll_url, method="GET")
        try:
            with urlopen(req) as resp:
                data = json.loads(resp.read())
        except HTTPError as exc:
            body = exc.read().decode()
            # Retry on rate-limit errors with exponential backoff
            if exc.code in (403, 429) and "rate" in body.lower():
                rate_limit_retries += 1
                if rate_limit_retries > MAX_RATE_LIMIT_RETRIES:
                    print(f"Rate-limited {rate_limit_retries} times — giving up.")
                    sys.exit(1)
                backoff = 60 * rate_limit_retries  # 60s, 120s, 180s, ...
                print(f"  Rate-limited — waiting {backoff}s before retry ({rate_limit_retries}/{MAX_RATE_LIMIT_RETRIES})")
                time.sleep(backoff)
                continue
            print(f"Poll error {exc.code}: {body}")
            sys.exit(1)

        rate_limit_retries = 0  # reset on success
        status = data.get("status_code", "UNKNOWN")
        print(f"  Status: {status}  ({int(elapsed)}s elapsed)")

        if status == "FINISHED":
            return
        if status == "ERROR":
            print(f"  Container processing failed: {data}")
            sys.exit(1)

        time.sleep(POLL_INTERVAL)


def publish(user_id, token, container_id):
    """Step 3: Publish the container as a Reel."""
    url = f"{GRAPH_API}/{user_id}/media_publish"
    params = {
        "creation_id": container_id,
        "access_token": token,
    }
    print("Publishing reel …")
    result = _api("POST", url, params)
    media_id = result.get("id")
    if not media_id:
        print(f"Unexpected response: {result}")
        sys.exit(1)
    print(f"  Published!  Media ID: {media_id}")
    return media_id


def _caption_from_filename(filepath):
    """Derive a caption from the video filename."""
    base = os.path.splitext(os.path.basename(filepath))[0]
    for suffix in ("_final", "_novocals", "_cropped_9_16", "_processing"):
        base = base.replace(suffix, "")
    name = base.replace("_", " ").strip().title()
    return f"{name}\n\n#Reels #Gaming #Highlights"


def upload_reel(filepath):
    """Full upload flow: validate → create container → poll → publish."""
    validate_file(filepath)

    user_id = _require_env("IG_USER_ID")
    token = _require_env("IG_ACCESS_TOKEN")
    ngrok_base = _require_env("NGROK_URL")

    caption = _caption_from_filename(filepath)
    print(f"Caption: {caption}")

    video_url = build_video_url(filepath, ngrok_base)
    print(f"Video URL: {video_url}")
    _preflight_check(video_url)
    print()

    container_id = create_container(user_id, token, video_url, caption)
    wait_for_container(container_id, token)
    media_id = publish(user_id, token, container_id)
    return media_id


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "--help":
        print("Usage: python instagram_upload.py <video_path>")
        print()
        print("  Uploads a _final video to Instagram Reels.")
        print("  Caption is derived from the filename.")
        print("  The video must be served via the ngrok file-server.")
        print()
        print("Docker usage:")
        print('  docker compose run --rm instagram_upload "/videos/clip_final.mp4"')
        sys.exit(0 if sys.argv[-1] == "--help" else 1)

    filepath = sys.argv[1]
    upload_reel(filepath)
