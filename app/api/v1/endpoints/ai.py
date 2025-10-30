"""
AI-powered features endpoints
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import logging

from ....models.quiz import QuizGenRequest, Question, DifficultyLevel
from ....models.note import AiInsights
from ....services.ai_service import AIService
from ....services.book_service import BookService
from .auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


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


# ========== Reading Intelligence Endpoints ==========

class ReadingQuestionRequest(BaseModel):
    """Request for asking questions about reading content"""
    question: str
    book_id: str
    current_page: int
    selected_text: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = []
    previous_page_text: Optional[str] = None
    current_page_text: Optional[str] = None
    next_page_text: Optional[str] = None


class BatchPageContentRequest(BaseModel):
    """Request for getting content from multiple pages"""
    book_id: str
    page_numbers: List[int]


@router.post("/reading/ask")
async def ask_reading_question(
    request: ReadingQuestionRequest,
    current_user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Answer questions about reading content with intelligent context extraction.
    Extracts current page + surrounding pages for better context.
    """
    try:
        from ....services.file_processor import FileProcessor
        
        logger.info(f"📖 Reading Q&A request for book_id={request.book_id}, page={request.current_page}")
        
        # Get book information
        book_service = BookService()
        book = await book_service.get_book(request.book_id)
        
        if not book:
            logger.error(f"❌ Book not found: {request.book_id}")
            raise HTTPException(status_code=404, detail="Book not found")
        
        logger.info(f"✅ Book found: {book.title}")
        logger.info(f"📄 Book file_url: '{book.file_url}'")
        logger.info(f"📚 Book total_pages: {book.total_pages}")
        
        if not book.file_url:
            logger.error(f"❌ Book has no file_url")
            raise HTTPException(status_code=400, detail="Book PDF not available")
        
        # Calculate page range for context
        # If selected text: current page + 1 before/after (3 pages)
        # If no selection: current page + 2 before/after (5 pages)
        pages_before = 1 if request.selected_text else 2
        pages_after = 1 if request.selected_text else 2
        
        start_page = max(1, request.current_page - pages_before)
        end_page = min(book.total_pages, request.current_page + pages_after)
        
        logger.info(f"📊 Extracting pages {start_page}-{end_page} (current page: {request.current_page})")
        
        # Extract page content
        file_processor = FileProcessor()
        page_content = await file_processor.extract_text_from_pdf_pages(
            book.file_url,
            start_page,
            end_page
        )
        
        logger.info(f"✅ Extracted {len(page_content)} characters from pages {start_page}-{end_page}")
        
        # Log a sample of extracted content for verification
        if len(page_content) > 0:
            sample = page_content[:200].replace('\n', ' ')
            logger.info(f"📄 Content sample: '{sample}...'")
        
        provided_page_context = {
            "previous_page_text": (request.previous_page_text or "").strip(),
            "current_page_text": (request.current_page_text or "").strip(),
            "next_page_text": (request.next_page_text or "").strip(),
        }

        provided_page_context = {
            key: value for key, value in provided_page_context.items() if value
        }

        if provided_page_context:
            context_lengths = {key: len(value) for key, value in provided_page_context.items()}
            logger.info(f"🧠 Provided page context lengths: {context_lengths}")

        # Prepare book metadata
        book_metadata = {
            "book_id": request.book_id,
            "title": book.title,
            "author": book.author,
            "subject": book.subject,
            "current_page": request.current_page,
            "total_pages": book.total_pages,
            "extracted_range": f"{start_page}-{end_page}"
        }
        
        logger.info(f"📚 Book metadata: {book_metadata}")
        logger.info(f"❓ Question: '{request.question}'")
        logger.info(f"📝 Selected text: {request.selected_text[:100] if request.selected_text else 'None'}")
        
        # Get AI answer using ADK agent
        ai_service = AIService()
        result = await ai_service.answer_reading_question(
            question=request.question,
            page_content=page_content,
            selected_text=request.selected_text,
            book_metadata=book_metadata,
            conversation_history=request.conversation_history,
            user_id=current_user_id,
            book_file_path=book.file_url,
            provided_page_context=provided_page_context,
        )
        
        logger.info(f"✅ AI response generated successfully")
        logger.info(f"   Response length: {len(result.get('answer', ''))} chars")
        logger.info(f"   Tokens used: {result.get('tokens_used', 'N/A')}")
        logger.info(f"   Context sent: {result.get('context_chars', 'N/A')} chars")
        
        # Add context information
        result["context_range"] = f"Pages {start_page}-{end_page}"
        result["current_page"] = request.current_page
        result["book_id"] = request.book_id
        result["user_id"] = current_user_id
        result["has_selected_text"] = bool(request.selected_text)
        if provided_page_context:
            result["client_context_sections"] = {
                key: len(value) for key, value in provided_page_context.items()
            }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error answering reading question: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing question: {str(e)}")


@router.post("/reading/page-content-batch")
async def get_multiple_page_content(
    request: BatchPageContentRequest,
    current_user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Extract and return content for multiple pages in a single request.
    Used by frontend to efficiently get page context for AI features.
    """
    try:
        from ....services.file_processor import FileProcessor
        
        # Get book information
        book_service = BookService()
        book = await book_service.get_book(request.book_id)
        
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
        
        if not book.file_url:
            raise HTTPException(status_code=400, detail="Book PDF not available")
        
        # Validate page numbers
        for page_number in request.page_numbers:
            if page_number < 1 or page_number > book.total_pages:
                raise HTTPException(
                    status_code=400,
                    detail=f"Page number {page_number} out of range (1-{book.total_pages})"
                )
        
        # Remove duplicates and sort
        unique_pages = sorted(set(request.page_numbers))
        
        logger.info(f"📖 Extracting content for {len(unique_pages)} pages: {unique_pages}")
        
        # Extract page content
        file_processor = FileProcessor()
        page_contents = {}
        
        for page_number in unique_pages:
            try:
                page_content = await file_processor.extract_text_from_pdf_page(
                    book.file_url,
                    page_number
                )
                page_contents[str(page_number)] = page_content
            except Exception as e:
                logger.warning(f"⚠️ Failed to extract page {page_number}: {str(e)}")
                page_contents[str(page_number)] = ""
        
        return {
            "book_id": request.book_id,
            "total_pages": book.total_pages,
            "pages": page_contents,
            "book_title": book.title,
            "book_subject": book.subject
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting page content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error extracting pages: {str(e)}")


@router.get("/reading/page-content/{book_id}/{page_number}")
async def get_page_content(
    book_id: str,
    page_number: int,
    current_user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Extract and return content for a specific page.
    Used by frontend to display context or for text extraction.
    """
    try:
        from ....services.file_processor import FileProcessor
        
        # Get book information
        book_service = BookService()
        book = await book_service.get_book(book_id)
        
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
        
        if not book.file_url:
            raise HTTPException(status_code=400, detail="Book PDF not available")
        
        # Validate page number
        if page_number < 1 or page_number > book.total_pages:
            raise HTTPException(
                status_code=400,
                detail=f"Page number {page_number} out of range (1-{book.total_pages})"
            )
        
        # Extract page content
        file_processor = FileProcessor()
        page_content = await file_processor.extract_text_from_pdf_page(
            book.file_url,
            page_number
        )
        
        return {
            "book_id": book_id,
            "page_number": page_number,
            "total_pages": book.total_pages,
            "content": page_content,
            "book_title": book.title,
            "book_subject": book.subject
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting page content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error extracting page: {str(e)}")
