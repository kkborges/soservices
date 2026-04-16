"""
Integration tests for alert management endpoints
"""

import pytest
from fastapi import status
from datetime import datetime


class TestAlertEndpoints:
    """Test alert CRUD, filtering, and resolution endpoints"""
    
    @pytest.mark.asyncio
    async def test_create_alert_success(self, async_client, auth_headers):
        """POST /alerts - Create new alert"""
        payload = {
            "title": "High CPU Usage",
            "description": "CPU usage exceeded 90%",
            "severity": "critical",
            "resource": "host-01"
        }
        
        response = await async_client.post(
            "/api/v1/alerts",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["title"] == "High CPU Usage"
        assert data["severity"] == "critical"
    
    @pytest.mark.asyncio
    async def test_create_alert_invalid_severity(self, async_client, auth_headers):
        """POST /alerts - Invalid severity value"""
        payload = {
            "title": "Test Alert",
            "severity": "invalid_severity",
            "resource": "host-01"
        }
        
        response = await async_client.post(
            "/api/v1/alerts",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_get_alert_by_id(self, async_client, auth_headers):
        """GET /alerts/{id} - Retrieve alert details"""
        # Create alert first
        create_payload = {
            "title": "Alert for retrieval",
            "severity": "high",
            "resource": "host-02"
        }
        
        create_response = await async_client.post(
            "/api/v1/alerts",
            json=create_payload,
            headers=auth_headers
        )
        
        alert_id = create_response.json()["id"]
        
        # Get alert
        response = await async_client.get(
            f"/api/v1/alerts/{alert_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == alert_id
    
    @pytest.mark.asyncio
    async def test_list_alerts_with_pagination(self, async_client, auth_headers):
        """GET /alerts - List alerts with pagination"""
        response = await async_client.get(
            "/api/v1/alerts?skip=0&limit=10",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_list_alerts_filter_by_severity(self, async_client, auth_headers):
        """GET /alerts?severity=critical - Filter alerts by severity"""
        response = await async_client.get(
            "/api/v1/alerts?severity=critical",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_list_alerts_filter_by_resource(self, async_client, auth_headers):
        """GET /alerts?resource=host-01 - Filter by resource"""
        response = await async_client.get(
            "/api/v1/alerts?resource=host-01",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_resolve_alert_success(self, async_client, auth_headers):
        """PATCH /alerts/{id}/resolve - Mark alert resolved"""
        # Create alert
        create_payload = {
            "title": "Alert to resolve",
            "severity": "medium",
            "resource": "host-03"
        }
        
        create_response = await async_client.post(
            "/api/v1/alerts",
            json=create_payload,
            headers=auth_headers
        )
        
        alert_id = create_response.json()["id"]
        
        # Resolve it
        resolve_payload = {
            "resolution": "Issue fixed"
        }
        
        response = await async_client.patch(
            f"/api/v1/alerts/{alert_id}/resolve",
            json=resolve_payload,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["resolved"] is True
    
    @pytest.mark.asyncio
    async def test_update_alert_success(self, async_client, auth_headers):
        """PATCH /alerts/{id} - Update alert properties"""
        # Create alert
        create_payload = {
            "title": "Alert to update",
            "severity": "low",
            "resource": "host-04"
        }
        
        create_response = await async_client.post(
            "/api/v1/alerts",
            json=create_payload,
            headers=auth_headers
        )
        
        alert_id = create_response.json()["id"]
        
        # Update severity
        update_payload = {
            "severity": "high"
        }
        
        response = await async_client.patch(
            f"/api/v1/alerts/{alert_id}",
            json=update_payload,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["severity"] == "high"
    
    @pytest.mark.asyncio
    async def test_delete_alert_success(self, async_client, auth_headers):
        """DELETE /alerts/{id} - Delete alert"""
        # Create alert
        create_payload = {
            "title": "Alert to delete",
            "severity": "low",
            "resource": "host-05"
        }
        
        create_response = await async_client.post(
            "/api/v1/alerts",
            json=create_payload,
            headers=auth_headers
        )
        
        alert_id = create_response.json()["id"]
        
        # Delete it
        response = await async_client.delete(
            f"/api/v1/alerts/{alert_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    @pytest.mark.asyncio
    async def test_list_unresolved_alerts(self, async_client, auth_headers):
        """GET /alerts?resolved=false - List unresolved alerts"""
        response = await async_client.get(
            "/api/v1/alerts?resolved=false",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_bulk_resolve_alerts(self, async_client, auth_headers):
        """POST /alerts/bulk-resolve - Resolve multiple alerts"""
        payload = {
            "alert_ids": [1, 2, 3],
            "resolution": "Mass resolution"
        }
        
        response = await async_client.post(
            "/api/v1/alerts/bulk-resolve",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_202_ACCEPTED
        ]
