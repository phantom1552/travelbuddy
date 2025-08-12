from pydantic_settings import BaseSettings
from typing import List, Optional
import secrets
import os


class Settings(BaseSettings):
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AI Trip Checklist API"
    VERSION: str = "1.0.0"
    
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1
    
    # CORS Configuration
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:19006,exp://localhost:19000"
    
    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
    
    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds
    
    # Groq API Configuration
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama3-8b-8192"
    GROQ_TIMEOUT: int = 30
    GROQ_MAX_RETRIES: int = 3
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: Optional[str] = None
    
    # Database Configuration (for future use)
    DATABASE_URL: Optional[str] = None
    
    # Monitoring
    ENABLE_METRICS: bool = False
    METRICS_PORT: int = 9090
    
    # Health Check
    HEALTH_CHECK_TIMEOUT: int = 5
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"
    
    @property
    def log_level_numeric(self) -> int:
        import logging
        return getattr(logging, self.LOG_LEVEL.upper(), logging.INFO)
    
    def get_cors_origins(self) -> List[str]:
        """Get CORS origins with production-safe defaults"""
        if self.is_production:
            # In production, be more restrictive with CORS
            origins = self.allowed_origins_list
            # Filter out localhost origins in production
            return [origin for origin in origins if not origin.startswith("http://localhost")]
        return self.allowed_origins_list
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        
        # Allow environment variables to override settings
        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str) -> any:
            if field_name == 'DEBUG':
                return raw_val.lower() in ('true', '1', 'yes', 'on')
            if field_name == 'ENABLE_METRICS':
                return raw_val.lower() in ('true', '1', 'yes', 'on')
            return cls.json_loads(raw_val)


# Create settings instance
settings = Settings()

# Validate critical settings
if settings.is_production:
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY must be set in production")
    
    if settings.SECRET_KEY == "your-secret-key-change-in-production":
        raise ValueError("SECRET_KEY must be changed in production")
    
    if settings.DEBUG:
        import warnings
        warnings.warn("DEBUG is enabled in production environment")

# Export commonly used values
__all__ = ["settings"]