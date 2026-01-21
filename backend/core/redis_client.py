import os
import redis
import time
from contextlib import contextmanager
from typing import Generator

def get_redis_client() -> redis.Redis:
    """
    Get a Redis client instance.
    Uses generic REDIS_URL environment variable.
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    # decode_responses=True ensures we get strings back, not bytes
    return redis.from_url(redis_url, socket_connect_timeout=5, decode_responses=True)

@contextmanager
def acquire_lock(lock_name: str, acquire_timeout: int = 10, lock_timeout: int = 60):
    """
    Distributed lock context manager using Redis.
    
    Args:
        lock_name: Unique identifier for the lock
        acquire_timeout: Max time to wait to acquire lock (seconds)
        lock_timeout: Max time to hold lock (seconds)
    """
    r = get_redis_client()
    lock_key = f"lock:{lock_name}"
    identifier = str(time.time())
    
    end_time = time.time() + acquire_timeout
    
    try:
        # Spin lock
        while time.time() < end_time:
            if r.set(lock_key, identifier, ex=lock_timeout, nx=True):
                yield True
                return
            time.sleep(0.1)
        
        # Failed to acquire
        yield False
        
    finally:
        # Release lock only if we own it
        try:
            current_value = r.get(lock_key)
            if current_value == identifier:
                r.delete(lock_key)
        except Exception as e:
            # Log error instead of silent failure
            print(f"Error releasing lock {lock_key}: {e}")
            pass
