"""
User Quiz Management endpoints
Handles saving quizzes to user's personal collection and tracking attempts/results
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import uuid
from datetime import datetime

from ....models.quiz import (
    QuizAttempt, UserQuizData, UserQuizResponse, QuizResultResponse,
    QuestionResult, DifficultyLevel
)
from ....services.book_service import BookService
from ....core.firebase_config import get_db
from .auth import get_current_user

router = APIRouter()


class SaveQuizRequest(BaseModel):
    """Request to save a generated quiz to user's collection"""
    quiz_id: str
    book_id: str
    title: str
    subject: str
    difficulty: str
    question_count: int


class SubmitAttemptRequest(BaseModel):
    """Request to submit a quiz attempt"""
    quiz_id: str
    answers: List[QuestionResult]
    time_taken: int  # in minutes


@router.post("/save-quiz")
async def save_quiz_to_user(
    request: SaveQuizRequest,
    current_user_id: str = Depends(get_current_user)
):
    """Save a generated quiz to user's personal collection"""
    try:
        db = get_db()
        
        # Get user document
        user_doc = db.collection('users').document(current_user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_doc.to_dict()
        user_quizzes = user_data.get('user_quizzes', {})
        
        # Check if quiz already exists
        if request.quiz_id in user_quizzes:
            return {
                "message": "Quiz already in your collection",
                "quiz_id": request.quiz_id
            }
        
        # Create quiz entry
        quiz_data = UserQuizData(
            quiz_id=request.quiz_id,
            book_id=request.book_id,
            title=request.title,
            subject=request.subject,
            difficulty=request.difficulty,
            created_at=datetime.now(),
            attempts=[],
            best_score=0.0,
            total_attempts=0
        )
        
        # Add quiz to user's collection
        user_quizzes[request.quiz_id] = quiz_data.dict()
        
        # Update user document
        db.collection('users').document(current_user_id).update({
            'user_quizzes': user_quizzes
        })
        
        return {
            "message": "Quiz saved to your collection successfully",
            "quiz_id": request.quiz_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving quiz: {str(e)}")


@router.get("/my-quizzes", response_model=List[UserQuizResponse])
async def get_user_quizzes(
    current_user_id: str = Depends(get_current_user),
    book_id: Optional[str] = None
):
    """Get user's quiz collection with attempt history"""
    try:
        db = get_db()
        
        # Get user document
        user_doc = db.collection('users').document(current_user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_doc.to_dict()
        user_quizzes = user_data.get('user_quizzes', {})
        
        if not user_quizzes:
            return []
        
        # Get book service for book titles
        book_service = BookService()
        quiz_responses = []
        
        for quiz_id, quiz_data in user_quizzes.items():
            # Filter by book_id if provided
            if book_id and quiz_data.get('book_id') != book_id:
                continue
            
            # Get book title
            book = await book_service.get_book(quiz_data.get('book_id'))
            book_title = book.title if book else "Unknown Book"
            
            # Get last attempt date
            attempts = quiz_data.get('attempts', [])
            last_attempt_date = None
            if attempts:
                last_attempt_date = max(
                    datetime.fromisoformat(attempt['completed_at']) if isinstance(attempt['completed_at'], str) 
                    else attempt['completed_at']
                    for attempt in attempts
                )
            
            quiz_response = UserQuizResponse(
                quiz_id=quiz_id,
                book_id=quiz_data.get('book_id', ''),
                book_title=book_title,
                title=quiz_data.get('title', ''),
                subject=quiz_data.get('subject', ''),
                difficulty=quiz_data.get('difficulty', 'medium'),
                question_count=len(quiz_data.get('questions', [])) if 'questions' in quiz_data else 10,
                total_attempts=quiz_data.get('total_attempts', 0),
                best_score=quiz_data.get('best_score', 0.0),
                last_attempt_date=last_attempt_date,
                created_at=quiz_data.get('created_at', datetime.now())
            )
            quiz_responses.append(quiz_response)
        
        # Sort by created_at (most recent first)
        quiz_responses.sort(key=lambda x: x.created_at, reverse=True)
        
        return quiz_responses
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user quizzes: {str(e)}")


@router.post("/submit-attempt")
async def submit_quiz_attempt(
    request: SubmitAttemptRequest,
    current_user_id: str = Depends(get_current_user)
):
    """Submit a quiz attempt and save results"""
    try:
        db = get_db()
        
        # Get user document
        user_doc = db.collection('users').document(current_user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_doc.to_dict()
        user_quizzes = user_data.get('user_quizzes', {})
        
        if request.quiz_id not in user_quizzes:
            raise HTTPException(status_code=404, detail="Quiz not found in your collection")
        
        quiz_data = user_quizzes[request.quiz_id]
        
        # Calculate score
        total_score = sum(result.points_earned for result in request.answers)
        max_score = sum(result.max_points for result in request.answers)
        percentage = (total_score / max_score * 100) if max_score > 0 else 0
        
        # Determine if passed (70% threshold)
        is_passed = percentage >= 70.0
        
        # Create attempt record
        attempt_number = quiz_data.get('total_attempts', 0) + 1
        attempt = QuizAttempt(
            attempt_number=attempt_number,
            score=total_score,
            percentage=percentage,
            completed_at=datetime.now(),
            time_taken=request.time_taken,
            answers={result.question_id: result.dict() for result in request.answers},
            is_passed=is_passed
        )
        
        # Update quiz data
        attempts = quiz_data.get('attempts', [])
        attempts.append(attempt.dict())
        quiz_data['attempts'] = attempts
        quiz_data['total_attempts'] = attempt_number
        quiz_data['best_score'] = max(quiz_data.get('best_score', 0.0), percentage)
        
        # Save back to user document
        user_quizzes[request.quiz_id] = quiz_data
        db.collection('users').document(current_user_id).update({
            'user_quizzes': user_quizzes
        })
        
        # Return result
        return QuizResultResponse(
            id=str(uuid.uuid4()),
            quiz_id=request.quiz_id,
            user_id=current_user_id,
            total_score=total_score,
            max_score=max_score,
            percentage=percentage,
            correct_answers=sum(1 for result in request.answers if result.is_correct),
            incorrect_answers=sum(1 for result in request.answers if not result.is_correct),
            time_taken=request.time_taken,
            is_passed=is_passed,
            completed_at=datetime.now(),
            attempt_number=attempt_number
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error submitting quiz attempt: {str(e)}")


@router.get("/results", response_model=List[QuizResultResponse])
async def get_quiz_results(
    current_user_id: str = Depends(get_current_user),
    quiz_id: Optional[str] = None
):
    """Get quiz results/attempts for current user"""
    try:
        db = get_db()
        
        # Get user document
        user_doc = db.collection('users').document(current_user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_doc.to_dict()
        user_quizzes = user_data.get('user_quizzes', {})
        
        results = []
        
        for qid, quiz_data in user_quizzes.items():
            # Filter by quiz_id if provided
            if quiz_id and qid != quiz_id:
                continue
            
            # Get all attempts for this quiz
            attempts = quiz_data.get('attempts', [])
            
            for idx, attempt in enumerate(attempts):
                # Calculate correct/incorrect from answers
                answers_dict = attempt.get('answers', {})
                correct = sum(1 for ans in answers_dict.values() if ans.get('is_correct', False))
                total = len(answers_dict)
                incorrect = total - correct
                
                result = QuizResultResponse(
                    id=str(uuid.uuid4()),
                    quiz_id=qid,
                    user_id=current_user_id,
                    total_score=attempt.get('score', 0),
                    max_score=total,  # Simplified, could be calculated from answers
                    percentage=attempt.get('percentage', 0),
                    correct_answers=correct,
                    incorrect_answers=incorrect,
                    time_taken=attempt.get('time_taken', 0),
                    is_passed=attempt.get('is_passed', False),
                    completed_at=attempt.get('completed_at', datetime.now()),
                    attempt_number=attempt.get('attempt_number', idx + 1)
                )
                results.append(result)
        
        # Sort by completed_at (most recent first)
        results.sort(key=lambda x: x.completed_at, reverse=True)
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching quiz results: {str(e)}")


@router.delete("/{quiz_id}")
async def delete_user_quiz(
    quiz_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Remove a quiz from user's collection"""
    try:
        db = get_db()
        
        # Get user document
        user_doc = db.collection('users').document(current_user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_doc.to_dict()
        user_quizzes = user_data.get('user_quizzes', {})
        
        if quiz_id not in user_quizzes:
            raise HTTPException(status_code=404, detail="Quiz not found in your collection")
        
        # Remove quiz
        del user_quizzes[quiz_id]
        
        # Update user document
        db.collection('users').document(current_user_id).update({
            'user_quizzes': user_quizzes
        })
        
        return {"message": "Quiz removed from your collection successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting quiz: {str(e)}")


@router.get("/{quiz_id}/attempts", response_model=List[QuizResultResponse])
async def get_quiz_attempts(
    quiz_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Get all attempts for a specific quiz"""
    try:
        db = get_db()
        
        # Get user document
        user_doc = db.collection('users').document(current_user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_doc.to_dict()
        user_quizzes = user_data.get('user_quizzes', {})
        
        if quiz_id not in user_quizzes:
            raise HTTPException(status_code=404, detail="Quiz not found in your collection")
        
        quiz_data = user_quizzes[quiz_id]
        attempts = quiz_data.get('attempts', [])
        
        results = []
        for idx, attempt in enumerate(attempts):
            # Calculate correct/incorrect from answers
            answers_dict = attempt.get('answers', {})
            correct = sum(1 for ans in answers_dict.values() if ans.get('is_correct', False))
            total = len(answers_dict)
            incorrect = total - correct
            
            result = QuizResultResponse(
                id=str(uuid.uuid4()),
                quiz_id=quiz_id,
                user_id=current_user_id,
                total_score=attempt.get('score', 0),
                max_score=total,
                percentage=attempt.get('percentage', 0),
                correct_answers=correct,
                incorrect_answers=incorrect,
                time_taken=attempt.get('time_taken', 0),
                is_passed=attempt.get('is_passed', False),
                completed_at=attempt.get('completed_at', datetime.now()),
                attempt_number=attempt.get('attempt_number', idx + 1)
            )
            results.append(result)
        
        # Sort by attempt number
        results.sort(key=lambda x: x.attempt_number)
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching quiz attempts: {str(e)}")

