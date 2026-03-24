from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from app.adapters.base import CliAgentRuntimeAdapter
from app.core.config import LaunchProfileConfig
from app.executors.base import Executor, ProcessHandle
from app.models import AgentType, LogEntry


class CliRuntimeExecutor(Executor):
    def __init__(
        self,
        profiles: dict[str, LaunchProfileConfig],
        adapters: dict[str, CliAgentRuntimeAdapter],
        max_logs: int,
        backend_root: Path,
        backend_python: str,
    ) -> None:
        self.profiles = profiles
        self.adapters = adapters
        self.max_logs = max_logs
        self.backend_root = backend_root
        self.backend_python = backend_python
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    async def start(
        self,
        agent_id: str,
        agent_type: AgentType,
        workspace: str | None = None,
        launch_profile: str | None = None,
        initial_prompt: str | None = None,
    ) -> ProcessHandle:
        if launch_profile is None:
            raise ValueError("Launch profile is required")
        profile = self.profiles.get(launch_profile)
        if profile is None:
            raise ValueError(f"Unknown launch profile: {launch_profile}")
        if profile.agent_type != agent_type:
            raise ValueError("Launch profile does not match agent type")
        if profile.workspace_required and not workspace:
            raise ValueError("Workspace is required for this launch profile")
        adapter = self._require_adapter(profile.adapter_id)
        adapter.preflight()

        cwd = str(Path(workspace).resolve()) if workspace else str(Path.cwd())
        env = adapter.launch_env()
        env.update(profile.env)
        env["AGENT_PROFILE"] = profile.id
        env["AGENT_INITIAL_PROMPT"] = initial_prompt or ""
        env["AGENT_ADAPTER_ID"] = adapter.adapter_id

        process = await asyncio.create_subprocess_exec(
            *adapter.build_launch_command(self.backend_root, self.backend_python),
            cwd=cwd,
            env=adapter.environment_with(env),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
        )

        handle = ProcessHandle(
            agent_id=agent_id,
            agent_type=agent_type,
            started_at=datetime.now(UTC),
            pid=process.pid,
            workspace=cwd,
            launch_profile=profile.id,
            metadata={"adapter_id": adapter.adapter_id},
        )
        self._processes[agent_id] = process
        self.append_runtime_log(handle, f"Process launched with PID {process.pid}", "system")
        asyncio.create_task(self._watch_process(agent_id, handle, process))
        asyncio.create_task(self._read_stream(handle, process.stdout, "stdout"))
        asyncio.create_task(self._read_stream(handle, process.stderr, "stderr"))
        return handle

    async def stop(self, handle: ProcessHandle) -> None:
        process = self._processes.get(handle.agent_id)
        if process is None:
            return
        self.append_runtime_log(handle, "Supervisor requested stop", "system")
        if process.stdin:
            process.stdin.write(b"exit\n")
            await process.stdin.drain()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            process.terminate()
            await process.wait()
        handle.stopped_at = datetime.now(UTC)
        handle.finished_at = handle.stopped_at
        handle.exit_code = process.returncode

    async def prompt(self, handle: ProcessHandle, prompt: str) -> None:
        process = self._processes.get(handle.agent_id)
        if process is None or process.stdin is None:
            raise ValueError("Agent process is not available for prompt delivery")
        payload = {
            "command": "prompt",
            "job_id": handle.active_job_id,
            "prompt": prompt,
        }
        process.stdin.write((__import__("json").dumps(payload) + "\n").encode("utf-8"))
        await process.stdin.drain()
        self.append_runtime_log(handle, prompt, "stdin")

    def recent_logs(self, handle: ProcessHandle, limit: int) -> list[LogEntry]:
        return handle.logs[-limit:]

    def append_runtime_log(self, handle: ProcessHandle, message: str, stream: str = "stdout") -> LogEntry:
        entry = LogEntry(timestamp=datetime.now(UTC), stream=stream, message=message)
        handle.logs.append(entry)
        if len(handle.logs) > self.max_logs:
            del handle.logs[0 : len(handle.logs) - self.max_logs]
        return entry

    async def _watch_process(self, agent_id: str, handle: ProcessHandle, process: asyncio.subprocess.Process) -> None:
        await process.wait()
        handle.finished_at = datetime.now(UTC)
        handle.exit_code = process.returncode
        self.append_runtime_log(handle, f"Process exited with code {process.returncode}", "system")
        self._processes.pop(agent_id, None)

    async def _read_stream(self, handle: ProcessHandle, stream: asyncio.StreamReader | None, stream_name: str) -> None:
        if stream is None:
            return
        while True:
            line = await stream.readline()
            if not line:
                return
            self.append_runtime_log(handle, line.decode("utf-8", errors="replace").rstrip(), stream_name)

    def _require_adapter(self, adapter_id: str) -> CliAgentRuntimeAdapter:
        adapter = self.adapters.get(adapter_id)
        if adapter is None:
            raise ValueError(f"Unknown runtime adapter: {adapter_id}")
        return adapter
