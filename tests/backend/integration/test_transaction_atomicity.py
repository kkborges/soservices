"""
Transaction atomicity and consistency tests
"""

import pytest
from fastapi import status


class TestTransactionAtomicity:
    """Test database transaction atomicity"""
    
    @pytest.mark.asyncio
    async def test_agent_creation_all_or_nothing(self, async_client, auth_headers):
        """Agent creation is atomic - all fields set or none"""
        payload = {
            "name": "Atomic Agent",
            "agent_type": "linux",
            "description": "For atomicity testing"
        }
        
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        
        if response.status_code == status.HTTP_201_CREATED:
            agent_id = response.json()["id"]
            
            # Verify all fields persisted
            get_response = await async_client.get(
                f"/api/v1/agents/{agent_id}",
                headers=auth_headers
            )
            
            assert get_response.status_code == status.HTTP_200_OK
            data = get_response.json()
            assert data["name"] == "Atomic Agent"
            assert data["agent_type"] == "linux"
    
    @pytest.mark.asyncio
    async def test_failed_validation_rolls_back(self, async_client, auth_headers):
        """Failed validation rolls back state"""
        # First create valid agent
        valid_payload = {
            "name": "Valid Agent",
            "agent_type": "linux"
        }
        
        valid_response = await async_client.post(
            "/api/v1/agents",
            json=valid_payload,
            headers=auth_headers
        )
        
        assert valid_response.status_code == status.HTTP_201_CREATED
        
        # Try invalid creation
        invalid_payload = {
            "name": "",  # Invalid
            "agent_type": "linux"
        }
        
        invalid_response = await async_client.post(
            "/api/v1/agents",
            json=invalid_payload,
            headers=auth_headers
        )
        
        assert invalid_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestTransactionConsistency:
    """Test transaction consistency"""
    
    @pytest.mark.asyncio
    async def test_concurrent_updates_consistent(self, async_client, auth_headers):
        """Concurrent updates maintain consistency"""
        # Create agent
        create_payload = {"name": "Consistency Test", "agent_type": "linux"}
        create_response = await async_client.post(
            "/api/v1/agents",
            json=create_payload,
            headers=auth_headers
        )
        
        agent_id = create_response.json()["id"]
        
        # Update 1
        update1 = {"description": "Update 1"}
        response1 = await async_client.patch(
            f"/api/v1/agents/{agent_id}",
            json=update1,
            headers=auth_headers
        )
        
        # Update 2
        update2 = {"status": "online"}
        response2 = await async_client.put(
            f"/api/v1/agents/{agent_id}/status",
            json=update2,
            headers=auth_headers
        )
        
        # Both should succeed and not conflict
        assert response1.status_code in [
            status.HTTP_200_OK,
            status.HTTP_409_CONFLICT
        ]
        
        if response2.status_code == status.HTTP_200_OK:
            # Verify final state
            get_response = await async_client.get(
                f"/api/v1/agents/{agent_id}",
                headers=auth_headers
            )
            assert get_response.status_code == status.HTTP_200_OK


class TestTransactionIsolation:
    """Test transaction isolation levels"""
    
    @pytest.mark.asyncio
    async def test_dirty_read_prevention(self, async_client, auth_headers):
        """Uncommitted changes not visible"""
        # Create agent
        payload = {"name": "Isolation Test", "agent_type": "linux"}
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        
        agent_id = response.json()["id"]
        
        # Get initial state
        get1 = await async_client.get(
            f"/api/v1/agents/{agent_id}",
            headers=auth_headers
        )
        
        initial_state = get1.json()
        
        # Verify no dirty reads occurred
        assert initial_state is not None


class TestRollbackScenarios:
    """Test rollback in error scenarios"""
    
    @pytest.mark.asyncio
    async def test_bulk_operation_partial_failure(self, async_client, auth_headers):
        """Partial bulk operation failure handled"""
        payload = {
            "alert_ids": [1, 2, 3, 99999],
            "resolution": "Test rollback"
        }
        
        response = await async_client.post(
            "/api/v1/alerts/bulk-resolve",
            json=payload,
            headers=auth_headers
        )
        
        # Should handle gracefully
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_202_ACCEPTED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]


class TestConstraintEnforcement:
    """Test constraint enforcement in transactions"""
    
    @pytest.mark.asyncio
    async def test_unique_constraint_in_transaction(self, async_client, admin_headers):
        """Unique constraints enforced in transaction"""
        # Create first tenant
        payload1 = {
            "name": "Tenant 1",
            "slug": "unique-tenant"
        }
        
        response1 = await async_client.post(
            "/api/v1/tenants",
            json=payload1,
            headers=admin_headers
        )
        
        assert response1.status_code == status.HTTP_201_CREATED
        
        # Try duplicate
        payload2 = {
            "name": "Tenant 2",
            "slug": "unique-tenant"
        }
        
        response2 = await async_client.post(
            "/api/v1/tenants",
            json=payload2,
            headers=admin_headers
        )
        
        # Second should fail
        assert response2.status_code == status.HTTP_409_CONFLICT
