"""process_all_videos.py
Find all unprocessed videos in a folder and run the full pipeline on each.

Skips files whose names end with known output suffixes so re-running is
safe (idempotent). Videos are processed in parallel with a live terminal
display showing real-time progress for each worker.

Usage:
    python process_all_videos.py /videos
"""
import sys
import os
import subprocess
import threading
import time
import shutil

KNOWN_SUFFIXES = (
    "_final", "_cropped", "_cropped_9_16", "_novocals",
)
IN_PROGRESS_SUFFIXES = (
    "_cropping", "_scrubbing", "_normalizing",
)
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm")

# ANSI escape codes
CLEAR_LINE = "\033[2K"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"


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
        existing = [f"{name}{suffix}{ext}" for suffix in KNOWN_SUFFIXES
                    if os.path.exists(os.path.join(folder, f"{name}{suffix}{ext}"))]
        if existing:
            print(f"  Skipping {entry} (found: {', '.join(existing)})")
            continue
        videos.append(full)
    videos.sort()
    return videos


PIPELINE_STEPS = [
    "Cropping to 9:16",
    "Scrubbing voices",
    "Normalizing audio",
    "Uploading",
]


class LiveDisplay:
    """Manages a live-updating multi-line terminal display.

    Each video shows a header line, per-step history with individual
    timings, and the latest log line under the active step.
    """

    def __init__(self, slots):
        self.slots = slots
        self.lock = threading.Lock()
        self.term_width = shutil.get_terminal_size((80, 24)).columns
        self.last_line_count = 0

        # Per-video state
        self.video_status = {n: "waiting" for n in slots}  # waiting/running/done/failed
        self.video_start = {n: None for n in slots}
        self.video_end = {n: None for n in slots}
        self.video_result = {n: "" for n in slots}  # e.g. "→ clip_final.mp4"

        # Per-video per-step state: list of dicts
        self.steps = {}
        for n in slots:
            self.steps[n] = [
                {"name": s, "status": "waiting", "start": None, "end": None}
                for s in PIPELINE_STEPS
            ]

        # Latest output line per video (shown under active step)
        self.last_output = {n: "" for n in slots}

    def start_video(self, name):
        with self.lock:
            self.video_status[name] = "running"
            self.video_start[name] = time.time()

    def start_step(self, name, step_index):
        with self.lock:
            step = self.steps[name][step_index]
            step["status"] = "running"
            step["start"] = time.time()

    def finish_step(self, name, step_index):
        with self.lock:
            step = self.steps[name][step_index]
            step["status"] = "done"
            step["end"] = time.time()

    def finish_video(self, name, ok, result_text=""):
        with self.lock:
            self.video_status[name] = "done" if ok else "failed"
            self.video_end[name] = time.time()
            self.video_result[name] = result_text
            # Mark any running steps as done/failed
            for step in self.steps[name]:
                if step["status"] == "running":
                    step["status"] = "done" if ok else "failed"
                    step["end"] = time.time()

    def set_output(self, name, line):
        with self.lock:
            self.last_output[name] = line.strip()

    def _fmt_time(self, start, end=None):
        if start is None:
            return ""
        elapsed = (end or time.time()) - start
        secs = int(elapsed)
        mins, secs = divmod(secs, 60)
        return f"{mins}:{secs:02d}"

    def _icon(self, status):
        if status == "waiting":
            return f"{DIM}○{RESET}"
        if status == "running":
            return f"{YELLOW}●{RESET}"
        if status == "done":
            return f"{GREEN}✔{RESET}"
        if status == "failed":
            return f"{RED}✘{RESET}"
        return " "

    def _truncate(self, text, max_len):
        if len(text) <= max_len:
            return text
        return text[:max_len - 1] + "…"

    def video_elapsed(self, name):
        return self._fmt_time(self.video_start[name], self.video_end.get(name))

    def render(self):
        """Render the full display as a list of lines."""
        lines = []
        for name in self.slots:
            vs = self.video_status[name]
            icon = self._icon(vs)
            steps = self.steps[name]

            # Find current step index
            current = -1
            for i, s in enumerate(steps):
                if s["status"] == "running":
                    current = i
                    break
            # If none running, find the last done step
            if current == -1:
                for i in range(len(steps) - 1, -1, -1):
                    if steps[i]["status"] in ("done", "failed"):
                        current = i
                        break

            total = len(steps)
            elapsed = self._fmt_time(self.video_start[name], self.video_end.get(name))

            if vs == "waiting":
                lines.append(f" {icon} {name}")
            elif vs in ("running", "done", "failed"):
                # Header: icon (mm:ss) name current/total StepName
                if current >= 0:
                    step_name = steps[current]["name"]
                    step_num = current + 1
                    if vs == "done":
                        header = f" {icon} [{elapsed}] {name} {total}/{total} Complete"
                    elif vs == "failed":
                        header = f" {icon} [{elapsed}] {name} {step_num}/{total} Failed"
                    else:
                        header = f" {icon} [{elapsed}] {name} {step_num}/{total} {step_name}"
                else:
                    header = f" {icon} [{elapsed}] {name} Starting…"

                lines.append(self._truncate(header, self.term_width))

                # Step history lines
                for i, s in enumerate(steps):
                    if s["status"] == "waiting":
                        continue
                    si = self._icon(s["status"])
                    st = self._fmt_time(s["start"], s["end"])
                    step_line = f"  {si} [{st}] {i + 1}. {s['name']}"

                    # Show last output under active/last step
                    if i == current and self.last_output[name]:
                        lines.append(step_line)
                        out = self.last_output[name]
                        out_line = f"    {DIM}{self._truncate(out, self.term_width - 6)}{RESET}"
                        lines.append(out_line)
                    else:
                        lines.append(step_line)

                # Show result line for finished videos
                if vs in ("done", "failed") and self.video_result[name]:
                    lines.append(f"  {self.video_result[name]}")

        return lines

    def draw(self):
        """Draw (or redraw) the display in-place."""
        lines = self.render()
        with self.lock:
            if self.last_line_count > 0:
                sys.stdout.write(f"\033[{self.last_line_count}A")
                # Clear all previous lines
                for _ in range(self.last_line_count):
                    sys.stdout.write(f"{CLEAR_LINE}\n")
                sys.stdout.write(f"\033[{self.last_line_count}A")
            for line in lines:
                sys.stdout.write(f"{CLEAR_LINE}{line}\n")
            self.last_line_count = len(lines)
            sys.stdout.flush()


def run_one_live(video_path, display, name, no_upload=False):
    """Run process_one_video, streaming output to the live display."""
    display.start_video(name)

    cmd = [sys.executable, "-u", "src/process_one_video.py"]
    if no_upload:
        cmd.append("--no-upload")
    cmd.append(video_path)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    current_step = -1

    for line in proc.stdout:
        stripped = line.strip()
        if not stripped:
            continue
        display.set_output(name, stripped)

        if "[1/4]" in stripped:
            current_step = 0
            display.start_step(name, 0)
        elif "[2/4]" in stripped:
            if current_step >= 0:
                display.finish_step(name, current_step)
            current_step = 1
            display.start_step(name, 1)
        elif "[3/4]" in stripped:
            if current_step >= 0:
                display.finish_step(name, current_step)
            current_step = 2
            display.start_step(name, 2)
        elif "[4/4]" in stripped:
            if current_step >= 0:
                display.finish_step(name, current_step)
            current_step = 3
            display.start_step(name, 3)

    proc.wait()

    if proc.returncode == 0:
        if current_step >= 0:
            display.finish_step(name, current_step)
        base, ext = os.path.splitext(video_path)
        final = os.path.basename(f"{base}_final{ext}")
        display.finish_video(name, True, f"→ {final}")
        return video_path, True, final
    else:
        display.finish_video(name, False)
        return video_path, False, f"exited with code {proc.returncode}"


def main():
    args = [a for a in sys.argv[1:] if a != "--no-upload"]
    no_upload = "--no-upload" in sys.argv

    if len(args) != 1 or sys.argv[1] == "--help":
        print("Usage: python process_all_videos.py [--no-upload] <folder>")
        print()
        print("  Processes every video in <folder> that hasn't already")
        print("  been processed (crop 9:16 + scrub voices + normalize).")
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

    names = [os.path.basename(v) for v in videos]
    max_workers = min(4, len(videos))

    print(f"Found {len(videos)} video(s) to process ({max_workers} workers):\n")

    display = LiveDisplay(names)
    results = {}

    def worker(video_path, name):
        result = run_one_live(video_path, display, name, no_upload)
        results[name] = result

    sys.stdout.write(HIDE_CURSOR)
    sys.stdout.flush()

    try:
        display.draw()

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
            display.draw()
            time.sleep(0.25)
            active = [t for t in active if t.is_alive()]
            while len(active) < max_workers and pending:
                start_next()
                active = [t for t in active if t.is_alive()]

        display.draw()

    finally:
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()

    # Summary
    print()
    succeeded = sum(1 for _, ok, _ in results.values() if ok)
    failed_count = sum(1 for _, ok, _ in results.values() if not ok)
    print(f"Done: {succeeded} succeeded, {failed_count} failed out of {len(results)} total.")

    if failed_count:
        print(f"\n{'=' * 60}")
        print("Failed video logs:")
        print(f"{'=' * 60}")
        for name in names:
            if name in results and not results[name][1]:
                print(f"\n--- {name} ---")
                for line in display.logs[name]:
                    print(f"  {line}")
        sys.exit(1)


if __name__ == "__main__":
    main()
