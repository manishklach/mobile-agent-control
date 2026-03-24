from __future__ import annotations

import sys
from pathlib import Path

from app.adapters.registry import get_runtime_adapters
from app.core.config import get_settings
from app.executors.cli_runtime_executor import CliRuntimeExecutor
from app.executors.mock_executor import MockExecutor
from app.services.agent_manager import AgentManager
from app.services.event_bus import EventBus
from app.services.state_store import StateStore

BASE_DIR = Path(__file__).resolve().parents[2]
settings = get_settings()
event_bus = EventBus()
mock_executor = MockExecutor(max_logs=settings.max_log_entries)
launch_profiles = settings.load_launch_profiles(BASE_DIR)
runtime_adapters = get_runtime_adapters()
cli_runtime_executor = CliRuntimeExecutor(
    profiles=launch_profiles,
    adapters=runtime_adapters,
    max_logs=settings.max_log_entries,
    backend_root=BASE_DIR,
    backend_python=Path(sys.executable).resolve().as_posix(),
)
state_store = StateStore(settings.state_store_file(BASE_DIR))
agent_manager = AgentManager(
    settings=settings,
    mock_executor=mock_executor,
    runtime_executor=cli_runtime_executor,
    launch_profiles=launch_profiles,
    event_bus=event_bus,
    state_store=state_store,
)


def get_agent_manager() -> AgentManager:
    return agent_manager


def get_event_bus() -> EventBus:
    return event_bus
