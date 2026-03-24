from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from app.models import MachineRecord, PersistedState, WorkerPoolState
from app.services.state_store import StateStore


class StateStoreTests(unittest.TestCase):
    def test_sqlite_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(Path(tmp_dir) / "supervisor_state.db")
            now = datetime.now(UTC)
            state = PersistedState(
                machine=MachineRecord(
                    id="machine-1",
                    name="test-machine",
                    status="online",
                    started_at=now,
                    updated_at=now,
                    worker_pool=WorkerPoolState(
                        desired_workers=2,
                        busy_workers=0,
                        idle_workers=2,
                        queue_depth=0,
                    ),
                )
            )

            store.save(state)
            loaded = store.load()

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.machine.id, "machine-1")
            self.assertEqual(loaded.machine.name, "test-machine")

    def test_migrates_legacy_json_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "supervisor_state.db"
            json_path = db_path.with_suffix(".json")
            now = datetime.now(UTC)
            legacy_state = PersistedState(
                machine=MachineRecord(
                    id="machine-legacy",
                    name="legacy-machine",
                    status="online",
                    started_at=now,
                    updated_at=now,
                    worker_pool=WorkerPoolState(
                        desired_workers=1,
                        busy_workers=0,
                        idle_workers=1,
                        queue_depth=0,
                    ),
                )
            )
            json_path.write_text(legacy_state.model_dump_json(indent=2), encoding="utf-8")

            store = StateStore(db_path)
            loaded = store.load()

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.machine.id, "machine-legacy")
            self.assertTrue(db_path.exists())


if __name__ == "__main__":
    unittest.main()
