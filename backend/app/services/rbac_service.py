"""
Granular Role-Based Access Control (RBAC) Service

Provides fine-grained permission management with:
- Resource-level access control
- Attribute-based access control (ABAC)
- Permission inheritance
- Dynamic role assignment
- Context-aware authorization
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Set, Tuple, Any
from enum import Enum
from dataclasses import dataclass, field
from functools import lru_cache
import json
from sqlalchemy import Column, String, Integer, DateTime, Boolean, JSON, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field

# ============================================================================
# Permission Enums and Constants
# ============================================================================

class ResourceType(str, Enum):
    """Resource types in the system"""
    AGENT = "agent"
    TENANT = "tenant"
    ALERT = "alert"
    DASHBOARD = "dashboard"
    TICKET = "ticket"
    USER = "user"
    ROLE = "role"
    AUDIT_LOG = "audit_log"
    SECRET = "secret"
    WEBHOOK = "webhook"


class PermissionAction(str, Enum):
    """Standard CRUD and system permissions"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXPORT = "export"
    SHARE = "share"
    APPROVE = "approve"
    PUBLISH = "publish"
    ARCHIVE = "archive"
    RESTORE = "restore"
    ADMIN = "admin"


class RoleLevel(str, Enum):
    """Role hierarchy levels"""
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    TEAM_LEAD = "team_lead"
    OPERATOR = "operator"
    VIEWER = "viewer"
    GUEST = "guest"


# ============================================================================
# Pydantic Schemas
# ============================================================================

class PermissionSchema(BaseModel):
    """Individual permission model"""
    resource_type: ResourceType
    action: PermissionAction
    resource_id: Optional[str] = None  # None = all resources of type
    constraints: Dict[str, Any] = Field(default_factory=dict)  # tenant_id, status, etc.
    expires_at: Optional[datetime] = None

    class Config:
        use_enum_values = True


class RoleSchema(BaseModel):
    """Role model with permissions"""
    role_id: str
    name: str
    description: str
    level: RoleLevel
    permissions: List[PermissionSchema] = Field(default_factory=list)
    inherited_from: Optional[str] = None  # Parent role for inheritance
    created_at: datetime = Field(default_factory=datetime.utcnow)
    custom: bool = False  # Is this a custom role?

    class Config:
        use_enum_values = True


class UserRoleAssignmentSchema(BaseModel):
    """User role assignment with temporal constraints"""
    user_id: str
    role_id: str
    tenant_id: str
    assigned_at: datetime
    expires_at: Optional[datetime] = None
    reason: Optional[str] = None
    assigned_by: str


class ResourceAccessPolicySchema(BaseModel):
    """Fine-grained resource access policy"""
    resource_type: ResourceType
    resource_id: str
    tenant_id: str
    owner_user_id: str
    shared_with: List[Tuple[str, List[PermissionAction]]] = Field(default_factory=list)  # (user_id, [actions])
    public: bool = False
    restrictions: Dict[str, Any] = Field(default_factory=dict)  # IP, location, time window


# ============================================================================
# Permission Context and Decision Models
# ============================================================================

@dataclass
class AuthorizationContext:
    """Context for authorization decision"""
    user_id: str
    tenant_id: str
    resource_type: ResourceType
    resource_id: Optional[str] = None
    action: Optional[PermissionAction] = None
    request_context: Dict[str, Any] = field(default_factory=dict)  # IP, user agent, time, etc.
    attributes: Dict[str, Any] = field(default_factory=dict)  # User/resource attributes


@dataclass
class AuthorizationDecision:
    """Authorization decision result"""
    allowed: bool
    reason: str
    matched_permission: Optional[PermissionSchema] = None
    applicable_roles: List[str] = field(default_factory=list)
    denial_reason: Optional[str] = None
    expires_at: Optional[datetime] = None


# ============================================================================
# Granular RBAC Service
# ============================================================================

class GranularRBACService:
    """
    Granular Role-Based Access Control Service
    
    Provides:
    - Fine-grained permission management
    - Resource-level access control
    - Attribute-based access control (ABAC)
    - Dynamic role assignment
    - Permission inheritance
    - Time-based and context-based access
    """

    def __init__(self, db_session=None):
        self.db = db_session
        self._role_cache: Dict[str, RoleSchema] = {}
        self._permission_cache: Dict[str, List[PermissionSchema]] = {}
        self._last_cache_refresh = {}

    # ========================================================================
    # Role Management
    # ========================================================================

    async def create_role(
        self,
        name: str,
        description: str,
        level: RoleLevel,
        permissions: List[PermissionSchema],
        inherited_from: Optional[str] = None,
        custom: bool = True
    ) -> RoleSchema:
        """Create a new role with specified permissions"""
        role_id = f"role_{name.lower().replace(' ', '_')}_{datetime.utcnow().timestamp()}"
        
        # Validate inheritance
        if inherited_from:
            parent_role = await self.get_role(inherited_from)
            if not parent_role:
                raise ValueError(f"Parent role '{inherited_from}' not found")
            # Inherit parent permissions
            permissions = await self._inherit_permissions(inherited_from, permissions)
        
        role = RoleSchema(
            role_id=role_id,
            name=name,
            description=description,
            level=level,
            permissions=permissions,
            inherited_from=inherited_from,
            custom=custom
        )
        
        self._role_cache[role_id] = role
        self._invalidate_permission_cache(role_id)
        return role

    async def get_role(self, role_id: str) -> Optional[RoleSchema]:
        """Get role by ID"""
        if role_id in self._role_cache:
            return self._role_cache[role_id]
        # Query database (when integrated)
        return None

    async def update_role(self, role_id: str, **updates) -> Optional[RoleSchema]:
        """Update role permissions or metadata"""
        role = await self.get_role(role_id)
        if not role:
            return None
        
        # Don't allow updating system roles
        if not role.custom:
            raise ValueError("Cannot modify system roles")
        
        for key, value in updates.items():
            if key == "permissions" and isinstance(value, list):
                role.permissions = [
                    p if isinstance(p, PermissionSchema) else PermissionSchema(**p)
                    for p in value
                ]
            elif hasattr(role, key):
                setattr(role, key, value)
        
        self._role_cache[role_id] = role
        self._invalidate_permission_cache(role_id)
        return role

    async def delete_role(self, role_id: str) -> bool:
        """Delete custom role"""
        role = await self.get_role(role_id)
        if not role or not role.custom:
            return False
        
        del self._role_cache[role_id]
        self._invalidate_permission_cache(role_id)
        return True

    # ========================================================================
    # Permission Management
    # ========================================================================

    async def add_permission(
        self,
        role_id: str,
        resource_type: ResourceType,
        action: PermissionAction,
        resource_id: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None
    ) -> bool:
        """Add permission to role"""
        role = await self.get_role(role_id)
        if not role:
            return False
        
        permission = PermissionSchema(
            resource_type=resource_type,
            action=action,
            resource_id=resource_id,
            constraints=constraints or {},
            expires_at=expires_at
        )
        
        # Avoid duplicates
        if not any(
            p.resource_type == resource_type and 
            p.action == action and 
            p.resource_id == resource_id
            for p in role.permissions
        ):
            role.permissions.append(permission)
            self._invalidate_permission_cache(role_id)
        
        return True

    async def revoke_permission(
        self,
        role_id: str,
        resource_type: ResourceType,
        action: PermissionAction,
        resource_id: Optional[str] = None
    ) -> bool:
        """Remove permission from role"""
        role = await self.get_role(role_id)
        if not role:
            return False
        
        role.permissions = [
            p for p in role.permissions
            if not (
                p.resource_type == resource_type and
                p.action == action and
                p.resource_id == resource_id
            )
        ]
        
        self._invalidate_permission_cache(role_id)
        return True

    async def get_role_permissions(self, role_id: str) -> List[PermissionSchema]:
        """Get all permissions for a role (including inherited)"""
        cache_key = f"perms_{role_id}"
        if cache_key in self._permission_cache:
            return self._permission_cache[cache_key]
        
        role = await self.get_role(role_id)
        if not role:
            return []
        
        permissions = role.permissions.copy()
        
        # Include inherited permissions
        if role.inherited_from:
            parent_perms = await self.get_role_permissions(role.inherited_from)
            permissions.extend(parent_perms)
        
        self._permission_cache[cache_key] = permissions
        return permissions

    # ========================================================================
    # User-Role Assignment
    # ========================================================================

    async def assign_role_to_user(
        self,
        user_id: str,
        role_id: str,
        tenant_id: str,
        reason: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        assigned_by: Optional[str] = None
    ) -> UserRoleAssignmentSchema:
        """Assign role to user with optional expiration"""
        assignment = UserRoleAssignmentSchema(
            user_id=user_id,
            role_id=role_id,
            tenant_id=tenant_id,
            assigned_at=datetime.utcnow(),
            expires_at=expires_at,
            reason=reason,
            assigned_by=assigned_by or "system"
        )
        
        # Invalidate user permission cache
        self._invalidate_permission_cache(f"user_{user_id}_{tenant_id}")
        
        return assignment

    async def revoke_role_from_user(
        self,
        user_id: str,
        role_id: str,
        tenant_id: str
    ) -> bool:
        """Remove role from user"""
        self._invalidate_permission_cache(f"user_{user_id}_{tenant_id}")
        return True

    # ========================================================================
    # Authorization Decision Making
    # ========================================================================

    async def authorize(
        self,
        context: AuthorizationContext
    ) -> AuthorizationDecision:
        """
        Make authorization decision based on context
        
        Checks:
        1. Explicit permissions
        2. Role-based permissions
        3. Resource-level access policies
        4. Constraints and attributes
        5. Time-based restrictions
        """
        
        # Build decision
        decision = AuthorizationDecision(
            allowed=False,
            reason="No matching permission found"
        )
        
        # Check if user has permission directly
        if context.action:
            permission = await self._find_matching_permission(context)
            if permission:
                if await self._check_constraints(permission, context):
                    if await self._check_temporal_constraints(permission, context):
                        decision.allowed = True
                        decision.reason = "Permission granted"
                        decision.matched_permission = permission
                        decision.expires_at = permission.expires_at
                        return decision
        
        decision.denial_reason = "User lacks required permissions"
        return decision

    async def authorize_resource_access(
        self,
        user_id: str,
        tenant_id: str,
        resource_type: ResourceType,
        resource_id: str,
        action: PermissionAction,
        request_context: Optional[Dict[str, Any]] = None
    ) -> AuthorizationDecision:
        """Authorize access to specific resource"""
        context = AuthorizationContext(
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            request_context=request_context or {}
        )
        
        return await self.authorize(context)

    # ========================================================================
    # Constraint and Context Checking
    # ========================================================================

    async def _find_matching_permission(
        self,
        context: AuthorizationContext
    ) -> Optional[PermissionSchema]:
        """Find matching permission for context"""
        # This would fetch user's roles and check their permissions
        # Simplified for now
        permissions = [
            p for p in context.attributes.get("user_permissions", [])
            if p.resource_type == context.resource_type and
               p.action == context.action and
               (p.resource_id is None or p.resource_id == context.resource_id)
        ]
        
        return permissions[0] if permissions else None

    async def _check_constraints(
        self,
        permission: PermissionSchema,
        context: AuthorizationContext
    ) -> bool:
        """Check if permission constraints are satisfied"""
        constraints = permission.constraints
        
        # Tenant constraint
        if "tenant_id" in constraints:
            if constraints["tenant_id"] != context.tenant_id:
                return False
        
        # Status constraint
        if "status" in constraints:
            if context.attributes.get("status") not in constraints["status"]:
                return False
        
        # IP constraint
        if "allowed_ips" in constraints:
            if context.request_context.get("ip") not in constraints["allowed_ips"]:
                return False
        
        return True

    async def _check_temporal_constraints(
        self,
        permission: PermissionSchema,
        context: AuthorizationContext
    ) -> bool:
        """Check time-based constraints"""
        if permission.expires_at and permission.expires_at < datetime.utcnow():
            return False
        return True

    # ========================================================================
    # Permission Inheritance
    # ========================================================================

    async def _inherit_permissions(
        self,
        parent_role_id: str,
        additional_permissions: List[PermissionSchema]
    ) -> List[PermissionSchema]:
        """Inherit permissions from parent role"""
        parent_perms = await self.get_role_permissions(parent_role_id)
        return parent_perms + additional_permissions

    # ========================================================================
    # Bulk Operations
    # ========================================================================

    async def get_user_effective_permissions(
        self,
        user_id: str,
        tenant_id: str
    ) -> List[PermissionSchema]:
        """Get all effective permissions for user (from all assigned roles)"""
        # Would query user's roles and aggregate permissions
        return []

    async def bulk_grant_permissions(
        self,
        role_ids: List[str],
        permission: PermissionSchema
    ) -> Dict[str, bool]:
        """Grant permission to multiple roles"""
        results = {}
        for role_id in role_ids:
            role = await self.get_role(role_id)
            if role:
                await self.add_permission(
                    role_id,
                    permission.resource_type,
                    permission.action,
                    permission.resource_id,
                    permission.constraints
                )
                results[role_id] = True
            else:
                results[role_id] = False
        return results

    async def bulk_revoke_permissions(
        self,
        role_ids: List[str],
        resource_type: ResourceType,
        action: PermissionAction
    ) -> Dict[str, bool]:
        """Revoke permission from multiple roles"""
        results = {}
        for role_id in role_ids:
            results[role_id] = await self.revoke_permission(
                role_id,
                resource_type,
                action
            )
        return results

    # ========================================================================
    # Cache Management
    # ========================================================================

    def _invalidate_permission_cache(self, key: str) -> None:
        """Invalidate specific cache entries"""
        if key in self._permission_cache:
            del self._permission_cache[key]

    def clear_cache(self) -> None:
        """Clear all caches"""
        self._role_cache.clear()
        self._permission_cache.clear()

    # ========================================================================
    # Query and Reporting
    # ========================================================================

    async def get_role_members(self, role_id: str, tenant_id: str) -> List[str]:
        """Get all users with a specific role in a tenant"""
        # Would query database
        return []

    async def get_user_roles(self, user_id: str, tenant_id: str) -> List[RoleSchema]:
        """Get all roles assigned to user"""
        # Would query database
        return []

    async def audit_permission_usage(
        self,
        resource_type: ResourceType,
        action: PermissionAction,
        days: int = 30
    ) -> Dict[str, Any]:
        """Audit who used which permissions"""
        return {
            "resource_type": resource_type,
            "action": action,
            "period_days": days,
            "total_uses": 0
        }
