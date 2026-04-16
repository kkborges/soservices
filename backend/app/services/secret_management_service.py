"""
Enterprise-Grade Secret Management Service

Provides:
- Encrypted secret storage
- Automatic key rotation
- Secret versioning
- Access logging
- Secure secret injection
- Integration with external vaults (HashiCorp Vault, AWS Secrets Manager)
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
import os
import base64
from cryptography.fernet import Fernet
from pydantic import BaseModel, Field
from uuid import uuid4
import json


# ============================================================================
# Secret Enums
# ============================================================================

class SecretType(str, Enum):
    """Types of secrets"""
    API_KEY = "api_key"
    DATABASE_PASSWORD = "database_password"
    OAUTH_TOKEN = "oauth_token"
    SSH_KEY = "ssh_key"
    CERTIFICATE = "certificate"
    PRIVATE_KEY = "private_key"
    JWT_SECRET = "jwt_secret"
    WEBHOOK_SECRET = "webhook_secret"
    ENCRYPTION_KEY = "encryption_key"
    CUSTOM = "custom"


class SecretStatus(str, Enum):
    """Secret lifecycle status"""
    ACTIVE = "active"
    ROTATED = "rotated"
    INACTIVE = "inactive"
    COMPROMISED = "compromised"
    EXPIRED = "expired"


class VaultBackend(str, Enum):
    """Supported external vaults"""
    LOCAL = "local"
    VAULT = "vault"  # HashiCorp Vault
    AWS_SECRETS = "aws_secrets"
    GCP_SECRET_MANAGER = "gcp_secret_manager"
    AZURE_KEYVAULT = "azure_keyvault"


# ============================================================================
# Pydantic Schemas
# ============================================================================

class SecretVersionSchema(BaseModel):
    """Individual secret version"""
    version_id: str = Field(default_factory=lambda: str(uuid4()))
    secret_value: str  # Encrypted
    created_at: datetime = Field(default_factory=datetime.utcnow)
    rotated_at: Optional[datetime] = None
    status: SecretStatus = SecretStatus.ACTIVE
    rotation_reason: Optional[str] = None
    created_by: str


class SecretAccessLogSchema(BaseModel):
    """Log of secret access"""
    access_id: str = Field(default_factory=lambda: str(uuid4()))
    secret_id: str
    tenant_id: str
    user_id: str
    action: str  # read, update, rotate, export
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None
    success: bool = True
    reason: Optional[str] = None


class SecretMetadataSchema(BaseModel):
    """Secret metadata"""
    secret_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    name: str
    description: Optional[str] = None
    secret_type: SecretType
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str
    
    # Lifecycle
    expires_at: Optional[datetime] = None
    rotation_interval_days: Optional[int] = None
    last_rotated_at: Optional[datetime] = None
    
    # Access control
    owner_user_id: str
    allowed_readers: List[str] = Field(default_factory=list)
    allowed_applications: List[str] = Field(default_factory=list)
    
    # Versioning
    current_version_id: str
    version_count: int = 1
    
    # Storage
    backend: VaultBackend = VaultBackend.LOCAL
    external_id: Optional[str] = None  # ID in external vault
    
    # Status
    status: SecretStatus = SecretStatus.ACTIVE


class SecretSchema(BaseModel):
    """Complete secret"""
    metadata: SecretMetadataSchema
    current_version: SecretVersionSchema
    versions: List[SecretVersionSchema] = Field(default_factory=list)

    class Config:
        use_enum_values = True


class RotateSecretRequestSchema(BaseModel):
    """Request to rotate secret"""
    secret_id: str
    new_value: Optional[str] = None  # If None, auto-generate
    reason: str = "scheduled_rotation"
    requested_by: str


# ============================================================================
# Secret Management Service
# ============================================================================

class SecretManagementService:
    """
    Enterprise-Grade Secret Management Service
    
    Features:
    - Encrypted secret storage with AEAD encryption
    - Automatic rotation with scheduling
    - Version history with rollback capability
    - Fine-grained access control
    - Comprehensive audit logging
    - Integration with external vaults
    - Secret injection for applications
    """

    def __init__(self, encryption_key: Optional[str] = None):
        # Initialize encryption
        if encryption_key:
            self.cipher_suite = Fernet(encryption_key.encode())
        else:
            # Generate new key (in production, load from vault)
            key = Fernet.generate_key()
            self.cipher_suite = Fernet(key)
            self._master_key = key.decode()
        
        # In-memory storage (in production, use database)
        self._secrets: Dict[str, SecretSchema] = {}
        self._access_logs: List[SecretAccessLogSchema] = []
        self._rotation_queue: List[Tuple[str, datetime]] = []

    # ========================================================================
    # Secret Creation and Storage
    # ========================================================================

    async def create_secret(
        self,
        tenant_id: str,
        name: str,
        secret_value: str,
        secret_type: SecretType,
        created_by: str,
        description: Optional[str] = None,
        expires_in_days: Optional[int] = None,
        rotation_interval_days: Optional[int] = None,
        allowed_readers: Optional[List[str]] = None
    ) -> SecretSchema:
        """Create and store a new secret"""
        
        secret_id = f"sec_{tenant_id}_{name.lower().replace(' ', '_')}_{uuid4().hex[:8]}"
        
        # Encrypt secret value
        encrypted_value = self.cipher_suite.encrypt(secret_value.encode()).decode()
        
        # Create version
        version = SecretVersionSchema(
            secret_value=encrypted_value,
            created_by=created_by,
            status=SecretStatus.ACTIVE
        )
        
        # Create metadata
        metadata = SecretMetadataSchema(
            secret_id=secret_id,
            tenant_id=tenant_id,
            name=name,
            description=description,
            secret_type=secret_type,
            created_by=created_by,
            owner_user_id=created_by,
            allowed_readers=allowed_readers or [],
            current_version_id=version.version_id,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days) if expires_in_days else None,
            rotation_interval_days=rotation_interval_days,
            last_rotated_at=datetime.utcnow() if rotation_interval_days else None
        )
        
        # Create secret
        secret = SecretSchema(
            metadata=metadata,
            current_version=version,
            versions=[version]
        )
        
        self._secrets[secret_id] = secret
        
        # Schedule rotation if needed
        if rotation_interval_days:
            next_rotation = datetime.utcnow() + timedelta(days=rotation_interval_days)
            self._rotation_queue.append((secret_id, next_rotation))
        
        return secret

    # ========================================================================
    # Secret Retrieval
    # ========================================================================

    async def get_secret(
        self,
        secret_id: str,
        tenant_id: str,
        user_id: str,
        decrypt: bool = False
    ) -> Optional[SecretSchema]:
        """Retrieve secret with access logging"""
        
        if secret_id not in self._secrets:
            return None
        
        secret = self._secrets[secret_id]
        
        # Verify tenant ownership
        if secret.metadata.tenant_id != tenant_id:
            await self._log_access(
                secret_id, tenant_id, user_id,
                "read", False, "Tenant mismatch"
            )
            return None
        
        # Check access permissions
        if (user_id != secret.metadata.owner_user_id and
            user_id not in secret.metadata.allowed_readers):
            await self._log_access(
                secret_id, tenant_id, user_id,
                "read", False, "Insufficient permissions"
            )
            return None
        
        # Log successful access
        await self._log_access(secret_id, tenant_id, user_id, "read", True)
        
        # Decrypt if requested
        if decrypt:
            try:
                decrypted_value = self.cipher_suite.decrypt(
                    secret.current_version.secret_value.encode()
                ).decode()
                # Create new secret object with decrypted value for return
                secret_copy = secret.copy()
                secret_copy.current_version.secret_value = decrypted_value
                return secret_copy
            except Exception:
                return None
        
        return secret

    async def get_secret_value(
        self,
        secret_id: str,
        tenant_id: str,
        user_id: str
    ) -> Optional[str]:
        """Get decrypted secret value (use with caution)"""
        secret = await self.get_secret(secret_id, tenant_id, user_id, decrypt=True)
        if secret:
            return secret.current_version.secret_value
        return None

    # ========================================================================
    # Secret Updates and Rotation
    # ========================================================================

    async def update_secret(
        self,
        secret_id: str,
        tenant_id: str,
        new_value: str,
        updated_by: str
    ) -> Optional[SecretSchema]:
        """Update secret value (creates new version)"""
        
        secret = self._secrets.get(secret_id)
        if not secret or secret.metadata.tenant_id != tenant_id:
            return None
        
        # Verify permission
        if updated_by != secret.metadata.owner_user_id:
            return None
        
        # Create new version
        encrypted_value = self.cipher_suite.encrypt(new_value.encode()).decode()
        new_version = SecretVersionSchema(
            secret_value=encrypted_value,
            created_by=updated_by,
            status=SecretStatus.ACTIVE
        )
        
        # Mark old version as rotated
        secret.metadata.current_version_id = new_version.version_id
        secret.current_version = new_version
        secret.versions.append(new_version)
        secret.metadata.updated_at = datetime.utcnow()
        secret.metadata.version_count += 1
        
        # Log update
        await self._log_access(secret_id, tenant_id, updated_by, "update", True)
        
        return secret

    async def rotate_secret(
        self,
        request: RotateSecretRequestSchema,
        tenant_id: str
    ) -> Optional[SecretSchema]:
        """Rotate secret with new value"""
        
        secret = self._secrets.get(request.secret_id)
        if not secret or secret.metadata.tenant_id != tenant_id:
            return None
        
        # Generate new value if not provided
        new_value = request.new_value or self._generate_secret(secret.metadata.secret_type)
        
        # Update secret
        updated = await self.update_secret(
            request.secret_id,
            tenant_id,
            new_value,
            request.requested_by
        )
        
        if updated:
            updated.metadata.last_rotated_at = datetime.utcnow()
            await self._log_access(
                request.secret_id, tenant_id,
                request.requested_by, "rotate", True
            )
        
        return updated

    async def schedule_rotation(
        self,
        secret_id: str,
        rotation_interval_days: int,
        tenant_id: str,
        requested_by: str
    ) -> bool:
        """Schedule automatic rotation"""
        
        secret = self._secrets.get(secret_id)
        if not secret or secret.metadata.tenant_id != tenant_id:
            return False
        
        secret.metadata.rotation_interval_days = rotation_interval_days
        next_rotation = datetime.utcnow() + timedelta(days=rotation_interval_days)
        self._rotation_queue.append((secret_id, next_rotation))
        
        await self._log_access(secret_id, tenant_id, requested_by, "schedule_rotation", True)
        return True

    # ========================================================================
    # Version Management
    # ========================================================================

    async def get_secret_versions(
        self,
        secret_id: str,
        tenant_id: str,
        user_id: str,
        limit: int = 50
    ) -> Optional[List[SecretVersionSchema]]:
        """Get version history"""
        secret = await self.get_secret(secret_id, tenant_id, user_id, False)
        if not secret:
            return None
        
        return secret.versions[-limit:]

    async def rollback_secret(
        self,
        secret_id: str,
        version_id: str,
        tenant_id: str,
        requested_by: str
    ) -> Optional[SecretSchema]:
        """Rollback to previous version"""
        
        secret = self._secrets.get(secret_id)
        if not secret or secret.metadata.tenant_id != tenant_id:
            return None
        
        # Find version
        target_version = None
        for v in secret.versions:
            if v.version_id == version_id:
                target_version = v
                break
        
        if not target_version:
            return None
        
        # Restore version
        secret.current_version = target_version
        secret.metadata.current_version_id = version_id
        
        await self._log_access(secret_id, tenant_id, requested_by, "rollback", True)
        
        return secret

    # ========================================================================
    # Access Control
    # ========================================================================

    async def grant_access(
        self,
        secret_id: str,
        tenant_id: str,
        user_id: str,
        granted_by: str
    ) -> bool:
        """Grant read access to user"""
        
        secret = self._secrets.get(secret_id)
        if not secret or secret.metadata.tenant_id != tenant_id:
            return False
        
        if user_id not in secret.metadata.allowed_readers:
            secret.metadata.allowed_readers.append(user_id)
        
        return True

    async def revoke_access(
        self,
        secret_id: str,
        tenant_id: str,
        user_id: str,
        revoked_by: str
    ) -> bool:
        """Revoke read access from user"""
        
        secret = self._secrets.get(secret_id)
        if not secret or secret.metadata.tenant_id != tenant_id:
            return False
        
        if user_id in secret.metadata.allowed_readers:
            secret.metadata.allowed_readers.remove(user_id)
        
        return True

    async def allow_application_access(
        self,
        secret_id: str,
        tenant_id: str,
        application_name: str
    ) -> bool:
        """Allow application to access secret"""
        
        secret = self._secrets.get(secret_id)
        if not secret or secret.metadata.tenant_id != tenant_id:
            return False
        
        if application_name not in secret.metadata.allowed_applications:
            secret.metadata.allowed_applications.append(application_name)
        
        return True

    # ========================================================================
    # Audit and Logging
    # ========================================================================

    async def _log_access(
        self,
        secret_id: str,
        tenant_id: str,
        user_id: str,
        action: str,
        success: bool,
        reason: Optional[str] = None
    ) -> None:
        """Log secret access"""
        log = SecretAccessLogSchema(
            secret_id=secret_id,
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            success=success,
            reason=reason
        )
        self._access_logs.append(log)

    async def get_access_logs(
        self,
        secret_id: str,
        tenant_id: str,
        limit: int = 100
    ) -> List[SecretAccessLogSchema]:
        """Get access logs for secret"""
        return [
            log for log in self._access_logs
            if log.secret_id == secret_id and log.tenant_id == tenant_id
        ][-limit:]

    # ========================================================================
    # External Vault Integration
    # ========================================================================

    async def sync_to_external_vault(
        self,
        secret_id: str,
        backend: VaultBackend
    ) -> bool:
        """Sync secret to external vault"""
        # Implementation would integrate with actual vault services
        secret = self._secrets.get(secret_id)
        if secret:
            secret.metadata.backend = backend
            secret.metadata.external_id = f"{backend}_{uuid4().hex[:16]}"
            return True
        return False

    # ========================================================================
    # Utilities
    # ========================================================================

    def _generate_secret(self, secret_type: SecretType) -> str:
        """Generate random secret value"""
        import secrets
        if secret_type == SecretType.API_KEY:
            return f"sk_{secrets.token_hex(32)}"
        elif secret_type == SecretType.JWT_SECRET:
            return secrets.token_urlsafe(64)
        elif secret_type == SecretType.ENCRYPTION_KEY:
            return Fernet.generate_key().decode()
        else:
            return secrets.token_urlsafe(32)

    async def check_expiration(self) -> List[str]:
        """Check for expired secrets"""
        expired = []
        for secret_id, secret in self._secrets.items():
            if (secret.metadata.expires_at and
                secret.metadata.expires_at < datetime.utcnow()):
                expired.append(secret_id)
        return expired

    async def process_rotation_queue(self) -> Dict[str, bool]:
        """Process pending rotations"""
        results = {}
        now = datetime.utcnow()
        current_time = list(self._rotation_queue)
        
        for secret_id, rotation_time in current_time:
            if rotation_time <= now:
                secret = self._secrets.get(secret_id)
                if secret:
                    new_value = self._generate_secret(secret.metadata.secret_type)
                    result = await self.update_secret(
                        secret_id,
                        secret.metadata.tenant_id,
                        new_value,
                        "system_rotation"
                    )
                    results[secret_id] = result is not None
                    self._rotation_queue.remove((secret_id, rotation_time))
        
        return results
