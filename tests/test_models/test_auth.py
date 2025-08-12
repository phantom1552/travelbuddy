"""
Tests for authentication-related Pydantic models.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models.auth import (
    UserCredentials,
    UserRegistration,
    UserResponse,
    TokenResponse,
    TokenData
)


class TestUserCredentials:
    """Test cases for UserCredentials model."""
    
    def test_valid_user_credentials(self):
        """Test creating valid user credentials."""
        data = {
            "username": "testuser",
            "password": "securepassword123"
        }
        
        credentials = UserCredentials(**data)
        
        assert credentials.username == "testuser"
        assert credentials.password == "securepassword123"
    
    def test_string_trimming(self):
        """Test that string fields are properly trimmed."""
        data = {
            "username": "  testuser  ",
            "password": "  securepassword123  "
        }
        
        credentials = UserCredentials(**data)
        
        assert credentials.username == "testuser"
        assert credentials.password == "securepassword123"
    
    def test_username_validation(self):
        """Test username field validation."""
        base_data = {"password": "validpassword123"}
        
        # Test missing username
        with pytest.raises(ValidationError) as exc_info:
            UserCredentials(**base_data)
        assert "username" in str(exc_info.value)
        
        # Test username too short
        with pytest.raises(ValidationError) as exc_info:
            UserCredentials(username="ab", **base_data)
        assert "at least 3 characters" in str(exc_info.value)
        
        # Test username too long
        with pytest.raises(ValidationError) as exc_info:
            UserCredentials(username="a" * 51, **base_data)
        assert "at most 50 characters" in str(exc_info.value)
        
        # Test valid boundary values
        credentials_min = UserCredentials(username="abc", **base_data)
        assert credentials_min.username == "abc"
        
        credentials_max = UserCredentials(username="a" * 50, **base_data)
        assert len(credentials_max.username) == 50
    
    def test_password_validation(self):
        """Test password field validation."""
        base_data = {"username": "testuser"}
        
        # Test missing password
        with pytest.raises(ValidationError) as exc_info:
            UserCredentials(**base_data)
        assert "password" in str(exc_info.value)
        
        # Test password too short
        with pytest.raises(ValidationError) as exc_info:
            UserCredentials(password="12345", **base_data)
        assert "at least 6 characters" in str(exc_info.value)
        
        # Test password too long
        with pytest.raises(ValidationError) as exc_info:
            UserCredentials(password="a" * 101, **base_data)
        assert "at most 100 characters" in str(exc_info.value)
        
        # Test valid boundary values
        credentials_min = UserCredentials(password="123456", **base_data)
        assert credentials_min.password == "123456"
        
        credentials_max = UserCredentials(password="a" * 100, **base_data)
        assert len(credentials_max.password) == 100


class TestUserRegistration:
    """Test cases for UserRegistration model."""
    
    def test_valid_user_registration(self):
        """Test creating valid user registration."""
        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "strongpassword123"
        }
        
        registration = UserRegistration(**data)
        
        assert registration.username == "newuser"
        assert registration.email == "newuser@example.com"
        assert registration.password == "strongpassword123"
    
    def test_minimal_user_registration(self):
        """Test creating minimal user registration without email."""
        data = {
            "username": "minimaluser",
            "password": "password123"
        }
        
        registration = UserRegistration(**data)
        
        assert registration.username == "minimaluser"
        assert registration.email is None
        assert registration.password == "password123"
    
    def test_string_trimming(self):
        """Test that string fields are properly trimmed."""
        data = {
            "username": "  trimuser  ",
            "email": "  trim@example.com  ",
            "password": "  trimpassword  "
        }
        
        registration = UserRegistration(**data)
        
        assert registration.username == "trimuser"
        assert registration.email == "trim@example.com"
        assert registration.password == "trimpassword"
    
    def test_email_validation(self):
        """Test email field validation."""
        base_data = {
            "username": "emailuser",
            "password": "password123"
        }
        
        # Test valid email
        registration = UserRegistration(email="valid@example.com", **base_data)
        assert registration.email == "valid@example.com"
        
        # Test invalid email format
        with pytest.raises(ValidationError) as exc_info:
            UserRegistration(email="invalid-email", **base_data)
        assert "value is not a valid email address" in str(exc_info.value)
        
        # Test empty email (EmailStr doesn't allow empty strings)
        with pytest.raises(ValidationError) as exc_info:
            UserRegistration(email="", **base_data)
        assert "value is not a valid email address" in str(exc_info.value)


class TestUserResponse:
    """Test cases for UserResponse model."""
    
    def test_valid_user_response(self):
        """Test creating valid user response."""
        now = datetime.utcnow()
        data = {
            "id": "user-123",
            "username": "responseuser",
            "email": "response@example.com",
            "created_at": now,
            "is_active": True
        }
        
        user_response = UserResponse(**data)
        
        assert user_response.id == "user-123"
        assert user_response.username == "responseuser"
        assert user_response.email == "response@example.com"
        assert user_response.created_at == now
        assert user_response.is_active is True
    
    def test_minimal_user_response(self):
        """Test creating minimal user response."""
        now = datetime.utcnow()
        data = {
            "id": "user-456",
            "username": "minimalresponse",
            "created_at": now
        }
        
        user_response = UserResponse(**data)
        
        assert user_response.id == "user-456"
        assert user_response.username == "minimalresponse"
        assert user_response.email is None
        assert user_response.created_at == now
        assert user_response.is_active is True  # default value


class TestTokenResponse:
    """Test cases for TokenResponse model."""
    
    def test_valid_token_response(self):
        """Test creating valid token response."""
        now = datetime.utcnow()
        user_data = UserResponse(
            id="user-789",
            username="tokenuser",
            created_at=now
        )
        
        data = {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "expires_in": 3600,
            "user": user_data
        }
        
        token_response = TokenResponse(**data)
        
        assert token_response.access_token == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        assert token_response.token_type == "bearer"
        assert token_response.expires_in == 3600
        assert token_response.user == user_data
    
    def test_default_token_type(self):
        """Test that token_type defaults to 'bearer'."""
        now = datetime.utcnow()
        user_data = UserResponse(
            id="user-101",
            username="defaultuser",
            created_at=now
        )
        
        data = {
            "access_token": "token123",
            "expires_in": 1800,
            "user": user_data
        }
        
        token_response = TokenResponse(**data)
        
        assert token_response.token_type == "bearer"


class TestTokenData:
    """Test cases for TokenData model."""
    
    def test_valid_token_data(self):
        """Test creating valid token data."""
        expires_at = datetime.utcnow()
        data = {
            "username": "tokenuser",
            "user_id": "user-123",
            "expires_at": expires_at
        }
        
        token_data = TokenData(**data)
        
        assert token_data.username == "tokenuser"
        assert token_data.user_id == "user-123"
        assert token_data.expires_at == expires_at
    
    def test_minimal_token_data(self):
        """Test creating minimal token data."""
        token_data = TokenData()
        
        assert token_data.username is None
        assert token_data.user_id is None
        assert token_data.expires_at is None
    
    def test_partial_token_data(self):
        """Test creating partial token data."""
        data = {"username": "partialuser"}
        
        token_data = TokenData(**data)
        
        assert token_data.username == "partialuser"
        assert token_data.user_id is None
        assert token_data.expires_at is None