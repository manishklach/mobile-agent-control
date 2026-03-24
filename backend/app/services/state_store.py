from __future__ import annotations

from pathlib import Path

from app.models import PersistedState


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> PersistedState | None:
        if not self.path.exists():
            return None
        return PersistedState.model_validate_json(self.path.read_text(encoding="utf-8"))

    def save(self, state: PersistedState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        tmp_path.replace(self.path)
