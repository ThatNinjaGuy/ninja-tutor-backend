"""
Main API router
"""
from fastapi import APIRouter

from .endpoints import books, auth, ai, quiz, notes, user_library, user_quiz, dashboard, reading_analytics
from . import proxy

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(books.router, prefix="/books", tags=["books"])
api_router.include_router(user_library.router, prefix="/library", tags=["user-library"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(quiz.router, prefix="/quizzes", tags=["quizzes"])
api_router.include_router(user_quiz.router, prefix="/user-quiz", tags=["user-quizzes"])
api_router.include_router(notes.router, prefix="/notes", tags=["notes"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(proxy.router, prefix="/proxy", tags=["proxy"])
api_router.include_router(reading_analytics.router, prefix="/reading", tags=["reading-analytics"])
