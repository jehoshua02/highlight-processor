"""
crop_video.py
Crop a video to 9:16 aspect ratio using moviepy (no ffmpeg CLI required).

Usage:
	python crop_video.py input.mp4 [output.mp4]

Requires:
	pip install moviepy
"""
import sys
import os
from moviepy.editor import VideoFileClip

def crop_video_9_16(input_path, output_path=None):
	clip = VideoFileClip(input_path)
	w, h = clip.size
	# Calculate crop for 9:16 aspect ratio
	crop_width = int(h * 9 / 16)
	x1 = int((w - crop_width) / 2)
	x2 = x1 + crop_width
	cropped = clip.crop(x1=x1, y1=0, x2=x2, y2=h)
	cropped = cropped.resize(newsize=(1080, 1920))
	if output_path is None:
		base, ext = os.path.splitext(input_path)
		output_path = f"{base}_cropped_9_16{ext}"
	cropped.write_videofile(output_path, audio_codec='aac')
	clip.close()
	cropped.close()
	return output_path

if __name__ == "__main__":
	if len(sys.argv) < 2 or len(sys.argv) > 3:
		print("Usage: python crop_video.py input.mp4 [output.mp4]")
		sys.exit(1)
	input_path = sys.argv[1]
	output_path = sys.argv[2] if len(sys.argv) == 3 else None
	result = crop_video_9_16(input_path, output_path)
	print(result)
