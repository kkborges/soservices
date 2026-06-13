const UI_STORAGE_KEY = "las_ui_version";
const state = {
  view: "dashboard",
  currentUser: null,
  selectedHostId: null,
  hostTimeframe: "1h",
  topologyScope: "network",
  filters: {},
  ui: localStorage.getItem(UI_STORAGE_KEY) || "classic",
};

const PLATFORM_VIEWS = ["dashboard", "tenants", "licensing", "settings"];
const TENANT_VIEWS = [
  "dashboard",
  "onboarding",
  "hosts",
  "processes",
  "services",
  "applications",
  "topologies",
  "dashboards",
  "databases",
  "messaging",
  "orchestration",
  "synthetics",
  "network",
  "security",
  "vulnerabilities",
  "ids",
  "pentest",
  "incidents",
  "logs",
  "traces",
  "gateways",
  "agents",
  "tasks",
  "alerts",
  "tickets",
  "integrations",
  "users",
  "settings",
];
const titleMap = {
  dashboard: "Home",
  onboarding: "Primeiros Passos",
  hosts: "Hosts",
  processes: "Processos",
  services: "Servicos",
  applications: "Aplicacoes",
  topologies: "Topologias",
  dashboards: "Dashboards",
  databases: "Bancos de Dados",
  messaging: "Mensageria",
  orchestration: "Orquestracao",
  synthetics: "Testes Sinteticos",
  network: "Ativos de Rede",
  security: "Seguranca",
  vulnerabilities: "Vulnerabilidades",
  ids: "IDS",
  pentest: "Pentest",
  incidents: "Problemas/Incidentes",
  logs: "Logs",
  traces: "Traces",
  gateways: "Gateways",
  agents: "Agentes",
  tasks: "Tarefas",
  alerts: "Alertas",
  integrations: "Integracoes",
  tickets: "Tickets",
  users: "Usuarios",
  tenants: "Tenants",
  licensing: "Licencas",
  settings: "Configuracoes Tenant",
};
const permissionGroups = {
  applications: { label: "Usuarios aplicacoes", role: "operator" },
  databases: { label: "Usuarios bancos de dados", role: "operator" },
  security: { label: "Usuarios seguranca", role: "operator" },
  administrators: { label: "Usuarios administradores", role: "admin" },
  networks: { label: "Usuarios redes", role: "operator" },
  viewer: { label: "Somente leitura", role: "viewer" },
};
const alertEntityTypes = [
  ["host", "Host"],
  ["network_asset", "Ativo de rede"],
  ["service", "Servico"],
  ["process", "Processo"],
  ["application", "Aplicacao"],
  ["log", "Log"],
  ["synthetic", "Teste sintetico"],
  ["gateway", "Gateway"],
];
const alertMetrics = [
  ["cpu_usage", "CPU"],
  ["memory_usage", "Memoria"],
  ["disk_usage", "Disco"],
  ["net_in_rate", "Rede IN"],
  ["net_out_rate", "Rede OUT"],
  ["status", "Status"],
  ["process.cpu", "Processo CPU"],
  ["process.memory", "Processo memoria"],
  ["service.errors", "Erros de servico"],
  ["log_query.count", "Consulta em logs"],
  ["network.port.utilization", "Utilizacao de porta"],
  ["network.port.errors", "Erros de porta"],
  ["synthetic.response_ms", "Sintetico resposta"],
  ["synthetic.availability", "Sintetico disponibilidade"],
];
const defaultDiscoveryPorts = [
  21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 161, 389, 443, 445, 465, 514, 587, 636,
  993, 995, 1433, 1521, 2049, 2375, 2376, 3000, 3306, 3389, 5000, 5432, 5601, 5672,
  5900, 5985, 5986, 6379, 7001, 7002, 8000, 8080, 8081, 8161, 8443, 8500, 8888, 9000,
  9042, 9092, 9200, 9300, 9418, 9443, 10050, 11211, 15672, 27017, 27018, 27019,
];

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function isUiV2() {
  return state.ui === "v2";
}

function applyUi() {
  document.body.dataset.ui = state.ui === "v2" ? "v2" : "classic";
  $("#ui-toggle") && ($("#ui-toggle").textContent = state.ui === "v2" ? "UI: v2" : "UI: classic");
}

function closeInspector() {
  const inspector = $("#inspector");
  if (!inspector) return;
  inspector.classList.add("hidden");
  document.body.classList.remove("has-inspector");
  $("#inspector-body").innerHTML = "";
}

function openInspector({ title = "Detalhes", eyebrow = "Propriedades", body = "" } = {}) {
  const inspector = $("#inspector");
  if (!inspector) return;
  $("#inspector-title").textContent = title;
  $("#inspector-eyebrow").textContent = eyebrow;
  $("#inspector-body").innerHTML = body;
  inspector.classList.remove("hidden");
  document.body.classList.add("has-inspector");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  if (response.status === 401) {
    throw new Error("unauthorized");
  }
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (path.startsWith("/api/") && !contentType.includes("application/json")) {
    const preview = typeof payload === "string" ? payload.slice(0, 120) : "";
    throw new Error(`API retornou conteudo invalido para ${path}. Verifique proxy/edge.${preview ? ` Preview: ${preview}` : ""}`);
  }
  if (!response.ok) {
    throw new Error(formatApiError(payload));
  }
  return payload;
}

function formatApiError(payload) {
  if (typeof payload === "string") return payload;
  const detail = payload?.detail ?? payload?.message ?? payload?.error ?? payload;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      if (typeof item === "string") return item;
      const loc = Array.isArray(item?.loc) ? item.loc.join(".") : item?.loc;
      const msg = item?.msg || item?.message || JSON.stringify(item);
      return loc ? `${loc}: ${msg}` : msg;
    }).join(" | ");
  }
  if (detail && typeof detail === "object") {
    return detail.msg || detail.message || JSON.stringify(detail);
  }
  return "Erro na requisicao.";
}

const esc = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll('"', "&quot;");
const trunc = (value, max = 160) => {
  const text = String(value ?? "");
  if (text.length <= max) return text;
  return `${text.slice(0, Math.max(0, max - 3))}...`;
};
const fmt = (value) => (value ? new Date(value).toLocaleString("pt-BR") : "-");
const num = (value) => Number(value || 0).toLocaleString("pt-BR");
const money = (value, currency = "BRL") => Number(value || 0).toLocaleString("pt-BR", { style: "currency", currency });
const maybeNum = (value, suffix = "") => (value === null || value === undefined || value === "" ? "-" : `${Number(value).toLocaleString("pt-BR")}${suffix}`);
const maybeUnit = (value, unit) => (value === null || value === undefined || value === "" ? "-" : `${Number(value).toLocaleString("pt-BR")} ${unit}`);
const status = (value) => {
  const text = String(value || "offline").toLowerCase();
  const css =
    text.includes("online") || text === "ok" || text === "completed" || text === "active"
      ? "online"
      : text.includes("warn") || text.includes("pending") || text.includes("triaged")
        ? "warning"
        : text.includes("error") || text.includes("failed") || text.includes("critical")
          ? "error"
          : "offline";
  return `<span class="status"><span class="dot ${css}"></span>${esc(value || "-")}</span>`;
};
const table = (headers, rows) =>
  `<div class="table-wrap"><table><thead><tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr></thead><tbody>${rows
    .map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`)
    .join("")}</tbody></table></div>`;
const empty = (title, message = "Ainda nao ha dados reais disponiveis para esta secao.") =>
  `<article class="card"><h3>${title}</h3><p class="muted">${message}</p></article>`;
const timeframes = [
  ["5m", "5 minutos"],
  ["15m", "15 minutos"],
  ["30m", "30 minutos"],
  ["1h", "1 hora"],
  ["2h", "2 horas"],
  ["6h", "6 horas"],
  ["12h", "12 horas"],
  ["today", "Dia atual"],
  ["24h", "Ultimas 24 horas"],
  ["72h", "72 horas"],
  ["1w", "1 semana"],
  ["30d", "30 dias"],
  ["custom", "Personalizado"],
];
const timeframeControl = (id, value = "1h") =>
  `<div class="timeframe-control"><label>Timeframe<select id="${id}-timeframe">${timeframes.map(([key, label]) => `<option value="${key}" ${key === value ? "selected" : ""}>${label}</option>`).join("")}</select></label><label class="custom-range hidden">Inicio<input id="${id}-start" type="datetime-local"></label><label class="custom-range hidden">Fim<input id="${id}-end" type="datetime-local"></label><button id="${id}-apply" class="button ghost" type="button">Aplicar</button></div>`;
const latestPoint = (metrics) => metrics.length ? metrics[metrics.length - 1] : {};
const healthState = (value) => {
  const text = String(value || "offline").toLowerCase();
  if (text.includes("online") || text === "ok" || text === "active") return { key: "online", label: "UP", hint: "Coletando agora" };
  if (text.includes("warn") || text.includes("stale") || text.includes("pending")) return { key: "warning", label: "ATENCAO", hint: "Requer validacao" };
  return { key: "offline", label: "DOWN", hint: "Sem heartbeat recente" };
};
const healthLabel = (value) => healthState(value).label;
const healthDot = (value) => `<span class="dot ${esc(healthState(value).key)}"></span>`;
const healthPill = (value) => {
  const health = healthState(value);
  return `<span class="health-pill ${health.key}"><span></span><strong>${health.label}</strong><small>${health.hint}</small></span>`;
};
const metricTile = (label, value, hint = "") =>
  `<div class="metric-tile"><span>${esc(label)}</span><strong>${value}</strong>${hint ? `<small>${esc(hint)}</small>` : ""}</div>`;
const featureTile = (label, enabled, detail = "") =>
  `<div class="feature-tile ${enabled ? "enabled" : "disabled"}"><span></span><div><strong>${esc(label)}</strong><small>${enabled ? "habilitado" : "desabilitado"}${detail ? ` - ${esc(detail)}` : ""}</small></div></div>`;
const percentBar = (label, value) => {
  const numeric = Math.max(0, Math.min(100, Number(value || 0)));
  return `<div class="percent-bar"><div><span>${esc(label)}</span><strong>${numeric.toFixed(1)}%</strong></div><b><i style="width:${numeric}%"></i></b></div>`;
};
const seriesChart = (label, metrics, fields, options = {}) => {
  if (!metrics.length) {
    return `<div class="chart-empty">Sem metricas reais neste periodo.</div>`;
  }
  const width = 640;
  const height = 180;
  const colors = ["var(--primary)", "var(--accent)", "var(--warning)", "var(--success)"];
  const maxValue = options.max || Math.max(1, ...metrics.flatMap((point) => fields.map((field) => Number(point[field.key] || 0))));
  const pointsFor = (field) =>
    metrics
      .map((point, index) => {
        const x = metrics.length === 1 ? width / 2 : (index / (metrics.length - 1)) * width;
        const y = height - (Number(point[field.key] || 0) / maxValue) * (height - 16) - 8;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  const gridLines = [25, 50, 75].map((pct) => `<line x1="0" x2="${width}" y1="${height - (pct / 100) * height}" y2="${height - (pct / 100) * height}" class="chart-grid-line"></line>`).join("");
  return `<div class="metric-chart"><div class="chart-title"><span>${esc(label)}</span><small>${metrics.length} amostras reais</small></div><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(label)}">${gridLines}${fields.map((field, index) => `<polyline points="${pointsFor(field)}" fill="none" stroke="${colors[index % colors.length]}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></polyline>`).join("")}</svg><div class="chart-legend">${fields.map((field, index) => `<span><i style="background:${colors[index % colors.length]}"></i>${esc(field.label)}</span>`).join("")}</div></div>`;
};
const deriveRates = (metrics) =>
  metrics.map((point, index) => {
    const previous = metrics[index - 1];
    if (!previous || !point.timestamp || !previous.timestamp) {
      return { ...point, netInRate: 0, netOutRate: 0, diskReadRate: 0, diskWriteRate: 0 };
    }
    const seconds = Math.max(1, (new Date(point.timestamp) - new Date(previous.timestamp)) / 1000);
    const delta = (current, before) => Math.max(0, Number(current || 0) - Number(before || 0)) / seconds;
    return {
      ...point,
      netInRate: delta(point.netRxBytes, previous.netRxBytes),
      netOutRate: delta(point.netTxBytes, previous.netTxBytes),
      diskReadRate: delta(point.diskReadBytes, previous.diskReadBytes),
      diskWriteRate: delta(point.diskWriteBytes, previous.diskWriteBytes),
    };
  });
const bytes = (value) => {
  const numeric = Number(value || 0);
  if (numeric >= 1024 ** 3) return `${(numeric / 1024 ** 3).toFixed(1)} GB`;
  if (numeric >= 1024 ** 2) return `${(numeric / 1024 ** 2).toFixed(1)} MB`;
  if (numeric >= 1024) return `${(numeric / 1024).toFixed(1)} KB`;
  return `${numeric} B`;
};
const asArray = (value) => (Array.isArray(value) ? value : []);
const asObject = (value) => (value && typeof value === "object" && !Array.isArray(value) ? value : {});
const incidentDuration = (incident) => {
  const start = incident.triggered_at ? new Date(incident.triggered_at) : null;
  const end = incident.resolved_at ? new Date(incident.resolved_at) : new Date();
  if (!start) return "-";
  const minutes = Math.max(0, Math.round((end - start) / 60000));
  if (minutes < 60) return `${minutes} min`;
  if (minutes < 1440) return `${Math.round(minutes / 60)} h`;
  return `${Math.round(minutes / 1440)} d`;
};
const actionMenu = (items) =>
  `<details class="kebab"><summary aria-label="Acoes">⋮</summary><div>${items.map((item) => item.disabled ? `<span class="disabled">${esc(item.label)}</span>` : `<button type="button" class="${esc(item.className || "")}" ${item.attrs || ""}>${esc(item.label)}</button>`).join("")}</div></details>`;
const jsonBlock = (value) => `<pre><code>${esc(JSON.stringify(value || {}, null, 2))}</code></pre>`;
const kvTable = (title, value) => `<article class="card"><h3>${esc(title)}</h3>${value && Object.keys(value).length ? table(["Chave", "Valor"], Object.entries(value).map(([key, item]) => [esc(key), esc(typeof item === "object" ? JSON.stringify(item) : item)])) : `<p class="muted">Sem dados.</p>`}</article>`;
const csvValue = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
const downloadCsv = (filename, rows) => {
  const csv = rows.map((row) => row.map(csvValue).join(";")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};
const queryString = (params) => {
  const search = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      search.set(key, value);
    }
  });
  const text = search.toString();
  return text ? `?${text}` : "";
};
const filterValue = (view, key, fallback = "") => state.filters[view]?.[key] ?? fallback;
const setFilter = (view, key, value) => {
  state.filters[view] = { ...(state.filters[view] || {}), [key]: value };
};
const filterPanel = (view, fields, timeframe = true) => {
  const controls = fields.map((field) => `<label>${esc(field.label)}<input name="${esc(field.name)}" value="${esc(filterValue(view, field.name))}" placeholder="${esc(field.placeholder || "")}"></label>`).join("");
  const timeframeHtml = timeframe ? `<label>Timeframe<select name="timeframe">${timeframes.map(([key, label]) => `<option value="${key}" ${filterValue(view, "timeframe", "24h") === key ? "selected" : ""}>${label}</option>`).join("")}</select></label><label>Inicio<input name="start" type="datetime-local" value="${esc(filterValue(view, "start"))}"></label><label>Fim<input name="end" type="datetime-local" value="${esc(filterValue(view, "end"))}"></label>` : "";
  return `<form id="${view}-filters" class="filter-panel">${controls}${timeframeHtml}<button class="button ghost" type="submit">Filtrar</button><button class="button ghost clear-filters" data-view="${esc(view)}" type="button">Limpar</button></form>`;
};
const bindFilters = (view, rerender) => {
  $(`#${view}-filters`)?.addEventListener("submit", (event) => {
    event.preventDefault();
    state.filters[view] = Object.fromEntries(new FormData(event.currentTarget).entries());
    rerender();
  });
  $(`#${view}-filters .clear-filters`)?.addEventListener("click", () => {
    state.filters[view] = {};
    rerender();
  });
};

function render(html) {
  $("#app-content").innerHTML = html;
}

function isPlatformAdmin() {
  return state.currentUser?.scope === "platform" || state.currentUser?.role === "superadmin";
}

function updateNavigation() {
  const tenantPermissions = Array.isArray(state.currentUser?.permissions) ? state.currentUser.permissions : [];
  const tenantViews = tenantPermissions.length && !["admin", "superadmin"].includes(state.currentUser?.role)
    ? TENANT_VIEWS.filter((view) => tenantPermissions.includes(view) || view === "dashboard")
    : TENANT_VIEWS;
  const allowed = new Set(isPlatformAdmin() ? PLATFORM_VIEWS : tenantViews);
  $$(".nav-link").forEach((button) => {
    if (!button.dataset.view) return;
    button.classList.toggle("hidden", !allowed.has(button.dataset.view));
  });
  $$(".nav-section").forEach((section) => {
    let cursor = section.nextElementSibling;
    let hasVisibleItem = false;
    while (cursor && !cursor.classList.contains("nav-section")) {
      if (cursor.classList?.contains("nav-link") && !cursor.classList.contains("hidden")) {
        hasVisibleItem = true;
        break;
      }
      cursor = cursor.nextElementSibling;
    }
    section.classList.toggle("hidden", !hasVisibleItem);
  });
  if (!allowed.has(state.view)) {
    state.view = isPlatformAdmin() ? "dashboard" : "hosts";
  }
}

function setView(view) {
  state.view = view;
  $("#view-title").textContent = titleMap[view] || view;
  $$(".nav-link").forEach((button) => {
    if (!button.dataset.view) return;
    button.classList.toggle("active", button.dataset.view === view);
  });
}

async function bootstrap() {
  try {
    const me = await api("/api/v1/auth/me");
    state.currentUser = me;
    $("#api-status").textContent = "API conectada";
    $("#api-status").style.color = "var(--success)";
    $("#user-summary").innerHTML = `<strong>${esc(me.full_name || me.username)}</strong><span>${esc(me.role)}</span><span>${esc(me.tenant?.name || "")}</span>`;
    $("#login-screen").classList.add("hidden");
    $("#app-screen").classList.remove("hidden");
    updateNavigation();
    await loadView(state.view);
  } catch {
    state.currentUser = null;
    $("#api-status").textContent = "Sem sessao";
    $("#api-status").style.color = "var(--danger)";
    $("#login-screen").classList.remove("hidden");
    $("#app-screen").classList.add("hidden");
  }
}

async function renderTenantDashboard() {
  const data = asObject(await api("/api/v1/dashboard/summary"));
  const counters = asObject(data.counters);
  const hosts = asArray(data.hosts);
  const logs = asArray(data.logs);
  const incidents = asArray(data.incidents);
  const problemHosts = asArray(data.problem_hosts);
  const okHosts = Number(counters.hosts_online || 0);
  const totalHosts = Number(counters.hosts_total || 0);
  const hostRows = hosts.map((host) => [
    `<button class="link-button dashboard-host-link" data-host-id="${esc(host.id)}" type="button"><strong>${esc(host.hostname)}</strong></button><br><small>${esc(host.ip || "-")}</small>`,
    status(host.status),
    `${num(host.cpu_usage)}%`,
    `${num(host.memory_usage)}%`,
    fmt(host.last_seen),
  ]);
  const logRows = logs.map((log) => [
    fmt(log.timestamp),
    esc(log.level),
    esc(log.source || "-"),
    esc(log.message),
  ]);
  const incidentRows = incidents.slice(0, 5).map((incident) => [
    `<span class="mono">${esc(incident.id.slice(0, 8))}</span>`,
    `<strong>${esc(incident.name)}</strong><br><small>${esc(incident.description || "-")}</small>`,
    status(incident.status),
    esc(incident.severity || "-"),
    esc(incident.entity_name || incident.entity_type || "-"),
    incidentDuration(incident),
  ]);
  render(`
    <section class="grid cards">
      <article class="card stat health-summary"><span class="eyebrow">Hosts status</span><strong>${num(okHosts)}/${num(totalHosts)} hosts OK</strong><p class="muted">${problemHosts.length ? `${num(problemHosts.length)} host(s) com incidentes` : "Sem incidentes em hosts"}</p></article>
      <article class="card stat"><span class="eyebrow">Gateways</span><strong>${num(counters.gateways_total)}</strong><p class="muted">registrados</p></article>
      <article class="card stat"><span class="eyebrow">Logs</span><strong>${num(counters.logs_total)}</strong><p class="muted">ingeridos</p></article>
      <article class="card stat"><span class="eyebrow">Traces</span><strong>${num(counters.traces_total)}</strong><p class="muted">observabilidade</p></article>
    </section>
    ${problemHosts.length ? `<article class="card incident-strip"><h3>Hosts com problemas</h3><div class="incident-links">${problemHosts.map((host) => `<button class="button ghost dashboard-host-link" data-host-id="${esc(host.id)}" type="button">${esc(host.hostname)} - ${esc(host.status || "-")}</button>`).join("")}</div></article>` : ""}
    <section class="grid two">
      <article class="card"><h3>Ultimos hosts</h3>${hostRows.length ? table(["Host", "Status", "CPU", "RAM", "Ultima vista"], hostRows) : `<p class="muted">Nenhum host monitorado ainda.</p>`}</article>
      <article class="card"><h3>Logs recentes</h3>${logRows.length ? table(["Quando", "Nivel", "Origem", "Mensagem"], logRows) : `<p class="muted">Nenhum log ingerido.</p>`}</article>
    </section>
    <article class="card"><h3>Ultimos incidentes</h3>${incidentRows.length ? table(["ID", "Descricao", "Status", "Severidade", "Entidade", "Duracao"], incidentRows) : `<p class="muted">Nenhum incidente real registrado.</p>`}</article>
  `);
  $$(".dashboard-host-link").forEach((button) => button.addEventListener("click", () => renderHostDetail(button.dataset.hostId)));
}

async function renderPlatformDashboard() {
  const [rawData, rawRuntime] = await Promise.all([
    api("/api/v1/admin/overview"),
    api("/api/v1/admin/runtime"),
  ]);
  const data = asObject(rawData);
  const runtime = asObject(rawRuntime);
  const summary = asObject(data.summary);
  const platform = asObject(data.platform);
  const gatewayHealth = asObject(runtime.gateway_health);
  const apiCluster = asObject(runtime.api_cluster);
  const ingestion = asObject(runtime.ingestion_last_24h);
  const dependencies = asObject(runtime.dependencies);
  const redis = asObject(dependencies.redis);
  const postgres = asObject(dependencies.postgres);
  const clusterDesign = asObject(runtime.cluster_design);
  const customerRows = asArray(data.tenants).map((tenant) => [
    esc(tenant.name),
    tenant.internal ? "interno" : "cliente",
    num(tenant.consumption.hosts),
    num(tenant.consumption.network_assets),
    num(tenant.consumption.synthetics),
    num(tenant.consumption.weighted_units),
  ]);
  const gatewayRows = asArray(gatewayHealth.tenants).map((tenant) => [
    esc(tenant.tenant_name),
    tenant.internal ? "interno" : "cliente",
    num(tenant.online),
    num(tenant.stale),
    num(tenant.offline),
    num(tenant.total),
  ]);
  const instanceRows = asArray(apiCluster.instances).map((item) => [
    `<span class="mono">${esc(item.instance_id)}</span><br><small>${esc(item.hostname || "-")}</small>`,
    esc(item.version || "-"),
    num(item.requests_total),
    num(item.errors_5xx_total),
    `${num(item.error_rate_5xx)}%`,
    `${num(item.latency_avg_ms)} ms`,
    `${num(item.latency_p95_ms)} ms`,
    fmt(item.updated_at),
  ]);
  render(`
    <section class="grid cards">
      <article class="card stat"><span class="eyebrow">Clientes</span><strong>${num(summary.tenant_customers)}</strong><p class="muted">tenants monitorados</p></article>
      <article class="card stat"><span class="eyebrow">Hosts</span><strong>${num(summary.hosts)}</strong><p class="muted">consumo consolidado</p></article>
      <article class="card stat"><span class="eyebrow">Ativos</span><strong>${num(summary.network_assets)}</strong><p class="muted">ativos de rede</p></article>
      <article class="card stat"><span class="eyebrow">Sinteticos</span><strong>${num(summary.synthetics)}</strong><p class="muted">checks configurados</p></article>
    </section>
    <section class="grid two">
      <article class="card">
        <h3>URLs da plataforma</h3>
        <p><strong>API:</strong> ${esc(platform.api_url)}</p>
        <p><strong>Frontend:</strong> ${esc(platform.frontend_url)}</p>
        <p class="muted">O superadmin observa clientes, licencas e consumo global. A operacao do tenant fica no tenant demo ou nos tenants de clientes.</p>
      </article>
      <article class="card">
        <h3>Consumo por tenant</h3>
        ${customerRows.length ? table(["Tenant", "Tipo", "Hosts", "Ativos", "Sinteticos", "Unidades"], customerRows) : `<p class="muted">Nenhum tenant cadastrado.</p>`}
      </article>
    </section>
    <section class="grid two">
      <article class="card">
        <h3>Runtime da plataforma</h3>
        <p><strong>Modo HA API:</strong> ${esc(apiCluster.mode)}</p>
        <p><strong>Instancias esperadas:</strong> ${num(apiCluster.expected_instances)}</p>
        <p><strong>Instancias ativas previstas:</strong> ${num(apiCluster.active_instances)}</p>
        <p><strong>Proxy:</strong> ${esc(apiCluster.frontend_proxy)}</p>
        <p><strong>PostgreSQL:</strong> ${esc(postgres.host)}:${esc(postgres.port)} (${esc(postgres.mode)})</p>
        <p><strong>Redis:</strong> ${esc(redis.host)}:${esc(redis.port)} (${esc(redis.mode)})</p>
        <p><strong>Sentinels:</strong> ${esc(asArray(redis.sentinels).join(", ") || "-")}</p>
      </article>
      <article class="card">
        <h3>Ingestao ultimas 24h</h3>
        <p><strong>Metricas:</strong> ${num(ingestion.metrics)}</p>
        <p><strong>Logs:</strong> ${num(ingestion.logs)}</p>
        <p><strong>Traces:</strong> ${num(ingestion.traces)}</p>
        <p class="muted">${esc(clusterDesign.tenant_policy)}. Estrategia atual: ${esc(clusterDesign.agent_strategy)}.</p>
      </article>
    </section>
    <section class="grid two">
      <article class="card">
        <h3>API por instancia</h3>
        ${instanceRows.length ? table(["Instancia", "Versao", "Requests", "5xx", "Taxa 5xx", "Lat avg", "Lat p95", "Ultima atividade"], instanceRows) : `<p class="muted">As instancias ainda nao publicaram metricas no Redis.</p>`}
      </article>
      <article class="card">
        <h3>Leitura operacional</h3>
        <p><strong>Objetivo:</strong> acompanhar latencia, erros 5xx e atividade por instancia.</p>
        <p><strong>Fonte:</strong> middleware real da API persistindo contadores e amostras no Redis.</p>
        <p class="muted">Quando houver troca de backend, esse painel ajuda a validar se cada instancia permaneceu ativa e sem degradacao.</p>
      </article>
    </section>
    <section class="grid two">
      <article class="card">
        <h3>Saude dos gateways</h3>
        ${gatewayRows.length ? table(["Tenant", "Tipo", "Online", "Stale", "Offline", "Total"], gatewayRows) : `<p class="muted">Nenhum gateway registrado.</p>`}
      </article>
      <article class="card">
        <h3>Resumo geral</h3>
        <p><strong>Gateways online:</strong> ${num(runtime.gateway_health.online)}</p>
        <p><strong>Gateways stale:</strong> ${num(runtime.gateway_health.stale)}</p>
        <p><strong>Gateways offline:</strong> ${num(runtime.gateway_health.offline)}</p>
        <p class="muted">Esses estados sao calculados pelo heartbeat real dos gateways e pela janela configurada em cada instancia.</p>
      </article>
    </section>
  `);
}

async function renderPlatformLicensing() {
  const [rawOverview, rawBilling] = await Promise.all([
    api("/api/v1/admin/overview"),
    api("/api/v1/licenses/admin/billing-config"),
  ]);
  const data = asObject(rawOverview);
  const billing = asObject(rawBilling);
  const currency = billing.currency || "BRL";
  const units = asArray(billing.units);
  const packages = asArray(billing.packages);
  const discounts = asObject(billing.discounts);
  const customerTenants = asArray(data.tenants).filter((tenant) => !tenant.internal);
  const summary = asObject(data.billing_summary);
  const formatIncludedUnits = (includedUnits) => Object.entries(asObject(includedUnits))
    .filter(([, value]) => Number(value || 0) > 0)
    .map(([code, value]) => `${code}: ${value}`)
    .join("\n");
  const tenantRows = customerTenants.map((tenant) => {
    const consumption = asObject(tenant.consumption);
    const billingUnits = asObject(consumption.billing_units);
    const billingState = asObject(tenant.billing);
    const best = asObject(billingState.best_option);
    const selected = asObject(billingState.selected_option);
    const effective = Object.keys(selected).length ? selected : best;
    return {
      tenant,
      row: [
        esc(tenant.name),
        status(tenant.status),
        esc(tenant.plan),
        num(billingUnits.hosts_infra_hours),
        num(billingUnits.hosts_full_hours),
        num(billingUnits.snmp_devices),
        num(billingUnits.discovered_devices),
        num(billingUnits.observability_units),
        num(billingUnits.security_units),
        num(billingUnits.integration_metric_units),
        maybeNum(billingUnits.logs_gb, " GB"),
        money(billingState.payg_total, currency),
        `${esc(effective.label || "-")}<br><small>${money(effective.total, currency)}</small>`,
        money(best.savings_vs_payg, currency),
      ],
      export: [
        tenant.name,
        tenant.slug,
        tenant.plan,
        tenant.status,
        billingUnits.hosts_infra_hours || 0,
        billingUnits.hosts_full_hours || 0,
        billingUnits.snmp_devices || 0,
        billingUnits.discovered_devices || 0,
        billingUnits.observability_units || 0,
        billingUnits.security_units || 0,
        billingUnits.integration_metric_units || 0,
        billingUnits.logs_gb || 0,
        billingState.payg_total || 0,
        effective.label || "-",
        effective.total || 0,
        best.savings_vs_payg || 0,
      ],
    };
  });
  const totalEstimate = Number(summary.best_total || 0);
  const paygEstimate = Number(summary.payg_total || 0);
  const totalSavings = Number(summary.estimated_savings || Math.max(0, paygEstimate - totalEstimate));
  const packageRows = packages.map((item) => [
    `<strong>${esc(item.label || item.code)}</strong><br><small>${esc(item.description || "-")}</small>`,
    `<label class="check-row"><input type="checkbox" name="package_enabled__${esc(item.code)}" ${item.enabled ? "checked" : ""}> ativo</label>`,
    `<input name="package_label__${esc(item.code)}" value="${esc(item.label || item.code)}">`,
    `<input name="package_base_price__${esc(item.code)}" type="number" min="0" step="0.01" value="${esc(item.base_price || 0)}">`,
    `<input name="package_discount_percent__${esc(item.code)}" type="number" min="0" step="0.01" value="${esc(item.discount_percent || 0)}">`,
    `<textarea name="package_included_units__${esc(item.code)}" rows="4" placeholder="hosts_infra_hours: 720&#10;logs_gb: 20">${esc(formatIncludedUnits(item.included_units))}</textarea>`,
  ]);
  render(`
    <section class="grid cards">
      <article class="card stat"><span class="eyebrow">Moeda</span><strong>${esc(currency)}</strong><p class="muted">ciclo ${esc(billing.billing_cycle || "monthly")}</p></article>
      <article class="card stat"><span class="eyebrow">Unidades cobraveis</span><strong>${num(units.filter((item) => item.enabled).length)}</strong><p class="muted">catalogo ativo</p></article>
      <article class="card stat"><span class="eyebrow">Clientes</span><strong>${num(customerTenants.length)}</strong><p class="muted">tenants faturaveis</p></article>
      <article class="card stat"><span class="eyebrow">Pay as you go</span><strong>${money(paygEstimate, currency)}</strong><p class="muted">sem pacote</p></article>
      <article class="card stat"><span class="eyebrow">Melhor simulacao</span><strong>${money(totalEstimate, currency)}</strong><p class="muted">com pacote/desconto</p></article>
      <article class="card stat"><span class="eyebrow">Economia estimada</span><strong>${money(totalSavings, currency)}</strong><p class="muted">otimizacao comercial</p></article>
    </section>
    <section class="grid two">
      <article class="card">
        <div class="section-header">
          <div>
            <h3>Configuracao comercial das licencas</h3>
            <p class="muted">Defina precificacao por unidade, pacotes, franquias e descontos por plano.</p>
          </div>
        </div>
        <form id="billing-config-form" class="form-grid">
          <label>Moeda<input name="currency" value="${esc(currency)}"></label>
          <label>Ciclo<select name="billing_cycle"><option value="monthly" ${billing.billing_cycle === "monthly" ? "selected" : ""}>Mensal</option><option value="hourly" ${billing.billing_cycle === "hourly" ? "selected" : ""}>Horario</option><option value="custom" ${billing.billing_cycle === "custom" ? "selected" : ""}>Customizado</option></select></label>
          <label style="grid-column:1/-1">Observacoes<textarea name="notes" placeholder="Regras comerciais, descontos, bundling, franquias">${esc(billing.notes || "")}</textarea></label>
          <div style="grid-column:1/-1">${table(["Unidade", "Categoria", "Ativa", "Preco", "Franquia", "Excedente", "Rotulo", "Codigo"], units.map((item) => [
            `<strong>${esc(item.label)}</strong><br><small>${esc(item.description || "-")}</small>`,
            esc(item.category || "-"),
            `<label class="check-row"><input type="checkbox" name="enabled__${esc(item.code)}" ${item.enabled ? "checked" : ""}> ativa</label>`,
            `<input name="price_per_unit__${esc(item.code)}" type="number" min="0" step="0.01" value="${esc(item.price_per_unit)}">`,
            `<input name="included_units__${esc(item.code)}" type="number" min="0" step="0.01" value="${esc(item.included_units)}">`,
            `<input name="overage_price__${esc(item.code)}" type="number" min="0" step="0.01" value="${esc(item.overage_price)}">`,
            `<input name="unit_label__${esc(item.code)}" value="${esc(item.unit_label || "")}">`,
            `<small>${esc(item.code)}</small>`,
          ]))}</div>
          <div style="grid-column:1/-1">${table(["Pacote", "Ativo", "Nome exibicao", "Base", "Desc.%", "Unidades inclusas"], packageRows)}</div>
          <div style="grid-column:1/-1">${table(["Desconto", "Valor"], [
            ["Trial", `<input name="discount_trial_percent" type="number" min="0" step="0.01" value="${esc(discounts.trial_percent || 0)}">`],
            ["Interno", `<input name="discount_internal_percent" type="number" min="0" step="0.01" value="${esc(discounts.internal_percent || 0)}">`],
            ["Starter", `<input name="discount_starter_percent" type="number" min="0" step="0.01" value="${esc(discounts.starter_percent || 0)}">`],
            ["Professional", `<input name="discount_professional_percent" type="number" min="0" step="0.01" value="${esc(discounts.professional_percent || 0)}">`],
            ["Enterprise", `<input name="discount_enterprise_percent" type="number" min="0" step="0.01" value="${esc(discounts.enterprise_percent || 0)}">`],
          ])}</div>
        </form>
        <div class="actions" style="margin-top:14px"><button id="save-billing-config" class="button primary" type="button">Salvar configuracao</button><button id="export-billing-csv" class="button ghost" type="button">Exportar CSV</button></div>
        <p id="billing-message" class="message"></p>
      </article>
      <article class="card">
        <h3>Leitura de consumo comercial</h3>
        <p><strong>Logs:</strong> volume aproximado persistido em GB por tenant.</p>
        <p><strong>Hosts:</strong> estimativa mensal em host-hora baseada nos hosts atuais infra/full.</p>
        <p><strong>SNMP:</strong> dispositivos com SNMP ativo x dispositivos apenas discovered.</p>
        <p><strong>Seguranca:</strong> pool somando IDS, eventos, scans e pentest.</p>
        <p><strong>Observabilidade:</strong> unidade consolidada para OTel/RUM/traces.</p>
        <p><strong>Pacotes:</strong> o simulador compara PAYG com bundles comerciais e aplica o desconto do plano do tenant.</p>
        <p class="muted">Esse bloco já serve como base para precificação inicial, pacotes MSP e negociação comercial por tenant.</p>
      </article>
    </section>
    <article class="card">
      <h3>Consumo estimado por tenant</h3>
      ${tenantRows.length ? table(["Tenant", "Status", "Plano", "Host-h infra", "Host-h full", "SNMP", "Discovery", "Observab.", "Seguranca", "Integracoes", "Logs", "PAYG", "Melhor opcao", "Economia"], tenantRows.map((item) => item.row)) : `<p class="muted">Nenhum tenant cliente disponivel.</p>`}
      <p class="muted">O tenant demo concentra o painel operacional atual. O superadmin observa clientes e consumo global.</p>
    </article>
  `);
  const parseIncludedUnits = (text) => {
    const raw = String(text || "").trim();
    if (!raw) return {};
    return raw.split(/\r?\n/).reduce((acc, line) => {
      const [key, value] = line.split(":").map((item) => item.trim());
      if (key && value !== undefined && value !== "") {
        acc[key] = Number(value);
      }
      return acc;
    }, {});
  };
  $("#save-billing-config").addEventListener("click", async () => {
    const form = $("#billing-config-form");
    const payload = {
      currency: form.currency.value || "BRL",
      billing_cycle: form.billing_cycle.value || "monthly",
      notes: form.notes.value || "",
      units: {},
      packages: {},
      discounts: {
        trial_percent: Number(form.elements.discount_trial_percent.value || 0),
        internal_percent: Number(form.elements.discount_internal_percent.value || 0),
        starter_percent: Number(form.elements.discount_starter_percent.value || 0),
        professional_percent: Number(form.elements.discount_professional_percent.value || 0),
        enterprise_percent: Number(form.elements.discount_enterprise_percent.value || 0),
      },
    };
    units.forEach((item) => {
      payload.units[item.code] = {
        enabled: form.elements[`enabled__${item.code}`].checked,
        price_per_unit: Number(form.elements[`price_per_unit__${item.code}`].value || 0),
        included_units: Number(form.elements[`included_units__${item.code}`].value || 0),
        overage_price: Number(form.elements[`overage_price__${item.code}`].value || 0),
        unit_label: form.elements[`unit_label__${item.code}`].value || item.unit_label || "",
        notes: item.notes || "",
      };
    });
    packages.forEach((item) => {
      payload.packages[item.code] = {
        enabled: form.elements[`package_enabled__${item.code}`].checked,
        label: form.elements[`package_label__${item.code}`].value || item.label || item.code,
        description: item.description || "",
        base_price: Number(form.elements[`package_base_price__${item.code}`].value || 0),
        discount_percent: Number(form.elements[`package_discount_percent__${item.code}`].value || 0),
        included_units: parseIncludedUnits(form.elements[`package_included_units__${item.code}`].value),
        notes: item.notes || "",
      };
    });
    try {
      await api("/api/v1/licenses/admin/billing-config", { method: "PUT", body: JSON.stringify(payload) });
      $("#billing-message").textContent = "Configuracao comercial salva.";
      await renderPlatformLicensing();
    } catch (error) {
      $("#billing-message").textContent = error.message;
    }
  });
  $("#export-billing-csv").addEventListener("click", () => {
    const rows = [
      ["Tenant", "Slug", "Plano", "Status", "Host-h Infra", "Host-h Full", "SNMP", "Discovery", "Observabilidade", "Seguranca", "Integracoes", "Logs GB", "PAYG", "Melhor Opcao", "Total Melhor Opcao", "Economia"],
      ...tenantRows.map((item) => item.export),
    ];
    downloadCsv(`las-licenciamento-${new Date().toISOString().slice(0, 10)}.csv`, rows);
  });
}

async function renderTenants() {
  const items = await api("/api/v1/tenants");
  render(`
    <section class="grid two">
      <article class="card">
        <h3>Clientes e tenants</h3>
        ${items.length ? table(["Nome", "Slug", "Plano", "Status", "Tipo", "Admin"], items.map((tenant) => [
          esc(tenant.name),
          esc(tenant.slug),
          esc(String(tenant.plan).replace("PlanType.", "")),
          esc(tenant.status),
          tenant.internal ? "interno" : "cliente",
          `${esc(tenant.admin_name || "-")}<br><small>${esc(tenant.admin_email || "-")}</small>`,
        ])) : `<p class="muted">Nenhum tenant cadastrado.</p>`}
      </article>
      <article class="card">
        <h3>Novo tenant</h3>
        <form id="tenant-form" class="form-grid">
          <label>Nome<input name="name" required></label>
          <label>Slug<input name="slug" placeholder="gerado automaticamente se vazio"></label>
          <label>Admin nome<input name="admin_name" required></label>
          <label>Admin email<input name="admin_email" placeholder="opcional"></label>
          <label>Admin usuario<input name="admin_username" placeholder="gerado pelo e-mail se vazio"></label>
          <label>Senha inicial<input name="admin_password" type="password" value="admin123" required></label>
          <label>Plano<select name="plan"><option value="enterprise">enterprise</option><option value="trial">trial</option><option value="professional">professional</option><option value="starter">starter</option></select></label>
        </form>
        <div class="actions" style="margin-top:14px"><button id="save-tenant" class="button primary" type="button">Criar tenant</button></div>
        <p id="tenant-message" class="message"></p>
      </article>
    </section>
  `);
  const tenantForm = $("#tenant-form");
  tenantForm.name.addEventListener("input", () => {
    if (!tenantForm.slug.value.trim()) {
      tenantForm.slug.value = tenantForm.name.value.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    }
  });
  tenantForm.admin_email.addEventListener("input", () => {
    if (!tenantForm.admin_username.value.trim() && tenantForm.admin_email.value.includes("@")) {
      tenantForm.admin_username.value = tenantForm.admin_email.value.split("@")[0].replace(/[^a-zA-Z0-9_.-]/g, "_");
    }
  });
  $("#save-tenant").addEventListener("click", async () => {
    const payload = Object.fromEntries(new FormData(tenantForm).entries());
    try {
      await api("/api/v1/tenants", { method: "POST", body: JSON.stringify(payload) });
      $("#tenant-message").textContent = "Tenant criado.";
      await loadView("tenants");
    } catch (error) {
      $("#tenant-message").textContent = error.message;
    }
  });
}

async function renderHosts() {
  const params = state.filters.hosts || {};
  const items = await api(`/api/v1/hosts${queryString(params)}`);
  render(`<article class="card"><h3>Hosts monitorados</h3><p class="muted">Somente hosts/servidores/estações monitoráveis. Ativos SNMP ficam em Ativos de Rede.</p>${filterPanel("hosts", [{ name: "q", label: "Host/IP/SO" }, { name: "status", label: "Status" }], false)}${items.length ? table(["Host", "Status", "Modo", "Agente", "OTel", "CPU", "RAM", "Acoes"], items.map((host) => [
    `<button class="link-button host-detail-trigger" data-host-id="${esc(host.id)}" type="button"><strong>${esc(host.hostname)}</strong></button><br><small>${num((host.interfaces || []).length || (host.known_ips || []).length)} interface(s)</small>`,
    status(host.status),
    esc(host.monitoring_mode || "-"),
    host.agent_installed ? "instalado" : "nao",
    host.otel_enabled ? "ativo" : "desligado",
    `${num(host.cpu_usage)}%`,
    `${num(host.memory_usage)}%`,
    actionMenu([
      { label: "Configuracoes", className: "host-settings-trigger", attrs: `data-host-id="${esc(host.id)}"` },
      { label: "Desabilitar monitoramento", disabled: host.monitoring_mode === "disabled" },
      { label: "Ir para processos/servicos", className: "go-processes", attrs: `data-host-name="${esc(host.hostname)}"` },
      { label: "Ir para logs", className: "go-logs", attrs: `data-host-name="${esc(host.hostname)}"` },
      { label: "Informacoes IDS", className: "go-security-ids", attrs: `data-host-name="${esc(host.hostname)}"`, disabled: !host.ids_enabled },
      { label: "Vulnerabilidades", className: "go-security-vulns", attrs: `data-host-name="${esc(host.hostname)}"`, disabled: !host.vuln_scan_enabled },
    ]),
  ])) : `<p class="muted">Nenhum host identificado.</p>`}</article>`);
  bindFilters("hosts", renderHosts);
  $$(".host-detail-trigger").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedHostId = button.dataset.hostId;
      renderHostDetail(button.dataset.hostId);
    });
  });
  $$(".host-settings-trigger").forEach((button) => {
    button.addEventListener("click", () => {
      renderHostSettings(button.dataset.hostId);
    });
  });
  $$(".go-processes").forEach((button) => button.addEventListener("click", () => {
    setFilter("processes", "host", button.dataset.hostName || "");
    loadView("processes");
  }));
  $$(".go-logs").forEach((button) => button.addEventListener("click", () => {
    setFilter("logs", "host", button.dataset.hostName || "");
    loadView("logs");
  }));
  $$(".go-security-ids").forEach((button) => button.addEventListener("click", () => {
    setFilter("security", "host", button.dataset.hostName || "");
    state.securityTab = "ids";
    loadView("security");
  }));
  $$(".go-security-vulns").forEach((button) => button.addEventListener("click", () => {
    setFilter("security", "host", button.dataset.hostName || "");
    state.securityTab = "vulnerabilities";
    loadView("security");
  }));
}

async function renderHostSettings(hostId) {
  const cfg = await api(`/api/v1/hosts/${hostId}/settings`);
  const detectedLogs = cfg.detected_log_paths || [];
  const detectedTech = cfg.technology_inventory || [];
  render(`<article class="card"><div class="actions"><button id="back-hosts" class="button ghost" type="button">Voltar para hosts</button></div><h3>Configuracao do host</h3><form id="host-settings-form" class="form-grid"><input type="hidden" name="host_id" value="${esc(cfg.id)}"><label>Host<input value="${esc(cfg.hostname)} (${esc(cfg.ip || "-")})" disabled></label><label>Modo<select name="monitoring_mode"><option value="infra">infra</option><option value="infra+otel">infra+otel</option><option value="disabled">disabled</option></select></label><label><input type="checkbox" name="otel_enabled" style="width:auto; margin-right:8px">OTel habilitado</label><label><input type="checkbox" name="log_collection" style="width:auto; margin-right:8px">Coleta de logs</label><label><input type="checkbox" name="ids_enabled" style="width:auto; margin-right:8px">IDS habilitado</label><label><input type="checkbox" name="vuln_scan_enabled" style="width:auto; margin-right:8px">Scan de vulnerabilidades</label><label><input type="checkbox" name="apm_enabled" style="width:auto; margin-right:8px">APM habilitado</label><label style="grid-column:1/-1">Tags<textarea name="tags" placeholder="producao, banco, api"></textarea></label><label style="grid-column:1/-1">Caminhos de log habilitados<textarea name="log_paths" placeholder="/var/log/syslog&#10;/opt/app/logs/app.log"></textarea></label></form><div class="card soft-card" style="margin-top:14px"><div class="section-header"><div><h3>Logs detectados pelo agente</h3><p class="muted">Detectados automaticamente; selecione para habilitar o consumo/processamento.</p></div><button id="add-detected-logs" class="button ghost" type="button">Adicionar selecionados</button></div>${detectedLogs.length ? detectedLogs.map((path, index) => `<label class="check-row"><input type="checkbox" class="detected-log" value="${esc(path)}" ${cfg.log_paths?.includes(path) ? "checked" : ""}>${esc(path)}</label>`).join("") : `<p class="muted">Nenhum log padrao detectado ainda. O agente atualizado informa estes caminhos no proximo heartbeat.</p>`}</div><div class="card soft-card" style="margin-top:14px"><div class="section-header"><div><h3>Tecnologias detectadas</h3><p class="muted">Processos e servidores candidatos a OpenTelemetry/RUM. Use os instaladores OTel para selecionar e preparar a instrumentacao.</p></div><div class="actions"><a class="button ghost" href="/api/v1/agents/download/otel/linux?appname=${encodeURIComponent(cfg.hostname || "host")}" target="_blank" rel="noreferrer">OTel Linux</a><a class="button ghost" href="/api/v1/agents/download/otel/windows?appname=${encodeURIComponent(cfg.hostname || "host")}" target="_blank" rel="noreferrer">OTel Windows</a></div></div>${detectedTech.length ? table(["PID", "Processo", "Tecnologia", "OTel", "Auto"], detectedTech.slice(0, 20).map((item) => [esc(item.pid || "-"), esc(item.name || "-"), esc(item.technology || "-"), item.otel_supported ? "suportado" : "manual", item.auto_apply_supported ? "preparavel" : "instrucoes"])) : `<p class="muted">Nenhuma tecnologia detectada ainda. O agente 4.1.4 enviara este inventario no proximo heartbeat.</p>`}</div><div class="actions" style="margin-top:14px"><button id="save-host-settings" class="button primary" type="button">Salvar configuracao</button></div><p id="host-settings-message" class="message"></p></article>`);
  const form = $("#host-settings-form");
  form.monitoring_mode.value = cfg.monitoring_mode || "infra+otel";
  form.otel_enabled.checked = !!cfg.otel_enabled;
  form.log_collection.checked = !!cfg.log_collection;
  form.ids_enabled.checked = !!cfg.ids_enabled;
  form.vuln_scan_enabled.checked = !!cfg.vuln_scan_enabled;
  form.apm_enabled.checked = !!cfg.apm_enabled;
  form.tags.value = (cfg.tags || []).join(", ");
  form.log_paths.value = (cfg.log_paths || []).join("\n");
  $("#back-hosts").addEventListener("click", () => loadView("hosts"));
  $("#add-detected-logs")?.addEventListener("click", () => {
    const selected = $$(".detected-log").filter((item) => item.checked).map((item) => item.value);
    const current = form.log_paths.value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
    form.log_paths.value = [...new Set([...current, ...selected])].join("\n");
  });
  $("#save-host-settings").addEventListener("click", async () => {
    try {
      await api(`/api/v1/hosts/${hostId}/settings`, {
        method: "PUT",
        body: JSON.stringify({
          monitoring_mode: form.monitoring_mode.value,
          otel_enabled: form.otel_enabled.checked,
          log_collection: form.log_collection.checked,
          ids_enabled: form.ids_enabled.checked,
          vuln_scan_enabled: form.vuln_scan_enabled.checked,
          apm_enabled: form.apm_enabled.checked,
          tags: form.tags.value.split(",").map((item) => item.trim()).filter(Boolean),
          log_paths: form.log_paths.value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean),
        }),
      });
      $("#host-settings-message").textContent = "Configuracao do host salva.";
      await loadView("hosts");
    } catch (error) {
      $("#host-settings-message").textContent = error.message;
    }
  });
}

async function renderHostDetail(hostId, options = {}) {
  if (isUiV2()) {
    await renderHostDetailV2(hostId, options);
    return;
  }
  closeInspector();
  const timeframe = options.timeframe || state.hostTimeframe || "1h";
  const params = new URLSearchParams({ timeframe });
  if (timeframe === "custom") {
    if (options.start) params.set("start", new Date(options.start).toISOString());
    if (options.end) params.set("end", new Date(options.end).toISOString());
  }
  const data = await api(`/api/v1/hosts/${hostId}/detail?${params.toString()}`);
  const host = data.host;
  const processes = data.processes || [];
  const logs = data.logs || [];
  const incidents = data.incidents || [];
  const rateMetrics = deriveRates(data.metrics || []);
  const latest = latestPoint(rateMetrics);
  const topProcess = processes[0];
  render(`<section class="entity-detail"><article class="detail-hero card"><div class="detail-hero-main"><p class="eyebrow">Host detalhado</p><h2>${esc(host.hostname)}</h2><p class="muted">${esc(host.os || "sistema nao identificado")} ${host.os_version ? `- ${esc(host.os_version)}` : ""}</p><div class="actions"><button id="back-hosts" class="button ghost" type="button">Voltar para hosts</button>${actionMenu([{ label: "Configuracoes", className: "host-detail-settings" }, { label: "Ir para processos/servicos", className: "host-detail-processes" }, { label: "Ir para logs", className: "host-detail-logs" }, { label: "Informacoes IDS", disabled: !host.ids_enabled }, { label: "Vulnerabilidades", disabled: !host.vuln_scan_enabled }])}</div></div><div class="detail-health">${healthPill(host.status)}<small>Ultima coleta<br><strong>${fmt(host.last_seen)}</strong></small></div></article><article class="card detail-kpis">${metricTile("IP", esc(host.ip || "-"))}${metricTile("Agente", esc(host.agent_version || "nao instalado"), esc(host.monitoring_mode || "-"))}${metricTile("CPU cores", maybeNum(host.cpu_cores))}${metricTile("RAM total", maybeUnit(host.memory_total_mb, "MB"))}${metricTile("Disco total", maybeUnit(host.disk_total_gb, "GB"))}${metricTile("Amostras no periodo", num((data.metrics || []).length), `${fmt(data.timeframe?.start)} ate ${fmt(data.timeframe?.end)}`)}</article><article class="card"><div class="section-header"><div><h3>Incidentes do host</h3><p class="muted">Ultimos 2 incidentes abertos ou fechados, com duracao operacional.</p></div></div>${incidents.length ? table(["ID", "Descricao", "Status", "Metrica", "Duracao"], incidents.map((incident) => [`<span class="mono">${esc(incident.id.slice(0, 8))}</span>`, `<strong>${esc(incident.name)}</strong><br><small>${esc(incident.description || "-")}</small>`, status(incident.status), esc(incident.metric || "-"), incidentDuration(incident)])) : `<p class="muted">Nenhum incidente real registrado para este host.</p>`}</article><article class="card"><div class="section-header"><div><h3>Modulos habilitados</h3><p class="muted">Estado operacional configurado para este host. IDS e scan de vulnerabilidade entram aqui no detalhe do host.</p></div></div><div class="feature-grid">${featureTile("Logs", host.log_collection, (host.log_paths || []).length ? `${(host.log_paths || []).length} paths` : "sem paths")}${featureTile("OpenTelemetry", host.otel_enabled)}${featureTile("IDS", host.ids_enabled)}${featureTile("Scan Vulnerabilidade", host.vuln_scan_enabled)}${featureTile("APM", host.apm_enabled)}</div></article><article class="card"><div class="section-header"><div><h3>Consumo de recursos</h3><p class="muted">Dados reais do agente no periodo selecionado. Rede mostra taxa aproximada por segundo derivada dos contadores do host.</p></div></div>${timeframeControl("host-detail", timeframe)}<div class="resource-snapshot">${percentBar("CPU agora", latest.cpuUsage)}${percentBar("Memoria agora", latest.memoryUsage)}${percentBar("Disco agora", latest.diskUsage)}</div><div class="charts-grid three">${seriesChart("CPU", data.metrics, [{ key: "cpuUsage", label: "CPU" }], { max: 100 })}${seriesChart("Memoria", data.metrics, [{ key: "memoryUsage", label: "Memoria" }], { max: 100 })}${seriesChart("Disco", data.metrics, [{ key: "diskUsage", label: "Disco" }], { max: 100 })}</div><div class="charts-grid">${seriesChart("Rede In / Download", rateMetrics, [{ key: "netInRate", label: "In / Download" }])}${seriesChart("Rede Out / Upload", rateMetrics, [{ key: "netOutRate", label: "Out / Upload" }])}</div></article><section class="grid two"><article class="card"><div class="section-header"><div><h3>Processos e consumo</h3><p class="muted">Snapshot real da ultima coleta: ${fmt(data.processes_collected_at)}</p></div>${topProcess ? `<span class="tag">Top: ${esc(topProcess.name)}</span>` : ""}</div>${processes.length ? table(["PID", "Processo", "Usuario", "Status", "CPU", "RAM"], processes.map((proc) => [esc(proc.pid || "-"), esc(proc.name), esc(proc.username || "-"), esc(proc.status || "-"), `${num(proc.cpuUsage)}%`, `${num(proc.memoryUsage)}%`])) : `<p class="muted">Ainda nao ha snapshot real de processos para este host. O proximo ciclo do agente atualizado deve preencher esta area.</p>`}</article><article class="card"><div class="section-header"><div><h3>Ultimos 5 logs</h3><p class="muted">Independente do timeframe do grafico. Mostramos os ultimos logs reais correlacionados por host, hostname ou IP.</p></div></div>${logs.length ? table(["Quando", "Nivel", "Origem", "Mensagem"], logs.map((log) => [fmt(log.timestamp), esc(log.level), esc(log.source || log.service || "-"), esc(log.message)])) : `<p class="muted">Nenhum log real encontrado para este host.</p>`}</article></section></section>`);
  const timeframeSelect = $("#host-detail-timeframe");
  const customRanges = $$(".custom-range");
  const updateCustomVisibility = () => customRanges.forEach((item) => item.classList.toggle("hidden", timeframeSelect.value !== "custom"));
  updateCustomVisibility();
  timeframeSelect.addEventListener("change", updateCustomVisibility);
  $("#host-detail-apply").addEventListener("click", () => {
    state.hostTimeframe = timeframeSelect.value;
    renderHostDetail(hostId, {
      timeframe: timeframeSelect.value,
      start: $("#host-detail-start")?.value,
      end: $("#host-detail-end")?.value,
    });
  });
  $("#back-hosts").addEventListener("click", () => loadView("hosts"));
  $(".host-detail-settings")?.addEventListener("click", () => renderHostSettings(hostId));
  $(".host-detail-processes")?.addEventListener("click", () => {
    setFilter("processes", "host", host.hostname || host.ip || "");
    loadView("processes");
  });
  $(".host-detail-logs")?.addEventListener("click", () => {
    setFilter("logs", "host", host.hostname || host.ip || "");
    loadView("logs");
  });
}

function hostPropertiesInspector(host) {
  const tags = (host.tags || []).slice(0, 20);
  const interfaces = host.interfaces || [];
  const ifaceRows = interfaces.length
    ? table(["Interface", "IPs", "MAC", "Status"], interfaces.slice(0, 6).map((iface) => [
      esc(iface.name || iface.iface || "-"),
      esc((iface.ips || iface.addresses || []).join(", ") || "-"),
      esc(iface.mac || "-"),
      status(iface.status || "-"),
    ]))
    : `<p class="muted">Interfaces nao informadas pelo agente ainda.</p>`;

  return `
    <article class="card">
      <h3>Geral</h3>
      <div class="detail-grid">
        <span>Hostname<br><strong>${esc(host.hostname || "-")}</strong></span>
        <span>Sistema<br><strong>${esc(host.os || "-")} ${esc(host.os_version || "")}</strong></span>
        <span>IP (primario)<br><strong>${esc(host.ip || "-")}</strong></span>
        <span>Ultima comunicacao<br><strong>${fmt(host.last_seen)}</strong></span>
        <span>Agente<br><strong>${esc(host.agent_version || "nao instalado")}</strong></span>
        <span>Modo<br><strong>${esc(host.monitoring_mode || "-")}</strong></span>
      </div>
    </article>
    <article class="card">
      <h3>Hardware</h3>
      <div class="detail-grid">
        <span>CPU cores<br><strong>${maybeNum(host.cpu_cores)}</strong></span>
        <span>RAM total<br><strong>${maybeUnit(host.memory_total_mb, "MB")}</strong></span>
        <span>Disco total<br><strong>${maybeUnit(host.disk_total_gb, "GB")}</strong></span>
        <span>Uptime<br><strong>${esc(host.uptime || "-")}</strong></span>
      </div>
    </article>
    <article class="card">
      <h3>Rede</h3>
      ${ifaceRows}
    </article>
    <article class="card">
      <h3>Tags</h3>
      ${tags.length ? `<div class="pill-row">${tags.map((tag) => `<span class="tag">${esc(tag)}</span>`).join("")}</div>` : `<p class="muted">Sem tags definidas.</p>`}
    </article>
  `;
}

async function renderHostDetailV2(hostId, options = {}) {
  const timeframe = options.timeframe || state.hostTimeframe || "1h";
  const params = new URLSearchParams({ timeframe });
  if (timeframe === "custom") {
    if (options.start) params.set("start", new Date(options.start).toISOString());
    if (options.end) params.set("end", new Date(options.end).toISOString());
  }
  const data = await api(`/api/v1/hosts/${hostId}/detail?${params.toString()}`);
  const host = data.host;
  const processes = data.processes || [];
  const logs = data.logs || [];
  const incidents = data.incidents || [];
  const rateMetrics = deriveRates(data.metrics || []);
  const latest = latestPoint(rateMetrics);
  const logsPreview = logs.slice(0, 10);

  render(`
    <section class="entity-detail v2">
      <article class="detail-hero card v2-hero">
        <div class="v2-hero-main">
          <p class="eyebrow">Hosts <span class="muted">/</span> ${esc(host.hostname)}</p>
          <div class="v2-title-row">
            <h2>${esc(host.hostname)}</h2>
            <span class="tag">${esc(host.os || "SO nao identificado")}</span>
            <span class="tag">${esc(host.monitoring_mode || "infra")}</span>
            <span class="status">${healthDot(host.status)} ${esc(host.status || "offline")}</span>
          </div>
          <p class="muted">${esc(host.os_version || "")} ${host.ip ? `- ${esc(host.ip)}` : ""} ${host.agent_version ? `- agente ${esc(host.agent_version)}` : ""}</p>
          <div class="actions v2-actions">
            <button class="button ghost v2-open-props" type="button">Propriedades</button>
            <button class="button ghost v2-open-procs" type="button">Processos</button>
            <button class="button ghost v2-open-logs" type="button">Logs</button>
            <button class="button primary v2-restart" type="button" disabled title="Disponivel quando o endpoint de controle do agente estiver ativo">Reiniciar agente</button>
            <button id="back-hosts" class="button ghost" type="button">Voltar</button>
          </div>
        </div>
        <div class="v2-hero-kpis">
          ${metricTile("Saude do host", healthLabel(host.status), "Resumo operacional")}
          ${metricTile("Ultima comunicacao", fmt(host.last_seen), "Heartbeat")}
          ${metricTile("CPU agora", `${num(latest.cpuUsage)}%`, "snapshot")}
          ${metricTile("Memoria agora", `${num(latest.memoryUsage)}%`, "snapshot")}
        </div>
      </article>

      <article class="card">
        <div class="section-header">
          <div>
            <h3>Consumo (timeframe)</h3>
            <p class="muted">CPU, memoria, disco e rede derivados dos dados reais do agente.</p>
          </div>
        </div>
        ${timeframeControl("host-detail", timeframe)}
        <div class="charts-grid three">
          ${seriesChart("CPU", data.metrics, [{ key: "cpuUsage", label: "CPU" }], { max: 100 })}
          ${seriesChart("Memoria", data.metrics, [{ key: "memoryUsage", label: "Memoria" }], { max: 100 })}
          ${seriesChart("Disco", data.metrics, [{ key: "diskUsage", label: "Disco" }], { max: 100 })}
        </div>
        <div class="charts-grid">
          ${seriesChart("Rede In / Download", rateMetrics, [{ key: "netInRate", label: "In / Download" }])}
          ${seriesChart("Rede Out / Upload", rateMetrics, [{ key: "netOutRate", label: "Out / Upload" }])}
        </div>
      </article>

      <section class="grid two">
        <article class="card">
          <div class="section-header">
            <div>
              <h3>Incidentes (ultimos 2)</h3>
              <p class="muted">Quando houver baselines e alertas, eles aparecem aqui para drill down.</p>
            </div>
          </div>
          ${incidents.length ? table(["ID", "Descricao", "Status", "Duracao"], incidents.slice(0, 2).map((incident) => [
            `<span class="mono">${esc(incident.id.slice(0, 8))}</span>`,
            `<strong>${esc(incident.name)}</strong><br><small>${esc(incident.description || "-")}</small>`,
            status(incident.status),
            incidentDuration(incident),
          ])) : `<p class="muted">Nenhum incidente real registrado para este host.</p>`}
        </article>
        <article class="card">
          <div class="section-header">
            <div>
              <h3>Logs recentes (10)</h3>
              <p class="muted">Preview rapido. Use "Logs" para pesquisar e filtrar.</p>
            </div>
            <div class="actions">
              <button class="button ghost v2-open-logs" type="button">Abrir Logs</button>
            </div>
          </div>
          ${logsPreview.length ? table(["Quando", "Nivel", "Origem", "Mensagem"], logsPreview.map((log) => [
            fmt(log.timestamp),
            esc(log.level),
            esc(log.source || log.service || "-"),
            esc(log.message),
          ])) : `<p class="muted">Nenhum log real encontrado para este host.</p>`}
        </article>
      </section>

      <article class="card">
        <div class="section-header">
          <div>
            <h3>Processos (top)</h3>
            <p class="muted">Ordenado pelo consumo no snapshot mais recente. Clique em "Processos" para aplicar filtros.</p>
          </div>
          <div class="actions">
            <button class="button ghost v2-open-procs" type="button">Ver processos</button>
          </div>
        </div>
        ${processes.length ? table(["PID", "Processo", "Usuario", "CPU", "RAM"], processes.slice(0, 12).map((proc) => [
          esc(proc.pid || "-"),
          `<strong>${esc(proc.name)}</strong>`,
          esc(proc.username || "-"),
          `${num(proc.cpuUsage)}%`,
          `${num(proc.memoryUsage)}%`,
        ])) : `<p class="muted">Ainda nao ha snapshot real de processos para este host.</p>`}
      </article>
    </section>
  `);

  // Inspector default
  openInspector({
    title: host.hostname || "Host",
    eyebrow: "Propriedades do host",
    body: hostPropertiesInspector(host),
  });

  const timeframeSelect = $("#host-detail-timeframe");
  const customRanges = $$(".custom-range");
  const updateCustomVisibility = () => customRanges.forEach((item) => item.classList.toggle("hidden", timeframeSelect.value !== "custom"));
  updateCustomVisibility();
  timeframeSelect.addEventListener("change", updateCustomVisibility);
  $("#host-detail-apply").addEventListener("click", () => {
    state.hostTimeframe = timeframeSelect.value;
    renderHostDetailV2(hostId, {
      timeframe: timeframeSelect.value,
      start: $("#host-detail-start")?.value,
      end: $("#host-detail-end")?.value,
    });
  });
  $("#back-hosts").addEventListener("click", () => loadView("hosts"));

  $$(".v2-open-props").forEach((button) => button.addEventListener("click", () => openInspector({
    title: host.hostname || "Host",
    eyebrow: "Propriedades do host",
    body: hostPropertiesInspector(host),
  })));
  $$(".v2-open-procs").forEach((button) => button.addEventListener("click", () => {
    setFilter("processes", "host", host.hostname || host.ip || "");
    loadView("processes");
  }));
  $$(".v2-open-logs").forEach((button) => button.addEventListener("click", () => {
    setFilter("logs", "host", host.hostname || host.ip || "");
    loadView("logs");
  }));
}

const topologyScopes = [
  ["network", "Rede"],
  ["processes", "Processos"],
  ["services", "Servicos"],
  ["applications", "Aplicacoes"],
  ["hosts", "Hosts"],
];

const topologyNodeType = {
  host: "Host",
  network_asset: "Ativo",
  process_group: "Processo",
  service: "Servico",
  application: "Aplicacao",
  external_service: "Externo",
};

const topologyMetricLabel = (key) => ({
  requests: "req",
  errors: "erros",
  instances: "instancias",
  cpu_pct: "cpu",
  memory_pct: "mem",
  disk_pct: "disco",
  ports: "portas",
  ports_up: "up",
  ports_down: "down",
  speed_mbps: "mbps",
  utilization_pct: "uso",
  rx_errors: "rx err",
  tx_errors: "tx err",
  rx_drops: "rx drop",
  tx_drops: "tx drop",
  net_in_bytes: "in",
  net_out_bytes: "out",
  net_errors: "erros rede",
  avg_duration_ms: "latencia",
}[key] || key);

const topologyMetricValue = (key, value) => {
  if (key.endsWith("_bytes") || key === "net_in_bytes" || key === "net_out_bytes") return bytes(value);
  if (key.endsWith("_pct") || key === "utilization_pct") return `${Number(value || 0).toFixed(1)}%`;
  if (key.endsWith("_ms")) return `${Number(value || 0).toFixed(1)} ms`;
  return num(value);
};

const topologyMetricChips = (metrics = {}) => {
  const entries = Object.entries(metrics).filter(([, value]) => value !== null && value !== undefined && value !== "" && Number(value) !== 0).slice(0, 5);
  return entries.length
    ? `<div class="topology-metrics">${entries.map(([key, value]) => `<span>${esc(topologyMetricLabel(key))}: <strong>${esc(topologyMetricValue(key, value))}</strong></span>`).join("")}</div>`
    : "";
};

const topologyNodeCard = (node) =>
  `<article class="topology-node ${esc(node.type)} ${esc(healthState(node.status).key)}">
    <div>
      <small>${esc(topologyNodeType[node.type] || node.type)}</small>
      <strong>${esc(node.label || node.id)}</strong>
      ${node.subtitle ? `<span>${esc(node.subtitle)}</span>` : ""}
    </div>
    ${topologyMetricChips(node.metrics)}
  </article>`;

const topologyEdgeRow = (edge, nodeById) =>
  `<div class="topology-edge-row">
    <span>${esc(nodeById[edge.source]?.label || edge.source)}</span>
    <b>${esc(edge.label || edge.type)}</b>
    <span>${esc(nodeById[edge.target]?.label || edge.target)}</span>
    ${topologyMetricChips(edge.metrics)}
  </div>`;

function topologyGraph(data, scope) {
  const nodes = data.nodes || [];
  const edges = data.edges || [];
  if (!nodes.length) return `<p class="muted">Nenhum no real encontrado para este escopo no periodo selecionado.</p>`;
  const lanesByScope = {
    network: ["network_asset", "host", "external_service"],
    processes: ["host", "process_group", "service", "external_service"],
    services: ["host", "service", "external_service"],
    applications: ["application", "service", "host", "network_asset", "external_service"],
    hosts: ["host", "external_service"],
  };
  const lanes = lanesByScope[scope] || ["application", "host", "process_group", "service", "network_asset", "external_service"];
  const laneNodes = new Map(lanes.map((lane) => [lane, []]));
  nodes.forEach((node) => {
    const lane = lanes.includes(node.type) ? node.type : lanes[lanes.length - 1];
    laneNodes.get(lane).push(node);
  });
  const visibleLanes = lanes.filter((lane) => laneNodes.get(lane)?.length);
  const width = Math.max(980, visibleLanes.length * 260);
  const maxLaneCount = Math.max(1, ...visibleLanes.map((lane) => laneNodes.get(lane).length));
  const height = Math.max(420, maxLaneCount * 150 + 90);
  const positions = {};
  visibleLanes.forEach((lane, laneIndex) => {
    const items = laneNodes.get(lane);
    const x = 70 + laneIndex * ((width - 140) / Math.max(visibleLanes.length - 1, 1));
    items.forEach((node, index) => {
      const y = 55 + index * Math.max(128, (height - 110) / Math.max(items.length, 1));
      positions[node.id] = { x, y };
    });
  });
  const pathFor = (edge) => {
    const source = positions[edge.source];
    const target = positions[edge.target];
    if (!source || !target) return "";
    const sx = source.x + 82;
    const sy = source.y + 38;
    const tx = target.x + 82;
    const ty = target.y + 38;
    const mid = Math.abs(tx - sx) / 2;
    return `<path d="M ${sx} ${sy} C ${sx + mid} ${sy}, ${tx - mid} ${ty}, ${tx} ${ty}" class="topology-link ${esc(healthState(edge.status).key)}"></path>`;
  };
  const labelFor = (edge) => {
    const source = positions[edge.source];
    const target = positions[edge.target];
    if (!source || !target) return "";
    const x = (source.x + target.x) / 2 + 82;
    const y = (source.y + target.y) / 2 + 26;
    const requests = edge.metrics?.requests ? ` - ${num(edge.metrics.requests)} req` : "";
    return `<text x="${x}" y="${y}" class="topology-link-label">${esc(edge.label || edge.type)}${requests}</text>`;
  };
  const iconFor = (type) => ({
    host: "H",
    network_asset: "SW",
    process_group: "P",
    service: "S",
    application: "APP",
    external_service: "EXT",
  }[type] || "N");
  return `<div class="topology-map" style="--map-width:${width}px; --map-height:${height}px">
    <svg viewBox="0 0 ${width} ${height}" class="topology-svg" role="img" aria-label="Mapa de topologia">
      <defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" class="topology-arrow"></path></marker></defs>
      ${edges.map(pathFor).join("")}
      ${edges.slice(0, 30).map(labelFor).join("")}
    </svg>
    ${visibleLanes.map((lane) => `<div class="topology-lane-label" style="left:${positions[laneNodes.get(lane)[0].id].x}px">${esc(topologyNodeType[lane] || lane)}</div>`).join("")}
    ${nodes.map((node) => {
      const pos = positions[node.id] || { x: 40, y: 40 };
      const health = healthState(node.status).key;
      return `<button class="topology-map-node ${esc(node.type)} ${health}" style="left:${pos.x}px; top:${pos.y}px" title="${esc(node.label)}" type="button">
        <span>${esc(iconFor(node.type))}</span>
        <strong>${esc(node.label || node.id)}</strong>
        ${node.subtitle ? `<small>${esc(node.subtitle)}</small>` : ""}
        ${topologyMetricChips(node.metrics)}
      </button>`;
    }).join("")}
  </div>`;
}

async function renderTopologies() {
  const filters = state.filters.topologies || {};
  const scope = filters.scope || state.topologyScope || "network";
  const params = { ...filters };
  delete params.scope;
  const data = await api(`/api/v1/topologies/${scope}${queryString(params)}`);
  state.topologyScope = scope;
  const nodeById = Object.fromEntries((data.nodes || []).map((node) => [node.id, node]));
  const sampleEdges = (data.edges || []).slice(0, 80);
  render(`<section class="grid">
    <article class="card">
      <div class="section-header">
        <div>
          <h3>Topologias</h3>
          <p class="muted">Flows baseados em dados reais coletados por agentes, gateways, SNMP e OpenTelemetry. Campos ainda nao coletados aparecem como observacao tecnica, sem mock.</p>
        </div>
      </div>
      <div class="topology-tabs">${topologyScopes.map(([key, label]) => `<button class="button ${key === scope ? "secondary" : "ghost"} topology-tab" data-scope="${key}" type="button">${label}</button>`).join("")}</div>
      <form id="topologies-filters" class="filter-panel">
        <input type="hidden" name="scope" value="${esc(scope)}">
        <label>Busca<input name="q" value="${esc(filterValue("topologies", "q"))}" placeholder="host, servico, IP, aplicacao"></label>
        <label>Host<input name="host" value="${esc(filterValue("topologies", "host"))}"></label>
        <label>Servico<input name="service" value="${esc(filterValue("topologies", "service"))}"></label>
        <label>Aplicacao<input name="application" value="${esc(filterValue("topologies", "application"))}"></label>
        <label>Timeframe<select name="timeframe">${timeframes.map(([key, label]) => `<option value="${key}" ${filterValue("topologies", "timeframe", "24h") === key ? "selected" : ""}>${label}</option>`).join("")}</select></label>
        <label>Inicio<input name="start" type="datetime-local" value="${esc(filterValue("topologies", "start"))}"></label>
        <label>Fim<input name="end" type="datetime-local" value="${esc(filterValue("topologies", "end"))}"></label>
        <button class="button ghost" type="submit">Filtrar</button>
        <button class="button ghost clear-filters" data-view="topologies" type="button">Limpar</button>
      </form>
    </article>
    <section class="grid cards">
      ${metricTile("Nos", num(data.summary?.nodes))}
      ${metricTile("Conexoes", num(data.summary?.edges))}
      ${metricTile("Hosts", num(data.summary?.hosts))}
      ${metricTile("Servicos", num(data.summary?.services))}
      ${metricTile("Externos", num(data.summary?.external))}
    </section>
    <article class="card topology-card">
      <div class="section-header">
        <div>
          <h3>${esc(topologyScopes.find(([key]) => key === scope)?.[1] || scope)}</h3>
          <p class="muted">Periodo: ${fmt(data.timeframe?.start)} ate ${fmt(data.timeframe?.end)}</p>
        </div>
      </div>
      ${topologyGraph(data, scope)}
    </article>
    <article class="card">
      <h3>Conexoes e dependencias</h3>
      ${sampleEdges.length ? `<div class="topology-edge-list">${sampleEdges.map((edge) => topologyEdgeRow(edge, nodeById)).join("")}</div>` : `<p class="muted">Nenhuma conexao real inferida ainda. Para Rede, precisamos de LLDP/CDP/connected_device via SNMP; para Servicos/Aplicacoes, traces OTLP correlacionados.</p>`}
    </article>
    ${(data.notes || []).length ? `<article class="card soft-card"><h3>Observacoes de coleta</h3>${data.notes.map((note) => `<p class="muted">${esc(note)}</p>`).join("")}</article>` : ""}
  </section>`);
  bindFilters("topologies", renderTopologies);
  $$(".topology-tab").forEach((button) => button.addEventListener("click", () => {
    state.filters.topologies = { ...(state.filters.topologies || {}), scope: button.dataset.scope };
    state.topologyScope = button.dataset.scope;
    renderTopologies();
  }));
}

async function renderSimpleTable(view, endpoint, title, headers, mapper, message) {
  const items = await api(endpoint);
  render(items.length ? `<article class="card"><h3>${title}</h3>${table(headers, items.map(mapper))}</article>` : empty(title, message));
}

async function renderTasks() {
  const tasks = await api("/api/v1/tasks");
  render(`<section class="grid"><article class="card"><div class="section-header"><div><h3>Tarefas, scans e coletas</h3><p class="muted">Clique no status para abrir logs, resultado e mensagem de falha da execucao.</p></div><button id="refresh-tasks" class="button ghost" type="button">Atualizar</button></div>${tasks.length ? table(["Nome", "Tipo", "Status", "Alvo", "Progresso", "Quando"], tasks.map((task) => [
    `<strong>${esc(task.name)}</strong><br><small class="mono">${esc(task.id || "")}</small>`,
    esc(task.type),
    `<button class="link-button task-detail-trigger" data-task-id="${esc(task.id)}" type="button">${status(task.status)}</button>`,
    esc(task.target || "-"),
    `${num(task.progress)}%`,
    fmt(task.scheduled_at || task.started_at || task.completed_at),
  ])) : `<p class="muted">Nenhuma tarefa executada ainda.</p>`}</article></section>`);
  $("#refresh-tasks").addEventListener("click", renderTasks);
  $$(".task-detail-trigger").forEach((button) => button.addEventListener("click", () => renderTaskDetail(button.dataset.taskId)));
}

async function renderTaskDetail(taskId) {
  const task = await api(`/api/v1/tasks/${taskId}`);
  const logRows = (task.logs || []).map((log) => [
    fmt(log.ts || log.timestamp || log.created_at),
    esc(log.level || log.status || "-"),
    esc(log.gateway_name || log.source || "-"),
    esc(log.message || log.msg || JSON.stringify(log)),
  ]);
  render(`<section class="grid"><article class="card"><div class="actions"><button id="back-tasks" class="button ghost" type="button">Voltar</button>${["pending", "running"].includes(String(task.status)) ? `<button id="cancel-task" class="button ghost" type="button">Cancelar</button>` : ""}</div><h3>${esc(task.name || task.id)}</h3><div class="detail-kpis">${metricTile("Status", status(task.status))}${metricTile("Tipo", esc(task.type || "-"))}${metricTile("Alvo", esc(task.target || "-"))}${metricTile("Progresso", `${num(task.progress)}%`)}</div>${task.error ? `<article class="soft-card card"><h3>Erro da execucao</h3><p class="message">${esc(task.error)}</p></article>` : ""}</article><article class="card"><h3>Logs da tarefa</h3>${logRows.length ? table(["Quando", "Nivel", "Origem", "Mensagem"], logRows) : `<p class="muted">Sem logs registrados para esta tarefa.</p>`}</article><article class="card"><h3>Resultado bruto</h3>${jsonBlock(task.result || {})}</article></section>`);
  $("#back-tasks").addEventListener("click", renderTasks);
  $("#cancel-task")?.addEventListener("click", async () => {
    await api(`/api/v1/tasks/${taskId}/cancel`, { method: "POST" });
    await renderTaskDetail(taskId);
  });
}

function alertRuleForm(rule = {}) {
  const selectedMetric = rule.metric || "cpu_usage";
  return `<form id="alert-rule-form" class="form-grid">
    <input name="id" type="hidden" value="${esc(rule.id || "")}">
    <label>Nome<input name="name" value="${esc(rule.name || "")}" required></label>
    <label>Entidade<select name="entity_type">${alertEntityTypes.map(([key, label]) => `<option value="${key}" ${key === (rule.entity_type || "host") ? "selected" : ""}>${label}</option>`).join("")}</select></label>
    <label>Metrica<select name="metric">${alertMetrics.map(([key, label]) => `<option value="${key}" ${key === selectedMetric ? "selected" : ""}>${label}</option>`).join("")}</select></label>
    <label>Operador<select name="condition_op">${[">", ">=", "<", "<=", "==", "!="].map((op) => `<option value="${op}" ${op === (rule.condition_op || ">") ? "selected" : ""}>${op}</option>`).join("")}</select></label>
    <label>Threshold<input name="threshold_value" type="number" step="0.01" value="${esc(rule.threshold_value ?? 80)}" required></label>
    <label>Duração (seg)<input name="duration_seconds" type="number" value="${esc(rule.duration_seconds ?? 60)}"></label>
    <label>Severidade<select name="severity">${["low", "medium", "high", "critical"].map((sev) => `<option value="${sev}" ${sev === (rule.severity || "medium") ? "selected" : ""}>${sev}</option>`).join("")}</select></label>
    <label>Supressao (seg)<input name="suppress_seconds" type="number" value="${esc(rule.suppress_seconds ?? 300)}"></label>
    <label>Entidades IDs<input name="entity_ids" value="${esc((rule.entity_ids || []).join(","))}" placeholder="opcional, separado por virgula"></label>
    <label>Tags<input name="tags_filter" value="${esc((rule.tags_filter || []).join(","))}" placeholder="opcional, separado por virgula"></label>
    <label style="grid-column:1/-1">Descricao<textarea name="description">${esc(rule.description || "")}</textarea></label>
    <label class="check-row"><input name="enabled" type="checkbox" ${rule.enabled === false ? "" : "checked"}> Regra habilitada</label>
    <label class="check-row"><input name="use_baseline" type="checkbox" ${rule.use_baseline ? "checked" : ""}> Usar baseline automatico</label>
  </form>`;
}

function alertRulePayload(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  return {
    name: data.name,
    description: data.description || null,
    entity_type: data.entity_type || "host",
    metric: data.metric || "cpu_usage",
    condition_op: data.condition_op || ">",
    threshold_value: Number(data.threshold_value || 0),
    duration_seconds: Number(data.duration_seconds || 60),
    severity: data.severity || "medium",
    enabled: form.elements.enabled.checked,
    use_baseline: form.elements.use_baseline.checked,
    suppress_seconds: Number(data.suppress_seconds || 300),
    entity_ids: String(data.entity_ids || "").split(",").map((item) => item.trim()).filter(Boolean),
    tags_filter: String(data.tags_filter || "").split(",").map((item) => item.trim()).filter(Boolean),
    channels: [],
  };
}

async function renderAlerts(editRule = null) {
  const [rules, alerts] = await Promise.all([
    api("/api/v1/alerts/rules"),
    api("/api/v1/alerts").catch(() => []),
  ]);
  const editing = editRule || {};
  render(`<section class="grid"><article class="card"><div class="section-header"><div><h3>Nova regra de alerta</h3><p class="muted">Crie regras por metricas padrao, status, logs, processos, servicos, aplicacoes, synthetics e portas de rede.</p></div></div>${alertRuleForm(editing)}<div class="actions" style="margin-top:14px"><button id="save-alert-rule" class="button primary" type="button">${editing.id ? "Salvar regra" : "Criar regra"}</button><button id="reset-alert-rule" class="button ghost" type="button">Limpar</button></div><p id="alert-rule-message" class="message"></p></article><article class="card"><h3>Regras cadastradas</h3>${rules.length ? table(["Nome", "Entidade", "Metrica", "Condicao", "Baseline", "Status", "Acoes"], rules.map((rule) => [
    esc(rule.name),
    esc(rule.entity_type),
    esc(rule.metric),
    `${esc(rule.condition_op)} ${num(rule.threshold_value)}`,
    rule.use_baseline ? "sim" : "nao",
    rule.enabled ? "habilitada" : "desabilitada",
    actionMenu([{ label: "Editar", className: "edit-alert-rule", attrs: `data-rule-id="${esc(rule.id)}"` }, { label: "Excluir", className: "delete-alert-rule", attrs: `data-rule-id="${esc(rule.id)}"` }]),
  ])) : `<p class="muted">Nenhuma regra criada ainda.</p>`}</article><article class="card"><h3>Alertas recentes</h3>${alerts.length ? table(["Quando", "Nome", "Severidade", "Entidade", "Metrica", "Valor"], alerts.slice(0, 20).map((alert) => [fmt(alert.triggered_at), esc(alert.name), esc(alert.severity), esc(alert.entity_name || alert.entity_type || "-"), esc(alert.metric || "-"), maybeNum(alert.observed_value)])) : `<p class="muted">Nenhum alerta gerado ainda.</p>`}</article></section>`);
  $("#save-alert-rule").addEventListener("click", async () => {
    const form = $("#alert-rule-form");
    const id = form.elements.id.value;
    try {
      await api(id ? `/api/v1/alerts/rules/${id}` : "/api/v1/alerts/rules", { method: id ? "PUT" : "POST", body: JSON.stringify(alertRulePayload(form)) });
      await renderAlerts();
    } catch (error) {
      $("#alert-rule-message").textContent = error.message;
    }
  });
  $("#reset-alert-rule").addEventListener("click", () => renderAlerts());
  $$(".edit-alert-rule").forEach((button) => button.addEventListener("click", () => renderAlerts(rules.find((rule) => rule.id === button.dataset.ruleId))));
  $$(".delete-alert-rule").forEach((button) => button.addEventListener("click", async () => {
    if (!confirm("Excluir esta regra de alerta?")) return;
    await api(`/api/v1/alerts/rules/${button.dataset.ruleId}`, { method: "DELETE" });
    await renderAlerts();
  }));
}

function userForm(user = {}) {
  const permissions = new Set(user.permissions || []);
  const group = user.permission_group || "viewer";
  return `<form id="user-form" class="form-grid">
    <input name="id" type="hidden" value="${esc(user.id || "")}">
    <label>Nome completo<input name="full_name" value="${esc(user.full_name || "")}" required></label>
    <label>E-mail<input name="email" type="email" value="${esc(user.email || "")}" required></label>
    <label>Usuario<input name="username" value="${esc(user.username || "")}" placeholder="opcional"></label>
    <label>Senha${user.id ? " (opcional)" : ""}<input name="password" type="password" autocomplete="new-password" ${user.id ? "" : "required"}></label>
    <label>Grupo<select name="permission_group">${Object.entries(permissionGroups).map(([key, item]) => `<option value="${key}" ${key === group ? "selected" : ""}>${esc(item.label)}</option>`).join("")}</select></label>
    <label>Papel<select name="role">${["viewer", "operator", "admin"].map((role) => `<option value="${role}" ${role === (user.role || permissionGroups[group]?.role || "viewer") ? "selected" : ""}>${role}</option>`).join("")}</select></label>
    <label class="check-row"><input name="active" type="checkbox" ${user.active === false ? "" : "checked"}> Usuario ativo</label>
    <div style="grid-column:1/-1"><p class="muted">Funcionalidades permitidas</p><div class="pill-row">${TENANT_VIEWS.map((view) => `<label class="pill-check"><input type="checkbox" name="permissions" value="${esc(view)}" ${permissions.has(view) ? "checked" : ""}>${esc(titleMap[view] || view)}</label>`).join("")}</div></div>
  </form>`;
}

function userPayload(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const permissions = [...form.querySelectorAll('input[name="permissions"]:checked')].map((input) => input.value);
  const payload = {
    full_name: data.full_name,
    email: data.email,
    username: data.username || data.email,
    role: data.role || "viewer",
    permission_group: data.permission_group || "viewer",
    permissions,
    active: form.elements.active.checked,
  };
  if (data.password) payload.password = data.password;
  return payload;
}

async function renderUsers(editUser = null) {
  const payload = await api("/api/v1/users");
  const users = Array.isArray(payload) ? payload : (payload.users || payload.items || payload.results || []);
  const editing = editUser || {};
  render(`<section class="grid"><article class="card"><div class="section-header"><div><h3>${editing.id ? "Editar usuario" : "Novo usuario"}</h3><p class="muted">Crie usuarios por grupo e selecione quais funcionalidades do menu ficam permitidas.</p></div></div>${userForm(editing)}<div class="actions" style="margin-top:14px"><button id="save-user" class="button primary" type="button">${editing.id ? "Salvar usuario" : "Criar usuario"}</button><button id="reset-user" class="button ghost" type="button">Limpar</button></div><p id="user-message" class="message"></p></article><article class="card"><h3>Usuarios</h3>${users.length ? table(["Usuario", "Nome", "Email", "Grupo", "Papel", "Status", "Acoes"], users.map((item) => [
    esc(item.username),
    esc(item.full_name || "-"),
    esc(item.email),
    esc(permissionGroups[item.permission_group]?.label || item.permission_group || "-"),
    esc(item.role),
    item.active ? "ativo" : "inativo",
    actionMenu([{ label: "Editar", className: "edit-user", attrs: `data-user-id="${esc(item.id)}"` }, { label: "Excluir", className: "delete-user", attrs: `data-user-id="${esc(item.id)}"`, disabled: item.id === state.currentUser?.id }]),
  ])) : `<p class="muted">Nenhum usuario cadastrado.</p>`}</article></section>`);
  $("#save-user").addEventListener("click", async () => {
    const form = $("#user-form");
    const id = form.elements.id.value;
    try {
      await api(id ? `/api/v1/users/${id}` : "/api/v1/users", { method: id ? "PUT" : "POST", body: JSON.stringify(userPayload(form)) });
      await renderUsers();
    } catch (error) {
      $("#user-message").textContent = error.message;
    }
  });
  $("#reset-user").addEventListener("click", () => renderUsers());
  $$(".edit-user").forEach((button) => button.addEventListener("click", () => renderUsers(users.find((item) => item.id === button.dataset.userId))));
  $$(".delete-user").forEach((button) => button.addEventListener("click", async () => {
    if (!confirm("Excluir este usuario?")) return;
    await api(`/api/v1/users/${button.dataset.userId}`, { method: "DELETE" });
    await renderUsers();
  }));
}

async function renderNetworkAssets() {
  const [items, gatewayPayload] = await Promise.all([
    api(`/api/v1/network-assets${queryString(state.filters.network || {})}`),
    api("/api/v1/gateways").catch(() => []),
  ]);
  const gateways = Array.isArray(gatewayPayload) ? gatewayPayload : (gatewayPayload.items || gatewayPayload.gateways || []);
  const gatewayOptions = [
    `<option value="">Automatico pelo tenant</option>`,
    ...gateways.map((gateway) => `<option value="${esc(gateway.id)}">${esc(gateway.name || gateway.hostname || gateway.id)} - ${esc(gateway.type || "gateway")} - ${esc(gateway.status || "unknown")}</option>`),
  ].join("");
  render(`<section class="grid"><article class="card"><div class="section-header"><div><h3>Discovery e ativos de rede</h3><p class="muted">Varredura real por CIDR. Pode executar via qualquer gateway online do tenant, inclusive Windows, desde que ele tenha conectividade com a rede alvo.</p></div></div><form id="network-discovery-form" class="form-grid"><label>CIDR<input name="cidr" placeholder="192.168.0.0/24" required></label><label>Gateway executor<select name="gateway_id">${gatewayOptions}</select></label><label style="grid-column:1/-1">Portas<input name="ports" value="${defaultDiscoveryPorts.join(",")}"></label><label>SNMP community<input name="snmp_community" value="public"></label><label>Timeout ms<input name="timeout_ms" type="number" value="350"></label></form><div class="actions" style="margin-top:14px"><button id="start-network-discovery" class="button primary" type="button">Iniciar discovery</button><button id="refresh-network-assets" class="button ghost" type="button">Atualizar lista</button></div><p id="network-message" class="message"></p></article><article class="card"><h3>Teste SNMP GET</h3><p class="muted">Execute um GET real via gateway do tenant. Use para validar community, ACL e resposta UDP/161 antes do discovery.</p><form id="snmp-get-form" class="form-grid"><label>IP<input name="ip" placeholder="192.168.0.50" required></label><label>Gateway executor<select name="gateway_id">${gatewayOptions}</select></label><label>Community<input name="snmp_community" value="public"></label><label>OID<input name="oid" value="1.3.6.1.2.1.1.1.0"></label><label>Porta<input name="snmp_port" type="number" value="161"></label></form><div class="actions" style="margin-top:14px"><button id="run-snmp-get" class="button primary" type="button">Executar SNMP GET</button></div><p id="snmp-get-message" class="message"></p></article><article class="card"><div class="section-header"><div><h3>Ativos</h3><p class="muted">Os ativos permanecem visiveis; use os tres pontos/acoes para coletar SNMP ou abrir detalhes.</p></div></div>${filterPanel("network", [{ name: "q", label: "Host/IP/Fabricante" }, { name: "group", label: "Grupo" }, { name: "asset_type", label: "Tipo" }, { name: "manufacturer", label: "Fabricante" }], false)}${items.length ? table(["Host", "Grupo", "Tipo", "SNMP", "SYSLOG", "Fabricante", "Portas", "Acoes"], items.map((asset) => [
    `<button class="link-button network-detail-trigger" data-asset-id="${esc(asset.id)}" type="button"><strong>${esc(asset.hostname || "-")}</strong></button><br><small>${esc(asset.ip)}</small>`,
    esc(asset.group || "-"),
    esc(asset.asset_type || "-"),
    asset.snmp_enabled ? "ativo" : "nao",
    asset.syslog_enabled ? "habilitado" : "nao",
    esc(asset.manufacturer || "-"),
    `${num(asset.port_count)}<br><small>${esc((asset.features || []).slice(0, 6).join(", "))}</small>`,
    asset.snmp_enabled ? `<button class="button ghost snmp-refresh" data-asset-id="${esc(asset.id)}" type="button">Coletar SNMP</button>` : `<span class="muted">Sem SNMP</span>`,
  ])) : `<p class="muted">Nenhum ativo de rede descoberto ainda.</p>`}</article></section>`);
  bindFilters("network", renderNetworkAssets);
  $("#start-network-discovery").addEventListener("click", async () => {
    const form = Object.fromEntries(new FormData($("#network-discovery-form")).entries());
    try {
      const payload = {
        cidr: form.cidr,
        ports: form.ports.split(",").map((item) => Number(item.trim())).filter(Boolean),
        gateway_id: form.gateway_id || undefined,
        snmp_community: form.snmp_community || "public",
        timeout_ms: Number(form.timeout_ms || 350),
      };
      const response = await api("/api/v1/network-assets/discovery", { method: "POST", body: JSON.stringify(payload) });
      $("#network-message").textContent = `Discovery agendado. Task: ${response.task_id}`;
    } catch (error) {
      $("#network-message").textContent = error.message;
    }
  });
  $("#refresh-network-assets").addEventListener("click", () => renderNetworkAssets());
  $("#run-snmp-get").addEventListener("click", async () => {
    const form = Object.fromEntries(new FormData($("#snmp-get-form")).entries());
    try {
      const response = await api("/api/v1/network-assets/snmp-get", {
        method: "POST",
        body: JSON.stringify({
          ip: form.ip,
          oid: form.oid || "1.3.6.1.2.1.1.1.0",
          gateway_id: form.gateway_id || undefined,
          snmp_community: form.snmp_community || "public",
          snmp_port: Number(form.snmp_port || 161),
        }),
      });
      $("#snmp-get-message").textContent = `SNMP GET agendado. Task: ${response.task_id}${response.gateway_name ? ` via ${response.gateway_name}` : ""}`;
    } catch (error) {
      $("#snmp-get-message").textContent = error.message;
    }
  });
  $$(".snmp-refresh").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        const response = await api(`/api/v1/network-assets/${button.dataset.assetId}/snmp-refresh`, { method: "POST" });
        $("#network-message").textContent = `SNMP refresh agendado. Task: ${response.task_id}`;
      } catch (error) {
        $("#network-message").textContent = error.message;
      }
    });
  });
  $$(".network-detail-trigger").forEach((button) => button.addEventListener("click", () => renderNetworkAssetDetail(button.dataset.assetId)));
}

async function renderNetworkAssetDetail(assetId) {
  if (isUiV2()) {
    await renderNetworkAssetDetailV2(assetId);
    return;
  }
  closeInspector();
  const data = await api(`/api/v1/network-assets/${assetId}/detail`);
  const asset = data.asset;
  const ports = data.ports || [];
  render(`<section class="entity-detail"><article class="detail-hero card"><div class="detail-hero-main"><p class="eyebrow">Ativo de rede</p><h2>${esc(asset.hostname || asset.ip)}</h2><p class="muted">${esc(asset.manufacturer || "-")} ${esc(asset.os_firmware || "")}</p><div class="actions"><button id="back-network" class="button ghost" type="button">Voltar para ativos</button></div></div><div class="detail-health">${healthPill(asset.status)}<small>Ultima coleta<br><strong>${fmt(asset.last_poll || asset.last_scan)}</strong></small></div></article><article class="card detail-kpis">${metricTile("IP", esc(asset.ip))}${metricTile("Tipo", esc(asset.asset_type || "-"))}${metricTile("SNMP", asset.snmp_enabled ? "ativo" : "nao")}${metricTile("SYSLOG", asset.syslog_enabled ? "habilitado" : "nao")}${metricTile("Portas", `${num(asset.ports_up)} up / ${num(asset.ports_down)} down`, `${num(asset.port_count)} total`)}</article><article class="card"><h3>Portas e interfaces SNMP</h3>${ports.length ? table(["#", "Nome", "Descricao", "Status", "Velocidade", "RX/TX", "Erros"], ports.map((port) => [num(port.port_number), esc(port.name || "-"), esc(port.description || "-"), status(port.status), `${num(port.speed_mbps)} Mbps`, `${bytes(port.rx_bytes)} / ${bytes(port.tx_bytes)}`, `${num(port.rx_errors)} / ${num(port.tx_errors)}`])) : `<p class="muted">Nenhuma porta coletada ainda. Execute Coletar SNMP no ativo após atualizar o gateway.</p>`}</article></section>`);
  const portTable = ports.length
    ? table(["#", "Nome", "Descricao", "Status", "Velocidade", "Utilizacao", "RX/TX", "Erros/Drops"], ports.map((port, index) => [
      num(port.port_number),
      `<button class="link-button network-port-detail" data-port-index="${index}" type="button">${esc(port.name || "-")}</button>`,
      esc(port.description || "-"),
      status(port.status),
      `${num(port.speed_mbps)} Mbps`,
      maybeNum(port.utilization, "%"),
      `${bytes(port.rx_bytes)} / ${bytes(port.tx_bytes)}`,
      `${num(port.rx_errors)} / ${num(port.tx_errors)} / ${num(port.rx_drops)} / ${num(port.tx_drops)}`,
    ]))
    : `<p class="muted">Nenhuma porta coletada ainda. Execute Coletar SNMP no ativo apos atualizar o gateway.</p>`;
  render(`<section class="entity-detail"><article class="detail-hero card"><div class="detail-hero-main"><p class="eyebrow">Ativo de rede</p><h2>${esc(asset.hostname || asset.ip)}</h2><p class="muted">${esc(asset.manufacturer || "-")} ${esc(asset.os_firmware || "")}</p><div class="actions"><button id="back-network" class="button ghost" type="button">Voltar para ativos</button></div></div><div class="detail-health">${healthPill(asset.status)}<small>Ultima coleta<br><strong>${fmt(asset.last_poll || asset.last_scan)}</strong></small></div></article><article class="card detail-kpis">${metricTile("IP", esc(asset.ip))}${metricTile("Tipo", esc(asset.asset_type || "-"))}${metricTile("SNMP", asset.snmp_enabled ? "ativo" : "nao")}${metricTile("SYSLOG", asset.syslog_enabled ? "habilitado" : "nao")}${metricTile("Portas", `${num(asset.ports_up)} up / ${num(asset.ports_down)} down`, `${num(asset.port_count)} total`)}</article><article class="card"><h3>Portas e interfaces SNMP</h3>${portTable}</article></section>`);
  $("#back-network").addEventListener("click", () => renderNetworkAssets());
  $$(".network-port-detail").forEach((button) => button.addEventListener("click", () => {
    const port = ports[Number(button.dataset.portIndex || 0)] || {};
    openInspector({ title: port.name || `Porta ${port.port_number || ""}`, eyebrow: "Detalhes da porta", body: networkPortInspector(port) });
  }));
}

function assetPropertiesInspector(asset) {
  const general = {
    hostname: asset.hostname || "-",
    ip: asset.ip || "-",
    tipo: asset.asset_type || "-",
    fabricante: asset.manufacturer || "-",
    os_firmware: asset.os_firmware || "-",
    snmp: asset.snmp_enabled ? "ativo" : "nao",
    syslog: asset.syslog_enabled ? "habilitado" : "nao",
    ultima_varredura: asset.last_scan ? fmt(asset.last_scan) : "-",
    ultima_coleta_snmp: asset.last_poll ? fmt(asset.last_poll) : "-",
  };
  const ports = {
    total: asset.port_count ?? "-",
    up: asset.ports_up ?? "-",
    down: asset.ports_down ?? "-",
  };
  return `${kvTable("Geral", general)}${kvTable("Portas", ports)}`;
}

function networkPortInspector(port) {
  return `${kvTable("Identificacao", {
    indice: port.port_number ?? "-",
    nome: port.name || "-",
    descricao: port.description || "-",
    status: port.status || "-",
    velocidade_mbps: port.speed_mbps ?? "-",
    duplex: port.duplex || "-",
    vlan: port.vlan || "-",
    dispositivo_conectado: port.connected_device || "-",
  })}${kvTable("Trafego e saude", {
    utilizacao_percentual: port.utilization ?? "-",
    rx_bytes: bytes(port.rx_bytes),
    tx_bytes: bytes(port.tx_bytes),
    rx_packets: port.rx_packets ?? "-",
    tx_packets: port.tx_packets ?? "-",
    rx_errors: port.rx_errors ?? "-",
    tx_errors: port.tx_errors ?? "-",
    rx_drops: port.rx_drops ?? "-",
    tx_drops: port.tx_drops ?? "-",
  })}`;
}

async function renderNetworkAssetDetailV2(assetId) {
  const data = await api(`/api/v1/network-assets/${assetId}/detail`);
  const asset = data.asset;
  const ports = data.ports || [];

  render(`
    <section class="entity-detail v2">
      <article class="detail-hero card v2-hero">
        <div class="v2-hero-main">
          <p class="eyebrow">Ativos de rede <span class="muted">/</span> ${esc(asset.hostname || asset.ip)}</p>
          <div class="v2-title-row">
            <h2>${esc(asset.hostname || asset.ip)}</h2>
            <span class="tag">${esc(asset.asset_type || "ativo")}</span>
            <span class="status">${healthDot(asset.status)} ${esc(asset.status || "offline")}</span>
          </div>
          <p class="muted">${esc(asset.manufacturer || "-")} ${asset.os_firmware ? `- ${esc(asset.os_firmware)}` : ""} ${asset.ip ? `- ${esc(asset.ip)}` : ""}</p>
          <div class="actions v2-actions">
            <button class="button ghost v2-open-props" type="button">Propriedades</button>
            <button id="back-network" class="button ghost" type="button">Voltar</button>
          </div>
        </div>
        <div class="v2-hero-kpis">
          ${metricTile("SNMP", asset.snmp_enabled ? "ativo" : "nao", "coleta via gateway")}
          ${metricTile("SYSLOG", asset.syslog_enabled ? "habilitado" : "nao", "listener no gateway")}
          ${metricTile("Portas up", num(asset.ports_up), `${num(asset.port_count)} total`)}
          ${metricTile("Ultima coleta", fmt(asset.last_poll || asset.last_scan), "poll/scan")}
        </div>
      </article>

      <article class="card">
        <div class="section-header">
          <div>
            <h3>Portas e interfaces (SNMP)</h3>
            <p class="muted">Status, velocidade, throughput e erros.</p>
          </div>
        </div>
        ${ports.length ? table(
          ["#", "Nome", "Descricao", "Status", "Velocidade", "Utilizacao", "RX/TX", "Erros/Drops"],
          ports.map((port, index) => [
            num(port.port_number),
            `<button class="link-button network-port-detail" data-port-index="${index}" type="button">${esc(port.name || "-")}</button>`,
            esc(port.description || "-"),
            status(port.status),
            `${num(port.speed_mbps)} Mbps`,
            maybeNum(port.utilization, "%"),
            `${bytes(port.rx_bytes)} / ${bytes(port.tx_bytes)}`,
            `${num(port.rx_errors)} / ${num(port.tx_errors)} / ${num(port.rx_drops)} / ${num(port.tx_drops)}`,
          ])
        ) : `<p class="muted">Nenhuma porta coletada ainda.</p>`}
      </article>
    </section>
  `);

  openInspector({
    title: asset.hostname || asset.ip || "Ativo",
    eyebrow: "Propriedades do ativo",
    body: assetPropertiesInspector(asset),
  });

  $("#back-network").addEventListener("click", () => renderNetworkAssets());
  $$(".network-port-detail").forEach((button) => button.addEventListener("click", () => {
    const port = ports[Number(button.dataset.portIndex || 0)] || {};
    openInspector({ title: port.name || `Porta ${port.port_number || ""}`, eyebrow: "Detalhes da porta", body: networkPortInspector(port) });
  }));
  $$(".v2-open-props").forEach((button) => button.addEventListener("click", () => openInspector({
    title: asset.hostname || asset.ip || "Ativo",
    eyebrow: "Propriedades do ativo",
    body: assetPropertiesInspector(asset),
  })));
}

async function renderProcessesLegacy() {
  const items = await api(`/api/v1/process-groups${queryString(state.filters.processes || {})}`);
  render(`<article class="card"><div class="section-header"><div><h3>Grupos de processos</h3><p class="muted">Agrupamento real por processos identificados nos snapshots dos agentes. Ex.: java/tomcat/node/python distribuídos em vários hosts.</p></div></div>${filterPanel("processes", [{ name: "host", label: "Host/IP" }, { name: "q", label: "Processo" }, { name: "sort", label: "Ordenar", placeholder: "instances | cpu | memory" }], false)}${items.length ? table(["Grupo", "Instancias", "Hosts", "Tecnologias", "CPU", "Memoria", "Servicos"], items.map((item) => [esc(item.name), num(item.instances), esc((item.hosts || []).join(", ") || "-"), esc((item.technologies || []).join(", ") || "-"), `${num(item.cpu_usage)}%`, `${num(item.memory_usage)}%`, num(item.services_count)])) : `<p class="muted">Nenhum processo real recebido ainda. Atualize os agentes para enviar snapshots de processos.</p>`}</article>`);
  bindFilters("processes", renderProcesses);
}

async function renderServicesLegacy() {
  const items = await api(`/api/v1/services${queryString(state.filters.services || { timeframe: "24h" })}`);
  render(`<article class="card"><div class="section-header"><div><h3>Servicos</h3><p class="muted">Servicos identificados por traces reais. O menu de acoes prepara habilitacao de OTLP/logs/IDS/vulnerabilidades por tecnologia suportada.</p></div></div>${filterPanel("services", [{ name: "host", label: "Host" }, { name: "service", label: "Servico" }, { name: "q", label: "Contexto" }])}${items.length ? table(["Servico", "Requests", "Erros", "Latencia media", "Tecnologia", "Monitoramento", "Hosts", "Acoes"], items.map((service) => [esc(service.name), num(service.requests), num(service.errors), `${num(service.avg_duration_ms)} ms`, esc(service.technology || "-"), esc(service.monitoring_mode || "-"), esc((service.hosts || []).join(", ") || "-"), actionMenu([{ label: "Propriedades" }, { label: "Habilitar OTLP", disabled: !["java", "nodejs", "python", "dotnet", "otel"].includes(String(service.technology || "").toLowerCase()) }, { label: "Ir para logs" }])])) : `<p class="muted">Nenhum servico OTLP real recebido ainda.</p>`}</article>`);
  bindFilters("services", renderServices);
}

async function renderProcesses() {
  const items = await api(`/api/v1/process-groups${queryString(state.filters.processes || { timeframe: "24h" })}`);
  render(`<article class="card"><div class="section-header"><div><h3>Grupos de processos</h3><p class="muted">Agrupamento real por processos identificados nos snapshots dos agentes. Processos com match em traces ficam lincados aos servicos.</p></div></div>${filterPanel("processes", [{ name: "host", label: "Host/IP" }, { name: "q", label: "Processo" }, { name: "sort", label: "Ordenar", placeholder: "instances | cpu | memory" }])}${items.length ? table(["Grupo", "Instancias", "Hosts", "Tecnologias", "CPU", "Memoria", "Servicos"], items.map((item) => [esc(item.name), num(item.instances), esc((item.hosts || []).join(", ") || "-"), esc((item.technologies || []).join(", ") || "-"), `${num(item.cpu_usage)}%`, `${num(item.memory_usage)}%`, item.services_count ? `<button class="link-button process-services" data-process="${esc(item.name)}" type="button">${num(item.services_count)} relacionados</button>` : `<span class="muted">sem correlacao</span>`])) : `<p class="muted">Nenhum processo real recebido ainda. Atualize os agentes para enviar snapshots de processos.</p>`}</article>`);
  bindFilters("processes", renderProcesses);
  $$(".process-services").forEach((button) => button.addEventListener("click", () => {
    setFilter("services", "q", button.dataset.process || "");
    loadView("services");
  }));
}

async function renderServices() {
  const items = await api(`/api/v1/services${queryString(state.filters.services || { timeframe: "24h" })}`);
  render(`<article class="card"><div class="section-header"><div><h3>Servicos</h3><p class="muted">Servicos identificados por traces reais. Acoes abrem propriedades, logs, traces e URLs acessadas.</p></div></div>${filterPanel("services", [{ name: "host", label: "Host" }, { name: "service", label: "Servico" }, { name: "q", label: "Contexto" }])}${items.length ? table(["Servico", "Requests", "Erros", "Latencia media", "Tecnologia", "Monitoramento", "Hosts", "URLs", "Acoes"], items.map((service) => [esc(service.name), num(service.requests), num(service.errors), `${num(service.avg_duration_ms)} ms`, esc(service.technology || "-"), esc(service.monitoring_mode || "-"), esc((service.hosts || []).join(", ") || "-"), esc((service.urls || []).slice(0, 3).join(", ") || "-"), actionMenu([{ label: "Propriedades", className: "service-detail", attrs: `data-service="${esc(service.name)}"` }, { label: "Habilitar OTLP", className: "service-otel", attrs: `data-service="${esc(service.name)}" data-tech="${esc(service.technology || "auto")}"`, disabled: !["java", "nodejs", "python", "dotnet", "otel"].includes(String(service.technology || "").toLowerCase()) }, { label: "Ir para logs", className: "service-logs", attrs: `data-service="${esc(service.name)}"` }, { label: "Ir para traces", className: "service-traces", attrs: `data-service="${esc(service.name)}"` }])])) : `<p class="muted">Nenhum servico OTLP real recebido ainda.</p>`}</article>`);
  bindFilters("services", renderServices);
  $$(".service-detail").forEach((button) => button.addEventListener("click", () => renderServiceDetail(button.dataset.service)));
  $$(".service-logs").forEach((button) => button.addEventListener("click", () => {
    setFilter("logs", "service", button.dataset.service || "");
    loadView("logs");
  }));
  $$(".service-traces").forEach((button) => button.addEventListener("click", () => {
    setFilter("traces", "service", button.dataset.service || "");
    loadView("traces");
  }));
  $$(".service-otel").forEach((button) => button.addEventListener("click", () => {
    window.open(`/api/v1/agents/download/otel-installer?appname=${encodeURIComponent(button.dataset.service || "service")}&language=${encodeURIComponent(button.dataset.tech || "auto")}`, "_blank", "noopener");
  }));
}

async function renderServiceDetail(serviceName) {
  if (isUiV2()) {
    await renderServiceDetailV2(serviceName);
    return;
  }
  closeInspector();
  const data = await api(`/api/v1/services/detail${queryString({ name: serviceName, ...(state.filters.services || { timeframe: "24h" }) })}`);
  render(`<section class="grid"><article class="card"><div class="actions"><button id="back-services" class="button ghost" type="button">Voltar</button><button id="svc-logs" class="button ghost" type="button">Ir para logs</button><button id="svc-traces" class="button ghost" type="button">Ir para traces</button></div><h3>${esc(data.name)}</h3><div class="detail-kpis">${metricTile("Requests", num(data.requests))}${metricTile("Erros", num(data.errors))}${metricTile("Hosts", esc((data.hosts || []).join(", ") || "-"))}</div><h3>URLs acessadas</h3>${data.urls?.length ? table(["URL", "Requests"], data.urls.map((item) => [esc(item.url), num(item.requests)])) : `<p class="muted">Nenhuma URL real correlacionada a este servico.</p>`}</article><article class="card"><h3>Ultimos traces</h3>${data.traces?.length ? table(["Trace", "Nome", "Status", "Duracao"], data.traces.map((trace) => [`<button class="link-button trace-detail-trigger" data-trace-id="${esc(trace.trace_id)}" type="button">${esc(trace.trace_id)}</button>`, esc(trace.name), status(trace.status), `${num(trace.duration_ms)} ms`])) : `<p class="muted">Sem traces no periodo.</p>`}</article><article class="card"><h3>Logs correlacionados</h3>${data.logs?.length ? table(["Quando", "Nivel", "Origem", "Mensagem"], data.logs.map((log) => [fmt(log.timestamp), esc(log.level), esc(log.source || "-"), esc(log.message)])) : `<p class="muted">Sem logs correlacionados.</p>`}</article></section>`);
  $("#back-services").addEventListener("click", renderServices);
  $("#svc-logs").addEventListener("click", () => {
    setFilter("logs", "service", serviceName);
    loadView("logs");
  });
  $("#svc-traces").addEventListener("click", () => {
    setFilter("traces", "service", serviceName);
    loadView("traces");
  });
  $$(".trace-detail-trigger").forEach((button) => button.addEventListener("click", () => renderTraceDetail(button.dataset.traceId)));
}

function servicePropertiesInspector(service) {
  const general = {
    servico: service.name || "-",
    tecnologia: service.technology || "-",
    monitoramento: service.monitoring_mode || "-",
    hosts: (service.hosts || []).join(", ") || "-",
  };
  const counters = {
    requests: service.requests ?? "-",
    errors: service.errors ?? "-",
    avg_duration_ms: service.avg_duration_ms ?? "-",
  };
  const urls = (service.urls || []).slice(0, 12).map((item) => `${item.url} (${item.requests})`).join("\n") || "-";
  return `
    ${kvTable("Geral", general)}
    ${kvTable("Counters", counters)}
    <article class="card"><h3>URLs (amostra)</h3><pre><code>${esc(urls)}</code></pre></article>
  `;
}

function logInspectorBody(log) {
  const general = {
    timestamp: log.timestamp ? fmt(log.timestamp) : "-",
    level: log.level || "-",
    host: log.host_name || "-",
    host_ip: log.host_ip || "-",
    source: log.source || log.group || "-",
    service: log.service || "-",
    trace_id: log.trace_id || log.traceId || "-",
  };
  return `
    ${kvTable("Geral", general)}
    <article class="card"><h3>Mensagem</h3><pre><code>${esc(String(log.message || ""))}</code></pre></article>
  `;
}

async function renderServiceDetailV2(serviceName) {
  const data = await api(`/api/v1/services/detail${queryString({ name: serviceName, ...(state.filters.services || { timeframe: "24h" }) })}`);
  render(`
    <section class="entity-detail v2">
      <article class="detail-hero card v2-hero">
        <div class="v2-hero-main">
          <p class="eyebrow">Servicos <span class="muted">/</span> ${esc(data.name)}</p>
          <div class="v2-title-row">
            <h2>${esc(data.name)}</h2>
            ${data.technology ? `<span class="tag">${esc(data.technology)}</span>` : ""}
            ${data.monitoring_mode ? `<span class="tag">${esc(data.monitoring_mode)}</span>` : ""}
          </div>
          <p class="muted">${esc((data.hosts || []).slice(0, 4).join(", ") || "Sem host correlacionado")}</p>
          <div class="actions v2-actions">
            <button class="button ghost v2-open-props" type="button">Propriedades</button>
            <button id="svc-logs" class="button ghost" type="button">Logs</button>
            <button id="svc-traces" class="button ghost" type="button">Traces</button>
            <button id="back-services" class="button ghost" type="button">Voltar</button>
          </div>
        </div>
        <div class="v2-hero-kpis">
          ${metricTile("Requests", num(data.requests), "periodo")}
          ${metricTile("Erros", num(data.errors), "periodo")}
          ${metricTile("Latencia media", data.avg_duration_ms != null ? `${num(data.avg_duration_ms)} ms` : "-", "periodo")}
          ${metricTile("Hosts", num((data.hosts || []).length), "correlacionados")}
        </div>
      </article>

      <section class="grid two">
        <article class="card">
          <div class="section-header">
            <div>
              <h3>URLs acessadas</h3>
              <p class="muted">Principais URLs vistas via traces.</p>
            </div>
          </div>
          ${data.urls?.length ? table(["URL", "Requests"], data.urls.map((item) => [esc(item.url), num(item.requests)])) : `<p class="muted">Nenhuma URL real correlacionada.</p>`}
        </article>
        <article class="card">
          <div class="section-header">
            <div>
              <h3>Ultimos traces</h3>
              <p class="muted">Clique em um trace para drill down.</p>
            </div>
          </div>
          ${data.traces?.length ? table(["Trace", "Nome", "Status", "Duracao"], data.traces.map((trace) => [`<button class="link-button trace-detail-trigger" data-trace-id="${esc(trace.trace_id)}" type="button"><span class="mono">${esc(trace.trace_id)}</span></button>`, esc(trace.name), status(trace.status), `${num(trace.duration_ms)} ms`])) : `<p class="muted">Sem traces no periodo.</p>`}
        </article>
      </section>

      <article class="card">
        <div class="section-header">
          <div>
            <h3>Logs correlacionados</h3>
            <p class="muted">Quando existir <span class="mono">trace_id</span> nos logs, eles aparecem aqui para acelerar triagem.</p>
          </div>
        </div>
        ${data.logs?.length ? table(["Quando", "Nivel", "Origem", "Mensagem"], data.logs.map((log) => [fmt(log.timestamp), esc(log.level), esc(log.source || "-"), esc(log.message)])) : `<p class="muted">Sem logs correlacionados.</p>`}
      </article>
    </section>
  `);

  openInspector({
    title: data.name || "Servico",
    eyebrow: "Propriedades do servico",
    body: servicePropertiesInspector(data),
  });

  $("#back-services").addEventListener("click", renderServices);
  $("#svc-logs").addEventListener("click", () => {
    setFilter("logs", "service", serviceName);
    loadView("logs");
  });
  $("#svc-traces").addEventListener("click", () => {
    setFilter("traces", "service", serviceName);
    loadView("traces");
  });
  $$(".v2-open-props").forEach((button) => button.addEventListener("click", () => openInspector({
    title: data.name || "Servico",
    eyebrow: "Propriedades do servico",
    body: servicePropertiesInspector(data),
  })));
  $$(".trace-detail-trigger").forEach((button) => button.addEventListener("click", () => renderTraceDetail(button.dataset.traceId)));
}

async function renderApplicationsLegacy() {
  const items = await api(`/api/v1/applications${queryString(state.filters.applications || { timeframe: "24h" })}`);
  render(`<section class="grid"><article class="card"><div class="section-header"><div><h3>Aplicacoes</h3><p class="muted">Candidatas descobertas por URLs reais em OTLP/RUM. RUM, traces, servicos, requests e erros ficam correlacionados conforme chegam dados reais.</p></div><div class="actions"><a class="button ghost" href="/api/v1/agents/download/rum-js?appname=web-app" target="_blank" rel="noreferrer">Baixar RUM app.js</a><a class="button ghost" href="/api/v1/agents/download/otel/linux?appname=web-app" target="_blank" rel="noreferrer">OTel Linux</a><a class="button ghost" href="/api/v1/agents/download/otel/windows?appname=web-app" target="_blank" rel="noreferrer">OTel Windows</a></div></div>${filterPanel("applications", [{ name: "q", label: "URL/contexto" }, { name: "service", label: "Servico" }])}${items.length ? table(["Aplicacao", "Satisfacao", "Sessoes", "Usuarios live", "Requests", "Acoes", "Erros req.", "Erros JS", "Latencia media", "Servicos"], items.map((app) => [`<button class="link-button app-detail-placeholder" type="button"><strong>${esc(app.name)}</strong></button>`, `${num(app.satisfaction_index)}%`, num(app.sessions), num(app.users_online), num(app.requests), num(app.actions), num(app.request_errors), num(app.javascript_errors), `${num(app.avg_response_ms)} ms`, esc((app.services || []).join(", ") || "-")])) : `<p class="muted">Nenhuma aplicacao candidata identificada por traces/RUM ainda.</p>`}</article><article class="card"><h3>Como ativar RUM</h3><p class="muted">Inclua o script antes de fechar o body da aplicacao web. Ele coleta navigation timing, clicks, erros JS e fetch().</p><pre><code>&lt;script src="/api/v1/agents/download/rum-js?appname=minha-app"&gt;&lt;/script&gt;</code></pre><p class="muted">A injecao automatica por agente/gateway em Nginx/Apache/IIS sera o proximo passo quando o agente detectar webservers e paths configurados.</p></article></section>`);
  bindFilters("applications", renderApplications);
  $$(".app-detail-placeholder").forEach((button) => button.addEventListener("click", () => {
    render(`<article class="card"><div class="actions"><button id="back-apps" class="button ghost" type="button">Voltar</button></div><h3>Detalhe da aplicacao</h3><p class="muted">O drill down de sessoes RUM por usuario entrara quando o coletor RUM estiver enviando sessoes, acoes, browser/OS e tempos client/server/network reais.</p></article>`);
    $("#back-apps").addEventListener("click", renderApplications);
  }));
}

async function renderApplications() {
  const items = await api(`/api/v1/applications${queryString(state.filters.applications || { timeframe: "24h" })}`);
  render(`<section class="grid"><article class="card"><div class="section-header"><div><h3>Aplicacoes</h3><p class="muted">Candidatas descobertas por URLs reais em OTLP/RUM. Voce tambem podera criar regras por URL, dominio, host, servico ou API.</p></div><div class="actions"><a class="button ghost" href="/api/v1/agents/download/rum-js?appname=web-app" target="_blank" rel="noreferrer">Baixar RUM app.js</a><a class="button ghost" href="/api/v1/agents/download/otel/linux?appname=web-app" target="_blank" rel="noreferrer">OTel Linux</a><a class="button ghost" href="/api/v1/agents/download/otel/windows?appname=web-app" target="_blank" rel="noreferrer">OTel Windows</a></div></div>${filterPanel("applications", [{ name: "q", label: "URL/contexto" }, { name: "service", label: "Servico" }])}${items.length ? table(["Aplicacao", "Satisfacao", "Sessoes", "Usuarios live", "Requests", "Acoes", "Erros req.", "Erros JS", "Latencia media", "Servicos"], items.map((app) => [`<button class="link-button app-detail-trigger" data-app-name="${esc(app.name)}" type="button"><strong>${esc(app.name)}</strong></button>`, `${num(app.satisfaction_index)}%`, num(app.sessions), num(app.users_online), num(app.requests), num(app.actions), num(app.request_errors), num(app.javascript_errors), `${num(app.avg_response_ms)} ms`, esc((app.services || []).join(", ") || "-")])) : `<p class="muted">Nenhuma aplicacao candidata identificada por traces/RUM ainda.</p>`}</article><article class="card"><h3>Regras de aplicacao</h3><p class="muted">Proximo passo: persistir regras como URL comeca/termina/contem/igual, dominio, webserver hostname, servico ou API. Hoje a API ja sugere nomes como LAS Home, LAS Protobuf e LAS Smoke a partir das URLs reais.</p><pre><code>Ex.: /las/home = LAS Home\nEx.: /las/protobuf = LAS Protobuf</code></pre></article><article class="card"><h3>Como ativar RUM</h3><p class="muted">Inclua o script antes de fechar o body da aplicacao web. Ele coleta navigation timing, clicks, erros JS e fetch().</p><pre><code>&lt;script src="/api/v1/agents/download/rum-js?appname=minha-app"&gt;&lt;/script&gt;</code></pre></article></section>`);
  bindFilters("applications", renderApplications);
  $$(".app-detail-trigger").forEach((button) => button.addEventListener("click", () => renderApplicationDetail(button.dataset.appName)));
}

async function renderApplicationDetail(appName) {
  const data = await api(`/api/v1/applications/detail${queryString({ name: appName, ...(state.filters.applications || { timeframe: "24h" }) })}`);
  render(`<section class="grid"><article class="card"><div class="actions"><button id="back-apps" class="button ghost" type="button">Voltar</button><a class="button ghost" href="/api/v1/agents/download/rum-js?appname=${encodeURIComponent(appName)}" target="_blank" rel="noreferrer">Baixar RUM</a></div><h3>${esc(data.name)}</h3>${data.message ? `<p class="muted">${esc(data.message)}</p>` : ""}<div class="detail-kpis">${metricTile("Requests", num(data.requests))}${metricTile("Erros", num(data.errors))}${metricTile("Sessoes RUM", num((data.sessions || []).length))}</div></article><article class="card"><h3>Sessoes de usuarios</h3>${data.sessions?.length ? table(["Sessao", "Usuario", "Live", "Satisfacao", "Req/Acoes/Erros"], data.sessions.map((session) => [`<span class="mono">${esc(session.session_id)}</span>`, esc(session.user_id || "-"), session.live ? "live" : "encerrada", `${num(session.satisfaction_index)}%`, `${num(session.requests_total)} / ${num(session.actions_total)} / ${num(session.errors_total)}`])) : `<p class="muted">Sem sessoes RUM suficientes ainda. Configure o app.js para iniciar UX/RUM.</p>`}</article><article class="card"><h3>Traces da aplicacao</h3>${data.traces?.length ? table(["Trace", "Servico", "Status", "URL", "Duracao"], data.traces.map((trace) => [`<button class="link-button trace-detail-trigger" data-trace-id="${esc(trace.trace_id)}" type="button">${esc(trace.trace_id)}</button>`, esc(trace.service), status(trace.status), esc(trace.url || "-"), `${num(trace.duration_ms)} ms`])) : `<p class="muted">Sem traces para esta aplicacao no periodo.</p>`}</article><article class="card"><h3>Eventos RUM</h3>${data.rum_events?.length ? table(["Quando", "Tipo", "Nome", "URL", "Duracao"], data.rum_events.map((event) => [fmt(event.timestamp), esc(event.event_type), esc(event.name || "-"), esc(event.url || "-"), `${num(event.duration_ms)} ms`])) : `<p class="muted">Sem eventos RUM para esta aplicacao.</p>`}</article></section>`);
  $("#back-apps").addEventListener("click", renderApplications);
  $$(".trace-detail-trigger").forEach((button) => button.addEventListener("click", () => renderTraceDetail(button.dataset.traceId)));
}

async function renderDatabases() {
  const items = await api(`/api/v1/databases${queryString(state.filters.databases || { timeframe: "24h" })}`);
  render(`<article class="card"><div class="section-header"><div><h3>Bancos de Dados</h3><p class="muted">Dados reais vindos de extensoes/integrações de banco e métricas OTel relacionadas a queries.</p></div></div>${filterPanel("databases", [{ name: "q", label: "Engine/host/database" }])}${items.length ? table(["Banco", "Engine", "Host", "Database", "Status", "Ultima coleta", "Metricas"], items.map((db) => [esc(db.name), esc(db.engine), esc(db.host || "-"), esc(db.database || "-"), status(db.status), fmt(db.last_check), Object.entries(db.metrics || {}).slice(0, 5).map(([key, metric]) => `${esc(key)}: ${num(metric.value)}`).join("<br>") || "-"])) : `<p class="muted">Nenhuma integracao de banco configurada ou coletada ainda. Configure PostgreSQL/MySQL/SQL Server/Oracle/Mongo/Redis em Integracoes.</p>`}</article>`);
  bindFilters("databases", renderDatabases);
}

async function renderSynthetics() {
  const items = await api(`/api/v1/synthetics${queryString(state.filters.synthetics || {})}`);
  render(`<section class="grid"><article class="card"><div class="section-header"><div><h3>Testes Sinteticos</h3><p class="muted">Crie checks reais de URL, API, SSL e jornadas Playwright para validar login, navegacao e tempo de resposta.</p></div></div>${filterPanel("synthetics", [{ name: "q", label: "Nome/URL" }, { name: "status", label: "Status" }], false)}${items.length ? table(["Teste", "Tipo", "Status", "URL", "Intervalo", "Resposta", "SSL", "Ultimo erro", "Acoes"], items.map((test) => [`<button class="link-button synthetic-detail" data-test-id="${esc(test.id)}" type="button"><strong>${esc(test.name)}</strong></button>`, esc(test.type), status(test.last_status), esc(test.url || "-"), `${num(test.interval_seconds)}s`, test.last_response_ms ? `${num(test.last_response_ms)} ms` : "-", test.latest_ssl_days_remaining == null ? "-" : `${num(test.latest_ssl_days_remaining)} dias`, esc(test.latest_error || "-"), `<button class="button ghost synthetic-run" data-test-id="${esc(test.id)}" type="button">Executar</button>`])) : `<p class="muted">Nenhum teste sintetico configurado ainda.</p>`}</article><article class="card"><h3>Novo teste sintetico</h3><p class="muted">Para fluxo de login, use tipo App Flow e informe os passos. Ex.: navegar, preencher usuario/senha, clicar, aguardar seletor e validar texto.</p><form id="synthetic-form" class="form-grid"><label>Nome<input name="name" required placeholder="Login portal cliente"></label><label>Tipo<select name="type"><option value="url_monitor">URL monitor</option><option value="api_monitor">API monitor</option><option value="ssl_check">SSL check</option><option value="app_flow">App Flow Playwright</option></select></label><label>URL<input name="url" required placeholder="https://las.soservices.com.br/login"></label><label>Metodo<select name="method"><option>GET</option><option>POST</option><option>PUT</option><option>DELETE</option></select></label><label>Intervalo segundos<input name="interval_seconds" type="number" value="60" min="30"></label><label>Timeout segundos<input name="timeout_seconds" type="number" value="30" min="5"></label><label>SSL warn dias<input name="ssl_warn_days" type="number" value="30"></label><label>SSL crit dias<input name="ssl_crit_days" type="number" value="7"></label><label style="grid-column:1/-1">Descricao<textarea name="description" placeholder="Objetivo do teste, aplicacao relacionada, criticidade"></textarea></label><label style="grid-column:1/-1">Headers JSON<textarea name="headers" placeholder='{"Content-Type":"application/json"}'></textarea></label><label style="grid-column:1/-1">Body<textarea name="body" placeholder='{"usuario":"demo"}'></textarea></label><label style="grid-column:1/-1">Assertions JSON<textarea name="assertions" placeholder='[{"type":"status_code","operator":"eq","value":200},{"type":"response_time","operator":"lt","value":2000}]'></textarea></label><label style="grid-column:1/-1">Passos App Flow JSON<textarea name="flow_steps" placeholder='[{"action":"navigate","url":"https://site/login"},{"action":"fill","selector":"#user","value":"demo"},{"action":"fill","selector":"#password","value":"senha"},{"action":"click","selector":"button[type=submit]"},{"action":"wait","selector":".dashboard"}]'></textarea></label><label><input type="checkbox" name="enabled" checked style="width:auto; margin-right:8px">Habilitado</label><label><input type="checkbox" name="alert_on_failure" checked style="width:auto; margin-right:8px">Alertar em falha</label></form><div class="actions" style="margin-top:14px"><button id="save-synthetic" class="button primary" type="button">Criar teste</button></div><p id="synthetic-message" class="message"></p></article><article class="card soft-card"><h3>Modelos rapidos</h3><div class="actions"><button class="button ghost synthetic-template" data-template="url" type="button">URL 200 OK</button><button class="button ghost synthetic-template" data-template="ssl" type="button">SSL</button><button class="button ghost synthetic-template" data-template="login" type="button">Login App Flow</button></div><p class="muted">Os modelos preenchem o formulario e podem ser ajustados antes de salvar.</p></article></section>`);
  bindFilters("synthetics", renderSynthetics);
  $("#save-synthetic").addEventListener("click", async () => {
    const form = $("#synthetic-form");
    const values = Object.fromEntries(new FormData(form).entries());
    const parseJson = (text, fallback) => {
      const value = String(text || "").trim();
      return value ? JSON.parse(value) : fallback;
    };
    try {
      const payload = {
        ...values,
        enabled: form.enabled.checked,
        alert_on_failure: form.alert_on_failure.checked,
        interval_seconds: Number(values.interval_seconds || 60),
        timeout_seconds: Number(values.timeout_seconds || 30),
        ssl_warn_days: Number(values.ssl_warn_days || 30),
        ssl_crit_days: Number(values.ssl_crit_days || 7),
        headers: parseJson(values.headers, {}),
        assertions: parseJson(values.assertions, []),
        flow_steps: parseJson(values.flow_steps, []),
      };
      await api("/api/v1/synthetics", { method: "POST", body: JSON.stringify(payload) });
      $("#synthetic-message").textContent = "Teste sintetico criado.";
      await renderSynthetics();
    } catch (error) {
      $("#synthetic-message").textContent = `Falha ao criar teste: ${error.message}`;
    }
  });
  $$(".synthetic-run").forEach((button) => button.addEventListener("click", async () => {
    try {
      const response = await api(`/api/v1/synthetics/${button.dataset.testId}/run`, { method: "POST" });
      $("#synthetic-message").textContent = `Execucao agendada. Task: ${response.task_id}`;
    } catch (error) {
      $("#synthetic-message").textContent = error.message;
    }
  }));
  $$(".synthetic-detail").forEach((button) => button.addEventListener("click", () => renderSyntheticDetail(button.dataset.testId)));
  $$(".synthetic-template").forEach((button) => button.addEventListener("click", () => fillSyntheticTemplate(button.dataset.template)));
}

function fillSyntheticTemplate(template) {
  const form = $("#synthetic-form");
  if (!form) return;
  if (template === "ssl") {
    form.name.value = "SSL las.soservices.com.br";
    form.type.value = "ssl_check";
    form.url.value = "https://las.soservices.com.br";
    form.assertions.value = "";
    form.flow_steps.value = "";
  } else if (template === "login") {
    form.name.value = "Login aplicacao";
    form.type.value = "app_flow";
    form.url.value = "https://las.soservices.com.br/login";
    form.flow_steps.value = JSON.stringify([
      { action: "navigate", url: "https://las.soservices.com.br/login" },
      { action: "fill", selector: "input[name=username]", value: "usuario@empresa.com.br" },
      { action: "fill", selector: "input[name=password]", value: "senha" },
      { action: "click", selector: "button[type=submit]" },
      { action: "wait", selector: "#app-screen" },
    ], null, 2);
  } else {
    form.name.value = "URL health";
    form.type.value = "url_monitor";
    form.url.value = "https://api.soservices.com.br/health";
    form.assertions.value = JSON.stringify([{ type: "status_code", operator: "eq", value: 200 }, { type: "response_time", operator: "lt", value: 2000 }], null, 2);
    form.flow_steps.value = "";
  }
}

async function renderSyntheticDetail(testId) {
  if (isUiV2()) {
    await renderSyntheticDetailV2(testId);
    return;
  }
  closeInspector();
  const data = await api(`/api/v1/synthetics/${testId}/detail`);
  const test = data.test || {};
  const results = data.results || [];
  const baseline = data.baseline || {};
  const timingBaseline = data.timing_baseline || {};
  const latest = results[0] || {};
  const latestTimings = latest.timings || {};
  const timingRows = [
    ["DNS", latestTimings.dns_ms, timingBaseline.p95_dns_ms],
    ["Connect", latestTimings.connect_ms, timingBaseline.p95_connect_ms],
    ["TLS", latestTimings.tls_ms, timingBaseline.p95_tls_ms],
    ["TTFB", latestTimings.ttfb_ms, timingBaseline.p95_ttfb_ms],
    ["Download", latestTimings.download_ms, timingBaseline.p95_download_ms],
    ["Total", latestTimings.total_ms, timingBaseline.p95_total_ms],
  ];
  render(`<section class="grid">
    <article class="card">
      <div class="actions">
        <button id="back-synthetics" class="button ghost" type="button">Voltar</button>
        <button id="run-synthetic-detail" class="button primary" type="button">Executar agora</button>
      </div>
      <h3>${esc(test.name)}</h3>
      <p class="muted">${esc(test.description || "Sem descricao.")}</p>
      <div class="detail-kpis">
        ${metricTile("Tipo", esc(test.type))}
        ${metricTile("Status", esc(test.last_status || "unknown"))}
        ${metricTile("Ultima execucao", fmt(test.last_check))}
        ${metricTile("Resposta", test.last_response_ms ? `${num(test.last_response_ms)} ms` : "-")}
        ${metricTile("Baseline p95", baseline.p95_response_ms ? `${num(baseline.p95_response_ms)} ms` : "-")}
        ${metricTile("Uptime", `${num(test.uptime_pct)}%`)}
      </div>
      <p><strong>URL:</strong> <span class="mono">${esc(test.url || "-")}</span></p>
      ${latest.remote_ip ? `<p class="muted">Ultimo IP remoto: <span class="mono">${esc(latest.remote_ip)}</span></p>` : ""}
    </article>
    <article class="card">
      <h3>Timing detalhado</h3>
      <p class="muted">DNS, connect e TLS sao medidos em preflight (best-effort). TTFB e total sao medidos durante a request.</p>
      ${latestTimings && Object.keys(latestTimings).length ? table(["Fase", "Ultimo (ms)", "Baseline p95 (ms)"], timingRows.map(([label, last, p95]) => [esc(label), last == null ? "-" : num(last), p95 == null ? "-" : num(p95)])) : `<p class="muted">Sem timings avancados ainda. Execute o teste para gerar.</p>`}
      ${latestTimings.bytes ? `<p class="muted">Bytes baixados: ${num(latestTimings.bytes)}</p>` : ""}
    </article>
    <article class="card">
      <h3>Historico de execucoes</h3>
      ${results.length ? table(["Quando", "Status", "HTTP", "Resposta", "SSL", "Assertions", "Steps", "Erro"], results.map((result) => [
        fmt(result.timestamp),
        status(result.status),
        esc(result.status_code || "-"),
        result.response_time_ms ? `${num(result.response_time_ms)} ms` : "-",
        result.ssl_days_remaining == null ? "-" : `${num(result.ssl_days_remaining)} dias`,
        `${num(result.assertions_passed)} ok / ${num(result.assertions_failed)} falhas`,
        result.steps_total == null ? "-" : `${num(result.steps_passed)} / ${num(result.steps_total)}`,
        esc(result.error_message || "-"),
      ])) : `<p class="muted">Ainda nao ha execucoes reais para este teste.</p>`}
    </article>
    <article class="card">
      <h3>Recursos (waterfall)</h3>
      ${(latest.resources || []).length ? table(["Recurso", "HTTP", "Total (ms)", "TTFB (ms)", "Bytes"], latest.resources.slice(0, 20).map((res) => [
        `<span class="mono">${esc(res.url || "-")}</span>`,
        esc(res.status_code || "-"),
        res.total_ms == null ? "-" : num(res.total_ms),
        res.ttfb_ms == null ? "-" : num(res.ttfb_ms),
        res.bytes == null ? "-" : num(res.bytes),
      ])) : `<p class="muted">Nenhum recurso coletado. Este detalhamento aparece em paginas HTML (URL monitor).</p>`}
    </article>
    <article class="card">
      <h3>Configuracao</h3>
      <pre><code>${esc(JSON.stringify({ assertions: test.assertions, flow_steps: test.flow_steps, headers: test.headers }, null, 2))}</code></pre>
    </article>
  </section>`);
  $("#back-synthetics").addEventListener("click", renderSynthetics);
  $("#run-synthetic-detail").addEventListener("click", async () => {
    await api(`/api/v1/synthetics/${testId}/run`, { method: "POST" });
    await renderSyntheticDetail(testId);
  });
}

function syntheticPropertiesInspector(test, baseline, timingBaseline) {
  const meta = {
    id: test.id || "-",
    type: test.type || "-",
    enabled: test.enabled ? "sim" : "nao",
    interval_seconds: test.interval_seconds ?? "-",
    timeout_seconds: test.timeout_seconds ?? "-",
    url: test.url || "-",
    alert_on_failure: test.alert_on_failure ? "sim" : "nao",
  };
  const base = {
    p95_response_ms: baseline.p95_response_ms ?? "-",
    uptime_pct: test.uptime_pct ?? "-",
  };
  const timing = {
    p95_dns_ms: timingBaseline.p95_dns_ms ?? "-",
    p95_connect_ms: timingBaseline.p95_connect_ms ?? "-",
    p95_tls_ms: timingBaseline.p95_tls_ms ?? "-",
    p95_ttfb_ms: timingBaseline.p95_ttfb_ms ?? "-",
    p95_download_ms: timingBaseline.p95_download_ms ?? "-",
    p95_total_ms: timingBaseline.p95_total_ms ?? "-",
  };
  return `
    ${kvTable("Meta", meta)}
    ${kvTable("Baseline", base)}
    ${kvTable("Timing baseline", timing)}
    <article class="card"><h3>Configuracao (JSON)</h3><pre><code>${esc(JSON.stringify({ assertions: test.assertions, flow_steps: test.flow_steps, headers: test.headers }, null, 2))}</code></pre></article>
  `;
}

async function renderSyntheticDetailV2(testId) {
  const data = await api(`/api/v1/synthetics/${testId}/detail`);
  const test = data.test || {};
  const results = data.results || [];
  const baseline = data.baseline || {};
  const timingBaseline = data.timing_baseline || {};
  const latest = results[0] || {};
  const latestTimings = latest.timings || {};
  const timingRows = [
    ["DNS", latestTimings.dns_ms, timingBaseline.p95_dns_ms],
    ["Connect", latestTimings.connect_ms, timingBaseline.p95_connect_ms],
    ["TLS", latestTimings.tls_ms, timingBaseline.p95_tls_ms],
    ["TTFB", latestTimings.ttfb_ms, timingBaseline.p95_ttfb_ms],
    ["Download", latestTimings.download_ms, timingBaseline.p95_download_ms],
    ["Total", latestTimings.total_ms, timingBaseline.p95_total_ms],
  ];

  render(`
    <section class="entity-detail v2">
      <article class="detail-hero card v2-hero">
        <div class="v2-hero-main">
          <p class="eyebrow">Synthetics <span class="muted">/</span> ${esc(test.name || "Teste")}</p>
          <div class="v2-title-row">
            <h2>${esc(test.name || "Teste")}</h2>
            <span class="tag">${esc(test.type || "-")}</span>
            <span class="status">${healthDot(test.last_status)} ${esc(test.last_status || "unknown")}</span>
          </div>
          <p class="muted">${esc(test.description || "Sem descricao.")}</p>
          <div class="actions v2-actions">
            <button class="button ghost v2-open-props" type="button">Propriedades</button>
            <button id="run-synthetic-detail" class="button primary" type="button">Executar agora</button>
            <button id="back-synthetics" class="button ghost" type="button">Voltar</button>
          </div>
        </div>
        <div class="v2-hero-kpis">
          ${metricTile("Resposta", test.last_response_ms ? `${num(test.last_response_ms)} ms` : "-", "ultima")}
          ${metricTile("Baseline p95", baseline.p95_response_ms ? `${num(baseline.p95_response_ms)} ms` : "-", "historico")}
          ${metricTile("Uptime", `${num(test.uptime_pct)}%`, "periodo")}
          ${metricTile("Ultima execucao", fmt(test.last_check), "check")}
        </div>
      </article>

      <article class="card">
        <div class="section-header">
          <div>
            <h3>Timing detalhado</h3>
            <p class="muted">DNS, connect e TLS sao medidos em preflight (best-effort). TTFB e total sao medidos durante a request.</p>
          </div>
        </div>
        ${latestTimings && Object.keys(latestTimings).length ? table(["Fase", "Ultimo (ms)", "Baseline p95 (ms)"], timingRows.map(([label, last, p95]) => [esc(label), last == null ? "-" : num(last), p95 == null ? "-" : num(p95)])) : `<p class="muted">Sem timings avancados ainda. Execute o teste para gerar.</p>`}
        ${latestTimings.bytes ? `<p class="muted">Bytes baixados: ${num(latestTimings.bytes)}</p>` : ""}
      </article>

      <article class="card">
        <div class="section-header">
          <div>
            <h3>Historico de execucoes</h3>
            <p class="muted">Disponibilidade, tempo de resposta e erros.</p>
          </div>
        </div>
        ${results.length ? table(["Quando", "Status", "HTTP", "Resposta", "SSL", "Assertions", "Steps", "Erro"], results.map((result) => [
          fmt(result.timestamp),
          status(result.status),
          esc(result.status_code || "-"),
          result.response_time_ms ? `${num(result.response_time_ms)} ms` : "-",
          result.ssl_days_remaining == null ? "-" : `${num(result.ssl_days_remaining)} dias`,
          `${num(result.assertions_passed)} ok / ${num(result.assertions_failed)} falhas`,
          result.steps_total == null ? "-" : `${num(result.steps_passed)} / ${num(result.steps_total)}`,
          esc(result.error_message || "-"),
        ])) : `<p class="muted">Ainda nao ha execucoes reais para este teste.</p>`}
      </article>

      <article class="card">
        <div class="section-header">
          <div>
            <h3>Recursos (waterfall)</h3>
            <p class="muted">Detalhamento de recursos baixados (quando aplicavel).</p>
          </div>
        </div>
        ${(latest.resources || []).length ? table(["Recurso", "HTTP", "Total (ms)", "TTFB (ms)", "Bytes"], latest.resources.slice(0, 20).map((res) => [
          `<span class="mono">${esc(res.url || "-")}</span>`,
          esc(res.status_code || "-"),
          res.total_ms == null ? "-" : num(res.total_ms),
          res.ttfb_ms == null ? "-" : num(res.ttfb_ms),
          res.bytes == null ? "-" : num(res.bytes),
        ])) : `<p class="muted">Nenhum recurso coletado.</p>`}
      </article>
    </section>
  `);

  openInspector({
    title: test.name || "Teste",
    eyebrow: "Propriedades do teste",
    body: syntheticPropertiesInspector(test, baseline, timingBaseline),
  });

  $("#back-synthetics").addEventListener("click", renderSynthetics);
  $("#run-synthetic-detail").addEventListener("click", async () => {
    await api(`/api/v1/synthetics/${testId}/run`, { method: "POST" });
    await renderSyntheticDetailV2(testId);
  });
  $$(".v2-open-props").forEach((button) => button.addEventListener("click", () => openInspector({
    title: test.name || "Teste",
    eyebrow: "Propriedades do teste",
    body: syntheticPropertiesInspector(test, baseline, timingBaseline),
  })));
}

async function renderIncidents() {
  const items = await api(`/api/v1/incidents${queryString(state.filters.incidents || { timeframe: "30d" })}`);
  render(`<article class="card"><h3>Problemas e incidentes</h3>${filterPanel("incidents", [{ name: "host", label: "Host/entidade" }, { name: "q", label: "Contexto" }, { name: "status", label: "Status" }, { name: "severity", label: "Severidade" }])}${items.length ? table(["ID", "Descricao", "Status", "Severidade", "Entidade", "Metrica", "Duracao"], items.map((incident) => [`<span class="mono">${esc(incident.id.slice(0, 8))}</span>`, `<strong>${esc(incident.name)}</strong><br><small>${esc(incident.description || "-")}</small>`, status(incident.status), esc(incident.severity || "-"), esc(incident.entity_name || incident.entity_type || "-"), esc(incident.metric || "-"), incidentDuration(incident)])) : `<p class="muted">Nenhum incidente real registrado pelo Alert Engine.</p>`}</article>`);
  bindFilters("incidents", renderIncidents);
}

async function renderSecurityLegacy() {
  const [incidents, tasks] = await Promise.all([
    api("/api/v1/incidents"),
    api("/api/v1/tasks"),
  ]);
  const securityTasks = tasks.filter((task) => ["ids_scan", "vuln_scan", "security", "network_scan"].includes(task.type));
  render(`<section class="grid two"><article class="card"><h3>Seguranca</h3><p class="muted">Visao consolidada para IDS, vulnerabilidades e eventos de seguranca reais.</p>${incidents.length ? table(["Incidente", "Status", "Severidade", "Entidade"], incidents.slice(0, 10).map((incident) => [esc(incident.name), status(incident.status), esc(incident.severity || "-"), esc(incident.entity_name || "-")])) : `<p class="muted">Nenhum incidente de seguranca registrado.</p>`}</article><article class="card"><h3>Vulnerabilidade e tasks</h3>${securityTasks.length ? table(["Task", "Tipo", "Status", "Alvo"], securityTasks.map((task) => [esc(task.name), esc(task.type), status(task.status), esc(task.target || "-")])) : `<p class="muted">Nenhuma task de IDS/vulnerabilidade executada ainda.</p>`}</article></section>`);
}

async function renderSecurity() {
  const tab = state.securityTab || "vulnerabilities";
  const params = state.filters.security || { timeframe: "30d" };
  const [vulnerabilities, ids, pentest] = await Promise.all([
    api(`/api/v1/security/vulnerabilities${queryString(params)}`),
    api(`/api/v1/security/ids${queryString(params)}`),
    api("/api/v1/security/pentest"),
  ]);
  render(`<section class="grid"><article class="card"><div class="section-header"><div><h3>Seguranca</h3><p class="muted">Scans de rede ficam em Tasks. Aqui ficam Vulnerabilidades, IDS e Pentest com drill down operacional.</p></div><div class="actions"><button class="button ghost security-tab" data-tab="vulnerabilities" type="button">Vulnerabilidades</button><button class="button ghost security-tab" data-tab="ids" type="button">IDS</button><button class="button ghost security-tab" data-tab="pentest" type="button">Pentest</button></div></div>${filterPanel("security", [{ name: "host", label: "Host/IP" }, { name: "severity", label: "Severidade" }])}</article>${tab === "vulnerabilities" ? `<article class="card"><h3>Vulnerabilidades encontradas</h3>${vulnerabilities.length ? table(["Titulo", "Severidade", "Status", "Host", "Metrica", "Quando"], vulnerabilities.map((item) => [esc(item.title), esc(item.severity || "-"), status(item.status), esc(item.host || "-"), esc(item.metric || "-"), fmt(item.triggered_at)])) : `<p class="muted">Nenhuma vulnerabilidade real encontrada no periodo.</p>`}</article>` : ""}${tab === "ids" ? `<article class="card"><h3>Seguranca IDS</h3>${ids.length ? table(["Host", "Severidade", "Ataque", "Origem", "Destino", "Tentativas", "Status"], ids.map((item) => [esc(item.host || "-"), esc(item.severity || "-"), esc(item.attack_type || item.category || "-"), esc(item.source_ip || "-"), `${esc(item.dest_ip || "-")}:${esc(item.dest_port || "-")}`, num(item.attempts), status(item.status)])) : `<p class="muted">Nenhuma anomalia IDS real identificada no periodo.</p>`}</article>` : ""}${tab === "pentest" ? `<article class="card"><h3>Seguranca Pentest</h3>${pentest.length ? table(["Task", "Status", "Alvo", "Progresso", "Inicio", "Fim"], pentest.map((task) => [esc(task.name), status(task.status), esc(task.target || "-"), `${num(task.progress)}%`, fmt(task.started_at), fmt(task.completed_at)])) : `<p class="muted">Nenhuma task de Pentest criada/executada ainda.</p>`}</article>` : ""}</section>`);
  bindFilters("security", renderSecurity);
  $$(".security-tab").forEach((button) => button.addEventListener("click", () => {
    state.securityTab = button.dataset.tab;
    renderSecurity();
  }));
}

async function renderLogs() {
  const params = { limit: 20, ...(state.filters.logs || { timeframe: "24h" }) };
  const [items, config] = await Promise.all([
    api(`/api/v1/logs${queryString(params)}`),
    api("/api/v1/logs/processing-config"),
  ]);
  const rows = items.map((log, index) => {
    const message = isUiV2()
      ? `<button class="link-button log-inspect" data-idx="${index}" type="button">${esc(trunc(log.message, 160))}</button>`
      : esc(log.message);
    return [
      fmt(log.timestamp),
      esc(log.level),
      `${esc(log.host_name || "-")}<br><small>${esc(log.host_ip || "")}</small>`,
      esc(log.source || log.group || "-"),
      esc(log.service || "-"),
      message,
    ];
  });

  render(`
    <section class="grid">
      <article class="card">
        <div class="section-header">
          <div>
            <h3>Logs reais</h3>
            <p class="muted">Exibindo inicialmente 20 linhas. Use os filtros para pesquisar por host, IP, servico, processo, source, nivel e contexto.</p>
          </div>
          <button id="open-log-monitor" class="button ghost" type="button">Criar metrica a partir da busca</button>
        </div>
        ${filterPanel("logs", [
          { name: "host", label: "Host" },
          { name: "ip", label: "IP" },
          { name: "source", label: "Source" },
          { name: "level", label: "Level" },
          { name: "service", label: "Servico/processo" },
          { name: "group", label: "Tipo/tecnologia" },
          { name: "q", label: "Contexto mensagem" },
        ])}
        ${items.length ? table(["Quando", "Nivel", "Host", "Origem", "Servico", "Mensagem"], rows) : `<p class="muted">Nenhum log encontrado para os filtros aplicados.</p>`}
      </article>

      <article class="card">
        <h3>Processamento de niveis</h3>
        <p class="muted">${esc(config.note || "")}</p>
        <form id="log-processing-form" class="feature-grid">
          ${(config.available_levels || []).map((level) => `<label class="check-row"><input type="checkbox" name="levels" value="${esc(level)}" ${(config.levels || []).includes(level) ? "checked" : ""}>${esc(level)}</label>`).join("")}
        </form>
        <div class="actions" style="margin-top:14px"><button id="save-log-processing" class="button primary" type="button">Salvar niveis processados</button></div>
        <p id="log-processing-message" class="message"></p>
      </article>

      <article id="log-monitor-card" class="card hidden">
        <h3>Nova metrica baseada em logs</h3>
        <p class="muted">A pesquisa atual vira um widget de dashboard e, opcionalmente, uma regra de alerta por contagem.</p>
        <form id="log-monitor-form" class="form-grid">
          <label>Nome<input name="name" required placeholder="Erro login portal"></label>
          <label>Visualizacao<select name="viz_type"><option value="timeseries">Linha</option><option value="area">Area</option><option value="table">Tabela</option><option value="honeycomb">Honeycomb</option><option value="gauge">Gauge</option></select></label>
          <label>Threshold count<input name="threshold_count" type="number" placeholder="10"></label>
          <label>Severidade<select name="severity"><option value="medium">media</option><option value="high">alta</option><option value="critical">critica</option><option value="low">baixa</option></select></label>
          <label><input type="checkbox" name="create_alert" style="width:auto; margin-right:8px">Criar alerta/incidente</label>
        </form>
        <div class="actions" style="margin-top:14px"><button id="save-log-monitor" class="button primary" type="button">Criar metrica</button></div>
        <p id="log-monitor-message" class="message"></p>
      </article>
    </section>
  `);
  bindFilters("logs", renderLogs);
  $("#open-log-monitor").addEventListener("click", () => $("#log-monitor-card").classList.toggle("hidden"));
  $("#save-log-processing").addEventListener("click", async () => {
    const levels = $$("#log-processing-form input[name=levels]").filter((input) => input.checked).map((input) => input.value);
    try {
      await api("/api/v1/logs/processing-config", { method: "PUT", body: JSON.stringify({ levels }) });
      $("#log-processing-message").textContent = "Configuracao salva.";
    } catch (error) {
      $("#log-processing-message").textContent = error.message;
    }
  });
  $("#save-log-monitor").addEventListener("click", async () => {
    const form = $("#log-monitor-form");
    const values = Object.fromEntries(new FormData(form).entries());
    const filters = state.filters.logs || {};
    try {
      const response = await api("/api/v1/logs/monitors", {
        method: "POST",
        body: JSON.stringify({
          name: values.name,
          viz_type: values.viz_type,
          threshold_count: values.threshold_count ? Number(values.threshold_count) : null,
          severity: values.severity,
          create_alert: form.create_alert.checked,
          query: filters.q,
          host: filters.host,
          ip: filters.ip,
          source: filters.source,
          level: filters.level,
          service: filters.service,
          group: filters.group,
          timeframe: filters.timeframe || "24h",
        }),
      });
      $("#log-monitor-message").textContent = `Metrica criada no dashboard. Widget: ${response.widget_id}`;
    } catch (error) {
      $("#log-monitor-message").textContent = error.message;
    }
  });

  if (isUiV2()) {
    $$(".log-inspect").forEach((button) => button.addEventListener("click", () => {
      const idx = Number(button.dataset.idx || 0);
      const log = items[idx];
      if (!log) return;
      openInspector({
        title: "Log",
        eyebrow: "Detalhe do log",
        body: logInspectorBody(log),
      });
    }));
  }
}

async function renderTracesLegacy() {
  const items = await api(`/api/v1/traces${queryString(state.filters.traces || { timeframe: "24h" })}`);
  render(`<section class="grid"><article class="card"><div class="section-header"><div><h3>Traces OpenTelemetry</h3><p class="muted">Traces reais recebidos por OTLP JSON/Protobuf via mTLS ou gateway.</p></div><div class="actions"><a class="button ghost" href="/api/v1/agents/download/otel/linux?appname=my-service" target="_blank" rel="noreferrer">OTel Linux</a><a class="button ghost" href="/api/v1/agents/download/otel/windows?appname=my-service" target="_blank" rel="noreferrer">OTel Windows</a><a class="button ghost" href="/api/v1/agents/download/otel-config?language=auto" target="_blank" rel="noreferrer">Docs multi linguagem</a></div></div>${filterPanel("traces", [{ name: "host", label: "Host" }, { name: "service", label: "Servico" }, { name: "status", label: "Status" }, { name: "q", label: "Trace/URL/contexto" }])}${items.length ? table(["Trace", "Servico", "Nome", "Status", "Metodo", "URL", "Duracao"], items.map((trace) => [`<span class="mono">${esc(trace.trace_id)}</span>`, esc(trace.service), esc(trace.name), status(trace.status), esc(trace.method || "-"), esc(trace.url || "-"), `${num(trace.duration_ms)} ms`])) : `<p class="muted">Nenhum trace encontrado para os filtros aplicados.</p>`}</article><article class="card"><h3>Instrumentacao automatizada</h3><p class="muted">Baixe o helper e execute no host da aplicacao. Exemplo:</p><pre><code>bash las-otel-installer-linux.sh --select all\npowershell -ExecutionPolicy Bypass -File .\\las-otel-installer-windows.ps1</code></pre><p class="muted">A automacao detecta Java, .NET, Python, Node.js, PHP e webservers, preparando assets sem reiniciar servicos automaticamente.</p></article></section>`);
  bindFilters("traces", renderTraces);
}

async function renderTraceDetail(traceId) {
  if (isUiV2()) {
    await renderTraceDetailV2(traceId);
    return;
  }
  closeInspector();
  const data = await api(`/api/v1/traces/${encodeURIComponent(traceId)}/detail`);
  const trace = data.trace || {};
  const attrs = { ...(trace.resource || {}), ...(trace.attributes || {}) };
  render(`<section class="grid"><article class="card"><div class="actions"><button id="back-traces" class="button ghost" type="button">Voltar</button><button id="trace-logs" class="button ghost" type="button">Ir para logs</button></div><h3>Trace ${esc(trace.trace_id)}</h3><div class="detail-kpis">${metricTile("Servico", esc(trace.service || "-"))}${metricTile("Host", esc(trace.host_name || "-"))}${metricTile("Status", esc(trace.status || "-"))}${metricTile("Duracao", `${num(trace.duration_ms)} ms`)}${metricTile("HTTP", `${esc(trace.method || "-")} ${esc(trace.response_code || trace.status_code || "-")}`)}${metricTile("Kind", esc(trace.kind || "-"))}</div><p class="muted">${esc(trace.url || trace.name || "-")}</p></article><article class="card"><h3>Flow da requisicao</h3>${data.flow?.length ? table(["Span", "Pai", "Servico", "Metodo/URI", "Host", "Status", "Duracao"], data.flow.map((span) => [`<span class="mono">${esc(span.span_id || "-")}</span>`, `<span class="mono">${esc(span.parent_span_id || "-")}</span>`, esc(span.service || "-"), `<strong>${esc(span.method || span.kind || "-")}</strong><br><small>${esc(span.url || span.name || "-")}</small>`, esc(span.host_name || "-"), status(span.status), `${num(span.duration_ms)} ms`])) : `<p class="muted">Sem spans suficientes para montar o flow.</p>`}</article>${kvTable("Atributos e resource do trace", attrs)}<article class="card"><h3>Spans detalhados</h3>${data.spans?.length ? table(["Span", "Servico", "Modulo/metodo", "Status", "Duracao", "Atributos"], data.spans.map((span) => [`<span class="mono">${esc(span.span_id || "-")}</span>`, esc(span.service || "-"), esc(span.name || "-"), status(span.status), `${num(span.duration_ms)} ms`, `<details><summary>Ver JSON</summary>${jsonBlock({ attributes: span.attributes, events: span.events })}</details>`])) : `<p class="muted">Sem spans detalhados alem do trace raiz.</p>`}</article><article class="card"><h3>Logs do trace</h3>${data.logs?.length ? table(["Quando", "Nivel", "Host/Servico", "Mensagem"], data.logs.map((log) => [fmt(log.timestamp), esc(log.level), esc(log.host_name || log.service || "-"), esc(log.message)])) : `<p class="muted">Nenhum log com este trace_id.</p>`}</article><article class="card"><h3>Eventos RUM correlacionados</h3>${data.rum_events?.length ? table(["Quando", "Aplicacao", "Tipo", "Nome", "Duracao"], data.rum_events.map((event) => [fmt(event.timestamp), esc(event.application || "-"), esc(event.event_type), esc(event.name || event.url || "-"), `${num(event.duration_ms)} ms`])) : `<p class="muted">Nenhum evento RUM com este trace_id.</p>`}</article></section>`);
  $("#back-traces").addEventListener("click", renderTraces);
  $("#trace-logs").addEventListener("click", () => {
    setFilter("logs", "q", traceId);
    loadView("logs");
  });
}

function tracePropertiesInspector(trace) {
  const general = {
    trace_id: trace.trace_id || "-",
    service: trace.service || "-",
    host: trace.host_name || "-",
    status: trace.status || "-",
    duration_ms: trace.duration_ms ?? "-",
    http: `${trace.method || "-"} ${trace.response_code || trace.status_code || "-"}`,
    url: trace.url || trace.name || "-",
    kind: trace.kind || "-",
  };
  const attrs = { ...(trace.resource || {}), ...(trace.attributes || {}) };
  return `${kvTable("Geral", general)}${kvTable("Atributos e resource", attrs)}`;
}

async function renderTraceDetailV2(traceId) {
  const data = await api(`/api/v1/traces/${encodeURIComponent(traceId)}/detail`);
  const trace = data.trace || {};
  render(`
    <section class="entity-detail v2">
      <article class="detail-hero card v2-hero">
        <div class="v2-hero-main">
          <p class="eyebrow">Traces <span class="muted">/</span> ${esc(trace.trace_id || traceId)}</p>
          <div class="v2-title-row">
            <h2>Trace</h2>
            <span class="tag">${esc(trace.service || "-")}</span>
            <span class="status">${healthDot(trace.status)} ${esc(trace.status || "-")}</span>
          </div>
          <p class="muted">${esc(trace.url || trace.name || "-")}</p>
          <div class="actions v2-actions">
            <button class="button ghost v2-open-props" type="button">Propriedades</button>
            <button id="trace-logs" class="button ghost" type="button">Logs</button>
            <button id="back-traces" class="button ghost" type="button">Voltar</button>
          </div>
        </div>
        <div class="v2-hero-kpis">
          ${metricTile("Duracao", trace.duration_ms != null ? `${num(trace.duration_ms)} ms` : "-", "trace raiz")}
          ${metricTile("HTTP", `${esc(trace.method || "-")} ${esc(trace.response_code || trace.status_code || "-")}`, "request")}
          ${metricTile("Host", esc(trace.host_name || "-"), "origem")}
          ${metricTile("Kind", esc(trace.kind || "-"), "span kind")}
        </div>
      </article>

      <article class="card">
        <div class="section-header">
          <div>
            <h3>Flow da requisicao</h3>
            <p class="muted">Cadeia de spans (pai/filho) com servicos e duracoes.</p>
          </div>
        </div>
        ${data.flow?.length ? table(
          ["Span", "Pai", "Servico", "Metodo/URI", "Host", "Status", "Duracao"],
          data.flow.map((span) => [
            `<span class="mono">${esc(span.span_id || "-")}</span>`,
            `<span class="mono">${esc(span.parent_span_id || "-")}</span>`,
            esc(span.service || "-"),
            `<strong>${esc(span.method || span.kind || "-")}</strong><br><small>${esc(span.url || span.name || "-")}</small>`,
            esc(span.host_name || "-"),
            status(span.status),
            `${num(span.duration_ms)} ms`,
          ])
        ) : `<p class="muted">Sem spans suficientes para montar o flow.</p>`}
      </article>

      <section class="grid two">
        <article class="card">
          <div class="section-header">
            <div>
              <h3>Spans detalhados</h3>
              <p class="muted">Atributos e eventos por span.</p>
            </div>
          </div>
          ${data.spans?.length ? table(
            ["Span", "Servico", "Modulo/metodo", "Status", "Duracao", "Atributos"],
            data.spans.map((span) => [
              `<span class="mono">${esc(span.span_id || "-")}</span>`,
              esc(span.service || "-"),
              esc(span.name || "-"),
              status(span.status),
              `${num(span.duration_ms)} ms`,
              `<details><summary>Ver JSON</summary>${jsonBlock({ attributes: span.attributes, events: span.events })}</details>`,
            ])
          ) : `<p class="muted">Sem spans detalhados alem do trace raiz.</p>`}
        </article>
        <article class="card">
          <div class="section-header">
            <div>
              <h3>Logs do trace</h3>
              <p class="muted">Logs correlacionados pelo trace_id.</p>
            </div>
          </div>
          ${data.logs?.length ? table(
            ["Quando", "Nivel", "Host/Servico", "Mensagem"],
            data.logs.map((log) => [fmt(log.timestamp), esc(log.level), esc(log.host_name || log.service || "-"), esc(log.message)])
          ) : `<p class="muted">Nenhum log com este trace_id.</p>`}
        </article>
      </section>

      <article class="card">
        <div class="section-header">
          <div>
            <h3>Eventos RUM correlacionados</h3>
            <p class="muted">Quando RUM estiver ativo, eventos podem correlacionar por trace_id.</p>
          </div>
        </div>
        ${data.rum_events?.length ? table(
          ["Quando", "Aplicacao", "Tipo", "Nome", "Duracao"],
          data.rum_events.map((event) => [fmt(event.timestamp), esc(event.application || "-"), esc(event.event_type), esc(event.name || event.url || "-"), `${num(event.duration_ms)} ms`])
        ) : `<p class="muted">Nenhum evento RUM com este trace_id.</p>`}
      </article>
    </section>
  `);

  openInspector({
    title: trace.trace_id || traceId,
    eyebrow: "Propriedades do trace",
    body: tracePropertiesInspector(trace),
  });

  $("#back-traces").addEventListener("click", renderTraces);
  $("#trace-logs").addEventListener("click", () => {
    setFilter("logs", "q", traceId);
    loadView("logs");
  });
  $$(".v2-open-props").forEach((button) => button.addEventListener("click", () => openInspector({
    title: trace.trace_id || traceId,
    eyebrow: "Propriedades do trace",
    body: tracePropertiesInspector(trace),
  })));
}

async function renderTraces() {
  const items = await api(`/api/v1/traces${queryString(state.filters.traces || { timeframe: "24h" })}`);
  render(`<section class="grid"><article class="card"><div class="section-header"><div><h3>Traces OpenTelemetry</h3><p class="muted">Traces reais recebidos por OTLP JSON/Protobuf via mTLS ou gateway. Clique no trace para drill down.</p></div><div class="actions"><a class="button ghost" href="/api/v1/agents/download/otel/linux?appname=my-service" target="_blank" rel="noreferrer">OTel Linux</a><a class="button ghost" href="/api/v1/agents/download/otel/windows?appname=my-service" target="_blank" rel="noreferrer">OTel Windows</a><a class="button ghost" href="/api/v1/agents/download/otel-config?language=auto" target="_blank" rel="noreferrer">Docs multi linguagem</a></div></div>${filterPanel("traces", [{ name: "host", label: "Host" }, { name: "service", label: "Servico" }, { name: "status", label: "Status" }, { name: "q", label: "Trace/URL/contexto" }])}${items.length ? table(["Trace", "Servico", "Nome", "Status", "Metodo", "URL", "Duracao"], items.map((trace) => [`<button class="link-button trace-detail-trigger" data-trace-id="${esc(trace.trace_id)}" type="button"><span class="mono">${esc(trace.trace_id)}</span></button>`, esc(trace.service), esc(trace.name), status(trace.status), esc(trace.method || "-"), esc(trace.url || "-"), `${num(trace.duration_ms)} ms`])) : `<p class="muted">Nenhum trace encontrado para os filtros aplicados.</p>`}</article><article class="card"><h3>Instrumentacao automatizada</h3><p class="muted">Baixe o instalador no host da aplicacao. Ele identifica Java, .NET, Python, Node.js, PHP e webservers, lista os processos e permite selecionar quais serao preparados para OTLP/RUM.</p><pre><code>bash las-otel-installer-linux.sh\npowershell -ExecutionPolicy Bypass -File .\\las-otel-installer-windows.ps1</code></pre><p class="muted">Quando nao for seguro aplicar automaticamente, o script informa o motivo e gera os passos manuais.</p></article></section>`);
  bindFilters("traces", renderTraces);
  $$(".trace-detail-trigger").forEach((button) => button.addEventListener("click", () => renderTraceDetail(button.dataset.traceId)));
}

async function renderDashboards() {
  const data = await api("/api/v1/dashboards");
  const dashboards = [...(data.system || []), ...(data.custom || [])];
  render(`<section class="grid"><article class="card"><div class="section-header"><div><h3>Dashboards</h3><p class="muted">Dashboards padroes e customizados. Widgets podem usar tabela, linhas, area, honeycomb, gauge, logs e topologia.</p></div></div>${dashboards.length ? table(["Dashboard", "Categoria", "Tipo", "Widgets", "Acoes"], dashboards.map((dashboard) => [`<strong>${esc(dashboard.name)}</strong><br><small>${esc(dashboard.description || "-")}</small>`, esc(dashboard.category || "-"), dashboard.is_system ? "padrao" : "custom", num(dashboard.widgets_count || (dashboard.widgets || []).length), `<button class="button ghost dashboard-detail" data-dashboard-id="${esc(dashboard.id)}" type="button">Abrir</button>`])) : `<p class="muted">Nenhum dashboard disponivel.</p>`}</article><article class="card"><h3>Novo dashboard</h3><form id="dashboard-form" class="form-grid"><label>Nome<input name="name" required></label><label>Categoria<select name="category"><option value="custom">custom</option><option value="host">host</option><option value="service">service</option><option value="app">app</option><option value="network">network</option><option value="database">database</option><option value="messaging">messaging</option><option value="security">security</option><option value="logs">logs</option></select></label><label>Time range<select name="time_range">${timeframes.map(([key, label]) => `<option value="${key}">${label}</option>`).join("")}</select></label><label><input type="checkbox" name="is_public" checked style="width:auto; margin-right:8px">Publico no tenant</label><label style="grid-column:1/-1">Descricao<textarea name="description"></textarea></label></form><div class="actions" style="margin-top:14px"><button id="save-dashboard" class="button primary" type="button">Criar dashboard</button></div><p id="dashboard-message" class="message"></p></article></section>`);
  $$(".dashboard-detail").forEach((button) => button.addEventListener("click", () => renderDashboardDetail(button.dataset.dashboardId)));
  $("#save-dashboard").addEventListener("click", async () => {
    const form = $("#dashboard-form");
    const payload = Object.fromEntries(new FormData(form).entries());
    payload.is_public = form.is_public.checked;
    try {
      const response = await api("/api/v1/dashboards", { method: "POST", body: JSON.stringify(payload) });
      $("#dashboard-message").textContent = `Dashboard criado: ${response.id}`;
      await renderDashboards();
    } catch (error) {
      $("#dashboard-message").textContent = error.message;
    }
  });
}

async function renderDashboardDetail(dashboardId) {
  if (isUiV2()) {
    await renderDashboardDetailV2(dashboardId);
    return;
  }
  closeInspector();
  const data = await api(`/api/v1/dashboards/${encodeURIComponent(dashboardId)}/detail`);
  render(`<section class="grid"><article class="card"><div class="actions"><button id="back-dashboards" class="button ghost" type="button">Voltar</button></div><h3>${esc(data.name)}</h3><p class="muted">${esc(data.description || "-")}</p><div class="detail-kpis">${metricTile("Categoria", esc(data.category || "-"))}${metricTile("Widgets", num((data.widgets || []).length))}${metricTile("Padrao", data.is_system ? "sim" : "nao")}</div></article><section class="grid cards">${(data.widgets || []).map((widget) => `<article class="card dashboard-widget"><span class="eyebrow">${esc(widget.viz_type)}</span><h3>${esc(widget.title)}</h3><p class="muted">${esc(widget.metric || widget.query || "-")}</p><div class="tag">${esc(widget.aggregation || "avg")}${widget.group_by ? ` por ${esc(widget.group_by)}` : ""}</div></article>`).join("") || `<article class="card"><p class="muted">Sem widgets ainda.</p></article>`}</section>${!data.is_system ? `<article class="card"><h3>Novo widget</h3><form id="widget-form" class="form-grid"><label>Titulo<input name="title" required></label><label>Visual<select name="viz_type"><option value="timeseries">Linha</option><option value="area">Area</option><option value="table">Tabela</option><option value="honeycomb">Honeycomb</option><option value="gauge">Gauge</option><option value="bar">Barra</option><option value="topology">Topologia</option></select></label><label>Metrica<input name="metric" placeholder="host.cpu_usage"></label><label>Agregacao<select name="aggregation"><option>avg</option><option>sum</option><option>max</option><option>min</option><option>count</option><option>p95</option></select></label><label>Entidade<input name="entity_type" placeholder="host|service|database|messaging"></label><label>Group by<input name="group_by" placeholder="host, service, level"></label><label style="grid-column:1/-1">Query<textarea name="query" placeholder="Opcional: query de logs/metrica"></textarea></label></form><button id="save-widget" class="button primary" type="button">Adicionar widget</button><p id="widget-message" class="message"></p></article>` : ""}</section>`);
  $("#back-dashboards").addEventListener("click", renderDashboards);
  $("#save-widget")?.addEventListener("click", async () => {
    const payload = Object.fromEntries(new FormData($("#widget-form")).entries());
    try {
      await api(`/api/v1/dashboards/${encodeURIComponent(dashboardId)}/widgets`, { method: "POST", body: JSON.stringify(payload) });
      await renderDashboardDetail(dashboardId);
    } catch (error) {
      $("#widget-message").textContent = error.message;
    }
  });
}

function dashboardPropertiesInspector(dashboard) {
  const meta = {
    id: dashboard.id || "-",
    categoria: dashboard.category || "-",
    tipo: dashboard.is_system ? "padrao" : "custom",
    time_range: dashboard.time_range || "-",
    widgets: (dashboard.widgets || []).length,
  };
  return `${kvTable("Meta", meta)}`;
}

async function renderDashboardDetailV2(dashboardId) {
  const data = await api(`/api/v1/dashboards/${encodeURIComponent(dashboardId)}/detail`);
  render(`
    <section class="entity-detail v2">
      <article class="detail-hero card v2-hero">
        <div class="v2-hero-main">
          <p class="eyebrow">Dashboards <span class="muted">/</span> ${esc(data.name)}</p>
          <div class="v2-title-row">
            <h2>${esc(data.name)}</h2>
            <span class="tag">${esc(data.category || "-")}</span>
            <span class="tag">${data.is_system ? "padrao" : "custom"}</span>
          </div>
          <p class="muted">${esc(data.description || "-")}</p>
          <div class="actions v2-actions">
            <button class="button ghost v2-open-props" type="button">Propriedades</button>
            <button id="back-dashboards" class="button ghost" type="button">Voltar</button>
          </div>
        </div>
        <div class="v2-hero-kpis">
          ${metricTile("Widgets", num((data.widgets || []).length), "no dashboard")}
          ${metricTile("Time range", esc(data.time_range || "-"), "padrao")}
          ${metricTile("Publico", data.is_public ? "sim" : "nao", "tenant")}
          ${metricTile("Sistema", data.is_system ? "sim" : "nao", "padrao")}
        </div>
      </article>

      <section class="grid cards">
        ${(data.widgets || []).map((widget) => `
          <article class="card dashboard-widget">
            <span class="eyebrow">${esc(widget.viz_type)}</span>
            <h3>${esc(widget.title)}</h3>
            <p class="muted">${esc(widget.metric || widget.query || "-")}</p>
            <div class="tag">${esc(widget.aggregation || "avg")}${widget.group_by ? ` por ${esc(widget.group_by)}` : ""}</div>
          </article>
        `).join("") || `<article class="card"><p class="muted">Sem widgets ainda.</p></article>`}
      </section>

      ${!data.is_system ? `
        <article class="card">
          <h3>Novo widget</h3>
          <form id="widget-form" class="form-grid">
            <label>Titulo<input name="title" required></label>
            <label>Visual<select name="viz_type"><option value="timeseries">Linha</option><option value="area">Area</option><option value="table">Tabela</option><option value="honeycomb">Honeycomb</option><option value="gauge">Gauge</option><option value="bar">Barra</option><option value="topology">Topologia</option></select></label>
            <label>Metrica<input name="metric" placeholder="host.cpu_usage"></label>
            <label>Agregacao<select name="aggregation"><option>avg</option><option>sum</option><option>max</option><option>min</option><option>count</option><option>p95</option></select></label>
            <label>Entidade<input name="entity_type" placeholder="host|service|database|messaging"></label>
            <label>Group by<input name="group_by" placeholder="host, service, level"></label>
            <label style="grid-column:1/-1">Query<textarea name="query" placeholder="Opcional: query de logs/metrica"></textarea></label>
          </form>
          <button id="save-widget" class="button primary" type="button">Adicionar widget</button>
          <p id="widget-message" class="message"></p>
        </article>
      ` : ""}
    </section>
  `);

  openInspector({
    title: data.name || "Dashboard",
    eyebrow: "Propriedades do dashboard",
    body: dashboardPropertiesInspector(data),
  });

  $("#back-dashboards").addEventListener("click", renderDashboards);
  $$(".v2-open-props").forEach((button) => button.addEventListener("click", () => openInspector({
    title: data.name || "Dashboard",
    eyebrow: "Propriedades do dashboard",
    body: dashboardPropertiesInspector(data),
  })));
  $("#save-widget")?.addEventListener("click", async () => {
    const payload = Object.fromEntries(new FormData($("#widget-form")).entries());
    try {
      await api(`/api/v1/dashboards/${encodeURIComponent(dashboardId)}/widgets`, { method: "POST", body: JSON.stringify(payload) });
      await renderDashboardDetailV2(dashboardId);
    } catch (error) {
      $("#widget-message").textContent = error.message;
    }
  });
}

async function renderMessaging() {
  const items = await api(`/api/v1/messaging${queryString(state.filters.messaging || { timeframe: "24h" })}`);
  render(`<article class="card"><h3>Filas e Mensageria</h3><p class="muted">Filas, topicos, namespaces, lag, mensagens e erros vindos de metricas OTel ou integracoes de mensageria.</p>${filterPanel("messaging", [{ name: "q", label: "Fila/topico/vendor/servico" }])}${items.length ? table(["Nome", "Vendor", "Namespace", "Servico", "Ultima coleta", "Metricas"], items.map((item) => [esc(item.name), esc(item.vendor || "-"), esc(item.namespace || "-"), esc(item.service || "-"), fmt(item.last_seen), Object.entries(item.metrics || {}).slice(0, 6).map(([key, metric]) => `${esc(key)}: ${num(metric.value)} ${esc(metric.unit || "")}`).join("<br>") || "-"])) : `<p class="muted">Nenhuma metrica real de mensageria encontrada ainda. Configure integracoes Kafka/RabbitMQ/SQS/Service Bus ou instrumentacao OTel com atributos messaging.*.</p>`}</article>`);
  bindFilters("messaging", renderMessaging);
}

async function renderOrchestration() {
  const items = await api(`/api/v1/orchestration${queryString(state.filters.orchestration || { timeframe: "24h" })}`);
  render(`<article class="card"><div class="section-header"><div><h3>Orquestracao</h3><p class="muted">Docker, Kubernetes, OpenShift, GKE e AKS. Dados reais vindos de agente, DaemonSet/worker e metricas OTel container/k8s.*.</p></div><div class="actions"><a class="button ghost" href="/api/v1/agents/download/docker" target="_blank" rel="noreferrer">Agente Docker</a><a class="button ghost" href="/api/v1/agents/download/k8s" target="_blank" rel="noreferrer">DaemonSet Kubernetes</a></div></div>${filterPanel("orchestration", [{ name: "q", label: "Container/pod/app/servico" }, { name: "platform", label: "Plataforma" }])}${items.length ? table(["Nome", "Plataforma", "Cluster", "Namespace", "Node", "Workload", "Servico", "Metricas"], items.map((item) => [esc(item.name), esc(item.platform || "-"), esc(item.cluster || "-"), esc(item.namespace || "-"), esc(item.node || "-"), esc(item.workload || "-"), esc(item.service || "-"), Object.entries(item.metrics || {}).slice(0, 6).map(([key, metric]) => `${esc(key)}: ${num(metric.value)} ${esc(metric.unit || "")}`).join("<br>") || "-"])) : `<p class="muted">Nenhum dado real de orquestracao ainda. Instale o agente Docker ou DaemonSet Kubernetes; ele deve identificar containers e, quando possivel, apps Java, .NET, Python, PHP, Node.js e correlacionar com processos/servicos/traces/logs.</p>`}</article>`);
  bindFilters("orchestration", renderOrchestration);
}

async function renderSettings() {
  const data = await api("/api/v1/settings");
  const channels = await api("/api/v1/settings/notification-channels");
  const user = state.currentUser || {};
  render(`<section class="grid"><article class="card"><h3>Configuracoes Tenant</h3><p class="muted">Instalacoes, gateways, tarefas, alertas e integracoes ficam agrupados aqui para manter a navegacao principal focada na operacao.</p><div class="actions"><button class="button ghost settings-shortcut" data-view="onboarding" type="button">Instalacoes</button><button class="button ghost settings-shortcut" data-view="gateways" type="button">Gateways</button><button class="button ghost settings-shortcut" data-view="agents" type="button">Agentes</button><button class="button ghost settings-shortcut" data-view="tasks" type="button">Tasks</button><button class="button ghost settings-shortcut" data-view="alerts" type="button">Alertas</button><button class="button ghost settings-shortcut" data-view="integrations" type="button">Integracoes</button><button class="button ghost settings-shortcut" data-view="users" type="button">Usuarios</button></div></article><section class="settings-grid"><article class="card"><h3>Meu perfil e senha</h3><form id="profile-form" class="form-grid"><label>Nome completo<input name="full_name" value="${esc(user.full_name || "")}"></label><label>E-mail<input name="email" type="email" value="${esc(user.email || "")}" required></label><label>Usuario<input name="username" value="${esc(user.username || "")}" required></label><label>Telefone<input name="phone" value="${esc(user.phone || "")}" placeholder="+55 11 99999-9999"></label></form><div class="actions" style="margin-top:14px"><button id="save-profile" class="button primary" type="button">Salvar perfil</button></div><p id="profile-message" class="message"></p><hr><form id="password-form" class="form-grid"><label>Senha atual<input name="current_password" type="password" autocomplete="current-password" required></label><label>Nova senha<input name="new_password" type="password" autocomplete="new-password" minlength="4" required></label><label>Confirmar nova senha<input name="confirm_password" type="password" autocomplete="new-password" minlength="4" required></label></form><div class="actions" style="margin-top:14px"><button id="change-password" class="button secondary" type="button">Alterar senha</button></div><p id="password-message" class="message"></p></article><article class="card"><h3>Configuracoes da plataforma</h3><form id="settings-form" class="form-grid"><label>Empresa<input name="company_name" value="${esc(data.settings.company_name)}" required></label><label>Nome da plataforma<input name="platform_name" value="${esc(data.settings.platform_name)}" required></label><label>URL da plataforma<input name="platform_url" value="${esc(data.settings.platform_url)}" required></label><label>URL publica<input name="public_web_url" value="${esc(data.settings.public_web_url || "")}"></label><label>SMTP host<input name="smtp_host" value="${esc(data.settings.smtp_host || "")}"></label><label>SMTP porta<input name="smtp_port" type="number" value="${esc(data.settings.smtp_port || "")}"></label><label>SMTP usuario<input name="smtp_user" value="${esc(data.settings.smtp_user || "")}"></label><label>SMTP remetente<input name="smtp_from" value="${esc(data.settings.smtp_from || "")}"></label><label>IA provider<select name="ai_provider"><option ${data.settings.ai_provider === "openai" ? "selected" : ""}>openai</option><option ${data.settings.ai_provider === "anthropic" ? "selected" : ""}>anthropic</option><option ${data.settings.ai_provider === "gemini" ? "selected" : ""}>gemini</option></select></label><label>Modelo IA<input name="ai_model" value="${esc(data.settings.ai_model || "")}"></label><label>Cor primaria<input name="theme_primary" value="${esc(data.settings.theme_primary || "#ff375f")}"></label><label>Cor secundaria<input name="theme_secondary" value="${esc(data.settings.theme_secondary || "#16233a")}"></label><label>Cor da superficie<input name="theme_surface" value="${esc(data.settings.theme_surface || "#0c1527")}"></label></form><div class="actions" style="margin-top:14px"><button id="save-settings" class="button primary" type="button">Salvar</button></div><p id="settings-message" class="message"></p></article><article class="card"><h3>Canais de notificacao</h3>${channels.length ? table(["Nome", "Tipo", "Status"], channels.map((channel) => [esc(channel.name), esc(channel.type), channel.enabled ? "habilitado" : "desabilitado"])) : `<p class="muted">Nenhum canal configurado.</p>`}<form id="channel-form" style="display:grid; gap:12px; margin-top:14px"><label>Nome<input name="name" required></label><label>Tipo<select name="type"><option>email</option><option>slack</option><option>teams</option><option>telegram</option><option>discord</option><option>webhook</option></select></label><label>Configuracao JSON<textarea name="config">{}</textarea></label><label><input type="checkbox" name="enabled" checked style="width:auto; margin-right:8px">Habilitado</label></form><div class="actions" style="margin-top:14px"><button id="save-channel" class="button secondary" type="button">Salvar canal</button></div><p id="channel-message" class="message"></p></article></section></section>`);
  $$(".settings-shortcut").forEach((button) => button.addEventListener("click", () => loadView(button.dataset.view)));
  $("#save-profile").addEventListener("click", async () => {
    const form = Object.fromEntries(new FormData($("#profile-form")).entries());
    try {
      const response = await api("/api/v1/auth/me", { method: "PUT", body: JSON.stringify(form) });
      state.currentUser = response.user || response;
      $("#profile-message").textContent = "Perfil salvo na plataforma.";
      await bootstrap();
    } catch (error) {
      $("#profile-message").textContent = error.message;
    }
  });
  $("#change-password").addEventListener("click", async () => {
    const form = Object.fromEntries(new FormData($("#password-form")).entries());
    if (form.new_password !== form.confirm_password) {
      $("#password-message").textContent = "A confirmacao da nova senha nao confere.";
      return;
    }
    try {
      await api("/api/v1/auth/change-password", { method: "POST", body: JSON.stringify({ current_password: form.current_password, new_password: form.new_password }) });
      $("#password-form").reset();
      $("#password-message").textContent = "Senha alterada e persistida na plataforma.";
    } catch (error) {
      $("#password-message").textContent = error.message;
    }
  });
  $("#save-settings").addEventListener("click", async () => {
    const form = Object.fromEntries(new FormData($("#settings-form")).entries());
    form.smtp_port = form.smtp_port ? Number(form.smtp_port) : null;
    try {
      await api("/api/v1/settings", { method: "PUT", body: JSON.stringify(form) });
      $("#settings-message").textContent = "Configuracoes salvas.";
    } catch (error) {
      $("#settings-message").textContent = error.message;
    }
  });
  $("#save-channel").addEventListener("click", async () => {
    const form = Object.fromEntries(new FormData($("#channel-form")).entries());
    try {
      form.enabled = form.enabled === "on";
      form.config = JSON.parse(form.config || "{}");
      await api("/api/v1/settings/notification-channels", { method: "POST", body: JSON.stringify(form) });
      $("#channel-message").textContent = "Canal salvo.";
    } catch (error) {
      $("#channel-message").textContent = error.message;
    }
  });
}

async function renderTickets() {
  const items = await api("/api/v1/tickets");
  const platformAdmin = isPlatformAdmin();
  const ticketHeaders = platformAdmin
    ? ["Titulo", "Tenant", "Severidade", "Status", "Servico", "IA"]
    : ["Titulo", "Severidade", "Status", "Servico", "IA"];
  const ticketRows = items.map((ticket) => {
    const title = `<button class="link-button ticket-detail" data-ticket-id="${esc(ticket.id)}" type="button">${esc(ticket.title)}</button>`;
    const base = [title, esc(ticket.severity), status(ticket.status), esc(ticket.service_name || "-"), esc(ticket.ai_status || "-")];
    return platformAdmin ? [title, esc(ticket.tenant_name || ticket.tenant_id || "-"), ...base.slice(1)] : base;
  });
  const listTitle = platformAdmin ? "Tickets dos clientes/tenants" : "Tickets do tenant";
  const listHint = platformAdmin
    ? "Visao consolidada para administracao principal da plataforma."
    : "Historico aberto por usuarios deste tenant.";
  render(`<section class="grid two"><article class="card"><h3>Abertura de ticket</h3><p class="muted">O ticket ja segue com dados do tenant e passa pela analise IA antes do administrador da plataforma atuar.</p><form id="ticket-form" class="form-grid"><label>Titulo<input name="title" required></label><label>Severidade<select name="severity"><option value="medium">media</option><option value="low">baixa</option><option value="high">alta</option><option value="critical">critica</option></select></label><label>Categoria<select name="category"><option value="incident">incidente</option><option value="question">duvida</option><option value="change">mudanca</option></select></label><label>Servico<input name="service_name" placeholder="api, gateway, host, aplicacao"></label><label style="grid-column:1/-1">Descricao<textarea name="description" required placeholder="Descreva o problema, horarios, impacto e passos ja testados."></textarea></label><label style="grid-column:1/-1">Logs/procedimentos<textarea name="log_collection_notes" placeholder="Cole trechos de logs ou instrucoes de coleta ja executadas."></textarea></label><label style="grid-column:1/-1">Anexos referenciados<textarea name="attachments" placeholder="Ex.: print-login.png, /var/log/nginx/error.log, coleta-kalix.zip"></textarea></label></form><div class="actions" style="margin-top:14px"><button id="create-ticket" class="button primary" type="button">Criar ticket</button></div><p id="ticket-message" class="message"></p></article><article class="card"><h3>${listTitle}</h3><p class="muted">${listHint}</p>${items.length ? table(ticketHeaders, ticketRows) : `<p class="muted">Nenhum ticket aberto.</p>`}</article></section>`);
  $("#create-ticket").addEventListener("click", async () => {
    const form = Object.fromEntries(new FormData($("#ticket-form")).entries());
    const attachments = String(form.attachments || "").split(/\r?\n/).map((name) => name.trim()).filter(Boolean).map((name) => ({ name }));
    delete form.attachments;
    try {
      const response = await api("/api/v1/tickets", { method: "POST", body: JSON.stringify({ ...form, attachments }) });
      $("#ticket-message").textContent = `Ticket criado. IA: ${response.ai_status}`;
      await renderTickets();
    } catch (error) {
      $("#ticket-message").textContent = error.message;
    }
  });
  $$(".ticket-detail").forEach((button) => button.addEventListener("click", () => renderTicketDetail(button.dataset.ticketId)));
}

async function renderTicketDetail(ticketId) {
  if (isUiV2()) {
    await renderTicketDetailV2(ticketId);
    return;
  }
  closeInspector();
  const data = await api(`/api/v1/tickets/${ticketId}`);
  const ticket = data.ticket;
  render(`<section class="grid"><article class="card"><div class="actions"><button id="back-tickets" class="button ghost" type="button">Voltar</button></div><h3>${esc(ticket.title)}</h3><div class="detail-kpis">${metricTile("Status", esc(ticket.status))}${metricTile("Severidade", esc(ticket.severity))}${metricTile("Servico", esc(ticket.service_name || "-"))}${metricTile("IA", esc(ticket.ai_status || "-"))}</div><p>${esc(ticket.description)}</p></article><article class="card"><h3>Analise IA</h3><p><strong>Resumo:</strong> ${esc(ticket.ai_summary || "Aguardando analise.")}</p><p><strong>Causa suspeita:</strong> ${esc(ticket.ai_suspected_cause || "-")}</p><p><strong>Acoes recomendadas:</strong> ${esc(ticket.ai_recommended_actions || "-")}</p><p class="muted">Confianca: ${num(ticket.ai_confidence)}%</p></article><article class="card"><h3>Interacoes</h3>${data.messages?.length ? table(["Quando", "Autor", "Mensagem"], data.messages.map((msg) => [fmt(msg.created_at), esc(msg.author_role), esc(msg.message)])) : `<p class="muted">Sem interacoes.</p>`}<form id="ticket-reply-form" class="form-grid" style="margin-top:14px"><label>Status<select name="status"><option value="">manter</option><option value="in_progress">em andamento</option><option value="waiting_customer">aguardando cliente</option><option value="resolved">resolvido</option><option value="closed">fechado</option></select></label><label style="grid-column:1/-1">Resposta<textarea name="message" required></textarea></label></form><button id="send-ticket-reply" class="button primary" type="button">Enviar interacao</button><p id="ticket-detail-message" class="message"></p></article></section>`);
  $("#back-tickets").addEventListener("click", renderTickets);
  $("#send-ticket-reply").addEventListener("click", async () => {
    const form = Object.fromEntries(new FormData($("#ticket-reply-form")).entries());
    try {
      await api(`/api/v1/tickets/${ticketId}/reply`, { method: "POST", body: JSON.stringify(form) });
      await renderTicketDetail(ticketId);
    } catch (error) {
      $("#ticket-detail-message").textContent = error.message;
    }
  });
}

function ticketPropertiesInspector(ticket) {
  const meta = {
    id: ticket.id || "-",
    status: ticket.status || "-",
    severidade: ticket.severity || "-",
    categoria: ticket.category || "-",
    servico: ticket.service_name || "-",
    ia_status: ticket.ai_status || "-",
    criado_em: ticket.created_at ? fmt(ticket.created_at) : "-",
    atualizado_em: ticket.updated_at ? fmt(ticket.updated_at) : "-",
  };
  const attachments = (ticket.attachments || []).map((a) => a.name || a.path).filter(Boolean);
  return `
    ${kvTable("Meta", meta)}
    <article class="card"><h3>Anexos (referencias)</h3>${attachments.length ? `<pre><code>${esc(attachments.join("\n"))}</code></pre>` : `<p class="muted">Nenhum anexo referenciado.</p>`}</article>
  `;
}

async function renderTicketDetailV2(ticketId) {
  const data = await api(`/api/v1/tickets/${ticketId}`);
  const ticket = data.ticket;
  render(`
    <section class="entity-detail v2">
      <article class="detail-hero card v2-hero">
        <div class="v2-hero-main">
          <p class="eyebrow">Tickets <span class="muted">/</span> ${esc(ticket.title)}</p>
          <div class="v2-title-row">
            <h2>${esc(ticket.title)}</h2>
            <span class="tag">${esc(ticket.severity || "-")}</span>
            <span class="status">${healthDot(ticket.status)} ${esc(ticket.status || "-")}</span>
          </div>
          <p class="muted">${esc(ticket.service_name || "Sem servico informado")}</p>
          <div class="actions v2-actions">
            <button class="button ghost v2-open-props" type="button">Propriedades</button>
            <button id="back-tickets" class="button ghost" type="button">Voltar</button>
          </div>
        </div>
        <div class="v2-hero-kpis">
          ${metricTile("IA", esc(ticket.ai_status || "-"), "triagem")}
          ${metricTile("Confianca", ticket.ai_confidence != null ? `${num(ticket.ai_confidence)}%` : "-", "IA")}
          ${metricTile("Criado", ticket.created_at ? fmt(ticket.created_at) : "-", "data")}
          ${metricTile("Atualizado", ticket.updated_at ? fmt(ticket.updated_at) : "-", "data")}
        </div>
      </article>

      <section class="grid two">
        <article class="card">
          <div class="section-header">
            <div>
              <h3>Descricao</h3>
              <p class="muted">Impacto, horarios e contexto do problema.</p>
            </div>
          </div>
          <p>${esc(ticket.description || "-")}</p>
          ${ticket.log_collection_notes ? `<article class="card" style="margin-top:14px"><h3>Logs / procedimentos</h3><pre><code>${esc(ticket.log_collection_notes)}</code></pre></article>` : ""}
        </article>
        <article class="card">
          <div class="section-header">
            <div>
              <h3>Analise IA</h3>
              <p class="muted">Triagem automatica antes da tratativa humana.</p>
            </div>
          </div>
          <p><strong>Resumo:</strong> ${esc(ticket.ai_summary || "Aguardando analise.")}</p>
          <p><strong>Causa suspeita:</strong> ${esc(ticket.ai_suspected_cause || "-")}</p>
          <p><strong>Acoes recomendadas:</strong> ${esc(ticket.ai_recommended_actions || "-")}</p>
        </article>
      </section>

      <article class="card">
        <div class="section-header">
          <div>
            <h3>Interacoes</h3>
            <p class="muted">Historico do atendimento.</p>
          </div>
        </div>
        ${data.messages?.length ? table(["Quando", "Autor", "Mensagem"], data.messages.map((msg) => [fmt(msg.created_at), esc(msg.author_role), esc(msg.message)])) : `<p class="muted">Sem interacoes.</p>`}
        <form id="ticket-reply-form" class="form-grid" style="margin-top:14px">
          <label>Status<select name="status"><option value="">manter</option><option value="in_progress">em andamento</option><option value="waiting_customer">aguardando cliente</option><option value="resolved">resolvido</option><option value="closed">fechado</option></select></label>
          <label style="grid-column:1/-1">Resposta<textarea name="message" required></textarea></label>
        </form>
        <button id="send-ticket-reply" class="button primary" type="button">Enviar interacao</button>
        <p id="ticket-detail-message" class="message"></p>
      </article>
    </section>
  `);

  openInspector({
    title: ticket.title || "Ticket",
    eyebrow: "Propriedades do ticket",
    body: ticketPropertiesInspector(ticket),
  });

  $("#back-tickets").addEventListener("click", renderTickets);
  $$(".v2-open-props").forEach((button) => button.addEventListener("click", () => openInspector({
    title: ticket.title || "Ticket",
    eyebrow: "Propriedades do ticket",
    body: ticketPropertiesInspector(ticket),
  })));
  $("#send-ticket-reply").addEventListener("click", async () => {
    const form = Object.fromEntries(new FormData($("#ticket-reply-form")).entries());
    try {
      await api(`/api/v1/tickets/${ticketId}/reply`, { method: "POST", body: JSON.stringify(form) });
      await renderTicketDetailV2(ticketId);
    } catch (error) {
      $("#ticket-detail-message").textContent = error.message;
    }
  });
}

async function renderIntegrations() {
  const items = await api("/api/v1/extensions");
  render(`
    <section class="grid">
      <article class="card">
        <div class="section-header">
          <div>
            <h3>Integracoes e Extensoes</h3>
            <p class="muted">Configure instancias reais (ex.: varios bancos) e execute via gateway do tenant (recomendado) para coletar metricas dentro da rede do cliente.</p>
          </div>
        </div>
        ${items.length ? table(
          ["Integracao", "Categoria", "Status", "Instancias", "Dados coletados", "Correlacao", "Acoes"],
          items.map((extension) => [
            `<strong>${esc(extension.name)}</strong><br><small>${esc(extension.slug)}</small><p class="muted">${esc(extension.description || "")}</p>`,
            esc(extension.category || "-"),
            extension.installed ? (extension.enabled ? "habilitada" : "instalada/desligada") : "nao instalada",
            num(extension.instances || 0),
            esc((extension.metrics || []).join(", ") || "-"),
            esc(integrationCorrelation(extension.category)),
            `<button class="button ghost extension-manage" data-slug="${esc(extension.slug)}" type="button">Gerenciar</button>`,
          ])
        ) : `<p class="muted">Nenhuma extensao catalogada ainda.</p>`}
      </article>
      <div id="extension-modal-backdrop" class="modal-backdrop hidden"></div>
      <section id="extension-modal" class="modal hidden" aria-hidden="true">
        <article class="card">
          <div class="section-header">
            <div>
              <h3 id="extension-modal-title">Extensao</h3>
              <p id="extension-modal-subtitle" class="muted"></p>
            </div>
            <div class="actions">
              <button id="extension-modal-close" class="button ghost" type="button">Fechar</button>
            </div>
          </div>
          <div id="extension-modal-body"></div>
        </article>
      </section>
    </section>
  `);

  const closeModal = () => {
    $("#extension-modal").classList.add("hidden");
    $("#extension-modal-backdrop").classList.add("hidden");
  };
  $("#extension-modal-close").addEventListener("click", closeModal);
  $("#extension-modal-backdrop").addEventListener("click", closeModal);

  const extensionFieldSpec = (extension) => {
    const schema = extension.config_schema || {};
    const defaults = schema.defaults || {};
    if (Array.isArray(schema.fields) && schema.fields.length) {
      return { fields: schema.fields, advanced: schema.advanced || [], defaults };
    }
    if (extension.category === "database") {
      const bySlug = {
        postgresql: { port: 5432, database: "postgres", user: "postgres" },
        mysql: { port: 3306, database: "information_schema", user: "root" },
        mariadb: { port: 3306, database: "information_schema", user: "root" },
        sqlserver: { port: 1433, database: "master", user: "sa" },
        oracle: { port: 1521, database: "", user: "" },
        mongodb: { port: 27017, database: "admin", user: "" },
        redis: { port: 6379, database: 0, user: "" },
        elasticsearch: { port: 9200, database: "", user: "" },
      }[extension.slug] || {};
      return {
        defaults: { lock_wait_threshold_s: 30, timeout_seconds: 10, ...bySlug },
        fields: [
          { name: "host", label: "Host/IP", type: "text", required: true },
          { name: "port", label: "Porta", type: "number", required: true },
          { name: "user", label: "Usuario", type: "text" },
          { name: "password", label: "Senha", type: "password" },
          { name: "database", label: "Banco/database", type: "text" },
          { name: "instance", label: "Instancia", type: "text" },
          { name: "lock_wait_threshold_s", label: "Threshold lock wait (s)", type: "number" },
          { name: "timeout_seconds", label: "Timeout coleta (s)", type: "number" },
          { name: "ssl", label: "Usar SSL/TLS", type: "checkbox" },
        ],
        advanced: [{ name: "custom_queries", label: "Metricas por query customizada", type: "metric_queries" }],
      };
    }
    return {
      defaults: {},
      fields: [
        { name: "host", label: "Host/IP ou URL", type: "text", required: true },
        { name: "port", label: "Porta", type: "number" },
        { name: "user", label: "Usuario", type: "text" },
        { name: "password", label: "Senha/token", type: "password" },
        { name: "timeout_seconds", label: "Timeout coleta (s)", type: "number", default: 10 },
      ],
      advanced: [{ name: "custom_queries", label: "Metricas customizadas", type: "metric_queries" }],
    };
  };

  const renderConfigField = (field, cfg, defaults) => {
    const value = cfg[field.name] ?? field.default ?? defaults[field.name] ?? "";
    const required = field.required ? "required" : "";
    if (field.type === "checkbox") {
      return `<label><input type="checkbox" name="cfg_${esc(field.name)}" data-config-field="${esc(field.name)}" data-config-type="checkbox" style="width:auto; margin-right:8px" ${value ? "checked" : ""}>${esc(field.label || field.name)}</label>`;
    }
    if (field.type === "select") {
      const options = field.options || [];
      return `<label>${esc(field.label || field.name)}<select name="cfg_${esc(field.name)}" data-config-field="${esc(field.name)}" data-config-type="text" ${required}>${options.map((opt) => `<option value="${esc(opt)}" ${String(value) === String(opt) ? "selected" : ""}>${esc(opt)}</option>`).join("")}</select></label>`;
    }
    const inputType = field.type === "password" ? "password" : field.type === "number" ? "number" : "text";
    return `<label>${esc(field.label || field.name)}<input name="cfg_${esc(field.name)}" data-config-field="${esc(field.name)}" data-config-type="${esc(inputType)}" type="${inputType}" value="${esc(String(value))}" ${required}></label>`;
  };

  const renderMetricQueries = (cfg) => {
    const queries = Array.isArray(cfg.custom_queries) ? cfg.custom_queries : [];
    return `<label style="grid-column:1/-1">Metricas por query customizada
      <textarea name="custom_queries" rows="5" spellcheck="false" class="mono" placeholder='[{"metric":"orders_total","query":"SELECT count(*) FROM orders"}]'>${esc(JSON.stringify(queries, null, 2))}</textarea>
      <small class="muted">Opcional. Cada query deve retornar um valor numerico/booleano para virar metrica e dashboard.</small>
    </label>`;
  };

  const renderInstanceForm = (extension, instance) => {
    const cfg = instance?.config || {};
    const spec = extensionFieldSpec(extension);
    return `
      <form class="form-grid extension-instance-form" data-instance-id="${esc(instance?.id || "")}">
        <label>Nome da instancia
          <input name="name" value="${esc(instance?.name || "default")}" required>
        </label>
        <label>Executar em
          <select name="run_on">
            <option value="auto" ${(instance?.run_on || "auto") === "auto" ? "selected" : ""}>auto (gateway se existir)</option>
            <option value="gateway" ${(instance?.run_on || "") === "gateway" ? "selected" : ""}>gateway</option>
            <option value="server" ${(instance?.run_on || "") === "server" ? "selected" : ""}>server (somente endpoints publicos)</option>
          </select>
        </label>
        <label>Gateway tipo
          <select name="gateway_type">
            <option value="integrations" ${(instance?.gateway_type || "integrations") === "integrations" ? "selected" : ""}>integracoes</option>
            <option value="agents" ${(instance?.gateway_type || "") === "agents" ? "selected" : ""}>agents</option>
            <option value="security" ${(instance?.gateway_type || "") === "security" ? "selected" : ""}>seguranca</option>
            <option value="logs" ${(instance?.gateway_type || "") === "logs" ? "selected" : ""}>logs</option>
          </select>
        </label>
        <label>Intervalo (s)
          <input name="interval_seconds" type="number" min="60" value="${esc(String(instance?.interval_seconds || 300))}">
        </label>
        <label><input type="checkbox" name="enabled" style="width:auto; margin-right:8px" ${instance?.enabled !== false ? "checked" : ""}>Habilitada</label>
        <div style="grid-column:1/-1"><h4>Dados de conexao e coleta padrao</h4><p class="muted">Informe apenas os dados de acesso. O LAS coleta as estatisticas padrao da tecnologia e cria metricas/alertas quando aplicavel.</p></div>
        ${spec.fields.map((field) => renderConfigField(field, cfg, spec.defaults)).join("")}
        ${spec.advanced.some((field) => field.type === "metric_queries") ? renderMetricQueries(cfg) : ""}
      </form>
      <div class="actions">
        <button class="button primary extension-save" type="button" data-instance-id="${esc(instance?.id || "")}">Salvar</button>
        ${instance?.id ? `<button class="button ghost extension-run" type="button" data-instance-id="${esc(instance.id)}">Executar agora</button>` : ""}
        ${instance?.id ? `<button class="button ghost extension-delete" type="button" data-instance-id="${esc(instance.id)}">Excluir</button>` : ""}
      </div>
      <p class="muted">${esc(extension.readme || "As metricas padrao serao coletadas automaticamente pelo gateway selecionado.")}</p>
    `;
  };

  const openModal = async (slug) => {
    $("#extension-modal").classList.remove("hidden");
    $("#extension-modal-backdrop").classList.remove("hidden");
    $("#extension-modal-body").innerHTML = `<p class="muted">Carregando...</p>`;
    const detail = await api(`/api/v1/extensions/${encodeURIComponent(slug)}`);
    const extension = detail.extension || {};
    const instances = detail.instances || [];
    $("#extension-modal-title").textContent = extension.name || slug;
    $("#extension-modal-subtitle").textContent = `${extension.slug || slug} - ${extension.category || "-"}`;
    $("#extension-modal-body").innerHTML = `
      <div class="grid two">
        <article class="card">
          <h3>Instancias cadastradas</h3>
          ${instances.length ? table(["Nome", "Status", "Ultima coleta", "Metricas", "Acoes"], instances.map((inst) => [
            `<button class="link-button extension-edit" type="button" data-instance-id="${esc(inst.id)}">${esc(inst.name)}</button>`,
            status(inst.last_status || "unknown"),
            fmt(inst.last_check),
            num(inst.metrics_collected || 0),
            `<button class="button ghost extension-run" type="button" data-instance-id="${esc(inst.id)}">Executar</button>`,
          ])) : `<p class="muted">Nenhuma instancia criada ainda.</p>`}
          <div class="actions" style="margin-top:12px">
            <button id="extension-new" class="button primary" type="button">Nova instancia</button>
          </div>
        </article>
        <article class="card">
          <h3 id="extension-form-title">Nova instancia</h3>
          <div id="extension-form-area">${renderInstanceForm(extension, null)}</div>
          <p id="extension-form-message" class="message"></p>
        </article>
      </div>
    `;

    const getFormPayload = () => {
      const form = $(".extension-instance-form");
      const values = Object.fromEntries(new FormData(form).entries());
      const config = {};
      form.querySelectorAll("[data-config-field]").forEach((field) => {
        const key = field.dataset.configField;
        const type = field.dataset.configType;
        if (type === "checkbox") {
          config[key] = field.checked;
        } else if (type === "number") {
          config[key] = field.value === "" ? undefined : Number(field.value);
        } else if (field.value !== "") {
          config[key] = field.value;
        }
      });
      if (values.custom_queries && values.custom_queries.trim()) {
        try { config.custom_queries = JSON.parse(values.custom_queries); } catch { throw new Error("Metricas por query customizada precisam estar em JSON valido."); }
      }
      return {
        name: values.name,
        enabled: !!form.elements.enabled.checked,
        run_on: values.run_on,
        gateway_type: values.gateway_type,
        interval_seconds: Number(values.interval_seconds || 300),
        config,
      };
    };

    const refresh = () => openModal(slug);

    $("#extension-new").addEventListener("click", () => {
      $("#extension-form-title").textContent = "Nova instancia";
      $("#extension-form-area").innerHTML = renderInstanceForm(extension, null);
      $("#extension-form-message").textContent = "";
      bindFormButtons();
    });

    const bindFormButtons = () => {
      $(".extension-save")?.addEventListener("click", async () => {
        try {
          const payload = getFormPayload();
          const instanceId = $(".extension-save").dataset.instanceId;
          if (instanceId) {
            await api(`/api/v1/extensions/instances/${encodeURIComponent(instanceId)}`, { method: "PUT", body: JSON.stringify(payload) });
            $("#extension-form-message").textContent = "Instancia atualizada.";
          } else {
            await api(`/api/v1/extensions/${encodeURIComponent(slug)}/instances`, { method: "POST", body: JSON.stringify(payload) });
            $("#extension-form-message").textContent = "Instancia criada.";
          }
          await refresh();
        } catch (error) {
          $("#extension-form-message").textContent = error.message;
        }
      });
      $$(".extension-run").forEach((btn) => btn.addEventListener("click", async () => {
        const instanceId = btn.dataset.instanceId;
        try {
          await api(`/api/v1/extensions/instances/${encodeURIComponent(instanceId)}/run`, { method: "POST" });
          $("#extension-form-message").textContent = "Execucao enfileirada no gateway.";
          await refresh();
        } catch (error) {
          $("#extension-form-message").textContent = error.message;
        }
      }));
      $$(".extension-delete").forEach((btn) => btn.addEventListener("click", async () => {
        const instanceId = btn.dataset.instanceId;
        if (!confirm("Excluir esta instancia?")) return;
        try {
          await api(`/api/v1/extensions/instances/${encodeURIComponent(instanceId)}`, { method: "DELETE" });
          $("#extension-form-message").textContent = "Instancia excluida.";
          await refresh();
        } catch (error) {
          $("#extension-form-message").textContent = error.message;
        }
      }));
    };

    bindFormButtons();

    $$(".extension-edit").forEach((btn) => btn.addEventListener("click", () => {
      const instanceId = btn.dataset.instanceId;
      const instance = instances.find((it) => it.id === instanceId);
      $("#extension-form-title").textContent = `Editar: ${instance?.name || instanceId}`;
      $("#extension-form-area").innerHTML = renderInstanceForm(extension, instance);
      $("#extension-form-message").textContent = "";
      bindFormButtons();
    }));
  };

  $$(".extension-manage").forEach((button) => button.addEventListener("click", () => openModal(button.dataset.slug)));
}

function integrationCorrelation(category) {
  if (category === "database") return "aplicacoes, servicos, queries e hosts";
  if (category === "notification") return "alertas, incidentes e tickets";
  if (category === "security") return "hosts, ativos de rede, IDS e vulnerabilidades";
  return "hosts, servicos, aplicacoes e processos quando houver identificadores comuns";
}

async function renderOnboarding() {
  const webUrl = "https://las.soservices.com.br";
  const apiUrl = "https://api.soservices.com.br";
  const mtlsUrl = "https://api.soservices.com.br:8443";
  const options = await api("/api/v1/agents/install-options");
  const profileOptions = (options.agent_profiles || []).map((profile) => `<option value="${esc(profile.key)}" ${profile.allowed ? "" : "disabled"}>${esc(profile.label)}${profile.allowed ? "" : " (nao licenciado)"}</option>`).join("");
  const moduleOptions = (options.agent_modules || []).map((module) => {
    const alwaysOn = module.key === "logs";
    return `<label class="pill-check"><input type="checkbox" class="agent-module-option" value="${esc(module.key)}" ${alwaysOn ? "checked disabled" : ""} ${module.allowed ? "" : "disabled"}> ${esc(module.label)}${module.allowed ? "" : " (licenca necessaria)"}</label>`;
  }).join("");
  const gatewayOptions = (options.gateway_types || []).map((gateway) => `<option value="${esc(gateway.key)}" ${gateway.allowed ? "" : "disabled"}>${esc(gateway.label)}${gateway.allowed ? "" : " (nao licenciado)"}</option>`).join("");
  render(`
    <section class="grid two">
      <article class="card">
        <h3>Instalacao real de agentes</h3>
        <p class="muted">Escolha o perfil de instalacao. Logs sempre ficam inclusos; OTel, traces, RUM, IDS e scans aparecem conforme as licencas do tenant.</p>
        <form id="agent-install-form" class="form-grid">
          <label>Perfil
            <select name="profile">${profileOptions}</select>
          </label>
          <label style="grid-column:1/-1">Modulos opcionais
            <div class="pill-row">${moduleOptions}</div>
          </label>
        </form>
        <div class="actions">
          <a id="download-agent-linux" class="button primary" href="/api/v1/agents/download/linux" target="_blank" rel="noreferrer">Agente Linux (.sh)</a>
          <a id="download-agent-windows" class="button ghost" href="/api/v1/agents/download/windows" target="_blank" rel="noreferrer">Agente Windows Setup.exe</a>
          <a id="download-agent-windows-ps1" class="button ghost" href="/api/v1/agents/download/windows?format=ps1" target="_blank" rel="noreferrer">Agente Windows PowerShell</a>
          <a id="download-agent-docker" class="button ghost" href="/api/v1/agents/download/docker" target="_blank" rel="noreferrer">Docker Compose</a>
          <a id="download-agent-k8s" class="button ghost" href="/api/v1/agents/download/k8s" target="_blank" rel="noreferrer">Kubernetes DaemonSet</a>
        </div>
        <p class="muted">O perfil Infra instala infraestrutura, processos, servicos e logs. O perfil Completa acrescenta OTel, traces e experiencia do usuario quando licenciados.</p>
        <p><strong>Servidor SaaS:</strong> <span class="mono">${apiUrl}</span></p>
        <p><strong>mTLS obrigatorio:</strong> <span class="mono">${mtlsUrl}</span></p>
        <p><strong>Frontend:</strong> <span class="mono">${webUrl}</span></p>
      </article>
      <article class="card">
        <h3>Gateways e failover</h3>
        <p class="muted">Selecione o tipo do gateway. Agents recebe trafego de agentes/OTel/RUM; Logs recebe syslog/log forwarding; Integracoes roda plugins; Seguranca executa tarefas de rede e security.</p>
        <form id="gateway-install-form" class="form-grid">
          <label>Tipo de gateway
            <select name="gateway_type">${gatewayOptions}</select>
          </label>
        </form>
        <div class="actions">
          <a id="download-gateway-linux" class="button primary" href="/api/v1/agents/download/gateway/linux" target="_blank" rel="noreferrer">Gateway Linux (.sh)</a>
          <a id="download-gateway-windows" class="button ghost" href="/api/v1/agents/download/gateway/windows" target="_blank" rel="noreferrer">Gateway Windows Setup.exe</a>
          <a id="download-gateway-windows-ps1" class="button ghost" href="/api/v1/agents/download/gateway/windows?format=ps1" target="_blank" rel="noreferrer">Gateway Windows PowerShell</a>
        </div>
        <p class="muted">Depois de instalar, acompanhe a tela Gateways para validar heartbeat, prioridade, peso, cluster e failover.</p>
      </article>
      <article class="card">
        <h3>Experiencia do usuario</h3>
        <p class="muted">No modo Completa, o agente podera preparar injecao assistida em webservers/app servers detectados. A opcao manual continua disponivel para apps onde a injecao automatica nao for segura.</p>
        <pre><code>&lt;script src="/api/v1/agents/download/rum-js?appname=minha-app"&gt;&lt;/script&gt;</code></pre>
      </article>
      <article class="card">
        <h3>Apps de validacao</h3>
        <p>Suba o laboratorio Docker em uma VM Linux com Docker:</p>
        <pre><code>cd lab/validation-apps
docker compose up -d --build</code></pre>
        <p class="muted">O laboratorio inclui exemplos .NET, Java e PHP/HTML para gerar trafego HTTP simples e facilitar validacao de RUM/APM/logs/traces.</p>
      </article>
      <article class="card">
        <h3>Documentacao do teste</h3>
        <p class="muted">Use a documentacao operacional durante a campanha piloto e para orientar os tenants trial de 15 dias.</p>
        <div class="actions">
          <a class="button ghost" href="/docs/cliente-validacao.html" target="_blank" rel="noreferrer">Guia do cliente</a>
          <a class="button ghost" href="/api/health" target="_blank" rel="noreferrer">Health API</a>
          <a class="button ghost" href="/api/v1/auth/bootstrap" target="_blank" rel="noreferrer">Bootstrap</a>
        </div>
      </article>
    </section>
  `);
  const updateAgentLinks = () => {
    const form = $("#agent-install-form");
    const profile = form.profile.value || "infra";
    const modules = $$(".agent-module-option")
      .filter((input) => input.checked && !input.disabled)
      .map((input) => input.value);
    const params = new URLSearchParams({ profile });
    if (modules.length) {
      params.set("modules", modules.join(","));
    }
    $("#download-agent-linux").href = `/api/v1/agents/download/linux?${params.toString()}`;
    $("#download-agent-windows").href = `/api/v1/agents/download/windows?${params.toString()}`;
    const ps1Params = new URLSearchParams(params);
    ps1Params.set("format", "ps1");
    $("#download-agent-windows-ps1").href = `/api/v1/agents/download/windows?${ps1Params.toString()}`;
    $("#download-agent-docker").href = `/api/v1/agents/download/docker?${params.toString()}`;
    $("#download-agent-k8s").href = `/api/v1/agents/download/k8s?${params.toString()}`;
  };
  const updateGatewayLinks = () => {
    const type = $("#gateway-install-form").gateway_type.value || "agents";
    const params = new URLSearchParams({ gateway_type: type });
    $("#download-gateway-linux").href = `/api/v1/agents/download/gateway/linux?${params.toString()}`;
    $("#download-gateway-windows").href = `/api/v1/agents/download/gateway/windows?${params.toString()}`;
    const ps1Params = new URLSearchParams(params);
    ps1Params.set("format", "ps1");
    $("#download-gateway-windows-ps1").href = `/api/v1/agents/download/gateway/windows?${ps1Params.toString()}`;
  };
  $("#agent-install-form").addEventListener("change", updateAgentLinks);
  $("#gateway-install-form").addEventListener("change", updateGatewayLinks);
  updateAgentLinks();
  updateGatewayLinks();
}

function gatewayTypeLabel(type) {
  return {
    agents: "Gateway Agents",
    integrations: "Gateway Integracoes",
    logs: "Gateway de Logs",
    security: "Gateway de Seguranca",
    infra: "Gateway Infra",
    proxy: "Gateway Proxy",
  }[type] || type || "-";
}

function gatewaySyslogSummary(gateway) {
  const syslog = gateway.syslog_runtime || {};
  const listeners = Object.values(syslog.listeners || {});
  const hasListening = listeners.some((listener) => listener?.status === "listening");
  const hasError = listeners.some((listener) => listener?.status === "error") || !!syslog.last_error;
  if (!syslog.enabled && gateway.type !== "logs") {
    return "syslog off";
  }
  if (hasListening) {
    return `syslog ouvindo | ${num(syslog.received || 0)} msgs`;
  }
  if (hasError) {
    return `syslog erro | ${esc(syslog.last_error || "listener falhou")}`;
  }
  return "syslog aguardando listener";
}

async function renderGateways() {
  const items = await api("/api/v1/gateways");
  const topology = await api("/api/v1/gateways/topology");
  const rows = items.map((gateway) => {
    const metrics = gateway.resource_metrics || {};
    const syslogSummary = gatewaySyslogSummary(gateway);
    return [
      `<button class="link-button gateway-detail-trigger" data-gateway-id="${esc(gateway.id)}" type="button"><strong>${esc(gateway.name)}</strong></button><br><small>${esc(gatewayTypeLabel(gateway.type))}</small>`,
      esc(gateway.cluster_name || "default"),
      `${num(gateway.priority)} / ${num(gateway.weight)}`,
      gateway.shared_with_tenants ? "compartilhado" : gateway.failover_only ? "failover" : "tenant",
      status(gateway.status),
      `${maybeNum(metrics.cpuUsage, "%")} CPU<br><small>${maybeNum(metrics.memoryUsage, "%")} RAM</small><br><small>${syslogSummary}</small>`,
      esc(gateway.public_endpoint || (gateway.host ? `${gateway.host}:${gateway.port}` : "-")),
      `<small>${fmt(gateway.last_activity || gateway.last_heartbeat)}</small><br><button class="button ghost gateway-edit" data-gateway-id="${esc(gateway.id)}" type="button">Editar</button>`,
    ];
  });

  render(`<section class="grid two"><article class="card"><div class="section-header"><div><h3>Gateways</h3><p class="muted">Heartbeat, consumo basico, fila local, tipo e cluster. Clique no nome para o drilldown operacional.</p></div></div>${items.length ? table(["Nome", "Cluster", "Prior/Peso", "Escopo", "Status", "Recursos", "Endpoint", "Acoes"], rows) : `<p class="muted">Nenhum gateway criado ou instalado ainda.</p>`}<p class="muted">Gateways sem heartbeat aparecem como pendentes/offline para facilitar diagnostico de instalacao.</p>${topology.clusters.length ? topology.clusters.map((cluster) => `<div class="card" style="margin-top:12px"><strong>${esc(cluster.cluster_name)}</strong><p class="muted">Primarios: ${num(cluster.primary.length)} | Failover: ${num(cluster.failover.length)} | Compartilhados: ${num(cluster.shared.length)}</p></div>`).join("") : ""}</article><article class="card"><h3>Gateway e cluster</h3><form id="gateway-form" class="form-grid"><input type="hidden" name="gateway_id"><label>Nome<input name="name" required></label><label>Tipo<select name="type"><option value="agents">Gateway Agents</option><option value="integrations">Gateway Integracoes</option><option value="logs">Gateway de Logs</option><option value="security">Gateway de Seguranca</option></select></label><label>Host<input name="host" placeholder="gw01.soservices.com.br"></label><label>Porta<input name="port" value="9443" type="number"></label><label>Cluster<input name="cluster_name" value="default"></label><label>Prioridade<input name="priority" value="100" type="number"></label><label>Peso<input name="weight" value="1" type="number"></label><label>Public endpoint<input name="public_endpoint" placeholder="https://gw01.soservices.com.br:9443"></label><label><input type="checkbox" name="failover_only" style="width:auto; margin-right:8px">Somente failover</label><label><input type="checkbox" name="shared_with_tenants" style="width:auto; margin-right:8px">Compartilhar com tenants</label><label><input type="checkbox" name="tls_enabled" checked style="width:auto; margin-right:8px">TLS habilitado</label><label><input type="checkbox" name="compress_enabled" checked style="width:auto; margin-right:8px">Compressao habilitada</label><label><input type="checkbox" name="encrypt_enabled" checked style="width:auto; margin-right:8px">Protecao dos dados habilitada</label></form><div class="actions" style="margin-top:14px"><button id="create-gateway" class="button primary" type="button">Salvar gateway</button><button id="delete-gateway" class="button ghost" type="button">Excluir</button><button id="cleanup-gateways" class="button ghost" type="button">Limpar testes</button><button id="reset-gateway" class="button ghost" type="button">Novo</button><a class="button ghost" href="/api/v1/agents/download/gateway/linux?gateway_type=agents" target="_blank" rel="noreferrer">Gateway Linux</a><a class="button ghost" href="/api/v1/agents/download/gateway/windows?gateway_type=agents" target="_blank" rel="noreferrer">Gateway Windows Setup</a><a class="button ghost" href="/api/v1/agents/download/gateway/windows?format=ps1&gateway_type=agents" target="_blank" rel="noreferrer">Gateway Windows Script</a></div><p id="gateway-message" class="message"></p></article></section>`);

  const form = $("#gateway-form");
  const resetGatewayForm = () => {
    form.gateway_id.value = "";
    form.name.value = "";
    form.type.value = "agents";
    form.host.value = "";
    form.port.value = 9443;
    form.cluster_name.value = "default";
    form.priority.value = 100;
    form.weight.value = 1;
    form.public_endpoint.value = "";
    form.failover_only.checked = false;
    form.shared_with_tenants.checked = false;
    form.tls_enabled.checked = true;
    form.compress_enabled.checked = true;
    form.encrypt_enabled.checked = true;
  };
  const fillGatewayForm = (gateway) => {
    form.gateway_id.value = gateway.id;
    form.name.value = gateway.name || "";
    form.type.value = gateway.type || "agents";
    form.host.value = gateway.host || "";
    form.port.value = gateway.port || 9443;
    form.cluster_name.value = gateway.cluster_name || "default";
    form.priority.value = gateway.priority || 100;
    form.weight.value = gateway.weight || 1;
    form.public_endpoint.value = gateway.public_endpoint || "";
    form.failover_only.checked = !!gateway.failover_only;
    form.shared_with_tenants.checked = !!gateway.shared_with_tenants;
    form.tls_enabled.checked = !!gateway.tls_enabled;
    form.compress_enabled.checked = !!gateway.compress_enabled;
    form.encrypt_enabled.checked = !!gateway.encrypt_enabled;
  };
  resetGatewayForm();
  $$(".gateway-detail-trigger").forEach((button) => button.addEventListener("click", () => renderGatewayDetail(button.dataset.gatewayId)));
  $$(".gateway-edit").forEach((button) => button.addEventListener("click", () => {
    const gateway = items.find((item) => item.id === button.dataset.gatewayId);
    if (gateway) fillGatewayForm(gateway);
  }));
  $("#create-gateway").addEventListener("click", async () => {
    const payload = Object.fromEntries(new FormData(form).entries());
    payload.port = Number(payload.port || 9443);
    payload.priority = Number(payload.priority || 100);
    payload.weight = Number(payload.weight || 1);
    payload.failover_only = form.failover_only.checked;
    payload.shared_with_tenants = form.shared_with_tenants.checked;
    payload.tls_enabled = form.tls_enabled.checked;
    payload.compress_enabled = form.compress_enabled.checked;
    payload.encrypt_enabled = form.encrypt_enabled.checked;
    try {
      if (form.gateway_id.value) {
        await api(`/api/v1/gateways/${form.gateway_id.value}`, { method: "PUT", body: JSON.stringify(payload) });
        $("#gateway-message").textContent = "Gateway atualizado.";
      } else {
        await api("/api/v1/gateways", { method: "POST", body: JSON.stringify(payload) });
        $("#gateway-message").textContent = "Gateway criado.";
      }
      await renderGateways();
    } catch (error) {
      $("#gateway-message").textContent = error.message;
    }
  });
  $("#delete-gateway").addEventListener("click", async () => {
    if (!form.gateway_id.value) {
      $("#gateway-message").textContent = "Selecione um gateway para excluir.";
      return;
    }
    try {
      await api(`/api/v1/gateways/${form.gateway_id.value}`, { method: "DELETE" });
      $("#gateway-message").textContent = "Gateway excluido.";
      await renderGateways();
    } catch (error) {
      $("#gateway-message").textContent = error.message;
    }
  });
  $("#cleanup-gateways").addEventListener("click", async () => {
    try {
      await api("/api/v1/gateways/cleanup", {
        method: "POST",
        body: JSON.stringify({
          delete_names: ["shared-gateway-core", "Gateway infra", "Gateway infra Windows"],
          delete_prefixes: ["demo-gw-", "gateway-hml-"],
          delete_offline_only: true,
        }),
      });
      $("#gateway-message").textContent = "Gateways de teste removidos.";
      await renderGateways();
    } catch (error) {
      $("#gateway-message").textContent = error.message;
    }
  });
  $("#reset-gateway").addEventListener("click", resetGatewayForm);
}

async function renderGatewayDetail(gatewayId, options = {}) {
  const timeframe = options.timeframe || state.gatewayTimeframe || "1h";
  const params = new URLSearchParams({ timeframe });
  if (timeframe === "custom") {
    if (options.start) params.set("start", new Date(options.start).toISOString());
    if (options.end) params.set("end", new Date(options.end).toISOString());
  }
  const data = await api(`/api/v1/gateways/${gatewayId}/detail?${params.toString()}`);
  const gateway = data.gateway;
  const metrics = data.metrics || [];
  const latest = latestPoint(metrics);
  const agents = data.agents || [];
  const syslog = data.syslog_runtime || gateway.syslog_runtime || {};
  const syslogListeners = Object.entries(syslog.listeners || {});
  const syslogRows = syslogListeners.map(([key, listener]) => [
    esc(key),
    status(listener?.status || "unknown"),
    esc(listener?.error || "-"),
    fmt(listener?.updated_at),
  ]);
  render(`<section class="entity-detail"><article class="detail-hero card"><div class="detail-hero-main"><p class="eyebrow">Gateway detalhado</p><h2>${esc(gateway.name)}</h2><p class="muted">${esc(gatewayTypeLabel(gateway.type))} - ${esc(gateway.public_endpoint || gateway.host || "-")}</p><div class="actions"><button id="back-gateways" class="button ghost" type="button">Voltar para gateways</button></div></div><div class="detail-health">${healthPill(gateway.status)}<small>Ultima atividade<br><strong>${fmt(gateway.last_activity || gateway.last_heartbeat)}</strong></small></div></article><article class="card detail-kpis">${metricTile("Versao", esc(gateway.version || "-"))}${metricTile("Cluster", esc(gateway.cluster_name || "default"), `prioridade ${num(gateway.priority)} / peso ${num(gateway.weight)}`)}${metricTile("CPU", maybeNum(latest.cpuUsage, "%"))}${metricTile("RAM", maybeNum(latest.memoryUsage, "%"))}${metricTile("Disco", maybeNum(latest.diskUsage, "%"))}${metricTile("Agentes usando", num(agents.length))}</article><article class="card"><div class="section-header"><div><h3>Consumo do gateway</h3><p class="muted">Historico enviado pelo heartbeat do proprio gateway.</p></div></div>${timeframeControl("gateway-detail", timeframe)}<div class="charts-grid three">${seriesChart("CPU", metrics, [{ key: "cpuUsage", label: "CPU" }], { max: 100 })}${seriesChart("Memoria", metrics, [{ key: "memoryUsage", label: "Memoria" }], { max: 100 })}${seriesChart("Disco", metrics, [{ key: "diskUsage", label: "Disco" }], { max: 100 })}</div></article><section class="grid two"><article class="card"><h3>Syslog remoto</h3><div class="detail-kpis">${metricTile("Estado", syslog.enabled ? "habilitado" : "desabilitado")}${metricTile("Mensagens", num(syslog.received || 0), "desde o start")}${metricTile("Ultima origem", esc(syslog.last_source_ip || "-"))}${metricTile("Ultima msg", fmt(syslog.last_received_at))}</div>${syslogRows.length ? table(["Listener", "Status", "Erro", "Atualizado"], syslogRows) : `<p class="muted">Nenhum listener syslog reportado ainda. Valide se o gateway e do tipo logs e se a feature syslog esta habilitada.</p>`}${syslog.last_error ? `<p class="message">${esc(syslog.last_error)}</p>` : ""}</article><article class="card"><h3>Funcionalidades reportadas</h3>${(data.capabilities || []).length ? table(["Modulo", "Status"], data.capabilities.map((item) => [esc(item.key), item.enabled ? status("online") : status("offline")])) : `<p class="muted">Nenhum modulo reportado ainda. Aguarde o proximo heartbeat do gateway atualizado.</p>`}<p class="muted">Fila local: logs ${num(data.queues?.logs || 0)} | metricas ${num(data.queues?.metrics || 0)}. Ultimo lote: ${fmt(data.last_batch?.timestamp)}.</p></article><article class="card"><h3>Agentes roteados por este gateway</h3>${agents.length ? table(["Agente", "Host", "IP", "Status", "Ultimo heartbeat"], agents.map((agent) => [esc(agent.name || agent.id), agent.host_id ? `<button class="link-button gateway-agent-host" data-host-id="${esc(agent.host_id)}" type="button">${esc(agent.host || "-")}</button>` : esc(agent.host || "-"), esc(agent.ip || "-"), status(agent.status), fmt(agent.last_heartbeat)])) : `<p class="muted">Nenhum agente reportou uso deste gateway ainda.</p>`}</article></section></section>`);
  const timeframeSelect = $("#gateway-detail-timeframe");
  const customRanges = $$(".custom-range");
  const updateCustomVisibility = () => customRanges.forEach((item) => item.classList.toggle("hidden", timeframeSelect.value !== "custom"));
  updateCustomVisibility();
  timeframeSelect.addEventListener("change", updateCustomVisibility);
  $("#gateway-detail-apply").addEventListener("click", () => {
    state.gatewayTimeframe = timeframeSelect.value;
    renderGatewayDetail(gatewayId, {
      timeframe: timeframeSelect.value,
      start: $("#gateway-detail-start")?.value,
      end: $("#gateway-detail-end")?.value,
    });
  });
  $("#back-gateways").addEventListener("click", renderGateways);
  $$(".gateway-agent-host").forEach((button) => button.addEventListener("click", () => renderHostDetail(button.dataset.hostId)));
}

async function loadView(view) {
  setView(view);
  closeInspector();
  render(`<article class="card"><p class="muted">Carregando ${esc(titleMap[view] || view)}...</p></article>`);
  try {
    if (view === "dashboard") {
      if (isPlatformAdmin()) {
        await renderPlatformDashboard();
      } else {
        await renderTenantDashboard();
      }
      return;
    }
    if (view === "licensing") {
      if (isPlatformAdmin()) {
        await renderPlatformLicensing();
      } else {
        render(empty("Licencas", "A visualizacao consolidada de licencas fica no painel da plataforma."));
      }
      return;
    }
    if (view === "tenants") {
      if (isPlatformAdmin()) {
        await renderTenants();
      } else {
        render(empty("Tenants", "A administracao de tenants fica disponivel apenas para o superadmin."));
      }
      return;
    }
    if (view === "hosts") {
      await renderHosts();
      return;
    }
    if (view === "processes") {
      await renderProcesses();
      return;
    }
    if (view === "services") {
      await renderServices();
      return;
    }
    if (view === "applications") {
      await renderApplications();
      return;
    }
    if (view === "topologies") {
      await renderTopologies();
      return;
    }
    if (view === "dashboards") {
      await renderDashboards();
      return;
    }
    if (view === "databases") {
      await renderDatabases();
      return;
    }
    if (view === "messaging") {
      await renderMessaging();
      return;
    }
    if (view === "orchestration") {
      await renderOrchestration();
      return;
    }
    if (view === "synthetics") {
      await renderSynthetics();
      return;
    }
    if (view === "onboarding") {
      await renderOnboarding();
      return;
    }
    if (view === "network") {
      await renderNetworkAssets();
      return;
    }
    if (view === "security" || view === "vulnerabilities" || view === "ids" || view === "pentest") {
      if (view === "vulnerabilities") state.securityTab = "vulnerabilities";
      if (view === "ids") state.securityTab = "ids";
      if (view === "pentest") state.securityTab = "pentest";
      await renderSecurity();
      return;
    }
    if (view === "incidents") {
      await renderIncidents();
      return;
    }
    if (view === "logs") {
      await renderLogs();
      return;
    }
    if (view === "traces") {
      await renderTraces();
      return;
    }
    if (view === "gateways") {
      await renderGateways();
      return;
      const items = await api("/api/v1/gateways");
      const topology = await api("/api/v1/gateways/topology");
      render(`<section class="grid two"><article class="card"><h3>Gateways</h3>${items.length ? table(["Nome", "Cluster", "Prioridade", "Peso", "Escopo", "Status", "Endpoint", "Heartbeat"], items.map((gateway) => [`<button class="link-button gateway-edit" data-gateway-id="${esc(gateway.id)}" type="button">${esc(gateway.name)}</button><br><small>${esc(gateway.type)}</small>`, esc(gateway.cluster_name || "default"), num(gateway.priority), num(gateway.weight), gateway.shared_with_tenants ? "compartilhado" : gateway.failover_only ? "failover" : "tenant", status(gateway.status), esc(gateway.public_endpoint || (gateway.host ? `${gateway.host}:${gateway.port}` : "-")), fmt(gateway.last_heartbeat)])) : `<p class="muted">Nenhum gateway criado.</p>`}<p class="muted">A ordenacao dos agentes usa prioridade, depois peso para balanceamento e, por fim, failover.</p>${topology.clusters.length ? topology.clusters.map((cluster) => `<div class="card" style="margin-top:12px"><strong>${esc(cluster.cluster_name)}</strong><p class="muted">Primarios: ${num(cluster.primary.length)} | Failover: ${num(cluster.failover.length)} | Compartilhados: ${num(cluster.shared.length)}</p></div>`).join("") : ""}</article><article class="card"><h3>Gateway e cluster</h3><form id="gateway-form" class="form-grid"><input type="hidden" name="gateway_id"><label>Nome<input name="name" required></label><label>Tipo<select name="type"><option value="agents">Gateway Agents</option><option value="integrations">Gateway Integracoes</option><option value="logs">Gateway de Logs</option><option value="security">Gateway de Seguranca</option></select></label><label>Host<input name="host" placeholder="gw01.soservices.com.br"></label><label>Porta<input name="port" value="9443" type="number"></label><label>Cluster<input name="cluster_name" value="default"></label><label>Prioridade<input name="priority" value="100" type="number"></label><label>Peso<input name="weight" value="1" type="number"></label><label>Public endpoint<input name="public_endpoint" placeholder="https://gw01.soservices.com.br:9443"></label><label><input type="checkbox" name="failover_only" style="width:auto; margin-right:8px">Somente failover</label><label><input type="checkbox" name="shared_with_tenants" style="width:auto; margin-right:8px">Compartilhar com tenants</label><label><input type="checkbox" name="tls_enabled" checked style="width:auto; margin-right:8px">TLS habilitado</label><label><input type="checkbox" name="compress_enabled" checked style="width:auto; margin-right:8px">Compressao habilitada</label><label><input type="checkbox" name="encrypt_enabled" checked style="width:auto; margin-right:8px">Protecao dos dados habilitada</label></form><div class="actions" style="margin-top:14px"><button id="create-gateway" class="button primary" type="button">Salvar gateway</button><button id="delete-gateway" class="button ghost" type="button">Excluir</button><button id="cleanup-gateways" class="button ghost" type="button">Limpar testes</button><button id="reset-gateway" class="button ghost" type="button">Novo</button><a class="button ghost" href="/api/v1/agents/download/gateway/linux?gateway_type=agents" target="_blank" rel="noreferrer">Gateway Linux</a><a class="button ghost" href="/api/v1/agents/download/gateway/windows?gateway_type=agents" target="_blank" rel="noreferrer">Gateway Windows Setup</a><a class="button ghost" href="/api/v1/agents/download/gateway/windows?format=ps1&gateway_type=agents" target="_blank" rel="noreferrer">Gateway Windows Script</a></div><p id="gateway-message" class="message"></p></article></section>`);
      const form = $("#gateway-form");
      const resetGatewayForm = () => {
        form.gateway_id.value = "";
        form.name.value = "";
        form.type.value = "agents";
        form.host.value = "";
        form.port.value = 8080;
        form.cluster_name.value = "default";
        form.priority.value = 100;
        form.weight.value = 1;
        form.public_endpoint.value = "";
        form.failover_only.checked = false;
        form.shared_with_tenants.checked = false;
        form.tls_enabled.checked = false;
        form.compress_enabled.checked = false;
        form.encrypt_enabled.checked = false;
      };
      resetGatewayForm();
      $$(".gateway-edit").forEach((button) => {
        button.addEventListener("click", () => {
          const gateway = items.find((item) => item.id === button.dataset.gatewayId);
          if (!gateway) {
            return;
          }
          form.gateway_id.value = gateway.id;
          form.name.value = gateway.name || "";
          form.type.value = gateway.type || "agents";
          form.host.value = gateway.host || "";
          form.port.value = gateway.port || 8080;
          form.cluster_name.value = gateway.cluster_name || "default";
          form.priority.value = gateway.priority || 100;
          form.weight.value = gateway.weight || 1;
          form.public_endpoint.value = gateway.public_endpoint || "";
          form.failover_only.checked = !!gateway.failover_only;
          form.shared_with_tenants.checked = !!gateway.shared_with_tenants;
          form.tls_enabled.checked = !!gateway.tls_enabled;
          form.compress_enabled.checked = !!gateway.compress_enabled;
          form.encrypt_enabled.checked = !!gateway.encrypt_enabled;
        });
      });
      $("#create-gateway").addEventListener("click", async () => {
        const payload = Object.fromEntries(new FormData(form).entries());
        payload.port = Number(payload.port || 8080);
        payload.priority = Number(payload.priority || 100);
        payload.weight = Number(payload.weight || 1);
        payload.failover_only = form.failover_only.checked;
        payload.shared_with_tenants = form.shared_with_tenants.checked;
        payload.tls_enabled = form.tls_enabled.checked;
        payload.compress_enabled = form.compress_enabled.checked;
        payload.encrypt_enabled = form.encrypt_enabled.checked;
        try {
          if (form.gateway_id.value) {
            await api(`/api/v1/gateways/${form.gateway_id.value}`, { method: "PUT", body: JSON.stringify(payload) });
            $("#gateway-message").textContent = "Gateway atualizado.";
          } else {
            await api("/api/v1/gateways", { method: "POST", body: JSON.stringify(payload) });
            $("#gateway-message").textContent = "Gateway criado.";
          }
          await loadView("gateways");
        } catch (error) {
          $("#gateway-message").textContent = error.message;
        }
      });
      $("#delete-gateway").addEventListener("click", async () => {
        if (!form.gateway_id.value) {
          $("#gateway-message").textContent = "Selecione um gateway para excluir.";
          return;
        }
        try {
          await api(`/api/v1/gateways/${form.gateway_id.value}`, { method: "DELETE" });
          $("#gateway-message").textContent = "Gateway excluido.";
          await loadView("gateways");
        } catch (error) {
          $("#gateway-message").textContent = error.message;
        }
      });
      $("#cleanup-gateways").addEventListener("click", async () => {
        try {
          await api("/api/v1/gateways/cleanup", {
            method: "POST",
            body: JSON.stringify({
              delete_names: ["shared-gateway-core", "Gateway infra", "Gateway infra Windows"],
              delete_prefixes: ["demo-gw-", "gateway-hml-"],
              delete_offline_only: true,
            }),
          });
          $("#gateway-message").textContent = "Gateways de teste removidos.";
          await loadView("gateways");
        } catch (error) {
          $("#gateway-message").textContent = error.message;
        }
      });
      $("#reset-gateway").addEventListener("click", resetGatewayForm);
      return;
    }
    if (view === "agents") {
      const items = await api("/api/v1/agents/tokens");
      render(`<section class="grid two"><article class="card"><h3>Instaladores e automacao</h3><p class="muted">Para escolher perfil Infra/Completa e modulos por licenca, use o onboarding do tenant. Estes atalhos baixam o perfil Infra padrao.</p><div class="actions"><a class="button primary" href="/api/v1/agents/download/linux?profile=infra" target="_blank" rel="noreferrer">Agente Linux</a><a class="button ghost" href="/api/v1/agents/download/windows?profile=infra" target="_blank" rel="noreferrer">Agente Windows Setup</a><a class="button ghost" href="/api/v1/agents/download/windows?format=ps1&profile=infra" target="_blank" rel="noreferrer">Agente Windows Script</a><a class="button ghost" href="/api/v1/agents/download/docker?profile=infra" target="_blank" rel="noreferrer">Docker</a><a class="button ghost" href="/api/v1/agents/download/k8s?profile=infra" target="_blank" rel="noreferrer">Kubernetes</a><a class="button ghost" href="/api/v1/agents/download/otel/linux?appname=auto-discovery" target="_blank" rel="noreferrer">OTel Linux</a><a class="button ghost" href="/api/v1/agents/download/otel/windows?appname=auto-discovery" target="_blank" rel="noreferrer">OTel Windows</a><a class="button ghost" href="/api/v1/agents/download/otel-config?language=auto" target="_blank" rel="noreferrer">OTel multi linguagem</a></div></article><article class="card"><h3>Tokens emitidos</h3>${items.length ? table(["Nome", "Papel", "Status", "Preview"], items.map((token) => [esc(token.name), esc(token.role), token.active ? "ativo" : "revogado", `<span class="mono">${esc(token.token_preview)}</span>`])) : `<p class="muted">Nenhum token emitido.</p>`}</article></section>`);
      return;
    }
    if (view === "tasks") {
      await renderTasks();
      return;
    }
    if (view === "alerts") {
      await renderAlerts();
      return;
    }
    if (view === "integrations") {
      await renderIntegrations();
      return;
    }
    if (view === "tickets") {
      await renderTickets();
      return;
    }
    if (view === "users") {
      await renderUsers();
      return;
    }
    if (view === "settings") {
      await renderSettings();
      return;
    }
  } catch (error) {
    if (error.message === "unauthorized") {
      await bootstrap();
      return;
    }
    render(`<article class="card"><h3>Falha ao carregar</h3><p class="muted">${esc(error.message)}</p></article>`);
  }
}

$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("#login-message").textContent = "";
  try {
    await api("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(new FormData(event.currentTarget).entries())),
    });
    await bootstrap();
  } catch {
    $("#login-message").textContent = "Falha no login.";
  }
});

$$(".nav-link").forEach((button) => {
  if (!button.dataset.view) return;
  button.addEventListener("click", () => loadView(button.dataset.view));
});

$("#logout-button").addEventListener("click", async () => {
  await api("/api/v1/auth/logout", { method: "POST" });
  $("#login-screen").classList.remove("hidden");
  $("#app-screen").classList.add("hidden");
  closeInspector();
});

$("#inspector-close")?.addEventListener("click", closeInspector);
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeInspector();
});

$("#ui-toggle")?.addEventListener("click", () => {
  state.ui = state.ui === "v2" ? "classic" : "v2";
  localStorage.setItem(UI_STORAGE_KEY, state.ui);
  applyUi();

  // Re-render current screen in the new UI without forcing navigation.
  if (!$("#app-screen").classList.contains("hidden")) {
    if ($(".entity-detail") && state.selectedHostId) {
      renderHostDetail(state.selectedHostId).catch(() => loadView(state.view));
      return;
    }
    loadView(state.view);
  }
});

applyUi();
bootstrap();
