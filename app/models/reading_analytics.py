"""
Reading Analytics Models
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PageTimeTracking(BaseModel):
    """Track time spent on each page of a book"""
    id: str = Field(default_factory=lambda: str(datetime.utcnow().timestamp()))
    user_id: str
    book_id: str
    page_number: int
    
    # Time tracking
    time_spent_seconds: int  # Total time on page
    active_time_seconds: int  # Active reading time
    
    # Metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Highlight(BaseModel):
    """User highlights in books"""
    id: str = Field(default_factory=lambda: str(datetime.utcnow().timestamp()))
    user_id: str
    book_id: str
    page_number: int
    
    # Highlight content
    text: str
    color: str = "yellow"  # yellow, green, blue, etc.
    
    # Position information
    position_data: Optional[str] = None  # Store bounding box coordinates as JSON string
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ReadingSession(BaseModel):
    """Track reading sessions for analytics"""
    id: str = Field(default_factory=lambda: str(datetime.utcnow().timestamp()))
    user_id: str
    book_id: str
    
    # Session data
    start_time: datetime
    end_time: Optional[datetime] = None
    total_pages_read: int = 0
    total_time_seconds: int = 0
    active_time_seconds: int = 0
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)