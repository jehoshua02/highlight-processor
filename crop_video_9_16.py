import subprocess
import sys
import os
import json

def get_video_dimensions(input_path, ffprobe_path=None):
    """
    Get video width and height using ffprobe.
    """
    if ffprobe_path is None:
        ffprobe_path = 'ffprobe'
    command = [
        ffprobe_path,
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'json',
        input_path
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    info = json.loads(result.stdout)
    width = info['streams'][0]['width']
    height = info['streams'][0]['height']
    return width, height

def crop_video_9_16(input_path, output_path, ffmpeg_path=None, ffprobe_path=None):
    # Explicit paths to ffmpeg and ffprobe in bin directory at workspace root
    workspace_root = os.path.dirname(os.path.abspath(__file__))
    bin_dir = os.path.join(workspace_root, 'bin')
    ffmpeg_path = os.path.join(bin_dir, 'ffmpeg.exe')
    ffprobe_path = os.path.join(bin_dir, 'ffprobe.exe')
    width, height = get_video_dimensions(input_path, ffprobe_path)
    crop_width = int(height * 9 / 16)
    crop_height = height
    x = int((width - crop_width) / 2)
    y = 0
    command = [
        ffmpeg_path,
        '-i', input_path,
        '-vf', f'crop={crop_width}:{crop_height}:{x}:{y},scale=1080:1920,setsar=1',
        '-c:v', 'libx264',
        '-crf', '18',
        '-preset', 'fast',
        '-c:a', 'copy',
        output_path
    ]
    try:
        subprocess.run(command, check=True)
        print(f"Cropped video saved to {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error cropping video: {e}")
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python crop_video_9_16.py <input>")
        sys.exit(1)
    input_path = sys.argv[1]
    base, ext = os.path.splitext(input_path)
    output_path = f"{base}_cropped_9_16{ext}"
    crop_video_9_16(input_path, output_path)
