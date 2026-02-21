"""process_all_videos.py
Find all unprocessed videos in a folder and run the full pipeline on each.

Skips files whose names end with known output suffixes so re-running is
safe (idempotent). Videos are processed one at a time.

Usage:
    python process_all_videos.py /videos
"""
import sys
import os
from process_one_video import process_video

KNOWN_SUFFIXES = (
    "_final", "_cropped", "_cropped_9_16", "_novocals",
    "_cropped_processing", "_final_processing",
)
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm")


def is_already_processed(filepath):
    """Return True if the filename ends with a known output suffix."""
    name = os.path.splitext(os.path.basename(filepath))[0]
    return any(name.endswith(suffix) for suffix in KNOWN_SUFFIXES)


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


def run_one(video_path):
    """Wrapper so each worker runs the full pipeline and returns status."""
    try:
        output = process_video(video_path)
        return video_path, True, output
    except Exception as e:
        return video_path, False, str(e)


def main():
    if len(sys.argv) != 2 or sys.argv[1] == "--help":
        print("Usage: python process_all_videos.py <folder>")
        print()
        print("  Processes every video in <folder> that hasn't already")
        print("  been processed (crop 9:16 + scrub voices).")
        print()
        print("Docker usage:")
        print("  docker compose run --rm process_all /videos")
        sys.exit(0 if sys.argv[-1] == "--help" else 1)

    folder = sys.argv[1]
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
        _, ok, detail = run_one(video)
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
