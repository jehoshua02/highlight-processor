"""
process_video.py
Pipeline: crop video to 9:16, scrub voices, and upload to Instagram.

Usage:
    python process_video.py input.mp4 [output.mp4] [--upload "caption"]
"""
import sys
import os
from crop_video_moviepy import crop_video_9_16
from scrub_voices import scrub_voices
from upload_instagram import upload_reel


def process_video(input_path, output_path=None, upload_caption=None):
    steps = 3 if upload_caption is not None else 2

    # Step 1: Crop to 9:16
    base, ext = os.path.splitext(input_path)
    cropped_path = f"{base}_cropped{ext}"
    print(f"[1/{steps}] Cropping to 9:16: {input_path}")
    crop_video_9_16(input_path, cropped_path)
    print(f"       -> {cropped_path}")

    # Step 2: Scrub voices
    if output_path is None:
        output_path = f"{base}_final{ext}"
    print(f"[2/{steps}] Scrubbing voices: {cropped_path}")
    scrub_voices(cropped_path, output_path)
    print(f"       -> {output_path}")

    # Clean up intermediate file
    os.remove(cropped_path)

    # Step 3: Upload to Instagram (optional)
    if upload_caption is not None:
        print(f"[3/{steps}] Uploading to Instagram...")
        media = upload_reel(output_path, caption=upload_caption)
        print(f"       -> https://www.instagram.com/reel/{media.code}/")

    print(f"Done! Output: {output_path}")
    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Crop video to 9:16, remove vocals, and optionally upload to Instagram."
    )
    parser.add_argument("input", help="Input video file path")
    parser.add_argument("output", nargs="?", default=None, help="Output file path (default: <name>_final.mp4)")
    parser.add_argument("--upload", metavar='"caption"', default=None,
                        help="Upload as Instagram Reel with this caption (requires IG_USERNAME & IG_PASSWORD env vars)")

    args = parser.parse_args()
    process_video(args.input, args.output, upload_caption=args.upload)
