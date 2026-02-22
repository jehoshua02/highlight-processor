# Architecture Quirks

1. **Services as CLI wrappers, not daemons.** Most Docker Compose services (`crop`, `scrub_voices`, `process`, `process_all`, `normalize`) are one-shot `docker compose run` commands rather than long-running services. This is an unconventional use of Compose — it's essentially a task runner, not an orchestrator. Tools like `make` or a shell script are more typical for this pattern.

3. **Two separate Dockerfiles for nearly the same base.** `Dockerfile` installs the full ML/video stack while `Dockerfile.webhook` is a minimal Flask image. This is a reasonable optimization, but the webhook service doesn't set `image:`, so it rebuilds from scratch every time. Meanwhile the processing services never rebuild because they rely on a named image.

4. **ngrok tunnels to nginx, which reverse-proxies back to the webhook.** The request path for webhook verification is: Internet → ngrok → nginx (file-server) → Flask (webhook). Adding nginx in the middle is only needed because it also serves static video files, but it creates an extra hop and a coupling (`depends_on: webhook`). A simpler setup could have ngrok route `/webhook/` directly.

5. **No health checks or restart policies on the long-running services.** The `ngrok` service has `restart: unless-stopped`, but `file-server` and `webhook` don't — if either crashes, the upload flow breaks silently.

6. **`normalize_audio.py` exists but isn't mentioned in the pipeline.** The documented pipeline is crop → scrub → upload, and `process_one_video.py` orchestrates crop → scrub. But there's a `normalize` service and `src/normalize_audio.py` that aren't referenced in the documented flow — possibly a later addition that hasn't been integrated into the orchestrator.
