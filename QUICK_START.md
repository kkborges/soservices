# Nexus Platform v2.0 - Quick Start Deployment

## 🚀 Quick Start (5 minutes)

### Prerequisites Checklist
- [ ] Python 3.12+ installed
- [ ] PostgreSQL 13+ installed and running
- [ ] Redis 6+ installed (optional but recommended)
- [ ] Git installed
- [ ] Minimum 8GB RAM available
- [ ] 50GB disk space available

### One-Command Deployment

```bash
# Clone repository
git clone https://github.com/your-org/nexus.git
cd nexus

# Run deployment script
python deploy.py
```

The script will:
- ✅ Create virtual environment with all dependencies
- ✅ Setup database and run migrations
- ✅ Create configuration files
- ✅ Generate systemd service file (Linux)
- ✅ Provide next steps

### Manual Deployment (Step-by-Step)

```bash
# 1. Create deployment directory
mkdir -p /srv/Projetos/nexus-2.0
cd /srv/Projetos/nexus-2.0

# 2. Create Python virtual environment
python -m venv venv

# 3. Activate virtual environment
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# 4. Install dependencies
cd backend
pip install -r requirements.txt

# 5. Create environment file
cp .env.example .env
# Edit .env with your configuration

# 6. Run migrations
alembic upgrade head

# 7. Start application
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app
```

### Access the Application

Once running, access the platform at:

- **API** - http://localhost:8000
- **Documentation** - http://localhost:8000/docs
- **Health Check** - http://localhost:8000/health

### Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete production setup including:
- Nginx reverse proxy
- SSL/TLS certificates
- Systemd service configuration
- Database optimization
- Security hardening
- Monitoring setup

## 📊 What's Included

### Enterprise Services (9 Total)

1. **RBAC** - Role-based access control with granular permissions
2. **Audit Logging** - Immutable audit trails with hash chain integrity
3. **Secret Management** - Encrypted secret storage with rotation
4. **Structured Logging** - JSON formatted logs with correlation IDs
5. **Distributed Tracing** - Request tracing across services
6. **Intelligent Alerting** - Smart anomaly detection and alerts
7. **Self-Healing** - Automatic remediation with circuit breakers
8. **Disaster Recovery** - Multi-region failover capabilities
9. **Predictive Analytics** - ML-based forecasting and capacity planning

### API Endpoints

```
POST   /api/v1/enterprise/permissions/check
GET    /api/v1/enterprise/permissions/user/{user_id}
POST   /api/v1/enterprise/audit/log
GET    /api/v1/enterprise/audit/logs
POST   /api/v1/enterprise/secrets
GET    /api/v1/enterprise/secrets/{secret_key}
DELETE /api/v1/enterprise/secrets/{secret_key}
POST   /api/v1/enterprise/alerts/rules
GET    /api/v1/enterprise/alerts/anomalies
POST   /api/v1/enterprise/recovery/backup
POST   /api/v1/enterprise/recovery/failover
GET    /api/v1/enterprise/recovery/health
GET    /api/v1/enterprise/analytics/forecast/{metric_name}
... and more
```

## 🧪 Testing

### Run Test Suite

```bash
cd backend
python -m pytest ../tests/backend/integration/test_enterprise_features.py -v
```

### Expected Results
- ✅ 38 tests passing
- ✅ All 9 enterprise services operational
- ✅ API endpoints functional

## 📝 Configuration

Key configuration variables in `.env`:

```env
# Application
ENVIRONMENT=production
DEBUG=false

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/nexus

# Redis (optional)
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256

# External APIs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Monitoring
OTEL_ENABLED=true
PROMETHEUS_ENABLED=true
```

## 🔐 Security

Before going to production:

1. **Update SECRET_KEY** - Generate new secure key
2. **Enable HTTPS** - Use SSL certificates
3. **Configure Firewall** - Restrict traffic
4. **Update Credentials** - Use strong passwords
5. **Enable Audit Logging** - Monitor all activities
6. **Setup Backups** - Regular automated backups

## 📊 Monitoring

### Health Checks

```bash
# API Health
curl http://localhost:8000/health

# Database
curl http://localhost:8000/health/db

# Cache
curl http://localhost:8000/health/cache
```

### View Logs

```bash
# Application logs
tail -f /srv/Projetos/nexus-2.0/logs/app.log

# Systemd logs
sudo journalctl -u nexus-api -f

# Error logs
grep ERROR /srv/Projetos/nexus-2.0/logs/*.log
```

## 🆘 Troubleshooting

**API not responding?**
- Check logs: `tail -f logs/app.log`
- Verify port 8000 is available: `lsof -i :8000`
- Check database connection: `psql -U user -d nexus`

**Database connection error?**
- Verify PostgreSQL is running: `sudo systemctl status postgresql`
- Check connection string in `.env`
- Ensure user has database privileges

**Import errors?**
- Reinstall dependencies: `pip install -r requirements.txt`
- Verify virtual environment is activated
- Check Python version: `python --version`

## 📚 Documentation

- [DEPLOYMENT.md](DEPLOYMENT.md) - Complete deployment guide
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture
- [TESTING_GUIDE.md](docs/TESTING_GUIDE.md) - Testing patterns
- [CONTRIBUTING.md](docs/CONTRIBUTING.md) - Development guidelines

## ✅ Deployment Checklist

- [ ] Environment configured
- [ ] Database created and migrated
- [ ] Redis running (optional)
- [ ] Dependencies installed
- [ ] Application started
- [ ] Health check passing
- [ ] API documentation accessible
- [ ] Tests passing (optional)
- [ ] Logging configured
- [ ] Backups scheduled (production)

## 🎉 Next Steps

1. **Configure Credentials** - Update .env with production values
2. **Run Tests** - Ensure everything works
3. **Setup Monitoring** - Configure alerts and dashboards
4. **Deploy to Production** - Follow complete deployment guide
5. **Train Team** - Onboard users and operators

---

**Version**: 2.0.0  
**Status**: Ready for Production  
**Last Updated**: April 2026
