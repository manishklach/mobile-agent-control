# Agent Control MVP

Agent Control MVP is a vendor-neutral mobile control plane for terminal-native coding agents.

The current implementation provides:

- an Android operator console
- a responsive web operator console at `/admin`
- a machine-side FastAPI supervisor
- a vendor-neutral CLI runtime adapter layer
- Gemini-first slash command and MCP awareness

Gemini CLI is the flagship default integration in the demo config and quickstart, while Codex CLI and Hermes Agent are implemented through the same adapter contract.

For pre-release deployment, use Tailscale only as the private connectivity layer between the Android client and each machine supervisor. This is not the final product architecture.

## Product Positioning

- Mobile-first control plane for remotely launching, monitoring, and steering terminal-native coding agents
- Machine supervisor owns local lifecycle, logs, worker capacity, and audit state
- Runtime adapters isolate vendor-specific CLI launch, auth, and prompt execution behavior
- Shared machine, agent, task, audit, and launch-profile models stay vendor-neutral
- Gemini CLI is the default example runtime, but the architecture is designed for additional adapters such as Codex CLI, Copilot CLI, Hermes, or Microsoft-backed runtimes later

## Scope

- FastAPI backend only
- machine model
- worker pool model
- agent model
- job model
- in-memory registry
- mock executor
- CLI runtime executor with safe launch profiles
- bearer token auth
- websocket streaming for live state and logs
- command audit log

Architecture, API contract, data model, and phased plan are documented in [docs/architecture.md](/C:/Users/ManishKL/Documents/Playground/agent-control-mvp/docs/architecture.md).

## Pre-Release Transport

- Use Tailscale private addresses or MagicDNS names for machine supervisor base URLs.
- Keep application bearer-token auth enabled even on the Tailscale network.
- Do not expose supervisor ports publicly.
- Do not hardcode LAN-specific assumptions such as emulator-only loopback or local subnet discovery into product design.

Example machine base URLs for pre-release:

- `http://100.x.y.z:8000`
- `http://workstation-main.tailnet-name.ts.net:8000`

## Backend Structure

```text
backend/
  app/
    adapters/
      base.py
      gemini_cli.py
      hermes_cli.py
      codex_cli.py
      copilot_cli.py
      registry.py
    api/
      deps.py
      routes.py
    core/
      auth.py
      config.py
    executors/
      base.py
      cli_runtime_executor.py
      cli_runtime_host.py
      mock_executor.py
    services/
      agent_manager.py
      event_bus.py
    main.py
    models.py
  requirements.txt
  .env.example
```

## REST Endpoints

- `GET /health`
- `GET /machines/self`
- `GET /machines`
- `GET /machines/{id}/health`
- `GET /agents`
- `GET /agents/overview`
- `GET /agents/running`
- `GET /agents/{id}`
- `GET /agents/{id}/events`
- `GET /agents/{id}/metrics`
- `POST /agents/start`
- `GET /launch-profiles`
- `GET /runtime/adapters`
- `GET /runtime/adapters/{adapter_id}`
- `GET /runtime/adapters/{adapter_id}/commands`
- `POST /runtime/adapters/{adapter_id}/commands`
- `DELETE /runtime/adapters/{adapter_id}/commands/{command_name}`
- `GET /workspaces`
- `GET /machines/{id}/mcp`
- `POST /agents/launch`
- `POST /agents/{id}/stop`
- `POST /agents/{id}/restart`
- `POST /agents/{id}/prompt`
- `POST /agents/{id}/tasks`
- `GET /agents/{id}/logs`
- `GET /audit`
- `GET /tasks`
- `GET /tasks/{id}`
- `WS /ws`

## Example Requests

Start a mock Gemini agent:

```powershell
curl -X POST http://localhost:8000/agents/start `
  -H "Authorization: Bearer replace-with-a-random-token" `
  -H "Content-Type: application/json" `
  -d "{\"type\":\"gemini\",\"initial_task\":\"Boot a coding agent for repo triage\"}"
```

Launch a supervised local Gemini process with the real Gemini CLI adapter:

```powershell
curl -X POST http://localhost:8000/agents/launch `
  -H "Authorization: Bearer 0118" `
  -H "Content-Type: application/json" `
  -d "{\"type\":\"gemini\",\"launch_profile\":\"gemini-safe-default\",\"workspace\":\"C:\\Users\\ManishKL\\Documents\\Playground\",\"initial_prompt\":\"Summarize the repo and confirm the control plane is connected\"}"
```

Inspect Gemini runtime status and capabilities:

```powershell
curl -X GET http://localhost:8000/runtime/adapters/gemini-cli `
  -H "Authorization: Bearer 0118"
```

List Gemini slash commands for a workspace:

```powershell
curl -X GET "http://localhost:8000/runtime/adapters/gemini-cli/commands?workspace=C:\Users\ManishKL\Documents\Playground" `
  -H "Authorization: Bearer 0118"
```

Inspect machine MCP visibility:

```powershell
curl -X GET "http://localhost:8000/machines/machine-self/mcp?workspace=C:\Users\ManishKL\Documents\Playground" `
  -H "Authorization: Bearer 0118"
```

Launch a supervised local Codex process with the Codex CLI adapter:

```powershell
curl -X POST http://localhost:8000/agents/launch `
  -H "Authorization: Bearer 0118" `
  -H "Content-Type: application/json" `
  -d "{\"type\":\"codex\",\"launch_profile\":\"codex-safe-default\",\"workspace\":\"C:\\Users\\ManishKL\\Documents\\Playground\",\"initial_prompt\":\"Print startup status\"}"
```

Launch a supervised Hermes Agent process through WSL:

```powershell
curl -X POST http://localhost:8000/agents/launch `
  -H "Authorization: Bearer 0118" `
  -H "Content-Type: application/json" `
  -d "{\"type\":\"hermes\",\"launch_profile\":\"hermes-safe-default\",\"workspace\":\"C:\\Users\\ManishKL\\Documents\\Playground\",\"initial_prompt\":\"Summarize this repository\"}"
```

Submit a task:

```powershell
curl -X POST http://localhost:8000/agents/<agent-id>/tasks `
  -H "Authorization: Bearer replace-with-a-random-token" `
  -H "Content-Type: application/json" `
  -d "{\"input_text\":\"Summarize repository status\",\"kind\":\"task\"}"
```

Send a prompt:

```powershell
curl -X POST http://localhost:8000/agents/<agent-id>/prompt `
  -H "Authorization: Bearer replace-with-a-random-token" `
  -H "Content-Type: application/json" `
  -d "{\"prompt\":\"Focus on open issues first\"}"
```

Restart an agent:

```powershell
curl -X POST http://localhost:8000/agents/<agent-id>/restart `
  -H "Authorization: Bearer replace-with-a-random-token" `
  -H "Content-Type: application/json" `
  -d "{\"reason\":\"Apply new control directive\"}"
```

## Websocket Events

Connect to `ws://localhost:8000/ws` with either:

- `Authorization: Bearer <token>` header, or
- `?token=<token>` query parameter

Event payloads may include:

- `machine`
- `machine_health`
- `agent`
- `agent_status`
- `job`
- `log`
- `audit`
- `message`

Monitoring highlights:

- The Android app includes a cross-machine `Running Agents` screen.
- Machine cards surface warning counts, heartbeat, worker usage, and offline state.
- Agent detail now shows elapsed time, last heartbeat, last log time, recent logs, recent events, and warning/stuck indicators.
- Stuck detection is heuristic-based: running agents with no logs for a configured interval are promoted to `warning`, then `stuck`.

## Local Run

```powershell
cd backend
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Launch profiles are loaded from `backend/config/launch_profiles.json`. The Codex profile is wired to a real local runner process. The phone never sends arbitrary shell commands.

Gemini setup on the machine:

1. Install Gemini CLI: `npm install -g @google/gemini-cli`
2. Complete one-time local auth on the machine by running `gemini`
3. Confirm non-interactive mode works with:

```powershell
gemini -p "Reply with exactly: hello from gemini" --output-format json
```

Once that succeeds locally, the supervisor can launch Gemini through `gemini-safe-default`.

Hermes setup on the machine:

1. Install Hermes inside WSL.
2. Run `hermes setup` inside WSL to configure a provider and local state.
3. Confirm non-interactive mode works inside WSL with:

```powershell
wsl.exe --cd /tmp hermes chat -q "Reply with exactly: hello from hermes"
```

Once that succeeds in WSL, the supervisor can launch Hermes through `hermes-safe-default`.

Gemini-first operator features:

- The Android launch flow now defaults to Gemini and can surface Gemini CLI version/auth status.
- The web console at `/admin` is responsive for desktop Chrome, Android Chrome, and Safari/WebKit-class mobile browsers.
- Workspace-scoped and user-scoped Gemini slash commands are listed from the real `.gemini/commands` directories.
- MCP servers are read from Gemini settings and surfaced in machine health and launch support views.
- Agent monitoring now includes runtime model, selected slash command, MCP usage, and last output time where available.

Adapter architecture:

- `CliAgentRuntimeAdapter`: vendor-neutral interface for terminal-native runtimes
- `GeminiCliAdapter`: default example adapter and demo path
- `HermesCliAdapter`: WSL-backed Hermes runtime adapter for Windows hosts
- `CodexCliAdapter`: alternate real CLI adapter
- `CopilotCliAdapter`: registered adapter placeholder for future activation
- `CliRuntimeExecutor`: supervisor-facing executor that delegates all vendor logic to adapters
- `cli_runtime_host.py`: generic runtime host used by all CLI adapters

Workspace discovery:

- Configure safe workspace roots with `AGENT_CONTROL_ALLOWED_WORKSPACE_ROOTS`
- Optionally configure preferred picker entries with `AGENT_CONTROL_CONFIGURED_WORKSPACES`
- The Android app now loads these from `GET /workspaces` and remembers the last-used workspace per machine

## Pre-Release Deployment With Tailscale

1. Install Tailscale on each machine that runs a supervisor.
2. Install Tailscale on the Android device.
3. Join all devices to the same tailnet.
4. Start the FastAPI supervisor on each machine bound to the Tailscale-reachable interface or `0.0.0.0`.
5. Confirm each supervisor is reachable from another tailnet device using its Tailscale IP or MagicDNS hostname.
6. In the Android app, register each machine using its private Tailscale base URL and the matching application bearer token.
7. Keep any firewall rules restricted to the tailnet/private network context; do not publish the service to the public internet.

## Later Migration To Cloud Control Plane

The current Android app should conceptually target a logical supervisor API, not “direct machine access” as a permanent product assumption.

Planned migration path:

1. Keep machine supervisors as local orchestration agents on each machine.
2. Introduce a cloud control-plane API that authenticates the mobile client.
3. Have the cloud API route or broker commands to machine supervisors.
4. Preserve the same high-level resource model in the client:
   - machine
   - agent
   - task/job
   - logs/events
5. Replace stored direct machine URLs with cloud-routed endpoint references or machine IDs.
6. Keep application-level auth and authorization independent from the transport layer.

## Notes

- `cli_runtime_executor.py` launches only configured safe profiles from `backend/config/launch_profiles.json`.
- Worker scaling and pause/resume semantics are intentionally deferred.
- All state is in memory and resets on restart.
- Recent agents, tasks, and audit entries are now persisted locally to `backend/data/supervisor_state.db`.
- The state store uses SQLite by default and will migrate a legacy `supervisor_state.json` snapshot if present.
- Tailscale is a temporary pre-release transport layer only.
- `gemini-safe-default` is the default sample runtime and uses `GeminiCliAdapter`.
- `codex-safe-default` uses the same adapter architecture via `CodexCliAdapter`.
- Vendor-specific auth and CLI detection now live in adapter modules instead of shared supervisor code paths.

## Automated Backend Tests

Run the current backend unit suite with:

```powershell
cd backend
. .venv\Scripts\Activate.ps1
python -m unittest discover -s tests -v
```

Current automated coverage focuses on:

- SQLite state-store round trips and JSON migration
- queued agent cancellation
- mock startup and task completion transitions
- restore-time normalization of in-flight agents and jobs after supervisor restart

## Minimal Test Checklist

1. `GET /health` returns `200` with machine and queue counts.
2. `GET /machines/self` returns worker pool state and capabilities.
3. `POST /agents/start` returns an agent in `pending` or `starting`, then the websocket shows it becoming `idle`.
4. `GET /launch-profiles` returns safe launch templates for `codex` and `gemini`.
5. `POST /agents/launch` returns an agent with `pid`, `workspace`, and `launch_profile`, then the websocket shows it becoming `idle`.
6. `GET /workspaces` returns safe configured/discovered workspace entries for the launch picker.
7. `POST /agents/{id}/prompt` on a launched agent appends stdin/stdout logs and keeps the process supervised.
8. `POST /agents/{id}/restart` on a launched agent restarts the process using the same saved profile and workspace.
9. `POST /agents/{id}/tasks` moves a mock agent to `running`, streams logs, then returns to `idle`.
10. `POST /agents/{id}/stop` stops a pending or active agent and records an audit entry.
11. Restart the backend and confirm recent agents/tasks/audit entries are still listed.
12. `GET /agents/{id}/logs` returns recent logs for that agent.
13. `GET /audit` shows accepted control commands.
14. Requests without the bearer token return `401`.
15. `GET /machines`, `GET /machines/{id}/health`, `GET /agents/running`, `GET /agents/{id}/events`, and `GET /agents/{id}/metrics` return monitoring data.
16. Websocket events include machine heartbeats, agent state updates, warning/stuck transitions, and live log entries.
