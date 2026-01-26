# Dockerfile for Voice Bot Test Server
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# - portaudio19-dev: Required for PyAudio (microphone/speaker support)
# - build-essential: Required for building Python packages
# - git: Required for some Python packages that install from git
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (for better caching)
COPY pyproject.toml uv.lock ./

# Install Python dependencies using uv (system-wide installation)
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Initialize menu data (optional - can be skipped if data already exists)
# The server will handle missing menu data gracefully
RUN uv run python scripts/init_menu_data.py || echo "Menu data initialization skipped or failed"

# Expose the test server port
EXPOSE 8001

# Set environment variables for the test server
ENV SERVER_HOST=0.0.0.0
ENV SERVER_PORT=8001

# Run the test server
CMD ["uv", "run", "python", "test_main.py"]
