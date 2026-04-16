"""
Integration tests for RBAC (Role-Based Access Control) endpoints
"""

import pytest
from fastapi import status


class TestRBACEndpoints:
    """Test role management, permissions, and access control"""
    
    @pytest.mark.asyncio
    async def test_create_role_success(self, async_client, admin_headers):
        """POST /roles - Create new role"""
        payload = {
            "name": "Agent Manager",
            "description": "Can manage agents",
            "permissions": ["agent:create", "agent:read", "agent:update"]
        }
        
        response = await async_client.post(
            "/api/v1/roles",
            json=payload,
            headers=admin_headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Agent Manager"
    
    @pytest.mark.asyncio
    async def test_list_roles(self, async_client, admin_headers):
        """GET /roles - List all roles"""
        response = await async_client.get(
            "/api/v1/roles",
            headers=admin_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_get_role_by_id(self, async_client, admin_headers):
        """GET /roles/{id} - Retrieve role details"""
        # Create role first
        create_payload = {
            "name": "Test Role",
            "permissions": ["read"]
        }
        
        create_response = await async_client.post(
            "/api/v1/roles",
            json=create_payload,
            headers=admin_headers
        )
        
        role_id = create_response.json()["id"]
        
        # Get role
        response = await async_client.get(
            f"/api/v1/roles/{role_id}",
            headers=admin_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_update_role_permissions(self, async_client, admin_headers):
        """PATCH /roles/{id} - Update role permissions"""
        # Create role
        create_payload = {
            "name": "Original Role",
            "permissions": ["read"]
        }
        
        create_response = await async_client.post(
            "/api/v1/roles",
            json=create_payload,
            headers=admin_headers
        )
        
        role_id = create_response.json()["id"]
        
        # Update permissions
        update_payload = {
            "permissions": ["read", "write", "delete"]
        }
        
        response = await async_client.patch(
            f"/api/v1/roles/{role_id}",
            json=update_payload,
            headers=admin_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_delete_role_success(self, async_client, admin_headers):
        """DELETE /roles/{id} - Delete role"""
        # Create role
        create_payload = {
            "name": "Role to Delete",
            "permissions": ["read"]
        }
        
        create_response = await async_client.post(
            "/api/v1/roles",
            json=create_payload,
            headers=admin_headers
        )
        
        role_id = create_response.json()["id"]
        
        # Delete
        response = await async_client.delete(
            f"/api/v1/roles/{role_id}",
            headers=admin_headers
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    @pytest.mark.asyncio
    async def test_assign_role_to_user(self, async_client, admin_headers):
        """POST /users/{id}/roles - Assign role to user"""
        # Create role first
        role_payload = {
            "name": "Viewer",
            "permissions": ["read"]
        }
        
        role_response = await async_client.post(
            "/api/v1/roles",
            json=role_payload,
            headers=admin_headers
        )
        
        role_id = role_response.json()["id"]
        
        # Assign to user (assuming user_id=1)
        assign_payload = {
            "role_ids": [role_id]
        }
        
        response = await async_client.post(
            "/api/v1/users/1/roles",
            json=assign_payload,
            headers=admin_headers
        )
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_201_CREATED
        ]
    
    @pytest.mark.asyncio
    async def test_remove_role_from_user(self, async_client, admin_headers):
        """DELETE /users/{id}/roles/{role_id} - Remove role"""
        # Assuming role is already assigned
        response = await async_client.delete(
            "/api/v1/users/1/roles/1",
            headers=admin_headers
        )
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_204_NO_CONTENT
        ]
    
    @pytest.mark.asyncio
    async def test_check_user_permission(self, async_client, auth_headers):
        """GET /users/me/permissions - Check current user permissions"""
        response = await async_client.get(
            "/api/v1/users/me/permissions",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list) or "permissions" in data
    
    @pytest.mark.asyncio
    async def test_permission_denied_without_role(self, async_client, auth_headers):
        """Access denied when user lacks required role"""
        # Try admin endpoint without admin role
        response = await async_client.post(
            "/api/v1/roles",
            json={"name": "Unauthorized Role", "permissions": ["read"]},
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    @pytest.mark.asyncio
    async def test_list_user_roles(self, async_client, auth_headers):
        """GET /users/{id}/roles - List user roles"""
        response = await async_client.get(
            "/api/v1/users/1/roles",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
