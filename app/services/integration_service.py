"""
Integration service to coordinate between AI, Quiz, and User data
Makes screens fully operational by providing combined data
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import HTTPException

from ..core.firebase_config import get_db
from .ai_service import AIService
from .book_service import BookService


class IntegrationService:
    """Service for integrating AI with user data for operational screens"""
    
    def __init__(self):
        self.db = get_db()
        self.ai_service = AIService()
        self.book_service = BookService()
    
    async def get_dashboard_data(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive dashboard data with AI recommendations"""
        try:
            # Get user document
            user_doc = self.db.collection('users').document(user_id).get()
            if not user_doc.exists:
                raise HTTPException(status_code=404, detail="User not found")
            
            user_data = user_doc.to_dict()
            
            # Extract user data
            library_books = user_data.get('library_books', {})
            user_quizzes = user_data.get('user_quizzes', {})
            progress = user_data.get('progress', {})
            
            # Get recent books (for continue reading)
            recent_books = []
            for book_id, book_data in library_books.items():
                book = await self.book_service.get_book(book_id)
                if book:
                    progress_data = book_data.get('progress', {})
                    recent_books.append({
                        'book_id': book_id,
                        'title': book.title,
                        'author': book.author,
                        'subject': book.subject,
                        'cover_url': book.cover_url,
                        'current_page': progress_data.get('current_page', 0),
                        'total_pages': book.total_pages,
                        'progress_percentage': progress_data.get('progress_percentage', 0.0),
                        'last_read_at': progress_data.get('last_read_at')
                    })
            
            # Sort by last_read_at
            recent_books.sort(
                key=lambda x: x.get('last_read_at') or datetime.min,
                reverse=True
            )
            
            # Get quiz statistics
            quiz_stats = self._calculate_quiz_stats(user_quizzes)
            
            # Generate AI recommendations
            recent_subjects = list(set([b['subject'] for b in recent_books[:5]]))
            ai_recommendations = await self.ai_service.generate_study_recommendations(
                user_id=user_id,
                reading_history=[b['book_id'] for b in recent_books],
                recent_subjects=recent_subjects,
                quiz_performance=quiz_stats.get('subject_performance', {})
            )
            
            return {
                "progress": {
                    "total_books_read": progress.get('total_books_read', 0),
                    "current_streak": progress.get('current_streak', 0),
                    "total_time_spent": progress.get('total_time_spent', 0),
                    "total_quizzes_taken": progress.get('total_quizzes_taken', 0),
                    "average_quiz_score": progress.get('average_quiz_score', 0.0)
                },
                "recent_books": recent_books[:5],
                "quiz_stats": quiz_stats,
                "ai_recommendations": ai_recommendations.get('recommendations', []),
                "quick_actions": self._generate_quick_actions(recent_books, user_quizzes)
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting dashboard data: {str(e)}")
    
    def _calculate_quiz_stats(self, user_quizzes: Dict) -> Dict[str, Any]:
        """Calculate quiz statistics from user_quizzes data"""
        if not user_quizzes:
            return {
                "total_quizzes": 0,
                "total_attempts": 0,
                "average_score": 0.0,
                "subject_performance": {}
            }
        
        total_quizzes = len(user_quizzes)
        total_attempts = 0
        all_scores = []
        subject_scores = {}
        
        for quiz_id, quiz_data in user_quizzes.items():
            attempts = quiz_data.get('attempts', [])
            total_attempts += len(attempts)
            
            subject = quiz_data.get('subject', 'Unknown')
            
            for attempt in attempts:
                score = attempt.get('percentage', 0)
                all_scores.append(score)
                
                if subject not in subject_scores:
                    subject_scores[subject] = []
                subject_scores[subject].append(score)
        
        # Calculate averages
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
        
        subject_performance = {}
        for subject, scores in subject_scores.items():
            subject_performance[subject] = sum(scores) / len(scores) if scores else 0.0
        
        return {
            "total_quizzes": total_quizzes,
            "total_attempts": total_attempts,
            "average_score": avg_score,
            "subject_performance": subject_performance
        }
    
    def _generate_quick_actions(self, recent_books: List[Dict], user_quizzes: Dict) -> List[Dict[str, str]]:
        """Generate contextual quick actions for dashboard"""
        actions = []
        
        # If has books with progress < 100%, suggest continue reading
        for book in recent_books[:3]:
            if book.get('progress_percentage', 0) < 1.0 and book.get('progress_percentage', 0) > 0:
                actions.append({
                    "title": f"Continue {book['title'][:20]}...",
                    "icon": "menu_book",
                    "action": "continue_reading",
                    "book_id": book['book_id']
                })
                break
        
        # If has books but no quizzes, suggest creating one
        if recent_books and not user_quizzes:
            actions.append({
                "title": "Generate your first quiz",
                "icon": "quiz",
                "action": "create_quiz",
                "book_id": recent_books[0]['book_id']
            })
        
        # If has quizzes with low scores, suggest retrying
        if user_quizzes:
            for quiz_id, quiz_data in user_quizzes.items():
                best_score = quiz_data.get('best_score', 0)
                if best_score < 70:
                    actions.append({
                        "title": "Retry quiz to improve score",
                        "icon": "replay",
                        "action": "retry_quiz",
                        "quiz_id": quiz_id
                    })
                    break
        
        return actions[:3]  # Return max 3 actions
    
    async def get_practice_suggestions(self, user_id: str) -> Dict[str, Any]:
        """Get AI-powered practice suggestions for Practice screen"""
        try:
            user_doc = self.db.collection('users').document(user_id).get()
            if not user_doc.exists:
                raise HTTPException(status_code=404, detail="User not found")
            
            user_data = user_doc.to_dict()
            library_books = user_data.get('library_books', {})
            user_quizzes = user_data.get('user_quizzes', {})
            
            suggestions = []
            
            # Suggest quizzes for books without quizzes
            books_with_quizzes = set(quiz_data.get('book_id') for quiz_data in user_quizzes.values())
            
            for book_id, book_data in library_books.items():
                if book_id not in books_with_quizzes:
                    book = await self.book_service.get_book(book_id)
                    if book:
                        progress_data = book_data.get('progress', {})
                        current_page = progress_data.get('current_page', 0)
                        
                        if current_page > 10:  # Only suggest if they've read some
                            suggestions.append({
                                "type": "generate_quiz",
                                "book_id": book_id,
                                "book_title": book.title,
                                "subject": book.subject,
                                "suggested_page_range": [1, min(current_page, 50)],
                                "reason": f"You've read {current_page} pages - test your knowledge!"
                            })
            
            # Suggest retrying quizzes with low scores
            for quiz_id, quiz_data in user_quizzes.items():
                best_score = quiz_data.get('best_score', 0)
                if best_score < 80:
                    suggestions.append({
                        "type": "retry_quiz",
                        "quiz_id": quiz_id,
                        "title": quiz_data.get('title', ''),
                        "current_best": best_score,
                        "reason": f"Current best: {best_score}% - you can do better!"
                    })
            
            return {
                "suggestions": suggestions[:5],
                "total_available": len(suggestions)
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting practice suggestions: {str(e)}")
    
    async def get_reading_analytics(self, user_id: str, book_id: str) -> Dict[str, Any]:
        """Get reading analytics for a specific book"""
        try:
            user_doc = self.db.collection('users').document(user_id).get()
            if not user_doc.exists:
                raise HTTPException(status_code=404, detail="User not found")
            
            user_data = user_doc.to_dict()
            library_books = user_data.get('library_books', {})
            
            if book_id not in library_books:
                return {
                    "in_library": False,
                    "message": "Add this book to your library to track progress"
                }
            
            book_data = library_books[book_id]
            progress_data = book_data.get('progress', {})
            
            # Get book details
            book = await self.book_service.get_book(book_id)
            if not book:
                raise HTTPException(status_code=404, detail="Book not found")
            
            # Calculate analytics
            current_page = progress_data.get('current_page', 0)
            total_pages = book.total_pages
            reading_time = progress_data.get('reading_time_minutes', 0)
            
            pages_per_session = current_page / max(reading_time / 30, 1) if reading_time > 0 else 0
            estimated_completion_time = ((total_pages - current_page) / pages_per_session * 30) if pages_per_session > 0 else 0
            
            return {
                "in_library": True,
                "current_page": current_page,
                "total_pages": total_pages,
                "progress_percentage": progress_data.get('progress_percentage', 0.0),
                "reading_time_minutes": reading_time,
                "pages_per_session": round(pages_per_session, 1),
                "estimated_completion_minutes": round(estimated_completion_time),
                "reading_status": progress_data.get('reading_status', 'not_started'),
                "started_at": progress_data.get('started_at'),
                "last_read_at": progress_data.get('last_read_at')
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting reading analytics: {str(e)}")

