FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y procps curl && rm -rf /var/lib/apt/lists/*

# Set the working directory for installation
WORKDIR /app

# Copy requirements from the current legacy_python build context
COPY src/trade_bot/ml/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source code
COPY src /app/src

# Set PYTHONPATH to include src so trade_bot package can be found
ENV PYTHONPATH=/app/src

# Set working directory to /app so that relative paths like "data/models" resolve correctly
# (The docker-compose mounts data volume to /app/data)
WORKDIR /app

# Run the application using the full package path
# This ensures that relative imports inside the package work correctly
CMD ["uvicorn", "trade_bot.ml.server:app", "--host", "0.0.0.0", "--port", "8002"]
