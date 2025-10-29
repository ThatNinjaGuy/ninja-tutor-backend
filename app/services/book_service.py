"""
Book management service
"""
import os
import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import UploadFile, HTTPException

from ..core.firebase_config import get_db, get_storage, initialize_firebase
from ..models.book import Book, BookUpload, BookResponse, BookCardResponse, BookMetadata, BookType
from .file_processor import FileProcessor
from .firebase_storage import FirebaseStorageService


class BookService:
    """Service for managing books"""
    
    def __init__(self):
        # Ensure Firebase is initialized
        initialize_firebase()
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
            
            # Upload file to Firebase Storage
            file_url = await self.storage_service.upload_book_file(temp_file_path, file.filename or "book.pdf")
            
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
            
            # Clean up temporary file after successful upload to Firebase Storage
            if temp_file_path:
                try:
                    await FileProcessor.cleanup_file(temp_file_path)
                except Exception:
                    pass  # Ignore cleanup errors
            
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
                       subject: Optional[str] = None, grade: Optional[str] = None) -> List[BookCardResponse]:
        """Get list of books with optional filtering - optimized for card display"""
        try:
            query = self.db.collection('books')
            
            # Apply filters
            if subject:
                query = query.where('subject', '==', subject)
            if grade:
                query = query.where('grade', '==', grade)
            
            # Note: We don't use order_by here when filters are applied because Firestore requires
            # composite indexes for order_by + where clauses. Instead, we'll fetch and sort in Python.
            # For no-filter queries, we can order by added_at without index issues.
            if not subject and not grade:
                # Only use order_by when there are no filters (no index needed)
                query = query.order_by('added_at', direction='DESCENDING')
            
            # Apply pagination
            query = query.limit(limit).offset(offset)
            
            docs = query.stream()
            books = []
            
            for doc in docs:
                book_data = doc.to_dict()
                # Return only essential fields for card display
                
                # Handle Firestore timestamp conversion
                added_at = book_data.get('added_at')
                if added_at and not isinstance(added_at, datetime):
                    # Firestore timestamp conversion
                    try:
                        from google.cloud.firestore import Timestamp
                        if isinstance(added_at, Timestamp):
                            added_at = added_at.to_datetime()
                        elif hasattr(added_at, 'timestamp'):
                            added_at = datetime.fromtimestamp(added_at.timestamp())
                    except (ImportError, AttributeError):
                        # If conversion fails, use current time
                        added_at = datetime.now()
                elif not added_at:
                    added_at = datetime.now()
                
                book_card = BookCardResponse(
                    id=doc.id,
                    title=book_data.get('title', ''),
                    author=book_data.get('author', ''),
                    subject=book_data.get('subject', ''),
                    grade=book_data.get('grade', ''),
                    cover_url=book_data.get('cover_url'),
                    file_url=book_data.get('file_url'),  # Include file_url for reading
                    total_pages=book_data.get('total_pages', 0),
                    progress_percentage=0.0,  # No progress for global book list
                    last_read_at=book_data.get('last_read_at'),
                    added_at=added_at
                )
                books.append(book_card)
            
            # Sort by added_at descending when filters are applied (since we can't use order_by)
            if subject or grade:
                books.sort(key=lambda b: b.added_at if b.added_at else datetime.min, reverse=True)
            
            return books
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching books: {str(e)}")
    
    async def get_books_by_category(self, per_category: int = 10, grade: Optional[str] = None) -> List[BookCardResponse]:
        """
        Get balanced books from each category - fetches in single query, groups server-side
        Returns per_category books from each category for balanced display
        """
        try:
            # Fetch a larger batch of books (estimate: 12 categories * 10 books = 120 minimum)
            # Fetch more to ensure we have enough from each category (200-300 should cover it)
            query = self.db.collection('books')
            
            if grade:
                query = query.where('grade', '==', grade)
            
            # Order by added_at descending (no subject filter = no index needed)
            query = query.order_by('added_at', direction='DESCENDING').limit(300)
            
            docs = query.stream()
            all_books = []
            
            # Process all documents
            for doc in docs:
                book_data = doc.to_dict()
                
                # Handle Firestore timestamp conversion
                added_at = book_data.get('added_at')
                if added_at and not isinstance(added_at, datetime):
                    try:
                        from google.cloud.firestore import Timestamp
                        if isinstance(added_at, Timestamp):
                            added_at = added_at.to_datetime()
                        elif hasattr(added_at, 'timestamp'):
                            added_at = datetime.fromtimestamp(added_at.timestamp())
                    except (ImportError, AttributeError):
                        added_at = datetime.now()
                elif not added_at:
                    added_at = datetime.now()
                
                book_card = BookCardResponse(
                    id=doc.id,
                    title=book_data.get('title', ''),
                    author=book_data.get('author', ''),
                    subject=book_data.get('subject', '') or 'General',  # Default to 'General' if empty
                    grade=book_data.get('grade', ''),
                    cover_url=book_data.get('cover_url'),
                    file_url=book_data.get('file_url'),
                    total_pages=book_data.get('total_pages', 0),
                    progress_percentage=0.0,
                    last_read_at=book_data.get('last_read_at'),
                    added_at=added_at
                )
                all_books.append(book_card)
            
            # Group books by category
            books_by_category = {}
            for book in all_books:
                category = book.subject if book.subject else 'General'
                if category not in books_by_category:
                    books_by_category[category] = []
                books_by_category[category].append(book)
            
            # Take top N books from each category (already sorted by added_at descending)
            result_books = []
            for category, books in books_by_category.items():
                # Take top per_category books from this category
                category_books = books[:per_category]
                result_books.extend(category_books)
            
            # Sort final result by added_at to maintain chronological order
            result_books.sort(key=lambda b: b.added_at if b.added_at else datetime.min, reverse=True)
            
            return result_books
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching books by category: {str(e)}")
    
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
    
    async def search_books(self, query: str, limit: int = 20, search_in: str = "title") -> List[BookCardResponse]:
        """
        Search books using contains matching with specific criteria
        
        Args:
            query: Search query string
            limit: Maximum number of results
            search_in: What field to search in - 'title', 'author', 'subject', 'description', or 'all'
        """
        try:
            # Note: Firestore doesn't support full-text search natively
            # We fetch books and filter in Python for contains matching
            # For production, consider using Algolia or Elasticsearch
            
            query_lower = query.lower().strip()
            if not query_lower:
                return []
            
            # Normalize search_in parameter
            search_in = search_in.lower() if search_in else "title"
            
            # Fetch all books (or a reasonable limit for searching)
            # In production with many books, you'd want to use a search service
            all_docs = self.db.collection('books').stream()
            
            books = []
            seen_ids = set()  # Track book IDs to avoid duplicates
            
            for doc in all_docs:
                if len(books) >= limit:
                    break
                    
                book_data = doc.to_dict()
                book_id = doc.id
                
                # Skip if already added
                if book_id in seen_ids:
                    continue
                
                # Get field values (lowercase for comparison)
                title_lower = book_data.get('title', '').lower()
                author_lower = book_data.get('author', '').lower()
                subject_lower = book_data.get('subject', '').lower()
                description_lower = (book_data.get('description') or '').lower()
                
                # Check if query matches based on search criteria
                matches = False
                if search_in == "title":
                    matches = query_lower in title_lower
                elif search_in == "author":
                    matches = query_lower in author_lower
                elif search_in == "subject":
                    matches = query_lower in subject_lower
                elif search_in == "description":
                    matches = query_lower in description_lower
                elif search_in == "all":
                    # Search in all fields
                    matches = (query_lower in title_lower or 
                              query_lower in author_lower or 
                              query_lower in subject_lower or
                              query_lower in description_lower)
                else:
                    # Default to title if unknown search_in value
                    matches = query_lower in title_lower
                
                if matches:
                    seen_ids.add(book_id)
                    
                    # Handle Firestore timestamp conversion
                    added_at = book_data.get('added_at')
                    if added_at and not isinstance(added_at, datetime):
                        try:
                            from google.cloud.firestore import Timestamp
                            if isinstance(added_at, Timestamp):
                                added_at = added_at.to_datetime()
                            elif hasattr(added_at, 'timestamp'):
                                added_at = datetime.fromtimestamp(added_at.timestamp())
                        except (ImportError, AttributeError):
                            added_at = datetime.now()
                    elif not added_at:
                        added_at = datetime.now()
                    
                    book_card = BookCardResponse(
                        id=book_id,
                        title=book_data.get('title', ''),
                        author=book_data.get('author', ''),
                        subject=book_data.get('subject', ''),
                        grade=book_data.get('grade', ''),
                        cover_url=book_data.get('cover_url'),
                        file_url=book_data.get('file_url'),
                        total_pages=book_data.get('total_pages', 0),
                        progress_percentage=0.0,
                        last_read_at=book_data.get('last_read_at'),
                        added_at=added_at
                    )
                    books.append(book_card)
            
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
