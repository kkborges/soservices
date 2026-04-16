"""
Integration tests for agent management endpoints
"""

import pytest
from fastapi import status


class TestAgentEndpoints:
    """Test agent CRUD and status endpoints"""
    
    @pytest.mark.asyncio
    async def test_create_agent_success(self, async_client, auth_headers):
        """POST /agents - Create new agent"""
        payload = {
            "name": "test-agent-01",
            "agent_type": "linux",
            "description": "Test agent"
        }
        
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "test-agent-01"
    
    @pytest.mark.asyncio
    async def test_create_agent_missing_name(self, async_client, auth_headers):
        """POST /agents - Missing required name field"""
        payload = {
            "agent_type": "linux"
        }
        
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_get_agent_by_id(self, async_client, auth_headers):
        """GET /agents/{id} - Retrieve agent details"""
        # First create an agent
        create_payload = {
            "name": "agent-for-retrieval",
            "agent_type": "linux"
        }
        
        create_response = await async_client.post(
            "/api/v1/agents",
            json=create_payload,
            headers=auth_headers
        )
        
        agent_id = create_response.json()["id"]
        
        # Now retrieve it
        response = await async_client.get(
            f"/api/v1/agents/{agent_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == agent_id
    
    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, async_client, auth_headers):
        """GET /agents/{id} - Agent not found"""
        response = await async_client.get(
            "/api/v1/agents/99999",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    @pytest.mark.asyncio
    async def test_list_agents_with_pagination(self, async_client, auth_headers):
        """GET /agents - List agents with pagination"""
        response = await async_client.get(
            "/api/v1/agents?skip=0&limit=10",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should have pagination info
        assert "items" in data or "total" in data or isinstance(data, list)
    
    @pytest.mark.asyncio
    async def test_update_agent_success(self, async_client, auth_headers):
        """PATCH /agents/{id} - Update agent details"""
        # Create agent first
        create_payload = {
            "name": "agent-to-update",
            "agent_type": "linux"
        }
        
        create_response = await async_client.post(
            "/api/v1/agents",
            json=create_payload,
            headers=auth_headers
        )
        
        agent_id = create_response.json()["id"]
        
        # Update it
        update_payload = {
            "description": "Updated description"
        }
        
        response = await async_client.patch(
            f"/api/v1/agents/{agent_id}",
            json=update_payload,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["description"] == "Updated description"
    
    @pytest.mark.asyncio
    async def test_delete_agent_success(self, async_client, auth_headers):
        """DELETE /agents/{id} - Delete agent"""
        # Create agent first
        create_payload = {
            "name": "agent-to-delete",
            "agent_type": "linux"
        }
        
        create_response = await async_client.post(
            "/api/v1/agents",
            json=create_payload,
            headers=auth_headers
        )
        
        agent_id = create_response.json()["id"]
        
        # Delete it
        response = await async_client.delete(
            f"/api/v1/agents/{agent_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    @pytest.mark.asyncio
    async def test_agent_status_update(self, async_client, auth_headers):
        """PUT /agents/{id}/status - Update agent status"""
        # Create agent
        create_payload = {
            "name": "agent-status-test",
            "agent_type": "linux"
        }
        
        create_response = await async_client.post(
            "/api/v1/agents",
            json=create_payload,
            headers=auth_headers
        )
        
        agent_id = create_response.json()["id"]
        
        # Update status
        status_payload = {"status": "online"}
        
        response = await async_client.put(
            f"/api/v1/agents/{agent_id}/status",
            json=status_payload,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "online"
    
    @pytest.mark.asyncio
    async def test_agent_heartbeat_endpoint(self, async_client):
        """POST /agents/heartbeat - Agent sends heartbeat"""
        heartbeat_payload = {
            "agent_id": "agent-001",
            "timestamp": "2026-04-22T10:00:00Z",
            "cpu_usage": 45.2,
            "memory_usage": 62.5,
            "disk_usage": 78.1
        }
        
        response = await async_client.post(
            "/api/v1/agents/heartbeat",
            json=heartbeat_payload
        )
        
        # Should accept without auth for heartbeat
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_202_ACCEPTED
        ]
    
    @pytest.mark.asyncio
    async def test_list_agents_filter_by_type(self, async_client, auth_headers):
        """GET /agents?agent_type=linux - Filter by agent type"""
        response = await async_client.get(
            "/api/v1/agents?agent_type=linux",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
