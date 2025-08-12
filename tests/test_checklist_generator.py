"""
Unit tests for the checklist generation service.

Tests cover prompt formatting, AI response parsing, fallback logic,
and integration with the Groq client.
"""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from app.models.trip import TripDataResponse, TransportType
from app.models.checklist import ChecklistGenerationResponse, PriorityLevel
from app.services.checklist_generator import (
    ChecklistGeneratorService,
    ChecklistGenerationError,
    create_checklist_generator
)
from app.services.groq_client import GroqClient, GroqAPIError, GroqRateLimitError


class TestChecklistGeneratorService:
    """Test cases for ChecklistGeneratorService class."""
    
    @pytest.fixture
    def mock_groq_client(self):
        """Create a mock Groq client."""
        client = Mock(spec=GroqClient)
        client.generate_completion = AsyncMock()
        return client
    
    @pytest.fixture
    def generator_service(self, mock_groq_client):
        """Create a ChecklistGeneratorService instance for testing."""
        return ChecklistGeneratorService(mock_groq_client)
    
    @pytest.fixture
    def sample_trip_data(self):
        """Create sample trip data for testing."""
        return TripDataResponse(
            location="Paris, France",
            days=5,
            transport=TransportType.PLANE,
            occasion="vacation",
            notes="First time visiting Europe",
            preferences=["lightweight", "comfortable"]
        )
    
    @pytest.fixture
    def sample_ai_response(self):
        """Create a sample AI response JSON."""
        return json.dumps({
            "items": [
                {
                    "text": "Passport",
                    "category": "Documents",
                    "priority": "high"
                },
                {
                    "text": "Comfortable walking shoes",
                    "category": "Clothing",
                    "priority": "medium"
                },
                {
                    "text": "Camera",
                    "category": "Electronics",
                    "priority": "low"
                },
                {
                    "text": "Sunscreen",
                    "category": "Health",
                    "priority": "medium"
                },
                {
                    "text": "Travel adapter",
                    "category": "Electronics",
                    "priority": "high"
                }
            ]
        })
    
    @pytest.mark.asyncio
    async def test_generate_checklist_success(self, generator_service, mock_groq_client, sample_trip_data, sample_ai_response):
        """Test successful checklist generation."""
        mock_groq_client.generate_completion.return_value = sample_ai_response
        
        result = await generator_service.generate_checklist(sample_trip_data)
        
        assert isinstance(result, ChecklistGenerationResponse)
        assert result.trip_data == sample_trip_data
        assert len(result.items) == 5
        assert result.items[0].text == "Passport"
        assert result.items[0].category == "Documents"
        assert result.items[0].priority == PriorityLevel.HIGH
        assert result.items[0].user_added is False
        
        mock_groq_client.generate_completion.assert_called_once()
        call_args = mock_groq_client.generate_completion.call_args
        assert "Paris, France" in call_args.kwargs["prompt"]
        assert "5 day" in call_args.kwargs["prompt"]
        assert "plane" in call_args.kwargs["prompt"]
    
    @pytest.mark.asyncio
    async def test_generate_checklist_with_rate_limit_fallback(self, generator_service, mock_groq_client, sample_trip_data):
        """Test fallback when rate limit is exceeded."""
        mock_groq_client.generate_completion.side_effect = GroqRateLimitError("Rate limit exceeded")
        
        result = await generator_service.generate_checklist(sample_trip_data)
        
        assert isinstance(result, ChecklistGenerationResponse)
        assert result.trip_data == sample_trip_data
        assert len(result.items) > 0  # Should have fallback items
        # Check that some items are transport-specific
        item_texts = [item.text for item in result.items]
        assert any("passport" in text.lower() or "boarding" in text.lower() for text in item_texts)
    
    @pytest.mark.asyncio
    async def test_generate_checklist_with_api_error_fallback(self, generator_service, mock_groq_client, sample_trip_data):
        """Test fallback when API error occurs."""
        mock_groq_client.generate_completion.side_effect = GroqAPIError("API error")
        
        result = await generator_service.generate_checklist(sample_trip_data)
        
        assert isinstance(result, ChecklistGenerationResponse)
        assert result.trip_data == sample_trip_data
        assert len(result.items) > 0  # Should have fallback items
    
    @pytest.mark.asyncio
    async def test_generate_checklist_with_insufficient_ai_items(self, generator_service, mock_groq_client, sample_trip_data):
        """Test fallback when AI returns too few items."""
        insufficient_response = json.dumps({
            "items": [
                {"text": "Passport", "category": "Documents", "priority": "high"},
                {"text": "Shoes", "category": "Clothing", "priority": "medium"}
            ]
        })
        mock_groq_client.generate_completion.return_value = insufficient_response
        
        result = await generator_service.generate_checklist(sample_trip_data)
        
        assert isinstance(result, ChecklistGenerationResponse)
        assert len(result.items) > 2  # Should use fallback items
    
    @pytest.mark.asyncio
    async def test_generate_checklist_with_unexpected_error(self, generator_service, mock_groq_client, sample_trip_data):
        """Test error handling for unexpected errors."""
        mock_groq_client.generate_completion.side_effect = Exception("Unexpected error")
        
        with pytest.raises(ChecklistGenerationError, match="Failed to generate checklist"):
            await generator_service.generate_checklist(sample_trip_data)
    
    def test_format_prompt_basic(self, generator_service, sample_trip_data):
        """Test basic prompt formatting."""
        prompt = generator_service._format_prompt(sample_trip_data)
        
        assert "Paris, France" in prompt
        assert "5 day" in prompt
        assert "plane" in prompt
        assert "vacation" in prompt
        assert "First time visiting Europe" in prompt
        assert "lightweight" in prompt
        assert "comfortable" in prompt
        assert "JSON response" in prompt
        assert "15-25 relevant items" in prompt
    
    def test_format_prompt_minimal_data(self, generator_service):
        """Test prompt formatting with minimal trip data."""
        minimal_trip = TripDataResponse(
            location="Tokyo",
            days=3,
            transport=TransportType.TRAIN,
            occasion="business"
        )
        
        prompt = generator_service._format_prompt(minimal_trip)
        
        assert "Tokyo" in prompt
        assert "3 day" in prompt
        assert "train" in prompt
        assert "business" in prompt
        assert "JSON response" in prompt
    
    def test_parse_ai_response_success(self, generator_service, sample_ai_response):
        """Test successful AI response parsing."""
        items = generator_service._parse_ai_response(sample_ai_response)
        
        assert len(items) == 5
        assert items[0].text == "Passport"
        assert items[0].category == "Documents"
        assert items[0].priority == PriorityLevel.HIGH
        assert items[0].user_added is False
        assert items[0].checked is False
    
    def test_parse_ai_response_with_markdown(self, generator_service):
        """Test parsing AI response with markdown formatting."""
        markdown_response = f"```json\n{json.dumps({'items': [{'text': 'Test item', 'category': 'Test', 'priority': 'high'}]})}\n```"
        
        items = generator_service._parse_ai_response(markdown_response)
        
        assert len(items) == 1
        assert items[0].text == "Test item"
        assert items[0].category == "Test"
        assert items[0].priority == PriorityLevel.HIGH
    
    def test_parse_ai_response_invalid_json(self, generator_service):
        """Test parsing invalid JSON response."""
        invalid_response = "This is not valid JSON"
        
        items = generator_service._parse_ai_response(invalid_response)
        
        assert items == []
    
    def test_parse_ai_response_missing_fields(self, generator_service):
        """Test parsing response with missing required fields."""
        incomplete_response = json.dumps({
            "items": [
                {"text": "Valid item", "category": "Test", "priority": "high"},
                {"text": "Missing category", "priority": "medium"},  # Missing category
                {"category": "Missing text", "priority": "low"}  # Missing text
            ]
        })
        
        items = generator_service._parse_ai_response(incomplete_response)
        
        assert len(items) == 1  # Only the valid item should be parsed
        assert items[0].text == "Valid item"
    
    def test_parse_priority_variations(self, generator_service):
        """Test priority parsing with different input variations."""
        assert generator_service._parse_priority("high") == PriorityLevel.HIGH
        assert generator_service._parse_priority("HIGH") == PriorityLevel.HIGH
        assert generator_service._parse_priority("essential") == PriorityLevel.HIGH
        assert generator_service._parse_priority("critical") == PriorityLevel.HIGH
        
        assert generator_service._parse_priority("low") == PriorityLevel.LOW
        assert generator_service._parse_priority("optional") == PriorityLevel.LOW
        assert generator_service._parse_priority("nice-to-have") == PriorityLevel.LOW
        
        assert generator_service._parse_priority("medium") == PriorityLevel.MEDIUM
        assert generator_service._parse_priority("unknown") == PriorityLevel.MEDIUM
        assert generator_service._parse_priority("") == PriorityLevel.MEDIUM
    
    def test_generate_fallback_items_plane(self, generator_service):
        """Test fallback item generation for plane travel."""
        trip_data = TripDataResponse(
            location="London",
            days=4,
            transport=TransportType.PLANE,
            occasion="vacation"
        )
        
        items = generator_service._generate_fallback_items(trip_data)
        
        assert len(items) > 0
        item_texts = [item.text.lower() for item in items]
        
        # Should include plane-specific items
        assert any("boarding" in text or "passport" in text for text in item_texts)
        # Should include general essentials
        assert any("underwear" in text for text in item_texts)
        assert any("toothbrush" in text for text in item_texts)
    
    def test_generate_fallback_items_car(self, generator_service):
        """Test fallback item generation for car travel."""
        trip_data = TripDataResponse(
            location="San Francisco",
            days=3,
            transport=TransportType.CAR,
            occasion="business"
        )
        
        items = generator_service._generate_fallback_items(trip_data)
        
        assert len(items) > 0
        item_texts = [item.text.lower() for item in items]
        
        # Should include car-specific items
        assert any("driver's license" in text or "car charger" in text for text in item_texts)
        # Should not include plane-specific items
        assert not any("boarding" in text for text in item_texts)
    
    def test_generate_fallback_items_long_trip(self, generator_service):
        """Test fallback item generation for long trips."""
        trip_data = TripDataResponse(
            location="Australia",
            days=14,  # Long trip
            transport=TransportType.PLANE,
            occasion="vacation"
        )
        
        items = generator_service._generate_fallback_items(trip_data)
        
        assert len(items) > 0
        item_texts = [item.text.lower() for item in items]
        
        # Should include long-trip specific items
        assert any("laundry" in text or "first aid" in text for text in item_texts)
    
    def test_should_skip_item_for_transport(self, generator_service):
        """Test transport-specific item filtering."""
        car_item = {"text": "Car registration", "category": "Documents", "priority": "high"}
        plane_item = {"text": "Boarding pass", "category": "Documents", "priority": "high"}
        
        # Car item should be skipped for plane travel
        assert generator_service._should_skip_item_for_transport(car_item, TransportType.PLANE) is True
        assert generator_service._should_skip_item_for_transport(car_item, TransportType.CAR) is False
        
        # Plane item should be skipped for car travel
        assert generator_service._should_skip_item_for_transport(plane_item, TransportType.CAR) is True
        assert generator_service._should_skip_item_for_transport(plane_item, TransportType.PLANE) is False
    
    def test_get_transport_specific_items_plane(self, generator_service):
        """Test getting plane-specific items."""
        items = generator_service._get_transport_specific_items(TransportType.PLANE)
        
        assert len(items) > 0
        item_texts = [item.text.lower() for item in items]
        assert any("boarding" in text or "passport" in text for text in item_texts)
        assert any("toiletries" in text for text in item_texts)
    
    def test_get_transport_specific_items_car(self, generator_service):
        """Test getting car-specific items."""
        items = generator_service._get_transport_specific_items(TransportType.CAR)
        
        assert len(items) > 0
        item_texts = [item.text.lower() for item in items]
        assert any("driver's license" in text or "car" in text for text in item_texts)
    
    def test_get_long_trip_items(self, generator_service):
        """Test getting long trip specific items."""
        items = generator_service._get_long_trip_items()
        
        assert len(items) > 0
        item_texts = [item.text.lower() for item in items]
        assert any("underwear" in text or "laundry" in text or "first aid" in text for text in item_texts)
    
    def test_create_fallback_response(self, generator_service, sample_trip_data):
        """Test creating fallback response."""
        response = generator_service._create_fallback_response(sample_trip_data)
        
        assert isinstance(response, ChecklistGenerationResponse)
        assert response.trip_data == sample_trip_data
        assert len(response.items) > 0
        assert response.generated_at is not None
        assert response.id is not None
    
    def test_load_fallback_items(self, generator_service):
        """Test loading fallback items."""
        items = generator_service._load_fallback_items()
        
        assert len(items) > 0
        assert all(isinstance(item, dict) for item in items)
        assert all("text" in item and "category" in item and "priority" in item for item in items)
        
        # Check for essential categories
        categories = [item["category"] for item in items]
        assert "Documents" in categories
        assert "Clothing" in categories
        assert "Health" in categories or "Toiletries" in categories


class TestCreateChecklistGenerator:
    """Test the factory function for creating checklist generator."""
    
    def test_create_checklist_generator(self):
        """Test factory function creates service correctly."""
        mock_client = Mock(spec=GroqClient)
        service = create_checklist_generator(mock_client)
        
        assert isinstance(service, ChecklistGeneratorService)
        assert service.groq_client == mock_client


@pytest.mark.integration
class TestChecklistGeneratorIntegration:
    """Integration tests for ChecklistGeneratorService."""
    
    @pytest.mark.skip(reason="Requires real Groq API key and network access")
    async def test_real_checklist_generation(self):
        """Test with real Groq API (skipped by default)."""
        # This test would require a real API key and should only be run
        # in integration test environments
        from app.services.groq_client import GroqClient
        
        real_client = GroqClient(api_key="real-api-key")
        service = ChecklistGeneratorService(real_client)
        
        trip_data = TripDataResponse(
            location="New York",
            days=3,
            transport=TransportType.PLANE,
            occasion="business"
        )
        
        result = await service.generate_checklist(trip_data)
        assert isinstance(result, ChecklistGenerationResponse)
        assert len(result.items) > 0