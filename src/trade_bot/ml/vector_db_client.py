"""Vector Database Client for ML feature storage and retrieval."""

import logging
import numpy as np
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import requests
import uuid

logger = logging.getLogger(__name__)


class VectorDBClient:
    """Client for Qdrant vector database operations."""
    
    def __init__(self, host: str = "localhost", port: int = 6333, 
                 collection_name: str = "trading_features"):
        """
        Initialize vector database client.
        
        Args:
            host: Qdrant server host
            port: Qdrant server port
            collection_name: Name of the collection to use
        """
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.base_url = f"http://{host}:{port}"
        
    def create_collection(self, vector_size: int) -> bool:
        """Create a new collection in Qdrant."""
        try:
            url = f"{self.base_url}/collections/{self.collection_name}"
            payload = {
                "vectors": {
                    "size": vector_size,
                    "distance": "Cosine"
                }
            }
            response = requests.put(url, json=payload)
            if response.status_code in [200, 201]:
                logger.info(f"Collection '{self.collection_name}' created with vector size {vector_size}")
                return True
            else:
                logger.error(f"Failed to create collection: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error creating collection: {e}")
            return False

    def delete_collection(self) -> bool:
        """Delete the collection."""
        try:
            url = f"{self.base_url}/collections/{self.collection_name}"
            response = requests.delete(url)
            if response.status_code == 200:
                logger.info(f"Collection '{self.collection_name}' deleted successfully")
                return True
            else:
                logger.error(f"Failed to delete collection: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
            return False
    
    def check_collection_exists(self) -> bool:
        """Check if collection exists."""
        try:
            url = f"{self.base_url}/collections/{self.collection_name}"
            response = requests.get(url)
            return response.status_code == 200
        except Exception:
            return False
    
    def upsert_vectors(self, vectors: List[np.ndarray], 
                      metadata: List[Dict[str, Any]]) -> bool:
        """Insert or update vectors in the collection."""
        try:
            if not self.check_collection_exists():
                # Create collection with appropriate vector size
                vector_size = len(vectors[0]) if vectors else 128
                if not self.create_collection(vector_size):
                    return False
            
            url = f"{self.base_url}/collections/{self.collection_name}/points"
            
            points = []
            for i, (vector, meta) in enumerate(zip(vectors, metadata)):
                point = {
                    "id": str(uuid.uuid4()),
                    "vector": vector.tolist(),
                    "payload": {
                        **meta,
                        "timestamp": datetime.now().isoformat(),
                        "vector_id": i
                    }
                }
                points.append(point)
            
            payload = {
                "points": points
            }
            
            response = requests.put(url, json=payload)
            
            if response.status_code in [200, 201]:
                logger.info(f"Upserted {len(vectors)} vectors successfully")
                return True
            else:
                logger.error(f"Failed to upsert vectors: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error upserting vectors: {e}")
            return False
    
    def search_similar_vectors(self, query_vector: np.ndarray, 
                              limit: int = 10, score_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Search for similar vectors."""
        try:
            if not self.check_collection_exists():
                logger.warning("Collection does not exist")
                return []
            
            url = f"{self.base_url}/collections/{self.collection_name}/points/search"
            
            payload = {
                "vector": query_vector.tolist(),
                "limit": limit,
                "score_threshold": score_threshold,
                "with_payload": True
            }
            
            response = requests.post(url, json=payload)
            
            if response.status_code == 200:
                results = response.json()
                return results.get("result", [])
            else:
                logger.error(f"Failed to search vectors: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching vectors: {e}")
            return []
    
    def get_vector_by_id(self, vector_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific vector by ID."""
        try:
            url = f"{self.base_url}/collections/{self.collection_name}/points/{vector_id}"
            
            response = requests.get(url)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get vector: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting vector: {e}")
            return None
    
    def delete_vector(self, vector_id: str) -> bool:
        """Delete a vector by ID."""
        try:
            url = f"{self.base_url}/collections/{self.collection_name}/points/{vector_id}"
            
            response = requests.delete(url)
            
            if response.status_code == 200:
                logger.info(f"Deleted vector {vector_id}")
                return True
            else:
                logger.error(f"Failed to delete vector: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting vector: {e}")
            return False
    
    def get_collection_info(self) -> Optional[Dict[str, Any]]:
        """Get collection information."""
        try:
            url = f"{self.base_url}/collections/{self.collection_name}"
            
            response = requests.get(url)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get collection info: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            return None
    
    def get_collection_stats(self) -> Optional[Dict[str, Any]]:
        """Get collection statistics."""
        try:
            url = f"{self.base_url}/collections/{self.collection_name}/points/count"
            
            response = requests.post(url, json={})
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get collection stats: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return None
    
    def batch_search(self, query_vectors: List[np.ndarray], 
                    limit: int = 10) -> List[List[Dict[str, Any]]]:
        """Perform batch search for multiple query vectors."""
        try:
            if not self.check_collection_exists():
                logger.warning("Collection does not exist")
                return []
            
            url = f"{self.base_url}/collections/{self.collection_name}/points/search/batch"
            
            searches = []
            for query_vector in query_vectors:
                searches.append({
                    "vector": query_vector.tolist(),
                    "limit": limit,
                    "with_payload": True
                })
            
            payload = {
                "searches": searches
            }
            
            response = requests.post(url, json=payload)
            
            if response.status_code == 200:
                results = response.json()
                return results.get("result", [])
            else:
                logger.error(f"Failed to batch search: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error batch searching: {e}")
            return []
    
    def filter_search(self, query_vector: np.ndarray, 
                     filter_conditions: Dict[str, Any],
                     limit: int = 10) -> List[Dict[str, Any]]:
        """Search with filter conditions."""
        try:
            if not self.check_collection_exists():
                logger.warning("Collection does not exist")
                return []
            
            url = f"{self.base_url}/collections/{self.collection_name}/points/search"
            
            must_conditions = []
            for key, value in filter_conditions.items():
                if isinstance(value, dict):
                    must_conditions.append({"key": key, "range": value})
                else:
                    must_conditions.append({"key": key, "match": {"value": value}})

            payload = {
                "vector": query_vector.tolist(),
                "limit": limit,
                "with_payload": True,
                "filter": {"must": must_conditions},
            }
            
            response = requests.post(url, json=payload)
            
            if response.status_code == 200:
                results = response.json()
                return results.get("result", [])
            else:
                logger.error(f"Failed to filter search: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error filter searching: {e}")
            return []
    
    def store_feature_vector(self, features: np.ndarray, 
                           metadata: Dict[str, Any]) -> Optional[str]:
        """Store a single feature vector with metadata."""
        try:
            vector_id = str(uuid.uuid4())
            
            success = self.upsert_vectors([features], [metadata])
            
            if success:
                return vector_id
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error storing feature vector: {e}")
            return None
    
    def find_similar_market_conditions(self, current_features: np.ndarray,
                                       symbol: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Find similar market conditions for a specific symbol."""
        filter_conditions = {"symbol": symbol}
        
        return self.filter_search(
            current_features, 
            filter_conditions, 
            limit
        )
    
    def get_historical_patterns(self, symbol: str, 
                               days_back: int = 30) -> List[Dict[str, Any]]:
        """Get historical patterns for a symbol using the scroll API."""
        try:
            if not self.check_collection_exists():
                logger.warning("Collection does not exist")
                return []

            # Calculate timestamp threshold
            threshold_time = datetime.now().timestamp() - (days_back * 24 * 3600)
            
            must_conditions = [
                {"key": "symbol", "match": {"value": symbol}},
                {"key": "timestamp", "range": {"gte": threshold_time}}
            ]

            url = f"{self.base_url}/collections/{self.collection_name}/points/scroll"
            payload = {
                "filter": {"must": must_conditions},
                "limit": 1000,  # Max limit for scrolling
                "with_payload": True,
                "with_vectors": True
            }
            
            response = requests.post(url, json=payload)
            
            if response.status_code == 200:
                results = response.json()
                return results.get("result", {}).get("points", [])
            else:
                logger.error(f"Failed to get historical patterns: {response.text}")
                return []
            
        except Exception as e:
            logger.error(f"Error getting historical patterns: {e}")
            return []
    
    def cleanup_old_vectors(self, days_back: int = 90) -> bool:
        """Clean up old vectors to manage storage."""
        try:
            threshold_time = datetime.now().timestamp() - (days_back * 24 * 3600)
            
            # This would require a more complex implementation
            # For now, we'll just log the intention
            logger.info(f"Cleanup of vectors older than {days_back} days requested")
            
            # In a real implementation, you would:
            # 1. Search for old vectors
            # 2. Delete them in batches
            # 3. Update collection statistics
            
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning up old vectors: {e}")
            return False
