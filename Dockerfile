# Backend Dockerfile for Trading Bot
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install uv for fast Python package management
RUN pip install --no-cache-dir uv

# Copy pyproject.toml and install dependencies
COPY config/pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy source code
COPY . .

# Create data directories
RUN mkdir -p data/databases outputs logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "app.py"]
