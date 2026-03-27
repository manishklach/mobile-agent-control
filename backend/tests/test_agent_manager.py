from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import AppSettings
from app.executors.mock_executor import MockExecutor
from app.models import (
    AgentRecord,
    AgentState,
    AgentType,
    AuditStatus,
    JobKind,
    JobRecord,
    JobState,
    MachineRecord,
    PersistedState,
    StartAgentRequest,
    SubmitTaskRequest,
    WorkerPoolState,
)
from app.services.agent_manager import AgentManager
from app.services.event_bus import EventBus
from app.services.state_store import StateStore


def make_settings(**overrides: object) -> AppSettings:
    values = {
        "bearer_token": "test-token",
        "machine_name": "test-machine",
        "machine_id": "machine-self",
        "max_active_agents": 4,
        "mock_worker_capacity": 1,
        "mock_job_step_delay_ms": 50,
        "mock_job_steps": 3,
        "monitoring_heartbeat_interval_seconds": 1,
        "monitoring_warning_after_seconds": 5,
        "monitoring_stuck_after_seconds": 10,
    }
    values.update(overrides)
    return AppSettings(**values)


def make_manager(state_path: Path, **setting_overrides: object) -> AgentManager:
    settings = make_settings(**setting_overrides)
    mock_executor = MockExecutor(max_logs=settings.max_log_entries)
    return AgentManager(
        settings=settings,
        mock_executor=mock_executor,
        runtime_executor=mock_executor,  # type: ignore[arg-type]
        launch_profiles={},
        event_bus=EventBus(),
        state_store=StateStore(state_path),
    )


class AgentManagerLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._managers: list[AgentManager] = []

    async def asyncTearDown(self) -> None:
        for manager in self._managers:
            await manager.stop_background_tasks()

    def _manager(self, state_path: Path, **setting_overrides: object) -> AgentManager:
        manager = make_manager(state_path, **setting_overrides)
        self._managers.append(manager)
        return manager

    async def test_start_agent_becomes_idle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = self._manager(Path(tmp_dir) / "state.db")

            response = await manager.start_agent(StartAgentRequest(type=AgentType.GEMINI, initial_task="boot"))
            self.assertEqual(response.agent.state, AgentState.STARTING)

            await asyncio.sleep(0.7)
            detail = await manager.get_agent(response.agent.id)

            self.assertEqual(detail.agent.state, AgentState.IDLE)
            self.assertIsNotNone(detail.latest_completed_job)
            assert detail.latest_completed_job is not None
            self.assertEqual(detail.latest_completed_job.state, JobState.COMPLETED)
            self.assertIn("started", detail.latest_completed_job.summary.lower())

    async def test_pending_agent_can_be_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = self._manager(Path(tmp_dir) / "state.db", mock_worker_capacity=0)

            response = await manager.start_agent(StartAgentRequest(type=AgentType.GEMINI, initial_task="queued"))
            self.assertEqual(response.agent.state, AgentState.PENDING)

            stopped = await manager.stop_agent(response.agent.id)

            self.assertEqual(stopped.agent.state, AgentState.STOPPED)
            cancelled_job = stopped.latest_completed_job or stopped.current_job
            self.assertIsNotNone(cancelled_job)
            assert cancelled_job is not None
            self.assertEqual(cancelled_job.state, JobState.CANCELLED)

    async def test_mock_prompt_completes_and_returns_idle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = self._manager(Path(tmp_dir) / "state.db")

            response = await manager.start_agent(StartAgentRequest(type=AgentType.GEMINI, initial_task="boot"))
            await asyncio.sleep(0.7)

            await manager.submit_task(response.agent.id, SubmitTaskRequest(input_text="inspect repo", kind=JobKind.TASK))
            await asyncio.sleep(0.05)
            detail_running = await manager.get_agent(response.agent.id)
            self.assertEqual(detail_running.agent.state, AgentState.RUNNING)

            await asyncio.sleep(0.25)
            detail = await manager.get_agent(response.agent.id)
            self.assertEqual(detail.agent.state, AgentState.IDLE)
            self.assertEqual(detail.latest_completed_job.state, JobState.COMPLETED)
            self.assertEqual(detail.latest_completed_job.kind, JobKind.TASK)

    async def test_restore_marks_inflight_work_as_failed_and_agents_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_path = Path(tmp_dir) / "state.db"
            now = datetime.now(UTC)
            persisted = PersistedState(
                machine=MachineRecord(
                    id="machine-self",
                    name="test-machine",
                    status="online",
                    started_at=now,
                    updated_at=now,
                    worker_pool=WorkerPoolState(
                        desired_workers=1,
                        busy_workers=1,
                        idle_workers=0,
                        queue_depth=0,
                    ),
                ),
                agents=[
                    AgentRecord(
                        id="agent-1",
                        type=AgentType.GEMINI,
                        state=AgentState.RUNNING,
                        started_at=now,
                        updated_at=now,
                        worker_id="worker-1",
                        current_job_id="job-1",
                    )
                ],
                jobs=[
                    JobRecord(
                        id="job-1",
                        agent_id="agent-1",
                        kind=JobKind.TASK,
                        state=JobState.RUNNING,
                        input_text="long-running",
                        created_at=now,
                        updated_at=now,
                        started_at=now,
                    )
                ],
            )
            StateStore(state_path).save(persisted)

            restored = self._manager(state_path)
            detail = await restored.get_agent("agent-1")
            task = await restored.get_task("job-1")

            self.assertEqual(detail.agent.state, AgentState.STOPPED)
            self.assertIsNone(detail.agent.worker_id)
            self.assertEqual(task.task.state, JobState.FAILED)
            self.assertIn("Interrupted by supervisor restart", task.task.summary)

    async def test_second_agent_stays_pending_when_worker_capacity_is_full(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = self._manager(Path(tmp_dir) / "state.db", max_active_agents=4, mock_worker_capacity=1)

            first = await manager.start_agent(StartAgentRequest(type=AgentType.GEMINI, initial_task="boot-1"))
            await asyncio.sleep(0.7)
            first_detail = await manager.get_agent(first.agent.id)
            self.assertEqual(first_detail.agent.state, AgentState.IDLE)

            second = await manager.start_agent(StartAgentRequest(type=AgentType.GEMINI, initial_task="boot-2"))
            second_detail = await manager.get_agent(second.agent.id)
            refreshed_first = await manager.get_agent(first.agent.id)

            self.assertEqual(second_detail.agent.state, AgentState.PENDING)
            self.assertEqual(refreshed_first.agent.state, AgentState.IDLE)

    async def test_clear_terminated_agents_removes_stopped_and_failed_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = self._manager(Path(tmp_dir) / "state.db")

            stopped = await manager.start_agent(StartAgentRequest(type=AgentType.GEMINI, initial_task="boot"))
            await asyncio.sleep(0.7)
            await manager.stop_agent(stopped.agent.id)

            failed_id = "failed-agent"
            now = datetime.now(UTC)
            manager._agents[failed_id] = AgentRecord(
                id=failed_id,
                type=AgentType.GEMINI,
                state=AgentState.FAILED,
                updated_at=now,
            )

            active = await manager.start_agent(StartAgentRequest(type=AgentType.GEMINI, initial_task="active"))
            await asyncio.sleep(0.1)

            await manager.clear_terminated_agents()

            self.assertNotIn(stopped.agent.id, manager._agents)
            self.assertNotIn(failed_id, manager._agents)
            self.assertIn(active.agent.id, manager._agents)
            self.assertEqual(manager._audits[-1].status, AuditStatus.ACCEPTED)


if __name__ == "__main__":
    unittest.main()
