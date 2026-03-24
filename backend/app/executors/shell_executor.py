from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import LaunchProfileConfig
from app.executors.base import Executor, ProcessHandle
from app.models import AgentType, LogEntry


class ShellExecutor(Executor):
    def __init__(self, profiles: dict[str, LaunchProfileConfig], max_logs: int) -> None:
        self.profiles = profiles
        self.max_logs = max_logs
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

        cwd = str(Path(workspace).resolve()) if workspace else os.getcwd()
        env = os.environ.copy()
        env.update(profile.env)
        env["AGENT_PROFILE"] = profile.id
        env["AGENT_INITIAL_PROMPT"] = initial_prompt or ""

        process = await asyncio.create_subprocess_exec(
            *profile.command,
            cwd=cwd,
            env=env,
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
        )
        self._processes[agent_id] = process
        self._append_log(handle, "system", f"Process launched with PID {process.pid}")
        asyncio.create_task(self._watch_process(agent_id, handle, process))
        asyncio.create_task(self._read_stream(handle, process.stdout, "stdout"))
        asyncio.create_task(self._read_stream(handle, process.stderr, "stderr"))
        return handle

    async def stop(self, handle: ProcessHandle) -> None:
        process = self._processes.get(handle.agent_id)
        if process is None:
            return
        self._append_log(handle, "system", "Supervisor requested stop")
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
        process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await process.stdin.drain()
        self._append_log(handle, "stdin", prompt)

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
        self._append_log(handle, "system", f"Process exited with code {process.returncode}")
        self._processes.pop(agent_id, None)

    async def _read_stream(self, handle: ProcessHandle, stream: asyncio.StreamReader | None, stream_name: str) -> None:
        if stream is None:
            return
        while True:
            line = await stream.readline()
            if not line:
                return
            self._append_log(handle, stream_name, line.decode("utf-8", errors="replace").rstrip())

    def _append_log(self, handle: ProcessHandle, stream: str, message: str) -> None:
        self.append_runtime_log(handle, message, stream)
