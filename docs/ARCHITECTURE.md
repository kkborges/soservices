# 🏗️ ARCHITECTURE.md

**Status**: Living Document  
**Last Updated**: Abril 16, 2026  
**Version**: 3.0.0

---

## 📊 System Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         USER / CLIENT LAYER                       │
│                  Web Browser | Mobile App | API Clients           │
└────────────────────┬─────────────────────────────────────────────┘
                     │ HTTPS / gRPC
                     ▼
┌──────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                        │
│                                                                   │
│  ┌──────────────────┐              ┌──────────────────┐         │
│  │  Frontend (SPA)  │              │  API Gateway     │         │
│  │  - Vue 3         │              │  - mTLS Proxy    │         │
│  │  - Vite Build    │              │  - Rate Limiting │         │
│  │  - Static Assets │              │  - Logging       │         │
│  └────────┬─────────┘              └────────┬─────────┘         │
└───────────┼──────────────────────────────────┼───────────────────┘
            │ HTTP                            │ HTTP/mTLS
            ▼                                  ▼
┌──────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER (FastAPI)                 │
│                                                                   │
│  Middleware:                                                      │
│  ├─ CORS Protection                                              │
│  ├─ Request ID Tracking                                          │
│  ├─ Authentication (JWT)                                         │
│  ├─ Multi-tenant Isolation                                       │
│  └─ mTLS Verification (guard)                                    │
│                                                                   │
│  Routers (v1):                                                    │
│  ├─ /api/v1/auth       (Authentication & tokens)                │
│  ├─ /api/v1/agents     (Agent management)                       │
│  ├─ /api/v1/gateways   (Gateway cluster)                        │
│  ├─ /api/v1/ingest     (Log/trace/metric ingestion)            │
│  ├─ /api/v1/management (CRUD resources)                        │
│  ├─ /api/v1/alerts     (Alert rules & incidents)               │
│  ├─ /api/v1/tickets    (Support tickets)                       │
│  └─ /api/v1/analytics  (Data analysis)                         │
│                                                                   │
└────────────┬──────────────────────────────────────────┬──────────┘
             │                                          │
    ┌────────▼─────────┐                      ┌─────────▼─────────┐
    │  SERVICE LAYER   │                      │  WORKER LAYER     │
    │  (Business Logic)│                      │  (Background Jobs)│
    │                  │                      │                   │
    │ ├ auth_service   │                      │ ├ notification    │
    │ ├ agent_service  │                      │ ├ email_sender    │
    │ ├ gateway_service│                      │ ├ data_aggregator │
    │ ├ alert_service  │                      │ └─ ai_analyzer    │
    │ ├ ticket_service │├─────┐              │                   │
    │ ├ mtls_service   ││msg queue            └─────────┬─────────┘
    │ ├ cache_service  │├─────┘                         │
    │ └ ai_service     │         ┌──────────────────────┘
    │                  │         │
    │ Depends on:      │         ▼
    │ └─ Models (ORM)  │    ┌──────────────┐
    └────────┬─────────┘    │  Celery      │
             │               │  + Redis     │
             ▼               └──────────────┘
    ┌──────────────────────────────────────┐
    │         DATA ACCESS LAYER (DAL)      │
    │  ├─ SQLAlchemy ORM                   │
    │  ├─ Async operations                 │
    │  └─ Transaction management           │
    └────────┬──────────────────┬──────────┘
             │                  │
    ┌────────▼────────┐  ┌──────▼────────┐
    │  PostgreSQL 16  │  │  Redis 7      │
    │  ├─ Users       │  │  ├─ Sessions  │
    │  ├─ Agents      │  │  ├─ Cache     │
    │  ├─ Logs        │  │  ├─ Celery    │
    │  ├─ Metrics     │  │  │   Broker   │
    │  ├─ Traces      │  │  └─ Pub/Sub   │
    │  └─ Alerts      │  │               │
    └─────────────────┘  └───────────────┘
```

---

## 🎯 Core Principles

### 1. Multi-Layered Architecture
- **Separation of Concerns**: Each layer has specific responsibility
- **Dependency Injection**: Loose coupling between layers
- **Middleware Pipeline**: Cross-cutting concerns handled uniformly

### 2. Asynchronous-First Design
- All I/O operations are async (DB, Redis, HTTP)
- Non-blocking request handling
- FastAPI + Uvicorn for performance

### 3. Multi-Tenant Isolation
- Strict tenant_id enforcement in all queries
- SQL constraints at database level
- Token-based tenant identification

### 4. Enterprise Security
- mTLS between agents/gateways and API
- JWT tokens with rotation
- Role-Based Access Control (RBAC)
- Audit logging of sensitive operations

### 5. Event-Driven Architecture
- Celery for background tasks
- Redis Pub/Sub for real-time notifications
- WebSocket for live updates (future)

---

## 📦 Detailed Layer Breakdown

### PRESENTATION LAYER

#### Frontend (SPA - Single Page Application)
```
frontend/
├── public/
│   └── index.html (Single entry point)
├── src/
│   ├── components/    # Reusable Vue components
│   ├── pages/        # Page-level components
│   ├── store/        # State management (Vuex/Pinia)
│   ├── utils/        # Helper functions
│   ├── assets/       # Static files
│   └── App.vue       # Root component
├── vite.config.ts    # Vite build tool config
└── package.json      # NPM dependencies
```

**Technology:**
- Vue 3 (Composition API)
- TypeScript
- Vite (fast build tool)
- HTTP client for API calls

**Key Features:**
- Responsive design
- Real-time updates (WebSocket)
- Tenant-aware UI
- Role-based navigation

---

### GATEWAY LAYER

#### Nginx API Gateway
```
docker/
├── nginx.conf      # Production config
├── nginx-ha.conf   # HA load balancer
└── nginx-mtls.conf # mTLS proxy
```

**Responsibilities:**
- HTTP to HTTPS redirect
- TLS termination
- Load balancing (round-robin, least_conn)
- Rate limiting per IP
- Request logging
- Header validation
- mTLS certificate verification

**Key Routes:**
```nginx
# Non-secured endpoints
location /api/health { ... }
location /api/v1/agents/bootstrap { ... }

# Secured endpoints (mTLS)
location /api/v1 {
    if ($ssl_client_verify != SUCCESS) {
        return 496;  # Invalid client certificate
    }
    proxy_pass http://las-api;
}
```

---

### APPLICATION LAYER

#### FastAPI Main Application
```python
# app/main.py
@app.on_event("startup")
async def startup():
    """Initialize connections, load config"""
    
@app.on_event("shutdown")
async def shutdown():
    """Cleanup resources"""

app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(agents_router, prefix="/api/v1/agents")
# ... more routers
```

#### Middleware Stack
```python
# Request pipeline (in order)
1. CORS middleware           # Cross-origin requests
2. GZip middleware           # Compression
3. Request ID middleware     # Tracking
4. Authentication middleware # Extract token
5. Multi-tenant middleware   # Set tenant context
6. Rate limit middleware     # Throttling
7. mTLS guard               # Certificate validation
8. Error handler            # Exception handling
```

#### Router Structure
```
api/v1/
├── __init__.py (router aggregator)
└── endpoints/
    ├── auth.py        # POST /login, /refresh, /logout
    ├── agents.py      # CRUD agents
    ├── gateways.py    # Gateway management
    ├── ingest.py      # Data ingestion endpoints
    ├── management.py  # Resource management
    ├── alerts.py      # Alert rules
    ├── tickets.py     # Support tickets
    └── analytics.py   # Data analysis

# Route example:
@auth_router.post("/login")
async def login(
    credentials: LoginSchema,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate user and return JWT tokens"""
```

---

### SERVICE LAYER

#### Business Logic Services
```
services/
├── auth_service.py         # Auth logic (hashing, tokens)
├── agent_service.py        # Agent bootstrap, registration
├── gateway_service.py      # Gateway routing, discovery
├── alert_service.py        # Alert rule evaluation
├── ticket_service.py       # Ticket lifecycle
├── mtls_service.py         # mTLS certificate generation
├── cache_service.py        # Redis caching
├── ai_service.py           # LLM integrations
├── runtime_monitor.py      # Instance metrics
└── seed_service.py         # Database initialization
```

**Pattern:**
```python
class AgentService:
    def __init__(self, db: AsyncSession, cache: RedisClient):
        self.db = db
        self.cache = cache
    
    async def create_agent(
        self,
        agent_data: CreateAgentSchema,
        tenant_id: str,
    ) -> Agent:
        """Create agent with validation and caching"""
        # Business logic here
        pass
```

**Characteristics:**
- Stateless (thread-safe)
- Dependency injection
- Error handling
- Logging
- Caching strategy

---

### DATA ACCESS LAYER

#### SQLAlchemy ORM Models
```python
# models/agent.py
class Agent(Base):
    __tablename__ = "agents"
    
    id: str = Column(String(36), primary_key=True)
    tenant_id: str = Column(String(36), ForeignKey("tenants.id"))
    name: str = Column(String(255), index=True)
    hostname: str = Column(String(255))
    status: str = Column(String(20), default="offline")
    
    # Relationships
    tenant = relationship("Tenant", back_populates="agents")
    
    # Indexes for performance
    __table_args__ = (
        UniqueConstraint("tenant_id", "name"),
        Index("agents_tenant_status", "tenant_id", "status"),
    )
```

**Key Tables:**
- `users` - User accounts
- `tenants` - Multi-tenant isolation
- `agents` - Monitored agents
- `hosts` - Physical/virtual hosts
- `services` - Applications
- `logs` - Log events
- `metrics` - Time-series data
- `alerts` - Alert rules
- `incidents` - Active incidents
- `tickets` - Support tickets

#### Query Patterns
```python
# Async query pattern
results = await db.execute(
    select(Agent)
    .where(Agent.tenant_id == tenant_id)
    .where(Agent.status == "online")
    .order_by(Agent.created_at.desc())
    .limit(100)
)
agents = results.scalars().all()
```

---

### WORKER LAYER

#### Celery Background Tasks
```
workers/
├── tasks.py           # Task definitions
├── alerts.py          # Alert evaluation
├── notifications.py   # Email/Slack
├── data_pipeline.py   # Aggregation
└── ai_analysis.py     # LLM calls
```

**Task Examples:**
```python
@app.task(bind=True, retry_limit=3)
async def analyze_logs_async(self, tenant_id: str, log_ids: list[str]):
    """Background task: analyze logs with AI"""
    try:
        # Process logs
        pass
    except Exception as exc:
        # Retry exponential backoff
        raise self.retry(exc=exc, countdown=60)
```

**Queue Structure:**
```python
# Celery configuration
CELERY_ROUTES = {
    'tasks.notifications.*': {'queue': 'notifications'},
    'tasks.analyses.*': {'queue': 'long_running'},
    'tasks.realtime.*': {'queue': 'high_priority'},
}

# Priority:
# high_priority -> long_running -> default -> notifications
```

---

### DATABASE LAYER

#### PostgreSQL Schema
```sql
-- Multi-tenant design
CREATE TABLE tenants (
    id VARCHAR(36) PRIMARY KEY,
    slug VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    tier VARCHAR(20),  -- free, pro, enterprise
    created_at TIMESTAMP DEFAULT NOW()
);

-- Agent records with tenant isolation
CREATE TABLE agents (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    status VARCHAR(20),
    UNIQUE(tenant_id, name),  -- Tenant-scoped uniqueness
    created_at TIMESTAMP DEFAULT NOW()
);

-- Log events
CREATE TABLE logs (
    id BIGSERIAL PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(id),
    agent_id VARCHAR(36) REFERENCES agents(id),
    level VARCHAR(20),
    message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
-- Index for performance
CREATE INDEX logs_tenant_created ON logs(tenant_id, created_at DESC);
```

**Design Principles:**
- Tenant ID on every table (for partition)
- Timestamps on all records
- Indexes on common queries
- Foreign keys for referential integrity
- Composite unique constraints for multi-tenant safety

---

### CACHE LAYER

#### Redis Usage Patterns
```python
# Session storage
redis.set(f"session:{session_id}", user_data, ex=1800)

# Real-time metrics
redis.hset(f"metrics:{host_id}", mapping={
    "cpu": 45.2,
    "memory": 62.1,
    "disk": 78.5,
})

# Pub/Sub for notifications
redis.publish(f"alerts:{tenant_id}", alert_message)

# Celery task broker
# (Handled by Celery automatically)
```

**TTL Strategy:**
- Session data: 30 minutes
- Metrics cache: 5 minutes
- User permissions: 1 hour
- Search results: 10 minutes

---

## 🔄 Request Flow Example

**Scenario: User requests to list agents**

```
1. User clicks "Agents" in frontend
   → GET /api/v1/agents
   
2. Request hits Nginx gateway
   → Nginx validates mTLS (if required)
   → Routes to FastAPI backend
   → Adds security headers
   
3. FastAPI middleware chain
   → CORS check ✓
   → Request ID generated: "abc123"
   → JWT token parsed
   → tenant_id extracted: "tenant-456"
   → Multi-tenant context set
   
4. Route handler called
   agents_service.list_agents(
       tenant_id="tenant-456",
       skip=0,
       limit=10,
   )
   
5. Service layer
   → Check cache for "agents:tenant-456:0:10"
   → If missed, query database
   
6. Database query
   SELECT * FROM agents 
   WHERE tenant_id = 'tenant-456'
   LIMIT 10
   
7. Results cached (5 min TTL)
8. Transform to response schema
9. Add response headers (X-Request-ID, etc)
10. Return JSON to frontend

Response time: ~50ms
```

---

## 🔒 Security Architecture

### Authentication Flow
```
┌─────────────┐
│ Client      │
└──────┬──────┘
       │ POST /api/v1/auth/login
       │ {email, password}
       ▼
┌──────────────────────────┐
│ Auth Service             │
│ ├─ Hash password         │
│ ├─ Verify against DB     │
│ ├─ Generate JWT (HS256)  │
│ └─ Store refresh token   │
└──────┬───────────────────┘
       │ Return {access_token, refresh_token}
       ▼
┌─────────────┐
│ Client      │ Stores tokens in localStorage
└─────────────┘

Subsequent Requests:
┌─────────────┐
│ Client      │ Authorization: Bearer {access_token}
└──────┬──────┘
       │
       ▼
┌──────────────────────────┐
│ JWT Verification (Middleware)
│ ├─ Verify signature
│ ├─ Check expiration
│ ├─ Extract claims (sub, tenant_id)
│ └─ Attach to request context
└──────┬───────────────────┘
       │
       ▼
Router Handler (authenticated)
```

### mTLS Flow
```
Agent generates CSR
     ↓
Requests cert from /api/agents/bootstrap/mtls (HTTP)
     ↓
API generates cert + CA
     ↓
Agent stores locally (/var/run/las/cert.pem)
     ↓
Subsequent connections use mTLS (port 8443)
     ↓
Nginx validates client cert
     ↓
API verifies subject DN
     ↓
Authorized request proceeds
```

---

## 📊 Data Flow Patterns

### 1. Real-Time Metrics

```
Agent (system metrics)
    → Sends to Gateway
    → Gateway aggregates
    → Sends to API /api/v1/ingest/metrics
    → Stored in PostgreSQL
    → Cached in Redis
    → Frontend polls /api/v1/metrics (cached)
    → UI updates
```

### 2. Log Ingestion

```
Application Logs
    → Syslog / HTTP
    → Gateway receiver
    → API /api/v1/ingest/logs
    → Async processing (Celery)
    → Stored in PostgreSQL
    → Indexed for search
    → Real-time UI streaming (WebSocket)
```

### 3. Alert Flow

```
Scheduled Task (every minute)
    → Check Alert Rules
    → Query metrics
    → Evaluate condition
    → If triggered:
        → Create Incident
        → Send notification (Celery task)
        → Update dashboard
        → Create ticket (if escalated)
```

---

## ⚡ Performance Optimizations

### 1. Database Query Optimization
- Indexes on tenant_id, created_at
- N+1 query prevention via eager loading
- Connection pooling (AsyncPG)
- Query result caching

### 2. Caching Strategy
- Redis cache layer
- Cache-aside pattern
- TTL-based expiration
- Cache invalidation on updates

### 3. Asynchronous Processing
- Non-blocking I/O
- Background tasks via Celery
- Batch processing for bulk operations

### 4. Code Optimization
- Connection reuse
- Lazy loading where appropriate
- Pagination with limits
- Search result limits

---

## 🔧 Technology Stack Summary

| Layer | Technology | Justification |
|-------|-----------|--------------|
| Web Server | Nginx | Performance, scalability, mTLS |
| Application | FastAPI | Modern, async, performance |
| Database | PostgreSQL | Reliability, ACID, features |
| Cache | Redis | Speed, pub/sub, session storage |
| Async Worker | Celery | Background jobs, scheduling |
| ORM | SQLAlchemy 2.0 | Async support, clean API |
| Frontend | Vue 3 | Reactive, component-based |
| Build | Vite | Fast dev server, optimized builds |
| Monitoring | OpenTelemetry | Vendor-neutral, comprehensive |
| Cloud | Multi-cloud | Provider-agnostic |

---

## 🚀 Scalability Considerations

### Horizontal Scaling
- Stateless API servers
- Shared database
- Redis cluster
- Load balancer (Nginx)

### Vertical Scaling
- Async-first design
- Connection pooling
- Query optimization
- Caching strategy

### Data Scaling
- Time-series partitioning
- Archive old data
- Search index optimization
- Data retention policies

---

## 📋 Architecture Decision Records (ADRs)

### ADR-001: Async-First Design
**Decision:** All I/O operations use async/await  
**Rationale:** Better throughput, non-blocking, leverages FastAPI  
**Consequences:** Requires async libraries, more complex debugging

### ADR-002: Multi-Tenant at Database Level
**Decision:** tenant_id on every table, SQL constraints  
**Rationale:** Data isolation, compliance, performance  
**Consequences:** Cannot share data across tenants, migration complexity

### ADR-003: Service Layer Pattern
**Decision:** Business logic in services, not endpoints  
**Rationale:** Reusability, testability, separation of concerns  
**Consequences:** Extra layer of abstraction

---

## 🎓 Key Concepts

### Multi-Tenancy
- Complete data isolation
- Per-tenant rate limits
- Per-tenant features
- Separate billing

### Circuit Breaker Pattern
- External service failures don't cascade
- Timeout on failed services
- Auto-recovery attempts

### Bulkhead Pattern
- Dedicated resources per critical function
- Queue limits per priority
- Resource isolation

---

## 📖 Documentation Links

- [CONTRIBUTING.md](CONTRIBUTING.md) - Development guidelines
- [TESTING_GUIDE.md](tests/TESTING_GUIDE.md) - Test strategies
- [DEVELOPMENT.md](docs/DEVELOPMENT.md) - Local setup
- [DEPLOYMENT.md](docs/DEPLOYMENT-CLIENTE.md) - Production deployment

---

**Architecture maintained by: Core Team**  
**Last reviewed: Abril 16, 2026**
