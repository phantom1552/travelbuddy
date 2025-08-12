"""
Tests for common Pydantic models.
"""
import pytest
from datetime import datetime
from typing import List
from pydantic import ValidationError

from app.models.common import (
    ErrorDetail,
    ErrorResponse,
    SuccessResponse,
    HealthCheckResponse,
    PaginationParams,
    PaginatedResponse
)


class TestErrorDetail:
    """Test cases for ErrorDetail model."""
    
    def test_valid_error_detail(self):
        """Test creating valid error detail."""
        data = {
            "field": "username",
            "message": "Username is required",
            "code": "REQUIRED_FIELD"
        }
        
        error_detail = ErrorDetail(**data)
        
        assert error_detail.field == "username"
        assert error_detail.message == "Username is required"
        assert error_detail.code == "REQUIRED_FIELD"
    
    def test_minimal_error_detail(self):
        """Test creating minimal error detail."""
        data = {"message": "Something went wrong"}
        
        error_detail = ErrorDetail(**data)
        
        assert error_detail.field is None
        assert error_detail.message == "Something went wrong"
        assert error_detail.code is None


class TestErrorResponse:
    """Test cases for ErrorResponse model."""
    
    def test_valid_error_response(self):
        """Test creating valid error response."""
        now = datetime.utcnow()
        details = [
            ErrorDetail(field="email", message="Invalid email format", code="INVALID_FORMAT")
        ]
        
        data = {
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": details,
            "timestamp": now,
            "request_id": "req-123"
        }
        
        error_response = ErrorResponse(**data)
        
        assert error_response.error == "VALIDATION_ERROR"
        assert error_response.message == "Request validation failed"
        assert len(error_response.details) == 1
        assert error_response.details[0].field == "email"
        assert error_response.timestamp == now
        assert error_response.request_id == "req-123"
    
    def test_minimal_error_response(self):
        """Test creating minimal error response."""
        data = {
            "error": "SERVER_ERROR",
            "message": "Internal server error"
        }
        
        error_response = ErrorResponse(**data)
        
        assert error_response.error == "SERVER_ERROR"
        assert error_response.message == "Internal server error"
        assert error_response.details is None
        assert isinstance(error_response.timestamp, datetime)
        assert error_response.request_id is None
    
    def test_timestamp_default(self):
        """Test that timestamp defaults to current time."""
        before_create = datetime.utcnow()
        
        error_response = ErrorResponse(
            error="TEST_ERROR",
            message="Test message"
        )
        
        after_create = datetime.utcnow()
        
        assert before_create <= error_response.timestamp <= after_create


class TestSuccessResponse:
    """Test cases for SuccessResponse model."""
    
    def test_valid_success_response(self):
        """Test creating valid success response."""
        now = datetime.utcnow()
        data = {
            "success": True,
            "message": "Operation completed successfully",
            "data": {"result": "success"},
            "timestamp": now
        }
        
        success_response = SuccessResponse(**data)
        
        assert success_response.success is True
        assert success_response.message == "Operation completed successfully"
        assert success_response.data == {"result": "success"}
        assert success_response.timestamp == now
    
    def test_minimal_success_response(self):
        """Test creating minimal success response."""
        data = {"message": "Success"}
        
        success_response = SuccessResponse(**data)
        
        assert success_response.success is True  # default
        assert success_response.message == "Success"
        assert success_response.data is None
        assert isinstance(success_response.timestamp, datetime)
    
    def test_timestamp_default(self):
        """Test that timestamp defaults to current time."""
        before_create = datetime.utcnow()
        
        success_response = SuccessResponse(message="Test success")
        
        after_create = datetime.utcnow()
        
        assert before_create <= success_response.timestamp <= after_create


class TestHealthCheckResponse:
    """Test cases for HealthCheckResponse model."""
    
    def test_valid_health_check_response(self):
        """Test creating valid health check response."""
        now = datetime.utcnow()
        dependencies = {
            "database": "healthy",
            "groq_api": "healthy",
            "redis": "degraded"
        }
        
        data = {
            "status": "healthy",
            "timestamp": now,
            "version": "1.0.0",
            "uptime": 3600.5,
            "dependencies": dependencies
        }
        
        health_response = HealthCheckResponse(**data)
        
        assert health_response.status == "healthy"
        assert health_response.timestamp == now
        assert health_response.version == "1.0.0"
        assert health_response.uptime == 3600.5
        assert health_response.dependencies == dependencies
    
    def test_minimal_health_check_response(self):
        """Test creating minimal health check response."""
        health_response = HealthCheckResponse()
        
        assert health_response.status == "healthy"  # default
        assert isinstance(health_response.timestamp, datetime)
        assert health_response.version is None
        assert health_response.uptime is None
        assert health_response.dependencies is None
    
    def test_timestamp_default(self):
        """Test that timestamp defaults to current time."""
        before_create = datetime.utcnow()
        
        health_response = HealthCheckResponse()
        
        after_create = datetime.utcnow()
        
        assert before_create <= health_response.timestamp <= after_create


class TestPaginationParams:
    """Test cases for PaginationParams model."""
    
    def test_valid_pagination_params(self):
        """Test creating valid pagination parameters."""
        data = {
            "page": 2,
            "limit": 50
        }
        
        pagination = PaginationParams(**data)
        
        assert pagination.page == 2
        assert pagination.limit == 50
        assert pagination.offset == 50  # (2-1) * 50
    
    def test_default_pagination_params(self):
        """Test creating pagination parameters with defaults."""
        pagination = PaginationParams()
        
        assert pagination.page == 1  # default
        assert pagination.limit == 20  # default
        assert pagination.offset == 0  # (1-1) * 20
    
    def test_offset_calculation(self):
        """Test offset calculation for different page/limit combinations."""
        # Page 1, limit 10
        pagination1 = PaginationParams(page=1, limit=10)
        assert pagination1.offset == 0
        
        # Page 3, limit 25
        pagination2 = PaginationParams(page=3, limit=25)
        assert pagination2.offset == 50  # (3-1) * 25
        
        # Page 5, limit 100
        pagination3 = PaginationParams(page=5, limit=100)
        assert pagination3.offset == 400  # (5-1) * 100
    
    def test_page_validation(self):
        """Test page field validation."""
        # Test page less than 1
        with pytest.raises(ValidationError) as exc_info:
            PaginationParams(page=0)
        assert "greater than or equal to 1" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            PaginationParams(page=-1)
        assert "greater than or equal to 1" in str(exc_info.value)
        
        # Test valid page
        pagination = PaginationParams(page=1)
        assert pagination.page == 1
    
    def test_limit_validation(self):
        """Test limit field validation."""
        # Test limit less than 1
        with pytest.raises(ValidationError) as exc_info:
            PaginationParams(limit=0)
        assert "greater than or equal to 1" in str(exc_info.value)
        
        # Test limit greater than 100
        with pytest.raises(ValidationError) as exc_info:
            PaginationParams(limit=101)
        assert "less than or equal to 100" in str(exc_info.value)
        
        # Test valid boundary values
        pagination_min = PaginationParams(limit=1)
        assert pagination_min.limit == 1
        
        pagination_max = PaginationParams(limit=100)
        assert pagination_max.limit == 100


class TestPaginatedResponse:
    """Test cases for PaginatedResponse model."""
    
    def test_valid_paginated_response(self):
        """Test creating valid paginated response."""
        items = ["item1", "item2", "item3"]
        data = {
            "items": items,
            "total": 100,
            "page": 2,
            "limit": 20,
            "pages": 5,
            "has_next": True,
            "has_prev": True
        }
        
        paginated_response = PaginatedResponse(**data)
        
        assert paginated_response.items == items
        assert paginated_response.total == 100
        assert paginated_response.page == 2
        assert paginated_response.limit == 20
        assert paginated_response.pages == 5
        assert paginated_response.has_next is True
        assert paginated_response.has_prev is True
    
    def test_create_paginated_response(self):
        """Test creating paginated response using create class method."""
        items = [f"item{i}" for i in range(1, 21)]  # 20 items
        total = 85
        pagination = PaginationParams(page=2, limit=20)
        
        paginated_response = PaginatedResponse.create(
            items=items,
            total=total,
            pagination=pagination
        )
        
        assert paginated_response.items == items
        assert paginated_response.total == 85
        assert paginated_response.page == 2
        assert paginated_response.limit == 20
        assert paginated_response.pages == 5  # ceil(85/20) = 5
        assert paginated_response.has_next is True  # page 2 < 5 pages
        assert paginated_response.has_prev is True  # page 2 > 1
    
    def test_create_first_page(self):
        """Test creating paginated response for first page."""
        items = [f"item{i}" for i in range(1, 11)]  # 10 items
        total = 50
        pagination = PaginationParams(page=1, limit=10)
        
        paginated_response = PaginatedResponse.create(
            items=items,
            total=total,
            pagination=pagination
        )
        
        assert paginated_response.page == 1
        assert paginated_response.pages == 5  # ceil(50/10) = 5
        assert paginated_response.has_next is True  # page 1 < 5 pages
        assert paginated_response.has_prev is False  # page 1 = 1
    
    def test_create_last_page(self):
        """Test creating paginated response for last page."""
        items = [f"item{i}" for i in range(1, 6)]  # 5 items
        total = 45
        pagination = PaginationParams(page=5, limit=10)
        
        paginated_response = PaginatedResponse.create(
            items=items,
            total=total,
            pagination=pagination
        )
        
        assert paginated_response.page == 5
        assert paginated_response.pages == 5  # ceil(45/10) = 5
        assert paginated_response.has_next is False  # page 5 = 5 pages
        assert paginated_response.has_prev is True  # page 5 > 1
    
    def test_create_single_page(self):
        """Test creating paginated response for single page."""
        items = [f"item{i}" for i in range(1, 6)]  # 5 items
        total = 5
        pagination = PaginationParams(page=1, limit=10)
        
        paginated_response = PaginatedResponse.create(
            items=items,
            total=total,
            pagination=pagination
        )
        
        assert paginated_response.page == 1
        assert paginated_response.pages == 1  # ceil(5/10) = 1
        assert paginated_response.has_next is False  # page 1 = 1 page
        assert paginated_response.has_prev is False  # page 1 = 1
    
    def test_create_empty_results(self):
        """Test creating paginated response with no items."""
        items = []
        total = 0
        pagination = PaginationParams(page=1, limit=10)
        
        paginated_response = PaginatedResponse.create(
            items=items,
            total=total,
            pagination=pagination
        )
        
        assert paginated_response.items == []
        assert paginated_response.total == 0
        assert paginated_response.page == 1
        assert paginated_response.pages == 0  # ceil(0/10) = 0
        assert paginated_response.has_next is False
        assert paginated_response.has_prev is False