"""
Tests for checklist-related Pydantic models.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models.checklist import (
    ChecklistItemRequest,
    ChecklistItemResponse,
    ChecklistItemUpdate,
    ChecklistRequest,
    ChecklistResponse,
    ChecklistGenerationRequest,
    ChecklistGenerationResponse,
    PriorityLevel
)
from app.models.trip import TripDataResponse, TransportType


class TestChecklistItemRequest:
    """Test cases for ChecklistItemRequest model."""
    
    def test_valid_checklist_item_request(self):
        """Test creating a valid checklist item request."""
        data = {
            "text": "Pack sunscreen",
            "category": "Health & Safety",
            "checked": False,
            "priority": "high",
            "user_added": True
        }
        
        item_request = ChecklistItemRequest(**data)
        
        assert item_request.text == "Pack sunscreen"
        assert item_request.category == "Health & Safety"
        assert item_request.checked is False
        assert item_request.priority == PriorityLevel.HIGH
        assert item_request.user_added is True
    
    def test_minimal_checklist_item_request(self):
        """Test creating a minimal checklist item request."""
        data = {
            "text": "Pack passport",
            "category": "Documents"
        }
        
        item_request = ChecklistItemRequest(**data)
        
        assert item_request.text == "Pack passport"
        assert item_request.category == "Documents"
        assert item_request.checked is False  # default
        assert item_request.priority == PriorityLevel.MEDIUM  # default
        assert item_request.user_added is True  # default
    
    def test_string_trimming(self):
        """Test that string fields are properly trimmed."""
        data = {
            "text": "  Pack camera  ",
            "category": "  Electronics  "
        }
        
        item_request = ChecklistItemRequest(**data)
        
        assert item_request.text == "Pack camera"
        assert item_request.category == "Electronics"
    
    def test_text_validation(self):
        """Test text field validation."""
        base_data = {"category": "Test"}
        
        # Test missing text
        with pytest.raises(ValidationError) as exc_info:
            ChecklistItemRequest(**base_data)
        assert "text" in str(exc_info.value)
        
        # Test empty text
        with pytest.raises(ValidationError) as exc_info:
            ChecklistItemRequest(text="", **base_data)
        assert "at least 2 characters" in str(exc_info.value)
        
        # Test text too short
        with pytest.raises(ValidationError) as exc_info:
            ChecklistItemRequest(text="A", **base_data)
        assert "at least 2 characters" in str(exc_info.value)
        
        # Test text too long
        with pytest.raises(ValidationError) as exc_info:
            ChecklistItemRequest(text="A" * 201, **base_data)
        assert "at most 200 characters" in str(exc_info.value)
    
    def test_category_validation(self):
        """Test category field validation."""
        base_data = {"text": "Test item"}
        
        # Test missing category
        with pytest.raises(ValidationError) as exc_info:
            ChecklistItemRequest(**base_data)
        assert "category" in str(exc_info.value)
        
        # Test empty category
        with pytest.raises(ValidationError) as exc_info:
            ChecklistItemRequest(category="", **base_data)
        assert "at least 1 character" in str(exc_info.value)
        
        # Test category too long
        with pytest.raises(ValidationError) as exc_info:
            ChecklistItemRequest(category="A" * 51, **base_data)
        assert "at most 50 characters" in str(exc_info.value)
    
    def test_priority_validation(self):
        """Test priority field validation."""
        base_data = {
            "text": "Test item",
            "category": "Test"
        }
        
        # Test invalid priority
        with pytest.raises(ValidationError) as exc_info:
            ChecklistItemRequest(priority="urgent", **base_data)
        assert "Input should be" in str(exc_info.value)
        
        # Test all valid priorities
        for priority in ["high", "medium", "low"]:
            item_request = ChecklistItemRequest(priority=priority, **base_data)
            assert item_request.priority.value == priority


class TestChecklistItemResponse:
    """Test cases for ChecklistItemResponse model."""
    
    def test_valid_checklist_item_response(self):
        """Test creating a valid checklist item response."""
        now = datetime.utcnow()
        data = {
            "id": "item-123",
            "text": "Pack toothbrush",
            "category": "Personal Care",
            "checked": True,
            "priority": PriorityLevel.MEDIUM,
            "user_added": False,
            "created_at": now,
            "updated_at": now
        }
        
        item_response = ChecklistItemResponse(**data)
        
        assert item_response.id == "item-123"
        assert item_response.text == "Pack toothbrush"
        assert item_response.category == "Personal Care"
        assert item_response.checked is True
        assert item_response.priority == PriorityLevel.MEDIUM
        assert item_response.user_added is False
        assert item_response.created_at == now
        assert item_response.updated_at == now


class TestChecklistItemUpdate:
    """Test cases for ChecklistItemUpdate model."""
    
    def test_valid_checklist_item_update(self):
        """Test creating a valid checklist item update."""
        data = {
            "text": "Updated item text",
            "category": "Updated Category",
            "checked": True,
            "priority": "low"
        }
        
        item_update = ChecklistItemUpdate(**data)
        
        assert item_update.text == "Updated item text"
        assert item_update.category == "Updated Category"
        assert item_update.checked is True
        assert item_update.priority == PriorityLevel.LOW
    
    def test_partial_checklist_item_update(self):
        """Test creating a partial checklist item update."""
        data = {"checked": True}
        
        item_update = ChecklistItemUpdate(**data)
        
        assert item_update.text is None
        assert item_update.category is None
        assert item_update.checked is True
        assert item_update.priority is None
    
    def test_empty_checklist_item_update(self):
        """Test creating an empty checklist item update."""
        item_update = ChecklistItemUpdate()
        
        assert item_update.text is None
        assert item_update.category is None
        assert item_update.checked is None
        assert item_update.priority is None


class TestChecklistRequest:
    """Test cases for ChecklistRequest model."""
    
    def test_valid_checklist_request(self):
        """Test creating a valid checklist request."""
        trip_data = TripDataResponse(
            location="Sydney",
            days=10,
            transport=TransportType.PLANE,
            occasion="vacation"
        )
        
        items = [
            ChecklistItemRequest(
                text="Pack swimwear",
                category="Clothing"
            ),
            ChecklistItemRequest(
                text="Pack sunscreen",
                category="Health & Safety"
            )
        ]
        
        checklist_request = ChecklistRequest(
            trip_data=trip_data,
            items=items
        )
        
        assert checklist_request.trip_data == trip_data
        assert len(checklist_request.items) == 2
        assert checklist_request.items[0].text == "Pack swimwear"
        assert checklist_request.items[1].text == "Pack sunscreen"
    
    def test_minimal_checklist_request(self):
        """Test creating a minimal checklist request."""
        trip_data = TripDataResponse(
            location="Melbourne",
            days=3,
            transport=TransportType.CAR,
            occasion="business"
        )
        
        checklist_request = ChecklistRequest(trip_data=trip_data)
        
        assert checklist_request.trip_data == trip_data
        assert checklist_request.items == []
    
    def test_too_many_items(self):
        """Test validation when too many items are provided."""
        trip_data = TripDataResponse(
            location="Perth",
            days=5,
            transport=TransportType.PLANE,
            occasion="vacation"
        )
        
        items = [
            ChecklistItemRequest(text=f"Item {i}", category="Test")
            for i in range(101)
        ]
        
        with pytest.raises(ValidationError) as exc_info:
            ChecklistRequest(trip_data=trip_data, items=items)
        assert "at most 100" in str(exc_info.value)


class TestChecklistResponse:
    """Test cases for ChecklistResponse model."""
    
    def test_valid_checklist_response(self):
        """Test creating a valid checklist response."""
        now = datetime.utcnow()
        
        trip_data = TripDataResponse(
            location="Brisbane",
            days=7,
            transport=TransportType.TRAIN,
            occasion="leisure"
        )
        
        items = [
            ChecklistItemResponse(
                id="item-1",
                text="Pack hiking boots",
                category="Footwear",
                checked=False,
                priority=PriorityLevel.HIGH,
                user_added=True,
                created_at=now,
                updated_at=now
            )
        ]
        
        checklist_response = ChecklistResponse(
            id="checklist-123",
            trip_data=trip_data,
            items=items,
            created_at=now,
            updated_at=now,
            synced=True
        )
        
        assert checklist_response.id == "checklist-123"
        assert checklist_response.trip_data == trip_data
        assert len(checklist_response.items) == 1
        assert checklist_response.items[0].text == "Pack hiking boots"
        assert checklist_response.created_at == now
        assert checklist_response.updated_at == now
        assert checklist_response.synced is True


class TestChecklistGenerationRequest:
    """Test cases for ChecklistGenerationRequest model."""
    
    def test_valid_checklist_generation_request(self):
        """Test creating a valid checklist generation request."""
        trip_data = TripDataResponse(
            location="Adelaide",
            days=4,
            transport=TransportType.BUS,
            occasion="conference",
            notes="Tech conference with networking events",
            preferences=["business attire", "tech gadgets"]
        )
        
        generation_request = ChecklistGenerationRequest(trip_data=trip_data)
        
        assert generation_request.trip_data == trip_data


class TestChecklistGenerationResponse:
    """Test cases for ChecklistGenerationResponse model."""
    
    def test_valid_checklist_generation_response(self):
        """Test creating a valid checklist generation response."""
        now = datetime.utcnow()
        
        trip_data = TripDataResponse(
            location="Darwin",
            days=6,
            transport=TransportType.PLANE,
            occasion="adventure"
        )
        
        items = [
            ChecklistItemResponse(
                id="gen-item-1",
                text="Pack insect repellent",
                category="Health & Safety",
                checked=False,
                priority=PriorityLevel.HIGH,
                user_added=False,
                created_at=now,
                updated_at=now
            ),
            ChecklistItemResponse(
                id="gen-item-2",
                text="Pack lightweight clothing",
                category="Clothing",
                checked=False,
                priority=PriorityLevel.MEDIUM,
                user_added=False,
                created_at=now,
                updated_at=now
            )
        ]
        
        generation_response = ChecklistGenerationResponse(
            id="generated-checklist-456",
            items=items,
            generated_at=now,
            trip_data=trip_data
        )
        
        assert generation_response.id == "generated-checklist-456"
        assert len(generation_response.items) == 2
        assert generation_response.items[0].text == "Pack insect repellent"
        assert generation_response.items[1].text == "Pack lightweight clothing"
        assert generation_response.generated_at == now
        assert generation_response.trip_data == trip_data


class TestPriorityLevel:
    """Test cases for PriorityLevel enum."""
    
    def test_priority_level_values(self):
        """Test that all priority levels have correct values."""
        assert PriorityLevel.HIGH.value == "high"
        assert PriorityLevel.MEDIUM.value == "medium"
        assert PriorityLevel.LOW.value == "low"
    
    def test_priority_level_from_string(self):
        """Test creating priority levels from strings."""
        assert PriorityLevel("high") == PriorityLevel.HIGH
        assert PriorityLevel("medium") == PriorityLevel.MEDIUM
        assert PriorityLevel("low") == PriorityLevel.LOW
    
    def test_invalid_priority_level(self):
        """Test that invalid priority levels raise ValueError."""
        with pytest.raises(ValueError):
            PriorityLevel("urgent")