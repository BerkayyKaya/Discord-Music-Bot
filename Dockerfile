# PYTHON
FROM python:3.12-slim

# UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# FFMPEG
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# WORK DIRECTORY
WORKDIR /app

# UV SETTINGS
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Required packages
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Bot codes
COPY . .

# Start commands
CMD ["uv", "run", "--no-sync", "python", "main.py"]
