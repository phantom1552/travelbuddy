"""
Integration tests for the complete API workflow.

Tests the full end-to-end flow from authentication to checklist generation,
including error handling and edge cases.
"""

import pytest
import asyncio
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from main import app
from app.services.groq_client import GroqClient
from app.models.trip import TripData
from app.models.checklist import ChecklistResponse


class TestAPIIntegration:
    """Integration tests for the complete API workflow."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, client):
        """Get authentication headers."""
        # Login to get token
        response = client.post("/api/v1/auth/login", json={
            "username": "testuser",
            "password": "testpass"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_complete_checklist_generation_flow(self, client, auth_headers):
        """Test the complete flow from authentication to checklist generation."""
        # Mock the Groq API response
        mock_response = """
        Here's your personalized packing checklist:

        **Documents:**
        - Passport
        - Travel insurance
        - Flight tickets

        **Clothing:**
        - Comfortable walking shoes
        - Weather-appropriate clothing
        - Underwear and socks

        **Electronics:**
        - Phone charger
        - Camera
        - Power adapter
        """

        with patch.object(GroqClient, 'generate_completion', new_callable=AsyncMock) as mock_groq:
            mock_groq.return_value = mock_response

            # Test data
            trip_data = {
                "location": "Paris, France",
                "days": 5,
                "transport": "plane",
                "occasion": "vacation",
                "notes": "First time visiting Europe"
            }

            # Make the request
            response = client.post(
                "/api/v1/generate-checklist",
                json=trip_data,
                headers=auth_headers
            )

            # Verify response
            assert response.status_code == 200
            data = response.json()

            # Check response structure
            assert "id" in data
            assert "items" in data
            assert "generated_at" in data
            assert len(data["items"]) > 0

            # Check that items have required fields
            for item in data["items"]:
                assert "id" in item
                assert "text" in item
                assert "category" in item
                assert "priority" in item

            # Verify Groq was called with correct parameters
            mock_groq.assert_called_once()
            call_args = mock_groq.call_args[0]
            assert "Paris, France" in call_args[0]
            assert "5 days" in call_args[0]
            assert "plane" in call_args[0]
            assert "vacation" in call_args[0]

    def test_authentication_required_for_checklist_generation(self, client):
        """Test that authentication is required for checklist generation."""
        trip_data = {
            "location": "Tokyo, Japan",
            "days": 3,
            "transport": "train",
            "occasion": "business"
        }

        # Request without authentication
        response = client.post("/api/v1/generate-checklist", json=trip_data)
        
        # Should return 401 Unauthorized
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]

    def test_invalid_trip_data_validation(self, client, auth_headers):
        """Test validation of invalid trip data."""
        invalid_data_sets = [
            # Missing required fields
            {"days": 5, "transport": "plane", "occasion": "vacation"},
            {"location": "Berlin", "transport": "plane", "occasion": "vacation"},
            {"location": "Berlin", "days": 5, "occasion": "vacation"},
            {"location": "Berlin", "days": 5, "transport": "plane"},
            
            # Invalid field values
            {"location": "", "days": 5, "transport": "plane", "occasion": "vacation"},
            {"location": "Berlin", "days": 0, "transport": "plane", "occasion": "vacation"},
            {"location": "Berlin", "days": -1, "transport": "plane", "occasion": "vacation"},
            {"location": "Berlin", "days": 5, "transport": "invalid", "occasion": "vacation"},
            {"location": "A" * 101, "days": 5, "transport": "plane", "occasion": "vacation"},
        ]

        for invalid_data in invalid_data_sets:
            response = client.post(
                "/api/v1/generate-checklist",
                json=invalid_data,
                headers=auth_headers
            )
            assert response.status_code == 422, f"Failed for data: {invalid_data}"

    def test_groq_api_error_handling(self, client, auth_headers):
        """Test handling of Groq API errors."""
        trip_data = {
            "location": "Sydney, Australia",
            "days": 7,
            "transport": "plane",
            "occasion": "vacation"
        }

        # Mock Groq API failure
        with patch.object(GroqClient, 'generate_completion', new_callable=AsyncMock) as mock_groq:
            mock_groq.side_effect = Exception("Groq API error")

            response = client.post(
                "/api/v1/generate-checklist",
                json=trip_data,
                headers=auth_headers
            )

            # Should return 500 Internal Server Error
            assert response.status_code == 500
            assert "error" in response.json()

    def test_rate_limiting_behavior(self, client, auth_headers):
        """Test rate limiting behavior with multiple requests."""
        trip_data = {
            "location": "London, UK",
            "days": 4,
            "transport": "train",
            "occasion": "business"
        }

        # Mock successful Groq response
        mock_response = "Test checklist items"
        
        with patch.object(GroqClient, 'generate_completion', new_callable=AsyncMock) as mock_groq:
            mock_groq.return_value = mock_response

            # Make multiple rapid requests
            responses = []
            for i in range(10):
                response = client.post(
                    "/api/v1/generate-checklist",
                    json=trip_data,
                    headers=auth_headers
                )
                responses.append(response)

            # Most requests should succeed, but some might be rate limited
            success_count = sum(1 for r in responses if r.status_code == 200)
            rate_limited_count = sum(1 for r in responses if r.status_code == 429)

            # At least some requests should succeed
            assert success_count > 0
            
            # If rate limiting is implemented, some might be limited
            # This is optional depending on implementation
            assert success_count + rate_limited_count == 10

    def test_different_transport_modes(self, client, auth_headers):
        """Test checklist generation for different transport modes."""
        transport_modes = ["car", "train", "plane", "bus", "other"]
        
        mock_response = "Test checklist for transport mode"
        
        with patch.object(GroqClient, 'generate_completion', new_callable=AsyncMock) as mock_groq:
            mock_groq.return_value = mock_response

            for transport in transport_modes:
                trip_data = {
                    "location": f"Test City for {transport}",
                    "days": 3,
                    "transport": transport,
                    "occasion": "vacation"
                }

                response = client.post(
                    "/api/v1/generate-checklist",
                    json=trip_data,
                    headers=auth_headers
                )

                assert response.status_code == 200, f"Failed for transport: {transport}"
                
                # Verify that transport mode is included in the prompt
                call_args = mock_groq.call_args[0][0]
                assert transport in call_args.lower()

    def test_long_trip_duration_handling(self, client, auth_headers):
        """Test handling of very long trip durations."""
        trip_data = {
            "location": "World Tour",
            "days": 365,  # One year trip
            "transport": "plane",
            "occasion": "adventure"
        }

        mock_response = "Extended travel checklist"
        
        with patch.object(GroqClient, 'generate_completion', new_callable=AsyncMock) as mock_groq:
            mock_groq.return_value = mock_response

            response = client.post(
                "/api/v1/generate-checklist",
                json=trip_data,
                headers=auth_headers
            )

            assert response.status_code == 200
            
            # Verify that long duration is handled in the prompt
            call_args = mock_groq.call_args[0][0]
            assert "365" in call_args or "year" in call_args.lower()

    def test_special_characters_in_location(self, client, auth_headers):
        """Test handling of special characters in location names."""
        locations_with_special_chars = [
            "São Paulo, Brazil",
            "Zürich, Switzerland",
            "Москва, Russia",
            "東京, Japan",
            "القاهرة, Egypt"
        ]

        mock_response = "International location checklist"
        
        with patch.object(GroqClient, 'generate_completion', new_callable=AsyncMock) as mock_groq:
            mock_groq.return_value = mock_response

            for location in locations_with_special_chars:
                trip_data = {
                    "location": location,
                    "days": 5,
                    "transport": "plane",
                    "occasion": "vacation"
                }

                response = client.post(
                    "/api/v1/generate-checklist",
                    json=trip_data,
                    headers=auth_headers
                )

                assert response.status_code == 200, f"Failed for location: {location}"

    def test_concurrent_requests_handling(self, client, auth_headers):
        """Test handling of concurrent requests."""
        import threading
        import time

        trip_data = {
            "location": "Concurrent Test City",
            "days": 3,
            "transport": "car",
            "occasion": "business"
        }

        mock_response = "Concurrent test checklist"
        results = []

        def make_request():
            with patch.object(GroqClient, 'generate_completion', new_callable=AsyncMock) as mock_groq:
                mock_groq.return_value = mock_response
                
                response = client.post(
                    "/api/v1/generate-checklist",
                    json=trip_data,
                    headers=auth_headers
                )
                results.append(response.status_code)

        # Create multiple threads to make concurrent requests
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All requests should succeed
        assert len(results) == 5
        assert all(status == 200 for status in results)

    def test_health_check_endpoint(self, client):
        """Test the health check endpoint."""
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_malformed_json_handling(self, client, auth_headers):
        """Test handling of malformed JSON requests."""
        # Send malformed JSON
        response = client.post(
            "/api/v1/generate-checklist",
            data="invalid json",
            headers={**auth_headers, "Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_empty_request_body(self, client, auth_headers):
        """Test handling of empty request body."""
        response = client.post(
            "/api/v1/generate-checklist",
            json={},
            headers=auth_headers
        )

        assert response.status_code == 422

    def test_sql_injection_prevention(self, client, auth_headers):
        """Test that SQL injection attempts are prevented."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "'; DELETE FROM checklists; --"
        ]

        for malicious_input in malicious_inputs:
            trip_data = {
                "location": malicious_input,
                "days": 5,
                "transport": "plane",
                "occasion": "vacation"
            }

            # Should either validate and reject, or sanitize the input
            response = client.post(
                "/api/v1/generate-checklist",
                json=trip_data,
                headers=auth_headers
            )

            # Should not cause a server error
            assert response.status_code in [200, 422]

    def test_xss_prevention(self, client, auth_headers):
        """Test that XSS attempts are prevented."""
        xss_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>"
        ]

        mock_response = "Safe checklist response"
        
        with patch.object(GroqClient, 'generate_completion', new_callable=AsyncMock) as mock_groq:
            mock_groq.return_value = mock_response

            for xss_input in xss_inputs:
                trip_data = {
                    "location": xss_input,
                    "days": 5,
                    "transport": "plane",
                    "occasion": "vacation"
                }

                response = client.post(
                    "/api/v1/generate-checklist",
                    json=trip_data,
                    headers=auth_headers
                )

                # Should handle safely
                assert response.status_code in [200, 422]
                
                if response.status_code == 200:
                    # Response should not contain the malicious script
                    response_text = response.text
                    assert "<script>" not in response_text
                    assert "javascript:" not in response_text