"""
Application configuration settings
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # App Configuration
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Firebase Configuration
    FIREBASE_PROJECT_ID: str
    FIREBASE_PRIVATE_KEY_ID: str
    FIREBASE_PRIVATE_KEY: str
    FIREBASE_CLIENT_EMAIL: str
    FIREBASE_CLIENT_ID: str
    FIREBASE_AUTH_URI: str = "https://accounts.google.com/o/oauth2/auth"
    FIREBASE_TOKEN_URI: str = "https://oauth2.googleapis.com/token"
    
    # AI Configuration
    OPENAI_API_KEY: str  # Keep for backward compatibility
    GOOGLE_API_KEY: Optional[str] = None  # Google Gemini API Key
    
    # File Storage
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_FILE_TYPES: list = ["pdf", "epub", "docx"]
    UPLOAD_DIR: str = "uploads"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = 'ignore'  # Ignore extra fields from .env (like old JWT config)


# Global settings instance
settings = Settings()
