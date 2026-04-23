"""Tenant license and installer entitlement helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.models import Tenant


LOG_MODULE = "logs"

AGENT_MODULE_CATALOG: dict[str, dict] = {
    "infra": {"label": "Infraestrutura", "license": "infra"},
    "processes": {"label": "Processos", "license": "infra"},
    "services": {"label": "Servicos", "license": "infra"},
    "logs": {"label": "Logs", "license": "included"},
    "otel": {"label": "OpenTelemetry", "license": "complete"},
    "traces": {"label": "Traces", "license": "complete"},
    "rum": {"label": "Experiencia do usuario", "license": "user_experience"},
    "ids": {"label": "IDS no host", "license": "sec"},
    "vuln_scan": {"label": "Scan vulnerabilidade host", "license": "vulnerability_hosts"},
}

AGENT_PROFILES: dict[str, dict] = {
    "infra": {
        "label": "Infra",
        "description": "Infraestrutura, processos, servicos e logs. Sem traces/OTel/RUM.",
        "modules": ["infra", "processes", "services", "logs"],
        "license": "infra",
    },
    "complete": {
        "label": "Completa",
        "description": "Infraestrutura, processos, servicos, logs, traces, OTel e experiencia do usuario.",
        "modules": ["infra", "processes", "services", "logs", "otel", "traces", "rum"],
        "license": "complete",
    },
}

GATEWAY_TYPE_CATALOG: dict[str, dict] = {
    "agents": {
        "label": "Gateway Agents",
        "description": "Proxy e failover para agentes, OTel, traces, IDS, DEM/RUM e trafego protegido.",
        "modules": ["agent_proxy", "otel", "traces", "rum", "ids", "logs"],
        "license": "infra",
    },
    "integrations": {
        "label": "Gateway Integracoes",
        "description": "Execucao de extensoes/plugins para bancos, ITSMs, mensageria e coletores especificos.",
        "modules": ["integrations", "database", "messaging", "itsm", "webhooks"],
        "license": "integrations",
    },
    "logs": {
        "label": "Gateway de Logs",
        "description": "Recepcao e encaminhamento de syslog, logs remotos e logs de servicos do cliente.",
        "modules": ["logs", "syslog", "log_forwarding"],
        "license": "snmp_logs",
    },
    "security": {
        "label": "Gateway de Seguranca",
        "description": "Orquestracao de IDS, pentest, discovery de rede e scans licenciados.",
        "modules": ["ids", "pentest", "network_discovery", "snmp", "security_events"],
        "license": "sec",
    },
    "control": {
        "label": "Gateway de Controle (On-Prem)",
        "description": "Conecta o ambiente on-prem ao SaaS para licencas, updates, diagnosticos e auto-tickets.",
        "modules": ["control_plane", "logs"],
        "license": "infra",
    },
}

PLAN_LICENSES: dict[str, set[str]] = {
    "trial": {
        "infra",
        "complete",
        "sec",
        "user_experience",
        "network_discovery",
        "snmp_logs",
        "pentest",
        "vulnerability_hosts",
        "integrations",
    },
    "starter": {"infra", "snmp_logs"},
    "professional": {"infra", "complete", "network_discovery", "snmp_logs", "integrations"},
    "enterprise": {
        "infra",
        "complete",
        "sec",
        "user_experience",
        "network_discovery",
        "snmp_logs",
        "pentest",
        "vulnerability_hosts",
        "integrations",
    },
}


@dataclass(frozen=True)
class EntitlementResult:
    modules: list[str]
    denied: list[str]
    licenses: set[str]
    profile: str


def normalize_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip().lower().replace("-", "_") for item in value.split(",") if item.strip()]


def normalize_modules(modules: Iterable[str] | None) -> list[str]:
    seen: set[str] = set()
    resolved: list[str] = []
    for module in modules or []:
        normalized = str(module).strip().lower().replace("-", "_")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        resolved.append(normalized)
    if LOG_MODULE not in seen:
        resolved.append(LOG_MODULE)
    return resolved


def tenant_license_codes(tenant: Tenant) -> set[str]:
    features = tenant.features or {}
    settings = tenant.settings or {}
    license_cfg = settings.get("licenses") or features.get("licenses") or {}

    # Base entitlements come from the tenant plan. Explicit `licenses` config acts as an override
    # (allow-list) for customer-by-customer licensing.
    plan = str(tenant.plan or "trial").replace("PlanType.", "")
    enabled: set[str] = set(PLAN_LICENSES.get(plan, PLAN_LICENSES["trial"]))

    # Optional explicit override (typically set by platform admin).
    explicit: set[str] = set()
    if isinstance(license_cfg, dict):
        explicit.update(str(code) for code, active in license_cfg.items() if active)
    elif isinstance(license_cfg, list):
        explicit.update(str(code) for code in license_cfg)
    if explicit:
        enabled = explicit

    enabled.add("infra")
    enabled.add("included")
    if "no_user_experience" in enabled:
        enabled.discard("user_experience")
    return enabled


def profile_modules(profile: str, requested_modules: Iterable[str] | None = None) -> list[str]:
    normalized_profile = (profile or "infra").lower().replace("-", "_")
    base = AGENT_PROFILES.get(normalized_profile, AGENT_PROFILES["infra"])["modules"]
    return normalize_modules([*base, *(requested_modules or [])])


def resolve_agent_entitlements(
    tenant: Tenant,
    profile: str = "infra",
    requested_modules: Iterable[str] | None = None,
) -> EntitlementResult:
    licenses = tenant_license_codes(tenant)
    normalized_profile = (profile or "infra").lower().replace("-", "_")
    if normalized_profile not in AGENT_PROFILES:
        normalized_profile = "infra"
    modules = profile_modules(normalized_profile, requested_modules)
    denied = []
    for module in modules:
        if module not in AGENT_MODULE_CATALOG:
            denied.append(module)
            continue
        required = AGENT_MODULE_CATALOG[module].get("license", "infra")
        if required not in licenses:
            denied.append(module)
    return EntitlementResult(modules=modules, denied=denied, licenses=licenses, profile=normalized_profile)


def resolve_gateway_type(gateway_type: str) -> dict:
    normalized = (gateway_type or "agents").lower().replace("-", "_")
    if normalized not in GATEWAY_TYPE_CATALOG:
        normalized = "agents"
    return {**GATEWAY_TYPE_CATALOG[normalized], "key": normalized}


def gateway_config_for_type(gateway_type: str) -> dict:
    info = resolve_gateway_type(gateway_type)
    modules = set(info["modules"])
    return {
        "gateway_profile": info["key"],
        "gateway_label": info["label"],
        "modules": {
            "agent_proxy": "agent_proxy" in modules,
            "logs": "logs" in modules,
            "otel": "otel" in modules,
            "traces": "traces" in modules,
            "rum": "rum" in modules,
            "integrations": "integrations" in modules,
            "database": "database" in modules,
            "messaging": "messaging" in modules,
            "itsm": "itsm" in modules,
            "webhooks": "webhooks" in modules,
            "security": "security_events" in modules,
            "ids": "ids" in modules,
            "pentest": "pentest" in modules,
            "network_discovery": "network_discovery" in modules,
            "snmp": "snmp" in modules,
            "syslog": "syslog" in modules,
        },
        "syslog": {
            "enabled": "syslog" in modules,
            "listen_host": "0.0.0.0",
            "udp_port": 514,
            "tcp_port": 514,
            "tls_port": 6514,
        },
    }


def installer_options_payload(tenant: Tenant) -> dict:
    licenses = tenant_license_codes(tenant)
    return {
        "licenses": sorted(licenses),
        "agent_profiles": [
            {**value, "key": key, "allowed": value.get("license") in licenses}
            for key, value in AGENT_PROFILES.items()
        ],
        "agent_modules": [
            {**value, "key": key, "allowed": value.get("license") in licenses}
            for key, value in AGENT_MODULE_CATALOG.items()
        ],
        "gateway_types": [
            {**value, "key": key, "allowed": value.get("license") in licenses}
            for key, value in GATEWAY_TYPE_CATALOG.items()
        ],
    }
