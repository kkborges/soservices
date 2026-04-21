"""
API Schema definitions for request/response validation
"""

from .auth import LoginSchema, TokenResponse
from .agent import AgentSchema, CreateAgentSchema, AgentResponseSchema
from .alert import AlertRuleSchema, AlertSchema
from .common import PaginationParams, ErrorResponse
from .tenant import CreateTenantSchema, TenantSchema

__all__ = [
    "LoginSchema",
    "TokenResponse",
    "AgentSchema",
    "CreateAgentSchema",
    "AgentResponseSchema",
    "AlertRuleSchema",
    "AlertSchema",
    "PaginationParams",
    "ErrorResponse",
    "CreateTenantSchema",
    "TenantSchema",
]
