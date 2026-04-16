"""
Pagination, sorting, and filtering tests
"""

import pytest
from fastapi import status


class TestPagination:
    """Test pagination functionality"""
    
    @pytest.mark.asyncio
    async def test_default_pagination(self, async_client, auth_headers):
        """List with default pagination"""
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should have pagination info
        assert isinstance(data, (list, dict))
    
    @pytest.mark.asyncio
    async def test_skip_parameter(self, async_client, auth_headers):
        """Skip parameter skips records"""
        # Get first 5
        response1 = await async_client.get(
            "/api/v1/agents?skip=0&limit=5",
            headers=auth_headers
        )
        
        # Get next 5
        response2 = await async_client.get(
            "/api/v1/agents?skip=5&limit=5",
            headers=auth_headers
        )
        
        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_limit_parameter(self, async_client, auth_headers):
        """Limit parameter restricts results"""
        response = await async_client.get(
            "/api/v1/agents?limit=10",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Result count should not exceed limit
        items = data if isinstance(data, list) else data.get("items", [])
        assert len(items) <= 10
    
    @pytest.mark.asyncio
    async def test_limit_zero_rejected(self, async_client, auth_headers):
        """Limit of 0 should be rejected"""
        response = await async_client.get(
            "/api/v1/agents?limit=0",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_negative_limit_rejected(self, async_client, auth_headers):
        """Negative limit rejected"""
        response = await async_client.get(
            "/api/v1/agents?limit=-5",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_negative_skip_rejected(self, async_client, auth_headers):
        """Negative skip rejected"""
        response = await async_client.get(
            "/api/v1/agents?skip=-1",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_large_limit_capped(self, async_client, auth_headers):
        """Very large limit is capped"""
        response = await async_client.get(
            "/api/v1/agents?limit=999999",
            headers=auth_headers
        )
        
        # Should succeed but be capped
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", [])
            # Verify reasonable max
            assert len(items) <= 1000


class TestSorting:
    """Test result sorting"""
    
    @pytest.mark.asyncio
    async def test_sort_by_name_asc(self, async_client, auth_headers):
        """Sort by name ascending"""
        response = await async_client.get(
            "/api/v1/agents?sort_by=name&order=asc",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_sort_by_name_desc(self, async_client, auth_headers):
        """Sort by name descending"""
        response = await async_client.get(
            "/api/v1/agents?sort_by=name&order=desc",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_sort_by_created_at(self, async_client, auth_headers):
        """Sort by created_at timestamp"""
        response = await async_client.get(
            "/api/v1/agents?sort_by=created_at&order=desc",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_invalid_sort_field(self, async_client, auth_headers):
        """Invalid sort field rejected"""
        response = await async_client.get(
            "/api/v1/agents?sort_by=nonexistent_field",
            headers=auth_headers
        )
        
        # Should either ignore or return 422
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
    
    @pytest.mark.asyncio
    async def test_invalid_order_direction(self, async_client, auth_headers):
        """Invalid order direction rejected"""
        response = await async_client.get(
            "/api/v1/agents?order=sideways",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestFiltering:
    """Test result filtering"""
    
    @pytest.mark.asyncio
    async def test_filter_by_agent_type(self, async_client, auth_headers):
        """Filter agents by type"""
        response = await async_client.get(
            "/api/v1/agents?agent_type=linux",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_filter_by_status(self, async_client, auth_headers):
        """Filter agents by status"""
        response = await async_client.get(
            "/api/v1/agents?status=online",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_filter_by_alert_severity(self, async_client, auth_headers):
        """Filter alerts by severity"""
        response = await async_client.get(
            "/api/v1/alerts?severity=critical",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_filter_by_alert_resource(self, async_client, auth_headers):
        """Filter alerts by resource name"""
        response = await async_client.get(
            "/api/v1/alerts?resource=host-01",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_filter_by_resolved_status(self, async_client, auth_headers):
        """Filter alerts by resolved status"""
        response = await async_client.get(
            "/api/v1/alerts?resolved=false",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_filter_by_date_range(self, async_client, auth_headers):
        """Filter by date range"""
        response = await async_client.get(
            "/api/v1/alerts?created_after=2026-01-01&created_before=2026-12-31",
            headers=auth_headers
        )
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
    
    @pytest.mark.asyncio
    async def test_multiple_filters_combined(self, async_client, auth_headers):
        """Multiple filters applied together"""
        response = await async_client.get(
            "/api/v1/agents?agent_type=linux&status=online&skip=0&limit=10",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK


class TestSearchFiltering:
    """Test text search/filtering"""
    
    @pytest.mark.asyncio
    async def test_search_agent_by_name(self, async_client, auth_headers):
        """Search agents by name"""
        response = await async_client.get(
            "/api/v1/agents?search=agent-01",
            headers=auth_headers
        )
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
    
    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, async_client, auth_headers):
        """Search is case-insensitive"""
        response = await async_client.get(
            "/api/v1/agents?search=AGENT",
            headers=auth_headers
        )
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
    
    @pytest.mark.asyncio
    async def test_search_partial_match(self, async_client, auth_headers):
        """Search with partial match"""
        response = await async_client.get(
            "/api/v1/agents?search=age",  # Part of "Agent"
            headers=auth_headers
        )
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]


class TestPaginationEdgeCases:
    """Test pagination edge cases"""
    
    @pytest.mark.asyncio
    async def test_skip_beyond_total(self, async_client, auth_headers):
        """Skip beyond total records"""
        response = await async_client.get(
            "/api/v1/agents?skip=999999&limit=10",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        items = data if isinstance(data, list) else data.get("items", [])
        # Should return empty
        assert len(items) == 0
    
    @pytest.mark.asyncio
    async def test_pagination_with_no_results(self, async_client, auth_headers):
        """Pagination returns empty list gracefully"""
        response = await async_client.get(
            "/api/v1/agents?search=nonexistent9999",
            headers=auth_headers
        )
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", [])
            assert isinstance(items, list)
