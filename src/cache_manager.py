import logging
import json
import pickle
import hashlib
from typing import Any, Optional, Dict, List, Union
from datetime import datetime, timedelta
from pathlib import Path
import redis
from functools import wraps
import time

from config import settings

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self, use_redis: bool = True):
        self.use_redis = use_redis
        self.redis_client = None
        self.file_cache_dir = Path("data/cache")
        self.file_cache_dir.mkdir(parents=True, exist_ok=True)
        
        if use_redis:
            try:
                self.redis_client = redis.from_url(settings.redis_url)
                self.redis_client.ping()
                logger.info("Connected to Redis cache")
            except Exception as e:
                logger.warning(f"Could not connect to Redis: {e}. Falling back to file cache.")
                self.use_redis = False
                self.redis_client = None
    
    def _generate_cache_key(self, prefix: str, params: Dict[str, Any]) -> str:
        # Create a stable hash from parameters
        param_str = json.dumps(params, sort_keys=True)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
        return f"{prefix}:{param_hash}"
    
    def _serialize_data(self, data: Any) -> bytes:
        return pickle.dumps(data)
    
    def _deserialize_data(self, data: bytes) -> Any:
        return pickle.loads(data)
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        ttl = ttl or settings.cache_ttl
        
        try:
            serialized_data = self._serialize_data(value)
            
            if self.use_redis and self.redis_client:
                return self.redis_client.setex(key, ttl, serialized_data)
            else:
                # File-based cache
                cache_file = self.file_cache_dir / f"{key}.cache"
                cache_data = {
                    'data': serialized_data,
                    'expires_at': (datetime.utcnow() + timedelta(seconds=ttl)).isoformat(),
                    'created_at': datetime.utcnow().isoformat()
                }
                
                with open(cache_file, 'wb') as f:
                    pickle.dump(cache_data, f)
                
                return True
                
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        try:
            if self.use_redis and self.redis_client:
                cached_data = self.redis_client.get(key)
                if cached_data:
                    return self._deserialize_data(cached_data)
            else:
                # File-based cache
                cache_file = self.file_cache_dir / f"{key}.cache"
                if cache_file.exists():
                    with open(cache_file, 'rb') as f:
                        cache_data = pickle.load(f)
                    
                    expires_at = datetime.fromisoformat(cache_data['expires_at'])
                    if datetime.utcnow() < expires_at:
                        return self._deserialize_data(cache_data['data'])
                    else:
                        # Expired, remove file
                        cache_file.unlink()
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        try:
            if self.use_redis and self.redis_client:
                return bool(self.redis_client.delete(key))
            else:
                cache_file = self.file_cache_dir / f"{key}.cache"
                if cache_file.exists():
                    cache_file.unlink()
                    return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    def clear_all(self) -> bool:
        try:
            if self.use_redis and self.redis_client:
                return self.redis_client.flushall()
            else:
                for cache_file in self.file_cache_dir.glob("*.cache"):
                    cache_file.unlink()
                return True
                
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        stats = {
            'backend': 'redis' if self.use_redis and self.redis_client else 'file',
            'total_keys': 0,
            'total_size_mb': 0,
            'oldest_entry': None,
            'newest_entry': None
        }
        
        try:
            if self.use_redis and self.redis_client:
                info = self.redis_client.info()
                stats['total_keys'] = info.get('db0', {}).get('keys', 0)
                stats['total_size_mb'] = info.get('used_memory', 0) / (1024 * 1024)
            else:
                cache_files = list(self.file_cache_dir.glob("*.cache"))
                stats['total_keys'] = len(cache_files)
                
                total_size = sum(f.stat().st_size for f in cache_files)
                stats['total_size_mb'] = total_size / (1024 * 1024)
                
                if cache_files:
                    timestamps = [f.stat().st_mtime for f in cache_files]
                    stats['oldest_entry'] = datetime.fromtimestamp(min(timestamps)).isoformat()
                    stats['newest_entry'] = datetime.fromtimestamp(max(timestamps)).isoformat()
        
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
        
        return stats

# Global cache manager instance
cache_manager = CacheManager()

def cached(prefix: str, ttl: int = None, key_params: List[str] = None):
    """
    Decorator for caching function results
    
    Args:
        prefix: Cache key prefix
        ttl: Time to live in seconds
        key_params: List of parameter names to include in cache key
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from specified parameters
            if key_params:
                cache_params = {}
                
                # Get function parameter names
                import inspect
                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())
                
                # Extract specified parameters
                for i, param_name in enumerate(param_names):
                    if param_name in key_params:
                        if i < len(args):
                            cache_params[param_name] = args[i]
                        elif param_name in kwargs:
                            cache_params[param_name] = kwargs[param_name]
            else:
                # Use all parameters
                import inspect
                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())
                
                cache_params = {}
                for i, param_name in enumerate(param_names):
                    if i < len(args):
                        cache_params[param_name] = args[i]
                    elif param_name in kwargs:
                        cache_params[param_name] = kwargs[param_name]
            
            # Generate cache key
            cache_key = cache_manager._generate_cache_key(prefix, cache_params)
            
            # Try to get from cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__} with key {cache_key}")
                return cached_result
            
            # Execute function and cache result
            logger.debug(f"Cache miss for {func.__name__} with key {cache_key}")
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Cache the result
            cache_manager.set(cache_key, result, ttl)
            logger.debug(f"Cached result for {func.__name__} (executed in {execution_time:.2f}s)")
            
            return result
        
        return wrapper
    return decorator

class RepositoryCache:
    """Specialized cache for repository data"""
    
    def __init__(self, cache_manager: CacheManager = None):
        self.cache = cache_manager or cache_manager
    
    def cache_repository_details(self, repo_id: int, repo_data: Dict[str, Any], ttl: int = 7200):
        """Cache detailed repository information"""
        key = f"repo_details:{repo_id}"
        return self.cache.set(key, repo_data, ttl)
    
    def get_repository_details(self, repo_id: int) -> Optional[Dict[str, Any]]:
        """Get cached repository details"""
        key = f"repo_details:{repo_id}"
        return self.cache.get(key)
    
    def cache_repository_metrics(self, repo_id: int, metrics: Dict[str, Any], ttl: int = 3600):
        """Cache calculated metrics for a repository"""
        key = f"repo_metrics:{repo_id}"
        return self.cache.set(key, metrics, ttl)
    
    def get_repository_metrics(self, repo_id: int) -> Optional[Dict[str, Any]]:
        """Get cached repository metrics"""
        key = f"repo_metrics:{repo_id}"
        return self.cache.get(key)
    
    def cache_search_results(self, query_hash: str, results: List[Dict[str, Any]], ttl: int = 1800):
        """Cache GitHub search results"""
        key = f"search_results:{query_hash}"
        return self.cache.set(key, results, ttl)
    
    def get_search_results(self, query_hash: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached search results"""
        key = f"search_results:{query_hash}"
        return self.cache.get(key)
    
    def cache_embeddings(self, repo_id: int, embeddings: List[float], ttl: int = 86400):
        """Cache README embeddings (24 hour TTL)"""
        key = f"embeddings:{repo_id}"
        return self.cache.set(key, embeddings, ttl)
    
    def get_embeddings(self, repo_id: int) -> Optional[List[float]]:
        """Get cached embeddings"""
        key = f"embeddings:{repo_id}"
        return self.cache.get(key)
    
    def cache_cluster_assignments(self, clustering_hash: str, assignments: Dict[int, int], ttl: int = 7200):
        """Cache clustering results"""
        key = f"clusters:{clustering_hash}"
        return self.cache.set(key, assignments, ttl)
    
    def get_cluster_assignments(self, clustering_hash: str) -> Optional[Dict[int, int]]:
        """Get cached cluster assignments"""
        key = f"clusters:{clustering_hash}"
        return self.cache.get(key)
    
    def invalidate_repository(self, repo_id: int):
        """Invalidate all cached data for a repository"""
        keys_to_delete = [
            f"repo_details:{repo_id}",
            f"repo_metrics:{repo_id}",
            f"embeddings:{repo_id}"
        ]
        
        for key in keys_to_delete:
            self.cache.delete(key)
    
    def cleanup_expired_entries(self):
        """Clean up expired cache entries (file cache only)"""
        if not self.cache.use_redis:
            now = datetime.utcnow()
            cache_files = list(self.cache.file_cache_dir.glob("*.cache"))
            
            cleaned_count = 0
            for cache_file in cache_files:
                try:
                    with open(cache_file, 'rb') as f:
                        cache_data = pickle.load(f)
                    
                    expires_at = datetime.fromisoformat(cache_data['expires_at'])
                    if now >= expires_at:
                        cache_file.unlink()
                        cleaned_count += 1
                        
                except Exception as e:
                    logger.warning(f"Error checking cache file {cache_file}: {e}")
                    # Remove corrupted cache files
                    cache_file.unlink()
                    cleaned_count += 1
            
            logger.info(f"Cleaned up {cleaned_count} expired cache entries")

# Global specialized cache instances
repo_cache = RepositoryCache(cache_manager)