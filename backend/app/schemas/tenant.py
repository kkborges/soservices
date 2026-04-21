"""
Tenant-related schemas for API validation
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator
import re


class CreateTenantSchema(BaseModel):
    """Schema for creating a new tenant"""
    name: str = Field(..., min_length=1, max_length=255, description="Tenant name")
    slug: str = Field(..., min_length=1, max_length=50, description="Tenant slug (URL-friendly identifier)")
    description: Optional[str] = Field(None, description="Tenant description")
    
    @field_validator("slug")
    @classmethod
    def validate_slug(cls, slug: str) -> str:
        """Validate slug format: lowercase, alphanumeric, hyphens only"""
        if not re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', slug):
            raise ValueError(
                "Slug must be lowercase, start/end with alphanumeric, "
                "and contain only alphanumeric and hyphens"
            )
        return slug

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Acme Corporation",
                "slug": "acme-corp",
                "description": "Production tenant for Acme Corp"
            }
        }


class TenantSchema(BaseModel):
    """Schema for tenant data"""
    id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Tenant name")
    slug: str = Field(..., description="Tenant slug")
    is_active: bool = Field(default=True, description="Whether tenant is active")
    plan: Optional[str] = Field(None, description="Tenant plan (free, pro, enterprise)")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "tenant-123",
                "name": "Acme Corporation",
                "slug": "acme-corp",
                "is_active": True,
                "plan": "enterprise"
            }
        }


class TenantUpdateSchema(BaseModel):
    """Schema for updating tenant"""
    name: Optional[str] = Field(None, description="Tenant name")
    description: Optional[str] = Field(None, description="Tenant description")
    is_active: Optional[bool] = Field(None, description="Whether tenant is active")


class TenantResponseSchema(BaseModel):
    """Schema for tenant response"""
    id: str
    name: str
    slug: str
    is_active: bool

    class Config:
        from_attributes = True
