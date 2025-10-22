"""
Bookmark data models
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Bookmark(BaseModel):
    id: Optional[str] = None
    book_id: str
    user_id: str
    page_number: int
    created_at: datetime = Field(default_factory=datetime.now)
    note: Optional[str] = None  # Optional note for the bookmark


class BookmarkCreate(BaseModel):
    book_id: str
    page_number: int
    note: Optional[str] = None


class BookmarkResponse(BaseModel):
    id: str
    book_id: str
    user_id: str
    page_number: int
    created_at: datetime
    note: Optional[str] = None

