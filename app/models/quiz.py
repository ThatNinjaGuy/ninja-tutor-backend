"""
Quiz and question data models
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class QuestionType(str, Enum):
    multiple_choice = "multipleChoice"
    multiple_select = "multipleSelect"
    true_false = "trueFalse"
    short_answer = "shortAnswer"
    essay = "essay"
    fill_blank = "fillInTheBlank"
    matching = "matching"
    ordering = "ordering"
    audio = "audio"
    video = "video"


class QuizType(str, Enum):
    practice = "practice"
    assessment = "assessment"
    review = "review"
    adaptive = "adaptive"
    timed = "timed"
    final_ = "final_"


class DifficultyLevel(str, Enum):
    beginner = "beginner"
    easy = "easy"
    medium = "medium"
    hard = "hard"
    expert = "expert"


class AnswerOption(BaseModel):
    id: str
    text: str
    is_correct: bool


class Question(BaseModel):
    id: Optional[str] = None
    type: QuestionType
    question_text: str
    options: List[AnswerOption] = []  # For multiple choice
    correct_answer: Optional[str] = None  # For short answer, true/false
    explanation: Optional[str] = None
    difficulty: DifficultyLevel = DifficultyLevel.medium
    points: int = 1
    page_reference: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        use_enum_values = True


class QuizSettings(BaseModel):
    time_limit: Optional[int] = None  # in minutes
    shuffle_questions: bool = True
    shuffle_options: bool = True
    show_results_immediately: bool = True
    allow_retakes: bool = True


class Quiz(BaseModel):
    id: Optional[str] = None
    title: str
    description: Optional[str] = None
    book_id: str
    subject: str
    page_range: List[int] = []  # [start_page, end_page]
    questions: List[Question] = []
    settings: QuizSettings = Field(default_factory=QuizSettings)
    created_at: datetime = Field(default_factory=datetime.now)
    type: QuizType = QuizType.practice
    difficulty: DifficultyLevel = DifficultyLevel.medium
    created_by: Optional[str] = None  # user_id or "ai"

    class Config:
        use_enum_values = True


class QuestionResult(BaseModel):
    question_id: str
    user_answer: Optional[str] = None
    selected_options: List[str] = []  # For multiple choice
    is_correct: bool
    points_earned: int
    time_spent: Optional[int] = None  # in seconds


class QuizResult(BaseModel):
    id: Optional[str] = None
    quiz_id: str
    user_id: str
    question_results: List[QuestionResult] = []
    total_score: float
    max_score: int
    percentage: float
    time_taken: int  # in minutes
    completed_at: datetime = Field(default_factory=datetime.now)
    attempts: int = 1


class QuizGenRequest(BaseModel):
    book_id: str
    page_range: List[int]
    question_count: int = 10
    difficulty: DifficultyLevel = DifficultyLevel.medium
    question_types: List[QuestionType] = [QuestionType.multiple_choice]


class QuizResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    book_id: str
    subject: str
    question_count: int
    difficulty: str
    type: str
    created_at: datetime


class QuizAttempt(BaseModel):
    """Single quiz attempt by a user"""
    attempt_number: int
    score: float
    percentage: float
    completed_at: datetime
    time_taken: int  # in minutes
    answers: Dict[str, Any]  # question_id -> user answer
    is_passed: bool = False


class UserQuizData(BaseModel):
    """Quiz data stored in user document"""
    quiz_id: str
    book_id: str
    title: str
    subject: str
    difficulty: str
    created_at: datetime
    attempts: List[QuizAttempt] = []
    best_score: float = 0.0
    total_attempts: int = 0


class UserQuizResponse(BaseModel):
    """Lightweight response for user quiz cards"""
    quiz_id: str
    book_id: str
    book_title: str
    title: str
    subject: str
    difficulty: str
    question_count: int
    total_attempts: int
    best_score: float
    last_attempt_date: Optional[datetime]
    created_at: datetime


class QuizResultResponse(BaseModel):
    """Response for quiz results"""
    id: str
    quiz_id: str
    user_id: str
    total_score: float
    max_score: int
    percentage: float
    correct_answers: int
    incorrect_answers: int
    time_taken: int
    is_passed: bool
    completed_at: datetime
    attempt_number: int
