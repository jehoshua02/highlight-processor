# Highlight Processing

Video processing tools for creating short-form content. Crops videos to 9:16 portrait and removes vocals.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

## Setup

```sh
docker compose build
```

## Usage

Drop your `.mp4` files into the `videos/` folder, then run:

### Crop + Scrub Voices (full pipeline)

**Single video:**

```sh
docker compose run --rm process /videos/input.mp4
```

Output: `videos/input_final.mp4`

**All videos in folder:**

```sh
docker compose run --rm process_all /videos
```

Processes every `.mp4` in the folder that hasn't already been processed (skips files ending in `_final`, `_cropped`, `_cropped_9_16`, `_novocals`). Videos are processed in parallel.

### Crop Only (9:16 portrait)

```sh
docker compose run --rm crop /videos/input.mp4
```

Output: `videos/input_cropped_9_16.mp4`

### Scrub Voices Only

```sh
docker compose run --rm scrub_voices /videos/input.mp4
```

Output: `videos/input_novocals.mp4`
