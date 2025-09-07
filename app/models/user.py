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


class UserPreferences(BaseModel):
    font_size: float = 16.0
    line_height: float = 1.5
    theme: str = "light"
    auto_scroll: bool = False
    night_mode: bool = False


class ReadingPreferences(BaseModel):
    preferred_subjects: List[str] = []
    reading_goals: Dict[str, int] = {}  # {"daily_minutes": 30, "weekly_books": 2}
    difficulty_level: str = "medium"


class UserProgress(BaseModel):
    total_books_read: int = 0
    total_reading_time: int = 0  # in minutes
    streak_days: int = 0
    last_activity: Optional[datetime] = None
    subjects_progress: Dict[str, float] = {}  # subject -> progress percentage


class User(BaseModel):
    id: Optional[str] = None
    email: str
    name: str
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


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
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
