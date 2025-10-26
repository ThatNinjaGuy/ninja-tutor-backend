"""
Book management endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
import os

from ....models.book import BookUpload, BookResponse, BookCardResponse, Book
from ....services.book_service import BookService
from ....core.config import settings

router = APIRouter()


@router.post("/upload", response_model=BookResponse)
async def upload_book(
    file: UploadFile = File(...),
    title: str = Form(...),
    author: str = Form("Unknown"),
    subject: str = Form("General"),
    grade: str = Form("General"),
    description: Optional[str] = Form(None),
    tags: str = Form("")  # Comma-separated tags
):
    """Upload a new book"""
    try:
        book_service = BookService()
        
        # Parse tags
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []
        
        # Create metadata
        metadata = BookUpload(
            title=title,
            author=author,
            subject=subject,
            grade=grade,
            description=description,
            tags=tag_list
        )
        
        # Upload and process book
        book = await book_service.upload_book(file, metadata)
        
        # Return response
        return BookResponse(
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
            tags=book.tags
        )
        
    except HTTPException:
        raise  # Re-raise HTTPExceptions as-is
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("", response_model=List[BookCardResponse])
async def get_books(
    limit: int = 20,
    offset: int = 0,
    subject: Optional[str] = None,
    grade: Optional[str] = None
):
    """Get list of books with optional filtering - optimized for card display"""
    book_service = BookService()
    books = await book_service.get_books(limit=limit, offset=offset, subject=subject, grade=grade)
    return books


@router.get("/search", response_model=List[BookCardResponse])
async def search_books(q: str, limit: int = 20):
    """Search books by title, author, or subject - optimized for card display"""
    book_service = BookService()
    books = await book_service.search_books(q, limit=limit)
    return books


# IMPORTANT: This must be BEFORE the generic /{book_id} route to avoid conflicts
@router.get("/{book_id}/file")
async def get_book_file(book_id: str):
    """
    Serve the PDF file for a book directly.
    Returns the PDF file with proper headers for viewing.
    """
    book_service = BookService()
    book = await book_service.get_book(book_id)
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if not book.file_url:
        raise HTTPException(status_code=404, detail="Book file not found")
    
    # Construct the full file path
    file_path = None
    if book.file_url.startswith('/uploads/'):
        # Local file path
        file_path = os.path.join(settings.UPLOAD_DIR, book.file_url.split('/uploads/')[-1])
    elif book.file_url.startswith('http'):
        # Remote URL (e.g., Firebase Storage)
        raise HTTPException(status_code=501, detail="Remote file access not supported through this endpoint. Use proxy endpoint instead.")
    else:
        # Assume it's a relative path
        file_path = os.path.join(settings.UPLOAD_DIR, book.file_url)
    
    # Check if file exists
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found at {file_path}")
    
    # Return the PDF file
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{book.title}.pdf"'
        }
    )


@router.get("/{book_id}", response_model=Book)
async def get_book(book_id: str):
    """Get a single book by ID"""
    book_service = BookService()
    book = await book_service.get_book(book_id)
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    return book


@router.delete("/{book_id}")
async def delete_book(book_id: str):
    """Delete a book"""
    book_service = BookService()
    success = await book_service.delete_book(book_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Book not found")
    
    return {"message": "Book deleted successfully"}
