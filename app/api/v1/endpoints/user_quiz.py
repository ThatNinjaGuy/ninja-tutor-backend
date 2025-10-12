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
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class SaveQuizRequest(BaseModel):
    """Request to save a generated quiz to user's collection"""
    quiz_id: str
    book_id: str
    title: str
    subject: str
    difficulty: str
    question_count: int


class AnswerSubmission(BaseModel):
    """Individual answer submission"""
    question_id: str
    selected_options: List[str] = []
    user_answer: str = ""
    is_correct: bool
    points_earned: int
    max_points: int
    time_spent: int = 0


class SubmitAttemptRequest(BaseModel):
    """Request to submit a quiz attempt"""
    quiz_id: str
    answers: List[AnswerSubmission]
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
        logger.info(f"📝 Submitting quiz attempt: quiz_id={request.quiz_id}, user={current_user_id}")
        logger.info(f"📊 Answers received: {len(request.answers)} questions, time={request.time_taken}min")
        
        db = get_db()
        
        # Get user document
        user_doc = db.collection('users').document(current_user_id).get()
        if not user_doc.exists:
            logger.error(f"❌ User not found: {current_user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_doc.to_dict()
        user_quizzes = user_data.get('user_quizzes', {})
        
        logger.debug(f"User has {len(user_quizzes)} quizzes in collection")
        
        # If quiz not in user's collection, fetch it from quizzes collection and add it
        if request.quiz_id not in user_quizzes:
            logger.info(f"📥 Quiz {request.quiz_id} not in user's collection, fetching from quizzes collection...")
            
            # Fetch quiz from main quizzes collection
            quiz_doc = db.collection('quizzes').document(request.quiz_id).get()
            if not quiz_doc.exists:
                logger.error(f"❌ Quiz {request.quiz_id} not found in quizzes collection")
                raise HTTPException(status_code=404, detail="Quiz not found")
            
            quiz_firestore_data = quiz_doc.to_dict()
            
            # Get book info for the quiz
            book_service = BookService()
            book = await book_service.get_book(quiz_firestore_data.get('book_id'))
            
            # Create new user quiz entry
            quiz_data = {
                'quiz_id': request.quiz_id,
                'book_id': quiz_firestore_data.get('book_id', ''),
                'title': quiz_firestore_data.get('title', 'Untitled Quiz'),
                'subject': quiz_firestore_data.get('subject', 'General'),
                'difficulty': quiz_firestore_data.get('difficulty', 'medium'),
                'created_at': quiz_firestore_data.get('created_at', datetime.now()),
                'attempts': [],
                'best_score': 0.0,
                'total_attempts': 0
            }
            user_quizzes[request.quiz_id] = quiz_data
            logger.info(f"✅ Created new quiz entry in user's collection: {quiz_data.get('title')}")
        else:
            quiz_data = user_quizzes[request.quiz_id]
            logger.info(f"✅ Found existing quiz in user's collection: {quiz_data.get('title', 'Untitled')}")
        
        # Calculate score
        total_score = sum(result.points_earned for result in request.answers)
        max_score = sum(result.max_points for result in request.answers)
        percentage = (total_score / max_score * 100) if max_score > 0 else 0
        
        logger.info(f"📈 Score calculated: {total_score}/{max_score} = {percentage:.1f}%")
        
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
        
        logger.info(f"✨ Created attempt #{attempt_number}: score={percentage:.1f}%, passed={is_passed}")
        
        # Update quiz data
        attempts = quiz_data.get('attempts', [])
        attempts.append(attempt.dict())
        quiz_data['attempts'] = attempts
        quiz_data['total_attempts'] = attempt_number
        quiz_data['best_score'] = max(quiz_data.get('best_score', 0.0), percentage)
        
        logger.info(f"📝 Updating quiz: {len(attempts)} total attempts, best score: {quiz_data['best_score']:.1f}%")
        
        # Save back to user document
        user_quizzes[request.quiz_id] = quiz_data
        db.collection('users').document(current_user_id).update({
            'user_quizzes': user_quizzes
        })
        
        logger.info(f"✅ Quiz attempt saved successfully to user document")
        logger.debug(f"Attempts array now has {len(attempts)} entries")
        
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
    logger.info(f"Getting quiz results for user {current_user_id}, quiz_id filter: {quiz_id}")
    try:
        db = get_db()
        
        # Get user document
        user_doc = db.collection('users').document(current_user_id).get()
        if not user_doc.exists:
            logger.warning(f"User {current_user_id} not found")
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_doc.to_dict()
        user_quizzes = user_data.get('user_quizzes', {})
        logger.debug(f"Found {len(user_quizzes)} quizzes for user")
        
        results = []
        
        for qid, quiz_data in user_quizzes.items():
            # Filter by quiz_id if provided
            if quiz_id and qid != quiz_id:
                logger.debug(f"Skipping quiz {qid} - does not match filter {quiz_id}")
                continue
            
            logger.debug(f"Processing quiz {qid} with data: {quiz_data}")
            # Get all attempts for this quiz
            attempts = quiz_data.get('attempts', [])
            logger.debug(f"Processing {len(attempts)} attempts for quiz {qid}")
            
            for idx, attempt in enumerate(attempts):
                # Calculate correct/incorrect from answers
                answers_dict = attempt.get('answers', {})
                correct = sum(1 for ans in answers_dict.values() if ans.get('is_correct', False))
                total = len(answers_dict)
                incorrect = total - correct
                
                logger.debug(f"Quiz {qid} attempt {idx+1}: {correct}/{total} correct")
                
                # Build question_results array from answers dict
                question_results = []
                for question_id, answer_data in answers_dict.items():
                    question_result = {
                        'question_id': question_id,
                        'user_answers': answer_data.get('selected_options', []),
                        'is_correct': answer_data.get('is_correct', False),
                        'points_earned': answer_data.get('points_earned', 0),
                        'max_points': answer_data.get('max_points', 1),
                        'time_spent': answer_data.get('time_spent', 0),
                        'hints_used': 0  # Default value
                    }
                    question_results.append(question_result)
                
                logger.debug(f"Built {len(question_results)} question results for attempt {idx+1}")
                
                result = QuizResultResponse(
                    id=str(uuid.uuid4()),
                    quiz_id=qid,
                    user_id=current_user_id,
                    question_results=question_results,
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
        logger.info(f"Returning {len(results)} quiz results")
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching quiz results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching quiz results: {str(e)}")


@router.get("/attempt/{quiz_id}/{attempt_number}")
async def get_attempt_detail(
    quiz_id: str,
    attempt_number: int,
    current_user_id: str = Depends(get_current_user)
):
    """Get detailed information about a specific quiz attempt"""
    logger.info(f"Getting attempt #{attempt_number} for quiz {quiz_id}, user {current_user_id}")
    try:
        db = get_db()
        
        # Get user document
        user_doc = db.collection('users').document(current_user_id).get()
        if not user_doc.exists:
            logger.warning(f"User {current_user_id} not found")
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_doc.to_dict()
        user_quizzes = user_data.get('user_quizzes', {})
        
        # Check if quiz exists in user's collection
        if quiz_id not in user_quizzes:
            logger.error(f"Quiz {quiz_id} not found in user's collection")
            raise HTTPException(status_code=404, detail="Quiz not found in your collection")
        
        quiz_data = user_quizzes[quiz_id]
        attempts = quiz_data.get('attempts', [])
        
        # Find the specific attempt
        attempt = None
        for att in attempts:
            if att.get('attempt_number') == attempt_number:
                attempt = att
                break
        
        if not attempt:
            logger.error(f"Attempt #{attempt_number} not found for quiz {quiz_id}")
            raise HTTPException(status_code=404, detail=f"Attempt #{attempt_number} not found")
        
        logger.info(f"✅ Found attempt #{attempt_number} with {len(attempt.get('answers', {}))} answers")
        
        # Return the attempt data
        return {
            'quiz_id': quiz_id,
            'attempt_number': attempt.get('attempt_number'),
            'score': attempt.get('score'),
            'percentage': attempt.get('percentage'),
            'is_passed': attempt.get('is_passed'),
            'time_taken': attempt.get('time_taken'),
            'completed_at': attempt.get('completed_at'),
            'answers': attempt.get('answers', {})  # Full answers dict with selected_options
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching attempt detail: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching attempt detail: {str(e)}")


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

