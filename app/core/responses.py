"""
Standardized API response models
"""
from typing import Any, Optional, Dict, List
from pydantic import BaseModel


class SuccessResponse(BaseModel):
    """Standard success response"""
    success: bool = True
    message: str
    data: Optional[Any] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {"id": "123", "name": "Example"}
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    error: str
    details: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "Resource not found",
                "details": {"resource_id": "123"}
            }
        }


class PaginatedResponse(BaseModel):
    """Standard paginated response"""
    success: bool = True
    message: str
    data: List[Any]
    pagination: Dict[str, Any]
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Retrieved items",
                "data": [],
                "pagination": {
                    "page": 1,
                    "page_size": 20,
                    "total": 100,
                    "total_pages": 5
                }
            }
        }


def success_response(message: str, data: Optional[Any] = None) -> Dict[str, Any]:
    """Helper function to create success response"""
    response = {"success": True, "message": message}
    if data is not None:
        response["data"] = data
    return response


def error_response(error: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Helper function to create error response"""
    response = {"success": False, "error": error}
    if details:
        response["details"] = details
    return response


def paginated_response(
    message: str,
    data: List[Any],
    page: int = 1,
    page_size: int = 20,
    total: Optional[int] = None
) -> Dict[str, Any]:
    """Helper function to create paginated response"""
    total_count = total if total is not None else len(data)
    total_pages = (total_count + page_size - 1) // page_size
    
    return {
        "success": True,
        "message": message,
        "data": data,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total_count,
            "total_pages": total_pages
        }
    }

