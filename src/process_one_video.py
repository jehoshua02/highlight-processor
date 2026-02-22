"""process_one_video.py
Pipeline: crop video to 9:16, scrub voices, normalize audio loudness,
then upload to Instagram Reels, YouTube Shorts, and TikTok.

Usage:
    python process_one_video.py [--no-upload] input.mp4 [output.mp4]
"""
import sys
import os
from crop_video import crop_video_9_16
from scrub_voices import scrub_voices
from normalize_audio import normalize_audio
from upload_one_video import upload_one_video


def process_video(input_path, output_path=None, upload=True):
    base, ext = os.path.splitext(input_path)
    if output_path is None:
        output_path = f"{base}_final{ext}"

    # In-progress suffixes describe what's happening, cleaned up on exit
    cropped_tmp = f"{base}_cropping{ext}"
    scrubbed_tmp = f"{base}_scrubbing{ext}"
    output_tmp = f"{base}_normalizing{ext}"

    try:
        # Step 1: Crop to 9:16
        print(f"[1/4] Cropping to 9:16: {input_path}")
        crop_video_9_16(input_path, cropped_tmp)
        print(f"       -> {cropped_tmp}")

        # Step 2: Scrub voices
        print(f"[2/4] Scrubbing voices: {cropped_tmp}")
        scrub_voices(cropped_tmp, scrubbed_tmp)
        print(f"       -> {scrubbed_tmp}")

        # Step 3: Normalize audio loudness
        print(f"[3/4] Normalizing audio: {scrubbed_tmp}")
        normalize_audio(scrubbed_tmp, output_tmp)
        print(f"       -> {output_tmp}")

        # Rename to final name only after fully complete
        os.replace(output_tmp, output_path)
        print(f"Done processing! Output: {output_path}")

        # Step 4: Upload to all platforms
        if upload:
            print(f"[4/4] Uploading to all platforms: {output_path}")
            upload_one_video(output_path)
        else:
            print("Skipping upload (--no-upload)")

        return output_path
    finally:
        # Always clean up intermediate/temp files
        for tmp in (cropped_tmp, scrubbed_tmp, output_tmp):
            if os.path.exists(tmp):
                os.remove(tmp)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--no-upload"]
    no_upload = "--no-upload" in sys.argv

    if len(args) < 1 or len(args) > 2 or sys.argv[1] == "--help":
        print("Usage: python process_one_video.py [--no-upload] input.mp4 [output.mp4]")
        print()
        print("  Crops video to 9:16 (1080x1920), removes vocals, normalizes audio,")
        print("  and uploads to Instagram Reels, YouTube Shorts, and TikTok.")
        print("  Output is saved as <name>_final.mp4 by default.")
        print()
        print("  --no-upload   Skip uploading after processing.")
        print()
        print("Docker usage:")
        print("  docker compose run --rm process /videos/myclip.mp4")
        print("  docker compose run --rm process --no-upload /videos/myclip.mp4")
        sys.exit(0 if len(sys.argv) >= 2 and sys.argv[1] == "--help" else 1)
    input_path = args[0]
    output_path = args[1] if len(args) == 2 else None
    process_video(input_path, output_path, upload=not no_upload)
