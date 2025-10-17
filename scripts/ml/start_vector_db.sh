#!/bin/bash
# Start Vector Database Services for ML Trading Optimization

set -e

echo "Starting Vector Database Services for ML Trading Optimization..."

# Check if podman-compose is available
if ! command -v podman-compose &> /dev/null; then
    echo "Error: podman-compose is not installed or not in PATH"
    echo "Please install podman-compose or use docker-compose instead"
    exit 1
fi

# Check if the trade_network exists
if ! podman network exists trade_network; then
    echo "Creating trade_network..."
    podman network create trade_network
fi

# Start vector database services
echo "Starting Qdrant Vector Database, Redis Cache, and ML Model Server..."
podman-compose -f podman-compose-vector-db.yml up -d

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Check service health
echo "Checking service health..."

# Check Qdrant
if curl -f http://localhost:6333/health > /dev/null 2>&1; then
    echo "✅ Qdrant Vector Database is healthy"
else
    echo "❌ Qdrant Vector Database is not responding"
fi

# Check Redis
if redis-cli -p 6380 ping > /dev/null 2>&1; then
    echo "✅ Redis Cache is healthy"
else
    echo "❌ Redis Cache is not responding"
fi

# Check ML Model Server
if curl -f http://localhost:8002/health > /dev/null 2>&1; then
    echo "✅ ML Model Server is healthy"
else
    echo "❌ ML Model Server is not responding (may take longer to start)"
fi

echo ""
echo "Vector Database Services Status:"
podman-compose -f podman-compose-vector-db.yml ps

echo ""
echo "Service URLs:"
echo "  Qdrant Vector DB: http://localhost:6333"
echo "  Redis Cache: localhost:6380"
echo "  ML Model Server: http://localhost:8002"
echo "  Prometheus Monitor: http://localhost:9090"

echo ""
echo "To view logs:"
echo "  podman-compose -f podman-compose-vector-db.yml logs -f"

echo ""
echo "To stop services:"
echo "  podman-compose -f podman-compose-vector-db.yml down"
