from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    CODEX = "codex"
    GEMINI = "gemini"


class AgentState(str, Enum):
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    IDLE = "idle"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class JobKind(str, Enum):
    STARTUP = "startup"
    TASK = "task"
    PROMPT = "prompt"
    RESTART = "restart"
    STOP = "stop"


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AuditStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"


class LogEntry(BaseModel):
    timestamp: datetime
    stream: str
    message: str


class ResourceUsage(BaseModel):
    cpu_percent: float | None = None
    memory_mb: float | None = None


class WorkerPoolState(BaseModel):
    desired_workers: int
    busy_workers: int
    idle_workers: int
    queue_depth: int
    supports_pause_resume: bool = False


class RuntimeCapabilities(BaseModel):
    supports_initial_prompt: bool = True
    supports_prompt_submission: bool = True
    supports_background_process: bool = True
    supports_streaming_logs: bool = True
    requires_workspace: bool = True
    requires_local_auth: bool = False
    supports_resume: bool = False


class MachineRecord(BaseModel):
    id: str
    name: str
    status: str
    started_at: datetime
    updated_at: datetime
    worker_pool: WorkerPoolState
    capabilities: dict[str, bool] = Field(default_factory=dict)


class LaunchProfileRecord(BaseModel):
    id: str
    agent_type: AgentType
    adapter_id: str
    label: str
    description: str
    workspace_required: bool = True
    supports_initial_prompt: bool = True
    capabilities: RuntimeCapabilities = Field(default_factory=RuntimeCapabilities)


class WorkspaceRecord(BaseModel):
    path: str
    label: str
    source: str


class JobRecord(BaseModel):
    id: str
    agent_id: str
    kind: JobKind
    state: JobState
    input_text: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    summary: str | None = None
    error: str | None = None


class AgentRecord(BaseModel):
    id: str
    type: AgentType
    state: AgentState
    pid: int | None = None
    workspace: str | None = None
    launch_profile: str | None = None
    current_task: str | None = None
    started_at: datetime | None = None
    updated_at: datetime
    worker_id: str | None = None
    current_job_id: str | None = None
    recent_logs: list[LogEntry] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditEntry(BaseModel):
    id: str
    timestamp: datetime
    action: str
    target_type: str
    target_id: str
    status: AuditStatus
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    time: datetime
    machine_id: str
    machine_name: str
    agents_total: int
    agents_running: int
    queued_jobs: int


class MachineHealthStatus(BaseModel):
    machine_id: str
    machine_name: str
    status: str
    monitor_state: str
    last_heartbeat: datetime
    last_seen: datetime
    agents_total: int
    agents_running: int
    agents_failed: int
    queued_jobs: int
    warning_count: int
    worker_pool: WorkerPoolState
    resources: ResourceUsage = Field(default_factory=ResourceUsage)


class MachineListResponse(BaseModel):
    machines: list[MachineRecord]


class MachineSelfResponse(BaseModel):
    machine: MachineRecord
    agents_total: int
    active_agents: int
    queued_jobs: int
    max_active_agents: int


class AgentListResponse(BaseModel):
    agents: list[AgentRecord]


class AgentDetailResponse(BaseModel):
    agent: AgentRecord
    current_job: JobRecord | None = None
    latest_completed_job: JobRecord | None = None
    recent_jobs: list[JobRecord] = Field(default_factory=list)


class StartAgentRequest(BaseModel):
    type: AgentType
    initial_task: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LaunchAgentRequest(BaseModel):
    type: AgentType
    launch_profile: str
    workspace: str
    initial_prompt: str | None = None


class RestartAgentRequest(BaseModel):
    reason: str | None = None


class SubmitTaskRequest(BaseModel):
    input_text: str
    kind: JobKind = JobKind.TASK


class PromptAgentRequest(BaseModel):
    prompt: str


class LogsResponse(BaseModel):
    agent_id: str
    logs: list[LogEntry]


class AgentRuntimeStatus(BaseModel):
    agent_id: str
    machine_id: str
    machine_name: str
    type: AgentType
    state: AgentState
    monitor_state: str
    elapsed_seconds: int = 0
    last_heartbeat: datetime | None = None
    last_log_timestamp: datetime | None = None
    warning_indicator: bool = False
    stuck_indicator: bool = False
    warning_message: str | None = None
    current_task: str | None = None
    workspace: str | None = None
    launch_profile: str | None = None
    pid: int | None = None
    recent_logs: list[LogEntry] = Field(default_factory=list)
    resources: ResourceUsage = Field(default_factory=ResourceUsage)


class RunningAgentsResponse(BaseModel):
    agents: list[AgentRuntimeStatus]


class AgentEventsResponse(BaseModel):
    agent_id: str
    events: list["SupervisorEvent"]


class AgentMetricsResponse(BaseModel):
    agent_id: str
    status: AgentRuntimeStatus


class AuditLogResponse(BaseModel):
    entries: list[AuditEntry]


class TaskListResponse(BaseModel):
    tasks: list[JobRecord]


class TaskDetailResponse(BaseModel):
    task: JobRecord


class LaunchProfilesResponse(BaseModel):
    profiles: list[LaunchProfileRecord]


class WorkspacesResponse(BaseModel):
    workspaces: list[WorkspaceRecord]


class ApiError(BaseModel):
    detail: str


class SupervisorEvent(BaseModel):
    event: str
    timestamp: datetime
    machine: MachineRecord | None = None
    machine_health: MachineHealthStatus | None = None
    agent: AgentRecord | None = None
    agent_status: AgentRuntimeStatus | None = None
    job: JobRecord | None = None
    log: LogEntry | None = None
    audit: AuditEntry | None = None
    message: str | None = None


class PersistedState(BaseModel):
    machine: MachineRecord
    agents: list[AgentRecord] = Field(default_factory=list)
    jobs: list[JobRecord] = Field(default_factory=list)
    audits: list[AuditEntry] = Field(default_factory=list)
