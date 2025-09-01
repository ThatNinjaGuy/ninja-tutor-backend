"""
Firebase Storage service
"""
import os
import uuid
from typing import Optional
from fastapi import HTTPException

from ..core.firebase_config import get_storage


class FirebaseStorageService:
    """Service for managing Firebase Storage operations"""
    
    def __init__(self):
        self.bucket = get_storage()
    
    async def upload_book_file(self, file_path: str, original_filename: str) -> str:
        """Upload book file to Firebase Storage"""
        try:
            # Generate unique storage path
            file_extension = os.path.splitext(original_filename)[1]
            storage_path = f"books/{uuid.uuid4()}{file_extension}"
            
            # Upload file
            blob = self.bucket.blob(storage_path)
            blob.upload_from_filename(file_path)
            
            # Make file publicly accessible
            blob.make_public()
            
            return blob.public_url
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error uploading to storage: {str(e)}")
    
    async def upload_cover_image(self, file_path: str, book_id: str) -> str:
        """Upload book cover image"""
        try:
            file_extension = os.path.splitext(file_path)[1]
            storage_path = f"covers/{book_id}{file_extension}"
            
            blob = self.bucket.blob(storage_path)
            blob.upload_from_filename(file_path)
            blob.make_public()
            
            return blob.public_url
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error uploading cover: {str(e)}")
    
    async def delete_file_by_url(self, file_url: str) -> bool:
        """Delete file from storage using its public URL"""
        try:
            # Extract blob path from URL
            # Firebase Storage URLs have format: https://storage.googleapis.com/{bucket}/o/{path}?...
            if "storage.googleapis.com" in file_url:
                # Extract the path part
                url_parts = file_url.split("/o/")
                if len(url_parts) > 1:
                    blob_path = url_parts[1].split("?")[0]
                    blob_path = blob_path.replace("%2F", "/")  # Decode URL encoding
                    
                    blob = self.bucket.blob(blob_path)
                    blob.delete()
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error deleting file from storage: {e}")
            return False
    
    async def get_signed_url(self, blob_path: str, expiration_minutes: int = 60) -> str:
        """Get signed URL for private file access"""
        try:
            from datetime import timedelta
            
            blob = self.bucket.blob(blob_path)
            url = blob.generate_signed_url(expiration=timedelta(minutes=expiration_minutes))
            
            return url
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating signed URL: {str(e)}")
