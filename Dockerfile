FROM python:3.10-slim

# Install system dependencies (ffmpeg + libsndfile for audio processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ /app/src/

# No default entrypoint — set per service in docker-compose
CMD ["python", "--version"]
