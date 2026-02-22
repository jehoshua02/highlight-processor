"""
crop_video.py
Center-crop a video to 9:16 (1080x1920) using FFmpeg directly.

Much faster than MoviePy: the entire crop+scale+encode pipeline runs in a
single FFmpeg process instead of decoding frame-by-frame through Python.

Usage:
    python crop_video.py input.mp4 [output.mp4]

Docker usage:
    docker compose run --rm crop "/videos/input.mp4"
"""
import subprocess
import sys
import os


def crop_video_9_16(input_path, output_path=None):
    """Center-crop and resize video to 1080x1920 (9:16) using FFmpeg.

    Uses a single FFmpeg command with crop + scale filters, which is
    significantly faster than frame-by-frame processing via MoviePy.
    """
    if not os.path.exists(input_path):
        print(f"File not found: {input_path}")
        sys.exit(1)

    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_cropped_9_16{ext}"

    # Probe input dimensions
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0",
        input_path,
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error probing video: {result.stderr}")
        sys.exit(1)

    w, h = map(int, result.stdout.strip().split(","))
    print(f"Input resolution: {w}x{h}")

    # Calculate center crop to 9:16 aspect ratio
    target_ratio = 9 / 16
    current_ratio = w / h

    if current_ratio > target_ratio:
        # Video is wider than 9:16 — crop width
        crop_w = int(h * target_ratio)
        crop_h = h
    else:
        # Video is taller than 9:16 — crop height
        crop_w = w
        crop_h = int(w / target_ratio)

    x_offset = (w - crop_w) // 2
    y_offset = (h - crop_h) // 2

    print(f"Cropping to {crop_w}x{crop_h} at offset ({x_offset}, {y_offset}), then scaling to 1080x1920")

    # Single FFmpeg command: crop → scale → AAC audio
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", f"crop={crop_w}:{crop_h}:{x_offset}:{y_offset},scale=1080:1920",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error cropping video:\n{result.stderr}")
        sys.exit(1)

    print(f"Cropped video saved to: {output_path}")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "--help":
        print("Usage: python crop_video.py input.mp4 [output.mp4]")
        print()
        print("  Center-crops video to 9:16 (1080x1920) with AAC audio.")
        print("  Output defaults to <name>_cropped_9_16.mp4.")
        print()
        print("Docker usage:")
        print('  docker compose run --rm crop "/videos/input.mp4"')
        sys.exit(0 if len(sys.argv) >= 2 and sys.argv[1] == "--help" else 1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) >= 3 else None
    result = crop_video_9_16(input_path, output_path)
    print(result)
