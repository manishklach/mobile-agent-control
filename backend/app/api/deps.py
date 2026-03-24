from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.executors.mock_executor import MockExecutor
from app.executors.shell_executor import ShellExecutor
from app.services.agent_manager import AgentManager
from app.services.event_bus import EventBus

BASE_DIR = Path(__file__).resolve().parents[2]
settings = get_settings()
event_bus = EventBus()
mock_executor = MockExecutor(max_logs=settings.max_log_entries)
launch_profiles = settings.load_launch_profiles(BASE_DIR)
shell_executor = ShellExecutor(profiles=launch_profiles, max_logs=settings.max_log_entries)
agent_manager = AgentManager(
    settings=settings,
    mock_executor=mock_executor,
    shell_executor=shell_executor,
    launch_profiles=launch_profiles,
    event_bus=event_bus,
)


def get_agent_manager() -> AgentManager:
    return agent_manager


def get_event_bus() -> EventBus:
    return event_bus
