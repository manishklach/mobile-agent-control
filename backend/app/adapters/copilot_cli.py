from __future__ import annotations

from app.adapters.base import CliAgentRuntimeAdapter
from app.models import AgentType, RuntimeCapabilities


class CopilotCliAdapter(CliAgentRuntimeAdapter):
    adapter_id = "copilot-cli"
    agent_type = AgentType.CODEX
    label = "GitHub Copilot CLI"
    capabilities = RuntimeCapabilities(
        supports_initial_prompt=False,
        supports_prompt_submission=False,
        supports_background_process=False,
        supports_streaming_logs=False,
        requires_workspace=True,
        requires_local_auth=True,
        supports_resume=False,
    )

    def binary_candidates(self) -> tuple[str, ...]:
        return ("github-copilot-cli", "copilot", "gh")

    def preflight(self) -> None:
        if not self.find_binary(*self.binary_candidates()):
            raise ValueError("Copilot CLI is not installed or not on PATH")

    def run_prompt(
        self,
        prompt: str,
        workspace: str,
        *,
        runtime_model: str | None = None,
        command_name: str | None = None,
    ) -> tuple[int, str]:
        raise ValueError("Copilot CLI adapter is registered but prompt execution is not enabled in this build")
