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

```sh
docker compose run --rm process /videos/input.mp4
```

Output: `videos/input_final.mp4`

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

### Upload to Instagram

Upload a processed video as an Instagram Reel. First, copy `.env.example` to `.env` and fill in your Instagram credentials:

```sh
cp .env.example .env
```

Then run:

```sh
docker compose run --rm upload-instagram /videos/input_final.mp4 "Check out this highlight! #gaming"
```

You can also upload as part of the full pipeline by adding `--upload`:

```sh
docker compose run --rm process /videos/input.mp4 --upload "My caption"
```
