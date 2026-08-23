# Deployment Guide

This document provides a comprehensive guide to deploying the Advanced Trading Bot and its components. The system is designed for a flexible, container-based deployment using Docker and Docker Compose.

## Deployment Options

There are two primary ways to deploy the application:

1.  **Full-Stack Deployment**: Run the entire application, including the backend, frontend, ML services, and databases, using the main `docker-compose.yml` file.
2.  **Individual Component Deployment**: Run individual services (e.g., the frontend) independently using their component-specific `docker-compose.yml` files.

## Full-Stack Deployment (Recommended)

The root `docker-compose.yml` file is the primary method for deploying the entire application. It orchestrates the deployment of all services, ensuring they are configured to work together.

### Prerequisites

*   Docker
*   Docker Compose

### Instructions

1.  **Navigate to the project root directory.**
2.  **Run the following command:**

    ```bash
    docker-compose up -d
    ```

This command will build and run all the services defined in the `docker-compose.yml` file, including:

*   **backend**: The Python FastAPI application.
*   **frontend**: The Next.js frontend application.
*   **ml-server**: The ML model server.
*   **qdrant**: The Qdrant vector database.
*   **db**: The PostgreSQL database.
*   **redis**: The Redis cache.

### Host port coexistence

The database listens on `5432` inside the Compose network and is published on
host port `15432` by default. This avoids colliding with another local
PostgreSQL installation or Compose project already using host port `5432`.
The backend continues to use `db:5432`; only host-side clients need the
published port:

```bash
# Use a different free host port when needed.
POSTGRES_HOST_PORT=55432 podman-compose up --no-build

# Restore the conventional host port only when it is free.
POSTGRES_HOST_PORT=5432 podman-compose up --no-build
```

If `POSTGRES_HOST_PORT` is not set, Compose uses `15432`.

## Individual Component Deployment

The `frontend` and `src/trade_bot/ml` directories contain their own `docker-compose.yml` files, allowing them to be run independently. This is useful for development and testing.

### Frontend Deployment

To run the frontend application independently:

1.  **Navigate to the `frontend` directory.**
2.  **Run the following command:**

    ```bash
    docker-compose up -d
    ```

This will build and run the Next.js frontend, which will be accessible at `http://localhost:3000`.

### ML Service Deployment

The ML services can also be run independently. See `docs/VECTOR_DATABASE_SERVICE.md` for more details on the hybrid deployment options for the ML components.
