import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone
import httpx
from .config import settings

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


@dataclass
class HealthCheck:
    name: str
    status: HealthStatus
    message: str
    duration_ms: float
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None


class HealthChecker:
    """Health check system for monitoring application components"""
    
    def __init__(self):
        self.checks: Dict[str, callable] = {}
        self.last_results: Dict[str, HealthCheck] = {}
    
    def register_check(self, name: str, check_func: callable):
        """Register a health check function"""
        self.checks[name] = check_func
        logger.info(f"Registered health check: {name}")
    
    async def run_check(self, name: str) -> HealthCheck:
        """Run a single health check"""
        if name not in self.checks:
            return HealthCheck(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check '{name}' not found",
                duration_ms=0,
                timestamp=datetime.now(timezone.utc)
            )
        
        start_time = time.time()
        try:
            # Run the check with timeout
            result = await asyncio.wait_for(
                self.checks[name](),
                timeout=settings.HEALTH_CHECK_TIMEOUT
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            if isinstance(result, HealthCheck):
                result.duration_ms = duration_ms
                result.timestamp = datetime.now(timezone.utc)
                return result
            elif isinstance(result, bool):
                return HealthCheck(
                    name=name,
                    status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                    message="OK" if result else "Check failed",
                    duration_ms=duration_ms,
                    timestamp=datetime.now(timezone.utc)
                )
            else:
                return HealthCheck(
                    name=name,
                    status=HealthStatus.HEALTHY,
                    message=str(result) if result else "OK",
                    duration_ms=duration_ms,
                    timestamp=datetime.now(timezone.utc)
                )
        
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check timed out after {settings.HEALTH_CHECK_TIMEOUT}s",
                duration_ms=duration_ms,
                timestamp=datetime.now(timezone.utc)
            )
        
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Health check '{name}' failed: {e}")
            return HealthCheck(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {str(e)}",
                duration_ms=duration_ms,
                timestamp=datetime.now(timezone.utc)
            )
    
    async def run_all_checks(self) -> Dict[str, HealthCheck]:
        """Run all registered health checks"""
        results = {}
        
        # Run checks concurrently
        tasks = [self.run_check(name) for name in self.checks.keys()]
        check_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(check_results):
            name = list(self.checks.keys())[i]
            if isinstance(result, Exception):
                results[name] = HealthCheck(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check failed with exception: {str(result)}",
                    duration_ms=0,
                    timestamp=datetime.now(timezone.utc)
                )
            else:
                results[name] = result
        
        # Cache results
        self.last_results = results
        return results
    
    def get_overall_status(self, results: Dict[str, HealthCheck]) -> HealthStatus:
        """Determine overall system health status"""
        if not results:
            return HealthStatus.HEALTHY
        
        statuses = [check.status for check in results.values()]
        
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY


# Global health checker instance
health_checker = HealthChecker()


# Built-in health checks
async def basic_health_check() -> HealthCheck:
    """Basic application health check"""
    return HealthCheck(
        name="basic",
        status=HealthStatus.HEALTHY,
        message="Application is running",
        duration_ms=0,
        timestamp=datetime.now(timezone.utc),
        details={
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "uptime": time.time()  # This would be better with actual uptime tracking
        }
    )


async def groq_api_health_check() -> HealthCheck:
    """Check Groq API connectivity"""
    if not settings.GROQ_API_KEY:
        return HealthCheck(
            name="groq_api",
            status=HealthStatus.DEGRADED,
            message="Groq API key not configured",
            duration_ms=0,
            timestamp=datetime.now(timezone.utc)
        )
    
    try:
        # Simple connectivity test (you might want to use actual Groq client here)
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
            )
            
            if response.status_code == 200:
                return HealthCheck(
                    name="groq_api",
                    status=HealthStatus.HEALTHY,
                    message="Groq API is accessible",
                    duration_ms=0,
                    timestamp=datetime.now(timezone.utc),
                    details={"status_code": response.status_code}
                )
            else:
                return HealthCheck(
                    name="groq_api",
                    status=HealthStatus.DEGRADED,
                    message=f"Groq API returned status {response.status_code}",
                    duration_ms=0,
                    timestamp=datetime.now(timezone.utc),
                    details={"status_code": response.status_code}
                )
    
    except Exception as e:
        return HealthCheck(
            name="groq_api",
            status=HealthStatus.UNHEALTHY,
            message=f"Cannot connect to Groq API: {str(e)}",
            duration_ms=0,
            timestamp=datetime.now(timezone.utc)
        )


async def memory_health_check() -> HealthCheck:
    """Check memory usage"""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_percent = process.memory_percent()
        
        # Consider unhealthy if using more than 90% of available memory
        status = HealthStatus.HEALTHY
        if memory_percent > 90:
            status = HealthStatus.UNHEALTHY
        elif memory_percent > 75:
            status = HealthStatus.DEGRADED
        
        return HealthCheck(
            name="memory",
            status=status,
            message=f"Memory usage: {memory_percent:.1f}%",
            duration_ms=0,
            timestamp=datetime.now(timezone.utc),
            details={
                "memory_percent": memory_percent,
                "memory_rss": memory_info.rss,
                "memory_vms": memory_info.vms
            }
        )
    
    except ImportError:
        return HealthCheck(
            name="memory",
            status=HealthStatus.DEGRADED,
            message="psutil not available for memory monitoring",
            duration_ms=0,
            timestamp=datetime.now(timezone.utc)
        )
    
    except Exception as e:
        return HealthCheck(
            name="memory",
            status=HealthStatus.UNHEALTHY,
            message=f"Memory check failed: {str(e)}",
            duration_ms=0,
            timestamp=datetime.now(timezone.utc)
        )


# Register built-in health checks
health_checker.register_check("basic", basic_health_check)
health_checker.register_check("groq_api", groq_api_health_check)
health_checker.register_check("memory", memory_health_check)


async def get_health_status() -> Dict[str, Any]:
    """Get comprehensive health status"""
    results = await health_checker.run_all_checks()
    overall_status = health_checker.get_overall_status(results)
    
    return {
        "status": overall_status.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "checks": {
            name: {
                "status": check.status.value,
                "message": check.message,
                "duration_ms": check.duration_ms,
                "timestamp": check.timestamp.isoformat(),
                "details": check.details
            }
            for name, check in results.items()
        }
    }


__all__ = [
    "HealthStatus",
    "HealthCheck", 
    "HealthChecker",
    "health_checker",
    "get_health_status"
]