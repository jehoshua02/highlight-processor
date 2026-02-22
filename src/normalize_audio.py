# normalize_audio.py
"""
Limit audio peaks in a video file using ffmpeg's alimiter filter.

Catches loud peaks and squashes them down so nothing exceeds a safe ceiling,
without boosting quiet audio. Keeps the overall mix natural — just shaves
the tops off anything that would blow out eardrums.

Usage:
    python normalize_audio.py input_video.mp4 [output_video.mp4]

Requires:
    ffmpeg (system package)
"""
import sys
import os
import subprocess


def normalize_audio(input_path, output_path=None):
    """Limit audio peaks in a video file.

    Uses ffmpeg's alimiter to hard-limit peaks at -1 dBFS. Loud transients
    are clamped down; quiet parts are left untouched.

    Args:
        input_path: Path to input video file.
        output_path: Path for output file. Defaults to <name>_normalized.mp4.

    Returns:
        Path to the output file.
    """
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_normalized{ext}"

    # alimiter: brickwall peak limiter
    #   limit=0.89 (-1 dBFS ceiling — nothing goes above this)
    #   attack=5ms  (fast enough to catch transients)
    #   release=50ms (smooth release to avoid pumping artifacts)
    #   level=false (don't auto-boost gain — just limit peaks)
    audio_filter = "alimiter=limit=0.89:attack=5:release=50:level=false"

    cmd = [
        "ffmpeg", "-hide_banner", "-y",
        "-i", input_path,
        "-af", audio_filter,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        output_path,
    ]

    print(f"  Limiting audio peaks: {input_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: ffmpeg peak limiting failed:\n{result.stderr}")
        sys.exit(1)

    print(f"  Output: {output_path}")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3 or sys.argv[1] == "--help":
        print("Usage: python normalize_audio.py input_video.mp4 [output_video.mp4]")
        print()
        print("  Limits audio peaks at -1 dBFS so nothing clips or gets too loud.")
        print("  Quiet audio is left untouched — only peaks are squashed.")
        print("  Output is saved as <name>_normalized.mp4 by default.")
        print()
        print("Docker usage:")
        print("  docker compose run --rm normalize /videos/myclip.mp4")
        sys.exit(0 if sys.argv[1] == "--help" else 1)
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) == 3 else None
    result = normalize_audio(input_path, output_path)
    print(f"Output video: {result}")
