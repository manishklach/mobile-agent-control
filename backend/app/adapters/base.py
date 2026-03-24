from __future__ import annotations

import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from app.models import AgentType, RuntimeCapabilities


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

    @abstractmethod
    def preflight(self) -> None:
        ...

    @abstractmethod
    def run_prompt(self, prompt: str, workspace: str) -> tuple[int, str]:
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
