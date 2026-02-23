"""process_one_video.py
Resumable pipeline: crop video to 9:16, scrub voices, normalize audio
loudness, then upload to Instagram Reels, YouTube Shorts, and TikTok.

Processing checkpoints (filesystem is source of truth):
  _cropped  — crop complete
  _novocals — voice removal complete
  _final    — all processing complete

Upload status is tracked in a sidecar JSON (<source>.status.json).
On re-run, completed steps are skipped automatically.

When all steps succeed, source, final, and sidecar files are moved to a
processed/ subfolder and intermediates are deleted.

Usage:
    python process_one_video.py [--no-upload] input.mp4 [output.mp4]
"""
import sys
import os
import json
import time
import shutil
from datetime import datetime, timezone
from crop_video import crop_video_9_16
from scrub_voices import scrub_voices
from normalize_audio import normalize_audio
from upload_one_video import upload_one_video


def _now():
    """ISO-formatted UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _read_sidecar(path):
    """Read sidecar JSON, or return a fresh structure."""
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"steps": {}}


def _write_sidecar(path, data):
    """Atomically write sidecar JSON."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def _run_step(sidecar, sidecar_path, step_name, step_fn, tmp_path, stable_path):
    """Run one processing step with checkpoint and sidecar tracking.

    Writes to tmp_path during processing, promoting to stable_path on
    success.  On failure the tmp file is deleted and the error is recorded
    in the sidecar.
    """
    t0 = time.time()
    started = _now()
    sidecar["steps"][step_name] = {"status": "in_progress", "started_at": started}
    _write_sidecar(sidecar_path, sidecar)
    try:
        step_fn()
        os.replace(tmp_path, stable_path)
    except BaseException as exc:
        error_msg = (f"exited with code {exc.code}"
                     if isinstance(exc, SystemExit) else str(exc))
        sidecar["steps"][step_name] = {
            "status": "failed",
            "started_at": started,
            "completed_at": _now(),
            "duration_seconds": round(time.time() - t0, 1),
            "error": error_msg,
        }
        _write_sidecar(sidecar_path, sidecar)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    sidecar["steps"][step_name] = {
        "status": "done",
        "started_at": started,
        "completed_at": _now(),
        "duration_seconds": round(time.time() - t0, 1),
        "output": os.path.basename(stable_path),
    }
    _write_sidecar(sidecar_path, sidecar)


def process_video(input_path, output_path=None, upload=True, skip_platforms=None):
    """Run the full pipeline with automatic resume from checkpoints.

    Filesystem is the source of truth for processing steps (checkpoint
    files).  Sidecar JSON is authoritative for upload status only; step
    timings and errors are recorded for debugging.
    """
    base, ext = os.path.splitext(input_path)
    if output_path is None:
        output_path = f"{base}_final{ext}"

    folder = os.path.dirname(input_path) or "."
    sidecar_path = f"{input_path}.status.json"

    # Checkpoint paths (stable — survive failure for resume)
    cropped_path = f"{base}_cropped{ext}"
    novocals_path = f"{base}_novocals{ext}"

    # In-progress paths (deleted on failure, promoted on success)
    cropping_tmp = f"{base}_cropping{ext}"
    scrubbing_tmp = f"{base}_scrubbing{ext}"
    normalizing_tmp = f"{base}_normalizing{ext}"

    # Load or initialise sidecar
    sidecar = _read_sidecar(sidecar_path)
    sidecar["source"] = os.path.basename(input_path)
    sidecar.setdefault("started_at", _now())
    sidecar["status"] = "in_progress"
    _write_sidecar(sidecar_path, sidecar)

    try:
        # --- Step 1: Crop to 9:16 ---
        if os.path.exists(output_path) or os.path.exists(novocals_path) or os.path.exists(cropped_path):
            print("[1/4] Cropping to 9:16: skipped (checkpoint exists)")
        else:
            print(f"[1/4] Cropping to 9:16: {input_path}")
            _run_step(sidecar, sidecar_path, "crop",
                      lambda: crop_video_9_16(input_path, cropping_tmp),
                      cropping_tmp, cropped_path)
            print(f"       -> {cropped_path}")

        # --- Step 2: Scrub voices ---
        if os.path.exists(output_path) or os.path.exists(novocals_path):
            print("[2/4] Scrubbing voices: skipped (checkpoint exists)")
        else:
            print(f"[2/4] Scrubbing voices: {cropped_path}")
            _run_step(sidecar, sidecar_path, "scrub_voices",
                      lambda: scrub_voices(cropped_path, scrubbing_tmp),
                      scrubbing_tmp, novocals_path)
            print(f"       -> {novocals_path}")

        # --- Step 3: Normalize audio ---
        if os.path.exists(output_path):
            print("[3/4] Normalizing audio: skipped (checkpoint exists)")
        else:
            print(f"[3/4] Normalizing audio: {novocals_path}")
            _run_step(sidecar, sidecar_path, "normalize",
                      lambda: normalize_audio(novocals_path, normalizing_tmp),
                      normalizing_tmp, output_path)
            print(f"       -> {output_path}")

    except SystemExit:
        sidecar = _read_sidecar(sidecar_path)
        if sidecar.get("status") != "failed":
            sidecar["status"] = "failed"
            sidecar["completed_at"] = _now()
            _write_sidecar(sidecar_path, sidecar)
        raise
    except Exception as exc:
        sidecar = _read_sidecar(sidecar_path)
        sidecar["status"] = "failed"
        sidecar["completed_at"] = _now()
        _write_sidecar(sidecar_path, sidecar)
        print(f"Pipeline failed: {exc}")
        sys.exit(1)

    print(f"Done processing! Output: {output_path}")

    # --- Step 4: Upload ---
    if not upload:
        print("Skipping upload (--no-upload)")
        return output_path

    print(f"[4/4] Uploading to all platforms: {output_path}")
    results = upload_one_video(output_path, sidecar_path=sidecar_path,
                               skip_platforms=skip_platforms)
    sidecar = _read_sidecar(sidecar_path)

    if any(not ok for ok, _ in results.values()):
        sidecar["status"] = "failed"
        sidecar["completed_at"] = _now()
        _write_sidecar(sidecar_path, sidecar)
        sys.exit(1)

    # --- Full success: move to processed/ ---
    sidecar["status"] = "done"
    sidecar["completed_at"] = _now()
    _write_sidecar(sidecar_path, sidecar)

    processed_dir = os.path.join(folder, "processed")
    os.makedirs(processed_dir, exist_ok=True)

    for src in (input_path, output_path, sidecar_path):
        if os.path.exists(src):
            dest = os.path.join(processed_dir, os.path.basename(src))
            shutil.move(src, dest)

    for intermediate in (cropped_path, novocals_path):
        if os.path.exists(intermediate):
            os.remove(intermediate)

    print(f"Moved to: {os.path.join(processed_dir, os.path.basename(output_path))}")
    return output_path


if __name__ == "__main__":
    flags = {"--no-upload", "--skip-upload-tt"}
    args = [a for a in sys.argv[1:] if a not in flags]
    no_upload = "--no-upload" in sys.argv
    skip_tt = "--skip-upload-tt" in sys.argv

    if len(args) < 1 or len(args) > 2 or sys.argv[1] == "--help":
        print("Usage: python process_one_video.py [--no-upload] [--skip-upload-tt] input.mp4 [output.mp4]")
        print()
        print("  Resumable pipeline: crops to 9:16, removes vocals, normalizes")
        print("  audio, and uploads to Instagram, YouTube, and TikTok.")
        print()
        print("  On re-run, completed steps are skipped automatically.")
        print("  Processing checkpoints: _cropped, _novocals, _final")
        print("  Upload status tracked in <source>.status.json")
        print()
        print("  --no-upload        Process only, skip uploading.")
        print("  --skip-upload-tt   Skip TikTok upload.")
        print()
        print("Docker usage:")
        print("  docker compose run --rm process /videos/myclip.mp4")
        print("  docker compose run --rm process --no-upload /videos/myclip.mp4")
        sys.exit(0 if len(sys.argv) >= 2 and sys.argv[1] == "--help" else 1)
    input_path = args[0]
    output_path = args[1] if len(args) == 2 else None
    skip_platforms = {"TikTok"} if skip_tt else None
    process_video(input_path, output_path, upload=not no_upload,
                  skip_platforms=skip_platforms)
