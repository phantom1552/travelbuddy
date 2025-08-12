from fastapi import Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security.utils import get_authorization_scheme_param
from typing import Optional
import logging
from .config import settings

logger = logging.getLogger(__name__)

# Security headers for production
SECURITY_HEADERS = {
    # Prevent clickjacking
    "X-Frame-Options": "DENY",
    
    # Prevent MIME type sniffing
    "X-Content-Type-Options": "nosniff",
    
    # Enable XSS protection
    "X-XSS-Protection": "1; mode=block",
    
    # Referrer policy
    "Referrer-Policy": "strict-origin-when-cross-origin",
    
    # Content Security Policy (basic)
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'; frame-ancestors 'none';",
    
    # Permissions policy
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=(), usb=(), magnetometer=(), gyroscope=(), speaker=()",
    
    # HSTS (only for HTTPS)
    # "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
}

# Development headers (less restrictive)
DEVELOPMENT_HEADERS = {
    "X-Frame-Options": "SAMEORIGIN",
    "X-Content-Type-Options": "nosniff",
    "X-XSS-Protection": "1; mode=block",
}


async def security_headers_middleware(request: Request, call_next):
    """Add security headers to responses"""
    response = await call_next(request)
    
    # Choose headers based on environment
    headers = SECURITY_HEADERS if settings.is_production else DEVELOPMENT_HEADERS
    
    # Add security headers
    for header, value in headers.items():
        response.headers[header] = value
    
    # Add HSTS only for HTTPS in production
    if settings.is_production and request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    
    # Add server header obfuscation
    response.headers["Server"] = "AI-Trip-Checklist-API"
    
    return response


class CustomHTTPBearer(HTTPBearer):
    """Custom HTTP Bearer authentication with better error handling"""
    
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)
    
    async def __call__(self, request: Request) -> Optional[HTTPAuthorizationCredentials]:
        authorization: str = request.headers.get("Authorization")
        
        if not authorization:
            if self.auto_error:
                logger.warning(f"Missing Authorization header from {request.client.host if request.client else 'unknown'}")
            return None
        
        scheme, credentials = get_authorization_scheme_param(authorization)
        
        if not (authorization and scheme and credentials):
            if self.auto_error:
                logger.warning(f"Invalid Authorization header format from {request.client.host if request.client else 'unknown'}")
            return None
        
        if scheme.lower() != "bearer":
            if self.auto_error:
                logger.warning(f"Invalid Authorization scheme '{scheme}' from {request.client.host if request.client else 'unknown'}")
            return None
        
        return HTTPAuthorizationCredentials(scheme=scheme, credentials=credentials)


def validate_request_size(max_size: int = 10 * 1024 * 1024):  # 10MB default
    """Middleware to validate request size"""
    async def middleware(request: Request, call_next):
        content_length = request.headers.get("content-length")
        
        if content_length:
            try:
                size = int(content_length)
                if size > max_size:
                    logger.warning(f"Request too large: {size} bytes from {request.client.host if request.client else 'unknown'}")
                    return Response(
                        content='{"error": "REQUEST_TOO_LARGE", "message": "Request body too large"}',
                        status_code=413,
                        media_type="application/json"
                    )
            except ValueError:
                logger.warning(f"Invalid Content-Length header from {request.client.host if request.client else 'unknown'}")
        
        return await call_next(request)
    
    return middleware


def sanitize_input(value: str, max_length: int = 1000) -> str:
    """Basic input sanitization"""
    if not isinstance(value, str):
        return str(value)
    
    # Truncate if too long
    if len(value) > max_length:
        value = value[:max_length]
    
    # Remove null bytes and control characters
    value = ''.join(char for char in value if ord(char) >= 32 or char in '\t\n\r')
    
    return value.strip()


def is_safe_redirect_url(url: str, allowed_hosts: list = None) -> bool:
    """Check if a redirect URL is safe"""
    if not url:
        return False
    
    # Prevent open redirects
    if url.startswith(('http://', 'https://')):
        if allowed_hosts:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc in allowed_hosts
        return False
    
    # Allow relative URLs
    if url.startswith('/'):
        return True
    
    return False


# Create security instances
security = CustomHTTPBearer(auto_error=False)
request_size_validator = validate_request_size()

__all__ = [
    "security_headers_middleware",
    "CustomHTTPBearer",
    "validate_request_size",
    "sanitize_input",
    "is_safe_redirect_url",
    "security",
    "request_size_validator"
]