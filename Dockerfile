# vietdub: dashboard + workers in one image (CPU only).
# Build:  docker build -t vietdub .
# Run:    see docker/compose.yml
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
# CPU-only PyTorch first so Demucs does not pull the multi-gigabyte GPU build
RUN pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir '.[all]'

ENV HF_HUB_DISABLE_XET=1 \
    PYTHONUNBUFFERED=1
VOLUME ["/data"]
EXPOSE 8800
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fsS http://127.0.0.1:8800/healthz || exit 1
CMD ["vietdub", "serve", "--config", "/data/pipeline.toml", "--host", "0.0.0.0"]
