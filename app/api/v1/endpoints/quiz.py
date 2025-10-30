"""
Quiz management endpoints
"""
from typing import List
from fastapi import APIRouter, HTTPException, Depends
import uuid
from datetime import datetime
import logging

from ....models.quiz import Quiz, QuizGenRequest, QuizResponse, QuizResult, QuestionResult, UserQuizData
from ....services.book_service import BookService
from ....services.ai_service import AIService
from ....services.file_processor import FileProcessor
from ....core.firebase_config import get_db
from .auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/debug/collections")
async def debug_collections(
    current_user_id: str = Depends(get_current_user)
):
    """Debug endpoint to check Firebase collections"""
    try:
        db = get_db()
        
        # Count documents in quizzes collection
        quizzes_count = len(list(db.collection('quizzes').stream()))
        
        # Get sample quiz IDs
        quiz_ids = [doc.id for doc in db.collection('quizzes').limit(5).stream()]
        
        return {
            "quizzes_collection_count": quizzes_count,
            "sample_quiz_ids": quiz_ids,
            "user_id": current_user_id
        }
    except Exception as e:
        logger.error(f"❌ Debug error: {str(e)}")
        return {"error": str(e)}


@router.get("/all", response_model=List[QuizResponse])
async def list_all_quizzes(
    current_user_id: str = Depends(get_current_user)
):
    """List all quizzes in the quizzes collection (for debugging)"""
    try:
        db = get_db()
        quizzes_ref = db.collection('quizzes')
        docs = quizzes_ref.stream()
        
        quizzes = []
        for doc in docs:
            quiz_data = doc.to_dict()
            quizzes.append(QuizResponse(
                id=doc.id,
                title=quiz_data.get('title', 'Untitled'),
                description=quiz_data.get('description'),
                book_id=quiz_data.get('book_id', ''),
                subject=quiz_data.get('subject', ''),
                question_count=len(quiz_data.get('questions', [])),
                difficulty=quiz_data.get('difficulty', 'medium'),
                type=quiz_data.get('type', 'practice'),
                created_at=quiz_data.get('created_at', datetime.now())
            ))
        
        logger.info(f"📋 Found {len(quizzes)} quizzes in collection")
        return quizzes
        
    except Exception as e:
        logger.error(f"❌ Error listing quizzes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing quizzes: {str(e)}")


@router.post("/generate", response_model=Quiz)
async def generate_quiz(
    request: QuizGenRequest,
    current_user_id: str = Depends(get_current_user)
):
    """Generate a quiz from book content"""
    logger.info(f"🎯 Quiz generation started for book_id={request.book_id}, user={current_user_id}")
    logger.info(f"📊 Request params: pages={request.page_range}, questions={request.question_count}, difficulty={request.difficulty}")
    
    # Get book content
    book_service = BookService()
    logger.info(f"📚 Fetching book from database...")
    book = await book_service.get_book(request.book_id)
    
    if not book:
        logger.error(f"❌ Book not found: {request.book_id}")
        raise HTTPException(status_code=404, detail="Book not found")
    
    logger.info(f"✅ Book found: {book.title} by {book.author}")
    logger.info(f"📄 Book file_url: {book.file_url}")
    logger.info(f"📝 Book has content_text: {hasattr(book, 'content_text') and book.content_text is not None}")
    
    # Extract content from PDF if not already available
    content_text = None
    if hasattr(book, 'content_text') and book.content_text:
        logger.info(f"✅ Using existing content_text ({len(book.content_text)} chars)")
        content_text = book.content_text
    elif book.file_url:
        logger.info(f"📖 Extracting content from PDF: {book.file_url}")
        try:
            # Extract from local file path (file_url contains the local path)
            content_text, _ = await FileProcessor.extract_text_from_pdf(book.file_url)
            logger.info(f"✅ Extracted {len(content_text)} characters from PDF")
        except Exception as e:
            logger.error(f"❌ Failed to extract PDF content: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to extract book content: {str(e)}")
    
    if not content_text:
        logger.error(f"❌ No content available for book {request.book_id}")
        raise HTTPException(status_code=400, detail="Book content not available")
    
    # Generate questions using AI
    logger.info(f"🤖 Generating questions with AI...")
    ai_service = AIService()
    
    # Extract content from requested page range if using PDF
    start_page = request.page_range[0]
    end_page = request.page_range[1]
    
    if book.file_url:
        logger.info(f"📖 Extracting content from pages {start_page}-{end_page}")
        try:
            content = await FileProcessor.extract_text_from_pdf_pages(
                book.file_url,
                start_page,
                end_page
            )
            logger.info(f"📝 Extracted {len(content)} characters from pages {start_page}-{end_page}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to extract specific pages, using full content: {str(e)}")
            content = content_text
    else:
        # Fallback to character-based slicing if no PDF
        logger.info(f"📝 Using character-based slicing for pages {start_page}-{end_page}")
        chars_per_page = 3000
        start_char = (start_page - 1) * chars_per_page
        end_char = end_page * chars_per_page
        content = content_text[start_char:end_char] if len(content_text) > start_char else content_text[:5000]
        logger.info(f"📝 Using content slice: chars {start_char}-{end_char} (length: {len(content)})")
    
    try:
        questions = await ai_service.generate_questions(
            content=content,
            question_count=request.question_count,
            difficulty=request.difficulty,
            question_types=request.question_types
        )
        logger.info(f"✅ Generated {len(questions)} questions")
    except Exception as e:
        logger.error(f"❌ AI question generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate questions: {str(e)}")
    
    # Create quiz
    logger.info(f"💾 Creating quiz object...")
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
    
    # Save to Firestore quizzes collection
    logger.info(f"💾 Saving quiz to Firestore...")
    logger.debug(f"Quiz ID: {quiz_id}")
    logger.debug(f"Quiz title: {quiz.title}")
    logger.debug(f"Quiz book_id: {quiz.book_id}")
    logger.debug(f"Number of questions: {len(quiz.questions)}")
    
    db = get_db()
    quiz_dict = quiz.dict()
    quiz_dict['created_at'] = quiz.created_at
    quiz_dict['questions'] = [q.dict() for q in quiz.questions]
    quiz_dict['settings'] = quiz.settings.dict()
    
    logger.debug(f"Quiz dict keys: {quiz_dict.keys()}")
    
    try:
        # Save to quizzes collection
        quiz_ref = db.collection('quizzes').document(quiz_id)
        logger.debug(f"Writing to Firestore path: quizzes/{quiz_id}")
        quiz_ref.set(quiz_dict)
        
        # Verify the write
        verify_doc = quiz_ref.get()
        if verify_doc.exists:
            logger.info(f"✅ Quiz saved and verified in quizzes collection: {quiz_id}")
            logger.debug(f"Saved quiz has {len(verify_doc.to_dict().get('questions', []))} questions")
        else:
            logger.error(f"❌ Quiz document not found after save attempt!")
            
    except Exception as e:
        logger.error(f"❌ Failed to save quiz: {str(e)}")
        logger.exception("Full exception trace:")
        raise HTTPException(status_code=500, detail=f"Failed to save quiz: {str(e)}")
    
    # Also save to user's quiz collection
    logger.info(f"👤 Saving quiz to user's collection...")
    try:
        user_doc = db.collection('users').document(current_user_id).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            user_quizzes = user_data.get('user_quizzes', {})
            
            # Create user quiz entry
            user_quiz = UserQuizData(
                quiz_id=quiz_id,
                book_id=request.book_id,
                title=quiz.title,
                subject=quiz.subject,
                difficulty=quiz.difficulty,
                created_at=datetime.now(),
                attempts=[],
                best_score=0.0,
                total_attempts=0
            )
            
            user_quizzes[quiz_id] = user_quiz.dict()
            db.collection('users').document(current_user_id).update({
                'user_quizzes': user_quizzes
            })
            logger.info(f"✅ Quiz saved to user's collection")
        else:
            logger.warning(f"⚠️ User document not found: {current_user_id}")
    except Exception as e:
        logger.error(f"❌ Failed to save to user collection: {str(e)}")
        # Don't fail the whole request if user update fails
    
    logger.info(f"🎉 Quiz generation completed successfully: {quiz_id}")
    logger.info(f"📦 Returning complete quiz with {len(quiz.questions)} questions")
    return quiz


@router.get("/{quiz_id}", response_model=Quiz)
async def get_quiz(quiz_id: str):
    """Get a specific quiz"""
    try:
        logger.info(f"📖 Fetching quiz: {quiz_id}")
        db = get_db()
        doc = db.collection('quizzes').document(quiz_id).get()
        
        if not doc.exists:
            logger.error(f"❌ Quiz not found: {quiz_id}")
            raise HTTPException(status_code=404, detail="Quiz not found")
        
        quiz_data = doc.to_dict()
        quiz_data['id'] = doc.id
        
        logger.info(f"✅ Quiz found: {quiz_data.get('title', 'Untitled')}")
        
        # Check questions data
        questions_data = quiz_data.get('questions', [])
        logger.info(f"📊 Raw Firestore quiz has {len(questions_data)} questions")
        logger.debug(f"First question keys: {questions_data[0].keys() if questions_data else 'No questions'}")
        logger.debug(f"Quiz data keys: {quiz_data.keys()}")
        
        # Manually reconstruct quiz to ensure all questions are included
        try:
            quiz = Quiz(**quiz_data)
            logger.info(f"✅ Quiz object created with {len(quiz.questions)} questions")
            
            if len(quiz.questions) != len(questions_data):
                logger.error(f"❌ Question count mismatch! Firestore: {len(questions_data)}, Pydantic: {len(quiz.questions)}")
                # Try to find which questions failed
                for i, q_data in enumerate(questions_data):
                    logger.debug(f"Question {i}: {q_data.get('id', 'no-id')} - {q_data.get('question_text', 'no-text')[:50]}")
        except Exception as pydantic_error:
            logger.error(f"❌ Pydantic validation error: {str(pydantic_error)}")
            logger.debug(f"Problematic quiz_data: {quiz_data}")
            raise
        
        return quiz
        
    except Exception as e:
        logger.error(f"❌ Error fetching quiz {quiz_id}: {str(e)}")
        logger.exception("Full exception trace:")
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
                
                if question.type == "multipleChoice":
                    # Check if selected option is correct
                    for option in question.options:
                        if option.id in user_answer.selected_options and option.is_correct:
                            is_correct = True
                            break
                elif question.type == "trueFalse":
                    is_correct = user_answer.user_answer == question.correct_answer
                elif question.type == "shortAnswer":
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
