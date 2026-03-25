from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from app.models import AgentType, LogEntry


@dataclass
class ProcessHandle:
    agent_id: str
    agent_type: AgentType
    started_at: datetime
    pid: int | None = None
    workspace: str | None = None
    launch_profile: str | None = None
    logs: list[LogEntry] = field(default_factory=list)
    stopped_at: datetime | None = None
    finished_at: datetime | None = None
    exit_code: int | None = None
    active_job_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Executor(Protocol):
    async def start(
        self,
        agent_id: str,
        agent_type: AgentType,
        workspace: str | None = None,
        launch_profile: str | None = None,
        initial_prompt: str | None = None,
        runtime_model: str | None = None,
        command_name: str | None = None,
    ) -> ProcessHandle:
        ...

    async def stop(self, handle: ProcessHandle) -> None:
        ...

    async def prompt(self, handle: ProcessHandle, prompt: str) -> None:
        ...

    def recent_logs(self, handle: ProcessHandle, limit: int) -> list[LogEntry]:
        ...
