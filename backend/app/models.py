from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    CODEX = "codex"
    GEMINI = "gemini"
    HERMES = "hermes"


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


class DiagnosisResponse(BaseModel):
    agent_id: str
    is_failed: bool
    cause: str | None = None
    suggestion: str | None = None
    logs_analyzed: int
    timestamp: datetime


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
    supports_command_templates: bool = False
    supports_mcp: bool = False
    supports_model_selection: bool = False


class RuntimeFeatureStatus(BaseModel):
    available: bool
    message: str | None = None


class RuntimeAdapterStatus(BaseModel):
    adapter_id: str
    agent_type: AgentType
    label: str
    installed: RuntimeFeatureStatus
    auth: RuntimeFeatureStatus
    version: str | None = None
    binary_path: str | None = None
    capabilities: RuntimeCapabilities = Field(default_factory=RuntimeCapabilities)
    warnings: list[str] = Field(default_factory=list)


class RuntimeAdapterRecord(BaseModel):
    adapter_id: str
    agent_type: AgentType
    label: str
    capabilities: RuntimeCapabilities = Field(default_factory=RuntimeCapabilities)
    status: RuntimeAdapterStatus


class SlashCommandRecord(BaseModel):
    name: str
    description: str | None = None
    scope: str
    path: str
    source: str
    managed: bool = False
    prompt_preview: str | None = None


class McpServerRecord(BaseModel):
    name: str
    scope: str
    transport: str
    health: str
    enabled: bool = True
    command: str | None = None
    endpoint: str | None = None
    description: str | None = None
    warning: str | None = None


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
    metadata: dict[str, Any] = Field(default_factory=dict)


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
    runtime_model: str | None = None
    command_name: str | None = None
    last_output_at: datetime | None = None
    mcp_enabled: bool = False
    mcp_servers: list[str] = Field(default_factory=list)
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
    mcp_server_count: int = 0
    mcp_healthy_count: int = 0
    adapter_warnings: list[str] = Field(default_factory=list)


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
    latest_diagnosis: DiagnosisResponse | None = None


class AgentOverviewRecord(BaseModel):
    agent: AgentRecord
    status: "AgentRuntimeStatus"
    current_job: JobRecord | None = None
    latest_completed_job: JobRecord | None = None


class AgentOverviewListResponse(BaseModel):
    agents: list[AgentOverviewRecord]


class StartAgentRequest(BaseModel):
    type: AgentType
    initial_task: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RestartMachineRequest(BaseModel):
    reason: str | None = None


class RestartMachineResponse(BaseModel):
    message: str
    machine_id: str


class LaunchAgentRequest(BaseModel):
    type: AgentType
    launch_profile: str
    workspace: str
    initial_prompt: str | None = None
    runtime_model: str | None = None
    command_name: str | None = None


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
    silence_seconds: int | None = None
    last_heartbeat: datetime | None = None
    last_log_timestamp: datetime | None = None
    warning_indicator: bool = False
    stuck_indicator: bool = False
    warning_message: str | None = None
    current_task: str | None = None
    workspace: str | None = None
    launch_profile: str | None = None
    runtime_model: str | None = None
    command_name: str | None = None
    last_output_at: datetime | None = None
    mcp_enabled: bool = False
    mcp_servers: list[str] = Field(default_factory=list)
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


class RuntimeAdaptersResponse(BaseModel):
    adapters: list[RuntimeAdapterRecord]


class RuntimeAdapterStatusResponse(BaseModel):
    adapter: RuntimeAdapterRecord


class SlashCommandsResponse(BaseModel):
    adapter_id: str
    commands: list[SlashCommandRecord]


class UpsertSlashCommandRequest(BaseModel):
    name: str
    prompt: str
    description: str | None = None
    scope: str = "project"
    workspace: str | None = None


class McpServersResponse(BaseModel):
    machine_id: str
    servers: list[McpServerRecord]


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
