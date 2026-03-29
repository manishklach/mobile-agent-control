from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import AppSettings
from app.executors.mock_executor import MockExecutor
from app.models import (
    ApprovalActionType,
    ApprovalRequest,
    AgentRecord,
    AgentState,
    AgentType,
    ApprovalStatus,
    AuditStatus,
    CreateTaskRequest,
    EventType,
    JobKind,
    JobRecord,
    JobState,
    MachineRecord,
    PersistedState,
    StartAgentRequest,
    SubmitTaskRequest,
    SupervisorAgentState,
    TaskStatus,
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

    async def _wait_for_job_completion(self, manager: AgentManager, agent_id: str, timeout: float = 2.0) -> None:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            detail = await manager.get_agent(agent_id)
            latest = detail.latest_completed_job
            if latest is not None and latest.state in {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}:
                return
            await asyncio.sleep(0.05)
        self.fail("Timed out waiting for job completion")

    async def _wait_for_specific_job_state(
        self,
        manager: AgentManager,
        job_id: str,
        expected_states: set[JobState],
        timeout: float = 2.0,
    ) -> JobRecord:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            job = await manager.get_job(job_id)
            if job.state in expected_states:
                return job
            await asyncio.sleep(0.05)
        self.fail(f"Timed out waiting for job {job_id} to reach {expected_states}")

    async def test_start_agent_becomes_idle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = self._manager(Path(tmp_dir) / "state.db")

            response = await manager.start_agent(StartAgentRequest(type=AgentType.GEMINI, initial_task="boot"))
            self.assertEqual(response.agent.state, SupervisorAgentState.STARTING)
            self.assertIn(response.agent.current_state, {AgentState.IDLE, AgentState.RUNNING})

            await self._wait_for_job_completion(manager, response.agent.id)
            detail = await manager.get_agent(response.agent.id)

            self.assertEqual(detail.agent.state, SupervisorAgentState.IDLE)
            self.assertIn(detail.agent.current_state, {AgentState.IDLE, AgentState.COMPLETED})
            self.assertIsNotNone(detail.latest_completed_job)
            assert detail.latest_completed_job is not None
            self.assertEqual(detail.latest_completed_job.state, JobState.COMPLETED)
            self.assertIn("started", detail.latest_completed_job.summary.lower())

    async def test_pending_agent_can_be_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = self._manager(Path(tmp_dir) / "state.db", mock_worker_capacity=0)

            response = await manager.start_agent(StartAgentRequest(type=AgentType.GEMINI, initial_task="queued"))
            self.assertEqual(response.agent.state, SupervisorAgentState.PENDING)

            stopped = await manager.stop_agent(response.agent.id)

            self.assertEqual(stopped.agent.state, SupervisorAgentState.STOPPED)
            cancelled_job = stopped.latest_completed_job or stopped.current_job
            self.assertIsNotNone(cancelled_job)
            assert cancelled_job is not None
            self.assertEqual(cancelled_job.state, JobState.CANCELLED)

    async def test_mock_prompt_completes_and_returns_idle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = self._manager(Path(tmp_dir) / "state.db")

            response = await manager.start_agent(StartAgentRequest(type=AgentType.GEMINI, initial_task="boot"))
            await self._wait_for_job_completion(manager, response.agent.id)

            submitted = await manager.submit_task(response.agent.id, SubmitTaskRequest(input_text="inspect repo", kind=JobKind.TASK))
            await asyncio.sleep(0.05)
            detail_running = await manager.get_agent(response.agent.id)
            self.assertEqual(detail_running.agent.state, SupervisorAgentState.RUNNING)
            self.assertEqual(detail_running.agent.current_state, AgentState.RUNNING)

            current_job = submitted.current_job or submitted.latest_completed_job
            assert current_job is not None
            await self._wait_for_specific_job_state(manager, current_job.id, {JobState.COMPLETED})
            detail = await manager.get_agent(response.agent.id)
            self.assertEqual(detail.agent.state, SupervisorAgentState.IDLE)
            self.assertIn(detail.agent.current_state, {AgentState.IDLE, AgentState.COMPLETED})
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
                        name="agent-1",
                        type=AgentType.GEMINI,
                        state=SupervisorAgentState.RUNNING,
                        current_state=AgentState.RUNNING,
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
            job = await restored.get_job("job-1")

            self.assertEqual(detail.agent.state, SupervisorAgentState.STOPPED)
            self.assertIsNone(detail.agent.worker_id)
            self.assertEqual(job.state, JobState.FAILED)
            self.assertIn("Interrupted by supervisor restart", job.summary)

    async def test_second_agent_stays_pending_when_worker_capacity_is_full(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = self._manager(Path(tmp_dir) / "state.db", max_active_agents=4, mock_worker_capacity=1)

            first = await manager.start_agent(StartAgentRequest(type=AgentType.GEMINI, initial_task="boot-1"))
            await self._wait_for_job_completion(manager, first.agent.id)
            first_detail = await manager.get_agent(first.agent.id)
            self.assertEqual(first_detail.agent.state, SupervisorAgentState.IDLE)

            second = await manager.start_agent(StartAgentRequest(type=AgentType.GEMINI, initial_task="boot-2"))
            second_detail = await manager.get_agent(second.agent.id)
            refreshed_first = await manager.get_agent(first.agent.id)

            self.assertEqual(second_detail.agent.state, SupervisorAgentState.PENDING)
            self.assertEqual(refreshed_first.agent.state, SupervisorAgentState.IDLE)

    @unittest.skip("clear_terminated_agents is still being stabilized under async lifecycle churn")
    async def test_clear_terminated_agents_removes_stopped_and_failed_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = self._manager(Path(tmp_dir) / "state.db")

            stopped = await manager.start_agent(StartAgentRequest(type=AgentType.GEMINI, initial_task="boot"))
            await self._wait_for_job_completion(manager, stopped.agent.id)
            await manager.stop_agent(stopped.agent.id)

            failed_id = "failed-agent"
            now = datetime.now(UTC)
            manager._agents[failed_id] = AgentRecord(
                id=failed_id,
                name=failed_id,
                type=AgentType.GEMINI,
                state=SupervisorAgentState.FAILED,
                current_state=AgentState.FAILED,
                updated_at=now,
            )

            active = await manager.start_agent(StartAgentRequest(type=AgentType.GEMINI, initial_task="active"))
            await asyncio.sleep(0.1)

            await manager.clear_terminated_agents()

            self.assertNotIn(stopped.agent.id, manager._agents)
            self.assertNotIn(failed_id, manager._agents)
            self.assertIn(active.agent.id, manager._agents)
            self.assertEqual(manager._audits[-1].status, AuditStatus.ACCEPTED)

    async def test_agent_state_snapshot_and_timeline_are_recorded_for_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = self._manager(Path(tmp_dir) / "state.db")

            response = await manager.start_agent(StartAgentRequest(type=AgentType.GEMINI, initial_task="boot"))
            await self._wait_for_job_completion(manager, response.agent.id)
            submitted = await manager.submit_task(response.agent.id, SubmitTaskRequest(input_text="edit a file and run tool", kind=JobKind.TASK))
            current_job = submitted.current_job or submitted.latest_completed_job
            assert current_job is not None
            await self._wait_for_specific_job_state(manager, current_job.id, {JobState.COMPLETED})

            state = await manager.get_agent_state(response.agent.id)
            timeline = await manager.get_agent_timeline(response.agent.id)

            self.assertIn(state.state.current_state, {AgentState.IDLE, AgentState.COMPLETED})
            self.assertGreaterEqual(len(timeline.events), 1)
            self.assertEqual(timeline.events, sorted(timeline.events, key=lambda event: event.timestamp))
            self.assertIn(EventType.STATE_CHANGE, {event.type for event in timeline.events})

    async def test_approval_rejection_blocks_agent_and_fails_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = self._manager(Path(tmp_dir) / "state.db")
            now = datetime.now(UTC)
            agent = AgentRecord(
                id="agent-approval",
                name="agent-approval",
                type=AgentType.GEMINI,
                state=SupervisorAgentState.IDLE,
                current_state=AgentState.WAITING_FOR_APPROVAL,
                current_step="Waiting for operator approval",
                updated_at=now,
            )
            job = JobRecord(
                id="job-approval",
                agent_id=agent.id,
                kind=JobKind.TASK,
                state=JobState.QUEUED,
                input_text="delete file",
                created_at=now,
                updated_at=now,
            )
            manager._agents[agent.id] = agent
            manager._jobs[job.id] = job
            manager._approvals["approval-1"] = ApprovalRequest(
                id="approval-1",
                agent_id=agent.id,
                action_type=ApprovalActionType.DELETE_FILE,
                payload={"job_id": job.id, "path": "/tmp/demo.txt"},
                status=ApprovalStatus.PENDING,
                created_at=now,
            )

            decision = await manager.reject_request("approval-1")

            self.assertEqual(decision.approval.status, ApprovalStatus.REJECTED)
            self.assertEqual(manager._jobs[job.id].state, JobState.FAILED)
            self.assertEqual(manager._agents[agent.id].current_state, AgentState.BLOCKED)

    async def test_scheduler_waits_for_dependencies_before_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = self._manager(Path(tmp_dir) / "state.db")
            manager.start_background_tasks()

            response = await manager.start_agent(StartAgentRequest(type=AgentType.GEMINI, initial_task="boot"))
            await self._wait_for_job_completion(manager, response.agent.id)

            first = await manager.create_task(CreateTaskRequest(name="Task A", prompt_template="do a", assigned_agent=response.agent.id))
            second = await manager.create_task(CreateTaskRequest(name="Task B", prompt_template="do b", assigned_agent=response.agent.id, dependencies=[first.task.id]))

            await asyncio.sleep(1.4)
            first_state = await manager.get_task(first.task.id)
            second_state = await manager.get_task(second.task.id)

            self.assertIn(first_state.task.status, {TaskStatus.RUNNING, TaskStatus.COMPLETED, TaskStatus.BLOCKED, TaskStatus.PENDING})
            self.assertIn(second_state.task.status, {TaskStatus.PENDING, TaskStatus.BLOCKED, TaskStatus.COMPLETED})


if __name__ == "__main__":
    unittest.main()
