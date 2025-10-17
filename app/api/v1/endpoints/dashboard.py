"""
Dashboard endpoints for comprehensive user data
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timedelta

from ....services.integration_service import IntegrationService
from ....core.firebase_config import get_db, initialize_firebase
from .auth import get_current_user

router = APIRouter()


@router.get("/overview")
async def get_dashboard_overview(
    current_user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get comprehensive dashboard data including:
    - User progress stats
    - Recent books (continue reading)
    - Quiz statistics
    - AI-powered recommendations
    - Quick actions
    """
    integration_service = IntegrationService()
    dashboard_data = await integration_service.get_dashboard_data(current_user_id)
    return dashboard_data


@router.get("/practice-suggestions")
async def get_practice_suggestions(
    current_user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get AI-powered practice suggestions for Practice screen
    Suggests which books to create quizzes for, which quizzes to retry, etc.
    """
    integration_service = IntegrationService()
    suggestions = await integration_service.get_practice_suggestions(current_user_id)
    return suggestions


@router.get("/reading-analytics/{book_id}")
async def get_reading_analytics(
    book_id: str,
    current_user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get detailed reading analytics for a specific book
    - Progress metrics
    - Reading speed
    - Estimated completion time
    - Reading patterns
    """
    integration_service = IntegrationService()
    analytics = await integration_service.get_reading_analytics(current_user_id, book_id)
    return analytics


@router.get("/stats")
async def get_dashboard_stats(
    current_user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get comprehensive dashboard statistics:
    - Books read (completed)
    - Study streak (consecutive days)
    - Total study time (from reading)
    - Average quiz score
    """
    initialize_firebase()
    db = get_db()
    
    # Get user document
    user_doc = db.collection('users').document(current_user_id).get()
    if not user_doc.exists:
        return {
            "books_read": 0,
            "study_streak": 0,
            "total_study_time_minutes": 0,
            "average_quiz_score": 0.0
        }
    
    user_data = user_doc.to_dict()
    user_books = user_data.get('library_books', {})
    
    # Calculate books read (books with more than 1 page read based on time)
    books_read = 0
    total_reading_time = 0
    last_read_dates = []
    
    for book_id, book_data in user_books.items():
        progress = book_data.get('progress', {})
        
        # Count pages with 60+ seconds from page_times
        page_times = progress.get('page_times', {})
        pages_with_significant_time = sum(1 for time in page_times.values() if time >= 60)
        
        # Count book as "read" if more than 1 page has 60+ seconds
        if pages_with_significant_time > 1:
            books_read += 1
        
        # Sum up reading time from all books
        reading_time = progress.get('reading_time_minutes', 0)
        total_reading_time += reading_time
        
        # Collect last read dates for streak calculation
        last_read = progress.get('last_read_at')
        if last_read:
            last_read_dates.append(last_read)
    
    # Calculate study streak (consecutive days)
    study_streak = _calculate_study_streak(last_read_dates)
    
    # Get quiz statistics
    quiz_results = db.collection('quiz_results').where('user_id', '==', current_user_id).stream()
    total_quizzes = 0
    total_score = 0
    
    for doc in quiz_results:
        result_data = doc.to_dict()
        total_quizzes += 1
        total_score += result_data.get('percentage', 0)
    
    average_quiz_score = (total_score / total_quizzes) if total_quizzes > 0 else 0.0
    
    return {
        "books_read": books_read,
        "study_streak": study_streak,
        "total_study_time_minutes": total_reading_time,
        "average_quiz_score": round(average_quiz_score, 1)
    }


def _calculate_study_streak(last_read_dates: list) -> int:
    """Calculate consecutive days of study"""
    if not last_read_dates:
        return 0
    
    # Sort dates in descending order
    sorted_dates = sorted(last_read_dates, reverse=True)
    
    # Check if there's activity today or yesterday
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    # Convert to dates
    read_dates = [d.date() if isinstance(d, datetime) else d for d in sorted_dates]
    
    if today not in read_dates and yesterday not in read_dates:
        return 0  # Streak broken
    
    # Count consecutive days
    streak = 0
    current_date = today if today in read_dates else yesterday
    
    while current_date in read_dates:
        streak += 1
        current_date -= timedelta(days=1)
    
    return streak

