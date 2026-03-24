from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["admin-ui"])


ADMIN_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Agent Control Admin</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #eef1f4;
      --panel: #ffffff;
      --ink: #16202a;
      --muted: #687785;
      --line: #d5dde5;
      --accent: #174d8c;
      --accent-soft: #deebfb;
      --ok: #dcefdc;
      --warn: #f6e4c6;
      --bad: #f4d7db;
      --shadow: 0 12px 30px rgba(18, 32, 52, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "Helvetica Neue", sans-serif;
      background: linear-gradient(180deg, #f7f9fb 0%, var(--bg) 100%);
      color: var(--ink);
    }
    header {
      padding: 24px 28px 18px;
      border-bottom: 1px solid var(--line);
      background: rgba(255,255,255,0.86);
      backdrop-filter: blur(10px);
      position: sticky;
      top: 0;
      z-index: 10;
    }
    h1 { margin: 0; font-size: 28px; }
    .subtitle { margin-top: 6px; color: var(--muted); }
    .shell {
      max-width: 1400px;
      margin: 0 auto;
      padding: 24px;
    }
    .toolbar, .grid {
      display: grid;
      gap: 16px;
    }
    .toolbar { grid-template-columns: 1.3fr 1fr auto auto; margin-bottom: 16px; align-items: end; }
    .grid { grid-template-columns: 1.2fr 1fr 1fr; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: var(--shadow);
      padding: 18px;
      min-width: 0;
    }
    .span-2 { grid-column: span 2; }
    .span-3 { grid-column: span 3; }
    label { display: block; margin-bottom: 6px; font-size: 13px; color: var(--muted); }
    input, textarea, select, button {
      width: 100%;
      border-radius: 12px;
      border: 1px solid var(--line);
      padding: 12px 14px;
      font: inherit;
      background: #fff;
    }
    textarea { min-height: 84px; resize: vertical; }
    button {
      cursor: pointer;
      font-weight: 600;
      background: var(--accent);
      color: white;
      border-color: var(--accent);
    }
    button.secondary {
      background: white;
      color: var(--accent);
    }
    button.inline {
      width: auto;
      padding: 8px 12px;
      font-size: 13px;
    }
    .section-title {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }
    .section-title h2 {
      margin: 0;
      font-size: 18px;
    }
    .kpis {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }
    .kpi {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      background: #fbfcfd;
    }
    .kpi .label { color: var(--muted); font-size: 13px; }
    .kpi .value { margin-top: 8px; font-size: 24px; font-weight: 700; }
    .badge {
      display: inline-flex;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      border: 1px solid transparent;
    }
    .status-online, .status-idle, .status-completed { background: var(--ok); }
    .status-running, .status-starting { background: var(--warn); }
    .status-failed, .status-stopped, .status-offline { background: var(--bad); }
    .list {
      display: grid;
      gap: 12px;
      max-height: 580px;
      overflow: auto;
      padding-right: 4px;
    }
    .card {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      background: #fff;
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
      margin-bottom: 10px;
    }
    .muted { color: var(--muted); font-size: 13px; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; word-break: break-all; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
    .log-view {
      background: #10161d;
      color: #dbe7f3;
      border-radius: 14px;
      padding: 14px;
      min-height: 340px;
      max-height: 560px;
      overflow: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      white-space: pre-wrap;
    }
    .flash {
      margin-top: 12px;
      padding: 12px 14px;
      border-radius: 12px;
      font-size: 14px;
      display: none;
    }
    .flash.show { display: block; }
    .flash.ok { background: var(--ok); }
    .flash.bad { background: var(--bad); }
    .cols-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    @media (max-width: 1100px) {
      .grid { grid-template-columns: 1fr; }
      .span-2, .span-3 { grid-column: span 1; }
      .toolbar, .kpis, .cols-2 { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Supervisor Admin</h1>
    <div class="subtitle">Local machine console for agents, tasks, audit, and launch control.</div>
  </header>
  <div class="shell">
    <div class="toolbar">
      <div>
        <label for="baseUrl">Supervisor Base URL</label>
        <input id="baseUrl" value="" placeholder="http://127.0.0.1:8000" />
      </div>
      <div>
        <label for="token">Bearer Token</label>
        <input id="token" value="" placeholder="0118" />
      </div>
      <button class="secondary" id="saveConfig">Save</button>
      <button id="refreshAll">Refresh</button>
    </div>
    <div id="flash" class="flash"></div>
    <div class="grid">
      <section class="panel span-3">
        <div class="section-title"><h2>Machine</h2><span id="streamState" class="badge status-offline">Disconnected</span></div>
        <div class="kpis" id="machineKpis"></div>
      </section>

      <section class="panel">
        <div class="section-title"><h2>Launch Agent</h2></div>
        <div class="cols-2">
          <div>
            <label for="launchType">Agent Type</label>
            <select id="launchType"></select>
          </div>
          <div>
            <label for="launchProfile">Launch Profile</label>
            <select id="launchProfile"></select>
          </div>
        </div>
        <div style="margin-top:12px">
          <label for="workspace">Workspace</label>
          <input id="workspace" value="C:\\Users\\ManishKL\\Documents\\Playground" />
        </div>
        <div style="margin-top:12px">
          <label for="initialPrompt">Initial Prompt</label>
          <textarea id="initialPrompt" placeholder="Optional initial task or prompt"></textarea>
        </div>
        <div class="actions">
          <button class="inline" id="launchAgent">Launch Agent</button>
        </div>
      </section>

      <section class="panel">
        <div class="section-title"><h2>Selected Agent</h2></div>
        <div id="selectedAgentMeta" class="muted">No agent selected.</div>
        <div style="margin-top:12px">
          <label for="agentPrompt">Send Prompt</label>
          <textarea id="agentPrompt" placeholder="Send work to selected agent"></textarea>
        </div>
        <div class="actions">
          <button class="inline" id="sendPrompt">Send Prompt</button>
          <button class="inline secondary" id="restartAgent">Restart</button>
          <button class="inline secondary" id="stopAgent">Stop</button>
        </div>
      </section>

      <section class="panel">
        <div class="section-title"><h2>Recent Result</h2></div>
        <div id="latestResult" class="muted">No completed task selected.</div>
      </section>

      <section class="panel">
        <div class="section-title"><h2>Agents</h2></div>
        <div id="agentsList" class="list"></div>
      </section>

      <section class="panel">
        <div class="section-title"><h2>Tasks</h2></div>
        <div id="tasksList" class="list"></div>
      </section>

      <section class="panel">
        <div class="section-title"><h2>Audit</h2></div>
        <div id="auditList" class="list"></div>
      </section>

      <section class="panel span-3">
        <div class="section-title"><h2>Logs</h2></div>
        <div id="logView" class="log-view">Select an agent to view logs.</div>
      </section>
    </div>
  </div>

  <script>
    const state = {
      machine: null,
      agents: [],
      tasks: [],
      audit: [],
      profiles: [],
      selectedAgentId: null,
      ws: null,
      reconnectTimer: null
    };

    const el = (id) => document.getElementById(id);

    function getConfig() {
      return {
        baseUrl: el("baseUrl").value.trim().replace(/\\/$/, ""),
        token: el("token").value.trim()
      };
    }

    function saveConfig() {
      localStorage.setItem("admin.baseUrl", el("baseUrl").value.trim());
      localStorage.setItem("admin.token", el("token").value.trim());
      flash("Saved local admin config.", "ok");
    }

    function loadConfig() {
      el("baseUrl").value = localStorage.getItem("admin.baseUrl") || window.location.origin;
      el("token").value = localStorage.getItem("admin.token") || "0118";
    }

    function flash(message, kind) {
      const node = el("flash");
      node.textContent = message;
      node.className = `flash show ${kind}`;
      clearTimeout(node._timer);
      node._timer = setTimeout(() => node.className = "flash", 3200);
    }

    function badgeClass(value) {
      const normalized = (value || "unknown").toLowerCase();
      return `badge status-${normalized}`;
    }

    async function api(path, options = {}) {
      const { baseUrl, token } = getConfig();
      const response = await fetch(baseUrl + path, {
        ...options,
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json",
          ...(options.headers || {})
        }
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `${response.status} ${response.statusText}`);
      }
      return response.json();
    }

    function renderMachine() {
      if (!state.machine) return;
      const machine = state.machine.machine;
      el("machineKpis").innerHTML = `
        <div class="kpi"><div class="label">Machine</div><div class="value">${machine.name}</div><div class="muted mono">${machine.id}</div></div>
        <div class="kpi"><div class="label">Status</div><div class="value"><span class="${badgeClass(machine.status)}">${machine.status}</span></div><div class="muted">Updated ${machine.updated_at || machine.updatedAt || ""}</div></div>
        <div class="kpi"><div class="label">Workers</div><div class="value">${machine.worker_pool.busy_workers}/${machine.worker_pool.desired_workers}</div><div class="muted">Queue ${machine.worker_pool.queue_depth}</div></div>
        <div class="kpi"><div class="label">Agents</div><div class="value">${state.machine.active_agents}</div><div class="muted">Queued jobs ${state.machine.queued_jobs}</div></div>
      `;
    }

    function latestTaskForAgent(agentId) {
      return state.tasks.find((task) => task.agent_id === agentId);
    }

    function renderAgents() {
      const selected = state.selectedAgentId;
      el("agentsList").innerHTML = state.agents.map((agent) => {
        const active = agent.id === selected ? " style='border-color: var(--accent); background: var(--accent-soft)'" : "";
        return `
          <div class="card"${active} data-agent="${agent.id}">
            <div class="card-header">
              <div>
                <div><strong>${agent.type.toUpperCase()}</strong></div>
                <div class="muted mono">${agent.id}</div>
              </div>
              <span class="${badgeClass(agent.state)}">${agent.state}</span>
            </div>
            <div class="muted">PID ${agent.pid ?? "-"}</div>
            <div class="muted mono">${agent.workspace ?? "-"}</div>
            <div class="muted">Profile ${agent.launch_profile ?? "-"}</div>
          </div>
        `;
      }).join("") || "<div class='muted'>No agents.</div>";
      document.querySelectorAll("[data-agent]").forEach((node) => {
        node.addEventListener("click", () => selectAgent(node.dataset.agent));
      });
    }

    function renderTasks() {
      el("tasksList").innerHTML = state.tasks.map((task) => `
        <div class="card">
          <div class="card-header">
            <div><strong>${task.kind}</strong><div class="muted mono">${task.id}</div></div>
            <span class="${badgeClass(task.state)}">${task.state}</span>
          </div>
          <div>${escapeHtml(task.input_text || "")}</div>
          <div class="muted" style="margin-top:8px">${escapeHtml(task.summary || task.error || "")}</div>
        </div>
      `).join("") || "<div class='muted'>No tasks.</div>";
    }

    function renderAudit() {
      el("auditList").innerHTML = state.audit.map((entry) => `
        <div class="card">
          <div class="card-header">
            <div><strong>${escapeHtml(entry.action)}</strong><div class="muted mono">${escapeHtml(entry.target_id)}</div></div>
            <span class="${badgeClass(entry.status)}">${escapeHtml(entry.status)}</span>
          </div>
          <div>${escapeHtml(entry.message || "")}</div>
          <div class="muted" style="margin-top:8px">${escapeHtml(entry.timestamp || "")}</div>
        </div>
      `).join("") || "<div class='muted'>No audit entries.</div>";
    }

    function renderProfiles() {
      const type = el("launchType").value || "codex";
      const types = [...new Set(state.profiles.map((profile) => profile.agent_type))];
      el("launchType").innerHTML = types.map((item) => `<option value="${item}" ${item === type ? "selected" : ""}>${item.toUpperCase()}</option>`).join("");
      const currentType = el("launchType").value || type;
      const profiles = state.profiles.filter((profile) => profile.agent_type === currentType);
      el("launchProfile").innerHTML = profiles.map((profile) => `<option value="${profile.id}">${escapeHtml(profile.label)}</option>`).join("");
    }

    function renderSelectedAgent() {
      const agent = state.agents.find((item) => item.id === state.selectedAgentId);
      if (!agent) {
        el("selectedAgentMeta").innerHTML = "<div class='muted'>No agent selected.</div>";
        el("logView").textContent = "Select an agent to view logs.";
        el("latestResult").innerHTML = "<div class='muted'>No completed task selected.</div>";
        return;
      }
      const task = latestTaskForAgent(agent.id);
      el("selectedAgentMeta").innerHTML = `
        <div><strong>${agent.type.toUpperCase()}</strong> <span class="${badgeClass(agent.state)}">${agent.state}</span></div>
        <div class="muted mono" style="margin-top:8px">${agent.id}</div>
        <div class="muted" style="margin-top:8px">PID ${agent.pid ?? "-"} · Worker ${agent.worker_id ?? "-"}</div>
        <div class="muted mono" style="margin-top:6px">${agent.workspace ?? "-"}</div>
      `;
      el("logView").textContent = (agent.recent_logs || []).map((log) => `[${log.timestamp}] ${log.stream}: ${log.message}`).join("\\n") || "No logs.";
      const latestResult = task && task.state === "completed" ? (task.summary || "Completed.") : "No completed task selected.";
      el("latestResult").innerHTML = `<div>${escapeHtml(latestResult)}</div>`;
    }

    function escapeHtml(value) {
      return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }

    function mergeAgent(agent) {
      const existing = state.agents.findIndex((item) => item.id === agent.id);
      if (existing >= 0) state.agents[existing] = agent;
      else state.agents.unshift(agent);
    }

    function mergeTask(task) {
      const existing = state.tasks.findIndex((item) => item.id === task.id);
      if (existing >= 0) state.tasks[existing] = task;
      else state.tasks.unshift(task);
      state.tasks.sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));
    }

    function mergeAudit(entry) {
      const existing = state.audit.findIndex((item) => item.id === entry.id);
      if (existing >= 0) state.audit[existing] = entry;
      else state.audit.unshift(entry);
    }

    function selectAgent(agentId) {
      state.selectedAgentId = agentId;
      renderAgents();
      renderSelectedAgent();
    }

    async function refreshAll() {
      try {
        const [machine, agents, tasks, audit, profiles] = await Promise.all([
          api("/machines/self"),
          api("/agents"),
          api("/tasks?limit=25"),
          api("/audit?limit=25"),
          api("/launch-profiles")
        ]);
        state.machine = machine;
        state.agents = agents.agents || [];
        state.tasks = tasks.tasks || [];
        state.audit = audit.entries || [];
        state.profiles = profiles.profiles || [];
        if (!state.selectedAgentId && state.agents.length) state.selectedAgentId = state.agents[0].id;
        renderMachine();
        renderProfiles();
        renderAgents();
        renderTasks();
        renderAudit();
        renderSelectedAgent();
        connectWs();
      } catch (error) {
        flash(`Refresh failed: ${error.message}`, "bad");
      }
    }

    async function launchAgent() {
      try {
        const response = await api("/agents/launch", {
          method: "POST",
          body: JSON.stringify({
            type: el("launchType").value,
            launch_profile: el("launchProfile").value,
            workspace: el("workspace").value.trim(),
            initial_prompt: el("initialPrompt").value.trim() || null
          })
        });
        state.selectedAgentId = response.agent.id;
        flash("Agent launch accepted.", "ok");
        await refreshAll();
      } catch (error) {
        flash(`Launch failed: ${error.message}`, "bad");
      }
    }

    async function sendPrompt() {
      if (!state.selectedAgentId) {
        flash("Select an agent first.", "bad");
        return;
      }
      try {
        await api(`/agents/${state.selectedAgentId}/prompt`, {
          method: "POST",
          body: JSON.stringify({ prompt: el("agentPrompt").value.trim() })
        });
        el("agentPrompt").value = "";
        flash("Prompt submitted.", "ok");
      } catch (error) {
        flash(`Prompt failed: ${error.message}`, "bad");
      }
    }

    async function stopAgent() {
      if (!state.selectedAgentId) return flash("Select an agent first.", "bad");
      try {
        await api(`/agents/${state.selectedAgentId}/stop`, { method: "POST" });
        flash("Stop requested.", "ok");
        await refreshAll();
      } catch (error) {
        flash(`Stop failed: ${error.message}`, "bad");
      }
    }

    async function restartAgent() {
      if (!state.selectedAgentId) return flash("Select an agent first.", "bad");
      try {
        await api(`/agents/${state.selectedAgentId}/restart`, {
          method: "POST",
          body: JSON.stringify({ reason: "Restarted from local admin UI" })
        });
        flash("Restart requested.", "ok");
        await refreshAll();
      } catch (error) {
        flash(`Restart failed: ${error.message}`, "bad");
      }
    }

    function connectWs() {
      const { baseUrl, token } = getConfig();
      if (!baseUrl || !token) return;
      const wsBase = baseUrl.replace(/^http/, "ws").replace(/\\/$/, "");
      if (state.ws) state.ws.close();
      const ws = new WebSocket(`${wsBase}/ws?token=${encodeURIComponent(token)}`);
      state.ws = ws;
      el("streamState").textContent = "Connecting";
      el("streamState").className = "badge status-starting";
      ws.onopen = () => {
        el("streamState").textContent = "Live";
        el("streamState").className = "badge status-online";
      };
      ws.onmessage = (message) => {
        const event = JSON.parse(message.data);
        if (event.machine) state.machine = { ...(state.machine || {}), machine: event.machine, active_agents: state.machine?.active_agents ?? 0, queued_jobs: state.machine?.queued_jobs ?? 0 };
        if (event.agent) mergeAgent(event.agent);
        if (event.job) mergeTask(event.job);
        if (event.audit) mergeAudit(event.audit);
        renderMachine();
        renderAgents();
        renderTasks();
        renderAudit();
        renderSelectedAgent();
      };
      ws.onclose = () => {
        el("streamState").textContent = "Reconnecting";
        el("streamState").className = "badge status-starting";
        clearTimeout(state.reconnectTimer);
        state.reconnectTimer = setTimeout(connectWs, 1600);
      };
      ws.onerror = () => ws.close();
    }

    el("saveConfig").addEventListener("click", saveConfig);
    el("refreshAll").addEventListener("click", refreshAll);
    el("launchType").addEventListener("change", renderProfiles);
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
