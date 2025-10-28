"""Vector Database Service Manager for integrated ML services."""

import logging
import asyncio
import subprocess
import time
import requests
import redis
from typing import Dict, Any, Optional, List
from pathlib import Path
import yaml
import os
import signal
import threading
from contextlib import asynccontextmanager

from .vector_db_client import VectorDBClient

logger = logging.getLogger(__name__)


class VectorDatabaseService:
    """Manages Qdrant, Redis, and ML Model Server as integrated services."""
    
    def __init__(self, config_path: str = "config/vector-db-config.yaml"):
        """
        Initialize vector database service manager.
        
        Args:
            config_path: Path to vector database configuration
        """
        self.config_path = config_path
        self.config = self._load_config()
        
        # Service processes
        self.qdrant_process = None
        self.redis_process = None
        self.ml_server_process = None
        
        # Service status
        self.services_running = False
        self.startup_timeout = 60  # seconds
        
        # Vector DB client
        self.vector_db_client = VectorDBClient(
            host=self.config['qdrant']['host'],
            port=self.config['qdrant']['port'],
            collection_name=self.config['qdrant']['collection_name']
        )
        
        # Redis client
        self.redis_client = None
        
    def _load_config(self) -> Dict[str, Any]:
        """Load vector database configuration."""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            # Return default config
            return {
                'qdrant': {
                    'host': 'localhost',
                    'port': 6333,
                    'collection_name': 'trading_features'
                },
                'redis': {
                    'host': 'localhost',
                    'port': 6380
                },
                'ml_server': {
                    'host': 'localhost',
                    'port': 8002
                }
            }
    
    async def start_services(self) -> bool:
        """Start all vector database services."""
        try:
            logger.info("Starting vector database services...")
            
            # Start Qdrant
            if not await self._start_qdrant():
                logger.error("Failed to start Qdrant")
                return False
            
            # Start Redis
            if not await self._start_redis():
                logger.error("Failed to start Redis")
                await self.stop_services()
                return False
            
            # Start ML Model Server
            if not await self._start_ml_server():
                logger.error("Failed to start ML Model Server")
                await self.stop_services()
                return False
            
            # Wait for services to be ready
            if not await self._wait_for_services():
                logger.error("Services failed to start within timeout")
                await self.stop_services()
                return False
            
            self.services_running = True
            logger.info("✅ All vector database services started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error starting vector database services: {e}")
            await self.stop_services()
            return False
    
    async def _start_qdrant(self) -> bool:
        """Check if Qdrant vector database is available."""
        try:
            logger.info("Checking Qdrant vector database...")

            # Check if Qdrant container is running via podman
            try:
                result = subprocess.run([
                    "podman", "ps", "--filter", "name=qdrant",
                    "--format", "{{.Names}}"
                ], capture_output=True, text=True, timeout=10)

                if "qdrant" in result.stdout:
                    logger.info("Qdrant container is already running via podman")
                    self.qdrant_process = "podman_container"  # Mark as external process
                    return True
                else:
                    logger.warning("No Qdrant container found, will attempt to start local Qdrant")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                logger.warning("Podman not available or failed, will attempt to start local Qdrant")

            # Fallback: Try to start local Qdrant (legacy behavior)
            # Create data directories
            storage_path = Path(self.config['qdrant']['storage_path'])
            wal_path = Path(self.config['qdrant']['wal_path'])
            storage_path.mkdir(parents=True, exist_ok=True)
            wal_path.mkdir(parents=True, exist_ok=True)

            # Start Qdrant process
            cmd = [
                "qdrant",
                "--config-path", self.config_path,
                "--storage-path", str(storage_path),
                "--wal-path", str(wal_path)
            ]

            self.qdrant_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )

            logger.info(f"Qdrant started with PID: {self.qdrant_process.pid}")
            return True

        except Exception as e:
            logger.error(f"Error starting Qdrant: {e}")
            return False
    
    async def _start_redis(self) -> bool:
        """Check if Redis cache server is available."""
        try:
            logger.info("Checking Redis cache server...")

            # Check if Redis container is running via podman
            try:
                result = subprocess.run([
                    "podman", "ps", "--filter", "name=redis",
                    "--format", "{{.Names}}"
                ], capture_output=True, text=True, timeout=10)

                if "redis" in result.stdout:
                    logger.info("Redis container is already running via podman")
                    self.redis_process = "podman_container"  # Mark as external process
                    return True
                else:
                    logger.warning("No Redis container found, will attempt to start local Redis")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                logger.warning("Podman not available or failed, will attempt to start local Redis")

            # Fallback: Try to start local Redis (legacy behavior)
            logger.info("Starting Redis cache server...")

            # Start Redis process
            cmd = [
                "redis-server",
                "--port", str(self.config['redis']['port']),
                "--maxmemory", self.config['redis']['max_memory'],
                "--maxmemory-policy", self.config['redis']['max_memory_policy'],
                "--save", self.config['redis']['save_interval'],
                "--appendonly", "yes"
            ]

            self.redis_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )

            logger.info(f"Redis started with PID: {self.redis_process.pid}")
            return True

        except Exception as e:
            logger.error(f"Error starting Redis: {e}")
            return False
    
    async def _start_ml_server(self) -> bool:
        """Start ML Model Server."""
        try:
            logger.info("Starting ML Model Server...")
            
            # Set environment variables
            env = os.environ.copy()
            env.update({
                'ML_SERVER_HOST': self.config['ml_server']['host'],
                'ML_SERVER_PORT': str(self.config['ml_server']['port']),
                'QDRANT_HOST': self.config['qdrant']['host'],
                'QDRANT_PORT': str(self.config['qdrant']['port']),
                'REDIS_HOST': self.config['redis']['host'],
                'REDIS_PORT': str(self.config['redis']['port']),
                'DB_PATH': 'data/databases/trading_cache.db',
                'MODELS_DIR': 'data/models'
            })
            
            # Start ML server process
            cmd = [
                "python", "-m", "src.trade_bot.ml.server"
            ]
            
            self.ml_server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            
            logger.info(f"ML Model Server started with PID: {self.ml_server_process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting ML Model Server: {e}")
            return False
    
    async def _wait_for_services(self) -> bool:
        """Wait for all services to be ready."""
        logger.info("Waiting for services to be ready...")
        
        start_time = time.time()
        
        while time.time() - start_time < self.startup_timeout:
            if await self._check_all_services():
                logger.info("All services are ready")
                return True
            
            await asyncio.sleep(2)
        
        logger.error("Services failed to start within timeout")
        return False
    
    async def _check_all_services(self) -> bool:
        """Check if all services are responding."""
        try:
            # Check Qdrant
            if not await self._check_qdrant():
                return False
            
            # Check Redis
            if not await self._check_redis():
                return False
            
            # Check ML Model Server
            if not await self._check_ml_server():
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking services: {e}")
            return False
    
    async def _check_qdrant(self) -> bool:
        """Check if Qdrant is responding."""
        try:
            response = requests.get(
                f"http://{self.config['qdrant']['host']}:{self.config['qdrant']['port']}/healthz",
                timeout=5
            )
            return response.status_code == 200 and "healthz check passed" in response.text
        except Exception:
            return False
    
    async def _check_redis(self) -> bool:
        """Check if Redis is responding."""
        try:
            if self.redis_client is None:
                self.redis_client = redis.Redis(
                    host=self.config['redis']['host'],
                    port=self.config['redis']['port'],
                    decode_responses=True
                )
            
            return self.redis_client.ping()
        except Exception:
            return False
    
    async def _check_ml_server(self) -> bool:
        """Check if ML Model Server is responding."""
        try:
            response = requests.get(
                f"http://{self.config['ml_server']['host']}:{self.config['ml_server']['port']}/health",
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def stop_services(self) -> None:
        """Stop all vector database services."""
        logger.info("Stopping vector database services...")

        # Stop ML Model Server
        if self.ml_server_process:
            try:
                if os.name != 'nt':
                    os.killpg(os.getpgid(self.ml_server_process.pid), signal.SIGTERM)
                else:
                    self.ml_server_process.terminate()
                self.ml_server_process.wait(timeout=10)
                logger.info("ML Model Server stopped")
            except Exception as e:
                logger.error(f"Error stopping ML Model Server: {e}")
            finally:
                self.ml_server_process = None

        # Stop Redis (only if it's a local process, not podman container)
        if self.redis_process and isinstance(self.redis_process, subprocess.Popen):
            try:
                if os.name != 'nt':
                    os.killpg(os.getpgid(self.redis_process.pid), signal.SIGTERM)
                else:
                    self.redis_process.terminate()
                self.redis_process.wait(timeout=10)
                logger.info("Redis stopped")
            except Exception as e:
                logger.error(f"Error stopping Redis: {e}")
            finally:
                self.redis_process = None
        elif self.redis_process == "podman_container":
            logger.info("Redis podman container will remain running (externally managed)")

        # Stop Qdrant (only if it's a local process, not podman container)
        if self.qdrant_process and isinstance(self.qdrant_process, subprocess.Popen):
            try:
                if os.name != 'nt':
                    os.killpg(os.getpgid(self.qdrant_process.pid), signal.SIGTERM)
                else:
                    self.qdrant_process.terminate()
                self.qdrant_process.wait(timeout=10)
                logger.info("Qdrant stopped")
            except Exception as e:
                logger.error(f"Error stopping Qdrant: {e}")
            finally:
                self.qdrant_process = None
        elif self.qdrant_process == "podman_container":
            logger.info("Qdrant podman container will remain running (externally managed)")

        self.services_running = False
        logger.info("All vector database services stopped")
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get status of all services."""
        def _get_process_info(process):
            """Helper to get process info safely."""
            if isinstance(process, subprocess.Popen):
                return {
                    'running': process.poll() is None,
                    'pid': process.pid
                }
            elif isinstance(process, str):
                # External container process
                return {
                    'running': True,  # Assume running if tracked
                    'pid': None
                }
            else:
                return {
                    'running': False,
                    'pid': None
                }

        return {
            'services_running': self.services_running,
            'qdrant': _get_process_info(self.qdrant_process),
            'redis': _get_process_info(self.redis_process),
            'ml_server': _get_process_info(self.ml_server_process)
        }
    
    def get_service_urls(self) -> Dict[str, str]:
        """Get URLs for all services."""
        return {
            'qdrant_http': f"http://{self.config['qdrant']['host']}:{self.config['qdrant']['port']}",
            'qdrant_grpc': f"{self.config['qdrant']['host']}:{self.config['qdrant']['grpc_port']}",
            'redis': f"{self.config['redis']['host']}:{self.config['redis']['port']}",
            'ml_server': f"http://{self.config['ml_server']['host']}:{self.config['ml_server']['port']}"
        }
    
    async def initialize_vector_database(self) -> bool:
        """Initialize vector database collections."""
        try:
            if not self.services_running:
                logger.error("Services not running, cannot initialize vector database")
                return False

            # Check if collection exists, create it if it doesn't
            if not self.vector_db_client.check_collection_exists():
                logger.info("Creating trading_features collection...")
                if not self.vector_db_client.create_collection():
                    logger.error("Failed to create vector database collection")
                    return False
                logger.info("Vector database collection created successfully")
            else:
                logger.info("Vector database collection already exists")

            return True

        except Exception as e:
            logger.error(f"Error initializing vector database: {e}")
            return False
    
    @asynccontextmanager
    async def managed_services(self):
        """Context manager for vector database services."""
        try:
            if await self.start_services():
                yield self
            else:
                raise RuntimeError("Failed to start vector database services")
        finally:
            await self.stop_services()


# Global service instance
_vector_db_service = None


def get_vector_db_service() -> VectorDatabaseService:
    """Get the global vector database service instance."""
    global _vector_db_service
    if _vector_db_service is None:
        _vector_db_service = VectorDatabaseService()
    return _vector_db_service


async def start_vector_db_services() -> bool:
    """Start vector database services."""
    service = get_vector_db_service()
    return await service.start_services()


async def stop_vector_db_services() -> None:
    """Stop vector database services."""
    service = get_vector_db_service()
    await service.stop_services()


def get_vector_db_status() -> Dict[str, Any]:
    """Get vector database service status."""
    service = get_vector_db_service()
    return service.get_service_status()
