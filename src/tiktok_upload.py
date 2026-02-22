"""tiktok_upload.py
Upload a processed video to TikTok via the Content Posting API v2.

Uses only urllib (no third-party SDK) to keep dependencies minimal.
Title is derived automatically from the video filename.

Usage:
    python tiktok_upload.py <video_path>
    python tiktok_upload.py --auth

Required environment variables (upload):
    TT_CLIENT_KEY       TikTok app client key
    TT_CLIENT_SECRET    TikTok app client secret
    TT_ACCESS_TOKEN     Access token (obtain/refresh via --auth)
    TT_REFRESH_TOKEN    Refresh token (obtain via --auth)

Required environment variables (--auth):
    TT_CLIENT_KEY       TikTok app client key
    TT_CLIENT_SECRET    TikTok app client secret
"""

import sys
import os
import json
import math
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.error import HTTPError

TOKEN_URI = "https://open.tiktokapis.com/v2/oauth/token/"
AUTH_URI = "https://www.tiktok.com/v2/auth/authorize/"
INIT_URI = "https://open.tiktokapis.com/v2/post/publish/video/init/"
STATUS_URI = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
SCOPE = "video.publish,video.upload"
CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB
POLL_INTERVAL = 5              # seconds between status checks
POLL_TIMEOUT = 300             # give up after 5 minutes


def _require_env(name):
    """Return the value of an environment variable or exit."""
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"Error: environment variable {name} is not set.")
        sys.exit(1)
    return value


def validate_file(filepath):
    """Ensure the file exists and has the _final suffix."""
    if not os.path.isfile(filepath):
        print(f"Error: file not found: {filepath}")
        sys.exit(1)

    name = os.path.splitext(os.path.basename(filepath))[0]
    if not name.endswith("_final"):
        print("Error: only processed videos (ending with _final) can be uploaded.")
        print(f"       Got: {os.path.basename(filepath)}")
        sys.exit(1)


def _refresh_access_token(client_key, client_secret, refresh_token):
    """Exchange a refresh token for a fresh access token."""
    data = urlencode({
        "client_key": client_key,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }).encode()

    req = Request(TOKEN_URI, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urlopen(req) as resp:
            result = json.loads(resp.read())
    except HTTPError as exc:
        body = exc.read().decode()
        print(f"Token refresh failed ({exc.code}): {body}")
        sys.exit(1)

    token = result.get("access_token")
    if not token:
        print(f"No access_token in response: {result}")
        sys.exit(1)

    new_refresh = result.get("refresh_token")
    if new_refresh and new_refresh != refresh_token:
        print(f"  New refresh token issued — update your .env:")
        print(f"  TT_REFRESH_TOKEN={new_refresh}")
        print()

    return token


def _init_upload(access_token, title, filepath):
    """Initialize a direct-post file upload and return (publish_id, upload_url)."""
    file_size = os.path.getsize(filepath)

    payload = {
        "post_info": {
            "title": title,
            "privacy_level": "SELF_ONLY",
            "disable_duet": False,
            "disable_stitch": False,
            "disable_comment": False,
            "video_cover_timestamp_ms": 1000,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": file_size,
            "total_chunk_count": 1,
        },
    }

    print(f"  video_size={file_size}")
    body = json.dumps(payload).encode()

    req = Request(INIT_URI, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Type", "application/json; charset=UTF-8")

    try:
        with urlopen(req) as resp:
            result = json.loads(resp.read())
    except HTTPError as exc:
        body_text = exc.read().decode()
        print(f"Failed to init upload ({exc.code}): {body_text}")
        sys.exit(1)

    error = result.get("error", {})
    if error.get("code") != "ok":
        print(f"Init upload error: {error}")
        sys.exit(1)

    data = result.get("data", {})
    publish_id = data.get("publish_id")
    upload_url = data.get("upload_url")

    if not publish_id or not upload_url:
        print(f"Unexpected init response: {result}")
        sys.exit(1)

    print(f"  Publish ID: {publish_id}")
    return publish_id, upload_url


def _upload_file(upload_url, filepath):
    """Upload the video file in chunks to TikTok's upload URL."""
    file_size = os.path.getsize(filepath)
    print(f"Uploading {file_size / (1024*1024):.1f} MB …")

    with open(filepath, "rb") as f:
        data = f.read()

    req = Request(upload_url, data=data, method="PUT")
    req.add_header("Content-Type", "video/mp4")
    req.add_header("Content-Length", str(file_size))
    req.add_header("Content-Range", f"bytes 0-{file_size - 1}/{file_size}")

    try:
        with urlopen(req) as resp:
            pass
    except HTTPError as exc:
        body_text = exc.read().decode()
        print(f"Upload failed ({exc.code}): {body_text}")
        sys.exit(1)

    print("  Upload complete!")


def _poll_status(access_token, publish_id):
    """Poll publish status until complete or failed."""
    print("Waiting for TikTok to process the video …")

    body = json.dumps({"publish_id": publish_id}).encode()
    start = time.time()

    while True:
        elapsed = time.time() - start
        if elapsed > POLL_TIMEOUT:
            print(f"Timed out after {POLL_TIMEOUT}s waiting for publish to complete.")
            sys.exit(1)

        req = Request(STATUS_URI, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {access_token}")
        req.add_header("Content-Type", "application/json; charset=UTF-8")

        try:
            with urlopen(req) as resp:
                result = json.loads(resp.read())
        except HTTPError as exc:
            body_text = exc.read().decode()
            print(f"Status poll error ({exc.code}): {body_text}")
            sys.exit(1)

        status = result.get("data", {}).get("status", "UNKNOWN")
        print(f"  Status: {status}  ({int(elapsed)}s elapsed)")

        if status == "PUBLISH_COMPLETE":
            print("  Published successfully!")
            return
        if status == "FAILED":
            fail_reason = result.get("data", {}).get("fail_reason", "unknown")
            print(f"  Publish failed: {fail_reason}")
            sys.exit(1)

        time.sleep(POLL_INTERVAL)


def _title_from_filename(filepath):
    """Derive a caption/title from the video filename (max 150 chars)."""
    base = os.path.splitext(os.path.basename(filepath))[0]
    for suffix in ("_final", "_novocals", "_cropped_9_16", "_processing"):
        base = base.replace(suffix, "")
    name = base.replace("_", " ").strip().title()
    title = f"{name} #Gaming #Highlights"
    return title[:150]


def upload_tiktok(filepath):
    """Full upload flow: validate → get token → init → upload → poll."""
    validate_file(filepath)

    client_key = _require_env("TT_CLIENT_KEY")
    client_secret = _require_env("TT_CLIENT_SECRET")
    refresh_token = _require_env("TT_REFRESH_TOKEN")

    title = _title_from_filename(filepath)
    print(f"Title: {title}")
    print()

    print("Refreshing access token …")
    access_token = _refresh_access_token(client_key, client_secret, refresh_token)
    print("  Token OK")
    print()

    print("Initializing upload …")
    publish_id, upload_url = _init_upload(access_token, title, filepath)
    print()

    _upload_file(upload_url, filepath)
    print()

    _poll_status(access_token, publish_id)


def authenticate():
    """One-time OAuth flow to obtain access and refresh tokens.

    Starts a tiny HTTP server on port 8080, prints a URL for the user
    to visit, and exchanges the authorization code for tokens.
    """
    client_key = _require_env("TT_CLIENT_KEY")
    client_secret = _require_env("TT_CLIENT_SECRET")
    ngrok_url = _require_env("NGROK_URL")
    redirect_uri = f"{ngrok_url.rstrip('/')}/tiktok/auth/"

    auth_params = urlencode({
        "client_key": client_key,
        "scope": SCOPE,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": "tiktok_auth",
    })
    auth_url = f"{AUTH_URI}?{auth_params}"

    print("1. Open this URL in your browser:\n")
    print(f"  {auth_url}\n")
    print("2. Authorize the app.")
    print("3. You'll be redirected — copy the FULL URL from your browser's address bar.")
    print("4. Paste it here:\n")

    redirect_input = input("  Redirect URL: ").strip()
    if not redirect_input:
        print("Error: no URL provided.")
        sys.exit(1)

    qs = parse_qs(urlparse(redirect_input).query)
    auth_code = qs.get("code", [None])[0]

    if not auth_code:
        print("Error: no authorization code found in the URL.")
        sys.exit(1)

    print(f"\n  Code received ({len(auth_code)} chars)")
    print()

    # Exchange code for tokens
    token_params = {
        "client_key": client_key,
        "client_secret": client_secret,
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    data = urlencode(token_params).encode()

    req = Request(TOKEN_URI, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urlopen(req) as resp:
            result = json.loads(resp.read())
    except HTTPError as exc:
        body_text = exc.read().decode()
        print(f"Token exchange failed ({exc.code}): {body_text}")
        sys.exit(1)

    access = result.get("access_token")
    refresh = result.get("refresh_token")

    if not access or not refresh:
        print(f"Missing tokens in response: {result}")
        sys.exit(1)

    print()
    print("Authentication successful!")
    print()
    print("Add these to your .env file:")
    print(f"  TT_ACCESS_TOKEN={access}")
    print(f"  TT_REFRESH_TOKEN={refresh}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "--help":
        print("Usage: python tiktok_upload.py <video_path>")
        print("       python tiktok_upload.py --auth")
        print()
        print("  Uploads a _final video to TikTok.")
        print("  Title is derived from the filename.")
        print()
        print("  --auth    Run one-time OAuth flow to get tokens.")
        print("            Starts a local server on port 8080.")
        print()
        print("Docker usage:")
        print('  docker compose run --rm tiktok_upload "/videos/clip_final.mp4"')
        print('  docker compose run --rm -p 8080:8080 tiktok_upload --auth')
        sys.exit(0 if sys.argv[-1] == "--help" else 1)

    if sys.argv[1] == "--auth":
        authenticate()
    else:
        filepath = sys.argv[1]
        upload_tiktok(filepath)
