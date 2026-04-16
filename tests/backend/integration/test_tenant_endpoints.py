"""
Integration tests for tenant management endpoints
"""

import pytest
from fastapi import status


class TestTenantEndpoints:
    """Test tenant CRUD and multi-tenancy endpoints"""
    
    @pytest.mark.asyncio
    async def test_create_tenant_success(self, async_client, admin_headers):
        """POST /tenants - Create new tenant"""
        payload = {
            "name": "Acme Corporation",
            "slug": "acme-corp-001"
        }
        
        response = await async_client.post(
            "/api/v1/tenants",
            json=payload,
            headers=admin_headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Acme Corporation"
        assert data["slug"] == "acme-corp-001"
    
    @pytest.mark.asyncio
    async def test_create_tenant_duplicate_slug(self, async_client, admin_headers):
        """POST /tenants - Duplicate slug rejected"""
        payload1 = {
            "name": "Tenant 1",
            "slug": "duplicate-slug"
        }
        
        # Create first tenant
        await async_client.post(
            "/api/v1/tenants",
            json=payload1,
            headers=admin_headers
        )
        
        # Try to create with same slug
        payload2 = {
            "name": "Tenant 2",
            "slug": "duplicate-slug"
        }
        
        response = await async_client.post(
            "/api/v1/tenants",
            json=payload2,
            headers=admin_headers
        )
        
        assert response.status_code == status.HTTP_409_CONFLICT
    
    @pytest.mark.asyncio
    async def test_get_tenant_by_id(self, async_client, admin_headers):
        """GET /tenants/{id} - Retrieve tenant details"""
        # Create tenant first
        create_payload = {
            "name": "Test Tenant",
            "slug": "test-tenant-001"
        }
        
        create_response = await async_client.post(
            "/api/v1/tenants",
            json=create_payload,
            headers=admin_headers
        )
        
        tenant_id = create_response.json()["id"]
        
        # Get tenant
        response = await async_client.get(
            f"/api/v1/tenants/{tenant_id}",
            headers=admin_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == tenant_id
    
    @pytest.mark.asyncio
    async def test_get_tenant_not_found(self, async_client, admin_headers):
        """GET /tenants/{id} - Tenant not found"""
        response = await async_client.get(
            "/api/v1/tenants/99999",
            headers=admin_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    @pytest.mark.asyncio
    async def test_list_tenants_pagination(self, async_client, admin_headers):
        """GET /tenants - List all tenants with pagination"""
        response = await async_client.get(
            "/api/v1/tenants?skip=0&limit=20",
            headers=admin_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_update_tenant_success(self, async_client, admin_headers):
        """PATCH /tenants/{id} - Update tenant"""
        # Create tenant
        create_payload = {
            "name": "Original Name",
            "slug": "original-slug"
        }
        
        create_response = await async_client.post(
            "/api/v1/tenants",
            json=create_payload,
            headers=admin_headers
        )
        
        tenant_id = create_response.json()["id"]
        
        # Update it
        update_payload = {
            "name": "Updated Name"
        }
        
        response = await async_client.patch(
            f"/api/v1/tenants/{tenant_id}",
            json=update_payload,
            headers=admin_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Updated Name"
    
    @pytest.mark.asyncio
    async def test_delete_tenant_success(self, async_client, admin_headers):
        """DELETE /tenants/{id} - Delete tenant"""
        # Create tenant
        create_payload = {
            "name": "Tenant to Delete",
            "slug": "delete-me"
        }
        
        create_response = await async_client.post(
            "/api/v1/tenants",
            json=create_payload,
            headers=admin_headers
        )
        
        tenant_id = create_response.json()["id"]
        
        # Delete it
        response = await async_client.delete(
            f"/api/v1/tenants/{tenant_id}",
            headers=admin_headers
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    @pytest.mark.asyncio
    async def test_tenant_without_admin_access_denied(self, async_client, auth_headers):
        """Non-admin user cannot manage tenants"""
        payload = {
            "name": "Unauthorized Tenant",
            "slug": "unauthorized"
        }
        
        response = await async_client.post(
            "/api/v1/tenants",
            json=payload,
            headers=auth_headers  # Regular auth, not admin
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    @pytest.mark.asyncio
    async def test_tenant_activation_toggle(self, async_client, admin_headers):
        """PATCH /tenants/{id}/activate - Activate/deactivate tenant"""
        # Create tenant
        create_payload = {
            "name": "Activation Test",
            "slug": "activation-test"
        }
        
        create_response = await async_client.post(
            "/api/v1/tenants",
            json=create_payload,
            headers=admin_headers
        )
        
        tenant_id = create_response.json()["id"]
        
        # Deactivate
        response = await async_client.patch(
            f"/api/v1/tenants/{tenant_id}/activate",
            json={"is_active": False},
            headers=admin_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_active"] is False
    
    @pytest.mark.asyncio
    async def test_get_tenant_users(self, async_client, admin_headers):
        """GET /tenants/{id}/users - List tenant users"""
        # Create tenant
        create_payload = {
            "name": "Users Test",
            "slug": "users-test"
        }
        
        create_response = await async_client.post(
            "/api/v1/tenants",
            json=create_payload,
            headers=admin_headers
        )
        
        tenant_id = create_response.json()["id"]
        
        # Get users
        response = await async_client.get(
            f"/api/v1/tenants/{tenant_id}/users",
            headers=admin_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
