"""
youtube_auth.py

Standalone script for YouTube OAuth2 flow to obtain a refresh token.

Usage:
    python youtube_auth.py
    # Or via Docker:
    docker compose run --rm -p 8080:8080 youtube_auth

Environment variables required:
    YT_CLIENT_ID, YT_CLIENT_SECRET
"""

import sys
import os
import http.server
import webbrowser
import json
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.error import HTTPError

TOKEN_URI = "https://oauth2.googleapis.com/token"
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
SCOPE = "https://www.googleapis.com/auth/youtube"
REDIRECT_URI = "http://localhost:8080"


def _require_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"Error: environment variable {name} is not set.")
        sys.exit(1)
    return value

def authenticate():
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
    authenticate()
