"""
User data models
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


class ReadingStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PAUSED = "paused"


class UserBookProgress(BaseModel):
    current_page: int = 0
    total_pages: int = 0
    progress_percentage: float = 0.0
    reading_status: ReadingStatus = ReadingStatus.NOT_STARTED
    last_read_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    reading_time_minutes: int = 0
    notes: str = ""
    pages_read_count: int = 0  # Number of pages with 60+ seconds reading time


class UserPreferences(BaseModel):
    """User app preferences matching Flutter UI"""
    language: str = "en"
    is_dark_mode: bool = False
    font_size: float = 16.0
    ai_tips_enabled: bool = True
    notifications_enabled: bool = True
    sound_enabled: bool = True
    class_grade: Optional[str] = None


class ReadingPreferences(BaseModel):
    """Reading-specific preferences matching Flutter UI"""
    line_height: float = 1.5
    font_family: str = "Inter"
    auto_scroll: bool = False
    auto_scroll_speed: int = 200  # words per minute
    highlight_difficult_words: bool = True
    show_definitions_on_tap: bool = True


class UserProgress(BaseModel):
    """User progress tracking matching Flutter UI"""
    total_books_read: int = 0
    total_time_spent: int = 0  # in minutes (renamed from total_reading_time)
    current_streak: int = 0  # consecutive days (renamed from streak_days)
    longest_streak: int = 0
    total_quizzes_taken: int = 0
    average_quiz_score: float = 0.0
    achieved_badges: List[str] = []
    last_activity: Optional[datetime] = None
    subjects_progress: Dict[str, float] = {}  # subject -> progress percentage


class User(BaseModel):
    id: Optional[str] = None
    email: str
    name: str
    avatar_url: Optional[str] = None
    password_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    reading_preferences: ReadingPreferences = Field(default_factory=ReadingPreferences)
    progress: UserProgress = Field(default_factory=UserProgress)
    is_active: bool = True


class UserCreate(BaseModel):
    email: str
    name: str
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    preferences: Optional[UserPreferences] = None
    reading_preferences: Optional[ReadingPreferences] = None
    avatar_url: Optional[str] = None


class PreferencesUpdate(BaseModel):
    """Update only user preferences"""
    language: Optional[str] = None
    is_dark_mode: Optional[bool] = None
    font_size: Optional[float] = None
    ai_tips_enabled: Optional[bool] = None
    notifications_enabled: Optional[bool] = None
    sound_enabled: Optional[bool] = None
    class_grade: Optional[str] = None


class ReadingPreferencesUpdate(BaseModel):
    """Update only reading preferences"""
    line_height: Optional[float] = None
    font_family: Optional[str] = None
    auto_scroll: Optional[bool] = None
    auto_scroll_speed: Optional[int] = None
    highlight_difficult_words: Optional[bool] = None
    show_definitions_on_tap: Optional[bool] = None


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: Optional[str] = None
    created_at: datetime
    preferences: UserPreferences
    reading_preferences: ReadingPreferences
    progress: UserProgress
    is_active: bool


class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
