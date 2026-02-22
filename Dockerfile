FROM python:3.10-slim

# Install system dependencies (ffmpeg + libsndfile for audio processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies first (better layer caching)
# Install CPU-only PyTorch first (much smaller than default CUDA build)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchaudio torchcodec --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ /app/src/

# Ensure src/ is on the Python path so modules can import each other
ENV PYTHONPATH="/app/src:${PYTHONPATH}"

# No default entrypoint — set per service in docker-compose
CMD ["python", "--version"]
