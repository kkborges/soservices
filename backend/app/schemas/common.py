"""
Common schemas used across the API
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Schema for pagination query parameters"""
    skip: int = Field(default=0, ge=0, description="Number of items to skip")
    limit: int = Field(default=10, ge=1, le=100, description="Number of items to return")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    order: str = Field(default="asc", description="Sort order (asc/desc)")

    class Config:
        json_schema_extra = {
            "example": {
                "skip": 0,
                "limit": 10,
                "sort_by": "created_at",
                "order": "desc"
            }
        }


class PaginatedResponse(BaseModel):
    """Base schema for paginated responses"""
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Number of items returned")
    total: int = Field(..., description="Total number of items")
    items: list[Any] = Field(default_factory=list, description="Response items")

    class Config:
        json_schema_extra = {
            "example": {
                "skip": 0,
                "limit": 10,
                "total": 50,
                "items": []
            }
        }


class ErrorResponse(BaseModel):
    """Schema for error responses"""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    status_code: int = Field(..., description="HTTP status code")

    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Invalid request parameters",
                "error_code": "INVALID_INPUT",
                "status_code": 400
            }
        }


class SuccessResponse(BaseModel):
    """Schema for success responses"""
    message: str = Field(..., description="Success message")
    data: Optional[Any] = Field(None, description="Response data")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Operation completed successfully",
                "data": {}
            }
        }
