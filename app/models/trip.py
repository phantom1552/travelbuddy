"""
Trip-related Pydantic models for request/response validation.
"""
from datetime import datetime
from typing import List, Optional
from enum import Enum

from pydantic import BaseModel, Field, field_validator, ConfigDict


class TransportType(str, Enum):
    """Valid transport methods for trips."""
    CAR = "car"
    TRAIN = "train"
    PLANE = "plane"
    BUS = "bus"
    OTHER = "other"


class TripDataRequest(BaseModel):
    """Request model for trip data input."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    location: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Trip destination location"
    )
    days: int = Field(
        ...,
        ge=1,
        le=365,
        description="Number of days for the trip"
    )
    transport: TransportType = Field(
        ...,
        description="Primary mode of transportation"
    )
    occasion: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Purpose or occasion for the trip"
    )
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Additional notes or special requirements"
    )
    preferences: Optional[List[str]] = Field(
        None,
        max_length=10,
        description="User preferences for packing"
    )

    @field_validator('preferences')
    @classmethod
    def validate_preferences(cls, v):
        """Validate preferences list."""
        if v is None:
            return v
        
        # Filter out empty strings and validate length
        filtered_prefs = []
        for pref in v:
            if not isinstance(pref, str):
                raise ValueError("Each preference must be a string")
            
            stripped_pref = pref.strip()
            if stripped_pref:
                if len(stripped_pref) > 50:
                    raise ValueError("Each preference must be less than 50 characters")
                filtered_prefs.append(stripped_pref)
        
        return filtered_prefs if filtered_prefs else None


class TripDataResponse(BaseModel):
    """Response model for trip data."""
    location: str
    days: int
    transport: TransportType
    occasion: str
    notes: Optional[str] = None
    preferences: Optional[List[str]] = None