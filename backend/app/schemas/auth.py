"""
Authentication schemas for API validation
"""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class LoginSchema(BaseModel):
    """Schema for user login request"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@soservices.com.br",
                "password": "SecurePassword123!"
            }
        }


class TokenResponse(BaseModel):
    """Schema for token response"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: Optional[str] = Field(None, description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(default=3600, description="Token expiration in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600
            }
        }


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request"""
    refresh_token: str = Field(..., description="Refresh token")

    class Config:
        json_schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }


class UserInfo(BaseModel):
    """Schema for user information"""
    id: str = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email")
    username: Optional[str] = Field(None, description="Username")
    is_active: bool = Field(default=True, description="Whether user is active")
    is_admin: bool = Field(default=False, description="Whether user is admin")
    tenant_id: str = Field(..., description="User's tenant ID")

    class Config:
        from_attributes = True
