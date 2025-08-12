import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.models.auth import UserCredentials, TokenResponse, TokenData
from app.models.common import ErrorResponse
from app.models.checklist import ChecklistGenerationRequest, ChecklistGenerationResponse
from app.services.auth import auth_service
from app.services import groq_client, create_checklist_generator
from app.services.checklist_generator import ChecklistGenerationError
from app.services.groq_client import GroqAPIError, GroqRateLimitError
from app.core.auth import get_current_active_user, security

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def api_health():
    return {"status": "API is healthy", "version": "1.0.0"}


# Authentication endpoints
@router.post(
    "/auth/login",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        422: {"model": ErrorResponse, "description": "Validation error"}
    }
)
async def login(credentials: UserCredentials):
    """
    Authenticate user and return JWT token.
    
    Demo credentials:
    - Username: testuser, Password: testpass123
    - Username: demo, Password: demopass123
    """
    user = auth_service.authenticate_user(credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_response = auth_service.create_token_response(user)
    return token_response


@router.get(
    "/auth/me",
    response_model=dict,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or missing token"}
    }
)
async def get_current_user_info(
    current_user: TokenData = Depends(get_current_active_user)
):
    """
    Get current authenticated user information.
    Requires valid JWT token in Authorization header.
    """
    return {
        "username": current_user.username,
        "user_id": current_user.user_id,
        "expires_at": current_user.expires_at,
        "message": "Authentication successful"
    }


@router.post("/auth/logout")
async def logout():
    """
    Logout endpoint. 
    Note: JWT tokens are stateless, so logout is handled client-side by discarding the token.
    """
    return {"message": "Logout successful. Please discard your token on the client side."}


# Protected endpoint example
@router.get(
    "/protected",
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"}
    }
)
async def protected_endpoint(
    current_user: TokenData = Depends(get_current_active_user)
):
    """
    Example protected endpoint that requires authentication.
    """
    return {
        "message": f"Hello {current_user.username}! This is a protected endpoint.",
        "user_id": current_user.user_id,
        "access_granted": True
    }


# Checklist generation endpoints
@router.post(
    "/generate-checklist",
    response_model=ChecklistGenerationResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request data"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "Service temporarily unavailable"}
    }
)
async def generate_checklist(
    request: ChecklistGenerationRequest,
    current_user: TokenData = Depends(get_current_active_user)
):
    """
    Generate a personalized trip checklist using AI.
    
    This endpoint takes trip details and generates a customized packing checklist
    using the Groq Llama AI model. The checklist includes items categorized by
    type (clothing, documents, electronics, etc.) with priority levels.
    
    **Authentication Required**: This endpoint requires a valid JWT token.
    
    **Request Body**:
    - trip_data: Trip information including location, duration, transport, and occasion
    
    **Response**:
    - Generated checklist with items, metadata, and trip information
    
    **Error Handling**:
    - Returns fallback items if AI generation fails
    - Handles rate limiting gracefully
    - Provides detailed error messages for debugging
    """
    try:
        logger.info(f"Generating checklist for user {current_user.username}")
        logger.debug(f"Trip data: {request.trip_data.location}, {request.trip_data.days} days")
        
        # Create checklist generator service
        generator = create_checklist_generator(groq_client)
        
        # Generate the checklist
        checklist_response = await generator.generate_checklist(request.trip_data)
        
        logger.info(f"Successfully generated checklist with {len(checklist_response.items)} items")
        return checklist_response
        
    except ChecklistGenerationError as e:
        logger.error(f"Checklist generation error for user {current_user.username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate checklist: {str(e)}"
        )
    
    except GroqRateLimitError:
        logger.warning(f"Rate limit exceeded for user {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable due to rate limiting. Please try again later."
        )
    
    except GroqAPIError as e:
        logger.error(f"Groq API error for user {current_user.username}: {str(e)}")
        # Don't expose internal API errors to the client
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service temporarily unavailable. Please try again later."
        )
    
    except Exception as e:
        logger.error(f"Unexpected error during checklist generation for user {current_user.username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later."
        )