"""
Groq API client service for AI checklist generation.

This module provides a secure interface to the Groq API for generating
personalized trip checklists using AI models.
"""

import logging
from typing import Optional, Dict, Any, List
from groq import Groq
from groq.types.chat import ChatCompletion
from app.core.config import settings

logger = logging.getLogger(__name__)


class GroqAPIError(Exception):
    """Custom exception for Groq API related errors."""
    pass


class GroqRateLimitError(GroqAPIError):
    """Exception raised when Groq API rate limit is exceeded."""
    pass


class GroqClient:
    """
    Client for interacting with Groq API to generate AI-powered checklists.
    
    This class handles secure API communication, error handling, and response
    parsing for the Groq Llama model integration.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the Groq client.
        
        Args:
            api_key: Groq API key. If None, uses settings.GROQ_API_KEY
            model: Model name to use. If None, uses settings.GROQ_MODEL
        """
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        
        if not self.api_key:
            raise GroqAPIError("Groq API key is required but not provided")
        
        self.client = Groq(api_key=self.api_key)
        logger.info(f"Groq client initialized with model: {self.model}")
    
    async def generate_completion(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """
        Generate a completion using the Groq API.
        
        Args:
            prompt: The input prompt for the AI model
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature (0.0 to 1.0)
            **kwargs: Additional parameters for the API call
            
        Returns:
            The generated text response
            
        Raises:
            GroqAPIError: For general API errors
            GroqRateLimitError: When rate limit is exceeded
        """
        try:
            logger.debug(f"Generating completion with prompt length: {len(prompt)}")
            
            response: ChatCompletion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            
            if not response.choices:
                raise GroqAPIError("No response choices returned from Groq API")
            
            content = response.choices[0].message.content
            if not content:
                raise GroqAPIError("Empty content returned from Groq API")
            
            logger.info("Successfully generated completion from Groq API")
            return content.strip()
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Handle rate limiting
            if "rate limit" in error_msg or "429" in error_msg:
                logger.warning("Groq API rate limit exceeded")
                raise GroqRateLimitError("Rate limit exceeded. Please try again later.")
            
            # Handle authentication errors
            if "unauthorized" in error_msg or "401" in error_msg:
                logger.error("Groq API authentication failed")
                raise GroqAPIError("Invalid API key or authentication failed")
            
            # Handle other API errors
            logger.error(f"Groq API error: {str(e)}")
            raise GroqAPIError(f"Failed to generate completion: {str(e)}")
    
    def validate_api_key(self) -> bool:
        """
        Validate that the API key is properly configured and working.
        
        Returns:
            True if API key is valid, False otherwise
        """
        try:
            # Make a simple test request to validate the API key
            test_response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            return bool(test_response.choices)
        except Exception as e:
            logger.error(f"API key validation failed: {str(e)}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model configuration.
        
        Returns:
            Dictionary containing model information
        """
        return {
            "model": self.model,
            "api_key_configured": bool(self.api_key),
            "api_key_valid": self.validate_api_key() if self.api_key else False
        }


# Global instance for dependency injection
groq_client = GroqClient()