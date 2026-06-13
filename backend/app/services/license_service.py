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
        "modules": ["agent_proxy", "otel", "traces", "rum", "ids", "logs", "network_discovery", "snmp"],
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

LICENSE_BILLING_UNIT_CATALOG: dict[str, dict] = {
    "hosts_infra_hours": {
        "label": "Host hora - Infra",
        "description": "Monitoramento de infraestrutura, processos, servicos e logs sem OTel/RUM.",
        "category": "hosts",
        "unit_label": "host-hora",
        "default_price": 0.12,
        "default_included": 0,
    },
    "hosts_full_hours": {
        "label": "Host hora - Completo",
        "description": "Monitoramento completo com OTel, traces e recursos de observabilidade.",
        "category": "hosts",
        "unit_label": "host-hora",
        "default_price": 0.25,
        "default_included": 0,
    },
    "logs_gb": {
        "label": "Logs por volume",
        "description": "Volume de logs ingeridos/armazenados em GB.",
        "category": "logs",
        "unit_label": "GB",
        "default_price": 2.50,
        "default_included": 5,
    },
    "snmp_devices": {
        "label": "Ativos SNMP monitorados",
        "description": "Dispositivos monitorados com coleta SNMP ativa.",
        "category": "network",
        "unit_label": "dispositivo",
        "default_price": 6.00,
        "default_included": 0,
    },
    "discovered_devices": {
        "label": "Ativos somente discovery",
        "description": "Dispositivos descobertos/atualizados via scan sem coleta SNMP ativa.",
        "category": "network",
        "unit_label": "dispositivo",
        "default_price": 1.50,
        "default_included": 0,
    },
    "security_units": {
        "label": "Unidades de seguranca",
        "description": "Pool comercial para IDS, vulnerabilidades, pentest e eventos de seguranca.",
        "category": "security",
        "unit_label": "unidade",
        "default_price": 8.00,
        "default_included": 0,
    },
    "vulnerability_host_scans": {
        "label": "Scan vulnerabilidade host",
        "description": "Execucoes/licencas de scan de vulnerabilidade de host.",
        "category": "security",
        "unit_label": "scan",
        "default_price": 1.20,
        "default_included": 0,
    },
    "vulnerability_app_scans": {
        "label": "Scan vulnerabilidade app",
        "description": "Execucoes/licencas de scan de vulnerabilidade de aplicacao/servico.",
        "category": "security",
        "unit_label": "scan",
        "default_price": 2.40,
        "default_included": 0,
    },
    "pentest_units": {
        "label": "Pentest",
        "description": "Execucoes/licencas de testes de pentest automatizados ou sob demanda.",
        "category": "security",
        "unit_label": "execucao",
        "default_price": 15.00,
        "default_included": 0,
    },
    "observability_units": {
        "label": "Unidades de observabilidade",
        "description": "Pool para traces, spans, RUM e correlacao avancada.",
        "category": "observability",
        "unit_label": "unidade",
        "default_price": 4.00,
        "default_included": 0,
    },
    "integration_metric_units": {
        "label": "Metricas customizadas / integracoes",
        "description": "Unidades derivadas de metricas customizadas coletadas por extensoes/plugins.",
        "category": "integrations",
        "unit_label": "unidade",
        "default_price": 3.00,
        "default_included": 0,
    },
}

LICENSE_PACKAGE_CATALOG: dict[str, dict] = {
    "infra_essentials": {
        "label": "Infra Essentials",
        "description": "Pacote base para hosts infra, logs e discovery.",
        "category": "bundle",
        "default_enabled": True,
        "default_price": 499.00,
        "default_discount_percent": 0.0,
        "included_units": {
            "hosts_infra_hours": 720,
            "logs_gb": 20,
            "discovered_devices": 50,
        },
    },
    "observability_suite": {
        "label": "Observability Suite",
        "description": "Pacote para hosts full, traces, RUM e integracoes.",
        "category": "bundle",
        "default_enabled": True,
        "default_price": 1490.00,
        "default_discount_percent": 12.0,
        "included_units": {
            "hosts_full_hours": 720,
            "logs_gb": 50,
            "observability_units": 250,
            "integration_metric_units": 100,
        },
    },
    "security_operations": {
        "label": "Security Operations",
        "description": "Pacote comercial para IDS, vulnerabilidades, pentest e SNMP.",
        "category": "bundle",
        "default_enabled": True,
        "default_price": 990.00,
        "default_discount_percent": 10.0,
        "included_units": {
            "security_units": 200,
            "vulnerability_host_scans": 100,
            "pentest_units": 5,
            "snmp_devices": 30,
        },
    },
}

DEFAULT_BILLING_DISCOUNTS: dict[str, float] = {
    "internal_percent": 100.0,
    "trial_percent": 100.0,
    "starter_percent": 0.0,
    "professional_percent": 5.0,
    "enterprise_percent": 10.0,
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


def default_billing_config() -> dict:
    return {
        "currency": "BRL",
        "billing_cycle": "monthly",
        "notes": "",
        "units": {
            code: {
                "enabled": True,
                "price_per_unit": spec["default_price"],
                "included_units": spec["default_included"],
                "overage_price": spec["default_price"],
                "unit_label": spec["unit_label"],
                "notes": "",
            }
            for code, spec in LICENSE_BILLING_UNIT_CATALOG.items()
        },
        "packages": {
            code: {
                "enabled": bool(spec.get("default_enabled", True)),
                "label": spec["label"],
                "description": spec["description"],
                "base_price": float(spec["default_price"]),
                "discount_percent": float(spec.get("default_discount_percent", 0.0)),
                "notes": "",
                "included_units": {
                    unit_code: float(value or 0)
                    for unit_code, value in (spec.get("included_units") or {}).items()
                    if unit_code in LICENSE_BILLING_UNIT_CATALOG
                },
            }
            for code, spec in LICENSE_PACKAGE_CATALOG.items()
        },
        "discounts": dict(DEFAULT_BILLING_DISCOUNTS),
    }


def merge_billing_config(config: dict | None) -> dict:
    merged = default_billing_config()
    incoming = config or {}
    if isinstance(incoming.get("currency"), str) and incoming["currency"].strip():
        merged["currency"] = incoming["currency"].strip().upper()
    if isinstance(incoming.get("billing_cycle"), str) and incoming["billing_cycle"].strip():
        merged["billing_cycle"] = incoming["billing_cycle"].strip().lower()
    if isinstance(incoming.get("notes"), str):
        merged["notes"] = incoming["notes"]
    units = incoming.get("units") if isinstance(incoming.get("units"), dict) else {}
    for code, spec in LICENSE_BILLING_UNIT_CATALOG.items():
        current = merged["units"][code]
        raw = units.get(code) if isinstance(units.get(code), dict) else {}
        current["enabled"] = bool(raw.get("enabled", current["enabled"]))
        current["price_per_unit"] = float(raw.get("price_per_unit", current["price_per_unit"]) or 0)
        current["included_units"] = float(raw.get("included_units", current["included_units"]) or 0)
        current["overage_price"] = float(raw.get("overage_price", current["overage_price"]) or 0)
        current["unit_label"] = str(raw.get("unit_label", spec["unit_label"]) or spec["unit_label"])
        current["notes"] = str(raw.get("notes", current.get("notes", "")) or "")
    packages = incoming.get("packages") if isinstance(incoming.get("packages"), dict) else {}
    for code, spec in LICENSE_PACKAGE_CATALOG.items():
        current = merged["packages"][code]
        raw = packages.get(code) if isinstance(packages.get(code), dict) else {}
        current["enabled"] = bool(raw.get("enabled", current["enabled"]))
        current["label"] = str(raw.get("label", current["label"]) or current["label"])
        current["description"] = str(raw.get("description", current["description"]) or current["description"])
        current["base_price"] = float(raw.get("base_price", current["base_price"]) or 0)
        current["discount_percent"] = float(raw.get("discount_percent", current["discount_percent"]) or 0)
        current["notes"] = str(raw.get("notes", current.get("notes", "")) or "")
        raw_included = raw.get("included_units") if isinstance(raw.get("included_units"), dict) else {}
        current["included_units"] = {
            unit_code: float(raw_included.get(unit_code, current["included_units"].get(unit_code, 0)) or 0)
            for unit_code in LICENSE_BILLING_UNIT_CATALOG
            if unit_code in current["included_units"] or unit_code in raw_included
        }
    discounts = incoming.get("discounts") if isinstance(incoming.get("discounts"), dict) else {}
    for key, default_value in DEFAULT_BILLING_DISCOUNTS.items():
        merged["discounts"][key] = float(discounts.get(key, default_value) or 0)
    return merged


def _round_money(value: float) -> float:
    return round(float(value or 0), 2)


def _discount_percent_for_plan(plan: str, config: dict, internal: bool = False) -> float:
    discounts = config.get("discounts") if isinstance(config.get("discounts"), dict) else {}
    normalized_plan = str(plan or "enterprise").replace("PlanType.", "").strip().lower()
    if internal:
        return float(discounts.get("internal_percent", DEFAULT_BILLING_DISCOUNTS["internal_percent"]) or 0)
    key = f"{normalized_plan}_percent"
    return float(discounts.get(key, 0) or 0)


def simulate_billing(
    consumption_units: dict | None,
    config: dict | None,
    *,
    plan: str = "enterprise",
    internal: bool = False,
    assigned_package: str | None = None,
) -> dict:
    merged = merge_billing_config(config)
    usage = {
        code: float((consumption_units or {}).get(code, 0) or 0)
        for code in LICENSE_BILLING_UNIT_CATALOG
    }
    plan_discount_percent = _discount_percent_for_plan(plan, merged, internal=internal)

    payg_lines = []
    payg_subtotal = 0.0
    for code, spec in LICENSE_BILLING_UNIT_CATALOG.items():
        unit_cfg = merged["units"][code]
        qty = usage[code]
        included = float(unit_cfg.get("included_units", 0) or 0)
        billable = max(0.0, qty - included)
        price = float(unit_cfg.get("price_per_unit", 0) or 0)
        subtotal = 0.0 if not unit_cfg.get("enabled", True) else billable * price
        payg_subtotal += subtotal
        payg_lines.append(
            {
                "code": code,
                "label": spec["label"],
                "quantity": qty,
                "included_units": included,
                "billable_units": billable,
                "price_per_unit": price,
                "subtotal": _round_money(subtotal),
            }
        )
    payg_total = _round_money(payg_subtotal * max(0.0, 1 - (plan_discount_percent / 100.0)))

    package_quotes = []
    for code, package_cfg in merged["packages"].items():
        if not package_cfg.get("enabled", True):
            continue
        base_price = float(package_cfg.get("base_price", 0) or 0)
        package_discount = float(package_cfg.get("discount_percent", 0) or 0)
        included_units = package_cfg.get("included_units") if isinstance(package_cfg.get("included_units"), dict) else {}
        quote_lines = []
        subtotal = base_price
        for unit_code, spec in LICENSE_BILLING_UNIT_CATALOG.items():
            unit_cfg = merged["units"][unit_code]
            qty = usage[unit_code]
            included = float(included_units.get(unit_code, 0) or 0)
            billable = max(0.0, qty - included)
            raw_overage_price = float(unit_cfg.get("overage_price", unit_cfg.get("price_per_unit", 0)) or 0)
            effective_price = raw_overage_price * max(0.0, 1 - (package_discount / 100.0))
            line_subtotal = 0.0 if not unit_cfg.get("enabled", True) else billable * effective_price
            subtotal += line_subtotal
            quote_lines.append(
                {
                    "code": unit_code,
                    "label": spec["label"],
                    "quantity": qty,
                    "included_units": included,
                    "billable_units": billable,
                    "price_per_unit": _round_money(effective_price),
                    "subtotal": _round_money(line_subtotal),
                }
            )
        total = _round_money(subtotal * max(0.0, 1 - (plan_discount_percent / 100.0)))
        package_quotes.append(
            {
                "code": code,
                "label": package_cfg.get("label", code),
                "description": package_cfg.get("description", ""),
                "base_price": _round_money(base_price),
                "discount_percent": package_discount,
                "plan_discount_percent": plan_discount_percent,
                "total": total,
                "lines": quote_lines,
            }
        )

    package_quotes.sort(key=lambda item: (item["total"], item["label"]))
    best_option = {
        "type": "payg",
        "code": "payg",
        "label": "Pay as you go",
        "total": payg_total,
        "savings_vs_payg": 0.0,
    }
    if package_quotes and package_quotes[0]["total"] < payg_total:
        best_option = {
            "type": "package",
            "code": package_quotes[0]["code"],
            "label": package_quotes[0]["label"],
            "total": package_quotes[0]["total"],
            "savings_vs_payg": _round_money(payg_total - package_quotes[0]["total"]),
        }

    selected_option = best_option
    if assigned_package:
        selected = next((item for item in package_quotes if item["code"] == assigned_package), None)
        if selected:
            selected_option = {
                "type": "package",
                "code": selected["code"],
                "label": selected["label"],
                "total": selected["total"],
                "savings_vs_payg": _round_money(payg_total - selected["total"]),
            }

    return {
        "currency": merged["currency"],
        "billing_cycle": merged["billing_cycle"],
        "plan_discount_percent": plan_discount_percent,
        "payg_subtotal": _round_money(payg_subtotal),
        "payg_total": payg_total,
        "payg_lines": payg_lines,
        "packages": package_quotes,
        "best_option": best_option,
        "selected_option": selected_option,
    }
