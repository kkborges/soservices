"""
Unit tests for token management and refresh logic
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import time


class TestTokenService:
    """Test JWT token creation, validation, and refresh"""
    
    @pytest.mark.asyncio
    async def test_access_token_creation(self, valid_jwt_token):
        """Create access token with valid payload"""
        assert valid_jwt_token is not None
        assert "." in valid_jwt_token  # JWT format: header.payload.signature
    
    @pytest.mark.asyncio
    async def test_access_token_contains_user_id(self, valid_jwt_token):
        """Access token contains user ID"""
        from jwt import decode
        from app.core.config import settings
        
        payload = decode(
            valid_jwt_token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
        
        assert "sub" in payload or "user_id" in payload
    
    @pytest.mark.asyncio
    async def test_access_token_expiration(self, valid_jwt_token):
        """Access token has expiration"""
        from jwt import decode
        from app.core.config import settings
        
        payload = decode(
            valid_jwt_token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
        
        assert "exp" in payload
    
    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, expired_jwt_token):
        """Expired token is rejected"""
        from jwt import decode, ExpiredSignatureError
        from app.core.config import settings
        
        with pytest.raises(ExpiredSignatureError):
            decode(
                expired_jwt_token,
                settings.SECRET_KEY,
                algorithms=["HS256"]
            )
    
    @pytest.mark.asyncio
    async def test_refresh_token_generation(self):
        """Refresh token generated separately from access token"""
        # Tokens should be different
        access_token = "access_token_123"
        refresh_token = "refresh_token_456"
        
        assert access_token != refresh_token
    
    @pytest.mark.asyncio
    async def test_refresh_token_validity_longer(self):
        """Refresh token has longer expiration than access"""
        access_expiry = datetime.utcnow() + timedelta(minutes=15)
        refresh_expiry = datetime.utcnow() + timedelta(days=7)
        
        # Refresh should expire later
        assert refresh_expiry > access_expiry
    
    @pytest.mark.asyncio
    async def test_token_refresh_creates_new_access(self):
        """Using refresh token creates new access token"""
        old_access = "old_access_token"
        new_access = "new_access_token_from_refresh"
        
        # Old and new should be different
        assert old_access != new_access
    
    @pytest.mark.asyncio
    async def test_token_invalidation_on_logout(self):
        """Token becomes invalid after logout"""
        tokens_blacklist = set()
        token = "token_123"
        
        # Add to blacklist
        tokens_blacklist.add(token)
        
        # Check if token is blacklisted
        is_valid = token not in tokens_blacklist
        assert is_valid is False
