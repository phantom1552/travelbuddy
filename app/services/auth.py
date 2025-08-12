"""
Authentication service for JWT token management and user authentication.
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.auth import TokenData, UserCredentials, UserResponse, TokenResponse


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Service class for authentication operations."""
    
    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = "HS256"
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Generate password hash."""
        return pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> TokenData:
        """Verify and decode a JWT token."""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            username: str = payload.get("sub")
            user_id: str = payload.get("user_id")
            expires_at: datetime = datetime.fromtimestamp(payload.get("exp", 0))
            
            if username is None:
                raise credentials_exception
                
            token_data = TokenData(
                username=username,
                user_id=user_id,
                expires_at=expires_at
            )
            return token_data
            
        except JWTError:
            raise credentials_exception
    
    def authenticate_user(self, credentials: UserCredentials) -> Optional[UserResponse]:
        """
        Authenticate a user with credentials.
        
        Note: This is a simplified implementation for demo purposes.
        In a real application, you would validate against a database.
        """
        # Demo user for testing - in production, this would query a database
        demo_users = {
            "testuser": {
                "id": "user_123",
                "username": "testuser",
                "email": "test@example.com",
                "hashed_password": self.get_password_hash("testpass123"),
                "created_at": datetime.utcnow(),
                "is_active": True
            },
            "demo": {
                "id": "user_456", 
                "username": "demo",
                "email": "demo@example.com",
                "hashed_password": self.get_password_hash("demopass123"),
                "created_at": datetime.utcnow(),
                "is_active": True
            }
        }
        
        user_data = demo_users.get(credentials.username)
        if not user_data:
            return None
            
        if not self.verify_password(credentials.password, user_data["hashed_password"]):
            return None
            
        return UserResponse(
            id=user_data["id"],
            username=user_data["username"],
            email=user_data["email"],
            created_at=user_data["created_at"],
            is_active=user_data["is_active"]
        )
    
    def create_token_response(self, user: UserResponse) -> TokenResponse:
        """Create a complete token response for a user."""
        access_token_expires = timedelta(minutes=self.access_token_expire_minutes)
        access_token = self.create_access_token(
            data={"sub": user.username, "user_id": user.id},
            expires_delta=access_token_expires
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=self.access_token_expire_minutes * 60,  # Convert to seconds
            user=user
        )


# Global auth service instance
auth_service = AuthService()