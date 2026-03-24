from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models import AgentType


class LaunchProfileConfig(BaseModel):
    id: str
    agent_type: AgentType
    label: str
    description: str
    command: list[str]
    env: dict[str, str] = Field(default_factory=dict)
    workspace_required: bool = True
    supports_initial_prompt: bool = True

    def public_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "agent_type": self.agent_type,
            "label": self.label,
            "description": self.description,
            "workspace_required": self.workspace_required,
            "supports_initial_prompt": self.supports_initial_prompt,
        }


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_CONTROL_", env_file=".env", extra="ignore")

    app_name: str = "Agent Control Service"
    machine_name: str = "developer-workstation"
    machine_id: str = "machine-self"
    bearer_token: str = "change-me"
    default_log_limit: int = 200
    max_log_entries: int = 200
    max_active_agents: int = 6
    mock_worker_capacity: int = 2
    mock_job_step_delay_ms: int = 800
    mock_job_steps: int = 3
    launch_profiles_path: str = "config/launch_profiles.json"
    allowed_workspace_roots: list[str] = Field(default_factory=list)
    supported_controls: list[str] = Field(
        default_factory=lambda: [
            "start_agent",
            "launch_agent",
            "stop_agent",
            "restart_agent",
            "submit_prompt",
            "submit_task",
        ]
    )

    def load_launch_profiles(self, base_dir: Path) -> dict[str, LaunchProfileConfig]:
        path = (base_dir / self.launch_profiles_path).resolve()
        raw = json.loads(path.read_text(encoding="utf-8"))
        substitutions = {
            "{backend_root}": str(base_dir),
            "{backend_python}": sys.executable,
        }
        profiles = []
        for item in raw["profiles"]:
            command = [
                self._expand_placeholders(part, substitutions)
                for part in item.get("command", [])
            ]
            env = {
                key: self._expand_placeholders(value, substitutions)
                for key, value in item.get("env", {}).items()
            }
            profiles.append(LaunchProfileConfig(**{**item, "command": command, "env": env}))
        return {profile.id: profile for profile in profiles}

    @staticmethod
    def _expand_placeholders(value: str, substitutions: dict[str, str]) -> str:
        expanded = value
        for placeholder, replacement in substitutions.items():
            expanded = expanded.replace(placeholder, replacement)
        return expanded


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
