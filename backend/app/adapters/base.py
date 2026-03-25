from __future__ import annotations

import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from app.models import (
    AgentType,
    McpServerRecord,
    RuntimeAdapterStatus,
    RuntimeCapabilities,
    RuntimeFeatureStatus,
    SlashCommandRecord,
)


class CliAgentRuntimeAdapter(ABC):
    adapter_id: str
    agent_type: AgentType
    label: str
    capabilities: RuntimeCapabilities

    def build_launch_command(self, backend_root: Path, backend_python: str) -> list[str]:
        return [
            backend_python,
            "-u",
            str((backend_root / "app" / "executors" / "cli_runtime_host.py").resolve()),
            "--adapter",
            self.adapter_id,
        ]

    def launch_env(self) -> dict[str, str]:
        return {}

    def binary_candidates(self) -> tuple[str, ...]:
        return ()

    def preflight(self) -> None:
        status = self.runtime_status()
        if not status.installed.available:
            raise ValueError(status.installed.message or f"{self.label} is not installed")
        if self.capabilities.requires_local_auth and not status.auth.available:
            raise ValueError(status.auth.message or f"{self.label} local auth is not available")

    def runtime_status(self, workspace: str | None = None) -> RuntimeAdapterStatus:
        binary_path = self.find_binary(*self.binary_candidates())
        installed = RuntimeFeatureStatus(
            available=binary_path is not None,
            message=None if binary_path else f"{self.label} is not installed or not on PATH",
        )
        auth = RuntimeFeatureStatus(available=True, message=None)
        return RuntimeAdapterStatus(
            adapter_id=self.adapter_id,
            agent_type=self.agent_type,
            label=self.label,
            installed=installed,
            auth=auth,
            binary_path=binary_path,
            capabilities=self.capabilities,
        )

    def list_command_templates(self, workspace: str | None = None) -> list[SlashCommandRecord]:
        return []

    def upsert_command_template(
        self,
        *,
        name: str,
        prompt: str,
        description: str | None = None,
        scope: str = "project",
        workspace: str | None = None,
    ) -> SlashCommandRecord:
        raise ValueError(f"{self.label} does not support managed slash commands")

    def delete_command_template(self, *, name: str, scope: str = "project", workspace: str | None = None) -> None:
        raise ValueError(f"{self.label} does not support managed slash commands")

    def list_mcp_servers(self, workspace: str | None = None) -> list[McpServerRecord]:
        return []

    def classify_runtime_error(self, message: str, exit_code: int | None = None) -> str:
        if exit_code is not None and "exit code" not in message.lower():
            return f"{message} (exit code {exit_code})"
        return message

    @abstractmethod
    def run_prompt(
        self,
        prompt: str,
        workspace: str,
        *,
        runtime_model: str | None = None,
        command_name: str | None = None,
    ) -> tuple[int, str]:
        ...

    @staticmethod
    def find_binary(*candidates: str) -> str | None:
        for candidate in candidates:
            path = shutil.which(candidate)
            if path:
                return path
        return None

    @staticmethod
    def environment_with(overrides: dict[str, str] | None = None) -> dict[str, str]:
        env = os.environ.copy()
        if overrides:
            env.update(overrides)
        return env
