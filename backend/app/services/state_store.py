from __future__ import annotations

import sqlite3
from pathlib import Path

from app.models import PersistedState


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> PersistedState | None:
        if self._uses_json():
            return self._load_json(self.path)
        self._ensure_parent()
        self._migrate_legacy_json_if_present()
        if not self.path.exists():
            return None
        connection = sqlite3.connect(self.path)
        try:
            self._ensure_schema(connection)
            row = connection.execute("SELECT payload FROM supervisor_state WHERE id = 1").fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        return PersistedState.model_validate_json(row[0])

    def save(self, state: PersistedState) -> None:
        if self._uses_json():
            self._save_json(self.path, state)
            return
        self._ensure_parent()
        payload = state.model_dump_json(indent=2)
        connection = sqlite3.connect(self.path)
        try:
            self._ensure_schema(connection)
            connection.execute(
                """
                INSERT INTO supervisor_state (id, payload, updated_at)
                VALUES (1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (payload,),
            )
            connection.commit()
        finally:
            connection.close()

    def _uses_json(self) -> bool:
        return self.path.suffix.lower() == ".json"

    def _ensure_parent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _load_json(path: Path) -> PersistedState | None:
        if not path.exists():
            return None
        return PersistedState.model_validate_json(path.read_text(encoding="utf-8"))

    @staticmethod
    def _save_json(path: Path, state: PersistedState) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        tmp_path.replace(path)

    @staticmethod
    def _ensure_schema(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS supervisor_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def _migrate_legacy_json_if_present(self) -> None:
        legacy_json = self.path.with_suffix(".json")
        if self.path.exists() or not legacy_json.exists():
            return
        state = self._load_json(legacy_json)
        if state is None:
            return
        self.save(state)
