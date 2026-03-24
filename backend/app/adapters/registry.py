from __future__ import annotations

from app.adapters.base import CliAgentRuntimeAdapter
from app.adapters.codex_cli import CodexCliAdapter
from app.adapters.copilot_cli import CopilotCliAdapter
from app.adapters.gemini_cli import GeminiCliAdapter


def get_runtime_adapters() -> dict[str, CliAgentRuntimeAdapter]:
    adapters: list[CliAgentRuntimeAdapter] = [
        GeminiCliAdapter(),
        CodexCliAdapter(),
        CopilotCliAdapter(),
    ]
    return {adapter.adapter_id: adapter for adapter in adapters}


def get_runtime_adapter(adapter_id: str) -> CliAgentRuntimeAdapter:
    adapters = get_runtime_adapters()
    adapter = adapters.get(adapter_id)
    if adapter is None:
        raise KeyError(f"Unknown runtime adapter: {adapter_id}")
    return adapter
