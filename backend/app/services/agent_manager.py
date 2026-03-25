from __future__ import annotations

import asyncio
import json
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.config import AppSettings, LaunchProfileConfig
from app.executors.base import ProcessHandle
from app.executors.cli_runtime_executor import CliRuntimeExecutor
from app.executors.mock_executor import MockExecutor
from app.models import (
    AgentDetailResponse,
    AgentEventsResponse,
    AgentListResponse,
    AgentMetricsResponse,
    AgentRecord,
    AgentRuntimeStatus,
    AgentState,
    AuditEntry,
    AuditLogResponse,
    AuditStatus,
    HealthResponse,
    JobKind,
    JobRecord,
    JobState,
    LaunchAgentRequest,
    LaunchProfileRecord,
    LaunchProfilesResponse,
    LogsResponse,
    McpServersResponse,
    MachineHealthStatus,
    MachineListResponse,
    MachineRecord,
    MachineSelfResponse,
    PromptAgentRequest,
    RestartAgentRequest,
    RuntimeAdapterRecord,
    RuntimeAdapterStatusResponse,
    RuntimeAdaptersResponse,
    RunningAgentsResponse,
    SlashCommandsResponse,
    StartAgentRequest,
    SubmitTaskRequest,
    SupervisorEvent,
    TaskDetailResponse,
    TaskListResponse,
    PersistedState,
    WorkspaceRecord,
    WorkspacesResponse,
    WorkerPoolState,
)
from app.services.event_bus import EventBus
from app.services.state_store import StateStore

EVENT_PREFIX = "__SUPERVISOR_EVENT__"

try:
    import psutil
except ImportError:  # pragma: no cover - optional runtime dependency
    psutil = None


class AgentManager:
    def __init__(
        self,
        settings: AppSettings,
        mock_executor: MockExecutor,
        runtime_executor: CliRuntimeExecutor,
        launch_profiles: dict[str, LaunchProfileConfig],
        event_bus: EventBus,
        state_store: StateStore,
    ) -> None:
        self.settings = settings
        self.mock_executor = mock_executor
        self.runtime_executor = runtime_executor
        self.launch_profiles = launch_profiles
        self.event_bus = event_bus
        self.state_store = state_store
        now = datetime.now(UTC)
        self.machine = MachineRecord(
            id=settings.machine_id,
            name=settings.machine_name,
            status="online",
            started_at=now,
            updated_at=now,
            worker_pool=WorkerPoolState(
                desired_workers=settings.mock_worker_capacity,
                busy_workers=0,
                idle_workers=settings.mock_worker_capacity,
                queue_depth=0,
                supports_pause_resume=False,
            ),
            capabilities={
                "start_agent": True,
                "launch_agent": True,
                "stop_agent": True,
                "restart_agent": True,
                "submit_prompt": True,
                "submit_task": True,
                "pause_resume": False,
                "scale_workers": False,
            },
        )
        self._agents: dict[str, AgentRecord] = {}
        self._jobs: dict[str, JobRecord] = {}
        self._handles: dict[str, ProcessHandle] = {}
        self._audits: list[AuditEntry] = []
        self._pending_queue: deque[str] = deque()
        self._job_tasks: dict[str, asyncio.Task[None]] = {}
        self._process_monitors: dict[str, asyncio.Task[None]] = {}
        self._log_offsets: dict[str, int] = {}
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._last_heartbeat_at = now
        self._event_history: deque[SupervisorEvent] = deque(maxlen=self.settings.max_log_entries)
        self._agent_event_history: dict[str, deque[SupervisorEvent]] = {}
        self._agent_monitor_state: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._restore_state()

    async def health(self) -> HealthResponse:
        await self._refresh_machine()
        return HealthResponse(
            status="ok",
            time=datetime.now(UTC),
            machine_id=self.machine.id,
            machine_name=self.machine.name,
            agents_total=len(self._agents),
            agents_running=sum(1 for agent in self._agents.values() if agent.state in {AgentState.RUNNING, AgentState.IDLE}),
            queued_jobs=sum(1 for job in self._jobs.values() if job.state == JobState.QUEUED),
        )

    async def machines(self) -> MachineListResponse:
        await self._refresh_machine()
        return MachineListResponse(machines=[self.machine])

    async def machine_health(self, machine_id: str) -> MachineHealthStatus:
        if machine_id != self.machine.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found")
        await self._refresh_machine()
        return self._machine_health_status()

    async def machine_self(self) -> MachineSelfResponse:
        await self._refresh_machine()
        return MachineSelfResponse(
            machine=self.machine,
            agents_total=len(self._agents),
            active_agents=sum(1 for agent in self._agents.values() if agent.state in {AgentState.RUNNING, AgentState.IDLE, AgentState.STARTING}),
            queued_jobs=sum(1 for job in self._jobs.values() if job.state == JobState.QUEUED),
            max_active_agents=self.settings.max_active_agents,
        )

    async def list_agents(self) -> AgentListResponse:
        await self._refresh_machine()
        for agent in self._agents.values():
            self._sanitize_agent_runtime_metadata(agent)
        return AgentListResponse(agents=sorted(self._agents.values(), key=lambda item: item.updated_at, reverse=True))

    async def running_agents(self) -> RunningAgentsResponse:
        await self._refresh_machine()
        active_states = {AgentState.RUNNING, AgentState.IDLE, AgentState.STARTING, AgentState.PENDING, AgentState.STOPPING}
        statuses = [
            self._agent_runtime_status(agent)
            for agent in self._agents.values()
            if agent.state in active_states
        ]
        return RunningAgentsResponse(agents=sorted(statuses, key=lambda item: (item.monitor_state, -item.elapsed_seconds)))

    async def get_agent(self, agent_id: str) -> AgentDetailResponse:
        agent = self._require_agent(agent_id)
        self._sanitize_agent_runtime_metadata(agent)
        current_job = self._jobs.get(agent.current_job_id) if agent.current_job_id else None
        recent_jobs = self._recent_jobs_for_agent(agent_id)
        latest_completed_job = next(
            (job for job in recent_jobs if job.state in {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}),
            None,
        )
        return AgentDetailResponse(agent=agent, current_job=current_job, latest_completed_job=latest_completed_job, recent_jobs=recent_jobs)

    async def get_launch_profiles(self) -> LaunchProfilesResponse:
        profiles = [LaunchProfileRecord(**profile.public_dict()) for profile in self.launch_profiles.values()]
        return LaunchProfilesResponse(profiles=profiles)

    async def list_runtime_adapters(self, workspace: str | None = None) -> RuntimeAdaptersResponse:
        adapters = [
            RuntimeAdapterRecord(
                adapter_id=adapter.adapter_id,
                agent_type=adapter.agent_type,
                label=adapter.label,
                capabilities=adapter.capabilities,
                status=adapter.runtime_status(workspace),
            )
            for adapter in self._runtime_adapters().values()
        ]
        return RuntimeAdaptersResponse(adapters=adapters)

    async def get_runtime_adapter(self, adapter_id: str, workspace: str | None = None) -> RuntimeAdapterStatusResponse:
        adapter = self._runtime_adapters().get(adapter_id)
        if adapter is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Runtime adapter not found")
        return RuntimeAdapterStatusResponse(
            adapter=RuntimeAdapterRecord(
                adapter_id=adapter.adapter_id,
                agent_type=adapter.agent_type,
                label=adapter.label,
                capabilities=adapter.capabilities,
                status=adapter.runtime_status(workspace),
            )
        )

    async def list_slash_commands(self, adapter_id: str, workspace: str | None = None) -> SlashCommandsResponse:
        adapter = self._require_runtime_adapter(adapter_id)
        workspace_path = str(self._validate_workspace(workspace)) if workspace else None
        return SlashCommandsResponse(adapter_id=adapter_id, commands=adapter.list_command_templates(workspace_path))

    async def upsert_slash_command(
        self,
        adapter_id: str,
        *,
        name: str,
        prompt: str,
        description: str | None = None,
        scope: str = "project",
        workspace: str | None = None,
    ) -> SlashCommandsResponse:
        adapter = self._require_runtime_adapter(adapter_id)
        workspace_path = str(self._validate_workspace(workspace)) if workspace else None
        adapter.upsert_command_template(
            name=name,
            prompt=prompt,
            description=description,
            scope=scope,
            workspace=workspace_path,
        )
        return await self.list_slash_commands(adapter_id, workspace_path)

    async def delete_slash_command(self, adapter_id: str, name: str, scope: str = "project", workspace: str | None = None) -> SlashCommandsResponse:
        adapter = self._require_runtime_adapter(adapter_id)
        workspace_path = str(self._validate_workspace(workspace)) if workspace else None
        adapter.delete_command_template(name=name, scope=scope, workspace=workspace_path)
        return await self.list_slash_commands(adapter_id, workspace_path)

    async def machine_mcp_servers(self, machine_id: str, workspace: str | None = None) -> McpServersResponse:
        if machine_id != self.machine.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found")
        workspace_path = str(self._validate_workspace(workspace)) if workspace else None
        servers = []
        for adapter in self._runtime_adapters().values():
            if not adapter.capabilities.supports_mcp:
                continue
            servers.extend(adapter.list_mcp_servers(workspace_path))
        return McpServersResponse(machine_id=self.machine.id, servers=servers)

    async def list_workspaces(self) -> WorkspacesResponse:
        configured: dict[str, WorkspaceRecord] = {}
        for raw_path in self.settings.configured_workspaces:
            if not raw_path.strip():
                continue
            try:
                path = self._validate_workspace(raw_path)
            except HTTPException:
                continue
            configured[str(path)] = WorkspaceRecord(path=str(path), label=path.name or str(path), source="configured")
        discovered: dict[str, WorkspaceRecord] = {}
        for root in self._workspace_roots():
            for candidate in self._discover_workspaces(root):
                discovered.setdefault(
                    str(candidate),
                    WorkspaceRecord(
                        path=str(candidate),
                        label=candidate.name,
                        source="discovered",
                    ),
                )
        recent = {
            agent.workspace: WorkspaceRecord(
                path=agent.workspace,
                label=Path(agent.workspace).name or agent.workspace,
                source="recent",
            )
            for agent in self._agents.values()
            if agent.workspace and Path(agent.workspace).exists()
        }
        combined = {**discovered, **configured, **recent}
        return WorkspacesResponse(workspaces=sorted(combined.values(), key=lambda item: (item.label.lower(), item.path.lower())))

    async def start_agent(self, request: StartAgentRequest) -> AgentDetailResponse:
        async with self._lock:
            self._enforce_capacity()
            now = datetime.now(UTC)
            agent_id = str(uuid4())
            startup_job = self._create_job(agent_id=agent_id, kind=JobKind.STARTUP, input_text=request.initial_task or "start agent")
            agent = AgentRecord(
                id=agent_id,
                type=request.type,
                state=AgentState.PENDING,
                pid=None,
                workspace=None,
                launch_profile=None,
                current_task=request.initial_task,
                started_at=None,
                updated_at=now,
                worker_id=None,
                current_job_id=startup_job.id,
                runtime_model=None,
                command_name=None,
                last_output_at=None,
                mcp_enabled=False,
                mcp_servers=[],
                recent_logs=[],
                metadata=request.metadata,
            )
            self._agents[agent_id] = agent
            self._pending_queue.append(agent_id)
            await self._append_audit(
                action="start_agent",
                target_type="agent",
                target_id=agent_id,
                status=AuditStatus.ACCEPTED,
                message="Start command accepted by supervisor",
                details={"type": request.type.value},
            )
            await self._schedule_pending_agents()
            return await self.get_agent(agent_id)

    async def launch_agent(self, request: LaunchAgentRequest) -> AgentDetailResponse:
        async with self._lock:
            self._enforce_capacity()
            profile = self.launch_profiles.get(request.launch_profile)
            if profile is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown launch profile")
            if profile.agent_type != request.type:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Launch profile does not match agent type")
            workspace = self._validate_workspace(request.workspace)
            runtime_model, command_name = self._normalize_launch_options(
                request.launch_profile,
                request.runtime_model,
                request.command_name,
            )

            now = datetime.now(UTC)
            agent_id = str(uuid4())
            startup_job = self._create_job(agent_id=agent_id, kind=JobKind.STARTUP, input_text=request.initial_prompt or "launch agent")
            metadata = self._build_launch_metadata(
                request.type,
                request.launch_profile,
                str(workspace),
                request.initial_prompt,
                runtime_model=runtime_model,
                command_name=command_name,
            )
            agent = AgentRecord(
                id=agent_id,
                type=request.type,
                state=AgentState.PENDING,
                pid=None,
                workspace=str(workspace),
                launch_profile=request.launch_profile,
                current_task=request.initial_prompt,
                started_at=None,
                updated_at=now,
                worker_id=None,
                current_job_id=startup_job.id,
                runtime_model=runtime_model,
                command_name=command_name,
                mcp_enabled=bool(self._profile_metadata(request.launch_profile).get("mcp_enabled", False)),
                mcp_servers=self._mcp_server_names(str(workspace)),
                recent_logs=[],
                metadata=metadata,
            )
            self._agents[agent_id] = agent
            await self._append_audit(
                action="launch_agent",
                target_type="agent",
                target_id=agent_id,
                status=AuditStatus.ACCEPTED,
                message="Launch command accepted by supervisor" if self._has_available_worker_slot() else "Launch queued; waiting for worker capacity",
                details={
                    "launch_profile": request.launch_profile,
                    "workspace": str(workspace),
                    "runtime_model": runtime_model,
                    "command_name": command_name,
                },
            )
            if self._has_available_worker_slot():
                await self._launch_process_agent(agent, raise_on_failure=True)
            else:
                self._pending_queue.append(agent_id)
                await self._publish("agent.pending", agent=agent, job=startup_job, message="Launch queued; waiting for worker capacity")
            return await self.get_agent(agent_id)

    async def stop_agent(self, agent_id: str) -> AgentDetailResponse:
        async with self._lock:
            agent = self._require_agent(agent_id)
            await self._append_audit(
                action="stop_agent",
                target_type="agent",
                target_id=agent_id,
                status=AuditStatus.ACCEPTED,
                message="Stop command accepted by supervisor",
            )
            if agent.state == AgentState.PENDING:
                self._remove_from_queue(agent_id)
                agent.state = AgentState.STOPPED
                agent.updated_at = datetime.now(UTC)
                if agent.current_job_id:
                    self._complete_job(agent.current_job_id, JobState.CANCELLED, "Agent start cancelled before launch")
                await self._publish("agent.stopped", agent=agent, message="Pending agent cancelled")
                await self._refresh_machine()
                return await self.get_agent(agent_id)

            handle = self._handles.get(agent_id)
            if handle is None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent is not active")

            agent.state = AgentState.STOPPING
            agent.updated_at = datetime.now(UTC)
            await self._publish("agent.stopping", agent=agent, message="Stopping agent")
            executor = self._executor_for(agent)
            await executor.stop(handle)
            if agent.current_job_id and self._jobs[agent.current_job_id].state in {JobState.QUEUED, JobState.RUNNING}:
                self._complete_job(agent.current_job_id, JobState.CANCELLED, "Stopped by supervisor")
            await self._finalize_stop(agent_id)
            return await self.get_agent(agent_id)

    async def restart_agent(self, agent_id: str, request: RestartAgentRequest) -> AgentDetailResponse:
        async with self._lock:
            agent = self._require_agent(agent_id)
            relaunch_profile = agent.launch_profile
            relaunch_workspace = agent.workspace
            await self._append_audit(
                action="restart_agent",
                target_type="agent",
                target_id=agent_id,
                status=AuditStatus.ACCEPTED,
                message=request.reason or "Restart command accepted",
            )
            if agent.state in {AgentState.RUNNING, AgentState.IDLE, AgentState.STARTING, AgentState.STOPPING}:
                handle = self._handles.get(agent_id)
                if handle is not None:
                    await self._executor_for(agent).stop(handle)
                await self._finalize_stop(agent_id)

            restart_job = self._create_job(agent_id=agent_id, kind=JobKind.RESTART, input_text=request.reason or "restart agent")
            if relaunch_profile and relaunch_workspace:
                agent.state = AgentState.PENDING
                agent.pid = None
                agent.worker_id = None
                agent.current_job_id = restart_job.id
                agent.current_task = request.reason
                agent.updated_at = datetime.now(UTC)
                if self._has_available_worker_slot():
                    await self._launch_process_agent(agent, raise_on_failure=True)
                else:
                    self._pending_queue.append(agent_id)
                    await self._publish("agent.pending", agent=agent, job=restart_job, message="Agent queued for restart")
            else:
                agent.state = AgentState.PENDING
                agent.pid = None
                agent.worker_id = None
                agent.current_job_id = restart_job.id
                agent.updated_at = datetime.now(UTC)
                self._pending_queue.append(agent_id)
                await self._publish("agent.pending", agent=agent, job=restart_job, message="Agent queued for restart")
                await self._schedule_pending_agents()
            return await self.get_agent(agent_id)

    async def submit_task(self, agent_id: str, request: SubmitTaskRequest) -> AgentDetailResponse:
        if request.kind not in {JobKind.TASK, JobKind.PROMPT}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported job kind for submit_task")
        return await self._submit_job(agent_id=agent_id, input_text=request.input_text, kind=request.kind)

    async def send_prompt(self, agent_id: str, request: PromptAgentRequest) -> AgentDetailResponse:
        return await self._submit_job(agent_id=agent_id, input_text=request.prompt, kind=JobKind.PROMPT)

    async def get_logs(self, agent_id: str, limit: int | None = None) -> LogsResponse:
        agent = self._require_agent(agent_id)
        handle = self._handles.get(agent_id)
        if handle is None:
            return LogsResponse(agent_id=agent_id, logs=agent.recent_logs[-(limit or self.settings.default_log_limit) :])
        return LogsResponse(agent_id=agent_id, logs=self._executor_for(agent).recent_logs(handle, limit or self.settings.default_log_limit))

    async def get_agent_events(self, agent_id: str, limit: int = 100) -> AgentEventsResponse:
        self._require_agent(agent_id)
        history = list(self._agent_event_history.get(agent_id, deque()))
        return AgentEventsResponse(agent_id=agent_id, events=history[-limit:])

    async def get_agent_metrics(self, agent_id: str) -> AgentMetricsResponse:
        agent = self._require_agent(agent_id)
        return AgentMetricsResponse(agent_id=agent_id, status=self._agent_runtime_status(agent))

    async def get_audit_log(self, limit: int = 100) -> AuditLogResponse:
        return AuditLogResponse(entries=self._audits[-limit:])

    async def list_tasks(self, limit: int = 100) -> TaskListResponse:
        tasks = sorted(self._jobs.values(), key=lambda job: job.updated_at, reverse=True)
        return TaskListResponse(tasks=tasks[:limit])

    async def get_task(self, task_id: str) -> TaskDetailResponse:
        return TaskDetailResponse(task=self._require_job(task_id))

    async def _submit_job(self, agent_id: str, input_text: str, kind: JobKind) -> AgentDetailResponse:
        async with self._lock:
            agent = self._require_agent(agent_id)
            await self._submit_job_locked(agent, input_text, kind)
            return await self.get_agent(agent_id)

    async def _submit_job_locked(self, agent: AgentRecord, input_text: str, kind: JobKind) -> JobRecord:
        allowed_states = {AgentState.IDLE}
        if not agent.launch_profile:
            allowed_states = {AgentState.IDLE, AgentState.RUNNING}
        if agent.state not in allowed_states:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent is not ready to receive work")

        handle = self._handles.get(agent.id)
        if handle is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent handle is unavailable")
        if agent.launch_profile and handle.active_job_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent is already running a task")

        job = self._create_job(agent_id=agent.id, kind=kind, input_text=input_text)
        agent.state = AgentState.RUNNING
        agent.current_task = input_text
        agent.current_job_id = job.id
        agent.updated_at = datetime.now(UTC)
        handle.active_job_id = job.id
        await self._executor_for(agent).prompt(handle, input_text)
        await self._append_audit(
            action="submit_job",
            target_type="job",
            target_id=job.id,
            status=AuditStatus.ACCEPTED,
            message=f"{kind.value} accepted by supervisor",
            details={"agent_id": agent.id},
        )
        await self._publish("job.accepted", agent=agent, job=job, message=f"{kind.value} accepted")
        if not agent.launch_profile:
            self._job_tasks[job.id] = asyncio.create_task(self._run_job(agent.id, job.id, input_text))
        return job

    async def _schedule_pending_agents(self) -> None:
        while self._pending_queue and self._has_available_worker_slot():
            agent_id = self._pending_queue.popleft()
            agent = self._agents.get(agent_id)
            if agent is None or agent.state != AgentState.PENDING:
                continue
            if agent.launch_profile:
                await self._launch_process_agent(agent)
            else:
                await self._launch_mock_agent(agent)
        await self._refresh_machine()

    async def _launch_mock_agent(self, agent: AgentRecord) -> None:
        now = datetime.now(UTC)
        worker_id = self._allocate_worker_id()
        agent.state = AgentState.STARTING
        agent.worker_id = worker_id
        agent.started_at = now
        agent.updated_at = now
        handle = await self.mock_executor.start(agent_id=agent.id, agent_type=agent.type)
        self._handles[agent.id] = handle
        self._log_offsets[agent.id] = 0
        startup_job = self._jobs.get(agent.current_job_id) if agent.current_job_id else None
        if startup_job:
            startup_job.state = JobState.RUNNING
            startup_job.started_at = now
            startup_job.updated_at = now
        await self._publish("agent.starting", agent=agent, job=startup_job, message="Agent assigned to worker")
        asyncio.create_task(self._complete_mock_startup(agent.id))

    async def _complete_mock_startup(self, agent_id: str) -> None:
        await asyncio.sleep(0.5)
        async with self._lock:
            agent = self._require_agent(agent_id)
            handle = self._handles.get(agent_id)
            if handle is None or agent.state != AgentState.STARTING:
                return
            self.mock_executor.append_runtime_log(handle, "Mock agent boot completed and is ready for remote tasks")
            agent.state = AgentState.IDLE
            agent.updated_at = datetime.now(UTC)
            agent.recent_logs = self.mock_executor.recent_logs(handle, self.settings.default_log_limit)
            if agent.current_job_id:
                self._complete_job(agent.current_job_id, JobState.COMPLETED, "Agent started successfully")
            await self._publish_new_logs(agent.id)
            await self._publish("agent.idle", agent=agent, message="Agent is idle and ready")

    async def _complete_process_launch(self, agent_id: str) -> None:
        await asyncio.sleep(1)
        async with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None or agent.state != AgentState.STARTING:
                return
            handle = self._handles.get(agent_id)
            if handle is None:
                agent.state = AgentState.FAILED
                agent.updated_at = datetime.now(UTC)
                if agent.current_job_id:
                    self._complete_job(agent.current_job_id, JobState.FAILED, "Agent failed to start", error="Agent process was not available after launch")
                await self._publish("agent.failed", agent=agent, message="Agent process was not available after launch")
                return
            if handle.finished_at is not None:
                error_message = self._classify_launch_error(self._extract_runtime_error(handle), agent=agent)
                agent.state = AgentState.FAILED
                agent.updated_at = datetime.now(UTC)
                if agent.current_job_id:
                    self._complete_job(agent.current_job_id, JobState.FAILED, "Agent failed to start", error=error_message)
                await self._publish_new_logs(agent_id)
                await self._publish("agent.failed", agent=agent, message=error_message)
                self._handles.pop(agent_id, None)
                return
            initial_prompt = agent.current_task
            agent.state = AgentState.IDLE
            agent.updated_at = datetime.now(UTC)
            if agent.current_job_id:
                self._complete_job(agent.current_job_id, JobState.COMPLETED, "Agent process launched successfully")
            await self._publish_new_logs(agent_id)
            await self._publish("agent.idle", agent=agent, message="Agent process ready")
            if initial_prompt:
                try:
                    await self._submit_job_locked(agent, initial_prompt, JobKind.PROMPT)
                except HTTPException as exc:
                    await self._append_audit(
                        action="initial_prompt_failed",
                        target_type="agent",
                        target_id=agent.id,
                        status=AuditStatus.REJECTED,
                        message=str(exc.detail),
                    )

    async def _launch_process_agent(self, agent: AgentRecord, raise_on_failure: bool = False) -> None:
        launch_request = self._launch_request_from_agent(agent)
        launch_profile = str(launch_request.get("launch_profile") or agent.launch_profile or "")
        workspace = str(launch_request.get("workspace") or agent.workspace or "")
        initial_prompt = agent.current_task
        runtime_model, command_name = self._normalize_launch_options(
            launch_profile,
            str(launch_request.get("runtime_model") or agent.runtime_model or "") or None,
            str(launch_request.get("command_name") or agent.command_name or "") or None,
        )
        now = datetime.now(UTC)
        startup_job = self._jobs.get(agent.current_job_id) if agent.current_job_id else None
        if startup_job:
            startup_job.state = JobState.RUNNING
            startup_job.started_at = now
            startup_job.updated_at = now
        agent.state = AgentState.STARTING
        agent.worker_id = self._allocate_worker_id()
        agent.started_at = agent.started_at or now
        agent.updated_at = now
        try:
            handle = await self.runtime_executor.start(
                agent_id=agent.id,
                agent_type=agent.type,
                workspace=workspace,
                launch_profile=launch_profile,
                initial_prompt=initial_prompt,
                runtime_model=runtime_model,
                command_name=command_name,
            )
        except Exception as exc:
            agent.state = AgentState.FAILED
            agent.worker_id = None
            agent.updated_at = datetime.now(UTC)
            error_message = self._classify_launch_error(str(exc), launch_profile=launch_profile)
            if startup_job:
                self._complete_job(startup_job.id, JobState.FAILED, "Launch failed", error=error_message)
            await self._append_audit(
                action="launch_agent",
                target_type="agent",
                target_id=agent.id,
                status=AuditStatus.REJECTED,
                message=error_message,
                details={"launch_profile": launch_profile, "workspace": workspace},
            )
            await self._publish("agent.failed", agent=agent, job=startup_job, message=error_message)
            if raise_on_failure:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_message) from exc
            return

        agent.pid = handle.pid
        agent.runtime_model = runtime_model
        agent.command_name = command_name
        agent.mcp_enabled = bool(self._profile_metadata(launch_profile).get("mcp_enabled", False))
        agent.mcp_servers = self._mcp_server_names(workspace)
        agent.metadata.update(handle.metadata)
        agent.recent_logs = self.runtime_executor.recent_logs(handle, self.settings.default_log_limit)
        self._handles[agent.id] = handle
        self._log_offsets[agent.id] = len(handle.logs)
        self._process_monitors[agent.id] = asyncio.create_task(self._monitor_process(agent.id))
        await self._publish("agent.starting", agent=agent, job=startup_job, message="Agent process launched")
        asyncio.create_task(self._complete_process_launch(agent.id))

    async def _run_job(self, agent_id: str, job_id: str, input_text: str) -> None:
        try:
            async with self._lock:
                job = self._require_job(job_id)
                job.state = JobState.RUNNING
                job.started_at = datetime.now(UTC)
                job.updated_at = job.started_at
                await self._publish("job.running", agent=self._agents[agent_id], job=job, message="Job started")

            for step in range(1, self.settings.mock_job_steps + 1):
                await asyncio.sleep(self.settings.mock_job_step_delay_ms / 1000)
                async with self._lock:
                    handle = self._handles.get(agent_id)
                    agent = self._agents.get(agent_id)
                    if handle is None or agent is None or agent.state in {AgentState.STOPPING, AgentState.STOPPED, AgentState.FAILED}:
                        return
                    self._executor_for(agent).append_runtime_log(handle, f"Processing '{input_text}' step {step}/{self.settings.mock_job_steps}")
                    agent.recent_logs = self._executor_for(agent).recent_logs(handle, self.settings.default_log_limit)
                    agent.updated_at = datetime.now(UTC)
                    await self._publish_new_logs(agent_id)

            async with self._lock:
                agent = self._require_agent(agent_id)
                handle = self._handles.get(agent_id)
                if handle is not None:
                    self._executor_for(agent).append_runtime_log(handle, f"Finished processing '{input_text}'")
                    agent.recent_logs = self._executor_for(agent).recent_logs(handle, self.settings.default_log_limit)
                agent.state = AgentState.IDLE
                agent.current_task = None
                agent.updated_at = datetime.now(UTC)
                self._complete_job(job_id, JobState.COMPLETED, "Execution completed")
                await self._publish_new_logs(agent_id)
                await self._publish("job.completed", agent=agent, job=self._jobs[job_id], message="Job completed")
                await self._refresh_machine()
        except Exception as exc:
            async with self._lock:
                agent = self._require_agent(agent_id)
                agent.state = AgentState.FAILED
                agent.updated_at = datetime.now(UTC)
                self._complete_job(job_id, JobState.FAILED, "Execution failed", error=str(exc))
                await self._append_audit(
                    action="job_failed",
                    target_type="job",
                    target_id=job_id,
                    status=AuditStatus.REJECTED,
                    message=str(exc),
                )
                await self._publish("job.failed", agent=agent, job=self._jobs[job_id], message=str(exc))

    async def _finalize_stop(self, agent_id: str) -> None:
        agent = self._require_agent(agent_id)
        handle = self._handles.get(agent_id)
        if handle is not None:
            agent.recent_logs = self._executor_for(agent).recent_logs(handle, self.settings.default_log_limit)
        agent.state = AgentState.STOPPED
        agent.current_task = None
        agent.worker_id = None
        agent.pid = None
        agent.updated_at = datetime.now(UTC)
        if agent.current_job_id and self._jobs[agent.current_job_id].state == JobState.RUNNING:
            self._complete_job(agent.current_job_id, JobState.CANCELLED, "Agent stopped")
        await self._publish_new_logs(agent_id)
        self._handles.pop(agent_id, None)
        monitor = self._process_monitors.pop(agent_id, None)
        if monitor:
            monitor.cancel()
        await self._publish("agent.stopped", agent=agent, message="Agent stopped")
        await self._refresh_machine()
        await self._schedule_pending_agents()

    async def _monitor_process(self, agent_id: str) -> None:
        while True:
            await asyncio.sleep(0.5)
            async with self._lock:
                agent = self._agents.get(agent_id)
                handle = self._handles.get(agent_id)
                if agent is None or handle is None:
                    return
                await self._publish_new_logs(agent_id)
                agent.pid = handle.pid
                if handle.finished_at is not None and agent.state not in {AgentState.STOPPED, AgentState.FAILED}:
                    if agent.state == AgentState.STARTING:
                        agent.state = AgentState.FAILED
                    else:
                        agent.state = AgentState.STOPPED if (handle.exit_code or 0) == 0 else AgentState.FAILED
                    agent.pid = None
                    agent.worker_id = None
                    agent.current_task = None
                    agent.updated_at = datetime.now(UTC)
                    if agent.current_job_id and self._jobs[agent.current_job_id].state == JobState.RUNNING:
                        error_message = self._classify_launch_error(self._extract_runtime_error(handle), agent=agent)
                        self._complete_job(
                            agent.current_job_id,
                            JobState.COMPLETED if agent.state == AgentState.STOPPED else JobState.FAILED,
                            "Process exited",
                            error=None if agent.state == AgentState.STOPPED else error_message,
                        )
                    await self._publish(
                        "agent.stopped" if agent.state == AgentState.STOPPED else "agent.failed",
                        agent=agent,
                        message="Process exited cleanly" if agent.state == AgentState.STOPPED else self._classify_launch_error(self._extract_runtime_error(handle), agent=agent),
                    )
                    self._handles.pop(agent_id, None)
                    await self._schedule_pending_agents()
                    return

    def _create_job(self, agent_id: str, kind: JobKind, input_text: str) -> JobRecord:
        now = datetime.now(UTC)
        job = JobRecord(
            id=str(uuid4()),
            agent_id=agent_id,
            kind=kind,
            state=JobState.QUEUED,
            input_text=input_text,
            created_at=now,
            updated_at=now,
        )
        self._jobs[job.id] = job
        return job

    def _complete_job(self, job_id: str, state: JobState, summary: str, error: str | None = None) -> None:
        job = self._require_job(job_id)
        now = datetime.now(UTC)
        job.state = state
        job.updated_at = now
        job.finished_at = now
        if job.started_at is None:
            job.started_at = job.created_at
        job.summary = summary
        job.error = error

    def _allocate_worker_id(self) -> str:
        busy = {agent.worker_id for agent in self._agents.values() if agent.worker_id}
        for index in range(1, self.settings.mock_worker_capacity + 1):
            worker_id = f"worker-{index}"
            if worker_id not in busy:
                return worker_id
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No worker capacity available")

    def _remove_from_queue(self, agent_id: str) -> None:
        self._pending_queue = deque(item for item in self._pending_queue if item != agent_id)

    def _enforce_capacity(self) -> None:
        active = sum(1 for agent in self._agents.values() if agent.state in {AgentState.PENDING, AgentState.STARTING, AgentState.RUNNING, AgentState.IDLE, AgentState.STOPPING})
        if active >= self.settings.max_active_agents:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Maximum active agent limit reached on this machine")

    def _has_available_worker_slot(self) -> bool:
        busy = sum(
            1
            for agent in self._agents.values()
            if agent.worker_id and agent.state in {AgentState.STARTING, AgentState.RUNNING, AgentState.IDLE, AgentState.STOPPING}
        )
        return busy < self.settings.mock_worker_capacity

    def _build_launch_metadata(
        self,
        agent_type,
        launch_profile: str,
        workspace: str,
        initial_prompt: str | None,
        runtime_model: str | None = None,
        command_name: str | None = None,
    ) -> dict[str, object]:
        adapter_id = self.launch_profiles.get(launch_profile).adapter_id if self.launch_profiles.get(launch_profile) else ""
        return {
            "adapter_id": adapter_id,
            "launch_request": {
                "type": agent_type.value if hasattr(agent_type, "value") else str(agent_type),
                "launch_profile": launch_profile,
                "workspace": workspace,
                "initial_prompt_template": initial_prompt or "",
                "runtime_model": runtime_model or "",
                "command_name": command_name or "",
            }
        }

    def _normalize_launch_options(
        self,
        launch_profile: str | None,
        runtime_model: str | None,
        command_name: str | None,
    ) -> tuple[str | None, str | None]:
        profile = self.launch_profiles.get(launch_profile or "")
        adapter = self._runtime_adapters().get(profile.adapter_id) if profile else None
        normalized_model = (runtime_model or "").strip() or None
        normalized_command = (command_name or "").strip() or None
        if adapter is not None:
            if not adapter.capabilities.supports_model_selection:
                normalized_model = None
            if not adapter.capabilities.supports_command_templates:
                normalized_command = None
        return normalized_model, normalized_command

    def _sanitize_agent_runtime_metadata(self, agent: AgentRecord) -> None:
        normalized_model, normalized_command = self._normalize_launch_options(
            agent.launch_profile,
            agent.runtime_model,
            agent.command_name,
        )
        agent.runtime_model = normalized_model
        agent.command_name = normalized_command
        launch_request = self._launch_request_from_agent(agent)
        if launch_request:
            launch_request["runtime_model"] = normalized_model or ""
            launch_request["command_name"] = normalized_command or ""

    def _launch_request_from_agent(self, agent: AgentRecord) -> dict[str, object]:
        launch_request = agent.metadata.get("launch_request", {})
        return launch_request if isinstance(launch_request, dict) else {}

    def _recent_jobs_for_agent(self, agent_id: str, limit: int = 8) -> list[JobRecord]:
        jobs = [job for job in self._jobs.values() if job.agent_id == agent_id]
        return sorted(jobs, key=lambda item: item.updated_at, reverse=True)[:limit]

    def _profile_metadata(self, launch_profile: str | None) -> dict[str, object]:
        if not launch_profile:
            return {}
        profile = self.launch_profiles.get(launch_profile)
        return dict(profile.metadata) if profile else {}

    def _runtime_adapters(self) -> dict[str, object]:
        adapters = getattr(self.runtime_executor, "adapters", None)
        return adapters if isinstance(adapters, dict) else {}

    def _mcp_server_names(self, workspace: str | None) -> list[str]:
        names: set[str] = set()
        for adapter in self._runtime_adapters().values():
            if not adapter.capabilities.supports_mcp:
                continue
            for server in adapter.list_mcp_servers(workspace):
                names.add(server.name)
        return sorted(names)

    def start_background_tasks(self) -> None:
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop_background_tasks(self) -> None:
        if self._heartbeat_task is None:
            return
        self._heartbeat_task.cancel()
        try:
            await self._heartbeat_task
        except asyncio.CancelledError:
            pass
        self._heartbeat_task = None

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(self.settings.monitoring_heartbeat_interval_seconds)
            async with self._lock:
                self._last_heartbeat_at = datetime.now(UTC)
                machine_health = self._machine_health_status()
                await self._publish("machine.heartbeat", machine_health=machine_health, message="Supervisor heartbeat")
                for agent in self._agents.values():
                    status_snapshot = self._agent_runtime_status(agent)
                    previous = self._agent_monitor_state.get(agent.id)
                    self._agent_monitor_state[agent.id] = status_snapshot.monitor_state
                    if status_snapshot.stuck_indicator and previous != "stuck":
                        await self._publish("agent.stuck", agent=agent, agent_status=status_snapshot, message=status_snapshot.warning_message or "Agent appears stalled")
                    elif status_snapshot.warning_indicator and previous not in {"warning", "stuck"}:
                        await self._publish("agent.warning", agent=agent, agent_status=status_snapshot, message=status_snapshot.warning_message or "Agent needs attention")
                    elif previous in {"warning", "stuck"} and status_snapshot.monitor_state not in {"warning", "stuck"}:
                        await self._publish("agent.recovered", agent=agent, agent_status=status_snapshot, message="Agent recovered")

    def _machine_health_status(self) -> MachineHealthStatus:
        statuses = [self._agent_runtime_status(agent) for agent in self._agents.values()]
        warning_count = sum(1 for status in statuses if status.warning_indicator or status.stuck_indicator)
        failed_count = sum(1 for agent in self._agents.values() if agent.state == AgentState.FAILED)
        mcp_server_records = []
        for adapter in self._runtime_adapters().values():
            if adapter.capabilities.supports_mcp:
                mcp_server_records.extend(adapter.list_mcp_servers(None))
        adapter_warnings = []
        for adapter in self._runtime_adapters().values():
            adapter_warnings.extend(adapter.runtime_status().warnings)
        monitor_state = "healthy"
        if failed_count > 0:
            monitor_state = "warning"
        if any(status.stuck_indicator for status in statuses):
            monitor_state = "warning"
        return MachineHealthStatus(
            machine_id=self.machine.id,
            machine_name=self.machine.name,
            status=self.machine.status,
            monitor_state=monitor_state,
            last_heartbeat=self._last_heartbeat_at,
            last_seen=self.machine.updated_at,
            agents_total=len(self._agents),
            agents_running=sum(1 for agent in self._agents.values() if agent.state in {AgentState.RUNNING, AgentState.IDLE}),
            agents_failed=failed_count,
            queued_jobs=sum(1 for job in self._jobs.values() if job.state == JobState.QUEUED),
            warning_count=warning_count,
            worker_pool=self.machine.worker_pool,
            resources=self._machine_resource_usage(),
            mcp_server_count=len(mcp_server_records),
            mcp_healthy_count=sum(1 for server in mcp_server_records if server.health == "healthy"),
            adapter_warnings=adapter_warnings,
        )

    def _agent_runtime_status(self, agent: AgentRecord) -> AgentRuntimeStatus:
        now = datetime.now(UTC)
        handle = self._handles.get(agent.id)
        last_heartbeat = self._coerce_datetime(agent.metadata.get("last_heartbeat_at")) or agent.updated_at
        last_log_timestamp = None
        if agent.recent_logs:
            last_log_timestamp = agent.recent_logs[-1].timestamp
        elif handle and handle.logs:
            last_log_timestamp = handle.logs[-1].timestamp
        elapsed_seconds = int((now - (agent.started_at or agent.updated_at)).total_seconds()) if (agent.started_at or agent.updated_at) else 0
        silence_seconds = int((now - last_log_timestamp).total_seconds()) if last_log_timestamp else None
        heartbeat_age_seconds = int((now - last_heartbeat).total_seconds()) if last_heartbeat else None
        warning_indicator = False
        stuck_indicator = False
        warning_message = None
        monitor_state = agent.state.value
        if agent.state == AgentState.FAILED:
            monitor_state = "failed"
        elif agent.state == AgentState.RUNNING:
            if silence_seconds is not None and silence_seconds >= self.settings.monitoring_stuck_after_seconds:
                stuck_indicator = True
                warning_indicator = True
                monitor_state = "stuck"
                warning_message = f"No logs for {silence_seconds}s while task is running"
            elif silence_seconds is not None and silence_seconds >= self.settings.monitoring_warning_after_seconds:
                warning_indicator = True
                monitor_state = "warning"
                warning_message = f"No logs for {silence_seconds}s while task is running"
            elif heartbeat_age_seconds is not None and heartbeat_age_seconds >= self.settings.monitoring_warning_after_seconds:
                warning_indicator = True
                monitor_state = "warning"
                warning_message = f"No supervisor heartbeat for {heartbeat_age_seconds}s"
            else:
                monitor_state = "running"
        elif agent.state == AgentState.IDLE:
            monitor_state = "idle"
        resources = self._resource_usage(handle)
        return AgentRuntimeStatus(
            agent_id=agent.id,
            machine_id=self.machine.id,
            machine_name=self.machine.name,
            type=agent.type,
            state=agent.state,
            monitor_state=monitor_state,
            elapsed_seconds=elapsed_seconds,
            last_heartbeat=last_heartbeat,
            last_log_timestamp=last_log_timestamp,
            warning_indicator=warning_indicator,
            stuck_indicator=stuck_indicator,
            warning_message=warning_message,
            current_task=agent.current_task,
            workspace=agent.workspace,
            launch_profile=agent.launch_profile,
            runtime_model=agent.runtime_model,
            command_name=agent.command_name,
            last_output_at=agent.last_output_at,
            mcp_enabled=agent.mcp_enabled,
            mcp_servers=agent.mcp_servers,
            pid=agent.pid,
            recent_logs=agent.recent_logs[-10:],
            resources=resources,
        )

    def _resource_usage(self, handle: ProcessHandle | None):
        from app.models import ResourceUsage

        if handle is None or handle.pid is None or psutil is None:
            return ResourceUsage()
        try:
            process = psutil.Process(handle.pid)
            return ResourceUsage(
                cpu_percent=process.cpu_percent(interval=0.0),
                memory_mb=round(process.memory_info().rss / (1024 * 1024), 2),
            )
        except Exception:
            return ResourceUsage()

    def _machine_resource_usage(self):
        from app.models import ResourceUsage

        if psutil is None:
            return ResourceUsage()
        try:
            return ResourceUsage(
                cpu_percent=psutil.cpu_percent(interval=0.0),
                memory_mb=round(psutil.virtual_memory().used / (1024 * 1024), 2),
            )
        except Exception:
            return ResourceUsage()

    @staticmethod
    def _coerce_datetime(value: object) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    def _validate_workspace(self, workspace: str) -> Path:
        path = Path(workspace).expanduser().resolve()
        if not path.exists() or not path.is_dir():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace does not exist or is not a directory")
        if self.settings.allowed_workspace_roots:
            allowed = [Path(root).expanduser().resolve() for root in self.settings.allowed_workspace_roots]
            if not any(path == root or root in path.parents for root in allowed):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace is outside allowed roots")
        return path

    def _workspace_roots(self) -> list[Path]:
        roots = [Path(root).expanduser().resolve() for root in self.settings.allowed_workspace_roots if root.strip()]
        if not roots:
            roots = [Path(workspace).expanduser().resolve() for workspace in self.settings.configured_workspaces if workspace.strip()]
        return [root for root in roots if root.exists() and root.is_dir()]

    def _discover_workspaces(self, root: Path) -> list[Path]:
        candidates = [root]
        max_depth = max(self.settings.workspace_discovery_depth, 0)
        if max_depth > 0:
            queue: deque[tuple[Path, int]] = deque([(root, 0)])
            while queue:
                current, depth = queue.popleft()
                if depth >= max_depth:
                    continue
                try:
                    children = list(current.iterdir())
                except OSError:
                    continue
                for child in children:
                    if not child.is_dir():
                        continue
                    if (child / ".git").exists():
                        candidates.append(child)
                    queue.append((child, depth + 1))
        unique: dict[str, Path] = {}
        for candidate in candidates:
            try:
                validated = self._validate_workspace(str(candidate))
            except HTTPException:
                continue
            unique[str(validated)] = validated
        return list(unique.values())

    def _restore_state(self) -> None:
        persisted = self.state_store.load()
        if persisted is None:
            return
        self.machine = persisted.machine
        now = datetime.now(UTC)
        self.machine.status = "online"
        self.machine.updated_at = now
        self._agents = {agent.id: agent for agent in persisted.agents}
        self._jobs = {job.id: job for job in persisted.jobs}
        self._audits = persisted.audits[-self.settings.max_log_entries :]
        for agent in self._agents.values():
            if agent.state in {AgentState.PENDING, AgentState.STARTING, AgentState.RUNNING, AgentState.IDLE, AgentState.STOPPING}:
                agent.state = AgentState.STOPPED
                agent.pid = None
                agent.worker_id = None
                agent.current_task = None
                agent.updated_at = now
        for job in self._jobs.values():
            if job.state in {JobState.QUEUED, JobState.RUNNING}:
                job.state = JobState.FAILED
                job.error = "Supervisor restarted before the task completed"
                job.summary = "Interrupted by supervisor restart"
                job.updated_at = now
                job.finished_at = now
                if job.started_at is None:
                    job.started_at = job.created_at

    async def _persist_state_locked(self) -> None:
        self.state_store.save(
            PersistedState(
                machine=self.machine,
                agents=list(self._agents.values()),
                jobs=list(self._jobs.values()),
                audits=self._audits[-self.settings.max_log_entries :],
            )
        )

    @staticmethod
    def _extract_runtime_error(handle: ProcessHandle) -> str:
        error_logs = [log.message for log in handle.logs if log.stream in {"stderr", "system", "stdout"} and log.message.strip()]
        return error_logs[-1] if error_logs else f"Process exited with code {handle.exit_code}"

    def _classify_launch_error(self, message: str, *, launch_profile: str | None = None, agent: AgentRecord | None = None) -> str:
        lowered = message.lower()
        adapter = None
        adapter_id = None
        if agent is not None:
            launch_request = agent.metadata.get("launch_request")
            adapter_from_request = launch_request.get("adapter_id") if isinstance(launch_request, dict) else None
            adapter_id = str(agent.metadata.get("adapter_id") or adapter_from_request or "")
            if not adapter_id and agent.launch_profile:
                adapter_id = self.launch_profiles.get(agent.launch_profile).adapter_id if self.launch_profiles.get(agent.launch_profile) else None
        if not adapter_id and launch_profile:
            adapter_id = self.launch_profiles.get(launch_profile).adapter_id if self.launch_profiles.get(launch_profile) else None
        if adapter_id:
            adapter = self._runtime_adapters().get(adapter_id)
        if adapter is not None:
            classified = adapter.classify_runtime_error(message)
            if classified != message:
                return classified
        if "not installed" in lowered or "not found on path" in lowered or "cli was not found" in lowered:
            return message
        if "workspace does not exist" in lowered or "not a directory" in lowered:
            return "Invalid workspace: the selected directory does not exist or is not accessible"
        if "outside allowed roots" in lowered:
            return "Invalid workspace: the selected directory is outside the configured safe workspace roots"
        if "429" in lowered or "too many requests" in lowered or "resource_exhausted" in lowered or "quota exceeded" in lowered:
            return "Gemini CLI hit a rate limit or quota limit. Retry shortly or switch auth/billing configuration."
        if "must specify the gemini_api_key" in lowered or "local auth is missing" in lowered:
            return "Gemini local auth is missing. Run gemini locally once or set GEMINI_API_KEY before starting the supervisor"
        if "authentication" in lowered or "auth missing" in lowered or "auth expired" in lowered or "login required" in lowered:
            return "Local CLI authentication is missing or expired on this machine"
        if "maximum active agent limit reached" in lowered:
            return "Maximum active agent limit reached on this machine"
        if "no worker capacity available" in lowered:
            return "No worker capacity available on this machine"
        if "exit code" in lowered:
            return f"Agent process exited immediately: {message}"
        return message

    async def _refresh_machine(self) -> None:
        busy_workers = sum(
            1
            for agent in self._agents.values()
            if agent.worker_id and agent.state in {AgentState.STARTING, AgentState.RUNNING, AgentState.IDLE, AgentState.STOPPING}
        )
        self.machine.worker_pool = WorkerPoolState(
            desired_workers=self.settings.mock_worker_capacity,
            busy_workers=busy_workers,
            idle_workers=max(self.settings.mock_worker_capacity - busy_workers, 0),
            queue_depth=len(self._pending_queue),
            supports_pause_resume=False,
        )
        self.machine.updated_at = datetime.now(UTC)

    async def _publish_new_logs(self, agent_id: str) -> None:
        handle = self._handles.get(agent_id)
        if handle is None:
            return
        start = self._log_offsets.get(agent_id, 0)
        new_logs = handle.logs[start:]
        if not new_logs:
            return
        self._log_offsets[agent_id] = len(handle.logs)
        agent = self._agents[agent_id]
        for log in new_logs:
            if await self._handle_internal_event(agent, handle, log):
                continue
            agent.recent_logs = (agent.recent_logs + [log])[-self.settings.default_log_limit :]
            await self._publish("agent.log", agent=agent, log=log, message=log.message)

    async def _handle_internal_event(self, agent: AgentRecord, handle: ProcessHandle, log) -> bool:
        if log.stream != "stdout" or not log.message.startswith(EVENT_PREFIX):
            return False
        try:
            payload = json.loads(log.message.removeprefix(EVENT_PREFIX))
        except json.JSONDecodeError:
            return False

        event_name = str(payload.get("event", ""))
        job_id = payload.get("job_id")
        if not job_id or job_id not in self._jobs:
            return True

        job = self._jobs[job_id]
        now = datetime.now(UTC)
        if event_name == "job.started":
            job.state = JobState.RUNNING
            job.started_at = now
            job.updated_at = now
            agent.state = AgentState.RUNNING
            agent.current_job_id = job.id
            agent.current_task = job.input_text
            agent.updated_at = now
            await self._publish("job.running", agent=agent, job=job, message="Job started")
            return True

        summary = str(payload.get("summary") or "").strip() or None
        error = str(payload.get("error") or "").strip() or None
        if event_name == "job.completed":
            self._complete_job(job.id, JobState.COMPLETED, summary or "Execution completed")
            handle.active_job_id = None
            agent.state = AgentState.IDLE
            agent.current_task = None
            agent.current_job_id = job.id
            agent.updated_at = datetime.now(UTC)
            agent.last_output_at = agent.updated_at
            await self._publish("job.completed", agent=agent, job=job, message=summary or "Job completed")
            return True

        if event_name == "job.failed":
            runtime_error = self._classify_launch_error(error or summary or "Execution failed", agent=agent)
            self._complete_job(job.id, JobState.FAILED, summary or "Execution failed", error=runtime_error)
            handle.active_job_id = None
            agent.state = AgentState.IDLE
            agent.current_task = None
            agent.current_job_id = job.id
            agent.updated_at = datetime.now(UTC)
            agent.last_output_at = agent.updated_at
            await self._publish("job.failed", agent=agent, job=job, message=runtime_error or summary or "Job failed")
            return True
        return True

    async def _append_audit(
        self,
        action: str,
        target_type: str,
        target_id: str,
        status: AuditStatus,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        entry = AuditEntry(
            id=str(uuid4()),
            timestamp=datetime.now(UTC),
            action=action,
            target_type=target_type,
            target_id=target_id,
            status=status,
            message=message,
            details=details or {},
        )
        self._audits.append(entry)
        if len(self._audits) > self.settings.max_log_entries:
            del self._audits[0 : len(self._audits) - self.settings.max_log_entries]
        await self._publish("audit.recorded", audit=entry, message=message)

    async def _publish(
        self,
        event: str,
        agent: AgentRecord | None = None,
        agent_status: AgentRuntimeStatus | None = None,
        job: JobRecord | None = None,
        log=None,
        audit: AuditEntry | None = None,
        machine_health: MachineHealthStatus | None = None,
        message: str | None = None,
    ) -> None:
        await self._refresh_machine()
        await self._persist_state_locked()
        timestamp = datetime.now(UTC)
        if agent is not None:
            agent.metadata["last_heartbeat_at"] = timestamp.isoformat()
            agent_status = agent_status or self._agent_runtime_status(agent)
        machine_health = machine_health or self._machine_health_status()
        emitted = SupervisorEvent(
            event=event,
            timestamp=timestamp,
            machine=self.machine,
            machine_health=machine_health,
            agent=agent,
            agent_status=agent_status,
            job=job,
            log=log,
            audit=audit,
            message=message,
        )
        self._event_history.append(emitted)
        if agent is not None:
            history = self._agent_event_history.setdefault(agent.id, deque(maxlen=self.settings.max_log_entries))
            history.append(emitted)
        await self.event_bus.publish(emitted)

    def _executor_for(self, agent: AgentRecord):
        return self.runtime_executor if agent.launch_profile else self.mock_executor

    def _require_agent(self, agent_id: str) -> AgentRecord:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        return agent

    def _require_job(self, job_id: str) -> JobRecord:
        job = self._jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return job

    def _require_runtime_adapter(self, adapter_id: str):
        adapter = self._runtime_adapters().get(adapter_id)
        if adapter is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Runtime adapter not found")
        return adapter
