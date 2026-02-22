"""process_all_videos.py
Find all unprocessed videos in a folder and run the full pipeline on each.

Skips files whose names end with known output suffixes so re-running is
safe (idempotent). Videos are processed one at a time.

Usage:
    python process_all_videos.py /videos
"""
import sys
import os
import subprocess

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


def find_unprocessed_videos(folder):
    """Return a sorted list of video files in *folder* that need processing."""
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
        # Skip if any known derived file already exists for this source
        existing = [f"{name}{suffix}{ext}" for suffix in KNOWN_SUFFIXES
                    if os.path.exists(os.path.join(folder, f"{name}{suffix}{ext}"))]
        if existing:
            print(f"  Skipping {entry} (found: {', '.join(existing)})")
            continue
        videos.append(full)
    videos.sort()
    return videos


def run_one(video_path, no_upload=False):
    """Run process_one_video in a subprocess to isolate TensorFlow state.

    Spleeter/TensorFlow corrupts its internal graph after a single run,
    so each video must be processed in a fresh Python process.
    """
    cmd = [sys.executable, "src/process_one_video.py"]
    if no_upload:
        cmd.append("--no-upload")
    cmd.append(video_path)
    result = subprocess.run(cmd)
    if result.returncode == 0:
        base, ext = os.path.splitext(video_path)
        return video_path, True, f"{base}_final{ext}"
    else:
        return video_path, False, f"exited with code {result.returncode}"


def main():
    args = [a for a in sys.argv[1:] if a != "--no-upload"]
    no_upload = "--no-upload" in sys.argv

    if len(args) != 1 or sys.argv[1] == "--help":
        print("Usage: python process_all_videos.py [--no-upload] <folder>")
        print()
        print("  Processes every video in <folder> that hasn't already")
        print("  been processed (crop 9:16 + scrub voices).")
        print()
        print("  --no-upload   Skip uploading after processing.")
        print()
        print("Docker usage:")
        print("  docker compose run --rm process_all /videos")
        print("  docker compose run --rm process_all --no-upload /videos")
        sys.exit(0 if sys.argv[-1] == "--help" else 1)

    folder = args[0]
    if not os.path.isdir(folder):
        print(f"Error: '{folder}' is not a directory.")
        sys.exit(1)

    videos = find_unprocessed_videos(folder)
    if not videos:
        print("No unprocessed videos found.")
        sys.exit(0)

    print(f"Found {len(videos)} video(s) to process:")
    for v in videos:
        print(f"  - {os.path.basename(v)}")
    print()

    succeeded = 0
    failed = 0
    for i, video in enumerate(videos, 1):
        name = os.path.basename(video)
        print(f"=== [{i}/{len(videos)}] {name} ===")
        _, ok, detail = run_one(video, no_upload=no_upload)
        if ok:
            print(f"[OK]   {name} -> {os.path.basename(detail)}\n")
            succeeded += 1
        else:
            print(f"[FAIL] {name}: {detail}\n")
            failed += 1

    print(f"Done: {succeeded} succeeded, {failed} failed out of {succeeded + failed} total.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
