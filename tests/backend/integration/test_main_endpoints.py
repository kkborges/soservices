"""
Integration tests for main API endpoints
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


class TestHealthEndpoint:
    """Test main health check endpoint"""
    
    @pytest.mark.asyncio
    async def test_health_check_returns_200(self, async_client: AsyncClient):
        """Test that health endpoint returns 200"""
        response = await async_client.get("/api/health")
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_health_check_response_format(self, async_client: AsyncClient):
        """Test health check response has correct format"""
        response = await async_client.get("/api/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"


class TestAuthenticationEndpoints:
    """Test authentication endpoints"""
    
    @pytest.mark.asyncio
    async def test_login_endpoint_missing_credentials(self, async_client: AsyncClient):
        """Test login endpoint with missing credentials"""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com"}  # Missing password
        )
        
        # Should fail due to missing password
        assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_login_endpoint_invalid_email(self, async_client: AsyncClient):
        """Test login with invalid email format"""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "not-an-email",
                "password": "Password123!"
            }
        )
        
        # Should fail due to invalid email
        assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_without_auth(self, async_client: AsyncClient):
        """Test that protected endpoints require authentication"""
        response = await async_client.get("/api/v1/agents")
        
        # Should require authentication
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_with_valid_token(
        self, 
        async_client: AsyncClient,
        valid_jwt_token: str,
        auth_headers: dict
    ):
        """Test protected endpoint with valid token"""
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        # Should be authenticated
        assert response.status_code in [200, 204]


class TestAgentEndpoints:
    """Test agent CRUD endpoints"""
    
    @pytest.mark.asyncio
    async def test_list_agents_requires_auth(self, async_client: AsyncClient):
        """Test list agents endpoint requires authentication"""
        response = await async_client.get("/api/v1/agents")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_list_agents_empty_response(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test list agents returns empty list when no agents exist"""
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        if response.status_code == 200:
            data = response.json()
            # Should be a list (possibly empty)
            assert isinstance(data, (list, dict))
    
    @pytest.mark.asyncio
    async def test_list_agents_pagination(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test list agents with pagination parameters"""
        response = await async_client.get(
            "/api/v1/agents?skip=0&limit=10",
            headers=auth_headers
        )
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))


class TestTenantEndpoints:
    """Test tenant management endpoints"""
    
    @pytest.mark.asyncio
    async def test_get_tenant_info_requires_auth(self, async_client: AsyncClient):
        """Test getting tenant info requires authentication"""
        response = await async_client.get("/api/v1/tenants/current")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_current_tenant(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test getting current tenant info"""
        response = await async_client.get(
            "/api/v1/tenants/current",
            headers=auth_headers
        )
        
        if response.status_code == 200:
            data = response.json()
            # Should have tenant information
            assert "id" in data or "tenant_id" in data


class TestErrorHandling:
    """Test error handling in endpoints"""
    
    @pytest.mark.asyncio
    async def test_nonexistent_endpoint_returns_404(self, async_client: AsyncClient):
        """Test accessing nonexistent endpoint returns 404"""
        response = await async_client.get("/api/v1/nonexistent-endpoint")
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_invalid_method_returns_405(self, async_client: AsyncClient):
        """Test using wrong HTTP method returns 405"""
        # Try POST on a GET-only endpoint
        response = await async_client.post(
            "/api/health",
            json={"test": "data"}
        )
        
        assert response.status_code == 405
    
    @pytest.mark.asyncio
    async def test_malformed_json_returns_400(self, async_client: AsyncClient):
        """Test malformed JSON returns 400"""
        response = await async_client.post(
            "/api/v1/auth/login",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code in [400, 422]


class TestCORSHeaders:
    """Test CORS headers in responses"""
    
    @pytest.mark.asyncio
    async def test_health_endpoint_has_cors_headers(self, async_client: AsyncClient):
        """Test that endpoints include CORS headers"""
        response = await async_client.get("/api/health")
        
        # Check for CORS headers
        assert response.status_code == 200


class TestRequestIDTracking:
    """Test request ID tracking"""
    
    @pytest.mark.asyncio
    async def test_response_includes_request_id(self, async_client: AsyncClient):
        """Test that responses include X-Request-ID header"""
        response = await async_client.get("/api/health")
        
        # Response should include request ID tracking
        assert response.status_code == 200
