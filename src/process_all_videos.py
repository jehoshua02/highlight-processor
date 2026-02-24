"""process_all_videos.py
Find all unprocessed videos in a folder and run the full pipeline on each.

Skips files whose names end with known output suffixes so re-running is
safe (idempotent).  Videos are processed in parallel; each worker's output
is printed line-by-line with a [filename] prefix.

Usage:
    python process_all_videos.py /videos
"""
import sys
import os
import subprocess
import threading
import time

KNOWN_SUFFIXES = (
    "_final", "_cropped", "_cropped_9_16", "_novocals",
)
IN_PROGRESS_SUFFIXES = (
    "_cropping", "_scrubbing", "_normalizing",
)
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm")


def is_already_processed(filepath):
    """Return True if the filename ends with a known output or in-progress suffix."""
    name = os.path.splitext(os.path.basename(filepath))[0]
    return any(name.endswith(suffix)
               for suffix in KNOWN_SUFFIXES + IN_PROGRESS_SUFFIXES)


def clean_stale_files(folder):
    """Delete orphaned in-progress files left by a crashed run.

    Files ending with _cropping, _scrubbing, or _normalizing represent
    interrupted writes and are not reusable.  Removing them lets the
    next run fall through to a clean retry of that step.
    """
    for entry in os.listdir(folder):
        name = os.path.splitext(entry)[0]
        if any(name.endswith(s) for s in IN_PROGRESS_SUFFIXES):
            full = os.path.join(folder, entry)
            if os.path.isfile(full):
                print(f"  Cleaning stale file: {entry}")
                os.remove(full)


def find_unprocessed_videos(folder):
    """Return a sorted list of source videos in *folder* that need work.

    Skips derivative files (_cropped, _novocals, _final, etc.) since they
    are not source videos.  Source files with existing checkpoints are
    included — process_one_video handles resume logic.
    """
    videos = []
    for entry in os.listdir(folder):
        full = os.path.join(folder, entry)
        if not os.path.isfile(full):
            continue
        name, ext = os.path.splitext(entry)
        if ext.lower() not in VIDEO_EXTENSIONS:
            continue
        if is_already_processed(full):
            continue
        checkpoints = [suffix for suffix in ("_cropped", "_novocals", "_final")
                       if os.path.exists(os.path.join(folder, f"{name}{suffix}{ext}"))]
        if checkpoints:
            found = ", ".join(f"{name}{s}{ext}" for s in checkpoints)
            print(f"  Resuming {entry} (found: {found})")
        videos.append(full)
    videos.sort()
    return videos


# Lock so parallel workers don't interleave partial lines
_print_lock = threading.Lock()


def _log(prefix, line):
    """Thread-safe print with a [filename] prefix."""
    with _print_lock:
        print(f" [{prefix}] {line}")


def run_one(video_path, name, no_upload=False, skip_tt=False, keep_voice=False):
    """Run process_one_video as a subprocess, printing prefixed output."""
    cmd = [sys.executable, "-u", "src/process_one_video.py"]
    if no_upload:
        cmd.append("--no-upload")
    if skip_tt:
        cmd.append("--skip-upload-tt")
    if keep_voice:
        cmd.append("--voice")
    cmd.append(video_path)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    logs = []
    for line in proc.stdout:
        stripped = line.strip()
        if not stripped:
            continue
        logs.append(stripped)
        _log(name, stripped)

    proc.wait()

    if proc.returncode == 0:
        base, ext = os.path.splitext(video_path)
        final = os.path.basename(f"{base}_final{ext}")
        return video_path, True, final, logs
    else:
        return video_path, False, f"exited with code {proc.returncode}", logs


def main():
    flags = {"--no-upload", "--skip-upload-tt", "--voice"}
    args = [a for a in sys.argv[1:]
            if a not in flags and not a.startswith("--limit=")]
    no_upload = "--no-upload" in sys.argv
    skip_tt = "--skip-upload-tt" in sys.argv
    keep_voice = "--voice" in sys.argv

    limit = None
    for a in sys.argv[1:]:
        if a.startswith("--limit="):
            try:
                limit = int(a.split("=", 1)[1])
            except ValueError:
                print(f"Error: invalid --limit value: {a}")
                sys.exit(1)

    if len(args) != 1 or sys.argv[1] == "--help":
        print("Usage: python process_all_videos.py [--no-upload] [--skip-upload-tt] [--voice] [--limit=N] <folder>")
        print()
        print("  Processes every video in <folder> that hasn't already")
        print("  been processed (crop 9:16 + scrub voices + normalize).")
        print()
        print("  --no-upload        Skip uploading after processing.")
        print("  --skip-upload-tt   Skip TikTok upload.")
        print("  --voice            Keep original audio (skip voice scrubbing).")
        print("  --limit=N          Process at most N videos.")
        print()
        print("Docker usage:")
        print("  docker compose run --rm process_all /videos")
        print("  docker compose run --rm process_all --no-upload /videos")
        sys.exit(0 if sys.argv[-1] == "--help" else 1)

    folder = args[0]
    if not os.path.isdir(folder):
        print(f"Error: '{folder}' is not a directory.")
        sys.exit(1)

    clean_stale_files(folder)
    videos = find_unprocessed_videos(folder)
    if not videos:
        print("No unprocessed videos found.")
        sys.exit(0)

    if limit is not None and limit < len(videos):
        print(f"Limiting to {limit} of {len(videos)} video(s).")
        videos = videos[:limit]

    names = [os.path.basename(v) for v in videos]
    max_workers = min(2, len(videos))

    print(f"Found {len(videos)} video(s) to process ({max_workers} workers):\n")

    results = {}
    results_lock = threading.Lock()

    def worker(video_path, name):
        result = run_one(video_path, name, no_upload, skip_tt, keep_voice)
        with results_lock:
            results[name] = result

    threads = []
    for video, name in zip(videos, names):
        t = threading.Thread(target=worker, args=(video, name))
        threads.append(t)

    active = []
    pending = list(threads)

    def start_next():
        if pending:
            t = pending.pop(0)
            t.start()
            active.append(t)

    for _ in range(max_workers):
        start_next()

    while any(t.is_alive() for t in threads) or pending:
        time.sleep(0.25)
        active = [t for t in active if t.is_alive()]
        while len(active) < max_workers and pending:
            start_next()

    # Summary
    print()
    succeeded = sum(1 for _, ok, _, _ in results.values() if ok)
    failed_count = sum(1 for _, ok, _, _ in results.values() if not ok)
    print(f"Done: {succeeded} succeeded, {failed_count} failed out of {len(results)} total.")

    if failed_count:
        print(f"\n{'=' * 60}")
        print("Failed video logs:")
        print(f"{'=' * 60}")
        for name in names:
            if name in results and not results[name][1]:
                print(f"\n--- {name} ---")
                for line in results[name][3]:
                    print(f"  {line}")
        sys.exit(1)


if __name__ == "__main__":
    main()
