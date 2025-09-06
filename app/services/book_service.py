"""
Book management service
"""
import os
import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import UploadFile, HTTPException

from ..core.firebase_config import get_db, get_storage
from ..models.book import Book, BookUpload, BookResponse, BookMetadata, BookType
from .file_processor import FileProcessor
from .firebase_storage import FirebaseStorageService


class BookService:
    """Service for managing books"""
    
    def __init__(self):
        self.db = get_db()
        self.storage_service = FirebaseStorageService()
    
    async def upload_book(self, file: UploadFile, metadata: BookUpload) -> Book:
        """Upload and process a new book"""
        temp_file_path = None
        try:
            # Save uploaded file temporarily
            temp_file_path = await FileProcessor.save_upload_file(file)
            
            # Process file to extract text and metadata
            text_content, page_count = await FileProcessor.process_book_file(temp_file_path)
            reading_time = FileProcessor.estimate_reading_time(text_content)
            
            # For now, use local storage instead of Firebase Storage
            # Keep the file in uploads directory as permanent storage
            file_url = f"/uploads/{os.path.basename(temp_file_path)}"
            
            # Create book metadata
            book_metadata = BookMetadata(
                format=file.filename.split('.')[-1].upper() if file.filename else "UNKNOWN",
                file_size=file.size / (1024 * 1024) if file.size else None  # Convert to MB
            )
            
            # Create book object
            book = Book(
                id=str(uuid.uuid4()),
                title=metadata.title,
                author=metadata.author,
                description=metadata.description,
                subject=metadata.subject,
                grade=metadata.grade,
                type=BookType.other,  # Default type
                file_url=file_url,
                total_pages=page_count,
                estimated_reading_time=reading_time,
                tags=metadata.tags,
                metadata=book_metadata,
                content_text=text_content,
                added_at=datetime.now()
            )
            
            # Save to Firestore
            book_dict = book.dict()
            book_dict['added_at'] = book.added_at
            book_dict['metadata'] = book_metadata.dict()
            
            self.db.collection('books').document(book.id).set(book_dict)
            
            # Don't cleanup the file since we're using it as the permanent storage
            return book
            
        except Exception as e:
            # Cleanup on error
            if temp_file_path:
                try:
                    await FileProcessor.cleanup_file(temp_file_path)
                except Exception:
                    pass  # Ignore cleanup errors
            
            raise HTTPException(status_code=500, detail=f"Error uploading book: {str(e)}")
    
    async def get_books(self, limit: int = 20, offset: int = 0, 
                       subject: Optional[str] = None, grade: Optional[str] = None) -> List[BookResponse]:
        """Get list of books with optional filtering"""
        try:
            query = self.db.collection('books')
            
            # Apply filters
            if subject:
                query = query.where('subject', '==', subject)
            if grade:
                query = query.where('grade', '==', grade)
            
            # Apply pagination
            query = query.limit(limit).offset(offset)
            
            docs = query.stream()
            books = []
            
            for doc in docs:
                book_data = doc.to_dict()
                book_response = BookResponse(
                    id=doc.id,
                    title=book_data.get('title', ''),
                    author=book_data.get('author', ''),
                    description=book_data.get('description'),
                    cover_url=book_data.get('cover_url'),
                    subject=book_data.get('subject', ''),
                    grade=book_data.get('grade', ''),
                    type=book_data.get('type', 'other'),
                    file_url=book_data.get('file_url'),
                    total_pages=book_data.get('total_pages', 0),
                    estimated_reading_time=book_data.get('estimated_reading_time'),
                    added_at=book_data.get('added_at', datetime.now()),
                    tags=book_data.get('tags', [])
                )
                books.append(book_response)
            
            return books
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching books: {str(e)}")
    
    async def get_book(self, book_id: str) -> Optional[Book]:
        """Get a single book by ID"""
        try:
            doc = self.db.collection('books').document(book_id).get()
            
            if not doc.exists:
                return None
            
            book_data = doc.to_dict()
            book_data['id'] = doc.id
            
            return Book(**book_data)
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching book: {str(e)}")
    
    async def search_books(self, query: str, limit: int = 20) -> List[BookResponse]:
        """Search books by title, author, or subject"""
        try:
            # Note: Firestore doesn't support full-text search natively
            # This is a simple implementation that searches in title and author fields
            # For production, consider using Algolia or Elasticsearch
            
            books = []
            
            # Search in title (case-insensitive)
            title_query = self.db.collection('books').where('title', '>=', query).where('title', '<=', query + '\uf8ff').limit(limit)
            title_docs = title_query.stream()
            
            for doc in title_docs:
                book_data = doc.to_dict()
                book_response = BookResponse(
                    id=doc.id,
                    title=book_data.get('title', ''),
                    author=book_data.get('author', ''),
                    description=book_data.get('description'),
                    cover_url=book_data.get('cover_url'),
                    subject=book_data.get('subject', ''),
                    grade=book_data.get('grade', ''),
                    type=book_data.get('type', 'other'),
                    file_url=book_data.get('file_url'),
                    total_pages=book_data.get('total_pages', 0),
                    estimated_reading_time=book_data.get('estimated_reading_time'),
                    added_at=book_data.get('added_at', datetime.now()),
                    tags=book_data.get('tags', [])
                )
                books.append(book_response)
            
            return books
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error searching books: {str(e)}")
    
    async def delete_book(self, book_id: str) -> bool:
        """Delete a book"""
        try:
            # Get book to get file URL for deletion
            book = await self.get_book(book_id)
            if not book:
                return False
            
            # Delete file from storage if exists
            if book.file_url:
                await self.storage_service.delete_file_by_url(book.file_url)
            
            # Delete from Firestore
            self.db.collection('books').document(book_id).delete()
            
            return True
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error deleting book: {str(e)}")
