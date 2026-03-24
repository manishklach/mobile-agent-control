from __future__ import annotations

import os
import subprocess
import tempfile
import threading
from pathlib import Path

from app.adapters.base import CliAgentRuntimeAdapter
from app.models import AgentType, RuntimeCapabilities


def _stream_pipe(pipe, sink: list[str], emit) -> None:
    try:
        for line in iter(pipe.readline, ""):
            text = line.rstrip()
            if text:
                sink.append(text)
                emit(text)
    finally:
        pipe.close()


class CodexCliAdapter(CliAgentRuntimeAdapter):
    adapter_id = "codex-cli"
    agent_type = AgentType.CODEX
    label = "Codex CLI"
    capabilities = RuntimeCapabilities(
        supports_initial_prompt=True,
        supports_prompt_submission=True,
        supports_background_process=True,
        supports_streaming_logs=True,
        requires_workspace=True,
        requires_local_auth=False,
        supports_resume=False,
    )

    def preflight(self) -> None:
        if not self.find_binary("codex.cmd", "codex.exe", "codex"):
            raise ValueError("Codex CLI is not installed or not on PATH")

    def run_prompt(self, prompt: str, workspace: str) -> tuple[int, str]:
        codex_binary = self.find_binary("codex.cmd", "codex.exe", "codex")
        if not codex_binary:
            raise FileNotFoundError("codex CLI was not found on PATH")
        output_file = Path(tempfile.mkstemp(prefix="codex-output-", suffix=".txt")[1])
        env = self.environment_with(
            {
                "CODEX_INTERNAL_ORIGINATOR_OVERRIDE": "Agent Control Mobile Control Plane",
            }
        )
        env.pop("CODEX_THREAD_ID", None)
        command = [
            codex_binary,
            "exec",
            "--skip-git-repo-check",
            "-C",
            workspace,
            "-o",
            str(output_file),
            prompt,
        ]
        process = subprocess.Popen(
            command,
            cwd=workspace,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        stdout_thread = threading.Thread(target=_stream_pipe, args=(process.stdout, stdout_lines, print), daemon=True)
        stderr_thread = threading.Thread(target=_stream_pipe, args=(process.stderr, stderr_lines, lambda text: print(text, file=os.sys.stderr)), daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        exit_code = process.wait()
        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)
        summary = output_file.read_text(encoding="utf-8").strip() if output_file.exists() else "\n".join(stdout_lines).strip()
        try:
            output_file.unlink(missing_ok=True)
        except PermissionError:
            pass
        return exit_code, summary
