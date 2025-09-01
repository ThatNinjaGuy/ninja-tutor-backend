"""
File processing service for books
"""
import os
import uuid
import aiofiles
from typing import Tuple, Optional
from fastapi import UploadFile, HTTPException
import PyPDF2
from docx import Document
import tempfile

from ..core.config import settings


class FileProcessor:
    """Service for processing uploaded book files"""
    
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
            
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                page_count = len(pdf_reader.pages)
                
                for page_num in range(page_count):
                    page = pdf_reader.pages[page_num]
                    text_content += page.extract_text() + "\n"
            
            return text_content.strip(), page_count
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")
    
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
