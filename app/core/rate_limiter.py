import time
import asyncio
from typing import Dict, Tuple, Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import logging
from .config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self, requests_per_window: int, window_seconds: int):
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.clients: Dict[str, Tuple[int, float]] = {}  # client_id -> (request_count, window_start)
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, client_id: str) -> Tuple[bool, Dict[str, any]]:
        """Check if client is allowed to make a request"""
        async with self._lock:
            current_time = time.time()
            
            if client_id not in self.clients:
                # First request from this client
                self.clients[client_id] = (1, current_time)
                return True, self._get_headers(1, current_time)
            
            request_count, window_start = self.clients[client_id]
            
            # Check if we're in a new window
            if current_time - window_start >= self.window_seconds:
                # New window, reset counter
                self.clients[client_id] = (1, current_time)
                return True, self._get_headers(1, current_time)
            
            # Same window, check if limit exceeded
            if request_count >= self.requests_per_window:
                # Rate limit exceeded
                return False, self._get_headers(request_count, window_start)
            
            # Increment counter
            self.clients[client_id] = (request_count + 1, window_start)
            return True, self._get_headers(request_count + 1, window_start)
    
    def _get_headers(self, current_requests: int, window_start: float) -> Dict[str, any]:
        """Get rate limit headers"""
        remaining = max(0, self.requests_per_window - current_requests)
        reset_time = int(window_start + self.window_seconds)
        
        return {
            "X-RateLimit-Limit": str(self.requests_per_window),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_time),
            "X-RateLimit-Window": str(self.window_seconds),
        }
    
    async def cleanup_expired_clients(self):
        """Remove expired client entries to prevent memory leaks"""
        async with self._lock:
            current_time = time.time()
            expired_clients = [
                client_id for client_id, (_, window_start) in self.clients.items()
                if current_time - window_start >= self.window_seconds * 2
            ]
            
            for client_id in expired_clients:
                del self.clients[client_id]
            
            if expired_clients:
                logger.debug(f"Cleaned up {len(expired_clients)} expired rate limit entries")


# Global rate limiter instance
rate_limiter = RateLimiter(
    requests_per_window=settings.RATE_LIMIT_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW
)


def get_client_id(request: Request) -> str:
    """Extract client identifier from request"""
    # Try to get real IP from headers (for reverse proxy setups)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"
    
    # Include user agent for better client identification
    user_agent = request.headers.get("User-Agent", "")[:50]  # Truncate to prevent abuse
    
    return f"{client_ip}:{hash(user_agent) % 10000}"


async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware"""
    
    # Skip rate limiting for health checks and internal endpoints
    if request.url.path in ["/health", "/", "/docs", "/redoc", "/openapi.json"]:
        return await call_next(request)
    
    client_id = get_client_id(request)
    
    try:
        allowed, headers = await rate_limiter.is_allowed(client_id)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for client {client_id} on {request.url.path}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Please try again later.",
                    "code": 429
                },
                headers=headers
            )
        
        # Process the request
        response = await call_next(request)
        
        # Add rate limit headers to response
        for key, value in headers.items():
            response.headers[key] = value
        
        return response
        
    except Exception as e:
        logger.error(f"Rate limiter error: {e}")
        # If rate limiter fails, allow the request to proceed
        return await call_next(request)


async def cleanup_rate_limiter():
    """Periodic cleanup task for rate limiter"""
    while True:
        try:
            await rate_limiter.cleanup_expired_clients()
            await asyncio.sleep(300)  # Cleanup every 5 minutes
        except Exception as e:
            logger.error(f"Rate limiter cleanup error: {e}")
            await asyncio.sleep(60)  # Retry after 1 minute on error