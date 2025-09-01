"""
Book management endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse

from ....models.book import BookUpload, BookResponse, Book
from ....services.book_service import BookService

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
        type=book.type.value,
        file_url=book.file_url,
        total_pages=book.total_pages,
        estimated_reading_time=book.estimated_reading_time,
        added_at=book.added_at,
        tags=book.tags
    )


@router.get("", response_model=List[BookResponse])
async def get_books(
    limit: int = 20,
    offset: int = 0,
    subject: Optional[str] = None,
    grade: Optional[str] = None
):
    """Get list of books with optional filtering"""
    book_service = BookService()
    books = await book_service.get_books(limit=limit, offset=offset, subject=subject, grade=grade)
    return books


@router.get("/{book_id}", response_model=Book)
async def get_book(book_id: str):
    """Get a single book by ID"""
    book_service = BookService()
    book = await book_service.get_book(book_id)
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    return book


@router.get("/search", response_model=List[BookResponse])
async def search_books(q: str, limit: int = 20):
    """Search books by title, author, or subject"""
    book_service = BookService()
    books = await book_service.search_books(q, limit=limit)
    return books


@router.delete("/{book_id}")
async def delete_book(book_id: str):
    """Delete a book"""
    book_service = BookService()
    success = await book_service.delete_book(book_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Book not found")
    
    return {"message": "Book deleted successfully"}
