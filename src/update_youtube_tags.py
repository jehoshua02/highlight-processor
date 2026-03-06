"""
update_youtube_tags.py

Update tags for a YouTube video using the YouTube Data API v3.
Requires OAuth2 credentials and a refresh token (see youtube_upload.py for setup).

Usage:
    python update_youtube_tags.py <video_id> <tag1,tag2,tag3,...>
    # Or via Docker:
    docker compose run --rm youtube_update_tags <video_id> <tag1,tag2,tag3,...>

Environment variables required:
    YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
"""


import os
import sys
import json
import http.client
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
import json

from config_helper import config

def get_access_token():
    client_id = os.environ.get('YT_CLIENT_ID')
    client_secret = os.environ.get('YT_CLIENT_SECRET')
    refresh_token = os.environ.get('YT_REFRESH_TOKEN')
    if not all([client_id, client_secret, refresh_token]):
        print("Missing YT_CLIENT_ID, YT_CLIENT_SECRET, or YT_REFRESH_TOKEN in environment.")
        sys.exit(1)
    data = urlencode({
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
    }).encode()
    req = Request('https://oauth2.googleapis.com/token', data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urlopen(req) as resp:
            result = json.loads(resp.read())
    except HTTPError as exc:
        body = exc.read().decode()
        print(f"Failed to get access token: {body}")
        sys.exit(1)
    return result['access_token']

def update_video_tags(video_id, tags, access_token):
    # Get current video metadata
    get_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}"
    req = Request(get_url, method="GET")
    req.add_header("Authorization", f"Bearer {access_token}")
    try:
        with urlopen(req) as resp:
            result = json.loads(resp.read())
    except HTTPError as exc:
        body = exc.read().decode()
        print(f"Failed to fetch video metadata: {body}")
        sys.exit(1)
    items = result.get('items')
    if not items:
        print("Video not found.")
        sys.exit(1)
    snippet = items[0]['snippet']
    snippet['tags'] = tags
    # Update video
    update_url = "https://www.googleapis.com/youtube/v3/videos?part=snippet"
    body = json.dumps({
        "id": video_id,
        "snippet": snippet
    }).encode()
    req2 = Request(update_url, data=body, method="PUT")
    req2.add_header("Authorization", f"Bearer {access_token}")
    req2.add_header("Content-Type", "application/json")
    try:
        with urlopen(req2) as resp:
            resp.read()  # ignore body
    except HTTPError as exc:
        body = exc.read().decode()
        print(f"Failed to update tags: {body}")
        sys.exit(1)
    print(f"Tags updated for video {video_id}: {tags}")


def load_tags_from_config():
    tags_str = config('tags.youtube', '')
    # Accepts either comma or space separated, strips #
    tags = [t.lstrip('#').strip() for t in tags_str.replace(',', ' ').split() if t.strip()]
    return tags

def main():
    if len(sys.argv) < 2:
        print("Usage: python update_youtube_tags.py <video_id> [tag1,tag2,...]")
        sys.exit(1)
    video_id = sys.argv[1]
    if len(sys.argv) >= 3:
        tags = [t.strip() for t in sys.argv[2].replace(',', ' ').split() if t.strip()]
    else:
        tags = load_tags_from_config()
    if not tags:
        print("No tags provided and none found in config.json.")
        sys.exit(1)
    access_token = get_access_token()
    update_video_tags(video_id, tags, access_token)

if __name__ == "__main__":
    main()
