"""scrub_voices.py
Remove vocals from a video using Demucs (Meta's AI source-separation model).

Extracts audio, runs 2-stem separation (vocals vs accompaniment),
and replaces the original audio with the accompaniment-only track.

Usage:
    python scrub_voices.py input_video.mp4 [output_video.mp4]

Docker usage:
    docker compose run --rm scrub_voices /videos/myclip.mp4
"""
import subprocess
import sys
import os
import tempfile
from moviepy.editor import VideoFileClip, AudioFileClip


def scrub_voices(input_video, output_video=None):
    """Remove vocals from video audio using Demucs 2-stem separation."""
    if not os.path.isfile(input_video):
        print(f"File not found: {input_video}")
        sys.exit(1)

    if output_video is None:
        base, ext = os.path.splitext(input_video)
        output_video = f"{base}_novocals{ext}"

    with tempfile.TemporaryDirectory(prefix="scrub_voices_") as tmp_dir:
        # Extract audio to WAV
        audio_path = os.path.join(tmp_dir, "audio.wav")
        print("  Extracting audio …")
        subprocess.run([
            "ffmpeg", "-y", "-i", input_video,
            "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
            audio_path,
        ], check=True, capture_output=True)

        # Run Demucs 2-stem separation (vocals vs everything else)
        print("  Running Demucs vocal separation …")
        subprocess.run([
            sys.executable, "-m", "demucs",
            "--two-stems", "vocals",
            "-o", tmp_dir,
            "--filename", "{stem}.{ext}",
            audio_path,
        ], check=True)

        # Find the accompaniment track (no_vocals.wav)
        accompaniment = os.path.join(tmp_dir, "htdemucs", "no_vocals.wav")
        if not os.path.isfile(accompaniment):
            accompaniment = os.path.join(tmp_dir, "htdemucs", "audio", "no_vocals.wav")
        if not os.path.isfile(accompaniment):
            print(f"  ERROR: Could not find separated audio. Contents:")
            for root, dirs, files in os.walk(tmp_dir):
                for f in files:
                    print(f"    {os.path.join(root, f)}")
            sys.exit(1)

        # Merge accompaniment back with video
        print("  Merging accompaniment with video …")
        video = VideoFileClip(input_video)
        new_audio = AudioFileClip(accompaniment)
        final = video.set_audio(new_audio)
        final.write_videofile(output_video, audio_codec="aac")
        video.close()
        new_audio.close()
        final.close()

    return output_video


if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3 or sys.argv[1] == "--help":
        print("Usage: python scrub_voices.py input_video.mp4 [output_video.mp4]")
        print()
        print("  Removes voices/vocals from a video file using Demucs.")
        print("  Output is saved next to the input as <name>_novocals.mp4 by default.")
        print()
        print("Docker usage:")
        print("  docker compose run --rm scrub_voices /videos/myclip.mp4")
        sys.exit(0 if len(sys.argv) >= 2 and sys.argv[1] == "--help" else 1)
    input_video = sys.argv[1]
    output_video = sys.argv[2] if len(sys.argv) == 3 else None
    result = scrub_voices(input_video, output_video)
    print(f"Output video: {result}")
