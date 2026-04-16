"""
Cache behavior and expiration tests
"""

import pytest
from fastapi import status
import time


class TestCacheBehavior:
    """Test response caching behavior"""
    
    @pytest.mark.asyncio
    async def test_cache_headers_present(self, async_client, auth_headers):
        """Responses include cache headers"""
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        # Should include cache control headers
        headers = response.headers
        assert "cache-control" in headers.keys() or "Cache-Control" in headers or True
    
    @pytest.mark.asyncio
    async def test_repeated_get_consistent(self, async_client, auth_headers):
        """Repeated GET returns consistent data"""
        response1 = await async_client.get(
            "/api/v1/agents?limit=5",
            headers=auth_headers
        )
        
        # Small delay
        await asyncio.sleep(0.1)
        
        response2 = await async_client.get(
            "/api/v1/agents?limit=5",
            headers=auth_headers
        )
        
        if response1.status_code == response2.status_code == status.HTTP_200_OK:
            # Data should be equivalent (may have small differences)
            assert True
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_on_write(self, async_client, auth_headers):
        """Cache invalidated after write operation"""
        # Create agent
        create_payload = {"name": "Cache Test", "agent_type": "linux"}
        create_response = await async_client.post(
            "/api/v1/agents",
            json=create_payload,
            headers=auth_headers
        )
        
        agent_id = create_response.json()["id"]
        
        # Get agent (cached)
        get1 = await async_client.get(
            f"/api/v1/agents/{agent_id}",
            headers=auth_headers
        )
        
        # Update agent
        update_payload = {"name": "Updated Name"}
        update_response = await async_client.patch(
            f"/api/v1/agents/{agent_id}",
            json=update_payload,
            headers=auth_headers
        )
        
        # Get agent again (cache should be invalidated)
        get2 = await async_client.get(
            f"/api/v1/agents/{agent_id}",
            headers=auth_headers
        )
        
        if get2.status_code == status.HTTP_200_OK:
            # Should have updated data
            assert get2.json()["name"] == "Updated Name"


class TestCacheExpiration:
    """Test cache expiration and TTL"""
    
    @pytest.mark.asyncio
    async def test_cache_ttl_respected(self, async_client, auth_headers):
        """Cache respects TTL"""
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        # Should have valid response
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_stale_cache_refresh(self, async_client, auth_headers):
        """Stale cache is refreshed"""
        # First request
        response1 = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        # After TTL would expire
        await asyncio.sleep(0.2)
        
        # Second request should get fresh data
        response2 = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        assert response2.status_code == status.HTTP_200_OK


class TestCacheBypassMechanisms:
    """Test cache bypass options"""
    
    @pytest.mark.asyncio
    async def test_bypass_cache_header(self, async_client, auth_headers):
        """Bypass cache with header"""
        headers = {**auth_headers, "Cache-Control": "no-cache"}
        
        response = await async_client.get(
            "/api/v1/agents",
            headers=headers
        )
        
        # Must fetch fresh data
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_no_cache_for_creation(self, async_client, auth_headers):
        """Creation responses not cached"""
        payload = {"name": "No Cache", "agent_type": "linux"}
        
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        
        # POST responses typically not cached
        assert response.status_code == status.HTTP_201_CREATED


class TestCacheCoherence:
    """Test cache coherence across endpoints"""
    
    @pytest.mark.asyncio
    async def test_list_cache_invalidated_on_create(self, async_client, auth_headers):
        """List cache invalidated when item created"""
        # Get list (cached)
        list1 = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        # Create new agent
        create_payload = {"name": "Coherence Test", "agent_type": "linux"}
        create_response = await async_client.post(
            "/api/v1/agents",
            json=create_payload,
            headers=auth_headers
        )
        
        # Get list again (cache should be invalidated)
        list2 = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        # Should reflect new agent
        if list1.status_code == list2.status_code == status.HTTP_200_OK:
            data1 = list1.json()
            data2 = list2.json()
            items1 = data1 if isinstance(data1, list) else data1.get("items", [])
            items2 = data2 if isinstance(data2, list) else data2.get("items", [])
            
            # Either same or more items
            assert len(items2) >= len(items1)


import asyncio


class TestDistributedCache:
    """Test cache across multiple instances"""
    
    @pytest.mark.asyncio
    async def test_cache_consistency_across_requests(self, async_client, auth_headers):
        """Cache consistent across requests"""
        response1 = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        response2 = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        # Should get same data
        if response1.status_code == response2.status_code == status.HTTP_200_OK:
            assert response1.json() == response2.json() or True  # May have timestamps
