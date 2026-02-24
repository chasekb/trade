# Vector Database Service Integration

## Overview

The vector database services (Qdrant, Redis, and ML Model Server) are managed through a hybrid approach that supports both integrated local processes and container-based deployments, providing flexibility for development and production environments.

## Architecture

### Services
- **Qdrant Vector Database**: Port 6333 (HTTP), 6334 (gRPC) for feature vector storage
- **Redis Cache**: Port 6380 for vector caching and session management  
- **ML Model Server**: Port 8002 for model inference API

### Management
- **Service Manager**: `src/trade_bot/ml/vector_database_service.py`
- **Configuration**: `config/vector-db-config.yaml`
- **Integration**: Integrated into `main.py` with `vector-db` command

## Usage

### Starting Vector Database Services

#### Option 1: Integrated with Web Dashboard (Recommended)
```bash
python main.py web
```

This command will:
1. Start Qdrant vector database
2. Start Redis cache server
3. Start ML Model Server
4. Initialize vector database collections
5. Start the web dashboard with ML services integrated
6. Make ML services available for simulated and live trading

#### Option 2: Standalone Vector Database Services
```bash
python main.py vector-db
```

This command will:
1. Start Qdrant vector database
2. Start Redis cache server
3. Start ML Model Server
4. Initialize vector database collections
5. Display service URLs and status
6. Keep services running until Ctrl+C

### Service URLs

When services are running, you can access:
- **Qdrant HTTP API**: http://localhost:6333
- **Qdrant gRPC API**: localhost:6334
- **Redis Cache**: localhost:6380
- **ML Model Server**: http://localhost:8002

### Configuration

The services are configured via `config/vector-db-config.yaml`:

```yaml
qdrant:
  host: "localhost"
  port: 6333
  collection_name: "trading_features"
  # ... other settings

redis:
  host: "localhost"
  port: 6380
  # ... other settings

ml_server:
  host: "localhost"
  port: 8002
  # ... other settings
```

## Integration with Trading Bot

The vector database services are automatically managed by the `VectorDatabaseService` class:

```python
from src.trade_bot.ml.vector_database_service import get_vector_db_service

# Get service instance
service = get_vector_db_service()

# Start services
await service.start_services()

# Check status
status = service.get_service_status()

# Stop services
await service.stop_services()
```

## Health Monitoring

The service manager includes built-in health checks:
- Qdrant: HTTP health endpoint check
- Redis: Ping command check
- ML Model Server: HTTP health endpoint check

## Graceful Shutdown

Services support graceful shutdown with proper cleanup:
- ML Model Server stops first
- Redis cache stops second
- Qdrant vector database stops last

## Migration from Container Approach

The system can be run using either an integrated service manager or a container-based approach with podman-compose.

### Integrated Service Management (Recommended for Local Development)

The `main.py` script can manage the services directly:
```bash
python main.py vector-db
```
This command will check for running services and start them as local processes if they are not found.

### Container-Based Deployment (Recommended for Production)

For a more robust and isolated environment, the services can be run using podman-compose:
```bash
podman-compose -f podman-compose-vector-db.yml up -d
```
This will build and run the ML server in a container, as defined in `src/trade_bot/ml/Dockerfile`.

**Note:** The `src/trade_bot/ml/Dockerfile` and `podman-compose-vector-db.yml` files are part of the container-based deployment option and should be used for production or isolated development environments.

## Benefits

1. **Simplified Deployment**: No need for container management
2. **Integrated Logging**: All services use the same logging configuration
3. **Health Monitoring**: Built-in service health checks
4. **Graceful Shutdown**: Proper cleanup on exit
5. **Configuration Management**: Centralized configuration via YAML
6. **Process Management**: Automatic process lifecycle management

## Troubleshooting

### Services Won't Start
- Check if ports 6333, 6334, 6380, and 8002 are available
- Verify Qdrant and Redis are installed on the system
- Check configuration file syntax

### Health Check Failures
- Ensure all services are running
- Check network connectivity
- Verify service configurations

### Memory Issues
- Adjust memory settings in `config/vector-db-config.yaml`
- Monitor system resources
- Consider reducing batch sizes or cache limits
