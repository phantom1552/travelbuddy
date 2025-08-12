"""
Authentication-related Pydantic models.
"""
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, EmailStr, ConfigDict


class UserCredentials(BaseModel):
    """Model for user login credentials."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Username for authentication"
    )
    password: str = Field(
        ...,
        min_length=6,
        max_length=100,
        description="User password"
    )


class UserRegistration(BaseModel):
    """Model for user registration."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Desired username"
    )
    email: Optional[EmailStr] = Field(
        None,
        description="User email address"
    )
    password: str = Field(
        ...,
        min_length=6,
        max_length=100,
        description="User password"
    )


class UserResponse(BaseModel):
    """Response model for user information."""
    id: str = Field(..., description="Unique user identifier")
    username: str
    email: Optional[str] = None
    created_at: datetime
    is_active: bool = Field(default=True)


class TokenResponse(BaseModel):
    """Response model for authentication tokens."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: UserResponse = Field(..., description="Authenticated user information")


class TokenData(BaseModel):
    """Model for token payload data."""
    username: Optional[str] = None
    user_id: Optional[str] = None
    expires_at: Optional[datetime] = None