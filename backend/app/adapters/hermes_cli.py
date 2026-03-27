from __future__ import annotations

import re
import subprocess
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.adapters.base import CliAgentRuntimeAdapter
from app.models import AgentType, RuntimeAdapterStatus, RuntimeCapabilities, RuntimeFeatureStatus


def _stream_pipe(pipe, sink: list[str], emit) -> None:
    try:
        for line in iter(pipe.readline, ""):
            text = line.rstrip()
            if text:
                sink.append(text)
                emit(text)
    finally:
        pipe.close()


class HermesCliAdapter(CliAgentRuntimeAdapter):
    adapter_id = "hermes-cli"
    agent_type = AgentType.HERMES
    label = "Hermes Agent (WSL)"
    capabilities = RuntimeCapabilities(
        supports_initial_prompt=True,
        supports_prompt_submission=True,
        supports_background_process=True,
        supports_streaming_logs=True,
        requires_workspace=True,
        requires_local_auth=True,
        supports_resume=False,
        supports_command_templates=False,
        supports_mcp=False,
        supports_model_selection=True,
    )

    def __init__(self) -> None:
        self._cached_status: tuple[datetime, RuntimeAdapterStatus] | None = None

    def runtime_status(self, workspace: str | None = None) -> RuntimeAdapterStatus:
        now = datetime.now(UTC)
        if self._cached_status and (now - self._cached_status[0]) < timedelta(seconds=20):
            return self._cached_status[1]

        wsl_available = self.find_binary("wsl.exe", "wsl")
        if not wsl_available:
            status = RuntimeAdapterStatus(
                adapter_id=self.adapter_id,
                agent_type=self.agent_type,
                label=self.label,
                installed=RuntimeFeatureStatus(available=False, message="WSL is not installed or not on PATH"),
                auth=RuntimeFeatureStatus(available=False, message="Hermes Agent requires WSL plus local Hermes setup"),
                binary_path=None,
                capabilities=self.capabilities,
                warnings=["Hermes Agent currently runs through WSL on Windows"],
            )
            self._cached_status = (now, status)
            return status

        binary_path = self._run_wsl(["bash", "-lc", "command -v hermes"], timeout=15)
        installed = RuntimeFeatureStatus(
            available=bool(binary_path),
            message=None if binary_path else "Hermes CLI is not installed in WSL. Install it inside WSL first.",
        )
        auth = self._auth_status() if binary_path else RuntimeFeatureStatus(
            available=False,
            message="Hermes local config is unavailable until the CLI is installed in WSL",
        )
        warnings = ["Hermes Agent is launched through WSL on this machine."]
        status = RuntimeAdapterStatus(
            adapter_id=self.adapter_id,
            agent_type=self.agent_type,
            label=self.label,
            installed=installed,
            auth=auth,
            version=self._detect_version() if binary_path else None,
            binary_path=binary_path or "wsl://hermes",
            capabilities=self.capabilities,
            warnings=warnings,
        )
        self._cached_status = (now, status)
        return status

    def preflight(self) -> None:
        status = self.runtime_status()
        if not status.installed.available:
            raise ValueError(status.installed.message or "Hermes CLI is not installed in WSL")
        if not status.auth.available:
            raise ValueError(status.auth.message or "Hermes CLI local auth/config is not available in WSL")

    def classify_runtime_error(self, message: str, exit_code: int | None = None) -> str:
        lowered = message.lower()
        if "wsl" in lowered and ("not found" in lowered or "command not found" in lowered):
            return "WSL is not available on this machine. Hermes Agent currently requires WSL on Windows."
        if "hermes" in lowered and "not installed" in lowered:
            return "Hermes Agent is not installed in WSL. Install it inside WSL before launching."
        if "config" in lowered and "missing" in lowered:
            return "Hermes local configuration is missing in WSL. Run 'hermes setup' inside WSL first."
        if "provider" in lowered and "missing" in lowered:
            return "Hermes provider/auth is not configured in WSL. Run 'hermes setup' or 'hermes model' inside WSL."
        if "timeout" in lowered:
            return "Hermes Agent timed out while running the task."
        if exit_code is not None and exit_code != 0:
            return f"Hermes Agent failed (exit code {exit_code}). Last output: {message[:140]}..."
        return super().classify_runtime_error(message, exit_code)

    def run_prompt(
        self,
        prompt: str,
        workspace: str,
        *,
        runtime_model: str | None = None,
        command_name: str | None = None,
    ) -> tuple[int, str]:
        linux_workspace = self._to_wsl_path(workspace)
        effective_prompt = prompt
        if command_name:
            effective_prompt = f"/{command_name} {prompt}".strip()
        command = ["wsl.exe", "--cd", linux_workspace, "hermes", "chat", "-q", effective_prompt]
        if runtime_model:
            command.extend(["--model", runtime_model])
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
        stdout_thread = threading.Thread(target=_stream_pipe, args=(process.stdout, stdout_lines, lambda _: None), daemon=True)
        stderr_thread = threading.Thread(target=_stream_pipe, args=(process.stderr, stderr_lines, lambda _: None), daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        try:
            exit_code = process.wait(timeout=900)
        except subprocess.TimeoutExpired:
            process.kill()
            exit_code = -1
            stderr_lines.append("Hermes Agent execution timed out after 15 minutes")
        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)
        combined_output = "\n".join([*stdout_lines, *stderr_lines]).strip()
        return exit_code, self._clean_summary(combined_output)

    def _auth_status(self) -> RuntimeFeatureStatus:
        config_present = self._run_wsl(
            ["bash", "-lc", "test -f ~/.hermes/config.yaml -o -f ~/.hermes/config.yml -o -f ~/.hermes/state.db && echo configured"],
            timeout=15,
        )
        if config_present:
            return RuntimeFeatureStatus(available=True, message="Using Hermes local config in WSL")
        return RuntimeFeatureStatus(
            available=False,
            message="Hermes local config is missing in WSL. Run 'hermes setup' inside WSL first.",
        )

    def _detect_version(self) -> str | None:
        return self._run_wsl(["hermes", "--version"], timeout=15)

    def _to_wsl_path(self, workspace: str) -> str:
        converted = self._run_wsl(["wslpath", "-a", workspace], timeout=15)
        if not converted:
            raise ValueError("Unable to translate workspace path for WSL")
        return converted

    def _run_wsl(self, args: list[str], timeout: int) -> str | None:
        try:
            result = subprocess.run(
                ["wsl.exe", *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=self.environment_with(),
            )
        except (OSError, subprocess.SubprocessError):
            return None
        output = (result.stdout or result.stderr or "").strip()
        if result.returncode != 0:
            return None
        return output or None

    @staticmethod
    def _clean_summary(output: str) -> str:
        ansi = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
        cleaned = ansi.sub("", output).strip()
        return cleaned
