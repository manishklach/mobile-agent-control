from __future__ import annotations

import json
import os
import subprocess
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


class GeminiCliAdapter(CliAgentRuntimeAdapter):
    adapter_id = "gemini-cli"
    agent_type = AgentType.GEMINI
    label = "Gemini CLI"
    capabilities = RuntimeCapabilities(
        supports_initial_prompt=True,
        supports_prompt_submission=True,
        supports_background_process=True,
        supports_streaming_logs=True,
        requires_workspace=True,
        requires_local_auth=True,
        supports_resume=False,
    )

    def preflight(self) -> None:
        if not self.find_binary("gemini.cmd", "gemini.exe", "gemini"):
            raise ValueError("Gemini CLI is not installed or not on PATH")
        if os.environ.get("GEMINI_API_KEY"):
            return
        gemini_settings = Path.home() / ".gemini" / "settings.json"
        oauth_creds = Path.home() / ".gemini" / "oauth_creds.json"
        if gemini_settings.exists() and oauth_creds.exists():
            return
        raise ValueError("Gemini local auth is missing. Run gemini locally once or set GEMINI_API_KEY before starting the supervisor")

    def run_prompt(self, prompt: str, workspace: str) -> tuple[int, str]:
        gemini_binary = self.find_binary("gemini.cmd", "gemini.exe", "gemini")
        if not gemini_binary:
            raise FileNotFoundError("gemini CLI was not found on PATH")
        command = [
            gemini_binary,
            "-p",
            prompt,
            "--output-format",
            "json",
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
            env=self.environment_with(),
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
        return exit_code, self.extract_summary("\n".join(stdout_lines).strip())

    @staticmethod
    def extract_summary(stdout_text: str) -> str:
        if not stdout_text:
            return ""
        stripped = stdout_text.strip()
        candidates = [stripped]
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end > start:
            candidates.append(stripped[start : end + 1])
        for candidate in candidates:
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            response = payload.get("response")
            if isinstance(response, str) and response.strip():
                return response.strip()
        return stripped
