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


class WorkerPoolState(BaseModel):
    desired_workers: int
    busy_workers: int
    idle_workers: int
    queue_depth: int
    supports_pause_resume: bool = False


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
    label: str
    description: str
    workspace_required: bool = True
    supports_initial_prompt: bool = True


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


class MachineSelfResponse(BaseModel):
    machine: MachineRecord
    agents_total: int
    active_agents: int
    queued_jobs: int


class AgentListResponse(BaseModel):
    agents: list[AgentRecord]


class AgentDetailResponse(BaseModel):
    agent: AgentRecord
    current_job: JobRecord | None = None


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


class AuditLogResponse(BaseModel):
    entries: list[AuditEntry]


class TaskListResponse(BaseModel):
    tasks: list[JobRecord]


class TaskDetailResponse(BaseModel):
    task: JobRecord


class LaunchProfilesResponse(BaseModel):
    profiles: list[LaunchProfileRecord]


class ApiError(BaseModel):
    detail: str


class SupervisorEvent(BaseModel):
    event: str
    timestamp: datetime
    machine: MachineRecord | None = None
    agent: AgentRecord | None = None
    job: JobRecord | None = None
    log: LogEntry | None = None
    audit: AuditEntry | None = None
    message: str | None = None
