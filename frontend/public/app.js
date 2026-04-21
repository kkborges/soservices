const state = { view: "dashboard", currentUser: null, selectedHostId: null, hostTimeframe: "1h", topologyScope: "network", filters: {} };

const PLATFORM_VIEWS = ["dashboard", "tenants", "licensing", "settings"];
const TENANT_VIEWS = [
  "dashboard",
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
  "incidents",
  "logs",
  "traces",
  "tickets",
  "integrations",
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

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

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
  if (!response.ok) {
    throw new Error(typeof payload === "string" ? payload : payload.detail || JSON.stringify(payload));
  }
  return payload;
}

const esc = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll('"', "&quot;");
const fmt = (value) => (value ? new Date(value).toLocaleString("pt-BR") : "-");
const num = (value) => Number(value || 0).toLocaleString("pt-BR");
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
  const allowed = new Set(isPlatformAdmin() ? PLATFORM_VIEWS : TENANT_VIEWS);
  $$(".nav-link").forEach((button) => {
    button.classList.toggle("hidden", !allowed.has(button.dataset.view));
  });
  if (!allowed.has(state.view)) {
    state.view = isPlatformAdmin() ? "dashboard" : "hosts";
  }
}

function setView(view) {
  state.view = view;
  $("#view-title").textContent = titleMap[view] || view;
  $$(".nav-link").forEach((button) => {
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
  const data = await api("/api/v1/dashboard/summary");
  const okHosts = Number(data.counters.hosts_online || 0);
  const totalHosts = Number(data.counters.hosts_total || 0);
  const problemHosts = data.problem_hosts || [];
  const hostRows = data.hosts.map((host) => [
    `<button class="link-button dashboard-host-link" data-host-id="${esc(host.id)}" type="button"><strong>${esc(host.hostname)}</strong></button><br><small>${esc(host.ip || "-")}</small>`,
    status(host.status),
    `${num(host.cpu_usage)}%`,
    `${num(host.memory_usage)}%`,
    fmt(host.last_seen),
  ]);
  const logRows = data.logs.map((log) => [
    fmt(log.timestamp),
    esc(log.level),
    esc(log.source || "-"),
    esc(log.message),
  ]);
  const incidentRows = (data.incidents || []).slice(0, 5).map((incident) => [
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
      <article class="card stat"><span class="eyebrow">Gateways</span><strong>${num(data.counters.gateways_total)}</strong><p class="muted">registrados</p></article>
      <article class="card stat"><span class="eyebrow">Logs</span><strong>${num(data.counters.logs_total)}</strong><p class="muted">ingeridos</p></article>
      <article class="card stat"><span class="eyebrow">Traces</span><strong>${num(data.counters.traces_total)}</strong><p class="muted">observabilidade</p></article>
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
  const [data, runtime] = await Promise.all([
    api("/api/v1/admin/overview"),
    api("/api/v1/admin/runtime"),
  ]);
  const customerRows = data.tenants.map((tenant) => [
    esc(tenant.name),
    tenant.internal ? "interno" : "cliente",
    num(tenant.consumption.hosts),
    num(tenant.consumption.network_assets),
    num(tenant.consumption.synthetics),
    num(tenant.consumption.weighted_units),
  ]);
  const gatewayRows = runtime.gateway_health.tenants.map((tenant) => [
    esc(tenant.tenant_name),
    tenant.internal ? "interno" : "cliente",
    num(tenant.online),
    num(tenant.stale),
    num(tenant.offline),
    num(tenant.total),
  ]);
  const instanceRows = (runtime.api_cluster.instances || []).map((item) => [
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
      <article class="card stat"><span class="eyebrow">Clientes</span><strong>${num(data.summary.tenant_customers)}</strong><p class="muted">tenants monitorados</p></article>
      <article class="card stat"><span class="eyebrow">Hosts</span><strong>${num(data.summary.hosts)}</strong><p class="muted">consumo consolidado</p></article>
      <article class="card stat"><span class="eyebrow">Ativos</span><strong>${num(data.summary.network_assets)}</strong><p class="muted">ativos de rede</p></article>
      <article class="card stat"><span class="eyebrow">Sinteticos</span><strong>${num(data.summary.synthetics)}</strong><p class="muted">checks configurados</p></article>
    </section>
    <section class="grid two">
      <article class="card">
        <h3>URLs da plataforma</h3>
        <p><strong>API:</strong> ${esc(data.platform.api_url)}</p>
        <p><strong>Frontend:</strong> ${esc(data.platform.frontend_url)}</p>
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
        <p><strong>Modo HA API:</strong> ${esc(runtime.api_cluster.mode)}</p>
        <p><strong>Instancias esperadas:</strong> ${num(runtime.api_cluster.expected_instances)}</p>
        <p><strong>Instancias ativas previstas:</strong> ${num(runtime.api_cluster.active_instances)}</p>
        <p><strong>Proxy:</strong> ${esc(runtime.api_cluster.frontend_proxy)}</p>
        <p><strong>PostgreSQL:</strong> ${esc(runtime.dependencies.postgres.host)}:${esc(runtime.dependencies.postgres.port)} (${esc(runtime.dependencies.postgres.mode)})</p>
        <p><strong>Redis:</strong> ${esc(runtime.dependencies.redis.host)}:${esc(runtime.dependencies.redis.port)} (${esc(runtime.dependencies.redis.mode)})</p>
        <p><strong>Sentinels:</strong> ${esc((runtime.dependencies.redis.sentinels || []).join(", ") || "-")}</p>
      </article>
      <article class="card">
        <h3>Ingestao ultimas 24h</h3>
        <p><strong>Metricas:</strong> ${num(runtime.ingestion_last_24h.metrics)}</p>
        <p><strong>Logs:</strong> ${num(runtime.ingestion_last_24h.logs)}</p>
        <p><strong>Traces:</strong> ${num(runtime.ingestion_last_24h.traces)}</p>
        <p class="muted">${esc(runtime.cluster_design.tenant_policy)}. Estrategia atual: ${esc(runtime.cluster_design.agent_strategy)}.</p>
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
  const data = await api("/api/v1/admin/overview");
  const licenseRows = data.tenants
    .filter((tenant) => !tenant.internal)
    .map((tenant) => [
      esc(tenant.name),
      status(tenant.status),
      esc(tenant.plan),
      num(tenant.consumption.hosts_infra ?? (tenant.consumption.hosts || 0)),
      num(tenant.consumption.hosts_full ?? 0),
      num(tenant.consumption.hosts),
      num(tenant.consumption.network_assets),
      num(tenant.consumption.users),
      num(tenant.consumption.synthetics),
      num(tenant.consumption.weighted_units),
    ]);
  render(`
    <article class="card">
      <h3>Licenciamento e consumo por tenant</h3>
      ${licenseRows.length ? table(["Tenant", "Status", "Plano", "Hosts Infra", "Hosts Full", "Hosts Total", "Ativos", "Usuarios", "Sinteticos", "Unidades"], licenseRows) : `<p class="muted">Nenhum tenant cliente disponivel.</p>`}
      <p class="muted">O tenant demo concentra o painel operacional atual. O superadmin observa clientes e consumo global.</p>
    </article>
  `);
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
          <label>Slug<input name="slug" required></label>
          <label>Admin nome<input name="admin_name" required></label>
          <label>Admin email<input name="admin_email" placeholder="opcional"></label>
          <label>Admin usuario<input name="admin_username" required></label>
          <label>Senha inicial<input name="admin_password" value="admin123" required></label>
        </form>
        <div class="actions" style="margin-top:14px"><button id="save-tenant" class="button primary" type="button">Criar tenant</button></div>
        <p id="tenant-message" class="message"></p>
      </article>
    </section>
  `);
  $("#save-tenant").addEventListener("click", async () => {
    const payload = Object.fromEntries(new FormData($("#tenant-form")).entries());
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
  render(`<article class="card"><div class="actions"><button id="back-hosts" class="button ghost" type="button">Voltar para hosts</button></div><h3>Configuracao do host</h3><form id="host-settings-form" class="form-grid"><input type="hidden" name="host_id" value="${esc(cfg.id)}"><label>Host<input value="${esc(cfg.hostname)} (${esc(cfg.ip || "-")})" disabled></label><label>Modo<select name="monitoring_mode"><option value="infra">infra</option><option value="infra+otel">infra+otel</option><option value="disabled">disabled</option></select></label><label><input type="checkbox" name="otel_enabled" style="width:auto; margin-right:8px">OTel habilitado</label><label><input type="checkbox" name="log_collection" style="width:auto; margin-right:8px">Coleta de logs</label><label><input type="checkbox" name="ids_enabled" style="width:auto; margin-right:8px">IDS habilitado</label><label><input type="checkbox" name="vuln_scan_enabled" style="width:auto; margin-right:8px">Scan de vulnerabilidades</label><label><input type="checkbox" name="apm_enabled" style="width:auto; margin-right:8px">APM habilitado</label><label style="grid-column:1/-1">Tags<textarea name="tags" placeholder="producao, banco, api"></textarea></label><label style="grid-column:1/-1">Caminhos de log habilitados<textarea name="log_paths" placeholder="/var/log/syslog&#10;/opt/app/logs/app.log"></textarea></label></form><div class="card soft-card" style="margin-top:14px"><div class="section-header"><div><h3>Logs detectados pelo agente</h3><p class="muted">Detectados automaticamente; selecione para habilitar o consumo/processamento.</p></div><button id="add-detected-logs" class="button ghost" type="button">Adicionar selecionados</button></div>${detectedLogs.length ? detectedLogs.map((path, index) => `<label class="check-row"><input type="checkbox" class="detected-log" value="${esc(path)}" ${cfg.log_paths?.includes(path) ? "checked" : ""}>${esc(path)}</label>`).join("") : `<p class="muted">Nenhum log padrao detectado ainda. O agente atualizado informa estes caminhos no proximo heartbeat.</p>`}</div><div class="actions" style="margin-top:14px"><button id="save-host-settings" class="button primary" type="button">Salvar configuracao</button></div><p id="host-settings-message" class="message"></p></article>`);
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
  render(`<section class="entity-detail"><article class="detail-hero card"><div class="detail-hero-main"><p class="eyebrow">Host detalhado</p><h2>${esc(host.hostname)}</h2><p class="muted">${esc(host.os || "sistema nao identificado")} ${host.os_version ? `- ${esc(host.os_version)}` : ""}</p><div class="actions"><button id="back-hosts" class="button ghost" type="button">Voltar para hosts</button>${actionMenu([{ label: "Configuracoes", className: "host-detail-settings" }, { label: "Ir para processos/servicos", className: "host-detail-processes" }, { label: "Ir para logs", className: "host-detail-logs" }, { label: "Informacoes IDS", disabled: !host.ids_enabled }, { label: "Vulnerabilidades", disabled: !host.vuln_scan_enabled }])}</div></div><div class="detail-health">${healthPill(host.status)}<small>Ultima coleta<br><strong>${fmt(host.last_seen)}</strong></small></div></article><article class="card detail-kpis">${metricTile("IP", esc(host.ip || "-"))}${metricTile("Agente", esc(host.agent_version || "nao instalado"), esc(host.monitoring_mode || "-"))}${metricTile("CPU cores", num(host.cpu_cores))}${metricTile("RAM total", `${num(host.memory_total_mb)} MB`)}${metricTile("Disco total", `${num(host.disk_total_gb)} GB`)}${metricTile("Amostras no periodo", num((data.metrics || []).length), `${fmt(data.timeframe?.start)} ate ${fmt(data.timeframe?.end)}`)}</article><article class="card"><div class="section-header"><div><h3>Incidentes do host</h3><p class="muted">Ultimos 2 incidentes abertos ou fechados, com duracao operacional.</p></div></div>${incidents.length ? table(["ID", "Descricao", "Status", "Metrica", "Duracao"], incidents.map((incident) => [`<span class="mono">${esc(incident.id.slice(0, 8))}</span>`, `<strong>${esc(incident.name)}</strong><br><small>${esc(incident.description || "-")}</small>`, status(incident.status), esc(incident.metric || "-"), incidentDuration(incident)])) : `<p class="muted">Nenhum incidente real registrado para este host.</p>`}</article><article class="card"><div class="section-header"><div><h3>Modulos habilitados</h3><p class="muted">Estado operacional configurado para este host. IDS e scan de vulnerabilidade entram aqui no detalhe do host.</p></div></div><div class="feature-grid">${featureTile("Logs", host.log_collection, (host.log_paths || []).length ? `${(host.log_paths || []).length} paths` : "sem paths")}${featureTile("OpenTelemetry", host.otel_enabled)}${featureTile("IDS", host.ids_enabled)}${featureTile("Scan Vulnerabilidade", host.vuln_scan_enabled)}${featureTile("APM", host.apm_enabled)}</div></article><article class="card"><div class="section-header"><div><h3>Consumo de recursos</h3><p class="muted">Dados reais do agente no periodo selecionado. Rede mostra taxa aproximada por segundo derivada dos contadores do host.</p></div></div>${timeframeControl("host-detail", timeframe)}<div class="resource-snapshot">${percentBar("CPU agora", latest.cpuUsage)}${percentBar("Memoria agora", latest.memoryUsage)}${percentBar("Disco agora", latest.diskUsage)}</div><div class="charts-grid three">${seriesChart("CPU", data.metrics, [{ key: "cpuUsage", label: "CPU" }], { max: 100 })}${seriesChart("Memoria", data.metrics, [{ key: "memoryUsage", label: "Memoria" }], { max: 100 })}${seriesChart("Disco", data.metrics, [{ key: "diskUsage", label: "Disco" }], { max: 100 })}</div><div class="charts-grid">${seriesChart("Rede In / Download", rateMetrics, [{ key: "netInRate", label: "In / Download" }])}${seriesChart("Rede Out / Upload", rateMetrics, [{ key: "netOutRate", label: "Out / Upload" }])}</div></article><section class="grid two"><article class="card"><div class="section-header"><div><h3>Processos e consumo</h3><p class="muted">Snapshot real da ultima coleta: ${fmt(data.processes_collected_at)}</p></div>${topProcess ? `<span class="tag">Top: ${esc(topProcess.name)}</span>` : ""}</div>${processes.length ? table(["PID", "Processo", "Usuario", "Status", "CPU", "RAM"], processes.map((proc) => [esc(proc.pid || "-"), esc(proc.name), esc(proc.username || "-"), esc(proc.status || "-"), `${num(proc.cpuUsage)}%`, `${num(proc.memoryUsage)}%`])) : `<p class="muted">Ainda nao ha snapshot real de processos para este host. O proximo ciclo do agente atualizado deve preencher esta area.</p>`}</article><article class="card"><div class="section-header"><div><h3>Ultimos 5 logs</h3><p class="muted">Independente do timeframe do grafico. Mostramos os ultimos logs reais correlacionados por host, hostname ou IP.</p></div></div>${logs.length ? table(["Quando", "Nivel", "Origem", "Mensagem"], logs.map((log) => [fmt(log.timestamp), esc(log.level), esc(log.source || log.service || "-"), esc(log.message)])) : `<p class="muted">Nenhum log real encontrado para este host.</p>`}</article></section></section>`);
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

async function renderNetworkAssets() {
  const items = await api(`/api/v1/network-assets${queryString(state.filters.network || {})}`);
  render(`<section class="grid"><article class="card"><div class="section-header"><div><h3>Discovery e ativos de rede</h3><p class="muted">Varredura real por CIDR. Somente switches, roteadores, firewalls, APs e dispositivos equivalentes aparecem aqui; servidores e estacoes ficam em Hosts.</p></div></div><form id="network-discovery-form" class="form-grid"><label>CIDR<input name="cidr" placeholder="192.168.0.0/24" required></label><label>Portas<input name="ports" value="22,80,443,161,3389,514,8080,8443"></label><label>SNMP community<input name="snmp_community" value="public"></label><label>Timeout ms<input name="timeout_ms" type="number" value="350"></label></form><div class="actions" style="margin-top:14px"><button id="start-network-discovery" class="button primary" type="button">Iniciar discovery</button><button id="refresh-network-assets" class="button ghost" type="button">Atualizar lista</button></div><p id="network-message" class="message"></p></article><article class="card"><h3>Teste SNMP GET</h3><p class="muted">Execute um GET real via gateway do tenant. Use para validar community, ACL e resposta UDP/161 antes do discovery.</p><form id="snmp-get-form" class="form-grid"><label>IP<input name="ip" placeholder="192.168.0.50" required></label><label>Community<input name="snmp_community" value="public"></label><label>OID<input name="oid" value="1.3.6.1.2.1.1.1.0"></label><label>Porta<input name="snmp_port" type="number" value="161"></label></form><div class="actions" style="margin-top:14px"><button id="run-snmp-get" class="button primary" type="button">Executar SNMP GET</button></div><p id="snmp-get-message" class="message"></p></article><article class="card"><h3>Ativos</h3>${filterPanel("network", [{ name: "q", label: "Host/IP/Fabricante" }, { name: "group", label: "Grupo" }, { name: "asset_type", label: "Tipo" }, { name: "manufacturer", label: "Fabricante" }], false)}${items.length ? table(["Host", "Grupo", "Tipo", "SNMP", "SYSLOG", "Fabricante", "Portas", "Acoes"], items.map((asset) => [
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
  const data = await api(`/api/v1/network-assets/${assetId}/detail`);
  const asset = data.asset;
  const ports = data.ports || [];
  render(`<section class="entity-detail"><article class="detail-hero card"><div class="detail-hero-main"><p class="eyebrow">Ativo de rede</p><h2>${esc(asset.hostname || asset.ip)}</h2><p class="muted">${esc(asset.manufacturer || "-")} ${esc(asset.os_firmware || "")}</p><div class="actions"><button id="back-network" class="button ghost" type="button">Voltar para ativos</button></div></div><div class="detail-health">${healthPill(asset.status)}<small>Ultima coleta<br><strong>${fmt(asset.last_poll || asset.last_scan)}</strong></small></div></article><article class="card detail-kpis">${metricTile("IP", esc(asset.ip))}${metricTile("Tipo", esc(asset.asset_type || "-"))}${metricTile("SNMP", asset.snmp_enabled ? "ativo" : "nao")}${metricTile("SYSLOG", asset.syslog_enabled ? "habilitado" : "nao")}${metricTile("Portas", `${num(asset.ports_up)} up / ${num(asset.ports_down)} down`, `${num(asset.port_count)} total`)}</article><article class="card"><h3>Portas e interfaces SNMP</h3>${ports.length ? table(["#", "Nome", "Descricao", "Status", "Velocidade", "RX/TX", "Erros"], ports.map((port) => [num(port.port_number), esc(port.name || "-"), esc(port.description || "-"), status(port.status), `${num(port.speed_mbps)} Mbps`, `${bytes(port.rx_bytes)} / ${bytes(port.tx_bytes)}`, `${num(port.rx_errors)} / ${num(port.tx_errors)}`])) : `<p class="muted">Nenhuma porta coletada ainda. Execute Coletar SNMP no ativo após atualizar o gateway.</p>`}</article></section>`);
  $("#back-network").addEventListener("click", () => renderNetworkAssets());
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

async function renderApplicationsLegacy() {
  const items = await api(`/api/v1/applications${queryString(state.filters.applications || { timeframe: "24h" })}`);
  render(`<section class="grid"><article class="card"><div class="section-header"><div><h3>Aplicacoes</h3><p class="muted">Candidatas descobertas por URLs reais em OTLP/RUM. RUM, traces, servicos, requests e erros ficam correlacionados conforme chegam dados reais.</p></div><div class="actions"><a class="button ghost" href="/api/v1/agents/download/rum-js?appname=web-app" target="_blank" rel="noreferrer">Baixar RUM app.js</a><a class="button ghost" href="/api/v1/agents/download/otel-installer?appname=web-app&language=java" target="_blank" rel="noreferrer">Instalador OTel</a></div></div>${filterPanel("applications", [{ name: "q", label: "URL/contexto" }, { name: "service", label: "Servico" }])}${items.length ? table(["Aplicacao", "Satisfacao", "Sessoes", "Usuarios live", "Requests", "Acoes", "Erros req.", "Erros JS", "Latencia media", "Servicos"], items.map((app) => [`<button class="link-button app-detail-placeholder" type="button"><strong>${esc(app.name)}</strong></button>`, `${num(app.satisfaction_index)}%`, num(app.sessions), num(app.users_online), num(app.requests), num(app.actions), num(app.request_errors), num(app.javascript_errors), `${num(app.avg_response_ms)} ms`, esc((app.services || []).join(", ") || "-")])) : `<p class="muted">Nenhuma aplicacao candidata identificada por traces/RUM ainda.</p>`}</article><article class="card"><h3>Como ativar RUM</h3><p class="muted">Inclua o script antes de fechar o body da aplicacao web. Ele coleta navigation timing, clicks, erros JS e fetch().</p><pre><code>&lt;script src="/api/v1/agents/download/rum-js?appname=minha-app"&gt;&lt;/script&gt;</code></pre><p class="muted">A injecao automatica por agente/gateway em Nginx/Apache/IIS sera o proximo passo quando o agente detectar webservers e paths configurados.</p></article></section>`);
  bindFilters("applications", renderApplications);
  $$(".app-detail-placeholder").forEach((button) => button.addEventListener("click", () => {
    render(`<article class="card"><div class="actions"><button id="back-apps" class="button ghost" type="button">Voltar</button></div><h3>Detalhe da aplicacao</h3><p class="muted">O drill down de sessoes RUM por usuario entrara quando o coletor RUM estiver enviando sessoes, acoes, browser/OS e tempos client/server/network reais.</p></article>`);
    $("#back-apps").addEventListener("click", renderApplications);
  }));
}

async function renderApplications() {
  const items = await api(`/api/v1/applications${queryString(state.filters.applications || { timeframe: "24h" })}`);
  render(`<section class="grid"><article class="card"><div class="section-header"><div><h3>Aplicacoes</h3><p class="muted">Candidatas descobertas por URLs reais em OTLP/RUM. Voce tambem podera criar regras por URL, dominio, host, servico ou API.</p></div><div class="actions"><a class="button ghost" href="/api/v1/agents/download/rum-js?appname=web-app" target="_blank" rel="noreferrer">Baixar RUM app.js</a><a class="button ghost" href="/api/v1/agents/download/otel-installer?appname=web-app&language=java" target="_blank" rel="noreferrer">Instalador OTel</a></div></div>${filterPanel("applications", [{ name: "q", label: "URL/contexto" }, { name: "service", label: "Servico" }])}${items.length ? table(["Aplicacao", "Satisfacao", "Sessoes", "Usuarios live", "Requests", "Acoes", "Erros req.", "Erros JS", "Latencia media", "Servicos"], items.map((app) => [`<button class="link-button app-detail-trigger" data-app-name="${esc(app.name)}" type="button"><strong>${esc(app.name)}</strong></button>`, `${num(app.satisfaction_index)}%`, num(app.sessions), num(app.users_online), num(app.requests), num(app.actions), num(app.request_errors), num(app.javascript_errors), `${num(app.avg_response_ms)} ms`, esc((app.services || []).join(", ") || "-")])) : `<p class="muted">Nenhuma aplicacao candidata identificada por traces/RUM ainda.</p>`}</article><article class="card"><h3>Regras de aplicacao</h3><p class="muted">Proximo passo: persistir regras como URL comeca/termina/contem/igual, dominio, webserver hostname, servico ou API. Hoje a API ja sugere nomes como LAS Home, LAS Protobuf e LAS Smoke a partir das URLs reais.</p><pre><code>Ex.: /las/home = LAS Home\nEx.: /las/protobuf = LAS Protobuf</code></pre></article><article class="card"><h3>Como ativar RUM</h3><p class="muted">Inclua o script antes de fechar o body da aplicacao web. Ele coleta navigation timing, clicks, erros JS e fetch().</p><pre><code>&lt;script src="/api/v1/agents/download/rum-js?appname=minha-app"&gt;&lt;/script&gt;</code></pre></article></section>`);
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
  const data = await api(`/api/v1/synthetics/${testId}/detail`);
  const test = data.test || {};
  const results = data.results || [];
  render(`<section class="grid"><article class="card"><div class="actions"><button id="back-synthetics" class="button ghost" type="button">Voltar</button><button id="run-synthetic-detail" class="button primary" type="button">Executar agora</button></div><h3>${esc(test.name)}</h3><p class="muted">${esc(test.description || "Sem descricao.")}</p><div class="detail-kpis">${metricTile("Tipo", esc(test.type))}${metricTile("Status", esc(test.last_status || "unknown"))}${metricTile("Ultima execucao", fmt(test.last_check))}${metricTile("Resposta", test.last_response_ms ? `${num(test.last_response_ms)} ms` : "-")}${metricTile("Uptime", `${num(test.uptime_pct)}%`)}</div><p><strong>URL:</strong> <span class="mono">${esc(test.url || "-")}</span></p></article><article class="card"><h3>Historico de execucoes</h3>${results.length ? table(["Quando", "Status", "HTTP", "Resposta", "SSL", "Assertions", "Steps", "Erro"], results.map((result) => [fmt(result.timestamp), status(result.status), esc(result.status_code || "-"), result.response_time_ms ? `${num(result.response_time_ms)} ms` : "-", result.ssl_days_remaining == null ? "-" : `${num(result.ssl_days_remaining)} dias`, `${num(result.assertions_passed)} ok / ${num(result.assertions_failed)} falhas`, result.steps_total == null ? "-" : `${num(result.steps_passed)} / ${num(result.steps_total)}`, esc(result.error_message || "-")])) : `<p class="muted">Ainda nao ha execucoes reais para este teste.</p>`}</article><article class="card"><h3>Configuracao</h3><pre><code>${esc(JSON.stringify({ assertions: test.assertions, flow_steps: test.flow_steps, headers: test.headers }, null, 2))}</code></pre></article></section>`);
  $("#back-synthetics").addEventListener("click", renderSynthetics);
  $("#run-synthetic-detail").addEventListener("click", async () => {
    await api(`/api/v1/synthetics/${testId}/run`, { method: "POST" });
    await renderSyntheticDetail(testId);
  });
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
  render(`<section class="grid"><article class="card"><div class="section-header"><div><h3>Logs reais</h3><p class="muted">Exibindo inicialmente 20 linhas. Use os filtros para pesquisar por host, IP, servico, processo, source, nivel e contexto.</p></div><button id="open-log-monitor" class="button ghost" type="button">Criar metrica a partir da busca</button></div>${filterPanel("logs", [{ name: "host", label: "Host" }, { name: "ip", label: "IP" }, { name: "source", label: "Source" }, { name: "level", label: "Level" }, { name: "service", label: "Servico/processo" }, { name: "group", label: "Tipo/tecnologia" }, { name: "q", label: "Contexto mensagem" }])}${items.length ? table(["Quando", "Nivel", "Host", "Origem", "Servico", "Mensagem"], items.map((log) => [fmt(log.timestamp), esc(log.level), `${esc(log.host_name || "-")}<br><small>${esc(log.host_ip || "")}</small>`, esc(log.source || log.group || "-"), esc(log.service || "-"), esc(log.message)])) : `<p class="muted">Nenhum log encontrado para os filtros aplicados.</p>`}</article><article class="card"><h3>Processamento de niveis</h3><p class="muted">${esc(config.note || "")}</p><form id="log-processing-form" class="feature-grid">${(config.available_levels || []).map((level) => `<label class="check-row"><input type="checkbox" name="levels" value="${esc(level)}" ${(config.levels || []).includes(level) ? "checked" : ""}>${esc(level)}</label>`).join("")}</form><div class="actions" style="margin-top:14px"><button id="save-log-processing" class="button primary" type="button">Salvar niveis processados</button></div><p id="log-processing-message" class="message"></p></article><article id="log-monitor-card" class="card hidden"><h3>Nova metrica baseada em logs</h3><p class="muted">A pesquisa atual vira um widget de dashboard e, opcionalmente, uma regra de alerta por contagem.</p><form id="log-monitor-form" class="form-grid"><label>Nome<input name="name" required placeholder="Erro login portal"></label><label>Visualizacao<select name="viz_type"><option value="timeseries">Linha</option><option value="area">Area</option><option value="table">Tabela</option><option value="honeycomb">Honeycomb</option><option value="gauge">Gauge</option></select></label><label>Threshold count<input name="threshold_count" type="number" placeholder="10"></label><label>Severidade<select name="severity"><option value="medium">media</option><option value="high">alta</option><option value="critical">critica</option><option value="low">baixa</option></select></label><label><input type="checkbox" name="create_alert" style="width:auto; margin-right:8px">Criar alerta/incidente</label></form><div class="actions" style="margin-top:14px"><button id="save-log-monitor" class="button primary" type="button">Criar metrica</button></div><p id="log-monitor-message" class="message"></p></article></section>`);
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
}

async function renderTracesLegacy() {
  const items = await api(`/api/v1/traces${queryString(state.filters.traces || { timeframe: "24h" })}`);
  render(`<section class="grid"><article class="card"><div class="section-header"><div><h3>Traces OpenTelemetry</h3><p class="muted">Traces reais recebidos por OTLP JSON/Protobuf via mTLS ou gateway.</p></div><div class="actions"><a class="button ghost" href="/api/v1/agents/download/otel-installer?appname=my-service&language=java" target="_blank" rel="noreferrer">Script auto OTel</a><a class="button ghost" href="/api/v1/agents/download/otel-config?language=auto" target="_blank" rel="noreferrer">Docs multi linguagem</a></div></div>${filterPanel("traces", [{ name: "host", label: "Host" }, { name: "service", label: "Servico" }, { name: "status", label: "Status" }, { name: "q", label: "Trace/URL/contexto" }])}${items.length ? table(["Trace", "Servico", "Nome", "Status", "Metodo", "URL", "Duracao"], items.map((trace) => [`<span class="mono">${esc(trace.trace_id)}</span>`, esc(trace.service), esc(trace.name), status(trace.status), esc(trace.method || "-"), esc(trace.url || "-"), `${num(trace.duration_ms)} ms`])) : `<p class="muted">Nenhum trace encontrado para os filtros aplicados.</p>`}</article><article class="card"><h3>Instrumentacao automatizada</h3><p class="muted">Baixe o helper e execute no host da aplicacao. Exemplo:</p><pre><code>bash las-otel-install.sh --host app01 --appname portal-cliente --language java</code></pre><p class="muted">A automacao completa por processo detectado sera ligada aos processos suportados: Java, .NET, Python, Node.js e Go.</p></article></section>`);
  bindFilters("traces", renderTraces);
}

async function renderTraceDetail(traceId) {
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

async function renderTraces() {
  const items = await api(`/api/v1/traces${queryString(state.filters.traces || { timeframe: "24h" })}`);
  render(`<section class="grid"><article class="card"><div class="section-header"><div><h3>Traces OpenTelemetry</h3><p class="muted">Traces reais recebidos por OTLP JSON/Protobuf via mTLS ou gateway. Clique no trace para drill down.</p></div><div class="actions"><a class="button ghost" href="/api/v1/agents/download/otel-installer?appname=my-service&language=java" target="_blank" rel="noreferrer">Script auto OTel</a><a class="button ghost" href="/api/v1/agents/download/otel-config?language=auto" target="_blank" rel="noreferrer">Docs multi linguagem</a></div></div>${filterPanel("traces", [{ name: "host", label: "Host" }, { name: "service", label: "Servico" }, { name: "status", label: "Status" }, { name: "q", label: "Trace/URL/contexto" }])}${items.length ? table(["Trace", "Servico", "Nome", "Status", "Metodo", "URL", "Duracao"], items.map((trace) => [`<button class="link-button trace-detail-trigger" data-trace-id="${esc(trace.trace_id)}" type="button"><span class="mono">${esc(trace.trace_id)}</span></button>`, esc(trace.service), esc(trace.name), status(trace.status), esc(trace.method || "-"), esc(trace.url || "-"), `${num(trace.duration_ms)} ms`])) : `<p class="muted">Nenhum trace encontrado para os filtros aplicados.</p>`}</article><article class="card"><h3>Instrumentacao automatizada</h3><p class="muted">Baixe o helper e execute no host da aplicacao. Exemplo:</p><pre><code>bash las-otel-install.sh --host app01 --appname portal-cliente --language java</code></pre><p class="muted">A automacao completa por processo detectado sera ligada aos processos suportados: Java, .NET, Python, Node.js e Go.</p></article></section>`);
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
  render(`<section class="grid"><article class="card"><h3>Configuracoes Tenant</h3><p class="muted">Instalacoes, gateways, tarefas, alertas e integracoes ficam agrupados aqui para manter a navegacao principal focada na operacao.</p><div class="actions"><button class="button ghost settings-shortcut" data-view="onboarding" type="button">Instalacoes</button><button class="button ghost settings-shortcut" data-view="gateways" type="button">Gateways</button><button class="button ghost settings-shortcut" data-view="agents" type="button">Agentes</button><button class="button ghost settings-shortcut" data-view="tasks" type="button">Tasks</button><button class="button ghost settings-shortcut" data-view="alerts" type="button">Alertas</button><button class="button ghost settings-shortcut" data-view="integrations" type="button">Integracoes</button><button class="button ghost settings-shortcut" data-view="users" type="button">Usuarios</button></div></article><section class="settings-grid"><article class="card"><h3>Configuracoes da plataforma</h3><form id="settings-form" class="form-grid"><label>Empresa<input name="company_name" value="${esc(data.settings.company_name)}" required></label><label>Nome da plataforma<input name="platform_name" value="${esc(data.settings.platform_name)}" required></label><label>URL da plataforma<input name="platform_url" value="${esc(data.settings.platform_url)}" required></label><label>URL publica<input name="public_web_url" value="${esc(data.settings.public_web_url || "")}"></label><label>SMTP host<input name="smtp_host" value="${esc(data.settings.smtp_host || "")}"></label><label>SMTP porta<input name="smtp_port" type="number" value="${esc(data.settings.smtp_port || "")}"></label><label>SMTP usuario<input name="smtp_user" value="${esc(data.settings.smtp_user || "")}"></label><label>SMTP remetente<input name="smtp_from" value="${esc(data.settings.smtp_from || "")}"></label><label>IA provider<select name="ai_provider"><option ${data.settings.ai_provider === "openai" ? "selected" : ""}>openai</option><option ${data.settings.ai_provider === "anthropic" ? "selected" : ""}>anthropic</option><option ${data.settings.ai_provider === "gemini" ? "selected" : ""}>gemini</option></select></label><label>Modelo IA<input name="ai_model" value="${esc(data.settings.ai_model || "")}"></label><label>Cor primaria<input name="theme_primary" value="${esc(data.settings.theme_primary || "#ff375f")}"></label><label>Cor secundaria<input name="theme_secondary" value="${esc(data.settings.theme_secondary || "#16233a")}"></label><label>Cor da superficie<input name="theme_surface" value="${esc(data.settings.theme_surface || "#0c1527")}"></label></form><div class="actions" style="margin-top:14px"><button id="save-settings" class="button primary" type="button">Salvar</button></div><p id="settings-message" class="message"></p></article><article class="card"><h3>Canais de notificacao</h3>${channels.length ? table(["Nome", "Tipo", "Status"], channels.map((channel) => [esc(channel.name), esc(channel.type), channel.enabled ? "habilitado" : "desabilitado"])) : `<p class="muted">Nenhum canal configurado.</p>`}<form id="channel-form" style="display:grid; gap:12px; margin-top:14px"><label>Nome<input name="name" required></label><label>Tipo<select name="type"><option>email</option><option>slack</option><option>teams</option><option>telegram</option><option>discord</option><option>webhook</option></select></label><label>Configuracao JSON<textarea name="config">{}</textarea></label><label><input type="checkbox" name="enabled" checked style="width:auto; margin-right:8px">Habilitado</label></form><div class="actions" style="margin-top:14px"><button id="save-channel" class="button secondary" type="button">Salvar canal</button></div><p id="channel-message" class="message"></p></article></section></section>`);
  $$(".settings-shortcut").forEach((button) => button.addEventListener("click", () => loadView(button.dataset.view)));
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
  render(`<section class="grid two"><article class="card"><h3>Abertura de ticket</h3><p class="muted">O ticket ja segue com dados do tenant e passa pela analise IA antes do administrador da plataforma atuar.</p><form id="ticket-form" class="form-grid"><label>Titulo<input name="title" required></label><label>Severidade<select name="severity"><option value="medium">media</option><option value="low">baixa</option><option value="high">alta</option><option value="critical">critica</option></select></label><label>Categoria<select name="category"><option value="incident">incidente</option><option value="question">duvida</option><option value="change">mudanca</option></select></label><label>Servico<input name="service_name" placeholder="api, gateway, host, aplicacao"></label><label style="grid-column:1/-1">Descricao<textarea name="description" required placeholder="Descreva o problema, horarios, impacto e passos ja testados."></textarea></label><label style="grid-column:1/-1">Logs/procedimentos<textarea name="log_collection_notes" placeholder="Cole trechos de logs ou instrucoes de coleta ja executadas."></textarea></label><label style="grid-column:1/-1">Anexos referenciados<textarea name="attachments" placeholder="Ex.: print-login.png, /var/log/nginx/error.log, coleta-kalix.zip"></textarea></label></form><div class="actions" style="margin-top:14px"><button id="create-ticket" class="button primary" type="button">Criar ticket</button></div><p id="ticket-message" class="message"></p></article><article class="card"><h3>Tickets do tenant</h3>${items.length ? table(["Titulo", "Severidade", "Status", "Servico", "IA"], items.map((ticket) => [`<button class="link-button ticket-detail" data-ticket-id="${esc(ticket.id)}" type="button">${esc(ticket.title)}</button>`, esc(ticket.severity), status(ticket.status), esc(ticket.service_name || "-"), esc(ticket.ai_status || "-")])) : `<p class="muted">Nenhum ticket aberto.</p>`}</article></section>`);
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

async function renderIntegrations() {
  const items = await api("/api/v1/extensions");
  render(`<article class="card"><div class="section-header"><div><h3>Integracoes</h3><p class="muted">Catalogo de integracoes e extensoes. Cada integracao informa dados coletaveis e onde correlaciona na plataforma.</p></div></div>${items.length ? table(["Integracao", "Categoria", "Status", "Dados coletados", "Correlacao"], items.map((extension) => [`<strong>${esc(extension.name)}</strong><br><small>${esc(extension.slug)}</small><p class="muted">${esc(extension.description || "")}</p>`, esc(extension.category || "-"), extension.installed ? (extension.enabled ? "habilitada" : "instalada/desligada") : "nao instalada", esc((extension.metrics || []).join(", ") || "-"), esc(integrationCorrelation(extension.category))])) : `<p class="muted">Nenhuma extensao catalogada ainda.</p>`}</article>`);
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

async function loadView(view) {
  setView(view);
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
    if (view === "security") {
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
      render(`<section class="grid two"><article class="card"><h3>Instaladores e automacao</h3><p class="muted">Para escolher perfil Infra/Completa e modulos por licenca, use o onboarding do tenant. Estes atalhos baixam o perfil Infra padrao.</p><div class="actions"><a class="button primary" href="/api/v1/agents/download/linux?profile=infra" target="_blank" rel="noreferrer">Agente Linux</a><a class="button ghost" href="/api/v1/agents/download/windows?profile=infra" target="_blank" rel="noreferrer">Agente Windows Setup</a><a class="button ghost" href="/api/v1/agents/download/windows?format=ps1&profile=infra" target="_blank" rel="noreferrer">Agente Windows Script</a><a class="button ghost" href="/api/v1/agents/download/docker?profile=infra" target="_blank" rel="noreferrer">Docker</a><a class="button ghost" href="/api/v1/agents/download/k8s?profile=infra" target="_blank" rel="noreferrer">Kubernetes</a><a class="button ghost" href="/api/v1/agents/download/otel-config?language=auto" target="_blank" rel="noreferrer">OTel multi linguagem</a></div></article><article class="card"><h3>Tokens emitidos</h3>${items.length ? table(["Nome", "Papel", "Status", "Preview"], items.map((token) => [esc(token.name), esc(token.role), token.active ? "ativo" : "revogado", `<span class="mono">${esc(token.token_preview)}</span>`])) : `<p class="muted">Nenhum token emitido.</p>`}</article></section>`);
      return;
    }
    if (view === "tasks") {
      await renderSimpleTable("tasks", "/api/v1/tasks", "Tarefas, scans e coletas", ["Nome", "Tipo", "Status", "Alvo", "Progresso"], (task) => [
        `<strong>${esc(task.name)}</strong><br><small>${fmt(task.scheduled_at)}</small>`,
        esc(task.type),
        status(task.status),
        esc(task.target || "-"),
        `${num(task.progress)}%`,
      ], "Nenhuma tarefa executada ainda.");
      return;
    }
    if (view === "alerts") {
      await renderSimpleTable("alerts", "/api/v1/alerts/rules", "Regras de alerta", ["Nome", "Entidade", "Metrica", "Condicao", "Severidade"], (rule) => [
        esc(rule.name),
        esc(rule.entity_type),
        esc(rule.metric),
        `${esc(rule.condition_op)} ${num(rule.threshold_value)}`,
        esc(rule.severity),
      ], "Nenhuma regra criada ainda.");
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
      await renderSimpleTable("users", "/api/v1/users", "Usuarios", ["Usuario", "Nome", "Email", "Papel", "Status"], (user) => [
        esc(user.username),
        esc(user.full_name || "-"),
        esc(user.email),
        esc(user.role),
        user.active ? "ativo" : "inativo",
      ], "Nenhum usuario cadastrado.");
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
  button.addEventListener("click", () => loadView(button.dataset.view));
});

$("#logout-button").addEventListener("click", async () => {
  await api("/api/v1/auth/logout", { method: "POST" });
  $("#login-screen").classList.remove("hidden");
  $("#app-screen").classList.add("hidden");
});

bootstrap();
