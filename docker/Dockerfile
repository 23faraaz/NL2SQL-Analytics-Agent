# =============================================================================
# STAGE 1: builder
#
# Multi-stage build, with an honest caveat: psycopg2-binary, streamlit, and
# google-genai are all precompiled wheels, so there's no compiler toolchain to
# strip out of the final image the way there would be for a package that
# needs gcc/postgres-dev headers. The real benefit here is smaller: the
# builder's pip cache and any transient files never make it into the final
# image. Still worth doing - it's the correct pattern, and it means adding
# a future dependency that DOES need compilation (e.g. a C extension) won't
# require restructuring this file.
# =============================================================================
FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS builder

WORKDIR /app

COPY requirements.txt .

# Install into an isolated venv rather than system site-packages, so the
# final stage can copy exactly this directory and nothing else - no pip
# cache, no apt lists, no build leftovers.
RUN python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --require-hashes -r requirements.txt


# =============================================================================
# STAGE 2: runtime
# =============================================================================
FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS runtime

# OCI standard labels - the metadata a registry/scanner reads to know what
# this image is, without needing to inspect layers.
LABEL org.opencontainers.image.title="nl2sql-agent" \
      org.opencontainers.image.description="NL2SQL analytics agent - Streamlit + Gemini + Postgres" \
      org.opencontainers.image.source="https://github.com/23faraaz/NL2SQL-Analytics-Agent" \
      org.opencontainers.image.licenses="MIT"

# tini provides proper PID 1 and signal handling. The health check uses
# Python's standard library so the runtime does not need curl and its
# additional OS packages.
RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

# Dedicated non-root user with no login shell and no home directory
# creation side effects - a real service account, not a workaround.
RUN groupadd --system appuser && \
    useradd --system \
        --gid appuser \
        --home-dir /app \
        --shell /usr/sbin/nologin \
        appuser

WORKDIR /app

# Copy the pre-built venv from the builder stage - none of pip's cache or
# build metadata comes along with it.
COPY --from=builder /opt/venv /opt/venv

COPY app/ ./app/
COPY .streamlit/config.toml ./.streamlit/config.toml

# PATH: ensures the copied virtual environment is used.
#
# PYTHONPATH: tells Python that /app is the project root so imports like
# `from app import db` resolve correctly.
#
# PYTHONUNBUFFERED: without this, stdout is block-buffered when Python
# isn't attached to a terminal (i.e. always, in a container), so logs can
# sit in the buffer instead of streaming to `docker logs` / CloudWatch in
# real time. This matters for the structured logging you actually rely on.
#
# STREAMLIT_BROWSER_GATHER_USAGE_STATS=false: stops Streamlit's telemetry
# ping, which otherwise tries to write to $HOME/.streamlit on every start -
# relevant once this runs with a read-only root filesystem (see below).
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    HOME=/app

# Pre-create the one directory Streamlit insists on writing to (its config/
# credentials file) and hand ownership to appuser BEFORE switching users -
# chown as root, then drop privileges. Doing this now, rather than at
# container start, is what makes the image work under a read-only root
# filesystem: this directory already exists with correct permissions, so
# nothing needs to be created at runtime except within it.
RUN mkdir -p /app/.streamlit && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=4)"

# WHY tini AS ENTRYPOINT:
# The original ask was right to flag signal handling, but the actual gap
# isn't shell-form vs exec-form CMD (already exec-form below, which forwards
# signals correctly in general). The specific problem is that Streamlit
# itself is known to handle SIGTERM poorly inside containers - it can hang
# on shutdown instead of exiting cleanly, which means ECS has to wait out
# the full stop timeout and SIGKILL it on every deploy. tini as PID 1 reaps
# zombie processes correctly AND forwards signals in a way that forces the
# shutdown through, so `docker stop` / ECS task stops are fast and clean.
ENTRYPOINT ["tini", "--"]

CMD ["python", "-m", "streamlit", "run", "app/main.py", "--server.address=0.0.0.0", "--server.port=8501"]

# =============================================================================
# READ-ONLY ROOT FILESYSTEM - what this image needs to run that way:
#
# This image is compatible with `docker run --read-only` / ECS
# `readonlyRootFilesystem: true`, PROVIDED you mount writable tmpfs volumes
# at these two paths (Streamlit and Python both need somewhere to write at
# runtime even though the app itself is stateless):
#   - /tmp                (Python/Streamlit temp files)
#   - /app/.streamlit     (Streamlit's runtime state - already chowned above)
#
# Docker:
#   docker run --read-only --tmpfs /tmp --tmpfs /app/.streamlit ...
#
# ECS task definition:
#   "readonlyRootFilesystem": true, plus a "tmpfs" block for /tmp (ECS
#   doesn't support arbitrary tmpfs mounts on Fargate outside /tmp as of
#   this writing - check current ECS docs before relying on a second tmpfs
#   mount for /app/.streamlit in Fargate specifically).
# =============================================================================
