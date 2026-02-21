# scrub_voices.py
"""
Script to remove voices from a video file using audio source separation.
This uses the 'spleeter' library to separate vocals from accompaniment.

Usage:
	python scrub_voices.py input_video.mp4 output_video.mp4

Requires:
	pip install spleeter moviepy
"""
import sys
import os
from moviepy.editor import VideoFileClip, AudioFileClip
from spleeter.separator import Separator

def scrub_voices(input_video, output_video):
	# Extract audio from video
	video = VideoFileClip(input_video)
	audio_path = 'temp_audio.wav'
	video.audio.write_audiofile(audio_path, logger=None)

	# Separate vocals using spleeter
	separator = Separator('spleeter:2stems')
	separator.separate_to_file(audio_path, 'output')
	no_vocals_path = os.path.join('output', os.path.splitext(os.path.basename(audio_path))[0], 'accompaniment.wav')

	# Generate output filename if not provided
	if output_video is None:
		base, ext = os.path.splitext(input_video)
		output_video = f"{base}_novocals{ext}"

	# Replace audio in video
	new_audio = AudioFileClip(no_vocals_path)
	new_video = video.set_audio(new_audio)
	new_video.write_videofile(output_video, audio_codec='aac')

	# Cleanup
	video.close()
	new_audio.close()
	new_video.close()
	os.remove(audio_path)
	import shutil
	shutil.rmtree('output')
	return output_video

if __name__ == '__main__':
	if len(sys.argv) < 2 or len(sys.argv) > 3 or sys.argv[1] == '--help':
		print('Usage: python scrub_voices.py input_video.mp4 [output_video.mp4]')
		print()
		print('  Removes voices/vocals from a video file.')
		print('  Output is saved next to the input as <name>_novocals.mp4 by default.')
		print()
		print('Docker usage:')
		print('  docker compose run --rm scrub_voices /videos/myclip.mp4')
		sys.exit(0 if len(sys.argv) >= 2 and sys.argv[1] == '--help' else 1)
	input_video = sys.argv[1]
	output_video = sys.argv[2] if len(sys.argv) == 3 else None
	result = scrub_voices(input_video, output_video)
	print(f"Output video: {result}")
