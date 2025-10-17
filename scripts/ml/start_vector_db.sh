#!/bin/bash
# Start Vector Database Services for ML Trading Optimization (Integrated Approach)

set -e

echo "Starting Vector Database Services for ML Trading Optimization..."

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo "Error: Python is not installed or not in PATH"
    echo "Please install Python 3.8+ to run the integrated services"
    exit 1
fi

# Check if required dependencies are installed
echo "Checking dependencies..."
python -c "import pandas, numpy, redis, requests, yaml" 2>/dev/null || {
    echo "Error: Required dependencies are not installed"
    echo "Please run: uv pip install -r config/requirements.txt"
    exit 1
}

# Start vector database services using integrated approach
echo "Starting integrated vector database services..."
echo "This will start Qdrant, Redis, and ML Model Server as managed services."
echo ""
echo "Service URLs will be:"
echo "  Qdrant Vector DB: http://localhost:6333"
echo "  Redis Cache: localhost:6380"
echo "  ML Model Server: http://localhost:8002"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Start the integrated services
python main.py vector-db
