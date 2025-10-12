"""
Dashboard endpoints for comprehensive user data
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends

from ....services.integration_service import IntegrationService
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

