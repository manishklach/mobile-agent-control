from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["admin-ui"])


ADMIN_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>Mobile Agent Control</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f8fafc;
      --panel: #ffffff;
      --panel-alt: #f1f5f9;
      --ink: #0f172a;
      --muted: #64748b;
      --line: #e2e8f0;
      --brand: #2563eb;
      --brand-soft: #eff6ff;
      --good: #dcfce7;
      --good-ink: #166534;
      --warn: #fef9c3;
      --warn-ink: #854d0e;
      --bad: #fee2e2;
      --bad-ink: #991b1b;
      --shadow: 0 1px 3px rgba(0,0,0,0.1);
      --radius: 12px;
      --radius-sm: 8px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.5;
      font-size: 14px;
    }
    .app { max-width: 1400px; margin: 0 auto; padding: 20px; }
    
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding: 12px 0;
      border-bottom: 1px solid var(--line);
    }
    .brand h1 { margin: 0; font-size: 20px; font-weight: 800; color: var(--brand); letter-spacing: -0.02em; }
    .brand p { margin: 2px 0 0; font-size: 12px; color: var(--muted); }
    
    .dashboard-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-bottom: 24px;
    }
    .kpi {
      background: var(--panel);
      padding: 12px 16px;
      border-radius: var(--radius);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
    }
    .kpi-label { font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
    .kpi-value { font-size: 18px; font-weight: 700; margin-top: 4px; }
    .kpi-meta { font-size: 11px; color: var(--muted); margin-top: 4px; }
    
    .main-grid {
      display: grid;
      grid-template-columns: 380px 1fr;
      gap: 24px;
    }
    
    .surface {
      background: var(--panel);
      border-radius: var(--radius);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      margin-bottom: 20px;
      overflow: hidden;
    }
    .section-header {
      padding: 12px 16px;
      border-bottom: 1px solid var(--line);
      background: var(--panel-alt);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .section-header h2 { margin: 0; font-size: 14px; font-weight: 700; }
    .section-body { padding: 16px; }
    
    .tabs {
      display: flex;
      background: var(--panel-alt);
      padding: 4px;
      gap: 4px;
      border-bottom: 1px solid var(--line);
    }
    .tab {
      flex: 1;
      padding: 6px;
      font-size: 12px;
      font-weight: 600;
      color: var(--muted);
      cursor: pointer;
      text-align: center;
      border-radius: 6px;
    }
    .tab.active { background: var(--panel); color: var(--brand); box-shadow: var(--shadow); }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    
    .input-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
    .input-group { margin-bottom: 12px; }
    label { display: block; font-size: 11px; font-weight: 700; color: var(--muted); margin-bottom: 4px; text-transform: uppercase; }
    input, select, textarea {
      width: 100%;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      font-size: 13px;
      background: white;
    }
    textarea { font-family: inherit; resize: vertical; }
    
    button {
      padding: 8px 16px;
      border-radius: 6px;
      font-weight: 700;
      font-size: 13px;
      cursor: pointer;
      border: 1px solid var(--brand);
      background: var(--brand);
      color: white;
    }
    button.secondary { background: white; color: var(--brand); border-color: var(--line); }
    button.danger { border-color: #ef4444; color: #ef4444; background: white; }
    
    .agent-card {
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      margin-bottom: 8px;
      cursor: pointer;
    }
    .agent-card.selected { border-color: var(--brand); background: var(--brand-soft); }
    .agent-card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px; }
    .agent-name { font-weight: 700; font-size: 13px; }
    
    .chip {
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
    }
    .status-online, .status-idle, .status-completed, .status-healthy { background: var(--good); color: var(--good-ink); }
    .status-running, .status-starting, .status-pending { background: var(--warn); color: var(--warn-ink); }
    .status-failed, .status-stopped, .status-offline { background: var(--bad); color: var(--bad-ink); }
    
    .log-view {
      background: #0f172a;
      color: #e2e8f0;
      padding: 12px;
      border-radius: 6px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 11px;
      height: 400px;
      overflow-y: auto;
      white-space: pre-wrap;
      line-height: 1.4;
    }
    
    .config-panel {
      display: none;
      background: var(--panel);
      padding: 16px;
      border-radius: var(--radius);
      border: 1px solid var(--line);
      margin-bottom: 24px;
      grid-template-columns: 1fr 1fr auto auto auto;
      gap: 12px;
      align-items: flex-end;
    }
    .config-panel.active { display: grid; }
    
    .flash {
      display: none;
      padding: 10px 16px;
      border-radius: var(--radius);
      margin-bottom: 20px;
      font-weight: 600;
      font-size: 13px;
    }
    .flash.show { display: block; }
    .flash.ok { background: var(--good); color: var(--good-ink); }
    .flash.bad { background: var(--bad); color: var(--bad-ink); }

    .scroll { max-height: 400px; overflow-y: auto; }
    .empty { padding: 20px; text-align: center; color: var(--muted); font-size: 13px; }

    @media (max-width: 1000px) {
      .main-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div class="brand">
        <h1>Mobile Agent Control</h1>
        <p id="streamStateHeader">Supervisor Monitoring</p>
      </div>
      <div style="display:flex; gap:8px">
        <button class="secondary" id="toggleConfigBtn">Settings</button>
        <button id="refreshAllBtn">Refresh</button>
      </div>
    </header>

    <div id="configPanel" class="config-panel">
      <div class="input-group" style="margin-bottom:0">
        <label>Base URL</label>
        <input id="baseUrl" placeholder="http://localhost:8000">
      </div>
      <div class="input-group" style="margin-bottom:0">
        <label>Token</label>
        <input id="token" type="password" placeholder="Bearer Token">
      </div>
      <button class="secondary" id="saveConfigBtn">Save</button>
      <button class="secondary" id="resetConfigBtn">Reset</button>
      <button class="danger" id="restartSupervisorBtn">Restart Supervisor</button>
    </div>

    <div id="flash" class="flash"></div>

    <div id="machineKpis" class="dashboard-grid"></div>

    <div class="main-grid">
      <div class="stack">
        <section class="surface">
          <div class="section-header"><h2>Launch Agent</h2></div>
          <div class="section-body">
            <div class="input-row">
              <div class="input-group">
                <label>Runtime</label>
                <select id="launchType"></select>
              </div>
              <div class="input-group">
                <label>Profile</label>
                <select id="launchProfile"></select>
              </div>
            </div>
            <div class="input-group">
              <label>Workspace</label>
              <select id="workspace"></select>
            </div>
            <div class="input-row">
              <div class="input-group">
                <label>Command</label>
                <select id="slashCommand"></select>
              </div>
              <div class="input-group">
                <label>Model</label>
                <input id="runtimeModel" placeholder="default">
              </div>
            </div>
            <div class="input-group">
              <label>Initial Prompt</label>
              <textarea id="initialPrompt" rows="2" placeholder="Task for the agent..."></textarea>
            </div>
            <button style="width:100%" id="launchAgentBtn">Launch Agent</button>
          </div>
        </section>

        <section class="surface">
          <div class="section-header">
            <h2>Active Agents</h2>
            <button class="secondary" style="padding:4px 8px; font-size:11px" id="clearTerminatedBtn">Clear Terminated</button>
          </div>
          <div class="section-body scroll" id="runningAgentsList"></div>
        </section>
      </div>

      <div class="stack">
        <section class="surface">
          <div class="section-header">
            <div id="selectedAgentTitle"><h2>No Agent Selected</h2></div>
            <div id="agentActions" style="display:none; gap:8px">
              <button class="secondary" id="restartAgentBtn">Restart</button>
              <button class="danger" id="stopAgentBtn">Stop</button>
            </div>
          </div>
          
          <div class="tabs" id="agentTabs">
            <div class="tab active" data-tab="logs">Logs</div>
            <div class="tab" data-tab="prompt">Prompt</div>
            <div class="tab" data-tab="info">Details</div>
          </div>

          <div id="tab-logs" class="tab-content active" style="padding:0">
            <div id="logView" class="log-view" style="border-radius:0">Select an agent to see logs.</div>
          </div>
          <div id="tab-prompt" class="tab-content" style="padding:16px">
            <textarea id="agentPrompt" rows="8" placeholder="Type a message to the agent..."></textarea>
            <button style="width:100%; margin-top:12px" id="sendPromptBtn">Send Message</button>
          </div>
          <div id="tab-info" class="tab-content" style="padding:16px">
            <div id="selectedAgentMeta"></div>
            <div id="latestResult" style="margin-top:16px"></div>
            <div id="mcpSummary" style="margin-top:16px"></div>
          </div>
        </section>

        <section class="surface">
          <div class="tabs" id="bottomTabs">
            <div class="tab active" data-tab="tasks">Tasks</div>
            <div class="tab" data-tab="audit">Audit</div>
            <div class="tab" data-tab="runtime">Runtime</div>
          </div>
          
          <div id="btab-tasks" class="tab-content active" style="padding:16px">
            <div id="tasksList" class="list scroll"></div>
          </div>
          <div id="btab-audit" class="tab-content" style="padding:16px">
            <div id="auditList" class="list scroll"></div>
          </div>
          <div id="btab-runtime" class="tab-content" style="padding:16px">
            <div id="runtimeList" class="list" style="margin-bottom:16px"></div>
            <div id="slashCommandsList" class="list scroll"></div>
          </div>
        </section>
      </div>
    </div>
  </div>

  <script>
    (function() {
      const state = {
        machineSelf: null, machineHealth: null,
        agents: [], running: [], tasks: [], audit: [],
        profiles: [], workspaces: [], runtimeAdapters: [],
        slashCommands: [], mcpServers: [],
        selectedAgentId: null, ws: null, reconnectTimer: null
      };

      function el(id) { return document.getElementById(id); }
      
      function toggleConfig() { 
        const panel = el('configPanel');
        if (panel.classList.contains('active')) panel.classList.remove('active');
        else panel.classList.add('active');
      }
      
      function showTab(containerId, tabId, prefix) {
        const container = el(containerId);
        if (!container) return;
        const tabs = container.querySelectorAll('.tab');
        const contents = container.closest('.surface').querySelectorAll('.tab-content');
        
        for (let i = 0; i < tabs.length; i++) {
          if (tabs[i].dataset.tab === tabId) tabs[i].classList.add('active');
          else tabs[i].classList.remove('active');
        }
        
        for (let i = 0; i < contents.length; i++) {
          if (contents[i].id === prefix + tabId) contents[i].classList.add('active');
          else contents[i].classList.remove('active');
        }
      }

      function getConfig() {
        const urlInput = el("baseUrl");
        let url = (urlInput ? urlInput.value : "") || "";
        if (url.indexOf("://") > 0) {
           const parts = url.split("://");
           url = parts[0] + "://" + parts[1].split("/")[0];
        } else {
           url = url.split("/")[0];
        }
        return {
          baseUrl: url,
          token: el("token").value || ""
        };
      }
      
      function saveConfig() {
        localStorage.setItem("admin.baseUrl", el("baseUrl").value.trim());
        localStorage.setItem("admin.token", el("token").value.trim());
        flash("Saved local web console config.", "ok");
        toggleConfig();
        refreshAll();
      }
      
      function loadConfig() {
        el("baseUrl").value = localStorage.getItem("admin.baseUrl") || window.location.origin;
        el("token").value = localStorage.getItem("admin.token") || "0118";
      }
      
      function flash(message, kind) {
        const node = el("flash");
        node.textContent = message;
        node.className = "flash show " + kind;
        if (node._timer) clearTimeout(node._timer);
        node._timer = setTimeout(function() { node.className = "flash"; }, 3600);
      }
      
      function escapeHtml(value) {
        if (!value) return "";
        return String(value)
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;");
      }
      
      function statusClass(value) {
        return "chip status-" + String(value || "unknown").toLowerCase();
      }
      
      function api(path, options) {
        const config = getConfig();
        const headers = {
          "Authorization": "Bearer " + config.token,
          "Content-Type": "application/json"
        };
        return fetch(config.baseUrl + path, {
          method: (options && options.method) || "GET",
          headers: headers,
          body: options && options.body ? options.body : undefined
        }).then(function(response) {
          if (!response.ok) {
            return response.text().then(function(text) {
              throw new Error(text || (response.status + " " + response.statusText));
            });
          }
          return response.json();
        });
      }
      
      function selectedWorkspace() { return el("workspace").value || ""; }
      
      function selectedRuntimeAdapterId() {
        const profileId = el("launchProfile").value;
        const profile = state.profiles.find(function(p) { return p.id === profileId; });
        return profile ? profile.adapter_id : "gemini-cli";
      }
      
      function updateStreamState(label) {
        el("streamStateHeader").textContent = label;
      }
      
      function formatDuration(seconds) {
        if (seconds == null) return "-";
        const total = Number(seconds);
        const hours = Math.floor(total / 3600);
        const minutes = Math.floor((total % 3600) / 60);
        const remainder = Math.floor(total % 60);
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
      
      function renderMachine() {
        const self = state.machineSelf;
        const health = state.machineHealth;
        if (!self || !self.machine) {
          el("machineKpis").innerHTML = "<div class='empty'>Machine data not loaded.</div>";
          return;
        }
        const machine = self.machine;
        const heartbeat = health ? health.last_heartbeat : machine.updated_at;
        el("machineKpis").innerHTML = [
          "<div class='kpi'><div class='kpi-label'>Machine</div><div class='kpi-value'>" + escapeHtml(machine.name) + "</div><div class='kpi-meta mono'>" + escapeHtml(machine.id) + "</div></div>",
          "<div class='kpi'><div class='kpi-label'>Status</div><div class='kpi-value'><span class='" + statusClass(health ? health.monitor_state : machine.status) + "'>" + escapeHtml(health ? health.monitor_state : machine.status) + "</span></div><div class='kpi-meta'>Heartbeat " + escapeHtml(heartbeat || "-") + "</div></div>",
          "<div class='kpi'><div class='kpi-label'>Workers</div><div class='kpi-value'>" + machine.worker_pool.busy_workers + "/" + machine.worker_pool.desired_workers + "</div><div class='kpi-meta'>Queue " + machine.worker_pool.queue_depth + "</div></div>",
          "<div class='kpi'><div class='kpi-label'>Active Agents</div><div class='kpi-value'>" + self.active_agents + "</div><div class='kpi-meta'>of " + self.max_active_agents + " max</div></div>"
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
      }
      
      function renderWorkspaces() {
        el("workspace").innerHTML = state.workspaces.map(function(workspace) {
          return "<option value='" + escapeHtml(workspace.path) + "'>" + escapeHtml(workspace.label) + "</option>";
        }).join("");
      }
      
      function renderRuntimeAdapters() {
        const node = el("runtimeList");
        if (!state.runtimeAdapters.length) { node.innerHTML = "<div class='empty'>No adapters reported.</div>"; return; }
        node.innerHTML = state.runtimeAdapters.map(function(adapter) {
          const status = adapter.status || {};
          return [
            "<div class='card' style='padding:8px; margin-bottom:8px; border:1px solid var(--line); border-radius:6px'>",
            "<div style='display:flex; justify-content:space-between'><strong>" + escapeHtml(adapter.label) + "</strong><span class='" + statusClass(status.auth && status.auth.available ? "healthy" : "warning") + "'>" + escapeHtml(status.version || "??") + "</span></div>",
            "<div class='tiny mono' style='font-size:10px; color:var(--muted)'>" + escapeHtml(status.binary_path || "-") + "</div>",
            "</div>"
          ].join("");
        }).join("");
      }
      
      function renderSlashCommands() {
        const node = el("slashCommandsList");
        const select = el("slashCommand");
        if (!state.slashCommands.length) {
          select.innerHTML = "<option value=''>No slash command</option>";
          node.innerHTML = "<div class='empty'>No commands in this workspace.</div>";
          return;
        }
        select.innerHTML = "<option value=''>None</option>" + state.slashCommands.map(function(command) {
          return "<option value='" + escapeHtml(command.name) + "'>/" + escapeHtml(command.name) + "</option>";
        }).join("");
        node.innerHTML = state.slashCommands.map(function(command) {
          return [
            "<div class='card' style='padding:8px; margin-bottom:8px; border:1px solid var(--line); border-radius:6px'>",
            "<strong>/" + escapeHtml(command.name) + "</strong> <span class='chip'>" + escapeHtml(command.scope) + "</span>",
            "<div style='font-size:11px; margin-top:2px'>" + escapeHtml(command.description || "") + "</div>",
            "</div>"
          ].join("");
        }).join("");
      }
      
      function renderMcpSummary() {
        const servers = state.mcpServers || [];
        if (!servers.length) { el("mcpSummary").innerHTML = "No MCP servers configured."; return; }
        el("mcpSummary").innerHTML = "<label>MCP Servers</label>" + servers.map(function(server) {
          return "<div class='card' style='padding:6px; margin-bottom:4px; font-size:11px; border:1px solid var(--line); border-radius:6px'>" + escapeHtml(server.name) + " <span class='" + statusClass(server.health) + "'>" + escapeHtml(server.health) + "</span></div>";
        }).join("");
      }
      
      function renderRunningAgents() {
        const node = el("runningAgentsList");
        if (!state.running.length) { node.innerHTML = "<div class='empty'>No active agents.</div>"; return; }
        node.innerHTML = state.running.map(function(agent) {
          const selected = state.selectedAgentId === agent.agent_id ? " selected" : "";
          return [
            "<div class='agent-card" + selected + "' data-aid='" + escapeHtml(agent.agent_id) + "'>",
            "<div class='agent-card-header'><span class='agent-name'>" + escapeHtml((agent.type || "").toUpperCase()) + "</span><span class='" + statusClass(agent.monitor_state || agent.state) + "'>" + escapeHtml(agent.monitor_state || agent.state) + "</span></div>",
            "<div style='font-size:11px; color:var(--muted)'>" + escapeHtml(agent.agent_id.substring(0,8)) + " · PID " + (agent.pid || "-") + " · " + formatDuration(agent.elapsed_seconds) + "</div>",
            "</div>"
          ].join("");
        }).join("");
        
        const cards = node.querySelectorAll('.agent-card');
        for (let i = 0; i < cards.length; i++) {
          cards[i].addEventListener('click', function() { selectAgent(this.dataset.aid); });
        }
      }
      
      function renderTasks() {
        const node = el("tasksList");
        if (!state.tasks.length) { node.innerHTML = "<div class='empty'>No task history.</div>"; return; }
        node.innerHTML = state.tasks.slice(0, 15).map(function(task) {
          return [
            "<div class='card' style='padding:8px; margin-bottom:8px; border:1px solid var(--line); border-radius:6px'>",
            "<div style='display:flex; justify-content:space-between'><strong>" + escapeHtml(task.kind) + "</strong><span class='" + statusClass(task.state) + "'>" + escapeHtml(task.state) + "</span></div>",
            "<div style='font-size:11px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap'>" + escapeHtml(task.input_text) + "</div>",
            "</div>"
          ].join("");
        }).join("");
      }
      
      function renderAudit() {
        const node = el("auditList");
        if (!state.audit.length) { node.innerHTML = "<div class='empty'>No audit logs.</div>"; return; }
        node.innerHTML = state.audit.slice(0, 15).map(function(entry) {
          return [
            "<div class='card' style='padding:8px; margin-bottom:8px; border:1px solid var(--line); border-radius:6px'>",
            "<strong>" + escapeHtml(entry.action) + "</strong>",
            "<div style='font-size:11px'>" + escapeHtml(entry.message) + "</div>",
            "</div>"
          ].join("");
        }).join("");
      }
      
      function renderSelectedAgent() {
        const agent = state.agents.find(function(item) { return item.id === state.selectedAgentId; }) || null;
        if (!agent) {
          el("selectedAgentTitle").innerHTML = "<h2>No Agent Selected</h2>";
          el("agentActions").style.display = "none";
          el("selectedAgentMeta").innerHTML = "";
          el("logView").textContent = "Select an agent to see logs.";
          return;
        }
        el("selectedAgentTitle").innerHTML = "<h2>" + escapeHtml(agent.type.toUpperCase()) + " Agent</h2>";
        el("agentActions").style.display = "flex";
        const recentLogs = agent.recent_logs || [];
        el("selectedAgentMeta").innerHTML = [
          "<div><strong>ID:</strong> " + escapeHtml(agent.id) + "</div>",
          "<div><strong>Workspace:</strong> " + escapeHtml(agent.workspace || "-") + "</div>",
          "<div><strong>Task:</strong> " + escapeHtml(agent.current_task || "-") + "</div>"
        ].join("");
        
        el("logView").textContent = recentLogs.length ? recentLogs.map(function(log) {
          const ts = String(log.timestamp || "");
          const timeStr = ts.indexOf('T') >= 0 ? ts.split('T')[1].split('.')[0] : ts;
          return "[" + timeStr + "] " + log.message;
        }).join("\n") : "No logs available.";
        
        const task = latestTaskForAgent(agent.id);
        el("latestResult").innerHTML = task ? "<strong>Last Result:</strong><br>" + escapeHtml(task.summary || task.error || "No summary yet.") : "";
      }
      
      function selectAgent(agentId) {
        state.selectedAgentId = agentId;
        renderRunningAgents();
        renderSelectedAgent();
      }
      
      async function refreshLaunchContext() {
        const adapterId = selectedRuntimeAdapterId();
        const workspace = selectedWorkspace();
        try {
          const [runtime, commands, machineMcp] = await Promise.all([
            api("/runtime/adapters/" + encodeURIComponent(adapterId) + (workspace ? ("?workspace=" + encodeURIComponent(workspace)) : "")),
            api("/runtime/adapters/" + encodeURIComponent(adapterId) + "/commands" + (workspace ? ("?workspace=" + encodeURIComponent(workspace)) : "")),
            state.machineSelf && state.machineSelf.machine ? api("/machines/" + encodeURIComponent(state.machineSelf.machine.id) + "/mcp" + (workspace ? ("?workspace=" + encodeURIComponent(workspace)) : "")) : Promise.resolve({ servers: [] })
          ]);
          state.runtimeAdapters = state.runtimeAdapters.filter(function(a) { return a.adapter_id !== runtime.adapter.adapter_id; });
          state.runtimeAdapters.unshift(runtime.adapter);
          state.slashCommands = commands.commands || [];
          state.mcpServers = machineMcp.servers || [];
          renderRuntimeAdapters();
          renderSlashCommands();
          renderMcpSummary();
        } catch (error) { flash("Context failed: " + error.message, "bad"); }
      }
      
      async function refreshAll() {
        try {
          const results = await Promise.all([
            api("/machines/self"), api("/agents"), api("/agents/running"),
            api("/tasks?limit=30"), api("/audit?limit=30"),
            api("/launch-profiles"), api("/workspaces"), api("/runtime/adapters")
          ]);
          state.machineSelf = results[0]; 
          state.agents = results[1].agents || [];
          state.running = results[2].agents || []; 
          state.tasks = results[3].tasks || [];
          state.audit = results[4].entries || []; 
          state.profiles = results[5].profiles || [];
          state.workspaces = results[6].workspaces || []; 
          state.runtimeAdapters = results[7].adapters || [];
          
          if (state.machineSelf && state.machineSelf.machine) {
            const mid = state.machineSelf.machine.id;
            state.machineHealth = await api("/machines/" + encodeURIComponent(mid) + "/health");
          }
          
          renderMachine(); 
          renderProfiles(); 
          renderWorkspaces();
          if (!state.selectedAgentId && state.running.length) state.selectedAgentId = state.running[0].agent_id;
          renderRunningAgents(); 
          renderTasks(); 
          renderAudit();
          await refreshLaunchContext(); 
          renderSelectedAgent();
          connectWs();
        } catch (error) { 
          console.error("Refresh all failed", error);
          flash("Refresh failed: " + error.message, "bad"); 
        }
      }
      
      async function launchAgent() {
        try {
          const res = await api("/agents/launch", {
            method: "POST",
            body: JSON.stringify({
              type: el("launchType").value, 
              launch_profile: el("launchProfile").value,
              workspace: selectedWorkspace(), 
              initial_prompt: el("initialPrompt").value,
              runtime_model: el("runtimeModel").value, 
              command_name: el("slashCommand").value
            })
          });
          state.selectedAgentId = res.agent.id; 
          flash("Agent launched.", "ok");
          await refreshAll();
        } catch (e) { flash("Launch failed: " + e.message, "bad"); }
      }
      
      async function sendPrompt() {
        if (!state.selectedAgentId) return;
        const prompt = el("agentPrompt").value;
        try {
          await api("/agents/" + encodeURIComponent(state.selectedAgentId) + "/prompt", {
            method: "POST", body: JSON.stringify({ prompt: prompt })
          });
          el("agentPrompt").value = ""; flash("Prompt sent.", "ok");
        } catch (e) { flash("Prompt failed: " + e.message, "bad"); }
      }
      
      async function stopAgent() {
        if (!state.selectedAgentId) return;
        try {
          await api("/agents/" + encodeURIComponent(state.selectedAgentId) + "/stop", { method: "POST" });
          flash("Stop requested.", "ok"); await refreshAll();
        } catch (e) { flash("Stop failed: " + e.message, "bad"); }
      }
      
      async function restartAgent() {
        if (!state.selectedAgentId) return;
        try {
          await api("/agents/" + encodeURIComponent(state.selectedAgentId) + "/restart", {
            method: "POST", body: JSON.stringify({ reason: "Manual restart" })
          });
          flash("Restart requested.", "ok"); await refreshAll();
        } catch (e) { flash("Restart failed: " + e.message, "bad"); }
      }
      
      async function restartSupervisor() {
        if (!confirm("Restart supervisor?")) return;
        try {
          await api("/machines/self/restart", { method: "POST", body: JSON.stringify({ reason: "Web UI" }) });
          flash("Restarting...", "ok"); setTimeout(function() { window.location.reload(); }, 3000);
        } catch (e) { flash("Failed: " + e.message, "bad"); }
      }
      
      async function clearTerminatedAgents() {
        try {
          await api("/agents/clear-terminated", { method: "POST" });
          flash("Terminated agents cleared.", "ok");
          await refreshAll();
        } catch (e) { flash("Clear failed: " + e.message, "bad"); }
      }
      
      function connectWs() {
        const config = getConfig();
        if (!config.baseUrl || !config.token) return;
        let protocol = "ws://";
        if (config.baseUrl.indexOf("https://") === 0) protocol = "wss://";
        const urlParts = config.baseUrl.split("://");
        const wsBase = urlParts[1] || urlParts[0];
        if (state.ws) { state.ws.onclose = null; state.ws.close(); }
        const ws = new WebSocket(protocol + wsBase + "/ws?token=" + encodeURIComponent(config.token));
        state.ws = ws;
        ws.onopen = function() { updateStreamState("Live"); };
        ws.onmessage = function(msg) {
          const ev = JSON.parse(msg.data);
          if (ev.machine) state.machineSelf.machine = ev.machine;
          if (ev.machine_health) state.machineHealth = ev.machine_health;
          if (ev.agent) mergeById(state.agents, ev.agent);
          if (ev.agent_status) {
            const index = state.running.findIndex(function(item) { return item.agent_id === ev.agent_status.agent_id; });
            if (index >= 0) state.running[index] = ev.agent_status;
            else state.running.unshift(ev.agent_status);
          }
          if (ev.job) mergeById(state.tasks, ev.job);
          if (ev.audit) mergeById(state.audit, ev.audit);
          renderMachine(); renderRunningAgents(); renderTasks(); renderAudit(); renderSelectedAgent();
        };
        ws.onclose = function() { updateStreamState("Disconnected"); setTimeout(connectWs, 2000); };
      }

      window.addEventListener('DOMContentLoaded', function() {
        el("launchType").addEventListener("change", function() { renderProfiles(); refreshLaunchContext(); });
        el("launchProfile").addEventListener("change", function() { refreshLaunchContext(); });
        el("workspace").addEventListener("change", function() { refreshLaunchContext(); });
        el("launchAgentBtn").addEventListener("click", launchAgent);
        el("sendPromptBtn").addEventListener("click", sendPrompt);
        el("stopAgentBtn").addEventListener("click", stopAgent);
        el("restartAgentBtn").addEventListener("click", restartAgent);
        el("restartSupervisorBtn").addEventListener("click", restartSupervisor);
        el("clearTerminatedBtn").addEventListener("click", clearTerminatedAgents);
        el("toggleConfigBtn").addEventListener("click", toggleConfig);
        el("saveConfigBtn").addEventListener("click", saveConfig);
        el("resetConfigBtn").addEventListener("click", function() { loadConfig(); flash("Reset to defaults", "ok"); });
        el("refreshAllBtn").addEventListener("click", refreshAll);
        
        const agentTabs = el('agentTabs').querySelectorAll('.tab');
        for (let i = 0; i < agentTabs.length; i++) {
          agentTabs[i].addEventListener('click', function() { showTab('agentTabs', this.dataset.tab, 'tab-'); });
        }
        
        const bottomTabs = el('bottomTabs').querySelectorAll('.tab');
        for (let i = 0; i < bottomTabs.length; i++) {
          bottomTabs[i].addEventListener('click', function() { showTab('bottomTabs', this.dataset.tab, 'btab-'); });
        }

        loadConfig();
        refreshAll();
      });
    })();
  </script>
</body>
</html>
"""


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_page() -> HTMLResponse:
    return HTMLResponse(ADMIN_HTML)
