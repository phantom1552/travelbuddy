"""
Authentication middleware and dependencies for FastAPI.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from app.services.auth import auth_service
from app.models.auth import TokenData, UserResponse


# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenData:
    """
    Dependency to get the current authenticated user from JWT token.
    """
    token = credentials.credentials
    token_data = auth_service.verify_token(token)
    return token_data


async def get_current_active_user(
    current_user: TokenData = Depends(get_current_user)
) -> TokenData:
    """
    Dependency to get the current active user.
    In a real application, you would check if the user is active in the database.
    """
    # For demo purposes, we assume all users are active
    # In production, you would query the database to check user status
    return current_user


# Optional authentication dependency
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[TokenData]:
    """
    Optional authentication dependency that doesn't raise an error if no token is provided.
    """
    if credentials is None:
        return None
    
    try:
        token = credentials.credentials
        token_data = auth_service.verify_token(token)
        return token_data
    except HTTPException:
        return None