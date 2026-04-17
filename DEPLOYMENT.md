# Nexus Platform v2.0 - Deployment Guide

## Overview

This guide provides complete instructions for deploying Nexus Platform v2.0 to production servers. The platform includes 9 enterprise services with comprehensive security, monitoring, and analytics capabilities.

## Prerequisites

### System Requirements
- **OS**: Windows/Linux/macOS
- **Python**: 3.12+ or 3.14+
- **Memory**: Minimum 8GB RAM, recommended 16GB+
- **Disk Space**: Minimum 50GB free space
- **Database**: PostgreSQL 13+
- **Cache**: Redis 6+
- **Network**: Stable internet connection for external API integrations

### Required Services
```bash
# PostgreSQL
postgresql-server (13+)

# Redis
redis-server (6+)

# Python Virtual Environment
python -m venv

# Optional but recommended
nginx (reverse proxy)
supervisor/systemd (process management)
```

## Installation Steps

### Step 1: Prepare the Server

```bash
# Create deployment directory
sudo mkdir -p /srv/Projetos/nexus-2.0
sudo chown $USER:$USER /srv/Projetos/nexus-2.0

# Create backup directory
sudo mkdir -p /srv/Projetos/nexus-backups
sudo chown $USER:$USER /srv/Projetos/nexus-backups

# Create logs directory
sudo mkdir -p /srv/Projetos/nexus-2.0/logs
```

### Step 2: Clone Repository

```bash
cd /srv/Projetos
git clone -b main https://github.com/your-org/nexus.git nexus-2.0
cd nexus-2.0
```

### Step 3: Run Automated Deployment

```bash
# Windows
python deploy.py

# Linux/macOS
python3 deploy.py
```

This script will:
- ✓ Create virtual environment
- ✓ Install all dependencies
- ✓ Run database migrations
- ✓ Create environment configuration
- ✓ Generate systemd service file

### Step 4: Configure Environment

Edit `/srv/Projetos/nexus-2.0/backend/.env`:

```env
# Application Settings
ENVIRONMENT=production
DEBUG=false

# Database
DATABASE_URL=postgresql+asyncpg://nexus_user:secure_password@localhost:5432/nexus

# Redis
REDIS_URL=redis://:redis_password@localhost:6379/0

# Security
SECRET_KEY=your-super-secret-key-generate-with-openssl
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# External APIs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Email Notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Observability
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
PROMETHEUS_ENABLED=true
```

### Step 5: Setup PostgreSQL Database

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE DATABASE nexus;
CREATE USER nexus_user WITH PASSWORD 'secure_password';
ALTER ROLE nexus_user SET client_encoding TO 'utf8';
ALTER ROLE nexus_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE nexus_user SET default_transaction_deferrable TO on;
ALTER ROLE nexus_user SET default_time_zone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE nexus TO nexus_user;
\q
```

### Step 6: Setup Redis (Optional but Recommended)

```bash
# Install Redis
sudo apt-get install redis-server  # Ubuntu/Debian
sudo yum install redis             # CentOS/RHEL
brew install redis                 # macOS

# Start Redis
redis-server
# Or as a service
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### Step 7: Start the Application

#### Option A: Manual Startup (Development)

```bash
cd /srv/Projetos/nexus-2.0/backend

# Activate virtual environment
source ../venv/bin/activate  # Linux/macOS
# or
..\venv\Scripts\activate  # Windows

# Run with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Or with gunicorn (production)
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 app.main:app
```

#### Option B: Systemd Service (Linux Production)

```bash
# Copy service file
sudo cp deployment-files/nexus-api.service /etc/systemd/system/

# Edit if necessary
sudo nano /etc/systemd/system/nexus-api.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable nexus-api.service
sudo systemctl start nexus-api.service

# Check status
sudo systemctl status nexus-api.service

# View logs
sudo journalctl -u nexus-api -f
```

#### Option C: Using Supervisor (Alternative)

```bash
# Install supervisor
sudo apt-get install supervisor

# Copy configuration
sudo cp deployment-files/nexus.conf /etc/supervisor/conf.d/

# Enable and start
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start nexus-api
```

### Step 8: Setup Reverse Proxy (Nginx)

```bash
# Create Nginx configuration
sudo nano /etc/nginx/sites-available/nexus

# Add configuration:
server {
    listen 80;
    server_name nexus.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

# Enable site
sudo ln -s /etc/nginx/sites-available/nexus /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Step 9: SSL/TLS Setup (Let's Encrypt)

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Generate certificate
sudo certbot certonly --nginx -d nexus.example.com

# Auto-renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

### Step 10: Verify Deployment

```bash
# Test API health
curl http://localhost:8000/health

# Check API documentation
curl http://localhost:8000/docs

# Test enterprise endpoints
curl -X POST http://localhost:8000/api/v1/enterprise/permissions/check \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "resource": "test", "action": "read"}'
```

## Monitoring & Maintenance

### View Logs

```bash
# Systemd
sudo journalctl -u nexus-api -f

# Application logs
tail -f /srv/Projetos/nexus-2.0/logs/*.log

# Specific services
grep "RBAC\|Audit\|Alert" /srv/Projetos/nexus-2.0/logs/app.log
```

### Health Checks

```bash
# API Health
curl -i http://localhost:8000/health

# Database connection
curl -i http://localhost:8000/health/db

# Cache (Redis)
curl -i http://localhost:8000/health/cache
```

### Backup Strategy

```bash
# Backup database
pg_dump -U nexus_user nexus > backup-$(date +%Y%m%d-%H%M%S).sql

# Backup application files
tar -czf nexus-backup-$(date +%Y%m%d).tar.gz /srv/Projetos/nexus-2.0

# Create automated backup script
# /usr/local/bin/nexus-backup.sh
#!/bin/bash
BACKUP_DIR="/srv/Projetos/nexus-backups"
DATE=$(date +%Y%m%d-%H%M%S)

pg_dump -U nexus_user nexus > "$BACKUP_DIR/db-backup-$DATE.sql"
tar -czf "$BACKUP_DIR/app-backup-$DATE.tar.gz" /srv/Projetos/nexus-2.0

# Keep only last 30 days
find "$BACKUP_DIR" -name "*.sql" -mtime +30 -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete
```

### Database Migrations

```bash
# Run migrations
cd /srv/Projetos/nexus-2.0/backend
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "your_migration_name"

# Rollback
alembic downgrade -1
```

## Troubleshooting

### Common Issues

#### 1. Port 8000 Already in Use
```bash
# Find process using port 8000
sudo lsof -i :8000

# Kill process or change port in configuration
export API_PORT=8001
```

#### 2. Database Connection Failed
```bash
# Test PostgreSQL connection
psql -U nexus_user -d nexus -h localhost

# Check connection string in .env
# Format: postgresql+asyncpg://user:password@host:port/database
```

#### 3. Redis Connection Failed
```bash
# Test Redis connection
redis-cli ping

# Check Redis service
sudo systemctl status redis-server

# View Redis logs
sudo journalctl -u redis-server -f
```

#### 4. Import Errors
```bash
# Reinstall dependencies
cd /srv/Projetos/nexus-2.0/backend
../venv/bin/pip install -r requirements.txt

# Check Python path
which python
../venv/bin/python --version
```

## Performance Tuning

### Database Optimization

```bash
# Edit PostgreSQL configuration
sudo nano /etc/postgresql/13/main/postgresql.conf

# Recommended settings for 8GB RAM
max_connections = 200
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
work_mem = 10MB
random_page_cost = 1.1
```

### Application Optimization

```bash
# Increase gunicorn workers
gunicorn -w 8 -k uvicorn.workers.UvicornWorker app.main:app

# Enable caching headers
export REDIS_TTL=3600

# Enable connection pooling
DATABASE_URL=postgresql+asyncpg://user:pass@host/db?poolsize=20
```

## Security Hardening

```bash
# Enable firewall
sudo ufw enable
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS

# Set file permissions
sudo chmod 700 /srv/Projetos/nexus-2.0
sudo chmod 600 /srv/Projetos/nexus-2.0/backend/.env

# Create dedicated user
sudo useradd -m -s /bin/bash nexus
sudo chown -R nexus:nexus /srv/Projetos/nexus-2.0
```

## Next Steps

1. **Run Tests** - Execute comprehensive test suite
2. **Setup Monitoring** - Configure Prometheus + Grafana
3. **Configure CI/CD** - Setup GitHub Actions pipeline
4. **Create Documentation** - API and operational docs
5. **Train Team** - Onboard team members
6. **Production Launch** - Go-live procedures

## Support

For issues or questions:
- Check logs in `/srv/Projetos/nexus-2.0/logs/`
- Review documentation in `/docs/`
- Contact platform team

---

**Version**: 2.0  
**Last Updated**: April 2026  
**Maintained By**: Nexus Platform Team
