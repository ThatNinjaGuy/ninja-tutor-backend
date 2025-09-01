"""
AI-powered features endpoints
"""
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ....models.quiz import QuizGenRequest, Question
from ....models.note import AiInsights
from ....services.ai_service import AIService
from ....services.book_service import BookService

router = APIRouter()


class DefinitionRequest(BaseModel):
    text: str
    context: str


class ExplanationRequest(BaseModel):
    concept: str
    context: str


class ComprehensionRequest(BaseModel):
    book_id: str
    page_number: int
    time_spent: int
    interactions: List[str]


class InsightsRequest(BaseModel):
    note_content: str
    book_context: str


@router.post("/definition")
async def get_definition(request: DefinitionRequest) -> Dict[str, Any]:
    """Get AI-powered definition for selected text"""
    ai_service = AIService()
    result = await ai_service.get_definition(request.text, request.context)
    return result


@router.post("/explanation")
async def get_explanation(request: ExplanationRequest) -> Dict[str, Any]:
    """Get AI explanation for complex concepts"""
    ai_service = AIService()
    result = await ai_service.get_explanation(request.concept, request.context)
    return result


@router.post("/generate-questions")
async def generate_questions(request: QuizGenRequest) -> Dict[str, List[Question]]:
    """Generate practice questions from book content"""
    # Get book content
    book_service = BookService()
    book = await book_service.get_book(request.book_id)
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if not book.content_text:
        raise HTTPException(status_code=400, detail="Book content not available for question generation")
    
    # Extract content for specified page range
    # This is a simplified implementation - in production, you'd want proper page extraction
    content = book.content_text[:2000]  # First 2000 characters as sample
    
    ai_service = AIService()
    questions = await ai_service.generate_questions(
        content=content,
        question_count=request.question_count,
        difficulty=request.difficulty,
        question_types=request.question_types
    )
    
    return {"questions": questions}


@router.post("/comprehension")
async def analyze_comprehension(request: ComprehensionRequest) -> Dict[str, Any]:
    """Analyze reading comprehension based on user behavior"""
    # Get book content for the specific page
    book_service = BookService()
    book = await book_service.get_book(request.book_id)
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Simplified - in production, extract specific page content
    content = book.content_text[:1000] if book.content_text else ""
    
    ai_service = AIService()
    analysis = await ai_service.analyze_comprehension(
        content=content,
        time_spent=request.time_spent,
        interactions=request.interactions
    )
    
    return analysis


@router.post("/insights")
async def get_ai_insights(request: InsightsRequest) -> AiInsights:
    """Get AI insights for student notes"""
    ai_service = AIService()
    insights = await ai_service.generate_ai_insights(
        note_content=request.note_content,
        book_context=request.book_context
    )
    
    return insights
