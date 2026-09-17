# Container image for the XPENG dashcam viewer.
#
# Build from the project root:
#     docker compose build          # or: docker build -t xpeng-dashcam .
#
# See the "Docker" section in README.md for how to run it and how to build the
# index. The image only *serves* the viewer; indexing stays an explicit step
# (scan.py -> thumbs.py -> ritten.py), exactly as with the venv workflow.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_DIR=/app \
    WEB_PORT=8965

# ffmpeg is required for thumbnails and for reading the speed bar.
# tzdata lets the configured timezone resolve inside the container.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg tzdata \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, so application edits do not invalidate the pip layer.
# The app is imported further down, which pulls in every third-party module it
# needs, so only the declared direct dependencies are installed.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application source. demo/ is in .dockerignore because its 27 MB of sample
# footage is not needed to run the viewer.
COPY . .

# Portability patch: speed.py hardcodes a macOS-only ffmpeg flag, which makes
# the speed/distance feature fail on Linux. The patch is idempotent, so this
# keeps working if upstream applies it directly. See patches/ for the detail.
#
# `import app` then pulls in every other module, so a broken dependency or a
# patch that did not apply fails the build instead of shipping a silent runtime
# error.
RUN python3 patches/0001-ffmpeg-hwaccel-portable.py speed.py \
 && python3 -c "import app"

# Index and thumbnails are written here. Mount them from the host so rebuilding
# the image never costs a re-index (see docker-compose.yml).
RUN mkdir -p data thumbs

# Run as a normal user, with the identity supplied at build time:
#     docker build --build-arg UID=$(id -u) --build-arg GID=$(id -g) .
# Compose passes these through, so the index, thumbnails and the settings
# back-up come out owned by you instead of by root.
#
# /app itself must be writable: save_config() writes config.json.bak next to
# config.json, which for a bind-mounted config lands in this directory, and the
# settings page would otherwise fail with a 500.
ARG UID=1000
ARG GID=1000
RUN groupadd -g "$GID" app 2>/dev/null || true \
 && useradd -u "$UID" -g "$GID" -M -s /usr/sbin/nologin app 2>/dev/null || true \
 && chown -R "$UID:$GID" /app
USER $UID:$GID

EXPOSE 8965

# Generous start period: the first thumbnail sweep on a large archive is slow.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8965/healthz', timeout=4).status==200 else 1)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8965"]
