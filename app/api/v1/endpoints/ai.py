"""
AI-powered features endpoints
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ....models.quiz import QuizGenRequest, Question, DifficultyLevel
from ....models.note import AiInsights
from ....services.ai_service import AIService
from ....services.book_service import BookService
from .auth import get_current_user

router = APIRouter()


class DefinitionRequest(BaseModel):
    text: str
    context: str
    book_id: Optional[str] = None
    page_number: Optional[int] = None


class ExplanationRequest(BaseModel):
    concept: str
    context: str
    book_id: Optional[str] = None


class ComprehensionRequest(BaseModel):
    book_id: str
    page_number: int
    time_spent: int
    interactions: List[str]


class InsightsRequest(BaseModel):
    note_content: str
    book_context: str
    book_id: Optional[str] = None


class RecommendationRequest(BaseModel):
    """Request for personalized AI recommendations"""
    user_reading_history: List[str] = []  # List of book_ids
    recent_subjects: List[str] = []
    quiz_performance: Dict[str, float] = {}  # subject -> avg score


@router.post("/definition")
async def get_definition(
    request: DefinitionRequest,
    current_user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get AI-powered definition for selected text in reading interface"""
    ai_service = AIService()
    result = await ai_service.get_definition(request.text, request.context)
    
    # Add metadata for tracking
    result['user_id'] = current_user_id
    if request.book_id:
        result['book_id'] = request.book_id
    if request.page_number:
        result['page_number'] = request.page_number
    
    return result


@router.post("/explanation")
async def get_explanation(
    request: ExplanationRequest,
    current_user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get AI explanation for complex concepts"""
    ai_service = AIService()
    result = await ai_service.get_explanation(request.concept, request.context)
    
    # Add metadata
    result['user_id'] = current_user_id
    if request.book_id:
        result['book_id'] = request.book_id
    
    return result


@router.post("/generate-questions")
async def generate_questions(
    request: QuizGenRequest,
    current_user_id: str = Depends(get_current_user)
) -> Dict[str, List[Question]]:
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
    
    return {
        "questions": questions,
        "book_id": request.book_id,
        "generated_by": current_user_id
    }


@router.post("/comprehension")
async def analyze_comprehension(
    request: ComprehensionRequest,
    current_user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
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
    
    # Add user context
    analysis['user_id'] = current_user_id
    analysis['book_id'] = request.book_id
    
    return analysis


@router.post("/insights")
async def get_ai_insights(
    request: InsightsRequest,
    current_user_id: str = Depends(get_current_user)
) -> AiInsights:
    """Get AI insights for student notes"""
    ai_service = AIService()
    insights = await ai_service.generate_ai_insights(
        note_content=request.note_content,
        book_context=request.book_context
    )
    
    return insights


@router.post("/recommendations")
async def get_study_recommendations(
    request: RecommendationRequest,
    current_user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get personalized study recommendations based on user activity"""
    ai_service = AIService()
    recommendations = await ai_service.generate_study_recommendations(
        user_id=current_user_id,
        reading_history=request.user_reading_history,
        recent_subjects=request.recent_subjects,
        quiz_performance=request.quiz_performance
    )
    
    return recommendations


@router.post("/study-tips")
async def get_contextual_tips(
    book_id: str,
    current_page: int,
    current_user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get contextual study tips based on current reading"""
    try:
        # Get book content
        book_service = BookService()
        book = await book_service.get_book(book_id)
        
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
        
        # Generate contextual tips
        ai_service = AIService()
        tips = await ai_service.generate_contextual_tips(
            subject=book.subject,
            content_sample=book.content_text[:500] if book.content_text else "",
            page_number=current_page
        )
        
        return tips
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating tips: {str(e)}")
