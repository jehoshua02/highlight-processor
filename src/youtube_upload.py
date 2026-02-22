"""youtube_upload.py
Upload a processed video to YouTube Shorts via the YouTube Data API v3.

Uses only urllib (no google-api-python-client) to keep dependencies minimal.
Shorts are regular YouTube uploads with vertical video (9:16).
The pipeline already crops to 9:16, so any _final video is Shorts-ready.

Usage:
    python youtube_upload.py <video_path> ["title"] ["description"]
    python youtube_upload.py --auth

Required environment variables (upload):
    YT_CLIENT_ID        OAuth2 client ID from Google Cloud Console
    YT_CLIENT_SECRET    OAuth2 client secret
    YT_REFRESH_TOKEN    Refresh token (obtain via --auth)

Required environment variables (--auth):
    YT_CLIENT_ID        OAuth2 client ID
    YT_CLIENT_SECRET    OAuth2 client secret
"""

import sys
import os
import json
import http.server
import webbrowser
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.error import HTTPError

TOKEN_URI = "https://oauth2.googleapis.com/token"
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
UPLOAD_URI = "https://www.googleapis.com/upload/youtube/v3/videos"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"
REDIRECT_URI = "http://localhost:8080"
CATEGORY_GAMING = "20"
CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB


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


def _get_access_token(client_id, client_secret, refresh_token):
    """Exchange a refresh token for a short-lived access token."""
    data = urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()

    req = Request(TOKEN_URI, data=data, method="POST")
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
    return token


def _init_resumable_upload(access_token, title, description, category, privacy):
    """Start a resumable upload session and return the upload URL."""
    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["Shorts", "gaming", "highlights"],
            "categoryId": category,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    body = json.dumps(metadata).encode()

    params = urlencode({"uploadType": "resumable", "part": "snippet,status"})
    url = f"{UPLOAD_URI}?{params}"

    req = Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Type", "application/json; charset=UTF-8")

    try:
        with urlopen(req) as resp:
            upload_url = resp.headers["Location"]
    except HTTPError as exc:
        body_text = exc.read().decode()
        print(f"Failed to init upload ({exc.code}): {body_text}")
        sys.exit(1)

    return upload_url


def _upload_file(upload_url, filepath):
    """Upload the video file in chunks and return the video ID."""
    file_size = os.path.getsize(filepath)
    print(f"Uploading {file_size / (1024*1024):.1f} MB …")

    with open(filepath, "rb") as f:
        offset = 0
        while offset < file_size:
            chunk = f.read(CHUNK_SIZE)
            end = offset + len(chunk) - 1

            req = Request(upload_url, data=chunk, method="PUT")
            req.add_header("Content-Type", "video/mp4")
            req.add_header("Content-Length", str(len(chunk)))
            req.add_header("Content-Range", f"bytes {offset}-{end}/{file_size}")

            try:
                with urlopen(req) as resp:
                    # Final chunk returns 200/201 with video metadata
                    result = json.loads(resp.read())
                    video_id = result["id"]
                    print(f"  Upload complete!  Video ID: {video_id}")
                    print(f"  https://youtube.com/shorts/{video_id}")
                    return video_id
            except HTTPError as exc:
                if exc.code == 308:
                    # 308 Resume Incomplete — keep going
                    pct = int((end + 1) / file_size * 100)
                    print(f"  {pct}% uploaded")
                    offset = end + 1
                else:
                    body_text = exc.read().decode()
                    print(f"Upload failed ({exc.code}): {body_text}")
                    sys.exit(1)

    print("Error: upload finished without a response from YouTube.")
    sys.exit(1)


def upload_short(filepath, title=None, description=None):
    """Full upload flow: validate → get token → init upload → send file."""
    validate_file(filepath)

    client_id = _require_env("YT_CLIENT_ID")
    client_secret = _require_env("YT_CLIENT_SECRET")
    refresh_token = _require_env("YT_REFRESH_TOKEN")

    if not title:
        base = os.path.splitext(os.path.basename(filepath))[0]
        base = base.replace("_final", "").replace("_", " ").strip()
        title = f"{base} #Shorts"
    elif "#shorts" not in title.lower():
        title = f"{title} #Shorts"

    if not description:
        description = ""

    print(f"Title:       {title}")
    print(f"Description: {description or '(none)'}")
    print()

    access_token = _get_access_token(client_id, client_secret, refresh_token)
    upload_url = _init_resumable_upload(
        access_token, title, description, CATEGORY_GAMING, "public"
    )
    return _upload_file(upload_url, filepath)


def authenticate():
    """One-time OAuth flow to obtain a refresh token.

    Starts a tiny HTTP server on port 8080, prints a URL for the user
    to visit, and exchanges the authorization code for tokens.
    """
    client_id = _require_env("YT_CLIENT_ID")
    client_secret = _require_env("YT_CLIENT_SECRET")

    auth_params = urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    })
    auth_url = f"{AUTH_URI}?{auth_params}"

    print("Open this URL in your browser:\n")
    print(f"  {auth_url}\n")

    # Tiny server to catch the redirect with the auth code
    auth_code = None

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            qs = parse_qs(urlparse(self.path).query)
            auth_code = qs.get("code", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization received. You can close this tab.</h1>")

        def log_message(self, *args):
            pass  # suppress request logs

    server = http.server.HTTPServer(("0.0.0.0", 8080), Handler)
    print("Waiting for authorization …")
    server.handle_request()
    server.server_close()

    if not auth_code:
        print("Error: no authorization code received.")
        sys.exit(1)

    # Exchange code for tokens
    data = urlencode({
        "code": auth_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()

    req = Request(TOKEN_URI, data=data, method="POST")
    try:
        with urlopen(req) as resp:
            result = json.loads(resp.read())
    except HTTPError as exc:
        body = exc.read().decode()
        print(f"Token exchange failed ({exc.code}): {body}")
        sys.exit(1)

    refresh = result.get("refresh_token")
    if not refresh:
        print(f"No refresh_token in response: {result}")
        sys.exit(1)

    print()
    print("Authentication successful!")
    print()
    print("Add this to your .env file:")
    print(f"  YT_REFRESH_TOKEN={refresh}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "--help":
        print("Usage: python youtube_upload.py <video_path> [title] [description]")
        print("       python youtube_upload.py --auth")
        print()
        print("  Uploads a _final video to YouTube Shorts.")
        print()
        print("  --auth    Run one-time OAuth flow to get a refresh token.")
        print("            Starts a local server on port 8080.")
        print()
        print("Docker usage:")
        print('  docker compose run --rm youtube_upload "/videos/clip_final.mp4" "My Title"')
        print('  docker compose run --rm -p 8080:8080 youtube_upload --auth')
        sys.exit(0 if sys.argv[-1] == "--help" else 1)

    if sys.argv[1] == "--auth":
        authenticate()
    else:
        filepath = sys.argv[1]
        title = sys.argv[2] if len(sys.argv) >= 3 else None
        description = sys.argv[3] if len(sys.argv) >= 4 else None
        upload_short(filepath, title, description)
