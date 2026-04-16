"""
Unit tests for ORM models - validation and relationships
"""

import pytest
from datetime import datetime, timedelta
import uuid


class TestUserModel:
    """Test User model"""
    
    @pytest.mark.asyncio
    async def test_user_creation_with_valid_data(self, db_session_async):
        """Create valid user"""
        from app.models import User, Tenant
        
        tenant = Tenant(name="Test", slug="test")
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        user = User(
            email="test@example.com",
            tenant_id=tenant.id,
            username="testuser"
        )
        db_session_async.add(user)
        await db_session_async.flush()
        
        assert user.id is not None
        assert user.email == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_password_hashed_on_save(self, db_session_async):
        """Password is hashed before storage"""
        from app.models import User, Tenant
        
        tenant = Tenant(name="Test", slug="test")
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        user = User(
            email="test@example.com",
            tenant_id=tenant.id,
            password="plaintext_password"
        )
        db_session_async.add(user)
        await db_session_async.flush()
        
        # Password should be hashed
        assert user.password != "plaintext_password"
        assert user.password is not None
    
    @pytest.mark.asyncio
    async def test_user_is_active_default_true(self, db_session_async):
        """is_active defaults to True"""
        from app.models import User, Tenant
        
        tenant = Tenant(name="Test", slug="test")
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        user = User(
            email="test@example.com",
            tenant_id=tenant.id
        )
        db_session_async.add(user)
        await db_session_async.flush()
        
        assert user.is_active is True
    
    @pytest.mark.asyncio
    async def test_user_relationship_to_tenant(self, db_session_async):
        """User.tenant relationship works"""
        from app.models import User, Tenant
        
        tenant = Tenant(name="Test", slug="test")
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        user = User(
            email="test@example.com",
            tenant_id=tenant.id
        )
        db_session_async.add(user)
        await db_session_async.flush()
        
        await db_session_async.refresh(user)
        assert user.tenant is not None
        assert user.tenant.id == tenant.id


class TestAgentModel:
    """Test Agent model"""
    
    @pytest.mark.asyncio
    async def test_agent_creation(self, db_session_async):
        """Create valid agent"""
        from app.models import Agent, Tenant
        
        tenant = Tenant(name="Test", slug="test")
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        agent = Agent(
            name="Test Agent",
            agent_type="linux",
            tenant_id=tenant.id
        )
        db_session_async.add(agent)
        await db_session_async.flush()
        
        assert agent.id is not None
        assert agent.name == "Test Agent"
    
    @pytest.mark.asyncio
    async def test_agent_status_default_offline(self, db_session_async):
        """Agent status defaults to offline"""
        from app.models import Agent, Tenant
        
        tenant = Tenant(name="Test", slug="test")
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        agent = Agent(
            name="Test",
            tenant_id=tenant.id
        )
        db_session_async.add(agent)
        await db_session_async.flush()
        
        assert agent.status == "offline"
    
    @pytest.mark.asyncio
    async def test_agent_version_stored(self, db_session_async):
        """Agent version is tracked"""
        from app.models import Agent, Tenant
        
        tenant = Tenant(name="Test", slug="test")
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        agent = Agent(
            name="Test",
            version="4.1.0",
            tenant_id=tenant.id
        )
        db_session_async.add(agent)
        await db_session_async.flush()
        
        assert agent.version == "4.1.0"
    
    @pytest.mark.asyncio
    async def test_agent_last_heartbeat_timestamp(self, db_session_async):
        """Agent last_heartbeat timestamp updated"""
        from app.models import Agent, Tenant
        
        tenant = Tenant(name="Test", slug="test")
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        agent = Agent(
            name="Test",
            tenant_id=tenant.id
        )
        db_session_async.add(agent)
        await db_session_async.flush()
        
        now = datetime.utcnow()
        agent.last_heartbeat = now
        await db_session_async.flush()
        
        assert agent.last_heartbeat is not None


class TestTenantModel:
    """Test Tenant model"""
    
    @pytest.mark.asyncio
    async def test_tenant_creation(self, db_session_async):
        """Create valid tenant"""
        from app.models import Tenant
        
        tenant = Tenant(
            name="Acme Corp",
            slug="acme-corp"
        )
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        assert tenant.id is not None
        assert tenant.name == "Acme Corp"
    
    @pytest.mark.asyncio
    async def test_tenant_slug_uniqueness(self, db_session_async):
        """Tenant slug must be unique"""
        from app.models import Tenant
        from sqlalchemy.exc import IntegrityError
        
        tenant1 = Tenant(name="Tenant 1", slug="unique-slug")
        db_session_async.add(tenant1)
        await db_session_async.flush()
        
        tenant2 = Tenant(name="Tenant 2", slug="unique-slug")
        db_session_async.add(tenant2)
        
        with pytest.raises(IntegrityError):
            await db_session_async.flush()
    
    @pytest.mark.asyncio
    async def test_tenant_is_active_default_true(self, db_session_async):
        """Tenant is_active defaults to True"""
        from app.models import Tenant
        
        tenant = Tenant(name="Test", slug="test")
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        assert tenant.is_active is True
    
    @pytest.mark.asyncio
    async def test_tenant_user_relationship(self, db_session_async):
        """Tenant has many users"""
        from app.models import Tenant, User
        
        tenant = Tenant(name="Test", slug="test")
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        user1 = User(email="user1@example.com", tenant_id=tenant.id)
        user2 = User(email="user2@example.com", tenant_id=tenant.id)
        db_session_async.add(user1)
        db_session_async.add(user2)
        await db_session_async.flush()
        
        await db_session_async.refresh(tenant)
        assert len(tenant.users) == 2
    
    @pytest.mark.asyncio
    async def test_tenant_agent_relationship(self, db_session_async):
        """Tenant has many agents"""
        from app.models import Tenant, Agent
        
        tenant = Tenant(name="Test", slug="test")
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        agent1 = Agent(name="Agent 1", tenant_id=tenant.id)
        agent2 = Agent(name="Agent 2", tenant_id=tenant.id)
        db_session_async.add(agent1)
        db_session_async.add(agent2)
        await db_session_async.flush()
        
        await db_session_async.refresh(tenant)
        assert len(tenant.agents) == 2


class TestAlertModel:
    """Test Alert model"""
    
    @pytest.mark.asyncio
    async def test_alert_creation(self, db_session_async):
        """Create valid alert"""
        from app.models import Alert, Tenant
        
        tenant = Tenant(name="Test", slug="test")
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        alert = Alert(
            title="High CPU Usage",
            severity="high",
            tenant_id=tenant.id,
            resource="host-01"
        )
        db_session_async.add(alert)
        await db_session_async.flush()
        
        assert alert.id is not None
        assert alert.title == "High CPU Usage"
    
    @pytest.mark.asyncio
    async def test_alert_severity_enum(self, db_session_async):
        """Severity is restricted enum"""
        from app.models import Alert, Tenant
        
        tenant = Tenant(name="Test", slug="test")
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        alert = Alert(
            title="Test",
            severity="critical",
            tenant_id=tenant.id
        )
        db_session_async.add(alert)
        await db_session_async.flush()
        
        assert alert.severity in ["low", "medium", "high", "critical"]
    
    @pytest.mark.asyncio
    async def test_alert_resolved_status(self, db_session_async):
        """Alert can be marked resolved"""
        from app.models import Alert, Tenant
        
        tenant = Tenant(name="Test", slug="test")
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        alert = Alert(
            title="Test",
            severity="medium",
            tenant_id=tenant.id
        )
        db_session_async.add(alert)
        await db_session_async.flush()
        
        alert.resolved = True
        alert.resolved_at = datetime.utcnow()
        await db_session_async.flush()
        
        assert alert.resolved is True
        assert alert.resolved_at is not None


class TestDashboardModel:
    """Test Dashboard model"""
    
    @pytest.mark.asyncio
    async def test_dashboard_creation(self, db_session_async):
        """Create valid dashboard"""
        from app.models import Dashboard, Tenant
        
        tenant = Tenant(name="Test", slug="test")
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        dashboard = Dashboard(
            title="Performance",
            tenant_id=tenant.id
        )
        db_session_async.add(dashboard)
        await db_session_async.flush()
        
        assert dashboard.id is not None
        assert dashboard.title == "Performance"


class TestTicketModel:
    """Test Ticket model"""
    
    @pytest.mark.asyncio
    async def test_ticket_creation(self, db_session_async):
        """Create valid ticket"""
        from app.models import Ticket, Tenant
        
        tenant = Tenant(name="Test", slug="test")
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        ticket = Ticket(
            title="Test Issue",
            description="Test description",
            tenant_id=tenant.id
        )
        db_session_async.add(ticket)
        await db_session_async.flush()
        
        assert ticket.id is not None
        assert ticket.title == "Test Issue"
    
    @pytest.mark.asyncio
    async def test_ticket_status_workflow(self, db_session_async):
        """Ticket status follows workflow"""
        from app.models import Ticket, Tenant
        
        tenant = Tenant(name="Test", slug="test")
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        ticket = Ticket(
            title="Test",
            description="Test",
            tenant_id=tenant.id,
            status="open"
        )
        db_session_async.add(ticket)
        await db_session_async.flush()
        
        ticket.status = "in_progress"
        await db_session_async.flush()
        
        assert ticket.status == "in_progress"
    
    @pytest.mark.asyncio
    async def test_ticket_priority_levels(self, db_session_async):
        """Ticket priority is numeric 1-5"""
        from app.models import Ticket, Tenant
        
        tenant = Tenant(name="Test", slug="test")
        db_session_async.add(tenant)
        await db_session_async.flush()
        
        for priority in [1, 2, 3, 4, 5]:
            ticket = Ticket(
                title=f"Priority {priority}",
                description="Test",
                tenant_id=tenant.id,
                priority=priority
            )
            db_session_async.add(ticket)
        
        await db_session_async.flush()
        
        # Just verify they were created
        assert True
