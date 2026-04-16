"""
Unit tests for Pydantic schemas and validation
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

pytestmark = pytest.mark.unit


class TestLoginSchema:
    """Test LoginSchema validation"""
    
    def test_valid_login_credentials(self):
        """Test valid login credentials pass validation"""
        from app.schemas.auth import LoginSchema
        
        schema = LoginSchema(
            email="user@soservices.com.br",
            password="SecurePassword123!"
        )
        
        assert schema.email == "user@soservices.com.br"
        assert schema.password == "SecurePassword123!"
    
    def test_login_invalid_email_format(self):
        """Test invalid email format raises validation error"""
        from app.schemas.auth import LoginSchema
        
        with pytest.raises(ValidationError) as exc_info:
            LoginSchema(
                email="not-an-email",
                password="SecurePassword123!"
            )
        
        # Should have email validation error
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("email",) for e in errors)
    
    def test_login_missing_required_fields(self):
        """Test missing required fields raises validation error"""
        from app.schemas.auth import LoginSchema
        
        with pytest.raises(ValidationError):
            LoginSchema(email="user@example.com")  # Missing password


class TestTokenResponseSchema:
    """Test TokenResponse schema"""
    
    def test_token_response_has_required_fields(self):
        """Test token response has all required fields"""
        from app.schemas.auth import TokenResponse
        
        response = TokenResponse(
            access_token="eyJhbGc...",
            refresh_token="eyJhbGc...",
            token_type="bearer"
        )
        
        assert response.access_token == "eyJhbGc..."
        assert response.refresh_token == "eyJhbGc..."
        assert response.token_type == "bearer"


class TestAgentSchema:
    """Test Agent schemas"""
    
    def test_create_agent_schema_validation(self):
        """Test agent creation schema validation"""
        from app.schemas.agent import CreateAgentSchema
        
        schema = CreateAgentSchema(
            name="Production Agent",
            hostname="prod-server-01",
            os_type="Linux"
        )
        
        assert schema.name == "Production Agent"
        assert schema.hostname == "prod-server-01"
        assert schema.os_type == "Linux"
    
    def test_agent_schema_name_required(self):
        """Test that agent name is required"""
        from app.schemas.agent import CreateAgentSchema
        
        with pytest.raises(ValidationError) as exc_info:
            CreateAgentSchema(
                hostname="prod-server-01",
                os_type="Linux"
            )
        
        errors = exc_info.value.errors()
        assert any("name" in str(e["loc"]).lower() for e in errors)
    
    def test_agent_response_schema(self):
        """Test agent response schema"""
        from app.schemas.agent import AgentResponseSchema
        
        schema = AgentResponseSchema(
            id="agent-123",
            name="Test Agent",
            status="online",
            tenant_id="tenant-123"
        )
        
        assert schema.id == "agent-123"
        assert schema.status == "online"


class TestPaginationSchema:
    """Test pagination schemas"""
    
    def test_pagination_query_params_valid(self):
        """Test valid pagination parameters"""
        from app.schemas.common import PaginationParams
        
        params = PaginationParams(skip=0, limit=10)
        
        assert params.skip == 0
        assert params.limit == 10
    
    def test_pagination_default_values(self):
        """Test pagination default values"""
        from app.schemas.common import PaginationParams
        
        # Use defaults
        params = PaginationParams()
        
        assert params.skip == 0
        assert params.limit == 10  # or whatever default


class TestErrorResponseSchema:
    """Test error response schemas"""
    
    def test_error_response_format(self):
        """Test error response has correct format"""
        from app.schemas.common import ErrorResponse
        
        error = ErrorResponse(
            status_code=400,
            detail="Invalid request",
            error_type="validation_error"
        )
        
        assert error.status_code == 400
        assert error.detail == "Invalid request"
        assert error.error_type == "validation_error"


class TestTenantSchema:
    """Test Tenant schemas"""
    
    def test_create_tenant_schema(self):
        """Test tenant creation schema"""
        from app.schemas.tenant import CreateTenantSchema
        
        schema = CreateTenantSchema(
            name="Acme Corp",
            slug="acme-corp"
        )
        
        assert schema.name == "Acme Corp"
        assert schema.slug == "acme-corp"
    
    def test_tenant_slug_format_validation(self):
        """Test tenant slug format validation"""
        from app.schemas.tenant import CreateTenantSchema
        
        # Valid slug (lowercase, hyphens)
        valid = CreateTenantSchema(name="Test", slug="my-tenant")
        assert valid.slug == "my-tenant"
        
        # Invalid slug should raise error
        with pytest.raises(ValidationError):
            CreateTenantSchema(name="Test", slug="Invalid Slug!")
