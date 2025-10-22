"""
AI service for definitions and explanations
"""
import logging
from typing import Dict, Any

from .base_ai_service import BaseAIService
from ...core.exceptions import AIServiceException

logger = logging.getLogger(__name__)


class DefinitionService(BaseAIService):
    """Service for AI-powered definitions and explanations"""
    
    async def get_definition(self, text: str, context: str) -> Dict[str, Any]:
        """
        Get AI-powered definition for selected text
        
        Args:
            text: Text to define
            context: Context around the text
            
        Returns:
            Definition with metadata
            
        Raises:
            AIServiceException: If definition generation fails
        """
        try:
            prompt = f"""
            Provide a clear, educational definition for the term or phrase: "{text}"
            
            Context: {context[:500]}...
            
            Please provide:
            1. A simple definition suitable for students
            2. An example of usage
            3. Any relevant synonyms or related terms
            """
            
            content = await self._generate_content(
                prompt,
                max_tokens=300,
                temperature=0.3
            )
            
            return {
                "definition": content,
                "source": "Gemini AI",
                "confidence": 0.85
            }
            
        except Exception as e:
            logger.error(f"Error getting definition: {str(e)}")
            raise AIServiceException(
                f"Failed to get definition for '{text}'",
                details={"error": str(e)}
            )
    
    async def get_explanation(self, concept: str, context: str) -> Dict[str, Any]:
        """
        Get AI explanation for complex concepts
        
        Args:
            concept: Concept to explain
            context: Context around the concept
            
        Returns:
            Explanation with metadata
            
        Raises:
            AIServiceException: If explanation generation fails
        """
        try:
            prompt = f"""
            Explain the concept: "{concept}" in simple, educational terms.
            
            Context: {context[:500]}...
            
            Please provide:
            1. A clear explanation suitable for students
            2. Why this concept is important
            3. How it relates to the broader topic
            4. A simple analogy if applicable
            
            Keep the explanation concise but comprehensive.
            """
            
            content = await self._generate_content(
                prompt,
                max_tokens=500,
                temperature=0.4
            )
            
            # Calculate approximate reading time
            word_count = len(content.split())
            estimated_read_time = max(1, word_count // 100)  # Assume 100 words per minute
            
            return {
                "explanation": content,
                "complexity_level": "intermediate",
                "estimated_read_time": estimated_read_time
            }
            
        except Exception as e:
            logger.error(f"Error getting explanation: {str(e)}")
            raise AIServiceException(
                f"Failed to get explanation for '{concept}'",
                details={"error": str(e)}
            )

