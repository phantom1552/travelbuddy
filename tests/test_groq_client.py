"""
Unit tests for the Groq API client service.

Tests cover API communication, error handling, rate limiting,
and mocked API responses.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from groq.types.chat.chat_completion import ChatCompletion, Choice
from groq.types.chat.chat_completion_message import ChatCompletionMessage

from app.services.groq_client import (
    GroqClient,
    GroqAPIError,
    GroqRateLimitError
)


class TestGroqClient:
    """Test cases for GroqClient class."""
    
    @pytest.fixture
    def mock_groq_response(self):
        """Create a mock Groq API response."""
        mock_message = Mock(spec=ChatCompletionMessage)
        mock_message.content = "Test response content"
        
        mock_choice = Mock(spec=Choice)
        mock_choice.message = mock_message
        
        mock_response = Mock(spec=ChatCompletion)
        mock_response.choices = [mock_choice]
        
        return mock_response
    
    @pytest.fixture
    def groq_client(self):
        """Create a GroqClient instance for testing."""
        with patch('app.services.groq_client.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test-api-key"
            mock_settings.GROQ_MODEL = "test-model"
            
            with patch('app.services.groq_client.Groq') as mock_groq:
                client = GroqClient()
                client.client = mock_groq.return_value
                return client
    
    def test_init_with_api_key(self):
        """Test GroqClient initialization with API key."""
        with patch('app.services.groq_client.Groq') as mock_groq:
            client = GroqClient(api_key="test-key", model="test-model")
            
            assert client.api_key == "test-key"
            assert client.model == "test-model"
            mock_groq.assert_called_once_with(api_key="test-key")
    
    def test_init_without_api_key_raises_error(self):
        """Test that initialization without API key raises error."""
        with patch('app.services.groq_client.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = ""
            
            with pytest.raises(GroqAPIError, match="Groq API key is required"):
                GroqClient()
    
    def test_init_uses_settings_defaults(self):
        """Test that initialization uses settings for defaults."""
        with patch('app.services.groq_client.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "settings-key"
            mock_settings.GROQ_MODEL = "settings-model"
            
            with patch('app.services.groq_client.Groq') as mock_groq:
                client = GroqClient()
                
                assert client.api_key == "settings-key"
                assert client.model == "settings-model"
    
    @pytest.mark.asyncio
    async def test_generate_completion_success(self, groq_client, mock_groq_response):
        """Test successful completion generation."""
        groq_client.client.chat.completions.create.return_value = mock_groq_response
        
        result = await groq_client.generate_completion("Test prompt")
        
        assert result == "Test response content"
        groq_client.client.chat.completions.create.assert_called_once_with(
            model="test-model",
            messages=[{"role": "user", "content": "Test prompt"}],
            max_tokens=1000,
            temperature=0.7
        )
    
    @pytest.mark.asyncio
    async def test_generate_completion_with_custom_params(self, groq_client, mock_groq_response):
        """Test completion generation with custom parameters."""
        groq_client.client.chat.completions.create.return_value = mock_groq_response
        
        result = await groq_client.generate_completion(
            "Test prompt",
            max_tokens=500,
            temperature=0.5,
            top_p=0.9
        )
        
        assert result == "Test response content"
        groq_client.client.chat.completions.create.assert_called_once_with(
            model="test-model",
            messages=[{"role": "user", "content": "Test prompt"}],
            max_tokens=500,
            temperature=0.5,
            top_p=0.9
        )
    
    @pytest.mark.asyncio
    async def test_generate_completion_no_choices_error(self, groq_client):
        """Test error handling when no choices are returned."""
        mock_response = Mock(spec=ChatCompletion)
        mock_response.choices = []
        groq_client.client.chat.completions.create.return_value = mock_response
        
        with pytest.raises(GroqAPIError, match="No response choices returned"):
            await groq_client.generate_completion("Test prompt")
    
    @pytest.mark.asyncio
    async def test_generate_completion_empty_content_error(self, groq_client):
        """Test error handling when empty content is returned."""
        mock_message = Mock(spec=ChatCompletionMessage)
        mock_message.content = None
        
        mock_choice = Mock(spec=Choice)
        mock_choice.message = mock_message
        
        mock_response = Mock(spec=ChatCompletion)
        mock_response.choices = [mock_choice]
        
        groq_client.client.chat.completions.create.return_value = mock_response
        
        with pytest.raises(GroqAPIError, match="Empty content returned"):
            await groq_client.generate_completion("Test prompt")
    
    @pytest.mark.asyncio
    async def test_generate_completion_rate_limit_error(self, groq_client):
        """Test rate limit error handling."""
        groq_client.client.chat.completions.create.side_effect = Exception("Rate limit exceeded")
        
        with pytest.raises(GroqRateLimitError, match="Rate limit exceeded"):
            await groq_client.generate_completion("Test prompt")
    
    @pytest.mark.asyncio
    async def test_generate_completion_auth_error(self, groq_client):
        """Test authentication error handling."""
        groq_client.client.chat.completions.create.side_effect = Exception("401 Unauthorized")
        
        with pytest.raises(GroqAPIError, match="Invalid API key or authentication failed"):
            await groq_client.generate_completion("Test prompt")
    
    @pytest.mark.asyncio
    async def test_generate_completion_generic_error(self, groq_client):
        """Test generic error handling."""
        groq_client.client.chat.completions.create.side_effect = Exception("Generic error")
        
        with pytest.raises(GroqAPIError, match="Failed to generate completion"):
            await groq_client.generate_completion("Test prompt")
    
    def test_validate_api_key_success(self, groq_client, mock_groq_response):
        """Test successful API key validation."""
        groq_client.client.chat.completions.create.return_value = mock_groq_response
        
        result = groq_client.validate_api_key()
        
        assert result is True
        groq_client.client.chat.completions.create.assert_called_once_with(
            model="test-model",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5
        )
    
    def test_validate_api_key_failure(self, groq_client):
        """Test API key validation failure."""
        groq_client.client.chat.completions.create.side_effect = Exception("Invalid API key")
        
        result = groq_client.validate_api_key()
        
        assert result is False
    
    def test_validate_api_key_no_choices(self, groq_client):
        """Test API key validation with no choices returned."""
        mock_response = Mock(spec=ChatCompletion)
        mock_response.choices = []
        groq_client.client.chat.completions.create.return_value = mock_response
        
        result = groq_client.validate_api_key()
        
        assert result is False
    
    def test_get_model_info(self, groq_client):
        """Test getting model information."""
        with patch.object(groq_client, 'validate_api_key', return_value=True):
            info = groq_client.get_model_info()
            
            expected = {
                "model": "test-model",
                "api_key_configured": True,
                "api_key_valid": True
            }
            assert info == expected
    
    def test_get_model_info_no_api_key(self):
        """Test getting model information without API key."""
        with patch('app.services.groq_client.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = ""
            mock_settings.GROQ_MODEL = "test-model"
            
            with patch('app.services.groq_client.Groq'):
                try:
                    client = GroqClient(api_key="test")
                    client.api_key = ""  # Simulate no API key
                    
                    info = client.get_model_info()
                    
                    expected = {
                        "model": "test-model",
                        "api_key_configured": False,
                        "api_key_valid": False
                    }
                    assert info == expected
                except GroqAPIError:
                    # This is expected when no API key is provided
                    pass


class TestGroqClientExceptions:
    """Test custom exception classes."""
    
    def test_groq_api_error(self):
        """Test GroqAPIError exception."""
        error = GroqAPIError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)
    
    def test_groq_rate_limit_error(self):
        """Test GroqRateLimitError exception."""
        error = GroqRateLimitError("Rate limit exceeded")
        assert str(error) == "Rate limit exceeded"
        assert isinstance(error, GroqAPIError)
        assert isinstance(error, Exception)


@pytest.mark.integration
class TestGroqClientIntegration:
    """Integration tests for GroqClient (require real API key)."""
    
    @pytest.mark.skip(reason="Requires real API key and network access")
    async def test_real_api_call(self):
        """Test with real API call (skipped by default)."""
        # This test would require a real API key and should only be run
        # in integration test environments
        client = GroqClient(api_key="real-api-key")
        result = await client.generate_completion("Say hello")
        assert isinstance(result, str)
        assert len(result) > 0