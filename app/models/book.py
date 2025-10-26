"""
Book data models
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class BookType(str, Enum):
    textbook = "textbook"
    workbook = "workbook"
    novel = "novel"
    reference = "reference"
    magazine = "magazine"
    research = "research"
    other = "other"


class DifficultyLevel(str, Enum):
    """Difficulty levels matching Flutter UI"""
    beginner = "beginner"
    easy = "easy"
    medium = "medium"
    hard = "hard"
    expert = "expert"


class BookMetadata(BaseModel):
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    published_date: Optional[datetime] = None
    language: str = "en"
    edition: Optional[str] = None
    keywords: List[str] = []
    difficulty: DifficultyLevel = DifficultyLevel.medium
    file_size: Optional[float] = None  # in MB
    format: Optional[str] = None  # PDF, EPUB, etc.


class ReadingProgress(BaseModel):
    book_id: str
    user_id: str
    current_page: int = 0
    total_pages: int
    progress_percentage: float = 0.0
    last_read_at: Optional[datetime] = None
    reading_time_minutes: int = 0


class Book(BaseModel):
    id: Optional[str] = None
    title: str
    author: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    subject: str
    grade: str
    type: BookType
    file_path: Optional[str] = None  # Local file path
    file_url: Optional[str] = None   # Firebase Storage URL
    total_pages: int
    estimated_reading_time: Optional[int] = None  # in minutes
    added_at: datetime = Field(default_factory=datetime.now)
    last_read_at: Optional[datetime] = None
    tags: List[str] = []
    metadata: BookMetadata
    progress: Optional[ReadingProgress] = None
    content_text: Optional[str] = None  # Extracted text content

    class Config:
        use_enum_values = True


class BookUpload(BaseModel):
    title: str
    author: str = "Unknown"
    subject: str = "General"
    grade: str = "General"
    description: Optional[str] = None
    tags: List[str] = []


class BookResponse(BaseModel):
    id: str
    title: str
    author: str
    description: Optional[str]
    cover_url: Optional[str]
    subject: str
    grade: str
    type: str
    file_url: Optional[str]
    total_pages: int
    estimated_reading_time: Optional[int]
    added_at: datetime
    tags: List[str]
    progress_percentage: float = 0.0


class BookCardResponse(BaseModel):
    """Lightweight response for book cards in list/grid views"""
    id: str
    title: str
    author: str
    subject: str
    grade: str
    cover_url: Optional[str] = None
    file_url: Optional[str] = None  # Firebase Storage URL for reading
    total_pages: int
    progress_percentage: float = 0.0
    last_read_at: Optional[datetime] = None
    added_at: datetime
    
    class Config:
        # Keep original field names (snake_case) for JSON serialization
        populate_by_name = True
