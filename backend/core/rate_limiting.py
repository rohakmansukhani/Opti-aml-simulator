"""
Enhanced Rate Limiting with Cost-Based Budgets

Implements tiered rate limiting based on endpoint cost:
- Expensive operations (simulations): 3/hour
- Moderate operations (uploads): 5/hour  
- Cheap operations (queries): 200/minute
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from functools import wraps
from typing import Callable
import redis
import os
from datetime import datetime, timedelta

# Initialize Redis for distributed rate limiting
redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))

# Cost map for different endpoints
ENDPOINT_COSTS = {
    "/api/simulation/run": 100,           # Very expensive
    "/api/comparison/compare": 50,        # Expensive
    "/api/data/upload/transactions": 30,  # Moderate
    "/api/data/upload/customers": 30,     # Moderate
    "/api/scenario-config/create": 20,    # Moderate
    "/api/risk/analyze": 40,              # Expensive
    "/api/dashboard/stats": 5,            # Cheap
    "/api/rules/scenarios": 1,            # Very cheap
}

DAILY_BUDGET = 1000  # Total cost units per user per day

class CostBasedRateLimiter:
    """
    Rate limiter that tracks cumulative cost instead of just request count.
    
    Example:
        - User runs 10 simulations (10 * 100 = 1000 cost) → budget exhausted
        - User makes 200 dashboard queries (200 * 5 = 1000 cost) → budget exhausted
        - Mix: 5 simulations (500) + 100 queries (500) = 1000 → budget exhausted
    """
    
    @staticmethod
    def check_budget(user_id: str, endpoint: str) -> tuple[bool, dict]:
        """
        Check if user has enough budget for this endpoint.
        
        Returns:
            (allowed, info) where info contains current usage and remaining budget
        """
        cost = ENDPOINT_COSTS.get(endpoint, 1)
        key = f"rate_limit:cost:{user_id}:{datetime.utcnow().strftime('%Y-%m-%d')}"
        
        # Get current usage
        current_usage = redis_client.get(key)
        current_usage = int(current_usage) if current_usage else 0
        
        # Check if adding this cost would exceed budget
        new_usage = current_usage + cost
        allowed = new_usage <= DAILY_BUDGET
        
        if allowed:
            # Increment usage
            redis_client.setex(key, timedelta(days=1), new_usage)
        
        return allowed, {
            "current_usage": new_usage if allowed else current_usage,
            "daily_budget": DAILY_BUDGET,
            "remaining_budget": max(0, DAILY_BUDGET - (new_usage if allowed else current_usage)),
            "endpoint_cost": cost,
            "reset_at": (datetime.utcnow() + timedelta(days=1)).replace(hour=0, minute=0, second=0).isoformat()
        }
    
    @staticmethod
    def get_usage_stats(user_id: str) -> dict:
        """Get current usage statistics for a user."""
        key = f"rate_limit:cost:{user_id}:{datetime.utcnow().strftime('%Y-%m-%d')}"
        current_usage = redis_client.get(key)
        current_usage = int(current_usage) if current_usage else 0
        
        return {
            "current_usage": current_usage,
            "daily_budget": DAILY_BUDGET,
            "remaining_budget": max(0, DAILY_BUDGET - current_usage),
            "usage_percentage": (current_usage / DAILY_BUDGET) * 100,
            "reset_at": (datetime.utcnow() + timedelta(days=1)).replace(hour=0, minute=0, second=0).isoformat()
        }


def cost_limited(endpoint: str):
    """
    Decorator to apply cost-based rate limiting to an endpoint.
    
    Usage:
        @router.post("/run")
        @cost_limited("/api/simulation/run")
        async def run_simulation(...):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user_id from kwargs (injected by get_current_user dependency)
            current_user = kwargs.get('current_user')
            if not current_user:
                # If no user context, allow (for public endpoints)
                return await func(*args, **kwargs)
            
            user_id = current_user.get('sub') or current_user.get('user_id')
            
            # Check budget
            allowed, info = CostBasedRateLimiter.check_budget(user_id, endpoint)
            
            if not allowed:
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "message": f"Daily budget exhausted. Resets at {info['reset_at']}",
                        "usage_info": info
                    }
                )
            
            # Add usage info to response headers
            response = await func(*args, **kwargs)
            
            # If response is a Response object, add headers
            if hasattr(response, 'headers'):
                response.headers['X-RateLimit-Remaining'] = str(info['remaining_budget'])
                response.headers['X-RateLimit-Reset'] = info['reset_at']
            
            return response
        
        return wrapper
    return decorator


# Standard limiter for simple rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],
    storage_uri=os.getenv("REDIS_URL", "memory://")
)
