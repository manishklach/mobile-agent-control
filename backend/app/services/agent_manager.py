from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status

LAUNCH_TRANSITION_DELAY_SECONDS = 2.5

from app.core.config import AppSettings, LaunchProfileConfig
from app.executors.base import ProcessHandle
from app.executors.cli_runtime_executor import CliRuntimeExecutor
from app.executors.mock_executor import MockExecutor
from app.models import (
    AgentDetailResponse,
    AgentEventsResponse,
    AgentEvent,
    AgentListResponse,
    AgentMetricsResponse,
    AgentOverviewListResponse,
    AgentOverviewRecord,
    AgentRecord,
    AgentRuntimeStatus,
    AgentState,
    AgentStateResponse,
    AgentStateSnapshot,
    AgentTimelineResponse,
    ApprovalActionType,
    ApprovalDecisionResponse,
    ApprovalListResponse,
    ApprovalRequest,
    ApprovalStatus,
    AuditEntry,
    AuditLogResponse,
    AuditStatus,
    CreateTaskRequest,
    DiagnosisResponse,
    EventType,
    HealthResponse,
    JobKind,
    JobListResponse,
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
    OrchestrationTask,
    PromptAgentRequest,
    ReplayAgentRequest,
    RestartAgentRequest,
    RestartMachineResponse,
    RuntimeAdapterRecord,
    RuntimeAdapterStatusResponse,
    RuntimeAdaptersResponse,
    RunningAgentsResponse,
    SlashCommandsResponse,
    StartAgentRequest,
    SupervisorAgentState,
    SubmitTaskRequest,
    SupervisorEvent,
    TaskDetailResponse,
    TaskListResponse,
    TaskStatus,
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
        self._diagnoses: dict[str, DiagnosisResponse] = {}
        self._jobs: dict[str, JobRecord] = {}
        self._handles: dict[str, ProcessHandle] = {}
        self._audits: list[AuditEntry] = []
        self._timeline_events: dict[str, deque[AgentEvent]] = {}
        self._approvals: dict[str, ApprovalRequest] = {}
        self._tasks: dict[str, OrchestrationTask] = {}
        self._pending_queue: deque[str] = deque()
        self._job_tasks: dict[str, asyncio.Task[None]] = {}
        self._process_monitors: dict[str, asyncio.Task[None]] = {}
        self._log_offsets: dict[str, int] = {}
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._scheduler_task: asyncio.Task[None] | None = None
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
            agents_running=sum(1 for agent in self._agents.values() if agent.state in {SupervisorAgentState.RUNNING, SupervisorAgentState.IDLE}),
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
            active_agents=sum(1 for agent in self._agents.values() if agent.state in {SupervisorAgentState.RUNNING, SupervisorAgentState.IDLE, SupervisorAgentState.STARTING}),
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
        active_states = {SupervisorAgentState.RUNNING, SupervisorAgentState.IDLE, SupervisorAgentState.STARTING, SupervisorAgentState.PENDING, SupervisorAgentState.STOPPING}
        statuses = [
            self._agent_runtime_status(agent)
            for agent in self._agents.values()
            if agent.state in active_states
        ]
        return RunningAgentsResponse(agents=sorted(statuses, key=lambda item: (item.monitor_state, -item.elapsed_seconds)))

    async def agent_overviews(self, limit: int = 100) -> AgentOverviewListResponse:
        await self._refresh_machine()
        records = []
        for agent in self._agents.values():
            self._sanitize_agent_runtime_metadata(agent)
            current_job = self._jobs.get(agent.current_job_id) if agent.current_job_id else None
            recent_jobs = self._recent_jobs_for_agent(agent.id)
            latest_completed_job = next(
                (job for job in recent_jobs if job.state in {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}),
                None,
            )
            records.append(
                AgentOverviewRecord(
                    agent=agent,
                    status=self._agent_runtime_status(agent),
                    current_job=current_job,
                    latest_completed_job=latest_completed_job,
                )
            )
        records.sort(
            key=lambda item: (
                self._overview_priority(item),
                -(item.status.elapsed_seconds or 0),
                item.agent.updated_at,
            ),
            reverse=False,
        )
        return AgentOverviewListResponse(agents=records[:limit])

    async def get_agent(self, agent_id: str) -> AgentDetailResponse:
        agent = self._require_agent(agent_id)
        self._sanitize_agent_runtime_metadata(agent)
        current_job = self._jobs.get(agent.current_job_id) if agent.current_job_id else None
        recent_jobs = self._recent_jobs_for_agent(agent_id)
        latest_completed_job = next(
            (job for job in recent_jobs if job.state in {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}),
            None,
        )
        return AgentDetailResponse(
            agent=agent,
            current_job=current_job,
            latest_completed_job=latest_completed_job,
            recent_jobs=recent_jobs,
            latest_diagnosis=self._diagnoses.get(agent_id),
        )

    async def get_agent_state(self, agent_id: str) -> AgentStateResponse:
        agent = self._require_agent(agent_id)
        return AgentStateResponse(agent_id=agent_id, state=self._agent_state_snapshot(agent))

    async def get_agent_timeline(self, agent_id: str, limit: int = 100) -> AgentTimelineResponse:
        self._require_agent(agent_id)
        timeline = list(self._timeline_events.get(agent_id, deque()))
        timeline.sort(key=lambda item: item.timestamp)
        return AgentTimelineResponse(agent_id=agent_id, events=timeline[-limit:])

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
        agent_id = str(uuid4())
        try:
            now = datetime.now(UTC)
            
            async with self._lock:
                self._enforce_capacity()
                startup_job = self._create_job(agent_id=agent_id, kind=JobKind.STARTUP, input_text=request.initial_task or "start agent")
                agent = AgentRecord(
                    id=agent_id,
                    name=self._default_agent_name(request.type, agent_id),
                    type=request.type,
                    state=SupervisorAgentState.PENDING,
                    current_state=AgentState.IDLE,
                    progress=0,
                    current_step="Queued for startup",
                    last_updated_ts=now,
                    error_message=None,
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
        except Exception as exc:
            error_msg = str(exc.detail) if isinstance(exc, HTTPException) else str(exc)
            await self._append_audit(
                action="start_agent",
                target_type="agent",
                target_id=agent_id,
                status=AuditStatus.REJECTED,
                message=error_msg,
            )
            raise

    async def launch_agent(self, request: LaunchAgentRequest) -> AgentDetailResponse:
        agent_id = str(uuid4())
        try:
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
            async with self._lock:
                self._enforce_capacity()
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
                    name=self._default_agent_name(request.type, agent_id),
                    type=request.type,
                    state=SupervisorAgentState.PENDING,
                    current_state=AgentState.IDLE,
                    progress=0,
                    current_step="Queued for launch",
                    last_updated_ts=now,
                    error_message=None,
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
                    message="Launch command accepted by supervisor",
                    details={
                        "launch_profile": request.launch_profile,
                        "workspace": str(workspace),
                        "runtime_model": runtime_model,
                        "command_name": command_name,
                    },
                )
                self._pending_queue.append(agent_id)
            
            # This handles capacity and worker slots
            await self._schedule_pending_agents()
            return await self.get_agent(agent_id)
        except Exception as exc:
            error_msg = str(exc.detail) if isinstance(exc, HTTPException) else str(exc)
            await self._append_audit(
                action="launch_agent",
                target_type="agent",
                target_id=agent_id,
                status=AuditStatus.REJECTED,
                message=error_msg,
            )
            raise

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
            if agent.state == SupervisorAgentState.PENDING:
                self._remove_from_queue(agent_id)
                agent.state = SupervisorAgentState.STOPPED
                agent.updated_at = datetime.now(UTC)
                if agent.current_job_id:
                    self._complete_job(agent.current_job_id, JobState.CANCELLED, "Agent start cancelled before launch")
                await self._publish("agent.stopped", agent=agent, message="Pending agent cancelled")
                await self._refresh_machine()
                return await self.get_agent(agent_id)

            handle = self._handles.get(agent_id)
            if handle is None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent is not active")

            agent.state = SupervisorAgentState.STOPPING
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
            if agent.state in {SupervisorAgentState.RUNNING, SupervisorAgentState.IDLE, SupervisorAgentState.STARTING, SupervisorAgentState.STOPPING}:
                handle = self._handles.get(agent_id)
                if handle is not None:
                    await self._executor_for(agent).stop(handle)
                await self._finalize_stop(agent_id)

            restart_job = self._create_job(agent_id=agent_id, kind=JobKind.RESTART, input_text=request.reason or "restart agent")
            if relaunch_profile and relaunch_workspace:
                agent.state = SupervisorAgentState.PENDING
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
                agent.state = SupervisorAgentState.PENDING
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

    async def diagnose_agent(self, agent_id: str) -> DiagnosisResponse:
        async with self._lock:
            agent = self._require_agent(agent_id)
            handle = self._handles.get(agent_id)
            logs = []
            if handle:
                logs = self._executor_for(agent).recent_logs(handle, 20)
            else:
                logs = agent.recent_logs[-20:]

            is_failed = agent.state == SupervisorAgentState.FAILED
            cause = None
            suggestion = None

            if is_failed and logs:
                cause, suggestion = await self._diagnose_logs_with_gemini(agent, logs)
            elif not is_failed:
                cause = "Agent is not in a failed state"
                suggestion = "No diagnosis needed"
            else:
                cause = "No logs available for analysis"
                suggestion = "Try restarting the agent"

            diagnosis = DiagnosisResponse(
                agent_id=agent_id,
                is_failed=is_failed,
                cause=cause,
                suggestion=suggestion,
                logs_analyzed=len(logs),
                timestamp=datetime.now(UTC),
            )
            self._diagnoses[agent_id] = diagnosis
            return diagnosis

    async def _diagnose_logs_with_gemini(self, agent: AgentRecord, logs: list[LogEntry]) -> tuple[str, str]:
        """
        Uses a separate Gemini process to analyze the failure logs of another agent.
        """
        log_text = "\n".join([f"[{log.stream}] {log.message}" for log in logs])
        prompt = (
            f"Analyze these failure logs for a coding agent of type '{agent.type.value}'.\n"
            f"Context: Workspace is {agent.workspace}, Profile is {agent.launch_profile}.\n\n"
            f"LOGS:\n{log_text}\n\n"
            "Identify the root cause of the failure and suggest a concrete fix.\n"
            "Format your response as a JSON object with 'cause' and 'suggestion' keys. "
            "Keep it concise for a mobile screen."
        )

        adapter = self.runtime_executor.adapters.get("gemini-cli")
        if not adapter or not agent.workspace:
            return "Unable to run Gemini diagnostic adapter", "Check machine logs manually"

        try:
            # We run a one-off prompt using the Gemini adapter to analyze the logs
            exit_code, output = await asyncio.to_thread(
                adapter.run_prompt,
                prompt=prompt,
                workspace=agent.workspace,
            )
            if exit_code == 0:
                try:
                    import json
                    # Try to find a JSON block in the output
                    start = output.find("{")
                    end = output.rfind("}")
                    if start >= 0 and end >= 0:
                        data = json.loads(output[start:end+1])
                        return str(data.get("cause", "Unknown")), str(data.get("suggestion", "No suggestion available"))
                except Exception:
                    pass
                return "Diagnostic completed", output[:200]
            return f"Diagnostic failed (Exit code {exit_code})", output[:200]
        except Exception as exc:
            return "Diagnostic tool crashed", str(exc)

    async def get_audit_log(self, limit: int = 100) -> AuditLogResponse:
        return AuditLogResponse(entries=self._audits[-limit:])

    async def list_tasks(self, limit: int = 100) -> TaskListResponse:
        tasks = sorted(self._tasks.values(), key=lambda task: task.updated_at, reverse=True)
        return TaskListResponse(tasks=tasks[:limit])

    async def get_task(self, task_id: str) -> TaskDetailResponse:
        task = self._tasks.get(task_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return TaskDetailResponse(task=task)

    async def list_jobs(self, limit: int = 100) -> JobListResponse:
        jobs = sorted(self._jobs.values(), key=lambda job: job.updated_at, reverse=True)
        return JobListResponse(jobs=jobs[:limit])

    async def get_job(self, job_id: str) -> JobRecord:
        return self._require_job(job_id)

    async def create_task(self, request: CreateTaskRequest) -> TaskDetailResponse:
        now = datetime.now(UTC)
        task = OrchestrationTask(
            id=str(uuid4()),
            name=request.name,
            assigned_agent=request.assigned_agent,
            status=TaskStatus.BLOCKED if request.dependencies else TaskStatus.PENDING,
            dependencies=request.dependencies,
            prompt_template=request.prompt_template,
            created_at=now,
            updated_at=now,
        )
        self._tasks[task.id] = task
        await self._append_audit(
            action="create_task",
            target_type="task",
            target_id=task.id,
            status=AuditStatus.ACCEPTED,
            message=f"Task '{task.name}' created",
            details={"assigned_agent": request.assigned_agent, "dependencies": request.dependencies},
        )
        await self._publish("task.created", task=task, message=f"Task '{task.name}' queued")
        return TaskDetailResponse(task=task)

    async def list_approvals(self) -> ApprovalListResponse:
        approvals = sorted(self._approvals.values(), key=lambda item: item.created_at, reverse=True)
        return ApprovalListResponse(approvals=approvals)

    async def approve_request(self, approval_id: str) -> ApprovalDecisionResponse:
        approval = self._require_approval(approval_id)
        approval.status = ApprovalStatus.APPROVED
        approval.decided_at = datetime.now(UTC)
        await self._append_audit(
            action="approval_approved",
            target_type="approval",
            target_id=approval.id,
            status=AuditStatus.COMPLETED,
            message=f"Approval {approval.id} approved",
            details={"agent_id": approval.agent_id, "action_type": approval.action_type.value},
        )
        await self._publish("approval.approved", approval=approval, message="Approval granted")
        await self._resume_agent_after_approval(approval)
        return ApprovalDecisionResponse(approval=approval)

    async def reject_request(self, approval_id: str) -> ApprovalDecisionResponse:
        approval = self._require_approval(approval_id)
        approval.status = ApprovalStatus.REJECTED
        approval.decided_at = datetime.now(UTC)
        agent = self._require_agent(approval.agent_id)
        job_id = str(approval.payload.get("job_id") or "")
        job = self._jobs.get(job_id) if job_id else None
        self._update_agent_execution_state(
            agent,
            current_state=AgentState.BLOCKED,
            progress=agent.progress,
            current_step="Approval rejected",
            error_message=f"{approval.action_type.value} rejected by operator",
        )
        if job is not None and job.state == JobState.QUEUED:
            self._complete_job(
                job.id,
                JobState.FAILED,
                "Approval rejected",
                error=f"{approval.action_type.value} rejected by operator",
            )
        await self._append_audit(
            action="approval_rejected",
            target_type="approval",
            target_id=approval.id,
            status=AuditStatus.REJECTED,
            message=f"Approval {approval.id} rejected",
            details={"agent_id": approval.agent_id, "action_type": approval.action_type.value},
        )
        if job is not None:
            await self._publish("job.failed", agent=agent, job=job, approval=approval, message="Approval rejected")
        await self._publish("approval.rejected", agent=agent, approval=approval, message="Approval rejected")
        return ApprovalDecisionResponse(approval=approval)

    async def replay_agent(self, agent_id: str, request: ReplayAgentRequest) -> AgentDetailResponse:
        agent = self._require_agent(agent_id)
        recent_jobs = self._recent_jobs_for_agent(agent_id)
        failed_job = next((job for job in recent_jobs if job.state == JobState.FAILED), None)
        base_prompt = failed_job.input_text if failed_job else (agent.current_task or "retry last action")
        replay_prompt = base_prompt if not request.instruction else f"{base_prompt}\n\nFix instruction: {request.instruction}"
        await self._append_audit(
            action="replay_agent",
            target_type="agent",
            target_id=agent_id,
            status=AuditStatus.ACCEPTED,
            message="Replay requested",
            details={"instruction": request.instruction},
        )
        await self._record_timeline_event(agent_id, EventType.USER_ACTION, {"action": "replay", "instruction": request.instruction})
        return await self._submit_job(agent_id, replay_prompt, JobKind.PROMPT)

    async def _submit_job(self, agent_id: str, input_text: str, kind: JobKind) -> AgentDetailResponse:
        async with self._lock:
            agent = self._require_agent(agent_id)
            await self._submit_job_locked(agent, input_text, kind)
            return await self.get_agent(agent_id)

    async def _submit_job_locked(self, agent: AgentRecord, input_text: str, kind: JobKind) -> JobRecord:
        allowed_states = {SupervisorAgentState.IDLE}
        if not agent.launch_profile:
            allowed_states = {SupervisorAgentState.IDLE, SupervisorAgentState.RUNNING}
        if agent.state not in allowed_states:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent is not ready to receive work")

        handle = self._handles.get(agent.id)
        if handle is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent handle is unavailable")
        if agent.launch_profile and handle.active_job_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent is already running a task")

        job = self._create_job(agent_id=agent.id, kind=kind, input_text=input_text)
        agent.current_job_id = job.id
        agent.current_task = input_text
        approval_requests = self._approval_requests_for_job(agent, input_text)
        if approval_requests:
            job.state = JobState.QUEUED
            self._update_agent_execution_state(
                agent,
                current_state=AgentState.WAITING_FOR_APPROVAL,
                progress=agent.progress,
                current_step="Waiting for operator approval",
                error_message=None,
            )
            for request in approval_requests:
                self._approvals[request.id] = request
                await self._record_timeline_event(
                    agent.id,
                    EventType.USER_ACTION,
                    {
                        "approval_id": request.id,
                        "status": request.status.value,
                        "action_type": request.action_type.value,
                        "payload": request.payload,
                    },
                    timestamp=request.created_at,
                )
                await self._publish(
                    "approval.requested",
                    agent=agent,
                    approval=request,
                    message=f"Approval requested for {request.action_type.value}",
                )
            return job

        await self._dispatch_existing_job_locked(agent, job)
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

    async def _dispatch_existing_job_locked(self, agent: AgentRecord, job: JobRecord) -> None:
        handle = self._handles.get(agent.id)
        if handle is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent handle is unavailable")
        if agent.launch_profile and handle.active_job_id and handle.active_job_id != job.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent is already running a task")

        agent.state = SupervisorAgentState.RUNNING
        agent.current_task = job.input_text
        agent.current_job_id = job.id
        agent.updated_at = datetime.now(UTC)
        self._update_agent_execution_state(
            agent,
            current_state=AgentState.RUNNING,
            progress=max(agent.progress, 5),
            current_step="Dispatching work",
            error_message=None,
        )
        handle.active_job_id = job.id
        await self._executor_for(agent).prompt(handle, job.input_text)

    async def _schedule_pending_agents(self) -> None:
        async with self._lock:
            while self._pending_queue:
                if not self._has_available_worker_slot():
                    break

                agent_id = self._pending_queue.popleft()
                agent = self._agents.get(agent_id)
                if agent is None or agent.state != SupervisorAgentState.PENDING:
                    continue
                if agent.launch_profile:
                    await self._launch_process_agent(agent)
                else:
                    await self._launch_mock_agent(agent)
            await self._refresh_machine()

    async def _launch_mock_agent(self, agent: AgentRecord) -> None:
        now = datetime.now(UTC)
        worker_id = self._allocate_worker_id()
        agent.state = SupervisorAgentState.STARTING
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
            if handle is None or agent.state != SupervisorAgentState.STARTING:
                return
            self.mock_executor.append_runtime_log(handle, "Mock agent boot completed and is ready for remote tasks")
            agent.state = SupervisorAgentState.IDLE
            agent.updated_at = datetime.now(UTC)
            agent.recent_logs = self.mock_executor.recent_logs(handle, self.settings.default_log_limit)
            if agent.current_job_id:
                self._complete_job(agent.current_job_id, JobState.COMPLETED, "Agent started successfully")
            await self._publish_new_logs(agent.id)
            await self._publish("agent.idle", agent=agent, message="Agent is idle and ready")

    async def _complete_process_launch(self, agent_id: str) -> None:
        await asyncio.sleep(LAUNCH_TRANSITION_DELAY_SECONDS)
        async with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                await self._append_audit(action="_complete_process_launch", target_type="agent", target_id=agent_id, status=AuditStatus.REJECTED, message="Agent not found")
                return
            if agent.state != SupervisorAgentState.STARTING:
                await self._append_audit(action="_complete_process_launch", target_type="agent", target_id=agent_id, status=AuditStatus.REJECTED, message=f"Agent in unexpected state {agent.state}")
                return
            
            await self._append_audit(action="_complete_process_launch", target_type="agent", target_id=agent_id, status=AuditStatus.ACCEPTED, message="Checking for process handle")
            handle = self._handles.get(agent_id)
            if handle is None:
                await self._append_audit(action="_complete_process_launch", target_type="agent", target_id=agent_id, status=AuditStatus.REJECTED, message="Process handle not found")
                agent.state = SupervisorAgentState.FAILED
                agent.updated_at = datetime.now(UTC)
                if agent.current_job_id:
                    self._complete_job(agent.current_job_id, JobState.FAILED, "Agent failed to start", error="Agent process was not available after launch")
                await self._publish("agent.failed", agent=agent, message="Agent process was not available after launch")
                return

            await self._append_audit(action="_complete_process_launch", target_type="agent", target_id=agent_id, status=AuditStatus.ACCEPTED, message="Checking if process exited")
            if handle.finished_at is not None:
                error_message = self._classify_launch_error(self._extract_runtime_error(handle), agent=agent)
                await self._append_audit(action="_complete_process_launch", target_type="agent", target_id=agent_id, status=AuditStatus.REJECTED, message=f"Process exited prematurely: {error_message}")
                agent.state = SupervisorAgentState.FAILED
                agent.updated_at = datetime.now(UTC)
                if agent.current_job_id:
                    self._complete_job(agent.current_job_id, JobState.FAILED, "Agent failed to start", error=error_message)
                await self._publish_new_logs(agent_id)
                await self._publish("agent.failed", agent=agent, message=error_message)
                self._handles.pop(agent_id, None)
                return
            
            await self._append_audit(action="_complete_process_launch", target_type="agent", target_id=agent_id, status=AuditStatus.ACCEPTED, message="Transitioning to IDLE")
            initial_prompt = agent.current_task
            agent.state = SupervisorAgentState.IDLE
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
        agent.state = SupervisorAgentState.STARTING
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
            agent.state = SupervisorAgentState.FAILED
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
                agent = self._require_agent(agent_id)
                self._update_agent_execution_state(
                    agent,
                    current_state=AgentState.RUNNING,
                    progress=max(agent.progress, 10),
                    current_step="Job started",
                    error_message=None,
                )
                await self._publish("job.running", agent=agent, job=job, message="Job started")

            for step in range(1, self.settings.mock_job_steps + 1):
                await asyncio.sleep(self.settings.mock_job_step_delay_ms / 1000)
                async with self._lock:
                    handle = self._handles.get(agent_id)
                    agent = self._agents.get(agent_id)
                    if handle is None or agent is None or agent.state in {SupervisorAgentState.STOPPING, SupervisorAgentState.STOPPED, SupervisorAgentState.FAILED}:
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
                agent.state = SupervisorAgentState.IDLE
                agent.current_task = None
                agent.updated_at = datetime.now(UTC)
                self._update_agent_execution_state(
                    agent,
                    current_state=AgentState.COMPLETED,
                    progress=100,
                    current_step="Completed",
                    error_message=None,
                )
                self._complete_job(job_id, JobState.COMPLETED, "Execution completed")
                await self._publish_new_logs(agent_id)
                await self._publish("job.completed", agent=agent, job=self._jobs[job_id], message="Job completed")
                await self._refresh_machine()
        except Exception as exc:
            async with self._lock:
                agent = self._require_agent(agent_id)
                agent.state = SupervisorAgentState.FAILED
                agent.updated_at = datetime.now(UTC)
                self._update_agent_execution_state(
                    agent,
                    current_state=AgentState.FAILED,
                    progress=agent.progress,
                    current_step="Execution failed",
                    error_message=str(exc),
                )
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
        agent.state = SupervisorAgentState.STOPPED
        self._update_agent_execution_state(
            agent,
            current_state=AgentState.IDLE,
            progress=0,
            current_step="Stopped",
            error_message=None,
        )
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
                if handle.finished_at is not None and agent.state not in {SupervisorAgentState.STOPPED, SupervisorAgentState.FAILED}:
                    if agent.state == SupervisorAgentState.STARTING:
                        agent.state = SupervisorAgentState.FAILED
                    else:
                        agent.state = SupervisorAgentState.STOPPED if (handle.exit_code or 0) == 0 else SupervisorAgentState.FAILED
                    self._update_agent_execution_state(
                        agent,
                        current_state=AgentState.COMPLETED if agent.state == SupervisorAgentState.STOPPED else AgentState.FAILED,
                        progress=100 if agent.state == SupervisorAgentState.STOPPED else agent.progress,
                        current_step="Exited",
                        error_message=None if agent.state == SupervisorAgentState.STOPPED else self._classify_launch_error(self._extract_runtime_error(handle), agent=agent),
                    )
                    agent.pid = None
                    agent.worker_id = None
                    agent.current_task = None
                    agent.updated_at = datetime.now(UTC)
                    if agent.current_job_id and self._jobs[agent.current_job_id].state == JobState.RUNNING:
                        error_message = self._classify_launch_error(self._extract_runtime_error(handle), agent=agent)
                        self._complete_job(
                            agent.current_job_id,
                            JobState.COMPLETED if agent.state == SupervisorAgentState.STOPPED else JobState.FAILED,
                            "Process exited",
                            error=None if agent.state == SupervisorAgentState.STOPPED else error_message,
                        )
                    await self._publish(
                        "agent.stopped" if agent.state == SupervisorAgentState.STOPPED else "agent.failed",
                        agent=agent,
                        message="Process exited cleanly" if agent.state == SupervisorAgentState.STOPPED else self._classify_launch_error(self._extract_runtime_error(handle), agent=agent),
                    )
                    self._handles.pop(agent_id, None)
                    await self._schedule_pending_agents()
                    return

    async def _task_scheduler_loop(self) -> None:
        while True:
            await asyncio.sleep(1.0)
            async with self._lock:
                runnable = [
                    task for task in self._tasks.values()
                    if task.status in {TaskStatus.PENDING, TaskStatus.BLOCKED} and self._task_dependencies_completed(task)
                ]
                for task in runnable:
                    await self._start_orchestration_task(task)

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
        active_states = {SupervisorAgentState.PENDING, SupervisorAgentState.STARTING, SupervisorAgentState.RUNNING, SupervisorAgentState.IDLE, SupervisorAgentState.STOPPING}
        active = sum(1 for agent in self._agents.values() if agent.state in active_states)
        
        # Always try to prune terminated agents to keep the state clean
        self._prune_agents_locked()
        
        if active >= self.settings.max_active_agents:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Maximum active agent limit reached on this machine")

    def _prune_agents_locked(self) -> None:
        # Keep only the last 5 finished agents to prevent state bloat
        terminated_states = {SupervisorAgentState.STOPPED, SupervisorAgentState.FAILED}
        finished_agents = [
            agent for agent in self._agents.values() 
            if agent.state in terminated_states
        ]
        
        if len(finished_agents) > 5:
            # Sort by updated_at and keep only the 5 newest ones
            finished_agents.sort(key=lambda a: a.updated_at or datetime.min.replace(tzinfo=UTC))
            to_remove = finished_agents[:-5]
            for agent in to_remove:
                self._agents.pop(agent.id, None)
                self._handles.pop(agent.id, None)
                self._agent_event_history.pop(agent.id, None)

    def _has_available_worker_slot(self) -> bool:
        busy_agents = sum(
            1
            for agent in self._agents.values()
            if agent.worker_id and agent.state in {SupervisorAgentState.STARTING, SupervisorAgentState.RUNNING, SupervisorAgentState.IDLE, SupervisorAgentState.STOPPING}
        )
        return busy_agents < self.settings.mock_worker_capacity

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
        if self._scheduler_task is None or self._scheduler_task.done():
            self._scheduler_task = asyncio.create_task(self._task_scheduler_loop())

    async def stop_background_tasks(self) -> None:
        for task in (self._heartbeat_task, self._scheduler_task):
            if task is None:
                continue
            task.cancel()
            try:
                await task
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
                for agent in list(self._agents.values()):
                    status_snapshot = self._agent_runtime_status(agent)
                    previous = self._agent_monitor_state.get(agent.id)
                    self._agent_monitor_state[agent.id] = status_snapshot.monitor_state
                    if status_snapshot.stuck_indicator and previous != "stuck":
                        await self._publish("agent.stuck", agent=agent, agent_status=status_snapshot, message=status_snapshot.warning_message or "Agent appears stalled")
                    if (
                        status_snapshot.stuck_indicator
                        and status_snapshot.silence_seconds is not None
                        and status_snapshot.silence_seconds >= self.settings.monitoring_force_fail_after_seconds
                        and agent.state == SupervisorAgentState.RUNNING
                    ):
                        await self._fail_stuck_agent(
                            agent.id,
                            status_snapshot.warning_message
                            or f"Agent stalled with no logs for {status_snapshot.silence_seconds}s",
                        )
                        continue
                    elif status_snapshot.warning_indicator and previous not in {"warning", "stuck"}:
                        await self._publish("agent.warning", agent=agent, agent_status=status_snapshot, message=status_snapshot.warning_message or "Agent needs attention")
                    elif previous in {"warning", "stuck"} and status_snapshot.monitor_state not in {"warning", "stuck"}:
                        await self._publish("agent.recovered", agent=agent, agent_status=status_snapshot, message="Agent recovered")

    def _machine_health_status(self) -> MachineHealthStatus:
        statuses = [self._agent_runtime_status(agent) for agent in self._agents.values()]
        warning_count = sum(1 for status in statuses if status.warning_indicator or status.stuck_indicator)
        failed_count = sum(1 for agent in self._agents.values() if agent.state == SupervisorAgentState.FAILED)
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
            agents_running=sum(1 for agent in self._agents.values() if agent.state in {SupervisorAgentState.RUNNING, SupervisorAgentState.IDLE}),
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
        
        # Determine the most recent activity timestamp
        last_log_timestamp = agent.last_output_at
        if not last_log_timestamp:
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
        if agent.state == SupervisorAgentState.FAILED:
            monitor_state = "failed"
        elif agent.state == SupervisorAgentState.RUNNING:
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
        elif agent.state == SupervisorAgentState.IDLE:
            monitor_state = "idle"
        resources = self._resource_usage(handle)
        return AgentRuntimeStatus(
            agent_id=agent.id,
            machine_id=self.machine.id,
            machine_name=self.machine.name,
            type=agent.type,
            state=agent.state,
            current_state=agent.current_state,
            progress=agent.progress,
            current_step=agent.current_step,
            last_updated_ts=agent.last_updated_ts,
            error_message=agent.error_message,
            monitor_state=monitor_state,
            elapsed_seconds=elapsed_seconds,
            silence_seconds=silence_seconds,
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
        self._approvals = {approval.id: approval for approval in persisted.approvals}
        self._tasks = {task.id: task for task in persisted.tasks}
        for event in persisted.timeline_events:
            history = self._timeline_events.setdefault(event.agent_id, deque(maxlen=self.settings.max_log_entries * 5))
            history.append(event)
        for agent in self._agents.values():
            if not agent.name:
                agent.name = self._default_agent_name(agent.type, agent.id)
            if not getattr(agent, "last_updated_ts", None):
                agent.last_updated_ts = now
            if agent.state in {SupervisorAgentState.PENDING, SupervisorAgentState.STARTING, SupervisorAgentState.RUNNING, SupervisorAgentState.IDLE, SupervisorAgentState.STOPPING}:
                agent.state = SupervisorAgentState.STOPPED
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
                timeline_events=[event for history in self._timeline_events.values() for event in history],
                approvals=list(self._approvals.values()),
                tasks=list(self._tasks.values()),
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
            if agent.worker_id and agent.state in {SupervisorAgentState.STARTING, SupervisorAgentState.RUNNING, SupervisorAgentState.IDLE, SupervisorAgentState.STOPPING}
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
        now = datetime.now(UTC)
        for log in new_logs:
            # Every log entry, internal or not, counts as activity
            agent.last_output_at = log.timestamp
            agent.updated_at = now
            
            if await self._handle_internal_event(agent, handle, log):
                continue
            agent.recent_logs = (agent.recent_logs + [log])[-self.settings.default_log_limit :]
            if log.stream == "stderr" or "error" in log.message.lower():
                await self._record_timeline_event(agent.id, EventType.ERROR, {"stream": log.stream, "message": log.message}, timestamp=log.timestamp)
            elif "tool" in log.message.lower():
                await self._record_timeline_event(agent.id, EventType.TOOL_CALL, {"stream": log.stream, "message": log.message}, timestamp=log.timestamp)
            elif any(token in log.message.lower() for token in ("diff", "patch", "edited", "wrote", "updated file")):
                await self._record_timeline_event(agent.id, EventType.FILE_EDIT, {"stream": log.stream, "message": log.message}, timestamp=log.timestamp)
            await self._publish("agent.log", agent=agent, log=log, message=log.message)

    async def _fail_stuck_agent(self, agent_id: str, reason: str) -> None:
        agent = self._agents.get(agent_id)
        if agent is None or agent.state != SupervisorAgentState.RUNNING:
            return
        handle = self._handles.get(agent_id)
        if handle is not None:
            await self._executor_for(agent).stop(handle)
            agent.recent_logs = self._executor_for(agent).recent_logs(handle, self.settings.default_log_limit)
            handle.active_job_id = None
        monitor = self._process_monitors.pop(agent_id, None)
        if monitor:
            monitor.cancel()
        self._handles.pop(agent_id, None)
        agent.state = SupervisorAgentState.FAILED
        self._update_agent_execution_state(
            agent,
            current_state=AgentState.BLOCKED,
            progress=agent.progress,
            current_step="Execution stalled",
            error_message=reason,
        )
        agent.pid = None
        agent.worker_id = None
        agent.current_task = None
        agent.updated_at = datetime.now(UTC)
        if agent.current_job_id and self._jobs[agent.current_job_id].state in {JobState.QUEUED, JobState.RUNNING}:
            self._complete_job(agent.current_job_id, JobState.FAILED, "Execution stalled", error=reason)
            await self._publish("job.failed", agent=agent, job=self._jobs[agent.current_job_id], message=reason)
        await self._append_audit(
            action="agent_stuck_timeout",
            target_type="agent",
            target_id=agent_id,
            status=AuditStatus.REJECTED,
            message=reason,
        )
        await self._publish("agent.failed", agent=agent, message=reason)
        await self._refresh_machine()
        await self._schedule_pending_agents()

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
        if event_name == "state.update":
            state_name = str(payload.get("state") or "RUNNING")
            step = str(payload.get("step") or agent.current_step or "Working")
            progress = int(payload.get("progress") or agent.progress or 0)
            error = str(payload.get("error") or "").strip() or None
            try:
                execution_state = AgentState(state_name)
            except ValueError:
                execution_state = AgentState.RUNNING
            self._update_agent_execution_state(
                agent,
                current_state=execution_state,
                progress=progress,
                current_step=step,
                error_message=error,
            )
            if execution_state == AgentState.BLOCKED:
                agent.state = SupervisorAgentState.FAILED
            await self._publish(
                "agent.state",
                agent=agent,
                state_update=self._agent_state_snapshot(agent),
                job=job,
                message=step,
            )
            return True
        if event_name == "job.started":
            job.state = JobState.RUNNING
            job.started_at = now
            job.updated_at = now
            agent.state = SupervisorAgentState.RUNNING
            agent.current_job_id = job.id
            agent.current_task = job.input_text
            agent.updated_at = now
            self._update_agent_execution_state(
                agent,
                current_state=AgentState.RUNNING,
                progress=max(agent.progress, 15),
                current_step="Job started",
                error_message=None,
            )
            await self._publish("job.running", agent=agent, job=job, message="Job started")
            return True

        summary = str(payload.get("summary") or "").strip() or None
        error = str(payload.get("error") or "").strip() or None
        if event_name == "job.completed":
            self._complete_job(job.id, JobState.COMPLETED, summary or "Execution completed")
            handle.active_job_id = None
            agent.state = SupervisorAgentState.IDLE
            agent.current_task = None
            agent.current_job_id = job.id
            agent.updated_at = datetime.now(UTC)
            agent.last_output_at = agent.updated_at
            self._update_agent_execution_state(
                agent,
                current_state=AgentState.COMPLETED,
                progress=100,
                current_step="Completed",
                error_message=None,
            )
            await self._publish("job.completed", agent=agent, job=job, message=summary or "Job completed")
            return True

        if event_name == "job.failed":
            runtime_error = self._classify_launch_error(error or summary or "Execution failed", agent=agent)
            self._complete_job(job.id, JobState.FAILED, summary or "Execution failed", error=runtime_error)
            handle.active_job_id = None
            agent.state = SupervisorAgentState.IDLE
            agent.current_task = None
            agent.current_job_id = job.id
            agent.updated_at = datetime.now(UTC)
            agent.last_output_at = agent.updated_at
            self._update_agent_execution_state(
                agent,
                current_state=AgentState.FAILED,
                progress=max(agent.progress, 100),
                current_step="Failed",
                error_message=runtime_error,
            )
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
        state_update: AgentStateSnapshot | None = None,
        job: JobRecord | None = None,
        log=None,
        approval: ApprovalRequest | None = None,
        audit: AuditEntry | None = None,
        task: OrchestrationTask | None = None,
        machine_health: MachineHealthStatus | None = None,
        message: str | None = None,
    ) -> None:
        await self._refresh_machine()
        await self._persist_state_locked()
        timestamp = datetime.now(UTC)
        timeline_entry = None
        computed_state_update = state_update
        if agent is not None:
            agent.metadata["last_heartbeat_at"] = timestamp.isoformat()
            agent_status = agent_status or self._agent_runtime_status(agent)
            computed_state_update = computed_state_update or self._agent_state_snapshot(agent)
            timeline_payload: dict[str, object] = {"event": event, "message": message}
            if job is not None:
                timeline_payload["job_id"] = job.id
                timeline_payload["job_state"] = job.state.value
            if approval is not None:
                timeline_payload["approval_id"] = approval.id
                timeline_payload["approval_status"] = approval.status.value
                timeline_payload["approval_action_type"] = approval.action_type.value
            if audit is not None:
                timeline_payload["audit_id"] = audit.id
                timeline_payload["audit_action"] = audit.action
            if task is not None:
                timeline_payload["task_id"] = task.id
                timeline_payload["task_status"] = task.status.value
            if log is not None:
                timeline_payload["log"] = {"stream": log.stream, "message": log.message}
            if event.startswith("agent.") or event.startswith("job.") or event.startswith("approval."):
                event_type = EventType.STATE_CHANGE
            elif event.startswith("audit.") or event.endswith(".requested"):
                event_type = EventType.USER_ACTION
            elif "failed" in event or "error" in event:
                event_type = EventType.ERROR
            else:
                event_type = EventType.USER_ACTION
            timeline_entry = await self._record_timeline_event(agent.id, event_type, timeline_payload, timestamp=timestamp)
        machine_health = machine_health or self._machine_health_status()
        emitted = SupervisorEvent(
            event=event,
            timestamp=timestamp,
            machine=self.machine,
            machine_health=machine_health,
            agent=agent,
            agent_status=agent_status,
            state_update=computed_state_update,
            timeline_event=timeline_entry,
            approval=approval,
            job=job,
            task=task,
            log=log,
            audit=audit,
            message=message,
        )
        self._event_history.append(emitted)
        if agent is not None:
            history = self._agent_event_history.setdefault(agent.id, deque(maxlen=self.settings.max_log_entries))
            history.append(emitted)
        await self.event_bus.publish(emitted)

    def _default_agent_name(self, agent_type, agent_id: str) -> str:
        return f"{agent_type.value}-{agent_id[:8]}"

    def _agent_state_snapshot(self, agent: AgentRecord) -> AgentStateSnapshot:
        return AgentStateSnapshot(
            agent_id=agent.id,
            name=agent.name,
            current_state=agent.current_state,
            progress=agent.progress,
            current_step=agent.current_step,
            last_updated_ts=agent.last_updated_ts,
            error_message=agent.error_message,
        )

    def _update_agent_execution_state(
        self,
        agent: AgentRecord,
        *,
        current_state: AgentState | None = None,
        progress: int | None = None,
        current_step: str | None = None,
        error_message: str | None = None,
    ) -> None:
        if current_state is not None:
            agent.current_state = current_state
        if progress is not None:
            agent.progress = max(0, min(100, progress))
        if current_step is not None:
            agent.current_step = current_step
        agent.error_message = error_message
        agent.last_updated_ts = datetime.now(UTC)

    async def _record_timeline_event(
        self,
        agent_id: str,
        event_type: EventType,
        payload: dict[str, object],
        *,
        timestamp: datetime | None = None,
    ) -> AgentEvent:
        entry = AgentEvent(
            event_id=str(uuid4()),
            agent_id=agent_id,
            timestamp=timestamp or datetime.now(UTC),
            type=event_type,
            payload=payload,
        )
        history = self._timeline_events.setdefault(agent_id, deque(maxlen=self.settings.max_log_entries * 5))
        history.append(entry)
        return entry

    def _approval_requests_for_job(self, agent: AgentRecord, input_text: str) -> list[ApprovalRequest]:
        if not agent.launch_profile or not agent.workspace:
            return []
        adapter_id = str(agent.metadata.get("adapter_id") or self._launch_request_from_agent(agent).get("adapter_id") or "")
        adapter = self._runtime_adapters().get(adapter_id)
        if adapter is None:
            return []
        current_job_id = agent.current_job_id
        requests = []
        for raw in adapter.risky_action_requests(
            input_text,
            agent.workspace,
            runtime_model=agent.runtime_model,
            command_name=agent.command_name,
        ):
            requests.append(
                ApprovalRequest(
                    id=str(uuid4()),
                    agent_id=agent.id,
                    action_type=ApprovalActionType(str(raw.get("action_type"))),
                    payload={
                        **dict(raw.get("payload") or {}),
                        "job_id": current_job_id,
                        "prompt": input_text,
                    },
                    created_at=datetime.now(UTC),
                )
            )
        return requests

    def _task_dependencies_completed(self, task: OrchestrationTask) -> bool:
        if not task.dependencies:
            return True
        dependency_states = [self._tasks.get(item_id).status for item_id in task.dependencies if self._tasks.get(item_id)]
        if len(dependency_states) != len(task.dependencies):
            return False
        return all(state == TaskStatus.COMPLETED for state in dependency_states)

    async def _start_orchestration_task(self, task: OrchestrationTask) -> None:
        agent = self._agents.get(task.assigned_agent or "")
        if agent is None:
            task.status = TaskStatus.BLOCKED
            task.updated_at = datetime.now(UTC)
            task.error_message = "Assigned agent is unavailable"
            return
        if agent.state not in {SupervisorAgentState.IDLE, SupervisorAgentState.RUNNING}:
            task.status = TaskStatus.BLOCKED
            task.updated_at = datetime.now(UTC)
            task.error_message = "Assigned agent is not ready"
            return
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(UTC)
        task.updated_at = task.started_at
        task.error_message = None
        await self._publish("task.running", agent=agent, task=task, message=f"Workflow task '{task.name}' started")
        try:
            await self._submit_job_locked(agent, task.prompt_template, JobKind.TASK)
            task.status = TaskStatus.COMPLETED
            task.finished_at = datetime.now(UTC)
            task.updated_at = task.finished_at
            task.summary = "Queued on assigned agent"
            await self._publish("task.completed", agent=agent, task=task, message=f"Workflow task '{task.name}' queued")
        except HTTPException as exc:
            task.status = TaskStatus.BLOCKED if exc.status_code == status.HTTP_409_CONFLICT else TaskStatus.FAILED
            task.updated_at = datetime.now(UTC)
            task.error_message = str(exc.detail)
            await self._publish("task.failed", agent=agent, task=task, message=task.error_message)

    async def _resume_agent_after_approval(self, approval: ApprovalRequest) -> None:
        pending = [item for item in self._approvals.values() if item.agent_id == approval.agent_id and item.status == ApprovalStatus.PENDING]
        if pending:
            return
        agent = self._require_agent(approval.agent_id)
        job_id = str(approval.payload.get("job_id") or agent.current_job_id or "")
        if not job_id:
            return
        job = self._jobs.get(job_id)
        if job is None or job.state != JobState.QUEUED:
            return
        self._update_agent_execution_state(
            agent,
            current_state=AgentState.RUNNING,
            progress=max(agent.progress, 10),
            current_step="Approval granted, resuming",
            error_message=None,
        )
        await self._dispatch_existing_job_locked(agent, job)
        await self._append_audit(
            action="approval_resume",
            target_type="job",
            target_id=job.id,
            status=AuditStatus.ACCEPTED,
            message="Queued job resumed after approvals",
            details={"agent_id": agent.id},
        )
        await self._publish("job.accepted", agent=agent, job=job, approval=approval, message="Approvals satisfied, dispatching queued job")

    def _require_approval(self, approval_id: str) -> ApprovalRequest:
        approval = self._approvals.get(approval_id)
        if approval is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")
        if approval.status != ApprovalStatus.PENDING:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval request is already resolved")
        return approval

    def _executor_for(self, agent: AgentRecord):
        return self.runtime_executor if agent.launch_profile else self.mock_executor

    @staticmethod
    def _overview_priority(item: AgentOverviewRecord) -> int:
        monitor = item.status.monitor_state.lower()
        state = item.agent.state.value.lower()
        if monitor == "stuck":
            return 0
        if monitor == "warning":
            return 1
        if state == "failed":
            return 2
        if state == "running":
            return 3
        if state == "starting":
            return 4
        if state == "pending":
            return 5
        if state == "idle":
            return 6
        if state == "stopping":
            return 7
        return 8

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

    async def restart_self(self, reason: str | None = None) -> RestartMachineResponse:
        await self._append_audit(
            action="restart_supervisor",
            target_type="machine",
            target_id=self.machine.id,
            status=AuditStatus.ACCEPTED,
            message=reason or "Supervisor restart requested",
        )
        
        # Give some time for the response to be sent and audit to be persisted
        async def delayed_restart():
            await asyncio.sleep(1)
            # Use the same python executable and arguments to restart
            # On Windows, we need specific flags to ensure the process is detached
            creation_flags = 0
            if sys.platform == "win32":
                # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
                creation_flags = 0x00000008 | 0x00000200
            
            subprocess.Popen(
                [sys.executable] + sys.argv,
                creationflags=creation_flags,
                close_fds=True,
                start_new_session=True if sys.platform != "win32" else False
            )
            os._exit(0)
            
        asyncio.create_task(delayed_restart())
        
        return RestartMachineResponse(
            message="Supervisor is restarting...",
            machine_id=self.machine.id
        )

    async def clear_terminated_agents(self) -> None:
        async with self._lock:
            to_remove = [
                agent_id for agent_id, agent in self._agents.items()
                if agent.state in {SupervisorAgentState.FAILED, SupervisorAgentState.STOPPED}
            ]
            for agent_id in to_remove:
                self._agents.pop(agent_id, None)
                self._handles.pop(agent_id, None)
                self._agent_event_history.pop(agent_id, None)
            await self._persist_state_locked()

        entry = AuditEntry(
            id=str(uuid4()),
            timestamp=datetime.now(UTC),
            action="clear_terminated_agents",
            target_type="machine",
            target_id=self.machine.id,
            status=AuditStatus.ACCEPTED,
            message=f"Cleared {len(to_remove)} terminated agents",
            details={},
        )
        self._audits.append(entry)
        if len(self._audits) > self.settings.max_log_entries:
            del self._audits[0 : len(self._audits) - self.settings.max_log_entries]

        await self._refresh_machine()

