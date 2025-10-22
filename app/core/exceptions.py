"""
Custom exception classes for better error handling
"""
from typing import Optional, Dict, Any


class NinjaTutorException(Exception):
    """Base exception for all custom exceptions"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class FirestoreException(NinjaTutorException):
    """Raised when Firestore operations fail"""
    pass


class StorageException(NinjaTutorException):
    """Raised when file storage operations fail"""
    pass


class AIServiceException(NinjaTutorException):
    """Raised when AI service operations fail"""
    pass


class ValidationException(NinjaTutorException):
    """Raised when input validation fails"""
    pass


class AuthenticationException(NinjaTutorException):
    """Raised when authentication fails"""
    pass


class AuthorizationException(NinjaTutorException):
    """Raised when user is not authorized"""
    pass


class ResourceNotFoundException(NinjaTutorException):
    """Raised when a requested resource is not found"""
    pass


class FileProcessingException(NinjaTutorException):
    """Raised when file processing fails"""
    pass


class QuizGenerationException(NinjaTutorException):
    """Raised when quiz generation fails"""
    pass

