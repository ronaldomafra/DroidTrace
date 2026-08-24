from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class AnalysisRecord:
    """A persisted analysis result; raw log input is intentionally excluded."""

    created_at: str
    prompt: str
    result: str
    model: str | None
    number: int | None = None

    @classmethod
    def from_dict(cls, data: object) -> AnalysisRecord | None:
        if not isinstance(data, dict):
            return None
        created_at = data.get("created_at")
        prompt = data.get("prompt")
        result = data.get("result")
        model = data.get("model")
        number = data.get("number")
        if not all(isinstance(value, str) for value in (created_at, prompt, result)):
            return None
        if model is not None and not isinstance(model, str):
            return None
        if number is not None and not isinstance(number, int):
            return None
        return cls(created_at, prompt, result, model, number)

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "created_at": self.created_at,
            "prompt": self.prompt,
            "result": self.result,
            "model": self.model,
        }
        if self.number is not None:
            data["number"] = self.number
        return data


@dataclass
class Session:
    id: str
    name: str
    started_at: str
    ended_at: str | None
    provider: str | None
    model: str | None
    device_serial: str | None = None
    filters: dict[str, object] = field(default_factory=dict)
    analyses: list[AnalysisRecord] = field(default_factory=list)
    recording_paths: list[Path] = field(default_factory=list)

    @property
    def start(self) -> str:
        return self.started_at

    @property
    def end(self) -> str | None:
        return self.ended_at


class SessionRepository:
    """Stores session metadata as one atomically-written JSON document per session."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)

    def create(
        self,
        *,
        name: str,
        provider: str | None,
        model: str | None,
        device_serial: str | None = None,
        filters: dict[str, object] | None = None,
    ) -> Session:
        session = Session(
            id=uuid4().hex,
            name=name,
            started_at=datetime.now(timezone.utc).isoformat(),
            ended_at=None,
            provider=provider,
            model=model,
            device_serial=device_serial,
            filters=dict(filters or {}),
        )
        self.save(session)
        return session

    def save(self, session: Session) -> Path:
        target = self._path_for(session.id)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(self._to_dict(session), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)
        return target

    def load(self, session_id: str) -> Session | None:
        try:
            data = json.loads(self._path_for(session_id).read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        return self._from_dict(data)

    def recent(self, limit: int | None = None) -> list[Session]:
        try:
            paths = self.directory.glob("*.json")
        except OSError:
            return []
        sessions = [session for path in paths if (session := self._load_path(path)) is not None]
        sessions.sort(key=lambda session: session.started_at, reverse=True)
        return sessions if limit is None else sessions[:limit]

    def _path_for(self, session_id: str) -> Path:
        return self.directory / f"{session_id}.json"

    def _load_path(self, path: Path) -> Session | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        return self._from_dict(data)

    @staticmethod
    def _to_dict(session: Session) -> dict[str, object]:
        return {
            "id": session.id,
            "name": session.name,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "provider": session.provider,
            "model": session.model,
            "device_serial": session.device_serial,
            "filters": session.filters,
            "analyses": [record.to_dict() for record in session.analyses],
            "recording_paths": [str(path) for path in session.recording_paths],
        }

    @staticmethod
    def _from_dict(data: object) -> Session | None:
        if not isinstance(data, dict):
            return None
        required_strings = ("id", "name", "started_at")
        if not all(isinstance(data.get(key), str) for key in required_strings):
            return None
        nullable_strings = ("ended_at", "provider", "model", "device_serial")
        if any(data.get(key) is not None and not isinstance(data.get(key), str) for key in nullable_strings):
            return None
        filters = data.get("filters", {})
        analyses = data.get("analyses", [])
        recording_paths = data.get("recording_paths", [])
        if not isinstance(filters, dict) or not isinstance(analyses, list) or not isinstance(recording_paths, list):
            return None
        records = [record for item in analyses if (record := AnalysisRecord.from_dict(item)) is not None]
        if len(records) != len(analyses) or not all(isinstance(path, str) for path in recording_paths):
            return None
        return Session(
            id=data["id"],
            name=data["name"],
            started_at=data["started_at"],
            ended_at=data.get("ended_at"),
            provider=data.get("provider"),
            model=data.get("model"),
            device_serial=data.get("device_serial"),
            filters=filters,
            analyses=records,
            recording_paths=[Path(path) for path in recording_paths],
        )
