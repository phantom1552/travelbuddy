"""
Common Pydantic models and utilities.
"""
from typing import List, Optional, Any, Dict
from datetime import datetime

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Model for detailed error information."""
    field: Optional[str] = Field(
        None,
        description="Field name that caused the error"
    )
    message: str = Field(
        ...,
        description="Human-readable error message"
    )
    code: Optional[str] = Field(
        None,
        description="Error code for programmatic handling"
    )


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str = Field(..., description="Error type or category")
    message: str = Field(..., description="Main error message")
    details: Optional[List[ErrorDetail]] = Field(
        None,
        description="Detailed error information"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the error occurred"
    )
    request_id: Optional[str] = Field(
        None,
        description="Unique request identifier for tracking"
    )


class SuccessResponse(BaseModel):
    """Standard success response model."""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(..., description="Success message")
    data: Optional[Any] = Field(None, description="Response data")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp"
    )


class HealthCheckResponse(BaseModel):
    """Health check response model."""
    status: str = Field(default="healthy", description="Service health status")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Health check timestamp"
    )
    version: Optional[str] = Field(None, description="API version")
    uptime: Optional[float] = Field(None, description="Service uptime in seconds")
    dependencies: Optional[Dict[str, str]] = Field(
        None,
        description="Status of external dependencies"
    )


class PaginationParams(BaseModel):
    """Model for pagination parameters."""
    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-based)"
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of items per page"
    )
    
    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.limit


class PaginatedResponse(BaseModel):
    """Model for paginated response data."""
    items: List[Any] = Field(..., description="List of items for current page")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")
    
    @classmethod
    def create(
        cls,
        items: List[Any],
        total: int,
        pagination: PaginationParams
    ) -> "PaginatedResponse":
        """Create a paginated response from items and pagination params."""
        pages = (total + pagination.limit - 1) // pagination.limit
        
        return cls(
            items=items,
            total=total,
            page=pagination.page,
            limit=pagination.limit,
            pages=pages,
            has_next=pagination.page < pages,
            has_prev=pagination.page > 1
        )