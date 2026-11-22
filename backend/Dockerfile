FROM python:3.13.15-slim-trixie

# Install tools (Debian uses apt)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      bash \
      curl \
      htop && \
    rm -rf /var/lib/apt/lists/*

# Copy the uv binary from the official image (the installer script puts it in
# a directory that is not on PATH).
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

WORKDIR /home
ENV HOME=/home

# Copy the shared manifest + lockfile first for better layer caching.
COPY pyproject.toml uv.lock /home/
RUN uv sync

COPY backend /home/backend

ENV PATH="/home/.venv/bin:${PATH}"
ENV PYTHONPATH=/home/backend/src

WORKDIR /home/backend
CMD ["bash"]
