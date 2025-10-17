"""
User Library Management endpoints
Handles adding/removing books to user's personal library and tracking reading progress
"""
from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import uuid
from datetime import datetime

from ....models.book import BookResponse, BookCardResponse
from ....models.user import UserBookProgress, ReadingStatus
from ....services.book_service import BookService
from ....core.firebase_config import get_db
from .auth import get_current_user

router = APIRouter()


class AddBookRequest(BaseModel):
    book_id: str


class UpdateProgressRequest(BaseModel):
    book_id: str
    current_page: int
    total_pages: Optional[int] = None
    reading_status: Optional[ReadingStatus] = None
    notes: Optional[str] = None
    page_times: Optional[Dict[str, int]] = None  # Dict of page_number: seconds_spent


class UserBookResponse(BaseModel):
    book_id: str
    book: BookResponse
    progress: UserBookProgress
    added_at: datetime


class UserBookCardResponse(BaseModel):
    """Lightweight response for user library book cards"""
    book_id: str
    title: str
    author: str
    subject: str
    grade: str
    cover_url: Optional[str]
    total_pages: int
    current_page: int
    progress_percentage: float
    reading_status: str
    last_read_at: Optional[datetime]
    added_at: datetime


@router.post("/add-book")
async def add_book_to_library(
    request: AddBookRequest,
    current_user_id: str = Depends(get_current_user)
):
    """Add a book to user's personal library"""
    try:
        # Check if book exists
        book_service = BookService()
        book = await book_service.get_book(request.book_id)
        
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
        
        db = get_db()
        
        # Check if book is already in user's library
        user_doc = db.collection('users').document(current_user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_doc.to_dict()
        user_books = user_data.get('library_books', {})
        
        if request.book_id in user_books:
            raise HTTPException(status_code=400, detail="Book already in your library")
        
        # Create initial progress entry
        progress = UserBookProgress(
            current_page=0,
            total_pages=book.total_pages,
            progress_percentage=0.0,
            reading_status=ReadingStatus.NOT_STARTED,
            last_read_at=None,
            started_at=None,
            completed_at=None,
            reading_time_minutes=0,
            notes=""
        )
        
        # Add book to user's library
        user_books[request.book_id] = {
            "added_at": datetime.now(),
            "progress": progress.dict()
        }
        
        # Update user document
        db.collection('users').document(current_user_id).update({
            'library_books': user_books
        })
        
        return {
            "message": "Book added to your library successfully",
            "book_id": request.book_id,
            "book_title": book.title
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding book to library: {str(e)}")


@router.delete("/remove-book/{book_id}")
async def remove_book_from_library(
    book_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Remove a book from user's personal library"""
    try:
        db = get_db()
        
        # Get user document
        user_doc = db.collection('users').document(current_user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_doc.to_dict()
        user_books = user_data.get('library_books', {})
        
        if book_id not in user_books:
            raise HTTPException(status_code=404, detail="Book not found in your library")
        
        # Remove book from user's library
        del user_books[book_id]
        
        # Update user document
        db.collection('users').document(current_user_id).update({
            'library_books': user_books
        })
        
        return {"message": "Book removed from your library successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing book from library: {str(e)}")


@router.get("/my-books", response_model=List[UserBookResponse])
async def get_user_library(
    current_user_id: str = Depends(get_current_user),
    status: Optional[ReadingStatus] = None
):
    """Get user's personal library with reading progress"""
    try:
        db = get_db()
        
        # Get user document
        user_doc = db.collection('users').document(current_user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_doc.to_dict()
        user_books = user_data.get('library_books', {})
        
        if not user_books:
            return []
        
        # Get book details for each book in user's library
        book_service = BookService()
        user_library = []
        
        for book_id, book_data in user_books.items():
            # Get book details
            book = await book_service.get_book(book_id)
            if not book:
                continue  # Skip if book no longer exists
            
            # Parse progress data
            progress_data = book_data.get('progress', {})
            
            # Calculate pages_read_count and reading_time_minutes from page_times
            page_times = progress_data.get('page_times', {})
            pages_read_count = sum(1 for time in page_times.values() if time >= 60)
            total_seconds = sum(page_times.values())
            reading_time_minutes = int(total_seconds / 60)
            
            # Debug logging
            if page_times:
                print(f"📊 Book {book_id[:8]}... - Pages with 60+ sec: {pages_read_count}/{len(page_times)}, Total time: {reading_time_minutes} min")
            
            progress = UserBookProgress(
                current_page=progress_data.get('current_page', 0),
                total_pages=progress_data.get('total_pages', book.total_pages),
                progress_percentage=progress_data.get('progress_percentage', 0.0),
                reading_status=ReadingStatus(progress_data.get('reading_status', 'not_started')),
                last_read_at=progress_data.get('last_read_at'),
                started_at=progress_data.get('started_at'),
                completed_at=progress_data.get('completed_at'),
                reading_time_minutes=reading_time_minutes,
                notes=progress_data.get('notes', ""),
                pages_read_count=pages_read_count
            )
            
            # Filter by status if provided
            if status and progress.reading_status != status:
                continue
            
            # Create optimized BookResponse with only essential fields + progress_percentage
            book_response = BookResponse(
                id=book.id,
                title=book.title,
                author=book.author,
                description=book.description,
                cover_url=book.cover_url,
                subject=book.subject,
                grade=book.grade,
                type=book.type.value if hasattr(book.type, 'value') else str(book.type),
                file_url=book.file_url,
                total_pages=book.total_pages,
                estimated_reading_time=book.estimated_reading_time,
                added_at=book.added_at,
                tags=book.tags,
                progress_percentage=progress.progress_percentage
            )
            
            user_library.append(UserBookResponse(
                book_id=book_id,
                book=book_response,
                progress=progress,
                added_at=book_data.get('added_at', datetime.now())
            ))
        
        # Sort by added_at (most recent first)
        user_library.sort(key=lambda x: x.added_at, reverse=True)
        
        return user_library
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user library: {str(e)}")


@router.put("/update-progress")
async def update_reading_progress(
    request: UpdateProgressRequest,
    current_user_id: str = Depends(get_current_user)
):
    """Update reading progress for a book in user's library"""
    try:
        db = get_db()
        
        # Get user document
        user_doc = db.collection('users').document(current_user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_doc.to_dict()
        user_books = user_data.get('library_books', {})
        
        if request.book_id not in user_books:
            raise HTTPException(status_code=404, detail="Book not found in your library")
        
        # Get current progress
        book_data = user_books[request.book_id]
        progress_data = book_data.get('progress', {})
        
        # Initialize page_times if it doesn't exist
        if 'page_times' not in progress_data:
            progress_data['page_times'] = {}
        
        # Update progress fields
        if request.current_page is not None:
            progress_data['current_page'] = request.current_page
            
            # Update page times if provided (merge with existing times)
            if request.page_times is not None:
                for page_num, time_seconds in request.page_times.items():
                    current_time = progress_data['page_times'].get(page_num, 0)
                    progress_data['page_times'][page_num] = current_time + time_seconds
            
            # Calculate total pages with significant time (1+ minute = 60 seconds)
            total_pages = request.total_pages or progress_data.get('total_pages', 1)
            progress_data['total_pages'] = total_pages
            
            pages_read = sum(1 for time in progress_data['page_times'].values() if time >= 60)
            progress_data['pages_read_count'] = pages_read
            
            # Calculate total reading time in minutes
            total_seconds = sum(progress_data['page_times'].values())
            progress_data['reading_time_minutes'] = int(total_seconds / 60)
            
            # Progress percentage is calculated based on pages with 1+ minute
            progress_data['progress_percentage'] = min(pages_read / total_pages, 1.0) if total_pages > 0 else 0.0
            
            # Auto-update reading status based on progress
            if pages_read == 0:
                progress_data['reading_status'] = ReadingStatus.NOT_STARTED.value
            elif pages_read >= total_pages:
                progress_data['reading_status'] = ReadingStatus.COMPLETED.value
                if not progress_data.get('completed_at'):
                    progress_data['completed_at'] = datetime.now()
            else:
                if progress_data.get('reading_status') == ReadingStatus.NOT_STARTED.value:
                    progress_data['reading_status'] = ReadingStatus.IN_PROGRESS.value
                    progress_data['started_at'] = datetime.now()
        
        # Update other fields if provided
        if request.reading_status:
            progress_data['reading_status'] = request.reading_status.value if hasattr(request.reading_status, 'value') else str(request.reading_status)
            
            if request.reading_status == ReadingStatus.IN_PROGRESS and not progress_data.get('started_at'):
                progress_data['started_at'] = datetime.now()
            elif request.reading_status == ReadingStatus.COMPLETED:
                progress_data['completed_at'] = datetime.now()
        
        if request.notes is not None:
            progress_data['notes'] = request.notes
        
        # Always update last_read_at when progress is updated
        progress_data['last_read_at'] = datetime.now()
        
        # Update user document
        user_books[request.book_id]['progress'] = progress_data
        db.collection('users').document(current_user_id).update({
            'library_books': user_books
        })
        
        return {
            "message": "Reading progress updated successfully",
            "current_page": progress_data['current_page'],
            "progress_percentage": progress_data['progress_percentage'],
            "reading_status": progress_data['reading_status']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating reading progress: {str(e)}")


@router.get("/check-book/{book_id}")
async def check_book_in_library(
    book_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Check if a book is in user's library"""
    try:
        db = get_db()
        
        # Get user document
        user_doc = db.collection('users').document(current_user_id).get()
        if not user_doc.exists:
            return {"in_library": False}
        
        user_data = user_doc.to_dict()
        user_books = user_data.get('library_books', {})
        
        is_in_library = book_id in user_books
        progress_data = None
        
        if is_in_library:
            progress_data = user_books[book_id].get('progress', {})
        
        return {
            "in_library": is_in_library,
            "progress": progress_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking book status: {str(e)}")
