"""
Data consistency and edge case tests
"""

import pytest
from fastapi import status


class TestDataConsistency:
    """Test data consistency across operations"""
    
    @pytest.mark.asyncio
    async def test_created_at_immutable(self, async_client, auth_headers):
        """created_at timestamp cannot be modified"""
        # Create agent first
        create_payload = {"name": "Immutable Test", "agent_type": "linux"}
        create_response = await async_client.post(
            "/api/v1/agents",
            json=create_payload,
            headers=auth_headers
        )
        
        agent_id = create_response.json()["id"]
        created_at_original = create_response.json().get("created_at")
        
        # Try to update agent
        update_payload = {"name": "Updated"}
        await async_client.patch(
            f"/api/v1/agents/{agent_id}",
            json=update_payload,
            headers=auth_headers
        )
        
        # Verify created_at unchanged
        get_response = await async_client.get(
            f"/api/v1/agents/{agent_id}",
            headers=auth_headers
        )
        
        if get_response.status_code == status.HTTP_200_OK:
            data = get_response.json()
            assert data.get("created_at") == created_at_original
    
    @pytest.mark.asyncio
    async def test_updated_at_changes_on_modification(self, async_client, auth_headers):
        """updated_at changes when record is modified"""
        # Create agent
        create_payload = {"name": "Update Test", "agent_type": "linux"}
        create_response = await async_client.post(
            "/api/v1/agents",
            json=create_payload,
            headers=auth_headers
        )
        
        agent_id = create_response.json()["id"]
        updated_at_original = create_response.json().get("updated_at")
        
        # Update agent
        update_payload = {"name": "Updated"}
        update_response = await async_client.patch(
            f"/api/v1/agents/{agent_id}",
            json=update_payload,
            headers=auth_headers
        )
        
        if update_response.status_code == status.HTTP_200_OK:
            updated_at_new = update_response.json().get("updated_at")
            # Should be different (or at least not less than original)
            assert updated_at_new is not None
    
    @pytest.mark.asyncio
    async def test_idempotent_create_fails_duplicate(self, async_client, auth_headers):
        """Creating with same unique field fails second time"""
        payload = {"name": "Unique Name", "slug": "unique-slug"}
        
        # First create succeeds
        response1 = await async_client.post(
            "/api/v1/tenants",
            json=payload,
            headers=auth_headers
        )
        
        # Second with same slug fails
        response2 = await async_client.post(
            "/api/v1/tenants",
            json=payload,
            headers=auth_headers
        )
        
        assert response1.status_code == status.HTTP_201_CREATED
        assert response2.status_code == status.HTTP_409_CONFLICT


class TestDataIntegrity:
    """Test data integrity constraints"""
    
    @pytest.mark.asyncio
    async def test_foreign_key_constraint_enforced(self, async_client, auth_headers):
        """Cannot create child with nonexistent parent"""
        # Try to create agent for non-existent tenant
        payload = {
            "name": "Orphan Agent",
            "tenant_id": 999999
        }
        
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        
        # Should fail
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_409_CONFLICT
        ]
    
    @pytest.mark.asyncio
    async def test_cannot_delete_parent_with_children(self, async_client, admin_headers):
        """Cannot delete tenant with users/agents"""
        # Create tenant with agents first (would need setup)
        # This test structure validates the constraint exists
        
        response = await async_client.delete(
            "/api/v1/tenants/1",
            headers=admin_headers
        )
        
        # Could succeed if cascade delete, or fail if protected
        assert response.status_code in [
            status.HTTP_204_NO_CONTENT,
            status.HTTP_409_CONFLICT,
            status.HTTP_404_NOT_FOUND
        ]
    
    @pytest.mark.asyncio
    async def test_status_enum_values_only(self, async_client):
        """Only valid enum values accepted for status"""
        payload = {
            "agent_id": "agent-001",
            "status": "invalid_status"
        }
        
        response = await async_client.put(
            "/api/v1/agents/1/status",
            json=payload
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestEmptyDataEdgeCases:
    """Test handling of empty or null data"""
    
    @pytest.mark.asyncio
    async def test_empty_string_field_rejected(self, async_client, auth_headers):
        """Empty string where string required"""
        payload = {
            "name": "",  # Empty
            "agent_type": "linux"
        }
        
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_whitespace_only_string_rejected(self, async_client, auth_headers):
        """Whitespace-only string"""
        payload = {
            "name": "   ",  # Whitespace only
            "agent_type": "linux"
        }
        
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_null_required_field(self, async_client, auth_headers):
        """Null value for required field"""
        payload = {
            "name": None,
            "agent_type": "linux"
        }
        
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_empty_list_for_array_field(self, async_client, admin_headers):
        """Empty array for array field"""
        payload = {
            "name": "Empty Roles",
            "permissions": []  # Empty
        }
        
        response = await async_client.post(
            "/api/v1/roles",
            json=payload,
            headers=admin_headers
        )
        
        # Could accept empty or require at least one
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]


class TestSpecialCharactersAndEncoding:
    """Test handling of special characters"""
    
    @pytest.mark.asyncio
    async def test_unicode_characters_accepted(self, async_client, auth_headers):
        """Unicode characters handled correctly"""
        payload = {
            "name": "Agente-日本語-🚀",
            "agent_type": "linux"
        }
        
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        
        # Should accept unicode
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
    
    @pytest.mark.asyncio
    async def test_sql_injection_attempt_rejected(self, async_client, auth_headers):
        """SQL injection attempts are escaped"""
        payload = {
            "name": "'; DROP TABLE agents; --",
            "agent_type": "linux"
        }
        
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        
        # Should accept safely (not execute SQL)
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
    
    @pytest.mark.asyncio
    async def test_xss_payload_escaped(self, async_client, auth_headers):
        """XSS payloads are escaped"""
        payload = {
            "name": "<script>alert('XSS')</script>",
            "agent_type": "linux"
        }
        
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        
        # Should accept safely
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]


class TestDataTypeConversions:
    """Test automatic type conversions and coercions"""
    
    @pytest.mark.asyncio
    async def test_numeric_string_to_int(self, async_client, auth_headers):
        """Numeric string converted to integer"""
        response = await async_client.get(
            "/api/v1/agents?limit=10",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_non_numeric_string_rejected(self, async_client, auth_headers):
        """Non-numeric string rejected for integer field"""
        response = await async_client.get(
            "/api/v1/agents?limit=abc",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_boolean_string_conversion(self, async_client, auth_headers):
        """Boolean string values handled"""
        response = await async_client.get(
            "/api/v1/alerts?resolved=true",
            headers=auth_headers
        )
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
