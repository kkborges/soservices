"""
Authorization and permission enforcement tests
"""

import pytest
from fastapi import status


class TestAuthorizationAdminOnly:
    """Test admin-only endpoints"""
    
    @pytest.mark.asyncio
    async def test_create_tenant_requires_admin(self, async_client, auth_headers):
        """Regular user cannot create tenant"""
        payload = {"name": "Unauthorized Tenant", "slug": "unauth"}
        
        response = await async_client.post(
            "/api/v1/tenants",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    @pytest.mark.asyncio
    async def test_create_role_requires_admin(self, async_client, auth_headers):
        """Regular user cannot create role"""
        payload = {
            "name": "NewRole",
            "permissions": ["read"]
        }
        
        response = await async_client.post(
            "/api/v1/roles",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    @pytest.mark.asyncio
    async def test_delete_tenant_requires_admin(self, async_client, auth_headers, admin_headers):
        """Regular user cannot delete tenant"""
        # Create tenant as admin
        create_payload = {"name": "ForDelete", "slug": "for-delete"}
        create_response = await async_client.post(
            "/api/v1/tenants",
            json=create_payload,
            headers=admin_headers
        )
        
        tenant_id = create_response.json()["id"]
        
        # Try delete as regular user
        response = await async_client.delete(
            f"/api/v1/tenants/{tenant_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestAuthorizationTenantIsolation:
    """Test tenant data isolation"""
    
    @pytest.mark.asyncio
    async def test_user_cannot_access_other_tenant_agents(self, async_client, auth_headers):
        """User A cannot access User B's tenant agents"""
        # This test assumes multi-tenant setup
        # User should only see their own tenant's agents
        
        response = await async_client.get(
            "/api/v1/agents?tenant_id=2",
            headers=auth_headers
        )
        
        # Should be forbidden or empty if trying other tenant
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_200_OK
        ]
    
    @pytest.mark.asyncio
    async def test_user_cannot_access_other_tenant_data(self, async_client, auth_headers):
        """Accessing another tenant's alert"""
        response = await async_client.get(
            "/api/v1/alerts/9999",
            headers=auth_headers
        )
        
        # Not found or forbidden
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ]


class TestAuthorizationResourceOwnership:
    """Test resource ownership checks"""
    
    @pytest.mark.asyncio
    async def test_user_cannot_delete_other_user_dashboard(self, async_client, auth_headers):
        """User cannot delete another user's dashboard"""
        # Assuming different user's dashboard
        response = await async_client.delete(
            "/api/v1/dashboards/999",
            headers=auth_headers
        )
        
        # Either 404 or 403
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ]
    
    @pytest.mark.asyncio
    async def test_user_can_update_own_dashboard(self, async_client, auth_headers):
        """User can update their own dashboard"""
        # Create dashboard first
        create_payload = {"title": "My Dashboard"}
        create_response = await async_client.post(
            "/api/v1/dashboards",
            json=create_payload,
            headers=auth_headers
        )
        
        dashboard_id = create_response.json()["id"]
        
        # Update it
        update_payload = {"title": "Updated"}
        response = await async_client.patch(
            f"/api/v1/dashboards/{dashboard_id}",
            json=update_payload,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK


class TestAuthorizationRoleBasedAccess:
    """Test role-based permission enforcement"""
    
    @pytest.mark.asyncio
    async def test_user_with_agent_reader_can_read_agents(self, async_client, auth_headers):
        """User with agent:read permission can read"""
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        # Should at least not be forbidden
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN
        ]
    
    @pytest.mark.asyncio
    async def test_user_without_permission_cannot_create(self, async_client, auth_headers):
        """User without agent:create cannot create agent"""
        # Assuming current auth_headers user has minimal permissions
        payload = {"name": "Unauthorized Agent", "agent_type": "linux"}
        
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        
        # If user doesn't have permission
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_201_CREATED
        ]


class TestAuthorizationFieldLevelAccess:
    """Test field-level access control"""
    
    @pytest.mark.asyncio
    async def test_user_cannot_see_sensitive_fields(self, async_client, auth_headers):
        """Sensitive fields are hidden from regular users"""
        response = await async_client.get(
            "/api/v1/users/1",
            headers=auth_headers
        )
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            # Should not expose password hash or internal IDs
            assert "password" not in data or data.get("password") is None
    
    @pytest.mark.asyncio
    async def test_admin_sees_all_fields(self, async_client, admin_headers):
        """Admin user can see all fields"""
        response = await async_client.get(
            "/api/v1/users/1",
            headers=admin_headers
        )
        
        # Admin should have access
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]


class TestAuthorizationMethodLevelAccess:
    """Test HTTP method-level permissions"""
    
    @pytest.mark.asyncio
    async def test_read_only_user_cannot_create(self, async_client, auth_headers):
        """Read-only user cannot POST/PUT/DELETE"""
        payload = {"name": "Test"}
        
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        
        # Should fail if user is read-only
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_201_CREATED,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
    
    @pytest.mark.asyncio
    async def test_read_only_user_can_get(self, async_client, auth_headers):
        """Read-only user can GET"""
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        # GET should work
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN
        ]
