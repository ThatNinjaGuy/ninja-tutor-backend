"""
Base AI service with common Google Gemini configuration
"""
import logging
import google.generativeai as genai
from typing import Dict, Any

from ...core.config import settings
from ...core.exceptions import AIServiceException

logger = logging.getLogger(__name__)


class BaseAIService:
    """Base service for AI operations using Google Gemini"""
    
    def __init__(self):
        """Initialize Google Gemini model"""
        # Get API key
        google_api_key = getattr(settings, 'GOOGLE_API_KEY', None) or settings.OPENAI_API_KEY
        
        if not google_api_key:
            logger.error("No API key found. Please set GOOGLE_API_KEY in .env")
            raise AIServiceException("GOOGLE_API_KEY not configured")
        
        genai.configure(api_key=google_api_key)
        
        # Initialize Gemini model
        self.model = genai.GenerativeModel('models/gemini-2.5-flash')
        logger.info("✅ Google Gemini initialized")
        logger.info("   Model: gemini-2.5-flash")
    
    async def _generate_content(
        self,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.4
    ) -> str:
        """
        Generate content using Gemini
        
        Args:
            prompt: The prompt to generate from
            max_tokens: Maximum output tokens
            temperature: Temperature for generation
            
        Returns:
            Generated content
            
        Raises:
            AIServiceException: If generation fails
        """
        try:
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            raise AIServiceException(
                "Failed to generate content",
                details={"error": str(e)}
            )

