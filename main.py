from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
import asyncio
import time
from typing import Callable

from app.api.routes import router as api_router
from app.core.config import settings
from app.core.logging_config import setup_logging, StructuredLogger
from app.core.rate_limiter import rate_limit_middleware, cleanup_rate_limiter
from app.core.security import security_headers_middleware, request_size_validator
from app.core.health import get_health_status

# Setup logging first
setup_logging()
logger = StructuredLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.logger.info(f"Starting up AI Trip Checklist API v{settings.VERSION}")
    logger.logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.logger.info(f"Debug mode: {settings.DEBUG}")
    
    # Start background tasks
    cleanup_task = None
    if settings.is_production:
        cleanup_task = asyncio.create_task(cleanup_rate_limiter())
        logger.logger.info("Started rate limiter cleanup task")
    
    yield
    
    # Shutdown
    logger.logger.info("Shutting down AI Trip Checklist API...")
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


# Create FastAPI app with production settings
app_kwargs = {
    "title": settings.PROJECT_NAME,
    "description": "Backend API for generating AI-powered travel packing checklists",
    "version": settings.VERSION,
    "lifespan": lifespan,
}

# In production, disable docs and redoc for security
if settings.is_production:
    app_kwargs.update({
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    })

app = FastAPI(**app_kwargs)


# Add middleware in correct order (last added = first executed)
# Note: These are function-based middleware, not class-based

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next: Callable):
    return await security_headers_middleware(request, call_next)

# Request size validation middleware  
@app.middleware("http")
async def validate_request_size(request: Request, call_next: Callable):
    return await request_size_validator(request, call_next)

# Rate limiting middleware (only in production)
if settings.is_production:
    @app.middleware("http")
    async def apply_rate_limiting(request: Request, call_next: Callable):
        return await rate_limit_middleware(request, call_next)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next: Callable):
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Log request with structured logging
    duration = time.time() - start_time
    logger.log_request(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration=duration
    )
    
    return response


# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail} - Path: {request.url.path}")
    
    # Don't expose internal details in production
    message = exc.detail
    if settings.is_production and exc.status_code >= 500:
        message = "Internal server error"
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "message": message,
            "code": exc.status_code,
            "path": str(request.url.path) if settings.is_development else None
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.logger.error(f"Unexpected error: {str(exc)} - Path: {request.url.path}", exc_info=True)
    
    # Don't expose internal error details in production
    message = "An unexpected error occurred"
    details = None
    
    if settings.is_development:
        message = str(exc)
        details = {
            "type": type(exc).__name__,
            "path": str(request.url.path)
        }
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": message,
            "code": 500,
            "details": details
        }
    )

# Configure CORS with production-safe settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"] if settings.is_development else [
        "Accept",
        "Accept-Language", 
        "Content-Language",
        "Content-Type",
        "Authorization"
    ],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "AI Trip Checklist API is running"}


@app.get("/health")
async def health_check():
    """Comprehensive health check endpoint"""
    return await get_health_status()


@app.get("/health/live")
async def liveness_check():
    """Simple liveness check for container orchestration"""
    return {"status": "alive", "timestamp": time.time()}


@app.get("/health/ready")
async def readiness_check():
    """Readiness check for container orchestration"""
    health_status = await get_health_status()
    
    if health_status["status"] == "unhealthy":
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "details": health_status}
        )
    
    return {"status": "ready", "timestamp": time.time()}


if __name__ == "__main__":
    # Development server configuration
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.is_development,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=settings.is_development,
        workers=1,  # Single worker for development
    )