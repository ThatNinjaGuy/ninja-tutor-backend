"""
Note and annotation data models
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


class NoteType(str, Enum):
    """Note types matching Flutter UI exactly"""
    highlight = "highlight"
    text = "text"  # Renamed from annotation to match UI
    drawing = "drawing"
    bookmark = "bookmark"
    question = "question"
    summary = "summary"


class HighlightStyle(BaseModel):
    color: str = "#ffff00"  # Yellow default
    opacity: float = 0.3


class NotePosition(BaseModel):
    page: int
    x: float
    y: float
    width: Optional[float] = None
    height: Optional[float] = None


class AiInsights(BaseModel):
    summary: Optional[str] = None
    key_concepts: List[str] = []
    related_topics: List[str] = []
    difficulty_analysis: Optional[str] = None
    suggested_questions: List[str] = []


class Note(BaseModel):
    id: Optional[str] = None
    book_id: str
    user_id: str
    type: NoteType
    content: str
    title: Optional[str] = None
    position: Optional[NotePosition] = None
    style: Optional[HighlightStyle] = None
    tags: List[str] = []
    ai_insights: Optional[AiInsights] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    is_shared: bool = False
    is_favorite: bool = False  # Added to match Flutter UI

    class Config:
        use_enum_values = True


class NoteCreate(BaseModel):
    book_id: str
    type: NoteType
    content: str
    title: Optional[str] = None
    position: Optional[NotePosition] = None
    style: Optional[HighlightStyle] = None
    tags: List[str] = []


class NoteUpdate(BaseModel):
    content: Optional[str] = None
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    is_shared: Optional[bool] = None
    is_favorite: Optional[bool] = None


class NoteResponse(BaseModel):
    id: str
    book_id: str
    user_id: str
    type: str
    content: str
    title: Optional[str]
    position: Optional[NotePosition]
    tags: List[str]
    ai_insights: Optional[AiInsights]
    created_at: datetime
    updated_at: Optional[datetime]
    is_shared: bool
    is_favorite: bool = False


class NoteCardResponse(BaseModel):
    """Lightweight response for note cards"""
    id: str
    book_id: str
    type: str
    content: str
    title: Optional[str]
    page_number: int
    tags: List[str]
    is_favorite: bool
    created_at: datetime
