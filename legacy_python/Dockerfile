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
COPY legacy_python/config/pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy source code, excluding unnecessary files
COPY legacy_python/app.py .
COPY legacy_python/src ./src

# Create data directories
RUN mkdir -p data/databases outputs logs

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "src.trade_bot.web.web_server:app", "--host", "0.0.0.0", "--port", "8000"]
