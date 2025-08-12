"""
Integration tests for checklist generation functionality.

These tests focus on the service integration without complex authentication mocking.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from app.services import groq_client, create_checklist_generator
from app.services.checklist_generator import ChecklistGenerationError
from app.services.groq_client import GroqAPIError, GroqRateLimitError
from app.models.trip import TripDataResponse, TransportType
from app.models.checklist import ChecklistGenerationRequest


class TestChecklistServiceIntegration:
    """Test checklist service integration."""
    
    @pytest.fixture
    def sample_trip_data(self):
        """Create sample trip data."""
        return TripDataResponse(
            location="Paris, France",
            days=5,
            transport=TransportType.PLANE,
            occasion="vacation",
            notes="First time visiting Europe",
            preferences=["lightweight", "comfortable"]
        )
    
    def test_create_checklist_generator(self):
        """Test that checklist generator can be created."""
        generator = create_checklist_generator(groq_client)
        assert generator is not None
        assert hasattr(generator, 'generate_checklist')
    
    @pytest.mark.asyncio
    async def test_checklist_generation_with_mock_groq(self, sample_trip_data):
        """Test checklist generation with mocked Groq client."""
        # Create a mock Groq client with a complete response
        mock_response = '''
        {
            "items": [
                {"text": "Passport", "category": "Documents", "priority": "high"},
                {"text": "Comfortable walking shoes", "category": "Clothing", "priority": "medium"},
                {"text": "Phone charger", "category": "Electronics", "priority": "medium"},
                {"text": "Sunscreen", "category": "Health", "priority": "medium"},
                {"text": "Travel adapter", "category": "Electronics", "priority": "high"},
                {"text": "Underwear", "category": "Clothing", "priority": "high"}
            ]
        }
        '''
        
        mock_groq_client = Mock()
        mock_groq_client.generate_completion = AsyncMock(return_value=mock_response)
        
        # Create generator with mock client
        generator = create_checklist_generator(mock_groq_client)
        
        # Generate checklist
        result = await generator.generate_checklist(sample_trip_data)
        
        # Verify result
        assert result is not None
        assert result.trip_data == sample_trip_data
        assert len(result.items) == 6  # Should have 6 items from the mock response
        assert result.items[0].text == "Passport"
        assert result.items[0].category == "Documents"
    
    @pytest.mark.asyncio
    async def test_checklist_generation_fallback(self, sample_trip_data):
        """Test checklist generation fallback when AI fails."""
        # Create a mock Groq client that fails
        mock_groq_client = Mock()
        mock_groq_client.generate_completion = AsyncMock(side_effect=GroqAPIError("API Error"))
        
        # Create generator with mock client
        generator = create_checklist_generator(mock_groq_client)
        
        # Generate checklist (should use fallback)
        result = await generator.generate_checklist(sample_trip_data)
        
        # Verify fallback result
        assert result is not None
        assert result.trip_data == sample_trip_data
        assert len(result.items) > 0
        
        # Should contain some essential items
        item_texts = [item.text.lower() for item in result.items]
        assert any("passport" in text for text in item_texts)
    
    @pytest.mark.asyncio
    async def test_checklist_generation_rate_limit_fallback(self, sample_trip_data):
        """Test checklist generation fallback when rate limited."""
        # Create a mock Groq client that hits rate limit
        mock_groq_client = Mock()
        mock_groq_client.generate_completion = AsyncMock(side_effect=GroqRateLimitError("Rate limit"))
        
        # Create generator with mock client
        generator = create_checklist_generator(mock_groq_client)
        
        # Generate checklist (should use fallback)
        result = await generator.generate_checklist(sample_trip_data)
        
        # Verify fallback result
        assert result is not None
        assert result.trip_data == sample_trip_data
        assert len(result.items) > 0
    
    def test_checklist_request_model_validation(self):
        """Test that the request model validates correctly."""
        # Valid request
        valid_data = {
            "location": "Tokyo, Japan",
            "days": 7,
            "transport": TransportType.TRAIN,
            "occasion": "business"
        }
        
        trip_data = TripDataResponse(**valid_data)
        request = ChecklistGenerationRequest(trip_data=trip_data)
        
        assert request.trip_data.location == "Tokyo, Japan"
        assert request.trip_data.days == 7
        assert request.trip_data.transport == TransportType.TRAIN
    
    def test_different_transport_types(self):
        """Test that all transport types work correctly."""
        transport_types = [
            TransportType.CAR,
            TransportType.TRAIN,
            TransportType.PLANE,
            TransportType.BUS,
            TransportType.OTHER
        ]
        
        for transport in transport_types:
            trip_data = TripDataResponse(
                location="Test Location",
                days=3,
                transport=transport,
                occasion="test"
            )
            
            generator = create_checklist_generator(groq_client)
            assert generator is not None
            
            # Verify the trip data is valid
            assert trip_data.transport == transport
    
    @pytest.mark.asyncio
    async def test_long_trip_items_included(self):
        """Test that long trip items are included for extended trips."""
        # Create a long trip
        long_trip_data = TripDataResponse(
            location="Australia",
            days=14,  # Long trip
            transport=TransportType.PLANE,
            occasion="vacation"
        )
        
        # Create a mock Groq client that fails (to force fallback)
        mock_groq_client = Mock()
        mock_groq_client.generate_completion = AsyncMock(side_effect=GroqAPIError("API Error"))
        
        # Create generator with mock client
        generator = create_checklist_generator(mock_groq_client)
        
        # Generate checklist (should use fallback with long trip items)
        result = await generator.generate_checklist(long_trip_data)
        
        # Verify long trip items are included
        item_texts = [item.text.lower() for item in result.items]
        has_long_trip_items = any(
            "laundry" in text or "first aid" in text or "extra underwear" in text 
            for text in item_texts
        )
        assert has_long_trip_items, f"Long trip items not found in: {item_texts}"
    
    @pytest.mark.asyncio
    async def test_transport_specific_items(self):
        """Test that transport-specific items are included."""
        # Test plane travel
        plane_trip = TripDataResponse(
            location="London",
            days=5,
            transport=TransportType.PLANE,
            occasion="vacation"
        )
        
        # Create a mock Groq client that fails (to force fallback)
        mock_groq_client = Mock()
        mock_groq_client.generate_completion = AsyncMock(side_effect=GroqAPIError("API Error"))
        
        generator = create_checklist_generator(mock_groq_client)
        result = await generator.generate_checklist(plane_trip)
        
        # Should include plane-specific items
        item_texts = [item.text.lower() for item in result.items]
        has_plane_items = any(
            "boarding" in text or "passport" in text or "toiletries" in text
            for text in item_texts
        )
        assert has_plane_items, f"Plane-specific items not found in: {item_texts}"
        
        # Test car travel
        car_trip = TripDataResponse(
            location="San Francisco",
            days=3,
            transport=TransportType.CAR,
            occasion="business"
        )
        
        result = await generator.generate_checklist(car_trip)
        
        # Should include car-specific items
        item_texts = [item.text.lower() for item in result.items]
        has_car_items = any(
            "driver's license" in text or "car" in text
            for text in item_texts
        )
        assert has_car_items, f"Car-specific items not found in: {item_texts}"


@pytest.mark.skip(reason="Requires real Groq API key")
class TestRealGroqIntegration:
    """Tests with real Groq API (skipped by default)."""
    
    @pytest.mark.asyncio
    async def test_real_groq_checklist_generation(self):
        """Test with real Groq API."""
        # This would test with the actual Groq API
        # Only run in integration environments with real API keys
        pass