# backend/Dockerfile
#
# We use Python 3.12 slim (small base image — no GUI tools).
# "slim" means fewer pre-installed packages → smaller image.
FROM python:3.12-slim

WORKDIR /app

# InsightFace uses OpenCV internally. Even the "headless" version needs
# these two system libraries for image decoding. We install them here.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy the uv binary directly from its official Docker image.
# This is faster than "pip install uv" and keeps the image small.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency definition first — Docker caches this layer separately.
# If only source code changes (not pyproject.toml), this expensive install
# step is skipped on the next build. This is called "layer caching."
COPY pyproject.toml uv.lock ./

# Local full stack builds with INSTALL_CLOUD=true; the hosted lite image
# leaves it false and installs only the JSON + numpy + psycopg runtime.
ARG INSTALL_CLOUD=false
RUN if [ "$INSTALL_CLOUD" = "true" ]; then uv sync --extra cloud; else uv sync --no-dev; fi

# Now copy the actual source code
COPY . .

EXPOSE 8000

# --host 0.0.0.0 makes uvicorn listen on all interfaces inside the container.
# Without this it only listens on 127.0.0.1, which is unreachable from outside.
# `${PORT:-8000}` honours the port injected by hosting platforms like Render.
CMD uv run uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
