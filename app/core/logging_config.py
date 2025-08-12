import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Dict, Any
from .config import settings


def setup_logging() -> None:
    """Configure logging for the application"""
    
    # Create logs directory if it doesn't exist
    if settings.LOG_FILE:
        log_path = Path(settings.LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level_numeric)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(
        fmt=settings.LOG_FORMAT,
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.log_level_numeric)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if settings.LOG_FILE:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=settings.LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(settings.log_level_numeric)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Configure specific loggers
    configure_logger_levels()
    
    # Log startup information
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured - Level: {settings.LOG_LEVEL}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    if settings.LOG_FILE:
        logger.info(f"Log file: {settings.LOG_FILE}")


def configure_logger_levels() -> None:
    """Configure log levels for specific loggers"""
    
    logger_configs = {
        "uvicorn": logging.INFO,
        "uvicorn.access": logging.INFO if settings.is_development else logging.WARNING,
        "uvicorn.error": logging.INFO,
        "fastapi": logging.INFO,
        "httpx": logging.WARNING,
        "groq": logging.INFO,
    }
    
    # In production, reduce noise from third-party libraries
    if settings.is_production:
        logger_configs.update({
            "uvicorn.access": logging.WARNING,
            "httpx": logging.ERROR,
        })
    
    for logger_name, level in logger_configs.items():
        logging.getLogger(logger_name).setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name"""
    return logging.getLogger(name)


class StructuredLogger:
    """Structured logger for better log analysis"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def log_request(self, method: str, path: str, status_code: int, 
                   duration: float, user_id: str = None) -> None:
        """Log HTTP request with structured data"""
        extra = {
            "event_type": "http_request",
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration": duration,
            "user_id": user_id,
        }
        
        level = logging.INFO
        if status_code >= 500:
            level = logging.ERROR
        elif status_code >= 400:
            level = logging.WARNING
        
        self.logger.log(
            level,
            f"{method} {path} - {status_code} - {duration:.3f}s",
            extra=extra
        )
    
    def log_api_call(self, service: str, operation: str, 
                    duration: float, success: bool, error: str = None) -> None:
        """Log external API call"""
        extra = {
            "event_type": "api_call",
            "service": service,
            "operation": operation,
            "duration": duration,
            "success": success,
            "error": error,
        }
        
        level = logging.INFO if success else logging.ERROR
        message = f"{service}.{operation} - {'SUCCESS' if success else 'FAILED'} - {duration:.3f}s"
        if error:
            message += f" - {error}"
        
        self.logger.log(level, message, extra=extra)
    
    def log_business_event(self, event: str, user_id: str = None, **kwargs) -> None:
        """Log business events for analytics"""
        extra = {
            "event_type": "business_event",
            "event": event,
            "user_id": user_id,
            **kwargs
        }
        
        self.logger.info(f"Business Event: {event}", extra=extra)


# Create application-specific loggers
app_logger = StructuredLogger("app")
api_logger = StructuredLogger("api")
groq_logger = StructuredLogger("groq")

__all__ = [
    "setup_logging",
    "get_logger",
    "StructuredLogger",
    "app_logger",
    "api_logger", 
    "groq_logger"
]