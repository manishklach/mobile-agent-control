# Mobile Agent Control Architecture

## System Architecture

- Android app: remote control plane UI only
- Machine-side FastAPI service: local supervisor and orchestration layer
- Runtime adapter layer: vendor-neutral interface for terminal-native coding runtimes
- Executor layer: launches or simulates concrete agent runtimes through adapters
- Transport layer: pre-release direct private connectivity over Tailscale, later replaceable with a cloud-routed control plane

## Runtime Responsibilities

- Android app registers machines and sends control commands
- FastAPI supervisor owns machine-local state, lifecycle decisions, worker capacity, audit records, and websocket streaming
- CLI runtime adapters own vendor-specific CLI launch, auth, detection, and prompt execution behavior
- Executors translate supervisor commands into real agent actions; Phase 1 uses only a mock executor, later phases add real adapter-backed runtimes

## Adapter Pattern

- Shared models remain vendor-neutral:
  - machine
  - agent instance
  - task/job
  - audit event
  - launch profile
- `CliAgentRuntimeAdapter` defines the contract for terminal-native vendor runtimes.
- Each concrete adapter declares a capability set and implements:
  - local CLI detection
  - local auth checks
  - prompt execution
  - adapter-specific launch environment
- Current concrete adapters:
  - `GeminiCliAdapter`
  - `CodexCliAdapter`
  - `CopilotCliAdapter` placeholder
- Gemini CLI is the flagship example runtime in launch profiles, quickstart docs, and sample flows.

## Transport Abstraction

- The Android client should treat each machine endpoint as a transport endpoint, not as a permanent topology decision.
- For pre-release, the endpoint is a private Tailscale URL such as `http://100.x.y.z:8000` or `http://machine-name.tailnet-name.ts.net:8000`.
- Application auth remains required even when Tailscale provides network-level reachability.
- The repository/network layer should depend on a logical supervisor API interface, so the app can later swap:
  - from direct machine supervisor URLs
  - to a central cloud API that routes commands to machine supervisors
- The machine supervisor API shape should stay stable enough that cloud routing becomes a transport/proxy concern rather than an app redesign.

## Pre-Release Connectivity Model

- Android app connects only to private Tailscale-reachable supervisor URLs.
- Machine supervisors are not exposed on public internet ports.
- Tailscale is only the temporary connectivity layer for pre-release validation.
- The long-term architecture should not assume device-to-machine direct reachability.

## API Contract

- `GET /health`: service health plus aggregate counts
- `GET /machines/self`: machine identity, worker pool state, capabilities
- `GET /agents`: list supervised agents
- `GET /agents/{id}`: agent detail plus current job
- `POST /agents/start`: create and queue/start a supervised agent
- `POST /agents/{id}/stop`: stop a pending or active agent
- `POST /agents/{id}/restart`: stop then queue/start the same agent again
- `POST /agents/{id}/prompt`: submit prompt input to an existing agent
- `POST /agents/{id}/tasks`: submit task work to an existing agent
- `GET /agents/{id}/logs`: recent agent logs
- `GET /audit`: supervisor command audit log
- `GET /ws`: websocket stream for machine, agent, job, log, and audit events

## Data Model

- Machine: machine id/name, status, worker pool, capabilities
- Worker pool: desired workers, busy workers, idle workers, queue depth, pause/resume support flag
- Agent: id, type, state, current task, worker assignment, current job id, logs, metadata
- Job: id, agent id, kind, state, input text, timestamps, summary, error
- Audit entry: action, target, timestamp, status, message, details
- Launch profile: neutral runtime metadata plus adapter binding and capability declarations

## State Model

- Agent states: `pending`, `starting`, `running`, `idle`, `stopping`, `stopped`, `failed`
- Job states: `queued`, `running`, `completed`, `failed`, `cancelled`

## Phased Implementation Plan

### Phase 1

- FastAPI supervisor only
- in-memory machine, worker, agent, and job registry
- mock executor only
- lifecycle endpoints and websocket events
- bearer token auth
- audit log

### Phase 2

- Android control-plane client
- machine registration, list/detail, agent list/detail, logs, live updates
- repository + ViewModel + StateFlow
- machine registration should store transport endpoints generically, with Tailscale URLs used in pre-release

### Phase 3

- real executor layer for Gemini-first and additional adapter-backed runtimes
- restart semantics backed by real processes
- richer task submission contracts
- safer local command controls
- cloud control-plane design that can proxy or broker the same supervisor API semantics

### Phase 4

- optional pause/resume support when executor exposes it
- worker scale up/down controls
- persistence, retries, notifications, and multi-machine operations
- migration from direct Tailscale-reachable machine URLs to cloud-routed endpoints without changing the UI model
