from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["admin-ui"])


ADMIN_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>Mobile Agent Control</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #edf2f6;
      --panel: rgba(255, 255, 255, 0.96);
      --panel-alt: #f7fafc;
      --ink: #12202d;
      --muted: #63707d;
      --line: #d7dfe6;
      --brand: #1560d0;
      --brand-soft: #e5efff;
      --good: #dff1df;
      --warn: #f8e8c7;
      --bad: #f6d8dc;
      --shadow: 0 14px 38px rgba(17, 31, 46, 0.08);
      --radius: 18px;
      --radius-sm: 14px;
      --safe-top: env(safe-area-inset-top, 0px);
      --safe-bottom: env(safe-area-inset-bottom, 0px);
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; min-height: 100%; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(21, 96, 208, 0.08), transparent 28%),
        linear-gradient(180deg, #f7fafc 0%, var(--bg) 100%);
      color: var(--ink);
      -webkit-font-smoothing: antialiased;
    }
    button, input, select, textarea { font: inherit; }
    .app {
      max-width: 1480px;
      margin: 0 auto;
      padding: calc(18px + var(--safe-top)) 16px calc(24px + var(--safe-bottom));
    }
    .topbar {
      position: sticky;
      top: 0;
      z-index: 20;
      margin: -18px -16px 16px;
      padding: calc(16px + var(--safe-top)) 16px 14px;
      background: rgba(247, 250, 252, 0.92);
      backdrop-filter: blur(14px);
      border-bottom: 1px solid rgba(215, 223, 230, 0.85);
    }
    .topbar-row, .section-header, .card-header, .meta-row, .action-row, .chip-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }
    .brand h1 { margin: 0; font-size: clamp(22px, 3vw, 30px); letter-spacing: -0.03em; }
    .brand p { margin: 6px 0 0; color: var(--muted); font-size: 14px; }
    .status-pill, .chip {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 7px 12px;
      font-size: 12px;
      font-weight: 700;
      border: 1px solid transparent;
      white-space: nowrap;
    }
    .stream-live, .status-online, .status-idle, .status-completed, .status-healthy { background: var(--good); }
    .stream-connecting, .stream-reconnecting, .status-starting, .status-running, .status-pending { background: var(--warn); }
    .status-warning, .status-stuck { background: #f2d3ac; }
    .status-failed, .status-stopped, .status-offline, .status-rejected, .status-error, .status-cancelled { background: var(--bad); }
    .surface {
      background: var(--panel);
      border: 1px solid rgba(215, 223, 230, 0.9);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }
    .config-bar, .grid, .stack, .kpis, .launch-grid, .list, .bottom-grid {
      display: grid;
      gap: 16px;
    }
    .config-bar {
      grid-template-columns: minmax(0, 1.45fr) minmax(0, 0.9fr) auto auto;
      padding: 16px;
      margin-bottom: 16px;
    }
    .grid { grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.9fr); }
    .stack { min-width: 0; }
    .bottom-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); margin-top: 16px; }
    .kpis { grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
    .launch-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .section { padding: 16px; min-width: 0; }
    label { display: block; margin-bottom: 6px; font-size: 13px; color: var(--muted); font-weight: 600; }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: #fff;
      color: var(--ink);
      padding: 12px 14px;
      min-height: 46px;
      appearance: none;
      -webkit-appearance: none;
    }
    textarea { min-height: 108px; resize: vertical; line-height: 1.4; }
    input:focus, select:focus, textarea:focus {
      outline: 2px solid rgba(21, 96, 208, 0.18);
      border-color: rgba(21, 96, 208, 0.48);
    }
    button {
      border: 1px solid var(--brand);
      background: var(--brand);
      color: #fff;
      border-radius: 14px;
      min-height: 46px;
      padding: 12px 16px;
      font-weight: 700;
      cursor: pointer;
      touch-action: manipulation;
    }
    button:disabled { opacity: 0.55; cursor: default; }
    .secondary { background: #fff; color: var(--brand); }
    .flash {
      display: none;
      padding: 12px 14px;
      margin-bottom: 16px;
      border-radius: 14px;
      font-size: 14px;
      font-weight: 600;
    }
    .flash.show { display: block; }
    .flash.ok { background: var(--good); }
    .flash.bad { background: var(--bad); }
    .section-header h2, .section-header h3 { margin: 0; font-size: 18px; letter-spacing: -0.02em; }
    .subtle, .tiny { color: var(--muted); font-size: 13px; }
    .kpi {
      padding: 14px;
      border-radius: var(--radius-sm);
      border: 1px solid var(--line);
      background: var(--panel-alt);
    }
    .kpi-label { color: var(--muted); font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
    .kpi-value { margin-top: 10px; font-size: clamp(22px, 3vw, 28px); font-weight: 800; letter-spacing: -0.03em; }
    .kpi-meta { margin-top: 8px; color: var(--muted); font-size: 13px; }
    .scroll {
      max-height: 540px;
      overflow: auto;
      overscroll-behavior: contain;
      -webkit-overflow-scrolling: touch;
      padding-right: 4px;
    }
    .card {
      padding: 14px;
      border-radius: var(--radius-sm);
      border: 1px solid var(--line);
      background: #fff;
      min-width: 0;
    }
    .card.selectable { cursor: pointer; touch-action: manipulation; }
    .card.selectable.selected {
      border-color: rgba(21, 96, 208, 0.5);
      background: var(--brand-soft);
      box-shadow: inset 0 0 0 1px rgba(21, 96, 208, 0.08);
    }
    .card-title { font-size: 15px; font-weight: 800; letter-spacing: -0.01em; }
    .mono {
      font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
      word-break: break-word;
      font-size: 12px;
    }
    .log-view {
      min-height: 300px;
      max-height: 620px;
      overflow: auto;
      overscroll-behavior: contain;
      -webkit-overflow-scrolling: touch;
      border-radius: 16px;
      padding: 14px;
      background: #0f1822;
      color: #d7e4f1;
      font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
      font-size: 12px;
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.45;
    }
    .empty { padding: 22px 0; color: var(--muted); font-size: 14px; }
    @media (max-width: 1180px) {
      .grid, .bottom-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 860px) {
      .config-bar, .kpis, .launch-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 640px) {
      .app { padding-left: 12px; padding-right: 12px; }
      .topbar { margin-left: -12px; margin-right: -12px; padding-left: 12px; padding-right: 12px; }
      .section, .card { padding: 12px; }
      button { width: 100%; }
      .action-row button { width: auto; flex: 1 1 140px; }
    }
  </style>
</head>
<body>
  <div class="app">
    <header class="topbar">
      <div class="topbar-row">
        <div class="brand">
          <h1>Mobile Agent Control</h1>
          <p>Responsive local control plane for Gemini-first terminal agents, usable on desktop and mobile browsers.</p>
        </div>
        <div id="streamState" class="status-pill stream-reconnecting">Disconnected</div>
      </div>
    </header>

    <section class="surface config-bar">
      <div>
        <label for="baseUrl">Supervisor Base URL</label>
        <input id="baseUrl" inputmode="url" autocomplete="url" placeholder="https://machine.tailnet.ts.net:8000" />
      </div>
      <div>
        <label for="token">Bearer Token</label>
        <input id="token" autocapitalize="off" autocorrect="off" spellcheck="false" placeholder="0118" />
      </div>
      <button class="secondary" id="saveConfig">Save Config</button>
      <button id="refreshAll">Refresh</button>
    </section>

    <div id="flash" class="flash"></div>

    <div class="grid">
      <div class="stack">
        <section class="surface section">
          <div class="section-header">
            <div>
              <h2>Fleet Dashboard</h2>
              <div class="subtle">At-a-glance health, activity, and active runtime state for this machine supervisor.</div>
            </div>
          </div>
          <div id="machineKpis" class="kpis"></div>
        </section>

        <section class="surface section">
          <div class="section-header">
            <div>
              <h2>Launch Agent</h2>
              <div class="subtle">Standards-based HTTPS + WebSocket control path. Gemini is the default runtime.</div>
            </div>
          </div>
          <div class="launch-grid">
            <div>
              <label for="launchType">Runtime Type</label>
              <select id="launchType"></select>
            </div>
            <div>
              <label for="launchProfile">Launch Profile</label>
              <select id="launchProfile"></select>
            </div>
          </div>
          <div class="launch-grid" style="margin-top:12px">
            <div>
              <label for="workspace">Workspace</label>
              <select id="workspace"></select>
            </div>
            <div>
              <label for="runtimeModel">Model</label>
              <input id="runtimeModel" autocapitalize="off" autocorrect="off" spellcheck="false" placeholder="gemini-2.5-pro" />
            </div>
          </div>
          <div class="launch-grid" style="margin-top:12px">
            <div>
              <label for="slashCommand">Slash Command</label>
              <select id="slashCommand"></select>
            </div>
            <div>
              <label>MCP Availability</label>
              <div id="mcpSummary" class="card" style="padding:12px; background:var(--panel-alt)">No MCP servers configured.</div>
            </div>
          </div>
          <div style="margin-top:12px">
            <label for="initialPrompt">Initial Prompt</label>
            <textarea id="initialPrompt" placeholder="Optional initial task or prompt"></textarea>
          </div>
          <div class="action-row">
            <button id="launchAgent">Launch Agent</button>
            <button class="secondary" id="refreshLaunchContext">Refresh Context</button>
          </div>
        </section>

        <section class="surface section">
          <div class="section-header">
            <div>
              <h2>Running Now</h2>
              <div class="subtle">Active and queued agents with touch-safe selection, recent output, and monitoring state.</div>
            </div>
          </div>
          <div id="runningAgentsList" class="list scroll"></div>
        </section>

        <section class="surface section">
          <div class="section-header">
            <div>
              <h2>Logs</h2>
              <div class="subtle">Optimized for touch scrolling and mobile viewport overflow.</div>
            </div>
          </div>
          <div id="logView" class="log-view">Select an agent to view logs.</div>
        </section>
      </div>

      <div class="stack">
        <section class="surface section">
          <div class="section-header">
            <div>
              <h2>Selected Agent</h2>
              <div class="subtle">Quick actions, current runtime state, and Gemini-specific launch metadata.</div>
            </div>
          </div>
          <div id="selectedAgentMeta" class="empty">No agent selected.</div>
          <div style="margin-top:12px">
            <label for="agentPrompt">Send Prompt</label>
            <textarea id="agentPrompt" placeholder="Send work to the selected agent"></textarea>
          </div>
          <div class="action-row">
            <button id="sendPrompt">Send Prompt</button>
            <button class="secondary" id="restartAgent">Restart</button>
            <button class="secondary" id="stopAgent">Stop</button>
          </div>
        </section>

        <section class="surface section">
          <div class="section-header">
            <div>
              <h2>Recent Result</h2>
              <div class="subtle">Latest completed or failed job summary for the selected agent.</div>
            </div>
          </div>
          <div id="latestResult" class="empty">No completed task selected.</div>
        </section>

        <section class="surface section">
          <div class="section-header">
            <div>
              <h2>Runtime Support</h2>
              <div class="subtle">Installed adapters, auth status, versions, and warnings.</div>
            </div>
          </div>
          <div id="runtimeList" class="list"></div>
        </section>
      </div>
    </div>

    <div class="bottom-grid">
      <section class="surface section">
        <div class="section-header">
          <div>
            <h3>Tasks</h3>
            <div class="subtle">Recent runs with completion and failure summaries.</div>
          </div>
        </div>
        <div id="tasksList" class="list scroll"></div>
      </section>
      <section class="surface section">
        <div class="section-header">
          <div>
            <h3>Audit</h3>
            <div class="subtle">Operator actions, launches, restarts, and failures.</div>
          </div>
        </div>
        <div id="auditList" class="list scroll"></div>
      </section>
      <section class="surface section">
        <div class="section-header">
          <div>
            <h3>Slash Commands</h3>
            <div class="subtle">Configured Gemini slash commands for the current workspace context.</div>
          </div>
        </div>
        <div id="slashCommandsList" class="list scroll"></div>
      </section>
    </div>
  </div>
  <script>
    const state = {
      machineSelf: null,
      machineHealth: null,
      agents: [],
      running: [],
      tasks: [],
      audit: [],
      profiles: [],
      workspaces: [],
      runtimeAdapters: [],
      slashCommands: [],
      mcpServers: [],
      selectedAgentId: null,
      ws: null,
      reconnectTimer: null
    };

    function el(id) { return document.getElementById(id); }
    function getConfig() {
      return {
        baseUrl: (el("baseUrl").value || "").trim().replace(/\\/$/, ""),
        token: (el("token").value || "").trim()
      };
    }
    function saveConfig() {
      localStorage.setItem("admin.baseUrl", el("baseUrl").value.trim());
      localStorage.setItem("admin.token", el("token").value.trim());
      flash("Saved local web console config.", "ok");
    }
    function loadConfig() {
      el("baseUrl").value = localStorage.getItem("admin.baseUrl") || window.location.origin;
      el("token").value = localStorage.getItem("admin.token") || "0118";
    }
    function flash(message, kind) {
      const node = el("flash");
      node.textContent = message;
      node.className = "flash show " + kind;
      clearTimeout(node._timer);
      node._timer = setTimeout(function() { node.className = "flash"; }, 3600);
    }
    function escapeHtml(value) {
      return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    }
    function statusClass(value) {
      return "chip status-" + String(value || "unknown").toLowerCase();
    }
    function streamClass(value) {
      const lower = String(value || "").toLowerCase();
      if (lower.indexOf("live") >= 0) return "status-pill stream-live";
      if (lower.indexOf("connect") >= 0) return "status-pill stream-connecting";
      return "status-pill stream-reconnecting";
    }
    function api(path, options) {
      const config = getConfig();
      return fetch(config.baseUrl + path, {
        method: (options && options.method) || "GET",
        headers: {
          "Authorization": "Bearer " + config.token,
          "Content-Type": "application/json"
        },
        body: options && options.body ? options.body : undefined
      }).then(async function(response) {
        if (!response.ok) {
          const text = await response.text();
          throw new Error(text || (response.status + " " + response.statusText));
        }
        return response.json();
      });
    }
    function selectedWorkspace() { return el("workspace").value || ""; }
    function selectedProfile() {
      return state.profiles.find(function(profile) { return profile.id === el("launchProfile").value; }) || null;
    }
    function selectedRuntimeAdapterId() {
      const profile = selectedProfile();
      return profile ? profile.adapter_id : "gemini-cli";
    }
    function updateStreamState(label) {
      const node = el("streamState");
      node.textContent = label;
      node.className = streamClass(label);
    }
    function formatDuration(seconds) {
      if (seconds == null) return "-";
      const total = Number(seconds);
      const hours = Math.floor(total / 3600);
      const minutes = Math.floor((total % 3600) / 60);
      const remainder = total % 60;
      if (hours > 0) return hours + "h " + minutes + "m";
      if (minutes > 0) return minutes + "m " + remainder + "s";
      return remainder + "s";
    }
    function latestTaskForAgent(agentId) {
      return state.tasks.find(function(task) { return task.agent_id === agentId; }) || null;
    }
    function mergeById(list, item) {
      const index = list.findIndex(function(entry) { return entry.id === item.id; });
      if (index >= 0) list[index] = item;
      else list.unshift(item);
    }
    function mergeAgent(agent) {
      mergeById(state.agents, agent);
      state.agents.sort(function(a, b) { return String(b.updated_at || "").localeCompare(String(a.updated_at || "")); });
    }
    function mergeTask(task) {
      mergeById(state.tasks, task);
      state.tasks.sort(function(a, b) { return String(b.updated_at || "").localeCompare(String(a.updated_at || "")); });
    }
    function mergeAudit(entry) {
      mergeById(state.audit, entry);
      state.audit.sort(function(a, b) { return String(b.timestamp || "").localeCompare(String(a.timestamp || "")); });
    }
    function mergeRunningStatus(status) {
      const index = state.running.findIndex(function(item) { return item.agent_id === status.agent_id; });
      if (index >= 0) state.running[index] = status;
      else state.running.unshift(status);
      state.running.sort(function(a, b) { return Number(b.elapsed_seconds || 0) - Number(a.elapsed_seconds || 0); });
    }
    function renderMachine() {
      const self = state.machineSelf;
      const health = state.machineHealth;
      if (!self || !self.machine) {
        el("machineKpis").innerHTML = "<div class='empty'>Machine data not loaded yet.</div>";
        return;
      }
      const machine = self.machine;
      const warningCount = health ? health.warning_count : 0;
      const failedCount = health ? health.agents_failed : 0;
      const heartbeat = health ? health.last_heartbeat : machine.updated_at;
      const cpu = health && health.resources && health.resources.cpu_percent != null ? Math.round(health.resources.cpu_percent) + "%" : "-";
      const memory = health && health.resources && health.resources.memory_mb != null ? Math.round(health.resources.memory_mb) + " MB" : "-";
      const mcpSummary = health ? (health.mcp_healthy_count + "/" + health.mcp_server_count) : "0/0";
      el("machineKpis").innerHTML = [
        "<div class='kpi'><div class='kpi-label'>Machine</div><div class='kpi-value'>" + escapeHtml(machine.name) + "</div><div class='kpi-meta mono'>" + escapeHtml(machine.id) + "</div></div>",
        "<div class='kpi'><div class='kpi-label'>Supervisor</div><div class='kpi-value'><span class='" + statusClass(health ? health.monitor_state : machine.status) + "'>" + escapeHtml(health ? health.monitor_state : machine.status) + "</span></div><div class='kpi-meta'>Heartbeat " + escapeHtml(heartbeat || "-") + "</div></div>",
        "<div class='kpi'><div class='kpi-label'>Workers</div><div class='kpi-value'>" + machine.worker_pool.busy_workers + "/" + machine.worker_pool.desired_workers + "</div><div class='kpi-meta'>Queue " + machine.worker_pool.queue_depth + " · Active agents " + self.active_agents + "</div></div>",
        "<div class='kpi'><div class='kpi-label'>Warnings</div><div class='kpi-value'>" + warningCount + "</div><div class='kpi-meta'>Failed " + failedCount + " · MCP " + mcpSummary + "</div></div>",
        "<div class='kpi'><div class='kpi-label'>CPU</div><div class='kpi-value'>" + escapeHtml(cpu) + "</div><div class='kpi-meta'>Host load</div></div>",
        "<div class='kpi'><div class='kpi-label'>Memory</div><div class='kpi-value'>" + escapeHtml(memory) + "</div><div class='kpi-meta'>Host memory</div></div>",
        "<div class='kpi'><div class='kpi-label'>Recent Activity</div><div class='kpi-value'>" + state.tasks.filter(function(task) { return ["completed", "failed", "cancelled"].indexOf(task.state) >= 0; }).slice(0, 6).length + "</div><div class='kpi-meta'>Task outcomes in current view</div></div>",
        "<div class='kpi'><div class='kpi-label'>Runtime Support</div><div class='kpi-value'>" + state.runtimeAdapters.filter(function(adapter) { return adapter.status && adapter.status.installed && adapter.status.installed.available; }).length + "</div><div class='kpi-meta'>Installed adapters</div></div>"
      ].join("");
    }
    function renderProfiles() {
      const currentType = el("launchType").value || "gemini";
      const types = [];
      state.profiles.forEach(function(profile) {
        if (types.indexOf(profile.agent_type) === -1) types.push(profile.agent_type);
      });
      if (!types.length) types.push("gemini");
      el("launchType").innerHTML = types.map(function(type) {
        return "<option value='" + escapeHtml(type) + "'" + (type === currentType ? " selected" : "") + ">" + escapeHtml(type.toUpperCase()) + "</option>";
      }).join("");
      const chosenType = el("launchType").value || currentType;
      const profiles = state.profiles.filter(function(profile) { return profile.agent_type === chosenType; });
      el("launchProfile").innerHTML = profiles.map(function(profile) {
        return "<option value='" + escapeHtml(profile.id) + "'>" + escapeHtml(profile.label) + "</option>";
      }).join("");
      if (profiles.length) {
        const metadata = profiles[0].metadata || {};
        if (!el("runtimeModel").value && metadata.default_model) {
          el("runtimeModel").value = metadata.default_model;
        }
      }
    }
    function renderWorkspaces() {
      el("workspace").innerHTML = state.workspaces.map(function(workspace) {
        return "<option value='" + escapeHtml(workspace.path) + "'>" + escapeHtml(workspace.label + " · " + workspace.source) + "</option>";
      }).join("");
    }
    function renderRuntimeAdapters() {
      const node = el("runtimeList");
      if (!state.runtimeAdapters.length) {
        node.innerHTML = "<div class='empty'>No runtime adapters reported by this supervisor.</div>";
        return;
      }
      node.innerHTML = state.runtimeAdapters.map(function(adapter) {
        const status = adapter.status || {};
        const warnings = (status.warnings || []).map(function(warning) {
          return "<div class='tiny' style='color:#8e3e43'>" + escapeHtml(warning) + "</div>";
        }).join("");
        return [
          "<div class='card'>",
          "<div class='card-header'><div><div class='card-title'>" + escapeHtml(adapter.label) + "</div><div class='tiny'>" + escapeHtml(status.version || "Version unavailable") + "</div></div><span class='" + statusClass(status.auth && status.auth.available ? "healthy" : "warning") + "'>" + escapeHtml((status.auth && status.auth.available) ? "ready" : "attention") + "</span></div>",
          "<div class='meta-row'><span class='" + statusClass(status.installed && status.installed.available ? "online" : "offline") + "'>" + escapeHtml((status.installed && status.installed.available) ? "installed" : "missing") + "</span><span class='" + statusClass(status.auth && status.auth.available ? "completed" : "warning") + "'>" + escapeHtml((status.auth && status.auth.available) ? "auth ok" : "auth needed") + "</span></div>",
          "<div class='tiny mono' style='margin-top:8px'>" + escapeHtml(status.binary_path || "-") + "</div>",
          status.auth && status.auth.message ? "<div class='tiny' style='margin-top:8px'>" + escapeHtml(status.auth.message) + "</div>" : "",
          warnings,
          "</div>"
        ].join("");
      }).join("");
    }
    function renderSlashCommands() {
      const node = el("slashCommandsList");
      const select = el("slashCommand");
      if (!state.slashCommands.length) {
        select.innerHTML = "<option value=''>No slash command</option>";
        node.innerHTML = "<div class='empty'>No Gemini slash commands configured for this workspace.</div>";
        return;
      }
      select.innerHTML = "<option value=''>No slash command</option>" + state.slashCommands.map(function(command) {
        return "<option value='" + escapeHtml(command.name) + "'>" + escapeHtml("/" + command.name + " · " + command.scope) + "</option>";
      }).join("");
      node.innerHTML = state.slashCommands.map(function(command) {
        return [
          "<div class='card'>",
          "<div class='card-header'><div><div class='card-title'>/" + escapeHtml(command.name) + "</div><div class='tiny'>" + escapeHtml(command.description || command.scope) + "</div></div><span class='" + statusClass("healthy") + "'>" + escapeHtml(command.scope) + "</span></div>",
          "<div class='tiny mono'>" + escapeHtml(command.path) + "</div>",
          command.prompt_preview ? "<div class='tiny' style='margin-top:8px'>" + escapeHtml(command.prompt_preview) + "</div>" : "",
          "</div>"
        ].join("");
      }).join("");
    }
    function renderMcpSummary() {
      const servers = state.mcpServers || [];
      if (!servers.length) {
        el("mcpSummary").innerHTML = "No MCP servers configured for this machine/workspace.";
        return;
      }
      el("mcpSummary").innerHTML = servers.slice(0, 4).map(function(server) {
        return "<div class='meta-row' style='margin-bottom:6px'><span class='" + statusClass(server.health) + "'>" + escapeHtml(server.health) + "</span><span>" + escapeHtml(server.name) + "</span><span class='tiny'>" + escapeHtml(server.transport + " · " + server.scope) + "</span></div>";
      }).join("");
    }
    function renderRunningAgents() {
      const node = el("runningAgentsList");
      if (!state.running.length) {
        node.innerHTML = "<div class='empty'>No active or queued agents right now.</div>";
        return;
      }
      node.innerHTML = state.running.map(function(agent) {
        const selected = state.selectedAgentId === agent.agent_id ? " selected" : "";
        const logs = agent.recent_logs || [];
        const lastLog = logs.length ? logs[logs.length - 1].message : "No recent output.";
        const runtimeBits = [agent.runtime_model, agent.command_name ? "/" + agent.command_name : null, agent.mcp_enabled ? "MCP" : null].filter(Boolean).join(" · ");
        return [
          "<div class='card selectable" + selected + "' data-agent='" + escapeHtml(agent.agent_id) + "'>",
          "<div class='card-header'><div><div class='card-title'>" + escapeHtml((agent.type || "").toUpperCase() + " on " + (agent.machine_name || "")) + "</div><div class='tiny mono'>" + escapeHtml(agent.agent_id) + "</div></div><span class='" + statusClass(agent.monitor_state || agent.state) + "'>" + escapeHtml(agent.monitor_state || agent.state) + "</span></div>",
          "<div class='chip-row'><span class='chip'>" + escapeHtml("Elapsed " + formatDuration(agent.elapsed_seconds)) + "</span><span class='chip'>" + escapeHtml("PID " + (agent.pid || "-")) + "</span></div>",
          runtimeBits ? "<div class='tiny' style='margin-top:8px'>" + escapeHtml(runtimeBits) + "</div>" : "",
          "<div class='tiny mono' style='margin-top:8px'>" + escapeHtml(agent.workspace || "-") + "</div>",
          "<div style='margin-top:8px'>" + escapeHtml(lastLog) + "</div>",
          agent.warning_message ? "<div class='tiny' style='margin-top:8px; color:#8e3e43'>" + escapeHtml(agent.warning_message) + "</div>" : "",
          "</div>"
        ].join("");
      }).join("");
      Array.prototype.forEach.call(document.querySelectorAll("[data-agent]"), function(nodeItem) {
        nodeItem.addEventListener("click", function() { selectAgent(nodeItem.getAttribute("data-agent")); });
      });
    }
    function renderTasks() {
      const node = el("tasksList");
      if (!state.tasks.length) {
        node.innerHTML = "<div class='empty'>No task history.</div>";
        return;
      }
      node.innerHTML = state.tasks.slice(0, 24).map(function(task) {
        return [
          "<div class='card'>",
          "<div class='card-header'><div><div class='card-title'>" + escapeHtml(task.kind) + "</div><div class='tiny mono'>" + escapeHtml(task.id) + "</div></div><span class='" + statusClass(task.state) + "'>" + escapeHtml(task.state) + "</span></div>",
          "<div>" + escapeHtml(task.input_text || "") + "</div>",
          "<div class='tiny' style='margin-top:8px'>" + escapeHtml(task.summary || task.error || "") + "</div>",
          "</div>"
        ].join("");
      }).join("");
    }
    function renderAudit() {
      const node = el("auditList");
      if (!state.audit.length) {
        node.innerHTML = "<div class='empty'>No audit entries.</div>";
        return;
      }
      node.innerHTML = state.audit.slice(0, 24).map(function(entry) {
        return [
          "<div class='card'>",
          "<div class='card-header'><div><div class='card-title'>" + escapeHtml(entry.action) + "</div><div class='tiny mono'>" + escapeHtml(entry.target_id) + "</div></div><span class='" + statusClass(entry.status) + "'>" + escapeHtml(entry.status) + "</span></div>",
          "<div>" + escapeHtml(entry.message || "") + "</div>",
          "<div class='tiny' style='margin-top:8px'>" + escapeHtml(entry.timestamp || "") + "</div>",
          "</div>"
        ].join("");
      }).join("");
    }
    function renderSelectedAgent() {
      const agent = state.agents.find(function(item) { return item.id === state.selectedAgentId; }) || null;
      if (!agent) {
        el("selectedAgentMeta").innerHTML = "No agent selected.";
        el("latestResult").innerHTML = "No completed task selected.";
        el("logView").textContent = "Select an agent to view logs.";
        return;
      }
      const task = latestTaskForAgent(agent.id);
      const recentLogs = agent.recent_logs || [];
      const runtimeDetails = [agent.runtime_model, agent.command_name ? "/" + agent.command_name : null, agent.mcp_enabled ? ("MCP " + ((agent.mcp_servers || []).join(", "))) : null].filter(Boolean).join(" · ");
      el("selectedAgentMeta").innerHTML = [
        "<div class='card-title'>" + escapeHtml((agent.type || "").toUpperCase()) + "</div>",
        "<div class='chip-row' style='margin-top:8px'><span class='" + statusClass(agent.state) + "'>" + escapeHtml(agent.state) + "</span><span class='chip'>PID " + escapeHtml(agent.pid || "-") + "</span><span class='chip'>Worker " + escapeHtml(agent.worker_id || "-") + "</span></div>",
        "<div class='tiny mono' style='margin-top:8px'>" + escapeHtml(agent.id) + "</div>",
        "<div class='tiny mono' style='margin-top:8px'>" + escapeHtml(agent.workspace || "-") + "</div>",
        "<div class='tiny' style='margin-top:8px'>Profile " + escapeHtml(agent.launch_profile || "-") + "</div>",
        runtimeDetails ? "<div class='tiny' style='margin-top:8px'>" + escapeHtml(runtimeDetails) + "</div>" : "",
        agent.last_output_at ? "<div class='tiny' style='margin-top:8px'>Last output " + escapeHtml(agent.last_output_at) + "</div>" : "",
        "<div style='margin-top:10px'>" + escapeHtml(agent.current_task || "No current task.") + "</div>"
      ].join("");
      el("logView").textContent = recentLogs.length ? recentLogs.map(function(log) {
        return "[" + log.timestamp + "] " + log.stream + ": " + log.message;
      }).join("\\n") : "No logs.";
      el("latestResult").innerHTML = task && ["completed", "failed", "cancelled"].indexOf(task.state) >= 0
        ? "<div class='chip-row'><span class='" + statusClass(task.state) + "'>" + escapeHtml(task.state) + "</span><span class='chip'>" + escapeHtml(task.kind) + "</span></div><div style='margin-top:10px'>" + escapeHtml(task.summary || task.error || task.input_text || "") + "</div>"
        : "No completed task selected.";
    }
    function selectAgent(agentId) {
      state.selectedAgentId = agentId;
      renderRunningAgents();
      renderSelectedAgent();
    }
    async function refreshLaunchContext() {
      renderProfiles();
      renderWorkspaces();
      const adapterId = selectedRuntimeAdapterId();
      const workspace = selectedWorkspace();
      try {
        const [runtime, commands, machineMcp] = await Promise.all([
          api("/runtime/adapters/" + encodeURIComponent(adapterId) + (workspace ? ("?workspace=" + encodeURIComponent(workspace)) : "")),
          api("/runtime/adapters/" + encodeURIComponent(adapterId) + "/commands" + (workspace ? ("?workspace=" + encodeURIComponent(workspace)) : "")),
          state.machineSelf && state.machineSelf.machine ? api("/machines/" + encodeURIComponent(state.machineSelf.machine.id) + "/mcp" + (workspace ? ("?workspace=" + encodeURIComponent(workspace)) : "")) : Promise.resolve({ servers: [] })
        ]);
        state.runtimeAdapters = state.runtimeAdapters.filter(function(adapter) { return adapter.adapter_id !== runtime.adapter.adapter_id; });
        state.runtimeAdapters.unshift(runtime.adapter);
        state.slashCommands = commands.commands || [];
        state.mcpServers = machineMcp.servers || [];
        renderRuntimeAdapters();
        renderSlashCommands();
        renderMcpSummary();
      } catch (error) {
        flash("Launch context refresh failed: " + error.message, "bad");
      }
    }
    async function refreshAll() {
      try {
        const results = await Promise.all([
          api("/machines/self"),
          api("/agents"),
          api("/agents/running"),
          api("/tasks?limit=30"),
          api("/audit?limit=30"),
          api("/launch-profiles"),
          api("/workspaces"),
          api("/runtime/adapters")
        ]);
        state.machineSelf = results[0];
        state.agents = results[1].agents || [];
        state.running = results[2].agents || [];
        state.tasks = results[3].tasks || [];
        state.audit = results[4].entries || [];
        state.profiles = results[5].profiles || [];
        state.workspaces = results[6].workspaces || [];
        state.runtimeAdapters = results[7].adapters || [];
        const machineId = state.machineSelf && state.machineSelf.machine ? state.machineSelf.machine.id : null;
        state.machineHealth = machineId ? await api("/machines/" + encodeURIComponent(machineId) + "/health") : null;
        renderMachine();
        renderProfiles();
        renderWorkspaces();
        if (!state.selectedAgentId && state.running.length) state.selectedAgentId = state.running[0].agent_id;
        if (!state.selectedAgentId && state.agents.length) state.selectedAgentId = state.agents[0].id;
        renderRuntimeAdapters();
        renderRunningAgents();
        renderTasks();
        renderAudit();
        await refreshLaunchContext();
        renderSelectedAgent();
        connectWs();
      } catch (error) {
        flash("Refresh failed: " + error.message, "bad");
      }
    }
    async function launchAgent() {
      try {
        const response = await api("/agents/launch", {
          method: "POST",
          body: JSON.stringify({
            type: el("launchType").value,
            launch_profile: el("launchProfile").value,
            workspace: selectedWorkspace(),
            initial_prompt: (el("initialPrompt").value || "").trim() || null,
            runtime_model: (el("runtimeModel").value || "").trim() || null,
            command_name: (el("slashCommand").value || "").trim() || null
          })
        });
        state.selectedAgentId = response.agent.id;
        flash("Agent launch accepted.", "ok");
        await refreshAll();
      } catch (error) {
        flash("Launch failed: " + error.message, "bad");
      }
    }
    async function sendPrompt() {
      if (!state.selectedAgentId) return flash("Select an agent first.", "bad");
      const prompt = (el("agentPrompt").value || "").trim();
      if (!prompt) return flash("Prompt is empty.", "bad");
      try {
        await api("/agents/" + encodeURIComponent(state.selectedAgentId) + "/prompt", {
          method: "POST",
          body: JSON.stringify({ prompt: prompt })
        });
        el("agentPrompt").value = "";
        flash("Prompt submitted.", "ok");
      } catch (error) {
        flash("Prompt failed: " + error.message, "bad");
      }
    }
    async function stopAgent() {
      if (!state.selectedAgentId) return flash("Select an agent first.", "bad");
      try {
        await api("/agents/" + encodeURIComponent(state.selectedAgentId) + "/stop", { method: "POST" });
        flash("Stop requested.", "ok");
        await refreshAll();
      } catch (error) {
        flash("Stop failed: " + error.message, "bad");
      }
    }
    async function restartAgent() {
      if (!state.selectedAgentId) return flash("Select an agent first.", "bad");
      try {
        await api("/agents/" + encodeURIComponent(state.selectedAgentId) + "/restart", {
          method: "POST",
          body: JSON.stringify({ reason: "Restarted from responsive web console" })
        });
        flash("Restart requested.", "ok");
        await refreshAll();
      } catch (error) {
        flash("Restart failed: " + error.message, "bad");
      }
    }
    function connectWs() {
      const config = getConfig();
      if (!config.baseUrl || !config.token) return;
      const protocol = config.baseUrl.indexOf("https://") === 0 ? "wss://" : "ws://";
      const wsBase = config.baseUrl.replace(/^https?:\\/\\//, "");
      if (state.ws) {
        state.ws.onclose = null;
        state.ws.onerror = null;
        state.ws.close();
      }
      updateStreamState("Connecting");
      const ws = new WebSocket(protocol + wsBase + "/ws?token=" + encodeURIComponent(config.token));
      state.ws = ws;
      ws.onopen = function() { updateStreamState("Live"); };
      ws.onmessage = function(message) {
        const event = JSON.parse(message.data);
        if (event.machine) {
          state.machineSelf = state.machineSelf || {};
          state.machineSelf.machine = event.machine;
        }
        if (event.machine_health) state.machineHealth = event.machine_health;
        if (event.agent) mergeAgent(event.agent);
        if (event.agent_status) mergeRunningStatus(event.agent_status);
        if (event.job) mergeTask(event.job);
        if (event.audit) mergeAudit(event.audit);
        renderMachine();
        renderRunningAgents();
        renderTasks();
        renderAudit();
        renderSelectedAgent();
      };
      ws.onerror = function() { try { ws.close(); } catch (error) {} };
      ws.onclose = function() {
        updateStreamState("Reconnecting");
        clearTimeout(state.reconnectTimer);
        state.reconnectTimer = setTimeout(function() { connectWs(); }, 1800);
      };
    }
    el("saveConfig").addEventListener("click", saveConfig);
    el("refreshAll").addEventListener("click", refreshAll);
    el("launchType").addEventListener("change", function() { renderProfiles(); refreshLaunchContext(); });
    el("launchProfile").addEventListener("change", refreshLaunchContext);
    el("workspace").addEventListener("change", refreshLaunchContext);
    el("refreshLaunchContext").addEventListener("click", refreshLaunchContext);
    el("launchAgent").addEventListener("click", launchAgent);
    el("sendPrompt").addEventListener("click", sendPrompt);
    el("stopAgent").addEventListener("click", stopAgent);
    el("restartAgent").addEventListener("click", restartAgent);
    loadConfig();
    refreshAll();
  </script>
</body>
</html>
"""


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_page() -> HTMLResponse:
    return HTMLResponse(ADMIN_HTML)
