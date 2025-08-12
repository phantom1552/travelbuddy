"""
Tests for trip-related Pydantic models.
"""
import pytest
from pydantic import ValidationError

from app.models.trip import TripDataRequest, TripDataResponse, TransportType


class TestTripDataRequest:
    """Test cases for TripDataRequest model."""
    
    def test_valid_trip_data_request(self):
        """Test creating a valid trip data request."""
        data = {
            "location": "Paris, France",
            "days": 7,
            "transport": "plane",
            "occasion": "vacation",
            "notes": "First time visiting Europe",
            "preferences": ["museums", "restaurants"]
        }
        
        trip_request = TripDataRequest(**data)
        
        assert trip_request.location == "Paris, France"
        assert trip_request.days == 7
        assert trip_request.transport == TransportType.PLANE
        assert trip_request.occasion == "vacation"
        assert trip_request.notes == "First time visiting Europe"
        assert trip_request.preferences == ["museums", "restaurants"]
    
    def test_minimal_valid_trip_data_request(self):
        """Test creating a minimal valid trip data request."""
        data = {
            "location": "Tokyo",
            "days": 3,
            "transport": "train",
            "occasion": "business"
        }
        
        trip_request = TripDataRequest(**data)
        
        assert trip_request.location == "Tokyo"
        assert trip_request.days == 3
        assert trip_request.transport == TransportType.TRAIN
        assert trip_request.occasion == "business"
        assert trip_request.notes is None
        assert trip_request.preferences is None
    
    def test_string_trimming(self):
        """Test that string fields are properly trimmed."""
        data = {
            "location": "  New York  ",
            "days": 5,
            "transport": "car",
            "occasion": "  sightseeing  ",
            "notes": "  Weekend trip  "
        }
        
        trip_request = TripDataRequest(**data)
        
        assert trip_request.location == "New York"
        assert trip_request.occasion == "sightseeing"
        assert trip_request.notes == "Weekend trip"
    
    def test_location_validation(self):
        """Test location field validation."""
        base_data = {
            "days": 5,
            "transport": "car",
            "occasion": "vacation"
        }
        
        # Test missing location
        with pytest.raises(ValidationError) as exc_info:
            TripDataRequest(**base_data)
        assert "location" in str(exc_info.value)
        
        # Test empty location
        with pytest.raises(ValidationError) as exc_info:
            TripDataRequest(location="", **base_data)
        assert "at least 2 characters" in str(exc_info.value)
        
        # Test location too short
        with pytest.raises(ValidationError) as exc_info:
            TripDataRequest(location="A", **base_data)
        assert "at least 2 characters" in str(exc_info.value)
        
        # Test location too long
        with pytest.raises(ValidationError) as exc_info:
            TripDataRequest(location="A" * 101, **base_data)
        assert "at most 100 characters" in str(exc_info.value)
    
    def test_days_validation(self):
        """Test days field validation."""
        base_data = {
            "location": "London",
            "transport": "plane",
            "occasion": "vacation"
        }
        
        # Test missing days
        with pytest.raises(ValidationError) as exc_info:
            TripDataRequest(**base_data)
        assert "days" in str(exc_info.value)
        
        # Test zero days
        with pytest.raises(ValidationError) as exc_info:
            TripDataRequest(days=0, **base_data)
        assert "greater than or equal to 1" in str(exc_info.value)
        
        # Test negative days
        with pytest.raises(ValidationError) as exc_info:
            TripDataRequest(days=-1, **base_data)
        assert "greater than or equal to 1" in str(exc_info.value)
        
        # Test too many days
        with pytest.raises(ValidationError) as exc_info:
            TripDataRequest(days=366, **base_data)
        assert "less than or equal to 365" in str(exc_info.value)
        
        # Test valid boundary values
        trip_1_day = TripDataRequest(days=1, **base_data)
        assert trip_1_day.days == 1
        
        trip_365_days = TripDataRequest(days=365, **base_data)
        assert trip_365_days.days == 365
    
    def test_transport_validation(self):
        """Test transport field validation."""
        base_data = {
            "location": "Berlin",
            "days": 4,
            "occasion": "conference"
        }
        
        # Test missing transport
        with pytest.raises(ValidationError) as exc_info:
            TripDataRequest(**base_data)
        assert "transport" in str(exc_info.value)
        
        # Test invalid transport
        with pytest.raises(ValidationError) as exc_info:
            TripDataRequest(transport="spaceship", **base_data)
        assert "Input should be" in str(exc_info.value)
        
        # Test all valid transport types
        for transport in ["car", "train", "plane", "bus", "other"]:
            trip_request = TripDataRequest(transport=transport, **base_data)
            assert trip_request.transport.value == transport
    
    def test_occasion_validation(self):
        """Test occasion field validation."""
        base_data = {
            "location": "Rome",
            "days": 6,
            "transport": "plane"
        }
        
        # Test missing occasion
        with pytest.raises(ValidationError) as exc_info:
            TripDataRequest(**base_data)
        assert "occasion" in str(exc_info.value)
        
        # Test empty occasion
        with pytest.raises(ValidationError) as exc_info:
            TripDataRequest(occasion="", **base_data)
        assert "at least 2 characters" in str(exc_info.value)
        
        # Test occasion too short
        with pytest.raises(ValidationError) as exc_info:
            TripDataRequest(occasion="A", **base_data)
        assert "at least 2 characters" in str(exc_info.value)
        
        # Test occasion too long
        with pytest.raises(ValidationError) as exc_info:
            TripDataRequest(occasion="A" * 101, **base_data)
        assert "at most 100 characters" in str(exc_info.value)
    
    def test_notes_validation(self):
        """Test notes field validation."""
        base_data = {
            "location": "Barcelona",
            "days": 4,
            "transport": "train",
            "occasion": "vacation"
        }
        
        # Test valid notes
        trip_request = TripDataRequest(notes="Looking forward to the trip!", **base_data)
        assert trip_request.notes == "Looking forward to the trip!"
        
        # Test empty notes (should be allowed)
        trip_request = TripDataRequest(notes="", **base_data)
        assert trip_request.notes == ""
        
        # Test notes too long
        with pytest.raises(ValidationError) as exc_info:
            TripDataRequest(notes="A" * 501, **base_data)
        assert "at most 500 characters" in str(exc_info.value)
    
    def test_preferences_validation(self):
        """Test preferences field validation."""
        base_data = {
            "location": "Amsterdam",
            "days": 3,
            "transport": "train",
            "occasion": "leisure"
        }
        
        # Test valid preferences
        trip_request = TripDataRequest(
            preferences=["museums", "cafes", "parks"],
            **base_data
        )
        assert trip_request.preferences == ["museums", "cafes", "parks"]
        
        # Test empty preferences list
        trip_request = TripDataRequest(preferences=[], **base_data)
        assert trip_request.preferences is None
        
        # Test preferences with empty strings (should be filtered out)
        trip_request = TripDataRequest(
            preferences=["museums", "", "  ", "cafes"],
            **base_data
        )
        assert trip_request.preferences == ["museums", "cafes"]
        
        # Test preferences with whitespace (should be trimmed)
        trip_request = TripDataRequest(
            preferences=["  museums  ", "  cafes  "],
            **base_data
        )
        assert trip_request.preferences == ["museums", "cafes"]
        
        # Test too many preferences
        with pytest.raises(ValidationError) as exc_info:
            TripDataRequest(
                preferences=["pref"] * 11,
                **base_data
            )
        assert "at most 10" in str(exc_info.value)
        
        # Test preference too long
        with pytest.raises(ValidationError) as exc_info:
            TripDataRequest(
                preferences=["A" * 51],
                **base_data
            )
        assert "less than 50 characters" in str(exc_info.value)
        
        # Test non-string preference
        with pytest.raises(ValidationError) as exc_info:
            TripDataRequest(
                preferences=["museums", 123],
                **base_data
            )
        assert "Input should be a valid string" in str(exc_info.value)


class TestTripDataResponse:
    """Test cases for TripDataResponse model."""
    
    def test_valid_trip_data_response(self):
        """Test creating a valid trip data response."""
        data = {
            "location": "Vienna",
            "days": 5,
            "transport": TransportType.TRAIN,
            "occasion": "cultural trip",
            "notes": "Visit museums and concerts",
            "preferences": ["classical music", "art galleries"]
        }
        
        trip_response = TripDataResponse(**data)
        
        assert trip_response.location == "Vienna"
        assert trip_response.days == 5
        assert trip_response.transport == TransportType.TRAIN
        assert trip_response.occasion == "cultural trip"
        assert trip_response.notes == "Visit museums and concerts"
        assert trip_response.preferences == ["classical music", "art galleries"]
    
    def test_minimal_trip_data_response(self):
        """Test creating a minimal trip data response."""
        data = {
            "location": "Prague",
            "days": 2,
            "transport": TransportType.BUS,
            "occasion": "weekend getaway"
        }
        
        trip_response = TripDataResponse(**data)
        
        assert trip_response.location == "Prague"
        assert trip_response.days == 2
        assert trip_response.transport == TransportType.BUS
        assert trip_response.occasion == "weekend getaway"
        assert trip_response.notes is None
        assert trip_response.preferences is None


class TestTransportType:
    """Test cases for TransportType enum."""
    
    def test_transport_type_values(self):
        """Test that all transport types have correct values."""
        assert TransportType.CAR.value == "car"
        assert TransportType.TRAIN.value == "train"
        assert TransportType.PLANE.value == "plane"
        assert TransportType.BUS.value == "bus"
        assert TransportType.OTHER.value == "other"
    
    def test_transport_type_from_string(self):
        """Test creating transport types from strings."""
        assert TransportType("car") == TransportType.CAR
        assert TransportType("train") == TransportType.TRAIN
        assert TransportType("plane") == TransportType.PLANE
        assert TransportType("bus") == TransportType.BUS
        assert TransportType("other") == TransportType.OTHER
    
    def test_invalid_transport_type(self):
        """Test that invalid transport types raise ValueError."""
        with pytest.raises(ValueError):
            TransportType("spaceship")