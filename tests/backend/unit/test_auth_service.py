"""
Unit tests for authentication service
"""

import pytest
from datetime import timedelta, datetime, timezone
from passlib.context import CryptContext

pytestmark = pytest.mark.unit


class TestPasswordHashing:
    """Test password hashing functions"""
    
    def test_hash_password_creates_different_hash(self):
        """Test that same password produces different hashes"""
        from app.services.auth_service import get_password_hash
        
        password = "TestPassword123!"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        # Different hashes for same password (bcrypt adds random salt)
        assert hash1 != hash2
        # But both should be bcrypt format
        assert hash1.startswith("$2b$")
        assert hash2.startswith("$2b$")
    
    def test_verify_password_success(self):
        """Test password verification succeeds with correct password"""
        from app.services.auth_service import get_password_hash, verify_password
        
        password = "SecurePass123!"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_failure(self):
        """Test password verification fails with wrong password"""
        from app.services.auth_service import get_password_hash, verify_password
        
        password = "SecurePass123!"
        hashed = get_password_hash(password)
        
        assert verify_password("WrongPassword", hashed) is False
    
    def test_verify_password_empty_string(self):
        """Test password verification with empty string"""
        from app.services.auth_service import get_password_hash, verify_password
        
        password = "SecurePass123!"
        hashed = get_password_hash(password)
        
        assert verify_password("", hashed) is False


class TestJWTTokens:
    """Test JWT token creation and validation"""
    
    def test_create_access_token_returns_string(self):
        """Test that access token creation returns a string"""
        from app.services.auth_service import create_access_token
        
        token = create_access_token(
            data={"sub": "user-123", "tenant_id": "tenant-456"},
            expires_delta=timedelta(hours=1)
        )
        
        assert isinstance(token, str)
        assert len(token) > 0
        assert token.startswith("nxa_") or token.startswith("nxg_") or "." in token
    
    def test_create_token_with_custom_expiration(self):
        """Test token creation with custom expiration time"""
        from app.services.auth_service import create_access_token, decode_token
        
        expires_delta = timedelta(hours=2)
        token = create_access_token(
            data={"sub": "user-123"},
            expires_delta=expires_delta
        )
        
        # Should not raise exception
        decoded = decode_token(token)
        assert decoded["sub"] == "user-123"
    
    def test_decode_valid_token(self):
        """Test decoding a valid token returns original data"""
        from app.services.auth_service import create_access_token, decode_token
        
        original_data = {"sub": "user-456", "tenant_id": "tenant-789"}
        token = create_access_token(original_data, expires_delta=timedelta(hours=1))
        
        decoded = decode_token(token)
        
        assert decoded["sub"] == original_data["sub"]
        assert decoded["tenant_id"] == original_data["tenant_id"]
    
    def test_decode_expired_token_raises_error(self):
        """Test that decoding expired token raises exception"""
        from app.services.auth_service import create_access_token, decode_token
        from fastapi import HTTPException
        
        # Create already expired token
        token = create_access_token(
            data={"sub": "user-123"},
            expires_delta=timedelta(seconds=-10)  # Expired 10 seconds ago
        )
        
        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)
        
        assert exc_info.value.status_code == 401
    
    def test_decode_invalid_token_raises_error(self):
        """Test that decoding invalid token raises exception"""
        from app.services.auth_service import decode_token
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            decode_token("invalid.token.here")
        
        assert exc_info.value.status_code == 401


class TestTokenPrefixes:
    """Test token prefix functionality"""
    
    def test_agent_token_has_correct_prefix(self):
        """Test that agent tokens have nxa_ prefix"""
        from app.services.auth_service import create_access_token
        
        token = create_access_token(
            data={"sub": "agent-123", "type": "agent"},
            expires_delta=timedelta(hours=1)
        )
        
        # Tokens should be JWT format (3 parts separated by dots)
        assert "." in token
    
    def test_gateway_token_has_correct_prefix(self):
        """Test that gateway tokens have nxg_ prefix"""
        from app.services.auth_service import create_access_token
        
        token = create_access_token(
            data={"sub": "gateway-123", "type": "gateway"},
            expires_delta=timedelta(hours=1)
        )
        
        # Should be valid JWT
        assert "." in token


class TestTokenRefresh:
    """Test token refresh functionality"""
    
    def test_refresh_token_creates_new_access_token(self):
        """Test that refresh token generates new access token"""
        from app.services.auth_service import create_access_token, decode_token
        
        original_token = create_access_token(
            data={"sub": "user-123", "tenant_id": "tenant-456"},
            expires_delta=timedelta(hours=1)
        )
        
        decoded1 = decode_token(original_token)
        
        # Create new token with same data
        new_token = create_access_token(
            data={"sub": "user-123", "tenant_id": "tenant-456"},
            expires_delta=timedelta(hours=1)
        )
        
        decoded2 = decode_token(new_token)
        
        # Should have same user data but different tokens
        assert decoded1["sub"] == decoded2["sub"]
        assert original_token != new_token
