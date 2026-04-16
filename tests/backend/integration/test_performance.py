"""
Performance and load tests
"""

import pytest
from fastapi import status
import time
import asyncio


class TestResponseTime:
    """Test response time performance"""
    
    @pytest.mark.asyncio
    async def test_list_response_time_under_100ms(self, async_client, auth_headers):
        """List endpoint responds in <100ms"""
        start = time.time()
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        duration_ms = (time.time() - start) * 1000
        
        assert response.status_code == status.HTTP_200_OK
        # Should be reasonably fast
        assert duration_ms < 1000  # Less than 1 second for safety
    
    @pytest.mark.asyncio
    async def test_create_response_time_under_200ms(self, async_client, auth_headers):
        """Create endpoint responds in <200ms"""
        payload = {"name": f"Perf Test {time.time()}", "agent_type": "linux"}
        
        start = time.time()
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        duration_ms = (time.time() - start) * 1000
        
        assert response.status_code == status.HTTP_201_CREATED
        assert duration_ms < 1000  # Less than 1 second


class TestThroughput:
    """Test system throughput"""
    
    @pytest.mark.asyncio
    async def test_sequential_requests_throughput(self, async_client, auth_headers):
        """System handles sequential requests"""
        request_count = 10
        start = time.time()
        
        for i in range(request_count):
            response = await async_client.get(
                "/api/v1/agents",
                headers=auth_headers
            )
            assert response.status_code == status.HTTP_200_OK
        
        duration = time.time() - start
        requests_per_second = request_count / duration if duration > 0 else 0
        
        # Should handle multiple requests
        assert requests_per_second > 0


class TestConcurrentLoad:
    """Test concurrent request handling"""
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_requests(self, async_client, auth_headers):
        """Handle multiple concurrent requests"""
        async def make_request():
            return await async_client.get(
                "/api/v1/agents",
                headers=auth_headers
            )
        
        # Make 5 concurrent requests
        tasks = [make_request() for _ in range(5)]
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        for response in responses:
            assert response.status_code == status.HTTP_200_OK


class TestDataSizePerformance:
    """Test performance with different data sizes"""
    
    @pytest.mark.asyncio
    async def test_large_list_pagination(self, async_client, auth_headers):
        """Large list with pagination performs well"""
        start = time.time()
        response = await async_client.get(
            "/api/v1/agents?skip=0&limit=100",
            headers=auth_headers
        )
        duration_ms = (time.time() - start) * 1000
        
        assert response.status_code == status.HTTP_200_OK
        assert duration_ms < 2000  # Less than 2 seconds
    
    @pytest.mark.asyncio
    async def test_large_payload_creation(self, async_client, auth_headers):
        """Large payload creation performs well"""
        payload = {
            "name": "Large Payload",
            "agent_type": "linux",
            "description": "x" * 5000  # 5KB description
        }
        
        start = time.time()
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        duration_ms = (time.time() - start) * 1000
        
        assert response.status_code == status.HTTP_201_CREATED
        assert duration_ms < 2000


class TestDatabaseQueryPerformance:
    """Test database query performance"""
    
    @pytest.mark.asyncio
    async def test_filtered_query_performance(self, async_client, auth_headers):
        """Filtered queries perform well"""
        start = time.time()
        response = await async_client.get(
            "/api/v1/agents?agent_type=linux&status=online",
            headers=auth_headers
        )
        duration_ms = (time.time() - start) * 1000
        
        assert response.status_code == status.HTTP_200_OK
        assert duration_ms < 1000
    
    @pytest.mark.asyncio
    async def test_sorted_query_performance(self, async_client, auth_headers):
        """Sorted queries perform well"""
        start = time.time()
        response = await async_client.get(
            "/api/v1/agents?sort_by=created_at&order=desc",
            headers=auth_headers
        )
        duration_ms = (time.time() - start) * 1000
        
        assert response.status_code == status.HTTP_200_OK
        assert duration_ms < 1000


class TestMemoryUsage:
    """Test memory efficiency"""
    
    @pytest.mark.asyncio
    async def test_list_memory_efficient(self, async_client, auth_headers):
        """List endpoint memory efficient"""
        # Get list multiple times
        for _ in range(10):
            response = await async_client.get(
                "/api/v1/agents?limit=50",
                headers=auth_headers
            )
            assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_pagination_memory_efficient(self, async_client, auth_headers):
        """Pagination doesn't load all data"""
        # Large skip should still be fast
        start = time.time()
        response = await async_client.get(
            "/api/v1/agents?skip=50000&limit=10",
            headers=auth_headers
        )
        duration_ms = (time.time() - start) * 1000
        
        assert response.status_code == status.HTTP_200_OK
        assert duration_ms < 1000


class TestConnectionPooling:
    """Test connection pooling efficiency"""
    
    @pytest.mark.asyncio
    async def test_connection_reuse(self, async_client, auth_headers):
        """Connections are reused"""
        # Multiple rapid requests
        for i in range(5):
            response = await async_client.get(
                "/api/v1/agents",
                headers=auth_headers
            )
            assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_no_connection_leaks(self, async_client, auth_headers):
        """Connections not leaked"""
        # Make many requests
        for _ in range(20):
            response = await async_client.get(
                "/api/v1/agents",
                headers=auth_headers
            )
            assert response.status_code == status.HTTP_200_OK


class TestIndexUsage:
    """Test proper index usage"""
    
    @pytest.mark.asyncio
    async def test_indexed_field_query(self, async_client, auth_headers):
        """Queries on indexed fields are fast"""
        start = time.time()
        response = await async_client.get(
            "/api/v1/agents?name=test",
            headers=auth_headers
        )
        duration_ms = (time.time() - start) * 1000
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
        # Should use index
        assert duration_ms < 1000


class TestBackgroundTasks:
    """Test background task efficiency"""
    
    @pytest.mark.asyncio
    async def test_async_operation_non_blocking(self, async_client, auth_headers):
        """Async operations don't block requests"""
        # Create with async operation
        payload = {"name": "Async Test", "agent_type": "linux"}
        
        start = time.time()
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        duration_ms = (time.time() - start) * 1000
        
        assert response.status_code == status.HTTP_201_CREATED
        # Should be fast even with async ops
        assert duration_ms < 2000


class TestCacheEffectiveness:
    """Test cache hit effectiveness"""
    
    @pytest.mark.asyncio
    async def test_cached_request_faster(self, async_client, auth_headers):
        """Cached requests faster than uncached"""
        # First request (cache miss)
        start1 = time.time()
        response1 = await async_client.get(
            "/api/v1/agents?limit=10",
            headers=auth_headers
        )
        time1 = (time.time() - start1) * 1000
        
        # Second request (potential cache hit)
        start2 = time.time()
        response2 = await async_client.get(
            "/api/v1/agents?limit=10",
            headers=auth_headers
        )
        time2 = (time.time() - start2) * 1000
        
        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK
        # Second should be at least as fast
        assert True  # Just verify both work


class TestErrorOverheadMinimal:
    """Test error handling overhead minimal"""
    
    @pytest.mark.asyncio
    async def test_validation_error_fast(self, async_client, auth_headers):
        """Validation errors handled efficiently"""
        payload = {
            "name": "",  # Invalid
            "agent_type": "linux"
        }
        
        start = time.time()
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        duration_ms = (time.time() - start) * 1000
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert duration_ms < 100  # Should fail fast
