"""Database bootstrap seed with separated platform admin and demo tenant."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Dashboard, Extension, Tenant, User
from app.services.auth_service import hash_password


async def ensure_initial_data(db: AsyncSession) -> None:
    platform_tenant_result = await db.execute(
        select(Tenant).where(Tenant.slug == settings.INITIAL_TENANT_SLUG)
    )
    platform_tenant = platform_tenant_result.scalar_one_or_none()

    platform_settings = {
        "platform_name": settings.APP_NAME,
        "company_name": "LAS",
        "platform_url": settings.PLATFORM_URL,
        "public_web_url": settings.PUBLIC_WEB_URL,
        "internal_platform": True,
        "hidden_from_customers": True,
        "theme": {
            "primary": "#ff375f",
            "secondary": "#18233a",
            "surface": "#0c1527",
        },
    }
    if not platform_tenant:
        platform_tenant = Tenant(
            name=settings.INITIAL_TENANT_NAME,
            slug=settings.INITIAL_TENANT_SLUG,
            admin_email=settings.INITIAL_ADMIN_EMAIL,
            admin_name=settings.INITIAL_ADMIN_NAME,
            plan="enterprise",
            status="active",
            max_hosts=1000,
            max_agents=1000,
            max_users=100,
            features={
                "agents": True,
                "gateways": True,
                "otel": True,
                "logs": True,
                "alerts": True,
            },
            settings=platform_settings,
        )
        db.add(platform_tenant)
        await db.flush()
    else:
        merged_platform_settings = dict(platform_tenant.settings or {})
        merged_platform_settings.update(platform_settings)
        platform_tenant.name = settings.INITIAL_TENANT_NAME
        platform_tenant.slug = settings.INITIAL_TENANT_SLUG
        platform_tenant.admin_email = settings.INITIAL_ADMIN_EMAIL
        platform_tenant.admin_name = settings.INITIAL_ADMIN_NAME
        platform_tenant.plan = "enterprise"
        platform_tenant.status = "active"
        platform_tenant.settings = merged_platform_settings

    platform_user_result = await db.execute(
        select(User).where(
            User.tenant_id == platform_tenant.id,
            User.username == settings.INITIAL_ADMIN_USERNAME,
        )
    )
    platform_users = platform_user_result.scalars().all()
    platform_user = next((item for item in platform_users if item.role == "superadmin"), None)
    if not platform_user and platform_users:
        platform_user = platform_users[0]
    if not platform_user:
        db.add(
            User(
                tenant_id=platform_tenant.id,
                username=settings.INITIAL_ADMIN_USERNAME,
                email=settings.INITIAL_ADMIN_EMAIL,
                full_name=settings.INITIAL_ADMIN_NAME,
                password_hash=hash_password(settings.INITIAL_ADMIN_PASSWORD),
                role="superadmin",
                active=True,
                must_change_password=False,
            )
        )
    else:
        platform_user.tenant_id = platform_tenant.id
        platform_user.email = settings.INITIAL_ADMIN_EMAIL
        platform_user.full_name = settings.INITIAL_ADMIN_NAME
        platform_user.role = "superadmin"
        platform_user.active = True

    demo_tenant_result = await db.execute(select(Tenant).where(Tenant.slug == settings.DEMO_TENANT_SLUG))
    demo_tenant = demo_tenant_result.scalar_one_or_none()
    if not demo_tenant:
        existing_tenants_result = await db.execute(select(Tenant).order_by(Tenant.created_at))
        for candidate in existing_tenants_result.scalars().all():
            candidate_settings = candidate.settings or {}
            if candidate.id == platform_tenant.id:
                continue
            if candidate.slug in {settings.DEMO_TENANT_SLUG, "las"} or not candidate_settings.get("internal_platform"):
                demo_tenant = candidate
                break

    demo_settings = {
        "platform_name": settings.APP_NAME,
        "company_name": "LAS",
        "platform_url": settings.PLATFORM_URL,
        "public_web_url": settings.PUBLIC_WEB_URL,
        "internal_platform": False,
        "theme": {
            "primary": "#ff375f",
            "secondary": "#18233a",
            "surface": "#0c1527",
        },
    }
    if not demo_tenant:
        demo_tenant = Tenant(
            name=settings.DEMO_TENANT_NAME,
            slug=settings.DEMO_TENANT_SLUG,
            admin_email=settings.DEMO_ADMIN_EMAIL,
            admin_name=settings.DEMO_ADMIN_NAME,
            plan="enterprise",
            status="active",
            max_hosts=1000,
            max_agents=1000,
            max_users=100,
            features={
                "agents": True,
                "gateways": True,
                "otel": True,
                "logs": True,
                "alerts": True,
                "network_discovery": True,
                "snmp": True,
            },
            settings=demo_settings,
        )
        db.add(demo_tenant)
        await db.flush()
    else:
        merged_demo_settings = dict(demo_tenant.settings or {})
        merged_demo_settings.update(demo_settings)
        demo_tenant.name = settings.DEMO_TENANT_NAME
        demo_tenant.slug = settings.DEMO_TENANT_SLUG
        demo_tenant.admin_email = settings.DEMO_ADMIN_EMAIL
        demo_tenant.admin_name = settings.DEMO_ADMIN_NAME
        demo_tenant.plan = "enterprise"
        demo_tenant.status = "active"
        demo_tenant.settings = merged_demo_settings

    demo_user_result = await db.execute(
        select(User).where(
            User.tenant_id == demo_tenant.id,
            User.username == settings.DEMO_ADMIN_USERNAME,
        )
    )
    demo_users = demo_user_result.scalars().all()
    demo_user = next((item for item in demo_users if item.role == "admin"), None)
    if not demo_user and demo_users:
        demo_user = demo_users[0]
    if not demo_user:
        db.add(
            User(
                tenant_id=demo_tenant.id,
                username=settings.DEMO_ADMIN_USERNAME,
                email=settings.DEMO_ADMIN_EMAIL,
                full_name=settings.DEMO_ADMIN_NAME,
                password_hash=hash_password(settings.DEMO_ADMIN_PASSWORD),
                role="admin",
                active=True,
                must_change_password=False,
            )
        )
    else:
        demo_user.email = settings.DEMO_ADMIN_EMAIL
        demo_user.full_name = settings.DEMO_ADMIN_NAME
        demo_user.role = "admin"
        demo_user.active = True

    dashboard_result = await db.execute(
        select(Dashboard).where(
            Dashboard.tenant_id == demo_tenant.id,
            Dashboard.name == "Visao Geral LAS",
        )
    )
    dashboard = dashboard_result.scalar_one_or_none()
    if not dashboard:
        db.add(
            Dashboard(
                tenant_id=demo_tenant.id,
                name="Visao Geral LAS",
                description="Dashboard inicial sem dados mockados.",
                icon="gauge",
                is_default=True,
                is_system=True,
                category="host",
                layout={},
            )
        )

    catalog = [
        {
            "slug": "kubernetes-monitoring",
            "name": "Kubernetes Monitoring",
            "description": "Monitoramento de cluster, pods, nodes e workloads Kubernetes.",
            "category": "integration",
            "version": "1.0.0",
            "author": "LAS",
            "metrics": ["k8s.pods.running", "k8s.nodes.ready", "k8s.restarts"],
        },
        {
            "slug": "vmware-esxi",
            "name": "VMware ESXi",
            "description": "Coleta de inventario, consumo e estado de hosts VMware ESXi.",
            "category": "integration",
            "version": "1.0.0",
            "author": "LAS",
            "metrics": ["vmware.hosts.up", "vmware.vms.running", "vmware.cpu.usage"],
        },
        {
            "slug": "teams-notifications",
            "name": "Microsoft Teams",
            "description": "Canal de notificacao via webhook do Microsoft Teams.",
            "category": "notification",
            "version": "1.0.0",
            "author": "LAS",
            "metrics": ["notifications.sent", "notifications.failed"],
        },
        {
            "slug": "webhooks-notifications",
            "name": "Webhooks",
            "description": "Canal generico de notificacoes por webhook.",
            "category": "notification",
            "version": "1.0.0",
            "author": "LAS",
            "metrics": ["notifications.sent", "notifications.failed"],
        },
        {
            "slug": "servicenow-itsm",
            "name": "ServiceNow ITSM",
            "description": "Integracao com ServiceNow para abertura e atualizacao de incidentes.",
            "category": "integration",
            "version": "1.0.0",
            "author": "LAS",
            "metrics": ["incidents.created", "incidents.updated"],
        },
    ]
    for item in catalog:
        existing_extension = await db.execute(select(Extension).where(Extension.slug == item["slug"]))
        if existing_extension.scalar_one_or_none():
            continue
        db.add(
            Extension(
                slug=item["slug"],
                name=item["name"],
                description=item["description"],
                category=item["category"],
                version=item["version"],
                author=item["author"],
                metrics=item["metrics"],
                is_official=True,
                is_active=True,
            )
        )

    await db.commit()
