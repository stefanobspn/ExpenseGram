# Use a slim official python base image
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the uv binary from the official Astral uv image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy package definitions
COPY pyproject.toml uv.lock ./

# Install dependencies globally inside the container
RUN uv pip install --system --no-cache -r pyproject.toml

# Copy restructured application source code
COPY main.py ./
COPY src/ ./src/

# Create data directory for SQLite database storage
RUN mkdir -p /data

# Default environment variables
ENV DB_PATH=/data/expenses.db
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "main.py"]
