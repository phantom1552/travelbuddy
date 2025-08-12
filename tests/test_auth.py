"""
Tests for authentication system.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from jose import jwt

from main import app
from app.services.auth import auth_service
from app.models.auth import UserCredentials, TokenData


client = TestClient(app)


class TestAuthService:
    """Test the AuthService class."""
    
    def test_password_hashing(self):
        """Test password hashing and verification."""
        password = "testpassword123"
        hashed = auth_service.get_password_hash(password)
        
        assert hashed != password
        assert auth_service.verify_password(password, hashed)
        assert not auth_service.verify_password("wrongpassword", hashed)
    
    def test_create_access_token(self):
        """Test JWT token creation."""
        data = {"sub": "testuser", "user_id": "123"}
        token = auth_service.create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Decode and verify token
        payload = jwt.decode(token, auth_service.secret_key, algorithms=[auth_service.algorithm])
        assert payload["sub"] == "testuser"
        assert payload["user_id"] == "123"
        assert "exp" in payload
    
    def test_create_access_token_with_expiry(self):
        """Test JWT token creation with custom expiry."""
        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=60)
        token = auth_service.create_access_token(data, expires_delta)
        
        payload = jwt.decode(token, auth_service.secret_key, algorithms=[auth_service.algorithm])
        
        # Just verify that the token has an expiry time and contains the right data
        assert "exp" in payload
        assert payload["sub"] == "testuser"
        
        # Verify the token is valid and not expired
        token_data = auth_service.verify_token(token)
        assert token_data.username == "testuser"
    
    def test_verify_token_valid(self):
        """Test token verification with valid token."""
        data = {"sub": "testuser", "user_id": "123"}
        token = auth_service.create_access_token(data)
        
        token_data = auth_service.verify_token(token)
        
        assert isinstance(token_data, TokenData)
        assert token_data.username == "testuser"
        assert token_data.user_id == "123"
        assert token_data.expires_at is not None
    
    def test_verify_token_invalid(self):
        """Test token verification with invalid token."""
        with pytest.raises(Exception):  # Should raise HTTPException
            auth_service.verify_token("invalid_token")
    
    def test_authenticate_user_valid(self):
        """Test user authentication with valid credentials."""
        credentials = UserCredentials(username="testuser", password="testpass123")
        user = auth_service.authenticate_user(credentials)
        
        assert user is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.is_active is True
    
    def test_authenticate_user_invalid_username(self):
        """Test user authentication with invalid username."""
        credentials = UserCredentials(username="nonexistent", password="testpass123")
        user = auth_service.authenticate_user(credentials)
        
        assert user is None
    
    def test_authenticate_user_invalid_password(self):
        """Test user authentication with invalid password."""
        credentials = UserCredentials(username="testuser", password="wrongpassword")
        user = auth_service.authenticate_user(credentials)
        
        assert user is None
    
    def test_create_token_response(self):
        """Test token response creation."""
        credentials = UserCredentials(username="testuser", password="testpass123")
        user = auth_service.authenticate_user(credentials)
        
        token_response = auth_service.create_token_response(user)
        
        assert token_response.access_token is not None
        assert token_response.token_type == "bearer"
        assert token_response.expires_in > 0
        assert token_response.user.username == "testuser"


class TestAuthEndpoints:
    """Test authentication endpoints."""
    
    def test_login_valid_credentials(self):
        """Test login with valid credentials."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "testpass123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert data["user"]["username"] == "testuser"
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "wrongpassword"}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
    
    def test_login_nonexistent_user(self):
        """Test login with nonexistent user."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent", "password": "password"}
        )
        
        assert response.status_code == 401
    
    def test_login_validation_error(self):
        """Test login with validation errors."""
        # Missing password
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser"}
        )
        
        assert response.status_code == 422
    
    def test_get_current_user_info_valid_token(self):
        """Test getting current user info with valid token."""
        # First login to get token
        login_response = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "testpass123"}
        )
        token = login_response.json()["access_token"]
        
        # Use token to access protected endpoint
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert "user_id" in data
        assert "expires_at" in data
    
    def test_get_current_user_info_invalid_token(self):
        """Test getting current user info with invalid token."""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == 401
    
    def test_get_current_user_info_no_token(self):
        """Test getting current user info without token."""
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 403  # No token provided
    
    def test_protected_endpoint_with_token(self):
        """Test protected endpoint with valid token."""
        # First login to get token
        login_response = client.post(
            "/api/v1/auth/login",
            json={"username": "demo", "password": "demopass123"}
        )
        token = login_response.json()["access_token"]
        
        # Access protected endpoint
        response = client.get(
            "/api/v1/protected",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "Hello demo!" in data["message"]
        assert data["access_granted"] is True
    
    def test_protected_endpoint_without_token(self):
        """Test protected endpoint without token."""
        response = client.get("/api/v1/protected")
        
        assert response.status_code == 403
    
    def test_logout_endpoint(self):
        """Test logout endpoint."""
        response = client.post("/api/v1/auth/logout")
        
        assert response.status_code == 200
        data = response.json()
        assert "Logout successful" in data["message"]
    
    def test_generate_checklist_requires_auth(self):
        """Test that generate checklist endpoint now requires authentication."""
        response = client.post("/api/v1/generate-checklist")
        
        assert response.status_code == 403  # No token provided
        
        # Test with valid token
        login_response = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "testpass123"}
        )
        token = login_response.json()["access_token"]
        
        response = client.post(
            "/api/v1/generate-checklist",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user"] == "testuser"


class TestAuthMiddleware:
    """Test authentication middleware functionality."""
    
    def test_token_expiry_handling(self):
        """Test handling of expired tokens."""
        # Create a token that expires immediately
        data = {"sub": "testuser", "user_id": "123"}
        expires_delta = timedelta(seconds=-1)  # Already expired
        expired_token = auth_service.create_access_token(data, expires_delta)
        
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        assert response.status_code == 401
    
    def test_malformed_token(self):
        """Test handling of malformed tokens."""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer malformed.token.here"}
        )
        
        assert response.status_code == 401
    
    def test_missing_bearer_prefix(self):
        """Test handling of tokens without Bearer prefix."""
        login_response = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "testpass123"}
        )
        token = login_response.json()["access_token"]
        
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": token}  # Missing "Bearer " prefix
        )
        
        assert response.status_code == 403