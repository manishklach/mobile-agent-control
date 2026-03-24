# Agent Control MVP

The current implementation provides a machine-side supervisor backend plus an Android control client.

The backend supervises in-memory agents, jobs, worker capacity, logs, and audit records. It supports both:

- mock agents through `POST /agents/start`
- safe local process launch through supervisor-approved launch profiles and `POST /agents/launch`
- a real local Codex runner profile that executes prompts through the installed `codex` CLI
- a real local Gemini runner profile that executes prompts through the installed `gemini` CLI

For pre-release deployment, use Tailscale only as the private connectivity layer between the Android client and each machine supervisor. This is not the final product architecture.

## Scope

- FastAPI backend only
- machine model
- worker pool model
- agent model
- job model
- in-memory registry
- mock executor
- shell executor with safe launch profiles
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
    api/
      deps.py
      routes.py
    core/
      auth.py
      config.py
    executors/
      base.py
      mock_executor.py
      shell_executor.py
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
- `GET /agents`
- `GET /agents/{id}`
- `POST /agents/start`
- `GET /launch-profiles`
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

Start a mock Codex agent:

```powershell
curl -X POST http://localhost:8000/agents/start `
  -H "Authorization: Bearer replace-with-a-random-token" `
  -H "Content-Type: application/json" `
  -d "{\"type\":\"codex\",\"initial_task\":\"Boot a coding agent for repo triage\"}"
```

Launch a supervised local Codex process with the real Codex CLI runner:

```powershell
curl -X POST http://localhost:8000/agents/launch `
  -H "Authorization: Bearer 0118" `
  -H "Content-Type: application/json" `
  -d "{\"type\":\"codex\",\"launch_profile\":\"codex-safe-default\",\"workspace\":\"C:\\Users\\ManishKL\\Documents\\Playground\",\"initial_prompt\":\"Print startup status\"}"
```

Launch a supervised local Gemini process with the real Gemini CLI runner:

```powershell
curl -X POST http://localhost:8000/agents/launch `
  -H "Authorization: Bearer 0118" `
  -H "Content-Type: application/json" `
  -d "{\"type\":\"gemini\",\"launch_profile\":\"gemini-safe-default\",\"workspace\":\"C:\\Users\\ManishKL\\Documents\\Playground\",\"initial_prompt\":\"Print startup status\"}"
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
- `agent`
- `job`
- `log`
- `audit`
- `message`

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

- `shell_executor.py` launches only configured safe profiles from `backend/config/launch_profiles.json`.
- Worker scaling and pause/resume semantics are intentionally deferred.
- All state is in memory and resets on restart.
- Tailscale is a temporary pre-release transport layer only.
- `codex-safe-default` now runs a supervised local Codex CLI runner and supports prompts from the Android app.
- `gemini-safe-default` now runs a supervised local Gemini CLI runner and requires Gemini CLI to be installed and authenticated on the machine.

## Minimal Test Checklist

1. `GET /health` returns `200` with machine and queue counts.
2. `GET /machines/self` returns worker pool state and capabilities.
3. `POST /agents/start` returns an agent in `pending` or `starting`, then the websocket shows it becoming `idle`.
4. `GET /launch-profiles` returns safe launch templates for `codex` and `gemini`.
5. `POST /agents/launch` returns an agent with `pid`, `workspace`, and `launch_profile`, then the websocket shows it becoming `idle`.
6. `POST /agents/{id}/prompt` on a launched agent appends stdin/stdout logs and keeps the process supervised.
7. `POST /agents/{id}/restart` on a launched agent restarts the process using the same saved profile and workspace.
8. `POST /agents/{id}/tasks` moves a mock agent to `running`, streams logs, then returns to `idle`.
9. `POST /agents/{id}/stop` stops a pending or active agent and records an audit entry.
10. `GET /agents/{id}/logs` returns recent logs for that agent.
11. `GET /audit` shows accepted control commands.
12. Requests without the bearer token return `401`.
