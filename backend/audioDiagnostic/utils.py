import os
import redis
import logging

logger = logging.getLogger(__name__)

def get_redis_connection():
    """
    Get Redis connection with appropriate host based on environment.
    
    When running inside Docker (Celery worker), use 'redis' as host.
    When running outside Docker (Django dev server), use 'localhost' as host.
    """
    # Check if we're running inside Docker
    is_docker = os.path.exists('/.dockerenv') or os.environ.get('CONTAINER_ENV') == 'true'
    
    if is_docker:
        # Running inside Docker container - use service name
        redis_host = 'redis'
        logger.info("Detected Docker environment - using redis:6379")
    else:
        # Running on host machine - use localhost
        redis_host = 'localhost'
        logger.info("Detected host environment - using localhost:6379")
    
    try:
        r = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)
        # Test connection
        r.ping()
        logger.info(f"Successfully connected to Redis at {redis_host}:6379")
        return r
    except Exception as e:
        logger.error(f"Failed to connect to Redis at {redis_host}:6379: {e}")
        # Try fallback
        fallback_host = 'localhost' if is_docker else 'redis'
        try:
            r = redis.Redis(host=fallback_host, port=6379, db=0, decode_responses=True)
            r.ping()
            logger.info(f"Successfully connected to Redis fallback at {fallback_host}:6379")
            return r
        except Exception as fallback_e:
            logger.error(f"Fallback Redis connection also failed at {fallback_host}:6379: {fallback_e}")
            raise Exception(f"Could not connect to Redis on either {redis_host} or {fallback_host}")

def get_redis_host():
    """
    Get the appropriate Redis host string for configuration.
    """
    is_docker = os.path.exists('/.dockerenv') or os.environ.get('CONTAINER_ENV') == 'true'
    return 'redis' if is_docker else 'localhost'