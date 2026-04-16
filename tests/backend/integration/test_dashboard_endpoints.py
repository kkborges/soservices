"""
Integration tests for dashboard and visualization endpoints
"""

import pytest
from fastapi import status


class TestDashboardEndpoints:
    """Test dashboard CRUD, widget management, and data endpoints"""
    
    @pytest.mark.asyncio
    async def test_create_dashboard_success(self, async_client, auth_headers):
        """POST /dashboards - Create new dashboard"""
        payload = {
            "title": "Infrastructure Overview",
            "description": "Main monitoring dashboard"
        }
        
        response = await async_client.post(
            "/api/v1/dashboards",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["title"] == "Infrastructure Overview"
    
    @pytest.mark.asyncio
    async def test_get_dashboard_by_id(self, async_client, auth_headers):
        """GET /dashboards/{id} - Retrieve dashboard"""
        # Create first
        create_payload = {
            "title": "Test Dashboard",
            "description": "For testing"
        }
        
        create_response = await async_client.post(
            "/api/v1/dashboards",
            json=create_payload,
            headers=auth_headers
        )
        
        dashboard_id = create_response.json()["id"]
        
        # Get dashboard
        response = await async_client.get(
            f"/api/v1/dashboards/{dashboard_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == dashboard_id
    
    @pytest.mark.asyncio
    async def test_list_dashboards(self, async_client, auth_headers):
        """GET /dashboards - List user dashboards"""
        response = await async_client.get(
            "/api/v1/dashboards",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_update_dashboard_success(self, async_client, auth_headers):
        """PATCH /dashboards/{id} - Update dashboard"""
        # Create first
        create_payload = {
            "title": "Original Title",
            "description": "Original description"
        }
        
        create_response = await async_client.post(
            "/api/v1/dashboards",
            json=create_payload,
            headers=auth_headers
        )
        
        dashboard_id = create_response.json()["id"]
        
        # Update
        update_payload = {
            "title": "Updated Title"
        }
        
        response = await async_client.patch(
            f"/api/v1/dashboards/{dashboard_id}",
            json=update_payload,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["title"] == "Updated Title"
    
    @pytest.mark.asyncio
    async def test_delete_dashboard_success(self, async_client, auth_headers):
        """DELETE /dashboards/{id} - Delete dashboard"""
        # Create first
        create_payload = {
            "title": "Dashboard to delete"
        }
        
        create_response = await async_client.post(
            "/api/v1/dashboards",
            json=create_payload,
            headers=auth_headers
        )
        
        dashboard_id = create_response.json()["id"]
        
        # Delete
        response = await async_client.delete(
            f"/api/v1/dashboards/{dashboard_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    @pytest.mark.asyncio
    async def test_add_widget_to_dashboard(self, async_client, auth_headers):
        """POST /dashboards/{id}/widgets - Add widget"""
        # Create dashboard first
        dashboard_payload = {"title": "Widget Container"}
        
        dashboard_response = await async_client.post(
            "/api/v1/dashboards",
            json=dashboard_payload,
            headers=auth_headers
        )
        
        dashboard_id = dashboard_response.json()["id"]
        
        # Add widget
        widget_payload = {
            "type": "metric",
            "title": "CPU Usage",
            "position": 0,
            "size": "medium"
        }
        
        response = await async_client.post(
            f"/api/v1/dashboards/{dashboard_id}/widgets",
            json=widget_payload,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
    
    @pytest.mark.asyncio
    async def test_remove_widget_from_dashboard(self, async_client, auth_headers):
        """DELETE /dashboards/{id}/widgets/{widget_id}"""
        # Create dashboard
        dashboard_payload = {"title": "Widget Removal Test"}
        
        dashboard_response = await async_client.post(
            "/api/v1/dashboards",
            json=dashboard_payload,
            headers=auth_headers
        )
        
        dashboard_id = dashboard_response.json()["id"]
        
        # Add widget
        widget_payload = {
            "type": "metric",
            "title": "CPU Usage"
        }
        
        widget_response = await async_client.post(
            f"/api/v1/dashboards/{dashboard_id}/widgets",
            json=widget_payload,
            headers=auth_headers
        )
        
        widget_id = widget_response.json()["id"]
        
        # Remove widget
        response = await async_client.delete(
            f"/api/v1/dashboards/{dashboard_id}/widgets/{widget_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    @pytest.mark.asyncio
    async def test_get_dashboard_metrics(self, async_client, auth_headers):
        """GET /dashboards/{id}/metrics - Retrieve dashboard data"""
        # Create dashboard
        dashboard_payload = {"title": "Metrics Test"}
        
        dashboard_response = await async_client.post(
            "/api/v1/dashboards",
            json=dashboard_payload,
            headers=auth_headers
        )
        
        dashboard_id = dashboard_response.json()["id"]
        
        # Get metrics
        response = await async_client.get(
            f"/api/v1/dashboards/{dashboard_id}/metrics",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_share_dashboard(self, async_client, auth_headers):
        """POST /dashboards/{id}/share - Share dashboard with others"""
        # Create dashboard
        dashboard_payload = {"title": "Shareable Dashboard"}
        
        dashboard_response = await async_client.post(
            "/api/v1/dashboards",
            json=dashboard_payload,
            headers=auth_headers
        )
        
        dashboard_id = dashboard_response.json()["id"]
        
        # Share dashboard
        share_payload = {
            "user_ids": [1, 2, 3],
            "permission": "view"
        }
        
        response = await async_client.post(
            f"/api/v1/dashboards/{dashboard_id}/share",
            json=share_payload,
            headers=auth_headers
        )
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_201_CREATED
        ]
    
    @pytest.mark.asyncio
    async def test_export_dashboard_as_json(self, async_client, auth_headers):
        """GET /dashboards/{id}/export?format=json"""
        # Create dashboard
        dashboard_payload = {"title": "Export Test"}
        
        dashboard_response = await async_client.post(
            "/api/v1/dashboards",
            json=dashboard_payload,
            headers=auth_headers
        )
        
        dashboard_id = dashboard_response.json()["id"]
        
        # Export
        response = await async_client.get(
            f"/api/v1/dashboards/{dashboard_id}/export?format=json",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.headers.get("content-type") == "application/json"
