"""
Application configuration settings
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # App Configuration
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    HOST: str = "0.0.0.0"
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Firebase Configuration (optional for initial deployment)
    FIREBASE_PROJECT_ID: Optional[str] = None
    FIREBASE_PRIVATE_KEY_ID: Optional[str] = None
    FIREBASE_PRIVATE_KEY: Optional[str] = None
    FIREBASE_CLIENT_EMAIL: Optional[str] = None
    FIREBASE_CLIENT_ID: Optional[str] = None
    FIREBASE_AUTH_URI: str = "https://accounts.google.com/o/oauth2/auth"
    FIREBASE_TOKEN_URI: str = "https://oauth2.googleapis.com/token"
    
    # AI Configuration (optional for initial deployment)
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None  # Google Gemini API Key
    
    # File Storage
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_FILE_TYPES: list = ["pdf", "epub", "docx"]
    UPLOAD_DIR: str = "uploads"
    
    # Cloud Storage Configuration (for production)
    USE_CLOUD_STORAGE: bool = os.getenv("USE_CLOUD_STORAGE", "false").lower() == "true"
    CLOUD_STORAGE_BUCKET: Optional[str] = os.getenv("CLOUD_STORAGE_BUCKET")
    
    # Firebase Hosting URL for CORS
    FIREBASE_HOSTING_URL: Optional[str] = os.getenv("FIREBASE_HOSTING_URL")
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = 'ignore'  # Ignore extra fields from .env (like old JWT config)
    
    @property
    def is_production(self) -> bool:
        """Check if running in production (Cloud Run)"""
        return os.getenv("K_SERVICE") is not None or not self.DEBUG


# Global settings instance
settings = Settings()
