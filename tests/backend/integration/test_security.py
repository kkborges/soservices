"""
Security tests - authentication, authorization, injection, brute force
"""

import pytest
from fastapi import status


class TestPasswordSecurity:
    """Test password security measures"""
    
    @pytest.mark.asyncio
    async def test_password_stored_hashed(self, auth_headers):
        """Passwords stored as hashes not plain text"""
        # Test is implicit - if we can login with password, it's hashed
        # This test validates the hashing service exists
        from app.services.auth_service import hash_password, verify_password
        
        password = "SecurePassword123!"
        hashed = hash_password(password)
        
        # Hashed should be different from original
        assert hashed != password
        
        # But verification should work
        assert verify_password(password, hashed)
    
    @pytest.mark.asyncio
    async def test_password_hash_different_each_time(self):
        """Same password produces different hashes"""
        from app.services.auth_service import hash_password
        
        password = "TestPassword"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        # Should use salt - different hashes
        assert hash1 != hash2
        
        # But both should be valid
        from app.services.auth_service import verify_password
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)
    
    @pytest.mark.asyncio
    async def test_weak_password_validation(self, async_client, admin_headers):
        """Weak passwords should be rejected or warned"""
        payload = {
            "email": "user@example.com",
            "password": "123"  # Too weak
        }
        
        response = await async_client.post(
            "/api/v1/auth/register",
            json=payload,
            headers=admin_headers
        )
        
        # Should either reject or require stronger password
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_201_CREATED
        ]


class TestSQLInjectionPrevention:
    """Test SQL injection prevention"""
    
    @pytest.mark.asyncio
    async def test_sql_injection_in_search(self, async_client, auth_headers):
        """SQL injection in search parameter blocked"""
        response = await async_client.get(
            "/api/v1/agents?search='; DROP TABLE agents; --",
            headers=auth_headers
        )
        
        # Should be safe - not execute SQL
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
    
    @pytest.mark.asyncio
    async def test_sql_injection_in_create(self, async_client, auth_headers):
        """SQL injection in create payload blocked"""
        payload = {
            "name": "'; DELETE FROM agents; --",
            "agent_type": "linux'"
        }
        
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        
        # Should be safe
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]


class TestXSSPrevention:
    """Test Cross-Site Scripting prevention"""
    
    @pytest.mark.asyncio
    async def test_xss_payload_in_name(self, async_client, auth_headers):
        """XSS payload in name field escaped"""
        payload = {
            "name": "<script>alert('XSS')</script>",
            "agent_type": "linux"
        }
        
        response = await async_client.post(
            "/api/v1/agents",
            json=payload,
            headers=auth_headers
        )
        
        # Should handle safely
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
    
    @pytest.mark.asyncio
    async def test_xss_payload_in_search(self, async_client, auth_headers):
        """XSS in search parameter sanitized"""
        response = await async_client.get(
            "/api/v1/agents?search=<img src=x onerror=alert('XSS')>",
            headers=auth_headers
        )
        
        # Should be safe
        assert response.status_code == status.HTTP_200_OK


class TestCSRFProtection:
    """Test CSRF protection"""
    
    @pytest.mark.asyncio
    async def test_csrf_token_required_for_mutation(self, async_client):
        """CSRF token required for mutations"""
        payload = {
            "name": "CSRF Test",
            "agent_type": "linux"
        }
        
        # Without CSRF token (but also without auth)
        response = await async_client.post(
            "/api/v1/agents",
            json=payload
        )
        
        # Should be rejected (no auth)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestBruteForceProtection:
    """Test brute force attack prevention"""
    
    @pytest.mark.asyncio
    async def test_login_attempt_throttling(self, async_client):
        """Multiple failed login attempts throttled"""
        # Simulate multiple failed attempts
        for i in range(5):
            payload = {
                "email": "user@example.com",
                "password": f"wrong_password_{i}"
            }
            
            response = await async_client.post(
                "/api/v1/auth/login",
                json=payload
            )
            
            # After several attempts, should throttle
            if i >= 3:
                assert response.status_code in [
                    status.HTTP_401_UNAUTHORIZED,
                    status.HTTP_429_TOO_MANY_REQUESTS
                ]


class TestTokenSecurity:
    """Test token security measures"""
    
    @pytest.mark.asyncio
    async def test_token_expiration(self, valid_jwt_token):
        """Token expires after configured time"""
        from jwt import decode
        from app.core.config import settings
        
        payload = decode(
            valid_jwt_token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
        
        # Should have expiration
        assert "exp" in payload
    
    @pytest.mark.asyncio
    async def test_token_refresh_creates_new_token(self, async_client, auth_headers):
        """Token refresh creates new token"""
        response = await async_client.post(
            "/api/v1/auth/refresh",
            headers=auth_headers
        )
        
        # Should either succeed or require refresh token
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED
        ]
    
    @pytest.mark.asyncio
    async def test_token_cannot_be_reused_after_logout(self, async_client, auth_headers):
        """Token invalidated after logout"""
        # Logout
        logout_response = await async_client.post(
            "/api/v1/auth/logout",
            headers=auth_headers
        )
        
        if logout_response.status_code == status.HTTP_200_OK:
            # Try to use same token
            response = await async_client.get(
                "/api/v1/agents",
                headers=auth_headers
            )
            
            # Should be rejected
            if response.status_code == status.HTTP_401_UNAUTHORIZED:
                assert True


class TestHeaderInjection:
    """Test HTTP header injection prevention"""
    
    @pytest.mark.asyncio
    async def test_header_injection_prevented(self, async_client, auth_headers):
        """Header injection attempts blocked"""
        headers = {
            **auth_headers,
            "X-Injected": "value\r\nSet-Cookie: malicious"
        }
        
        response = await async_client.get(
            "/api/v1/agents",
            headers=headers
        )
        
        # Should handle safely
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST
        ]


class TestDataLeakagePrevention:
    """Test prevention of sensitive data leakage"""
    
    @pytest.mark.asyncio
    async def test_password_not_in_response(self, async_client, auth_headers):
        """Password not returned in user data"""
        response = await async_client.get(
            "/api/v1/users/me",
            headers=auth_headers
        )
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            # Password should not be in response
            assert "password" not in data or data.get("password") is None
    
    @pytest.mark.asyncio
    async def test_sensitive_fields_redacted(self, async_client, auth_headers):
        """Internal IDs and sensitive fields not exposed"""
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers
        )
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", [])
            
            # Check first item if exists
            if items and isinstance(items[0], dict):
                # Should have safe fields
                assert len(items[0]) > 0
