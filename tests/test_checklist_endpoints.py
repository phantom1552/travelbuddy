"""
Unit tests for checklist generation API endpoints.

Tests cover request validation, authentication, error handling,
and integration with the checklist generation service.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import json

from main import app
from app.models.trip import TripDataResponse, TransportType
from app.models.checklist import ChecklistGenerationResponse, ChecklistItemResponse, PriorityLevel
from app.services.checklist_generator import ChecklistGenerationError
from app.services.groq_client import GroqAPIError, GroqRateLimitError


class TestChecklistGenerationEndpoint:
    """Test cases for the /generate-checklist endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers with a valid token."""
        # This would normally use a real token, but for testing we'll mock the auth
        return {"Authorization": "Bearer test-token"}
    
    @pytest.fixture
    def sample_request_data(self):
        """Create sample request data for checklist generation."""
        return {
            "trip_data": {
                "location": "Paris, France",
                "days": 5,
                "transport": "plane",
                "occasion": "vacation",
                "notes": "First time visiting Europe",
                "preferences": ["lightweight", "comfortable"]
            }
        }
    
    @pytest.fixture
    def sample_checklist_response(self):
        """Create a sample checklist response."""
        items = [
            ChecklistItemResponse(
                id="item-1",
                text="Passport",
                category="Documents",
                checked=False,
                priority=PriorityLevel.HIGH,
                user_added=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            ),
            ChecklistItemResponse(
                id="item-2",
                text="Comfortable shoes",
                category="Clothing",
                checked=False,
                priority=PriorityLevel.MEDIUM,
                user_added=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        ]
        
        return ChecklistGenerationResponse(
            id="checklist-123",
            items=items,
            generated_at=datetime.utcnow(),
            trip_data=TripDataResponse(
                location="Paris, France",
                days=5,
                transport=TransportType.PLANE,
                occasion="vacation",
                notes="First time visiting Europe",
                preferences=["lightweight", "comfortable"]
            )
        )
    
    @patch('app.api.routes.get_current_active_user')
    @patch('app.api.routes.create_checklist_generator')
    def test_generate_checklist_success(self, mock_create_generator, mock_get_user, client, auth_headers, sample_request_data, sample_checklist_response):
        """Test successful checklist generation."""
        # Mock authentication
        mock_user = Mock()
        mock_user.username = "testuser"
        mock_user.user_id = "user-123"
        mock_get_user.return_value = mock_user
        
        # Mock checklist generator
        mock_generator = Mock()
        mock_generator.generate_checklist = AsyncMock(return_value=sample_checklist_response)
        mock_create_generator.return_value = mock_generator
        
        # Make request
        response = client.post(
            "/api/v1/generate-checklist",
            json=sample_request_data,
            headers=auth_headers
        )
        
        # Assertions
        assert response.status_code == 200
        response_data = response.json()
        
        assert response_data["id"] == "checklist-123"
        assert len(response_data["items"]) == 2
        assert response_data["items"][0]["text"] == "Passport"
        assert response_data["items"][0]["category"] == "Documents"
        assert response_data["items"][0]["priority"] == "high"
        assert response_data["trip_data"]["location"] == "Paris, France"
        
        # Verify service was called correctly
        mock_generator.generate_checklist.assert_called_once()
        call_args = mock_generator.generate_checklist.call_args[0][0]
        assert call_args.location == "Paris, France"
        assert call_args.days == 5
        assert call_args.transport == TransportType.PLANE
    
    def test_generate_checklist_no_auth(self, client, sample_request_data):
        """Test checklist generation without authentication."""
        response = client.post(
            "/api/v1/generate-checklist",
            json=sample_request_data
        )
        
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]
    
    @patch('app.api.routes.get_current_active_user')
    def test_generate_checklist_invalid_request_data(self, mock_get_user, client, auth_headers):
        """Test checklist generation with invalid request data."""
        # Mock authentication
        mock_user = Mock()
        mock_user.username = "testuser"
        mock_get_user.return_value = mock_user
        
        # Invalid request data (missing required fields)
        invalid_data = {
            "trip_data": {
                "location": "",  # Empty location
                "days": 0,  # Invalid days
                "transport": "invalid_transport",  # Invalid transport
                "occasion": ""  # Empty occasion
            }
        }
        
        response = client.post(
            "/api/v1/generate-checklist",
            json=invalid_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422  # Validation error
    
    @patch('app.api.routes.get_current_active_user')
    @patch('app.api.routes.create_checklist_generator')
    def test_generate_checklist_generation_error(self, mock_create_generator, mock_get_user, client, auth_headers, sample_request_data):
        """Test handling of checklist generation errors."""
        # Mock authentication
        mock_user = Mock()
        mock_user.username = "testuser"
        mock_get_user.return_value = mock_user
        
        # Mock generator to raise error
        mock_generator = Mock()
        mock_generator.generate_checklist = AsyncMock(
            side_effect=ChecklistGenerationError("Generation failed")
        )
        mock_create_generator.return_value = mock_generator
        
        response = client.post(
            "/api/v1/generate-checklist",
            json=sample_request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 500
        assert "Failed to generate checklist" in response.json()["detail"]
    
    @patch('app.api.routes.get_current_active_user')
    @patch('app.api.routes.create_checklist_generator')
    def test_generate_checklist_rate_limit_error(self, mock_create_generator, mock_get_user, client, auth_headers, sample_request_data):
        """Test handling of rate limit errors."""
        # Mock authentication
        mock_user = Mock()
        mock_user.username = "testuser"
        mock_get_user.return_value = mock_user
        
        # Mock generator to raise rate limit error
        mock_generator = Mock()
        mock_generator.generate_checklist = AsyncMock(
            side_effect=GroqRateLimitError("Rate limit exceeded")
        )
        mock_create_generator.return_value = mock_generator
        
        response = client.post(
            "/api/v1/generate-checklist",
            json=sample_request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 503
        assert "temporarily unavailable due to rate limiting" in response.json()["detail"]
    
    @patch('app.api.routes.get_current_active_user')
    @patch('app.api.routes.create_checklist_generator')
    def test_generate_checklist_groq_api_error(self, mock_create_generator, mock_get_user, client, auth_headers, sample_request_data):
        """Test handling of Groq API errors."""
        # Mock authentication
        mock_user = Mock()
        mock_user.username = "testuser"
        mock_get_user.return_value = mock_user
        
        # Mock generator to raise API error
        mock_generator = Mock()
        mock_generator.generate_checklist = AsyncMock(
            side_effect=GroqAPIError("API error")
        )
        mock_create_generator.return_value = mock_generator
        
        response = client.post(
            "/api/v1/generate-checklist",
            json=sample_request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 503
        assert "AI service temporarily unavailable" in response.json()["detail"]
    
    @patch('app.api.routes.get_current_active_user')
    @patch('app.api.routes.create_checklist_generator')
    def test_generate_checklist_unexpected_error(self, mock_create_generator, mock_get_user, client, auth_headers, sample_request_data):
        """Test handling of unexpected errors."""
        # Mock authentication
        mock_user = Mock()
        mock_user.username = "testuser"
        mock_get_user.return_value = mock_user
        
        # Mock generator to raise unexpected error
        mock_generator = Mock()
        mock_generator.generate_checklist = AsyncMock(
            side_effect=Exception("Unexpected error")
        )
        mock_create_generator.return_value = mock_generator
        
        response = client.post(
            "/api/v1/generate-checklist",
            json=sample_request_data,
            headers=auth_headers
        )
        
        assert response.status_code == 500
        assert "unexpected error occurred" in response.json()["detail"]
    
    @patch('app.api.routes.get_current_active_user')
    @patch('app.api.routes.create_checklist_generator')
    def test_generate_checklist_minimal_data(self, mock_create_generator, mock_get_user, client, auth_headers, sample_checklist_response):
        """Test checklist generation with minimal trip data."""
        # Mock authentication
        mock_user = Mock()
        mock_user.username = "testuser"
        mock_get_user.return_value = mock_user
        
        # Mock checklist generator
        mock_generator = Mock()
        mock_generator.generate_checklist = AsyncMock(return_value=sample_checklist_response)
        mock_create_generator.return_value = mock_generator
        
        # Minimal request data
        minimal_data = {
            "trip_data": {
                "location": "Tokyo",
                "days": 3,
                "transport": "train",
                "occasion": "business"
            }
        }
        
        response = client.post(
            "/api/v1/generate-checklist",
            json=minimal_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["id"] == "checklist-123"
        
        # Verify service was called with minimal data
        mock_generator.generate_checklist.assert_called_once()
        call_args = mock_generator.generate_checklist.call_args[0][0]
        assert call_args.location == "Tokyo"
        assert call_args.days == 3
        assert call_args.transport == TransportType.TRAIN
        assert call_args.occasion == "business"
        assert call_args.notes is None
        assert call_args.preferences is None
    
    @patch('app.api.routes.get_current_active_user')
    @patch('app.api.routes.create_checklist_generator')
    def test_generate_checklist_all_transport_types(self, mock_create_generator, mock_get_user, client, auth_headers, sample_checklist_response):
        """Test checklist generation with different transport types."""
        # Mock authentication
        mock_user = Mock()
        mock_user.username = "testuser"
        mock_get_user.return_value = mock_user
        
        # Mock checklist generator
        mock_generator = Mock()
        mock_generator.generate_checklist = AsyncMock(return_value=sample_checklist_response)
        mock_create_generator.return_value = mock_generator
        
        transport_types = ["car", "train", "plane", "bus", "other"]
        
        for transport in transport_types:
            request_data = {
                "trip_data": {
                    "location": "Test Location",
                    "days": 3,
                    "transport": transport,
                    "occasion": "test"
                }
            }
            
            response = client.post(
                "/api/v1/generate-checklist",
                json=request_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200, f"Failed for transport type: {transport}"
            
            # Verify correct transport type was passed
            call_args = mock_generator.generate_checklist.call_args[0][0]
            assert call_args.transport.value == transport
    
    def test_generate_checklist_request_validation_edge_cases(self, client, auth_headers):
        """Test request validation with edge cases."""
        with patch('app.api.routes.get_current_active_user') as mock_get_user:
            mock_user = Mock()
            mock_user.username = "testuser"
            mock_get_user.return_value = mock_user
            
            # Test cases with invalid data
            test_cases = [
                # Days too high
                {
                    "trip_data": {
                        "location": "Test",
                        "days": 400,  # Over limit
                        "transport": "plane",
                        "occasion": "test"
                    }
                },
                # Days too low
                {
                    "trip_data": {
                        "location": "Test",
                        "days": 0,  # Under limit
                        "transport": "plane",
                        "occasion": "test"
                    }
                },
                # Location too short
                {
                    "trip_data": {
                        "location": "A",  # Too short
                        "days": 3,
                        "transport": "plane",
                        "occasion": "test"
                    }
                },
                # Invalid transport
                {
                    "trip_data": {
                        "location": "Test",
                        "days": 3,
                        "transport": "spaceship",  # Invalid
                        "occasion": "test"
                    }
                }
            ]
            
            for i, test_case in enumerate(test_cases):
                response = client.post(
                    "/api/v1/generate-checklist",
                    json=test_case,
                    headers=auth_headers
                )
                
                assert response.status_code == 422, f"Test case {i} should fail validation"


@pytest.mark.integration
class TestChecklistEndpointIntegration:
    """Integration tests for checklist endpoints."""
    
    @pytest.mark.skip(reason="Requires real authentication and API setup")
    def test_real_checklist_generation(self):
        """Test with real authentication and API (skipped by default)."""
        # This test would require real authentication setup
        # and should only be run in integration test environments
        pass