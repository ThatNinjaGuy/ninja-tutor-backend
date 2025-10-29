"""
Book management endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
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
    grade: Optional[str] = None,
    per_category: Optional[int] = None
):
    """
    Get list of books with optional filtering - optimized for card display
    
    Args:
        limit: Total number of books to return (ignored if per_category is set)
        offset: Offset for pagination (ignored if per_category is set)
        subject: Filter by subject/category
        grade: Filter by grade
        per_category: If set, returns this many books per category (balanced distribution)
    """
    book_service = BookService()
    
    # If per_category is specified, fetch balanced books from each category
    if per_category:
        books = await book_service.get_books_by_category(per_category=per_category, grade=grade)
    else:
        books = await book_service.get_books(limit=limit, offset=offset, subject=subject, grade=grade)
    
    return books


@router.get("/search", response_model=List[BookCardResponse])
async def search_books(
    q: str, 
    limit: int = 20,
    search_in: str = "title"  # Options: title, author, subject, description, all
):
    """
    Search books with specific criteria - optimized for card display
    
    Args:
        q: Search query string
        limit: Maximum number of results
        search_in: What field to search in - 'title' (default), 'author', 'subject', 'description', or 'all'
    """
    book_service = BookService()
    books = await book_service.search_books(q, limit=limit, search_in=search_in)
    return books


# IMPORTANT: This must be BEFORE the generic /{book_id} route to avoid conflicts
@router.get("/{book_id}/file")
async def get_book_file(book_id: str, request: Request):
    """
    Serve the PDF/EPUB file for a book with HTTP Range request support.
    For PDFs: Enables streaming and partial content delivery for faster initial load.
    For EPUBs: Returns full file (EPUB.js requires complete file).
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"📚 Fetching file for book ID: {book_id}")
    logger.info(f"🔍 Request method: {request.method}")
    logger.info(f"🔍 Request URL: {request.url}")
    logger.info(f"🔍 Request headers: {dict(request.headers)}")
    
    book_service = BookService()
    book = await book_service.get_book(book_id)
    
    if not book:
        logger.error(f"❌ Book not found: {book_id}")
        raise HTTPException(status_code=404, detail="Book not found")
    
    logger.info(f"📖 Book found: {book.title}")
    logger.info(f"🔗 File URL: {book.file_url}")
    
    if not book.file_url:
        logger.error(f"❌ No file_url for book: {book_id}")
        raise HTTPException(status_code=404, detail="Book file not found")
    
    # Determine file format and MIME type
    file_url_lower = book.file_url.lower()
    if file_url_lower.endswith('.epub'):
        media_type = "application/epub+zip"
        file_extension = "epub"
        is_pdf = False
        logger.info(f"📕 Detected EPUB format")
    elif file_url_lower.endswith('.pdf'):
        media_type = "application/pdf"
        file_extension = "pdf"
        is_pdf = True
        logger.info(f"📄 Detected PDF format")
    else:
        # Default to PDF for backward compatibility
        media_type = "application/pdf"
        file_extension = "pdf"
        is_pdf = True
        logger.warning(f"⚠️ Unknown format, defaulting to PDF")
    
    # Handle different file storage types
    if book.file_url.startswith('http'):
        # Remote URL (e.g., Firebase Storage)
        logger.info(f"🌐 File stored in Firebase Storage: {book.file_url}")
        
        # Security: Validate that the URL is from Firebase Storage only
        allowed_domains = ['firebasestorage.googleapis.com', 'firebasestorage.app', 'storage.googleapis.com']
        from urllib.parse import urlparse
        parsed_url = urlparse(book.file_url)
        
        if not any(domain in parsed_url.netloc for domain in allowed_domains):
            logger.error(f"❌ Security: Invalid storage domain: {parsed_url.netloc}")
            raise HTTPException(
                status_code=400, 
                detail="Invalid file storage URL. Only Firebase Storage URLs are allowed."
            )
        
        # For PDFs: Stream Range requests from Firebase Storage
        # This ensures Range headers are properly forwarded and responses streamed (not buffered)
        if is_pdf:
            logger.info(f"🚀 Streaming PDF with Range request support")
            import httpx
            from fastapi.responses import StreamingResponse
            from copy import copy
            
            # Get Range header from client request if present
            range_header = request.headers.get('Range')
            logger.info(f"📊 Client Range header: {range_header}")
            
            try:
                async def stream_from_firebase():
                    """Generator function to stream chunks from Firebase Storage"""
                    # IMPORTANT: Get current Range header from request (not closure variable)
                    current_range_header = request.headers.get('Range')
                    
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        headers = {}
                        if current_range_header:
                            headers['Range'] = current_range_header
                            logger.info(f"📊 Forwarding Range request to Firebase: {current_range_header}")
                        
                        # Stream the response instead of buffering it
                        async with client.stream('GET', book.file_url, headers=headers) as response:
                            response.raise_for_status()
                            
                            logger.info(f"✅ Firebase response: {response.status_code}")
                            logger.info(f"📊 Firebase headers: {dict(response.headers)}")
                            
                            # Forward Range-related headers for subsequent requests
                            if 'Content-Range' in response.headers:
                                logger.info(f"✅ Content-Range: {response.headers['Content-Range']}")
                            
                            # Stream chunks as they arrive
                            chunk_count = 0
                            total_bytes = 0
                            async for chunk in response.aiter_bytes():
                                chunk_count += 1
                                total_bytes += len(chunk)
                                if chunk_count % 100 == 0:  # Log every 100 chunks
                                    logger.info(f"📦 Streamed {chunk_count} chunks, {total_bytes} bytes so far")
                                yield chunk
                            
                            logger.info(f"✅ Streaming complete: {chunk_count} chunks, {total_bytes} total bytes")
                
                # Check if Range header was provided
                async with httpx.AsyncClient(timeout=60.0) as test_client:
                    status_code = 200
                    if range_header:
                        test_headers = {'Range': range_header}
                        logger.info(f"🔍 Testing Firebase range support with Range: {range_header}")
                        test_response = await test_client.head(book.file_url, headers=test_headers)
                        status_code = test_response.status_code
                        logger.info(f"✅ Firebase range response: {status_code}")
                    else:
                        logger.info(f"📝 No range header, will return 200 OK")
                
                # Create response headers
                response_headers = {
                    "Content-Disposition": f'inline; filename="{book.title}.{file_extension}"',
                    "Cache-Control": "public, max-age=3600",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Expose-Headers": "Content-Range, Accept-Ranges, Content-Length",
                    "Accept-Ranges": "bytes",  # CRITICAL: PDF.js needs this to enable Range requests
                }
                
                logger.info(f"✅ Response headers: Accept-Ranges=bytes")
                
                logger.info(f"🚀 Starting streaming response with status {status_code}")
                
                return StreamingResponse(
                    stream_from_firebase(),
                    status_code=status_code,
                    media_type=media_type,
                    headers=response_headers
                )
                    
            except httpx.HTTPError as e:
                logger.error(f"❌ Failed to stream PDF from Firebase: {str(e)}")
                raise HTTPException(status_code=503, detail=f"Failed to fetch PDF from Firebase Storage: {str(e)}")
        else:
            # For EPUB: Fetch and stream full file (EPUB.js needs complete file)
            logger.info(f"📦 Fetching full EPUB from Firebase Storage")
            import httpx
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.get(book.file_url)
                    response.raise_for_status()
                    
                    logger.info(f"✅ Firebase fetch successful, size: {len(response.content)} bytes")
                    
                    from fastapi.responses import StreamingResponse
                    from io import BytesIO
                    
                    return StreamingResponse(
                        BytesIO(response.content),
                        media_type=media_type,
                        headers={
                            "Content-Disposition": f'inline; filename="{book.title}.{file_extension}"',
                            "Content-Length": str(len(response.content)),
                            "Cache-Control": "public, max-age=3600",
                        }
                    )
            except httpx.HTTPError as e:
                logger.error(f"❌ Failed to fetch from Firebase: {str(e)}")
                raise HTTPException(status_code=503, detail=f"Failed to fetch file from Firebase Storage: {str(e)}")
    else:
        # Local file path
        logger.info(f"📁 Serving from local storage: {book.file_url}")
        
        # Security: Sanitize file path to prevent path traversal attacks
        # Remove any path traversal attempts (../, ..\, etc.)
        clean_file_url = book.file_url.replace('..', '').replace('\\', '/').strip('/')
        
        if book.file_url.startswith('/uploads/'):
            file_path = os.path.join(settings.UPLOAD_DIR, clean_file_url.split('/uploads/')[-1])
        else:
            # Assume it's a relative path
            file_path = os.path.join(settings.UPLOAD_DIR, clean_file_url)
        
        # Security: Ensure the resolved path is within UPLOAD_DIR
        upload_dir_abs = os.path.abspath(settings.UPLOAD_DIR)
        file_path_abs = os.path.abspath(file_path)
        
        if not file_path_abs.startswith(upload_dir_abs):
            logger.error(f"❌ Security: Path traversal attempt detected: {book.file_url}")
            raise HTTPException(
                status_code=400, 
                detail="Invalid file path. Path traversal attempts are not allowed."
            )
        
        logger.info(f"📂 Resolved file path: {file_path_abs}")
        
        # Check if file exists
        if not os.path.exists(file_path_abs):
            logger.error(f"❌ File not found at: {file_path_abs}")
            raise HTTPException(status_code=404, detail="Book file not found")
        
        logger.info(f"✅ File exists, serving {file_extension.upper()}")
        
        # FileResponse natively supports Range requests
        # FastAPI automatically handles Accept-Ranges and partial content (206)
        # Security Note: Path validated above to prevent traversal attacks
        # CORS "*" is intentional - books are public content (see FIREBASE_STORAGE_SECURITY.md)
        return FileResponse(
            path=file_path_abs,
            media_type=media_type,
            headers={
                "Content-Disposition": f'inline; filename="{book.title}.{file_extension}"',
                "Cache-Control": "public, max-age=3600",
                "Access-Control-Allow-Origin": "*",  # Intentional: Public content
                "Access-Control-Expose-Headers": "Content-Range, Accept-Ranges",
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
