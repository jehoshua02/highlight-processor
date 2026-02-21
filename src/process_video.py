"""
process_video.py
Pipeline: crop video to 9:16, then scrub voices.

Usage:
    python process_video.py input.mp4 [output.mp4]
"""
import sys
import os
from crop_video_moviepy import crop_video_9_16
from scrub_voices import scrub_voices


def process_video(input_path, output_path=None):
    # Step 1: Crop to 9:16
    base, ext = os.path.splitext(input_path)
    cropped_path = f"{base}_cropped{ext}"
    print(f"[1/2] Cropping to 9:16: {input_path}")
    crop_video_9_16(input_path, cropped_path)
    print(f"       -> {cropped_path}")

    # Step 2: Scrub voices
    if output_path is None:
        output_path = f"{base}_final{ext}"
    print(f"[2/2] Scrubbing voices: {cropped_path}")
    scrub_voices(cropped_path, output_path)
    print(f"       -> {output_path}")

    # Clean up intermediate file
    os.remove(cropped_path)
    print(f"Done! Output: {output_path}")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3 or sys.argv[1] == "--help":
        print("Usage: python process_video.py input.mp4 [output.mp4]")
        print()
        print("  Crops video to 9:16 (1080x1920) and removes vocals.")
        print("  Output is saved as <name>_final.mp4 by default.")
        print()
        print("Docker usage:")
        print("  docker compose run --rm process /videos/myclip.mp4")
        sys.exit(0 if len(sys.argv) >= 2 and sys.argv[1] == "--help" else 1)
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) == 3 else None
    process_video(input_path, output_path)
