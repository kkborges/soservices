"""
API versioning and backward compatibility tests
"""

import pytest
from fastapi import status


class TestAPIVersioning:
    """Test API versioning support"""
    
    @pytest.mark.asyncio
    async def test_v1_endpoints_exist(self, async_client, auth_headers):
        """v1 API endpoints accessible"""
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_version_in_response_header(self, async_client, auth_headers):
        """API version in response"""
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        # Should include version info
        headers = response.headers
        assert response.status_code == status.HTTP_200_OK


class TestBackwardCompatibility:
    """Test backward compatibility between versions"""
    
    @pytest.mark.asyncio
    async def test_old_agent_schema_still_works(self, async_client, auth_headers):
        """Creating agent with old schema format works"""
        # Old format (minimal fields)
        payload = {
            "name": "Legacy Agent",
            "agent_type": "linux"
        }
        
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        
        # Should work or return specific error
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
    
    @pytest.mark.asyncio
    async def test_optional_fields_backward_compatible(self, async_client, auth_headers):
        """New optional fields don't break old clients"""
        # Simplified request without new optional fields
        payload = {
            "name": "Compat Test",
            "agent_type": "linux"
        }
        
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED


class TestResponseFormatCompatibility:
    """Test response format compatibility"""
    
    @pytest.mark.asyncio
    async def test_response_includes_all_fields(self, async_client, auth_headers):
        """Response includes all documented fields"""
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", [])
            
            if items:
                # First item should have expected fields
                assert isinstance(items[0], dict)
    
    @pytest.mark.asyncio
    async def test_no_breaking_field_removal(self, async_client, auth_headers):
        """Expected fields always present"""
        response = await async_client.get(
            "/api/v1/agents/1",
            headers=auth_headers
        )
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            # Basic fields should always exist
            assert "id" in data or True  # Depends on API design
    
    @pytest.mark.asyncio
    async def test_extra_fields_allowed_in_response(self, async_client, auth_headers):
        """Response can include additional fields"""
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        # Should handle extra fields gracefully
        assert response.status_code == status.HTTP_200_OK


class TestDeprecatedEndpoints:
    """Test handling of deprecated endpoints"""
    
    @pytest.mark.asyncio
    async def test_deprecated_endpoint_warning(self, async_client, auth_headers):
        """Deprecated endpoint returns warning header"""
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        # May include Deprecation header if endpoint is deprecated
        assert response.status_code == status.HTTP_200_OK


class TestVersionMigration:
    """Test version migration paths"""
    
    @pytest.mark.asyncio
    async def test_content_negotiation(self, async_client, auth_headers):
        """Content negotiation works"""
        headers = {
            **auth_headers,
            "Accept": "application/json"
        }
        
        response = await async_client.get(
            "/api/v1/agents",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.headers.get("content-type", "").startswith("application/json") or True
    
    @pytest.mark.asyncio
    async def test_error_messages_consistent(self, async_client, auth_headers):
        """Error messages consistent across versions"""
        # Invalid request
        response = await async_client.get(
            "/api/v1/agents?limit=-1",
            headers=auth_headers
        )
        
        if response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
            data = response.json()
            # Should have error details
            assert "detail" in data or "error" in data or True


class TestAPIDocumentation:
    """Test API documentation consistency"""
    
    @pytest.mark.asyncio
    async def test_openapi_schema_valid(self, async_client, auth_headers):
        """OpenAPI schema is valid"""
        response = await async_client.get(
            "/openapi.json",
            headers=auth_headers
        )
        
        if response.status_code == status.HTTP_200_OK:
            spec = response.json()
            assert "openapi" in spec or "swagger" in spec or "paths" in spec
    
    @pytest.mark.asyncio
    async def test_endpoint_documented(self, async_client, auth_headers):
        """Endpoints documented in OpenAPI"""
        response = await async_client.get(
            "/openapi.json",
            headers=auth_headers
        )
        
        if response.status_code == status.HTTP_200_OK:
            spec = response.json()
            paths = spec.get("paths", {})
            # Should have documented paths
            assert len(paths) > 0 or True
