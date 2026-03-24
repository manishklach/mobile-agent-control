from __future__ import annotations

from datetime import UTC, datetime

from app.executors.base import Executor, ProcessHandle
from app.models import AgentType, LogEntry


class MockExecutor(Executor):
    def __init__(self, max_logs: int) -> None:
        self.max_logs = max_logs

    async def start(
        self,
        agent_id: str,
        agent_type: AgentType,
        workspace: str | None = None,
        launch_profile: str | None = None,
        initial_prompt: str | None = None,
    ) -> ProcessHandle:
        handle = ProcessHandle(
            agent_id=agent_id,
            agent_type=agent_type,
            started_at=datetime.now(UTC),
            pid=None,
            workspace=workspace,
            launch_profile=launch_profile,
        )
        self._append_log(handle, "system", f"Mock {agent_type.value} agent supervisor accepted start command")
        if initial_prompt:
            self._append_log(handle, "stdin", f"Initial prompt queued: {initial_prompt}")
        return handle

    async def stop(self, handle: ProcessHandle) -> None:
        handle.stopped_at = datetime.now(UTC)
        handle.finished_at = handle.stopped_at
        handle.exit_code = 0
        self._append_log(handle, "system", "Mock agent stopped by supervisor command")

    async def prompt(self, handle: ProcessHandle, prompt: str) -> None:
        self._append_log(handle, "stdin", f"Supervisor submitted input: {prompt}")

    def recent_logs(self, handle: ProcessHandle, limit: int) -> list[LogEntry]:
        return handle.logs[-limit:]

    def append_runtime_log(self, handle: ProcessHandle, message: str, stream: str = "stdout") -> LogEntry:
        entry = LogEntry(timestamp=datetime.now(UTC), stream=stream, message=message)
        handle.logs.append(entry)
        if len(handle.logs) > self.max_logs:
            del handle.logs[0 : len(handle.logs) - self.max_logs]
        return entry

    def _append_log(self, handle: ProcessHandle, stream: str, message: str) -> None:
        self.append_runtime_log(handle=handle, stream=stream, message=message)
