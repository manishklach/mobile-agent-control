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
from app.executors.mock_executor import MockExecutor
from app.executors.shell_executor import ShellExecutor
from app.models import (
    AgentDetailResponse,
    AgentListResponse,
    AgentRecord,
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
    MachineRecord,
    MachineSelfResponse,
    PromptAgentRequest,
    RestartAgentRequest,
    StartAgentRequest,
    SubmitTaskRequest,
    SupervisorEvent,
    TaskDetailResponse,
    TaskListResponse,
    WorkerPoolState,
)
from app.services.event_bus import EventBus

EVENT_PREFIX = "__SUPERVISOR_EVENT__"


class AgentManager:
    def __init__(
        self,
        settings: AppSettings,
        mock_executor: MockExecutor,
        shell_executor: ShellExecutor,
        launch_profiles: dict[str, LaunchProfileConfig],
        event_bus: EventBus,
    ) -> None:
        self.settings = settings
        self.mock_executor = mock_executor
        self.shell_executor = shell_executor
        self.launch_profiles = launch_profiles
        self.event_bus = event_bus
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
        self._lock = asyncio.Lock()

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

    async def machine_self(self) -> MachineSelfResponse:
        await self._refresh_machine()
        return MachineSelfResponse(
            machine=self.machine,
            agents_total=len(self._agents),
            active_agents=sum(1 for agent in self._agents.values() if agent.state in {AgentState.RUNNING, AgentState.IDLE, AgentState.STARTING}),
            queued_jobs=sum(1 for job in self._jobs.values() if job.state == JobState.QUEUED),
        )

    async def list_agents(self) -> AgentListResponse:
        await self._refresh_machine()
        return AgentListResponse(agents=sorted(self._agents.values(), key=lambda item: item.updated_at, reverse=True))

    async def get_agent(self, agent_id: str) -> AgentDetailResponse:
        agent = self._require_agent(agent_id)
        current_job = self._jobs.get(agent.current_job_id) if agent.current_job_id else None
        return AgentDetailResponse(agent=agent, current_job=current_job)

    async def get_launch_profiles(self) -> LaunchProfilesResponse:
        profiles = [LaunchProfileRecord(**profile.public_dict()) for profile in self.launch_profiles.values()]
        return LaunchProfilesResponse(profiles=sorted(profiles, key=lambda item: (item.agent_type.value, item.id)))

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

            now = datetime.now(UTC)
            agent_id = str(uuid4())
            startup_job = self._create_job(agent_id=agent_id, kind=JobKind.STARTUP, input_text=request.initial_prompt or "launch agent")
            startup_job.state = JobState.RUNNING
            startup_job.started_at = now
            startup_job.updated_at = now

            agent = AgentRecord(
                id=agent_id,
                type=request.type,
                state=AgentState.STARTING,
                pid=None,
                workspace=str(workspace),
                launch_profile=request.launch_profile,
                current_task=request.initial_prompt,
                started_at=now,
                updated_at=now,
                worker_id=self._allocate_worker_id(),
                current_job_id=startup_job.id,
                recent_logs=[],
                metadata={},
            )
            self._agents[agent_id] = agent

            try:
                handle = await self.shell_executor.start(
                    agent_id=agent_id,
                    agent_type=request.type,
                    workspace=str(workspace),
                    launch_profile=request.launch_profile,
                    initial_prompt=request.initial_prompt,
                )
            except Exception as exc:
                agent.state = AgentState.FAILED
                agent.updated_at = datetime.now(UTC)
                self._complete_job(startup_job.id, JobState.FAILED, "Launch failed", error=str(exc))
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

            agent.pid = handle.pid
            agent.recent_logs = self.shell_executor.recent_logs(handle, self.settings.default_log_limit)
            self._handles[agent_id] = handle
            self._log_offsets[agent_id] = len(handle.logs)
            self._process_monitors[agent_id] = asyncio.create_task(self._monitor_process(agent_id))
            await self._append_audit(
                action="launch_agent",
                target_type="agent",
                target_id=agent_id,
                status=AuditStatus.ACCEPTED,
                message="Launch command accepted by supervisor",
                details={"launch_profile": request.launch_profile, "workspace": str(workspace)},
            )
            await self._publish("agent.starting", agent=agent, job=startup_job, message="Agent process launched")
            asyncio.create_task(self._complete_process_launch(agent_id))
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
            if agent.current_job_id:
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
                now = datetime.now(UTC)
                restart_job.state = JobState.RUNNING
                restart_job.started_at = now
                restart_job.updated_at = now
                agent.state = AgentState.STARTING
                agent.pid = None
                agent.worker_id = self._allocate_worker_id()
                agent.current_job_id = restart_job.id
                agent.current_task = request.reason
                agent.started_at = now
                agent.updated_at = now
                try:
                    handle = await self.shell_executor.start(
                        agent_id=agent_id,
                        agent_type=agent.type,
                        workspace=relaunch_workspace,
                        launch_profile=relaunch_profile,
                        initial_prompt=request.reason,
                    )
                except Exception as exc:
                    agent.state = AgentState.FAILED
                    agent.updated_at = datetime.now(UTC)
                    self._complete_job(restart_job.id, JobState.FAILED, "Restart failed", error=str(exc))
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

                agent.pid = handle.pid
                agent.recent_logs = self.shell_executor.recent_logs(handle, self.settings.default_log_limit)
                self._handles[agent_id] = handle
                self._log_offsets[agent_id] = len(handle.logs)
                self._process_monitors[agent_id] = asyncio.create_task(self._monitor_process(agent_id))
                await self._publish("agent.starting", agent=agent, job=restart_job, message="Agent process restarting")
                asyncio.create_task(self._complete_process_launch(agent_id))
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
        while self._pending_queue and self.machine.worker_pool.idle_workers > 0:
            agent_id = self._pending_queue.popleft()
            agent = self._agents.get(agent_id)
            if agent is None or agent.state != AgentState.PENDING:
                continue
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
                    agent.state = AgentState.STOPPED if (handle.exit_code or 0) == 0 else AgentState.FAILED
                    agent.pid = None
                    agent.updated_at = datetime.now(UTC)
                    if agent.current_job_id and self._jobs[agent.current_job_id].state == JobState.RUNNING:
                        self._complete_job(
                            agent.current_job_id,
                            JobState.COMPLETED if agent.state == AgentState.STOPPED else JobState.FAILED,
                            "Process exited",
                            error=None if agent.state == AgentState.STOPPED else f"Exit code {handle.exit_code}",
                        )
                    await self._publish(
                        "agent.stopped" if agent.state == AgentState.STOPPED else "agent.failed",
                        agent=agent,
                        message=f"Process exited with code {handle.exit_code}",
                    )
                    self._handles.pop(agent_id, None)
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

    def _validate_workspace(self, workspace: str) -> Path:
        path = Path(workspace).expanduser().resolve()
        if not path.exists() or not path.is_dir():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace does not exist or is not a directory")
        if self.settings.allowed_workspace_roots:
            allowed = [Path(root).expanduser().resolve() for root in self.settings.allowed_workspace_roots]
            if not any(path == root or root in path.parents for root in allowed):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace is outside allowed roots")
        return path

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
            await self._publish("job.completed", agent=agent, job=job, message=summary or "Job completed")
            return True

        if event_name == "job.failed":
            self._complete_job(job.id, JobState.FAILED, summary or "Execution failed", error=error)
            handle.active_job_id = None
            agent.state = AgentState.IDLE
            agent.current_task = None
            agent.current_job_id = job.id
            agent.updated_at = datetime.now(UTC)
            await self._publish("job.failed", agent=agent, job=job, message=error or summary or "Job failed")
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
        job: JobRecord | None = None,
        log=None,
        audit: AuditEntry | None = None,
        message: str | None = None,
    ) -> None:
        await self._refresh_machine()
        await self.event_bus.publish(
            SupervisorEvent(
                event=event,
                timestamp=datetime.now(UTC),
                machine=self.machine,
                agent=agent,
                job=job,
                log=log,
                audit=audit,
                message=message,
            )
        )

    def _executor_for(self, agent: AgentRecord):
        return self.shell_executor if agent.launch_profile else self.mock_executor

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
