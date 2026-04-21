"""Alert-related schemas for API validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AlertSchema(BaseModel):
    """Schema for alert data."""

    id: str = Field(..., description="Alert ID")
    name: str = Field(..., description="Alert name")
    severity: str = Field(..., description="Alert severity")
    status: str = Field(default="active", description="Alert status")
    entity_type: Optional[str] = Field(None, description="Affected entity type")
    entity_id: Optional[str] = Field(None, description="Affected entity ID")
    entity_name: Optional[str] = Field(None, description="Affected entity name")
    metric: Optional[str] = Field(None, description="Metric or signal that triggered the alert")
    description: Optional[str] = Field(None, description="Alert description")
    triggered_at: Optional[datetime] = Field(None, description="Alert trigger timestamp")

    class Config:
        from_attributes = True


class AlertRuleSchema(BaseModel):
    """Schema for alert rule data."""

    id: str = Field(..., description="Alert rule ID")
    name: str = Field(..., description="Alert rule name")
    metric: str = Field(..., description="Metric evaluated by this rule")
    threshold: Optional[float] = Field(None, description="Threshold value")
    enabled: bool = Field(default=True, description="Whether the rule is enabled")

    class Config:
        from_attributes = True

