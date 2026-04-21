"""
Agent-related schemas for API validation
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class CreateAgentSchema(BaseModel):
    """Schema for creating a new agent"""
    name: str = Field(..., min_length=1, max_length=255, description="Agent name")
    description: Optional[str] = Field(None, description="Agent description")
    agent_type: str = Field(default="linux", description="Agent type (linux, windows, kubernetes, etc)")
    hostname: Optional[str] = Field(None, description="Agent hostname")
    os_type: Optional[str] = Field(None, description="Operating system type")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Production Agent 01",
                "description": "Linux monitoring agent",
                "agent_type": "linux"
            }
        }


class AgentSchema(BaseModel):
    """Schema for agent data"""
    id: str = Field(..., description="Agent ID")
    name: str = Field(..., description="Agent name")
    agent_type: str = Field(..., description="Agent type")
    status: str = Field(default="offline", description="Agent status (online/offline)")
    hostname: Optional[str] = Field(None, description="Agent hostname")
    os_type: Optional[str] = Field(None, description="Operating system type")
    version: Optional[str] = Field(None, description="Agent version")
    tenant_id: str = Field(..., description="Associated tenant ID")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "agent-123",
                "name": "Production Agent",
                "agent_type": "linux",
                "status": "online",
                "hostname": "prod-server-01",
                "os_type": "Linux",
                "version": "4.1.0",
                "tenant_id": "tenant-123"
            }
        }


class AgentResponseSchema(BaseModel):
    """Schema for agent response"""
    id: str
    name: str
    agent_type: str = "agent"
    status: str
    tenant_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AgentStatusUpdate(BaseModel):
    """Schema for updating agent status"""
    status: str = Field(..., description="New agent status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "online"
            }
        }
