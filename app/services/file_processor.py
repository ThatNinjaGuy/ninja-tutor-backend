"""
File processing service for books
"""
import os
import uuid
import aiofiles
import httpx
import logging
from typing import Tuple, Optional
from fastapi import UploadFile, HTTPException
try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader
from docx import Document
import tempfile

from ..core.config import settings

logger = logging.getLogger(__name__)


class FileProcessor:
    """Service for processing uploaded book files"""
    
    @staticmethod
    async def download_file_from_url(url: str) -> str:
        """Download a file from URL to temporary location"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Create temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                temp_file.write(response.content)
                temp_file.close()
                
                return temp_file.name
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")
    
    @staticmethod
    def _is_url(path: str) -> bool:
        """Check if path is a URL"""
        return path.startswith('http://') or path.startswith('https://')
    
    @staticmethod
    def _resolve_file_path(file_path: str) -> str:
        """Resolve file path to absolute path with comprehensive logging"""
        logger.info(f"📁 Resolving file path: '{file_path}'")
        logger.info(f"   Current working directory: {os.getcwd()}")
        
        # If it's a URL, return as-is
        if FileProcessor._is_url(file_path):
            logger.info(f"   ✅ Detected as URL, returning as-is")
            return file_path
        
        # Special handling for /uploads/ paths (these are relative to project root, not absolute)
        if file_path.startswith('/uploads/'):
            file_path = file_path[1:]  # Remove leading slash → "uploads/..."
            logger.info(f"   Detected /uploads/ path, stripped to: '{file_path}'")
        
        if file_path.startswith('uploads/'):
            # Get the current working directory and join with uploads
            base_dir = os.getcwd()
            absolute_path = os.path.join(base_dir, file_path)
            logger.info(f"   Resolved uploads/ path to: '{absolute_path}'")
            logger.info(f"   File exists: {os.path.exists(absolute_path)}")
            
            # List what's actually in the uploads directory for debugging
            uploads_dir = os.path.join(base_dir, 'uploads')
            if os.path.exists(uploads_dir):
                try:
                    files = os.listdir(uploads_dir)
                    logger.info(f"   📂 Files in uploads/: {len(files)} files")
                    if files:
                        logger.info(f"   Sample files: {files[:3]}")
                except Exception as e:
                    logger.warning(f"   ⚠️ Could not list uploads directory: {e}")
            else:
                logger.error(f"   ❌ Uploads directory does not exist: {uploads_dir}")
            
            return absolute_path
        
        # If it's already a real absolute path (not /uploads/), check if it exists
        if os.path.isabs(file_path):
            logger.info(f"   ✅ Already absolute path")
            logger.info(f"   File exists: {os.path.exists(file_path)}")
            return file_path
        
        # Otherwise, treat as relative to current directory
        absolute_path = os.path.abspath(file_path)
        logger.info(f"   Resolved relative path to: '{absolute_path}'")
        logger.info(f"   File exists: {os.path.exists(absolute_path)}")
        return absolute_path
    
    @staticmethod
    async def save_upload_file(upload_file: UploadFile) -> str:
        """Save uploaded file and return file path"""
        # Validate file type
        if not FileProcessor.is_valid_file_type(upload_file.filename):
            raise HTTPException(status_code=400, detail="Invalid file type")
        
        # Check file size
        content = await upload_file.read()
        if len(content) > settings.MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large")
        
        # Generate unique filename
        file_extension = os.path.splitext(upload_file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        return file_path
    
    @staticmethod
    def is_valid_file_type(filename: str) -> bool:
        """Check if file type is supported"""
        if not filename:
            return False
        
        extension = os.path.splitext(filename)[1].lower().lstrip('.')
        return extension in settings.ALLOWED_FILE_TYPES
    
    @staticmethod
    async def extract_text_from_pdf(file_path: str) -> Tuple[str, int]:
        """Extract text from PDF file"""
        try:
            text_content = ""
            page_count = 0
            
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            with open(file_path, 'rb') as file:
                pdf_reader = PdfReader(file)
                page_count = len(pdf_reader.pages)
                
                for page_num in range(page_count):
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    text_content += page_text + "\n"
            
            return text_content.strip(), page_count
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")
    
    @staticmethod
    async def extract_text_from_pdf_page(file_path: str, page_number: int) -> str:
        """Extract text from a single PDF page (1-indexed)"""
        temp_file = None
        try:
            # Resolve file path (handles URLs, relative paths, absolute paths)
            resolved_path = FileProcessor._resolve_file_path(file_path)
            
            # Handle URLs by downloading first
            if FileProcessor._is_url(resolved_path):
                temp_file = await FileProcessor.download_file_from_url(resolved_path)
                resolved_path = temp_file
            
            if not os.path.exists(resolved_path):
                raise FileNotFoundError(f"File not found: {resolved_path} (original: {file_path})")
            
            with open(resolved_path, 'rb') as file:
                pdf_reader = PdfReader(file)
                page_count = len(pdf_reader.pages)
                
                # Validate page number
                if page_number < 1 or page_number > page_count:
                    raise ValueError(f"Page number {page_number} out of range (1-{page_count})")
                
                # Extract text from the specified page (convert to 0-indexed)
                page = pdf_reader.pages[page_number - 1]
                page_text = page.extract_text()
                
                return page_text.strip()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error extracting page {page_number}: {str(e)}")
        finally:
            # Clean up temporary file if created
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
    
    @staticmethod
    async def extract_text_from_pdf_pages(file_path: str, start_page: int, end_page: int) -> str:
        """Extract text from specific page range (inclusive, 1-indexed)"""
        temp_file = None
        try:
            logger.info(f"🔍 extract_text_from_pdf_pages called with: '{file_path}', pages {start_page}-{end_page}")
            
            # Resolve file path (handles URLs, relative paths, absolute paths)
            resolved_path = FileProcessor._resolve_file_path(file_path)
            logger.info(f"✅ Path resolved to: '{resolved_path}'")
            
            # Handle URLs by downloading first
            if FileProcessor._is_url(resolved_path):
                logger.info(f"🌐 Downloading PDF from URL...")
                temp_file = await FileProcessor.download_file_from_url(resolved_path)
                resolved_path = temp_file
                logger.info(f"✅ Downloaded to temp file: '{resolved_path}'")
            
            if not os.path.exists(resolved_path):
                logger.error(f"❌ File does not exist at resolved path: '{resolved_path}'")
                raise FileNotFoundError(f"File not found: {resolved_path} (original: {file_path})")
            
            logger.info(f"✅ File exists, opening PDF...")
            
            with open(resolved_path, 'rb') as file:
                pdf_reader = PdfReader(file)
                page_count = len(pdf_reader.pages)
                logger.info(f"📄 PDF has {page_count} pages")
                
                # Validate page range
                if start_page < 1 or end_page > page_count or start_page > end_page:
                    raise ValueError(
                        f"Invalid page range {start_page}-{end_page} for document with {page_count} pages"
                    )
                
                # Extract text from the specified range (convert to 0-indexed)
                logger.info(f"📖 Extracting text from pages {start_page}-{end_page}...")
                text_content = ""
                for page_num in range(start_page - 1, end_page):
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    text_content += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
                    logger.info(f"   Page {page_num + 1}: {len(page_text)} chars extracted")
                
                logger.info(f"✅ Successfully extracted {len(text_content)} total characters")
                return text_content.strip()
        except Exception as e:
            logger.error(f"❌ Error in extract_text_from_pdf_pages: {str(e)}")
            logger.exception("Full traceback:")
            raise HTTPException(status_code=500, detail=f"Error extracting pages {start_page}-{end_page}: {str(e)}")
        finally:
            # Clean up temporary file if created
            if temp_file and os.path.exists(temp_file):
                try:
                    logger.info(f"🧹 Cleaning up temp file: {temp_file}")
                    os.remove(temp_file)
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ Failed to clean up temp file: {cleanup_error}")
    
    @staticmethod
    async def extract_text_from_docx(file_path: str) -> Tuple[str, int]:
        """Extract text from DOCX file"""
        try:
            doc = Document(file_path)
            text_content = ""
            
            for paragraph in doc.paragraphs:
                text_content += paragraph.text + "\n"
            
            # Estimate page count based on word count (approximately 250 words per page)
            word_count = len(text_content.split())
            estimated_pages = max(1, word_count // 250)
            
            return text_content.strip(), estimated_pages
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing DOCX: {str(e)}")
    
    @staticmethod
    async def extract_text_from_epub(file_path: str) -> Tuple[str, int]:
        """Extract text from EPUB file (placeholder)"""
        # For now, return basic info
        # You can implement proper EPUB parsing with libraries like ebooklib
        return "EPUB content extraction not implemented yet", 1
    
    @staticmethod
    async def process_book_file(file_path: str) -> Tuple[str, int]:
        """Process book file and extract text content"""
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if file_extension == '.pdf':
            return await FileProcessor.extract_text_from_pdf(file_path)
        elif file_extension == '.docx':
            return await FileProcessor.extract_text_from_docx(file_path)
        elif file_extension == '.epub':
            return await FileProcessor.extract_text_from_epub(file_path)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")
    
    @staticmethod
    def estimate_reading_time(text: str) -> int:
        """Estimate reading time in minutes (average 200 words per minute)"""
        word_count = len(text.split())
        return max(1, word_count // 200)
    
    @staticmethod
    async def cleanup_file(file_path: str):
        """Delete uploaded file after processing"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error cleaning up file {file_path}: {e}")
