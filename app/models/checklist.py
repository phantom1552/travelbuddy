"""
Checklist-related Pydantic models for request/response validation.
"""
from datetime import datetime
from typing import List, Optional
from enum import Enum

from pydantic import BaseModel, Field, validator, ConfigDict

from .trip import TripDataResponse


class PriorityLevel(str, Enum):
    """Valid priority levels for checklist items."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ChecklistItemRequest(BaseModel):
    """Request model for creating/updating checklist items."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    text: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Text content of the checklist item"
    )
    category: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Category for organizing the item"
    )
    checked: bool = Field(
        default=False,
        description="Whether the item is checked/completed"
    )
    priority: PriorityLevel = Field(
        default=PriorityLevel.MEDIUM,
        description="Priority level of the item"
    )
    user_added: bool = Field(
        default=True,
        description="Whether this item was added by the user"
    )


class ChecklistItemResponse(BaseModel):
    """Response model for checklist items."""
    id: str = Field(..., description="Unique identifier for the item")
    text: str
    category: str
    checked: bool
    priority: PriorityLevel
    user_added: bool
    created_at: datetime
    updated_at: datetime


class ChecklistItemUpdate(BaseModel):
    """Model for updating existing checklist items."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    text: Optional[str] = Field(
        None,
        min_length=2,
        max_length=200,
        description="Updated text content"
    )
    category: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="Updated category"
    )
    checked: Optional[bool] = Field(
        None,
        description="Updated checked status"
    )
    priority: Optional[PriorityLevel] = Field(
        None,
        description="Updated priority level"
    )


class ChecklistRequest(BaseModel):
    """Request model for creating a new checklist."""
    trip_data: TripDataResponse = Field(
        ...,
        description="Trip data associated with this checklist"
    )
    items: List[ChecklistItemRequest] = Field(
        default_factory=list,
        max_length=100,
        description="Initial checklist items"
    )


class ChecklistResponse(BaseModel):
    """Response model for complete checklist."""
    id: str = Field(..., description="Unique identifier for the checklist")
    trip_data: TripDataResponse
    items: List[ChecklistItemResponse]
    created_at: datetime
    updated_at: datetime
    synced: bool = Field(
        default=False,
        description="Whether the checklist is synced with external storage"
    )


class ChecklistGenerationRequest(BaseModel):
    """Request model for AI checklist generation."""
    trip_data: TripDataResponse = Field(
        ...,
        description="Trip data to generate checklist for"
    )


class ChecklistGenerationResponse(BaseModel):
    """Response model for AI-generated checklist."""
    id: str = Field(..., description="Generated checklist ID")
    items: List[ChecklistItemResponse] = Field(
        ...,
        description="AI-generated checklist items"
    )
    generated_at: datetime = Field(
        ...,
        description="Timestamp when the checklist was generated"
    )
    trip_data: TripDataResponse = Field(
        ...,
        description="Trip data used for generation"
    )