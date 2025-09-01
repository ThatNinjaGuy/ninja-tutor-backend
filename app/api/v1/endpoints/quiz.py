"""
Quiz management endpoints
"""
from typing import List
from fastapi import APIRouter, HTTPException, Depends
import uuid
from datetime import datetime

from ....models.quiz import Quiz, QuizGenRequest, QuizResponse, QuizResult, QuestionResult
from ....services.book_service import BookService
from ....services.ai_service import AIService
from ....core.firebase_config import get_db
from .auth import get_current_user

router = APIRouter()


@router.post("/generate", response_model=QuizResponse)
async def generate_quiz(
    request: QuizGenRequest,
    current_user_id: str = Depends(get_current_user)
):
    """Generate a quiz from book content"""
    # Get book content
    book_service = BookService()
    book = await book_service.get_book(request.book_id)
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if not book.content_text:
        raise HTTPException(status_code=400, detail="Book content not available")
    
    # Generate questions using AI
    ai_service = AIService()
    content = book.content_text[:2000]  # Sample content
    questions = await ai_service.generate_questions(
        content=content,
        question_count=request.question_count,
        difficulty=request.difficulty,
        question_types=request.question_types
    )
    
    # Create quiz
    quiz_id = str(uuid.uuid4())
    quiz = Quiz(
        id=quiz_id,
        title=f"{book.subject} Quiz - {book.title[:30]}",
        description=f"Auto-generated quiz from pages {request.page_range[0]}-{request.page_range[1]}",
        book_id=request.book_id,
        subject=book.subject,
        page_range=request.page_range,
        questions=questions,
        type=request.type if hasattr(request, 'type') else "practice",
        difficulty=request.difficulty,
        created_by=current_user_id,
        created_at=datetime.now()
    )
    
    # Save to Firestore
    db = get_db()
    quiz_dict = quiz.dict()
    quiz_dict['created_at'] = quiz.created_at
    quiz_dict['questions'] = [q.dict() for q in quiz.questions]
    quiz_dict['settings'] = quiz.settings.dict()
    
    db.collection('quizzes').document(quiz_id).set(quiz_dict)
    
    return QuizResponse(
        id=quiz.id,
        title=quiz.title,
        description=quiz.description,
        book_id=quiz.book_id,
        subject=quiz.subject,
        question_count=len(quiz.questions),
        difficulty=quiz.difficulty.value,
        type=quiz.type.value,
        created_at=quiz.created_at
    )


@router.get("/{quiz_id}", response_model=Quiz)
async def get_quiz(quiz_id: str):
    """Get a specific quiz"""
    try:
        db = get_db()
        doc = db.collection('quizzes').document(quiz_id).get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Quiz not found")
        
        quiz_data = doc.to_dict()
        quiz_data['id'] = doc.id
        
        return Quiz(**quiz_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching quiz: {str(e)}")


@router.post("/{quiz_id}/submit", response_model=QuizResult)
async def submit_quiz(
    quiz_id: str,
    answers: List[QuestionResult],
    current_user_id: str = Depends(get_current_user)
):
    """Submit quiz answers and get results"""
    try:
        # Get quiz
        quiz_doc = get_db().collection('quizzes').document(quiz_id).get()
        if not quiz_doc.exists:
            raise HTTPException(status_code=404, detail="Quiz not found")
        
        quiz_data = quiz_doc.to_dict()
        quiz = Quiz(**quiz_data)
        
        # Calculate score
        total_score = 0
        max_score = 0
        processed_answers = []
        
        for question in quiz.questions:
            max_score += question.points
            
            # Find user's answer for this question
            user_answer = next((a for a in answers if a.question_id == question.id), None)
            
            if user_answer:
                is_correct = False
                
                if question.type == "multiple_choice":
                    # Check if selected option is correct
                    for option in question.options:
                        if option.id in user_answer.selected_options and option.is_correct:
                            is_correct = True
                            break
                elif question.type == "true_false":
                    is_correct = user_answer.user_answer == question.correct_answer
                elif question.type == "short_answer":
                    # Simple string comparison - in production, use fuzzy matching
                    is_correct = user_answer.user_answer.lower().strip() == question.correct_answer.lower().strip()
                
                points_earned = question.points if is_correct else 0
                total_score += points_earned
                
                processed_answers.append(QuestionResult(
                    question_id=question.id,
                    user_answer=user_answer.user_answer,
                    selected_options=user_answer.selected_options,
                    is_correct=is_correct,
                    points_earned=points_earned,
                    time_spent=user_answer.time_spent
                ))
        
        # Create quiz result
        result_id = str(uuid.uuid4())
        percentage = (total_score / max_score * 100) if max_score > 0 else 0
        
        quiz_result = QuizResult(
            id=result_id,
            quiz_id=quiz_id,
            user_id=current_user_id,
            question_results=processed_answers,
            total_score=total_score,
            max_score=max_score,
            percentage=percentage,
            time_taken=sum(a.time_spent or 0 for a in processed_answers) // 60,  # Convert to minutes
            completed_at=datetime.now()
        )
        
        # Save result
        db = get_db()
        result_dict = quiz_result.dict()
        result_dict['completed_at'] = quiz_result.completed_at
        result_dict['question_results'] = [qr.dict() for qr in quiz_result.question_results]
        
        db.collection('quiz_results').document(result_id).set(result_dict)
        
        return quiz_result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error submitting quiz: {str(e)}")


@router.get("/stats/{user_id}")
async def get_quiz_stats(
    user_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Get quiz statistics for a user"""
    try:
        # Only allow users to view their own stats
        if user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        db = get_db()
        
        # Get all quiz results for user
        results_query = db.collection('quiz_results').where('user_id', '==', user_id)
        results_docs = results_query.stream()
        
        total_quizzes = 0
        total_score = 0
        total_possible = 0
        subject_stats = {}
        
        for doc in results_docs:
            result_data = doc.to_dict()
            total_quizzes += 1
            total_score += result_data.get('total_score', 0)
            total_possible += result_data.get('max_score', 0)
            
            # Get quiz info for subject stats
            quiz_id = result_data.get('quiz_id')
            if quiz_id:
                quiz_doc = db.collection('quizzes').document(quiz_id).get()
                if quiz_doc.exists:
                    quiz_data = quiz_doc.to_dict()
                    subject = quiz_data.get('subject', 'Unknown')
                    
                    if subject not in subject_stats:
                        subject_stats[subject] = {'count': 0, 'avg_score': 0, 'total_score': 0}
                    
                    subject_stats[subject]['count'] += 1
                    subject_stats[subject]['total_score'] += result_data.get('percentage', 0)
        
        # Calculate averages
        for subject in subject_stats:
            if subject_stats[subject]['count'] > 0:
                subject_stats[subject]['avg_score'] = subject_stats[subject]['total_score'] / subject_stats[subject]['count']
        
        overall_percentage = (total_score / total_possible * 100) if total_possible > 0 else 0
        
        return {
            "total_quizzes_taken": total_quizzes,
            "overall_percentage": overall_percentage,
            "subject_breakdown": subject_stats,
            "total_points_earned": total_score,
            "total_possible_points": total_possible
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching quiz stats: {str(e)}")
